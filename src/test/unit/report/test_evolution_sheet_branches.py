"""组合演进页签「自上次快照变化摘要」契约测试。

锁住的契约：
  - 快照差异可用时逐项渲染新增/移除品种、HHI 变化与超限品种
  - 差异可用但四项全空时给出「无变化」文案
  - 差异不可用时以原因文案占位

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_evolution_sheet_branches.py -v
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from src.python.report.evolution_sheet import write_evolution_sheet

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _evolution_data() -> dict:
    return {
        "available": True,
        "snapshot_count": 5,
        "min_snapshots": 3,
        "periods": ["07-01"],
        "total_value": [100000.0],
        "total_cost": [90000.0],
        "total_pnl": [10000.0],
        "holding_counts": [2],
        "account_flows": {},
        "hhi": [0.5],
        "top_holdings": [],
        "reason": "",
    }


def _render(diff: dict | None) -> list[str]:
    wb = Workbook()
    write_evolution_sheet(wb.active, _evolution_data(), diff)
    return [str(c.value) for row in wb.active.iter_rows() for c in row if c.value not in (None, "")]


class TestSnapshotDiffSummary:
    """快照差异摘要块的呈现分支。"""

    def test_all_diff_rows_are_rendered(self):
        texts = _render(
            {
                "available": True,
                "added": [{"name": "新标的", "code": "600519"}],
                "removed": [{"name": "", "code": "000001"}],
                "hhi_previous": 0.52,
                "hhi_current": 0.61,
                "hhi_change": 0.09,
                "over_limit": [{"name": "重仓标的", "code": "300750", "weight_pct": 31.5, "threshold_pct": 30.0}],
            }
        )

        assert any("新增品种" in t and "新标的" in t for t in texts)
        assert any("移除品种" in t and "000001" in t for t in texts)
        assert any("集中度 HHI" in t for t in texts)
        assert any("超限品种" in t and "300750" in t for t in texts)
        assert not any("持仓结构无变化" in t for t in texts)

    def test_empty_diff_falls_back_to_no_change_line(self):
        texts = _render({"available": True})

        assert any("持仓结构无变化" in t for t in texts)

    def test_unavailable_diff_renders_reason(self):
        texts = _render({"available": False, "reason": "上次快照缺失"})

        assert any("上次快照缺失" in t for t in texts)
        assert not any("持仓结构无变化" in t for t in texts)
