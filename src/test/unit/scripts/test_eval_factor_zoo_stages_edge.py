"""`_eval_factor_zoo.stages` 阶段编排的边缘场景（缺产物 / 校验不过 / 采集异常）。

阶段编排的失败模式集中在「前置阶段产物缺失」与「性能采集整体异常」两类：
前者必须**中止**（缺产物继续跑会产出误导性指标），后者必须**继续**（性能评测
不该因一次探针崩掉整个评测）。本文件只覆盖这两类分支，正常路径见
`test_eval_factor_zoo_stages.py`。
"""

from __future__ import annotations

import json

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.edge,
]


@pytest.fixture(scope="module")
def zoo():
    return load_script("eval-factor-zoo.py")


@pytest.fixture
def stages_mod(zoo):
    from _eval_factor_zoo import stages

    return stages


def _write(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ── 目录阶段：冻结校验不过必须中止 ───────────────────────────


def test_stage_catalog_aborts_when_validation_reports_problems(stages_mod, tmp_path, monkeypatch):
    """目录校验有问题时抛 SystemExit（不允许带着坏目录继续评测）。"""
    monkeypatch.setattr(stages_mod, "validate_catalog", lambda _catalog: ["slug 重复"])

    with pytest.raises(SystemExit):
        stages_mod.stage_catalog(tmp_path)
    assert not (tmp_path / "factor_catalog.json").exists()


# ── 字段阶段：缺前段目录 → 中止 ──────────────────────────────


def test_stage_fields_aborts_without_catalog(stages_mod, tmp_path):
    """无 factor_catalog.json 时提示先跑 catalog 阶段并中止。"""
    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_fields(tmp_path)

    assert "catalog" in str(exc.value)
    assert not (tmp_path / "stock_pool.json").exists()


# ── 信号阶段：前置产物缺失 / 形状不对 → 中止 ─────────────────


def test_stage_signals_aborts_without_fields_report(stages_mod, tmp_path):
    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_signals(tmp_path)

    assert "fields" in str(exc.value)


def test_stage_signals_aborts_without_probe_cache(stages_mod, tmp_path):
    """指标 A 通过却没有探测原始数据 → 中止（否则会算出「全因子不可评估」的假结论）。"""
    _write(tmp_path / "fields_report.json", {"pass": True, "computable": [], "total": 0})

    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_signals(tmp_path)

    assert "probe_cache" in str(exc.value)


def test_stage_signals_aborts_when_catalog_shape_broken(stages_mod, tmp_path):
    """factor_catalog.json 的 catalog 不是列表 → 中止并点名文件。"""
    _write(tmp_path / "fields_report.json", {"pass": True, "computable": ["fund_pb"], "total": 1})
    _write(tmp_path / "probe_cache.json", {"bars_by_code": {}, "index_bars": []})
    _write(tmp_path / "factor_catalog.json", {"catalog": {"fund_pb": {}}})

    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_signals(tmp_path)

    assert "factor_catalog" in str(exc.value)


# ── 耗时阶段：前置产物缺失 → 中止；采集异常 → 继续 ───────────


def test_stage_timing_aborts_without_fields_report(stages_mod, tmp_path):
    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_timing(tmp_path)

    assert "fields_report" in str(exc.value)


def test_stage_timing_aborts_without_signals_report(stages_mod, tmp_path):
    _write(tmp_path / "fields_report.json", {"pass": True, "pool_size": 3})

    with pytest.raises(SystemExit) as exc:
        stages_mod.stage_timing(tmp_path)

    assert "signals_report" in str(exc.value)


def test_stage_timing_records_cold_sample_failure_and_continues(stages_mod, tmp_path, monkeypatch):
    """冷样本采集整体抛异常 → 记入 cold_sample.error、指标 C 判不可判定，而不是中断评测。"""
    _write(tmp_path / "fields_report.json", {"pass": True, "pool_size": 2, "probe_total_seconds": 1.5})
    _write(tmp_path / "signals_report.json", {"skipped": False, "compute_seconds": 0.5})

    def _boom():
        raise RuntimeError("缓存目录不可读")

    monkeypatch.setattr(stages_mod, "measure_cold_sample", _boom)
    monkeypatch.setattr(
        stages_mod,
        "read_report_baseline",
        lambda _path=None: {"available": True, "n": 1, "median_seconds": 60.0},
    )

    report = stages_mod.stage_timing(tmp_path)

    assert "ratio" not in report
    assert report["pass"] is False
    assert "缓存目录不可读" in report["cold_sample"]["error"]
    assert report["cold_sample"]["mean_cold_request_seconds"] is None
    assert report["estimated_requests"] == 2 * 3 + 1
    assert stages_mod._read_json(tmp_path / "timing_report.json") == report
