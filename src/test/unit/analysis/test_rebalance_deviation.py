"""test_rebalance 兄弟分片（deviation）：目标偏离度与股债偏离。"""

from __future__ import annotations
import datetime
import pytest
from src.python.analysis.rebalance import (
    compute_target_deviation,
    equity_fixed_income_deviation,
    compute_rebalance_signals,
)
from src.python.analysis._silence import _filter_silenced_signals, _load_silence_state, _save_silence_state
from src.python.analysis._rebalance_deviation import _compute_confidence

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestComputeTargetDeviation:
    """目标配置偏离度计算测试。"""

    def test_no_target_allocation_returns_empty(self):
        result = compute_target_deviation(
            [{"name": "茅台", "code": "600519", "market_value": 10000}],
            10000,
            {},
        )
        assert result == []

    def test_within_target_range(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 5000},
            {"name": "XX纯债债券", "code": "008123", "market_value": 5000},
        ]
        target = {
            "equity": {"min": 30, "max": 70, "target": 50},
            "fixed_income": {"min": 20, "max": 50, "target": 35},
        }
        result = compute_target_deviation(holdings, 10000, target)
        # 权益 50%、固收 50% — 权益在范围内，固收超上限 50>50? 等于 max 不超出
        # deviation = 50 - 35 = 15 > 5 → 有信号
        assert len(result) >= 1
        # 固收 50% = max 50%，在范围内
        dev_types = [r["type"] for r in result]
        assert "category" in dev_types

    def test_equity_overweight(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 8000},
            {"name": "XX纯债债券", "code": "008123", "market_value": 2000},
        ]
        target = {
            "equity": {"min": 30, "max": 60, "target": 50},
        }
        result = compute_target_deviation(holdings, 10000, target)
        assert len(result) >= 1
        r = result[0]
        assert r["type"] == "category"
        assert r["current_weight"] == 80.0
        assert r["deviation"] > 0

    def test_security_level_target(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 20000},
            {"name": "XX债券", "code": "008123", "market_value": 8000},
        ]
        target = {
            "600519": {"min": 5, "max": 15, "target": 10},
        }
        result = compute_target_deviation(holdings, 28000, target)
        assert len(result) >= 1
        r = result[0]
        assert r["type"] == "security"
        assert r["code"] == "600519"

    def test_empty_holdings(self):
        result = compute_target_deviation(None, 0, {"equity": {"min": 0, "max": 100}})
        assert result == []


class TestComputeTargetDeviationThreshold:
    """偏离度阈值配置测试。"""

    def test_tight_threshold_detects_small_deviation(self):
        """严格阈值（1%）能检测到小偏离。"""
        holdings = [
            {"name": "A", "code": "600001", "market_value": 5500},
            {"name": "B", "code": "600002", "market_value": 4500},
        ]
        target = {"equity": {"min": 0, "max": 100, "target": 50}}
        # 偏离 = 5% > 1% 阈值 → 应有信号
        result = compute_target_deviation(holdings, 10000, target, deviation_threshold=0.01)
        assert len(result) >= 1
        assert result[0]["type"] == "category"

    def test_loose_threshold_suppresses_small_deviation(self):
        """宽松阈值（10%）忽略 2% 的小偏离。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 5200},
            {"name": "债券A", "code": "008123", "market_value": 4800},
        ]
        target = {"equity": {"min": 0, "max": 100, "target": 50}}
        # equity=52%, deviation=2%, 2% < 10% 阈值且在范围 0-100 内 → 无信号
        result = compute_target_deviation(holdings, 10000, target, deviation_threshold=0.10)
        assert result == []

    def test_security_level_tight_threshold(self):
        """品种级偏离也受 deviation_threshold 控制。"""
        holdings = [
            {"name": "茅台", "code": "600519", "market_value": 6000},
            {"name": "B", "code": "600002", "market_value": 4000},
        ]
        target = {"600519": {"min": 0, "max": 100, "target": 50}}
        # 偏离 = 10% > 8% 阈值 → 信号
        result = compute_target_deviation(holdings, 10000, target, deviation_threshold=0.08)
        assert len(result) >= 1
        assert result[0]["type"] == "security"

    def test_security_level_loose_threshold(self):
        holdings = [
            {"name": "茅台", "code": "600519", "market_value": 6000},
            {"name": "B", "code": "600002", "market_value": 4000},
        ]
        target = {"600519": {"min": 0, "max": 100, "target": 50}}
        # 偏离 = 10% < 15% 阈值 → 无信号
        result = compute_target_deviation(holdings, 10000, target, deviation_threshold=0.15)
        assert result == []


class TestEquityFixedIncomeDeviation:
    """权益/固收超大类偏离信号计算测试。"""

    def test_empty_holdings_returns_empty(self):
        """空持仓返回空列表。"""
        assert equity_fixed_income_deviation(None, 0, {"equity": {"min": 0, "max": 100}}) == []
        assert equity_fixed_income_deviation([], 0, {"equity": {"min": 0, "max": 100}}) == []

    def test_no_target_returns_empty(self):
        """目标配置为空字典时返回空列表。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "债券A", "code": "008123", "market_value": 2000},
        ]
        assert equity_fixed_income_deviation(holdings, 10000, {}) == []

    def test_equity_above_max_triggers_signal(self):
        """权益类超上限时触发信号。"""
        # 纯权益类持仓：全部归入 equity (equity + fund_equity + qdii)
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "混合基金", "code": "001234", "market_value": 2000},
        ]
        target = {"equity": {"min": 30, "max": 70, "target": 60}}
        # equity 聚合 = 100% (8000 + 2000) / 10000 → 超出 max 70%
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert result[0]["type"] == "equity_fixed_income"
        assert result[0]["group"] == "equity"
        assert result[0]["current_weight"] == 100.0
        assert result[0]["deviation"] > 0  # 超配

    def test_equity_below_min_triggers_signal(self):
        """权益类低于下限时触发信号。"""
        # 大部分是固收，小部分是权益
        holdings = [
            {"name": "债券A", "code": "008123", "market_value": 9000},
            {"name": "A股", "code": "600001", "market_value": 1000},
        ]
        target = {"equity": {"min": 30, "max": 80, "target": 50}}
        # equity = 1000/10000 = 10% < 30% 下限
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert result[0]["group"] == "equity"
        assert result[0]["deviation"] < 0  # 低配

    def test_fixed_income_above_max_triggers_signal(self):
        """固收类超上限时触发信号。"""
        holdings = [
            {"name": "XX纯债债券A", "code": "008123", "market_value": 7000},
            {"name": "XX货币A", "code": "000001", "market_value": 2000},
            {"name": "A股", "code": "600001", "market_value": 1000},
        ]
        target = {"fixed_income": {"min": 20, "max": 60, "target": 40}}
        # fixed_income = fixed_income(7000) + money_market(2000) = 9000/10000 = 90%
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert result[0]["group"] == "fixed_income"
        assert result[0]["current_weight"] == 90.0
        assert result[0]["deviation"] > 0

    def test_both_groups_within_target_no_signal(self):
        """权益和固收均在目标范围内时无信号。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 3000},
            {"name": "XX纯债债券A", "code": "008123", "market_value": 5000},
            {"name": "XX货币A", "code": "000001", "market_value": 2000},
        ]
        target = {
            "equity": {"min": 20, "max": 50, "target": 30},
            "fixed_income": {"min": 50, "max": 80, "target": 70},
        }
        # equity = 30%, fixed_income = 70%, 均在范围内
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert result == []

    def test_deviation_below_threshold_suppressed(self):
        """偏离低于阈值且未超限时不输出信号。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 5200},
            {"name": "债券A", "code": "008123", "market_value": 4800},
        ]
        target = {"equity": {"min": 0, "max": 100, "target": 50}}
        # equity = 52%, deviation = 2% < 5% threshold
        result = equity_fixed_income_deviation(holdings, 10000, target, deviation_threshold=0.05)
        assert result == []

    def test_mixed_holdings_correct_aggregation(self):
        """混合持仓正确汇总权益和固收大类。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 4000},  # equity
            {"name": "XX混合A", "code": "001234", "market_value": 1000},  # fund_equity
            {"name": "标普QDII", "code": "513100", "market_value": 1000},  # qdii
            {"name": "XX纯债债券A", "code": "008123", "market_value": 2000},  # fixed_income
            {"name": "XX货币A", "code": "000001", "market_value": 1000},  # money_market
            {"name": "XX转债", "code": "123456", "market_value": 1000},  # alternative
        ]
        total = 10000
        # equity 聚合 = 4000+1000+1000 = 6000 → 60%
        # fixed_income 聚合 = 2000+1000+1000 = 4000 → 40%
        target = {
            "equity": {"min": 40, "max": 80, "target": 60},
            "fixed_income": {"min": 20, "max": 60, "target": 40},
        }
        result = equity_fixed_income_deviation(holdings, total, target)
        # 60% / 40% 均在范围内 → 无信号
        assert result == []

    def test_mixed_aggregation_detects_deviation(self):
        """混合持仓正确检测权益/固收偏离。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 5000},  # equity
            {"name": "XX混合A", "code": "001234", "market_value": 2000},  # fund_equity
            {"name": "XX纯债债券A", "code": "008123", "market_value": 2000},  # fixed_income
            {"name": "XX货币A", "code": "000001", "market_value": 1000},  # money_market
        ]
        total = 10000
        # equity 聚合 = 5000+2000 = 7000 → 70%
        # fixed_income 聚合 = 2000+1000 = 3000 → 30%
        target = {
            "equity": {"min": 30, "max": 60, "target": 50},  # 70% > 60%
            "fixed_income": {"min": 40, "max": 70, "target": 50},  # 30% < 40%
        }
        result = equity_fixed_income_deviation(holdings, total, target)
        # 两个大类均偏离 → 应有 2 个信号
        assert len(result) == 2
        types = {r["group"] for r in result}
        assert types == {"equity", "fixed_income"}

    def test_signal_format(self):
        """信号包含完整字段。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "XX纯债债券A", "code": "008123", "market_value": 1000},
            {"name": "XX货币A", "code": "000001", "market_value": 1000},
        ]
        target = {"equity": {"min": 30, "max": 60, "target": 50}}
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        sig = result[0]
        assert "type" in sig
        assert "group" in sig
        assert "group_label" in sig
        assert "current_weight" in sig
        assert "target_weight" in sig
        assert "min" in sig
        assert "max" in sig
        assert "deviation" in sig
        assert "confidence" in sig
        assert "action" in sig

    def test_equity_only_target(self):
        """仅配置 equity 目标时，只检查权益类偏离。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 5000},
            {"name": "债券A", "code": "008123", "market_value": 5000},
        ]
        target = {"equity": {"min": 40, "max": 60, "target": 50}}
        # equity = 50%, 在范围内 → 无信号
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert result == []

    def test_only_fixed_income_target(self):
        """仅配置 fixed_income 目标时，只检查固收类偏离。"""
        holdings = [
            {"name": "债券A", "code": "008123", "market_value": 9000},
            {"name": "A股", "code": "600001", "market_value": 1000},
        ]
        target = {"fixed_income": {"min": 30, "max": 60, "target": 50}}
        # fixed_income = 90% > 60% → 触发
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert result[0]["group"] == "fixed_income"
        assert result[0]["current_weight"] == 90.0

    def test_tight_threshold_detects_small_deviation(self):
        """严格阈值（1%）检测小偏离。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 5100},
            {"name": "债券A", "code": "008123", "market_value": 4900},
        ]
        target = {"equity": {"min": 0, "max": 100, "target": 50}}
        # equity = 51%, deviation = 1% > 1% → 触发（未超限但偏离超阈值）
        result = equity_fixed_income_deviation(holdings, 10000, target, deviation_threshold=0.01)
        assert len(result) >= 1
        assert result[0]["group"] == "equity"
        assert abs(result[0]["deviation"]) == 1.0

    def test_confidence_high_for_large_deviation(self):
        """大偏离 → 高置信度。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 9000},
            {"name": "债券A", "code": "008123", "market_value": 1000},
        ]
        target = {"equity": {"min": 30, "max": 60, "target": 50}}
        # equity = 90%, deviation = 40% > 10% (2×5% threshold) → high
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert result[0]["confidence"] == "high"

    def test_action_text_for_overweight(self):
        """超配时 action 包含降配建议。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 8000},
            {"name": "债券A", "code": "008123", "market_value": 2000},
        ]
        target = {"equity": {"min": 30, "max": 70, "target": 60}}
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert "超过目标上限" in result[0]["action"]

    def test_action_text_for_underweight(self):
        """低配时 action 包含增配建议。"""
        holdings = [
            {"name": "A股", "code": "600001", "market_value": 1000},
            {"name": "债券A", "code": "008123", "market_value": 9000},
        ]
        target = {"equity": {"min": 30, "max": 70, "target": 60}}
        result = equity_fixed_income_deviation(holdings, 10000, target)
        assert len(result) >= 1
        assert "低于目标下限" in result[0]["action"]


class TestConfidence:
    """再平衡信号置信度计算测试。"""

    def test_single_overflow_high_confidence(self):
        """weight 超过 2× threshold → high。"""
        conf = _compute_confidence("single_overflow", deviation=45.0, threshold=0.15)
        # 45% > 30% (2×15%) → high
        assert conf == "high"

    def test_single_overflow_medium_confidence(self):
        """weight 超过 threshold 但未达 2× → medium。"""
        conf = _compute_confidence("single_overflow", deviation=20.0, threshold=0.15)
        # 20% > 15% but 20% < 30% (2×15%) → medium
        assert conf == "medium"

    def test_category_high_confidence(self):
        """偏离 > 2× deviation_threshold → high。"""
        conf = _compute_confidence("category", deviation=15.0, deviation_threshold_pct=5.0)
        # 15% > 10% (2×5%) → high
        assert conf == "high"

    def test_category_medium_confidence(self):
        """偏离 > threshold < 2× threshold → medium。"""
        conf = _compute_confidence("category", deviation=8.0, deviation_threshold_pct=5.0)
        # 8% > 5% but 8% < 10% → medium
        assert conf == "medium"

    def test_category_low_confidence(self):
        """偏离 < threshold → low。"""
        conf = _compute_confidence("category", deviation=3.0, deviation_threshold_pct=5.0)
        assert conf == "low"


class TestSilencePeriod:
    """再平衡信号静默期机制测试。"""

    def test_load_empty_state(self):
        """无静默期文件时返回空字典。"""
        state = _load_silence_state("/tmp/nonexistent_silence_test.json")
        assert state == {}

    def test_save_and_load(self, tmp_path):
        """写入后可恢复读取。"""
        f = str(tmp_path / "rebalance_silence.json")
        state = {"600001": "2026-07-01", "600002": "2026-07-15"}
        _save_silence_state(state, f)
        loaded = _load_silence_state(f)
        assert loaded == state

    def test_save_corrupted_file_returns_empty(self, tmp_path):
        """损坏的 JSON 文件返回空字典。"""
        f = str(tmp_path / "rebalance_silence.json")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("not json")
        state = _load_silence_state(f)
        assert state == {}

    def test_filter_within_silence(self, tmp_path):
        """静默期内的品种被过滤。"""
        today = datetime.date.today()
        silences = {"600001": today.isoformat()}  # 今天触发 → 静默期内
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state(silences, f)

        signals = [
            {"type": "single_overflow", "code": "600001", "name": "A", "weight": 30.0},
        ]
        result = _filter_silenced_signals(signals, silence_days=30, silence_file=f)
        assert result == []

    def test_filter_category_not_silenced(self, tmp_path):
        """大类偏离信号不受静默期影响。"""
        today = datetime.date.today()
        silences = {"equity": today.isoformat()}
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state(silences, f)

        signals = [
            {"type": "category", "category": "equity", "deviation": 5.0},
        ]
        result = _filter_silenced_signals(signals, silence_days=30, silence_file=f)
        # category signals pass through regardless of silence state
        assert len(result) == 1

    def test_summary_not_silenced(self, tmp_path):
        """汇总信号不受静默期影响。"""
        signals = [
            {"type": "summary", "summary": True, "count": 3},
        ]
        result = _filter_silenced_signals(signals, silence_days=30, silence_file=str(tmp_path / "s.json"))
        assert len(result) == 1

    def test_expired_silence_allows_through(self, tmp_path):
        """静默期到期后品种重新触发，过期条目被清理。"""
        past = datetime.date.today() - datetime.timedelta(days=31)
        silences = {"600001": past.isoformat()}  # 31 天前 → 已过期
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state(silences, f)

        signals = [
            {"type": "single_overflow", "code": "600001", "name": "A", "weight": 30.0},
        ]
        result = _filter_silenced_signals(signals, silence_days=30, silence_file=f)
        assert len(result) == 1
        # 过期条目应从状态中清理
        remaining = _load_silence_state(f)
        assert "600001" not in remaining

    def test_update_silence_state_records_new(self, tmp_path):
        """新触发的信号写入静默期状态后再触发被过滤。"""
        f = str(tmp_path / "rebalance_silence.json")
        config = {"profile": "moderate", "_silence_file": f}
        holdings = [{"name": "A", "code": "600001", "market_value": 500}]
        # 第一次应触发
        result = compute_rebalance_signals(holdings, 1000, config)
        assert len(result) == 1
        # 第二次应被静默过滤
        result2 = compute_rebalance_signals(holdings, 1000, config)
        assert len(result2) == 0
