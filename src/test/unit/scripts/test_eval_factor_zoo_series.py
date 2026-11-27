"""因子动物园评测的日频序列 / 阶段产物 / 注入探针纯函数测试（网络无关）。

覆盖 `_eval_factor_zoo` 的 series 与 stage、probe 面：差分与步进口径、
多族信号序列构建（含降级族与未知族）、族相关性评估的三种跳过分支、
阶段产物读写与对数市值、池内等权收益、穿透代码递归抽取与字段值键映射。
边界清单见 test_eval_factor_zoo_edge.py。
"""

from __future__ import annotations

import math

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def zoo():
    return load_script("eval-factor-zoo.py")


def _index_bars(count: int) -> list[dict]:
    from datetime import date, timedelta

    start = date(2025, 1, 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "close": 100.0 + i * 0.5} for i in range(count)]


# ── 差分与步进判定 ────────────────────────────────────────────


def test_delta_drops_first_date_and_keeps_order(zoo):
    from _eval_factor_zoo import metrics

    out = metrics._delta({"2026-01-02": 3.0, "2026-01-01": 1.0})

    assert list(out) == ["2026-01-02"]
    assert out["2026-01-02"] == pytest.approx(2.0)


def test_delta_of_single_point_is_empty(zoo):
    from _eval_factor_zoo import metrics

    assert metrics._delta({"2026-01-01": 5.0}) == {}


def test_step_signal_flags_constant_and_sparse_series(zoo):
    from _eval_factor_zoo import metrics

    assert metrics._is_step_signal([]) is True  # 空序列按步进口径（无日频变化）
    assert metrics._is_step_signal([0.0] * 40) is True  # 常量
    assert metrics._is_step_signal([1.0] * 40) is False  # 每日都变


def test_step_signal_threshold_is_fraction_based(zoo):
    from _eval_factor_zoo import catalog, metrics

    n = 100
    nonzero = max(1, int(n * catalog.STEP_NONZERO_FRACTION) - 1)
    below = [1.0] * nonzero + [0.0] * (n - nonzero)
    above = [1.0] * (nonzero + 5) + [0.0] * (n - nonzero - 5)

    assert metrics._is_step_signal(below) is True
    assert metrics._is_step_signal(above) is False


# ── 族序列构建 ────────────────────────────────────────────────


def test_build_family_series_rejects_snapshot_family(zoo):
    from _eval_factor_zoo import catalog, metrics

    with pytest.raises(ValueError, match="快照"):
        metrics.build_family_series(catalog.FAMILY_REBALANCE, _index_bars(10))


def test_build_family_series_rejects_unknown_family(zoo):
    from _eval_factor_zoo import metrics

    with pytest.raises(ValueError, match="未知信号族"):
        metrics.build_family_series("no_such_family", _index_bars(10))


def test_build_family_series_valuation_percentile_keys_are_dates(zoo):
    from _eval_factor_zoo import catalog, metrics

    bars = _index_bars(80)
    series = metrics.build_family_series(catalog.FAMILY_VALUATION_PERCENTILE, bars)

    assert series, "价格分位族在足够样本下须产出序列"
    assert set(series) <= {b["date"] for b in bars}
    assert all(isinstance(v, float) for v in series.values())


def test_build_family_series_style_beta_requires_pool(zoo):
    from _eval_factor_zoo import catalog, metrics

    with pytest.raises(ValueError, match="池均值"):
        metrics.build_family_series(catalog.FAMILY_STYLE_BETA, _index_bars(80))


def test_build_family_series_style_beta_with_pool(zoo):
    from _eval_factor_zoo import catalog, metrics

    bars = _index_bars(90)
    pool = {b["date"]: 0.001 for b in bars}
    series = metrics.build_family_series(catalog.FAMILY_STYLE_BETA, bars, pool)

    assert isinstance(series, dict)
    assert set(series) <= {b["date"] for b in bars}


# ── 族相关性评估的跳过分支 ────────────────────────────────────


def _factor_series(n: int) -> dict[str, float]:
    from datetime import date, timedelta

    start = date(2025, 1, 1)
    return {(start + timedelta(days=i)).isoformat(): float(i % 7) for i in range(n)}


def test_evaluate_correlation_empty_family_is_skipped(zoo):
    from _eval_factor_zoo import metrics

    out = metrics.evaluate_factor_correlation(_factor_series(40), {"market_temperature": {}})

    assert out["per_family"]["market_temperature"]["rho"] is None
    assert "为空" in out["per_family"]["market_temperature"]["note"]
    assert out["max_abs_rho"] is None
    assert out["low_corr"] is False
    assert out["note"], "无可评估族时须给 fail-closed 说明"


def test_evaluate_correlation_insufficient_alignment_is_skipped(zoo):
    from _eval_factor_zoo import metrics

    factor = _factor_series(40)
    short = dict(list(factor.items())[-3:])  # 共享日不足 MIN_PAIRS
    out = metrics.evaluate_factor_correlation(factor, {"tail_risk_var95": short})

    assert out["per_family"]["tail_risk_var95"]["rho"] is None
    assert "对齐样本" in out["per_family"]["tail_risk_var95"]["note"]


def test_evaluate_correlation_step_signal_scores_zero(zoo):
    from _eval_factor_zoo import metrics

    constant_factor = dict.fromkeys(_factor_series(40), 1.0)
    family = {"market_temperature": _factor_series(40)}
    out = metrics.evaluate_factor_correlation(constant_factor, family)

    assert out["step_signal"] is True
    assert out["per_family"]["market_temperature"]["rho"] == 0.0
    assert out["low_corr"] is True


def test_evaluate_correlation_independent_series_scores_low(zoo):
    from _eval_factor_zoo import catalog, metrics

    factor = _factor_series(400)
    dates = sorted(factor)
    shuffled = {d: factor[dates[(i * 37) % len(dates)]] for i, d in enumerate(dates)}
    out = metrics.evaluate_factor_correlation(factor, {"valuation_percentile": shuffled})

    assert out["step_signal"] is False
    assert out["max_abs_rho"] is not None
    assert out["low_corr"] is (out["max_abs_rho"] < catalog.CORR_LOW)
    assert out["closest_family"] == "valuation_percentile"


# ── 阶段产物读写与对数市值 ────────────────────────────────────


def test_stage_json_roundtrip_creates_parents(zoo, tmp_path):
    from _eval_factor_zoo import stages

    target = tmp_path / "nested" / "payload.json"
    stages._write_json(target, {"k": [1, 2], "中文": True})

    assert stages._read_json(target) == {"k": [1, 2], "中文": True}


def test_stage_read_json_tolerates_missing_and_broken(tmp_path):
    from _eval_factor_zoo import stages

    assert stages._read_json(tmp_path / "absent.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert stages._read_json(broken) is None


def test_json_cap_log_rejects_illegal_values(zoo):
    from _eval_factor_zoo import stages

    for bad in (None, "abc", 0, -1.0, "", float("nan"), float("inf")):
        assert stages.json_cap_log(bad) is None, f"{bad!r} 应判非法"


def test_json_cap_log_is_log10_scaled(zoo):
    from _eval_factor_zoo import stages

    assert stages.json_cap_log(1e10) == pytest.approx(1000.0)
    assert stages.json_cap_log(1e8) == pytest.approx(800.0)
    assert stages.json_cap_log(3e9) == pytest.approx(round(math.log10(3e9) * 100, 2))


def test_stage_catalog_writes_frozen_artifacts(zoo, tmp_path):
    from _eval_factor_zoo import stages

    catalog = stages.stage_catalog(tmp_path)

    assert catalog, "冻结目录不应为空"
    payload = stages._read_json(tmp_path / "factor_catalog.json")
    assert payload["catalog"] == catalog
    assert payload["families"]
    assert (tmp_path / "_catalog.md").exists()


def test_pool_mean_returns_respects_min_codes(zoo):
    from _eval_factor_zoo import catalog, stages

    bars = {
        "600519": [{"date": "2026-01-05", "close": 100.0}, {"date": "2026-01-06", "close": 110.0}],
        "000001": [{"date": "2026-01-05", "close": 10.0}, {"date": "2026-01-06", "close": 9.0}],
    }
    mean = stages._pool_mean_returns(bars, [])

    if catalog.MIN_CODES_PER_DAY <= 2:
        assert mean["2026-01-06"] == pytest.approx(0.0)  # +10% 与 -10% 等权
    else:
        assert mean == {}, "代码数不足当日最小池规模时不得产出均值"

    single = stages._pool_mean_returns({"600519": bars["600519"]}, [])
    assert single == {}


# ── 注入探针与字段键映射 ──────────────────────────────────────


def test_extract_share_codes_walks_nested_shapes(zoo):
    from _eval_factor_zoo import probe

    nodes = {
        "top10": [
            {"code": "600519", "codes": ["000001", "not_a_code"]},
            {"name": "基金", "children": [{"code": "300750"}]},
        ]
    }
    assert probe._extract_share_codes(nodes) == ["000001", "300750", "600519"]


def test_extract_share_codes_missing_code_key_is_empty(zoo):
    from _eval_factor_zoo import probe

    assert probe._extract_share_codes({"name": "无代码"}) == []


def test_required_value_key_maps_field_types(zoo):
    from _eval_factor_zoo import probe

    assert probe._required_value_key({"slug": "fund_size_log_cap"}, probe.FIELD_VAL) == "market_cap"
    assert probe._required_value_key({"slug": "fund_pb"}, probe.FIELD_VAL) == "pb"
    assert probe._required_value_key({"slug": "fund_roe"}, probe.FIELD_FIN) == "roe"
    assert probe._required_value_key({"slug": "fund_revenue_yoy"}, probe.FIELD_FIN) == "revenue_yoy"
    assert probe._required_value_key({"slug": "fund_gross_margin"}, probe.FIELD_FIN) == "gross_margin"
    assert probe._required_value_key({"slug": "fund_roe"}, probe.FIELD_BARS) == ""


def test_probe_bars_returns_empty_on_unavailable(zoo, monkeypatch):
    from _eval_factor_zoo import probe

    from src.python.fetcher import chain_incremental

    monkeypatch.setattr(chain_incremental, "fetch_with_incremental_fallback", lambda *a, **k: None)
    assert probe.probe_bars("600519") == []

    monkeypatch.setattr(
        chain_incremental,
        "fetch_with_incremental_fallback",
        lambda *a, **k: [{"date": "2026-01-05", "close": 1.0}],
    )
    assert probe.probe_bars("600519") == [{"date": "2026-01-05", "close": 1.0}]


def test_build_stock_pool_falls_back_when_penetration_fails(zoo, monkeypatch):
    from _eval_factor_zoo import probe

    from src.python.core import reader
    from src.python.core.models import Holding
    from src.python.report import penetration

    monkeypatch.setattr(reader, "read_holdings", lambda _p: [Holding("证券", "贵州茅台", "600519", 100, 1500.0)])

    def _boom(*_a, **_k):
        raise RuntimeError("穿透不可用")

    monkeypatch.setattr(penetration, "compute_penetration_top10", _boom)

    pool = probe.build_stock_pool("ignored.xlsx")

    assert pool["direct_stocks"] == ["600519"]
    assert pool["penetration_stocks"] == []
    assert "穿透失败" in pool["penetration_note"]
    assert pool["codes"] == ["600519"]
