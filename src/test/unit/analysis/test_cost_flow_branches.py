"""cost_flow 残余分支 — 日期解析失败、二分兜底、流水跳过与近似快照过滤。

锁住的契约：
  - `_as_date` 接受 datetime / date / ``YYYY-MM-DD`` 字符串；非法日期串（如 13 月）
    与非日期类型一律 None（下游据此跳过该条流水，不猜日期）；
  - `_bisect_root` 在扫描端点恰好 NPV=0 时直接返回端点；扫描区间内无变号返回 None；
    未达容差时按区间中点收尾（不无限迭代）；
  - `solve_xirr` 在牛顿迭代退化（导数为零 / 步长溢出）时降级二分，返回 None 或有限解，
    不抛异常；
  - `build_xirr_cashflows` 跳过日期非法的流水与份额 ≤0 的分红；
  - `build_approximate_fund_flow_data` 跳过份额或成本 ≤0 的持仓（不造假流水）。
"""

from __future__ import annotations

import datetime as _dt

import pytest

from src.python.analysis.cost_flow import (
    _as_date,
    _bisect_root,
    build_approximate_fund_flow_data,
    build_xirr_cashflows,
    solve_xirr,
)
from src.python.core.models import DividendRecord, Holding, TradeRecord

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _trade(code, date, action, shares, price, fee=0.0):
    """构造交易流水记录。"""
    return TradeRecord(date=date, code=code, action=action, shares=shares, price=price, fee=fee)


def _div(code, date, amount, shares=0.0):
    """构造分红流水记录。"""
    return DividendRecord(date=date, code=code, amount=amount, shares=shares)


def _holding(code, name, shares, cost_price):
    """构造当前持仓记录。"""
    return Holding(account="账户A", name=name, code=code, shares=shares, cost_price=cost_price)


class TestAsDate:
    """`_as_date` 的接受面与拒绝面。"""

    def test_datetime_is_truncated_to_date(self):
        """datetime 输入取日期部分（时间分量丢弃）。"""
        assert _as_date(_dt.datetime(2024, 5, 6, 15, 30)) == _dt.date(2024, 5, 6)

    def test_impossible_calendar_date_returns_none(self):
        """形如 YYYY-MM-DD 但日历上不存在的日期 → None（不是抛异常）。"""
        assert _as_date("2024-13-01") is None
        assert _as_date("2024-02-30") is None

    def test_non_date_type_returns_none(self):
        """非 date/datetime/字符串的输入（如整数时间戳）→ None。"""
        assert _as_date(20240506) is None


class TestBisectRoot:
    """`_bisect_root` 的端点命中、无解与中点收尾。"""

    def test_exact_root_at_lower_scan_point(self):
        """NPV(0)=0（-100 现值 + 100 一年后）→ 直接返回下端点 0.0。"""
        assert _bisect_root([-100.0, 100.0], [0.0, 1.0], 1e-7) == pytest.approx(0.0)

    def test_exact_root_at_upper_scan_point(self):
        """NPV(0.5)=0（-100 + 150/1.5）→ 直接返回上端点 0.5。"""
        assert _bisect_root([-100.0, 150.0], [0.0, 1.0], 1e-7) == pytest.approx(0.5)

    def test_exact_root_at_first_scan_point(self):
        """首个扫描端点处 NPV 恰为 0 → 直接返回该端点（−0.9999）。

        取与实现同源的 ``1 + rate`` 作为现金流金额，使 -1 + factor/factor 在浮点下
        恰为 0.0（不依赖近似相等）。
        """
        factor = 1.0 + (-0.9999)
        assert _bisect_root([-1.0, factor], [0.0, 1.0], 1e-7) == pytest.approx(-0.9999)

    def test_no_sign_change_returns_none(self):
        """全正现金流 NPV 恒为正 → 无变号点，返回 None。"""
        assert _bisect_root([100.0, 100.0], [0.0, 1.0], 1e-7) is None

    def test_midpoint_returned_when_tolerance_never_met(self):
        """tolerance=0 时 |NPV| 恒不达标 → 按 200 步二分后的中点收尾（≈真实根 10%）。"""
        root = _bisect_root([-100.0, 110.0], [0.0, 1.0], 0.0)
        assert root == pytest.approx(0.1, abs=1e-6)


class TestSolveXirrDegenerate:
    """`solve_xirr` 牛顿迭代退化时降级二分（不抛异常）。"""

    def test_zero_derivative_falls_back_to_bisect(self):
        """末期现金流近乎为零使导数 ~0 → 降级二分；无可解区间返回 None。"""
        assert solve_xirr([-100.0, 1e-12], ["2024-01-01", "2025-01-01"]) is None

    def test_overflowing_step_falls_back_to_bisect(self):
        """首笔现金流接近 float 上限、导数微小 → 步长溢出为非有限值，降级二分返回 None。"""
        assert solve_xirr([1e308, 10.0], ["2024-01-01", "2024-01-02"]) is None


class TestCashflowSkips:
    """`build_xirr_cashflows` 对不可计流水的跳过口径。"""

    def test_invalid_trade_date_and_invalid_dividend_date_skipped(self):
        """交易日期非法与分红日期非法都跳过；剩余合法流水仍构成现金流。"""
        flows = build_xirr_cashflows(
            [_trade("X", "bad-date", "buy", 10, 10.0), _trade("X", "2024-01-02", "buy", 10, 10.0)],
            [_div("X", "2024-13-40", 0.5, shares=10)],
            [],
            {"X": 12.0},
        )
        assert flows is not None
        assert flows[0] == (_dt.date(2024, 1, 2), pytest.approx(-100.0))

    def test_dividend_without_known_shares_skipped(self):
        """分红份额为 0 且无对应持仓 → 份额取不到，跳过该条分红。"""
        flows = build_xirr_cashflows(
            [_trade("X", "2024-01-02", "buy", 10, 10.0)],
            [_div("X", "2024-06-01", 0.5)],
            [],
            None,
        )
        assert flows is not None
        # 只剩买入一笔负现金流（无分红、无期末市值）
        assert [amount for _, amount in flows] == [pytest.approx(-100.0)]


class TestApproximateFundFlowData:
    """`build_approximate_fund_flow_data` 的持仓过滤。"""

    def test_non_positive_shares_or_cost_skipped(self):
        """份额 ≤0 或成本 ≤0 的持仓不生成近似流水（不冒充建仓记录）。"""
        data = build_approximate_fund_flow_data(
            [
                _holding("A", "正常", 100, 1.5),
                _holding("B", "零份额", 0, 1.5),
                _holding("C", "零成本", 100, 0.0),
            ],
            {"A": 2.0, "B": 2.0, "C": 2.0},
            end_date=_dt.date(2024, 12, 31),
        )
        assert data["available"] is True
        assert data["approximate"] is True
        assert set(data["cost_tiers"]["per_code"]) == {"A"}
