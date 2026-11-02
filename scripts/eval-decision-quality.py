"""投资决策质量待验证项回测（入口）。

阶段：horizon / factor-ic / valuation / discipline / correlation。
实现拆在 `_eval_decision_quality/` 包（primitives / stages / report），本文件只留路径、
原面 re-export 与 CLI——既有调用方与测试仍按本入口取函数。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── 项目路径（脚本独立运行 / 动态加载时先把仓库根与 scripts/ 加入 sys.path） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
for _p in (str(_PROJECT_ROOT), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _eval_decision_quality.primitives import (  # noqa: F401  原面 re-export
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
from _eval_decision_quality.stages import (  # noqa: F401  原面 re-export
    aggregate_correlation,
    aggregate_discipline,
    aggregate_valuation,
    average_pairwise_correlation,
    build_correlation_windows,
    collect_factor_pairs,
    collect_valuation_rows,
    daily_volatility,
    discipline_sample,
    max_drawdown_of,
    series_daily_returns,
    stage_correlation,
    stage_discipline,
    stage_factor_ic,
    stage_horizon,
    stage_valuation,
    window_return_series,
)
from _eval_decision_quality.report import (  # noqa: F401  原面 re-export
    render_markdown,
    write_outputs,
    _print_phase_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="投资决策质量待验证项回测（产物落 docs/tmp/decision-quality/）")
    parser.add_argument(
        "stage",
        choices=["horizon", "factor-ic", "valuation", "discipline", "correlation", "all"],
        nargs="?",
        default="all",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="取数窗口（交易日 bar 数）")
    parser.add_argument("--bench", default=BENCHMARK_INDEX, help="基准指数代码")
    parser.add_argument("--ledger-dir", default=str(DEFAULT_LEDGER_DIR), help="账本目录（data/state）")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="产物输出目录")
    args = parser.parse_args(argv)

    stages = ["horizon", "factor-ic", "valuation", "discipline", "correlation"] if args.stage == "all" else [args.stage]
    for stage_name in stages:
        print(f"[..] 回测阶段 {stage_name}（days={args.days}）")
        if stage_name == "horizon":
            result = stage_horizon(ledger_dir=args.ledger_dir, days=args.days, bench_index=args.bench)
        elif stage_name == "factor-ic":
            result = stage_factor_ic(ledger_dir=args.ledger_dir, days=args.days, bench_index=args.bench)
        elif stage_name == "discipline":
            result = stage_discipline(ledger_dir=args.ledger_dir, days=args.days)
        elif stage_name == "correlation":
            result = stage_correlation(ledger_dir=args.ledger_dir, days=args.days)
        else:
            result = stage_valuation(ledger_dir=args.ledger_dir, days=args.days)
        _print_phase_summary(result)
        paths = write_outputs(result, args.out)
        print(f"[OK] {stage_name} 产物: {', '.join(str(p) for p in paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
