"""核心层降级分支：数据源探针异常、决策头解析、新鲜度阈值、并发档位、桌面能力探测。

每个用例都针对「上游异常/畸形输入 → 已声明的降级行为」这一具体分支，
断言落在可观测结果（符号/返回值/中文提示）上，而不是「没抛异常」。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

import src.python.core.artifacts as artifacts
import src.python.core.check_sources as cs
from src.python.core import concurrency, data_freshness, decision_header

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestCheckAnyCandidates:
    """``_check_any``：单候选命中不加端点标注，多候选命中标注降级接管。"""

    def test_single_candidate_hit_has_no_endpoint_note(self, monkeypatch):
        monkeypatch.setattr(cs, "_check_http", lambda url, **kwargs: (cs._OK, 3.0, "3ms 正常"))

        symbol, elapsed, message = cs._check_any([("主源", "http://example.invalid/x")])

        assert (symbol, elapsed, message) == (cs._OK, 3.0, "3ms 正常")


class TestProbeExceptionsBecomeErr:
    """探针内部异常必须变成一行的 ERR 结果（体检不中断）。"""

    def test_cninfo_probe_exception(self, monkeypatch):
        def _boom(_symbol):
            raise RuntimeError("连接被重置\n详细堆栈第二行")

        monkeypatch.setattr("src.python.fetcher.report_adapters.probe_cninfo_orgid", _boom)

        symbol, _elapsed, message = cs._check_cninfo()

        assert symbol == cs._ERR
        assert message == "连接被重置"

    def test_sector_flow_probe_exception(self, monkeypatch):
        def _boom():
            raise RuntimeError("通道探测失败\n详细堆栈第二行")

        monkeypatch.setattr("src.python.providers.akshare_extras.probe_sector_flow_channels", _boom)

        symbol, _elapsed, message = cs._check_sector_flow()

        assert symbol == cs._ERR
        assert message == "通道探测失败"


class TestProxyHintAndRender:
    """代理诊断提示项：空结果原样返回、提示行走告警行、不影响退出码。"""

    def test_empty_results_returned_as_is(self):
        assert cs._with_proxy_hint([]) == []

    def test_hint_line_rendered_without_affecting_exit_code(self, monkeypatch):
        monkeypatch.setattr(
            cs,
            "run_health_checks",
            lambda max_timeout=15.0: [
                {"name": "src_a", "label": "用途", "ok": False, "latency_ms": 3.0, "message": "全部失败", "hint": True},
                {"name": "src_b", "label": "用途", "ok": True, "latency_ms": 1.0, "message": "正常"},
            ],
        )

        text, exit_code = cs.collect_check_sources_report()

        assert "全部失败" in text
        assert "src_a" not in text
        assert exit_code == 0


class TestHealthCheckBudgetZero:
    """max_timeout=0：预算在首轮等待前即耗尽，仍要返回（不卡死）。"""

    def test_zero_budget_returns_without_blocking(self, monkeypatch):
        release = threading.Event()

        def _pending_check():
            release.wait()  # 永不置位：模拟挂起的数据源探针
            return cs._OK, 1.0, "ok"

        monkeypatch.setattr(cs, "_checks", [("src_a", "src_a", "测试", _pending_check)])

        results = cs.run_health_checks(max_timeout=0.0)
        release.set()

        # 预算 0s：不等挂起探针，直接按未完成项落「超时」占位项返回
        assert [item["name"] for item in results] == ["src_a"]
        assert results[0]["ok"] is False
        assert results[0]["message"].startswith("超时"), results[0]


class TestDecisionHeaderParsing:
    """决策头解析：标签/装饰剥离与括号配对扫描的边界。"""

    def test_tag_only_text_has_no_direction(self):
        """``<abc>`` 去标签后为空——不猜方向，返回 None（不默认 FLAT）。"""
        assert decision_header.parse_decision_word("<abc>") is None

    def test_match_json_end_skips_escaped_quote(self):
        """字符串值内的转义引号不结束字符串，闭合花括号仍是唯一的配对终点。"""
        text = '{"k":"a\\"b"}'

        assert decision_header._match_json_end(text, 0, len(text)) == len(text)

    def test_invalid_json_payload_falls_back(self):
        """载荷非 JSON → 返回 None 交由确定性表格解析兜底。"""
        assert decision_header.parse_structured_header("决策头：{not json}") is None


class TestFreshnessDegradation:
    """新鲜度降级：日历不可读按无日历、阈值不可读按默认。"""

    def test_unreadable_calendar_returns_empty_list(self, monkeypatch):
        def _boom():
            raise RuntimeError("缓存不可用")

        monkeypatch.setattr("src.python.core.trading_calendar.cached_trading_days", _boom)

        assert data_freshness._cached_trading_days() == []

    def test_unreadable_threshold_config_returns_default(self):
        assert data_freshness.header_stale_threshold_days(["bad"]) == data_freshness._DEFAULT_T2_STALE_DAYS


class TestConcurrencyProfileAndBudget:
    """并发档位/预算：配置不可读回落默认，预算只解析一次。"""

    def test_unreadable_profile_config_falls_back(self, monkeypatch):
        def _boom():
            raise RuntimeError("配置不可用")

        monkeypatch.setattr("src.python.config.get_config", _boom)

        assert concurrency.ConcurrencyGovernor.resolve_profile() == concurrency.DEFAULT_PROFILE

    def test_budget_cached_after_first_resolve(self, monkeypatch):
        governor = concurrency.ConcurrencyGovernor()
        calls: list[int] = []
        monkeypatch.setattr(
            concurrency.ConcurrencyGovernor,
            "resolve_budget",
            staticmethod(lambda: calls.append(1) or 7),
        )

        assert governor.budget() == 7
        assert governor.budget() == 7
        assert len(calls) == 1


class TestDesktopOpenDetection:
    """桌面能力探测：DISPLAY 残留、xdg-open 缺失、Windows 直开。"""

    def test_display_without_screen_segment_rejected(self):
        assert artifacts._x11_socket_present("") is False

    def test_opener_present_follows_which(self, monkeypatch):
        monkeypatch.setattr(artifacts.shutil, "which", lambda name: "/usr/bin/xdg-open")
        assert artifacts._opener_present() is True

        monkeypatch.setattr(artifacts.shutil, "which", lambda name: None)
        assert artifacts._opener_present() is False

    def test_wayland_session_uses_opener_probe(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        for key in ("SSH_CONNECTION", "SSH_TTY", "MOSH_CONNECTION"):
            monkeypatch.delenv(key, raising=False)
        for key in artifacts._BRIDGED_SESSION_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setattr(artifacts, "_opener_present", lambda: True)

        assert artifacts.local_open_supported() is True

    def test_x11_socket_present_uses_opener_probe(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        for key in ("SSH_CONNECTION", "SSH_TTY", "MOSH_CONNECTION"):
            monkeypatch.delenv(key, raising=False)
        for key in artifacts._BRIDGED_SESSION_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(artifacts, "_x11_socket_present", lambda display: True)
        monkeypatch.setattr(artifacts, "_opener_present", lambda: True)

        assert artifacts.local_open_supported() is True

    def test_non_linux_platform_assumes_desktop(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")

        assert artifacts.local_open_supported() is True

    def test_windows_open_uses_startfile(self, monkeypatch, tmp_path):
        opened: list[str] = []
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr(os, "startfile", lambda target: opened.append(target), raising=False)
        target = Path(tmp_path) / "report.html"

        assert artifacts.open_path(target) is True
        assert opened == [str(target)]
