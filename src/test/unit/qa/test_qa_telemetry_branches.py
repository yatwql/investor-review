"""报告追问埋点的容错分支单元测试（qa/telemetry）。

锁住的契约：
  - 费用估算/计价表不可用 → 该条记录不带费用（None），埋点不抛
  - 报告名净化只取 basename；报告名为空或路径解析失败 → 空串（不落目录）
  - 币种混合判定只依赖可解析计价币种的模型；解析失败的模型被忽略而非致错
  - 账本读取：空行跳过、时间戳非法的行**不丢**（只跳过时间过滤）
  - 汇总上屏文本：失败码非空时单独一行列出（截断前 4 种）
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.python.qa import telemetry

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa]


class TestCostEstimateDegradation:
    def test_pricing_failure_yields_no_cost(self, monkeypatch):
        def _raise(*_a, **_k):
            raise RuntimeError("计价表不可用")

        monkeypatch.setattr("src.python.llm.pricing.compute_cost_value", _raise)

        assert telemetry._cost_of("model-x", 10, 20) is None


class TestBasenameSanitizing:
    def test_missing_report_name_is_empty(self):
        assert telemetry._basename(None) == ""
        assert telemetry._basename("") == ""

    def test_path_resolution_failure_is_empty(self, monkeypatch):
        class _BadPath:
            def __init__(self, _raw: str) -> None:
                raise ValueError("非法路径")

        monkeypatch.setattr(telemetry, "Path", _BadPath)

        assert telemetry._basename("a/b.html") == ""


class TestCurrencyMixed:
    def test_two_resolvable_currencies_is_mixed(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.llm.pricing.model_currency",
            lambda model: {"a": "CNY", "b": "USD"}[model],
        )

        assert telemetry._currency_mixed([{"model": "a"}, {"model": "b"}, {"model": ""}]) is True

    def test_unresolvable_model_is_ignored(self, monkeypatch):
        def _raise(_model):
            raise RuntimeError("定价表缺行")

        monkeypatch.setattr("src.python.llm.pricing.model_currency", _raise)

        assert telemetry._currency_mixed([{"model": "a"}]) is False


class TestLoadRecords:
    def test_blank_lines_skipped_and_bad_timestamp_kept(self, tmp_path):
        ledger = tmp_path / "qa_usage.jsonl"
        now_ts = datetime.now().isoformat(timespec="seconds")
        ledger.write_text(
            f'{{"ts": "{now_ts}", "ok": true, "channel": "web"}}\n'
            "\n"
            '{"ts": "not-a-timestamp", "ok": false, "channel": "tui"}\n',
            encoding="utf-8",
        )

        rows = telemetry._load_records(days=30, path=ledger)

        assert [row["channel"] for row in rows] == ["web", "tui"], "坏时间戳只跳过时间过滤，不丢记录"


class TestSummaryBlockFailureCodes:
    def test_failure_codes_rendered_as_own_line(self):
        summary = {
            "attempts": 3,
            "answered": 2,
            "failed": 1,
            "no_answer_rate": 0.333,
            "by_code": {"qa_timeout": 1},
            "by_channel": {},
            "avg_rounds": 2.0,
            "max_rounds": 3,
            "avg_input_tokens": 10,
            "avg_output_tokens": 5,
            "total_tokens": 45,
            "total_cost": 0.01,
            "currency_mixed": False,
            "fact_warning_rate": 0.0,
            "verdict": {"ready": False, "checks": []},
        }

        lines = telemetry.format_summary_block(summary)

        assert any(line.startswith("  失败码：") and "qa_timeout ×1" in line for line in lines)
