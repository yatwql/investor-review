"""`check-doc-drift` 手册菜单块检查 —— 双手册主菜单 code block ↔ tui_menu.MENU_ITEMS（第 18 项）。

主菜单标签的真值在 ``tui/tui_menu.py::MENU_ITEMS``；双手册
（how-to-start.md / how-to-use-tui-menu.md）的主菜单 code block 是文档侧副本，
本模块机检「键集合一致 + 每键标签头一致」。标签头 = 第一个全角括号前的文本——
手册允许在括号内追加补充说明（如 [D] 的「二级：」提示），头文本必须与真值相同。
"""

from __future__ import annotations

import re
from pathlib import Path

from _checklib import rel
from src.python.tui.tui_menu import MENU_ITEMS

#: 主菜单项：(快捷键, 显示标签, 回调, 是否退出)
_MENU_LABEL_BY_KEY = {key: label for key, label, _cb, _is_quit in MENU_ITEMS}
_ITEM_RE = re.compile(r"^\[(\w)\]\s+(.+)$")
#: 多列菜单行的切分点：两个以上空白后紧跟下一个按键记号
_COLUMN_SPLIT_RE = re.compile(r"\s{2,}(?=\[)")
#: 行首光标前缀（TUI 主菜单输入提示符）
_CURSOR_PREFIX_RE = re.compile(r"^>\s*")
#: 主菜单块识别：同时出现首项 [E] 与退出项 [X] 的围栏代码块
_BLOCK_KEYS = ("[E]", "[X]")


def parse_menu_block_lines(md_text: str) -> dict[str, str]:
    """解析主菜单围栏块 → ``{按键: 标签}``（多块合并；无块返回空 dict）。

    行前导空白与 ``> `` 光标前缀剥除；两列排版的行按 ``_COLUMN_SPLIT_RE``
    切分为多段。不含 [E] 或 [X] 的围栏块（非主菜单）忽略。
    """
    items: dict[str, str] = {}
    in_block = False
    block_lines: list[str] = []
    for raw in md_text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            if in_block:
                block = "\n".join(block_lines)
                if all(key in block for key in _BLOCK_KEYS):
                    for line in block_lines:
                        for segment in _COLUMN_SPLIT_RE.split(line.strip()):
                            match = _ITEM_RE.match(_CURSOR_PREFIX_RE.sub("", segment))
                            if match:
                                items[match.group(1)] = match.group(2).strip()
                block_lines = []
            in_block = not in_block
            continue
        if in_block:
            block_lines.append(raw)
    return items


def _label_head(label: str) -> str:
    """标签头：第一个全角括号前的文本（手册允许在括号内补充说明）。"""
    return label.split("（", 1)[0].strip()


def check_menu_blocks(manual_texts: dict[Path, str]) -> list[str]:
    """逐手册校验主菜单块与 ``MENU_ITEMS`` 一致，返回不一致描述列表。"""
    findings: list[str] = []
    for path, text in manual_texts.items():
        documented = parse_menu_block_lines(text)
        if not documented:
            findings.append(f"{rel(path)}: 未找到主菜单 code block（需同时含 [E] 与 [X]）")
            continue
        expected_keys = set(_MENU_LABEL_BY_KEY)
        got_keys = set(documented)
        for key in sorted(expected_keys - got_keys):
            findings.append(f"{rel(path)}: 主菜单块缺少 [{key}] {_MENU_LABEL_BY_KEY[key]}")
        for key in sorted(got_keys - expected_keys):
            findings.append(f"{rel(path)}: 主菜单块出现未知按键 [{key}]（MENU_ITEMS 无此项）")
        for key in sorted(expected_keys & got_keys):
            want = _label_head(_MENU_LABEL_BY_KEY[key])
            got = _label_head(documented[key])
            if got != want:
                findings.append(f"{rel(path)}: [{key}] 标签头「{got}」与 tui_menu.MENU_ITEMS「{want}」不一致")
    return findings
