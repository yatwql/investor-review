"""因子暴露取数并行度与小片告警：持仓 K 线与因子指数 K 线同池并发 + 单路慢告警。

回归场景（2026-11-01 12:27 运行）：因子暴露 10.48s，其中 9.4s 是「持仓 K 线全部
回来后才开始拉因子指数」的串行等待，且无单路耗时、无告警。
"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import cast

import pytest

from src.python.analysis import style_factor_regression as sfr
from src.python.report import _report_factor_metrics as rfm
from src.python.report.progress import ProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _holding(code: str, name: str = "标的") -> SimpleNamespace:
    return SimpleNamespace(code=code, name=name, shares=100.0)


def _bars() -> list[dict]:
    return [{"date": "2026-09-01", "close": 1.0}]


def _stub_pipeline(monkeypatch) -> None:
    monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: True)
    monkeypatch.setattr(sfr, "asif_portfolio_daily_returns", lambda bars: {"2026-09-01": 0.02})
    monkeypatch.setattr(sfr, "filter_stale_factor_klines", lambda klines, today: (dict(klines), []))
    monkeypatch.setattr(sfr, "klines_to_returns", lambda bars: {"2026-09-01": 0.01})
    monkeypatch.setattr(sfr, "compute_factor_exposure", lambda *a, **k: {"available": True, "sample_count": 60})


class _Reporter:
    def info(self, *a, **k):
        pass

    def ok(self, *a, **k):
        pass

    def warn(self, *a, **k):
        pass


class TestFactorFetchParallelism:
    def test_holdings_and_factor_indices_fetch_concurrently(self, monkeypatch):
        """两组取数同池并发：总耗时 ≈ 单路耗时，而不是两组之和。"""
        _stub_pipeline(monkeypatch)
        sleep = 0.2
        calls: list[str] = []

        def _slow_holding(code, name, days):
            calls.append(f"h:{code}")
            time.sleep(sleep)
            return _bars()

        def _slow_index(code, days=90, start_from=None):
            calls.append(f"i:{code}")
            time.sleep(sleep)
            return _bars()

        monkeypatch.setattr(rfm, "_fetch_holding_bars", _slow_holding)
        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", _slow_index)

        holdings = [_holding("600900"), _holding("601398"), _holding("601939")]
        # 池内 = 持仓 + 因子指数；池外另有一次基准指数（沪深300）
        serial_seconds = (len(holdings) + len(sfr.FACTOR_INDICES) + 1) * sleep

        started = time.perf_counter()
        result = rfm.compute_factor_exposure_data(holdings, {}, cast(ProgressReporter, _Reporter()))
        elapsed = time.perf_counter() - started

        assert result is not None and result.get("available") is True
        assert len(calls) == len(holdings) + len(sfr.FACTOR_INDICES) + 1, calls
        assert elapsed < serial_seconds * 0.7, f"两组取数未并发（{elapsed:.2f}s vs 串行 {serial_seconds:.2f}s）"

    def test_slow_single_fetch_logs_warning_with_label(self, monkeypatch, caplog):
        """单路取数超阈 → WARNING 带标的与耗时（此前只有阶段总数，无法定位）。"""
        _stub_pipeline(monkeypatch)
        monkeypatch.setattr(rfm, "_SLOW_FETCH_WARN_SECONDS", 0.05)

        def _slow_holding(code, name, days):
            if code == "600900":
                time.sleep(0.12)
            return _bars()

        monkeypatch.setattr(rfm, "_fetch_holding_bars", _slow_holding)
        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", lambda code, days=90, start_from=None: _bars())

        with caplog.at_level(logging.WARNING, logger="invest"):
            rfm.compute_factor_exposure_data([_holding("600900", "长江电力")], {}, cast(ProgressReporter, _Reporter()))

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("取数偏慢" in m and "600900" in m for m in warnings), warnings
