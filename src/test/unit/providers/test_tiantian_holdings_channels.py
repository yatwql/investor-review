"""tiantian_holdings 通道产出 / 兜底跳 / 解析否弃的单源契约。

覆盖三处契约：
  - ``_quarter_channel_payloads`` 是生成器，调用方按「取到内容即 break」消费时
    只会走前半段；本文件按完整消费（``list``）锁定两个通道的产出次序与对冲后
    两侧内容的合并次序；
  - ``_fetch_default_quarter`` / ``fetch_quarterly_holdings`` 的第 3 跳兜底语义
    （日志回显 + 结果透传 + 全部无数据时的空返回）；
  - 主页表格与季报行解析中的否弃分支（时段标记表、列数不足行、空锚点行）。
"""

from __future__ import annotations

import threading
from datetime import datetime

import pytest

from src.python.providers import tiantian_holdings as th

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class TestHomepageTableParsingBranches:
    """主页表格/持仓行的否弃分支：命中即跳过，绝不产出伪持仓。"""

    def test_table_with_period_marker_skipped_but_data_rows_rescue(self):
        """含「近N年」时段标记的表被排除，同页数据行充足的表仍能被 rescue。"""
        html = (
            "<table><tr><td>近1年涨幅</td><td>12.34%</td></tr>"
            "<tr><td>近3月</td><td>5.00%</td></tr>"
            "<tr><td>占净值比例</td><td>1.00%</td></tr></table>"
            "<table>" + "".join(f"<tr><td>股票{i}</td><td>{i}.25%</td></tr>" for i in range(1, 7)) + "</table>"
        )

        table = th._find_holdings_table(html)

        assert table is not None
        assert "股票1" in table, "排除时段标记表后应回落到数据行充足的持仓表"
        assert "近1年涨幅" not in table

    def test_rows_without_name_or_cells_are_dropped(self):
        """列数不足的行、锚点内容为空的行都不产出持仓，合法行照常产出。"""
        table = (
            "<tr><td>只有一列</td></tr>"
            "<tr><td><a></a></td><td>3.00%</td></tr>"
            '<tr><td><a href="x">贵州茅台</a> stockcode="stock_600519"</td><td>12.50%</td></tr>'
        )

        holdings = th._parse_holdings_rows(table)

        assert holdings == [{"name": "贵州茅台", "code": "600519", "ratio": pytest.approx(12.5)}]


class TestQuarterAnchorWrap:
    """季度回溯窗口在 Q1 时跨年回退到上一年 Q4。"""

    def test_first_quarter_wraps_to_previous_year_q4(self):
        with th.quarter_walk_anchor(datetime(2026, 2, 15)):
            quarters = th._recent_quarters(2)

        assert quarters == [(2025, 12), (2025, 9)], "Q1 的最近完整季度锚点须落到上一年 Q4"


class TestChannelPayloadsFullConsumption:
    """完整消费生成器：两通道的产出次序与对冲后的合并次序。"""

    @staticmethod
    def _stub(monkeypatch, jj, zq):
        def _fake(code, api_type, year=None, month=None):
            return jj() if api_type == "jjcc" else zq()

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)

    def test_fast_jjcc_yields_both_channels(self, monkeypatch):
        """jjcc 快速返回内容时先产出 jjcc，再产出 zqcc 的递补内容。"""
        self._stub(monkeypatch, lambda: "jj", lambda: "zq")

        assert list(th._quarter_channel_payloads("011506", 2026, 9)) == [("jjcc", "jj"), ("zqcc", "zq")]

    def test_hedge_merges_both_sides_when_zqcc_arrives_first(self, monkeypatch):
        """对冲后 zqcc 先到且 jjcc 稍后带回内容：两侧内容都产出（zqcc 在前）。"""
        monkeypatch.setattr(th, "_HEDGE_AFTER_SECONDS", 0.0)
        release_jjcc = threading.Event()
        zqcc_started = threading.Event()

        def _jj():
            release_jjcc.wait(timeout=10)
            return "jj"

        def _zq():
            zqcc_started.set()
            return "zq"

        self._stub(monkeypatch, _jj, _zq)
        released: list[bool] = []

        def _release_after_hedge() -> None:
            released.append(zqcc_started.wait(timeout=10))
            release_jjcc.set()

        helper = threading.Thread(target=_release_after_hedge, name="fund-hold-hedge", daemon=True)
        helper.start()
        try:
            payloads = list(th._quarter_channel_payloads("012325", 2026, 9))
        finally:
            release_jjcc.set()
            helper.join(timeout=10)

        assert released == [True], "对冲须在 jjcc 未返回时发出 zqcc"
        assert payloads == [("zqcc", "zq"), ("jjcc", "jj")]

    def test_hedge_yields_none_pair_when_both_channels_empty(self, monkeypatch):
        """对冲后两通道皆空：产出 (jjcc, None) + (zqcc, None)，由调用方收口。"""
        monkeypatch.setattr(th, "_HEDGE_AFTER_SECONDS", 0.0)
        release_jjcc = threading.Event()
        zqcc_started = threading.Event()

        def _jj():
            release_jjcc.wait(timeout=10)
            return None

        def _zq():
            zqcc_started.set()
            return None

        self._stub(monkeypatch, _jj, _zq)

        def _release_after_hedge() -> None:
            zqcc_started.wait(timeout=10)
            release_jjcc.set()

        helper = threading.Thread(target=_release_after_hedge, name="fund-hold-empty", daemon=True)
        helper.start()
        try:
            payloads = list(th._quarter_channel_payloads("012325", 2026, 9))
        finally:
            release_jjcc.set()
            helper.join(timeout=10)

        assert payloads == [("jjcc", None), ("zqcc", None)]


class TestDefaultQuarterFallback:
    """第 3 跳（无年份兜底）的透传与回显。"""

    def test_success_echoes_report_date(self, monkeypatch, caplog):
        """兜底成功时回显报告期（诊断性兜底必须可见），并透传结构化结果。"""
        payload = {
            "code": "012325",
            "name": "某债基",
            "date": "2025-06-30",
            "holdings": [{"name": "债", "code": "", "ratio": 5.0}],
        }
        monkeypatch.setattr(th, "_fetch_single_quarter", lambda code, year=None, month=None: payload)

        with caplog.at_level("INFO", logger="invest"):
            result = th._fetch_default_quarter("012325")

        assert result is payload
        assert any("2025-06-30" in rec.getMessage() for rec in caplog.records), "兜底成功须回显报告期"

    def test_quarterly_holdings_reports_total_miss(self, monkeypatch, caplog):
        """年份域与兜底均无数据时返回 None，并回显「全部无有效持仓」。"""
        monkeypatch.setattr(th, "_fetch_dated_quarterly", lambda code: None)
        monkeypatch.setattr(th, "_fetch_default_quarter", lambda code: None)

        with caplog.at_level("INFO", logger="invest"):
            result = th.fetch_quarterly_holdings("012325")

        assert result is None
        assert any("全部无有效持仓" in rec.getMessage() for rec in caplog.records)


class TestQuarterlyRowRejection:
    """季报行缺代码或缺名称时否弃该行（不产出空代码持仓）。"""

    def test_row_without_code_or_name_dropped(self):
        html = "<table><tr><td>1</td><td>只有两列</td></tr><tr><td>1</td><td></td><td></td><td>8.00%</td></tr></table>"

        assert th._parse_quarterly_holdings(html) == []


class TestYearDomainChannelOutcomes:
    """年份域通道的短路成功与单通道异常（按空结果递补）。"""

    def test_dated_quarter_returns_first_hit(self, monkeypatch):
        """首个季度带回持仓即短路返回，不再回溯更早季度。"""
        calls: list[int] = []

        def _fake(code, api_type, year=None, month=None):
            calls.append(month)
            return (
                None
                if api_type == "zqcc"
                else "<a title='某基金'>截止至：2026-09-30"
                "<table><tr><td>1</td><td>600519</td><td>贵州茅台</td><td>8.00%</td></tr></table>"
            )

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)

        result = th._fetch_dated_quarterly("000001")

        assert result is not None and result["date"] == "2026-09-30"
        assert len(calls) == 1, f"首个季度命中后不应继续回溯：{calls}"

    def test_channel_exception_treated_as_empty(self, monkeypatch):
        """单通道抛异常按空结果处理，另一通道照常递补（异常不穿透链路）。"""

        def _fake(code, api_type, year=None, month=None):
            if api_type == "jjcc":
                raise ValueError("接口异常")
            return "zq"

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)

        assert list(th._quarter_channel_payloads("011506", 2026, 9)) == [("jjcc", None), ("zqcc", "zq")]

    def test_quarterly_holdings_short_circuits_on_dated_hit(self, monkeypatch):
        """年份域命中时 fetch_quarterly_holdings 不再触发第 3 跳兜底。"""
        dated = {
            "code": "000001",
            "name": "某基金",
            "date": "2026-09-30",
            "holdings": [{"name": "甲", "code": "1", "ratio": 5.0}],
        }
        monkeypatch.setattr(th, "_fetch_dated_quarterly", lambda code: dated)
        monkeypatch.setattr(th, "_fetch_default_quarter", lambda code: pytest.fail("年份域已命中，不应触发兜底"))

        assert th.fetch_quarterly_holdings("000001") is dated


class TestSecondChannelReportDateBackfill:
    """首个有内容的通道无报告期时，由下一通道补回报告期。"""

    def test_report_date_backfilled_from_later_channel(self, monkeypatch):
        jjcc_html = "<a title='某债基'>无报告期标注</a>"
        zqcc_html = (
            "<a title='某债基'>截止至：2026-09-30</a>"
            "<table><tr><td>1</td><td>112233</td><td>某债券</td><td>8.00%</td></tr></table>"
        )
        pages = [("jjcc", jjcc_html), ("zqcc", zqcc_html)]
        monkeypatch.setattr(th, "_quarter_channel_payloads", lambda code, year, month: iter(pages))

        result = th._fetch_single_quarter("012325", 2026, 9)

        assert result is not None
        assert result["date"] == "2026-09-30", "报告期须由后续通道补齐"
        assert result["holdings"][0]["ratio"] == pytest.approx(8.0)
