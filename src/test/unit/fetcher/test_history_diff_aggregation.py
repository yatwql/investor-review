"""快照差异聚合（`fetcher/history_diff`）：跨账户同码合并与时间戳兜底。

锁住的契约：
  - 同一 code 出现在多个账户 → 先按份额加权合并成本价、市值/盈亏累加，
    差异只与合并后的口径比较（否则同码会被当成两条独立持仓重复计差）；
  - 时间戳任一侧不可解析 → `days_since_last_report` 记 0（不猜天数）；
  - 时间戳解析只认四种写法，其余返回 None（不得抛异常打断环比段落）。
"""

from __future__ import annotations

import pytest

from src.python.fetcher.history_diff import HistoryDiff, _parse_timestamp
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]

_TS_OLD = "2026-07-01T10:00:00"
_TS_NEW = "2026-07-11T10:00:00"


def _holding(shares: float, cost_price: float, market_value: float, total_pnl: float = 0.0) -> SnapshotHolding:
    return SnapshotHolding(
        code="600519",
        name="贵州茅台",
        shares=shares,
        cost_price=cost_price,
        market_value=market_value,
        total_pnl=total_pnl,
        cost_total=cost_price * shares,
    )


def _snapshot(timestamp: str, accounts: tuple[AccountSnapshot, ...]) -> SnapshotData:
    return SnapshotData(accounts=accounts, total_value=0.0, timestamp=timestamp)


class TestSameCodeAcrossAccounts:
    def test_holdings_of_same_code_are_weighted_merged(self):
        """A 账户 400 份 @200、B 账户 200 份 @250 → 合并后 600 份 @216.67（加权成本）。"""
        old = _snapshot(
            _TS_OLD,
            (
                AccountSnapshot("A", (_holding(400.0, 200.0, 80000.0),)),
                AccountSnapshot("B", (_holding(200.0, 250.0, 50000.0),)),
            ),
        )
        merged = HistoryDiff._index_holdings(old)

        assert list(merged) == ["600519"]
        assert merged["600519"].shares == pytest.approx(600.0)
        assert merged["600519"].market_value == pytest.approx(130000.0)
        assert merged["600519"].cost_price == pytest.approx((200.0 * 400 + 250.0 * 200) / 600)

    def test_diff_uses_merged_shares(self):
        """合并口径下加仓 100 份：新增份额按合并后差额算，不是按单账户差额。"""
        old = _snapshot(
            _TS_OLD,
            (
                AccountSnapshot("A", (_holding(400.0, 200.0, 80000.0),)),
                AccountSnapshot("B", (_holding(200.0, 250.0, 50000.0),)),
            ),
        )
        new = _snapshot(
            _TS_NEW,
            (
                AccountSnapshot("A", (_holding(450.0, 200.0, 90000.0),)),
                AccountSnapshot("B", (_holding(250.0, 250.0, 62000.0),)),
            ),
        )

        summary = HistoryDiff.compute(new, old)

        assert [d.code for d in summary.increased] == ["600519"]
        assert summary.increased[0].shares_diff == pytest.approx(100.0)
        assert summary.days_since_last_report == 10


class TestTimestampFallbacks:
    def test_unparsable_timestamp_yields_zero_days(self):
        """任一侧时间戳不合法 → 天数记 0（不按默认天数硬凑）。"""
        assert HistoryDiff._compute_days_since(_TS_NEW, "不是时间戳") == 0
        assert HistoryDiff._compute_days_since("2026/07/11", _TS_OLD) == 0

    def test_parse_timestamp_unknown_format_returns_none(self):
        assert _parse_timestamp("2026/07/11 10:00") is None
        assert _parse_timestamp("20260711").isoformat().startswith("2026-07-11")
