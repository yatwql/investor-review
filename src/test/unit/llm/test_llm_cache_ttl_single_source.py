"""LLM 模块缓存 TTL 单一来源 —— 读侧与清理侧必须用同一个数。

历史偏差：`get_cache_ttl_llm("self_review")` 未在映射表里，回落到
`llm_global_macro`（24h），而缓存清理按 data_registry 的 7200s 判定——
2h 后启动清理删掉了读侧仍认为有效的文件，下一份报告白重算一次自检/归因
（真金白银 + 耗时），日志上只写「无此缓存文件」，看不出原因。

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

    def test_expert_review_keeps_short_ttl(self):
        """专家复盘按 2h 刷新（日内行情/持仓变化快），不受本次对齐影响。"""
        assert get_cache_ttl_llm("expert_review") == pytest.approx(7200, abs=1e-9)
