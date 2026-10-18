"""终端键盘输入封装，跨平台支持方向键操作。

Windows: 使用 msvcrt
Linux:   使用 tty + termios + select（超时）
"""

from __future__ import annotations

import os
import sys

# 标准键名常量
KEY_UP = "KEY_UP"
KEY_DOWN = "KEY_DOWN"
KEY_ENTER = "KEY_ENTER"
KEY_CTRL_C = "KEY_CTRL_C"
KEY_ESC = "KEY_ESC"
KEY_UNKNOWN = "KEY_UNKNOWN"

# Linux ESC 序列读取超时（秒）。0.3s 面向高延迟链路（手机蜂窝网 / SSH）：
# 方向键三字节序列可能分节到达，过短的超时会把序列拆散误判成孤 ESC
_ESC_TIMEOUT = 0.3


def get_key() -> str:
    """读取一个键盘输入，返回标准化键名。

    支持方向键、回车、Ctrl+C、Esc（孤立 ESC → KEY_ESC）和普通字母键（字母统一转为大写）。

    Returns:
        标准键名字符串
    """
    if os.name == "nt":
        return _get_key_windows()
    return _get_key_linux()


# ── Windows ──────────────────────────────────────────────────


def _get_key_windows() -> str:
    import msvcrt  # Windows 标准库，无需额外安装

    try:
        ch = msvcrt.getch()
    except KeyboardInterrupt:
        return KEY_CTRL_C

    if ch == b"\x03":  # Ctrl+C
        return KEY_CTRL_C
    if ch == b"\r":  # Enter
        return KEY_ENTER
    if ch == b"\x1b":  # ESC（孤 ESC → Esc 键，首页退出别名）
        return KEY_ESC
    if ch in (b"\xe0", b"\x00"):  # 方向键/功能键前缀
        try:
            ch2 = msvcrt.getch()
        except KeyboardInterrupt:
            return KEY_CTRL_C
        mapping = {b"H": KEY_UP, b"P": KEY_DOWN}
        return mapping.get(ch2, KEY_UNKNOWN)
    try:
        return ch.decode("utf-8").upper()
    except (UnicodeDecodeError, KeyboardInterrupt):
        return KEY_UNKNOWN


# ── Linux ────────────────────────────────────────────────────


def _get_key_linux() -> str:
    import select

    if not sys.stdin.isatty():
        return KEY_UNKNOWN
    try:
        import termios  # Linux/macOS only
        import tty  # Linux/macOS only
    except ImportError:
        return KEY_UNKNOWN
    ch = ""
    try:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)  # type: ignore[attr-defined]
        tty.setraw(fd)  # type: ignore[attr-defined]
        ch = sys.stdin.read(1)
    except (termios.error, ValueError, OSError):  # type: ignore[attr-defined]
        pass
    except KeyboardInterrupt:
        ch = "\x03"  # 让下游 KEY_CTRL_C 分支处理

    try:
        if ch == "\x03":
            return KEY_CTRL_C
        if ch in ("\r", "\n"):
            return KEY_ENTER
        if ch == "\x1b":  # ESC 序列 -> 方向键；超时无后继字节 → 孤 ESC（Esc 键）
            rdy, _, _ = select.select([sys.stdin], [], [], _ESC_TIMEOUT)
            if not rdy:
                return KEY_ESC
            b1 = sys.stdin.read(1)
            if not b1:
                return KEY_UNKNOWN
            rdy2, _, _ = select.select([sys.stdin], [], [], _ESC_TIMEOUT)
            if not rdy2:
                return KEY_UNKNOWN
            b2 = sys.stdin.read(1)
            if not b2:
                return KEY_UNKNOWN
            seq = ch + b1 + b2
            mapping = {"\x1b[A": KEY_UP, "\x1b[B": KEY_DOWN}
            return mapping.get(seq, KEY_UNKNOWN)
        if ch:
            return ch.upper()
        return KEY_UNKNOWN
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)  # type: ignore[attr-defined]


# ── 菜单行输入 ────────────────────────────────────────────────


def input_choice(prompt: str) -> str | None:
    """菜单选择行输入：单独 Esc **即时**取消（返回 None），其余与 ``input()`` 同语义。

    子菜单用它替换 ``input()``——误入子菜单后按 Esc 立刻回上一步，不必找「0 返回」；
    回车提交、首尾空白剥离、Ctrl+C 抛 KeyboardInterrupt（与既有 except 分支衔接）。
    非 TTY（测试 / 管道）回退到内置 ``input()``（同样 strip），既有测试驱动方式不变。

    Args:
        prompt: 输入提示（调用方负责折行）。

    Returns:
        提交的行内容（已 strip）；Esc 取消返回 None。
    """
    if os.name == "nt":
        return _input_choice_windows(prompt)
    return _input_choice_linux(prompt)


def _input_choice_linux(prompt: str) -> str | None:
    """POSIX 分支：raw 模式逐字节读行（回显自理），孤立 ESC 按超时判定即时取消。"""
    if not sys.stdin.isatty():
        return input(prompt).strip()
    import select

    try:
        import termios
        import tty
    except ImportError:
        return input(prompt).strip()

    print(prompt, end="", flush=True)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)  # type: ignore[attr-defined]
    buf = b""
    try:
        tty.setraw(fd)  # type: ignore[attr-defined]
        while True:
            b = os.read(fd, 1)
            if not b:  # EOF
                print(flush=True)
                return None
            if b in (b"\r", b"\n"):
                print(flush=True)
                return buf.decode("utf-8", errors="replace").strip()
            if b in (b"\x7f", b"\x08"):  # 退格：按 UTF-8 字符回剥（含多字节续字节）
                while buf and (buf[-1] & 0xC0) == 0x80:
                    buf = buf[:-1]
                if buf:
                    buf = buf[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            if b == b"\x1b":
                rdy, _, _ = select.select([fd], [], [], _ESC_TIMEOUT)
                if not rdy:  # 孤立 Esc → 即时取消（手机 SSH 直接回上一步）
                    print(flush=True)
                    return None
                nxt = os.read(fd, 1)  # 方向键等序列：吞掉不响应（本行不支持移动）
                if nxt == b"[":
                    while True:
                        fin = os.read(fd, 1)
                        if not fin or fin.isalpha() or fin == b"~":
                            break
                continue
            if b == b"\x03":  # raw 模式 ISIG 关闭 → Ctrl+C 手动转发给 except 分支
                raise KeyboardInterrupt
            if b < b" ":
                continue
            buf += b
            sys.stdout.write(b.decode("utf-8", errors="replace"))
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)  # type: ignore[attr-defined]


def _input_choice_windows(prompt: str) -> str | None:
    """Windows 分支：msvcrt 逐字符读行，Esc 键（\x1b 单字符）即时取消。"""
    if not sys.stdin.isatty():
        return input(prompt).strip()
    import msvcrt  # Windows 标准库，无需额外安装

    print(prompt, end="", flush=True)
    buf = ""
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            print(flush=True)
            return buf.strip()
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1b":  # Esc 键 → 即时取消
            print(flush=True)
            return None
        if ch in ("\x00", "\xe0"):  # 方向键/功能键双字节前缀：吞掉
            msvcrt.getwch()
            continue
        if ch in ("\x7f", "\x08"):
            if buf:
                buf = buf[:-1]
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if ch < " ":
            continue
        buf += ch
        sys.stdout.write(ch)
        sys.stdout.flush()
