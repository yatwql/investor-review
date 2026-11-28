"""fee_schedule_model 残余分支 — 档位边界、连续性校验与配置档位合法性。

锁住的契约：
  - `_label_bounds` / `_amount_bounds` 对无边界文字与倒置边界一律判不可解析（不猜档位）；
    ``小于等于X元`` 的含端点语义以 +0.01 元右扩成半开区间；
  - `parse_*_fee_schedule` 在覆盖率不连续（末档非开区间）时整表判 None；
  - `_tiers_from_config` 对非 dict 条目、费率非数/布尔/非有限、末档带上界、
    中间档上界非严格递增一律整侧放弃（不拼半张表）；
  - `select_redemption_tier` / `select_purchase_tier` 对非 dict 档位与无命中返回 None；
  - `purchase_fee` 命中档位但既无固定费也无费率 → (None, None)。
"""

from __future__ import annotations

import pytest

from src.python.core.fee_schedule_model import (
    build_config_fee_schedules,
    parse_purchase_fee_schedule,
    parse_redemption_fee_schedule,
    purchase_fee,
    select_purchase_tier,
    select_redemption_tier,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestLabelBoundsRejection:
    """档位标签无边界 / 倒置时整行判不可解析。"""

    def test_redemption_label_without_bounds_returns_none(self):
        """赎回档位标签不含「大于/小于」边界 → 不可解析，整表 None。"""
        assert parse_redemption_fee_schedule([["持有期", "0.50%"]]) is None

    def test_purchase_amount_label_without_bounds_returns_none(self):
        """申购档位标签不含金额边界 → 不可解析，整表 None。"""
        assert parse_purchase_fee_schedule([["金额", "0.15%"]]) is None

    def test_purchase_inverted_bounds_returns_none(self):
        """下界 ≥ 上界（交叠/倒置）→ 不可解析，整表 None。"""
        assert parse_purchase_fee_schedule([["大于等于5000元，小于1000元", "0.15%"]]) is None


class TestPurchaseScheduleBounds:
    """`_amount_bounds` 的 ``---`` 与「小于等于」端点语义。"""

    def test_dash_label_yields_open_tier(self):
        """``---`` 标签 → (None, None) 全开区间档位（来源无分档时的合法形态）。"""
        schedule = parse_purchase_fee_schedule([["---", "0.15%"]])
        assert schedule is not None
        tier = schedule["tiers"][0]
        assert (tier["min_amount"], tier["max_amount"]) == (None, None)
        assert tier["rate"] == pytest.approx(0.0015)

    def test_less_or_equal_upper_bound_is_right_extended(self):
        """``小于等于5000元`` 的含端点语义 → 上界 5000.01；但末档非开区间 → 整表 None。"""
        assert parse_purchase_fee_schedule([["小于等于5000元", "0.15%"]]) is None


class TestConfigRedemptionTiers:
    """`_tiers_from_config` 的条目合法性闸门（非法即整侧放弃）。"""

    def test_non_dict_tier_rejected(self):
        """档位条目非 dict → 整侧 None，且无申购侧 → 整体 None。"""
        assert build_config_fee_schedules({"redemption_tiers": ["0.5%"]}) is None

    def test_boolean_rate_rejected(self):
        """费率为布尔（bool 是 int 子类，需显式排除）→ 整侧 None。"""
        assert build_config_fee_schedules({"redemption_tiers": [{"max_days": None, "rate": True}]}) is None

    def test_last_tier_must_be_open_ended(self):
        """末档带 max_days（右端有缺口）→ 整侧 None。"""
        assert build_config_fee_schedules({"redemption_tiers": [{"max_days": 30, "rate": 0.005}]}) is None

    def test_middle_tier_upper_bound_must_increase(self):
        """中间档上界未严格递增 → 整侧 None。"""
        assert (
            build_config_fee_schedules(
                {
                    "redemption_tiers": [
                        {"max_days": 30, "rate": 0.015},
                        {"max_days": 30, "rate": 0.005},
                        {"max_days": None, "rate": 0.0},
                    ]
                }
            )
            is None
        )

    def test_legal_tiers_built_with_contiguous_bounds(self):
        """合法两档：首档 min_days=None、次档 min_days=上一档上界、末档开区间。"""
        schedule = build_config_fee_schedules(
            {"redemption_tiers": [{"max_days": 7, "rate": 0.015}, {"max_days": None, "rate": 0.0}]}
        )
        assert schedule is not None
        tiers = schedule["redemption"]["tiers"]
        assert [(t["min_days"], t["max_days"]) for t in tiers] == [(None, 7), (7, None)]


class TestTierSelection:
    """档位选择对异常结构的拒绝与无命中口径。"""

    def test_redemption_tier_non_dict_rejected(self):
        """档位非 dict（结构损坏）→ None（不是跳过继续找）。"""
        assert select_redemption_tier({"tiers": ["7天0.5%"]}, 3) is None

    def test_redemption_no_tier_matched(self):
        """持有期超出最末档上界（表未覆盖）→ None。"""
        schedule = {"tiers": [{"min_days": None, "max_days": 7, "rate": 0.015}]}
        assert select_redemption_tier(schedule, 30) is None

    def test_purchase_tiers_not_list_returns_none(self):
        """``tiers`` 非列表 → None。"""
        assert select_purchase_tier({"tiers": "broken"}, 100.0) is None

    def test_purchase_tier_non_dict_rejected(self):
        """档位非 dict → None。"""
        assert select_purchase_tier({"tiers": [["0", "1000", 0.0015]]}, 100.0) is None

    def test_purchase_no_tier_matched(self):
        """金额超出最末档上界（表未覆盖）→ None。"""
        assert select_purchase_tier({"tiers": [{"min_amount": None, "max_amount": 100.0}]}, 500.0) is None

    def test_purchase_fee_without_rate_or_flat_fee(self):
        """命中档位但既无固定费也无费率 → (None, None)（不做 0 费冒充）。"""
        schedule = {"tiers": [{"min_amount": None, "max_amount": None, "rate": None, "flat_fee": None}]}
        assert purchase_fee(100.0, schedule) == (None, None)
