"""test_rebalance 兄弟分片（signals）：再平衡信号与误报保护。"""

from __future__ import annotations
import pytest
from src.python.analysis.rebalance import (
    build_holding_trading_days,
    compute_rebalance_signals,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestComputeRebalanceSignals:
    """再平衡信号入口函数测试。"""

    def test_no_holdings_returns_empty(self):
        assert compute_rebalance_signals(None, 0) == []
        assert compute_rebalance_signals([], 0) == []

    def test_single_overflow_within_threshold(self):
        holdings = [
            {"name": "A", "code": "600001", "market_value": 100},
            {"name": "B", "code": "600002", "market_value": 900},
        ]
        config = {"threshold": 0.9}
        result = compute_rebalance_signals(holdings, 1000, config)
        assert len(result) == 0  # 无品种超 90%

    def test_single_overflow(self):
        holdings = [
            {"name": "A", "code": "600001", "market_value": 300},
            {"name": "B", "code": "600002", "market_value": 700},
        ]
        config = {"threshold": 0.15}
        # B: 700/1000 = 70%, 超 15% 阈值
        result = compute_rebalance_signals(holdings, 1000, config)
        assert len(result) >= 1
        assert result[0]["type"] == "single_overflow"
        assert result[0]["code"] == "600002"

    def test_multiple_overflow_summary(self):
        """超过 3 个品种触发时聚合为一条汇总建议。"""
        holdings = [{"name": f"品种{i}", "code": f"60000{i}", "market_value": 250} for i in range(5)]
        # total = 1250, 每品种 250/1250 = 20%, 全部超 15%
        config = {"threshold": 0.15}
        result = compute_rebalance_signals(holdings, 1250, config)
        assert len(result) == 1
        assert result[0]["type"] == "summary"
        assert result[0]["summary"] is True
        assert result[0]["count"] == 5

    def test_rebalance_with_target_config(self):
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "债券A", "code": "008123", "market_value": 2000},
        ]
        config = {
            "threshold": 0.15,
            "target_allocation": {
                "equity": {"min": 30, "max": 60, "target": 50},
            },
        }
        result = compute_rebalance_signals(holdings, 10000, config)
        # 应有单品超限信号 (8000/10000=80% > 15%) + 目标偏离信号
        types = {r["type"] for r in result}
        assert "single_overflow" in types
        assert "category" in types

    def test_empty_config_defaults(self):
        """target_allocation 为空字典 → 无目标偏离信号，但单品超限仍独立触发。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 1000},
        ]
        result = compute_rebalance_signals(holdings, 1000, {"threshold": 0.5, "target_allocation": {}})
        # 单品超限独立于 target_allocation：1000/1000=100% > 50% → 触发
        assert len(result) == 1
        assert result[0]["type"] == "single_overflow"

    def test_rebalance_with_equity_fixed_income_config(self):
        """compute_rebalance_signals 集成 equity_fixed_income 配置。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "债券A", "code": "008123", "market_value": 2000},
        ]
        config = {
            "threshold": 0.15,
            "equity_fixed_income": {
                "equity": {"min": 30, "max": 70, "target": 60},
            },
        }
        result = compute_rebalance_signals(holdings, 10000, config)
        # 应有单品超限 (80%) + 权益/固收偏离 (equity=80% > 70%)
        types = {r["type"] for r in result}
        assert "single_overflow" in types
        assert "equity_fixed_income" in types

    def test_equity_fixed_income_empty_config_no_extra_signal(self):
        """equity_fixed_income 为空时无额外信号，其他信号不受影响。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5100},
        ]
        config = {"threshold": 0.5, "equity_fixed_income": {}}
        result = compute_rebalance_signals(holdings, 10000, config)
        # 单品超限仍独立触发 (51% > 50%)
        assert len(result) == 1
        assert result[0]["type"] == "single_overflow"


class TestComputeRebalanceSignalsProfile:
    """再平衡入口函数与预设阈值集集成测试。"""

    def test_conservative_profile_triggers_at_11pct(self):
        """保守预设（10% 阈值）对 11% 品种触发单品超限。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 220},
        ]
        # 220/2000 = 11% > 10% → 触发
        result = compute_rebalance_signals(holdings, 2000, {"profile": "conservative"})
        assert len(result) >= 1
        assert result[0]["type"] == "single_overflow"

    def test_moderate_profile_not_triggers_at_14pct(self):
        """稳健预设（15% 阈值）不触发 14% 的品种。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 280},
        ]
        # 280/2000 = 14% < 15% → 不触发
        result = compute_rebalance_signals(holdings, 2000, {"profile": "moderate"})
        assert len(result) == 0

    def test_moderate_profile_triggers_at_16pct(self):
        """稳健预设（15% 阈值）触发 16% 的品种。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 320},
        ]
        # 320/2000 = 16% > 15% → 触发
        result = compute_rebalance_signals(holdings, 2000, {"profile": "moderate"})
        assert len(result) >= 1
        assert result[0]["type"] == "single_overflow"

    def test_aggressive_profile_not_triggers_at_20pct(self):
        """进取预设（25% 阈值）不触发 20% 的品种。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 400},
        ]
        # 400/2000 = 20% < 25% → 不触发
        result = compute_rebalance_signals(holdings, 2000, {"profile": "aggressive"})
        assert len(result) == 0

    def test_aggressive_profile_triggers_at_30pct(self):
        """进取预设（25% 阈值）对 30% 品种触发。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 600},
        ]
        # 600/2000 = 30% > 25% → 触发
        result = compute_rebalance_signals(holdings, 2000, {"profile": "aggressive"})
        assert len(result) >= 1
        assert result[0]["type"] == "single_overflow"


class TestFalsePositiveProtection:
    """再平衡信号误报防护测试。"""

    def test_new_holding_filtered(self):
        """持仓不足 20 天的品种被过滤。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5000, "holding_days": 5},
        ]
        result = compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})
        # 50% > 15% 但持有仅 5 天 → 被过滤
        assert len(result) == 0

    def test_established_holding_not_filtered(self):
        """持仓超过 20 天时正常触发。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5000, "holding_days": 30},
        ]
        result = compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})
        assert len(result) >= 1
        assert result[0]["type"] == "single_overflow"

    def test_convertible_bond_near_maturity_annotated(self):
        """可转债触发时标注 near_maturity。"""
        holdings = [
            {"name": "XX转债", "code": "123456", "market_value": 5000},
        ]
        result = compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})
        assert len(result) >= 1
        assert result[0].get("near_maturity") is True

    def test_false_positive_flag_structure(self):
        """信号包含 shares_available 字段。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5000},
        ]
        result = compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})
        assert len(result) >= 1
        assert "shares_available" in result[0]
        assert result[0]["shares_available"] is False  # 测试中没有 shares 字段

    def test_shares_available_flag(self):
        """有 shares 字段时标记为 True。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5000, "shares": 100},
        ]
        result = compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})
        assert len(result) >= 1
        assert result[0]["shares_available"] is True


class TestBuildHoldingTradingDays:
    """交易流水 → 各品种持仓交易日数。"""

    @staticmethod
    def _tx(date: str, code: str, action: str = "buy"):
        from src.python.core.models import TradeRecord

        return TradeRecord(date=date, code=code, action=action, shares=100.0, price=1.0)

    def _calendar(self):
        from unittest.mock import patch

        return patch(
            "src.python.core.trading_calendar._get_trading_calendar",
            return_value={"2026-09-09", "2026-09-10", "2026-09-11"},
        )

    def test_counts_from_first_buy(self):
        """取最早一条买入记录为建仓日，按交易日计数（而非自然日）。"""
        tx = [
            self._tx("2026-09-10", "600001"),
            self._tx("2026-09-01", "600001"),  # 更早的买入 → 建仓日
            self._tx("2026-09-09", "600001"),
        ]
        with self._calendar():
            # 建仓日 2026-09-01 → 基准日 2026-09-11，经过 09-09/09-10/09-11 共 3 个交易日
            assert build_holding_trading_days(tx, "2026-09-11") == {"600001": 3}

    def test_normalizes_slash_date(self):
        """YYYY/MM/DD 形态归一化后参与计算。"""
        with self._calendar():
            assert build_holding_trading_days([self._tx("2026/09/09", "600001")], "2026-09-11") == {"600001": 2}

    def test_sell_only_code_excluded(self):
        """仅有卖出记录的品种不产出（未知则不参与观察期过滤）。"""
        with self._calendar():
            assert build_holding_trading_days([self._tx("2026-09-09", "600002", action="sell")], "2026-09-11") == {}

    def test_invalid_date_excluded(self):
        """日期非法的记录不产出。"""
        with self._calendar():
            assert build_holding_trading_days([self._tx("bad-date", "600003")], "2026-09-11") == {}

    def test_empty_transactions(self):
        """无交易流水 → 空字典（不误报也不误抑制）。"""
        assert build_holding_trading_days(None, "2026-09-11") == {}
        assert build_holding_trading_days([], "2026-09-11") == {}

    def test_observation_window_boundary(self):
        """阈值边界：19 个交易日过滤、20 个交易日放行。"""
        for holding_days, expected_count in ((19, 0), (20, 1)):
            holdings = [
                {"name": "A", "code": "600001", "market_value": 5000, "holding_days": holding_days},
            ]
            assert len(compute_rebalance_signals(holdings, 10000, {"threshold": 0.15})) == expected_count

    def test_reason_reports_trading_days(self):
        """过滤原因以交易日表述（回归：原实现措辞为「N 天」而判据实为交易日）。"""
        from src.python.analysis._rebalance_deviation import _apply_false_positive_protection

        signals = [{"code": "600001", "type": "single_overflow", "action": "减仓"}]
        holdings = [{"name": "A", "code": "600001", "holding_days": 3}]
        kept = _apply_false_positive_protection(signals, holdings)

        assert kept == []
        assert signals[0]["false_positive"] is True
        assert "3 个交易日" in signals[0]["false_positive_reason"]
        assert "不足 20 个交易日" in signals[0]["false_positive_reason"]
