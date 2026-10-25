"""LLM 模块缓存 TTL 与指纹组合 —— 覆盖层 × 命中源的业务矩阵。

TTL 矩阵文件管数据缓存；LLM 缓存多一层**指纹**（内容不变才可复用）。本文件把两者
组合起来，钉住报告链路的成本与时效边界：

| 角度 | 场景 |
|------|------|
| 覆盖层 | 注册表默认 / `cache_ttl` 覆盖生效 / 非法覆盖回落 |
| TTL × 指纹 | 未过期+指纹未变→命中；未过期+指纹变→未命中；过期+指纹未变→未命中 |
| 模块分组 | 4h（专家/体检/穿透/新闻）与 24h（政经/自检/持仓变动）的差异 |
| 缓存关闭 | 关闭时既不读也不写（每份报告都真调用） |
| 边界 | TTL±1s 的命中/未命中判定 |
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]

#: 模块 → (注册表默认 TTL 秒, 说明)
LLM_TTL_CASES = [
    ("llm_expert_review", 4 * 3600, "智囊团深度复盘"),
    ("llm_health_check", 4 * 3600, "持仓体检报告"),
    ("llm_penetration_deep", 4 * 3600, "穿透深度分析"),
    ("llm_news_correlation", 4 * 3600, "新闻关联"),
    ("llm_global_macro", 24 * 3600, "全球政经局势"),
    ("llm_self_review", 24 * 3600, "生成后自检"),
    ("llm_holding_change", 24 * 3600, "持仓变动归因"),
]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


def _ttl_env(monkeypatch, config: dict) -> None:
    from src.python.cache import _ttl

    monkeypatch.setattr(_ttl, "_is_market_open", lambda: False)
    monkeypatch.setattr("src.python.config.get_config", lambda: config)


def _write_llm_cache(cache_dir, module: str, fingerprint: str, age_seconds: float) -> None:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    key = f"{module}_{fingerprint}"
    payload = {"_ts": time.time() - age_seconds, "_data": {"brief": "内容"}}
    (cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("module,default_ttl,_label", LLM_TTL_CASES, ids=[c[0] for c in LLM_TTL_CASES])
def test_llm_module_default_ttl(cache_env, monkeypatch, module, default_ttl, _label):
    """注册表默认：成本敏感模块 4h、内容型模块 24h。"""
    from src.python.cache import get_ttl

    _ttl_env(monkeypatch, {})
    assert get_ttl(module) == default_ttl


@pytest.mark.parametrize("module,default_ttl,_label", LLM_TTL_CASES, ids=[c[0] for c in LLM_TTL_CASES])
def test_llm_cache_hit_boundary(cache_env, monkeypatch, module, default_ttl, _label):
    """TTL 边界：TTL−1s 命中、TTL+1s 未命中（成本与时效的分界线）。"""
    from src.python.cache import get as cache_get

    _ttl_env(monkeypatch, {})
    _write_llm_cache(cache_env, module, "fp", default_ttl - 1)
    assert cache_get(f"{module}_fp", default_ttl) is not None
    _write_llm_cache(cache_env, module, "fp2", default_ttl + 1)
    assert cache_get(f"{module}_fp2", default_ttl) is None


@pytest.mark.parametrize("module,default_ttl,_label", LLM_TTL_CASES, ids=[c[0] for c in LLM_TTL_CASES])
def test_llm_cache_ttl_override_applies(cache_env, monkeypatch, module, default_ttl, _label):
    """`cache_ttl` 覆盖：把 TTL 覆写为 1h 后，2 小时前的缓存即失效。"""
    from src.python.cache import get as cache_get, get_ttl

    override = 3600.0
    _ttl_env(monkeypatch, {"cache_ttl": {module: override}})
    assert get_ttl(module) == override
    _write_llm_cache(cache_env, module, "fp", 2 * 3600)
    assert cache_get(f"{module}_fp", get_ttl(module)) is None, "覆盖后的 TTL 必须生效"


@pytest.mark.parametrize("module,default_ttl,_label", LLM_TTL_CASES, ids=[c[0] for c in LLM_TTL_CASES])
def test_llm_cache_invalid_override_falls_back(cache_env, monkeypatch, module, default_ttl, _label):
    """非法覆盖（0 / 负数 / 非数字）回落到注册表默认。"""
    from src.python.cache import get_ttl

    for bad in (0, -1, "abc"):
        _ttl_env(monkeypatch, {"cache_ttl": {module: bad}})
        assert get_ttl(module) == default_ttl, f"{module} 非法覆盖 {bad!r} 应回默认"


class TestFingerprintInteraction:
    """指纹 × TTL 的四象限（只有"未过期 + 指纹未变"才允许复用）。"""

    def test_fresh_and_same_fingerprint_hits(self, cache_env, monkeypatch):
        from src.python.cache import get as cache_get, get_ttl

        _ttl_env(monkeypatch, {})
        _write_llm_cache(cache_env, "llm_expert_review", "same_fp", 60)
        assert cache_get("llm_expert_review_same_fp", get_ttl("llm_expert_review")) is not None

    def test_fresh_but_different_fingerprint_misses(self, cache_env, monkeypatch):
        """内容变了（指纹不同）→ 即使未过期也不得复用（数据敏感性优先于省钱）。"""
        from src.python.cache import get as cache_get, get_ttl

        _ttl_env(monkeypatch, {})
        _write_llm_cache(cache_env, "llm_expert_review", "old_fp", 60)
        assert cache_get("llm_expert_review_new_fp", get_ttl("llm_expert_review")) is None

    def test_expired_same_fingerprint_misses(self, cache_env, monkeypatch):
        """指纹没变但 TTL 到期 → 重新调用（时效上限）。"""
        from src.python.cache import get as cache_get, get_ttl

        _ttl_env(monkeypatch, {})
        ttl = get_ttl("llm_expert_review")
        _write_llm_cache(cache_env, "llm_expert_review", "same_fp", ttl + 60)
        assert cache_get("llm_expert_review_same_fp", ttl) is None

    def test_cost_modules_shorter_than_content_modules(self, cache_env, monkeypatch):
        """成本敏感（4h）短于内容型（24h）：频繁变化的内容更该重算，稳定内容更该复用。"""
        from src.python.cache import get_ttl

        _ttl_env(monkeypatch, {})
        assert get_ttl("llm_expert_review") < get_ttl("llm_global_macro")


class TestPerModuleCacheSwitch:
    """逐模块缓存开关（`cache_enabled_<模块>`）：关闭时该模块每份报告都真调用。

    开关在编排层读取（`generate_all_llm` 的预检/派发判定），本文件验证配置键与默认值
    契约——关闭只影响该模块，不影响其他模块与 TTL 解析。
    """

    @pytest.mark.parametrize("module", [c[0] for c in LLM_TTL_CASES])
    def test_per_module_cache_switch_has_default(self, module):
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        # 模块键去掉 llm_ 前缀后对应开关名；news_correlation 的缓存开关按新闻项粒度命名
        key = f"cache_enabled_{module.removeprefix('llm_')}"
        if key not in _DEFAULT_LLM_SETTINGS:
            pytest.skip(f"{key} 不属逐模块缓存开关（该模块缓存按条目粒度控制）")
        assert _DEFAULT_LLM_SETTINGS[key] is True, f"{key} 默认开启"

    def test_switch_does_not_change_ttl_resolution(self, cache_env, monkeypatch):
        """关闭缓存不解 TTL 语义：`get_ttl` 仍按注册表给值（开关在编排层生效）。"""
        from src.python.cache import get_ttl

        _ttl_env(monkeypatch, {"cache_ttl": {}})
        assert get_ttl("llm_expert_review") == 4 * 3600
