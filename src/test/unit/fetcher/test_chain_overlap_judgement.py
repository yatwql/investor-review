"""历史增量链路的重叠判定：**日期重叠 ≠ 历史修正，重叠段数值变化才是**。

回归背景：历史接口的增量参数是「从某日起的最近 N 条」，N 大于缓存覆盖时必然整段
重叠。旧口径「只要重叠就全量刷新」把正常衔接误判为除权修正——实测一次运行触发
两次（个股 400 天 + 沪深300 2928 天），同一份数据被整段重拉。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.fetcher.chain_incremental import _RUN_HISTORY_MEMO, _validate_continuity

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_fetcher,
    pytest.mark.usefixtures("offline_external_sources"),
]


def _bars(dates: list[str], close: float = 10.0) -> list[dict]:
    """构造升序日线（价格四键同值，便于按需改价）。"""
    return [{"date": d, "open": close, "close": close, "high": close, "low": close, "volume": 1000} for d in dates]


_CACHED_DATES = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]


class TestOverlapValueAwareJudgement:
    """`_validate_continuity` 的两层判据。"""

    def test_identical_values_are_not_a_revision(self):
        """重叠日期数值一致 → 正常衔接，不触发全量刷新、不打修正标记。"""
        cached = _bars(_CACHED_DATES)
        new = _bars(["2026-01-07", "2026-01-08", "2026-01-09"])  # 整窗后移，重叠两天
        with patch("src.python.fetcher.chain_incremental.cache_set") as mock_set:
            assert _validate_continuity(cached, new, "history_history_stock_600000") is False
        mock_set.assert_not_called()

    def test_changed_values_are_a_revision(self):
        """重叠日期价格变化 1% → 判定历史修正，置修正标记。"""
        cached = _bars(_CACHED_DATES)
        new = _bars(["2026-01-07", "2026-01-08", "2026-01-09"])
        new[0]["close"] = cached[2]["close"] * 1.01  # 重叠首日价格变了
        with patch("src.python.fetcher.chain_incremental.cache_set") as mock_set:
            assert _validate_continuity(cached, new, "history_history_stock_600001") is True
        mock_set.assert_any_call("history_history_stock_600001_correction_flag", True)

    def test_rounding_noise_within_tolerance_is_benign(self):
        """末位舍入差（相对 1e-6）不构成修正——复权价两次请求可差末位。"""
        cached = _bars(_CACHED_DATES, close=10.0)
        new = _bars(["2026-01-07", "2026-01-08", "2026-01-09"], close=10.0)
        new[0]["close"] = 10.00001
        with patch("src.python.fetcher.chain_incremental.cache_set"):
            assert _validate_continuity(cached, new, "history_history_stock_600002") is False

    def test_no_overlap_returns_false(self):
        """无日期重叠（新数据全在缓存末日之后）→ 不是修正。"""
        cached = _bars(_CACHED_DATES)
        new = _bars(["2026-01-09", "2026-01-12"])
        with patch("src.python.fetcher.chain_incremental.cache_set") as mock_set:
            assert _validate_continuity(cached, new, "history_history_stock_600003") is False
        mock_set.assert_not_called()


class TestEndToEndNoDoubleFetch:
    """整窗重叠时只向 provider 请求一次（不再整段重拉）。"""

    @staticmethod
    def _cached(n: int = 40) -> list[dict]:
        from datetime import date, timedelta

        out, d = [], date(2026, 1, 1)
        while len(out) < n:
            if d.weekday() < 5:
                out.append({"date": d.isoformat(), "close": 10.0})
            d += timedelta(days=1)
        return out

    def test_benign_overlap_fetches_once(self):
        from src.python.fetcher.chain_incremental import fetch_with_incremental_fallback

        cached = self._cached(40)
        last = cached[-1]["date"]
        # 源按「最近 N 条」返回：整窗后移一天，与缓存大段重叠但数值一致
        overlapping = [dict(r) for r in cached[-10:]] + [{"date": "2099-01-01", "close": 10.0}]
        _RUN_HISTORY_MEMO.clear()

        with (
            patch("src.python.fetcher.chain_incremental.cache_get", return_value=cached),
            patch("src.python.fetcher.chain_incremental.cache_set"),
            patch("src.python.fetcher.chain_incremental.cache_clear") as mock_clear,
            patch(
                "src.python.fetcher.chain_incremental._try_providers",
                return_value=overlapping,
            ) as mock_try,
        ):
            result = fetch_with_incremental_fallback("history_stock", "600010", 30)

        assert mock_try.call_count == 1, "整窗重叠且数值一致时不得再拉一次全量"
        mock_clear.assert_not_called()
        assert result and result[-1]["date"] == "2099-01-01"
        assert last
