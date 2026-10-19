"""TUI 提示语模板（提示四成分的唯一定义处）。

契约见 ``docs/managements/DESIGN-TUI.md``：列表面板提示一律由本模块产出，
调用方不再手写提示串——手写即意味着语义会随作者心情漂移（裸提示、只列按键字母、
默认项不标注等都由此而来）。

四成分：
  动作(+示例) · 默认项声明 · 帮助入口 · 返回键

约定：默认项必须写明**动作名**（「回车=用缓存生成」而非「回车=确定」）；
取消类语义不得用回车表达（用 ``0`` / ``Esc``），确需时置句首显式声明。
"""

from __future__ import annotations

from src.python.tui.text_layout import terminal_columns, wrap_hanging

__all__ = ["panel_prompt", "keys_help_lines", "item_detail_lines"]


def panel_prompt(
    action: str,
    *,
    example: str | None = None,
    default: str | None = None,
    help_hint: str | None = "? 看说明",
    back: str | None = "0 返回",
    prefix: str = "  ",
) -> str:
    """列表面板提示：动作（+示例） · 默认项 · 帮助入口 · 返回键。

    Args:
        action: 动作指令（动词短语，如「输入编号切换」）。
        example: 具体示例（如「如 3」）——给出一个可照抄的输入，胜过长篇说明。
        default: 回车将执行的动作名；``None`` 表示本面板回车不派发任何项。
        help_hint: 帮助入口文案；``None`` 表示该面板不提供 ``?``。
        back: 返回键文案；``None`` 表示不提供返回项。
        prefix: 行首缩进（与面板版面一致）。

    Returns:
        以 ``": "`` 结尾的提示串（已含行首缩进，调用方仍可按需 ``wrap_prompt``）。
    """
    head = f"{prefix}{action}"
    if example:
        head += f"（如 {example}）"
    parts = [head]
    if default:
        parts.append(f"回车={default}")
    if help_hint:
        parts.append(help_hint)
    if back:
        parts.append(back)
    return " · ".join(parts) + ": "


def keys_help_lines(items, *, columns: int | None = None) -> list[str]:  # noqa: ANN001 - PanelItem 协议
    """``?`` 无参帮助：本面板可用键与作用（含导航与返回口径）。

    Args:
        items: 面板项清单（``PanelItem`` 序列，返回项单列一行）。
        columns: 折行列宽；缺省取当前终端宽度。

    Returns:
        直接可打印的行列表。
    """
    columns = columns or terminal_columns()
    lines = ["  可用键："]
    for item in items:
        if getattr(item, "kind", "action") == "return":
            continue
        lines += wrap_hanging(f"    {item.key} — {item.label}", columns, indent="      ")
    lines += wrap_hanging("    ↑ ↓ 移动选中 · 回车 执行提示行标注的默认项 · 0 / Esc 返回", columns, indent="      ")
    return lines


def item_detail_lines(item, *, hint: str | None = None, columns: int | None = None) -> list[str]:  # noqa: ANN001
    """``?N`` 单项详情：键、名称与可选说明。

    Args:
        item: 目标面板项。
        hint: 该项的补充说明（如当前值/默认值）；``None`` 时只给键与名称。
        columns: 折行列宽；缺省取当前终端宽度。

    Returns:
        直接可打印的行列表。
    """
    columns = columns or terminal_columns()
    lines = wrap_hanging(f"  {item.key}. {item.label}", columns)
    if hint:
        lines += wrap_hanging(f"  说明  : {hint}", columns, indent="          ")
    return lines
