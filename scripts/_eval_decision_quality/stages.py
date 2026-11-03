"""回测阶段实现（决策视界 / 因子 IC / 估值口径 / 止损口径 / 相关性↔回撤）。"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Callable

from src.python.analysis.valuation_percentile import (  # noqa: F401  口径函数
    compute_price_percentile,
    compute_real_valuation,
)
from src.python.core import decision_ledger as dl  # noqa: F401  方向判定
from src.python.fetcher.financial_indicator import fetch_indicator_series  # noqa: F401
from src.python.report.decision_settlement import (  # noqa: F401  行情/指数序列
    _series_at_date,
    fetch_index_series,
    fetch_price_series,
)

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
#  止损口径对照：固定止损线 vs 波动率归一化止损线
# ═══════════════════════════════════════════════════════════════


def daily_volatility(
    series: list[dict[str, Any]] | None,
    rep_date: str,
    window: int = DISCIPLINE_VOL_WINDOW,
) -> float | None:
    """报告日之前 window 个交易日收益率的总体标准差（未年化）。

    Args:
        series: 行情 bar 序列（含 date / close 或 nav）。
        rep_date: 报告日（只用 <= 该日的 bar，避免前视偏差）。
        window: 窗口交易日数。

    Returns:
        日波动率；窗口不足或无有效收盘价 → None（不猜）。
    """
    prior = [b for b in (series or []) if str(b.get("date") or "") <= rep_date]
    closes: list[float] = []
    for bar in prior[-(window + 1) :]:
        close = bar.get("close") or bar.get("nav")
        try:
            close_f = float(close) if close is not None else 0.0
        except (TypeError, ValueError):
            close_f = 0.0
        if close_f > 0:
            closes.append(close_f)
    if len(closes) < window + 1:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    if len(rets) < 2:
        return None
    return round(statistics.pstdev(rets), 6)


def discipline_sample(
    decision: dict[str, Any],
    series: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """单个决策样本：触发窗口收益 + 效果窗口收益 + 两条止损线判定。

    两条线的口径都是「标的价格自报告日累计跌幅」——与决策方向无关（止损针对持仓风险），
    故样本取全部已结算决策；判不出（窗口未成熟 / 波动率不足 / 基线缺失）即跳过。
    """
    code = str(decision.get("code") or "")
    rep = str(decision.get("report_date") or "")
    try:
        baseline = float(decision.get("baseline_close") or 0.0)
    except (TypeError, ValueError):
        baseline = 0.0
    if not code or not rep or baseline <= 0:
        return None
    sigma = daily_volatility(series, rep)
    trig_close, _ = forward_close(series, rep, DISCIPLINE_TRIGGER_HORIZON)
    eff_close, _ = forward_close(series, rep, DISCIPLINE_EFFECT_HORIZON)
    if sigma is None or trig_close is None or eff_close is None:
        return None
    trigger_return = trig_close / baseline - 1.0
    effect_return = eff_close / trig_close - 1.0  # 第 6~20 日收益（触发窗口之后）
    normalized_line = -DISCIPLINE_VOL_MULTIPLE * sigma
    return {
        "decision_id": str(decision.get("decision_id") or ""),
        "code": code,
        "report_date": rep,
        "sigma": sigma,
        "trigger_return": round(trigger_return, 6),
        "effect_return": round(effect_return, 6),
        "normalized_line": round(normalized_line, 6),
        "fixed_hit": trigger_return <= DISCIPLINE_FIXED_STOP_PCT,
        "normalized_hit": trigger_return <= normalized_line,
    }


def aggregate_discipline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """两组（固定线 / 归一化线）效果对比与预注册判定。"""

    def _group(hit_key: str) -> dict[str, Any]:
        group = [r for r in rows if r.get(hit_key)]
        mean_effect = _mean([r["effect_return"] for r in group])
        return {
            "n": len(group),
            "mean_effect_return": None if mean_effect is None else round(mean_effect, 6),
            "hit_rate": round(len(group) / len(rows), 4) if rows else None,
        }

    fixed = _group("fixed_hit")
    normalized = _group("normalized_hit")
    verdict = "样本不足（<100，仅记录不裁决）"
    edge: float | None = None
    if fixed["n"] >= MIN_SAMPLES and normalized["n"] >= MIN_SAMPLES:
        if fixed["mean_effect_return"] is not None and normalized["mean_effect_return"] is not None:
            edge = round(normalized["mean_effect_return"] - fixed["mean_effect_return"], 6)
            if edge <= DISCIPLINE_MIN_EDGE:
                verdict = "归一化更优（触发的样本后续跌得更多）"
            elif edge >= abs(DISCIPLINE_MIN_EDGE):
                verdict = "归一化更差（触发的样本后续反弹更多）"
            else:
                verdict = "无差异（差值在预注册容差内）"
    return {
        "n_samples": len(rows),
        "fixed": fixed,
        "normalized": normalized,
        "edge": edge,
        "verdict": verdict,
    }


def stage_discipline(
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    days: int = DEFAULT_DAYS,
    price_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """阶段：止损阈值口径对照（固定 −15% vs −k·σ），取数可注入。"""
    price_fn = price_fn or fetch_price_series
    decisions = load_decisions(Path(ledger_dir) / "decision_ledger.jsonl")
    series_by_code: dict[str, list[dict[str, Any]] | None] = {}
    for d in decisions:
        code = str(d.get("code") or "")
        if code not in series_by_code:
            series_by_code[code] = price_fn(code, str(d.get("name") or ""), days)
    rows = []
    for d in decisions:
        row = discipline_sample(d, series_by_code.get(str(d.get("code") or "")))
        if row is not None:
            rows.append(row)
    return {
        "phase": "discipline",
        "params": {
            "fixed_stop_pct": DISCIPLINE_FIXED_STOP_PCT,
            "vol_window": DISCIPLINE_VOL_WINDOW,
            "vol_multiple": DISCIPLINE_VOL_MULTIPLE,
            "trigger_horizon": DISCIPLINE_TRIGGER_HORIZON,
            "effect_horizon": DISCIPLINE_EFFECT_HORIZON,
            "min_samples": MIN_SAMPLES,
            "min_edge": DISCIPLINE_MIN_EDGE,
        },
        "n_decisions": len(decisions),
        "summary": aggregate_discipline(rows),
        "rows": rows,
        "caveats": CAVEATS
        + [
            "止损口径对照以「标的跌幅」判定，与决策方向无关；样本取全部已结算决策",
            "效果窗口取触发窗口之后的第 6~20 个交易日收益（越负表示止损越早避开后续下跌）",
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  相关性↔回撤（持仓相关性矩阵与最大回撤的关系）
# ═══════════════════════════════════════════════════════════════


def series_daily_returns(bars: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """行情 bar → 日收益序列（升序，缺收盘价的相邻对跳过）。"""
    closes: list[tuple[str, float]] = []
    for bar in bars or []:
        close = bar.get("close") or bar.get("nav")
        try:
            close_f = float(close) if close is not None else 0.0
        except (TypeError, ValueError):
            close_f = 0.0
        if close_f > 0:
            closes.append((str(bar.get("date") or ""), close_f))
    out: list[dict[str, Any]] = []
    for i in range(1, len(closes)):
        prev_date, prev_close = closes[i - 1]
        date, close = closes[i]
        if not date or not prev_date or prev_close <= 0:
            continue
        out.append({"date": date, "return": close / prev_close - 1.0})
    return out


def average_pairwise_correlation(returns_by_code: dict[str, list[dict[str, Any]]]) -> float | None:
    """窗口内平均两两相关系数（复用 `analysis.correlation.compute_correlation_matrix`）。"""
    from src.python.analysis.correlation import compute_correlation_matrix

    if len(returns_by_code) < 2:
        return None
    # 窗口内日期对齐后有效样本会少于窗口天数（停牌/净值缺口），门槛按窗口的 60% 取，
    # 低于下限的样本对由矩阵格里 None 表达，不影响其余配对
    result = compute_correlation_matrix(
        returns_by_code,
        window=CORRELATION_WINDOW,
        min_samples=max(20, int(CORRELATION_WINDOW * 0.6)),
    )
    if not result.get("available"):
        return None
    # 逐对可用性由矩阵下三角表达（部分格为 None）：只对有效格取均值，不因个别品种
    # 样本不足而丢掉整个窗口（`status` 可能为 partial，属正常态）
    matrix = result.get("matrix") or []
    values: list[float] = []
    for row_idx, row in enumerate(matrix):
        for col_idx, value in enumerate(row):
            if col_idx < row_idx and isinstance(value, (int, float)):
                values.append(float(value))
    return _mean(values)


def window_return_series(returns_by_code: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """窗口内等权组合的日收益序列（按日期对齐，缺该日收益的品种当日不参与）。"""
    by_date: dict[str, list[float]] = {}
    for seq in returns_by_code.values():
        for item in seq:
            by_date.setdefault(str(item.get("date") or ""), []).append(float(item.get("return") or 0.0))
    return [{"date": d, "return": _mean(vals) or 0.0} for d, vals in sorted(by_date.items()) if d]


def max_drawdown_of(returns: list[dict[str, Any]]) -> float | None:
    """收益序列的最大回撤（正数=跌幅百分比，便于与相关性同向比较）。"""
    if not returns:
        return None
    equity, peak, worst = 1.0, 1.0, 0.0
    for item in returns:
        equity *= 1.0 + float(item.get("return") or 0.0)
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return round(worst, 6)


def build_correlation_windows(
    series_by_code: dict[str, list[dict[str, Any]] | None],
) -> tuple[list[dict[str, Any]], int]:
    """滚动窗口 → [(窗口, 平均两两相关, 等权组合最大回撤)]；返回 (窗口行, 样本期交易日数)。"""
    returns_by_code = {code: rets for code, bars in series_by_code.items() if (rets := series_daily_returns(bars))}
    if len(returns_by_code) < 2:
        return [], 0
    all_dates = sorted({item["date"] for seq in returns_by_code.values() for item in seq})
    span = len(all_dates)
    rows: list[dict[str, Any]] = []
    for start in range(0, max(span - CORRELATION_WINDOW + 1, 0), CORRELATION_STEP):
        end_date = all_dates[min(start + CORRELATION_WINDOW, span) - 1]
        window_returns = {
            code: [item for item in seq if item["date"] <= end_date][-CORRELATION_WINDOW:]
            for code, seq in returns_by_code.items()
        }
        corr = average_pairwise_correlation(window_returns)
        drawdown = max_drawdown_of(window_return_series(window_returns))
        if corr is None or drawdown is None:
            continue
        rows.append(
            {
                "start": all_dates[start],
                "end": end_date,
                "mean_correlation": round(corr, 6),
                "max_drawdown": drawdown,
                "n_codes": len([c for c, seq in window_returns.items() if seq]),
            }
        )
    return rows, span


def aggregate_correlation(rows: list[dict[str, Any]], span_days: int) -> dict[str, Any]:
    """相关性↔回撤关系判定（预注册：样本期 ≥250、窗口 ≥100、|IC| ≥0.05、三分位单调）。"""
    xs = [float(r["mean_correlation"]) for r in rows]
    ys = [float(r["max_drawdown"]) for r in rows]
    ic = spearman(xs, ys) if len(rows) >= 3 else None
    monotonic = tercile_monotonic(xs, ys) if len(rows) >= MONO_MIN_N else False
    if span_days < CORRELATION_MIN_SPAN:
        verdict = f"样本期不足（{span_days} < {CORRELATION_MIN_SPAN} 交易日，仅记录不裁决）"
    elif len(rows) < MIN_SAMPLES:
        verdict = f"样本不足（窗口 {len(rows)} < {MIN_SAMPLES}，仅记录不裁决）"
    elif ic is None or abs(ic) < IC_THRESHOLD or not monotonic:
        verdict = "叙述性维度（不进决策路径）"
    elif (ic > 0) != (CORRELATION_EXPECTED_SIGN > 0):
        verdict = "方向相反（与预注册方向不符，不采信）"
    else:
        verdict = "通过（相关性升高与更深回撤同向且单调）"
    return {
        "span_days": span_days,
        "n_windows": len(rows),
        "ic": None if ic is None else round(ic, 4),
        "tercile_monotonic": monotonic,
        "expected_sign": CORRELATION_EXPECTED_SIGN,
        "verdict": verdict,
    }


def stage_correlation(
    *,
    ledger_dir: str | Path = DEFAULT_LEDGER_DIR,
    days: int = DEFAULT_DAYS,
    price_fn: Callable[..., list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """阶段：持仓相关性矩阵与最大回撤的关系（品种集合取决策账本，等权组合口径）。"""
    price_fn = price_fn or fetch_price_series
    decisions = load_decisions(Path(ledger_dir) / "decision_ledger.jsonl")
    names: dict[str, str] = {}
    for d in decisions:
        code = str(d.get("code") or "")
        if code:
            names.setdefault(code, str(d.get("name") or ""))
    series_by_code = {code: price_fn(code, name, days) for code, name in names.items()}
    rows, span_days = build_correlation_windows(series_by_code)
    return {
        "phase": "correlation",
        "params": {
            "window": CORRELATION_WINDOW,
            "step": CORRELATION_STEP,
            "min_span": CORRELATION_MIN_SPAN,
            "min_samples": MIN_SAMPLES,
            "ic_threshold": IC_THRESHOLD,
            "expected_sign": CORRELATION_EXPECTED_SIGN,
        },
        "n_codes": len(names),
        "summary": aggregate_correlation(rows, span_days),
        "rows": rows,
        "caveats": CAVEATS
        + [
            "品种集合取决策账本出现过的代码，组合口径为等权（非实际持仓权重）",
            "窗口步长 20 交易日以降低重叠自相关；相关性为窗口内平均两两相关系数",
        ],
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
