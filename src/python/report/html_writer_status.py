"""HTML 报告的数据状态块装配：自述块、降级状态安全构建、时间串与三处状态区块。

从 :mod:`report.html_writer` 拆出——这些是「把 DataStatus 组装成模板可渲染结构」的
纯装配逻辑，与模板渲染/落盘无关；单向依赖：渲染 → 状态装配。
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.python.core.models import Holding
from src.python.report.category import build_category_data_status
from src.python.report.data_status import STATUS_MESSAGES, DataStatus, DataStatusItem
from src.python.report.fund_performance import build_perf_data_status, is_fund
from src.python.report.market_value import get_last_trading_day
from src.python.report.penetration_sheet import build_penetration_data_status
from src.python.report.summary import build_index_data_status

logger = logging.getLogger("invest")

# ── 辅助函数 ──────────────────────────────────────────────


def _self_review_block() -> str | None:
    """取本轮生成后自检区块 HTML（零参 pull；无产出返回 None）。"""
    from src.python.llm.self_review import get_self_review_block

    return get_self_review_block()


def _safe_build_data_status(builder, *args, label: str = "", **kwargs) -> DataStatus:
    """安全构建数据状态，异常时返回空字典并记录日志。

    统一处理 data_status 构建中的 try/except/log 三步骤，
    避免 3 个 try 块重复此模式。

    Args:
        builder: 状态构建函数（如 build_index_data_status）
        label: 模块名称（用于日志消息），如 "指数"/"穿透"/"基金业绩"
        *args, **kwargs: 透传给 builder 的参数

    Returns:
        构建成功返回 DataStatus 字典，异常返回 {}
    """
    try:
        result = builder(*args, **kwargs)
        return result if isinstance(result, dict) else {}
    except Exception:
        logger.debug("HTML 报告构建%s数据状态失败（非关键）", label, exc_info=True)
        return {}


def _time_strings() -> tuple[str, str, str]:
    """返回 (now_str, today_str, trading_day)。"""
    return (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d"),
        get_last_trading_day(),
    )


def _build_data_status_sections(
    a_indices: dict,
    us_indices: dict,
    penetration: dict | None,
    penetration_profit_ok: bool,
    penetration_dividend_ok: bool,
    perf_data: list[dict] | None,
    holdings: list[Holding],
    cat_dividend_ok: bool,
) -> tuple[DataStatus, DataStatus, DataStatus, DataStatus]:
    """构建 4 个 data_status 摘要字典（指数/穿透/基金业绩/持仓分类）。

    各模块的 data_status 构建互相独立，任一模块失败不影响其他。
    """
    data_status_summary: DataStatus = _safe_build_data_status(
        build_index_data_status, a_indices, us_indices, label="指数"
    )
    data_status_penetration: DataStatus = {}
    if penetration:
        data_status_penetration = _safe_build_data_status(
            build_penetration_data_status, penetration, penetration_profit_ok, penetration_dividend_ok, label="穿透"
        )
    # 从 perf_data 提取真实 adjusted_ratings（无异常风险，放外面不吞）
    _adj_ratings: dict[str, str] = {}
    if perf_data:
        for _entry in perf_data:
            _code = _entry.get("code")
            _tag = _entry.get("rating_tag")
            if _code and _tag:
                _adj_ratings[_code] = _tag
    data_status_perf: DataStatus = _safe_build_data_status(
        build_perf_data_status, _adj_ratings, sum(1 for h in holdings if is_fund(h)), label="基金业绩"
    )
    data_status_category: DataStatus = _safe_build_data_status(
        build_category_data_status, cat_dividend_ok, label="持仓分类"
    )
    return data_status_summary, data_status_penetration, data_status_perf, data_status_category


def _build_history_data_status(history_data: dict | None) -> DataStatus:
    """从 history_data 构建历史走势数据状态字典。"""
    data_status_history: DataStatus = {}
    if not history_data:
        return data_status_history
    status = history_data.get("status", "unavailable")
    warnings = history_data.get("warnings", [])
    if status == "unavailable":
        data_status_history["history_source"] = DataStatusItem(
            available=False,
            tier="T3",
            message=STATUS_MESSAGES.get("history_price_unavailable", "历史走势数据暂不可用"),
        )
    else:
        if status == "degraded":
            data_status_history["history_degraded"] = DataStatusItem(
                available=True,
                tier="T3",
                message=STATUS_MESSAGES.get("history_degraded", "历史走势部分数据来自降级链路"),
            )
        for w in warnings:
            if "收盘价为 0" in w or "零收盘" in w:
                key = "history_zero_value"
            elif "修正" in w or "重叠" in w:
                key = "history_correction"
            elif "净值滞后" in w:
                key = "history_nav_stale"
            else:
                continue
            data_status_history[key] = DataStatusItem(
                available=True,
                tier="T3",
                message=STATUS_MESSAGES.get(key) or w,
            )
    return data_status_history
