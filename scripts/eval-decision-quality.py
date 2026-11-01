"""投资决策质量待验证项回测工具（非生产代码；评测产物落 docs/tmp/decision-quality/）。

承接讨论稿 `docs/plan/investment-decision-quality.md` §2.2 的预注册口径，三个阶段：

  horizon     决策建议在 5/20/60 交易日视界的命中率与超额（讨论稿 §8「视界」项）
  factor-ic   因子目录单因子 IC（组合级因子 × 沪深300 前向收益代理口径）
  valuation   估值信号「价格代理 / 真实 PE·PB」两口径区分度（同窗对比）
  all         依序执行全部阶段

预注册判据（跑完不得回改；改判据须改本段并全量重跑）：
  - 样本量门槛：每类统计 ≥100 个可结算样本才下结论，否则「样本不足，仅记录不裁决」
  - 信号区分度判据：①三分位组均值单调 ②Spearman 秩相关 |IC| ≥ 0.05（满足其一）
  - 拒绝标准：|IC| < 0.05 且无单调性 →「叙述性维度」（记录在案，不进方向轴）

已知陷阱（结论不得外推，产物脚注必须带）：
  - 样本期约 3 个月、单一市场状态，任何结论都不能外推到其他市场状态
  - 同一份报告的多个品种收益高度相关（共同 β），有效独立样本远小于记录条数
  - 报告盘后生成，信号与结算价之间存在延迟

口径说明：
  - 固定视界结算：取「报告日之后第 N 个交易日收盘」对比决策登记的 baseline_close；
    账本生产结算（decision_settlement）用「最新收盘」动态视界，两者基线同源、终点不同，
    本工具用于回测对比，不替代账本结算。
  - 估值两口径同窗：价格代理与真实估值均用「报告日及之前」同一窗口 bars 重算，
    隔离口径定义差异；账本内展示值另行记录（ledger_percentile）供对照，不参与分组统计。

纪律：
  - 取数只经既有能力（decision_settlement 行情/指数序列 + valuation_percentile 口径函数 +
    financial_indicator 缓存链），不裸调 provider；
  - 只读账本与缓存，不写 data/ 生产状态；产物只落 docs/tmp/（git 忽略）；
  - 不 import report 管线与 llm，生产侧零改动。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

# ── 项目路径（脚本独立运行 / 动态加载时先把仓库根加入 sys.path） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.python.analysis.valuation_percentile import (  # noqa: E402
    compute_price_percentile,
    compute_real_valuation,
)
from src.python.core import decision_ledger as dl  # noqa: E402
from src.python.fetcher.financial_indicator import fetch_indicator_series  # noqa: E402
from src.python.report.decision_settlement import (  # noqa: E402
    _series_at_date,
    fetch_index_series,
    fetch_price_series,
)

# ── 预注册常量（讨论稿 §2.2；改动即口径变更，须全量重跑） ──
HORIZONS = (5, 20, 60)  # 结算视界（交易日）
BENCHMARK_INDEX = "sh000300"  # 组合/因子层基准代理
MIN_SAMPLES = 100  # 样本量门槛：低于此只记录不裁决
IC_THRESHOLD = 0.05  # |IC| 拒绝线
TERCILE_BUCKETS = 3  # 分组单调性桶数
MONO_MIN_N = 6  # 单调性判定最少样本（每桶 ≥2）

DEFAULT_DAYS = 120  # 取数窗口（交易日 bar 数）
DEFAULT_OUT_DIR = _PROJECT_ROOT / "docs" / "tmp" / "decision-quality"
DEFAULT_LEDGER_DIR = _PROJECT_ROOT / "data" / "state"

SIGNAL_VALUATION = "valuation_percentile"
SIGNAL_FACTOR = "factor_catalog"

CAVEATS = [
    "样本期约 3 个月、单一市场状态，结论不得外推到其他市场状态",
    "同报告多品种收益高度相关（共同 β），有效独立样本远小于记录条数",
    "报告盘后生成，信号与结算价之间存在延迟",
]


# ═══════════════════════════════════════════════════════════════
#  账本读取（只读）
# ═══════════════════════════════════════════════════════════════


def load_events(path: str | Path) -> list[dict[str, Any]]:
    """读取 jsonl 账本事件（一行一条 JSON）；读取/解析失败即中止（评测不猜数据）。"""
    events: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except OSError as exc:
        raise SystemExit(f"账本读取失败: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"账本格式错误（非合法 JSON 行）: {path}: {exc}") from exc
    return events


def load_decisions(path: str | Path) -> list[dict[str, Any]]:
    """取有方向、有基线、有报告日的决策事件（可结算候选全集）。"""
    out: list[dict[str, Any]] = []
    for e in load_events(path):
        if e.get("event") != "decision":
            continue
        direction = int(e.get("direction") or 0)
        if direction not in (dl.DIRECTION_LONG, dl.DIRECTION_SHORT):
            continue
        if float(e.get("baseline_close") or 0) <= 0 or not e.get("report_date"):
            continue
        out.append(e)
    return out


def load_signals(path: str | Path, signal_type: str) -> list[dict[str, Any]]:
    """取 signal_ledger 中指定类型的信号事件。"""
    return [e for e in load_events(path) if e.get("event") == "signal" and e.get("signal_type") == signal_type]


# ═══════════════════════════════════════════════════════════════
#  纯计算原语（可单测）
# ═══════════════════════════════════════════════════════════════


def bars_after(series: list[dict[str, Any]] | None, rep_date: str) -> list[dict[str, Any]]:
    """报告日之后的交易日 bar（严格大于报告日）。"""
    return [b for b in (series or []) if str(b.get("date") or "") > rep_date]


def forward_close(
    series: list[dict[str, Any]] | None,
    rep_date: str,
    horizon: int,
) -> tuple[float | None, int]:
    """固定视界收盘：报告日之后第 horizon 个交易日的 close。

    Returns:
        (close, bars_after 数)；未满视界或该 bar 无有效 close → (None, bars_after 数)。
    """
    after = bars_after(series, rep_date)
    if len(after) < max(horizon, 1):
        return None, len(after)
    bar = after[horizon - 1]
    close = bar.get("close") or bar.get("nav")
    try:
        close_f = float(close) if close is not None else 0.0
    except (TypeError, ValueError):
        close_f = 0.0
    return (close_f if close_f > 0 else None), len(after)


def _ranks(xs: list[float]) -> list[float]:
    """平均秩（并列取均值），Spearman 用。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 秩相关；样本 <3 或任一侧零方差 → None。"""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def tercile_monotonic(xs: list[float], ys: list[float]) -> bool:
    """按 x 排序三分组，y 组均值单调（升或降）；样本不足或空桶 → False。"""
    n = len(xs)
    if n < MONO_MIN_N or len(ys) != n:
        return False
    pairs = sorted(zip(xs, ys))
    size = n // TERCILE_BUCKETS
    means: list[float] = []
    for b in range(TERCILE_BUCKETS):
        chunk = [y for _, y in pairs[b * size : n if b == TERCILE_BUCKETS - 1 else (b + 1) * size]]
        if not chunk:
            return False
        means.append(sum(chunk) / len(chunk))
    if len(set(means)) == 1:  # 组均值无差异（零区分度）不算单调
        return False
    asc = all(a <= b for a, b in zip(means, means[1:]))
    desc = all(a >= b for a, b in zip(means, means[1:]))
    return asc or desc


def verdict_discrimination(n: int, ic: float | None, monotonic: bool) -> dict[str, Any]:
    """信号区分度三态判定（预注册：样本门槛 → 区分度 → 叙述性维度）。"""
    if n < MIN_SAMPLES:
        return {"verdict": "样本不足，仅记录不裁决", "passed": None}
    if (ic is not None and abs(ic) >= IC_THRESHOLD) or monotonic:
        return {"verdict": "有区分度", "passed": True}
    return {"verdict": "叙述性维度（不进方向轴）", "passed": False}


def verdict_sample_gate(n: int) -> dict[str, Any]:
    """命中率可信度判定（只看样本量门槛，不做 IC 判据）。"""
    if n < MIN_SAMPLES:
        return {"verdict": "样本不足，仅记录不裁决", "credible": False}
    return {"verdict": "达到采信门槛（记录命中率）", "credible": True}


# ═══════════════════════════════════════════════════════════════
#  阶段一：决策建议视界命中率
# ═══════════════════════════════════════════════════════════════


def _aggregate_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    """按视界聚合决策行：成熟数 / 命中率 / 均值收益 / 超额 / 方向拆分。"""
    key = str(horizon)
    matured = [r["horizons"][key] for r in rows if r["horizons"][key]["matured"]]
    hits = [m["direction_hit"] for m in matured if m["direction_hit"] is not None]
    raws = [m["raw_return"] for m in matured]
    excess = [m["excess"] for m in matured if m["excess"] is not None]
    by_dir: dict[str, dict[str, Any]] = {}
    for d, label in ((dl.DIRECTION_LONG, "long"), (dl.DIRECTION_SHORT, "short")):
        sub = [r["horizons"][key] for r in rows if int(r["direction"]) == d and r["horizons"][key]["matured"]]
        sub_hits = [m["direction_hit"] for m in sub if m["direction_hit"] is not None]
        by_dir[label] = {
            "n": len(sub),
            "hit_rate": round(sum(sub_hits) / len(sub_hits), 4) if sub_hits else None,
        }
    n = len(matured)
    n_hit = len(hits)
    return {
        "n_decisions": len(rows),
        "n_matured": n,
        "n_unmatured": len(rows) - n,
        "hit_rate": round(sum(hits) / n_hit, 4) if n_hit else None,
        "mean_raw_return": round(sum(raws) / n, 6) if n else None,
        "mean_excess": round(sum(excess) / len(excess), 6) if excess else None,
        "n_with_bench": len(excess),
        "by_direction": by_dir,
        **verdict_sample_gate(n),
    }


def stage_horizon(
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    days: int = DEFAULT_DAYS,
    bench_index: str = BENCHMARK_INDEX,
    price_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
    index_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """阶段一：决策建议在各视界的命中率与超额（取数可注入，测试用）。"""
    price_fn = price_fn or fetch_price_series
    index_fn = index_fn or fetch_index_series
    decisions = load_decisions(Path(ledger_dir) / "decision_ledger.jsonl")

    series_by_code: dict[str, list[dict[str, Any]] | None] = {}
    for d in decisions:
        code = str(d.get("code") or "")
        if code not in series_by_code:
            series_by_code[code] = price_fn(code, str(d.get("name") or ""), days)
    index_series = index_fn(bench_index, days)

    rows: list[dict[str, Any]] = []
    for d in decisions:
        code = str(d.get("code") or "")
        rep = str(d.get("report_date") or "")
        baseline = float(d["baseline_close"])
        direction = int(d["direction"])
        series = series_by_code.get(code)
        idx_base = _series_at_date(index_series, rep) if index_series else None
        horizons: dict[str, Any] = {}
        for h in HORIZONS:
            fwd, n_after = forward_close(series, rep, h)
            if fwd is None:
                horizons[str(h)] = {"matured": False, "bars_after": n_after}
                continue
            raw = fwd / baseline - 1.0
            outcome, hit = dl.classify_direction_outcome(raw, direction)
            bench_ret: float | None = None
            if index_series is not None and idx_base:
                idx_fwd, _ = forward_close(index_series, rep, h)
                if idx_fwd:
                    bench_ret = idx_fwd / idx_base - 1.0
            horizons[str(h)] = {
                "matured": True,
                "raw_return": round(raw, 6),
                "outcome": outcome,
                "direction_hit": hit,
                "bench_return": round(bench_ret, 6) if bench_ret is not None else None,
                "excess": round(raw - bench_ret, 6) if bench_ret is not None else None,
            }
        rows.append(
            {
                "decision_id": str(d.get("decision_id") or ""),
                "code": code,
                "direction": direction,
                "report_date": rep,
                "horizons": horizons,
            }
        )

    return {
        "phase": "horizon",
        "bench_index": bench_index,
        "days": days,
        "horizons": {str(h): _aggregate_horizon(rows, h) for h in HORIZONS},
        "unique_codes": sorted({r["code"] for r in rows}),
        "rows": rows,
        "caveats": CAVEATS,
    }


# ═══════════════════════════════════════════════════════════════
#  阶段二：因子目录单因子 IC
# ═══════════════════════════════════════════════════════════════


def collect_factor_pairs(
    signals: list[dict[str, Any]],
    index_fwd_by_date: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """收集各因子 × 各视界的 (因子值, 基准前向收益) 配对。"""
    per_factor: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for s in signals:
        values = (s.get("detail") or {}).get("values") or {}
        fwd = index_fwd_by_date.get(str(s.get("report_date") or ""), {})
        for k, v in values.items():
            if v is None:
                continue
            try:
                v_f = float(v)
            except (TypeError, ValueError):
                continue
            for h in HORIZONS:
                f = fwd.get(str(h))
                if f is None:
                    continue
                per_factor.setdefault(k, {}).setdefault(str(h), []).append((v_f, f))
    return per_factor


def stage_factor_ic(
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    days: int = DEFAULT_DAYS,
    bench_index: str = BENCHMARK_INDEX,
    index_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """阶段二：因子目录单因子 IC（组合级因子 × 基准前向收益代理口径）。"""
    index_fn = index_fn or fetch_index_series
    signals = load_signals(Path(ledger_dir) / "signal_ledger.jsonl", SIGNAL_FACTOR)
    index_series = index_fn(bench_index, days)

    # 每报告日 × 视界的基准前向收益（同一日期只算一次）
    index_fwd_by_date: dict[str, dict[str, float | None]] = {}
    for s in signals:
        rep = str(s.get("report_date") or "")
        if rep in index_fwd_by_date:
            continue
        base = _series_at_date(index_series, rep) if index_series else None
        entry: dict[str, float | None] = {}
        for h in HORIZONS:
            fwd, _ = forward_close(index_series, rep, h)
            entry[str(h)] = fwd / base - 1.0 if (fwd and base) else None
        index_fwd_by_date[rep] = entry

    per_factor = collect_factor_pairs(signals, index_fwd_by_date)
    rows: list[dict[str, Any]] = []
    for factor in sorted(per_factor):
        for h in HORIZONS:
            pairs = per_factor[factor].get(str(h), [])
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            ic = spearman(xs, ys)
            mono = tercile_monotonic(xs, ys)
            rows.append(
                {
                    "factor": factor,
                    "horizon": h,
                    "n": len(xs),
                    "ic": ic,
                    "tercile_monotonic": mono,
                    **verdict_discrimination(len(xs), ic, mono),
                }
            )

    n_signals = len(signals)
    dates = sorted({str(s.get("report_date") or "") for s in signals})
    return {
        "phase": "factor-ic",
        "bench_index": bench_index,
        "proxy_note": "组合级因子无横截面，以基准指数前向收益作代理；IC 仅回答「能否预测市场」，不代表组合归因",
        "n_signals": n_signals,
        "date_range": [dates[0], dates[-1]] if dates else [],
        "rows": rows,
        "caveats": CAVEATS,
    }


# ═══════════════════════════════════════════════════════════════
#  阶段三：估值信号两口径区分度
# ═══════════════════════════════════════════════════════════════


def collect_valuation_rows(
    signals: list[dict[str, Any]],
    *,
    days: int,
    price_fn: Callable[..., list[dict[str, Any]] | None],
    fin_fn: Callable[[str], list[dict[str, Any]]],
    proxy_fn: Callable[..., dict[str, Any]] = compute_price_percentile,
    real_fn: Callable[..., dict[str, Any]] = compute_real_valuation,
) -> list[dict[str, Any]]:
    """逐信号重算两口径分位（报告日及之前同窗 bars）并附各视界前向收益。"""
    rows: list[dict[str, Any]] = []
    series_cache: dict[str, list[dict[str, Any]] | None] = {}
    fin_cache: dict[str, list[dict[str, Any]]] = {}
    for s in signals:
        subject = str(s.get("subject") or "")
        rep = str(s.get("report_date") or "")
        if subject not in series_cache:
            series_cache[subject] = price_fn(subject, str(s.get("name") or ""), days)
        series = series_cache.get(subject)
        price = _series_at_date(series, rep) if series else None
        bars_to = [b for b in (series or []) if str(b.get("date") or "") <= rep]
        row: dict[str, Any] = {
            "subject": subject,
            "report_date": rep,
            "ledger_percentile": s.get("value"),
            "proxy_percentile": None,
            "real_percentile": None,
            "real_reason": None,
            "forward_returns": {},
        }
        if price is None or not bars_to:
            row["skipped"] = "no_bars"
            rows.append(row)
            continue
        proxy = proxy_fn(bars_to)
        row["proxy_percentile"] = proxy.get("price_percentile") if proxy.get("available") else None
        if subject not in fin_cache:
            fin_cache[subject] = fin_fn(subject)
        real = real_fn(bars_to, fin_cache.get(subject, []), price)
        pct = real.get("pe_percentile")
        if pct is None:
            pct = real.get("pb_percentile")
        row["real_percentile"] = pct
        if pct is None:
            row["real_reason"] = real.get("reason")
        for h in HORIZONS:
            fwd, _ = forward_close(series, rep, h)
            row["forward_returns"][str(h)] = fwd / price - 1.0 if fwd else None
        rows.append(row)
    return rows


def aggregate_valuation(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """按视界 × 口径聚合：n / IC / 单调性 / 三态判定。"""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for h in HORIZONS:
        out[str(h)] = {}
        for caliber in ("proxy", "real"):
            pts = [
                (r[f"{caliber}_percentile"], r["forward_returns"].get(str(h)))
                for r in rows
                if r.get(f"{caliber}_percentile") is not None and r["forward_returns"].get(str(h)) is not None
            ]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ic = spearman(xs, ys)
            mono = tercile_monotonic(xs, ys)
            out[str(h)][caliber] = {
                "n": len(pts),
                "ic": ic,
                "tercile_monotonic": mono,
                **verdict_discrimination(len(xs), ic, mono),
            }
    return out


def stage_valuation(
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    days: int = DEFAULT_DAYS,
    price_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
    fin_fn: Callable[[str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """阶段三：估值信号「价格代理 / 真实 PE·PB」两口径区分度（同窗对比）。"""
    price_fn = price_fn or fetch_price_series
    fin_fn = fin_fn or fetch_indicator_series
    signals = load_signals(Path(ledger_dir) / "signal_ledger.jsonl", SIGNAL_VALUATION)
    rows = collect_valuation_rows(signals, days=days, price_fn=price_fn, fin_fn=fin_fn)
    reasons: dict[str, int] = {}
    for r in rows:
        if r.get("real_reason"):
            reasons[str(r["real_reason"])] = reasons.get(str(r["real_reason"]), 0) + 1
    return {
        "phase": "valuation",
        "n_signals": len(rows),
        "n_skipped_no_bars": sum(1 for r in rows if r.get("skipped")),
        "real_unavailable_reasons": reasons,
        "caliber_note": "两口径同窗（报告日及之前 bars）重算，隔离口径定义差异；ledger_percentile 仅对照不参与统计",
        "summary": aggregate_valuation(rows),
        "rows": rows,
        "caveats": CAVEATS,
    }


# ═══════════════════════════════════════════════════════════════
#  产物落盘与摘要输出
# ═══════════════════════════════════════════════════════════════


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
    elif phase == "valuation":
        for h in HORIZONS:
            p = result["summary"][str(h)]["proxy"]
            r = result["summary"][str(h)]["real"]
            print(
                f"  {h:>2} 日视界: 代理 n={p['n']} IC={p['ic']} → {p['verdict']} | 真实 n={r['n']} IC={r['ic']} → {r['verdict']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="投资决策质量待验证项回测（产物落 docs/tmp/decision-quality/）")
    parser.add_argument("stage", choices=["horizon", "factor-ic", "valuation", "all"], nargs="?", default="all")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="取数窗口（交易日 bar 数）")
    parser.add_argument("--bench", default=BENCHMARK_INDEX, help="基准指数代码")
    parser.add_argument("--ledger-dir", default=str(DEFAULT_LEDGER_DIR), help="账本目录（data/state）")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="产物输出目录")
    args = parser.parse_args(argv)

    stages = ["horizon", "factor-ic", "valuation"] if args.stage == "all" else [args.stage]
    for stage_name in stages:
        print(f"[..] 回测阶段 {stage_name}（days={args.days}）")
        if stage_name == "horizon":
            result = stage_horizon(ledger_dir=args.ledger_dir, days=args.days, bench_index=args.bench)
        elif stage_name == "factor-ic":
            result = stage_factor_ic(ledger_dir=args.ledger_dir, days=args.days, bench_index=args.bench)
        else:
            result = stage_valuation(ledger_dir=args.ledger_dir, days=args.days)
        _print_phase_summary(result)
        paths = write_outputs(result, args.out)
        print(f"[OK] {stage_name} 产物: {', '.join(str(p) for p in paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
