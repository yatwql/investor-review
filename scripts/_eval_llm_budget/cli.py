"""`scripts/eval-llm-budget.py` 的 CLI 实现（薄壳，逻辑在上述各模块）。

子命令：
  freeze  从持仓快照生成冻结样本（离线，零网络）
  run     跑测量矩阵并落盘（真实调用 LLM；``--dry-run`` 只打印计划）

退出码：
  0 — 成功（含判定不通过但在记录里标注）
  1 — 运行失败（样本缺失/依赖缺失/生成异常）
  2 — 参数错误
  3 — 判定不通过（供 CI 之外的人工流程快速判断）
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

from .budget import BUDGET_TIERS
from .report import build_verdict, render_markdown, summarize, write_outputs
from .runner import ALL_MODES, run_matrix
from .sample import build_sample_from_snapshot, load_sample, save_sample

DEFAULT_OUT_DIR = Path("docs/tmp/llm-budget")
DEFAULT_SAMPLE = Path("docs/tmp/llm-budget/sample.json")

logger = logging.getLogger("eval-llm-budget")


def _cmd_freeze(args: argparse.Namespace) -> int:
    try:
        sample = build_sample_from_snapshot(Path(args.snapshot))
    except (OSError, ValueError) as exc:
        print(f"  [ERR] 样本构建失败：{exc}")
        return 1
    output = save_sample(sample, Path(args.out))
    print(f"  [OK] 样本：{output}（{sample['holdings_count']} 只持仓）")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        sample = load_sample(Path(args.sample))
    except (OSError, ValueError) as exc:
        print(f"  [ERR] 样本读取失败：{exc}")
        return 1

    modes = tuple(args.modes.split(",")) if args.modes else ALL_MODES
    tiers = tuple(args.tiers.split(",")) if args.tiers else tuple(BUDGET_TIERS)
    unknown = [mode for mode in modes if mode not in ALL_MODES]
    if unknown:
        print(f"  [ERR] 未知模式：{unknown}（可选 {ALL_MODES}）")
        return 2
    unknown_tiers = [tier for tier in tiers if tier not in BUDGET_TIERS]
    if unknown_tiers:
        print(f"  [ERR] 未知档位：{unknown_tiers}（可选 {tuple(BUDGET_TIERS)}）")
        return 2

    records = run_matrix(
        sample,
        modes=modes,
        tiers=tiers,
        repeats=args.repeats,
        dry_run=args.dry_run,
        keep_text=args.keep_text,
        do_repair=args.repair,
    )
    if args.dry_run:
        planned = sum(1 for record in records)
        print(
            f"  [OK] 计划 {planned} 次生成（dry-run，未调用 LLM）：modes={modes} tiers={tiers} repeats={args.repeats}"
        )
        return 0

    summary = summarize(records)
    baseline = None
    if args.baseline:
        try:
            baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"  [ERR] 基线读取失败：{args.baseline}（{exc}）")
            return 2
    verdict = build_verdict(summary, baseline)
    meta = {
        "sample": Path(args.sample).name,
        "holdings_count": sample["holdings_count"],
        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
        "model": records[0].get("model", "—") if records else "—",
    }
    paths = write_outputs(Path(args.out_dir), records, summary, render_markdown(summary, verdict, meta))
    print(f"  [OK] 记录：{paths['records']}")
    print(f"  [OK] 报告：{paths['report']}")
    print("  " + ("[OK] 判定通过" if verdict["passed"] else f"  [!] 判定不通过：{verdict['failed']}"))
    return 0 if verdict["passed"] else 3


def build_parser() -> argparse.ArgumentParser:
    """构造参数解析器（供测试与 `--help`）。"""
    parser = argparse.ArgumentParser(
        prog="eval-llm-budget.py",
        description="LLM 表达预算校准（离线评测，不进三档门禁）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="从持仓快照生成冻结样本")
    freeze.add_argument("--snapshot", required=True, help="data/history/snapshots/snapshot_*.json")
    freeze.add_argument("--out", default=str(DEFAULT_SAMPLE), help="样本输出路径")
    freeze.set_defaults(func=_cmd_freeze)

    run = sub.add_parser("run", help="跑测量矩阵并落盘")
    run.add_argument("--sample", default=str(DEFAULT_SAMPLE), help="冻结样本路径")
    run.add_argument("--modes", default="", help=f"逗号分隔，可选 {','.join(ALL_MODES)}")
    run.add_argument("--tiers", default="", help=f"逗号分隔，可选 {','.join(BUDGET_TIERS)}")
    run.add_argument("--repeats", type=int, default=3, help="每组合重复次数（默认 3）")
    run.add_argument("--baseline", default="", help="基线 JSON（含 duration_p50/action_rows/codes）")
    run.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="产物目录")
    run.add_argument("--dry-run", action="store_true", help="只打印计划，不调用 LLM")
    run.add_argument("--keep-text", action="store_true", help="记录输出摘录（排查解析问题用）")
    run.add_argument("--repair", action="store_true", help="缺结构时追加一次短补写（评测实验）")
    run.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口；返回退出码。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover - 常规由薄壳脚本调用
    sys.exit(main())
