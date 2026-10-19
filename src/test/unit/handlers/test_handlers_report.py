"""TUI 报告生成命令处理器单元测试。

测试可独立辅助函数。

运行：
  pytest src/test/unit/handlers/test_handlers_report.py -v
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


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


def _budget(**over):
    base = {"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False, "symbol": "¥"}
    base.update(over)
    return base


@pytest.mark.unit_core
class TestSelectForceModules(unittest.TestCase):
    """_select_force_modules：合并单屏按 f 后的模块级强刷选择。"""

    def test_module_subset_by_name(self):
        """输入键名子集 → (False, [keys])，去重保序。"""
        from src.python.tui.handlers_report import _select_force_modules

        reporter = MagicMock()
        with patch("builtins.input", return_value="expert_review, global_macro expert_review"):
            result = _select_force_modules(reporter)
        self.assertEqual(result, (False, ["expert_review", "global_macro"]))

    def test_module_subset_by_index(self):
        """输入编号子集 → 映射为键名。"""
        from src.python.llm.force_scope import FORCEABLE_LLM_MODULES
        from src.python.tui.handlers_report import _select_force_modules

        reporter = MagicMock()
        with patch("builtins.input", return_value="1,3"):
            result = _select_force_modules(reporter)
        self.assertEqual(result, (False, [FORCEABLE_LLM_MODULES[0], FORCEABLE_LLM_MODULES[2]]))

    def test_empty_returns_full_force(self):
        """空回车 → 全量强制 (True, None)。"""
        from src.python.tui.handlers_report import _select_force_modules

        reporter = MagicMock()
        with patch("builtins.input", return_value=""):
            result = _select_force_modules(reporter)
        self.assertEqual(result, (True, None))

    def test_unknown_token_falls_back_to_all(self):
        """含无法识别 token → 警告并回退全量 (True, None)。"""
        from src.python.tui.handlers_report import _select_force_modules

        reporter = MagicMock()
        with patch("builtins.input", return_value="nonsense"):
            result = _select_force_modules(reporter)
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
class TestPromptGenerateConfirm(unittest.TestCase):
    """_prompt_generate_confirm：合并单屏一次确认 + 日预算安全网。"""

    def _config(self, mode: str = "auto") -> dict:
        return {"history": {"fetch_mode": mode}}

    def _call(self, resp, config=None, *, budget=None, force_modules=(False, None)):
        from src.python.tui import handlers_report as hr

        reporter = MagicMock()
        with (
            patch.object(hr, "forecast_run_cost", return_value=_fc()),
            patch.object(hr, "budget_status", return_value=budget or _budget()),
            patch.object(hr, "input_choice", return_value=resp),
            patch.object(hr, "_select_force_modules", return_value=force_modules),
            patch("src.python.config.is_enable_history", return_value=True),
        ):
            return hr._prompt_generate_confirm(reporter, config or self._config())

    def test_enter_defaults_no_force(self):
        """回车=默认生成（走缓存、不强刷）；auto 模式历史默认 True。"""
        self.assertEqual(self._call(""), (False, None, True))

    def test_q_aborts(self):
        """输入 q → 中止（None）。"""
        self.assertIsNone(self._call("q"))

    def test_f_triggers_module_selection(self):
        """输入 f → 触发模块选择，透传其返回的强刷范围。"""
        self.assertEqual(self._call("f", force_modules=(True, None)), (True, None, True))

    def test_prompt_mode_enter_no_history(self):
        """fetch_mode=prompt 且回车（未按 h）→ 历史 False。"""
        self.assertEqual(self._call("", config=self._config("prompt"))[2], False)

    def test_prompt_mode_h_opts_history(self):
        """fetch_mode=prompt 且按 h → 历史 True。"""
        self.assertEqual(self._call("h", config=self._config("prompt"))[2], True)

    def test_off_mode_history_false(self):
        """fetch_mode=off → 历史 False（h 无效）。"""
        self.assertEqual(self._call("h", config=self._config("off"))[2], False)

    def test_budget_exceeded_yes_degrades_no_force(self):
        """预算超限 + y → 用已有结果继续（不重新生成）；auto 模式历史仍自动获取，不输出历史提示。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._call("y", budget=_budget(enabled=True, limit=1.0, spent=1.2, exceeded=True))
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], None)
        self.assertEqual(result[2], True)
        self.assertNotIn("不获取历史走势", buf.getvalue())

    def test_budget_exceeded_prompt_mode_history_not_asked(self):
        """安全网降级不追加历史询问：prompt 模式历史=不获取，并输出提示行告知（告知后覆盖语义锁定）。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._call(
                "y", config=self._config("prompt"), budget=_budget(enabled=True, limit=1.0, spent=1.2, exceeded=True)
            )
        self.assertEqual(result[0], False)
        self.assertEqual(result[2], False)
        self.assertIn("本次用已有结果，不获取历史走势", buf.getvalue())

    def test_budget_exceeded_off_mode_no_history_notice(self):
        """off 模式无历史概念 → 不输出历史提示（提示仅 prompt 模式）。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self._call(
                "y", config=self._config("off"), budget=_budget(enabled=True, limit=1.0, spent=1.2, exceeded=True)
            )
        self.assertEqual(result[2], False)
        self.assertNotIn("不获取历史走势", buf.getvalue())

    def test_substring_word_not_mistrigger(self):
        """词级精确匹配：'of' 不误触强刷（默认生成）、'faq' 不误中止（非 None）。"""
        r_of = self._call("of")
        self.assertIsNotNone(r_of)
        self.assertEqual(r_of[0], False, "子串含 f 不应触发强刷")
        r_faq = self._call("faq")
        self.assertIsNotNone(r_faq, "子串含 q 不应中止")
        self.assertEqual(r_faq[0], False)

    def test_combo_space_triggers_both(self):
        """'f h' 空格分隔组合：强刷与历史同时生效。"""
        result = self._call("f h", config=self._config("prompt"), force_modules=(True, None))
        self.assertEqual(result, (True, None, True))

    def test_budget_exceeded_default_aborts(self):
        """预算超限 + 默认（非 y）→ 中止（None）。"""
        self.assertIsNone(self._call("", budget=_budget(enabled=True, limit=1.0, spent=1.2, exceeded=True)))

    def test_question_line_explains_force_cost_tradeoff(self):
        """问句必须讲清重新生成的代价差异：默认用已有结果免费 / f 重调模型产生费用。

        守护点：仅给键位图例（回车 / f / q）而无代价说明时，用户须记住暗语并自行推断
        两者差别——问句描述丢失即视为回归。
        """
        from src.python.tui import handlers_report as hr

        reporter = MagicMock()
        buf = io.StringIO()
        at_prompt: list[str] = []

        def _capture(prompt: str) -> str:
            at_prompt.append(buf.getvalue())  # 按下提示的瞬间，问句是否已上屏
            return ""

        with (
            patch.object(hr, "forecast_run_cost", return_value=_fc()),
            patch.object(hr, "budget_status", return_value=_budget()),
            patch.object(hr, "input_choice", side_effect=_capture) as mock_choice,
            patch.object(hr, "_select_force_modules"),
            patch("src.python.config.is_enable_history", return_value=True),
            contextlib.redirect_stdout(buf),
        ):
            hr._prompt_generate_confirm(reporter, self._config())
        out = buf.getvalue()
        self.assertIn("是否重新生成", out)
        self.assertIn("会产生费用", out)
        self.assertIn("免费", out)
        # 问句必须在按键行之前上屏（先讲为什么，再让人按键作答）
        self.assertIn("是否重新生成", at_prompt[0])
        prompt_text = mock_choice.call_args.args[0]
        self.assertIn("用已有结果生成", prompt_text)
        self.assertIn("可选模块", prompt_text)

    def test_summary_lines_printed_with_prefix(self):
        """费用预估行带上屏前缀 [..]。"""
        from src.python.tui import handlers_report as hr

        reporter = MagicMock()
        buf = io.StringIO()
        with (
            patch.object(hr, "forecast_run_cost", return_value=_fc()),
            patch.object(hr, "budget_status", return_value=_budget()),
            patch.object(hr, "input_choice", return_value=""),
            patch.object(hr, "_select_force_modules"),
            patch("src.python.config.is_enable_history", return_value=True),
            contextlib.redirect_stdout(buf),
        ):
            hr._prompt_generate_confirm(reporter, self._config())
        out = buf.getvalue()
        self.assertIn("[..]", out)


@pytest.mark.unit_core
class TestCmdGenerateFullForecastWiring(unittest.TestCase):
    """_cmd_generate_full 与合并单屏确认的接线：中止不进生成、继续则透传。"""

    def _run(self, confirm_result):
        from src.python.tui import handlers_report as hr

        with (
            patch.object(hr, "TuiProgressReporter"),
            patch.object(hr, "_prompt_generate_confirm", return_value=confirm_result) as confirm,
            patch.object(hr, "get_config_cache", return_value={}),
            patch.object(hr, "_run_generate") as run_gen,
            patch.object(hr, "print_llm_session_usage") as usage,
        ):
            hr._cmd_generate_full()
            return confirm, run_gen, usage

    def test_abort_skips_generation(self):
        confirm, run_gen, usage = self._run(None)
        confirm.assert_called_once()
        run_gen.assert_not_called()
        usage.assert_not_called()

    def test_proceed_passes_through(self):
        _, run_gen, _ = self._run((True, ["global_macro"], True))
        run_gen.assert_called_once()
        _, kwargs = run_gen.call_args
        self.assertIs(kwargs["force_llm"], True)
        self.assertEqual(kwargs["force_llm_modules"], ["global_macro"])
        self.assertIs(kwargs["fetch_history"], True)


@pytest.mark.unit_core
class TestPromptEscCancel(unittest.TestCase):
    """提示处 Esc 统一取消：合并单屏 / 模块选择 / 历史 防回退。"""

    def test_history_ask_esc_cancels(self):
        """历史走势 y/N 处按 Esc → 取消生成（_prompt_history 仍服务直连路径）。"""
        from src.python.tui.handlers_report import PromptCancelledError, _prompt_history

        with (
            patch(
                "src.python.tui.handlers_report.get_config_cache",
                return_value={"history": {"fetch_mode": "prompt"}},
            ),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.tui.handlers_report.input_choice", return_value=None),
            pytest.raises(PromptCancelledError),
        ):
            _prompt_history()

    def test_force_module_subset_esc_cancels(self):
        """模块子集录入处按 Esc → 取消流程（而非空串=全部模块）。"""
        from src.python.tui.handlers_report import PromptCancelledError, _select_force_modules

        with (
            patch("src.python.tui.handlers_report.input_choice", return_value=None),
            pytest.raises(PromptCancelledError),
        ):
            _select_force_modules(MagicMock())

    def test_confirm_esc_aborts_with_message(self):
        """合并单屏处按 Esc → 中止并给出取消反馈。"""
        from src.python.tui import handlers_report as hr

        reporter = MagicMock()
        buf = io.StringIO()
        with (
            patch.object(hr, "forecast_run_cost", return_value=_fc()),
            patch.object(hr, "budget_status", return_value=_budget()),
            patch.object(hr, "input_choice", return_value=None),
            patch.object(hr, "_select_force_modules"),
            patch("src.python.config.is_enable_history", return_value=True),
            contextlib.redirect_stdout(buf),
        ):
            result = hr._prompt_generate_confirm(reporter, {"history": {"fetch_mode": "auto"}})
        self.assertIsNone(result)
        self.assertIn("已取消本次生成", buf.getvalue())

    def test_budget_exceeded_esc_aborts(self):
        """日预算超限处置处按 Esc → 中止生成。"""
        from src.python.tui import handlers_report as hr

        reporter = MagicMock()
        buf = io.StringIO()
        with (
            patch.object(hr, "forecast_run_cost", return_value=_fc()),
            patch.object(hr, "budget_status", return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True)),
            patch.object(hr, "input_choice", return_value=None),
            patch.object(hr, "_select_force_modules"),
            patch("src.python.config.is_enable_history", return_value=True),
            contextlib.redirect_stdout(buf),
        ):
            result = hr._prompt_generate_confirm(reporter, {"history": {"fetch_mode": "auto"}})
        self.assertIsNone(result)
        self.assertIn("已取消本次生成", buf.getvalue())
