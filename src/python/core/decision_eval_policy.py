"""决策建议的事后评估政策 —— 阈值、单位与对外口径的单一事实位。

设计意图：把「什么算命中」从各处消费方收回来。方性命中阈值、不动作类容忍带、
有效样本门槛与视界单位都在此声明；`core/decision_ledger.py` 单向引用本模块并
以原名重新导出（既有导入面不变），本模块**零依赖**（不 import 账本/报告，避免成环）。

判定入口仍然只有一个：`decision_ledger.classify_direction_outcome`（方向性）——
不动作类（`direction == 0`，持有/观望/不操作）另由 :func:`classify_flat_hit` 给出
「判对/判偏/不可判」，不引入第二套 outcome 枚举。
"""

from __future__ import annotations

#: 方向性命中阈值（分数口径）：|区间涨跌| 低于该值判「平盘不判定」，防噪声计为命中
DIRECTION_HIT_THRESHOLD = 0.015
#: 不动作类（持有/观望/不操作）判对的容忍带（分数口径）：|区间涨跌| 低于该值视为判对
FLAT_HIT_TOLERANCE = 0.02
#: 有效样本门槛：不足时只给「命中/总数」，不给百分比结论
MEANINGFUL_SAMPLE = 20
#: 视界单位（本方结算即按交易日 bar 数计）
HORIZON_UNIT = "trading_days"

#: 对外声明（报告脚注 / CLI / 文档同源引用；百分比口径便于人读）
EVAL_POLICY: dict[str, object] = {
    "horizon_unit": HORIZON_UNIT,
    "direction_hit_threshold_pct": DIRECTION_HIT_THRESHOLD * 100,
    "flat_hit_tolerance_pct": FLAT_HIT_TOLERANCE * 100,
    "meaningful_sample": MEANINGFUL_SAMPLE,
    "directional_rules": "方向性：涨跌 > +阈值判看多命中、< -阈值判看空命中、带宽内记平盘不判定",
    "inaction_rules": "不动作类：|区间涨跌| < 容忍带 ⇒ 判对；越带 ⇒ 判偏；无收益数据 ⇒ 不可判",
    "units": "代码常量用分数（0.015/0.02）；对外文案用百分比（1.5%/2.0%）",
}

__all__ = [
    "DIRECTION_HIT_THRESHOLD",
    "FLAT_HIT_TOLERANCE",
    "MEANINGFUL_SAMPLE",
    "HORIZON_UNIT",
    "EVAL_POLICY",
    "classify_flat_hit",
]


def classify_flat_hit(raw_return: float | None, *, tolerance: float = FLAT_HIT_TOLERANCE) -> bool | None:
    """不动作类建议的事后判定：区间涨跌落在容忍带内视为判对。

    Args:
        raw_return: 区间涨跌（分数，如 0.012 表示 +1.2%）；None 表示无收益数据。
        tolerance: 容忍带（分数）；缺省取政策常量。

    Returns:
        True=判对、False=判偏、None=不可判（无收益数据或非数值）。
    """
    if raw_return is None:
        return None
    try:
        value = float(raw_return)
    except (TypeError, ValueError):
        return None
    return abs(value) < tolerance
