"""Excel 输出引擎单元测试 — 异常场景与边界测试。

测试目标：
  - _ensure_reports_dir — 目录创建/写入权限异常
  - save_workbook — 存档权限异常降级
  - create_workbook/write_title_row/write_header_row/write_data_row
  - write_subtotal_row/write_total_row
  - auto_width / freeze_header

运行：
  pytest src/test/unit/report/test_excel_writer.py -v
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from src.python.report import excel_writer as ew
from src.python.report.styles import FMT_MONEY
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestCreateWorkbook(unittest.TestCase):
    """Workbook 创建测试。"""

    def test_create_workbook(self):
        """create_workbook 返回合法 Workbook。"""
        wb = ew.create_workbook()
        self.assertIsInstance(wb, Workbook)

    def test_create_workbook_has_active_sheet(self):
        """新 Workbook 默认有一个活动页签。"""
        wb = ew.create_workbook()
        self.assertIsNotNone(wb.active)


class TestEnsureReportsDir(unittest.TestCase):
    """_ensure_reports_dir 异常场景测试。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_directory(self):
        """目录不存在 → 创建目录和子目录。"""
        sub = os.path.join(self.tmp.name, "reports")
        ew._ensure_reports_dir(sub)
        # 目录应存在（内含 YYYYMMDD 子目录）
        self.assertTrue(os.path.exists(sub))

    def test_no_permission_raises(self):
        """无写入权限 → 抛出 PermissionError。"""
        # 创建一个只读目录
        readonly_dir = os.path.join(self.tmp.name, "readonly")
        os.makedirs(readonly_dir, exist_ok=True)
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                ew._ensure_reports_dir(readonly_dir)


class TestSaveWorkbook(unittest.TestCase):
    """save_workbook 异常场景测试。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wb = ew.create_workbook()
        ws = self.wb.active
        ws.title = "测试"
        ws.cell(row=1, column=1, value="test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_success(self):
        """正常保存 → 返回最新文件路径。"""
        path = ew.save_workbook(self.wb, output_dir=self.tmp.name)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".xlsx"))

    def test_archive_failure_still_returns_latest(self):
        """存档权限异常 → 降级，最新版仍保存成功（原子落盘：写临时再替换）。"""
        calls = {"n": 0}

        def _fake_save(_wb, path):
            # 模拟真实 Workbook.save 落盘：首次写文件成功，存档那次抛权限异常
            calls["n"] += 1
            if calls["n"] > 1:
                raise PermissionError("denied")
            with open(path, "wb") as f:
                f.write(b"PK\x03\x04stub")

        with patch("openpyxl.Workbook.save", _fake_save):
            # 不应抛异常
            path = ew.save_workbook(self.wb, output_dir=self.tmp.name)
            self.assertIsNotNone(path)
            # 原子落盘：最终文件在，临时文件无残留
            self.assertTrue(os.path.exists(path))
            self.assertFalse(os.path.exists(path + ".tmp"))


class TestWriteRows(unittest.TestCase):
    """各类行写入函数测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_write_title_row(self):
        """标题行写入并返回下一行号。"""
        row = ew.write_title_row(self.ws, 1, "测试标题", 5)
        self.assertEqual(row, 2)
        self.assertEqual(self.ws.cell(row=1, column=1).value, "测试标题")

    def test_write_header_row(self):
        """表头行写入。"""
        headers = ["名称", "代码", "价格"]
        row = ew.write_header_row(self.ws, 1, headers)
        self.assertEqual(row, 2)
        self.assertEqual(self.ws.cell(row=1, column=1).value, "名称")

    def test_write_data_row(self):
        """数据行写入。"""
        vals = ["长江电力", "600900", 26.65]
        row = ew.write_data_row(self.ws, 1, vals)
        self.assertEqual(row, 2)

    def test_write_data_row_with_fmts(self):
        """带格式的数据行写入。"""
        fmts = ["", "", FMT_MONEY]
        ew.write_data_row(self.ws, 1, [1, 2, 1234.56], fmts)
        cell = self.ws.cell(row=1, column=3)
        self.assertEqual(cell.value, 1234.56)

    def test_write_subtotal_row(self):
        """小计行写入。"""
        ew.write_title_row(self.ws, 1, "测试", 8)
        ew.write_header_row(self.ws, 2, ["A", "B", "C", "D", "E", "F", "G", "H"])
        vals = ["", "", "", "", 100.0, 80.0, 20.0, 0.25, 5.0]
        row = ew.write_subtotal_row(self.ws, 3, "测试小计", vals, 8)
        self.assertIsNotNone(row)

    def test_write_total_row(self):
        """总计行写入。"""
        ew.write_title_row(self.ws, 1, "测试", 8)
        ew.write_header_row(self.ws, 2, ["A", "B", "C", "D", "E", "F", "G", "H"])
        vals = ["", "", "", "", 1000.0, 800.0, 200.0, 0.25, 50.0]
        row = ew.write_total_row(self.ws, 3, "总计", vals, 8)
        self.assertIsNotNone(row)


class TestAutoWidth(unittest.TestCase):
    """auto_width 边界测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_auto_width_basic(self):
        """基本列宽自适应。"""
        self.ws.cell(row=1, column=1, value="名称")
        self.ws.cell(row=2, column=1, value="长江电力")
        ew.auto_width(self.ws)
        col_letter = chr(64 + 1)  # A
        width = self.ws.column_dimensions[col_letter].width
        self.assertIsNotNone(width)

    def test_auto_width_cjk(self):
        """CJK 字符占用双倍宽度。"""
        self.ws.cell(row=1, column=1, value="长江电力投资有限公司")
        ew.auto_width(self.ws)
        width = self.ws.column_dimensions["A"].width
        self.assertGreater(width, 10)

    def test_auto_width_with_min_max(self):
        """min_width / max_width 参数。"""
        self.ws.cell(row=1, column=1, value="短")
        ew.auto_width(self.ws, min_width=10, max_width=40)
        width = self.ws.column_dimensions["A"].width
        self.assertGreaterEqual(width, 10)

    def test_auto_width_empty(self):
        """空工作表 → 不崩溃。"""
        try:
            ew.auto_width(self.ws)
        except Exception as e:  # noqa: BLE001 — 测试断言口径：空表自动列宽不得抛异常，抛出即判失败
            self.fail(f"auto_width on empty sheet raised: {e}")


class TestFreezeHeader(unittest.TestCase):
    """freeze_header 测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_freeze_header(self):
        """冻结首行。"""
        ew.freeze_header(self.ws, 2)
        self.assertIsNotNone(self.ws.freeze_panes)

    def test_freeze_header_empty(self):
        """空 sheet 冻结 → 不崩溃。"""
        try:
            ew.freeze_header(self.ws, 2)
        except Exception as e:  # noqa: BLE001 — 测试断言口径：空表冻结表头不得抛异常，抛出即判失败
            self.fail(f"freeze_header raised: {e}")


if __name__ == "__main__":
    unittest.main()


# ═══════════════════════════════════════════════════════════
#  数据源状态页脚 / 占位测试
# ═══════════════════════════════════════════════════════════


class TestDataStatusFoot(unittest.TestCase):
    """_write_data_status_foot 页脚写入测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_all_available_no_render(self):
        """全部 available=True → 不新增任何行。"""
        max_row_before = self.ws.max_row
        ew._write_data_status_foot(
            self.ws,
            {
                "source_a": {"available": True, "tier": "T2", "message": "OK"},
                "source_b": {"available": True, "tier": "T3", "message": "OK"},
            },
        )
        self.assertEqual(self.ws.max_row, max_row_before)

    def test_empty_dict_no_render(self):
        """空字典 → 不新增行。"""
        max_row_before = self.ws.max_row
        ew._write_data_status_foot(self.ws, {})
        self.assertEqual(self.ws.max_row, max_row_before)

    def test_with_failures(self):
        """有失败项 → 渲染标题行 + 状态行。"""
        row_start = 5
        next_row = ew._write_data_status_foot(
            self.ws,
            {
                "industry": {"available": False, "tier": "T3", "message": "行业分类数据不可用"},
                "rank": {"available": False, "tier": "T2", "message": "排名数据不可用"},
            },
            start_row=row_start,
        )
        # 标题行 + 2 条状态 = 3 行
        self.assertEqual(next_row, row_start + 3)
        # 验证标题行
        title_val = self.ws.cell(row=row_start, column=1).value
        self.assertIsNotNone(title_val)
        self.assertIn("数据加载状态", str(title_val))
        # 验证 ℹ 前缀
        industry_val = self.ws.cell(row=row_start + 1, column=1).value
        self.assertIn("ℹ", str(industry_val))
        # 验证 ⚠ 前缀
        rank_val = self.ws.cell(row=row_start + 2, column=1).value
        self.assertIn("⚠", str(rank_val))

    def test_with_mixed_available(self):
        """混合 available=True/False → 只渲染失败项。"""
        ew._write_data_status_foot(
            self.ws,
            {
                "source_a": {"available": True, "tier": "T2", "message": "OK"},
                "source_b": {"available": False, "tier": "T3", "message": "出错啦"},
            },
            start_row=1,
        )
        # 标题 + 1 行 = 3 行
        row_val = self.ws.cell(row=2, column=1).value
        self.assertIn("ℹ", str(row_val))

    def test_tier_font_color(self):
        """状态行字体为灰色。"""
        ew._write_data_status_foot(
            self.ws,
            {
                "test": {"available": False, "tier": "T2", "message": "测试失败"},
            },
            start_row=1,
        )
        cell = self.ws.cell(row=2, column=1)
        font_color = cell.font.color
        self.assertIsNotNone(font_color)
        # openpyxl 可能返回 Color 对象，也可能返回 str
        color_str = str(font_color.rgb if hasattr(font_color, "rgb") else font_color)
        self.assertTrue("999" in color_str or "99" in color_str, f"字体颜色 {color_str} 不是灰色")


class TestWritePlaceholder(unittest.TestCase):
    """_write_placeholder 占位写入测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_placeholder_basic(self):
        """占位文本写入。"""
        self.ws.cell(row=1, column=1, value="已有内容")
        next_row = ew._write_placeholder(self.ws, "测试占位文本")
        # 应写在已有内容 + 2 空行后
        self.assertEqual(next_row, 4)
        cell_val = self.ws.cell(row=3, column=1).value
        self.assertEqual(cell_val, "测试占位文本")


class TestWriteStatusTitle(unittest.TestCase):
    """_write_status_title 标题写入测试。"""

    def setUp(self):
        self.wb = ew.create_workbook()
        self.ws = self.wb.active

    def test_stauts_title_text(self):
        """标题文本为 '数据加载状态'。"""
        ew._write_status_title(self.ws, 3, 5)
        cell_val = self.ws.cell(row=3, column=1).value
        self.assertEqual(cell_val, "数据加载状态")


class TestEnsureReportsDirArchiveBranch(unittest.TestCase):
    """_ensure_reports_dir 存档子目录权限探测分支。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_archive_subdir_not_writable_raises(self):
        """根目录可写但存档子目录不可写 → 报存档子目录无权限（定位到失败层）。"""
        real_open = open
        calls = {"n": 0}

        def _open(path, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:  # 第 2 次即存档子目录探测
                raise PermissionError("denied")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=_open):
            with self.assertRaises(PermissionError) as ctx:
                ew._ensure_reports_dir(self.tmp.name)
        self.assertIn("存档子目录", str(ctx.exception))


class TestCleanupOldArchives(unittest.TestCase):
    """_cleanup_old_archives — 过期归档目录清理与异常兜底。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _mkdir(self, name):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(path, exist_ok=True)
        return path

    def test_old_archive_dir_removed_and_others_kept(self):
        """超过保留期的 YYYYMMDD 目录被删；非 8 位数字目录与非日期名一律保留。"""
        from datetime import datetime, timedelta

        old = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
        fresh = datetime.now().strftime("%Y%m%d")
        old_path = self._mkdir(old)
        fresh_path = self._mkdir(fresh)
        notes_path = self._mkdir("notes")

        ew._cleanup_old_archives(self.tmp.name, max_days=180)

        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(fresh_path))
        self.assertTrue(os.path.exists(notes_path))

    def test_invalid_date_dir_skipped(self):
        """8 位数字但非法日期 → ValueError 分支跳过，目录保留且不抛出。"""
        bad = self._mkdir("99999999")
        ew._cleanup_old_archives(self.tmp.name, max_days=180)
        self.assertTrue(os.path.exists(bad))

    def test_listdir_exception_swallowed(self):
        """扫描目录异常（非关键路径）→ 记 warning 后返回，不向上抛出。"""
        with patch("os.listdir", side_effect=OSError("boom")):
            with self.assertLogs("invest", level="WARNING") as captured:
                ew._cleanup_old_archives(self.tmp.name, max_days=180)
        self.assertTrue(any("归档清理过程异常" in line for line in captured.output))


class TestSaveWorkbookLatestPermissionError(unittest.TestCase):
    """最新版落盘权限异常：记 error 后向上抛出（调用方需感知未保存）。"""

    def test_latest_permission_error_raised(self):
        wb = ew.create_workbook()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ew, "_save_workbook_atomic", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    ew.save_workbook(wb, output_dir=tmp)


class TestWriteHeaderRowTypeError(unittest.TestCase):
    """write_header_row 参数契约：row 非 int 时快速失败并给出调用签名提示。"""

    def test_non_int_row_raises_type_error(self):
        wb = ew.create_workbook()
        ws = wb.active
        with self.assertRaises(TypeError) as ctx:
            ew.write_header_row(ws, "3", ["A", "B"])
        self.assertIn("write_header_row", str(ctx.exception))
