"""perf-view 数据派生：从 perf_history 记录算出版本演进 / 漂移 / 对比 / 机读信封。

纯数据层（不拼 Markdown 文本）——渲染见 :mod:`_perf_view.report`，统计原语见
:mod:`_perf_view.stats`，CLI 见 :mod:`_perf_view.cli`。
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _perf_view.stats import (
    _DRIFT_MIN_SAMPLES,
    _OUTLIER_K,
    _cv,
    _group_by_version_type,
    _group_records as _group_records,  # re-export：经 load_script 供测试直调
    _is_outlier as _is_outlier,  # re-export：经 load_script 供测试直调
    _mad as _mad,  # re-export：同上
    _mean,
    _median,
    _merge_phase_stats,
    _min_max,
    _outlier_records,
    _per_holding_median,
    _percentile,
    _stdev,
    _total_summary,
)


_TMP_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_TREND_REPORT_PATH = os.path.join(_TMP_DIR, "perf_trend.md")


def _slowest_phase(record: dict[str, Any]) -> str:
    """记录中最慢阶段名（无阶段数据返回空串）。"""
    phases = record.get("phases") if isinstance(record.get("phases"), dict) else {}
    if not phases:
        return ""
    return max(phases.items(), key=lambda kv: kv[1])[0]


def _version_evolution_data(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """版本演进数据：每（版本, 报告类型）一行，按该版本首次运行时间排序。

    Returns:
        [{report_type, version, count, median, p95, per_holding, delta_prev, pct_prev}]
        （同类型首版的 delta_prev/pct_prev 为 None）。
    """
    groups, first_ts = _group_by_version_type(records)

    rows: list[dict[str, Any]] = []
    for rt in sorted({key[0] for key in groups}):
        versions = sorted((key[1] for key in groups if key[0] == rt), key=lambda v: first_ts[(rt, v)])
        prev_median: float | None = None
        for ver in versions:
            recs = groups[(rt, ver)]
            totals = [float(r.get("total_seconds") or 0) for r in recs]
            median = round(_median(totals), 1)
            delta: float | None = None
            pct: float | None = None
            if prev_median is not None:
                delta = round(median - prev_median, 1)
                pct = round((median - prev_median) / prev_median * 100, 1) if prev_median > 0 else None
            rows.append(
                {
                    "report_type": rt,
                    "version": ver,
                    "count": len(recs),
                    "median": median,
                    "p95": round(_percentile(totals, 95), 1),
                    "per_holding": _per_holding_median(recs),
                    "delta_prev": delta,
                    "pct_prev": pct,
                }
            )
            prev_median = median
    return rows


def _is_abnormal_record(record: dict[str, Any]) -> bool:
    """中断 / 非完成状态 / 带错误——三者占其一即异常。"""
    if record.get("interrupted_stage"):
        return True
    if record.get("status") not in (None, "", "completed"):
        return True
    return bool(record.get("errors"))


def _drift_data(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同版本漂移数据：同（版本, 类型）按时间对半，后半 vs 前半中位差 + 显著性。

    显著性与版本对比同口径：|变化| 超过两半变异系数之和 × 较大中位（噪声带）。
    样本 < `_DRIFT_MIN_SAMPLES` 的组不参与（半样本中位不稳）；输入须按时间升序
    （load_history 追加写入天然有序）。
    """
    groups, first_ts = _group_by_version_type(records)

    rows: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda k: (first_ts[k], k)):
        recs = groups[key]
        if len(recs) < _DRIFT_MIN_SAMPLES:
            continue
        half = len(recs) // 2
        first, second = recs[:half], recs[-half:]
        first_totals = [float(r.get("total_seconds") or 0) for r in first]
        second_totals = [float(r.get("total_seconds") or 0) for r in second]
        first_med = round(_median(first_totals), 1)
        second_med = round(_median(second_totals), 1)
        delta = round(second_med - first_med, 1)
        pct = round((second_med - first_med) / first_med * 100, 1) if first_med > 0 else None
        noise = (_cv(first_totals) + _cv(second_totals)) * max(first_med, second_med)
        rows.append(
            {
                "report_type": key[0],
                "version": key[1],
                "count": len(recs),
                "first_median": first_med,
                "second_median": second_med,
                "delta": delta,
                "pct": pct,
                "significant": bool(abs(delta) > noise),
            }
        )
    return rows


def _bucket_key(timestamp: str, by: str) -> str:
    """时间戳 → 时段键（day=日期 / week=ISO 周 / hour=小时）。"""
    ts = str(timestamp or "")
    if by == "hour":
        return ts[11:13] or "?"
    if by == "week":
        try:
            year, week, _ = datetime.fromisoformat(ts).isocalendar()
            return f"{year}-W{week:02d}"
        except ValueError:
            return "?"
    return ts[:10] or "?"


def _version_records(records: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    """取指定版本的记录（版本号精确匹配）。"""
    return [r for r in records if str(r.get("version", "")) == version]


def _cv_of_phase(records: list[dict[str, Any]], phase: str) -> float:
    """某阶段在该版本内的变异系数（噪声带）；样本不足或均值为 0 时返回 0。"""
    vals = [
        float(r["phases"][phase])
        for r in records
        if isinstance(r.get("phases"), dict) and isinstance(r["phases"].get(phase), (int, float))
    ]
    if len(vals) < 2:
        return 0.0
    return _cv(vals)


def _compare_versions(
    records: list[dict[str, Any]],
    version_a: str,
    version_b: str,
) -> dict[str, Any]:
    """版本间阶段级对比（含变异系数判显著）。

    显著性口径：两版本各自阶段耗时的**变异系数**（标准差/均值）作为噪声带——
    差异幅度超过两版本噪声带之和才判「显著」，避免把运行抖动当回归。

    Returns:
        {"a": {...}, "b": {...}, "phases": [{name, a_median, b_median, delta, ratio, significant}]}
    """
    recs_a = _version_records(records, version_a)
    recs_b = _version_records(records, version_b)

    def _summary(recs: list[dict[str, Any]], version: str) -> dict[str, Any]:
        totals = [float(r.get("total_seconds") or 0) for r in recs]
        return {
            "version": version,
            "count": len(recs),
            "median": round(_median(totals), 1),
            "p95": round(_percentile(totals, 95), 1),
            "cv": round(_stdev(totals) / _mean(totals), 3) if totals and _mean(totals) > 0 else 0.0,
            "per_holding": _per_holding_median(recs),
        }

    stats_a = _merge_phase_stats(recs_a)
    stats_b = _merge_phase_stats(recs_b)
    rows: list[dict[str, Any]] = []
    for name in sorted(set(stats_a) | set(stats_b)):
        a_med = stats_a.get(name, {}).get("p50", 0.0)
        b_med = stats_b.get(name, {}).get("p50", 0.0)
        a_cv = _cv_of_phase(recs_a, name)
        b_cv = _cv_of_phase(recs_b, name)
        delta = b_med - a_med
        ratio = (b_med / a_med) if a_med > 0 else 0.0
        noise = (a_cv + b_cv) * max(a_med, b_med)
        rows.append(
            {
                "name": name,
                "a_median": round(a_med, 2),
                "b_median": round(b_med, 2),
                "delta": round(delta, 2),
                "ratio": round(ratio, 3),
                "significant": abs(delta) > noise,
            }
        )
    rows.sort(key=lambda row: -abs(row["delta"]))
    return {"a": _summary(recs_a, version_a), "b": _summary(recs_b, version_b), "phases": rows}


def _llm_cost_data(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """机读费用汇总：含 llm 记录数与费用合计/均值/中位/单次最高（无样本 → None）。

    费用字段与 Markdown LLM 段的「累计费用」同源（``llm.total_cost``），
    统计用既有均值/中位/极值 helper（中位稳健抗单次异常）。
    """
    costs = [float(r["llm"].get("total_cost") or 0) for r in records if isinstance(r.get("llm"), dict) and r["llm"]]
    if not costs:
        return None
    return {
        "runs": len(costs),
        "total": round(sum(costs), 6),
        "mean": round(_mean(costs), 6),
        "median": round(_median(costs), 6),
        "max": round(_min_max(costs)[1], 6),
    }


def _cost_period_data(records: list[dict[str, Any]], by: str) -> list[dict[str, Any]]:
    """按 ``--by`` 时段的费用序列（机读）：``[{bucket, runs, total_cost}]``（时段键升序）。

    runs 为时段内全部记录数，total_cost 仅累加含 ``llm.total_cost`` 的记录；
    时段键升序即时间序，消费方可直接做相邻差分。
    """
    runs: dict[str, int] = defaultdict(int)
    costs: dict[str, float] = defaultdict(float)
    for r in records:
        key = _bucket_key(r.get("timestamp", ""), by)
        runs[key] += 1
        llm = r.get("llm")
        if isinstance(llm, dict):
            costs[key] += float(llm.get("total_cost") or 0)
    return [{"bucket": key, "runs": runs[key], "total_cost": round(costs.get(key, 0.0), 6)} for key in sorted(runs)]


def _machine_summary(
    records: list[dict[str, Any]],
    outlier_k: float = _OUTLIER_K,
    by: str | None = None,
) -> dict[str, Any]:
    """机读汇总：与 Markdown 段同源的分位/离群/异常/演进/漂移统计 + 费用字段。

    ``llm_cost`` 恒为键（无费用样本为 null）；``by`` 给定时附 ``by_period``
    时段费用序列，否则为 null。
    """
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_type[str(r.get("report_type", "?"))].append(r)
    return {
        "total_seconds": _total_summary(records),
        "per_holding_median": _per_holding_median(records),
        "by_report_type": {rt: _total_summary(sub) for rt, sub in sorted(by_type.items())},
        "llm_cost": _llm_cost_data(records),
        "by_period": _cost_period_data(records, by) if by else None,
        "outliers": [
            {
                "timestamp": r.get("timestamp", ""),
                "version": r.get("version", ""),
                "report_type": r.get("report_type", ""),
                "total_seconds": float(r.get("total_seconds") or 0),
                "slowest_phase": _slowest_phase(r),
                "errors_count": len(r.get("errors") or []),
            }
            for r in _outlier_records(records, outlier_k)
        ],
        "abnormal": [
            {
                "timestamp": r.get("timestamp", ""),
                "version": r.get("version", ""),
                "report_type": r.get("report_type", ""),
                "status": r.get("status"),
                "interrupted_stage": r.get("interrupted_stage"),
                "errors_count": len(r.get("errors") or []),
                "total_seconds": float(r.get("total_seconds") or 0),
            }
            for r in records
            if _is_abnormal_record(r)
        ],
        "version_evolution": _version_evolution_data(records),
        "drift": _drift_data(records),
    }


def _machine_readable(
    records: list[dict[str, Any]],
    fmt: str,
    outlier_k: float = _OUTLIER_K,
    by: str | None = None,
) -> str:
    """机读输出：JSON 信封（记录 + 汇总统计含费用字段）或 CSV（含归一/离群/最慢阶段列）。

    ``by`` 透传给汇总的 ``by_period`` 时段费用序列（仅 JSON；CSV 列不变）。
    """
    if fmt == "json":
        payload = {
            "record_count": len(records),
            "records": records,
            "summary": _machine_summary(records, outlier_k, by),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "timestamp",
            "version",
            "report_type",
            "holdings_count",
            "total_seconds",
            "status",
            "per_holding_seconds",
            "outlier",
            "slowest_phase",
            "interrupted_stage",
            "errors_count",
        ]
    )
    outlier_ids = {id(r) for r in _outlier_records(records, outlier_k)}
    for r in records:
        holdings = int(r.get("holdings_count") or 0)
        total = float(r.get("total_seconds") or 0)
        writer.writerow(
            [
                r.get("timestamp", ""),
                r.get("version", ""),
                r.get("report_type", ""),
                r.get("holdings_count", ""),
                r.get("total_seconds", 0),
                r.get("status", ""),
                f"{total / holdings:.3f}" if holdings > 0 else "",
                "1" if id(r) in outlier_ids else "0",
                _slowest_phase(r),
                r.get("interrupted_stage") or "",
                len(r.get("errors") or []),
            ]
        )
    return buf.getvalue()
