"""LLM 缓存命中矩阵 — 逐模块、逐场景的可复现验证（同进程、真实生成入口）。

与 `test_report_sequence_cache.py` 的分工：那个文件守「同输入第二份全命中」这条底线，
本文件把矩阵铺开——**每个模块单独**变换它自己消费的输入，断言「该模块必重算、
其余模块必须仍命中」；再覆盖强制重算、模块级强制、Provider 切换、生成参数变化、
TTL 过期、内存态复位、串行后置模块（生成后自检 / 持仓变动复盘归因）。

全部用例不联网：`call_llm` 一律 mock，缓存目录隔离到 tmp（`llm_cache_dir`）。
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from src.test.unit.llm._cache_fixtures import (
    CHAIN_CONFIG,
    MODULE_INDEX,
    LLM_REPLY_DEFAULT,
    degradation_events,
    make_inputs,
    run_generate_all_llm,
)

# `unit_core` 横切标记：缓存命中契约属核心基础设施行为，需随 P0 `dev-verify` 跑
# （该档选择面不含 `unit_llm`，只标 llm 域会让这批回归只在 P1 才执行）。
pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.unit_core,
    pytest.mark.usefixtures("offline_external_sources"),
]

_IDX = MODULE_INDEX


def _run(inputs, degradation=None, **kwargs):
    return run_generate_all_llm(inputs, degradation=degradation, **kwargs)


def _precheck_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage()]


class TestPerModulePrecision:
    """每个模块只对自己消费的输入敏感；别人的输入变，它必须仍命中。"""

    def test_index_change_invalidates_index_consumers_only(self, llm_cache_dir):
        """指数变化 → 直接消费指数的 global_macro 与含竞争语境的 expert_review 重算；
        health_check / penetration_deep 的提示词不含指数段，必须仍命中。"""
        base = make_inputs()
        _run(base)
        changed = dict(base)
        changed["a_indices"] = {"sh000300": {"name": "沪深300", "close": 4100.0, "change_pct": 3.0}}
        flags = _run(changed)
        assert flags[_IDX["global_macro"]] is False
        assert flags[_IDX["expert_review"]] is False, "竞争语境块由指数渲染，须重算"
        for key in ("health_check", "penetration_deep"):
            assert flags[_IDX[key]] is True, f"{key} 不该因指数变化重算：{flags}"

    def test_metrics_change_only_invalidates_expert(self, llm_cache_dir):
        base = make_inputs()
        _run(base)
        changed = dict(base, metrics={"sharpe": 2.4, "hhi": 0.55})
        flags = _run(changed)
        assert flags[_IDX["expert_review"]] is False
        for key in ("global_macro", "health_check", "penetration_deep"):
            assert flags[_IDX[key]] is True, f"{key} 不该因量化指标变化重算：{flags}"

    def test_penetration_change_invalidates_penetration_consumers(self, llm_cache_dir):
        """穿透资产是 expert_review / health_check / penetration_deep 三处的入参，
        变化时三者都要重算；global_macro 不消费穿透明细，必须仍命中。"""
        base = make_inputs()
        _run(base)
        changed = dict(base)
        changed["penetrated_assets"] = [{"name": "测试B", "code": "000001", "weight": 100.0}]
        flags = _run(changed)
        for key in ("expert_review", "health_check", "penetration_deep"):
            assert flags[_IDX[key]] is False, f"{key} 消费穿透资产，必须重算：{flags}"
        assert flags[_IDX["global_macro"]] is True, f"global_macro 不该被牵连：{flags}"

    def test_new_failure_source_invalidates_health_not_others(self, llm_cache_dir):
        """数据源失败集合变化（新增一个源）→ health_check 重算，其余不动。

        与「同一源的失败条数/累计次数变化 → 不重算」互补：去噪不得把新故障也一起抹平。
        """
        base = make_inputs()
        _run(base, degradation_events("industry"))
        flags = _run(base, degradation_events("industry", "tencent"))
        assert flags[_IDX["health_check"]] is False
        for key in ("global_macro", "expert_review", "penetration_deep"):
            assert flags[_IDX[key]] is True, f"{key} 不该因数据源失败集合变化重算：{flags}"

    def test_history_risk_change_invalidates_risk_consumers(self, llm_cache_dir):
        """历史风险信号变化 → 消费该摘要的模块重算（global_macro 不消费，仍命中）。"""
        base = make_inputs()
        _run(base)
        changed = dict(base)
        changed["history_data"] = dict(base["history_data"], max_drawdown_pct=-25.0)
        flags = _run(changed)
        assert flags[_IDX["global_macro"]] is True, "global_macro 提示词不含风险信号摘要"
        assert flags[_IDX["expert_review"]] is False
        assert flags[_IDX["health_check"]] is False


class TestForceScopes:
    def test_global_force_bypasses_every_module(self, llm_cache_dir, caplog):
        base = make_inputs()
        _run(base)
        with caplog.at_level(logging.INFO, logger="invest"):
            flags = _run(base, force=True)
        assert not any(flags), f"强制重算应全部未命中：{flags}"
        summary = _precheck_lines(caplog)[-1]
        assert "重新生成（跳过缓存）" in summary
        for key in _IDX:
            assert key in summary

    def test_module_force_only_affects_target(self, llm_cache_dir):
        base = make_inputs()
        _run(base)
        flags = _run(base, force_modules=frozenset({"health_check"}))
        assert flags[_IDX["health_check"]] is False
        for key in ("global_macro", "expert_review", "penetration_deep"):
            assert flags[_IDX[key]] is True, f"{key} 不该被模块级强制牵连：{flags}"


class TestProviderKeying:
    def test_provider_switch_does_not_reuse_other_provider_cache(self, llm_cache_dir):
        """切到备链 provider → 键不同 → 必须重算（不得跨 provider 复用结论）。"""
        base = make_inputs()
        _run(base)
        routed = dict(CHAIN_CONFIG, _preferred_providers={"health_check": "probe-backup"})
        flags = _run(base, llm_config=routed)
        assert flags[_IDX["health_check"]] is False
        assert flags[_IDX["global_macro"]] is True


class TestGenerationParams:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"system_prompt_global_macro": "换成全新提示词"},
            {"output_brief_global_macro": True},
            {"model_global_macro": "another-model"},
        ],
        ids=["prompt-override", "output-brief", "model-override"],
    )
    def test_prompt_and_model_options_invalidate_key(self, llm_cache_dir, overrides):
        """自定义提示词 / 精简模式 / 模块级模型覆写都直接改写调用，必须换键。

        回归：三者不入指纹时，用户改完配置照旧命中旧缓存，报告静默复用按旧提示词
        （或旧模型）生成的结论。
        """
        base = make_inputs()
        _run(base)
        flags = _run(base, llm_config=dict(CHAIN_CONFIG, **overrides))
        assert flags[_IDX["global_macro"]] is False, f"{overrides} 必须使该模块重算"
        assert flags[_IDX["expert_review"]] is True, "其它模块不受影响"

    def test_default_params_keep_five_component_suffix(self):
        """默认参数下后缀只含五项基础参数——新增项不得改变存量缓存键。

        这里必须 patch 配置读取（而不是走隔离环境）：本用例的被测对象就是
        「按配置计算参数摘要」，读什么配置必须是确定的输入。
        """
        from src.python import config as cfg_mod
        from src.python.llm.fingerprint import compute_fingerprint
        from src.python.llm.module_fingerprint import generation_params_suffix

        module = "global_macro"
        defaults = {
            f"temperature_{module}": 0.3,
            f"max_tokens_{module}": 3072,
            f"thinking_enabled_{module}": False,
            f"thinking_budget_{module}": 6000,
            f"reasoning_effort_{module}": "low",
            f"model_{module}": None,
            f"output_brief_{module}": False,
            f"system_prompt_{module}": None,
        }
        expected = "_" + compute_fingerprint("t=0.3", "mt=3072", "th=0", "tb=6000", "te=low")
        with patch.object(cfg_mod, "get_llm_config", return_value=dict(defaults)):
            assert generation_params_suffix(module) == expected

    def test_cache_disabled_bypasses_read(self, llm_cache_dir, caplog):
        """`cache_enabled_{module}=false` → 该模块不读缓存（且不计为命中）。"""
        base = make_inputs()
        _run(base)
        disabled = dict(CHAIN_CONFIG, cache_enabled_health_check=False)
        with caplog.at_level(logging.INFO, logger="invest"):
            flags = _run(base, llm_config=disabled)
        assert flags[_IDX["health_check"]] is False
        assert flags[_IDX["global_macro"]] is True


class TestTTLExpiry:
    def test_expired_cache_is_regenerated(self, llm_cache_dir, monkeypatch):
        """TTL 过期必须重算（缓存不是永久真相）。"""
        base = make_inputs()
        _run(base)
        from src.python.llm import generators_orchestrator as go
        from src.python.llm import skeleton

        # 编排层与骨架层各持一份 TTL 读取（生产同源），测试需同时覆盖
        monkeypatch.setattr(go, "get_cache_ttl_llm", lambda _m: 0)
        monkeypatch.setattr(skeleton, "get_cache_ttl_llm", lambda _m: 0)
        flags = _run(base)
        assert not any(flags), f"TTL=0 时全部应过期：{flags}"


class TestInMemoryStateReset:
    def test_hit_survives_inmemory_state_reset(self, llm_cache_dir):
        """清掉进程内状态（日志去重/审计基线）后同输入仍命中——键只由输入决定。

        真正的跨进程重启由 `test_cache_real_config` 的磁盘键交叉比对覆盖：本用例
        不启动新进程，名字如实反映「仅内存态复位」。
        """
        base = make_inputs()
        _run(base)

        from src.python.cache import _store
        from src.python.llm import generators_orchestrator as go

        _store.reset_debug_log_state()
        go.reset_fingerprint_audit()
        flags = _run(base)
        assert all(flags), f"磁盘缓存应不受内存态复位影响：{flags}"


class TestSerialModules:
    """串行后置模块（生成后自检 / 持仓变动复盘归因）的缓存行为。"""

    _OUTPUTS = {
        "global_macro": "<p>宏观</p>",
        "expert_review": "<p>专家</p>",
        "health_check": "<p>体检</p>",
        "penetration_deep": "<p>穿透</p>",
    }

    def _self_review_calls(self) -> int:
        from src.python import config as cfg_mod
        from src.python.llm import self_review

        self_review.reset_self_review()
        conf = dict(CHAIN_CONFIG)
        with (
            patch.object(cfg_mod, "get_llm_config", return_value=conf),
            patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_DEFAULT) as mock_call,
        ):
            assert self_review.run_self_review(self._OUTPUTS, [], [], conf)
            first = mock_call.call_count
            assert self_review.run_self_review(self._OUTPUTS, [], [], conf)
            second = mock_call.call_count
        return second - first

    def test_self_review_hits_when_outputs_unchanged(self, llm_cache_dir):
        assert self._self_review_calls() == 0, "上游产出未变时自检应命中缓存"

    def test_self_review_misses_when_upstream_output_changes(self, llm_cache_dir):
        from src.python import config as cfg_mod
        from src.python.llm import self_review

        conf = dict(CHAIN_CONFIG)
        self_review.reset_self_review()
        with (
            patch.object(cfg_mod, "get_llm_config", return_value=conf),
            patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_DEFAULT) as mock_call,
        ):
            self_review.run_self_review(self._OUTPUTS, [], [], conf)
            changed = dict(self._OUTPUTS, expert_review="<p>专家（新）</p>")
            self_review.run_self_review(changed, [], [], conf)
            assert mock_call.call_count == 2, "上游正文变化时自检必须重算"

    def _holding_change_runs(self, block: str, second_block: str) -> int:
        from src.python import config as cfg_mod
        from src.python.llm.holding_change_review import run_holding_change_review

        conf = dict(CHAIN_CONFIG)
        pipeline = {"holding_change_data": {"available": True, "prompt_block": block, "llm_review": None}}
        with (
            patch.object(cfg_mod, "get_llm_config", return_value=conf),
            patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_DEFAULT) as mock_call,
        ):
            run_holding_change_review(pipeline, conf)
            pipeline["holding_change_data"]["llm_review"] = None
            pipeline["holding_change_data"]["prompt_block"] = second_block
            run_holding_change_review(pipeline, conf)
            return mock_call.call_count

    def test_holding_change_hits_when_contract_unchanged(self, llm_cache_dir):
        assert self._holding_change_runs("块A", "块A") == 1, "契约未变时归因应命中缓存"

    def test_holding_change_misses_when_block_changes(self, llm_cache_dir):
        assert self._holding_change_runs("块A", "块B") == 2, "复盘块变化时归因必须重算"
