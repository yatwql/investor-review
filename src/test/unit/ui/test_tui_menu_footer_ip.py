# -*- coding: utf-8 -*-
"""首页页脚「本机 IP」行（首页最下方一行，供手机/其他终端访问本机时抄写）。

为什么需要：IP 来自运行时探测（``get_machine_ip``），而页脚又处在每帧重绘的位置——
既要保证它真的落在帧的最下方，也要保证重绘不每帧重跑一次探测，且取不到时降级为
``—``，不把内部哨兵值 ``unknown`` 甩到屏幕上。
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import patch

import pytest

from src.python.tui.status_line import machine_ip_line, reset_status_memo

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture(autouse=True)
def _clear_memo():
    """每条用例前后清空状态行记忆（含本机 IP 段），避免跨用例串味。"""
    reset_status_memo()
    yield
    reset_status_memo()


class TestMachineIpLine:
    """``machine_ip_line`` 取数与降级。"""

    def test_returns_ip_from_single_source(self):
        """IP 取自 ``core.system_info.get_machine_ip``（不另写探测逻辑）。"""
        with patch("src.python.core.system_info.get_machine_ip", return_value="192.168.1.5"):
            assert machine_ip_line() == "本机 IP 192.168.1.5"

    def test_unknown_sentinel_degrades_to_dash(self):
        """取数原语失败时的哨兵值 ``unknown`` 不上屏，按 ``—`` 展示。"""
        with patch("src.python.core.system_info.get_machine_ip", return_value="unknown"):
            assert machine_ip_line() == "本机 IP —"

    def test_probe_exception_degrades_to_dash(self):
        """探测抛错不冒成首页渲染失败（页脚整行降级）。"""
        with patch("src.python.core.system_info.get_machine_ip", side_effect=OSError("no route")):
            assert machine_ip_line() == "本机 IP —"

    def test_memoized_within_ttl(self):
        """TTL 内复用记忆：首页逐帧重绘不得每帧重跑一次探测。"""
        with patch("src.python.core.system_info.get_machine_ip", return_value="10.0.0.7") as probe:
            machine_ip_line(now=1000.0)
            machine_ip_line(now=1000.5)
        assert probe.call_count == 1

    def test_retakes_after_memo_reset(self):
        """``reset_status_memo``（[R] 刷新 / 配置变更）后重新取数，新地址即刻上屏。"""
        with patch("src.python.core.system_info.get_machine_ip", return_value="10.0.0.7"):
            machine_ip_line(now=2000.0)
        reset_status_memo()
        with patch("src.python.core.system_info.get_machine_ip", return_value="10.0.0.9"):
            assert machine_ip_line(now=2000.1) == "本机 IP 10.0.0.9"


class TestHomeFrameFooter:
    """首页整帧渲染：IP 行落在帧的最下方一行。"""

    def _frame_lines(self, columns: int = 90) -> list[str]:
        from src.python.tui import text_layout, tui

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with patch.object(text_layout, "terminal_columns", return_value=columns):
                with patch("src.python.core.system_info.get_machine_ip", return_value="192.168.1.5"):
                    with patch("src.python.tui.tui.print_header", lambda: None):
                        with patch("src.python.tui.tui.show_config", lambda: None):
                            with patch("src.python.tui.tui.render_menu", lambda *_a, **_k: None):
                                assert tui._render_menu_frame(0) > 0
        return out.getvalue().splitlines()

    def test_ip_is_bottom_most_line(self):
        """IP 行是该帧最后一个非空行（排在菜单与键位页脚之后）。"""
        lines = [line for line in self._frame_lines() if line.strip()]
        assert "本机 IP 192.168.1.5" in lines[-1]

    def test_rendered_below_menu_footer(self):
        """渲染顺序固定：菜单（含键位页脚）在前，IP 行在后。"""
        from src.python.tui.text_layout import display_width

        lines = [line for line in self._frame_lines(columns=56) if line.strip()]
        ip_index = next(i for i, line in enumerate(lines) if "本机 IP" in line)
        assert ip_index == len(lines) - 1
        assert all(display_width(line) <= 56 for line in lines)
