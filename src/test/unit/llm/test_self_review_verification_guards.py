"""自检模块百分比核对的容错分支单元测试（llm/self_review.py）。

锁住的契约：
  - 语料百分比提取逐条容错：单条解析失败只跳过该条，不影响其余取值（去重升序）
  - 派生百分比判定：语料为空恒不认「可推出」；容差内直接命中即认；分项上限被
    调低时不做多项组合验算（宁漏判不漏放——宁可多一条「无法核实」注记）
  - `prepend_review_block("")` 不改写载体（无内容不落空串）
  - 账本不可读、失败原因登记失败都不得阻断自检主流程
"""

from __future__ import annotations

import pytest

from src.python.llm import self_review as sr
from src.python.llm.self_review import (
    SELF_REVIEW_MODULE_KEY,
    get_self_review_block,
    reset_self_review,
    run_self_review,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_OUTPUTS: dict[str, str | None] = {"global_macro": "<p>宏观分析正文</p>"}


def _llm_config(enabled: bool) -> dict:
    return {"enabled_llm": {SELF_REVIEW_MODULE_KEY: enabled}}


@pytest.fixture(autouse=True)
def _clean_carrier():
    reset_self_review()
    yield
    reset_self_review()


class TestCorpusPercentageExtraction:
    def test_unparsable_match_is_skipped_without_losing_others(self, monkeypatch):
        attempts: list[str] = []

        def _raise(match):
            attempts.append(match.group(0))
            raise ValueError("异常输入")

        monkeypatch.setattr(sr, "_signed_value", _raise)

        assert sr._corpus_pct_values("涨 1.20%、跌 -3.40%") == []
        assert len(attempts) >= 2, "两条百分比都应尝试解析后逐条跳过"


class TestDerivedPercentage:
    def test_empty_pool_never_accepts_derived_value(self):
        assert sr._is_derived_percentage(5.0, []) is False

    def test_direct_tolerance_hit_is_accepted(self):
        assert sr._is_derived_percentage(5.0, [5.01]) is True

    def test_multi_term_combination_accepted_at_default_limit(self):
        assert sr._is_derived_percentage(35.0, [5.0, 10.0, 20.0]) is True

    def test_lowered_term_limit_skips_multi_term_combination(self, monkeypatch):
        monkeypatch.setattr(sr, "_DERIVED_PCT_MAX_TERMS", 2)

        assert sr._is_derived_percentage(35.0, [5.0, 10.0, 20.0]) is False, "分项上限调低后宁漏判不漏放"


class TestPrependReviewBlock:
    def test_empty_html_leaves_carrier_untouched(self):
        assert sr.prepend_review_block("") is None
        assert get_self_review_block() is None


class TestSelfReviewDegradations:
    def test_inaction_ledger_failure_continues_with_empty_line(self, monkeypatch):
        seen: dict[str, object] = {}

        def _raise(*_a, **_k):
            raise RuntimeError("账本不可读")

        def _generate(*_a, **kwargs):
            seen.update(kwargs)
            return ("<p>【自检清单】未发现矛盾</p>", False)

        monkeypatch.setattr("src.python.core.decision_ledger.inaction_summary_line", _raise)
        monkeypatch.setattr("src.python.llm.generators.generate_self_review", _generate)

        assert run_self_review(_OUTPUTS, [], [], _llm_config(True)) is True
        assert seen["inaction_line"] == "", "账本不可读时以空提示继续，不阻断自检"

    def test_skip_reason_registration_failure_keeps_skip_outcome(self, monkeypatch):
        class _ExplodingMapping(dict):
            def __setitem__(self, key, value):
                raise TypeError("载体只读")

        monkeypatch.setattr("src.python.llm.prompts.LLM_MODULE_FAILURE", _ExplodingMapping())

        assert run_self_review({"global_macro": None}, [], [], _llm_config(True)) is False
        assert get_self_review_block() is None, "登记失败不得产出空洞自检区块"
