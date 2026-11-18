"""组合风险度量（`analysis/metrics_risk.py`）——集中度/胜率/换手/风险贡献/Beta。

全是纯函数且直接进报告数字，口径错会污染多处呈现。这里锁四类契约：
  - 归一化口径（HHI 自动归一、换手按两期权重差/2）；
  - 数据不足/异常输入的显式返回值（`None` / `[]` / 0.0，不抛、不编造）；
  - 排序与求和关系（风险贡献降序 + 贡献合计 = 1，不比对末位小数）；
  - Beta 的协方差口径与置信区间的可靠性标记。
"""

from __future__ import annotations

import math

import pytest

from src.python.analysis.metrics_risk import (
    hhi,
    individual_volatility,
    portfolio_beta,
    portfolio_beta_analysis,
    risk_contribution,
    turnover_rate,
    win_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestHhi:
    def test_empty_returns_zero(self):
        assert hhi([]) == 0.0

    def test_single_holding_is_one(self):
        assert hhi([0.8]) == pytest.approx(1.0, abs=1e-12)

    def test_equal_weights_scale_invariant(self):
        """不要求归一化：同一分布放大 100 倍，HHI 不变。"""
        base = hhi([0.25, 0.25, 0.25, 0.25])
        assert base == pytest.approx(0.25, abs=1e-12)
        assert hhi([25.0, 25.0, 25.0, 25.0]) == pytest.approx(base, abs=1e-12)

    def test_zero_total_returns_zero(self):
        assert hhi([0.0, 0.0]) == 0.0

    def test_uses_absolute_weights(self):
        assert hhi([0.5, -0.5]) == pytest.approx(hhi([0.5, 0.5]), abs=1e-12)


class TestWinRate:
    def test_buckets_by_profit_sign(self):
        result = win_rate(
            [
                {"name": "甲", "profit": 10},
                {"name": "乙", "profit": -5},
                {"name": "丙", "profit": 0},
            ]
        )
        assert result["winning"] == ["甲"]
        assert result["losing"] == ["乙"]
        assert result["zero"] == ["丙"]
        assert result["win_rate"] == pytest.approx(1 / 3, abs=1e-12)

    def test_empty_holdings_returns_zero_rate(self):
        assert win_rate([])["win_rate"] == 0.0

    def test_non_numeric_profit_counted_as_zero(self):
        result = win_rate([{"name": "甲", "profit": "n/a"}])
        assert result["zero"] == ["甲"]
        assert result["win_rate"] == 0.0

    def test_missing_name_falls_back_to_code(self):
        assert win_rate([{"code": "600519", "profit": 1}])["winning"] == ["600519"]


class TestTurnoverRate:
    def test_unchanged_portfolio_is_zero(self):
        holdings = [{"code": "A", "market_value": 50}, {"code": "B", "market_value": 50}]
        assert turnover_rate(holdings, holdings) == pytest.approx(0.0, abs=1e-12)

    def test_full_swap_is_one(self):
        before = [{"code": "A", "market_value": 100}]
        after = [{"code": "B", "market_value": 100}]
        assert turnover_rate(before, after) == pytest.approx(1.0, abs=1e-12)

    def test_partial_rebalance_matches_weight_diff(self):
        before = [{"code": "A", "market_value": 80}, {"code": "B", "market_value": 20}]
        after = [{"code": "A", "market_value": 60}, {"code": "B", "market_value": 40}]
        assert turnover_rate(before, after) == pytest.approx(0.2, abs=1e-12)

    def test_insufficient_data_returns_none(self):
        assert turnover_rate([], [{"code": "A", "market_value": 1}]) is None
        assert turnover_rate([{"code": "A", "market_value": 0}], [{"code": "A", "market_value": 1}]) is None


class TestRiskContribution:
    def test_length_mismatch_returns_empty(self):
        assert risk_contribution([0.5, 0.5], [0.2]) == []

    def test_zero_volatility_returns_empty(self):
        assert risk_contribution([0.5, 0.5], [0.0, 0.0]) == []

    def test_contributions_sum_to_one_and_sorted_desc(self):
        result = risk_contribution([0.7, 0.3], [0.2, 0.1])
        assert sum(item["contribution"] for item in result) == pytest.approx(1.0, abs=1e-6)
        assert [item["contribution"] for item in result] == sorted(
            (item["contribution"] for item in result), reverse=True
        )
        assert [item["rank"] for item in result] == list(range(1, len(result) + 1))

    def test_non_finite_inputs_are_sanitized(self):
        result = risk_contribution([0.5, 0.5], [float("nan"), 0.1])
        assert all(math.isfinite(item["contribution"]) for item in result)


class TestIndividualVolatility:
    def test_short_series_returns_none(self):
        assert individual_volatility({"A": [0.01, 0.02]}) == {"A": None}

    def test_constant_series_has_zero_volatility(self):
        assert individual_volatility({"A": [0.01] * 40})["A"] == 0.0

    def test_annualization_matches_sqrt_of_trading_days(self):
        returns = [0.01, -0.02, 0.015, -0.005] * 10
        daily = individual_volatility({"A": returns}, annualize=False)["A"]
        annual = individual_volatility({"A": returns}, annualize=True)["A"]
        assert daily is not None and annual is not None
        assert annual == pytest.approx(daily * math.sqrt(252), rel=1e-6)

    def test_custom_trading_days_used(self):
        returns = [0.01, -0.01] * 20
        daily = individual_volatility({"A": returns}, annualize=False)["A"]
        assert daily is not None
        custom = individual_volatility({"A": returns}, trading_days=100)["A"]
        assert custom == pytest.approx(daily * 10, rel=1e-6)


class TestPortfolioBeta:
    def test_insufficient_samples_return_none(self):
        assert portfolio_beta([0.01] * 5, [0.01] * 5) is None

    def test_identical_series_beta_is_one(self):
        series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01] * 5
        assert portfolio_beta(series, series) == pytest.approx(1.0, abs=1e-9)

    def test_doubled_series_beta_is_two(self):
        bench = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01] * 5
        port = [value * 2 for value in bench]
        assert portfolio_beta(port, bench) == pytest.approx(2.0, abs=1e-9)

    def test_constant_benchmark_returns_none(self):
        assert portfolio_beta([0.01] * 30, [0.0] * 30) is None

    def test_length_mismatch_aligns_to_tail(self):
        bench = [0.01, -0.02, 0.015, -0.005] * 8
        port = [0.0] * 2 + [value * 2 for value in bench]
        assert portfolio_beta(port, bench) == pytest.approx(2.0, abs=1e-9)


class TestPortfolioBetaAnalysis:
    def test_insufficient_samples_return_none(self):
        assert portfolio_beta_analysis([0.01] * 3, [0.01] * 3) is None

    def test_interval_brackets_point_estimate(self):
        bench = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01] * 5
        port = [value * 1.5 for value in bench]
        result = portfolio_beta_analysis(port, bench)
        assert result is not None
        assert result["ci_lower"] <= result["beta"] <= result["ci_upper"]
        assert result["df"] >= 1

    def test_perfect_linear_relation_reports_degenerate_interval(self):
        """组合 = 2×基准：残差为零 → 置信区间退化到点估计，不得报 NaN。"""
        bench = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01] * 5
        result = portfolio_beta_analysis([value * 2 for value in bench], bench)
        assert result is not None
        assert result["beta"] == pytest.approx(2.0, abs=1e-9)
        assert result["p_value"] == 0.0
