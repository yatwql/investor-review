#!/usr/bin/env python3
"""变异得分离线评测（`eval-` 域：不进提交/发布门禁）。

行覆盖率证明「用例执行过这行代码」，不证明「断言住了这行代码的行为」——恒真断言、
自证用例、弱 mock 断言在接近满格的覆盖率下照样存活。本脚本用变异得分作为**测试有效性
指标**：按目标切片委托后端 `mutmut` 逐块注入变异，解析其输出统计

    变异得分 = killed / (killed + survived)

逐目标与阈值比较：全部达标退出 0，任一低于阈值（或得分解析不出）退出 2。

**为什么是离线评测、不进提交门禁**：单个切片要反复重跑被测用例集，时长以分钟计；
且 `mutmut` 是**可选工具**，刻意不写入 `requirements.txt`（提交门禁必须短而决定性，
不允许依赖可选工具与长尾耗时）。故本脚本只在「测试质量自省」时按需人工跑，`eval-`
域脚本一律不进守护清单。

**首期目标与算子口径**（配置集中在模块级 `TARGETS` / `OPERATORS`，改目标只改这张表）：
  - 目标：`analysis/metrics*.py`、`analysis/correlation.py`、`cache/`（TTL 与原子写）、
    `core/dates.py`——高杠杆的纯计算与基础设施，断言强度最值得盯，切片也足够小
  - 算子：算术替换 / 比较取反 / 布尔取反 / 返回值替换四类。mutmut 侧用其内置算子集，
    本表只记录**声明口径**；后端不提供算子筛选时按全量跑，差异如实体现在得分里
    （本脚本不擅自按算子过滤，也不回算分数）

用法：
  .venv/bin/python scripts/eval-mutation-score.py --list-targets   # 目标清单（不依赖后端）
  .venv/bin/python scripts/eval-mutation-score.py --dry            # 只打印将执行的后端命令
  .venv/bin/python scripts/eval-mutation-score.py                  # 实跑并判定（需 mutmut）
  .venv/bin/python scripts/eval-mutation-score.py -v               # 逐目标明细
  .venv/bin/python scripts/eval-mutation-score.py --json           # 机读结果
  .venv/bin/python scripts/eval-mutation-score.py --ci             # 仅输出 文件:描述（未达标目标各一行）
  .venv/bin/python scripts/eval-mutation-score.py --threshold 60   # 放宽阈值

退出码：
  0 — 全部目标得分达标（`--list-targets` / `--dry` 亦返回本码）
  1 — 后端 mutmut 未安装（环境缺失，已打印安装命令）
  2 — 存在低于阈值或无法解析得分的目标
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ── 项目路径（脚本独立运行：先把 scripts/ 加入 sys.path 以引用共享设施） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _shared.checklib import REPO_ROOT, add_common_args

#: 后端模块名（可选工具；未写入 requirements.txt，脚本负责给出安装提示）
BACKEND_MODULE = "mutmut"

#: 后端缺失时的安装提示（与项目虚拟环境口径一致）
INSTALL_COMMAND = ".venv/bin/python -m pip install mutmut（Windows：.venv\\Scripts\\python.exe -m pip install mutmut）"

#: 默认变异得分阈值（百分比）：killed / (killed + survived)
DEFAULT_THRESHOLD = 80

#: 单个目标切片的后端超时（秒）：含被测用例集反复重跑，远高于普通检查脚本
DEFAULT_TIMEOUT = 1800

#: 声明口径的变异算子集（mutmut 侧用其内置算子，本表只记录我们关心的四类）
OPERATORS: tuple[str, ...] = ("算术替换", "比较取反", "布尔取反", "返回值替换")

#: 判定三态（passed = 达标，below = 低于阈值，no-data = 解析不出得分）
STATUS_PASSED = "passed"
STATUS_BELOW = "below"
STATUS_NO_DATA = "no-data"


@dataclass(frozen=True)
class MutationTarget:
    """一个变异目标切片（= 一次后端调用的边界，逐切片跑避免一次全仓）。"""

    name: str
    paths: tuple[str, ...]
    rationale: str
    operators: tuple[str, ...] = OPERATORS


#: 首期变异目标清单（新增/调整目标只改这张表）
TARGETS: tuple[MutationTarget, ...] = (
    MutationTarget(
        name="analysis-metrics",
        paths=("src/python/analysis/metrics*.py",),
        rationale="指标计算全家桶（收益率/风险/派生）：纯算术，算术替换与返回值替换最能曝出弱断言",
    ),
    MutationTarget(
        name="analysis-correlation",
        paths=("src/python/analysis/correlation.py",),
        rationale="相关性计算：比较取反会翻转符号判定，断言只查范围而不查方向的用例在此暴露",
    ),
    MutationTarget(
        name="cache-ttl-atomic-write",
        paths=("src/python/cache/",),
        rationale="缓存 TTL 与原子写：边界比较（> / >=）与布尔取反决定过期与覆盖语义，最易漏测",
    ),
    MutationTarget(
        name="core-dates",
        paths=("src/python/core/dates.py",),
        rationale="交易日历与日期换算：比较取反与算术替换会错位日期边界，静默影响全仓取数窗口",
    ),
)


@dataclass(frozen=True)
class MutationCounts:
    """后端输出解析出的变异体计数。"""

    killed: int
    survived: int
    timed_out: int = 0
    suspicious: int = 0

    @property
    def evaluated(self) -> int:
        """参与得分的变异体数（超时/可疑不计入分母，与得分口径一致）。"""
        return self.killed + self.survived

    @property
    def score(self) -> float | None:
        """变异得分（百分比）；无参与得分的变异体时返回 None（不编造 0 分）。"""
        return None if self.evaluated == 0 else self.killed * 100.0 / self.evaluated


@dataclass(frozen=True)
class TargetResult:
    """单个目标切片的评测结果（`note` 记录无数据的原因，供 finding 文案如实说明）。"""

    target: MutationTarget
    counts: MutationCounts | None
    note: str = ""


#: mutmut 进度行：`3/40  🎉 2  ⏰ 0  🤔 0  🙁 1  🔇 0`
#: 依次为 killed / timeout / suspicious / survived / skipped，每行都是**累计值**
_PROGRESS_RE = re.compile(r"\d+/\d+\s+🎉\s*(\d+)\s+⏰\s*(\d+)\s+🤔\s*(\d+)\s+🙁\s*(\d+)\s+🔇\s*(\d+)")

#: 计数行备用口径：`killed: 12` / `survived = 3`（后端换输出格式或包装输出时仍可解析）
_KILLED_RE = re.compile(r"killed\s*[:=]\s*(\d+)", re.IGNORECASE)
_SURVIVED_RE = re.compile(r"survived\s*[:=]\s*(\d+)", re.IGNORECASE)


def _last_int(pattern: re.Pattern[str], text: str) -> int | None:
    """取最后一次匹配到的整数（多行刷新的输出以末行为准），无匹配返回 None。"""
    matches = pattern.findall(text)
    return int(matches[-1]) if matches else None


def parse_counts(output: str) -> MutationCounts | None:
    """从后端输出解析 killed / survived 计数；认不出时返回 None。

    优先取**最后一条** mutmut 进度行（行内是累计值，多行刷新时末行才是终态）；
    无进度行时退回 `killed:` / `survived:` 计数行（任一缺失即视为无数据）。
    """
    counts: MutationCounts | None = None
    for match in _PROGRESS_RE.finditer(output):
        counts = MutationCounts(
            killed=int(match.group(1)),
            timed_out=int(match.group(2)),
            suspicious=int(match.group(3)),
            survived=int(match.group(4)),
        )
    if counts is not None:
        return counts
    killed = _last_int(_KILLED_RE, output)
    survived = _last_int(_SURVIVED_RE, output)
    if killed is None or survived is None:
        return None
    return MutationCounts(killed=killed, survived=survived)


def backend_command(target: MutationTarget, *, python_executable: str | None = None) -> list[str]:
    """目标切片 → 后端命令行（同一解释器起 `-m mutmut`，按路径切片逐个跑）。"""
    executable = python_executable or sys.executable
    return [executable, "-m", BACKEND_MODULE, "run", f"--paths-to-mutate={','.join(target.paths)}"]


def backend_available(*, python_executable: str | None = None, timeout: int = 60) -> bool:
    """后端是否已安装（`-c "import mutmut"` 探测，不触发任何变异、不写任何文件）。"""
    executable = python_executable or sys.executable
    try:
        completed = subprocess.run(
            [executable, "-c", f"import {BACKEND_MODULE}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def evaluate_target(target: MutationTarget, *, timeout: int = DEFAULT_TIMEOUT) -> TargetResult:
    """跑一个目标切片并解析结果（超时/启动失败都收敛为「无数据」，由判定分支如实报出）。"""
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


def score_of(result: TargetResult) -> float | None:
    """目标切片的变异得分（百分比）；无数据时 None。"""
    return None if result.counts is None else result.counts.score


def status_of(result: TargetResult, threshold: int) -> str:
    """判定三态：passed（达标）/ below（低于阈值）/ no-data（解析不出得分）。"""
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


def _detail_line(result: TargetResult, threshold: int) -> str:
    """`-v` 的逐目标明细行。"""
    counts = result.counts
    if counts is None or counts.score is None:
        return f"[ERR] {result.target.name}：{_format_score(None)}（{result.note}）"
    mark = "[OK]" if counts.score >= threshold else "[ERR]"
    extra = ""
    if counts.timed_out or counts.suspicious:
        extra = f" / timeout {counts.timed_out} / suspicious {counts.suspicious}"
    return f"{mark} {result.target.name}：{counts.score:.1f}%（killed {counts.killed} / survived {counts.survived}{extra}）"


def _target_payload(result: TargetResult, threshold: int) -> dict[str, object]:
    """单个目标的机读表示。"""
    score = score_of(result)
    return {
        "name": result.target.name,
        "paths": list(result.target.paths),
        "operators": list(result.target.operators),
        "killed": None if result.counts is None else result.counts.killed,
        "survived": None if result.counts is None else result.counts.survived,
        "score": None if score is None else round(score, 4),
        "status": status_of(result, threshold),
        "note": result.note,
    }


def _print_targets(*, as_json: bool) -> int:
    """`--list-targets`：目标清单（纯配置读取，不依赖后端）。"""
    if as_json:
        payload = {
            "backend": BACKEND_MODULE,
            "operators": list(OPERATORS),
            "targets": [
                {
                    "name": target.name,
                    "paths": list(target.paths),
                    "operators": list(target.operators),
                    "rationale": target.rationale,
                }
                for target in TARGETS
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"[..] 变异评测目标：{len(TARGETS)} 个切片；算子口径：{' / '.join(OPERATORS)}")
    for target in TARGETS:
        print(f"  - {target.name}: {','.join(target.paths)}")
        print(f"      {target.rationale}")
    print(f"[..] 后端 {BACKEND_MODULE}（可选工具，未写入 requirements.txt）；实跑默认阈值 {DEFAULT_THRESHOLD}%")
    return 0


def _print_plan(threshold: int, timeout: int, *, as_json: bool) -> int:
    """`--dry`：只解析目标与配置并打印将执行的后端命令（不执行任何变异）。"""
    commands = [
        {"name": target.name, "paths": list(target.paths), "command": backend_command(target)} for target in TARGETS
    ]
    if as_json:
        payload = {
            "backend": BACKEND_MODULE,
            "threshold": threshold,
            "timeout": timeout,
            "cwd": str(REPO_ROOT),
            "commands": commands,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"[..] 干跑（不执行变异）：{len(commands)} 个目标切片，阈值 {threshold}%，单切片超时 {timeout}s")
    for item in commands:
        print(f"  {item['name']}: {' '.join(str(part) for part in item['command'])}")
    print(f"[..] 工作目录 {REPO_ROOT}；子进程 text=True 且显式 encoding=utf-8")
    return 0


def _report(results: list[TargetResult], *, threshold: int, verbose: bool, ci: bool, as_json: bool) -> int:
    """汇总输出与退出码（0 = 全达标，2 = 有未达标/无数据目标）。"""
    score = overall_score(results)
    findings = [finding_of(result, threshold) for result in results if status_of(result, threshold) != STATUS_PASSED]

    if as_json:
        payload = {
            "backend": BACKEND_MODULE,
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
    if findings:
        for finding in findings:
            print(f"[ERR] {finding}")
        print(
            f"[!] {len(findings)} 个目标未达阈值 {threshold}%（总体变异得分 {_format_score(score)}），须补强断言而非补行"
        )
        return 2
    print(f"[OK] 变异得分 {_format_score(score)}（阈值 {threshold}%，{len(results)} 个目标全部达标）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="变异得分离线评测（委托 mutmut 按目标切片逐块跑，不进提交门禁）")
    add_common_args(parser)
    parser.add_argument("--list-targets", action="store_true", help="打印本期变异目标清单（不依赖后端）")
    parser.add_argument("--dry", action="store_true", help="只解析目标与配置、打印将执行的后端命令")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="变异得分阈值（百分比）")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单个目标切片的后端超时（秒）")
    parser.add_argument("--json", action="store_true", help="输出机读结果")
    args = parser.parse_args(argv)

    if args.list_targets:
        return _print_targets(as_json=args.json)
    if args.dry:
        return _print_plan(args.threshold, args.timeout, as_json=args.json)

    if not backend_available():
        print(f"[ERR] 未安装变异评测后端 {BACKEND_MODULE}（可选工具，未写入 requirements.txt）")
        print(f"[..] 安装：{INSTALL_COMMAND}")
        print("[..] 未开始评测，也没有产生任何 finding——这属环境缺失，不是测试质量问题")
        return 1

    results = [evaluate_target(target, timeout=args.timeout) for target in TARGETS]
    return _report(results, threshold=args.threshold, verbose=args.verbose, ci=args.ci, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
