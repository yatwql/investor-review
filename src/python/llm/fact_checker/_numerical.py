"""fact_checker 子包 — 检查器 1：数值一致性（带语境感知）。

校验 LLM 引用的收益/回报率百分比与实际数据匹配。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import re

from src.python.llm.fact_checker import _coverage
from src.python.llm.fact_checker._constants import (
    _ATTACHED_SUBJECT_MAX_DIST,
    _DEFAULT_TOLERANCE_PCT,
    _EXPOSURE_KEYWORDS,
    _INDEX_CODES,
    _PROFIT_KEYWORDS,
    _MARKET_SCOPE_NOUNS,
    _PROPORTION_KEYWORDS,
    _REBALANCE_TARGET_KEYWORDS,
)
from src.python.llm.fact_checker._context import (
    _is_metric_word_context,
    _is_threshold_context,
    _is_weight_target_context,
    _is_benchmark_relative_context,
    _is_breakdown_sum_context,
    _is_contribution_sentence,
    _is_change_rate_context,
    _is_daily_change_context,
    _is_drawdown_context,
    _is_hypothetical_context,
    _is_non_rate_pre_word_context,
    _is_portfolio_daily_change_context,
    _is_portfolio_level_context,
    _is_position_weight_context,
    _is_replay_context,
    _is_table_weight_cell_context,
    _is_target_value_context,
    _is_trim_target_context,
    _is_weight_context,
    _is_win_rate_context,
)
from src.python.llm.fact_checker._utils import (
    _format_rate_pct,
)
from src.python.llm.fact_checker._patterns import _CODE_PATTERN, _PERCENT_PATTERN
from src.python.llm.fact_checker._utils import (
    _build_stock_change_map,
    _build_stock_rate_map,
    _calc_portfolio_values,
    _clause_span,
    _enclosing_bracket_span,
    _extract_holding_map,
    _locate_subject_code,
    _locate_subject_in,
    _sentence_snippet,
    _split_sentences,
    _subject_spans,
    _unresolved_attached_subject,
)


@dataclass(frozen=True)
class PercentContext:
    """单条百分比数值的评估上下文（把 22 个逐参实参收成一组语义字段）。

    为什么要收：每新增一种语境（变化率 / 胜率 / 权重 / 相对基准 / 目标比例 /
    数值前文度量…）都要同时改签名、文档与唯一调用点；字段化后新增语境只加一个
    字段，调用点用 `replace()` 派生变体即可。

    Attributes:
        value / value_str: 数值与其原始文本（修正替换用原样字符串）。
        sentence / anchor: 所在句子与数值在句中的起始位置（主体归属与语境窗口用）。
        stock_rates_abs / stock_rates: `{code: 收益率}` 的绝对值映射（容差比较）与带符号映射（修正输出）。
        holding_codes / name_to_code: 持仓代码集合与「名称 → 代码」映射（主体定位来源）。
        profit_rate / profit_rate_signed / profit_sign: 组合总收益率（绝对值 / 带符号）与盈亏方向词。
        tolerance_pct / drawdown_pct: 容差（百分点）与实际最大回撤。
        stock_changes: `{code: 单日涨跌}`（单日行情语境校验）。
        is_drawdown / is_change_rate / is_daily_change: 回撤 / 环比同比 / 单日涨跌 语境开关。
        is_win_rate / is_weight / is_benchmark_relative / is_trim_target: 胜率 / 评分权重 /
            相对基准跑输跑赢 / 止盈减仓目标比例——四者均为**非收益率**语境。
        is_non_rate_metric: 数值紧邻前文是占比 / 份额 / 市值 / 仓位类度量（非收益率）。
    """

    value: float
    value_str: str
    sentence: str
    stock_rates_abs: dict[str, float]
    holding_codes: set[str]
    profit_rate: float
    profit_sign: str
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT
    drawdown_pct: float | None = None
    is_drawdown: bool = False
    is_change_rate: bool = False
    is_daily_change: bool = False
    stock_changes: dict[str, float] | None = None
    name_to_code: dict[str, str] | None = None
    anchor: int = 0
    stock_rates: dict[str, float] | None = None
    profit_rate_signed: float | None = None
    is_win_rate: bool = False
    is_weight: bool = False
    is_benchmark_relative: bool = False
    is_trim_target: bool = False
    is_target_value: bool = False
    is_breakdown_sum: bool = False
    is_non_rate_metric: bool = False
    is_table_weight_cell: bool = False
    confirmed_rates: dict[str, str] | None = None


def _subject_distance(spans: list[tuple[int, int, str]], code: str, anchor: int) -> int:
    """该主体到数值的最小**边缘距离**；分句内找不到其出现处时返回极大值。"""
    best: int | None = None
    for start, end, mapped in spans:
        if mapped != code:
            continue
        dist = min(abs(start - anchor), abs(end - anchor))
        best = dist if best is None else min(best, dist)
    return best if best is not None else 10**6


def _is_market_scope_no_subject(
    sentence: str,
    anchor: int,
    holding_codes: set[str],
    name_to_code: dict[str, str] | None,
) -> bool:
    """判断数值是否落在「市场/板块口径且无持仓主体」的分句里。

    分句含板块/指数/大盘类名词，同时分句内出现不了任何持仓主体（代码/全名/简称/
    描述性尾名）时，该数值讲的是市场涨跌，不是持仓收益率——**归属不可知**，不能
    按收益率改写。

    实盘事故：「银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%」——
    板块单日涨跌被全局最近邻兜底改写成某品种收益率（先是 102.0%、后是 4.6%，随
    最近邻漂移），回写缓存后每轮让自检输入变化，多付一次 11~17s 的自检调用。

    Returns:
        命中「市场口径且无持仓主体」时为 True。
    """
    clause_start, clause_end = _clause_span(sentence, anchor)
    clause = sentence[clause_start:clause_end]
    _rel = anchor - clause_start

    spans = _subject_spans(clause, holding_codes, name_to_code)

    _noun_dist: int | None = None
    for noun in _MARKET_SCOPE_NOUNS:
        idx = clause.find(noun)
        while idx != -1:
            end = idx + len(noun)
            # 该出现处落在某持仓主体区间内 → 它是主体的一部分而非市场简称
            # （「华安纳指」里的「纳指」指 040046，不是纳指市场）。
            if not any(start < end and idx < span_end for start, span_end, _c in spans):
                dist = abs(end - _rel) if end <= _rel else abs(idx - _rel)
                _noun_dist = dist if _noun_dist is None else min(_noun_dist, dist)
            idx = clause.find(noun, idx + 1)
    if _noun_dist is None:
        return False
    if not spans:
        return True

    # 分句里既有市场名词也有持仓主体：按**谁更近**判定。指数中文名常与基金名重叠
    # （「纳斯达克100涨1.18%」——「纳斯达克100」同时是 016055 名称的一部分），
    # 只看「有没有主体」会把它当成持仓收益率；距离相等时判为市场口径（宁漏改）。
    subject_code = _locate_subject_in(clause, holding_codes, name_to_code, _rel)
    if subject_code is None:
        return True
    return _subject_distance(spans, subject_code, _rel) >= _noun_dist


#: 回看期/区间口径词：`022365 看空后 9 个交易日 −19.4%` 是区间价格涨跌，不是持仓
#: 收益率——带符号也绝不能拿去改写正文。
_LOOKBACK_WORDS = (
    "交易日",
    "区间",
    "以来",
    "此后",
    "期间",
    "年初",
    "本月",
    "上一交易日",
    "上年",
)


def _is_signed_return_after_code(ctx: PercentContext) -> bool:
    """带符号百分比紧跟在持仓代码后（``040046（+103.91%）``）→ 视为持仓收益率声称。

    走「无收益关键词」早退的声称里，这类是真错值的高发形态（LLM 常用括号列收益率而
    句子不带「收益率」字样）。判据刻意收窄：**必须**带正负号且紧邻持仓代码，且整句不含
    回看期词——集中度/敞口/风险度量都是无符号百分比，区间涨跌则可被回看期词挡下。
    """
    if any(word in ctx.sentence for word in _LOOKBACK_WORDS):
        return False
    value = ctx.value_str.strip()
    if not value:
        return False
    pattern = re.compile(rf"(\d{{6}})\s*[（(]?\s*[+＋\-−]\s*{re.escape(value)}\s*%")
    return any(match.group(1) in ctx.holding_codes for match in pattern.finditer(ctx.sentence))


def _rewrite_allowed(ctx: PercentContext) -> bool:
    """是否允许**自动改写**该数值（不满足则只报告、不改写）。

    改写直接进用户可见正文，门槛必须高于「报告一条提示」：
      - 带正负号（`+103.91%` / `−5.06%`）→ 明确是收益率；
      - 或数值紧邻「收益率/收益/浮盈/浮亏」字样（±6 字）→ 明确是收益率。
    无符号且无紧邻收益词的数值绝大多数是仓位/占比/同比等（批量重放实测：剩余的
    不符全部落在这类——13.4%/29.4%/6.6%），把权重改写成收益率是硬伤。
    """
    sign_char = ctx.sentence[max(0, ctx.anchor - 1) : ctx.anchor]
    if sign_char in ("+", "-", "＋", "−", "–"):
        return True
    nearby = ctx.sentence[max(0, ctx.anchor - 6) : ctx.anchor + 6]
    # 「上涨/下跌」这类涨跌动词同样是收益率声称（"招商银行上涨20.0%"）
    if any(word in nearby for word in ("收益率", "收益", "浮盈", "浮亏", "上涨", "下跌")):
        return True
    # 就近（±12 字）出现盈亏措辞也算收益率声称（"（8.5%）为唯一亏损QDII"）
    wider = ctx.sentence[max(0, ctx.anchor - 12) : ctx.anchor + 12]
    return any(word in wider for word in ("亏损", "浮亏", "浮盈", "盈利"))


def _ambiguous_multi_subject(ctx: PercentContext) -> bool:
    """多主体句中该数值的主体归因是否分不清（分不清 → 不改写也不告警）。

    判据：句中出现 ≥2 个不同持仓主体，且（最近主体边缘距离 > 贴身阈值，或两个不同
    主体的最近距离都 ≤ 贴身阈值）；同一主体的多处出现只取最近一次。
    """
    spans = _subject_spans(ctx.sentence, ctx.holding_codes, ctx.name_to_code)
    if not spans:
        return False
    nearest: dict[str, int] = {}
    for start, end, code in spans:
        dist = min(abs(start - ctx.anchor), abs(end - ctx.anchor))
        nearest[code] = min(nearest.get(code, dist), dist)
    if len(nearest) < 2:
        return False
    # 括号作用域优先：数值落在只含一个持仓代码的括号内时，归属由括号决定（与
    # `_locate_subject_code` 同口径），不因括号外更近的另一个主体而判歧义。
    bracket = _enclosing_bracket_span(ctx.sentence, ctx.anchor)
    if bracket is not None:
        codes = {
            match.group(0)
            for match in _CODE_PATTERN.finditer(ctx.sentence, bracket[0], bracket[1])
            if match.group(0) in ctx.holding_codes
        }
        if len(codes) == 1:
            return False
    ordered = sorted(nearest.values())
    return ordered[0] > _ATTACHED_SUBJECT_MAX_DIST or ordered[1] <= _ATTACHED_SUBJECT_MAX_DIST


#: 判定终态：``(issue, correction)``；``(None, None)`` = 本段判定为「跳过该数值」，
#: 而 ``None`` 表示「不归本段，继续下一段」——两种「无 issue」必须可区分。
_Final = tuple[str | None, tuple[str, str, str, str] | None]


@dataclass
class _Attribution:
    """跨步骤携带的归因中间态（只承载，不作判断；判断留在各步骤函数内）。"""

    allow_rewrite: bool = False
    best_code: str | None = None
    closest_ref: str = "_portfolio"


def _step_non_rate_contexts(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """① 非收益率语境早退（变化率/胜率/权重/相对基准/止盈目标/目标位/分项合计/表格权重列
    + 数值前文度量词）。

    分项合计与表格权重列用**近邻窗口**检测（数值紧邻对应语境词），避免同句其他真实收益率
    被连带跳过。「数值前文是占比/份额/市值/仓位」必须在收益语境判定之前：共现句
    （"最大持仓 12.3%，持仓收益率 +4.55%"）整句含「收益」，整句级判定救不了，只有局部
    前文能区分两个数值的语义。
    """
    if (
        ctx.is_change_rate
        or ctx.is_win_rate
        or ctx.is_weight
        or ctx.is_benchmark_relative
        or ctx.is_trim_target
        or ctx.is_target_value
        or ctx.is_breakdown_sum
        or ctx.is_table_weight_cell
    ):
        return None, None
    if ctx.is_non_rate_metric:
        return None, None
    return None


def _step_daily_change(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """② 单日/当日涨跌语境 → 按该品种 ``change_pct`` 校验（维度匹配）。

    无持仓主体（如"科创50单日重挫4.43%"的指数/大盘）或无单日涨跌数据 → 跳过，
    不误修正为个股收益率。
    """
    if not ctx.is_daily_change:
        return None
    subject = _locate_subject_code(ctx.sentence, ctx.holding_codes, ctx.name_to_code, ctx.anchor)
    change = ctx.stock_changes.get(subject) if subject and ctx.stock_changes else None
    if change is None:
        return None, None  # 无持仓主体或无单日涨跌数据 → 无法校验，跳过
    if abs(ctx.value - abs(change)) <= ctx.tolerance_pct:
        _coverage.note_verified()
        return None, None
    correct_str = _format_rate_pct(change)
    _ctx = _sentence_snippet(ctx.sentence)
    issue = f"单日涨跌数值 {ctx.value}% 与 {subject} 实际单日涨跌 {correct_str}%（句段：{_ctx}）"
    return issue, (ctx.value_str, correct_str, ctx.sentence, f"{subject}单日涨跌{correct_str}%")


def _step_proportion_words(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """③ 品种计数/比例语境（"3 只基金""过半持仓"）→ 跳过。"""
    if any(kw in ctx.sentence for kw in _PROPORTION_KEYWORDS):
        return None, None
    return None


def _step_drawdown(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """④ 回撤语境 → 与实际最大回撤比较（无回撤数据则无法校验，跳过）。"""
    if not ctx.is_drawdown:
        return None
    if ctx.drawdown_pct is None or ctx.drawdown_pct < 0.01:
        return None, None
    diff = abs(ctx.value - ctx.drawdown_pct)
    if diff <= ctx.tolerance_pct:
        _coverage.note_verified()
        return None, None
    correct_str = _format_rate_pct(ctx.drawdown_pct)
    _ctx = _sentence_snippet(ctx.sentence)
    issue = f"回撤相关数值 {ctx.value}% 与实际最大回撤 {correct_str}% 偏差超过容差（句段：{_ctx}）"
    return issue, (ctx.value_str, correct_str, ctx.sentence, f"回撤实际{correct_str}%")


def _step_profit_context_gate(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """⑤ 收益语境闸门：无收益关键词（或收益率过小）→ 无法校验。

    例外：带符号百分比紧跟持仓代码（``040046（+103.91%）``）本身就是持仓收益率声称，
    句子缺「收益率」字样不影响判定（见 :func:`_is_signed_return_after_code` 的收窄护栏）。

    另在此拦下「今日组合 +0.21%」这类**组合当日表现**：它既非个股收益率，也无组合当日
    收益基准可比；若留到全局最近邻兜底，会被改写成数值最接近的某只品种收益率。
    """
    is_profit_context = any(kw in ctx.sentence for kw in _PROFIT_KEYWORDS) or _is_signed_return_after_code(ctx)
    if not is_profit_context or ctx.profit_rate < 0.01:
        return None, None
    if _is_portfolio_daily_change_context(ctx.sentence, ctx.anchor):
        return None, None
    return None


def _step_portfolio_level(ctx: PercentContext, attr: _Attribution) -> _Final | None:
    """⑥ 组合级收益语境（"组合累计收益约10.0%"）→ 归到组合总收益率，不走个股路由。

    必须在主体定位前判定：同句含多个持仓代码时（如"组合累计收益10%，招商银行上涨8%，
    贵州茅台上涨15%"），组合收益数值若走个股路由会被误归到数值最近的个股。
    """
    if not _is_portfolio_level_context(ctx.sentence, ctx.anchor):
        return None
    if abs(ctx.value - ctx.profit_rate) <= ctx.tolerance_pct:
        _coverage.note_verified()
        return None, None
    signed = ctx.profit_rate_signed if ctx.profit_rate_signed is not None else ctx.profit_rate
    correct_str = _format_rate_pct(signed)
    _ctx = _sentence_snippet(ctx.sentence)
    issue = (
        f"收益相关数值 {ctx.value}% 与实际累计收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
    )
    _corr = (ctx.value_str, correct_str, ctx.sentence, f"组合实际收益率{correct_str}%") if attr.allow_rewrite else None
    return issue, _corr


def _step_metric_and_weight_target(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """⑦ 风险/财务类指标词（夏普/卡玛/VaR/波动率/分位/净利同比）与仓位目标措辞
    （"从 19.4% 减到 15% 以内"）紧邻的数值 → 不是持仓收益率。

    批量重放实测这两类贡献了不符的大头（净利 -6.6% 被判成 600900 的 61% 收益率、
    仓位 19.4% 被判成 64.1%）。
    """
    if _is_metric_word_context(ctx.sentence, ctx.anchor) or _is_weight_target_context(ctx.sentence, ctx.anchor):
        return None, None
    return None


def _step_attribution_ambiguity(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """⑧ 归因不可靠的三类形态 → 宁漏改不误改。

    - 多主体句的**归因歧义**：同句 ≥2 个持仓主体且最近主体不贴身（或两者都贴身）时，
      括号/顿号枚举让最近邻归因不可靠——实测把建设银行 +252.19% 归到工商银行、把仓位
      13.5% 归成持仓收益率（批量重放 10 份报告：不符 26 条里 20 条属此形态）。只挡
      「分不清」的，不挡「紧贴唯一主体」的（否则整份报告覆盖率被压到 8%）。
    - 阈值/比较语境的**无符号**百分比（"长江电力 20.7% 超过 15% 线"）是占比与阈值：同句
      别处出现「收益率」字样时会漏过整句级收益判定，按邻近主体归因就会拿占比去比收益率。
    - 数值紧贴一个解析不出持仓的名称（如简称「建信装备」）→ 主体归属不可知，不可用同句
      其他持仓的收益率去改写。
    """
    if _ambiguous_multi_subject(ctx):
        return None, None
    _sign_char = ctx.sentence[max(0, ctx.anchor - 1) : ctx.anchor]
    if _sign_char not in ("+", "-", "＋", "−", "–") and _is_threshold_context(ctx.sentence, ctx.anchor):
        return None, None
    if _unresolved_attached_subject(ctx.sentence, ctx.anchor, ctx.holding_codes, ctx.name_to_code):
        return None, None
    return None


def _step_subject_rates(ctx: PercentContext, attr: _Attribution) -> _Final | None:
    """⑨ 主体归因 + 按该主体收益率校验（容差内通过）。

    归因走 `_locate_subject_code`「紧邻优先 + 代码/全名最近兜底」（含代码、全名、简称、
    描述性尾名四来源），而非全局最近邻：同句含多个名称主体时（如"040046 收益率 +130.61%、
    建设银行收益率 +181.37%"）各数值各自就近归因。句中无名称/代码主体时回退全局最近邻。

    本步同时把归因结果写进 ``attr``（``best_code`` / ``closest_ref``）供最终产出行使用；
    「同句同品种已有收益率」的确认表也在此写入。
    """
    # 市场/板块口径且分句内无持仓主体 → 数值是市场涨跌，归属不可知，不改写。
    if _is_market_scope_no_subject(ctx.sentence, ctx.anchor, ctx.holding_codes, ctx.name_to_code):
        return None, None

    codes_in_sentence = _CODE_PATTERN.findall(ctx.sentence)
    index_codes_in_sentence = [c for c in codes_in_sentence if c in _INDEX_CODES]
    holding_codes_in_sentence = [c for c in codes_in_sentence if c in ctx.holding_codes]

    ref_rates: dict[str, float] = dict(ctx.stock_rates_abs)
    ref_rates["_portfolio"] = ctx.profit_rate
    attr.closest_ref = min(ref_rates, key=lambda k: abs(ctx.value - ref_rates[k]))

    name_code = _locate_subject_code(ctx.sentence, ctx.holding_codes, ctx.name_to_code, ctx.anchor)
    if name_code is not None and name_code in ctx.stock_rates_abs:
        best_code = name_code
    elif len(holding_codes_in_sentence) > 1:
        # 句中主体无收益率数据但多代码：按收益率最近者归因（历史语义，防仅按位置
        # 就近把数值错配到同句其他品种）。
        best_code = min(holding_codes_in_sentence, key=lambda c: abs(ctx.value - ctx.stock_rates_abs.get(c, 999)))
    elif holding_codes_in_sentence:
        best_code = holding_codes_in_sentence[0]
    else:
        # 句中无代码但以名称指代持仓（如"建设银行收益率+1.87%"）→ 名称定位到代码，
        # 否则该收益声称无法归因到具体品种，会误修正到数值最接近的无关品种。
        # 仅当该品种确有收益率数据时采用，否则回退组合收益率。
        best_code = None
    attr.best_code = best_code

    # 同句同品种只有一个持仓收益率：该品种的收益率已在同一句内确认过，本数值只能是
    # 别的口径（括号里的占比/贡献等），不参与收益率改写。
    # 实盘事故：「561910（-36.20%，7.3%）」——7.3% 是占比，却被改写成 -36.2%。
    if ctx.confirmed_rates is not None:
        _prev = ctx.confirmed_rates.get(best_code or "")
        if _prev is not None and _prev != ctx.value_str:
            return None, None

    # 策略 1：句中有明确持仓主体 → 按该主体实际收益率校验（容差内通过）；
    # 主体无收益率数据（ref 为 None）或无主体 → 回退全局最近邻（历史语义）。
    if best_code is not None:
        ref = ctx.stock_rates_abs.get(best_code)
        if ref is not None and abs(ctx.value - ref) <= ctx.tolerance_pct:
            if ctx.confirmed_rates is not None:
                ctx.confirmed_rates[best_code] = ctx.value_str
            _coverage.note_verified()
            return None, None
        if ref is None and abs(ctx.value - ref_rates[attr.closest_ref]) <= ctx.tolerance_pct:
            _coverage.note_verified()
            return None, None
    elif abs(ctx.value - ref_rates[attr.closest_ref]) <= ctx.tolerance_pct:
        _coverage.note_verified()
        return None, None

    # 策略 2：句中代码全部为指数代码
    if not holding_codes_in_sentence and index_codes_in_sentence:
        return None, None
    return None


def _step_non_holding_scopes(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """⑩ 非持仓语义段：贡献/归因、金融基准（国债/利率/通胀/GDP/CPI/PMI）→ 跳过。"""
    if _is_contribution_sentence(ctx.sentence):
        return None, None
    if any(kw in ctx.sentence for kw in ("国债", "利率", "通胀", "GDP", "CPI", "PMI")):
        return None, None
    return None


def _step_narrative_scopes(ctx: PercentContext, _attr: _Attribution) -> _Final | None:
    """⑪ 叙述性非收益率语境：仓位/占比、假设/情景、调仓目标、币种/敞口 → 跳过。"""
    if _is_position_weight_context(ctx.sentence):
        return None, None
    if _is_hypothetical_context(ctx.sentence):
        return None, None
    if any(kw in ctx.sentence for kw in _REBALANCE_TARGET_KEYWORDS):
        return None, None
    if any(kw in ctx.sentence for kw in _EXPOSURE_KEYWORDS):
        return None, None
    return None


def _emit_rate_issue(ctx: PercentContext, attr: _Attribution) -> _Final:
    """全部步骤均未拦下 → 判定为不一致，产出告警与（门槛满足时的）修正。

    修正值用**带符号**收益率（``stock_rates`` / ``profit_rate_signed``）以保留盈亏方向：
    亏损品种（如 518880 实际 -8.86%）必须输出 -8.86%，不得写成 +8.86%。最近邻比较仍用
    绝对值（``_PERCENT_PATTERN`` 不捕获负号，``ctx.value`` 恒为正，做的是幅度匹配）。
    """
    if attr.best_code:
        stock_rate = (ctx.stock_rates or ctx.stock_rates_abs).get(attr.best_code, 0)
        correct_str = _format_rate_pct(stock_rate)
        # 方向标注取**该品种**自己的盈亏，不沿用组合盈亏（否则亏损品种被标成「（盈利）」，
        # 修正明细读起来自相矛盾）
        _sign = "盈利" if stock_rate >= 0 else "亏损"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = (
            f"收益相关数值 {ctx.value}% 与 {attr.best_code} 的实际收益率 {correct_str}%"
            f"（{_sign}）偏差超过容差（句段：{_ctx}）"
        )
        _corr = (
            (ctx.value_str, correct_str, ctx.sentence, f"{attr.best_code}实际收益率{correct_str}%")
            if attr.allow_rewrite
            else None
        )
        return issue, _corr
    if attr.closest_ref != "_portfolio":
        stock_rate = (ctx.stock_rates or ctx.stock_rates_abs).get(attr.closest_ref, 0)
        correct_str = _format_rate_pct(stock_rate)
        _ctx = _sentence_snippet(ctx.sentence)
        issue = (
            f"收益相关数值 {ctx.value}% 与 {attr.closest_ref} 的实际收益率 {correct_str}%"
            f"（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
        )
        _corr = (
            (ctx.value_str, correct_str, ctx.sentence, f"{attr.closest_ref}实际收益率{correct_str}%")
            if attr.allow_rewrite
            else None
        )
        return issue, _corr
    signed = ctx.profit_rate_signed if ctx.profit_rate_signed is not None else ctx.profit_rate
    correct_str = _format_rate_pct(signed)
    _ctx = _sentence_snippet(ctx.sentence)
    issue = (
        f"收益相关数值 {ctx.value}% 与实际累计收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
    )
    _corr = (ctx.value_str, correct_str, ctx.sentence, f"组合实际收益率{correct_str}%") if attr.allow_rewrite else None
    return issue, _corr


#: 百分比判定步骤——**顺序即语义**：自上而下首个返回终态者定论，步骤函数只做本段判断。
#: 改这里的顺序等于改判定口径：须同步复核 `_context` 的各语境判定与
#: `docs/managements/llm-technical.md` 的事实校验口径说明，并跑全量 fact_checker 用例。
_GUARD_STEPS: tuple[Callable[[PercentContext, _Attribution], _Final | None], ...] = (
    _step_non_rate_contexts,
    _step_daily_change,
    _step_proportion_words,
    _step_drawdown,
    _step_profit_context_gate,
    _step_portfolio_level,
    _step_metric_and_weight_target,
    _step_attribution_ambiguity,
    _step_subject_rates,
    _step_non_holding_scopes,
    _step_narrative_scopes,
)


def _evaluate_percent_impl(ctx: PercentContext) -> _Final:
    """评估单个百分比数值（语境判定 → 主体归因 → 是否需要修正）。

    判定顺序由 :data:`_GUARD_STEPS` 单源维护（先「非收益率」早退 → 单日/回撤 → 收益语境
    → 主体归因 → 残余叙述语境），全部步骤都不拦下才判不一致。字段含义见
    :class:`PercentContext`。

    Returns:
        (issue_str_or_None, correction_or_None)
        correction = (wrong_value_str, correct_value_str, context_sentence, reason)
        reason 为修正语义（如"601939实际收益率187.12%"），供修正明细展示。
    """
    # 改写门槛是纯谓词（只看句子与位置），提前算一次供「组合级」与「产出」两步共用
    attr = _Attribution(allow_rewrite=_rewrite_allowed(ctx))
    for step in _GUARD_STEPS:
        verdict = step(ctx, attr)
        if verdict is not None:
            return verdict
    return _emit_rate_issue(ctx, attr)


def _evaluate_percent(ctx: PercentContext) -> tuple[str | None, tuple[str, str, str, str] | None]:
    """评估单个百分比并登记覆盖率（判定本体见 :func:`_evaluate_percent_impl`）。

    覆盖率是「有多少声称被真正比对过」的唯一来源：检查器过去只报「告警/检查项」，
    跳过的声称在统计上与「通过」无区别（实测一只基金的 8.5% 就这样消失）。
    """
    before = _coverage.verified_count()
    issue, correction = _evaluate_percent_impl(ctx)
    _coverage.note_claim(ctx, issue, before)
    return issue, correction


@dataclass(frozen=True)
class _DetectionRefs:
    """一次检查所需的持仓侧参考数据（构造一次、逐条声称复用）。"""

    stock_rates: dict[str, float]
    stock_rates_abs: dict[str, float]
    holding_codes: set[str]
    stock_changes: dict[str, float]
    name_to_code: dict[str, str]
    profit_rate: float
    profit_rate_signed: float
    profit_sign: str


def _build_detection_refs(holdings_details: list[dict] | None) -> _DetectionRefs:
    """构建持仓侧参考数据（收益率映射 / 代码集合 / 名称映射 / 单日涨跌 / 组合收益率）。"""
    values = _calc_portfolio_values(holdings_details)
    stock_rates = _build_stock_rate_map(holdings_details)
    holding_map = _extract_holding_map(holdings_details)
    return _DetectionRefs(
        stock_rates=stock_rates,
        stock_rates_abs={code: abs(rate) for code, rate in stock_rates.items()},
        holding_codes=set(holding_map.keys()),
        stock_changes=_build_stock_change_map(holdings_details),
        name_to_code={name: code for code, name in holding_map.items()},
        profit_rate=abs(values["total_profit_rate"]),
        profit_rate_signed=values["total_profit_rate"],
        profit_sign="盈利" if values["total_profit"] >= 0 else "亏损",
    )


def _make_percent_context(
    *,
    refs: _DetectionRefs,
    sentence: str,
    anchor: int,
    value: float,
    value_str: str,
    tolerance_pct: float,
    max_drawdown_pct: float | None,
    confirmed_rates: dict[str, str],
) -> PercentContext:
    """把「一句话 + 一个数值位置」的 14 项语境探测结果收成 :class:`PercentContext`。

    语境探测全部在此单点调用（每个 `_is_*_context` 只在这一处出现），新增语境时
    只改本函数与 `PercentContext` 字段两处。
    """
    return PercentContext(
        value=value,
        value_str=value_str,
        sentence=sentence,
        stock_rates_abs=refs.stock_rates_abs,
        holding_codes=refs.holding_codes,
        profit_rate=refs.profit_rate,
        profit_sign=refs.profit_sign,
        tolerance_pct=tolerance_pct,
        drawdown_pct=max_drawdown_pct,
        # 回撤语境只在给了回撤数据时探测（无数据即无法校验）
        is_drawdown=_is_drawdown_context(sentence, anchor) if max_drawdown_pct is not None else False,
        is_change_rate=_is_change_rate_context(sentence, anchor),
        is_daily_change=_is_daily_change_context(sentence, anchor),
        stock_changes=refs.stock_changes,
        name_to_code=refs.name_to_code,
        anchor=anchor,
        # 带符号收益率（修正输出保留盈亏方向）
        stock_rates=refs.stock_rates,
        profit_rate_signed=refs.profit_rate_signed,
        # 非收益率语境（胜率/评分权重/相对基准跑输跑赢/止盈减仓目标比例）
        is_win_rate=_is_win_rate_context(sentence, anchor),
        is_weight=_is_weight_context(sentence, anchor),
        is_benchmark_relative=_is_benchmark_relative_context(sentence, anchor),
        is_trim_target=_is_trim_target_context(sentence, anchor),
        # 目标位/估计值（"提到 25% 附近"）与「合计 = 分项之和」（"18.3%（12.5%+5.8%）"）
        is_target_value=_is_target_value_context(sentence, anchor),
        is_breakdown_sum=_is_breakdown_sum_context(sentence, anchor, value),
        # 同句内已确认的品种收益率（同品种第二个百分数只能是别的口径）
        confirmed_rates=confirmed_rates,
        # 表格并列裸百分比单元格（权重列/目标列）：归属不可知，不改写
        is_table_weight_cell=_is_table_weight_cell_context(sentence, anchor),
        # 数值前文语义（占比/份额/市值/仓位）：局部窗口判定，优先于整句收益语境
        is_non_rate_metric=_is_non_rate_pre_word_context(sentence, anchor),
    )


def check_numerical_consistency(
    text: str,
    holdings_details: list[dict] | None,
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT,
    max_drawdown_pct: float | None = None,
) -> tuple[list[str], int, int, list[tuple[str, str, str, str]]]:
    """检查 LLM 输出中的百分比数值与实际组合/个股数据是否一致。

    沿革：
    - v2：按句子粒度分析、跳过收益归因段落、优先按句中代码/名称归因、未识别到个股时
      回退组合总收益率、指数基准跳过分母
    - v3：返回修正信息列表（供 auto_correct 消费）+ 容差可配置
    - v4：回撤语境检测（"最大回撤"数值与实际最大回撤比较而非与收益率比较）

    Args:
        text: 去 HTML 标签后的纯文本。
        holdings_details: 持仓明细列表。
        tolerance_pct: 数值偏差容差（百分点），默认 1.0。
        max_drawdown_pct: 实际组合最大回撤百分比（可选）。

    Returns:
        (issues, total_checked, passed_count, corrections)
        corrections: [(wrong_value_str, correct_value_str, context_sentence, reason), ...]
    """
    issues: list[str] = []
    corrections: list[tuple[str, str, str, str]] = []
    if not text:
        return issues, 0, 0, corrections

    refs = _build_detection_refs(holdings_details)
    total_checked = 0
    passed = 0
    # 去重粒度是「(数值, 所在句)」而非仅数值：同一数值出现在多个句子里时各句语境不同
    # （「止盈约30%」与「收益率30%」），必须逐句各自判定；只按数值去重会让后续出现处
    # 永远不被检查，再叠加回写就形成「改一处、留其余」的自相矛盾正文。
    seen_values: set[tuple[str, str]] = set()
    # 逐句重置：句内已确认的「品种代码 → 收益率文本」（见 PercentContext.confirmed_rates）
    confirmed_rates: dict[str, str] = {}
    confirmed_sentence = ""

    for sentence in _split_sentences(text):
        # 跳过收益归因段落（贡献度占比不可与收益率直接比较）与策略回放/回测段落
        # （模拟指标与实际收益率不同源，不可比较）
        if _is_contribution_sentence(sentence) or _is_replay_context(sentence):
            continue
        if sentence != confirmed_sentence:
            confirmed_rates = {}
            confirmed_sentence = sentence

        for match in re.finditer(_PERCENT_PATTERN, sentence):
            value_str = match.group(1)
            occurrence_key = (value_str, sentence)
            if occurrence_key in seen_values:
                continue
            seen_values.add(occurrence_key)
            value = float(value_str)
            total_checked += 1

            issue, correction = _evaluate_percent(
                _make_percent_context(
                    refs=refs,
                    sentence=sentence,
                    anchor=match.start(),
                    value=value,
                    value_str=value_str,
                    tolerance_pct=tolerance_pct,
                    max_drawdown_pct=max_drawdown_pct,
                    confirmed_rates=confirmed_rates,
                )
            )
            if issue is None:
                passed += 1
            else:
                issues.append(issue)
                if correction:
                    corrections.append(correction)

    return issues, total_checked, passed, corrections
