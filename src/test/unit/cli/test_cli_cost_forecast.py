"""CLI 事前费用预估与日预算单元测试（--yes / 交互确认 / 非交互硬闸）。

覆盖：
  - report 子命令 ``--yes`` 解析
  - ``_confirm_cost_forecast``：交互 y/N、非交互跳过确认、日预算超限
    非交互直接中止（自动化硬闸）、预估失败不阻塞
  - ``_handle_report``：中止 → 退出码 2 且不进生成；降级 → 清空强刷范围；
    非 full 模式不触发预估
"""

from __future__ import annotations

import argparse
import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest

from src.python.cli import _confirm_cost_forecast, _handle_report, _build_parser, _EXIT_SEVERE

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


def _fc(**over):
    base = {"ok": True, "module_count": 3, "low": 0.1, "high": 0.9, "basis": "static", "symbol": "¥", "reason": None}
    base.update(over)
    return base


def _budget(**over):
    base = {"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False, "symbol": "¥"}
    base.update(over)
    return base


def _confirm_with(fc, budget, *, stdin_tty=True, yes=False, non_interactive=False, answer="y"):
    """在受控环境下执行 _confirm_cost_forecast，返回 (结果, stdout)。"""
    args = argparse.Namespace(yes=yes, non_interactive=non_interactive)
    stdin = MagicMock()
    stdin.isatty.return_value = stdin_tty
    buf = io.StringIO()
    with (
        patch("src.python.llm.cost_forecast.forecast_run_cost", return_value=fc),
        patch("src.python.llm.cost_forecast.budget_status", return_value=budget),
        patch("src.python.cli._handlers.sys.stdin", stdin),
        patch("builtins.input", return_value=answer) if isinstance(answer, str) else patch("builtins.input", answer),
        contextlib.redirect_stdout(buf),
    ):
        result = _confirm_cost_forecast(args)
    return result, buf.getvalue()


class TestParserYesFlag:
    """report 子命令 --yes 解析。"""

    def test_yes_flag_parsed(self):
        args = _build_parser().parse_args(["report", "--type", "full", "--yes"])
        assert args.yes is True
        assert args.type == "full"

    def test_yes_flag_defaults_false(self):
        args = _build_parser().parse_args(["report"])
        assert args.yes is False


class TestConfirmCostForecast:
    """_confirm_cost_forecast 分支矩阵。"""

    def test_interactive_confirm_yes(self):
        result, out = _confirm_with(_fc(), _budget(), stdin_tty=True, answer="y")
        assert result == (True, False)
        assert "费用预估" in out, "预估行须上屏"

    def test_interactive_confirm_default_aborts(self):
        result, _ = _confirm_with(_fc(), _budget(), stdin_tty=True, answer="")
        assert result == (False, False)

    def test_yes_flag_skips_prompt(self):
        result, _ = _confirm_with(
            _fc(),
            _budget(),
            yes=True,
            answer=MagicMock(side_effect=AssertionError("--yes 不应询问")),
        )
        assert result == (True, False)

    def test_non_interactive_skips_prompt(self):
        result, _ = _confirm_with(
            _fc(), _budget(), non_interactive=True, answer=MagicMock(side_effect=AssertionError("非交互不应询问"))
        )
        assert result == (True, False)

    def test_non_tty_skips_prompt(self):
        result, _ = _confirm_with(
            _fc(), _budget(), stdin_tty=False, answer=MagicMock(side_effect=AssertionError("非 TTY 不应询问"))
        )
        assert result == (True, False)

    def test_forecast_unavailable_nonblocking(self):
        result, _ = _confirm_with(
            _fc(ok=False, reason="模型未知"), _budget(), answer=MagicMock(side_effect=AssertionError("不阻塞"))
        )
        assert result == (True, False)

    def test_zero_modules_skips_prompt(self):
        result, _ = _confirm_with(
            _fc(module_count=0, low=0.0, high=0.0), _budget(), answer=MagicMock(side_effect=AssertionError("无模块"))
        )
        assert result == (True, False)

    def test_budget_exceeded_noninteractive_aborts(self):
        """非交互 + 超限 → 直接中止（自动化的预算硬闸），打印 [ERR]。"""
        result, out = _confirm_with(
            _fc(),
            _budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            stdin_tty=True,
            non_interactive=True,
            answer=MagicMock(side_effect=AssertionError("非交互超限不应询问")),
        )
        assert result == (False, False)
        assert "[ERR]" in out and "日预算上限" in out

    def test_budget_exceeded_yes_degrades(self):
        result, _ = _confirm_with(
            _fc(),
            _budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            stdin_tty=True,
            answer="y",
        )
        assert result == (True, True)

    def test_budget_exceeded_no_aborts(self):
        result, _ = _confirm_with(
            _fc(),
            _budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            stdin_tty=True,
            answer="n",
        )
        assert result == (False, False)


class TestHandleReportGating:
    """_handle_report 的预估门接线（中止退出码 / 降级清强刷 / 非 full 不触发）。"""

    @staticmethod
    def _args(**over):
        base = dict(
            type="full",
            verbose=False,
            history=None,
            force_llm=False,
            llm_module=None,
            output=None,
            prefer_source=None,
            exclude_source=None,
            yes=False,
            non_interactive=False,
        )
        base.update(over)
        return argparse.Namespace(**base)

    def test_abort_returns_severe_without_generation(self):
        with (
            patch("src.python.cli._handlers._cli_read_holdings_with_flows", return_value=([], [], [])),
            patch("src.python.cli._handlers._confirm_cost_forecast", return_value=(False, False)),
            patch("src.python.report.orchestrator.generate_report") as gen,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = _handle_report(self._args(), {})
        assert code == _EXIT_SEVERE
        gen.assert_not_called()

    def test_degrade_clears_force_scope(self):
        captured = {}

        def _fake_generate(**kwargs):
            captured.update(kwargs)
            return MagicMock(exit_code=0)

        with (
            patch("src.python.cli._handlers._cli_read_holdings_with_flows", return_value=([], [], [])),
            patch("src.python.cli._handlers._confirm_cost_forecast", return_value=(True, True)),
            patch("src.python.report.orchestrator.generate_report", side_effect=_fake_generate),
            patch("src.python.cli._handlers._resolve_source_overrides", return_value=(None, None)),
            patch("src.python.fetcher.chain.chain_overrides"),
        ):
            code = _handle_report(self._args(force_llm=True, llm_module=["global_macro"]), {})
        assert code == 0
        assert captured["force_llm"] is False, "降级走缓存须清空全量强刷"
        assert captured["force_llm_modules"] is None, "降级走缓存须清空模块级强刷"

    def test_basic_mode_never_asks(self):
        with (
            patch("src.python.cli._handlers._cli_read_holdings_with_flows", return_value=([], [], [])),
            patch(
                "src.python.cli._handlers._confirm_cost_forecast",
                side_effect=AssertionError("非 full 模式不应触发费用预估确认"),
            ),
            patch("src.python.report.orchestrator.generate_report", return_value=MagicMock(exit_code=0)),
            patch("src.python.cli._handlers._resolve_source_overrides", return_value=(None, None)),
            patch("src.python.fetcher.chain.chain_overrides"),
        ):
            code = _handle_report(self._args(type="basic"), {})
        assert code == 0

    def test_full_passes_force_through_when_confirmed(self):
        captured = {}

        def _fake_generate(**kwargs):
            captured.update(kwargs)
            return MagicMock(exit_code=0)

        with (
            patch("src.python.cli._handlers._cli_read_holdings_with_flows", return_value=([], [], [])),
            patch("src.python.cli._handlers._confirm_cost_forecast", return_value=(True, False)),
            patch("src.python.report.orchestrator.generate_report", side_effect=_fake_generate),
            patch("src.python.cli._handlers._resolve_source_overrides", return_value=(None, None)),
            patch("src.python.fetcher.chain.chain_overrides"),
        ):
            _handle_report(self._args(force_llm=True), {})
        assert captured["force_llm"] is True, "未降级时强刷范围原样透传"
