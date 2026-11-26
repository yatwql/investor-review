"""历史走势质量守卫的空输入分支：空序列跳过、无有效观测返回 None、空 bars 不诊断。

这三条分支只在「某标的完全没有走势数据 / 整条走势为空」时触发，正常取值路径的
用例覆盖不到，但它们决定了空态是否被静默当成「无滞后 / 无异常」。
"""

from __future__ import annotations

import pytest

from src.python.report._history_quality import _detect_terminal_staleness, _diagnose_return

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestTerminalStalenessEmptyInputs:
    def test_empty_series_is_skipped(self):
        """空序列不参与滞后判定：只有有数据的标的进入 assets。"""
        result = _detect_terminal_staleness(
            [
                ("空净值基金(000000)", "000000", []),
                ("滞后基金(110011)", "110011", [{"date": "2026-01-05", "value": 80.0}]),
            ],
            merged_dates=["2026-01-05", "2026-01-06", "2026-01-07"],
            terminal_total=100.0,
        )

        assert result is not None
        assert [a["label"] for a in result["assets"]] == ["滞后基金(110011)"]
        assert result["max_lag_trading_days"] == 2
        # 权重按终点总市值折算（80/100），空序列不占权重
        assert result["assets"][0]["weight_pct"] == pytest.approx(80.0)

    def test_all_series_empty_returns_none(self):
        """全部标的都无走势数据 → 无滞后结论（不得伪造滞后提示）。"""
        assert (
            _detect_terminal_staleness(
                [("甲(000000)", "000000", []), ("乙(110011)", "110011", [])],
                merged_dates=["2026-01-05", "2026-01-06"],
                terminal_total=100.0,
            )
            is None
        )


class TestDiagnoseReturnEmptyBars:
    def test_empty_bars_returns_early(self, caplog):
        """空 bars 无起止日可诊断 → 直接返回 None 且不写诊断日志。"""
        with caplog.at_level("INFO", logger="invest"):
            assert _diagnose_return([], 0, {}, 0.0, 0) is None
        assert caplog.text == ""
