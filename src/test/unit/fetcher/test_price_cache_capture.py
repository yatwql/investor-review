"""价格缓存写入时刻读取：无缓存/读取异常一律 None（新鲜度判定退化为「未知」）。"""

from __future__ import annotations

import pytest

from src.python.fetcher import price

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestCacheCapturedAt:
    def test_missing_cache_returns_none(self):
        """空键与「该键没有缓存文件」都返回 None，不抛异常。"""
        assert price._cache_captured_at("") is None
        assert price._cache_captured_at("price_probe_absent_900001") is None

    def test_read_failure_returns_none(self, monkeypatch):
        """缓存年龄读取抛异常 → None（新鲜度按未知处理，不冒泡）。"""

        def _raise(key):
            raise OSError("stats failed")

        monkeypatch.setattr("src.python.cache.get_cache_age", _raise)
        assert price._cache_captured_at("price_probe_any") is None
