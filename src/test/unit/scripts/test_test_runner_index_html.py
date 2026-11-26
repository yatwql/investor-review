"""`_test_runner/report_html.py` 汇总页渲染测试（`test-reports/latest/index.html`）。

覆盖：总体状态三态（全过 / 部分 / 超时接 -1）、逐模式行徽标与报告链接列、
归档与覆盖率备注的出现条件、排序按 `MODES` 的 order。

全部渲染到临时目录，不写仓库真实 `test-reports/`。
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="report_html")
def fixture_report_html():
    """经入口脚本加载（内部包按 `_test_runner.*` 绝对名导入，需入口的 sys.path 修补）。"""
    load_script("test-runner.py", module_name="test_runner_index_html_entry")
    return importlib.import_module("_test_runner.report_html")


@pytest.fixture(name="latest_dir")
def fixture_latest_dir(report_html, tmp_path, monkeypatch):
    latest = tmp_path / "latest"
    latest.mkdir()
    monkeypatch.setattr(report_html, "_LATEST_DIR", str(latest))
    monkeypatch.setattr(report_html, "_REPORTS_DIR", str(tmp_path))
    return latest


def _result(mode: str, *, exit_code: int = 0, passed: int = 10, failed: int = 0, duration: float = 1.5) -> dict:
    return {
        "mode": mode,
        "desc": f"{mode} 说明",
        "exit_code": exit_code,
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "errors": 0,
        "duration": duration,
    }


class TestOverallStatus:
    def test_all_passed(self, report_html):
        assert report_html._overall_status([_result("unit"), _result("regression")]) == ("PASS", "全部通过")

    def test_partial_reports_pass_ratio(self, report_html):
        status, desc = report_html._overall_status([_result("unit"), _result("regression", exit_code=2)])
        assert status == "PARTIAL"
        assert desc == "1/2 模式通过"

    def test_empty_results_treated_as_pass(self, report_html):
        assert report_html._overall_status([]) == ("PASS", "全部通过")


class TestReportLinks:
    def test_single_report_link(self, report_html, latest_dir):
        mode_dir = latest_dir / "unit"
        mode_dir.mkdir()
        (mode_dir / "report.html").write_text("<html></html>", encoding="utf-8")
        html = report_html._report_links_html("unit")
        assert html == '<a href="unit/report.html">📄 查看</a>'

    def test_phase_reports_each_linked(self, report_html, latest_dir):
        mode_dir = latest_dir / "dev-verify"
        mode_dir.mkdir()
        for tag in ("core", "scenario"):
            (mode_dir / f"report_phase_{tag}.html").write_text("<html></html>", encoding="utf-8")
        html = report_html._report_links_html("dev-verify")
        assert "Phase core" in html and "Phase scenario" in html
        assert html.index("Phase core") < html.index("Phase scenario"), "逐阶段按文件名排序"

    def test_no_report_placeholder(self, report_html, latest_dir):
        assert report_html._report_links_html("unit") == '<span class="dim">无</span>'


class TestRenderIndexHtml:
    def test_rows_badges_and_totals(self, report_html, latest_dir):
        results = [
            _result("regression", exit_code=2, passed=8, failed=2, duration=4.0),
            _result("unit", passed=20, duration=2.0),
            _result("integration", exit_code=-1, passed=0, duration=0.0),
        ]
        html = report_html._render_index_html(results, coverage=False, archive_path=None)
        assert "<!DOCTYPE html>" in html and "测试报告汇总" in html
        assert "badge-pass" in html and "FAIL (2)" in html and "超时" in html
        assert '<span class="badge badge-partial">PARTIAL</span>' in html
        assert "1/3 模式通过" in html
        assert '<span class="num" style="color:#155724;">28</span>' in html  # 通过合计
        assert '<span class="num" style="color:#721c24;">2</span>' in html  # 失败合计
        assert "6.0s" in html  # 耗时合计
        # 行按 MODES 的 order 排序（与传入顺序无关：传入是 regression → unit → integration）
        modes = ("unit", "integration", "regression")
        rendered_order = sorted(modes, key=lambda mode: html.index(f"<strong>{mode}</strong>"))
        declared_order = sorted(modes, key=lambda mode: report_html.MODES[mode]["order"])
        assert rendered_order == declared_order
        assert rendered_order != ["regression", "unit", "integration"], "排序应重排传入顺序"

    def test_notes_only_when_conditions_met(self, report_html, latest_dir, tmp_path):
        results = [_result("unit")]
        bare = report_html._render_index_html(results, coverage=False, archive_path=None)
        assert '<div class="note archive-note">' not in bare and '<div class="note cov-note">' not in bare
        assert "全部通过" in bare

        coverage_dir = latest_dir / "coverage"
        coverage_dir.mkdir()
        (coverage_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        archive = tmp_path / "archive" / "2026-10-08_1200"
        decorated = report_html._render_index_html(results, coverage=True, archive_path=str(archive))
        assert '<div class="note cov-note">' in decorated and "coverage/index.html" in decorated
        assert '<div class="note archive-note">' in decorated
        assert Path("archive/2026-10-08_1200").as_posix() in decorated

    def test_coverage_flag_without_report_omits_note(self, report_html, latest_dir):
        html = report_html._render_index_html([_result("unit")], coverage=True, archive_path=None)
        assert '<div class="note cov-note">' not in html, "覆盖率报告未生成时不得给出死链"
