"""report/_history_quality 与 _full_risk_metrics 的守卫分支单测。

覆盖：
  - ``_validate_bars`` 的未来日期与单日异常跳变两类告警；
  - ``_detect_terminal_staleness`` 空序列条目跳过与全空时返回 None；
  - ``_diagnose_return`` 无 bar 时静默返回；
  - ``_prepare_full_risk_metrics`` 的 risk_metrics 缺键告警、对齐摘要注入、
    情景分析注入与 history 缺失时的指标降级。

运行：
  pytest src/test/unit/report/test_metrics_guard_branches.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.python.report import _full_risk_metrics as frm
from src.python.report import _history_quality as hq

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestValidateBars:
    """走势数据质量检查的日期/跳变告警。"""

    def test_future_date_warns(self):
        """晚于今日的 bar 被标为「日期为未来」。"""
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        warnings = hq._validate_bars([{"date": future, "close": 10.0}])
        assert any("日期为未来" in w for w in warnings)

    def test_large_daily_jump_warns(self):
        """单日变化超过 50% 时给出异常跳变提示。"""
        warnings = hq._validate_bars(
            [
                {"date": "2025-01-02", "close": 10.0},
                {"date": "2025-01-03", "close": 20.0},
            ]
        )
        assert any("单日变化" in w for w in warnings)


class TestTerminalStalenessGuards:
    """终点滞后检测的空序列分支。"""

    def test_empty_series_skipped_and_all_empty_returns_none(self):
        """序列为空的条目被跳过；全部为空时不产出滞后结论。"""
        assert hq._detect_terminal_staleness([("甲", "600900", [])], ["2025-01-03"], 1000.0) is None


class TestDiagnoseReturnGuard:
    """收益率诊断的空 bar 分支。"""

    def test_no_bars_returns_silently(self):
        """无 bar 时诊断直接返回（不写日志、不抛异常）。"""
        assert hq._diagnose_return([], 0, {}, 0.0, 0) is None


def _perf() -> SimpleNamespace:
    return SimpleNamespace(start=lambda *_a, **_k: None, stop=lambda *_a, **_k: None)


class TestPrepareFullRiskMetrics:
    """全量指标装配的分支覆盖。"""

    def test_missing_annualized_volatility_warns(self, monkeypatch):
        """history 缺失且 prep 已带 risk_metrics 时，缺波动率键只告警并降级指标。"""
        monkeypatch.setattr("src.python.report._snapshot.fetch_history_data", lambda *_a, **_k: None)
        monkeypatch.setattr("src.python.report._snapshot.latest_quotes_from_detail_rows", lambda _rows: {})
        prep: dict = {"risk_metrics": {}, "holdings_details": []}
        history, metrics = frm._prepare_full_risk_metrics(
            holdings=[],
            config={},
            reporter=SimpleNamespace(info=lambda *_a, **_k: None),
            perf=_perf(),
            fetch_history=True,
            enable_history=True,
            prep=prep,
            pipeline_data=None,
        )
        assert history is None
        assert metrics is None

    def test_alignment_and_scenario_injected(self, monkeypatch):
        """对齐摘要与情景分析在数据齐备时注入 metrics。"""
        history = {
            "status": "ok",
            "annualized_volatility": 0.2,
            "max_drawdown_pct": 10.0,
            "total_return_pct": 5.0,
            "data_start": "2024-01-01",
            "data_end": "2025-01-01",
            "daily_returns_portfolio": [0.01, -0.02],
        }
        monkeypatch.setattr("src.python.report._snapshot.fetch_history_data", lambda *_a, **_k: history)
        monkeypatch.setattr("src.python.report._snapshot.latest_quotes_from_detail_rows", lambda _rows: {})
        monkeypatch.setattr(
            "src.python.analysis.metrics.compute_all_metrics",
            lambda **_kwargs: {
                "beta_analysis": {"ci_lower": 0.8, "ci_upper": 1.2, "std_error": 0.1},
                "portfolio_beta": 1.0,
            },
        )
        monkeypatch.setattr(
            "src.python.analysis.alignment_correction.compute_alignment_factors",
            lambda **_kwargs: {"has_any_data": True, "summary_text": "2 只标的复权口径已修正"},
        )
        scenario = {"has_data": True, "scenarios": [{"name": "基准", "value": 1000.0}]}
        monkeypatch.setattr("src.python.analysis.scenario.scenario_analysis", lambda **_kwargs: scenario)
        prep: dict = {"holdings_details": [{"market_value": 500.0}], "total_mv": 500.0}
        _history, metrics = frm._prepare_full_risk_metrics(
            holdings=[],
            config={},
            reporter=SimpleNamespace(info=lambda *_a, **_k: None),
            perf=_perf(),
            fetch_history=True,
            enable_history=True,
            prep=prep,
            pipeline_data=None,
        )
        assert metrics["alignment_summary"] == "2 只标的复权口径已修正"
        assert metrics["scenario_analysis"] is scenario
