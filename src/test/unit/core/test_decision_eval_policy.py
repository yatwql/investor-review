"""决策评估政策（`core/decision_eval_policy.py`）与不动作类判定的单元测试。

覆盖：
  - 口径单源：账本转出的阈值/门槛与政策模块一致（值引用，不断言字面量）
  - 不动作判定矩阵：容忍带边界、无收益数据不可判、非数值不可判
  - 政策声明结构：百分比口径、单位声明、视界单位
  - 零依赖：政策模块不得反向 import 账本（否则成环）
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.python.core import decision_eval_policy as policy
from src.python.core import decision_ledger as ledger

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestPolicySingleSource:
    """阈值与样本门槛只有政策模块一个事实位。"""

    def test_ledger_reexports_policy_thresholds(self):
        assert ledger.DIRECTION_THRESHOLD == policy.DIRECTION_HIT_THRESHOLD
        assert ledger.FLAT_HIT_TOLERANCE == policy.FLAT_HIT_TOLERANCE
        assert ledger.MEANINGFUL_SAMPLE == policy.MEANINGFUL_SAMPLE
        assert ledger.HORIZON_UNIT == policy.HORIZON_UNIT

    def test_policy_declares_pct_and_units(self):
        assert policy.EVAL_POLICY["direction_hit_threshold_pct"] == pytest.approx(policy.DIRECTION_HIT_THRESHOLD * 100)
        assert policy.EVAL_POLICY["flat_hit_tolerance_pct"] == pytest.approx(policy.FLAT_HIT_TOLERANCE * 100)
        assert policy.EVAL_POLICY["horizon_unit"] == policy.HORIZON_UNIT
        assert "分数" in str(policy.EVAL_POLICY["units"])
        assert policy.EVAL_POLICY["meaningful_sample"] == policy.MEANINGFUL_SAMPLE

    def test_policy_module_has_no_ledger_dependency(self):
        """政策模块零依赖：反向引用账本会造成 import 环。"""
        source = Path(policy.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert not any("decision_ledger" in name for name in imported), imported


class TestClassifyFlatHit:
    """不动作类判定：|区间涨跌| < 容忍带 ⇒ 判对。"""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, None),
            (0.0, True),
            (0.019, True),
            (-0.019, True),
            (0.02, False),  # 恰好等于容忍带：越带（严格小于）
            (-0.02, False),
            (0.05, False),
            (-0.12, False),
            ("not-a-number", None),
        ],
    )
    def test_matrix(self, raw, expected):
        assert policy.classify_flat_hit(raw) is expected

    def test_custom_tolerance(self):
        assert policy.classify_flat_hit(0.03, tolerance=0.05) is True
        assert policy.classify_flat_hit(0.03, tolerance=0.02) is False

    def test_ledger_reexports_function(self):
        assert ledger.classify_flat_hit is policy.classify_flat_hit


class TestFoldInactionStats:
    """折叠统计：不动作类单独成项，不稀释方向性命中率。"""

    @staticmethod
    def _events(inaction_raw: list[float]) -> list[dict]:
        events = [
            {
                "event": ledger.EVENT_DECISION,
                "decision_id": "d-dir",
                "code": "600000",
                "name": "方向性",
                "direction": ledger.DIRECTION_LONG,
                "carrier": ledger.CARRIER_EXPERT_REVIEW,
                "report_date": "2026-11-01",
                "status": "pending",
            },
            {
                "event": ledger.EVENT_SETTLEMENT,
                "decision_id": "d-dir",
                "target_horizon": ledger.MIN_SETTLE_BARS,
                "horizon_bars": ledger.MIN_SETTLE_BARS,
                "raw_return": 0.05,
                "outcome": ledger.OUTCOME_HIT,
                "direction_hit": True,
            },
        ]
        for idx, raw in enumerate(inaction_raw):
            did = f"d-flat-{idx}"
            events.append(
                {
                    "event": ledger.EVENT_DECISION,
                    "decision_id": did,
                    "code": f"00000{idx}",
                    "name": "不动作",
                    "direction": ledger.DIRECTION_FLAT,
                    "carrier": ledger.CARRIER_EXPERT_REVIEW,
                    "report_date": "2026-11-01",
                    "status": "pending",
                }
            )
            events.append(
                {
                    "event": ledger.EVENT_SETTLEMENT,
                    "decision_id": did,
                    "target_horizon": ledger.MIN_SETTLE_BARS,
                    "horizon_bars": ledger.MIN_SETTLE_BARS,
                    "raw_return": raw,
                    "outcome": ledger.OUTCOME_FLAT,
                    "flat_hit": ledger.classify_flat_hit(raw),
                }
            )
        return events

    def test_inaction_counts_and_keeps_directional_denominator(self):
        stats = ledger.fold_ledger(events=self._events([0.01, 0.03, -0.004]))
        assert stats["directional_total"] == 1  # 只有方向性那条进分母
        assert stats["direction_accuracy"] == 1.0
        inaction = stats["inaction"]
        assert inaction["total"] == 3
        assert inaction["hit"] == 2  # 0.01 与 -0.004 在带内
        assert inaction["hit_rate"] == pytest.approx(2 / 3)
        assert inaction["sample_sufficient"] is False  # 3 < 20

    def test_by_carrier_exposes_inaction(self):
        stats = ledger.fold_ledger(events=self._events([0.01]))
        carrier = stats["by_carrier"][ledger.CARRIER_EXPERT_REVIEW]
        assert carrier["inaction_total"] == 1
        assert carrier["inaction_hit"] == 1

    def test_legacy_settlement_without_flat_hit_not_counted(self):
        """旧账本结算无 `flat_hit` 字段 ⇒ 未判，不计入不动作样本。"""
        events = self._events([])
        events.append(
            {
                "event": ledger.EVENT_DECISION,
                "decision_id": "d-legacy",
                "code": "600001",
                "name": "旧账本",
                "direction": ledger.DIRECTION_FLAT,
                "carrier": ledger.CARRIER_EXPERT_REVIEW,
                "report_date": "2026-10-01",
                "status": "pending",
            }
        )
        events.append(
            {
                "event": ledger.EVENT_SETTLEMENT,
                "decision_id": "d-legacy",
                "target_horizon": ledger.MIN_SETTLE_BARS,
                "raw_return": 0.01,
                "outcome": ledger.OUTCOME_FLAT,
            }
        )
        stats = ledger.fold_ledger(events=events)
        assert stats["inaction"]["total"] == 0
        assert stats["inaction"]["hit_rate"] is None

    def test_inaction_only_carrier_still_listed(self):
        """只有不动作样本的载体也要出现在 by_carrier（统计视图不缺行）。"""
        events = self._events([])
        events.append(
            {
                "event": ledger.EVENT_DECISION,
                "decision_id": "d-only-flat",
                "code": "600002",
                "name": "仅不动作",
                "direction": ledger.DIRECTION_FLAT,
                "carrier": ledger.CARRIER_REBALANCE,
                "report_date": "2026-11-01",
                "status": "pending",
            }
        )
        events.append(
            {
                "event": ledger.EVENT_SETTLEMENT,
                "decision_id": "d-only-flat",
                "target_horizon": ledger.MIN_SETTLE_BARS,
                "raw_return": 0.01,
                "outcome": ledger.OUTCOME_FLAT,
                "flat_hit": True,
            }
        )
        stats = ledger.fold_ledger(events=events)
        carrier = stats["by_carrier"][ledger.CARRIER_REBALANCE]
        assert carrier["directional"] == 0
        assert carrier["inaction_total"] == 1
