"""错误尾巴：``[ERR]`` 统一输出「原因 → 下一步动作」。

契约要求错误行给「原因 + 下一步动作」，而动作短语必须指到具体菜单键才可执行。
短语取自 :mod:`src.python.tui.action_hints`（与页头状态行同一份），本模块只负责
拼装上屏形状：``  [ERR] 原因 → [D]→L 看运行日志``。

不进本模块的两类行：
  - **就地纠正类**输入校验（「金额应为数字」「份额必须大于 0」「无效编号」）——用户
    下一步就是在同一条提示里重输，键路径反而是噪声；
  - **进度/成功行**（``[..]`` / ``[OK]`` / ``[!]``）——动作信息由上下文自带。
"""

from __future__ import annotations

from collections.abc import Callable

from src.python.core.ansi_colors import RED, RESET
from src.python.tui.action_hints import action_phrase

#: 续行缩进（与 ``[ERR]`` 正文起始列对齐：两空格 + 前缀 5 列）
_ADVICE_INDENT = "        "


def format_error_lines(
    message: str,
    action_key: str | None = None,
    *,
    advice: str | None = None,
    columns: int | None = None,
) -> list[str]:
    """拼装错误行（纯函数：不打印，供用例直接断言形状）。

    折行按终端宽度（与菜单/面板同一折行设施）：窄屏手机上错误行不会硬折成锯齿，
    也不会因为多加一句动作短语而超宽。

    Args:
        message: 面向用户的原因（不含前缀、不含动作）。
        action_key: :data:`action_hints.ACTION_TEMPLATES` 的语义名；None = 不给动作。
        advice: 可选的补充一句（缩进续行）。
        columns: 折行宽度；None 取实时终端宽度。

    Returns:
        上屏行列表：首行带 ``[ERR]`` 与 ``→ 短语``，其后为可选建议行。
    """
    from src.python.tui.text_layout import terminal_columns, wrap_with_prefix

    phrase = action_phrase(action_key)
    tail = f" → {phrase}" if phrase else ""
    cols = columns or terminal_columns()
    body = wrap_with_prefix("  ", f"[ERR] {message}{tail}", cols)
    head = body[0].replace("[ERR]", f"{RED}[ERR]{RESET}", 1)
    lines = [head, *body[1:]]
    if advice:
        lines.extend(wrap_with_prefix(_ADVICE_INDENT, advice, cols))
    return lines


def emit_error(
    message: str,
    action_key: str | None = None,
    *,
    advice: str | None = None,
    echo: Callable[[str], None] = print,
) -> None:
    """输出带下一步动作的错误行（TUI 各 ``[ERR]`` 站点的统一出口）。"""
    for line in format_error_lines(message, action_key, advice=advice):
        echo(line)
