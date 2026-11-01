"""指数历史「全链空」负缓存：确定性空 12h / 含传输失败 1h 短退避。

回归场景（2026-11-01 13:10 运行）：事件窗为 `sh000012`（中证全债）取 K 线，
tencent SSL 握手白等 10s、东财/新浪同样 0 条，事件窗装配被拖到 10.6s；此后每轮重复。
"""

from __future__ import annotations

import pytest

from src.python.fetcher import index as idx

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class _FakeRegistry:
    """会话缓存直通空（让测试落到链路而不是会话缓存）。"""

    def session_cache_get(self, domain: str, code: str):
        from src.python.core.provider_registry import NOT_FOUND

        return NOT_FOUND

    def session_cache_set(self, *a, **k) -> None:
        return None


def _patch_base(monkeypatch, chain_fn):
    calls: list[str] = []

    def _wrapped(*a, **k):
        calls.append(a[1] if len(a) > 1 else k.get("code", ""))
        return chain_fn(*a, **k)

    # 函数内 `from src.python.fetcher.chain import ...`：patch 源模块属性
    monkeypatch.setattr("src.python.fetcher.chain.fetch_with_incremental_fallback", _wrapped)
    monkeypatch.setattr(idx, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr("src.python.core.provider_registry.get_registry", lambda: _FakeRegistry())
    return calls


class TestDeterministicEmpty:
    def test_empty_with_no_failure_is_cached_for_12h(self, monkeypatch):
        calls = _patch_base(monkeypatch, lambda *a, **k: [])

        assert idx.fetch_index_history("sh000012", days=365) == []
        assert len(calls) == 1
        assert idx.INDEX_HISTORY_MISS.is_missing(idx.INDEX_HISTORY_MISS.key("history_index:sh000012"))

        assert idx.fetch_index_history("sh000012", days=365) == []
        assert len(calls) == 1, "确定性空应命中负缓存，第二轮不再取数"

    def test_other_codes_not_affected(self, monkeypatch):
        calls = _patch_base(monkeypatch, lambda *a, **k: [])
        idx.fetch_index_history("sh000012", days=365)
        idx.fetch_index_history("sh000300", days=365)
        assert len(calls) == 2, "负缓存按 code 隔离"


class TestTransportFailureBackoff:
    def test_failure_empty_uses_short_backoff(self, monkeypatch):
        def _chain(*a, **k):
            diag = k.get("diagnostics")
            if diag is not None:
                diag.add("Tencent", "ConnectError")
            return []

        calls = _patch_base(monkeypatch, _chain)

        assert idx.fetch_index_history("sh000012", days=365) == []
        assert len(calls) == 1
        backoff_key = idx.INDEX_HISTORY_BACKOFF.key("history_index:sh000012")
        assert idx.INDEX_HISTORY_BACKOFF.is_missing(backoff_key)
        assert not idx.INDEX_HISTORY_MISS.is_missing(idx.INDEX_HISTORY_MISS.key("history_index:sh000012"))

        assert idx.fetch_index_history("sh000012", days=365) == []
        assert len(calls) == 1, "含传输失败的全链空走 1h 短退避，不重复白等"


class TestNonEmptyNotCached:
    def test_data_present_writes_no_negative_marker(self, monkeypatch):
        calls = _patch_base(monkeypatch, lambda *a, **k: [{"date": "2026-09-01", "close": 1.0}])
        bars = idx.fetch_index_history("sh000300", days=365)
        assert bars
        assert not idx.INDEX_HISTORY_MISS.is_missing(idx.INDEX_HISTORY_MISS.key("history_index:sh000300"))
        assert not idx.INDEX_HISTORY_BACKOFF.is_missing(idx.INDEX_HISTORY_BACKOFF.key("history_index:sh000300"))
        assert len(calls) == 1
