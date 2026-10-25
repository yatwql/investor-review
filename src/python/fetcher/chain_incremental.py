"""历史序列增量合并 —— 按日合并/连续性校验、历史 provider 递补调度。

``fetch_with_incremental_fallback`` 是「链外手写降级路径」的统一出口：取数按日合并
（``_merge_by_date``）并校验交易日连续性（``_validate_continuity``）。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.cache import clear as cache_clear
from src.python.cache import get as cache_get
from src.python.cache import set as cache_set
from src.python.core.constants import CACHE_WEEKLY
from src.python.core.datasource_credential import (
    credential_hint,
    missing_credential,
)
from src.python.core.provider_registry import get_registry
from src.python.core.trading_calendar import count_trading_days_elapsed
from src.python.fetcher.chain_config import _get_chain
from src.python.fetcher.chain_diagnostics import (
    FailureDiagnostics,
    _brief_reason,
    _mark_provider_used,
)


logger = logging.getLogger("invest")


# ── 单轮报告内的历史取数复用与「空结果」短路 ───────────────────
# 同一份报告里多个消费方按不同窗口（20/35/90/260/365/400/750）取同一代码的历史，
# 而历史 chain 的缓存是「代码级」而非「窗口级」——每次调用都重新合并/续拉，
# 实测一轮上百次重复请求、数十秒白耗。这里做两层单轮约束：
#   1. 窗口复用：按（chain, code）记住本轮已取到的最大窗口，窗口 ≤ 已取到的
#      直接截尾返回；要更大窗口才真正再取一次。
#   2. 空结果短路：同一（chain, provider）连续多次返回空（结构性不支持，
#      如 hithink 对 A 股历史）→ 本行余下请求不再尝试它，只留一条汇总告警。
_RUN_HISTORY_MEMO: dict[tuple[str, str], tuple[int, list[dict]]] = {}
_EMPTY_STREAK: dict[tuple[str, str], int] = {}
_EMPTY_SKIP_LOGGED: set[tuple[str, str]] = set()

#: 同一 provider 对同一 chain 连续空结果达此值 → 判为结构性不覆盖，本轮跳过
_EMPTY_STREAK_SKIP = 5


def reset_run_history_state() -> None:
    """清空单轮历史取数状态（报告开始/测试隔离时调用）。"""
    _RUN_HISTORY_MEMO.clear()
    _EMPTY_STREAK.clear()
    _EMPTY_SKIP_LOGGED.clear()


def _try_providers(
    providers: list[str],
    registry: Any,
    chain_name: str,
    code: str,
    days: int,
    start_from: str | None,
    diagnostics: FailureDiagnostics | None = None,
) -> list[dict]:
    """遍历 providers 获取数据，返回第一个非空结果。

    Args:
        providers: provider 名称列表（按优先级排序）
        registry: DataSourceRegistry（熔断检测用）
        chain_name: chain 名称
        code: 证券代码
        days: 获取天数
        start_from: 起始日期，None 时获取完整 days 条数据
        diagnostics: 可选的失败原因收集器（不传则零采集）

    Returns:
        list[dict] 或 []（全部链路失败时）
    """
    for provider_name in providers:
        if registry.is_circuit_broken(provider_name):
            logger.debug("[%s] %s 已被熔断，跳过", chain_name, provider_name)
            if diagnostics is not None:
                diagnostics.add(provider_name, "已被熔断跳过")
            continue
        _streak_key = (chain_name, provider_name)
        if _EMPTY_STREAK.get(_streak_key, 0) >= _EMPTY_STREAK_SKIP:
            if _streak_key not in _EMPTY_SKIP_LOGGED:
                _EMPTY_SKIP_LOGGED.add(_streak_key)
                logger.warning(
                    "[%s] %s 连续 %d 次返回空数据，本行余下请求不再尝试（结构性不覆盖，非网络故障）",
                    chain_name,
                    provider_name,
                    _EMPTY_STREAK_SKIP,
                )
            if diagnostics is not None:
                diagnostics.add(provider_name, "连续空结果，本轮跳过")
            continue
        # 凭据就绪预检：与 fetch_with_fallback 同一判定（见彼处注释——配置级
        # 问题不计入熔断）。历史 chain 若缺此分支，需 key 的源会在此被当作
        # 「不可达」反复重试并累计熔断，正是本机制要消除的行为。
        _spec = missing_credential(provider_name)
        if _spec is not None:
            logger.info("[%s] %s 缺少凭据，跳过（%s）", chain_name, provider_name, _spec.env_var)
            if diagnostics is not None:
                diagnostics.add(provider_name, credential_hint(_spec))
            continue
        logger.info("[%s] 尝试 %s（code=%s, days=%d）", chain_name, provider_name, code, days)
        try:
            data = _call_history_provider(provider_name, chain_name, code, days, start_from)
            if not data:
                _EMPTY_STREAK[_streak_key] = _EMPTY_STREAK.get(_streak_key, 0) + 1
                logger.info("[%s] %s 返回空数据（无此品种历史数据），尝试下一链路", chain_name, provider_name)
                if diagnostics is not None:
                    diagnostics.add(provider_name, "返回空")
                continue
            _EMPTY_STREAK[_streak_key] = 0
            registry.record_success(provider_name)
            _mark_provider_used(chain_name, provider_name, _history_provider_label(provider_name))
            return data
        except Exception as e:
            reason = _brief_reason(f"{type(e).__name__}: {e}")
            registry.record_failure(provider_name, f"{chain_name}: {reason}")
            if diagnostics is not None:
                diagnostics.add(provider_name, reason)
            continue
    return []


def fetch_with_incremental_fallback(
    chain_name: str,
    code: str,
    days: int = 30,
    diagnostics: FailureDiagnostics | None = None,
) -> list[dict]:
    """增量合并版 Fallback 路由（历史数据用）。

    当检测到新旧数据重叠时，自动全量刷新缓存，确保历史修正被正确覆盖。

    - chain 层管理缓存读/写/合并
    - Provider 函数只负责纯数据获取（不碰缓存层）
    - 熔断器预检、fallback 遍历与 fetch_with_fallback() 共享

    Args:
        chain_name: chain 名称（如 "history_stock"、"history_fund_otc"）
        code: 证券代码
        days: 获取天数（默认 30）
        diagnostics: 可选的失败原因收集器（不传则零采集）

    Returns:
        list[dict]: 按日期升序排列的数据列表，至少返回 days 条。
        全链路失败时返回空列表（不使用过期缓存——走势数据降级后显示占位文本）。
    """
    cache_key = f"history_{chain_name}_{code}"
    # 单轮窗口复用：同一（chain, code）已被更大窗口取过时直接截尾，不再走
    # 缓存合并与 provider 链路（同一份报告内多个消费方各拉一道的根源）。
    _memo_key = (chain_name, code)
    _memo = _RUN_HISTORY_MEMO.get(_memo_key)
    if _memo is not None and _memo[0] >= days:
        return _memo[1][-days:]

    cached = cache_get(cache_key, CACHE_WEEKLY) or []
    last_cached_date = cached[-1]["date"] if cached else None
    # 缓存历史短于请求窗口时，增量续拉永远补不长（新数据只从缓存尾部续上，
    # 合并后仍 < days，且每次调用都重复同一路径）——滚动窗口类消费会拿到恒定
    # 短历史。此时直接从头全量拉取一次补齐：start_from=None 后 provider 全量
    # 返回会命中下方「new_data[0] ≤ cached[0]」替换分支刷新缓存；拉取失败则
    # 落回既有 `elif cached` 分支返回短缓存（降级不阻断，尽力而为满足
    # 「至少 days 条」契约）。短历史仪器（上市不足 days）重复全量的代价与单次增量等同。
    if cached and len(cached) < days:
        last_cached_date = None

    registry = get_registry()
    providers = _get_chain(chain_name)

    # 第一轮：增量获取（从 last_cached_date 开始）
    new_data = _try_providers(providers, registry, chain_name, code, days, last_cached_date, diagnostics)

    if new_data:
        # 判断 provider 是否实际支持增量获取。
        # 若新数据起点 ≤ 缓存起点，说明 provider 未按 start_from 过滤
        # （如 OTC 基金 fetch_fund_nav_history 始终全量返回），
        # 直接写入新数据，跳过合并与重叠检测。
        if cached and new_data and new_data[0].get("date", "") <= cached[0].get("date", ""):
            logger.debug("[%s] %s provider 全量返回，直接使用新数据", chain_name, code)
            cache_set(cache_key, new_data)
            _RUN_HISTORY_MEMO[_memo_key] = (max(days, len(new_data)), new_data)
            return new_data[-days:]

        merged = _merge_by_date(cached, new_data)
        needs_refresh = False
        try:
            needs_refresh = _validate_continuity(cached, new_data, cache_key)
        except Exception:
            logger.warning("[%s] 连续性校验异常（不影响合并）", cache_key)

        if needs_refresh and cached:
            streak_key = f"{cache_key}_correction_streak"
            streak = int(cache_get(streak_key, CACHE_WEEKLY) or 0)
            cache_set(streak_key, streak + 1)  # 每次检出都计数：若全量刷新无法根治，下次继续累计
            if streak + 1 >= _CORRECTION_STREAK_SKIP:
                # 结构性回看：全量刷新未能消除重叠（源对增量固定向前多看若干天），
                # 按日合并的同日覆盖已能吸收窗口内修正——跳过多拉一次全量
                logger.warning(
                    "[%s] 连续 %d 次检出重叠，判定为源结构性回看：跳过全量刷新，沿用按日合并结果",
                    cache_key,
                    streak + 1,
                )
            else:
                # 检测到历史修正（如除权除息回溯调整）：旧缓存中非重叠部分已过时
                # 自动全量刷新：删旧缓存，不带 start_from 重新获取完整历史
                logger.info("[%s] 检测到历史修正 → 自动全量刷新", chain_name)
                cache_clear(cache_key)
                full_data = _try_providers(providers, registry, chain_name, code, days, None, diagnostics)
                if full_data:
                    cache_set(cache_key, full_data)
                    _RUN_HISTORY_MEMO[_memo_key] = (max(days, len(full_data)), full_data)
                    return full_data[-days:]
                logger.warning("[%s] 全量刷新失败，使用增量合并数据（仅修正重叠窗口）", chain_name)

            # 全量刷新失败或冷却跳过 → 降级：用合并结果继续（merged 已含重叠窗口新数据）
        if not needs_refresh:
            streak_key = f"{cache_key}_correction_streak"
            if cache_get(streak_key, CACHE_WEEKLY):
                cache_set(streak_key, 0)  # 正常合并（无重叠检出）→ 重置连续触发计数
        cache_set(cache_key, merged)
        _RUN_HISTORY_MEMO[_memo_key] = (max(days, len(merged)), merged)
        return merged[-days:]
    elif cached:
        # 有缓存但无新数据 — 返回已有缓存（同样入本轮 memo：无新数据时下次同窗口
        # 请求不必再走一遍 provider 链路）
        _RUN_HISTORY_MEMO[_memo_key] = (max(days, len(cached)), cached)
        return cached[-days:]

    return []


_HISTORY_PROVIDER_MAP: dict[str, str] = {
    "tencent": "src.python.providers.tencent",
    "sina": "src.python.providers.sina",
    "tiantian": "src.python.providers.tiantian_nav",
    "eastmoney": "src.python.providers.eastmoney",
    "hithink": "src.python.providers.hithink",
}


#: 历史链路 provider 展示名——模块未声明 ``DISPLAY_NAME`` 者在此补齐（声明了的以模块为准）
_HISTORY_PROVIDER_LABELS: dict[str, str] = {
    "tencent": "腾讯财经",
    "sina": "新浪财经",
    "tiantian": "天天基金",
    "eastmoney": "东方财富",
}


def _history_provider_label(provider_name: str) -> str:
    """历史链路 provider → 展示名（模块 ``DISPLAY_NAME`` 优先；其次本表；末位回退标识）。"""
    module_path = _HISTORY_PROVIDER_MAP.get(provider_name)
    if module_path:
        try:
            import importlib

            declared = getattr(importlib.import_module(module_path), "DISPLAY_NAME", "")
            if declared:
                return str(declared)
        except Exception:  # 展示名解析失败不影响取数
            logger.debug("[history] provider 展示名解析失败: %s", provider_name, exc_info=True)
    return _HISTORY_PROVIDER_LABELS.get(provider_name, provider_name)


# 新旧 K 线之间缺失的交易日数超过此值 → 判定数据跳空（部分历史不可达）
_MAX_GAP_TRADING_DAYS: int = 5

# 历史修正全量刷新冷却阈值：部分源对增量请求固定向前回看若干天（结构性重叠），
# 全量刷新无法根治——连续检出重叠达到该阈值后判定为源结构性回看，跳过全量刷新
# （_merge_by_date 的同日覆盖已能吸收窗口内修正），避免每次运行都多拉一次全量。
_CORRECTION_STREAK_SKIP = 3


def _call_history_provider(
    provider_name: str,
    chain_name: str,
    code: str,
    days: int,
    start_from: str | None,
) -> list[dict]:
    """动态调用对应 provider 的历史数据获取函数。

    通过 _HISTORY_PROVIDER_MAP 实现惰性导入，避免模块加载时的循环依赖。

    Args:
        provider_name: provider 名称（如 "tencent"、"sina"、"tiantian"）
        chain_name: chain 名称（决定调用 fetch_kline 还是 fetch_fund_nav_history）
        code: 证券代码
        days: 获取天数
        start_from: 起始日期（YYYY-MM-DD），增量获取参数

    Returns:
        list[dict] 或 []（失败时）
    """
    import importlib

    module_path = _HISTORY_PROVIDER_MAP.get(provider_name)
    if not module_path:
        logger.warning("[history] 未知 Provider: %s", provider_name)
        return []

    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        logger.warning("[history] 导入 %s 失败: %s", module_path, e)
        return []

    if chain_name == "history_fund_otc":
        fn = getattr(mod, "fetch_fund_nav_history", None)
        if fn:
            return fn(code)
    elif chain_name in ("history_index", "history_index_us"):
        # 两条链共用指数 K 线函数：命中 provider 有实现才真正发起请求，
        # 无实现者落到末尾的统一告警。
        fn = getattr(mod, "fetch_index_kline", None)
        if fn:
            return fn(code, days=days, start_from=start_from)
    elif chain_name == "history_stock":
        fn = getattr(mod, "fetch_kline", None)
        if fn:
            return fn(code, days=days, start_from=start_from)

    fn_name = {
        "history_stock": "fetch_kline",
        "history_index": "fetch_index_kline",
        "history_index_us": "fetch_index_kline",
        "history_fund_otc": "fetch_fund_nav_history",
    }.get(chain_name, "未知函数")
    logger.warning("[history] %s 无 %s 函数", provider_name, fn_name)
    return []


def clear_incremental_cache(chain_name: str, code: str) -> None:
    """清空增量链路的文件缓存（供调用方检测到窗口缩水时强制全量重取）。

    缓存键格式与 :func:`fetch_with_incremental_fallback` 保持一致，
    避免调用方重复拼接键名。
    """
    cache_clear(f"history_{chain_name}_{code}")


def _merge_by_date(cached: list[dict], new_data: list[dict]) -> list[dict]:
    """按日期合并去重，new_data 中同天数据覆盖 cached（修正感知）。

    Args:
        cached: 已有的缓存数据列表（按日期升序）
        new_data: 新获取的数据列表（按日期升序）

    Returns:
        合并后的完整数据列表（按日期升序）
    """
    seen = {d["date"] for d in cached}
    merged = list(cached)
    for d in new_data:
        if d["date"] in seen:
            # 覆盖旧数据（处理历史修正）
            _replace_by_date(merged, d)
        else:
            merged.append(d)
    return sorted(merged, key=lambda x: x["date"])


def _replace_by_date(data: list[dict], item: dict) -> None:
    """在已排序列表中用同日期项替换。"""
    for i, existing in enumerate(data):
        if existing["date"] == item["date"]:
            data[i] = item
            break


def _validate_continuity(cached: list[dict], new_data: list[dict], cache_key: str) -> bool:
    """校验新旧数据连续性，检测历史修正信号。

    注意：此函数为纯检测/日志用途，异常不影响主流程。
    调用方应在 try/except 中包装。

    Returns:
        True 检测到数据重叠（可能为历史修正，调用方可据此触发全量刷新）
        False 无重叠或数据不足
    """
    if not cached or not new_data:
        return False
    last_old = cached[-1]
    first_new = new_data[0]

    # 检测日期重叠：新数据首日早于旧数据末日（非相等，相等=API 包含边界日），说明有修正
    if first_new.get("date") < last_old.get("date"):
        logger.warning("[%s] 新旧数据重叠——可能是历史修正，自动全量刷新", cache_key)
        cache_set(f"{cache_key}_correction_flag", True)
        return True
    else:
        gap = _missing_trading_days(last_old.get("date"), first_new.get("date"))
        if gap > _MAX_GAP_TRADING_DAYS:
            logger.warning("[%s] 数据跳空 %d 个交易日——部分历史不可达", cache_key, gap)
    return False


def _missing_trading_days(date1: str | None, date2: str | None) -> int:
    """计算两个 K 线日期之间**缺失**的交易日数（不含两端）。

    以交易日而非自然日计——周末与长假会放大自然日差（如国庆前后相邻的两个
    交易日相差 10 个自然日），按自然日判定会把正常连续的 K 线误判为跳空。
    相邻交易日 → 0；两端相等/逆序、日期为空或格式非法 → 0。
    """
    if not date1 or not date2:
        return 0
    elapsed = count_trading_days_elapsed(date1, date2)
    if elapsed is None or elapsed <= 0:
        return 0
    return elapsed - 1
