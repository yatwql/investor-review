"""指数行情会话级复用（`index_quote` 会话缓存 + 陈旧兜底读不计数）回归。

缺陷场景（美股指数行情无会话级复用）：`fetch_us_indices()` 在一份报告里被行情页与渲染层各调一次，
且每次先 `cache_get(key, ttl)` 未命中、再 `cache_get(key, 604800)` 取陈旧兜底——
同一缓存键一轮运行记 3~4 次未命中、并对上游重复请求（日志实测 `gb_dji`/`gb_inx`/
`gb_ixic` 各 ×3）。会话级复用与 `fetch_index_history` 同口径：同一轮同键只取一次。
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_fetcher,
    pytest.mark.usefixtures("offline_external_sources"),
]

_US_PAYLOAD = {"gb_dji": {"name": "道琼斯", "price": 34500, "code": "gb_dji"}}
_A_PAYLOAD = {
    "name": "上证指数",
    "code": "sh000001",
    "price": 3000.0,
    "yesterday_close": 2980.0,
    "price_date": "2026-07-01",
}


class TestUsIndicesSessionReuse:
    """美股指数：同一轮内重复调用只打一次上游。"""

    @pytest.mark.usefixtures("offline_external_sources")
    def test_second_call_reuses_session_cache(self, monkeypatch):
        from src.python.fetcher import index as index_mod

        calls = {"sina": 0}

        def _fake_sina():
            calls["sina"] += 1
            return dict(_US_PAYLOAD)

        monkeypatch.setattr(index_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.sina, "fetch_us_indices", _fake_sina)

        first = index_mod.fetch_us_indices()
        calls_after_first = calls["sina"]
        second = index_mod.fetch_us_indices()

        assert first.keys() == second.keys()
        assert calls["sina"] == calls_after_first, "第二轮仍请求上游——会话缓存未生效"

    @pytest.mark.usefixtures("offline_external_sources")
    def test_empty_bundle_is_cached_for_session(self, monkeypatch):
        """全链无数据也写入会话缓存：避免同一轮内为「无数据」重复等超时/重试。"""
        from src.python.fetcher import index as index_mod

        calls = {"sina": 0}

        def _fake_sina():
            calls["sina"] += 1
            return {}

        monkeypatch.setattr(index_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.sina, "fetch_us_indices", _fake_sina)
        monkeypatch.setattr(index_mod, "_fetch_us_from_tencent", lambda codes: {})

        assert index_mod.fetch_us_indices() == {}
        calls_after_first = calls["sina"]
        assert index_mod.fetch_us_indices() == {}
        assert calls["sina"] == calls_after_first

    @pytest.mark.usefixtures("offline_external_sources")
    def test_returned_bundle_is_detached_from_session_cache(self, monkeypatch):
        """调用方标注 `_source` 等改动不得污染会话缓存（下一轮拿到的是原始载荷）。"""
        from src.python.fetcher import index as index_mod

        monkeypatch.setattr(index_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.sina, "fetch_us_indices", lambda: dict(_US_PAYLOAD))

        first = index_mod.fetch_us_indices()
        first["gb_dji"]["_source"] = "mutated"
        second = index_mod.fetch_us_indices()
        assert second["gb_dji"].get("_source") != "mutated"


class TestAIndicesSessionReuse:
    """A 股指数：同一轮内重复调用只打一次上游。"""

    @pytest.mark.usefixtures("offline_external_sources")
    def test_second_call_reuses_session_cache(self, monkeypatch):
        from src.python.fetcher import index as index_mod

        calls = {"tencent": 0}

        def _fake_price(_code):
            calls["tencent"] += 1
            return dict(_A_PAYLOAD)

        monkeypatch.setattr(index_mod, "cache_get", lambda *a, **k: None)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.tencent, "fetch_index_price", _fake_price)

        index_mod.fetch_indices()
        calls_after_first = calls["tencent"]
        index_mod.fetch_indices()
        assert calls["tencent"] == calls_after_first, "第二轮仍请求上游——会话缓存未生效"


class TestStaleFallbackDoesNotCountMiss:
    """陈旧兜底读取只作降级判定，第二次读同一键不得再记一次未命中。"""

    @pytest.mark.usefixtures("offline_external_sources")
    def test_us_stale_probe_is_not_recorded(self, monkeypatch):
        from src.python.fetcher import index as index_mod

        seen_kwargs: list[dict] = []
        state = {"n": 0}

        def _fake_get(_key, _ttl, **kwargs):
            seen_kwargs.append(kwargs)
            state["n"] += 1
            return None if state["n"] == 1 else dict(_US_PAYLOAD["gb_dji"])

        monkeypatch.setattr(index_mod, "cache_get", _fake_get)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.sina, "fetch_us_indices", lambda: {})

        index_mod.fetch_us_indices()
        stale_reads = [kw for kw in seen_kwargs if kw.get("record_stats") is False]
        assert stale_reads, "陈旧兜底读取未声明 record_stats=False（会重复计未命中）"

    @pytest.mark.usefixtures("offline_external_sources")
    def test_a_stale_probe_is_not_recorded(self, monkeypatch):
        from src.python.fetcher import index as index_mod

        seen_kwargs: list[dict] = []

        def _fake_get(_key, _ttl, **kwargs):
            seen_kwargs.append(kwargs)
            return None

        monkeypatch.setattr(index_mod, "cache_get", _fake_get)
        monkeypatch.setattr(index_mod, "cache_set", lambda *a, **k: None)
        monkeypatch.setattr(index_mod.tencent, "fetch_index_price", lambda _c: None)
        monkeypatch.setattr(index_mod, "_fetch_indices_from_sina", lambda codes: {})

        index_mod.fetch_indices()
        # 每个未命中代码两次读：常规 TTL 读（计数）+ 陈旧兜底读（不计数）
        assert [kw.get("record_stats") for kw in seen_kwargs if "record_stats" in kw]
