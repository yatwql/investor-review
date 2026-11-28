"""基金风格判定的扩展数据预取 — 市值/PE 三级降级取数（push2 → 腾讯 → 代码段估算由报告侧兜底）。

职责边界：本模块只做**取数**（含会话缓存与文件缓存复用、熔断登记），不做风格判定。
风格判定属纯计算，留在 `report/fund_style_classify.py`；缓存预热与报告生成都要预取
同一批扩展数据，故预取必须落在取数层，否则预热只能反向依赖报告层。

三级来源：
  1. `push2_extended` — 复用行业数据通道（一次 push2 响应同带市值/PE/PB），
     自带 Provider Chain + 文件缓存 + 会话缓存；
  2. `tencent_extended` — 腾讯行情（自带全天 TTL 文件缓存，与第 1 级共享同一缓存键）；
  3. 代码段估算 — 由报告侧风格判定在两级都取不到时兜底，不在本模块。

返回字段口径：`market_cap` 统一为**元**（腾讯 f46 为亿，本模块换算）。
"""

from __future__ import annotations

import contextlib
import logging
from concurrent.futures import as_completed
from typing import Any

from src.python.core.code_utils import is_a_share_stock
from src.python.core.concurrency import worker_pool

logger = logging.getLogger("invest")

__all__ = [
    "batch_tencent_extended",
    "prefetch_extended_data",
    "push2_extended",
    "tencent_extended",
]


def push2_extended(code: str) -> dict[str, Any] | None:
    """获取市值+PE 扩展数据（复用行业数据请求通道，不另发 push2 请求）。

    这些字段与行业分类同属**一次** push2 请求的响应（provider 的 ``_FIELDS``
    已含 f9/f20/f23），故此处经 ``fetch_industry_data`` 取用——该入口自带
    Provider Chain、文件缓存与会话缓存，同一股票同一轮只请求一次。

    结果以全天 TTL 写入 ``extended_{code}`` 文件缓存，与 ``tencent_extended``
    共享（二级降级读取同一键，跨进程同日内不重复取数）。

    Args:
        code: 6 位 A 股代码

    Returns:
        {"market_cap": float, "pe": float, "pb": float} 或 None
    """
    from src.python.cache import get as _cache_get
    from src.python.cache import set as _cache_set
    from src.python.core.constants import CACHE_DAILY

    _key = f"extended_{code}"
    _cached = _cache_get(_key, CACHE_DAILY)
    if _cached is not None:
        return _cached

    try:
        from src.python.fetcher.industry import fetch_industry_data_cached

        # 走会话缓存变体：同一代码一轮报告内只探一次（含失败结果），
        # 直接调 fetch_industry_data 会让「取不到」的标的每轮重探。
        industry_data = fetch_industry_data_cached(code)
        if industry_data is None:
            return None

        result: dict[str, Any] = {}
        for field in ("market_cap", "pe", "pb"):
            value = industry_data.get(field)
            if value is None:
                continue
            with contextlib.suppress(ValueError, TypeError):
                result[field] = float(value)

        if result:
            _cache_set(_key, result)
        return result if result else None
    except Exception:  # noqa: BLE001 — 扩展数据获取失败 [%s]
        logger.warning("扩展数据获取失败 [%s]", code, exc_info=True)
        return None


def tencent_extended(code: str, name: str = "") -> dict[str, Any] | None:
    """从腾讯财经 API 获取市值+PE 扩展数据（二级降级）。

    结果以全天 TTL 写入文件缓存，同一股票同日内跨进程不重复请求。

    Args:
        code: 6 位 A 股代码

    Returns:
        {"market_cap": float, "pe": float} 或 None
    """
    from src.python.cache import get as _cache_get
    from src.python.cache import set as _cache_set
    from src.python.core.constants import CACHE_DAILY

    _key = f"extended_{code}"
    _cached = _cache_get(_key, CACHE_DAILY)
    if _cached is not None:
        return _cached

    from src.python.core.provider_registry import get_registry

    reg = get_registry()
    try:
        from src.python.fetcher.price import fetch_market_data

        # 带上名称：行情会话缓存按 (代码, 名称) 分键（00 重叠区同码可能是股票与
        # 场外基金两只证券），不传名称会与被持仓核算侧的带名调用分叉成两次取数。
        data = fetch_market_data(code, name)
        if data is None:
            return None

        result: dict[str, Any] = {}
        # Tencent f46 总市值单位为亿，转换为元以与 push2 单位一致
        market_cap = data.get("market_cap")
        if market_cap is not None and market_cap > 0:
            result["market_cap"] = market_cap * 1e8  # 亿 → 元

        pe = data.get("pe")
        if pe is not None and pe > 0:
            result["pe"] = pe

        if result:
            reg.record_success("tencent_style")
            _cache_set(_key, result)
            return result
        return None
    except Exception:  # noqa: BLE001 — Tencent 扩展数据获取失败 [%s]
        logger.warning("Tencent 扩展数据获取失败 [%s]", code, exc_info=True)
        reg.record_failure("tencent_style", f"extended:{code}")
        return None


def batch_tencent_extended(codes: list[str], names: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """并发批量通过腾讯 API 获取多只股票的扩展数据。

    当 push2 熔断时作为批量降级方案，避免逐个串行请求。
    结果同时写入 registry session_cache（domain="extended"）供主循环复用。

    Args:
        codes: 6 位 A 股代码列表

    Returns:
        {code: {"market_cap": float, "pe": float}, ...} —
        仅包含有成功返回的股票代码
    """
    if not codes:
        return {}
    results: dict[str, dict[str, Any]] = {}
    from src.python.fetcher.batch import get_batch_worker_count

    with worker_pool(
        "batch:fund_style",
        get_batch_worker_count("fund_style_workers", 8),  # 弱机器可配小
        thread_name_prefix="fund_style",
    ) as ex:
        _names = names or {}
        fut_map = {ex.submit(tencent_extended, c, _names.get(c, "")): c for c in codes}
        for fut in as_completed(fut_map):
            c = fut_map[fut]
            try:
                data = fut.result()
            except Exception:  # noqa: BLE001 — Tencent 批量并发获取失败 [%s]
                logger.warning("Tencent 批量并发获取失败 [%s]", c, exc_info=True)
                data = None
            if data is not None:
                results[c] = data
    # 同步写入 registry session_cache（主循环不会重复请求）
    if results:
        from src.python.core.provider_registry import get_registry

        reg = get_registry()
        for c, d in results.items():
            reg.session_cache_set("extended", c, d)
    return results


def prefetch_extended_data(
    holdings: list[dict],
    reg: Any,
) -> None:
    """预取各持仓股票的扩展数据（三级降级：push2 → Tencent → 代码段估算）。"""
    _codes_to_fetch = [
        c
        for h in holdings
        if (c := (h.get("code") or "").strip()) and c and is_a_share_stock(h.get("name", "") or "", c)
    ]
    _names: dict[str, str] = {(h.get("code") or "").strip(): (h.get("name") or "").strip() for h in holdings}
    # 去重：同一股票跨基金不重复请求
    _seen: set[str] = set()
    _unique_codes = [c for c in _codes_to_fetch if not (c in _seen or _seen.add(c))]
    # 仅处理尚未缓存到 registry session_cache 的代码
    _need_tencent: list[str] = []
    for code in _unique_codes:
        if reg.session_cache_contains("extended", code):
            continue
        ext_data = push2_extended(code)
        if ext_data is None:
            _need_tencent.append(code)
        else:
            reg.session_cache_set("extended", code, ext_data)
    # 并发批量腾讯回退（push2 熔断时的降级方案）
    if _need_tencent and not reg.is_circuit_broken("tencent_style"):
        batch_tencent_extended(_need_tencent, _names)
