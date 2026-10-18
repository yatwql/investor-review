"""`[S]` 功能开关面板的响应式排版本模块。

职责边界：**只排版、不取数、不写配置**——条目数据（编号/名称/键名/状态/备注）
由 `handlers_config` 从注册表装配后传入，本模块按终端宽度决定「一行怎么摆」。

为什么单独成模块：TUI 会在**不同终端宽度**下使用（笔记本宽终端、手机 SSH 窄
终端），同一份条目必须能自适应三种版面；把宽度决策与列对齐集中在此，避免渠道
处理器里散落 `if width` 分支，也让排版可被纯函数用例逐档锁定（不需要真终端）。

三档版面（`layout_tier`）：

================  ============  ================================================
档位              触发宽度      版面
================  ============  ================================================
``wide``          ≥ 96 列       单行四列：``编号. 名称 | 键名(淡色) | 状态 | 备注``
``medium``        64~95 列      两行：``编号. 名称 [状态]`` / 缩进 ``键名(淡色) 备注``
``narrow``        < 64 列       单行压缩：``编号 名称(可截断) [开/关]``，键名改用 ``? 编号`` 查
================  ============  ================================================

不变式：任何档位下**每一行的显示宽度都不超过面板内宽**（`inner_width`）——窄终端
上宁可截断名称，也不让盒线右边框错位或被终端硬折成锯齿。
"""

from __future__ import annotations

import os

from src.python.core.ansi_colors import DIM, RESET
from src.python.tui.text_layout import display_width, pad_right, truncate_display, wrap_display

#: 单行四列版面的最小终端宽度（含面板边框与标题占位）
WIDE_MIN_COLUMNS = 96
#: 两行版本的终端宽度下限（低于此值降级为窄终端压缩版）
MEDIUM_MIN_COLUMNS = 64
#: 面板边框与左右留白占用的列数（`  │ ` + `│`）
_PANEL_CHROME = 6

#: 状态短标签（窄终端用，省 2 列）
_STATUS_SHORT = {True: "开", False: "关"}
#: 状态标签（宽/中档用）
_STATUS_LONG = {True: "开启", False: "关闭"}


def terminal_columns(default: int = 100) -> int:
    """当前终端列数（读 `COLUMNS` 环境变量与实际终端尺寸，取可用值的较大者兜底）。

    Args:
        default: 无法探测时的兜底列数。

    Returns:
        终端列数（下限 40，避免异常值把小面板压成不可读）。
    """
    # 优先级：显式 COLUMNS（用户/SSH 客户端声明）> 实际终端尺寸 > 兜底值。
    # 不取三者最大值——手机 SSH 的 COLUMNS 本就小于笔记本，取最大会让窄终端
    # 永远走宽版面（面板被终端硬折成锯齿）。
    env = os.environ.get("COLUMNS")
    if env and env.isdigit() and int(env) > 0:
        return max(40, int(env))
    try:
        return max(40, os.get_terminal_size().columns)
    except OSError:
        return max(40, default)


def layout_tier(columns: int) -> str:
    """按终端列数返回版面档位：``wide`` / ``medium`` / ``narrow``。"""
    if columns >= WIDE_MIN_COLUMNS:
        return "wide"
    if columns >= MEDIUM_MIN_COLUMNS:
        return "medium"
    return "narrow"


def inner_width(columns: int) -> int:
    """面板内容可用的显示列数（终端宽度扣除盒线边框与左右留白）。"""
    return max(30, columns - _PANEL_CHROME)


def _status(enabled: bool, tier: str) -> str:
    """状态文本：宽/中档用「开启/关闭」，窄档用「开/关」。"""
    label = _STATUS_SHORT[enabled] if tier == "narrow" else _STATUS_LONG[enabled]
    return f"[{label}]"


def format_heading(head: str, enabled_count: int, total: int, columns: int) -> str:
    """分组标题行（含该组开启数，窄终端自动截断）。"""
    text = f"{head}（{enabled_count}/{total} 开）"
    return truncate_display(text, inner_width(columns))


def format_item(
    *,
    number: int,
    label: str,
    key: str,
    enabled: bool,
    star: str,
    marker: str,
    notes: str,
    columns: int,
    name_column: int,
    key_column: int,
    number_width: int = 1,
) -> list[str]:
    """把一个开关/模块条目排版成 1~2 行（随终端宽度自适应）。

    Args:
        number: 面板编号（用户可直接输入的整数）。
        label: 中文显示名。
        key: 配置键名（`features.json` 键 / `enabled_llm` 子键）。
        enabled: 当前是否开启。
        star: 与出厂默认不一致的标记（`"*"` 或 `""`）。
        marker: 实验项标记（`⚗` + 占位空格，已按显示列补齐）。
        notes: 备注（互指提示 / 费用摘要 / 启用统计），已拼好的纯文本。
        columns: 终端列数。
        name_column: 名称列宽（宽/中档对齐用，取面板内最长名称）。
        key_column: 键名列宽（同上）。
        number_width: 编号列宽（按最大编号位数右对齐，使 1 与 10 起各列同位）。

    Returns:
        1 行（wide/narrow）或 2 行（medium）文本，均不超过 `inner_width(columns)`。
    """
    tier = layout_tier(columns)
    limit = inner_width(columns)
    status = _status(enabled, tier)

    num = f"{number:>{number_width}}"

    if tier == "wide":
        head = f"{num}. {marker}{pad_right(label, name_column)} {DIM}{pad_right(key, key_column)}{RESET} {status}{star}"
        line = head + (f"{DIM}{notes}{RESET}" if notes else "")
        return [truncate_display(line, limit)]

    if tier == "medium":
        # 两行：名称与状态上行，键名(淡色)+备注缩进下行——手机上既看得全名称，
        # 又不牺牲键名可见性（`? 键名` / `键名=on|off` 照常可用）。
        first = (
            f"{num}. {marker}{truncate_display(label, limit - display_width(f'{num}. {marker} ') - 7)}{star} {status}"
        )
        indent = " " * (display_width(num) + 2)
        second = f"{indent}{DIM}{key}{RESET}"
        if notes:
            second += f"{DIM}{notes}{RESET}"
        return [truncate_display(first, limit), *wrap_display(second, limit)]

    # narrow：单行压缩，键名不进版面（改由 `? 编号` 查看），名称按剩余列截断
    prefix = f"{num} {marker}"
    tail = f" {status}{star}"
    name_budget = limit - display_width(prefix) - display_width(tail)
    return [f"{prefix}{truncate_display(label, name_budget)}{tail}"]


def wrap_hanging(text: str, columns: int, indent: str = "    ") -> list[str]:
    """按列宽折行并给续行加悬挂缩进（面板内成段文字用，续行不顶到左边框）。"""
    wrapped = wrap_display(text, columns)
    if len(wrapped) <= 1:
        return wrapped
    return [wrapped[0], *(indent + line.lstrip() for line in wrapped[1:])]


def legend_lines(cost_days: int, columns: int, *, tier: str | None = None) -> list[str]:
    """页脚图例（按终端宽度折行；窄档只保留符号释义与命令提示）。

    Args:
        cost_days: 费用摘要回看窗口天数（与 `perf.module_cost_summary` 口径一致）。
        columns: 终端列数。
        tier: 版面档位；缺省按 `columns` 推导。

    Returns:
        图例行列表，每行不超过 `inner_width(columns)`。
    """
    tier = tier or layout_tier(columns)
    limit = inner_width(columns)
    lines: list[str] = []

    if tier == "narrow":
        # 窄终端：只留「怎么用」——符号释义与键名位置说明对 40~60 列的手机太占地方
        lines += wrap_hanging("  ⚗ 实验项（默认关） · * 与默认不同", limit)
        lines += wrap_hanging("  输入编号切换；? 编号 查看说明（含键名）", limit)
        lines += wrap_hanging("  r 编号 恢复本组默认 · ra 全部恢复 · x 实验项全关", limit)
        return lines

    lines += wrap_hanging("  ⚗ 实验项（默认关，质量可能不稳定） · * 与出厂默认不一致（配置漂移）", limit)
    key_note = (
        "  键名即行内淡色列：可直接输入键名（也可 ? 键名 / 键名=on|off）代替编号，面板增删项后仍然稳定"
        if tier == "wide"
        else "  键名在每项第二行（淡色）：可直接输入键名 / ? 键名 / 键名=on|off 代替编号"
    )
    lines += wrap_hanging(key_note, limit)
    lines += wrap_hanging(f"  行尾「N次 ¥X 均¥Y」= 近 {cost_days} 日该模块调用次数 / 累计费用 / 单次均值", limit)
    lines += wrap_hanging("  ? 编号 查看说明 · r 编号 恢复本组默认 · ra 恢复全部 · x 实验项全关 · 0 返回", limit)
    return lines


__all__ = [
    "MEDIUM_MIN_COLUMNS",
    "WIDE_MIN_COLUMNS",
    "format_heading",
    "format_item",
    "inner_width",
    "layout_tier",
    "legend_lines",
    "wrap_hanging",
    "terminal_columns",
]
