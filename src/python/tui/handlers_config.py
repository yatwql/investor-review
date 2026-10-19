"""TUI 配置管理命令处理器。

所有配置管理相关的 TUI 命令处理函数（菜单 D（二级 C/F/O）/P/S/R/A/I）。
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from src.python.core.constants import PROJECT_ROOT
from src.python.core.logger import setup_logger
from src.python.core.reader import list_xlsx_files
from src.python.tui.tui_menu import (
    GREEN,
    RED,
    RESET,
    YELLOW,
    filter_menu_llm_modules,
    get_config_cache,
    refresh_config,
)
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
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.handlers_switch import (
    COST_HISTORY_DAYS,
    DUAL_ENTRY_CROSS_HINTS,
    EXPERIMENT_MARK_COLUMNS,
    match_switch_item,
    show_switch_detail,
)
from src.python.tui.text_layout import display_width, pad_right, render_panel, style_heading, truncate_display
from src.python.tui.tui_keys import input_choice

logger = setup_logger()


def _apply_edit(payload: dict) -> bool:
    """经共享编辑层（config.edit_ops）应用配置变更。

    白名单校验、值规则与写入分派的唯一实现在共享层（与 Web 同一函数、同一强度）；
    本函数仅做 TUI 错误呈现（校验失败 → 黄色提示行，写入失败 → 红色错误行）。

    Args:
        payload: 与 Web POST /api/config/edit 相同结构（key + value 或 action）。

    Returns:
        True = 写入成功。
    """
    from src.python.config.edit_ops import ConfigEditError, apply_config_edit

    try:
        apply_config_edit(payload)
        return True
    except ConfigEditError as e:
        print(f"  {YELLOW}[!]{RESET} {e}")
        return False
    except Exception:
        logger.exception("配置写入失败")
        print(f"  {RED}[ERR]{RESET} 配置写入失败，详情请查看日志 logs/app.log")
        return False


def _read_llm_settings() -> tuple[dict, str] | None:
    """读取 llm_settings.json 配置（支持 JSON 注释）。

    Returns:
        (settings_dict, path) 成功时；失败时返回 None（已输出错误提示）
    """
    from src.python.config import get_config, strip_json_comments

    config_path = get_config().get(
        "llm_settings_file",
        os.path.join(PROJECT_ROOT, "data/config/llm_settings.json"),
    )
    try:
        with open(config_path, encoding="utf-8-sig") as f:
            raw = f.read()
        settings = json.loads(strip_json_comments(raw))
        return settings, config_path
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"  {RED}[ERR]{RESET} 无法读取 llm_settings.json")
        return None


def _edit_single_config(key: str, label: str, default: str = "", *, pre_hook=None) -> None:
    """通用单配置项编辑命令。

    封装 刷新 → 显示当前值 → 输入新值 → 保存 的重复模式。

    Args:
        key: config.json 中的键名
        label: 显示用名称
        default: 默认值
        pre_hook: 可选前置回调（如显示文件列表），无参回调
    """
    refresh_config()
    config = get_config_cache() or {}
    current = config.get(key, default)
    if pre_hook:
        pre_hook()
    print(f"  当前{label}: {current}")
    print(f"  请输入新{label}（留空则不修改）:")
    try:
        new_val = input_choice("  > ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if new_val is None:
        print("  未修改")
        return
    if new_val:
        if _apply_edit({"key": key, "value": new_val}):
            refresh_config()
            print(f"  {GREEN}[OK]{RESET} {label}已更新为: {new_val}")
    else:
        print("  未修改")


def _list_xlsx_preview() -> None:
    """列出当前 holdings_dir 中的 xlsx 文件（供 _cmd_config_filename 使用）。"""
    config = get_config_cache() or {}
    files = list_xlsx_files(config.get("holdings_dir", ""))
    if files:
        print("  当前目录中的 xlsx 文件:")
        for i, f in enumerate(files, 1):
            print(f"    [{i}] {os.path.basename(f)}")
        print()


def _cmd_config_dir() -> None:
    """配置持仓目录。"""
    _edit_single_config("holdings_dir", "目录")


def _cmd_config_filename() -> None:
    """配置持仓文件名。"""
    _edit_single_config("holdings_filename", "文件名", pre_hook=_list_xlsx_preview)


def _cmd_config_output_dir() -> None:
    """配置报告输出目录。"""
    _edit_single_config("output_dir", "报告输出目录")


# 配置入口地图（只读索引）：配置项 → 所在菜单键。真值是主菜单 MENU_ITEMS 的按键，
# 本表只做「配置散在哪些键」的导流说明（零行为变化，不改任何配置）。新增配置入口时
# 在此补一行；键位调整时由 test_handlers_config 的「入口地图键均存在于主菜单」用例兜底。
_CONFIG_ENTRY_MAP: tuple[tuple[str, str, str], ...] = (
    ("功能开关 / LLM 模块启停 / 实验项", "[S]", "四组功能开关 + 7 个 LLM 标准模块，行尾费用摘要与启用统计"),
    ("报告章节取舍（顺序与开关）", "[P]", "基金深度分析 / 市场新闻 / 历史走势+回撤 / 组合演进 / 行动建议"),
    ("对比指数池（自定义基准）", "[I]", "增删指数、恢复默认"),
    ("持仓匿名化（代码/名称脱敏）", "[A]", "off / code_display / full_anonymous / summary 四档"),
    ("配置文件与目录位置", "[D]", "持仓目录 / 持仓文件名 / 报告输出目录（子菜单 C/F/O）"),
    ("重新加载配置", "[R]", "改完 config.json / llm_settings.json 手工项后刷新内存配置"),
    ("缓存管理（统计与清理）", "[3]", "统计首屏 + 子菜单内 3 清理过期缓存"),
    ("数据源健康历史 / 运行日志", "[H] / [V]", "近期数据源检查记录 / 结构化运行日志（可按级别筛选）"),
    ("系统自检", "[T]", "环境/配置/目录/数据源一键体检（开关 doctor_check 关闭时该键不可见）"),
)


def _render_config_entry_map() -> None:
    """渲染配置入口地图（只读索引，不写配置、不等待按键）。"""
    print()
    print(style_heading("  ── 配置入口地图（哪个配置在哪个菜单）──"))
    width = max(display_width(label) for label, _key, _hint in _CONFIG_ENTRY_MAP)
    for label, key, hint in _CONFIG_ENTRY_MAP:
        print(f"   {pad_right(label, width)}  →  {pad_right(key, 9)} {hint}")
    print("  （仅索引导流，不修改任何配置；config.json 手工键说明见手册 how-to-config）")


def _cmd_config_dir_info() -> None:
    """查看配置与目录信息子菜单 — 对应主菜单 [D] 及其二级选项 [C]/[F]/[O]/[M]/[0]。

    持仓目录 / 持仓文件名 / 报告输出目录三项聚合到 [D] 之下（主菜单不再单列）；
    ``[M]`` 打印配置入口地图（各配置项 → 所在菜单键，只读索引）；
    子菜单循环直至 [0]（或空输入 / Ctrl+C）返回主菜单。
    子项在调用时从模块全局取函数（便于测试打桩与后续替换）。
    """
    items = [
        ("C", "持仓信息目录", _cmd_config_dir),
        ("F", "持仓信息文件名", _cmd_config_filename),
        ("O", "报告输出目录", _cmd_config_output_dir),
        ("M", "配置入口地图（各配置项所在菜单）", _render_config_entry_map),
    ]

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 配置与目录信息 ──"))
        for i, (_key, label, _fn) in enumerate(items):
            print(f" {nav.marker(i)} [{_key}] {label}")
        print(f" {nav.marker(len(items))} [0] 返回主菜单")
        print()
        return []

    panel_items = [PanelItem(key, label, action=fn) for key, label, fn in items]
    panel_items.append(PanelItem("0", "返回主菜单", kind="return"))

    try:
        panel_loop(
            panel_items,
            render=_render,
            prompt=panel_prompt("选择", example="C/F/O/M", help_hint=None),
            read=input_choice,
            on_text=lambda _t: print("  [!] 无效选择，请输入 C/F/O/M/0"),
            default_key="0",
        )
    except (EOFError, KeyboardInterrupt):
        print()


# 持仓变动复盘双入口互指标注（只读行尾提示，行为零变化）：章本体（独立章节组
# `holding_change_review`）与归因内容（LLM 区 `holding_change` 模块）为解耦的有意
# 设计、默认态相反，面板相邻两行命名近似易误判——两侧行尾互相指出对方入口位置。
def _cmd_config_llm_modules() -> None:
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

    result = _read_llm_settings()
    if result is None:
        return
    settings = result[0]

    enabled_map = settings.get("enabled_llm", {})
    # 出厂默认（漂移比对基准）：enabled_llm 缺省值与运行时兜底一致取 True
    default_enabled = default_enabled_llm()
    # LLM 模块清单 = 模块注册表全集（辩论三段不在模块注册表内，其缓存登记在缓存域）；
    # 辩论运行开关由下方功能开关（正反辩论 / 条件推理）控制
    module_names = filter_menu_llm_modules(get_llm_module_names())

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
        if _apply_edit({"key": payload_key, "value": new_val}):
            if kind == "llm":
                enabled_map[key] = new_val
            _emit(f"  {GREEN}[OK]{RESET} {num} {name} 已{'开启' if new_val else '关闭'}")
            state["repaint"] = True
            refresh_config()

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
            logger.debug("[S] 模块费用摘要读取失败，静默省略", exc_info=True)
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
            read=input_choice,
            repaint="feedback",
            on_text=_on_text,
            on_help=_on_help,
            on_nav_moved=lambda: state.update(repaint=True),
        )
    except (EOFError, KeyboardInterrupt):
        print()


def _cmd_config_comparison_indices() -> None:
    """管理对比指数池（竞争语境中使用的多指数对比）。交互循环经 `panel_loop` 单源。"""
    from src.python.config import get_default

    def _indices() -> dict[str, str]:
        config = get_config_cache() or {}
        return config.get("comparison_indices") or get_default("comparison_indices")

    def _render(nav: NavState) -> list[str]:
        refresh_config()
        indices = _indices()
        rows: list[str | None] = ["自定义基准指数，用于报告中组合 vs 多指数对比", f"当前指数 ({len(indices)} 个):"]
        if indices:
            for i, (code, name) in enumerate(indices.items(), 1):
                rows.append(f"  {i}. {code} ({name})")
        else:
            rows.append("  空池（仅显示沪深300）")
        rows += [
            None,
            f"{nav.marker(0)}A. 添加指数",
            f"{nav.marker(1)}D. 删除指数",
            f"{nav.marker(2)}R. 重置为默认预设",
            f"{nav.marker(3)}0. 返回主菜单",
        ]
        print()
        print("\n".join(render_panel("管理对比指数池", rows)))
        print()
        return []

    def _reset() -> None:
        if _apply_edit({"key": "comparison_indices", "action": "reset"}):
            print(f"  {GREEN}[OK]{RESET} 对比指数池已重置为默认预设")

    items = [
        PanelItem("A", "添加指数", action=lambda: _add_comparison_index(_indices())),
        PanelItem("D", "删除指数", action=lambda: _remove_comparison_index(_indices())),
        PanelItem("R", "重置为默认预设", action=_reset),
        PanelItem("0", "返回主菜单", kind="return"),
    ]

    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("选择操作", example="A 添加 / D 删除 / R 重置"),
            read=input_choice,
            on_text=lambda _t: print(f"  {YELLOW}[!]{RESET} 无效选择，请重试"),
        )
    except (EOFError, KeyboardInterrupt):
        print()


def _add_comparison_index(indices: dict[str, str]) -> None:
    """添加指数到对比池。"""
    print("  请输入指数代码（如 sh000905）:")
    try:
        code = input_choice("  > ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if code is None:
        return
    if not code:
        print(f"  {YELLOW}[!]{RESET} 代码不能为空")
        return
    print("  请输入指数名称（如 中证500）:")
    try:
        name = input_choice("  > ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if name is None:
        return
    if not name:
        print(f"  {YELLOW}[!]{RESET} 名称不能为空")
        return
    # 重复/长度/字符等规则校验与写入全在共享层（与 Web 同一函数、同一强度）
    if _apply_edit({"key": "comparison_indices", "action": "add", "code": code, "name": name}):
        print(f"  {GREEN}[OK]{RESET} 已添加 {code} ({name})")


def _remove_comparison_index(indices: dict[str, str]) -> None:
    """从对比池中删除指数。"""
    if not indices:
        print(f"  {YELLOW}[!]{RESET} 对比池为空，无指数可删除")
        return
    items = list(indices.items())
    print("  选择要删除的指数编号:")
    for i, (code, name) in enumerate(items, 1):
        print(f"    [{i}] {code} ({name})")
    print("    [0] 取消")
    try:
        choice = input_choice("  > ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice is None:
        return
    try:
        idx = int(choice)
    except (ValueError, TypeError):
        print(f"  {YELLOW}[!]{RESET} 无效编号")
        return
    if idx == 0:
        return
    if 1 <= idx <= len(items):
        code, name = items[idx - 1]
        if _apply_edit({"key": "comparison_indices", "action": "remove", "code": code}):
            print(f"  {GREEN}[OK]{RESET} 已删除 {code} ({name})")
    else:
        print(f"  {YELLOW}[!]{RESET} 编号超出范围")


def _cmd_config_report_boards() -> None:
    """配置基础报告章节（基金深度分析 / 市场新闻 / 组合历史走势+回撤 / 组合演进 / 行动建议）。

    报告章节与增强子模块（数据质量/估值分位/市场温度/财报摘要/财务指标等）已在
    功能开关注册表的「报告章节与增强」组，统一在菜单 [S] 配置（本面板不再另设入口）。
    交互循环经 `panel_loop` 单源：方向键游标、Enter 防误触、直达同步、无效反馈。
    """
    from src.python.config import (
        get_config,
        is_enable_action,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_news,
        is_enable_portfolio_evolution,
    )

    # 编号 → (配置键, 章节名, 状态读取器)：编号与派发键单源，渲染与动作共用
    _flags: dict[str, tuple[str, str, Callable[[dict], bool]]] = {
        "1": ("enable_fund_deep_analysis", "基金深度分析", is_enable_fund_deep_analysis),
        "2": ("enable_news", "市场新闻", is_enable_news),
        "3": ("enable_history", "组合历史走势+回撤", is_enable_history),
        "4": ("enable_portfolio_evolution", "组合演进", is_enable_portfolio_evolution),
        "5": ("enable_action", "行动建议", is_enable_action),
    }

    def _make_toggle(num: str) -> Callable[[], None]:
        cfg_key, label, getter = _flags[num]

        def _toggle() -> None:
            current = getter(get_config())
            if _apply_edit({"key": cfg_key, "value": not current}):
                print(f"  {GREEN}[OK]{RESET} {label}已{'禁用' if current else '启用'}")

        return _toggle

    def _render(nav: NavState) -> list[str | None]:
        config = get_config()
        # 编号后的章节名补齐到同一列，使状态方括号纵向对齐
        section_column = max(display_width(label) for _k, label, _g in _flags.values())
        rows: list[str | None] = []
        for i, num in enumerate(sorted(_flags)):
            _key, label, getter = _flags[num]
            enabled = getter(config)
            status = f"{GREEN}启用{RESET}" if enabled else f"{RED}禁用{RESET}"
            rows.append(f"{nav.marker(i)}{num}. {pad_right(label, section_column)} [{status}]")
        rows.append("")
        rows.append(f"{nav.marker(5)}6. 报告增强子模块 / LLM 分析章节 — 请在菜单 S 配置")
        rows.append(f"{nav.marker(6)}0. 返回主菜单")
        return [
            None,
            *render_panel("配置报告可选章节", rows),
            "  提示：报告章节与增强、LLM 分析章节请在菜单 [S] 配置",
            None,
        ]

    items = [PanelItem(num, _flags[num][1], action=_make_toggle(num)) for num in sorted(_flags)]
    items += [
        PanelItem(
            "6",
            "报告增强子模块 / LLM 分析章节",
            kind="info",
            action=lambda: print(f"  {YELLOW}[!]{RESET} 报告增强子模块与 LLM 分析章节请使用菜单 [S] 配置"),
        ),
        PanelItem("0", "返回主菜单", kind="return"),
    ]

    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("输入编号切换 (0-6)"),
            read=input_choice,
            on_text=lambda _t: print(f"  {YELLOW}[!]{RESET} 无效编号"),
        )
    except (EOFError, KeyboardInterrupt):
        print()

    refresh_config()


def _cmd_refresh_config() -> None:
    """重新加载所有配置（config.json + llm_settings.json + llm_key.json）。"""
    from src.python.config import get_config, get_llm_config
    from src.python.config._core import invalidate_config_cache
    from src.python.config._llm_settings import invalidate_llm_config_cache
    from src.python.llm.pricing import reload_pricing

    invalidate_config_cache()
    invalidate_llm_config_cache()

    config = get_config()
    llm_config = get_llm_config()
    reload_pricing()

    # 刷新 BatchDispatcher 限速器配置（batch_rate_limit 即时生效）
    from src.python.fetcher.batch import get_rate_limiter

    get_rate_limiter.cache_clear()

    # 刷新 tui_menu 配置缓存
    refresh_config()

    if config:
        print(f"  {GREEN}[OK]{RESET} config.json 已重新加载")
    if llm_config:
        print(f"  {GREEN}[OK]{RESET} llm_settings.json + llm_key.json 已重新加载")
    else:
        print(f"  {YELLOW}[!]{RESET} LLM 未配置（llm_key.json 或 llm_providers.json 缺失或无效）")


def _cmd_config_anonymization_mode() -> None:
    """配置持仓匿名化（关闭/代码显示/完全匿名/汇总）。交互循环经 `panel_loop` 单源。"""
    from src.python.config.anonymizer import (
        ANONYMIZATION_MODE_DESCRIPTIONS,
        get_anonymization_mode,
    )

    # 定义显示顺序
    _ORDERED_KEYS = ["off", "code_display", "full_anonymous", "summary"]

    # 说明列宽：取最长模式说明，使选中标记、编号与说明各占固定列
    desc_column = max(map(display_width, ANONYMIZATION_MODE_DESCRIPTIONS.values()))

    def _apply_mode(num: str) -> None:
        current = get_anonymization_mode()
        new_mode = _ORDERED_KEYS[int(num) - 1]
        if new_mode == current:
            print(f"  {YELLOW}[!]{RESET} 已是当前模式")
        elif _apply_edit({"key": "anonymization.mode", "value": new_mode}):
            print(f"  {GREEN}[OK]{RESET} 持仓匿名化已切换为: {new_mode}")

    def _render(nav: NavState) -> list[str]:
        current = get_anonymization_mode()
        rows: list[str | None] = [f"当前模式: {current}", None]
        for i, mode_key in enumerate(_ORDERED_KEYS):
            desc = ANONYMIZATION_MODE_DESCRIPTIONS.get(mode_key, mode_key)
            mode_marker = "►" if mode_key == current else " "
            rows.append(f"{nav.marker(i)}{mode_marker} {i + 1}. {pad_right(desc, desc_column)}")
        rows += [None, f"{nav.marker(4)}0. 返回主菜单"]
        print()
        print("\n".join(render_panel("配置持仓匿名化", rows)))
        print()
        return []

    def _on_text(t: str) -> None:
        try:
            idx = int(t)
        except (ValueError, TypeError):
            print(f"  {YELLOW}[!]{RESET} 请输入有效编号")
            return
        if 1 <= idx <= len(_ORDERED_KEYS):
            _apply_mode(str(idx))
        else:
            print(f"  {YELLOW}[!]{RESET} 无效编号")

    items = [
        PanelItem(str(i), ANONYMIZATION_MODE_DESCRIPTIONS.get(k, k), action=lambda i=i: _apply_mode(str(i)))
        for i, k in enumerate(_ORDERED_KEYS, 1)
    ]
    items.append(PanelItem("0", "返回主菜单", kind="return"))

    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("选择匿名化模式", example="1-4 选模式"),
            read=input_choice,
            on_text=_on_text,
        )
    except (EOFError, KeyboardInterrupt):
        print()


def _cmd_config_llm_providers() -> None:
    """管理 LLM 多链线路优先级（备用顺序）。

    与 CLI ``--llm-provider-order``、Web 配置面同源：写路径全部经共享编辑层
    ``apply_config_edit``（llm_providers.priority / reorder），本面板只做展示与
    「交换两个编号」的输入适配。Esc 即时返回主菜单。
    """
    from src.python.config import get_llm_providers

    state: dict = {"ordered": [], "width": 80}

    def _load() -> tuple[str, list]:
        cfg = get_llm_providers()
        strategy = str(cfg.get("strategy") or "priority")
        raw_providers = [p for p in (cfg.get("providers") or []) if isinstance(p, dict)]
        # 展示顺序 = priority 升序（数值小 = 链序靠前），与运行时 priority 策略口径一致
        ordered = sorted(enumerate(raw_providers), key=lambda t: (t[1].get("priority", 99), t[0]))
        return strategy, ordered

    strategy, ordered = _load()
    columns = terminal_columns()
    width = inner_width(columns)
    if len(ordered) < 2:
        # 单线路直接返回（不进入输入循环，行输入不被触发）
        print()
        print(style_heading(truncate_display(f"  ── LLM 多链线路优先级（strategy: {strategy}） ──", width)))
        for line in wrap_hanging("  当前仅一条线路（或未配置多链），无需调整", width):
            print(line)
        return

    def _render(nav: NavState) -> list[str]:
        strategy, ordered = _load()
        columns = terminal_columns()
        width = inner_width(columns)
        state["ordered"] = ordered
        state["width"] = width
        print()
        print(truncate_display(f"  ── LLM 多链线路优先级（strategy: {strategy}） ──", width))
        for num, (_i, provider) in enumerate(ordered, 1):
            row = (
                f"  {nav.marker(num - 1)}{num}. {provider.get('name')}（{provider.get('provider')}）priority "
                f"{provider.get('priority', 99)}"
            )
            for line in wrap_hanging(row, width):
                print(line)
        print(f"  {nav.marker(len(ordered))}0. 返回主菜单")
        if strategy not in ("priority", "fallback_only"):
            for line in wrap_hanging(
                f"  提示：当前策略 {strategy} 下实际链序由权重/成本决定，此处顺序仅在 priority / fallback_only 策略下生效",
                width,
            ):
                print(line)
        print()
        return []

    def _try_swap(a: int, b: int) -> bool:
        """配对交换：越界/相同编号返回 False（调用方给统一重提示），成功经共享编辑层写盘。"""
        ordered = state["ordered"]
        width = state["width"]
        if not (1 <= a <= len(ordered) and 1 <= b <= len(ordered) and a != b):
            return False
        names = [str(p.get("name")) for _i, p in ordered]
        names[a - 1], names[b - 1] = names[b - 1], names[a - 1]
        if _apply_edit({"key": "llm_providers.priority", "action": "reorder", "order": names}):
            for line in wrap_hanging(
                f"  {GREEN}[OK]{RESET} 已交换 {ordered[a - 1][1].get('name')} 与 {ordered[b - 1][1].get('name')} 的优先级",
                width,
            ):
                print(line)
        return True

    def _invalid() -> None:
        ordered = state["ordered"]
        width = state["width"]
        for line in wrap_hanging(
            f"  {YELLOW}[!]{RESET} 请输入两个不同的编号交换位置（如 3 1），范围 1-{len(ordered)}",
            width,
        ):
            print(line)

    def _on_text(choice: str) -> None:
        parts = choice.split()
        if len(parts) == 2:
            try:
                a, b = int(parts[0]), int(parts[1])
            except ValueError:
                a = b = -1
            if _try_swap(a, b):
                return
        _invalid()

    def _on_picked(keys: tuple[str, ...]) -> None:
        try:
            a, b = int(keys[0]), int(keys[1])
        except ValueError:
            a = b = -1
        if not _try_swap(a, b):
            _invalid()

    # 可派发项：编号线路（可导航，供 ↑↓ + Enter 收集配对）+ 0 返回
    items = [PanelItem(str(i), str(p.get("name"))) for i, (_x, p) in enumerate(ordered, 1)]
    items.append(PanelItem("0", "返回主菜单", kind="return"))

    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("输入两个编号交换优先级", example="3 1"),
            read=input_choice,
            pick=2,
            on_picked=_on_picked,
            on_text=_on_text,
        )
    except (EOFError, KeyboardInterrupt):
        print()
