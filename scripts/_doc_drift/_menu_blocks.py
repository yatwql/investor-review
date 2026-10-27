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

from _shared.checklib import rel
from src.python.tui.handlers_config import GLOBAL_SETTINGS_ITEMS
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
_RET_NEAR_KEY_RE = re.compile(r"\[([A-Za-z0-9])\][`*\s]{0,6}返回主菜单")
#: 返回前缀行尾裸键：列表/图块行「**0 返回」「0 返回」形态
_RET_TAIL_KEY_RE = re.compile(r"([A-Za-z0-9])\s*(?:\*\*|\])?\s*$")
#: 二级面板键集合（`[G]` 全局设置项 ∪ `[D]` 诊断项）：裸写这些字母时提示改写成
#: 「菜单 `G` → `X`」/「菜单 `D` → `X`」，避免读者把二级键当主菜单键找。
_SUBMENU_KEYS: frozenset[str] = frozenset({item[0] for item in GLOBAL_SETTINGS_ITEMS}) | frozenset({"V", "H", "T", "L"})

#: 二级面板的父子归属（箭头路径合法性）：`[G]` 全局设置 / `[D]` 诊断与排查
_SUBMENU_CHILDREN: dict[str, frozenset[str]] = {
    "G": frozenset({item[0] for item in GLOBAL_SETTINGS_ITEMS}),
    "D": frozenset({"L", "V", "H", "T"}),
}

#: 「主菜单」声明分句切分：分句内才成立「主菜单 + 键」的同句关系
_MAIN_MENU_CLAUSE_SPLIT_RE = re.compile(r"[，。；：、（）()]")
#: 分句内出现这些词即说明作者已在说「层级关系」，不属「把二级项当主菜单项」误写
_MAIN_MENU_CLAIM_EXEMPT = ("二级", "一级", "不在", "→", "->", "不是")
#: 分句内键记号：仅反引号包裹的 `[X]`（裸字母不参与，避免英文首字母误捕）
_CLAUSE_KEY_REF_RE = re.compile(r"`\[([A-Za-z0-9])\]`")
#: 箭头路径：`` `[X]` → `[Y]` ``（含 `->`）
_SUBMENU_PATH_RE = re.compile(r"`\[([A-Za-z0-9]+)\]`\s*(?:→|->)\s*`\[([A-Za-z0-9.]+)\]`")

#: 正文菜单引用：``菜单 `X` `` / ``菜单 `[X]` `` / ``菜单 [X]`` / ``菜单 **`[X]`**`` / 裸键 ``菜单 F 的…``
#: 裸键形态必须紧跟空白/标点/句末，否则「主菜单 code block」的 ``c`` 会被误捕
_MENU_REF_RE = re.compile(
    r"菜单\s*(?:\*\*)?(?:"
    r"`\[([A-Za-z0-9])\]`"
    r"|`([A-Za-z0-9])`"
    r"|\[([A-Za-z0-9])\]"
    r"|([A-Za-z0-9])(?=[\s，。、；：（）]|$)"
    r")"
)


def check_menu_key_references(docs: dict[Path, str]) -> list[str]:
    """校验正文「菜单 `X`」引用均为主菜单键（第 18 项域）。

    主菜单块校验只能护住 code block；正文里的「菜单 `C`」类引用无人看管——
    菜单编号调整或把若干项收进 `[D]` 二级面板后，正文往往会留着已不存在的主
    菜单键，读者按提示直接找不到入口。

    合法域 = ``MENU_ITEMS`` 键 ∪ 返回键 ``0``；``[G]`` 的二级选项（C/F/O/M）
    必须以「菜单 `G` → `F`」写法出现（写成裸「菜单 `F`」即发 finding）——例外是
    该字母本身已是主菜单键者（如 `C` 现为主菜单「章节显隐」，裸写合法）。

    另三条同域规则（均针对“读者按文档找不到入口”的同一后果）：

    1. **主菜单归属**：分句内把二级项说成在主菜单里（「`[T]` 恒出现在主菜单中」）即
       发 finding——二级项的入口是 ``[D] → [T]``；已在说「二级 / 不在 / 箭头路径」
       的分句豁免（「`[T]` 是 `[D]` 的二级项」属正确表述）。
    2. **箭头路径合法性**：``[X] → [Y]`` 要求 ``X`` 为 `[G]` / `[D]` 且 ``Y`` 属其二级项。
    3. 三项均在手册与 `README.md` 范围内生效，历史记录类文档由扫描入口排除。
    """
    findings: list[str] = []
    allowed = set(_MENU_LABEL_BY_KEY) | {"0"}
    for path, text in docs.items():
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in _MENU_REF_RE.finditer(line):
                key = next(g for g in match.groups() if g)
                if key.upper() in allowed:
                    continue
                hint = (
                    f"（若指 [G] 的二级选项，请写作「菜单 `G` → `{key.upper()}`」）"
                    if key.upper() in _SUBMENU_KEYS
                    else "（MENU_ITEMS 无此项）"
                )
                shown = match.group(0).strip()
                findings.append(f"{rel(path)}:{lineno}: 「{shown}」不是主菜单键{hint}")
            findings.extend(_main_menu_claim_findings(path, lineno, line, allowed))
            findings.extend(_submenu_path_findings(path, lineno, line))
    return findings


def _main_menu_claim_findings(path: Path, lineno: int, line: str, allowed: set[str]) -> list[str]:
    """分句内把二级项说成在主菜单里 → finding（同一分句只报一次）。"""
    findings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for clause in _MAIN_MENU_CLAUSE_SPLIT_RE.split(line):
        if "主菜单" not in clause:
            continue
        if any(token in clause for token in _MAIN_MENU_CLAIM_EXEMPT):
            continue
        stripped = clause.strip().strip("*").strip()
        for match in _CLAUSE_KEY_REF_RE.finditer(clause):
            key = match.group(1).upper()
            if key in allowed or key not in _SUBMENU_KEYS:
                continue
            if (key, stripped) in seen:
                continue
            seen.add((key, stripped))
            findings.append(
                f"{rel(path)}:{lineno}: 「{stripped}」把二级项 [{key}] 说成在主菜单里"
                f"（二级项须写作 `[D]` → `[{key}]` 或 `[G]` → `[{key}]`，主菜单没有该项）"
            )
    return findings


def _submenu_path_findings(path: Path, lineno: int, line: str) -> list[str]:
    """箭头路径 ``[X] → [Y]`` 的父子关系必须成立。"""
    findings: list[str] = []
    for match in _SUBMENU_PATH_RE.finditer(line):
        parent, child = match.group(1).upper(), match.group(2).upper()
        children = _SUBMENU_CHILDREN.get(parent)
        if children is not None and child in children:
            continue
        if children is None:
            findings.append(f"{rel(path)}:{lineno}: 「[{parent}] → [{child}]」无效——[{parent}] 无二级项")
        else:
            findings.append(f"{rel(path)}:{lineno}: 「[{parent}] → [{child}]」无效——[{parent}] 下无 [{child}] 项")
    return findings


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
