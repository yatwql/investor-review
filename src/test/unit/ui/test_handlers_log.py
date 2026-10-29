"""TUI 日志/健康历史查看命令处理器单元测试。

覆盖 `tui/handlers_log.py`：
  - _cmd_view_logs — 输出渲染 / 级别提示透传 / traceback 折叠 / 空结果 / 异常兜底
  - _cmd_view_health_history — 摘要输出 / 空结果 / 异常兜底

长输出统一交 `pager.view` 承载（分页或整段直打由分页器按环境决定），故断言分开两层：
「渲染出的行内容」看传给 pager 的形参，「短反馈 / 错误」看直接上屏文本。

数据源健康历史（data/state/datasource_health.jsonl）已被 conftest 隔离，
测试统一 mock 核心层函数，不触真实状态文件。
"""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

import pytest

from src.python.core.log_reader import LogEntry
from src.python.tui.handlers_log import _cmd_view_health_history, _cmd_view_logs

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _view_args(mock_view) -> tuple[str, str]:
    """取分页器实参并拼回可断言的（标题, 正文）。"""
    title, lines = mock_view.call_args.args[0], mock_view.call_args.args[1]
    return title, "\n".join(lines)


class TestCmdViewLogs(unittest.TestCase):
    """_cmd_view_logs 日志查看。"""

    def _run(self, level_input: str = "") -> tuple[str, str, str]:
        """执行命令并捕获输出（mock 输入与分页器，返回上屏文本 / 标题 / 正文）。"""
        out = io.StringIO()
        with (
            patch("sys.stdout", out),
            patch("src.python.tui.handlers_log.input_choice", return_value=level_input),
            patch("src.python.tui.pager.view") as mock_view,
        ):
            _cmd_view_logs()
        if mock_view.called:
            title, body = _view_args(mock_view)
            return out.getvalue(), title, body
        return out.getvalue(), "", ""

    def test_output_entries(self):
        """有日志时条目进分页视图，traceback 折叠为提示行。"""
        entries = [
            LogEntry(time="2026-08-16 10:00:00,123", level="INFO", message="应用启动", body="应用启动"),
            LogEntry(
                time="2026-08-16 10:00:01,456",
                level="ERROR",
                message="读取行情失败",
                body="读取行情失败\n  堆栈行1\n  堆栈行2",
            ),
        ]
        with patch("src.python.core.log_reader.read_log", return_value=entries):
            _out, title, body = self._run()
        self.assertIn("最近日志（级别: 全部）", title)
        self.assertIn("应用启动", body)
        self.assertIn("读取行情失败", body)
        self.assertIn("⤷ 堆栈详情 +2 行", body)

    def test_level_filter_passthrough(self):
        """级别提示输入 ERROR → read_log(level="ERROR")。"""
        with (
            patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read,
            patch("src.python.tui.handlers_log.input_choice", return_value="ERROR"),
            patch("src.python.tui.pager.view"),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            _cmd_view_logs()
        self.assertEqual(mock_read.call_args.kwargs["level"], "ERROR")

    def test_empty_level_means_all(self):
        """空回车 → level=None（全部）。"""
        with (
            patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read,
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.tui.pager.view"),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            _cmd_view_logs()
        self.assertIsNone(mock_read.call_args.kwargs["level"])

    def test_invalid_level_shows_all(self):
        """无效级别 → 提示并将 level 置 None（显示全部）。"""
        with (
            patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read,
            patch("src.python.tui.handlers_log.input_choice", return_value="VERBOSE"),
            patch("src.python.tui.pager.view"),
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            _cmd_view_logs()
        self.assertIsNone(mock_read.call_args.kwargs["level"])
        self.assertIn("无效级别", mock_out.getvalue())

    def test_no_match(self):
        """无匹配条目：直接给一行提示，不进分页视图。"""
        with (
            patch("src.python.core.log_reader.read_log", return_value=[]),
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.tui.pager.view") as mock_view,
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            _cmd_view_logs()
        self.assertIn("无匹配日志条目", mock_out.getvalue())
        mock_view.assert_not_called()

    def test_exception_fallback(self):
        """read_log 抛异常 → [ERR] 提示且不崩溃，不进分页视图。"""
        with (
            patch("src.python.core.log_reader.read_log", side_effect=OSError("IO error")),
            patch("src.python.tui.handlers_log.input_choice", return_value=""),
            patch("src.python.tui.pager.view") as mock_view,
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            _cmd_view_logs()
        self.assertIn("[ERR]", mock_out.getvalue())
        mock_view.assert_not_called()


class TestCmdViewHealthHistory(unittest.TestCase):
    """_cmd_view_health_history 健康历史查看。"""

    def test_output_summaries(self):
        """有摘要时输出时间线（ok/total 与失败源）。"""
        summaries = [
            {
                "timestamp": "2026-08-16T10:00:00",
                "report_type": "basic",
                "holdings_count": 3,
                "total": 10,
                "ok_count": 8,
                "fail_count": 2,
                "failed_sources": ["腾讯K线", "财联社"],
            }
        ]
        with (
            patch("src.python.core.perf.summarize_health_history", return_value=summaries),
            patch("src.python.tui.pager.view") as mock_view,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            _cmd_view_health_history()
        title, body = _view_args(mock_view)
        self.assertIn("数据源健康历史", title)
        self.assertIn("2026-08-16 10:00:00", body)
        self.assertIn("8/10", body)
        self.assertIn("腾讯K线", body)

    def test_empty(self):
        """无历史记录：一行提示，不进分页视图。"""
        with (
            patch("src.python.core.perf.summarize_health_history", return_value=[]),
            patch("src.python.tui.pager.view") as mock_view,
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            _cmd_view_health_history()
        self.assertIn("暂无数据源健康历史记录", mock_out.getvalue())
        mock_view.assert_not_called()

    def test_exception_fallback(self):
        """异常 → [ERR] 提示且不崩溃，不进分页视图。"""
        with (
            patch("src.python.core.perf.summarize_health_history", side_effect=OSError("IO error")),
            patch("src.python.tui.pager.view") as mock_view,
            patch("sys.stdout", new_callable=io.StringIO) as mock_out,
        ):
            _cmd_view_health_history()
        self.assertIn("[ERR]", mock_out.getvalue())
        mock_view.assert_not_called()


class TestPromptEscCancel(unittest.TestCase):
    """提示处 Esc 统一取消（PromptCancelledError）：级别筛选 / 自检联网询问。"""

    def test_level_prompt_esc_cancels(self):
        """级别筛选处按 Esc → 取消查看（而非视为全部级别继续）。"""
        from src.python.tui.handlers_log import PromptCancelledError, _level_prompt

        with (
            patch("src.python.tui.handlers_log.input_choice", return_value=None),
            pytest.raises(PromptCancelledError),
        ):
            _level_prompt()

    def test_doctor_network_prompt_esc_cancels(self):
        """自检联网询问处按 Esc → 中止自检（而非仅本地继续）。"""
        from src.python.tui.handlers_log import PromptCancelledError, _cmd_run_doctor

        with (
            patch("src.python.tui.handlers_log.input_choice", return_value=None),
            pytest.raises(PromptCancelledError),
        ):
            _cmd_run_doctor()
