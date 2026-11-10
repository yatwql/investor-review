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


def reset_numerical_coverage() -> None:
    """清空累计（每次 run_fact_check / 评测开始前调用）。"""
    global _total, _verified, _mismatched
    with _lock:
        _total = _verified = _mismatched = 0
        _skipped.clear()


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
        _skipped[_classify_skip(ctx)] = _skipped.get(_classify_skip(ctx), 0) + 1


def verified_count() -> int:
    """当前已比对条数（包装器用来判断本条是否发生过比对）。"""
    with _lock:
        return _verified


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
    return "无收益语境或无主体可归因"
