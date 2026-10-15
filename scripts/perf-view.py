#!/usr/bin/env python3
"""性能历史趋势查看工具 — Layer 3：跨版本耗时趋势可视化。

读取 data/state/perf_history.jsonl，按版本和报告类型分组统计，
输出版本间性能趋势对比 Markdown 表格；另输出跨版本「总体分位概览」，
给出 P95 / P99 报告生成耗时（最近秩分位：95% / 99% 的报告在该时间内完成）。

用法：
  python scripts/perf-view.py                          # 输出到 stdout
  python scripts/perf-view.py --save                   # 同时写入 docs/tmp/perf_trend.md
  python scripts/perf-view.py --report-type full       # 仅查看 full 类型
  python scripts/perf-view.py --last 30                # 仅查看最近 30 条记录
  python scripts/perf-view.py --exclude-outlier        # 剔除离群运行（稳健口径）
  python scripts/perf-view.py --by day                 # 按时段聚合（day/week/hour）

归因能力：离群点标注（中位 ± MAD）、稳健均值、阶段级分位、尾部归因（最慢运行
逐阶段 z 分数）、时段聚合。
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

from src.python.core.perf import load_history

_TMP_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_TREND_REPORT_PATH = os.path.join(_TMP_DIR, "perf_trend.md")


# ── 统计工具 ──


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _min_max(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def _percentile(values: list[float], pct: float) -> float:
    """最近秩（nearest-rank）分位数：`ceil(pct% × n)` 位样本值。

    口径含义：至少 `pct%` 的样本 ≤ 返回值——P95 即「95% 的报告生成在该耗时内完成」，
    P99 即「99% 的报告生成在该耗时内完成」。空输入返回 0.0。

    Args:
        values: 样本值（任意顺序，内部排序）。
        pct: 百分位（0~100）。

    Returns:
        分位值；空输入为 0.0。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    rank = min(max(rank, 1), len(ordered))
    return ordered[rank - 1]


def _median(values: list[float]) -> float:
    """中位数（空输入 0.0）。"""
    if not values:
        return 0.0
    return statistics.median(values)


def _mad(values: list[float]) -> float:
    """中位绝对偏差（MAD）：`median(|x - median(x)|)`。

    比标准差更耐离群点——单条 6636s 异常几乎不影响 MAD，故用它做离群判定基准。
    """
    if not values:
        return 0.0
    med = _median(values)
    return statistics.median([abs(v - med) for v in values])


def _outlier_threshold(values: list[float], k: float = 3.5) -> float | None:
    """离群上界：`中位 + k × 1.4826 × MAD`（MAD 归一化到正态尺度）。

    MAD 为 0（样本高度一致）时返回 None——此时任何偏离都不宜判为离群，
    避免把正常抖动误标。
    """
    if not values:
        return None
    scale = 1.4826 * _mad(values)
    if scale <= 0:
        return None
    return _median(values) + k * scale


def _is_outlier(value: float, values: list[float], k: float = 3.5) -> bool:
    """该值是否超出稳健离群上界（阈值不可得时一律不判离群）。"""
    threshold = _outlier_threshold(values, k)
    return threshold is not None and value > threshold


def _robust_mean(values: list[float]) -> float:
    """稳健均值：剔除离群点后的均值（无离群点时等于普通均值）。"""
    kept = [v for v in values if not _is_outlier(v, values)]
    return _mean(kept or values)


def _stdev(values: list[float]) -> float:
    """总体标准差（空输入 0.0）；与 MAD 对照用，说明稳健性差异。"""
    if not values:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _z_scores(values: list[float]) -> list[float]:
    """逐样本 z 分数（总体标准差口径）；标准差为 0 时全为 0。"""
    if not values:
        return []
    sd = _stdev(values)
    if sd <= 0:
        return [0.0] * len(values)
    mean = _mean(values)
    return [(v - mean) / sd for v in values]


def _total_summary(records: list[dict[str, Any]]) -> dict[str, float]:
    """总耗时汇总：样本数 / 平均 / 中位 / P95 / P99 / 最长。

    Returns:
        {"count", "avg", "p50", "p95", "p99", "max"}（秒，保留 1 位小数）。
    """
    totals = [float(r.get("total_seconds") or 0) for r in records]
    if not totals:
        return {key: 0.0 for key in ("count", "avg", "p50", "p95", "p99", "max")}
    return {
        "count": float(len(totals)),
        "avg": round(_mean(totals), 1),
        "p50": round(_percentile(totals, 50), 1),
        "p95": round(_percentile(totals, 95), 1),
        "p99": round(_percentile(totals, 99), 1),
        "max": round(_min_max(totals)[1], 1),
    }


def _filter_records(
    records: list[dict[str, Any]],
    report_type: str | None,
    last_n: int | None,
    exclude_outlier: bool = False,
) -> list[dict[str, Any]]:
    """按报告类型过滤并截取最近 N 条（分组与分位概览共用同一口径）。

    ``exclude_outlier``：按总耗时稳健离群上界（中位 ± MAD）剔除离群运行——
    服务端超时重试等外部故障会把均值抬高数十秒，剔除后才是「正常运行」口径。
    """
    filtered = records
    if report_type:
        filtered = [r for r in filtered if r.get("report_type") == report_type]
    if last_n:
        filtered = filtered[-last_n:]
    if exclude_outlier:
        totals = [float(r.get("total_seconds") or 0) for r in filtered]
        filtered = [r for r in filtered if not _is_outlier(float(r.get("total_seconds") or 0), totals)]
    return filtered


def _outlier_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """标出总耗时离群的运行（供报告显式列出，而非静默剔除）。"""
    totals = [float(r.get("total_seconds") or 0) for r in records]
    return [r for r in records if _is_outlier(float(r.get("total_seconds") or 0), totals)]


def _merge_breakdown_stats(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """合并记录中的阶段细分（`breakdown`）统计。

    Returns:
        {父阶段: {子项名: {avg, max, count}}}；无细分数据时为空字典。
    """
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        breakdown = r.get("breakdown")
        if not isinstance(breakdown, dict):
            continue
        for parent, spans in breakdown.items():
            if not isinstance(spans, dict):
                continue
            for name, sec in spans.items():
                if isinstance(sec, bool) or not isinstance(sec, (int, float)):
                    continue
                values[parent][name].append(float(sec))
    result: dict[str, dict[str, dict[str, float]]] = {}
    for parent, spans in values.items():
        result[parent] = {
            name: {
                "avg": round(_mean(vals), 2),
                "max": round(_min_max(vals)[1], 2),
                "count": len(vals),
            }
            for name, vals in sorted(spans.items())
        }
    return result


def _merge_phase_stats(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """合并所有记录中的阶段统计（含阶段级分位）。

    Returns:
        {phase_name: {avg, min, max, p50, p95, count}}
    """
    phase_values: dict[str, list[float]] = defaultdict(list)
    for r in records:
        phases = r.get("phases", {})
        if isinstance(phases, dict):
            for name, sec in phases.items():
                phase_values[name].append(sec)
    result: dict[str, dict[str, float]] = {}
    for name, vals in sorted(phase_values.items()):
        result[name] = {
            "avg": round(_mean(vals), 2),
            "min": round(_min_max(vals)[0], 2),
            "max": round(_min_max(vals)[1], 2),
            "p50": round(_percentile(vals, 50), 2),
            "p95": round(_percentile(vals, 95), 2),
            "count": len(vals),
        }
    return result


def _group_records(
    records: list[dict[str, Any]],
    report_type: str | None,
    last_n: int | None,
    exclude_outlier: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """按 version+report_type 分组。

    Returns:
        {group_key: [records]}
    """
    filtered = _filter_records(records, report_type, last_n, exclude_outlier)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in filtered:
        key = f"{r.get('version', '?')} / {r.get('report_type', '?')}"
        groups[key].append(r)
    # 按时间排序
    for g in groups:
        groups[g].sort(key=lambda x: x.get("timestamp", ""))
    return dict(sorted(groups.items()))


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
        "分位为**最近秩**口径——P95/P99 即 95%/99% 的报告生成在该耗时内完成。",
        "",
        "| 口径 | 样本数 | 平均 | 中位 | P95 | P99 | 最长 |",
        "|:-----|------:|----:|----:|----:|----:|-----:|",
    ]
    for label, subset in rows:
        stat = _total_summary(subset)
        lines.append(
            f"| {label} | {int(stat['count'])} | {stat['avg']:.1f}s | {stat['p50']:.1f}s | "
            f"{stat['p95']:.1f}s | {stat['p99']:.1f}s | {stat['max']:.1f}s |"
        )
    lines.append("")
    return lines


def _outlier_lines(records: list[dict[str, Any]]) -> list[str]:
    """离群运行提示段（显式列出而非静默剔除）。"""
    outliers = _outlier_records(records)
    if not outliers:
        return []
    threshold = _outlier_threshold([float(r.get("total_seconds") or 0) for r in records])
    lines = [
        "## 离群运行（稳健口径）",
        "",
        f"判定：总耗时 > 中位 + 3.5 × 1.4826 × MAD（上界 {threshold:.1f}s）；"
        "MAD 为 0 时不判离群。用 `--exclude-outlier` 可剔除后重算。",
        "",
        "| 时间 | 版本 | 类型 | 总耗时 | 最慢阶段 |",
        "|:-----|:-----|:-----|------:|:---------|",
    ]
    for r in outliers:
        phases = r.get("phases") if isinstance(r.get("phases"), dict) else {}
        slowest = max(phases.items(), key=lambda kv: kv[1])[0] if phases else "?"
        lines.append(
            f"| {r.get('timestamp', '?')[:16]} | {r.get('version', '?')} | {r.get('report_type', '?')} | "
            f"{float(r.get('total_seconds') or 0):.1f}s | {slowest} |"
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


def build_trend_report(
    records: list[dict[str, Any]],
    report_type: str | None = None,
    last_n: int | None = None,
    exclude_outlier: bool = False,
    by: str | None = None,
) -> str:
    """生成性能趋势 Markdown 报告字符串。"""
    groups = _group_records(records, report_type, last_n, exclude_outlier)
    scoped = _filter_records(records, report_type, last_n, exclude_outlier)

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

    # ── 离群运行与尾部归因（稳健口径） ──
    lines.extend(_outlier_lines(scoped))
    lines.extend(_tail_attribution_lines(scoped))

    # ── LLM 运行上下文（等待/重试/降级/缓存/用量） ──
    lines.extend(_llm_context_lines(scoped))

    # ── 时段聚合（可选） ──
    if by:
        lines.extend(_bucket_lines(scoped, by))

    # ── 按组输出详情 ──
    for group_key, group_records in groups.items():
        lines.append(f"## {group_key}")
        lines.append("")
        lines.append(f"运行次数：**{len(group_records)}**")
        lines.append("")

        totals = [r.get("total_seconds", 0) for r in group_records]
        lines.append(f"- 总耗时范围：{_min_max(totals)[0]:.1f}s ~ {_min_max(totals)[1]:.1f}s")
        lines.append(f"- 平均总耗时：**{_mean(totals):.1f}s**（稳健均值 {_robust_mean(totals):.1f}s）")
        lines.append(
            f"- 95% 的报告在 **{_percentile(totals, 95):.1f}s** 内完成，"
            f"99% 在 **{_percentile(totals, 99):.1f}s** 内完成"
        )
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
    args = parser.parse_args()

    records = load_history()
    if not records:
        print("[!] 暂无性能历史数据（data/state/perf_history.jsonl 不存在或为空）")
        return 1

    report = build_trend_report(
        records,
        report_type=args.report_type,
        last_n=args.last,
        exclude_outlier=args.exclude_outlier,
        by=args.by,
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
