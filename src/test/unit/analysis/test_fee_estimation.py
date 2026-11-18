"""组合综合费率估算（`analysis/_fee_estimation.py`）——类型归类与加权口径。

纯函数：类型判定按名称关键词优先、代码特征兜底；费率由市值权重加权，
未知类型计默认费率并在 `warning` 里如实说明，不静默当成已知类型。
"""

from __future__ import annotations

import pytest

from src.python.analysis._fee_estimation import _classify_fund_type, portfolio_fee_estimation

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

_DEFAULT_RATE = 0.010


class TestClassifyFundType:
    @pytest.mark.parametrize(
        ("name", "code", "label"),
        [
            ("某某货币基金", "000001", "money_market"),
            ("某某纯债债券", "000002", "bond"),
            ("沪深300指数增强", "000003", "equity_index"),
            ("某某价值精选混合", "000004", "equity"),
            ("某某半导体主题", "000005", "equity_sector"),
            ("某某纳斯达克QDII", "000006", "equity_qdii"),
        ],
    )
    def test_keyword_rules_win_over_code(self, name, code, label):
        assert _classify_fund_type(name, code)[0] == label

    def test_a_share_code_without_keyword_is_stock(self):
        """名称无关键词时按代码特征兜底：6 位 A 股代码 → 股票费率。"""
        label, rate = _classify_fund_type("某某股份", "600519")
        assert label == "stock"
        assert rate < _DEFAULT_RATE

    def test_unknown_code_falls_back_to_default_rate(self):
        label, rate = _classify_fund_type("某某未知品种", "????")
        assert label == "unknown"
        assert rate == _DEFAULT_RATE

    def test_code_is_normalized_before_classification(self):
        """代码带空格/小写也要能识别（归一在大写 strip 之后判定）。"""
        assert _classify_fund_type("某某股份", " 600519 ")[0] == "stock"


class TestPortfolioFeeEstimation:
    def test_reports_no_data_without_holdings(self):
        result = portfolio_fee_estimation([], 1000.0)
        assert result["has_data"] is False
        assert result["fee_rate"] is None
        assert "持仓数据不足" in result["warning"]

    def test_reports_no_data_when_total_mv_not_positive(self):
        assert (
            portfolio_fee_estimation([{"name": "货币基金", "code": "000001", "market_value": 10.0}], 0.0)["has_data"]
            is False
        )

    def test_all_zero_market_values_reports_no_data(self):
        result = portfolio_fee_estimation([{"name": "某债券", "code": "000002", "market_value": 0.0}], 1000.0)
        assert result["has_data"] is False
        assert "市值均为零" in result["warning"]

    def test_weighted_rate_and_annual_fee(self):
        holdings = [
            {"name": "某某货币基金", "code": "000001", "market_value": 500.0},
            {"name": "某某纯债债券", "code": "000002", "market_value": 500.0},
        ]
        result = portfolio_fee_estimation(holdings, 1000.0)
        rates = {row["品种名称"]: row["fee_rate"] for row in result["fee_breakdown"]}
        expected = sum(0.5 * rate for rate in rates.values())
        assert result["fee_rate"] == pytest.approx(expected, abs=1e-9)
        assert result["annual_fee"] == pytest.approx(1000.0 * result["fee_rate"], abs=1e-6)
        assert sum(row["weight"] for row in result["fee_breakdown"]) == pytest.approx(1.0, abs=1e-6)

    def test_zero_value_item_is_excluded_from_breakdown(self):
        holdings = [
            {"name": "某某货币基金", "code": "000001", "market_value": 1000.0},
            {"name": "某某纯债债券", "code": "000002", "market_value": 0.0},
        ]
        result = portfolio_fee_estimation(holdings, 1000.0)
        assert [row["品种名称"] for row in result["fee_breakdown"]] == ["某某货币基金"]

    def test_unknown_type_raises_warning_with_default_rate(self):
        result = portfolio_fee_estimation([{"name": "奇怪品种", "code": "????", "market_value": 1000.0}], 1000.0)
        assert result["fee_rate"] == pytest.approx(_DEFAULT_RATE, abs=1e-9)
        assert "默认费率" in result["warning"]

    def test_known_types_produce_no_warning(self):
        result = portfolio_fee_estimation([{"name": "某某货币基金", "code": "000001", "market_value": 1000.0}], 1000.0)
        assert result["warning"] is None

    def test_name_falls_back_to_code_in_label(self):
        result = portfolio_fee_estimation([{"name": "", "code": "600519", "market_value": 1000.0}], 1000.0)
        assert result["fee_breakdown"][0]["品种名称"] == "600519"

    def test_missing_market_value_key_skips_item(self):
        result = portfolio_fee_estimation([{"name": "某某货币基金", "code": "000001"}], 1000.0)
        assert result["has_data"] is False
