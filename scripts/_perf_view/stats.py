"""perf-view 统计工具 — 分位 / 离群 / 分组的纯函数。

perf-view 报告编排的统计实现层；主入口以 re-export 保持
``load_script("perf-view.py")`` 后 ``mod._percentile`` 等符号可访问。
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any


#: 离群判定系数（中位 + k × 1.4826 × MAD）；3.5 为常用经验值，可经 --outlier-k 覆盖
_OUTLIER_K = 3.5
#: 同版本漂移检测的最少样本（时间对半后每边 ≥3；低于此不参与，半样本中位不稳）
_DRIFT_MIN_SAMPLES = 6

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

    口径含义：至少 `pct%` 的样本 ≤ 返回值——P95 即「95% 的报告在该耗时内完成」，
    P99 即「99% 的报告在该耗时内完成」。空输入返回 0.0。

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


def _outlier_threshold(values: list[float], k: float = _OUTLIER_K) -> float | None:
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


def _is_outlier(value: float, values: list[float], k: float = _OUTLIER_K) -> bool:
    """该值是否超出稳健离群上界（阈值不可得时一律不判离群）。"""
    threshold = _outlier_threshold(values, k)
    return threshold is not None and value > threshold


def _robust_mean(values: list[float], k: float = _OUTLIER_K) -> float:
    """稳健均值：剔除离群点后的均值（无离群点时等于普通均值）。"""
    kept = [v for v in values if not _is_outlier(v, values, k)]
    return _mean(kept or values)


def _stdev(values: list[float]) -> float:
    """总体标准差（空输入 0.0）；与 MAD 对照用，说明稳健性差异。"""
    if not values:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _cv(values: list[float]) -> float:
    """变异系数（标准差/均值）；样本 <2 或均值为 0 时返回 0。"""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return (_stdev(values) / mean) if mean > 0 else 0.0


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


def _per_holding_median(records: list[dict[str, Any]]) -> float | None:
    """秒/品种（总耗时 ÷ 持仓数）的中位——跨规模（持仓数不同）可比的归一化口径。

    持仓数为 0/缺失的记录跳过；无有效记录返回 None。
    """
    vals = [
        float(r.get("total_seconds") or 0) / int(r.get("holdings_count") or 0)
        for r in records
        if int(r.get("holdings_count") or 0) > 0
    ]
    return round(_median(vals), 3) if vals else None


def _filter_records(
    records: list[dict[str, Any]],
    report_type: str | None,
    last_n: int | None,
    exclude_outlier: bool = False,
    outlier_k: float = _OUTLIER_K,
    version: str | None = None,
) -> list[dict[str, Any]]:
    """按版本、报告类型过滤并截取最近 N 条（分组与分位概览共用同一口径）。

    ``version``：前缀匹配（`X.Y.Z` 命中带后缀的同系列版本），None 不过滤版本；
    在报告类型过滤之后、截尾之前应用。
    ``exclude_outlier``：按总耗时稳健离群上界（中位 ± MAD）剔除离群运行——
    服务端超时重试等外部故障会把均值抬高数十秒，剔除后才是「正常运行」口径。
    """
    filtered = records
    if report_type:
        filtered = [r for r in filtered if r.get("report_type") == report_type]
    if version:
        filtered = [r for r in filtered if str(r.get("version") or "").startswith(version)]
    if last_n:
        filtered = filtered[-last_n:]
    if exclude_outlier:
        totals = [float(r.get("total_seconds") or 0) for r in filtered]
        filtered = [r for r in filtered if not _is_outlier(float(r.get("total_seconds") or 0), totals, outlier_k)]
    return filtered


def _outlier_records(records: list[dict[str, Any]], k: float = _OUTLIER_K) -> list[dict[str, Any]]:
    """标出总耗时离群的运行（供报告显式列出，而非静默剔除）。"""
    totals = [float(r.get("total_seconds") or 0) for r in records]
    return [r for r in records if _is_outlier(float(r.get("total_seconds") or 0), totals, k)]


def _merge_breakdown_stats(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """合并记录中的阶段细分（`breakdown`）统计。

    Returns:
        {父阶段: {子项名: {avg, max, count}}}；无细分数据时为空字典。
        父内子项按平均耗时降序（最慢在前，同分按名——输出稳定可 diff）。
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
        spans_stats = {
            name: {
                "avg": round(_mean(vals), 2),
                "max": round(_min_max(vals)[1], 2),
                "count": len(vals),
            }
            for name, vals in spans.items()
        }
        result[parent] = dict(sorted(spans_stats.items(), key=lambda kv: (-kv[1]["avg"], kv[0])))
    return result


def _merge_phase_stats(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """合并所有记录中的阶段统计（含阶段级分位）。

    Returns:
        {phase_name: {avg, min, max, p50, p95, count}}，按中位降序
        （最慢阶段排最前，同分按名——输出稳定可 diff）。
    """
    phase_values: dict[str, list[float]] = defaultdict(list)
    for r in records:
        phases = r.get("phases", {})
        if isinstance(phases, dict):
            for name, sec in phases.items():
                phase_values[name].append(sec)
    result: dict[str, dict[str, float]] = {}
    for name, vals in phase_values.items():
        result[name] = {
            "avg": round(_mean(vals), 2),
            "min": round(_min_max(vals)[0], 2),
            "max": round(_min_max(vals)[1], 2),
            "p50": round(_percentile(vals, 50), 2),
            "p95": round(_percentile(vals, 95), 2),
            "count": len(vals),
        }
    return dict(sorted(result.items(), key=lambda kv: (-kv[1]["p50"], kv[0])))


def _group_records(
    records: list[dict[str, Any]],
    report_type: str | None,
    last_n: int | None,
    exclude_outlier: bool = False,
    outlier_k: float = _OUTLIER_K,
    version: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """按 version+report_type 分组（``version`` 前缀透传给过滤器）。

    组间顺序按各组**首次运行时间**升序（与版本演进总表同口径）——最新版本组
    在最末；组内记录按时间戳升序。不用版本号字符串序：主版本位数不同时
    字典序与数值序相反（“9” > “10”），与真实先后不符。

    Returns:
        {group_key: [records]}
    """
    filtered = _filter_records(records, report_type, last_n, exclude_outlier, outlier_k, version)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in filtered:
        key = f"{r.get('version', '?')} / {r.get('report_type', '?')}"
        groups[key].append(r)
    # 组内按时间排序；组间按首次运行时间（首条即最早）升序，最新组在末尾
    for g in groups:
        groups[g].sort(key=lambda x: x.get("timestamp", ""))
    return {k: groups[k] for k in sorted(groups, key=lambda k: (str(groups[k][0].get("timestamp", "")), k))}
