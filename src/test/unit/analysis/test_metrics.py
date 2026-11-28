"""量化指标计算模块测试 — 覆盖 9 个核心指标的正、边缘、异常路径。

测试覆盖：
  1. sharpe_ratio — 正常计算 / 不足 20 日返回 None
  2. calmar_ratio — 正常计算 / 最大回撤小于阈值返回 None
  3. hhi — 等权集中度 1/N / 空列表返回 0
  4. win_rate — 全部盈利 / 全部亏损
  5. turnover_rate — 正常换手 / 空输入返回 None
  6. risk_contribution — 正常贡献度 / 空列表返回 []
  7. individual_volatility — 正常波动率 / 不足样本 None
  8. portfolio_beta — 正常 Beta / 不足样本 None
  9. portfolio_beta_analysis — 置信区间 / 统计检验 / 噪声 CI 宽度
"""

from __future__ import annotations


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

# ── 测试数据 Helpers ─────────────────────────────────────


def _make_positive_returns(n: int = 252, mean: float = 0.001, std: float = 0.01) -> list[float]:
    """生成日收益率序列（伪随机但确定性的振荡序列）。"""
    import hashlib

    rng = []
    for i in range(n):
        h = hashlib.md5(f"seed_{i}".encode()).hexdigest()
        v = mean + std * (int(h[:4], 16) / 65535 - 0.5) * 2
        rng.append(v)
    return rng


def _make_holdings(profits: list[float]) -> list[dict]:
    """生成指定盈亏的持仓列表。"""
    return [{"name": f"品种{i}", "code": f"00000{i}", "profit": p} for i, p in enumerate(profits)]


class TestSharpeRatio:
    """夏普比率测试。"""

    def test_normal_sharpe(self):
        """正常数据 → 返回正值（预期 > 0）。"""
        from src.python.analysis.metrics import sharpe_ratio

        returns = _make_positive_returns(252, 0.001, 0.01)
        sr = sharpe_ratio(returns, rf_annual=0.015)
        assert sr is not None
        assert sr > 0, f"预期正夏普比率，实际 {sr}"

    def test_insufficient_data_returns_none(self):
        """不足 20 日 → None。"""
        from src.python.analysis.metrics import sharpe_ratio

        assert sharpe_ratio([0.001] * 10) is None

    def test_matches_hand_computed_annualized_value(self):
        """21 日、无风险利率非零 → 夏普等于按四步公式手算的定值。

        样本：0.004/-0.002/0.003/-0.001 各 5 次 + 0.010 → 均值 0.0005，
        样本标准差按 (n-1) 口径；期望值由公式手算后固化为字面量。
        逐项敏感：超额收益的减号、方差分母、两处年化乘法、末步除法任一被换
        （`-`→`+`、`*`→`/`、`/`→`*`）都改变末位之前的量级。
        """
        from src.python.analysis.metrics import sharpe_ratio

        returns = [0.004, -0.002, 0.003, -0.001] * 5 + [0.010]
        sr = sharpe_ratio(returns, rf_annual=0.0175)
        assert sr == pytest.approx(6.704097506126198, rel=1e-9)

    def test_variance_at_epsilon_boundary_is_still_computed(self):
        """样本方差恰为 epsilon（1e-15）→ 不判为「零波动」，夏普仍返回数值。

        构造：`[a, -a] + [0]*19`（a = nextafter(1e-7)）的样本方差精确等于
        `1e-15`，故 `variance < eps` 为假、`variance <= eps` 为真——用恰等边界
        区分 `<` 与 `<=`。无风险利率取 0，超额收益为 0，期望夏普 0.0（不是 None）。
        """
        import math

        from src.python.analysis.metrics import sharpe_ratio

        a = math.nextafter(1e-7, 1.0)
        returns = [a, -a] + [0.0] * 19

        sr = sharpe_ratio(returns, rf_annual=0.0)
        assert sr is not None, "方差恰等于 epsilon 时不应按零波动判 None"
        assert sr == pytest.approx(0.0, abs=1e-12)


class TestCalmarRatio:
    """卡玛比率测试。"""

    def test_normal_calmar(self):
        """正常上升序列 → 卡玛比率应为正。"""
        from src.python.analysis.metrics import calmar_ratio

        returns = _make_positive_returns(252, 0.001, 0.01)
        cr = calmar_ratio(returns)
        assert cr is not None
        assert cr > 0, f"预期正卡玛比率，实际 {cr}"

    def test_flat_returns_returns_none(self):
        """近乎无波动 → 最大回撤小于阈值 → None。"""
        from src.python.analysis.metrics import calmar_ratio

        # 极小幅波动，最大回撤远低于 0.1%
        returns = [0.00001] * 252
        cr = calmar_ratio(returns)
        assert cr is None

    def test_matches_hand_computed_value(self):
        """先连涨 10 日（+1%×10）再单日 -5% → 卡玛 = 年化收益 / 5%。

        手算：复利终值 1.01^10×0.95，年化 = 终值^(252/21) - 1；最大回撤恰为 5%
        （峰值即第 10 日的复利值，随后一日跌 5%）。卡玛的分母口径（除以回撤幅度
        而非乘以）与年化收益的分子都在这个定值里锁住。
        """
        from src.python.analysis.metrics import calmar_ratio

        returns = [0.01] * 10 + [-0.05] + [0.0] * 10
        cr = calmar_ratio(returns)
        assert cr == pytest.approx(15.667947033448772, rel=1e-9)

    def test_missing_annual_return_or_drawdown_returns_none(self, monkeypatch):
        """年化收益或回撤任一为 None → 返回 None（不是「两者都 None」才返回）。"""
        from src.python.analysis import metrics_returns

        returns = [0.01, -0.02, 0.015, -0.005] * 10
        monkeypatch.setattr(metrics_returns, "annualized_return", lambda *a, **k: None)
        assert metrics_returns.calmar_ratio(returns) is None

        monkeypatch.undo()
        monkeypatch.setattr(metrics_returns, "max_drawdown_pct", lambda *a, **k: None)
        assert metrics_returns.calmar_ratio(returns) is None

    def test_drawdown_exactly_at_epsilon_is_not_dropped(self, monkeypatch):
        """最大回撤恰等于下限 → 仍计算卡玛（`<` 与 `<=` 的分界）。

        日收益 `[-0.5]` 单日 → 累计 0.5、峰值 1.0 → 回撤幅度精确为 0.5。
        把下限常量临时设为 0.5（测试侧构造边界，不改被测口径）：`0.5 < 0.5` 为假
        → 照常计算，`<=` 会误判为 0 回撤而返回 None。
        """
        from src.python.analysis import metrics_returns

        monkeypatch.setattr(metrics_returns, "_MAX_DRAWDOWN_EPSILON", 0.5)
        cr = metrics_returns.calmar_ratio([-0.5] + [0.0] * 20)
        assert cr == pytest.approx(-1.99951171875, rel=1e-9)


class TestMaxDrawdownPct:
    """最大回撤幅度（正数口径）测试。"""

    def test_multi_leg_drawdown_measures_from_peak(self):
        """先涨 10% 再两次各跌 10%/20% → 回撤从峰值算 = 28%。

        手算：1.10 → 0.99 → 0.792，相对峰值 1.10 的跌幅 = 1 - 0.792/1.10 = 0.28。
        用峰值为基准（而非起点 1.0）是本函数的口径。
        """
        from src.python.analysis.metrics import max_drawdown_pct

        returns = [0.10, -0.10, -0.20] + [0.0] * 21
        assert max_drawdown_pct(returns) == pytest.approx(0.28, abs=1e-12)


class TestHHI:
    """HHI 集中度指数测试。"""

    def test_equal_weights(self):
        """N 品种等权重 → HHI = 1/N。"""
        from src.python.analysis.metrics import hhi

        n = 10
        result = hhi([1.0 / n] * n)
        expected = 1.0 / n
        assert result == pytest.approx(expected, rel=1e-4), f"期望 {expected}，实际 {result}"

    def test_empty_weights_returns_zero(self):
        """空列表 → 0。"""
        from src.python.analysis.metrics import hhi

        assert hhi([]) == 0.0


class TestWinRate:
    """持仓胜率测试。"""

    def test_all_winning(self):
        """全部盈利 → 胜率 1.0。"""
        from src.python.analysis.metrics import win_rate

        holdings = _make_holdings([100, 200, 50])
        result = win_rate(holdings)
        assert result["win_rate"] == 1.0
        assert len(result["winning"]) == 3
        assert len(result["losing"]) == 0

    def test_all_losing(self):
        """全部亏损 → 胜率 0.0。"""
        from src.python.analysis.metrics import win_rate

        holdings = _make_holdings([-100, -200, -50])
        result = win_rate(holdings)
        assert result["win_rate"] == 0.0
        assert len(result["winning"]) == 0
        assert len(result["losing"]) == 3


class TestTurnoverRate:
    """换手率测试。"""

    def test_no_change_returns_zero(self):
        """两期完全一致 → 换手率 0。"""
        from src.python.analysis.metrics import turnover_rate

        data = [{"code": "A", "market_value": 100}, {"code": "B", "market_value": 200}]
        result = turnover_rate(data, data)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-4)

    def test_empty_before_returns_none(self):
        """空上期 → None。"""
        from src.python.analysis.metrics import turnover_rate

        after = [{"code": "A", "market_value": 100}]
        assert turnover_rate([], after) is None


class TestRiskContribution:
    """风险贡献测试。"""

    def test_equal_risk_contribution(self):
        """等权等波动率 → 贡献度均等。"""
        from src.python.analysis.metrics import risk_contribution

        n = 5
        result = risk_contribution([0.2] * n, [0.1] * n)
        assert len(result) == n
        for r in result:
            assert r["contribution"] == pytest.approx(1.0 / n, rel=1e-4)

    def test_empty_input_returns_empty(self):
        """空列表 → []。"""
        from src.python.analysis.metrics import risk_contribution

        assert risk_contribution([], []) == []


class TestIndividualVolatility:
    """个股波动率测试。"""

    def test_normal_volatility(self):
        """正常序列 → 返回正值波动率。"""
        from src.python.analysis.metrics import individual_volatility

        returns = _make_positive_returns(252, 0.0, 0.02)
        result = individual_volatility({"A": returns})
        vol = result.get("A")
        assert vol is not None
        assert vol > 0, f"预期正波动率，实际 {vol}"

    def test_insufficient_data_returns_none(self):
        """不足 20 日 → None。"""
        from src.python.analysis.metrics import individual_volatility

        result = individual_volatility({"A": [0.001] * 10})
        assert result.get("A") is None


class TestPortfolioBeta:
    """组合 Beta 测试。"""

    def test_beta_near_one(self):
        """组合与基准高度正相关 → Beta ≈ 1。"""
        from src.python.analysis.metrics import portfolio_beta

        # 生成高度相关的收益率序列
        base = _make_positive_returns(252, 0.001, 0.01)
        portfolio = [b + 0.0001 for b in base]  # 非常接近基准
        beta = portfolio_beta(portfolio, base)
        assert beta is not None
        assert abs(beta - 1.0) < 0.5, f"期望接近 1，实际 {beta}"

    def test_insufficient_data_returns_none(self):
        """不足 20 日 → None。"""
        from src.python.analysis.metrics import portfolio_beta

        assert portfolio_beta([0.001] * 10, [0.002] * 10) is None


class TestPortfolioBetaAnalysis:
    """组合 Beta 置信区间与统计检验。"""

    def test_analysis_returns_all_keys(self):
        """正常数据返回完整字典。"""
        from src.python.analysis.metrics import portfolio_beta_analysis

        base = _make_positive_returns(252, 0.001, 0.01)
        portfolio = [b for b in base]  # 同序列 → Beta=1
        result = portfolio_beta_analysis(portfolio, base)
        assert result is not None
        expected_keys = {"beta", "ci_lower", "ci_upper", "t_stat", "p_value", "reliable", "df"}
        assert set(result.keys()) == expected_keys, f"缺失键：{expected_keys - set(result.keys())}"

    def test_beta_one_analysis(self):
        """Beta=1 时 CI 紧密，p 值显著。"""
        from src.python.analysis.metrics import portfolio_beta_analysis

        base = _make_positive_returns(252, 0.001, 0.01)
        result = portfolio_beta_analysis(base, base)  # 完全相同 → Beta=1
        assert result is not None
        assert abs(result["beta"] - 1.0) < 0.5
        assert result["ci_lower"] is not None and result["ci_lower"] <= result["beta"]
        assert result["ci_upper"] is not None and result["ci_upper"] >= result["beta"]
        assert result["p_value"] == 0.0  # 完美相关 → 零不确定性
        assert result["reliable"] is True
        assert result["df"] > 0

    def test_unrelated_returns_beta_near_zero(self):
        """不相关序列 → Beta≈0，p 值不显著。"""
        from src.python.analysis.metrics import portfolio_beta_analysis
        import random

        random.seed(123)
        n = 252
        base = [random.gauss(0.001, 0.015) for _ in range(n)]
        unrelated = [random.gauss(0.001, 0.02) for _ in range(n)]
        result = portfolio_beta_analysis(unrelated, base)
        assert result is not None
        assert abs(result["beta"]) < 0.5
        assert result["p_value"] > 0.05  # 不显著

    def test_high_beta_ci(self):
        """Beta>1 时 CI 包含 Beta 值。"""
        from src.python.analysis.metrics import portfolio_beta_analysis
        import random

        random.seed(42)
        base = [random.gauss(0.001, 0.015) for _ in range(252)]
        portfolio = [b * 1.5 + random.gauss(0.0, 0.005) for b in base]
        result = portfolio_beta_analysis(portfolio, base)
        assert result is not None
        assert result["beta"] > 1.0
        assert result["ci_lower"] <= result["beta"]
        assert result["ci_upper"] >= result["beta"]
        assert result["df"] > 0

    def test_insufficient_data_returns_none(self):
        """不足 20 日 → None。"""
        from src.python.analysis.metrics import portfolio_beta_analysis

        assert portfolio_beta_analysis([0.001] * 10, [0.002] * 10) is None

    def test_flat_returns_none(self):
        """无波动基准 → None。"""
        from src.python.analysis.metrics import portfolio_beta_analysis

        assert portfolio_beta_analysis([0.001] * 252, [0.0] * 252) is None

    def test_high_noise_ci_wider(self):
        """高噪声 → CI 更宽。"""
        from src.python.analysis.metrics import portfolio_beta_analysis
        import random

        random.seed(42)
        n = 252
        base = [random.gauss(0.0, 0.015) for _ in range(n)]
        # 低噪声 → 窄 CI
        low_noise = [b * 1.0 + random.gauss(0.0, 0.005) for b in base]
        # 高噪声 → 宽 CI
        high_noise = [b * 1.0 + random.gauss(0.0, 0.05) for b in base]

        r1 = portfolio_beta_analysis(low_noise, base)
        r2 = portfolio_beta_analysis(high_noise, base)
        assert r1 is not None and r2 is not None

        ci_w1 = r1["ci_upper"] - r1["ci_lower"]
        ci_w2 = r2["ci_upper"] - r2["ci_lower"]
        assert ci_w2 > ci_w1, "高噪声应产生更宽的置信区间"

    def test_compute_all_metrics_includes_analysis(self):
        """compute_all_metrics 包含 beta_analysis 键。"""
        from src.python.analysis.metrics import compute_all_metrics

        base = _make_positive_returns(252, 0.001, 0.01)
        portfolio = [b for b in base]
        result = compute_all_metrics(
            portfolio, benchmark_daily_returns=base, rf_annual=0.02, portfolio_weights=[1.0], individual_vols={"A": 0.2}
        )
        assert "beta_analysis" in result
        assert result["beta_analysis"] is not None
        assert isinstance(result["beta_analysis"], dict)


# ── 数值清理函数测试 ──────────────────────────────────────


class TestSanitizeMetric:
    """数值清理测试。"""

    def test_nan_returns_default(self):
        from src.python.analysis.metrics import sanitize_metric

        assert sanitize_metric(float("nan")) is None
        assert sanitize_metric(float("nan"), 0.0) == 0.0

    def test_inf_returns_default(self):
        from src.python.analysis.metrics import sanitize_metric

        assert sanitize_metric(float("inf")) is None
        assert sanitize_metric(float("-inf")) is None

    def test_normal_value_passes_through(self):
        from src.python.analysis.metrics import sanitize_metric

        assert sanitize_metric(1.5) == 1.5
        assert sanitize_metric(0) == 0


class TestTruncateExtremeValues:
    """极端值截断测试。"""

    def test_no_extremes_unchanged(self):
        from src.python.analysis.metrics import truncate_extreme_values

        data = [0.1, 0.2, 0.3]
        result = truncate_extreme_values(data)
        assert result == data

    def test_outliers_truncated(self):
        from src.python.analysis.metrics import truncate_extreme_values

        # 两端极端值各占 1%，分位数上下界都落在中间档位 0.01 → 截断必须把极端值拉回
        data = [-9.0] + [0.01] * 98 + [9.0]
        result = truncate_extreme_values(data, lower_quantile=0.1, upper_quantile=0.9)
        allowed_levels = {min(data[1:-1]), max(data[1:-1])}
        assert len(result) == len(data)
        # 截断后每个取值都属于允许档位（中间档位 / 分位数端点），原始极端值不得残留
        assert set(result) <= allowed_levels
        assert -9.0 not in result
        assert 9.0 not in result


class TestCheckDataSufficiency:
    """数据充分性检查测试。"""

    def test_full_year_data_high_confidence(self):
        from src.python.analysis.metrics import check_data_sufficiency

        assert check_data_sufficiency([0.001] * 252) == 2

    def test_short_data_insufficient(self):
        from src.python.analysis.metrics import check_data_sufficiency

        assert check_data_sufficiency([0.001] * 10) == 0

    def test_empty_data_insufficient(self):
        from src.python.analysis.metrics import check_data_sufficiency

        assert check_data_sufficiency([]) == 0

    def test_exactly_min_days_is_low_confidence(self):
        """恰好等于最小样本天数 → 低置信度而非 0（不足判定是严格小于）。"""
        from src.python.analysis.metrics import check_data_sufficiency

        assert check_data_sufficiency([0.001] * 20, min_days=20) == 1


class TestComputePortfolioPeakMv:
    """组合历史峰值市值（回撤纪律基准）计算测试。"""

    def test_peak_is_historical_max(self):
        """bars 含中途峰值 → 返回最大值（含首日）。"""
        from src.python.analysis.metrics import compute_portfolio_peak_mv

        bars = [
            {"date": "2026-01-01", "total_value": 100.0},
            {"date": "2026-01-02", "total_value": 120.0},
            {"date": "2026-01-03", "total_value": 90.0},
            {"date": "2026-01-04", "total_value": 110.0},
        ]
        assert compute_portfolio_peak_mv(bars) == pytest.approx(120.0)

    def test_peak_ignores_nonpositive_placeholder(self):
        """0/负值占位（缺失/清仓）不参与峰值。"""
        from src.python.analysis.metrics import compute_portfolio_peak_mv

        bars = [
            {"date": "2026-01-01", "total_value": 0.0},
            {"date": "2026-01-02", "total_value": 100.0},
            {"date": "2026-01-03", "total_value": 0.0},
            {"date": "2026-01-04", "total_value": 80.0},
        ]
        assert compute_portfolio_peak_mv(bars) == pytest.approx(100.0)

    def test_peak_none_on_empty_or_all_nonpositive(self):
        """None / 空序列 / 全非正值 → None（峰值未知，回撤纪律不激活）。"""
        from src.python.analysis.metrics import compute_portfolio_peak_mv

        assert compute_portfolio_peak_mv(None) is None
        assert compute_portfolio_peak_mv([]) is None
        assert compute_portfolio_peak_mv([{"date": "2026-01-01", "total_value": 0.0}]) is None
        assert compute_portfolio_peak_mv([{"date": "2026-01-01", "total_value": -5.0}]) is None


class TestComputeDailyReturns:
    """日收益率口径（统一源）：空输入返回空列表，而非 None。"""

    def test_empty_input_returns_empty_list(self):
        from src.python.analysis.metrics import compute_daily_returns

        assert compute_daily_returns(None) == []
        assert compute_daily_returns([]) == []


class TestComputeAllMetricsDerivedFields:
    """全量聚合里派生出的 HHI 等效数 / 换手率 / 个股波动率 / 风险贡献。"""

    def test_hhi_equivalent_is_reciprocal_of_hhi(self):
        """等权两品种 → HHI 0.5、等效品种数 2.0（是 1/HHI 而非 HHI 本身）。"""
        from src.python.analysis.metrics import compute_all_metrics

        result = compute_all_metrics([], portfolio_weights=[0.5, 0.5])

        assert result["hhi"] == pytest.approx(0.5)
        assert result["hhi_equivalent"] == pytest.approx(2.0)

    def test_turnover_needs_both_periods(self, monkeypatch):
        """只给上期持仓（本期为 None）→ 换手率为 None，且不调用 turnover_rate。"""
        from src.python.analysis import metrics

        calls: list = []
        monkeypatch.setattr(metrics, "turnover_rate", lambda before, after: calls.append((before, after)) or 0.5)

        result = metrics.compute_all_metrics([], holdings_before=[{"code": "600900", "shares": 100}])

        assert result["turnover_rate"] is None
        assert calls == []

    def test_individual_volatility_passed_through(self):
        """传入个股波动率字典 → 原样透出，不被抹成 None。"""
        from src.python.analysis.metrics import compute_all_metrics

        vols = {"600900": 0.21}

        result = compute_all_metrics([], individual_vols=vols)

        assert result["individual_volatility"] == vols

    def test_risk_contributions_empty_without_individual_vols(self):
        """有权重但无个股波动率 → 风险贡献为空（不去对 None 取 values）。"""
        from src.python.analysis.metrics import compute_all_metrics

        result = compute_all_metrics([], portfolio_weights=[0.6, 0.4], individual_vols=None)

        assert result["risk_contributions"] == []

    def test_missing_volatility_padded_with_zero(self):
        """波动率条目少于权重 → 缺的按 0 补齐，仍逐品种出贡献条目。"""
        from src.python.analysis.metrics import compute_all_metrics

        weights = [0.6, 0.4]

        result = compute_all_metrics([], portfolio_weights=weights, individual_vols={"600900": 0.2})

        assert len(result["risk_contributions"]) == len(weights)
