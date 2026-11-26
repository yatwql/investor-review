"""报告侧百分比格式化原语（`report/_format`）的口径契约。

锁三件事：百分点口径不补尾随零、比例口径固定两位小数且 `signed` 决定正负号、
缺失/非数值一律回「无数据」占位而不抛异常——这三处原先由三个同名 `_fmt_pct`
分别实现，缺失值表现各异（其一直接抛 `ValueError`），脏数据会把整章渲染中断。
"""

from __future__ import annotations

import pytest

from src.python.report._format import DASH, fmt_pct_fraction, fmt_pct_points

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestFmtPctPoints:
    """百分点口径：入参已是点数。"""

    def test_points_keep_g_notation(self):
        assert fmt_pct_points(12.5) == "12.5%"
        assert fmt_pct_points(20.0) == "20%"
        assert fmt_pct_points(-3.25) == "-3.25%"

    def test_zero_and_non_numeric(self):
        assert fmt_pct_points(0) == "0%"
        assert fmt_pct_points(None) == DASH
        assert fmt_pct_points("N/A") == DASH


class TestFmtPctFraction:
    """比例口径：入参是小数比例。"""

    def test_unsigned_two_decimals(self):
        assert fmt_pct_fraction(0.125) == "12.50%"
        assert fmt_pct_fraction(0) == "0.00%"
        assert fmt_pct_fraction(-0.5) == "-50.00%"

    def test_signed_prefixes_positive_values(self):
        assert fmt_pct_fraction(0.0123, signed=True) == "+1.23%"
        assert fmt_pct_fraction(-0.0123, signed=True) == "-1.23%"
        assert fmt_pct_fraction(0, signed=True) == "+0.00%"

    def test_non_numeric_renders_dash_instead_of_raising(self):
        assert fmt_pct_fraction(None) == DASH
        assert fmt_pct_fraction("N/A") == DASH
