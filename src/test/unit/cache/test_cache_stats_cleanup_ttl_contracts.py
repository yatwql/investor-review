"""缓存命中率统计 / 过期清理 / TTL 查询的计数与边界契约。

统计与清理都是「旁路可观测」层：它们的返回值与播报文案被面板与运行收尾汇总消费，
所以这里断言的是**具体数与具体文案**（计数累加、恰等窗口的保留/回收、单位换算），
而不是「非空/非 None」——弱断言放过了 `count + 1 → - 1`、`age/86400 → *86400`
这类不改形状只改数值的偏差。
"""

from __future__ import annotations

import json
import logging

import pytest

from src.python.cache import _cleanup, _groups, _paths, _stats, _store, _ttl, _cache_refresh
from src.test.unit.cache._cache_fixtures import write_cache, write_cache_at


class _RecordingReporter:
    """最小进度上报替身：只收信息/成功文案，供缓存统计断言用。"""

    def __init__(self):
        self.infos: list[str] = []
        self.oks: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def ok(self, message: str) -> None:
        self.oks.append(message)


pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    """把各子模块的缓存目录都重定向到临时目录（各模块各自持有 `_CACHE_DIR` 引用）。"""
    for module in (_cleanup, _groups, _paths, _stats):
        monkeypatch.setattr(module, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


@pytest.fixture()
def clean_stats():
    _stats.reset_cache_stats()
    yield
    _stats.reset_cache_stats()


class TestProbeKeyAndPrefix:
    def test_probe_key_markers(self):
        """负缓存/纠偏探测键判为「预期缺失」，常规键不判。"""
        assert _stats.is_probe_key("report_symbol_miss_600519") is True
        assert _stats.is_probe_key("holdings_correction_streak") is True
        assert _stats.is_probe_key("price_600519") is False

    def test_key_prefix_joins_first_two_segments(self):
        """前缀取前两段：三段键归并、两段键原样、单段键原样、空键归 other。"""
        assert _stats._key_prefix("llm_global_macro_a1") == "llm_global"
        assert _stats._key_prefix("price_600519") == "price_600519"
        assert _stats._key_prefix("single") == "single"
        assert _stats._key_prefix("") == "other"


class TestMissBucketing:
    def test_empty_and_probe_keys_not_bucketed(self, clean_stats):
        """空键与探测键只计未命中总数，不进前缀分桶。"""
        _stats._record_cache_miss("")
        _stats._record_cache_miss("report_symbol_miss_x")

        assert _stats.get_cache_miss_prefixes() == {}
        assert _stats.get_cache_hit_rate()["misses"] == 2

    def test_prefix_counts_accumulate(self, clean_stats):
        _stats._record_cache_miss("llm_global_a")
        _stats._record_cache_miss("llm_global_b")

        assert _stats.get_cache_miss_prefixes() == {"llm_global": 2}

    def test_miss_key_tracking_is_bounded(self, clean_stats, monkeypatch):
        """同键计数表有界：达到上限后新键不再纳入（上限值可注入以便构造）。"""
        monkeypatch.setattr(_stats, "_MISS_KEY_TRACK_LIMIT", 1)
        _stats._record_cache_miss("llm_a_one")
        _stats._record_cache_miss("llm_b_two")

        assert list(_stats._cache_miss_keys) == ["llm_a_one"]

    def test_stats_hit_rate_zero_when_total_zero(self):
        """采样总数为 0 时不采用 rate：上游即使给了非零 rate，也不得把命中率顶上屏。"""
        from unittest.mock import patch as _patch

        from src.python.cache import operations as _operations

        raw = {"total_files": 0, "total_size_bytes": 0, "by_prefix": {}, "top_by_size": []}
        reporter = _RecordingReporter()
        with (
            _patch("src.python.cache.get_cache_stats", return_value=raw),
            _patch("src.python.cache.get_cache_hit_rate", return_value={"total": 0, "rate": 42.0}),
            _patch("src.python.cache.cleanup_expired", return_value=0),
        ):
            stats = _operations.get_cache_stats(reporter)

        assert stats.hit_rate == 0.0, "total=0 时命中率必须为 0，不得采用无样本的 rate"
        assert stats.hit_total == 0
        assert not any("命中率" in msg for msg in getattr(reporter, "infos", []))

    def test_hit_rate_zero_without_samples(self, clean_stats):
        assert _stats.get_cache_hit_rate() == {"hits": 0, "misses": 0, "total": 0, "rate": 0.0}


class TestLogCacheSummary:
    def test_empty_when_no_samples(self, clean_stats):
        assert _stats.log_cache_summary() == ""

    def test_reports_rate_and_placeholder_prefix(self, clean_stats, caplog):
        """有样本但无可分桶前缀时，返回值是占位「无」，命中率按百分数上屏。"""
        _stats._record_cache_hit()
        _stats._record_cache_miss("report_symbol_miss_x")

        with caplog.at_level(logging.INFO, logger="invest"):
            detail = _stats.log_cache_summary(top=5)

        assert detail == "无"
        assert "命中率 50%" in caplog.text

    def test_same_key_misses_raise_warning(self, clean_stats, caplog):
        """同键未命中恰达阈值（第 3 次）即告警，并给出键名与次数。"""
        for _ in range(3):
            _stats._record_cache_miss("llm_global_macro_a")

        with caplog.at_level(logging.WARNING, logger="invest"):
            _stats.log_cache_summary()

        assert "llm_global_macro_a×3" in caplog.text


class TestDirStats:
    def test_counts_files_and_prefixes(self, cache_env):
        (cache_env / "llm_global_macro_v4.json").write_text("{}", encoding="utf-8")
        (cache_env / "price_600519_v4.json.gz").write_text("xx", encoding="utf-8")
        (cache_env / "notes.txt").write_text("xxx", encoding="utf-8")

        stats = _stats.get_cache_stats()

        assert stats["total_files"] == 2
        assert stats["by_prefix"] == {"llm": 1, "price": 1}

    def test_missing_dir_returns_empty_stats(self, monkeypatch):
        """缓存目录不存在 → 返回空统计（不是 None，调用方直接取键）。"""
        monkeypatch.setattr(_stats, "_CACHE_DIR", "/nonexistent/cache/dir")

        assert _stats.get_cache_stats() == {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_prefix": {},
            "top_by_size": [],
        }

    def test_listdir_failure_returns_empty_stats(self, cache_env, monkeypatch):
        """isdir 与 listdir 之间目录消失（TOCTOU）：按空目录返回，不抛。"""
        monkeypatch.setattr(_stats.os.path, "isdir", lambda path: True)
        monkeypatch.setattr(_stats.os, "listdir", lambda path: (_ for _ in ()).throw(OSError("gone")))

        assert _stats.get_cache_stats() == {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_prefix": {},
            "top_by_size": [],
        }


class TestFormatSpan:
    def test_unit_switch_boundaries(self):
        """<60s 用 s、<60min 用 min、其余 h；恰等边界归入上一档。"""
        assert _cleanup._fmt_span(30) == "30.0s"
        assert _cleanup._fmt_span(-5) == "0.0s"
        assert _cleanup._fmt_span(60) == "1.0min"
        assert _cleanup._fmt_span(120) == "2.0min"
        assert _cleanup._fmt_span(3600) == "1.0h"
        assert _cleanup._fmt_span(7200) == "2.0h"


class TestCleanupExpiredBoundaries:
    def test_age_equal_ttl_is_kept(self, cache_env, monkeypatch):
        """年龄恰等于 TTL → 未过期（判据是 `age <= ttl` 保留）。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_cleanup.time, "time", lambda: now)
        monkeypatch.setattr(_cleanup, "get_cleanup_ttl", lambda data_type, written_at=None: 100.0)
        write_cache_at(cache_env, "price_600519", now - 100.0)

        assert _cleanup.cleanup_expired(dry_run=False) == 0
        assert len(list(cache_env.iterdir())) == 1

    def test_log_reports_released_kb(self, cache_env, monkeypatch, caplog):
        """汇总行按 KB 播报释放量（字节 / 1024）。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_cleanup.time, "time", lambda: now)
        monkeypatch.setattr(_cleanup, "get_cleanup_ttl", lambda data_type, written_at=None: 10.0)
        write_cache_at(cache_env, "price_600519", now - 100.0)
        size = next(cache_env.iterdir()).stat().st_size

        with caplog.at_level(logging.INFO, logger="invest"):
            assert _cleanup.cleanup_expired(dry_run=False) == 1

        assert f"释放 {size / 1024:.1f} KB" in caplog.text


class TestCleanSensitiveBounds:
    def test_days_to_seconds_conversion(self, cache_env, monkeypatch):
        """窗口按 N×86400 秒换算：2 天龄的敏感缓存不入 3 天窗。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_cleanup.time, "time", lambda: now)
        write_cache_at(cache_env, "holding_snapshot", now - 2 * 86400)

        assert _cleanup.clean_sensitive(older_than_days=3, dry_run=False) == 0
        assert len(list(cache_env.iterdir())) == 1

    def test_age_equal_to_window_is_kept(self, cache_env, monkeypatch):
        """年龄恰等于窗口 → 保留（判据是 `age <= older_than_secs` 跳过）。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_cleanup.time, "time", lambda: now)
        write_cache_at(cache_env, "holding_snapshot", now - 3 * 86400)

        assert _cleanup.clean_sensitive(older_than_days=3, dry_run=False) == 0

    def test_log_reports_age_in_days(self, cache_env, monkeypatch, caplog):
        """逐文件明细按天播报年龄（秒 / 86400）。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_cleanup.time, "time", lambda: now)
        write_cache_at(cache_env, "holding_snapshot", now - 2 * 86400)

        with caplog.at_level(logging.INFO, logger="invest"):
            assert _cleanup.clean_sensitive(older_than_days=1, dry_run=False) == 1

        assert "age=2.0d" in caplog.text


class TestCacheAgeQueries:
    def test_get_cache_age_returns_elapsed_seconds(self, cache_env):
        write_cache(cache_env, "price_600519", 100.0)

        age = _ttl.get_cache_age("price_600519")

        assert isinstance(age, float)
        assert age == pytest.approx(100.0, abs=5.0)

    def test_age_by_data_type_uses_registered_prefix(self, cache_env):
        """按数据类型查龄：用注册表前缀拼键，不取其他类型同标识符的缓存。"""
        write_cache(cache_env, "index_sh000001", 50.0)
        write_cache(cache_env, "price_sh000001", 900.0)

        age = _ttl.get_cache_age_by_data_type("index", "sh000001")

        assert age == pytest.approx(50.0, abs=5.0)

    def test_age_by_data_type_requires_identifier(self, cache_env):
        """identifier 为 None 时不拼键查询（不得把 None 当标识符拼进键名）。"""
        write_cache(cache_env, "price_None", 50.0)

        assert _ttl.get_cache_age_by_data_type("price", None) is None


class TestCleanupTtlMarketSensitivity:
    def test_non_market_type_uses_static_ttl_even_intraday(self, monkeypatch):
        """非盘中敏感类型（注册表无 market_ttl）恒按静态 TTL，不看写入时刻。"""
        from src.python.core.registry import get_cache_ttl_defaults

        static = get_cache_ttl_defaults()["rank"]
        monkeypatch.setattr(_ttl, "_is_market_open", lambda: False)
        monkeypatch.setattr("src.python.core.market_hours.is_intraday_timestamp", lambda ts: True)

        assert _ttl.get_cleanup_ttl("rank", written_at=1_700_000_000.0) == static


class TestIntradayTtlOverrideLog:
    @pytest.fixture()
    def market_open_config(self, monkeypatch):
        _ttl._INTRADAY_OVERRIDE_NOTIFIED.clear()
        monkeypatch.setattr(_ttl, "_is_market_open", lambda: True)
        monkeypatch.setattr(
            "src.python.config.get_config",
            lambda: {"cache_ttl": {"price": 3600}, "market_hour_ttl": 30},
        )
        yield
        _ttl._INTRADAY_OVERRIDE_NOTIFIED.clear()

    def test_override_logged_once(self, market_open_config, caplog):
        """盘中 TTL 覆盖 cache_ttl 的提示每类型只打一次（先记后判，不重复刷屏）。"""
        with caplog.at_level(logging.INFO, logger="invest"):
            assert _ttl.get_ttl("price") == 30.0
            assert _ttl.get_ttl("price") == 30.0

        assert caplog.text.count("使用盘中 TTL") == 1


class TestClearByGroupReturnContract:
    def test_exact_key_counted_without_gzip_variant(self, cache_env):
        """精确键只在 .json 存在时也计入清除数（不得因为缺 .gz 变体漏计）。"""
        from src.python.core.registry import get_cache_registry

        # 精确键若被自身前缀覆盖，计数会由前缀路径给出而掩盖精确键分支，故避开这类模块。
        module = next(
            m
            for m in get_cache_registry()
            if m.exact_cache_keys
            and m.cache_groups
            and not any(m.exact_cache_keys[0].startswith(p) for p in m.cache_prefixes)
        )
        exact_key = module.exact_cache_keys[0]
        (cache_env / f"{exact_key}_{_paths._CACHE_KEY_VERSION}.json").write_text(
            json.dumps({"_ts": 1, "_data": {}}), encoding="utf-8"
        )

        result = _groups.clear_by_group(module.cache_groups[0], only=[exact_key])
        assert result == {module.name: 1}

        # 组内键仍在、但磁盘文件已不存在 → 命中 0 条不得产出「模块 0」行
        assert _groups.clear_by_group(module.cache_groups[0], only=[exact_key]) == {}


class TestPathsContract:
    def test_cache_dir_is_absolute(self, cache_env):
        assert _paths.get_cache_dir() == str(cache_env.resolve())
        assert _paths.get_cache_dir().startswith("/")


class TestStoreFreshnessBoundary:
    def test_age_equal_max_age_is_stale(self, cache_env, monkeypatch):
        """年龄恰等于上限 → 仍算新鲜（判据 `age > max_age_seconds`）；超出即过期。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_store.time, "time", lambda: now)
        _store.set("price_600519", {"v": 1})
        monkeypatch.setattr(_store.time, "time", lambda: now + 100.0)

        assert _store.get("price_600519", 100.0) == {"v": 1}
        assert _store.get("price_600519", 99.5) is None

    def test_gzip_threshold_is_strict(self, cache_env, monkeypatch):
        """载荷恰等于 gzip 阈值时不压缩（判据 `len > 阈值`）。"""
        now = 1_700_000_000.0
        monkeypatch.setattr(_store.time, "time", lambda: now)
        threshold = _store._GZIP_THRESHOLD

        def _payload_bytes(width: int) -> int:
            raw = json.dumps({"_ts": now, "_data": "x" * width}, ensure_ascii=False, indent=2)
            return len(raw.encode("utf-8"))

        width = threshold
        while _payload_bytes(width) < threshold:
            width += 1
        while _payload_bytes(width) > threshold:
            width -= 1
        _store.set("edge_payload", "x" * width)

        stem = f"edge_payload_{_paths._CACHE_KEY_VERSION}.json"
        assert (cache_env / stem).exists()
        assert not (cache_env / f"{stem}.gz").exists()


class _Holder:
    def __init__(self, code: str, name: str, account: str = "A") -> None:
        self.code = code
        self.name = name
        self.account = account
        self.shares = 1
        self.cost_price = 1.0


class TestHoldingsTrackingTraces:
    """跟踪基线的两条「预期缺失」痕迹：没上一轮数据时不得报「代码集合无变化」。"""

    @pytest.fixture()
    def tracker(self, monkeypatch):
        from src.python.cache.services import holdings_tracker

        monkeypatch.setattr(holdings_tracker, "compute_holdings_fingerprint", lambda h: "fp-new")
        monkeypatch.setattr(holdings_tracker, "compute_holdings_codes", lambda h: {"600519"})
        monkeypatch.setattr(holdings_tracker, "_clear_holdings_related_caches", lambda: [])
        monkeypatch.setattr(holdings_tracker, "set", lambda key, value: None)
        return holdings_tracker

    def test_known_prev_codes_skips_all_new_note(self, tracker, monkeypatch, caplog):
        monkeypatch.setattr(
            tracker,
            "_read_holdings_tracking",
            lambda key: {"fingerprint": "fp-old", "codes": ["600519"]},
        )

        with caplog.at_level(logging.DEBUG, logger="invest"):
            assert tracker.check_and_refresh_caches([_Holder("600519", "贵州茅台")]) == []

        assert "所有代码将被视为新增" not in caplog.text
        assert "代码集合无变化" in caplog.text

    def test_empty_holdings_skips_no_change_note(self, tracker, monkeypatch, caplog):
        """空持仓（代码集合为空）走「无新增」路径：上一轮无代码时不得报「代码集合无变化」。"""
        monkeypatch.setattr(tracker, "compute_holdings_codes", lambda h: set())
        monkeypatch.setattr(
            tracker,
            "_read_holdings_tracking",
            lambda key: {"fingerprint": "fp-old", "codes": []},
        )

        with caplog.at_level(logging.DEBUG, logger="invest"):
            assert tracker.check_and_refresh_caches([]) == []

        assert "代码集合无变化" not in caplog.text

    def test_empty_prev_codes_skips_no_change_note(self, tracker, monkeypatch, caplog):
        monkeypatch.setattr(
            tracker,
            "_read_holdings_tracking",
            lambda key: {"fingerprint": "fp-old", "codes": []},
        )

        with caplog.at_level(logging.DEBUG, logger="invest"):
            assert tracker.check_and_refresh_caches([_Holder("600519", "贵州茅台")]) == ["600519"]

        assert "所有代码将被视为新增" in caplog.text
        assert "代码集合无变化" not in caplog.text


class TestExtendedCacheRefreshCount:
    def test_no_a_share_returns_zero_count(self):
        """无 A 股标的时返回整数 0（调用方按计数播报，None 会打崩格式化）。"""
        assert _cache_refresh._refresh_extended_cache([]) == 0
