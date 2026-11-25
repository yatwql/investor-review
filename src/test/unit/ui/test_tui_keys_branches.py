"""按键读取底层分支（`tui/tui_keys`）：字节解码、拆包序列补全、Windows 行输入。

补齐主用例未触达的分支：
  - `_read_key_char`：OSError / EOF / 1~4 字节 UTF-8 / 非法首字节 / 续字节超时（半截字符）
  - `_take_esc_residue`：无残留、非序列续段、末字节超时（转半途前缀）、续读为空
  - `_swallow_esc_residue_byte`：无残留、非前缀、前缀后超时、逐字节吞到字母/`~`、EOF
  - `_get_key_windows`：msvcrt 缺 getch 降级、两次 KeyboardInterrupt、未知功能键
  - `_input_choice_windows`：回车/退格/Ctrl+C/Esc/方向键（空行与非空行）/控制字符
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from src.python.tui import tui_keys as tk

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture(autouse=True)
def _clean_parser_state():
    tk.reset_key_parser_state()
    yield
    tk.reset_key_parser_state()


class _ByteFeed:
    """按脚本喂字节的假 fd：`os.read` / `select.select` 全部走它。"""

    def __init__(self, monkeypatch, chunks: list[bytes], *, ready: bool = True) -> None:
        self._chunks = list(chunks)
        self.ready = ready
        monkeypatch.setattr(tk.os, "read", self._read)
        monkeypatch.setattr("select.select", self._select)

    def _read(self, fd: int, n: int) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def _select(self, rlist, _w, _x, _timeout):
        if self._chunks and self.ready:
            return ([rlist[0]], [], [])
        return ([], [], [])


class TestReadKeyChar:
    def test_oserror_returns_empty(self, monkeypatch):
        monkeypatch.setattr(tk.os, "read", lambda _fd, _n: (_ for _ in ()).throw(OSError("gone")))

        assert tk._read_key_char(0) == ""

    def test_eof_returns_empty(self, monkeypatch):
        _ByteFeed(monkeypatch, [b""])

        assert tk._read_key_char(0) == ""

    def test_ascii_byte(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"q"])

        assert tk._read_key_char(0) == "q"

    def test_two_byte_utf8(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"\xc3", b"\xa9"])

        assert tk._read_key_char(0) == "é"

    def test_three_byte_utf8(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"\xe4", b"\xb8", b"\xad"])

        assert tk._read_key_char(0) == "中"

    def test_four_byte_utf8(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"\xf0", b"\x9d", b"\x84", b"\x9e"])

        assert tk._read_key_char(0) == "\U0001d11e"

    def test_invalid_lead_byte_decodes_with_replacement(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"\x80"])

        assert tk._read_key_char(0) == "\ufffd"

    def test_continuation_timeout_returns_partial_char(self, monkeypatch):
        _ByteFeed(monkeypatch, [b"\xe4"], ready=False)

        assert tk._read_key_char(0) == "\ufffd"


class TestTakeEscResidue:
    def test_no_residue_returns_none(self):
        assert tk._take_esc_residue("[", 0) is None

    def test_non_sequence_prefix_clears_flag(self):
        tk._mark_esc_residue()

        assert tk._take_esc_residue("x", 0) is None
        assert tk._take_esc_residue("[", 0) is None, "残留标志只消费一次"

    def test_prefix_with_ready_bytes_maps_arrow(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([r[0]], [], []))
        monkeypatch.setattr(tk, "_read_key_char", lambda _fd: "B")

        assert tk._take_esc_residue("[", 0) == tk.KEY_DOWN

    def test_prefix_with_timeout_marks_half_sequence(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([], [], []))

        assert tk._take_esc_residue("[", 0) == tk.KEY_UNKNOWN
        assert tk._take_seq_completion("B") == tk.KEY_DOWN, "末字节迟到后必须走补全而非字母分派"

    def test_prefix_with_empty_completion_marks_half_sequence(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([r[0]], [], []))
        monkeypatch.setattr(tk, "_read_key_char", lambda _fd: "")

        assert tk._take_esc_residue("O", 0) == tk.KEY_UNKNOWN
        assert tk._take_seq_completion("A") == tk.KEY_UP


class TestSwallowEscResidueByte:
    def test_no_residue_returns_false(self):
        assert tk._swallow_esc_residue_byte(b"[", 0) is False

    def test_non_prefix_clears_flag_and_returns_false(self):
        tk._mark_esc_residue()

        assert tk._swallow_esc_residue_byte(b"a", 0) is False
        assert tk._swallow_esc_residue_byte(b"[", 0) is False, "标志只消费一次"

    def test_prefix_with_timeout_consumes_byte(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([], [], []))

        assert tk._swallow_esc_residue_byte(b"[", 0) is True

    def test_prefix_swallows_until_letter(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([r[0]], [], []))
        feed = _ByteFeed(monkeypatch, [b"1", b"2", b"A"])

        assert tk._swallow_esc_residue_byte(b"[", 0) is True
        assert feed._chunks == [], "序列必须吞到终止字母为止，不得泄漏为按键"

    def test_prefix_with_eof_consumes_byte(self, monkeypatch):
        tk._mark_esc_residue()
        monkeypatch.setattr("select.select", lambda r, w, x, t: ([r[0]], [], []))
        _ByteFeed(monkeypatch, [b""])

        assert tk._swallow_esc_residue_byte(b"O", 0) is True


def _fake_msvcrt(monkeypatch, getch_values: list[Any], *, raise_at: set[int] | None = None) -> None:
    """注入假 msvcrt 模块（Windows 分支在非 Windows 上亦可覆盖）。"""
    state = {"i": 0}
    fail = raise_at or set()

    def _getch() -> bytes:
        idx = state["i"]
        state["i"] += 1
        if idx in fail:
            raise KeyboardInterrupt
        return getch_values[idx]

    module = type(sys)("msvcrt")
    module.getch = _getch
    monkeypatch.setitem(sys.modules, "msvcrt", module)


class TestGetKeyWindowsBranches:
    def _call(self, monkeypatch, *, isatty: bool = True) -> str:
        monkeypatch.setattr(tk.sys.stdin, "isatty", lambda: isatty)
        monkeypatch.setattr(tk.os, "name", "nt")

        return tk._get_key_windows()

    def test_missing_getch_degrades_to_unknown(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "msvcrt", type(sys)("msvcrt"))

        assert self._call(monkeypatch) == tk.KEY_UNKNOWN

    def test_first_getch_interrupt_maps_to_ctrl_c(self, monkeypatch):
        _fake_msvcrt(monkeypatch, [b""], raise_at={0})

        assert self._call(monkeypatch) == tk.KEY_CTRL_C

    def test_arrow_prefix_second_getch_interrupt(self, monkeypatch):
        _fake_msvcrt(monkeypatch, [b"\xe0"], raise_at={1})

        assert self._call(monkeypatch) == tk.KEY_CTRL_C

    def test_unknown_function_key_after_prefix(self, monkeypatch):
        _fake_msvcrt(monkeypatch, [b"\x00", b"Q"])

        assert self._call(monkeypatch) == tk.KEY_UNKNOWN

    def test_decode_error_maps_to_unknown(self, monkeypatch):
        _fake_msvcrt(monkeypatch, [b"\xff"])

        assert self._call(monkeypatch) == tk.KEY_UNKNOWN


class TestInputChoiceWindows:
    def _module(self, monkeypatch, chars: list[str]):
        state = {"i": 0}

        def _getwch() -> str:
            value = chars[state["i"]]
            state["i"] += 1
            return value

        module = type(sys)("msvcrt")
        module.getwch = _getwch
        monkeypatch.setitem(sys.modules, "msvcrt", module)
        monkeypatch.setattr(tk.sys.stdin, "isatty", lambda: True)
        return module

    def test_enter_returns_stripped_line(self, monkeypatch):
        self._module(monkeypatch, [" ", "a", "b", " ", "\r"])

        assert tk._input_choice_windows("> ") == "ab"

    def test_ctrl_c_raises_interrupt(self, monkeypatch):
        self._module(monkeypatch, ["\x03"])

        with pytest.raises(KeyboardInterrupt):
            tk._input_choice_windows("> ")

    def test_esc_cancels(self, monkeypatch):
        self._module(monkeypatch, ["\x1b"])

        assert tk._input_choice_windows("> ") is None

    def test_backspace_removes_last_char(self, monkeypatch):
        self._module(monkeypatch, ["a", "b", "\x7f", "\x08", "\r"])

        assert tk._input_choice_windows("> ") == ""

    def test_backspace_on_empty_buffer_is_noop(self, monkeypatch):
        self._module(monkeypatch, ["\x7f", "a", "\r"])

        assert tk._input_choice_windows("> ") == "a"

    def test_control_characters_ignored(self, monkeypatch):
        self._module(monkeypatch, ["\x01", "a", "\r"])

        assert tk._input_choice_windows("> ") == "a"

    def test_arrows_enabled_on_empty_line_return_nav_keys(self, monkeypatch):
        self._module(monkeypatch, ["\x00", "H"])

        assert tk._input_choice_windows("> ", arrows=True) == tk.KEY_UP

    def test_arrow_down_on_empty_line(self, monkeypatch):
        self._module(monkeypatch, ["\xe0", "P"])

        assert tk._input_choice_windows("> ", arrows=True) == tk.KEY_DOWN

    def test_arrows_swallowed_when_line_has_content(self, monkeypatch):
        self._module(monkeypatch, ["a", "\x00", "H", "\r"])

        assert tk._input_choice_windows("> ", arrows=True) == "a"

    def test_arrows_disabled_swallows_prefix(self, monkeypatch):
        self._module(monkeypatch, ["\x00", "H", "b", "\r"])

        assert tk._input_choice_windows("> ") == "b"

    def test_missing_getwch_falls_back_to_input(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "msvcrt", type(sys)("msvcrt"))
        monkeypatch.setattr(tk.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _p="": "  x  ")

        assert tk._input_choice_windows("> ") == "x"
