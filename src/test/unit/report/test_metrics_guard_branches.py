"""走势数据质量告警与全量指标装配的可见产物单测。

两类「守卫分支」都锁**用户可见形态**，而不是内部调用次数：

  - 走势数据质量：`get_combined_timeseries` 返回契约里的 `warnings` 与
    `terminal_staleness`（HTML 章节与 Excel 页签直接呈现这两处）——未来日期、
    单日异常跳变、终点净值滞后三类告警必须落在 `warnings` 里；
    无走势时静默降级为 `unavailable`，不产出收益率诊断日志。
  - 全量指标装配：`_prepare_full_risk_metrics` 就地注入 `prep["risk_metrics"]`
    的键值、返回 `metrics` 的键值，以及缺波动率时的 checkpoint 告警。

取数（`calculate_for_holding` / `fetch_history_data`）与计算模块（`metrics` /
`alignment_correction` / `scenario`）作为协作方边界替换为极薄 fake，断言落在最终产物上。

运行：
  pytest src/test/unit/report/test_metrics_guard_branches.py -v
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.python.report import _full_risk_metrics as frm
from src.python.report.portfolio_history import PortfolioHistoryCalculator
from src.test._fixtures.reporters import RecordingReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _series(dates: list[str], values: list[float]) -> list[dict]:
    """单只标的的历史序列（`close` 与 `value` 同值，两种取数口径同形）。"""
    return [{"date": d, "close": v, "value": v} for d, v in zip(dates, values)]


def _calculator(monkeypatch, series_by_code: dict[str, list[dict]]) -> PortfolioHistoryCalculator:
    """装配走势计算器：持仓取数换成给定序列，基准指数禁用（零网络）。"""
    calc = PortfolioHistoryCalculator()
    monkeypatch.setattr(calc, "calculate_for_holding", lambda code, *_a, **_k: series_by_code.get(code, []))
    return calc


class TestHistoryQualityWarnings:
    """走势数据质量告警的可见契约（`warnings` 列表）。"""

    def test_future_dated_bar_warns(self, monkeypatch):
        """晚于今日的 bar → `warnings` 出现「日期为未来」，且该日进入数据区间。"""
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        calc = _calculator(monkeypatch, {"600900": _series(["2026-01-05", future], [10.0, 10.2])})

        result = calc.get_combined_timeseries([("600900", "长江电力", 100.0)])

        assert any("日期为未来" in w for w in result["warnings"]), result["warnings"]
        assert result["data_end"] == future
        assert result["status"] == "ok"

    def test_large_daily_jump_warns(self, monkeypatch):
        """单日变化超过 50% → `warnings` 给出异常跳变提示（收益率照实算）。"""
        calc = _calculator(monkeypatch, {"600900": _series(["2026-01-05", "2026-01-06"], [10.0, 20.0])})

        result = calc.get_combined_timeseries([("600900", "长江电力", 100.0)])

        assert any("单日变化 100.0%" in w for w in result["warnings"]), result["warnings"]
        assert result["total_return_pct"] == pytest.approx(100.0)


class TestTerminalStalenessContract:
    """终点滞后契约：`terminal_staleness` 明细 + `warnings` 提示同现。"""

    def test_stale_asset_surfaces_in_contract_and_warnings(self, monkeypatch):
        """两标的终点相差 3 个交易日 → 滞后标的进契约明细，且提示写入 warnings。"""
        calc = _calculator(
            monkeypatch,
            {
                "600900": _series(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"], [10.0, 10.1, 10.2, 10.3]),
                "270042": _series(["2026-01-05"], [2.0]),
            },
        )

        result = calc.get_combined_timeseries([("600900", "长江电力", 100.0), ("270042", "广发纳斯达克100", 100.0)])

        staleness = result["terminal_staleness"]
        assert staleness is not None, "滞后 ≥2 个交易日必须产出契约明细"
        assert staleness["max_lag_trading_days"] == 3
        assert [a["code"] for a in staleness["assets"]] == ["270042"]
        assert staleness["assets"][0]["detail"].startswith(
            "广发纳斯达克100(270042)：最新净值日 2026-01-05（滞后 3 个交易日"
        ), staleness["assets"][0]["detail"]
        assert "历史走势终点净值滞后" in result["warnings"][-1], result["warnings"]
        assert "至多 3 个交易日" in staleness["caveat"], staleness["caveat"]

    def test_no_history_degrades_silently_without_diagnosis(self, monkeypatch, caplog):
        """无任何走势 → 降级为 unavailable 占位，且不产出收益率诊断日志。"""
        calc = _calculator(monkeypatch, {})

        with caplog.at_level(logging.INFO, logger="invest"):
            result = calc.get_combined_timeseries([("600900", "长江电力", 100.0)])

        assert result["status"] == "unavailable"
        assert result["warnings"] == ["所有持仓均无法获取历史走势数据"]
        assert "累计收益率诊断" not in caplog.text, "无 bar 时诊断必须静默返回"


def _perf() -> SimpleNamespace:
    return SimpleNamespace(start=lambda *_a, **_k: None, stop=lambda *_a, **_k: None)


def _prepare(monkeypatch, *, history: dict | None, prep: dict, reporter: RecordingReporter, pipeline_data=None):
    monkeypatch.setattr("src.python.report._snapshot.fetch_history_data", lambda *_a, **_k: history)
    return frm._prepare_full_risk_metrics(
        holdings=[],
        config={},
        reporter=reporter,
        perf=_perf(),
        fetch_history=True,
        enable_history=True,
        prep=prep,
        pipeline_data=pipeline_data,
    )


class TestPrepareFullRiskMetrics:
    """全量指标装配：注入的键值与返回结构（不是内部调用次数）。"""

    def test_history_unavailable_keeps_prior_metrics_and_warns_checkpoint(self, monkeypatch, caplog):
        """history 缺失 → 返回 (None, None)、不覆盖既有 risk_metrics，并告警缺波动率键。"""
        prep: dict = {"risk_metrics": {}, "holdings_details": []}
        reporter = RecordingReporter()

        with caplog.at_level(logging.WARNING, logger="invest"):
            history, metrics = _prepare(monkeypatch, history=None, prep=prep, reporter=reporter)

        assert (history, metrics) == (None, None)
        assert prep["risk_metrics"] == {}, "无 history 时不得用空值覆盖既有指标"
        assert any("缺 annualized_volatility" in r.getMessage() for r in caplog.records), caplog.text
        assert reporter.warns == []

    def test_metrics_injected_with_alignment_and_scenario(self, monkeypatch):
        """数据齐备 → prep 与 metrics 拿到同一批指标键值，对齐摘要与情景分析注入。"""
        history = {
            "status": "ok",
            "annualized_volatility": 0.2,
            "max_drawdown_pct": 10.0,
            "total_return_pct": 5.0,
            "data_start": "2024-01-01",
            "data_end": "2025-01-01",
            "daily_returns_portfolio": [0.01, -0.02],
        }
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

        _history, metrics = _prepare(monkeypatch, history=history, prep=prep, reporter=RecordingReporter())

        assert prep["risk_metrics"] == {
            "annualized_volatility": 0.2,
            "max_drawdown_pct": 10.0,
            "total_return_pct": 5.0,
            "data_start": "2024-01-01",
            "data_end": "2025-01-01",
        }
        assert metrics["annualized_volatility"] == 0.2
        assert metrics["max_drawdown"] == pytest.approx(-0.1)
        assert metrics["alignment_summary"] == "2 只标的复权口径已修正"
        assert metrics["scenario_analysis"] is scenario
