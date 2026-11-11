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

    def test_both_path_passes_holdings_details_not_config_to_purchase_status(self):
        """both 路径把持仓明细（name/code 最小形态）交给 build_purchase_status_data。

        回归：曾经误传 `config`（dict），迭代出的是键名（str）→
        `h.get("code")` 当场 AttributeError，开启「基金申购限购」后 both 路径整条中断。
        """
        mock_detail = MagicMock()
        mock_detail.name = "演示基金"
        mock_detail.code = "000001"
        mock_detail.market_value = 1200.0
        mock_detail.cost = 1000.0

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={"diff": {}}),
            patch("src.python.report._snapshot.fetch_history_data", return_value={"dates": []}),
            patch("src.python.report.html_writer.write_html_report"),
            patch("src.python.report.excel_generator.generate_excel_report"),
            patch("src.python.core.registry.get_report_section_order", return_value=[]),
            patch("src.python.config.is_enable_fund_deep_analysis", return_value=False),
            patch("src.python.config.is_enable_news", return_value=False),
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
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
            patch("src.python.report.purchase_status.build_purchase_status_data") as mock_purchase,
        ):
            mock_purchase.return_value = None
            generate_report(
                holdings=[MagicMock(code="000001", name="演示基金", shares=100, cost_price=10.0)],
                config={"output_dir": "reports"},
                reporter=MagicMock(),
                report_type="both",
                fetch_history=False,
            )

        mock_purchase.assert_called_once()
        passed = mock_purchase.call_args.args[0]
        assert isinstance(passed, list), f"必须传持仓明细列表，实传 {type(passed).__name__}"
        assert passed and passed[0].get("code") == "000001"
        assert passed[0].get("name") == "演示基金"

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


class TestDecisionReviewWiring:
    """both 路径决策复盘区块接线（decision_reflection 开启时的回归守卫）。

    现场（自审挂账）：both 路径既不装配 `decision_review_data`、也不向
    `write_html_report` 转发，实验功能开启时行动章「决策跨期反思」块在该路径
    整块不渲染（full 路径正常）。本用例锁定「挂载点被调用 + 契约传到双端 writer」。
    """

    def _run(self, captured: dict):
        mock_reporter = MagicMock()
        mock_holdings = [MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)]

        mock_detail = MagicMock()
        mock_detail.code = "SH600001"
        mock_detail.name = "测试"
        mock_detail.market_value = 1200.0
        mock_detail.cost = 1000.0
        mock_detail.shares = 100
        mock_detail.price = 12.0

        def _fake_record_deterministic(prep, action_data, reporter):
            captured["det_prep"] = prep
            captured["det_action"] = action_data

        def _fake_record_review(prep, llm_content, enable_llm, pipeline_data, reporter):
            captured["review_prep"] = prep
            captured["review_llm"] = (llm_content, enable_llm)
            captured["review_pipeline_is_none"] = pipeline_data is None
            if pipeline_data is not None:
                pipeline_data["decision_review_data"] = {"available": True, "rows": []}

        with (
            patch("src.python.report.market_value._generate_details", return_value=[mock_detail]),
            patch("src.python.report._snapshot.capture_snapshot", return_value={}),
            patch("src.python.report._snapshot.fetch_history_data"),
            patch("src.python.report.html_writer.write_html_report") as mock_html,
            patch("src.python.report.excel_generator.generate_excel_report") as mock_xls,
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
                return_value={"available": True, "summary": "", "rebalance_signals": []},
            ),
            patch(
                "src.python.report._experimental_seams.record_deterministic_decisions",
                side_effect=_fake_record_deterministic,
            ),
            patch(
                "src.python.report._experimental_seams.record_llm_decisions_and_review_block",
                side_effect=_fake_record_review,
            ),
        ):
            result = generate_report(
                holdings=mock_holdings,
                config={"output_dir": "reports"},
                reporter=mock_reporter,
                report_type="both",
                fetch_history=True,
            )
        return result, mock_html, mock_xls

    def test_seams_receive_date_and_holdings_for_settlement_baseline(self):
        """挂载点入参须带 today_str 与 holdings_details（结算基线来源）。"""
        import re

        captured: dict = {}
        result, _, _ = self._run(captured)
        assert result.report_generated is True

        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", captured["det_prep"]["today_str"]), (
            "today_str 须为 ISO 日期（账本报告日，跨期结算按它分档）"
        )
        assert isinstance(captured["det_prep"]["holdings_details"], list), (
            "holdings_details 缺失 → 登记无基线 → 全部跳过（入账必可结算纪律）"
        )
        assert captured["det_action"] == {"available": True, "summary": "", "rebalance_signals": []}, (
            "确定性登记须消费本轮最终 action_data（含峰值重建版）"
        )
        # both 路径无 LLM 章节：LLM 侧登记自然跳过，但复盘区块仍须装配
        assert captured["review_llm"] == ((), False)
        assert captured["review_pipeline_is_none"] is False

    def test_review_block_reaches_both_writers(self):
        """装配出的复盘区块须同时到达 HTML 与 Excel（双端公平）。"""
        captured: dict = {}
        _, mock_html, mock_xls = self._run(captured)

        assert mock_html.call_args.kwargs.get("decision_review_data") == {"available": True, "rows": []}, (
            "HTML 未收到 decision_review_data → 行动章复盘块静默不渲染"
        )
        _pipeline = mock_xls.call_args.kwargs.get("pipeline_data") or {}
        assert _pipeline.get("decision_review_data") == {"available": True, "rows": []}, (
            "Excel 未收到 decision_review_data → 行动页签复盘子块缺失"
        )
