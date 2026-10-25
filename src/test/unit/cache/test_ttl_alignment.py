"""TTL 三处对齐 —— 默认值唯一来源、清理侧与读侧同源、未注册键可见。

本文件守住五条契约（默认值/覆盖/清理/告警/盘中敏感）：

1. **默认值唯一来源**：生成的 `config.json` 里 `cache_ttl` 是空对象，默认值只来自
   缓存注册表；用户在 config 里写键才构成覆盖，删键即回默认。
2. **清理侧与读侧同源**：TTL 只由数据类型决定，清理按「剥离版本戳后的逻辑键」
   查类型——两侧取到同一个数（`get_ttl` 只接受 `data_type`，不存在按 key 的第二口径）。
3. **精确键映射用逻辑键**：文件名带 `_v{N}` 版本戳，去查精确键表必须先剥离。
4. **未注册键可见**：`cache_ttl.fund_overlap` 这类历史残留要告警（不自动删）。
5. **盘中敏感类型逐类生效**：价/指盘中 30s（清理侧同源，防"过期价被当收盘价"），
   盘后回到静态 TTL（防为"实时"白打上游）；负缓存按各自 12h/6h 判定，不吃 24h 兜底。
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    """缓存目录隔离：`_paths`（读写路径）与 `_cleanup`（模块级绑定）都要重定向。"""
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


def _write_cache(cache_env, key: str, age_seconds: float) -> None:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    payload = {"_ts": time.time() - age_seconds, "_data": {"v": 1}}
    (cache_env / f"{key}_{_CACHE_KEY_VERSION}.json").write_text(json.dumps(payload), encoding="utf-8")


def _cleanup(cache_env) -> int:
    from src.python.cache._cleanup import cleanup_expired

    return cleanup_expired(dry_run=True)


class TestCleanupReaderAlignment:
    def test_reader_ttl_has_no_key_parameter(self):
        """`get_ttl` 只接受数据类型：无 key 参数（抖动兼容层已删除）。"""
        import inspect

        from src.python.cache._ttl import get_ttl

        assert list(inspect.signature(get_ttl).parameters) == ["data_type"]

    def test_cleanup_threshold_equals_reader_ttl(self, cache_env):
        """清理判定的过期阈值 == 读侧 TTL：略小于不删、略大于才删。"""
        from src.python.cache._ttl import get_ttl

        key = "llm_expert_review_deadbeef_probe-main"
        ttl = get_ttl("llm_expert_review")

        _write_cache(cache_env, key, age_seconds=ttl - 60)
        assert _cleanup(cache_env) == 0, "读侧仍有效的文件不得被清理删除"

        _write_cache(cache_env, key, age_seconds=ttl + 60)
        assert _cleanup(cache_env) == 1

    def test_exact_key_mapping_uses_version_stripped_key(self, cache_env):
        """精确键（无指纹后缀）在清理侧也命中精确映射，不因版本戳退化为 default/前缀类型。

        判别法：从注册表的精确键表里挑一个「按精确键查到的类型 TTL」与「按前缀/默认
        查到的 TTL」不同的样本，构造年龄落在两者之间的文件——只有精确映射生效时
        才不会被判过期。
        """
        from src.python.cache._ttl import get_ttl
        from src.python.core.data_registry import get_cache_ttl_defaults, get_exact_type_map, get_prefix_type_map

        exact_map = get_exact_type_map()
        prefix_map = get_prefix_type_map()
        defaults = get_cache_ttl_defaults()

        sample = None
        for key, exact_type in exact_map.items():
            prefix_type = next((dt for pfx, dt in prefix_map.items() if key.startswith(pfx)), "default")
            exact_ttl = defaults.get(exact_type, 86400)
            naive_ttl = defaults.get(prefix_type, 86400)
            if exact_ttl > naive_ttl * 1.5:
                sample = (key, exact_type, exact_ttl, naive_ttl)
                break
        assert sample, "注册表里应至少有一个精确键，其类型 TTL 明显长于前缀/默认兜底"
        key, data_type, exact_ttl, naive_ttl = sample

        ttl = get_ttl(data_type)
        assert ttl == pytest.approx(exact_ttl, rel=1e-9)
        _write_cache(cache_env, key, age_seconds=(naive_ttl + ttl) / 2)
        assert _cleanup(cache_env) == 0, f"精确键 {key} 应命中 {data_type} 的 TTL，未被提前删除"


class TestSparseOverride:
    def test_registry_is_the_default(self, monkeypatch):
        """没有任何 config 覆盖时，`get_ttl` 取注册表默认值。"""
        from src.python.cache import _ttl
        from src.python.core.data_registry import get_cache_ttl_defaults

        monkeypatch.setattr(_ttl, "get_config", lambda: {"cache_ttl": {}}, raising=False)
        assert _ttl.get_ttl("llm_expert_review") == pytest.approx(
            get_cache_ttl_defaults()["llm_expert_review"], rel=1e-9
        )

    def test_new_install_config_file_has_empty_ttl_block(self, tmp_path, monkeypatch):
        """新装/重置生成的 config.json：cache_ttl 为空对象（不是 37 行副本）。"""
        from src.python.config._config_defaults import _get_default_config_template

        text = _get_default_config_template()
        doc = json.loads("\n".join(line.split("  //")[0] for line in text.splitlines()))
        assert doc["cache_ttl"] == {}


class TestUnregisteredKeyWarning:
    def test_unknown_cache_ttl_key_warns(self, caplog):
        import logging

        from src.python.config._validation_scalars import _validate_cache_ttl

        with caplog.at_level(logging.WARNING, logger="invest"):
            issues = _validate_cache_ttl({"cache_ttl": {"fund_overlap": 604800}}, 0)
        assert issues == 1
        assert any(
            "fund_overlap" in r.getMessage() and "不是已注册的缓存类型" in r.getMessage() for r in caplog.records
        )

    def test_registered_key_does_not_warn(self, caplog):
        import logging

        from src.python.config._validation_scalars import _validate_cache_ttl

        with caplog.at_level(logging.WARNING, logger="invest"):
            issues = _validate_cache_ttl({"cache_ttl": {"price": 3600, "llm_expert_review": 21600}}, 0)
        assert issues == 0
        assert not any("不是已注册的缓存类型" in r.getMessage() for r in caplog.records)


class TestIntradayAndNegativeCacheTTL:
    """盘中敏感与缺失负缓存的 TTL 契约（数据敏感性与上游负担的平衡点）。"""

    def test_negative_cache_types_are_registered(self):
        """两个负缓存类型的 TTL 由注册表承载（而非调用点常量）。"""
        from src.python.core.registry import get_cache_ttl_defaults, get_prefix_type_map

        ttl = get_cache_ttl_defaults()
        assert ttl["datasink_probe_miss"] == 12 * 3600
        assert ttl["report_symbol_miss"] == 6 * 3600
        prefixes = get_prefix_type_map()
        assert prefixes["datasink_probe_miss_"] == "datasink_probe_miss"
        assert prefixes["report_symbol_miss_"] == "report_symbol_miss"

    def test_probe_miss_survives_twelve_hours_only(self, cache_env):
        """带 12h 负缓存的探测缺失：7h 保留、13h 清理（不被 24h 兜底延长）。"""
        _write_cache(cache_env, "datasink_probe_miss_abc123", age_seconds=7 * 3600)
        assert _cleanup(cache_env) == 0, "7h 未到 12h，应保留"
        _write_cache(cache_env, "datasink_probe_miss_def456", age_seconds=13 * 3600)
        assert _cleanup(cache_env) == 1, "13h 超过 12h，应清理"

    def test_symbol_miss_expires_at_six_hours(self, cache_env):
        """标的正文缺失（6h）在 7h 后清理——负结论不跨报告周期堆积。"""
        _write_cache(cache_env, "report_symbol_miss_abc123", age_seconds=7 * 3600)
        assert _cleanup(cache_env) == 1

    def test_intraday_price_uses_short_ttl_on_cleanup(self, cache_env, monkeypatch):
        """盘中：价的 60s 缓存即过期（清理侧与读侧同为 30s），防盘中价被当收盘价。"""
        from src.python.cache import _ttl as ttl_mod

        monkeypatch.setattr(ttl_mod, "_is_market_open", lambda: True)

        _write_cache(cache_env, "price_600519", age_seconds=60)
        assert _cleanup(cache_env) == 1, "盘中 30s TTL：60s 前写入的价必须清理"

    def test_closed_market_price_keeps_static_ttl(self, cache_env, monkeypatch):
        """盘后：静态 TTL（24h）生效，1h 前抓的价格不重复清理（避免白打上游）。"""
        from src.python.cache import _ttl as ttl_mod

        monkeypatch.setattr(ttl_mod, "_is_market_open", lambda: False)

        _write_cache(cache_env, "price_600519", age_seconds=3600)
        assert _cleanup(cache_env) == 0

    def test_every_registered_type_has_positive_ttl(self):
        """全量结构不变量：每个注册类型的 TTL 为正（含负缓存与盘中敏感类型）。"""
        from src.python.core.registry import get_cache_ttl_defaults, get_market_ttl_map

        ttl = get_cache_ttl_defaults()
        assert ttl, "注册表不应为空"
        assert all(value > 0 for value in ttl.values())
        assert all(value > 0 for value in get_market_ttl_map().values())
