"""集中度与相关性约束判定（只标注，不阻断动作）。

定位：把「单品种 / 行业 / 相关性」三道上限做成**可配置的判定**，结论只用于在报告与
决策账本上标注「受约束」，不改动作清单、不改 LLM 提示词、不改历史账本条目。

口径：
  - 单品种上限：沿用 `rebalance.threshold`（与再平衡信号、判断依据风险预算同源，
    不再新增第二个单品种上限键，避免两处口径漂移）；
  - 行业上限：`constraints.industry_max_pct` 显式配置才启用，缺省 `None` = 未配置
    不拦截；行业分类由调用方传入（复用既有穿透分类，本模块不另起一套归类）；
  - 相关性上限：`constraints.correlation_max` 显式配置且样本窗口 ≥
    `constraints.correlation_min_window_days`（默认 250 交易日）才评估，否则
    「未评估」不拦截（短样本相关性不稳定，宁可空着）。

开关 `portfolio_constraints` 默认关：关闭时判定返回 `{"enabled": False}`，报告与账本
输出与未接线逐字节一致（回滚通道）。
"""

from __future__ import annotations

from typing import Any

from src.python.config import get_config
from src.python.config.features import is_feature_enabled

FEATURE_FLAG = "portfolio_constraints"
CONSTRAINTS_SECTION = "constraints"

#: 约束项显示名（双端/文档同源）
ITEM_SINGLE = "单品种权重"
ITEM_INDUSTRY = "行业权重"
ITEM_CORRELATION = "最大相关性"

#: 未配置/未评估口径（不按 0 显示）
UNCONFIGURED = "未配置上限"
UNEVALUATED = "未评估"
DEFAULT_CORRELATION_MIN_WINDOW_DAYS = 250


def is_constraints_enabled() -> bool:
    """开关 `portfolio_constraints` 生效值（默认关：行为变更类，需显式启用）。"""
    return is_feature_enabled(FEATURE_FLAG)


def status_of(max_pct: float | None, current_pct: float | None, breached: bool) -> tuple[str, str]:
    """约束项状态标签与语义色类（渲染层零计算；只用既有 data-status 语义角色）。"""
    if breached:
        return "超限", "data-status-warn"
    if max_pct is None:
        return "未配置", "data-status-info"
    if current_pct is None:
        return "未评估", "data-status-info"
    return "正常", "data-status-ok"


def max_single_weight(
    holdings_details: list[dict[str, Any]] | None, total_mv: float
) -> tuple[float | None, str, list[str]]:
    """最大单品种权重（百分数）、其持有人与全部超限前的权重映射。

    Returns:
        (最大权重, 持有人描述, 各品种权重明细 ["code: 权重"] 不参与判定，仅供调用方)
    """
    best_pct: float | None = None
    best_holder = ""
    for row in holdings_details or []:
        mv = row.get("market_value")
        if isinstance(mv, bool) or not isinstance(mv, (int, float)) or mv <= 0:
            continue
        pct = mv / total_mv * 100
        if best_pct is None or pct > best_pct:
            best_pct = pct
            best_holder = f"{row.get('name', '')}（{row.get('code', '')}）"
    return best_pct, best_holder, []


def _single_limit_pct(config: dict[str, Any]) -> float:
    """单品种上限（百分数）：经 `resolve_rebalance_config` 应用 profile 预设。"""
    from src.python.analysis.rebalance import resolve_rebalance_config

    resolved = resolve_rebalance_config(config.get("rebalance"))
    try:
        return float(resolved.get("threshold") or 0.0) * 100
    except (TypeError, ValueError):
        return 0.0


def _to_float(value: Any) -> float | None:
    """配置值 → float（None/非数值 → None，表示未配置）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_constraints(
    holdings_details: list[dict[str, Any]] | None = None,
    total_mv: float | None = None,
    *,
    config: dict[str, Any] | None = None,
    industry_shares: dict[str, float] | None = None,
    correlation_value: float | None = None,
    correlation_window_days: int | None = None,
) -> dict[str, Any]:
    """装配三道约束的判定结果（只标注，不阻断）。

    Args:
        holdings_details: 持仓明细行（含 market_value/name/code）。
        total_mv: 组合总市值（≤0 或非数值 → 判定不可用）。
        config: 全局配置（None 时读当前配置）。
        industry_shares: 行业 → 权重（百分数）；None 表示缺行业分类数据 → 未评估。
        correlation_value: 当前最大两两相关系数；None → 未评估。
        correlation_window_days: 相关性样本窗口（交易日）；不足门槛 → 未评估。

    Returns:
        {enabled, available, reason, items[{item, kind, limit_pct, current_pct,
        breached, limit_label, current_label, status_label, status_class, note}],
        breached_count, breached_codes}
    """
    if not is_constraints_enabled():
        return {"enabled": False}
    if not holdings_details or isinstance(total_mv, bool) or not isinstance(total_mv, (int, float)) or total_mv <= 0:
        return {
            "enabled": True,
            "available": False,
            "reason": "缺少持仓市值",
            "items": [],
            "breached_count": 0,
            "breached_codes": [],
        }

    cfg = config if config is not None else get_config()
    section = cfg.get(CONSTRAINTS_SECTION) or {}
    single_limit = _single_limit_pct(cfg)
    items: list[dict[str, Any]] = []

    # ① 单品种
    best_pct, best_holder, _ = max_single_weight(holdings_details, total_mv)
    breached_codes: list[str] = []
    if best_pct is not None and best_pct > single_limit:
        for row in holdings_details or []:
            mv = row.get("market_value")
            if isinstance(mv, bool) or not isinstance(mv, (int, float)) or mv <= 0:
                continue
            if mv / total_mv * 100 > single_limit:
                code = str(row.get("code") or "")
                if code:
                    breached_codes.append(code)
    items.append(
        _item(
            ITEM_SINGLE,
            "single",
            single_limit,
            best_pct,
            breached_codes != [],
            note=f"最大：{best_holder}" if best_holder else "无有效市值行",
        )
    )

    # ② 行业（显式配置才启用；缺分类数据 → 未评估）
    industry_limit = _to_float(section.get("industry_max_pct"))
    if industry_limit is None:
        items.append(_item(ITEM_INDUSTRY, "industry", None, None, False, note="无行业上限配置键"))
    elif not industry_shares:
        items.append(_item(ITEM_INDUSTRY, "industry", industry_limit, None, False, note="缺行业分类数据"))
    else:
        top_industry, top_share = max(industry_shares.items(), key=lambda kv: kv[1])
        items.append(
            _item(
                ITEM_INDUSTRY,
                "industry",
                industry_limit,
                float(top_share),
                float(top_share) > industry_limit,
                note=f"最大行业：{top_industry}",
            )
        )

    # ③ 相关性（显式配置 + 样本窗口达标才评估）
    correlation_limit = _to_float(section.get("correlation_max"))
    min_window = int(_to_float(section.get("correlation_min_window_days")) or DEFAULT_CORRELATION_MIN_WINDOW_DAYS)
    if correlation_limit is None:
        items.append(_item(ITEM_CORRELATION, "correlation", None, None, False, note="无相关性上限配置键"))
    elif correlation_window_days is None or correlation_window_days < min_window:
        items.append(
            _item(
                ITEM_CORRELATION,
                "correlation",
                correlation_limit,
                None,
                False,
                note=f"样本期不足 {min_window} 交易日",
            )
        )
    elif correlation_value is None:
        items.append(_item(ITEM_CORRELATION, "correlation", correlation_limit, None, False, note="缺相关性计算结果"))
    else:
        items.append(
            _item(
                ITEM_CORRELATION,
                "correlation",
                correlation_limit,
                float(correlation_value),
                float(correlation_value) > correlation_limit,
                note="两两相关系数最大值",
            )
        )

    return {
        "enabled": True,
        "available": True,
        "reason": "",
        "items": items,
        "breached_count": sum(1 for it in items if it["breached"]),
        "breached_codes": sorted(set(breached_codes)),
    }


def _item(
    item: str,
    kind: str,
    limit_pct: float | None,
    current_pct: float | None,
    breached: bool,
    *,
    note: str = "",
) -> dict[str, Any]:
    """构造一条约束项（上限/现状各自可缺，展示口径百分数数值）。"""
    limit = None if limit_pct is None else round(float(limit_pct), 2)
    current = None if current_pct is None else round(float(current_pct), 2)
    status_label, status_class = status_of(limit, current, breached)
    return {
        "item": item,
        "kind": kind,
        "limit_pct": limit,
        "current_pct": current,
        "breached": breached,
        "limit_label": UNCONFIGURED if limit is None else f"{limit:g}%",
        "current_label": UNEVALUATED if current is None else f"{current:g}%",
        "status_label": status_label,
        "status_class": status_class,
        "note": note,
    }


__all__ = [
    "CONSTRAINTS_SECTION",
    "DEFAULT_CORRELATION_MIN_WINDOW_DAYS",
    "FEATURE_FLAG",
    "ITEM_CORRELATION",
    "ITEM_INDUSTRY",
    "ITEM_SINGLE",
    "UNCONFIGURED",
    "UNEVALUATED",
    "evaluate_constraints",
    "is_constraints_enabled",
    "max_single_weight",
    "status_of",
]
