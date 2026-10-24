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

# 归档文件头部的两行自述（随每次并入自动重写，见 render_archive_header）
_HEADER_SPAN_RE = re.compile(r"^> 涵盖版本：.*$", re.M)
_HEADER_TIME_RE = re.compile(r"^> 归档时间：.*$", re.M)
# 归档内各发布段标题：`## [X.Y.Z] - YYYY-MM-DD`
_RELEASE_SECTION_RE = re.compile(r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$", re.M)


#: 报错时附带的「期望格式」样例——发布跑挂在格式不符时，人不必翻代码猜写法
_FMT_POINTER = (
    "> **最近发布 [X.Y.Z]**（YYYY-MM-DD）——已发布版本段随发布移入 "
    "[`archived_changelog.X.Y.x.md`](../archive/vX.Y.x/archived_changelog.X.Y.x.md)；"
    "本文件只保留当前开发版本段与归档索引。"
)
_FMT_INDEX = "- [`archived_changelog.X.Y.x.md`](../archive/vX.Y.x/archived_changelog.X.Y.x.md) — vX.Y.Z（YYYY-MM-DD）"
_FMT_SECTION = "## [X.Y.Z-dev] - 开发中（未发布）"
_HINT_INIT = "新小版本首个版本：先跑 `release.py archive-init` 自动生成骨架（幂等，可 --dry）"


def _fmt_hint(*lines: str) -> str:
    """把「期望格式 + 下一步」拼成多行提示（缩进对齐，便于终端扫读）。"""
    body = "\n".join(f"      期望：{ln}" for ln in lines)
    return f"\n{body}\n      下一步：{_HINT_INIT}"


def _find_section(text: str) -> tuple[int, int, str]:
    """定位当前开发段（含正文），返回 (起点, 终点, 段内版本号)；终点=下一 ## 行。"""
    header = re.search(r"^## \[([^\]]+)\] - 开发中（未发布）\s*$", text, re.M)
    if not header:
        raise ReleaseError("changelog 未找到「开发中（未发布）」段" + _fmt_hint(_FMT_SECTION))
    next_header = re.search(r"^## ", text[header.end() :], re.M)
    if not next_header:
        raise ReleaseError("changelog 开发段之后没有归档章节（缺 `## 归档` 索引块）" + _fmt_hint("## 归档", _FMT_INDEX))
    return header.start(), header.end() + next_header.start(), header.group(1)


def release_section_has_entries(text: str, release_version: str) -> bool:
    """归档文件里 `## [X.Y.Z] - YYYY-MM-DD` 段是否含实际条目。

    gate 侧兜底：prepare 已拦住「占位句被原样归档」，但归档文件仍可能被人工/旁路
    写成只有标题的空段（实测已发生过一次，发布记录永久缺内容）。此处按段扫描，
    与 `_has_release_entries` 同一判据（`### ` 分类标题或 `- ` 条目行）。
    """
    target = str(release_version).lstrip("v")
    heads = list(_RELEASE_SECTION_RE.finditer(text))
    for pos, match in enumerate(heads):
        if match.group(1).lstrip("v") != target:
            continue
        end = heads[pos + 1].start() if pos + 1 < len(heads) else len(text)
        return _has_release_entries(text[match.end() : end])
    return False


def _has_release_entries(body_core: str) -> bool:
    """开发段是否含实际条目（分类标题 `###` 或 `- ` 条目行）。

    纯白/只余占位句/只有 `##` 级空段 → 视为空段（发布会被拦）。
    """
    for line in body_core.splitlines():
        stripped = line.strip()
        if not stripped or stripped == SECTION_NOTE:
            continue
        if stripped.startswith("### ") or stripped.startswith("- "):
            return True
    return False


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

    # 空段拦截：开发期 changelog 停在占位句时，迁出结果就是「只有标题的空发布段」——
    # 归档会永久缺失该版内容（实测已发生一次），而下游无任何断言。此处前置中止。
    if not _has_release_entries(body_core):
        raise ReleaseError(
            f"changelog 开发段 {release_version}-dev 没有实际条目"
            f"（当前内容只有占位句「{SECTION_NOTE}」）\n"
            "      发布前必须先把本版变更写进该段（如 `### Changed` + 条目），否则归档会丢内容\n"
            "      下一步：补写 changelog 开发段后重跑 `release.py prepare`"
        )

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
        raise ReleaseError("changelog 未找到「最近发布」指针行" + _fmt_hint(_FMT_POINTER))

    archive_name = archive_name_for(release_version)
    # 指针行的归档文件名也要一并改写：跨小版本发布时归档文件换名（0.13.x → 0.14.x），
    # 只改版本号/日期会让指针继续指向上一系列的归档（链接失准且到下一系列才被发现）。
    out, n_link = re.subn(
        r"(^> \*\*最近发布 \[[\d.]+\]\*\*（[\d-]+）——已发布版本段随发布移入\s*\[`)[^`]+(`\])",
        lambda m: m.group(1) + archive_name + m.group(2),
        out,
        count=1,
        flags=re.M,
    )
    if n_link != 1:
        raise ReleaseError("changelog 指针行的归档文件链接改写失败（格式与预期不符）" + _fmt_hint(_FMT_POINTER))
    idx_pat = re.compile(
        rf"^(- \[`{re.escape(archive_name)}`\]\([^)]*\)\s*—\s*[^（]*?)"
        # 版本 token 两种形态：既有的 `vX.Y.Z`（可带 `~ vX.Y.Z` 区间），以及
        # `archive-init` 为新小版本生成的占位 `vX.Y.x`（该 minor 还没有任何正式版本）
        r"(v[\d.]+|v\d+\.\d+\.x)( ~ v[\d.]+)?（(\d{4}-\d{2}-\d{2})( ~ \d{4}-\d{2}-\d{2})?）",
        re.M,
    )
    if archive_name not in out:
        raise ReleaseError(
            f"changelog 归档索引中没有 {archive_name} 行（新小版本需先建归档文件）" + _fmt_hint(_FMT_INDEX)
        )

    def _idx_repl(m: re.Match) -> str:
        head, start_v, tail_v, start_d, tail_d = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
            m.group(5),
        )
        # 区间化：首次出现的单版本行（无 `~ v…` 尾巴）在第二次发布后必须变成区间，
        # 否则索引永远停在首个版本（连续两次发布后仍是首版单版本形态）。
        # 真值口径：起止都取发布实参，与归档文件头（按归档自身段标题派生）保持一致。
        #
        # 占位形态（`vX.Y.x`，由 `archive-init` 为新小版本生成）视为「该 minor 尚无发布
        # 版本」：本次发布即其首版，归一为单版本 + 发布日；否则保持区间扩展语义。
        is_placeholder = start_v.endswith(".x")
        if is_placeholder:
            span_v = f"v{release_version}"
            span_d = date
        else:
            span_v = f"{start_v} ~ v{release_version}" if release_version.lstrip("v") not in start_v else start_v
            span_d = f"{start_d} ~ {date}" if start_d != date else start_d
        _ = (tail_v, tail_d)  # 既有区间形态由 span_* 重算，无需区分
        return f"{head}{span_v}（{span_d}）"

    out, n_idx = idx_pat.subn(_idx_repl, out, count=1)
    if n_idx != 1:
        raise ReleaseError("changelog 归档索引行改写失败（格式与预期不符）" + _fmt_hint(_FMT_INDEX))
    return out, body_core


def render_archive_header(text: str, release_version: str, date: str) -> str:
    """按归档内实际发布段重写头部「涵盖版本 / 归档时间」两行（纯文本变换）。

    两行的真值是**归档文件自身各发布段标题**（`## [X.Y.Z] - 日期`）——先追加新段再
    调用本函数，涵盖区间与并入记录就由段列表唯一派生，无需人工维护、不会与正文漂移：

    - `> 涵盖版本：v{首段} ~ v{末段}（{首段日期} ~ {末段日期}）`（单段时省略区间）
    - `> 归档时间：{发行日期}（v{版本} 发布并入；已并入 N 段：v{版本}（MM-DD）、…）`

    早期归档（如 v0.1.x）头部没有这两行，属既成历史文件：**原样跳过**，不补写、不报错
    ——那个小版本不会再发布，改造它的历史头部没有收益。

    Args:
        text: 已包含新发布段的归档全文。
        release_version: 目标版本字符串（三段式，由调用方传入）。
        date: 本次发行日期（`YYYY-MM-DD`）。

    Returns:
        头部两行已更新的全文；两行缺任一行时原样返回。
    """
    if not (_HEADER_SPAN_RE.search(text) and _HEADER_TIME_RE.search(text)):
        return text
    sections = _RELEASE_SECTION_RE.findall(text)
    if not sections:
        raise ReleaseError("归档文件内没有 `## [版本] - 日期` 段，无法推导头部涵盖版本")

    first_version, first_date = sections[0]
    last_version, last_date = sections[-1]
    span = (
        f"v{first_version}（{first_date}）"
        if first_version == last_version
        else f"v{first_version} ~ v{last_version}（{first_date} ~ {last_date}）"
    )
    merged = "、".join(f"v{version}（{day[5:]}）" for version, day in sections)
    time_note = f"{date}（v{release_version} 发布并入；已并入 {len(sections)} 段：{merged}）"

    text = _HEADER_SPAN_RE.sub(f"> 涵盖版本：{span}", text, count=1)
    return _HEADER_TIME_RE.sub(f"> 归档时间：{time_note}", text, count=1)


def write_archive_release(archive_file: Path, release_version: str, date: str, body_core: str) -> None:
    """把发布段正文追加到归档文件，并重写头部涵盖版本/归档时间两行。

    段格式：`## [X.Y.Z] - 日期` 头条 + 正文，段间空行、无分隔线。头部两行的更新
    由 :func:`render_archive_header` 依段落列表派生——头部两行由发布编排自动维护。
    """
    if not archive_file.exists():
        raise ReleaseError(f"归档文件不存在：{archive_file}")
    old = archive_file.read_text(encoding="utf-8")
    block = f"## [{release_version}] - {date}\n\n{body_core.strip()}\n\n"
    merged = old.rstrip("\n") + "\n\n" + block.strip("\n") + "\n"
    archive_file.write_text(render_archive_header(merged, release_version, date), encoding="utf-8")
