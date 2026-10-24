"""报告运行边界（`report/_run_scope`）与用量基线回归。

缺陷背景：同一非交易日、同持仓、新闻缓存命中的连续两次报告，LLM 模块全部
缓存 miss。原因是把**上一轮自己产生**的状态带进了下一轮：
  - 降级事件日志是会话级累积，上一轮告警进入本轮数据质量块 → 指纹变化
  - 自检载体未清空，本轮未产出时仍可能复用旧内容
  - 会话用量是累计值，第二份报告 perf 里 token/调用数看起来翻倍
"""

from __future__ import annotations

import pytest

from src.python.report import data_status as ds
from src.python.report._generation_shared import _usage_delta

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestBeginReportClearsEvents:
    def test_begin_report_clears_log_but_keeps_counts(self, tmp_path):
        tracker = ds.DegradationTracker(persist_path=str(tmp_path / "degradation.json"))
        tracker.record("price_a", "T2", success=False, failure_type="unreachable")
        assert tracker.get_log()
        before = tracker.get_counts("price_a")

        tracker.begin_report()

        assert tracker.get_log() == [], "上一轮事件不得进入本轮数据质量块"
        assert tracker.get_counts("price_a") == before, "失败计数是跨报告事实，必须保留"

    def test_begin_report_keeps_last_success(self, tmp_path):
        tracker = ds.DegradationTracker(persist_path=str(tmp_path / "degradation.json"))
        tracker.record("price_a", "T2", success=True)
        assert "price_a" in tracker._last_success
        tracker.begin_report()
        assert "price_a" in tracker._last_success, "跨会话成功时间戳不得被报告边界清掉"


class TestStartReportRun:
    def test_resets_self_review_carrier(self):
        from src.python.llm.self_review import get_self_review_block, set_self_review_block
        from src.python.report._run_scope import start_report_run

        set_self_review_block("<p>上一轮自检</p>")
        start_report_run()
        assert get_self_review_block() is None

    def test_returns_usage_baseline_snapshot(self):
        from src.python.llm.session import get_session_usage, reset_session_usage
        from src.python.report._run_scope import start_report_run

        reset_session_usage()
        baseline = start_report_run()
        assert baseline["call_count"] == get_session_usage()["call_count"]

    def test_failure_inside_scope_does_not_raise(self, monkeypatch):
        from src.python.report import _run_scope

        monkeypatch.setattr(ds, "get_tracker", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert isinstance(_run_scope.start_report_run(), dict)


class TestUsageDelta:
    def test_delta_subtracts_baseline(self):
        baseline = {"input_tokens": 100, "output_tokens": 20, "call_count": 1, "total_cost": 0.5, "per_module": {}}
        current = {
            "input_tokens": 160,
            "output_tokens": 50,
            "cache_hit_tokens": 0,
            "call_count": 3,
            "total_cost": 0.9,
            "per_module": {"expert_review": {"input_tokens": 60, "output_tokens": 30, "cost": 0.4}},
        }
        delta = _usage_delta(current, baseline)
        assert delta["input_tokens"] == 60
        assert delta["output_tokens"] == 30
        assert delta["call_count"] == 2
        assert delta["total_cost"] == pytest.approx(0.4)
        assert delta["per_module"]["expert_review"]["input_tokens"] == 60

    def test_no_baseline_returns_current(self):
        current = {"input_tokens": 10, "per_module": {}}
        assert _usage_delta(current, None) is current
