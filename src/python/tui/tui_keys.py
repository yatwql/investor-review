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
# 方向键序列映射（CSI 与应用光标模式 O 前缀变体同权——部分终端/会话在 smkx 后发送后者）
_CSI_SEQUENCE_MAPPING = {
    "\x1b[A": KEY_UP,
    "\x1b[B": KEY_DOWN,
    "\x1bOA": KEY_UP,
    "\x1bOB": KEY_DOWN,
}

# 孤 ESC 残留标志：高延迟链路上 ESC 与其后续字节拆包到达时，首段超时已按孤 ESC 返回，
# 迟到的前缀（[ / O）由下一次读键按序列续读吸收并映射回方向键——否则残留字节会被当成
# 普通按键误触发直达键（如 [A 的 A 命中匿名化面板）。get_key 与 input_choice 共用。
_esc_residue_pending = False


def _mark_esc_residue() -> None:
    """孤 ESC 判定后置残留标志（下一次读键优先按序列吸收迟到前缀）。"""
    global _esc_residue_pending
    _esc_residue_pending = True


def _take_esc_residue(ch: str) -> str | None:
    """get_key 路径的残留吸收：迟到序列前缀 → 读完整段并映射；其他 → 清标志放行。

    Args:
        ch: 本次读到的首个字符（孤 ESC 之后的下一次读）。

    Returns:
        映射后的键名（方向键或 KEY_UNKNOWN）；无残留或首字符非前缀时 None。
    """
    global _esc_residue_pending
    if not _esc_residue_pending:
        return None
    _esc_residue_pending = False
    if ch not in ("[", "O"):
        return None  # 非序列续段：按普通键继续处理
    import select

    rdy, _, _ = select.select([sys.stdin], [], [], _ESC_TIMEOUT)
    if not rdy:
        return KEY_UNKNOWN
    b2 = sys.stdin.read(1)
    if not b2:
        return KEY_UNKNOWN
    return _CSI_SEQUENCE_MAPPING.get("\x1b" + ch + b2, KEY_UNKNOWN)


def _swallow_esc_residue_byte(b: bytes, fd: int) -> bool:
    """input_choice 路径的残留吸收：迟到的 [ / O 前缀吞掉整段序列并清标志。

    Args:
        b: 本次读到的字节（孤 ESC 之后的下一次读）。
        fd: 输入文件描述符（续读用）。

    Returns:
        bool True = 已消费该字节（调用方 continue）。
    """
    global _esc_residue_pending
    if not _esc_residue_pending:
        return False
    _esc_residue_pending = False
    if b not in (b"[", b"O"):
        return False
    import select

    rdy, _, _ = select.select([fd], [], [], _ESC_TIMEOUT)
    if not rdy:
        return True
    fin = os.read(fd, 1)
    while fin and not (fin.isalpha() or fin == b"~"):
        rdy2, _, _ = select.select([fd], [], [], _ESC_TIMEOUT)
        if not rdy2:
            break
        fin = os.read(fd, 1)
    return True


# 方向键序列续读窗口（同一次输入爆发内的后续字节）与首段共聚窗口（ESC 后等 '[' 的窗口）。
# 首段更大：高延迟链路（手机网络/SSH）上终端会把 ESC [ A 拆成独立分节到达，
# 窗口过短会把方向键误判为孤 Esc（主菜单上 = 退出别名，行为最重，须留足余量）
_ESC_TIMEOUT = 0.3
_ESC_FIRST_TIMEOUT = 0.5


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
        residue = _take_esc_residue(ch)  # 孤 ESC 后迟到的序列续段：吸收并映射回方向键
        if residue is not None:
            return residue
        if ch == "\x1b":  # ESC 序列 -> 方向键；超时无后继字节 → 孤 ESC（Esc 键）
            rdy, _, _ = select.select([sys.stdin], [], [], _ESC_FIRST_TIMEOUT)
            if not rdy:
                _mark_esc_residue()  # 迟到续段由下一次读键吸收（拆包不致误触发直达键）
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
            return _CSI_SEQUENCE_MAPPING.get(ch + b1 + b2, KEY_UNKNOWN)
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
            if _swallow_esc_residue_byte(b, fd):  # 孤 Esc 后迟到的方向键序列：整段吞掉
                continue
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
                rdy, _, _ = select.select([fd], [], [], _ESC_FIRST_TIMEOUT)
                if not rdy:  # 孤立 Esc → 即时取消（手机 SSH 直接回上一步）
                    _mark_esc_residue()  # 迟到续段由下一次读键吸收
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
