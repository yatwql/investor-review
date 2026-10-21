"""台账与设计文档归档迁移（纯文本变换，落盘由调用方负责）。

发布前的「归档迁移」原先纯人工，机械部分集中在这里：

  - `apply_rf_archive`：review-findings 该版本「开发期已修复」表的**原表搬运**
    （表格块逐行无损，含原分隔行；表外散文留在主台账）+ 主台账留迁档占位 +
    归档头部「涵盖版本」区间尾延展、`归档时间` 行**追加**本批（不改写既有叙述）
  - `apply_plan_archive`：plan.md 已完成任务节（标题带完成标记）整节搬入计划归档，
    沿用归档既有的**扁平 `## plan-N … ✅`** 结构（不另造版本包装节）
  - `design_doc_candidates`：`docs/plan/` 设计文件是否「已完成」的判定（被引用的
    plan-/rf- 编号**全都已归档**才列为候选），返回候选与理由供人工复核；
    `unreferenced_docs` 单独列出无编号引用的文件（仅提示，不自动迁档）
  - `rewrite_doc_refs`：设计文件迁档后的路径引用改写（`[文字](旧路径)` 与裸路径）
  - `move_tree_entry`：folders.md 目录树行的「plan 子树 → 版本归档子树」搬迁

**格式随既有归档走**（不另立规范）：批次标题 `## 开发期已修复（X.Y.Z-dev）`、
说明行 `> 完整复盘见 changelog.md X.Y.Z-dev 段；…`、归档头部两行与主文件「归档档案」
索引区间；本模块只做「把已有格式的下一个批次写出来」。

判定边界（**脚本不替人决定**）：条目内容是否真的该归档、完成标记是否打对、设计文件
是否真的完成、摘要要不要精简，仍由人复核；脚本只保证机械动作一致、可重复（幂等）
且不动语义。该版本尚无自审条目（缺「开发期已修复」节）时一律视作「无待迁档」放行。
"""

from __future__ import annotations

import re

from _release._common import ReleaseError

#: 主台账里的目标节标题：`### 开发期已修复（X.Y.Z-dev）`
#: 节标题（`[ \t]*$` 而非 `\s*$`：避免把标题后的空行吞进匹配、占位前多出空行）
_RF_SECTION_RE = re.compile(r"^### 开发期已修复（(?P<dev>\d+\.\d+\.\d+)-dev）[ \t]*$", re.M)
#: 已解决表数据行（只认 `| **rf-N**` 开头，用于计数与「有没有表」的判定）
_RF_ROW_RE = re.compile(r"^\|\s*\*\*rf-\d+\*\*\s*\|", re.M)
#: 表格行（表块边界判定：任意 `|` 起头行，保留原分隔行/续行）
_TABLE_LINE_RE = re.compile(r"^\s*\|")
#: 归档内各批次节标题（既有格式，随版本批次追加）：`## 开发期已修复（X.Y.Z-dev）`
_RF_ARCHIVE_HEAD_FMT = "## 开发期已修复（{version}-dev）"
_HEADER_SPAN_RE = re.compile(r"^> 涵盖版本：.*$", re.M)
_HEADER_TIME_RE = re.compile(r"^> 归档时间：.*$", re.M)
_TRAILING_VERSION_RE = re.compile(r"(v\d+\.\d+\.\d+)\s*）\s*$")
#: 主文件「归档档案」索引行里的日期区间
_INDEX_RANGE_RE = re.compile(
    r"^(?P<head>- \[`archived_review-findings\.\d+\.\d+\.x\.md`\][^（]*（)"
    r"(?P<start>\d{4}-\d{2}-\d{2}) ~ (?P<end>\d{4}-\d{2}-\d{2})(?P<tail>）.*)$",
    re.M,
)

RF_PLACEHOLDER = "（本版开发期已修复项已随 v{version} 发布迁入上方归档档案）"
RF_SECTION_NOTE = "> 完整复盘见 `changelog.md` {version}-dev 段；此处为台账原表搬运（无损），本批发布日 {date}。"


# ─────────────────────────── review-findings ───────────────────────────


def _rf_section_or_none(text: str, dev_version: str) -> tuple[int, int] | None:
    """目标节正文的 (起点, 终点)：节标题行之后到下一个 ### / ## 之前。

    该版本尚无自审条目时**可缺节**（返回 None）——不强迫先建空节才能发布。
    """
    m = None
    for cand in _RF_SECTION_RE.finditer(text):
        if cand.group("dev") == dev_version:
            m = cand
            break
    if m is None:
        return None
    tail = re.search(r"^(?:###|## )", text[m.end() :], re.M)
    end = m.end() + tail.start() if tail else len(text)
    return m.end(), end


def split_section_table(section_body: str) -> tuple[str, str, str] | None:
    """节正文切成 (表前散文, 表格块, 表后散文)；无表格行返回 None。

    表块 = 从第一条 `|` 行起、连续 `|` 行为止——**原样**返回（含分隔行与所有行），
    不按 `rf-N` 前缀筛选，避免漏搬合并行/续行；表外散文由调用方保留在原位。
    """
    lines = section_body.splitlines()
    start = next((i for i, line in enumerate(lines) if _TABLE_LINE_RE.match(line)), None)
    if start is None:
        return None
    end = start
    while end < len(lines) and _TABLE_LINE_RE.match(lines[end]):
        end += 1
    return (
        "\n".join(lines[:start]),
        "\n".join(lines[start:end]),
        "\n".join(lines[end:]),
    )


def extract_rf_table(section_body: str) -> str | None:
    """取已解决表格块原文（含原表头与分隔行）；已迁档（只剩占位）或无 rf 行时 None。"""
    parts = split_section_table(section_body)
    if parts is None or not _RF_ROW_RE.search(parts[1]):
        return None
    return parts[1]


def count_rf_rows(section_body: str) -> int:
    """未迁档的已解决条目数（门禁断言用；0 表示已迁档或本节为空）。"""
    table = extract_rf_table(section_body)
    return 0 if table is None else sum(1 for line in table.splitlines() if _RF_ROW_RE.match(line))


def apply_rf_archive(main_text: str, archive_text: str, version: str, date: str) -> tuple[str, str, int]:
    """把该版本已解决表格块搬进归档，主台账留占位。幂等：已迁档时原样返回（计数 0）。"""
    bounds = _rf_section_or_none(main_text, version)
    if bounds is None:  # 本版无自审条目：无待迁档内容，原样返回（幂等）
        return main_text, archive_text, 0
    start, end = bounds
    parts = split_section_table(main_text[start:end])
    if parts is None or not _RF_ROW_RE.search(parts[1]):
        return main_text, archive_text, 0
    before, table, after = parts
    moved = sum(1 for line in table.splitlines() if _RF_ROW_RE.match(line))

    placeholder = RF_PLACEHOLDER.format(version=version)
    kept_prose = [block.strip("\n") for block in (before, after) if block.strip()]
    body = "\n\n".join([*kept_prose, placeholder]) + "\n\n"
    new_main = main_text[:start] + "\n\n" + body + main_text[end:].lstrip("\n")

    section = (
        _RF_ARCHIVE_HEAD_FMT.format(version=version)
        + "\n\n"
        + RF_SECTION_NOTE.format(version=version, date=date)
        + "\n\n"
        + table
        + "\n"
    )
    new_archive = archive_text.rstrip("\n") + "\n\n" + section
    new_archive = _bump_archive_header(new_archive, version, date)
    new_main = _bump_index_range(new_main, date)
    return new_main, new_archive, moved


def _bump_archive_header(text: str, version: str, date: str) -> str:
    """归档头部两行：`涵盖版本` 区间尾延展、`归档时间` 末尾**追加**本批（既有叙述不删）。"""
    out = _HEADER_SPAN_RE.sub(
        lambda m: (
            _TRAILING_VERSION_RE.sub(f"v{version}）", m.group(0), count=1)
            if _TRAILING_VERSION_RE.search(m.group(0))
            else m.group(0).rstrip() + f"（含 v{version}）"
        ),
        text,
        count=1,
    )
    stamp = f"{date} v{version}"
    return _HEADER_TIME_RE.sub(
        lambda m: m.group(0) if stamp in m.group(0) else m.group(0).rstrip() + f"；{stamp} 本批原表搬运",
        out,
        count=1,
    )


def rf_archive_status(text: str, version: str) -> tuple[str, int]:
    """该版本已解决节的迁档状态：`absent`（无本节）/ `pending`（还有 N 条未搬）/ `archived`（已搬空）。"""
    bounds = _rf_section_or_none(text, version)
    if bounds is None:
        return "absent", 0
    rows = count_rf_rows(text[bounds[0] : bounds[1]])
    return ("pending", rows) if rows else ("archived", 0)


def pending_rf_rows(text: str, version: str) -> int:
    """门禁断言用：该版本已解决节里**尚未迁档**的条目数（无本节或已搬空=0）。"""
    return rf_archive_status(text, version)[1]


def has_archive_section(archive_text: str, version: str) -> bool:
    """归档文件内是否已有该版本批次节（`## 开发期已修复（X.Y.Z-dev）`）。"""
    return _RF_ARCHIVE_HEAD_FMT.format(version=version) in archive_text


def archive_header_findings(archive_text: str) -> list[str]:
    """归档头部两行是否齐备（缺行时头部无法派生——报给人补，不静默放行）。"""
    findings = []
    if not _HEADER_SPAN_RE.search(archive_text):
        findings.append("归档文件缺 `> 涵盖版本：` 行，区间尾无法派生")
    if not _HEADER_TIME_RE.search(archive_text):
        findings.append("归档文件缺 `> 归档时间：` 行，本批日期无法记录")
    return findings


def _bump_index_range(text: str, date: str) -> str:
    """主文件「归档档案」索引行的区间右端延展到本次发布日（无匹配行时原样返回）。"""

    def _repl(m: re.Match[str]) -> str:
        start = m.group("start")
        end = max(start, date)  # 同日或多批同日时不回退
        return f"{m.group('head')}{start} ~ {end}{m.group('tail')}"

    return _INDEX_RANGE_RE.sub(_repl, text, count=1)


# ─────────────────────────── plan 台账 ───────────────────────────

#: 已完成任务节标题：`## plan-N 标题 ✅`（既有归档格式）/ `## ✅ plan-N 标题`（表格口径兼容）
_PLAN_DONE_HEAD_RE = re.compile(
    r"^##\s*(?:`?plan-\d+[^\n]*(?:✅|已完成)|(?:✅|已完成)[^\n]*`?plan-\d+)",
    re.M,
)
_PLAN_ANY_HEAD_RE = re.compile(r"^## (?P<title>.+?)\s*$", re.M)


def plan_completed_sections(text: str) -> list[tuple[int, int, str]]:
    """plan.md 内已完成任务节（标题含完成标记）的 (起点, 终点, 标题)。"""
    hits = []
    for m in _PLAN_DONE_HEAD_RE.finditer(text):
        tail = _PLAN_ANY_HEAD_RE.search(text[m.end() :])
        end = m.end() + tail.start() if tail else len(text)
        hits.append((m.start(), end, m.group(0)))
    return hits


def apply_plan_archive(main_text: str, archive_text: str, version: str, date: str) -> tuple[str, str, int]:
    """把 plan.md 已完成任务节整节搬入计划归档（沿用扁平 `## plan-N … ✅` 结构）。"""
    sections = plan_completed_sections(main_text)
    if not sections:
        return main_text, archive_text, 0
    chunks = [main_text[s:e].strip("\n") for s, e, _t in sections]
    for s, e, _t in reversed(sections):  # 从后往前删，避免位移
        main_text = main_text[:s] + main_text[e:]
    main_text = re.sub(r"\n{3,}", "\n\n", main_text)

    new_archive = archive_text.rstrip("\n") + "\n\n" + "\n\n".join(chunks) + "\n"
    # 头部沿用同一套追加口径（涵盖版本补「含 vX.Y.Z」/ 归档时间补本批）
    new_archive = _bump_archive_header(new_archive, version, date)
    return main_text, new_archive, len(chunks)


# ─────────────────────── docs/plan 设计文件判定 ───────────────────────

_ID_RE = re.compile(r"\b(?:plan|rf)-\d+\b")


def referenced_ids(text: str) -> set[str]:
    """文内引用的任务编号集合（plan-N / rf-N）。"""
    return set(_ID_RE.findall(text))


def open_ids(plan_text: str, rf_text: str) -> set[str]:
    """仍开放（未归档）的任务编号：plan.md 现行条目 + 主台账现行条目。"""
    return referenced_ids(plan_text) | referenced_ids(rf_text)


def design_doc_candidates(files: dict[str, str], still_open: set[str]) -> list[tuple[str, str]]:
    """可自动归档的 `docs/plan/` 设计文件：[(文件名, 理由)]。

    判定口径（保守、只认强信号）：文内引用的任务编号**全都已归档**才列为候选——
    仍在办者留原处；**一个编号都没引用**的文件不自动判定（设计文档常先于任务编号
    存在），只在 `unreferenced_docs` 里列出供人复核，绝不被本函数纳入搬运。
    """
    out: list[tuple[str, str]] = []
    for name, text in sorted(files.items()):
        refs = referenced_ids(text)
        if refs and not (refs & still_open):
            out.append((name, f"引用编号均已归档：{', '.join(sorted(refs))}"))
    return out


def unreferenced_docs(files: dict[str, str]) -> list[str]:
    """未引用任何任务编号的设计文件（仅提示，不自动迁档——判定权留人）。"""
    return [name for name, text in sorted(files.items()) if not referenced_ids(text)]


def rewrite_doc_refs(text: str, old_path: str, new_path: str) -> tuple[str, int]:
    """把引用从原路径指向迁档后的新路径：`](路径)` 链接与裸路径两种形态。"""
    count = text.count(old_path)
    if not count:
        return text, 0
    return text.replace(old_path, new_path), count


# ─────────────────────────── folders 目录树 ───────────────────────────


def _block_bounds(lines: list[str], head_index: int) -> tuple[int, int]:
    """块范围：块标题行之后，到第一条不比子项更深（前缀不再以其开头）的行之前。"""
    head = lines[head_index]
    m = re.match(r"^([│\s]*)(?:├──|└──)", head)
    depth = len(m.group(1)) if m else 0
    child_prefix = None
    end = len(lines)
    for i in range(head_index + 1, len(lines)):
        line = lines[i]
        if not line.startswith("│"):
            end = i
            break
        pm = re.match(r"^([│\s]*)(?:├──|└──)", line)
        if pm is None or len(pm.group(1)) <= depth:
            end = i
            break
        if child_prefix is None:
            child_prefix = pm.group(1)
    return head_index + 1, end


def _split_entries(lines: list[str], start: int, end: int, child_prefix: str) -> list[list[str]]:
    """把块内行按直接子项分组（每组 = 直接行 + 其下更深行）。"""
    groups: list[list[str]] = []
    for line in lines[start:end]:
        if line.startswith(child_prefix) and re.match(r"^[│\s]*(?:├──|└──)", line):
            groups.append([line])
        elif groups:
            groups[-1].append(line)
    return groups


def _entry_name(line: str) -> str:
    m = re.search(r"(?:├──|└──)\s+(\S+)", line)
    return m.group(1) if m else ""


def _child_prefix_of(lines: list[str], start: int, end: int) -> str | None:
    for line in lines[start:end]:
        pm = re.match(r"^([│\s]*)(?:├──|└──)", line)
        if pm:
            return pm.group(1)
    return None


def _render_group(group: list[str], child_prefix: str, last: bool) -> list[str]:
    """按位置重画连接符：末项 └──（其子项前缀补空格），其余 ├──。"""
    connector = "└──" if last else "├──"
    out = [re.sub(r"(?:├──|└──)", connector, group[0], count=1)]
    child_marker = "    " if last else "│   "
    for line in group[1:]:
        out.append(child_prefix + child_marker + "└──" + line.split("└──", 1)[1] if "└──" in line else line)
    return out


def move_tree_entry(text: str, stem: str, minor: str) -> str:
    """把 `docs/plan/<stem>.md` 的树行组搬到 `docs/archive/v<minor>.x/` 块下。"""
    lines = text.splitlines()
    plan_head = next((i for i, ln in enumerate(lines) if re.search(r"(?:├──|└──)\s+plan/\s*#", ln)), None)
    if plan_head is None:
        raise ReleaseError("folders.md 未找到 plan/ 子树块")
    p_start, p_end = _block_bounds(lines, plan_head)
    p_prefix = _child_prefix_of(lines, p_start, p_end) or "│       "
    groups = _split_entries(lines, p_start, p_end, p_prefix)
    kept = [g for g in groups if _entry_name(g[0]) != f"{stem}.md"]
    if len(kept) == len(groups):
        raise ReleaseError(f"folders.md 的 plan/ 子树没有 {stem}.md 条目")

    ver_head = next(
        (i for i, ln in enumerate(lines) if re.search(rf"(?:├──|└──)\s+v{re.escape(minor)}\.x/\s*#", ln)),
        None,
    )
    if ver_head is None:
        raise ReleaseError(f"folders.md 未找到 v{minor}.x 归档子树块——新小版本首份归档需先在目录树补该目录块")
    a_start, a_end = _block_bounds(lines, ver_head)
    a_prefix = _child_prefix_of(lines, a_start, a_end) or "│   │   │   "
    a_groups = _split_entries(lines, a_start, a_end, a_prefix)
    new_group = [
        f"{a_prefix}├── {stem}/ # 设计文档归档（任务完成后由发布归档迁入）",
        f"{a_prefix}    └── {stem}.md # 原 docs/plan/{stem}.md",
    ]
    names = [_entry_name(g[0]).rstrip("/") for g in a_groups]
    pos = next((i for i, n in enumerate(names) if n.lower() > stem.lower()), len(a_groups))
    a_groups.insert(pos, new_group)

    # 归档块在计划块之前（同一文件内），故按索引**从后往前**替换
    plan_out = [ln for g in kept for ln in _render_group(g, p_prefix, g is kept[-1])]
    arch_out = [ln for g in a_groups for ln in _render_group(g, a_prefix, g is a_groups[-1])]
    new_lines = list(lines)
    new_lines[p_start:p_end] = plan_out
    new_lines[ver_head + 1 : a_end] = arch_out
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
