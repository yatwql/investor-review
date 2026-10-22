"""发布准备阶段命令 — check / archive-init / prepare / archive。

路径与共用原语经 `env` 投影取（入口 `scripts/release.py` 声明路径常量）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
import time

from _release._archive_flow import ArchiveContext, run_archive as archive_flow  # noqa: F401
from _release._archive_init import init_archive
from _release._changelog_archive import apply_changelog_release, write_archive_release
from _release._commands_base import (
    _print_results,
    _timer,
    ledger_archive_paths,  # noqa: F401 — prepare/check 共用
)
from _release._common import ReleaseError, exec_command as _exec
from _release._versioning import (
    RELEASE_VERSION_RE as _RELEASE_VERSION_RE,
    next_dev_version_of,
    read_app_version,
    release_version_of,
    render_app_version,
    render_readme_version,
)


def cmd_check(args: argparse.Namespace, env, runner=None) -> int:
    print("[..] 发布预检")
    ok = _print_results(env.run_preflight(env.REPO_ROOT, expect_release=False, runner=runner))
    if not ok:
        print("[ERR] 预检未通过，先处理上述项再继续")
        return 2
    dev_version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    release_version = dev_version if not dev_version.endswith("-dev") else release_version_of(dev_version)
    findings = env.archive_prerequisites(release_version)
    if findings:
        for finding in findings:
            print(f"[ERR] {finding}")
        print(f"[ERR] v{release_version} 归档前置未就绪，先补齐再执行 prepare")
        return 2
    print(f"[OK] 归档前置就绪（v{release_version} 台账归档与目录树块）")
    print("[OK] 预检通过 — 可执行 prepare")
    return 0


def cmd_archive_init(args: argparse.Namespace, env, runner=None) -> int:
    """新小版本归档骨架初始化：三份归档文件 + 目录树块 + 三处索引行（幂等）。"""
    dev_version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    version = args.version or (release_version_of(dev_version) if dev_version.endswith("-dev") else dev_version)
    date = args.date or _dt.date.today().isoformat()
    if not _RELEASE_VERSION_RE.match(version):
        print(f"[ERR] 目标版本 {version} 不是 X.Y.Z 发布版形态")
        return 2
    print(f"[..] 归档骨架初始化（v{version}）{'——试运行' if args.dry else ''}")
    try:
        actions = init_archive(env.archive_ctx(version), version, date, dry=args.dry)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        return 2
    for action in actions:
        print(f"  [OK] {action}")
    if not actions:
        print("  [OK] 无需改动（骨架已就绪，幂等）")
    if not args.dry:
        rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], env.REPO_ROOT, runner)
        print((out or err).rstrip())
        if rc != 0:
            print("[ERR] 文档统计同步未通过，按上方提示处理后重跑")
            return rc
    print("[OK] 归档骨架就绪——下一步：release.py check")
    return 0


def cmd_prepare(args: argparse.Namespace, env, runner=None) -> int:
    constants_text = env.CONSTANTS_FILE.read_text(encoding="utf-8")
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
    if not _print_results(env.run_preflight(env.REPO_ROOT, expect_release=False, runner=runner)):
        print("[ERR] 预检未通过，prepare 中止（未写入任何文件）")
        return 2

    main_text = env.CHANGELOG_FILE.read_text(encoding="utf-8")
    new_main, body_core = apply_changelog_release(main_text, release_version, date)
    archive_file, _ = env.archive_paths_for(release_version)
    write_archive_release(archive_file, release_version, date, body_core)
    env.CHANGELOG_FILE.write_text(new_main, encoding="utf-8")

    next_dev = next_dev_version_of(release_version)
    env.CONSTANTS_FILE.write_text(render_app_version(constants_text, release_version), encoding="utf-8")
    env.README_FILE.write_text(
        render_readme_version(env.README_FILE.read_text(encoding="utf-8"), release_version), encoding="utf-8"
    )
    print(f"[OK] 版本全链 → {release_version}（changelog 段迁入 {archive_file.name}，新开发段 {next_dev}）")

    rc, out, err = _exec([sys.executable, "scripts/check-version-consistency.py", "--fix"], env.REPO_ROOT, runner)
    print((out or err).rstrip())
    if rc != 0:
        print("[ERR] 版本一致性 --fix 未收敛，按上方 [ERR] 逐个处理后重跑 prepare")
        return rc

    # prepare 改写了 changelog/归档/版本头等多处文档，会改变 folders.md 统计表所依据的
    # 行数 → 立即同步，否则后续 refresh 的 bench（含 doc-drift crosscheck 单测）会因
    # 统计过期而红，被迫手动 sync 后重跑整套 bench
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], env.REPO_ROOT, runner)
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
        rc = run_archive(date, env, runner=runner)
        _timer().mark_elapsed("台账归档迁移", started)
        if rc != 0:
            print("[ERR] 归档迁移未通过，按上方输出处理后重跑 prepare（或 --no-archive 跳过）")
            return rc

    rc, status_out, _ = _exec(["git", "status", "--short"], env.REPO_ROOT, runner)
    if rc == 0 and status_out.strip():
        print("\n[..] 本次改动清单（请审阅 diff）：")
        print(status_out.rstrip())
    print("\n[OK] prepare 完成。后续人工项：")
    print("  1. 审阅 git diff（重点：changelog 指针/归档索引、演进列头）")
    print("  2. 复核归档迁移结果（台账原表搬运 / 设计文件迁档判定——机械部分已自动完成）")
    print("  3. 按序继续：refresh → evolution --release → gate → publish → devbump")
    return 0


def cmd_archive(args: argparse.Namespace, env, runner=None) -> int:
    """发布归档迁移的机械部分（条目内容是否该归档仍由人复核）。"""
    return run_archive(
        date=args.date or _dt.date.today().isoformat(),
        env=env,
        runner=runner,
        dry=bool(getattr(args, "dry_run", False)),
        skip_design_docs=bool(getattr(args, "skip_design_docs", False)),
    )


def run_archive(date: str, env, runner=None, dry: bool = False, skip_design_docs: bool = False) -> int:
    """台账 + 设计文件归档迁移（`prepare` 内置步；实现见 `_release/_archive_flow.py`）。"""
    version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))
    if version.endswith("-dev"):  # 版本形态校验先于路径推导（开发版推不出归档名）
        print(f"[ERR] 当前仍是开发版 {version} — 先跑 prepare 把版本全链切到发布形态，再归档")
        return 2
    return archive_flow(
        version=version,
        date=date,
        ctx=env.archive_ctx(version),
        runner=runner,
        dry=dry,
        skip_design_docs=skip_design_docs,
    )
