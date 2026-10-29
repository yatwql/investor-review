"""缓存文件 IO（序列化/反序列化/原子写入）单元测试。"""

from __future__ import annotations

import gzip
import logging
import json
import os
import tempfile

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestCacheIo:
    """缓存文件 IO 测试。"""

    def test_read_cache_data_not_exists(self):
        """文件不存在 → 返回 None。"""
        from src.python.cache._io import _read_cache_data

        result = _read_cache_data("/tmp/nonexistent_cache_file.json", "test_key")
        assert result is None

    def test_read_cache_data_corrupt_then_delete(self, tmp_path):
        """文件损坏 → 自动删除并返回 None。"""
        from src.python.cache._io import _read_cache_data

        corrupt_file = os.path.join(tmp_path, "corrupt.json")
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("这不是 JSON{")
        result = _read_cache_data(corrupt_file, "corrupt_key")
        assert result is None
        assert not os.path.exists(corrupt_file)

    def test_read_cache_data_dry_keep_corrupt(self, tmp_path):
        """dry_run=True → 不删除损坏文件。"""
        from src.python.cache._io import _read_cache_data

        corrupt_file = os.path.join(tmp_path, "corrupt_dry.json")
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        result = _read_cache_data(corrupt_file, "corrupt_dry", dry_run=True)
        assert result is None
        assert os.path.exists(corrupt_file)

    def test_write_atomic_json(self, tmp_path):
        """写入纯 JSON → 文件内容正确。"""
        from src.python.cache._io import _write_atomic

        final_path = os.path.join(tmp_path, "test.json")
        fd, tmp_file = tempfile.mkstemp(dir=tmp_path, suffix=".json.tmp")
        data = {"key": "value", "num": 42}
        json_str = json.dumps(data, ensure_ascii=False)
        raw_bytes = json_str.encode("utf-8")

        _write_atomic(fd, tmp_file, final_path, final_path, json_str, raw_bytes, use_gzip=False)

        assert os.path.exists(final_path)
        with open(final_path, encoding="utf-8") as f:
            assert json.load(f) == data

    def test_write_atomic_gzip(self, tmp_path):
        """写入 gzip 压缩 JSON → 可正常解压读取。"""
        from src.python.cache._io import _write_atomic

        final_path = os.path.join(tmp_path, "test.json.gz")
        fd, tmp_file = tempfile.mkstemp(dir=tmp_path, suffix=".json.gz.tmp")
        data = {"key": "gzip_test"}
        json_str = json.dumps(data, ensure_ascii=False)
        raw_bytes = json_str.encode("utf-8")

        # path 参数是原始缓存路径（用于清理另一格式文件），不应等于 final_path
        plain_path = os.path.join(tmp_path, "test.json")
        _write_atomic(fd, tmp_file, final_path, plain_path, json_str, raw_bytes, use_gzip=True)

        assert os.path.exists(final_path)
        with open(final_path, "rb") as f:
            decompressed = gzip.decompress(f.read()).decode("utf-8")
            assert json.loads(decompressed) == data


class TestCacheDebugOnce:
    """命中/写入的 DEBUG 追踪按 key 每进程首见一次（防日志被同一 key 刷屏）。"""

    def test_repeated_hit_logs_once(self, tmp_path, monkeypatch, caplog):
        from src.python.cache import _store

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.reset_debug_log_state()
        _store.set("k1", {"v": 1})
        with caplog.at_level(logging.DEBUG, logger="invest"):
            _store.get("k1", 60)
            _store.get("k1", 60)
            _store.get("k1", 60)
        hits = [r for r in caplog.records if r.getMessage().startswith("缓存命中: k1")]
        assert len(hits) == 1

    def test_distinct_keys_each_logged(self, tmp_path, monkeypatch, caplog):
        from src.python.cache import _store

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.reset_debug_log_state()
        _store.set("k2", 1)
        _store.set("k3", 2)
        with caplog.at_level(logging.DEBUG, logger="invest"):
            _store.get("k2", 60)
            _store.get("k3", 60)
        keys = {r.args[0] for r in caplog.records if r.getMessage().startswith("缓存命中")}
        assert keys == {"k2", "k3"}


class TestCacheMissVisibility:
    """未命中的两种原因在 **INFO** 级别可区分（无此文件 / 已过期）。

    为何必须是 INFO：默认日志级别下用户只能看到「又调了一遍 LLM」，无法判断是
    缓存被清、TTL 到期，还是自己选了「重新生成」——现场排查靠猜。
    """

    def test_missing_file_logged_once_at_debug(self, tmp_path, monkeypatch, caplog):
        """逐键未命中只到 DEBUG（每进程每 key 一条），INFO 交给收尾汇总行。"""
        from src.python.cache import _store

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.reset_debug_log_state()
        with caplog.at_level(logging.DEBUG, logger="invest"):
            _store.get("absent", 60)
            _store.get("absent", 60)
        hits = [r for r in caplog.records if r.getMessage().startswith("缓存未命中（无此缓存文件）")]
        assert len(hits) == 1  # 每进程每 key 首见一次
        assert hits[0].levelno == logging.DEBUG
        assert hits[0].args[0] == "absent"

    def test_missing_file_not_logged_at_info(self, tmp_path, monkeypatch, caplog):
        """INFO 通道不再逐键刷屏（真实运行里曾占日志 10%~30%）。"""
        from src.python.cache import _store

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.reset_debug_log_state()
        with caplog.at_level(logging.INFO, logger="invest"):
            _store.get("absent-info", 60)
        assert not [r for r in caplog.records if r.getMessage().startswith("缓存未命中")]

    def test_expired_logged_at_debug_with_age_and_ttl(self, tmp_path, monkeypatch, caplog):
        from src.python.cache import _store

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.reset_debug_log_state()
        _store.set("stale", {"v": 1})
        with caplog.at_level(logging.DEBUG, logger="invest"):
            assert _store.get("stale", max_age_seconds=0) is None
        hits = [r for r in caplog.records if r.getMessage().startswith("缓存已过期")]
        assert len(hits) == 1
        assert hits[0].levelno == logging.DEBUG
        assert hits[0].args[0] == "stale"
