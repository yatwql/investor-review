"""test_handlers 兄弟分片（system）：配置回填 / 健康检查 / 系统信息 / 日志 / 自检接口。"""

from __future__ import annotations
import os
from unittest.mock import patch
import pytest
from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.core.log_reader import LogEntry
from src.python.web.app import create_app
from src.python.web.handlers import _build_system_info
from src.python.web.handlers_health import _health_cache
from src.python.web.runs import RunManager

# 夹具按名注入（由测试签名消费），代码里无引用

# ruff: noqa: F811 — 参数与模块级夹具同名（pytest 按名注入），非重定义
from src.test.unit.web.test_handlers import (
    _fake_executor,  # noqa: F401
    app_client,  # noqa: F401
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]


class TestIndexConfigBackfill:
    """索引页按 get_config() 回填表单默认（历史走势/强制 LLM 复选框）。"""

    def test_index_renders_form_and_status_sections(self, app_client):
        resp = app_client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # 生成区新增控件
        assert 'id="history-fetch"' in html
        assert 'id="force-llm"' in html
        # 状态区：健康 + 历史
        assert 'id="health-list"' in html
        assert 'id="history-list"' in html

    def test_index_header_shows_app_name_and_version(self, app_client):
        """首页顶部强调应用名称 + 版本号（APP_NAME 常量 + app_version）。"""
        from src.python.core.constants import APP_NAME, APP_VERSION

        resp = app_client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert f"<h1>{APP_NAME}</h1>" in html
        assert f"v{APP_VERSION} ·" in html

    def test_history_checkbox_follows_config_default(self, app_client):
        """默认 fetch_mode=auto → 历史走势复选框勾选 + 配置说明。"""
        resp = app_client.get("/")
        html = resp.data.decode("utf-8")
        assert 'name="fetch_history" checked' in html
        assert "跟随配置开启" in html

    def test_history_checkbox_off_when_config_fetch_mode_off(self, tmp_path, monkeypatch):
        """配置 history.fetch_mode=off → 复选框不勾选。"""
        monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
        monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG["history"], "fetch_mode", "off")
        invalidate_config_cache()
        rm = RunManager(executor=_fake_executor(tmp_path))
        app = create_app(rm)
        app.config["TESTING"] = True
        html = app.test_client().get("/").data.decode("utf-8")
        assert 'name="fetch_history"' in html  # 控件存在
        assert 'name="fetch_history" checked' not in html  # 未勾选
        assert "当前配置关闭" in html


class TestHealthEndpoint:
    """/api/health 缓存 + fresh 强制重测。"""

    def test_cached_and_fresh(self, app_client):
        _health_cache["ts"] = 0.0
        _health_cache["data"] = None
        calls = {"n": 0}

        def fake_health(max_timeout=15.0):
            calls["n"] += 1
            return [{"name": "x", "label": "测试源", "ok": True, "latency_ms": 1.0, "message": "ok"}]

        with patch("src.python.core.check_sources.run_health_checks", side_effect=fake_health):
            r1 = app_client.get("/api/health")
            assert r1.status_code == 200
            assert r1.get_json()["data"][0]["ok"] is True
            # 60s 缓存内：不触发真实探测
            app_client.get("/api/health")
            assert calls["n"] == 1
            # fresh=1 强制重测
            app_client.get("/api/health?fresh=1")
            assert calls["n"] == 2


class TestSystemInfo:
    """状态区系统信息组装（_build_system_info：版本 / IP / 持仓摘要 / LLM 状态，对齐 TUI）。

    覆盖：默认未配置 / 持仓摘要字段（含文件就绪判定）/ 顶层字段不参与配置 /
    credentials_ref 多链 / 读配置异常兜底 / 索引页渲染（未配置时显示「未配置」）。
    """

    @staticmethod
    def _patch_llm(monkeypatch, config=None, module_names=None, circuit="正常"):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: config)
        monkeypatch.setattr(
            "src.python.core.registry.get_llm_module_names",
            lambda: module_names or {},
        )
        monkeypatch.setattr("src.python.llm.circuit_breaker.get_circuit_status", lambda ep: circuit)
        monkeypatch.setattr("src.python.core.logger.get_machine_ip", lambda: "192.168.1.100")
        return config

    @staticmethod
    def _patch_config(monkeypatch, config=None, privacy_shown=False):
        """替换配置摘要数据源：get_config / 本地状态标志 / 机器 IP。"""
        monkeypatch.setattr("src.python.config.get_config", lambda: config or {})
        monkeypatch.setattr("src.python.config._local_state.get_flag", lambda key: privacy_shown)
        monkeypatch.setattr("src.python.core.logger.get_machine_ip", lambda: "192.168.1.100")
        return config

    def test_default_no_llm_config(self, monkeypatch):
        """未配置（get_llm_config 返回 None）：configured=False，版本/IP 正常。"""
        self._patch_llm(monkeypatch, config=None)
        info = _build_system_info()
        assert info["app_version"]
        assert info["machine_ip"] == "192.168.1.100"
        assert info["llm"] == {"configured": False}

    def test_config_summary_defaults(self, monkeypatch):
        """配置为空 dict：持仓目录/文件未设置、输出取 get_default、新闻 300、匿名化关闭。"""
        from src.python.config import get_default, resolve_holdings_path

        self._patch_llm(monkeypatch, config=None)
        self._patch_config(monkeypatch, config={})
        info = _build_system_info()
        assert info["holdings_dir"] == "未设置"
        assert info["holdings_filename"] == "未设置"
        # 输出默认 = get_default（真值来源，单源解析；不写死字面量）
        assert info["output_dir"] == get_default("output_dir")
        assert info["news_top_count"] == 300
        # 就绪判定反映 resolve_holdings_path 指向的真实文件（状态与生成链路同一路径口径）
        assert info["holdings_ready"] is os.path.exists(resolve_holdings_path())
        assert info["anonymization"] == "关闭"
        assert info["privacy_shown"] is False

    def test_config_summary_fields_and_ready(self, monkeypatch, tmp_path):
        """持仓文件就绪：目录/文件名/输出/新闻/匿名化/隐私齐全，状态为就绪。"""
        holdings_file = tmp_path / "持仓.xlsx"
        holdings_file.touch()
        self._patch_llm(monkeypatch, config=None)
        self._patch_config(
            monkeypatch,
            config={
                "holdings_dir": str(tmp_path),
                "holdings_filename": "持仓.xlsx",
                "output_dir": str(tmp_path / "reports"),
                "news_top_count": 200,
                "anonymization": {"mode": "full_anonymous"},
            },
            privacy_shown=True,
        )
        info = _build_system_info()
        assert info["holdings_dir"] == str(tmp_path)
        assert info["holdings_filename"] == "持仓.xlsx"
        assert info["output_dir"] == str(tmp_path / "reports")
        assert info["news_top_count"] == 200
        assert info["holdings_ready"] is True
        assert info["anonymization"] == "完全匿名"
        assert info["privacy_shown"] is True

    def test_config_summary_file_missing(self, monkeypatch, tmp_path):
        """持仓文件不存在：holdings_ready=False（状态「未找到」）。"""
        self._patch_llm(monkeypatch, config=None)
        self._patch_config(
            monkeypatch,
            config={"holdings_dir": str(tmp_path), "holdings_filename": "不存在的.xlsx"},
        )
        info = _build_system_info()
        assert info["holdings_ready"] is False

    def test_get_config_raises_falls_back_defaults(self, monkeypatch):
        """get_config 抛异常 → 摘要按默认值兜底，不阻断页面渲染。"""
        self._patch_llm(monkeypatch, config=None)
        self._patch_config(monkeypatch, config=None)

        def _boom():
            raise RuntimeError("config read failed")

        monkeypatch.setattr("src.python.config.get_config", _boom)
        info = _build_system_info()
        assert info["holdings_dir"] == "未设置"
        assert info["news_top_count"] == 300
        assert info["holdings_ready"] is False
        assert info["llm"] == {"configured": False}

    def test_default_llm_key_missing(self, monkeypatch):
        """缺 provider 链：按未配置兜底。"""
        self._patch_llm(monkeypatch, config={"model": "claude-sonnet-4-6"})
        info = _build_system_info()
        assert info["llm"] == {"configured": False}

    def test_single_provider_fields_show_unconfigured(self, monkeypatch):
        """顶层 api_key/provider（旧单 Provider 形态）不再产出 flat 详情。"""
        self._patch_llm(
            monkeypatch,
            config={"api_key": "sk-test", "provider": "claude", "model": "m", "endpoint": "https://e"},
        )
        info = _build_system_info()
        assert info["llm"] == {"configured": False}


class TestLogsEndpoint:
    """/api/logs 结构化日志查看。"""

    def test_logs_success(self, app_client):
        """正常读取 → 200 + LogEntry.to_dict 列表。"""
        entries = [
            LogEntry(time="2026-08-16 10:00:00,123", level="INFO", message="应用启动", body="应用启动"),
            LogEntry(
                time="2026-08-16 10:00:01,456",
                level="ERROR",
                message="读取行情失败",
                body="读取行情失败\n  堆栈行",
            ),
        ]
        with patch("src.python.core.log_reader.read_log", return_value=entries):
            resp = app_client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0] == {
            "time": "2026-08-16 10:00:00,123",
            "level": "INFO",
            "message": "应用启动",
            "body": "应用启动",
            "is_decorative": False,
        }
        assert data[1]["body"] == "读取行情失败\n  堆栈行"

    def test_invalid_level_400(self, app_client):
        """非法 level → 400 BAD_PARAM。"""
        resp = app_client.get("/api/logs?level=VERBOSE")
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_invalid_lines_400(self, app_client):
        """非法 lines → 400 BAD_PARAM。"""
        resp = app_client.get("/api/logs?lines=abc")
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_lines_clamped_to_5000(self, app_client):
        """lines 超上限被钳制为 5000。"""
        with patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read:
            resp = app_client.get("/api/logs?lines=999999")
        assert resp.status_code == 200
        assert mock_read.call_args.kwargs["limit"] == 5000

    def test_lines_min_one(self, app_client):
        """lines 为 0 被钳制为 1。"""
        with patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read:
            resp = app_client.get("/api/logs?lines=0")
        assert resp.status_code == 200
        assert mock_read.call_args.kwargs["limit"] == 1

    def test_level_filter_passthrough(self, app_client):
        """level 参数透传核心层。"""
        with patch("src.python.core.log_reader.read_log", return_value=[]) as mock_read:
            app_client.get("/api/logs?level=ERROR")
        assert mock_read.call_args.kwargs["level"] == "ERROR"

    def test_read_failure_500(self, app_client):
        """read_log 抛 OSError → 500 LOG_READ_FAILED。"""
        with patch("src.python.core.log_reader.read_log", side_effect=OSError("IO error")):
            resp = app_client.get("/api/logs")
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "LOG_READ_FAILED"


class TestHealthHistoryEndpoint:
    """/api/health/history 数据源健康历史摘要。"""

    def test_returns_summaries_on_200(self, app_client):
        """有历史 → 200 + 摘要列表。"""
        summaries = [
            {
                "timestamp": "2026-08-16T10:00:00",
                "report_type": "basic",
                "holdings_count": 3,
                "total": 10,
                "ok_count": 8,
                "fail_count": 2,
                "failed_sources": ["腾讯K线"],
            }
        ]
        with patch("src.python.core.perf.summarize_health_history", return_value=summaries):
            resp = app_client.get("/api/health/history")
        assert resp.status_code == 200
        assert resp.get_json()["data"][0]["failed_sources"] == ["腾讯K线"]

    def test_empty(self, app_client):
        """无历史 → 200 + 空列表。"""
        with patch("src.python.core.perf.summarize_health_history", return_value=[]):
            resp = app_client.get("/api/health/history")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_read_failure_500(self, app_client):
        """异常 → 500 HEALTH_HISTORY_READ_FAILED。"""
        with patch("src.python.core.perf.summarize_health_history", side_effect=OSError("IO error")):
            resp = app_client.get("/api/health/history")
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "HEALTH_HISTORY_READ_FAILED"


class TestDoctorEndpoint:
    """/api/doctor 系统自检（恒上屏，无开关）。

    Web 侧只做参数解析与 JSON 渲染，检查逻辑全在 core.doctor（其自身测试见
    test_doctor.py）——故此处 mock 掉 run_doctor_checks，只断言接口契约。
    """

    _SAMPLE = [
        {"group": "环境", "label": "Python 版本", "ok": True, "message": "3.12", "hint": ""},
        {"group": "目录", "label": "输出目录", "ok": False, "message": "不可写", "hint": "chmod +w"},
    ]

    def test_success_envelope(self, app_client):
        """200 + results/ok_count/bad_count 三键。"""
        with patch("src.python.core.doctor.run_doctor_checks", return_value=self._SAMPLE):
            resp = app_client.get("/api/doctor")

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["ok_count"] == 1
        assert data["bad_count"] == 1
        assert data["results"][1]["hint"] == "chmod +w"

    def test_network_default_on(self, app_client):
        """默认含联网检查。"""
        with patch("src.python.core.doctor.run_doctor_checks", return_value=self._SAMPLE) as mock_run:
            app_client.get("/api/doctor")

        assert mock_run.call_args.kwargs["include_network"] is True

    def test_network_off(self, app_client):
        """network=0 → 跳过联网检查。"""
        with patch("src.python.core.doctor.run_doctor_checks", return_value=self._SAMPLE) as mock_run:
            resp = app_client.get("/api/doctor?network=0")

        assert resp.status_code == 200
        assert mock_run.call_args.kwargs["include_network"] is False

    def test_timeout_clamped_to_ceiling(self, app_client):
        """timeout 超上限被钳制，防单次自检拖垮接口。"""
        with patch("src.python.core.doctor.run_doctor_checks", return_value=self._SAMPLE) as mock_run:
            app_client.get("/api/doctor?timeout=999")

        assert mock_run.call_args.kwargs["max_timeout"] == 15.0

    def test_timeout_invalid_falls_back_default(self, app_client):
        """非法 timeout → 回落到默认值而非 400（自检不该被查询串绊倒）。"""
        with patch("src.python.core.doctor.run_doctor_checks", return_value=self._SAMPLE) as mock_run:
            resp = app_client.get("/api/doctor?timeout=abc")

        assert resp.status_code == 200
        assert mock_run.call_args.kwargs["max_timeout"] == 12.0

    def test_broken_config_still_returns_200(self, app_client):
        """配置损坏时自检照常出结果（含失败行）——这正是它存在的场景。"""
        with patch("src.python.config.get_config", side_effect=RuntimeError("配置文件损坏")):
            resp = app_client.get("/api/doctor?network=0")

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["bad_count"] >= 1
        assert any("配置文件损坏" in r["message"] for r in data["results"])


class TestSystemInfoDoctorAlwaysOn:
    """status_grid /api/status 的自检卡恒可见（无功能开关）。"""

    def test_always_enabled(self):
        assert _build_system_info()["doctor_enabled"] is True

    def test_index_card_present(self, app_client):
        html = app_client.get("/").get_data(as_text=True)

        assert 'id="doctor-list"' in html
        assert 'id="doctor-run"' in html

    def test_no_feature_gate_remains(self):
        """TUI 侧不再门控、注册表不再有自检开关——三面同源的可见性口径。"""
        from src.python.config.features import feature_switch_registry
        from src.python.tui import tui_menu

        assert "doctor_check" not in feature_switch_registry
        assert "T" not in tui_menu.FEATURE_GATED_ITEMS
