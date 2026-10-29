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
    def test_boundary_clears_events_and_carrier_keeps_cross_facts(self, tmp_path):
        """一次报告边界同时成立：事件清空 + 自检载体复位 + 跨报告事实保留。

        这三件事此前分散在三条用例里各自验证；此处按**真实入口** `start_report_run()`
        一次性断言，防止将来只做到其中一两件（例如又在报告边界里重置指纹审计基线）。
        """
        from src.python.llm.self_review import get_self_review_block, set_self_review_block
        from src.python.report._run_scope import start_report_run

        tracker = ds.get_tracker()
        tracker.clear_log()
        tracker.record("price_a", "T2", success=False, failure_type="unreachable")
        counts_before = dict(tracker.get_counts("price_a"))
        set_self_review_block("<p>上一轮自检</p>")

        baseline = start_report_run()

        assert tracker.get_log() == [], "上一轮降级事件不得进入本轮"
        assert tracker.get_counts("price_a") == counts_before, "失败计数属跨报告事实"
        assert get_self_review_block() is None, "上一轮自检区块不得残留"
        assert isinstance(baseline, dict), "必须返回用量基线（供收尾算 delta）"

    def test_resets_cache_hit_rate_counters(self):
        """报告边界重置缓存命中率计数（汇总行与「同前缀未命中」告警都按轮口径）。

        长驻进程（Web/TUI）连跑多份报告时不清零会把「本次命中 X / 未命中 Y」
        累计成进程累计值（实测 5→10→15 递进），告警阈值也随之失真。
        """
        from src.python.cache import get_cache_hit_rate
        from src.python.cache._stats import _record_cache_miss
        from src.python.report._run_scope import start_report_run

        _record_cache_miss("report_datasink_index_600900.SS")
        assert get_cache_hit_rate()["misses"] >= 1

        start_report_run()

        assert get_cache_hit_rate()["misses"] == 0, "报告边界应把命中率计数清零"

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

    def test_keeps_fingerprint_audit_baseline_across_reports(self):
        """报告边界不得清空指纹审计基线：清了它就永远报「无变化」。

        回归：曾把 reset_fingerprint_audit 接进 start_report_run，导致审计失效，
        日志里再也看不到「相对上次报告哪些组件变了」。
        """
        from src.python.llm import generators_orchestrator as go
        from src.python.report._run_scope import start_report_run

        go.reset_fingerprint_audit()
        go._LAST_FP_COMPONENTS = {"totals": "abc"}
        start_report_run()
        assert go._LAST_FP_COMPONENTS == {"totals": "abc"}

    def test_failure_inside_scope_does_not_raise(self, monkeypatch):
        from src.python.report import _run_scope

        monkeypatch.setattr(ds, "get_tracker", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert isinstance(_run_scope.start_report_run(), dict)


class TestUsageDelta:
    def test_delta_subtracts_baseline(self):
        baseline = {"input_tokens": 100, "output_tokens": 20, "call_count": 1, "costs": {"CNY": 0.5}, "per_module": {}}
        current = {
            "input_tokens": 160,
            "output_tokens": 50,
            "cache_hit_tokens": 0,
            "call_count": 3,
            "costs": {"CNY": 0.9},
            "per_module": {"expert_review": {"input_tokens": 60, "output_tokens": 30, "cost": 0.4}},
        }
        delta = _usage_delta(current, baseline)
        assert delta["input_tokens"] == 60
        assert delta["output_tokens"] == 30
        assert delta["call_count"] == 2
        assert delta["costs"]["CNY"] == pytest.approx(0.4)
        assert delta["per_module"]["expert_review"]["input_tokens"] == 60

    def test_record_llm_context_records_per_report_delta(self):
        """perf 里记的是**本份报告**的调用数与费用，不是会话累计（报告级缓存隔离的验收项）。

        会话累计仍要跨报告累计（TUI 退出汇总用），故只能在此处取 delta 写入 perf；
        直接写累计会让第二份报告看起来「又花了第一份的钱」。
        """
        from src.python.report._generation_shared import _record_llm_context
        from src.python.llm import session as session_mod

        baseline = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "call_count": 4,
            "costs": {"CNY": 0.5},
            "per_module": {},
        }
        current = {
            "input_tokens": 1200,
            "output_tokens": 600,
            "cache_hit_tokens": 0,
            "call_count": 5,
            "costs": {"CNY": 0.62},
            "per_module": {"expert_review": {"input_tokens": 200, "output_tokens": 100, "cost": 0.12}},
        }
        recorded: dict = {}

        class _Perf:
            def set_llm_context(self, ctx):
                recorded.update(ctx or {})

        original = session_mod.get_session_usage
        session_mod.get_session_usage = lambda: dict(current)
        try:
            _record_llm_context(_Perf(), baseline=baseline)
        finally:
            session_mod.get_session_usage = original

        assert recorded["call_count"] == 1, "调用数必须是本份报告的增量"
        assert recorded["cost_by_currency"]["CNY"] == pytest.approx(0.12)
        assert recorded["modules"]["expert_review"]["input_tokens"] == 200

    def test_no_baseline_returns_current(self):
        current = {"input_tokens": 10, "per_module": {}}
        assert _usage_delta(current, None) is current
