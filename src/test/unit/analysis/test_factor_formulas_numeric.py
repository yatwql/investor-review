"""因子公式的数值口径测试（`analysis/_factor_formulas`）。

为什么单独成文件：该模块既有用例多数只断「非 None / 落在范围内 / 单调」，而
`+`→`-`、`/`→`*`、`<`→`<=` 这类算术与边界替换在这类断言下会等价通过（变异得
分实测偏低即由此暴露）。本文件按公式逐一给**可手算的期望数值**，每条期望值在
注释里写明推导，目标断言是「算错就失败」而不是「有值就行」。

覆盖：`_mean` / `_std` / `_pearson` / `_ema` / `_rolling_beta` / `_daily_returns` /
`_aligned_index_returns` 七个原语 + `compute_factor_values` 全部公式分支 +
`cross_sectional_series` 的横截面均值。
"""

from __future__ import annotations

import math

import pytest

from src.python.analysis._factor_formulas import (
    _aligned_index_returns,
    _daily_returns,
    _ema,
    _mean,
    _pearson,
    _rolling_beta,
    _std,
    compute_factor_values,
    cross_sectional_series,
)
from src.python.schemas.factor_catalog import MIN_CODES_PER_DAY

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _bars(
    closes: list[float | None],
    *,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> list[dict]:
    """构造日线序列（未显式给出的价量取收盘价/固定量；close=None 表示坏价）。"""
    n = len(closes)
    opens = opens or [10.0 if c is None else float(c) for c in closes]
    highs = highs or [10.0 if c is None else float(c) for c in closes]
    lows = lows or [10.0 if c is None else float(c) for c in closes]
    volumes = volumes or [100.0] * n
    dates = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    return [
        {
            "date": dates[i],
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": float("nan") if closes[i] is None else closes[i],
            "volume": volumes[i],
        }
        for i in range(n)
    ]


# ── 统计原语（逐式手算） ──


def test_mean_averages_valid_values_only():
    """`_mean` = Σ有效值 / 有效个数：NaN 剔除，不参与分母。"""
    assert _mean([1.0, float("nan"), 3.0]) == pytest.approx(2.0)
    assert _mean([float("nan")]) is None


def test_std_uses_sample_denominator():
    """`_std` = √(Σ(v-m̄)²/(n-1))：[1,2,3] → m̄=2，Σ=2，/2=1，√1=1。"""
    assert _std([1.0, 2.0, 3.0]) == pytest.approx(1.0, rel=1e-9)


def test_std_needs_two_values():
    """样本标准差在 n=1 时不可算（返回 None），n=2 时已可算（√2）。"""
    assert _std([5.0]) is None
    assert _std([1.0, 3.0]) == pytest.approx(math.sqrt(2.0), rel=1e-9)


def test_pearson_three_nanfree_pairs_yield_half():
    """3 对非共线样本已出相关系数：[1,2,3] vs [1,3,2] → 1/2（不是 None）。"""
    assert _pearson([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]) == pytest.approx(0.5, rel=1e-9)


def test_pearson_pairs_with_nan_are_dropped():
    """任一侧为 NaN 的配对整体剔除，剩余 3 对仍出相关系数 1/2。"""
    values = _pearson([1.0, 2.0, 3.0, float("nan")], [1.0, 3.0, 2.0, 4.0])

    assert values == pytest.approx(0.5, rel=1e-9)


def test_ema_matches_manual_recursion():
    """EMA(span=3, α=0.5)：10→20→30→40 手算为 10 / 15 / 22.5 / 31.25，首两个为 None。"""
    assert _ema([10.0, 20.0, 30.0, 40.0], 3) == [
        None,
        None,
        pytest.approx(22.5, rel=1e-9),
        pytest.approx(31.25, rel=1e-9),
    ]


def test_rolling_beta_recovers_double_exposure():
    """组合收益恒为指数 2 倍 → 协方差/方差 = 2（window=2 时逐窗成立）。"""
    rets = [0.02, -0.01, 0.03, -0.02]
    mkt = [0.01, -0.005, 0.015, -0.01]

    betas = _rolling_beta(rets, mkt, 2)

    assert betas[0] is None, "首窗不足 window 天，不出值"
    assert betas[1:] == [pytest.approx(2.0, rel=1e-9)] * 3


def test_rolling_beta_none_when_index_has_zero_variance():
    """指数收益恒 0 → 方差为 0，Beta 无定义（返回 None 而不是除零）。"""
    betas = _rolling_beta([0.01, 0.02, 0.03], [0.0, 0.0, 0.0], 2)

    assert betas[1] is None


def test_daily_returns_divides_by_previous_close():
    """日收益 = 今收/昨收 − 1：[100,110,99] → [NaN, 0.1, −0.1]。"""
    rets = _daily_returns([100.0, 110.0, 99.0])

    assert math.isnan(rets[0])
    assert rets[1] == pytest.approx(0.1, rel=1e-9)
    assert rets[2] == pytest.approx(-0.1, rel=1e-9)


def test_daily_returns_zero_previous_close_is_nan():
    """昨日收盘价为 0 时当日收益不可算，落 NaN 而非除零；次日恢复正常口径。"""
    rets = _daily_returns([0.0, 5.0, 6.0])

    assert math.isnan(rets[1])
    assert rets[2] == pytest.approx(0.2, rel=1e-9)


def test_aligned_index_returns_uses_previous_index_close():
    """对齐指数收益 = 指数今收/指数昨收 − 1；首日与缺日与坏价一律 NaN。"""
    bars = _bars([1.0, 1.0, 1.0, 1.0])
    index_bars = [
        {"date": bars[0]["date"], "close": 100.0},
        {"date": bars[1]["date"], "close": 110.0},
        {"date": bars[3]["date"], "close": None},
    ]

    values = _aligned_index_returns(bars, index_bars)

    assert math.isnan(values[0]), "指数首日无昨收"
    assert values[1] == pytest.approx(0.1, rel=1e-9)
    assert math.isnan(values[2]), "今日在指数序列中缺日"
    assert math.isnan(values[3]), "指数今日价为坏价"


# ── 公式分支（window 取自 factor_catalog，期望值逐式手算） ──


def test_ma_cross_deviation_from_preceding_mean():
    """qlib_ma_cross(20)：closes=10..30，ma=mean(10..29)=19.5 → (30−19.5)/19.5 = 7/13。"""
    values = compute_factor_values("qlib_ma_cross", _bars([10.0 + i for i in range(21)]), [])

    assert values[19] is None, "窗口未满不出值"
    assert values[20] == pytest.approx(7.0 / 13.0, rel=1e-9)


def test_macd_hist_is_diff_minus_signal():
    """qlib_macd_hist：closes=100+2i（41 根），快慢 EMA 与信号线 EMA 逐根手算。"""
    closes = [100.0 + 2.0 * i for i in range(41)]

    values = compute_factor_values("qlib_macd_hist", _bars(closes), [])

    assert values[40] == pytest.approx(0.756257080087245, rel=1e-9)


def test_rsi_is_gain_share_of_total_move():
    """qlib_rsi_14：收益交替 +10% / −5%，14 个收益中 7 涨 7 跌 →
    100×0.7/(0.7+0.35) = 66.666…（不是 50，也不是 100）。"""
    closes = [100.0]
    for i in range(1, 16):
        closes.append(closes[-1] * (1.1 if i % 2 else 0.95))

    values = compute_factor_values("qlib_rsi_14", _bars(closes), [])

    assert values[14] == pytest.approx(66.66666666666666, rel=1e-9)


def test_rsi_flat_series_is_neutral_fifty():
    """qlib_rsi_14：价格恒定时涨跌和为零 → 50.0（该分支不得落入除零）。"""
    values = compute_factor_values("qlib_rsi_14", _bars([10.0] * 16), [])

    assert values[15] == pytest.approx(50.0)


def test_beta_60_is_one_for_identical_portfolio_and_index():
    """qlib_beta_60：组合与指数逐日同价 → 收益完全相同 → Beta = 1。"""
    closes = [100.0 + i for i in range(61)]

    values = compute_factor_values("qlib_beta_60", _bars(closes), _bars(closes))

    # 首日收益为 NaN，双侧同填 0 后仍同值 → 两个满窗都为 1
    assert values[58] is None, "窗口未满不出值"
    assert values[59:] == [pytest.approx(1.0, rel=1e-9)] * 2


def test_aroon_uses_window_positions_of_extremes():
    """qlib_aroon_25：窗口内高点在第 7 根（k=6）、低点在第 19 根（k=18）→
    up=100×18/24=75，down=100×6/24=25 → (75−25)/100 = 0.5。"""
    highs = [10.0] * 26
    lows = [5.0] * 26
    highs[7] = 20.0
    lows[19] = 1.0

    values = compute_factor_values("qlib_aroon_25", _bars([8.0] * 26, highs=highs, lows=lows), [])

    assert values[25] == pytest.approx(0.5, rel=1e-9)


def test_aroon_monotone_series_is_minus_one():
    """qlib_aroon_25：价格单调上行（高点在窗口末、低点在窗口首）→ up=0, down=100 → −1。"""
    closes = [10.0 + i for i in range(26)]
    values = compute_factor_values("qlib_aroon_25", _bars(closes, highs=closes, lows=closes), [])

    assert values[25] == pytest.approx(-1.0)


def test_corr_cv_is_negative_price_volume_correlation():
    """alpha_corr_cv_10：收盘价与成交量同步上行（r=+1）→ 因子值 = −r = −1。"""
    closes = [10.0 + i for i in range(11)]
    volumes = [100.0 + 10.0 * i for i in range(11)]

    values = compute_factor_values("alpha_corr_cv_10", _bars(closes, volumes=volumes), [])

    assert values[10] == pytest.approx(-1.0)


def test_corr_cv_20_is_negative_price_volume_correlation():
    """alpha_corr_cv_20：同上口径（window=20），r=+1 → −1。"""
    closes = [10.0 + i for i in range(21)]
    volumes = [100.0 + 10.0 * i for i in range(21)]

    values = compute_factor_values("alpha_corr_cv_20", _bars(closes, volumes=volumes), [])

    assert values[20] == pytest.approx(-1.0)


def test_rev_open_uses_open_prices_not_closes():
    """alpha_rev_open_10：开盘价与成交量反向（r=−1）→ 因子值 = −r = +1。

    与 `alpha_corr_cv_10` 的差异只在「取开盘价还是收盘价」：此处的收盘价与成交量
    同步上行，若误用收盘价，结果会是 −1 而不是 +1。
    """
    closes = [10.0 + i for i in range(11)]
    opens = [20.0 - i for i in range(11)]
    volumes = [100.0 + 10.0 * i for i in range(11)]

    values = compute_factor_values("alpha_rev_open_10", _bars(closes, opens=opens, volumes=volumes), [])

    assert values[10] == pytest.approx(1.0)


def test_pvt_is_volume_weighted_price_change_per_unit_volume():
    """alpha_pvt_10：Σ(Δclose×vol)/Σvol，窗口 10 根。

    Δclose = +2,−1,+2,−1,…；vol = 200,300,…,1100 →
    Σ(Δclose×vol)=2×(200+400+…)+(−1)×(300+500+…) 归一后为 0.384615…（=5/13）。
    """
    closes = [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0, 15.0, 14.0, 16.0, 15.0]
    volumes = [100.0 * (k + 1) for k in range(11)]

    values = compute_factor_values("alpha_pvt_10", _bars(closes, volumes=volumes), [])

    assert values[10] == pytest.approx(5.0 / 13.0, rel=1e-9)


def test_vwma_deviation_from_volume_weighted_mean():
    """alpha_vwma_dev_20：窗内 20 根收 10 元（量 100），末根收 20 元（量 1000）→
    vwma=(20×10×100+20×1000)/(20×100+1000)=40000/3000=13.333… → (20−13.333)/13.333=0.5。
    """
    closes = [10.0] * 20 + [20.0]
    volumes = [100.0] * 20 + [1000.0]

    values = compute_factor_values("alpha_vwma_dev_20", _bars(closes, volumes=volumes), [])

    assert values[20] == pytest.approx(0.5, rel=1e-9)


def test_mom_20_is_total_return_over_window():
    """gtja_mom_20：closes=10..30 → 30/10 − 1 = 2.0。"""
    values = compute_factor_values("gtja_mom_20", _bars([10.0 + i for i in range(21)]), [])

    assert values[20] == pytest.approx(2.0)


def test_bias_60_deviation_from_preceding_mean():
    """gtja_bias_60：closes=10..70，ma=mean(10..69)=39.5 → (70−39.5)/39.5 = 0.7721518…。"""
    values = compute_factor_values("gtja_bias_60", _bars([10.0 + i for i in range(61)]), [])

    assert values[60] == pytest.approx(0.7721518987341772, rel=1e-9)


def test_rsv_positions_close_between_window_high_and_low():
    """gtja_rsv_9：窗内 high=20 / low=10 恒定，收盘 19 → (19−10)/(20−10) = 0.9。"""
    closes = [10.0 + i for i in range(10)]
    values = compute_factor_values("gtja_rsv_9", _bars(closes, highs=[20.0] * 10, lows=[10.0] * 10), [])

    assert values[9] == pytest.approx(0.9)


def test_atr_normalizes_true_range_by_close():
    """gtja_atr_14：high=close+1、low=close−1、收盘 10..24 →
    真实波幅恒为 max(2, 2, 0)=2，均值 2，末根收盘 24 → 2/24。"""
    closes = [10.0 + i for i in range(15)]
    values = compute_factor_values(
        "gtja_atr_14",
        _bars(closes, highs=[c + 1 for c in closes], lows=[c - 1 for c in closes]),
        [],
    )

    assert values[14] == pytest.approx(1.0 / 12.0, rel=1e-9)


def test_pv_divergence_none_when_price_flat():
    """gtja_pv_divergence：20 日动量为 0（价格恒定）→ 不出值，不得误判成 −1。"""
    volumes = [1000.0 + 10.0 * i for i in range(30)]

    values = compute_factor_values("gtja_pv_divergence", _bars([10.0] * 30, volumes=volumes), [])

    assert values[24] is None


def test_pv_divergence_none_when_volume_flat():
    """gtja_pv_divergence：量能 10 日斜率（相关系数）为 0 → 不出值。"""
    closes = [10.0 + 0.5 * i for i in range(30)]

    values = compute_factor_values("gtja_pv_divergence", _bars(closes, volumes=[1000.0] * 30), [])

    assert values[24] is None


def test_pv_divergence_none_when_previous_close_invalid():
    """gtja_pv_divergence：窗口起点收盘价为 0（动量不可算）→ 不出值。"""
    closes = [10.0 + 0.5 * i for i in range(30)]
    closes[4] = 0.0
    volumes = [1000.0 + 10.0 * i for i in range(30)]

    values = compute_factor_values("gtja_pv_divergence", _bars(closes, volumes=volumes), [])

    assert values[24] is None


def test_acad_max_is_largest_intraday_gain():
    """acad_max_60：开盘恒 10 元、最高价 10+0.1k → 最大日内涨幅 = 16/10 − 1 = 0.6。"""
    highs = [10.0 + 0.1 * k for k in range(61)]
    values = compute_factor_values("acad_max_60", _bars([10.0] * 61, opens=[10.0] * 61, highs=highs), [])

    assert values[60] == pytest.approx(0.6, rel=1e-9)


def test_idio_vol_is_std_of_residual_returns():
    """acad_idio_vol_60：指数恒价（指数收益恒 0）→ 残差 = 组合收益 →
    60 日样本标准差 0.0010842282523791551（closes=100..160）。"""
    closes = [100.0 + i for i in range(61)]

    values = compute_factor_values("acad_idio_vol_60", _bars(closes), _bars([100.0] * 61))

    assert values[60] == pytest.approx(0.0010842282523791551, rel=1e-9)


def test_amihud_proxy_averages_absolute_return_over_turnover():
    """acad_amihud_proxy_60：Σ(|收益|/成交量×1e9)/有效天数，零成交量日剔除。

    成交量恒 100、第 31 根为 0 → 该日剔除后 59 天均值 5505769.932295127。
    """
    closes = [10.0 + (1.0 if k % 2 else 2.0) * k for k in range(61)]
    volumes = [100.0] * 61
    volumes[30] = 0.0

    values = compute_factor_values("acad_amihud_proxy_60", _bars(closes, volumes=volumes), [])

    assert values[60] == pytest.approx(5505769.932295127, rel=1e-9)


def test_low_vol_is_std_of_returns():
    """acad_low_vol_60：60 日收益样本标准差（closes=100..160）→ 0.0010842282523791551。"""
    values = compute_factor_values("acad_low_vol_60", _bars([100.0 + i for i in range(61)]), [])

    assert values[60] == pytest.approx(0.0010842282523791551, rel=1e-9)


def test_skew_60_outputs_sample_skewness_value():
    """acad_skew_60：每 10 日一次 +2% 其余 +0.3% 的序列，60 日样本偏度 2.73553559…。"""
    closes = [10.0]
    for i in range(70):
        closes.append(closes[-1] * (1.003 if i % 10 else 1.02))

    values = compute_factor_values("acad_skew_60", _bars(closes), [])

    assert values[64] == pytest.approx(2.7355355918424853, rel=1e-9)


def test_skew_60_skips_nan_returns_within_window():
    """acad_skew_60：窗内含坏价（收益 NaN）时按有效收益算偏度，不整体丢弃该日。"""
    closes = [10.0 + (0.5 if i % 2 else -0.3) * i for i in range(71)]
    closes[30] = None

    values = compute_factor_values("acad_skew_60", _bars(closes), [])

    assert values[64] == pytest.approx(-4.024047231981996, rel=1e-9)


# ── 横截面日均值 ──


def test_cross_sectional_mean_of_registered_codes():
    """横截面均值 = 当日有效值之和 / 成分数：0.1/0.4/1.0 → 0.5。"""
    values = [0.1 * (i + 1) for i in range(MIN_CODES_PER_DAY)]
    factor_values_by_code = {f"code{i}": [("2026-02-01", value)] for i, value in enumerate(values)}
    expected = sum(values) / len(values)

    assert cross_sectional_series(factor_values_by_code) == {"2026-02-01": pytest.approx(expected, rel=1e-9)}


def test_cross_sectional_drops_day_below_code_floor():
    """成分数比下限少 1 的日期被剔除，达到下限的日期保留。"""
    below = [f"code{i}" for i in range(MIN_CODES_PER_DAY - 1)]
    factor_values_by_code = {code: [("2026-02-02", 0.5)] for code in below}
    factor_values_by_code.update({f"thick{i}": [("2026-02-03", 0.5)] for i in range(MIN_CODES_PER_DAY)})

    series = cross_sectional_series(factor_values_by_code)

    assert set(series) == {"2026-02-03"}
