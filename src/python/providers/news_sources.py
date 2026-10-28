"""财经新闻源获取模块。

管理各新闻源（新浪/东方财富/财联社/华尔街见闻/akshare）的获取函数和注册表。

各新闻源的启用在 config.json 中配置（news_sources 字段），
代码不硬编码开关状态。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger("invest")

# ── 新闻来源注册（静态元数据，不含开关状态） ─────────────────

_SOURCE_LABELS: dict[str, str] = {
    "sina": "新浪财经",
    "eastmoney": "东方财富",
    "cls": "财联社",
    "wallstreetcn": "华尔街见闻",
    "akshare": "财新网 / CCTV",
}


def get_source_label(name: str) -> str:
    """返回新闻源的中文标签。"""
    return _SOURCE_LABELS.get(name, name)


#: 新浪整源预算（秒）：6 类×翻页都是串行请求，单类偶发挂起会把整段拉长。
#: 预算内能取多少算多少，超预算即收尾——已取到的条目照常参与聚合，不整源丢弃。
_SINA_SOURCE_BUDGET = 20.0

#: 单请求的上限（与 `sina_news._TIMEOUT` 同量级）；剩余预算更小时按剩余收紧。
_SINA_REQUEST_READ_TIMEOUT = 6.0
_SINA_REQUEST_CONNECT_TIMEOUT = 3.0


def _sina_request_timeout(remaining: float) -> httpx.Timeout:
    """按整源剩余预算收缩单请求超时（预算见底时不再给满额等待）。"""
    read = max(1.0, min(_SINA_REQUEST_READ_TIMEOUT, remaining))
    connect = max(1.0, min(_SINA_REQUEST_CONNECT_TIMEOUT, remaining))
    return httpx.Timeout(connect=connect, read=read, write=connect, pool=connect)


def _fetch_from_sina(num: int) -> list[dict[str, Any]]:
    """从新浪财经获取新闻，均匀覆盖多个分类（支持翻页）。

    各分类通过 page 参数逐页获取，突破单次 50 条上限。
    整源受 `_SINA_SOURCE_BUDGET` 预算约束：超预算即停止翻页并返回已取条目。
    """
    try:
        from src.python.providers.sina_news import fetch_news as sina_fetch
    except ImportError:
        logger.warning("新浪财经模块不可用")
        return []

    lids = ["2516", "2509", "2510"]  # 财经要闻, 国内财经, 国际财经
    per_category = max(1, num // len(lids))
    per_page = 50  # API 每页上限

    all_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    deadline = time.monotonic() + _SINA_SOURCE_BUDGET
    budget_exhausted = False
    for lid in lids:
        page = 1
        category_fetched = 0
        while category_fetched < per_category:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                budget_exhausted = True
                break
            need = min(per_page, per_category - category_fetched)
            items = sina_fetch(lid=lid, num=need, page=page, timeout=_sina_request_timeout(remaining))
            if not items:
                break
            prev_fetched = category_fetched
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
                    category_fetched += 1
            page += 1
            # 无新增条目（全部被去重命中），避免死循环
            if category_fetched == prev_fetched:
                break
            if len(items) < need:
                break  # 该分类无更多数据
        if budget_exhausted:
            break

    if budget_exhausted:
        logger.warning(
            "新浪财经取数预算耗尽（%.0fs），已取 %d 条后收尾（其余源不受影响）",
            _SINA_SOURCE_BUDGET,
            len(all_items),
        )
    logger.info("新浪财经: 获取 %d 条 (去重后)", len(all_items))
    return all_items


def _fetch_from_eastmoney(num: int) -> list[dict[str, Any]]:
    """从东方财富获取新闻。"""
    try:
        from src.python.providers.eastmoney_news import fetch_news as em_fetch
    except ImportError:
        logger.warning("东方财富模块不可用")
        return []

    items = em_fetch(num=num)
    logger.info("东方财富: 获取 %d 条", len(items))
    return items


def _fetch_from_cls(num: int) -> list[dict[str, Any]]:
    """从财联社获取新闻。"""
    try:
        from src.python.providers.cls_news import fetch_news as cls_fetch
    except ImportError:
        logger.warning("财联社模块不可用")
        return []

    items = cls_fetch(num=num)
    logger.info("财联社: 获取 %d 条", len(items))
    return items


def _fetch_from_wallstreetcn(num: int) -> list[dict[str, Any]]:
    """从华尔街见闻获取新闻。"""
    try:
        from src.python.providers.wallstreetcn_news import fetch_news as wsc_fetch
    except ImportError:
        logger.warning("华尔街见闻模块不可用")
        return []

    items = wsc_fetch(num=num)
    logger.info("华尔街见闻: 获取 %d 条", len(items))
    return items


def _fetch_from_akshare(num: int) -> list[dict[str, Any]]:
    """通过 akshare 获取财新网 + CCTV 财经新闻。"""
    try:
        from src.python.providers.akshare_news import fetch_news as ak_fetch
    except ImportError:
        logger.warning("akshare 模块不可用")
        return []

    items = ak_fetch(num=num)
    logger.info("akshare 新闻: 获取 %d 条", len(items))
    return items


_FETCH_MAP: dict[str, Callable] = {
    "sina": _fetch_from_sina,
    "eastmoney": _fetch_from_eastmoney,
    "cls": _fetch_from_cls,
    "wallstreetcn": _fetch_from_wallstreetcn,
    "akshare": _fetch_from_akshare,
}
