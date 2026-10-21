"""持仓读取模块单元测试。

测试目标：
  - list_xlsx_files — 目录遍历/排序/临时文件跳过
  - get_xlsx_info — xlsx 元信息读取（账号数量、数据行数）
  - read_holdings — 正常解析/多账户/表头校验/空行跳过/数值校验/格式异常
  - _safe_str / _safe_float / _match_header — 辅助函数

运行：
  pytest src/test/unit/core/test_reader.py -v"""

from __future__ import annotations
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from src.python.core import reader
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestSafeStr(unittest.TestCase):
    """测试 _safe_str 转换逻辑。"""

    @pytest.mark.smoke
    def test_none_returns_empty(self):
        """None -> 空字符串。"""
        self.assertEqual(reader._safe_str(None), "")

    @pytest.mark.smoke
    def test_string_stripped(self):
        """字符串 -> 去除前后空格。"""
        self.assertEqual(reader._safe_str("  贵州茅台  "), "贵州茅台")

    @pytest.mark.smoke
    def test_number_to_string(self):
        """数字 -> 字符串。"""
        self.assertEqual(reader._safe_str(513300), "513300")

    def test_float_to_string(self):
        """浮点数 -> 字符串。"""
        self.assertEqual(reader._safe_str(100.5), "100.5")

    @pytest.mark.smoke
    def test_empty_string(self):
        """空字符串 -> 空字符串。"""
        self.assertEqual(reader._safe_str(""), "")

    def test_whitespace_only(self):
        """纯空格 -> 空字符串。"""
        self.assertEqual(reader._safe_str("   "), "")


class TestSafeFloat(unittest.TestCase):
    """测试 _safe_float 转换逻辑。"""

    def test_normal_float(self):
        """正常浮点数 -> float。"""
        self.assertEqual(reader._safe_float(100.5, "份额", "测试表", 2), 100.5)

    def test_integer(self):
        """整数 -> float。"""
        self.assertEqual(reader._safe_float(100, "份额", "测试表", 2), 100.0)

    def test_string_numeric(self):
        """数字字符串 -> float。"""
        self.assertEqual(reader._safe_float("100.5", "份额", "测试表", 2), 100.5)

    def test_none_returns_none(self):
        """None -> 返回 None 并记录警告。"""
        with self.assertLogs("invest", level="WARNING") as log:
            result = reader._safe_float(None, "份额", "测试表", 2)
        self.assertIsNone(result)
        self.assertIn("第 2 行 '份额' 为空", log.output[0])

    def test_invalid_string_returns_none(self):
        """不可解析的字符串 -> 返回 None 并记录警告。"""
        with self.assertLogs("invest", level="WARNING") as log:
            result = reader._safe_float("abc", "份额", "测试表", 2)
        self.assertIsNone(result)
        self.assertIn("第 2 行 '份额' 无法解析 (abc)", log.output[0])

    def test_boolean_true_returns_none(self):
        """布尔值 True -> None（份额列出现布尔是脏数据，不得静默变 1 股）。"""
        with self.assertLogs("invest", level="WARNING") as log:
            result = reader._safe_float(True, "份额", "测试表", 2)
        self.assertIsNone(result)
        self.assertIn("无法解析 (True)", log.output[0])

    def test_boolean_false_returns_none(self):
        """布尔值 False -> None（同上，不得静默变 0 股）。"""
        with self.assertLogs("invest", level="WARNING") as log:
            result = reader._safe_float(False, "份额", "测试表", 2)
        self.assertIsNone(result)
        self.assertIn("无法解析 (False)", log.output[0])

    def test_nan_returns_none(self):
        """NaN -> None（Excel =NA()/错误单元格；NaN 绕过 shares<=0 校验放行脏行）。"""
        with self.assertLogs("invest", level="WARNING") as log:
            result = reader._safe_float(float("nan"), "份额", "测试表", 2)
        self.assertIsNone(result)
        self.assertIn("无法解析 (nan)", log.output[0])

    def test_inf_returns_none(self):
        """±inf -> None。"""
        with self.assertLogs("invest", level="WARNING"):
            self.assertIsNone(reader._safe_float(float("inf"), "份额", "测试表", 2))
            self.assertIsNone(reader._safe_float(float("-inf"), "每份成本", "测试表", 3))


class TestMatchHeader(unittest.TestCase):
    """测试 _match_header 表头匹配逻辑。"""

    _expected = ["名称", "代码", "持仓份额", "每份成本"]

    def test_exact_match(self):
        """完全匹配 -> True。"""
        self.assertTrue(reader._match_header(self._expected, self._expected))

    def test_extra_columns(self):
        """比预期多列 -> True。"""
        actual = ["名称", "代码", "持仓份额", "每份成本", "备注", "市值"]
        self.assertTrue(reader._match_header(actual, self._expected))

    def test_fewer_columns(self):
        """比预期少列 -> False。"""
        actual = ["名称", "代码"]
        self.assertFalse(reader._match_header(actual, self._expected))

    def test_first_column_mismatch(self):
        """首列不匹配 -> False。"""
        actual = ["股票名称", "代码", "持仓份额", "每份成本"]
        self.assertFalse(reader._match_header(actual, self._expected))

    def test_middle_column_mismatch(self):
        """中间列不匹配 -> False。"""
        actual = ["名称", "证券代码", "持仓份额", "每份成本"]
        self.assertFalse(reader._match_header(actual, self._expected))

    def test_empty_actual(self):
        """空表头 -> False。"""
        self.assertFalse(reader._match_header([], self._expected))

    def test_whitespace_in_header(self):
        """表头含前后空格（实际不会被 _safe_str 传入，但防御性验证）。"""
        actual = ["  名称  ", "代码", "持仓份额", "每份成本"]
        self.assertFalse(reader._match_header(actual, self._expected))


class TestListXlsxFiles(unittest.TestCase):
    """测试 list_xlsx_files 目录遍历与排序。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir_path = self.tmpdir.name

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_directory_not_exist(self):
        """不存在的目录 -> 返回空列表。"""
        result = reader.list_xlsx_files("D:/nonexistent_dir_12345_test")
        self.assertEqual(result, [])

    def test_directory_empty(self):
        """空目录 -> 返回空列表。"""
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(result, [])

    def test_only_xlsx_files(self):
        """目录中只有 .xlsx 文件 -> 返回这些文件。"""
        f1 = os.path.join(self.dir_path, "a.xlsx")
        f2 = os.path.join(self.dir_path, "b.xlsx")
        open(f1, "w", encoding="utf-8").close()
        open(f2, "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(len(result), 2)
        self.assertIn(f1, result)
        self.assertIn(f2, result)

    def test_skip_non_xlsx(self):
        """非 .xlsx 文件被过滤。"""
        open(os.path.join(self.dir_path, "a.xlsx"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "b.csv"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "c.txt"), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith("a.xlsx"))

    def test_skip_temp_files(self):
        """跳过 ~$ 开头的临时文件。"""
        open(os.path.join(self.dir_path, "~$工作簿1.xlsx"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "工作簿1.xlsx"), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith("工作簿1.xlsx"))

    def test_all_temp_files_skipped(self):
        """全是 ~$ 临时文件 -> 返回空列表。"""
        open(os.path.join(self.dir_path, "~$a.xlsx"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "~$b.xlsx"), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(result, [])

    def test_case_insensitive_extension(self):
        """不区分 .xlsx 大小写。"""
        open(os.path.join(self.dir_path, "a.XLSX"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "b.Xlsx"), "w", encoding="utf-8").close()
        open(os.path.join(self.dir_path, "c.xlsX"), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(len(result), 3)

    def test_sorted_by_mtime_desc(self):
        """按修改时间降序排列。"""
        f1 = os.path.join(self.dir_path, "older.xlsx")
        f2 = os.path.join(self.dir_path, "newer.xlsx")
        open(f1, "w", encoding="utf-8").close()
        open(f2, "w", encoding="utf-8").close()
        now = time.time()
        os.utime(f1, (now, now - 100))
        os.utime(f2, (now, now))
        result = reader.list_xlsx_files(self.dir_path)
        self.assertEqual(result[0], f2)
        self.assertEqual(result[1], f1)

    def test_absolute_paths_returned(self):
        """返回绝对路径。"""
        open(os.path.join(self.dir_path, "a.xlsx"), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        self.assertTrue(os.path.isabs(result[0]))

    def test_mixed_files_with_xlsx(self):
        """混合各种类型的文件，只保留 .xlsx（不含 ~$）。"""
        for name in ["a.xlsx", "b.xlsx", "c.csv", "d.txt", "~$e.xlsx", "f.xlsx"]:
            open(os.path.join(self.dir_path, name), "w", encoding="utf-8").close()
        result = reader.list_xlsx_files(self.dir_path)
        basenames = {os.path.basename(p) for p in result}
        self.assertEqual(basenames, {"a.xlsx", "b.xlsx", "f.xlsx"})


class TestGetXlsxInfo(unittest.TestCase):
    """测试 get_xlsx_info 元信息读取。"""

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_single_sheet(self, mock_load):
        """单个工作表 -> 返回正确元信息。"""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["证券账户"]
        mock_ws = MagicMock()
        mock_ws.max_row = 10
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        result = reader.get_xlsx_info("dummy.xlsx")
        self.assertEqual(result["sheet_names"], ["证券账户"])
        self.assertEqual(result["accounts"], 1)
        self.assertEqual(result["total_rows"], 9)

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_multiple_sheets(self, mock_load):
        """多个工作表 -> 汇总所有账号行数。"""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["账户A", "账户B", "账户C"]

        def getitem(name):
            ws = MagicMock()
            ws.max_row = {"账户A": 10, "账户B": 5, "账户C": 2}[name]
            return ws

        mock_wb.__getitem__.side_effect = getitem
        mock_load.return_value = mock_wb

        result = reader.get_xlsx_info("dummy.xlsx")
        self.assertEqual(result["accounts"], 3)
        self.assertEqual(result["total_rows"], 14)

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_sheet_with_only_header(self, mock_load):
        """只有标题行无数据 -> total_rows 为 0。"""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["空白表"]
        mock_ws = MagicMock()
        mock_ws.max_row = 1
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        result = reader.get_xlsx_info("dummy.xlsx")
        self.assertEqual(result["total_rows"], 0)

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_sheet_with_none_max_row(self, mock_load):
        """max_row 为 None -> 按 1 处理，total_rows 为 0。"""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["空表"]
        mock_ws = MagicMock()
        mock_ws.max_row = None
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        result = reader.get_xlsx_info("dummy.xlsx")
        self.assertEqual(result["total_rows"], 0)

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_invalid_file_returns_error_dict(self, mock_load):
        """无法读取的文件 -> 返回含 error 字段的字典。"""
        mock_load.side_effect = OSError("无法打开文件")
        result = reader.get_xlsx_info("dummy.xlsx")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "无法打开文件")

    @patch("src.python.core.reader.openpyxl.load_workbook")
    def test_workbook_closed(self, mock_load):
        """get_xlsx_info 结束后应当 close workbook。"""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["证券账户"]
        mock_ws = MagicMock()
        mock_ws.max_row = 5
        mock_wb.__getitem__.return_value = mock_ws
        mock_load.return_value = mock_wb

        reader.get_xlsx_info("dummy.xlsx")
        mock_wb.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
