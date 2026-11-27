"""内置变异器的执行协议层：备份 → 写入单点变异 → 跑目标测试 → `finally` 还原校验 → 分类。

安全协议（改写真实源码是唯一风险点，故四层兜底）：

  1. 跑之前校验工作树干净（`git status --porcelain` 在切片路径上为空）——脏即拒跑，
     否则还原时会把用户未提交的编辑一起写掉；
  2. 逐文件**字节级**备份（`read_bytes`），`finally` 还原并校验 sha256 与备份一致，
     不一致立刻抛 `RestoreError`（大声失败，不静默继续）；
  3. `atexit` + SIGTERM/SIGHUP 处理兜底还原（Ctrl-C 走 `finally`，被 supervisord/kill
     结束则走信号处理——`atexit` 对 SIGTERM 不生效，只靠它会留下变异版源码）；
  4. pytest 子进程带 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`——变异源码绝不写 `.pyc`。
     否则断言重写缓存按 (size, mtime) 命中，还原后仍指向**变异版**字节码，下一次正常
     跑测试会凭空失败。

分类口径（分母只含判定得了的变异体）：

  - 退出码 0            → `survived`（测试没断言住这处行为）
  - 退出码 1            → `killed`（有用例失败）
  - 子进程超时          → `timeout`，不计入分母
  - 其他退出码          → `error`，不计入分母（pytest 2 = 收集中断/变异体语法错误，
                          3 = 内部错误，4 = 用法错，5 = 无用例——都说明这次变异没被评上，
                          记成 survived 会把工具故障算成测试质量问题）
"""

from __future__ import annotations

import atexit
import hashlib
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from _eval_mutation.operators import Mutant, iter_mutants
from _eval_mutation.results import (
    STATUS_ERROR,
    STATUS_KILLED,
    STATUS_SURVIVED,
    STATUS_TIMEOUT,
    MutantOutcome,
    MutationCounts,
    SliceRun,
)
from _eval_mutation.targets import (
    DEFAULT_JOBS,
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MUTANT_TIMEOUT,
    DEFAULT_SLICE_TIMEOUT,
    MutationTarget,
)
from _shared.checklib import REPO_ROOT, repo_relative_posix


class RestoreError(RuntimeError):
    """还原校验失败：源文件已经不是变异前的字节（必须人工介入，不得继续跑）。"""


@dataclass
class _RestoreRegistry:
    """变异期间的字节级备份登记表（`finally` 与 `atexit` 双兜底，Ctrl-C 也不留脏文件）。"""

    pending: dict[Path, bytes] = field(default_factory=dict)

    def register(self, path: Path, original: bytes) -> None:
        self.pending[path] = original

    def restore(self, path: Path) -> None:
        """还原为备份字节并校验 sha256；校验失败抛 `RestoreError`。"""
        original = self.pending[path]
        path.write_bytes(original)
        expected = hashlib.sha256(original).hexdigest()
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RestoreError(f"还原校验失败（sha256 不一致），请人工检查：{path}")
        self.pending.pop(path, None)

    def restore_all(self) -> None:
        """兜底还原全部登记文件（幂等；还原失败只告警不抛——已无从收拾，别掩盖原始异常）。"""
        for path in list(self.pending):
            try:
                self.restore(path)
            except (OSError, RestoreError):
                continue


_REGISTRY = _RestoreRegistry()
atexit.register(_REGISTRY.restore_all)

#: 信号兜底是否已装（进程内只装一次）
_TERMINATION_GUARD_INSTALLED = False


def _on_termination(signum: int, _frame: object) -> None:
    """收到终止信号：先还原再退出（退出码沿用 shell 的 128+N 惯例）。"""
    _REGISTRY.restore_all()
    raise SystemExit(128 + int(signum))


def install_termination_guard() -> None:
    """装 SIGTERM / SIGHUP 处理器——变异期间被强杀时也要还原源码，别留变异版。"

    非主线程 / 不支持的平台只跳过（`finally` 与 `atexit` 仍兜底）。
    """
    global _TERMINATION_GUARD_INSTALLED
    if _TERMINATION_GUARD_INSTALLED:
        return
    for name in ("SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            signal.signal(number, _on_termination)
        except (OSError, ValueError):  # 非主线程 / 平台不支持：放弃该信号，仍有 finally+atexit
            continue
    _TERMINATION_GUARD_INSTALLED = True


def slice_files(target: MutationTarget, *, repo_root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """切片路径（可含 glob）→ 实际源文件清单（排序后确定）。"""
    files: list[Path] = []
    for pattern in target.paths:
        files.extend(sorted(path for path in repo_root.glob(pattern) if path.is_file()))
    return tuple(files)


def collect_mutants(
    target: MutationTarget,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[list[Mutant], list[str]]:
    """枚举切片内全部变异体；无法解析的源文件跳过并如实记一条 note。"""
    mutants: list[Mutant] = []
    notes: list[str] = []
    for path in slice_files(target, repo_root=repo_root):
        source = path.read_text(encoding="utf-8")
        try:
            mutants.extend(iter_mutants(repo_relative_posix(path, repo_root), source))
        except SyntaxError as exc:
            notes.append(f"{repo_relative_posix(path, repo_root)} 无法解析（{exc.msg}，第 {exc.lineno} 行），已跳过")
    return mutants, notes


def test_command(
    target: MutationTarget,
    *,
    python_executable: str | None = None,
) -> list[str]:
    """逐变异体跑的 pytest 选择命令（只跑该切片的相关测试，命中首个失败即停）。

    `-B` 与继承的 `PYTHONDONTWRITEBYTECODE=1` 是硬要求：变异源码不得留下 `.pyc`。
    """
    executable = python_executable or "python"
    return [
        executable,
        "-B",
        "-m",
        "pytest",
        *target.tests,
        "-x",
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]


def dirty_paths(paths: Sequence[str], *, repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """指定路径上的未提交改动（空元组 = 干净）；git 不可用时抛 `OSError`（宁可不跑）。"""
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    return tuple(line for line in completed.stdout.splitlines() if line.strip())


def mutation_paths(targets: Sequence[MutationTarget]) -> tuple[str, ...]:
    """需要保持干净的关键路径 = 各切片的源码路径 + 测试选择路径。"""
    paths: list[str] = []
    for target in targets:
        paths.extend(target.paths)
        paths.extend(target.tests)
    return tuple(paths)


def _first_failure(output: str) -> str:
    """失败输出里第一条 `FAILED ...` 行（判读时知道是哪个用例杀的）；没有则取末行。"""
    for line in output.splitlines():
        if line.startswith("FAILED"):
            return line.strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def classify(returncode: int) -> str:
    """退出码 → 变异体判定（0 存活 / 1 被杀 / 其余为 error，见模块 docstring）。"""
    if returncode == 0:
        return STATUS_SURVIVED
    if returncode == 1:
        return STATUS_KILLED
    return STATUS_ERROR


def _execute_mutant(
    mutant: Mutant,
    *,
    path: Path,
    original: bytes,
    command: Sequence[str],
    repo_root: Path,
    timeout: int,
) -> MutantOutcome:
    """写入单点变异 → 跑测试 → `finally` 还原（含 sha256 校验）→ 分类。"""
    _REGISTRY.register(path, original)
    path.write_bytes(mutant.source.encode("utf-8"))
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=_child_env(),
        )
    except subprocess.TimeoutExpired:
        return MutantOutcome(mutant=mutant, status=STATUS_TIMEOUT, summary=f"超时（>{timeout}s）")
    except OSError as exc:
        return MutantOutcome(mutant=mutant, status=STATUS_ERROR, summary=f"pytest 启动失败：{exc}")
    finally:
        _REGISTRY.restore(path)
    output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    status = classify(completed.returncode)
    summary = "" if status == STATUS_SURVIVED else _first_failure(output)
    return MutantOutcome(mutant=mutant, status=status, summary=summary)


def _child_env() -> dict[str, str]:
    """子进程环境：禁止写 `.pyc`（变异源码的字节码会污染还原后的正常跑测试）。"""
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


@dataclass(frozen=True)
class _BucketResult:
    outcomes: tuple[MutantOutcome, ...]
    skipped: int


def _run_file_bucket(
    path: Path,
    mutants: Sequence[Mutant],
    *,
    command: Sequence[str],
    repo_root: Path,
    timeout: int,
    deadline: float,
) -> _BucketResult:
    """单文件桶内串行执行（同一文件的变异体永不并发——文件互斥的落点）。"""
    original = path.read_bytes()
    executed: list[MutantOutcome] = []
    skipped = 0
    for index, mutant in enumerate(mutants):
        if time.monotonic() >= deadline:
            skipped = len(mutants) - index
            break
        executed.append(
            _execute_mutant(
                mutant,
                path=path,
                original=original,
                command=command,
                repo_root=repo_root,
                timeout=timeout,
            )
        )
    _REGISTRY.pending.pop(path, None)
    return _BucketResult(outcomes=tuple(executed), skipped=skipped)


def run_slice(
    target: MutationTarget,
    *,
    repo_root: Path = REPO_ROOT,
    python_executable: str | None = None,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    mutant_timeout: int = DEFAULT_MUTANT_TIMEOUT,
    slice_timeout: int = DEFAULT_SLICE_TIMEOUT,
    jobs: int = DEFAULT_JOBS,
) -> SliceRun:
    """跑完一个切片的全部（有界）变异体并汇总计数；不改动任何源码的最终字节。"""
    install_termination_guard()
    mutants, notes = collect_mutants(target, repo_root=repo_root)
    generated = len(mutants)
    selected = mutants[:max_mutants]
    if generated > len(selected):
        notes.append(f"变异体截断：生成 {generated} 个，按 --max-mutants={max_mutants} 只执行前 {len(selected)} 个")

    by_file: dict[Path, list[Mutant]] = {}
    for mutant in selected:
        by_file.setdefault(repo_root / mutant.path, []).append(mutant)

    command = test_command(target, python_executable=python_executable or _python_executable())
    deadline = time.monotonic() + slice_timeout
    buckets = sorted(by_file.items())
    workers = max(1, min(jobs, len(buckets)))
    if jobs > 1 and len(buckets) > 1:
        notes.append(
            f"并行度 {workers}：不同文件同时变异，跨文件相互依赖的切片可能误判 killed，判读存疑时用 --jobs 1 复跑"
        )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(
            pool.map(
                lambda item: _run_file_bucket(
                    item[0],
                    item[1],
                    command=command,
                    repo_root=repo_root,
                    timeout=mutant_timeout,
                    deadline=deadline,
                ),
                buckets,
            )
        )

    outcomes = [outcome for result in results for outcome in result.outcomes]
    skipped = sum(result.skipped for result in results)
    if skipped:
        notes.append(f"切片时限 {slice_timeout}s 已达：{skipped} 个变异体未执行（不计入分母）")

    counts = MutationCounts(
        killed=sum(1 for outcome in outcomes if outcome.status == STATUS_KILLED),
        survived=sum(1 for outcome in outcomes if outcome.status == STATUS_SURVIVED),
        timed_out=sum(1 for outcome in outcomes if outcome.status == STATUS_TIMEOUT),
        errored=sum(1 for outcome in outcomes if outcome.status == STATUS_ERROR),
        generated=generated,
        executed=len(outcomes),
    )
    survivors = tuple(outcome for outcome in outcomes if outcome.status == STATUS_SURVIVED)
    return SliceRun(counts=counts, survivors=survivors, notes=tuple(notes))


def _python_executable() -> str:
    """被测测试用**当前解释器**跑（项目虚拟环境，含 pandas 等依赖）。"""
    return sys.executable
