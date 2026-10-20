"""需求菜单表 ↔ 主菜单代码一致性（doc-drift 第 19 项）。

`requirements.md` §3.2「菜单选项」是需求文档里对主菜单的**结构化承诺**——它与
`tui/tui_menu.py` 的 `MENU_ITEMS`（键集合）/ `MENU_GROUPS`（分组与组内顺序）必须逐项一致。
该表是纯手写清单且此前无机检：组重排未跟、整行缺失、缓存管理编号与键位不符都不会被发现
（现行检查见下），因此按集合与序列关系逐项对账。

校验口径（全部为集合/序列关系，不写死条数，新增菜单项自动纳入）：
  1. 键集合：表格键集合 == `MENU_ITEMS` 键集合（双向报缺/多）；
  2. 分组标题序列：表格组标题 == `MENU_GROUPS` 标题序列 + 「系统」（退出项分组）；
  3. 组内成员与顺序：每组键序列 == `MENU_GROUPS` 对应元组；「系统」组 == 退出项键。
标签文案不比对（菜单标签含面向用户的完整说明，表格「功能」列是缩短版，逐字比对无意义）。
"""

from __future__ import annotations

import re

from ._shared import _REQUIREMENTS_MD, _doc_section, rel

# 表格键：单字符快捷键（字母或数字，与 MENU_ITEMS 的键位形态一致）
_KEY_RE = re.compile(r"^\|\s*([A-Za-z0-9])\s*\|")
_EXIT_GROUP = "系统"


def parse_requirements_menu(text: str) -> list[tuple[str, list[str]]]:
    """解析 §3.2 菜单表 → ``[(组标题, [键…], …)]``（保持文档顺序）。

    Args:
        text: `requirements.md` 全文。

    Returns:
        分组序列；未找到该章节时返回空列表。
    """
    section = _doc_section(text, "### 3.2 菜单选项", "### 3.3")
    if not section:
        return []
    groups: list[tuple[str, list[str]]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        head = cells[0] if cells else ""
        if head.startswith("**") and head.strip("*"):
            groups.append((head.strip("*").strip(), []))
            continue
        match = _KEY_RE.match(line)
        if match and groups:
            groups[-1][1].append(match.group(1).upper())
    return groups


def check_requirements_menu_table(text: str) -> list[str]:
    """比对 §3.2 菜单表与 `tui/tui_menu.py` 的菜单定义，返回不一致描述列表。"""
    from src.python.tui.tui_menu import MENU_GROUPS, MENU_ITEMS

    doc_groups = parse_requirements_menu(text)
    if not doc_groups:
        return [f"{rel(_REQUIREMENTS_MD)}: 未解析到 §3.2 菜单选项表（章节标题或表头被改动）"]

    menu_keys = [key for key, *_ in MENU_ITEMS]
    exit_keys = [key for key, _label, _cb, is_exit in MENU_ITEMS if is_exit]
    expected = [(title, list(keys)) for title, keys in MENU_GROUPS]
    expected += [(_EXIT_GROUP, exit_keys)]

    findings: list[str] = []

    # ① 键集合（双向）
    doc_keys = [k for _title, keys in doc_groups for k in keys]
    missing = [k for k in menu_keys if k not in doc_keys]
    extra = [k for k in doc_keys if k not in menu_keys]
    dup = sorted({k for k in doc_keys if doc_keys.count(k) > 1})
    if missing:
        findings.append(f"{rel(_REQUIREMENTS_MD)}: §3.2 菜单表缺菜单项 {missing}（MENU_ITEMS 中存在）")
    if extra:
        findings.append(f"{rel(_REQUIREMENTS_MD)}: §3.2 菜单表多出未实现的菜单项 {extra}")
    if dup:
        findings.append(f"{rel(_REQUIREMENTS_MD)}: §3.2 菜单表键重复 {dup}")

    # ② 分组标题序列
    doc_titles = [title for title, _keys in doc_groups]
    exp_titles = [title for title, _keys in expected]
    if doc_titles != exp_titles:
        findings.append(f"{rel(_REQUIREMENTS_MD)}: §3.2 分组标题/次序 {doc_titles} ≠ 菜单定义 {exp_titles}")

    # ③ 组内成员与顺序
    doc_map = dict(doc_groups)
    for title, keys in expected:
        if title not in doc_map:
            continue
        if doc_map[title] != keys:
            findings.append(f"{rel(_REQUIREMENTS_MD)}: §3.2「{title}」组键顺序 {doc_map[title]} ≠ 菜单定义 {keys}")
    return findings
