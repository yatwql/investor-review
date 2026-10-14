"""成本区间位置 — 边缘场景测试（极端值 / 非有限值 / 退化序列）。

必须使用 @pytest.mark.edge 标记，存放于 *_edge.py 文件（conftest 收集期校验）。
"""

from __future__ import annotations

import pytest

from src.python.analysis.cost_position import (
    NEUTRAL_POSITION,
    PLACEHOLDER,
    compute_window_position,
    positions_from_closes,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis, pytest.mark.edge]


class TestDegenerateCloses:
    """退化价格序列。"""

    def test_high_equals_low_returns_neutral(self):
        """窗口内最高 == 最低（停牌/极窄波动）→ 中性值，不除零。"""
        assert compute_window_position(100.0, [100.0, 100.0, 100.0], 20) == NEUTRAL_POSITION

    def test_single_bar(self):
        """仅一根 bar → high==low → 中性值。"""
        assert compute_window_position(50.0, [50.0], 20) == NEUTRAL_POSITION

    def test_empty_closes(self):
        assert compute_window_position(100.0, [], 20) is None

    def test_all_non_positive_closes(self):
        """序列全为 0/负 → 无有效价 → None。"""
        assert compute_window_position(100.0, [0.0, -1.0, 0.0], 20) is None


class TestInvalidCost:
    """无效成本价。"""

    def test_zero_cost(self):
        """成本为 0（成本行缺失/为 0 的老报告缺陷面）→ None，不产出 0% 假象。"""
        assert compute_window_position(0.0, [100.0, 200.0], 20) is None

    def test_negative_cost(self):
        assert compute_window_position(-5.0, [100.0, 200.0], 20) is None

    def test_none_cost(self):
        assert compute_window_position(None, [100.0, 200.0], 20) is None

    def test_zero_window(self):
        assert compute_window_position(100.0, [100.0, 200.0], 0) is None

    def test_negative_window(self):
        assert compute_window_position(100.0, [100.0, 200.0], -5) is None


class TestOutOfRangeCost:
    """成本价越出历史区间（加仓摊薄/大幅浮盈浮亏后调仓）。"""

    def test_far_above_clamps_to_one(self):
        assert compute_window_position(1e9, [10.0, 20.0], 20) == 1.0

    def test_far_below_clamps_to_zero(self):
        assert compute_window_position(1e-6, [10.0, 20.0], 20) == 0.0


class TestNonFiniteValues:
    """NaN / ±inf / 非数值不得穿透成 NaN 百分位（在窗口区间内过滤）。"""

    def test_nan_close_excluded_from_range(self):
        """序列夹杂 NaN → 过滤后区间仍正确（不影响极值）。"""
        # valid = [100,200] → (150-100)/(200-100) = 0.5；若 NaN 穿透则整段变 NaN
        assert compute_window_position(150.0, [100.0, float("nan"), 200.0], 20) == pytest.approx(0.5)

    def test_inf_close_excluded_from_range(self):
        assert compute_window_position(150.0, [100.0, float("inf"), 200.0], 20) == pytest.approx(0.5)

    def test_nan_cost_is_none(self):
        assert compute_window_position(float("nan"), [100.0, 200.0], 20) is None

    def test_inf_cost_is_none(self):
        """inf 成本按无效数据处理（finite_or 归一 → None），不得产出 NaN。"""
        assert compute_window_position(float("inf"), [100.0, 200.0], 20) is None

    def test_positions_never_nan(self):
        """混合脏数据 + 有效成本下两窗口值要么 0~1 要么 None，绝不 NaN。"""
        closes = [float("nan"), 0.0, 100.0, float("inf"), 200.0]
        for value in positions_from_closes(150.0, closes).values():
            assert value is None or (0.0 <= value <= 1.0)


class TestPlaceholderContract:
    """占位符常量与渲染层口径一致（防止两处各写一个占位符）。"""

    def test_placeholder_is_double_dash(self):
        assert PLACEHOLDER == "--"
