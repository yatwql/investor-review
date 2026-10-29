"""符号表与 ASCII 降级（`TUI_ASCII=1`）。

为什么在输出层替换而不逐处查表：全仓 TUI 层有百余处符号字面量（结构线、游标、
实验标记、进度块、状态点），分散在 17 个文件。逐处查表会让可读的版面代码变成拼接
表达式，且每处都要单独核对宽度。这里按「**一字符换一字符**」映射，在写出流的最
后一刻替换——宽度按定义不变，版面代码一行不动。

映射约束（新增符号必须满足）：

  - 每条映射两侧的显示宽度相同（当前全部为 1 列）；
  - 只映射装饰性符号，不动数字、字母、标点与中文——`TUI_ASCII` 是「让老控制台与
    朗读工具能读」，不是「把界面换成英文」。
"""

from __future__ import annotations

import sys
from typing import TextIO

#: 装饰符号 → ASCII 等价物（两侧显示宽度必须相同）
ASCII_MAP: dict[str, str] = {
    "─": "-",
    "│": "|",
    "├": "|",
    "└": "+",
    "┌": "+",
    "┐": "+",
    "┘": "+",
    "═": "=",
    "▸": ">",
    "▏": "|",
    "⚗": "*",
    "█": "#",
    "░": ".",
    "●": "O",
    "○": "o",
    "⤷": ">",
    "▲": "^",
    "▼": "v",
    "·": ".",
    "…": "~",
}

_TRANSLATION = str.maketrans(ASCII_MAP)


def ascii_mode_requested() -> bool:
    """是否请求 ASCII 降级（环境变量 ``TUI_ASCII`` 非空）。"""
    import os

    return bool(os.environ.get("TUI_ASCII"))


def translate(text: str) -> str:
    """按符号表把装饰符号替换为 ASCII 等价物（其余字符原样保留）。"""
    return text.translate(_TRANSLATION)


class AsciiStream:
    """透明代理：写出前替换装饰符号，其余行为透传（含 ``isatty``）。"""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        return self._stream.write(translate(text))

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def install_ascii_stream(stream: TextIO | AsciiStream | None = None) -> TextIO | AsciiStream:
    """把 ASCII 代理装到 ``sys.stdout`` 并返回（未请求时原样返回，零行为变化）。"""
    if not ascii_mode_requested():
        return stream if stream is not None else sys.stdout
    target = stream if stream is not None else sys.stdout
    if isinstance(target, AsciiStream):
        return target
    wrapper = AsciiStream(target)
    if stream is None:
        sys.stdout = wrapper
    return wrapper
