# -*- coding: utf-8 -*-
"""符号表与 ASCII 降级（`tui/symbols.py`）。

硬不变量：每条映射两侧显示宽度相同——ASCII 模式只换字符不换版面，否则窄档每行
宽度不变式与「≤ 列宽」用例会一起失效。
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest

from src.python.tui.symbols import (
    ASCII_MAP,
    AsciiStream,
    ascii_mode_requested,
    install_ascii_stream,
    translate,
)
from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestAsciiMap:
    """映射表不变量。"""

    @pytest.mark.parametrize(("symbol", "ascii_equivalent"), sorted(ASCII_MAP.items()))
    def test_width_is_preserved(self, symbol, ascii_equivalent):
        """每个装饰符号与其 ASCII 等价物显示宽度相同（否则版面会错位）。"""
        assert display_width(symbol) == display_width(ascii_equivalent), f"{symbol} → {ascii_equivalent}"

    def test_replacement_is_single_char(self):
        """替换后只有一个字符：多字符会推宽该行。"""
        assert all(len(ascii_equivalent) == 1 for ascii_equivalent in ASCII_MAP.values())


class TestTranslate:
    """替换只动装饰符号，不动正文。"""

    def test_decorations_replaced(self):
        assert translate("── 标题 ── ▸ ⚗") == "-- 标题 -- > *"

    def test_cjk_digits_and_punct_untouched(self):
        """中文、数字、ASCII 标点一律原样保留（降级不是翻译）。"""
        text = "12:30 提示（含空格）ab-c_d"
        assert translate(text) == text

    def test_empty_string(self):
        assert translate("") == ""


class TestModeDetection:
    def test_env_enables_mode(self):
        with patch.dict(os.environ, {"TUI_ASCII": "1"}):
            assert ascii_mode_requested() is True

    def test_unset_disables_mode(self):
        with patch.dict(os.environ, {}, clear=True):
            assert ascii_mode_requested() is False


class TestAsciiStream:
    """代理流：写出前替换，其余接口透传。"""

    def test_write_translates(self):
        sink = io.StringIO()
        stream = AsciiStream(sink)
        stream.write("▸ 选项 ──")
        assert sink.getvalue() == "> 选项 --"

    def test_isatty_passthrough(self):
        class _Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        assert AsciiStream(_Tty()).isatty() is True
        assert AsciiStream(io.StringIO()).isatty() is False


class TestInstall:
    def test_noop_when_not_requested(self):
        """未请求降级时返回原流且不包装（零行为变化）。"""
        sink = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            assert install_ascii_stream(sink) is sink

    def test_wraps_explicit_stream_when_requested(self):
        """请求降级时对显式传入的流返回包装，且不改 sys.stdout。"""
        import sys

        sink = io.StringIO()
        original = sys.stdout
        with patch.dict(os.environ, {"TUI_ASCII": "1"}):
            wrapped = install_ascii_stream(sink)
        assert isinstance(wrapped, AsciiStream)
        assert sys.stdout is original, "显式传流时不应改动全局 stdout"
        wrapped.write("● 正常")
        assert sink.getvalue() == "O 正常"

    def test_install_is_idempotent(self):
        """重复安装不叠加包装（嵌套代理会让映射跑两遍）。"""
        sink = io.StringIO()
        with patch.dict(os.environ, {"TUI_ASCII": "1"}):
            first = install_ascii_stream(sink)
            second = install_ascii_stream(first)
        assert first is second
