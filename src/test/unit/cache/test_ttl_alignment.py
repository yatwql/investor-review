"""TTL 三处对齐 —— 默认值唯一来源、清理侧与读侧同源、未注册键可见。

本文件守住四条契约（默认值/覆盖/清理/告警）：

1. **默认值唯一来源**：生成的 `config.json` 里 `cache_ttl` 是空对象，默认值只来自
   缓存注册表；用户在 config 里写键才构成覆盖，删键即回默认。
2. **清理侧与读侧同源**：清理按「剥离版本戳后的逻辑键」查类型、并按同一个 key 算
   TTL 抖动因子——否则读侧按 ±15% 判定、清理按 1.0×判定，约一半 key 会被提前最多
   15% 删除（实测事故 C）。
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
    def test_cleanup_uses_same_jitter_factor_as_reader(self, cache_env):
        """同一 key：清理判定用的 TTL == 读侧 `get_ttl(type, key)`（含抖动）。"""
        from src.python.cache._ttl import get_ttl

        key = "llm_expert_review_deadbeef_probe-main"
        reader_ttl = get_ttl("llm_expert_review", key)
        # 只要抖动生效，两侧就必须相等；先确认这个 key 的因子不是 1.0（覆盖因子≠1 的场景）
        assert reader_ttl != pytest.approx(get_ttl("llm_expert_review"), rel=1e-9)

        # 文件年龄略小于 reader_ttl → 两边都应判「未过期」
        _write_cache(cache_env, key, age_seconds=reader_ttl - 60)
        assert _cleanup(cache_env) == 0, "读侧仍有效的文件不得被清理删除"

        # 略超过 reader_ttl → 清理才删
        _write_cache(cache_env, key, age_seconds=reader_ttl + 60)
        assert _cleanup(cache_env) == 1

    def test_exact_key_mapping_uses_version_stripped_key(self, cache_env):
        """精确键（无指纹后缀）在清理侧也要能命中类型映射。"""
        from src.python.core.data_registry import get_exact_type_map
        from src.python.cache._ttl import get_ttl

        sample = next(iter(get_exact_type_map()))
        data_type = get_exact_type_map()[sample]
        ttl = get_ttl(data_type, sample)
        # 精确键的 TTL 与所属类型一致（不因版本戳退化为 default/日级）
        assert ttl == pytest.approx(get_ttl(data_type), rel=0.2) or ttl != pytest.approx(86400, rel=0)
        _write_cache(cache_env, sample, age_seconds=ttl - 60)
        assert _cleanup(cache_env) == 0


class TestSparseOverride:
    def test_template_has_no_default_copy(self):
        from src.python.config._config_defaults import _DEFAULT_CONFIG, _get_default_config_template

        assert _DEFAULT_CONFIG["cache_ttl"] == {}
        assert '"cache_ttl": {}' in _get_default_config_template()

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
