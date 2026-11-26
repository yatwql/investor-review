"""天天基金公共 HTTP 层的故障面（`providers/tiantian_base`）。

三个请求函数共享一条契约：**任何网络/解析故障都归 None，不抛异常**——上层据此降级到
下一数据源。按异常类型逐一注入，防止某一路（如 429 触发的 HTTPStatusError）漏接而成
为报告链的崩溃点。
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.python.providers import tiantian_base
from src.test._fixtures.http import FakeClient, FakeResponse

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


def _client_factory(resp=None, *, error: Exception | None = None):
    def _make(*args, **kwargs):
        return FakeClient(resp, error=error)

    return _make


class TestFundHtml:
    def test_success_reads_text(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(FakeResponse("<html>ok</html>")))

        assert tiantian_base._request_fund_html("000001") == "<html>ok</html>"

    def test_timeout_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            tiantian_base, "make_http_client", _client_factory(error=httpx.ConnectTimeout("probe timeout"))
        )

        assert tiantian_base._request_fund_html("000001") is None

    def test_request_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(error=httpx.ConnectError("dns failed")))

        assert tiantian_base._request_fund_html("000001") is None


class TestPingzhongData:
    def test_success_reads_text(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(FakeResponse("var x = 1;")))

        assert tiantian_base._request_pingzhong_data("000001") == "var x = 1;"

    def test_timeout_returns_none(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(error=httpx.ReadTimeout("probe")))

        assert tiantian_base._request_pingzhong_data("000001") is None

    def test_http_status_error_returns_none(self, monkeypatch):
        """429/404 等状态码异常单独一路：不得与连接错误混为一谈（日志要带状态码）。"""
        request = httpx.Request("GET", "https://fund.eastmoney.com/pingzhongdata/000001.js")
        response = httpx.Response(429, request=request)
        resp = FakeResponse(raise_status=httpx.HTTPStatusError("too many", request=request, response=response))
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(resp))

        assert tiantian_base._request_pingzhong_data("000001") is None

    def test_request_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(error=httpx.ConnectError("refused")))

        assert tiantian_base._request_pingzhong_data("000001") is None


def _api_text(content: str) -> str:
    """构造季报 API 的 JS 响应（`content: "..." , arryear` 形状）。"""
    return f'var apidata={{ content:"{content}",arryear:"2024" }};'


class TestQuarterlyApi:
    def test_success_decodes_js_escapes(self, monkeypatch):
        payload = "<table>持仓</table>"
        monkeypatch.setattr(
            tiantian_base, "make_http_client", _client_factory(FakeResponse(_api_text(payload.replace('"', '\\"'))))
        )

        assert tiantian_base._request_quarterly_api("000001", "jjcc") == payload

    def test_request_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(error=httpx.ReadTimeout("probe")))

        assert tiantian_base._request_quarterly_api("000001", "jjcc") is None

    def test_missing_content_field_returns_none(self, monkeypatch):
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(FakeResponse("var apidata={};")))

        assert tiantian_base._request_quarterly_api("000001", "jjcc") is None

    def test_blank_content_returns_none(self, monkeypatch):
        """无持仓的季度里 API 返回空 content：按「无数据」跳过，不当解析失败。"""
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(FakeResponse(_api_text("   "))))

        assert tiantian_base._request_quarterly_api("000001", "jjcc") is None

    def test_invalid_json_escape_returns_none(self, monkeypatch):
        """content 内含非法转义（`\\x`）→ JSONDecodeError 归 None，不抛给调用方。"""
        monkeypatch.setattr(tiantian_base, "make_http_client", _client_factory(FakeResponse(_api_text(r"a\x b"))))

        assert tiantian_base._request_quarterly_api("000001", "jjcc") is None


class TestPhaseTimeout:
    def test_connect_timeout_tighter_than_total(self):
        """连接（含 SSL 握手）超时须严于总超时，否则单跳挂死会占满整段预算。"""
        timeout = tiantian_base._phase_timeout()

        assert timeout.connect == tiantian_base._CONNECT_TIMEOUT
        assert timeout.connect < tiantian_base._TIMEOUT
        assert timeout.read == tiantian_base._TIMEOUT


def test_safe_float_reexport_is_shared():
    """`safe_float` 从 providers.utils 单源再导出（多个 tiantian_* 模块共用同一实现）。"""
    from src.python.providers.utils import safe_float

    assert tiantian_base._safe_float is safe_float
    assert json.dumps({"v": tiantian_base._safe_float("3.5")}) == '{"v": 3.5}'
