"""缓存清理与统计单元测试 — _cleanup / _stats / _groups 子模块。

测试目标：
  - cleanup_expired — 过期清理、损坏清理、dry_run
  - get_cache_stats — 文件计数/大小/前缀分组
  - clear_by_group — 按组清除缓存
  - get_cache_age — 缓存文件年龄查询

运行：
  pytest src/test/unit/core/test_cache_cleanup.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

# ═══════════════════════════════════════════════════════════
#  基类：统一的临时目录 + 补丁
# ═══════════════════════════════════════════════════════════


class CacheTestBase(unittest.TestCase):
    """所有缓存测试的基类。在 setUp 中创建临时目录并替换 _CACHE_DIR。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.cache_dir = self._tmpdir.name
        self._patcher_paths = patch("src.python.cache._paths._CACHE_DIR", self.cache_dir)
        self._patcher_stats = patch("src.python.cache._stats._CACHE_DIR", self.cache_dir)
        self._patcher_cleanup = patch("src.python.cache._cleanup._CACHE_DIR", self.cache_dir)
        self._patcher_groups = patch("src.python.cache._groups._CACHE_DIR", self.cache_dir)
        self._patcher_paths.start()
        self._patcher_stats.start()
        self._patcher_cleanup.start()
        self._patcher_groups.start()

    def tearDown(self):
        self._patcher_groups.stop()
        self._patcher_cleanup.stop()
        self._patcher_stats.stop()
        self._patcher_paths.stop()
        self._tmpdir.cleanup()

    def _write_cache(self, key: str, data: object, ts: float) -> str:
        """向缓存目录写入指定内容的 JSON 文件，返回完整路径。"""
        from src.python.cache._paths import _cache_path

        path = _cache_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_ts": ts, "_data": data}, f, ensure_ascii=False)
        return path

    def _write_gz_cache(self, key: str, data: object, ts: float) -> str:
        """向缓存目录写入 gzip 压缩的 JSON 文件，返回完整路径。"""
        import gzip

        from src.python.cache._paths import _cache_path

        path = _cache_path(key) + ".gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump({"_ts": ts, "_data": data}, f, ensure_ascii=False)
        return path


# ═══════════════════════════════════════════════════════════
#  get_cache_stats 测试
# ═══════════════════════════════════════════════════════════


class TestCacheGetStats(CacheTestBase):
    """测试 get_cache_stats 的统计功能。"""

    def test_empty_dir(self):
        """空目录 → 全零统计。"""
        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["total_files"], 0)
        self.assertEqual(stats["total_size_bytes"], 0)
        self.assertEqual(stats["by_prefix"], {})

    def test_missing_dir(self):
        """目录不存在 → 全零统计。"""
        import shutil

        shutil.rmtree(self.cache_dir)
        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["total_files"], 0)

    def test_files_counted(self):
        """多个缓存文件 → 正确计数。"""
        self._write_cache("price_a", 1, 100.0)
        self._write_cache("price_b", 2, 100.0)
        self._write_cache("index_c", 3, 100.0)

        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["total_files"], 3)

    def test_files_size_summed(self):
        """文件大小累加正确。"""
        self._write_cache("small", "x", 100.0)
        path = os.path.join(self.cache_dir, "big.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_ts": 100.0, "_data": "x" * 1000}, f)

        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertGreater(stats["total_size_bytes"], 0)

    def test_prefix_grouping(self):
        """文件名前缀分组正确。"""
        self._write_cache("price_a", 1, 100.0)
        self._write_cache("price_b", 2, 100.0)
        self._write_cache("index_a", 3, 100.0)
        self._write_cache("other", 4, 100.0)

        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["by_prefix"]["price"], 2)
        self.assertEqual(stats["by_prefix"]["index"], 1)
        self.assertIn("other", stats["by_prefix"])

    def test_non_json_ignored(self):
        """非 .json 文件不被计入统计。"""
        self._write_cache("mykey", 1, 100.0)
        path = os.path.join(self.cache_dir, "readme.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not cache")

        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["total_files"], 1)

    def test_no_underscore_goes_to_other(self):
        """文件名不含下划线 → 归入 other 分组。"""
        # _cache_path 生成的键名带 _v3 后缀（必然含下划线），
        # 这里手动写入无下划线文件以覆盖分组逻辑的 other 兜底分支。
        path = os.path.join(self.cache_dir, "plain.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_ts": 100.0, "_data": 1}, f, ensure_ascii=False)

        from src.python.cache import get_cache_stats

        stats = get_cache_stats()
        self.assertEqual(stats["by_prefix"].get("other"), 1)


# ═══════════════════════════════════════════════════════════
#  cleanup_expired 测试
# ═══════════════════════════════════════════════════════════


class TestCleanupExpired(CacheTestBase):
    """测试 cleanup_expired 的全部分支。"""

    def _set_time_and_write(self, key: str, data: object, ts: float):
        """写入缓存并返回路径。"""
        return self._write_cache(key, data, ts)

    def _read_ts_file(self, key: str) -> float:
        from src.python.cache._paths import _cache_path

        path = _cache_path(key)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("_ts", 0)

    @patch("src.python.cache._cleanup.time.time")
    def test_empty_dir_returns_zero(self, mock_time):
        """空目录 → 返回 0。"""
        mock_time.return_value = 1000.0
        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 0)

    @patch("src.python.cache._cleanup.time.time")
    def test_missing_dir_returns_zero(self, mock_time):
        """目录不存在 → 返回 0。"""
        import shutil

        shutil.rmtree(self.cache_dir)
        mock_time.return_value = 1000.0
        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 0)

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_expired_files_deleted(self, mock_ttl, mock_time):
        """过期的缓存文件被删除。"""
        mock_time.return_value = 10000.0
        mock_ttl.return_value = 100.0

        self._set_time_and_write("price_old", 1, ts=9500.0)
        self._set_time_and_write("price_fresh", 2, ts=9950.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 1)

        from src.python.cache._paths import _cache_path

        old_path = _cache_path("price_old")
        fresh_path = _cache_path("price_fresh")
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(fresh_path))

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_dry_run_does_not_delete(self, mock_ttl, mock_time):
        """dry_run=True 时文件不被删除，但计数正确。"""
        mock_time.return_value = 10000.0
        mock_ttl.return_value = 100.0

        self._set_time_and_write("price_old", 1, ts=9500.0)
        self._set_time_and_write("price_keep", 2, ts=9950.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired(dry_run=True)
        self.assertEqual(count, 1)
        from src.python.cache._paths import _cache_path

        old_path = _cache_path("price_old")
        self.assertTrue(os.path.exists(old_path))

    @patch("src.python.cache._cleanup.time.time")
    def test_corrupted_file_deleted_in_cleanup(self, mock_time):
        """损坏的文件在 cleanup 中被删除。"""
        mock_time.return_value = 1000.0
        path = os.path.join(self.cache_dir, "broken.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{{broken")

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 1)
        self.assertFalse(os.path.exists(path))

    @patch("src.python.cache._cleanup.time.time")
    def test_corrupted_file_dry_run(self, mock_time):
        """损坏的文件在 dry_run 时只计数不删除。"""
        mock_time.return_value = 1000.0
        path = os.path.join(self.cache_dir, "broken.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{{broken")

        from src.python.cache import cleanup_expired

        count = cleanup_expired(dry_run=True)
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(path))

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_non_json_ignored(self, mock_ttl, mock_time):
        """非 .json 文件被忽略。"""
        mock_time.return_value = 1000.0
        mock_ttl.return_value = 100.0

        path = os.path.join(self.cache_dir, "notes.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not cache")

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 0)
        self.assertTrue(os.path.exists(path))

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_multiple_prefixes_use_different_ttl(self, mock_ttl, mock_time):
        """不同前缀使用对应 TTL 判断过期。"""
        mock_time.return_value = 10000.0

        def ttl_side_effect(dtype: str, key: str | None = None) -> float:
            # 清理侧与读侧同源取 TTL（key 参数保留兼容，不参与计算）
            mapping = {"price": 100.0, "news": 500.0}
            return mapping.get(dtype, 300.0)

        mock_ttl.side_effect = ttl_side_effect

        self._set_time_and_write("price_old", 1, ts=9800.0)
        self._set_time_and_write("news_old", 2, ts=9800.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 1)
        from src.python.cache._paths import _cache_path

        self.assertFalse(os.path.exists(_cache_path("price_old")))
        self.assertTrue(os.path.exists(_cache_path("news_old")))

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_cleanup_os_error_removal_skipped(self, mock_ttl, mock_time):
        """删除文件时 OSError 被吞掉。"""
        mock_time.return_value = 10000.0
        mock_ttl.return_value = 1.0

        self._set_time_and_write("price_x", 1, ts=100.0)

        from src.python.cache import cleanup_expired as real_clean

        with patch("src.python.cache._cleanup.os.remove") as mock_remove:
            mock_remove.side_effect = OSError("permission denied")
            count = real_clean()
            self.assertEqual(count, 0)

    @patch("src.python.cache._cleanup.time.time")
    def test_unknown_prefix_uses_default_ttl(self, mock_time):
        """未知前缀的缓存文件按默认 TTL 判断过期。"""
        mock_time.return_value = 10000.0
        self._set_time_and_write("unknown_xyz", 1, ts=9500.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 0)

    @patch("src.python.cache._cleanup.time.time")
    def test_trading_calendar_not_cleaned_early(self, mock_time):
        """交易日历注册了 exact key → 使用 calendar TTL。"""
        mock_time.return_value = 10000.0
        self._set_time_and_write("trading_calendar", ["2026-01-01"], ts=8000.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 0)
        from src.python.cache._paths import _cache_path

        path = _cache_path("trading_calendar")
        self.assertTrue(os.path.exists(path))

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_sorted_file_processing(self, mock_ttl, mock_time):
        """文件按名称排序处理，不报错。"""
        mock_time.return_value = 10000.0
        mock_ttl.return_value = 1.0

        self._set_time_and_write("a_file", 1, ts=100.0)
        self._set_time_and_write("b_file", 2, ts=100.0)
        self._set_time_and_write("c_file", 3, ts=100.0)

        from src.python.cache import cleanup_expired

        count = cleanup_expired()
        self.assertEqual(count, 3)


# ═══════════════════════════════════════════════════════════
#  生成入口自动清理包装（尽力而为）测试
# ═══════════════════════════════════════════════════════════


class TestAutoCleanupBestEffort(CacheTestBase):
    """auto_cleanup_expired：正常委托 cleanup_expired + 异常吞掉不影响调用方。"""

    def test_auto_cleanup_delegates_to_cleanup_expired(self):
        """正常路径委托 cleanup_expired(dry_run=False) 并透传删除数。"""
        with patch("src.python.cache._cleanup.cleanup_expired", return_value=3) as m:
            from src.python.cache import auto_cleanup_expired

            self.assertEqual(auto_cleanup_expired(), 3)
            m.assert_called_once_with(dry_run=False)

    def test_auto_cleanup_swallows_exception(self):
        """清理抛任何异常时返回 0 且不上抛（主流程绝不因清理失败中断）。"""
        with patch("src.python.cache._cleanup.cleanup_expired", side_effect=OSError("磁盘错误")):
            from src.python.cache import auto_cleanup_expired

            self.assertEqual(auto_cleanup_expired(), 0)


# ═══════════════════════════════════════════════════════════
#  clear_by_group 测试
# ═══════════════════════════════════════════════════════════


class TestClearByGroup(CacheTestBase):
    """测试 clear_by_group 函数。"""

    def test_clear_refresh_group_deletes_matching(self):
        """refresh 组清除基金/新闻/行业/分红/盈利预测缓存，保留 preload 组。"""
        self._write_cache("fund_perf_000001", {"d": 1}, ts=1000.0)
        self._write_cache("news_abc", {"d": 2}, ts=1000.0)
        self._write_cache("industry_600000", {"d": 3}, ts=1000.0)
        self._write_cache("dividend_600000", {"d": 4}, ts=1000.0)
        self._write_cache("price_600000", {"d": 5}, ts=1000.0)

        from src.python.cache import clear_by_group

        result = clear_by_group("refresh")

        from src.python.cache._paths import _cache_path

        for key in ("fund_perf_000001", "news_abc", "industry_600000", "dividend_600000"):
            self.assertFalse(os.path.exists(_cache_path(key)))
        self.assertTrue(os.path.exists(_cache_path("price_600000")))
        self.assertIn("基金业绩排名", result)

    def test_clear_preload_group(self):
        """preload 组清除价格/指数/LLM 缓存，保留 refresh 组。"""
        self._write_cache("price_000001", {"d": 1}, ts=1000.0)
        self._write_cache("index_sh000001", {"d": 2}, ts=1000.0)
        self._write_cache("llm_global_macro_abc", {"d": 3}, ts=1000.0)
        self._write_cache("news_abc", {"d": 4}, ts=1000.0)

        from src.python.cache import clear_by_group

        result = clear_by_group("preload")

        from src.python.cache._paths import _cache_path

        for key in ("price_000001", "index_sh000001", "llm_global_macro_abc"):
            self.assertFalse(os.path.exists(_cache_path(key)))
        self.assertTrue(os.path.exists(_cache_path("news_abc")))
        self.assertIn("股票价格", result)

    def test_clear_preload_group_covers_debate_segments(self):
        """preload 组清除辩论三段缓存（缓存专属登记改挂后防回退）。"""
        self._write_cache("llm_debate_pro_abc", {"d": 1}, ts=1000.0)
        self._write_cache("llm_debate_con_abc", {"d": 2}, ts=1000.0)
        self._write_cache("llm_debate_synthesis_abc", {"d": 3}, ts=1000.0)
        self._write_cache("news_abc", {"d": 4}, ts=1000.0)

        from src.python.cache import clear_by_group

        result = clear_by_group("preload")

        from src.python.cache._paths import _cache_path

        for key in ("llm_debate_pro_abc", "llm_debate_con_abc", "llm_debate_synthesis_abc"):
            self.assertFalse(os.path.exists(_cache_path(key)), key)
        self.assertTrue(os.path.exists(_cache_path("news_abc")))
        for label in ("辩论白脸", "辩论黑脸", "辩论综合"):
            self.assertIn(label, result)

    def test_clear_refresh_clears_exact_keys(self):
        """refresh 组也清除 fund_benchmarks 精确键名。"""
        self._write_cache("fund_benchmarks", {"d": 1}, ts=1000.0)
        from src.python.cache import clear_by_group

        result = clear_by_group("refresh")
        from src.python.cache._paths import _cache_path

        self.assertFalse(os.path.exists(_cache_path("fund_benchmarks")))
        self.assertIn("基金业绩基准", result)

    def test_clear_unknown_group(self):
        """未知组名返回空字典。"""
        from src.python.cache import clear_by_group

        self.assertEqual(clear_by_group("nonexistent"), {})

    def test_clear_group_empty_dir(self):
        """空目录不报错。"""
        from src.python.cache import clear_by_group

        self.assertEqual(clear_by_group("refresh"), {})


# ═══════════════════════════════════════════════════════════
#  get_cache_age 测试
# ═══════════════════════════════════════════════════════════


class TestGetCacheAge(CacheTestBase):
    """测试 get_cache_age() 函数。"""

    @patch("src.python.cache._ttl.time.time")
    def test_get_cache_age_fresh(self, mock_time):
        """缓存刚写入 → 年龄 ≈0。"""
        from src.python.cache import set, get_cache_age

        mock_time.return_value = 1000.0
        set("age_test", "data")

        age = get_cache_age("age_test")
        assert age is not None  # 类型收窄（get_cache_age 缺文件时返回 None）
        self.assertAlmostEqual(age, 0, delta=0.1)

    @patch("src.python.cache._ttl.time.time")
    def test_get_cache_age_aged(self, mock_time):
        """写入后快进 → 年龄 = 时间差。"""
        from src.python.cache import set, get_cache_age

        mock_time.return_value = 1000.0
        set("age_test2", "data")

        mock_time.return_value = 2000.0
        age = get_cache_age("age_test2")
        assert age is not None
        self.assertAlmostEqual(age, 1000.0, delta=0.1)

    def test_get_cache_age_missing(self):
        """缓存不存在 → 返回 None。"""
        from src.python.cache import get_cache_age

        self.assertIsNone(get_cache_age("nonexistent_key"))

    def test_get_cache_age_gz(self):
        """gzip 压缩的缓存也正确返回年龄。"""
        ts_now = 10000.0
        self._write_gz_cache("gz_age", "some_data", ts=ts_now)
        from src.python.cache import get_cache_age

        age = get_cache_age("gz_age")
        assert age is not None
        self.assertGreaterEqual(age, 0)


# ═══════════════════════════════════════════════════════════
#  非缓存引擎托管文件 / 日志量级（回归）
# ═══════════════════════════════════════════════════════════


class TestCleanupUnmanagedAndLogNoise(CacheTestBase):
    """无 `_ts` 包封的文件不得按 epoch 虚龄删除；逐文件明细不得刷 INFO。"""

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_file_without_ts_is_skipped_not_deleted(self, mock_ttl, mock_time):
        """脚本自管的性能缓存（裸 JSON，无 `_ts`）不得按虚龄删除。

        判定口径：`_ts` 缺失时不能取 0 当写入时间——实测 `test_coverage_snapshot.json`
        / `test_redundancy_facts.json` 会算出 `age=497959.4h`（57 年），缓存每轮被删、
        优化形同虚设且日志留下荒谬条目。
        """
        mock_time.return_value = 10_000_000.0
        mock_ttl.return_value = 100.0
        path = os.path.join(self.cache_dir, "test_redundancy_facts.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": "x", "files": {}}, f)

        from src.python.cache import cleanup_expired

        assert cleanup_expired() == 0
        assert os.path.exists(path), "无 _ts 的文件不属缓存引擎托管，不得删除"

    @patch("src.python.cache._cleanup.time.time")
    @patch("src.python.cache._cleanup.get_ttl")
    def test_per_file_detail_is_debug_only(self, mock_ttl, mock_time):
        """逐文件明细必须留在 DEBUG；INFO 只允许汇总行（单日 257 行刷屏回归）。"""
        mock_time.return_value = 10000.0
        mock_ttl.return_value = 100.0
        for i in range(3):
            self._write_cache(f"price_old_{i}", i, 9500.0)

        from src.python.cache import cleanup_expired

        with self.assertLogs("invest", level="DEBUG") as logs:
            assert cleanup_expired() == 3
        info_lines = [r.getMessage() for r in logs.records if r.levelname == "INFO"]
        detail_lines = [m for m in info_lines if "price_old_" in m]
        assert detail_lines == [], f"逐文件明细不应出现在 INFO: {detail_lines}"
        assert any("缓存清理完成" in m for m in info_lines), "汇总行应保留在 INFO"

    def test_span_format_uses_small_units(self):
        """TTL 量级自适应：30s 不得印成 `0.0h`（读起来像配置错误）。"""
        from src.python.cache._cleanup import _fmt_span

        assert _fmt_span(30) == "30.0s"
        assert _fmt_span(600) == "10.0min"
        assert _fmt_span(7200) == "2.0h"


# ═══════════════════════════════════════════════════════════
#  未命中前缀聚合 + 收尾汇总行（日志噪声治理）
# ═══════════════════════════════════════════════════════════

pytestmark_summary = [pytest.mark.unit, pytest.mark.unit_core]


class TestCacheMissSummary:
    """逐键未命中只留 DEBUG，INFO 由一行汇总（命中率 + 前缀 Top）承担。

    动机：真实运行里「缓存未命中（无此缓存文件）: <key>」逐键刷屏，占日志
    10%~30%，单条几乎无信息；有价值的是命中率与「哪一类键在反复未命中」。
    """

    pytestmark = pytestmark_summary

    @pytest.fixture(autouse=True)
    def _clean_stats(self):
        from src.python.cache._stats import reset_cache_stats

        reset_cache_stats()
        yield
        reset_cache_stats()

    def test_miss_prefixes_bucket_by_two_segments(self):
        """未命中按「前两段」前缀分桶（report_datasink_index_x → report_datasink）。"""
        from src.python.cache._stats import _record_cache_miss, get_cache_miss_prefixes

        for key in ("report_datasink_index_600900.SS", "report_datasink_sections_4493", "sector_flow_abc"):
            _record_cache_miss(key)
        assert get_cache_miss_prefixes() == {"report_datasink": 2, "sector_flow": 1}

    def test_summary_is_single_info_line_with_prefixes(self, caplog):
        """汇总只打一行 INFO，含命中/未命中数与未命中前缀分布。"""
        import logging

        from src.python.cache._stats import _record_cache_hit, _record_cache_miss, log_cache_summary

        _record_cache_hit()
        _record_cache_miss("report_datasink_sections_1")
        _record_cache_miss("report_datasink_sections_2")
        with caplog.at_level(logging.INFO, logger="invest"):
            log_cache_summary()
        rows = [r for r in caplog.records if r.getMessage().startswith("[cache] 本次命中")]
        assert len(rows) == 1 and rows[0].levelno == logging.INFO
        assert "report_datasink 2" in rows[0].getMessage()

    def test_repeated_prefix_raises_warning(self, caplog):
        """同一前缀未命中 ≥5 次 → 单独一条 WARNING（每轮重取/缓存键失效的信号）。"""
        import logging

        from src.python.cache._stats import _record_cache_miss, log_cache_summary

        for i in range(5):
            _record_cache_miss(f"report_sections_miss_{i}")
        with caplog.at_level(logging.INFO, logger="invest"):
            log_cache_summary()
        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warns) == 1 and "report_sections" in warns[0].getMessage()

    def test_summary_silent_without_samples(self, caplog):
        """无可观测命中/未命中时不打汇总行（避免空噪声）。"""
        import logging

        from src.python.cache._stats import log_cache_summary

        with caplog.at_level(logging.INFO, logger="invest"):
            log_cache_summary()
        assert not [r for r in caplog.records if r.getMessage().startswith("[cache] 本次命中")]


class TestNegativeCacheProbeNotCounted:
    """负缓存探测不计入全局命中率。

    「负缓存里没有这条记录」是**正常预期**（说明该确定性缺失不存在，应照常取数），
    计入未命中会让命中率虚低、未命中前缀分布失真，并误触发「同前缀未命中 ≥N 次」
    告警——实测单次运行虚计 7~13 次（report_symbol_* / report_sections_miss_* 等）。
    """

    pytestmark = pytestmark_summary

    @pytest.fixture(autouse=True)
    def _clean_stats(self):
        from src.python.cache._stats import reset_cache_stats

        reset_cache_stats()
        yield
        reset_cache_stats()

    def test_negative_cache_miss_not_recorded(self, tmp_path, monkeypatch):
        """负缓存 probe 未命中 → 全局未命中计数与前缀分布都不增加。"""
        from src.python.cache import _negative, _store
        from src.python.cache._stats import get_cache_hit_rate, get_cache_miss_prefixes

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        probe = _negative.NegativeCache("测试缺失", "probe_miss_", "report_symbol_miss")
        assert probe.probe("probe_miss_600900.SS") is None
        assert get_cache_hit_rate()["misses"] == 0
        assert get_cache_miss_prefixes() == {}

    def test_negative_cache_hit_not_recorded(self, tmp_path, monkeypatch):
        """负缓存命中同样不进全局统计（它有自己的 hits 计数与报告级汇总）。"""
        from src.python.cache import _negative, _store
        from src.python.cache._stats import get_cache_hit_rate

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        probe = _negative.NegativeCache("测试缺失二", "probe_hit_", "report_symbol_miss")
        probe.mark("probe_hit_1", "确定性缺失")
        assert probe.probe("probe_hit_1") == "确定性缺失"
        assert probe.hits() == 1
        assert get_cache_hit_rate()["hits"] == 0

    def test_normal_get_still_counted(self, tmp_path, monkeypatch):
        """守卫不过度：常规正缓存的未命中仍计入统计。"""
        from src.python.cache import _store
        from src.python.cache._stats import get_cache_hit_rate

        monkeypatch.setattr(_store, "_cache_path", lambda key: str(tmp_path / f"{key}.json"))
        _store.get("normal_missing_key", 60)
        assert get_cache_hit_rate()["misses"] == 1
