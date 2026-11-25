"""行情/财务 provider 的取数降级分支（sina_kline / eastmoney_industry / akshare_financial）。

测试场景：
  1. 新浪 K 线：不支持的类型直接空表；非文本响应走 json()、文本响应走解析；请求异常返回空表
  2. 东财 push2：限速配置读取失败回落兜底；瞬态失败且观测登记也失败仍返回 None；JSON 损坏返回 None
  3. akshare 财务：可选依赖缺席返回 None；指标行缺指标名时跳过该行
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from src.python.providers import akshare_financial, eastmoney_industry, sina_kline

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers, pytest.mark.usefixtures("offline_external_sources")]


def _client(text: object, json_payload: object = None) -> MagicMock:
    """构造 make_http_client 替身（响应文本可为非字符串，模拟流式/替身对象）。"""
    resp = MagicMock()
    resp.text = text
    resp.json.return_value = json_payload
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestSinaKlineRequestBranches:
    """``fetch_kline`` 的类型闸门、响应形态分叉与请求异常。"""

    def test_unsupported_code_returns_empty(self):
        """非 A 股/ETF 代码 → 空表且不发起请求。"""
        with patch("src.python.providers.sina.make_http_client") as client_factory:
            assert sina_kline.fetch_kline("999999") == []
        client_factory.assert_not_called()

    def test_non_text_response_parsed_from_json_payload(self):
        """响应无文本体（非 str）→ 直接取 resp.json() 解析。"""
        payload = [{"day": "2026-07-01", "open": "1", "close": "2", "high": "3", "low": "0.5", "volume": "9"}]
        with patch("src.python.providers.sina.make_http_client", return_value=_client(None, payload)):
            bars = sina_kline.fetch_kline("600519")
        assert [b["date"] for b in bars] == ["2026-07-01"]
        assert bars[0]["close"] == pytest.approx(2.0)

    def test_json_text_response_parsed(self):
        """文本响应为 JSON 数组 → json.loads 后按日期升序返回。"""
        body = '[{"day": "2026-07-02", "close": "2"}, {"day": "2026-07-01", "close": "1"}]'
        with patch("src.python.providers.sina.make_http_client", return_value=_client(body)):
            bars = sina_kline.fetch_kline("600519")
        assert [b["date"] for b in bars] == ["2026-07-01", "2026-07-02"]

    def test_request_error_returns_empty(self):
        """请求异常（超时/连接失败）→ 空表，不向上抛。"""
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.get.side_effect = httpx.ConnectError("连不上")
        with patch("src.python.providers.sina.make_http_client", return_value=client):
            assert sina_kline.fetch_kline("600519") == []


class TestPush2RequestBranches:
    """东财 push2 的限速兜底与失败收口。"""

    def test_interval_falls_back_when_config_read_fails(self, monkeypatch):
        """配置读取异常 → 回落兜底间隔（不阻断取数）。"""
        monkeypatch.setattr(
            "src.python.config.get_config",
            lambda: (_ for _ in ()).throw(RuntimeError("配置读取失败")),
        )
        assert eastmoney_industry._push2_interval() == pytest.approx(eastmoney_industry._PUSH2_MIN_INTERVAL)

    def test_transient_failure_with_broken_observer_still_returns_none(self, monkeypatch):
        """瞬态失败且限流观测登记也异常 → 仍返回 None（观测失败不影响取数结论）。"""

        def _boom(*_a: object, **_k: object) -> str:
            raise httpx.ConnectError("上游断连")

        monkeypatch.setattr(eastmoney_industry, "retry_transient", _boom)
        with patch(
            "src.python.core.rate_limit_state.note_failure",
            side_effect=RuntimeError("观测登记失败"),
        ):
            assert eastmoney_industry.make_push2_request("600519") is None

    def test_broken_json_returns_none(self, monkeypatch):
        """响应体不是 JSON → 解析失败返回 None（不抛 JSONDecodeError）。"""
        monkeypatch.setattr(eastmoney_industry, "retry_transient", lambda *_a, **_k: "<html>风控页</html>")
        assert eastmoney_industry.make_push2_request("600519") is None


class TestAkshareFinancialBranches:
    """akshare 可选依赖与指标行脏值。"""

    def test_missing_akshare_returns_none(self, monkeypatch):
        """aksahre 不可导入 → 返回 None（调用方跳过取数）。"""
        import sys

        monkeypatch.setitem(sys.modules, "akshare", None)
        assert akshare_financial._import_akshare() is None

    def test_installed_akshare_returns_module(self, monkeypatch):
        """akshare 可导入 → 返回模块本身（取数路径首步）。"""
        import sys
        import types

        stub = types.ModuleType("akshare")
        monkeypatch.setitem(sys.modules, "akshare", stub)
        assert akshare_financial._import_akshare() is stub

    def test_row_without_indicator_name_skipped(self):
        """指标名为空的行被跳过，其余行按报告期取值。"""
        abstract = pd.DataFrame([{"指标": "", "2025-12-31": 1.0}, {"指标": "净利润", "2025-12-31": 2.5}])
        values = akshare_financial._indicator_values(abstract, ["2025-12-31"])
        assert set(values) == {"净利润"}
        assert values["净利润"]["2025-12-31"] == pytest.approx(2.5)
