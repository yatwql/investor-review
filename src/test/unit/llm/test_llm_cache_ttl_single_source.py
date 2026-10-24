"""LLM 模块缓存 TTL 单一来源 —— 读侧与清理侧必须用同一个数。

契约来源：**读侧不持有任何独立配置**——`get_cache_ttl_llm(模块)` 只是把模块键换成
`llm_<模块>` 后直读 `cache.get_ttl`，而后者本身就是「config.json 覆盖 → 注册表默认值 →
CACHE_DAILY 兜底」。因此读侧、启动清理、统计、配置模板读的是同一份数字，不存在
「两套值各写一遍」的漂移面；未注册模块会告警而不是静默借用别的模块 TTL。

本文件锁两条契约：
1. 每个 LLM 模块的读侧 TTL == 注册表（清理/配置）TTL；
2. 未登记模块必须「告警 + 日级兜底」，不得静默借用别的模块 TTL；
3. 本轮产品决策的 4h 默认值（专家复盘/体检/穿透/新闻关联）逐项锁定。
"""

from __future__ import annotations

import pytest

from src.python.core.data_registry import get_cache_ttl_defaults
from src.python.llm.fingerprint import get_cache_ttl_llm

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]


def _llm_cache_modules() -> list[str]:
    """从缓存注册表派生「LLM 缓存模块」清单（键 = `llm_<模块>`，不写死清单）。"""
    from src.python.core.data_registry import get_registered_data_types

    return sorted(dt[len("llm_") :] for dt in get_registered_data_types() if dt.startswith("llm_"))


class TestTTLSingleSource:
    @pytest.mark.parametrize("module", _llm_cache_modules())
    def test_reader_ttl_matches_registry(self, module):
        """读侧 TTL 与注册表（清理/配置同源）逐模块相等。"""
        registry = get_cache_ttl_defaults()
        data_type = f"llm_{module}"
        assert data_type in registry, f"{data_type} 未在缓存注册表登记"
        assert get_cache_ttl_llm(module) == pytest.approx(registry[data_type], abs=1e-9)

    def test_unknown_module_warns_and_falls_back_to_daily(self, caplog):
        """未登记模块：告警 + 日级兜底，绝不静默借用别的模块 TTL。"""
        import logging

        from src.python.core.constants import CACHE_DAILY

        with caplog.at_level(logging.WARNING, logger="invest"):
            ttl = get_cache_ttl_llm("nonexistent_module")
        assert ttl == pytest.approx(CACHE_DAILY, abs=1e-9)
        assert any("未在 data_registry 登记" in r.getMessage() for r in caplog.records)

    def test_content_addressed_modules_use_daily_ttl(self):
        """内容寻址模块（自检/归因）按 24h：键含上游正文，输入不变无需按时间重算。"""
        for module in ("self_review", "holding_change"):
            assert get_cache_ttl_llm(module) == pytest.approx(86400, abs=1e-9), module

    def test_registry_carries_the_four_hour_defaults(self):
        """4h 决策落在注册表（默认值唯一来源）；模板稀疏性由缓存域用例守护。"""
        from src.python.core.data_registry import get_cache_ttl_defaults

        defaults = get_cache_ttl_defaults()
        for module in ("expert_review", "health_check", "penetration_deep", "news_correlation"):
            assert defaults[f"llm_{module}"] == 14400, module

    @pytest.mark.parametrize("module", ("expert_review", "health_check", "penetration_deep", "news_correlation"))
    def test_analysis_modules_use_four_hour_ttl(self, module):
        """分析类模块统一 4h：平衡「日内变化要看得到」与「每次重算都是钱」。"""
        assert get_cache_ttl_llm(module) == pytest.approx(14400, abs=1e-9), module
