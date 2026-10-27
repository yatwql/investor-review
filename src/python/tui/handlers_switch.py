#!/usr/bin/env python3
"""TUI ``[S]`` 报告章节内容呈现面板：18 项五组（组序与编号取自功能开关注册表）。

``[S]`` 只呈现 ``PANEL_GROUPS["[S]"]`` 的五组内容开关（持仓与交易 / 市场与估值 /
基金与风格 / 事件与摘要 / 机制与质量）；LLM 章节、默认关闭的整章与
关联产物在 ``[C]``，本面板不再混排。编号由 :func:`config.features.panel_option_numbers`
派生——增删开关后自动重排，渠道层不写死数字。

写盘、读数、提示输入统一经 ``handlers_config`` **函数内局部导入**
（``_apply_edit`` / ``refresh_config`` / ``input_choice``）——既保证写路径与错误呈现
单源，也让既有 ``handlers_config.<符号>`` 的测试 patch 点继续有效。

只读信息面：``? 编号`` 查看说明与当前值/默认值；行尾 ``*`` 标记与出厂默认值不一致
项（配置漂移）；⚗ 实验项行尾附 ``experiment_stats`` 启用统计（读取失败静默省略）。
写路径三通道：批量（``r 编号`` / ``ra`` / ``x``）、键名直切、``键名=on|off`` 赋值。
"""

from __future__ import annotations

from collections.abc import Callable

from src.python.core.ansi_colors import GREEN, RESET, YELLOW
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.switch_panel import (
    format_heading,
    format_item,
    inner_width,
    layout_tier,
    legend_lines,
    terminal_columns,
    use_panel_box,
    wrap_hanging,
)
from src.python.tui.text_layout import display_width, pad_right, render_panel, style_heading, truncate_display

EXPERIMENT_MARK_COLUMNS = 2
"""行首实验项标记 ⚗ 的占位列宽（非实验项留同宽空白以对齐状态列）。"""


def match_switch_item(token: str, items: list[tuple[int, str, str, bool]]) -> tuple[int, str, str, bool] | None:
    """按编号（纯数字）或条目键名在面板条目中定位一项。

    Args:
        token: 用户输入的目标（编号或键名，允许首尾空白）。
        items: 面板当前派发的条目 ``(编号, 键, 显示名, 当前状态)``。

    Returns:
        匹配的条目；无匹配返回 None（调用方给出行内提示）。
    """
    token = token.strip()
    if token.isdigit():
        return next((it for it in items if it[0] == int(token)), None)
    return next((it for it in items if it[1] == token), None)


def show_switch_detail(choice: str, items: list[tuple[int, str, str, bool]]) -> None:
    """``? 编号或键名`` 上屏面板单项说明与当前值/默认值（只读信息查询，不写配置）。

    Args:
        choice: 用户输入（``?`` 后跟编号或条目键名，如 ``? 3`` / ``? report_qa``）。
        items: 面板当前派发的条目 ``(编号, 键, 显示名, 当前状态)``。
    """
    from src.python.config.features import GROUP_LABELS, feature_switch_registry
    from src.python.core.experiment_stats import load_experiment_usage

    raw = choice.lstrip("?？").strip()  # 半角/全角问号均可作前缀
    matched = [it for it in items if (it[0] == int(raw) if raw.isdigit() else it[1] == raw)]
    if not matched:
        if raw.isdigit():
            print(f"  {YELLOW}[!]{RESET} 无效编号")
        else:
            print(f"  {YELLOW}[!]{RESET} 请输入 ? 加编号或键名（如 ?3 或 ? report_qa）")
        return
    _, key, name, curr = matched[0]
    definition = feature_switch_registry[key]
    default = definition.default
    group_label = GROUP_LABELS.get(definition.group, definition.group)
    life = ""
    if definition.experimental:
        entry = load_experiment_usage().get(key) or {}
        life = " · 实验项"
        if isinstance(entry.get("enabled_count"), int):
            date = str(entry.get("last_enabled_date") or "")[5:]
            life += f" · 启用 {entry['enabled_count']} 次" + (f" · 最近 {date}" if date else "")
    # 详情按终端宽度折行：手机窄终端的说明段（`desc` 常含整句）与存储路径都能读全
    width = inner_width(terminal_columns()) - 2
    print()
    print(style_heading(truncate_display(f"  ── {name}（{key}）", width)))
    for line in wrap_hanging(f"  说明  : {definition.desc}", width, indent="          "):
        print(line)
    for line in wrap_hanging(f"  分组  : {group_label}{life}", width, indent="          "):
        print(line)
    for line in wrap_hanging(f"  存储  : features.json → {key}", width, indent="          "):
        print(line)
    detail = f"  当前  : {'开启' if curr else '关闭'}   出厂默认: {'开启' if default else '关闭'}"
    if curr != default:
        detail += "（不一致，行尾标 *）"
    for line in wrap_hanging(detail, width, indent="          "):
        print(line)


def run_content_options_panel() -> None:
    """配置报告章节内的内容与呈现（五组功能开关，编号由注册表派生）。

    分组标题、显示名与顺序均取自 ``features.PANEL_GROUPS`` / ``GROUP_LABELS``，
    新增开关自动上屏，渠道层不另写清单。
    """
    from src.python.tui import handlers_config as hc

    from src.python.config.features import (
        GROUP_LABELS,
        PANEL_GROUPS,
        clear_feature_overrides,
        experimental_flags,
        feature_switch_registry,
        is_feature_enabled,
        panel_option_numbers,
        parse_switch_override,
        switches_in_group,
    )
    from src.python.core.experiment_stats import load_experiment_usage

    panel = "[S]"
    numbered = panel_option_numbers(panel)
    groups = PANEL_GROUPS[panel]
    blocks: dict[str, list[tuple[int, str, object]]] = {group: [] for group in groups}
    for num, flag, definition in numbered:
        blocks[definition.group].append((num, flag, definition))

    # 行首 ⚗ 标记仅给实验项（experimental 字段，与所属组无关）
    experiment_keys = {flag for flag, _d in experimental_flags()}
    # 名称列宽 / 键名列宽：取本面板清单内最长值，使各行状态列与键名列纵向对齐
    name_column = max(display_width(definition.label) for _n, _f, definition in numbered)
    key_column = max(display_width(flag) for _n, flag, _d in numbered)
    number_width = len(str(len(numbered)))

    state = {"repaint": True, "reveal_keys": False, "tuples": []}

    def _emit(message: str) -> None:
        """按当前内宽输出一行提示（窄屏上 `[!]`/`[OK]` 长句也不越界折行）。"""
        for line in wrap_hanging(message, inner_width(terminal_columns())):
            print(line)

    def _apply_toggle(num: int, key: str, name: str, new_val: bool) -> None:
        """写路径单源：应用开/关切换 + 反馈 + 置重绘 + 刷新缓存（各通道汇合）。"""
        if hc._apply_edit({"key": key, "value": new_val}):
            _emit(f"  {GREEN}[OK]{RESET} {num} {name} 已{'开启' if new_val else '关闭'}")
            state["repaint"] = True
            hc.refresh_config()

    def _make_toggle(num: int, key: str, name: str) -> Callable[[], None]:
        """回车派发项：**调用时**读取当前状态再取反（面板构造期的值会过期）。"""
        return lambda: _apply_toggle(num, key, name, not is_feature_enabled(key))

    def _render(nav: NavState) -> list[str]:
        rows: list[str | None] = []
        tuples: list[tuple[int, str, str, bool]] = []
        exp_stats = load_experiment_usage()
        columns = terminal_columns()
        narrow = layout_tier(columns) == "narrow"
        for group in groups:
            block = blocks[group]
            rows.append(None if use_panel_box(columns) else "")
            rows.extend(
                format_heading(
                    GROUP_LABELS[group].split("（", 1)[0],
                    sum(1 for _n, flag, _d in block if is_feature_enabled(flag)),
                    len(block),
                    columns,
                )
            )
            for num, flag, definition in block:
                status = is_feature_enabled(flag)
                marker = pad_right("⚗" if flag in experiment_keys else "", EXPERIMENT_MARK_COLUMNS)
                notes = ""
                if flag in experiment_keys:
                    entry = exp_stats.get(flag) or {}
                    if isinstance(entry.get("enabled_count"), int):
                        date = str(entry.get("last_enabled_date") or "")[5:]
                        notes += f"（启用 {entry['enabled_count']} 次" + (f" · 最近 {date}" if date else "") + "）"
                tuples.append((num, flag, definition.label, status))
                rows.extend(
                    format_item(
                        number=num,
                        label=definition.label,
                        key=flag,
                        enabled=status,
                        star="" if status == definition.default else "*",
                        marker=marker,
                        cursor=nav.marker(len(tuples) - 1),
                        notes=notes,
                        columns=columns,
                        name_column=name_column,
                        key_column=key_column,
                        number_width=number_width,
                        reveal_key=state["reveal_keys"],
                    )
                )
        rows.append("")
        rows.append(f"{nav.marker(len(tuples))}0. 返回主菜单")
        state["tuples"] = tuples
        print()
        panel_rows = [
            *rows,
            None if use_panel_box(columns) else "",
            *legend_lines(0, columns, reveal_key=state["reveal_keys"]),
        ]
        if not state["repaint"]:
            # 窄终端（手机）：只读查询（? 说明）与失败路径不整屏重绘——详情/报错留屏
            # 不被面板顶走；写路径成功后 repaint=True 即时重绘（结果必须立刻可见）
            print("  （输入 p 重绘面板）")
            print()
        elif use_panel_box(columns):
            print("\n".join(render_panel("配置报告章节内容呈现", panel_rows)))
        else:
            header = truncate_display(f"章节内容（{len(tuples)} 项）", inner_width(columns) - 5)
            print(style_heading(f"  ── {header} ──"))
            print("\n".join(f"  {row}" if row else "" for row in panel_rows))
        if state["repaint"]:
            for _line in wrap_hanging(
                "  章节显隐（顶层 / LLM / 整章 / 关联产物）在菜单 [C] 配置", inner_width(columns)
            ):
                print(_line)
            print()
        # 本轮已渲染 → 窄终端下一轮只回反馈行（省纵向空间）；宽/中档照常整屏重绘
        state["repaint"] = not narrow
        return []

    def _on_help(target: str) -> bool:
        """``?键`` 详情（丰富多段输出）；``?`` 无参交运行时印可用键一览。"""
        if not target:
            return False
        show_switch_detail(target, state["tuples"])
        return True

    def _on_text(choice: str) -> None:
        tuples = state["tuples"]
        if choice.lower() == "p":
            state["repaint"] = True
            return
        if choice.lower() == "k":
            if layout_tier(terminal_columns()) == "narrow":
                state["reveal_keys"] = not state["reveal_keys"]
                state["repaint"] = True  # 版面行数变化，需要重绘才能生效
            else:
                _emit("  [!] 当前终端宽度已直接显示键名列，无需 k 切换")
            return

        # ── 写路径三通道：批量命令 / 赋值（CLI 同词表）/ 编号或键名直取 ──
        raw = choice.strip()
        lowered = raw.lower()
        if lowered == "ra":
            removed = clear_feature_overrides(None)
            _emit(f"  {GREEN}[OK]{RESET} 已恢复功能开关全部默认（移除 {removed} 项覆写）")
            state["repaint"] = True
            return
        if lowered == "x":
            exp_keys = sorted(flag for flag, _d in experimental_flags())
            clear_feature_overrides(exp_keys)
            _emit(f"  {GREEN}[OK]{RESET} 实验项已全部关闭（回到无实验态）：{'、'.join(exp_keys)}")
            state["repaint"] = True
            return
        head, space, rest = raw.partition(" ")
        if head.lower() == "r" and space and rest.strip():
            target = match_switch_item(rest, tuples)
            if target is None:
                _emit(f"  {YELLOW}[!]{RESET} 未识别目标「{rest.strip()}」（输入编号或键名）")
            else:
                group = feature_switch_registry[target[1]].group
                group_flags = [flag for flag, _d in switches_in_group(group)]
                removed = clear_feature_overrides(group_flags)
                _emit(f"  {GREEN}[OK]{RESET} 已恢复「{GROUP_LABELS[group]}」默认（移除 {removed} 项覆写）")
                state["repaint"] = True
            return

        assign_name, eq, _assign_val = raw.partition("=")
        assign_name = assign_name.strip()
        if eq:
            item = next((it for it in tuples if it[1] == assign_name), None)
            if item is None:
                try:
                    parse_switch_override(raw)
                except ValueError as e:
                    _emit(f"  {YELLOW}[!]{RESET} {e}")
                else:
                    _emit(f"  {YELLOW}[!]{RESET} 未知条目「{assign_name}」")
                return
            try:
                _parsed_flag, new_val = parse_switch_override(raw)
            except ValueError as e:
                _emit(f"  {YELLOW}[!]{RESET} {e}")
                return
            _apply_toggle(item[0], item[1], item[2], new_val)
            return

        target = match_switch_item(raw, tuples)
        if target is None:
            if raw.isdigit():
                _emit(f"  {YELLOW}[!]{RESET} 无效编号")
            else:
                _emit(f"  {YELLOW}[!]{RESET} 未知编号或键名「{raw}」（可输入编号、键名 或 键名=on|off）")
            return
        _apply_toggle(target[0], target[1], target[2], not target[3])

    # 可派发项清单：编号与面板派生同源（连续 1..N）
    panel_items = [
        PanelItem(str(num), definition.label, action=_make_toggle(num, flag, definition.label))
        for num, flag, definition in numbered
    ]
    panel_items.append(PanelItem("0", "返回主菜单", kind="return"))

    try:
        # 提示只教主路径：一个具体例子 + 说明查询 + 返回。r/ra/x/k 等高级命令放页脚图例
        panel_loop(
            panel_items,
            render=_render,
            prompt=panel_prompt("输入编号切换开关", example="3", help_hint="?3 查看说明"),
            read=hc.input_choice,
            repaint="feedback",
            on_text=_on_text,
            on_help=_on_help,
            on_nav_moved=lambda: state.update(repaint=True),
        )
    except (EOFError, KeyboardInterrupt):
        print()
