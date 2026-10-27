"""报告追问埋点（需求 R-QA-11）：账本记录、效果汇总与转正判据。

覆盖四类边界：
  - **记录**：字段齐全、只记问题字数不记正文、渠道/错误码、滚动上限
  - **容错**：写盘异常不外抛（埋点不得阻断追问）、坏行/非对象行跳过
  - **汇总**：无回答占比 / 失败码分布 / 渠道 / 平均轮数 / tokens / 降级率 / 判据逐条
  - **接线**：`ask_report_qa` 成功与失败各记一行，且返回值不暴露内部 `_telemetry`

时间窗过滤用「写入旧时间戳行」而非 freeze 时间，避免依赖时钟桩。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.python.qa import telemetry

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa]


@pytest.fixture(name="ledger")
def fixture_ledger(tmp_path, monkeypatch) -> Path:
    """把账本重定向到 tmp（`_QA_USAGE_PATH` 是模块级变量，路径隔离即状态隔离）。"""
    path = tmp_path / "qa_usage.jsonl"
    monkeypatch.setattr(telemetry, "_QA_USAGE_PATH", path)
    return path


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestRecordAttempt:
    """单条记录的字段与隐私边界。"""

    def test_writes_expected_fields_without_question_text(self, ledger):
        telemetry.record_attempt(
            channel="web",
            report="/abs/path/个人投资分析报告.html",
            ok=True,
            session_id="abcdef1234567890",
            rounds=2,
            input_tokens=1200,
            output_tokens=300,
            provider="deepseek-main",
            latency_ms=812.4,
            fact_warning=True,
            question_chars=17,
        )
        rows = _rows(ledger)
        assert len(rows) == 1
        row = rows[0]
        assert row["channel"] == "web"
        assert row["report"] == "个人投资分析报告.html", "只记 basename，不落目录"
        assert row["session"] == "abcdef12", "会话 id 只留前 8 位"
        assert row["rounds"] == 2 and row["ok"] is True
        assert row["in"] == 1200 and row["out"] == 300
        assert row["fact_warning"] is True
        assert row["q_chars"] == 17
        assert "question" not in row and "q" not in row, "问题正文不得落盘"
        assert isinstance(row["ts"], str) and row["ts"]

    def test_failure_row_keeps_error_code(self, ledger):
        telemetry.record_attempt(
            channel="tui",
            report="r.html",
            ok=False,
            error_code="QA_SESSION_LIMIT",
            question_chars=5,
        )
        row = _rows(ledger)[0]
        assert row["ok"] is False and row["code"] == "QA_SESSION_LIMIT"
        assert row["in"] == 0 and row["out"] == 0
        assert row["cost"] is None

    def test_write_failure_never_raises(self, ledger, monkeypatch):
        """埋点失败必须被吞掉——追问本身不能因账本不可写而失败。"""

        def _boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(telemetry, "append_jsonl_atomic", _boom)
        telemetry.record_attempt(channel="web", report="r.html", ok=True)
        assert not ledger.exists(), "写盘失败时不应留下半成品账本"


class TestSummarize:
    """汇总口径与转正判据。"""

    def test_empty_ledger_is_not_ready(self, ledger):
        summary = telemetry.summarize_qa_usage()
        assert summary["attempts"] == 0
        assert summary["verdict"]["ready"] is False
        assert all(check["passed"] is False for check in summary["verdict"]["checks"])

    def test_rates_channels_and_verdict(self, ledger):
        for _ in range(8):
            telemetry.record_attempt(channel="web", report="r.html", ok=True, rounds=1, fact_warning=False)
        telemetry.record_attempt(channel="web", report="r.html", ok=False, error_code="QA_LLM_FAILED")
        telemetry.record_attempt(channel="tui", report="r.html", ok=True, rounds=3, fact_warning=True)

        summary = telemetry.summarize_qa_usage()
        assert summary["attempts"] == 10 and summary["answered"] == 9 and summary["failed"] == 1
        assert summary["no_answer_rate"] == pytest.approx(0.1)
        assert summary["by_code"] == {"QA_LLM_FAILED": 1}
        assert summary["by_channel"]["web"] == {"attempts": 9, "ok": 8}
        assert summary["by_channel"]["tui"] == {"attempts": 1, "ok": 1}
        assert summary["avg_rounds"] == pytest.approx(round((8 * 1 + 3) / 9, 2), abs=1e-9), "avg_rounds 保留两位小数"
        assert summary["max_rounds"] == 3
        assert summary["fact_warning_rate"] == pytest.approx(round(1 / 9, 3), abs=1e-9), "降级率保留三位小数"
        # 样本 10 < 30 → 未达判据，但无回答与降级率两项本身达标
        checks = {c["name"]: c["passed"] for c in summary["verdict"]["checks"]}
        assert checks[f"提问量 ≥ {telemetry.PROMOTION_MIN_ATTEMPTS}"] is False
        assert all(c["passed"] for c in summary["verdict"]["checks"][1:])
        assert summary["verdict"]["ready"] is False

    def test_verdict_ready_when_thresholds_met(self, ledger):
        for _ in range(telemetry.PROMOTION_MIN_ATTEMPTS):
            telemetry.record_attempt(channel="web", report="r.html", ok=True, rounds=1)
        assert telemetry.summarize_qa_usage()["verdict"]["ready"] is True

    def test_days_window_filters_old_rows(self, ledger):
        telemetry.record_attempt(channel="web", report="r.html", ok=True)
        old = {"ts": (datetime.now() - timedelta(days=45)).isoformat(timespec="seconds"), "channel": "web", "ok": True}
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(old, ensure_ascii=False) + "\n")
        assert telemetry.summarize_qa_usage(days=30)["attempts"] == 1
        assert telemetry.summarize_qa_usage(days=60)["attempts"] == 2

    def test_corrupt_lines_are_skipped(self, ledger):
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text('not json\n[1,2]\n{"ok": true}\n', encoding="utf-8")
        summary = telemetry.summarize_qa_usage()
        assert summary["attempts"] == 1 and summary["answered"] == 1


class TestFormatSummary:
    """`doctor` 上屏文本。"""

    def test_empty_ledger_says_no_records(self, ledger):
        lines = telemetry.format_summary_block(telemetry.summarize_qa_usage())
        assert any("尚无记录" in line for line in lines)

    def test_non_empty_mentions_metrics_and_verdict(self, ledger):
        for _ in range(3):
            telemetry.record_attempt(channel="web", report="r.html", ok=True, rounds=1, input_tokens=100, output_tokens=10)
        text = "\n".join(telemetry.format_summary_block(telemetry.summarize_qa_usage()))
        assert "提问 3 次" in text
        assert "无回答占比 0.0%" in text
        assert "转正判据" in text
        assert "维持实验状态" in text


class TestAskReportQaWiring:
    """`ask_report_qa` 接线：成功/失败各记一行，且不泄漏内部字段。"""

    @staticmethod
    def _patch_impl(monkeypatch, result: dict):
        from src.python.qa import session

        monkeypatch.setattr(session, "_ask_report_qa_impl", lambda *a, **k: dict(result))
        return session

    def test_success_records_tokens_and_strips_internal_key(self, ledger, monkeypatch):
        session = self._patch_impl(
            monkeypatch,
            {
                "ok": True,
                "session_id": "sess-12345678",
                "answer_html": "<p>x</p>",
                "turns": 2,
                "fact_warning": False,
                "_telemetry": {"in_tokens": 900, "out_tokens": 120, "model": "", "provider": "deepseek-main"},
            },
        )

        result = session.ask_report_qa("r.html", "这只基金能加仓吗", channel="web")

        assert "_telemetry" not in result, "内部字段不得出现在返回值里"
        row = _rows(ledger)[0]
        assert row["channel"] == "web" and row["ok"] is True
        assert row["in"] == 900 and row["out"] == 120
        assert row["rounds"] == 2
        assert row["q_chars"] == len("这只基金能加仓吗")
        assert row["latency_ms"] >= 0

    def test_failure_records_code(self, ledger, monkeypatch):
        session = self._patch_impl(
            monkeypatch,
            {"ok": False, "error_code": "QA_LLM_FAILED", "error": "服务暂不可用"},
        )

        result = session.ask_report_qa("r.html", "问", channel="tui")

        assert result["ok"] is False
        row = _rows(ledger)[0]
        assert row["channel"] == "tui" and row["ok"] is False and row["code"] == "QA_LLM_FAILED"
