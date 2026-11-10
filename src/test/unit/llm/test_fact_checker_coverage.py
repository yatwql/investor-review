"""数值校验覆盖率统计（`fact_checker/_coverage.py`）单元测试。

为什么单独测：检查器过去只报「告警/检查项」，跳过的声称在统计上与「通过」没区别——
实测一份真实报告 276 条百分比声称只有 52 条被真正比对（19%），漏检因此长期不可见。
"""

from __future__ import annotations

import pytest

from src.python.llm.fact_checker import numerical_coverage, reset_numerical_coverage, run_fact_check

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_HOLDINGS = [
    {"name": "贵州茅台", "code": "600519", "market_value": 200000.0, "cost": 150000.0, "profit": 50000.0, "profit_rate": 33.33},
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
