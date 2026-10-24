"""LLM 模块缓存 TTL 单一来源 —— 读侧与清理侧必须用同一个数。

契约来源：读侧 TTL 由 `get_cache_ttl_llm` 的映射表给出，清理/配置派生由
`core/data_registry` 的 `cache_ttl` 给出；两侧必须是同一个数——任一侧漏登记
就会「读侧认为有效、清理侧已删」，表现为刚写的缓存下一轮又没了（真金白银 +
耗时，日志只写「无此缓存文件」）。

本文件锁两条契约：
1. 每个 LLM 模块的读侧 TTL == 注册表（清理/配置）TTL；
2. 新增模块漏登记映射时，测试直接报红（不再静默继承 global_macro）。
"""

from __future__ import annotations

import pytest

from src.python.core.data_registry import get_cache_ttl_defaults
from src.python.llm.fingerprint import get_cache_ttl_llm

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]

#: 走 LLM 缓存读路径的模块（含串行后置模块）
_LLM_CACHE_MODULES = (
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "self_review",
    "holding_change",
    "debate_pro",
    "debate_con",
    "debate_synthesis",
)


class TestTTLSingleSource:
    @pytest.mark.parametrize("module", _LLM_CACHE_MODULES)
    def test_reader_ttl_matches_registry(self, module):
        """读侧 TTL 与注册表（清理/配置同源）逐模块相等。"""
        registry = get_cache_ttl_defaults()
        data_type = f"llm_{module}"
        assert data_type in registry, f"{data_type} 未在缓存注册表登记"
        assert get_cache_ttl_llm(module) == pytest.approx(registry[data_type], abs=1e-9)

    def test_unknown_module_does_not_silently_inherit_global(self):
        """未登记的子类型不得伪装成 global_macro 的 24h（暴露漏登记）。"""
        registry = get_cache_ttl_defaults()
        assert get_cache_ttl_llm("self_review") != pytest.approx(registry["llm_global_macro"]) or (
            registry["llm_self_review"] == registry["llm_global_macro"]
        )

    def test_content_addressed_modules_use_daily_ttl(self):
        """内容寻址模块（自检/归因）按 24h：键含上游正文，输入不变无需按时间重算。"""
        for module in ("self_review", "holding_change"):
            assert get_cache_ttl_llm(module) == pytest.approx(86400, abs=1e-9), module

    @pytest.mark.parametrize("module", ("expert_review", "health_check", "penetration_deep"))
    def test_generated_config_template_carries_four_hour_ttl(self, module):
        """生成配置的程序（`_DEFAULT_CONFIG` → 模板）写出的值同样是 4h。"""
        from src.python.config._config_defaults import _DEFAULT_CONFIG

        assert int(_DEFAULT_CONFIG["cache_ttl"][f"llm_{module}"]) == 14400

    @pytest.mark.parametrize("module", ("expert_review", "health_check", "penetration_deep"))
    def test_analysis_modules_use_four_hour_ttl(self, module):
        """三个分析模块统一 4h：平衡「日内变化要看得到」与「每次重算都是钱」。"""
        assert get_cache_ttl_llm(module) == pytest.approx(14400, abs=1e-9), module
