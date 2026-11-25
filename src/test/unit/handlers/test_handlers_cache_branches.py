# -*- coding: utf-8 -*-
"""TUI 缓存管理动线（handlers_cache）：选文件→清缓存→跑更新→格式化输出。

覆盖：
  - `_read_holdings_and_clear_cache` 的四态（未选文件 / 校验失败 / 清理有产出 / 清理无产出 / 读取异常）
  - `_run_cache_update` 的早退（无持仓）与更新异常降级（含按键闸门）
  - `_cmd_update_basic_cache` / `_cmd_update_position_cache` 的分组名与更新函数绑定
  - `_render_cache_stats` 的最大文件列表与快照目录不可读降级

上屏文本用 capsys 断言；取数与清理入口全部替身，零网络、零真实缓存目录。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.python.tui import handlers_cache

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


_HOLDINGS = [{"name": "长江电力", "code": "600900", "shares": 100}]


class TestReadHoldingsAndClearCache:
    def test_no_file_selected_returns_none(self, capsys):
        with (
            patch.object(handlers_cache, "refresh_config"),
            patch.object(handlers_cache, "select_holdings_file", return_value=""),
        ):
            assert handlers_cache._read_holdings_and_clear_cache("refresh") is None
        assert capsys.readouterr().out == ""

    def test_holdings_validation_failure_emits_error(self):
        with (
            patch.object(handlers_cache, "refresh_config"),
            patch.object(handlers_cache, "select_holdings_file", return_value="/tmp/持仓.xlsx"),
            patch.object(handlers_cache, "read_holdings", return_value=[]),
            patch.object(handlers_cache, "require_holdings", side_effect=ValueError("持仓文件为空")),
            patch.object(handlers_cache, "emit_error") as emitted,
        ):
            assert handlers_cache._read_holdings_and_clear_cache("refresh") is None
        emitted.assert_called_once_with("持仓文件为空", "cache")

    def test_cleared_groups_reported(self, capsys):
        with (
            patch.object(handlers_cache, "refresh_config"),
            patch.object(handlers_cache, "select_holdings_file", return_value="/tmp/持仓.xlsx"),
            patch.object(handlers_cache, "read_holdings", return_value=_HOLDINGS),
            patch.object(handlers_cache, "require_holdings"),
            patch("src.python.cache.clear_by_group", return_value={"fund_perf": 3, "price": 2}),
        ):
            assert handlers_cache._read_holdings_and_clear_cache("refresh") == _HOLDINGS
        out = capsys.readouterr().out
        assert "共 1 条持仓记录" in out
        assert "fund_perf 3条 + price 2条 已清除" in out

    def test_nothing_to_clear(self, capsys):
        with (
            patch.object(handlers_cache, "refresh_config"),
            patch.object(handlers_cache, "select_holdings_file", return_value="/tmp/持仓.xlsx"),
            patch.object(handlers_cache, "read_holdings", return_value=_HOLDINGS),
            patch.object(handlers_cache, "require_holdings"),
            patch("src.python.cache.clear_by_group", return_value={}),
        ):
            assert handlers_cache._read_holdings_and_clear_cache("refresh") == _HOLDINGS
        assert "无缓存需清除" in capsys.readouterr().out

    def test_read_exception_reported_with_hint(self):
        with (
            patch.object(handlers_cache, "refresh_config"),
            patch.object(handlers_cache, "select_holdings_file", return_value="/tmp/持仓.xlsx"),
            patch.object(handlers_cache, "read_holdings", side_effect=OSError("文件被占用")),
            patch.object(handlers_cache, "print_error_with_hint") as printed,
        ):
            assert handlers_cache._read_holdings_and_clear_cache("refresh") is None
        printed.assert_called_once()
        assert printed.call_args.args[1] == "读取持仓失败"


class TestRunCacheUpdate:
    def test_returns_early_without_holdings(self):
        update_fn = Mock()
        with patch.object(handlers_cache, "_read_holdings_and_clear_cache", return_value=None):
            handlers_cache._run_cache_update("refresh", update_fn, Mock(), "基础缓存")
        update_fn.assert_not_called()

    def test_success_passes_reporter_and_prints(self):
        seen = {}

        def update(holdings, reporter):
            seen["holdings"] = holdings
            seen["reporter"] = type(reporter).__name__
            return "结果对象"

        print_fn = Mock()
        with (
            patch.object(handlers_cache, "_read_holdings_and_clear_cache", return_value=_HOLDINGS),
            patch.object(handlers_cache, "press_any_key") as gated,
        ):
            handlers_cache._run_cache_update("refresh", update, print_fn, "基础缓存")
        assert seen["holdings"] == _HOLDINGS
        assert seen["reporter"] == "TuiProgressReporter"
        print_fn.assert_called_once_with("结果对象")
        gated.assert_called_once()

    def test_update_exception_degrades_and_still_gates(self, caplog):
        with (
            patch.object(handlers_cache, "_read_holdings_and_clear_cache", return_value=_HOLDINGS),
            patch.object(handlers_cache, "press_any_key") as gated,
            patch.object(handlers_cache, "print_error_with_hint") as printed,
        ):
            handlers_cache._run_cache_update("refresh", Mock(side_effect=RuntimeError("网络全挂")), Mock(), "基础缓存")
        assert printed.call_args.args[1] == "更新基础缓存"
        assert "网络全挂" in str(printed.call_args.args[0])
        gated.assert_called_once()


class TestCommands:
    def test_basic_cache_command_binds_group_and_fn(self):
        update = Mock(return_value=SimpleNamespace())
        with (
            patch("src.python.cache.operations.update_basic_cache", update),
            patch.object(handlers_cache, "_run_cache_update") as runner,
        ):
            handlers_cache._cmd_update_basic_cache()
        assert runner.call_args.args[0] == "refresh"
        assert runner.call_args.args[3] == "基础缓存"

    def test_position_cache_command_binds_preload_group(self):
        update = Mock(return_value=SimpleNamespace())
        with (
            patch("src.python.cache.operations.update_position_cache", update),
            patch.object(handlers_cache, "_run_cache_update") as runner,
        ):
            handlers_cache._cmd_update_position_cache()
        assert runner.call_args.args[0] == "preload"
        assert runner.call_args.args[3] == "行情类缓存"


def _stats(**overrides):
    stats = {
        "total_files": 4,
        "total_size_bytes": 2048,
        "hit_total": 10,
        "hit_rate": 50.0,
        "top_by_size": [("price_600900", 1024), ("fund_perf_005827", 512)],
        "by_prefix": {"price": 2, "fund_perf": 2},
        "expired": 1,
        "snapshot_files": 2,
        "snapshot_size_bytes": 4096,
        "state_files": 0,
        "state_size_bytes": 0,
    }
    stats.update(overrides)
    return SimpleNamespace(**stats)


class TestRenderCacheStats:
    def test_lists_top_files_and_snapshot_block(self, tmp_path, capsys):
        snapshot_dir = tmp_path / "snapshots"
        snapshot_dir.mkdir()
        (snapshot_dir / "2026-11-25.json").write_text("{}", encoding="utf-8")
        with (
            patch("src.python.cache.operations.get_cache_stats", return_value=_stats()),
            patch("src.python.cache.get_cache_dir", return_value=str(tmp_path)),
            patch("src.python.core.constants.PROJECT_ROOT", str(tmp_path)),
        ):
            handlers_cache._render_cache_stats()
        out = capsys.readouterr().out
        assert "最大文件:" in out
        assert "price_600900.json" in out
        assert "前缀分布:" in out
        assert "过期文件: 1 个" in out

    def test_snapshot_dir_unreadable_degrades(self, tmp_path, capsys):
        stats = _stats(snapshot_files=2)
        with (
            patch("src.python.cache.operations.get_cache_stats", return_value=stats),
            patch("src.python.cache.get_cache_dir", return_value=str(tmp_path)),
            patch("src.python.core.constants.PROJECT_ROOT", str(tmp_path)),
            patch.object(handlers_cache.os, "listdir", side_effect=OSError("目录已消失")),
        ):
            handlers_cache._render_cache_stats()
        out = capsys.readouterr().out
        assert "data/history/snapshots" in out
        assert "最新:" not in out  # 目录不可读只丢最新一行，统计主体保留
