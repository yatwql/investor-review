"""财经新闻源获取模块。

管理各新闻源（新浪/东方财富/财联社/华尔街见闻/akshare）的获取函数和注册表。

各新闻源的启用在 config.json 中配置（news_sources 字段），
代码不硬编码开关状态。
"""

from __future__ import annotations

import logging
import threading
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
    """从新浪财经获取新闻，均匀覆盖多个分类（分类并发 + 分类内翻页）。

    三个分类（财经要闻/国内财经/国际财经）各走 `worker_pool` 并发、分类内仍逐页取；
    整源共享 `_SINA_SOURCE_BUDGET` 预算（先到先得，耗尽即收尾），合并时按分类顺序
    做 URL 去重。实测串行时单源 3.70s（其余源 0.29~1.33s），并发后墙钟取最慢分类。
    """
    try:
        from src.python.providers.sina_news import fetch_news as sina_fetch
    except ImportError:
        logger.warning("新浪财经模块不可用")
        return []

    lids = ["2516", "2509", "2510"]  # 财经要闻, 国内财经, 国际财经
    per_category = max(1, num // len(lids))
    per_page = 50  # API 每页上限
    deadline = time.monotonic() + _SINA_SOURCE_BUDGET
    exhausted = threading.Event()

    def _fetch_category(lid: str, target: int) -> list[dict[str, Any]]:
        """单个分类内翻页；分类内先按 URL 去重（无新增即止，避免死循环）。"""
        page = 1
        fetched: list[dict[str, Any]] = []
        seen: set[str] = set()
        while len(fetched) < target:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                exhausted.set()
                break
            need = min(per_page, target - len(fetched))
            items = sina_fetch(lid=lid, num=need, page=page, timeout=_sina_request_timeout(remaining))
            if not items:
                break
            added = 0
            for item in items:
                url = item.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    fetched.append(item)
                    added += 1
            page += 1
            if added == 0 or len(items) < need:
                break
        return fetched

    from src.python.core.concurrency import worker_pool

    per_lid: dict[str, list[dict[str, Any]]] = {}
    with worker_pool("batch:sina_news", len(lids), thread_name_prefix="sina_news") as pool:
        futures = {pool.submit(_fetch_category, lid, per_category): lid for lid in lids}
        for fut, lid in futures.items():
            try:
                per_lid[lid] = fut.result()
            except Exception:  # 单分类异常不影响其余分类
                logger.debug("[news] 新浪分类 %s 取数异常", lid, exc_info=True)
                per_lid[lid] = []

    # 合并（保持分类顺序；跨分类按 URL 去重，与串行实现的全局去重口径一致）
    all_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for lid in lids:
        for item in per_lid.get(lid, []):
            url = item.get("url", "")
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            all_items.append(item)

    if exhausted.is_set():
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
