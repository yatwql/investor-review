"""调仓纪律回放的规则/窗口降级分支单元测试。

覆盖既有回放手算用例之外的分支：
  - 季度桶键与目标权重的三种来源（末日市值归一 / 部分覆盖补 0 重归一 / 空交集非法）；
  - 窗口与持仓的不可回放降级（窗口内无净值、持仓品种窗口内无行情）；
  - 期初批次注入、清仓后的仓位与批次收口、场内未建模腿的成本标注。
"""

from __future__ import annotations

import pytest

from src.python.analysis.schedule_replay import (
    _month_key,
    _resolve_target_weights,
    run_schedule_replay,
)
from src.python.schemas.replay_schedule import parse_replay_schedule

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

#: 短窗口夹具：绕过 12 个月跨度/净值日验收下限（默认值行为由 edge 文件守）
FAST = {"min_span_days": 0, "min_points": 1}


def _holdings() -> list[dict]:
    return [
        {"code": "A", "name": "甲基金", "shares": 100.0, "cost": 1.0},
        {"code": "B", "name": "乙基金", "shares": 100.0, "cost": 1.0},
    ]


def _flat_navs() -> dict[str, dict[str, float]]:
    """两只品种跨两个月的平盘净值（触发一期定期调仓）。"""
    return {"A": {"2025-01-02": 10.0, "2025-02-03": 10.0}, "B": {"2025-01-02": 10.0, "2025-02-03": 10.0}}


class TestMonthKey:
    """回放桶键：季度规则取季度末月所属季度。"""

    def test_quarterly_bucket(self):
        assert _month_key("2025-05-06", "quarterly") == "2025-Q2"

    def test_monthly_bucket_keeps_year_month(self):
        assert _month_key("2025-11-06", "monthly") == "2025-11"


class TestTargetWeightSources:
    """目标权重三种来源与非法规则。"""

    ROWS = [{"code": "A", "shares": 100.0}, {"code": "B", "shares": 100.0}]

    def test_zero_total_value_maps_every_holding_to_zero(self):
        notes: list[str] = []

        out = _resolve_target_weights(parse_replay_schedule(None), self.ROWS, {}, notes)

        assert out == {"A": 0.0, "B": 0.0}, "末日市值全零时全部按 0 解释（不凭空造权重）"

    def test_partial_coverage_zeroes_missing_and_renormalizes(self):
        notes: list[str] = []
        schedule = parse_replay_schedule({"target_weights": {"A": 0.5, "Z": 0.5}})

        out = _resolve_target_weights(schedule, self.ROWS, {"A": 10.0, "B": 10.0}, notes)

        assert out == {"A": 1.0, "B": 0.0}, "未覆盖持仓按 0（清仓），交集内重归一"
        assert any("未覆盖的持仓按 0" in n for n in notes)
        assert any("非持仓代码已忽略" in n for n in notes)

    def test_empty_intersection_raises(self):
        schedule = parse_replay_schedule({"target_weights": {"Z": 1.0}})

        with pytest.raises(ValueError, match="交集为空"):
            _resolve_target_weights(schedule, self.ROWS, {"A": 10.0, "B": 10.0}, [])


class TestUnavailableInputs:
    """不可回放的输入：窗口内无净值 / 持仓品种窗口内无行情。"""

    def test_window_without_nav_reports_reason(self):
        result = run_schedule_replay(_holdings(), _flat_navs(), None, end_date="2025-06-01", window_days=1, **FAST)

        assert result["available"] is False
        assert "窗口 2025-05-31 ~ 2025-06-01 内无净值数据" in result["reason"]

    def test_holdings_without_nav_reports_reason(self):
        navs = {"Z": {"2025-01-02": 10.0, "2025-02-03": 10.0}}

        result = run_schedule_replay(_holdings(), navs, None, **FAST)

        assert result["available"] is False
        assert "无可回放品种" in result["reason"]


class TestReplayScheduleInstance:
    """已解析的 ReplaySchedule 实例可直接复用，不再走二次解析。"""

    def test_parsed_instance_runs_replay(self):
        schedule = parse_replay_schedule({"rule_type": "cadence", "cadence": "monthly"})

        result = run_schedule_replay(_holdings(), _flat_navs(), schedule, **FAST)

        assert result["available"] is True
        assert result["schedule_version"] == schedule.version


class TestLotsAndClearing:
    """期初批次注入与清仓后的仓位/批次收口。"""

    def test_supplied_lots_skip_synthetic_opening_note(self):
        lots = {
            "A": [{"start_date": "2024-06-03", "shares": 100.0}],
            "B": [{"start_date": "2024-06-03", "shares": 100.0}],
        }

        result = run_schedule_replay(_holdings(), _flat_navs(), None, lots_by_code=lots, **FAST)

        assert not any("期初批次建仓日" in n for n in result["notes"]), "批次已注入时不得再声称合成期初批"

    def test_cleared_holding_leaves_no_residual_position(self):
        """目标权重 0 的持仓被清仓：该期两条腿，且后续期不再重新买回。"""
        navs = {
            "A": {"2025-01-02": 10.0, "2025-02-03": 10.0, "2025-03-03": 10.0},
            "B": {"2025-01-02": 10.0, "2025-02-03": 10.0, "2025-03-03": 10.0},
        }

        result = run_schedule_replay(_holdings(), navs, {"target_weights": {"A": 1.0}}, **FAST)

        assert [row["trades"] for row in result["periods"]] == [2, 0], "清仓期两条腿；已清仓持仓不得被重新买回"

    def test_unmodeled_legs_are_noted(self):
        """场内未建模品种的腿只计数并标注，不冒充成本数字。"""
        fee_index = {"A": {"purchase": {"tiers": [{"min_amount": None, "max_amount": None, "rate": 0.01}]}}}

        result = run_schedule_replay(
            _holdings(),
            _flat_navs(),
            {"target_weights": {"A": 1.0}},
            fee_index=fee_index,
            unmodeled_codes={"B"},
            cost_counter=lambda start, end: 10,
            **FAST,
        )

        assert result["periods"][0]["cost_known"] is True
        assert any("未建模品种" in n for n in result["notes"])
