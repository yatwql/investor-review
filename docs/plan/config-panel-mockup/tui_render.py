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


MODES = {
    "main": _render_main_menu,
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
