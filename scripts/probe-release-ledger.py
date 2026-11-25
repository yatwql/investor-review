#!/usr/bin/env python3
"""发布台账按版本汇总 —— 读 `logs/release.jsonl`，输出「每版发布 × 墙钟 × 分步耗时 × token 增量 × 失败步」。

用途（非门禁）：台账本身是 append-only 的第一现场记录（每命令一行，含失败步与输出尾部），
`session_usage` 是**agent 会话级累加值**（跨发布、跨会话）。因此「这一版发布花了多少墙钟 /
多少 token」不能直接读某一行，而要按发布边界切段后**对相邻行取增量**——本脚本只做这件事，
不改台账写入路径、不动任何发布步骤。

切段口径：`version` 去掉 `-dev` 后的基号即所属台账版本（`X.Y.Z-dev` 的 check/prepare 与
`X.Y.Z` 的 publish 同属一版）；同一基号按时间聚合，相邻批次不会互相串账。
token 增量：同一 `agent.session_id` 内取 `session_usage.total` 的前后差（新会话首行记 0，
避免把上一会话的累计算进本版）。

用法：
  python scripts/probe-release-ledger.py                     # 最近 3 版
  python scripts/probe-release-ledger.py --last 10           # 最近 10 版
  python scripts/probe-release-ledger.py --version X.Y.Z     # 只看某一版（可重复）
  python scripts/probe-release-ledger.py --ledger /tmp/x.jsonl
  python scripts/probe-release-ledger.py -v                  # 逐命令/逐步骤明细
  python scripts/probe-release-ledger.py --ci                # 仅输出表格行（不含说明段）
  python scripts/probe-release-ledger.py --json              # 机器可读

`--ci` 与检查脚本的公共口径不同：只隐去说明段，不改变表格/JSON 内容，也**不以退出码 2
表达任何 finding**（本脚本不是门禁，它汇总的「失败步」是台账事实，不是本脚本的判断）。

退出码：
  0 — 汇总已输出（本脚本不是门禁，失败步只影响台账统计，不影响退出码）
  1 — 台账不可读（路径存在但权限不足/无法打开）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 共享设施包（_shared/checklib）
from _shared.checklib import REPO_ROOT  # noqa: E402

DEFAULT_LEDGER = REPO_ROOT / "logs" / "release.jsonl"


def _load(ledger: Path) -> list[dict]:
    """读台账；文件不存在视为空（首次使用），单行损坏跳过。"""
    if not ledger.exists():
        return []
    records: list[dict] = []
    text = ledger.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("command"):
            records.append(record)
    return records


def _as_float(value: object) -> float:
    """台账里的耗时字段容错转 float（缺失/非数值一律记 0，不让脏行打断汇总）。"""
    try:
        return float(value)  # type: ignore[arg-type]  # 台账字段可能是字符串（手写/外部写入）
    except (TypeError, ValueError):
        return 0.0


def _base_version(record: dict) -> str:
    """所属台账版本：去掉 `-dev` 后缀的基号。"""
    return str(record.get("version") or "").removesuffix("-dev")


def _session_total(record: dict) -> tuple[str, int] | None:
    """``(session_id, 会话累计 total)``；缺字段返回 None。"""
    usage = record.get("session_usage")
    agent = record.get("agent")
    if not isinstance(usage, dict) or not isinstance(agent, dict):
        return None
    total = usage.get("total")
    session = agent.get("session_id")
    if not isinstance(total, (int, float)) or not isinstance(session, str):
        return None
    return session, int(total)


def summarize(records: list[dict]) -> list[dict]:
    """按台账版本聚合，返回按首次出现时间排序的摘要列表。"""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for record in records:
        version = _base_version(record)
        if not version:
            continue
        if version not in groups:
            groups[version] = []
            order.append(version)
        groups[version].append(record)

    out: list[dict] = []
    last_seen: dict[str, int] = {}  # session_id → 上一行会话累计
    for record in records:  # token 增量必须按全局时间序推进
        key = _session_total(record)
        if key is None:
            continue
        session, total = key
        prev = last_seen.get(session)
        record["_token_delta"] = total - prev if prev is not None and total >= prev else 0
        last_seen[session] = total

    for version in order:
        rows = groups[version]
        steps: dict[str, float] = defaultdict(float)
        failures: list[dict] = []
        tokens = 0
        for row in rows:
            tokens += int(row.get("_token_delta") or 0)
            for step in row.get("steps") or []:
                if isinstance(step, dict) and step.get("step"):
                    steps[str(step["step"])] += _as_float(step.get("elapsed_s"))
            if not row.get("ok", True):
                failures.append({"command": row.get("command"), "failure": row.get("failure")})
        out.append(
            {
                "version": version,
                "published": any(row.get("command") == "publish" and row.get("ok") for row in rows),
                "commands": [str(row.get("command")) for row in rows],
                "wall_seconds": round(sum(_as_float(row.get("elapsed_s")) for row in rows), 2),
                "first_ts": str(rows[0].get("ts") or ""),
                "last_ts": str(rows[-1].get("ts") or ""),
                "steps": {k: round(v, 2) for k, v in steps.items()},
                "tokens": tokens,
                "failures": failures,
                "records": rows,
            }
        )
    return out


def _clip(text: str, width: int) -> str:
    """过长的步骤名截断（终端表格对齐优先，完整名见 `-v`）。"""
    return text if len(text) <= width else text[: width - 1] + "…"


def _format_table(items: list[dict], verbose: bool) -> list[str]:
    """表格行：(版本 | 已发布 | 命令数 | 墙钟 | token | 最耗时步 | 失败步)。"""
    lines = ["版本      发布  命令  墙钟s   token(会话增量)  最耗时步(截断)     失败步"]
    for item in items:
        slow = max(item["steps"].items(), key=lambda kv: kv[1], default=("-", 0.0))
        slow_label = f"{_clip(slow[0], 12)} {slow[1]:.1f}s"
        failed = "、".join(str(f["command"]) for f in item["failures"]) or "—"
        lines.append(
            f"{item['version']:<9} {'是' if item['published'] else '否':<4} {len(item['commands']):<4} "
            f"{item['wall_seconds']:<6.1f} {item['tokens']:<15} {slow_label:<19} {failed}"
        )
        if verbose:
            for command, seconds in zip(item["commands"], _command_seconds(item["records"])):
                lines.append(f"    · {command:<10} {seconds:>7.2f}s")
            for step, seconds in sorted(item["steps"].items(), key=lambda kv: -kv[1]):
                lines.append(f"    - {step}: {seconds:.2f}s")
    return lines


def _command_seconds(records: list[dict]) -> list[float]:
    return [_as_float(row.get("elapsed_s")) for row in records]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布台账按版本汇总（只读，非门禁）")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="台账路径（默认 logs/release.jsonl）")
    parser.add_argument("--last", type=int, default=3, help="只看最近 N 版（默认 3；0 = 全部）")
    parser.add_argument(
        "--version",
        action="append",
        default=[],
        help="只看指定版本（基号，可重复；与 --last 互斥，给了就忽略 --last）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON（机器可读）")
    # 本脚本不是门禁：`--ci` 只隐去说明段（表格/JSON 内容不变），退出码恒为 0（台账不可读才是 1）；
    # 故不复用检查脚本的公共 `--ci`（那个口径是「仅输出 文件:描述，发现即退出 2」）。
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出（逐命令与逐步骤明细）")
    parser.add_argument("--ci", action="store_true", help="只输出表格行（略去说明段；本脚本非门禁，恒退出 0）")
    args = parser.parse_args(argv)

    ledger = Path(args.ledger)
    try:
        records = _load(ledger)
    except OSError as exc:
        print(f"[ERR] 台账不可读：{exc}", file=sys.stderr)
        return 1

    items = summarize(records)
    if args.version:
        wanted = set(args.version)
        items = [item for item in items if item["version"] in wanted]
    elif args.last > 0:
        items = items[-args.last :]

    if args.json:
        payload = [{k: v for k, v in item.items() if k != "records"} for item in items]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not items:
        print("[!] 台账内没有可汇总的发布记录" if not args.ci else "")
        return 0

    lines = _format_table(items, verbose=bool(args.verbose))
    for line in lines:
        print(line)
    if not args.ci:
        print(
            "\n注：token 列为**相邻台账行之间的 agent 会话累计增量**（含期间的全部对话与改码），"
            "不是发布命令本身的成本口径。"
        )
        if args.verbose:
            print(f"[OK] 共 {len(items)} 版；台账 {len(records)} 行（{ledger}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
