"""`check-doc-drift` 手册菜单块检查 —— 双手册主菜单 code block ↔ tui_menu.MENU_ITEMS（第 18 项）。

主菜单标签的真值在 ``tui/tui_menu.py::MENU_ITEMS``；双手册
（how-to-start.md / how-to-use-tui-menu.md）的主菜单 code block 是文档侧副本，
本模块机检「键集合一致 + 每键标签头一致」。标签头 = 第一个全角括号前的文本——
手册允许在括号内追加补充说明（如 [D] 的「二级：」提示），头文本必须与真值相同。

同时承载**返回键不变量**（同属第 18 项域）：子菜单面板返回键已全局统一为 0，
本模块对全部受检文档校验「返回主菜单」行的键必须为 0——覆盖主菜单块以外的
图块/列表项/表格行（本轮实际拦住的残留形态正是表格内 `` `[B]` 返回``，人工
grep 模式会漏）；自由 prose 叙述豁免，防 FAQ「Ctrl+C 返回主菜单」类误报。
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


#: 返回键紧邻键记号：`[X]` 与「返回主菜单」间仅记号/空白（≤6 字符）——
#: 排除行内远处 `[L]` 等非返回键（防 changelog 式列表行误报）
_RET_NEAR_KEY_RE = re.compile(r"\[([A-Za-z0-9])\][`*\s]{0,6}返回主菜单")
#: 返回前缀行尾裸键：列表/图块行「**0 返回」「0 返回」形态
_RET_TAIL_KEY_RE = re.compile(r"([A-Za-z0-9])\s*(?:\*\*|\])?\s*$")


def check_return_key_invariant(manual_texts: dict[Path, str]) -> list[str]:
    """校验文档中「返回主菜单」的键必须为 0（返回键全局统一），返回不一致列表。

    校验域：code block 内行 ∪ 列表项行 ∪ 表格行（结构化描述）；自由 prose
    叙述豁免（FAQ 的「Ctrl+C 返回主菜单」、QA 流内「`q` 返回主菜单」——线性
    输入流退出非面板导航）。紧邻与行尾键均解析不出时同样豁免，宁漏勿误报。
    历史记录类文档（changelog/plan/review-findings）由扫描入口排除。
    """
    findings: list[str] = []
    for path, text in manual_texts.items():
        in_block = False
        for lineno, raw in enumerate(text.splitlines(), 1):
            stripped = raw.strip()
            if stripped.startswith("```"):
                in_block = not in_block
                continue
            if "返回主菜单" not in stripped:
                continue
            in_list = bool(re.match(r"^\s*[-*]\s", raw))
            in_table = stripped.startswith("|")
            if not (in_block or in_list or in_table):
                continue
            m = _RET_NEAR_KEY_RE.search(stripped)
            if m is None:
                m = _RET_TAIL_KEY_RE.search(stripped[: stripped.find("返回主菜单")])
            if m is None:
                continue  # 键解析不出（叙述/特殊形态）→ 豁免
            if m.group(1) != "0":
                findings.append(f"{rel(path)}:{lineno}: 「返回主菜单」键为 [{m.group(1)}]，应为 0（返回键全局统一）")
    return findings
