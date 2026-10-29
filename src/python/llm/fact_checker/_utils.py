"""fact_checker 子包 — 基础工具函数。

HTML 剥离、句子拆分、上下文摘要、持仓映射与组合数值计算。
"""

from __future__ import annotations

import re

from src.python.llm.fact_checker._constants import (
    _ATTACHED_SUBJECT_MAX_DIST,
    _ATTACHED_SUBJECT_STRIP_WORDS,
    _NAME_ALIAS_MAP,
    _NON_SUBJECT_FILLER_WORDS,
)
from src.python.llm.fact_checker._patterns import _CODE_PATTERN

#: 叮在数值前的分隔/符号：剥掉后才能看到紧贴的「主体名称」汉字串。
_ATTACHED_SUBJECT_SEPARATORS = " \u3000\t:：，,、（）()「」“”\"'+-~≈%"

#: 剥离时依次尝试的词表：度量词（收益率/涨幅…）与时间/范围填充词（本季度/近期…）。
#: 两类都剥完后剩下的末尾汉字串才当作「主体名称」看待。
_ATTACHED_SUBJECT_PREFIX_WORDS: tuple[str, ...] = _ATTACHED_SUBJECT_STRIP_WORDS + _NON_SUBJECT_FILLER_WORDS


def _strip_html(html: str) -> str:
    """去除 HTML 标签，返回纯文本。"""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_sentences(text: str) -> list[str]:
    """按中英文句号、感叹号、问号、换行拆分句子。"""
    sentences = re.split(r"[。！？\n!?]", text)
    return [s.strip() for s in sentences if s.strip()]


def _sentence_snippet(sentence: str, max_len: int = 50) -> str:
    """截取句子前 max_len 字作为上下文摘要。"""
    s = sentence.replace(" ", "").strip()
    return s[:max_len] + "…" if len(s) > max_len else s


def _extract_holding_map(holdings_details: list[dict] | None) -> dict[str, str]:
    """从持仓明细构建 {code: name} 映射。"""
    result: dict[str, str] = {}
    for d in holdings_details or []:
        code = d.get("code", "") or ""
        name = d.get("name", "") or ""
        if code:
            result[code] = name
    return result


def _calc_portfolio_values(holdings_details: list[dict] | None) -> dict[str, float]:
    """计算组合核心数值。

    Returns:
        {"total_mv": float, "total_cost": float, "total_profit": float, "total_profit_rate": float}
    """
    total_mv = sum(d.get("market_value", 0) or 0 for d in holdings_details or [])
    total_cost = sum(d.get("cost", 0) or 0 for d in holdings_details or [])
    total_profit = total_mv - total_cost
    total_profit_rate = 0.0
    if total_cost and abs(total_cost) > 1e-10:
        total_profit_rate = (total_profit / total_cost) * 100
    return {
        "total_mv": total_mv,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_profit_rate": total_profit_rate,
    }


def _build_stock_rate_map(holdings_details: list[dict] | None) -> dict[str, float]:
    """构建 {code: profit_rate} 映射用于个股级校验。

    每个品种的盈亏比例来自持仓明细中的 profit_rate 字段（百分单位，
    orchestrator 已统一为百分比，如 187.12 = +187.12%），
    用于在 LLM 提及个股收益时进行精准比对，而非一律回退到组合总收益。
    """
    result: dict[str, float] = {}
    for d in holdings_details or []:
        code = d.get("code", "") or ""
        rate = d.get("profit_rate")
        if code and rate is not None:
            result[code] = float(rate)
    return result


def _build_stock_weight_map(holdings_details: list[dict] | None) -> dict[str, float]:
    """构建 {code: 组合权重%} 映射（市值占比）。

    用于品种代码近似纠正的佐证：LLM 笔误代码（如 161910）后紧跟的
    "规模达 X%"/"占比 X%"，与真实持仓代码（561910）的组合权重比对，
    容差内吻合才自动纠正，避免把合法引用的非持仓代码误改。
    市值缺失/为 0 的品种不纳入（无法计算占比，佐证不可用）。
    """
    result: dict[str, float] = {}
    mv_by_code: dict[str, float] = {}
    for d in holdings_details or []:
        code = d.get("code", "") or ""
        mv = d.get("market_value", 0) or 0
        if code and mv:
            mv_by_code[code] = float(mv)
    total = sum(mv_by_code.values())
    if not total:
        return result
    for code, mv in mv_by_code.items():
        result[code] = mv / total * 100
    return result


def _edit_distance_le_one(a: str, b: str) -> bool:
    """判断两串编辑距离是否 ≤1（6 位代码场景：同长即 ≤1 次替换）。

    用于品种代码近似纠正：LLM 常把持仓代码写错/易位一位数字
    （如 561910→161910）。仅需判 ≤1，做长度预检 + 逐位差异计数即可，
    不引入完整 Levenshtein。完全相同（diffs==0）亦返回 True，
    调用方已先排除有效集成员，无需在此剔除。
    """
    if len(a) != len(b):
        return False
    diffs = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            diffs += 1
            if diffs > 1:
                return False
    return True


def _build_stock_change_map(holdings_details: list[dict] | None) -> dict[str, float]:
    """构建 {code: change_pct} 映射（单日涨跌幅度，百分单位）。

    用于单日涨跌语境校验（如"今日下跌-3.41%"与 601939 的 change_pct=-3.41 比对）。
    """
    result: dict[str, float] = {}
    for d in holdings_details or []:
        code = d.get("code", "") or ""
        chg = d.get("change_pct")
        if code and chg is not None:
            result[code] = float(chg)
    return result


def _extract_core_name(name: str) -> str:
    """提取持仓名称的核心名（首个 ASCII 字母/数字之前的汉字部分）。

    如"华安纳斯达克100ETF联接基金A"→"华安纳斯达克"、"建设银行"→"建设银行"、
    "华安黄金ETF"→"华安黄金"。简称匹配按核心名做前缀包含判断，
    避免被"ETF联接基金A"等类型尾缀干扰。
    """
    if not name:
        return ""
    m = re.search(r"[A-Za-z0-9（(]", name)
    if m:
        return name[: m.start()]
    return name


# 描述性尾名匹配最小中文核心长度：LLM 缩写省略基金公司前缀后保留的
# 「描述词+产品后缀」（如"电池主题ETF"→561910"招商中证电池主题ETF"）须含
# ≥3 个汉字才算特异，避免"混合C""股票A"等纯产品型泛词被当作主体。
_DESCRIPTIVE_TAIL_MIN_CJK = 3


def _cjk_len(s: str) -> int:
    """统计字符串中的汉字（CJK 统一表意文字）个数。"""
    return sum(1 for ch in s if "一" <= ch <= "鿿")


def _leading_token(s: str) -> str:
    """取字符串前导的连续数字串（产品代号中的数字部分）。

    如"100ETF联接基金A"→"100"、"ETF"→""、"2040三年A"→"2040"。仅取数字——
    LLM 以「核心名+数字代号」缩写持仓时只保留指数/产品代码数字（"华安纳斯达克
    100"），不含类型尾缀字母（"ETF"等）；若后缀以字母开头（"ETF""C""A"）则
    无数字代号，不生成短尾候选。
    """
    m = re.match(r"[0-9]+", s)
    return m.group(0) if m else ""


def _match_descriptive_tail(
    sentence: str,
    name_to_code: dict[str, str] | None,
    anchor: int,
) -> tuple[str, int] | None:
    """按持仓核心名的「描述性后缀 + 产品后缀」匹配句中主体。

    LLM 常省略基金公司前缀指代持仓（如"电池主题ETF"→561910"招商中证电池
    主题ETF"），全名/别名匹配均失败时会回退全局最近邻 → 误路由到同句其他
    品种。逐持仓取核心名后缀（≥3 汉字）拼接产品后缀（"ETF"/"股票A"/"混合C"
    等）为完整候选，命中句中候选则按 (距锚点距离, 候选长度) 择优；产品后缀
    将候选锚定为产品名而非泛词（"科技""指数"等），避免无谓误路由。

    Returns:
        (code, 最近边距锚点距离)；无命中返回 None。
    """
    best_code: str | None = None
    best_dist: int | None = None
    best_len = 0
    for name, code in sorted((name_to_code or {}).items(), key=lambda kv: -len(kv[0])):
        core = _extract_core_name(name)
        rest = name[len(core) :]
        if len(core) < _DESCRIPTIVE_TAIL_MIN_CJK:
            continue
        # 核心名后缀从最长（完整核心名）到最短（≥3 汉字）逐一尝试；同一持仓
        # 的嵌套后缀可能命中更近位置（如"电池主题ETF"内再命中"池主题ETF"）。
        for start in range(0, len(core) - _DESCRIPTIVE_TAIL_MIN_CJK + 1):
            tail = core[start:]
            if _cjk_len(tail) < _DESCRIPTIVE_TAIL_MIN_CJK:
                continue
            cand = tail + rest
            for m in re.finditer(re.escape(cand), sentence):
                dist = min(abs(m.start() - anchor), abs(m.end() - anchor))
                if best_dist is None or dist < best_dist or (dist == best_dist and len(cand) > best_len):
                    best_code, best_dist, best_len = code, dist, len(cand)
            # 短尾候选：核心名后缀 + 类型后缀的「数字/字母前缀」——LLM 常省略类型尾缀
            # （"ETF联接基金A""(QDII)A"等）仅保留「核心名+数字代号」指代持仓（如
            # "华安纳斯达克100"→040046"华安纳斯达克100ETF联接基金A"、"博时纳斯达克100"
            # →016055），全名/别名/完整长尾候选均不命中 → 回退全局最近邻误路由。
            # 取 rest 的前导字母/数字串（"100ETF联接基金A"→"100"）拼核心名后缀，
            # 仅当前导串是 rest 真前缀（短于 rest）时生成，避免与完整候选重复。
            _short = _leading_token(rest)
            if _short and _short != rest:
                cand_short = tail + _short
                for m in re.finditer(re.escape(cand_short), sentence):
                    dist = min(abs(m.start() - anchor), abs(m.end() - anchor))
                    if best_dist is None or dist < best_dist or (dist == best_dist and len(cand_short) > best_len):
                        best_code, best_dist, best_len = code, dist, len(cand_short)
    if best_code is None or best_dist is None:
        return None
    return best_code, best_dist


#: 分句符（与 `_split_sentences` 的断句口径一致，另含顿号与换行）
_CLAUSE_SEPARATORS = "，,；;。、\n"


def _clause_span(sentence: str, anchor: int) -> tuple[int, int]:
    """返回 ``anchor`` 所在分句的区间 ``[start, end)``（按分句符切分）。"""
    start = 0
    for i in range(anchor - 1, -1, -1):
        if sentence[i] in _CLAUSE_SEPARATORS:
            start = i + 1
            break
    end = len(sentence)
    for i in range(anchor, len(sentence)):
        if sentence[i] in _CLAUSE_SEPARATORS:
            end = i
            break
    return start, end


_BRACKET_PAIRS: tuple[tuple[str, str], ...] = (("（", "）"), ("(", ")"))


def _enclosing_bracket_span(sentence: str, anchor: int) -> tuple[int, int] | None:
    """返回 ``anchor`` 所在最内层括号的区间 ``[start, end)``；不在括号内返回 None。

    只认「未闭合的最近左括号 + 其后第一个右括号」这一对，跨括号（上一括号已闭合）
    的候选被排除；中英文括号分别计算后取交集最紧的一对。
    """
    best: tuple[int, int] | None = None
    for left, right in _BRACKET_PAIRS:
        start = sentence.rfind(left, 0, anchor)
        if start == -1:
            continue
        end = sentence.find(right, anchor)
        if end == -1:
            continue
        # 左括号与新右括号之间若出现过右括号，说明 anchor 已在该括号之外
        if sentence.rfind(right, 0, anchor) > start:
            continue
        best = (start, end) if best is None else (max(best[0], start), min(best[1], end))
    return best


def _alias_normalized(text: str) -> str:
    """把文本中的常用简称替换为规范名（"纳指"→"纳斯达克"），供简称匹配复用。"""
    for alias, canon in sorted(_NAME_ALIAS_MAP.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(alias, canon)
    return text


def _unresolved_attached_subject(
    sentence: str,
    anchor: int,
    holding_codes: set[str],
    name_to_code: dict[str, str] | None,
) -> bool:
    """判断数值是否紧贴一个「未识别为持仓」的主体名（无法安全归因）。

    从数值向前取一段字符，反复剥掉分隔符与「收益率/涨幅/约/达」等度量词，剩下的
    末尾汉字串即为数值的紧邻主体（如「建信装备 +21.91%」→「建信装备」）。该串
    若不能被识别为任意持仓（代码/全名/简称/描述尾名），则数值的主体是一个检查器
    看不懂的名称，**归属不可知**——此时不能用同句其他持仓的收益率去改写它。

    实盘事故：「纳指联接 016055 +18.66%、建信装备 +21.91%」——「建信装备」是
    011506（建信高端装备）的口语简称，未能解析 → 回退到同句代码 016055，把正确
    的 +21.91% 改写成 016055 的 18.7%，同一句里两个品种报出同一数字。

    设计取舍：宁可漏改（不修正），不可误改（把对的改错）——改写会直接进入用户
    可见正文，而漏改只是保守。

    Args:
        sentence: 所在句子。
        anchor: 数值在句中的起始位置。
        holding_codes: 持仓代码集合。
        name_to_code: 「名称 → 代码」映射。

    Returns:
        紧邻主体存在但解析不出持仓时为 True（该数值应跳过校验）。
    """
    prefix = sentence[max(0, anchor - 24) : anchor].rstrip(_ATTACHED_SUBJECT_SEPARATORS)
    changed = True
    while changed:
        changed = False
        for word in _ATTACHED_SUBJECT_PREFIX_WORDS:
            if prefix.endswith(word):
                prefix = prefix[: -len(word)].rstrip(_ATTACHED_SUBJECT_SEPARATORS)
                changed = True
    token_match = re.search(r"[\u4e00-\u9fff]{2,12}$", prefix)
    if not token_match:
        return False
    token = token_match.group(0)
    # 可归因三选一：持仓名称包含该串（如「建信高端装备」⊂「建信高端装备股票A」，
    # 省略类型尾缀的完整核心名）、或常规主体匹配（代码/别名/描述尾名）能解析。
    if any(token in name for name in (name_to_code or {})):
        return False
    return not _has_subject_candidate(token, holding_codes, name_to_code, len(token) - 1)


def _has_subject_candidate(
    text: str,
    holding_codes: set[str],
    name_to_code: dict[str, str] | None,
    anchor: int,
) -> bool:
    """分句内是否出现任何可归因主体（代码 / 全名 / 简称 / 描述性尾名）。

    简称与尾名用与 :func:`_locate_subject_in` 同源的口径探测，避免「分句里有主体
    但没识别出来」而错误回退全句、被远处的另一个主体抢走归属。
    """
    if any(code in holding_codes for code in _CODE_PATTERN.findall(text)):
        return True
    for name in name_to_code or {}:
        if name in text:
            return True
    norm = _alias_normalized(text)
    if norm != text:
        for name in name_to_code or {}:
            core = _extract_core_name(name)
            if len(core) >= 2 and core in norm:
                return True
    return _match_descriptive_tail(text, name_to_code, anchor) is not None


def _locate_subject_code(
    sentence: str,
    holding_codes: set[str],
    name_to_code: dict[str, str] | None,
    anchor: int,
) -> str | None:
    """定位数值的主体持仓代码——作用域优先：括号 > 分句 > 全句。

    1. **括号作用域**：数值落在某对括号内、且括号内有持仓**代码**时取该代码。
       「超短债（012325，最大持仓12.3%，持仓收益率+4.55%）」的 +4.55% 属括号内
       012325，不会因括号闭合符让后一个代码在距离上更近而误判。只认代码：标识符
       形式无歧义；名称留给下级，避免括号内首个全名吃掉括号内全部数值。
    2. **分句作用域**：主体通常写在本分句内（「超短债（012325）持仓收益率+45.5%，
       华宝增强债券A（240012）收益率为-9.0%」——+45.5% 属前一分句）。本分句能识别
       出任何主体时只在本分句内归因。
    3. **全句**：分句内无主体时回退全句四来源匹配（保留「句中唯一代码钉扎」语义）。

    各级内部规则见 :func:`_locate_subject_in`。
    """
    span = _enclosing_bracket_span(sentence, anchor)
    if span is not None:
        for cm in _CODE_PATTERN.finditer(sentence, span[0], span[1]):
            if cm.group(0) in holding_codes:
                return cm.group(0)

    clause_start, clause_end = _clause_span(sentence, anchor)
    clause = sentence[clause_start:clause_end]
    if clause != sentence and _has_subject_candidate(clause, holding_codes, name_to_code, anchor - clause_start):
        return _locate_subject_in(clause, holding_codes, name_to_code, anchor - clause_start)
    return _locate_subject_in(sentence, holding_codes, name_to_code, anchor)


def _locate_subject_in(
    sentence: str,
    holding_codes: set[str],
    name_to_code: dict[str, str] | None,
    anchor: int,
) -> str | None:
    """在给定文本内定位数值主体（四来源：代码 → 全名 → 简称归一 → 描述性尾名）。

    主体来源分四级：句中持仓代码 → 持仓全名 → 简称归一化 → 描述性尾名。
    采用「紧邻优先 + 可靠主体兜底」：
      - 任一来源的主体若紧贴该数值（主体边缘距数值 ≤ _ATTACHED_SUBJECT_MAX_DIST），
        取其中最近者为其主体——同句含代码与多个名称主体时（"040046 收益率
        +130.61%、建设银行收益率 +181.37%"）181.37 紧邻建设银行 → 归 601939，
        不再被句内唯一代码 040046 钉扎误修正；
      - 无紧邻主体时，若句中已有代码/全名则取其中最近者（代码钉扎优先，防远距
        别名/尾名误覆盖；如"040046 ... +130% ... 与博时纳斯达克
        100合计17.4%"，+130% 归最近的代码 040046 而非 17 字符外的尾名 016055）；
      - 仅当句中既无代码也无全名时才以最近的简称/尾名候选作为主体（历史兜底）。

    最近边距离（min(abs(idx-anchor), abs(idx+len(subject)-anchor))）：名称与数值
    相邻时（如"建设银行收益率+171.23%"）若只按起点距离 abs(idx-anchor)，名称
    起点距数值可能与其相邻另一名称（如"工商银行"）平局，先迭代者胜出导致误路由。
    """
    best: str | None = None
    best_dist: int | None = None
    attached: str | None = None
    attached_dist: int | None = None
    has_reliable = False  # 句中是否存在代码或全名（可靠主体）

    def _offer(code: str, dist: int, into_best: bool = True) -> None:
        nonlocal best, best_dist, attached, attached_dist
        if dist <= _ATTACHED_SUBJECT_MAX_DIST:
            if attached_dist is None or dist < attached_dist:
                attached, attached_dist = code, dist
        if into_best and (best_dist is None or dist < best_dist):
            best, best_dist = code, dist

    for cm in _CODE_PATTERN.finditer(sentence):
        code = cm.group(0)
        if code not in holding_codes:
            continue
        has_reliable = True
        _offer(code, min(abs(cm.start() - anchor), abs(cm.end() - anchor)))

    for name, code in sorted((name_to_code or {}).items(), key=lambda kv: -len(kv[0])):
        idx = sentence.find(name)
        if idx == -1:
            continue
        has_reliable = True
        _offer(code, min(abs(idx - anchor), abs(idx + len(name) - anchor)))

    # 简称归一化匹配：先将句中常用简称归一化（"纳指"→"纳斯达克"等），
    # 再与持仓名称核心名前缀匹配。仅在句中确实出现简称（norm != sentence）
    # 时执行，避免额外开销与误匹配。句中已有代码/全名时简称仅以「紧邻」覆盖
    # （不参与全局最近竞争），防止远距简称误路由。
    norm = _alias_normalized(sentence)
    if norm != sentence:
        for name, code in sorted((name_to_code or {}).items(), key=lambda kv: -len(kv[0])):
            core = _extract_core_name(name)
            if len(core) < 2:
                continue
            idx = norm.find(core)
            if idx == -1:
                continue
            # 归一化位置映射回原句的近似：减去 norm[:idx] 中别名替换带来的
            # 长度增量（core 内部含 canon 时略有偏差，仅影响多候选排序，
            # 不影响唯一简称的归因）。
            _extra = sum((len(_c) - len(_a)) * norm[:idx].count(_c) for _a, _c in _NAME_ALIAS_MAP.items())
            _pos = idx - _extra
            _offer(code, min(abs(_pos - anchor), abs(_pos + len(core) - anchor)), into_best=not has_reliable)

    # 描述性尾名匹配（兜底）：按持仓核心名的「描述性后缀 + 产品后缀」匹配
    # （LLM 省略基金公司前缀，如"电池主题ETF"→561910、"华安纳斯达克100"
    # →040046）。与简称一致：句中已有代码/全名时尾名仅以「紧邻」覆盖。
    _tail = _match_descriptive_tail(sentence, name_to_code, anchor)
    if _tail is not None:
        _code, _dist = _tail
        _offer(_code, _dist, into_best=not has_reliable)

    if attached is not None:
        return attached
    return best
