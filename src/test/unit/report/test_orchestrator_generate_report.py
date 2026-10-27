"""orchestrator 报告生成主流程 — generate_report 产物落盘与快照比对。

覆盖场景：
  - generate_report 调用前后 reports/ 目录快照差异（新增/覆盖产物）
  - 报告产物落盘副作用与返回值契约

运行：
  pytest src/test/unit/report/test_orchestrator_generate_report.py -v"""

from __future__ import annotations
import os
import pytest
from unittest.mock import MagicMock, patch
from src.python.config import resolve_output_dir
from src.python.report.orchestrator import (
    ReportResult,
    generate_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _real_reports_dir() -> str:
    """项目真实 reports 目录（与 conftest 防线基准一致）。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "reports"))


def _snapshot_reports() -> frozenset:
    """返回项目 reports/ 下所有文件相对路径（用于断言防线生效）。"""
    root = _real_reports_dir()
    if not os.path.isdir(root):
        return frozenset()
    result = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            result.add(os.path.relpath(os.path.join(dirpath, f), root))
    return frozenset(result)


@pytest.mark.unit
@pytest.mark.unit_report
class TestGenerateReport:
    """generate_report 骨架测试。"""

    def test_generate_report_skeleton(self):
        """骨架模式返回 ReportResult，不抛异常（输出隔离由 conftest 防线兜底）。

        report_type 默认 basic（仅生成 Excel 不写 HTML），config 缺 output_dir
        时输出回退到相对路径 "reports"，解析为项目真实 reports/ 目录；空持仓
        会生成空页签 Excel 归档并覆盖根目录最新版，累积残留。conftest.
        _isolate_report_output_dir 兜底把指向项目真实 reports/ 的输出重定向到
        临时目录，此处用运行前后文件快照断言真实 reports/ 无新增，作永久回归
        守护。
        """
        mock_reporter = MagicMock()
        before = _snapshot_reports()
        with (
            # 市场数据网络依赖：交易日历（akshare）+ A 股/美股指数（腾讯/新浪）
            patch("src.python.core.trading_calendar._get_trading_calendar", return_value=set()),
            patch("src.python.fetcher.index.fetch_indices", return_value={}),
            patch("src.python.fetcher.index.fetch_us_indices", return_value={}),
            # 后台数据源健康检查（全量 HTTP 连通性探测）
            patch("src.python.report._report_health._spawn_health_checks", return_value=None),
            patch("src.python.report._report_health._collect_health_checks"),
        ):
            result = generate_report(holdings=[], config={}, reporter=mock_reporter)
        assert isinstance(result, ReportResult)
        assert result.report_generated is True
        assert result.exit_code == 0
        after = _snapshot_reports()
        assert before == after, "报告输出未重定向，真实 reports/ 目录被测试污染"

    def test_generate_report_basic(self):
        """basic 路径直接调用 excel_generator.generate_excel_report 生成 Excel 报告。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.excel_generator.generate_excel_report") as mock_gen,
            patch("src.python.core.registry.get_report_section_order", return_value=[{"key": "overview"}]),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="basic",
            )

        assert isinstance(result, ReportResult)
        assert result.excel_ok is True
        assert result.holdings_ok is True
        assert result.report_generated is True
        assert result.exit_code == 0
        # 验证 generate_excel_report 被正确调用（行动建议/数据质量仪表盘默认开，
        # 成本流式子模块默认关）——enable_action 必须显式下传，漏传则行动建议页签
        # 在 basic 路径下静默缺席（页签由 board 层开关决定创建与否）
        mock_gen.assert_called_once_with(
            mock_holdings,
            include_news=False,
            output_dir=resolve_output_dir(config),
            section_order=[{"key": "overview"}],
            progress=mock_reporter,
            enable_action=True,
            enable_cost_lots=False,
            transactions=None,
            dividends=None,
        )
        # 验证不调用数据准备/快照/历史等函数
        with pytest.raises(AssertionError):
            mock_reporter.info.assert_any_call("generate_report: 骨架模式")

    def test_generate_report_basic_exception(self):
        """basic 路径异常时 result.excel_ok=False，errors 非空。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]

        with (
            patch(
                "src.python.report.excel_generator.generate_excel_report",
                side_effect=RuntimeError("生成失败"),
            ),
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={},
                reporter=mock_reporter,
                report_type="basic",
            )

        assert result.excel_ok is False
        assert len(result.errors) > 0
        # reporter.add_error 被调用
        mock_reporter.add_error.assert_called_once()

    def test_generate_report_basic_uses_output_dir(self):
        """output_dir 参数覆盖 config 中的 output_dir。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]

        with (
            patch("src.python.report.excel_generator.generate_excel_report") as mock_gen,
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports"},
                reporter=mock_reporter,
                report_type="basic",
                output_dir="/custom/path",
            )

        assert result.report_generated is True
        mock_gen.assert_called_once()
        # output_dir 使用传参而非 config 值
        _call_kwargs = mock_gen.call_args.kwargs
        assert _call_kwargs["output_dir"] == "/custom/path"


@pytest.mark.unit
@pytest.mark.unit_report
class TestAutoCleanupOnGenerate:
    """生成入口触发过期缓存自动清理（无人值守路径回收缺失回归）。"""

    def test_generate_report_triggers_auto_cleanup(self, monkeypatch) -> None:
        """generate_report 开头调用 auto_cleanup_expired（CLI/TUI/Web 三渠道共用入口）。"""
        calls: list[int] = []
        monkeypatch.setattr(
            "src.python.cache.auto_cleanup_expired",
            lambda: calls.append(1) or 0,
        )
        mock_reporter = MagicMock()
        with (
            patch("src.python.core.trading_calendar._get_trading_calendar", return_value=set()),
            patch("src.python.fetcher.index.fetch_indices", return_value={}),
            patch("src.python.fetcher.index.fetch_us_indices", return_value={}),
            patch("src.python.report._report_health._spawn_health_checks", return_value=None),
            patch("src.python.report._report_health._collect_health_checks"),
        ):
            generate_report(holdings=[], config={}, reporter=mock_reporter, report_type="basic")
        assert calls == [1], "生成入口须触发一次过期缓存自动清理"
