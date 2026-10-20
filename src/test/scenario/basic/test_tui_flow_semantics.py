# -*- coding: utf-8 -*-
"""TUI 主路径「击键数 + 屏幕语义」E2E 动线（人因门禁）。

三条动线覆盖用户最常用的三类操作：

1. 生成完整报告且只强刷指定模块——费用决策屏必须说清「重新生成会不会花钱」；
2. 改一个功能开关并确认生效——写盘载荷正确且屏上给「已开启」反馈；
3. 按级别筛日志——筛选条件与结果标题必须同屏可核对。

每条动线同时断言两件事（缺一不可）：
  - **击键数不增**：与 ``tui_flow_contract.json`` 记录一致——优化不得靠加确认屏换语义；
  - **关键语义词上屏**：用户词（重新生成 / 会产生费用 / 已开启 / 级别）必须真的出现，
    否则「语义变好」只是代码注释里的说法。

门禁分层：
  - ``scenario_basic``（P0 快反馈）：仅动线 1（生成主路径）；
  - ``scenario``（P2 回归）：三条全跑。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.test._tui_flow import common_patches, run_flow

# P0（scenario_basic）只跑生成主路径；P2（scenario）三条全跑
pytestmark = [pytest.mark.scenario]

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_FILE = REPO_ROOT / "src" / "test" / "data" / "fixtures" / "tui_flow_contract.json"


def _contract() -> dict:
    return json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))


def _assert_flow(name: str, feeder) -> None:
    """断言击键数与屏幕语义词（两者共用同一份契约快照）。"""
    spec = _contract()[name]
    assert feeder.consumed == spec["keys"], (
        f"动线「{name}」击键数由 {spec['keys']} 变为 {feeder.consumed}——主路径不得变长"
    )
    # 屏幕文本按列折行（空白处断行或超长硬切），语义词比对前两侧同剥空白
    screen = "".join(feeder.output.split())
    missing = [word for word in spec["must_show"] if "".join(word.split()) not in screen]
    assert missing == [], f"动线「{name}」缺少关键语义词 {missing}；实际上屏：\n{feeder.output[-800:]}"


def _report_patches(captured: dict):
    """报告生成编排打桩（不触真实行情/LLM），并把透传参数记进 captured。"""
    from src.python.tui import handlers_report

    def _generate(**kwargs):
        captured.update(kwargs)
        return None

    return [
        patch.object(handlers_report, "prepare_holdings", return_value=([], None, None)),
        patch.object(handlers_report, "forecast_run_cost", return_value={"ok": False}),
        patch.object(
            handlers_report,
            "budget_status",
            return_value={"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False},
        ),
        patch.object(handlers_report.orchestrator, "generate_report", side_effect=_generate),
        patch.object(handlers_report, "finish_report"),
        patch.object(handlers_report, "print_llm_session_usage"),
    ]


@pytest.mark.scenario_basic
class TestGenerateFullWithModuleForce:
    """动线 1：生成完整报告且只重新生成指定模块（P0 快反馈）。"""

    def test_flow_counts_and_cost_semantics(self):
        from src.python.llm.force_scope import FORCEABLE_LLM_MODULES

        captured: dict = {}
        feeder = run_flow(
            ["L", "N", "1 3", "X"],
            pre_patches=common_patches(),
            handler_patches=_report_patches(captured),
        )
        _assert_flow("generate_full_force_modules", feeder)
        assert captured.get("force_llm") is False, "指定模块后不得再置全量重新生成"
        assert captured.get("force_llm_modules") == [FORCEABLE_LLM_MODULES[0], FORCEABLE_LLM_MODULES[2]], (
            f"模块子集解析错误: {captured.get('force_llm_modules')}"
        )


class TestToggleFeatureSwitch:
    """动线 2：改一个功能开关并确认生效（写入载荷 + 屏上反馈）。"""

    def test_flow_counts_and_write_payload(self):
        from src.python.tui import handlers_config

        applied = MagicMock()
        feeder = run_flow(
            ["S", "decision_reflection=on", "0", "X"],
            pre_patches=common_patches(),
            handler_patches=[
                patch("src.python.config.edit_ops.apply_config_edit", applied),
                # 面板读 llm_settings.json：测试环境隔离后路径不存在会令面板提前退出，
                # 故注入确定性配置，保证动线覆盖到开关派发与反馈行
                patch.object(
                    handlers_config,
                    "_read_llm_settings",
                    return_value=({"enabled_llm": {}}, "/tmp/llm_settings.json"),
                ),
                patch.object(handlers_config, "refresh_config"),
            ],
        )
        _assert_flow("toggle_feature_switch", feeder)
        applied.assert_called_once_with({"key": "decision_reflection", "value": True})


class TestFilterLogsByLevel:
    """动线 3：按级别筛日志（筛选条件与结果标题同屏可核对）。"""

    def test_flow_counts_and_level_visible(self):
        from src.python.core.log_reader import LogEntry as _Entry

        entries = [
            _Entry(time="2026-10-20 09:00:00,001", level="ERROR", message="读取行情失败", body="读取行情失败"),
        ]
        read_log = MagicMock(return_value=entries)
        feeder = run_flow(
            ["V", "ERROR", " ", "X"],
            pre_patches=common_patches(),
            handler_patches=[patch("src.python.core.log_reader.read_log", read_log)],
        )
        _assert_flow("filter_logs_by_level", feeder)
        assert read_log.call_args.kwargs["level"] == "ERROR", "级别筛选未透传到核心层"
        assert "读取行情失败" in feeder.output, "筛选结果条目未上屏"


def test_contract_covers_every_flow():
    """契约文件必须恰好覆盖三条动线（新增动线须同步快照，否则数字与人因判据脱节）。"""
    assert set(_contract()) == {"generate_full_force_modules", "toggle_feature_switch", "filter_logs_by_level"}
