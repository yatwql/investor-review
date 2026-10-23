#!/usr/bin/env python3
"""TUI 全层级面板渲染取样 —— 设计图样数据源（真实渲染路径，非手绘）。

覆盖一级主菜单、二级面板、三级子面板：每屏在独立伪终端里跑真实处理器，
按脚本送键后取整屏输出（含 ANSI 颜色），由 `tui_build.py` 转成 HTML 图样。

只读纪律：不触发报告生成、不刷新缓存、不改写任何配置文件——
文件选择类屏幕取出列表后即中止（Ctrl+C），统计/日志/自检类只读。

用法（单个屏幕，供驱动脚本调用）::

    COLUMNS=110 .venv/bin/python docs/plan/config-panel-mockup/tui_render.py --mode current
"""

from __future__ import annotations

import argparse
import dataclasses

#: 目标组序（内容域在前、机制收尾、LLM 增强收尾）
PROPOSED_ORDER = ("analysis", "standalone", "presentation", "mechanism", "llm_enhance")

#: 目标组标题（与现有四组同措辞风格，新增 LLM 分析增强）
PROPOSED_LABELS = {
    "analysis": "🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表）",
    "standalone": "📑 独立章节与回放（默认关闭 · 新增整页签或多期回放）",
    "presentation": "📊 呈现与体验（默认开启 · 只改呈现不改内容）",
    "mechanism": "⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验）",
    "llm_enhance": "🧠 LLM 分析增强（默认关闭 · 在 LLM 章节内追加辩论/情景段，无独立章节）",
}

#: 迁入 LLM 分析增强组的开关（在既有 LLM 调用内追加段落、不新增章节）
LLM_ENHANCE_KEYS = ("llm_debate_procon", "llm_debate_conditional")


def apply_proposed_grouping() -> None:
    """把注册表分组视图替换为目标组序（仅内存态，不写任何配置文件）。

    注册表本体在 ``_feature_registry``，``features`` 只是 re-export：
    ``switches_in_group`` 读前者，面板的局部导入读后者——两处都要替换，
    否则组内清单仍按旧归属派发。
    """
    import src.python.config._feature_registry as registry_module
    import src.python.config.features as features

    registry = dict(registry_module.feature_switch_registry)
    for key in LLM_ENHANCE_KEYS:
        registry[key] = dataclasses.replace(registry[key], group="llm_enhance")
    registry_module.feature_switch_registry = registry
    features.feature_switch_registry = registry
    registry_module.GROUP_ORDER = PROPOSED_ORDER
    registry_module.GROUP_LABELS = dict(PROPOSED_LABELS)
    features.GROUP_ORDER = PROPOSED_ORDER
    features.GROUP_LABELS = dict(PROPOSED_LABELS)


def _render_main_menu() -> None:
    from src.python.tui.tui_menu import render_menu

    render_menu(0)


def _switches(proposed: bool) -> None:
    if proposed:
        apply_proposed_grouping()
    from src.python.tui.handlers_switch import run_llm_modules_panel

    run_llm_modules_panel()



#: 目标菜单标签（配置组四项；宽度均 ≤ 48，80 列不折行）
PROPOSED_MENU_LABELS = {
    "P": "报告章节（顶层章节取舍与顺序）",
    "S": "分析增强与章节增补（五组 · 含 LLM 章节）",
    "G": "全局设置（目录 / LLM / 指数 / 匿名化）",
}

#: 目标菜单中移出主菜单的键（收进 [G] 二级）
RETIRED_MAIN_KEYS = frozenset({"M", "I", "A"})


def _render_main_menu_proposed() -> None:
    """主菜单目标结构：16 项；`M`/`I`/`A` 收进 `[G]`，`D` 改 `G`。"""
    import src.python.tui.tui_menu as menu

    items = []
    for key, label, cb, is_exit in menu.MENU_ITEMS:
        if key in RETIRED_MAIN_KEYS:
            continue
        new_key = "G" if key == "D" else key
        items.append((new_key, PROPOSED_MENU_LABELS.get(new_key, label), cb, is_exit))
    menu.MENU_ITEMS[:] = items
    menu.MENU_GROUPS[:] = [
        (
            title,
            tuple("G" if k == "D" else k for k in keys if k not in RETIRED_MAIN_KEYS),
        )
        for title, keys in menu.MENU_GROUPS
    ]
    menu.render_menu(0)


def _g_menu_proposed() -> None:
    """`[G]` 二级面板目标结构：标题「全局设置」、提示补全 `C/F/O/L/M`、`[L]` 改称「LLM 设置」。"""
    import src.python.tui.handlers_config as hc
    import src.python.tui.prompt_text as prompt_text
    from src.python.tui.text_layout import style_heading as real_heading

    hc.DIR_INFO_ITEMS.clear()
    hc.DIR_INFO_ITEMS.update(
        {
            "C": ("持仓信息目录", "_cmd_config_dir"),
            "F": ("持仓信息文件名", "_cmd_config_filename"),
            "O": ("报告输出目录", "_cmd_config_output_dir"),
            "L": ("LLM 设置（运行参数 / 多链线路）", "_cmd_config_llm_tuning"),
            "I": ("对比基准指数", "_cmd_config_comparison_indices"),
            "A": ("持仓匿名化（代码 / 名称脱敏）", "_cmd_config_anonymization_mode"),
            "M": ("配置入口地图（各配置项所在菜单）", "_render_config_entry_map"),
        }
    )
    hc.style_heading = lambda text: real_heading(text.replace("配置与目录信息", "全局设置"))
    real_prompt = prompt_text.panel_prompt
    hc.panel_prompt = lambda *a, **kw: real_prompt(*a, **kw).replace("C/F/O/M", "C/F/O/L/I/A/M")
    hc._cmd_config_dir_info()


def _d_llm_proposed() -> None:
    """`[D]` → `[L]` 目标结构：6 个运行参数 + 「多链线路优先级」入口（第 7 项）。"""
    from src.python.config import get_llm_config, get_llm_providers
    from src.python.config.edit_ops import LLM_TUNING_SPECS
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.text_layout import style_heading
    from src.python.tui.tui_keys import input_choice

    llm = get_llm_config() or {}
    providers = [
        p
        for p in (get_llm_providers().get("providers") or [])
        if isinstance(p, dict)
    ]
    providers.sort(key=lambda p: p.get("priority", 99))
    head = str(providers[0].get("name")) if providers else "—"
    keys = list(LLM_TUNING_SPECS)
    line_no = len(keys) + 1

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── LLM 设置 ──"))
        for i, key in enumerate(keys, 1):
            spec = LLM_TUNING_SPECS[key]
            print(f" {nav.marker(i - 1)} {i}. {spec['label']}（当前 {llm.get(key, '—')}）")
        print(f" {nav.marker(len(keys))} {line_no}. 多链线路优先级（{len(providers)} 条，当前链首 {head}）")
        print(f" {nav.marker(len(keys) + 1)} 0. 返回")
        print()
        return []

    items = [PanelItem(str(i), spec["label"], action=lambda: None) for i, spec in enumerate(LLM_TUNING_SPECS.values(), 1)]
    items.append(PanelItem(str(line_no), "多链线路优先级", action=lambda: None))
    items.append(PanelItem("0", "返回", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("输入编号修改", example="7 调多链线路", help_hint=None),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入编号或 0"),
        default_key="0",
    )



def _boards_proposed() -> None:
    """`[P]` 目标结构：只列 5 个顶层章节，底部一行提示指向 `[S]`。"""
    from src.python.config import (
        get_config,
        is_enable_action,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_news,
        is_enable_portfolio_evolution,
    )
    from src.python.tui import handlers_config as hc
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.switch_panel import inner_width, terminal_columns, wrap_hanging
    from src.python.tui.text_layout import display_width, style_heading
    from src.python.tui.tui_keys import input_choice

    config = get_config()
    flags = [
        ("基金深度分析", is_enable_fund_deep_analysis(config)),
        ("市场新闻", is_enable_news(config)),
        ("组合历史走势+回撤", is_enable_history(config)),
        ("组合演进", is_enable_portfolio_evolution(config)),
        ("行动建议", is_enable_action(config)),
    ]
    width = max(display_width(name) for name, _on in flags) + 2

    def _render(nav: NavState) -> list[str]:
        from src.python.tui.text_layout import pad_right

        print()
        print(style_heading("  ── 配置报告可选章节 ──"))
        for i, (name, on) in enumerate(flags):
            status = f"[{'启用' if on else '停用'}]"
            print(f" {nav.marker(i)} {i + 1}. {pad_right(name, width)}{status}")
        print(f" {nav.marker(len(flags))} 0. 返回主菜单")
        for line in wrap_hanging("  提示：章内增强与整章增补见 [S]", inner_width(terminal_columns())):
            print(line)
        print()
        return []

    items = [PanelItem(str(i + 1), name, action=lambda: None) for i, (name, _on) in enumerate(flags)]
    items.append(PanelItem("0", "返回主菜单", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("输入编号切换", example="1-5 切换", help_hint="? 看说明"),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入 0-5"),
        default_key="0",
    )


MODES = {
    "main": _render_main_menu,
    "main_proposed": _render_main_menu_proposed,
    "g_menu_proposed": _g_menu_proposed,
    "d_llm_proposed": _d_llm_proposed,
    "boards_proposed": _boards_proposed,
    "switches": lambda: _switches(False),
    "switches_proposed": lambda: _switches(True),
    "dmenu": lambda: _run("handlers_config", "_cmd_config_dir_info"),
    "boards": lambda: _run("handlers_config", "_cmd_config_report_boards"),
    "indices": lambda: _run("handlers_config", "_cmd_config_comparison_indices"),
    "anon": lambda: _run("handlers_config", "_cmd_config_anonymization_mode"),
    "providers": lambda: _run("handlers_config", "_cmd_config_llm_providers"),
    "dir": lambda: _run("handlers_config", "_cmd_config_dir"),
    "filename": lambda: _run("handlers_config", "_cmd_config_filename"),
    "outdir": lambda: _run("handlers_config", "_cmd_config_output_dir"),
    "tuning": lambda: _run("handlers_config", "_cmd_config_llm_tuning"),
    "refresh": lambda: _run("handlers_config", "_cmd_refresh_config"),
    "cache": lambda: _run("handlers_cache", "_cmd_cache_management"),
    "logs": lambda: _run("handlers_log", "_cmd_view_logs"),
    "health": lambda: _run("handlers_log", "_cmd_view_health_history"),
    "doctor": lambda: _run("handlers_log", "_cmd_run_doctor"),
    "generate": lambda: _run("handlers_report", "_cmd_generate_full"),
    "qa": lambda: _run("handlers_qa", "_cmd_report_qa"),
    "whatif": lambda: _run("handlers_whatif", "_cmd_whatif"),
}


def _run(module: str, func: str) -> None:
    import importlib

    getattr(importlib.import_module(f"src.python.tui.{module}"), func)()


def main() -> int:
    parser = argparse.ArgumentParser(description="TUI 面板渲染取样")
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    args = parser.parse_args()
    MODES[args.mode]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
