"""行动建议页签（`report/action_sheet.py`）章内块与空态分支契约测试。

锁住的契约：
  - 集中度约束不可用时写「约束数据不可用：<原因>」而非静默跳过
  - 行动数据不可用时章内块（景气度/市场情绪）仍按契约渲染
  - 市场情绪块：不可用原因 + 各源失败留痕；可用时命中事件按事件类型分列说明
  - 判断依据块旧契约（无 headline）回落单行 summary，且不可用时写空态行

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_action_sheet_branches.py -v
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _flat(ws) -> list[str]:
    return [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]


def _write(action_data, **kwargs):
    from openpyxl import Workbook

    from src.python.report.action_sheet import write_action_sheet

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    write_action_sheet(ws, action_data, **kwargs)
    return ws


def _available_action(**extra) -> dict:
    data = {
        "available": True,
        "summary": "再平衡建议 1 条。",
        "rebalance_signals": [],
        "discipline_signals": [],
        "rebalance_advice": [],
        "attribution": {"available": False},
    }
    data.update(extra)
    return data


def _prosperity() -> dict:
    return {
        "available": True,
        "total_score": 40,
        "scored_weight": 60,
        "total_score_pct": 66,
        "rating_label": "较契合",
        "dimensions": [],
        "holdings_view": [],
    }


class TestConstraintsUnavailable:
    """集中度约束不可用的空态文案（读判断依据契约的 constraints 段）。"""

    def test_unavailable_constraints_write_reason_row(self):
        ws = _write(
            _available_action(),
            decision_basis_data={
                "enabled": True,
                "available": True,
                "constraints": {"enabled": True, "available": False, "reason": "阈值未配置"},
            },
        )

        assert any("约束数据不可用：阈值未配置" in text for text in _flat(ws))


class TestChapterBlocksWhenActionUnavailable:
    """行动数据不可用时章内块照常渲染。"""

    def test_prosperity_block_rendered(self):
        ws = _write({"available": False}, prosperity_framework_data=_prosperity())

        assert any("景气度框架诊断" in text for text in _flat(ws))

    def test_market_sentiment_block_rendered(self):
        ws = _write({"available": False}, market_sentiment_data={"available": False, "reason": "缺凭据"})

        assert any("市场情绪与持仓热点" in text for text in _flat(ws))
        assert any("缺凭据" in text for text in _flat(ws))


class TestMarketSentimentRows:
    """市场情绪块的行级口径。"""

    def test_block_rendered_when_action_available(self):
        ws = _write(_available_action(), market_sentiment_data={"available": False, "reason": "缺凭据"})

        assert any("市场情绪与持仓热点" in text for text in _flat(ws))

    def test_unavailable_lists_each_source_failure(self):
        ws = _write(
            _available_action(),
            market_sentiment_data={
                "available": False,
                "reason": "两源均不可用",
                "failures": [{"source": "同花顺龙虎榜", "reason": "超时"}],
            },
        )

        assert any("⚠ 同花顺龙虎榜：超时" in text for text in _flat(ws))

    def test_ladder_event_row_carries_board_and_seal_note(self):
        ws = _write(
            _available_action(),
            market_sentiment_data={
                "available": True,
                "trade_date": "2026-03-02",
                "summary": {"board_caps": {"3 板": 1}},
                "rows": [
                    {
                        "name": "贵州茅台",
                        "code": "600519",
                        "holding_kind": "直接持有",
                        "event_type": "连板梯队",
                        "board_label": "3 板",
                        "event_date": "2026-03-02",
                        "seal_nextday": True,
                    }
                ],
            },
        )
        flat = _flat(ws)

        assert any("3 板｜日期 2026-03-02｜次日封板" in text for text in flat)
        assert any("贵州茅台" == text for text in flat)

    def test_available_block_appends_source_failures(self):
        ws = _write(
            _available_action(),
            market_sentiment_data={
                "available": True,
                "trade_date": "2026-03-02",
                "summary": {},
                "rows": [],
                "failures": [{"source": "连板梯队", "reason": "空返回"}],
            },
        )

        assert any("⚠ 连板梯队：空返回" in text for text in _flat(ws))


class TestDecisionBasisLegacyContract:
    """判断依据块的旧契约回落与空态。"""

    def test_legacy_summary_and_unavailable_row(self):
        ws = _write(
            _available_action(),
            decision_basis_data={"enabled": True, "available": False, "reason": "缺数据", "summary": "旧版摘要行"},
        )
        flat = _flat(ws)

        assert any("旧版摘要行" == text for text in flat), "无 headline 的旧契约须回落 summary"
        assert any("数据不可用：缺数据" in text for text in flat)
