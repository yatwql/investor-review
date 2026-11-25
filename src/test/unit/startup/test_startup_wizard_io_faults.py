"""首次运行引导的 IO 与终端探测容错测试。

覆盖契约（`startup_wizard.py`）：
  - 首次运行标记读写失败时按「首次运行」处理，标记写入失败只记调试日志
  - 终端探测（`sys.stdin.isatty`）异常时判为非交互，避免流程阻塞
  - 交互询问遇 EOF/中断时按「不输入」处理
  - Key 输入空回车走「跳过」、遇 EOF 走「已取消」两条退出路径
"""

from __future__ import annotations

import logging
from unittest import mock

import pytest

from src.python import startup_wizard

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


# ── 首次运行标记 ────────────────────────────────────────


class TestFirstRunFlagFaults:
    def test_flag_read_failure_counts_as_first_run(self, monkeypatch):
        """读取标记失败时按首次运行处理（引导多显示一次好过不显示）。"""
        monkeypatch.setattr(startup_wizard, "get_local_flag", mock.Mock(side_effect=RuntimeError("state broken")))

        assert startup_wizard.is_first_run() is True

    def test_flag_write_failure_is_non_fatal(self, monkeypatch, caplog):
        """标记写入失败只记调试日志，不向调用方抛异常。"""
        monkeypatch.setattr(startup_wizard, "get_local_flag", lambda key: False)
        monkeypatch.setattr(startup_wizard, "set_local_flag", mock.Mock(side_effect=RuntimeError("ro fs")))

        with caplog.at_level(logging.DEBUG, logger=startup_wizard.logger.name):
            startup_wizard.mark_wizard_shown()

        assert any("标记引导失败" in record.getMessage() for record in caplog.records)


# ── 终端探测 ────────────────────────────────────────────


class TestNonInteractiveDetection:
    def test_isatty_failure_is_treated_as_non_interactive(self, monkeypatch):
        """终端探测异常时判为非交互（宁可少引导，不可阻塞流程）。"""
        broken_stdin = mock.Mock()
        broken_stdin.isatty = mock.Mock(side_effect=OSError("no tty"))
        monkeypatch.setattr(startup_wizard.sys, "stdin", broken_stdin)

        assert startup_wizard._is_non_interactive() is True


# ── 交互输入退出路径 ────────────────────────────────────


class TestPromptEnterKey:
    def test_eof_means_decline(self, monkeypatch):
        """询问遇 EOF 时按「不现在配置」处理。"""
        monkeypatch.setattr("builtins.input", mock.Mock(side_effect=EOFError))

        assert startup_wizard._prompt_enter_key() is False

    def test_keyboard_interrupt_means_decline(self, monkeypatch):
        """询问遇中断时按「不现在配置」处理。"""
        monkeypatch.setattr("builtins.input", mock.Mock(side_effect=KeyboardInterrupt))

        assert startup_wizard._prompt_enter_key() is False


class TestHandleKeyInput:
    def test_empty_input_skips_without_writing(self, monkeypatch, capsys):
        """空回车跳过输入，不写凭据文件。"""
        monkeypatch.setattr("builtins.input", lambda prompt="": "   ")
        writer = mock.Mock()
        monkeypatch.setattr(startup_wizard, "_write_llm_credentials", writer)

        startup_wizard._handle_key_input()

        writer.assert_not_called()
        assert "已跳过 Key 输入" in capsys.readouterr().out

    def test_eof_prints_cancel_and_writes_nothing(self, monkeypatch, capsys):
        """读 Key 遇 EOF 时提示已取消，且不写凭据文件。"""
        monkeypatch.setattr("builtins.input", mock.Mock(side_effect=EOFError))
        writer = mock.Mock()
        monkeypatch.setattr(startup_wizard, "_write_llm_credentials", writer)

        startup_wizard._handle_key_input()

        writer.assert_not_called()
        assert "已取消 Key 输入" in capsys.readouterr().out
