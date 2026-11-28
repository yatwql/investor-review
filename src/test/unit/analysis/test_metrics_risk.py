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

    def test_exactly_min_sample_days_is_enough(self):
        """样本数恰等于下限 20 → 照常计算（`<` 与 `<=` 的分界）。

        `[0.01, -0.01]`×10 的均值为 0，样本方差 = 0.002/19，
        日波动率 = sqrt(0.002/19)，手算后固化为字面量：
        分母口径（n-1 而非 n+1）也在其中锁死。
        """
        returns = [0.01, -0.01] * 10
        daily = individual_volatility({"A": returns}, annualize=False)["A"]
        assert daily is not None, "20 个样本已达标，不应判数据不足"
        assert daily == pytest.approx(0.01025978352085154, rel=1e-9)
        annual = individual_volatility({"A": returns})["A"]
        assert annual == pytest.approx(0.1628690142091911, rel=1e-9)

    def test_variance_at_epsilon_boundary_is_computed_not_zeroed(self):
        """样本方差恰等于 epsilon（1e-15）→ 按 sqrt 计算，而非报 0.0。

        构造 `[a, -a] + [0]*19`（a = nextafter(1e-7)）使样本方差精确为 `1e-15`：
        `variance < eps` 为假、`variance <= eps` 为真，恰等边界区分两个算子。
        """
        a = math.nextafter(1e-7, 1.0)
        daily = individual_volatility({"A": [a, -a] + [0.0] * 19}, annualize=False)["A"]
        assert daily == pytest.approx(math.sqrt(1e-15), rel=1e-9)
        assert daily != 0.0


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

    def test_exactly_min_sample_days_on_both_sides(self):
        """两侧长度恰等于下限 20 → 计算 Beta（`<` 与 `<=` 的分界，两侧各一条）。"""
        bench = [0.01, -0.01] * 10
        port = [value * 2 for value in bench]
        assert portfolio_beta(port, bench) == pytest.approx(2.0, abs=1e-9)
        assert portfolio_beta(bench, port) == pytest.approx(0.5, abs=1e-9)

    def test_only_one_side_short_returns_none(self):
        """只有一侧不足 20 日 → 仍返回 None（不是「两侧都不足」才返回）。"""
        bench = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01] * 4
        assert portfolio_beta([0.01, -0.01] * 2 + [0.005], bench) is None
        assert portfolio_beta(bench, [0.01, -0.01] * 2 + [0.005]) is None

    def test_centered_beta_ignores_mean_level(self):
        """基准均值非零时，组合 = 2×基准 + 0.5 仍得 Beta = 2。

        锁住协方差口径：均值中心化（两侧各减自己的均值）与 (n-1) 分母任一被改，
        平移不变性即失效——均值项会跟着「水平」偏移，Beta 随之偏离 2。
        """
        bench = [0.01, 0.012, 0.008, 0.011, 0.009, 0.013] * 4
        port = [value * 2 + 0.5 for value in bench]
        assert portfolio_beta(port, bench) == pytest.approx(2.0, rel=1e-9)


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

    def test_sample_too_short_for_standard_error_reports_point_estimate_only(self):
        """20 日（点估计够、标准误自由度不够）→ 返回点估计 + 区间字段 None。

        不得整份结果退化为 None：调用方需要 beta 才能继续，只应降级区间与检验字段。
        """
        bench = [0.01, -0.01] * 10
        noise = [0.02, -0.015, 0.018, -0.022, 0.019, -0.017, 0.021, -0.023, 0.016, -0.019] * 2
        port = [value * 1.2 + delta for value, delta in zip(bench, noise)]

        result = portfolio_beta_analysis(port, bench)
        assert result is not None
        assert result["beta"] == pytest.approx(3.1, abs=1e-9)
        assert result["ci_lower"] is None
        assert result["ci_upper"] is None
        assert result["reliable"] is False
        assert result["df"] == 0

    def test_t_stat_and_p_value_match_hand_computed_values(self):
        """点估计 1.695、df 22 的含噪序列 → t 统计量与双侧 p 值为定值。

        t = beta / se（除号），p = 2×P(T<=-|t|)（乘 2 的双侧换算）：
        除号被换成乘、或双侧乘 2 被换成除 2，两个量级都会成倍偏离。
        p 值极小，故 `approx` 的绝对容差必须显式归零（默认 1e-12 会把
        4e-26 与 1.6e-25 这类差异当成零，断言退化为恒真）。
        """
        bench = [0.01, -0.01, 0.012, -0.008] * 6
        noise = [0.006, -0.005, 0.004, -0.007, 0.005, -0.003] * 4
        port = [value * 1.2 + delta for value, delta in zip(bench, noise)]

        result = portfolio_beta_analysis(port, bench)
        assert result is not None
        assert result["t_stat"] == pytest.approx(57.75129555197038, rel=1e-9)
        assert result["p_value"] == pytest.approx(1.614308306842165e-25, rel=1e-6, abs=0.0)

    def test_noisy_estimate_widens_interval_and_flags_unreliable(self):
        """残差远大于基准波动 → 置信区间宽度 > 1.5 → reliable 为 False。

        宽度按 `(上界 - 下界)` 算：界限任一被换成恒 0、`<=` 判据被换成 `or`，
        「太宽不可靠」的标记都会恒真。
        """
        bench = [0.002, -0.002] * 12
        noise = [0.05, -0.02, 0.04, -0.06, 0.03, -0.05] * 4
        port = [value * 1.2 + delta for value, delta in zip(bench, noise)]

        result = portfolio_beta_analysis(port, bench)
        assert result is not None
        assert result["ci_upper"] - result["ci_lower"] > 1.5
        assert result["reliable"] is False

    def test_interval_width_exactly_threshold_is_reliable(self, monkeypatch):
        """区间宽度恰为 1.5 → 仍判可靠（`<=` 与 `<` 的分界）。

        se 与 t 临界值钉成 (0.5, 1.5)，beta = 1 → 半宽 0.75，宽度精确 1.5。
        """
        from src.python.analysis import metrics_risk

        bench = [0.01, -0.01] * 10
        monkeypatch.setattr(metrics_risk, "_beta_se", lambda *args, **kwargs: (0.5, 22))
        monkeypatch.setattr(metrics_risk, "_t_critical_95", lambda df: 1.5)

        result = metrics_risk.portfolio_beta_analysis(bench, bench)
        assert result is not None
        assert result["ci_upper"] - result["ci_lower"] == pytest.approx(1.5, abs=1e-12)
        assert result["reliable"] is True
