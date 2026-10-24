"""生成参数入指纹：温度/输出上限/思考参数变化 → 键变化；cache 等无关项 → 键不变。"""

from __future__ import annotations

import copy

import pytest

from src.python.llm import module_fingerprint as mf
from src.python.llm.module_fingerprint import ModuleFingerprintInputs

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


def _config(**overrides) -> dict:
    base = {
        "temperature_global_macro": 0.3,
        "max_tokens_global_macro": 3072,
        "thinking_enabled_global_macro": False,
        "thinking_budget_global_macro": 6000,
        "reasoning_effort_global_macro": "high",
        "temperature_expert_review": 0.3,
        "max_tokens_expert_review": 36000,
        "thinking_enabled_expert_review": True,
        "thinking_budget_expert_review": 24000,
        "reasoning_effort_expert_review": "low",
        "temperature_health_check": 0.1,
        "max_tokens_health_check": 24000,
        "thinking_enabled_health_check": True,
        "thinking_budget_health_check": 18000,
        "reasoning_effort_health_check": "medium",
        "temperature_penetration_deep": 0.1,
        "max_tokens_penetration_deep": 12288,
        "thinking_enabled_penetration_deep": False,
        "thinking_budget_penetration_deep": 12000,
        "reasoning_effort_penetration_deep": "high",
        "temperature_self_review": 0.1,
        "max_tokens_self_review": 2048,
        "thinking_enabled_self_review": False,
        "thinking_budget_self_review": None,
        "reasoning_effort_self_review": None,
        "temperature_holding_change": 0.2,
        "max_tokens_holding_change": 2048,
        "thinking_enabled_holding_change": False,
        "thinking_budget_holding_change": None,
        "reasoning_effort_holding_change": None,
        "debate": {"procon": {"synthesis_temperature": 0.5}},
    }
    base.update(overrides)
    return base


@pytest.fixture
def fingerprint_config(monkeypatch):
    """可切换的 llm 配置（patch 到调用点模块属性）。"""

    def _apply(**overrides):
        config = _config(**overrides)
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: copy.deepcopy(config))
        return config

    return _apply


def _inputs() -> ModuleFingerprintInputs:
    return ModuleFingerprintInputs(
        total_mv=100.0,
        total_cost=90.0,
        total_profit=10.0,
        total_today_profit=1.0,
        holdings_details=[{"name": "示例", "code": "600519", "cost": 100.0}],
        penetrated_assets=[{"name": "资产", "code": "000001", "ratio": 0.5}],
        categories={"股票": 1},
        history_data={"annualized_volatility": 0.15},
    )


_BUILDERS = {
    "global_macro": lambda i: mf.global_macro_fingerprint(i),
    "expert_review": lambda i: mf.expert_review_fingerprint(i),
    "health_check": lambda i: mf.health_check_fingerprint(i),
    "penetration_deep": lambda i: mf.penetration_deep_fingerprint(i),
    "self_review": lambda i: mf.self_review_fingerprint({"global_macro": "<p>x</p>"}),
    "debate_procon": lambda i: mf.debate_procon_fingerprint(i),
    "debate_synthesis": lambda i: mf.debate_synthesis_fingerprint(i, "综合提示词"),
}


@pytest.mark.unit
class TestGenerationParamsInFingerprint:
    @pytest.mark.parametrize("name", list(_BUILDERS))
    def test_temperature_change_changes_key(self, name, fingerprint_config):
        fingerprint_config()
        before = _BUILDERS[name](_inputs())
        module = "expert_review" if name.startswith("debate") else name
        fingerprint_config(**{f"temperature_{module}": 0.9})
        after = _BUILDERS[name](_inputs())
        assert before != after

    @pytest.mark.parametrize("name", ["global_macro", "expert_review", "health_check", "penetration_deep"])
    def test_max_tokens_change_changes_key(self, name, fingerprint_config):
        fingerprint_config()
        before = _BUILDERS[name](_inputs())
        fingerprint_config(**{f"max_tokens_{name}": 9000})
        assert _BUILDERS[name](_inputs()) != before

    def test_thinking_budget_change_changes_key(self, fingerprint_config):
        fingerprint_config()
        before = _BUILDERS["expert_review"](_inputs())
        fingerprint_config(thinking_budget_expert_review=30000)
        assert _BUILDERS["expert_review"](_inputs()) != before

    def test_unrelated_setting_keeps_key(self, fingerprint_config):
        """cache 等与生成无关的项不参与指纹（避免无谓失效）。"""
        fingerprint_config()
        before = _BUILDERS["expert_review"](_inputs())
        fingerprint_config(cache_enabled_expert_review=False, llm_max_concurrency=8, max_retries=5)
        assert _BUILDERS["expert_review"](_inputs()) == before

    def test_same_config_twice_is_stable(self, fingerprint_config):
        """预检侧与写侧调用同一构造器 → 两次结果逐字节一致。"""
        fingerprint_config()
        first = mf.expert_review_fingerprint(_inputs())
        second = mf.expert_review_fingerprint(_inputs())
        assert first == second

    def test_config_unavailable_keeps_key(self, monkeypatch):
        """读取失败（无凭据/未初始化）不并入后缀——存量缓存不整体失效。"""
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: None)
        config_fp = mf.expert_review_fingerprint(_inputs())

        monkeypatch.setattr("src.python.config.get_llm_config", lambda: _config())
        assert mf.expert_review_fingerprint(_inputs()) != config_fp
