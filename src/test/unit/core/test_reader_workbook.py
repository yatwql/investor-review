"""test_reader 兄弟分片（workbook）：工作簿解析与持仓读取。"""

from __future__ import annotations
import zipfile
import unittest
from typing import Any, List
from unittest.mock import MagicMock, patch
from openpyxl.utils.exceptions import InvalidFileException
from src.python.core import reader
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestParseWorkbook(unittest.TestCase):
    """测试 _parse_workbook 的工作表解析逻辑。"""

    def _make_cell(self, value):
        """创建 mock cell，支持 .value 属性。"""
        cell = MagicMock()
        cell.value = value
        return cell

    def _make_worksheet(self, header: List[str], data_rows: List[List[Any]], max_row: int | None = None):
        """创建 mock worksheet，模拟 iter_rows 行为。"""
        ws = MagicMock()
        ws.max_row = max_row if max_row is not None else (len(data_rows) + 1)
        header_cells = [self._make_cell(v) for v in header]

        def iter_rows_side_effect(min_row=1, max_row=None, values_only=False):
            if min_row == 1 and not values_only:
                return iter([header_cells])
            elif min_row >= 2 and values_only:
                return iter(data_rows)
            return iter([])

        ws.iter_rows.side_effect = iter_rows_side_effect
        return ws

    def _make_workbook(self, sheets: dict):
        """创建 mock workbook。

        sheets: {name: (header, data_rows, max_row?)}
        """
        wb = MagicMock()
        wb.sheetnames = list(sheets.keys())

        sheet_map = {}
        for name, params in sheets.items():
            header = params[0]
            data = params[1]
            max_row = params[2] if len(params) > 2 else None
            sheet_map[name] = self._make_worksheet(header, data, max_row)

        wb.__getitem__.side_effect = sheet_map.get
        return wb

    def test_single_sheet_valid(self):
        """单个工作表中有效数据行 -> 正确解析。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", 200, 50.0],
            ["贵州茅台", "600519", 10, 2000.0],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 2)
        self.assertEqual(holdings[0].account, "证券账户")
        self.assertEqual(holdings[0].name, "长江电力")
        self.assertEqual(holdings[0].code, "600900")
        self.assertAlmostEqual(holdings[0].shares, 200.0)
        self.assertAlmostEqual(holdings[0].cost_price, 50.0)
        self.assertEqual(holdings[1].name, "贵州茅台")

    def test_multiple_accounts(self):
        """多个账户 -> 分别解析并合并。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        sheets = {
            "证券账户": (header, [["长江电力", "600900", 200, 50.0]]),
            "支付宝": (header, [["某混合基金", "001234", 1000, 1.0]]),
        }
        wb = self._make_workbook(sheets)
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 2)
        accounts = {h.account for h in holdings}
        self.assertEqual(accounts, {"证券账户", "支付宝"})

    def test_empty_sheet_skipped(self):
        """max_row < 2 的空表 -> 跳过。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", "600900", 200, 50.0]]
        wb = self._make_workbook(
            {
                "证券账户": (header, data),
                "空表": (header, [], 1),
            }
        )
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)

    def test_sheet_with_none_max_row_skipped(self):
        """max_row 为 None 的工作表 -> 跳过。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", "600900", 200, 50.0]]
        wb = self._make_workbook(
            {
                "证券账户": (header, data),
                "空表": (header, [], None),
            }
        )
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)

    def test_header_mismatch_skipped(self):
        """表头不匹配 -> 整表跳过。"""
        header_ok = ["名称", "代码", "持仓份额", "每份成本"]
        header_bad = ["股票名称", "代码", "持仓份额", "每份成本"]
        sheets = {
            "证券账户": (header_ok, [["长江电力", "600900", 200, 50.0]]),
            "支付宝": (header_bad, [["某基金", "001234", 1000, 1.0]]),
        }
        wb = self._make_workbook(sheets)
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0].account, "证券账户")

    def test_header_fewer_columns_skipped(self):
        """表头列数不足 -> 跳过。"""
        header_ok = ["名称", "代码", "持仓份额", "每份成本"]
        header_short = ["名称", "代码"]
        sheets = {
            "证券账户": (header_ok, [["长江电力", "600900", 200, 50.0]]),
            "短表": (header_short, [["某基金", "001234"]]),
        }
        wb = self._make_workbook(sheets)
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)

    def test_extra_columns_allowed(self):
        """多列（超出预期）-> 仍可解析。"""
        header = ["名称", "代码", "持仓份额", "每份成本", "备注"]
        data = [["长江电力", "600900", 200, 50.0, "测试备注"]]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)

    def test_skip_empty_data_rows(self):
        """全空数据行 -> 跳过。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", 200, 50.0],
            [None, None, None, None],
            ["贵州茅台", "600519", 10, 2000.0],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 2)

    def test_skip_row_with_empty_name(self):
        """名称为空的行 -> 跳过。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", 200, 50.0],
            ["", "000001", 100, 10.0],
            [None, "000002", 100, 10.0],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)

    def test_skip_invalid_numeric_values(self):
        """数值格式无效 -> 跳过并记录警告。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", "not_a_number", 50.0],
            ["贵州茅台", "600519", 10, "invalid"],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        with self.assertLogs("invest", level="WARNING") as log:
            holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 0)
        self.assertTrue(any("份额" in msg for msg in log.output))
        self.assertTrue(any("成本" in msg for msg in log.output))

    def test_skip_zero_negative_values(self):
        """份额 <= 0 或成本 < 0 -> 跳过并记录警告；成本为 0 时视为有效（零成本获赠/继承）。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", 0, 50.0],
            ["贵州茅台", "600519", -10, 2000.0],
            ["某基金", "001234", 1000, 0],
            ["另一基金", "005678", 500, -1.0],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        with self.assertLogs("invest", level="WARNING") as log:
            holdings = reader._parse_workbook(wb)
        # cost_price=0 的行（某基金）应被保留，其余 3 行跳过
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0].name, "某基金")
        self.assertEqual(holdings[0].cost_price, 0.0)
        self.assertTrue(any("无效数值" in msg for msg in log.output))

    def test_mixed_valid_and_invalid(self):
        """混合有效行与无效行 -> 只返回有效行。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [
            ["长江电力", "600900", 200, 50.0],
            ["无效份额", "000001", "abc", 10.0],
            ["贵州茅台", "600519", 10, 2000.0],
            [None, "000002", 100, 10.0],
        ]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 2)
        self.assertEqual(holdings[0].name, "长江电力")
        self.assertEqual(holdings[1].name, "贵州茅台")

    def test_whitespace_account_name_stripped(self):
        """账户名称去除空格。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", "600900", 200, 50.0]]
        wb = self._make_workbook({"  证券账户  ": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(holdings[0].account, "证券账户")

    def test_float_string_conversion(self):
        """字符串格式的数字应能正确转换为 float。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", "600900", "200.5", "50.0"]]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(len(holdings), 1)
        self.assertAlmostEqual(holdings[0].shares, 200.5)
        self.assertAlmostEqual(holdings[0].cost_price, 50.0)

    def test_all_sheets_empty_returns_empty(self):
        """所有表都为空 -> 返回空列表。"""
        wb = self._make_workbook({})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(holdings, [])

    def test_sheet_name_stripped_from_account(self):
        """账号从 sheet_name 获取并 strip。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", "600900", 200, 50.0]]
        wb = self._make_workbook({" 证券账户 ": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(holdings[0].account, "证券账户")

    def test_code_as_numeric_parsed(self):
        """代码为数值类型时转字符串。"""
        header = ["名称", "代码", "持仓份额", "每份成本"]
        data = [["长江电力", 600900, 200, 50.0]]
        wb = self._make_workbook({"证券账户": (header, data)})
        holdings = reader._parse_workbook(wb)
        self.assertEqual(holdings[0].code, "600900")


class TestReadHoldings(unittest.TestCase):
    """测试 read_holdings 文件打开与异常处理。"""

    def test_file_not_found(self):
        """文件不存在 -> FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            reader.read_holdings("D:/nonexistent_file_for_test.xlsx")

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_invalid_file_format(self, mock_load, mock_exists):
        """InvalidFileException -> ValueError。"""
        mock_exists.return_value = True
        mock_load.side_effect = InvalidFileException("格式错误")

        with self.assertRaises(ValueError) as ctx:
            reader.read_holdings("bad.xlsx")
        self.assertIn("格式错误", str(ctx.exception))

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_bad_zip_file(self, mock_load, mock_exists):
        """BadZipFile -> ValueError。"""
        mock_exists.return_value = True
        mock_load.side_effect = zipfile.BadZipFile("不是 zip 文件")

        with self.assertRaises(ValueError) as ctx:
            reader.read_holdings("bad.xlsx")
        self.assertIn("格式错误", str(ctx.exception))

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_empty_workbook(self, mock_load, mock_exists):
        """空工作簿 -> 返回空列表。"""
        mock_exists.return_value = True
        mock_wb = MagicMock()
        mock_wb.sheetnames = []
        mock_load.return_value = mock_wb

        holdings = reader.read_holdings("empty.xlsx")
        self.assertEqual(holdings, [])

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_workbook_closed_after_read(self, mock_load, mock_exists):
        """文件读取完后 close 被调用。"""
        mock_exists.return_value = True
        mock_wb = MagicMock()
        mock_wb.sheetnames = []
        mock_load.return_value = mock_wb

        reader.read_holdings("dummy.xlsx")
        mock_wb.close.assert_called_once()

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_logging_on_empty_result(self, mock_load, mock_exists):
        """无持仓记录时记录 WARNING 日志。"""
        mock_exists.return_value = True
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["空表"]
        mock_ws = MagicMock()
        mock_ws.max_row = 1
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        with self.assertLogs("invest", level="WARNING") as log:
            holdings = reader.read_holdings("empty.xlsx")
        self.assertEqual(holdings, [])
        self.assertTrue(any("未读取到任何持仓记录" in msg for msg in log.output))

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_file_not_exists_before_load(self, mock_load, mock_exists):
        """os.path.exists 在 load_workbook 之前被调用。"""
        mock_exists.return_value = False

        with self.assertRaises(FileNotFoundError):
            reader.read_holdings("missing.xlsx")
        mock_load.assert_not_called()

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_logging_info_on_start(self, mock_load, mock_exists):
        """读取开始时记录 INFO 日志。"""
        mock_exists.return_value = True
        mock_wb = MagicMock()
        mock_wb.sheetnames = []
        mock_load.return_value = mock_wb

        with self.assertLogs("invest", level="INFO") as log:
            reader.read_holdings("dummy.xlsx")
        self.assertTrue(any("正在读取持仓文件" in msg for msg in log.output))
