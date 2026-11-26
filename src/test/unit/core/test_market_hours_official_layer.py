# -*- coding: utf-8 -*-
"""市场时段判定第 2 层（官方 API）与口径桶的朴素时间输入。

第 2 层只在「配置开启 official_source + 工作日」时打源：本文件锁定
缓存命中（status 1/2）、缓存未命中后实时取数（1/2/None）、关闭开关、周末
四条分支的判定顺序（缓存未命中不得直接判定闭市）。

时钟用固定北京时点替身（不是 sleep），缓存与取数入口全部 mock。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from src.python.core import market_hours

#: 会话级 autouse fixture 会把 `_is_market_open_official` 换成「恒 None」桩（避免每类首发
#: 打外网）。收集期在 fixture 之前拿到的这个引用才是真实实现——本文件要验的就是它本身，
#: 故固定走该别名，而不是模块属性（后者已被替身覆盖）。
_REAL_OFFICIAL_LAYER = market_hours._is_market_open_official

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _freeze(monkeypatch, moment: datetime) -> None:
    """把模块内 `datetime.now(tz)` 钉在给定时点（其余 datetime 能力保持原样）。"""

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(market_hours, "datetime", _Frozen)


#: 2026-11-25 是周三，13:30 落在下午盘内（official_ttl 取 60s 档）
_WEDNESDAY_INTRADAY = datetime(2026, 11, 25, 13, 30)
#: 同日 20:00（盘后 → official_ttl 取一周档）
_WEDNESDAY_AFTER_HOURS = datetime(2026, 11, 25, 20, 0)
#: 2026-11-28 是周六
_SATURDAY = datetime(2026, 11, 28, 10, 0)


def _config(official_source: bool = True) -> dict:
    return {"market_hours": {"official_source": official_source}}


class TestOfficialLayer:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_config", lambda: _config(False))
        assert _REAL_OFFICIAL_LAYER(13 * 60 + 30) is None

    def test_weekend_returns_none(self, monkeypatch):
        _freeze(monkeypatch, _SATURDAY)
        monkeypatch.setattr("src.python.config.get_config", lambda: _config(True))
        with patch("src.python.cache.get") as cached:
            assert _REAL_OFFICIAL_LAYER(10 * 60) is None
        cached.assert_not_called()

    @pytest.mark.parametrize(("status", "expected"), [(1, True), (2, False)])
    def test_cache_hit_returns_status(self, monkeypatch, status, expected):
        _freeze(monkeypatch, _WEDNESDAY_INTRADAY)
        monkeypatch.setattr("src.python.config.get_config", lambda: _config(True))
        with patch("src.python.cache.get", return_value={"status": status}) as cached:
            assert _REAL_OFFICIAL_LAYER(13 * 60 + 30) is expected
        # 盘中 60s 刷新档
        assert cached.call_args.args[1] == 60

    def test_after_hours_uses_weekly_ttl(self, monkeypatch):
        _freeze(monkeypatch, _WEDNESDAY_AFTER_HOURS)
        monkeypatch.setattr("src.python.config.get_config", lambda: _config(True))
        with patch("src.python.cache.get", return_value={"status": 2}) as cached:
            assert _REAL_OFFICIAL_LAYER(20 * 60) is False
        assert cached.call_args.args[1] == market_hours.CACHE_WEEKLY

    @pytest.mark.parametrize(("status", "expected"), [(1, True), (2, False), (0, None)])
    def test_live_fetch_stores_and_maps_status(self, monkeypatch, status, expected):
        _freeze(monkeypatch, _WEDNESDAY_INTRADAY)
        monkeypatch.setattr("src.python.config.get_config", lambda: _config(True))
        with (
            patch("src.python.cache.get", return_value={"status": 0}),  # 不认识的缓存值 → 落到实时
            patch("src.python.cache.set") as stored,
            patch.object(market_hours, "_fetch_trading_status_from_official", return_value=status),
        ):
            assert _REAL_OFFICIAL_LAYER(13 * 60 + 30) is expected
        # 只要拿到数值就回写缓存（未知状态 0 也缓存，下一轮仍回落 fallback 层）
        stored.assert_called_once_with(market_hours._CACHE_KEY_MARKET_HOURS, {"status": status})


class TestSnapshotBucketNaiveInput:
    def test_naive_datetime_is_interpreted_as_beijing(self, monkeypatch):
        monkeypatch.setattr("src.python.core.trading_calendar.trading_day_as_of_cached", lambda moment: "2026-11-25")
        bucket = market_hours.market_snapshot_bucket(datetime(2026, 11, 25, 10, 0))
        assert bucket.key == "intraday:2026-11-25"
        assert bucket.as_of == "2026-11-25"
        assert bucket.intraday is True

    def test_tz_aware_input_converted_to_beijing(self, monkeypatch):
        from datetime import timezone

        monkeypatch.setattr("src.python.core.trading_calendar.trading_day_as_of_cached", lambda moment: "2026-11-25")
        # UTC 02:00 = 北京 10:00 → 盘中档（不换时区会被判成盘前）
        bucket = market_hours.market_snapshot_bucket(datetime(2026, 11, 25, 2, 0, tzinfo=timezone.utc))
        assert bucket.key == "intraday:2026-11-25"
