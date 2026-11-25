"""新浪行情 provider 的解析兜底与请求异常分支。

覆盖 `_parse_price_response` / `_parse_a_index` 的格式异常返回 None、
`fetch_price` 的类型闸门与超时/请求失败、场外基金净值超时，
以及指数批量取的畸形行（`warn_malformed` 开关）跳过。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.python.providers import sina

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


def _client(text: str):
    resp = MagicMock()
    resp.text = text
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestParsePriceResponse:
    """个股行情文本解析的三个 None 出口：无引号 / 空 body / 字段不足。"""

    def test_missing_quotes_returns_none(self, caplog) -> None:
        with caplog.at_level("WARNING", logger="invest"):
            assert sina._parse_price_response("garbage-without-quotes", "600900") is None
        assert "Sina 行情格式异常" in caplog.text

    def test_empty_body_returns_none(self) -> None:
        assert sina._parse_price_response('var hq_str_sh600900=""', "600900") is None

    def test_too_few_fields_returns_none(self, caplog) -> None:
        with caplog.at_level("WARNING", logger="invest"):
            assert sina._parse_price_response('var hq_str_sh600900="长江电力,1,2,3"', "600900") is None
        assert "Sina 行情字段不足(4)" in caplog.text


class TestParseAIndex:
    """A 股指数文本解析：格式异常与正例字段换算。"""

    def test_missing_quotes_returns_none(self) -> None:
        assert sina._parse_a_index("var hq_str_sh000001=...") is None

    def test_empty_body_returns_none(self) -> None:
        assert sina._parse_a_index('var hq_str_sh000001=""') is None

    def test_too_few_fields_returns_none(self) -> None:
        assert sina._parse_a_index('var hq_str_sh000001="上证指数,3100.00,10.00"') is None

    def test_derives_yclose_and_change_pct_from_absolute_change(self) -> None:
        """昨收 = 现价 - 涨跌额；涨跌幅按昨收换算，日期斜杠归一为短横。"""
        text = 'var hq_str_sh000001="上证指数,3110.00,10.00,0.32,100,2000,2025/01/02 15:00:00";'

        parsed = sina._parse_a_index(text)

        assert parsed is not None
        assert parsed["name"] == "上证指数"
        assert parsed["price"] == pytest.approx(3110.0)
        assert parsed["change"] == pytest.approx(10.0)
        assert parsed["yesterday_close"] == pytest.approx(3100.0)
        assert parsed["change_pct"] == pytest.approx(0.32, abs=0.01)
        assert parsed["price_date"] == "2025-01-02"
        assert parsed["source"] == "新浪财经"

    def test_non_positive_price_yields_zero_yclose(self) -> None:
        """现价缺失（0）→ 昨收与涨跌幅按 0 兜底，不产生除零。"""
        parsed = sina._parse_a_index('var hq_str_sh000001="上证指数,0,0,0,0,0,"')

        assert parsed is not None
        assert parsed["yesterday_close"] == 0.0
        assert parsed["change_pct"] == 0.0
        assert parsed["price_date"] == ""


class TestFetchPriceGuards:
    """`fetch_price` 的类型闸门与两条网络异常出口。"""

    def test_unsupported_code_skipped_without_request(self, caplog) -> None:
        with patch.object(sina, "make_http_client") as factory:
            with caplog.at_level("DEBUG", logger="invest"):
                assert sina.fetch_price("AAPL") is None

        factory.assert_not_called()
        assert "Sina 跳过不支持的类型: AAPL" in caplog.text

    def test_timeout_returns_none(self, caplog) -> None:
        with patch.object(sina, "make_http_client", side_effect=httpx.ReadTimeout("slow")):
            with caplog.at_level("WARNING", logger="invest"):
                assert sina.fetch_price("600900") is None

        assert "Sina 行情 API 超时: sh600900" in caplog.text

    def test_request_error_returns_none(self, caplog) -> None:
        with patch.object(sina, "make_http_client", side_effect=httpx.ConnectError("down")):
            with caplog.at_level("WARNING", logger="invest"):
                assert sina.fetch_price("600900") is None

        assert "Sina 行情 API 请求失败" in caplog.text


def test_fund_nav_timeout_returns_none(caplog) -> None:
    """场外基金净值超时 → None（交给链路下一槽）。"""
    with patch.object(sina, "make_http_client", side_effect=httpx.ReadTimeout("slow")):
        with caplog.at_level("WARNING", logger="invest"):
            assert sina.fetch_fund_nav("011506") is None

    assert "新浪场外基金净值超时: 011506" in caplog.text


class TestFetchSinaIndicesMalformedLines:
    """指数批量取：畸形行按 warned 开关记日志后跳过，合法行照常解析。"""

    _TEXT = (
        'var hq_str_sh000001="上证指数,3110.00,10.00,0.32,100,2000,2025/01/02 15:00:00";\n'
        "noise-line\n"
        "var hq_str_sh000300_no_equals\n"
        'var hq_str_sh999999="未知,1,0,0,0,0,2025/01/02 15:00:00";\n'
    )

    def test_warn_malformed_logs_noise_lines(self, caplog) -> None:
        with patch.object(sina, "make_http_client", return_value=_client(self._TEXT)):
            with caplog.at_level("WARNING", logger="invest"):
                result = sina._fetch_sina_indices(
                    {"sh000001": "上证指数"}, sina._parse_a_index, market_label="A 股指数", warn_malformed=True
                )

        assert list(result) == ["sh000001"]
        assert result["sh000001"]["price"] == pytest.approx(3110.0)
        assert "Sina 格式异常: noise-line" in caplog.text

    def test_warn_malformed_off_keeps_quiet(self, caplog) -> None:
        with patch.object(sina, "make_http_client", return_value=_client(self._TEXT)):
            with caplog.at_level("WARNING", logger="invest"):
                result = sina._fetch_sina_indices(
                    {"sh000001": "上证指数"}, sina._parse_a_index, market_label="A 股指数", warn_malformed=False
                )

        assert list(result) == ["sh000001"]
        assert "Sina 格式异常" not in caplog.text

    def test_fetch_a_indices_delegates_without_malformed_warnings(self, caplog) -> None:
        """`fetch_a_indices` 走 warn_malformed=False 档（噪声行不刷屏），代码表取 A 股指数。"""
        client = _client(
            'var hq_str_s_sh000001="上证指数,3110.00,10.00,0.32,100,2000,2025/01/02 15:00:00";\nnoise-line\n'
        )
        with patch.object(sina, "make_http_client", return_value=client):
            with caplog.at_level("WARNING", logger="invest"):
                result = sina.fetch_a_indices()

        assert [code for code in result] == ["s_sh000001"]
        assert result["s_sh000001"]["name"] == "上证指数"
        assert "Sina 格式异常" not in caplog.text
        requested_url = client.get.call_args.args[0]
        assert "s_sh000001" in requested_url and requested_url.startswith(sina._BASE_URL)
