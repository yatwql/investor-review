"""决策结算服务的取数降级与判据分支契约测试。

锁住的契约：
  - 行情/基准取数异常一律降级为 None 序列，不抛出
  - 空序列取不到最新收盘 → 视界不可判定（返回空结论元组）
  - 决策日缺失时按目标视界计视界数（不回退为 0）
  - 无序列时按日期取值返回 None

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_decision_settlement_branches.py -v
"""

from __future__ import annotations

import pytest

from src.python.core import decision_ledger as dl
from src.python.report import decision_settlement as ds

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _bars(pairs: list[tuple[str, float]]) -> list[dict]:
    return [{"date": d, "close": c} for d, c in pairs]


class TestSeriesLookup:
    """序列取值的空输入口径。"""

    def test_empty_series_at_date_is_none(self):
        assert ds._series_at_date([], "2026-01-05") is None

    def test_last_close_before_target_date_is_used(self):
        series = _bars([("2026-01-05", 10.0), ("2026-01-07", 11.0)])

        assert ds._series_at_date(series, "2026-01-06") == pytest.approx(10.0)


class TestFetchDegrade:
    """取数链路的异常降级。"""

    def test_price_series_exception_degrades_to_none(self, monkeypatch):
        class _BoomCalculator:
            def calculate_for_holding(self, **_kwargs):
                raise RuntimeError("history boom")

        monkeypatch.setattr("src.python.report.portfolio_history.PortfolioHistoryCalculator", _BoomCalculator)

        assert ds.fetch_price_series("600519", "贵州茅台", 60) is None

    def test_index_series_exception_degrades_to_none(self, monkeypatch):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("index boom")

        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", _boom)

        assert ds.fetch_index_series("sh000300", 60) is None


class TestSettleFromSeries:
    """单视界结算的不可判定分支。"""

    def test_empty_series_is_not_settleable(self):
        result = ds._settle_from_series(
            series=[],
            direction=dl.DIRECTION_LONG,
            baseline=10.0,
            rep_date="2026-01-05",
            horizon=5,
            index_series=None,
            threshold=dl.DIRECTION_THRESHOLD,
        )

        assert result == (None, None, 0.0, None, 0)

    def test_missing_report_date_counts_target_horizon(self):
        result = ds._settle_from_series(
            series=_bars([("2026-01-05", 10.0), ("2026-01-06", 11.0)]),
            direction=dl.DIRECTION_LONG,
            baseline=10.0,
            rep_date="",
            horizon=5,
            index_series=None,
            threshold=dl.DIRECTION_THRESHOLD,
        )

        outcome, hit, raw, bench_ret, horizon_used = result
        assert horizon_used == 5
        assert raw == pytest.approx(0.1)
        assert bench_ret is None
        assert outcome is not None
        assert isinstance(hit, bool)


class TestSettleMissingBaseline:
    """无结算基线的决策按视界暂缓（不猜方向、不落账）。"""

    def test_missing_baseline_defers_every_target_horizon(self, tmp_path):
        from src.python.config.features import reset_feature_flags, set_feature_enabled
        from src.test._relative_dates import day

        set_feature_enabled("decision_reflection", True)
        try:
            ledger = str(tmp_path / "ledger.jsonl")
            report_date = day(0)
            dl.append_decision(
                code="600000",
                name="test",
                direction=dl.DIRECTION_LONG,
                carrier=dl.CARRIER_DISCIPLINE,
                report_date=report_date,
                baseline_close=None,
                path=ledger,
            )

            result = ds.settle_pending_decisions(
                report_date=report_date,
                ledger_path=ledger,
                price_series_fn=lambda *_a: _bars([(report_date, 10.0)]),
                index_series_fn=lambda *_a: None,
            )
        finally:
            reset_feature_flags()

        expected_deferred = len({max(int(h), dl.MIN_SETTLE_BARS) for h in dl.SETTLE_HORIZONS})
        assert result["settled"] == 0
        assert result["deferred"] == expected_deferred, "无基线的登记按目标视界各计一次暂缓"
        assert result["summary"] == []
