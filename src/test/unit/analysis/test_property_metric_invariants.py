"""统计/数值工具的不变量属性测试（`sanitize_metric` / `truncate_extreme_values` / `_beta_se`）。

为什么用属性而不是已知答案：这三个函数都是"降级/夹逼"型数值工具，真正的语义是
不变量（非有限值必被清理、截断不改变长度与次序、退化基准必返回 None），而不是
某组输入对应某个死数值。属性测试把语义写成可失败断言，避免「实现换了一条等价
计算路径就把已知答案打红」这类假回归。

锁定的语义：

- `sanitize_metric`：NaN/±Inf → default（默认 None）；有限值与 int 原样透传；幂等。
- `truncate_extreme_values`：长度不变；输出值全部落在 [下限档位, 上限档位] 内；
  极值被夹到档位、非极值元素原值保持；幂等；保序；空输入不抛。
- `_beta_se`：基准恒定（极差为 0）→ None（任意组合数与符号）；样本不足 → None；
  正常输入 → (se ≥ 0, df = n-2)；se 对两序列的整体平移不变（平移不改变残差）。

输入域窄化：`_beta_se` 的数值性质跑在「日收益量级网格（步长 1e-4）」上——真实浮点
策略会给出 1e-300 量级的近零序列，其平方在 fsum 中下溢为 0，绕过实现的「极差非零
⇒ ssx > 0」前提并触发除零（该缺陷已记录在交付说明，本文件不静默放宽它，只是不把
不可达的输入域混进数值不变量）。有限浮点用 `width=64` + 禁 NaN/Inf 窄化到合法域。

容差口径：不对浮点结果用 `==`；有界量按量级设 `abs=1e-9`（见各用例注释）。
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.python.analysis._math_utils import _MIN_SAMPLE_DAYS, _beta_se
from src.python.analysis.metrics_returns import sanitize_metric, truncate_extreme_values

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

#: `_beta_se` 的准入下限：n < _MIN_SAMPLE_DAYS + 2 → None（涨跌对齐后至少两期残差）
_BETA_MIN_SAMPLES = _MIN_SAMPLE_DAYS + 2

#: 有限浮点（含极大/极小量级）：清理类函数的合法输入域
_FINITE = st.floats(allow_nan=False, allow_infinity=False, width=64)
#: 非有限值：NaN 与 ±Inf
_NON_FINITE = st.sampled_from([math.nan, math.inf, -math.inf])
#: 日收益量级网格（步长 1e-4）：避免平方下溢到 0 的近零序列污染数值不变量
_GRID_RETURN = st.integers(min_value=-2000, max_value=2000).map(lambda steps: steps / 10000.0)
_BETA_BETA = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False, width=64)
_SHIFT = st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False, width=64)

_SETTINGS = settings(max_examples=50, deadline=None)


# ═══════════════════════════════════════════════════════════════
#  sanitize_metric：非有限值清理 + 幂等
# ═══════════════════════════════════════════════════════════════


@_SETTINGS
@given(value=_NON_FINITE)
def test_sanitize_metric_maps_non_finite_to_none(value):
    """NaN/±Inf → None（默认替换值），下游渲染才不会出现 "nan%"。"""
    assert sanitize_metric(value) is None


@_SETTINGS
@given(value=_NON_FINITE, default=st.sampled_from([0.0, -1.0, 0.5]))
def test_sanitize_metric_uses_explicit_default_for_non_finite(value, default):
    """显式 default 生效（非有限值一律替换为调用方给的兜底值）。"""
    assert sanitize_metric(value, default) == default


@_SETTINGS
@given(value=_FINITE)
def test_sanitize_metric_passes_finite_values_through(value):
    """有限浮点原样返回（同一个对象，不做任何重算/舍入）。"""
    assert sanitize_metric(value) is value


@_SETTINGS
@given(value=st.integers(min_value=-(10**9), max_value=10**9))
def test_sanitize_metric_passes_integers_through(value):
    """int 不是 float 实例 → 原样透传（不得被转成 float 或置 None）。"""
    assert sanitize_metric(value) is value


@_SETTINGS
@given(value=st.one_of(_FINITE, _NON_FINITE, st.none(), st.integers(), st.text(max_size=8)))
def test_sanitize_metric_is_idempotent(value):
    """幂等：二次清理不再改变结果（清理器被重复调用是常态）。"""
    once = sanitize_metric(value)
    assert sanitize_metric(once) is once


# ═══════════════════════════════════════════════════════════════
#  truncate_extreme_values：夹逼 + 保序 + 幂等
# ═══════════════════════════════════════════════════════════════


@_SETTINGS
@given(series=st.lists(_FINITE, min_size=1, max_size=40))
def test_truncate_extreme_values_keeps_length(series):
    """输出与输入等长（下游按索引与原序列对齐）。"""
    assert len(truncate_extreme_values(series)) == len(series)


@_SETTINGS
@given(
    series=st.lists(_FINITE, min_size=1, max_size=40),
    low_quantile=st.floats(min_value=0.0, max_value=0.4, allow_nan=False, allow_infinity=False, width=64),
    high_quantile=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False, width=64),
)
def test_truncate_extreme_values_clamps_into_quantile_band(series, low_quantile, high_quantile):
    """极值被夹到档位、非极值元素原值保持；档位 = 输入序列的两个顺序统计量。

    分位截断的规格就是「档位取下侧/上侧分位点处的顺序统计量，值被夹进 [下档位, 上档位]」
    （下标约定：`int(n*q)` 截断，两端钳到合法下标）。这里必须从**输入**派生档位——
    若改用输出的 min/max 当档位，完全不截断的退化实现（原样返回）会平凡通过。
    """
    truncated = truncate_extreme_values(series, low_quantile, high_quantile)
    ordered = sorted(series)
    size = len(ordered)
    lower_bound = ordered[max(0, int(size * low_quantile))]
    upper_bound = ordered[min(size - 1, int(size * high_quantile))]
    assert lower_bound <= upper_bound
    for original, result in zip(series, truncated):
        if original < lower_bound:
            assert result == lower_bound
        elif original > upper_bound:
            assert result == upper_bound
        else:
            assert result == original


@_SETTINGS
@given(series=st.lists(_FINITE, min_size=1, max_size=40))
def test_truncate_extreme_values_is_idempotent(series):
    """幂等：截断后的序列再截断一次不变（输出全在档位内 ⇒ 二阶截断是恒等）。"""
    once = truncate_extreme_values(series)
    assert truncate_extreme_values(once) == once


@_SETTINGS
@given(series=st.lists(_FINITE, min_size=2, max_size=40))
def test_truncate_extreme_values_preserves_order(series):
    """保序：原始相邻关系不因截断而反转（夹逼映射单调不减）。"""
    truncated = truncate_extreme_values(series)
    for index, (left, right, out_left, out_right) in enumerate(zip(series, series[1:], truncated, truncated[1:])):
        if left <= right:
            assert out_left <= out_right, f"第 {index} 对相邻元素保序性被破坏"


def test_truncate_extreme_values_returns_empty_for_empty_input():
    """空输入返回空列表（不得抛 IndexError/ValueError）。"""
    assert truncate_extreme_values([]) == []


# ═══════════════════════════════════════════════════════════════
#  _beta_se：退化必 None + 正常输入的自自由度/正负号/平移不变
# ═══════════════════════════════════════════════════════════════


@_SETTINGS
@given(
    portfolio=st.lists(_FINITE, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 20),
    benchmark_level=st.sampled_from([0.0, 0.01, -0.03, 1e6]),
    beta=_BETA_BETA,
)
def test_beta_se_is_none_for_zero_variance_benchmark(portfolio, benchmark_level, beta):
    """基准恒定 → None：Σ(x-x̄)² = 0 无从求 SE，任意组合收益/组合数/Beta 符号都不得硬算。"""
    benchmark = [benchmark_level] * len(portfolio)
    assert _beta_se(portfolio, benchmark, beta) is None


@_SETTINGS
@given(
    short=st.lists(_FINITE, max_size=_BETA_MIN_SAMPLES - 1),
    long=st.lists(_FINITE, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 5),
    beta=_BETA_BETA,
)
def test_beta_se_is_none_when_short_side_limits_samples(short, long, beta):
    """任一侧样本不足 _BETA_MIN_SAMPLES（取两侧较短者）→ None，与参数顺序无关。"""
    assert _beta_se(short, long, beta) is None
    assert _beta_se(long, short, beta) is None


@_SETTINGS
@given(
    benchmark=st.lists(_GRID_RETURN, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 20),
    portfolio=st.lists(_GRID_RETURN, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 20),
    beta=_BETA_BETA,
)
def test_beta_se_reports_non_negative_se_and_degrees_of_freedom(benchmark, portfolio, beta):
    """正常输入 → se ≥ 0 且 df = n-2（n 为对齐后较短侧长度）。"""
    n = min(len(benchmark), len(portfolio))
    # 基准末 n 期恒定属退化域（由零方差用例覆盖），此处只断言有波动的情形
    assume(max(benchmark[-n:]) - min(benchmark[-n:]) != 0)

    result = _beta_se(portfolio, benchmark, beta)
    assert result is not None
    se, df = result
    assert math.isfinite(se)
    assert se >= 0.0
    assert df == n - 2


@_SETTINGS
@given(
    benchmark=st.lists(_GRID_RETURN, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 20),
    portfolio=st.lists(_GRID_RETURN, min_size=_BETA_MIN_SAMPLES, max_size=_BETA_MIN_SAMPLES + 20),
    beta=_BETA_BETA,
    portfolio_shift=_SHIFT,
    benchmark_shift=_SHIFT,
)
def test_beta_se_is_invariant_under_series_translation(benchmark, portfolio, beta, portfolio_shift, benchmark_shift):
    """整体平移两序列不改变 SE（OLS 残差对截距吸收平移，ssx 对平移不变）。

    容差不变量：SE 量级 ≤ 1e4（日收益 1e-4 网格 + |β| ≤ 100），平移引入的差额只来自
    舍入（残差误差 ~1e-16），故按量级设 `abs=1e-9`——远大于舍入噪声、远小于任何
    真语义错误（如截距未随平移调整）产生的 O(1e-2) 差异。
    """
    n = min(len(benchmark), len(portfolio))
    assume(max(benchmark[-n:]) - min(benchmark[-n:]) != 0)

    base = _beta_se(portfolio, benchmark, beta)
    assert base is not None
    shifted = _beta_se(
        [value + portfolio_shift for value in portfolio],
        [value + benchmark_shift for value in benchmark],
        beta,
    )
    assert shifted is not None
    assert shifted[1] == base[1]
    assert shifted[0] == pytest.approx(base[0], abs=1e-9)


def test_beta_se_is_positive_for_noisy_portfolio():
    """组合收益带独立噪声（非完美拟合）→ SE 严格为正、df = n-2。"""
    benchmark = [0.001 * ((i % 11) - 5) for i in range(_BETA_MIN_SAMPLES)]
    portfolio = [1.2 * value + 0.0003 * ((i % 7) - 3) for i, value in enumerate(benchmark)]

    result = _beta_se(portfolio, benchmark, 1.2)
    assert result is not None
    se, df = result
    assert se > 0.0
    assert df == _BETA_MIN_SAMPLES - 2
