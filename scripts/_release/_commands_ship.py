"""发布交付阶段命令 — refresh / evolution / publish / devbump。

路径与共用原语经 `env` 投影取（入口 `scripts/release.py` 声明路径常量）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import time

from _release._cli import RELEASE_BENCH_MODES
from _release._commands_base import (
    _changed_code_files,
    _code_fingerprint,
    _print_results,
    _current_branch,
    _docs_only_changes_since,
    _gate_stamp_matches,
    _git_ok,
    _last_release_tag,
    _read_gate_stamp,
    _run_step,
    _timer,
    _write_bench_stamp,
)
from _release._common import ReleaseError, exec_command as _exec
from _release._evolution import (
    build_evolution_stats,
    fmt_pair as _fmt_pair,
    update_case_note,
    update_evolution_table,
    update_ratio_note,
)
from _release._hygiene import clean_stale_bytecode
from _release._ledger_archive import drop_migration_placeholders
from _release._versioning import (
    RELEASE_VERSION_RE as _RELEASE_VERSION_RE,
    next_dev_version_of,
    normalize_release_title,
    read_app_version,
    render_app_version,
    render_readme_version,
)


def cmd_refresh(args: argparse.Namespace, env, runner=None) -> int:
    force = bool(getattr(args, "force_refresh", False))
    full_bench = bool(getattr(args, "full_bench", False))
    bench_scope = "bench" if full_bench else ",".join(RELEASE_BENCH_MODES)
    bench_jobs = getattr(args, "bench_jobs", None)
    bench_label = (
        "测试量与耗时快照回填（全量模式）"
        if full_bench
        else f"测试量与耗时快照回填（发布子集 {len(RELEASE_BENCH_MODES)} 档，未测模式沿用上次实测）"
    )
    snapshot_steps: list[tuple[str, list[str]]] = [
        (
            bench_label if not bench_jobs else f"{bench_label}，并行度 {bench_jobs}",
            [
                sys.executable,
                "scripts/test-runner.py",
                "--mode",
                bench_scope,
                "--update-docs",
                # 发布前快速反馈：首个失败即停，失败用例名随 runner 输出直达
                "--fail-fast",
            ]
            + (["--jobs", str(bench_jobs)] if bench_jobs else []),
        ),
        ("测试收集计数回填", [sys.executable, "scripts/test-collect-coverage.py"]),
    ]
    if force:
        print("[..] --force-refresh：bench 与 collect 强制刷新")
        steps = list(snapshot_steps)
    else:
        tag = _last_release_tag(env, runner)
        if tag is None:
            print("[!] 未找到发布 tag，保守执行 bench 与 collect")
            pure_docs, non_doc = False, []
        else:
            pure_docs, non_doc = _docs_only_changes_since(tag, env, runner)
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
            rc = _run_step(label, cmd, env.REPO_ROOT, runner)
        if rc != 0:
            return rc
    bench_cmd = next((cmd for label, cmd in steps if "scripts/test-runner.py" in " ".join(cmd)), None)
    if bench_cmd is not None:
        # bench 实跑（含 unit 档 = verify 严格超集）且全部退出 0 → 写通过戳，
        # 供 gate 跳过重复 verify；纯文档跳过 bench 时无戳，gate 照常实跑
        modes = list(RELEASE_BENCH_MODES) if not full_bench else ["bench"]
        _write_bench_stamp(_code_fingerprint(env, runner), modes, covers_unit=full_bench or "unit" in modes, env=env)
        print("[OK] bench 通过戳已写入（gate 可凭代码指纹复用该次 unit 结果替代 P1 verify）")

    if not full_bench and any("scripts/test-runner.py" in " ".join(cmd) for _, cmd in steps):
        print(
            f"[..] bench 只测发布子集 {', '.join(RELEASE_BENCH_MODES)}（其余模式耗时沿用上次实测；--full-bench 全量复测）"
        )
    # 本地卫生（最佳努力）：模块改名/删除后遗留的陈旧 .pyc 不会被 Python 回收，
    # 会让 rg / traceback 里出现旧文件名与旧路径；清掉后下次导入自动重建。
    hygiene = clean_stale_bytecode(env.REPO_ROOT)
    if hygiene["files"]:
        print(f"[OK] 陈旧字节码清理：删除 {hygiene['files']} 个 .pyc、{hygiene['dirs']} 个空 __pycache__ 目录")
    else:
        print("[OK] 陈旧字节码：无（__pycache__ 与源文件一致）")

    print("[OK] refresh 完成")
    return 0


def cmd_evolution(args: argparse.Namespace, env, runner=None) -> int:
    print("[..] 版本演进快照（git 清单 + 逐文件行数）")
    started = time.perf_counter()
    stats = build_evolution_stats(env.REPO_ROOT, runner)
    _timer().mark_elapsed("演进快照统计", started)
    if stats["missing"]:
        print(f"[!] {stats['missing']} 个跟踪文件在工作区缺失（已跳过计数）")
    text = env.FOLDERS_FILE.read_text(encoding="utf-8")
    date = _dt.date.today().isoformat()
    try:
        text = update_evolution_table(text, stats, with_release=args.release, date=date)
        text = update_ratio_note(text, stats, with_release=args.release)
        text = update_case_note(text, stats)
    except ReleaseError as exc:
        print(f"[ERR] {exc}")
        return 2
    env.FOLDERS_FILE.write_text(text, encoding="utf-8")

    # evolution 改写了 folders.md（演进表/比率/注释），会改变其统计表所依据的行数 → 立即
    # 同步，否则后续 publish 的 verify（含 doc-drift crosscheck 单测）会因统计过期而红
    started = time.perf_counter()
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], env.REPO_ROOT, runner)
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
    print("[OK] 注释行核对：用例口径（grep/严格）已回写；pytest 收集数与「文档」目录分解数")
    print("     分别由 check-doc-drift 的计数行校验与目录树双向比对兜底，不再人工核对")
    return 0


def cmd_publish(args: argparse.Namespace, env, runner=None) -> int:
    print("[..] publish 预检（发布形态；工作树此时允许带 prepare 待提交改动）")
    if not _print_results(env.run_preflight(env.REPO_ROOT, expect_release=True, runner=runner, require_clean=False)):
        print("[ERR] 预检未通过，publish 中止")
        return 2
    release_version = read_app_version(env.CONSTANTS_FILE.read_text(encoding="utf-8"))

    # 提交前先按 pre-commit 钩子同源参数同步统计快照：钩子对「含 src/test 变更」的提交走
    # `--sync --ci --with-test-count`，而只跑 `--sync` 时 test-coverage.md 的收集派生计数
    # 不会被校验——本地「通过」、钩子里仍红，publish 白跑一轮（实测曾连败两次）。
    print("[..] 提交前统计快照同步（与 pre-commit 钩子同源参数）")
    started = time.perf_counter()
    rc, out, err = _exec(
        [sys.executable, "scripts/check-doc-drift.py", "--sync", "--ci", "--with-test-count"],
        env.REPO_ROOT,
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

    rc, staged, _ = _git_ok(["status", "--porcelain"], env.REPO_ROOT, runner)
    if rc != 0:
        return 1
    commit_started = time.perf_counter()
    if staged.strip():
        _git_ok(["add", "-A"], env.REPO_ROOT, runner)
        rc, out, err = _git_ok(
            ["commit", "-m", f"release: v{release_version} —— {normalize_release_title(args.title)}"],
            env.REPO_ROOT,
            runner,
        )
        if rc != 0:
            print(f"[ERR] release 提交失败：{(err or out).strip()}")
            return rc
        _timer().mark_elapsed("release 提交", commit_started)
        print(f"[OK] release 提交完成（v{release_version}）")
    else:
        _timer().mark_elapsed("release 提交（无需提交）", commit_started)
        print("[OK] release 提交已存在，跳过")

    fingerprint = _code_fingerprint(env, runner)
    stamp = _gate_stamp_matches(release_version, fingerprint, env)
    if stamp:
        passed = str(stamp.get("verify_passed") or "")
        print(f"[OK] 复用 gate 阶段的 P1 verify（树指纹一致 {fingerprint[:12]}…，{passed or '项数见 gate 输出'} 项）")
    else:
        # 说清「为什么重跑」：gate 绿了之后再改代码/测试/脚本，旧结论就不再覆盖当前树
        previous = _read_gate_stamp(env)
        if previous is None:
            print("[..] P1 合入门禁：--mode verify（尚无 gate 通过戳，实跑）")
        else:
            changed = _changed_code_files(env, previous, runner)
            shown = "、".join(changed[:5]) + (" …" if len(changed) > 5 else "")
            detail = f"（gate {previous.get('ts', '?')}）"
            if changed:
                print(f"[!] 自上次 gate {detail}后有 {len(changed)} 个代码文件改动：{shown}")
            else:
                print(f"[!] 代码指纹与上次 gate {detail}不一致（gate 后代码/测试/脚本有变动）")
            print("[..] gate 结论只对当时代码树有效 → 实跑 P1 verify（不是白跑）")
        started = time.perf_counter()
        rc, out, err = _exec([sys.executable, "scripts/test-runner.py", "--mode", "verify"], env.REPO_ROOT, runner)
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

    merge_started = time.perf_counter()
    rc, out, err = _git_ok(["checkout", "master"], env.REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 切换 master 失败：{(err or out).strip()}")
        return rc
    merge_msg = (
        f"merge: dev → master，发布 v{release_version}（P1 verify {passed} 项已全绿）"
        if passed
        else f"merge: dev → master，发布 v{release_version}（P1 verify 全绿）"
    )
    rc, out, err = _git_ok(["merge", "--no-ff", "dev", "-m", merge_msg], env.REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 合并失败：{(err or out).strip()}")
        _git_ok(["checkout", "dev"], env.REPO_ROOT, runner)
        return rc
    _timer().mark_elapsed("合并到 master", merge_started)
    print("[OK] dev → master 已合并（--no-ff）")

    tag_started = time.perf_counter()
    rc, out, err = _git_ok(["tag", f"v{release_version}"], env.REPO_ROOT, runner)
    if rc != 0:
        print(f"[ERR] 打 tag 失败：{(err or out).strip()}")
        _git_ok(["checkout", "dev"], env.REPO_ROOT, runner)
        return rc
    _timer().mark_elapsed("打 tag", tag_started)
    print(f"[OK] tag v{release_version} 已打在 master 合并提交")

    _git_ok(["checkout", "dev"], env.REPO_ROOT, runner)
    if args.push:
        push_started = time.perf_counter()
        for push_args in (["push", "origin", "dev"], ["push", "origin", "master"], ["push", "origin", "--tags"]):
            rc, out, err = _git_ok(push_args, env.REPO_ROOT, runner, capture=True)
            if rc != 0:
                print(f"[ERR] git {' '.join(push_args)} 失败：{(err or out).strip()}")
                return rc
        _timer().mark_elapsed("推送 dev/master/tags", push_started)
        print("[OK] dev / master / tags 已推送")
    else:
        print("[..] 未推送（默认）。确认后执行：")
        print("      git push origin dev && git push origin master && git push origin --tags")
    print("[OK] publish 完成 —— 最后执行 devbump 切开发版")
    return 0


def cmd_devbump(args: argparse.Namespace, env, runner=None) -> int:
    branch = _current_branch(env.REPO_ROOT, runner)
    if branch != "dev":
        print(f"[ERR] 当前分支 {branch or '<获取失败>'}，devbump 仅在 dev 上执行")
        return 2
    constants_text = env.CONSTANTS_FILE.read_text(encoding="utf-8")
    current = read_app_version(constants_text)
    if not _RELEASE_VERSION_RE.match(current):
        print(f"[ERR] 当前版本 {current} 不是发布形态 X.Y.Z（devbump 应在发布提交之后执行）")
        return 2
    release_version = current
    next_dev = next_dev_version_of(release_version)
    env.CONSTANTS_FILE.write_text(render_app_version(constants_text, next_dev), encoding="utf-8")
    env.README_FILE.write_text(
        render_readme_version(env.README_FILE.read_text(encoding="utf-8"), next_dev), encoding="utf-8"
    )
    rc, out, err = _exec([sys.executable, "scripts/check-version-consistency.py", "--fix"], env.REPO_ROOT, runner)
    if rc != 0:
        print((out or err).rstrip())
        print("[ERR] 切版后版本一致性未收敛")
        return rc
    print(f"[OK] 版本全链 → {next_dev}")

    # 新开发周期：上一版的迁档占位节属过期信息（「本版已迁入归档档案」只对刚结束的
    # 发布周期有意义），连同空节一并清掉——归档正文与下方「归档档案」索引已记录全部版本
    rf_text = env.RF_FILE.read_text(encoding="utf-8")
    cleaned = drop_migration_placeholders(rf_text)
    if cleaned != rf_text:
        env.RF_FILE.write_text(cleaned, encoding="utf-8")
        print("[OK] review-findings：已清掉上一版迁档占位节（新周期台账从空开始）")

    _, staged, _ = _git_ok(["status", "--porcelain"], env.REPO_ROOT, runner)
    if staged.strip():
        _git_ok(["add", "-A"], env.REPO_ROOT, runner)
        rc, out, err = _git_ok(
            ["commit", "-m", f"chore: 切 {next_dev} 开发版本（v{release_version} 发布后）"],
            env.REPO_ROOT,
            runner,
        )
        if rc != 0:
            print(f"[ERR] 切版提交失败：{(err or out).strip()}")
            return rc
        print("[OK] 切版提交完成")
    # 默认推送：发布闭环的收尾就是把切版提交同步到远端（本地领先会让下个发布周期
    # 的 push/合并口径不一致）；需要本地先复核时用 `--no-push`
    if getattr(args, "push", True):
        rc, out, err = _git_ok(["push", "origin", "dev"], env.REPO_ROOT, runner)
        if rc != 0:
            print(f"[ERR] push 失败：{(err or out).strip()}")
            print("[..] 切版提交已落盘，网络恢复后重试：git push origin dev（或 --no-push 跳过）")
            return rc
        print("[OK] dev 已推送")
    else:
        print("[..] 未推送（--no-push）。确认后执行：git push origin dev")
    return 0
