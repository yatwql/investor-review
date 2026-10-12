"""report_qa_session 会话服务测试 — 编排/会话复用/历史折叠/用量记账/降级口径。

LLM 调用与事实核对全部 mock（零真实费用/零网络）；样本报告来自包内夹具。
"""

from __future__ import annotations

import ast
import threading
import time
from pathlib import Path

import pytest

import src.python.qa.session as qa_session
from src.python.qa.session import (
    _QA_MAX_TURNS,
    ask_report_qa,
    create_report_qa_session,
    report_qa_session_count,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa, pytest.mark.usefixtures("offline_external_sources")]

_MOCK_CONFIG = {"provider": "openai", "model": "test-model"}


class _LlmRecorder:
    """可编程 call_llm 替身：记录每次入参，返回预置答案/用量/渠道信息。"""

    def __init__(self, answer: str = "**要点**：按报告数据回答。", usage=None, provider=None, delay=0.0):
        self.calls: list[dict] = []
        self.answer = answer
        self.usage = usage if usage is not None else {"input_tokens": 100, "output_tokens": 50}
        self.provider = provider if provider is not None else {"name": "mock-provider", "model": "m"}
        self.delay = delay

    def __call__(self, system, user, config, max_tokens=None, http_client=None):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return self.answer, self.usage, self.provider


def _patch_llm(monkeypatch, recorder):
    monkeypatch.setattr(qa_session, "call_llm", recorder)
    return recorder


def _ask(output_dir, report, question, session_id=None, **kw):
    kw.setdefault("llm_config", _MOCK_CONFIG)
    return ask_report_qa(report, question, session_id, output_dir=output_dir, **kw)


class TestAskHappyPath:
    """单轮问答主链路（渲染/契约字段/账单/系统提示装配）。"""

    def test_single_turn_returns_rendered_answer_and_contract(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        result = _ask(output_dir, report, "本期汇率风险如何？")

        assert result["ok"] is True
        assert isinstance(result["session_id"], str) and result["session_id"]
        assert "<strong>要点</strong>" in result["answer_html"]  # Markdown → HTML
        assert "qa-answer-note" in result["answer_html"]  # 尾注（非实时声明）
        assert "qa-fact-warning" not in result["answer_html"]  # 干净回答无告警
        assert result["turns"] == 1
        assert result["remaining_turns"] == _QA_MAX_TURNS - 1
        assert result["usage"] == {"input_tokens": 100, "output_tokens": 50, "provider": "mock-provider"}
        assert result["fact_warning"] is False
        assert len(recorder.calls) == 1

    def test_system_prompt_carries_rules_declaration_and_report_text(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        _ask(output_dir, report, "我的持仓市值多少？")

        system = recorder.calls[0]["system"]
        assert "不给出仓位操作建议" in system  # 边界规则
        assert "【生成条件】" in system and "非实时" in system  # 生成条件声明
        assert "【本期报告内容】" in system
        assert "统计时间" in system  # 汇总章正文入上下文
        assert "沪深300ETF" in system  # 持仓明细表入上下文
        assert recorder.calls[0]["user"].endswith("我的持仓市值多少？")
        assert recorder.calls[0]["max_tokens"] is not None  # 回答长度受限

    def test_output_tokens_accumulate_across_turns(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        first = _ask(output_dir, report, "问题一")
        second = _ask(output_dir, report, "问题二", session_id=first["session_id"])

        assert second["session_id"] == first["session_id"]
        assert second["turns"] == 2
        assert second["usage"]["input_tokens"] == 200
        assert second["usage"]["output_tokens"] == 100
        assert len(recorder.calls) == 2


class TestHistory:
    """问答历史：同会话衔接、跨会话/跨报告隔离、更早问题折叠。"""

    def test_second_turn_user_prompt_contains_recent_history(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        first = _ask(output_dir, report, "第一问：汇率影响")
        _ask(output_dir, report, "第二问：债券占比", session_id=first["session_id"])

        second_prompt = recorder.calls[1]["user"]
        assert "【近期问答" in second_prompt
        assert "第一问：汇率影响" in second_prompt
        assert second_prompt.endswith("第二问：债券占比")

    def test_history_stores_markdown_plain_text_not_html(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        first = _ask(output_dir, report, "问题")
        _ask(output_dir, report, "追加问题", session_id=first["session_id"])

        second_prompt = recorder.calls[1]["user"]
        assert "<strong>" not in second_prompt  # 历史为 Markdown 源文本，无渲染标签
        assert "**要点**" in second_prompt

    def test_different_report_gets_fresh_session(self, qa_report, monkeypatch):
        report, report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())

        first = _ask(output_dir, report, "问题A")
        second = _ask(output_dir, report2, "问题B", session_id=first["session_id"])

        assert second["session_id"] != first["session_id"]  # 换报告不继承历史
        assert "【近期问答" not in recorder.calls[1]["user"]

    def test_unknown_session_id_creates_new_session(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder())

        result = _ask(output_dir, report, "问题", session_id="deadbeef0000")

        assert result["ok"] is True
        assert result["session_id"] != "deadbeef0000"

    def test_older_history_folds_to_question_list(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        recorder = _patch_llm(monkeypatch, _LlmRecorder())
        monkeypatch.setattr(qa_session, "_QA_HISTORY_TURNS", 2)

        sids = []
        for i in range(1, 4):
            result = _ask(output_dir, report, f"早期问题{i}", session_id=sids[-1] if sids else None)
            sids.append(result["session_id"])
        _ask(output_dir, report, "收尾问题", session_id=sids[-1])

        user = recorder.calls[3]["user"]
        assert "更早讨论过的问题" in user
        assert "早期问题1" in user  # 折叠清单只列问题
        assert "近期问答" in user
        assert "早期问题3" in user
        assert len(qa_session._sessions[sids[-1]].history) == 4  # 折叠只影响 prompt，不丢历史


class TestValidationAndFailures:
    """输入校验 / LLM 降级 / 失败不消耗轮次。"""

    def test_empty_question_rejected(self, qa_report):
        report, _report2, output_dir = qa_report
        result = _ask(output_dir, report, "   ")
        assert result["ok"] is False
        assert result["error_code"] == "QA_BAD_QUESTION"

    def test_overlong_question_rejected(self, qa_report):
        report, _report2, output_dir = qa_report
        result = _ask(output_dir, report, "长" * 1001)
        assert result["ok"] is False
        assert result["error_code"] == "QA_QUESTION_TOO_LONG"

    def test_unconfigured_llm_returns_unavailable_without_turn(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        monkeypatch.setattr(qa_session, "get_llm_config", lambda: None)

        result = ask_report_qa(report, "问题", output_dir=output_dir)

        assert result["ok"] is False
        assert result["error_code"] == "QA_LLM_UNAVAILABLE"
        assert report_qa_session_count() == 0  # 配置检查在会话创建之前

    def test_llm_no_content_fails_without_consuming_turn(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder(answer="   "))

        failed = _ask(output_dir, report, "问题")
        assert failed["ok"] is False
        assert failed["error_code"] == "QA_LLM_FAILED"

        _patch_llm(monkeypatch, _LlmRecorder())
        retried = _ask(output_dir, report, "问题", session_id=failed.get("session_id"))
        assert retried["ok"] is True
        assert retried["turns"] == 1  # 失败轮不计数，成功重试按新一轮计数


class TestFactCheck:
    """事实核对口径（只检不改 / 警示标注 / 异常降级原文）。"""

    def test_warning_summary_appends_quality_notice(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder())

        def _warn(_html, _holdings, **kw):
            return _html, "⚠ 事实校验：2/3 项提示"

        monkeypatch.setattr(qa_session, "run_fact_check", _warn)
        result = _ask(output_dir, report, "本期收益多少？")

        assert result["ok"] is True
        assert result["fact_warning"] is True
        assert "qa-fact-warning" in result["answer_html"]

    def test_fact_check_exception_degrades_to_original(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder())

        def _boom(*a, **kw):
            raise RuntimeError("校验器故障")

        monkeypatch.setattr(qa_session, "run_fact_check", _boom)
        result = _ask(output_dir, report, "问题")

        assert result["ok"] is True
        assert result["fact_warning"] is False
        assert "<strong>要点</strong>" in result["answer_html"]

    def test_holdings_baseline_feeds_fact_check(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder())
        captured = {}

        def _capture(_html, holdings, **kw):
            captured["holdings"] = holdings
            return _html, ""

        monkeypatch.setattr(qa_session, "run_fact_check", _capture)
        _ask(output_dir, report, "问题")

        assert [row["code"] for row in captured["holdings"]] == ["510300", "000001"]


class TestSessionTable:
    """会话表生命周期（登记/保留上限/清空）与并发隔离。"""

    def test_create_and_count_and_reset(self):
        s1 = create_report_qa_session("a.html")
        s2 = create_report_qa_session("b.html")
        assert report_qa_session_count() == 2
        assert s1.session_id != s2.session_id
        qa_session.reset_report_qa_sessions()
        assert report_qa_session_count() == 0

    def test_table_trimmed_at_keep_limit(self, monkeypatch):
        monkeypatch.setattr(qa_session, "_QA_SESSION_KEEP", 3)
        for i in range(5):
            create_report_qa_session(f"r{i}.html")
        assert report_qa_session_count() == 3

    def test_concurrent_asks_same_session_serialize_without_lost_turns(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(monkeypatch, _LlmRecorder(delay=0.02))
        session = create_report_qa_session(report)
        results: list[dict] = []
        lock = threading.Lock()

        def _worker(q):
            res = _ask(output_dir, report, q, session_id=session.session_id)
            with lock:
                results.append(res)

        threads = [threading.Thread(target=_worker, args=(f"并发问题{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 2
        assert all(r["ok"] for r in results)
        assert session.turns == 2  # 同会话串行，无丢轮
        assert len(session.history) == 2


class TestAccountingIsolation:
    """用量独立记账（架构边界：qa 不写报告周期 LLM 用量统计）。"""

    def test_session_module_does_not_import_report_llm_session(self):
        src = Path(qa_session.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert not any("llm.session" in mod for mod in imported)
        assert not any(mod and mod.endswith(".llm.usage") for mod in imported)


class TestPromptUsage:
    """用量字典语义（键名/累加口径——前端与诊断按此取数）。"""

    def test_usage_keys_stable_across_turns(self, qa_report, monkeypatch):
        report, _report2, output_dir = qa_report
        _patch_llm(
            monkeypatch,
            _LlmRecorder(usage={"input_tokens": 7, "output_tokens": 3}),
        )
        first = _ask(output_dir, report, "q1")
        second = _ask(output_dir, report, "q2", session_id=first["session_id"])
        assert set(second["usage"]) == {"input_tokens", "output_tokens", "provider"}
        assert second["usage"]["input_tokens"] == 14
        assert second["usage"]["output_tokens"] == 6
