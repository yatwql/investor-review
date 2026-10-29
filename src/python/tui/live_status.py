"""长任务状态条：单行原地刷新的「当前阶段 · 已耗时 · ETA · 中止键」。

作用域严格限定在**报告生成期间**：主菜单不出现状态条，生成结束后整行清除。
非 TTY / 设置 ``TUI_PLAIN`` / 非 POSIX 时 :meth:`LiveStatusBar.supported` 为假，
调用方退回既有逐行 ``[..]`` 输出（管道输出与无状态条时逐字节一致）。

与落地行的关系：``[OK]`` / ``[!]`` / ``[ERR]`` 是历史流水，必须整行留存；状态条只
表达「现在在做什么」。因此 reporter 每次落地行前须 :meth:`suspend`（清掉状态条），
打印后 :meth:`resume`（重画），否则两套输出会互相覆盖成鬼影行。
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

from src.python.core.ansi_colors import DIM, RESET
from src.python.tui.text_layout import terminal_columns, truncate_display

#: 清到行尾（状态条每帧先回车归位、再清残影，避免上一帧更长时留尾）
_CLEAR_LINE = "\r\x1b[K"


def status_bar_text(phase: str, elapsed: float, eta: float | None, *, cancel_hint: str = "q 中止") -> str:
    """状态条正文（阶段文案复用 ``perf.format_stage_status``，本函数只加前缀与中止键）。

    阶段/已耗时/ETA 的措辞在 ``core.perf`` 单源——CLI、Web、TUI 三渠道看到的是同一句话，
    不会出现「已 12s」与「已耗时 12s」两种说法。

    Args:
        phase: 当前阶段名（如「行情获取」）。
        elapsed: 本阶段已耗时（秒）。
        eta: 预计剩余秒数；None = 历史样本不足，只报已耗时。
        cancel_hint: 中止键提示；空串表示当前环境无法按键中止。

    Returns:
        单行文本（未着色、未截断）。
    """
    from src.python.core.perf import format_stage_status

    parts = [f"[..] {format_stage_status({'phase': phase, 'elapsed': elapsed}, eta)}"]
    if cancel_hint:
        parts.append(cancel_hint)
    return " · ".join(parts)


class LiveStatusBar:
    """单行原地刷新的状态条（非线程安全：由调用方串行 update/suspend/resume）。"""

    def __init__(self, stream: TextIO | None = None, *, cancel_hint: str = "q 中止") -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._cancel_hint = cancel_hint
        self._last: str = ""
        self._active = False
        self._closed = False

    @staticmethod
    def supported(stream: TextIO | None = None) -> bool:
        """当前环境是否可用状态条（POSIX + TTY + 未设 ``TUI_PLAIN``）。"""
        if os.environ.get("TUI_PLAIN"):
            return False
        if os.name != "posix":
            return False
        out = stream if stream is not None else sys.stdout
        try:
            return bool(out.isatty())
        except Exception:
            return False

    @property
    def cancel_hint(self) -> str:
        """中止键提示（心跳层据环境把 ``q 中止`` 降级为 ``Ctrl+C 中断``）。"""
        return self._cancel_hint

    def _write(self, text: str) -> None:
        self._stream.write(text)
        self._stream.flush()

    def _render(self, text: str) -> str:
        columns = terminal_columns()
        body = f"  {DIM}{text}{RESET}"
        return truncate_display(body, columns, ellipsis="…")

    def update(self, text: str) -> None:
        """刷新状态条（覆写同一行；调用方负责把正文交给 :func:`status_bar_text`）。"""
        if self._closed:
            return
        self._last = text
        self._active = True
        self._write(_CLEAR_LINE + self._render(text))

    def suspend(self) -> None:
        """清掉状态条（落地行打印前调用；无状态条时为空操作）。"""
        if not self._active or self._closed:
            return
        self._write(_CLEAR_LINE)
        self._active = False

    def resume(self) -> None:
        """重画最近一帧（落地行打印后调用）。"""
        if self._active or not self._last or self._closed:
            return
        self._active = True
        self._write(self._render(self._last))

    def close(self) -> None:
        """清除状态条并停止后续输出（生成收尾/异常路径必调）。"""
        self.suspend()
        self._closed = True
        self._last = ""


class KeyWatcher:
    """单键轮询（POSIX TTY，cbreak）：供后台心跳检测中止键。

    只在报告生成期间开启：把终端从行缓冲切到 cbreak（不等回车、不回显），
    :meth:`close` 恢复原属性。异常路径也必须走到 close——条带外的按键仍按原语义
    交给主循环。
    """

    def __init__(self, fd: int = 0) -> None:
        self._fd = fd
        self._saved: list | None = None

    @staticmethod
    def supported() -> bool:
        """当前环境能否单键轮询（POSIX + stdin 是 TTY + 未禁用纯文本模式）。"""
        if os.name != "posix" or os.environ.get("TUI_PLAIN"):
            return False
        try:
            return bool(sys.stdin.isatty())
        except Exception:
            return False

    def open(self) -> bool:
        """切 cbreak 模式；失败返回 False（调用方据此退化为「只显示不可中止」）。"""
        try:
            import termios
            import tty

            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            return True
        except Exception:
            self._saved = None
            return False

    def poll(self) -> str | None:
        """非阻塞取一个按键；无按键/读失败返回 None。"""
        try:
            import select

            ready, _, _ = select.select([self._fd], [], [], 0)
            if not ready:
                return None
            data = os.read(self._fd, 1)
            return data.decode(errors="ignore") if data else None
        except (OSError, ValueError):
            return None

    def close(self) -> None:
        """恢复终端原属性（未成功 open 时为空操作）。"""
        if self._saved is None:
            return
        try:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        except Exception:
            pass
        self._saved = None
