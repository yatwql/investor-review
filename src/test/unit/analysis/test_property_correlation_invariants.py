"""`_pearson_pvalue` 不变量属性测试（对称性 / 缩放不变 / 值域 / 顺序无关）。

为什么用属性而不是已知答案：已知答案只锁一条计算路径的死数值，换解释器或换元素
顺序就漂——同一对取值在 Python 3.11 与 3.12 上曾出现末位不一致（求和累加策略随
解释器版本变化）。这里用 hypothesis 锁语义不变量：

  ① 交换对称：r(x,y) ≈ r(y,x)，p 同；
  ② 正仿射不变：r(a·x+b, c·y+d) ≈ r(x,y)（a, c > 0；平移与正缩放不改变线性关系）；
  ③ 值域：-1 ≤ r ≤ 1 且 0 ≤ p ≤ 1；
  ④ 配对置换不变：同一批配对随机打乱后 r/p 近似不变（实现走 math.fsum，正确舍入
     即与求和顺序无关——这条正是跨解释器末位差事故的守护）。

退化语义按实现锁定：`_pearson_pvalue` 自身的样本下限是 3（n < 3 → (0.0, 1.0)），
常数/近常数序列（标准差 < _CONSTANT_EPS）同样返回 (0.0, 1.0)。`MIN_SAMPLES`（60）
是 `compute_correlation_matrix` 的调用层口径，不在本函数内，本文件只验证函数自身界线。

容差口径：r ∈ [-1,1]、p ∈ [0,1] 均为有界量，故按量级设绝对容差 `abs=1e-9`
（远大于末位 ulp，远小于任何真语义错误的 O(1) 差异），不对浮点计算结果用 `==`。
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.python.analysis.correlation import MIN_SAMPLES, _pearson_pvalue

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

#: r/p 都是有界量，按量级设绝对容差（见模块 docstring 的容差口径）
_TOL = 1e-9

#: 合法域：日收益量级的有界浮点；NaN/Inf 会使 Pearson 无意义，故排除
_RETURN = st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False, width=64)
_PAIRS = st.lists(st.tuples(_RETURN, _RETURN), min_size=3, max_size=40)

#: 仿射不变性用 1e-4 步长网格：真实浮点能生成 1e-300 量级的近常数序列，会被实现的
#: 「标准差 < _CONSTANT_EPS」退化保护按阈值切成不同分支（假失败）；网格保证不同取值
#: 的间距 ≥ 1e-4，退化与否在缩放前后判定一致。
_GRID_RETURN = st.integers(min_value=-2000, max_value=2000).map(lambda steps: steps / 10000.0)
_GRID_PAIRS = st.lists(st.tuples(_GRID_RETURN, _GRID_RETURN), min_size=3, max_size=40)

_SETTINGS = settings(max_examples=50, deadline=None)


def _split(pairs: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """配对列表 → 两条等长序列（保配对，供 r(x, y) 使用）。"""
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


@_SETTINGS
@given(pairs=_PAIRS)
def test_pearson_symmetric_under_argument_swap(pairs):
    """交换两个序列后 r 与 p 不变（相关是对称关系，不是有向关系）。"""
    x, y = _split(pairs)
    r_xy, p_xy = _pearson_pvalue(x, y)
    r_yx, p_yx = _pearson_pvalue(y, x)
    assert r_yx == pytest.approx(r_xy, abs=_TOL)
    assert p_yx == pytest.approx(p_xy, abs=_TOL)


@_SETTINGS
@given(
    pairs=_GRID_PAIRS,
    scale_x=st.floats(min_value=0.5, max_value=4.0, allow_nan=False, allow_infinity=False, width=64),
    scale_y=st.floats(min_value=0.5, max_value=4.0, allow_nan=False, allow_infinity=False, width=64),
    shift_x=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False, width=64),
    shift_y=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False, width=64),
)
def test_pearson_invariant_under_positive_affine_scaling(pairs, scale_x, scale_y, shift_x, shift_y):
    """r(a·x+b, c·y+d) ≈ r(x, y)：单位换算（百分比↔小数）不得改变相关系数。"""
    x, y = _split(pairs)
    base_r, base_p = _pearson_pvalue(x, y)
    scaled_r, scaled_p = _pearson_pvalue(
        [scale_x * v + shift_x for v in x],
        [scale_y * v + shift_y for v in y],
    )
    if (base_r, base_p) == (0.0, 1.0):
        # 常数序列退化：正仿射变换后仍是常数，退化语义必须保持（缩放不得把零方差"救活"）
        assert (scaled_r, scaled_p) == (0.0, 1.0)
        return
    assert scaled_r == pytest.approx(base_r, abs=_TOL)
    if min(1.0 - abs(base_r), 1.0 - abs(scaled_r)) < 1e-12:
        # |r| → 1 奇异点：实现走「|r| ≥ 1 ⇒ p = 0」早退，而末位扰动就能把 |r| 推到 1 的另一侧
        # 落到 t 分布尾部（相邻取值上 p 从 0.0 跳到 ~1e-8）。p 在 r→1 处不连续属数值奇点，
        # 不是缩放不变量能约束的行为（r 本身的不变性已在上方断言）。
        return
    assert scaled_p == pytest.approx(base_p, abs=_TOL)


@_SETTINGS
@given(pairs=_PAIRS)
def test_pearson_result_stays_within_unit_range(pairs):
    """任意合法输入下 -1 ≤ r ≤ 1 且 0 ≤ p ≤ 1（下游色彩/显著性判定的前提）。"""
    x, y = _split(pairs)
    r, p = _pearson_pvalue(x, y)
    assert -1.0 <= r <= 1.0
    assert 0.0 <= p <= 1.0


@_SETTINGS
@given(pairs=_PAIRS, seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_pearson_invariant_under_pair_permutation(pairs, seed):
    """配对随机打乱后 r/p 不变（顺序无关：正确舍入求和不受累加次序影响）。"""
    x, y = _split(pairs)
    shuffled = list(pairs)
    random.Random(seed).shuffle(shuffled)
    shuffled_x, shuffled_y = _split(shuffled)

    base_r, base_p = _pearson_pvalue(x, y)
    shuffled_r, shuffled_p = _pearson_pvalue(shuffled_x, shuffled_y)
    assert shuffled_r == pytest.approx(base_r, abs=_TOL)
    assert shuffled_p == pytest.approx(base_p, abs=_TOL)


@pytest.mark.parametrize("length", [0, 1, 2])
def test_pearson_returns_undefined_sentinel_below_three_samples(length):
    """样本不足 3 期 → (0.0, 1.0)（无法判定线性关系，渲染为"不显著"）。"""
    x = [0.01 * i for i in range(length)]
    y = [0.02 * i + 0.001 for i in range(length)]
    assert _pearson_pvalue(x, y) == (0.0, 1.0)


def test_pearson_returns_undefined_sentinel_for_constant_series():
    """任一序列恒定（方差为 0）→ (0.0, 1.0)，绝不硬算出虚假相关。"""
    noise = [0.01 * ((i % 7) - 3) for i in range(MIN_SAMPLES)]
    constant = [0.005] * MIN_SAMPLES
    assert _pearson_pvalue(constant, noise) == (0.0, 1.0)
    assert _pearson_pvalue(noise, constant) == (0.0, 1.0)


def test_pearson_computes_defined_result_at_min_samples_boundary():
    """样本数恰为 MIN_SAMPLES 且两序列同比例 → 完全正相关（r=1, p=0），非退化哨兵。"""
    x = [0.01 * ((i % 5) - 2) for i in range(MIN_SAMPLES)]
    r, p = _pearson_pvalue(x, [2.0 * v for v in x])
    assert r == pytest.approx(1.0, abs=_TOL)
    assert p == pytest.approx(0.0, abs=_TOL)
