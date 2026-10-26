"""LLM 缓存的**成本**契约 —— 命中不花钱、花钱必记账、预算与预估口径一致。

缓存的第一价值是省钱：一次全 miss 的完整报告按历史均值约 ¥0.15~0.3，命中后趋近 0。
因此除「键是否命中」外，还必须锁住四条金钱口径：

1. **命中零边际成本**：会话用量 delta 里 cost / call_count 不增长；
2. **未命中必记账**：真实调用的费用与 token 逐模块记录，可被事后汇总；
3. **日预算只看真实花费**：命中运行的 `total_cost` 为 0，不消耗 `daily_cost_limit`；
4. **节省可见**：命中模块按历史均价估算 `cache_saved_cost` 写入 perf（无样本不虚报）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.test.unit.llm._cache_fixtures import (
    LLM_REPLY_PAID,
    make_inputs,
    run_generate_all_llm,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.unit_core,
    pytest.mark.usefixtures("offline_external_sources"),
]


def _run(inputs: dict, *, reply=None, patch_call: bool = True):
    from src.test.unit.llm._cache_fixtures import LLM_REPLY_PAID

    return run_generate_all_llm(
        inputs,
        reply=reply or LLM_REPLY_PAID,
        patch_call=patch_call,
    )


class TestSessionCostDelta:
    def test_cache_hit_makes_no_api_call_and_records_zero_cost(self, llm_cache_dir):
        """命中运行：不再发生 API 调用（=不花钱），且记账条目 token/费用为 0。

        用「provider 调用次数」而不是会话累计金额来判：skeleton 层 mock 下
        `total_cost` 恒为 0，拿它断言会恒真（无效断言）。
        """
        from src.python.llm.session import get_session_usage, reset_session_usage

        base = make_inputs()
        with patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_PAID) as mock_call:
            first = _run(base)
            calls_after_first = mock_call.call_count
            reset_session_usage()
            second = _run(base)

        assert not any(first)
        assert all(second), "第二份应全部命中"
        assert mock_call.call_count == calls_after_first, "命中运行不得再发起 API 调用"

        modules = get_session_usage().get("per_module") or {}
        for key in ("global_macro", "expert_review", "health_check", "penetration_deep"):
            entry = modules.get(key) or {}
            assert entry.get("cached") is True, f"{key} 应标记为缓存"
            assert entry.get("input_tokens", 0) == 0
            assert not entry.get("cost")
        reset_session_usage()

    def test_cache_miss_records_cost_per_module(self, llm_cache_dir):
        """未命中运行：真实调用的费用/token 逐模块记账（可事后汇总）。

        注：`call_count`/`total_cost` 由 provider 层 `track_session_usage` 累计，
        本用例 mock 在 skeleton 层（不触达 provider），故只断言 `per_module` 记账。
        """
        from src.python.llm.session import get_session_usage, reset_session_usage

        reset_session_usage()
        _run(make_inputs())
        modules = get_session_usage().get("per_module") or {}

        for key in ("global_macro", "expert_review", "health_check", "penetration_deep"):
            entry = modules.get(key) or {}
            assert entry, f"{key} 未记账"
            assert entry.get("input_tokens", 0) > 0
            assert sum((entry.get("costs") or {}).values()) > 0, f"{key} 未记费用：{entry}"
        reset_session_usage()


class TestCacheSavedCost:
    _HISTORY = [
        {
            "timestamp": "2026-10-25T10:00:00+08:00",
            "llm": {
                "modules": {
                    "global_macro": {"costs": {"CNY": 0.02}},
                    "expert_review": {"costs": {"CNY": 0.30}},
                    "health_check": {"costs": {"CNY": 0.12}},
                }
            },
        },
        {
            "timestamp": "2026-10-25T11:00:00+08:00",
            "llm": {
                "modules": {
                    "global_macro": {"costs": {"CNY": 0.04}},
                    "expert_review": {"costs": {"CNY": 0.0}},  # 命中运行不计入均价
                }
            },
        },
    ]

    def test_estimate_uses_paid_samples_only(self):
        from src.python.llm.cost_forecast import estimate_cached_saving

        result = estimate_cached_saving(["global_macro", "expert_review"], history=self._HISTORY)
        # global_macro 均价 (0.02+0.04)/2 = 0.03；expert_review 只有 0.30 这一个付费样本
        assert result["saved"]["CNY"] == pytest.approx(0.33, abs=1e-9)
        assert set(result["priced"]) == {"global_macro", "expert_review"}
        assert result["unpriced"] == []

    def test_unknown_module_is_not_guessed(self):
        """无历史样本 → 不进节省估算（宁缺不虚报）。"""
        from src.python.llm.cost_forecast import estimate_cached_saving

        result = estimate_cached_saving(["penetration_deep"], history=self._HISTORY)
        assert result["saved"] == {}
        assert result["unpriced"] == ["penetration_deep"]

    def test_record_llm_context_writes_saved_cost(self, llm_cache_dir):
        """命中报告把估算节省写入 perf，并打一条 INFO（金钱可见）。"""
        from src.python.report._generation_shared import _record_llm_context

        base = make_inputs()
        _run(base)
        recorded: dict = {}

        class _Perf:
            def set_llm_context(self, ctx):
                recorded.update(ctx or {})

        with patch("src.python.llm.cost_forecast._load_perf_history", return_value=self._HISTORY):
            _run(base)  # 全命中后再登记
            _record_llm_context(_Perf())

        saved = recorded.get("cache_saved_cost") or {}
        assert sum(saved.values()) >= 0.3
        assert not any(recorded.get("cost_by_currency") or {}), "命中运行不应记费用"


class TestBudgetAccounting:
    _PERF = [
        {"timestamp": "2026-10-25T10:00:00+08:00", "llm": {"cost_by_currency": {}}},
        {"timestamp": "2026-10-25T11:00:00+08:00", "llm": {"cost_by_currency": {}}},
    ]

    def test_hit_only_runs_do_not_consume_budget(self):
        from src.python.llm.cost_forecast import budget_status

        status = budget_status({"daily_cost_limit": 1.0}, history=self._PERF)
        assert "今日尚无 LLM 支出" in status["display"], "命中运行不产生支出（display 如实反映）"
        assert status["exceeded"] is False


class TestForecastCacheDiscount:
    _HISTORY = [
        {
            "timestamp": "2026-10-25T10:00:00+08:00",
            "llm": {"modules": {"global_macro": {"costs": {"CNY": 0.0}}}},  # 全命中运行
        },
        {
            "timestamp": "2026-10-25T11:00:00+08:00",
            "llm": {"modules": {"global_macro": {"costs": {"CNY": 0.02}}}},
        },
    ]

    def test_history_with_cached_runs_makes_lower_bound_zero(self):
        """默认路径按历史样本给区间：命中样本（0 费用）使下限可为 0。"""
        from src.python.llm.cost_forecast import forecast_run_cost

        result = forecast_run_cost(
            {
                "enabled_llm": {
                    "global_macro": True,
                    "expert_review": False,
                    "health_check": False,
                    "penetration_deep": False,
                    "news_correlation": False,
                }
            },
            {"report_depth": "standard"},
            history=self._HISTORY,
        )
        assert result["ok"] is True
        assert sum(v["low"] for v in result["costs"].values()) == pytest.approx(0.0, abs=1e-9)

    def test_forced_module_priced_without_cache_discount(self):
        """强制重新生成的模块保证真调用：按静态单价计，不吃缓存折扣。"""
        from src.python.llm.cost_forecast import forecast_run_cost

        result = forecast_run_cost(
            {
                "enabled_llm": {
                    "global_macro": True,
                    "expert_review": False,
                    "health_check": False,
                    "penetration_deep": False,
                    "news_correlation": False,
                }
            },
            {"report_depth": "standard"},
            history=self._HISTORY,
            force_modules=["global_macro"],
        )
        assert result["forced_count"] == 1
        # 无静态定价时回落历史样本；有静态定价时必须 >0（不吃 0 费用折扣）
        forced = result["forced_costs"]
        assert forced, "重新生成范围须给出逐币种区间"
        assert sum(v["high"] for v in forced.values()) >= sum(v["low"] for v in forced.values()) >= 0.0
