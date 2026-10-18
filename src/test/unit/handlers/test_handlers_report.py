"""TUI 报告生成命令处理器单元测试。

测试可独立辅助函数。

运行：
  pytest src/test/unit/handlers/test_handlers_report.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.mark.unit_core
class TestPromptForceLlm(unittest.TestCase):
    """_prompt_force_llm 用户确认（返回 (force_llm, force_llm_modules) 元组）。"""

    def test_yes_returns_true(self):
        """输入 y + 回车全量 → (True, None)，并调用 reporter.ok。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["y", ""]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (True, None))
        self.assertEqual(reporter.ok.call_count, 1)

    def test_no_returns_false(self):
        """输入 n → (False, None)。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", return_value="n"):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, None))
        reporter.ok.assert_not_called()

    def test_empty_input_returns_false(self):
        """空回车 → (False, None)。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", return_value=""):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, None))

    def test_eof_error_returns_false(self):
        """EOFError → (False, None)，不崩溃。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=EOFError):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, None))

    def test_keyboard_interrupt_returns_false(self):
        """KeyboardInterrupt → (False, None)，不崩溃。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, None))

    def test_uppercase_y(self):
        """大写 Y 也视为 yes（第二次询问 EOF → 全量）。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["Y", EOFError]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (True, None))

    def test_whitespace_y(self):
        """y 带前后空格仍视为 yes。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["  y  ", ""]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (True, None))

    def test_module_keys_by_name(self):
        """第二次询问输入键名子集 → (False, [keys])，去重保序。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["y", "expert_review, global_macro expert_review"]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, ["expert_review", "global_macro"]))

    def test_module_keys_by_index(self):
        """第二次询问输入编号子集 → 映射为键名。"""
        from src.python.llm.force_scope import FORCEABLE_LLM_MODULES
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["y", "1,3"]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (False, [FORCEABLE_LLM_MODULES[0], FORCEABLE_LLM_MODULES[2]]))

    def test_unknown_token_falls_back_to_all(self):
        """含无法识别的 token → 警告并回退全量 (True, None)。"""
        from src.python.tui.handlers_report import _prompt_force_llm

        reporter = MagicMock()
        with patch("builtins.input", side_effect=["y", "nonsense"]):
            result = _prompt_force_llm(reporter)
        self.assertEqual(result, (True, None))
        reporter.warn.assert_called_once()


@pytest.mark.unit_core
class TestPromptHistory(unittest.TestCase):
    """_prompt_history 历史走势获取决定（读 history.fetch_mode 三态）。"""

    def _config(self, mode: str) -> dict:
        return {"history": {"fetch_mode": mode}}

    def test_auto_returns_true(self):
        """fetch_mode=auto → True（自动获取，不询问）。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("auto")),
            patch("src.python.config.is_enable_history", return_value=True),
        ):
            result = _prompt_history()
        self.assertTrue(result)

    def test_off_returns_false(self):
        """fetch_mode=off → False（不获取，不询问）。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("off")),
            patch("src.python.config.is_enable_history", return_value=True),
        ):
            result = _prompt_history()
        self.assertFalse(result)

    def test_enable_history_false_returns_false(self):
        """enable_history 关闭 → False（总闸优先）。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("auto")),
            patch("src.python.config.is_enable_history", return_value=False),
        ):
            result = _prompt_history()
        self.assertFalse(result)

    def test_prompt_yes_returns_true(self):
        """fetch_mode=prompt 且用户答 y → True。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("prompt")),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("builtins.input", return_value="y"),
        ):
            result = _prompt_history()
        self.assertTrue(result)

    def test_prompt_no_returns_false(self):
        """fetch_mode=prompt 且用户答 n → False。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("prompt")),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("builtins.input", return_value="n"),
        ):
            result = _prompt_history()
        self.assertFalse(result)

    def test_prompt_eof_returns_false(self):
        """fetch_mode=prompt 且 EOFError → False，不崩溃。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value=self._config("prompt")),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("builtins.input", side_effect=EOFError),
        ):
            result = _prompt_history()
        self.assertFalse(result)

    def test_missing_fetch_mode_defaults_auto(self):
        """fetch_mode 缺失时默认 auto → True。"""
        from src.python.tui.handlers_report import _prompt_history

        with (
            patch("src.python.tui.handlers_report.get_config_cache", return_value={}),
            patch("src.python.config.is_enable_history", return_value=True),
        ):
            result = _prompt_history()
        self.assertTrue(result)


@pytest.mark.unit_core
class TestPromptCostForecast(unittest.TestCase):
    """_prompt_cost_forecast：区间预估确认 + 日预算超限处置（预估失败不阻塞）。"""

    @staticmethod
    def _fc(**over):
        base = {
            "ok": True,
            "module_count": 3,
            "low": 0.1,
            "high": 0.9,
            "basis": "static",
            "symbol": "¥",
            "reason": None,
        }
        base.update(over)
        return base

    @staticmethod
    def _budget(**over):
        base = {"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False, "symbol": "¥"}
        base.update(over)
        return base

    def test_confirm_yes_proceeds(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch("src.python.tui.handlers_report.budget_status", return_value=self._budget()),
            patch("builtins.input", return_value="y"),
        ):
            assert _prompt_cost_forecast(False, None) == (True, False)

    def test_confirm_default_no_aborts_with_message(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch("src.python.tui.handlers_report.budget_status", return_value=self._budget()),
            patch("builtins.input", return_value=""),
        ):
            assert _prompt_cost_forecast(False, None) == (False, False)

    def test_forecast_unavailable_skips_prompt(self):
        """预估失败不阻塞生成：不询问、直接继续。"""
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch(
                "src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc(ok=False, reason="模型未知")
            ),
            patch("src.python.tui.handlers_report.budget_status", return_value=self._budget()),
            patch("builtins.input", side_effect=AssertionError("预估失败时不应询问")),
        ):
            assert _prompt_cost_forecast(False, None) == (True, False)

    def test_zero_modules_skips_prompt(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch(
                "src.python.tui.handlers_report.forecast_run_cost",
                return_value=self._fc(module_count=0, low=0.0, high=0.0),
            ),
            patch("src.python.tui.handlers_report.budget_status", return_value=self._budget()),
            patch("builtins.input", side_effect=AssertionError("无模块参与不应询问")),
        ):
            assert _prompt_cost_forecast(False, None) == (True, False)

    def test_budget_exceeded_yes_degrades_force(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch(
                "src.python.tui.handlers_report.budget_status",
                return_value=self._budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            ),
            patch("builtins.input", return_value="y"),
        ):
            assert _prompt_cost_forecast(True, None) == (True, True), "超限确认降级须回报清空强刷范围"

    def test_budget_exceeded_default_aborts(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch(
                "src.python.tui.handlers_report.budget_status",
                return_value=self._budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            ),
            patch("builtins.input", return_value=""),
        ):
            assert _prompt_cost_forecast(False, None) == (False, False)

    def test_budget_exceeded_eof_aborts(self):
        from src.python.tui.handlers_report import _prompt_cost_forecast

        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch(
                "src.python.tui.handlers_report.budget_status",
                return_value=self._budget(enabled=True, limit=1.0, spent=1.2, exceeded=True),
            ),
            patch("builtins.input", side_effect=EOFError),
        ):
            assert _prompt_cost_forecast(False, None) == (False, False)

    def test_summary_lines_printed_with_prefix(self):
        import contextlib
        import io

        from src.python.tui.handlers_report import _prompt_cost_forecast

        buf = io.StringIO()
        with (
            patch("src.python.tui.handlers_report.forecast_run_cost", return_value=self._fc()),
            patch("src.python.tui.handlers_report.budget_status", return_value=self._budget()),
            patch("builtins.input", return_value="y"),
            contextlib.redirect_stdout(buf),
        ):
            _prompt_cost_forecast(False, None)
        out = buf.getvalue()
        assert "[..]" in out and "费用预估" in out, "预估行须带上屏前缀"


@pytest.mark.unit_core
class TestCmdGenerateFullForecastWiring(unittest.TestCase):
    """_cmd_generate_full 与费用预估的接线：中止不进生成、降级清空强刷。"""

    def _run(self, forecast_result, force=(False, None)):
        from src.python.tui import handlers_report as hr

        with (
            patch.object(hr, "TuiProgressReporter") as reporter_cls,
            patch.object(hr, "_prompt_force_llm", return_value=force),
            patch.object(hr, "_prompt_cost_forecast", return_value=forecast_result) as fc,
            patch.object(hr, "_run_generate") as run_gen,
            patch.object(hr, "print_llm_session_usage") as usage,
        ):
            hr._cmd_generate_full()
            return fc, run_gen, usage, reporter_cls

    def test_abort_skips_generation(self):
        fc, run_gen, usage, _ = self._run((False, False))
        fc.assert_called_once()
        run_gen.assert_not_called()
        usage.assert_not_called()

    def test_degrade_clears_force_scope(self):
        _, run_gen, _, _ = self._run((True, True), force=(True, ["global_macro"]))
        run_gen.assert_called_once()
        _, kwargs = run_gen.call_args
        assert kwargs["force_llm"] is False, "降级走缓存须清空全量强刷"
        assert kwargs["force_llm_modules"] is None, "降级走缓存须清空模块级强刷"

    def test_normal_proceed_passes_force_through(self):
        _, run_gen, _, _ = self._run((True, False), force=(True, None))
        run_gen.assert_called_once()
        _, kwargs = run_gen.call_args
        assert kwargs["force_llm"] is True, "未降级时强刷范围原样透传"
