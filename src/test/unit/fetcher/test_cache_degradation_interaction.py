"""缓存与链路降级/熔断的组合行为 —— 断源时读旧还是返空、失败不得污染缓存。

业务背景：数据源会抖（超时/断连/限流）。此时缓存承担两种截然不同的角色：

- **快照类数据**（行情、指数、行业分类）：全链路失败时用**过期缓存兜底**
  （宁可给旧值也不给空），否则报告整段缺数据；
- **历史序列**：全链路失败时**不用过期缓存**（走势数据降级后显示占位文本），
  避免把陈旧曲线当最新走势。

同时有两条**不得越过**的红线：

1. **失败结果不得写进缓存**：瞬时网络错误若被缓存成"空结果"，会污染整个 TTL 窗口；
2. **熔断中的源不得被反复尝试**：已熔断的 provider 直接跳过，命中降级分支。
"""

from __future__ import annotations

import pytest

from src.python.core.constants import CACHE_WEEKLY

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


@pytest.fixture()
def chain_env(monkeypatch):
    """把 chain 的 provider 表与链定义替换成测试用桩，避免真实网络与真实链配置。"""
    from src.python.fetcher import chain as chain_mod

    monkeypatch.setattr(chain_mod, "_get_chain", lambda data_type: ["p1", "p2"])
    monkeypatch.setattr(chain_mod, "missing_credential", lambda provider: None)
    monkeypatch.setattr(chain_mod, "_mark_provider_used", lambda *a, **k: None)
    return chain_mod


class _Registry:
    """最小的断路器替身：可控 broken 集合与失败记录。"""

    def __init__(self, broken: set[str] | None = None):
        self.broken = set(broken or ())
        self.failures: list[tuple[str, str]] = []
        self.successes: list[str] = []

    def is_circuit_broken(self, provider: str) -> bool:
        return provider in self.broken

    def record_success(self, provider: str) -> None:
        self.successes.append(provider)

    def record_failure(self, provider: str, context: str) -> None:
        self.failures.append((provider, context))


def _call(chain_mod, cache_key, providers, *, cache_ttl=60, cache_validate=None):
    return chain_mod.fetch_with_fallback(
        "price",
        providers,
        cache_key,
        cache_ttl,
        cache_validate=cache_validate,
    )


class TestDegradedReadUsesStaleCache:
    """全链路失败：快照类数据用过期缓存兜底（报告不缺段）。"""

    def test_all_providers_fail_returns_stale_cache(self, cache_env, chain_env, monkeypatch):
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"price": 1600.0})
        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry())
        providers = {"p1": ("源1", lambda **kw: None), "p2": ("源2", lambda **kw: None)}
        # 缓存 TTL 设为 0 → 正常读未命中，走降级分支拿过期缓存
        assert _call(chain_env, "price_600519", providers, cache_ttl=0) == {"price": 1600.0}

    def test_no_stale_cache_returns_none(self, cache_env, chain_env, monkeypatch):
        """无过期缓存可用 → 返回 None（调用方按数据缺失展示占位）。"""
        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry())
        providers = {"p1": ("源1", lambda **kw: None), "p2": ("源2", lambda **kw: None)}
        assert _call(chain_env, "price_600519", providers, cache_ttl=0) is None

    def test_stale_cache_rejected_by_shape_validation(self, cache_env, chain_env, monkeypatch):
        """过期缓存也必须过形状判据：畸形载荷不得兜底进展示层。"""
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"bad": True})
        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry())
        providers = {"p1": ("源1", lambda **kw: None), "p2": ("源2", lambda **kw: None)}
        assert _call(chain_env, "price_600519", providers, cache_ttl=0, cache_validate=lambda d: "price" in d) is None


class TestFailureDoesNotPolluteCache:
    """失败不得写缓存（瞬时错误被缓存会污染整个 TTL 窗口）。"""

    def test_transport_failure_does_not_write_cache(self, cache_env, chain_env, monkeypatch):
        from src.python.cache import get as cache_get

        def _boom(**kwargs):
            raise TimeoutError("connect timeout")

        registry = _Registry()
        monkeypatch.setattr(chain_env, "get_registry", lambda: registry)
        providers = {"p1": ("源1", _boom), "p2": ("源2", lambda **kw: None)}
        assert _call(chain_env, "price_600519", providers, cache_ttl=60) is None
        assert cache_get("price_600519", CACHE_WEEKLY) is None, "失败结果不得落盘"
        assert registry.failures, "传输级失败应计入熔断计数器"

    def test_code_level_empty_not_counted_as_failure(self, cache_env, chain_env, monkeypatch):
        """代码级空结果（API 不识别该代码）不计入熔断：同请求同答案，重试无意义。"""
        registry = _Registry()
        monkeypatch.setattr(chain_env, "get_registry", lambda: registry)
        providers = {"p1": ("源1", lambda **kw: None), "p2": ("源2", lambda **kw: None)}
        assert _call(chain_env, "price_999999999", providers, cache_ttl=60) is None
        assert registry.failures == [], "预期缺失不应拖垮可用性统计"

    def test_successful_fetch_is_cached_and_reused(self, cache_env, chain_env, monkeypatch):
        from src.python.cache import get as cache_get

        calls: list[int] = []

        def _fetch(**kwargs):
            calls.append(1)
            return {"price": 1610.0}

        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry())
        providers = {"p1": ("源1", _fetch)}
        assert _call(chain_env, "price_600519", providers) == {"price": 1610.0}
        assert _call(chain_env, "price_600519", providers) == {"price": 1610.0}
        assert len(calls) == 1, "第二次应命中缓存，不再打上游"
        assert cache_get("price_600519", 60) == {"price": 1610.0}


class TestCircuitBrokenSkipsProvider:
    """熔断中的源直接跳过：不再消耗请求，直接进入下一槽或降级。"""

    def test_broken_provider_not_called(self, cache_env, chain_env, monkeypatch):
        called: list[str] = []

        def _p1(**kwargs):
            called.append("p1")
            return {"price": 1.0}

        def _p2(**kwargs):
            called.append("p2")
            return {"price": 2.0}

        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry(broken={"p1"}))
        providers = {"p1": ("源1", _p1), "p2": ("源2", _p2)}
        assert _call(chain_env, "price_600519", providers) == {"price": 2.0}
        assert called == ["p2"], "熔断中的源不得被调用"

    def test_all_broken_falls_back_to_stale(self, cache_env, chain_env, monkeypatch):
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"price": 1550.0})
        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry(broken={"p1", "p2"}))
        providers = {"p1": ("源1", lambda **kw: {"price": 1.0}), "p2": ("源2", lambda **kw: None)}
        assert _call(chain_env, "price_600519", providers, cache_ttl=0) == {"price": 1550.0}


class TestOverrideInvalidation:
    """缓存载荷形状不合：主动丢弃重取（不把畸形数据留在盘上）。"""

    def test_malformed_cached_payload_is_cleared_and_refetched(self, cache_env, chain_env, monkeypatch):
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"truncated": True})
        monkeypatch.setattr(chain_env, "get_registry", lambda: _Registry())
        providers = {"p1": ("源1", lambda **kw: {"price": 1620.0})}
        result = _call(chain_env, "price_600519", providers, cache_validate=lambda d: "price" in d)
        assert result == {"price": 1620.0}
        assert cache_get("price_600519", 60) == {"price": 1620.0}, "重取后应写入正确载荷"


class TestHistoryDoesNotDegrade:
    """历史序列：全链路失败**不使用过期缓存**（走势降级显示占位，不显示陈旧曲线）。

    契约差异（与快照类相反）：`fetch_with_incremental_fallback` 全链路失败返回空列表，
    即使盘上有过期缓存也不兜底——陈旧曲线会被读成"最新走势"，比缺数据更糟。
    """

    def test_history_failure_within_ttl_returns_cached_series(self, cache_env, monkeypatch):
        """**TTL 内**已有缓存 + 本次链路失败 → 返回缓存序列（有效数据不因抖动丢弃）。"""
        from src.python.cache import set as cache_set
        from src.python.fetcher import chain_incremental as inc

        cache_set("history_history_stock_600519", [{"date": "2026-10-01", "close": 1600.0}])
        monkeypatch.setattr(inc, "_get_chain", lambda chain_name: ["p1"])
        monkeypatch.setattr(inc, "get_registry", lambda: _Registry())
        monkeypatch.setattr(inc, "_try_providers", lambda *a, **k: [])
        inc.reset_run_history_state()
        result = inc.fetch_with_incremental_fallback("history_stock", "600519", 30)
        assert result == [{"date": "2026-10-01", "close": 1600.0}]

    def test_history_expired_cache_is_not_degraded_back(self, cache_env, monkeypatch):
        """**超过 CACHE_WEEKLY** 的旧缓存 + 本次链路失败 → 不下沉兜底（不把陈年曲线当最新）。"""
        import json
        import time

        from src.python.cache._paths import _CACHE_KEY_VERSION
        from src.python.fetcher import chain_incremental as inc

        payload = {"_ts": time.time() - (CACHE_WEEKLY + 3600), "_data": [{"date": "2026-01-01", "close": 1500.0}]}
        (cache_env / f"history_history_stock_600519_{_CACHE_KEY_VERSION}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        monkeypatch.setattr(inc, "_get_chain", lambda chain_name: ["p1"])
        monkeypatch.setattr(inc, "get_registry", lambda: _Registry())
        monkeypatch.setattr(inc, "_try_providers", lambda *a, **k: [])
        inc.reset_run_history_state()
        assert inc.fetch_with_incremental_fallback("history_stock", "600519", 30) == []

    def test_history_failure_without_cache_returns_empty(self, cache_env, monkeypatch):
        from src.python.fetcher import chain_incremental as inc

        monkeypatch.setattr(inc, "_get_chain", lambda chain_name: ["p1"])
        monkeypatch.setattr(inc, "get_registry", lambda: _Registry())
        monkeypatch.setattr(inc, "_try_providers", lambda *a, **k: [])
        inc.reset_run_history_state()
        assert inc.fetch_with_incremental_fallback("history_stock", "600519", 30) == []

    def test_history_success_is_cached_and_reused_in_same_run(self, cache_env, monkeypatch):
        """成功取数写缓存，且同轮更大窗口复用不重复打源（性能契约）。"""
        from src.python.fetcher import chain_incremental as inc

        calls: list[int] = []

        def _providers(*args, **kwargs):
            calls.append(1)
            return [{"date": f"2026-09-{d:02d}", "close": 1600.0} for d in range(1, 31)]

        monkeypatch.setattr(inc, "_get_chain", lambda chain_name: ["p1"])
        monkeypatch.setattr(inc, "get_registry", lambda: _Registry())
        monkeypatch.setattr(inc, "_try_providers", _providers)
        inc.reset_run_history_state()
        first = inc.fetch_with_incremental_fallback("history_stock", "600519", 20)
        second = inc.fetch_with_incremental_fallback("history_stock", "600519", 10)
        assert len(first) >= 20 and len(second) == 10
        assert len(calls) == 1, "同轮更小窗口应直接截尾复用，不再打源"
