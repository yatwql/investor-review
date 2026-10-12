"""report_qa_session 边缘/异常场景 — 轮数硬上限 / 输入软上限 / 路径防御 / 文件缺失。"""

from __future__ import annotations

import pytest

import src.python.qa.session as qa_session
from src.python.qa.session import ask_report_qa, report_qa_session_count

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_qa,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]

_MOCK_CONFIG = {"provider": "openai", "model": "test-model"}


class _AlwaysOk:
    def __call__(self, system, user, config, max_tokens=None, http_client=None):
        return "回答。", {"input_tokens": 1, "output_tokens": 1}, {"name": "mock"}


def _ask(output_dir, report, question, session_id=None):
    return ask_report_qa(report, question, session_id, output_dir=output_dir, llm_config=_MOCK_CONFIG)


class TestHardLimits:
    """轮数/输入两类上限的显式报错口径（不静默截断、不静默超卖）。"""

    def test_turn_limit_returns_session_limit(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        monkeypatch.setattr(qa_session, "call_llm", _AlwaysOk())
        monkeypatch.setattr(qa_session, "_QA_MAX_TURNS", 2)
        monkeypatch.setattr(qa_session, "run_fact_check", lambda html, h, **kw: (html, ""))

        first = _ask(output_dir, report, "一问")
        second = _ask(output_dir, report, "二问", session_id=first["session_id"])
        third = _ask(output_dir, report, "三问", session_id=first["session_id"])

        assert second["ok"] is True
        assert third["ok"] is False
        assert third["error_code"] == "QA_SESSION_LIMIT"
        assert "上限" in third["error"]
        assert third["session_id"] == first["session_id"]  # 超限仍回会话标识供提示

    def test_input_token_cap_returns_exceeded(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        monkeypatch.setattr(qa_session, "call_llm", _AlwaysOk())
        monkeypatch.setattr(qa_session, "_QA_INPUT_TOKEN_CAP", 1)
        monkeypatch.setattr(qa_session, "run_fact_check", lambda html, h, **kw: (html, ""))

        result = _ask(output_dir, report, "问题")

        assert result["ok"] is False
        assert result["error_code"] == "QA_INPUT_CAP_EXCEEDED"
        assert "刷新" in result["error"]

    def test_failed_context_extraction_consumes_no_turn(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        monkeypatch.setattr(qa_session, "call_llm", _AlwaysOk())

        result = _ask(output_dir, "缺失报告.html", "问题")

        assert result["ok"] is False
        assert result["error_code"] == "QA_REPORT_NOT_FOUND"
        assert report_qa_session_count() == 1  # 会话壳已建、上下文未构建、轮数未耗


class TestPathDefenseInDepth:
    """会话层路径防御（与 Web 路由/上下文提取三层同语义）。"""

    @pytest.mark.parametrize("bad", ["../evil.html", "sub/dir.html", "a\\b.html", "x.txt"])
    def test_illegal_report_rejected_before_any_io(self, tmp_path, bad):
        result = _ask(str(tmp_path), bad, "问题")
        assert result["ok"] is False
        assert result["error_code"] == "QA_BAD_REPORT"
        assert report_qa_session_count() == 0  # 路径校验在会话创建之前
