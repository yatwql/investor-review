"""tencent 残余分支 — 指数行情链路、不支持品种的跳过与 K 线解析异常。

锁住的契约：
  - `_parse_response` 的字段值允许带 ``key=value`` 形态（取 ``=`` 右侧）；
  - `fetch_price` / `fetch_kline` 对既非 A 股也非场内基金的代码直接返回 None / []；
  - `fetch_index_price` 超时/传输失败/解析失败一律返回 None（不抛异常）；
  - `_parse_kline_response` 遇到不可迭代的 K 线体时记告警返回 []。
"""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import MagicMock, patch

from src.python.providers.tencent import (
    _parse_kline_response,
    _parse_response,
    fetch_index_price,
    fetch_kline,
    fetch_price,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]

_QUOTE_BODY = "1~科创材料ETF~561910~0.853~0.901~0.900~1200~1023.5~1.2~~20240102150000"


def _client(resp=None, error=None):
    """构造 make_http_client 替身（上下文管理器返回自身）。"""
    client = MagicMock()
    client.__enter__.return_value = client
    if error is not None:
        client.get.side_effect = error
    else:
        client.get.return_value = resp
    return client


class TestParseResponseFieldWithEquals:
    """字段值内含 ``=`` 时取等号右侧。"""

    def test_equals_in_field_keeps_trailing_value(self):
        """价格字段写成 ``price=0.853`` → 解析为 0.853（不是 0）。"""
        body = _QUOTE_BODY.split("~")
        body[3] = "price=0.853"
        result = _parse_response(f'v_sh561910="{"~".join(body)}";')
        assert result is not None
        assert result["price"] == pytest.approx(0.853)


class TestUnsupportedCodeSkipped:
    """不支持品种（既非 A 股也非场内基金）直接跳过。"""

    def test_fetch_price_unsupported_code(self):
        """港股/非法代码 → None，且不发请求。"""
        with patch("src.python.providers.tencent.make_http_client") as factory:
            assert fetch_price("00700") is None
        factory.assert_not_called()

    def test_fetch_kline_unsupported_code(self):
        """港股/非法代码 → 空列表，且不发请求。"""
        with patch("src.python.providers.tencent.make_http_client") as factory:
            assert fetch_kline("00700") == []
        factory.assert_not_called()


class TestFetchIndexPrice:
    """指数行情链路的成功与三类失败。"""

    def test_success_parses_index_quote(self):
        """正常 GBK 行情文本 → 结构化 dict（指数不加交易所前缀）。"""
        resp = MagicMock()
        resp.text = f'v_sh000001="{_QUOTE_BODY}";'
        client = _client(resp=resp)
        with patch("src.python.providers.tencent.make_http_client", return_value=client):
            result = fetch_index_price(" sh000001 ")

        assert result is not None
        assert result["price"] == pytest.approx(0.853)
        assert client.get.call_args.args == ("https://qt.gtimg.cn/q=sh000001",)

    def test_timeout_returns_none(self):
        """请求超时 → None。"""
        with patch(
            "src.python.providers.tencent.make_http_client",
            return_value=_client(error=httpx.TimeoutException("slow")),
        ):
            assert fetch_index_price("sh000001") is None

    def test_request_error_returns_none(self):
        """传输级失败 → None。"""
        with patch(
            "src.python.providers.tencent.make_http_client",
            return_value=_client(error=httpx.RequestError("network")),
        ):
            assert fetch_index_price("sh000001") is None

    def test_unparsable_body_returns_none(self):
        """返回体无引号内容（解析失败）→ None。"""
        resp = MagicMock()
        resp.text = "unexpected body"
        with patch("src.python.providers.tencent.make_http_client", return_value=_client(resp=resp)):
            assert fetch_index_price("sh000001") is None


class TestFetchKlineFailurePath:
    """K 线取数失败与解析异常都收敛为空列表。"""

    def test_missing_kline_payload_returns_empty(self):
        """底层 JSON 取数返回 None（请求失败/超时耗尽）→ []。"""
        with patch("src.python.providers.tencent._fetch_kline_json", return_value=None):
            assert fetch_kline("600000") == []

    def test_non_iterable_kline_body_returns_empty(self):
        """K 线体非可迭代（上游异常载荷）→ 记告警返回 []，不抛 TypeError。"""
        data = {"data": {"sh600000": {"day": 5}}}
        assert _parse_kline_response(data, "sh600000") == []
