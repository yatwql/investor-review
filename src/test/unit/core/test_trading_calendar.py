"""交易日历原语单元测试。

测试目标：
  - count_trading_days_elapsed — 按交易日（而非自然日）统计区间内经过的交易日数
  - 回退口径 — 交易日历不可用时按「排除周六日」近似计数

运行：
  pytest src/test/unit/core/test_trading_calendar.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from src.python.core.trading_calendar import count_trading_days_elapsed

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

# 测试日历（2026 年 9-10 月片段）：09-16 ~ 09-25 与 10-01 ~ 10-07 为假期
_TEST_CALENDAR = {
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-28",
    "2026-09-29",
    "2026-09-30",
    "2026-10-08",
    "2026-10-09",
    "2026-10-12",
}


def _with_calendar(calendar: set[str]):
    """打桩交易日历（隔离 akshare 网络调用）。"""
    return patch("src.python.core.trading_calendar._get_trading_calendar", return_value=calendar)


class TestCountTradingDaysElapsed:
    """交易日计数（不含起点、含终点）。"""

    def test_adjacent_trading_days_elapse_one(self):
        """相邻两个交易日 → 1。"""
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("2026-09-10", "2026-09-11") == 1

    def test_weekend_is_not_counted(self):
        """周五 → 下周一：跨越周末但仅经过 1 个交易日。"""
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("2026-09-11", "2026-09-14") == 1

    def test_long_holiday_counts_as_one_trading_day(self):
        """长假前后相邻的两个交易日相差 8 个自然日，但仅经过 1 个交易日。

        缺陷场景：按自然日差判定会把长假前后的正常间隔误判为「延迟/停更」。
        """
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("2026-09-30", "2026-10-08") == 1

    def test_counts_every_session_in_range(self):
        """区间内每个交易日各计一次（不含起点、含终点）。"""
        with _with_calendar(_TEST_CALENDAR):
            # 2026-09-09 / 09-10 / 09-11 / 09-14 / 09-15 共 5 个交易日
            assert count_trading_days_elapsed("2026-09-08", "2026-09-15") == 5

    def test_same_date_returns_zero(self):
        """起点 == 终点 → 0。"""
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("2026-09-11", "2026-09-11") == 0

    def test_reverse_order_returns_zero(self):
        """起点晚于终点（数据异常）→ 0。"""
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("2026-09-11", "2026-09-10") == 0

    def test_invalid_date_returns_none(self):
        """日期格式非法 → None（消费方按「未知」处理）。"""
        with _with_calendar(_TEST_CALENDAR):
            assert count_trading_days_elapsed("not-a-date", "2026-09-11") is None
            assert count_trading_days_elapsed("2026-09-11", "") is None


class TestCalendarUnavailableFallback:
    """交易日历不可用时的近似口径（排除周六日）。"""

    def test_weekend_still_excluded(self):
        """日历不可用 → 周五到下周一只计 1（周六日不算交易日）。"""
        with _with_calendar(set()):
            assert count_trading_days_elapsed("2026-09-11", "2026-09-14") == 1

    def test_saturday_not_counted(self):
        """日历不可用 → 周六不计入。"""
        with _with_calendar(set()):
            assert count_trading_days_elapsed("2026-09-11", "2026-09-12") == 0


class TestHithinkCalendarFallback:
    """akshare 不可用 → 同花顺官方近一年交易日序列兜底（需 key；再失败才走简易判断）。"""

    def test_official_series_used_when_akshare_fails(self, monkeypatch):
        from src.python.core import trading_calendar as tc

        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        written: list = []
        monkeypatch.setattr(tc.cache, "set", lambda key, value: written.append((key, value)))
        monkeypatch.setitem(sys.modules, "akshare", None)  # import akshare 触发 ImportError
        # 兜底经注册钩子注入（core 不反向 import providers）
        original = tc._TRADING_DAYS_FALLBACK
        tc.register_trading_days_fallback(lambda: {"item": [{"date": "2026-09-17"}, {"date": "2026-09-18"}]})
        try:
            dates = tc._get_trading_calendar()
        finally:
            tc._TRADING_DAYS_FALLBACK = original
        assert dates == {"2026-09-17", "2026-09-18"}
        assert written  # 官方序列同样写缓存

    def test_both_sources_fail_returns_empty(self, monkeypatch):
        from src.python.core import trading_calendar as tc
        from src.python.providers import hithink

        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        monkeypatch.setattr(tc.cache, "set", lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, "akshare", None)
        monkeypatch.setattr(hithink, "fetch_trading_days", lambda: None)
        assert tc._get_trading_calendar() == set()


class TestFallbackRegistration:
    """官方序列兜底经注册钩子注入（core 不反向 import providers——分层纪律）。"""

    def test_unregister_returns_empty_calendar(self, monkeypatch):
        from src.python.core import trading_calendar as tc

        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, "akshare", None)  # 阻断主链路（兜底已卸除）
        original = tc._TRADING_DAYS_FALLBACK
        tc._TRADING_DAYS_FALLBACK = None
        try:
            assert tc._get_trading_calendar() == set()
        finally:
            tc._TRADING_DAYS_FALLBACK = original

    def test_fallback_exception_swallowed(self, monkeypatch):
        """兜底函数抛异常 → 降级空集合（与官方源不可用同语义），不向上抛。"""
        from src.python.core import trading_calendar as tc

        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, "akshare", None)
        original = tc._TRADING_DAYS_FALLBACK
        tc.register_trading_days_fallback(lambda: (_ for _ in ()).throw(RuntimeError("down")))
        try:
            assert tc._get_trading_calendar() == set()
        finally:
            tc._TRADING_DAYS_FALLBACK = original


class TestElapsedTradingDaysWithNaturalFallback:
    """历时统计：正常按交易日计，日历/日期不可用回退自然日保底非负。"""

    def test_unknown_dates_fall_back_to_weekday_exclusion(self, monkeypatch):
        """日历不可用 → 回退「排除周六日」近似计数（2024-12-20(五)→12-27(五) 经 5 个工作日）。"""
        from src.python.core import trading_calendar as tc

        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        monkeypatch.setitem(sys.modules, "akshare", None)
        original = tc._TRADING_DAYS_FALLBACK
        tc._TRADING_DAYS_FALLBACK = None
        try:
            assert tc.elapsed_trading_days_with_natural_fallback("2024-12-20", "2024-12-27") == 5
        finally:
            tc._TRADING_DAYS_FALLBACK = original

    def test_negative_interval_clamped_to_zero(self):
        """end 早于 start（异常数据）→ 差值钳为 0，不为负。"""
        from src.python.core import trading_calendar as tc

        tc.register_trading_days_fallback(lambda: {})
        assert tc.elapsed_trading_days_with_natural_fallback("2024-12-27", "2024-12-20") == 0

    def test_unparseable_dates_return_zero(self):
        """两端日期均不可解析 → 0（不中断展示，且不会为零值误判崩溃）。"""
        from src.python.core import trading_calendar as tc

        tc.register_trading_days_fallback(lambda: {})
        assert tc.elapsed_trading_days_with_natural_fallback("not-a-date", "2024-12-27") == 0
        assert tc.elapsed_trading_days_with_natural_fallback("", "bad-end") == 0

    def test_trading_calendar_available_counts_trading_days(self, monkeypatch):
        """日历可用 → 按交易日计（扣除周末/节假日）。"""
        from src.python.core import trading_calendar as tc

        monkeypatch.setattr(
            tc, "count_trading_days_elapsed", lambda s, e: 5 if (s, e) == ("2024-12-20", "2024-12-27") else None
        )
        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: None)
        assert tc.elapsed_trading_days_with_natural_fallback("2024-12-20", "2024-12-27") == 5


class TestCalendarProcessMemo:
    """进程内日历 memo：同一进程内高频调用不得重复读盘解析（回归实测 600+ 次）。"""

    def test_second_call_reuses_memo_without_cache_read(self, monkeypatch, tmp_path):
        from src.python.core import trading_calendar as tc

        # 缓存文件真实存在（memo 的失效判据含文件指纹）
        cache_file = tmp_path / "trading_calendar.json"
        cache_file.write_text('{"_ts": 1, "_data": []}', encoding="utf-8")
        monkeypatch.setattr(tc.cache, "get_cache_path", lambda key: str(cache_file))
        monkeypatch.setattr(tc.cache, "get_ttl", lambda *a, **k: 3600.0)

        calls = {"n": 0}

        def _fake_get(key, ttl):
            calls["n"] += 1
            return ["2026-09-17", "2026-09-18"]

        monkeypatch.setattr(tc.cache, "get", _fake_get)
        tc._reset_calendar_memo()

        first = tc._get_trading_calendar()
        second = tc._get_trading_calendar()

        assert first == {"2026-09-17", "2026-09-18"}
        assert second == first
        assert calls["n"] == 1, "第二次调用应命中进程内 memo，不再读缓存文件"

    def test_memo_invalidated_when_cache_file_rewritten(self, monkeypatch, tmp_path):
        """缓存文件被重写（指纹变化）→ 必须回落磁盘，不得继续用旧日历。"""
        from src.python.core import trading_calendar as tc

        cache_file = tmp_path / "trading_calendar.json"
        cache_file.write_text('{"_ts": 1, "_data": []}', encoding="utf-8")
        monkeypatch.setattr(tc.cache, "get_cache_path", lambda key: str(cache_file))
        monkeypatch.setattr(tc.cache, "get_ttl", lambda *a, **k: 3600.0)

        payload = {"dates": ["2026-09-17"]}
        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: payload["dates"])
        tc._reset_calendar_memo()

        assert tc._get_trading_calendar() == {"2026-09-17"}
        payload["dates"] = ["2026-10-08"]
        cache_file.write_text('{"_ts": 2, "_data": []}', encoding="utf-8")  # 指纹变化

        assert tc._get_trading_calendar() == {"2026-10-08"}

    def test_memo_returns_copy_so_callers_cannot_corrupt_it(self, monkeypatch, tmp_path):
        """调用方拿到的必须是副本：改它不能污染后续调用（日历是共享只读事实）。"""
        from src.python.core import trading_calendar as tc

        cache_file = tmp_path / "trading_calendar.json"
        cache_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(tc.cache, "get_cache_path", lambda key: str(cache_file))
        monkeypatch.setattr(tc.cache, "get_ttl", lambda *a, **k: 3600.0)
        monkeypatch.setattr(tc.cache, "get", lambda *a, **k: ["2026-09-17"])
        tc._reset_calendar_memo()

        first = tc._get_trading_calendar()
        first.discard("2026-09-17")
        assert tc._get_trading_calendar() == {"2026-09-17"}


class TestCalendarFailureCooldown:
    """日历取不到时须记失败冷却：同一进程内不重复探源（否则同键未命中告警成噪音）。

    现场（README 截图复核）：演示报告一轮内 `trading_calendar` 同一缓存键未命中 6 次，
    每次都重新尝试 akshare + 兜底源；而日历缺失时调用方本就回落周度判断，重探不改变结果。
    """

    def _fail_asis(self):
        """akshare 与兜底源同时不可用（真实失败态）。"""
        from unittest.mock import patch as _patch

        return [
            _patch.dict(sys.modules, {"akshare": None}),
            _patch("src.python.core.trading_calendar._TRADING_DAYS_FALLBACK", None),
            _patch("src.python.core.trading_calendar.cache.get", return_value=None),
        ]

    def test_repeated_calls_probe_once_within_cooldown(self):
        from src.python.core import trading_calendar as tc

        tc._reset_calendar_memo()
        patches = self._fail_asis()
        for p in patches:
            p.start()
        try:
            assert tc._get_trading_calendar() == set()
            assert tc._calendar_failure_active() is True
            assert tc._get_trading_calendar() == set()
            assert tc._get_trading_calendar() == set()
        finally:
            for p in patches:
                p.stop()
            tc._reset_calendar_memo()

    def test_cooldown_expires_and_retries(self):
        from unittest.mock import patch as _patch

        from src.python.core import trading_calendar as tc

        tc._reset_calendar_memo()
        with _patch.object(tc, "_CAL_FAILURE_COOLDOWN_SECONDS", 60.0), _patch.object(
            tc.time, "monotonic", return_value=1000.0
        ):
            tc._calendar_failure_mark()
            assert tc._calendar_failure_active() is True
        with _patch.object(tc.time, "monotonic", return_value=1061.0):
            assert tc._calendar_failure_active() is False
        tc._reset_calendar_memo()


class TestCachedTradingDaysSingleSource:
    """「只看已缓存日历」的调用方须走统一出口：共用 memo、不重复读盘、不触网。"""

    def test_repeated_reads_hit_memo_once(self):
        from unittest.mock import patch as _patch

        from src.python.core import trading_calendar as tc

        tc._reset_calendar_memo()
        calls = []

        def _fake_get(key, ttl=None):
            calls.append(key)
            return ["2026-11-02", "2026-11-03"]

        with _patch.object(tc.cache, "get", side_effect=_fake_get), _patch.object(
            tc.cache, "get_ttl", return_value=86400.0
        ):
            assert tc.cached_trading_days() == ["2026-11-02", "2026-11-03"]
            assert tc.cached_trading_days() == ["2026-11-02", "2026-11-03"]
        assert len(calls) == 1, "第二次起须由进程内 memo 供给，不再读缓存文件"
        tc._reset_calendar_memo()

    def test_never_fetches_when_cache_empty(self):
        from unittest.mock import patch as _patch

        from src.python.core import trading_calendar as tc

        tc._reset_calendar_memo()
        with _patch.object(tc.cache, "get", return_value=None), _patch.object(
            tc, "_get_trading_calendar", side_effect=AssertionError("不得触网")
        ):
            assert tc.cached_trading_days() == []
        tc._reset_calendar_memo()

    def test_data_freshness_uses_shared_exit(self):
        """数据新鲜度判定经统一出口取值（不再各自 cache.get 同一键）。"""
        import inspect

        from src.python.core import data_freshness

        src = inspect.getsource(data_freshness._cached_trading_days)
        assert "cached_trading_days" in src
        assert 'cache.get("trading_calendar"' not in src
