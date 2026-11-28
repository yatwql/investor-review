"""报告运行边界的观测隔离容错（`report/_run_scope`）。

`start_report_run` / `finish_report_run` 串了十来步跨模块的状态复位与日志。任一步失败
都必须只留 DEBUG —— 观测隔离属旁路，绝不允许把「降级事件没清掉」升级成「报告生成失败」。
本文件逐步骤注入故障，锁住这条容错契约（一次性全挂只测出第一处，故按步参数化）。
"""

from __future__ import annotations

import importlib
import logging
import threading
import time

import pytest

from src.python.report import _run_scope

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

#: (模块路径, 属性名) —— `start_report_run` 内的每一步复位/读取
_START_STEPS = [
    ("src.python.llm.skeleton", "reset_prev_module_cache_keys"),
    ("src.python.core.degradation", "get_tracker"),
    ("src.python.llm.fingerprint", "log_cache_key_salts"),
    ("src.python.cache", "reset_cache_stats"),
    ("src.python.core.rate_limit_state", "reset_push2_limit_state"),
    ("src.python.llm.research_contract", "reset_contract_state"),
    ("src.python.llm.self_review", "reset_self_review"),
    ("src.python.llm.session", "get_session_usage"),
    ("src.python.fetcher.chain_incremental", "reset_run_history_state"),
]


def _boom(*args, **kwargs):
    raise RuntimeError("probe fault")


class TestStartReportRunFaults:
    @pytest.mark.parametrize("module_name,attr", _START_STEPS, ids=[f"{m.split('.')[-1]}.{a}" for m, a in _START_STEPS])
    def test_single_step_failure_does_not_raise(self, module_name, attr, monkeypatch):
        """任一步抛异常 → 边界照常返回基线 dict，报告链不受影响。"""
        from src.python.llm.session import get_session_usage

        monkeypatch.setattr(importlib.import_module(module_name), attr, _boom)

        baseline = _run_scope.start_report_run()

        assert isinstance(baseline, dict)
        if (module_name, attr) == ("src.python.llm.session", "get_session_usage"):
            assert baseline == {}, "会话用量读不到时才退化为空基线"
        else:
            assert baseline == get_session_usage(), f"{attr} 故障泄漏到了用量基线"

    def test_usage_baseline_empty_when_session_read_fails(self, monkeypatch):
        """会话用量读不到时基线退化为空 dict（delta 随之为全量，与引入前行为一致）。"""
        import src.python.llm.session as session_mod

        monkeypatch.setattr(session_mod, "get_session_usage", _boom)

        assert _run_scope.start_report_run() == {}


class TestFinishReportRunFaults:
    def test_perf_save_failure_does_not_raise(self, caplog):
        """台账落盘失败（磁盘满）只丢台账，不影响收尾日志与主流程。"""

        class _FailingPerf:
            def save(self):
                raise OSError("disk full")

        with caplog.at_level(logging.DEBUG, logger="invest"):
            _run_scope.finish_report_run(_FailingPerf())

        assert "耗时台账落盘失败" in caplog.text, "失败痕迹必须留在日志里（便于排查）"

    def test_salt_read_failure_degrades_summary_note(self, monkeypatch):
        """版本盐读不到 → 汇总行不带盐后缀，但汇总本身照打。"""
        import src.python.cache as cache_pkg
        import src.python.llm.fingerprint as fingerprint_mod

        monkeypatch.setattr(fingerprint_mod, "cache_key_salts", _boom)
        captured: dict = {}
        monkeypatch.setattr(cache_pkg, "log_cache_summary", lambda **kwargs: captured.update(kwargs))

        _run_scope.finish_report_run()

        assert captured == {"salts_note": ""}

    def test_cache_summary_failure_does_not_raise(self, monkeypatch, caplog):
        import src.python.cache as cache_pkg

        monkeypatch.setattr(cache_pkg, "log_cache_summary", _boom)

        with caplog.at_level(logging.DEBUG, logger="invest"):
            _run_scope.finish_report_run()

        assert "缓存命中汇总失败" in caplog.text


class TestRunMemo:
    def test_same_key_computed_once(self):
        calls: list[int] = []

        def _factory():
            calls.append(1)
            return {"v": len(calls)}

        _run_scope.clear_run_memo()
        first = _run_scope.run_memo("probe-key", _factory)
        second = _run_scope.run_memo("probe-key", _factory)

        assert first is second
        assert len(calls) == 1, "同轮同键只算一次"

    def test_concurrent_same_key_computes_once(self):
        """并发同键：后到线程等锁后重查一次（否则最坏重复算一遍重 IO）。"""
        started = threading.Event()
        release = threading.Event()
        calls: list[int] = []
        results: list[str] = []

        def _factory():
            calls.append(1)
            started.set()
            release.wait(5)
            return "共享结果"

        def _run():
            results.append(_run_scope.run_memo("probe-concurrent", _factory))

        _run_scope.clear_run_memo()
        first = threading.Thread(target=_run)
        first.start()
        assert started.wait(5)
        second = threading.Thread(target=_run)
        second.start()
        time.sleep(0.05)  # 让第二个线程阻塞在同键锁上
        release.set()
        first.join(5)
        second.join(5)

        assert results == ["共享结果", "共享结果"]
        assert len(calls) == 1, "等锁期间已算完时不得重复执行 factory"

    def test_cleared_between_runs(self):
        _run_scope.clear_run_memo()
        _run_scope.run_memo("probe-key", lambda: "第一轮")

        _run_scope.start_report_run()

        assert _run_scope.run_memo("probe-key", lambda: "第二轮") == "第二轮", "跨轮必须重算"
