"""成本区间位置 — 纯计算层单元测试（analysis/cost_position）。

覆盖 clamp / 中性值 / 窗口切片 / 无效值跳过。
收盘价条目提取为共享能力（``valuation_percentile.extract_closes``），在其自身测试覆盖。
极端值与非有限值场景见兄弟分片 test_cost_position_edge.py。
"""

from __future__ import annotations

import pytest

from src.python.analysis.cost_position import (
    LONG_WINDOW_DAYS,
    SHORT_WINDOW_DAYS,
    compute_window_position,
    positions_from_closes,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestComputeWindowPosition:
    """compute_window_position — 成本价在窗口区间中的百分位。"""

    def test_midpoint(self):
        """成本价位于区间中点 → 0.5。"""
        assert compute_window_position(150.0, [100.0, 200.0], 20) == pytest.approx(0.5)

    def test_high_position(self):
        """成本价贴近区间高位 → 接近 1（追涨嫌疑）。"""
        assert compute_window_position(190.0, [100.0, 200.0], 20) == pytest.approx(0.9)

    def test_low_position(self):
        """成本价贴近区间低位 → 接近 0（低位布局）。"""
        assert compute_window_position(110.0, [100.0, 200.0], 20) == pytest.approx(0.1)

    def test_clamp_above(self):
        """成本价高于区间最高 → clamp 到 1.0。"""
        assert compute_window_position(300.0, [100.0, 200.0], 20) == 1.0

    def test_clamp_below(self):
        """成本价低于区间最低 → clamp 到 0.0。"""
        assert compute_window_position(50.0, [100.0, 200.0], 20) == 0.0

    def test_window_slice_ignores_older_bars(self):
        """只取末 window 根：窗口外的更高/更低价不参与极值。"""
        # 序列末 2 根为 [100, 200]，第 3 根（更早）为 1000——不应抬高 high
        closes = [1000.0, 100.0, 200.0]
        assert compute_window_position(150.0, closes, 2) == pytest.approx(0.5)

    def test_valid_closes_below_window_count(self):
        """有效价少于窗口长度时用全部有效价（不因不足 window 根而返回 None）。"""
        assert compute_window_position(120.0, [100.0, 200.0], 20) == pytest.approx(0.2)

    def test_zero_close_excluded_from_range(self):
        """0 收盘价（脏数据）不参与区间极值——区间仍为 [100,200]，不影响百分位。"""
        # 若 0 被误计入区间，low=0 → (150-0)/200 = 0.75 ≠ 0.5
        assert compute_window_position(150.0, [100.0, 0.0, 200.0], 20) == pytest.approx(0.5)


class TestPositionsFromCloses:
    """positions_from_closes — 同源两窗口百分位装配。"""

    def test_returns_both_windows(self):
        closes = [float(c) for c in range(100, 300)]
        pos = positions_from_closes(250.0, closes)
        assert set(pos) == {"short", "long"}
        assert pos["short"] is not None and pos["long"] is not None

    def test_short_window_uses_tail(self):
        """短窗口取长序列尾部切片——前段大涨不影响短窗口百分位。"""
        # 前 300 根低位（=10），末 20 根高位（=100..120 线性）
        closes = [10.0] * 300 + [float(c) for c in range(100, 120)]
        pos = positions_from_closes(110.0, closes)
        # 短窗口：110 落在 [100,119] 中点 → ~0.5；长窗口：110 落在 [10,119] 靠上 → >0.9
        assert pos["short"] == pytest.approx((110 - 100) / (119 - 100))
        assert pos["long"] == pytest.approx((110 - 10) / (119 - 10))

    def test_window_constants_consistent(self):
        """短窗口小于长窗口（结构性断言，不写死具体天数）。"""
        assert SHORT_WINDOW_DAYS < LONG_WINDOW_DAYS
