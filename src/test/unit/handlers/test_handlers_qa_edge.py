"""TUI 报告对话式追问入口 — 边缘场景（EOF / Ctrl+C / 目录不可读）。

与常规用例分文件（`test_handlers_qa.py`）：本文件全部为 @pytest.mark.edge。
LLM/会话服务一律 mock，不发起真实调用。
"""

from __future__ import annotations

import pytest

from src.python.tui import handlers_qa

pytestmark = [pytest.mark.unit, pytest.mark.unit_core, pytest.mark.edge]


def _input_raising(exc_type):
    """input() 替身：总是抛出指定异常（模拟 stdin 关闭/Ctrl+C）。"""

    def _fake(prompt: str = "") -> str:
        raise exc_type()

    return _fake


class TestSelectionEdge:
    """报告选择的异常输入与异常目录。"""

    def test_eof_on_selection_returns_none(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "报告.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setattr("builtins.input", _input_raising(EOFError))
        assert handlers_qa._select_report(str(tmp_path)) is None

    def test_keyboard_interrupt_on_selection_returns_none(self, tmp_path, monkeypatch):
        (tmp_path / "报告.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setattr("builtins.input", _input_raising(KeyboardInterrupt))
        assert handlers_qa._select_report(str(tmp_path)) is None

    def test_missing_output_dir_returns_none(self, tmp_path, monkeypatch, capsys):
        assert handlers_qa._list_reports(str(tmp_path / "不存在")) == []
        monkeypatch.setattr("builtins.input", _input_mock_no_call())
        assert handlers_qa._select_report(str(tmp_path / "不存在")) is None
        assert "暂无 HTML 报告" in capsys.readouterr().out


class TestAskLoopEdge:
    """输入循环的异常输入与报告不可用终止。"""

    def test_eof_on_question_exits_without_calling_service(self, monkeypatch, capsys):
        def _unexpected_call(*args, **kwargs):
            raise AssertionError("EOF 守护失效：不应调用会话服务")

        monkeypatch.setattr(handlers_qa, "ask_report_qa", _unexpected_call)
        monkeypatch.setattr("builtins.input", _input_raising(EOFError))
        handlers_qa._qa_input_loop("报告.html")  # 不抛异常即守护生效
        assert "追问会话" in capsys.readouterr().out

    def test_keyboard_interrupt_on_question_exits_gracefully(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", _input_raising(KeyboardInterrupt))
        handlers_qa._qa_input_loop("报告.html")
        assert "追问会话" in capsys.readouterr().out

    def test_report_unavailable_terminates_loop(self, monkeypatch, capsys):
        calls = []

        def _fake(report: str, question: str, session_id=None, **kwargs) -> dict:
            calls.append(question)
            return {"ok": False, "error_code": "QA_REPORT_NOT_FOUND", "error": "报告文件不可用，请重新生成后再追问"}

        monkeypatch.setattr(handlers_qa, "ask_report_qa", _fake)
        monkeypatch.setattr("builtins.input", _input_mock_one("这份报告呢？"))
        handlers_qa._qa_input_loop("报告.html")
        out = capsys.readouterr().out
        assert "报告文件不可用" in out
        assert len(calls) == 1  # 报告不可用即终止，不再等待输入


def _input_mock_no_call():
    def _fake(prompt: str = "") -> str:
        raise AssertionError(f"不应出现 input() 调用：{prompt!r}")

    return _fake


def _input_mock_one(value: str):
    state = {"done": False}

    def _fake(prompt: str = "") -> str:
        if state["done"]:
            raise AssertionError(f"终止性错误后不应再等待输入：{prompt!r}")
        state["done"] = True
        return value

    return _fake
