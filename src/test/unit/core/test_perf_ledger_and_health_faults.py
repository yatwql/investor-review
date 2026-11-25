"""性能采集与台账读取的容错分支测试。

覆盖契约（`core/perf.py`）：
  - `warn_slow_write` 取产物大小时 stat 失败不打断告警（大小段留空）
  - `PerfCollector` 在并发预算观测不可用时不中断计时与快照
  - 阶段计时：未结束即再次 `start` 自动关闭前一阶段；无活跃阶段 `stop` 返回 None
  - JSONL 台账：文件不可读按空历史、空行跳过、坏行告警后跳过
  - `summarize_health_history` / `module_cost_summary` / `_phase_seconds` 对非预期
    记录形状（缺字段、类型不对、时间戳非法、费用取值异常）的跳过口径一致
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from src.python.core import perf

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


# ── warn_slow_write ──────────────────────────────────────


class TestWarnSlowWrite:
    def test_unreadable_product_path_keeps_warning_without_size(self, monkeypatch, caplog):
        """产物 stat 抛 OSError 时仍发出偏慢告警，只是不带产物大小段。"""

        def _boom(_path):
            raise OSError("stat failed")

        with monkeypatch.context() as m:
            m.setattr(perf.os.path, "isfile", _boom)
            with caplog.at_level("WARNING", logger=perf.logger.name):
                perf.warn_slow_write("HTML 页面写入", perf.SLOW_SPAN_WARN_SECONDS + 1, "/tmp/report.html")

        messages = [record.getMessage() for record in caplog.records if "偏慢" in record.getMessage()]
        assert len(messages) == 1
        assert "产物 " not in messages[0]


# ── PerfCollector 计时与快照 ─────────────────────────────


class TestPerfCollectorPhaseTiming:
    def test_start_twice_auto_closes_previous_phase(self):
        """前一阶段未 stop 即 start 新阶段，旧阶段被自动收尾并留在阶段表里。"""
        collector = perf.PerfCollector(report_type="basic", holdings=[])
        collector.start("行情获取")
        collector.start("分析计算")

        names = [record.name for record in collector.snapshot().phases]
        assert "行情获取" in names, "未结束的阶段应由第二次 start 自动关闭并记账"
        assert "分析计算" not in names, "当前阶段尚未 stop，不应出现在已完成阶段表"

    def test_stop_without_active_phase_returns_none(self):
        """无活跃阶段时 stop 返回 None（重复收尾不误记阶段）。"""
        collector = perf.PerfCollector(report_type="basic", holdings=[])

        assert collector.stop() is None
        assert collector.snapshot().phases == []

    def test_governor_begin_run_failure_does_not_block_timing(self, monkeypatch):
        """并发预算观测初始化失败只记调试日志，计时照常可用。"""
        from src.python.core.concurrency import GOVERNOR

        with monkeypatch.context() as m:
            m.setattr(GOVERNOR, "begin_run", mock.Mock(side_effect=RuntimeError("gov down")))
            collector = perf.PerfCollector(report_type="basic", holdings=[])

        collector.start("行情获取")
        assert collector.stop() is not None

    def test_governor_snapshot_failure_keeps_counters(self, monkeypatch):
        """读并发预算快照失败时快照仍可生成，只是缺 concurrency_* 计数。"""
        from src.python.core.concurrency import GOVERNOR

        collector = perf.PerfCollector(report_type="basic", holdings=[])
        with monkeypatch.context() as m:
            m.setattr(GOVERNOR, "snapshot", mock.Mock(side_effect=RuntimeError("gov down")))
            snapshot = collector.snapshot()

        assert snapshot.report_type == "basic"
        assert "concurrency_budget" not in snapshot.counters


# ── JSONL 台账读取 ──────────────────────────────────────


class TestJsonlLedgerRead:
    def test_unreadable_file_yields_empty_history(self, tmp_path, monkeypatch):
        """文件存在但打开失败（如正被换名）按空历史处理，不向上抛。"""
        ledger = tmp_path / "perf_history.jsonl"
        ledger.write_text("{}\n", encoding="utf-8")

        def _boom(*_args, **_kwargs):
            raise OSError("locked")

        with monkeypatch.context() as m:
            m.setattr("builtins.open", _boom)
            assert perf._load_jsonl_records(str(ledger), "perf") == []

    def test_blank_and_corrupt_lines_are_skipped(self, tmp_path):
        """空行跳过、坏行告警后跳过，好行照常返回。"""
        ledger = tmp_path / "perf_history.jsonl"
        ledger.write_text('{"a": 1}\n\n{not json\n{"a": 2}\n', encoding="utf-8")

        records = perf._load_jsonl_records(str(ledger), "perf")

        assert [record["a"] for record in records] == [1, 2]


# ── 健康历史摘要 ────────────────────────────────────────


class TestSummarizeHealthHistory:
    def test_failed_sources_capped_and_counts_derived(self, tmp_path, monkeypatch):
        """失败源清单截前 5 个，成功/失败计数在记录缺字段时由 sources 派生。"""
        ledger = tmp_path / "datasource_health.jsonl"
        sources = {f"src{i}": {"ok": i < 2} for i in range(7)}
        ledger.write_text(
            json.dumps({"timestamp": "2026-01-01T00:00:00", "sources": sources}) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(perf, "_HEALTH_CHECK_FILE", str(ledger))

        (summary,) = perf.summarize_health_history(limit=10)

        assert len(summary["failed_sources"]) == 5, "失败源最多列出前 5 个"
        assert summary["ok_count"] == 2
        assert summary["fail_count"] == 5

    def test_zero_limit_returns_no_summary(self, tmp_path, monkeypatch):
        """limit=0 表示不取样，返回空摘要列表。"""
        ledger = tmp_path / "datasource_health.jsonl"
        ledger.write_text(json.dumps({"sources": {"a": {"ok": True}}}) + "\n", encoding="utf-8")
        monkeypatch.setattr(perf, "_HEALTH_CHECK_FILE", str(ledger))

        assert perf.summarize_health_history(limit=0) == []


# ── 模块费用汇总 ────────────────────────────────────────


class TestModuleCostSummary:
    def test_ledger_read_failure_returns_empty(self, monkeypatch):
        """台账读取抛 OSError 时返回空汇总（调用方静默省略展示）。"""
        with monkeypatch.context() as m:
            m.setattr(perf, "load_history", mock.Mock(side_effect=OSError("io")))
            assert perf.module_cost_summary() == {}

    def test_records_with_unexpected_shapes_are_skipped(self, tmp_path):
        """时间戳非法 / llm 非字典 / modules 非字典 / 条目非字典 / 费用异常均跳过。"""
        ledger = tmp_path / "perf_history.jsonl"
        lines = [
            {"timestamp": "not-a-date", "llm": {"modules": {"good": {"costs": {"CNY": 1.0}}}}},
            {"timestamp": "2026-01-01T00:00:00", "llm": "bad"},
            {"timestamp": "2026-01-01T00:00:00", "llm": {"modules": ["bad"]}},
            {"timestamp": "2026-01-01T00:00:00", "llm": {"modules": {"skip": "bad"}}},
            {"timestamp": "2026-01-01T00:00:00", "llm": {"modules": {"zero": {"costs": {"CNY": 0}}}}},
        ]
        ledger.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")

        summary = perf.module_cost_summary(days=3650, path=str(ledger))

        assert set(summary) == {"good"}, "只有形状合法的条目进入汇总"
        assert summary["good"]["costs"]["CNY"]["total"] == pytest.approx(1.0)

    def test_cost_extraction_error_is_skipped(self, tmp_path, monkeypatch):
        """费用提取抛 ValueError 时跳过该条目，不影响同记录的其它条目。"""
        from src.python.core.costs import costs_of as real_costs_of

        ledger = tmp_path / "perf_history.jsonl"
        entry = {
            "timestamp": "2026-01-01T00:00:00",
            "llm": {"modules": {"bad": {"costs": {"CNY": 1.0}}, "good": {"costs": {"CNY": 2.0}}}},
        }
        ledger.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        def _costs_of(payload):
            if payload.get("costs", {}).get("CNY") == 1.0:
                raise ValueError("bad bucket")
            return real_costs_of(payload)

        monkeypatch.setattr("src.python.core.costs.costs_of", _costs_of)

        summary = perf.module_cost_summary(days=3650, path=str(ledger))

        assert set(summary) == {"good"}
        assert summary["good"]["runs"] == 1


# ── 阶段 ETA 的样本提取 ─────────────────────────────────


class TestPhaseSecondsShape:
    def test_non_dict_phases_yields_no_sample(self):
        """历史记录 phases 不是字典时不计样本（返回 None 而非抛异常）。"""
        assert perf._phase_seconds([1.0, 2.0], "行情获取") is None

    def test_eta_ignores_records_without_phase(self):
        """phases 为列表形状的记录被忽略，ETA 降级为 None。"""
        history = [{"report_type": "basic", "phases": [{"name": "行情获取", "seconds": 10.0}]}]

        assert perf.estimate_stage_eta("行情获取", 1.0, history=history) is None
