"""Token 预算闸与成本摘要的分支单元测试（cost_tracker）。

锁住的契约：
  - 首次超预算：告警并返回 False（告警不截断，调用照常进行）；已告警后重复检查
    返回 True（同一报告周期只告警一次），`warn_once=False` 时不置位告警标记
  - 耗时格式化：<60s 用秒、≥60s 用「分 + 秒」
  - 成本摘要两套格式（报告紧凑版 / verbose 详细版）都输出缓存命中行
"""

from __future__ import annotations

import pytest

from src.python.llm import cost_tracker as ct

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_BUDGET = 1000
_USED = 900
_ASK = 200


@pytest.fixture()
def _tight_budget(monkeypatch):
    """把预算与告警状态钉在局部值（monkeypatch 负责复位模块级全局）。"""
    monkeypatch.setattr(ct, "_input_budget", _BUDGET)
    monkeypatch.setattr(ct, "_budget_warned", False)
    monkeypatch.setattr(ct, "get_session_usage", lambda: {"input_tokens": _USED})
    return ct


class TestInputBudgetGate:
    def test_first_over_budget_warns_and_returns_false(self, _tight_budget):
        assert _tight_budget.check_input_budget("global_macro", _ASK) is False
        assert _tight_budget.get_budget_status()["warned"] is True

    def test_second_check_after_warning_returns_true(self, _tight_budget):
        assert _tight_budget.check_input_budget("global_macro", _ASK) is False
        assert _tight_budget.check_input_budget("global_macro", _ASK) is True, "同一周期只告警一次"

    def test_warn_once_false_keeps_flag_unset(self, _tight_budget):
        assert _tight_budget.check_input_budget("global_macro", _ASK, warn_once=False) is False
        assert _tight_budget.get_budget_status()["warned"] is False


class TestFormatDuration:
    def test_under_a_minute_rendered_in_seconds(self):
        assert ct._format_duration(3.0) == "3.0s"

    def test_at_or_over_a_minute_rendered_in_minutes(self):
        assert ct._format_duration(72) == "1m 12s"


def _patch_formatted_usage(monkeypatch, *, cache_hit: int) -> None:
    monkeypatch.setattr(ct, "get_session_usage", lambda: {"per_module": {}})
    monkeypatch.setattr(
        ct,
        "format_session_usage",
        lambda _raw: {
            "has_usage": True,
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_hit_tokens": cache_hit,
            "cost_display": "¥0.0100",
            "model_display": "m",
            "call_count": 1,
        },
    )


class TestCostSummaryCacheLine:
    def test_report_format_prints_cache_hit_tokens(self, monkeypatch):
        _patch_formatted_usage(monkeypatch, cache_hit=40)
        monkeypatch.setattr(ct, "_input_budget", 0)  # 未设预算 → 不输出预算行

        assert "缓存命中: 40 tokens" in ct.get_cost_summary(for_report=True)

    def test_verbose_format_prints_cache_hit_tokens(self, monkeypatch):
        _patch_formatted_usage(monkeypatch, cache_hit=40)

        assert "缓存命中: 40" in ct.get_cost_summary(for_report=False)
