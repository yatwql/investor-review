"""`eval-decision-quality.py` 回测脚本单元测试（纯函数 + 注入取数的阶段聚合）。

覆盖：账本读取过滤、固定视界前向收盘、Spearman/三分位单调、三态判定、
阶段聚合（命中率/IC/口径对比）——全部离线注入，不触网。
"""

from __future__ import annotations

import json

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

mod = load_script("eval-decision-quality.py")


def _bar(date: str, close: float) -> dict:
    return {"date": date, "close": close}


def _series(dates_closes: list[tuple[str, float]]) -> list[dict]:
    return [_bar(d, c) for d, c in dates_closes]


# ── 账本读取 ──────────────────────────────────────────────


def test_load_decisions_filters_direction_and_baseline(tmp_path):
    p = tmp_path / "decision_ledger.jsonl"
    rows = [
        {
            "event": "decision",
            "decision_id": "a",
            "direction": 1,
            "baseline_close": 1.2,
            "report_date": "2026-09-17",
            "code": "600000",
            "name": "X",
        },
        {
            "event": "decision",
            "decision_id": "b",
            "direction": 0,
            "baseline_close": 1.2,
            "report_date": "2026-09-17",
            "code": "600001",
            "name": "Y",
        },
        {
            "event": "decision",
            "decision_id": "c",
            "direction": -1,
            "baseline_close": 0,
            "report_date": "2026-09-17",
            "code": "600002",
            "name": "Z",
        },
        {
            "event": "decision",
            "decision_id": "d",
            "direction": 1,
            "baseline_close": 1.2,
            "report_date": "",
            "code": "600003",
            "name": "W",
        },
        {"event": "settlement", "decision_id": "a", "outcome": "hit"},
    ]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    out = mod.load_decisions(p)
    assert [d["decision_id"] for d in out] == ["a"]


def test_load_signals_filters_type(tmp_path):
    p = tmp_path / "signal_ledger.jsonl"
    rows = [
        {"event": "signal", "signal_type": "valuation_percentile", "subject": "600000"},
        {"event": "signal", "signal_type": "factor_catalog", "subject": "portfolio"},
        {"event": "decision", "signal_type": "valuation_percentile"},
    ]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    out = mod.load_signals(p, "valuation_percentile")
    assert len(out) == 1 and out[0]["subject"] == "600000"


def test_load_events_missing_file_aborts(tmp_path):
    with pytest.raises(SystemExit):
        mod.load_events(tmp_path / "nope.jsonl")


def test_load_events_bad_json_aborts(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.load_events(p)


# ── 固定视界前向收盘 ─────────────────────────────────────


def test_forward_close_returns_h_th_bar_after_report_date():
    series = _series([("2026-09-16", 10.0), ("2026-09-17", 10.5), ("2026-09-18", 11.0), ("2026-09-21", 12.0)])
    close, n_after = mod.forward_close(series, "2026-09-17", 2)
    assert n_after == 2
    assert close == pytest.approx(12.0)


def test_forward_close_immature_returns_none():
    series = _series([("2026-09-17", 10.5), ("2026-09-18", 11.0)])
    close, n_after = mod.forward_close(series, "2026-09-17", 5)
    assert close is None
    assert n_after == 1  # 报告日当日 bar 不计，仅 1 根后置 bar


def test_forward_close_empty_series():
    assert mod.forward_close(None, "2026-09-17", 5) == (None, 0)


# ── 统计原语 ─────────────────────────────────────────────


def test_spearman_perfect_negative():
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [4.0, 3.0, 2.0, 1.0]
    assert mod.spearman(xs, ys) == pytest.approx(-1.0)


def test_spearman_ties_and_degenerate():
    assert mod.spearman([1.0, 1.0, 1.0], [2.0, 3.0, 4.0]) is None  # 零方差
    assert mod.spearman([1.0, 2.0], [2.0, 1.0]) is None  # 样本 <3


def test_tercile_monotonic_true_and_false():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert mod.tercile_monotonic(xs, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]) is True  # 升
    assert mod.tercile_monotonic(xs, [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]) is True  # 降
    assert mod.tercile_monotonic(xs, [1.0, 6.0, 5.0, 4.0, 2.0, 3.0]) is False  # 非单调（组均值 3.5/4.5/2.5）
    assert mod.tercile_monotonic(xs, [2.0, 2.0, 2.0, 2.0, 2.0, 2.0]) is False  # 组均值无差异不算单调
    assert mod.tercile_monotonic([1.0, 2.0], [1.0, 2.0]) is False  # 样本不足


def test_verdict_discrimination_three_states():
    assert mod.verdict_discrimination(99, 0.2, True)["passed"] is None  # 样本门槛优先
    assert mod.verdict_discrimination(100, 0.08, False)["passed"] is True  # IC 达标
    assert mod.verdict_discrimination(100, None, True)["passed"] is True  # 单调达标
    assert mod.verdict_discrimination(100, 0.02, False)["passed"] is False  # 叙述性维度


def test_verdict_sample_gate():
    assert mod.verdict_sample_gate(99)["credible"] is False
    assert mod.verdict_sample_gate(100)["credible"] is True


# ── 阶段一：命中率聚合（注入行情/指数） ──────────────────


def _fake_price_series(code: str, name: str, days: int):
    # 报告日 2026-09-17 基线 100；之后 60 个交易日线性上涨到 160
    series = [_bar("2026-09-17", 100.0)]
    for i in range(1, 61):
        series.append(_bar(f"2026-09-{18 + i:02d}" if 18 + i <= 30 else f"2026-10-{(18 + i - 30):02d}", 100.0 + i))
    return series


def _fake_index_series(index_code: str, days: int):
    series = [_bar("2026-09-17", 1000.0)]
    for i in range(1, 61):
        series.append(
            _bar(f"2026-09-{18 + i:02d}" if 18 + i <= 30 else f"2026-10-{(18 + i - 30):02d}", 1000.0 + i * 0.5)
        )
    return series


def test_stage_horizon_aggregates_hits(tmp_path):
    rows = [
        {
            "event": "decision",
            "decision_id": "a",
            "direction": 1,
            "baseline_close": 100.0,
            "report_date": "2026-09-17",
            "code": "600000",
            "name": "X",
        },
        {
            "event": "decision",
            "decision_id": "b",
            "direction": -1,
            "baseline_close": 100.0,
            "report_date": "2026-09-17",
            "code": "600000",
            "name": "X",
        },
    ]
    (tmp_path / "decision_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = mod.stage_horizon(
        ledger_dir=tmp_path,
        days=120,
        price_fn=_fake_price_series,
        index_fn=_fake_index_series,
    )
    h5 = result["horizons"]["5"]
    assert h5["n_matured"] == 2
    # 行情 100→105 上涨：做多 hit、做空 miss → 命中率 0.5
    assert h5["hit_rate"] == pytest.approx(0.5)
    assert h5["mean_raw_return"] == pytest.approx(0.05, abs=1e-4)
    # 指数同期 1000→1002.5 → 超额 = 5% − 0.25%
    assert h5["mean_excess"] == pytest.approx(0.0475, abs=1e-4)
    assert h5["by_direction"]["long"]["hit_rate"] == pytest.approx(1.0)
    assert h5["by_direction"]["short"]["hit_rate"] == pytest.approx(0.0)


def test_stage_horizon_unmatured_counts(tmp_path):
    rows = [
        {
            "event": "decision",
            "decision_id": "a",
            "direction": 1,
            "baseline_close": 100.0,
            "report_date": "2099-01-01",
            "code": "600000",
            "name": "X",
        },
    ]
    (tmp_path / "decision_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = mod.stage_horizon(ledger_dir=tmp_path, days=120, price_fn=_fake_price_series, index_fn=_fake_index_series)
    for h in mod.HORIZONS:
        assert result["horizons"][str(h)]["n_matured"] == 0
        assert result["horizons"][str(h)]["n_unmatured"] == 1
        assert result["horizons"][str(h)]["verdict"] == "样本不足，仅记录不裁决"


# ── 阶段二：因子配对收集 ─────────────────────────────────


def test_collect_factor_pairs_skips_missing_forward():
    signals = [
        {"report_date": "2026-09-17", "detail": {"values": {"f_a": 1.5, "f_b": None}}},
        {"report_date": "2099-01-01", "detail": {"values": {"f_a": 2.5}}},
    ]
    fwd = {"2026-09-17": {"5": 0.01, "20": None, "60": 0.02}}
    pairs = mod.collect_factor_pairs(signals, fwd)
    assert set(pairs) == {"f_a"}  # f_b None、无前向收益日期均被剔除
    assert pairs["f_a"]["5"] == [(1.5, 0.01)]
    assert pairs["f_a"]["60"] == [(1.5, 0.02)]
    assert "20" not in pairs["f_a"] or all(v[1] is not None for v in pairs["f_a"].get("20", []))


# ── 阶段三：口径聚合 ─────────────────────────────────────


def _valuation_row(pct_proxy, pct_real, ret5):
    return {
        "subject": "600000",
        "report_date": "2026-09-17",
        "proxy_percentile": pct_proxy,
        "real_percentile": pct_real,
        "forward_returns": {"5": ret5, "20": None, "60": None},
    }


def test_aggregate_valuation_per_caliber():
    # 代理口径 10 条单调（分位升 → 收益降），真实口径仅 2 条（样本不足）
    rows = [_valuation_row(10.0 * (i + 1), None if i % 2 else 50.0, 0.1 - 0.01 * i) for i in range(10)]
    out = mod.aggregate_valuation(rows)
    proxy = out["5"]["proxy"]
    assert proxy["n"] == 10
    assert proxy["ic"] == pytest.approx(-1.0)
    assert proxy["tercile_monotonic"] is True
    assert proxy["passed"] is None  # 10 < 100 → 样本不足，仅记录不裁决
    real = out["5"]["real"]
    assert real["n"] == 5  # 只有非 None 的一半
    assert real["verdict"] == "样本不足，仅记录不裁决"


def test_collect_valuation_rows_same_window_both_calibers():
    series = _series(
        [(f"2026-08-{d:02d}", 10.0 + d * 0.1) for d in range(1, 29)] + [("2026-09-17", 12.0), ("2026-09-18", 12.5)]
    )
    signals = [{"subject": "600000", "report_date": "2026-09-17", "value": 86.96, "name": ""}]
    seen_bars: dict[str, list] = {}

    def fake_proxy(bars, current=None):
        seen_bars["proxy"] = list(bars)
        return {"available": True, "price_percentile": 80.0}

    def fake_real(bars, records, price):
        seen_bars["real"] = list(bars)
        return {"pe_percentile": 60.0, "pb_percentile": None, "reason": None}

    rows = mod.collect_valuation_rows(
        signals,
        days=120,
        price_fn=lambda code, name, days: series,
        fin_fn=lambda code: [{"report_period": "2026-06-30"}],
        proxy_fn=fake_proxy,
        real_fn=fake_real,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["proxy_percentile"] == 80.0
    assert row["real_percentile"] == 60.0
    # 同窗：两口径收到完全相同的 bars（报告日及之前）
    assert seen_bars["proxy"] == seen_bars["real"]
    assert all(str(b.get("date")) <= "2026-09-17" for b in seen_bars["proxy"])
    # 前向收益：12.5 / 12.0 − 1（第 1 个报告日后 bar）
    assert row["forward_returns"]["5"] is None  # 仅 1 根后置 bar，5 日未成熟
    assert row["ledger_percentile"] == 86.96


def test_collect_valuation_rows_no_bars_skipped():
    rows = mod.collect_valuation_rows(
        [{"subject": "000001", "report_date": "2026-09-17", "value": 50.0}],
        days=120,
        price_fn=lambda code, name, days: None,
        fin_fn=lambda code: [],
    )
    assert rows[0]["skipped"] == "no_bars"
    assert rows[0]["proxy_percentile"] is None
    assert rows[0]["real_percentile"] is None


# ── 产物渲染 ─────────────────────────────────────────────


def test_render_markdown_contains_caveats_and_rows(tmp_path):
    rows = [
        {
            "event": "decision",
            "decision_id": "a",
            "direction": 1,
            "baseline_close": 100.0,
            "report_date": "2026-09-17",
            "code": "600000",
            "name": "X",
        },
    ]
    (tmp_path / "decision_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = mod.stage_horizon(ledger_dir=tmp_path, days=120, price_fn=_fake_price_series, index_fn=_fake_index_series)
    md = mod.render_markdown(result)
    assert "已知陷阱" in md
    assert "不得外推" in md
    assert "5 日" in md
