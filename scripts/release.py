#!/usr/bin/env python3
"""发布流程分步编排脚本 —— 把发布口径从文档散文固化为可执行子命令。

七个分步子命令（每步独立可审阅、失败即停不连锁，按序执行）：

    check      预检：分支 / 工作树干净 / 版本形态 / tag 未占用 / 版本一致性
    prepare    文档手术：版本全链（constants + README + --fix 传播）+ changelog
               发布段迁入归档、指针与归档索引改写（changelog 段由本步自动完成）；
               rf 已解决条目 / plan 已完成任务 / docs/plan 已完成任务设计文件三项归档迁移为
               人工强制项（未完成不得继续 gate/publish）
    refresh    数据刷新：bench --update-docs + collect-test-coverage + doc-drift --sync
               （自上一 release tag 起仅文档变更时跳过 bench 与 collect，
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
    .venv/bin/python scripts/release.py refresh
    .venv/bin/python scripts/release.py evolution --release
    .venv/bin/python scripts/release.py gate
    .venv/bin/python scripts/release.py publish --title "<发布主题>"
    .venv/bin/python scripts/release.py devbump

退出码：0 = 通过；2 = 预检/门禁发现（与守护脚本 CLI 契约一致）；1 = 执行失败。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_FILE = REPO_ROOT / "src" / "python" / "core" / "constants.py"
README_FILE = REPO_ROOT / "README.md"
# 文档树路径（本脚本自包含不依赖 _checklib，常量语义与其同名项一致）
_MANAGEMENTS_DIR = REPO_ROOT / "docs" / "managements"
_ARCHIVE_DOCS_DIR = REPO_ROOT / "docs" / "archive"
CHANGELOG_FILE = _MANAGEMENTS_DIR / "changelog.md"
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

# ── 内部实现拆分（_release/ 包）：入口保留 CLI 面与路径常量，测试引用的符号原名 re-export ──
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享设施（_release 包）
from _release._changelog_archive import (  # noqa: E402, F401 — _SECTION_NOTE 供测试经入口模块引用
    SECTION_NOTE as _SECTION_NOTE,
    apply_changelog_release,
    render_archive_header,
    write_archive_release,
)
from _release._common import ReleaseError, exec_command as _exec  # noqa: E402
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


def archive_paths_for(release_version: str) -> tuple[Path, str]:
    """按小版本推导归档目录与文件名（小版本号 → docs/archive/vX.Y.x/… 目录）。"""
    m = _RELEASE_VERSION_RE.match(release_version)
    if not m:
        raise ReleaseError(f"{release_version} 不是 X.Y.Z 发布版形态")
    minor = f"{m.group(1)}.{m.group(2)}"
    name = f"archived_changelog.{minor}.x.md"
    return _ARCHIVE_DOCS_DIR / f"v{minor}.x" / name, name


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


def cmd_check(args: argparse.Namespace, runner=None) -> int:
    print("[..] 发布预检")
    ok = _print_results(run_preflight(REPO_ROOT, expect_release=False, runner=runner))
    if not ok:
        print("[ERR] 预检未通过，先处理上述项再继续")
        return 2
    print("[OK] 预检通过 — 可执行 prepare")
    return 0


# ─────────────────────────── prepare ───────────────────────────


def cmd_prepare(args: argparse.Namespace, runner=None) -> int:
    constants_text = CONSTANTS_FILE.read_text(encoding="utf-8")
    dev_version = read_app_version(constants_text)
    release_version = args.version or release_version_of(dev_version)
    if args.version and args.version != release_version_of(dev_version):
        print(f"[!] --version {args.version} 与当前 {dev_version} 推导结果 {release_version} 不一致，按推导执行")
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

    rc, status_out, _ = _exec(["git", "status", "--short"], REPO_ROOT, runner)
    if rc == 0 and status_out.strip():
        print("\n[..] 本次改动清单（请审阅 diff）：")
        print(status_out.rstrip())
    print("\n[OK] prepare 完成。后续人工项：")
    print("  1. 审阅 git diff（重点：changelog 指针/归档索引、演进列头）")
    print(
        "  2. 发布归档迁移（强制）：rf 已解决条目 + plan 已完成任务 + docs/plan 已完成任务设计文件迁档（changelog 段已由本步自动完成），未完成不得继续 gate/publish"
    )
    print("  3. 按序继续：refresh → evolution --release → gate → publish → devbump")
    return 0


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
    snapshot_steps: list[tuple[str, list[str]]] = [
        (
            "测试量与耗时快照回填",
            [sys.executable, "scripts/test-runner.py", "--mode", "bench", "--update-docs"],
        ),
        ("测试收集计数回填", [sys.executable, "scripts/collect-test-coverage.py"]),
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
        rc = _run_step(label, cmd, REPO_ROOT, runner)
        if rc != 0:
            return rc
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
    stats = build_evolution_stats(REPO_ROOT, runner)
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
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], REPO_ROOT, runner)
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

    print("[..] P2 门禁：场景回归")
    rc, out, err = _exec([sys.executable, "scripts/test-runner.py", "--mode", "regression"], REPO_ROOT, runner)
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
    if worst:
        print("[ERR] P2 守护存在 finding，先修复再发布")
        return worst

    # 设计护栏（不入十守护清单——清单为 pre-commit/CI guards 五处同源硬约定；
    # 发布门禁域单独纳入：E 级拦 / W 级观察统计，开发期快反馈由 unit 测试承担）
    print("[..] P2 门禁：设计护栏（check-style-guardrails，E 级拦 / W 级观察统计）")
    rc, out, err = _exec([sys.executable, "scripts/check-style-guardrails.py", "--ci"], REPO_ROOT, runner)
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
    rc, out, err = _exec([sys.executable, "scripts/test-runner.py", "--mode", "verify"], REPO_ROOT, runner)
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

    p_prepare = sub.add_parser("prepare", help="版本全链 + changelog 发布段归档 + 一致性 --fix")
    p_prepare.add_argument("--version", help="目标发布版（默认按 APP_VERSION 推导）")
    p_prepare.add_argument("--date", help="发布日期 YYYY-MM-DD（默认今天）")

    p_refresh = sub.add_parser(
        "refresh", help="数据刷新：bench --update-docs + collect + doc-drift --sync（纯文档变更自动跳过前两者）"
    )
    p_refresh.add_argument("--force-refresh", action="store_true", help="忽略纯文档变更判定，强制刷新 bench 与 collect")

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
        "refresh": cmd_refresh,
        "evolution": cmd_evolution,
        "gate": cmd_gate,
        "publish": cmd_publish,
        "devbump": cmd_devbump,
    }
    try:
        return handlers[args.command](args)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
