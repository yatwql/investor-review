"""分析层残余守卫/降级分支补齐（行覆盖率收口）。

集中覆盖「每文件仅缺 1~2 行」的守卫与降级分支：这些分支只在边界输入
（样本数恰在阈值上下、常数序列、港股代码、零期收益、窗口参数为 0、
基准行情晚于事件日、持仓代码为空）下走到。每条用例断言分支的**实际行为**
（返回值 / 降级文案 / 序列形态），不靠 mock 恒真属性。

可证明不可达的死分支不在此列（已在对应提交中删除）。
"""

from __future__ import annotations

import pytest

from src.python.analysis import (
    alignment_correction,
    correlation,
    drawdown_warning,
    liquidity,
    metrics,
    metrics_risk,
    portfolio_evolution,
    prosperity_scoring,
    rebalance_advisor,
)
from src.python.analysis.event_window_impact import compute_event_impact
from src.python.core.snapshot_store import save
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


# ── alignment_correction：年化 TWR 摘要 ────────────────────────


def test_alignment_summary_includes_annualized_twr_for_full_year():
    """有效期间 ≥ 252 → TWR 摘要追加年化一行。"""
    snapshots = [{"value": 100000.0 * (1.001**i), "cash_flow": 0.0} for i in range(260)]
    holdings = [{"name": "沪深300ETF", "code": "510300", "market_value": 260000.0}]

    result = alignment_correction.compute_alignment_factors(holdings, 260000.0, snapshots=snapshots)

    assert result["twr"]["annualized_twr"] is not None
    assert "年化 TWR" in result["summary_text"]


# ── correlation：全常数序列 → 无可用端点 ───────────────────────────


def test_rolling_correlations_constant_series_has_no_valid_endpoint():
    """两序列均无波动（r 恒 None）→ 组合平均端点为空的降级输出。"""
    dates = [f"2026-01-{d:02d}" for d in range(1, 11)]
    returns = {"A": [{"date": d, "return": 0.01} for d in dates], "B": [{"date": d, "return": 0.02} for d in dates]}

    result = correlation.compute_rolling_correlations(returns, min_samples=5, windows=(5,))

    assert result["available"] is False
    assert result["status"] == "insufficient"
    # 不可用壳契约：全部窗口键在位且序列为空（渲染层无需分支判空）
    assert set(result["portfolio"]) == {str(w) for w in result["windows"]}
    assert all(points == [] for points in result["portfolio"].values())


# ── drawdown_warning：窗口为 0 的退化切片 ──────────────────────────


def test_rolling_max_drawdown_zero_window_fills_zeros():
    """window=0 时切片恒空 → 逐日填 0.0（长度与输入一致）。"""
    result = drawdown_warning.rolling_max_drawdown([-0.1, -0.2, -0.3], 0)

    assert result == [0.0, 0.0, 0.0]


# ── event_window_impact：窗口参数退化与基准行情晚于事件日 ─────────────


def _wk_days(start: str, end: str) -> list[str]:
    from datetime import datetime, timedelta

    out: list[str] = []
    cur, last = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d")
    while cur <= last:
        if cur.weekday() < 5:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _patch_calendar(monkeypatch, days: list[str]) -> None:
    monkeypatch.setattr("src.python.core.trading_calendar._get_trading_calendar", lambda: set(days))


def _closes(days: list[str], price: float) -> list[dict]:
    return [{"date": d, "close": price} for d in days]


def test_event_impact_negative_window_after_degrades(monkeypatch):
    """window_after=-1 → 后窗可用交易日为负 → 降级「事件日后无可用交易日」。"""
    days = _wk_days("2026-08-24", "2026-10-30")
    _patch_calendar(monkeypatch, days)

    result = compute_event_impact(
        "2026-09-22",
        _closes(days, 100.0),
        _closes(days, 3000.0),
        window_after=-1,
    )

    assert result["reason"] == "事件日后无可用交易日"
    assert result["match"] == "不可判"


def test_event_impact_index_bars_start_after_prev_day_degrades(monkeypatch):
    """基准行情自事件日之后才有值 → 事件日前基点无法解析 → 该事件降级。"""
    days = _wk_days("2026-08-24", "2026-10-30")
    _patch_calendar(monkeypatch, days)
    index_days = [d for d in days if d > "2026-09-22"]

    result = compute_event_impact("2026-09-22", _closes(days, 100.0), _closes(index_days, 3000.0))

    assert result["reason"] == "基准关键位无法解析"
    assert result["asset_return"] is None


# ── liquidity：港股等其他类型 → assumed_liquid ────────────────────


def test_liquidity_hk_stock_marked_assumed_liquid():
    """港股通 5 位代码既非场外基金也非场内 A 股口径 → 默认流动性充足。"""
    holdings = [{"code": "00700", "name": "腾讯控股", "market_value": 50000.0}]

    result = liquidity.check_liquidity(holdings, 50000.0)

    assert len(result) == 1
    assert result[0]["type"] == "assumed_liquid"
    assert result[0]["tag"] == "流动性充足（数据缺失）"


# ── metrics：上下期持仓都给定时计算换手率 ───────────────────────────


def test_compute_all_metrics_uses_turnover_when_both_periods_given():
    """holdings_before/after 同时给定时换手率进指标（缺一则留 None）。"""
    before = [{"code": "510300", "name": "沪深300ETF", "market_value": 10000.0}]
    after = [{"code": "511990", "name": "华宝添益", "market_value": 10000.0}]

    result = metrics.compute_all_metrics([0.01, -0.02] * 12, holdings_before=before, holdings_after=after)

    # 满仓从 A 切到 B：Σ|Δw|/2 = 1.0
    assert result["turnover_rate"] == pytest.approx(1.0)


# ── metrics_risk：样本数不足标准误下限 → 区间降级 ────────────────────


def test_beta_analysis_degraded_when_sample_below_se_minimum():
    """样本数达到 beta 点估计下限（20）但不足标准误下限（22）→ CI 降级为 None。"""
    portfolio = [0.01 * ((-1) ** i) + 0.001 * i for i in range(21)]
    benchmark = [0.02 * ((-1) ** i) + 0.0005 * i for i in range(21)]

    result = metrics_risk.portfolio_beta_analysis(portfolio, benchmark)

    assert result["beta"] is not None
    assert result["ci_lower"] is None
    assert result["reliable"] is False


# ── portfolio_evolution：全零权重期与空代码持仓 ─────────────────────


def _snapshot(ts: str, holdings: list[SnapshotHolding]) -> None:
    save(
        SnapshotData(
            accounts=(AccountSnapshot(account_name="全部", holdings=tuple(holdings)),),
            total_value=sum(h.market_value for h in holdings),
            total_cost=sum(h.cost_total for h in holdings),
            total_pnl=0.0,
            timestamp=ts,
        )
    )


def _plain_holding(code: str, name: str, mv: float) -> SnapshotHolding:
    return SnapshotHolding(
        code=code,
        name=name,
        shares=0.0,
        cost_price=0.0,
        market_value=mv,
        daily_pnl=0.0,
        total_pnl=0.0,
        cost_total=mv,
    )


def test_evolution_zero_weight_period_and_blank_code_holding():
    """全部持仓市值为 0 → HHI 记 None；代码为空的持仓行跳过不建序列。"""
    for ts in ("20260105T150000", "20260106T150000", "20260107T150000"):
        _snapshot(ts, [_plain_holding("", "未登记品种", 0.0), _plain_holding("510300", "沪深300ETF", 0.0)])

    data = portfolio_evolution.build_evolution_data()

    assert data["available"] is True
    assert data["hhi"] == [None, None, None]
    assert "510300" in [item["code"] for item in data["top_holdings"]]
    assert "" not in [item["code"] for item in data["top_holdings"]]


# ── snapshot_diff：基线回退到同一份快照时不可自比 ─────────────────


def test_snapshot_diff_skips_baseline_equal_to_latest(monkeypatch):
    """基线加载器退化返回最新同期快照 → 视为无基线，降级不可用。"""
    from src.python.analysis import snapshot_diff
    from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

    holding = SnapshotHolding(
        code="510300",
        name="沪深300ETF",
        shares=100.0,
        cost_price=1.0,
        market_value=10000.0,
        daily_pnl=0.0,
        total_pnl=0.0,
        cost_total=10000.0,
    )
    snap = SnapshotData(
        accounts=(AccountSnapshot(account_name="全部", holdings=(holding,)),),
        total_value=10000.0,
        total_cost=10000.0,
        total_pnl=0.0,
        timestamp="20260105T150000",
    )
    monkeypatch.setattr("src.python.core.snapshot_store.load_all", lambda _ns=None: [snap, snap])
    monkeypatch.setattr("src.python.core.snapshot_store.load_comparison_baseline", lambda *_a: snap)

    result = snapshot_diff.build_snapshot_diff(min_snapshots=1)

    assert result["available"] is False
    assert result["added"] == [] and result["removed"] == []


# ── trade_cost_model：空代码持仓行不入批次表 ───────────────────────


def test_position_lots_skip_holding_without_code():
    """持仓行代码为空（未登记）→ 跳过，不建 FIFO 批次。"""
    from src.python.analysis import trade_cost_model
    from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

    def _h(code: str) -> SnapshotHolding:
        return SnapshotHolding(
            code=code,
            name="未登记" if not code else "沪深300ETF",
            shares=100.0,
            cost_price=1.0,
            market_value=100.0,
            daily_pnl=0.0,
            total_pnl=0.0,
            cost_total=100.0,
        )

    snap = SnapshotData(
        accounts=(AccountSnapshot(account_name="全部", holdings=(_h(""), _h("510300"))),),
        total_value=200.0,
        total_cost=200.0,
        total_pnl=0.0,
        timestamp="20260105T150000",
    )

    lots = trade_cost_model.rebuild_position_lots([snap])

    assert set(lots) == {"510300"}
    assert lots["510300"][0]["shares"] == pytest.approx(100.0)


# ── prosperity_scoring / rebalance_advisor：口径兜底 ──────────────────


def test_rating_below_lowest_threshold_falls_back_to_low_fit():
    """低于最低档阈值（0）的得分不匹配任何档 → 兜底「不契合」。"""
    assert prosperity_scoring._rating(-5) == ("low_fit", "不契合")


def test_discipline_candidate_skips_non_stop_action():
    """含「止损/止盈」以外的动作无可对应订单 → 不产出候选。"""
    signal = {"code": "600000", "name": "浦发银行", "action": "加仓"}

    assert rebalance_advisor._candidate_from_discipline(signal, {"price": 10.0, "shares": 100.0}) is None
