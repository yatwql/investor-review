"""报告健康检查收口的容错（`report/_report_health`）。

健康检查是**非关键旁路**：启动失败、结果形状不对、结果收集失败都只能留 INFO 日志，
绝不能让报告生成因「数据源体检没跑起来」而失败。本文件锁这条契约的每个出口。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.report import _report_health

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_report,
    # 健康检查探针会起线程真实体检（网络 + akshare）：用例验的是收口容错，
    # 取数本身不是测试目标，统一挂离线桩（失败即刻返回，不再等真网络）
    pytest.mark.usefixtures("offline_external_sources"),
]


class _Future:
    def __init__(self, value=None, *, error: Exception | None = None) -> None:
        self._value = value
        self._error = error

    def result(self, timeout=None):
        if self._error is not None:
            raise self._error
        return self._value


class TestSpawn:
    def test_start_failure_returns_none(self, monkeypatch, caplog):
        """健康检查启动失败（线程池不可用）→ None + INFO，报告照常继续。"""
        import src.python.core.check_sources as check_sources

        monkeypatch.setattr(check_sources, "run_health_checks", lambda: [])
        with patch("concurrent.futures.ThreadPoolExecutor", side_effect=RuntimeError("no threads")):
            assert _report_health._spawn_health_checks() is None

        assert "启动健康检查失败" in caplog.text

    def test_returns_future(self, monkeypatch):
        """启动成功 → 返回可收取的 Future（探针本身换空实现，不把真网络带进用例）。"""
        import src.python.core.check_sources as check_sources

        monkeypatch.setattr(check_sources, "run_health_checks", lambda: [])

        future = _report_health._spawn_health_checks()

        assert future is not None
        assert callable(getattr(future, "result", None))


class TestCollect:
    def test_none_future_is_noop(self):
        with patch("src.python.core.perf.save_health_check_snapshot") as save:
            _report_health._collect_health_checks(None, "basic", [])

        save.assert_not_called()

    def test_non_future_is_noop(self):
        """鸭子类型不符（无 `result`）→ 跳过，不猜实现。"""
        with patch("src.python.core.perf.save_health_check_snapshot") as save:
            _report_health._collect_health_checks(object(), "basic", [])

        save.assert_not_called()

    def test_non_list_result_is_ignored(self, monkeypatch):
        with patch("src.python.core.perf.save_health_check_snapshot") as save:
            _report_health._collect_health_checks(_Future({"bad": "shape"}), "basic", [])

        save.assert_not_called()

    def test_non_dict_items_are_filtered_out(self, monkeypatch):
        """列表内混入非 dict 条目 → 逐层剔除；剔完为空则不写盘。"""
        with patch("src.python.core.perf.save_health_check_snapshot") as save:
            _report_health._collect_health_checks(_Future(["x", 1, None]), "basic", [])

        save.assert_not_called()

    def test_results_are_persisted_and_recorded(self):
        results = [
            {"name": "price", "ok": True, "detail": ""},
            {"name": "news", "ok": False, "detail": "timeout"},
        ]
        with (
            patch("src.python.core.perf.save_health_check_snapshot") as save,
            patch("src.python.core.degradation.get_tracker") as tracker,
        ):
            _report_health._collect_health_checks(_Future(results), "basic", [1, 2, 3])

        save.assert_called_once()
        assert save.call_args.args[0] == results
        assert save.call_args.kwargs["holdings_count"] == 3
        recorded = {
            call.kwargs["source_key"]: call.kwargs["success"] for call in tracker.return_value.record.call_args_list
        }
        assert recorded == {"health_price": True, "health_news": False}

    def test_collect_failure_is_swallowed(self, caplog):
        """落盘/登记失败（磁盘满）→ INFO 日志，报告链不受影响。"""
        results = [{"name": "price", "ok": True}]
        with patch("src.python.core.perf.save_health_check_snapshot", side_effect=OSError("disk full")):
            _report_health._collect_health_checks(_Future(results), "basic", [])

        assert "收集健康检查结果失败" in caplog.text

    def test_future_raising_is_swallowed(self, caplog):
        _report_health._collect_health_checks(_Future(error=RuntimeError("worker died")), "basic", [])

        assert "收集健康检查结果失败" in caplog.text
