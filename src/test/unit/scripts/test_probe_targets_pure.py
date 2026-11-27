"""探测目标 `_probes`（csi/sector_flow）与 `_eval_halluc_sampler.holdings` 纯函数测试。

覆盖：指数 K 线探测的日期换算 / provider 实现探测 / 因子可行性三态判定、
行业资金流逐通道探测的四类结果（成功/空榜/不可用/异常）、
持仓明细的品种分类计数、组合数值委派与数据集按序号过滤。
均为纯计算或注入 fetch，不触网。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(autouse=True)
def _scripts_on_path(monkeypatch):
    """把 scripts/ 加入导入面，供 `_probes` / `_eval_halluc_sampler` 子包导入。"""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    return None


def _csi():
    from _probes import csi

    return csi


# ── 日期换算 ─────────────────────────────────────────────────


def test_days_since_handles_missing_and_broken():
    csi = _csi()

    assert csi._days_since(None) == -1
    assert csi._days_since("") == -1
    assert csi._days_since("not-a-date") == -1
    assert csi._days_since("2026-13-01") == -1


def test_days_since_counts_calendar_days():
    csi = _csi()
    today = date.today()

    assert csi._days_since(today.isoformat()) == 0
    assert csi._days_since((today - timedelta(days=7)).isoformat()) == 7


# ── provider 实现探测 ────────────────────────────────────────


def test_has_fetch_index_kline_true_for_real_provider():
    csi = _csi()

    assert csi._has_fetch_index_kline("src.python.providers.tencent") is True


def test_has_fetch_index_kline_false_for_missing_module():
    csi = _csi()

    assert csi._has_fetch_index_kline("src.python.providers.no_such_module") is False


# ── 因子可行性判定三态 ───────────────────────────────────────


def test_evaluate_all_five_fresh_is_5f():
    csi = _csi()
    freshness = {f"idx{i}": 2 for i in range(5)}

    out = csi.evaluate(freshness, 5, 10)

    assert out["verdict"] == "5f"
    assert out["stale_codes"] == []
    assert out["stale_threshold_days"] == 10
    assert sorted(out["available"]) == sorted(freshness)


def test_evaluate_three_fresh_with_stale_lists_replacements():
    csi = _csi()
    freshness = {"a": 1, "b": 2, "c": 3, "d": 99, "e": -1}

    out = csi.evaluate(freshness, 5, 10)

    assert out["verdict"] == "3f"
    assert sorted(out["available"]) == ["a", "b", "c"], "-1（无数据）不计可用"
    assert out["stale_codes"] == ["d"]
    assert "停更指数" in out["message"]


def test_evaluate_two_fresh_is_infeasible():
    csi = _csi()

    out = csi.evaluate({"a": 1, "b": 2, "c": 99}, 5, 10)

    assert out["verdict"] == "infeasible"
    assert "不可实现" in out["message"]


# ── provider 直调 ────────────────────────────────────────────


def test_probe_code_delegates_to_provider(monkeypatch):
    csi = _csi()
    from src.python.providers import sina, tencent

    calls: list[tuple[str, int]] = []

    def _fake(code: str, days: int):
        calls.append((code, days))
        return [{"date": "2026-01-05", "close": 1.0}]

    monkeypatch.setattr(tencent, "fetch_index_kline", _fake)
    monkeypatch.setattr(sina, "fetch_index_kline", _fake)

    assert csi.probe_code("sh000001", 30) == [{"date": "2026-01-05", "close": 1.0}]
    assert csi.probe_code("sh000001", 30, provider="sina") == [{"date": "2026-01-05", "close": 1.0}]
    assert calls == [("sh000001", 30), ("sh000001", 30)]


# ── 行业资金流逐通道探测 ─────────────────────────────────────


def test_probe_channel_counts_successful_rows():
    from _probes import sector_flow

    ok, detail = sector_flow._probe_channel("东财", lambda: [{"name": "银行"}, {"name": "非银"}], 3)

    assert ok == 3
    assert len(detail) == 3
    assert all("成功" in line and "行业数=2" in line for line in detail)


def test_probe_channel_reports_empty_board():
    from _probes import sector_flow

    ok, detail = sector_flow._probe_channel("东财", lambda: [], 2)

    assert ok == 0
    assert all("空榜" in line for line in detail)


def test_probe_channel_reports_unavailable_kind():
    from _probes import sector_flow
    from src.python.providers.akshare_extras import _SectorFlowUnavailable

    def _raise() -> list[dict]:
        raise _SectorFlowUnavailable("connection", "同花顺")

    ok, detail = sector_flow._probe_channel("同花顺", _raise, 1)

    assert ok == 0
    assert "不可用" in detail[0]
    assert "connection" in detail[0]


def test_probe_channel_reports_generic_exception():
    from _probes import sector_flow

    def _raise() -> list[dict]:
        raise RuntimeError("boom")

    ok, detail = sector_flow._probe_channel("同花顺", _raise, 1)

    assert ok == 0
    assert "异常" in detail[0]
    assert "RuntimeError: boom" in detail[0]


# ── 幻觉抽样：持仓派生 ───────────────────────────────────────


def test_compute_categories_classifies_by_code_prefix():
    from _eval_halluc_sampler import holdings

    details = [
        {"code": "005827"},
        {"code": "110011"},
        {"code": "510300"},
        {"code": "600519"},
        {"code": "002943"},
        {"code": "430047"},
    ]

    counts = holdings._compute_categories(details)

    assert counts["基金"] == 2
    assert counts["ETF"] == 1
    assert counts["股票"] == 2
    assert counts["其他"] == 1
    assert sum(counts.values()) == len(details)


def test_compute_portfolio_values_extends_delegate_output():
    from _eval_halluc_sampler import holdings

    vals = holdings._compute_portfolio_values([{"code": "600519", "market_value": 100.0}])

    assert vals["total_today_profit"] == 0.0


def test_load_datasets_filter_selects_by_one_based_index():
    from _eval_halluc_sampler import holdings

    full = holdings._load_datasets()

    assert full, "内置语料不应为空"
    first = holdings._load_datasets([1])
    assert first == full[:1]
    assert len(holdings._load_datasets([1, 2])) == min(2, len(full))
