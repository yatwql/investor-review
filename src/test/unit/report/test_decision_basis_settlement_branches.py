"""决策结算展示块对畸形账本条目的容错契约测试。

锁住的契约：
  - `settlements` 非 dict、结算事件非 dict、视界键非整数的一律整条跳过，
    不污染「我的建议历史表现」与「结算摘要」的计数
  - 缺 `settle_date` 或 `raw_return` 非数值的结算事件不进结算摘要批次

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_decision_basis_settlement_branches.py -v
"""

from __future__ import annotations

import pytest

from src.python.report.decision_basis_settlement import build_performance, build_settlement_summary

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestBuildPerformanceMalformedEntries:
    """历史表现聚合对畸形条目的跳过。"""

    def test_non_dict_settlements_contributes_nothing(self):
        assert build_performance([{"direction": 1, "settlements": "oops"}]) == []

    def test_non_int_direction_does_not_raise(self):
        assert build_performance([{"direction": "abc", "settlements": {}}]) == []

    def test_non_int_horizon_key_is_skipped(self):
        assert build_performance([{"direction": 1, "settlements": {"abc": {"raw_return": 0.05}}}]) == []

    def test_non_dict_settlement_event_is_skipped(self):
        assert build_performance([{"direction": 1, "settlements": {"5": "oops"}}]) == []


class TestBuildSettlementSummaryMalformedEntries:
    """结算摘要批次对畸形条目的跳过。"""

    def test_non_dict_settlements_yields_no_batch(self):
        summary = build_settlement_summary([{"settlements": "oops"}])

        assert summary["batches"] == []

    def test_non_dict_settlement_event_yields_no_batch(self):
        summary = build_settlement_summary([{"settlements": {"5": "oops"}}])

        assert summary["batches"] == []

    def test_non_int_horizon_key_yields_no_batch(self):
        summary = build_settlement_summary(
            [{"settlements": {"abc": {"settle_date": "2026-01-05", "raw_return": 0.05}}}]
        )

        assert summary["batches"] == []

    def test_event_without_settle_date_yields_no_batch(self):
        summary = build_settlement_summary([{"settlements": {"5": {"raw_return": 0.05}}}])

        assert summary["batches"] == []

    def test_event_without_numeric_return_yields_no_batch(self):
        summary = build_settlement_summary([{"settlements": {"5": {"settle_date": "2026-01-05", "raw_return": "--"}}}])

        assert summary["batches"] == []


class _FlakyFloat(float):
    """首次 float() 抛错的数值对象（模拟账本里取不出的脏数值）。"""

    def __new__(cls, value: float) -> "_FlakyFloat":
        obj = super().__new__(cls, value)
        obj._raise_next = True
        return obj

    def __float__(self) -> float:
        if self._raise_next:
            self._raise_next = False
            raise ValueError("bad float")
        return super().__float__()


class TestBuildSettlementSummaryUncoercibleValues:
    """结算摘要对「数值形态但不可转换」脏值的容错。"""

    def test_uncoercible_raw_return_is_skipped(self):
        summary = build_settlement_summary(
            [{"settlements": {"5": {"settle_date": "2026-01-05", "raw_return": _FlakyFloat(0.05)}}}]
        )

        assert summary["batches"] == [], "换算不了的收益不得进均值（避免 NaN 污染整批）"

    def test_uncoercible_bench_return_only_drops_excess(self):
        summary = build_settlement_summary(
            [
                {
                    "settlements": {
                        "5": {
                            "settle_date": "2026-01-05",
                            "raw_return": 0.05,
                            "bench_return": _FlakyFloat(0.02),
                        }
                    }
                }
            ]
        )

        cell = summary["batches"][0]["cells"][0]
        assert cell["n"] == 1
        assert cell["mean_return_pct"] == pytest.approx(5.0)
        assert cell["mean_excess_pct"] is None, "基准换算失败时只丢超额，收益均值照常计入"
