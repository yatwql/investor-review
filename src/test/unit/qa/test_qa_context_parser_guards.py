"""报告追问上下文解析器的容错分支单元测试（qa/context）。

锁住的契约：
  - script/style 区块内的标签一律不参与解析（开始/结束标签都是）
  - 未闭合的行容错落盘（下一 `<tr>` 开始时先收上一行）
  - `<br>` 结束当前文本行
  - 数值解析：净化后为空/纯符号 → None；无法转成浮点 → None（不抛）
  - 持仓表提取：非持仓章、表头缺必需列、行列数与表头不一致一律跳过
  - 空章节（trim 后无文本）不进上下文，避免拼接出空段落
"""

from __future__ import annotations

import pytest

from src.python.qa.context import (
    _HOLDINGS_SECTION_ID,
    _ReportHtmlParser,
    _extract_holdings,
    _to_float,
    extract_report_qa_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_qa]


def _parse(html: str) -> _ReportHtmlParser:
    parser = _ReportHtmlParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    return parser


class TestScriptStyleSkipping:
    def test_nested_tags_inside_script_are_ignored(self):
        parser = _parse(
            '<html><body><div id="sec-summary"><p>汇总正文</p>'
            "<script><div>脚本伪标签</div><br></script></div></body></html>"
        )

        summary_text = "\n".join(dict(parser.sections)["sec-summary"])

        assert "汇总正文" in summary_text
        assert "脚本伪标签" not in summary_text, "script 区块内的开始/结束标签都不得进入正文"

    def test_tag_events_during_skip_are_dropped(self):
        """跳过计数未归零时，任何开始/结束标签事件都不得改写缓冲（防守型契约）。"""
        parser = _parse('<html><body><div id="sec-summary"><p>汇总正文</p></div></body></html>')
        before = (list(parser.sections), list(parser.tables), list(parser._lines), parser._sid)
        parser._skip = 1

        parser.handle_starttag("div", [("id", "sec-injected")])
        parser.handle_endtag("div")

        assert (parser.sections, parser.tables, parser._lines, parser._sid) == before


class TestRowAndLineBuffering:
    def test_unclosed_previous_row_is_flushed_on_next_tr(self):
        parser = _parse(
            '<html><body><div id="sec-holdings_detail"><table>'
            "<tr><td>名称</td><td>代码</td></tr>"
            "<tr><td>沪深300</td><td>000300</td><tr><td>中证500</td><td>000905</td></tr>"
            "</table></div></body></html>"
        )

        table_rows = parser.tables[0][1]

        assert ["沪深300", "000300"] in table_rows, "未闭合行须容错落盘，不吞掉该行"

    def test_br_terminates_current_text_line(self):
        parser = _parse('<html><body><div id="sec-summary"><p>第一句<br>第二句</p></div></body></html>')

        lines = dict(parser.sections)["sec-summary"]

        assert "第一句" in lines and "第二句" in lines, "<br> 应断行而不是把两句粘成一行"


class TestToFloatTolerance:
    @pytest.mark.parametrize("raw", ["", "  ", "-", "+", ".", "-."])
    def test_blank_or_sign_only_yields_none(self, raw):
        assert _to_float(raw) is None

    def test_unparsable_number_yields_none(self):
        assert _to_float("1.2.3") is None


class TestExtractHoldingsGuards:
    def test_non_holdings_section_and_empty_table_are_skipped(self):
        tables = [("sec-summary", [["名称", "代码", "市值"]]), (_HOLDINGS_SECTION_ID, [])]

        assert _extract_holdings(tables) == []

    def test_header_missing_required_column_is_skipped(self):
        tables = [(_HOLDINGS_SECTION_ID, [["名称", "代码"], ["沪深300", "000300"]])]

        assert _extract_holdings(tables) == [], "缺市值列的表不是持仓明细表"

    def test_row_width_mismatch_is_skipped(self):
        tables = [
            (
                _HOLDINGS_SECTION_ID,
                [
                    ["名称", "代码", "市值"],
                    ["沪深300", "000300", "10000"],
                    ["中证500", "000905"],
                ],
            )
        ]

        holdings = _extract_holdings(tables)

        assert [h["code"] for h in holdings] == ["000300"]


class TestEmptySectionExcluded:
    def test_blank_section_contributes_no_text_block(self, tmp_path):
        html = '<html><body><div id="sec-blank">   </div><div id="sec-summary"><p>汇总正文</p></div></body></html>'
        (tmp_path / "报告.html").write_text(html, encoding="utf-8")

        ctx = extract_report_qa_context("报告.html", output_dir=str(tmp_path))

        assert "汇总正文" in ctx.text
        assert not ctx.text.startswith("\n\n"), "空章节不得在上下文开头留下空段落"
