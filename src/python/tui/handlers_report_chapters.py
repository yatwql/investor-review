#!/usr/bin/env python3
"""TUI ``[C]`` 报告章节显隐面板：四块章节 + 智囊团生成子项（数量由注册表派生）。

清单、编号、分块、来源与子项全部取自 :mod:`config.chapter_registry`（唯一来源）；
本模块只做「取值 → 渲染 → 派发」。写路径经 ``handlers_config._apply_edit``
（与 Web / CLI 同一编辑层），读路径经 ``handlers_config`` 的配置缓存与
``llm_settings`` 读取函数——函数内局部导入，保持既有 ``handlers_config.<符号>``
patch 点有效（与 ``[S]`` 面板同一手法）。

面板只切换显隐：章节集合与顺序由注册表与 ``report_section_order`` 决定，
本面板不提供增删或排序；四块来源不同（``config.json`` / ``llm_settings.json`` /
``features.json``）但对用户统一呈现为「章节」。
"""

from __future__ import annotations

from src.python.core.ansi_colors import DIM, GREEN, RESET, YELLOW
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.switch_panel import (
    inner_width,
    layout_tier,
    render_titled_panel,
    status_text,
    terminal_columns,
    wrap_hanging,
)
from src.python.tui.text_layout import (
    display_width,
    group_heading,
    pad_right,
    style_heading,
    truncate_display,
)

COST_HISTORY_DAYS = 7
"""LLM 章节行尾历史费用摘要的回看窗口天数（与 ``perf.module_cost_summary`` 同口径）。"""


def _cost_notes(key: str, cost_history: dict) -> str:
    """LLM 章节行尾费用摘要（无样本 / 读取失败均返回空串，静默省略）。"""
    from src.python.llm.pricing import currency_symbol

    info = cost_history.get(key) or {}
    runs = info.get("runs")
    if not isinstance(runs, int) or runs <= 0:
        return ""
    parts: list[str] = []
    for code in sorted(info.get("costs") or {}):
        bucket = info["costs"][code]
        symbol = currency_symbol(code)
        parts.append(f"{symbol}{float(bucket.get('total') or 0.0):.4f} 均{symbol}{float(bucket.get('avg') or 0.0):.4f}")
    if not parts:
        return ""
    return f" · {runs}次 " + " + ".join(parts)


def _format_row(
    *,
    cursor: str,
    number: str,
    label: str,
    key: str,
    status: str,
    star: str,
    notes: str,
    columns: int,
    name_column: int,
    key_column: int,
    number_width: int,
    indent: int,
    grey: bool,
) -> list[str]:
    """章节行排版：宽/中档单行；窄档两行（名称+状态 / 键名+备注），键名恒可见。"""
    tier = layout_tier(columns)
    limit = inner_width(columns) - 2
    pad = " " * indent
    suffix = "." if "." not in number else ""
    prefix = f"{f'{number:>{number_width}}{suffix}'}{pad} "
    if tier == "narrow":
        shown_label = f"{DIM}{label}{RESET}" if grey else label
        head = f"{cursor}{prefix}{shown_label} {status}{star}"
        second = f"{' ' * display_width(prefix)}{DIM}{key}{RESET}"
        if notes:
            second += f"{DIM}{notes}{RESET}"
        return [truncate_display(head, limit), truncate_display(second, limit)]
    shown_label = (
        f"{DIM}{pad_right(label, max(0, name_column - indent))}{RESET}"
        if grey
        else pad_right(label, max(0, name_column - indent))
    )
    head = f"{cursor}{prefix}{shown_label} {DIM}{pad_right(key, key_column)}{RESET} {status}{star}"
    if notes:
        head += f"{DIM}{notes}{RESET}"
    return [truncate_display(head, limit)]


def invalid_number_hint() -> str:
    """无效编号提示里的可输入范围——编号与子项都从注册表现取，不写死数字。

    章节/子项是注册表派生量：新增一章或一个生成子项后，写死的「1-16」「7.1」
    会立刻过期，把用户引到不存在的编号上。
    """
    from src.python.config.chapter_registry import chapter_numbers, sub_item_numbers

    numbers = [str(number) for number, _entry in chapter_numbers()]
    span = f"{numbers[0]}-{numbers[-1]}" if numbers else "编号"
    subs = sorted(sub_item_numbers())
    return f"可输入 {span}" + (f" 或子项 {' / '.join(subs)}" if subs else "")


def run_report_chapters_panel() -> None:
    """报告章节显隐面板主循环（编号或子项编号切换；``?编号`` / ``?键名`` 看详情）。"""
    from src.python.tui import handlers_config as hc

    from src.python.config import default_enabled_llm, get_config
    from src.python.config.chapter_registry import (
        BLOCK_LABELS,
        BLOCK_ORDER,
        SOURCE_CONFIG,
        SOURCE_FILES,
        SOURCE_LLM,
        chapter_by_key,
        chapter_default,
        chapter_edit_key,
        chapter_label,
        chapter_number,
        chapter_numbers,
        chapters_in_block,
        sub_item_numbers,
    )
    from src.python.config.features import feature_switch_registry, is_feature_enabled
    from src.python.core.experiment_stats import load_experiment_usage
    from src.python.core.registry import get_llm_module_names

    # ``llm_settings.json`` 读不到时仍让顶层章节 / 功能开关可用：LLM 块按出厂默认展示，
    # 切换时由编辑层给出具体错误（不静默回落，也不整面板罢工）。
    snapshot = hc._read_llm_settings()
    settings = snapshot[0] if snapshot else {}
    enabled_llm: dict[str, bool] = dict(settings.get("enabled_llm") or {})
    llm_defaults = default_enabled_llm()
    llm_names = hc.filter_menu_llm_modules(get_llm_module_names())

    try:
        from src.python.core.perf import module_cost_summary

        cost_history = module_cost_summary(COST_HISTORY_DAYS)
    except Exception:
        hc.logger.debug("[C] LLM 章节费用摘要读取失败，静默省略", exc_info=True)
        cost_history = {}

    def _status(entry) -> bool:  # noqa: ANN001 — ChapterEntry（运行时取值，避免导入环）
        if entry.source == SOURCE_CONFIG:
            return bool((get_config() or {}).get(entry.key, True))
        if entry.source == SOURCE_LLM:
            return bool(enabled_llm.get(entry.key, llm_defaults.get(entry.key, True)))
        return is_feature_enabled(entry.key)

    def _emit(message: str) -> None:
        for line in wrap_hanging(message, inner_width(terminal_columns())):
            print(line)

    def _toggle_chapter(entry) -> None:  # noqa: ANN001
        current = _status(entry)
        label = chapter_label(entry, llm_names)
        if hc._apply_edit({"key": chapter_edit_key(entry), "value": not current}):
            if entry.source == SOURCE_LLM:
                enabled_llm[entry.key] = not current
            _emit(f"  {GREEN}[OK]{RESET} {label}已{'启用' if not current else '禁用'}")
            hc.refresh_config()

    def _toggle_sub(flag: str, parent) -> None:  # noqa: ANN001
        definition = feature_switch_registry.get(flag)
        label = definition.label if definition is not None else flag
        if not _status(parent):
            _emit(
                f"  {YELLOW}[!]{RESET} 先启用第 {chapter_number(parent.key)} 项"
                f"（{chapter_label(parent, llm_names)}）后可切换{label}"
            )
            return
        current = is_feature_enabled(flag)
        if hc._apply_edit({"key": flag, "value": not current}):
            _emit(f"  {GREEN}[OK]{RESET} {label}已{'启用' if not current else '禁用'}")
            hc.refresh_config()

    # 面板项序 = 渲染行序（章节后紧跟其子项），方向键游标按同一序推进
    panel_items: list[PanelItem] = []
    for number, entry in chapter_numbers():
        panel_items.append(
            PanelItem(
                str(number),
                chapter_label(entry, llm_names),
                action=lambda e=entry: _toggle_chapter(e),
                detail=_chapter_detail(entry, llm_names),
            )
        )
        for offset, flag in enumerate(entry.sub_items, 1):
            definition = feature_switch_registry.get(flag)
            panel_items.append(
                PanelItem(
                    f"{number}.{offset}",
                    definition.label if definition is not None else flag,
                    action=lambda f=flag, p=entry: _toggle_sub(f, p),
                    detail=f"智囊团深度复盘生成选项 · {SOURCE_FILES['features']} → {flag}",
                )
            )
    panel_items.append(PanelItem("0", "返回主菜单", kind="return"))

    def _on_text(token: str) -> None:
        _emit(f"  {YELLOW}[!]{RESET} 无效编号「{token}」（{invalid_number_hint()}，? 看说明）")

    def _help(target: str) -> bool:
        """``?编号`` / ``?7.1`` / ``?键名`` 富详情（只读，不写配置）。"""
        raw = target.strip()
        if not raw:
            return False
        flag = ""
        chapter = None
        if raw in sub_item_numbers():
            flag = sub_item_numbers()[raw]
            chapter = chapter_by_key(flag)
        elif raw.isdigit():
            chapter = next((e for n, e in chapter_numbers() if str(n) == raw), None)
        else:
            chapter = chapter_by_key(raw)
            if chapter is not None and raw in chapter.sub_items:
                flag = raw
        if chapter is None:
            return False
        return _print_detail(chapter, flag, llm_names, cost_history)

    def _render(nav: NavState) -> list[str]:
        columns = terminal_columns()
        tier = layout_tier(columns)
        numbered = dict(chapter_numbers())
        sub_flags = [f for e in numbered.values() for f in e.sub_items]
        labels = {e.key: chapter_label(e, llm_names) for e in numbered.values()}
        name_column = max(
            [
                *(display_width(v) for v in labels.values()),
                *(display_width(feature_switch_registry[f].label) for f in sub_flags),
            ]
        )
        key_column = max([*(display_width(e.key) for e in numbered.values()), *(display_width(f) for f in sub_flags)])
        number_width = len(str(len(numbered)))
        experimental_subs = {
            f for f in sub_flags if f in feature_switch_registry and feature_switch_registry[f].experimental
        }
        exp_stats = load_experiment_usage() if experimental_subs else {}

        rows: list[str] = []
        index = 0
        for block in BLOCK_ORDER:
            entries = chapters_in_block(block)
            if not entries:
                continue
            enabled_count = sum(1 for e in entries if _status(e))
            heading = f"── {BLOCK_LABELS[block]}（{enabled_count}/{len(entries)} 开）"
            rows.extend(group_heading(heading, inner_width(columns), prefix=""))
            for entry in entries:
                number = chapter_number(entry.key)
                enabled = _status(entry)
                notes = f"（{entry.artifact_note}）" if entry.artifact_note else ""
                if entry.source == SOURCE_LLM:
                    notes += _cost_notes(entry.key, cost_history)
                rows.extend(
                    _format_row(
                        cursor=nav.marker(index),
                        number=str(number),
                        label=labels[entry.key],
                        key=entry.key,
                        status=status_text(enabled, tier),
                        star="" if enabled == chapter_default(entry) else "*",
                        notes=notes,
                        columns=columns,
                        name_column=name_column,
                        key_column=key_column,
                        number_width=number_width,
                        indent=0,
                        grey=False,
                    )
                )
                index += 1
                for offset, flag in enumerate(entry.sub_items, 1):
                    definition = feature_switch_registry.get(flag)
                    label = definition.label if definition is not None else flag
                    sub_enabled = is_feature_enabled(flag)
                    sub_notes = ""
                    if flag in experimental_subs:
                        usage = exp_stats.get(flag) or {}
                        if isinstance(usage.get("enabled_count"), int):
                            date = str(usage.get("last_enabled_date") or "")[5:]
                            sub_notes = (
                                f"（启用 {usage['enabled_count']} 次" + (f" · 最近 {date}" if date else "") + "）"
                            )
                    if not enabled:
                        sub_notes += "（启用本章节后可切换）"
                    rows.extend(
                        _format_row(
                            cursor=nav.marker(index),
                            number=f"{number}.{offset}",
                            label=label,
                            key=flag,
                            status=status_text(enabled and sub_enabled, tier),
                            star="" if definition is None or (enabled and sub_enabled) == definition.default else "*",
                            notes=sub_notes,
                            columns=columns,
                            name_column=name_column,
                            key_column=key_column,
                            number_width=number_width,
                            indent=2,
                            grey=not enabled,
                        )
                    )
                    index += 1
            rows.append("")
        rows.append(f"{nav.marker(index)}0. 返回主菜单")
        return [
            None,
            *render_titled_panel("报告章节显隐", rows, columns=columns),
            *wrap_hanging(
                "  提示：本章只切换显隐、不增删章节也不改顺序；关闭即整章不出现（关联产物仅影响对应报告页签）",
                inner_width(columns),
            ),
            *wrap_hanging(
                "  稳定入口是键名：?编号 / ?键名 查看说明（如 ?7 / ?7.1 / ?expert_review）",
                inner_width(columns),
            ),
            None,
        ]

    try:
        panel_loop(
            panel_items,
            render=_render,
            prompt=panel_prompt("输入章节编号切换", example="7 或 7.1", help_hint="?7 查看说明"),
            read=hc.input_choice,
            on_text=_on_text,
            on_help=_help,
        )
    except (EOFError, KeyboardInterrupt):
        print()

    hc.refresh_config()


def _chapter_detail(entry, llm_names) -> str:  # noqa: ANN001
    """面板单项详情：来源文件 + 写键 + 出厂默认 + 影响面（``?编号`` 用）。"""
    from src.python.config.chapter_registry import (
        SOURCE_FILES,
        chapter_default,
        chapter_edit_key,
        chapter_label,
    )

    impact = "仅影响调仓模拟报告的页签" if entry.artifact_note else "关闭后整章不出现"
    return (
        f"{chapter_label(entry, llm_names)} · {SOURCE_FILES[entry.source]} → {chapter_edit_key(entry)}"
        f" · 出厂默认{'开启' if chapter_default(entry) else '关闭'} · {impact}"
    )


def _print_detail(chapter, flag: str, llm_names, cost_history) -> bool:  # noqa: ANN001
    """打印章节 / 子项详情（只读）；未知目标返回 False 交运行时通用帮助。"""
    from src.python.config.chapter_registry import (
        SOURCE_FILES,
        chapter_default,
        chapter_edit_key,
        chapter_label,
        chapter_numbers,
    )
    from src.python.config.features import feature_switch_registry

    columns = terminal_columns()
    width = inner_width(columns) - 2
    print()
    if flag:
        definition = feature_switch_registry.get(flag)
        name = definition.label if definition is not None else flag
        desc = definition.desc if definition is not None else ""
        print(style_heading(truncate_display(f"  ── {name}（{flag}）", width)))
        for line in wrap_hanging(f"  说明  : {desc}", width, indent="          "):
            print(line)
        for line in wrap_hanging(f"  存储  : {SOURCE_FILES['features']} → {flag}", width, indent="          "):
            print(line)
        for line in wrap_hanging("  归属  : 智囊团深度复盘的生成选项（不新增章节）", width, indent="          "):
            print(line)
        return True
    name = chapter_label(chapter, llm_names)
    number = next((n for n, e in chapter_numbers() if e.key == chapter.key), 0)
    print(style_heading(truncate_display(f"  ── {name}（{chapter.key}）", width)))
    impact = "仅影响调仓模拟报告的页签" if chapter.artifact_note else "关闭后整章不出现"
    for line in (
        f"  编号  : {number}",
        f"  存储  : {SOURCE_FILES[chapter.source]} → {chapter_edit_key(chapter)}",
        f"  出厂默认: {'开启' if chapter_default(chapter) else '关闭'}",
        f"  影响面  : {impact}",
    ):
        for wrapped in wrap_hanging(line, width, indent="          "):
            print(wrapped)
    if chapter.sub_items:
        subs = " / ".join(f"{number}.{offset}" for offset, _flag in enumerate(chapter.sub_items, 1))
        for line in wrap_hanging(f"  子项  : {subs}（本章节关闭时不可切换）", width, indent="          "):
            print(line)
    cost = _cost_notes(chapter.key, cost_history)
    if cost:
        print(f"  费用  : 近 {COST_HISTORY_DAYS} 日{cost[3:]}")
    return True
