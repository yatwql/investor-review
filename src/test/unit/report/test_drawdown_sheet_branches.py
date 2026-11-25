"""组合历史走势与回撤页签的分支覆盖：基准对照列、危机回放双层表、风险调整超额区块。

三组未覆盖契约：
  一、带基准（benchmarks）的走势表与指标矩阵：基准列取值/缺值留空 + 百分比折算
  二、危机区间标注三态：非回放态窗口内无重叠、窗口内外混合、回放态双层 9 列
  三、风险调整超额区块：可用性降级占位、胜率缺值「数据不足」、滚动序列、
     滚动不可用原因、口径说明行、开关关闭时整块不写
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from src.python.report.portfolio_history_drawdown_sheet import write_portfolio_history_drawdown_sheet

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _history(**extra) -> dict:
    """最小可用 history_data（3 根 bar，可追加基准/月度/尾部字段）。"""
    base = {
        "status": "ok",
        "bars": [
            {"date": "2026-01-05", "total_value": 100.0},
            {"date": "2026-01-06", "total_value": 110.0},
            {"date": "2026-01-07", "total_value": 121.0},
        ],
        "total_return_pct": 21.0,
        "total_return": 2100.0,
        "max_drawdown_pct": -4.5,
        "annualized_volatility": 0.12,
        "data_start": "2026-01-05",
        "data_end": "2026-01-07",
        "drawdown_available": True,
        "drawdown_events": [],
    }
    base.update(extra)
    return base


def _write(**extra) -> object:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    write_portfolio_history_drawdown_sheet(
        ws,
        extra.pop("history_data", _history()),
        extra.pop("crisis", None),
        extra.pop("tail_risk", None),
        extra.pop("excess", None),
    )
    return ws


def _cells(ws) -> list[object]:
    return [c.value for row in ws.iter_rows() for c in row if c.value is not None]


def _row_of(ws, first_cell_value: str) -> list[object]:
    for row in ws.iter_rows():
        if row[0].value == first_cell_value:
            return [c.value for c in row]
    raise AssertionError(f"未找到首列值 {first_cell_value!r} 的行")


# ── 一、基准对照列 ──────────────────────────────────────


class TestBenchmarkColumns:
    def test_trend_rows_carry_benchmark_values_and_blank_when_bar_missing(self):
        """基准 bars 短于组合 bars 时该格留空（不抛 IndexError）。"""
        history = _history(
            benchmarks=[
                {"name": "沪深300", "bars": [{"value": 100.0}, {"value": 101.0}], "total_return_pct": 12.0},
            ]
        )
        ws = _write(history_data=history)
        # 表头首列 = 「日期」行含基准名
        assert "沪深300" in _row_of(ws, "日期")
        # 首根 bar 行：基准值落在下标 4（0=日期/1=市值/2=收益率/3=归一化，基准列从 4 起）
        assert _row_of(ws, "2026-01-05")[4] == pytest.approx(100.0)
        # 第三根 bar 无基准数据 → 基准列空（不是留 0 也不是拉前一根的值）
        assert _row_of(ws, "2026-01-07")[4] is None

    def test_metric_matrix_scales_percent_and_keeps_blank_on_missing(self):
        """指标矩阵：百分比类基准值除以 100，缺值留空；非百分比原样。"""
        history = _history(
            benchmarks=[
                {
                    "code": "sh000300",
                    "total_return_pct": 12.0,
                    "max_drawdown_pct": -8.0,
                    "annualized_volatility": 0.21,
                    "data_start": "2026-01-05",
                },
            ],
        )
        ws = _write(history_data=history)
        cum_row = _row_of(ws, "累计收益率(%)")
        assert cum_row[2] == pytest.approx(0.12)
        dd_row = _row_of(ws, "最大回撤(%)")
        assert dd_row[2] == pytest.approx(-0.08)
        # 终止日基准缺值 → 留空
        end_row = _row_of(ws, "终止日")
        assert end_row[2] is None
        # 未提供 name → 表头回落 code
        assert "sh000300" in _row_of(ws, "指标")

    def test_tail_risk_none_recovery_state_renders_dash(self):
        """recovery_state='none' → 恢复耗时列写 '--'（无下跌事件，区别于未恢复）。"""
        ws = _write(
            tail_risk={
                "available": True,
                "var95": -2.1,
                "var99": -3.4,
                "max_single_day_drop": -4.0,
                "consecutive_down_days": 2,
                "recovery_days_after_drop": None,
                "recovery_state": "none",
            }
        )
        assert _row_of(ws, "最大单日跌幅后恢复(天)")[1] == "--"


# ── 二、危机区间标注 ────────────────────────────────────


def _crisis_interval(name: str, in_range: bool, **extra) -> dict:
    interval = {
        "name": name,
        "start": "2022-01-04",
        "end": "2022-04-27",
        "in_range": in_range,
        "interval_drawdown_pct": 25.0,
        "trough_date": "2022-03-15",
        "recovery_days": 60,
        "recovered": True,
        "portfolio_return_pct": 30.0,
        "index_return_pct": 20.0,
        "index_drawdown_pct": 22.0,
    }
    interval.update(extra)
    return interval


class TestCrisisAnnotationBranches:
    def test_no_interval_overlapping_window_writes_hint_row(self):
        ws = _write(crisis={"available": True, "intervals": [_crisis_interval("2020 疫情", in_range=False)]})
        flat = _cells(ws)
        assert "报告数据窗口内无历史危机区间" in flat
        assert any(isinstance(v, str) and "说明：阴影/高亮区间" in v for v in flat)

    def test_mixed_ranges_list_out_of_window_names(self):
        ws = _write(
            crisis={
                "available": True,
                "intervals": [
                    _crisis_interval("2022 市场调整", in_range=True),
                    _crisis_interval("2015 股灾", in_range=False),
                    _crisis_interval("2018 熊市", in_range=False),
                ],
            }
        )
        flat = _cells(ws)
        assert any(isinstance(v, str) and v.startswith("数据窗口外（未重叠）：2015 股灾、2018 熊市") for v in flat)
        assert "2022 市场调整" in flat

    @pytest.mark.parametrize(
        ("recovered", "expected_status"),
        [(True, "已恢复"), (False, "未恢复"), (None, "—")],
    )
    def test_replay_status_tristate(self, recovered, expected_status):
        ws = _write(
            crisis={
                "replay": True,
                "intervals": [_crisis_interval("2022 市场调整", in_range=True, recovered=recovered)],
                "index_reason": None,
            }
        )
        row = _row_of(ws, "2022 市场调整")
        assert row[8] == expected_status
        # 组合层与指数层各自折算为小数
        assert row[2] == pytest.approx(0.30)
        assert row[3] == pytest.approx(0.25)
        assert row[6] == pytest.approx(0.20)
        assert row[7] == pytest.approx(0.22)

    def test_replay_out_of_window_row_keeps_index_layer_only(self):
        """非重叠区间：组合层三列留空、恢复耗时留空、指数层仍出值。"""
        ws = _write(
            crisis={
                "replay": True,
                "intervals": [
                    _crisis_interval(
                        "2015 股灾",
                        in_range=False,
                        portfolio_return_pct=-30.0,
                        index_return_pct=-43.0,
                        index_drawdown_pct=-45.0,
                    )
                ],
                "index_reason": "指数层使用沪深300全历史日线",
            }
        )
        row = _row_of(ws, "2015 股灾")
        assert row[2] is None and row[3] is None and row[4] is None and row[5] is None
        assert row[6] == pytest.approx(-0.43)
        assert row[7] == pytest.approx(-0.45)
        assert row[8] == "组合窗口外"
        assert any(isinstance(v, str) and v.startswith("指数层：") for v in _cells(ws))

    def test_replay_without_intervals_writes_placeholder(self):
        ws = _write(crisis={"replay": True, "intervals": []})
        flat = _cells(ws)
        assert "危机区间数据不可用" in flat
        assert any(isinstance(v, str) and "说明：双层回放" in v for v in flat)

    def test_replay_missing_recovery_days_uses_dash(self):
        ws = _write(
            crisis={
                "replay": True,
                "intervals": [_crisis_interval("2022 市场调整", in_range=True, recovery_days=None)],
            }
        )
        assert _row_of(ws, "2022 市场调整")[5] == "--"


# ── 三、风险调整超额 ────────────────────────────────────


class TestExcessBlockBranches:
    def test_disabled_block_writes_nothing(self):
        """开关关闭（excess=None）时区块整体不写，产物无「五、」标题。"""
        flat = _cells(_write(excess=None))
        assert "五、风险调整超额" not in flat

    def test_unavailable_writes_reason_placeholder(self):
        flat = _cells(_write(excess={"available": False, "reason": "完整月数不足 12"}))
        assert "五、风险调整超额" in flat
        assert any(isinstance(v, str) and v.startswith("数据不可用：完整月数不足 12") for v in flat)

    def test_unavailable_without_reason_uses_fallback(self):
        flat = _cells(_write(excess={"available": False}))
        assert any(isinstance(v, str) and v == "数据不可用：未知原因" for v in flat)

    def test_benchmark_row_scales_and_marks_missing_win_rate(self):
        ws = _write(
            excess={
                "available": True,
                "benchmarks": [
                    {
                        "name": "沪深300",
                        "ir_annual": 0.62,
                        "te_annual": 0.18,
                        "excess_annual_pct": 4.5,
                        "win_rate_12m": 58.3,
                        "win_rate_24m": None,
                        "complete_months": 26,
                    }
                ],
                "rolling": {"available": True, "window_days": 60, "primary_name": "沪深300"},
                "notes": ["超额 = 组合收益 - 基准收益", "滚动窗口按交易日计"],
            }
        )
        row = _row_of(ws, "沪深300")
        assert row[1] == pytest.approx(0.62)
        assert row[3] == pytest.approx(0.045)
        assert row[4] == "58.3%"
        assert row[5] == "数据不足"
        assert row[6] == 26
        flat = _cells(ws)
        assert "滚动 60 日超额（沪深300）" in flat
        assert "超额 = 组合收益 - 基准收益" in flat
        assert "滚动窗口按交易日计" in flat

    def test_rolling_points_scaled_to_fraction(self):
        ws = _write(
            excess={
                "available": True,
                "benchmarks": [],
                "rolling": {
                    "available": True,
                    "window_days": 20,
                    "primary_name": "中证500",
                    "points": [
                        {"date": "2025-12-01", "excess_pct": 1.5},
                        {"date": "2025-12-02", "excess_pct": None},
                    ],
                },
            }
        )
        assert _row_of(ws, "2025-12-01")[1] == pytest.approx(0.015)
        # excess_pct=None 归一为 0.0（契约：缺项不连续断行，按 0 计）
        assert _row_of(ws, "2025-12-02")[1] == pytest.approx(0.0)

    @pytest.mark.parametrize(
        ("rolling", "expected"),
        [
            ({"available": False, "reason": "样本不足 20 个交易日"}, "滚动超额数据不可用：样本不足 20 个交易日"),
            ({"available": False}, "滚动超额数据不可用：未知原因"),
            ({}, "滚动超额数据不可用：未知原因"),
        ],
    )
    def test_rolling_unavailable_reason(self, rolling, expected):
        flat = _cells(_write(excess={"available": True, "benchmarks": [], "rolling": rolling}))
        assert expected in flat
