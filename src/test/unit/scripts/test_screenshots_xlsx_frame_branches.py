"""`_screenshots/xlsx_frame.py` 的显示值、内联样式、列宽收缩与截图落盘。

只读真实 openpyxl 工作簿（临时构造），不启动浏览器：截图链路由
`demo_workspace` / `web_shot` 替身接管，断言退出码与落盘的 HTML 中转文件。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("_screenshots/xlsx_frame.py", module_name="_screenshots_xlsx_frame_branches_under_test")


def _workbook(path: Path, *, wide_columns: int = 1, narrow_columns: int = 0) -> Path:
    """构造最小演示工作簿：布尔/整数/百分比 + 合并区 + 着色/加粗字体。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    book = Workbook()
    sheet = book.active
    sheet.title = "总览"
    sheet["A1"] = True
    sheet["A2"] = 1234567
    sheet["A3"] = 0.0512
    sheet["A3"].number_format = "0.00%"
    sheet["A4"] = "备注"
    sheet["A4"].font = Font(bold=True, sz=14, color="FFFF0000")
    sheet["A4"].fill = PatternFill(fill_type="solid", fgColor="FFE8F1FB")
    sheet.merge_cells("B2:C2")
    sheet["B2"] = "跨列"
    sheet.merge_cells("D3:D4")
    sheet["D3"] = "跨行"
    for index in range(wide_columns):
        sheet.cell(row=1, column=6 + index, value="二十二个字符的宽列内容示例文字填充")
    for index in range(narrow_columns):
        sheet.cell(row=1, column=6 + wide_columns + index, value="x")
    book.create_sheet("明细")["A1"] = "甲"
    book.save(path)
    return path


class TestValueRendering:
    """`format_value` 的布尔与数字格式分支。"""

    def test_boolean_renders_excel_literal(self, mod):
        assert mod.format_value(True, "General") == "TRUE"
        assert mod.format_value(False, "General") == "FALSE"

    def test_general_int_gets_thousands_separator(self, mod):
        assert mod.format_value(1234567, "General") == "1,234,567"

    def test_general_float_trims_trailing_zeros(self, mod):
        assert mod.format_value(1234.5, "General") == "1,234.5"

    def test_unknown_type_falls_back_to_str(self, mod):
        assert mod.format_value([1, 2], "General") == "[1, 2]"


class TestColorParsing:
    """`_argb_rgb`：取末 6 位；缺省主题色的黑白视为「无显式色」。"""

    def test_alpha_prefix_is_stripped(self, mod):
        assert mod._argb_rgb(SimpleNamespace(rgb="FF1F2328", theme=None)) == "#1F2328"

    def test_non_string_rgb_is_ignored(self, mod):
        assert mod._argb_rgb(SimpleNamespace(rgb=7, theme=None)) is None

    def test_black_with_theme_is_not_an_explicit_color(self, mod):
        """`theme` 存在时 rgb 只是主题色的近似值，上屏会盖掉主题配色。"""
        assert mod._argb_rgb(SimpleNamespace(rgb="FFFFFFFF", theme=1)) is None

    def test_plain_white_without_theme_is_kept(self, mod):
        assert mod._argb_rgb(SimpleNamespace(rgb="FFFFFF", theme=None)) == "#FFFFFF"


class TestCellStyle:
    """填充色 / 字色 / 加粗 / 字号 都进内联样式。"""

    def test_fill_color_becomes_background(self, mod):
        cell = SimpleNamespace(
            value="文本",
            fill=SimpleNamespace(patternType="solid", fgColor=SimpleNamespace(rgb="FFE8F1FB", theme=None)),
            font=SimpleNamespace(color=None, bold=False, sz=None),
        )
        assert "background:#E8F1FB" in mod._cell_style(cell)

    def test_font_color_bold_and_size(self, mod):
        cell = SimpleNamespace(
            value="文本",
            fill=None,
            font=SimpleNamespace(color=SimpleNamespace(rgb="FFFF0000", theme=None), bold=True, sz=12),
        )
        style = mod._cell_style(cell)
        assert "color:#FF0000" in style
        assert "font-weight:700" in style
        assert "font-size:15px" in style


class TestColumnWidths:
    """超宽表的等比收缩：先整表等比，再在可压缩空间里削二轮。"""

    def test_second_pass_fits_available_width(self, mod):
        from openpyxl import Workbook

        sheet = Workbook().active
        sheet.column_dimensions["A"].width = 40
        for col in range(2, 22):
            sheet.column_dimensions[mod.column_letter(col)].width = 6
        widths = mod._column_widths(sheet, 21, 1, 1000)
        assert len(widths) == 21
        # 一轮等比后仍有下限 48px 撑破时，二轮只削可压缩列（宽列变窄、窄列到底）
        assert widths[0] < widths[1]
        assert sum(widths) <= 1000

    def test_narrow_table_keeps_per_column_budget(self, mod):
        from openpyxl import Workbook

        sheet = Workbook().active
        sheet.cell(row=1, column=1, value="甲")
        sheet.cell(row=1, column=2, value="乙")
        widths = mod._column_widths(sheet, 2, 1, 4000)
        assert widths[0] == widths[1]
        assert sum(widths) < 4000


class TestBuildHtml:
    """合并区展开成 colspan/rowspan，页签条列出全部页签名。"""

    def test_merged_cells_render_spans(self, mod, tmp_path: Path):
        html_text = mod.build_html(_workbook(tmp_path / "demo.xlsx"))
        assert 'colspan="2"' in html_text
        assert 'rowspan="2"' in html_text
        assert "明细" in html_text

    def test_sheet_name_selects_target_sheet(self, mod, tmp_path: Path):
        html_text = mod.build_html(_workbook(tmp_path / "demo.xlsx"), sheet_name="明细")
        assert "页签「明细」" in html_text

    def test_max_cols_caps_rendered_columns(self, mod, tmp_path: Path):
        html_text = mod.build_html(_workbook(tmp_path / "demo.xlsx"), max_cols=2)
        assert 'class="colno">C<' not in html_text


class TestRender:
    """截图链路：HTML 先落到 demo 工作区，再交给 web_shot；退出码透传。"""

    @pytest.fixture(name="shot_env")
    def fixture_shot_env(self, tmp_path: Path, monkeypatch):
        calls: dict = {}

        def _run(uri, output, **kwargs):
            calls["uri"] = uri
            calls["output"] = output
            calls["kwargs"] = kwargs
            return 0

        web_shot = types.ModuleType("_screenshots.web_shot")
        web_shot.run = _run
        demo_workspace = types.ModuleType("_screenshots.demo_workspace")
        demo_workspace.DEFAULT_ROOT = tmp_path / "demo"
        package = types.ModuleType("_screenshots")
        package.web_shot = web_shot
        package.demo_workspace = demo_workspace
        for name, module in (
            ("_screenshots", package),
            ("_screenshots.web_shot", web_shot),
            ("_screenshots.demo_workspace", demo_workspace),
        ):
            monkeypatch.setitem(sys.modules, name, module)
        return SimpleNamespace(calls=calls, root=tmp_path / "demo", tmp_path=tmp_path)

    def test_stages_html_and_forwards_exit_code(self, mod, shot_env, tmp_path: Path):
        workbook = _workbook(tmp_path / "持仓 报告.xlsx")
        assert mod.render(workbook, tmp_path / "out.png") == 0
        staged = sorted((shot_env.root / "out").glob("*.html"))
        assert len(staged) == 1
        assert staged[0].name.startswith("持仓_报告-sheet1")
        assert shot_env.calls["uri"].startswith("file://")
        assert shot_env.calls["output"] == tmp_path / "out.png"

    def test_named_sheet_lands_in_staging_name(self, mod, shot_env, tmp_path: Path):
        assert mod.render(_workbook(tmp_path / "demo.xlsx"), tmp_path / "out.png", sheet_name="明细") == 0
        assert (shot_env.root / "out" / "demo-明细.html").is_file()
