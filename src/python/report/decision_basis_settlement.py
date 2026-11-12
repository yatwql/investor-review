"""判断依据章内块 — 结算摘要与按视界历史表现（由 `decision_basis.py` 聚合门面 re-export）。

批次口径 = 结算交易日（与「历史决策复盘」块同一数据源 `fold_ledger`，不另算一套）；
命中判定复用 `core.decision_ledger.classify_direction_outcome`，均值超额 = 原始收益 −
同期基准收益（基准缺失的条目不进超额均值），命中率仅在方向性样本 ≥
`MEANINGFUL_SAMPLE` 时给结论值。只读账本，零取数零 LLM；着色只给涨跌域变量。
"""

from __future__ import annotations

from typing import Any

from src.python.core.decision_ledger import fold_ledger

# ── 结算摘要（最近 5 批 × 多视界；批次 = 结算交易日）────────────
SETTLEMENT_HORIZONS: tuple[int, ...] = (5, 20, 60)
SETTLEMENT_MAX_BATCHES = 5


def _tone_of(value: float | None) -> str:
    """涨跌域色变量（红涨绿跌，A 股口径；与状态域互斥，不混用）。"""
    if value is None or value == 0:
        return ""
    return "--profit" if value > 0 else "--loss"


def _tone_class_of(value: float | None) -> str:
    """涨跌域语义类（红涨绿跌；零/缺失不加类，与状态域互斥）。"""
    if value is None or value == 0:
        return ""
    return "tone-profit" if value > 0 else "tone-loss"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


PERFORMANCE_TITLE = "我的建议历史表现（按视界）"


def performance_verdict(accuracy: float | None, excess_pct: float | None) -> str:
    """按「命中率 × 均值超额」两轴给一句人话结论（四象限 + 缺轴降级）。

    命中过半只看 > 50%（含 50% 视为「过半」边界；口径与账本「方向命中」一致），
    超额正负按 0 分界。任一轴缺数据时只说可得的那一轴，不拿单项冒充整体。

    Args:
        accuracy: 命中率（0~1；None = 无方向性样本）。
        excess_pct: 均值超额（百分数；None = 无基准数据）。

    Returns:
        一句结论文本；两轴都缺 → 「—」。
    """
    if accuracy is None and excess_pct is None:
        return "—"
    if accuracy is None:
        return "仅有超额：跑赢基准" if excess_pct is not None and excess_pct >= 0 else "仅有超额：跑输基准"
    hit_half = accuracy >= 0.5
    if excess_pct is None:
        return "方向命中过半（缺基准，无法比超额）" if hit_half else "方向命中不足一半（缺基准，无法比超额）"
    if hit_half and excess_pct >= 0:
        return "方向有效且跑赢基准"
    if hit_half:
        return "方向命中但跑输基准"
    if excess_pct >= 0:
        return "方向偏错但选品仍跑赢基准"
    return "方向与超额双弱"


def build_performance(
    decisions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """按视界聚合「我的建议历史表现」（只读账本，与 `settle-decisions` 同口径）。

    口径单源：命中判定复用 `core.decision_ledger.classify_direction_outcome`
    （含 ±1.5% 平盘不判定阈值），均值超额 = 原始收益 − 同期基准收益（基准缺失
    的条目不进超额均值）。命中率仅在方向性有效样本 ≥ `MEANINGFUL_SAMPLE` 时给
    百分比结论，否则以「命中/总数」并列并标注样本不足——与命令行结算、`doctor`
    账本概览同一判据，不另立口径。

    Args:
        decisions: `fold_ledger()` 的 decisions；None 时读当前账本。

    Returns:
        每个视界一行：{horizon, settled, directional, hit, miss, flat, gap,
        accuracy_label, accuracy_value, mean_excess_label, sample_sufficient,
        tone_class}
    """
    from src.python.core import decision_ledger as dl

    ledger_decisions: list[dict[str, Any]] = (
        decisions if decisions is not None else list(fold_ledger().get("decisions") or [])
    )
    per_horizon: dict[int, dict[str, Any]] = {}
    for decision in ledger_decisions:
        settlements = decision.get("settlements") or {}
        if not isinstance(settlements, dict):
            continue
        try:
            direction = int(decision.get("direction") or 0)
        except (TypeError, ValueError):
            direction = 0
        for raw_horizon, event in settlements.items():
            if not isinstance(event, dict):
                continue
            try:
                horizon = int(raw_horizon)
            except (TypeError, ValueError):
                continue
            raw_return = event.get("raw_return")
            raw_value: float | None = None
            if isinstance(raw_return, (int, float)) and not isinstance(raw_return, bool):
                raw_value = float(raw_return)
            bucket = per_horizon.setdefault(horizon, {"counts": {}, "excess": []})
            # 缺失收益的行计入 gap（数据缺口），不能静默丢样本——否则已结算数与账本不符
            outcome, _hit = dl.classify_direction_outcome(raw_value, direction)
            bucket["counts"][outcome] = bucket["counts"].get(outcome, 0) + 1
            bench_return = event.get("bench_return")
            if raw_value is not None and isinstance(bench_return, (int, float)) and not isinstance(bench_return, bool):
                bucket["excess"].append(raw_value - float(bench_return))

    rows: list[dict[str, Any]] = []
    for horizon in SETTLEMENT_HORIZONS:
        bucket = per_horizon.get(horizon)
        if bucket is None:
            continue
        counts = bucket["counts"]
        hit = counts.get("hit", 0)
        miss = counts.get("miss", 0)
        directional = hit + miss
        settled = sum(counts.values())
        mean_excess = _mean(bucket["excess"])
        excess_pct = None if mean_excess is None else mean_excess * 100
        sufficient = directional >= dl.MEANINGFUL_SAMPLE
        accuracy = hit / directional if directional else None
        if accuracy is None:
            accuracy_label = "—"
        elif sufficient:
            accuracy_label = f"{accuracy:.0%}"
        else:
            accuracy_label = f"{hit}/{directional}（样本不足）"
        rows.append(
            {
                "horizon": horizon,
                "settled": settled,
                "directional": directional,
                "hit": hit,
                "miss": miss,
                "flat": counts.get("flat", 0),
                "gap": counts.get("gap", 0),
                "accuracy_label": accuracy_label,
                "accuracy_value": None if accuracy is None else round(accuracy, 4),
                "mean_excess_label": "—" if excess_pct is None else f"{excess_pct:+.2f}%",
                "verdict": performance_verdict(accuracy, excess_pct),
                # 样本不足时把结论降级为「仅参考」标注，避免小样本被当定论
                "verdict_label": (
                    performance_verdict(accuracy, excess_pct)
                    if sufficient or accuracy is None
                    else f"{performance_verdict(accuracy, excess_pct)}（样本不足，仅参考）"
                ),
                "sample_sufficient": sufficient,
                "tone_class": _tone_class_of(excess_pct),
            }
        )
    return rows


def build_settlement_summary(
    decisions: list[dict[str, Any]] | None = None,
    *,
    max_batches: int = SETTLEMENT_MAX_BATCHES,
) -> dict[str, Any]:
    """装配结算摘要块（最近 N 批 × 5/20/60 视界，均值收益与均值超额）。

    批次口径 = 结算交易日（与「历史决策复盘」块同一数据源 `fold_ledger`，不另算
    一套）；超额 = 该条原始收益 − 同期基准收益，基准缺失的条目只计入收益均值。

    Args:
        decisions: `fold_ledger()` 的 decisions（含 `settlements` 多视界映射）；
            None 时读当前账本。
        max_batches: 批次上限（默认 5）。

    Returns:
        {available, reason, horizons, batches[{date, n, cells[{horizon, n,
        state, mean_return_pct, mean_excess_pct, value_label, excess_label,
        color_var}]}], note}
    """
    ledger_decisions: list[dict[str, Any]] = (
        decisions if decisions is not None else list(fold_ledger().get("decisions") or [])
    )
    # settle_date → horizon → [(raw_return, excess|None)]
    buckets: dict[str, dict[int, list[tuple[float, float | None]]]] = {}
    for decision in ledger_decisions:
        settlements = decision.get("settlements") or {}
        if not isinstance(settlements, dict):
            continue
        for raw_horizon, event in settlements.items():
            if not isinstance(event, dict):
                continue
            try:
                horizon = int(raw_horizon)
            except (TypeError, ValueError):
                continue
            settle_date = str(event.get("settle_date") or "")
            raw_return = event.get("raw_return")
            if not settle_date or not isinstance(raw_return, (int, float)) or isinstance(raw_return, bool):
                continue
            try:
                raw_value = float(raw_return)
            except (TypeError, ValueError):
                continue
            bench_return = event.get("bench_return")
            excess: float | None = None
            if isinstance(bench_return, (int, float)) and not isinstance(bench_return, bool):
                try:
                    excess = raw_value - float(bench_return)
                except (TypeError, ValueError):
                    excess = None
            buckets.setdefault(settle_date, {}).setdefault(horizon, []).append((raw_value, excess))

    dates = sorted(buckets, reverse=True)[: max(int(max_batches), 1)]
    batches: list[dict[str, Any]] = []
    for date in dates:
        cells: list[dict[str, Any]] = []
        batch_n = 0
        for horizon in SETTLEMENT_HORIZONS:
            samples: list[tuple[float, float | None]] = buckets[date].get(horizon) or []
            batch_n = max(batch_n, len(samples))
            if not samples:
                cells.append(
                    {
                        "horizon": horizon,
                        "n": 0,
                        "state": "pending",
                        "mean_return_pct": None,
                        "mean_excess_pct": None,
                        "value_label": "未到期",
                        "excess_label": "—",
                        "color_var": "",
                        "tone_class": "",
                    }
                )
                continue
            mean_return = _mean([raw for raw, _ in samples])
            excess_values = [exc for _, exc in samples if exc is not None]
            mean_excess = _mean(excess_values)
            return_pct = None if mean_return is None else mean_return * 100
            excess_pct = None if mean_excess is None else mean_excess * 100
            cells.append(
                {
                    "horizon": horizon,
                    "n": len(samples),
                    "state": "settled",
                    "mean_return_pct": None if return_pct is None else round(return_pct, 2),
                    "mean_excess_pct": None if excess_pct is None else round(excess_pct, 2),
                    # 展示口径：收益（超额）——超额缺失只显示收益
                    "value_label": "—" if return_pct is None else f"{return_pct:+.2f}%",
                    "excess_label": "—" if excess_pct is None else f"{excess_pct:+.2f}%",
                    "color_var": _tone_of(return_pct),
                    "tone_class": _tone_class_of(return_pct),
                }
            )
        batches.append({"date": date, "n": batch_n, "cells": cells})
    return {
        "available": True,
        "reason": "",
        "horizons": list(SETTLEMENT_HORIZONS),
        "batches": batches,
        # 「我的建议历史表现」按视界聚合：只读账本、不依赖 decision_reflection 开关
        "performance_title": PERFORMANCE_TITLE,
        "performance": build_performance(ledger_decisions),
        "note": ("批次按结算交易日聚合（上限 5 批），更多明细见「历史决策复盘」块" if batches else "暂无结算样本"),
    }
