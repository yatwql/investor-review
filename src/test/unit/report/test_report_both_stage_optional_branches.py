"""both 路径可选块的装配分支（report/_both_stages.py）。

测试场景：
  1. 开启个股基本面开关 → 财报摘要与财务指标两个契约按持仓取数装配
  2. 快照契约返回非映射 → checkpoint 只告警不中断
  3. 快照 diff 非映射 → 单独一条 checkpoint 告警
  4. 市场情绪非空且 pipeline_data 就绪 → 情绪契约挂到 pipeline_data
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.python.report._both_stages import BothOptions, BothRun, stage_history_assembly, stage_quotes, stage_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _options(**overrides) -> BothOptions:
    """最小开关组合（默认全关，按用例开启）。"""
    values = {
        "enable_fund_deep_analysis": False,
        "enable_news": False,
        "enable_history": False,
        "enable_portfolio_evolution": False,
        "enable_action": False,
        "enable_cost_lots": False,
        "enable_stock_fundamentals": False,
        "enable_summary_highlights": False,
        "section_order": [],
        "output": "reports",
        "news_top_count": 10,
    }
    values.update(overrides)
    return BothOptions(**values)


def _run(**overrides) -> BothRun:
    """最小运行上下文（阶段函数只经它取输入）。"""
    values = {
        "holdings": [],
        "config": {},
        "reporter": MagicMock(),
        "fetch_history": False,
        "transactions": None,
        "dividends": None,
        "snapshot_namespace": None,
        "options": _options(),
        "perf": MagicMock(),
        "result": None,
    }
    values.update(overrides)
    return BothRun(**values)


def test_stock_fundamentals_enabled_builds_both_contracts():
    """开关开启 → 财报摘要与财务指标各自装配，价格映射取自行情明细。"""
    details = [MagicMock()]
    run = _run(options=_options(enable_stock_fundamentals=True), details=details)
    digest = MagicMock(return_value={"available": True, "digest": "摘要"})
    indicator = MagicMock(return_value={"available": True, "indicator": "指标"})
    price_map = MagicMock(return_value={"SH600001": 12.0})
    with (
        patch("src.python.report._both_stages._compute_details", return_value=details),
        patch("src.python.report.orchestrator.compute_valuation_data", return_value=None),
        patch("src.python.report.orchestrator.compute_market_temperature_data", return_value=None),
        patch("src.python.report.purchase_status.build_purchase_status_data", return_value=None),
        patch("src.python.fetcher.financial_indicator.collect_price_map", price_map),
        patch("src.python.report.financial_indicator.build_financial_indicator", indicator),
        patch("src.python.report.financial_report_digest.build_financial_report_digest", digest),
    ):
        stage_quotes(run)

    assert run.contracts["financial_report_digest_data"] == {"available": True, "digest": "摘要"}
    assert run.contracts["financial_indicator_data"] == {"available": True, "indicator": "指标"}
    price_map.assert_called_once_with(details)


@pytest.mark.parametrize(
    ("pipeline_payload", "expected_key"),
    [
        (["不是映射"], "pipeline_data 类型异常(both)"),
        ({"diff": "不是映射"}, "pipeline_data.diff 类型异常(both)"),
    ],
)
def test_snapshot_checkpoint_warns_on_wrong_shape(pipeline_payload, expected_key, caplog):
    """快照契约形状异常 → 对应 checkpoint 告警，流程不中断。"""
    run = _run()
    with (
        patch("src.python.report._snapshot.capture_snapshot", return_value=pipeline_payload),
        patch(
            "src.python.report.pipeline_data_builder.merge_pipeline_data",
            side_effect=lambda data, **_kw: data,
        ),
        patch("src.python.report._experimental_seams.inject_holding_change_data"),
        patch("src.python.core.holding_status.build_coverage_summary", return_value={}),
        patch("src.python.core.data_freshness.build_freshness_summary", return_value={}),
        patch("src.python.report.market_value.get_last_trading_day", return_value="2025-01-02"),
        patch("src.python.report.market_value.get_prev_trading_day", return_value="2025-01-01"),
        caplog.at_level(logging.WARNING),
    ):
        stage_snapshot(run)

    assert any(expected_key in rec.message for rec in caplog.records), [r.message for r in caplog.records]


def test_market_sentiment_attached_when_pipeline_ready():
    """市场情绪非空且 pipeline_data 就绪 → 情绪契约落进 pipeline_data。"""
    pipeline_data: dict = {}
    run = _run(pipeline_data=pipeline_data)
    with (
        patch("src.python.report._snapshot.assemble_history_augmented_data"),
        patch("src.python.report._snapshot.latest_quotes_from_detail_rows", return_value={}),
        patch("src.python.analysis.tail_risk.compute_tail_risk", return_value={"available": False}),
        patch("src.python.report._report_helpers._action_holdings_details", return_value=[]),
        patch("src.python.analysis.metrics.compute_portfolio_peak_mv", return_value=None),
        patch("src.python.analysis.action_advisor.build_action_data", return_value={"discipline_signals": None}),
        patch("src.python.report.decision_basis.build_decision_basis_data", return_value={"available": True}),
        patch("src.python.report._experimental_seams.record_deterministic_decisions"),
        patch("src.python.report._experimental_seams.record_llm_decisions_and_review_block"),
        patch("src.python.report._experimental_seams.record_prosperity_diagnosis"),
        patch("src.python.report._report_aux_metrics.compute_market_sentiment_data", return_value={"hot": ["银行"]}),
    ):
        stage_history_assembly(run)

    assert run.pipeline_data["market_sentiment_data"] == {"hot": ["银行"]}
    assert "tail_risk_data" in run.pipeline_data
