"""缓存引擎行为契约 —— 读/写/压缩/清除/统计/并发/损坏恢复的多角度组合。

TTL 矩阵文件管「多久算过期」，本文件管**引擎本身的行为**：同一份数据在什么条件下
会被命中、被压缩、被清除、被统计，以及异常输入（损坏文件、不可序列化数据、并发写）
时的降级方向。这些是缓存"敏感 + 不能出错"的底层契约。
"""

from __future__ import annotations

import gzip
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.python.cache._paths import _CACHE_KEY_VERSION, _GZIP_THRESHOLD

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _groups, _paths, _stats, _store

    for module in (_paths, _cleanup, _groups, _stats):
        monkeypatch.setattr(module, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    _stats.reset_cache_stats()
    yield tmp_path
    _store.reset_debug_log_state()
    _stats.reset_cache_stats()


def _payload_file(cache_dir, key: str, age_seconds: float, data=None):
    path = cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json"
    path.write_text(
        json.dumps({"_ts": time.time() - age_seconds, "_data": data if data is not None else {"v": 1}}),
        encoding="utf-8",
    )
    return path


class TestRoundTrip:
    """写入 → 读取往返：类型保真、覆盖写、清除、gzip 阈值两侧。"""

    @pytest.mark.parametrize(
        "value",
        [
            {"a": 1},
            [1, 2, 3],
            "纯文本",
            0,
            False,
            None,
            {"嵌套": {"列表": [1, {"x": 2}], "空": {}}},
        ],
        ids=["dict", "list", "str", "zero", "false", "none", "nested"],
    )
    def test_round_trip_preserves_value(self, cache_env, value):
        """任意可 JSON 化数据往返后等值（含 0/False/None 等假值，不能被当"未命中"）。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", value)
        assert cache_get("price_600519", 60) == value

    def test_overwrite_replaces_previous_value(self, cache_env):
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"v": 1})
        cache_set("price_600519", {"v": 2})
        assert cache_get("price_600519", 60) == {"v": 2}

    def test_clear_removes_json_and_gz_variants(self, cache_env):
        """clear 同时清 .json 与 .json.gz（避免压缩切换后残留旧文件）。"""
        from src.python.cache import clear, get as cache_get

        _payload_file(cache_env, "price_600519", 0)
        (cache_env / f"price_600519_{_CACHE_KEY_VERSION}.json.gz").write_bytes(
            gzip.compress(json.dumps({"_ts": time.time(), "_data": {"v": 2}}).encode())
        )
        clear("price_600519")
        assert cache_get("price_600519", 60) is None
        assert not list(cache_env.glob("price_600519*"))

    def test_small_payload_stays_plain_json(self, cache_env):
        from src.python.cache import set as cache_set

        cache_set("news_demo", {"v": "x" * 100})
        names = [p.name for p in cache_env.iterdir()]
        assert any(n.endswith(".json") for n in names)
        assert not any(n.endswith(".json.gz") for n in names)

    def test_large_payload_compressed(self, cache_env):
        """超过 100KB 阈值自动 gzip（大历史序列省盘）。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        big = {"v": "x" * (_GZIP_THRESHOLD + 1024)}
        cache_set("history_stock_600519", big)
        assert (cache_env / f"history_stock_600519_{_CACHE_KEY_VERSION}.json.gz").exists()
        assert cache_get("history_stock_600519", 60) == big

    def test_gz_and_plain_read_interchangeably(self, cache_env):
        """读路径两种格式都认（压缩阈值切换后旧文件仍可读，直到 TTL 过期）。"""
        from src.python.cache import get as cache_get

        (cache_env / f"news_demo_{_CACHE_KEY_VERSION}.json.gz").write_bytes(
            gzip.compress(json.dumps({"_ts": time.time(), "_data": {"from": "gz"}}).encode())
        )
        assert cache_get("news_demo", 60) == {"from": "gz"}


class TestCorruptionRecovery:
    """损坏缓存：视为未命中、可自动恢复，绝不把异常抛给报告链路。"""

    def test_truncated_gzip_is_miss_and_removed(self, cache_env):
        from src.python.cache import get as cache_get

        path = cache_env / f"history_stock_600519_{_CACHE_KEY_VERSION}.json.gz"
        path.write_bytes(gzip.compress(b'{"_ts": 1, "_data": 1}')[:8])  # 截断
        assert cache_get("history_stock_600519", 60) is None
        assert not path.exists(), "损坏文件应被删除以便下次重取"

    @pytest.mark.parametrize(
        "raw",
        [b"{not json", b"\xff\xfe\x00bad-utf8", b"", b"[]", b'{"no_ts": 1, "_data": 1}'],
        ids=["bad-json", "bad-utf8", "empty", "wrong-shape", "missing-ts"],
    )
    def test_malformed_payloads_are_misses(self, cache_env, raw):
        """畸形载荷统一按未命中处理（含缺 _ts：age 视为无穷大）。"""
        from src.python.cache import get as cache_get

        path = cache_env / f"price_600519_{_CACHE_KEY_VERSION}.json"
        path.write_bytes(raw)
        assert cache_get("price_600519", 86400) is None

    def test_non_serializable_data_skips_write_without_raise(self, cache_env):
        """不可序列化数据：写失败但不抛异常（缓存是旁路，不能打断取数）。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"bad": object()})
        assert cache_get("price_600519", 60) is None


class TestStatsAccounting:
    """命中率统计：读到的每一次命中/未命中都要计入（成本可观测的基础）。"""

    def test_hit_and_miss_counted(self, cache_env):
        from src.python.cache import get as cache_get
        from src.python.cache import get_cache_hit_rate, reset_cache_stats
        from src.python.cache import set as cache_set

        reset_cache_stats()
        cache_set("price_600519", {"v": 1})
        cache_get("price_600519", 60)  # 命中
        cache_get("price_missing", 60)  # 无文件
        _payload_file(cache_env, "price_600520", 120)  # 过期
        cache_get("price_600520", 60)
        stats = get_cache_hit_rate()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["rate"] == pytest.approx(1 / 3, abs=1e-4)

    def test_stats_report_prefix_grouping(self, cache_env):
        from src.python.cache import get_cache_stats
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"v": 1})
        cache_set("news_demo", {"v": 1})
        stats = get_cache_stats()
        assert stats["total_files"] == 2
        assert stats["total_size_bytes"] > 0


class TestGroupClear:
    """按组/前缀批量清除：报告级隔离与「刷新基础缓存」的底层手段。"""

    def test_clear_by_prefix_only_hits_matching_keys(self, cache_env):
        from src.python.cache import clear_by_prefix, get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"v": 1})
        cache_set("price_601398", {"v": 1})
        cache_set("news_demo", {"v": 1})
        removed = clear_by_prefix("price_")
        assert removed == 2
        assert cache_get("news_demo", 60) == {"v": 1}

    def test_clear_by_group_uses_registry_groups(self, cache_env):
        """refresh 组：清新闻与情绪，不动 preload 组的价格。"""
        from src.python.cache import clear_by_group, get as cache_get
        from src.python.cache import set as cache_set

        cache_set("news_demo", {"v": 1})
        cache_set("sentiment_dragon_tiger", {"v": 1})
        cache_set("price_600519", {"v": 1})
        clear_by_group("refresh")
        assert cache_get("news_demo", 60) is None
        assert cache_get("sentiment_dragon_tiger", 60) is None
        assert cache_get("price_600519", 60) == {"v": 1}, "preload 组不应被 refresh 清除波及"


class TestConcurrency:
    """并发：多线程读写同一键不产生半写文件或异常（报告内模块并行取数）。"""

    def test_concurrent_writes_leave_readable_payload(self, cache_env):
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        def _write(i: int) -> None:
            cache_set("price_600519", {"writer": i, "pad": "x" * 200})

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(_write, range(32)))
        value = cache_get("price_600519", 60)
        assert isinstance(value, dict) and "writer" in value

    def test_reader_never_sees_partial_json(self, cache_env):
        """写入过程中并发读：只能读到完整旧值或完整新值，不出现 JSON 解析失败。"""
        from src.python.cache import get as cache_get
        from src.python.cache import set as cache_set

        cache_set("price_600519", {"v": 0})
        results: list[int] = []
        stop = threading.Event()

        def _reader() -> None:
            while not stop.is_set():
                value = cache_get("price_600519", 60)
                assert value is not None, "并发写入期间不得出现读到半写文件"
                results.append(value["v"])

        thread = threading.Thread(target=_reader)
        thread.start()
        try:
            for i in range(1, 20):
                cache_set("price_600519", {"v": i})
        finally:
            stop.set()
            thread.join(timeout=5)
        assert results, "读线程应至少读到一次"
