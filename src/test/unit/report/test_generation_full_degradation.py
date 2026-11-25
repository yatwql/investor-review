"""报告全量生成层的降级登记与观测计数测试。

覆盖 `_generation_full` 两个编排辅助：
  - `_fetch_sector_flow` — 行业资金流向的陈旧回退 / 正常 / 异常三态登记（失败不中断报告）
  - `_record_llm_stage_counters` — 事实校验修正数与 thinking 串行等待入 perf counters

取数、降级登记与 perf 采集全部替身，不发起真实网络请求。

运行：
  pytest src/test/unit/report/test_generation_full_degradation.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_MOD = "src.python.report._generation_full"


class TestFetchSectorFlow:
    """行业资金流向获取的三态降级登记。"""

    def _run(self, *, payload, failure: str | None, raises: bool = False):
        reporter = MagicMock()
        perf = MagicMock()
        fetch = MagicMock(side_effect=RuntimeError("boom")) if raises else MagicMock(return_value=payload)
        with (
            patch("src.python.fetcher.akshare.get_sector_fund_flow", fetch),
            patch("src.python.fetcher.akshare.sector_flow_failure", return_value=failure),
            patch("src.python.core.degradation.mark_data_used") as mock_used,
            patch("src.python.core.degradation.mark_data_unavailable") as mock_unavailable,
            patch("src.python.cache.operations.sector_flow_hint", return_value="暂不可用"),
        ):
            from src.python.report._generation_full import _fetch_sector_flow

            result = _fetch_sector_flow(reporter, perf)
        return result, reporter, perf, mock_used, mock_unavailable

    def test_stale_payload_marked_and_warned(self):
        """源不可达回退上次成功数据 → 以 stale 登记并给出陈旧告警。"""
        result, reporter, perf, mock_used, _ = self._run(payload=[{"行业": "银行"}], failure="stale")

        assert result == [{"行业": "银行"}]
        mock_used.assert_called_once_with("ff_sector_flow", "T4", freshness="stale")
        assert "上次成功数据" in reporter.warn.call_args.args[0]
        reporter.ok.assert_called_once()
        perf.start.assert_called_once()
        perf.stop.assert_called_once()

    def test_fresh_payload_no_stale_mark(self):
        """可用载荷未回退 → freshness 留空、不告警。"""
        result, reporter, _perf, mock_used, _ = self._run(payload=[{"行业": "银行"}], failure=None)

        assert result == [{"行业": "银行"}]
        mock_used.assert_called_once_with("ff_sector_flow", "T4", freshness="")
        reporter.warn.assert_not_called()

    def test_exception_degrades_without_raising(self):
        """取数异常 → 返回 None、登记不可用并告警，报告链路不中断。"""
        result, reporter, perf, _, mock_unavailable = self._run(payload=None, failure=None, raises=True)

        assert result is None
        mock_unavailable.assert_called_once_with(
            "ff_sector_flow", "T4", failure_type="unreachable", message="akshare（调用异常）"
        )
        assert "获取失败" in reporter.warn.call_args.args[0]
        perf.stop.assert_called_once()


class TestRecordLlmStageCounters:
    """事实校验修正数与 thinking 串行等待写入 perf counters。"""

    def test_correction_counts_and_thinking_wait_recorded(self):
        """有修正数与 thinking 等待 → 逐项入 counters（毫秒整数）。"""
        perf = MagicMock()
        with (
            patch(
                "src.python.llm.fact_checker.auto_correction_counts",
                return_value={"fact_fix_numeric": 2},
            ),
            patch(
                "src.python.llm.generators_orchestrator.thinking_wait_total_seconds",
                return_value=1.5,
            ),
        ):
            from src.python.report._generation_full import _record_llm_stage_counters

            _record_llm_stage_counters(perf)

        assert perf.count.call_args_list == [
            call("fact_fix_numeric", 2),
            call("llm_thinking_wait_ms", 1500),
        ]

    def test_zero_thinking_wait_not_recorded(self):
        """无 thinking 等待 → 不写 llm_thinking_wait_ms（不产生 0 值噪声）。"""
        perf = MagicMock()
        with (
            patch("src.python.llm.fact_checker.auto_correction_counts", return_value={}),
            patch(
                "src.python.llm.generators_orchestrator.thinking_wait_total_seconds",
                return_value=0.0,
            ),
        ):
            from src.python.report._generation_full import _record_llm_stage_counters

            _record_llm_stage_counters(perf)

        perf.count.assert_not_called()
