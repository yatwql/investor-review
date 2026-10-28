"""缓存版本戳迁移与按类型清理 —— 旧戳不可读、且按类型 TTL 清理而非默认兜底。

两条业务契约：

1. **版本戳不兼容**：缓存文件名带 `_{版本戳}`（当前 `v4`），读路径只认当前戳——
   旧戳文件永远读不到（等效"作废旧缓存"），不会被误当成有效数据。
2. **清理按类型 TTL**：旧戳文件不是"永远留着"的垃圾，而是按所属类型的 TTL 清理；
   LLM 模块也各按自己的 TTL（`llm_expert_review` 4h vs `llm_global_macro` 24h），
   不会退化成统一默认值。
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "src.python.config.get_config",
        lambda: {"market_hours": {"start": "00:00", "end": "00:00"}},  # 恒为非交易时段
    )
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


def _write(cache_dir, filename: str, age_seconds: float) -> None:
    payload = {"_ts": time.time() - age_seconds, "_data": {"v": 1}}
    (cache_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def _cleanup(cache_dir=None) -> int:
    from src.python.cache._cleanup import cleanup_expired

    return cleanup_expired(dry_run=False)


class TestLegacyStampIsUnreachable:
    """非当前版本戳的缓存文件不可读，但会被按类型 TTL 清理。"""

    def test_legacy_stamp_not_readable(self, cache_env):
        from src.python.cache import get as cache_get

        _write(cache_env, "price_600519_v3.json", age_seconds=0)
        assert cache_get("price_600519", 86400) is None, "旧戳文件不得被读路径命中"

    def test_legacy_stamp_still_cleaned_by_type_ttl(self, cache_env):
        """非当前版本戳的价缓存超过 price TTL → 清理（不是永远滞留）。"""
        _write(cache_env, "price_600519_v3.json", age_seconds=86401)
        assert _cleanup() == 1

    def test_legacy_stamp_fresh_survives(self, cache_env):
        """非当前版本戳但仍在 TTL 内 → 保留（迁移期不误删有效期内数据）。"""
        _write(cache_env, "price_600519_v3.json", age_seconds=60)
        assert _cleanup() == 0


class TestPerTypeCleanupTTL:
    """清理按各类型自己的 TTL 判定，不退化成单一默认值。"""

    def test_llm_module_ttl_differs_by_type(self, cache_env):
        """expert_review（4h）5 小时后清理；global_macro（24h）同年龄保留。"""
        _write(cache_env, "llm_expert_review_abc_v4.json", age_seconds=5 * 3600)
        _write(cache_env, "llm_global_macro_abc_v4.json", age_seconds=5 * 3600)
        assert _cleanup() == 1, "只应清理 4h TTL 的 expert_review"
        assert (cache_env / "llm_global_macro_abc_v4.json").exists()
        assert not (cache_env / "llm_expert_review_abc_v4.json").exists()

    def test_negative_cache_cleaned_before_default_ttl(self, cache_env):
        """负缓存 6h/12h 的判定早于「未注册默认 24h」——不会多留半天以上。"""
        _write(cache_env, "datasink_probe_miss_a_v4.json", age_seconds=13 * 3600)  # 12h TTL
        _write(cache_env, "report_symbol_miss_a_v4.json", age_seconds=7 * 3600)  # 6h TTL
        assert _cleanup() == 2

    def test_unknown_prefix_falls_back_to_daily(self, cache_env):
        """未注册前缀走 CACHE_DAILY 兜底（仍可清理，不是永久滞留）。"""
        _write(cache_env, "some_unknown_cache_v4.json", age_seconds=86401)
        assert _cleanup() == 1


class TestExactKeyTTLOverride:
    """同前缀下的异构寿命键按精确键独立 TTL 裁，不被前缀默认值删。

    回归背景：`sector_flow_` 前缀默认 900s，但同前缀的「陈旧回退基准」设计寿命 3 天、
    「失败负缓存」设计寿命 30 分钟——曾经它们都被 900s 一并裁掉，回退链路形同虚设。
    """

    def test_stale_baseline_survives_prefix_ttl(self, cache_env):
        """1 小时龄的回退基准（前缀 TTL 只有 15 分钟）必须留下。"""
        _write(cache_env, "sector_flow_last_good.json", age_seconds=3600)
        assert _cleanup() == 0
        assert (cache_env / "sector_flow_last_good.json").exists()

    def test_negative_cache_survives_prefix_ttl(self, cache_env):
        """20 分钟龄的负缓存（前缀 TTL 只 15 分钟，自身 30 分钟）必须留下。"""
        from src.python.cache._paths import _CACHE_KEY_VERSION

        _write(cache_env, f"sector_flow_negative_{_CACHE_KEY_VERSION}.json", age_seconds=20 * 60)
        assert _cleanup() == 0

    def test_stale_baseline_expires_after_own_ttl(self, cache_env):
        """超过自身 3 天寿命才删（不是永久滞留）。"""
        _write(cache_env, "sector_flow_last_good.json", age_seconds=4 * 86400)
        assert _cleanup() == 1

    def test_negative_cache_expires_after_own_ttl(self, cache_env):
        """31 分钟即过期（负缓存不该跟 3 天基准同寿命）。"""
        from src.python.cache._paths import _CACHE_KEY_VERSION

        _write(cache_env, f"sector_flow_negative_{_CACHE_KEY_VERSION}.json", age_seconds=31 * 60)
        assert _cleanup() == 1

    def test_regular_payload_keeps_prefix_ttl(self, cache_env):
        """同前缀的常规列表载荷不受覆盖影响：仍按 900s 裁。"""
        from src.python.cache._paths import _CACHE_KEY_VERSION

        _write(cache_env, f"sector_flow_abc123def456_{_CACHE_KEY_VERSION}.json", age_seconds=3600)
        assert _cleanup() == 1

    def test_provider_ttls_come_from_registry(self):
        """取数侧与清理器同一份 TTL（两处各写一份就会飘）。"""
        from src.python.core.data_registry import get_exact_ttl_map
        from src.python.providers import akshare_extras as ae

        exact = get_exact_ttl_map()
        assert ae._SECTOR_FLOW_STALE_TTL == exact[ae._SECTOR_FLOW_LAST_KEY]
        assert ae._SECTOR_FLOW_NEG_TTL == exact[ae._SECTOR_FLOW_NEG_KEY]


class TestCacheKeyFromFileName:
    """文件名 → 逻辑缓存键的单源转换（清理与页头新鲜度共用，不得各自拼字符串）。"""

    def test_strips_version_stamp_and_json(self):
        from src.python.cache._paths import _CACHE_KEY_VERSION, cache_key_from_file_name

        assert cache_key_from_file_name(f"price_600519_{_CACHE_KEY_VERSION}.json") == "price_600519"

    def test_strips_gzip_suffix(self):
        from src.python.cache._paths import _CACHE_KEY_VERSION, cache_key_from_file_name

        assert cache_key_from_file_name(f"report_x_{_CACHE_KEY_VERSION}.json.gz") == "report_x"

    def test_legacy_stamp_kept_verbatim(self):
        """旧戳不是当前戳 → 原样保留（旧戳文件本就该读不到，转换不做猜测）。"""
        from src.python.cache import cache_key_from_file_name

        assert cache_key_from_file_name("price_600519_v3.json") == "price_600519_v3"

    def test_non_cache_file_returns_none(self):
        from src.python.cache import cache_key_from_file_name

        assert cache_key_from_file_name("notes.txt") is None
