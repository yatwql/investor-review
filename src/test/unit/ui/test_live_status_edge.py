# -*- coding: utf-8 -*-
"""长任务状态条边缘：心跳线程生命周期与中止键轮询的容错（`@pytest.mark.edge`）。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.python.core.cancel import CancelToken

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui, pytest.mark.edge]


class _FakePerf:
    """最小 perf 替身：恒有活跃阶段。"""

    report_type = "basic"

    def stage_status(self) -> dict:
        return {"phase": "行情获取", "elapsed": 1.0}


def _live_reporter(token: CancelToken):
    """在「伪 TTY + 可轮询」条件下构造启用状态条的报告器（心跳节拍压到毫秒级）。"""
    from src.python.report.progress import TuiProgressReporter
    from src.python.tui import live_status

    watcher = MagicMock()
    watcher.open.return_value = True
    watcher.poll.return_value = "q"
    patcher = [
        patch.object(live_status.LiveStatusBar, "supported", return_value=True),
        patch.object(live_status.KeyWatcher, "supported", return_value=True),
        patch.object(live_status, "KeyWatcher", return_value=watcher),
        patch("src.python.report.progress._HEARTBEAT_SECONDS", 0.01),
    ]
    for p in patcher:
        p.start()
    reporter = TuiProgressReporter(live=True, cancel_token=token)
    return reporter, patcher, watcher


class TestHeartbeatLifecycle:
    def test_q_key_sets_cancel_token(self):
        """心跳轮询到 `q` 即置位令牌（有序中止的触发点）。"""
        token = CancelToken("用户取消")
        reporter, patchers, _watcher = _live_reporter(token)
        try:
            reporter.stage_progress(_FakePerf())
            deadline = time.monotonic() + 2.0
            while not token.cancelled and time.monotonic() < deadline:
                time.sleep(0.01)
            assert token.cancelled is True
            assert reporter.cancel_token is token
        finally:
            reporter.close()
            for p in patchers:
                p.stop()

    def test_thread_stops_after_close(self):
        """close 后心跳线程结束（不留后台线程）。"""
        token = CancelToken("用户取消")
        reporter, patchers, _watcher = _live_reporter(token)
        try:
            reporter.stage_progress(_FakePerf())
            ticker = reporter._ticker
            assert ticker is not None and ticker.is_alive()
            reporter.close()
            assert not ticker.is_alive(), "close 后心跳线程必须退出"
        finally:
            for p in patchers:
                p.stop()

    def test_poll_error_does_not_break_generation(self):
        """轮询抛错被吞掉：状态条/中止键的问题不得影响生成流程。"""
        token = CancelToken("用户取消")
        reporter, patchers, watcher = _live_reporter(token)
        watcher.poll.side_effect = OSError("读终端失败")
        try:
            reporter.stage_progress(_FakePerf())
            time.sleep(0.05)
            assert token.cancelled is False
        finally:
            reporter.close()
            for p in patchers:
                p.stop()
