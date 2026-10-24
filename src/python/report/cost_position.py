"""持仓成本区间位置（cost_position_data）数据契约 — 编排装配 / 可见性判据 / 单源文案。

数据契约 ``cost_position_data``（条件列契约，形如 ``purchase_status_data``）::

    {"available": bool,                       # 开关关 → 契约整体 None
     "positions": dict[str, dict],             # code → {"short": float|None,
                                               #         "long": float|None}
     "footnote": str}                          # 口径脚注（唯一文案来源）

  - 开关 ``cost_position`` 关闭 → :func:`compute_cost_position_data` 返回 None
    （渲染层保持既有输出，列不渲染）
  - 全链路行情不可得 / 无有效百分位 → ``available=False``（渲染层静默隐列，
    宁缺毋错；``reason`` 供排查）

取数**不新增数据源**：复用 ``PortfolioHistoryCalculator.calculate_for_holding``
（kline/nav 统一 + 代码类型路由 + 多源降级 + ``data/cache/`` 缓存），shares=1.0
得纯价格 close 序列；长窗口一次取数、短窗口取同源尾部切片
（:func:`src.python.analysis.cost_position.positions_from_closes`）。

纯数学（百分位 / clamp / 中性值）在 ``analysis/cost_position.py``——本层只做
取数、装配与单元格文案；下述逻辑出现第二份实现即为新增技术债。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.analysis.cost_position import (
    LONG_WINDOW_DAYS,
    PLACEHOLDER,
    SHORT_WINDOW_DAYS,
    positions_from_closes,
)
from src.python.analysis.valuation_percentile import extract_closes  # 共享收盘价提取（单一事实来源）

logger = logging.getLogger("invest")

__all__ = [
    "COST_POSITION_FOOTNOTE",
    "compute_cost_position_data",
    "cost_position_visible",
    "format_cost_position_cell",
    "cost_position_footnote",
]

#: 口径脚注（唯一文案来源；渲染层同源引用）——设计文档 §5 要求：成本均价近似
#: 买入价、窗口参数与公式须随呈现注明
COST_POSITION_FOOTNOTE = (
    f"成本区间位置 = clamp((每份成本 − 近 {SHORT_WINDOW_DAYS}/{LONG_WINDOW_DAYS} 交易日价格"
    f"区间最低) ÷ (区间最高 − 区间最低), 0, 1)；≈100% 表示成本买在区间高位（追涨嫌疑），"
    f"≈0% 表示低位布局。每份成本为持仓均价（近似买入价，无法区分一次性买入与分批定投）；"
    f"行情缺失显示 {PLACEHOLDER}。"
)


def compute_cost_position_data(holdings: list[Any], config: dict | None = None) -> dict | None:
    """编排持仓成本区间位置数据（``cost_position_data`` 数据契约）。

    功能开关 ``cost_position`` 关闭返回 None（列不渲染）；开启时对每条持仓
    复用 ``PortfolioHistoryCalculator`` 取近 ``LONG_WINDOW_DAYS`` 交易日价格
    序列（内含缓存与多源降级），同源切片计算短/长两窗口百分位。

    Args:
        holdings: 持仓列表（``Holding``；仅消费 ``code``/``name``/``cost_price``）
        config: 完整配置（只读；None 时读全局配置）

    Returns:
        数据契约 dict；开关关闭返回 None；全链路无有效百分位时
        ``available=False``（渲染层静默隐列，不阻断主链路）。
    """
    from src.python.config import is_enable_cost_position

    if not is_enable_cost_position():
        return None

    rows: dict[str, dict[str, float | None]] = {}
    if holdings:
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        calc = PortfolioHistoryCalculator()
        for h in holdings:
            code = str(getattr(h, "code", "") or "").strip()
            if not code or code in rows:
                continue
            cost = getattr(h, "cost_price", None)
            bars = calc.calculate_for_holding(
                holding_code=code,
                holding_name=str(getattr(h, "name", "") or ""),
                shares=1.0,
                days=LONG_WINDOW_DAYS,
            )
            rows[code] = positions_from_closes(cost, extract_closes(bars or []))

    available = any(pos.get("short") is not None or pos.get("long") is not None for pos in rows.values())
    if not available:
        logger.info("[cost_position] 无有效百分位（持仓为空或行情全部不可得），列静默隐藏")

    return {
        "available": available,
        "positions": rows,
        "footnote": COST_POSITION_FOOTNOTE,
    }


def cost_position_visible(cost_position_data: dict | None) -> bool:
    """成本区间位置列是否渲染（开关关闭 / 取数失败 → False，渲染层静默隐列）。"""
    return bool(cost_position_data) and bool(cost_position_data.get("available"))


def format_cost_position_cell(cost_position_data: dict | None, code: str, window: str) -> Any:
    """单代码单窗口单元格值（0~1 浮点供 Excel 百分比格式；缺失写 ``--``）。

    Args:
        cost_position_data: 数据契约（None 或缺席代码返回占位符）
        code: 证券代码
        window: ``"short"`` 或 ``"long"``
    """
    pos = (cost_position_data or {}).get("positions", {}).get(code) or {}
    value = pos.get(window)
    return value if isinstance(value, (int, float)) else PLACEHOLDER


def cost_position_footnote(cost_position_data: dict | None) -> str:
    """口径脚注全文（列展示时恒在；文案单源取契约 ``footnote`` 字段）。"""
    return str((cost_position_data or {}).get("footnote") or COST_POSITION_FOOTNOTE)
