"""report/signal_record.py 的「数据不可用」空返回与脏条目过滤分支。

锁住的契约：
  - 五类确定性信号的数据缺失/未 available 时一律返回空列表（不入账）；
  - 估值 ``by_code`` 中非 dict 或缺百分位的条目跳过；
  - ``data_freshness.items`` 中非 dict 条目跳过，其余照常建索引。
"""

from __future__ import annotations

import pytest

from src.python.report import signal_record as sr

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_freshness_index_skips_non_dict_items() -> None:
    ctx = sr._QualityContext({"data_freshness": {"items": ["脏条目", {"code": "600519", "freshness": "live"}]}})
    assert ctx.freshness_of("600519") == "live"
    assert ctx.freshness_of("000001") is None


def test_missing_payloads_yield_no_signals() -> None:
    ctx = sr._QualityContext({})
    assert sr._temperature_signals({}, "2025-01-02", ctx) == []
    assert sr._valuation_signals({}, "2025-01-02", ctx) == []
    assert sr._tail_risk_signals({}, "2025-01-02", ctx) == []
    assert sr._style_factor_signals({}, "2025-01-02", ctx) == []
    assert sr._overflow_signals({}, "2025-01-02", ctx) == []


def test_valuation_rows_without_percentile_are_skipped() -> None:
    payload = {
        "valuation_data": {
            "available": True,
            "by_code": {"600519": {"percentile_available": False}, "000001": "脏条目"},
        }
    }
    assert sr._valuation_signals(payload, "2025-01-02", sr._QualityContext({})) == []


def test_available_payloads_missing_required_fields_yield_no_signals() -> None:
    ctx = sr._QualityContext({})
    assert sr._temperature_signals({"market_temperature_data": {"available": True}}, "2025-01-02", ctx) == []
    assert sr._valuation_signals({"valuation_data": {"available": True, "by_code": []}}, "2025-01-02", ctx) == []
    assert sr._tail_risk_signals({"tail_risk_data": {"available": True, "var95": "非数值"}}, "2025-01-02", ctx) == []
    assert (
        sr._style_factor_signals({"style_factor_data": {"available": True, "style_allocation": {}}}, "2025-01-02", ctx)
        == []
    )
    assert sr._overflow_signals({"action_data": {"rebalance_signals": {}}}, "2025-01-02", ctx) == []


def test_valuation_row_without_tier_is_skipped() -> None:
    payload = {"valuation_data": {"available": True, "by_code": {"600519": {"percentile_available": True}}}}
    assert sr._valuation_signals(payload, "2025-01-02", sr._QualityContext({})) == []
