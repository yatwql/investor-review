"""组合历史走势与回撤 Excel 写入模块 — 走势表 + 回撤矩阵 + 危机区间标注 + 月度收益日历 + 风险调整超额合一页签（一章五区块）。

「组合历史走势与回撤」一章分「走势表 + 回撤矩阵 + 危机区间标注 + 月度收益日历 + 风险调整超额」五区块：
  一、走势表（upper）—— 净值时间线 + 基准归一化 + 指标汇总（组合 vs 基准对比矩阵，仅一份）
  二、回撤矩阵（lower）—— 独立回撤事件明细（含恢复耗时）
  三、危机区间标注 —— 静态历史危机表 + 区间统计；回放态（开关 crisis_replay）扩为
    「组合 vs 指数」双层 9 列（组合层仅窗口内有值，指数层覆盖历史全区间）
  四、月度收益日历 —— 年 × 月红绿格（正值红字/负值绿字）+ 口径与胜亏平统计说明行；
    数据源 `history_data.monthly_returns`（analysis/monthly_returns，as-if 口径，
    双口径并排预留）
  五、风险调整超额 —— 开关 risk_adjusted_excess 开启才写：基准 × 年化 IR/跟踪误差/
    年化超额/近 12·24 月跑赢胜率表 + 滚动窗口超额序列 + 口径说明（§1.4.5 逐指标降级）

指标区（累计收益/最大回撤/波动率/起止日）在章内**只出现一次**（组合 vs 基准矩阵，
组合为第一列，天然包含全部组合指标）。数据不可用时整页写占位。
"""

from __future__ import annotations

import logging
from typing import Any

from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from src.python.core.registry import get_report_sheet_name
from src.python.report.excel_writer import (
    write_block_title,
    _write_placeholder,
    auto_width,
    freeze_header,
    write_data_row,
    write_header_row,
    write_title_row,
)
from src.python.report.styles import FMT_MONEY, FMT_PERCENT, profit_font

logger = logging.getLogger("invest")

# 回撤明细表列数（危机区间表、指标矩阵均 ≤ 此列数时可复用 ncols）
_DD_NCOLS = 8
# 危机区间表列数（关态 6 列）
_CRISIS_NCOLS = 6
# 危机回放态区间表列数（组合层 + 指数层双层 9 列）
_CRISIS_REPLAY_NCOLS = 9
# 风险调整超额指标表列数（基准 + 6 指标）
_EXCESS_NCOLS = 7
# 月度收益日历列数（年 + 12 月）
_CAL_NCOLS = 13

# 危机标注说明行（图下说明：区间数据出 → 说明出；不列举具体危机清单，静态表增补自动跟随）
_CRISIS_NOTE = (
    "说明：阴影/高亮区间为历史上 A 股主要危机时段（静态历史事实表，清单见危机名称列）；"
    "区间与报告数据窗口重叠时统计区间最大回撤与恢复耗时"
)

# 危机回放说明行（双层口径：组合层窗口内 + 指数层历史全区间）
_CRISIS_REPLAY_NOTE = (
    "说明：双层回放——组合层区间统计仅覆盖报告数据窗口内的危机（窗口外标「组合窗口外」）；"
    "指数层为主基准历史日线全区间统计，超出组合数据窗口的历史危机以指数表现作市场参照"
)


def _data_ok(history_data: dict | None) -> bool:
    """判断历史数据是否可渲染（非 None、非 unavailable、有 bars）。"""
    return bool(history_data and history_data.get("status") != "unavailable" and history_data.get("bars"))


def _compute_ncols(history_data: dict | None) -> int:
    """计算标题栏跨列数：走势表（4 + 基准数）、回撤明细（8）与月度日历（13）取最大。"""
    n_bm = len((history_data or {}).get("benchmarks", [])) if history_data else 0
    return max(4 + n_bm, _DD_NCOLS, _CRISIS_NCOLS, _CAL_NCOLS)


def _apply_italic(ws: Worksheet, row: int, ncols: int) -> None:
    """将指定行整行字体置为斜体（说明/注释行，图下说明）。"""
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = Font(italic=True)


def _write_trend_block(
    ws: Worksheet,
    row: int,
    history_data: dict,
    ncols: int,
    tail_risk: dict[str, Any] | None = None,
) -> int:
    """写入一、走势表区块（净值时间线 + 指标汇总 + 尾部风险），返回下一行起始行号。"""
    write_block_title(ws, row, "一、走势表", ncols=ncols)
    row += 1

    bars = history_data.get("bars", [])
    benchmarks = history_data.get("benchmarks", [])
    n_bm = len(benchmarks)
    first_value = bars[0]["total_value"] if bars and bars[0].get("total_value") else 0

    headers = ["日期", "组合市值", "组合收益(%)", "组合归一化(%)"]
    for bm in benchmarks:
        headers.append(bm.get("name", bm.get("code", "基准")))
    row = write_header_row(ws, row, headers)

    for i, bar in enumerate(bars):
        tv = bar.get("total_value", 0)
        cum_return = (tv - first_value) / first_value if first_value > 0 else 0
        norm_value = tv / first_value * 100 if first_value > 0 else 0

        values = [bar.get("date", ""), tv, cum_return, round(norm_value, 2)]
        for bm in benchmarks:
            bm_bars = bm.get("bars", [])
            bm_value = bm_bars[i].get("value") if i < len(bm_bars) else None
            values.append(bm_value)

        fmts: list[str | None] = [None, FMT_MONEY, FMT_PERCENT, "0.00"]
        for _ in range(n_bm):
            fmts.append("0.00")
        row = write_data_row(ws, row, values, formats=fmts)

    # ── 指标汇总（组合 vs 基准对比矩阵，仅此一份） ──
    row += 1
    row = write_title_row(ws, row, "指标汇总（组合 vs 基准）", ncols=ncols)
    matrix_headers = ["指标", "组合"]
    for bm in benchmarks:
        matrix_headers.append(bm.get("name", bm.get("code", "基准")))
    row = write_header_row(ws, row, matrix_headers)

    pd = history_data
    metrics: list[tuple[str, Any, str | None, str, str | None]] = [
        ("累计收益率(%)", round(pd.get("total_return_pct", 0) / 100, 4), FMT_PERCENT, "total_return_pct", FMT_PERCENT),
        ("累计收益(元)", pd.get("total_return", 0), FMT_MONEY, None, None),
        ("最大回撤(%)", round(pd.get("max_drawdown_pct", 0) / 100, 4), FMT_PERCENT, "max_drawdown_pct", FMT_PERCENT),
        ("年化波动率", pd.get("annualized_volatility", 0), FMT_PERCENT, "annualized_volatility", FMT_PERCENT),
        ("起算日", pd.get("data_start", ""), None, "data_start", None),
        ("终止日", pd.get("data_end", ""), None, "data_end", None),
    ]
    for metric_name, portfolio_val, portfolio_fmt, bm_key, bm_fmt in metrics:
        values = [metric_name, portfolio_val]
        for bm in benchmarks:
            if bm_key and bm.get(bm_key) is not None:
                raw = bm[bm_key]
                bm_val = round(raw / 100, 4) if bm_fmt == FMT_PERCENT else raw
            else:
                bm_val = None
            values.append(bm_val)
        flist: list[str | None] = [None, portfolio_fmt]
        for _ in range(n_bm):
            flist.append(bm_fmt if bm_key else None)
        row = write_data_row(ws, row, values, formats=flist)

    # ── 尾部风险指标行（组合独有，无基准对照列；样本不足写占位） ──
    row = _write_tail_risk_rows(ws, row, tail_risk, n_bm)

    row += 1
    return row


def _write_tail_risk_rows(
    ws: Worksheet,
    row: int,
    tail_risk: dict[str, Any] | None,
    n_bm: int,
) -> int:
    """追加尾部风险指标行（VaR / 最大单日跌幅 / 连续下跌 / 恢复天数），返回下一行行号。

    仅当 tail_risk 可用（available=True）时写实值；数据不足（§1.4.5）时写占位说明。
    """
    if not tail_risk or not tail_risk.get("available"):
        values: list[Any] = ["尾部风险统计", "样本不足，指标不可用"] + [None] * n_bm
        flist: list[str | None] = [None] * (2 + n_bm)
        return write_data_row(ws, row, values, formats=flist)

    recovery_days = tail_risk.get("recovery_days_after_drop")
    recovery_state = tail_risk.get("recovery_state")
    if recovery_state == "unrecovered":
        recovery_cell: Any = "未恢复"
    elif recovery_state == "none":
        recovery_cell = "--"
    else:
        recovery_cell = recovery_days

    rows: list[tuple[str, Any, str | None]] = [
        ("VaR(95)", round(tail_risk.get("var95", 0) / 100, 4), FMT_PERCENT),
        ("VaR(99)", round(tail_risk.get("var99", 0) / 100, 4), FMT_PERCENT),
        ("最大单日跌幅(%)", round(tail_risk.get("max_single_day_drop", 0) / 100, 4), FMT_PERCENT),
        ("最长连续下跌(天)", tail_risk.get("consecutive_down_days"), None),
        ("最大单日跌幅后恢复(天)", recovery_cell, None),
    ]
    for name, value, fmt in rows:
        values = [name, value] + [None] * n_bm
        flist = [None, fmt] + [None] * n_bm
        row = write_data_row(ws, row, values, formats=flist)
    return row


def _write_drawdown_block(
    ws: Worksheet,
    row: int,
    history_data: dict,
    ncols: int,
) -> int:
    """写入二、回撤矩阵区块（独立回撤事件明细），返回下一行起始行号。"""
    write_block_title(ws, row, "二、回撤矩阵", ncols=ncols)
    row += 1

    dd_events = history_data.get("drawdown_events") or []
    dd_available = bool(history_data.get("drawdown_available"))
    ncols_eff = max(ncols, _DD_NCOLS)
    dd_headers = ["序号", "起峰日", "最深日", "恢复日", "最大回撤(%)", "持续天数", "恢复耗时(天)", "当前状态"]
    dd_headers += [""] * (ncols_eff - _DD_NCOLS)
    row = write_header_row(ws, row, dd_headers)
    if not dd_available:
        row = write_data_row(ws, row, ["历史数据不足（回撤计算样本不足），无法计算回撤事件"] + [None] * (ncols_eff - 1))
    elif not dd_events:
        row = write_data_row(ws, row, ["未检测到显著回撤事件"] + [None] * (ncols_eff - 1))
    else:
        for idx, e in enumerate(dd_events, start=1):
            cells: list[Any] = [
                idx,
                e.get("peak_date", ""),
                e.get("trough_date", ""),
                e.get("recovery_date") or "未恢复",
                round(e.get("drawdown_pct", 0.0) / 100, 4),
                e.get("duration_days", 0),
                e.get("recovery_days") if e.get("recovery_days") is not None else "--",
                "已恢复" if e.get("recovered") else "未恢复",
            ]
            cells += [None] * (ncols_eff - _DD_NCOLS)
            dd_fmts: list[str | None] = [None] * 4 + [FMT_PERCENT] + [None] * 3
            dd_fmts += [None] * (ncols_eff - _DD_NCOLS)
            row = write_data_row(ws, row, cells, formats=dd_fmts)

    row += 1
    return row


def _write_crisis_block(
    ws: Worksheet,
    row: int,
    crisis_annotation: dict[str, Any] | None,
    ncols: int,
) -> int:
    """写入三、危机区间标注区块（静态日期表 + 区间统计），返回下一行起始行号。"""
    write_block_title(ws, row, "三、危机区间标注", ncols=ncols)
    row += 1

    if crisis_annotation and crisis_annotation.get("replay"):
        return _write_crisis_replay_rows(ws, row, crisis_annotation, ncols)

    intervals = (crisis_annotation or {}).get("intervals", []) if crisis_annotation else []
    ncols_eff = max(ncols, _CRISIS_NCOLS)
    headers = ["危机名称", "区间", "区间最大回撤(%)", "最深日", "恢复耗时(天)", "状态"]
    headers += [""] * (ncols_eff - _CRISIS_NCOLS)
    row = write_header_row(ws, row, headers)

    in_range = [it for it in intervals if it.get("in_range")]
    if not intervals:
        row = write_data_row(ws, row, ["危机区间数据不可用"] + [None] * (ncols_eff - 1))
    elif not in_range:
        row = write_data_row(ws, row, ["报告数据窗口内无历史危机区间"] + [None] * (ncols_eff - 1))
    else:
        for it in in_range:
            dd_pct = it.get("interval_drawdown_pct")
            cells: list[Any] = [
                it.get("name", ""),
                f"{it.get('start', '')} ~ {it.get('end', '')}",
                round(dd_pct / 100, 4) if dd_pct is not None else None,
                it.get("trough_date", ""),
                it.get("recovery_days") if it.get("recovery_days") is not None else "--",
                "已恢复" if it.get("recovered") else "未恢复",
            ]
            cells += [None] * (ncols_eff - _CRISIS_NCOLS)
            fmts: list[str | None] = [None] * 2 + [FMT_PERCENT] + [None] * 3
            fmts += [None] * (ncols_eff - _CRISIS_NCOLS)
            row = write_data_row(ws, row, cells, formats=fmts)
        # 未重叠的危机区间以说明形式补充（供读者了解完整危机清单）
        out_of_range = [it for it in intervals if not it.get("in_range")]
        if out_of_range:
            names = "、".join(it.get("name", "") for it in out_of_range)
            row += 1
            row = write_data_row(ws, row, [f"数据窗口外（未重叠）：{names}"] + [None] * (ncols_eff - 1))
            _apply_italic(ws, row - 1, ncols_eff)

    row += 1
    row = write_data_row(ws, row, [_CRISIS_NOTE] + [None] * (ncols_eff - 1))
    _apply_italic(ws, row - 1, ncols_eff)
    return row


def _write_crisis_replay_rows(
    ws: Worksheet,
    row: int,
    crisis_annotation: dict[str, Any],
    ncols: int,
) -> int:
    """写入危机回放态区间表（双层 9 列：组合层 + 指数层），返回下一行行号。"""
    ncols_eff = max(ncols, _CRISIS_REPLAY_NCOLS)
    headers = [
        "危机名称",
        "区间",
        "组合区间收益(%)",
        "组合区间最大回撤(%)",
        "最深日",
        "恢复耗时(天)",
        "指数区间收益(%)",
        "指数区间最大回撤(%)",
        "状态",
    ]
    headers += [""] * (ncols_eff - _CRISIS_REPLAY_NCOLS)
    row = write_header_row(ws, row, headers)

    intervals = crisis_annotation.get("intervals") or []
    if not intervals:
        row = write_data_row(ws, row, ["危机区间数据不可用"] + [None] * (ncols_eff - 1))
    else:
        for it in intervals:
            in_range = bool(it.get("in_range"))
            p_ret = it.get("portfolio_return_pct")
            p_dd = it.get("interval_drawdown_pct")
            i_ret = it.get("index_return_pct")
            i_dd = it.get("index_drawdown_pct")
            if not in_range:
                status: Any = "组合窗口外"
            elif it.get("recovered") is True:
                status = "已恢复"
            elif it.get("recovered") is False:
                status = "未恢复"
            else:
                status = "—"
            cells: list[Any] = [
                it.get("name", ""),
                f"{it.get('start', '')} ~ {it.get('end', '')}",
                round(p_ret / 100, 4) if in_range and p_ret is not None else None,
                round(p_dd / 100, 4) if in_range and p_dd is not None else None,
                it.get("trough_date", "") if in_range else None,
                it.get("recovery_days")
                if in_range and it.get("recovery_days") is not None
                else ("--" if in_range else None),
                round(i_ret / 100, 4) if i_ret is not None else None,
                round(i_dd / 100, 4) if i_dd is not None else None,
                status,
            ]
            cells += [None] * (ncols_eff - _CRISIS_REPLAY_NCOLS)
            fmts: list[str | None] = [None, None, FMT_PERCENT, FMT_PERCENT, None, None, FMT_PERCENT, FMT_PERCENT, None]
            fmts += [None] * (ncols_eff - _CRISIS_REPLAY_NCOLS)
            row = write_data_row(ws, row, cells, formats=fmts)

    idx_reason = crisis_annotation.get("index_reason")
    if idx_reason:
        row += 1
        row = write_data_row(ws, row, [f"指数层：{idx_reason}"] + [None] * (ncols_eff - 1))
        _apply_italic(ws, row - 1, ncols_eff)
    row += 1
    row = write_data_row(ws, row, [_CRISIS_REPLAY_NOTE] + [None] * (ncols_eff - 1))
    _apply_italic(ws, row - 1, ncols_eff)
    return row


def _write_excess_block(
    ws: Worksheet,
    row: int,
    excess: dict[str, Any] | None,
    ncols: int,
) -> int:
    """写入五、风险调整超额区块（指标表 + 滚动超额序列 + 口径说明），返回下一行行号。

    excess 为 None（开关 risk_adjusted_excess 关闭）时整块不写——关态产物逐字节不变。
    """
    if not excess:
        return row
    write_block_title(ws, row, "五、风险调整超额", ncols=ncols)
    row += 1
    ncols_eff = max(ncols, _EXCESS_NCOLS)

    if not excess.get("available"):
        row = write_data_row(ws, row, [f"数据不可用：{excess.get('reason') or '未知原因'}"] + [None] * (ncols_eff - 1))
        return row + 1

    headers = ["基准", "年化IR", "跟踪误差", "年化超额(%)", "近12月跑赢胜率", "近24月跑赢胜率", "完整月数"]
    headers += [""] * (ncols_eff - _EXCESS_NCOLS)
    row = write_header_row(ws, row, headers)
    for bm in excess.get("benchmarks") or []:
        wr12 = bm.get("win_rate_12m")
        wr24 = bm.get("win_rate_24m")
        cells: list[Any] = [
            bm.get("name", ""),
            bm.get("ir_annual"),
            bm.get("te_annual"),
            round(bm["excess_annual_pct"] / 100, 4) if bm.get("excess_annual_pct") is not None else None,
            f"{wr12:.1f}%" if wr12 is not None else "数据不足",
            f"{wr24:.1f}%" if wr24 is not None else "数据不足",
            bm.get("complete_months"),
        ]
        cells += [None] * (ncols_eff - _EXCESS_NCOLS)
        fmts: list[str | None] = [None, "0.00", "0.00", FMT_PERCENT, None, None, None]
        fmts += [None] * (ncols_eff - _EXCESS_NCOLS)
        row = write_data_row(ws, row, cells, formats=fmts)

    rolling = excess.get("rolling") or {}
    row += 1
    if rolling.get("available"):
        row = write_title_row(
            ws, row, f"滚动 {rolling.get('window_days')} 日超额（{rolling.get('primary_name')}）", ncols=ncols
        )
        row = write_header_row(ws, row, ["日期", "滚动超额(%)"])
        for pt in rolling.get("points") or []:
            row = write_data_row(
                ws,
                row,
                [pt.get("date", ""), round(float(pt.get("excess_pct") or 0.0) / 100, 4)],
                formats=[None, FMT_PERCENT],
            )
    else:
        row = write_data_row(
            ws, row, [f"滚动超额数据不可用：{rolling.get('reason') or '未知原因'}"] + [None] * (ncols_eff - 1)
        )

    for note in excess.get("notes") or []:
        row += 1
        row = write_data_row(ws, row, [note] + [None] * (ncols_eff - 1))
        _apply_italic(ws, row - 1, ncols_eff)
    row += 1
    return row


def _write_monthly_calendar_block(
    ws: Worksheet,
    row: int,
    history_data: dict | None,
    ncols: int,
) -> int:
    """写入四、月度收益日历区块（年 × 月红绿格 + 口径/胜亏平说明行），返回下一行起始行号。"""
    write_block_title(ws, row, "四、月度收益日历", ncols=ncols)
    row += 1

    monthly = (history_data or {}).get("monthly_returns") or {}
    if not monthly.get("available"):
        row = write_data_row(ws, row, ["月度收益数据不可用（样本不足）"])
        return row + 1

    stats = monthly.get("stats") or {}
    streak = stats.get("max_down_streak") or {}
    note = (
        f"口径：{monthly.get('caliber_label', '')} · 最近 {monthly.get('window_months')} 个月"
        f"：胜 {stats.get('up', 0)} / 亏 {stats.get('down', 0)} / 平 {stats.get('flat', 0)}"
        f" · 最长连亏 {streak.get('length', 0)} 个月（结束于 {streak.get('end_key') or '—'}）"
        "；正值红字、负值绿字，空格为窗口外或无样本月份"
    )
    row = write_data_row(ws, row, [note])
    _apply_italic(ws, row - 1, max(ncols, _CAL_NCOLS))

    row = write_header_row(ws, row, ["年"] + [f"{m}月" for m in range(1, 13)])
    for year_group in monthly.get("years", []):
        ws.cell(row=row, column=1, value=f"{year_group.get('year')}年")
        for col, cell in enumerate(year_group.get("cells", [])[:12], start=2):
            ret = cell.get("return_pct")
            if ret is None:
                continue
            frac = ret / 100.0
            target = ws.cell(row=row, column=col, value=frac)
            target.number_format = FMT_PERCENT
            target.font = profit_font(frac)
        row += 1
    return row + 1


def write_portfolio_history_drawdown_sheet(
    ws: Worksheet,
    history_data: dict | None = None,
    crisis_annotation: dict[str, Any] | None = None,
    tail_risk: dict[str, Any] | None = None,
    risk_adjusted_excess: dict[str, Any] | None = None,
) -> None:
    """写入组合历史走势与回撤页签（一章五区块：走势表 + 回撤矩阵 + 危机区间标注 + 月度收益日历 + 风险调整超额；尾部风险统计随回撤矩阵）。

    Args:
        ws: openpyxl Worksheet 对象。
        history_data: `history_data` 数据契约 dict（bars / 指标 / drawdown_events / benchmarks）。
            None、status=unavailable 或 bars 为空时整页写占位。
        crisis_annotation: `crisis_annotation_data` 数据契约 dict（危机区间标注；回放态含双层字段）；
            None 时危机区块写"数据不可用"占位。
        tail_risk: `tail_risk_data` 数据契约 dict（尾部风险统计）；
            None 或 available=False 时尾部指标行写占位。
        risk_adjusted_excess: `risk_adjusted_excess_data` 数据契约 dict（风险调整超额）；
            None（开关关闭）时「五、风险调整超额」区块整体不写。
    """
    _name = get_report_sheet_name("portfolio_history_drawdown")
    ncols = _compute_ncols(history_data)
    write_title_row(ws, 1, _name, ncols=ncols)

    if not _data_ok(history_data):
        _write_placeholder(ws, "组合历史走势与回撤数据暂不可用（配置或网络原因）", max_cols=ncols)
        auto_width(ws)
        logger.info("组合历史走势与回撤：数据不可用，写入整页占位")
        return

    row = 2
    row = _write_trend_block(ws, row, history_data, ncols, tail_risk)
    row = _write_drawdown_block(ws, row, history_data, ncols)
    row = _write_crisis_block(ws, row, crisis_annotation, ncols)
    row = _write_monthly_calendar_block(ws, row, history_data, ncols)
    row = _write_excess_block(ws, row, risk_adjusted_excess, ncols)

    freeze_header(ws, row=2)
    auto_width(ws, min_width=10, max_width=28)
    logger.info("组合历史走势与回撤页签写入完成")
