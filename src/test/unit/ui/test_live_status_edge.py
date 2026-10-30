# -*- coding: utf-8 -*-
"""状态条边缘（`@pytest.mark.edge`）：真实伪终端上的写入与终端属性不变式。

为什么用 pty：状态条的写入序列与「有没有动终端模式」只有真终端才测得准。这一组
正是用来钉住「状态条不得触碰 termios / stdin」：后台读键与 cbreak 一旦存在，就会把
终端留在无回显状态，而假流覆盖不到这类问题。
"""

from __future__ import annotations

import os
import pty
import termios

import pytest

from src.python.tui.live_status import LiveStatusBar, status_bar_text

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui, pytest.mark.edge]


@pytest.fixture()
def pty_pair():
    """(master, slave) 伪终端对；用例结束关闭。"""
    master, slave = pty.openpty()
    try:
        yield master, slave
    finally:
        os.close(master)
        os.close(slave)


class TestRealTerminal:
    def test_writes_reach_terminal(self, pty_pair):
        """状态条写入能到达终端（不是被缓冲丢弃）。"""
        master, slave = pty_pair
        with os.fdopen(os.dup(slave), "w", buffering=1, encoding="utf-8") as stream:
            bar = LiveStatusBar(stream)
            bar.update(status_bar_text("行情获取"))
            bar.close()
        data = os.read(master, 4096).decode(errors="ignore")
        assert "行情获取" in data or "\x1b[K" in data

    def test_termios_untouched(self, pty_pair):
        """状态条不得改动终端属性（cbreak 泄漏会让终端失去回显）。"""
        _master, slave = pty_pair
        before = termios.tcgetattr(slave)
        bar = LiveStatusBar(os.fdopen(os.dup(slave), "w", buffering=1, encoding="utf-8"))
        bar.update(status_bar_text("行情获取"))
        bar.close()
        assert termios.tcgetattr(slave) == before

    def test_no_stdin_read(self, pty_pair, monkeypatch):
        """状态条生命周期内不得读 stdin（后台读键会与交互提示抢输入）。"""
        _master, slave = pty_pair
        read_calls: list[int] = []
        real_read = os.read

        def _spy(fd, n):
            read_calls.append(fd)
            return real_read(fd, n)

        monkeypatch.setattr(os, "read", _spy)
        bar = LiveStatusBar(os.fdopen(os.dup(slave), "w", buffering=1, encoding="utf-8"))
        bar.update(status_bar_text("行情获取"))
        bar.close()
        assert read_calls == [], f"状态条不得读 stdin，实际读了 fd={read_calls}"
