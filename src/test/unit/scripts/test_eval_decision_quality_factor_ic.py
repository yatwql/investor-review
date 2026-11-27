"""`scripts/_eval_decision_quality/stages.py` 因子 IC 阶段测试（数据全部注入，不触网）。

既有 `test_eval_decision_quality.py` 覆盖视界/纪律/相关性/估值阶段；本文件补：
  - `collect_factor_pairs`：脏值（None / 非数值）与缺失前向收益的跳过口径
  - `stage_factor_ic`：基准前向收益按日期去重、逐因子×视界出判定行、样本不足只记录不裁决
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

# 内部实现包按 `_eval_decision_quality.*` 绝对名导入，经入口脚本加载以完成 sys.path 自助修补
mod = load_script("eval-decision-quality.py", module_name="eval_decision_quality_stages_under_test")


def _rising_series(bars: int = 80, start_price: float = 100.0) -> list[dict]:
    """逐日递增的收盘序列（视界最长 60 日，需留足后置 bar）。"""
    day = date(2026, 1, 5)
    series = []
    for index in range(bars):
        series.append({"date": day.isoformat(), "close": start_price + index})
        day += timedelta(days=1)
    return series


def _signal(rep_date: str, values: dict) -> dict:
    return {"event": "signal", "signal_type": mod.SIGNAL_FACTOR, "report_date": rep_date, "detail": {"values": values}}


class TestCollectFactorPairs:
    """ "(因子值, 基准前向收益)" 配对：脏值必须跳过而不是让整列 IC 变 NaN。"""

    def test_pairs_only_for_available_values_and_horizons(self):
        signals = [
            _signal("2026-01-05", {"momentum": 0.3, "value": None, "junk": "abc"}),
            _signal("2026-01-06", {"momentum": 0.5}),
        ]
        fwd = {"2026-01-05": {"5": 0.01, "20": None}, "2026-01-06": {"5": 0.02}}
        pairs = mod.collect_factor_pairs(signals, fwd)
        assert pairs["momentum"] == {"5": [(0.3, 0.01), (0.5, 0.02)]}
        assert "value" not in pairs, "None 值不参与配对"
        assert "junk" not in pairs, "非数值不参与配对"
        assert "20" not in pairs["momentum"], "该视界前向收益缺失时不产生配对"

    def test_signal_without_index_forward_is_skipped(self):
        signals = [_signal("2026-01-07", {"momentum": 0.3})]
        assert mod.collect_factor_pairs(signals, {}) == {}


class TestStageFactorIc:
    """阶段二：组合级因子无横截面，用基准指数前向收益作代理（结论只回答「能否预测市场」）。"""

    @pytest.fixture(name="ledger")
    def _ledger(self, tmp_path):
        series = _rising_series()
        rep_date = series[5]["date"]
        rows = [_signal(rep_date, {"momentum": 0.3, "value": 1.1}), _signal(rep_date, {"momentum": 0.6})]
        (tmp_path / "signal_ledger.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
        )
        return tmp_path, series, rep_date

    def test_rows_cover_every_factor_and_horizon(self, ledger):
        ledger_dir, series, rep_date = ledger
        result = mod.stage_factor_ic(ledger_dir=ledger_dir, days=120, index_fn=lambda *_a, **_k: series)
        assert result["phase"] == "factor-ic"
        assert result["n_signals"] == 2
        assert result["date_range"] == [rep_date, rep_date]
        assert {row["factor"] for row in result["rows"]} == {"momentum", "value"}
        assert [row["horizon"] for row in result["rows"] if row["factor"] == "momentum"] == list(mod.HORIZONS)
        momentum_n = {row["horizon"]: row["n"] for row in result["rows"] if row["factor"] == "momentum"}
        assert set(momentum_n.values()) == {2}, "同一日期的两条信号都进入配对"
        assert all(row["n"] == 1 for row in result["rows"] if row["factor"] == "value")
        assert all("verdict" in row for row in result["rows"])

    def test_single_signal_per_factor_is_recorded_not_judged(self, ledger):
        """样本量不足时只记录不裁决（图稳定值由 verdict_discrimination 决定，不在此重复断言）。"""
        ledger_dir, series, _rep = ledger
        result = mod.stage_factor_ic(ledger_dir=ledger_dir, days=120, index_fn=lambda *_a, **_k: series)
        value_rows = [row for row in result["rows"] if row["factor"] == "value"]
        assert value_rows and all(row["tercile_monotonic"] is False for row in value_rows)
        assert "代理" in result["proxy_note"]
        assert result["caveats"] == mod.CAVEATS

    def test_missing_index_series_degrades_to_zero_pairs(self, ledger):
        ledger_dir, _series, rep = ledger
        result = mod.stage_factor_ic(ledger_dir=ledger_dir, days=120, index_fn=lambda *_a, **_k: None)
        assert result["rows"] == [], "无基准序列时不出判定行（避免拿 0 收益当结论）"
        assert result["n_signals"] == 2
        assert result["date_range"] == [rep, rep]
