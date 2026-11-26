"""`_eval_halluc_sampler.from_report` 解析容错与落盘失败分支单元测试。

重放的价值全在「敢对任意一份历史报告跑」：解析器遇到非数字单元格、缺表头、
缺列、短行都必须退化成「该项不可得」而不是抛异常；落盘失败也必须以退出码 2
区分开「核对出告警」（退出码 0）。主流程与真实报告样例见 `test_eval_from_report.py`。
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
    _number,
    run_from_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{cell}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# ── 单元格数值解析 ──────────────────────────────────────────


def test_number_strips_formatting_and_rejects_placeholders():
    """千分位/货币/百分号可取数；占位符（—、空）返回 None 而不是 0。"""
    assert _number("1,234.5") == pytest.approx(1234.5)
    assert _number("¥-3.5") == pytest.approx(-3.5)
    assert _number("-5.06%") == pytest.approx(-5.06)
    assert _number("—") is None
    assert _number("") is None


# ── 持仓表解析的退化路径 ────────────────────────────────────


def test_holdings_absent_section_is_empty():
    assert _extract_holdings_details({}) == []
    assert _extract_holdings_details({"holdings_detail": ""}) == []


def test_holdings_section_without_table_is_empty():
    assert _extract_holdings_details({"holdings_detail": "<p>本节无表格</p>"}) == []


def test_holdings_table_without_code_header_is_empty():
    """无「代码」列无法定位品种 → 返回空（宁缺勿错配）。"""
    chunk = _table(["名称", "市值"], [["甲", "100"]])

    assert _extract_holdings_details({"holdings_detail": chunk}) == []


def test_holdings_row_shorter_than_code_column_is_skipped():
    """短行（列数不足）跳过；合法行照常解析，证明跳过是按行而非整表丢弃。"""
    chunk = _table(
        ["名称", "代码", "市值", "成本", "盈亏", "收益率"],
        [["短行"], ["嘉实全球产业升级股票(QDII)A", "017730", "23,941.69", "25,218.95", "-1,277.26", "-5.06"]],
    )

    holdings = _extract_holdings_details({"holdings_detail": chunk})

    assert len(holdings) == 1
    assert holdings[0]["code"] == "017730"
    assert holdings[0]["market_value"] == pytest.approx(23941.69)


def test_holdings_derives_rate_when_column_missing():
    """无「收益率」列时用 盈亏 ÷ 成本 补算（否则整表收益率为空，核对全被跳过）。"""
    chunk = _table(
        ["名称", "代码", "市值", "成本", "盈亏"],
        [["甲基金", "017730", "100", "50", "-5"]],
    )

    holdings = _extract_holdings_details({"holdings_detail": chunk})

    assert len(holdings) == 1
    assert holdings[0]["profit_rate"] == pytest.approx(-10.0)


# ── 落盘失败与打印分支 ──────────────────────────────────────


def _minimal_report(tmp_path: Path) -> Path:
    path = tmp_path / "report.html"
    path.write_text(
        '<html><body><div class="section" id="sec-global_macro"><p>全球政经局势正文</p></div></body></html>',
        encoding="utf-8",
    )
    return path


def test_write_failure_returns_exit_code_2(tmp_path):
    """输出落点不可写 → 退出码 2（核对告警是 0，落盘失败必须区分开）。"""
    report_path = _minimal_report(tmp_path)

    code = run_from_report(str(report_path), output_path=str(tmp_path))  # 目录当文件写 → OSError

    assert code == 2


def test_prints_rendered_markdown_when_no_output_path(tmp_path, capsys):
    """未指定落点 → Markdown 打到 stdout（便于管道/临时排查）。"""
    report_path = _minimal_report(tmp_path)

    code = run_from_report(str(report_path))

    assert code == 0
    out = capsys.readouterr().out
    assert "# 报告确定性核对（离线，零 LLM 调用）" in out
    assert "## " in out or "| 模块 |" in out
