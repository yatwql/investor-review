"""因子动物园评测阶段5（判定书）与温度/尾部风险族序列分支测试（网络无关）。

覆盖：`report.stage_verdict` 的报告齐备闸门与落盘链路、`_write_verdict_md` 的
A 逐因子表 / B 未评估与已评估两态 / C 耗时口径行；`metrics.build_family_series`
的温度族与尾部风险族分支。阈值边界与异常分支见 test_eval_factor_zoo_edge.py。
"""

from __future__ import annotations

from datetime import date, timedelta

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
    start = date(2025, 1, 1)
    out = []
    for i in range(count):
        close = 100.0 + 10.0 * ((i % 17) - 8) / 8.0 + i * 0.05
        out.append({"date": (start + timedelta(days=i)).isoformat(), "close": close, "total_value": close})
    return out


# ── 温度 / 尾部风险族分支 ──────────────────────────────────────


def test_build_family_series_market_temperature_branch(zoo):
    from _eval_factor_zoo import catalog, metrics

    bars = _index_bars(160)
    series = metrics.build_family_series(catalog.FAMILY_MARKET_TEMPERATURE, bars)

    assert set(series) <= {b["date"] for b in bars}, "序列键必须是 bar 日期"
    assert all(0.0 <= v <= 100.0 for v in series.values()), "温度分落在 0~100"


def test_build_family_series_tail_risk_branch(zoo):
    from _eval_factor_zoo import catalog, metrics

    bars = _index_bars(120)
    series = metrics.build_family_series(catalog.FAMILY_TAIL_VAR, bars)

    assert set(series) <= {b["date"] for b in bars}
    assert all(isinstance(v, float) for v in series.values())


# ── 判定书阶段 ────────────────────────────────────────────────


def _verdict() -> dict:
    return {
        "verdict": "不通过",
        "approved": False,
        "failed": ["A 字段可得率"],
        "metrics": {"A": 0.5, "B": 0.0, "C": 0.9},
        "captured_at": "2026-01-01T00:00:00",
    }


def _fields_report() -> dict:
    return {
        "n_computable": 1,
        "total": 2,
        "ratio": 0.5,
        "pass": False,
        "pool_size": 3,
        "timings": {"bars": 1.5},
        "per_factor": {
            "fund_roe": {
                "ok": True,
                "missing": [],
                "fields": {"fin": {"coverage": 1.0}},
            },
            "fund_revenue_yoy": {
                "ok": False,
                "missing": ["fin"],
                "fields": {"fin": {"coverage": 0.0}, "bars": {"coverage": 0.5}},
            },
        },
    }


def test_stage_verdict_requires_all_three_reports(zoo, tmp_path):
    from _eval_factor_zoo import report

    (tmp_path / "fields_report.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="指标报告不齐"):
        report.stage_verdict(tmp_path)


def test_stage_verdict_writes_json_and_markdown(zoo, tmp_path, monkeypatch):
    from _eval_factor_zoo import report, stages

    stages._write_json(tmp_path / "fields_report.json", _fields_report())
    stages._write_json(tmp_path / "signals_report.json", {"skipped": True})
    stages._write_json(tmp_path / "timing_report.json", {"cold_seconds": 3.0, "pass": True})
    monkeypatch.setattr(report, "judge", lambda *_a, **_k: _verdict())

    verdict = report.stage_verdict(tmp_path)

    assert verdict["captured_at"] != "2026-01-01T00:00:00", "阶段须自行写入生成时间"
    saved = stages._read_json(tmp_path / "verdict.json")
    assert saved["verdict"] == verdict["verdict"]
    assert saved["metrics"] == verdict["metrics"]
    md = (tmp_path / "verdict.md").read_text(encoding="utf-8")
    assert "# 因子动物园目录评测判定书" in md
    assert "## 预注册口径" in md
    assert "`fund_revenue_yoy`" in md  # A 逐因子表逐行渲染
    assert "未评估（指标 A 未过" in md  # B 的 skipped 分支
    assert "## 指标 C：耗时预算" in md


def test_write_verdict_md_renders_evaluated_signals(zoo, tmp_path):
    from _eval_factor_zoo import report

    b = {
        "n_low_corr": 2,
        "denom": 5,
        "ratio": 0.4,
        "pass": True,
        "sample_ok": True,
        "family_series_sizes": {"market_temperature": 40},
        "family_degraded": {"rebalance_overflow": "快照域"},
        "per_factor": {
            "fund_roe": {
                "max_abs_rho": 0.12,
                "closest_family": "market_temperature",
                "low_corr": True,
                "step_signal": False,
            },
        },
    }
    c = {
        "cold_seconds": 12.0,
        "warm_seconds": 8.0,
        "baseline_seconds": 30.0,
        "ratio": 0.4,
        "pass": True,
        "cold_basis": "池外样本实测",
        "estimated_requests": 42,
        "warm_probe_total_seconds": 8.0,
        "timings_by_field": {"bars": 3.0},
        "baseline": {"samples": [29.0, 30.0], "compute_only_median_seconds": 4.0},
    }

    report._write_verdict_md(tmp_path, _verdict(), _fields_report(), b, c)

    md = (tmp_path / "verdict.md").read_text(encoding="utf-8")
    assert "`fund_roe` | 0.12" in md
    assert "样本门槛" in md
    assert "非 LLM 计算阶段中位数 4.0s" in md
    assert "降级信号族" in md
