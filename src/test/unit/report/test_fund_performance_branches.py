# -*- coding: utf-8 -*-
"""基金业绩页签：评级标色、排名数据源降级、候选比较子表各标注行。

补齐主表「评级→字色」映射的深绿分支、`build_perf_data_status` 全失败降级项，
以及候选比较子表（可用/不可用两态 + 报告期/陈旧基准/超限/无效代码四种标注）。

取数（批量排名/基准/候选数据）全部经替身注入，零网络。
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from openpyxl import Workbook

from src.python.core.models import Holding
from src.python.report import fund_performance as fp
from src.python.report.styles import DARK_GREEN_FONT

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _fund_holding(code: str = "005827", name: str = "蓝筹精选") -> Holding:
    return Holding(account="基金账户", name=name, code=code, shares=100.0, cost_price=2.0)


def _sheet_text(ws) -> str:
    return "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


class TestRatingFont:
    def test_worst_rating_dark_green(self):
        wb = Workbook()
        ws = wb.active
        rankings = {"rankings": {"近3月": {"return": -0.05}, "同类排名": {"rank": 900, "total": 1000}}}
        with (
            patch.object(fp, "fetch_fund_rankings", return_value={**rankings, "rating": "较差"}),
            patch.object(fp, "fetch_fund_benchmark", return_value="--"),
        ):
            rating = fp._write_one_fund_row(ws, 5, _fund_holding(), {})
        assert rating == "较差"
        assert ws.cell(row=5, column=10).font == DARK_GREEN_FONT


class TestPerfDataStatus:
    def test_all_rank_failures_record_degradation(self):
        tracker = Mock()
        tracker.record.return_value = (True, "龙", 1)
        with patch.object(fp, "_tracker", return_value=tracker), patch.object(fp, "get_ttl", return_value=0):
            status = fp.build_perf_data_status({}, 3)
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["failure_type"] == "empty"
        assert kwargs["cache_ttl_hours"] == pytest.approx(24)
        assert status["rank"]["available"] is False
        assert status["rank"]["tier"] == "T2"

    def test_all_rank_failures_but_not_degraded(self):
        tracker = Mock()
        tracker.record.return_value = (False, "", 1)
        with patch.object(fp, "_tracker", return_value=tracker), patch.object(fp, "get_ttl", return_value=7200):
            assert fp.build_perf_data_status({}, 3) == {}


class TestCandidateCompareBlock:
    def _candidate(self, **overrides) -> dict:
        row = {
            "code": "161725",
            "name": "白酒指数",
            "available": True,
            "rating": "良好",
            "rank_text": "120/900",
            "style": "价值",
            "overlap_name": "贵州茅台",
            "overlap_jaccard_raw": 0.35,
            "overlap_jaccard": "35%",
            "report_label": "2026Q3",
        }
        row.update(overrides)
        return row

    def test_rows_annotations_all_present(self):
        wb = Workbook()
        ws = wb.active
        data = {
            "available": True,
            "rows": [
                self._candidate(),
                {"code": "000002", "available": False},
            ],
            "report_label": "2026Q3",
            "stale_baseline_notes": ["某基金报告期 2019Q1"],
            "exceed_limit": True,
            "invalid": ["ABC123"],
        }
        next_row = fp._write_candidate_compare_block(ws, 2, data)
        text = _sheet_text(ws)
        assert "候选基金比较（比较对象由配置指定）" in text
        assert "白酒指数" in text
        assert "35%（贵州茅台）" in text
        assert "获取失败" in text  # 不可得候选写占位行
        assert "持仓报告期：2026Q3" in text
        assert "⚠ 现有持仓报告期陈旧" in text
        assert "候选基金超过 10 只，仅比较前 10 只" in text
        assert "无效候选代码（忽略）: ABC123" in text
        assert next_row > 2

    def test_overlap_missing_falls_back_to_dash(self):
        wb = Workbook()
        ws = wb.active
        data = {
            "available": True,
            "rows": [self._candidate(overlap_name="", overlap_jaccard_raw=None, report_label=None)],
        }
        fp._write_candidate_compare_block(ws, 2, data)
        text = _sheet_text(ws)
        assert "--" in text
        assert "2026Q3" not in text  # rows 无 report_label → 不写期标注

    def test_unavailable_block_explains_config(self):
        wb = Workbook()
        ws = wb.active
        row = fp._write_candidate_unavailable_block(ws, 2, {"available": False, "invalid": ["BAD1"]})
        text = _sheet_text(ws)
        assert "comparison_candidates" in text
        assert "无效候选代码已忽略：BAD1" in text
        assert row > 2


class TestMainSheetCandidateBranches:
    def _write(self, candidate_data) -> str:
        wb = Workbook()
        ws = wb.active
        holdings = [_fund_holding()]
        with (
            patch.object(
                fp,
                "fetch_fund_rankings_batch",
                return_value={"005827": {"rankings": {"近3月": {"return": 0.1}}, "rating": "良好"}},
            ),
            patch.object(fp, "fetch_fund_benchmark", return_value="沪深300"),
            patch.object(fp, "build_candidate_compare_data", return_value=candidate_data),
        ):
            fp.write_fund_performance_sheet(ws, holdings, [])
        return _sheet_text(ws)

    def test_available_candidate_block_written(self):
        text = self._write(
            {
                "available": True,
                "rows": [{"code": "161725", "name": "白酒指数", "available": True, "report_label": "2026Q3"}],
            }
        )
        assert "白酒指数" in text

    def test_unavailable_candidate_block_written(self):
        text = self._write({"available": False, "invalid": []})
        assert "未配置候选基金" in text

    def test_candidate_block_absent_when_switch_off(self):
        text = self._write(None)
        assert "候选基金比较" not in text
        assert "基金业绩" in text or "评级" in text
