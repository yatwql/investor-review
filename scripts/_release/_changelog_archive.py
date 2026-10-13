"""changelog 发布段迁出与归档追加（纯文本变换，不落盘除归档写入外）。

路径由调用方显式传入；归档文件名经 `archive_name_for` 纯函数派生，
入口模块的路径常量重定向（测试夹具）始终生效。
"""

from __future__ import annotations

import re
from pathlib import Path

from _release._common import ReleaseError
from _release._versioning import archive_name_for, next_dev_version_of

SECTION_NOTE = "（本次发布内容见下方归档索引）"


def _find_section(text: str) -> tuple[int, int, str]:
    """定位当前开发段（含正文），返回 (起点, 终点, 段内版本号)；终点=下一 ## 行。"""
    header = re.search(r"^## \[([^\]]+)\] - 开发中（未发布）\s*$", text, re.M)
    if not header:
        raise ReleaseError("changelog 未找到「开发中（未发布）」段")
    next_header = re.search(r"^## ", text[header.end() :], re.M)
    if not next_header:
        raise ReleaseError("changelog 开发段之后没有归档章节")
    return header.start(), header.end() + next_header.start(), header.group(1)


def apply_changelog_release(text: str, release_version: str, date: str) -> tuple[str, str]:
    """发布段迁出：改指针、改归档索引、清空开发段并生成下一开发段。

    返回 (新主文件文本, 迁出的发布段正文)。纯文本变换，不落盘。
    """
    section_start, section_end, current_dev = _find_section(text)
    if current_dev != f"{release_version}-dev":
        raise ReleaseError(f"changelog 开发段 {current_dev} 与目标发布版 {release_version} 不一致")

    body = text[section_start:section_end]
    # 迁出正文 = 段头之后到段尾注之前（尾注只属于主文件的占位说明）
    body_core = body.split("\n", 1)[1] if "\n" in body else ""
    body_core = re.sub(rf"^\s*\n*{re.escape(SECTION_NOTE)}\s*$", "", body_core, flags=re.M)
    body_core = body_core.strip("\n")

    next_dev = next_dev_version_of(release_version)
    new_section = f"## [{next_dev}] - 开发中（未发布）\n\n\n{SECTION_NOTE}\n\n"

    out = text[:section_start] + new_section + text[section_end:]

    out, n_ptr = re.subn(
        r"^(> \*\*最近发布 \[)[\d.]+(\]\*\*（)[\d-]+(）)",
        lambda m: m.group(1) + release_version + m.group(2) + date + m.group(3),
        out,
        count=1,
        flags=re.M,
    )
    if n_ptr != 1:
        raise ReleaseError("changelog 未找到「最近发布」指针行")

    archive_name = archive_name_for(release_version)
    idx_pat = re.compile(
        rf"^(- \[`{re.escape(archive_name)}`\]\([^)]*\)\s*—\s*[^（]*?)"
        r"(v[\d.]+)( ~ v[\d.]+)?（(\d{4}-\d{2}-\d{2})( ~ \d{4}-\d{2}-\d{2})?）",
        re.M,
    )
    if archive_name not in out:
        raise ReleaseError(f"changelog 归档索引中没有 {archive_name} 行（新小版本需先手工建归档文件）")

    def _idx_repl(m: re.Match) -> str:
        head, start_v, tail_v, start_d, tail_d = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
            m.group(5),
        )
        end_v = f" ~ v{release_version}" if tail_v else ""
        end_d = f" ~ {date}" if tail_d else ""
        return f"{head}{start_v}{end_v}（{start_d}{end_d}）"

    out, n_idx = idx_pat.subn(_idx_repl, out, count=1)
    if n_idx != 1:
        raise ReleaseError("changelog 归档索引行改写失败（格式与预期不符）")
    return out, body_core


def write_archive_release(archive_file: Path, release_version: str, date: str, body_core: str) -> None:
    """把发布段正文追加到归档文件（`## [X.Y.Z] - 日期` 头，段间空行、无分隔线）。"""
    if not archive_file.exists():
        raise ReleaseError(f"归档文件不存在：{archive_file}")
    old = archive_file.read_text(encoding="utf-8")
    block = f"## [{release_version}] - {date}\n\n{body_core.strip()}\n\n"
    archive_file.write_text(old.rstrip("\n") + "\n\n" + block.strip("\n") + "\n", encoding="utf-8")
