# -*- coding: utf-8 -*-
"""按交易日取场外净值（fetcher/nav_lookup.py）单元测试。

取数链本身由既有 provider 测试覆盖；本文件只钉住「交易日 → 净值」的选取与降级口径：
当日命中取当日、当日无净值取之前最近净值日并标注、全无数据返回 None（绝不猜价）。
"""

from __future__ import annotations

import pytest

from src.python.fetcher import nav_lookup

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


def _bars(*pairs: tuple[str, float]) -> list[dict]:
    return [{"date": date, "nav": nav, "acc_nav": nav} for date, nav in pairs]


def test_exact_trade_date_hit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        nav_lookup,
        "fetch_with_incremental_fallback",
        lambda *args, **kwargs: _bars(("2026-07-01", 1.2), ("2026-07-02", 1.25)),
    )
    result = nav_lookup.resolve_nav_on_trade_date("007301", "2026-07-01")
    assert result is not None
    assert result["nav"] == pytest.approx(1.2)
    assert result["nav_date"] == "2026-07-01"
    assert result["exact_date"] is True


def test_non_trading_day_falls_back_to_previous_nav(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        nav_lookup,
        "fetch_with_incremental_fallback",
        lambda *args, **kwargs: _bars(("2026-07-02", 1.2), ("2026-07-03", 1.3)),
    )
    result = nav_lookup.resolve_nav_on_trade_date("007301", "2026/07/04")
    assert result is not None
    assert result["nav"] == pytest.approx(1.3)
    assert result["nav_date"] == "2026-07-03"
    assert result["exact_date"] is False


def test_no_nav_before_trade_date_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        nav_lookup,
        "fetch_with_incremental_fallback",
        lambda *args, **kwargs: _bars(("2026-07-05", 1.2)),
    )
    assert nav_lookup.resolve_nav_on_trade_date("007301", "2026-07-01") is None


def test_empty_nav_series_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(nav_lookup, "fetch_with_incremental_fallback", lambda *args, **kwargs: [])
    assert nav_lookup.resolve_nav_on_trade_date("007301", "2026-07-01") is None


def test_fetch_exception_returns_none(monkeypatch: pytest.MonkeyPatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("网络异常")

    monkeypatch.setattr(nav_lookup, "fetch_with_incremental_fallback", _boom)
    assert nav_lookup.resolve_nav_on_trade_date("007301", "2026-07-01") is None


def test_invalid_trade_date_returns_none(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple] = []
    monkeypatch.setattr(nav_lookup, "fetch_with_incremental_fallback", lambda *a, **k: calls.append(a) or [])
    assert nav_lookup.resolve_nav_on_trade_date("007301", "2026-13-40") is None
    assert calls == []  # 日期非法：连取数都不发起


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2026-07-01", "2026-07-01"), ("2026/7/1", "2026-07-01"), ("2026-7-01", "2026-07-01")],
)
def test_normalize_trade_date_accepts_separators(raw: str, expected: str):
    assert nav_lookup.normalize_trade_date(raw) == expected


@pytest.mark.parametrize("raw", ["20260701", "2026-07", "", "abc"])
def test_normalize_trade_date_rejects_bad_shape(raw: str):
    with pytest.raises(ValueError):
        nav_lookup.normalize_trade_date(raw)
