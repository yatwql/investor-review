"""再平衡信号计算模块测试。

测试策略：
  - 单元测试验证各函数独立逻辑，mock config 隔离真实配置
  - edge 场景放入独立 _edge.py 文件
  - 使用 monkeypatch 隔离 get_config()"""

from __future__ import annotations
import datetime
import pytest
from src.python.analysis.rebalance import (
    _categorize_holdings,
    _calc_category_weights,
    _REBALANCE_PROFILES,
    _load_silence_state,
    _save_silence_state,
    classify_holding,
    resolve_rebalance_config,
)
from src.python.analysis.simple_rebalance import compute_simple_rebalance_signals

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _mk_holding(code: str, market_value: float, name: str = "") -> dict:
    """构造极简再平衡信号所需的持仓行。"""
    return {"code": code, "name": name or code, "market_value": market_value}


class TestSimpleRebalanceConfigThreshold:
    """compute_simple_rebalance_signals 配置化阈值。"""

    def test_explicit_threshold_lower_triggers_more(self):
        """显式收紧阈值 → 更多品种触发（10% 阈值下 12% 品种触发）。"""
        # 600001 占 12%、600002 占 8%：默认 15% 均合规，10% 阈值下 600001 触发
        holdings = [
            _mk_holding("600001", 1200.0),
            _mk_holding("600002", 800.0),
        ]
        signals = compute_simple_rebalance_signals(holdings, 10000.0, threshold=0.10)
        assert [s["code"] for s in signals] == ["600001"]

    def _single_overweight(self, code: str, mv: float, n_compliant: int = 7) -> list[dict]:
        """构造「1 只超重 + N 只合规」持仓集，总市值 10000。"""
        holdings = [_mk_holding(code, mv)]
        holdings.extend(_mk_holding(f"6000{n:02d}", 1000.0) for n in range(2, 2 + n_compliant))
        return holdings

    def test_explicit_threshold_higher_suppresses(self):
        """显式放宽阈值 → 原触发品种不再触发（25% 阈值下 20% 品种合规）。"""
        # 600001 占 20%（超 15%），其余各 10%（合规）：25% 阈值下全部合规
        holdings = self._single_overweight("600001", 2000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, threshold=0.25)
        assert signals == []

    def test_threshold_value_in_signal(self):
        """信号携带实际生效的 threshold 值（显式 0.12）。"""
        # 600001 占 20%（超 15%），其余各 10%：12% 阈值下 600001 触发
        holdings = self._single_overweight("600001", 2000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, threshold=0.12)
        assert signals[0]["threshold"] == 0.12
        assert {s["code"] for s in signals} == {"600001"}

    def test_default_threshold_still_15(self, monkeypatch):
        """未显式传阈值 → 默认 15%（0.15），20% 触发。"""
        holdings = self._single_overweight("600001", 2000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0)
        assert signals[0]["threshold"] == 0.15
        assert {s["code"] for s in signals} == {"600001"}

    def test_default_uses_config_silence(self, tmp_path):
        """未显式传静默期 → 默认读配置（30 天），静默期内品种被过滤。"""
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state({"600001": datetime.date.today().isoformat()}, f)
        holdings = self._single_overweight("600001", 2000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, silence_file=f)
        assert signals == []


class TestSimpleRebalanceSilence:
    """compute_simple_rebalance_signals 静默期过滤。"""

    def _single_overweight(self, code: str, mv: float, n_compliant: int = 7) -> list[dict]:
        """构造「1 只超重 + N 只合规」持仓集，总市值 10000。"""
        holdings = [_mk_holding(code, mv)]
        holdings.extend(_mk_holding(f"6000{n:02d}", 1000.0) for n in range(2, 2 + n_compliant))
        return holdings

    def test_signal_suppressed_within_silence(self, tmp_path):
        """静默期内品种被过滤（今天触发）。"""
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state({"600001": datetime.date.today().isoformat()}, f)
        # 600001 占 30%（超 15% 触发），其余各 10%（合规）
        holdings = self._single_overweight("600001", 3000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, silence_days=30, silence_file=f)
        assert signals == []

    def test_signal_passes_after_silence(self, tmp_path):
        """静默期到期后品种重新触发。"""
        past = datetime.date.today() - datetime.timedelta(days=31)
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state({"600001": past.isoformat()}, f)
        holdings = self._single_overweight("600001", 3000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, silence_days=30, silence_file=f)
        assert {s["code"] for s in signals} == {"600001"}

    def test_silence_zero_disables(self, tmp_path):
        """silence_days=0 → 不过滤、不写文件。"""
        f = str(tmp_path / "rebalance_silence.json")
        _save_silence_state({"600001": datetime.date.today().isoformat()}, f)
        holdings = self._single_overweight("600001", 3000.0)
        signals = compute_simple_rebalance_signals(holdings, 10000.0, silence_days=0, silence_file=f)
        assert {s["code"] for s in signals} == {"600001"}

    def test_silence_writes_state(self, tmp_path):
        """触发信号写入静默状态（下次同品种被抑制）。"""
        f = str(tmp_path / "rebalance_silence.json")
        holdings = self._single_overweight("600001", 3000.0)
        compute_simple_rebalance_signals(holdings, 10000.0, silence_days=30, silence_file=f)
        state = _load_silence_state(f)
        # 触发品种写入静默状态（600001 占 30% 超 15%）
        assert "600001" in state

    def test_silence_carries_summary_passthrough(self, tmp_path):
        """汇总信号不受静默期影响（未触发单品时汇总直接返回）。"""
        f = str(tmp_path / "rebalance_silence.json")
        # 5 只各占 22%：超过 _MAX_DETAILED=3 → 汇总；默认 15% 阈值
        holdings = [_mk_holding(f"60000{n}", 1100.0) for n in range(1, 6)]
        signals = compute_simple_rebalance_signals(holdings, 5000.0, silence_days=30, silence_file=f)
        assert signals == [
            {
                "summary": True,
                "count": 5,
                "message": "您的组合集中度较高，有 5 个品种超过 15% 警戒线，建议整体考虑适度分散",
            }
        ]


class TestClassifyHolding:
    """资产分类函数测试。"""

    def test_a_share_stock(self):
        assert classify_holding("贵州茅台", "600519") == "equity"

    def test_hk_stock(self):
        assert classify_holding("腾讯控股", "00700") == "equity"

    def test_bond_fund(self):
        assert classify_holding("XX纯债债券A", "008123") == "fixed_income"

    def test_money_fund(self):
        assert classify_holding("余额宝货币", "000001") == "money_market"

    def test_qdii(self):
        assert classify_holding("纳斯达克100QDII", "513100") == "qdii"

    def test_convertible_bond(self):
        assert classify_holding("XX转债", "123456") == "alternative"

    def test_etf_equity(self):
        assert classify_holding("沪深300ETF", "510300") == "equity"

    def test_etf_bond(self):
        assert classify_holding("XX国债ETF", "511000") == "fixed_income"

    def test_index_fund(self):
        assert classify_holding("XX沪深300指数", "001234") == "fund_equity"

    def test_money_etf(self):
        assert classify_holding("华宝添益ETF", "511990") == "money_market"

    def test_otc_equity_fund(self):
        assert classify_holding("XX灵活配置混合", "002345") == "fund_equity"


class TestCategorizeHoldings:
    """分类汇总逻辑测试。"""

    def test_categorize_single_type(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 10000},
            {"name": "腾讯控股", "code": "00700", "market_value": 5000},
        ]
        result = _categorize_holdings(holdings)
        assert len(result["equity"]) == 2
        assert sum(1 for items in result.values() for _ in items) == 2

    def test_categorize_mixed(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 10000},
            {"name": "XX纯债债券A", "code": "008123", "market_value": 5000},
            {"name": "余额宝货币", "code": "000001", "market_value": 3000},
        ]
        result = _categorize_holdings(holdings)
        assert len(result["equity"]) == 1
        assert len(result["fixed_income"]) == 1
        assert len(result["money_market"]) == 1

    def test_empty_input(self):
        result = _categorize_holdings([])
        assert all(len(items) == 0 for items in result.values())

    def test_weight_calculation(self):
        holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 10000},
            {"name": "XX纯债债券A", "code": "008123", "market_value": 5000},
        ]
        categorized = _categorize_holdings(holdings)
        weights = _calc_category_weights(categorized, 15000)
        assert weights["equity"] == pytest.approx(66.67, rel=0.01)
        assert weights["fixed_income"] == pytest.approx(33.33, rel=0.01)

    def test_weight_zero_total(self):
        weights = _calc_category_weights({}, 0)
        assert all(w == 0.0 for w in weights.values())


class TestResolveRebalanceConfig:
    """预设阈值集解析测试。"""

    def test_none_config_uses_defaults(self):
        result = resolve_rebalance_config(None)
        assert result["threshold"] == 0.15
        assert result["deviation_threshold"] == 0.05

    def test_conservative_profile(self):
        result = resolve_rebalance_config({"profile": "conservative"})
        assert result["threshold"] == _REBALANCE_PROFILES["conservative"]["threshold"]
        assert result["deviation_threshold"] == _REBALANCE_PROFILES["conservative"]["deviation_threshold"]

    def test_aggressive_profile(self):
        result = resolve_rebalance_config({"profile": "aggressive"})
        assert result["threshold"] == _REBALANCE_PROFILES["aggressive"]["threshold"]
        assert result["deviation_threshold"] == _REBALANCE_PROFILES["aggressive"]["deviation_threshold"]

    def test_custom_profile_no_override(self):
        """custom 模式不使用 preset，使用 config 中的值或默认值。"""
        result = resolve_rebalance_config({"profile": "custom", "threshold": 0.20})
        assert result["threshold"] == 0.20
        assert result["deviation_threshold"] == 0.05  # 默认值

    def test_explicit_values_override_preset(self):
        """显式指定的值优先于预设。"""
        result = resolve_rebalance_config(
            {
                "profile": "conservative",
                "threshold": 0.12,  # 覆盖 conservative 的 0.10
            }
        )
        assert result["threshold"] == 0.12
        # deviation_threshold 未显式指定 → 使用 preset
        assert result["deviation_threshold"] == _REBALANCE_PROFILES["conservative"]["deviation_threshold"]

    def test_moderate_profile_default(self):
        """默认 profile 为 moderate。"""
        result = resolve_rebalance_config({})
        assert result["threshold"] == _REBALANCE_PROFILES["moderate"]["threshold"]
        assert result["deviation_threshold"] == _REBALANCE_PROFILES["moderate"]["deviation_threshold"]

    def test_target_allocation_preserved(self):
        result = resolve_rebalance_config(
            {
                "profile": "aggressive",
                "target_allocation": {"equity": {"min": 20, "max": 80}},
            }
        )
        assert "equity" in result["target_allocation"]
