"""`scripts/probe-report-claims.py` 单元测试 —— 批量重放报告做确定性数值核对（只读、零 LLM）。

覆盖：报告选取（日期目录 / --since / --limit）、单份核对聚合、结果渲染与 CLI 退出码。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _eval_halluc_sampler import from_report  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_ROW = (
    "<tr><td>证券账户</td><td>嘉实全球产业升级股票(QDII)A</td><td>017730</td><td>1.0</td>"
    "<td>2026-11-10</td><td>1.0</td><td>行情</td><td>—</td><td>100</td><td>23,941.69</td>"
    "<td>25,218.95</td><td>-1,277.26</td><td>-5.06</td><td>0</td><td>tencent</td><td>—</td><td>开放申购</td></tr>"
)
_HEAD = (
    "<thead><tr><th>账户</th><th>名称</th><th>代码</th><th>最新价</th><th>净值日期</th><th>昨日价</th>"
    "<th>取价方式</th><th>溢价率</th><th>份额</th><th>市值</th><th>成本</th><th>盈亏</th><th>收益率</th>"
    "<th>本日盈亏</th><th>取价渠道</th><th>资金加权成本</th><th>申购状态</th></tr></thead>"
)


def _page(module_body: str) -> str:
    return (
        "<html><body>"
        f'<div class="section" id="sec-holdings_detail"><table>{_HEAD}<tbody>{_ROW}</tbody></table></div>'
        f'<div class="section" id="sec-global_macro"><p>{module_body}</p></div>'
        "</body></html>"
    )


@pytest.fixture(scope="module")
def claims_audit():
    from_report.extract_sections, from_report.extract_holdings_details  # noqa: B018 — 触发模块加载
    return load_script("probe-report-claims.py", module_name="probe_report_claims")


def _write_report(root: Path, day: str, name: str, body: str) -> Path:
    target = root / day / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_page(body), encoding="utf-8")
    return target


class TestSelectReports:
    def test_picks_newest_and_respects_limit(self, claims_audit, tmp_path):
        for day in ("20261101", "20261105", "20261110"):
            _write_report(tmp_path, day, f"个人投资分析报告-{day}-010101.html", "<p>017730 收益率 -5.06%</p>")

        picked = claims_audit.select_reports(str(tmp_path), limit=2)
        assert [Path(p).parent.name for p in picked] == ["20261110", "20261105"]

    def test_since_filter_drops_old_dates(self, claims_audit, tmp_path):
        _write_report(tmp_path, "20200101", "个人投资分析报告-20200101-010101.html", "<p>x</p>")
        _write_report(tmp_path, "20261110", "个人投资分析报告-20261110-010101.html", "<p>y</p>")

        picked = claims_audit.select_reports(str(tmp_path), limit=10, since_days=30)
        assert [Path(p).parent.name for p in picked] == ["20261110"]

    def test_ignores_non_report_files(self, claims_audit, tmp_path):
        (tmp_path / "20261110").mkdir(parents=True)
        (tmp_path / "20261110" / "调仓模拟-20261110-010101.html").write_text("<html></html>", encoding="utf-8")
        assert claims_audit.select_reports(str(tmp_path), limit=5) == []


class TestAuditReport:
    def test_collects_claims_and_issues(self, claims_audit, tmp_path):
        """带符号错值（-5.06% 写成 +18.0%）→ 计入告警，且持仓从报告表格解析。"""
        target = _write_report(tmp_path, "20261110", "个人投资分析报告-20261110-010101.html", "017730 收益率 +18.0%")

        row = claims_audit.audit_report(str(target))
        assert row["claims"] >= 1
        assert row["issues"] >= 1 and row["rewrites"] >= 1
        assert any("017730" in line for line in row["issue_lines"])

    def test_consistent_value_is_verified_without_issue(self, claims_audit, tmp_path):
        target = _write_report(tmp_path, "20261110", "个人投资分析报告-20261110-010101.html", "017730 收益率 -5.06%")

        row = claims_audit.audit_report(str(target))
        assert row["issues"] == 0 and row["rewrites"] == 0
        assert row["verified"] >= 1


class TestCli:
    def test_missing_reports_returns_error_code(self, claims_audit, tmp_path):
        assert claims_audit.main([str(tmp_path)]) == 2

    def test_output_file_written(self, claims_audit, tmp_path):
        _write_report(tmp_path, "20261110", "个人投资分析报告-20261110-010101.html", "017730 收益率 +18.0%")
        out = tmp_path / "audit.md"

        assert claims_audit.main([str(tmp_path), "--output", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
        assert "报告数值声称体检" in text and "告警明细" in text
