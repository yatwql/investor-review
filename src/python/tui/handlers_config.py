"""TUI 配置管理命令处理器。

所有配置管理相关的 TUI 命令处理函数（菜单 D（二级 C/F/O）/P/S/R/A/I）。
"""

from __future__ import annotations

import os
from collections.abc import Callable

from src.python.core.logger import setup_logger
from src.python.core.reader import list_xlsx_files
from src.python.tui.tui_menu import (
    GREEN,
    RED,
    RESET,
    YELLOW,
    get_config_cache,
    refresh_config,
)
from src.python.tui.switch_panel import (
    inner_width,
    terminal_columns,
    render_titled_panel,
    use_panel_box,
    wrap_hanging,
)
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.text_layout import display_width, pad_right, style_heading, truncate_display
from src.python.tui.tui_keys import input_choice

# ── 兼容再导出（面板本体已迁至 handlers_switch）──────────────────────────
# `[S]` 面板现在 `handlers_switch.run_llm_modules_panel`，但它对该模块的取值统一经
# `handlers_config.<符号>`（函数内局部导入），以便既有测试 patch 点与外部调用保持有效。
# 这些名字在本文件内可能已无直接引用，故显式豁免 F401。
from src.python.tui.tui_menu import filter_menu_llm_modules  # noqa: F401

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
        # 配置已变：清页头状态行记忆（否则 TTL 内回首页仍显示旧值）
        from src.python.tui.status_line import reset_status_memo

        reset_status_memo()
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
    from src.python.config import read_llm_settings_file

    snapshot = read_llm_settings_file()
    if snapshot is None:
        print(f"  {RED}[ERR]{RESET} 无法读取 llm_settings.json")
        return None
    return snapshot


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
    ("功能开关 / LLM 模块启停 / 实验项", "[S]", "八组功能开关 + 7 个 LLM 标准模块，行尾费用摘要与启用统计"),
    ("报告章节取舍（顺序与开关）", "[C]", "五个顶层章节组的可见性"),
    ("对比指数池（自定义基准）", "[G]", "全局设置 → I（增删指数、恢复默认）"),
    ("持仓匿名化（代码/名称脱敏）", "[G]", "全局设置 → A（四档）"),
    ("配置文件与目录位置", "[G]", "全局设置 → D / F / O"),
    ("LLM 运行参数 / 多链线路", "[G]", "全局设置 → L（运行参数）/ M（线路优先级）"),
    ("重新加载配置", "[R]", "改完 config.json / llm_settings.json 手工项后刷新内存配置"),
    ("缓存管理（统计与清理）", "[3]", "统计首屏 + 子菜单内 3 清理过期缓存"),
    ("运行日志 / 健康历史 / 系统自检", "[D]", "诊断与排查 → V / H / T"),
)


def _render_config_entry_map() -> None:
    """渲染配置入口地图（只读索引，不写配置、不等待按键）。"""
    columns = terminal_columns()
    inner = inner_width(columns)
    print()
    print(style_heading(truncate_display("  ── 配置入口地图（哪个配置在哪个菜单）──", inner)))
    if use_panel_box(columns):
        width = max(display_width(label) for label, _key, _hint in _CONFIG_ENTRY_MAP)
        for label, key, hint in _CONFIG_ENTRY_MAP:
            print(f"   {pad_right(label, width)}  →  {pad_right(key, 9)} {hint}")
    else:
        # 窄档：表格放不下 → 两项一组（菜单键 + 标签 + 悬挂缩进说明），不硬折成锯齿
        for label, key, hint in _CONFIG_ENTRY_MAP:
            for line in wrap_hanging(f"   [{key}] {label}", inner):
                print(line)
            for line in wrap_hanging(f"     {hint}", inner, indent="     "):
                print(line)
    for line in wrap_hanging("  （仅索引导流，不修改任何配置；config.json 手工键说明见手册 how-to-config）", inner):
        print(line)


#: [D] 查看配置与目录信息 面板的二级选项登记表（键 → (显示名, 处理器属性名)）
#:
#: 单一登记点：面板渲染、按键分发与手册机检（`check-doc-drift` 第 18 项的
#: 「正文菜单键引用」分支）均从此表派生键集合——增删子项只改这一处，
#: 不会出现「面板上有、机检认为不存在」（或反过来）的双维护漂移。
#:
#: 处理器登记**属性名**而非函数对象：分发时按名从模块全局取（`_dir_info_items()`），
#: 使 `@patch("...handlers_config._cmd_config_dir")` 这类模块属性打桩始终生效——
#: 若在导入时就把函数对象存进表里，打桩会落空且不报错。
DIR_INFO_ITEMS: dict[str, tuple[str, str]] = {
    "H": ("持仓信息目录", "_cmd_config_dir"),
    "F": ("持仓信息文件名", "_cmd_config_filename"),
    "O": ("报告输出目录", "_cmd_config_output_dir"),
    "M": ("配置入口地图（各配置项所在菜单）", "_render_config_entry_map"),
}

#: [D] 面板二级选项键（由 `DIR_INFO_ITEMS` 派生，供手册校验引用）
CONFIG_DIR_INFO_KEYS: tuple[str, ...] = tuple(DIR_INFO_ITEMS)


def _dir_info_items() -> list[tuple[str, str, Callable[[], None]]]:
    """解析登记表为 `(键, 显示名, 处理器)`——处理器按名实时取，便于打桩与替换。"""
    return [(key, label, globals()[handler_name]) for key, (label, handler_name) in DIR_INFO_ITEMS.items()]


def _cmd_config_dir_info() -> None:
    """查看配置与目录信息子菜单 — 对应 [G]→D 及其二级选项 [H]/[F]/[O]/[M]/[0]。

    持仓目录 / 持仓文件名 / 报告输出目录三项聚合到 [G]→D 之下（主菜单不再单列）；
    ``[M]`` 打印配置入口地图（各配置项 → 所在菜单键，只读索引）；
    子菜单循环直至 [0]（或空输入 / Ctrl+C）返回主菜单。
    子项在调用时从模块全局取函数（便于测试打桩与后续替换）。
    """
    items = _dir_info_items()

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 配置与目录信息 ──"))
        for i, (_key, label, _fn) in enumerate(items):
            print(f" {nav.marker(i)} [{_key}] {label}")
        print(f" {nav.marker(len(items))} [0] 返回全局设置")
        print()
        return []

    panel_items = [PanelItem(key, label, action=fn) for key, label, fn in items]
    panel_items.append(PanelItem("0", "返回全局设置", kind="return"))

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
#: [G] 全局设置七项（数字为主入口，字母为别名；分组只影响渲染）
GLOBAL_SETTINGS_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("D", "查看配置与目录信息", "_cmd_config_dir_info", "目录与文件"),
    ("F", "持仓文件名", "_cmd_config_filename", "目录与文件"),
    ("O", "报告输出目录", "_cmd_config_output_dir", "目录与文件"),
    ("L", "LLM 设置（运行参数 / 多链线路）", "_cmd_config_llm_tuning", "LLM"),
    ("I", "对比指数池", "_cmd_config_comparison_indices", "基准与呈现"),
    ("A", "持仓匿名化", "_cmd_config_anonymization_mode", "基准与呈现"),
    ("M", "LLM 多链线路优先级", "_cmd_config_llm_providers", "LLM"),
)


def _cmd_global_settings() -> None:
    """[G] 全局设置：七项分组渲染，数字为主入口、字母为别名；0 返回主菜单。"""
    from src.python.tui.tui_keys import input_choice

    while True:
        print()
        print(style_heading("  ── 全局设置 ──"))
        last_group = None
        for number, (letter, label, _handler, group) in enumerate(GLOBAL_SETTINGS_ITEMS, 1):
            if group != last_group:
                print(f"  {group}")
                last_group = group
            print(f"   {number}. [{letter}] {label}")
        print("   0. 返回主菜单")
        print()
        raw = input_choice("  选择编号或字母（回车=返回 · 0=返回）: ")
        if raw is None or raw.strip() in ("", "0"):
            return
        token = raw.strip().upper()
        letter = None
        if token.isdigit() and 1 <= int(token) <= len(GLOBAL_SETTINGS_ITEMS):
            letter = GLOBAL_SETTINGS_ITEMS[int(token) - 1][0]
        elif token in {item[0] for item in GLOBAL_SETTINGS_ITEMS}:
            letter = token
        if letter is None:
            print("  [!] 无效选择，请输入编号或字母")
            continue
        entry = next(item for item in GLOBAL_SETTINGS_ITEMS if item[0] == letter)
        globals()[entry[2]]()


def _cmd_config_llm_tuning() -> None:
    """LLM 调优参数（thinking 并发 / 总并发 / 重试 / 时间与费用预算）。

    清单、取值范围与说明全部来自 ``config.edit_ops.LLM_TUNING_SPECS``（与 Web 面板、
    编辑 API 同一白名单）；保存经 ``_apply_edit`` → 共享编辑层，校验强度与 Web 一致。
    """
    from src.python.config import get_llm_config
    from src.python.config.edit_ops import LLM_TUNING_SPECS, config_edit_whitelist
    from src.python.tui.panel_runtime import PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt

    llm = get_llm_config() or {}
    keys = list(LLM_TUNING_SPECS)

    def _edit(key: str):
        spec = LLM_TUNING_SPECS[key]

        def _run() -> None:
            current = llm.get(key, config_edit_whitelist[key].get("default"))
            print(f"  当前 {spec['label']}: {current}（范围 {spec['min']}~{spec['max']}）")
            if spec.get("hint"):
                print(f"  {spec['hint']}")
            try:
                new_val = input_choice("  输入新值（回车=不修改）> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not new_val:
                print("  未修改")
                return
            if _apply_edit({"key": key, "value": new_val}):
                refresh_config()
                print(f"  {GREEN}[OK]{RESET} {spec['label']}已更新为: {new_val}")

        return _run

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── LLM 调优参数 ──"))
        for i, key in enumerate(keys, 1):
            spec = LLM_TUNING_SPECS[key]
            print(
                f" {nav.marker(i - 1)} {i}. {spec['label']}"
                f"（当前 {llm.get(key, config_edit_whitelist[key].get('default'))}）"
            )
        print(f" {nav.marker(len(keys))} {len(keys) + 1}. LLM 多链线路优先级")
        print(f" {nav.marker(len(keys) + 1)} 0. 返回全局设置")
        print()
        return []

    items = [
        PanelItem(str(i), spec["label"], action=_edit(key)) for i, (key, spec) in enumerate(LLM_TUNING_SPECS.items(), 1)
    ]
    items.append(
        PanelItem(
            str(len(keys) + 1),
            "LLM 多链线路优先级",
            action=lambda: globals()["_cmd_config_llm_providers"](),
        )
    )
    items.append(PanelItem("0", "返回全局设置", kind="return"))
    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("输入编号修改", example="1 改 thinking 并发", help_hint=None),
            read=input_choice,
            on_text=lambda _t: print("  [!] 无效选择，请输入编号或 0"),
            default_key="0",
        )
    except (EOFError, KeyboardInterrupt):
        print()


def _cmd_config_content_options() -> None:
    """配置报告章节内容呈现（20 项六组）——实现见 ``handlers_switch``。

    本文件只保留菜单入口；面板本体（渲染/派发/重绘/帮助）在
    ``handlers_switch.run_content_options_panel``（域拆分：本文件已接近单文件行数红线）。
    """
    from src.python.tui.handlers_switch import run_content_options_panel

    run_content_options_panel()


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
        print("\n".join(render_titled_panel("管理对比指数池", rows)))
        print()
        return []

    def _reset() -> None:
        if _apply_edit({"key": "comparison_indices", "action": "reset"}):
            print(f"  {GREEN}[OK]{RESET} 对比指数池已重置为默认预设")

    items = [
        PanelItem(
            "A",
            "添加指数",
            action=lambda: _add_comparison_index(_indices()),
            detail="输入指数代码与名称后加入对比指数池（用于报告中的基准对比）",
        ),
        PanelItem(
            "D",
            "删除指数",
            action=lambda: _remove_comparison_index(_indices()),
            detail="从对比指数池中移除一个指数（不影响已生成的报告）",
        ),
        PanelItem(
            "R",
            "重置为默认预设",
            action=_reset,
            detail="清空自定义，恢复出厂预设的对比指数清单",
        ),
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
    """配置报告章节显隐（16 项四块 + 智囊团两个子项）——实现见 ``handlers_report_chapters``。

    章节清单/编号/来源/子项全部由 ``config.chapter_registry`` 派生，面板本体
    （渲染/派发/帮助）在 ``handlers_report_chapters.run_report_chapters_panel``；
    本文件只保留菜单入口（域拆分：本文件已接近单文件行数红线）。
    """
    from src.python.tui.handlers_report_chapters import run_report_chapters_panel

    run_report_chapters_panel()


def _cmd_refresh_config() -> None:
    """重新加载所有配置（config.json + LLM 三文件合并缓存：llm_settings/llm_key/llm_providers）。"""
    from src.python.config import get_config, get_llm_config
    from src.python.config._core import invalidate_config_cache
    from src.python.config._llm_settings import invalidate_llm_config_cache
    from src.python.llm.pricing import reload_pricing
    from src.python.tui.status_line import reset_status_memo

    invalidate_config_cache()
    invalidate_llm_config_cache()
    # 页头状态行记忆一并清除（TTL 内不清则首页仍显旧状态）
    reset_status_memo()

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
        print(f"  {GREEN}[OK]{RESET} LLM 配置已重新加载（llm_settings + llm_key + llm_providers）")
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
        print("\n".join(render_titled_panel("配置持仓匿名化", rows)))
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
        PanelItem(
            str(i),
            ANONYMIZATION_MODE_DESCRIPTIONS.get(k, k),
            action=lambda i=i: _apply_mode(str(i)),
            detail="切换到该匿名化模式（当前模式见面板顶部；立即写入配置）",
        )
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
    """管理 LLM 多链线路优先级（备用顺序）——实现见 ``handlers_llm_providers``。

    与 CLI ``--llm-provider-order``、Web 配置面同源：写路径全部经共享编辑层
    ``apply_config_edit``（llm_providers.priority / reorder）。本文件只保留菜单入口。
    """
    from src.python.tui.handlers_llm_providers import run_llm_providers_panel

    run_llm_providers_panel()
