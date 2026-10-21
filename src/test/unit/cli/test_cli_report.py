"""test_cli 兄弟分片（report）：报告生成子命令与进度通道。"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.python.cli import (
    _EXIT_SEVERE,
    _cli_read_holdings,
    _cli_read_holdings_with_flows,
    _handle_report,
)
from src.python.cli._handlers import _collect_degradation_summary

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


@pytest.mark.unit
class TestCliProgressReporter:
    """CliProgressReporter 行为测试。"""

    def test_info_logging(self, caplog):
        """非 verbose 模式：info 写入日志。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)  # DEBUG
        r = CliProgressReporter(verbose=False)
        r.info("测试信息")
        assert "测试信息" in caplog.text

    def test_ok_logging(self, caplog):
        """非 verbose 模式：ok 写入日志。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter(verbose=False)
        r.ok("成功")
        assert "成功" in caplog.text

    def test_warn_logging(self, caplog):
        """非 verbose 模式：warn 写入日志。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter(verbose=False)
        r.warn("警告")
        # WARNING 级别
        assert "警告" in caplog.text
        assert any(r.levelname == "WARNING" for r in caplog.records if "警告" in r.message)

    def test_error_logging(self, caplog):
        """非 verbose 模式：error 写入日志。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter(verbose=False)
        r.error("错误")
        assert "错误" in caplog.text

    def test_verbose_stderr(self, capsys):
        """verbose 模式：消息同步到 stderr 带 [..]/[OK] 前缀。"""
        from src.python.report.cli_progress import CliProgressReporter

        r = CliProgressReporter(verbose=True)
        r.info("进度消息")
        r.ok("成功消息")
        stderr = capsys.readouterr().err
        assert "[..]" in stderr
        assert "[OK]" in stderr
        assert "进度消息" in stderr
        assert "成功消息" in stderr

    def test_non_verbose_no_stderr(self, capsys):
        """非 verbose 模式：stderr 无输出。"""
        from src.python.report.cli_progress import CliProgressReporter

        r = CliProgressReporter(verbose=False)
        r.info("不应出现")
        r.ok("也不应出现")
        stderr = capsys.readouterr().err
        assert stderr == ""

    def test_call_sheet_success(self, capsys, caplog):
        """call_sheet 成功时 verbose 模式输出开始/完成。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter(verbose=True)
        fn = MagicMock(return_value=True)
        result = r.call_sheet("测试页", fn)
        assert result is True
        fn.assert_called_once()
        stderr = capsys.readouterr().err
        assert "测试页" in stderr

    def test_call_sheet_fn_none(self):
        """call_sheet 函数为 None 时返回 False。"""
        from src.python.report.cli_progress import CliProgressReporter

        r = CliProgressReporter()
        result = r.call_sheet("缺失模块", None)
        assert result is False
        assert len(r.get_errors()) == 1

    def test_call_sheet_exception(self):
        """call_sheet 函数抛出异常时返回 False。"""
        from src.python.report.cli_progress import CliProgressReporter

        def _broken():
            raise ValueError("测试异常")

        r = CliProgressReporter()
        result = r.call_sheet("异常页", _broken)
        assert result is False

    def test_add_error(self):
        """add_error 记录非致命错误。"""
        from src.python.report.cli_progress import CliProgressReporter

        r = CliProgressReporter()
        r.add_error("测试错误")
        assert "测试错误" in r.get_errors()

    def test_print_timing_summary_empty(self, caplog):
        """无耗时记录时 print_timing_summary 不输出。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter()
        r.print_timing_summary()
        # 不应有耗时相关日志
        assert not any("耗时" in r.message for r in caplog.records)

    def test_print_timing_summary_with_records(self, caplog):
        """有耗时记录时输出排行。"""
        from src.python.report.cli_progress import CliProgressReporter

        caplog.set_level(10)
        r = CliProgressReporter()
        r._timing_records.append(("测试模块", 1.5))
        r.print_timing_summary()
        assert any("测试模块" in r.message for r in caplog.records)
        assert any("耗时" in r.message for r in caplog.records)


@pytest.mark.unit
class TestCliReadHoldings:
    """_cli_read_holdings 行为测试。"""

    def test_file_not_found(self, caplog):
        """文件不存在时返回 None + ERROR 日志。"""
        caplog.set_level(10)
        config = {"holdings_dir": "/nonexistent", "holdings_filename": "test.xlsx"}
        result = _cli_read_holdings(config)
        assert result is None
        assert any("持仓文件不存在" in r.message for r in caplog.records if r.levelname == "ERROR")


@pytest.mark.unit
class TestCliReadHoldingsWithFlows:
    """_cli_read_holdings_with_flows 行为测试（含交易/分红流水页签）。"""

    def test_returns_holdings_and_flows(self):
        """有流水页签时返回 (holdings, transactions, dividends) 三元组。"""
        mock_parsed = MagicMock()
        mock_parsed.holdings = [MagicMock(), MagicMock()]
        mock_parsed.transactions = [MagicMock()]
        mock_parsed.dividends = [MagicMock()]
        with (
            patch("src.python.cli._handlers._cli_resolve_holdings_file", return_value="/tmp/h.xlsx"),
            patch("src.python.core.reader.read_holdings_with_flows", return_value=mock_parsed),
        ):
            result = _cli_read_holdings_with_flows({"holdings_dir": "/tmp", "holdings_filename": "h.xlsx"})
        assert result is not None
        holdings, transactions, dividends = result
        assert len(holdings) == 2
        assert len(transactions) == 1
        assert len(dividends) == 1

    def test_empty_flows_when_no_flow_sheets(self):
        """无流水页签时 transactions/dividends 为空列表。"""
        mock_parsed = MagicMock()
        mock_parsed.holdings = [MagicMock()]
        mock_parsed.transactions = []
        mock_parsed.dividends = []
        with (
            patch("src.python.cli._handlers._cli_resolve_holdings_file", return_value="/tmp/h.xlsx"),
            patch("src.python.core.reader.read_holdings_with_flows", return_value=mock_parsed),
        ):
            result = _cli_read_holdings_with_flows({})
        assert result is not None
        holdings, transactions, dividends = result
        assert len(holdings) == 1
        assert transactions == []
        assert dividends == []

    def test_none_when_holdings_empty(self, caplog):
        """主表为空 → 返回 None + ERROR 日志。"""
        caplog.set_level(10)
        mock_parsed = MagicMock()
        mock_parsed.holdings = []
        with (
            patch("src.python.cli._handlers._cli_resolve_holdings_file", return_value="/tmp/h.xlsx"),
            patch("src.python.core.reader.read_holdings_with_flows", return_value=mock_parsed),
        ):
            result = _cli_read_holdings_with_flows({})
        assert result is None
        assert any("持仓文件为空" in r.message for r in caplog.records if r.levelname == "ERROR")


@pytest.mark.unit
class TestHandleReport:
    """_handle_report 委托 generate_report 并透传交易/分红流水。"""

    def test_threads_transactions_and_dividends(self):
        """报告生成将持仓 + 交易/分红流水一并传给 generate_report。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        with (
            patch(
                "src.python.cli._handlers._cli_read_holdings_with_flows",
                return_value=([MagicMock()], [MagicMock()], [MagicMock()]),
            ),
            patch("src.python.report.cli_progress.CliProgressReporter"),
            patch("src.python.report.orchestrator.generate_report", return_value=mock_result) as mock_gen,
        ):
            args = MagicMock()
            args.type = "basic"
            args.history = "auto"
            args.force_llm = False
            args.output = None
            args.verbose = False
            code = _handle_report(args, {})
        assert code == 0
        kwargs = mock_gen.call_args[1]
        assert len(kwargs["holdings"]) == 1
        assert len(kwargs["transactions"]) == 1
        assert len(kwargs["dividends"]) == 1

    def test_none_holdings_returns_severe(self):
        """持仓读取失败 → 返回 SEVERE 且不调用 generate_report。"""
        with (
            patch("src.python.cli._handlers._cli_read_holdings_with_flows", return_value=None),
            patch("src.python.report.orchestrator.generate_report") as mock_gen,
        ):
            args = MagicMock()
            args.verbose = False
            code = _handle_report(args, {})
        assert code == _EXIT_SEVERE
        mock_gen.assert_not_called()

    def test_prints_run_resource_summary(self):
        """报告完成后调用 LLM 成本 + 缓存命中率摘要方法（无调用时各自自行静默）。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_reporter = MagicMock()
        with (
            patch(
                "src.python.cli._handlers._cli_read_holdings_with_flows",
                return_value=([MagicMock()], [], []),
            ),
            patch("src.python.report.cli_progress.CliProgressReporter", return_value=mock_reporter),
            patch("src.python.report.orchestrator.generate_report", return_value=mock_result),
        ):
            args = MagicMock()
            args.type = "basic"
            args.history = "auto"
            args.force_llm = False
            args.output = None
            args.verbose = False
            code = _handle_report(args, {})
        assert code == 0
        mock_reporter.print_llm_cost_summary.assert_called_once()
        mock_reporter.print_cache_hit_summary.assert_called_once()

    def test_notify_dispatched_on_completion(self):
        """通知门控通过 → 构造事件并分发（报告类型/退出码/结果标志透传）。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.errors = []
        mock_result.excel_ok = True
        mock_result.html_ok = False
        cfg = {"notify": {"webhook_url": "https://hooks.example.test/x", "on_success": True}}
        with (
            patch(
                "src.python.cli._handlers._cli_read_holdings_with_flows",
                return_value=([MagicMock()], [], []),
            ),
            patch("src.python.report.cli_progress.CliProgressReporter"),
            patch("src.python.report.orchestrator.generate_report", return_value=mock_result),
            patch("src.python.core.completion_notify.dispatch_completion_notification") as mock_dispatch,
        ):
            args = MagicMock()
            args.type = "both"
            args.history = "auto"
            args.force_llm = False
            args.output = None
            args.verbose = False
            code = _handle_report(args, cfg)
        assert code == 0
        mock_dispatch.assert_called_once()
        event, notify_cfg = mock_dispatch.call_args[0]
        assert event["report_type"] == "both"
        assert event["ok"] is True
        assert event["exit_code"] == 0
        assert event["artifacts"], "excel_ok=True 应列示产物路径"
        assert notify_cfg["webhook_url"] == "https://hooks.example.test/x"

    def test_notify_silent_when_unconfigured(self):
        """config 无 notify 节 → 门控前置，不触达分发（静默跳过）。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        with (
            patch(
                "src.python.cli._handlers._cli_read_holdings_with_flows",
                return_value=([MagicMock()], [], []),
            ),
            patch("src.python.report.cli_progress.CliProgressReporter"),
            patch("src.python.report.orchestrator.generate_report", return_value=mock_result),
            patch("src.python.core.completion_notify.dispatch_completion_notification") as mock_dispatch,
        ):
            args = MagicMock()
            args.type = "basic"
            args.history = "auto"
            args.force_llm = False
            args.output = None
            args.verbose = False
            code = _handle_report(args, {})
        assert code == 0
        mock_dispatch.assert_not_called()

    def test_notify_failure_never_changes_exit_code(self):
        """通知流程内部抛异常 → 退出码原样返回（尽力而为契约）。"""
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.errors = []
        cfg = {"notify": {"webhook_url": "https://hooks.example.test/x", "on_success": True}}
        with (
            patch(
                "src.python.cli._handlers._cli_read_holdings_with_flows",
                return_value=([MagicMock()], [], []),
            ),
            patch("src.python.report.cli_progress.CliProgressReporter"),
            patch("src.python.report.orchestrator.generate_report", return_value=mock_result),
            patch(
                "src.python.core.completion_notify.build_completion_event",
                side_effect=RuntimeError("事件构造爆炸"),
            ),
        ):
            args = MagicMock()
            args.type = "full"
            args.history = "auto"
            args.force_llm = False
            args.output = None
            args.verbose = False
            code = _handle_report(args, cfg)
        assert code == 0


class TestDegradationSummary:
    """_collect_degradation_summary：跟踪器降级事件 → 摘要行（最新在前、按源去重）。"""

    def test_dedupes_latest_first(self):
        """同源多事件只留最新一条；未降级事件不入摘要。"""
        events = [
            {"source_key": "tencent", "degraded": True, "failure_type": "timeout", "count": 1},
            {"source_key": "akshare", "degraded": True, "failure_type": "circuit", "count": 3},
            {"source_key": "tencent", "degraded": True, "failure_type": "timeout", "count": 5},
            {"source_key": "sina", "degraded": False, "failure_type": None, "count": 0},
        ]
        tracker = MagicMock()
        tracker.get_log.return_value = events
        with patch("src.python.report.data_status.get_tracker", return_value=tracker):
            lines = _collect_degradation_summary()
        assert lines == [
            "tencent: timeout（累计5次）",
            "akshare: circuit（累计3次）",
        ]

    def test_tracker_failure_returns_empty(self):
        """跟踪器异常 → 返回空列表（通知摘要非关键，不拖垮收尾）。"""
        with patch("src.python.report.data_status.get_tracker", side_effect=RuntimeError("boom")):
            assert _collect_degradation_summary() == []


class TestLlmStatusLogging:
    """_show_llm_config_status_cli — 消费 llm_status 单源的日志渲染。"""

    @staticmethod
    def _records(caplog) -> str:
        from src.python.cli._handlers import _show_llm_config_status_cli

        with caplog.at_level("INFO", logger="invest"):
            _show_llm_config_status_cli()
        return "\n".join(r.getMessage() for r in caplog.records)

    def test_unconfigured(self, caplog, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: None)
        assert "状态: 未配置" in self._records(caplog)

    def test_flat_configured(self, caplog, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"api_key": "k", "provider": "claude"})
        text = self._records(caplog)
        assert "状态: 已配置" in text
        assert "provider=claude" in text

    def test_multi_chain(self, caplog, monkeypatch):
        monkeypatch.setattr(
            "src.python.config.get_llm_config",
            lambda: {"_provider_list": [{"name": "alpha", "provider": "claude"}]},
        )
        text = self._records(caplog)
        assert "多链服务: 1 provider" in text
        assert "alpha" in text
