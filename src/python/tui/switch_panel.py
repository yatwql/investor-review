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

设计约定（同一份代码同时服务手机 SSH 与笔记本终端，故按「宽 → 窄」逐级让位）：

1. **先让装饰、再让信息**：窄档（< 64 列）不画盒线（省 6 列与每块的分隔线，直接换
   来可用宽度），组间用空白行分隔；宽/中档保留盒线做视觉分区。
2. **纵向稀缺优先**：中档逐行判断「单行放得下就单行」——同一面板里短条目仍是一行，
   只有超宽条目才换第二行，避免手机上把 34 项摊成 70 行。
3. **键名可见性分级**：宽档行内淡色列；中档优先行内、放不下才移到次行；窄档不进版面，
   由页脚明确指路 `? 编号`（**绝不静默隐藏**，否则用户又要猜）。
4. **宽度探测取实时值**：`os.get_terminal_size()` 优先（resize 后立即生效），不可用时
   退回 `COLUMNS`，最后兜底值——避免手机端设了窄宽却被判成宽屏。
"""

from __future__ import annotations


from src.python.core.ansi_colors import DIM, GREEN, RED, RESET
from src.python.tui.text_layout import (
    display_width,
    pad_right,
    style_heading,
    terminal_columns,
    truncate_display,
    wrap_display,
    wrap_hanging,
)

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


def narrow_rule(columns: int | None = None) -> str:
    """窄档分隔线：宽度随内宽自适应（不硬折成两截）。

    长输出面板（日志/健康历史/缓存统计）在窄屏上共用同一分隔线口径，
    避免各处手写 ``"=" * 40`` 在 40 列终端上正好溢出。
    """
    cols = columns or terminal_columns()
    return "  " + "=" * max(10, min(40, inner_width(cols) - 2))


def render_titled_panel(title: str, rows, *, columns: int | None = None) -> list[str]:  # noqa: ANN001
    """按档位渲染「标题 + 行」面板：宽/中档画盒线，窄档退化为无边框 + 行内截断。

    为什么需要：``text_layout.render_panel`` 的宽度是**内容驱动**的（下限 41 列内容 +
    边框），它不看终端宽度——直接在窄终端画盒线会撑出 49~57 列，被终端硬折成锯齿，
    违背「窄档不画盒线、先让装饰再让信息」的既有约定（见模块 docstring 约定 1）。

    Args:
        title: 面板标题（窄档渲染为 ``── 标题 ──`` 结构标题行）。
        rows: 内容行；``None`` 表示盒线版式下的内区分隔线，窄档渲染为空行。
        columns: 终端列数；``None`` 取实时值。

    Returns:
        待逐行打印的文本（已按档位决定盒线/截断；每行显示宽度 ≤ ``inner_width(columns)``）。
    """
    from src.python.tui.text_layout import render_panel

    cols = columns or terminal_columns()
    body = list(rows)
    if use_panel_box(cols):
        return render_panel(title, body)
    width = inner_width(cols)
    lines = [style_heading(truncate_display(f"  ── {title} ──", width))]
    for row in body:
        lines.append("" if row is None else truncate_display(f"  {row}", width))
    return lines


def use_panel_box(columns: int) -> bool:
    """是否画盒线面板（窄终端不画：把边框与分隔线的列宽/行数让给内容）。"""
    return layout_tier(columns) != "narrow"


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
    """状态文本：宽/中档用「开启/关闭」，窄档用「开/关」；**开启绿 / 关闭红**。

    着色在方括号内（`[` + 颜色 + 标签 + `RESET` + `]`），非 TTY 或 `NO_COLOR`
    下颜色常量为空串，宽度计算不受影响（`display_width` 会剥离 ANSI 序列）。
    关闭项必须一眼可辨——面板里 34 项逐行扫读时，靠颜色而非靠读字判断状态。
    """
    label = _STATUS_SHORT[enabled] if tier == "narrow" else _STATUS_LONG[enabled]
    color = GREEN if enabled else RED
    return f"[{color}{label}{RESET}]" if color else f"[{label}]"


def format_heading(head: str, enabled_count: int, total: int, columns: int) -> str:
    """分组标题行（含该组开启数；窄终端先截断再上色——截断不吃转义序列）。"""
    text = truncate_display(f"{head}（{enabled_count}/{total} 开）", inner_width(columns))
    return style_heading(text)


def format_item(
    *,
    number: int,
    label: str,
    key: str,
    enabled: bool,
    star: str,
    marker: str,
    cursor: str = "",
    notes: str,
    columns: int,
    name_column: int,
    key_column: int,
    number_width: int = 1,
    reveal_key: bool = False,
) -> list[str]:
    """把一个开关/模块条目排版成 1~2 行（随终端宽度自适应）。

    Args:
        number: 面板编号（用户可直接输入的整数）。
        label: 中文显示名。
        key: 配置键名（`features.json` 键 / `enabled_llm` 子键）。
        enabled: 当前是否开启。
        star: 与出厂默认不一致的标记（`"*"` 或 `""`）。
        marker: 实验项标记（`⚗` + 占位空格，已按显示列补齐）。
        cursor: 方向键游标标记（``nav.marker(i)``，即 ``▸`` 或空格占位）——拼在首行
            编号前、截断前生效，保证「每行 ≤ 面板内宽」不变式；续行（medium 键名行）
            不带游标。
        notes: 备注（互指提示 / 费用摘要 / 启用统计），已拼好的纯文本。
        columns: 终端列数。
        name_column: 名称列宽（宽/中档对齐用，取面板内最长名称）。
        key_column: 键名列宽（同上）。
        number_width: 编号列宽（按最大编号位数右对齐，使 1 与 10 起各列同位）。
        reveal_key: 窄档是否显示键名——手机屏幕窄、键名放不进单行，故**默认不显示**
            （用编号即可操作）；按 `k` 时才追加缩进的键名行，供需要时抄写/粘贴。

    Returns:
        1 行（wide/narrow）或 2 行（medium）文本，均不超过 `inner_width(columns)`。
    """
    tier = layout_tier(columns)
    limit = inner_width(columns)
    status = _status(enabled, tier)

    num = f"{number:>{number_width}}"

    if tier == "wide":
        head = f"{cursor}{num}. {marker}{pad_right(label, name_column)} {DIM}{pad_right(key, key_column)}{RESET} {status}{star}"
        line = head + (f"{DIM}{notes}{RESET}" if notes else "")
        return [truncate_display(line, limit)]

    if tier == "medium":
        # 逐行判断：单行放得下就单行（纵向稀缺优先，短条目不必占两行）；放不下才换行
        # ——名称+状态一行，键名(淡色)+备注缩进一行，键名可见性不牺牲。
        single = f"{cursor}{num}. {marker}{label} {DIM}{key}{RESET} {status}{star}"
        if display_width(single) + display_width(notes) <= limit:
            return [single + (f"{DIM}{notes}{RESET}" if notes else "")]
        first = f"{cursor}{num}. {marker}{truncate_display(label, limit - display_width(f'{num}. {marker} ') - 8)}{star} {status}"
        indent = " " * (display_width(num) + 2)
        second = f"{indent}{DIM}{key}{RESET}"
        if notes:
            second += f"{DIM}{notes}{RESET}"
        return [truncate_display(first, limit), *wrap_display(second, limit)]

    # narrow：单行压缩（键名默认不进版面——手机窄屏放不下，且编号足够操作）；
    # 用户按 `k` 时输出两行：名称+状态 / 缩进键名，供抄写粘贴。
    prefix = f"{cursor}{num} {marker}"
    tail = f" {status}{star}"
    if reveal_key:
        indent = " " * (display_width(num) + 1)
        second = f"{indent}{DIM}{key}{RESET}" + (f"{DIM}{notes}{RESET}" if notes else "")
        return [truncate_display(f"{prefix}{label}{tail}", limit), *wrap_display(second, limit)]
    name_budget = limit - display_width(prefix) - display_width(tail)
    return [f"{prefix}{truncate_display(label, name_budget)}{tail}"]


def legend_lines(cost_days: int, columns: int, *, tier: str | None = None, reveal_key: bool = False) -> list[str]:
    """页脚图例（按终端宽度折行；窄档只保留符号释义与命令提示）。

    Args:
        cost_days: 费用摘要回看窗口天数（与 `perf.module_cost_summary` 口径一致）；
            ``0`` 表示本面板无模块费用行（如 ``[S]``），省略该条图例。
        columns: 终端列数。
        tier: 版面档位；缺省按 `columns` 推导。
        reveal_key: 窄档当前是否已显示键名（决定提示写「k 显示键名」还是「k 隐藏键名」）。

    Returns:
        图例行列表，每行不超过 `inner_width(columns)`。
    """
    tier = tier or layout_tier(columns)
    limit = inner_width(columns)
    lines: list[str] = []

    if tier == "narrow":
        # 窄终端：只留「怎么用」——符号释义与键名位置说明对 40~60 列的手机太占地方
        lines += wrap_hanging("  ⚗ 实验项（默认关） · * 与默认不同", limit)
        # 主路径（编号切换 / ?3 说明 / 0 返回）已在输入提示里教，这里只列高级命令
        lines += wrap_hanging(
            "  r 编号 恢复本组默认 · ra 全部恢复 · x 实验项全关 · " + ("k 隐藏键名" if reveal_key else "k 显示键名"),
            limit,
        )
        return lines

    lines += wrap_hanging("  ⚗ 实验项（默认关，质量可能不稳定） · * 与出厂默认不一致", limit)
    key_note = (
        "  键名即行内淡色列：可直接输入键名（也可 ? 键名 / 键名=on|off）代替编号，面板增删项后仍然稳定"
        if tier == "wide"
        else "  键名在每项第二行（淡色）：可直接输入键名 / ? 键名 / 键名=on|off 代替编号"
    )
    lines += wrap_hanging(key_note, limit)
    if cost_days > 0:
        lines += wrap_hanging(f"  行尾「N次 ¥X 均¥Y」= 近 {cost_days} 日该模块调用次数 / 累计费用 / 单次均值", limit)
    lines += wrap_hanging("  ?编号 查看说明 · r 编号 恢复本组默认 · ra 恢复全部 · x 实验项全关 · 0 返回", limit)
    return lines


__all__ = [
    "MEDIUM_MIN_COLUMNS",
    "WIDE_MIN_COLUMNS",
    "format_heading",
    "format_item",
    "inner_width",
    "layout_tier",
    "legend_lines",
    "narrow_rule",
    "render_titled_panel",
    "use_panel_box",
    "wrap_hanging",
    "terminal_columns",
]
