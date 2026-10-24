"""`check-doc-drift` 面板编号族检查 —— `[C]` 章节显隐与 `[S]` 章内内容的编号派生校验。

从 :mod:`_doc_drift._format` 拆出：面板编号的派生规则（章节注册表 + 面板归属）与
其余文档格式族（章节表 / 开关表 / 默认值 / 覆盖计数）没有共享状态，独立成模块后
两份文件都留在行数警告线内，改动面板口径时也不必在长文件里定位。

校验口径：`[S]` 六组编号由 `panel_option_numbers` 派生，`[C]` 章节与 `7.1/7.2`
子项由章节注册表派生；组/块标题区间与 features 键名映射逐项与派生值比对。
"""

from __future__ import annotations

import re

from _shared.checklib import rel
from src.python.config.chapter_registry import (
    BLOCK_LABELS,
    BLOCK_ORDER,
    SOURCE_FEATURES,
    chapter_number,
    chapter_numbers,
    chapter_registry,
    chapters_in_block,
    sub_item_numbers,
)
from src.python.config.features import PANEL_GROUPS, feature_switch_registry, panel_option_numbers
from _doc_drift._shared import _TUI_MENU_MD
from _doc_drift._format import _group_doc_name


_HOWTO_PANEL_HEADING = re.compile(r"^####\s+\[([CS])\]")

#: 面板章节表格行（章节编号或区间）；子项编号另用 `_SUB_ITEM_ROW`（十进制）
_PANEL_ROW = re.compile(r"^\|\s*(\d+)(?:[-–](\d+))?\s*\|")
_SUB_ITEM_ROW = re.compile(r"^\|\s*(\d+\.\d+)\s*\|")

#: 每组的块标题「组短名（面板编号 X-Y）」——边界由 ``panel_option_numbers`` 派生
_GROUP_PANEL_RANGE: dict[str, "re.Pattern[str]"] = {
    group: re.compile(re.escape(_group_doc_name(group)) + r"（面板编号\s*(\d+)-(\d+)）")
    for group in PANEL_GROUPS["[S]"]
}

#: ``[C]`` 四块的块标题「块名（X-Y，...）」——边界由章节注册表派生；单块可写「（16，...）」
_BLOCK_PANEL_RANGE: dict[str, "re.Pattern[str]"] = {
    block: re.compile(re.escape(BLOCK_LABELS[block]) + r"（(\d+)(?:-(\d+))?") for block in BLOCK_ORDER
}

#: features.json 键名 → 面板与编号映射表行：``| `flag` | `[S]` 1 | 组名 | 功能 |``
_PANEL_KEY_MAP_ROW = re.compile(r"^(?:>\s*)?\|\s*`([a-z0-9_]+)`\s*\|\s*`\[([CS])\]`\s*([\d.]+)\s*\|\s*([^|]+?)\s*\|")


def _panel_section(doc_text: str, panel: str) -> list[str] | None:
    """截取手册中某面板小节：``#### [S]`` / ``#### [C]`` 起，到下一个 ``####``/``##``/``---`` 止。"""
    lines = doc_text.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if (m := _HOWTO_PANEL_HEADING.match(ln)) is not None and m.group(1) == panel),
        None,
    )
    if start is None:
        return None
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("#### ") or lines[i].startswith("## ") or lines[i] == "---"
        ),
        len(lines),
    )
    return lines[start:end]


def check_panel_numbering(doc_text: str) -> list[str]:
    """校验手册两面板编号表与注册表派生一致。

    - ``[S]``：六组 20 项，编号 = ``panel_option_numbers("[S]")``（组序派生、无 LLM 前缀）；
      组块标题区间与 features.json 键名映射同源；
    - ``[C]``：章节编号自 1 连续 + 智囊团子项（``7.1``/``7.2`` 形态），四块标题区间由章节注册表派生。

    面板编号一律派生、不硬编码——新增/挪动章节或开关时，手册表格不改即报错。
    """
    findings: list[str] = []

    s_section = _panel_section(doc_text, "S")
    if s_section is None:
        findings.append(f"{rel(_TUI_MENU_MD)}: 未找到 [S] 面板编号表区段")
    else:
        numbered = panel_option_numbers("[S]")
        got: list[int] = []
        for line in s_section:
            m = _PANEL_ROW.match(line)
            if not m:
                continue
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            got.extend(range(lo, hi + 1))
        expect = [n for n, _flag, _d in numbered]
        if got != expect:
            findings.append(
                f"{rel(_TUI_MENU_MD)}: [S] 开关编号序列 {got or '空'} 与派生编号 "
                f"{expect[0]}~{expect[-1]}（{len(expect)} 项，连续无缺）不一致"
            )
        group_numbers: dict[str, list[int]] = {}
        for number, _flag, definition in numbered:
            group_numbers.setdefault(definition.group, []).append(number)
        section_text = "\n".join(s_section)
        for group, numbers in group_numbers.items():
            name = _group_doc_name(group)
            first, last = numbers[0], numbers[-1]
            m = _GROUP_PANEL_RANGE[group].search(section_text)
            if not m:
                findings.append(f"{rel(_TUI_MENU_MD)}: 缺少组块标题「{name}（面板编号 {first}-{last}）」")
            elif (int(m.group(1)), int(m.group(2))) != (first, last):
                findings.append(
                    f"{rel(_TUI_MENU_MD)}: 组「{name}」块标题编号 {m.group(1)}-{m.group(2)} "
                    f"与派生区间 {first}-{last} 不一致"
                )

    p_section = _panel_section(doc_text, "C")
    if p_section is None:
        findings.append(f"{rel(_TUI_MENU_MD)}: 未找到 [C] 面板编号表区段")
    else:
        chapter_got: list[int] = []
        sub_got: list[str] = []
        for line in p_section:
            m = _PANEL_ROW.match(line)
            if m:
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.group(2) else lo
                chapter_got.extend(range(lo, hi + 1))
            sub = _SUB_ITEM_ROW.match(line)
            if sub:
                sub_got.append(sub.group(1))
        chapter_expect = [n for n, _e in chapter_numbers()]
        if chapter_got != chapter_expect:
            findings.append(
                f"{rel(_TUI_MENU_MD)}: [C] 章节编号序列 {chapter_got or '空'} 与派生编号 "
                f"{chapter_expect[0]}~{chapter_expect[-1]} 不一致"
            )
        sub_expect = list(sub_item_numbers())
        if sub_got != sub_expect:
            findings.append(f"{rel(_TUI_MENU_MD)}: [C] 子项编号 {sub_got or '空'} 与派生 {sub_expect} 不一致")
        p_text = "\n".join(p_section)
        for block in BLOCK_ORDER:
            numbers = [chapter_number(entry.key) for entry in chapters_in_block(block)]
            first, last = numbers[0], numbers[-1]
            m = _BLOCK_PANEL_RANGE[block].search(p_text)
            if not m:
                findings.append(f"{rel(_TUI_MENU_MD)}: 缺少 [C] 块标题「{BLOCK_LABELS[block]}（{first}-{last}）」")
                continue
            got_pair = (int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1)))
            if got_pair != (first, last):
                findings.append(
                    f"{rel(_TUI_MENU_MD)}: [C] 块「{BLOCK_LABELS[block]}」标题编号 {got_pair[0]}-{got_pair[1]} "
                    f"与派生区间 {first}-{last} 不一致"
                )

    # features.json 键名 → 面板/编号映射：全量、按面板顺序、组名一致
    got_pairs: list[tuple[str, str, str, str]] = []
    for line in doc_text.splitlines():
        m = _PANEL_KEY_MAP_ROW.match(line)
        if m and m.group(1) in feature_switch_registry:
            got_pairs.append((m.group(1), m.group(2), m.group(3), m.group(4).strip()))
    expect_pairs: list[tuple[str, str, str, str]] = [
        (flag, "S", str(number), _group_doc_name(definition.group))
        for number, flag, definition in panel_option_numbers("[S]")
    ]
    for entry in chapter_registry:
        if entry.source != SOURCE_FEATURES:
            continue
        definition = feature_switch_registry[entry.key]
        expect_pairs.append((entry.key, "C", str(chapter_number(entry.key)), _group_doc_name(definition.group)))
    for sub_number, flag in sub_item_numbers().items():
        expect_pairs.append((flag, "C", sub_number, _group_doc_name(feature_switch_registry[flag].group)))
    if got_pairs != expect_pairs:
        findings.append(
            f"{rel(_TUI_MENU_MD)}: features.json 键名→面板编号映射 {got_pairs} 与注册表派生 {expect_pairs} 不一致"
        )
    return findings
