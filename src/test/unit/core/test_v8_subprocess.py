"""V8 类 akshare 取数的子进程隔离：白名单、JSON 契约、超时/崩溃降级、离线开关。

背景见 `src/python/core/v8_subprocess.py`：V8（py_mini_racer）在主进程内无论怎么调度
都可能段错误/退出死锁，故这些取数一律放子进程，父进程只收 JSON、按源不可用降级。
"""

from __future__ import annotations

import json
import subprocess

import pytest

from src.python.core import v8_subprocess
from src.python.core.v8_subprocess import (
    V8SourceError,
    _parse_child_output,
    run_akshare_v8,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _proc(stdout: str = "", stderr: str = "", code: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=code, stdout=stdout, stderr=stderr)


@pytest.mark.unit
class TestWhitelist:
    def test_unknown_function_rejected(self):
        """白名单外接口一律拒绝（接口名会被拼进子进程脚本，不可自由传入）。"""
        with pytest.raises(ValueError, match="白名单"):
            run_akshare_v8("tool_trade_date_hist_sina' ; import os", runner=lambda *a: [])

    def test_non_serializable_kwargs_rejected(self):
        """参数须 JSON 可序列化（子进程只收纯数据，不 pickle 任意对象）。"""
        with pytest.raises(ValueError, match="JSON"):
            run_akshare_v8("tool_trade_date_hist_sina", {"obj": object()}, runner=lambda *a: [])

    def test_payload_shape_passed_to_runner(self):
        """传给执行器的载荷是 {func, names, kwargs}，参数原样保留。"""
        captured: list[dict] = []

        def _runner(payload, timeout):
            captured.append(payload)
            return [{"trade_date": "2026-09-17"}]

        rows = run_akshare_v8("stock_fund_flow_industry", {"symbol": "即时"}, runner=_runner)

        assert rows == [{"trade_date": "2026-09-17"}]
        assert captured == [
            {
                "func": "stock_fund_flow_industry",
                "names": ["stock_fund_flow_industry", "stock_fund_flow_industry_ths"],
                "kwargs": {"symbol": "即时"},
            }
        ]

    def test_candidate_names_cover_renamed_interface(self):
        """akshare 重命名接口时必须同时试候选链里的两个名字（否则只认一个名字的机器上取数静默失效）。"""
        names = v8_subprocess.candidate_names("stock_fund_flow_industry")
        assert "stock_fund_flow_industry_ths" in names, "新版 akshare 的改名后接口名必须在内"
        assert names[0] == "stock_fund_flow_industry", "旧名仍可用的环境优先走旧名（同一函数，不改语义）"
        assert v8_subprocess.candidate_names("tool_trade_date_hist_sina") == (
            "tool_trade_date_hist_sina",
            "calendar_trade_date_hist_sina",
        )

    def test_none_kwargs_becomes_empty_dict(self):
        seen: list[dict] = []
        run_akshare_v8("tool_trade_date_hist_sina", runner=lambda payload, t: seen.append(payload) or [])
        assert seen[0]["kwargs"] == {}


@pytest.mark.unit
class TestChildOutputParsing:
    def test_result_marker_parsed(self):
        out = v8_subprocess._RESULT_MARKER + json.dumps([{"a": 1}], ensure_ascii=False)
        assert _parse_child_output(_proc(stdout=out)) == [{"a": 1}]

    def test_error_marker_raises_source_failed(self):
        """子进程内异常 → V8SourceError(source_failed)，调用方按源不可用降级。"""
        out = v8_subprocess._ERROR_MARKER + json.dumps({"type": "ConnectionError", "message": "offline"})
        with pytest.raises(V8SourceError) as ctx:
            _parse_child_output(_proc(stdout=out, code=1))
        assert ctx.value.reason == "source_failed"
        assert "ConnectionError" in str(ctx.value)

    def test_missing_marker_reports_exit_code_and_stderr_tail(self):
        with pytest.raises(V8SourceError) as ctx:
            _parse_child_output(_proc(stdout="", stderr="boom line", code=139))
        assert ctx.value.reason == "no_result"
        assert "139" in str(ctx.value)
        assert "boom line" in str(ctx.value)

    def test_unparsable_result_reports_reason(self):
        out = v8_subprocess._RESULT_MARKER + "{not json"
        with pytest.raises(V8SourceError) as ctx:
            _parse_child_output(_proc(stdout=out))
        assert ctx.value.reason == "unparsable"

    def test_non_list_result_is_empty(self):
        """子进程返回非数组（契约破坏）→ 空列表，不把脏数据带进分析。"""
        out = v8_subprocess._RESULT_MARKER + json.dumps({"a": 1})
        assert _parse_child_output(_proc(stdout=out)) == []


@pytest.mark.unit
class TestTimeoutIsolation:
    def test_timeout_kills_child_and_degrades(self, monkeypatch):
        """子进程超时（V8 死锁的典型表现）→ 杀子进程 + V8SourceError，父进程不挂死。"""

        def _raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd="child", timeout=1.0)

        monkeypatch.setattr(v8_subprocess.subprocess, "run", _raise_timeout)
        with pytest.raises(V8SourceError) as ctx:
            v8_subprocess._run_child({"func": "tool_trade_date_hist_sina", "kwargs": {}}, 1.0)
        assert ctx.value.reason == "timeout"
