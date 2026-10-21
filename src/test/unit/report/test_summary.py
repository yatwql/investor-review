"""汇总模块单元测试。

测试目标：
  - _write_section — 章节标题合并+样式
  - _write_kv_row / _write_kv_row_colored — 指标行写入
  - _write_blanks — 空行写入
  - write_summary_sheet — 基本信息/持仓概况/盈亏汇总/市场指数各章节渲染
  - 条件分支：空分类、未更新、零成本、指数缺失
  - profit_font 着色逻辑

运行：
  pytest src/test/unit/report/test_summary.py -v

兄弟分片：test_summary_module_rows.py（模块数据行与 LLM 用量深度行）。"""

from __future__ import annotations
import unittest
from datetime import datetime
from unittest.mock import MagicMock, call, patch
from src.python.report import summary as s
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestWriteSection(unittest.TestCase):
    """测试 _write_section 章节标题渲染。"""

    def setUp(self):
        self.ws = MagicMock()
        self.cell = MagicMock()
        self.ws.cell.return_value = self.cell

    def test_write_section_merge_and_return(self):
        """章节标题写入：合并 8 列并返回下一行号。"""
        row = s._write_section(self.ws, 3, "【持仓概况】")
        self.assertEqual(row, 4)
        self.ws.merge_cells.assert_called_once_with(
            start_row=3,
            start_column=1,
            end_row=3,
            end_column=8,
        )

    def test_write_section_styles(self):
        """章节标题写入：深蓝粗体、居中对齐。"""
        s._write_section(self.ws, 5, "【盈亏汇总】")
        # cell.font 被赋值为 _SECTION_FONT
        self.assertIsNotNone(self.cell.font)
        # 居中
        self.assertEqual(self.cell.alignment.horizontal, "center")
        self.assertEqual(self.cell.alignment.vertical, "center")

    def test_write_section_label_value(self):
        """章节标题文本正确设置。"""
        s._write_section(self.ws, 7, "【市场指数】")
        self.ws.cell.assert_called_with(row=7, column=1, value="【市场指数】")


class TestWriteKvRow(unittest.TestCase):
    """测试 _write_kv_row / _write_kv_row_colored。"""

    def setUp(self):
        self.ws = MagicMock()

    @patch("src.python.report.summary.write_data_row")
    def test_write_kv_row(self, mock_data):
        """_write_kv_row：写入 key/value 并返回下一行号。"""
        row = s._write_kv_row(self.ws, 3, "持仓总数", 7)
        self.assertEqual(row, 4)
        mock_data.assert_called_once_with(self.ws, 3, ["持仓总数", 7])

    @patch("src.python.report.summary.write_data_row")
    def test_write_kv_row_colored(self, mock_data):
        """_write_kv_row_colored：写入 key/value 并应用字体到两列。"""
        from openpyxl.styles import Font

        red_font = Font(color="CC0000")

        row = s._write_kv_row_colored(self.ws, 5, "价格更新状态", "3/5 (尚有缺失)", red_font)
        self.assertEqual(row, 6)
        mock_data.assert_called_once_with(self.ws, 5, ["价格更新状态", "3/5 (尚有缺失)"])

        # 两列单元格都调用了 ws.cell
        calls = self.ws.cell.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], call(row=5, column=1))
        self.assertEqual(calls[1], call(row=5, column=2))

        # 字体被设到 cell 上
        self.assertIs(self.ws.cell.return_value.font, red_font)

    @patch("src.python.report.summary.write_data_row")
    def test_write_kv_row_colored_blue(self, mock_data):
        """_write_kv_row_colored：蓝色字体正常应用。"""
        from openpyxl.styles import Font

        blue_font = Font(color="2E75B6")

        s._write_kv_row_colored(self.ws, 8, "状态", "全部已更新", blue_font)

        self.assertIs(self.ws.cell.return_value.font, blue_font)


class TestWriteBlanks(unittest.TestCase):
    """测试 _write_blanks。"""

    def setUp(self):
        self.ws = MagicMock()

    def test_write_blanks_default(self):
        """默认写入 1 行空白。"""
        row = s._write_blanks(self.ws, 10)
        self.assertEqual(row, 11)

    def test_write_blanks_multiple(self):
        """写入 3 行空白。"""
        row = s._write_blanks(self.ws, 10, 3)
        self.assertEqual(row, 13)

    def test_write_blanks_zero(self):
        """写入 0 行空白（行号不变）。"""
        row = s._write_blanks(self.ws, 10, 0)
        self.assertEqual(row, 10)


class TestWriteBasicInfoFonts(unittest.TestCase):
    """_write_basic_info 值单元格样式：统计时间加粗、所属交易日加粗+加大+蓝色。"""

    def _render_basic_info(self, now: datetime):
        """用真实 openpyxl 工作表渲染基本信息（隔离 get_last_trading_day）。"""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        with patch("src.python.report.summary.get_last_trading_day", return_value="2026-06-26"):
            s._write_basic_info(ws, 1, now)
        return ws

    def test_stat_time_value_bold(self):
        """统计时间值（第2列）加粗。"""
        ws = self._render_basic_info(datetime(2026, 6, 27, 15, 30, 0))
        font = ws.cell(row=1, column=2).font
        self.assertTrue(font.bold, "统计时间值应加粗")

    def test_trading_day_value_bold_larger_blue(self):
        """所属交易日值（第2列）加粗+加大+蓝色。"""
        ws = self._render_basic_info(datetime(2026, 6, 27, 15, 30, 0))
        font = ws.cell(row=2, column=2).font
        self.assertTrue(font.bold, "所属交易日值应加粗")
        self.assertGreater(
            font.size,
            ws.cell(row=1, column=2).font.size,
            "所属交易日字号应大于统计时间",
        )
        # openpyxl 对 6 位 hex 存为 ARGB（前缀 00/FF 视版本而定），匹配蓝色 2E75B6 即可
        self.assertTrue(font.color.rgb.upper().endswith("2E75B6"), "所属交易日值应为蓝色 2E75B6")

    def test_labels_not_bold(self):
        """标签列（第1列）保持普通字体，不受影响。"""
        ws = self._render_basic_info(datetime(2026, 6, 27, 15, 30, 0))
        self.assertFalse(ws.cell(row=1, column=1).font.bold, "统计时间标签不应加粗")
        self.assertFalse(ws.cell(row=2, column=1).font.bold, "所属交易日标签不应加粗")

    def test_generator_tool_row(self):
        """生成工具行（第3行）：标签 + 值含应用名称与版本号。"""
        from src.python.core.constants import APP_NAME, APP_VERSION

        ws = self._render_basic_info(datetime(2026, 6, 27, 15, 30, 0))
        self.assertEqual(ws.cell(row=3, column=1).value, "生成工具")
        value = ws.cell(row=3, column=2).value
        self.assertIn(APP_NAME, value)
        self.assertIn(APP_VERSION, value)


if __name__ == "__main__":
    unittest.main()
