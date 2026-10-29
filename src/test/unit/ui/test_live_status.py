# -*- coding: utf-8 -*-
"""长任务状态条（`tui/live_status.py`）：正文拼装、环境判据、覆写与挂起/恢复序列。

状态条只允许在 TTY 上出现，且必须能被落地行安全打断（suspend/resume）——这两条
是「不出现鬼影行」与「管道输出逐字节不变」的关键前提。
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
    """正文拼装（阶段 / 已耗时 / ETA / 中止键）。"""

    def test_includes_eta_when_available(self):
        text = status_bar_text("行情获取", 12.4, 40.2)
        assert "「行情获取」" in text
        assert "已耗时 12s" in text
        assert "预计剩余 ~40s" in text
        assert "q 中止" in text

    def test_omits_eta_when_unknown(self):
        """历史样本不足时只报已耗时（不显示凭空的剩余时间）。"""
        text = status_bar_text("行情获取", 8.0, None)
        assert "预计剩余" not in text

    def test_omits_cancel_hint_when_unavailable(self):
        """环境无法按键中止时不留一个按不了的键提示。"""
        assert "中止" not in status_bar_text("行情获取", 1.0, None, cancel_hint="")


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
        """连续刷新不产生换行（状态条始终占一行）。"""
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        bar.update("第一帧")
        bar.update("第二帧")
        assert "\n" not in stream.getvalue()
        assert stream.getvalue().endswith("第二帧")

    def test_narrow_terminal_truncates(self):
        """窄屏按列宽截断，不硬折成两行。"""
        stream = _TtyStream()
        bar = LiveStatusBar(stream)
        with patch("src.python.tui.live_status.terminal_columns", return_value=40):
            bar.update(status_bar_text("一个非常非常长的阶段名称用于触发截断", 12.0, 40.0))
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
        """重复挂起不重复清行（避免清到上一行内容）。"""
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
        """收尾与异常路径都可能调 close：重复调用不得抛错、不得再输出。"""
        from src.python.report.progress import TuiProgressReporter

        reporter = TuiProgressReporter(live=True)
        reporter.close()
        reporter.close()
        assert reporter._bar is None and reporter._watcher is None, "close 后状态条与轮询器都已释放"


class TestWatcherInstance:
    """D1 回归：状态条保留的轮询器必须是**已 open** 的实例（否则 cbreak 没生效，q 不响应）。"""

    def test_opened_instance_is_the_retained_one(self, monkeypatch):
        opened: list[object] = []

        class _FakeWatcher:
            def open(self) -> bool:
                opened.append(self)
                return True

            def poll(self) -> str:
                return ""

            def close(self) -> None:
                pass

        monkeypatch.setattr("src.python.tui.live_status.LiveStatusBar.supported", lambda *a, **k: True)
        monkeypatch.setattr("src.python.tui.live_status.KeyWatcher", _FakeWatcher)
        monkeypatch.setattr(
            "src.python.tui.live_status.KeyWatcher.supported", staticmethod(lambda *a, **k: True), raising=False
        )

        from src.python.core.cancel import CancelToken
        from src.python.report.progress import TuiProgressReporter

        reporter = TuiProgressReporter(live=True, cancel_token=CancelToken("用户取消"))
        try:
            assert len(opened) == 1, f"open() 应只调用一次，实际 {len(opened)}"
            assert reporter._watcher is opened[0], "保留的实例必须就是已 open 的那个"
        finally:
            reporter.close()

    def test_unopenable_watcher_degrades_hint(self, monkeypatch):
        """切不了 cbreak → 不给中止键，状态条提示降级为 Ctrl+C。"""

        class _FakeWatcher:
            def open(self) -> bool:
                return False

            def close(self) -> None:
                pass

        monkeypatch.setattr("src.python.tui.live_status.LiveStatusBar.supported", lambda *a, **k: True)
        monkeypatch.setattr("src.python.tui.live_status.KeyWatcher", _FakeWatcher)
        monkeypatch.setattr(
            "src.python.tui.live_status.KeyWatcher.supported", staticmethod(lambda *a, **k: True), raising=False
        )

        from src.python.core.cancel import CancelToken
        from src.python.report.progress import TuiProgressReporter

        reporter = TuiProgressReporter(live=True, cancel_token=CancelToken("用户取消"))
        try:
            assert reporter._watcher is None
            assert "Ctrl+C" in reporter._bar.cancel_hint
        finally:
            reporter.close()


class TestEtaCaching:
    """ETA 估算按阶段缓存：心跳每 5s 排队时不重复读 perf_history。"""

    def test_estimate_called_once_per_phase(self, monkeypatch):
        from unittest.mock import patch as _patch

        from src.python.report.progress import TuiProgressReporter

        class _Perf:
            report_type = "full"

            def __init__(self):
                self.elapsed = 1.0

            def stage_status(self):
                return {"phase": "行情获取", "elapsed": self.elapsed}

        perf = _Perf()
        sink = _TtyStream()
        reporter = TuiProgressReporter()
        reporter._bar = LiveStatusBar(sink)
        reporter._last_perf = perf
        with _patch("src.python.core.perf.estimate_stage_eta", return_value=30.0) as estimate:
            reporter._draw()
            perf.elapsed = 6.0
            reporter._draw()
            perf.elapsed = 12.0
            reporter._draw()
        assert estimate.call_count == 1, "同一阶段只估一次（其余帧用缓存的预计完成时刻推算）"
        assert "预计剩余" in sink.getvalue(), "ETA 仍随已耗时递减显示"
