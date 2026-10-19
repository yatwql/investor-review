"""TUI [M] LLM 多链线路优先级面板（tui/handlers_config._cmd_config_llm_providers）测试。

覆盖：交换编号 → 经共享编辑层 reorder 写盘 / Esc 即时返回不写 / 非法输入重提示 /
单线路直接返回。面板展示顺序 = priority 升序，与 Web 配置面同源。
"""

from __future__ import annotations

import pytest

from unittest.mock import patch

from src.python.tui.handlers_config import _cmd_config_llm_providers

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


_PROVIDERS = {
    "strategy": "priority",
    "providers": [
        {"name": "main", "provider": "claude", "priority": 10},
        {"name": "aux", "provider": "openai", "priority": 20},
        {"name": "last", "provider": "gemini", "priority": 30},
    ],
}


class TestLlmProvidersPanel:
    """[M] 面板：交换写盘与返回路径。"""

    def test_swap_writes_reordered_names(self, capsys) -> None:
        """输入「2 1」→ apply_config_edit 收到逆序 order，输出 [OK]。"""
        with (
            patch("src.python.config.get_llm_providers", return_value=_PROVIDERS),
            patch("src.python.tui.handlers_config.input_choice", side_effect=["2 1", "0"]),
            patch("src.python.tui.handlers_config._apply_edit", return_value=True) as edited,
        ):
            _cmd_config_llm_providers()
        edited.assert_called_once_with(
            {"key": "llm_providers.priority", "action": "reorder", "order": ["aux", "main", "last"]}
        )
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "aux 与 main" in out  # 交换双方点名（2=aux 与 1=main）

    def test_esc_returns_without_write(self, capsys) -> None:
        """Esc（input_choice 返回 None）→ 即时返回，零写盘。"""
        with (
            patch("src.python.config.get_llm_providers", return_value=_PROVIDERS),
            patch("src.python.tui.handlers_config.input_choice", return_value=None),
            patch("src.python.tui.handlers_config._apply_edit") as edited,
        ):
            _cmd_config_llm_providers()
        edited.assert_not_called()
        assert "LLM 多链线路优先级" in capsys.readouterr().out

    def test_invalid_input_reprompts_then_exits(self, capsys) -> None:
        """越界编号 → [!] 重提示，零写盘；随后 0 返回。"""
        with (
            patch("src.python.config.get_llm_providers", return_value=_PROVIDERS),
            patch("src.python.tui.handlers_config.input_choice", side_effect=["9 9", "0"]),
            patch("src.python.tui.handlers_config._apply_edit") as edited,
        ):
            _cmd_config_llm_providers()
        edited.assert_not_called()
        out = capsys.readouterr().out
        assert "[!]" in out
        assert "输入两个不同的编号" in out

    def test_single_provider_returns_immediately(self, capsys) -> None:
        """仅一条线路：提示无需调整并返回，不进入输入循环。"""
        single = {"strategy": "priority", "providers": [_PROVIDERS["providers"][0]]}
        with (
            patch("src.python.config.get_llm_providers", return_value=single),
            patch("src.python.tui.handlers_config.input_choice") as prompted,
        ):
            _cmd_config_llm_providers()
        prompted.assert_not_called()
        assert "无需调整" in capsys.readouterr().out

    def test_non_priority_strategy_shows_effect_hint(self, capsys) -> None:
        """weighted/cost_first 策略：显示「实际链序由权重/成本决定」提示。"""
        weighted = {**_PROVIDERS, "strategy": "weighted"}
        with (
            patch("src.python.config.get_llm_providers", return_value=weighted),
            patch("src.python.tui.handlers_config.input_choice", return_value=None),
        ):
            _cmd_config_llm_providers()
        assert "实际链序由权重/成本决定" in capsys.readouterr().out
