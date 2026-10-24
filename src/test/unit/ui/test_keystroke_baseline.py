# -*- coding: utf-8 -*-
"""主路径击键数基线 + 动线语义快照（人因指标）。

为什么需要：门禁此前只有「通过/失败」与工程指标（问数、行数），于是交互优化
容易被工程指标带跑——把三问合并成一问（问数 3→1）曾换来「提示像记密码」。
本基线记录**走完一条主路径最少需要几次击键**，任何新增确认屏、新增闸门、
把一键拆成两问的改动都会让它变红。

基线文件：``src/test/data/fixtures/tui_keystroke_baseline.json``
更新方式：确认改动是有意为之且已复核击键数合理后，运行
``TUI_KEYSTROKE_UPDATE=1 .venv/bin/python -m pytest src/test/unit/ui/test_keystroke_baseline.py -q``

击键数与语义的分工：本文件守**击键数不增**（含主菜单 `/` 筛选动线）；
三条动线的**关键语义词必须上屏**由 ``src/test/scenario/basic/test_tui_flow_semantics.py``
守着——两者共用 ``src/test/_tui_flow.py`` 的同一套驱动器，避免打点分叉。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.test._tui_flow import common_patches as _common_patches
from src.test._tui_flow import run_flow as _run_flow

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

REPO_ROOT = Path(__file__).resolve().parents[4]
BASELINE_FILE = REPO_ROOT / "src" / "test" / "data" / "fixtures" / "tui_keystroke_baseline.json"


class TestReaderPatchMatrix:
    """打点矩阵自证：任一读取入口未绑定 feeder 即视为「动线没跑到位」。"""

    def test_detects_unpatched_builtin_input(self):
        """动线打点失效的守卫：局部导入路径只能靠 builtins.input 兜底，缺失必须报出来。"""
        import builtins

        from src.test import _tui_flow

        feeder = _tui_flow.KeyFeeder(["X"])
        with patch.object(builtins, "input", lambda *_args, **_kwargs: ""):
            violations = _tui_flow.validate_reader_patches(feeder)
        assert "builtins.input" in violations

    def test_detects_unpatched_consumer_entry(self):
        """消费方模块的 `input_choice` 被替换成别的实现时同样要报出来。"""
        from src.python.tui import handlers_log
        from src.test import _tui_flow

        feeder = _tui_flow.KeyFeeder(["X"])
        with patch.object(handlers_log, "input_choice", lambda *_args, **_kwargs: ""):
            violations = _tui_flow.validate_reader_patches(feeder)
        assert f"{handlers_log.__name__}.input_choice" in violations


class TestKeystrokeBaseline:
    """主路径的击键数快照。"""

    def _measure_all(self) -> dict[str, int]:
        from src.python.tui import handlers_cache, handlers_config, handlers_report

        flows: dict[str, int] = {}

        # 1) 主菜单 → X 退出
        flows["exit_via_x"] = _run_flow(["X"], pre_patches=_common_patches()).consumed

        # 2) 主菜单 → 0 退出（返回键在首页即退出别名）
        flows["exit_via_zero"] = _run_flow(["0"], pre_patches=_common_patches()).consumed

        # 3) 主菜单 → [S] 功能开关面板 → ?3 看说明（只读路径）→ 0 返回 → X
        #    取只读路径：切换项会写 llm_settings.json，基线采集不得改动用户配置；
        #    面板退出后不再有「按任意键」闸门（短反馈直接回菜单，长输出才设闸门）
        self.write_guard = MagicMock(return_value=False)
        flows["switch_panel_readonly"] = _run_flow(
            ["S", "?3", "0", "X"],
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

        # 4) 主菜单 → [3] 缓存管理 → 0 返回 → X（清理/返回均无闸门）
        flows["cache_panel_return"] = _run_flow(
            ["3", "0", "X"],
            pre_patches=_common_patches(),
            handler_patches=[patch.object(handlers_cache, "_render_cache_stats", return_value=None)],
        ).consumed

        # 5) 主菜单 → [L] → 回车（默认=用已有结果生成）→ 生成（编排打桩，收尾闸门不计）→ X
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

        # 6) 主菜单 → `/` 筛选「缓存」→ [3] 缓存面板 → 0 返回 → 0 清除筛选 → 0 退出
        #    筛选是「少按键找项」的手段，本身不得比直接按 [3] 多出无谓确认
        flows["filter_then_cache_panel"] = _run_flow(
            ["/", "缓存", "3", "0", "0", "0"],
            pre_patches=_common_patches(),
            handler_patches=[patch.object(handlers_cache, "_render_cache_stats", return_value=None)],
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
