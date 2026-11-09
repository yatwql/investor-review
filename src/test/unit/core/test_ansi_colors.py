"""`core.ansi_colors` 着色判据单源测试。

锁三件事：
① `supports_color` / `codes_for` 的判据（`NO_COLOR`、TTY、按调用方的流判定）；
② 模块级常量与 `RAW_CODES` 同源（转义码字面量只在一处定义，降级时全空串）；
③ CLI 的 `_use_ansi_color` **委托**同一判据（不再自写 NO_COLOR/isatty），
   仅额外要求 stdout 是 UTF-8（cp936 控制台上色会输出乱码）。
"""

from __future__ import annotations

import sys

import pytest

from src.python.core import ansi_colors

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _Stream:
    """最小流桩：只提供 isatty。"""

    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class TestSupportsColor:
    def test_tty_stream_supports_color(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)

        assert ansi_colors.supports_color(_Stream(tty=True)) is True

    def test_non_tty_stream_drops_color(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)

        assert ansi_colors.supports_color(_Stream(tty=False)) is False

    def test_no_color_env_wins_over_tty(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")

        assert ansi_colors.supports_color(_Stream(tty=True)) is False

    def test_stream_argument_is_honoured_not_stdout(self, monkeypatch):
        """按传入流判定：stdout 有 TTY 但 stderr 被重定向时报错流应降级。"""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr(sys, "stdout", _Stream(tty=True))

        assert ansi_colors.supports_color(_Stream(tty=False)) is False


class TestCodesFor:
    def test_supported_stream_returns_raw_codes(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)

        assert ansi_colors.codes_for(_Stream(tty=True)) == ansi_colors.RAW_CODES

    def test_unsupported_stream_returns_empty_strings(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)

        assert set(ansi_colors.codes_for(_Stream(tty=False)).values()) == {""}

    def test_module_constants_are_raw_codes_or_empty(self):
        """模块级常量必须是 RAW_CODES 的同一份字面量（不是第二份手写值）。"""
        for name, raw in ansi_colors.RAW_CODES.items():
            assert getattr(ansi_colors, name) in ("", raw)


class TestCliDelegatesToSingleSource:
    def test_cli_uses_shared_predicate(self, monkeypatch):
        """CLI 的着色判定必须走 `supports_color`（否则 NO_COLOR/非 TTY 会二次实现、口径漂移）。"""
        from src.python.cli import _handlers

        monkeypatch.setattr(sys, "stdout", type("S", (), {"encoding": "UTF-8", "isatty": lambda self: True})())
        monkeypatch.setattr(ansi_colors, "supports_color", lambda stream=None: False)

        assert _handlers._use_ansi_color() is False

    def test_cli_still_requires_utf8_stdout(self, monkeypatch):
        """判据通过但 stdout 非 UTF-8 → CLI 仍降级（cp936 上色会乱码）。"""
        from src.python.cli import _handlers

        monkeypatch.setattr(sys, "stdout", type("S", (), {"encoding": "cp936", "isatty": lambda self: True})())
        monkeypatch.setattr(ansi_colors, "supports_color", lambda stream=None: True)

        assert _handlers._use_ansi_color() is False
