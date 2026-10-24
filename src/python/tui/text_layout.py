"""终端文本宽度与盒线面板排版助手。

中文/全角字符在等宽终端占 2 列，而 `len()` 按码点计数只算 1——面板行若用
`' ' * N` 手写补白，含中文的行就会比含英文的行短，盒线右边框参差不齐；行与行
之间还各自写着不同的补白数（上下边框、分隔线、内容行三者口径不一），同一面板
的右边框因此对不到同一列。本模块按东亚宽度计算显示列数，并由 `render_panel`
按整块面板的最长行统一定宽，调用方不必预估列宽，也不会因某行超宽而撑破右边框。

ANSI 颜色序列不占显示列：`GREEN`/`RESET` 等常量在非 TTY 下为空串，但着色开启
时若不先剥离，会把转义字符按可见字符多算，故 `display_width` 先剔除。
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Iterable

_ANSI_SEQ = re.compile(r"\x1b\[[0-9;]*m")


def style_heading(text: str) -> str:
    """分组标题样式（蓝色粗体）——结构色，不承载状态语义。

    约定先排版（折行/截断）再调用本函数：`display_width` 会剔除 ANSI，但
    截断按字符逐个累加，先上色有把转义序列切断的风险；
    非 TTY / `NO_COLOR` 下颜色常量为空串，本函数退化为恒等（文本本身仍可读）。

    Args:
        text: 已排好版的标题文本。

    Returns:
        着色后的标题；无颜色能力时原样返回。
    """
    from src.python.core.ansi_colors import BLUE, BOLD, RESET

    return f"{BOLD}{BLUE}{text}{RESET}"


# 东亚宽度 W(ide)/F(ullwidth) 的字符占 2 列；A(mbiguous)（含盒线字符）与其余按 1 列计
_WIDE = ("W", "F")

# 内容行可用列数的下限——面板至少这么宽，窄面板不至于缩成一条
MIN_TERMINAL_COLUMNS = 40
"""终端列数下限（同时是全部上屏文案的窄屏设计基准与机检口径）。"""

MIN_FIELD_WIDTH = 41

# 标题与边框之间的固定装饰：`┌── ` + 标题 + ` `，即标题占 4 列外框
_TITLE_DECOR = 4


def display_width(text: str) -> int:
    """返回文本在等宽终端占用的列数。

    先剥离 ANSI 颜色序列；组合字符（重音符号等）不占列；东亚宽字符计 2 列。
    """
    width = 0
    for char in _ANSI_SEQ.sub("", text):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in _WIDE else 1
    return width


def terminal_columns(default: int = 100) -> int:
    """当前终端列数（实时尺寸优先，其次 `COLUMNS` 环境变量，最后兜底值）。

    优先级取实时值——终端 resize（手机横竖屏、分屏）后 ioctl 立即反映新宽度；
    `COLUMNS` 只是会话建立时的快照，常已过期。不取两者最大值，否则窄终端会被
    误判成宽屏（内容被终端硬折成锯齿）。下限 40 列，避免异常值压成不可读。

    Args:
        default: 探测不到时的兜底列数。

    Returns:
        终端列数（≥ ``MIN_TERMINAL_COLUMNS``）。
    """
    for fd in (1, 2):
        try:
            return max(MIN_TERMINAL_COLUMNS, os.get_terminal_size(fd).columns)
        except OSError:
            continue
    env = os.environ.get("COLUMNS")
    if env and env.isdigit() and int(env) > 0:
        return max(MIN_TERMINAL_COLUMNS, int(env))
    return max(MIN_TERMINAL_COLUMNS, default)


def pad_right(text: str, columns: int) -> str:
    """右补空格至指定显示列数，用于对齐表格列；已超宽则原样返回（不截断）。"""
    return text + " " * max(0, columns - display_width(text))


def wrap_display(text: str, columns: int) -> list[str]:
    """按显示列宽折行（中文按 2 列计），返回行列表。

    用于面板页脚图例：图例文本长度随文案演进变化，手写多行容易越界或被终端硬折
    得参差不齐。折行在**空白处**优先断行（保持词/短语完整），超长无空白串才按列
    硬切；已含换行的文本逐段处理。

    Args:
        text: 待折行文本（可含 ANSI 序列，宽度计算已剔除）。
        columns: 每行最大显示列数（≤0 时原样返回单行）。

    Returns:
        折行后的行列表（无内容时返回空列表）。
    """
    if columns <= 0:
        return [text]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for token in re.split(r"(\s+)", paragraph):
            if not token:
                continue
            candidate = current + token
            if display_width(candidate) <= columns or not current.strip():
                # 单个 token 本身就超宽时按列硬切，避免整行越界
                while display_width(candidate) > columns and display_width(token) > columns:
                    cut = ""
                    for char in token:
                        if display_width(cut + char) > columns:
                            break
                        cut += char
                    if current.strip():
                        lines.append(current.rstrip())
                        current = ""
                    lines.append(cut)
                    token = token[len(cut) :]
                    candidate = current + token
                current = candidate
                continue
            lines.append(current.rstrip())
            current = token.lstrip()
        lines.append(current.rstrip())
    return [line for line in lines if line.strip() or line == ""]


def render_panel(title: str, rows: Iterable[str | None] = (), *, min_field: int = MIN_FIELD_WIDTH) -> list[str]:
    """渲染一个盒线面板，返回待逐行打印的文本。

    Args:
        title: 面板标题（渲染为上边框 `┌── 标题 ──…─┐`）
        rows: 内容行；`None` 渲染为一条内区分隔线，`""` 渲染为空白行
        min_field: 内容可用列数的下限

    内区宽度取「标题所需」与「最长内容行」的较大者，四边因此对齐到同一列。
    """
    body = list(rows)
    field = max(
        [min_field, display_width(title) + _TITLE_DECOR - 1] + [display_width(row) for row in body if row is not None]
    )
    lines = [f"  ┌── {title} {'─' * (field - display_width(title) - _TITLE_DECOR + 1)}┐"]
    for row in body:
        if row is None:
            lines.append(f"  │{'─' * (field + 1)}│")
        else:
            lines.append(f"  │ {row}{' ' * (field - display_width(row))}│")
    lines.append(f"  └{'─' * (field + 1)}┘")
    return lines


def truncate_display(text: str, columns: int, ellipsis: str = "…") -> str:
    """按显示列宽截断文本（超宽时以省略号收尾），用于窄终端的单行压缩。

    ANSI 序列按零宽整体保留；截断时**必须补 RESET**——否则上一行被截在着色段中，
    颜色会泄漏到下一行（真实案例：窄档截断蓝色分组标题后，紧接着的章节行整体变蓝）。

    Args:
        text: 原文（可含 ANSI 序列）。
        columns: 允许的最大显示列数（≤0 时返回空串）。
        ellipsis: 省略号（自身宽度计入列宽预算）。

    Returns:
        截断后的文本；未超宽时原样返回；截断时以省略号收尾并闭合颜色。
    """
    if columns <= 0:
        return ""
    if display_width(text) <= columns:
        return text
    budget = columns - display_width(ellipsis)
    if budget <= 0:
        return ellipsis[:0]
    out: list[str] = []
    width = 0
    i = 0
    while i < len(text):
        match = _ANSI_SEQ.match(text, i)
        if match is not None:
            out.append(match.group())
            i = match.end()
            continue
        char = text[i]
        char_width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in _WIDE else 1)
        if width + char_width > budget:
            break
        out.append(char)
        width += char_width
        i += 1
    from src.python.core.ansi_colors import RESET

    return "".join(out) + ellipsis + RESET


def wrap_hanging(text: str, columns: int, indent: str = "    ") -> list[str]:
    """按列宽折行并给续行加悬挂缩进（面板内成段文字用，续行不顶到左边框）。

    首行用满 `columns` 列，续行**扣除缩进宽度后**再折行——否则「缩进 + 满宽续行」
    会超出面板内宽 2~10 列（窄终端上表现为右侧被硬折）。
    """
    indent_width = display_width(indent)
    remaining = text
    lines: list[str] = []
    first = True
    while remaining:
        budget = columns if first else max(10, columns - indent_width)
        wrapped = wrap_display(remaining, budget)
        if not wrapped:
            break
        head = wrapped[0]
        lines.append(head if first else indent + head)
        cut = remaining.find(head)
        if cut < 0:
            break
        remaining = remaining[cut + len(head) :].lstrip()
        first = False
    return lines


def wrap_prompt(prompt: str, columns: int | None = None) -> str:
    """``input()`` 提示折行助手：超宽按显示宽度折行，末行留「  > 」输入位。

    提示显示宽度不超过当前终端宽度时原样返回（零开销）；超窄屏（手机）
    折行后追加短尾缀行，输入光标与提示不再脱节。窄屏验收基准 40 列
    （与 :func:`terminal_columns` 下限一致），超长提示的机检守护见
    ``test_text_layout.py::TestInputPromptNarrowContract``。
    """
    columns = columns or terminal_columns()
    if display_width(prompt) <= columns:
        return prompt
    lines = wrap_display(prompt.strip(), columns)
    return "\n".join(lines) + "\n  >  "


def group_heading(title: str, columns: int | None = None, *, prefix: str = "  ") -> list[str]:
    """分组标题行（结构色）——主菜单与全部面板的**唯一产出点**。

    视觉契约（`DESIGN-TUI.md`「分组标题视觉纪律」）：
      - 形态统一为 ``── 标题 ──``，与首页分组同款，任何渠道不得自造分隔符；
      - 颜色统一走 :func:`style_heading`（蓝 + 粗，结构色，不承载状态语义）；
      - 宽度按终端折行（``prefix`` 不参与断行），窄屏不硬折、不撑破右边框。

    Args:
        title: 组标题（不含 ``──`` 装饰）。
        columns: 终端列数；``None`` 取实时值。
        prefix: 首行缩进（主菜单用 ``"  "``；已带缩进的盒线面板内用 ``""``）。

    Returns:
        可直接逐行打印的标题行列表（已着色，每行 ≤ ``columns``）。
    """
    cols = columns or terminal_columns()
    return [style_heading(line) for line in wrap_with_prefix(prefix, f"── {title} ──", cols)]


def wrap_with_prefix(prefix: str, text: str, columns: int, *, indent: str | None = None) -> list[str]:
    """带首行前缀的折行：首行用「前缀 + 正文」，续行按缩进对齐。

    与 :func:`wrap_hanging` 的区别：前缀（如 `  > [B] `、`  说明  : `）**不参与**
    折行断点——否则 `wrap_display` 会在前缀后的空白处断开，出现「第一行只剩前缀」
    的碎片行。折行预算逐行扣减：首行 = `columns - 前缀宽`，续行 = `columns - 缩进宽`。

    Args:
        prefix: 首行前缀（原样保留，可含 ANSI）。
        text: 正文。
        columns: 每行最大显示列数。
        indent: 续行缩进；缺省用与前缀等宽的空白（视觉上对齐到正文起始列）。

    Returns:
        行列表，每行显示宽度 ≤ `columns`（单 token 超宽时才硬切）。
    """
    head_indent = indent if indent is not None else " " * display_width(prefix)
    indent_width = display_width(head_indent)
    remaining = text
    lines: list[str] = []
    prefix_cell = prefix
    budget = max(10, columns - display_width(prefix_cell))
    while remaining:
        wrapped = wrap_display(remaining, budget)
        if not wrapped:
            break
        chunk = wrapped[0]
        lines.append(prefix_cell + chunk)
        cut = remaining.find(chunk)
        if cut < 0:
            break
        remaining = remaining[cut + len(chunk) :].lstrip()
        if not remaining:
            break
        prefix_cell = head_indent
        budget = max(10, columns - indent_width)
    return lines or [prefix]
