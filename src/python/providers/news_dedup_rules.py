"""新闻去重规则原语 — 阈值常量、模板词表、相似度口径（纯函数，不含状态）。

本模块是**去重判定的唯一口径来源**：阈值常量（候选区/安全区/专名梯度/同源）、
模板词表与掩码、标题归一化、实体 bigram 提取、方向对立词对、规则指纹。

调用方：
  - ``providers/news_dedup.py`` —— 去重主流程与锚点采集（本模块名称在其 re-export）
  - ``scripts/eval-dedup-threshold.py`` —— 校准工具按当前口径重算锚点样本

拆出理由（可维护性）：规则数据（模板词表等）与纯原语聚在一处，主流程模块只留
锚点采集与比较循环；两者合计增长曾使单模块越过多文件的可维护行数上限。规则调整
只改本模块，指纹（``_rules_fingerprint``）随之自动变化。
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from ._news_dedup_tables import (
    _EVENT_GROUPS,
    _OPPOSITE_PAIRS,
    _STOP_BIGRAMS,
)


def _normalize_title(title: str) -> str:
    """标准化标题：去标点、去空格、去常见前缀，过滤通用数字模式降虚高。

    数字模式（百分比、金额、年份、排名标记）在不同新闻中可能无意共享，导致
    SequenceMatcher 比率虚高和实体 bigram 中数字 token 的虚假重叠。
    过滤后同时降低 bigram 提取噪声和比率比较的误判。

    用于跨源标题去重，消除"快讯：""收评"等差异。
    """
    for prefix in (
        "快讯",
        "收评",
        "收盘",
        "早评",
        "午评",
        "盘中",
        "盘后",
        "数据图解",
        "CCI快报",
        "市场动态",
        "市场洞察",
        "行业深度",
        "周刊提前读",
        "公司观察",
        "量化观察",
        "刷屏",
        "尾盘",
        "华尔街见闻早餐",
    ):
        if title.startswith(prefix):
            title = title[len(prefix) :]
            break
    # 同义收盘术语归一（收评/收盘/午评）：三者为同一收评簇语义（每日/午间
    # 市场收盘汇总），只在标题开头时被上方前缀剥离，出现在标题中段（如
    # "港股收评""港股午评"）会保留差异，导致相同收评簇共享 bigram 不足而漏判。
    # 校准发现 cross_skip 漏判簇（"港股收评恒指涨0.07%…" vs "8月18日港股收盘
    # 恒指涨0.07%…"）。归一为"收评"后两边带上同一 bigram 对齐，overlap 由 2 升至
    # 4、ratio≥0.50，进入安全区合并；且仅增不减，不破坏既有合并。
    title = title.replace("收盘", "收评").replace("午评", "收评")
    # 过滤通用数字模式，避免跨源去重时不同新闻因共享
    # "20%""25亿"等数字模式而获得虚高 SequenceMatcher 比率。
    # 日期模式（2026年/7月/8日）已在 _dedup_by_title 的 _RATIO_CLEAN 中处理，
    # 但前导日期（如 "7月18日美股成交额前20"）在 bigram 提取前剥离。
    title = re.sub(r"\d+(?:\.?\d+)?%", "", title)  # 20%、2.5%
    title = re.sub(r"\d+(?:\.?\d+)?[万亿]", "", title)  # 25亿、1.2万亿
    # 孤立 4 位年份数字（如 "WAIC 2026" → "WAIC"），避免不同年报道因共享英文
    # 事件名 + 不同年份标识导致 SequenceMatcher 比率虚高。
    title = re.sub(r"(?<=[a-zA-Z])\s*\d{4}\b", "", title)
    # 排名/列表标记（"前20""前10"），可安全移除的修饰语
    title = re.sub(r"前\d+", "", title)
    # 孤立 4 位年份数字（1900-2099），避免不同新闻因共享"2026"等年份数字
    # 在实体 bigram 提取和 SequenceMatcher 中产生虚假重叠。
    title = re.sub(r"\b(?:19|20)\d{2}\b", "", title)
    # 地震等量级模式（"3.5级""4.4级"），剥离后避免"级地震"模板虚高
    title = re.sub(r"\d+(?:\.?\d+)?级", "", title)
    # ⚠ 保留空格：剥离标点但保留单词间空格，避免英文 token 粘连
    # （"Blackwell AI" → blackwellai 无法切分，导致同事件两标题英文 token 不重叠）。
    title = re.sub(r"[^\w一-鿿 ]", "", title)
    return title.strip().lower()


# ── 高频财经常见动词/形容词/副词 — 不作为实体判定依据 ──────
# ⚠ 2026-08-17 校准扩充：财报/回购/指数/预警/地震/目标价等模板词
# 此前未覆盖，导致任何两条同类新闻（不同公司业绩快报、回购公告、指数行情、
# 天气预警）天然共享 3-6 个 bigram，跨源 bg≥3 形同虚设（实测误合并 ~70-80%）。
# 提取 bigram 前先整体掩码替换为占位符（见 _mask_stop），彻底消除模板词贡献，
# 也杜绝"累计|回购"跨词边界 bigram（计回）泄漏。

# 停用词掩码正则（长词优先，防重叠替换）：
# "累计回购" → "□□"，杜绝跨词边界 bigram（计回/购股）泄漏；
# 中文 bigram 提取时跳过含占位符的滑窗，使模板词彻底不贡献实体重叠。
_STOP_MASK_RE = re.compile("|".join(re.escape(w) for w in sorted(_STOP_BIGRAMS, key=len, reverse=True)))


def _mask_stop(text: str) -> str:
    """将停用模板词整体替换为占位符，供 bigram 提取前掩码。"""
    return _STOP_MASK_RE.sub("□", text)


@lru_cache(maxsize=4096)
def _extract_entity_bigrams_cached(text: str) -> frozenset[str]:
    """bigram 提取的缓存包装（返回不可变集合，调用方只做集合运算）。"""
    return frozenset(_extract_entity_bigrams(text))


def _extract_entity_bigrams(text: str) -> set[str]:
    """提取标题中的实体特征：中文 bigram + 英数 token + 长英文专名加权。

    中文实体判定依赖 2-gram 重叠；英数 token 补全"AI""AMD"等被中文
    正则过滤的专名；长度 ≥ 4 的英文专名（Anthropic/Meta/Helios 等）
    额外插入 _tk: 前缀虚拟 bigram，使共享专名在 bigram 计数中获得
    权重加成，避免因英文专名占比高但 token 条数少而漏过候选区。

    模板词（见 _STOP_BIGRAMS）在提取前被整体掩码替换为占位符，
    不产生任何中文 bigram——财报/回购/指数/预警等通用财经词汇不再
    虚增实体重叠（此前不同公司同类新闻天然共享 3-6 bigram）。
    孤立 4 位年份数字（2026 等）不作为专名 token。
    """
    # 英数 token：长度 ≥ 2 避免单字符噪声；孤立年份数字（19xx/20xx）
    # 为通用时间标识，不作专名。
    tokens = re.findall(r"[a-zA-Z]+|[0-9]+", text)
    result: set[str] = set()
    for t in tokens:
        t_lower = t.lower()
        if len(t_lower) >= 2 and not re.fullmatch(r"(?:19|20)\d{2}", t_lower):
            result.add(t_lower)
            # 长英文专名（≥4 字符）额外插入虚拟 bigram 占用位，
            # 提升共享专名在实体重叠计数中的权重（如 Anthropic+Meta
            # 在 bg 计数中额外贡献 2 点，使 bg=2+2=4 进入合并区）。
            if t_lower.isalpha() and len(t_lower) >= 4:
                result.add(f"_tk:{t_lower}")
    # 中文 bigram：先掩码模板词，再滑窗提取，跳过含占位符的窗口
    chinese_only = re.sub(r"[^一-鿿]", "", text)
    masked = _mask_stop(chinese_only)
    for i in range(len(masked) - 1):
        bg = masked[i : i + 2]
        if "□" in bg:
            continue
        result.add(bg)
    return result


# 用于 SequenceMatcher 的归一化——剥离通用日期模式，避免
# "2026年7月票房破25亿" 与 "2026年7月经营质量因子" 等完全不同的
# 新闻因共享日期格式而获得虚高 ratio，进入不必要的候选区。
# ⚠ 仅用于 ratio 计算，不影响 kept_norms（后者用于 bigram 提取）。
_RATIO_CLEAN = re.compile(r"\d{4}年|\d+月|\d+日")
# 英文词占位化：用于 ratio 比较时降权共享英文专名（Anthropic/Meta 等），
# 避免 SequenceMatcher 比率虚高。英文专名在 _extract_entity_bigrams
# 中已有独立处理，不影响 bigram 提取。
# ⚠ 按长度分桶占位（_tk2_/_tk4_/_tk6_）：统一 _tk_ 会让任意英文 token
# （msci/vn、ETF/CPI…）都共享同一占位符，人为抬高 ratio 0.1+；
# 分桶后仅同长度段英文词共享，恢复真实相似度。
_ENG_PLACEHOLDER = re.compile(r"[a-z]+")


def _eng_len_placeholder(match: re.Match) -> str:
    """按英文 token 长度分桶的占位符：2-3 字符 → _tk2_，4-5 → _tk4_，6+ → _tk6_。"""
    n = len(match.group())
    if n <= 2:
        return "_tk2_"
    if n <= 5:
        return "_tk4_"
    return "_tk6_"


# 42560 锚点分层采样验证：旧规则（候选区 0.30 + bg≥3 任意 ratio、
# 安全区 0.50 直接合并、bg=2 梯度 0.40）误合并率 ~70-80%。新规则收紧：
#   - 安全区：ratio ≥ 0.65 直接合并（改写型重复）；0.50~0.65 需专名 bg ≥ 2
#     （防"算力服务合同""指数上涨 N%"等模板骨架把 ratio 推到 0.5+ 的误合并）
#   - 候选区：ratio ≥ 0.35 进区；bg ≥ 3 合并；bg=2 需 ratio ≥ 0.375
#     且共享 bigram 含英数 token（含字母、非泛词否决表；纯中文公司名共享
#     如"英伟达/伟达"、共享数字如"纳斯达克100 vs KSE100"不代表同一事件）
# 阈值一律以这些常量为唯一来源（校准工具从本模块读，不自写一份数字——
# 两处各写一份会漂移，如工具正文写 0.30 而代码为 0.35，据此得到的建议无意义）。
_CROSS_CANDIDATE_RATIO = 0.35
_CROSS_BIGRAM_MIN = 3
_CROSS_BG2_RATIO = 0.375
_CROSS_DIRECT_RATIO = 0.65
_CROSS_SAFE_RATIO = 0.50
_SAME_SRC_BIGRAM_MIN = 4


# 跨源方向对立词对：共享实体 + 相反方向词分属两标题 → 不合并。
# 跨源会同时出现"暂缓加息"vs"将加息"这类方向对立报道，
# 而同源规则假设同源不出现对立报道——跨源必须显式防护。
# 2026-09-18 校准补充：金价类"站稳 vs 跌破"（如"金价站稳4000美元上方"vs
# "现货黄金跌破4000美元关口"，共享数字 token 4000，ratio 0.359）此前漏防。

# 共享 bigram 中的专名证据判定：英数 token 需含至少一个字母，或 _tk 虚拟专名。
# 2026-09-18 校准收紧：旧式 ^[a-z0-9]+$ 把**纯数字**也算作专名证据，导致
# 只共享数字的无关标题（指数名/榜单序号/型号数字 + 中文模板 bigram）靠 bg=2
# 梯度被误合并（实测 cross_merge_bg2 147 条中 27 条仅靠数字证据成立）。
# 数字共享不代表同一事件，不再作为专名证据。
_TOKEN_LIKE = re.compile(r"^(?=.*[a-z])[a-z0-9]+$|^_tk:[a-z]+$")

# bg=2 梯度的泛词否决表（锚点 7.8 万对实测定档）：ai/etf 这类 2~3 字母串既是
# 跨主体高频共现的泛词、又与指标/板块缩写同形，仅凭「含字母」无法区分——
# 靠这些词过闸的 bg=2 合并抽样绝大多数为误合并（不同基金各自行情、不同指数、
# "20cm" 俚语、CE 认证标记）；CPI/PPI/IPO/AMD 类真发布会与公司缩写不在表内、
# 照常作专名证据（gdp 除外：2026-10-20 校准实证「沙特阿拉伯二季度GDP」与
# 「欧元区二季度GDP」共享 gdp 被合并，跨经济体数据发布非同一事件，同口径入表）；
# 误合并会静默丢掉一篇独立报道，可见重复不会，故宁可少合并不错合；
# 新泛词在校准抽样中现身时按同口径扩表（与 _STOP_BIGRAMS/
# _OPPOSITE_PAIRS 同为词表维护项）。本表已入规则指纹，改动自动分锚点时代。
_GENERIC_TOKENS: frozenset[str] = frozenset({"ai", "etf", "cm", "gb", "ce", "pcb", "gdp"})

# 跨源 bg=3 下限档的事件信号词组（2026-10-20 锚点回放定档）：实体重叠 ≠ 事件
# 重叠——同主体公司名天然贡献多个 bigram，bg=3 可由「同主体不同事件」对凑满
# （中际旭创「暗盘跌 vs 资金抢筹」、SK海力士「盘前跌 vs 上调目标价」）。仅
# overlap 恰为 bg=3 下限档引入本判据（≥4 实体证据更强，维持现状）：两标题
# 命中的事件词组须有交集（组内互认，立案/调查/留置/被查属同一事件类型），
# 否则不合并、落候选区保留。词表刻意排除职务/身份词（董事长/总经理——跨事件
# 普遍命中，会把「中投副总任命」与「卫通副总离任」误连）与泛状态词（新高/
# 反弹/放量——跨事件高频）；误合并会静默丢掉一篇独立报道，可见重复不会，
# 宁可少合并。词组入规则指纹，改动自动分锚点时代。


def share_event_group(text_a: str, text_b: str) -> bool:
    """两标题是否命中同一事件信号词组（bg=3 下限档事件一致性判据）。

    参数须为已归一化标题（调用方负责 ``_normalize_title``）。
    """
    return any(any(w in text_a for w in group) and any(w in text_b for w in group) for group in _EVENT_GROUPS)


def proper_noun_tokens(tokens: set[str]) -> list[str]:
    """共享项中的专名证据 token：``_TOKEN_LIKE`` 命中且不在泛词否决表（升序）。"""
    return sorted(t for t in tokens if _TOKEN_LIKE.match(t) and t not in _GENERIC_TOKENS)


def has_proper_noun_token(tokens: set[str]) -> bool:
    """共享项中是否含专名证据（``proper_noun_tokens`` 非空）。"""
    return bool(proper_noun_tokens(tokens))


#: 指纹探针：走一遍归一化 + 实体提取的真实路径，使指纹覆盖模板词表/正则/
#: 提取逻辑的变化（只堆常量清单会漏掉这些结构性调整）
_FINGERPRINT_PROBES: tuple[str, ...] = (
    "2026年7月票房破25亿 同比上涨3.5级预警",
    "XX公司：拟回购公司股份不超过1.2亿元 董事会审议通过",
    "美联储与英伟达AMD签署AI芯片采购协议",
)

#: 锚点记录的规则版本字段名（校准工具按它分规则时代）
ANCHOR_RULES_FIELD = "anchor_rules_version"


def _rules_fingerprint() -> str:
    """当前去重规则的指纹（阈值 + 模板词表 + 方向词对 + 正则 + 行为探针）。

    锚点文件是 append-only 累积：规则一调整，旧样本就成了「另一个时代的产物」，
    与新样本混在一起会让校准报告失真（曾实测 cross_skip 中 46% 的 ratio 低于
    当前候选区入口、cross_safe 中 508 条 merged 但 bg=0——均为收紧前的旧规则
    记录）。故每条锚点带上当时的指纹，校准工具据此只按当前时代的样本出结论，
    不必依赖「改规则记得同步文档」这类人工纪律。
    """
    import hashlib

    probes = "\n".join(
        f"{_normalize_title(p)}|{sorted(_extract_entity_bigrams(_normalize_title(p)))}" for p in _FINGERPRINT_PROBES
    )
    parts = [
        "|".join(
            str(v)
            for v in (
                _CROSS_CANDIDATE_RATIO,
                _CROSS_BIGRAM_MIN,
                _CROSS_BG2_RATIO,
                _CROSS_DIRECT_RATIO,
                _CROSS_SAFE_RATIO,
                _SAME_SRC_BIGRAM_MIN,
            )
        ),
        ",".join(sorted(_STOP_BIGRAMS)),
        ",".join(f"{a}>{b}" for a, b in _OPPOSITE_PAIRS),
        _TOKEN_LIKE.pattern,
        ",".join(sorted(_GENERIC_TOKENS)),
        ";".join(",".join(group) for group in _EVENT_GROUPS),
        _RATIO_CLEAN.pattern,
        _ENG_PLACEHOLDER.pattern,
        probes,
    ]
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:10]


#: 当前规则指纹（规则调整后自动变化，无须人工维护版本号）
_ANCHOR_RULES_VERSION = _rules_fingerprint()


def _has_opposite_direction(title_a: str, title_b: str) -> bool:
    """两标题是否含相反方向的词对（一正一反分属两标题）。"""
    return any((w1 in title_a and w2 in title_b) or (w2 in title_a and w1 in title_b) for w1, w2 in _OPPOSITE_PAIRS)


@lru_cache(maxsize=4096)
def _ratio_ready(norm: str) -> str:
    """归一标题 → 相似度比较串（去通用日期 + 英文专名按长度分桶占位）。

    这是纯字符串变换，同一份新闻标题在去重循环里会被作为「已保留项」参与
    数十次比较；按字符串缓存可避免每次都重跑两条正则（实测占比较耗时的
    可观比例）。缓存键是内容，不引入跨轮语义耦合。
    """
    return _ENG_PLACEHOLDER.sub(_eng_len_placeholder, _RATIO_CLEAN.sub("", norm))


@lru_cache(maxsize=4096)
def _char_multiset(norm: str) -> tuple[tuple[str, int], ...]:
    """比较串的字符多重集（排序后的 (字符, 次数) 元组，可直接哈希缓存）。"""
    return tuple(sorted(Counter(_ratio_ready(norm)).items()))


def _multiset_upper_bound(norm_a: str, norm_b: str) -> float:
    """相似度的**严格上界**：2·Σ_c min(count_a, count_b) / (len_a + len_b)。

    ``SequenceMatcher.ratio`` = 2M/T，其中 M 为匹配字符数；任意匹配方案里每个
    字符都要从两侧各消耗一个，故 M ≤ Σ_c min(count_a, count_b)（多重集交集）。
    该上界只需比较计数表，比构造两个 ``SequenceMatcher`` 便宜一个量级。
    """
    counts_a = dict(_char_multiset(norm_a))
    counts_b = dict(_char_multiset(norm_b))
    total = sum(counts_a.values()) + sum(counts_b.values())
    if total == 0:
        return 0.0
    shared = sum(min(count, counts_b.get(char, 0)) for char, count in counts_a.items())
    return 2.0 * shared / total


def _ratio_of_norms(norm_a: str, norm_b: str) -> float:
    """已归一标题的相似度（双向 SequenceMatcher 取 max）。

    SequenceMatcher 贪心匹配方向不对称（含多个英文占位块的串上
    ratio(a,b)≠ratio(b,a)，实测差异可达 0.18），取双向 max 消除方向偏差，
    保证同一对标题的判定与比较顺序无关。
    """
    from difflib import SequenceMatcher

    a = _ratio_ready(norm_a)
    b = _ratio_ready(norm_b)
    return max(
        SequenceMatcher(None, a, b).ratio(),
        SequenceMatcher(None, b, a).ratio(),
    )


def _ratio_of_norms_bounded(norm_a: str, norm_b: str, threshold: float) -> float:
    """带去重循环下界的相似度：上界不足阈值时不做完整 SequenceMatcher。

    ``SequenceMatcher.quick_ratio`` 是真实 ratio 的上界；若双向上界都低于
    候选区门槛，所有合并规则都不可能命中。此时返回上界（仍 < threshold），
    只影响负样本锚点的记录值，不改变任何合并结果；超过门槛才走
    :func:`_ratio_of_norms` 的完整双向计算。
    """
    from difflib import SequenceMatcher

    # 先取零分配的字符多重集上界：达不到门槛时连 SequenceMatcher 都不必构造。
    # 该上界不小于真实 ratio，故「上界 < 门槛 ⇒ 所有合并规则都不可能命中」与原
    # 实现（quick_ratio 双向上界）判据等价，判定结果不变。
    cheap_upper = _multiset_upper_bound(norm_a, norm_b)
    if cheap_upper < threshold:
        return cheap_upper
    a = _ratio_ready(norm_a)
    b = _ratio_ready(norm_b)
    upper = max(
        SequenceMatcher(None, a, b).quick_ratio(),
        SequenceMatcher(None, b, a).quick_ratio(),
    )
    if upper < threshold:
        return upper
    return _ratio_of_norms(norm_a, norm_b)


def _overlap_of_norms(norm_a: str, norm_b: str) -> int:
    """已归一标题的实体 bigram 交集大小（当前模板词表掩码后）。"""
    return len(_extract_entity_bigrams_cached(norm_a) & _extract_entity_bigrams_cached(norm_b))


def _pair_similarity(title_a: str, title_b: str) -> tuple[float, int]:
    """两个**原始标题**的相似度与实体重叠 —— 判定口径的唯一实现。

    归一化 → 剥离通用日期 → 英文专名按长度分桶占位 → 双向 ratio 取 max；
    重叠取当前模板词表掩码后的实体 bigram 交集大小。

    ``_dedup_by_title`` 在循环内用已归一字符串调 :func:`_ratio_of_norms` /
    :func:`_overlap_of_norms`（避开重复归一化的开销），而校准工具用本函数对
    锚点里的原始标题重算——两者同源，保证校准报告反映**当前**规则，
    而不是记录时的旧规则（锚点文件 append-only，存量记录夹带历次规则调整）。
    """
    norm_a = _normalize_title(title_a)
    norm_b = _normalize_title(title_b)
    return _ratio_of_norms(norm_a, norm_b), _overlap_of_norms(norm_a, norm_b)
