# -*- coding: utf-8 -*-
"""长任务状态条（`tui/live_status.py`）：正文拼装、环境判据、覆写与挂起/恢复序列。

设计约束（与后台轮询的取舍）：状态条**只报当前阶段**，不启后台线程、不读 stdin、
不切 terminal 模式——后台读键会与生成前的交互提示抢输入，cbreak 泄漏会让终端失去
回显。因此本文件不测「心跳」，只测单帧渲染与生命周期幂等。
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest

from src.python.tui.live_status import LiveStatusBar, status_bar_text
from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

_CLEAR = "\r\x1b[K"


class _TtyStream(io.StringIO):
    """伪终端流：`isatty()` 为真，写入内容可断言。"""

    def isatty(self) -> bool:  # noqa: D102 - 覆写标准接口
        return True


class TestStatusBarText:
    """正文拼装：只报阶段；给出耗时/剩余时才带进度细节。"""

    def test_phase_only(self):
        """默认形态只报阶段与中断方式（不猜剩余时间）。"""
        text = status_bar_text("行情获取")
        assert text == "[..] 「行情获取」 · Ctrl+C 中断"

    def test_with_elapsed_and_eta(self):
        """给了已耗时与 ETA 时复用 `format_stage_status` 的措辞（三渠道同源）。"""
        text = status_bar_text("行情获取", 12.4, 40.2)
        assert "已耗时 12s" in text
        assert "预计剩余 ~40s" in text

    def test_hint_can_be_dropped(self):
        """hint 为空串时不出现中断方式（非交互场景）。"""
        assert "Ctrl+C" not in status_bar_text("行情获取", hint="")


class TestSupported:
    """环境判据矩阵：POSIX + TTY + 未禁用纯文本模式。"""

    def test_true_on_posix_tty(self):
        assert LiveStatusBar.supported(_TtyStream()) is True

    def test_false_on_non_tty(self):
        assert LiveStatusBar.supported(io.StringIO()) is False

    def test_false_when_plain_mode_requested(self):
        with patch.dict(os.environ, {"TUI_PLAIN": "1"}):
            assert LiveStatusBar.supported(_TtyStream()) is False

    def test_false_on_non_posix(self):
        with patch.object(os, "name", "nt"):
            assert LiveStatusBar.supported(_TtyStream()) is False


class TestRenderSequence:
    """覆写序列：回车归位 + 清行 + 本帧正文。"""

    def test_update_clears_line_then_writes(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("第一帧")
        assert stream.getvalue() == _CLEAR + "  第一帧"

    def test_repeated_update_keeps_single_line(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("第一帧")
        bar.update("第二帧")
        assert "\n" not in stream.getvalue()
        assert stream.getvalue().endswith("第二帧")

    def test_narrow_terminal_truncates(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        with patch("src.python.tui.live_status.terminal_columns", return_value=40):
            bar.update(status_bar_text("一个非常非常长的阶段名称用于触发截断"))
        line = stream.getvalue().split(_CLEAR)[-1]
        assert "\n" not in line
        assert display_width(line) <= 40


class TestSuspendResume:
    """落地行穿插：清条 → 打印 → 重画。"""

    def test_suspend_clears_and_resume_redraws_last(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("阶段一")
        bar.suspend()
        assert stream.getvalue().endswith(_CLEAR)
        bar.resume()
        assert stream.getvalue().endswith("阶段一")

    def test_resume_without_frames_is_noop(self):
        stream = _TtyStream()
        LiveStatusBar(stream).resume()
        assert stream.getvalue() == ""

    def test_close_clears_and_stops_output(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("阶段一")
        bar.close()
        before = stream.getvalue()
        bar.update("阶段二")
        assert stream.getvalue() == before, "关闭后不得再有状态条输出"

    def test_suspend_twice_clears_once(self):
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("阶段一")
        bar.suspend()
        bar.suspend()
        assert stream.getvalue().count(_CLEAR) == 2  # 一次 update + 一次 suspend


class TestReporterLiveWiring:
    """报告器接线：非 TTY 下 live=True 与不启用时逐行输出一致（管道等价前提）。"""

    def test_non_tty_output_identical_to_plain_mode(self, capsys):
        from src.python.report.progress import TuiProgressReporter

        plain = TuiProgressReporter()
        plain.info("正在获取行情")
        plain.ok("行情获取完成")
        plain.warn("部分源不可达")
        baseline = capsys.readouterr().out

        live = TuiProgressReporter(live=True)
        try:
            live.info("正在获取行情")
            live.ok("行情获取完成")
            live.warn("部分源不可达")
        finally:
            live.close()
        actual = capsys.readouterr().out
        assert actual == baseline, "非 TTY 下启用状态条不得改变输出"
        assert "\r" not in actual

    def test_close_is_idempotent(self):
        """收尾与异常路径都可能调 close：重复调用不抛错。"""
        from src.python.report.progress import TuiProgressReporter

        reporter = TuiProgressReporter(live=True)
        reporter.close()
        reporter.close()
        assert reporter._bar is None
