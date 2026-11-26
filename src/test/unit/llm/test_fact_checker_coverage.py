"""数值校验覆盖率统计（`fact_checker/_coverage.py`）单元测试。

为什么单独测：检查器过去只报「告警/检查项」，跳过的声称在统计上与「通过」没区别——
实测一份真实报告 276 条百分比声称只有 52 条被真正比对（19%），漏检因此长期不可见。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.llm.fact_checker._coverage import _classify_skip
from src.python.llm.fact_checker import numerical_coverage, reset_numerical_coverage, run_fact_check

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_HOLDINGS = [
    {
        "name": "贵州茅台",
        "code": "600519",
        "market_value": 200000.0,
        "cost": 150000.0,
        "profit": 50000.0,
        "profit_rate": 33.33,
    },
]


class TestCoverageAccounting:
    def setup_method(self):
        reset_numerical_coverage()

    def teardown_method(self):
        reset_numerical_coverage()

    def test_consistent_claim_counts_as_verified(self):
        run_fact_check("<p>600519 收益率 33.3%</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        cov = numerical_coverage()
        assert cov["total"] == 1
        assert cov["verified"] == 1
        assert cov["mismatched"] == 0

    def test_mismatch_counts_as_verified_and_mismatched(self):
        run_fact_check("<p>600519 收益率 88.0%</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        cov = numerical_coverage()
        assert cov["verified"] == 1
        assert cov["mismatched"] == 1

    def test_non_rate_claims_are_bucketed_as_skipped(self):
        """占比/市值类数值不是收益率 → 计入「跳过」并带原因，不进已比对。"""
        run_fact_check("<p>账户占比 52.4%，市值 12.3 万</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        cov = numerical_coverage()
        assert cov["verified"] == 0
        assert cov["skipped"] >= 1
        assert cov["skip_reasons"], "跳过原因必须可解释（不能只给一个总数）"

    def test_reset_clears_counters(self):
        run_fact_check("<p>600519 收益率 33.3%</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        reset_numerical_coverage()
        cov = numerical_coverage()
        assert cov == {"total": 0, "verified": 0, "mismatched": 0, "skipped": 0, "skip_reasons": {}}


class TestSkipReasonGranularity:
    """跳过原因要能指导下一步：只给一个粗桶看不出该补归因还是该补关键词。"""

    def setup_method(self):
        reset_numerical_coverage()

    def teardown_method(self):
        reset_numerical_coverage()

    def test_non_profit_sentence_has_its_own_bucket(self):
        run_fact_check("<p>本季度行业景气度 68%</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        reasons = numerical_coverage()["skip_reasons"]
        assert any("无收益关键词" in reason for reason in reasons), reasons

    def test_unresolvable_attached_name_has_its_own_bucket(self):
        """紧邻一个解析不出持仓的名称 → 归因缺口（该补归因，不是补关键词）。"""
        run_fact_check("<p>某某新能源主题 收益率 45.2%</p>", _HOLDINGS, module_label="测试", auto_correct=False)
        reasons = numerical_coverage()["skip_reasons"]
        assert any("紧邻名称解析不出持仓" in reason for reason in reasons), reasons


class TestSkipReasonContextBuckets:
    """语境细分桶逐条可命中：每个桶对应一条「该补规则」的具体语境。"""

    @pytest.mark.parametrize(
        ("sentence", "reason"),
        [
            ("组合收益的贡献度主要来自减仓节奏", "贡献/归因语境"),
            ("组合收益 5.0% 高于国债利率", "宏观基准语境"),
            ("当前仓位下组合收益 4.2%", "仓位/占比语境"),
            ("如果组合收益达到 6.0% 则继续持有", "假设/情景语境"),
            ("组合累计收益 5.0% 后续计划调至低风险品种", "调仓目标语境"),
            ("组合收益 5.0%，美元敞口约 20%", "币种/敞口语境"),
        ],
    )
    def test_context_bucket_matched(self, sentence, reason):
        """收益关键词齐备但语境不同 → 落到对应细分桶而非笼统的「无收益关键词」。"""
        ctx = SimpleNamespace(sentence=sentence, holding_codes=set(), name_to_code={}, anchor=0)

        assert _classify_skip(ctx) == reason


def test_module_label_tolerance_override_wins_over_default():
    """模块级容差映射按「空格→下划线」归一命中；调用级容差仍最高优先。"""
    from src.python.llm.fact_checker._runner import _resolve_tolerance

    assert _resolve_tolerance(None, {"expert_review": 2.0}, "expert review") == 2.0
    assert _resolve_tolerance(1.5, {"expert_review": 2.0}, "expert review") == 1.5
