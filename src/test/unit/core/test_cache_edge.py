"""缓存 edge 场景专项测试。

edge 场景：
  - TestGetTTLMarketHourAware: 市场交易时段感知的 TTL 计算
  - TestGzipCacheEdge: gzip 压缩边界（100KB 阈值）+ 损坏文件恢复

运行：
  pytest src/test/unit/core/test_cache_edge.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core, pytest.mark.edge]


# ── 测试基类 ─────────────────────────────────


class _CacheTestBase:
    """测试辅助方法。"""

    def setUp(self):
        self.cache_dir = tempfile.TemporaryDirectory()
        self._p_paths = patch("src.python.cache._paths._CACHE_DIR", self.cache_dir.name)
        self._p_cleanup = patch("src.python.cache._cleanup._CACHE_DIR", self.cache_dir.name)
        self._p_groups = patch("src.python.cache._groups._CACHE_DIR", self.cache_dir.name)
        self._p_paths.start()
        self._p_cleanup.start()
        self._p_groups.start()

    def tearDown(self):
        if hasattr(self, "_p_groups"):
            self._p_groups.stop()
        if hasattr(self, "_p_cleanup"):
            self._p_cleanup.stop()
        self._p_paths.stop()
        self.cache_dir.cleanup()

    def _write_cache(self, key, data, ts=None):
        """写入一个 .json 缓存文件（可选带时间戳）。"""
        from src.python.cache._paths import _cache_path

        path = _cache_path(key)
        payload = {"data": data}
        if ts is not None:
            payload["timestamp"] = ts
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _write_gz_cache(self, key, data, ts=None):
        """写入一个 .json.gz 缓存文件（可选带时间戳）。"""
        import gzip

        from src.python.cache._paths import _cache_path

        path = _cache_path(key) + ".gz"
        payload = {"data": data}
        if ts is not None:
            payload["timestamp"] = ts
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(payload, f)


# ── 交易时段 TTL 边界 ──────────────────────────────────────────────


@pytest.mark.edge
class TestGetTTLIntraday(unittest.TestCase, _CacheTestBase):
    """get_ttl 盘中/盘后行为：盘中敏感性由注册表声明（`market_hour_aware` 已退役）。

    契约（数据敏感性与性能的平衡点）：
      - 价/指（`price`/`index`）盘中降到 30s（可被 `market_hour_ttl` 全局覆盖，钳制 [30, 86400]）；
      - 盘后回到静态 TTL（24h），不为"实时"白打上游；
      - 其余类型（如 `news` 900s）**不因盘中而变短**——避免非行情数据被误配成高频打源。
    """

    def setUp(self):
        _CacheTestBase.setUp(self)

    def tearDown(self):
        _CacheTestBase.tearDown(self)

    def test_market_open_uses_short_ttl(self):
        """交易时段 + 注册表声明盘中敏感（price）→ 用 `market_hour_ttl` 覆盖值。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 120}
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("price"), 120)

    def test_market_open_clamps_min_30(self):
        """刷新 TTL 最小值限制为 30 秒。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 5}
            from src.python.cache import get_ttl

            result = get_ttl("price")
            self.assertGreaterEqual(result, 30)

    def test_market_open_clamps_max_86400(self):
        """刷新 TTL 最大值限制为 86400 秒。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 999999}
            from src.python.cache import get_ttl

            result = get_ttl("price")
            self.assertLessEqual(result, 86400)

    def test_non_intraday_type_uses_static(self):
        """未声明盘中敏感的类型 → 即使开盘也用静态 TTL（短 TTL 不生效）。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 120, "cache_ttl": {"news": 900}}
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("news"), 900)

    def test_market_closed_uses_static_ttl(self):
        """非交易时段 → 即使属感知类型也用静态 cache_ttl。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=False),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 120, "cache_ttl": {"price": 43200}}
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("price"), 43200)

    def test_market_closed_no_config_uses_default(self):
        """非交易时段且无 cache_ttl 配置 → 回退注册表内置默认 TTL。"""
        from src.python.core.registry import get_cache_ttl_defaults

        with (
            patch("src.python.cache._ttl._is_market_open", return_value=False),
            patch("src.python.config.get_config", return_value={}),
        ):
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("price"), float(get_cache_ttl_defaults()["price"]))

    def test_market_hour_ttl_missing_fallback_to_30(self):
        """market_hour_ttl 配置缺失 → 默认 30 秒。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {}
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("price"), 30, "未配置时用注册表声明的盘中 TTL")

    def test_invalid_market_hour_ttl_fallback_to_30(self):
        """market_hour_ttl 配置值非法 → 使用 30 秒默认值。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": "not_a_number"}
            from src.python.cache import get_ttl

            result = get_ttl("price")
            self.assertEqual(result, 30)

    def test_intraday_types_are_declared_by_registry(self):
        """盘中敏感集合来自注册表 `market_ttl`，不是配置列表（退役键无法扩权）。"""
        from src.python.core.registry import get_market_ttl_map

        market_ttl = get_market_ttl_map()
        self.assertIn("price", market_ttl)
        self.assertIn("index", market_ttl)
        self.assertNotIn("news", market_ttl, "非行情数据不得因盘中而降频")

    def test_retired_aware_key_cannot_widen_intraday_set(self):
        """旧 `market_hour_aware` 仍写着 `news` 也不生效：news 盘中维持静态 TTL。"""
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {
                "market_hour_aware": ["news"],
                "market_hour_ttl": 30,
                "cache_ttl": {"news": 900},
            }
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("news"), 900)

    def test_cache_ttl_override_on_intraday_type_notifies_once(self):
        """配了 `cache_ttl.price` 而盘中以 market_hour_ttl 为准 → 只提示一次（不刷屏）。"""
        import logging

        from src.python.cache import _ttl

        _ttl._INTRADAY_OVERRIDE_NOTIFIED.clear()
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=True),
            patch("src.python.config.get_config") as mock_cfg,
            self.assertLogs("invest", level=logging.INFO) as captured,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 30, "cache_ttl": {"price": 3600}}
            from src.python.cache import get_ttl

            self.assertEqual(get_ttl("price"), 30)
            self.assertEqual(get_ttl("price"), 30)
        notices = [line for line in captured.output if "盘中 TTL" in line]
        self.assertEqual(len(notices), 1, "同一类型只提示一次")

    def test_closed_hours_use_static_ttl(self):
        """非交易时段（午间休市 / 下午收盘后）→ 均走静态 TTL 分支。

        两种情况在 `get_ttl` 里由同一分支决定（只看 `_is_market_open`），
        故用一条用例覆盖，不拆成两条同义用例。
        """
        with (
            patch("src.python.cache._ttl._is_market_open", return_value=False),
            patch("src.python.config.get_config") as mock_cfg,
        ):
            mock_cfg.return_value = {"market_hour_ttl": 120, "cache_ttl": {"price": 86400}}
            from src.python.cache import get_ttl

            with self.subTest(scenario="午间休市"):
                self.assertEqual(get_ttl("price"), 86400)
            with self.subTest(scenario="下午收盘后"):
                self.assertEqual(get_ttl("price"), 86400)


# ── Gzip 边界场景 ──────────────────────────────────────────────────


class TestGzipCacheEdge(unittest.TestCase, _CacheTestBase):
    """gzip 压缩边界与损坏恢复。"""

    def setUp(self):
        _CacheTestBase.setUp(self)

    def tearDown(self):
        _CacheTestBase.tearDown(self)

    @patch("src.python.cache._store.time.time")
    def test_exact_100kb_boundary_not_gzip(self, mock_time):
        """恰 100KB（未超阈值）→ 不 gzip。"""
        mock_time.return_value = 1000.0
        from src.python.cache import set

        # 恰好 100*1024 字节（阈值是 > 不是 >=）
        boundary_data = "x" * (100 * 1024 - 50)  # 留余量给 JSON 序列化开销
        set("boundary_key", boundary_data)

        from src.python.cache._paths import _cache_path

        json_path = _cache_path("boundary_key")
        gz_path = json_path + ".gz"
        self.assertTrue(os.path.exists(json_path), "≤100KB 数据应仍为 .json")
        self.assertFalse(os.path.exists(gz_path))

    @patch("src.python.cache._store.time.time")
    def test_gz_corrupted_file_deleted_on_read(self, mock_time):
        """损坏的 .json.gz → 删除并返回 None。"""
        mock_time.return_value = 1000.0
        # 创建一个损坏的 .json.gz 文件
        from src.python.cache._paths import _cache_path

        gz_path = _cache_path("corrupted_gz") + ".gz"
        with open(gz_path, "wb") as f:
            f.write(b"this is not valid gzip data")

        from src.python.cache import get

        result = get("corrupted_gz", 3600)

        self.assertIsNone(result)
        # 损坏文件应被删除
        self.assertFalse(os.path.exists(gz_path))


# ── 旧缓存文件不兼容（带 BOM 一律按损坏清理） ────────────────


@pytest.mark.edge
class TestBomCacheFile(unittest.TestCase):
    """不再兼容带 BOM 的旧缓存文件：写侧从不写 BOM，读到即按损坏清除并重取。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_bom_cache_file_discarded(self):
        from src.python.cache._io import _read_cache_data

        fpath = os.path.join(self.tmp.name, "bom_test.json")
        payload = '{"_ts": 1000.0, "_data": {"price": 10.5}}'
        with open(fpath, "w", encoding="utf-8-sig") as f:
            f.write(payload)

        self.assertIsNone(_read_cache_data(fpath, "bom_test"))
        self.assertFalse(os.path.exists(fpath))  # 损坏文件被清理，下次重新生成


if __name__ == "__main__":
    unittest.main()
