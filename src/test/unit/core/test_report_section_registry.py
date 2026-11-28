"""报告章节注册表（`core/report_section_registry`）——默认顺序、可见性类型与自定义序号合并。

只断言结构关系（首尾固定、类型契约、序号连续不重复、合并后的 key 集合），
不写死「每类各几条」——新增章节是良性变更，条数由 `check-doc-drift` 的
章节-区块矩阵与文档对齐，写进用例只会把良性新增判成回归。
"""

from __future__ import annotations

import unittest

import pytest

from src.python.core.registry import (
    _REPORT_SECTION_DEFAULT,
    get_report_section_order,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestReportSectionDefaultOrder(unittest.TestCase):
    """注册表默认顺序的结构契约。"""

    def test_starts_with_summary_ends_with_llm_usage(self):
        order = get_report_section_order()
        self.assertEqual(order[0]["key"], "summary")
        self.assertEqual(order[-1]["key"], "llm_usage")

    def test_always_type_section_contract(self):
        """always 类型：无 data_flag 控制可见性，数据源可用性矩阵在其中，组合演进不在其中。"""
        always = [s for s in _REPORT_SECTION_DEFAULT if s["type"] == "always"]
        keys = {s["key"] for s in always}
        self.assertIn("data_source_status", keys)
        self.assertNotIn("portfolio_evolution", keys)
        for sec in always:
            self.assertIsNone(sec["data_flag"], f"{sec['key']} 属 always 却声明了 data_flag")

    def test_portfolio_evolution_is_the_evolution_section(self):
        """组合演进独占 evolution 类型，可见性由 evolution_data 控制（available=False 时展示层写占位）。"""
        evolution = [s for s in _REPORT_SECTION_DEFAULT if s["type"] == "evolution"]
        self.assertEqual([s["key"] for s in evolution], ["portfolio_evolution"])
        self.assertEqual(evolution[0]["data_flag"], "evolution_data")

    def test_fund_deep_analysis_type_covers_merged_chapters(self):
        """基金深度分析由「持仓结构 + 风格与因子」两章承载，旧的独立章节名不得回潮。"""
        fund_deep = [s for s in _REPORT_SECTION_DEFAULT if s["type"] == "fund_deep_analysis"]
        keys = {s["key"] for s in fund_deep}
        self.assertIn("position_structure", keys)
        self.assertIn("style_factor", keys)
        self.assertNotIn("fund_style", keys)
        self.assertNotIn("factor_exposure", keys)

    def test_news_type_section_is_news_correlation(self):
        news = [s for s in _REPORT_SECTION_DEFAULT if s["type"] == "news"]
        self.assertEqual([s["key"] for s in news], ["news_correlation"])

    def test_fund_deep_analysis_data_flags_are_distinct(self):
        """同类型章节共用 data_flag 会导致开关连带隐藏，故必须各不相同。"""
        fund_deep = [s for s in _REPORT_SECTION_DEFAULT if s["type"] == "fund_deep_analysis"]
        flags = [s["data_flag"] for s in fund_deep]
        self.assertEqual(len(set(flags)), len(flags), f"data_flag 应各不相同: {flags}")


class TestCustomSectionOrder(unittest.TestCase):
    """`get_report_section_order(config)` 在用户自定义序号下的合并行为。"""

    def _partial_config(self) -> dict:
        """只覆盖前 3 个模块序号的部分自定义配置。"""
        return {
            "report_section_order": {
                "fund_performance": 1,
                "summary": 2,
                "holdings_detail": 3,
            }
        }

    def test_partial_custom_reorders_modules(self):
        order = get_report_section_order(self._partial_config())
        self.assertEqual([s["key"] for s in order[:3]], ["fund_performance", "summary", "holdings_detail"])
        self.assertEqual([s["number"] for s in order[:3]], [1, 2, 3])

    def test_partial_custom_auto_numbers_remaining(self):
        """未配置项排在已配置项之后，序号保持单调不减。"""
        order = get_report_section_order(self._partial_config())
        remaining = order[3:]
        self.assertEqual(len(remaining), len(_REPORT_SECTION_DEFAULT) - 3)
        numbers = [s["number"] for s in remaining]
        for prev, cur in zip(numbers, numbers[1:]):
            self.assertGreaterEqual(cur, prev, f"剩余项序号不单调递增: {numbers}")

    def test_partial_custom_all_keys_present(self):
        order = get_report_section_order(self._partial_config())
        keys = [s["key"] for s in order]
        self.assertEqual(len(set(keys)), len(_REPORT_SECTION_DEFAULT), "合并后 key 不得重复或丢失")

    def test_custom_unknown_key_falls_back_to_default(self):
        """配置里出现注册表外的 key → 忽略，合并结果不含该 key。"""
        config = {"report_section_order": {"summary": 1, "nonexistent_key": 99}}
        order = get_report_section_order(config)
        keys = [s["key"] for s in order]
        self.assertNotIn("nonexistent_key", keys)
        self.assertEqual(len(order), len(_REPORT_SECTION_DEFAULT))
