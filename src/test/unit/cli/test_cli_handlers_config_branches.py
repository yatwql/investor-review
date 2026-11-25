"""CLI 配置子命令与持仓读取的成功/校验分支（`cli/_handlers`）。

两条契约：
  - 持仓读取成功路径必须打出条数日志（排除「读到 0 条却当成功」的静默放行）；
  - `config set` 的文本解析失败一律转 ``ConfigEditError``（带可操作提示），
    且 `--dry-run` 只校验不写盘、写盘成功要回报备份文件名。
"""

from __future__ import annotations

import argparse
import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from src.python.cli import _handlers
from src.python.config.edit_ops import ConfigEditError

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


def _holdings_book(tmp_path):
    book = tmp_path / "持仓.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["名称", "代码", "持仓份额", "每份成本"])
    ws.append(["长江电力", "600900", 100, 10.0])
    wb.save(book)
    return book


class TestReadHoldingsSuccess:
    def test_holdings_loaded_and_logged(self, tmp_path, caplog):
        """有效持仓 → 返回列表并记录条数（证明不是「读到 0 条」的静默放行）。"""
        book = _holdings_book(tmp_path)
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(book)}

        with caplog.at_level("INFO", logger="invest"):
            holdings = _handlers._cli_read_holdings(config)

        assert holdings and len(holdings) == 1
        assert "成功读取持仓文件" in caplog.text

    def test_missing_file_returns_none(self, tmp_path):
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(tmp_path / "不存在.xlsx")}

        assert _handlers._cli_read_holdings(config) is None

    def test_with_flows_missing_file_returns_none(self, tmp_path):
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(tmp_path / "不存在.xlsx")}

        assert _handlers._cli_read_holdings_with_flows(config) is None

    def test_with_flows_returns_triple(self, tmp_path):
        book = _holdings_book(tmp_path)
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(book)}

        parsed = _handlers._cli_read_holdings_with_flows(config)

        assert parsed is not None
        holdings, transactions, dividends = parsed
        assert len(holdings) == 1
        assert transactions == [] and dividends == []


class TestConfigValueParsing:
    def test_int_field_rejects_non_numeric(self):
        with pytest.raises(ConfigEditError) as exc:
            _handlers._parse_cli_config_value("llm_max_concurrency", "abc", {"kind": "int"})

        assert "需要整数" in str(exc.value)

    def test_int_field_parses(self):
        assert _handlers._parse_cli_config_value("llm_max_concurrency", "8", {"kind": "int"}) == 8

    def test_bool_field_rejects_unknown_token(self):
        with pytest.raises(ConfigEditError):
            _handlers._parse_cli_config_value("some_flag", "maybe", {"kind": "bool"})

    def test_bool_field_parses(self):
        assert _handlers._parse_cli_config_value("some_flag", "yes", {"kind": "bool"}) is True

    def test_scheduler_weekdays_rejects_non_numeric(self):
        with pytest.raises(ConfigEditError) as exc:
            _handlers._parse_scheduler_value("weekdays", "1,x")

        assert "scheduler.weekdays" in str(exc.value)

    def test_scheduler_weekdays_parses(self):
        assert _handlers._parse_scheduler_value("weekdays", "1, 3,5") == [1, 3, 5]

    def test_scheduler_enabled_parses_bool(self):
        assert _handlers._parse_scheduler_value("enabled", "off") is False

    def test_unknown_scheduler_field_in_current_value(self):
        with pytest.raises(ConfigEditError) as exc:
            _handlers._config_current_value("scheduler.not_a_field")

        assert "未知调度字段" in str(exc.value)


class TestConfigList:
    def test_plain_text_lists_values_and_action_keys(self):
        """非 JSON 输出：标量键逐行 `key = value`，动作型键标出可用动作。"""
        keys = {
            "llm_max_concurrency": {"writer": "scalar"},
            "comparison_indices": {"writer": "comparison_indices", "actions": ("add", "remove")},
        }
        with (
            patch("src.python.config.edit_ops.config_edit_whitelist", keys),
            patch("src.python.config.edit_ops.read_config_value", return_value=4),
            patch("src.python.config.edit_ops.scheduler_values", return_value={}),
        ):
            code, out = _capture(_handlers._handle_config_list, False)

        assert code == 0
        assert "llm_max_concurrency = 4" in out
        assert "<动作型: add/remove>" in out

    def test_json_output_has_values_and_actions(self):
        keys = {"llm_max_concurrency": {"writer": "scalar"}, "llm_providers.priority": {"writer": "llm_providers"}}
        with (
            patch("src.python.config.edit_ops.config_edit_whitelist", keys),
            patch("src.python.config.edit_ops.read_config_value", return_value=4),
            patch("src.python.config.edit_ops.scheduler_values", return_value={}),
        ):
            code, out = _capture(_handlers._handle_config_list, True)

        assert code == 0
        assert '"values"' in out and '"actions"' in out


class TestConfigSetScheduler:
    def _args(self, key: str, value: str, dry_run: bool = False):
        return argparse.Namespace(key=key, value=value, dry_run=dry_run)

    def test_dry_run_validates_without_writing(self):
        with (
            patch("src.python.config.edit_ops.scheduler_field_names", return_value=["enabled"]),
            patch("src.python.config.edit_ops.validate_scheduler_value", return_value=True),
            patch("src.python.config.edit_ops.set_scheduler_field") as write,
        ):
            code, out = _capture(_handlers._handle_config_set, self._args("scheduler.enabled", "on", True))

        assert code == 0
        assert "校验通过" in out
        write.assert_not_called()

    def test_write_reports_backup_file(self):
        with (
            patch("src.python.config.edit_ops.scheduler_field_names", return_value=["enabled"]),
            patch(
                "src.python.config.edit_ops.set_scheduler_field",
                return_value={"value": {"enabled": True}, "backup": "/tmp/cfg.bak"},
            ),
        ):
            code, out = _capture(_handlers._handle_config_set, self._args("scheduler.enabled", "on"))

        assert code == 0
        assert "已备份：/tmp/cfg.bak" in out

    def test_unknown_scheduler_field_raises(self):
        with patch("src.python.config.edit_ops.scheduler_field_names", return_value=["enabled"]):
            with pytest.raises(ConfigEditError) as exc:
                _handlers._handle_config_set(self._args("scheduler.bogus", "1"))

        assert "未知调度字段" in str(exc.value)


class TestConfigSetScalar:
    def _args(self, key: str, value: str, dry_run: bool = False):
        return argparse.Namespace(key=key, value=value, dry_run=dry_run)

    def test_write_reports_backup_file(self):
        whitelist = {"llm_max_concurrency": {"kind": "int", "writer": "scalar"}}
        with (
            patch("src.python.config.edit_ops.config_edit_whitelist", whitelist),
            patch(
                "src.python.config.edit_ops.apply_config_edit",
                return_value={"value": 8, "backup": "/tmp/config.json.bak"},
            ),
        ):
            code, out = _capture(_handlers._handle_config_set, self._args("llm_max_concurrency", "8"))

        assert code == 0
        assert "已备份：/tmp/config.json.bak" in out

    def test_dry_run_previews_without_writing(self):
        whitelist = {"llm_max_concurrency": {"kind": "int", "writer": "scalar"}}
        with (
            patch("src.python.config.edit_ops.config_edit_whitelist", whitelist),
            patch("src.python.config.edit_ops.preview_config_edit", return_value={"value": 8}) as preview,
            patch("src.python.config.edit_ops.apply_config_edit") as apply_edit,
        ):
            code, out = _capture(_handlers._handle_config_set, self._args("llm_max_concurrency", "8", True))

        assert code == 0
        assert "校验通过" in out
        preview.assert_called_once()
        apply_edit.assert_not_called()

    def test_unknown_key_rejected(self):
        with patch("src.python.config.edit_ops.config_edit_whitelist", {}):
            with pytest.raises(ConfigEditError) as exc:
                _handlers._handle_config_set(self._args("nope", "1"))

        assert "不在白名单" in str(exc.value)

    def test_action_only_key_rejected(self):
        whitelist = {"comparison_indices": {"writer": "comparison_indices"}}
        with patch("src.python.config.edit_ops.config_edit_whitelist", whitelist):
            with pytest.raises(ConfigEditError) as exc:
                _handlers._handle_config_set(self._args("comparison_indices", "x"))

        assert "动作型键" in str(exc.value)


class TestConfigDispatchError:
    def test_dispatch_converts_edit_error_to_exit_code(self):
        """`config` 入口把编辑层异常转成非零退出码 + [ERR] 提示，不抛栈给用户。"""
        args = argparse.Namespace(config_action="get", key="nope")
        with patch.object(_handlers, "_config_current_value", MagicMock(side_effect=ConfigEditError("bad key"))):
            code, out = _capture(_handlers._handle_config, args, {})

        assert code != 0
        assert "[ERR]" in out
        assert "bad key" in out


class TestProviderSourceArgs:
    def _args(self, prefer=None, exclude=None):
        return argparse.Namespace(prefer_source=prefer, exclude_source=exclude)

    def test_unknown_source_names_abort_with_available_list(self):
        """未知源名 → SystemExit 提示可用源（避免拼错源名静默变成「全默认」）。"""
        with patch("src.python.fetcher.chain.known_provider_names", return_value={"tencent", "sina"}):
            with pytest.raises(SystemExit) as exc:
                _handlers._resolve_source_overrides(self._args(prefer=["tengxun"]))

        message = str(exc.value.code)
        assert "未知数据源" in message
        assert "tencent" in message

    def test_known_sources_returned(self):
        with patch("src.python.fetcher.chain.known_provider_names", return_value={"tencent", "sina"}):
            preferred, exclude = _handlers._resolve_source_overrides(self._args(prefer=["tencent", "sina"]))

        assert preferred == "tencent"
        assert exclude == ()

    def test_no_args_returns_empty(self):
        assert _handlers._resolve_source_overrides(self._args()) == (None, ())


class TestStdoutUtf8Probe:
    def test_non_utf8_stdout_disables_color(self):
        """cp936 控制台上色会输成乱码 → 探测为 False。"""
        with (
            patch("src.python.core.ansi_colors.supports_color", return_value=True),
            patch.object(_handlers.sys, "stdout", MagicMock(encoding="cp936")),
        ):
            assert _handlers._use_ansi_color() is False

    def test_utf8_stdout_with_color_support(self):
        with (
            patch("src.python.core.ansi_colors.supports_color", return_value=True),
            patch.object(_handlers.sys, "stdout", MagicMock(encoding="utf-8")),
        ):
            assert _handlers._use_ansi_color() is True


class TestBoolSpecConversion:
    def test_argparse_error_is_converted_to_edit_error(self):
        """argparse 的布尔校验异常转成编辑层异常（CLI 统一 [ERR] 呈现）。"""
        with patch(
            "src.python.cli._parser._parse_switch_bool",
            MagicMock(side_effect=argparse.ArgumentTypeError("布尔取值须为 on/off")),
        ):
            with pytest.raises(ConfigEditError) as exc:
                _handlers._parse_cli_config_value("some_flag", "x", {"kind": "bool"})

        assert "布尔取值须为 on/off" in str(exc.value)


class TestSchedulerBoolField:
    def test_invalid_switch_token_converted_to_edit_error(self):
        """`scheduler.enabled` 取值非法 → argparse 异常转编辑层异常（统一提示通道）。"""
        with patch(
            "src.python.cli._parser._parse_switch_bool",
            MagicMock(side_effect=argparse.ArgumentTypeError("布尔取值须为 on/off")),
        ):
            with pytest.raises(ConfigEditError) as exc:
                _handlers._parse_scheduler_value("enabled", "maybe")

        assert "布尔取值须为 on/off" in str(exc.value)


class TestArtifactPathsPrinting:
    def test_degradation_line_printed_after_paths(self):
        """有产物且有本轮降级 → 路径之后追加一行降级汇总（与报告数据状态块同源）。"""
        with (
            patch("src.python.core.artifacts.collect_artifacts", return_value=["/tmp/r.html"]),
            patch("src.python.core.degradation.report_degradation_summary", return_value={"text": "行情 T2 降级"}),
            patch.object(_handlers, "resolve_output_dir", return_value="/tmp"),
        ):
            code, out = _capture(_handlers._print_artifact_paths, {}, None)

        assert "[!] 行情 T2 降级" in out

    def test_no_artifacts_prints_nothing(self):
        with patch("src.python.core.artifacts.collect_artifacts", return_value=[]):
            _code, out = _capture(_handlers._print_artifact_paths, {}, None)

        assert out == ""

    def test_no_degradation_keeps_single_listing(self):
        with (
            patch("src.python.core.artifacts.collect_artifacts", return_value=["/tmp/r.html"]),
            patch("src.python.core.degradation.report_degradation_summary", return_value={"text": ""}),
            patch.object(_handlers, "resolve_output_dir", return_value="/tmp"),
        ):
            _code, out = _capture(_handlers._print_artifact_paths, {}, None)

        assert "[!]" not in out
