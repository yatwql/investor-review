"""perf-history 渲染：Markdown 表格拼装、机读输出与趋势报告。

依赖 :mod:`_perf_history.data` 的数据派生与 :mod:`_perf_history.stats` 的统计原语；
CLI 入口见 :mod:`_perf_history.cli`。
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.python.llm.pricing import PRICING_CURRENCY, currency_symbol, format_costs

from _perf_history.data import (
    _add_costs,
    _record_costs,
    _slowest_phase,
    _version_evolution_data,
    _is_abnormal_record,
    _drift_data,
    _bucket_key,
    _compare_versions,
)
import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _perf_history.stats import (
    _DRIFT_MIN_SAMPLES,
    _OUTLIER_K,
    _filter_records,
    _group_filtered,
    _group_records as _group_records,  # re-export：经 load_script 供测试直调
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
    _total_summary,
    _z_scores,
)


_TMP_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_TREND_REPORT_PATH = os.path.join(_TMP_DIR, "perf_trend.md")


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


def _format_bucket(bucket: dict[str, float]) -> str:
    """时段费用单元格：有非零金额按币种分列；只有 0 值样本时给本币 0.0000。"""
    if not bucket:
        return "—"
    if any(amount for amount in bucket.values()):
        return format_costs(bucket)
    return f"{currency_symbol(sorted(bucket)[0])}0.0000"


def _cost_delta(prev: dict[str, float], cur: dict[str, float]) -> str:
    """两个时段的费用环比：同币种才给数值，跨币种返回破折号（不相减）。"""
    codes = set(prev) | set(cur)
    if len(codes) != 1:
        return "—"
    code = next(iter(codes))
    delta = float(cur.get(code, 0.0)) - float(prev.get(code, 0.0))
    sign = "-" if delta < 0 else "+"
    return f"{sign}{currency_symbol(code)}{abs(delta):.4f}"


def _bucket_lines(records: list[dict[str, Any]], by: str) -> list[str]:
    """按时段聚合（day/week/hour）：样本数 / 中位 / P95 / 最长 / 费用合计 / 费用环比。

    费用列仅在范围内存在费用样本时出现（零费用不制造全列噪音）；费用环比 =
    本时段 llm 费用合计 − 上一时序时段合计，首时段无上期为 —。时段键升序即
    时间序（ISO 日期 / ISO 周 / 小时），费用与耗时同表交叉，直接读出趋势。
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    costs: dict[str, dict[str, float]] = defaultdict(dict)
    for r in records:
        key = _bucket_key(r.get("timestamp", ""), by)
        buckets[key].append(float(r.get("total_seconds") or 0))
        llm = r.get("llm")
        if isinstance(llm, dict):
            _add_costs(costs[key], _record_costs(llm) or {PRICING_CURRENCY: 0.0})
    if not buckets:
        return []
    has_cost = any(any(v > 0 for v in bucket.values()) for bucket in costs.values())
    label = {"day": "日期", "week": "ISO 周", "hour": "小时"}[by]
    lines = [f"## 时段聚合（按{label}）", ""]
    if has_cost:
        lines.extend(
            [
                "| 时段 | 样本数 | 中位 | P95 | 最长 | 费用合计 | 费用环比 |",
                "|:-----|------:|----:|----:|-----:|--------:|--------:|",
            ]
        )
    else:
        lines.extend(
            [
                "| 时段 | 样本数 | 中位 | P95 | 最长 |",
                "|:-----|------:|----:|----:|-----:|",
            ]
        )
    keys = sorted(buckets)
    prev_cost: dict[str, float] | None = None
    for key in keys:
        vals = buckets[key]
        row = (
            f"| {key} | {len(vals)} | {_median(vals):.1f}s | {_percentile(vals, 95):.1f}s | {_min_max(vals)[1]:.1f}s |"
        )
        if has_cost:
            cur_costs = costs.get(key) or {}
            delta_cell = "—" if prev_cost is None else _cost_delta(prev_cost, cur_costs)
            row += f" {_format_bucket(cur_costs)} | {delta_cell} |"
            prev_cost = cur_costs
        lines.append(row)
    if has_cost and len(keys) >= 2:
        last_costs = costs.get(keys[-1]) or {}
        prev_costs = costs.get(keys[-2]) or {}
        delta = _cost_delta(prev_costs, last_costs)
        if delta != "—":
            lines.append("")
            lines.append(
                f"**费用环比（末档 vs 前档）**：{_format_bucket(prev_costs)} → {_format_bucket(last_costs)}（{delta}）"
            )
        elif last_costs or prev_costs:
            lines.append("")
            lines.append("**费用环比（末档 vs 前档）**：跨币种不可直接相减，已省略数值环比")
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
    total_costs: dict[str, float] = {}
    for r in with_ctx:
        _add_costs(total_costs, _record_costs(r["llm"]))

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
    if any(total_costs.values()):
        lines.append(f"| 累计费用 | {format_costs(total_costs)} | 按币种分列 |")
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


def _freshness_line(records: list[dict[str, Any]]) -> str | None:
    """数据新鲜度行：最新记录时间戳与距今时长（读表先判断数据是否新鲜）。

    时间戳解析失败时降级为仅展示原值；时刻不得展示相对时长。
    """
    stamps = sorted(str(r.get("timestamp") or "") for r in records if r.get("timestamp"))
    if not stamps:
        return None
    latest = stamps[-1]
    try:
        dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        secs = max((now - dt).total_seconds(), 0.0)
    except ValueError:
        return f"**数据新鲜度**：最新记录 {latest[:19]}（时间解析失败，显示原值）"
    when = latest[:16]
    if secs < 60:
        return f"**数据新鲜度**：最新记录 {when}（刚刚）"
    if secs < 3600:
        return f"**数据新鲜度**：最新记录 {when}（{int(secs // 60)} 分钟前）"
    if secs < 86400:
        return f"**数据新鲜度**：最新记录 {when}（{int(secs // 3600)} 小时前）"
    return f"**数据新鲜度**：最新记录 {when}（{int(secs // 86400)} 天前）"


def build_trend_report(
    records: list[dict[str, Any]],
    report_type: str | None = None,
    last_n: int | None = None,
    exclude_outlier: bool = False,
    by: str | None = None,
    compare: tuple[str, str] | None = None,
    summary: bool = False,
    outlier_k: float = _OUTLIER_K,
    version: str | None = None,
) -> str:
    """生成性能趋势 Markdown 报告字符串。

    ``summary``：仅输出概览段（总体分位/离群/尾部归因/LLM 上下文/时段聚合/对比），
    略去逐版本分组详情——记录多、分组多时避免输出过长。
    """
    scoped = _filter_records(records, report_type, last_n, exclude_outlier, outlier_k, version)
    groups = _group_filtered(scoped)
    fresh = _freshness_line(records)

    lines: list[str] = [
        "# 报告生成性能趋势",
        "",
        "**数据来源**：`data/state/perf_history.jsonl`",
        f"**总记录数**：{len(records)} 条",
        *([f"**版本筛选**：{version}（前缀匹配）"] if version else []),
        f"**分组数**：{len(groups)} 组",
        *([fresh] if fresh else []),
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
    llm_ctx_lines = _llm_context_lines(scoped)
    if llm_ctx_lines:
        lines.extend(llm_ctx_lines)
    elif any(str(r.get("report_type")) == "full" for r in scoped):
        # 范围内有完整报告记录（会产生上下文）但无数据：明示缺而非静默省段
        lines.append("## LLM 运行上下文")
        lines.append("")
        lines.append("_（暂无 LLM 上下文记录：provider/等待/用量维度随完整报告采集，历史记录不含此维度）_")
        lines.append("")

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
            total_avg = _mean(totals) if totals else 0.0
            lines.append("| 阶段 | 平均耗时 | 中位 | P95 | 最短 | 最长 | 次数 | 占比 |")
            lines.append("|:-----|--------:|----:|----:|----:|----:|-----:|-----:|")
            for name, stat in phase_stats.items():
                pct = (stat["avg"] / total_avg * 100) if total_avg > 0 else 0.0
                lines.append(
                    f"| {name} | {stat['avg']:.2f}s | {stat['p50']:.2f}s | {stat['p95']:.2f}s | "
                    f"{stat['min']:.2f}s | {stat['max']:.2f}s | {stat['count']} | {pct:.0f}% |"
                )
            lines.append("_（占比 = 阶段均值 ÷ 组平均总耗时；并行执行的阶段之和可超 100%）_")
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
        elif str(group_records[0].get("report_type")) == "full":
            # 完整报告组但无细分数据（记录早于细分采集）：明示缺而非静默省表
            lines.append("_（暂无阶段细分：LLM/新闻子项细分随完整报告采集，该组历史记录不含此维度）_")
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
