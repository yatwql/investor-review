"""台账与设计文档归档迁移（纯文本变换，落盘由调用方负责）。

发布前的「归档迁移」原先纯人工，机械部分集中在这里：

  - `apply_rf_archive`：review-findings 该版本「开发期已修复」表的**原表搬运**
    （逐行无损，不做摘要改写）+ 主台账留迁档占位 + 归档头部两行派生 + 索引日期延展
  - `apply_plan_archive`：plan.md 已完成任务节（标题带完成标记）整节搬入计划归档
  - `design_doc_candidates`：`docs/plan/` 设计文件是否「已完成」的判定（只认强信号：
    文内引用的 plan-/rf- 编号**全都已归档**才列为候选），返回候选与理由供人工复核；
    `unreferenced_docs` 单独列出无编号引用的文件（仅提示，不自动迁档）
  - `rewrite_doc_refs`：设计文件迁档后的路径引用改写（`[文字](旧路径)` 与裸路径）
  - `move_tree_entry`：folders.md 目录树行的「plan 子树 → 版本归档子树」搬迁

判定边界（**脚本不替人决定**）：条目内容是否真的该归档、完成标记是否打对、设计文件
是否真的完成、摘要要不要精简，仍由人复核；脚本只保证机械动作一致、可重复（幂等）
且不动语义。该版本尚无自审条目（缺「开发期已修复」节）时一律视作「无待迁档」放行。
"""

from __future__ import annotations

import re

from _release._common import ReleaseError

#: 主台账里的目标节标题：`### 开发期已修复（X.Y.Z-dev）`
_RF_SECTION_RE = re.compile(r"^### 开发期已修复（(?P<dev>\d+\.\d+\.\d+)-dev）\s*$", re.M)
#: 已解决表表头与数据行（只认 `| **rf-N**` 开头的行，避免误吃相邻表格）
_RF_TABLE_HEAD_RE = re.compile(r"^\|\s*#\s*\|\s*问题\s*\|\s*处理\s*\|\s*$", re.M)
_RF_ROW_RE = re.compile(r"^\|\s*\*\*rf-\d+\*\*\s*\|")
#: 归档内各批次节标题：`## vX.Y.Z 开发期已修复（YYYY-MM-DD）`
_RF_ARCHIVE_HEAD_RE = re.compile(r"^## v(?P<version>\d+\.\d+\.\d+) 开发期已修复", re.M)
_HEADER_SPAN_RE = re.compile(r"^> 涵盖版本：.*$", re.M)
_HEADER_TIME_RE = re.compile(r"^> 归档时间：.*$", re.M)
_TRAILING_VERSION_RE = re.compile(r"(v\d+\.\d+\.\d+)\s*）\s*$")
#: 主文件「归档档案」索引行里的日期区间
_INDEX_RANGE_RE = re.compile(
    r"^(?P<head>- \[`archived_review-findings\.\d+\.\d+\.x\.md`\][^（]*（)(?P<start>\d{4}-\d{2}-\d{2}) ~ (?P<end>\d{4}-\d{2}-\d{2})(?P<tail>）.*)$",
    re.M,
)

RF_PLACEHOLDER = "（本版开发期已修复项已随 v{version} 发布迁入上方归档档案）"
RF_SECTION_NOTE = "> 完整复盘见 `changelog.md` {version}-dev 段；此处为台账原表搬运（无损）。"


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


def extract_rf_table(section_body: str) -> str | None:
    """取已解决表原文（表头 + 分隔行 + 数据行）；已迁档（只剩占位）返回 None。"""
    head = _RF_TABLE_HEAD_RE.search(section_body)
    if head is None:
        return None
    rows: list[str] = []
    for line in section_body[head.start() :].splitlines():
        if _RF_ROW_RE.match(line):
            rows.append(line)
        elif rows:
            break
    if not rows:
        return None
    return "\n".join([head.group(0), "|---|------|------|", *rows])


def count_rf_rows(section_body: str) -> int:
    """未迁档的已解决条目数（门禁断言用；0 表示已迁档或本节为空）。"""
    table = extract_rf_table(section_body)
    return 0 if table is None else sum(1 for line in table.splitlines() if _RF_ROW_RE.match(line))


def apply_rf_archive(main_text: str, archive_text: str, version: str, date: str) -> tuple[str, str, int]:
    """把该版本已解决表搬进归档，主台账留占位。幂等：已迁档时原样返回（计数 0）。"""
    bounds = _rf_section_or_none(main_text, version)
    if bounds is None:  # 本版无自审条目：无待迁档内容，原样返回（幂等）
        return main_text, archive_text, 0
    start, end = bounds
    body = main_text[start:end]
    table = extract_rf_table(body)
    if table is None:
        return main_text, archive_text, 0
    moved = sum(1 for line in table.splitlines() if _RF_ROW_RE.match(line))

    placeholder = "\n\n" + RF_PLACEHOLDER.format(version=version) + "\n"
    new_main = main_text[:start] + placeholder + main_text[end:]

    section = (
        f"## v{version} 开发期已修复（{date}）\n\n" + RF_SECTION_NOTE.format(version=version) + "\n\n" + table + "\n"
    )
    new_archive = archive_text.rstrip("\n") + "\n\n" + section
    new_archive = _bump_archive_header(new_archive, version, date)
    new_main = _bump_index_range(new_main, date)
    return new_main, new_archive, moved


def _bump_archive_header(text: str, version: str, date: str) -> str:
    """归档头部两行派生：区间尾与归档时间按本次发布填写（两行均为可派生定式句）。"""
    out = text

    def _span(m: re.Match[str]) -> str:
        line = m.group(0)
        if _TRAILING_VERSION_RE.search(line):
            return _TRAILING_VERSION_RE.sub(f"v{version}）", line, count=1)
        return line.rstrip() + f"；追加至 v{version}"

    out = _HEADER_SPAN_RE.sub(_span, out, count=1)
    time_line = f"> 归档时间：{date}（v{version} 发布）；各批发布日期见下方各节标题。"
    if _HEADER_TIME_RE.search(out):
        out = _HEADER_TIME_RE.sub(lambda _m: time_line, out, count=1)
    return out


def _bump_index_range(text: str, date: str) -> str:
    """主文件「归档档案」索引行的区间右端延展到本次发布日。"""

    def _repl(m: re.Match[str]) -> str:
        start = m.group("start")
        end = max(start, date)  # 同日或多批同日时不回退
        return f"{m.group('head')}{start} ~ {end}{m.group('tail')}"

    return _INDEX_RANGE_RE.sub(_repl, text, count=1)


# ─────────────────────────── plan 台账 ───────────────────────────

_PLAN_DONE_HEAD_RE = re.compile(r"^## plan-\d+.*(?:✅|已完成)\s*$", re.M)
_PLAN_MARK_HEAD_RE = re.compile(r"^## (?P<title>.+?)\s*$", re.M)


def plan_completed_sections(text: str) -> list[tuple[int, int, str]]:
    """plan.md 内已完成任务节（标题含完成标记）的 (起点, 终点, 标题)。"""
    hits = []
    for m in _PLAN_DONE_HEAD_RE.finditer(text):
        tail = _PLAN_MARK_HEAD_RE.search(text[m.end() :])
        end = m.end() + tail.start() if tail else len(text)
        hits.append((m.start(), end, m.group(0)))
    return hits


def apply_plan_archive(main_text: str, archive_text: str, version: str, date: str) -> tuple[str, str, int]:
    """把 plan.md 已完成任务节整节搬入计划归档；无完成项时原样返回（计数 0）。"""
    sections = plan_completed_sections(main_text)
    if not sections:
        return main_text, archive_text, 0
    chunks = [main_text[s:e].strip("\n") for s, e, _t in sections]
    for s, e, _t in reversed(sections):  # 从后往前删，避免位移
        main_text = main_text[:s] + main_text[e:]
    main_text = re.sub(r"\n{3,}", "\n\n", main_text)
    block = f"## v{version} 已完成任务（{date}）\n\n" + "\n\n".join(chunks) + "\n"
    new_archive = archive_text.rstrip("\n") + "\n\n" + block
    new_archive = _HEADER_SPAN_RE.sub(
        lambda m: m.group(0) if f"v{version}" in m.group(0) else m.group(0).rstrip() + f"；并入 v{version} 批次",
        new_archive,
        count=1,
    )
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

_TREE_BLOCK_HEAD_RE = r"^│\s*(?:├──|└──)\s+{name}\s*#"


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
    # 1) 定位 plan 子树块并摘出该文件条目
    plan_head = next(
        (i for i, ln in enumerate(lines) if re.search(r"(?:├──|└──)\s+plan/\s*#", ln)),
        None,
    )
    if plan_head is None:
        raise ReleaseError("folders.md 未找到 plan/ 子树块")
    p_start, p_end = _block_bounds(lines, plan_head)
    p_prefix = next(
        (re.match(r"^([│\s]*)(?:├──|└──)", ln).group(1) for ln in lines[p_start:p_end] if "├──" in ln or "└──" in ln),
        "│       ",
    )
    groups = _split_entries(lines, p_start, p_end, p_prefix)
    kept = [g for g in groups if _entry_name(g[0]) != f"{stem}.md"]
    if len(kept) == len(groups):
        raise ReleaseError(f"folders.md 的 plan/ 子树没有 {stem}.md 条目")
    # 2) 版本归档子树块内插入（按名称序）
    ver_head = next(
        (i for i, ln in enumerate(lines) if re.search(rf"(?:├──|└──)\s+v{re.escape(minor)}\.x/\s*#", ln)),
        None,
    )
    if ver_head is None:
        raise ReleaseError(f"folders.md 未找到 v{minor}.x 归档子树块")
    a_start, a_end = _block_bounds(lines, ver_head)
    a_prefix = next(
        (re.match(r"^([│\s]*)(?:├──|└──)", ln).group(1) for ln in lines[a_start:a_end] if "├──" in ln or "└──" in ln),
        "│   │   │   ",
    )
    a_groups = _split_entries(lines, a_start, a_end, a_prefix)
    new_group = [
        f"{a_prefix}├── {stem}/ # 设计文档归档（任务完成后由发布归档迁入）",
        f"{a_prefix}    └── {stem}.md # 原 docs/plan/{stem}.md",
    ]
    names = [_entry_name(g[0]).rstrip("/") for g in a_groups]
    pos = next((i for i, n in enumerate(names) if n.lower() > stem.lower()), len(a_groups))
    a_groups.insert(pos, new_group)

    # 3) 重画两块子行（连接符按位置重排）；归档块在计划块之前，故按索引**从后往前**替换
    plan_out = [ln for g in kept for ln in _render_group(g, p_prefix, g is kept[-1])]
    arch_out = [ln for g in a_groups for ln in _render_group(g, a_prefix, g is a_groups[-1])]
    new_lines = list(lines)
    new_lines[p_start:p_end] = plan_out
    new_lines[ver_head + 1 : a_end] = arch_out
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


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
    """归档文件内是否已有该版本批次节（`## vX.Y.Z 开发期已修复`）。"""
    return re.search(rf"^## v{re.escape(version)} 开发期已修复", archive_text, re.M) is not None
