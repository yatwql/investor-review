"""fact_checker 子包 — 检查器 1：数值一致性（带语境感知）。

校验 LLM 引用的收益/回报率百分比与实际数据匹配。
"""

from __future__ import annotations

from dataclasses import dataclass

import re

from src.python.llm.fact_checker._constants import (
    _DEFAULT_TOLERANCE_PCT,
    _EXPOSURE_KEYWORDS,
    _INDEX_CODES,
    _PROFIT_KEYWORDS,
    _PROPORTION_KEYWORDS,
    _REBALANCE_TARGET_KEYWORDS,
)
from src.python.llm.fact_checker._context import (
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
    _is_target_value_context,
    _is_trim_target_context,
    _is_weight_context,
    _is_win_rate_context,
)
from src.python.llm.fact_checker._patterns import _CODE_PATTERN, _PERCENT_PATTERN
from src.python.llm.fact_checker._utils import (
    _build_stock_change_map,
    _build_stock_rate_map,
    _calc_portfolio_values,
    _extract_holding_map,
    _locate_subject_code,
    _sentence_snippet,
    _split_sentences,
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


def _evaluate_percent(ctx: PercentContext) -> tuple[str | None, tuple[str, str, str, str] | None]:
    """评估单个百分比数值（语境判定 → 主体归因 → 是否需要修正）。

    语境开关的**判定顺序**（先「非收益率」早退，再回撤，最后收益语境）在本函数体内
    单源维持；字段含义见 :class:`PercentContext`。

    Returns:
        (issue_str_or_None, correction_or_None)
        correction = (wrong_value_str, correct_value_str, context_sentence, reason)
        reason 为修正语义（如"601939实际收益率187.1%"），供修正明细展示。
    """
    # 环比/同比变化率、胜率、评分权重、相对基准跑输/跑赢、止盈/减仓目标比例、
    # 目标位/估计值、合计=分项之和
    # → 数值均非收益率，不可比较。均用近邻窗口检测（数值紧邻对应语境词），
    # 避免同句其他真实收益率被连带跳过。
    if (
        ctx.is_change_rate
        or ctx.is_win_rate
        or ctx.is_weight
        or ctx.is_benchmark_relative
        or ctx.is_trim_target
        or ctx.is_target_value
        or ctx.is_breakdown_sum
    ):
        return None, None

    # 数值前文是占比/份额/市值/仓位类度量 → 该数值不是收益率。
    # 必须在收益语境判定之前：共现句（"最大持仓 12.3%，持仓收益率 +4.55%"）整句
    # 含「收益」，整句级判定救不了，只有局部前文能区分两个数值的语义。
    if ctx.is_non_rate_metric:
        return None, None

    # 单日/当日涨跌语境 → 数值为单日行情涨跌而非收益率。
    # 句中含持仓主体（代码/名称）时按该品种 change_pct 校验（维度匹配），
    # 无主体（如"科创50单日重挫4.43%"的指数/大盘）→ 跳过，不误修正为个股收益率。
    if ctx.is_daily_change:
        subject = _locate_subject_code(ctx.sentence, ctx.holding_codes, ctx.name_to_code, ctx.anchor)
        change = ctx.stock_changes.get(subject) if subject and ctx.stock_changes else None
        if change is None:
            return None, None  # 无持仓主体或无单日涨跌数据 → 无法校验，跳过
        if abs(ctx.value - abs(change)) <= ctx.tolerance_pct:
            return None, None
        correct_str = f"{change:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"单日涨跌数值 {ctx.value}% 与 {subject} 实际单日涨跌 {correct_str}%（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"{subject}单日涨跌{correct_str}%")

    # 品种计数/比例语境
    if any(kw in ctx.sentence for kw in _PROPORTION_KEYWORDS):
        return None, None

    # 回撤语境 → 与实际最大回撤比较
    if ctx.is_drawdown:
        if ctx.drawdown_pct is None or ctx.drawdown_pct < 0.01:
            return None, None  # 无回撤数据，无法校验，跳过
        diff = abs(ctx.value - ctx.drawdown_pct)
        if diff <= ctx.tolerance_pct:
            return None, None
        correct_str = f"{ctx.drawdown_pct:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"回撤相关数值 {ctx.value}% 与实际最大回撤 {correct_str}% 偏差超过容差（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"回撤实际{correct_str}%")

    # 无收益关键词或收益率太小 → 无法校验
    is_profit_context = any(kw in ctx.sentence for kw in _PROFIT_KEYWORDS)
    if not is_profit_context or ctx.profit_rate < 0.01:
        return None, None

    # 构建参考收益率列表：个股收益率 + 组合总收益率
    ref_rates: dict[str, float] = dict(ctx.stock_rates_abs)
    ref_rates["_portfolio"] = ctx.profit_rate

    # 组合级收益语境（"组合累计收益约10.0%"）→ 数值归到组合总收益率而非某个个股。
    # 必须在主体定位前判定：同句含多个持仓代码时（如"组合累计收益10%，招商银行上涨8%，
    # 贵州茅台上涨15%"），组合收益数值若走个股路由会被误归到数值最近的个股。
    if _is_portfolio_level_context(ctx.sentence, ctx.anchor):
        if abs(ctx.value - ctx.profit_rate) <= ctx.tolerance_pct:
            return None, None
        signed = ctx.profit_rate_signed if ctx.profit_rate_signed is not None else ctx.profit_rate
        correct_str = f"{signed:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"收益相关数值 {ctx.value}% 与实际累计收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"组合实际收益率{correct_str}%")

    # 组合单日/当日表现语境（"今日组合 +0.21%"）→ 数值为组合当日收益，非个股收益率，
    # 且无组合当日收益基准数据可校验 → 跳过。必须在此判定：否则回退全局最近邻会将
    # 当日收益（如 0.21%）误修正为数值最接近的品种收益率（如 561910 的 -2.3%）。
    if _is_portfolio_daily_change_context(ctx.sentence, ctx.anchor):
        return None, None

    # 数值紧贴一个解析不出持仓的名称（如简称「建信装备」）→ 主体归属不可知，
    # 不可用同句其他持仓的收益率去改写（宁漏改不误改）。
    if _unresolved_attached_subject(ctx.sentence, ctx.anchor, ctx.holding_codes, ctx.name_to_code):
        return None, None

    # 定位句中明确持仓主体：统一按 _locate_subject_code「紧邻优先 + 代码/全名最近兜底」
    # 归因（含代码、全名、简称、描述性尾名四来源），而非全局最近邻。同句含多个名称
    # 主体时（如"040046 收益率 +130.61%、建设银行收益率 +181.37%"）各数值各自就近
    # 归因，建设银行主体的 181.37% 归 601939，不被句内代码 040046 钉扎。句中无名称/
    # 代码主体时回退全局最近邻（兜底语义）。
    codes_in_sentence = _CODE_PATTERN.findall(ctx.sentence)
    index_codes_in_sentence = [c for c in codes_in_sentence if c in _INDEX_CODES]
    holding_codes_in_sentence = [c for c in codes_in_sentence if c in ctx.holding_codes]

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
        # 仅当该品种确有收益率数据（在 ctx.stock_rates_abs 中）时采用，否则回退组合收益率。
        best_code = None

    closest_ref = min(ref_rates, key=lambda k: abs(ctx.value - ref_rates[k]))

    # 策略 1：句中有明确持仓主体 → 按该主体实际收益率校验（容差内通过）；
    # 主体无收益率数据（ref 为 None）或无主体 → 回退全局最近邻（历史语义）。
    if best_code is not None:
        ref = ctx.stock_rates_abs.get(best_code)
        if ref is not None and abs(ctx.value - ref) <= ctx.tolerance_pct:
            return None, None
        if ref is None and abs(ctx.value - ref_rates[closest_ref]) <= ctx.tolerance_pct:
            return None, None
    elif abs(ctx.value - ref_rates[closest_ref]) <= ctx.tolerance_pct:
        return None, None

    # 策略 2：句中代码全部为指数代码
    if not holding_codes_in_sentence and index_codes_in_sentence:
        return None, None

    # 策略 3：贡献/归因类关键词
    if _is_contribution_sentence(ctx.sentence):
        return None, None

    # 策略 4：金融基准类关键词
    if any(kw in ctx.sentence for kw in ("国债", "利率", "通胀", "GDP", "CPI", "PMI")):
        return None, None

    # 策略 5：仓位/占比语境
    if _is_position_weight_context(ctx.sentence):
        return None, None

    # 策略 6：假设/情景语境
    if _is_hypothetical_context(ctx.sentence):
        return None, None

    # 策略 7：调仓目标语境
    if any(kw in ctx.sentence for kw in _REBALANCE_TARGET_KEYWORDS):
        return None, None

    # 策略 8：币种/敞口语境
    if any(kw in ctx.sentence for kw in _EXPOSURE_KEYWORDS):
        return None, None

    # 全部策略均未通过 → 标记为不一致（best_code 已在策略 1 前解析）

    # 修正输出用带符号收益率（ctx.stock_rates / ctx.profit_rate_signed），保留盈亏方向：
    # 亏损品种（如 518880 实际 -8.86%）修正时必须输出 -8.9%，不得写成 +8.9%。
    # 最近邻比较仍用绝对值（_PERCENT_PATTERN 不捕获负号，ctx.value 恒为正，幅度匹配）。
    if best_code:
        stock_rate = (ctx.stock_rates or ctx.stock_rates_abs).get(best_code, 0)
        correct_str = f"{stock_rate:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"收益相关数值 {ctx.value}% 与 {best_code} 的实际收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"{best_code}实际收益率{correct_str}%")
    elif closest_ref != "_portfolio":
        stock_rate = (ctx.stock_rates or ctx.stock_rates_abs).get(closest_ref, 0)
        correct_str = f"{stock_rate:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"收益相关数值 {ctx.value}% 与 {closest_ref} 的实际收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"{closest_ref}实际收益率{correct_str}%")
    else:
        signed = ctx.profit_rate_signed if ctx.profit_rate_signed is not None else ctx.profit_rate
        correct_str = f"{signed:.1f}"
        _ctx = _sentence_snippet(ctx.sentence)
        issue = f"收益相关数值 {ctx.value}% 与实际累计收益率 {correct_str}%（{ctx.profit_sign}）偏差超过容差（句段：{_ctx}）"
        return issue, (ctx.value_str, correct_str, ctx.sentence, f"组合实际收益率{correct_str}%")


def check_numerical_consistency(
    text: str,
    holdings_details: list[dict] | None,
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT,
    max_drawdown_pct: float | None = None,
) -> tuple[list[str], int, int, list[tuple[str, str, str, str]]]:
    """检查 LLM 输出中的百分比数值与实际组合/个股数据是否一致。

    v2 改进：
    - 按句子粒度分析，准确识别收益归因段落并跳过
    - 优先匹配句中持仓代码对应的个股收益率
    - 未识别到个股时回退到组合总收益率
    - 指数基准代码数值自动跳过
    - 贡献度/归因段落数值跳过（不可直接比较）

    v3 改进：
    - 返回修正信息列表，供 auto_correct 消费
    - 容差可配置

    v4 改进：
    - 回撤语境检测：将"最大回撤"等数值与实际最大回撤比较而非与收益率比较

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

    values = _calc_portfolio_values(holdings_details)
    profit_rate = abs(values["total_profit_rate"])
    profit_sign = "盈利" if values["total_profit"] >= 0 else "亏损"

    # 构建个股收益率映射
    stock_rates = _build_stock_rate_map(holdings_details)
    stock_rates_abs = {code: abs(r) for code, r in stock_rates.items()}
    holding_codes = set(_extract_holding_map(holdings_details).keys())

    # 单日涨跌映射 {code: change_pct} 与名称→代码映射（单日涨跌语境校验用）
    stock_changes = _build_stock_change_map(holdings_details)
    name_to_code = {name: code for code, name in _extract_holding_map(holdings_details).items()}

    total_checked = 0
    passed = 0
    seen_values: set[str] = set()

    for sentence in _split_sentences(text):
        # 跳过收益归因段落（贡献度占比不可与收益率直接比较）
        if _is_contribution_sentence(sentence):
            continue
        # 跳过策略回放/回测段落（模拟指标与实际收益率不同源，不可比较）
        if _is_replay_context(sentence):
            continue

        for match in re.finditer(_PERCENT_PATTERN, sentence):
            value_str = match.group(1)
            if value_str in seen_values:
                continue
            seen_values.add(value_str)
            value = float(value_str)

            total_checked += 1

            # 回撤语境检测
            is_dd = _is_drawdown_context(sentence, match.start()) if max_drawdown_pct is not None else False
            # 环比/同比变化率语境检测
            is_change_rate = _is_change_rate_context(sentence, match.start())
            # 单日/当日涨跌语境检测
            is_daily_change = _is_daily_change_context(sentence, match.start())

            issue, correction = _evaluate_percent(
                PercentContext(
                    value=value,
                    value_str=value_str,
                    sentence=sentence,
                    stock_rates_abs=stock_rates_abs,
                    holding_codes=holding_codes,
                    profit_rate=profit_rate,
                    profit_sign=profit_sign,
                    tolerance_pct=tolerance_pct,
                    drawdown_pct=max_drawdown_pct,
                    is_drawdown=is_dd,
                    is_change_rate=is_change_rate,
                    is_daily_change=is_daily_change,
                    stock_changes=stock_changes,
                    name_to_code=name_to_code,
                    anchor=match.start(),
                    # 带符号收益率（修正输出保留盈亏方向）
                    stock_rates=stock_rates,
                    profit_rate_signed=values["total_profit_rate"],
                    # 非收益率语境（胜率/评分权重/相对基准跑输跑赢/止盈减仓目标比例）
                    is_win_rate=_is_win_rate_context(sentence, match.start()),
                    is_weight=_is_weight_context(sentence, match.start()),
                    is_benchmark_relative=_is_benchmark_relative_context(sentence, match.start()),
                    is_trim_target=_is_trim_target_context(sentence, match.start()),
                    # 目标位/估计值（"提到 25% 附近"）与「合计 = 分项之和」（"18.3%（12.5%+5.8%）"）
                    is_target_value=_is_target_value_context(sentence, match.start()),
                    is_breakdown_sum=_is_breakdown_sum_context(sentence, match.start(), value),
                    # 数值前文语义（占比/份额/市值/仓位）：局部窗口判定，优先于整句收益语境
                    is_non_rate_metric=_is_non_rate_pre_word_context(sentence, match.start()),
                )
            )
            if issue is None:
                passed += 1
            else:
                issues.append(issue)
                if correction:
                    corrections.append(correction)

    return issues, total_checked, passed, corrections
