"""统计原语与因子公式的残差分支测试。

覆盖：
  - `_math_utils`：`_log_beta` 闭式值、`_incomplete_beta_cf` 端点短路、
    `_t_cdf(t=0)` 中位数 CDF（0.5，与两侧极限连续）、`_t_critical_95` 自由度下溢、
    `_beta_se` 样本不足与基准零方差两种退化
  - `_factor_formulas`：`_closes` 非法收盘价转 NaN、`_pearson` 有效对不足、
    `compute_factor_values` 空 bars / 标量 NaN 铺满 / 量价背离符号 / 收益偏度、
    `cross_sectional_series` 横截面日均值（成分数下限剔除 + 缺失值剔除）
"""

from __future__ import annotations

import math

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _bars(closes: list[float], volumes: list[float] | None = None, start_day: int = 1) -> list[dict]:
    """构造最小日线序列（close 涨跌交替，high/low/open 取 close 的邻域）。"""
    vols = volumes or [1000.0 + 10.0 * i for i in range(len(closes))]
    return [
        {
            "date": f"2026-01-{start_day + i:02d}",
            "open": c * 0.995,
            "high": c * 1.01,
            "low": c * 0.99,
            "close": c,
            "volume": v,
        }
        for i, (c, v) in enumerate(zip(closes, vols))
    ]


def test_log_beta_matches_closed_form():
    """`_log_beta` 等于 ln(B(a,b)) = lnΓ(a)+lnΓ(b)-lnΓ(a+b)。"""
    from src.python.analysis._math_utils import _log_beta

    assert _log_beta(2.0, 3.0) == pytest.approx(math.log(1.0 / 12.0))


@pytest.mark.parametrize(("x", "expected"), [(0.0, 0.0), (1.0, 1.0)])
def test_incomplete_beta_short_circuits_at_endpoints(x, expected):
    """正则化不完全 Beta 在 x≤0 / x≥1 处直接返回端点值（级数在端点发散）。"""
    from src.python.analysis._math_utils import _incomplete_beta_cf

    assert _incomplete_beta_cf(2.0, 3.0, x) == pytest.approx(expected)


def test_t_cdf_at_zero_is_median():
    """t=0 处 CDF 为 0.5：p 值不能因 x 恰为 1 而跳成 1.0。"""
    from src.python.analysis._math_utils import _t_cdf

    assert _t_cdf(0.0, 10) == pytest.approx(0.5, abs=1e-12)


def test_t_critical_95_underflows_to_first_table_row():
    """自由度小于表内最小键（df<1）时落到最小自由度临界值。"""
    from src.python.analysis._math_utils import _t_critical_95

    assert _t_critical_95(0) == pytest.approx(12.706)


def test_beta_se_returns_none_when_sample_too_short():
    """样本天数不足 22 时不给标准误（自由度不可用）。"""
    from src.python.analysis._math_utils import _beta_se

    portfolio = [0.01, -0.02, 0.03] * 5
    benchmark = [0.005, -0.01, 0.02] * 5

    assert _beta_se(portfolio, benchmark, 1.1) is None


def test_beta_se_returns_none_when_benchmark_has_zero_variance():
    """基准收益恒定时 Σ(x-x̄)²=0，标准误不可算。"""
    from src.python.analysis._math_utils import _beta_se

    portfolio = [0.001 * i for i in range(1, 25)]
    benchmark = [0.002] * 24

    assert _beta_se(portfolio, benchmark, 1.0) is None


def test_closes_turns_unparsable_close_into_nan():
    """非法收盘价（缺失/非数值）落 NaN 占位，不中断整列。"""
    from src.python.analysis._factor_formulas import _closes

    values = _closes([{"close": 10.0}, {"close": None}, {}])

    assert values[0] == pytest.approx(10.0)
    assert math.isnan(values[1])
    assert math.isnan(values[2])


def test_pearson_needs_three_valid_pairs():
    """有效配对少于 3 对时不给相关系数。"""
    from src.python.analysis._factor_formulas import _pearson

    assert _pearson([1.0, float("nan"), 3.0], [1.0, 2.0, 3.0]) is None


def test_compute_factor_values_empty_bars_returns_empty(monkeypatch):
    """bars 为空时不做任何计算，直接返回空序列。"""
    from src.python.analysis import _factor_formulas

    monkeypatch.setattr(_factor_formulas, "_daily_returns", lambda closes: [float("nan")] * len(closes))

    assert _factor_formulas.compute_factor_values("qlib_ma_cross", [], []) == []


def test_compute_factor_values_scalar_nan_fills_none():
    """标量为 NaN（基本面缺失）时整列落 None，而非把 NaN 当有效值传出。"""
    from src.python.analysis._factor_formulas import compute_factor_values

    bars = _bars([10.0, 11.0, 12.0])

    assert compute_factor_values("fund_roe", bars, [], scalar=float("nan")) == [None, None, None]


def test_pv_divergence_sign_flags_price_up_on_rising_volume():
    """量价同步（价格与量能同向上行）→ 背离值为 -1。"""
    from src.python.analysis._factor_formulas import compute_factor_values

    closes = [10.0 + 0.5 * i for i in range(30)]
    volumes = [1000.0 + 50.0 * i for i in range(30)]

    values = compute_factor_values("gtja_pv_divergence", _bars(closes, volumes), [])

    assert values[24] == pytest.approx(-1.0)


def test_pv_divergence_sign_flags_price_up_on_falling_volume():
    """价格上行而量能下行 → 背离值为 +1（另一侧符号）。"""
    from src.python.analysis._factor_formulas import compute_factor_values

    closes = [10.0 + 0.5 * i for i in range(30)]
    volumes = [3000.0 - 50.0 * i for i in range(30)]

    values = compute_factor_values("gtja_pv_divergence", _bars(closes, volumes), [])

    assert values[24] == pytest.approx(1.0)


def test_acad_skew_60_outputs_return_skewness():
    """60 日收益偏度按样本偏度公式出值（右偏序列为正）。"""
    from src.python.analysis._factor_formulas import compute_factor_values

    closes = [10.0]
    for i in range(70):
        closes.append(closes[-1] * (1.003 if i % 10 else 1.02))
    bars = _bars(closes)

    values = compute_factor_values("acad_skew_60", bars, [])

    assert values[65] is not None
    assert values[65] > 0


def test_cross_sectional_series_averages_and_drops_thin_days():
    """按日横截面均值：缺失值（None/NaN）剔除，成分数不足下限的日期不出值。"""
    from src.python.analysis._factor_formulas import cross_sectional_series
    from src.python.schemas.factor_catalog import MIN_CODES_PER_DAY

    thick_day = {"a": [(f"2026-02-{d:02d}", 0.1) for d in (1, 2)]}
    for code, value in (("b", 0.2), ("c", 0.3)):
        thick_day[code] = [(f"2026-02-{d:02d}", value) for d in (1, 2)]
    thick_day["d"] = [("2026-02-01", None), ("2026-02-02", float("nan"))]

    series = cross_sectional_series(thick_day)

    assert series == {"2026-02-01": pytest.approx(0.2), "2026-02-02": pytest.approx(0.2)}
    assert MIN_CODES_PER_DAY >= 3, "构造数据须达到成分数下限，否则本用例不验证下限剔除"
