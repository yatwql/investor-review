"""缓存操作共享层 — TUI 和 CLI 共用。

公共缓存函数（盈利预测/行业资金流向/行业/分红）+ print→reporter 替换
行情类缓存（价格+指数）+ 清理 + 统计
"""

from __future__ import annotations

import os
from concurrent.futures import as_completed
from dataclasses import dataclass, field

import src.python.core.logger as _logger_mod

logger = _logger_mod.setup_logger()


# ── 数据结构 ───────────────────────────────────────────────


from ._cache_refresh import (  # noqa: E402, F401 — 兼容既有导入面
    _POOL,
    _get_news_top_count,
    _get_pool,
    _refresh_common_caches,
    _refresh_dividend_cache,
    _refresh_extended_cache,
    _refresh_extended_caches,
    _refresh_fund_manager_cache,
    _refresh_industry_cache,
    _refresh_news_cache,
    _refresh_one_fund_cache,
    _refresh_profit_forecast_cache,
    _refresh_sector_flow_cache,
    _sector_flow_hint,
)


@dataclass
class CacheUpdateResult:
    """基础缓存更新结果。"""

    total_funds: int = 0
    holdings_count: int = 0
    perf_ok: int = 0
    hold_ok: int = 0
    bm_ok: int = 0
    pf_ok: int = 0
    sf_ok: int = 0
    ind_ok: int = 0
    div_ok: int = 0
    # 扩展缓存刷新：新闻 / 基金经理 / 风格扩展
    news_ok: int = 0
    manager_ok: int = 0
    ext_ok: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if (
            self.total_funds == 0
            and self.pf_ok == 0
            and self.sf_ok == 0
            and self.news_ok == 0
            and self.manager_ok == 0
            and self.ext_ok == 0
        ):
            return 2
        if self.errors:
            return 1
        return 0


@dataclass
class PositionCacheResult:
    """行情类缓存（价格+指数）更新结果。"""

    total: int = 0
    price_ok: int = 0
    a_index_count: int = 0
    us_index_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if self.total == 0:
            return 2
        if self.errors:
            return 1
        return 0


@dataclass
class CacheStats:
    """缓存统计信息。"""

    total_files: int = 0
    total_size_bytes: int = 0
    expired: int = 0
    hit_rate: float = 0.0
    hit_total: int = 0
    by_prefix: dict[str, int] = field(default_factory=dict)
    top_by_size: list[tuple[str, int]] = field(default_factory=list)
    # 快照目录
    snapshot_files: int = 0
    snapshot_size_bytes: int = 0
    # 运行时状态
    state_files: int = 0
    state_size_bytes: int = 0


# ── 内部线程池（仅 operations 内部使用）──


# ═══════════════════════════════════════════════════════════════
# 基金刷新
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 公共缓存函数
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 公共缓存并行刷新（print→reporter 替换）
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 扩展缓存（新闻 / 基金经理 / 风格扩展）
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# update_basic_cache（基金 + 公共缓存 + 扩展缓存）
# ═══════════════════════════════════════════════════════════════


def update_basic_cache(holdings: list, reporter) -> CacheUpdateResult:
    """更新基础类缓存（基金业绩+持仓+基准 + 公共缓存 + 扩展缓存）。

    内部管理线程池，operations 池唯一存在。
    基金刷新 + 公共缓存并行获取；随后并行刷新扩展缓存（新闻/基金经理/风格扩展）。

    Args:
        holdings: 持仓列表
        reporter: 进度报告接口

    Returns:
        CacheUpdateResult — TUI 外壳可据此输出格式化结果
    """
    from src.python.cache import clear_by_group

    result = CacheUpdateResult()
    result.holdings_count = len(holdings)

    # 先清旧缓存（匹配 TUI 语义）
    clear_by_group("refresh")

    from src.python.report.fund_performance import is_fund

    funds = [h for h in holdings if is_fund(h)]
    result.total_funds = len(funds)

    pool = _get_pool()

    if not funds:
        # 无基金：刷新公共缓存 + 扩展缓存（新闻/风格扩展，跳过基金经理）
        result.pf_ok, result.sf_ok, result.ind_ok, result.div_ok = _refresh_common_caches(holdings, reporter)
        _refresh_extended_caches(holdings, [], result, reporter)
        return result

    # 有基金：基金 + 公共缓存并行提交，随后刷新扩展缓存
    reporter.info("正在并行获取全部缓存数据...")
    all_futures: dict = {}
    for f in funds:
        all_futures[pool.submit(_refresh_one_fund_cache, f)] = ("fund", f)
    all_futures[pool.submit(_refresh_profit_forecast_cache)] = ("profit_forecast", None)
    all_futures[pool.submit(_refresh_sector_flow_cache)] = ("sector_flow", None)
    if holdings:
        all_futures[pool.submit(_refresh_industry_cache, holdings)] = ("industry", None)
        all_futures[pool.submit(_refresh_dividend_cache, holdings)] = ("dividend", None)

    for future in as_completed(all_futures):
        tag, _ = all_futures[future]
        try:
            res = future.result()
            if tag == "fund":
                _, code, name, p_ok, h_ok, h_cnt, b_ok = res
                if p_ok:
                    result.perf_ok += 1
                if h_ok:
                    result.hold_ok += 1
                if b_ok:
                    result.bm_ok += 1
                reporter.ok(
                    f"{name} ({code}) — 业绩={'OK' if p_ok else '失败'} | "
                    f"持仓={h_cnt}条 | 基准={'OK' if b_ok else '未找到'}"
                )
            elif tag == "profit_forecast":
                result.pf_ok = res[1]
                if result.pf_ok:
                    reporter.ok(f"盈利预测 ({result.pf_ok} 只股票)")
                else:
                    reporter.warn("盈利预测 获取失败")
            elif tag == "sector_flow":
                result.sf_ok = res[1]
                if result.sf_ok:
                    reporter.ok(f"行业资金流向 ({result.sf_ok} 个行业)")
                else:
                    reporter.warn(f"行业资金流向 {_sector_flow_hint()}")
            elif tag == "industry":
                result.ind_ok = res
                if result.ind_ok:
                    reporter.ok(f"行业分类 ({result.ind_ok} 只证券)")
                else:
                    reporter.warn("行业分类 获取失败")
            elif tag == "dividend":
                result.div_ok = res
                if result.div_ok:
                    reporter.ok(f"分红数据 ({result.div_ok} 只股票)")
                else:
                    reporter.warn("分红数据 获取失败")
        except Exception as e:
            logger.debug("缓存刷新 Future 异常: %s", e)
            result.errors.append(f"缓存刷新异常: {e}")
            reporter.warn("基金刷新异常" if tag == "fund" else "其他缓存刷新异常")

    _refresh_extended_caches(holdings, funds, result, reporter)

    return result


# ═══════════════════════════════════════════════════════════════
# 行情类缓存（价格+指数）
# ═══════════════════════════════════════════════════════════════


def _fetch_prices_and_indices(holdings: list, reporter) -> PositionCacheResult:
    """并行获取持仓价格 + 市场指数，通过 reporter.* 输出进度。

    内部管理线程池，operations 池唯一存在。
    """
    from src.python.fetcher.index import fetch_indices, fetch_us_indices
    from src.python.fetcher.price import fetch_market_data

    result = PositionCacheResult(total=len(holdings))
    pool = _get_pool()
    fut_map: dict = {}

    for h in holdings:
        fut_map[pool.submit(fetch_market_data, h.code, h.name)] = h
    idx_a_fut = pool.submit(fetch_indices)
    idx_us_fut = pool.submit(fetch_us_indices)
    fut_map[idx_a_fut] = None
    fut_map[idx_us_fut] = None

    for future in as_completed(fut_map):
        h_or_none = fut_map[future]
        try:
            if h_or_none is None:
                idx_res = future.result() or {}
                if future is idx_a_fut:
                    result.a_index_count = len(idx_res)
                    reporter.ok(f"A 股指数: {result.a_index_count} 个")
                else:
                    result.us_index_count = len(idx_res)
                    reporter.ok(f"美股指数: {result.us_index_count} 个")
            else:
                h = h_or_none
                price_res = future.result()
                if price_res and price_res.get("price", 0) > 0:
                    result.price_ok += 1
                    reporter.ok(f"{h.name} ({h.code}) → {price_res['price']:.4f}")
                else:
                    reporter.warn(f"{h.name} ({h.code}) → 失败")
        except Exception as e:
            if h_or_none is not None:
                _msg = str(e)
                if any(kw in _msg.lower() for kw in ("connect", "timeout", "network", "reset")):
                    _hint = "网络异常"
                elif "parse" in _msg.lower() or "decode" in _msg.lower():
                    _hint = "数据解析失败"
                else:
                    _hint = "获取失败"
                reporter.error(f"{h_or_none.name} ({h_or_none.code}) → {_hint}")
                result.errors.append(f"{h_or_none.name}: {_hint}")

    return result


def update_position_cache(holdings: list, reporter) -> PositionCacheResult:
    """更新行情类缓存（价格+指数）。

    内部管理线程池，使用 reporter.* 输出进度。
    """
    from src.python.cache import clear_by_group

    clear_by_group("preload")
    reporter.info("正在并行获取持仓价格/净值 + 市场指数...")
    return _fetch_prices_and_indices(holdings, reporter)


# ═══════════════════════════════════════════════════════════════
# 缓存清理 + 统计
# ═══════════════════════════════════════════════════════════════


def cleanup_cache(reporter) -> int:
    """清理过期缓存文件。

    Returns:
        清理的文件数量
    """
    from src.python.cache import cleanup_expired, get_cache_dir

    reporter.info("正在扫描缓存目录...")
    removed = cleanup_expired(dry_run=False)
    cache_dir = get_cache_dir()
    if removed > 0:
        reporter.ok(f"已删除 {removed} 个过期缓存文件 ({cache_dir})")
    else:
        reporter.info(f"无需清理 ({cache_dir})")
    return removed


def get_cache_stats(reporter) -> CacheStats:
    """返回缓存统计信息，无 print 格式化。

    扫描 data/cache、data/history/snapshots、data/state 三个目录。
    """
    from src.python.cache import (
        cleanup_expired,
        get_cache_hit_rate,
    )
    from src.python.cache import (
        get_cache_stats as _get_cache_stats,
    )
    from src.python.core.constants import PROJECT_ROOT

    stats = CacheStats()
    raw_stats = _get_cache_stats()
    hit_rate = get_cache_hit_rate()

    # ── 1. data/cache ──
    stats.total_files = raw_stats.get("total_files", 0)
    stats.total_size_bytes = raw_stats.get("total_size_bytes", 0)
    if hit_rate.get("total", 0) > 0:
        stats.hit_rate = hit_rate.get("rate", 0.0) * 100
        stats.hit_total = hit_rate.get("total", 0)
    stats.by_prefix = raw_stats.get("by_prefix", {})
    stats.top_by_size = raw_stats.get("top_by_size", [])

    reporter.info(f"缓存文件: {stats.total_files} 个 | 大小: {stats.total_size_bytes / 1024:.0f} KB")
    if stats.hit_total > 0:
        reporter.info(f"命中率: {stats.hit_rate:.1f}%")
    reporter.info("正在检查过期文件...")
    stats.expired = cleanup_expired(dry_run=True)
    reporter.info(f"过期文件: {stats.expired} 个")

    # ── 2. data/history/snapshots ──
    _hist_dir = os.path.join(PROJECT_ROOT, "data", "history", "snapshots")
    if os.path.isdir(_hist_dir):
        s_files = s_size = 0
        for _f in os.listdir(_hist_dir):
            _fp = os.path.join(_hist_dir, _f)
            if os.path.isfile(_fp) and _f.endswith(".json"):
                s_files += 1
                s_size += os.path.getsize(_fp)
        stats.snapshot_files = s_files
        stats.snapshot_size_bytes = s_size

    # ── 3. data/state ──
    _state_dir = os.path.join(PROJECT_ROOT, "data", "state")
    if os.path.isdir(_state_dir):
        s_files = s_size = 0
        for _f in os.listdir(_state_dir):
            _fp = os.path.join(_state_dir, _f)
            if os.path.isfile(_fp):
                s_files += 1
                s_size += os.path.getsize(_fp)
        stats.state_files = s_files
        stats.state_size_bytes = s_size

    return stats


# 公开别名：展示提示文案（渠道层统一用此名；私有名保留供既有内部引用）
sector_flow_hint = _sector_flow_hint


def update_all_cache(holdings: list, reporter) -> int:
    """基础 + 持仓全量缓存更新（最大努力模式，渠道无关）。

    basic 失败仍继续 position；退出码取两者最大值（单调：失败等级越高越严重）。

    Args:
        holdings: 持仓列表
        reporter: 进度报告接口

    Returns:
        退出码（max(basic, position)）
    """
    basic_result = update_basic_cache(holdings, reporter)
    pos_result = update_position_cache(holdings, reporter)
    return max(basic_result.exit_code, pos_result.exit_code)


def warm_new_asset_caches(holdings: list, reporter) -> list[str]:
    """持仓变更预热：检测新增资产并预取行情 / 基金业绩与持仓 / 行业分类。

    变更检测委托 ``cache.check_and_refresh_caches``；预取编排属缓存域业务，
    渠道层只负责进度呈现。全程异常不阻断后续生成。

    Args:
        holdings: 持仓列表
        reporter: 进度报告接口（info/ok/warn）

    Returns:
        预热涉及的新增代码列表（无新增时为空表；异常中断时为已处理部分）
    """
    from src.python.cache import check_and_refresh_caches
    from src.python.fetcher.fund import fetch_fund_holdings, fetch_fund_rankings
    from src.python.fetcher.industry import batch_fetch_industry_data
    from src.python.fetcher.price import fetch_market_data
    from src.python.report.fund_performance import is_fund

    new_codes: list[str] = []
    try:
        new_codes = check_and_refresh_caches(holdings)
        if not new_codes:
            return []

        code_map = {h.code: h for h in holdings}
        reporter.info(f"检测到 {len(new_codes)} 个新增资产，正在预热缓存...")
        for code in new_codes:
            h = code_map.get(code)
            name = h.name if h else code
            reporter.info(f"新增 {name} ({code}) — 获取行情...")
            result = fetch_market_data(code, name)
            if result and result.get("price", 0) > 0:
                reporter.ok(f"行情 {name} {result['price']:.4f}")
            else:
                reporter.warn(f"行情 {name} 获取失败")
            if h and is_fund(h):
                perf = fetch_fund_rankings(code)
                if perf:
                    reporter.ok(f"业绩排名 {name}")
                else:
                    reporter.warn(f"业绩排名 {name} 获取失败")
                holds = fetch_fund_holdings(code)
                if holds and holds.get("holdings"):
                    reporter.ok(f"持仓明细 {name} {len(holds['holdings'])} 条")
                else:
                    reporter.warn(f"持仓明细 {name} 无数据")
            reporter.info(f"新增 {name} ({code}) — 获取行业分类...")
            ind_map = batch_fetch_industry_data([code])
            if ind_map and code in ind_map:
                ind_name = ind_map[code].get("industry") or "未知"
                reporter.ok(f"行业 {name} {ind_name}")
            else:
                reporter.warn(f"行业 {name} 无数据")
        reporter.ok("新增资产缓存预热完成")
    except Exception:
        logger.warning("新资产预热过程异常，跳过（不影响后续生成）", exc_info=True)
    return new_codes


def get_cache_stats_payload() -> dict:
    """缓存统计的结构化载荷（GET /api/cache 单源组装，前端契约不变）。

    by_prefix 以 [前缀, 数量] 数组按文件数降序下发——Flask JSON 默认
    sort_keys 会重排 dict 键序，只有数组能保序；top_by_size 截断前 5
    （防长尾撑乱前端卡片）；过期数为 cleanup_expired(dry_run=True) 预估。
    """
    from src.python.cache import cleanup_expired, get_cache_hit_rate, get_cache_stats

    raw = get_cache_stats()
    by_prefix: dict = raw.get("by_prefix", {}) or {}
    prefixes = sorted(by_prefix.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "total_files": raw.get("total_files", 0),
        "total_size_bytes": raw.get("total_size_bytes", 0),
        "by_prefix": [[k, v] for k, v in prefixes],
        "top_by_size": raw.get("top_by_size", [])[:5],
        "hit_rate": get_cache_hit_rate(),
        "expired_count": cleanup_expired(dry_run=True),
    }
