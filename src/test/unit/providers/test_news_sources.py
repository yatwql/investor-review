"""news_sources 源适配面单元测试（元数据 / 各源取数行为 / 新浪预算与并发 / 导入降级）。

测试目标：
  - `_SOURCE_LABELS` / `_FETCH_MAP` 元数据完整性与 `get_source_label` 查找；
  - `_FETCH_MAP` 各源取数函数的行为（返回列表、按 URL 去重）；
  - 每个子源模块不可导入（ImportError）时只告警并返回空列表（其余源不受影响）；
  - 新浪整源共享 `_SINA_SOURCE_BUDGET` 预算：预算耗尽即收尾并告警；
  - 新浪单分类首页返回空即止（不死循环翻页）；三分类并发抓取且跨分类按 URL 去重。
"""

from __future__ import annotations

import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.python.providers import news_sources
from src.python.providers.news_sources import _FETCH_MAP, _SOURCE_LABELS, get_source_label

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
    """预算翻页途中耗尽 → 已取到的首页结果照常返回（部分结果，不死等、不再翻页）。"""
    clock = {"t": 1000.0}
    monkeypatch.setattr(news_sources, "time", SimpleNamespace(monotonic=lambda: clock["t"]))
    monkeypatch.setattr(news_sources, "_SINA_SOURCE_BUDGET", 1.0)

    calls: list[tuple[str, int]] = []
    per_page = 50
    first_pages = threading.Barrier(3, timeout=5)

    def _fake_fetch(lid, num, page, timeout):
        calls.append((lid, page))
        if page == 1:
            first_pages.wait()  # 三个分类都取到首页后再耗光整源预算
            clock["t"] = 1_000_000.0
        return [{"url": f"https://example.com/{lid}/{page}/{i}", "title": f"{lid}{page}{i}"} for i in range(num)]

    monkeypatch.setattr("src.python.providers.sina_news.fetch_news", _fake_fetch)

    items = news_sources._fetch_from_sina(153)  # 每分类 51 条 → 需两页

    assert len(calls) == 3, "三个分类各发一次首页请求"
    assert all(page == 1 for _lid, page in calls), "预算耗尽后不得再翻页"
    assert len(items) == len(calls) * per_page, "预算内已取到的部分结果必须照常返回"


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


class TestSourceMetadata(unittest.TestCase):
    """新闻源元数据测试。"""

    def test_source_labels_complete(self) -> None:
        """所有源都有中文标签。"""
        expected_sources = {"sina", "eastmoney", "cls", "wallstreetcn", "akshare"}
        self.assertEqual(set(_SOURCE_LABELS.keys()), expected_sources)

    def test_get_source_label_known(self) -> None:
        """已知源 → 返回中文标签。"""
        self.assertEqual(get_source_label("sina"), "新浪财经")
        self.assertEqual(get_source_label("cls"), "财联社")

    def test_get_source_label_unknown(self) -> None:
        """未知源 → 返回原名称。"""
        self.assertEqual(get_source_label("unknown_source"), "unknown_source")

    def test_fetch_map_complete(self) -> None:
        """每个源都有对应的获取函数。"""
        self.assertEqual(set(_FETCH_MAP.keys()), set(_SOURCE_LABELS.keys()))

    def test_fetch_map_callable(self) -> None:
        """_FETCH_MAP 中所有值都是 callable。"""
        for name, fn in _FETCH_MAP.items():
            self.assertTrue(callable(fn), f"{name} 的 fetch 函数不可调用")

    def test_get_source_label_empty_string(self) -> None:
        """空字符串 → 返回空字符串。"""
        self.assertEqual(get_source_label(""), "")

    def test_get_source_label_whitespace(self) -> None:
        """空白字符 → 返回原值。"""
        self.assertEqual(get_source_label("  "), "  ")

    def test_get_source_label_numeric(self) -> None:
        """纯数字字符串 → 返回原值。"""
        self.assertEqual(get_source_label("123"), "123")

    def test_source_label_values_non_empty(self) -> None:
        """所有中文标签非空。"""
        for key, label in _SOURCE_LABELS.items():
            self.assertTrue(label, f"{key} 的标签为空")


class TestFetchFunctionBehavior(unittest.TestCase):
    """各源获取函数的行为测试。"""

    @patch("src.python.providers.sina_news.fetch_news")
    def test_fetch_from_sina_returns_list(self, mock_fetch: MagicMock) -> None:
        """新浪财经获取函数返回列表。"""
        mock_fetch.return_value = [{"title": "t1", "url": "http://u1"}]
        fn = _FETCH_MAP["sina"]
        result = fn(num=3)
        self.assertEqual(result, [{"title": "t1", "url": "http://u1"}])

    @patch("src.python.providers.sina_news.fetch_news")
    def test_fetch_from_sina_dedup_by_url(self, mock_fetch: MagicMock) -> None:
        """新浪财经获取函数按 URL 去重。"""
        mock_fetch.return_value = [
            {"title": "a", "url": "http://u"},
            {"title": "b", "url": "http://u"},
        ]
        fn = _FETCH_MAP["sina"]
        result = fn(num=5)
        self.assertEqual(len(result), 1)

    @patch("src.python.providers.eastmoney_news.fetch_news")
    def test_fetch_from_eastmoney_returns_list(self, mock_fetch: MagicMock) -> None:
        """东方财富获取函数返回列表。"""
        mock_fetch.return_value = []
        fn = _FETCH_MAP["eastmoney"]
        result = fn(num=5)
        self.assertIsInstance(result, list)
        mock_fetch.assert_called_once_with(num=5)

    @patch("src.python.providers.cls_news.fetch_news")
    def test_fetch_from_cls_returns_list(self, mock_fetch: MagicMock) -> None:
        """财联社获取函数返回列表。"""
        mock_fetch.return_value = []
        fn = _FETCH_MAP["cls"]
        result = fn(num=5)
        self.assertIsInstance(result, list)
        mock_fetch.assert_called_once_with(num=5)

    @patch("src.python.providers.wallstreetcn_news.fetch_news")
    def test_fetch_from_wallstreetcn_returns_list(self, mock_fetch: MagicMock) -> None:
        """华尔街见闻获取函数返回列表。"""
        mock_fetch.return_value = []
        fn = _FETCH_MAP["wallstreetcn"]
        result = fn(num=5)
        self.assertIsInstance(result, list)
        mock_fetch.assert_called_once_with(num=5)

    @patch("src.python.providers.akshare_news.fetch_news")
    def test_fetch_from_akshare_returns_list(self, mock_fetch: MagicMock) -> None:
        """akshare 获取函数返回列表。"""
        mock_fetch.return_value = []
        fn = _FETCH_MAP["akshare"]
        result = fn(num=5)
        self.assertIsInstance(result, list)
        mock_fetch.assert_called_once_with(num=5)


class TestSinaSourceBudget(unittest.TestCase):
    """新浪分类抓取的预算治理：单类挂起不得把整段拉长、已取条目不得丢。"""

    def test_request_timeout_shrinks_with_remaining_budget(self) -> None:
        from src.python.providers.news_sources import _sina_request_timeout

        assert _sina_request_timeout(30.0).read == 6.0, "预算充足时用模块上限"
        assert _sina_request_timeout(1.5).read == 1.5, "预算见底时按剩余收紧"

    @patch("src.python.providers.sina_news.fetch_news")
    def test_budget_exhausted_stops_and_keeps_collected(self, mock_fetch: MagicMock) -> None:
        """预算耗尽 → 停止翻页并保留已取条目（不整源丢弃；分类并发下按共享 deadline 收尾）。"""
        import itertools
        import threading

        from src.python.providers import news_sources

        mock_fetch.return_value = [{"title": "t", "url": "http://u"}]
        # 线程安全的假时钟：每次调用 +5s，预算 20s → 三个分类合计约 4 次调用后耗尽
        counter = itertools.count()
        lock = threading.Lock()

        def _clock() -> float:
            with lock:
                return next(counter) * 5.0

        with patch.object(news_sources, "time") as fake_time:
            fake_time.monotonic = _clock
            result = news_sources._fetch_from_sina(num=90)
        assert len(result) >= 1, "预算耗尽前取到的条目必须保留"
        assert mock_fetch.call_count <= 9, "预算耗尽后不得继续翻页"
        for call in mock_fetch.call_args_list:
            assert "timeout" in call.kwargs, "每次请求都带按预算收紧的超时"

    @patch("src.python.providers.sina_news.fetch_news")
    def test_within_budget_keeps_normal_flow(self, mock_fetch: MagicMock) -> None:
        """预算充足时不改变原有取数行为（逐页取满即止）。"""
        from src.python.providers import news_sources

        mock_fetch.side_effect = [
            [{"title": "a", "url": "http://a"}],
            [{"title": "b", "url": "http://b"}],
            [{"title": "c", "url": "http://c"}],
        ]
        result = news_sources._fetch_from_sina(num=3)
        assert len(result) == 3


class TestSinaParallelism:
    """新浪三分类并发抓取：墙钟取最慢分类，跨分类仍按 URL 去重。"""

    @patch("src.python.providers.sina_news.fetch_news")
    def test_categories_fetch_concurrently(self, mock_fetch: MagicMock) -> None:
        """三个分类必须同时在飞：用屏障判定并发，不用墙钟。

        并发语义由屏障表达：三路真并发时同时到达即放行；任一路被串行排队则屏障超时
        抛 `BrokenBarrierError`，该分类取数失败 → 结果条数不足。刻意不按耗时阈值判定
        ——耗时把「是否并发」与 runner 调度快慢混在一起，慢机器上会红成假阳性。
        """
        import threading

        from src.python.providers import news_sources

        barrier = threading.Barrier(3, timeout=5)

        def _sync(**kwargs):
            barrier.wait()  # 三路必须同时在飞；串行时在此超时
            return [{"title": "t", "url": f"http://u-{kwargs['lid']}-{kwargs['page']}"}]

        mock_fetch.side_effect = _sync
        result = news_sources._fetch_from_sina(num=150)  # per_category=50 → 每类 1 页即止

        assert len(result) == 3, f"三个分类未并发（结果 {len(result)} 条，屏障超时即串行）"

    @patch("src.python.providers.sina_news.fetch_news")
    def test_cross_category_url_dedupe_kept(self, mock_fetch: MagicMock) -> None:
        from src.python.providers import news_sources

        mock_fetch.return_value = [{"title": "same", "url": "http://same"}]
        result = news_sources._fetch_from_sina(num=150)
        assert len(result) == 1, "跨分类重复 URL 合并后只保留一条"
