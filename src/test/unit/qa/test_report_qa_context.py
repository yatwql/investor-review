"""report_qa_context 提取测试 — 锚点分章 / 表头名映射持仓 / 摘要截断 / 生成条件声明。

网络守卫下全程零取数（只读样本 HTML 文件）。
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.python.qa.context import (
    _QA_CONTEXT_CHAR_CAP,
    _TRUNC_MARK,
    ReportQaContextError,
    extract_report_qa_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa, pytest.mark.usefixtures("offline_external_sources")]


class TestSectionExtraction:
    """分章文本提取（章节/标题/时间行入上下文，噪声排除）。"""

    def test_sections_titles_and_time_rows_extracted(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert "投资分析汇总" in ctx.text
        assert "◆" in ctx.text  # 章标题前缀
        assert "统计时间" in ctx.text
        assert "2026-10-11 17:00" in ctx.text
        assert "全球宏观判断第一段" in ctx.text
        assert "专家复盘正文" in ctx.text

    def test_script_style_nav_noise_excluded(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert "alert_x" not in ctx.text
        assert "sec-noise" not in ctx.text
        assert "导航目录链接" not in ctx.text

    def test_declaration_carries_title_and_report(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert "个人投资分析报告" in ctx.declaration
        assert report in ctx.declaration
        assert "非实时" in ctx.declaration


class TestHoldingsBaseline:
    """持仓明细表 → 事实核对/上下文基线（按表头名映射，合计行剔除）。"""

    def test_rows_mapped_by_header_names_despite_optional_columns(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert ctx.holdings_details == [
            {
                "name": "沪深300ETF",
                "code": "510300",
                "market_value": 3900.0,
                "shares": 1000.0,
                "profit_rate": 5.2,
            },
            {
                "name": "某债券基金",
                "code": "000001",
                "market_value": 2000.0,
                "shares": 2000.0,
                "profit_rate": -1.1,
            },
        ]

    def test_total_row_without_code_excluded(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert all(row["code"] for row in ctx.holdings_details)
        assert all(row["name"] != "合计" for row in ctx.holdings_details)

    def test_structure_without_holdings_table_gives_empty_baseline(self, tmp_path):
        html = (
            "<html><head><title>t</title></head><body>"
            '<div class="section" id="sec-summary">'
            '<div class="section-title">1、汇总</div><p>仅有汇总。</p></div>'
            "</body></html>"
        )
        path = tmp_path / "简版报告.html"
        path.write_text(html, encoding="utf-8")
        ctx = extract_report_qa_context("简版报告.html", output_dir=str(tmp_path))
        assert ctx.holdings_details == []
        assert "仅有汇总" in ctx.text


class TestTruncation:
    """数据章摘要化 + LLM 章全文 + 整体字符上限的分层截断口径。"""

    def test_long_data_section_truncated_llm_section_kept(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert _TRUNC_MARK in ctx.text  # 超长数据章截断
        assert "专家复盘正文：组合波动主要来自权益仓位。" in ctx.text

    def test_context_within_global_cap(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert len(ctx.text) <= _QA_CONTEXT_CHAR_CAP

    def test_text_section_marker_prefix_present(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert "◆ 1、投资分析汇总" in ctx.text


class TestContractSurface:
    """值对象契约（冻结/字段完备——调用方按字段名取用）。"""

    def test_context_is_immutable_value_object(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        with pytest.raises(FrozenInstanceError):
            ctx.text = "x"  # type: ignore[misc]

    def test_report_field_echoes_request(self, qa_report):
        report, _report2, output_dir = qa_report
        ctx = extract_report_qa_context(report, output_dir=output_dir)
        assert ctx.report == report
        assert isinstance(ctx.holdings_details, list)

    def test_error_carries_machine_code(self):
        err = ReportQaContextError("x", code="QA_CONTEXT_INVALID")
        assert err.code == "QA_CONTEXT_INVALID"
        assert str(err) == "x"
