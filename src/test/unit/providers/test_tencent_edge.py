"""Tencent 指数 K 线边缘场景测试。

必须放在 *_edge.py 文件中（边缘测试文件隔离）。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.python.providers.tencent import fetch_index_kline

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers, pytest.mark.edge]


class TestFetchIndexKlineEdge(unittest.TestCase):
    """fetch_index_kline 边缘/异常场景。"""

    @patch("src.python.providers.tencent.make_http_client")
    def test_request_error_returns_empty(self, mock_factory):
        """网络异常 → 空列表。"""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_client.get.side_effect = httpx.RequestError("network error")

        result = fetch_index_kline("sh000300", 30)
        self.assertEqual(result, [])

    @patch("src.python.providers.tencent.make_http_client")
    def test_invalid_json_returns_empty(self, mock_factory):
        """非法 JSON 响应 → 空列表。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("invalid json")
        mock_client.get.return_value = mock_resp

        result = fetch_index_kline("sh000300", 30)
        self.assertEqual(result, [])

    @patch("src.python.providers.tencent.make_http_client")
    def test_malformed_data_structure(self, mock_factory):
        """API 返回非标准结构 → 空列表（不抛异常）。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"unexpected": "format"}
        mock_client.get.return_value = mock_resp

        result = fetch_index_kline("sh000300", 30)
        self.assertEqual(result, [])

    @patch("src.python.providers.tencent.make_http_client")
    def test_kline_entry_too_short(self, mock_factory):
        """K 线条目字段不足 6 个 → 自动跳过该条目。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "sh000300": {
                    "qfqday": [
                        ["2026-07-01", "4000.0"],
                        ["2026-07-02", "4010.0", "4020.0", "3990.0", "4015.0", "1000000"],
                    ]
                }
            }
        }
        mock_client.get.return_value = mock_resp

        result = fetch_index_kline("sh000300", 30)
        self.assertEqual(len(result), 1)

    @patch("src.python.providers.tencent.make_http_client")
    def test_all_bars_filtered_due_to_zero_close(self, mock_factory):
        """所有 K 线 close 为 0 → 空列表。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "sh000300": {
                    "qfqday": [
                        ["2026-07-01", "3990.0", "0.0", "4010.0", "3980.0", "1000000"],
                        ["2026-07-02", "4000.0", "0.0", "4020.0", "3990.0", "1000000"],
                    ]
                }
            }
        }
        mock_client.get.return_value = mock_resp

        result = fetch_index_kline("sh000300", 30)
        self.assertEqual(result, [])

    @patch("src.python.providers.tencent.make_http_client")
    def test_api_returns_list_not_dict(self, mock_factory):
        """API 返回 list（而非 dict）→ 空列表，不抛 AttributeError。

        `_parse_kline_response` 须兼容 list 响应形态（days=3650 超限时 API 返回
        list），不得以 `data.get(...)` 方式访问而抛 `'list' object has no attribute 'get'`。
        """
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = []  # 超限时 API 返回 list
        mock_client.get.return_value = mock_resp

        result = fetch_index_kline("sh000300", 3650)
        self.assertEqual(result, [])

    @patch("src.python.providers.tencent.make_http_client")
    def test_days_clamped_to_2000(self, mock_factory):
        """请求 days=3650 时钳位到 2000（API 上限），避免超限响应。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"sh000300": {"qfqday": []}}}
        mock_client.get.return_value = mock_resp

        fetch_index_kline("sh000300", 3650)
        call_kwargs = mock_client.get.call_args.kwargs
        param = call_kwargs["params"]["param"]
        self.assertIn(",,2000,qfq", param)
        self.assertNotIn(",,3650,qfq", param)


class TestBlockPageDetection:
    """回归：K 线接口返回 200 + HTML/风控页时，必须记该源失败并交下一链路。

    判定口径：`resp.json()` 抛 ValueError 被当「解析失败」既不解决问题、又白等退避，
    也不推动熔断——同一批代码会逐个再撞一次风控页（实测腾讯/新浪各 4 次/轮）。
    """

    def _factory(self, text, monkeypatch):
        from unittest.mock import MagicMock

        from src.python.providers import tencent as tc

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.text = text
        mock_client.get.return_value = resp
        monkeypatch.setattr(tc, "make_http_client", lambda **kw: mock_client)
        return mock_client

    def test_tencent_html_block_page_records_failure(self, monkeypatch):
        from src.python.core.provider_registry import get_registry
        from src.python.providers import tencent as tc

        reg = get_registry()
        reg.reset()
        self._factory("<html><body>429 Too Many Requests</body></html>", monkeypatch)
        attempts = {"n": 0}
        orig_get = self._factory("<html>访问过于频繁</html>", monkeypatch).get

        def _counting_get(*a, **k):
            attempts["n"] += 1
            return orig_get(*a, **k)

        monkeypatch.setattr(
            tc,
            "make_http_client",
            lambda **kw: type(
                "C",
                (),
                {
                    "__enter__": lambda s: type(
                        "M", (), {"get": staticmethod(_counting_get), "text": "<html>访问过于频繁</html>"}
                    )(),
                    "__exit__": lambda s, *a: False,
                },
            )(),
        )

        assert tc.fetch_index_kline("sh000300", 30) == []
        assert attempts["n"] == 1, "风控页不应重试（白等退避）"

    def test_sina_block_page_returns_empty_and_marks_source(self, monkeypatch):
        from unittest.mock import MagicMock

        from src.python.core.provider_registry import get_registry
        from src.python.providers import sina as sina_mod
        from src.python.providers import sina_kline

        reg = get_registry()
        reg.reset()
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.text = "<html>请稍后再试</html>"
        mock_client.get.return_value = resp
        monkeypatch.setattr(sina_mod, "make_http_client", lambda **kw: mock_client)

        assert sina_kline.fetch_kline("600900", 30) == []
        status = reg.generate_status_report().get("sina") or {}
        assert status.get("consecutive_failures", 0) >= 1, "风控页必须计入该源失败（驱动熔断冷却）"
        assert "block_page" in str(status.get("last_failure_context") or "")
