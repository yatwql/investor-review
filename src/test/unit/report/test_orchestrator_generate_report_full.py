"""orchestrator 报告生成主流程 — generate_report 产物落盘与快照比对。

覆盖场景：
  - generate_report 调用前后 reports/ 目录快照差异（新增/覆盖产物）
  - 报告产物落盘副作用与返回值契约

运行：
  pytest src/test/unit/report/test_orchestrator_generate_report.py -v

兄弟分片：full 路径（HTML+Excel+LLM 编排）。"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.python.report.orchestrator import (
    ReportResult,
    generate_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class TestGenerateReportFull:
    """full 路径（HTML+Excel+LLM 编排）。"""

    def test_generate_report_full_calls_prepare_report_data(self):
        """full 路径调用 prepare_report_data（含指数/穿透/分类）。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]
        config = {
            "output_dir": "reports",
            "news_top_count": 100,
            "history": {"fetch_mode": "auto"},
        }

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report._llm_news._fetch_llm_and_news") as mock_llm_news,
            patch("src.python.report.html_writer.write_html_report") as mock_html,
            patch("src.python.report.excel_generator.generate_excel_report") as mock_xls,
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.config.is_enable_llm", return_value=True),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 0,
                "total_cost": 0,
                "total_profit": 0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }
            mock_llm_news.return_value = (
                (None, None, None, None),
                [],
                {},
                False,
                None,
            )

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
                fetch_history=True,
                force_llm=False,
            )

        assert isinstance(result, ReportResult)
        assert result.report_generated is True
        # prepare_report_data 被调用且传入了 config；transactions 透传（未提供时为 None），
        # 供持仓明细附加 holding_days（再平衡误报防护的「新买入品种观察期」判据）
        mock_prep.assert_called_once_with(mock_holdings, mock_reporter, config, transactions=None)
        # HTML 和 Excel 报告生成
        assert mock_html.call_count >= 1
        assert mock_xls.call_count >= 1
        # 传入 enable_llm=True（full 路径含 LLM）
        _html_kwargs = mock_html.call_args.kwargs
        assert _html_kwargs.get("enable_llm") is True

    def test_generate_report_full_injects_portfolio_peak_mv(self):
        """full 路径历史走势后重建 action_data，注入组合历史峰值市值。

        回归：prepare_report_data 的 action_data 为中间占位构建（无峰值），
        full 路径必须在 _prepare_full_risk_metrics（history 就绪）后重建并
        注入 portfolio_peak_mv，组合回撤纪律方能激活。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]
        config = {
            "output_dir": "reports",
            "news_top_count": 100,
            "history": {"fetch_mode": "auto"},
        }

        captured: dict = {}

        def _fake_build(holdings_details, total_mv, **kwargs):
            captured["portfolio_peak_mv"] = kwargs.get("portfolio_peak_mv")
            return {"available": True, "summary": "", "rebalance_signals": []}

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            # 历史走势 bars：峰值 200.0（100→200→150），回撤纪律基准应为历史峰值
            patch(
                "src.python.report._snapshot.fetch_history_data",
                return_value={
                    "status": "ok",
                    "bars": [
                        {"date": "2026-01-01", "total_value": 100.0},
                        {"date": "2026-01-02", "total_value": 200.0},
                        {"date": "2026-01-03", "total_value": 150.0},
                    ],
                },
            ),
            patch("src.python.report._llm_news._fetch_llm_and_news") as mock_llm_news,
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.config.is_enable_llm", return_value=True),
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                side_effect=_fake_build,
            ),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 1250.0,
                "total_cost": 1000.0,
                "total_profit": 250.0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [
                    {
                        "name": "测试",
                        "code": "SH600001",
                        "market_value": 1250.0,
                        "cost": 1000.0,
                        "profit": 250.0,
                        "profit_rate": 25.0,
                        "shares": 100,
                        "price": 12.5,
                    }
                ],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }
            mock_llm_news.return_value = (
                (None, None, None, None),
                [],
                {},
                False,
                None,
            )

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
                fetch_history=True,
                force_llm=False,
            )

        assert result.report_generated is True
        assert captured["portfolio_peak_mv"] == pytest.approx(200.0)

    def test_generate_report_full_news_only(self):
        """full 路径仅新闻（LLM 关闭）时正常工作。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value=None),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=None),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.config.is_enable_llm", return_value=False),
            patch("src.python.report.news_correlation.build_news_data", return_value=([{"title": "新闻1"}], {})),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 0,
                "total_cost": 0,
                "total_profit": 0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
            )

        assert result.report_generated is True
        assert result.news_ok is True

    def test_generate_report_full_llm_only(self):
        """full 路径仅 LLM（新闻关闭）时正常工作。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value=None),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=None),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=False),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.config.is_enable_llm", return_value=True),
            patch(
                "src.python.llm.generate_all_llm",
                return_value=(
                    "<p>宏观</p>",
                    None,
                    None,
                    None,
                    False,
                    False,
                    False,
                    False,
                ),
            ),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 0,
                "total_cost": 0,
                "total_profit": 0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
            )

        assert result.report_generated is True

    def test_generate_report_full_both_disabled(self):
        """full 路径 LLM 和新闻均关闭时跳过内容生成，报告仍正常生成。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value=None),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=None),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=False),
            patch("src.python.config.is_enable_history", return_value=True),
            patch("src.python.config.is_enable_llm", return_value=False),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 0,
                "total_cost": 0,
                "total_profit": 0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
            )

        assert result.report_generated is True

    def test_generate_report_full_excel_fallback(self):
        """full 路径 HTML 失败时仍继续生成 Excel 报告。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.orchestrator.prepare_report_data") as mock_prep,
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch(
                "src.python.report.html_writer.write_html_report",
                side_effect=RuntimeError("HTML 失败"),
            ),
            patch("src.python.report.excel_generator.generate_excel_report") as mock_xls,
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.providers.akshare_extras.get_sector_fund_flow", return_value=None),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=False),
            patch("src.python.config.is_enable_history", return_value=False),
            patch("src.python.config.is_enable_llm", return_value=False),
        ):
            mock_prep.return_value = {
                "details": [],
                "total_mv": 0,
                "total_cost": 0,
                "total_profit": 0,
                "total_today_profit": 0,
                "categories": [],
                "a_indices": {},
                "us_indices": {},
                "penetrated_assets": [],
                "holdings_details": [],
                "today_str": "2026-07-16",
                "output_dir": "reports",
                "news_top_count": 100,
            }

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="full",
            )

        assert result.html_ok is False
        assert result.excel_ok is True
        assert result.report_generated is True
        mock_xls.assert_called_once()
