#!/usr/bin/env python3
"""守护项命中统计 —— 读 `logs/guard-hits.jsonl`，输出「守护项 × 运行次数 × 命中次数 × 处置」表。

用途（非门禁）：分清「拦截过真问题的守护」与「永远干净的死规则」。台账由
`_shared/checklib.report()` 每次运行追加（脚本级），`check-doc-drift` 另记
「子项 → finding 数」明细；本脚本只做聚合与建议，**不改任何守护脚本的启用状态**。

用法：
  python scripts/probe-guard-hits.py
  python scripts/probe-guard-hits.py --min-runs 5      # 样本不足的判定门槛（默认 5）
  python scripts/probe-guard-hits.py --ledger /tmp/x.jsonl
  python scripts/probe-guard-hits.py -v                # 逐脚本附子项明细
  python scripts/probe-guard-hits.py --ci              # 仅输出表格行（不含说明段）

退出码：
  0 — 统计已输出（本脚本不是门禁，命中 0 次也不算失败）
  1 — 台账不可读（路径存在但解析失败/权限不足）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 共享设施包（_shared/checklib）
from _shared.checklib import GUARD_HITS_LEDGER, add_common_args  # noqa: E402

#: 处置判定
_KEEP = "保留"
_DOWNGRADE = "建议降频（CI 恒跑兜底）"
_NEED_MORE = "样本不足"
_NO_DATA = "无数据"


def _load(ledger: Path) -> tuple[list[dict], int]:
    """读台账，返回 ``(记录列表, 损坏行数)``；台账不存在视为空（首次使用）。"""
    if not ledger.exists():
        return [], 0
    records: list[dict] = []
    broken = 0
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            broken += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            broken += 1
    return records, broken


def summarize(records: list[dict], *, min_runs: int = 5) -> dict[str, list[dict]]:
    """聚合台账为 ``{"scripts": [...], "items": [...]}``（各自含运行/命中计数与处置）。"""
    script_runs: dict[str, int] = defaultdict(int)
    script_hits: dict[str, int] = defaultdict(int)
    script_findings: dict[str, int] = defaultdict(int)
    item_runs: dict[str, int] = defaultdict(int)
    item_hits: dict[str, int] = defaultdict(int)
    item_owner: dict[str, str] = {}

    for record in records:
        script = str(record.get("script") or "unknown")
        findings = int(record.get("findings") or 0)
        script_runs[script] += 1
        script_findings[script] += findings
        if findings > 0:
            script_hits[script] += 1
        details = record.get("details") or {}
        if isinstance(details, dict):
            for name, count in details.items():
                key = f"{script}::{name}"
                item_owner[key] = script
                item_runs[key] += 1
                if int(count or 0) > 0:
                    item_hits[key] += 1

    def _dispose(runs: int, hits: int) -> str:
        if runs == 0:
            return _NO_DATA
        if hits > 0:
            return _KEEP
        return _DOWNGRADE if runs >= min_runs else _NEED_MORE

    scripts = [
        {
            "name": name,
            "runs": script_runs[name],
            "hits": script_hits[name],
            "findings": script_findings[name],
            "dispose": _dispose(script_runs[name], script_hits[name]),
        }
        for name in script_runs
    ]
    scripts.sort(key=lambda row: (-row["hits"], -row["runs"], row["name"]))

    items = [
        {
            "name": key.split("::", 1)[1],
            "script": item_owner[key],
            "runs": item_runs[key],
            "hits": item_hits[key],
            "dispose": _dispose(item_runs[key], item_hits[key]),
        }
        for key in item_runs
    ]
    items.sort(key=lambda row: (row["script"], -row["hits"], row["name"]))
    return {"scripts": scripts, "items": items}


def format_table(summary: dict[str, list[dict]], *, verbose: bool) -> list[str]:
    """渲染为紧凑表格行（脚本级；verbose 追加子项级）。"""
    lines = ["守护脚本 | 运行次数 | 命中次数 | 命中 finding 总数 | 处置"]
    for row in summary["scripts"]:
        lines.append(f"{row['name']} | {row['runs']} | {row['hits']} | {row['findings']} | {row['dispose']}")
    if verbose and summary["items"]:
        lines.append("")
        lines.append("子项 | 所属脚本 | 运行次数 | 命中次数 | 处置")
        for row in summary["items"]:
            lines.append(f"{row['name']} | {row['script']} | {row['runs']} | {row['hits']} | {row['dispose']}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="守护项命中统计（读 logs/guard-hits.jsonl，输出运行次数/命中次数/处置建议；非门禁）",
    )
    add_common_args(parser)
    parser.add_argument(
        "--ledger", default=str(GUARD_HITS_LEDGER), help="命中台账路径（默认仓库 logs/guard-hits.jsonl）"
    )
    parser.add_argument("--min-runs", type=int, default=5, help="判定「样本不足」的运行次数门槛（默认 5）")
    args = parser.parse_args()

    ledger = Path(args.ledger)
    try:
        records, broken = _load(ledger)
    except OSError as exc:
        print(f"[ERR] 台账不可读: {exc}")
        sys.exit(1)

    summary = summarize(records, min_runs=args.min_runs)
    lines = format_table(summary, verbose=args.verbose)
    if args.ci:
        for line in lines:
            print(line)
        sys.exit(0)

    for line in lines:
        print(line)
    if not records:
        print(f"\n[!] 台账暂无记录（{ledger}）：先跑任意守护脚本即可开始积累。")
    else:
        downgrade = [row["name"] for row in summary["scripts"] if row["dispose"].startswith("建议降频")]
        note = f"建议降频 {len(downgrade)} 项：{'、'.join(downgrade)}" if downgrade else "无建议降频项"
        print(f"\n共 {len(records)} 次运行记录（损坏行 {broken}）; {note}")
        print("口径：命中 0 次且运行次数达标者只降频不改 CI 阻塞语义；处置结论需人工复核后落 scripts-reference.md。")
    sys.exit(0)


if __name__ == "__main__":
    main()
