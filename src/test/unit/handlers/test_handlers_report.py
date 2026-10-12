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
