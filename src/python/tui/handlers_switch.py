#!/usr/bin/env python3
"""TUI `[S]` 功能开关面板本体：主循环 + 匹配与详情查询辅助。

``[S]`` 面板的渲染/派发/重绘/帮助全在此模块（``run_llm_modules_panel``）；``handlers_config``
只保留菜单入口薄包装。写盘、读数、提示输入统一经 ``handlers_config`` **函数内局部导入**
（``_apply_edit`` / ``_read_llm_settings`` / ``filter_menu_llm_modules`` / ``refresh_config`` /
``input_choice``）——既保证写路径与错误呈现单源，也让既有 ``handlers_config.<符号>`` 的
测试 patch 点继续有效。

``show_switch_detail`` 内部按需 import 配置/实验统计（``? 编号/键名`` 查询会取数），
故不并入「只排版不取数」的 ``switch_panel``。
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

DUAL_ENTRY_CROSS_HINTS = {
    "holding_change": "· 见独立组",
    "holding_change_review": "· 见 LLM 区",
}

EXPERIMENT_MARK_COLUMNS = 2
"""行首实验项标记 ⚗ 的占位列宽（非实验项留同宽空白以对齐状态列）。"""

COST_HISTORY_DAYS = 7
"""LLM 模块行尾历史费用摘要的回看窗口天数（数据源 perf 历史 llm.modules 费用）。"""


def match_switch_item(
    token: str, items: list[tuple[int, str, str, bool, str]]
) -> tuple[int, str, str, bool, str] | None:
    """按编号（纯数字）或条目键名（LLM 模块/功能开关键）在面板条目中定位一项。

    Args:
        token: 用户输入的目标（编号或键名，允许首尾空白）。
        items: 面板当前派发的条目 ``(编号, 键, 显示名, 当前状态, 类别)``。

    Returns:
        匹配的条目；无匹配返回 None（调用方给出行内提示）。
    """
    token = token.strip()
    if token.isdigit():
        return next((it for it in items if it[0] == int(token)), None)
    return next((it for it in items if it[1] == token), None)


def show_switch_detail(choice: str, items: list[tuple[int, str, str, bool, str]]) -> None:
    """``? 编号或键名`` 上屏面板单项说明与当前值/默认值（只读信息查询，不写配置）。

    Args:
        choice: 用户输入（``?`` 后跟编号或条目键名，如 ``? 3`` / ``? doctor_check``）。
        items: 面板当前派发的条目 ``(编号, 键, 显示名, 当前状态, 类别)``。
    """
    from src.python.config import default_enabled_llm
    from src.python.config.features import GROUP_LABELS, feature_switch_registry
    from src.python.core.experiment_stats import load_experiment_usage

    raw = choice.lstrip("?？").strip()  # 半角/全角问号均可作前缀
    matched: list[tuple[int, str, str, bool, str]] = []
    if raw.isdigit():
        matched = [it for it in items if it[0] == int(raw)]
        if not matched:
            print(f"  {YELLOW}[!]{RESET} 无效编号")
            return
    else:
        matched = [it for it in items if it[1] == raw]
        if not matched:
            print(f"  {YELLOW}[!]{RESET} 请输入 ? 加编号或键名（如 ?3 或 ? news_correlation）")
            return
    _, key, name, curr, kind = matched[0]
    if kind == "llm":
        default = default_enabled_llm().get(key, True)
        desc = "标准 LLM 分析章节（模块配置说明见 how-to-config 手册「LLM 分析章节」）"
        group_label = "LLM 分析章节"
        storage = f"llm_settings.json → enabled_llm.{key}"
        life = ""
    else:
        d = feature_switch_registry[key]
        default = d.default
        desc = d.desc
        group_label = GROUP_LABELS.get(d.group, d.group)
        storage = f"features.json → {key}"
        life = ""
        if d.experimental:
            entry = load_experiment_usage().get(key) or {}
            life = " · 实验项"
            if isinstance(entry.get("enabled_count"), int):
                date = str(entry.get("last_enabled_date") or "")[5:]
                life += f" · 启用 {entry['enabled_count']} 次" + (f" · 最近 {date}" if date else "")
    # 详情按终端宽度折行：手机窄终端的说明段（`desc` 常含整句）与存储路径都能读全，
    # 且任何一行都不越界（否则窄屏右侧被硬折成锯齿）
    width = inner_width(terminal_columns()) - 2
    print()
    print(style_heading(truncate_display(f"  ── {name}（{key}）", width)))
    for line in wrap_hanging(f"  说明  : {desc}", width, indent="          "):
        print(line)
    for line in wrap_hanging(f"  分组  : {group_label}{life}", width, indent="          "):
        print(line)
    for line in wrap_hanging(f"  存储  : {storage}", width, indent="          "):
        print(line)
    detail = f"  当前  : {'开启' if curr else '关闭'}   出厂默认: {'开启' if default else '关闭'}"
    if curr != default:
        detail += "（不一致，行尾标 *）"
    for line in wrap_hanging(detail, width, indent="          "):
        print(line)


def run_llm_modules_panel() -> None:
    """配置各 LLM 报告的启用/停用，以及全部功能开关（llm_settings.json + features.json）。

    标准 LLM 模块通过 enabled_llm 控制，存储在 llm_settings.json。
    功能开关（辩论模式增强、决策跨期反思闭环、量化指标、系统自检、
    确定性信号等）通过 Feature Flag 控制，存储在 features.json；四组分块的
    分组标题、显示名与顺序均取自 ``features.GROUP_ORDER`` / ``GROUP_LABELS``，
    新增开关自动上屏，渠道层不另写清单。
    辩论白脸/黑脸/综合（debate_pro/con/synthesis）保留在注册表
    （缓存 TTL/前缀清理仍依赖），菜单层隐藏，不在此面板展示。

    只读信息面（不引入配置写路径、不改编号派发）：``? 编号`` 查看该项说明与
    当前值/默认值；行尾 ``*`` 标记与出厂默认值不一致项（配置漂移）；⚗ 实验项
    行尾附 ``experiment_stats`` 启用统计（读取失败静默省略）。

    写路径三通道（编号派发与 Web 面板派生不受影响）：
      - 批量：``r 编号或键名`` 恢复该项所在分组出厂默认、``ra`` 恢复全部默认
        （均走 ``features.clear_feature_overrides`` 批量原子写，恢复默认=删覆写键）、
        ``x`` 实验项一键全关（experimental 集合回到无实验态，便于 bisect）；
      - 键名：裸键名切换，与编号双通道（编号漂移免疫）；
      - 赋值：``键名=on|off``，与 CLI ``--feature NAME=VALUE`` 同一解析器与词表
        （含已合并旧键别名过渡）。
    """
    # 局部导入：写盘/读数/提示读取统一经 handlers_config（与 [M] 拆分同一手法），
    # 保证既有 `handlers_config.<符号>` 的 patch 点继续有效，测试零改动。
    from src.python.tui import handlers_config as hc

    from src.python.config import default_enabled_llm
    from src.python.config.features import (
        GROUP_LABELS,
        GROUP_ORDER,
        clear_feature_overrides,
        experimental_flags,
        feature_switch_registry,
        is_feature_enabled,
        parse_switch_override,
        parse_switch_value,
        switches_in_group,
    )
    from src.python.core.experiment_stats import load_experiment_usage
    from src.python.core.perf import module_cost_summary
    from src.python.core.registry import get_llm_module_names

    result = hc._read_llm_settings()
    if result is None:
        return
    settings = result[0]

    enabled_map = settings.get("enabled_llm", {})
    # 出厂默认（漂移比对基准）：enabled_llm 缺省值与运行时兜底一致取 True
    default_enabled = default_enabled_llm()
    # LLM 模块清单 = 模块注册表全集（辩论三段不在模块注册表内，其缓存登记在缓存域）；
    # 辩论运行开关由下方功能开关（正反辩论 / 条件推理）控制
    module_names = hc.filter_menu_llm_modules(get_llm_module_names())

    # 功能开关分块：(分组标题, [(flag_key, 显示名), ...])，顺序即注册表顺序
    switch_blocks = [(group, list(switches_in_group(group))) for group in GROUP_ORDER]
    # 行首 ⚗ 标记仅给实验项（experimental 字段，与所属组无关；当前 2 项均落机制与诊断块内）
    experiment_keys = {flag for flag, _d in experimental_flags()}

    # 名称列宽：取清单内最长显示名，使各行状态方括号纵向对齐（超宽名不截断）
    name_column = max(
        map(
            display_width,
            [
                *module_names.values(),
                *(d.label for _title, block in switch_blocks for _flag, d in block),
            ],
        )
    )
    # 键名列宽：面板内显式展示每一项的键名（`? 编号`/`键名`/`键名=on|off` 都以此为输入，
    # 不让用户猜）。标准模块与功能开关**各自取块内最长键名**分行对齐——开关键名明显更长
    # （如 `rebalance_schedule_replay`），统一取全局最长会把整个面板宽度撑大。
    key_column_llm = max(map(display_width, module_names)) if module_names else 0
    key_column_sw = max((display_width(flag) for _title, block in switch_blocks for flag, _d in block), default=0)

    def _emit(message: str) -> None:
        """按当前内宽输出一行提示（窄屏上 `[!]`/`[OK]` 长句也不越界折行）。"""
        for line in wrap_hanging(message, inner_width(terminal_columns())):
            print(line)

    state = {"repaint": True, "reveal_keys": False, "tuples": []}

    def _apply_toggle(num: int, key: str, name: str, kind: str, new_val: bool) -> None:
        """写路径单源：应用开/关切换 + 反馈 + 置重绘 + 刷新缓存（编号/键名/赋值三通道汇合）。"""
        payload_key = f"enabled_llm.{key}" if kind == "llm" else key
        if hc._apply_edit({"key": payload_key, "value": new_val}):
            if kind == "llm":
                enabled_map[key] = new_val
            _emit(f"  {GREEN}[OK]{RESET} {num} {name} 已{'开启' if new_val else '关闭'}")
            state["repaint"] = True
            hc.refresh_config()

    def _make_toggle(num: str, key: str, name: str, kind: str) -> Callable[[], None]:
        def _toggle() -> None:
            curr = enabled_map.get(key, True) if kind == "llm" else is_feature_enabled(key)
            _apply_toggle(int(num), key, name, kind, not curr)

        return _toggle

    def _render(nav: NavState) -> list[str]:
        rows: list[str | None] = []
        tuples: list[tuple[int, str, str, bool, str]] = []
        exp_stats = load_experiment_usage()
        try:
            cost_history = module_cost_summary(COST_HISTORY_DAYS)
        except Exception:
            hc.logger.debug("[S] 模块费用摘要读取失败，静默省略", exc_info=True)
            cost_history = {}

        columns = terminal_columns()
        narrow = layout_tier(columns) == "narrow"

        # ① 标准 LLM 模块（1-7）——行尾 * 标记与出厂默认不一致项
        for i, (sfx, name) in enumerate(module_names.items(), 1):
            status = enabled_map.get(sfx, True)
            star = "" if status == default_enabled.get(sfx, True) else "*"
            tuples.append((i, sfx, name, status, "llm"))
            cross_hint = DUAL_ENTRY_CROSS_HINTS.get(sfx, "")
            cost_info = cost_history.get(sfx) or {}
            runs = cost_info.get("runs")
            notes = f" {cross_hint}" if cross_hint else ""
            if isinstance(runs, int) and runs > 0:
                notes += (
                    f" · {runs}次 ¥{float(cost_info.get('total') or 0.0):.4f}"
                    f" 均¥{float(cost_info.get('avg') or 0.0):.4f}"
                )
            rows.extend(
                format_item(
                    number=i,
                    label=name,
                    key=sfx,
                    enabled=status,
                    star=star,
                    marker="",
                    cursor=nav.marker(i - 1),
                    notes=notes,
                    columns=columns,
                    name_column=name_column,
                    key_column=key_column_llm,
                    number_width=len(str(len(module_names) + len(feature_switch_registry))),
                    reveal_key=state["reveal_keys"],
                )
            )

        # ② 功能开关：编号紧随标准模块之后，四组按 GROUP_ORDER 逐块顺序派发
        next_serial = len(module_names) + 1
        boxed = use_panel_box(columns)
        for group, block in switch_blocks:
            rows.append(None if boxed else "")
            rows.append(
                format_heading(
                    GROUP_LABELS[group].split("（", 1)[0],
                    sum(1 for flag, _d in block if is_feature_enabled(flag)),
                    len(block),
                    columns,
                )
            )
            for j, (flag, d) in enumerate(block, next_serial):
                status = is_feature_enabled(flag)
                # 行首 ⚗ 占位列：实验项标 ⚗、其余留同宽空白以对齐状态列
                marker = pad_right("⚗" if flag in experiment_keys else "", EXPERIMENT_MARK_COLUMNS)
                star = "" if status == d.default else "*"
                notes = ""
                if flag in experiment_keys:
                    entry = exp_stats.get(flag) or {}
                    if isinstance(entry.get("enabled_count"), int):
                        date = str(entry.get("last_enabled_date") or "")[5:]
                        notes += f"（启用 {entry['enabled_count']} 次" + (f" · 最近 {date}" if date else "") + "）"
                tuples.append((j, flag, d.label, status, "feature"))
                cross_hint = DUAL_ENTRY_CROSS_HINTS.get(flag, "")
                if cross_hint:
                    notes += f" {cross_hint}"
                rows.extend(
                    format_item(
                        number=j,
                        label=d.label,
                        key=flag,
                        enabled=status,
                        star=star,
                        marker=marker,
                        cursor=nav.marker(j - 1),
                        notes=notes,
                        columns=columns,
                        name_column=name_column,
                        key_column=key_column_sw,
                        number_width=len(str(len(module_names) + len(feature_switch_registry))),
                        reveal_key=state["reveal_keys"],
                    )
                )
            next_serial += len(block)

        rows.append("")
        rows.append(f"{nav.marker(len(tuples))}0. 返回主菜单")
        state["tuples"] = tuples
        print()
        panel_rows = [
            *rows,
            None if boxed else "",
            *legend_lines(COST_HISTORY_DAYS, columns, reveal_key=state["reveal_keys"]),
        ]
        if not state["repaint"]:
            # 窄终端（手机）：只读查询（? 说明）与失败路径不整屏重绘——详情/报错留屏
            # 不被面板顶走；写路径成功后 repaint=True 即时重绘（结果必须立刻可见）
            print("  （输入 p 重绘面板）")
            print()
        elif boxed:
            print("\n".join(render_panel("配置 LLM 报告章节与功能开关", panel_rows)))
        else:
            header = truncate_display(f"功能开关（{len(tuples)} 项）", inner_width(columns) - 5)
            print(style_heading(f"  ── {header} ──"))
            print("\n".join(f"  {row}" if row else "" for row in panel_rows))
        if state["repaint"]:
            for _line in wrap_hanging(
                "  基础报告章节组（基金深度分析/市场新闻/历史走势+回撤/组合演进/行动建议）在菜单 [P] 配置",
                inner_width(columns),
            ):
                print(_line)
            print()
        # 本轮已渲染 → 窄终端下一轮只回反馈行（省纵向空间）；宽/中档照常整屏重绘
        state["repaint"] = not narrow
        return []

    def _dispatch_tuple(target: tuple[int, str, str, bool, str], new_val: bool) -> None:
        num, key, name, _curr, kind = target
        _apply_toggle(num, key, name, kind, new_val)

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
            elif target[4] != "feature":
                _emit(f"  {YELLOW}[!]{RESET} 恢复默认仅支持功能开关分组（LLM 模块可逐项切换）")
            else:
                group = feature_switch_registry[target[1]].group
                group_flags = [flag for flag, _d in switches_in_group(group)]
                removed = clear_feature_overrides(group_flags)
                _emit(f"  {GREEN}[OK]{RESET} 已恢复「{GROUP_LABELS[group]}」默认（移除 {removed} 项覆写）")
                state["repaint"] = True
            return

        assign_name, eq, assign_val = raw.partition("=")
        assign_name = assign_name.strip()
        if eq:
            # 赋值通道：功能开关走 CLI 同一解析器（词表/旧键别名过渡一致）；
            # LLM 模块不在 feature 注册表，用与 CLI 相同的 on/off 词表本地校验
            feature_item = next((it for it in tuples if it[1] == assign_name and it[4] == "feature"), None)
            llm_item = next((it for it in tuples if it[1] == assign_name and it[4] == "llm"), None)
            if feature_item is not None:
                try:
                    _parsed_flag, new_val = parse_switch_override(raw)
                except ValueError as e:
                    _emit(f"  {YELLOW}[!]{RESET} {e}")
                    return
                _dispatch_tuple(feature_item, new_val)
                return
            if llm_item is not None:
                new_val = parse_switch_value(assign_val)
                if new_val is None:
                    _emit(f"  {YELLOW}[!]{RESET} 取值不可识别；可选: on / off")
                    return
                _dispatch_tuple(llm_item, new_val)
                return
            try:
                parse_switch_override(raw)
            except ValueError as e:
                _emit(f"  {YELLOW}[!]{RESET} {e}")
            else:
                _emit(f"  {YELLOW}[!]{RESET} 未知条目「{assign_name}」")
            return

        target = match_switch_item(raw, tuples)
        if target is None:
            if raw.isdigit():
                _emit(f"  {YELLOW}[!]{RESET} 无效编号")
            else:
                _emit(f"  {YELLOW}[!]{RESET} 未知编号或键名「{raw}」（可输入编号、键名 或 键名=on|off）")
            return
        _dispatch_tuple(target, not target[3])

    # 可派发项清单：编号在 setup 已固定（module_names + switch_blocks 顺序稳定）
    panel_items = [
        PanelItem(str(i), name, action=_make_toggle(str(i), sfx, name, "llm"))
        for i, (sfx, name) in enumerate(module_names.items(), 1)
    ]
    _next_serial = len(module_names) + 1
    for _g, _block in switch_blocks:
        for _flag, _d in _block:
            panel_items.append(
                PanelItem(
                    str(_next_serial), _d.label, action=_make_toggle(str(_next_serial), _flag, _d.label, "feature")
                )
            )
            _next_serial += 1
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
