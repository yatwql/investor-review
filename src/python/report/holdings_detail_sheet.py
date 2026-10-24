"""持仓明细与分类 — Excel 写入层。

职责：把「市值核算明细」与「持仓分类汇总」两张表写入同一个 Excel 工作表，
分两个区块呈现：

  区块① 市值核算明细（按账户分组 + 分账户小计 + 总计，15/16 列）
  区块② 持仓分类汇总（资产属性 → 投资分类 → 明细 + 小计 + 总计，10/12 列）

仅依赖领域层类型与分类函数，不含行情获取/计算逻辑。

依赖方向：
  market_value.py  ← 本模块（DetailRow 类型）
  category.py      ← 本模块（分类/股息/数据状态领域函数）
  excel_generator.py / excel_content_sheets.py → 本模块（编排器调用）

分层边界：章节层（本模块）只做 Excel 呈现；分类领域函数
（`_categorize_holding` / `_tier_label` / `build_category_data_status` /
`calc_yield_text`）归 `category.py`，市值领域计算（`DetailRow` /
`classify_holdings` / `_compute_detail_row`）归 `market_value.py`，
本模块不重复实现。
"""

from __future__ import annotations

import logging

from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from src.python.core.models import Holding
from src.python.core.registry import get_report_sheet_name
from src.python.report.purchase_status import (
    purchase_column_visible,
    purchase_status_footnote,
)
from src.python.report.cost_position import (
    cost_position_footnote,
    cost_position_visible,
)
from src.python.report.excel_writer import (
    auto_width,
    freeze_header,
    write_title_row,
)
from src.python.report.market_value import DetailRow

from ._holdings_detail_blocks import (  # noqa: F401 — 兼容既有导入面
    _COST_POS_NCOLS,
    _MV_EXTRA_HEADERS,
    _MV_NCOLS,
    _apply_price_type_colors,
    _apply_profit_colors,
    _detail_to_row_values,
    _weighted_avg_cost,
    _write_category_block,
    _write_market_value_block,
)

logger = logging.getLogger("invest")

__all__ = [
    "write_holdings_detail_sheet",
    "_weighted_avg_cost",
    "_detail_to_row_values",
    "_apply_profit_colors",
    "_apply_price_type_colors",
]

# ── 区块① 市值核算明细 ──────────────────────────────────────
# 15 列表头（由 sheet 层维护）
# 成本流水子列（功能开关 `cost_lots` 开启时追加，默认关不渲染）

_MV_NCOLS_WITH_FLOW = _MV_NCOLS + len(_MV_EXTRA_HEADERS)
# 申购限购状态列（功能开关 `fund_purchase_limit`）：追加于市值明细区块末列
# 持仓成本区间位置列（功能开关 `cost_position`）：追加于市值明细区块末列，
# 两窗口百分位并列（窗口数字由 analysis/cost_position 常量单源派生）


# ── 区块② 持仓分类汇总 ──────────────────────────────────────
# 成本流水子列（功能开关 `cost_lots` 开启时追加，默认关不渲染）
# 申购限购状态列（功能开关 `fund_purchase_limit`）：追加于分类汇总区块末列，
# 与区块① `_MV_PURCHASE_HEADERS` 同开关同判据（`purchase_column_visible`）
# 持仓成本区间位置列（功能开关 `cost_position`）：追加于分类汇总区块末列，
# 与区块① `_MV_COST_POS_HEADERS` 同开关同判据（`cost_position_visible`）

# 区块小节标题


def write_holdings_detail_sheet(
    ws: Worksheet,
    holdings: list[Holding] | None = None,
    details: list[DetailRow] | None = None,
    fund_flow_data: dict | None = None,
    purchase_status_data: dict | None = None,
    cost_position_data: dict | None = None,
) -> tuple[float, float, float, float, list[DetailRow]]:
    """写入「持仓明细与分类」工作表（区块①市值明细 + 区块②分类汇总）。

    Args:
        ws: 目标工作表
        holdings: 原始持仓列表（区块②分类分组用；None 视为空）
        details: 预计算明细行（必须传入，由编排器预计算）
        fund_flow_data: 成本流水数据契约（非 None 时两区块各追加子列；
            None 时保持既有 15 列 / 10 列输出）
        purchase_status_data: 申购限购状态契约（开关 `fund_purchase_limit`；
            None 或 available=False 时申购状态列不渲染——保持既有输出；
            开启时市值明细与分类汇总**两区块**末列各追加「申购状态」，并在
            区块①下方空行写口径脚注（该行位于两区块之间，口径覆盖两块）
        cost_position_data: 持仓成本区间位置契约（开关 `cost_position`；
            None 或 available=False 时两列不渲染——保持既有输出；开启时
            两区块末列各追加「成本区间位置」两列，口径脚注与申购限购脚注
            共用两区块间空行，文案各自单源、用「｜」分隔）

    Returns:
        (总市值, 总成本, 总盈亏, 本日总盈亏, 明细行列表)
    """
    _details = details or []
    _holdings = holdings or []
    show_purchase = purchase_column_visible(purchase_status_data)
    show_cost_pos = cost_position_visible(cost_position_data)
    title_cols = _MV_NCOLS_WITH_FLOW + (1 if show_purchase else 0) + (_COST_POS_NCOLS if show_cost_pos else 0)

    row = write_title_row(ws, 1, get_report_sheet_name("holdings_detail"), title_cols)

    grand_mv, grand_cost, grand_profit, grand_today, _details, next_row = _write_market_value_block(
        ws, _details, fund_flow_data, row, purchase_status_data, cost_position_data
    )

    # 口径脚注：占用区块①与区块②之间的空行（文案单源，与 HTML 端同一条）；
    # 两条契约脚注共用同一行，各自文案仍单源于各自契约，以「｜」分隔
    foot_parts: list[str] = []
    if show_purchase:
        foot_parts.append(purchase_status_footnote(purchase_status_data))
    if show_cost_pos:
        foot_parts.append(cost_position_footnote(cost_position_data))
    if foot_parts:
        foot = ws.cell(row=next_row, column=1, value=" ｜ ".join(foot_parts))
        foot.font = Font(size=9, color="999999")
        ws.merge_cells(start_row=next_row, start_column=1, end_row=next_row, end_column=title_cols)

    _write_category_block(
        ws, _holdings, _details, fund_flow_data, next_row + 1, purchase_status_data, cost_position_data
    )

    freeze_header(ws, 3)
    auto_width(ws)

    logger.info(
        "%s写入完成，共 %d 个账户，%d 条持仓",
        get_report_sheet_name("holdings_detail"),
        len(set(d.account for d in _details)),
        len(_details),
    )
    return grand_mv, grand_cost, grand_profit, grand_today, _details
