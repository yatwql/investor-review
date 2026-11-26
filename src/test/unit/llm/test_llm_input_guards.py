"""LLM 侧的输入防御分支：信号行格式、估值档位聚合、数字方向、排名注记。

断言落在「畸形载荷 → 声明的返回值」上（空串/None/中性），不校验内部步骤。
"""

from __future__ import annotations

import pytest

from src.python.llm import prompts_signals
from src.python.llm.fact_checker import _ranking

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestSignalLineFormat:
    """无依据时省略括号（避免出现空括号）。"""

    def test_detail_absent_omits_parentheses(self):
        assert prompts_signals._format_signal("市场温度", "偏热") == f"{prompts_signals.SIGNAL_PREFIX}市场温度 偏热"


class TestValuationSignalDirections:
    """档位分布聚合：高估多于低估 → 看空；反之看多。"""

    def _pipeline(self, tiers: list[str]) -> dict:
        return {
            "valuation_data": {
                "available": True,
                "by_code": {f"60000{i}": {"tier": tier} for i, tier in enumerate(tiers)},
            }
        }

    def test_more_overvalued_than_undervalued_is_bearish(self):
        from src.python.analysis.valuation_percentile import TIER_FAIR, TIER_OVERVALUED, TIER_UNDERVALUED

        line = prompts_signals._valuation_signal(
            self._pipeline([TIER_OVERVALUED, TIER_OVERVALUED, TIER_UNDERVALUED, TIER_FAIR])
        )

        assert prompts_signals.SIGNAL_BEARISH in line


class TestNumericDirection:
    """数字方向：同比超阈值判强弱，窗口内判持平。"""

    def test_net_profit_yoy_above_bound_is_strong(self):
        assert prompts_signals._numeric_direction({"net_profit_yoy": 50.0}) == prompts_signals.DIRECTION_STRONG

    def test_revenue_yoy_below_negative_bound_is_weak(self):
        assert prompts_signals._numeric_direction({"revenue_yoy": -50.0}) == prompts_signals.DIRECTION_WEAK


class TestNarrativeDivergenceRows:
    """叙事摘要侧的非字典行直接跳过（不当作持仓配对对象）。"""

    def test_non_dict_narrative_row_skipped(self):
        pipeline = {
            "financial_report_digest_data": {
                "available": True,
                "rows": ["不是字典的行", {"code": "600000", "summary": "业绩稳步增长"}],
            },
            "financial_indicator_data": {
                "available": True,
                "rows": [{"code": "600000", "net_profit_yoy": -50.0, "revenue_yoy": -50.0}],
            },
        }

        line = prompts_signals._narrative_divergence_signal(pipeline)

        assert "600000" in line


class TestRankNumberParsing:
    """排名数字解析：空串 → 0；阿拉伯数字原样取整。"""

    def test_empty_text_is_zero(self):
        assert _ranking._parse_rank_number("") == 0

    def test_digit_text_is_parsed(self):
        assert _ranking._parse_rank_number("20") == 20


class TestNearTieNoteGuards:
    """近并列注记的不可计算场景一律返回空串（不猜）。"""

    def test_empty_holdings_returns_empty(self):
        assert _ranking._near_tie_note("max", 0, "600000", []) == ""

    def test_claim_on_boundary_slot_returns_empty(self):
        holdings = [{"code": "600000", "market_value": 100.0}]

        assert _ranking._near_tie_note("max", 0, "600000", holdings) == ""

    def test_zero_total_market_value_returns_empty(self):
        holdings = [{"code": "000001", "market_value": 0.0}]

        assert _ranking._near_tie_note("max", 0, "600000", holdings) == ""

    def test_claimed_code_absent_returns_empty(self):
        holdings = [{"code": "000001", "market_value": 100.0}]

        assert _ranking._near_tie_note("max", 0, "600000", holdings) == ""
