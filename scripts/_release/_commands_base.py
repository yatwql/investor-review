"""发布编排共用原语 — 耗时埋点、预检、git 探测、发布戳与归档路径推导。

命令实现（`_commands_prep.py` / `_commands_ship.py`）与本模块共用这组原语；
入口 `scripts/release.py` 保留路径常量并经 `env` 投影注入，故测试对入口模块
做 `setattr` 重定向对本模块同样生效。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from _release import _gate
from _release._archive_flow import prerequisite_findings
from _release._common import ReleaseError, exec_command as _exec
from _release._timing import StepTimer as _StepTimer
from _release._timing import (
    agent_identity as _agent_identity,
    append_record as _append_record,
    build_record as _build_record,
    format_agent as _format_agent,
    format_tokens as _format_tokens,
    release_token_usage as _release_token_usage,
    session_usage as _session_usage,
)
from _release._versioning import (
    DEV_VERSION_RE as _DEV_VERSION_RE,
    RELEASE_VERSION_RE as _RELEASE_VERSION_RE,
    read_app_version,
    release_version_of,
)

_DOC_ONLY_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".gif", ".svg")


_TIMER: _StepTimer | None = None

#: 失败原因快照（当前命令内首次失败的步骤；`_finish_timing` 写进台账 failure 字段）
_FAILURE: dict | None = None

#: 失败输出里「报告归档」行的路径（test-runner 归档成功后打印）
_REPORT_DIR_RE = re.compile(r"历史报告已归档[:：]\s*(\S+?)/?\s*$", re.MULTILINE)
#: pytest 短摘要的失败/错误用例行
_FAILED_TEST_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)
#: 台账里保留的输出尾部行数与字符上限（足够看出原因，不至于把整份日志塞进 JSONL）
_FAILURE_TAIL_LINES = 12
_FAILURE_TAIL_CHARS = 1600


def _timer() -> _StepTimer:
    """取当前命令的计时器（未初始化时新建，保证 handler 可独立调用）。"""
    global _TIMER
    if _TIMER is None:
        _TIMER = _StepTimer()
    return _TIMER


def _reset_timer() -> _StepTimer:
    """为下一条命令重置计时器与失败快照（`main` 入口调用，避免进程内多次调用串味）。"""
    global _TIMER, _FAILURE
    _TIMER = _StepTimer()
    _FAILURE = None
    return _TIMER


def _failure_context() -> dict | None:
    """当前命令的失败快照（未失败返回 None）。"""
    return _FAILURE


def _summarize_failure(
    label: str,
    rc: int,
    out: str = "",
    err: str = "",
    root: Path | None = None,
) -> dict:
    """把一次步骤失败压成台账可用的小快照。

    报告目录与失败用例名从输出里提取（test-runner 的归档行 / pytest 短摘要）；
    某些 runner 只把 FAILED 明细写进归档 debug.log、stdout 只剩摘要，故失败用例
    为空时再读该报告目录的 `*_debug.log` 兜底。台账因此自证「折在哪一步、哪些
    用例红、报告在哪」，不必再去 `test-reports/archives/` 按 mtime 反查。
    """
    combined = "\n".join(part for part in (out, err) if part)
    report_match = _REPORT_DIR_RE.search(combined)
    report_dir = report_match.group(1) if report_match else ""
    extract_text = combined
    diagnostic_tail = ""
    if not _FAILED_TEST_RE.search(combined) and root is not None and report_dir:
        candidates = [Path(root) / report_dir, Path(root) / "test-reports" / report_dir]
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            debug_logs = sorted(candidate.glob("*_debug.log"))
            if not debug_logs:
                continue
            debug_text = debug_logs[-1].read_text(encoding="utf-8", errors="replace")
            extract_text += "\n" + debug_text
            debug_lines = [line for line in debug_text.splitlines() if line.strip()]
            first_failure = next(
                (idx for idx, line in enumerate(debug_lines) if line.startswith(("FAILED ", "ERROR "))),
                0,
            )
            diagnostic_tail = "\n".join(debug_lines[first_failure : first_failure + _FAILURE_TAIL_LINES])
            break
    failed_tests = list(dict.fromkeys(_FAILED_TEST_RE.findall(extract_text)))[:20]
    tail_source = diagnostic_tail or combined
    tail_lines = [line for line in tail_source.splitlines() if line.strip()][-_FAILURE_TAIL_LINES:]
    tail = "\n".join(tail_lines)[-_FAILURE_TAIL_CHARS:]
    return {
        "step": label,
        "rc": int(rc),
        "report_dir": report_dir,
        "failed_tests": failed_tests,
        "tail": tail,
    }


def _record_failure(label: str, rc: int, out: str = "", err: str = "", root: Path | None = None) -> None:
    """记录当前命令的首次失败（后续步骤的失败不覆盖第一现场）。"""
    global _FAILURE
    if _FAILURE is None:
        _FAILURE = _summarize_failure(label, rc, out, err, root=root)


def _finish_timing(command: str, rc: int, env) -> None:
    """尾行打印耗时摘要并追加 `logs/release.jsonl`——埋点是观测面，写失败只提示。"""
    timer = _timer()
    summary = timer.summary()
    print(f"[..] {command} 耗时 {timer.total:.1f}s" + (f"（{summary}）" if summary else ""))
    try:
        version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ReleaseError):
        version = ""
    tokens = _session_usage(os.environ.get("PI_SESSION_FILE"))
    agent = _agent_identity()
    failure = _failure_context() if rc != 0 else None
    if rc != 0 and failure is None:
        # 非 `_run_step` 路径（门禁断言/预检/归档前置等）只拿得到退出码：
        # 仍写入 rc，原因由终端输出承担，避免失败记录只剩 ok=false
        failure = {"step": "", "rc": int(rc), "note": "见终端输出（未经过 _run_step 的步骤）"}
    record = _build_record(
        command=command,
        elapsed_s=timer.total,
        ok=(rc == 0),
        steps=timer.steps,
        version=version,
        session_usage=tokens,
        agent=agent,
        failure=failure,
    )
    try:
        path = _append_record(env.RELEASE_LOG_FILE, record)
    except (OSError, ReleaseError, ValueError) as exc:
        print(f"[!] 耗时记录未写入（{exc}）——不影响本次结果")
        return
    shown = path.relative_to(env.REPO_ROOT) if path.is_relative_to(env.REPO_ROOT) else path
    print(f"[..] 耗时已记录到 {shown}")
    agent_text = _format_agent(agent)
    if agent_text:
        print(f"[..] 执行环境：{agent_text}")
    # 发布窗口 token 统计：以「上一次 devbump」为界，避免把开发期对话算进发布成本
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        used = _release_token_usage(rows)
        text = _format_tokens(used)
        if text:
            print(f"[..] 本次发布累计 token：{text}")
    except (OSError, ValueError, TypeError):
        print("[!] token 统计读取失败（不影响本次结果）")


def archive_paths_for(release_version: str, env) -> tuple[Path, str]:
    """按小版本推导归档目录与文件名（小版本号 → docs/archive/vX.Y.x/… 目录）。"""
    m = _RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    name = f"archived_changelog.{minor}.x.md"
    return env.ARCHIVE_DOCS_DIR / f"v{minor}.x" / name, name


def ledger_archive_paths(release_version: str, env) -> tuple[Path, Path]:
    """按小版本推导台账归档文件（review-findings / plan 两份，同版本目录下）。"""
    m = _RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    base = env.ARCHIVE_DOCS_DIR / f"v{minor}.x"
    return (
        base / f"archived_review-findings.{minor}.x.md",
        base / f"archived_plan.{minor}.x.md",
    )


def _current_branch(root: Path, runner=None) -> str:
    rc, out, _ = _exec(["git", "branch", "--show-current"], root, runner)
    return out.strip() if rc == 0 else ""


def _worktree_clean(root: Path, runner=None) -> bool:
    rc, out, _ = _exec(["git", "status", "--porcelain"], root, runner)
    return rc == 0 and out.strip() == ""


def _tag_absent(root: Path, tag: str, runner=None) -> bool:
    rc, _, _ = _exec(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], root, runner)
    return rc != 0


def run_preflight(
    root: Path, expect_release: bool = False, runner=None, require_clean: bool = True
) -> list[tuple[str, bool, str]]:
    """前置条件 + 版本一致性；返回 [(检查名, 是否通过, 详情)]。

    ``require_clean=False`` 供 publish 使用——彼时 prepare 手术改动尚待提交，属预期状态。
    """
    results: list[tuple[str, bool, str]] = []
    branch = _current_branch(root, runner)
    results.append(("工作分支为 dev", branch == "dev", f"当前分支：{branch or '<获取失败>'}"))
    if require_clean:
        clean = _worktree_clean(root, runner)
        results.append(("工作树干净", clean, "有未提交改动" if not clean else "无未提交改动"))

    constants_path = root / "src" / "python" / "core" / "constants.py"
    try:
        version = read_app_version(constants_path.read_text(encoding="utf-8"))
    except (OSError, ReleaseError) as exc:
        results.append(("版本形态", False, f"读取 APP_VERSION 失败：{exc}"))
        version = ""
    if version:
        if expect_release:
            ok = bool(_RELEASE_VERSION_RE.match(version))
            results.append(("版本为发布形态", ok, f"APP_VERSION = {version}"))
        else:
            ok = bool(_DEV_VERSION_RE.match(version))
            results.append(("版本为开发形态", ok, f"APP_VERSION = {version}"))
        if ok:
            rel = version if expect_release else release_version_of(version)
            results.append((f"tag v{rel} 未占用", _tag_absent(root, f"v{rel}", runner), "已存在则发布会被拒"))

    rc, out, _ = _exec([sys.executable, "scripts/check-version-consistency.py", "--ci"], root, runner)
    results.append(("版本号一致性", rc == 0, (out or "").strip().splitlines()[0] if (out or "").strip() else ""))
    return results


def _print_results(results: list[tuple[str, bool, str]]) -> bool:
    all_ok = True
    for name, ok, detail in results:
        mark = "[OK]" if ok else "[ERR]"
        all_ok = all_ok and ok
        print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    return all_ok


def archive_prerequisites(release_version: str, env) -> list[str]:
    """发布归档前置（两份归档文件 + 目录树该小版本块）：`check` 阶段提前报缺件。"""
    return prerequisite_findings(release_version, env.archive_ctx(release_version))


def _git_ok(args: list[str], root: Path, runner=None, capture: bool = True) -> tuple[int, str, str]:
    return _exec(["git", *args], root, runner, capture=capture)


def _last_release_tag(env, runner=None) -> str | None:
    """最近的发布 tag（v*）；无则 None（调用方保守地视为需刷新）。"""
    rc, out, _ = _git_ok(["describe", "--tags", "--abbrev=0", "--match", "v*"], env.REPO_ROOT, runner)
    tag = out.strip() if rc == 0 else ""
    return tag or None


def _docs_only_changes_since(tag: str, env, runner=None) -> tuple[bool, list[str]]:
    """自 tag 起（含未提交/未跟踪）的变更是否纯文档。

    Returns:
        (是否纯文档, 非文档后缀文件清单——空即纯文档)
        git 查询失败返回 (False, [])（保守：视同有程序变更，必跑刷新）。
    """
    rc1, out1, _ = _git_ok(["diff", "--name-only", tag], env.REPO_ROOT, runner)
    rc2, out2, _ = _git_ok(["ls-files", "--others", "--exclude-standard"], env.REPO_ROOT, runner)
    if rc1 != 0:
        return False, []
    changed = [ln.strip() for ln in out1.splitlines() if ln.strip()]
    if rc2 == 0:
        changed += [ln.strip() for ln in out2.splitlines() if ln.strip()]
    non_doc = sorted({f for f in changed if not f.endswith(_DOC_ONLY_SUFFIXES)})
    return (not non_doc), non_doc


def _run_step(label: str, cmd: list[str], root: Path, runner=None) -> int:
    print(f"[..] {label}")
    rc, out, err = _exec(cmd, root, runner)
    if out.strip():
        print(out.rstrip())
    if rc != 0:
        if err.strip():
            print(err.rstrip())
        _record_failure(label, rc, out, err, root=root)
        print(f"[ERR] {label} 退出码 {rc}（按输出处理后重跑本子命令）")
        return rc
    print(f"[OK] {label}")
    return 0


def _gate_workers() -> int:
    """十守护并行度：4 路封顶、随核数收敛——弱机器（如 2 核）自动降路，避免 CPU 超订反而拖慢总墙钟。"""
    return max(1, min(4, os.cpu_count() or 4))


def _tree_fingerprint(env, runner=None) -> str:
    """工作区全树指纹（保留：供需要「改动过任何文件」语义的调用方；发布戳用代码指纹）。"""
    return _gate.tree_fingerprint(_exec, env.REPO_ROOT, runner)


def _write_gate_stamp(
    version: str,
    fingerprint: str,
    verify_passed: str,
    env,
    source: str = "run",
    code_files: dict[str, str] | None = None,
) -> None:
    """写 gate 通过戳（实现在 `_release/_gate.py`）。"""
    _gate.write_gate_stamp(env.GATE_STAMP_FILE, version, fingerprint, verify_passed, source, code_files)


def _read_gate_stamp(env) -> dict | None:
    """读现有 gate 戳（不论是否匹配当前指纹），供 publish 解释「为何重跑 verify」。"""
    return _gate.read_gate_stamp(env.GATE_STAMP_FILE)


def _changed_code_files(env, stamp: dict | None, runner=None) -> list[str]:
    """gate 之后发生改动的代码文件（戳里没存文件清单时返回空）。"""
    if not stamp:
        return []
    current = _gate.code_file_hashes(_exec, env.REPO_ROOT, runner)
    return _gate.diff_code_files(stamp.get("code_files") or {}, current)


def _code_fingerprint(env, runner=None) -> str:
    """测试相关代码路径指纹（实现在 `_release/_gate.py`）。"""
    return _gate.code_fingerprint(_exec, env.REPO_ROOT, runner)


def _write_bench_stamp(fingerprint: str, modes: list[str], covers_unit: bool, env) -> None:
    """写 refresh bench 通过戳（实现在 `_release/_gate.py`）。"""
    version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    _gate.write_bench_stamp(env.BENCH_STAMP_FILE, version, modes, fingerprint, covers_unit)


def _bench_covers_verify(env, runner=None) -> dict | None:
    """bench 戳是否可替代 P1 verify（实现在 `_release/_gate.py`）。"""
    version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    return _gate.bench_covers_verify(env.BENCH_STAMP_FILE, version, _code_fingerprint(env, runner))


def _gate_stamp_matches(version: str, fingerprint: str, env) -> dict | None:
    """读 gate 通过戳并按「版本 + 树指纹」校验（实现在 `_release/_gate.py`）。"""
    return _gate.gate_stamp_matches(env.GATE_STAMP_FILE, version, fingerprint)
