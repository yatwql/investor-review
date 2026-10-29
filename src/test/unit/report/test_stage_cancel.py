# -*- coding: utf-8 -*-
"""阶段边界协作式取消（`core/cancel.py` + `PerfCollector.start` + 编排层收口）。

三条口径：
  - 令牌未置位时对生成零影响（默认路径不感知取消）；
  - 置位后**只在阶段边界**生效（不在阶段中途硬切，已完成产物与缓存保留）；
  - 编排入口把取消收口成正常结果对象（渠道层不必区分取消与失败）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.core.cancel import CancelToken, StageCancelled
from src.python.core.perf import PerfCollector
from src.python.report.progress import SilentProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestCancelToken:
    """令牌语义：幂等置位、首个原因不被覆盖、可复位。"""

    def test_cancel_is_idempotent_and_keeps_first_reason(self):
        token = CancelToken("用户取消")
        token.cancel("用户按 q")
        token.cancel("第二次")
        assert token.cancelled is True
        assert token.reason == "用户按 q"

    def test_reset_allows_reuse(self):
        token = CancelToken("用户取消")
        token.cancel()
        token.reset()
        assert token.cancelled is False


class TestPerfStageBoundary:
    """取消只在 `PerfCollector.start` 处生效。"""

    def test_no_token_never_raises(self):
        perf = PerfCollector(report_type="basic", holdings=[])
        perf.start("阶段一")
        perf.stop()
        perf.start("阶段二")
        status = perf.stage_status()
        assert status is not None and status["phase"] == "阶段二"
        perf.stop()

    def test_cancel_raises_at_next_stage_start(self):
        token = CancelToken("用户取消")
        token.cancel("用户按 q")
        perf = PerfCollector(report_type="basic", holdings=[], cancel_token=token)
        with pytest.raises(StageCancelled) as excinfo:
            perf.start("阶段一")
        assert "用户按 q" in str(excinfo.value)

    def test_cancel_waits_for_boundary_not_mid_stage(self):
        """进行中的阶段不被中断：置位后本阶段可正常 stop，下一次 start 才抛。"""
        token = CancelToken("用户取消")
        perf = PerfCollector(report_type="basic", holdings=[], cancel_token=token)
        perf.start("阶段一")
        token.cancel()
        assert perf.stop() is not None, "阶段进行中不受取消影响"
        with pytest.raises(StageCancelled):
            perf.start("阶段二")


class TestOrchestratorCancelHandling:
    """编排入口把取消收口成正常结果并保留中断收口。"""

    def test_cancel_returns_result_and_calls_interruption(self, tmp_path):
        from src.python.report import orchestrator, run_integrity

        reporter = SilentProgressReporter()
        with (
            patch.object(orchestrator, "_generate_report_impl", side_effect=StageCancelled("用户取消")),
            patch.object(run_integrity, "begin_run"),
            patch.object(run_integrity, "clear_run"),
            # 收口函数在 orchestrator 导入时绑定，patch 须指向调用点所在模块
            patch.object(orchestrator, "handle_interruption") as handle,
        ):
            result = orchestrator.generate_report([], {}, reporter, output_dir=str(tmp_path))
        handle.assert_called_once()
        assert result.report_generated is False, "取消不得标记为已生成"

    def test_failure_other_than_cancel_propagates(self, tmp_path):
        """非取消异常不被吞：仍按既有异常路径传播。"""
        from src.python.report import orchestrator, run_integrity

        with (
            patch.object(orchestrator, "_generate_report_impl", side_effect=ValueError("坏数据")),
            patch.object(run_integrity, "begin_run"),
            patch.object(run_integrity, "clear_run"),
        ):
            with pytest.raises(ValueError):
                orchestrator.generate_report([], {}, SilentProgressReporter(), output_dir=str(tmp_path))


class TestTokenOf:
    """``token_of``：替身报告器不得被当成「永远已取消」。"""

    def test_mock_reporter_yields_no_token(self):
        from unittest.mock import MagicMock

        from src.python.core.cancel import token_of

        assert token_of(MagicMock()) is None, "MagicMock 的 cancel_token 属性存在且为真，必须被过滤"

    def test_real_token_is_returned(self):
        from src.python.core.cancel import token_of

        class _Reporter:
            cancel_token = CancelToken("用户取消")

        assert isinstance(token_of(_Reporter()), CancelToken)

    def test_plain_object_yields_no_token(self):
        from src.python.core.cancel import token_of

        assert token_of(object()) is None
