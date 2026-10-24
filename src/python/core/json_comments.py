"""JSONC 注释剥离 — 叶子模块（仅标准库，禁止 import 其他项目模块）。

配置生成器输出带中文注释的 JSONC；所有读取路径都必须先经本模块剥离注释再
``json.loads``，禁止直接解析原始文本（字符串内的 ``//`` / ``/* */`` 不受影响）。

放在 ``core/`` 而非 ``config/`` 的原因：``core/logger.py``、``llm/pricing.py`` 等
core 级使用方也需要读配置，若从 ``config`` 包导入会形成向上依赖并可能成环。
``config/_comments.py`` 仅做再导出，保持配置包既有导入面。
"""

from __future__ import annotations

import json
from typing import IO, Any


def strip_json_comments(text: str) -> str:
    """剥离 JSON 中的 ``//`` 单行注释和 ``/* */`` 多行注释。

    逐字符扫描，仅在字符串外识别注释；字符串内的转义引号、``//``、``/*``
    均按普通字符保留。

    Args:
        text: 可能包含注释的 JSON 文本

    Returns:
        不含注释的纯 JSON 文本
    """
    result: list[str] = []
    i = 0
    length = len(text)
    in_string = False
    in_single_line_comment = False
    in_multi_line_comment = False

    while i < length:
        ch = text[i]

        if in_string:
            result.append(ch)
            if ch == "\\":
                i += 1
                if i < length:
                    result.append(text[i])
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_multi_line_comment:
            if ch == "*" and i + 1 < length and text[i + 1] == "/":
                i += 2
                in_multi_line_comment = False
            else:
                i += 1
            continue

        if in_single_line_comment:
            if ch == "\n":
                in_single_line_comment = False
                result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < length:
            nxt = text[i + 1]
            if nxt == "/":
                in_single_line_comment = True
                i += 2
                continue
            if nxt == "*":
                in_multi_line_comment = True
                i += 2
                continue

        if ch == '"':
            in_string = True

        result.append(ch)
        i += 1

    return "".join(result)


def loads(text: str) -> Any:
    """解析可能带注释的 JSON 文本（统一读取入口）。"""
    return json.loads(strip_json_comments(text))


def load(fp: IO[str]) -> Any:
    """从文件对象读取并解析可能带注释的 JSON（统一读取入口）。"""
    return loads(fp.read())


__all__ = ["strip_json_comments", "loads", "load"]
