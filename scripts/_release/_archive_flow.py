"""台账归档迁移的命令编排（`prepare` 内置步 / `archive` 子命令共用）。

设计纪律（同 `_release/` 其他下沉模块）：只收**显式参数**——路径由调用方以
`ArchiveContext` 传入，本模块不读入口模块的路径常量，保证测试对入口模块属性的
重定向始终生效（`release.py` 在调用点取模块常量组装 ctx）。

流程把控（先算后写）：纯函数算出全部结果 → 设计文件先迁（目录树 → `git mv` →
引用改写，`git mv` 失败回滚目录树）→ 台账最后落盘；任一步失败即中止且台账原样，
不留「表已搬走、归档没写成」的半迁移。归档变换本身幂等，补好前置后重跑即可。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from _release._common import ReleaseError, exec_command as _exec
from _release._ledger_archive import (
    apply_plan_archive,
    apply_rf_archive,
    archive_header_findings,
    design_doc_candidates,
    move_tree_entry,
    open_ids,
    rewrite_doc_refs,
    unreferenced_docs,
)


@dataclass(frozen=True)
class ArchiveContext:
    """归档迁移涉及的全部路径（由入口按当前模块常量组装，便于测试重定向）。"""

    repo_root: Path
    rf_file: Path
    plan_file: Path
    folders_file: Path
    changelog_file: Path
    readme_file: Path
    claude_file: Path
    plan_docs_dir: Path
    rf_archive: Path
    plan_archive: Path


def prerequisite_findings(release_version: str, ctx: ArchiveContext) -> list[str]:
    """发布归档的前置条件：两份台账归档文件 + folders.md 的该小版本归档子树块。

    新小版本（vX.Y.0）首份归档需先建文件与目录树块；在 `check` 阶段就报出，
    避免发布跑到 `prepare` 中途才因缺件中止（那时版本全链已改、需回滚）。
    """
    findings: list[str] = []
    for path in (ctx.rf_archive, ctx.plan_archive):
        if not path.exists():
            findings.append(f"归档文件不存在：{path.relative_to(ctx.repo_root).as_posix()}（新小版本首份归档需先建）")
    minor = release_version.rsplit(".", 1)[0]
    folders = ctx.folders_file.read_text(encoding="utf-8") if ctx.folders_file.exists() else ""
    if f"v{minor}.x/" not in folders:
        findings.append(f"folders.md 目录树缺 `v{minor}.x/` 归档子树块（新小版本需先在归档子树补该目录块）")
    return findings


def _rewrite_refs_in(target: Path, old_bases: tuple[str, ...], new_ref: str) -> int:
    """把 target 内对设计文件的引用改指新路径；返回改写次数。"""
    if not target.exists():
        return 0
    text = target.read_text(encoding="utf-8")
    total = 0
    for base in old_bases:
        text, n = rewrite_doc_refs(text, base, new_ref)
        total += n
    if total:
        target.write_text(text, encoding="utf-8")
    return total


def run_archive(
    *, version: str, date: str, ctx: ArchiveContext, runner=None, dry: bool = False, skip_design_docs: bool = False
) -> int:
    """台账 + 设计文件归档迁移。调用方负责版本形态校验与路径推导（开发版无归档名）。"""
    rf_archive, plan_archive = ctx.rf_archive, ctx.plan_archive
    for path in (rf_archive, plan_archive):
        if not path.exists():
            print(f"[ERR] 归档文件不存在：{path}（新小版本需先手工建归档文件）")
            return 2
    minor = version.rsplit(".", 1)[0]

    print("[..] 归档迁移（机械部分；条目内容与设计文件判定仍须人工复核）")

    # 顺序纪律：先做设计文件迁档（目录树 → git mv → 引用改写），再做台账落盘。
    # 任一步失败即中止，此时台账仍原样——不会留下「表已搬走但归档没写成」的半迁移。
    rf_text = ctx.rf_file.read_text(encoding="utf-8")
    plan_text = ctx.plan_file.read_text(encoding="utf-8")
    new_rf, new_arch, moved = apply_rf_archive(rf_text, rf_archive.read_text(encoding="utf-8"), version, date)
    new_plan, new_plan_arch, n_plan = apply_plan_archive(
        plan_text, plan_archive.read_text(encoding="utf-8"), version, date
    )
    for label, text in (("review-findings", new_arch), ("plan", new_plan_arch)):
        for finding in archive_header_findings(text):
            print(f"  [!] {label} 归档头部：{finding}（人工补齐后再跑 gate）")

    moved_docs: list[str] = []
    if not skip_design_docs:
        docs = {path.name: path.read_text(encoding="utf-8") for path in sorted(ctx.plan_docs_dir.glob("*.md"))}
        candidates = design_doc_candidates(docs, open_ids(new_plan, new_rf))
        pending_review = unreferenced_docs(docs)
        if not candidates:
            print("  [OK] docs/plan：无引用编号已全部归档的设计文件（无可自动迁档项）")
        if pending_review:
            print("  [..] docs/plan 未引用任何任务编号（不自动迁档，人工确认是否完成）：" + "、".join(pending_review))
        for name, reason in candidates:
            stem = name.removesuffix(".md")
            rel_new = f"docs/archive/v{minor}.x/{stem}/{name}"
            dest = ctx.repo_root / rel_new
            print(f"  [..] {name} — {reason}")
            if dry:
                print(f"       将迁至 {rel_new} 并改写引用")
                continue
            # ① 目录树先搬（失败时尚未改动任何文件，直接中止）
            folders_before = ctx.folders_file.read_text(encoding="utf-8")
            try:
                folders_moved = move_tree_entry(folders_before, stem, minor)
            except ReleaseError as exc:
                print(f"[ERR] 目录树搬迁失败：{exc}")
                print("[ERR] 台账尚未改写（先算后写），按上方提示补好目录树后重跑 archive")
                return 2
            ctx.folders_file.write_text(folders_moved, encoding="utf-8")
            # ② 移动文件本体（失败则回滚目录树，避免树指向不存在的位置）
            dest.parent.mkdir(parents=True, exist_ok=True)
            rc, out, err = _exec(["git", "mv", str(ctx.plan_docs_dir / name), str(dest)], ctx.repo_root, runner)
            if rc != 0:  # 文件没动成 → 目录树回滚（不指向不存在的位置）
                ctx.folders_file.write_text(folders_before, encoding="utf-8")
                print(f"[ERR] git mv 失败：{name} {(err or out).strip()}（目录树已回滚）")
                return rc or 1
            # ③ 改写引用：管理文档用 ../archive/…，根文档用 docs/archive/…，同级设计文档同样改
            for target in (
                ctx.changelog_file,
                ctx.plan_file,
                ctx.rf_file,
                ctx.folders_file,
                ctx.repo_root / "CLAUDE.md",
            ):
                _rewrite_refs_in(
                    target, (f"../plan/{name}", f"docs/plan/{name}"), f"../archive/v{minor}.x/{stem}/{name}"
                )
            _rewrite_refs_in(ctx.readme_file, (f"docs/plan/{name}",), rel_new)
            for sibling in sorted(ctx.plan_docs_dir.glob("*.md")):
                if sibling.name != name:
                    _rewrite_refs_in(sibling, (name,), f"../archive/v{minor}.x/{stem}/{name}")
            moved_docs.append(rel_new)
            print(f"  [OK] 迁入 {rel_new}（引用已改写，目录树已搬）")

    # 台账落盘（含头部/索引派生），失败面已收敛到「台账未动」
    if moved:
        if not dry:
            ctx.rf_file.write_text(new_rf, encoding="utf-8")
            rf_archive.write_text(new_arch, encoding="utf-8")
        print(f"  [OK] review-findings：{moved} 条原表搬入 {rf_archive.name}（主台账留迁档占位）")
    else:
        print("  [OK] review-findings：该版本已迁档（占位已在），跳过")
    if n_plan:
        if not dry:
            ctx.plan_file.write_text(new_plan, encoding="utf-8")
            plan_archive.write_text(new_plan_arch, encoding="utf-8")
        print(f"  [OK] plan：{n_plan} 个已完成任务节搬入 {plan_archive.name}")
    else:
        print("  [OK] plan：无已完成任务节，跳过")

    if dry:
        print("\n[OK] dry-run 结束（未写入任何文件）")
        return 0

    # 归档改写了台账/目录树/索引 → 统计快照立即同步，再跑两台便宜守护兜住文档面
    rc, out, err = _exec([sys.executable, "scripts/check-doc-drift.py", "--sync"], ctx.repo_root, runner)
    print((out or err).rstrip())
    if rc != 0:
        print("[ERR] 文档统计快照同步失败，按上方输出处理后重跑 archive")
        return rc
    for script in ("scripts/check-doc-traces.py", "scripts/check-doc-links.py"):
        rc, out, err = _exec([sys.executable, script, "--ci"], ctx.repo_root, runner)
        if out.strip():
            print(out.rstrip())
        if rc != 0:
            print(f"[ERR] {Path(script).name} 未通过，按上方输出修正后重跑 archive")
            return rc

    print("\n[OK] 归档迁移完成（机械部分）。人工复核项：")
    print("  1. 迁入归档的条目是否确实属于本版已解决项（原表搬运，未做摘要改写）")
    print("  2. 设计文件迁档判定是否正确（引用编号均已归档 ≠ 内容必然完成）")
    if moved_docs:
        print("  3. 本次迁档设计文件：" + "、".join(moved_docs))
    print("  4. 复核后按序继续：refresh → evolution --release → gate → publish → devbump")
    return 0
