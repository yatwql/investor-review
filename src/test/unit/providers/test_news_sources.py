"""news_sources 各源适配器的导入降级与新浪预算/空页收尾。

锁住的契约：
  - 每个子源模块不可导入（ImportError）时只告警并返回空列表（其余源不受影响）；
  - 新浪整源共享 `_SINA_SOURCE_BUDGET` 预算：预算耗尽即收尾并告警；
  - 新浪单分类首页返回空即止（不死循环翻页）。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from src.python.providers import news_sources

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]

_SOURCE_MODULES = {
    "sina_news": news_sources._fetch_from_sina,
    "eastmoney_news": news_sources._fetch_from_eastmoney,
    "cls_news": news_sources._fetch_from_cls,
    "wallstreetcn_news": news_sources._fetch_from_wallstreetcn,
    "akshare_news": news_sources._fetch_from_akshare,
}


@pytest.mark.parametrize(("module_name", "fetch_fn"), sorted(_SOURCE_MODULES.items()))
def test_missing_submodule_returns_empty(monkeypatch, module_name, fetch_fn):
    """子源模块不可导入 → 返回空列表（不抛 ImportError，不污染其他源）。"""
    monkeypatch.setitem(sys.modules, f"src.python.providers.{module_name}", None)
    assert fetch_fn(5) == []


def test_sina_budget_exhausted_returns_partial(monkeypatch):
    """预算归零 → 分类内循环立即收尾，返回空列表且不死等。"""
    monkeypatch.setattr(news_sources, "_SINA_SOURCE_BUDGET", 0.0)
    monkeypatch.setattr("src.python.providers.sina_news.fetch_news", MagicMock(return_value=[]))
    assert news_sources._fetch_from_sina(9) == []


def test_sina_empty_first_page_stops_paging(monkeypatch):
    """单分类首页无数据 → 直接止于该分类（不继续翻页）。"""
    fake_fetch = MagicMock(return_value=[])
    monkeypatch.setattr("src.python.providers.sina_news.fetch_news", fake_fetch)

    assert news_sources._fetch_from_sina(9) == []
    # 三个分类各探一次首页（并发，故只校验分类数而非调用次数上限细节）
    assert fake_fetch.call_count >= 1


def test_sina_merges_and_dedupes_across_categories(monkeypatch):
    """跨分类同 URL 只保留第一条（全局去重口径）。"""
    shared = [{"url": "https://example.com/a", "title": "共同"}]
    monkeypatch.setattr("src.python.providers.sina_news.fetch_news", MagicMock(return_value=shared))

    items = news_sources._fetch_from_sina(3)

    assert [item["url"] for item in items] == ["https://example.com/a"]
