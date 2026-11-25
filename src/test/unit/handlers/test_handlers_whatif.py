"""TUI 调仓 What-if 模拟命令处理器单元测试。

测试 `_select_candidate_file`（目标持仓文件选择）与 `_cmd_whatif`（整体流程）。
全程 mock 文件系统与计算/输出函数，避免真实文件读写与报告产物残留。

运行：
  pytest src/test/unit/handlers/test_handlers_whatif.py -v
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.python.report.whatif_operations import WhatifRunResult

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestSelectCandidateFile(unittest.TestCase):
    """_select_candidate_file 目标持仓文件选择逻辑。"""

    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_excludes_base_and_auto_select(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
    ) -> None:
        """基准文件被排除后仅剩一个候选时自动选择。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx", "dummy_dir/target.xlsx"]
        out = __import__("io").StringIO()
        with patch("sys.stdout", out):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertEqual(result, "dummy_dir/target.xlsx")
        self.assertIn("唯一找到", out.getvalue())

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_only_base_no_candidate(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """目录下只有基准文件时引导手动输入；直接回车取消返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.return_value = ""
        out = __import__("io").StringIO()
        with patch("sys.stdout", out):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)
        self.assertIn("未找到", out.getvalue())

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_only_base_manual_input_valid(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """目录下只有基准文件时选[2]手动输入有效路径，返回该路径。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["2", "/tmp/after.xlsx"]
        with patch("src.python.tui.handlers_whatif.os.path.isfile", return_value=True):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        # 输入路径经 os.path.abspath 归一化（Windows 下 /tmp/... → D:\\tmp\\...），
        # 期望值同样用 abspath 构造，保证跨平台一致。
        self.assertEqual(result, os.path.abspath("/tmp/after.xlsx"))

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_manual_input_not_exist_then_cancel(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """手动输入的文件不存在时递归重输；再次回车取消返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["2", "/no/such.xlsx", ""]
        with patch("src.python.tui.handlers_whatif.os.path.isfile", return_value=False):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_manual_input_eof(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """手动输入时 input 引发 EOFError 返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["2", EOFError()]
        with patch("src.python.tui.handlers_whatif.os.path.isfile", return_value=True):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_only_base_choose_copy_template(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """目录下只有基准文件时选[1]自动复制模板，返回模板路径。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["1"]
        with (
            patch("src.python.tui.handlers_whatif.os.path.isdir", return_value=True),
            patch("src.python.tui.handlers_whatif.os.path.exists", return_value=False),
            patch("src.python.tui.handlers_whatif.shutil.copy2") as mock_copy2,
        ):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        # 模板路径经 os.path.join 拼接（Windows 下用 \\），期望值同源构造保证跨平台。
        expected = os.path.join("dummy_dir", "base-调仓后模板.xlsx")
        self.assertEqual(result, expected)
        mock_copy2.assert_called_once_with("dummy_dir/base.xlsx", expected)

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_only_base_invalid_choice_then_copy_template(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """无效选择后再次输入[1]复制模板，返回模板路径。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["x", "1"]
        with (
            patch("src.python.tui.handlers_whatif.os.path.isdir", return_value=True),
            patch("src.python.tui.handlers_whatif.os.path.exists", return_value=False),
            patch("src.python.tui.handlers_whatif.shutil.copy2"),
        ):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertEqual(result, os.path.join("dummy_dir", "base-调仓后模板.xlsx"))

    @patch("builtins.input")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_copy_template_failure_returns_none(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """复制模板失败（OSError）返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/base.xlsx"]
        mock_input.side_effect = ["1"]
        with (
            patch("src.python.tui.handlers_whatif.os.path.exists", return_value=False),
            patch(
                "src.python.tui.handlers_whatif.shutil.copy2",
                side_effect=OSError("disk full"),
            ),
        ):
            result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)

    @patch("builtins.input")
    @patch("os.path.getmtime")
    @patch("os.path.getsize")
    @patch("src.python.tui.handlers_whatif.get_xlsx_info")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_multiple_user_select(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_info: MagicMock,
        mock_size: MagicMock,
        mock_mtime: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """多个候选时用户输入编号选择。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/a.xlsx", "dummy_dir/b.xlsx", "dummy_dir/c.xlsx"]
        mock_info.return_value = {"accounts": 3}
        mock_input.return_value = "2"
        mock_size.return_value = 2048
        mock_mtime.return_value = 1000000.0
        result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertEqual(result, "dummy_dir/b.xlsx")

    @patch("builtins.input")
    @patch("os.path.getmtime")
    @patch("os.path.getsize")
    @patch("src.python.tui.handlers_whatif.get_xlsx_info")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_invalid_input(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_info: MagicMock,
        mock_size: MagicMock,
        mock_mtime: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """无效编号输入返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/a.xlsx", "dummy_dir/b.xlsx"]
        mock_info.return_value = {"accounts": 3}
        mock_input.return_value = "abc"
        mock_size.return_value = 2048
        mock_mtime.return_value = 1000000.0
        result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)

    @patch("builtins.input")
    @patch("os.path.getmtime")
    @patch("os.path.getsize")
    @patch("src.python.tui.handlers_whatif.get_xlsx_info")
    @patch("src.python.tui.handlers_whatif.list_xlsx_files")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    def test_eof_error(
        self,
        mock_config: MagicMock,
        mock_list: MagicMock,
        mock_info: MagicMock,
        mock_size: MagicMock,
        mock_mtime: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """input 引发 EOFError 时返回 None。"""
        from src.python.tui.handlers_whatif import _select_candidate_file

        mock_config.return_value = {"holdings_dir": "dummy_dir"}
        mock_list.return_value = ["dummy_dir/a.xlsx", "dummy_dir/b.xlsx"]
        mock_info.return_value = {"accounts": 3}
        mock_input.side_effect = EOFError()
        mock_size.return_value = 2048
        mock_mtime.return_value = 1000000.0
        result = _select_candidate_file("dummy_dir/base.xlsx")
        self.assertIsNone(result)


class TestCmdWhatif(unittest.TestCase):
    """_cmd_whatif 调仓模拟整体流程。"""

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.read_holdings")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_success_flow(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_read: MagicMock,
        mock_run: MagicMock,
        mock_config: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """正常流程：两份持仓 → 共享层计算 → 输出报告路径。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_config.return_value = {"output_dir": "reports"}
        mock_select_base.return_value = "dummy_dir/base.xlsx"
        mock_select_cand.return_value = "dummy_dir/target.xlsx"
        mock_read.side_effect = lambda p: [{"code": "000001", "name": "测试"}]
        mock_run.return_value = WhatifRunResult(ok=True, excel="/r/调仓模拟.xlsx", html="/r/调仓模拟.html")
        mock_prompt_eff.return_value = ""

        out = __import__("io").StringIO()
        with patch("sys.stdout", out):
            _cmd_whatif()

        mock_run.assert_called_once()
        # 输出目录由 config.resolve_output_dir 统一解析（绝对化），渠道不再自带回退链
        self.assertTrue(mock_run.call_args.kwargs["output_dir"].endswith("reports"))
        self.assertEqual(mock_run.call_args.kwargs["effective_date"], None)
        self.assertIn("调仓模拟报告已生成", out.getvalue())
        self.assertIn("调仓模拟.xlsx", out.getvalue())

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_base_not_selected(
        self,
        mock_select_base: MagicMock,
        mock_run: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """基准文件未选择时提前返回，不触发共享层。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_select_base.return_value = None
        with patch("sys.stdout", __import__("io").StringIO()):
            _cmd_whatif()
        mock_run.assert_not_called()
        mock_prompt_eff.assert_not_called()

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_candidate_not_selected(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_run: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """目标文件未选择时提前返回：不进共享层，也不问生效日期。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_select_base.return_value = "dummy_dir/base.xlsx"
        mock_select_cand.return_value = None
        with patch("sys.stdout", __import__("io").StringIO()):
            _cmd_whatif()
        mock_run.assert_not_called()
        mock_prompt_eff.assert_not_called()

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.read_holdings")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_empty_base_holdings(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_read: MagicMock,
        mock_run: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """基准持仓为空时提示错误，不触发共享层。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_select_base.return_value = "dummy_dir/base.xlsx"
        mock_select_cand.return_value = "dummy_dir/target.xlsx"
        mock_read.side_effect = lambda p: []
        out = __import__("io").StringIO()
        with patch("sys.stdout", out):
            _cmd_whatif()
        mock_run.assert_not_called()
        mock_prompt_eff.assert_not_called()
        self.assertIn("基准持仓读取失败或为空", out.getvalue())

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.read_holdings")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_data_not_available(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_read: MagicMock,
        mock_run: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """共享层返回不可用时提示错误，不打印报告路径。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_select_base.return_value = "dummy_dir/base.xlsx"
        mock_select_cand.return_value = "dummy_dir/target.xlsx"
        mock_read.side_effect = lambda p: [{"code": "000001", "name": "测试"}]
        mock_run.return_value = WhatifRunResult(ok=False, reason="两侧均为空")
        mock_prompt_eff.return_value = ""
        out = __import__("io").StringIO()
        with patch("sys.stdout", out):
            _cmd_whatif()
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.kwargs["effective_date"], None)
        self.assertIn("调仓对比数据不可用", out.getvalue())
        self.assertNotIn("调仓模拟报告已生成", out.getvalue())


class TestPromptEffectiveDate(unittest.TestCase):
    """_prompt_effective_date：格式校验委托共享层，非法重新询问（TUI 只做交互外壳）。"""

    @patch("builtins.input", side_effect=["20260101", "2026-07-01"])
    def test_reasks_until_valid(self, mock_input):
        from src.python.tui.handlers_whatif import _prompt_effective_date

        self.assertEqual(_prompt_effective_date(), "2026-07-01")
        self.assertEqual(mock_input.call_count, 2)

    @patch("builtins.input", return_value="")
    def test_blank_skips(self, mock_input):
        from src.python.tui.handlers_whatif import _prompt_effective_date

        self.assertEqual(_prompt_effective_date(), "")

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_interrupt_skips(self, mock_input):
        from src.python.tui.handlers_whatif import _prompt_effective_date

        self.assertEqual(_prompt_effective_date(), "")


if __name__ == "__main__":
    unittest.main()


class TestEffectiveDateEscCancel(unittest.TestCase):
    """日期录入处 Esc 统一取消（PromptCancelledError，与同命令兄弟提示同径）。"""

    def test_date_prompt_esc_cancels(self):
        """生效日录入处按 Esc → 中止 What-if 流程（而非当作跳过继续向导）。"""
        from src.python.tui.handlers_whatif import PromptCancelledError, _prompt_effective_date

        with (
            patch("src.python.tui.handlers_whatif.input_choice", return_value=None),
            pytest.raises(PromptCancelledError),
        ):
            _prompt_effective_date()

    def test_effective_date_prompt_declares_skip(self) -> None:
        """生效日提示：回车=跳过（写明动作名与后果），不是裸回车。"""
        from src.python.tui import handlers_whatif

        prompts: list[str] = []

        def _capture(prompt):
            prompts.append(prompt)
            return ""

        with patch.object(handlers_whatif, "input_choice", _capture):
            assert handlers_whatif._prompt_effective_date() == ""
        assert prompts, "未捕获到生效日提示"
        assert "回车=跳过" in prompts[0]


class TestCopyBaseAsTemplate(unittest.TestCase):
    """_copy_base_as_template — 复制基准文件为目标模板（同名追加序号）。"""

    def _run(self, holdings_dir, base_file, exists=None, copy_side=None):
        from src.python.tui import handlers_whatif as hw

        exists = exists or (lambda p: False)
        with (
            patch.object(hw, "get_config_cache", return_value={"holdings_dir": holdings_dir}),
            patch.object(hw, "emit_error") as mock_err,
            patch.object(hw.os.path, "isdir", return_value=bool(holdings_dir)),
            patch.object(hw.os.path, "exists", side_effect=exists),
            patch.object(hw.shutil, "copy2", side_effect=copy_side) as mock_copy,
            patch("builtins.print"),
        ):
            result = hw._copy_base_as_template(base_file)
        return result, mock_err, mock_copy

    def test_holdings_dir_unusable_reports_error(self):
        """持仓目录未配置/不存在 → 报错并返回 None（不落任何副本）。"""
        result, mock_err, mock_copy = self._run("", "/x/基准.xlsx")
        assert result is None
        mock_err.assert_called_once()
        mock_copy.assert_not_called()

    def test_collision_appends_sequence_suffix(self):
        """同名模板已存在 → 追加 ``-1`` 序号，避免覆盖用户已编辑的模板。"""
        result, _err, mock_copy = self._run("/holdings", "/x/基准.xlsx", exists=lambda p: p.endswith("调仓后模板.xlsx"))
        assert result is not None
        assert result.endswith("基准-调仓后模板-1.xlsx")
        mock_copy.assert_called_once()

    def test_copy_failure_returns_none(self):
        """复制抛 OSError → 报错并返回 None（流程可退回手动输入）。"""
        result, mock_err, _copy = self._run("/holdings", "/x/基准.xlsx", copy_side=OSError("disk full"))
        assert result is None
        assert "复制基准文件失败" in mock_err.call_args.args[0]


class TestManualInputPath(unittest.TestCase):
    """_manual_input_path — 取消与异常一律返回 None。"""

    def test_eof_returns_none(self):
        from src.python.tui import handlers_whatif as hw

        with (
            patch.object(hw, "input_choice", side_effect=EOFError),
            patch("builtins.print"),
        ):
            assert hw._manual_input_path() is None

    def test_cancel_returns_none(self):
        from src.python.tui import handlers_whatif as hw

        with patch.object(hw, "input_choice", return_value=None):
            assert hw._manual_input_path() is None


class TestInputCandidatePath(unittest.TestCase):
    """_input_candidate_path — 无候选文件时的引导分支。"""

    def test_eof_returns_none(self):
        from src.python.tui import handlers_whatif as hw

        with (
            patch.object(hw, "emit_error"),
            patch.object(hw, "input_choice", side_effect=EOFError),
            patch("builtins.print"),
        ):
            assert hw._input_candidate_path("/x/基准.xlsx") is None

    def test_cancel_returns_none(self):
        from src.python.tui import handlers_whatif as hw

        with (
            patch.object(hw, "emit_error"),
            patch.object(hw, "input_choice", return_value=None),
            patch("builtins.print"),
        ):
            assert hw._input_candidate_path("/x/基准.xlsx") is None


class TestSelectCandidateCancelAndInvalid(unittest.TestCase):
    """_select_candidate_file — Esc 取消与无效编号。"""

    def _run(self, choice):
        from src.python.tui import handlers_whatif as hw

        with (
            patch.object(hw, "list_xlsx_files", return_value=["/h/甲.xlsx", "/h/乙.xlsx", "/h/丙.xlsx"]),
            patch.object(hw, "get_config_cache", return_value={"holdings_dir": "/h"}),
            patch.object(hw, "input_choice", return_value=choice),
            patch.object(hw, "get_xlsx_info", return_value={"accounts": 1}),
            patch.object(hw.os.path, "getsize", return_value=1024),
            patch.object(hw.os.path, "getmtime", return_value=1_700_000_000.0),
            patch("builtins.print"),
        ):
            return hw._select_candidate_file("/h/甲.xlsx")

    def test_esc_returns_none(self):
        assert self._run(None) is None

    def test_out_of_range_returns_none(self):
        assert self._run("9") is None


class TestCmdWhatifErrorBranches(unittest.TestCase):
    """_cmd_whatif 目标持仓不可读与运行异常两条降级分支。"""

    @patch("src.python.tui.handlers_whatif.get_config_cache")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.read_holdings")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_unreadable_target_reports_and_stops(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_read: MagicMock,
        mock_run: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """目标持仓读不出条目 → 报目标不可读并中止，不进入模拟。"""
        from src.python.report.whatif_operations import WHATIF_TARGET_HOLDINGS_UNREADABLE
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_config.return_value = {"output_dir": "reports"}
        mock_select_base.return_value = "d/base.xlsx"
        mock_select_cand.return_value = "d/target.xlsx"
        mock_read.side_effect = lambda p: [{"code": "000001", "name": "测试"}]

        def _read(path):
            return [] if path.endswith("target.xlsx") else [{"code": "000001", "name": "测试"}]

        mock_read.side_effect = _read
        with (
            patch("src.python.tui.handlers_whatif.emit_error") as mock_err,
            patch("sys.stdout", __import__("io").StringIO()),
        ):
            _cmd_whatif()

        mock_err.assert_called_once()
        self.assertIn(WHATIF_TARGET_HOLDINGS_UNREADABLE, mock_err.call_args.args[0])
        mock_run.assert_not_called()

    @patch("src.python.tui.handlers_whatif._prompt_effective_date")
    @patch("src.python.tui.handlers_whatif.get_config_cache")
    @patch("src.python.report.whatif_operations.run_whatif_simulation")
    @patch("src.python.tui.handlers_whatif.read_holdings")
    @patch("src.python.tui.handlers_whatif._select_candidate_file")
    @patch("src.python.tui.handlers_whatif.select_holdings_file")
    def test_simulation_exception_error_hint(
        self,
        mock_select_base: MagicMock,
        mock_select_cand: MagicMock,
        mock_read: MagicMock,
        mock_run: MagicMock,
        mock_config: MagicMock,
        mock_prompt_eff: MagicMock,
    ) -> None:
        """模拟抛异常 → 记日志并给出统一失败提示，不向 TUI 抛出。"""
        from src.python.tui.handlers_whatif import _cmd_whatif

        mock_config.return_value = {"output_dir": "reports"}
        mock_select_base.return_value = "d/base.xlsx"
        mock_select_cand.return_value = "d/target.xlsx"
        mock_read.return_value = [{"code": "000001", "name": "测试"}]
        mock_prompt_eff.return_value = ""
        mock_run.side_effect = RuntimeError("boom")

        with (
            patch("src.python.tui.handlers_whatif.print_error_with_hint") as mock_hint,
            patch("sys.stdout", __import__("io").StringIO()),
        ):
            _cmd_whatif()

        mock_hint.assert_called_once()
        self.assertEqual(mock_hint.call_args.args[1], "调仓 What-if 模拟失败")
