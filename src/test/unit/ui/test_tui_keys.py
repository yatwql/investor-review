"""TUI 键盘输入函数单元测试。

测试目标：
  - get_key()      — Windows/Linux 分发逻辑
  - _get_key_windows() — Windows 分支（msvcrt）
  - _get_key_linux()    — Linux 分支（tty + termios + select）
  - 键名常量

运行：
  pytest src/test/unit/ui/test_tui_keys.py -v
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from src.python.tui.tui_keys import (
    KEY_CTRL_C,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_UNKNOWN,
    KEY_UP,
    get_key,
    input_choice,
    _get_key_linux,
    _get_key_windows,
    _input_choice_linux,
    _input_choice_windows,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestConstants(unittest.TestCase):
    """键名常量测试。"""

    def test_key_up(self) -> None:
        self.assertEqual(KEY_UP, "KEY_UP")

    def test_key_down(self) -> None:
        self.assertEqual(KEY_DOWN, "KEY_DOWN")

    def test_key_enter(self) -> None:
        self.assertEqual(KEY_ENTER, "KEY_ENTER")

    def test_key_ctrl_c(self) -> None:
        self.assertEqual(KEY_CTRL_C, "KEY_CTRL_C")

    def test_key_esc(self) -> None:
        self.assertEqual(KEY_ESC, "KEY_ESC")

    def test_key_unknown(self) -> None:
        self.assertEqual(KEY_UNKNOWN, "KEY_UNKNOWN")


class TestGetKeyDispatch(unittest.TestCase):
    """get_key() 分发逻辑测试。

    通过 mock _get_key_windows / _get_key_linux 验证 os.name 的分支选择，
    不依赖实际平台模块，可跨平台运行。
    """

    @patch("src.python.tui.tui_keys._get_key_windows")
    @patch("src.python.tui.tui_keys._get_key_linux")
    def test_windows_dispatch(
        self,
        mock_linux: MagicMock,
        mock_windows: MagicMock,
    ) -> None:
        """os.name == 'nt' 时走 Windows 分支。"""
        with patch("src.python.tui.tui_keys.os.name", "nt"):
            get_key()
        mock_windows.assert_called_once()
        mock_linux.assert_not_called()

    @patch("src.python.tui.tui_keys._get_key_windows")
    @patch("src.python.tui.tui_keys._get_key_linux")
    def test_linux_dispatch(
        self,
        mock_linux: MagicMock,
        mock_windows: MagicMock,
    ) -> None:
        """os.name != 'nt' 时走 Linux 分支。"""
        with patch("src.python.tui.tui_keys.os.name", "posix"):
            get_key()
        mock_linux.assert_called_once()
        mock_windows.assert_not_called()


@unittest.skipIf(os.name != "nt", "Windows only")
class TestGetKeyWindows(unittest.TestCase):
    """Windows 分支 _get_key_windows 测试。"""

    def setUp(self) -> None:
        # 确保 msvcrt 已在 sys.modules 中，patch 才能正确拦截

        self._patcher = patch("msvcrt.getch")
        self._mock_getch = self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()

    # -- 特殊键 -------------------------------------------------------

    def test_ctrl_c(self) -> None:
        """Ctrl+C 输入 → KEY_CTRL_C。"""
        self._mock_getch.return_value = b"\x03"
        self.assertEqual(_get_key_windows(), KEY_CTRL_C)

    def test_enter(self) -> None:
        """Enter 回车 → KEY_ENTER。"""
        self._mock_getch.return_value = b"\r"
        self.assertEqual(_get_key_windows(), KEY_ENTER)

    def test_esc(self) -> None:
        """ESC 键 → KEY_ESC（首页退出别名）。"""
        self._mock_getch.return_value = b"\x1b"
        self.assertEqual(_get_key_windows(), KEY_ESC)

    def test_arrow_up(self) -> None:
        """方向键上 (b'\\xe0' + b'H') → KEY_UP。"""
        self._mock_getch.side_effect = [b"\xe0", b"H"]
        self.assertEqual(_get_key_windows(), KEY_UP)

    def test_arrow_down(self) -> None:
        """方向键下 (b'\\xe0' + b'P') → KEY_DOWN。"""
        self._mock_getch.side_effect = [b"\xe0", b"P"]
        self.assertEqual(_get_key_windows(), KEY_DOWN)

    def test_arrow_unknown(self) -> None:
        """方向键前缀后跟未知键 → KEY_UNKNOWN。"""
        self._mock_getch.side_effect = [b"\xe0", b"Q"]
        self.assertEqual(_get_key_windows(), KEY_UNKNOWN)

    def test_func_key_prefix(self) -> None:
        """功能键前缀 b'\\x00' 后跟未知键 → KEY_UNKNOWN。"""
        self._mock_getch.side_effect = [b"\x00", b"Q"]
        self.assertEqual(_get_key_windows(), KEY_UNKNOWN)

    # -- 普通键 -------------------------------------------------------

    def test_upper_letter(self) -> None:
        """大写字母键 → 返回大写字母。"""
        self._mock_getch.return_value = b"X"
        self.assertEqual(_get_key_windows(), "X")

    def test_lowercase_letter(self) -> None:
        """小写字母键 → 转为大写。"""
        self._mock_getch.return_value = b"a"
        self.assertEqual(_get_key_windows(), "A")

    def test_digit(self) -> None:
        """数字键 → 返回数字字符串。"""
        self._mock_getch.return_value = b"7"
        self.assertEqual(_get_key_windows(), "7")

    # -- 异常路径 -----------------------------------------------------

    def test_unicode_decode_error(self) -> None:
        """UnicodeDecodeError → KEY_UNKNOWN。"""
        self._mock_getch.return_value = b"\x80"
        self.assertEqual(_get_key_windows(), KEY_UNKNOWN)

    def test_keyboard_interrupt(self) -> None:
        """KeyboardInterrupt 异常 → KEY_CTRL_C。"""
        self._mock_getch.side_effect = KeyboardInterrupt()
        self.assertEqual(_get_key_windows(), KEY_CTRL_C)


@unittest.skipIf(os.name != "posix", "Linux only")
class TestGetKeyLinux(unittest.TestCase):
    """Linux 分支 _get_key_linux 测试。"""

    def setUp(self) -> None:
        import termios

        import src.python.tui.tui_keys as tui_keys_mod

        tui_keys_mod._esc_residue_pending = False  # 残留/半途序列标志隔离：不跨用例泄漏
        tui_keys_mod._seq_prefix_pending = ""
        self._termios_error = termios.error
        self._stdin_patcher = patch("src.python.tui.tui_keys.sys.stdin")
        self._mock_stdin = self._stdin_patcher.start()
        self._mock_stdin.fileno.return_value = 99
        # 读键根因：os.read 原始字节（sys.stdin.read 带缓冲会让 select(fd) 谎报）
        self._osread_patcher = patch("src.python.tui.tui_keys.os.read")
        self._mock_osread = self._osread_patcher.start()

        # 使用全局模块级 patch，因为 _get_key_linux 内部通过 import 获取模块
        self._tcgetattr_patcher = patch("termios.tcgetattr")
        self._mock_tcgetattr = self._tcgetattr_patcher.start()
        self._mock_tcgetattr.return_value = MagicMock()

        self._tcsetattr_patcher = patch("termios.tcsetattr")
        self._mock_tcsetattr = self._tcsetattr_patcher.start()

        self._setraw_patcher = patch("tty.setraw")
        self._mock_setraw = self._setraw_patcher.start()

        self._select_patcher = patch("select.select")
        self._mock_select = self._select_patcher.start()

    def tearDown(self) -> None:
        self._osread_patcher.stop()
        self._select_patcher.stop()
        self._setraw_patcher.stop()
        self._tcsetattr_patcher.stop()
        self._tcgetattr_patcher.stop()
        self._stdin_patcher.stop()

    # -- 特殊键 -------------------------------------------------------

    def test_ctrl_c(self) -> None:
        """Ctrl+C 输入 → KEY_CTRL_C。"""
        self._mock_osread.return_value = b"\x03"
        self.assertEqual(_get_key_linux(), KEY_CTRL_C)

    def test_enter_cr(self) -> None:
        """回车 \\r → KEY_ENTER。"""
        self._mock_osread.return_value = b"\r"
        self.assertEqual(_get_key_linux(), KEY_ENTER)

    def test_enter_lf(self) -> None:
        """换行 \\n → KEY_ENTER。"""
        self._mock_osread.return_value = b"\n"
        self.assertEqual(_get_key_linux(), KEY_ENTER)

    # -- ESC / 方向键 -------------------------------------------------

    def test_escape_up(self) -> None:
        """ESC [ A → KEY_UP。"""
        self._mock_osread.side_effect = [b"\x1b", b"[", b"A"]
        self._mock_select.return_value = ([self._mock_stdin], [], [])
        self.assertEqual(_get_key_linux(), KEY_UP)

    def test_escape_down(self) -> None:
        """ESC [ B → KEY_DOWN。"""
        self._mock_osread.side_effect = [b"\x1b", b"[", b"B"]
        self._mock_select.return_value = ([self._mock_stdin], [], [])
        self.assertEqual(_get_key_linux(), KEY_DOWN)

    def test_escape_unknown_seq(self) -> None:
        """ESC [ X → KEY_UNKNOWN。"""
        self._mock_osread.side_effect = [b"\x1b", b"[", b"X"]
        self._mock_select.return_value = ([self._mock_stdin], [], [])
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)

    def test_standalone_esc(self) -> None:
        """单独 ESC 键（select 超时无后继字节）→ KEY_ESC（首页连按两次退出首按）。"""
        self._mock_osread.return_value = b"\x1b"
        self._mock_select.return_value = ([], [], [])
        self.assertEqual(_get_key_linux(), KEY_ESC)

    def test_late_arrow_sequence_mapped_after_lone_esc(self) -> None:
        """孤 ESC 之后迟到的方向键续段被吸收并映射回方向键（拆包不误触发直达键）。"""
        self._mock_osread.side_effect = [b"\x1b"]
        self._mock_select.return_value = ([], [], [])
        self.assertEqual(_get_key_linux(), KEY_ESC)
        self._mock_osread.side_effect = [b"[", b"A"]
        self._mock_select.return_value = ([self._mock_stdin], [], [])
        self.assertEqual(_get_key_linux(), KEY_UP)

    def test_partial_sequence_final_byte_maps_not_dispatches(self) -> None:
        """序列末字节超时后迟到：按补全映射回方向键，绝不进字母分派（曾泄漏启动 B 报告）。"""
        # ESC [ 齐到、末字节 B 超时 → KEY_UNKNOWN + 记半途前缀
        self._mock_osread.side_effect = [b"\x1b", b"["]
        self._mock_select.side_effect = [([self._mock_stdin], [], []), ([], [], [])]
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)
        # 迟到的 B → 补全映射为 KEY_DOWN（导航），而非独立键 "B"
        self._mock_osread.side_effect = [b"B"]
        self.assertEqual(_get_key_linux(), KEY_DOWN)

    def test_partial_sequence_swallow_unrelated_byte(self) -> None:
        """半途序列后的无关字节：吞掉为 KEY_UNKNOWN（丢失一键，不误触发功能）。"""
        self._mock_osread.side_effect = [b"\x1b", b"["]
        self._mock_select.side_effect = [([self._mock_stdin], [], []), ([], [], [])]
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)
        self._mock_osread.side_effect = [b"x"]
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)
        self._mock_osread.side_effect = [b"y"]  # 标志已清，恢复正常分派
        self.assertEqual(_get_key_linux(), "Y")

    def test_residue_cleared_by_normal_key(self) -> None:
        """残留标志下的普通字符：清标志并按普通键处理（不吞字）。"""
        self._mock_osread.side_effect = [b"\x1b"]
        self._mock_select.return_value = ([], [], [])
        self.assertEqual(_get_key_linux(), KEY_ESC)
        self._mock_osread.side_effect = [b"q"]
        self.assertEqual(_get_key_linux(), "Q")
        self._mock_osread.side_effect = [b"z"]
        self.assertEqual(_get_key_linux(), "Z")

    def test_esc_timeout_relaxed_for_high_latency_links(self) -> None:
        """首段共聚窗口 ≥0.5s + 续读窗口 ≥0.3s：高延迟链路（手机网络/SSH）方向键
        序列拆包不被误判为孤 Esc（主菜单上孤 Esc = 退出别名，误判即意外退出）。"""
        from src.python.tui.tui_keys import _ESC_FIRST_TIMEOUT, _ESC_TIMEOUT

        assert _ESC_FIRST_TIMEOUT >= 0.5
        assert _ESC_TIMEOUT >= 0.3

    def test_escape_ss3_application_cursor(self) -> None:
        """应用光标模式序列（O 前缀变体）→ KEY_UP（部分终端 smkx 后发送此格式）。"""
        self._mock_osread.side_effect = [b"\x1b", b"O", b"A"]
        self._mock_select.return_value = ([self._mock_stdin], [], [])
        self.assertEqual(_get_key_linux(), KEY_UP)

    # -- 普通键 -------------------------------------------------------

    def test_normal_key(self) -> None:
        """普通字母键 → 转为大写。"""
        self._mock_osread.return_value = b"x"
        self.assertEqual(_get_key_linux(), "X")

    def test_empty_key(self) -> None:
        """空字符串 → KEY_UNKNOWN。"""
        self._mock_osread.return_value = b""
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)

    # -- 异常路径 -----------------------------------------------------

    def test_setraw_error(self) -> None:
        """tty.setraw 抛出 termios.error → KEY_UNKNOWN，finally 仍调用 tcsetattr。"""
        self._mock_setraw.side_effect = self._termios_error("fake error")
        self.assertEqual(_get_key_linux(), KEY_UNKNOWN)
        self._mock_tcsetattr.assert_called_once()

    def test_keyboard_interrupt(self) -> None:
        """os.read 抛出 KeyboardInterrupt → KEY_CTRL_C。"""
        self._mock_osread.side_effect = KeyboardInterrupt()
        self.assertEqual(_get_key_linux(), KEY_CTRL_C)


class TestInputChoice(unittest.TestCase):
    """input_choice：菜单行输入（Esc 即时取消 / 回车提交 / 非 TTY 回退 input）。"""

    def test_non_tty_falls_back_to_input(self) -> None:
        """非 TTY（测试/管道）回退内置 input，行为与旧直调一致（含 strip）。"""
        with (
            patch("src.python.tui.tui_keys.sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="  3  "),
        ):
            mock_stdin.isatty.return_value = False
            self.assertEqual(input_choice("  > "), "3")

    def setUp(self) -> None:
        import src.python.tui.tui_keys as tui_keys_mod

        tui_keys_mod._esc_residue_pending = False  # 残留/半途序列标志隔离：不跨用例泄漏
        tui_keys_mod._seq_prefix_pending = ""

    def _linux_env(self, read_bytes):
        """装配 Linux raw 读行环境（与 TestGetKeyLinux 同手法）。"""
        return (
            patch("src.python.tui.tui_keys.sys.stdin"),
            patch("termios.tcgetattr", return_value=MagicMock()),
            patch("termios.tcsetattr"),
            patch("tty.setraw"),
            patch("src.python.tui.tui_keys.os.read", side_effect=read_bytes),
        )

    def test_linux_esc_cancels_immediately(self) -> None:
        """孤立 Esc（超时无后继字节）→ None：误入子菜单即时返回上一步。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"\x1b"])
        with (
            stdin as mock_stdin,
            _tcg,
            _tcs,
            _raw,
            patch("select.select", return_value=([], [], [])),
            _read,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertIsNone(_input_choice_linux("  > "))

    def test_linux_residue_sequence_swallowed(self) -> None:
        """孤 Esc 后迟到的方向键序列：整段吞掉不进输入行，随后输入正常。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"\x1b"])
        with (
            stdin as mock_stdin,
            _tcg,
            _tcs,
            _raw,
            patch("select.select", return_value=([], [], [])),
            _read,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertIsNone(_input_choice_linux("  > "))  # 孤 Esc → 取消并置残留标志
        stdin2, _tcg2, _tcs2, _raw2, _read2 = self._linux_env([b"[", b"A", b"3", b"\r"])
        with (
            stdin2 as mock_stdin,
            _tcg2,
            _tcs2,
            _raw2,
            patch("select.select", return_value=([mock_stdin], [], [])),
            _read2,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertEqual(_input_choice_linux("  > "), "3")

    def test_linux_enter_submits_line(self) -> None:
        """逐字节输入 + 回车 → strip 后的行内容。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"3", b"\r"])
        with stdin as mock_stdin, _tcg, _tcs, _raw, _read:
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertEqual(_input_choice_linux("  > "), "3")

    def test_linux_backspace_edits_last_char(self) -> None:
        """退格回剥最后一个字符。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"3", b"4", b"\x7f", b"\r"])
        with stdin as mock_stdin, _tcg, _tcs, _raw, _read:
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertEqual(_input_choice_linux("  > "), "3")

    def test_linux_ctrl_c_raises_interrupt(self) -> None:
        """raw 模式下 Ctrl+C 转发为 KeyboardInterrupt（与调用方 except 分支衔接）。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"\x03"])
        with stdin as mock_stdin, _tcg, _tcs, _raw, _read:
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            with self.assertRaises(KeyboardInterrupt):
                _input_choice_linux("  > ")

    def test_linux_arrows_return_nav_keys(self) -> None:
        """arrows=True 且行为空：↑/↓ 序列返回方向键键名（列表面板导航）。"""
        for seq, expect in (([b"\x1b", b"[", b"A"], KEY_UP), ([b"\x1b", b"[", b"B"], KEY_DOWN)):
            stdin, _tcg, _tcs, _raw, _read = self._linux_env(seq)
            with (
                stdin as mock_stdin,
                _tcg,
                _tcs,
                _raw,
                patch("select.select", return_value=([mock_stdin], [], [])),
                _read,
            ):
                mock_stdin.isatty.return_value = True
                mock_stdin.fileno.return_value = 99
                self.assertEqual(_input_choice_linux("  > ", arrows=True), expect)

    def test_linux_arrows_swallowed_when_line_has_content(self) -> None:
        """行内已有内容：方向键序列仍吞掉（保行编辑），Enter 提交原行。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"3", b"\x1b", b"[", b"B", b"\r"])
        with (
            stdin as mock_stdin,
            _tcg,
            _tcs,
            _raw,
            patch("select.select", return_value=([mock_stdin], [], [])),
            _read,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertEqual(_input_choice_linux("  > ", arrows=True), "3")

    def test_linux_arrows_disabled_swallows_sequences(self) -> None:
        """默认（arrows=False）：方向键序列整段吞掉（既有调用方行为不变）。"""
        stdin, _tcg, _tcs, _raw, _read = self._linux_env([b"\x1b", b"[", b"B", b"3", b"\r"])
        with (
            stdin as mock_stdin,
            _tcg,
            _tcs,
            _raw,
            patch("select.select", return_value=([mock_stdin], [], [])),
            _read,
        ):
            mock_stdin.isatty.return_value = True
            mock_stdin.fileno.return_value = 99
            self.assertEqual(_input_choice_linux("  > "), "3")

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_windows_esc_cancels(self) -> None:
        """Esc 键（单字符 \x1b）即时取消。"""
        with patch("msvcrt.getwch", side_effect=["\x1b"]):
            self.assertIsNone(_input_choice_windows("  > "))

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_windows_enter_submits_line(self) -> None:
        """逐字符输入 + 回车 → strip 后的行内容。"""
        with patch("msvcrt.getwch", side_effect=["3", "\r"]):
            self.assertEqual(_input_choice_windows("  > "), "3")


@unittest.skipIf(os.name != "posix", "Linux only")
class TestGetKeyWholePacketPty(unittest.TestCase):
    """整包 ESC[B（电脑常态）必须即时解析为方向键。

    回归锚点：sys.stdin.read 缓冲把整包吞进用户态后 select(fd) 谎报「无数据」，
    每次方向键都被误判为孤 ESC——首按挂上退出确认态、次按即误退出程序（用户实测
    「首页按两次方向键第二次退出」）。pty 真链路断言 <0.4s 返回 KEY_DOWN（误判
    路径耗时 ≥0.8s 且返回 KEY_ESC）。
    """

    @unittest.skipUnless(os.name == "posix", "pty 仅 POSIX")
    def test_whole_packet_arrow_returns_down_immediately(self) -> None:
        """整包 ESC[B 到达 → 子进程全新解释器上 get_key 即时返回 KEY_DOWN（<0.4s）。

        误判路径（缓冲谎报）耗时 ≥0.8s 且返回 KEY_ESC，本断言两头都拦得住。
        """
        import subprocess
        import sys as _sys
        import time as _time

        import pty as _pty

        code = (
            "import sys, time\n"
            f"sys.path.insert(0, {os.getcwd()!r})\n"
            "from src.python.tui.tui_keys import get_key\n"
            "import termios, tty\n"
            "tty.setraw(0)\n"  # 先切 raw：父进程随后写入的字节不进规范行缓冲
            "sys.stderr.write('READY\\n'); sys.stderr.flush()\n"
            "t0 = time.time()\n"
            "k = get_key()\n"
            "dt = time.time() - t0\n"
            "sys.stderr.write(f'k={k} dt={dt:.2f}\\n'); sys.stderr.flush()\n"
            "sys.exit(0 if (k == 'KEY_DOWN' and dt < 0.4) else 1)\n"
        )
        master, slave = _pty.openpty()
        proc = subprocess.Popen(
            [_sys.executable, "-c", code],
            stdin=slave,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        os.close(slave)
        # 子进程 READY（已 setraw）后写入 → dt 为纯解析耗时：
        # 即时解析 ~ms；缓冲谎报误判路径 = 0.5+0.3 两段超时 ≥0.8s，两头都拦得住
        ready = proc.stderr.readline()
        if b"READY" not in ready:
            os.close(master)
            proc.kill()
            self.fail(f"子进程未就绪：{ready!r}")
        _time.sleep(0.12)  # 等子进程跨入 get_key 读阻塞（READY 后立即写有毫秒级竞态）
        os.write(master, b"\x1b[B")
        try:
            _, err = proc.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            os.close(master)
            self.fail("get_key 未在 6s 内返回（疑似阻塞）")
        os.close(master)
        self.assertEqual(
            proc.returncode,
            0,
            f"整包方向键须即时解析为 KEY_DOWN（<0.4s），而非孤 ESC 误判；child={err.decode(errors='replace')[-300:]}",
        )


if __name__ == "__main__":
    unittest.main()
