#!/usr/bin/env python3
"""时间炸弹探测（date bomb probe）——「测试写死绝对日期会不会随墙钟腐化」的经验筛查。

做法（变异筛查）：把候选测试文件里的绝对日期整体回移 N 年，再逐个跑 pytest 看是否失败。
失败即意味着该用例要求「日期处于近期（相对 now）」——这正是墙上时钟走过去的效果。

为什么是 probe 而不是 check：
- 本工具要**临时改写真实测试文件**再跑（非纯静态），单文件秒级、全集分钟级，不适合入门禁；
- 静态窄口径守卫见 `check-test-redundancy.py` 的 I 类（账本类调用的日期实参）；
- probe- 前缀属探测类活动，不进十守护、不进 CI，按需运行。

安全约定（改写真实文件是唯一风险点，故三层兜底）：
1. 只处理 git 工作区干净的文件（脏文件一律跳过，除 `--allow-dirty`）；
2. 改写前备份原文到临时目录，`finally` 还原并校验 sha256 与原文一致；
3. 进程异常退出时由 `atexit` 兜底还原（Ctrl-C / 用例崩溃都不会留下脏文件）。

判读要求：rot-suspect ≠ 缺陷。常见变异伪信号——生产侧显式注入 today 参数、星期/财季语义
随日期位移改变、断言目标在未被替换的 fixture 模块里。必须人工过一遍再动手改。

用法：
  python scripts/probe-date-bombs.py                    # 默认候选：含保留期/TTL 关键词的测试文件
  python scripts/probe-date-bombs.py --all              # 所有含绝对日期的测试文件（慢）
  python scripts/probe-date-bombs.py --years 3          # 回移年数（默认 3）
  python scripts/probe-date-bombs.py --files a.py b.py  # 只跑指定文件
  python scripts/probe-date-bombs.py -v                 # 打印每个文件的判定与失败用例
  python scripts/probe-date-bombs.py --ci               # 仅输出 文件:描述，有 suspect 即退出码 2

退出码：
  0 — 本次探测范围内无 rot-suspect（或全部跳过）
  2 — 发现 rot-suspect / 变异后跑测试超时（需人工判读，非缺陷确认）
  注：本工具**不入门禁**（probe- 前缀：探测类，要改写测试文件并真跑 pytest）；静态窄口径
  守卫是 `check-test-redundancy.py` 的 I 类 `check_ledger_absolute_dates`。
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

# 脚本与实现包同名不同层：把 scripts/ 放进 sys.path 以复用统一 CLI 契约
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _shared.checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402

_TEST_ROOT = REPO_ROOT / "src" / "test"

#: 绝对日期字面量：匹配 `"2026-09-01"` 与 `datetime(2026, 9, 1)` 两种写法。
_STR_DATE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
_TUPLE_DATE = re.compile(r"(20\d{2}),\s*(\d{1,2}),\s*(\d{1,2})(?=[),])")

#: 默认候选筛子：与「按 now() 判定窗口」相关关键词同现，才可能腐化。
_RETENTION_HINTS = re.compile(
    r"retention|_ttl\b|cutoff|expired|stale|within_window|retention_days|HISTORY_SNAPSHOT_RETENTION"
)

#: 待还原文件登记表：{路径: (原文, sha256)}，供 finally 与 atexit 双保险还原。
_PENDING_RESTORE: dict[Path, tuple[str, str]] = {}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _restore_all() -> None:
    """把登记表里的文件还原为原文（幂等，异常路径兜底）。"""
    for path, (original, digest) in list(_PENDING_RESTORE.items()):
        try:
            path.write_text(original, encoding="utf-8")
        except OSError:
            continue
        finally:
            _PENDING_RESTORE.pop(path, None)
        if _digest(path.read_text(encoding="utf-8")) != digest:
            print(f"[ERR] 还原校验失败，请人工检查：{path}")


atexit.register(_restore_all)


def mutate_dates(text: str, years: int = 3) -> str:
    """把所有绝对日期整体回移 `years` 年（年-月-日与 (年, 月, 日) 两种写法）。"""

    def _shift_str(match: re.Match[str]) -> str:
        return f"{int(match.group(1)) - years:04d}-{match.group(2)}-{match.group(3)}"

    def _shift_tuple(match: re.Match[str]) -> str:
        return f"{int(match.group(1)) - years:04d}, {match.group(2)}, {match.group(3)}"

    return _TUPLE_DATE.sub(_shift_tuple, _STR_DATE.sub(_shift_str, text))


def _has_absolute_date(text: str) -> bool:
    return bool(_STR_DATE.search(text) or _TUPLE_DATE.search(text))


def candidate_files(scan_all: bool = False) -> list[Path]:
    """候选测试文件：含绝对日期，且（默认）与保留期/TTL 类关键词同现。"""
    files: list[Path] = []
    for path in sorted(_TEST_ROOT.rglob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _has_absolute_date(text):
            continue
        if scan_all or _RETENTION_HINTS.search(text):
            files.append(path)
    return files


def _git_dirty(path: Path) -> bool:
    """该文件在工作区是否有未提交改动（脏文件不动，避免覆盖用户编辑）。"""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return True  # 判不出就当脏：宁可不测，不冒险
    return bool(proc.stdout.strip())


def probe_file(path: Path, years: int, timeout: int, python: str) -> dict:
    """单文件变异筛查：改写 → 跑 pytest → 还原，返回 {status, fails, summary}。"""
    original = path.read_text(encoding="utf-8")
    mutated = mutate_dates(original, years)
    if mutated == original:
        return {"status": "no-literal", "fails": [], "summary": ""}
    _PENDING_RESTORE[path] = (original, _digest(original))
    try:
        path.write_text(mutated, encoding="utf-8")
        proc = subprocess.run(
            [python, "-m", "pytest", rel(path), "-q", "-p", "no:cacheprovider", "--tb=no"],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
            timeout=timeout,
        )
        out = f"{proc.stdout}\n{proc.stderr}"
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "fails": [], "summary": f"超时（>{timeout}s）"}
    finally:
        _restore_all()

    fails = sorted({line.split("::", 1)[-1].split(" ")[0] for line in out.splitlines() if line.startswith("FAILED")})
    errors = [line for line in out.splitlines() if line.startswith("ERROR")]
    summary = next(
        (line.strip() for line in reversed(out.splitlines()) if re.search(r"\d+ (passed|failed|error)", line)), ""
    )
    status = "rot" if fails or errors else "ok"
    if errors:
        summary = f"{summary} / 收集期错误 {len(errors)} 处"
    return {"status": status, "fails": fails, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="时间炸弹探测：回移绝对日期后跑测试，找出依赖「日期处于近期」的用例")
    add_common_args(parser)
    parser.add_argument("--files", nargs="+", default=None, help="只探测指定测试文件（路径相对仓库根）")
    parser.add_argument("--all", action="store_true", help="探测所有含绝对日期的测试文件（默认只查保留期/TTL 相关）")
    parser.add_argument("--years", type=int, default=3, help="日期回移年数（默认 3）")
    parser.add_argument("--timeout", type=int, default=600, help="单文件 pytest 超时秒数（默认 600）")
    parser.add_argument("--python", default=sys.executable, help="跑 pytest 的解释器（默认当前解释器）")
    parser.add_argument("--allow-dirty", action="store_true", help="允许改写有未提交改动的文件（默认跳过）")
    parser.add_argument("--dry-run", action="store_true", help="只列出候选与命中数，不改写不跑测试")
    args = parser.parse_args()

    targets = [REPO_ROOT / name for name in args.files] if args.files else candidate_files(scan_all=args.all)

    if args.dry_run:
        print(f"[..] 候选测试文件 {len(targets)} 个（回移 {args.years} 年）：")
        for path in targets:
            print(f"  {rel(path)}")
        return

    findings: list[str] = []
    counts = {"ok": 0, "rot": 0, "skipped": 0, "timeout": 0}
    for path in targets:
        if not path.is_file():
            counts["skipped"] += 1
            print(f"[!] 跳过（文件不存在）：{rel(path)}")
            continue
        if not args.allow_dirty and _git_dirty(path):
            counts["skipped"] += 1
            if args.verbose:
                print(f"[!] 跳过（工作区有未提交改动，--allow-dirty 可强制）：{rel(path)}")
            continue
        result = probe_file(path, args.years, args.timeout, args.python)
        if result["status"] == "timeout":
            counts["timeout"] += 1
            findings.append(f"{rel(path)}: 变异后跑测试超时（{result['summary']}）")
            continue
        if result["status"] == "rot":
            counts["rot"] += 1
            detail = "、".join(result["fails"][:4]) + ("…" if len(result["fails"]) > 4 else "")
            findings.append(f"{rel(path)}: rot-suspect（{result['summary']}）{detail}")
            continue
        counts["ok"] += 1
        if args.verbose:
            print(f"[OK] {rel(path)} — {result['summary'] or '变异后仍全绿'}")

    if args.verbose or counts["skipped"]:
        print(
            f"  探测文件 通过 {counts['ok']} / rot-suspect {counts['rot']} /"
            f" 跳过 {counts['skipped']} / 超时 {counts['timeout']}（回移 {args.years} 年）"
        )
    print(
        "  判读提醒：rot-suspect ≠ 缺陷——生产侧显式注入 today、星期/财季语义、"
        "断言目标在未变异的 fixture 模块里，都会造成变异伪信号，需人工过一遍"
    )
    sys.exit(
        report(
            findings,
            "[OK] 未发现依赖「日期处于近期」的用例（本次探测范围内）",
            ci=args.ci,
            fail_message="[!] 发现 {n} 处 rot-suspect，须人工判读后修正或登记",
        )
    )


if __name__ == "__main__":
    main()
