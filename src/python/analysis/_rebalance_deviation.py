"""再平衡偏离度信号：目标偏离、股债偏离、单品种超限与信号汇总。

从 :mod:`analysis.rebalance` 拆出——「偏离度 → 信号」这一族（含分类/分组权重、
置信度与误报保护）集中在此；配置解析与持仓分类入口留在原模块。

**依赖方向**：本模块在**函数内**延迟导入 `classify_holding` / `resolve_rebalance_config`
（模块级导入会与入口形成环：入口 re-export 本模块符号）。
"""

from __future__ import annotations

import logging

from typing import Any

from src.python.core.code_utils import (
    is_convertible_bond_by_name,
)
from src.python.config._core import get_config
from src.python.analysis._silence import (
    _filter_silenced_signals,
    _update_silence_state,
    _SILENCE_FILE,  # noqa: F401  # re-export，conftest 通过 rebalance._SILENCE_FILE 重定向
    _load_silence_state,  # noqa: F401  # re-export，test_rebalance / test_rebalance_edge 引用
    _save_silence_state,  # noqa: F401  # re-export，test_rebalance / test_rebalance_edge 引用
)


# 新买入品种观察期（交易日）：建仓不足此交易日数的品种，其超限/偏离信号视为
# 建仓期短期波动，暂不触发再平衡（requirements R-RBL-07 第 (2) 条）
MIN_NEW_POSITION_TRADING_DAYS: int = 20


_CATEGORY_ORDER: list[str] = [
    "equity",
    "fund_equity",
    "fixed_income",
    "money_market",
    "alternative",
    "qdii",
    "others",
]


_CATEGORY_LABELS: dict[str, str] = {
    "equity": "权益（股票/ETF）",
    "fund_equity": "权益类基金",
    "fixed_income": "固收（债券/纯债基金）",
    "money_market": "货币基金",
    "alternative": "另类（商品/REITs/可转债）",
    "qdii": "QDII 海外",
    "others": "其他",
}


# 权益/固收超大类分组定义
# 将 7 个资产大类汇总为两个超大类用于权益/固收偏离检查
_EQUITY_FI_GROUPS: dict[str, dict[str, Any]] = {
    "equity": {
        "categories": ["equity", "fund_equity", "qdii"],
        "label": "权益类",
    },
    "fixed_income": {
        "categories": ["fixed_income", "money_market", "alternative"],
        "label": "固收类",
    },
}


logger = logging.getLogger("invest")


def _apply_false_positive_protection(
    signals: list[dict[str, Any]],
    holdings_details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """对再平衡信号应用误报防护逻辑。

    三类防护：
      (1) 分红/拆股假超限：检查 shares 字段是否可用，持有量未变时标记 low_confidence
      (2) 新买入短期波动：持仓不足 MIN_NEW_POSITION_TRADING_DAYS 个交易日时直接过滤
      (3) 临近行权/到期品种：标注 near_maturity 字段

    Args:
        signals: 再平衡信号列表
        holdings_details: 持仓明细列表

    Returns:
        经过误报防护处理后的信号列表
    """
    if not signals or not holdings_details:
        return signals

    # 构建 code → holding 字典
    holding_map: dict[str, dict[str, Any]] = {}
    for h in holdings_details:
        code = h.get("code", "")
        if code:
            holding_map[code] = h

    result: list[dict[str, Any]] = []
    for sig in signals:
        code = sig.get("code", "")
        if not code:
            result.append(sig)
            continue

        holding = holding_map.get(code)
        if not holding:
            result.append(sig)
            continue

        # (1) 分红/拆股假超限检查
        shares = holding.get("shares")
        if shares is not None:
            sig["shares_available"] = True
        else:
            sig["shares_available"] = False

        # (2) 新买入短期波动（holding_days 由 build_holding_trading_days 按
        #     交易流水首次买入日以交易日计，未知时不参与过滤）
        holding_days = holding.get("holding_days")
        if holding_days is not None and holding_days < MIN_NEW_POSITION_TRADING_DAYS:
            sig["false_positive"] = True
            sig["false_positive_reason"] = (
                f"持仓仅 {holding_days} 个交易日，不足 {MIN_NEW_POSITION_TRADING_DAYS} 个交易日，暂不触发再平衡"
            )
            continue

        # (3) 临近行权/到期品种
        if is_convertible_bond_by_name(holding.get("name", "")):
            sig["near_maturity"] = True
            sig["action"] = sig.get("action", "") + "（可转债临近到期，建议关注转股或自然到期）"

        result.append(sig)

    return result


def _compute_confidence(
    signal_type: str,
    deviation: float | None,
    threshold: float | None = None,
    deviation_threshold_pct: float = 5.0,
) -> str:
    """计算再平衡信号置信度。

    规则：
      - single_overflow: weight 超过 2× threshold → high，否则 medium
      - category/security: abs(deviation) > 2× threshold → high，
        abs(deviation) > threshold → medium，否则 low

    Args:
        signal_type: 信号类型
        deviation: 偏离值（百分比，已有正负号）
        threshold: 单品超限阈值（小数，如 0.15）
        deviation_threshold_pct: 配置偏离阈值（百分比，如 5.0）

    Returns:
        "high" / "medium" / "low"
    """
    if signal_type == "single_overflow":
        # 单品超限：基于 weight 是否超过 2× threshold
        if threshold and deviation and deviation > threshold * 100 * 2:
            return "high"
        return "medium"

    # category / security 偏离
    abs_dev = abs(deviation) if deviation is not None else 0
    if abs_dev > deviation_threshold_pct * 2:
        return "high"
    if abs_dev > deviation_threshold_pct:
        return "medium"
    return "low"


def _categorize_holdings(
    holdings_details: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """按大类分类持仓列表。

    Args:
        holdings_details: 持仓明细列表（含 name / code / market_value）

    Returns:
        {大类名称: [持仓条目, ...]}
    """
    from src.python.analysis.rebalance import classify_holding  # 延迟导入：避免模块级环

    categorized: dict[str, list[dict[str, Any]]] = {cat: [] for cat in _CATEGORY_ORDER}
    for h in holdings_details:
        name = h.get("name", "")
        code = h.get("code", "")
        cat = classify_holding(name, code)
        if cat not in categorized:
            cat = "others"
        categorized[cat].append(h)
    return categorized


def _calc_category_weights(
    categorized: dict[str, list[dict[str, Any]]],
    total_mv: float,
) -> dict[str, float]:
    """计算各资产大类的市值权重百分比。

    Args:
        categorized: _categorize_holdings() 返回的分类字典
        total_mv: 持仓总市值

    Returns:
        {大类名称: 权重百分比（如 45.5 表示 45.5%）}
    """
    weights: dict[str, float] = {}
    for cat in _CATEGORY_ORDER:
        items = categorized.get(cat, [])
        mv = sum(h.get("market_value", 0) or 0 for h in items)
        weights[cat] = round(mv / total_mv * 100, 2) if total_mv > 0 else 0.0
    return weights


def _calc_group_weights(cat_weights: dict[str, float]) -> dict[str, float]:
    """汇总各大类权重为权益/固收超大类权重。

    Args:
        cat_weights: _calc_category_weights() 的返回

    Returns:
        {超大类key: 权重百分比}
    """
    group_weights: dict[str, float] = {}
    for group_key, group_info in _EQUITY_FI_GROUPS.items():
        total_w = sum(cat_weights.get(cat, 0.0) for cat in group_info["categories"])
        group_weights[group_key] = round(total_w, 2)
    return group_weights


def _build_category_deviation_signals(
    cat_weights: dict[str, float],
    target_allocation: dict[str, dict],
    deviation_threshold: float,
) -> list[dict[str, Any]]:
    """大类配置偏离检查：遍历 target_allocation 中属于大类的条目，生成偏离信号。"""
    signals: list[dict[str, Any]] = []
    threshold_pct = deviation_threshold * 100
    for key, target in target_allocation.items():
        if key not in _CATEGORY_ORDER and key not in _CATEGORY_LABELS:
            continue
        current = cat_weights.get(key, 0.0)
        t_min = target.get("min", 0)
        t_max = target.get("max", 100)
        t_target = target.get("target")

        deviation = round(current - (t_target or (t_min + t_max) / 2), 2)
        out_of_range = current < t_min or current > t_max
        if abs(deviation) < threshold_pct and not out_of_range:
            continue

        if current > t_max:
            action = (
                f"权益占比 {current}%，超过目标上限 {t_max}%，超配 {deviation:.1f}%，建议适当止盈权益类，增配固收类"
            )
        elif current < t_min:
            action = f"权益占比 {current}%，低于目标下限 {t_min}%，低配 {-deviation:.1f}%，建议适当增配权益类"
        else:
            action = f"权益占比 {current}%，在目标范围 {t_min}%-{t_max}% 内，无需调整"

        label = _CATEGORY_LABELS.get(key, key)
        confidence = _compute_confidence(
            "category",
            deviation=deviation,
            deviation_threshold_pct=deviation_threshold * 100,
        )
        signals.append(
            {
                "type": "category",
                "category": key,
                "category_label": label,
                "current_weight": current,
                "target_weight": t_target or (t_min + t_max) / 2,
                "min": t_min,
                "max": t_max,
                "deviation": deviation,
                "confidence": confidence,
                "action": action,
            }
        )
    return signals


def _build_security_deviation_signals(
    holdings_details: list[dict[str, Any]],
    total_mv: float,
    target_allocation: dict[str, dict],
    deviation_threshold: float,
) -> list[dict[str, Any]]:
    """品种级配置偏离检查：遍历 target_allocation 中属于证券代码的条目，生成偏离信号。"""
    signals: list[dict[str, Any]] = []
    threshold_pct = deviation_threshold * 100
    for key, target in target_allocation.items():
        if key in _CATEGORY_ORDER or key in _CATEGORY_LABELS:
            continue
        for h in holdings_details:
            if h.get("code") == key:
                mv = h.get("market_value", 0) or 0
                current_w = round(mv / total_mv * 100, 2) if total_mv > 0 else 0.0
                t_min = target.get("min", 0)
                t_max = target.get("max", 100)
                t_target = target.get("target")

                deviation = round(current_w - (t_target or (t_min + t_max) / 2), 2)
                out_of_range = current_w < t_min or current_w > t_max
                if abs(deviation) < threshold_pct and not out_of_range:
                    continue

                if current_w > t_max:
                    act = f"持有 {current_w}%，目标 {t_target or t_max}%，超配 {deviation:.1f}%，建议部分止盈"
                elif current_w < t_min:
                    act = f"持有 {current_w}%，低于目标下限 {t_min}%，低配 {-deviation:.1f}%，建议适当增持"
                else:
                    act = f"持有 {current_w}%，在目标范围 {t_min}%-{t_max}% 内"
                sec_confidence = _compute_confidence(
                    "security",
                    deviation=deviation,
                    deviation_threshold_pct=deviation_threshold * 100,
                )
                signals.append(
                    {
                        "type": "security",
                        "code": key,
                        "name": h.get("name", ""),
                        "current_weight": current_w,
                        "target_weight": t_target or (t_min + t_max) / 2,
                        "deviation": deviation,
                        "confidence": sec_confidence,
                        "action": act,
                    }
                )
                break
    return signals


def compute_target_deviation(
    holdings_details: list[dict[str, Any]] | None,
    total_mv: float,
    target_allocation: dict[str, dict] | None = None,
    deviation_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """计算当前持仓与目标配置的偏离度。

    编排 _build_category_deviation_signals 和 _build_security_deviation_signals，
    分别计算大类偏离和品种级偏离信号。
    """
    if not holdings_details or total_mv <= 0:
        return []

    if target_allocation is None:
        config = get_config()
        rebalance_cfg = config.get("rebalance", {})
        target_allocation = rebalance_cfg.get("target_allocation", {})

    if not target_allocation:
        return []

    categorized = _categorize_holdings(holdings_details)
    cat_weights = _calc_category_weights(categorized, total_mv)

    signals: list[dict[str, Any]] = []
    signals.extend(_build_category_deviation_signals(cat_weights, target_allocation, deviation_threshold))
    signals.extend(
        _build_security_deviation_signals(holdings_details, total_mv, target_allocation, deviation_threshold)
    )
    return signals


def _build_equity_fi_signals(
    group_weights: dict[str, float],
    equity_fi_target: dict[str, dict],
    threshold_pct: float,
    deviation_threshold: float,
) -> list[dict[str, Any]]:
    """构建权益/固收超大类偏离信号。"""
    signals: list[dict[str, Any]] = []
    for group_key, target in equity_fi_target.items():
        if group_key not in _EQUITY_FI_GROUPS:
            logger.warning("equity_fixed_income_deviation: 未知超大类 %r，跳过", group_key)
            continue

        current = group_weights.get(group_key, 0.0)
        t_min = target.get("min", 0)
        t_max = target.get("max", 100)
        t_target = target.get("target")

        deviation = round(current - (t_target or (t_min + t_max) / 2), 2)
        out_of_range = current < t_min or current > t_max

        if abs(deviation) < threshold_pct and not out_of_range:
            continue

        group_label = _EQUITY_FI_GROUPS[group_key]["label"]

        if current > t_max:
            action = (
                f"{group_label}仓位 {current}%，超过目标上限 {t_max}%，"
                f"超配 {deviation:.1f}%，建议适当降低{group_label}配置"
            )
        elif current < t_min:
            action = (
                f"{group_label}仓位 {current}%，低于目标下限 {t_min}%，"
                f"低配 {-deviation:.1f}%，建议适当增加{group_label}配置"
            )
        else:
            action = f"{group_label}仓位 {current}%，在目标范围 {t_min}%-{t_max}% 内，无需调整"

        confidence = _compute_confidence(
            "category",
            deviation=deviation,
            deviation_threshold_pct=deviation_threshold * 100,
        )

        signals.append(
            {
                "type": "equity_fixed_income",
                "group": group_key,
                "group_label": group_label,
                "current_weight": current,
                "target_weight": t_target or (t_min + t_max) / 2,
                "min": t_min,
                "max": t_max,
                "deviation": deviation,
                "confidence": confidence,
                "action": action,
            }
        )

    return signals


def equity_fixed_income_deviation(
    holdings_details: list[dict[str, Any]],
    total_mv: float,
    equity_fi_target: dict[str, dict] | None = None,
    deviation_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """计算权益/固收超大类偏离信号。

    将 7 个资产大类汇总为权益类和固收类超大类，
    委托 _calc_group_weights / _build_equity_fi_signals 计算偏离信号。
    """
    if not holdings_details or total_mv <= 0:
        return []

    if equity_fi_target is None:
        config = get_config()
        rebalance_cfg = config.get("rebalance", {})
        equity_fi_target = rebalance_cfg.get("equity_fixed_income", {})

    if not equity_fi_target:
        return []

    categorized = _categorize_holdings(holdings_details)
    cat_weights = _calc_category_weights(categorized, total_mv)
    group_weights = _calc_group_weights(cat_weights)
    threshold_pct = deviation_threshold * 100

    return _build_equity_fi_signals(group_weights, equity_fi_target, threshold_pct, deviation_threshold)


def _compute_single_overflow_signals(
    holdings_details: list[dict[str, Any]],
    total_mv: float,
    threshold: float,
) -> list[dict[str, Any]]:
    """单品超限信号：检查每个品种是否超过单项配置上限，超过 3 个时汇总。"""
    _MAX_DETAILED = 3
    single_signals: list[dict[str, Any]] = []
    for h in holdings_details:
        mv = h.get("market_value", 0) or 0
        weight = mv / total_mv
        if weight > threshold:
            weight_pct = round(weight * 100, 2)
            confidence = _compute_confidence(
                "single_overflow",
                deviation=weight_pct,
                threshold=threshold,
            )
            single_signals.append(
                {
                    "type": "single_overflow",
                    "code": h.get("code", ""),
                    "name": h.get("name", ""),
                    "weight": weight_pct,
                    "threshold": threshold * 100,
                    "confidence": confidence,
                    "action": f"持仓 {weight * 100:.1f}%，超出建议上限 {threshold * 100:.0f}%，建议部分止盈至 {threshold * 50:.0f}-{threshold * 100:.0f}% 区间",
                }
            )

    signals: list[dict[str, Any]] = []
    if len(single_signals) > _MAX_DETAILED:
        signals.append(
            {
                "type": "summary",
                "summary": True,
                "count": len(single_signals),
                "message": (
                    f"您的组合集中度较高，有 {len(single_signals)} 个品种超过 "
                    f"{threshold * 100:.0f}% 警戒线，建议整体考虑适度分散"
                ),
            }
        )
    else:
        single_signals.sort(key=lambda x: -x["weight"])
        signals.extend(single_signals[:_MAX_DETAILED])

    return signals


def compute_rebalance_signals(
    holdings_details: list[dict[str, Any]] | None,
    total_mv: float,
    rebalance_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """计算完整再平衡信号。

    编排五步流程：
      1. 单品超限信号（_compute_single_overflow_signals）
      2. 目标配置偏离信号（compute_target_deviation）
      3. 权益/固收超大类偏离信号（equity_fixed_income_deviation）
      4. 误报防护（_apply_false_positive_protection）
      5. 静默期过滤（_filter_silenced_signals）
    """
    from src.python.analysis.rebalance import resolve_rebalance_config  # 延迟导入：避免模块级环

    if not holdings_details or total_mv <= 0:
        return []

    resolved = resolve_rebalance_config(rebalance_config)
    threshold = resolved.get("threshold", 0.15)
    deviation_threshold = resolved.get("deviation_threshold", 0.05)
    target_allocation = resolved.get("target_allocation", {})
    equity_fi_target = resolved.get("equity_fixed_income", {})

    signals: list[dict[str, Any]] = []

    # 1. 单品超限信号
    signals.extend(_compute_single_overflow_signals(holdings_details, total_mv, threshold))

    # 2. 目标配置偏离信号
    if target_allocation:
        signals.extend(compute_target_deviation(holdings_details, total_mv, target_allocation, deviation_threshold))

    # 3. 权益/固收超大类偏离信号
    if equity_fi_target:
        signals.extend(equity_fixed_income_deviation(holdings_details, total_mv, equity_fi_target, deviation_threshold))

    # 4. 误报防护
    signals = _apply_false_positive_protection(signals, holdings_details)

    # 5. 静默期过滤 + 更新
    silence_days = resolved.get("silence_days", 30)
    if silence_days > 0:
        silence_file = resolved.get("_silence_file")
        signals = _filter_silenced_signals(signals, silence_days, silence_file)
        _update_silence_state(signals, silence_file)

    return signals
