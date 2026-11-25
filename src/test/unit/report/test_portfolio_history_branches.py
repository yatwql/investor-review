"""组合历史走势（`report/portfolio_history.py`）降级分支契约测试。

锁住的契约：
  - QDII 基金按名称走基金净值链路（不误派给股票 K 线链路）
  - 合并时间线为空时返回 unavailable 契约（不抛异常）
  - 单只持仓取数异常只记该只失败，其余持仓照常入走势
  - 最新行情格式异常（不可解包）时跳过终点回填，历史序列保持原样
  - 有效区间截断：日期表为空时返回空区间；首尾覆盖不足时截掉该端
  - 回撤跟踪记录峰值回撤的起止日
  - 基准指数获取为空 / 归一化全部失败均降级为空基准列表

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_portfolio_history_branches.py -v
"""

from __future__ import annotations

import pytest

from src.python.report.portfolio_history import PortfolioHistoryCalculator

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _series(dates: list[str], values: list[float]) -> list[dict]:
    return [{"date": d, "close": v, "value": v} for d, v in zip(dates, values)]


class TestQdiiRouting:
    """QDII 基金的链路路由。"""

    def test_qdii_name_routes_to_fund_nav(self, monkeypatch):
        calc = PortfolioHistoryCalculator()
        calls: list[str] = []

        def _fund_history(code, days=30):
            calls.append(code)
            return [{"date": "2026-03-02", "close": 2.0}]

        monkeypatch.setattr(calc, "_get_fund_history", _fund_history)
        monkeypatch.setattr(calc, "_get_stock_history", lambda *_a, **_k: pytest.fail("QDII 不得走股票 K 线链路"))

        result = calc.calculate_for_holding("270042", "广发纳斯达克100", 100.0, 30)

        assert calls == ["270042"]
        assert result is not None
        assert result[0]["value"] == pytest.approx(200.0)


class TestEmptyTimeline:
    """合并时间线为空的降级契约。"""

    def test_empty_merged_dates_yield_unavailable(self, monkeypatch):
        calc = PortfolioHistoryCalculator()
        monkeypatch.setattr(
            calc, "calculate_for_holding", lambda code, name, shares, days: _series(["2026-03-02"], [10.0])
        )
        monkeypatch.setattr(calc, "_merge_locf", lambda _all_series: ([], {}, {}))

        result = calc.get_combined_timeseries([("600519", "贵州茅台", 10.0)])

        assert result["bars"] == []
        assert result["status"] == "unavailable"
        assert result["monthly_returns"]["available"] is False, "无走势即月度收益日历不可用"


class TestFetchFailureIsolation:
    """单只持仓取数异常不影响其余持仓。"""

    def test_single_holding_exception_is_isolated(self, monkeypatch):
        calc = PortfolioHistoryCalculator()

        def _calc(code, name, shares, days=30):
            if code == "600519":
                raise RuntimeError("history boom")
            return _series(["2026-03-02", "2026-03-03"], [10.0, 11.0])

        monkeypatch.setattr(calc, "calculate_for_holding", _calc)

        result = calc.get_combined_timeseries([("600519", "贵州茅台", 10.0), ("000858", "五粮液", 5.0)])

        assert result["status"] == "degraded"
        assert result["successful_holdings"] == ["五粮液(000858)"]
        assert result["failed_holdings"] == ["贵州茅台(600519)"]


class TestLatestQuoteBackfill:
    """最新行情回填的格式容错。"""

    def test_unpackable_quote_skips_backfill(self):
        series = _series(["2026-03-02"], [10.0])

        patched = PortfolioHistoryCalculator._apply_latest_quote(series, {"600519": 5}, "600519", 100.0)

        assert patched is series, "行情格式异常时原序列不得被改动"


class TestTrimEffectiveRange:
    """有效区间截断的边界口径。"""

    def test_empty_dates_yield_empty_range(self):
        calc = PortfolioHistoryCalculator()

        assert calc._trim_effective_range([], {}, 3) == []

    def test_insufficient_head_coverage_is_trimmed(self):
        calc = PortfolioHistoryCalculator()
        dates = ["2026-03-02", "2026-03-03", "2026-03-04"]
        fund_count = {"2026-03-02": 1, "2026-03-03": 3, "2026-03-04": 3}

        assert calc._trim_effective_range(dates, fund_count, 3) == dates[1:]


class TestComputeDrawdown:
    """回撤跟踪的起止日取值。"""

    def test_peak_then_trough_records_drawdown_window(self):
        dates = ["2026-03-02", "2026-03-03", "2026-03-04"]
        date_map = {"2026-03-02": 100.0, "2026-03-03": 120.0, "2026-03-04": 90.0}

        bars, max_dd, max_dd_pct, start, end = PortfolioHistoryCalculator._compute_drawdown(dates, date_map)

        assert [b["total_value"] for b in bars] == [100.0, 120.0, 90.0]
        assert max_dd == pytest.approx(30.0)
        assert max_dd_pct == pytest.approx(25.0)
        assert (start, end) == ("2026-03-03", "2026-03-04")

    def test_first_date_below_peak_records_same_day_window(self):
        dates = ["2026-03-02", "2026-03-03"]
        date_map = {"2026-03-02": -5.0, "2026-03-03": 10.0}

        bars, max_dd, _pct, start, end = PortfolioHistoryCalculator._compute_drawdown(dates, date_map)

        assert bars[0]["total_value"] == -5.0
        assert max_dd == pytest.approx(5.0)
        assert (start, end) == ("2026-03-02", "2026-03-02"), "峰值未建立时的回撤窗口取当日（不得留空起点）"


class TestFetchBenchmarks:
    """基准指数取数与归一化的降级。"""

    def test_normalize_all_failed_degrades_to_empty(self, monkeypatch):
        calc = PortfolioHistoryCalculator(benchmark_indices={"sh000300": "沪深300"})
        monkeypatch.setattr("src.python.report.portfolio_history.fetch_benchmarks", lambda *a, **k: {"sh000300": [1]})
        monkeypatch.setattr("src.python.report.portfolio_history.normalize_benchmarks", lambda *a, **k: [])

        assert calc._fetch_benchmarks(_series(["2026-03-02"], [100.0]), 30) == []

    def test_no_raw_benchmark_degrades_to_empty(self, monkeypatch):
        calc = PortfolioHistoryCalculator(benchmark_indices={"sh000300": "沪深300"})
        monkeypatch.setattr("src.python.report.portfolio_history.fetch_benchmarks", lambda *a, **k: {})

        assert calc._fetch_benchmarks(_series(["2026-03-02"], [100.0]), 30) == []
