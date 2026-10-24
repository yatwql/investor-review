"""test_cli 兄弟分片（cache_whatif）：缓存更新与调仓 What-if 子命令。"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.python.cli.cli import _EXIT_SEVERE, _EXIT_SUCCESS, _build_parser, _handle_cache_update, _handle_whatif
from src.python.report.whatif_operations import WhatifRunResult

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


@pytest.mark.unit
class TestHandleCacheUpdate:
    """_handle_cache_update 委托测试。"""

    def test_update_basic(self):
        """--update basic 委托 update_basic_cache 并返回 exit_code。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0

        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.cache.operations.update_basic_cache", return_value=mock_result),
        ):
            code = _handle_cache_update("basic", {}, MagicMock())
        assert code == 0

    def test_update_position(self):
        """--update position 委托 update_position_cache。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0

        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.cache.operations.update_position_cache", return_value=mock_result),
        ):
            code = _handle_cache_update("position", {}, MagicMock())
        assert code == 0

    def test_update_all_max_effort(self):
        """--update all 最大努力：basic 失败后仍执行 position。"""
        mock_basic = MagicMock()
        mock_basic.exit_code = 1
        mock_pos = MagicMock()
        mock_pos.exit_code = 0

        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.cache.operations.update_basic_cache", return_value=mock_basic),
            patch("src.python.cache.operations.update_position_cache", return_value=mock_pos),
        ):
            code = _handle_cache_update("all", {}, MagicMock())
        assert code == 1  # max(1, 0)

    def test_holdings_none_returns_severe(self):
        """持仓为 None 时返回 _EXIT_SEVERE。"""
        with patch("src.python.cli._handlers._cli_read_holdings", return_value=None):
            code = _handle_cache_update("basic", {}, MagicMock())
        assert code == _EXIT_SEVERE


@pytest.mark.unit
class TestHandleWhatif:
    """_handle_whatif 委托测试。"""

    def _args(self, base=None, candidate="after.xlsx"):
        return _build_parser().parse_args(["whatif", "--candidate", candidate] + (["--base", base] if base else []))

    def test_success_explicit_base(self):
        """显式 --base + --candidate → 委托共享层生成报告并返回成功。"""
        with (
            patch("src.python.core.reader.read_holdings", side_effect=[[MagicMock()], [MagicMock()]]),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            mock_run.return_value = WhatifRunResult(ok=True, excel="/r/调仓模拟.xlsx", html="/r/调仓模拟.html")
            code = _handle_whatif(self._args(base="before.xlsx"), {})
        assert code == _EXIT_SUCCESS
        mock_run.assert_called_once()
        from src.python.config import get_default

        assert mock_run.call_args.kwargs["base_file"] == "before.xlsx"
        assert mock_run.call_args.kwargs["output_dir"] == get_default("output_dir")

    def test_success_config_default_base(self):
        """缺省 --base → 用 config 持仓文件（_cli_read_holdings）。"""
        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.core.reader.read_holdings", return_value=[MagicMock()]),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            mock_run.return_value = WhatifRunResult(ok=True, excel="/r/e.xlsx", html="/r/e.html")
            code = _handle_whatif(self._args(), {"holdings_dir": "data/holdings", "holdings_filename": "cur.xlsx"})
        assert code == _EXIT_SUCCESS
        mock_run.assert_called_once()

    def test_base_read_failure_severe(self):
        """基准持仓读取失败 → 返回 _EXIT_SEVERE，不触发共享层。"""
        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=None),
            patch("src.python.core.reader.read_holdings", return_value=None),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            code = _handle_whatif(self._args(base="before.xlsx"), {})
        assert code == _EXIT_SEVERE
        mock_run.assert_not_called()

    def test_candidate_read_failure_severe(self):
        """目标持仓读取失败 → 返回 _EXIT_SEVERE，不触发共享层。"""
        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.core.reader.read_holdings", return_value=None),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            code = _handle_whatif(self._args(), {})
        assert code == _EXIT_SEVERE
        mock_run.assert_not_called()

    def test_unavailable_data_severe(self):
        """共享层返回不可用 → 返回 _EXIT_SEVERE。"""
        with (
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.core.reader.read_holdings", return_value=[MagicMock()]),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            mock_run.return_value = WhatifRunResult(ok=False, reason="调仓对比数据为空")
            code = _handle_whatif(self._args(), {})
        assert code == _EXIT_SEVERE
        mock_run.assert_called_once()

    def test_effective_date_passthrough(self):
        """--effective-date → 透传到 run_whatif_simulation kwargs。"""
        with (
            # 基准持仓（未传 --base）走 _cli_read_holdings，目标持仓走 read_holdings；
            # 两者都要 stub，否则会真读 data/holdings/ 而依赖开发机本地文件
            patch("src.python.cli._handlers._cli_read_holdings", return_value=[MagicMock()]),
            patch("src.python.core.reader.read_holdings", side_effect=[[MagicMock()], [MagicMock()]]),
            patch("src.python.report.whatif_operations.run_whatif_simulation") as mock_run,
        ):
            mock_run.return_value = WhatifRunResult(ok=True, excel="/r/e.xlsx", html="/r/e.html")
            args = _build_parser().parse_args(["whatif", "--candidate", "after.xlsx", "--effective-date", "2026-07-01"])
            code = _handle_whatif(args, {})
        assert code == _EXIT_SUCCESS
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["effective_date"] == "2026-07-01"
