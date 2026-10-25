"""TTL 三处对齐 —— 默认值唯一来源、清理侧与读侧同源、未注册键可见。

本文件守住四条契约（默认值/覆盖/清理/告警）：

1. **默认值唯一来源**：生成的 `config.json` 里 `cache_ttl` 是空对象，默认值只来自
   缓存注册表；用户在 config 里写键才构成覆盖，删键即回默认。
2. **清理侧与读侧同源**：TTL 与 key 无关（抖动层已移除），清理按「剥离版本戳后的
   逻辑键」查类型——两侧取到同一个数。若 TTL 依赖 key 而只有部分调用点传 key，
   就会出现「读侧仍有效、清理已删」的成规模白删（实测事故 C）。
3. **精确键映射用逻辑键**：文件名带 `_v{N}` 版本戳，去查精确键表必须先剥离。
4. **未注册键可见**：`cache_ttl.fund_overlap` 这类历史残留要告警（不自动删）。
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
    def test_ttl_is_key_independent(self):
        """同一数据类型的 TTL 与传入的 key 无关（历史 key 参数保留但不参与计算）。

        深度审计结论：按 key 抖动若只在部分调用点生效，就会与清理侧判定期不一致
        （成规模的白删）。本应用缓存按资产逐条写入、过期时刻天然分散，抖动的收益
        低于其维护成本，故整层移除——读侧/清理侧因此天然同值。
        """
        from src.python.cache._ttl import get_ttl

        base = get_ttl("llm_expert_review")
        for key in ("llm_expert_review_a", "llm_expert_review_b", "llm_expert_review_c"):
            assert get_ttl("llm_expert_review", key) == base, key

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
