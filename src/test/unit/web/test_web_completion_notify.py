"""Web 生成收尾完成通知 — 单元测试。

覆盖 `_notify_web_completion`（门控前置 / 载荷构造 / 尽力而为契约）与
`_run_generation` 收尾接线（执行体委托 + 通知派发）；通知原语本体
（should_notify / build_completion_event / 分发器）由
`unit/core/test_completion_notify.py` 覆盖，此处只验渠道层接线。

运行：
  pytest src/test/unit/web/test_web_completion_notify.py -v
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.python.core.completion_notify import LATEST_HTML_NAME, LATEST_XLSX_NAME
from src.python.web.handlers import _notify_web_completion, _run_generation
from src.python.web.runs import RunState

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]


def _state(errors=None, output_dir=None):
    state = RunState("r-notify", {"report_type": "basic"})
    state.errors = list(errors or [])
    if output_dir is not None:
        state.output_dir = output_dir
    return state


class TestNotifyWebCompletion:
    """_notify_web_completion：Web 手动生成/定时调度共用收尾通知。"""

    def test_unconfigured_gate_skips_without_tracker_access(self):
        """未配置任何通道 → 不构造事件、不碰降级跟踪器（门控前置契约）。"""
        with (
            patch("src.python.config.get_config", return_value={"notify": {}}),
            patch("src.python.core.completion_notify.build_completion_event") as mock_build,
            patch("src.python.report.data_status.degradation_summary") as mock_degr,
        ):
            _notify_web_completion(_state(), {"report_type": "basic"}, 0, None)

        mock_build.assert_not_called()
        mock_degr.assert_not_called()

    def test_partial_failure_dispatches_with_artifacts(self):
        """部分失败（exit 1）→ 必发（不受 on_success 影响），载荷含产物路径与错误明细。"""
        cfg = {
            "notify": {"webhook_url": "http://example.invalid/hook", "on_success": False},
            "output_dir": "reports",
        }
        state = _state(errors=["某模块失败"])
        result = MagicMock(excel_ok=True, html_ok=True)
        with (
            patch("src.python.config.get_config", return_value=cfg),
            patch("src.python.report.data_status.degradation_summary", return_value=["tencent: timeout（累计5次）"]),
            patch("src.python.core.completion_notify.dispatch_completion_notification") as mock_dispatch,
        ):
            _notify_web_completion(state, {"report_type": "basic"}, 1, result)

        mock_dispatch.assert_called_once()
        event, notify_cfg = mock_dispatch.call_args.args
        assert notify_cfg == cfg["notify"]
        assert event["exit_code"] == 1
        assert event["ok"] is False
        assert event["report_type"] == "basic"
        assert event["errors"] == ["某模块失败"]
        assert event["degradations"] == ["tencent: timeout（累计5次）"]
        assert any(LATEST_XLSX_NAME in p for p in event["artifacts"])
        assert any(LATEST_HTML_NAME in p for p in event["artifacts"])

    def test_severe_failure_no_result_lists_no_artifacts(self):
        """严重失败（无 result）→ 产物标志全 False，事件不列产物路径。"""
        cfg = {"notify": {"webhook_url": "http://example.invalid/hook"}, "output_dir": "reports"}
        with (
            patch("src.python.config.get_config", return_value=cfg),
            patch("src.python.report.data_status.degradation_summary", return_value=[]),
            patch("src.python.core.completion_notify.dispatch_completion_notification") as mock_dispatch,
        ):
            _notify_web_completion(_state(errors=["上传文件已过期"]), {"report_type": "both"}, 2, None)

        event = mock_dispatch.call_args.args[0]
        assert event["artifacts"] == []
        assert event["exit_code"] == 2

    def test_dispatch_exception_swallowed(self):
        """分发内部异常 → 吞掉只记 DEBUG（尽力而为，不改变退出码语义）。"""
        cfg = {"notify": {"webhook_url": "http://example.invalid/hook"}, "output_dir": "reports"}
        with (
            patch("src.python.config.get_config", return_value=cfg),
            patch("src.python.report.data_status.degradation_summary", return_value=[]),
            patch(
                "src.python.core.completion_notify.dispatch_completion_notification",
                side_effect=RuntimeError("boom"),
            ),
            patch("src.python.web.handlers.logger.debug") as mock_log,
        ):
            # 不抛出即通过（异常若上抛会改变 run 状态机），且必须留 DEBUG 痕迹
            _notify_web_completion(_state(), {"report_type": "basic"}, 2, None)

        mock_log.assert_called_once()
        assert "完成通知" in str(mock_log.call_args.args)

    def test_output_dir_falls_back_to_config_when_state_unset(self):
        """state.output_dir 未置（早期路径）→ 产物路径基于配置 output_dir 绝对化。"""
        cfg = {
            "notify": {"webhook_url": "http://example.invalid/hook", "on_success": True},
            "output_dir": "custom_dir",
        }
        state = _state()
        state.output_dir = None
        result = MagicMock(excel_ok=True, html_ok=False)
        with (
            patch("src.python.config.get_config", return_value=cfg),
            patch("src.python.report.data_status.degradation_summary", return_value=[]),
            patch("src.python.core.completion_notify.dispatch_completion_notification") as mock_dispatch,
        ):
            _notify_web_completion(state, {"report_type": "basic"}, 0, result)

        event = mock_dispatch.call_args.args[0]
        assert len(event["artifacts"]) == 1
        assert event["artifacts"][0].endswith(os.path.join("custom_dir", LATEST_XLSX_NAME))


class TestRunGenerationNotifyWiring:
    """_run_generation 包装器：委托执行体 + 收尾通知派发。"""

    @patch("src.python.web.handlers._notify_web_completion")
    @patch("src.python.web.handlers._run_generation_impl")
    def test_delegates_and_notifies_with_result(self, mock_impl, mock_notify):
        """执行体 result 经 result_box 回传给通知（excel_ok/html_ok 载荷来源）。"""
        state = _state()
        params = {"report_type": "both"}
        fake_result = MagicMock(excel_ok=True, html_ok=False)

        def _impl(state_arg, params_arg, result_box):
            result_box["result"] = fake_result
            return 1

        mock_impl.side_effect = _impl

        code = _run_generation(state, params)

        assert code == 1
        mock_impl.assert_called_once()
        mock_notify.assert_called_once_with(state, params, 1, fake_result)

    @patch("src.python.web.handlers._notify_web_completion")
    @patch("src.python.web.handlers._run_generation_impl", return_value=2)
    def test_severe_path_still_notifies(self, mock_impl, mock_notify):
        """早期严重失败（无 result）→ 通知仍派发（无人值守失败提醒是核心价值）。"""
        state = _state()
        params = {"file_id": "gone", "report_type": "basic"}

        code = _run_generation(state, params)

        assert code == 2
        mock_notify.assert_called_once_with(state, params, 2, None)
