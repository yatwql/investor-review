"""Excel 页签 → HTML 网格 → PNG（README / 手册配图）。

Excel 报告的图没法直接截：`.xlsx` 不是可截屏的界面，本机也常无 LibreOffice。做法是
**按工作簿内容重排一张表格图**——读真实演示产物（`make-screenshots.py report` 生成的
xlsx），逐格取「显示值 / 填充色 / 字体 / 合并区 / 列宽」，写成一张带列标行号与页签
条的 HTML 网格，再用既有的无头 Chromium 截图。图里每个数字都来自那次真实生成，
不含真实持仓（调用方先过 `demo_workspace.assert_demo_holdings`）。

不做的事：不模仿 Excel 的窗口边框/功能区（那会把「内容渲染」伪装成软件截图），
只保留电子表格的通用读法——列标 `A..R`、行号、网格线、页签条。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

#: 单元格字体栈（与报告 HTML 同源的中文可用字体）
_FONT_STACK = '"Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", "Source Han Sans SC", sans-serif'

#: 默认取前多少行（一屏可视；页签条单独给出全部页签名）
DEFAULT_MAX_ROWS = 26

#: 渲染列上限（演示报告最多 19 页签宽表，26 列已覆盖；超宽表按比例收缩）
_MAX_COLUMNS = 26

#: 列宽字符数上下限（防止超长备注把整张表撑爆）
_MIN_CHARS, _MAX_CHARS = 6, 22

#: 每「视觉字符」的像素宽（12px 字号下 CJK≈12px，ASCII≈6.6px，取 2 倍关系对齐）
_CHAR_PX = 6.6

#: 行号列宽与单元格左右内边距（列宽预算里预留）
_ROWNO_PX = 36
_CELL_PAD_PX = 12

_HYPERLINK = re.compile(r'^=HYPERLINK\(\s*"[^"]*"\s*,\s*"(?P<text>(?:[^"]|"")*)"\s*\)', re.IGNORECASE)


def hyperlink_text(value: object) -> str | None:
    """`=HYPERLINK("...","显示文本")` → 显示文本；非超链接公式返回 None。

    openpyxl 非 `data_only` 读回的是公式原文，直接上屏会印出 `=HYPERLINK(...)`；
    报告里的页签导航整行都是这种公式，取第二个参数才与 Excel 里所见一致。
    """
    if not isinstance(value, str):
        return None
    match = _HYPERLINK.match(value.strip())
    if match is None:
        return None
    return match.group("text").replace('""', '"')


def format_value(value: object, number_format: str | None) -> str:
    """按单元格数字格式把值转成 Excel 里的显示文本。

    Args:
        value: 单元格原值（数字 / 字符串 / 日期 / 空）。
        number_format: openpyxl 的 `number_format`；`General` 按通用规则收敛。

    Returns:
        上屏文本；空值返回空串。
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return hyperlink_text(value) or value
    fmt = (number_format or "General").strip()
    if isinstance(value, (int, float)):
        if "%" in fmt:
            decimals = _decimals(fmt)
            return f"{value * 100:.{decimals}f}%"
        if "#,##" in fmt:
            decimals = _decimals(fmt)
            return f"{value:,.{decimals}f}"
        if fmt == "General":
            if isinstance(value, int):
                return f"{value:,}"
            text = f"{value:,.6f}".rstrip("0").rstrip(".")
            return text
    return str(value)


def _decimals(number_format: str) -> int:
    """从小数占位符个数取小数位（`0.00%` → 2）；缺省 0。"""
    match = re.search(r"\.(0+)", number_format)
    return len(match.group(1)) if match else 0


def _is_numeric(value: object) -> bool:
    """右对齐判定：数字与数字格式的百分比/金额都右对齐。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _argb_rgb(color: object) -> str | None:
    """openpyxl 颜色 → `#rrggbb`；取不到或全透明返回 None。"""
    rgb = getattr(color, "rgb", None)
    if not isinstance(rgb, str) or len(rgb) not in (6, 8):
        return None
    rgb = rgb[-6:]
    if rgb.upper() in ("000000", "FFFFFF") and getattr(color, "theme", None) is not None:
        return None
    return f"#{rgb}"


def _span_map(sheet) -> dict[tuple[int, int], tuple[int, int]]:
    """合并区左上角 → (跨列数, 跨行数)。"""
    spans: dict[tuple[int, int], tuple[int, int]] = {}
    for merged in sheet.merged_cells.ranges:
        spans[(merged.min_row, merged.min_col)] = (
            merged.max_col - merged.min_col + 1,
            merged.max_row - merged.min_row + 1,
        )
    return spans


def _covered_cells(sheet) -> set[tuple[int, int]]:
    """被合并区覆盖的非左上角坐标（不单独出格）。"""
    covered: set[tuple[int, int]] = set()
    for merged in sheet.merged_cells.ranges:
        for row in range(merged.min_row, merged.max_row + 1):
            for col in range(merged.min_col, merged.max_col + 1):
                if (row, col) != (merged.min_row, merged.min_col):
                    covered.add((row, col))
    return covered


def column_letter(index: int) -> str:
    """1 → `A`，27 → `AA`（列标行用）。"""
    name = ""
    while index > 0:
        index, rest = divmod(index - 1, 26)
        name = chr(ord("A") + rest) + name
    return name


def _display_width(text: str) -> int:
    """视觉宽度：CJK/全角按 2 列计。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _cell_style(cell) -> str:
    """单元格内联样式（填充 / 字色 / 加粗 / 字号 / 对齐）。"""
    rules: list[str] = []
    fill = getattr(cell.fill, "fgColor", None) if cell.fill is not None and cell.fill.patternType else None
    background = _argb_rgb(fill) if fill is not None else None
    if background:
        rules.append(f"background:{background}")
    color = _argb_rgb(cell.font.color) if cell.font is not None and cell.font.color is not None else None
    if color:
        rules.append(f"color:{color}")
    if cell.font is not None:
        if cell.font.bold:
            rules.append("font-weight:700")
        if cell.font.sz:
            rules.append(f"font-size:{round(float(cell.font.sz) * 1.24)}px")
    rules.append("text-align:right" if _is_numeric(cell.value) else "text-align:left")
    return ";".join(rules)


def _column_widths(sheet, max_col: int, max_rows: int, available: int) -> list[int]:
    """各列像素宽：先按内容撑开，超宽时整表等比收缩（不低于 48px）。"""
    widths: list[float] = []
    for col in range(1, max_col + 1):
        content = _display_width(column_letter(col))
        for row in range(1, min(sheet.max_row, max_rows) + 1):
            cell = sheet.cell(row=row, column=col)
            text = format_value(cell.value, cell.number_format)
            if text:
                content = max(content, _display_width(text))
        explicit = sheet.column_dimensions[column_letter(col)].width
        chars = int(explicit) if explicit else content
        widths.append(max(_MIN_CHARS, min(_MAX_CHARS, chars)) * _CHAR_PX + _CELL_PAD_PX)
    total = sum(widths)
    if total > available:
        ratio = available / total
        widths = [max(48.0, width * ratio) for width in widths]
        # 下限 48px 仍可能撑破（列极多时）：在可压缩空间里等比再削一轮
        overflow = sum(widths) - available
        if overflow > 0:
            room = sum(max(0.0, width - 48.0) for width in widths)
            if room > 0:
                widths = [width - max(0.0, width - 48.0) * overflow / room for width in widths]
    return [int(width) for width in widths]


def build_html(
    xlsx_path: Path,
    *,
    sheet_name: str | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_cols: int | None = None,
    viewport_width: int = 1440,
) -> str:
    """把一个页签排成 HTML 表格网格（列标 + 行号 + 页签条）。

    Args:
        xlsx_path: 报告工作簿路径。
        sheet_name: 目标页签名；None 取第一个页签。
        max_rows: 最多渲染多少行（从第 1 行起）。
        max_cols: 最多渲染多少列（None 取该页全部列，上限 ``_MAX_COLUMNS``）。
        viewport_width: 目标视口宽（列总宽超出时整表等比收缩）。

    Returns:
        完整 HTML 文本（含内联样式，无外部依赖）。
    """
    from openpyxl import load_workbook

    workbook = load_workbook(xlsx_path, data_only=False)
    sheet = workbook[sheet_name] if sheet_name else workbook[workbook.sheetnames[0]]
    max_col = min(sheet.max_column, max_cols or sheet.max_column, _MAX_COLUMNS)
    last_row = min(sheet.max_row, max_rows)
    widths = _column_widths(sheet, max_col, last_row, viewport_width - 2 * 24 - _ROWNO_PX)
    spans = _span_map(sheet)
    covered = _covered_cells(sheet)

    rows_html: list[str] = []
    for row in range(1, last_row + 1):
        cells: list[str] = [f'<th class="rowno">{row}</th>']
        for col in range(1, max_col + 1):
            if (row, col) in covered:
                continue
            cell = sheet.cell(row=row, column=col)
            colspan, rowspan = spans.get((row, col), (1, 1))
            attrs = f' style="{_cell_style(cell)}"'
            if colspan > 1:
                attrs += f' colspan="{colspan}"'
            if rowspan > 1:
                attrs += f' rowspan="{rowspan}"'
            text = html.escape(format_value(cell.value, cell.number_format))
            cells.append(f"<td{attrs}>{text}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    head = "".join(f'<th class="colno">{column_letter(i + 1)}</th>' for i in range(len(widths)))
    cols = "".join(f'<col style="width:{w}px">' for w in widths)
    tabs = "".join(
        f'<span class="tab{" active" if name == sheet.title else ""}">{html.escape(name)}</span>'
        for name in workbook.sheetnames
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{html.escape(sheet.title)}</title>
<style>
  html,body{{margin:0;padding:0;background:#f6f7f9;font-family:{_FONT_STACK}}}
  .frame{{margin:24px auto;width:max-content}}
  table{{border-collapse:collapse;table-layout:fixed;background:#fff;font-size:12px;color:#1f2328}}
  th.colno,th.rowno{{background:#eef1f4;color:#5a6672;font-weight:500;text-align:center;
    border:1px solid #d7dde3;height:20px;font-size:11px}}
  th.rowno{{width:{_ROWNO_PX}px;min-width:{_ROWNO_PX}px}}
  td{{border:1px solid #dfe4e9;padding:1px 5px;height:20px;overflow:hidden;white-space:pre;
    text-overflow:ellipsis;vertical-align:middle}}
  .sheetbar{{display:flex;gap:2px;align-items:center;padding:6px 8px;background:#eef1f4;
    border:1px solid #d7dde3;border-top:none;font-size:12px;color:#5a6672}}
  .tab{{padding:3px 8px;border:1px solid transparent;border-radius:3px 3px 0 0;white-space:nowrap}}
  .tab.active{{background:#fff;border-color:#d7dde3;color:#1f2328;font-weight:600;
    box-shadow:inset 0 -2px 0 #2f6fbe}}
  caption{{caption-side:top;text-align:left;font-size:13px;color:#5a6672;padding:6px 8px;
    background:#eef1f4;border:1px solid #d7dde3;border-bottom:none}}
</style></head><body>
<div class="frame"><table><caption>页签「{html.escape(sheet.title)}」· 演示数据</caption>
<colgroup>{cols}</colgroup>
<thead><tr><th class="rowno"></th>{head}</tr></thead>
<tbody>{"".join(rows_html)}</tbody></table>
<div class="sheetbar">{tabs}</div></div>
</body></html>
"""


def render(
    xlsx_path: Path,
    output: Path,
    *,
    sheet_name: str | None = None,
    width: int = 1440,
    height: int = 940,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_cols: int | None = None,
    chrome: str | None = None,
) -> int:
    """把工作簿页签截成 PNG，返回退出码（0 成功 / 1 截图失败）。"""
    from _screenshots import demo_workspace, web_shot

    html_text = build_html(
        Path(xlsx_path),
        sheet_name=sheet_name,
        max_rows=max_rows,
        max_cols=max_cols,
        viewport_width=width,
    )
    staging = demo_workspace.DEFAULT_ROOT / "out" / f"{Path(xlsx_path).stem}-{sheet_name or 'sheet1'}.html"
    staging = staging.with_name(re.sub(r"[^\w.\-一-龥]", "_", staging.name))
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(html_text, encoding="utf-8")
    return web_shot.run(
        staging.resolve().as_uri(),
        Path(output),
        scroll_y=0,
        width=width,
        height=height,
        chrome=chrome,
    )
