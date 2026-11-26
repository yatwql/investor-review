"""端点节流策略解析与 429 并发诊断的容错分支单元测试（llm/pacing.py）。

锁住的契约：
  - pacing 段**逐字段**容错：单个坏字段按 0 处理并记 WARNING，其余字段的约束照常生效
  - 惰性装载失败（配置层不可用）按「无约束」继续，不污染调用主链路
  - 429 并发诊断：配置读取失败回落默认全局并发 3；端点策略装载失败按「未配置」提示
  - 端点未配置 pacing 且全局并发已为 1 → 建议指向配额/风控而非继续降并发
"""

from __future__ import annotations

import pytest

from src.python.llm import pacing as pacing_mod
from src.python.llm.pacing import parse_policy, reset_policies

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


def _raise_config_unreadable():
    raise RuntimeError("配置层不可用")


class TestParsePolicyFieldTolerance:
    def test_non_numeric_jitter_zeroed_while_min_interval_kept(self):
        policy = parse_policy({"min_interval": 1.5, "jitter": "abc"})

        assert policy is not None
        assert policy.min_interval == pytest.approx(1.5)
        assert policy.jitter == pytest.approx(0.0)

    def test_non_integer_max_concurrency_zeroed_while_min_interval_kept(self):
        policy = parse_policy({"min_interval": 2, "max_concurrency": "many"})

        assert policy is not None
        assert policy.min_interval == pytest.approx(2.0)
        assert policy.max_concurrency == 0


class TestLazyLoadDegradation:
    def test_lazy_load_failure_means_no_constraint(self, monkeypatch):
        reset_policies()
        monkeypatch.setattr("src.python.config.get_llm_config", _raise_config_unreadable)
        try:
            assert pacing_mod.get_policy("kimi-main") is None
        finally:
            reset_policies()


class TestConcurrencyHintDegradation:
    def test_config_failure_falls_back_to_default_global_limit(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", _raise_config_unreadable)

        hint = pacing_mod._concurrency_hint("")

        assert "llm_max_concurrency=3" in hint, "配置不可读时回显默认全局并发，不阻断诊断日志"

    def test_policy_load_failure_reported_as_unconfigured(self, monkeypatch):
        def _raise(_key):
            raise RuntimeError("策略装载失败")

        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"llm_max_concurrency": 4})
        monkeypatch.setattr(pacing_mod, "get_policy", _raise)

        hint = pacing_mod._concurrency_hint("kimi-main")

        assert "pacing.max_concurrency=未配置" in hint, "策略装载失败按无约束提示，不给假约束"

    def test_no_endpoint_pacing_at_global_floor_points_to_quota(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"llm_max_concurrency": 1})

        hint = pacing_mod._concurrency_hint("")

        assert "该端点未配置 pacing" in hint
        assert "RPM/TPM" in hint, "并发已是下限时建议须指向配额/风控而非继续降并发"
