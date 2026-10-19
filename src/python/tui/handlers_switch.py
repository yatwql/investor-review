#!/usr/bin/env python3
"""TUI `[S]` 功能开画面板的匹配与详情查询辅助。

`[S]` 面板主循环 ``_cmd_config_llm_modules`` 仍在 ``handlers_config``（大量测试以
``handlers_config.*`` 为 patch 点，本体迁移属独立的域拆分工作）；此处先抽出**无测试
patch 依赖**的纯匹配与详情渲染辅助，朝 switch 面板 handler 域模块演进，并把
``handlers_config`` 行数压回单文件行数红线（≤1000 行）之内。

``show_switch_detail`` 内部按需 import 配置/实验统计（``? 编号/键名`` 查询会取数），
故不并入「只排版不取数」的 ``switch_panel``。
"""

from __future__ import annotations

from src.python.core.ansi_colors import RESET, YELLOW
from src.python.tui.switch_panel import inner_width, terminal_columns, wrap_hanging
from src.python.tui.text_layout import truncate_display

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
    print(truncate_display(f"  ── {name}（{key}）", width))
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
