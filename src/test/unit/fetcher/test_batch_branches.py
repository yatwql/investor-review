"""batch 残余分支 — 注册表加载失败、缓存预检异常与配置读取失败的回退口径。

锁住的契约：
  - `execute_with_chain_precheck` 惰性加载注册表失败 → 跳过熔断预检直接执行
    （fail-open，不因预检故障丢批次）；
  - `execute_with_cache_check` 在 CACHE_ONLY 策略下 cache_check_fn 抛异常 →
    该资产记失败结果（error 带异常文本），同批其余资产照常返回；
  - `get_batch_worker_count`：``max_total_workers`` 非法（<1）回退默认上限；
    配置读取整体抛异常时回退调用方给的 default；
  - `get_strategy_hook` 注册表构造失败 → None（调用方退化为无钩子执行）；
  - `_build_rate_limiter_from_config` 配置读取失败 → 空配置限速器。
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from src.python.fetcher.batch import (
    BatchDispatcher,
    _build_rate_limiter_from_config,
    get_batch_worker_count,
    get_strategy_hook,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestChainPrecheckRegistryFault:
    """注册表加载失败时跳过熔断预检（fail-open）。"""

    def test_registry_load_failure_runs_tasks(self):
        """get_registry 抛异常 → 任务照常执行并返回结果。"""
        with BatchDispatcher(max_workers=1) as dispatcher:
            with patch("src.python.core.provider_registry.get_registry", side_effect=RuntimeError("registry down")):
                results = dispatcher.execute_with_chain_precheck([("id_a", lambda: 42)], "price_stock")

        assert [r.result for r in results] == [42]


class TestCacheCheckFault:
    """CACHE_ONLY 策略下缓存预检异常的逐项隔离。"""

    def test_cache_check_error_becomes_failed_result(self):
        """cache_check_fn 抛异常 → 该项 success=False 且 error 含异常文本。"""
        with BatchDispatcher(max_workers=1) as dispatcher:
            results = dispatcher.execute_with_cache_check(
                [("id_a", lambda: "live")],
                lambda cache_id: (_ for _ in ()).throw(RuntimeError(f"cache broken: {cache_id}")),
                strategy_hook=lambda: "cache",
            )

        assert results[0].success is False
        assert "cache broken: id_a" in results[0].error


class TestWorkerCountFallbacks:
    """并发上限配置的回退口径。"""

    def test_invalid_max_total_falls_back_to_default_cap(self):
        """``max_total_workers`` 非法（<1）时的结果与一个足够大的合法上限一致。"""
        with patch("src.python.config.get_config", return_value={"batch": {"max_total_workers": 0}}):
            broken_cap = get_batch_worker_count("max_workers_price", 3)
        with patch("src.python.config.get_config", return_value={"batch": {"max_total_workers": 64}}):
            valid_cap = get_batch_worker_count("max_workers_price", 3)

        assert broken_cap == valid_cap

    def test_config_read_failure_returns_default(self):
        """配置读取抛异常 → 返回调用方给的 default。"""
        with patch("src.python.config.get_config", side_effect=RuntimeError("config broken")):
            assert get_batch_worker_count("max_workers_price", 7) == 7


class TestStrategyHookFault:
    """策略钩子构造失败 → None。"""

    def test_registry_failure_returns_none(self):
        """注册表不可用 → None（调用方退化为无钩子）。"""
        with patch("src.python.core.provider_registry.get_registry", side_effect=RuntimeError("registry down")):
            assert get_strategy_hook("price_stock", "chain_price") is None


class TestRateLimiterConfigFault:
    """限速配置读取失败 → 空配置限速器。"""

    def test_config_failure_yields_empty_rate_limiter(self):
        """配置抛异常 → 仍返回可用 RateLimiter（空配置）。"""
        with patch("src.python.config.get_config", side_effect=RuntimeError("config broken")):
            limiter = _build_rate_limiter_from_config()

        assert hasattr(limiter, "acquire")
