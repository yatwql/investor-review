"""配置章节校验器的降级分支：非法条目逐条告警并累计 issues（不抛错、不阻断加载）。

被覆盖的契约（每个用例断言「告警触发 + issues 增量」，即降级而非拒绝）：
  - 费率兑底表 / What-if 基准指数 / 基准指数表 / 对比指数池：键与值的类型守卫
  - rebalance 段：阈值区间、静默期、目标配置与股债配比的两层（条目 + 字段）类型守卫
  - discipline 段：静默期整数化失败降级
"""

from __future__ import annotations

import pytest

from src.python.config._validation_sections import (
    _validate_benchmark_indices,
    _validate_comparison_indices,
    _validate_discipline_config,
    _validate_fund_fee_fallback,
    _validate_history_fetch_mode,
    _validate_history_lookback_days,
    _validate_rebalance_config,
    _validate_whatif_benchmark_index,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


# ── 费率兑底表 ──────────────────────────────────────────


class TestFundFeeFallback:
    def test_invalid_code_and_invalid_entry_each_count_one(self):
        config = {
            "fund_fee_fallback": {
                "notacode": {"purchase_rate": 0.0015},
                123456: {"purchase_rate": 0.0015},  # int 键：非字符串 → 告警
                "000001": "not-a-dict",  # 条目不可解析 → 告警
            }
        }
        assert _validate_fund_fee_fallback(config, 0) == 3

    def test_section_absent_keeps_issue_count(self):
        assert _validate_fund_fee_fallback({}, 5) == 5


# ── What-if 基准指数 ────────────────────────────────────


class TestWhatifBenchmarkIndex:
    @pytest.mark.parametrize("value", [None, ""])
    def test_absent_or_empty_is_silent(self, value):
        assert _validate_whatif_benchmark_index({"whatif_benchmark_index": value}, 0) == 0

    def test_invalid_index_code_warns(self):
        assert _validate_whatif_benchmark_index({"whatif_benchmark_index": "not-an-index"}, 0) == 1

    def test_non_string_warns(self):
        assert _validate_whatif_benchmark_index({"whatif_benchmark_index": 300}, 2) == 3

    def test_valid_index_code_silent(self):
        assert _validate_whatif_benchmark_index({"whatif_benchmark_index": "sh000300"}, 0) == 0


# ── 基准 / 对比指数池 ───────────────────────────────────


class TestIndexPools:
    def test_benchmark_indices_with_non_dict_history_returns_unchanged(self):
        assert _validate_benchmark_indices({"history": ["x"]}, 4) == 4

    def test_benchmark_indices_invalid_key_and_value(self):
        config = {"history": {"benchmark_indices": {"sh": 1, "sh000300": 5}}}
        # "sh" 键过短 → 1；"sh000300" 值非字符串 → 1；"sh" 值非字符串 → 另 1
        assert _validate_benchmark_indices(config, 0) == 3

    def test_comparison_indices_invalid_key_and_value(self):
        config = {"comparison_indices": {"sz": "x", "sh000905": 7}}
        # "sz" 键过短 → 1；"sh000905" 值非字符串 → 1（"sz" 值为字符串，不再计数）
        assert _validate_comparison_indices(config, 0) == 2

    def test_comparison_indices_non_dict_section_counts_once(self):
        assert _validate_comparison_indices({"comparison_indices": []}, 0) == 1


# ── history 段 ─────────────────────────────────────────


class TestHistorySections:
    def test_fetch_mode_with_non_dict_history_returns_unchanged(self):
        assert _validate_history_fetch_mode({"history": "auto"}, 2) == 2

    def test_fetch_mode_invalid_value(self):
        assert _validate_history_fetch_mode({"history": {"fetch_mode": "sometimes"}}, 0) == 1

    def test_lookback_absent_is_silent(self):
        assert _validate_history_lookback_days({"history": {}}, 3) == 3


# ── rebalance 段 ───────────────────────────────────────


class TestRebalanceConfig:
    def test_threshold_and_deviation_non_numeric(self):
        config = {"rebalance": {"threshold": ["bad"], "deviation_threshold": None}}
        # threshold 列表 → TypeError；deviation_threshold=None 视为缺省（不校验）
        assert _validate_rebalance_config(config, 0) == 1

    def test_deviation_out_of_range_and_non_numeric(self):
        assert _validate_rebalance_config({"rebalance": {"deviation_threshold": 1.5}}, 0) == 1
        assert _validate_rebalance_config({"rebalance": {"deviation_threshold": {"x": 1}}}, 0) == 1

    def test_silence_days_non_integer(self):
        assert _validate_rebalance_config({"rebalance": {"silence_days": "很多天"}}, 0) == 1

    def test_target_allocation_entry_not_object(self):
        config = {"rebalance": {"target_allocation": {"equity": "half"}}}
        assert _validate_rebalance_config(config, 0) == 1

    def test_target_allocation_field_not_number(self):
        config = {"rebalance": {"target_allocation": {"equity": {"min": "0.1", "max": 0.6, "target": 0.3}}}}
        assert _validate_rebalance_config(config, 0) == 1

    def test_target_allocation_section_not_object(self):
        assert _validate_rebalance_config({"rebalance": {"target_allocation": [0.6, 0.4]}}, 0) == 1

    def test_equity_fixed_income_not_object(self):
        assert _validate_rebalance_config({"rebalance": {"equity_fixed_income": "60/40"}}, 0) == 1

    def test_equity_fixed_income_unknown_key_counts_once(self):
        config = {"rebalance": {"equity_fixed_income": {"bond": {"target": 0.4}}}}
        assert _validate_rebalance_config(config, 0) == 1

    def test_equity_fixed_income_entry_not_object(self):
        config = {"rebalance": {"equity_fixed_income": {"equity": 0.6}}}
        assert _validate_rebalance_config(config, 0) == 1

    def test_equity_fixed_income_field_not_number(self):
        config = {"rebalance": {"equity_fixed_income": {"equity": {"min": "0.3"}}}}
        assert _validate_rebalance_config(config, 0) == 1

    def test_valid_rebalance_section_is_silent(self):
        config = {
            "rebalance": {
                "threshold": 0.15,
                "deviation_threshold": 0.05,
                "silence_days": 30,
                "target_allocation": {"equity": {"min": 0.3, "max": 0.7, "target": 0.5}},
                "equity_fixed_income": {"equity": {"target": 0.6}, "fixed_income": {"target": 0.4}},
            }
        }
        assert _validate_rebalance_config(config, 0) == 0


# ── discipline 段 ──────────────────────────────────────


class TestDisciplineConfig:
    def test_silence_days_non_integer(self):
        assert _validate_discipline_config({"discipline": {"silence_days": "一个月"}}, 0) == 1

    def test_valid_discipline_section_is_silent(self):
        config = {"discipline": {"take_profit_pct": 20.0, "stop_loss_pct": -15.0, "silence_days": 30}}
        assert _validate_discipline_config(config, 0) == 0
