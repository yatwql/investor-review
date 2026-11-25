"""TUI 诊断面板的交互分支（`tui/handlers_log`）：无效输入 / 配置读失败 / 窄档渲染 / 自检失败。

这些分支是「用户按错键」「配置文件坏了」「自检进程挂了」的真实路径：面板必须给出
明确提示并留在原面板（不抛异常、不静默退出），否则一次手误就把用户踢回主菜单。
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest

from src.python.tui.handlers_log import (
    _cmd_diagnose_menu,
    _cmd_log_settings,
    _cmd_run_doctor,
    _cmd_view_health_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _item(group: str, ok: bool) -> dict:
    """自检结果条目（`core/doctor` 的渲染契约形状：group/label/message/ok/hint）。"""
    return {
        "group": group,
        "label": f"{group} 检查",
        "message": "ok" if ok else "failed",
        "ok": ok,
        "hint": "" if ok else "按提示修复",
    }


def _stdout():
    return patch("sys.stdout", new_callable=io.StringIO)


class TestDiagnoseMenu:
    def test_invalid_choice_reports_and_stays(self):
        """输入 L/V/H/T/0 之外的键 → 提示无效、留在面板，随后 0 才返回。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["X", "0"]),
            _stdout() as out,
        ):
            _cmd_diagnose_menu()

        assert "无效选择" in out.getvalue()
        assert "L/V/H/T/0" in out.getvalue(), "提示须列出合法键位"

    def test_empty_input_runs_doctor(self):
        """空回车 = 缺省项（系统自检），不落回主菜单。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["", "0"]),
            patch("src.python.tui.handlers_log._cmd_run_doctor") as doctor,
        ):
            _cmd_diagnose_menu()

        doctor.assert_called_once_with()


class TestLogSettings:
    def test_read_failure_reports_and_returns(self):
        """读日志设置失败（配置文件损坏）→ [ERR] 提示并返回，不进编号面板。"""
        from src.python.config import LoggerConfigError

        with (
            patch("src.python.config.read_logger_config", side_effect=LoggerConfigError("bad json")),
            patch("src.python.tui.handlers_log.emit_error") as emit,
            _stdout(),
        ):
            _cmd_log_settings()

        emit.assert_called_once()
        assert "读取日志设置失败" in emit.call_args.args[0]

    def test_out_of_range_number_reports_and_stays(self):
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["9", "0"]),
            _stdout() as out,
        ):
            _cmd_log_settings()

        assert "无效选择" in out.getvalue()
        assert "1-6" in out.getvalue()

    def test_empty_new_value_keeps_current(self):
        """选中编号后直接回车 = 不修改：回到编号面板而不是退出。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["1", "", "0"]),
            patch("src.python.config.write_logger_config") as write,
            _stdout(),
        ):
            _cmd_log_settings()

        write.assert_not_called()

    def test_non_integer_for_numeric_field_reports(self):
        """数值型字段（单文件上限/备份份数/首屏行数）填非数字 → [ERR] 提示，不写配置。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["3", "abc", "0"]),
            patch("src.python.config.write_logger_config") as write,
            _stdout() as out,
        ):
            _cmd_log_settings()

        assert "应为整数" in out.getvalue()
        write.assert_not_called()

    def test_numeric_field_applies_scale(self):
        """数值型字段按单位换算后写盘（单文件上限 MB → 字节）。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["3", "5", "0"]),
            patch("src.python.config.write_logger_config") as write,
            _stdout(),
        ):
            _cmd_log_settings()

        write.assert_called_once_with({"max_bytes": 5 * 1024 * 1024})


class TestLogSettingsWrite:
    def test_level_value_is_upper_cased(self):
        """级别字段统一转大写写盘（小写输入也生效）。"""
        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["1", "info", "0"]),
            patch("src.python.config.write_logger_config") as write,
            _stdout(),
        ):
            _cmd_log_settings()

        write.assert_called_once_with({"level": "INFO"})

    def test_write_failure_reports_and_continues(self):
        """写盘失败（配置只读）→ [ERR] 提示并留在面板，不退出。"""
        from src.python.config import LoggerConfigError

        with (
            patch("src.python.tui.tui_keys.input_choice", side_effect=["1", "DEBUG", "0"]),
            patch("src.python.config.write_logger_config", side_effect=LoggerConfigError("read-only")),
            _stdout() as out,
        ):
            _cmd_log_settings()

        assert "[ERR]" in out.getvalue()
        assert "read-only" in out.getvalue()


class TestHealthHistoryNarrow:
    def _summary(self):
        return {
            "timestamp": "2026-08-16T10:00:00",
            "report_type": "basic",
            "holdings_count": 3,
            "total": 10,
            "ok_count": 8,
            "fail_count": 2,
            "failed_sources": ["腾讯K线"],
        }

    def test_narrow_columns_split_into_two_lines(self):
        """窄档：一条记录压成「时间 + 结果」两行，避免列错位。"""
        with (
            patch("src.python.core.perf.summarize_health_history", return_value=[self._summary()]),
            patch("src.python.tui.switch_panel.use_panel_box", return_value=False),
            patch("src.python.tui.handlers_log.terminal_columns", return_value=40),
            patch("src.python.tui.pager.view") as view,
            _stdout(),
        ):
            _cmd_view_health_history()

        body = view.call_args.args[1]
        assert any("2026-08-16 10:00:00" in line for line in body)
        assert any("8/10 正常" in line and "失败 2" in line for line in body)

    def test_empty_failed_sources_skips_hanging_line(self):
        summary = self._summary()
        summary["failed_sources"] = []
        with (
            patch("src.python.core.perf.summarize_health_history", return_value=[summary]),
            patch("src.python.tui.switch_panel.use_panel_box", return_value=True),
            patch("src.python.tui.handlers_log.terminal_columns", return_value=120),
            patch("src.python.tui.pager.view") as view,
            _stdout(),
        ):
            _cmd_view_health_history()

        body = view.call_args.args[1]
        assert not any("失败源" in line for line in body)


class TestRunDoctor:
    def test_network_prompt_accepts_yes_alias(self):
        """`y`/`yes`/`是` 都认作联网自检；文案标出时间预算。"""
        results = [_item("env", True)]
        with (
            patch("src.python.tui.handlers_log.input_choice", return_value="是"),
            patch("src.python.core.doctor.run_doctor_checks", return_value=results) as run,
            patch("src.python.tui.pager.view"),
            _stdout() as out,
        ):
            _cmd_run_doctor()

        assert run.call_args.kwargs["include_network"] is True
        assert "含数据源联网检查" in out.getvalue()

    def test_failed_checks_get_fix_hint(self):
        results = [_item("env", True), _item("network", False), _item("config", False)]
        with (
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.core.doctor.run_doctor_checks", return_value=results),
            patch("src.python.tui.pager.view") as view,
            _stdout(),
        ):
            _cmd_run_doctor()

        body = view.call_args.args[1]
        assert any("2 项未通过" in line for line in body), "失败项数须上屏并指向修复建议"

    def test_all_passed_prints_ok_line(self):
        results = [_item("env", True)]
        with (
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.core.doctor.run_doctor_checks", return_value=results),
            patch("src.python.tui.pager.view") as view,
            _stdout(),
        ):
            _cmd_run_doctor()

        assert any("全部通过" in line for line in view.call_args.args[1])

    def test_run_failure_reports_and_returns(self):
        """自检执行抛异常（环境探测崩）→ [ERR] 提示 + 指向日志，不把 traceback 抛给用户。"""
        with (
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.core.doctor.run_doctor_checks", side_effect=RuntimeError("probe")),
            patch("src.python.tui.handlers_log.emit_error") as emit,
            patch("src.python.tui.pager.view") as view,
            _stdout(),
        ):
            _cmd_run_doctor()

        emit.assert_called_once()
        assert "系统自检执行失败" in emit.call_args.args[0]
        view.assert_not_called()
