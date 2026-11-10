"""`scripts/_eval_halluc_sampler/from_report.py` — 既有报告重放（零 LLM）单元测试。

重放的用途：不花钱、可复现地对一份已生成报告重跑确定性核对，回答「多少收益率声称
被真正比对过、哪些与持仓真值不符」。因此本文件只测解析与编排，**不触发任何 LLM 调用**。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    # sampler 包内部是扁平 import（`_eval_halluc_sampler.*`），注入 scripts/ 才能加载
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _eval_halluc_sampler.from_report import (  # noqa: E402
    _extract_holdings_details,
    _extract_sections,
    run_from_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_ROW_TMPL = (
    "<tr><td>证券账户</td><td>{name}</td><td>{code}</td><td>1.0</td><td>2026-11-10</td>"
    "<td>1.0</td><td>行情</td><td>—</td><td>100</td><td>{mv}</td><td>{cost}</td>"
    "<td>{profit}</td><td>{rate}</td><td>0</td><td>tencent</td><td>—</td><td>开放申购</td></tr>"
)

_HEADER = (
    "<thead><tr><th>账户</th><th>名称</th><th>代码</th><th>最新价</th><th>净值日期</th><th>昨日价</th>"
    "<th>取价方式</th><th>溢价率</th><th>份额</th><th>市值</th><th>成本</th><th>盈亏</th><th>收益率</th>"
    "<th>本日盈亏</th><th>取价渠道</th><th>资金加权成本</th><th>申购状态</th></tr></thead>"
)


def _report(module_body: str = "<p>017730 收益率 -5.06%</p>") -> str:
    rows = _ROW_TMPL.format(
        name="嘉实全球产业升级股票(QDII)A",
        code="017730",
        mv="23,941.69",
        cost="25,218.95",
        profit="-1,277.26",
        rate="-5.06",
    )
    return (
        "<html><body>"
        '<div class="section" id="sec-holdings_detail">'
        f"<table>{_HEADER}<tbody>{rows}</tbody></table></div>"
        '<div class="section" id="sec-global_macro">'
        f"<p>全球政经局势</p>{module_body}</div>"
        '<div class="section" id="sec-expert_review"><p>智囊团</p><p>017730 收益率 -8.5%</p></div>'
        "</body></html>"
    )


class TestReportParsing:
    def test_sections_are_split_by_anchor(self):
        sections = _extract_sections(_report())
        assert "global_macro" in sections and "holdings_detail" in sections
        assert "017730 收益率 -5.06%" in sections["global_macro"]
        assert "017730 收益率 -8.5%" in sections["expert_review"]

    def test_holdings_parsed_from_report_table(self):
        """持仓取自报告自身表格（重放要用当时的数字，不是今天的价格）。"""
        holdings = _extract_holdings_details(_extract_sections(_report()))
        assert holdings == [
            {
                "name": "嘉实全球产业升级股票(QDII)A",
                "code": "017730",
                "market_value": 23941.69,
                "cost": 25218.95,
                "profit": -1277.26,
                "profit_rate": -5.06,
            }
        ]


class TestRunFromReport:
    def test_missing_file_returns_error_code(self):
        assert run_from_report("/nonexistent/report.html") == 2

    def test_report_without_sections_returns_error_code(self, tmp_path):
        target = tmp_path / "empty.html"
        target.write_text("<html><body>无章节</body></html>", encoding="utf-8")
        assert run_from_report(str(target)) == 2

    def test_replay_writes_coverage_and_issues(self, tmp_path):
        """重放产出：覆盖率表 + 告警明细（含被修正的错值原句）。"""
        src = tmp_path / "report.html"
        src.write_text(_report(), encoding="utf-8")
        out = tmp_path / "det-check.md"

        assert run_from_report(str(src), str(out)) == 0
        text = out.read_text(encoding="utf-8")
        assert "总体覆盖率" in text
        assert "| 模块 | 百分比声称 |" in text
        assert "017730" in text, "与持仓真值不符的声称必须出现在告警明细里"


class TestDumpSkipped:
    """跳过声称抽样导出：改规则前先用它看证据（真非收益 / 漏关键词 / 漏归因）。"""

    def test_dump_lists_skipped_claims_with_context(self, tmp_path):
        src = tmp_path / "report.html"
        src.write_text(_report("<p>建设银行 18.7% 超线，行业集中度偏高</p>"), encoding="utf-8")
        out = tmp_path / "det-check.md"

        assert run_from_report(str(src), str(out), dump_skipped="all") == 0
        text = out.read_text(encoding="utf-8")
        assert "## 跳过声称抽样" in text
        assert "18.7%" in text, "被跳过的声称必须连同前文一起导出，否则无法人工判定"

    def test_without_flag_no_dump_section(self, tmp_path):
        src = tmp_path / "report.html"
        src.write_text(_report(), encoding="utf-8")
        out = tmp_path / "det-check.md"

        assert run_from_report(str(src), str(out)) == 0
        assert "跳过声称抽样" not in out.read_text(encoding="utf-8")
