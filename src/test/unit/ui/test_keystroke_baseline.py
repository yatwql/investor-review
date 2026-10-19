# -*- coding: utf-8 -*-
"""主路径击键数基线（人因指标快照）。

为什么需要：门禁此前只有「通过/失败」与工程指标（问数、行数），于是交互优化
容易被工程指标带跑——把三问合并成一问（问数 3→1）曾换来「提示像记密码」。
本基线记录**走完一条主路径最少需要几次击键**，任何新增确认屏、新增闸门、
把一键拆成两问的改动都会让它变红。

基线文件：``src/test/data/fixtures/tui_keystroke_baseline.json``
更新方式：确认改动是有意为之且已复核击键数合理后，运行
``TUI_KEYSTROKE_UPDATE=1 .venv/bin/python -m pytest src/test/unit/ui/test_keystroke_baseline.py -q``

边界说明：计数从**主菜单进入**到**该动线结束**，不含报告生成内部与退出提示；
每条动线的最短击键序列即其可执行规格，序列耗尽即视为「主路径变长」。
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

REPO_ROOT = Path(__file__).resolve().parents[4]
BASELINE_FILE = REPO_ROOT / "src" / "test" / "data" / "fixtures" / "tui_keystroke_baseline.json"


class _KeyFeeder:
    """按脚本喂键并计数；序列耗尽即断言「主路径变长」。"""

    def __init__(self, keys: list[str]):
        self._keys = list(keys)
        self.consumed = 0
        self.prompts: list[str] = []

    def __call__(self, prompt: str = "", **_kw) -> str:
        if not self._keys:
            raise AssertionError(
                f"击键序列已耗尽（已消费 {self.consumed} 键）——主路径变长或新增了确认屏；已记录的提示语：{self.prompts}"
            )
        self.prompts.append(prompt)
        self.consumed += 1
        return self._keys.pop(0)


def _patch_readers(feeder: _KeyFeeder):
    """把所有按键读取入口替换为 feeder（各模块按名导入，需逐模块打点）。"""
    from src.python.tui import (
        handlers_cache,
        handlers_config,
        handlers_report,
        panel_runtime,
        tui,
        tui_keys,
        tui_menu,
    )

    patches = []
    for mod in (tui, tui_menu, tui_keys):
        if hasattr(mod, "get_key"):
            patches.append(patch.object(mod, "get_key", feeder))
    for mod in (tui_keys, panel_runtime, handlers_report, handlers_config, handlers_cache):
        if hasattr(mod, "input_choice"):
            patches.append(patch.object(mod, "input_choice", feeder))
    return patches


def _run_flow(keys: list[str], *, pre_patches=(), handler_patches=()) -> _KeyFeeder:
    """驱动主循环走完一条动线，返回 feeder（含消费数）。"""
    from src.python.tui import tui

    feeder = _KeyFeeder(keys)
    ctxs = [p for p in _patch_readers(feeder)] + list(pre_patches) + list(handler_patches)
    with contextlib.ExitStack() as stack:
        for ctx in ctxs:
            stack.enter_context(ctx)
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.suppress(SystemExit):
                tui.main()
    if os.environ.get("TUI_KEYSTROKE_DEBUG") == "1":
        print(f"[keystroke] 消费 {feeder.consumed} 键，剩余 {feeder._keys}，提示 {feeder.prompts}", file=sys.stderr)
    return feeder


def _common_patches():
    """屏蔽与交互无关的体量：帧渲染、启动副作用、退出统计。"""
    from src.python.tui import tui

    return [
        patch.object(tui, "_render_menu_frame", return_value=0),
        patch.object(tui, "init_config"),
        patch.object(tui, "_print_session_usage_on_exit"),
        patch("src.python.cache.cleanup_expired", return_value=0),
        patch("src.python.report.privacy_notice.show_privacy_notice_if_needed"),
        patch("src.python.startup_wizard.show_startup_wizard_if_needed"),
    ]


class TestKeystrokeBaseline(unittest.TestCase):
    """三条主路径的击键数快照。"""

    def _measure_all(self) -> dict[str, int]:
        from src.python.tui import handlers_cache, handlers_config, handlers_report

        flows: dict[str, int] = {}

        # 1) 主菜单 → X 退出
        flows["exit_via_x"] = _run_flow(["X"], pre_patches=_common_patches()).consumed

        # 2) 主菜单 → 0 退出（返回键在首页即退出别名）
        flows["exit_via_zero"] = _run_flow(["0"], pre_patches=_common_patches()).consumed

        # 3) 主菜单 → [S] 功能开关面板 → ?3 看说明（只读路径）→ 0 返回 → 任意键 → X
        #    取只读路径：切换项会写 llm_settings.json，基线采集不得改动用户配置
        self.write_guard = MagicMock(return_value=False)
        flows["switch_panel_readonly"] = _run_flow(
            ["S", "?3", "0", " ", "X"],
            pre_patches=_common_patches(),
            handler_patches=[
                patch.object(handlers_config, "_apply_edit", self.write_guard),
                # 面板读 llm_settings.json：测试环境隔离后路径不存在会令面板提前退出，
                # 故注入确定性配置，保证动线覆盖到面板提示与只读命令
                patch.object(
                    handlers_config,
                    "_read_llm_settings",
                    return_value=({"enabled_llm": {}}, "/tmp/llm_settings.json"),
                ),
                patch.object(handlers_config, "refresh_config"),
            ],
        ).consumed

        # 4) 主菜单 → [3] 缓存管理 → 0 返回 → 任意键 → X
        flows["cache_panel_return"] = _run_flow(
            ["3", "0", " ", "X"],
            pre_patches=_common_patches(),
            handler_patches=[patch.object(handlers_cache, "_render_cache_stats", return_value=None)],
        ).consumed

        # 5) 主菜单 → [L] → 回车（默认=用缓存生成）→ 生成（编排打桩，收尾闸门不计）→ X
        flows["generate_full_default_path"] = _run_flow(
            ["L", "", "X"],
            pre_patches=_common_patches(),
            handler_patches=[
                patch.object(handlers_report, "prepare_holdings", return_value=([], None, None)),
                patch.object(handlers_report, "forecast_run_cost", return_value={"ok": False}),
                patch.object(
                    handlers_report,
                    "budget_status",
                    return_value={"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False},
                ),
                patch.object(handlers_report.orchestrator, "generate_report", return_value=None),
                patch.object(handlers_report, "finish_report"),
                patch.object(handlers_report, "print_llm_session_usage"),
            ],
        ).consumed
        return flows

    def test_baseline_collection_never_writes_user_config(self):
        """基线采集必须只读：切换类动线一律走只读路径，写入口恒不被触达。

        守护理由：``data/config/llm_settings.json`` 不在 conftest 隔离范围内，
        基线用例若真按了切换键，会静默改写用户真实配置（实测已发生过一次）。
        """
        self._measure_all()
        assert not self.write_guard.called, "基线采集触发了配置写入（必须改走只读路径）"

    def test_flows_match_recorded_baseline(self):
        """主路径击键数与基线一致（变红即意味着用户多按了键或少了一步提示）。"""
        measured = self._measure_all()
        if os.environ.get("TUI_KEYSTROKE_UPDATE") == "1":
            BASELINE_FILE.write_text(json.dumps(measured, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            pytest.skip("基线已按当前实现重写（TUI_KEYSTROKE_UPDATE=1）")

        assert BASELINE_FILE.is_file(), f"击键基线缺失: {BASELINE_FILE}"
        recorded = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        assert set(measured) == set(recorded), f"动线集合不一致: 实测 {set(measured)} vs 基线 {set(recorded)}"
        drift = {k: (recorded[k], measured[k]) for k in measured if recorded[k] != measured[k]}
        assert not drift, f"主路径击键数偏离基线（基线, 实测）: {drift}"
