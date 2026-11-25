"""TUI 长任务状态条的接线（`tui/progress`）：启用条件 / 绘制 / 落地行挂起恢复。

状态条只在 TTY 生效，且**任何绘制失败都不得影响输出**——它是纯装饰，一旦抛异常就会
把整份报告的进度流打断。本文件用桩状态条锁这些接线点，不碰真实终端。
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest

from src.python.tui.progress import TuiProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class _StubBar:
    """桩状态条：记录 update/suspend/resume/close 的调用顺序。"""

    cancel_hint = "Ctrl+C 中断"

    def __init__(self, recorder: list[str]) -> None:
        self._recorder = recorder

    def update(self, text: str) -> None:
        self._recorder.append(f"update:{text}")

    def suspend(self) -> None:
        self._recorder.append("suspend")

    def resume(self) -> None:
        self._recorder.append("resume")

    def close(self) -> None:
        self._recorder.append("close")


class _StubPerf:
    def __init__(self, stage: dict | None, *, raise_on_call: bool = False) -> None:
        self._stage = stage
        self._raise = raise_on_call

    def stage_status(self):
        if self._raise:
            raise RuntimeError("probe fault")
        return self._stage


def _reporter(recorder: list[str]) -> TuiProgressReporter:
    """构造已挂上桩状态条的 reporter（绕开 TTY 探测）。"""
    reporter = TuiProgressReporter()
    reporter._bar = _StubBar(recorder)
    return reporter


class TestLiveStatusEnablement:
    def test_not_started_when_unsupported(self):
        with patch("src.python.tui.live_status.LiveStatusBar.supported", return_value=False):
            reporter = TuiProgressReporter(live=True)

        assert reporter._bar is None, "非 TTY 下不得创建状态条"

    def test_started_when_supported(self):
        recorder: list[str] = []
        with (
            patch("src.python.tui.live_status.LiveStatusBar.supported", return_value=True),
            patch("src.python.tui.live_status.LiveStatusBar", return_value=_StubBar(recorder)),
        ):
            reporter = TuiProgressReporter(live=True)

        assert reporter._bar is not None, "TTY 下应启用状态条"

    def test_default_is_no_bar(self):
        assert TuiProgressReporter()._bar is None


class TestDraw:
    def test_no_op_without_bar(self):
        reporter = TuiProgressReporter()
        reporter._last_perf = _StubPerf({"phase": "行情"})

        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter._draw()

        assert out.getvalue() == "", "无状态条时不得自行打印（落地行由 _emit 负责）"

    def test_no_op_without_perf(self):
        recorder: list[str] = []
        _reporter(recorder)._draw()

        assert recorder == []

    def test_no_op_when_stage_idle(self):
        """无活跃阶段（阶段已结束）→ 不刷新，避免状态条停在上一阶段文案。"""
        recorder: list[str] = []
        reporter = _reporter(recorder)
        reporter.stage_progress(_StubPerf(None))

        assert recorder == []

    def test_updates_with_phase_and_cancel_hint(self):
        recorder: list[str] = []
        reporter = _reporter(recorder)

        reporter.stage_progress(_StubPerf({"phase": "估值计算"}))

        assert len(recorder) == 1
        assert recorder[0].startswith("update:")
        assert "估值计算" in recorder[0]
        assert "Ctrl+C 中断" in recorder[0], "状态条须写明中断方式"

    def test_draw_failure_is_swallowed(self):
        """状态条绘制抛异常 → 只留 DEBUG，不打断进度流。"""
        recorder: list[str] = []
        reporter = _reporter(recorder)

        reporter.stage_progress(_StubPerf(None, raise_on_call=True))

        assert recorder == []
        assert reporter._bar is not None, "单帧失败不得丢弃状态条"


class TestStageProgressFallback:
    def test_without_bar_delegates_to_base(self):
        """未启用状态条时走基类逐行输出（行为与未启用前一致）。"""
        reporter = TuiProgressReporter()
        with patch("src.python.report.progress.AnnouncingProgressReporter.stage_progress") as base:
            reporter.stage_progress(_StubPerf({"phase": "行情"}))

        base.assert_called_once()
        assert reporter._last_perf is None, "无状态条时不记录 perf"


class TestEmitAndClose:
    def test_landing_line_suspends_and_resumes(self):
        recorder: list[str] = []
        reporter = _reporter(recorder)
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter.ok("报告已生成")

        assert recorder == ["suspend", "resume"], "落地行打印前后须挂起/恢复状态条"
        assert "[OK]" in out.getvalue()

    def test_emit_without_bar_prints_directly(self):
        reporter = TuiProgressReporter()
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter.warn("部分缺失")

        assert "[!]" in out.getvalue()

    def test_close_is_idempotent(self):
        recorder: list[str] = []
        reporter = _reporter(recorder)

        reporter.close()
        reporter.close()

        assert recorder == ["close"], "重复收尾只关一次"
        assert reporter._bar is None


class TestErrorChannel:
    def test_error_prefix(self):
        reporter = TuiProgressReporter()
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter.error("板块取数失败")

        assert "[ERR]" in out.getvalue()

    def test_add_error_and_get_errors(self):
        reporter = TuiProgressReporter()
        reporter.add_error("第一个问题")
        reporter.add_error("第二个问题")

        errors = reporter.get_errors()

        assert errors == ["第一个问题", "第二个问题"]
        assert errors is not reporter._errors, "返回副本，调用方改动不得污染 reporter"

    def test_print_error_summary_empty_is_noop(self):
        reporter = TuiProgressReporter()
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter.print_error_summary()

        assert out.getvalue() == ""

    def test_print_error_summary_prints_and_clears(self):
        reporter = TuiProgressReporter()
        reporter.add_error("板块取数失败")
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            reporter.print_error_summary()

        captured = out.getvalue()
        assert "以下模块遇到问题" in captured
        assert "板块取数失败" in captured
        assert reporter.get_errors() == [], "汇总后须清空，避免下一轮重复播报"
