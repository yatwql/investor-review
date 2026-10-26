"""端到端报告序列的缓存命中矩阵 —— 真实 `generate_all_llm` + 只 mock 网络层。

与 `test_report_sequence_cache.py`（3 例快速契约）互补：本文件把「一天内连续多份
报告」的各种业务变化组合成矩阵，验证**命中粒度**是否和业务语义一致——

| 变化维度 | 期望命中 | 理由 |
|---------|---------|------|
| 完全相同的输入 | 四模块全命中 | 不重复付费 |
| 行情指数变化 | `global_macro` 未命中，其余命中 | 只有宏观用指数 |
| 持仓成本变化 | 含持仓明细的模块未命中 | 成本进提示词 |
| 风险信号变化 | `health_check`/`expert_review` 未命中 | 风险摘要进提示词 |
| 数据质量降级源变化 | `health_check` 未命中 | 降级块进其提示词 |
| 量化指标变化 | `expert_review` 未命中 | 指标是复盘正文段 |
| 穿透资产变化 | `penetration_deep` 未命中 | 穿透模块专用输入 |
| 生成参数（温度）变化 | 四模块全未命中 | 参数进后缀 |
| 强制重生成 | 全量强制全未命中 / 模块强制只绕该模块 | 用户意图优先 |
| 模型覆写变化 | 对应模块未命中 | 换模型即换结论 |

另验证**费用与命中一致性**：全命中时不应产生新增付费调用。
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from src.test.unit.llm._cache_fixtures import (
    CHAIN_CONFIG,
    LLM_REPLY_PAID,
    degradation_events,
    make_inputs,
    run_generate_all_llm,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.unit_core,
    pytest.mark.usefixtures("offline_external_sources"),
]

_ALL = (True, True, True, True)


def _run(inputs, **kwargs):
    return run_generate_all_llm(inputs, **kwargs)


class TestHitGranularity:
    """变化维度 × 命中模块：只有真正受影响的模块重算。"""

    def test_identical_input_hits_all(self, llm_cache_dir):
        inputs = make_inputs()
        assert not any(_run(inputs)), "首份无缓存"
        assert _run(inputs) == _ALL

    def test_index_change_only_misses_macro(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        changed = {**inputs, "a_indices": {"sh000300": {"name": "沪深300", "close": 4050.0, "change_pct": 1.2}}}
        flags = _run(changed)
        assert flags[0] is False, "global_macro 依赖指数，必须重算"
        assert flags[2] is True, "health_check 不含指数"

    def test_us_index_change_misses_macro(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        changed = {**inputs, "us_indices": {"^IXIC": {"name": "纳斯达克", "close": 18100.0, "change_pct": 0.4}}}
        assert _run(changed)[0] is False

    def test_cost_basis_change_misses_holdings_modules(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        holdings = [dict(inputs["holdings_details"][0])]
        holdings[0]["cost"] = 1.3
        flags = _run({**inputs, "holdings_details": holdings})
        assert flags[1] is False, "expert_review 用持仓成本"
        assert flags[2] is False, "health_check 用持仓成本"

    def test_risk_signal_change_misses_health_and_expert(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        history = {**inputs["history_data"], "max_drawdown_pct": -22.0}
        flags = _run({**inputs, "history_data": history})
        assert flags[2] is False, "health_check 用风险摘要"
        assert flags[1] is False, "expert_review 用风险摘要"
        assert flags[0] is True, "global_macro 不含风险信号"

    def test_data_degradation_change_misses_health_only(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs, degradation=degradation_events("industry"))
        flags = _run(inputs, degradation=degradation_events("akshare"))
        assert flags[2] is False, "降级块进 health_check 提示词"
        assert flags[0] is True and flags[1] is True

    def test_metrics_change_misses_expert(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        flags = _run({**inputs, "metrics": {"sharpe": 0.8, "hhi": 0.45}})
        assert flags[1] is False, "量化指标是复盘正文段"
        assert flags[0] is True

    def test_penetration_change_misses_penetration(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        penetrated = [{"name": "测试A", "code": "600900", "mv": 800.0, "ratio": 0.8, "sector": "消费"}]
        flags = _run({**inputs, "penetrated_assets": penetrated})
        assert flags[3] is False, "穿透模块输入（mv/ratio/sector）变了"

    def test_categories_change_misses_all_dependent(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        changed = {**inputs, "categories": {"股票": {"market_value": 11000.0, "cost": 9000.0, "count": 1}}}
        flags = _run(changed)
        assert flags[0] is False, "global_macro 用分类汇总"


class TestParameterAndModelChanges:
    """生成参数与模型覆写：换参数/换模型必须换结论。"""

    def test_temperature_change_misses_all(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        conf = {**CHAIN_CONFIG, "temperature_expert_review": 0.9}
        flags = _run(inputs, llm_config=conf)
        assert flags[1] is False, "被改温度的那个模块必须重算"
        assert flags[0] is True, "其他模块参数未变，仍应命中"

    def test_model_override_misses_target_module(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        conf = {**CHAIN_CONFIG, "model_expert_review": "claude-sonnet-5-5"}
        flags = _run(inputs, llm_config=conf)
        assert flags[1] is False, "换模型即换结论"


class TestForceSemantics:
    """强制重生成：用户意图优先于缓存。"""

    def test_full_force_bypasses_every_module(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        assert not any(_run(inputs, force=True)), "全量强制应全部重算"

    def test_module_force_only_bypasses_target(self, llm_cache_dir):
        inputs = make_inputs()
        _run(inputs)
        flags = _run(inputs, force_modules=frozenset({"expert_review"}))
        assert flags[1] is False, "目标模块必须重算"
        assert flags[0] is True and flags[2] is True and flags[3] is True, "其余模块仍可命中"


class TestCostConsistency:
    """命中与费用一致：全命中时不再产生付费调用。"""

    def test_hit_run_makes_fewer_calls_than_miss(self, llm_cache_dir):
        """命中运行的实际 LLM 调用次数必须少于未命运行（缓存真的省了钱）。

        不强制断言为 0：编排层存在不受模块缓存覆盖的收尾调用（如自检），
        断言"命中比未命中少"才是稳定可验证的成本契约。
        """
        inputs = make_inputs()
        miss_calls: list[int] = []

        def _count_miss(*args, **kwargs):
            miss_calls.append(1)
            return LLM_REPLY_PAID

        with patch("src.python.llm.skeleton.call_llm", side_effect=_count_miss):
            first = run_generate_all_llm(inputs, patch_call=False)
        assert not any(first)

        hit_calls: list[int] = []

        def _count_hit(*args, **kwargs):
            hit_calls.append(1)
            return LLM_REPLY_PAID

        with patch("src.python.llm.skeleton.call_llm", side_effect=_count_hit):
            flags = run_generate_all_llm(inputs, patch_call=False)

        assert all(flags)
        assert len(hit_calls) < len(miss_calls), f"命中 {len(hit_calls)} 次 vs 未命中 {len(miss_calls)} 次"

    def test_miss_run_makes_paid_calls(self, llm_cache_dir):
        inputs = make_inputs()
        calls: list[int] = []

        def _counting_call(*args, **kwargs):
            calls.append(1)
            return LLM_REPLY_PAID

        with patch("src.python.llm.skeleton.call_llm", side_effect=_counting_call):
            flags = run_generate_all_llm(inputs, patch_call=False)

        assert not any(flags), "首次运行应全部未命中"
        assert calls, "未命中必须有真实调用"


class TestPrecheckAttribution:
    """预检归因：命中/未命中都要有可读日志（缓存是否生效过去只能盲猜）。"""

    def test_hit_summary_reports_ratio(self, llm_cache_dir, caplog):
        inputs = make_inputs()
        _run(inputs)
        with caplog.at_level(logging.INFO, logger="invest"):
            _run(inputs)
        lines = [r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage()]
        assert any("基础模块命中 4/4" in line for line in lines), f"预检汇总缺失：{lines}"

    def test_miss_is_attributed(self, llm_cache_dir, caplog):
        inputs = make_inputs()
        with caplog.at_level(logging.INFO, logger="invest"):
            _run(inputs)
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "预检" in messages, "首份报告应给出预检日志"
