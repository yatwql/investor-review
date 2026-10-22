"""LLM 总时间预算闸（`make_budget_guard`）。

背景：日志审计发现一次 full 运行 LLM+新闻阶段耗时 6,623s（正常中位 150s）——
单模块卡住 + 重试叠加会把一次报告拖成小时级。预算闸在**每个模块启动前**检查
已用时长，超预算跳过余下模块（不打断在跑的），整套行为可脱离线程池单测。
"""

from __future__ import annotations

import logging

import pytest

from src.python.llm._llm_dispatch import make_budget_guard

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestBudgetGuard:
    def test_zero_budget_never_blocks(self):
        """预算 0 = 不启用（默认），任何时刻都放行。"""
        guard = make_budget_guard(0, 0.0, [], {}, clock=lambda: 10**6)
        assert guard("global_macro", lambda: ("内容", False))() == ("内容", False)

    def test_within_budget_runs_module(self):
        guard = make_budget_guard(60, 0.0, [], {}, clock=lambda: 59.9)
        called = []
        guard("global_macro", lambda: called.append(1) or ("内容", True))()
        assert called == [1]

    def test_over_budget_skips_and_records(self, caplog):
        skipped: list[str] = []
        guard = make_budget_guard(60, 0.0, skipped, {"expert_review": "智囊团深度复盘"}, clock=lambda: 61.0)
        with caplog.at_level(logging.WARNING, logger="invest"):
            result = guard("expert_review", lambda: ("不该被调用", True))()
        assert result == (None, False)
        assert skipped == ["expert_review"]
        message = caplog.records[-1].getMessage()
        assert "预算已用尽" in message
        assert "智囊团深度复盘" in message
        # 日志回显纪律：提示调参时同时给出当前预算值
        assert "60s" in message
