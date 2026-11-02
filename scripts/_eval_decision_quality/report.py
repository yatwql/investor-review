"""回测产物落盘与控制台摘要（纯展示）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _eval_decision_quality.primitives import (  # noqa: F401  原面依赖（常量 / 纯原语）
    BENCHMARK_INDEX,
    CAVEATS,
    CORRELATION_EXPECTED_SIGN,
    CORRELATION_MIN_SPAN,
    CORRELATION_STEP,
    CORRELATION_WINDOW,
    DEFAULT_DAYS,
    DEFAULT_LEDGER_DIR,
    DEFAULT_OUT_DIR,
    DISCIPLINE_EFFECT_HORIZON,
    DISCIPLINE_FIXED_STOP_PCT,
    DISCIPLINE_MIN_EDGE,
    DISCIPLINE_TRIGGER_HORIZON,
    DISCIPLINE_VOL_MULTIPLE,
    DISCIPLINE_VOL_WINDOW,
    HORIZONS,
    IC_THRESHOLD,
    MIN_SAMPLES,
    MONO_MIN_N,
    SIGNAL_FACTOR,
    SIGNAL_VALUATION,
    TERCILE_BUCKETS,
    _PROJECT_ROOT,
    _SCRIPTS_DIR,
    _aggregate_horizon,
    _mean,
    _ranks,
    bars_after,
    forward_close,
    load_decisions,
    load_events,
    load_signals,
    spearman,
    tercile_monotonic,
    verdict_discrimination,
    verdict_sample_gate,
)


def write_outputs(result: dict[str, Any], out_dir: str | Path) -> list[Path]:
    """阶段产物落 docs/tmp/：完整 JSON + 摘要 Markdown。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    phase = result["phase"]
    json_path = out / f"{phase}.json"
    md_path = out / f"{phase}.md"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_markdown(result))
    except OSError as exc:
        raise SystemExit(f"产物写入失败: {out}: {exc}") from exc
    return [json_path, md_path]


def render_markdown(result: dict[str, Any]) -> str:
    """阶段摘要 Markdown（判定表 + 陷阱脚注）。"""
    phase = result["phase"]
    lines = [f"# 回测摘要 — {phase}", ""]
    if phase == "horizon":
        lines += ["| 视界 | 成熟样本 | 命中率 | 均值收益 | 均值超额 | 判定 |", "|:---:|:---:|:---:|:---:|:---:|:---|"]
        for h in HORIZONS:
            a = result["horizons"][str(h)]
            lines.append(
                f"| {h} 日 | {a['n_matured']}/{a['n_decisions']} | {a['hit_rate']} | {a['mean_raw_return']} | {a['mean_excess']} | {a['verdict']} |"
            )
    elif phase == "factor-ic":
        lines += [
            f"信号条数：{result['n_signals']}；日期范围：{' ~ '.join(result['date_range'])}",
            "",
            "| 因子 | 视界 | n | IC | 单调 | 判定 |",
            "|:---|:---:|:---:|:---:|:---:|:---|",
        ]
        for r in result["rows"]:
            lines.append(
                f"| {r['factor']} | {r['horizon']} | {r['n']} | {r['ic']} | {'是' if r['tercile_monotonic'] else '否'} | {r['verdict']} |"
            )
    elif phase == "discipline":
        s = result["summary"]
        p_ = result["params"]
        lines += [
            f"样本 {s['n_samples']} 条（决策总数 {result['n_decisions']}）；"
            f"固定线 {p_['fixed_stop_pct']:.0%} vs 归一化线 −{p_['vol_multiple']}σ（窗口 {p_['vol_window']} 日）",
            "",
            "| 口径 | 触发数 | 触发率 | 效果窗口均值（第 6~20 日） |",
            "|:---|:---:|:---:|:---:|",
            f"| 固定线 | {s['fixed']['n']} | {s['fixed']['hit_rate']} | {s['fixed']['mean_effect_return']} |",
            f"| 归一化线 | {s['normalized']['n']} | {s['normalized']['hit_rate']} | {s['normalized']['mean_effect_return']} |",
            "",
            f"判定：{s['verdict']}（差值 {s['edge']}，预注册门槛 ±{abs(p_['min_edge']):.0%}、样本 ≥{p_['min_samples']}）",
        ]
    elif phase == "correlation":
        s = result["summary"]
        p_ = result["params"]
        lines += [
            f"品种 {result['n_codes']} 个；样本期 {s['span_days']} 交易日；窗口 {p_['window']} 日 / 步长 {p_['step']} 日",
            "",
            "| 窗口数 | Spearman IC | 三分位单调 | 预注册方向 | 判定 |",
            "|:---:|:---:|:---:|:---:|:---|",
            f"| {s['n_windows']} | {s['ic']} | {'是' if s['tercile_monotonic'] else '否'} | 正（相关性↑→回撤↑） | {s['verdict']} |",
        ]
    elif phase == "valuation":
        lines += [
            f"信号条数：{result['n_signals']}；真实口径不可得原因分布：{result['real_unavailable_reasons']}",
            "",
            "| 视界 | 口径 | n | IC | 单调 | 判定 |",
            "|:---:|:---|:---:|:---:|:---:|:---|",
        ]
        for h in HORIZONS:
            for caliber in ("proxy", "real"):
                a = result["summary"][str(h)][caliber]
                label = "价格代理" if caliber == "proxy" else "真实PE·PB"
                lines.append(
                    f"| {h} 日 | {label} | {a['n']} | {a['ic']} | {'是' if a['tercile_monotonic'] else '否'} | {a['verdict']} |"
                )
    lines += ["", "## 已知陷阱（结论不得外推）", ""]
    lines += [f"- {c}" for c in result.get("caveats", [])]
    lines.append("")
    return "\n".join(lines)


def _print_phase_summary(result: dict[str, Any]) -> None:
    """控制台摘要（UI 前缀口径）。"""
    phase = result["phase"]
    if phase == "horizon":
        for h in HORIZONS:
            a = result["horizons"][str(h)]
            print(
                f"  {h:>2} 日视界: 成熟 {a['n_matured']}/{a['n_decisions']} 命中率 {a['hit_rate']} 超额 {a['mean_excess']} → {a['verdict']}"
            )
    elif phase == "factor-ic":
        passed = [r for r in result["rows"] if r["passed"]]
        print(f"  因子数 {len({r['factor'] for r in result['rows']})}；有区分度判定 {len(passed)} 条（视界 × 因子）")
    elif phase == "correlation":
        s = result["summary"]
        print(f"  样本期 {s['span_days']} 交易日；窗口 {s['n_windows']} 个；IC={s['ic']} → {s['verdict']}")
    elif phase == "discipline":
        s = result["summary"]
        print(
            f"  样本 {s['n_samples']} 条；固定线触发 {s['fixed']['n']} / 归一化线触发 {s['normalized']['n']} → {s['verdict']}"
        )
    elif phase == "valuation":
        for h in HORIZONS:
            p = result["summary"][str(h)]["proxy"]
            r = result["summary"][str(h)]["real"]
            print(
                f"  {h:>2} 日视界: 代理 n={p['n']} IC={p['ic']} → {p['verdict']} | 真实 n={r['n']} IC={r['ic']} → {r['verdict']}"
            )
