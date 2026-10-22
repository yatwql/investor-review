#!/usr/bin/env python3
"""发布流程分步编排脚本 —— 把发布口径从文档散文固化为可执行子命令。

八个分步子命令（每步独立可审阅、失败即停不连锁，按序执行）：

    check      预检：分支 / 工作树干净 / 版本形态 / tag 未占用 / 版本一致性
    prepare    文档手术：版本全链（constants + README + --fix 传播）+ changelog
               发布段迁入归档、指针与归档索引改写（changelog 段由本步自动完成）
    archive    台账归档迁移（机械部分自动、判定仍人工复核）：review-findings 该版本
               已解决表**原表搬运**入归档 + 主台账留占位 + 归档头部/索引日期派生；
               plan 已完成任务节整节搬入计划归档；docs/plan 已完成设计文件（引用编号
               均已归档）迁入版本归档并改写引用与目录树；收尾 doc-drift --sync + 两台
               便宜守护。`--dry-run` 只报告动作；gate 会断言该版本表已搬空
    refresh    数据刷新：bench --update-docs（默认只测发布子集四档 unit / dev-verify /
               regression / integration，`--full-bench` 跑全量模式）+ test-collect-coverage
               + doc-drift --sync（自上一 release tag 起仅文档变更时跳过 bench 与 collect，
                 --force-refresh 强制刷新；同步恒跑）
    evolution  版本演进对照快照：git 清单 + 逐文件行数口径；默认只滚「当前开发版」列，
               `--release` 时发布列与增长比一并写入（发布期在 prepare 之后执行）
    gate       P2 门禁：`--mode regression` + 十守护 `--ci`（清单与门禁文档同源）
               + 设计护栏 `check-style-guardrails --ci`（E 级拦 / W 级观察统计）
    publish    release 提交 + P1 verify + --no-ff 合并 dev→master + tag（默认不推送）
    devbump    切下一开发版 X.Y.(Z+1)-dev + chore 提交

典型发布序列：
    .venv/bin/python scripts/release.py check
    .venv/bin/python scripts/release.py prepare
    .venv/bin/python scripts/release.py archive
    .venv/bin/python scripts/release.py refresh
    .venv/bin/python scripts/release.py evolution --release
    .venv/bin/python scripts/release.py gate
    .venv/bin/python scripts/release.py publish --title "<发布主题>"
    .venv/bin/python scripts/release.py devbump

退出码：0 = 通过；2 = 预检/门禁发现（与守护脚本 CLI 契约一致）；1 = 执行失败。

耗时埋点：每命令的总墙钟与分步耗时（gate 的回归/十守护/护栏、refresh 的
bench/collect/sync、publish 的 P1 verify）追加写入 `logs/release.jsonl`（git 忽略域，
不入目录树、无门禁依赖），终端尾行同步打印摘要——跨版本对拍直接
`tail -n 20 logs/release.jsonl`，无需现场重测。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_FILE = REPO_ROOT / "src" / "python" / "core" / "constants.py"
README_FILE = REPO_ROOT / "README.md"
# 文档树路径（本脚本自包含不依赖 _checklib，常量语义与其同名项一致）
_MANAGEMENTS_DIR = REPO_ROOT / "docs" / "managements"
_ARCHIVE_DOCS_DIR = REPO_ROOT / "docs" / "archive"
CHANGELOG_FILE = _MANAGEMENTS_DIR / "changelog.md"
RF_FILE = _MANAGEMENTS_DIR / "review-findings.md"
PLAN_FILE = _MANAGEMENTS_DIR / "plan.md"
PLAN_DOCS_DIR = REPO_ROOT / "docs" / "plan"
FOLDERS_FILE = _MANAGEMENTS_DIR / "folders.md"
TEST_COVERAGE_FILE = _MANAGEMENTS_DIR / "test-coverage.md"

# P2 十守护清单（与 CLAUDE.md / testplan.md / developer-guide.md / ci.yml / pre-commit 钩子同源）
GUARD_SCRIPTS = [
    "scripts/check-code-traces.py",
    "scripts/check-doc-traces.py",
    "scripts/check-task-numbering.py",
    "scripts/check-semantic-index.py",
    "scripts/check-doc-drift.py",
    "scripts/check-test-redundancy.py",
    "scripts/check-requirement-trace.py",
    "scripts/check-version-consistency.py",
    "scripts/check-doc-links.py",
    "scripts/check-file-length.py",
]

#: refresh 的 bench 模式子集——只测**门禁口径**关心的四档：P0 `dev-verify`、
#: P1 `verify` 的 unit 总量面、P2 `regression`、CI 恒跑的 `integration`。全量 14 档
#: 串行约 5.5 min（2 路采集 3.2 min），占单次发布机器时间约 75%，而其余模式与这四档
#: 高度重叠（standard / scenario / edge / data / smoke / report / all_no_unit /
#: scenario_extreme / all）；未实测模式的耗时与计数按 `--update-docs` 既有口径
#: 「保留上次实测值」，不会写脏。需要全量复测时用 `--full-bench`。
RELEASE_BENCH_MODES: tuple[str, ...] = ("unit", "dev-verify", "regression", "integration")

#: 发布耗时台账（`logs/` 属 git 忽略域：不入目录树、不进门禁）
RELEASE_LOG_FILE = REPO_ROOT / "logs" / "release.jsonl"

# ── 内部实现拆分（_release/ 包）：入口保留 CLI 面与路径常量，测试引用的符号原名 re-export ──
sys.path.insert(0, str(REPO_ROOT))  # 仓库根：耗时台账复用 core 层 JSONL 原子追加原语
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享设施（_release 包）
from _release._changelog_archive import (  # noqa: E402, F401 — _SECTION_NOTE 供测试经入口模块引用
    SECTION_NOTE as _SECTION_NOTE,
    apply_changelog_release,
    render_archive_header,
    write_archive_release,
)
from _release._archive_init import init_archive  # noqa: E402
from _release._common import ReleaseError, exec_command as _exec  # noqa: E402
from _release._archive_flow import (  # noqa: E402
    ArchiveContext,
    prerequisite_findings,
    run_archive as archive_flow,
)
from _release._ledger_archive import (  # noqa: E402, F401 — 纯函数面经入口 re-export 供测试按脚本名访问
    apply_plan_archive,
    _INDEX_RANGE_RE,
    _RF_ARCHIVE_HEAD_FMT,
    RF_PLACEHOLDER,
    _bump_index_range,
    _collapse_superseded_placeholders,
    drop_migration_placeholders,
    apply_rf_archive,
    archive_header_findings,
    count_rf_rows,
    design_doc_candidates,
    extract_rf_table,
    has_archive_section,
    move_tree_entry,
    open_ids,
    pending_rf_rows,
    plan_completed_sections,
    rf_archive_status,
    rewrite_doc_refs,
    stale_reference_files,  # noqa: F401 — 供测试经入口模块引用
    unreferenced_docs,
)
from _release._timing import StepTimer as _StepTimer, append_record as _append_record  # noqa: E402
from _release._timing import format_tokens as _format_tokens  # noqa: E402
from _release._timing import release_token_usage as _release_token_usage  # noqa: E402
from _release._timing import session_usage as _session_usage  # noqa: E402
from _release._timing import agent_identity as _agent_identity  # noqa: E402
from _release._timing import format_agent as _format_agent  # noqa: E402
from _release._timing import (  # noqa: E402, F401 — 纯函数面经入口 re-export 供测试按脚本名访问
    build_record,
    format_tokens,
    release_token_usage,
    session_usage,
    agent_identity,
    format_agent,
)
from _release._timing import build_record as _build_record  # noqa: E402
from _release._evolution import (  # noqa: E402, F401 — _line_count 供测试经入口模块引用
    build_evolution_stats,
    check_evolution_freshness,
    fmt_pair as _fmt_pair,
    line_count as _line_count,
    update_case_note,
    update_evolution_table,
    update_ratio_note,
)
from _release._versioning import (  # noqa: E402
    DEV_VERSION_RE as _DEV_VERSION_RE,
    RELEASE_VERSION_RE as _RELEASE_VERSION_RE,
    next_dev_version_of,
    normalize_release_title,
    read_app_version,
    release_version_of,
    render_app_version,
    render_readme_version,
)


# ─────────────────────────── 耗时埋点 ───────────────────────────

#: 当前命令的分步计时器（`main` 每命令重建；直接调 handler 的测试惰性创建）
_TIMER: _StepTimer | None = None


def _timer() -> _StepTimer:
    """取当前命令的计时器（未初始化时新建，保证 handler 可独立调用）。"""
    global _TIMER
    if _TIMER is None:
        _TIMER = _StepTimer()
    return _TIMER


def _reset_timer() -> _StepTimer:
    """为下一条命令重置计时器（`main` 入口调用，避免进程内多次调用串味）。"""
    global _TIMER
    _TIMER = _StepTimer()
    return _TIMER


def _finish_timing(command: str, rc: int) -> None:
    """尾行打印耗时摘要并追加 `logs/release.jsonl`——埋点是观测面，写失败只提示。"""
    timer = _timer()
    summary = timer.summary()
    print(f"[..] {command} 耗时 {timer.total:.1f}s" + (f"（{summary}）" if summary else ""))
    try:
        version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ReleaseError):
        version = ""
    tokens = _session_usage(os.environ.get("PI_SESSION_FILE"))
    agent = _agent_identity()
    record = _build_record(
        command=command,
        elapsed_s=timer.total,
        ok=(rc == 0),
        steps=timer.steps,
        version=version,
        session_usage=tokens,
        agent=agent,
    )
    try:
        path = _append_record(RELEASE_LOG_FILE, record)
    except (OSError, ReleaseError, ValueError) as exc:
        print(f"[!] 耗时记录未写入（{exc}）——不影响本次结果")
        return
    shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
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


def archive_paths_for(release_version: str) -> tuple[Path, str]:
    """按小版本推导归档目录与文件名（小版本号 → docs/archive/vX.Y.x/… 目录）。"""
    m = _RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    name = f"archived_changelog.{minor}.x.md"
    return _ARCHIVE_DOCS_DIR / f"v{minor}.x" / name, name


def ledger_archive_paths(release_version: str) -> tuple[Path, Path]:
    """按小版本推导台账归档文件（review-findings / plan 两份，同版本目录下）。"""
    m = _RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    base = _ARCHIVE_DOCS_DIR / f"v{minor}.x"
    return (
        base / f"archived_review-findings.{minor}.x.md",
        base / f"archived_plan.{minor}.x.md",
    )


# ─────────────────────────── changelog 发布段迁移 ───────────────────────────

# ─────────────────────────── 预检 ───────────────────────────


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


def _archive_ctx(version: str) -> ArchiveContext:
    """按当前模块路径常量组装归档上下文（测试对模块属性的重定向在此生效）。"""
    rf_archive, plan_archive = ledger_archive_paths(version)
    return ArchiveContext(
        repo_root=REPO_ROOT,
        rf_file=RF_FILE,
        plan_file=PLAN_FILE,
        folders_file=FOLDERS_FILE,
        changelog_file=CHANGELOG_FILE,
        readme_file=README_FILE,
        claude_file=REPO_ROOT / "CLAUDE.md",
        plan_docs_dir=PLAN_DOCS_DIR,
        rf_archive=rf_archive,
        plan_archive=plan_archive,
    )


def archive_prerequisites(release_version: str) -> list[str]:
    """发布归档前置（两份归档文件 + 目录树该小版本块）：`check` 阶段提前报缺件。"""
    return prerequisite_findings(release_version, _archive_ctx(release_version))


def cmd_check(args: argparse.Namespace, runner=None) -> int:
    print("[..] 发布预检")
    ok = _print_results(run_preflight(REPO_ROOT, expect_release=False, runner=runner))
    if not ok:
        print("[ERR] 预检未通过，先处理上述项再继续")
        return 2
    dev_version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))
    release_version = dev_version if not dev_version.endswith("-dev") else release_version_of(dev_version)
    findings = archive_prerequisites(release_version)
    if findings:
        for finding in findings:
            print(f"[ERR] {finding}")
        print(f"[ERR] v{release_version} 归档前置未就绪，先补齐再执行 prepare")
        return 2
    print(f"[OK] 归档前置就绪（v{release_version} 台账归档与目录树块）")
    print("[OK] 预检通过 — 可执行 prepare")
    return 0


# ─────────────────────────── archive-init ───────────────────────────


def cmd_archive_init(args: argparse.Namespace, runner=None) -> int:
    """新小版本归档骨架初始化：三份归档文件 + 目录树块 + 三处索引行（幂等）。"""
    dev_version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))
    version = args.version or (release_version_of(dev_version) if dev_version.endswith("-dev") else dev_version)
    date = args.date or _dt.date.today().isoformat()
    if not _RELEASE_VERSION_RE.match(version):
        print(f"[ERR] 目标版本 {version} 不是 X.Y.Z 发布版形态")
        return 2
    print(f"[..] 归档骨架初始化（v{version}）{'——试运行' if args.dry else ''}")
    try:
        actions = init_archive(_archive_ctx(version), version, date, dry=args.dry)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        return 2
    for action in actions:
        print(f"  [OK] {action}")
    if not actions:
        print("  [OK] 无需改动（骨架已就绪，幂等）")
    if not args.dry:
        rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], REPO_ROOT, runner)
        print((out or err).rstrip())
        if rc != 0:
            print("[ERR] 文档统计同步未通过，按上方提示处理后重跑")
            return rc
    print("[OK] 归档骨架就绪——下一步：release.py check")
    return 0


# ─────────────────────────── prepare ───────────────────────────


def cmd_prepare(args: argparse.Namespace, runner=None) -> int:
    constants_text = CONSTANTS_FILE.read_text(encoding="utf-8")
    dev_version = read_app_version(constants_text)
    derived = release_version_of(dev_version) if dev_version.endswith("-dev") else dev_version
    release_version = args.version or derived
    if args.version and args.version != derived:
        print(f"[ERR] --version {args.version} 与当前 {dev_version} 推导的发布版 {derived} 不一致")
        print(f"      prepare 不跨版本发布：发布版恒等于开发链推导值（{dev_version} → {derived}）。")
        print(f"      要发 {args.version}，先把开发链切到 {args.version}-dev，再跑不带 --version 的 prepare：")
        print(f"      ① 改 src/python/core/constants.py 的 APP_VERSION 为 {args.version}-dev")
        print("      ② 跑 .venv/bin/python scripts/check-version-consistency.py --fix（收口 15 处版本头）")
        print(f"      ③ 把 changelog 开发段头与 rf 台账「开发期已修复」节头改为 {args.version}-dev")
        print("      ④ 提交后依次跑 archive-init（首次进新小版本）→ check → prepare")
        return 2
    date = args.date or _dt.date.today().isoformat()

    print("[..] prepare 预检（发布形态前的开发态条件）")
    if not _print_results(run_preflight(REPO_ROOT, expect_release=False, runner=runner)):
        print("[ERR] 预检未通过，prepare 中止（未写入任何文件）")
        return 2

    main_text = CHANGELOG_FILE.read_text(encoding="utf-8")
    new_main, body_core = apply_changelog_release(main_text, release_version, date)
    archive_file, _ = archive_paths_for(release_version)
    write_archive_release(archive_file, release_version, date, body_core)
    CHANGELOG_FILE.write_text(new_main, encoding="utf-8")

    next_dev = next_dev_version_of(release_version)
    CONSTANTS_FILE.write_text(render_app_version(constants_text, release_version), encoding="utf-8")
    README_FILE.write_text(
        render_readme_version(README_FILE.read_text(encoding="utf-8"), release_version), encoding="utf-8"
    )
    print(f"[OK] 版本全链 → {release_version}（changelog 段迁入 {archive_file.name}，新开发段 {next_dev}）")

    rc, out, err = _exec([sys.executable, "scripts/check-version-consistency.py", "--fix"], REPO_ROOT, runner)
    print((out or err).rstrip())
    if rc != 0:
        print("[ERR] 版本一致性 --fix 未收敛，按上方 [ERR] 逐个处理后重跑 prepare")
        return rc

    # prepare 改写了 changelog/归档/版本头等多处文档，会改变 folders.md 统计表所依据的
    # 行数 → 立即同步，否则后续 refresh 的 bench（含 doc-drift crosscheck 单测）会因
    # 统计过期而红，被迫手动 sync 后重跑整套 bench
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], REPO_ROOT, runner)
    print((out or err).rstrip())
    if rc != 0:
        print("[ERR] 文档统计快照同步失败，按上方输出处理后重跑 prepare")
        return rc

    # 归档迁移（台账 + 设计文件）紧随版本全链之后自动执行：它改写的台账/目录树/索引
    # 与 changelog 同属「发布文档面」，人工漏做正是过去发布返工的最大来源（gate 断言兜底）
    if getattr(args, "no_archive", False):
        print("[!] 已跳过归档迁移（--no-archive）：gate 会拦截未迁档，需单独跑 scripts/release.py archive")
    else:
        started = time.perf_counter()
        rc = run_archive(date, runner=runner)
        _timer().mark_elapsed("台账归档迁移", started)
        if rc != 0:
            print("[ERR] 归档迁移未通过，按上方输出处理后重跑 prepare（或 --no-archive 跳过）")
            return rc

    rc, status_out, _ = _exec(["git", "status", "--short"], REPO_ROOT, runner)
    if rc == 0 and status_out.strip():
        print("\n[..] 本次改动清单（请审阅 diff）：")
        print(status_out.rstrip())
    print("\n[OK] prepare 完成。后续人工项：")
    print("  1. 审阅 git diff（重点：changelog 指针/归档索引、演进列头）")
    print("  2. 复核归档迁移结果（台账原表搬运 / 设计文件迁档判定——机械部分已自动完成）")
    print("  3. 按序继续：refresh → evolution --release → gate → publish → devbump")
    return 0


# ─────────────────────────── archive ───────────────────────────


def cmd_archive(args: argparse.Namespace, runner=None) -> int:
    """发布归档迁移的机械部分（条目内容是否该归档仍由人复核）。"""
    return run_archive(
        date=args.date or _dt.date.today().isoformat(),
        runner=runner,
        dry=bool(getattr(args, "dry_run", False)),
        skip_design_docs=bool(getattr(args, "skip_design_docs", False)),
    )


def run_archive(date: str, runner=None, dry: bool = False, skip_design_docs: bool = False) -> int:
    """台账 + 设计文件归档迁移（`prepare` 内置步；实现见 `_release/_archive_flow.py`）。"""
    version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))
    if version.endswith("-dev"):  # 版本形态校验先于路径推导（开发版推不出归档名）
        print(f"[ERR] 当前仍是开发版 {version} — 先跑 prepare 把版本全链切到发布形态，再归档")
        return 2
    return archive_flow(
        version=version,
        date=date,
        ctx=_archive_ctx(version),
        runner=runner,
        dry=dry,
        skip_design_docs=skip_design_docs,
    )


# ─────────────────────────── refresh ───────────────────────────

#: 判定「纯文档变更」的后缀白名单：文档正文 + 文档配图；其余后缀
#: （含 .py/.html/.ps1/.toml/.ini/.xlsx 等）一律视为程序/测试变更 → 必跑刷新
_DOC_ONLY_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".gif", ".svg")


def _last_release_tag(runner=None) -> str | None:
    """最近的发布 tag（v*）；无则 None（调用方保守地视为需刷新）。"""
    rc, out, _ = _git_ok(["describe", "--tags", "--abbrev=0", "--match", "v*"], REPO_ROOT, runner)
    tag = out.strip() if rc == 0 else ""
    return tag or None


def _docs_only_changes_since(tag: str, runner=None) -> tuple[bool, list[str]]:
    """自 tag 起（含未提交/未跟踪）的变更是否纯文档。

    Returns:
        (是否纯文档, 非文档后缀文件清单——空即纯文档)
        git 查询失败返回 (False, [])（保守：视同有程序变更，必跑刷新）。
    """
    rc1, out1, _ = _git_ok(["diff", "--name-only", tag], REPO_ROOT, runner)
    rc2, out2, _ = _git_ok(["ls-files", "--others", "--exclude-standard"], REPO_ROOT, runner)
    if rc1 != 0:
        return False, []
    changed = [ln.strip() for ln in out1.splitlines() if ln.strip()]
    if rc2 == 0:
        changed += [ln.strip() for ln in out2.splitlines() if ln.strip()]
    non_doc = sorted({f for f in changed if not f.endswith(_DOC_ONLY_SUFFIXES)})
    return (not non_doc), non_doc


def cmd_refresh(args: argparse.Namespace, runner=None) -> int:
    force = bool(getattr(args, "force_refresh", False))
    full_bench = bool(getattr(args, "full_bench", False))
    bench_scope = "bench" if full_bench else ",".join(RELEASE_BENCH_MODES)
    bench_label = (
        "测试量与耗时快照回填（全量模式）"
        if full_bench
        else f"测试量与耗时快照回填（发布子集 {len(RELEASE_BENCH_MODES)} 档，未测模式沿用上次实测）"
    )
    snapshot_steps: list[tuple[str, list[str]]] = [
        (bench_label, [sys.executable, "scripts/test-runner.py", "--mode", bench_scope, "--update-docs"]),
        ("测试收集计数回填", [sys.executable, "scripts/test-collect-coverage.py"]),
    ]
    if force:
        print("[..] --force-refresh：bench 与 collect 强制刷新")
        steps = list(snapshot_steps)
    else:
        tag = _last_release_tag(runner)
        if tag is None:
            print("[!] 未找到发布 tag，保守执行 bench 与 collect")
            pure_docs, non_doc = False, []
        else:
            pure_docs, non_doc = _docs_only_changes_since(tag, runner)
        if pure_docs:
            print(f"[OK] 自 {tag} 起仅文档变更，跳过 bench 与 collect（--force-refresh 强制）")
            steps = []
        else:
            shown = ", ".join(non_doc[:5]) + (" …" if len(non_doc) > 5 else "")
            print(f"[..] 自 {tag} 起存在程序/测试变更（{shown}），执行 bench 与 collect")
            steps = list(snapshot_steps)
    steps.append(("文档统计快照回写", [sys.executable, "scripts/check-doc-drift.py", "--sync"]))
    for label, cmd in steps:
        with _timer().step(label):
            rc = _run_step(label, cmd, REPO_ROOT, runner)
        if rc != 0:
            return rc
    if not full_bench and any("scripts/test-runner.py" in " ".join(cmd) for _, cmd in steps):
        print(
            f"[..] bench 只测发布子集 {', '.join(RELEASE_BENCH_MODES)}（其余模式耗时沿用上次实测；--full-bench 全量复测）"
        )
    print("[OK] refresh 完成")
    return 0


def _run_step(label: str, cmd: list[str], root: Path, runner=None) -> int:
    print(f"[..] {label}")
    rc, out, err = _exec(cmd, root, runner)
    if out.strip():
        print(out.rstrip())
    if rc != 0:
        if err.strip():
            print(err.rstrip())
        print(f"[ERR] {label} 退出码 {rc}（按输出处理后重跑本子命令）")
        return rc
    print(f"[OK] {label}")
    return 0


# ─────────────────────────── evolution ───────────────────────────


def cmd_evolution(args: argparse.Namespace, runner=None) -> int:
    print("[..] 版本演进快照（git 清单 + 逐文件行数）")
    started = time.perf_counter()
    stats = build_evolution_stats(REPO_ROOT, runner)
    _timer().mark_elapsed("演进快照统计", started)
    if stats["missing"]:
        print(f"[!] {stats['missing']} 个跟踪文件在工作区缺失（已跳过计数）")
    text = FOLDERS_FILE.read_text(encoding="utf-8")
    date = _dt.date.today().isoformat()
    try:
        text = update_evolution_table(text, stats, with_release=args.release, date=date)
        text = update_ratio_note(text, stats, with_release=args.release)
        text = update_case_note(text, stats)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        return 2
    FOLDERS_FILE.write_text(text, encoding="utf-8")

    # evolution 改写了 folders.md（演进表/比率/注释），会改变其统计表所依据的行数 → 立即
    # 同步，否则后续 publish 的 verify（含 doc-drift crosscheck 单测）会因统计过期而红
    started = time.perf_counter()
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], REPO_ROOT, runner)
    _timer().mark_elapsed("文档统计同步", started)
    print((out or err).rstrip())
    if rc != 0:
        print("[ERR] 文档统计快照同步失败，按上方输出处理后重跑本子命令")
        return rc

    scope = "发布列 + 当前开发版列" if args.release else "当前开发版列（发布列不动）"
    print(f"[OK] 演进对照已更新：{scope}（{date}）")
    print(
        "     摘要："
        + ", ".join(
            [
                f"主程序 {_fmt_pair(stats['main_files'], stats['main_lines'])}",
                f"测试 {_fmt_pair(stats['test_files'], stats['test_lines'])}",
                f"用例 {stats['def_test_lines']:,}（严格 {stats['def_test_strict']:,}）",
            ]
        )
    )
    print("[..] 需人工核对的注释行（脚本不代写）：")
    print("  - 用例口径注释中的 pytest 实际收集数与 opt-in live 项数（见 test-coverage.md）")
    print("  - 「文档」注释行的目录分解数（根/管理/手册/计划/归档）")
    return 0


# ─────────────────────────── gate ───────────────────────────


def _gate_workers() -> int:
    """十守护并行度：4 路封顶、随核数收敛——弱机器（如 2 核）自动降路，避免 CPU 超订反而拖慢总墙钟。"""
    return max(1, min(4, os.cpu_count() or 4))


def cmd_gate(args: argparse.Namespace, runner=None) -> int:
    print("[..] P2 门禁：演进对照新鲜度（当前开发版列头须今日刷新）")
    findings = check_evolution_freshness(FOLDERS_FILE.read_text(encoding="utf-8"), _dt.date.today().isoformat())
    if findings:
        for item in findings:
            print(f"[ERR] {item}")
        print("[ERR] 演进对照过期，先执行 scripts/release.py evolution 刷新后重跑 gate")
        return 2
    print("[OK] 演进对照新鲜度通过\n")

    print("[..] P2 门禁：归档迁移前置（该版本已解决表须已迁档且归档节存在）")
    version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))
    if version.endswith("-dev"):
        print(f"[ERR] 版本仍是开发版 {version} —— gate 须在 prepare 之后执行")
        return 2
    rf_archive, _ = ledger_archive_paths(version)
    status, pending = rf_archive_status(RF_FILE.read_text(encoding="utf-8"), version)
    if status == "pending":
        print(f"[ERR] review-findings 该版本仍有 {pending} 条已解决条目未迁档")
        print("[ERR] 先执行 scripts/release.py archive（或人工迁档）后重跑 gate")
        return 2
    if status == "archived":
        archived_ok = rf_archive.exists() and has_archive_section(rf_archive.read_text(encoding="utf-8"), version)
        if not archived_ok:
            print(f"[ERR] 主台账已留迁档占位，但 {rf_archive.name} 缺 `## v{version} 开发期已修复` 批次节")
            print("[ERR] 先执行 scripts/release.py archive（或人工迁档）后重跑 gate")
            return 2
    else:  # absent：本版没有自审条目，无待迁档内容
        print("[!] 该版本无「开发期已修复」节（无自审条目），跳过归档断言")
    print("[OK] 归档迁移前置通过\n")

    print("[..] P2 门禁：场景回归")
    started = time.perf_counter()
    rc, out, err = _exec([sys.executable, "scripts/test-runner.py", "--mode", "regression"], REPO_ROOT, runner)
    _timer().mark_elapsed("P2 场景回归", started)
    if out.strip():
        print(out.rstrip())
    if rc != 0:
        if err.strip():
            print(err.rstrip())
        print("[ERR] 场景回归未通过，P2 中止")
        return rc if rc != 0 else 1
    print("[OK] 场景回归通过\n")

    workers = _gate_workers()
    print(f"[..] P2 门禁：十守护 --ci（{workers} 路并行）")
    from concurrent.futures import ThreadPoolExecutor

    started = time.perf_counter()
    worst = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # 全部守护为 --ci 只读子进程（不写业务文件；结论缓存为每 namespace 独立
        # 文件、事实缓存为单文件，均原子 temp+rename 写，并行无互踩），按清单序
        # 收集结果，与串行版输出顺序一致，便于门禁日志对拍；并发度见 _gate_workers
        futures = [
            (script, pool.submit(_exec, [sys.executable, script, "--ci"], REPO_ROOT, runner))
            for script in GUARD_SCRIPTS
        ]
        for script, fut in futures:
            rc, out, err = fut.result()
            if rc == 0:
                print(f"  [OK] {Path(script).name}")
            else:
                print(f"  [ERR] {Path(script).name}（退出码 {rc}）")
                if out.strip():
                    print("    " + out.strip().replace("\n", "\n    "))
                if err.strip():
                    print("    " + err.strip().replace("\n", "\n    "))
                worst = max(worst, rc) if rc in (1, 2, 3) else 1
    _timer().mark_elapsed("P2 十守护", started, workers=workers)
    if worst:
        print("[ERR] P2 守护存在 finding，先修复再发布")
        return worst

    # 设计护栏（不入十守护清单——清单为 pre-commit/CI guards 五处同源硬约定；
    # 发布门禁域单独纳入：E 级拦 / W 级观察统计，开发期快反馈由 unit 测试承担）
    print("[..] P2 门禁：设计护栏（check-style-guardrails，E 级拦 / W 级观察统计）")
    started = time.perf_counter()
    rc, out, err = _exec([sys.executable, "scripts/check-style-guardrails.py", "--ci"], REPO_ROOT, runner)
    _timer().mark_elapsed("P2 设计护栏", started)
    if out.strip():
        print("  " + out.strip().replace("\n", "\n  "))
    if rc != 0:
        if err.strip():
            print("  " + err.strip().replace("\n", "\n  "))
        print("[ERR] 设计护栏未通过，P2 中止")
        return rc if rc in (1, 2, 3) else 1
    print("[OK] 设计护栏通过\n")

    print("[OK] P2 门禁全绿（演进新鲜度 + regression + 十守护 + 设计护栏）")
    return 0


# ─────────────────────────── publish / devbump ───────────────────────────


def _git_ok(args: list[str], root: Path, runner=None, capture: bool = True) -> tuple[int, str, str]:
    return _exec(["git", *args], root, runner, capture=capture)


def cmd_publish(args: argparse.Namespace, runner=None) -> int:
    print("[..] publish 预检（发布形态；工作树此时允许带 prepare 待提交改动）")
    if not _print_results(run_preflight(REPO_ROOT, expect_release=True, runner=runner, require_clean=False)):
        print("[ERR] 预检未通过，publish 中止")
        return 2
    release_version = read_app_version(CONSTANTS_FILE.read_text(encoding="utf-8"))

    # 提交前先按 pre-commit 钩子同源参数同步统计快照：钩子对「含 src/test 变更」的提交走
    # `--sync --ci --with-test-count`，而只跑 `--sync` 时 test-coverage.md 的收集派生计数
    # 不会被校验——本地「通过」、钩子里仍红，publish 白跑一轮（实测曾连败两次）。
    print("[..] 提交前统计快照同步（与 pre-commit 钩子同源参数）")
    started = time.perf_counter()
    rc, out, err = _exec(
        [sys.executable, "scripts/check-doc-drift.py", "--sync", "--ci", "--with-test-count"],
        REPO_ROOT,
        runner,
    )
    _timer().mark_elapsed("统计快照同步", started)
    if out.strip():
        print(out.rstrip())
    if rc != 0:
        if err.strip():
            print(err.rstrip())
        print("[ERR] 统计快照同步未通过 —— 先按上方提示修复（多为 test-coverage.md 收集计数陈旧）")
        return rc

    rc, staged, _ = _git_ok(["status", "--porcelain"], REPO_ROOT, runner)
    if rc != 0:
        return 1
    if staged.strip():
        _git_ok(["add", "-A"], REPO_ROOT, runner)
        rc, out, err = _git_ok(
            ["commit", "-m", f"release: v{release_version} —— {normalize_release_title(args.title)}"],
            REPO_ROOT,
            runner,
        )
        if rc != 0:
            print(f"[ERR] release 提交失败：{(err or out).strip()}")
            return rc
        print(f"[OK] release 提交完成（v{release_version}）")
    else:
        print("[OK] release 提交已存在，跳过")

    print("[..] P1 合入门禁：--mode verify")
    started = time.perf_counter()
    rc, out, err = _exec([sys.executable, "scripts/test-runner.py", "--mode", "verify"], REPO_ROOT, runner)
    _timer().mark_elapsed("P1 verify", started)
    if out.strip():
        print(out.rstrip())
    if rc != 0:
        if err.strip():
            print(err.rstrip())
        print("[ERR] P1 verify 未通过 —— 已停在 release 提交，修复后重跑 publish（提交步骤会自动跳过）")
        return rc
    counts = re.findall(r"(\d[\d,]*) 通过", out)
    passed = counts[-1].replace(",", "") if counts else ""
    print(f"[OK] P1 verify 通过（{passed or '见报告'} 项）")

    rc, out, err = _git_ok(["checkout", "master"], REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 切换 master 失败：{(err or out).strip()}")
        return rc
    merge_msg = (
        f"merge: dev → master，发布 v{release_version}（P1 verify {passed} 项已全绿）"
        if passed
        else f"merge: dev → master，发布 v{release_version}（P1 verify 全绿）"
    )
    rc, out, err = _git_ok(["merge", "--no-ff", "dev", "-m", merge_msg], REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 合并失败：{(err or out).strip()}")
        _git_ok(["checkout", "dev"], REPO_ROOT, runner)
        return rc
    print("[OK] dev → master 已合并（--no-ff）")

    rc, out, err = _git_ok(["tag", f"v{release_version}"], REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 打 tag 失败：{(err or out).strip()}")
        _git_ok(["checkout", "dev"], REPO_ROOT, runner)
        return rc
    print(f"[OK] tag v{release_version} 已打在 master 合并提交")

    _git_ok(["checkout", "dev"], REPO_ROOT, runner)
    if args.push:
        for push_args in (["push", "origin", "dev"], ["push", "origin", "master"], ["push", "origin", "--tags"]):
            rc, out, err = _git_ok(push_args, REPO_ROOT, runner, capture=True)
            if rc != 0:
                print(f"[ERR] git {' '.join(push_args)} 失败：{(err or out).strip()}")
                return rc
        print("[OK] dev / master / tags 已推送")
    else:
        print("[..] 未推送（默认）。确认后执行：")
        print("      git push origin dev && git push origin master && git push origin --tags")
    print("[OK] publish 完成 —— 最后执行 devbump 切开发版")
    return 0


def cmd_devbump(args: argparse.Namespace, runner=None) -> int:
    branch = _current_branch(REPO_ROOT, runner)
    if branch != "dev":
        print(f"[ERR] 当前分支 {branch or '<获取失败>'}，devbump 仅在 dev 上执行")
        return 2
    constants_text = CONSTANTS_FILE.read_text(encoding="utf-8")
    current = read_app_version(constants_text)
    if not _RELEASE_VERSION_RE.match(current):
        print(f"[ERR] 当前版本 {current} 不是发布形态 X.Y.Z（devbump 应在发布提交之后执行）")
        return 2
    release_version = current
    next_dev = next_dev_version_of(release_version)
    CONSTANTS_FILE.write_text(render_app_version(constants_text, next_dev), encoding="utf-8")
    README_FILE.write_text(render_readme_version(README_FILE.read_text(encoding="utf-8"), next_dev), encoding="utf-8")
    rc, out, err = _exec([sys.executable, "scripts/check-version-consistency.py", "--fix"], REPO_ROOT, runner)
    if rc != 0:
        print((out or err).rstrip())
        print("[ERR] 切版后版本一致性未收敛")
        return rc
    print(f"[OK] 版本全链 → {next_dev}")

    # 新开发周期：上一版的迁档占位节属过期信息（「本版已迁入归档档案」只对刚结束的
    # 发布周期有意义），连同空节一并清掉——归档正文与下方「归档档案」索引已记录全部版本
    rf_text = RF_FILE.read_text(encoding="utf-8")
    cleaned = drop_migration_placeholders(rf_text)
    if cleaned != rf_text:
        RF_FILE.write_text(cleaned, encoding="utf-8")
        print("[OK] review-findings：已清掉上一版迁档占位节（新周期台账从空开始）")

    _, staged, _ = _git_ok(["status", "--porcelain"], REPO_ROOT, runner)
    if staged.strip():
        _git_ok(["add", "-A"], REPO_ROOT, runner)
        rc, out, err = _git_ok(
            ["commit", "-m", f"chore: 切 {next_dev} 开发版本（v{release_version} 发布后）"],
            REPO_ROOT,
            runner,
        )
        if rc != 0:
            print(f"[ERR] 切版提交失败：{(err or out).strip()}")
            return rc
        print("[OK] 切版提交完成")
    if args.push:
        rc, out, err = _git_ok(["push", "origin", "dev"], REPO_ROOT, runner)
        if rc != 0:
            print(f"[ERR] push 失败：{(err or out).strip()}")
            return rc
        print("[OK] dev 已推送")
    else:
        print("[..] 未推送（默认）。确认后执行：git push origin dev")
    return 0


# ─────────────────────────── CLI ───────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release.py",
        description="发布流程分步编排（每步独立可审阅、失败即停；详见模块文档字符串与 developer-guide）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="预检：分支/工作树/版本形态/tag/版本一致性")

    p_prepare = sub.add_parser("prepare", help="版本全链 + changelog 发布段归档 + 一致性 --fix + 台账/设计文件归档迁移")
    p_prepare.add_argument("--version", help="目标发布版（默认按 APP_VERSION 推导）")
    p_prepare.add_argument("--date", help="发布日期 YYYY-MM-DD（默认今天）")
    p_prepare.add_argument("--no-archive", action="store_true", help="跳过自动归档迁移（需单独跑 archive）")

    p_archive = sub.add_parser(
        "archive", help="台账归档迁移：rf 已解决表原表搬入归档 + plan 已完成节 + docs/plan 已完成设计文件"
    )
    p_archive.add_argument("--date", help="发布日（缺省今天）")
    p_archive.add_argument("--dry-run", action="store_true", help="只报告动作，不写任何文件")
    p_archive.add_argument("--skip-design-docs", action="store_true", help="跳过 docs/plan 设计文件迁档（只做台账）")

    p_archive_init = sub.add_parser(
        "archive-init", help="新小版本归档骨架初始化（三份归档 + 目录树块 + 三处索引行，幂等）"
    )
    p_archive_init.add_argument("--version", default=None, help="目标发布版（默认按 APP_VERSION 推导）")
    p_archive_init.add_argument("--date", default=None, help="发布日期 YYYY-MM-DD（默认今天）")
    p_archive_init.add_argument("--dry", action="store_true", help="只报告将做的改动，不落盘")

    p_refresh = sub.add_parser(
        "refresh",
        help="数据刷新：bench（发布子集）--update-docs + collect + doc-drift --sync（纯文档变更自动跳过前两者）",
    )
    p_refresh.add_argument("--force-refresh", action="store_true", help="忽略纯文档变更判定，强制刷新 bench 与 collect")
    p_refresh.add_argument(
        "--full-bench",
        action="store_true",
        help=f"bench 跑全量模式（默认只测发布子集 {', '.join(RELEASE_BENCH_MODES)}，未测模式耗时沿用上次实测）",
    )

    p_evolution = sub.add_parser("evolution", help="版本演进对照快照（默认只滚当前开发版列）")
    p_evolution.add_argument("--release", action="store_true", help="发布期使用：发布列与增长比一并写入")

    sub.add_parser("gate", help="P2 门禁：演进新鲜度 + regression + 十守护 --ci + 设计护栏")

    p_publish = sub.add_parser("publish", help="release 提交 + P1 verify + --no-ff 合并 + tag")
    p_publish.add_argument("--title", required=True, help="release 提交主题（changelog 摘要式短描述）")
    p_publish.add_argument("--push", action="store_true", help="完成后推送 dev/master/tags（默认只打印命令）")

    p_devbump = sub.add_parser("devbump", help="切下一开发版并提交")
    p_devbump.add_argument("--push", action="store_true", help="完成后推送 dev（默认只打印命令）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "check": cmd_check,
        "prepare": cmd_prepare,
        "archive": cmd_archive,
        "archive-init": cmd_archive_init,
        "refresh": cmd_refresh,
        "evolution": cmd_evolution,
        "gate": cmd_gate,
        "publish": cmd_publish,
        "devbump": cmd_devbump,
    }
    _reset_timer()
    try:
        rc = handlers[args.command](args)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        rc = 2
    _finish_timing(args.command, rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
