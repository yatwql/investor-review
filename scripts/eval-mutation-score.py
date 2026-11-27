#!/usr/bin/env python3
"""变异得分离线评测（`eval-` 域：不进提交/发布门禁）。

行覆盖率证明「用例执行过这行代码」，不证明「断言住了这行代码的行为」——恒真断言、
自证用例、弱 mock 断言在接近满格的覆盖率下照样存活。本脚本用变异得分作为**测试有效性
指标**：按目标切片逐点注入变异，再跑该切片的相关测试，统计

    变异得分 = killed / (killed + survived)

逐目标与阈值比较：全部达标退出 0，任一低于阈值（或得分算不出）退出 2。

**后端**：默认 `builtin`——脚本自带的**有界变异器**（AST 定位 + 单点文本替换，四类算子：
比较取反 / 布尔取反 / 算术替换 / 返回值替换），**无任何外部依赖**。`--backend mutmut` 保留
为可选后端，但需要 3.x 兼容配置（`[tool.mutmut]` 声明路径与测试命令、关掉它在 `mutants/`
子目录里的裸 `pytest`）才真能跑，缺配置时表现是 `collected 0 items`，故不作默认。

**为什么是离线评测、不进提交门禁**：单个切片要反复重跑被测用例集（每变异体一次 pytest，
单切片分钟量级），且可选后端 mutmut 不在 `requirements.txt` 里——提交门禁必须短而决定性。
故本脚本只在「测试质量自省」时按需人工跑，`eval-` 域脚本一律不进守护清单。

**安全协议**（内置变异器改的是真实源码，故四层兜底，实现见 `_eval_mutation/runner.py`）：
工作树脏即拒跑 / 字节级备份 + `finally` 还原 + sha256 校验 / `atexit` 兜底（Ctrl-C 也不留
脏文件）/ 子进程 `-B` 且 `PYTHONDONTWRITEBYTECODE=1`（变异源码绝不写 `.pyc`）。

用法：
  .venv/bin/python scripts/eval-mutation-score.py --list-targets   # 目标清单（不依赖后端）
  .venv/bin/python scripts/eval-mutation-score.py --dry            # 只打印执行计划
  .venv/bin/python scripts/eval-mutation-score.py                  # 实跑全部切片并判定
  .venv/bin/python scripts/eval-mutation-score.py --only core-dates -v
  .venv/bin/python scripts/eval-mutation-score.py --max-mutants 30 --timeout 60
  .venv/bin/python scripts/eval-mutation-score.py --json           # 机读结果
  .venv/bin/python scripts/eval-mutation-score.py --ci             # 仅输出 文件:描述（未达标各一行）

退出码：
  0 — 全部目标得分达标（`--list-targets` / `--dry` 亦返回本码）
  1 — `--backend mutmut` 但后端未安装（环境缺失，已打印安装命令；内置后端不会返回本码）
  2 — 存在低于阈值或无法解析得分的目标；工作树脏（拒跑）；切片名未匹配；还原校验失败
  130 — 用户中断（Ctrl-C），原文件已还原
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ── 项目路径（脚本独立运行：先把仓库根与 scripts/ 加入 sys.path 以引用内部包） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
for _path in (str(_PROJECT_ROOT), str(_SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from _eval_mutation.mutmut_backend import (
    BACKEND_MODULE,
    INSTALL_COMMAND,
    backend_available,
    parse_counts,
)
from _eval_mutation.mutmut_backend import mutmut_command as backend_command
from _eval_mutation.operators import (  # noqa: F401  门面 re-export
    OPERATOR_ARITH,
    OPERATOR_BOOL,
    OPERATOR_COMPARE,
    OPERATOR_RETURN,
    Mutant,
    iter_mutants,
)
from _eval_mutation.results import MutantOutcome, MutationCounts
from _eval_mutation.runner import (
    RestoreError,
    collect_mutants,
    dirty_paths,
    mutation_paths,
    run_slice,
    test_command,
)
from _eval_mutation.targets import (
    BACKEND_BUILTIN,
    BACKEND_MUTMUT,
    DEFAULT_JOBS,
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MUTANT_TIMEOUT,
    DEFAULT_SLICE_TIMEOUT,
    DEFAULT_THRESHOLD,
    OPERATORS,
    MutationTarget,
    TARGETS,
)
from _shared.checklib import REPO_ROOT, add_common_args

#: 判定三态（passed = 达标，below = 低于阈值，no-data = 算不出得分）
STATUS_PASSED = "passed"
STATUS_BELOW = "below"
STATUS_NO_DATA = "no-data"


@dataclass(frozen=True)
class TargetResult:
    """单个目标切片的评测结果（`note` 记录口径信息，`survivors` 供 `-v` 逐条判读）。"""

    target: MutationTarget
    counts: MutationCounts | None
    note: str = ""
    survivors: tuple[MutantOutcome, ...] = ()


def evaluate_target(target: MutationTarget, *, timeout: int = DEFAULT_SLICE_TIMEOUT) -> TargetResult:
    """跑一个切片（`--backend mutmut`）并解析结果（超时/启动失败收敛为「无数据」）。"""
    try:
        completed = subprocess.run(
            backend_command(target),
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TargetResult(target=target, counts=None, note=f"后端超时（>{timeout}s）")
    except OSError as exc:
        return TargetResult(target=target, counts=None, note=f"后端启动失败：{exc}")
    output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    counts = parse_counts(output)
    note = "" if counts is not None else f"后端退出码 {completed.returncode}，输出中无 killed/survived 计数"
    return TargetResult(target=target, counts=counts, note=note)


def evaluate_builtin(
    target: MutationTarget,
    *,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    mutant_timeout: int = DEFAULT_MUTANT_TIMEOUT,
    slice_timeout: int = DEFAULT_SLICE_TIMEOUT,
    jobs: int = DEFAULT_JOBS,
) -> TargetResult:
    """用内置变异器跑一个切片（`RestoreError` 不吞：还原失败必须立刻中止整轮）。"""
    outcome = run_slice(
        target,
        max_mutants=max_mutants,
        mutant_timeout=mutant_timeout,
        slice_timeout=slice_timeout,
        jobs=jobs,
    )
    return TargetResult(
        target=target,
        counts=outcome.counts,
        note="；".join(outcome.notes),
        survivors=outcome.survivors,
    )


def score_of(result: TargetResult) -> float | None:
    """目标切片的变异得分（百分比）；无数据时 None。"""
    return None if result.counts is None else result.counts.score


def status_of(result: TargetResult, threshold: int) -> str:
    """判定三态：passed（达标）/ below（低于阈值）/ no-data（算不出得分）。"""
    score = score_of(result)
    if score is None:
        return STATUS_NO_DATA
    return STATUS_PASSED if score >= threshold else STATUS_BELOW


def finding_of(result: TargetResult, threshold: int) -> str:
    """未达标目标的 `文件:描述` 文本（`--ci` 与失败汇总共用）。"""
    files = ",".join(result.target.paths)
    counts = result.counts
    if counts is None or counts.score is None:
        return f"{files}:无法解析变异得分（{result.note or '后端无输出'}），须人工核对后端输出"
    return f"{files}:变异得分 {counts.score:.1f}% 低于阈值 {threshold}%（killed {counts.killed} / survived {counts.survived}）"


def overall_score(results: list[TargetResult]) -> float | None:
    """总体变异得分：各切片 killed 之和 ÷（killed + survived）之和（按变异体加权，不取平均）。"""
    killed = sum(result.counts.killed for result in results if result.counts is not None)
    survived = sum(result.counts.survived for result in results if result.counts is not None)
    total = killed + survived
    return None if total == 0 else killed * 100.0 / total


def _format_score(score: float | None) -> str:
    """得分文案（无数据时如实说无数据，不落成 0.0%）。"""
    return "无数据" if score is None else f"{score:.1f}%"


def _counts_extra(counts: MutationCounts) -> str:
    """`-v` 明细行里的「执行规模 + 未计入分母的变异体」后缀。"""
    parts: list[str] = []
    if counts.generated is not None and counts.executed is not None:
        parts.append(f"生成 {counts.generated} / 执行 {counts.executed}")
    if counts.timed_out:
        parts.append(f"timeout {counts.timed_out}")
    if counts.errored:
        parts.append(f"error {counts.errored}")
    return f"（{' / '.join(parts)}）" if parts else ""


def _detail_line(result: TargetResult, threshold: int) -> str:
    """`-v` 的逐目标明细行。"""
    counts = result.counts
    if counts is None or counts.score is None:
        return f"[ERR] {result.target.name}：{_format_score(None)}（{result.note}）"
    mark = "[OK]" if counts.score >= threshold else "[ERR]"
    extra = _counts_extra(counts)
    return f"{mark} {result.target.name}：{counts.score:.1f}%（killed {counts.killed} / survived {counts.survived}）{extra}"


def _survivor_lines(result: TargetResult) -> list[str]:
    """`-v` 的存活变异体明细（逐条人工判读：等价变异 vs 测试没断言住）。"""
    lines = [f"      survived {outcome.mutant.label}" for outcome in result.survivors]
    if lines:
        lines.append(f"      （{result.target.name} 共 {len(lines)} 个存活变异体，逐条判读等价性与漏测面）")
    if result.note:
        lines.append(f"      note: {result.note}")
    return lines


def _target_payload(result: TargetResult, threshold: int) -> dict[str, object]:
    """单个目标的机读表示。"""
    score = score_of(result)
    counts = result.counts
    return {
        "name": result.target.name,
        "paths": list(result.target.paths),
        "tests": list(result.target.tests),
        "operators": list(result.target.operators),
        "killed": None if counts is None else counts.killed,
        "survived": None if counts is None else counts.survived,
        "timed_out": None if counts is None else counts.timed_out,
        "errored": None if counts is None else counts.errored,
        "generated": None if counts is None else counts.generated,
        "executed": None if counts is None else counts.executed,
        "score": None if score is None else round(score, 4),
        "status": status_of(result, threshold),
        "note": result.note,
        "survivors": [
            {"label": outcome.mutant.label, "operator": outcome.mutant.operator} for outcome in result.survivors
        ],
    }


def _print_targets(targets: list[MutationTarget], *, as_json: bool) -> int:
    """`--list-targets`：目标清单（纯配置读取，不依赖后端）。"""
    if as_json:
        payload = {
            "backend": BACKEND_BUILTIN,
            "operators": list(OPERATORS),
            "targets": [
                {
                    "name": target.name,
                    "paths": list(target.paths),
                    "tests": list(target.tests),
                    "operators": list(target.operators),
                    "rationale": target.rationale,
                }
                for target in targets
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"[..] 变异评测目标：{len(targets)} 个切片；算子口径：{' / '.join(OPERATORS)}")
    for target in targets:
        print(f"  - {target.name}: {','.join(target.paths)}")
        print(f"      测试选择: {', '.join(target.tests)}")
        print(f"      {target.rationale}")
    print(f"[..] 默认后端 {BACKEND_BUILTIN}（内置有界变异器，无额外依赖）；实跑默认阈值 {DEFAULT_THRESHOLD}%")
    return 0


def _print_plan(targets: list[MutationTarget], args: argparse.Namespace) -> int:
    """`--dry`：只解析目标与配置并打印执行计划（不写任何文件、不起任何子进程）。"""
    plan: list[dict[str, object]] = []
    for target in targets:
        entry: dict[str, object] = {
            "name": target.name,
            "paths": list(target.paths),
            "tests": list(target.tests),
            "backend": args.backend,
        }
        if args.backend == BACKEND_BUILTIN:
            mutants, notes = collect_mutants(target)
            entry["mutants"] = min(len(mutants), args.max_mutants)
            entry["generated"] = len(mutants)
            entry["command"] = test_command(target, python_executable=sys.executable)
            entry["notes"] = notes
        else:
            entry["command"] = backend_command(target)
            entry["generated"] = None
            entry["mutants"] = None
            entry["notes"] = []
        plan.append(entry)

    if args.json:
        print(
            json.dumps(
                {
                    "backend": args.backend,
                    "threshold": args.threshold,
                    "max_mutants": args.max_mutants,
                    "mutant_timeout": args.timeout,
                    "slice_timeout": args.slice_timeout,
                    "jobs": args.jobs,
                    "cwd": str(REPO_ROOT),
                    "slices": plan,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(
        f"[..] 干跑（不写文件、不起子进程）：{len(plan)} 个切片，后端 {args.backend}，"
        f"阈值 {args.threshold}%，单变异体超时 {args.timeout}s，变异体上限 {args.max_mutants}/切片"
    )
    for item in plan:
        print(f"  {item['name']}: 变异体 {item['mutants']}（生成 {item['generated']}）")
        print(f"      测试选择: {', '.join(item['tests'])}")  # type: ignore[arg-type]
        print(f"      命令: {' '.join(str(part) for part in item['command'])}")  # type: ignore[union-attr]
        for note in item["notes"]:  # type: ignore[union-attr]
            print(f"      note: {note}")
    print(f"[..] 工作目录 {REPO_ROOT}；子进程 text=True 且显式 encoding=utf-8")
    return 0


def _report(
    results: list[TargetResult], *, threshold: int, verbose: bool, ci: bool, as_json: bool, backend: str
) -> int:
    """汇总输出与退出码（0 = 全达标，2 = 有未达标/无数据目标）。"""
    score = overall_score(results)
    findings = [finding_of(result, threshold) for result in results if status_of(result, threshold) != STATUS_PASSED]

    if as_json:
        payload = {
            "backend": backend,
            "threshold": threshold,
            "score": None if score is None else round(score, 4),
            "ok": not findings,
            "exit_code": 2 if findings else 0,
            "targets": [_target_payload(result, threshold) for result in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2 if findings else 0

    if ci:
        for finding in findings:
            print(finding)
        return 2 if findings else 0

    if verbose:
        for result in results:
            print(_detail_line(result, threshold))
            for line in _survivor_lines(result):
                print(line)
    if findings:
        for finding in findings:
            print(f"[ERR] {finding}")
        print(
            f"[!] {len(findings)} 个目标未达阈值 {threshold}%（总体变异得分 {_format_score(score)}），须补强断言而非补行"
        )
        return 2
    print(f"[OK] 变异得分 {_format_score(score)}（阈值 {threshold}%，{len(results)} 个目标全部达标）")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="变异得分离线评测（内置有界变异器逐点注入，不进提交门禁）")
    add_common_args(parser)
    parser.add_argument("--list-targets", action="store_true", help="打印本期变异目标清单（不依赖后端）")
    parser.add_argument("--dry", action="store_true", help="只解析目标与配置、打印执行计划（不写文件）")
    parser.add_argument(
        "--backend",
        choices=(BACKEND_BUILTIN, BACKEND_MUTMUT),
        default=BACKEND_BUILTIN,
        help="变异后端：builtin = 内置有界变异器（默认）；mutmut = 可选后端，需 3.x 兼容配置",
    )
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="只跑指定切片（可重复）")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="变异得分阈值（百分比）")
    parser.add_argument(
        "--max-mutants", type=int, default=DEFAULT_MAX_MUTANTS, help="单切片变异体上限（默认 60，防无界耗时）"
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_MUTANT_TIMEOUT, help="单变异体超时（秒，默认 180，超即记 timeout）"
    )
    parser.add_argument(
        "--slice-timeout",
        type=int,
        default=DEFAULT_SLICE_TIMEOUT,
        help="单切片总时限（秒，默认 1800；到点即停，未执行的不计入分母）",
    )
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS, help="并行度（默认 1 串行；>1 时按文件互斥）")
    parser.add_argument("--json", action="store_true", help="输出机读结果")
    return parser.parse_args(argv)


def _select_targets(only: list[str]) -> list[MutationTarget]:
    """按 `--only` 过滤切片（空即全部）。"""
    if not only:
        return list(TARGETS)
    return [target for target in TARGETS if target.name in set(only)]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    targets = _select_targets(args.only)

    if args.list_targets:
        return _print_targets(targets, as_json=args.json)
    if not targets:
        print(f"[ERR] --only 未匹配任何切片：{', '.join(args.only)}")
        print(f"[..] 可选切片：{', '.join(target.name for target in TARGETS)}")
        return 2
    if args.dry:
        return _print_plan(targets, args)

    if args.backend == BACKEND_MUTMUT:
        if not backend_available():
            print(f"[ERR] 未安装变异评测后端 {BACKEND_MODULE}（可选工具，未写入 requirements.txt）")
            print(f"[..] 安装：{INSTALL_COMMAND}")
            print("[..] 未开始评测，也没有产生任何 finding——这属环境缺失，不是测试质量问题")
            print(f"[..] 无外部依赖的默认后端是 {BACKEND_BUILTIN}（去掉 --backend 即可）")
            return 1
        results = [evaluate_target(target, timeout=args.slice_timeout) for target in targets]
        return _report(
            results, threshold=args.threshold, verbose=args.verbose, ci=args.ci, as_json=args.json, backend=args.backend
        )

    dirty = dirty_paths(mutation_paths(targets))
    if dirty:
        print("[ERR] 工作树在切片路径上有未提交改动，变异会覆盖你的编辑——已拒跑：")
        for line in dirty:
            print(f"  {line}")
        print("[..] 先提交或 `git stash` 后再跑；确认无误时可在干净副本上评测")
        return 2

    try:
        results: list[TargetResult] = []
        for target in targets:
            if not (args.ci or args.json):
                mutants, _ = collect_mutants(target)
                print(
                    f"[..] {target.name}：生成 {len(mutants)} 个变异体，执行前 {min(len(mutants), args.max_mutants)} 个"
                )
            results.append(
                evaluate_builtin(
                    target,
                    max_mutants=args.max_mutants,
                    mutant_timeout=args.timeout,
                    slice_timeout=args.slice_timeout,
                    jobs=args.jobs,
                )
            )
    except RestoreError as exc:
        print(f"[ERR] {exc}")
        return 2
    except KeyboardInterrupt:
        print("[!] 已中断（Ctrl-C）：变异过的源文件已按备份还原")
        return 130

    return _report(
        results, threshold=args.threshold, verbose=args.verbose, ci=args.ci, as_json=args.json, backend=args.backend
    )


if __name__ == "__main__":
    sys.exit(main())
