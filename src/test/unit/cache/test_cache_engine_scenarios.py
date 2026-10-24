"""缓存引擎场景矩阵（`cache/_store` + `cache/_paths` 层，不含 LLM 语义）。

这里只测「缓存基础设施的硬契约」，与 `unit/llm` 下的 LLM 缓存命中契约分工：
- 本文件：TTL 边界、压缩往返、损坏载荷、原子写、键版本升级、目录不可写；
- LLM 侧：指纹/键同源、逐模块精度、强制范围、串行模块等。

归域说明：`unit/cache` 目录按 `scripts/check-test-markers.py` 期望表归 `unit_core`
（缓存基础设施无专属域，搭核心域的 P0 `dev-verify` 车）。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    """缓存目录隔离到 tmp，并复位「每 key 首见一次」的日志去重状态。"""
    from src.python.cache import _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


def _cache_file(cache_dir: Path, key: str) -> Path:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    return cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json"


class TestTTLBoundary:
    def test_fresh_entry_hits(self, cache_env):
        from src.python.cache import set as cache_set
        from src.python.cache import get as cache_get

        cache_set("k_fresh", {"v": 1})
        assert cache_get("k_fresh", 60) == {"v": 1}

    def test_entry_just_expired_misses(self, cache_env):
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("k_boundary", {"v": 1})
        time.sleep(0.01)
        assert cache_get("k_boundary", 0.001) is None

    def test_expired_entry_is_replaced_not_deleted_silently(self, cache_env):
        """过期后重新写入：新值可读，且 `_ts` 已刷新（不是靠删除才可用）。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("k_replace", {"v": 1})
        assert cache_get("k_replace", 0) is None
        cache_set("k_replace", {"v": 2})
        assert cache_get("k_replace", 60) == {"v": 2}


class TestCompressionRoundtrip:
    def test_large_payload_uses_gzip_and_reads_back(self, cache_env):
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set
        from src.python.cache._paths import _GZIP_THRESHOLD

        payload = {"text": "x" * (_GZIP_THRESHOLD + 1024)}
        cache_set("k_big", payload)
        files = list(cache_env.glob("k_big*"))
        assert any(p.name.endswith(".gz") for p in files), files
        assert cache_get("k_big", 60) == payload

    def test_small_payload_stays_plain(self, cache_env):
        from src.python.cache import set as cache_set

        cache_set("k_small", {"v": 1})
        files = [p.name for p in cache_env.glob("k_small*")]
        assert files and not any(n.endswith(".gz") for n in files), files


class TestCorruptionHandling:
    def test_corrupt_json_is_miss_not_crash(self, cache_env):
        from src.python.cache import get as cache_get

        path = _cache_file(cache_env, "k_corrupt")
        path.write_text("{not json", encoding="utf-8")
        assert cache_get("k_corrupt", 3600) is None

    def test_truncated_gzip_is_miss_not_crash(self, cache_env):
        from src.python.cache import get as cache_get

        path = cache_env / "k_truncated_v3.json.gz"
        path.write_bytes(b"\x1f\x8b\x08garbage")
        assert cache_get("k_truncated", 3600) is None

    def test_missing_ts_field_is_treated_as_expired(self, cache_env):
        """无 `_ts` 的载荷按「很久以前」处理（不得被当成刚写入长期复用）。"""
        from src.python.cache import get as cache_get

        path = _cache_file(cache_env, "k_no_ts")
        path.write_text(json.dumps({"_data": {"v": 1}}), encoding="utf-8")
        assert cache_get("k_no_ts", 3600) is None


class TestAtomicity:
    def test_concurrent_writes_keep_file_parseable(self, cache_env):
        """并发写同一 key：最终文件必须始终是完整 JSON（原子替换）。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        def _writer(idx: int) -> None:
            for _ in range(20):
                cache_set("k_race", {"writer": idx, "blob": "y" * 2000})

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        payload = cache_get("k_race", 60)
        assert isinstance(payload, dict), payload
        assert payload["blob"] == "y" * 2000

    def test_no_temp_files_left_behind(self, cache_env):
        """原子写完成后不得残留 `.tmp` 中间文件。"""
        from src.python.cache import set as cache_set

        cache_set("k_tmp", {"v": 1})
        assert [p.name for p in cache_env.glob("*.tmp")] == []


class TestKeyVersioning:
    def test_old_version_file_is_invisible(self, cache_env):
        """键版本号升级后，非当前版本的文件不得被读到（自动失效重建）。"""
        from src.python.cache import get as cache_get

        legacy = cache_env / "k_old_v2.json"
        legacy.write_text(json.dumps({"_ts": time.time(), "_data": {"stale": True}}), encoding="utf-8")
        assert cache_get("k_old", 3600) is None, "旧版本缓存必须不可见"

    def test_current_version_file_is_read(self, cache_env):
        from src.python.cache import get as cache_get

        current = _cache_file(cache_env, "k_now")
        current.write_text(json.dumps({"_ts": time.time(), "_data": {"fresh": True}}), encoding="utf-8")
        assert cache_get("k_now", 3600) == {"fresh": True}


class TestUnwritableDirectory:
    def test_write_failure_does_not_raise(self, cache_env, monkeypatch):
        """目录不可写 → 写入静默失败（只告警），读回落空，不抛异常。"""
        from src.python.cache import _store

        def _raise(*_a, **_k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(_store.tempfile, "mkstemp", _raise)
        _store.set("k_ro", {"v": 1})  # 不得抛异常
        assert _store.get("k_ro", 60) is None

    def test_read_from_missing_dir_returns_none(self, cache_env, monkeypatch):
        from src.python.cache import _paths, _store

        monkeypatch.setattr(_paths, "_CACHE_DIR", str(cache_env / "not-created"))
        assert _store.get("k_absent", 60) is None
