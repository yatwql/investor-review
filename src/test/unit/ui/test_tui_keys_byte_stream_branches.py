"""终端读键底层（`tui/tui_keys`）：平台分发、字节续读异常、raw 行编辑的边角通道。

锁住的契约：
  - 非 TTY（管道 / 重定向 / 测试）读键立即返回 `KEY_UNKNOWN`，**绝不阻塞**等键；
  - 平台能力缺失（`msvcrt` / `termios` / `tty` 不可用、`fileno()` 不可用）统一降级，
    不让程序在导入/读键处崩掉；
  - 多字节序列只读半截（首字节到、续字节超时或读到 EOF）时给 `KEY_UNKNOWN` 或记下
    半途前缀，绝不把半截序列当独立字母派发（否则 `ESC [ A` 会被当成按了 `A`）。
"""

from __future__ import annotations

import sys
import types

import pytest

from src.python.tui import tui_keys as tk

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture(autouse=True)
def _reset_seq_state(monkeypatch):
    """残留/半途序列标志隔离：不跨用例泄漏（否则前一条留下的半途前缀会改写后一条的判定）。"""
    monkeypatch.setattr(tk, "_esc_residue_pending", False)
    monkeypatch.setattr(tk, "_seq_prefix_pending", "")


@pytest.fixture
def raw_stdin(monkeypatch):
    """把一个「真终端」替身上到 `sys.stdin`，并可注入逐字节读序列。"""

    class _Stdin:
        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            return 99

    monkeypatch.setattr(tk.sys, "stdin", _Stdin())
    monkeypatch.setattr("termios.tcgetattr", lambda _fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda *_args: None)
    monkeypatch.setattr("tty.setraw", lambda _fd: None)
    return _Stdin


def _reads(monkeypatch, chunks: list[bytes]) -> None:
    seq = iter(chunks)
    monkeypatch.setattr("src.python.tui.tui_keys.os.read", lambda _fd, _n: next(seq))


def _select_ready(monkeypatch, ready: list[bool]) -> None:
    seq = iter(ready)
    monkeypatch.setattr("select.select", lambda *_args: ([object()] if next(seq) else [], [], []))


class TestReadKeyCharByteStream:
    def test_oserror_mid_sequence_returns_partial(self, monkeypatch):
        """续字节读抛 OSError（终端断开）→ 只返回已读部分，不向上抛异常。"""
        calls: list[bytes] = [b"\xe4", OSError("tty gone")]

        def _read(_fd, _n):
            item = calls.pop(0)
            if isinstance(item, OSError):
                raise item
            return item

        monkeypatch.setattr("src.python.tui.tui_keys.os.read", _read)
        _select_ready(monkeypatch, [True])

        assert tk._read_key_char(99) == "\ufffd", "半截 UTF-8 按替换符解码（不抛异常）"


class TestEscResidueScan:
    def test_scan_stops_when_followup_times_out(self, monkeypatch):
        """续段扫描遇到非终止字节且下一字节超时 → 停止扫描并声明「已消费」。"""
        monkeypatch.setattr(tk, "_esc_residue_pending", True)
        _select_ready(monkeypatch, [True, False])
        _reads(monkeypatch, [b"1"])

        assert tk._swallow_esc_residue_byte(b"[", 99) is True
        assert tk._esc_residue_pending is False, "残留标志须在本字节上清掉（只吸收一次）"

    def test_non_prefix_byte_is_not_consumed(self, monkeypatch):
        """孤 Esc 之后不是 `[`/`O` 的字节不算续段 → 交回正常行编辑。"""
        monkeypatch.setattr(tk, "_esc_residue_pending", True)

        assert tk._swallow_esc_residue_byte(b"A", 99) is False
        assert tk._esc_residue_pending is False

    def test_no_pending_residue_never_consumes(self, monkeypatch):
        monkeypatch.setattr(tk, "_esc_residue_pending", False)

        assert tk._swallow_esc_residue_byte(b"[", 99) is False
        assert tk._take_esc_residue("[", 99) is None


class TestWindowsKeyMapping:
    @staticmethod
    def _windows(monkeypatch, getch_chars: list[bytes] | None, *, tty: bool = True):
        class _Stdin:
            def isatty(self) -> bool:
                return tty

        fake = types.ModuleType("msvcrt")
        if getch_chars is not None:
            seq = iter(getch_chars)
            fake.getch = lambda: next(seq)
        monkeypatch.setattr(tk.sys, "stdin", _Stdin())
        monkeypatch.setitem(sys.modules, "msvcrt", fake)
        return tk._get_key_windows()

    def test_non_tty_returns_unknown_without_blocking(self, monkeypatch):
        """非交互 stdin 不得调 msvcrt.getch（会永久挂起）——直接给 KEY_UNKNOWN。"""
        assert self._windows(monkeypatch, [b"\x03"], tty=False) == tk.KEY_UNKNOWN

    @pytest.mark.parametrize(
        ("ch", "expected"),
        [(b"\x03", tk.KEY_CTRL_C), (b"\r", tk.KEY_ENTER), (b"\x1b", tk.KEY_ESC)],
    )
    def test_special_keys_mapped(self, monkeypatch, ch, expected):
        assert self._windows(monkeypatch, [ch]) == expected

    def test_unicode_decode_error_returns_unknown(self, monkeypatch):
        """非法字节（非法 UTF-8 首字节）不抛异常，按未识别键处理。"""
        assert self._windows(monkeypatch, [b"\xff"]) == tk.KEY_UNKNOWN


class TestLinuxKeyDegrades:
    def test_non_tty_returns_unknown(self, monkeypatch):
        class _Stdin:
            def isatty(self) -> bool:
                return False

        monkeypatch.setattr(tk.sys, "stdin", _Stdin())

        assert tk._get_key_linux() == tk.KEY_UNKNOWN

    def test_missing_termios_returns_unknown(self, monkeypatch):
        """POSIX 版缺 termios/tty（非常见平台）→ KEY_UNKNOWN，不抛 ImportError。"""

        class _Stdin:
            def isatty(self) -> bool:
                return True

        monkeypatch.setattr(tk.sys, "stdin", _Stdin())
        monkeypatch.setitem(sys.modules, "termios", None)

        assert tk._get_key_linux() == tk.KEY_UNKNOWN

    def test_unusable_fileno_returns_unknown(self, monkeypatch):
        """`fileno()` 抛 ValueError（非真终端）→ KEY_UNKNOWN（与 isatty 不过同口径）。"""

        class _Stdin:
            def isatty(self) -> bool:
                return True

            def fileno(self) -> int:
                raise ValueError("no fd")

        monkeypatch.setattr(tk.sys, "stdin", _Stdin())

        assert tk._get_key_linux() == tk.KEY_UNKNOWN

    def test_esc_prefix_without_followup_byte(self, monkeypatch, raw_stdin):
        """ESC 之后 `[` 读不到（EOF/断开）→ KEY_UNKNOWN，绝不当作 `[` 派发。"""
        _select_ready(monkeypatch, [True, True])
        _reads(monkeypatch, [b"\x1b", b""])

        assert tk._get_key_linux() == tk.KEY_UNKNOWN

    def test_esc_sequence_without_final_byte(self, monkeypatch, raw_stdin):
        """`ESC [` 齐到、末字节缺 → KEY_UNKNOWN 并记下半途前缀（迟到字节按补全处理）。"""
        _select_ready(monkeypatch, [True, True, True])
        _reads(monkeypatch, [b"\x1b", b"[", b""])

        assert tk._get_key_linux() == tk.KEY_UNKNOWN
        assert tk._seq_prefix_pending == "\x1b["


class TestInputChoiceDispatch:
    def test_windows_dispatch(self, monkeypatch):
        """`os.name == "nt"` → 走 Windows 行编辑分支。"""
        seen: list[str] = []
        monkeypatch.setattr(tk.os, "name", "nt")
        monkeypatch.setattr(tk, "_input_choice_windows", lambda prompt, arrows=False: seen.append(prompt) or "9")

        assert tk.input_choice("  > ", arrows=True) == "9"
        assert seen == ["  > "]

    def test_linux_without_termios_falls_back_to_input(self, monkeypatch):
        """POSIX 版缺 termios/tty → 回退内置 input（strip 后返回）。"""

        class _Stdin:
            def isatty(self) -> bool:
                return True

        monkeypatch.setattr(tk.sys, "stdin", _Stdin())
        monkeypatch.setitem(sys.modules, "termios", None)
        monkeypatch.setattr("builtins.input", lambda _prompt: "  3  ")

        assert tk._input_choice_linux("  > ") == "3"

    def test_windows_without_tty_falls_back_to_input(self, monkeypatch):
        """Windows 分支在非 TTY 下同样回退 input（测试/管道驱动方式不变）。"""

        class _Stdin:
            def isatty(self) -> bool:
                return False

        monkeypatch.setattr(tk.sys, "stdin", _Stdin())
        monkeypatch.setattr("builtins.input", lambda _prompt: "  7  ")

        assert tk._input_choice_windows("  > ") == "7"


class TestLinuxLineEditing:
    def test_eof_returns_none(self, monkeypatch, raw_stdin):
        """读到 EOF（stdin 关掉）→ 换行收尾并返回 None（等同取消）。"""
        _reads(monkeypatch, [b""])

        assert tk._input_choice_linux("  > ") is None

    def test_backspace_strips_multibyte_char(self, monkeypatch, raw_stdin):
        """退格按 UTF-8 字符回剥：多字节字符的续字节一并剥掉，不留残字。"""
        _reads(monkeypatch, [b"\xe4", b"\xb8", b"\x7f", b"\r"])

        assert tk._input_choice_linux("  > ") == ""

    def test_control_byte_is_ignored(self, monkeypatch, raw_stdin):
        """非回车/退格/转义的其它控制字节（如 Ctrl+A）被丢弃，不进输入行。"""
        _reads(monkeypatch, [b"\x01", b"A", b"\r"])

        assert tk._input_choice_linux("  > ") == "A"

    def test_escape_sequence_of_unknown_length_is_swallowed(self, monkeypatch, raw_stdin):
        """转义序列中间字节（数字参数）继续吞，直到字母/`~` 终止 —— 整段不进输入行。"""
        _select_ready(monkeypatch, [True])
        _reads(monkeypatch, [b"\x1b", b"[", b"1", b"A", b"ok", b"\r"])

        assert tk._input_choice_linux("  > ") == "ok"
