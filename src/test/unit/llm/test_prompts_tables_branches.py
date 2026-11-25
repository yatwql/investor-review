"""Prompt 表格构建器：情景分析 / 国别敞口 / 数据质量与白名单的分支与退化。

覆盖此前零覆盖的输入形态：
- `_build_scenario_block` 全量分支（Beta 缺省、情景缺 market_change、缺 expected）
- `_calc_country_exposure` 的港股/美股/其他币种归类
- `_build_nav_freshness_basis_lines` 的不可用与「无有效行情品种」
- `_build_data_quality_detail_block` 的 `failure_type=empty` 汇总
- `_build_holdings_summary` 的穿透资产行业/概念标签
- `_build_code_whitelist_block` 无有效代码时不留退化块
"""

from __future__ import annotations

import pytest

from src.python.llm.prompts_tables import (
    _build_alignment_block,
    _build_code_whitelist_block,
    _build_data_quality_detail_block,
    _build_holdings_summary,
    _build_nav_freshness_basis_lines,
    _build_scenario_block,
    _calc_country_exposure,
)
from src.python.llm.prompts_core import _fmt_wan

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestScenarioBlock:
    """情景分析块：空数据不出块，Beta/预期缺省各自降级为 `--`。"""

    def test_no_data_returns_empty(self) -> None:
        assert _build_scenario_block(None) == ""
        assert _build_scenario_block({"has_data": False, "scenarios": [{"market_change": 0.1}]}) == ""

    def test_beta_and_expected_missing_degrade_to_dash(self) -> None:
        block = _build_scenario_block(
            {
                "has_data": True,
                "scenarios": [
                    {"market_change": -0.1, "expected_change_pct": -0.0234},
                    {"market_change": 0.05},
                    {"expected_change_pct": 0.01},
                ],
            }
        )

        lines = block.splitlines()
        assert lines[0] == "【情景分析（Beta 置信区间传播）】"
        assert lines[1] == "组合 Beta: --"
        assert lines[2] == "  市场 -10% → 组合预期 -2.34%"
        assert lines[3] == "  市场 +5% → 组合预期: --"
        assert len(lines) == 4  # 缺 market_change 的情景整行跳过

    def test_beta_rendered_with_two_decimals(self) -> None:
        block = _build_scenario_block({"has_data": True, "beta": 1.234, "scenarios": []})

        assert "组合 Beta: 1.23" in block


def test_alignment_block_prepends_newline() -> None:
    """口径修正块自带前导换行（拼接处不留空行），空摘要不出块。"""
    assert _build_alignment_block(None) == ""
    assert _build_alignment_block("") == ""
    assert _build_alignment_block("口径已按 T-1 修正") == "\n口径已按 T-1 修正"


class TestCountryExposure:
    """国别敞口按币种归类，按市值降序。"""

    def test_classifies_hk_us_and_a_share_by_currency(self) -> None:
        details = [
            {"name": "长江电力", "code": "600900", "market_value": 100.0},
            {"name": "腾讯控股", "code": "00700", "market_value": 500.0},
            {"name": "纳斯达克100ETF", "code": "513100", "market_value": 300.0},
        ]

        rows = _calc_country_exposure(details)

        assert [row.split(":")[0] for row in rows] == ["港股", "美股", "A股"]  # 按市值降序
        assert rows == [f"{label}: {_fmt_wan(mv)}" for label, mv in (("港股", 500.0), ("美股", 300.0), ("A股", 100.0))]

    def test_empty_details_yield_no_rows(self) -> None:
        assert _calc_country_exposure(None) == []
        assert _calc_country_exposure([]) == []


class TestNavFreshnessBasisLines:
    """净值新鲜度基准：契约不可用 / 无交易日 → 不注入任何行。"""

    def test_unavailable_contract_returns_no_lines(self) -> None:
        assert _build_nav_freshness_basis_lines(None) == []
        assert _build_nav_freshness_basis_lines({"available": False, "trading_day": "2025-01-03"}) == []
        assert _build_nav_freshness_basis_lines({"available": True, "trading_day": ""}) == []

    def test_degraded_codes_listed_verbatim(self) -> None:
        lines = _build_nav_freshness_basis_lines(
            {
                "available": True,
                "trading_day": "2025-01-03",
                "prev_trading_day": "2025-01-02",
                "items": [
                    {"code": "600900", "freshness": "stale"},
                    {"code": "011506", "freshness": "degraded"},
                ],
            }
        )

        assert lines[0] == "净值新鲜度基准：最近交易日 2025-01-03，前一交易日 2025-01-02"
        assert any(line.startswith("净值滞后品种") and "600900" in line for line in lines)
        assert lines[-1] == "无有效行情品种：011506"


class TestDataQualityDetailEmptyFailures:
    """`failure_type=empty` 与连不上分列统计（去重后按源排序）。"""

    def test_empty_failure_type_summarized(self) -> None:
        block = _build_data_quality_detail_block(
            [
                {"source_key": "eastmoney", "success": False, "failure_type": "empty"},
                {"source_key": "akshare", "success": False, "failure_type": "unreachable"},
                {"source_key": "akshare", "success": False, "failure_type": "unreachable"},
            ]
        )

        assert "连接失败: akshare" in block
        assert "数据为空: eastmoney" in block
        assert "2" not in block.split("连接失败")[1].splitlines()[0]  # 次数不入文


class TestHoldingsSummaryIndustryTags:
    """持仓摘要与穿透资产的行业/概念标签（各自条数上限不同）。"""

    def _holding(self, code: str, name: str):
        return type("_H", (), {"code": code, "name": name})()

    def test_penetrated_assets_get_industry_and_up_to_two_concepts(self) -> None:
        block = _build_holdings_summary(
            [self._holding("600900", "长江电力")],
            penetrated_assets=[{"name": "白酒龙头", "codes": ["600519", "000858", "000000"]}],
            industry_data={
                "600900": {"industry": "电力", "concepts": ["a", "b", "c", "d"]},
                "600519": {"industry": "白酒", "concepts": ["消费", "高端", "第三个不列"]},
            },
        )

        lines = block.splitlines()
        assert lines[0].endswith("[电力·a·b·c]")  # 持仓行取前 3 个概念
        assert lines[1] == "    [穿透] 白酒龙头 (600519,000858,000000) [白酒·消费·高端]"  # 穿透行取前 2 个

    def test_penetrated_assets_without_industry_data_have_no_tags(self) -> None:
        block = _build_holdings_summary(
            [self._holding("600900", "长江电力")],
            penetrated_assets=[{"name": "白酒龙头", "codes": ["600519"]}],
            industry_data=None,
        )

        assert block.splitlines()[1] == "    [穿透] 白酒龙头 (600519)"


class TestCodeWhitelistBlock:
    """白名单：无可列代码时不出退化块。"""

    def test_empty_codes_returns_empty(self) -> None:
        assert _build_code_whitelist_block(None, 1000.0) == ""
        assert _build_code_whitelist_block([], 1000.0) == ""
        assert _build_code_whitelist_block([{"code": "", "market_value": 1000.0}], 1000.0) == ""

    def test_zero_total_market_value_returns_empty(self) -> None:
        assert _build_code_whitelist_block([{"code": "600900", "market_value": 0.0}], 0.0) == ""
