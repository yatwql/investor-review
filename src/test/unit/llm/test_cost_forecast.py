"""LLM 事前费用预估与日预算上限单元测试（cost_forecast）。

覆盖：
  - 计划参与模块解析（enabled_llm ∩ 深度档位收窄，结构关系断言不写死清单）
  - 区间预估三态：历史实际费用 / 静态单价兜底 / 混合与无法定价降级
  - 辩论模式费用口径（标准样本 ×3、辩论三键并入 expert_review）
  - 日预算：上限解析（非法归 0）、今日费用按日期求和、超限边界
  - 摘要行分支（预估失败不阻塞、预算开/关文案）
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.python.core.registry import get_llm_module_names
from src.python.llm import cost_forecast as cf
from src.python.llm.cost_forecast import (
    budget_status,
    daily_cost_limit,
    forecast_run_cost,
    forecast_summary_lines,
    resolve_planned_modules,
    today_llm_cost,
)
from src.python.llm.pricing import PRICING_MERGED, compute_cost_value, reload_pricing

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


def _enabled_only(*targets: str) -> dict:
    """构造 enabled_llm：仅 targets 开启（键空间取自注册表，不写死清单）。"""
    return {k: (k in targets) for k in get_llm_module_names()}


def _known_model() -> str:
    """取定价表中一个真实模型键（定价表演进不改测试）。

    选**显示币种**（缺省 CNY）计价的模型：预估的历史样本与模型币种必须一致，
    否则同币种无样本会按静态兜底（跨币种样本不混算）。
    """
    from src.python.llm.pricing import PRICING_CURRENCY, model_currency

    reload_pricing()
    assert PRICING_MERGED, "定价表不应为空（缺省定价随代码发布）"
    return next(m for m in PRICING_MERGED if model_currency(m) == PRICING_CURRENCY)


def _rec(ts: str, total: float, modules: dict) -> dict:
    return {"timestamp": ts, "llm": {"cost_by_currency": {"CNY": total}, "modules": modules}}


def _total_forced(fc: dict, key: str = "low") -> float:
    """逐币种「重新生成范围内」区间求和（单币种用例）。"""
    return sum(float(v[key]) for v in (fc.get("forced_costs") or {}).values())


def _total(fc: dict, key: str = "low") -> float:
    """逐币种区间求和（用例均为单币种场景；多币种分组另有用例覆盖）。"""
    return sum(float(v[key]) for v in fc["costs"].values())


class TestResolvePlannedModules:
    """计划参与模块 = 可见标准模块 ∩ enabled_llm ∩ 深度档位上界。"""

    def test_enabled_filter_is_structural(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro", "expert_review")}
        planned = resolve_planned_modules(cfg, {"llm_report_depth": "standard"})
        assert set(planned) == {"global_macro", "expert_review"}
        assert planned == sorted(planned), "返回稳定有序（可断言可复现）"

    def test_brief_depth_narrows_to_profile_ceiling(self) -> None:
        from src.python.llm.depth_profile import DEPTH_PROFILES

        cfg = {"enabled_llm": _enabled_only("global_macro", "expert_review", "health_check")}
        planned = set(resolve_planned_modules(cfg, {"llm_report_depth": "brief"}))
        ceiling = DEPTH_PROFILES["brief"].max_modules
        assert planned <= ceiling, "brief 档不得超过其上界"
        assert planned == {"global_macro"}, "brief 档 = 上界 ∩ 已开模块"
        assert "expert_review" not in planned, "brief 档上界外模块不得参与"

    def test_depth_cannot_open_disabled_module(self) -> None:
        cfg = {"enabled_llm": _enabled_only()}  # 全关
        planned = resolve_planned_modules(cfg, {"llm_report_depth": "deep"})
        assert planned == [], "档位只收窄，不得打开已关模块"

    def test_empty_config_returns_empty(self) -> None:
        assert resolve_planned_modules({}, None) == []


class TestForecastHistoryBasis:
    """历史实际费用优先：区间 = 逐模块样本 min~max 求和。"""

    def test_full_history_coverage(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro", "expert_review")}
        history = [
            _rec("2026-01-01T10:00:00", 0.4, {"global_macro": {"cost": 0.1}, "expert_review": {"cost": 0.3}}),
            _rec("2026-01-02T10:00:00", 0.5, {"global_macro": {"cost": 0.2}, "expert_review": {"cost": 0.3}}),
        ]
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=history)
        assert fc["ok"] is True
        assert fc["basis"] == "history:2"
        assert fc["history_runs"] == 2
        assert _total(fc, "low") == pytest.approx(0.1 + 0.3)
        assert _total(fc, "high") == pytest.approx(0.2 + 0.3)
        assert fc["unpriced"] == []
        assert fc["detail"]["global_macro"]["samples"] == 2

    def test_partial_history_yields_mixed_basis(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro", "expert_review"), "model": _known_model()}
        history = [_rec("2026-01-01T10:00:00", 0.1, {"global_macro": {"cost": 0.1}})]
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=history)
        assert fc["ok"] is True
        assert fc["basis"] == "mixed"
        assert fc["detail"]["global_macro"]["basis"] == "history"
        assert fc["detail"]["expert_review"]["basis"] == "static"
        assert _total(fc, "high") >= _total(fc, "low") > 0

    def test_no_llm_records_yields_static_basis(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro"), "model": _known_model()}
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[{"timestamp": "x"}])
        assert fc["ok"] is True
        assert fc["basis"] == "static"
        assert fc["history_runs"] == 0


class TestForecastStaticFallback:
    """静态兜底 = 输入/输出包络 × 模型单价（数学与 pricing 单源一致）。"""

    def test_static_range_matches_envelope_math(self) -> None:
        from src.python.llm.cost_forecast import _STATIC_IN_HIGH, _STATIC_IN_LOW, _STATIC_OUT_LOW

        model = _known_model()
        cfg = {"enabled_llm": _enabled_only("global_macro"), "model": model, "max_tokens_global_macro": 3072}
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[])
        assert fc["ok"] is True
        expected_low = compute_cost_value(model, _STATIC_IN_LOW, _STATIC_OUT_LOW)
        expected_high = compute_cost_value(model, _STATIC_IN_HIGH, 3072)
        assert _total(fc, "low") == pytest.approx(round(expected_low, 6))
        assert _total(fc, "high") == pytest.approx(round(expected_high, 6))
        assert expected_high > expected_low

    def test_max_tokens_fallback_when_unconfigured(self) -> None:
        from src.python.llm.cost_forecast import _STATIC_IN_HIGH, _STATIC_OUT_FALLBACK

        model = _known_model()
        cfg = {"enabled_llm": _enabled_only("global_macro"), "model": model}
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[])
        assert _total(fc, "high") == pytest.approx(
            round(compute_cost_value(model, _STATIC_IN_HIGH, _STATIC_OUT_FALLBACK), 6)
        )

    def test_unknown_model_without_history_fails_nonblocking(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro"), "model": "no-such-model-xyz"}
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[])
        assert fc["ok"] is False
        assert fc["reason"], "失败须给出可读原因（渠道层据此跳过确认）"
        lines = forecast_summary_lines(fc, budget_status(cfg, []))
        assert any("不可用" in ln for ln in lines)

    def test_partial_unpriced_stays_ok_with_reason(self) -> None:
        cfg = {"enabled_llm": _enabled_only("global_macro", "expert_review"), "model": "no-such-model-xyz"}
        history = [_rec("2026-01-01T10:00:00", 0.1, {"global_macro": {"cost": 0.1}})]
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=history)
        assert fc["ok"] is True, "有历史覆盖时仍给可用区间"
        assert fc["unpriced"] == ["expert_review"]
        assert fc["reason"] and "expert_review" in fc["reason"]

    def test_no_planned_modules_is_zero_ok(self) -> None:
        fc = forecast_run_cost({"enabled_llm": _enabled_only()}, {"llm_report_depth": "standard"}, history=[])
        assert fc["ok"] is True
        assert fc["module_count"] == 0
        assert fc["basis"] == "no-modules"
        assert _total(fc, "low") == _total(fc, "high") == 0.0


class TestForecastDebateCaliber:
    """辩论模式：expert_review 静态 ×3；历史标准样本 ×3、辩论三键并入求和。"""

    def test_static_expert_review_multiplied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.python.llm.cost_forecast import _DEBATE_CALL_MULT, _STATIC_IN_HIGH, _STATIC_OUT_FALLBACK

        model = _known_model()
        monkeypatch.setattr(cf, "is_feature_enabled_for_debate", lambda: True)
        cfg = {"enabled_llm": _enabled_only("expert_review"), "model": model}
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[])
        base = compute_cost_value(model, _STATIC_IN_HIGH, _STATIC_OUT_FALLBACK)
        assert _total(fc, "high") == pytest.approx(round(base * _DEBATE_CALL_MULT, 6))

    def test_history_standard_sample_scaled_and_debate_run_merged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.python.llm.cost_forecast import _DEBATE_CALL_MULT

        monkeypatch.setattr(cf, "is_feature_enabled_for_debate", lambda: True)
        cfg = {"enabled_llm": _enabled_only("expert_review"), "model": "no-such-model-xyz"}
        history = [
            _rec("2026-01-01T10:00:00", 0.4, {"expert_review": {"cost": 0.1}}),
            _rec(
                "2026-01-02T10:00:00",
                0.23,
                {
                    "expert_review": {"cost": 0.1},
                    "debate_pro": {"cost": 0.05},
                    "debate_con": {"cost": 0.05},
                    "debate_synthesis": {"cost": 0.03},
                },
            ),
        ]
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=history)
        assert fc["ok"] is True
        assert _total(fc, "low") == pytest.approx(0.23)
        assert _total(fc, "high") == pytest.approx(round(0.1 * _DEBATE_CALL_MULT, 6))

    def test_debate_off_excludes_hidden_keys(self) -> None:
        cfg = {"enabled_llm": _enabled_only("expert_review"), "model": "no-such-model-xyz"}
        history = [
            _rec(
                "2026-01-01T10:00:00",
                0.5,
                {"expert_review": {"cost": 0.4}, "debate_pro": {"cost": 0.1}},
            ),
        ]
        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=history)
        assert fc["ok"] is True
        assert _total(fc, "low") == _total(fc, "high") == pytest.approx(0.4), "辩论特征关闭时不得把辩论键计入计划模块"


class TestBudget:
    """日预算：上限解析 / 今日费用 / 超限边界。"""

    def test_limit_parsing_normalizes_invalid(self) -> None:
        assert daily_cost_limit({"daily_cost_limit": 1.5}) == 1.5
        assert daily_cost_limit({"daily_cost_limit": -3}) == 0.0, "负值归 0（未启用）"
        assert daily_cost_limit({"daily_cost_limit": "abc"}) == 0.0, "非法值归 0"
        assert daily_cost_limit({}) == 0.0, "缺省 = 未启用"

    def test_today_cost_sums_only_local_date(self) -> None:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        history = [
            _rec(f"{today}T09:00:00", 0.25, {"global_macro": {"cost": 0.25}}),
            _rec(f"{today}T18:30:00", 0.5, {"expert_review": {"cost": 0.5}}),
            _rec(f"{yesterday}T10:00:00", 9.9, {"expert_review": {"cost": 9.9}}),
            {"timestamp": f"{today}T10:00:00"},  # 无 llm 段
        ]
        assert today_llm_cost(history)["CNY"] == pytest.approx(0.75)

    def test_budget_status_exceeded_boundary(self) -> None:
        today = date.today().isoformat()
        cfg = {"daily_cost_limit": 0.5}
        st = budget_status(cfg, [_rec(f"{today}T10:00:00", 0.5, {})])
        assert st["enabled"] is True
        assert st["exceeded"] is True, "达到上限即视为超限（>=）"
        st2 = budget_status({"daily_cost_limit": 0.5}, [_rec(f"{today}T10:00:00", 0.49, {})])
        assert st2["exceeded"] is False
        st3 = budget_status({"daily_cost_limit": 0}, [_rec(f"{today}T10:00:00", 99.0, {})])
        assert st3["enabled"] is False
        assert st3["exceeded"] is False, "未设上限永不超限"

    def test_budget_status_shape(self) -> None:
        st = budget_status({"daily_cost_limit": 2}, [])
        assert {"enabled", "limit", "currency", "spent", "spent_converted", "exceeded", "display"} <= set(st)
        assert st["limit"] == 2.0, "上限为本币单个数字"
        assert st["spent"] == {}, "无历史 = 今日零支出"
        assert st["display"], "须给出可上屏的预算摘要"


class TestSummaryLines:
    """摘要行分支（渠道层加前缀直接上屏的纯文本）。"""

    def test_ok_history_line_mentions_dynamic_run_count(self) -> None:
        fc = {
            "ok": True,
            "module_count": 2,
            "costs": {"CNY": {"low": 0.1, "high": 0.2}},
            "cost_display": "¥0.1000 ~ ¥0.2000",
            "basis": "history:7",
            "reason": None,
        }
        lines = forecast_summary_lines(fc)
        assert any("0.1000" in ln and "0.2000" in ln for ln in lines)
        assert any("近 7 次运行实际费用" in ln for ln in lines), "依据行取自 basis 实际值"

    def test_no_modules_line(self) -> None:
        fc = {"ok": True, "module_count": 0, "basis": "no-modules", "symbol": "¥", "reason": None}
        lines = forecast_summary_lines(fc)
        assert any("无 LLM 模块参与" in ln for ln in lines)

    def test_budget_lines_branch(self) -> None:
        fc = {
            "ok": True,
            "module_count": 1,
            "costs": {"CNY": {"low": 0.1, "high": 0.2}},
            "cost_display": "¥0.1000 ~ ¥0.2000",
            "basis": "static",
            "reason": None,
        }
        on = {
            "enabled": True,
            "limits": {"CNY": 1.0},
            "spent": {"CNY": 1.2},
            "exceeded": True,
            "display": "已花 ¥1.2000；预算 ¥1.2000 / ¥1.0000（已达上限）",
        }
        off = {"enabled": False, "limits": {}, "spent": {"CNY": 0.3}, "exceeded": False, "display": "已花 ¥0.3000"}
        assert any("已达上限" in ln for ln in forecast_summary_lines(fc, on))
        assert any("未设日预算上限" in ln for ln in forecast_summary_lines(fc, off))


class TestForceScopeForecast:
    """重新生成范围感知：选模块路径与默认路径不再给同一区间（范围内模块静态口径）。"""

    @staticmethod
    def _cfg():
        return {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "k",
            "base_url": "",
            "temperature": 0.2,
            "timeout": 30,
            "max_retries": 2,
            "enabled": True,
            "enabled_llm": [],
        }

    @staticmethod
    def _hist():
        # perf 历史真实结构：rec["llm"]["modules"][键]["cost"]
        return [
            {
                "run_id": "r1",
                "llm": {
                    "modules": {
                        "expert_review": {"ok": True, "cost": 0.5, "model": "gpt-4o", "currency": "USD"},
                        "global_macro": {"ok": True, "cost": 0.3, "model": "gpt-4o", "currency": "USD"},
                    }
                },
            }
        ]

    def test_default_path_has_no_forced_breakdown(self):
        fc = forecast_run_cost(self._cfg(), self._cfg(), history=self._hist())
        assert fc["force_scope"] == []
        assert fc["forced_count"] == 0
        lines = forecast_summary_lines(fc)
        assert not any("重新生成" in ln for ln in lines), "默认路径无重新生成拆行"

    def test_module_scope_prices_forced_module_at_static(self):
        fc = forecast_run_cost(self._cfg(), self._cfg(), history=self._hist(), force_modules=["expert_review"])
        assert fc["force_scope"] == ["expert_review"]
        assert fc["detail"]["expert_review"]["basis"] == "static", "范围内模块按静态口径（历史样本含缓存折扣不适用）"
        assert fc["forced_count"] == 1
        assert _total_forced(fc, "low") > 0 and _total_forced(fc, "high") >= _total_forced(fc, "low")
        assert any("重新生成" in ln for ln in forecast_summary_lines(fc)), "重新生成拆行须上屏"

    def test_unscoped_modules_keep_history_caliber(self):
        fc = forecast_run_cost(self._cfg(), self._cfg(), history=self._hist(), force_modules=["expert_review"])
        other = fc["detail"]["global_macro"]
        assert other["basis"] == "history", "范围外模块维持历史实际费用口径"
        assert other["samples"] == 1

    def test_full_force_covers_planned_forceable(self):
        fc = forecast_run_cost(self._cfg(), self._cfg(), history=self._hist(), force_llm=True)
        assert fc["force_scope"], "全量重新生成须列出范围"
        assert fc["forced_count"] == len(set(fc["force_scope"]) & set(fc["modules"]))
        assert fc["forced_count"] == len(fc["modules"]), "计划模块均可重新生成时全覆盖"

    def test_invalid_force_module_raises(self):
        with pytest.raises(ValueError):
            forecast_run_cost(self._cfg(), self._cfg(), history=self._hist(), force_modules=["market_overview"])
