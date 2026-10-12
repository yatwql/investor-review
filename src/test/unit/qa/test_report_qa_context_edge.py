"""report_qa_context 边缘/异常场景 — 路径净化 / 文件缺失 / 锚点缺失 / 上限钉死。"""

from __future__ import annotations

import pytest

import src.python.qa.context as context_mod
from src.python.qa.context import (
    _CAP_MARK,
    _QA_CONTEXT_CHAR_CAP,
    ReportQaContextError,
    extract_report_qa_context,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_qa,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestPathGuard:
    """路径净化（与 Web 路由同款语义的双层防御）。"""

    @pytest.mark.parametrize("bad", ["../evil.html", "sub/dir.html", "a\\b.html", "", ".."])
    def test_illegal_report_name_rejected(self, tmp_path, bad):
        with pytest.raises(ReportQaContextError) as excinfo:
            extract_report_qa_context(bad, output_dir=str(tmp_path))
        assert excinfo.value.code == "QA_BAD_REPORT"

    @pytest.mark.parametrize("bad", ["notes.txt", "report.html.exe", "noext"])
    def test_non_html_suffix_rejected(self, tmp_path, bad):
        with pytest.raises(ReportQaContextError) as excinfo:
            extract_report_qa_context(bad, output_dir=str(tmp_path))
        assert excinfo.value.code == "QA_BAD_REPORT"

    def test_missing_file_reports_not_found(self, tmp_path):
        with pytest.raises(ReportQaContextError) as excinfo:
            extract_report_qa_context("不存在.html", output_dir=str(tmp_path))
        assert excinfo.value.code == "QA_REPORT_NOT_FOUND"
        assert "报告" in str(excinfo.value)


class TestStructureGuard:
    """锚点缺失 → 结构不可解析（显式报错，不静默给空上下文）。"""

    def test_html_without_section_anchors_raises_invalid(self, tmp_path):
        path = tmp_path / "无结构.html"
        path.write_text("<html><body><p>一大段没有章节锚点的旧版正文。</p></body></html>", encoding="utf-8")
        with pytest.raises(ReportQaContextError) as excinfo:
            extract_report_qa_context("无结构.html", output_dir=str(tmp_path))
        assert excinfo.value.code == "QA_CONTEXT_INVALID"

    def test_empty_file_raises_invalid(self, tmp_path):
        path = tmp_path / "空.html"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ReportQaContextError) as excinfo:
            extract_report_qa_context("空.html", output_dir=str(tmp_path))
        assert excinfo.value.code == "QA_CONTEXT_INVALID"


class TestCapBoundary:
    """整体上下文字符上限（超限截尾 + 截断声明标记）。"""

    def test_global_cap_enforced_with_mark(self, tmp_path, monkeypatch):
        html = (
            "<html><head><title>长报告</title></head><body>"
            '<div class="section" id="sec-summary">'
            '<div class="section-title">汇总</div><p>' + "正文。" * 400 + "</p></div>"
            '<div class="section" id="sec-penetration">'
            '<div class="section-title">穿透</div><p>' + "穿透。" * 400 + "</p></div>"
            "</body></html>"
        )
        path = tmp_path / "长报告.html"
        path.write_text(html, encoding="utf-8")
        monkeypatch.setattr(context_mod, "_QA_CONTEXT_CHAR_CAP", 300)
        ctx = extract_report_qa_context("长报告.html", output_dir=str(tmp_path))
        assert len(ctx.text) <= 300 + len(_CAP_MARK)
        assert _CAP_MARK in ctx.text

    def test_default_cap_is_positive_bound(self):
        assert 0 < _QA_CONTEXT_CHAR_CAP < 200_000
