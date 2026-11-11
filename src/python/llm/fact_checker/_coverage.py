"""数值校验覆盖率统计——回答「这一轮有多少收益率声称被真正比对过」。

为什么需要：检查器长期只报「告警/检查项」，从不报「可校验声称里还有多少被静默跳过」。
实测一只基金的 `8.5%`（真值 -5.06%）就这么溜过去——不是判成通过，而是整条声称在
「主体不可解析」分支被跳过，而统计上看不出任何异常。

口径（按 **百分比声称** 计数，不是按句子）：
  - verified：与某条参考值比对过（通过 / 不符都算，后者另计入 mismatched）；
  - skipped：未比对，按语境原因分桶（非收益率语境 / 度量非收益率 / 单日涨跌 /
    回撤 / 无收益语境 / 无主体）。

实现方式：包一层 `_evaluate_percent`，统计与它同批；**不改判定行为**。跳过原因按
上下文字段分类（近似口径，只用于统计展示，不参与判定）。
"""

from __future__ import annotations

import threading
from typing import TypedDict

from ._constants import _PROPORTION_KEYWORDS


class NumericalCoverage(TypedDict):
    """覆盖率快照（按百分比声称计数）。"""

    total: int
    verified: int
    mismatched: int
    skipped: int
    skip_reasons: dict[str, int]


_lock = threading.Lock()
_total = 0
_verified = 0
_mismatched = 0
_skipped: dict[str, int] = {}
#: 跳过声称的抽样（按原因各留前 N 条，供 `--dump-skipped` 人工判定是「真非收益」还是「漏了关键词」）
_SAMPLE_LIMIT_PER_REASON = 20
_skipped_samples: dict[str, list[dict[str, str]]] = {}


def reset_numerical_coverage() -> None:
    """清空累计（**每次报告重放/评测开始前**由调用方显式调用）。

    报告主路径不消费本统计、也不复位：计数在进程内累积（长驻 TUI 多轮报告
    会一直加），唯一消费者是离线重放（`_eval_halluc_sampler.from_report`，
    按「一份报告」为单位先复位再统计全模块）。之所以不在 `run_fact_check` 内
    自动复位：那会切断重放的跨模块汇总，复位权因此留在调用方。
    """
    global _total, _verified, _mismatched
    with _lock:
        _total = _verified = _mismatched = 0
        _skipped.clear()
        _skipped_samples.clear()


def note_verified() -> None:
    """标记「本条声称已与参考值比对通过」（由判定函数在通过分支调用）。"""
    global _verified
    with _lock:
        _verified += 1


def note_claim(ctx: object, verdict_issue: str | None, verified_before: int) -> None:
    """登记一条声称的归属（由包装器调用）。"""
    global _total, _verified, _mismatched
    with _lock:
        _total += 1
        if verdict_issue is not None:
            _mismatched += 1
            _verified += 1
            return
        if _verified > verified_before:
            return
        reason = _classify_skip(ctx)
        _skipped[reason] = _skipped.get(reason, 0) + 1
        bucket = _skipped_samples.setdefault(reason, [])
        if len(bucket) < _SAMPLE_LIMIT_PER_REASON:
            bucket.append(
                {
                    "value": str(getattr(ctx, "value_str", "")) or str(getattr(ctx, "value", "")),
                    "sentence": str(getattr(ctx, "sentence", ""))[:120],
                }
            )


def verified_count() -> int:
    """当前已比对条数（包装器用来判断本条是否发生过比对）。"""
    with _lock:
        return _verified


def skipped_samples() -> dict[str, list[dict[str, str]]]:
    """跳过声称的抽样（每原因最多 ``_SAMPLE_LIMIT_PER_REASON`` 条）。"""
    with _lock:
        return {reason: list(items) for reason, items in _skipped_samples.items()}


def numerical_coverage() -> NumericalCoverage:
    """覆盖率快照：``{total, verified, mismatched, skipped, skip_reasons}``。"""
    with _lock:
        return {
            "total": _total,
            "verified": _verified,
            "mismatched": _mismatched,
            "skipped": sum(_skipped.values()),
            "skip_reasons": dict(sorted(_skipped.items(), key=lambda kv: -kv[1])),
        }


def _classify_skip(ctx: object) -> str:
    """跳过原因（近似分类，仅统计用）：按判定函数的语境早退顺序归类。"""
    if (
        getattr(ctx, "is_change_rate", False)
        or getattr(ctx, "is_win_rate", False)
        or getattr(ctx, "is_weight", False)
        or getattr(ctx, "is_benchmark_relative", False)
        or getattr(ctx, "is_trim_target", False)
        or getattr(ctx, "is_target_value", False)
        or getattr(ctx, "is_breakdown_sum", False)
        or getattr(ctx, "is_table_weight_cell", False)
    ):
        return "非收益率语境（变化率/权重/胜率/目标/合计）"
    if getattr(ctx, "is_non_rate_metric", False):
        return "度量非收益率（占比/份额/市值/仓位）"
    if getattr(ctx, "is_daily_change", False):
        return "单日涨跌语境（无对应日行情）"
    sentence = str(getattr(ctx, "sentence", ""))
    if any(kw in sentence for kw in _PROPORTION_KEYWORDS):
        return "比例/计数语境"
    if getattr(ctx, "is_drawdown", False):
        return "回撤语境（无回撤基准）"

    # 下面把粗桶「无收益语境或无主体可归因」拆细：只报粗桶看不出该补归因还是该补规则
    from ._constants import _ATTACHED_SUBJECT_MAX_DIST, _EXPOSURE_KEYWORDS, _PROFIT_KEYWORDS, _REBALANCE_TARGET_KEYWORDS
    from ._context import (
        _is_contribution_sentence,
        _is_hypothetical_context,
        _is_metric_word_context,
        _is_position_weight_context,
        _is_weight_target_context,
        _is_threshold_context,
    )
    from ._utils import _subject_spans, _unresolved_attached_subject

    if not any(kw in sentence for kw in _PROFIT_KEYWORDS):
        return "无收益关键词（非收益语境）"
    holding_codes = getattr(ctx, "holding_codes", set())
    name_to_code = getattr(ctx, "name_to_code", None) or {}
    anchor = int(getattr(ctx, "anchor", 0))
    if _unresolved_attached_subject(sentence, anchor, holding_codes, name_to_code):
        return "紧邻名称解析不出持仓"
    if _is_contribution_sentence(sentence):
        return "贡献/归因语境"
    if any(kw in sentence for kw in ("国债", "利率", "通胀", "GDP", "CPI", "PMI")):
        return "宏观基准语境"
    nearest: dict[str, int] = {}
    for start, end, code in _subject_spans(sentence, holding_codes, name_to_code):
        dist = min(abs(start - anchor), abs(end - anchor))
        nearest[code] = min(nearest.get(code, dist), dist)
    if len(nearest) >= 2:
        ordered = sorted(nearest.values())
        if ordered[0] > _ATTACHED_SUBJECT_MAX_DIST or ordered[1] <= _ATTACHED_SUBJECT_MAX_DIST:
            return "多主体句（归因歧义）"
    if _is_metric_word_context(sentence, anchor):
        return "风险/财务指标语境"
    if _is_weight_target_context(sentence, anchor):
        return "仓位/目标比例语境"
    if _is_threshold_context(sentence, anchor):
        return "阈值/比较语境"
    if _is_position_weight_context(sentence):
        return "仓位/占比语境"
    if _is_hypothetical_context(sentence):
        return "假设/情景语境"
    if any(kw in sentence for kw in _REBALANCE_TARGET_KEYWORDS):
        return "调仓目标语境"
    if any(kw in sentence for kw in _EXPOSURE_KEYWORDS):
        return "币种/敞口语境"

    # 市场/板块口径且句中无持仓主体（延迟导入：本模块被 _numerical 导入，反之不可在模块级）
    from ._numerical import _is_market_scope_no_subject

    if _is_market_scope_no_subject(sentence, anchor, holding_codes, name_to_code):
        return "市场/板块口径且无持仓主体"
    return "主体可解析但无可比对参考值"
