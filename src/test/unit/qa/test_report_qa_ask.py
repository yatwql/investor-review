"""report_qa Web 路由测试（``POST /api/qa/ask``，Flask test_client）。

覆盖设计 §3.6 校验矩阵：开关关闭 403 / 参数与超长 400 / 报告缺失与结构
不可解析 404 / LLM 全链失败 503 / 正常 200；路径净化与 session_id 类型校验。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.web.app import create_app
from src.python.web.runs import RunManager

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa, pytest.mark.usefixtures("offline_external_sources")]


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Flask test_client：output_dir 重定向 tmp_path + 无副作用 executor。"""
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
    invalidate_config_cache()

    def _exec(state, params):
        state.output_dir = str(tmp_path)
        state.push_event("ok", "done")
        return 0

    app = create_app(RunManager(executor=_exec))
    app.config["TESTING"] = True
    return app.test_client()


def _enable_qa(monkeypatch, enabled: bool = True):
    """显式设定追问开关（FEATURE_FLAGS 为内存态，conftest 逐用例重置）。"""
    from src.python.config.features import set_feature_enabled

    set_feature_enabled("report_qa", enabled)


def _post(client, payload):
    return client.post("/api/qa/ask", json=payload)


class TestSwitchGate:
    """开关门（默认关 → 403，且不进入会话服务）。"""

    def test_disabled_returns_403_and_never_calls_service(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, False)
        with patch("src.python.qa.session.ask_report_qa") as mocked:
            resp = _post(app_client, {"report": "任何.html", "question": "问题"})
        assert resp.status_code == 403
        assert resp.get_json()["error_code"] == "QA_DISABLED"
        mocked.assert_not_called()

    def test_enabled_passes_gate(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, True)
        with patch("src.python.qa.session.ask_report_qa", return_value={"ok": True, "answer_html": "x"}):
            resp = _post(app_client, {"report": "任何.html", "question": "问题"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["answer_html"] == "x"


class TestParamValidation:
    """路由层参数/路径净化（session_id 类型、report 白名单语义）。"""

    @pytest.mark.parametrize(
        "bad_report",
        ["", "../evil.html", "sub/dir.html", "a\\b.html", "报告.txt", "报告.html.exe"],
    )
    def test_illegal_report_returns_400(self, app_client, monkeypatch, bad_report):
        _enable_qa(monkeypatch, True)
        with patch("src.python.qa.session.ask_report_qa") as mocked:
            resp = _post(app_client, {"report": bad_report, "question": "问题"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"
        mocked.assert_not_called()

    def test_non_string_session_id_returns_400(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, True)
        with patch("src.python.qa.session.ask_report_qa") as mocked:
            resp = _post(app_client, {"report": "报告.html", "question": "问题", "session_id": 123})
        assert resp.status_code == 400
        mocked.assert_not_called()

    def test_missing_question_returns_400_from_service(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, True)
        resp = _post(app_client, {"report": "报告.html", "question": "  "})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "QA_BAD_QUESTION"

    def test_missing_payload_returns_400(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, True)
        resp = app_client.post("/api/qa/ask", json=None)
        assert resp.status_code == 400


class TestStatusMapping:
    """服务错误码 → HTTP 状态码映射矩阵（信封携带 code 供前端分支）。"""

    @pytest.mark.parametrize(
        ("service_result", "expected_status"),
        [
            ({"ok": False, "error_code": "QA_REPORT_NOT_FOUND", "error": "缺失"}, 404),
            ({"ok": False, "error_code": "QA_CONTEXT_INVALID", "error": "不可解析"}, 404),
            ({"ok": False, "error_code": "QA_LLM_UNAVAILABLE", "error": "未配置"}, 503),
            ({"ok": False, "error_code": "QA_LLM_FAILED", "error": "未产出"}, 503),
            ({"ok": False, "error_code": "QA_SESSION_LIMIT", "error": "超限"}, 400),
            ({"ok": False, "error_code": "QA_QUESTION_TOO_LONG", "error": "过长"}, 400),
        ],
    )
    def test_error_code_maps_to_status(self, app_client, monkeypatch, service_result, expected_status):
        _enable_qa(monkeypatch, True)
        with patch("src.python.qa.session.ask_report_qa", return_value=service_result):
            resp = _post(app_client, {"report": "报告.html", "question": "问题"})
        assert resp.status_code == expected_status
        body = resp.get_json()
        assert body["ok"] is False
        assert body["error_code"] == service_result["error_code"]

    def test_success_envelope_carries_contract_fields(self, app_client, monkeypatch):
        _enable_qa(monkeypatch, True)
        payload = {
            "ok": True,
            "session_id": "abc123",
            "answer_html": "<p>回答</p>",
            "turns": 1,
            "remaining_turns": 9,
            "usage": {"input_tokens": 10, "output_tokens": 5, "provider": "p"},
            "fact_warning": False,
        }
        with patch("src.python.qa.session.ask_report_qa", return_value=payload):
            resp = _post(app_client, {"report": "报告.html", "question": "问题"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["session_id"] == "abc123"
        assert data["answer_html"] == "<p>回答</p>"
        assert data["usage"]["input_tokens"] == 10


class TestEndToEndSmoke:
    """阶段 3 冒烟：路由 → 会话服务 → 真实样本报告上下文（LLM mock），
    覆盖「提问→回答→多轮→超限提示→刷新重建」全链（设计阶段 3 验收项）。"""

    @staticmethod
    def _fake_llm(system, user, config, max_tokens=None, http_client=None):
        return "**回答**：按本期报告数据。", {"input_tokens": 10, "output_tokens": 5}, {"name": "mock"}

    def test_multi_turn_limit_and_refresh_rebuild(self, app_client, qa_report, monkeypatch):
        report, _report2, _output_dir = qa_report  # output_dir 即 app_client 重定向的 tmp_path
        _enable_qa(monkeypatch, True)
        monkeypatch.setattr("src.python.qa.session.call_llm", self._fake_llm)
        monkeypatch.setattr(
            "src.python.qa.session.get_llm_config", lambda: {"provider": "mock", "model": "m"}
        )  # 隔离环境无真实密钥：仅检验链路，LLM 调用本身已 mock
        monkeypatch.setattr("src.python.qa.session._QA_MAX_TURNS", 2)

        first = _post(app_client, {"report": report, "question": "本期汇率风险如何？"})
        assert first.status_code == 200
        d1 = first.get_json()["data"]
        assert d1["turns"] == 1 and d1["remaining_turns"] == 1
        assert "<strong>回答</strong>" in d1["answer_html"]
        assert "qa-answer-note" in d1["answer_html"]

        second = _post(
            app_client,
            {"report": report, "question": "债券占比呢？", "session_id": d1["session_id"]},
        )
        assert second.status_code == 200
        d2 = second.get_json()["data"]
        assert d2["session_id"] == d1["session_id"]
        assert d2["remaining_turns"] == 0

        third = _post(
            app_client,
            {"report": report, "question": "再问一个", "session_id": d1["session_id"]},
        )
        assert third.status_code == 400
        assert third.get_json()["error_code"] == "QA_SESSION_LIMIT"

        rebuilt = _post(app_client, {"report": report, "question": "刷新后再问"})
        assert rebuilt.status_code == 200
        d3 = rebuilt.get_json()["data"]
        assert d3["session_id"] != d1["session_id"]  # 不带 session_id = 刷新重建
        assert d3["turns"] == 1
