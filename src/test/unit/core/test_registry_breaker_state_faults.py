"""数据源注册中心的熔断状态与缓存回退容错测试。

覆盖契约（`core/provider_registry.py`）：
  - 启动加载持久化熔断状态失败不阻断单例初始化
  - 重复注册时自定义熔断阈值/冷却期随注册更新
  - `_load_state` 对「无状态文件 / 文件损坏 / 条目过期 / Provider 未注册」四种情况的处理
  - `is_chain_broken` 的冷却期满恢复与「链中混有未注册 Provider」
  - 会话缓存淘汰在空字典上退化为空操作
  - 交易时段检测异常降级为盘后（CACHE_ONLY）
  - `fetch_cached_only` 的文件缓存回退与 `_cache_date_mismatch` 标记
"""

from __future__ import annotations

import json
import time
from unittest import mock

import pytest

from src.python.core.provider_registry import (
    _CIRCUIT_BREAKER_TTL,
    DataSourceRegistry,
    FetchStrategy,
    get_registry,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _fresh_registry() -> DataSourceRegistry:
    """返回干净的 registry 实例（测试用）。"""
    registry = get_registry()
    registry.reset()
    return registry


# ── 单例初始化与注册 ────────────────────────────────────


class TestRegistryInitAndRegister:
    def test_state_load_failure_does_not_block_init(self, monkeypatch):
        """熔断状态加载抛异常时单例仍完成初始化（首次运行/状态文件异常）。"""
        registry = _fresh_registry()
        registry._initialized = False
        with monkeypatch.context() as m:
            m.setattr(DataSourceRegistry, "_load_state", mock.Mock(side_effect=RuntimeError("bad state")))
            registry.__init__()

        assert registry._initialized is True, "状态加载失败不得让单例停留在未初始化"
        assert registry._providers == {}

    def test_reregister_updates_custom_threshold_and_cooldown(self):
        """重复注册传入自定义阈值/冷却期时覆盖旧值，并写回 cooldown_override。"""
        registry = _fresh_registry()
        registry.register_provider("t1", failure_threshold=3, cooldown_secs=60)
        registry.register_provider("t1", failure_threshold=6, cooldown_secs=120)

        state = registry._providers["t1"]
        assert state.failure_threshold == 6
        assert state.cooldown_secs == 120
        assert state.cooldown_override == 120


# ── 熔断状态加载 ────────────────────────────────────────


class TestLoadBreakerState:
    def test_missing_state_file_is_noop(self, tmp_path, monkeypatch):
        """状态文件不存在时直接返回，不创建任何 Provider。"""
        registry = _fresh_registry()
        monkeypatch.setattr(
            DataSourceRegistry, "_get_breaker_state_path", staticmethod(lambda: str(tmp_path / "none.json"))
        )

        registry._load_state()

        assert registry._providers == {}

    def test_corrupt_state_file_is_skipped(self, tmp_path, monkeypatch):
        """状态文件 JSON 损坏时跳过加载，不影响已注册 Provider 的熔断计数。"""
        registry = _fresh_registry()
        registry.register_provider("t1")
        path = tmp_path / "breaker.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(DataSourceRegistry, "_get_breaker_state_path", staticmethod(lambda: str(path)))

        registry._load_state()

        assert registry._providers["t1"].consecutive_failures == 0

    def test_expired_and_unregistered_entries_are_dropped(self, tmp_path, monkeypatch):
        """超过 TTL 的条目与未注册 Provider 的条目都不回填状态。"""
        registry = _fresh_registry()
        registry.register_provider("fresh")
        path = tmp_path / "breaker.json"
        stale = time.time() - _CIRCUIT_BREAKER_TTL - 1
        path.write_text(
            json.dumps(
                {
                    "fresh": {"_saved_at": stale, "consecutive_failures": 9, "is_skipped": True},
                    "unknown": {"_saved_at": time.time(), "consecutive_failures": 5},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(DataSourceRegistry, "_get_breaker_state_path", staticmethod(lambda: str(path)))

        registry._load_state()

        assert registry._providers["fresh"].consecutive_failures == 0, "过期条目不得回填"
        assert "unknown" not in registry._providers, "未注册 Provider 不因状态文件而凭空注册"


# ── 链式熔断判定 ────────────────────────────────────────


class TestChainBrokenRecovery:
    def test_unregistered_member_ignored_in_recovery_scan(self):
        """链中混有未注册 Provider 时，恢复扫描跳过它且不影响判定结果。"""
        registry = _fresh_registry()
        registry.register_provider("a", cooldown_secs=300)
        with mock.patch("time.time", return_value=1000.0):
            for _ in range(3):
                registry.record_failure("a", "timeout")

        with mock.patch("time.time", return_value=1000.0 + 10):
            assert registry.is_chain_broken(["a", "never_registered"]) is True, "冷却未满应保持全链熔断"
        with mock.patch("time.time", return_value=1000.0 + 400):
            assert registry.is_chain_broken(["a", "never_registered"]) is False, "冷却期满应恢复"


# ── 会话缓存淘汰 ────────────────────────────────────────


class TestSessionCacheEvict:
    def test_evict_on_empty_mapping_is_noop(self):
        """空字典淘汰无候选，退化为空操作（不抛 StopIteration）。"""
        bucket: dict = {}

        DataSourceRegistry._evict_one(bucket)

        assert bucket == {}


# ── 策略选择 ────────────────────────────────────────────


class TestStrategyMarketHoursFault:
    def test_market_hours_error_degrades_to_cache_only(self, monkeypatch):
        """交易时段检测自身异常时按盘后处理（CACHE_ONLY），不发起实时取数。"""
        registry = _fresh_registry()
        monkeypatch.setattr(
            "src.python.core.market_hours.is_market_open",
            mock.Mock(side_effect=RuntimeError("calendar down")),
        )

        assert registry.get_effective_strategy("a_share") is FetchStrategy.CACHE_ONLY


# ── 文件缓存回退 ────────────────────────────────────────


class TestFetchCachedOnlyFileFallback:
    def test_same_day_file_cache_clears_mismatch_flag(self, monkeypatch):
        """文件缓存 price_date 为当日时，落 session cache 并标记日期未失配。"""
        registry = _fresh_registry()
        today = time.strftime("%Y-%m-%d")
        monkeypatch.setattr("src.python.cache.get", mock.Mock(return_value={"price_date": today}))

        data = registry.fetch_cached_only("600519", cache_key_fn=lambda code: f"price_stock_{code}")

        assert data["_cache_date_mismatch"] is False
        cached = registry.session_cache_get("price", "600519")
        assert cached is not None and cached["_cache_date_mismatch"] is False, "命中回填 session cache 以加速后续读取"

    def test_stale_file_cache_marks_mismatch(self, monkeypatch):
        """文件缓存日期非当日时标记 _cache_date_mismatch=True，供详情行降级展示。"""
        registry = _fresh_registry()
        monkeypatch.setattr("src.python.cache.get", mock.Mock(return_value={"price_date": "2000-01-01"}))

        data = registry.fetch_cached_only("600519", cache_key_fn=lambda code: f"price_stock_{code}")

        assert data["_cache_date_mismatch"] is True
        assert data["price_date"] == "2000-01-01", "回退读取不得改写缓存中的价格日期"
