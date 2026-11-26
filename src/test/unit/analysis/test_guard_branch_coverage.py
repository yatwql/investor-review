"""分析层小缺口分支补齐：各模块的守卫早退与降级分支。

集中覆盖「每文件仅缺数行」的守卫分支——这些分支平时只在异常/边界输入下走到，
单文件单用例即可闭合，集中一处便于按模块定位：

  - 类型/代码识别与基准映射：美股字母代码、空代码与空基准文本跳过
  - 相关性/波动/夏普/月收益：样本过短与空序列的早退（不产出伪指标）
  - 因子横截面：非数值标量、样本不足、K 线短于 min_bars
  - 财务指标解析：不可解析 token、非有限值、报告期格式异常
  - 行业 beta：空表/单点/常数序列 → None
  - 市场情绪：非 dict 条目跳过、资产自带 code 入池
  - 流动性评分/景气度：assumed_liquid 计入未验证说明
  - 再平衡：空代码流水跳过、债券/货币 ETF 与场外债基归类
  - 尾部风险：空收益序列、跌前市值缺失、越界取日期
"""

from __future__ import annotations

import pytest

from src.python.analysis import (
    correlation,
    drawdown_warning,
    financial_indicator_extract as fie,
    financial_statement_derive as fsd,
    industry_beta,
    market_sentiment,
    metrics_returns,
    metrics_risk,
    monthly_returns,
    prosperity_scoring,
    prosperity_signals,
    purchase_feasibility,
    rebalance,
    rebalance_advisor,
    tail_risk,
    whatif,
)
from src.python.analysis import _fee_estimation
from src.python.analysis import factor_evaluator as fe
from src.python.analysis import benchmark_index_resolver as bir
from src.python.core.models import Holding
from src.python.schemas.factor_catalog import CATALOG

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _catalog_entry(slug: str) -> dict:
    return dict(next(e for e in CATALOG if e["slug"] == slug))


# ── 类型识别与基准映射 ──────────────────────────────────


class TestTypeAndBenchmarkMapping:
    def test_letter_based_code_classified_as_stock(self):
        """美股字母代码（既非 A 股也非 5 位港股）判为股票费率。"""
        label, rate = _fee_estimation._classify_fund_type("", "AAPL")
        assert label == "stock"
        assert rate == pytest.approx(_fee_estimation._STOCK_FEE_RATE)

    def test_blank_code_and_blank_benchmark_text_fall_back_to_default(self):
        """持仓代码为空/基准文本为空时跳过该持仓，最终回落宽基默认。"""
        result = bir.resolve_benchmark_index(
            [{"code": "", "cost": 99.0}, {"code": "000001", "cost": 1.0}],
            comparison_indices={"sh000300": "沪深300"},
            benchmark_text_getter=lambda code: "",
        )
        assert result["source"] == bir.SOURCE_DEFAULT
        assert result["code"] == bir.DEFAULT_BENCHMARK_INDEX


# ── 相关性 / 收益指标早退 ──────────────────────────────


class TestStatGuardBranches:
    def test_pvalue_and_r_short_series(self):
        """样本 <3 时 p 值固定 (0.0, 1.0)、r 为 None（无法判定线性关系）。"""
        assert correlation._pearson_pvalue([1.0, 2.0], [2.0, 3.0]) == (0.0, 1.0)
        assert correlation._pearson_r([1.0, 2.0], [2.0, 3.0]) is None

    def test_rolling_correlations_without_any_return(self):
        """无有效收益（代码序列为空）→ 滚动相关不可用，不抛错。"""
        result = correlation.compute_rolling_correlations({"600000": []})
        assert result["available"] is False
        assert result["status"] == "insufficient"
        assert set(result["windows"]) == set(correlation.ROLLING_WINDOWS)

    def test_daily_returns_and_truncate_on_empty_input(self):
        assert metrics_returns.compute_daily_returns(None) == []
        assert metrics_returns.truncate_extreme_values([]) == []

    def test_sharpe_single_sample_returns_none(self):
        """单个样本：充分性通过但无法算标准差 → None（不产出伪夏普）。"""
        assert metrics_returns.sharpe_ratio([0.012]) is None

    def test_risk_contribution_treats_unclean_value_as_zero(self):
        """权重/波动率经 sanitize 后为 None 的项按 0 计入，不中断聚合（贡献度合计仍为 1）。"""
        result = metrics_risk.risk_contribution([None, 1.0], [0.1, 0.2])
        assert {item["index"]: item["weight"] for item in result}[1] == pytest.approx(1.0)
        assert [item["index"] for item in result] == [1, 0]
        assert sum(item["contribution"] for item in result) == pytest.approx(1.0, abs=1e-6)

    def test_portfolio_beta_short_series_returns_none(self):
        assert metrics_risk.portfolio_beta([0.01, 0.02], [0.01, 0.02]) is None

    def test_monthly_returns_unavailable_without_valued_month(self):
        """只有一根 bar → 无月度收益可取，返回不可用形态（键集与可用形态一致）。"""
        result = monthly_returns.aggregate_monthly_returns([{"date": "2026-01-05", "total_value": 100.0}])
        assert result["available"] is False
        assert result["stats"] is None

    def test_compute_drawdown_warning_normal_level(self):
        """当前回撤就是历史最深值（回撤分位最低）→ 无预警阈值触发，级别回落 normal。"""
        bars = [
            {"date": "2026-01-05", "drawdown_pct": 0.0},
            {"date": "2026-01-06", "drawdown_pct": -0.05},
            {"date": "2026-01-07", "drawdown_pct": -0.10},
            {"date": "2026-01-08", "drawdown_pct": -0.30},
        ]
        result = drawdown_warning.compute_drawdown_warning(bars)
        assert result["alert_level"] == "normal"
        assert result["current_drawdown"] == pytest.approx(-0.30)
        assert result["all_time"]["below_warning"] is False


# ── 因子横截面守卫 ─────────────────────────────────────


class TestFactorGuards:
    def test_scalar_non_numeric_string_is_skipped(self):
        """数值字符串可转换，非数值串（"N/A"）解析失败即跳过，不污染均值。"""
        item = _catalog_entry("fund_roe")
        key = fe.required_value_key(item, fe.FIELD_FIN)
        row: dict = {}
        fe._apply_scalar(row, item, {"600000": {key: "N/A"}}, fe.FIELD_FIN, ["600000"])
        assert row["codes_ok"] == 0
        assert row["reason"] == "财务指标不可得"

    def test_scalar_below_min_codes_reports_count(self):
        """有效码数 >0 但不足下限 → 给出「有效码数不足」原因（非「不可得」）。"""
        item = _catalog_entry("fund_roe")
        key = fe.required_value_key(item, fe.FIELD_FIN)
        row: dict = {}
        fe._apply_scalar(row, item, {"600000": {key: 12.5}}, fe.FIELD_FIN, ["600000"])
        assert row["codes_ok"] == 1
        assert row["reason"] == f"有效码数不足(1<{fe.MIN_CODES_PER_DAY})"

    def test_bars_shorter_than_min_bars_are_skipped(self):
        """K 线根数不足 min_bars 的代码跳过，不进入因子计算。"""
        item = _catalog_entry("qlib_ma_cross")
        row: dict = {}
        fe._apply_bars(row, item, {"600000": [{"close": 10.0}, {"close": 11.0}]}, [])
        assert row.get("computable") is not True
        assert row["codes_ok"] == 0


# ── 财务指标解析 ──────────────────────────────────────


class TestFinancialParsingGuards:
    def test_to_float_rejects_unparsable_token(self):
        assert fie._to_float("N/A") is None
        assert fie._to_float("1,234.5") == pytest.approx(1234.5)

    def test_is_plausible_rejects_non_finite(self):
        assert fie._is_plausible("amount", float("inf")) is False
        assert fie._is_plausible("amount", 1e9) is True

    def test_prior_year_entry_with_unparsable_period(self):
        """报告期无 '-'（无法回推上年）→ None（不抛 ValueError）。"""
        assert fsd._prior_year_entry({}, period="2024", doc_type="annual") is None


# ── 行业 beta 守卫 ────────────────────────────────────


class TestIndustryBetaGuards:
    def test_empty_portfolio_frame_returns_none(self):
        assert industry_beta._portfolio_industry_corr([], [{"date": "2026-01-05", "return": 0.01}], 20) is None

    def test_empty_industry_frame_returns_none(self):
        assert industry_beta._portfolio_industry_corr([{"date": "2026-01-05", "return": 0.01}], [], 20) is None

    def test_single_overlap_returns_none(self):
        """重叠日期不足 2 个 → 无法算相关，返回 None。"""
        assert (
            industry_beta._portfolio_industry_corr(
                [{"date": "2026-01-05", "return": 0.01}],
                [{"date": "2026-01-05", "return": 0.02}],
                20,
            )
            is None
        )

    def test_constant_series_returns_none(self):
        """任一方方差为 0（常数序列）→ 相关系数无定义，返回 None。"""
        portfolio = [{"date": f"2026-01-{i:02d}", "return": 0.01} for i in (1, 2, 3)]
        industry = [{"date": f"2026-01-{i:02d}", "return": 0.01 * i} for i in (1, 2, 3)]
        assert industry_beta._portfolio_industry_corr(portfolio, industry, 20) is None


# ── 市场情绪目标池 ────────────────────────────────────


class TestMarketSentimentTargets:
    def test_penetrated_non_dict_skipped_and_asset_code_used(self):
        """穿透资产非 dict 条目跳过；自带 code 的资产按该代码入池。"""
        targets = market_sentiment.tracked_targets(
            [Holding(account="A", name="贵州茅台", code="600519", shares=100, cost_price=10.0)],
            ["not-a-dict", {"name": "宁德时代", "code": "300750"}],
        )
        assert targets["600519"]["holding_kind"] == "直接持有"
        assert targets["300750"]["name"] == "宁德时代"

    def test_dragon_tiger_non_dict_item_skipped(self):
        rows = market_sentiment._dragon_tiger_rows(
            {"trade_date": "2026-01-05", "stock_items": ["bad", {"ticker": "600519", "net_buy": 1.0}]},
            {"600519": {"name": "贵州茅台", "holding_kind": "直接持有"}},
        )
        assert [row["code"] for row in rows] == ["600519"]

    def test_ladder_non_dict_member_skipped(self):
        ladder = {
            "item": [
                {
                    "date": "2026-01-05",
                    "boards": {"连续涨停": ["bad", {"ticker": "600519", "board_num": 3}]},
                }
            ]
        }
        rows = market_sentiment._ladder_rows(ladder, {"600519": {"name": "贵州茅台", "holding_kind": "直接持有"}})
        assert [row["code"] for row in rows] == ["600519"]


# ── 景气度评分与信号 ──────────────────────────────────


class TestProsperityGuards:
    def test_rating_below_lowest_threshold_is_low_fit(self):
        assert prosperity_scoring._rating(0) == ("low_fit", "不契合")

    def test_liquidity_assumed_entries_listed_as_unverified(self):
        """成交额缺失按「流动性充足」假设的品种须在未验证说明中点名。"""
        result = prosperity_scoring._score_liquidity(
            [
                {"code": "600519", "type": "stock", "liquidation_days": 1.0},
                {"code": "300750", "type": "assumed_liquid"},
            ]
        )
        assert result["status"] in {"scored", "partial"}
        assert any("成交额数据缺失" in note for note in result["unverified"])

    def test_turnover_proxy_unparsable_snapshot_shape(self, monkeypatch):
        """快照形态不可解析 → 换手代理标记未验证（返回 None，异常不外泄）。"""
        monkeypatch.setattr(
            prosperity_signals,
            "_snapshot_holding_codes",
            lambda snap: (_ for _ in ()).throw(AttributeError("bad shape")),
        )
        assert prosperity_signals._turnover_proxy_pct([object(), object()]) is None


# ── 申购可行性话术 ────────────────────────────────────


def test_describe_feasibility_reports_infeasible_path():
    text = purchase_feasibility.describe_feasibility({"limit_text": "1000", "days": 9, "feasible": False})
    assert text.startswith("限大额，日限 1000 元")
    assert f"> {purchase_feasibility.FEASIBILITY_MAX_DAYS}" in text
    assert "路径不可行" in text


# ── 再平衡归类与流水 ──────────────────────────────────


class TestRebalanceBranches:
    def test_transaction_without_code_is_skipped(self):
        txn = type("Txn", (), {"action": "buy", "code": "", "date": "2026-01-05"})()
        assert rebalance.build_holding_trading_days([txn], "2026-01-06") == {}

    def test_bond_and_money_etf_and_otc_bond_classified(self):
        """债券 ETF → 固收；货币 ETF → 货币；场外债基 → 固收。"""
        assert rebalance.classify_holding("国债ETF", "511010") == "fixed_income"
        assert rebalance.classify_holding("货币ETF", "511990") == "money_market"
        assert rebalance.classify_holding("华夏纯债基金", "000001") == "fixed_income"


class TestRebalanceAdvisorBranches:
    def test_non_positive_shares_round_to_zero(self):
        assert rebalance_advisor._round_to_lot(0, "600519", "贵州茅台") == 0

    def test_rebalance_candidate_without_code_or_excess(self):
        assert rebalance_advisor._candidate_from_rebalance({"code": ""}, {"price": 10.0}, 100.0) is None
        assert (
            rebalance_advisor._candidate_from_rebalance(
                {"code": "600519", "threshold": 0.5},
                {"price": 10.0, "market_value": 1.0},
                100.0,
            )
            is None
        )

    def test_discipline_candidate_without_stop_action(self):
        """行动文案既非止损也非止盈 → 不产出减仓候选。"""
        assert (
            rebalance_advisor._candidate_from_discipline(
                {"code": "600519", "action": "继续观察"},
                {"shares": 100, "name": "贵州茅台"},
            )
            is None
        )


# ── 尾部风险工具函数 ──────────────────────────────────


class TestTailRiskHelpers:
    def test_max_single_day_drop_on_empty_returns(self):
        assert tail_risk._max_single_day_drop([]) == (0.0, -1)

    def test_recovery_after_drop_with_missing_pre_drop_value(self):
        """跌前市值为 0/缺失 → 无法判定是否收复，按「未收复」处理。"""
        assert tail_risk._recovery_after_drop([{"total_value": 0}, {"total_value": 5}], 0) == (None, "unrecovered")

    def test_bar_date_at_out_of_range(self):
        assert tail_risk._bar_date_at([{"date": "2026-01-05"}], 5) is None
        assert tail_risk._bar_date_at([{"date": "2026-01-05"}], 0) == "2026-01-05"


# ── what-if 持仓合并 ──────────────────────────────────


class TestWhatifMerge:
    def test_blank_code_skipped_and_name_falls_back_to_code(self):
        merged = whatif._merge_holdings(
            [
                Holding(account="A", name="", code="", shares=1, cost_price=1.0),
                Holding(account="A", name="", code="600519", shares=1, cost_price=2.0),
                Holding(account="A", name="贵州茅台", code="600519", shares=1, cost_price=3.0),
            ]
        )
        assert set(merged) == {"600519"}
        # 首笔同名品种无名称 → 以代码作显示名（后续同名笔不覆盖已定名称）
        assert merged["600519"]["name"] == "600519"
        assert merged["600519"]["shares"] == pytest.approx(2.0)
