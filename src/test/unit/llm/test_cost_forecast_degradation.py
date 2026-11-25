"""事前费用预估的降级与容错分支单元测试（cost_forecast）。

锁住的契约：
  - 配置层/历史账本读取失败 → 按空配置、无历史继续（预估失败永不阻塞生成）
  - 生效模型三级回落：`model_<模块>` 覆写 → 多链首链 → 配置顶层默认；多链解析
    异常同样回落到顶层默认
  - 历史记录形状容错：缺 `modules`、modules 为空、明细项非 dict 一律跳过，
    且只有 `modules` 非空的记录计入「参与样本的运行数」
  - 辩论特性开关读取失败按关闭处理（费用按静态口径兜底，安全方向）
  - 强制重算范围内的模块既无单价又无历史样本 → 计入 unpriced，全部无法定价时
    `ok=False` 且不计入强制费用区间
  - 摘要行：依据串为空回落「未知」，部分模块无法定价时追加说明行
"""

from __future__ import annotations

import pytest

from src.python.core.registry import get_llm_module_names
from src.python.llm import cost_forecast as cf
from src.python.llm.cost_forecast import (
    estimate_cached_saving,
    forecast_run_cost,
    forecast_summary_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_UNKNOWN_MODEL = "no-such-pricing-model-xyz"


def _enabled_only(*targets: str) -> dict:
    return {k: (k in targets) for k in get_llm_module_names()}


class TestConfigReadFailures:
    """配置/历史不可读属降级路径：按空值继续，绝不向上抛。"""

    def test_llm_config_read_failure_falls_back_to_empty_config(self, monkeypatch):
        def _raise():
            raise RuntimeError("配置不可读")

        monkeypatch.setattr("src.python.config.get_llm_config", _raise)

        assert cf._get_llm_config() == {}

    def test_perf_history_read_failure_falls_back_to_no_history(self, monkeypatch):
        def _raise():
            raise RuntimeError("历史不可读")

        monkeypatch.setattr("src.python.core.perf.load_history", _raise)

        assert cf._load_perf_history() == []


class TestModuleModelResolution:
    """生效模型三级回落，前级命中即不再解析后级。"""

    def test_module_override_wins_without_resolving_chain(self, monkeypatch):
        def _boom(*_a, **_k):
            raise AssertionError("有模块级覆写时不应解析多链")

        monkeypatch.setattr("src.python.llm.api._resolve_first_provider_model_endpoint", _boom)

        assert cf._module_model({"model": "top-model", "model_global_macro": "  module-model "}, "global_macro") == (
            "module-model"
        )

    def test_chain_first_model_used_without_module_override(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.llm.api._resolve_first_provider_model_endpoint",
            lambda *_a, **_k: ("chain-model", None),
        )

        assert cf._module_model({"model": "top-model"}, "global_macro") == "chain-model"

    def test_chain_resolution_failure_falls_back_to_top_default(self, monkeypatch):
        def _raise(*_a, **_k):
            raise RuntimeError("链路不可解析")

        monkeypatch.setattr("src.python.llm.api._resolve_first_provider_model_endpoint", _raise)

        assert cf._module_model({"model": "top-model"}, "global_macro") == "top-model"


class TestHistoryShapeTolerance:
    """手工编辑/早期版本的 perf 记录形状不齐时按「无该条样本」处理。"""

    def test_only_records_with_non_empty_modules_count_as_samples(self):
        records = [
            {"llm": "not-a-dict"},
            {"llm": {"modules": {}}},
            {"llm": {"modules": None}},
            {"llm": {"modules": {"global_macro": "not-a-dict"}}},
            {"llm": {"modules": {"global_macro": {"costs": {"CNY": 0.25}}}}},
        ]

        samples, runs_used = cf._history_module_costs(records, False)

        assert runs_used == 2, "只有 modules 非空 dict 的记录计入参与样本的运行数"
        assert samples["global_macro"]["CNY"] == pytest.approx([0.25]), "非 dict 明细项不得产出样本"


class TestDebateFlagDegradation:
    def test_feature_read_failure_treated_as_disabled(self, monkeypatch):
        def _raise(*_a, **_k):
            raise RuntimeError("特性读取失败")

        monkeypatch.setattr("src.python.config.features.is_feature_enabled", _raise)

        assert cf.is_feature_enabled_for_debate() is False


class TestForcedScopeUnpriced:
    def test_forced_module_without_price_or_samples_is_unpriced(self, monkeypatch):
        monkeypatch.setattr(cf, "is_feature_enabled_for_debate", lambda: False)
        cfg = {"enabled_llm": _enabled_only("global_macro"), "model": _UNKNOWN_MODEL}

        fc = forecast_run_cost(cfg, {"llm_report_depth": "standard"}, history=[], force_modules=["global_macro"])

        assert fc["ok"] is False, "全部模块无法定价时隔 → 预估不可用（渠道层跳过确认）"
        assert fc["unpriced"] == ["global_macro"]
        assert fc["forced_count"] == 0, "无法定价的强制模块不得计入强制费用区间"
        assert fc["reason"], "预估不可用必须给出可展示的原因"


class TestCachedSavingEmptyInput:
    def test_no_module_keys_returns_empty_saving_without_reading_history(self):
        assert estimate_cached_saving([]) == {
            "saved": {},
            "saved_display": "-",
            "priced": [],
            "unpriced": [],
        }


class TestSummaryLineFallbacks:
    def test_unknown_basis_falls_back_to_unknown_label(self):
        lines = forecast_summary_lines({"ok": True, "module_count": 1, "cost_display": "", "basis": ""})

        assert any("依据：未知" in line for line in lines), "依据串缺失时摘要须给可读占位而非空"

    def test_partial_unpriced_reason_rendered_as_note_line(self):
        lines = forecast_summary_lines(
            {
                "ok": True,
                "module_count": 1,
                "cost_display": "¥0.0100",
                "basis": "static",
                "reason": "部分模块无法定价（expert_review）",
            }
        )

        assert any(line.startswith("预估说明：") and "expert_review" in line for line in lines)
