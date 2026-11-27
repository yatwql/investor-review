"""`scripts/_eval_decision_quality/stages.py` 的降级与全链阶段补盲用例。

补前序用例未覆盖的分支：行情脏值（非数值收盘/缺日期）的跳过口径、波动率与基线的
「判不出即 None」早退、聚合判定三态中的「无差异」档、相关性矩阵不可用与窗口跳过、
`stage_correlation` / `stage_valuation` 的全链编排（取数与账本全部注入，不触网），
以及估值两口径的 PE→PB 兜底与不可用原因归集。
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

mod = load_script("eval-decision-quality.py")


@pytest.fixture()
def stages():
    """`stages` 实现模块本体（常量与内部调用的补丁须打到持有者，而非入口 re-export）。"""
    import _eval_decision_quality.stages as stages_mod

    return stages_mod


def _rising_series(bars: int = 80, start_price: float = 100.0) -> list[dict]:
    """逐日序列（30 日足够覆盖 20 日视界；相关性窗口另用更大长度）。"""
    day = date(2026, 1, 5)
    out: list[dict] = []
    for index in range(bars):
        out.append({"date": day.isoformat(), "close": start_price + index})
        day += timedelta(days=1)
    return out


class TestDirtyBarHandling:
    """脏行情值的跳过口径：非数值收盘与缺日期 bar 不得进入序列。"""

    def test_daily_volatility_skips_non_numeric_close(self):
        """非数值收盘按 0 处理并剔除；有效收盘不足窗口 → None（不猜）。"""
        series = [{"date": f"2026-01-0{i}", "close": "不是数字"} for i in range(1, 5)]

        assert mod.daily_volatility(series, "2026-01-10", window=2) is None

    def test_daily_volatility_single_return_is_none(self):
        """恰好凑满窗口但只有 1 个收益率样本（无法算标准差）→ None。"""
        series = [{"date": "2026-01-05", "close": 100.0}, {"date": "2026-01-06", "close": 101.0}]

        assert mod.daily_volatility(series, "2026-01-10", window=1) is None

    def test_series_daily_returns_drops_dirty_and_undated_bars(self):
        bars = [
            {"date": "2026-01-05", "close": 100.0},
            {"date": "2026-01-06", "close": "坏值"},  # 非数值 → 剔除
            {"date": "2026-01-08", "close": 98.0},
            {"close": 97.0},  # 缺日期 → 无法配对，该对跳过
        ]

        returns = mod.series_daily_returns(bars)

        assert [item["date"] for item in returns] == ["2026-01-08"]
        assert returns[0]["return"] == pytest.approx(98.0 / 100.0 - 1.0)


class TestDisciplineEarlyExit:
    """`discipline_sample` 的判不出早退（基线脏值/缺失）。"""

    def test_non_numeric_baseline_is_skipped(self):
        decision = {"decision_id": "d", "code": "600000", "report_date": "2026-01-05", "baseline_close": "坏值"}

        assert mod.discipline_sample(decision, _rising_series(10)) is None

    def test_missing_code_is_skipped(self):
        decision = {"decision_id": "d", "code": "", "report_date": "2026-01-05", "baseline_close": 100.0}

        assert mod.discipline_sample(decision, _rising_series(30)) is None


class TestAggregateDisciplineNeutralVerdict:
    """「无差异」档：两组样本充足但差值落在预注册容差内。"""

    def test_edge_within_tolerance_reports_no_difference(self, stages, monkeypatch):
        monkeypatch.setattr(stages, "MIN_SAMPLES", 2)
        rows = [
            {"fixed_hit": True, "normalized_hit": True, "effect_return": -0.02},
            {"fixed_hit": True, "normalized_hit": True, "effect_return": -0.02},
            {"fixed_hit": False, "normalized_hit": True, "effect_return": -0.03},
            {"fixed_hit": False, "normalized_hit": True, "effect_return": -0.03},
        ]

        out = mod.aggregate_discipline(rows)

        assert out["verdict"].startswith("无差异")
        assert abs(out["edge"]) < abs(mod.DISCIPLINE_MIN_EDGE)


class TestCorrelationDegradedPaths:
    """相关性↔回撤：品种不足、矩阵不可用、窗口判定不出时的降级。"""

    def test_single_code_has_no_pairwise_correlation(self):
        assert mod.average_pairwise_correlation({"600000": [{"date": "2026-01-05", "return": 0.01}]}) is None

    def test_unavailable_matrix_returns_none(self, monkeypatch):
        """矩阵整体不可用（样本期不足等）→ None，不返回部分格均值。"""
        import src.python.analysis.correlation as correlation

        monkeypatch.setattr(correlation, "compute_correlation_matrix", lambda *a, **k: {"available": False})
        series = {
            "600000": [{"date": "2026-01-05", "return": 0.01}],
            "600001": [{"date": "2026-01-05", "return": 0.02}],
        }

        assert mod.average_pairwise_correlation(series) is None

    def test_build_windows_needs_two_codes_with_returns(self):
        rows, span = mod.build_correlation_windows({"600000": _rising_series(80), "600001": None})

        assert rows == []
        assert span == 0

    def test_window_skipped_when_correlation_undecidable(self, stages, monkeypatch):
        """窗口内相关系数判不出 → 该窗口不入行（不填 0 冒充）。"""
        monkeypatch.setattr(stages, "average_pairwise_correlation", lambda _series: None)
        long_enough = 2 * mod.CORRELATION_WINDOW

        rows, span = mod.build_correlation_windows(
            {"600000": _rising_series(long_enough), "600001": _rising_series(long_enough, 50.0)}
        )

        assert rows == []
        assert span > mod.CORRELATION_WINDOW, "样本期足够，逐窗口判定后才判不出"


class TestStageCorrelation:
    """`stage_correlation` 全链：决策账本定品种集 → 注入行情 → 窗口聚合。"""

    def test_stage_uses_ledger_codes_and_injected_prices(self, tmp_path):
        decisions = [
            {
                "event": "decision",
                "decision_id": "d1",
                "direction": 1,
                "baseline_close": 100.0,
                "report_date": "2026-01-05",
                "code": "600000",
                "name": "X",
            },
            {
                "event": "decision",
                "decision_id": "d2",
                "direction": -1,
                "baseline_close": 50.0,
                "report_date": "2026-01-05",
                "code": "600001",
                "name": "Y",
            },
        ]
        (tmp_path / "decision_ledger.jsonl").write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in decisions), encoding="utf-8"
        )
        long_enough = 2 * mod.CORRELATION_WINDOW

        result = mod.stage_correlation(
            ledger_dir=tmp_path,
            days=200,
            price_fn=lambda code, name, days: _rising_series(long_enough),
        )

        assert result["phase"] == "correlation"
        assert result["n_codes"] == len({d["code"] for d in decisions})
        assert result["summary"]["n_windows"] == len(result["rows"])
        assert "等权" in " ".join(result["caveats"])


class TestValuationTwoCalibers:
    """估值两口径：PE 缺失回退 PB，两值皆缺时归集不可用原因。"""

    def _row(self, *, real: dict) -> dict:
        series = _rising_series(30)
        rows = mod.collect_valuation_rows(
            [{"event": "signal", "subject": "600000", "report_date": series[0]["date"]}],
            days=30,
            price_fn=lambda *a, **k: series,
            fin_fn=lambda _code: [],
            real_fn=lambda bars, recs, price: real,
        )
        assert len(rows) == 1
        return rows[0]

    def test_pb_percentile_used_when_pe_missing(self):
        row = self._row(real={"pe_percentile": None, "pb_percentile": 0.42, "reason": None})

        assert row["real_percentile"] == pytest.approx(0.42)
        assert row["real_reason"] is None

    def test_unavailable_real_carries_reason(self):
        row = self._row(real={"pe_percentile": None, "pb_percentile": None, "reason": "no_financial_records"})

        assert row["real_percentile"] is None
        assert row["real_reason"] == "no_financial_records"


class TestStageValuation:
    """`stage_valuation` 全链：账本 → 逐信号重算 → 原因归集。"""

    def test_stage_collects_rows_and_reasons(self, tmp_path):
        series = _rising_series(80)
        signals = [
            {
                "event": "signal",
                "signal_type": mod.SIGNAL_VALUATION,
                "subject": "600000",
                "report_date": series[0]["date"],
                "value": 0.5,
                "name": "X",
            }
        ]
        (tmp_path / "signal_ledger.jsonl").write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in signals), encoding="utf-8"
        )

        result = mod.stage_valuation(
            ledger_dir=tmp_path,
            days=80,
            price_fn=lambda code, name, days: series,
            fin_fn=lambda _code: [],
        )

        assert result["phase"] == "valuation"
        assert result["n_signals"] == len(signals)
        assert result["n_skipped_no_bars"] == 0
        assert sum(result["real_unavailable_reasons"].values()) == len(result["rows"]), (
            "无财务记录时每行都应带不可用原因（原因计数须能覆盖到行）"
        )
