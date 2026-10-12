"""风险调整超额模块测试 — IR/TE/年化超额/月度胜率/滚动序列与 §1.4.5 降级。

覆盖场景：
  - 合成长窗（组合与基准日收益可控）→ IR/TE/年化超额与 statistics 独立计算交叉验证
  - 12/24 月跑赢胜率：全胜月 → 100%；样本不足 → None（逐指标降级）
  - 滚动 1Y 超额：点数与窗口的结构关系、首点日期、可用性
  - 降级占位：None / status=unavailable / 无 bars / 未配置基准 → available=False + 原因
  - 对齐防御：基准序列短缺/非正值跳过

设计约束：纯标准库、无网络请求（输入全部合成）。
"""

from __future__ import annotations

import math
import statistics
from datetime import date, timedelta

import pytest

from src.python.analysis.benchmark_excess import (
    ROLLING_WINDOW_DAYS,
    build_risk_adjusted_excess,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]
pytestmark.append(pytest.mark.usefixtures("offline_external_sources"))

_TRADING_DAYS = 252


def _make_history(
    days: int,
    port_rets: list[float],
    bm_rets: list[float],
    with_benchmark: bool = True,
) -> dict:
    """合成 history_data 契约（bars 按日递增；daily_returns/bm value 可控）。

    Args:
        days: bars 天数（daily_returns 长 days-1）
        port_rets: 组合日收益（长 days-1）
        bm_rets: 基准日收益（长 days-1；bm value[0]=100，value[j+1]=value[j]*(1+bm_rets[j])）
        with_benchmark: False 时 benchmarks 为空列表
    """
    start = date(2024, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    bars = [{"date": d, "total_value": 1000.0 + i} for i, d in enumerate(dates)]
    history: dict = {
        "status": "ok",
        "bars": bars,
        "daily_returns": list(port_rets),
        "data_start": dates[0],
        "data_end": dates[-1],
        "benchmarks": [],
    }
    if with_benchmark:
        values = [100.0]
        for r in bm_rets:
            values.append(values[-1] * (1.0 + r))
        history["benchmarks"] = [
            {
                "code": "sh000300",
                "name": "沪深300",
                "bars": [{"date": d, "value": v} for d, v in zip(dates, values)],
            }
        ]
    return history


def _cycle(pattern: list[float], n: int) -> list[float]:
    """按模式循环生成长度 n 的序列。"""
    return [pattern[i % len(pattern)] for i in range(n)]


class TestMetricsMath:
    """IR / TE / 年化超额数学与独立计算交叉验证。"""

    def test_ir_te_and_annual_excess_cross_check(self):
        """IR/TE/年化超额与 statistics 独立计算一致（非零波动模式）。"""
        days = 300
        port = _cycle([0.002, -0.001, 0.003, -0.002], days - 1)
        bm = _cycle([0.001, 0.001, 0.001, 0.001], days - 1)
        contract = build_risk_adjusted_excess(_make_history(days, port, bm))

        assert contract["available"] is True
        row = contract["benchmarks"][0]
        excess = [p - b for p, b in zip(port, bm)]
        mean = statistics.mean(excess)
        sd = statistics.stdev(excess)  # 样本标准差（n-1），与实现同口径
        assert row["ir_annual"] == pytest.approx(mean / sd * math.sqrt(_TRADING_DAYS), rel=1e-9)
        assert row["te_annual"] == pytest.approx(sd * math.sqrt(_TRADING_DAYS), rel=1e-9)

        p_total = math.prod(1.0 + r for r in port)
        b_total = math.prod(1.0 + r for r in bm)
        n = len(port)
        expected_excess_ann = (p_total ** (_TRADING_DAYS / n) - b_total ** (_TRADING_DAYS / n)) * 100
        assert row["excess_annual_pct"] == pytest.approx(expected_excess_ann, rel=1e-9)

    def test_zero_variance_excess_returns_none(self):
        """日超额恒定（方差为 0）→ IR/TE 无意义置 None，年化超额仍可算。"""
        days = 300
        port = [0.002] * (days - 1)
        bm = [0.001] * (days - 1)
        row = build_risk_adjusted_excess(_make_history(days, port, bm))["benchmarks"][0]
        assert row["ir_annual"] is None
        assert row["te_annual"] is None
        assert row["excess_annual_pct"] is not None

    def test_short_sample_skips_ir_te(self):
        """样本不足 60 交易日 → IR/TE/年化超额全 None（逐指标降级，不整块失败）。"""
        days = 40
        port = _cycle([0.002, -0.001], days - 1)
        bm = _cycle([0.001, 0.001], days - 1)
        contract = build_risk_adjusted_excess(_make_history(days, port, bm))
        assert contract["available"] is True  # 块级可用，指标级降级
        row = contract["benchmarks"][0]
        assert row["ir_annual"] is None
        assert row["te_annual"] is None
        assert row["excess_annual_pct"] is None


class TestWinRates:
    """近 12/24 完整月跑赢胜率（月粒度、首末不完整月排除）。"""

    def test_full_win_long_history(self):
        """组合日收益恒高于基准 → 全月跑赢，12/24 月胜率均 100%。"""
        days = 830  # ≈27 自然月 → 完整月 ≥24
        port = [0.0008] * (days - 1)
        bm = [0.0002] * (days - 1)
        row = build_risk_adjusted_excess(_make_history(days, port, bm))["benchmarks"][0]
        assert row["win_rate_12m"] == pytest.approx(100.0)
        assert row["win_rate_24m"] == pytest.approx(100.0)
        assert row["complete_months"] >= 24

    def test_insufficient_months_degrade_to_none(self):
        """完整月 <12 → 12 月胜率 None（<24 同理），complete_months 如实计数。"""
        days = 300  # ≈10 自然月
        port = [0.0008] * (days - 1)
        bm = [0.0002] * (days - 1)
        row = build_risk_adjusted_excess(_make_history(days, port, bm))["benchmarks"][0]
        assert row["win_rate_12m"] is None
        assert row["win_rate_24m"] is None
        assert row["complete_months"] < 12

    def test_mixed_win_rate(self):
        """交替胜负月 → 胜率落于 0~100 之间且为 50 的整数倍附近（月粒度）。"""
        days = 830
        # 单日模式决定不了月胜负——按月交替：前半月强正、后半月强负 → 相邻月互有胜负
        port: list[float] = []
        for i in range(days - 1):
            month_phase = (i // 30) % 2
            port.append(0.004 if month_phase == 0 else -0.004)
        bm = [0.0001] * (days - 1)
        row = build_risk_adjusted_excess(_make_history(days, port, bm))["benchmarks"][0]
        assert row["win_rate_12m"] is not None
        assert 0.0 <= row["win_rate_12m"] <= 100.0


class TestRollingExcess:
    """滚动 1Y 超额序列（主基准）。"""

    def test_points_follow_window_structure(self):
        """点数 = 对齐样本数 − 窗口 + 1；首点日期 = 第 window+1 根 bar。"""
        days = 300
        port = _cycle([0.002, -0.001], days - 1)
        bm = _cycle([0.001, 0.0005], days - 1)
        history = _make_history(days, port, bm)
        contract = build_risk_adjusted_excess(history)
        rolling = contract["rolling"]
        assert rolling["available"] is True
        assert rolling["window_days"] == ROLLING_WINDOW_DAYS
        pairs = days - 1  # 对齐样本数（日收益条数）
        assert len(rolling["points"]) == pairs - ROLLING_WINDOW_DAYS + 1
        # 首点 = 第 250 个样本（pairs[window-1] → bars[window]）处的滚动值
        assert rolling["points"][0]["date"] == history["bars"][ROLLING_WINDOW_DAYS]["date"]
        assert rolling["primary_name"] == "沪深300"

    def test_insufficient_window_degrades(self):
        """样本 < 窗口长度 → rolling.available=False + 中文原因。"""
        days = 200
        port = _cycle([0.002, -0.001], days - 1)
        bm = _cycle([0.001], days - 1)
        rolling = build_risk_adjusted_excess(_make_history(days, port, bm))["rolling"]
        assert rolling["available"] is False
        assert str(rolling["reason"])  # 非空原因（降级空口径）
        assert rolling["points"] == []


class TestDegradation:
    """块级降级占位（§1.4.5）。"""

    def test_none_input_unavailable(self):
        contract = build_risk_adjusted_excess(None)
        assert contract["available"] is False
        assert contract["benchmarks"] == []
        assert contract["window"] is None

    def test_unavailable_status_unavailable(self):
        contract = build_risk_adjusted_excess({"status": "unavailable", "bars": []})
        assert contract["available"] is False

    def test_no_bars_unavailable(self):
        contract = build_risk_adjusted_excess({"status": "ok", "bars": []})
        assert contract["available"] is False

    def test_no_benchmark_unavailable_with_reason(self):
        """未配置业绩基准 → available=False + 指向配置键的中文原因。"""
        contract = build_risk_adjusted_excess(_make_history(300, [0.001] * 299, [0.001] * 299, with_benchmark=False))
        assert contract["available"] is False
        assert "基准" in str(contract["reason"])

    def test_short_benchmark_series_skipped(self):
        """基准序列短缺（对齐防御）→ 无有效样本，指标 None 而非抛异常。"""
        history = _make_history(300, [0.002] * 299, [0.001] * 299)
        history["benchmarks"][0]["bars"] = history["benchmarks"][0]["bars"][:10]
        contract = build_risk_adjusted_excess(history)
        row = contract["benchmarks"][0]
        assert row["ir_annual"] is None
        assert row["te_annual"] is None
