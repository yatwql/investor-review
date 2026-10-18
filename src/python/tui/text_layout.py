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

import re
import unicodedata
from collections.abc import Iterable

_ANSI_SEQ = re.compile(r"\x1b\[[0-9;]*m")

# 东亚宽度 W(ide)/F(ullwidth) 的字符占 2 列；A(mbiguous)（含盒线字符）与其余按 1 列计
_WIDE = ("W", "F")

# 内容行可用列数的下限——面板至少这么宽，窄面板不至于缩成一条
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

    Args:
        text: 原文（可含 ANSI 序列）。
        columns: 允许的最大显示列数（≤0 时返回空串）。
        ellipsis: 省略号（自身宽度计入列宽预算）。

    Returns:
        截断后的文本；未超宽时原样返回。
    """
    if columns <= 0:
        return ""
    if display_width(text) <= columns:
        return text
    budget = columns - display_width(ellipsis)
    if budget <= 0:
        return ellipsis[:0]
    out = ""
    for char in text:
        if display_width(out + char) > budget:
            break
        out += char
    return out + ellipsis
