"""数据质量仪表盘页签写入 —「数据源可用性矩阵」章节改造。

该页签恒渲染（原 `data_quality` 开关已移除，仪表盘内置恒开），以
「数据质量仪表盘」标题展示三个区块：

  区块 A 源健康   — 数据源可用性矩阵（现状保留，来自 DegradationTracker 聚合）
  区块 B 品种覆盖 — 逐品种数据状态清单（`position_status` 契约，
                     由品种覆盖诊断组装）
  区块 C 可信度   — 逐品种数据新鲜度分类 + 单日 ±20% 异常跳变检测
                     （`data_freshness` 契约，由数据新鲜度诊断组装）

"""

from __future__ import annotations

import logging

from openpyxl.styles import Font

from src.python.report.excel_writer import (
    auto_width,
    write_data_row,
    write_header_row,
    write_title_row,
    write_block_title,
)

logger = logging.getLogger("invest")

# 品种覆盖区块降级占位（未获取行情数据时提示）
_COVERAGE_PLACEHOLDER = "未获取行情数据，品种覆盖无法判定"

_FONT_RED = Font(color="CC0000")
_FONT_GREEN = Font(color="009900")
_FONT_ORANGE = Font(color="E67E22")


# ── 数据规范化 ──────────────────────────────────────────────


def build_coverage_block(position_status: dict | None) -> dict:
    """规范化品种覆盖区块数据，供 Excel/HTML 渲染。

    Args:
        position_status: `position_status` 契约 dict（build_coverage_summary
            输出），为 None 或 available=False 表示品种覆盖数据不可用。

    Returns:
        {"has_data": bool, "items": list[dict], "abnormal_count": int,
         "summary": str}；不可用时 has_data=False、items 为空。
    """
    if not position_status or not position_status.get("available"):
        return {"has_data": False, "items": [], "abnormal_count": 0, "summary": ""}
    items = position_status.get("items") or []
    return {
        "has_data": True,
        "items": items,
        "abnormal_count": int(position_status.get("abnormal_count") or 0),
        "summary": position_status.get("summary") or "",
    }


# ── Excel 页签写入 ──────────────────────────────────────────


def write_data_quality_sheet(
    ws,
    matrix: list[dict],
    position_status: dict | None,
    data_freshness: dict | None = None,
    history_staleness: dict | None = None,
) -> int:
    """写入数据质量仪表盘页签（源健康 + 品种覆盖 + 可信度三区块）。

    Args:
        ws: openpyxl worksheet
        matrix: build_data_source_matrix() 输出的源健康矩阵行列表
        position_status: `position_status` 契约 dict，None 表示无行情数据
        data_freshness: `data_freshness` 契约 dict（新鲜度 + 单日跳变），
            None 表示可信度数据不可用
        history_staleness: `history_data.terminal_staleness` 契约（终点由滞后净值
            构成的标的明细），None 表示无滞后。非空时在源健康行标降级、在品种
            覆盖行逐标的标出滞后交易日数（与 HTML 数据状态同事实）

    Returns:
        写入结束行号
    """
    ncols = 5
    row = write_title_row(ws, 1, "数据质量仪表盘", ncols)
    row = _write_source_health_block(ws, row, _apply_history_staleness(matrix, history_staleness))
    row = write_source_catalog_block(ws, row)
    row = _write_coverage_block(ws, row, position_status, ncols, history_staleness)
    row = _write_freshness_block(ws, row, data_freshness, ncols)
    auto_width(ws)
    logger.info("数据质量仪表盘页签已写入")
    return row


def _apply_history_staleness(matrix: list[dict], history_staleness: dict | None) -> list[dict]:
    """把历史走势终点滞后叠到矩阵的「历史走势」行（转降级 + 降级明细）。

    不改入参矩阵：返回浅拷贝行，避免同一矩阵实例被多处复用后状态串改。

    Args:
        matrix: 源健康矩阵行列表
        history_staleness: `history_data.terminal_staleness` 契约（可为 None）

    Returns:
        叠加后的新矩阵列表（无滞时时逐行原样返回）
    """
    assets = (history_staleness or {}).get("assets") or []
    if not matrix or not assets:
        return matrix
    max_lag = int((history_staleness or {}).get("max_lag_trading_days") or 0)
    reasons = [
        f"{a.get('label', '?')}: 最新数据日 {a.get('last_date', '?')}"
        f"（滞后 {a.get('lag_trading_days', 0)} 个交易日，占 {a.get('weight_pct', 0):.1f}%）"
        for a in assets
    ]
    out: list[dict] = []
    for m in matrix:
        if m.get("key") != "history":
            out.append(m)
            continue
        row = dict(m)
        if row.get("status") == "ok":
            row["status"] = "degraded"
        row["degraded"] = max(int(row.get("degraded") or 0), len(assets))
        row["detail"] = f"{row.get('detail', '')}；终点净值滞后 {max_lag} 个交易日（{len(assets)} 只标的）"
        row["degraded_list"] = list(row.get("degraded_list") or []) + reasons
        out.append(row)
    return out


def _write_source_health_block(ws, row: int, matrix: list[dict]) -> int:
    """写入区块 A：源健康（数据源可用性矩阵，现状保留 + 「命中源」列）。

    列宽取 :data:`data_source_matrix.MATRIX_HEADERS`（矩阵行的展示契约），
    与其它区块（5 列）不同宽——区块内部标题按本区块列数合并。

    Returns:
        区块结束行号
    """
    from src.python.report.data_source_matrix import MATRIX_HEADERS

    ncols = len(MATRIX_HEADERS)
    row = write_block_title(ws, row, "源健康（数据源可用性）", ncols)
    row = write_header_row(ws, row, list(MATRIX_HEADERS))
    for m in matrix:
        if m["status"] == "ok":
            status_label = "✅ 正常"
            _font = _FONT_GREEN
        elif m["status"] == "degraded":
            status_label = "⚠️ 降级"
            _font = _FONT_ORANGE
        else:
            status_label = "❌ 失败"
            _font = _FONT_RED
        row = write_data_row(
            ws,
            row,
            [
                m["name"],
                status_label,
                m.get("providers_text", "—"),
                m["detail"],
                m["ok"],
                f"{m['degraded']}/{m['failed']}",
            ],
        )
        if m["status"] != "ok":
            for col in range(1, ncols + 1):
                ws.cell(row=row - 1, column=col).font = _font

    _degraded_list = [dg for m in matrix for dg in m.get("degraded_list", [])]
    if _degraded_list:
        row += 1
        row = write_title_row(ws, row, "降级明细", ncols)
        for m in matrix:
            for dg in m.get("degraded_list", []):
                row = write_data_row(ws, row, [m["name"], dg, "", "", "", ""])

    _failures = [sf for m in matrix for sf in m.get("sample_failures", [])]
    if _failures:
        row += 1
        row = write_title_row(ws, row, "失败明细", ncols)
        for m in matrix:
            for sf in m.get("sample_failures", []):
                row = write_data_row(ws, row, [m["name"], sf, "", "", "", ""])
    return row


def write_source_catalog_block(ws, row: int, catalog: list[dict] | None = None) -> int:
    """写入数据源说明区块（实际使用清单：用途 / 计费 / 凭据要求）。

    Args:
        ws: openpyxl worksheet
        row: 起始行号
        catalog: `build_data_source_catalog()` 输出；None 时现算

    Returns:
        区块结束行号
    """
    from src.python.report.data_source_matrix import build_data_source_catalog

    catalog = catalog if catalog is not None else build_data_source_catalog()
    if not catalog:
        return row
    ncols = 6
    row += 1
    row = write_block_title(ws, row, "数据源说明（实际使用清单）", ncols)
    row = write_header_row(ws, row, ["数据类别", "实际数据源（链路）", "用途", "计费", "凭据/就绪", "本次使用"])
    for item in catalog:
        provider = item.get("provider", "")
        note = item.get("note") or ""
        if note:
            provider = f"{provider}；{note}"
        row = write_data_row(
            ws,
            row,
            [
                item.get("category", ""),
                provider,
                item.get("usage", ""),
                item.get("billing", ""),
                item.get("auth", ""),
                "✅ 已使用" if item.get("used") else "○ 未使用",
            ],
        )
    return row


def _write_coverage_block(
    ws,
    row: int,
    position_status: dict | None,
    ncols: int,
    history_staleness: dict | None = None,
) -> int:
    """写入区块 B：品种覆盖（逐品种数据状态清单）。

    position_status 不可用（None / available=False）时写降级占位。
    history_staleness 非空时，逐标的用它标注「净值数据滞后 N 个交易日」
    （仅限当前状态为 ok 的标的：已有更严重异常时保留原原因）。

    Returns:
        区块结束行号
    """
    row += 1
    row = write_block_title(ws, row, "品种覆盖（逐品种数据状态）", ncols)
    block = build_coverage_block(position_status)
    if not block["has_data"]:
        row = write_data_row(ws, row, [_COVERAGE_PLACEHOLDER, "", "", "", ""])
        return row

    stale_by_code = {a.get("code"): a for a in (history_staleness or {}).get("assets") or [] if a.get("code")}
    row = write_header_row(ws, row, ["代码", "名称", "账户", "状态", "原因"])
    for item in block["items"]:
        stale = stale_by_code.get(item["code"])
        status_label, reason = item["status_label"], item["reason"]
        abnormal = item["status"] != "ok"
        if stale and not abnormal:
            status_label = f"净值数据滞后 {stale.get('lag_trading_days', 0)} 个交易日"
            reason = f"历史净值最新数据日 {stale.get('last_date', '?')}；走势终点已按最新行情回填"
            abnormal = True
        row = write_data_row(
            ws,
            row,
            [item["code"], item["name"], item["account"], status_label, reason],
        )
        if abnormal:
            for col in range(1, 6):
                ws.cell(row=row - 1, column=col).font = _FONT_RED
    return row


# 可信度区块降级占位（未获取可信度数据时提示）
_FRESHNESS_PLACEHOLDER = "未获取可信度数据，新鲜度/跳变无法判定"


def _write_freshness_block(ws, row: int, data_freshness: dict | None, ncols: int) -> int:
    """写入区块 C：可信度（逐品种新鲜度分类 + 单日跳变）。

    data_freshness 不可用（None / available=False）时写降级占位。

    Returns:
        区块结束行号
    """
    row += 1
    row = write_block_title(ws, row, "可信度（数据新鲜度 + 单日跳变）", ncols)
    if not data_freshness or not data_freshness.get("available"):
        row = write_data_row(ws, row, [_FRESHNESS_PLACEHOLDER, "", "", "", ""])
        return row

    row = write_header_row(ws, row, ["代码", "名称", "账户", "新鲜度", "单日变化/跳变"])
    for item in data_freshness.get("items") or []:
        freshness_label = item.get("freshness_label", "") or ""
        jump_label = item.get("jump_label", "") or ""
        change_pct = item.get("change_pct", 0.0) or 0.0
        change_text = f"{change_pct:+.2f}%"
        detail_text = jump_label if jump_label else change_text
        abnormal = bool(item.get("jump")) or item.get("freshness") in ("stale", "degraded")
        row = write_data_row(
            ws,
            row,
            [item.get("code", ""), item.get("name", ""), item.get("account", ""), freshness_label, detail_text],
        )
        if abnormal:
            for col in range(1, 6):
                ws.cell(row=row - 1, column=col).font = _FONT_RED
    return row
