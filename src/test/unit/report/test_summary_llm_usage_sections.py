# -*- coding: utf-8 -*-
"""LLM 用量页签（summary_llm_usage）的排版分支。

覆盖：生成后自检清单块（开关开/关两态）、缓存命中 Token 行、辩论模式行、
数据缓存命中率区块（有/无请求两态）、模块明细全空时整页签不写。

零网络、零真实报告：工作表用内存 Workbook。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from openpyxl import Workbook

from src.python.report import summary_llm_usage as usage_sheet

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _sheet_text(ws) -> str:
    return "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


def _module_info() -> list[dict]:
    return [
        {
            "name": "全球政经局势",
            "status": "success",
            "status_label": "成功",
            "model": "claude-sonnet",
            "total_tokens": 1200,
            "input_tokens": 900,
            "output_tokens": 300,
            "cache_hit_tokens": 0,
        }
    ]


def _session_usage(**overrides) -> dict:
    usage = {
        "has_usage": True,
        "call_count": 2,
        "model_display": "claude-sonnet",
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
        "cache_hit_tokens": 0,
        "cost_display": "¥0.12",
    }
    usage.update(overrides)
    return usage


class TestSelfReviewBlock:
    def test_block_rendered_line_by_line(self):
        wb = Workbook()
        ws = wb.active
        with (
            patch("src.python.llm.self_review.get_self_review_block", return_value="<p>第一行</p>\n<p>第二行</p>"),
            patch("src.python.report.llm_content.strip_html", return_value="第一行\n\n第二行"),
        ):
            usage_sheet.write_llm_usage_sheet(ws, _session_usage(), _module_info())
        text = _sheet_text(ws)
        assert usage_sheet._REVIEW_TITLE in text
        assert "第一行" in text
        assert "第二行" in text

    def test_no_block_keeps_sheet_clean(self):
        wb = Workbook()
        ws = wb.active
        with patch("src.python.llm.self_review.get_self_review_block", return_value=""):
            usage_sheet.write_llm_usage_sheet(ws, _session_usage(), _module_info())
        assert usage_sheet._REVIEW_TITLE not in _sheet_text(ws)


class TestSummarySection:
    def test_cache_hit_row_and_debate_mode(self):
        wb = Workbook()
        ws = wb.active
        usage = _session_usage(cache_hit_tokens=4096)
        with patch("src.python.llm.self_review.get_self_review_block", return_value=""):
            usage_sheet.write_llm_usage_sheet(ws, usage, _module_info(), debate_mode_label="六方辩论")
        text = _sheet_text(ws)
        assert "缓存命中 Token" in text
        assert "4,096" in text
        assert "实验模式" in text
        assert "六方辩论" in text

    def test_no_usage_section_skipped(self):
        wb = Workbook()
        ws = wb.active
        with patch("src.python.llm.self_review.get_self_review_block", return_value=""):
            usage_sheet.write_llm_usage_sheet(ws, {"has_usage": False}, _module_info())
        assert "▎汇总数据" not in _sheet_text(ws)


class TestCacheStatsSection:
    def test_populated_stats_block(self):
        wb = Workbook()
        ws = wb.active
        stats = {"total": 40, "hits": 30, "misses": 10, "rate": 0.75}
        with (
            patch("src.python.llm.self_review.get_self_review_block", return_value=""),
            patch.object(usage_sheet, "get_cache_hit_rate", return_value=stats),
        ):
            usage_sheet.write_llm_usage_sheet(ws, _session_usage(), _module_info())
        text = _sheet_text(ws)
        assert "▎数据缓存系统" in text
        assert "30 次" in text
        assert "10 次" in text
        assert "40 次" in text
        assert "75.0%" in text

    def test_zero_rate_displayed_as_dash(self):
        wb = Workbook()
        ws = wb.active
        stats = {"total": 5, "hits": 0, "misses": 5, "rate": 0.0}
        with (
            patch("src.python.llm.self_review.get_self_review_block", return_value=""),
            patch.object(usage_sheet, "get_cache_hit_rate", return_value=stats),
        ):
            usage_sheet.write_llm_usage_sheet(ws, _session_usage(), _module_info())
        rows = [[c.value for c in row][:2] for row in ws.iter_rows()]
        assert ["命中率", "—"] in rows

    def test_no_requests_section_absent(self):
        wb = Workbook()
        ws = wb.active
        with (
            patch("src.python.llm.self_review.get_self_review_block", return_value=""),
            patch.object(usage_sheet, "get_cache_hit_rate", return_value={"total": 0}),
        ):
            usage_sheet.write_llm_usage_sheet(ws, _session_usage(), _module_info())
        assert "▎数据缓存系统" not in _sheet_text(ws)


class TestEmptyModuleInfo:
    def test_sheet_left_untouched(self):
        wb = Workbook()
        ws = wb.active
        usage_sheet.write_llm_usage_sheet(ws, _session_usage(), [])
        assert ws.max_row == 1
        assert _sheet_text(ws) == ""
