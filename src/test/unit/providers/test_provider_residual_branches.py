"""providers 域残余分支：契约级空返回 / 非对象响应 / 相似度上界短路。

补齐的都是「上游给了不合约输入」时的对外行为（返回空、返回空串、返回 None），
正常源响应路径覆盖不到。断言只看返回值，不依赖日志文案。
"""

from __future__ import annotations

import pytest

from src.python.providers import cls_news, datasink, eastmoney
from src.python.providers import news_dedup_rules as ndr
from src.python.providers import sina_news
from src.test._fixtures.http import FakeClient, FakeResponse

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class TestIndexSecidUnmappable:
    """`_index_secid` 的「无法映射返回空串」契约：判据函数给出非指数/非 6 位码时不得拼错 secid。"""

    def test_no_exchange_yields_empty(self, monkeypatch):
        monkeypatch.setattr(eastmoney, "is_index_code", lambda code: True)
        monkeypatch.setattr(eastmoney, "index_exchange_of", lambda code: "")

        assert eastmoney._index_secid("000300") == ""

    def test_tail_not_six_digits_yields_empty(self, monkeypatch):
        monkeypatch.setattr(eastmoney, "is_index_code", lambda code: True)
        monkeypatch.setattr(eastmoney, "index_exchange_of", lambda code: "sh")

        assert eastmoney._index_secid("sh0012") == ""


class TestDatasinkNonObjectPayload:
    def test_json_list_payload_is_treated_as_structure_fault(self, monkeypatch):
        client = FakeClient(FakeResponse(json_body=[{"id": 1}]))
        monkeypatch.setattr(datasink, "make_http_client", lambda **_kw: client)
        monkeypatch.setattr(datasink, "credential_value", lambda _sid: "test-key")
        monkeypatch.setattr(datasink, "missing_credential", lambda _sid: None)

        assert datasink._request("/documents", {}) is None
        assert client.calls  # 确认确实走到了响应解析而非提前跳过


class TestNewsSourceMalformedPayloads:
    def test_cls_news_roll_data_not_list_returns_empty(self, monkeypatch):
        client = FakeClient(FakeResponse(json_body={"data": {"roll_data": "不是数组"}}))
        monkeypatch.setattr(cls_news, "make_http_client", lambda **_kw: client)

        assert cls_news.fetch_news(num=5) == []

    def test_sina_news_skips_non_object_items(self, monkeypatch):
        payload = {
            "result": {
                "data": [
                    "不是对象",
                    {"title": "央行降准", "url": "https://example.com/a", "ctime": "1700000000", "media_name": "新浪"},
                ]
            }
        }
        client = FakeClient(FakeResponse(json_body=payload))
        monkeypatch.setattr(sina_news, "make_http_client", lambda **_kw: client)

        items = sina_news.fetch_news(lid="2516", num=5)

        assert [item["title"] for item in items] == ["央行降准"]


class TestNewsDedupUpperBounds:
    def test_multiset_upper_bound_of_two_empty_titles_is_zero(self):
        assert ndr._multiset_upper_bound("", "") == 0.0
