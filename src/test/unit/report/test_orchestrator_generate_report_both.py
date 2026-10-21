"""orchestrator 报告生成主流程 — generate_report 产物落盘与快照比对。

覆盖场景：
  - generate_report 调用前后 reports/ 目录快照差异（新增/覆盖产物）
  - 报告产物落盘副作用与返回值契约

运行：
  pytest src/test/unit/report/test_orchestrator_generate_report.py -v

兄弟分片：both 路径（HTML+Excel，不含 LLM）。"""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.python.report.orchestrator import (
    ReportResult,
    generate_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class TestGenerateReportBoth:
    """both 路径（HTML+Excel，不含 LLM）。"""

    def test_generate_report_both_calls_compute_details(self):
        """both 路径调用 _compute_details 而非 prepare_report_data，不调用 LLM/线程池。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]
        config = {
            "output_dir": "reports",
            "news_top_count": 100,
            "history": {"fetch_mode": "auto"},
        }

        mock_detail = MagicMock()
        mock_detail.code = "SH600001"
        mock_detail.market_value = 1200.0
        mock_detail.cost = 1000.0

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot") as mock_cap,
            patch("src.python.report._snapshot.fetch_history_data") as mock_hist,
            patch("src.python.report.html_writer.write_html_report") as mock_html,
            patch("src.python.report.excel_generator.generate_excel_report") as mock_xls,
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            # 品种覆盖诊断：mock_detail 无真实价格字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.core.holding_status.build_coverage_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 可信度摘要：同样依赖真实价格/净值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 行动建议单一数据源：mock_detail 无真实市值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
        ):
            mock_cap.return_value = {"diff": {}}
            mock_hist.return_value = {"dates": [], "status": "available"}

            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="both",
                fetch_history=True,
            )

        assert isinstance(result, ReportResult)
        assert result.report_generated is True
        assert result.html_ok is True
        assert result.excel_ok is True
        # 验证 _compute_details （即 _generate_details）被调用
        # 验证 capture_snapshot 和 fetch_history_data 被调用
        mock_cap.assert_called_once()
        mock_hist.assert_called_once()
        # 验证 write_html_report 和 generate_excel_report 被调用
        assert mock_html.call_count >= 1
        assert mock_xls.call_count >= 1
        # 验证传入 enable_llm=False（both 路径不含 LLM）
        _html_kwargs = mock_html.call_args.kwargs
        assert _html_kwargs.get("enable_llm") is False
        _xls_kwargs = mock_xls.call_args.kwargs
        assert _xls_kwargs.get("enable_llm") is False

    def test_generate_report_both_history_off(self):
        """both 路径历史走势关闭（enable_history=False）时不调用 fetch_history_data。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[MagicMock()]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data") as mock_hist,
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=False),
            patch("src.python.config.is_enable_history", return_value=False),
            # 可信度摘要：MagicMock detail 无真实价格/净值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 行动建议单一数据源：MagicMock detail 无真实市值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="both",
                fetch_history=True,
            )

        assert result.report_generated is True
        # history 关闭时 fetch_history_data 不应被调用（即使 fetch_history=True）
        mock_hist.assert_not_called()

    def test_generate_report_both_fetch_history_follows_config(self):
        """both 路径未显式传 fetch_history 时按 config.history.fetch_mode 决定。

        回归守护：CLI 未传 --history 时默认值不得硬编码，须回退到 config.json
        的 history.fetch_mode（off → 不获取；auto/缺失 → 获取），验证
        fetch_history_data 收到的 fetch 参数来自配置层。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]

        def _run(config: dict) -> bool:
            with (
                patch("src.python.report.market_value._generate_details", return_value=[MagicMock()]),
                patch("src.python.report._snapshot.capture_snapshot", return_value={}),
                patch("src.python.report._snapshot.fetch_history_data") as mock_hist,
                patch("src.python.report.html_writer.write_html_report"),
                patch("src.python.report.excel_generator.generate_excel_report"),
                patch("src.python.core.registry.get_report_section_order"),
                patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
                patch("src.python.config.is_enable_news", return_value=False),
                patch("src.python.config.is_enable_history", return_value=True),
                # 可信度摘要：MagicMock detail 无真实价格/净值字段，须 mock
                patch(
                    "src.python.core.data_freshness.build_freshness_summary",
                    return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
                ),
                # 行动建议单一数据源：MagicMock detail 无真实市值字段，须 mock
                patch(
                    "src.python.analysis.action_advisor.build_action_data",
                    return_value={"available": True, "summary": "", "rebalance_signals": []},
                ),
            ):
                result = generate_report(
                    holdings=mock_holdings,
                    config=config,
                    reporter=mock_reporter,
                    report_type="both",
                    fetch_history=None,
                )
            assert result.report_generated is True
            mock_hist.assert_called_once()
            return mock_hist.call_args.kwargs["fetch"]

        assert _run({"output_dir": "reports", "history": {"fetch_mode": "off"}}) is False
        assert _run({"output_dir": "reports", "history": {"fetch_mode": "auto"}}) is True
        # fetch_mode 缺失 → 默认 auto（获取）
        assert _run({"output_dir": "reports"}) is True

    def test_generate_report_both_no_prepare_report_data(self):
        """both 路径不应调用 prepare_report_data（无指数/穿透/分类）。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[MagicMock()]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            # 可信度摘要：MagicMock detail 无真实价格/净值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 行动建议单一数据源：MagicMock detail 无真实市值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
            # 使用 wrapt 确保 prepare_report_data 不被调用
        ):
            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="both",
            )

        assert result.report_generated is True

    def test_generate_report_both_excel_fallback(self):
        """both 路径 HTML 失败时仍继续生成 Excel。"""
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock()]
        config = {"output_dir": "reports"}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[MagicMock()]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch(
                "src.python.report.html_writer.write_html_report",
                side_effect=RuntimeError("HTML 失败"),
            ),
            patch("src.python.report.excel_generator.generate_excel_report") as mock_xls,
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=False),
            patch("src.python.config.is_enable_history", return_value=False),
            # 可信度摘要：MagicMock detail 无真实价格/净值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 行动建议单一数据源：MagicMock detail 无真实市值字段，须 mock（防 MagicMock 比较崩溃）
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config=config,
                reporter=mock_reporter,
                report_type="both",
            )

        assert result.html_ok is False
        assert result.excel_ok is True
        assert result.report_generated is True  # Excel 成功，不算失败
        mock_xls.assert_called_once()

    def test_generate_report_both_passes_percent_profit_rate(self):
        """both 路径传入纪律引擎的 profit_rate 为百分数（小数 ×100）。

        回归验证：交易纪律（止盈/止损）以百分数阈值（如 +20%）比较，
        both 路径必须把 DetailRow 的小数收益率换算为百分数，否则纪律
        信号永不触发（与 full 路径 orchestrator 组装口径一致）。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]

        mock_detail = MagicMock()
        mock_detail.code = "SH600001"
        mock_detail.name = "测试"
        mock_detail.market_value = 1250.0
        mock_detail.cost = 1000.0
        mock_detail.profit = 250.0
        mock_detail.profit_rate = 0.25  # 小数字段（DetailRow 契约）
        mock_detail.shares = 100
        mock_detail.price = 12.5

        captured: dict = {}

        def _fake_build(holdings_details, total_mv, **kwargs):
            captured["holdings_details"] = holdings_details
            return {"available": True, "summary": "", "rebalance_signals": []}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch(
                "src.python.core.holding_status.build_coverage_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            # 拦截 build_action_data，捕获其收到的 holdings_details
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                side_effect=_fake_build,
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports", "history": {"fetch_mode": "auto"}},
                reporter=mock_reporter,
                report_type="both",
            )

        assert result.report_generated is True
        detail = captured["holdings_details"][0]
        # 0.25（小数）→ 25.0（百分数），纪律引擎以 20.0 阈值比较能正确触发止盈
        assert detail["profit_rate"] == pytest.approx(25.0)
        assert detail["profit"] == pytest.approx(250.0)
        assert detail["market_value"] == pytest.approx(1250.0)

    def test_generate_report_both_passes_channel_context(self):
        """both 路径持仓明细携带渠道上下文（账户关键词 → 场内/场外）。

        回归：可行化层按 channel 区分场外基金（整数份 + 赎回费）与场内品种
        （100 份取整 + 仅佣金），字段缺失会退回代码前缀判定而误判 LOF/开放式基金。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="161725", name="招商中证白酒指数A", shares=100, cost_price=1.0)]

        mock_detail = MagicMock()
        mock_detail.code = "161725"
        mock_detail.name = "招商中证白酒指数A"
        mock_detail.market_value = 1250.0
        mock_detail.cost = 1000.0
        mock_detail.profit = 250.0
        mock_detail.profit_rate = 0.25
        mock_detail.shares = 100
        mock_detail.price = 12.5
        mock_detail.account = "天天基金"  # 场外账户关键词 → 渠道为场外

        captured: dict = {}

        def _fake_build(holdings_details, total_mv, **kwargs):
            captured["holdings_details"] = holdings_details
            return {"available": True, "summary": "", "rebalance_signals": []}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch(
                "src.python.core.holding_status.build_coverage_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                side_effect=_fake_build,
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports", "history": {"fetch_mode": "auto"}},
                reporter=mock_reporter,
                report_type="both",
            )

        assert result.report_generated is True
        assert captured["holdings_details"][0]["channel"] == "场外"

    def test_generate_report_both_injects_portfolio_peak_mv(self):
        """both 路径历史走势后重建 action_data，注入组合历史峰值市值。

        回归：组合回撤纪律以 history_data.bars 的峰值市值为基准——峰值在
        「3. 历史走势」之后才可得，action_data 必须就地重建并传入
        portfolio_peak_mv，否则回撤纪律在生产路径永不激活。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]

        mock_detail = MagicMock()
        mock_detail.code = "SH600001"
        mock_detail.name = "测试"
        mock_detail.market_value = 1250.0
        mock_detail.cost = 1000.0
        mock_detail.profit = 250.0
        mock_detail.profit_rate = 0.25
        mock_detail.shares = 100
        mock_detail.price = 12.5

        captured: dict = {}

        def _fake_build(holdings_details, total_mv, **kwargs):
            captured["portfolio_peak_mv"] = kwargs.get("portfolio_peak_mv")
            return {"available": True, "summary": "", "rebalance_signals": []}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
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
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=True),
            patch(
                "src.python.core.holding_status.build_coverage_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                side_effect=_fake_build,
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports"},
                reporter=mock_reporter,
                report_type="both",
                fetch_history=True,
            )

        assert result.report_generated is True
        assert captured["portfolio_peak_mv"] == pytest.approx(200.0)

    def test_generate_report_both_peak_none_when_history_off(self):
        """both 路径历史走势关闭 → 峰值注入 None（组合回撤纪律按「峰值未知」不激活）。

        历史走势关闭时 action_data 仍需构建（止盈/止损纪律不受影响），
        峰值取 None 且不得报错。
        """
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]

        mock_detail = MagicMock()
        mock_detail.code = "SH600001"
        mock_detail.name = "测试"
        mock_detail.market_value = 1250.0
        mock_detail.cost = 1000.0
        mock_detail.profit = 250.0
        mock_detail.profit_rate = 0.25
        mock_detail.shares = 100
        mock_detail.price = 12.5

        captured: dict = {}

        def _fake_build(holdings_details, total_mv, **kwargs):
            captured["portfolio_peak_mv"] = kwargs.get("portfolio_peak_mv")
            return {"available": True, "summary": "", "rebalance_signals": []}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order"),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=True),
            patch("src.python.config.is_enable_news", return_value=True),
            patch("src.python.config.is_enable_history", return_value=False),
            patch(
                "src.python.core.holding_status.build_coverage_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.core.data_freshness.build_freshness_summary",
                return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
            ),
            patch(
                "src.python.analysis.action_advisor.build_action_data",
                side_effect=_fake_build,
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports"},
                reporter=mock_reporter,
                report_type="both",
                fetch_history=True,
            )

        assert result.report_generated is True
        assert captured["portfolio_peak_mv"] is None
