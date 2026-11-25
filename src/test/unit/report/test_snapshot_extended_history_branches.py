"""report/_snapshot.py 的长窗取数配置兜底与危机回放指数层跳过分支。

锁住的契约：
  - 危机表区间起点不可解析时取数窗口封顶 3650；
  - ``history`` 子配置非 dict 或 ``lookback_days`` 不可转 int 时，长窗窗口回退 365 交易日；
  - 长窗取数异常只记 info 并返回 None（子块按数据不足降级）；持仓为空返回 None；
  - 危机回放指数层在 history 非 dict / benchmark_indices 非 dict 或为空时返回 None。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.report import _snapshot as snap
from src.python.report.progress import SilentProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_HOLDINGS = [SimpleNamespace(code="600519", name="贵州茅台", shares=100)]


class _FailingCalculator:
    """固定的长窗取数失败替身（抛异常路径）。"""

    def __init__(self, **_kwargs) -> None:
        pass

    def get_combined_timeseries(self, *_args, **_kwargs):
        raise RuntimeError("历史源不可达")


class _UnavailableCalculator:
    """固定的长窗取数失败替身（返回 unavailable 契约路径）。"""

    def __init__(self, **_kwargs) -> None:
        pass

    def get_combined_timeseries(self, *_args, **_kwargs) -> dict:
        return {"status": "unavailable"}


def test_crisis_index_days_falls_back_to_source_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.python.analysis import crisis_annotation

    monkeypatch.setattr(crisis_annotation, "CRISIS_INTERVALS", [{"start": "不可解析"}])
    assert snap._crisis_index_days() == snap._CRISIS_INDEX_DAYS_MAX


def test_extended_history_empty_holdings_returns_none() -> None:
    assert snap.fetch_extended_history([], {}, SilentProgressReporter()) is None


def test_extended_history_non_dict_history_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, int] = {}

    class _OkCalculator:
        def __init__(self, **_kwargs) -> None:
            pass

        def get_combined_timeseries(self, _tuples, days=0, **_kwargs) -> dict:
            seen["days"] = days
            return {"status": "ok"}

    monkeypatch.setattr("src.python.report.portfolio_history.PortfolioHistoryCalculator", _OkCalculator)
    snap.fetch_extended_history(_HOLDINGS, {"history": "坏配置"}, SilentProgressReporter())
    assert seen["days"] == snap._EXTENDED_HISTORY_DAYS


def test_extended_history_unparsable_lookback_days_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, int] = {}

    class _OkCalculator:
        def __init__(self, **_kwargs) -> None:
            pass

        def get_combined_timeseries(self, _tuples, days=0, **_kwargs) -> dict:
            seen["days"] = days
            return {"status": "unavailable"}

    monkeypatch.setattr("src.python.report.portfolio_history.PortfolioHistoryCalculator", _OkCalculator)
    result = snap.fetch_extended_history(_HOLDINGS, {"history": {"lookback_days": "久"}}, SilentProgressReporter())
    assert (result, seen["days"]) == (None, snap._EXTENDED_HISTORY_DAYS)


def test_extended_history_exception_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.python.report.portfolio_history.PortfolioHistoryCalculator", _FailingCalculator)
    assert snap.fetch_extended_history(_HOLDINGS, {}, SilentProgressReporter()) is None


def test_extended_history_unavailable_status_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.python.report.portfolio_history.PortfolioHistoryCalculator", _UnavailableCalculator)
    assert snap.fetch_extended_history(_HOLDINGS, {}, SilentProgressReporter()) is None


def test_crisis_index_series_skips_non_dict_history_and_indices() -> None:
    assert snap.fetch_crisis_index_series({"history": "坏配置"}) is None
    assert snap.fetch_crisis_index_series({"history": {"benchmark_indices": "坏配置"}}) is None
    assert snap.fetch_crisis_index_series({"history": {"benchmark_indices": {}}}) is None
