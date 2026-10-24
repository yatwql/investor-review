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

#: 辩论两项：作为 `[C]` 中智囊团章的子项（`7.1`/`7.2`），不入任何组
DEBATE_KEYS = ("llm_debate_procon", "llm_debate_conditional")


def apply_panel_grouping() -> None:
    """按设计的 `PANEL_GROUPS` 注入分组视图（仅内存态，不写任何配置文件）。

    - `[S]` 只渲染 analysis / presentation / mechanism 三组；
    - 默认关闭的整章（standalone）归 `[C]`，不在 `[S]` 出现；
    - 辩论两项作为 `[C]` 中智囊团章的子项，不入任何组。
    """
    import dataclasses

    import src.python.config._feature_registry as registry_module
    import src.python.config.features as features
    import src.python.tui.handlers_config as hc

    registry = {
        flag: d
        for flag, d in registry_module.feature_switch_registry.items()
        if flag not in DEBATE_KEYS and flag != "doctor_check"
    }
    regroup = {
        "cost_position": "portfolio", "fund_purchase_limit": "portfolio",
        "cost_lots": "portfolio", "risk_adjusted_excess": "portfolio",
        "market_temperature": "market", "valuation_percentile": "market",
        "prosperity_framework": "market", "crisis_replay": "market",
        "candidate_compare": "fund_style", "industry_beta": "fund_style",
        "factor_catalog": "fund_style",
        "event_window_impact": "event_summary", "market_sentiment": "event_summary",
        "data_quality": "event_summary", "summary_highlights": "event_summary",
    }
    for flag, group in regroup.items():
        if flag in registry:
            registry[flag] = dataclasses.replace(registry[flag], group=group)
    if "report_qa" in registry:
        registry["report_qa"] = dataclasses.replace(registry["report_qa"], group="presentation")
    registry_module.feature_switch_registry = registry
    features.feature_switch_registry = registry
    order = ("portfolio", "market", "fund_style", "event_summary", "presentation", "mechanism")
    registry_module.GROUP_LABELS = {
        "portfolio": "💼 持仓与交易（成本、申赎状态、成本收益、风险调整）",
        "market": "📈 市场与估值（温度、估值分位、景气度、危机回放）",
        "fund_style": "🧩 基金与风格（候选比较、行业 Beta、因子目录）",
        "event_summary": "📰 事件与摘要（事件窗、情绪热点、数据质量、本期要点）",
        "presentation": "🧭 呈现与交互（图表轴值 / 报告页追问）",
        "mechanism": "⚙ 机制与质量（提示词注入 / 输出评级）",
    }
    features.GROUP_LABELS = dict(registry_module.GROUP_LABELS)
    registry_module.GROUP_ORDER = order
    features.GROUP_ORDER = order
    # 面板内不再有 LLM 模块块
    hc.filter_menu_llm_modules = lambda _names: {}
    # 面板横幅改为与目标语义一致（真实实现会同步改字面量）
    import src.python.tui.handlers_switch as hs

    real_wrap = hs.wrap_hanging
    hs.wrap_hanging = lambda text, *a, **k: real_wrap(
        text.replace(
            "基础报告章节组（基金深度分析/市场新闻/历史走势+回撤/组合演进/行动建议）在菜单 [C] 配置",
            "章节显隐与整章开关见 [C]；本面板为报告内的呈现与增强内容",
        ),
        *a,
        **k,
    )
    real_panel = hs.render_panel
    hs.render_panel = lambda title, rows=(), **kw: real_panel(
        title.replace("配置 LLM 报告章节与功能开关", "报告章节内容呈现"), rows, **kw
    )



#: 目标菜单标签（配置组四项）
PROPOSED_MENU_LABELS = {
    "P": "报告章节显隐（顶层 / LLM / 整章 / 关联产物）",
    "S": "报告章节内容呈现",
    "G": "全局设置（目录 / LLM / 指数 / 匿名化 / 索引）",
}

#: 目标菜单中移出主菜单的键（M/I/A 收进 [G]；V/H/T 收进 [D]）
RETIRED_MAIN_KEYS = frozenset({"M", "I", "A", "V", "H", "T"})

#: 诊断与排查一级入口
DIAG_ITEM = ("D", "诊断与排查（设置 / 日志 / 健康 / 自检）", None, False)


def _render_main_menu() -> None:
    from src.python.tui.tui_menu import render_menu

    render_menu(0)


def _switches(proposed: bool) -> None:
    if proposed:
        apply_panel_grouping()
    from src.python.tui.handlers_switch import run_llm_modules_panel

    run_llm_modules_panel()


def _render_main_menu_proposed() -> None:
    """主菜单设计结构：16 项；`M`/`I`/`A` 收进 `[G]`，`D` 改 `G`。"""
    import src.python.tui.tui_menu as menu

    items = []
    diag_inserted = False
    for key, label, cb, is_exit in menu.MENU_ITEMS:
        if key == "V" and not diag_inserted:
            items.append(DIAG_ITEM)
            diag_inserted = True
        if key in RETIRED_MAIN_KEYS:
            continue
        new_key = "G" if key == "D" else key
        items.append((new_key, PROPOSED_MENU_LABELS.get(new_key, label), cb, is_exit))
    menu.MENU_ITEMS[:] = items
    groups: list[tuple[str, tuple[str, ...]]] = []
    for title, keys in menu.MENU_GROUPS:
        if title == "诊断与排查":
            groups.append((title, ("D",)))
            continue
        groups.append((title, tuple("G" if k == "D" else k for k in keys if k not in RETIRED_MAIN_KEYS)))
    menu.MENU_GROUPS[:] = groups
    menu.render_menu(0)


def _g_menu_proposed() -> None:
    """`[G]` 二级设计结构：按键位分组排版（目录与文件 / LLM 调优 / 基准与脱敏 / 索引）。"""
    from src.python.tui import handlers_config as hc
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.text_layout import style_heading
    from src.python.tui.tui_keys import input_choice

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "目录与文件",
            [
                ("H", "持仓信息目录"),
                ("F", "持仓信息文件名"),
                ("O", "报告输出目录"),
            ],
        ),
        ("LLM 调优", [("L", "LLM 设置（运行参数 / 多链线路）")]),
        ("基准与脱敏", [("I", "对比基准指数"), ("A", "持仓匿名化（代码 / 名称脱敏）")]),
        ("索引", [("M", "配置入口地图（各配置项所在菜单）")]),
    ]
    flat = [item for _title, items in groups for item in items]

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 全局设置 ──"))
        idx = 0
        for title, items in groups:
            print("     " + style_heading(f"── {title} ──"))
            for key, label in items:
                print(f" {nav.marker(idx)}     {idx + 1} [{key}] {label}")
                idx += 1
        print(f" {nav.marker(idx)}     0 返回主菜单")
        print()
        return []

    def _noop() -> None:
        return None

    items = [PanelItem(key, label, action=_noop) for key, label in flat]
    items.append(PanelItem("0", "返回主菜单", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("选择", example="1 或 C", help_hint=None),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入编号 1-7 或字母 D/F/O/L/I/A/M（0 返回）"),
        default_key="0",
    )


def _d_llm_proposed() -> None:
    """`[D]` → `[L]` 设计结构：6 个运行参数 + 「多链线路优先级」入口（第 7 项）。"""
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
        print(f" {nav.marker(len(keys) + 1)} 0. 返回全局设置")
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
    """`[C]` 设计结构：16 项四块（顶层 5 / LLM 7 / 默认关闭的整章 3 / 关联产物 1）+ 智囊团下 7.1/7.2 子项。"""
    from src.python.config import (
        get_config,
        get_llm_config,
        is_enable_action,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_news,
        is_enable_portfolio_evolution,
    )
    from src.python.config.features import is_feature_enabled, switches_in_group
    from src.python.core.registry import get_llm_module_names
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.switch_panel import inner_width, terminal_columns, wrap_hanging
    from src.python.tui.text_layout import display_width, pad_right, style_heading
    from src.python.tui.tui_keys import input_choice

    config = get_config()
    enabled_llm = (get_llm_config() or {}).get("enabled_llm") or {}
    top = [
        ("基金深度分析", is_enable_fund_deep_analysis(config)),
        ("市场新闻", is_enable_news(config)),
        ("组合历史走势+回撤", is_enable_history(config)),
        ("组合演进", is_enable_portfolio_evolution(config)),
        ("行动建议", is_enable_action(config)),
    ]
    modules = [(name, bool(enabled_llm.get(sfx, True))) for sfx, name in get_llm_module_names().items()]
    standalone = [(flag, d.label, is_feature_enabled(flag)) for flag, d in switches_in_group("standalone")]
    related_keys = {"whatif_trade_cost"}
    chapters = [(label, on) for flag, label, on in standalone if flag not in related_keys]
    related = [(label, on) for flag, label, on in standalone if flag in related_keys]
    from src.python.config.features import feature_switch_registry

    debate = [
        (feature_switch_registry[flag].label, is_feature_enabled(flag))
        for flag in DEBATE_KEYS
    ]
    width = max(
        display_width(name) for name, _on in top + modules + chapters + related + debate
    ) + 2
    expert_on = bool(enabled_llm.get("expert_review", True))

    def _row(nav: NavState, idx: int, number: str, name: str, on: bool, *, sub: bool = False) -> str:
        status = f"[{'启用' if on else '关闭'}]"
        marker = nav.marker(idx)
        prefix = "      " if sub else ""
        tail = " " if sub else ". "
        return f" {marker}{prefix}{number}{tail}{pad_right(name, width)}{status}"

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 报告章节 ──"))
        idx = 0
        blocks = [
            ("顶层章节", top, 1),
            ("LLM 章节", modules, len(top) + 1),
            ("默认关闭的整章", chapters, len(top) + len(modules) + 1),
            ("关联产物", related, len(top) + len(modules) + len(chapters) + 1),
        ]
        for title, items, start in blocks:
            print("   " + style_heading(f"── {title} ──"))
            for offset, (name, on) in enumerate(items):
                number = str(start + offset)
                row_text = _row(nav, idx, number, name, on)
                if title == "关联产物":
                    row_text += "（仅调仓模拟报告）"
                print(row_text)
                idx += 1
                if title == "LLM 章节" and name == "智囊团深度复盘":
                    for j, (dname, don) in enumerate(debate, 1):
                        print(_row(nav, idx, f"7.{j}", dname, don and expert_on, sub=True))
                        idx += 1
        print(f" {nav.marker(idx)} 0. 返回主菜单")
        for line in wrap_hanging("  章节内追加的内容（因子目录/估值分位等）见 [S]", inner_width(terminal_columns())):
            print(line)
        print()
        return []

    items: list[PanelItem] = [
        PanelItem(str(i), name, action=lambda: None)
        for i, (name, _on) in enumerate(top + modules + chapters + related, 1)
    ]
    items.append(PanelItem("7.1", "辩论-正反辩论", action=lambda: None))
    items.append(PanelItem("7.2", "辩论-条件推理", action=lambda: None))
    items.append(PanelItem("0", "返回主菜单", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("输入编号切换章节", example="7.1 切辩论", help_hint="?7 看说明"),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入编号或 0"),
        default_key="0",
    )


def _d_diag_proposed() -> None:
    """`[D]` 二级设计结构：诊断入口聚合（运行日志 / 健康历史 / 系统自检）。"""
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.text_layout import style_heading
    from src.python.tui.tui_keys import input_choice

    groups = [
        ("L", "日志设置（级别 / 轮转 / 查看器）"),
        ("V", "运行日志（可按级别筛选）"),
        ("H", "数据源健康历史"),
        ("T", "系统自检（环境 / 配置 / 目录 / 数据源）"),
    ]

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 诊断与排查 ──"))
        for i, (key, label) in enumerate(groups):
            print(f" {nav.marker(i)} {i + 1} [{key}] {label}")
        print(f" {nav.marker(len(groups))} 0 返回主菜单")
        print()
        return []

    def _noop() -> None:
        return None

    items = [PanelItem(key, label, action=_noop) for key, label in groups]
    items.append(PanelItem("0", "返回主菜单", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("选择", example="1 或 L", default="4 系统自检", help_hint=None),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入编号 1-4 或字母 L/V/H/T（0 返回）"),
        default_key="0",
    )


def _d_log_proposed() -> None:
    """`[D]`→`[L]` 三级设计结构：日志设置（6 项，数字编号）。"""
    from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
    from src.python.tui.prompt_text import panel_prompt
    from src.python.tui.text_layout import pad_right, style_heading
    from src.python.tui.tui_keys import input_choice

    rows = [
        ("写盘级别", "INFO"),
        ("控制台级别", "INFO"),
        ("单文件上限 MB", "10"),
        ("备份份数", "5"),
        ("查看器默认级别", "INFO"),
        ("查看器首屏行数", "500"),
    ]
    width = max(len(k) * 2 for k, _v in rows) + 2

    def _render(nav: NavState) -> list[str]:
        print()
        print(style_heading("  ── 日志设置 ──"))
        for i, (label, value) in enumerate(rows, 1):
            print(f" {nav.marker(i - 1)} {i}. {pad_right(label, width)}（当前 {value}）")
        print(f" {nav.marker(len(rows))} 0. 返回诊断与排查")
        print()
        return []

    def _noop() -> None:
        return None

    items = [PanelItem(str(i), label, action=_noop) for i, (label, _v) in enumerate(rows, 1)]
    items.append(PanelItem("0", "返回诊断与排查", kind="return"))
    panel_loop(
        items,
        render=_render,
        prompt=panel_prompt("输入编号修改", example="1 改写盘级别", help_hint=None),
        read=input_choice,
        on_text=lambda _t: print("  [!] 无效选择，请输入编号或 0"),
        default_key="T",
    )


MODES = {
    "main": _render_main_menu,
    "main_proposed": _render_main_menu_proposed,
    "g_menu_proposed": _g_menu_proposed,
    "d_diag_proposed": _d_diag_proposed,
    "d_log_proposed": _d_log_proposed,
    "d_llm_proposed": _d_llm_proposed,
    "boards_proposed": _boards_proposed,
    "switches": lambda: _switches(False),
    "switches_proposed": lambda: _switches(True),
    "dmenu": lambda: _run("handlers_config", "_cmd_global_settings"),
    "entrymap": lambda: _run("handlers_config", "_render_config_entry_map"),
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
