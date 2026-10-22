"""perf-history 命令行入口：参数解析 → build_trend_report → 输出。

完整用法见入口文件 ``scripts/perf-history.py`` 的模块 docstring。
"""

from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from _perf_history.data import (
    _machine_readable,
)
from _perf_history.report import (
    build_trend_report,
)
import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _perf_history.stats import (
    _OUTLIER_K,
    _filter_records,
    _group_records as _group_records,  # re-export：经 load_script 供测试直调
    _is_outlier as _is_outlier,  # re-export：经 load_script 供测试直调
    _mad as _mad,  # re-export：同上
)

from src.python.core.perf import load_history

_TMP_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_TREND_REPORT_PATH = os.path.join(_TMP_DIR, "perf_trend.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="查看性能历史趋势")
    parser.add_argument("--report-type", choices=["basic", "both", "full"], help="仅查看指定报告类型")
    parser.add_argument(
        "--version",
        help="仅查看指定版本（前缀匹配，如 0.13.4 可命中 0.13.4-dev）",
    )
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="机读输出：完整记录 JSON（附 llm_cost 费用汇总，--by 时另附 by_period 时段费用序列）",
    )
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

    scoped = _filter_records(records, args.report_type, args.last, args.exclude_outlier, args.outlier_k, args.version)

    # ── 机读输出（与 Markdown 互斥，便于管道消费） ──
    if args.json or args.csv:
        if args.save:
            print("[!] --save 在机读模式下不适用（--json/--csv 只向 stdout 输出）", file=sys.stderr)
        print(_machine_readable(scoped, "json" if args.json else "csv", args.outlier_k, by=args.by))
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
            version=args.version,
        )
        print(report)

        if args.save:
            os.makedirs(_TMP_DIR, exist_ok=True)
            with open(_TREND_REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"[OK] 已写入: {_TREND_REPORT_PATH}")

    return 0
