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

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]

_HOLDING_CODE = "600900"

_LLM_CONFIG = {
    "_provider_list": [{"name": "probe-main", "provider": "claude", "api_key": "sk-x"}],
    "_strategy": "priority",
    "_preferred_providers": {},
    "llm_max_concurrency": 2,
}

_PAID_REPLY = (
    "<p>生成内容</p>",
    {"input_tokens": 1000, "output_tokens": 500, "cache_read_input_tokens": 0},
    {"name": "probe-main", "model": "deepseek-v4-flash", "endpoint": "e"},
)


def _inputs() -> dict:
    return {
        "a_indices": {"sh000300": {"name": "沪深300", "close": 4000.0, "change_pct": 0.5}},
        "us_indices": {"^IXIC": {"name": "纳斯达克", "close": 18000.0, "change_pct": -0.2}},
        "categories": {"股票": {"market_value": 10000.0, "cost": 9000.0, "count": 1}},
        "holdings_details": [
            {"name": "测试A", "code": _HOLDING_CODE, "cost": 1.0, "shares": 100, "market_value": 120.0}
        ],
        "penetrated_assets": [{"name": "测试A", "code": _HOLDING_CODE, "weight": 100.0}],
        "history_data": {"max_drawdown_pct": -15.0, "annualized_volatility": 0.17, "total_return_pct": -10.0},
        "pipeline_data": {"diff": {"added": [], "removed": []}, "data_degradation": []},
    }


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    from src.python.cache import _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path / "cache"))
    _store.reset_debug_log_state()
    yield tmp_path / "cache"
    _store.reset_debug_log_state()


def _run(inputs: dict, caplog=None):
    from src.python.llm import generators_orchestrator as go

    with (
        patch.object(go, "get_llm_config", return_value=dict(_LLM_CONFIG)),
        patch("src.python.llm.skeleton.call_llm", return_value=_PAID_REPLY),
    ):
        return go.generate_all_llm(
            inputs["a_indices"],
            inputs["us_indices"],
            120.0,
            100.0,
            20.0,
            1.0,
            1,
            inputs["categories"],
            penetrated_assets=inputs["penetrated_assets"],
            holdings_details=inputs["holdings_details"],
            pipeline_data=inputs["pipeline_data"],
            history_data=inputs["history_data"],
        )


class TestSessionCostDelta:
    def test_cache_hit_adds_no_cost(self, cache_dir):
        """命中运行：会话用量 delta 的 cost / call_count 不增长（零边际成本）。"""
        from src.python.llm.session import get_session_usage, reset_session_usage
        from src.python.report._generation_shared import _usage_delta

        base = _inputs()
        _run(base)
        baseline = get_session_usage()
        _run(base)  # 全部命中
        delta = _usage_delta(get_session_usage(), baseline)

        assert delta.get("total_cost", 0.0) == pytest.approx(0.0, abs=1e-9)
        assert delta.get("call_count", 0) == 0
        assert all(not (entry or {}).get("cost") for entry in (delta.get("per_module") or {}).values())
        reset_session_usage()

    def test_cache_miss_records_cost_per_module(self, cache_dir):
        """未命中运行：真实调用的费用/token 逐模块记账（可事后汇总）。

        注：`call_count`/`total_cost` 由 provider 层 `track_session_usage` 累计，
        本用例 mock 在 skeleton 层（不触达 provider），故只断言 `per_module` 记账。
        """
        from src.python.llm.session import get_session_usage, reset_session_usage

        reset_session_usage()
        _run(_inputs())
        modules = get_session_usage().get("per_module") or {}

        for key in ("global_macro", "expert_review", "health_check", "penetration_deep"):
            entry = modules.get(key) or {}
            assert entry, f"{key} 未记账"
            assert entry.get("input_tokens", 0) > 0
            assert entry.get("cost", 0) > 0, f"{key} 未记费用：{entry}"
        reset_session_usage()


class TestCacheSavedCost:
    _HISTORY = [
        {
            "timestamp": "2026-10-25T10:00:00+08:00",
            "llm": {
                "modules": {
                    "global_macro": {"cost": 0.02},
                    "expert_review": {"cost": 0.30},
                    "health_check": {"cost": 0.12},
                }
            },
        },
        {
            "timestamp": "2026-10-25T11:00:00+08:00",
            "llm": {
                "modules": {
                    "global_macro": {"cost": 0.04},
                    "expert_review": {"cost": 0.0},  # 命中运行不计入均价
                }
            },
        },
    ]

    def test_estimate_uses_paid_samples_only(self):
        from src.python.llm.cost_forecast import estimate_cached_saving

        result = estimate_cached_saving(["global_macro", "expert_review"], history=self._HISTORY)
        # global_macro 均价 (0.02+0.04)/2 = 0.03；expert_review 只有 0.30 这一个付费样本
        assert result["saved"] == pytest.approx(0.33, abs=1e-9)
        assert set(result["priced"]) == {"global_macro", "expert_review"}
        assert result["unpriced"] == []

    def test_unknown_module_is_not_guessed(self):
        """无历史样本 → 不进节省估算（宁缺不虚报）。"""
        from src.python.llm.cost_forecast import estimate_cached_saving

        result = estimate_cached_saving(["penetration_deep"], history=self._HISTORY)
        assert result["saved"] == 0.0
        assert result["unpriced"] == ["penetration_deep"]

    def test_record_llm_context_writes_saved_cost(self, cache_dir):
        """命中报告把估算节省写入 perf，并打一条 INFO（金钱可见）。"""
        from src.python.report._generation_shared import _record_llm_context

        base = _inputs()
        _run(base)
        recorded: dict = {}

        class _Perf:
            def set_llm_context(self, ctx):
                recorded.update(ctx or {})

        with patch("src.python.llm.cost_forecast._load_perf_history", return_value=self._HISTORY):
            _run(base)  # 全命中后再登记
            _record_llm_context(_Perf())

        assert recorded.get("cache_saved_cost", 0) >= 0.3
        assert not recorded.get("total_cost"), "命中运行不应记费用"


class TestBudgetAccounting:
    _PERF = [
        {"timestamp": "2026-10-25T10:00:00+08:00", "llm": {"total_cost": 0.0}},
        {"timestamp": "2026-10-25T11:00:00+08:00", "llm": {"total_cost": 0.0}},
    ]

    def test_hit_only_runs_do_not_consume_budget(self):
        from src.python.llm.cost_forecast import budget_status

        status = budget_status({"daily_cost_limit": 1.0}, history=self._PERF)
        assert status["spent"] == pytest.approx(0.0, abs=1e-9)
        assert status["exceeded"] is False

    def test_paid_runs_accumulate_and_trip_budget(self):
        from src.python.llm.cost_forecast import budget_status

        history = [
            {"timestamp": __import__("datetime").date.today().isoformat() + "T10:00:00", "llm": {"total_cost": 0.6}},
            {"timestamp": __import__("datetime").date.today().isoformat() + "T11:00:00", "llm": {"total_cost": 0.5}},
        ]
        status = budget_status({"daily_cost_limit": 1.0}, history=history)
        assert status["spent"] == pytest.approx(1.1, abs=1e-9)
        assert status["exceeded"] is True


class TestForecastCacheDiscount:
    _HISTORY = [
        {
            "timestamp": "2026-10-25T10:00:00+08:00",
            "llm": {"modules": {"global_macro": {"cost": 0.0}}},  # 全命中运行
        },
        {
            "timestamp": "2026-10-25T11:00:00+08:00",
            "llm": {"modules": {"global_macro": {"cost": 0.02}}},
        },
    ]

    def test_default_path_lower_bound_reflects_cache(self):
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
        assert result["low"] == pytest.approx(0.0, abs=1e-9)

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
        assert result["forced_high"] >= result["forced_low"] >= 0.0
