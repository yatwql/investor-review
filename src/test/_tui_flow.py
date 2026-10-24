# -*- coding: utf-8 -*-
"""TUI 动线驱动骨架（击键数基线与 E2E 动线语义断言共用）。

为什么抽成共享设施：击键数基线与「动线语义」两类断言必须驱动**同一条**动线——
两份各写一份驱动器，迟早在打点范围/退出处理上分叉，届时「击键没变但语义丢了」
这类回归就检不出来。

边界说明：计数从**主菜单进入**到**该动线结束**，不含报告生成内部与退出提示；
每条动线的最短击键序列即其可执行规格，序列耗尽即视为「主路径变长」。
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from unittest.mock import patch

__all__ = ["KeyFeeder", "run_flow", "common_patches", "validate_reader_patches"]


class KeyFeeder:
    """按脚本喂键并计数；序列耗尽即断言「主路径变长」。"""

    def __init__(self, keys: list[str]):
        self._keys = list(keys)
        self.consumed = 0
        self.prompts: list[str] = []
        self.output = ""  # 动线期间的全部上屏文本（语义断言用）

    def __call__(self, prompt: str = "", **_kw) -> str:
        if not self._keys:
            raise AssertionError(
                f"击键序列已耗尽（已消费 {self.consumed} 键）——主路径变长或新增了确认屏；已记录的提示语：{self.prompts}"
            )
        self.prompts.append(prompt)
        self.consumed += 1
        return self._keys.pop(0)


def _patch_readers(feeder: KeyFeeder):
    """把按键读取入口替换为 feeder。

    打点纪律（踩过一次坑）：**不得** patch 源头 ``tui_keys.input_choice``——
    处理器模块在流程中被惰性导入，导入期读到的若是 feeder 就会永久绑定，
    污染后续所有用例。故只 patch「已导入的消费方」与 ``get_key`` 源头；
    主菜单筛选关键词走 ``tui._read_filter_keyword`` 这一个可替换入口。
    """
    from src.python.tui import (
        handlers_cache,
        handlers_config,
        handlers_log,
        handlers_qa,
        handlers_report,
        handlers_whatif,
        panel_runtime,
        tui,
        tui_keys,
        tui_menu,
        tui_handlers,
    )

    patches = []
    # get_key 是 input_choice 的内部读取入口（同模块动态查找）→ patch 源头即可覆盖两者
    for mod in (tui, tui_menu, tui_keys):
        if hasattr(mod, "get_key"):
            patches.append(patch.object(mod, "get_key", feeder))
    # 消费方逐个 patch（这些模块已在测试导入期完成导入，绑定固定）
    consumers = (
        panel_runtime,
        tui_handlers,
        handlers_report,
        handlers_config,
        handlers_cache,
        handlers_log,
        handlers_qa,
        handlers_whatif,
    )
    for mod in consumers:
        if hasattr(mod, "input_choice"):
            patches.append(patch.object(mod, "input_choice", feeder))
    if hasattr(tui, "_read_filter_keyword"):
        patches.append(patch.object(tui, "_read_filter_keyword", lambda _prompt="": feeder(_prompt)))
    # 兜底：`input_choice` 在非 TTY 下退化为内置 `input()`，而部分处理器在函数内
    # `from tui_keys import input_choice`（局部导入绕不过模块属性 patch）——只有替换
    # `input` 本身才能覆盖这类路径，且不产生「源头被永久绑定」的跨用例污染。
    # 必须把 feeder 本身放进去（而非包一层 lambda）：`validate_reader_patches`
    # 靠同一性判定「打点确实生效」。
    patches.append(patch("builtins.input", feeder))
    return patches


def validate_reader_patches(feeder: KeyFeeder) -> list[str]:
    """打点矩阵自证：返回未绑定到 feeder 的读取入口（空清单 = 全部命中）。

    守住一类静默失效：处理器在函数内 `from tui_keys import input_choice` 时，
    模块属性 patch 不生效，动线会去读真实 stdin（或静默错位）——用例看似在跑，
    实际没走到目标处理器。跑动线前先验证每个已暴露的读取入口都指向 feeder，
    并在后续任何时候删除兜底/消费方登记时立即变红。
    """
    import builtins

    from src.python.tui import (
        handlers_cache,
        handlers_config,
        handlers_log,
        handlers_qa,
        handlers_report,
        handlers_whatif,
        panel_runtime,
        tui,
        tui_handlers,
        tui_keys,
        tui_menu,
    )

    violations: list[str] = []
    if builtins.input is not feeder:
        violations.append("builtins.input")
    consumers = (
        panel_runtime,
        tui_handlers,
        handlers_report,
        handlers_config,
        handlers_cache,
        handlers_log,
        handlers_qa,
        handlers_whatif,
    )
    for mod in consumers:
        if hasattr(mod, "input_choice") and mod.input_choice is not feeder:
            violations.append(f"{mod.__name__}.input_choice")
    for mod in (tui, tui_menu, tui_keys):
        if hasattr(mod, "get_key") and mod.get_key is not feeder:
            violations.append(f"{mod.__name__}.get_key")
    return violations


def common_patches():
    """屏蔽与交互无关的体量：帧渲染、启动副作用、退出统计。"""
    from src.python.tui import tui

    return [
        patch.object(tui, "_render_menu_frame", return_value=0),
        patch.object(tui, "init_config"),
        patch.object(tui, "_apply_feature_gates"),
        patch.object(tui, "_print_session_usage_on_exit"),
        patch("src.python.cache.cleanup_expired", return_value=0),
        patch("src.python.report.privacy_notice.show_privacy_notice_if_needed"),
        patch("src.python.startup_wizard.show_startup_wizard_if_needed"),
    ]


def run_flow(keys: list[str], *, pre_patches=(), handler_patches=()) -> KeyFeeder:
    """驱动主循环走完一条动线，返回 feeder（含消费数与上屏提示语）。"""
    from src.python.tui import tui
    from src.python.tui.tui_menu import MENU_ITEMS

    feeder = KeyFeeder(keys)
    snapshot = list(MENU_ITEMS)  # 主循环会按功能开关就地裁剪菜单，跑完必须还原
    ctxs = [p for p in _patch_readers(feeder)] + list(pre_patches) + list(handler_patches)
    entered = []
    try:
        for ctx in ctxs:  # 显式进入/退出：ExitStack 在 unittest 与 pytest 混跑时曾遗留激活中的打点
            ctx.__enter__()
            entered.append(ctx)
        violations = validate_reader_patches(feeder)
        if violations:
            raise AssertionError("TUI 动线打点未生效（局部导入会绕过模块属性 patch）：" + "、".join(violations))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with contextlib.suppress(SystemExit):
                tui.main()
        feeder.output = out.getvalue()
    finally:
        for ctx in reversed(entered):
            with contextlib.suppress(RuntimeError):
                ctx.__exit__(None, None, None)
        MENU_ITEMS[:] = snapshot
    if os.environ.get("TUI_KEYSTROKE_DEBUG") == "1":
        print(f"[keystroke] 消费 {feeder.consumed} 键，剩余 {feeder._keys}，提示 {feeder.prompts}", file=sys.stderr)
    return feeder
