"""负缓存探针原语 — 键族/计数/汇总的单一样板。

判定口径：负缓存只登记**确定性**缺失，TTL 取注册表类型；命中是省请求而非错误，
只做分类计数与一行汇总，不参与降级统计。三类财报负缓存与 provider 侧的 404 探测
负缓存共用本原语，新增一类只需登记实例（见 `cache.negative_cache_entries`）。
"""

from __future__ import annotations

import pytest

from src.python.cache import NegativeCache, negative_cache_entries, nonzero_summaries, reset_all_negative_hits

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    """缓存目录隔离（负缓存走真实 cache 层，不 mock）。"""
    from src.python.cache import _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    return tmp_path


class TestKeyAndStorage:
    def test_key_joins_parts_under_prefix(self, isolated_cache):
        cache = NegativeCache("演示缺失", "demo_miss_", "report_symbol_miss")
        assert cache.key("600900", "_", "full") == "demo_miss_600900_full"

    def test_mark_then_probe_roundtrip(self, isolated_cache):
        cache = NegativeCache("演示缺失", "demo_miss_", "report_symbol_miss")
        key = cache.key("A")
        assert cache.probe(key) is None
        cache.mark(key, "该文档无该章节")
        assert cache.probe(key) == "该文档无该章节"
        assert cache.is_missing(key) is True

    def test_clear_removes_entry(self, isolated_cache):
        cache = NegativeCache("演示缺失", "demo_miss_", "report_symbol_miss")
        key = cache.key("A")
        cache.mark(key)
        cache.clear(key)
        assert cache.is_missing(key) is False

    def test_ttl_comes_from_registry_type(self, isolated_cache, monkeypatch):
        """读侧 TTL 必须取自注册表类型（与清理判定同源），不得自持常量。"""
        from src.python.cache import _negative, get_ttl

        calls: list[str] = []

        def _ttl(data_type: str) -> float:
            calls.append(data_type)
            return 123.0

        monkeypatch.setattr(_negative, "get_ttl", _ttl)
        cache = NegativeCache("演示缺失", "demo_miss_", "report_sections_miss")
        cache.probe(cache.key("A"))
        assert calls == ["report_sections_miss"]
        assert get_ttl("report_sections_miss") > 0


class TestHitCounting:
    def test_hits_count_only_on_positive_probe(self, isolated_cache):
        cache = NegativeCache("演示缺失", "demo_miss_", "report_symbol_miss")
        cache.reset()
        assert cache.hits() == 0
        cache.probe(cache.key("miss"))  # 未命中 → 不计数
        assert cache.hits() == 0
        cache.mark(cache.key("hit"))
        cache.probe(cache.key("hit"))
        cache.probe(cache.key("hit"))
        assert cache.hits() == 2

    def test_registry_lists_instances_and_resets_all(self, isolated_cache):
        a = NegativeCache("甲缺失", "demo_a_", "report_symbol_miss")
        b = NegativeCache("乙缺失", "demo_b_", "report_symbol_miss")
        assert a in negative_cache_entries() and b in negative_cache_entries()
        for entry in (a, b):
            entry.mark(entry.key("x"))
            entry.probe(entry.key("x"))
        reset_all_negative_hits()
        assert a.hits() == 0 and b.hits() == 0

    def test_summaries_only_include_nonzero(self, isolated_cache):
        cache = NegativeCache("丙缺失", "demo_c_", "report_symbol_miss", hit_note="跳过重复请求")
        reset_all_negative_hits()
        assert cache.summary_text() not in nonzero_summaries()
        cache.mark(cache.key("x"))
        cache.probe(cache.key("x"))
        assert "丙缺失命中负缓存 1 次（跳过重复请求）" in nonzero_summaries()
