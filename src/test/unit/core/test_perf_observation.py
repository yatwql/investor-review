"""运行观测面单元测试（core/perf.py 的 breakdown / counters / 日志采集）。

测试目标：
  - PhaseBreakdownRecorder：子项累加、非法输入忽略、并发写不丢计数
  - PerfCollector.recorder：同父阶段复用同一实例、快照按父阶段归集
  - 诊断计数：count/inc_warning/note_error 与 errors 截断上限
  - 日志采集：WARNING/ERROR 自动入计数、save 后摘除 handler
  - 口径不变：breakdown/counters 不参与 total_seconds

运行：
  pytest src/test/unit/core/test_perf_observation.py -v
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from src.python.core.perf import PerfCollector, PhaseBreakdownRecorder

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestPhaseBreakdownRecorder:
    """子项记录器：累加、非法输入、并发安全。"""

    def test_records_accumulate_per_name(self):
        rec = PhaseBreakdownRecorder("LLM+新闻")
        rec.record("持仓体检报告", 10.0)
        rec.record("持仓体检报告", 2.5)
        rec.record("新闻获取", 3.0)
        assert rec.spans() == {"持仓体检报告": 12.5, "新闻获取": 3.0}

    @pytest.mark.parametrize("bad", [None, "abc", -1.0, float("nan"), float("inf")])
    def test_invalid_seconds_ignored(self, bad):
        rec = PhaseBreakdownRecorder("LLM+新闻")
        rec.record("模块", bad)
        assert rec.spans() == {}

    def test_counters_accumulate(self):
        rec = PhaseBreakdownRecorder("LLM+新闻")
        rec.count("retry")
        rec.count("retry", 2)
        assert rec.counters() == {"retry": 3}

    def test_spans_and_counters_return_copies(self):
        rec = PhaseBreakdownRecorder("LLM+新闻")
        rec.record("模块", 1.0)
        rec.spans()["模块"] = 999.0
        assert rec.spans()["模块"] == 1.0

    def test_concurrent_records_do_not_lose_counts(self):
        """四模块在线程池中并发写：累加不得丢更新（锁保护）。"""
        rec = PhaseBreakdownRecorder("LLM+新闻")
        threads = [threading.Thread(target=lambda: [rec.record("模块", 1.0) for _ in range(200)]) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert rec.spans()["模块"] == pytest.approx(800.0)


class TestCollectorRecorderRegistry:
    """collector.recorder：实例复用与快照归集。"""

    def test_same_parent_phase_reuses_instance(self):
        perf = PerfCollector(report_type="full", holdings=[])
        assert perf.recorder("LLM+新闻") is perf.recorder("LLM+新闻")

    def test_snapshot_groups_spans_by_parent_phase(self):
        perf = PerfCollector(report_type="full", holdings=[])
        perf.recorder("LLM+新闻").record("持仓体检报告", 40.0)
        perf.recorder("数据准备").record("行情", 4.0)
        snap = perf.snapshot().to_json()
        assert snap["breakdown"] == {"LLM+新闻": {"持仓体检报告": 40.0}, "数据准备": {"行情": 4.0}}

    def test_empty_recorder_omitted_from_breakdown(self):
        perf = PerfCollector(report_type="full", holdings=[])
        perf.recorder("LLM+新闻")
        assert perf.snapshot().to_json()["breakdown"] == {}

    def test_breakdown_does_not_affect_total_seconds(self):
        """口径锁定：细分与计数是旁路观测面，不参与 total_seconds。"""
        perf = PerfCollector(report_type="full", holdings=[])
        perf.start("LLM+新闻")
        perf.recorder("LLM+新闻").record("持仓体检报告", 999.0)
        perf.recorder("LLM+新闻").count("retry", 5)
        perf.stop()
        snap = perf.snapshot().to_json()
        assert snap["total_seconds"] == pytest.approx(snap["phases"]["LLM+新闻"])
        assert snap["total_seconds"] < 999.0

    def test_recorder_counters_merge_into_snapshot_counters(self):
        perf = PerfCollector(report_type="full", holdings=[])
        perf.recorder("LLM+新闻").count("retry", 2)
        perf.count("retry")
        assert perf.snapshot().to_json()["counters"]["retry"] == 3


class TestDiagnosticCounters:
    """诊断计数：warnings/errors 与 errors 截断。"""

    def test_inc_warning_and_count_share_bucket(self):
        perf = PerfCollector(report_type="basic", holdings=[])
        perf.inc_warning()
        perf.count("warnings", 2)
        snap = perf.snapshot().to_json()
        assert snap["counters"]["warnings"] == 3
        assert snap["warnings_count"] == 3

    def test_note_error_records_message_and_counter(self):
        perf = PerfCollector(report_type="basic", holdings=[])
        perf.note_error("Excel 报告生成失败")
        snap = perf.snapshot().to_json()
        assert snap["errors"] == ["Excel 报告生成失败"]
        assert snap["counters"]["errors"] == 1

    def test_add_error_delegates_to_note_error(self):
        perf = PerfCollector(report_type="basic", holdings=[])
        perf.add_error("模块缺失")
        assert perf.snapshot().to_json()["counters"]["errors"] == 1

    def test_error_list_is_capped_but_counter_keeps_growing(self):
        """异常百出时字段不膨胀：列表封顶，计数照常累加。"""
        from src.python.core.perf import _MAX_CAPTURED_ERRORS

        perf = PerfCollector(report_type="basic", holdings=[])
        for i in range(_MAX_CAPTURED_ERRORS + 5):
            perf.note_error(f"错误 {i}")
        snap = perf.snapshot().to_json()
        assert len(snap["errors"]) == _MAX_CAPTURED_ERRORS
        assert snap["counters"]["errors"] == _MAX_CAPTURED_ERRORS + 5

    def test_long_error_message_truncated(self):
        from src.python.core.perf import _MAX_ERROR_MESSAGE_CHARS

        perf = PerfCollector(report_type="basic", holdings=[])
        perf.note_error("长" * (_MAX_ERROR_MESSAGE_CHARS + 50))
        assert len(perf.snapshot().to_json()["errors"][0]) == _MAX_ERROR_MESSAGE_CHARS


class TestLogCapture:
    """日志采集：WARNING/ERROR 自动入计数，save 后摘除。"""

    def test_warning_and_error_logged_during_run_are_counted(self):
        perf = PerfCollector(report_type="full", holdings=[])
        perf.start("数据准备")
        logger = logging.getLogger("invest")
        logger.warning("数据源降级")
        logger.error("模块缺失")
        perf.stop()
        snap = perf.snapshot().to_json()
        assert snap["counters"]["warnings"] == 1
        assert snap["counters"]["errors"] == 1
        assert "模块缺失" in snap["errors"]

    def test_handler_detached_after_save(self):
        """save 后摘除 handler：后续日志不再计入本次运行（也不泄漏 handler）。"""
        logger = logging.getLogger("invest")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "perf_history.jsonl")
            with patch("src.python.core.perf._PERF_HISTORY_FILE", path):
                perf = PerfCollector(report_type="basic", holdings=[])
                perf.start("Excel 生成")
                perf.stop()
                before = len(logger.handlers)
                perf.save()
                assert len(logger.handlers) == before - 1
                logger.warning("save 之后的告警")
                assert perf.snapshot().to_json()["counters"].get("warnings", 0) == 0

    def test_saved_record_carries_observation_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "perf_history.jsonl")
            with patch("src.python.core.perf._PERF_HISTORY_FILE", path):
                perf = PerfCollector(report_type="full", holdings=[])
                perf.start("LLM+新闻")
                perf.recorder("LLM+新闻").record("持仓体检报告", 40.0)
                logging.getLogger("invest").warning("降级")
                perf.stop()
                perf.save()
            record = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            assert record["breakdown"]["LLM+新闻"]["持仓体检报告"] == 40.0
            assert record["counters"]["warnings"] == 1
            assert record["warnings_count"] == 1
