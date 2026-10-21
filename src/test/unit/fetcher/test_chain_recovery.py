"""test_chain 兄弟分片（recovery）：短缓存全量重取与纠正连击冷却。"""

from __future__ import annotations
import unittest
from unittest.mock import patch
from src.python.fetcher.chain import (
    fetch_with_incremental_fallback,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestShortCacheFullRefetch(unittest.TestCase):
    """缓存历史短于请求窗口时的全量补齐行为（滚动窗口数据底座约束）。"""

    def _days(self, n: int, start: str = "2026-01-01") -> list[dict]:
        from datetime import date, timedelta

        out = []
        d = date.fromisoformat(start)
        while len(out) < n:
            if d.weekday() < 5:
                out.append({"date": d.isoformat(), "close": 10.0})
            d += timedelta(days=1)
        return out

    def test_short_cache_forces_full_fetch(self):
        """缓存 15 条 < 请求 30 条 → start_from 置 None 全量拉取并整段替换缓存。"""
        cached = self._days(15, start="2026-01-01")
        full = self._days(30, start="2025-11-01")  # 起点早于缓存 → 走全量替换分支

        with (
            patch(
                "src.python.fetcher.chain_incremental.cache_get",
                return_value=cached,
            ),
            patch("src.python.fetcher.chain_incremental.cache_set") as mock_set,
            patch(
                "src.python.fetcher.chain_incremental._try_providers",
                return_value=full,
            ) as mock_try,
        ):
            result = fetch_with_incremental_fallback("history_stock", "600000", 30)

        # start_from=None（第 6 个位置参数）→ provider 从头拉满 days 条
        self.assertIsNone(mock_try.call_args[0][5])
        self.assertEqual(len(result), 30)
        mock_set.assert_called()

    def test_long_cache_keeps_incremental(self):
        """缓存 ≥ 请求窗口 → 维持增量语义（start_from = 缓存末日），不触发全量。"""
        cached = self._days(40, start="2026-01-01")
        last = cached[-1]["date"]
        new_bars = [{"date": "2026-03-16", "close": 10.5}]

        with (
            patch(
                "src.python.fetcher.chain_incremental.cache_get",
                return_value=cached,
            ),
            patch("src.python.fetcher.chain_incremental.cache_set"),
            # 连续性校验会走交易日历（测试隔离环境不建真实日历连接）
            patch(
                "src.python.fetcher.chain_incremental._validate_continuity",
                return_value=False,
            ),
            patch(
                "src.python.fetcher.chain_incremental._try_providers",
                return_value=new_bars,
            ) as mock_try,
        ):
            result = fetch_with_incremental_fallback("history_stock", "600000", 30)

        self.assertEqual(mock_try.call_args[0][5], last)
        self.assertEqual(len(result), 30)


class TestCorrectionStreakCooldown(unittest.TestCase):
    """历史修正全量刷新的连续触发冷却（源结构性回看）。

    部分源对增量请求固定向前回看若干天：重叠每次运行都检出、全量刷新无法根治。
    连续检出达到阈值后跳过全量刷新（按日合并的同日覆盖已吸收窗口内修正）；
    一次无重叠的合并成功即重置计数，保证真历史修正仍能获得全量刷新机会。
    """

    def _days(self, n: int, start: str = "2026-01-01") -> list[dict]:
        from datetime import date, timedelta

        out = []
        d = date.fromisoformat(start)
        while len(out) < n:
            if d.weekday() < 5:
                out.append({"date": d.isoformat(), "close": 10.0})
            d += timedelta(days=1)
        return out

    def _streak_store(self, cached):
        """cache_get/cache_set 假件：主键返回 cached，修正连续计数键读写 store。"""
        store = {"streak": 0}

        def fake_get(key, ttl=None, **_kw):
            if key.endswith("_correction_streak"):
                return store["streak"]
            return cached

        def fake_set(key, value, *_a, **_kw):
            if key.endswith("_correction_streak"):
                store["streak"] = value

        return store, fake_get, fake_set

    def test_streak_cools_down_full_refresh(self):
        """连续检出重叠达阈值 → 跳过全量刷新，仍返回按日合并结果。"""
        from src.python.fetcher import chain_incremental as ci

        skip = ci._CORRECTION_STREAK_SKIP  # 阈值从真值源取（不写死演进量）
        cached = self._days(30, start="2026-01-01")
        # 首日落在缓存区间内部 → 不命中「provider 全量返回」替换分支，走重叠检测
        overlapping = [{"date": "2026-01-20", "close": 9.0}, {"date": cached[-1]["date"], "close": 10.1}]
        store, fake_get, fake_set = self._streak_store(cached)
        full_calls = {"n": 0}

        def fake_try(providers, registry, chain_name, code, days, start_from, diagnostics=None):
            if start_from is None:
                full_calls["n"] += 1
                return []  # 全量刷新失败：冷却逻辑与刷新成败无关
            return overlapping

        with (
            patch("src.python.fetcher.chain_incremental.cache_get", side_effect=fake_get),
            patch("src.python.fetcher.chain_incremental.cache_set", side_effect=fake_set),
            patch("src.python.fetcher.chain_incremental.cache_clear"),
            patch("src.python.fetcher.chain_incremental._validate_continuity", return_value=True),
            patch("src.python.fetcher.chain_incremental._try_providers", side_effect=fake_try),
        ):
            result = []
            for _ in range(skip):
                result = fetch_with_incremental_fallback("history_stock", "600000", 30)

        # 前 skip-1 次全量刷新，第 skip 次冷却跳过 → 共 skip-1 次全量调用
        self.assertEqual(full_calls["n"], skip - 1)
        self.assertEqual(store["streak"], skip)  # 持续累计（检出重叠的合并不重置计数）
        self.assertTrue(result)  # 冷却跳过仍返回合并结果（降级不阻断）

    def test_streak_resets_after_clean_merge(self):
        """一次无重叠的合并成功 → 计数重置（真修正仍能获得全量刷新机会）。"""
        cached = self._days(30, start="2026-01-01")
        fresh = [{"date": cached[-1]["date"], "close": 10.2}]  # 首日 = 缓存末日 → 无重叠
        store, fake_get, fake_set = self._streak_store(cached)
        store["streak"] = 2

        with (
            patch("src.python.fetcher.chain_incremental.cache_get", side_effect=fake_get),
            patch("src.python.fetcher.chain_incremental.cache_set", side_effect=fake_set),
            patch("src.python.fetcher.chain_incremental._validate_continuity", return_value=False),
            patch("src.python.fetcher.chain_incremental._try_providers", return_value=fresh),
        ):
            fetch_with_incremental_fallback("history_stock", "600000", 30)

        self.assertEqual(store["streak"], 0)
