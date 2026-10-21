"""新小版本归档骨架初始化（`release.py archive-init`）。

新小版本（vX.Y.0）首发前，归档侧有五类空位需先就位——`check` 会逐条报缺，
逐条手工补齐则每补一处都要重跑一次 `check`。本模块把它们一次建齐：

1. `docs/archive/vX.Y.x/` 下三份归档文件（changelog / plan / review-findings），
   头部按既有格式写全（`归档时间` / `原始文件` / `涵盖版本` / `归档内容`），
   使 `archive_header_findings` 与 `write_archive_release` 的头部派生都有落点；
2. `folders.md` 目录树的 `vX.Y.x/` 归档子树块（含三份文件条目）；
3. 主文件三处「归档档案」索引行（plan / review-findings / changelog）。

全部动作幂等：已存在的文件不覆盖、已有条目/块不重复插入。
"""

from __future__ import annotations

import re
from pathlib import Path

from _release._archive_flow import ArchiveContext
from _release._common import ReleaseError

_TREE_VER_RE = re.compile(r"^(?P<prefix>.*?)[├└]── v(?P<minor>\d+\.\d+)\.x/\s")
_INDEX_LINE_FMT = "- [`{name}`](../archive/v{minor}.x/{name}) — v{minor}.x（{date} ~ {date}）"


def _minor(version: str) -> str:
    m = re.match(r"^(\d+\.\d+)\.\d+$", version)
    if not m:
        raise ReleaseError(f"{version} 不是 X.Y.Z 发布版形态")
    return m.group(1)


def _archive_file_body(kind: str, version: str, date: str) -> str:
    minor = re.sub(r"\.\d+$", "", version)  # X.Y
    if kind == "changelog":
        return (
            f"# 变更日志归档 — v{minor}.x\n\n"
            f"> 归档时间：{date}（v{version} 发布并入）\n"
            "> 原始文件：`docs/managements/changelog.md`\n"
            f"> 涵盖版本：v{version}（{date}）起\n"
            "> 归档内容：由 `release.py prepare` 自动迁入各发布段\n\n---\n"
        )
    if kind == "review-findings":
        return (
            f"# 自审记录归档 — v{minor}.x\n\n"
            f"> 归档时间：{date}（v{version} 发布，本系列首批开发期已修复批次并入）\n"
            "> 原始文件：`docs/managements/review-findings.md`\n"
            f"> 涵盖版本：v{minor}.x 开发期已修复项（v{version} → ）\n"
            "> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账\n\n---\n"
        )
    return (
        f"# 计划归档 — v{minor}.x\n\n"
        f"> 归档时间：{date}（v{version} 发布，本系列首份）\n"
        "> 原始文件：`docs/managements/plan.md`\n"
        f"> 涵盖版本：v{minor}.x 开发期完成项\n"
        "> 归档内容：已完成任务节经 `release.py prepare` 自动搬入\n\n---\n"
    )


def insert_tree_block(folders_text: str, minor: str) -> tuple[str, bool]:
    """在目录树归档子树末尾补 `v{minor}.x/` 块；已存在则原样返回。

    树标记维护：新块用 `└──`（末尾目录）；其紧邻的前一个目录用 `├──`，
    且该目录的子女续行符为 `│   `（否则父级标记与子女缩进不自洽）。
    """
    if f"v{minor}.x/" in folders_text:
        return folders_text, False
    lines = folders_text.splitlines()
    versions = [(i, m) for i, line in enumerate(lines) if (m := _TREE_VER_RE.match(line))]
    if not versions:
        raise ReleaseError("folders.md 目录树未找到任何 `vX.Y.x/` 归档子树——请人工确认目录树格式")

    last_idx, last_match = versions[-1]
    prefix = last_match.group("prefix")
    last_minor = tuple(int(n) for n in last_match.group("minor").split("."))
    new_minor = tuple(int(n) for n in minor.split("."))
    if new_minor < last_minor:
        raise ReleaseError(
            f"新归档 v{minor}.x 早于目录树中最后一个版本 v{last_match.group('minor')}.x——"
            "请人工插入到正确位置（脚本只追加到末尾）"
        )

    def _is_sibling(line: str) -> bool:
        return bool(re.match(rf"^{re.escape(prefix)}[├└]── ", line))

    block_end = last_idx + 1
    while block_end < len(lines):
        nxt = lines[block_end]
        if not nxt.strip() or not nxt.startswith(prefix) or _is_sibling(nxt):
            break
        block_end += 1

    # 原最后一个目录要接纳新兄弟 → 标记改 ├── 并给子女补竖线续行
    if "└── " in lines[last_idx]:
        lines[last_idx] = lines[last_idx].replace(f"{prefix}└── ", f"{prefix}├── ", 1)
        for i in range(last_idx + 1, block_end):
            lines[i] = lines[i].replace(f"{prefix}    ", f"{prefix}│   ", 1)

    block = [
        f"{prefix}└── v{minor}.x/                         # v{minor}.x 版本归档（changelog/plan/review-findings + 设计文档）",
        f"{prefix}    ├── archived_changelog.{minor}.x.md # 变更日志归档 v{minor}.x（发布段）",
        f"{prefix}    ├── archived_plan.{minor}.x.md      # 实现计划归档 v{minor}.x（已完成任务节）",
        f"{prefix}    └── archived_review-findings.{minor}.x.md # 自审记录归档 v{minor}.x（开发期已修复批次）",
    ]
    lines[block_end:block_end] = block
    return "\n".join(lines) + "\n", True


def insert_index_line(text: str, name: str, minor: str, date: str, *, kind: str) -> tuple[str, bool]:
    """主文件「归档档案」索引列表补一行（区间口径，与既有行同形）；已有则跳过。

    插入位置 = 该 kind 第一条既有索引行之前（列表按版本倒序，新增行处于最前）。
    """
    if name in text:
        return text, False
    line = _INDEX_LINE_FMT.format(name=name, minor=minor, date=date)
    lines = text.splitlines()
    pat = re.compile(rf"^- \[`archived_{re.escape(kind)}\.\d+\.\d+\.x\.md`\]")
    anchor = next((i for i, ln in enumerate(lines) if pat.match(ln)), None)
    if anchor is None:
        raise ReleaseError(f"未找到 `archived_{kind}.*.x.md` 归档索引行——请人工确认索引格式")
    lines.insert(anchor, line)
    return "\n".join(lines) + "\n", True


def init_archive(ctx: ArchiveContext, version: str, date: str, *, dry: bool = False) -> list[str]:
    """建齐新小版本归档骨架；返回动作描述列表（幂等）。"""
    minor = _minor(version)
    actions: list[str] = []
    archive_dir = ctx.rf_archive.parent

    def _write(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    if not dry:
        archive_dir.mkdir(parents=True, exist_ok=True)
    for kind, path in (
        ("changelog", ctx.rf_archive.parent / f"archived_changelog.{minor}.x.md"),
        ("review-findings", ctx.rf_archive),
        ("plan", ctx.plan_archive),
    ):
        if path.exists():
            continue
        actions.append(f"新建归档文件 {path.relative_to(ctx.repo_root).as_posix()}")
        if not dry:
            _write(path, _archive_file_body(kind, version, date))

    folders_text = ctx.folders_file.read_text(encoding="utf-8")
    new_text, changed = insert_tree_block(folders_text, minor)
    if changed:
        actions.append(f"folders.md 目录树补 `v{minor}.x/` 归档子树块")
        if not dry:
            ctx.folders_file.write_text(new_text, encoding="utf-8")

    for kind, path in (
        ("review-findings", ctx.rf_file),
        ("plan", ctx.plan_file),
        ("changelog", ctx.changelog_file),
    ):
        name = f"archived_{kind}.{minor}.x.md"
        text = path.read_text(encoding="utf-8")
        new_text, changed = insert_index_line(text, name, minor, date, kind=kind)
        if changed:
            actions.append(f"{path.name} 归档索引补 `{name}`")
            if not dry:
                path.write_text(new_text, encoding="utf-8")
    return actions
