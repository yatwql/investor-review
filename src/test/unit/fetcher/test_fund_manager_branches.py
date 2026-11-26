"""fund_manager 残余分支 — 无链接经理名回退、首页请求失败口径与确定性空负缓存。

锁住的契约：
  - `_parse_info_of_fund` 旧格式 td 内无 ``<a>`` 时回退纯文本，并按「（」/「(」截断注释；
    纯空白 cell 判无名字（空串，不猜）；任职起始日缺「任职起始日」标签时回退
    ``YYYY-MM-DD 至今`` 形态；
  - `_request_fund_html_status` 成功返回 ``(html, False)``；超时返回 ``(None, True)``
    （站点不可达）；其它传输失败返回 ``(None, False)``（不算站点整体不可达）；
  - 档案页新格式表格能解析出经理行；行内 td 不足 3 列时该行判空；
  - `fetch_fund_manager` 命中确定性空负缓存时不再发请求。
"""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import MagicMock, patch

from src.python.fetcher.fund_manager import (
    _parse_info_of_fund,
    _parse_manager_from_archive_page,
    _request_fund_html_status,
    fetch_fund_manager,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


def _client(resp=None, error=None):
    """构造 make_http_client 替身（上下文管理器返回自身）。"""
    client = MagicMock()
    client.__enter__.return_value = client
    if error is not None:
        client.get.side_effect = error
    else:
        client.get.return_value = resp
    return client


class TestParseInfoOfFundFallbacks:
    """旧格式 infoOfFund 的纯文本经理名与日期回退。"""

    def test_plain_text_manager_name_and_till_now_date(self):
        """td 内无链接且无「任职起始日」标签 → 取纯文本名 + ``X 至今`` 日期。"""
        html = '<div class="infoOfFund"><td>基金经理 </td><td>张三（2020-01-02 至今）</td></div>'
        assert _parse_info_of_fund(html) == ("张三", "2020-01-02")

    def test_blank_cell_yields_empty_name(self):
        """cell 只有标签无文字 → 名字空串（不猜）。"""
        html = '<div class="infoOfFund"><td>基金经理 </td><td><span> </span></td></div>'
        assert _parse_info_of_fund(html) == ("", "")


class TestRequestFundHtmlStatus:
    """首页请求的三类结局。"""

    def test_success_returns_html_and_reachable(self):
        """正常响应 → (html, False)。"""
        resp = MagicMock()
        resp.text = "<html>ok</html>"
        with patch("src.python.fetcher.fund_manager.make_http_client", return_value=_client(resp=resp)):
            assert _request_fund_html_status("000001") == ("<html>ok</html>", False)

    def test_timeout_marks_site_unreachable(self):
        """超时 → (None, True)（站点整体不可达，回退档案页只会翻倍等待）。"""
        with patch(
            "src.python.fetcher.fund_manager.make_http_client",
            return_value=_client(error=httpx.TimeoutException("slow")),
        ):
            assert _request_fund_html_status("000001") == (None, True)

    def test_request_error_is_not_site_unreachable(self):
        """其它传输失败 → (None, False)。"""
        with patch(
            "src.python.fetcher.fund_manager.make_http_client",
            return_value=_client(error=httpx.RequestError("network")),
        ):
            assert _request_fund_html_status("000001") == (None, False)


_ARCHIVE_HTML = (
    "<table class='w782 comm jloff'>"
    "<thead><tr><th>起始期</th><th>截止期</th><th>基金经理</th></tr></thead>"
    "<tbody>"
    "<tr><td>2021-03-01</td><td>至今</td><td>李四</td></tr>"
    "<tr><td>2018-06-01</td><td>2021-02-26</td><td>王五</td></tr>"
    "</tbody></table>"
)


class TestArchivePageParsing:
    """档案页新格式表格解析。"""

    def test_new_format_table_yields_manager_and_history(self):
        """新格式表格 → 首行作当前经理、其余入历任。"""
        resp = MagicMock()
        resp.text = _ARCHIVE_HTML
        with patch("src.python.fetcher.fund_manager.make_http_client", return_value=_client(resp=resp)):
            result = _parse_manager_from_archive_page("000001")

        assert result is not None
        assert result["manager_name"] == "李四"
        assert result["start_date"] == "2021-03-01"
        assert [row["name"] for row in result["history"]] == ["王五"]

    def test_row_with_too_few_cells_is_skipped(self):
        """行内 td 不足 3 列 → 该行判空（不误取他人名字）。"""
        resp = MagicMock()
        resp.text = (
            "<table class='w782 comm jloff'>"
            "<thead><tr><th>起始期</th><th>截止期</th><th>基金经理</th></tr></thead>"
            "<tbody><tr><td>2021-03-01</td><td>至今</td></tr></tbody></table>"
        )
        with patch("src.python.fetcher.fund_manager.make_http_client", return_value=_client(resp=resp)):
            result = _parse_manager_from_archive_page("000001")

        assert result is not None
        assert result["manager_name"] == ""


class TestDeterministicMissCache:
    """确定性空负缓存命中即跳过取数。"""

    def test_miss_cache_hit_returns_none_without_request(self):
        """负缓存命中 → None，且不发 HTTP 请求。"""
        miss = MagicMock()
        miss.is_missing.return_value = True
        with (
            patch("src.python.fetcher.fund_manager.FUND_MANAGER_MISS", miss),
            patch("src.python.fetcher.fund_manager._request_fund_html_status") as request,
        ):
            assert fetch_fund_manager("000001") is None

        request.assert_not_called()
