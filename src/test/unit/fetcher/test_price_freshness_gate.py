"""价格缓存新鲜度门禁 —— 盘中残留不得被当成收盘价（数据敏感性的核心防线）。

背景：缓存 TTL 只管"多旧算过期"，管不了"这份数据是什么时候抓的"。若 T 日 13:01 抓到
的盘中价在盘后 15:30 仍被当作"当日收盘价"使用，「本日盈亏」与「快照环比」会系统性
偏离真实涨跌。`_price_cache_fresh` 因此做两道校验：

1. **日期门禁**：`price_date` 必须 ≥ 该路由允许的最新交易日（场外 QDII 合法 T-1）；
2. **收盘时点门禁**：T 日已收盘时，缓存写入时刻必须 ≥ T 日 15:00。

本文件直接测这两道门禁（既有用例多把该函数 mock 掉，门禁本身缺直接覆盖）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.fetcher.price import _price_cache_fresh

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]

_TODAY = "2026-10-23"  # 周五
_YESTERDAY = "2026-10-22"
_CLOSE_TS = 1_790_000_000.0  # 任意收盘 epoch（具体值由测试注入）


def _gate(data, data_type="price_stock", name="", cache_key="price_600519", *, market_open=False):
    """在受控环境下调用门禁：固定交易日、收盘 epoch、缓存写入时刻与当前时刻。"""
    captured = data.pop("_captured_at", None)

    def _fake_captured(_key):
        # 真实实现：无 cache_key 直接返回 None（跳过时点门禁）
        return None if _key is None else captured

    with (
        patch("src.python.core.market_hours.is_market_open", return_value=market_open),
        patch("src.python.report.market_value.get_last_trading_day", return_value=_TODAY),
        patch("src.python.report.market_value.get_prev_trading_day", return_value=_YESTERDAY),
        patch("src.python.fetcher.price._cache_captured_at", side_effect=_fake_captured),
        patch("src.python.fetcher.price._trading_day_close_epoch", return_value=_CLOSE_TS),
        patch("src.python.fetcher.price.time.time", return_value=_CLOSE_TS + 1800),
    ):
        return _price_cache_fresh(data, data_type, name=name, cache_key=cache_key)


class TestCloseTimeGate:
    """收盘时点门禁：T 日盘中写入的缓存盘后必须失效。"""

    def test_intraday_written_cache_rejected_after_close(self):
        """13:01 抓的盘中价，盘后不得当作当日收盘价（历史故障场景）。"""
        assert _gate({"price_date": _TODAY, "_captured_at": _CLOSE_TS - 7200}) is False

    def test_after_close_written_cache_accepted(self):
        """收盘后（15:05）抓的价是真正的收盘价，可以复用。"""
        assert _gate({"price_date": _TODAY, "_captured_at": _CLOSE_TS + 300}) is True

    def test_morning_session_price_accepted_during_market(self):
        """盘中不施加时点门禁（短 TTL 已保证实时性）。"""
        assert _gate({"price_date": _TODAY, "_captured_at": _CLOSE_TS - 7200}, market_open=True) is True

    def test_missing_cache_key_skips_time_gate(self):
        """不传 cache_key 时跳过时点校验（旧调用面），仍按日期门禁判定。"""
        assert _gate({"price_date": _TODAY, "_captured_at": _CLOSE_TS - 7200}, cache_key=None) is True


class TestDateGate:
    """日期门禁：跨日残留与场内/场外 QDII 的差异。"""

    def test_stale_previous_day_rejected(self):
        assert _gate({"price_date": _YESTERDAY, "_captured_at": _CLOSE_TS + 300}) is False

    def test_missing_price_date_rejected(self):
        assert _gate({"_captured_at": _CLOSE_TS + 300}) is False

    def test_domestic_otc_previous_day_rejected(self):
        """国内场外 T 日当晚即披露 → 盘后仍是 T-1 属过期。"""
        assert (
            _gate(
                {"price_date": _YESTERDAY, "_captured_at": _CLOSE_TS + 300},
                data_type="price_fund_otc",
                name="易方达蓝筹精选",
            )
            is False
        )

    def test_qdii_previous_day_accepted(self):
        """QDII 因海外时差与披露节奏 T-1 属合法新鲜度。"""
        with patch("src.python.fetcher.price.is_qdii_extended", return_value=True):
            assert (
                _gate(
                    {"price_date": _YESTERDAY, "_captured_at": _CLOSE_TS + 300},
                    data_type="price_fund_otc",
                    name="华夏纳斯达克100ETF联接",
                )
                is True
            )
