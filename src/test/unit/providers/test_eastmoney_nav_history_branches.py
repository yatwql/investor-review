"""eastmoney 历史净值分页 + push2his K 线拉取的分支补齐测试。

覆盖点：
  - `fetch_fund_nav_history` 多页拼接、无更多数据、三类单页异常（HTTP 状态/请求/JSON 解析）
    在「已有数据」与「首屏失败」两种状态下的不同处置、脏行过滤
  - `_fetch_index_kline_json` 成功路径直接返回 JSON 体

外部 HTTP 一律 mock 在 `providers.eastmoney.make_http_client`（调用点所在模块），
分页限速器同模块替换为桩，避免真实 sleep。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.python.providers import eastmoney as em

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


def _page_resp(records: list[dict], total: int) -> MagicMock:
    """构造一个 JSONP 包裹的历史净值页响应。"""
    payload = {"Data": {"LSJZList": records}, "TotalCount": total}
    resp = MagicMock()
    resp.text = f"jQuery({json.dumps(payload, ensure_ascii=False)})"
    resp.raise_for_status.return_value = None
    return resp


def _nav_record(date: str, nav: str = "1.5", acc: str = "2.5") -> dict:
    return {"FSRQ": date, "DWJZ": nav, "LJJZ": acc}


class _ClientStub:
    """按调用序号依次返回预置响应（异常实例即抛出）。"""

    def __init__(self, items: list) -> None:
        self._items = items
        self.params: list[dict] = []

    def __enter__(self) -> _ClientStub:
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def get(self, url, params=None, headers=None):
        self.params.append(dict(params or {}))
        item = self._items[min(len(self.params) - 1, len(self._items) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


def _patch_pager() -> tuple:
    limiter = MagicMock()
    return patch.object(em, "_get_pager_limiter", return_value=limiter), limiter


def test_nav_history_concatenates_pages_until_total_reached() -> None:
    """两页 20 条、总数 40 → 取满两页后停止，结果按日期升序。"""
    page1 = [_nav_record(f"2026-06-{d:02d}") for d in range(20, 0, -1)]
    page2 = [_nav_record(f"2026-05-{d:02d}") for d in range(20, 0, -1)]
    client = _ClientStub([_page_resp(page1, 40), _page_resp(page2, 40)])
    pager, limiter = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        result = em.fetch_fund_nav_history("011506")

    assert len(result) == 40
    assert result[0]["date"] == "2026-05-01"
    assert result[-1]["date"] == "2026-06-20"
    assert result[0] == {"date": "2026-05-01", "nav": 1.5, "acc_nav": 2.5}
    # 翻页请求带页序与基金代码；页间限速只发生一次（第一页无需等待）
    assert [p["pageIndex"] for p in client.params] == [1, 2]
    assert {p["fundCode"] for p in client.params} == {"011506"}
    assert limiter.acquire.call_count == 1


def test_nav_history_stops_when_page_returns_no_records() -> None:
    client = _ClientStub([_page_resp([], 0)])
    pager, limiter = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        assert em.fetch_fund_nav_history("011506") == []

    assert len(client.params) == 1
    limiter.acquire.assert_not_called()


def test_nav_history_filters_rows_without_date_or_positive_nav() -> None:
    """缺日期、净值与累计净值均非正的行被丢弃，其余保留。"""
    page = [
        _nav_record(""),
        _nav_record("2026-06-02", nav="0", acc="0"),
        _nav_record("2026-06-03", nav="1.2345", acc="0"),
    ]
    client = _ClientStub([_page_resp(page, 3)])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        result = em.fetch_fund_nav_history("011506")

    assert result == [{"date": "2026-06-03", "nav": pytest.approx(1.2345), "acc_nav": 0.0}]


@pytest.mark.parametrize(
    "exc",
    [
        httpx.HTTPStatusError("500", request=httpx.Request("GET", "http://x"), response=httpx.Response(500)),
        httpx.ConnectError("down"),
    ],
    ids=["http_status", "request_error"],
)
def test_nav_history_first_page_failure_returns_empty(exc: BaseException) -> None:
    client = _ClientStub([exc])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        assert em.fetch_fund_nav_history("011506") == []


def test_nav_history_json_decode_failure_on_first_page_returns_empty() -> None:
    resp = MagicMock()
    resp.text = "jQuery(<html>error</html>)"
    resp.raise_for_status.return_value = None
    client = _ClientStub([resp])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        assert em.fetch_fund_nav_history("011506") == []


def test_nav_history_tolerates_http_failure_on_later_page() -> None:
    """已有数据时后续页 HTTP 错误 → 用已有页返回，不再是空结果。"""
    page1 = [_nav_record(f"2026-06-{d:02d}") for d in (2, 1)]
    failure = httpx.HTTPStatusError("503", request=httpx.Request("GET", "http://x"), response=httpx.Response(503))
    client = _ClientStub([_page_resp(page1, 100), failure])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        result = em.fetch_fund_nav_history("011506")

    assert [r["date"] for r in result] == ["2026-06-01", "2026-06-02"]


def test_nav_history_tolerates_request_error_on_later_page() -> None:
    page1 = [_nav_record("2026-06-01")]
    client = _ClientStub([_page_resp(page1, 100), httpx.ReadTimeout("slow")])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        result = em.fetch_fund_nav_history("011506")

    assert result == [{"date": "2026-06-01", "nav": 1.5, "acc_nav": 2.5}]


def test_nav_history_tolerates_json_decode_failure_on_later_page() -> None:
    page1 = [_nav_record("2026-06-01")]
    broken = MagicMock()
    broken.text = "{not json"
    broken.raise_for_status.return_value = None
    client = _ClientStub([_page_resp(page1, 100), broken])
    pager, _ = _patch_pager()

    with patch.object(em, "make_http_client", return_value=client), pager:
        result = em.fetch_fund_nav_history("011506")

    assert [r["date"] for r in result] == ["2026-06-01"]


def test_index_kline_json_returns_body_on_success() -> None:
    """首次尝试成功 → 直接返回 JSON 体（不进入重试分支）。"""
    resp = MagicMock()
    resp.json.return_value = {"data": {"klines": ["2026-07-01,1,2,3,0.5,100"]}}
    resp.raise_for_status.return_value = None
    client = _ClientStub([resp])

    with patch.object(em, "make_http_client", return_value=client):
        body = em._fetch_index_kline_json("1.000300", 30)

    assert body == {"data": {"klines": ["2026-07-01,1,2,3,0.5,100"]}}
    assert client.params[0]["secid"] == "1.000300"
    assert client.params[0]["lmt"] == 30
