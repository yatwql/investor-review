"""TUI 报告对话式追问入口测试（主菜单 [Q] 输入循环）。

测试目标：`tui/handlers_qa.py` —— 报告选择 / 输入循环 / 回答展示 / 会话续传 /
菜单开关门控；`qa/session.ask_report_qa` 一律 mock（防费用、防 API 依赖），
并断言与 Web 同源（同一函数对象、无 TUI 私有副本）。

边缘场景（EOF / Ctrl+C / 目录不可读）见同目录 `test_handlers_qa_edge.py`。
"""

from __future__ import annotations

import os
import time

import pytest

from src.python.tui import handlers_qa

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


# ── 共用夹具/辅助 ─────────────────────────────────────────────


def _fake_reports(directory, names: list[str]) -> list[str]:
    """在临时目录创建假报告文件（列表序即新旧序：首元素最新，mtime 逐个递减）。"""
    base = int(time.time())
    for i, name in enumerate(names):
        path = directory / name
        path.write_text("<html><body>report</body></html>", encoding="utf-8")
        os.utime(path, (base - i * 60, base - i * 60))
    return list(names)  # 首元素 = 最新


def _input_mock(answers: list):
    """input() 替身：按序返回 answers；元素为异常实例则抛出；耗尽则断言失败。"""
    iterator = iter(answers)

    def _fake(prompt: str = "") -> str:
        try:
            value = next(iterator)
        except StopIteration:
            raise AssertionError(f"出现意外的 input() 调用：{prompt!r}") from None
        if isinstance(value, BaseException):
            raise value
        return value

    return _fake


def _ok_result(session_id: str = "sid-1", turns: int = 1, **extra) -> dict:
    result = {
        "ok": True,
        "session_id": session_id,
        "answer_html": "<p>结论 A</p><p>细节 B</p>",
        "turns": turns,
        "remaining_turns": 10 - turns,
        "usage": {"input_tokens": 1200, "output_tokens": 300},
        "fact_warning": False,
    }
    result.update(extra)
    return result


# ── 报告选择 ─────────────────────────────────────────────────


class TestReportSelection:
    """输出目录报告列举与编号选择。"""

    def test_list_reports_sorted_by_mtime_and_capped(self, tmp_path):
        names = [f"报告{i:02d}.html" for i in range(10)]
        _fake_reports(tmp_path, names)
        listed = handlers_qa._list_reports(str(tmp_path))
        assert len(listed) == handlers_qa._QA_REPORT_LIST_MAX
        assert listed[0] == names[0]  # 最新在前
        assert names[-1] not in listed and names[-2] not in listed  # 超上限截断

    def test_ignores_non_html_and_subdirectories(self, tmp_path):
        _fake_reports(tmp_path, ["最新.html"])
        (tmp_path / "说明.txt").write_text("x", encoding="utf-8")
        (tmp_path / "归档").mkdir()
        (tmp_path / "归档" / "历史.html").write_text("x", encoding="utf-8")
        assert handlers_qa._list_reports(str(tmp_path)) == ["最新.html"]

    def test_default_enter_selects_latest(self, tmp_path, monkeypatch, capsys):
        _fake_reports(tmp_path, ["A.html", "B.html"])
        monkeypatch.setattr("builtins.input", _input_mock([""]))
        assert handlers_qa._select_report(str(tmp_path)) == "A.html"
        assert "可追问的报告" in capsys.readouterr().out

    def test_number_selection_and_revalidate(self, tmp_path, monkeypatch, capsys):
        _fake_reports(tmp_path, ["A.html", "B.html"])
        monkeypatch.setattr("builtins.input", _input_mock(["x", "99", "2"]))
        assert handlers_qa._select_report(str(tmp_path)) == "B.html"
        out = capsys.readouterr().out
        assert "请输入编号" in out and "编号超出范围" in out

    def test_q_cancels(self, tmp_path, monkeypatch):
        _fake_reports(tmp_path, ["A.html"])
        monkeypatch.setattr("builtins.input", _input_mock(["q"]))
        assert handlers_qa._select_report(str(tmp_path)) is None

    def test_empty_directory_returns_none(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", _input_mock([]))
        assert handlers_qa._select_report(str(tmp_path)) is None
        assert "暂无 HTML 报告" in capsys.readouterr().out


# ── 问答输入循环 ─────────────────────────────────────────────


class TestAskLoop:
    """输入循环：提问/回答展示/会话续传/错误信封/退出。"""

    @pytest.fixture
    def calls(self):
        """记录 ask_report_qa 调用参数的替身容器。"""
        return []

    def _patch_ask(self, monkeypatch, calls, results: list[dict]):
        def _fake(report: str, question: str, session_id=None, **kwargs) -> dict:
            calls.append({"report": report, "question": question, "session_id": session_id})
            return results[min(len(calls) - 1, len(results) - 1)]

        monkeypatch.setattr(handlers_qa, "ask_report_qa", _fake)

    def test_question_renders_answer_as_plain_text(self, monkeypatch, capsys, calls):
        self._patch_ask(monkeypatch, calls, [_ok_result()])
        monkeypatch.setattr("builtins.input", _input_mock(["这个组合怎么样？", "q"]))
        handlers_qa._qa_input_loop("报告.html")
        out = capsys.readouterr().out
        assert "结论 A" in out and "细节 B" in out
        assert "<p>" not in out  # 终端不出现 HTML 标签
        assert "第 1 轮完成，剩余 9 轮" in out and "1200/300" in out
        assert calls[0]["question"] == "这个组合怎么样？" and calls[0]["report"] == "报告.html"

    def test_session_id_reused_across_turns(self, monkeypatch, capsys, calls):
        self._patch_ask(
            monkeypatch, calls, [_ok_result(session_id="sid-42", turns=1), _ok_result(session_id="sid-42", turns=2)]
        )
        monkeypatch.setattr("builtins.input", _input_mock(["第一问", "第二问", "q"]))
        handlers_qa._qa_input_loop("报告.html")
        assert calls[0]["session_id"] is None  # 首轮无续传
        assert calls[1]["session_id"] == "sid-42"  # 次轮续传同一会话
        assert "追问结束（共 2 轮" in capsys.readouterr().out

    def test_empty_or_q_exits_without_call(self, monkeypatch, capsys, calls):
        self._patch_ask(monkeypatch, calls, [_ok_result()])
        monkeypatch.setattr("builtins.input", _input_mock([""]))
        handlers_qa._qa_input_loop("报告.html")
        assert calls == []
        assert "追问结束" not in capsys.readouterr().out

    def test_transient_error_continues_loop(self, monkeypatch, capsys, calls):
        self._patch_ask(
            monkeypatch,
            calls,
            [
                {"ok": False, "error_code": "QA_LLM_FAILED", "error": "服务暂不可用（本次未产出有效回答）"},
                _ok_result(turns=1),
            ],
        )
        monkeypatch.setattr("builtins.input", _input_mock(["重试一问", "下一问", "q"]))
        handlers_qa._qa_input_loop("报告.html")
        out = capsys.readouterr().out
        assert "[!] 服务暂不可用" in out and "结论 A" in out
        assert len(calls) == 2  # 失败不中断会话，可继续提问

    def test_session_limit_exits_loop(self, monkeypatch, capsys, calls):
        self._patch_ask(
            monkeypatch,
            calls,
            [{"ok": False, "error_code": "QA_SESSION_LIMIT", "error": "本轮对话已达 10 轮上限，请刷新页面开始新会话"}],
        )
        monkeypatch.setattr("builtins.input", _input_mock(["再问一句"]))
        handlers_qa._qa_input_loop("报告.html")
        out = capsys.readouterr().out
        assert "已达 10 轮上限" in out and "会话已达上限" in out
        assert len(calls) == 1  # 上限终止后不再等待输入

    def test_fact_warning_printed(self, monkeypatch, capsys, calls):
        self._patch_ask(monkeypatch, calls, [_ok_result(fact_warning=True)])
        monkeypatch.setattr("builtins.input", _input_mock(["数值核对？", "q"]))
        handlers_qa._qa_input_loop("报告.html")
        assert "未能与报告数据完全核对一致" in capsys.readouterr().out


# ── HTML → 纯文本 ────────────────────────────────────────────


class TestHtmlToText:
    """终端展示用 HTML 剥离。"""

    def test_block_tags_become_lines_and_script_dropped(self):
        html = "<p>第一段</p><script>alert(1)</script><div>第二段</div><style>.x{}</style>"
        text = handlers_qa._html_to_text(html)
        assert text == "第一段\n第二段"
        assert "alert" not in text and ".x" not in text

    def test_table_cells_flattened(self):
        text = handlers_qa._html_to_text("<tr><td>行1列1</td><td>行1列2</td></tr>")
        assert "行1列1" in text and "行1列2" in text

    def test_empty_input(self):
        assert handlers_qa._html_to_text("") == ""
        assert handlers_qa._html_to_text(None) == ""


# ── 同源接线与菜单门控 ────────────────────────────────────────


class TestSameServiceWiring:
    """与 Web 同源：同一会话服务，无 TUI 私有副本（阶段验收项）。"""

    def test_uses_shared_session_service_object(self):
        from src.python.qa import session as qa_session

        assert handlers_qa.ask_report_qa is qa_session.ask_report_qa

    def test_no_private_qa_copies_in_module(self):
        for banned in (
            "call_llm",
            "QaSession",
            "create_report_qa_session",
            "markdown_to_html",
            "run_fact_check",
            "_sessions",
            "extract_report_qa_context",
        ):
            assert banned not in vars(handlers_qa), f"handlers_qa 出现私有副本符号：{banned}"


class TestMenuGating:
    """菜单项注册与 `report_qa` 开关门控（裁剪同源）。"""

    def _with_menu(self, monkeypatch, enabled_keys: set[str]):
        """临时重放菜单门控（就地裁剪，测试内保存/还原 MENU_ITEMS）。"""
        from src.python.tui import tui_menu

        original = list(tui_menu.MENU_ITEMS)
        monkeypatch.setattr(
            "src.python.config.features.is_feature_enabled",
            lambda key, _on=enabled_keys: key in _on,
        )
        try:
            tui_menu._apply_feature_gates()
            return tui_menu.MENU_ITEMS[:]
        finally:
            tui_menu.MENU_ITEMS[:] = original

    def test_menu_contains_q_entry(self):
        from src.python.tui import tui_menu

        keys = [item[0] for item in tui_menu.MENU_ITEMS]
        assert "Q" in keys
        label = next(item[1] for item in tui_menu.MENU_ITEMS if item[0] == "Q")
        assert "追问" in label

    def test_q_gated_by_report_qa_switch(self, monkeypatch):
        from src.python.tui import tui_menu

        assert tui_menu.FEATURE_GATED_ITEMS.get("Q") == "report_qa"
        # 开关开（含 doctor_check 开）→ Q 保留
        visible = self._with_menu(monkeypatch, {"report_qa", "doctor_check"})
        assert "Q" in {item[0] for item in visible} and "T" in {item[0] for item in visible}
        # 开关关 → Q 与 T 一并就地裁剪
        hidden = self._with_menu(monkeypatch, set())
        assert "Q" not in {item[0] for item in hidden} and "T" not in {item[0] for item in hidden}
