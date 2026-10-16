#!/usr/bin/env python3
"""性能历史趋势查看工具 — Layer 3：跨版本耗时趋势可视化。

读取 data/state/perf_history.jsonl，按版本和报告类型分组统计，
输出版本间性能趋势对比 Markdown 表格；另输出跨版本「总体分位概览」，
给出 P95 / P99 报告生成耗时（最近秩分位：95% 的报告在该耗时内完成，99% 的报告在该耗时内完成）。

用法：
  python scripts/perf-view.py                          # 输出到 stdout
  python scripts/perf-view.py --save                   # 同时写入 docs/tmp/perf_trend.md
  python scripts/perf-view.py --report-type full       # 仅查看 full 类型
  python scripts/perf-view.py --last 30                # 仅查看最近 30 条记录
  python scripts/perf-view.py --exclude-outlier        # 剔除离群运行（稳健口径）
  python scripts/perf-view.py --by day                 # 按时段聚合（day/week/hour）
  python scripts/perf-view.py --compare 0.13.3 0.13.4  # 版本间阶段级对比
  python scripts/perf-view.py --json                   # 机读输出（JSON）
  python scripts/perf-view.py --csv                    # 机读输出（CSV）
  python scripts/perf-view.py --summary                # 仅输出概览段（略去逐版本分组）
  python scripts/perf-view.py --outlier-k 4.0          # 自定义离群判定系数（默认 3.5）

归因能力：版本演进总表、离群点标注（中位 ± MAD）、稳健均值、阶段级分位、尾部归因
（最慢运行逐阶段 z 分数）、异常运行专区（中断/失败）、同版本漂移检测（渐进劣化）、
秒/品种归一化、小样本分位提示、时段聚合、版本间对比、机读输出（记录 + 汇总信封）。

定位说明：本脚本是**运行历史查看**（被动统计既有记录），不是性能测试——
样本取决于最近跑过什么，不可复现，故**不用于 CI 门禁**；性能门禁由主动压测的
`perf-test-report.py` 承担（同条件可比，退化即回归）。
"""

from __future__ import annotations

import argparse
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
    _filter_records,
    _group_records,
    _is_outlier as _is_outlier,  # re-export：经 load_script 供测试直调
    _mad as _mad,  # re-export：同上
    _mean,
    _median,
    _merge_breakdown_stats,
    _merge_phase_stats,
    _min_max,
    _outlier_records,
    _outlier_threshold,
    _per_holding_median,
    _percentile,
    _robust_mean,
    _stdev,
    _total_summary,
    _z_scores,
)

from src.python.core.perf import load_history

_TMP_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_TREND_REPORT_PATH = os.path.join(_TMP_DIR, "perf_trend.md")


# ── 报告生成 ──


def _overview_lines(records: list[dict[str, Any]]) -> list[str]:
    """跨版本总体分位概览（含 P95/P99 报告生成耗时）Markdown 行。"""
    report_types = sorted({str(r.get("report_type", "?")) for r in records})
    rows: list[tuple[str, list[dict[str, Any]]]] = [("合计（当前口径）", records)]
    if len(report_types) > 1:  # 单一类型时与合计行重复，不重复渲染
        rows.extend((rt, [r for r in records if str(r.get("report_type", "?")) == rt]) for rt in report_types)

    lines = [
        "## 总体分位概览（跨版本）",
        "",
        "样本口径与下方分组一致（受 `--report-type` / `--last` 影响）；"
        "分位为**最近秩**口径——P95 即 95% 的报告在该耗时内完成，P99 即 99% 的报告在该耗时内完成。",
        "",
        "| 口径 | 样本数 | 平均 | 中位 | P95 | P99 | 最长 | 中位秒/品种 |",
        "|:-----|------:|----:|----:|----:|----:|-----:|-----------:|",
    ]
    for label, subset in rows:
        stat = _total_summary(subset)
        ph = _per_holding_median(subset)
        lines.append(
            f"| {label} | {int(stat['count'])} | {stat['avg']:.1f}s | {stat['p50']:.1f}s | "
            f"{stat['p95']:.1f}s | {stat['p99']:.1f}s | {stat['max']:.1f}s | {ph if ph is not None else '—'} |"
        )
    if any(len(subset) < 20 for _, subset in rows):
        lines.append("注：样本数 <20 的口径，最近秩 P95/P99 趋近最大值，参考性有限。")
    lines.append("")
    return lines


def _outlier_lines(records: list[dict[str, Any]], k: float = _OUTLIER_K) -> list[str]:
    """离群运行提示段（显式列出而非静默剔除）。"""
    outliers = _outlier_records(records, k)
    if not outliers:
        return []
    threshold = _outlier_threshold([float(r.get("total_seconds") or 0) for r in records], k)
    lines = [
        "## 离群运行（稳健口径）",
        "",
        f"判定：总耗时 > 中位 + {k} × 1.4826 × MAD（上界 {threshold:.1f}s）；"
        "MAD 为 0 时不判离群。用 `--exclude-outlier` 可剔除后重算。",
        "",
        "| 时间 | 版本 | 类型 | 总耗时 | 最慢阶段 | 错误数 |",
        "|:-----|:-----|:-----|------:|:---------|------:|",
    ]
    for r in outliers:
        slowest = _slowest_phase(r) or "?"
        lines.append(
            f"| {r.get('timestamp', '?')[:16]} | {r.get('version', '?')} | {r.get('report_type', '?')} | "
            f"{float(r.get('total_seconds') or 0):.1f}s | {slowest} | {len(r.get('errors') or [])} |"
        )
    lines.append("")
    return lines


def _tail_attribution_lines(records: list[dict[str, Any]]) -> list[str]:
    """尾部归因：最慢那次运行逐阶段 z 分数，直给「哪一步超常、超多少倍」。"""
    if len(records) < 3:
        return []
    slowest = max(records, key=lambda r: float(r.get("total_seconds") or 0))
    slowest_phases = slowest.get("phases") if isinstance(slowest.get("phases"), dict) else {}
    if not slowest_phases:
        return []

    rows: list[tuple[str, float, float, float, float]] = []
    for name, sec in slowest_phases.items():
        # 同阶段历史序列（仅取含该阶段的运行，缺失阶段不参与该阶段基线）
        series = [
            float(r["phases"][name])
            for r in records
            if isinstance(r.get("phases"), dict) and isinstance(r["phases"].get(name), (int, float))
        ]
        if len(series) < 3:
            continue
        zs = _z_scores(series)
        # 本次运行在该序列中的位置：按「含该阶段的运行」顺序对齐
        ordered = [
            r for r in records if isinstance(r.get("phases"), dict) and isinstance(r["phases"].get(name), (int, float))
        ]
        z = zs[ordered.index(slowest)] if slowest in ordered else 0.0
        med = _median(series)
        ratio = (float(sec) / med) if med > 0 else 0.0
        rows.append((name, float(sec), med, z, ratio))

    if not rows:
        return []
    rows.sort(key=lambda row: -row[3])
    lines = [
        "## 尾部归因（最慢一次运行）",
        "",
        f"样本：{slowest.get('timestamp', '?')[:16]} · {slowest.get('version', '?')} · "
        f"总耗时 {float(slowest.get('total_seconds') or 0):.1f}s；z 分数按同阶段历史序列计算。",
        "",
        "| 阶段 | 本次耗时 | 历史中位 | 倍数 | z 分数 |",
        "|:-----|--------:|--------:|-----:|------:|",
    ]
    for name, sec, med, z, ratio in rows:
        lines.append(f"| {name} | {sec:.1f}s | {med:.1f}s | {ratio:.2f}× | {z:+.2f} |")
    lines.append("")
    return lines


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
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[(str(r.get("report_type", "?")), str(r.get("version", "?")))].append(r)
    first_ts = {key: min(str(r.get("timestamp", "")) for r in recs) for key, recs in groups.items()}

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


def _version_evolution_lines(records: list[dict[str, Any]]) -> list[str]:
    """版本演进总表：一眼看出哪个版本开始变慢。"""
    rows = _version_evolution_data(records)
    if not rows:
        return []
    lines = [
        "## 版本演进总表",
        "",
        "同报告类型按版本**首次运行时间**排序；「较上一版」为中位总耗时之差，"
        "|变化| ≥10% 标注 ⚠（变慢/变快）；秒/品种为跨规模归一化口径。",
        "",
        "| 版本 | 报告类型 | 样本数 | 中位 | P95 | 中位秒/品种 | 较上一版中位 |",
        "|:-----|:---------|------:|----:|----:|-----------:|:-----------|",
    ]
    for row in rows:
        ph = f"{row['per_holding']:.3f}" if row["per_holding"] is not None else "—"
        if row["delta_prev"] is None:
            delta_cell = "—"
        else:
            delta_cell = f"{row['delta_prev']:+.1f}s"
            if row["pct_prev"] is not None:
                delta_cell += f"（{row['pct_prev']:+.1f}%）"
                if abs(row["pct_prev"]) >= 10:
                    delta_cell += " ⚠变慢" if row["delta_prev"] > 0 else " ⚠变快"
        lines.append(
            f"| {row['version']} | {row['report_type']} | {row['count']} | "
            f"{row['median']:.1f}s | {row['p95']:.1f}s | {ph} | {delta_cell} |"
        )
    lines.append("")
    return lines


def _is_abnormal_record(record: dict[str, Any]) -> bool:
    """中断 / 非完成状态 / 带错误——三者占其一即异常。"""
    if record.get("interrupted_stage"):
        return True
    if record.get("status") not in (None, "", "completed"):
        return True
    return bool(record.get("errors"))


def _abnormal_lines(records: list[dict[str, Any]]) -> list[str]:
    """异常运行专区：中断/非完成/带错误的运行（无则整段省略）。"""
    bad = [r for r in records if _is_abnormal_record(r)]
    if not bad:
        return []
    lines = [
        "## 异常运行（中断 / 非完成 / 带错误）",
        "",
        "| 时间 | 版本 | 类型 | 状态 | 中断阶段 | 总耗时 | 错误数 | 错误摘要 |",
        "|:-----|:-----|:-----|:-----|:---------|------:|------:|:---------|",
    ]
    for r in bad:
        errs = r.get("errors") or []
        summary = "—"
        if errs:
            summary = str(errs[0])[:40] + (f"（共 {len(errs)} 条）" if len(errs) > 1 else "")
        lines.append(
            f"| {str(r.get('timestamp', '?'))[:16]} | {r.get('version', '?')} | {r.get('report_type', '?')} | "
            f"{r.get('status') or '—'} | {r.get('interrupted_stage') or '—'} | "
            f"{float(r.get('total_seconds') or 0):.1f}s | {len(errs)} | {summary} |"
        )
    lines.append("")
    return lines


def _drift_data(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同版本漂移数据：同（版本, 类型）按时间对半，后半 vs 前半中位差 + 显著性。

    显著性与版本对比同口径：|变化| 超过两半变异系数之和 × 较大中位（噪声带）。
    样本 < `_DRIFT_MIN_SAMPLES` 的组不参与（半样本中位不稳）；输入须按时间升序
    （load_history 追加写入天然有序）。
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[(str(r.get("report_type", "?")), str(r.get("version", "?")))].append(r)
    first_ts = {key: min(str(r.get("timestamp", "")) for r in recs) for key, recs in groups.items()}

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


def _drift_lines(records: list[dict[str, Any]]) -> list[str]:
    """同版本漂移段（渐进劣化检测；无合格组则整段省略）。"""
    rows = _drift_data(records)
    if not rows:
        return []
    lines = [
        "## 同版本漂移（渐进劣化检测）",
        "",
        f"同（版本, 类型）按时间对半，后半 vs 前半中位差；样本 <{_DRIFT_MIN_SAMPLES} 的组不参与。"
        "显著性与版本对比同口径（变化 > 两半变异系数之和 × 较大中位 = 噪声带）。",
        "",
        "| 版本 | 类型 | 样本 | 前半中位 | 后半中位 | 变化 | 显著 |",
        "|:-----|:-----|-----:|--------:|--------:|-----:|:-----|",
    ]
    for row in rows:
        pct_cell = f"（{row['pct']:+.1f}%）" if row["pct"] is not None else ""
        mark = "是" if row["significant"] else "否（噪声带内）"
        lines.append(
            f"| {row['version']} | {row['report_type']} | {row['count']} | "
            f"{row['first_median']:.1f}s | {row['second_median']:.1f}s | {row['delta']:+.1f}s{pct_cell} | {mark} |"
        )
    lines.append("")
    return lines


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


def _bucket_lines(records: list[dict[str, Any]], by: str) -> list[str]:
    """按时段聚合（day/week/hour）：样本数 / 中位 / P95 / 最长。"""
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in records:
        buckets[_bucket_key(r.get("timestamp", ""), by)].append(float(r.get("total_seconds") or 0))
    if not buckets:
        return []
    label = {"day": "日期", "week": "ISO 周", "hour": "小时"}[by]
    lines = [
        f"## 时段聚合（按{label}）",
        "",
        "| 时段 | 样本数 | 中位 | P95 | 最长 |",
        "|:-----|------:|----:|----:|-----:|",
    ]
    for key in sorted(buckets):
        vals = buckets[key]
        lines.append(
            f"| {key} | {len(vals)} | {_median(vals):.1f}s | {_percentile(vals, 95):.1f}s | {_min_max(vals)[1]:.1f}s |"
        )
    lines.append("")
    return lines


def _llm_context_lines(records: list[dict[str, Any]]) -> list[str]:
    """LLM 运行上下文汇总：等待/重试/降级/缓存命中/用量。

    回答「时间花在白等还是真推理」「缓存冷热影响多大」——等待秒数与真实推理
    耗时并列展示，便于判断优化方向。
    """
    with_ctx = [r for r in records if isinstance(r.get("llm"), dict) and r["llm"]]
    if not with_ctx:
        return []

    def _sum(key: str) -> float:
        return sum(float(r["llm"].get(key) or 0) for r in with_ctx)

    retry_wait = _sum("retry_wait_seconds")
    pacing_wait = _sum("pacing_wait_seconds")
    retries = int(_sum("retry_count"))
    fallbacks = int(_sum("fallbacks"))
    hits = int(_sum("cache_hits"))
    misses = int(_sum("cache_misses"))
    cost = _sum("total_cost")

    lines = [
        "## LLM 运行上下文",
        "",
        f"样本：{len(with_ctx)} 条含上下文记录（共 {len(records)} 条）。",
        "",
        "| 指标 | 合计 | 均值/次 |",
        "|:-----|-----:|--------:|",
        f"| 重试次数 | {retries} | {retries / len(with_ctx):.2f} |",
        f"| 重试退避等待 | {retry_wait:.1f}s | {retry_wait / len(with_ctx):.1f}s |",
        f"| 端点节流等待 | {pacing_wait:.1f}s | {pacing_wait / len(with_ctx):.1f}s |",
        f"| provider 降级 | {fallbacks} | {fallbacks / len(with_ctx):.2f} |",
        f"| 缓存命中/未命中 | {hits} / {misses} | — |",
    ]
    if cost:
        lines.append(f"| 累计费用 | {cost:.4f} | {cost / len(with_ctx):.4f} |")
    lines.append("")

    providers: dict[str, int] = defaultdict(int)
    models: dict[str, int] = defaultdict(int)
    for r in with_ctx:
        for name, n in (r["llm"].get("providers") or {}).items():
            providers[name] += int(n)
        for name, n in (r["llm"].get("models") or {}).items():
            models[name] += int(n)
    if providers or models:
        lines.append("| 维度 | 取值（调用次数） |")
        lines.append("|:-----|:-----------------|")
        if providers:
            lines.append("| provider | " + "、".join(f"{k}×{v}" for k, v in sorted(providers.items())) + " |")
        if models:
            lines.append("| 模型 | " + "、".join(f"{k}×{v}" for k, v in sorted(models.items())) + " |")
        lines.append("")
    return lines


def _version_records(records: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    """取指定版本的记录（版本号精确匹配）。"""
    return [r for r in records if str(r.get("version", "")) == version]


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

    def _summary(recs: list[dict[str, Any]]) -> dict[str, Any]:
        totals = [float(r.get("total_seconds") or 0) for r in recs]
        return {
            "version": version_a if recs is recs_a else version_b,
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
    return {"a": _summary(recs_a), "b": _summary(recs_b), "phases": rows}


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


def _compare_lines(records: list[dict[str, Any]], version_a: str, version_b: str) -> list[str]:
    """版本间对比 Markdown 段。"""
    cmp = _compare_versions(records, version_a, version_b)
    lines = [
        f"## 版本对比：{version_a} → {version_b}",
        "",
        "| 版本 | 样本数 | 中位总耗时 | P95 | 中位秒/品种 | 变异系数 |",
        "|:-----|------:|----------:|----:|-----------:|--------:|",
    ]
    for key in ("a", "b"):
        s = cmp[key]
        ph = f"{s['per_holding']:.3f}" if s["per_holding"] is not None else "—"
        lines.append(f"| {s['version']} | {s['count']} | {s['median']:.1f}s | {s['p95']:.1f}s | {ph} | {s['cv']:.3f} |")
    lines.append("")
    if not cmp["phases"]:
        lines.append("_两版本均无阶段样本。_")
        lines.append("")
        return lines
    lines.append("| 阶段 | 旧版中位 | 新版中位 | 变化 | 倍数 | 显著 |")
    lines.append("|:-----|--------:|--------:|-----:|-----:|:-----|")
    for row in cmp["phases"]:
        mark = "是" if row["significant"] else "否（噪声带内）"
        lines.append(
            f"| {row['name']} | {row['a_median']:.2f}s | {row['b_median']:.2f}s | "
            f"{row['delta']:+.2f}s | {row['ratio']:.2f}× | {mark} |"
        )
    lines.append("")
    lines.append("显著性口径：变化幅度需超过两版本各自变异系数之和 × 较大中位值（噪声带）。")
    lines.append("")
    return lines


def _machine_summary(records: list[dict[str, Any]], outlier_k: float = _OUTLIER_K) -> dict[str, Any]:
    """机读汇总：与 Markdown 段同源的分位/离群/异常/演进/漂移统计。"""
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_type[str(r.get("report_type", "?"))].append(r)
    return {
        "total_seconds": _total_summary(records),
        "per_holding_median": _per_holding_median(records),
        "by_report_type": {rt: _total_summary(sub) for rt, sub in sorted(by_type.items())},
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


def _machine_readable(records: list[dict[str, Any]], fmt: str, outlier_k: float = _OUTLIER_K) -> str:
    """机读输出：JSON 信封（记录 + 汇总统计）或 CSV（含归一/离群/最慢阶段列）。"""
    if fmt == "json":
        payload = {
            "record_count": len(records),
            "records": records,
            "summary": _machine_summary(records, outlier_k),
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


def build_trend_report(
    records: list[dict[str, Any]],
    report_type: str | None = None,
    last_n: int | None = None,
    exclude_outlier: bool = False,
    by: str | None = None,
    compare: tuple[str, str] | None = None,
    summary: bool = False,
    outlier_k: float = _OUTLIER_K,
) -> str:
    """生成性能趋势 Markdown 报告字符串。

    ``summary``：仅输出概览段（总体分位/离群/尾部归因/LLM 上下文/时段聚合/对比），
    略去逐版本分组详情——记录多、分组多时避免输出过长。
    """
    groups = _group_records(records, report_type, last_n, exclude_outlier, outlier_k)
    scoped = _filter_records(records, report_type, last_n, exclude_outlier, outlier_k)

    lines: list[str] = [
        "# 报告生成性能趋势",
        "",
        "**数据来源**：`data/state/perf_history.jsonl`",
        f"**总记录数**：{len(records)} 条",
        f"**分组数**：{len(groups)} 组",
        "",
    ]

    if not groups:
        lines.append("_暂无性能历史数据。_")
        lines.append("")
        return "\n".join(lines)

    # ── 跨版本分位概览（P95/P99 报告生成耗时） ──
    lines.extend(_overview_lines(scoped))

    # ── 版本演进总表（哪一版开始变慢） ──
    lines.extend(_version_evolution_lines(scoped))

    # ── 离群运行与尾部归因（稳健口径） ──
    lines.extend(_outlier_lines(scoped, outlier_k))
    lines.extend(_tail_attribution_lines(scoped))

    # ── 异常运行与同版本渐进漂移 ──
    lines.extend(_abnormal_lines(scoped))
    lines.extend(_drift_lines(scoped))

    # ── LLM 运行上下文（等待/重试/降级/缓存/用量） ──
    lines.extend(_llm_context_lines(scoped))

    # ── 时段聚合（可选） ──
    if by:
        lines.extend(_bucket_lines(scoped, by))

    # ── 版本间对比（可选） ──
    if compare:
        lines.extend(_compare_lines(records, compare[0], compare[1]))

    # ── 概览模式：略去逐版本分组详情 ──
    if summary:
        lines.append("_（概览模式：已略去逐版本分组详情，去掉 `--summary` 可查看）_")
        lines.append("")
        return "\n".join(lines)

    # ── 按组输出详情 ──
    for group_key, group_records in groups.items():
        lines.append(f"## {group_key}")
        lines.append("")
        lines.append(f"运行次数：**{len(group_records)}**")
        lines.append("")

        totals = [r.get("total_seconds", 0) for r in group_records]
        lines.append(f"- 总耗时范围：{_min_max(totals)[0]:.1f}s ~ {_min_max(totals)[1]:.1f}s")
        # 稳健均值仅在存在离群点时并列展示（无离群时与普通均值相同，并列属冗余）
        if _outlier_records(group_records, outlier_k):
            lines.append(f"- 平均总耗时：**{_mean(totals):.1f}s**（稳健均值 {_robust_mean(totals, outlier_k):.1f}s）")
        else:
            lines.append(f"- 平均总耗时：**{_mean(totals):.1f}s**")
        lines.append(
            f"- 95% 的报告在 **{_percentile(totals, 95):.1f}s** 内完成，"
            f"99% 的报告在 **{_percentile(totals, 99):.1f}s** 内完成"
        )
        if len(group_records) < 20:
            lines.append("_（样本 <20：最近秩分位趋近最大值，参考性有限）_")
        lines.append("")

        # ── 各阶段耗时（含阶段级分位） ──
        phase_stats = _merge_phase_stats(group_records)
        if phase_stats:
            lines.append("| 阶段 | 平均耗时 | 中位 | P95 | 最短 | 最长 | 次数 |")
            lines.append("|:-----|--------:|----:|----:|----:|----:|-----:|")
            for name, stat in phase_stats.items():
                lines.append(
                    f"| {name} | {stat['avg']:.2f}s | {stat['p50']:.2f}s | {stat['p95']:.2f}s | "
                    f"{stat['min']:.2f}s | {stat['max']:.2f}s | {stat['count']} |"
                )
            lines.append("")

        # ── 阶段细分（breakdown：子项自身耗时，可并行，之和不等于父阶段墙钟） ──
        breakdown_stats = _merge_breakdown_stats(group_records)
        if breakdown_stats:
            lines.append("**阶段细分**（子项自身耗时；父阶段内子项可并行，之和不等于父阶段耗时）：")
            lines.append("")
            lines.append("| 父阶段 | 子项 | 平均耗时 | 最长 | 次数 |")
            lines.append("|:-----|:-----|--------:|----:|-----:|")
            for parent, spans in breakdown_stats.items():
                for name, stat in spans.items():
                    lines.append(f"| {parent} | {name} | {stat['avg']:.2f}s | {stat['max']:.2f}s | {stat['count']} |")
            lines.append("")

        # ── 最近 5 次运行明细 ──
        lines.append("**最近 5 次运行明细：**")
        lines.append("")
        lines.append("| 时间 | 总耗时 | 持仓数 | 阶段数 | 错误 |")
        lines.append("|:-----|------:|------:|------:|-----:|")
        for r in group_records[-5:]:
            ts = r.get("timestamp", "?")[:16]  # 日期+时:分（去秒）
            lines.append(
                f"| {ts} | {r.get('total_seconds', 0):.1f}s | "
                f"{r.get('holdings_count', '?')} | "
                f"{len(r.get('phases', {}))} | "
                f"{len(r.get('errors', []))} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    return "\n".join(lines)


# ── CLI ──


def main() -> int:
    parser = argparse.ArgumentParser(description="查看性能历史趋势")
    parser.add_argument("--report-type", choices=["basic", "both", "full"], help="仅查看指定报告类型")
    parser.add_argument("--last", type=int, default=None, help="仅查看最近 N 条记录")
    parser.add_argument("--save", action="store_true", help="同时写入 docs/tmp/perf_trend.md")
    parser.add_argument(
        "--exclude-outlier",
        action="store_true",
        help="剔除离群运行（中位 ± MAD 稳健口径）后统计",
    )
    parser.add_argument("--by", choices=["day", "week", "hour"], help="按时段聚合（日/ISO 周/小时）")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("旧版本", "新版本"),
        help="版本间阶段级对比（带变异系数判显著）",
    )
    parser.add_argument("--json", action="store_true", help="机读输出：完整记录 JSON")
    parser.add_argument("--csv", action="store_true", help="机读输出：逐运行 CSV")
    parser.add_argument("--summary", action="store_true", help="仅输出概览段（略去逐版本分组详情）")
    parser.add_argument(
        "--outlier-k",
        type=float,
        default=_OUTLIER_K,
        metavar="系数",
        help=f"离群判定系数（中位 + k × 1.4826 × MAD，默认 {_OUTLIER_K}）",
    )
    args = parser.parse_args()

    records = load_history()
    if not records:
        print("[!] 暂无性能历史数据（data/state/perf_history.jsonl 不存在或为空）")
        return 1

    scoped = _filter_records(records, args.report_type, args.last, args.exclude_outlier, args.outlier_k)

    # ── 机读输出（与 Markdown 互斥，便于管道消费） ──
    if args.json or args.csv:
        if args.save:
            print("[!] --save 在机读模式下不适用（--json/--csv 只向 stdout 输出）", file=sys.stderr)
        print(_machine_readable(scoped, "json" if args.json else "csv", args.outlier_k))
    else:
        report = build_trend_report(
            records,
            report_type=args.report_type,
            last_n=args.last,
            exclude_outlier=args.exclude_outlier,
            by=args.by,
            compare=tuple(args.compare) if args.compare else None,
            summary=args.summary,
            outlier_k=args.outlier_k,
        )
        print(report)

        if args.save:
            os.makedirs(_TMP_DIR, exist_ok=True)
            with open(_TREND_REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"[OK] 已写入: {_TREND_REPORT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
