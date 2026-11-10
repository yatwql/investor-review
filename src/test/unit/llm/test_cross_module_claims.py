"""跨模块收益率口径冲突检查（确定性，零 LLM 调用）单元测试。

背景：单模块事实校验看不出模块之间互相打架——实测同一只基金（017730）一处写
「亏损 8.5%」、两处写「-5.06%」（摘要真值 -5.06%），模型层自检还把错值当事实转述。
该冲突纯算术可判定，故由本检查器兜住，不依赖第二次 LLM 调用。
"""

from __future__ import annotations

import pytest

from src.python.llm.fact_checker import build_cross_module_block, check_cross_module_claims

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]

_HOLDINGS = [
    {"name": "嘉实全球产业升级股票(QDII)A", "code": "017730", "market_value": 23941.69, "profit": -1277.26},
    {"name": "华安纳斯达克100ETF联接基金A", "code": "040046", "market_value": 22231.0, "profit": 11334.9},
]


class TestCrossModuleClaims:
    def test_conflicting_returns_are_reported(self):
        """同一基金两处收益率差 > 容差 → 一条冲突，含两处原值与模块名。"""
        issues = check_cross_module_claims(
            {
                "全球政经局势": "<p>嘉实全球产业升级(017730) 为唯一亏损QDII，亏损 8.5%</p>",
                "智囊团深度复盘": "<p>017730 持仓收益率 -5.06%，是唯一亏损品种</p>",
            },
            _HOLDINGS,
        )
        assert len(issues) == 1
        assert "017730" in issues[0] and "-8.50%" in issues[0] and "-5.06%" in issues[0]

    def test_consistent_returns_are_not_reported(self):
        """两处一致（含符号写法差异）→ 不报。"""
        issues = check_cross_module_claims(
            {
                "全球政经局势": "<p>017730 亏损 -5.06%</p>",
                "持仓体检报告": "<p>017730 收益率 -5.06%</p>",
            },
            _HOLDINGS,
        )
        assert issues == []

    def test_different_metric_families_are_not_compared(self):
        """不同指标族（仓位占比 vs 收益率）不属同一口径 → 不报。"""
        issues = check_cross_module_claims(
            {
                "全球政经局势": "<p>040046 仓位占比 9.5%</p>",
                "持仓体检报告": "<p>040046 收益率 103.91%</p>",
            },
            _HOLDINGS,
        )
        assert issues == []

    def test_single_module_is_not_a_conflict(self):
        """只有一个模块提到该实体 → 无跨模块冲突可比。"""
        issues = check_cross_module_claims(
            {"全球政经局势": "<p>017730 亏损 8.5%</p>"},
            _HOLDINGS,
        )
        assert issues == []

    def test_entities_outside_holdings_are_ignored(self):
        """非持仓实体（指数/行业）不在比对名单内。"""
        issues = check_cross_module_claims(
            {
                "全球政经局势": "<p>纳斯达克100 收益率 12.0%</p>",
                "智囊团深度复盘": "<p>纳斯达克100 收益率 9.0%</p>",
            },
            _HOLDINGS,
        )
        assert issues == []


class TestCrossModuleBlock:
    def test_block_lists_issues_and_token_free_label(self):
        block = build_cross_module_block(["「X(1)」收益率不一致"])
        assert "跨模块一致性核对" in block and "确定性" in block
        assert "「X(1)」收益率不一致" in block

    def test_empty_issues_yield_empty_block(self):
        assert build_cross_module_block([]) == ""


class TestReviewBlockOrdering:
    def test_deterministic_block_precedes_model_opinion(self):
        """事实先于观点：确定性核对段插在模型层自检之前。"""
        from src.python.llm.self_review import (
            get_self_review_block,
            prepend_review_block,
            reset_self_review,
            set_self_review_block,
        )

        reset_self_review()
        try:
            set_self_review_block("<p>模型层结论</p>")
            prepend_review_block("<p>确定性核对</p>")
            block = get_self_review_block() or ""
            assert block.index("确定性核对") < block.index("模型层结论")
        finally:
            reset_self_review()
