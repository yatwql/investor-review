"""test_reader 兄弟分片（flows）：流水页签解析与空持仓闸门。"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from src.python.core import reader
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestParseFlowSheets(unittest.TestCase):
    """交易流水 / 分红流水页签解析测试（持仓文件格式扩展）。

    覆盖：正常解析、表头不匹配跳过、空表跳过、非法行容错（日期/操作/数值）、
    费用列可选、操作归一化、无流水页签回退、文件级入口、向后兼容。
    """

    def _make_cell(self, value):
        cell = MagicMock()
        cell.value = value
        return cell

    def _make_worksheet(self, title, header, data_rows, max_row=None):
        ws = MagicMock()
        ws.title = title
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

    # ── _parse_trade_sheet ─────────────────────────────────

    def test_trade_sheet_valid(self):
        """含费用列的交易流水 -> 正确解析并归一化操作。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "操作", "份额", "价格", "费用"],
            [
                ["2026-01-05", "600900", "买入", 200, 25.0, 5.0],
                ["2026-02-10", "600519", "卖出", 10, 2100.0, 10.0],
            ],
        )
        records = reader._parse_trade_sheet(ws)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].date, "2026-01-05")
        self.assertEqual(records[0].code, "600900")
        self.assertEqual(records[0].action, "buy")
        self.assertAlmostEqual(records[0].shares, 200.0)
        self.assertAlmostEqual(records[0].price, 25.0)
        self.assertAlmostEqual(records[0].fee, 5.0)
        self.assertEqual(records[1].action, "sell")

    def test_trade_sheet_without_fee_column(self):
        """无费用列 -> fee 默认 0。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "操作", "份额", "价格"],
            [["2026-01-05", "600900", "买入", 200, 25.0]],
        )
        records = reader._parse_trade_sheet(ws)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0].fee, 0.0)

    def test_trade_header_mismatch_skipped(self):
        """表头不匹配 -> 返回空列表。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "方向", "数量", "单价"],
            [["2026-01-05", "600900", "买入", 200, 25.0]],
        )
        self.assertEqual(reader._parse_trade_sheet(ws), [])

    def test_trade_empty_sheet(self):
        """空表（max_row<2）-> 空列表。"""
        ws = self._make_worksheet("交易流水", ["日期", "代码", "操作", "份额", "价格"], [], 1)
        self.assertEqual(reader._parse_trade_sheet(ws), [])

    def test_trade_invalid_date_skipped(self):
        """非法日期行跳过，其余行保留。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "操作", "份额", "价格"],
            [
                ["昨天", "600900", "买入", 200, 25.0],
                ["2026-02-10", "600519", "买入", 10, 2000.0],
            ],
        )
        records = reader._parse_trade_sheet(ws)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].code, "600519")

    def test_trade_invalid_action_skipped(self):
        """非法操作方向行跳过。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "操作", "份额", "价格"],
            [
                ["2026-01-05", "600900", "转仓", 200, 25.0],
                ["2026-02-10", "600519", "买入", 10, 2000.0],
            ],
        )
        records = reader._parse_trade_sheet(ws)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].code, "600519")

    def test_trade_invalid_numbers_skipped(self):
        """非法份额/价格/负值行跳过。"""
        ws = self._make_worksheet(
            "交易流水",
            ["日期", "代码", "操作", "份额", "价格"],
            [
                ["2026-01-05", "600900", "买入", "abc", 25.0],
                ["2026-01-06", "600900", "买入", 200, -5.0],
                ["2026-01-07", "600900", "买入", 200, 25.0],
            ],
        )
        records = reader._parse_trade_sheet(ws)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0].price, 25.0)

    def test_trade_action_normalization(self):
        """买卖中英文操作归一化为 buy/sell。"""
        for raw, expected in [
            ("买入", "buy"),
            ("买", "buy"),
            ("buy", "buy"),
            ("申购", "buy"),
            ("卖出", "sell"),
            ("卖", "sell"),
            ("sell", "sell"),
            ("赎回", "sell"),
        ]:
            ws = self._make_worksheet(
                "交易流水",
                ["日期", "代码", "操作", "份额", "价格"],
                [["2026-01-05", "600900", raw, 200, 25.0]],
            )
            records = reader._parse_trade_sheet(ws)
            self.assertEqual(records[0].action, expected, f"操作 {raw} 应归一化为 {expected}")

    # ── _parse_dividend_sheet ──────────────────────────────

    def test_dividend_sheet_valid(self):
        """分红流水正常解析。"""
        ws = self._make_worksheet(
            "分红流水",
            ["日期", "代码", "每份分红"],
            [
                ["2026-06-01", "600900", 0.35],
                ["2026-06-01", "600519", 0.0],
            ],
        )
        records = reader._parse_dividend_sheet(ws)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].date, "2026-06-01")
        self.assertEqual(records[0].code, "600900")
        self.assertAlmostEqual(records[0].amount, 0.35)

    def test_dividend_header_mismatch(self):
        """分红表头不匹配 -> 空列表。"""
        ws = self._make_worksheet(
            "分红流水",
            ["日期", "代码", "分红"],
            [["2026-06-01", "600900", 0.35]],
        )
        self.assertEqual(reader._parse_dividend_sheet(ws), [])

    def test_dividend_invalid_amount_skipped(self):
        """非法/负分红金额行跳过。"""
        ws = self._make_worksheet(
            "分红流水",
            ["日期", "代码", "每份分红"],
            [
                ["2026-06-01", "600900", -1.0],
                ["2026-06-01", "600519", 2.0],
            ],
        )
        records = reader._parse_dividend_sheet(ws)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].code, "600519")

    # ── read_flow_sheets 文件级入口 ────────────────────────

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_read_flow_sheets_with_sheets(self, mock_load, mock_exists):
        """含流水页签的工作簿 -> 解析两个页签。"""
        mock_exists.return_value = True
        wb = MagicMock()
        wb.sheetnames = ["交易流水", "分红流水"]
        wb.__getitem__.side_effect = {
            "交易流水": self._make_worksheet(
                "交易流水",
                ["日期", "代码", "操作", "份额", "价格"],
                [["2026-01-05", "600900", "买入", 200, 25.0]],
            ),
            "分红流水": self._make_worksheet(
                "分红流水",
                ["日期", "代码", "每份分红"],
                [["2026-06-01", "600900", 0.35]],
            ),
        }.get
        mock_load.return_value = wb

        transactions, dividends = reader.read_flow_sheets("flows.xlsx")
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].code, "600900")
        self.assertEqual(len(dividends), 1)
        self.assertEqual(dividends[0].amount, 0.35)
        wb.close.assert_called_once()

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_read_flow_sheets_missing_sheets(self, mock_load, mock_exists):
        """无流水页签 -> 返回空列表（向后兼容）。"""
        mock_exists.return_value = True
        wb = MagicMock()
        wb.sheetnames = ["证券账户"]
        mock_load.return_value = wb

        transactions, dividends = reader.read_flow_sheets("plain.xlsx")
        self.assertEqual(transactions, [])
        self.assertEqual(dividends, [])

    def test_read_flow_sheets_file_not_found(self):
        """文件不存在 -> FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            reader.read_flow_sheets("D:/nonexistent_flows_for_test.xlsx")

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_read_holdings_with_flows(self, mock_load, mock_exists):
        """read_holdings_with_flows 组合主表 + 流水。"""
        mock_exists.return_value = True
        wb = MagicMock()
        wb.sheetnames = ["证券账户", "交易流水", "分红流水"]
        wb.__getitem__.side_effect = {
            "证券账户": self._make_worksheet(
                "证券账户",
                ["名称", "代码", "持仓份额", "每份成本"],
                [["长江电力", "600900", 200, 50.0]],
            ),
            "交易流水": self._make_worksheet(
                "交易流水",
                ["日期", "代码", "操作", "份额", "价格"],
                [["2026-01-05", "600900", "买入", 200, 25.0]],
            ),
            "分红流水": self._make_worksheet(
                "分红流水",
                ["日期", "代码", "每份分红"],
                [["2026-06-01", "600900", 0.35]],
            ),
        }.get
        mock_load.return_value = wb

        result = reader.read_holdings_with_flows("full.xlsx")
        self.assertEqual(len(result.holdings), 1)
        self.assertEqual(result.holdings[0].name, "长江电力")
        self.assertEqual(len(result.transactions), 1)
        self.assertEqual(len(result.dividends), 1)

    def test_valid_date_formats(self):
        """日期格式判定：支持 - 与 / 分隔。"""
        self.assertTrue(reader._valid_date("2026-01-05"))
        self.assertTrue(reader._valid_date("2026/1/5"))
        self.assertFalse(reader._valid_date("20260105"))
        self.assertFalse(reader._valid_date("昨天"))
        self.assertFalse(reader._valid_date(""))

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_multi_account_with_flows(self, mock_load, mock_exists):
        """多账户主表 + 流水页签组合解析（流水为文件级单页签，不干扰多账户主表）。"""
        mock_exists.return_value = True
        wb = MagicMock()
        wb.sheetnames = ["账户A", "账户B", "交易流水", "分红流水"]
        wb.__getitem__.side_effect = {
            "账户A": self._make_worksheet(
                "账户A",
                ["名称", "代码", "持仓份额", "每份成本"],
                [["长江电力", "600900", 200, 50.0]],
            ),
            "账户B": self._make_worksheet(
                "账户B",
                ["名称", "代码", "持仓份额", "每份成本"],
                [["贵州茅台", "600519", 10, 1800.0]],
            ),
            "交易流水": self._make_worksheet(
                "交易流水",
                ["日期", "代码", "操作", "份额", "价格"],
                [["2026-01-05", "600900", "买入", 200, 25.0]],
            ),
            "分红流水": self._make_worksheet(
                "分红流水",
                ["日期", "代码", "每份分红"],
                [["2026-06-01", "600900", 0.35]],
            ),
        }.get
        mock_load.return_value = wb

        result = reader.read_holdings_with_flows("multi.xlsx")
        self.assertEqual(len(result.holdings), 2)
        accounts = {h.account for h in result.holdings}
        self.assertEqual(accounts, {"账户A", "账户B"})
        self.assertEqual(len(result.transactions), 1)
        self.assertEqual(len(result.dividends), 1)

    @patch("src.python.core.reader.os.path.exists")
    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_backward_compat_no_flows_field_equal(self, mock_load, mock_exists):
        """旧格式文件（无流水）：read_holdings_with_flows 的 holdings 与 read_holdings 逐字段一致。"""
        mock_exists.return_value = True
        wb = MagicMock()
        wb.sheetnames = ["证券账户"]
        wb.__getitem__.side_effect = {
            "证券账户": self._make_worksheet(
                "证券账户",
                ["名称", "代码", "持仓份额", "每份成本"],
                [["长江电力", "600900", 200, 50.0]],
            ),
        }.get
        mock_load.return_value = wb

        holdings_plain = reader.read_holdings("plain.xlsx")
        result = reader.read_holdings_with_flows("plain.xlsx")
        self.assertEqual(result.transactions, [])
        self.assertEqual(result.dividends, [])
        self.assertEqual(len(result.holdings), len(holdings_plain))
        for new, old in zip(result.holdings, holdings_plain):
            self.assertEqual(
                (new.account, new.name, new.code, new.shares, new.cost_price, new.data_status),
                (old.account, old.name, old.code, old.shares, old.cost_price, old.data_status),
            )

    def test_normalize_action_unknown(self):
        """未知操作返回 None。"""
        self.assertIsNone(reader._normalize_action("转仓"))
        self.assertIsNone(reader._normalize_action(""))
        self.assertEqual(reader._normalize_action("BUY"), "buy")


@pytest.mark.unit_core
class TestRequireHoldings(unittest.TestCase):
    """require_holdings — 空持仓门（读取域不变量，三渠道共用单一入口）。"""

    def test_nonempty_passes(self):
        """非空持仓直接通过（不抛异常、无返回值）。"""
        self.assertIsNone(reader.require_holdings([object()], "/tmp/a.xlsx"))

    def test_empty_raises_unified_hint(self):
        """空持仓 → ValueError，含「持仓文件为空」与四列格式提示。"""
        with self.assertRaises(ValueError) as ctx:
            reader.require_holdings([], "/tmp/holdings.xlsx")
        msg = str(ctx.exception)
        self.assertIn("持仓文件为空", msg)
        self.assertIn("四列", msg)
        self.assertIn("/tmp/holdings.xlsx", msg)

    def test_no_filepath_omits_path(self):
        """不传 filepath（HTTP 端）→ 文案不带服务端路径（无路径分隔符）。"""
        with self.assertRaises(ValueError) as ctx:
            reader.require_holdings([])
        msg = str(ctx.exception)
        self.assertIn("持仓文件为空", msg)
        self.assertNotIn("/", msg)
