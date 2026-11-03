"""行业分类 / 概念板块数据获取。

Provider Chain（可配置）：
  1. eastmoney_industry — 东方财富 push2（主链路，含概念板块）
  2. eastmoney_industry_rest — 东方财富行情页（备用，纯行业分类）
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.python.cache import get_ttl
from src.python.core.code_utils import is_a_share_code
from src.python.core.log_dedupe import log_throttled
from src.python.fetcher.chain import FailureDiagnostics, fetch_with_fallback, is_provider_chain_broken
from src.python.providers import eastmoney_industry, eastmoney_industry_rest

logger = logging.getLogger("invest")

# 申万行业层级后缀：行业名末尾的 Ⅰ/Ⅱ/Ⅲ/Ⅳ（如「银行Ⅱ」「白酒Ⅱ」）是申万分层命名标记
# （层级与上级/同名行业区分），对零售报告是纯展示噪音。统一在网关剥离，消费方见干净名。
_HIERARCHY_SUFFIX_RE = re.compile(r"[ⅠⅡⅢⅣ]+$")


_INDUSTRY_CACHE_PREFIX = "industry_"

_INDUSTRY_PROVIDERS: dict[str, tuple[str, Any]] = {
    "eastmoney_industry": ("东方财富行业", eastmoney_industry.fetch_industry_and_concepts),
    "eastmoney_industry_rest": ("东方财富行业(行情页)", eastmoney_industry_rest.fetch_industry_and_concepts),
}

# 批量获取失败重试：重试等待基秒数 + 随机抖动
_BATCH_RETRY_DELAY = 0.8
_BATCH_RETRY_JITTER = 0.4


def strip_hierarchy_suffix(name: str | None) -> str | None:
    """剥离行业名末尾的申万层级后缀（Ⅰ/Ⅱ/Ⅲ/Ⅳ）。

    东方财富 f127 / bk_name 返回申万行业名带层级标记（如「银行Ⅱ」「白酒Ⅱ」——
    申万用 Ⅰ/Ⅱ/Ⅲ 区分同级同名行业与上级层级）。对零售报告读者，该后缀是纯
    层级噪音，展示时统一剥离（「银行Ⅱ」→「银行」）；无后缀或空串原样返回。

    Args:
        name: 原始行业名（如 "银行Ⅱ"）

    Returns:
        剥离层级后缀后的行业名（如 "银行"）
    """
    if not name:
        return name
    return _HIERARCHY_SUFFIX_RE.sub("", name)


def _industry_transform(raw: dict | None, _source: str) -> dict | None:
    """东方财富行业原始数据 → 统一行业格式（行业名剥离申万层级后缀）。

    同时**透传**同一次 push2 响应已带出的扩展行情字段（pe/pb/market_cap）。
    这些字段与行业分类来自同一个请求（见 ``_FIELDS``），在此丢弃会让消费方
    只能再发一次同参数请求——即会话缓存要消除的重复取数。
    """
    if not raw:
        return None
    return {
        "code": raw.get("code", ""),
        "industry": strip_hierarchy_suffix(raw.get("industry", "") or ""),
        "industry_id": raw.get("industry_id", ""),
        "concepts": raw.get("concepts", []),
        "concept_ids": raw.get("concept_ids", []),
        "pe": raw.get("pe"),
        "pb": raw.get("pb"),
        "market_cap": raw.get("market_cap"),
    }


def fetch_industry_data(code: str) -> dict | None:
    """获取一只证券的行业分类和概念板块归属。

    缓存键: industry_{code}.json
    缓存 TTL: 两周（可通过 cache_ttl.industry 配置）

    Args:
        code: 6 位证券代码

    Returns:
        {code, industry, industry_id, concepts, concept_ids, pe, pb, market_cap}
        失败返回 None
    """
    from src.python.report.data_status import get_tracker

    _t = get_tracker()
    _src_key = f"industry_{code.strip()}"
    industry_cache_key = _INDUSTRY_CACHE_PREFIX + code.strip()
    diag = FailureDiagnostics()
    result = fetch_with_fallback(
        "industry",
        _INDUSTRY_PROVIDERS,
        industry_cache_key,
        get_ttl("industry"),
        fn_kwargs={"code": code.strip()},
        transform=_industry_transform,
        diagnostics=diag,
    )
    if result is not None:
        # 热缓存命中的旧值可能未经 transform（历史缓存含申万层级后缀），出口统一归一化
        result["industry"] = strip_hierarchy_suffix(result.get("industry") or "")
        _t.record(_src_key, "T3", success=True)
    else:
        _t.record(_src_key, "T3", success=False, failure_type="unreachable", message=diag.summary())
    return result


def fetch_industry_data_cached(code: str) -> dict | None:
    """行业数据获取（含会话缓存），同一报告生成中同证券只获取一次。

    消除多个模块独立调用 fetch_industry_data 的冗余文件缓存读取。
    """
    from src.python.core.provider_registry import get_registry

    # 失败也写会话缓存（值为 None）：场外基金等非 A 股标的会被上层逐个调用，
    # 不缓存失败结果时同一代码在一轮报告里会被反复重探（实测同一键未命中 16 次）；
    # single-flight 再压并发首探——三个报告阶段并行查同一只时只探一次。
    return get_registry().session_cache_fetch("industry", code, lambda: fetch_industry_data(code))


def fetch_valuation_fields(code: str) -> dict[str, float | None] | None:
    """获取一只证券的当前 PE/PB（经 Provider Chain + 文件/会话缓存）。

    PE 与市净率是东财 push2 响应中的扩展字段（f9/f23），与行业分类同属一次
    请求——故经行业数据入口取用，而不是绕开 Provider Chain 直连 provider。
    好处：享受链路熔断/降级/诊断与 7 天文件缓存，同一代码同会话不重复取数。

    Args:
        code: 6 位 A 股代码

    Returns:
        {"pe": float|None, "pb": float|None}；数据不可得返回 None。
    """
    data = fetch_industry_data_cached(code)
    if data is None:
        return None
    return {"pe": data.get("pe"), "pb": data.get("pb")}


def _retry_industry_fetch(code: str) -> dict | None:
    """批内重试专用取数：绕开会话缓存，并把新结论回写。

    会话缓存会记住失败结论（防同轮重探），若重试也走 `fetch_industry_data_cached`，
    首次失败即被记忆、重试退化为空转——「失败后重试」这条降级治理要求因此失效
    （双重降级治理：链路失败必须真重试，只有最终结论才进会话缓存）。
    """
    from src.python.core.provider_registry import get_registry

    result = fetch_industry_data(code)
    get_registry().session_cache_set(
        "industry", code, result, source="api" if result is not None else "miss"
    )
    return result


def batch_fetch_industry_data(codes: list[str]) -> dict[str, dict]:
    """批量获取多只证券的行业分类和概念板块归属。

    使用 BatchDispatcher 统一并行调度，支持缓存优先、熔断预检、通用重试。
    非 A 股代码（美股/港股等）自动跳过，不调用 API。
    并发数由配置 `industry_workers` 控制（见 get_batch_worker_count）。

    注：「持仓是否按 A 股个股处理」（排除 `00` 前缀重叠区场外基金）属**调用方路由决策**
    ——有名称的调用方先用 `core.code_utils.is_a_share_stock(name, code)` 过滤后再传入；
    本函数内的前缀过滤仅作防御（拦截美股/港股等非 A 股）。

    Args:
        codes: 6 位证券代码列表

    Returns:
        {code: {code, industry, concepts, ...}, ...}
    """
    valid_codes = [c.strip() for c in codes if c and c.strip()]
    if not valid_codes:
        return {}

    # 过滤非 A 股代码，避免无效 API 调用
    a_codes = [c for c in valid_codes if is_a_share_code(c)]
    skipped = len(valid_codes) - len(a_codes)
    if skipped:
        logger.debug("跳过 %d 个非 A 股代码（行业数据仅支持 A 股）", skipped)

    if not a_codes:
        return {}

    # 会话缓存已给过结论（成功或明确取不到）的代码不再进批：既省一次文件缓存探测，
    # 也让「同键未命中」告警只反映真实重探（同一代码一轮内被多次批量查询时，
    # 此前每次都记一次未命中，命中率与告警都被稀释）。
    from src.python.core.provider_registry import NOT_FOUND, get_registry

    _registry = get_registry()
    settled: dict[str, dict] = {}
    pending: list[str] = []
    for code in a_codes:
        _cached = _registry.session_cache_get("industry", code)
        if _cached is NOT_FOUND:
            pending.append(code)
        elif _cached:
            settled[code] = _cached
    a_codes = pending
    if not a_codes:
        return settled

    # 熔断预检：全链已熔断时跳过批量请求，避免逐条冗余调用
    if is_provider_chain_broken("industry"):
        logger.warning("[industry] 行业数据 API 全链不可用（熔断），跳过 %d 个代码的批量获取", len(a_codes))
        return {}

    from functools import partial

    from src.python.fetcher.batch import BatchDispatcher, get_batch_worker_count

    dispatcher = BatchDispatcher(
        max_workers=get_batch_worker_count("industry_workers", 8),
        thread_name_prefix="batch_industry",
        rate_limit_provider="eastmoney_industry",
    )

    # 走会话缓存变体：同一代码一轮报告内只探一次（失败结论也记），
    # 否则失败标的会在「批内 → 重试 → 下一阶段再来一批」里被反复重探
    # （实测场外基金同一缓存键一轮未命中 16 次，污染「同键未命中」告警指向）。
    items = [
        (
            f"{_INDUSTRY_CACHE_PREFIX}{code}",
            partial(fetch_industry_data_cached, code=code),
        )
        for code in a_codes
    ]

    def _cache_check(cache_id: str) -> Any:
        """批前预检只看会话缓存（已结案即跳过调度）。

        文件缓存探测有意留在任务内的 `fetch_with_fallback`：那里已由会话级
        single-flight 收口，每个代码一轮只探一次；若此处直接 `cache_get`，
        三个并行报告阶段会为同一只标的各记一次未命中（实测 `industry_005827` ×3），
        而「同键未命中」告警本应只指向真实重探。
        """
        code = cache_id[len(_INDUSTRY_CACHE_PREFIX) :]
        cached = _registry.session_cache_get("industry", code)
        return None if cached is NOT_FOUND else cached

    results = dispatcher.execute_with_cache_check(
        items,
        cache_check_fn=_cache_check,
        strict_none=True,
    )

    # 通用重试（复用主 executor）
    results = dispatcher.retry_failed(
        results,
        task_factory=lambda idx: partial(_retry_industry_fetch, code=a_codes[idx]),
        delay=_BATCH_RETRY_DELAY,
        jitter=_BATCH_RETRY_JITTER,
    )

    result_map: dict[str, dict] = dict(settled)
    for code, r in zip(a_codes, results):
        if r.success and r.result:
            # 缓存命中路径绕过 fetch_industry_data 出口归一化，组装时兜底剥离层级后缀
            r.result["industry"] = strip_hierarchy_suffix(r.result.get("industry") or "")
            result_map[code] = r.result

    dispatcher.shutdown()
    failed = sum(1 for r in results if not r.success and not r.skipped)
    if failed:
        logger.warning("[industry] 行业数据批量失败 %d/%d（push2 已回落备用链路）", failed, len(a_codes))
    log_throttled(
        logger,
        "industry_batch_ready",
        "批量行业数据就绪: %d/%d 个代码（含缓存命中）",
        len(result_map),
        len(a_codes),
    )
    return result_map
