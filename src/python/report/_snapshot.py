"""快照与历史数据 — 持仓快照创建/环比差异计算/组合历史走势。

管理快照对比和历史走势两个工序。
"""

from __future__ import annotations


from src.python.report.progress import ProgressReporter

logger = __import__("logging").getLogger("invest")


def _baseline_labels(ts: str) -> tuple[str, str]:
    """基线快照时间戳 →（所属交易日, 生成时间）展示串。

    供 ``diff.baseline_trading_day`` / ``diff.baseline_generated_at`` 派生——
    环比时标注“比对的是哪个交易日、什么时间生成的报告”。交易日归属与报告头
    “所属交易日”同口径（``trading_day_as_of``）。时间戳不可解析时返回 ("", "")，
    展示层按缺席降级（不写标注行）。
    """
    from src.python.core.trading_calendar import trading_day_as_of
    from src.python.report.history_snapshot import _parse_snapshot_timestamp

    dt = _parse_snapshot_timestamp(ts or "")
    if dt is None:
        return "", ""
    return trading_day_as_of(dt), dt.strftime("%Y-%m-%d %H:%M")


def _classify_qdii_value_diff(details: list, old) -> tuple[float, bool]:
    """环比中 QDII 官方净值变动的金额与是否滞后口径（T-1）。

    QDII 官方净值天然滞后一个交易日：本次快照用的是 T-1 净值、基线快照用的是
    更早一期净值，故其市值差实际反映的是**上一交易日**的净值变动，与当日 A 股
    涨跌混在同一个「总市值环比」里。此处按 ``is_qdii_extended`` 与 HistoryDiff
    同口径（按 code 合并账户）算出该分项，供摘要区在环比下注明口径。

    滞后判定用明细行的净值日期是否早于最近交易日：当日已披露即非滞后（罕见，
    部分 QDII 会按时披露）；无 QDII 持仓时返回 (0.0, False)，渲染层省略该注。

    Args:
        details: 本次行情明细行（含 ``code`` / ``name`` / ``market_value`` / ``nav_date``）
        old: 基线快照（``SnapshotData``；None=首次运行）

    Returns:
        (QDII 市值差金额, 是否滞后口径)。
    """
    from src.python.core.code_utils import is_qdii_extended

    names: dict[str, str] = {d.code.strip(): getattr(d, "name", "") for d in details}
    new_by_code: dict[str, float] = {}
    for d in details:
        code = d.code.strip()
        new_by_code[code] = new_by_code.get(code, 0.0) + d.market_value
    old_by_code: dict[str, float] = {}
    if old is not None:
        for account in old.accounts:
            for h in account.holdings:
                code = h.code.strip()
                names.setdefault(code, h.name)
                old_by_code[code] = old_by_code.get(code, 0.0) + h.market_value

    qdii_codes = {code for code, name in names.items() if is_qdii_extended(name)}
    if not qdii_codes:
        return 0.0, False

    value_diff = sum(new_by_code.get(code, 0.0) - old_by_code.get(code, 0.0) for code in qdii_codes)

    from src.python.core.trading_calendar import get_last_trading_day

    trading_day = get_last_trading_day()
    lagged = any(
        getattr(d, "nav_date", "") and d.nav_date < trading_day for d in details if d.code.strip() in qdii_codes
    )
    return round(value_diff, 2), lagged


def capture_snapshot(
    holdings: list,
    details: list,
    config: dict | None,
    reporter: ProgressReporter,
    *,
    snapshot_namespace: str | None = None,
    **extra,
) -> dict | None:
    """持仓快照创建 + 差异计算 + 保存 + 清理。

    Args:
        holdings: 持仓列表
        details: 行情明细
        config: 配置字典
        reporter: 进度报告接口
        snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域），
            差异计算基于同域上一份**不同交易日**的快照（同一交易日多次运行跳过，
            见 ``load_comparison_baseline``）、保存与清理均在域内闭环
        extra: 额外扩展字段（调用方 kwargs），透传到 pipeline_data

    Returns:
        pipeline_data 字典（含 diff），首次运行或异常时返回 None。

    持仓源守卫：快照写入共享主目录（``snapshot_namespace=None``）前先经
    ``config.is_formal_holdings_source`` 校验，非正式源（demo/试算/临时持仓，
    路径不在 ``data/holdings/`` 下）直接返回 None——不落盘、不与真实历史对比，
    下游历史章（快照对比/组合演进/持仓变动复盘）随 pipeline_data 缺席同首次
    运行口径隐藏。命名空间域（如 web 试算域）域内闭环，不受守卫限制。
    """
    # ── 持仓源守卫（共享主目录）────────────────────────
    # 非正式持仓源不得写入/比对真实快照历史，否则幻影持仓会污染用户历史
    # （症状：未持有品种被报成清仓）；命名空间域天然隔离，不受此限制。
    if snapshot_namespace is None:
        from src.python.config import is_formal_holdings_source

        if not is_formal_holdings_source(config):
            logger.info("[快照] 非正式持仓源，跳过快照捕获与环比对比（不落盘、不与真实历史比对）")
            reporter.info(
                "持仓源不在正式持仓目录（data/holdings/）：本次不写入持仓快照历史，"
                "快照对比/组合演进/持仓变动复盘章不出现（demo/临时持仓防污染）"
            )
            return None

    from src.python.fetcher.history_diff import HistoryDiff
    from src.python.report.data_status import get_tracker as _get_degradation_tracker
    from src.python.report.history_snapshot import load_comparison_baseline, save
    from src.python.schemas.history import (
        AccountSnapshot,
        SnapshotData,
        SnapshotHolding,
    )

    pipeline_data: dict | None = None
    try:
        _snapshot_holdings = [
            SnapshotHolding(
                code=d.code,
                name=getattr(d, "name", ""),
                shares=0.0,
                cost_price=0.0,
                market_value=d.market_value,
                total_pnl=d.profit,
                cost_total=d.cost,
            )
            for d in details
        ]
        for h in _snapshot_holdings:
            _orig = next((x for x in holdings if x.code == h.code), None)
            if _orig:
                object.__setattr__(h, "shares", _orig.shares)
                object.__setattr__(h, "cost_price", _orig.cost_price)
        from datetime import datetime

        _snapshot = SnapshotData(
            accounts=(AccountSnapshot(account_name="全部", holdings=tuple(_snapshot_holdings)),),
            total_value=sum(d.market_value for d in details),
            total_cost=sum(d.cost for d in details),
            total_pnl=sum(d.profit for d in details),
            timestamp=datetime.now().strftime("%Y%m%dT%H%M%S"),
        )
        _old = load_comparison_baseline(_snapshot.timestamp, snapshot_namespace)
        _diff = HistoryDiff.compute(_snapshot, _old)
        save(_snapshot, snapshot_namespace)
        from src.python.core.constants import HISTORY_SNAPSHOT_MAX_COUNT, HISTORY_SNAPSHOT_RETENTION_DAYS
        from src.python.report.history_snapshot import prune as _prune_snapshots

        _history_cfg = (config or {}).get("history", {})
        _prune_snapshots(
            retention_days=_history_cfg.get("snapshot_retention_days", HISTORY_SNAPSHOT_RETENTION_DAYS),
            max_count=_history_cfg.get("snapshot_max_count", HISTORY_SNAPSHOT_MAX_COUNT),
            namespace=snapshot_namespace,
        )
        if not _diff.is_first_check:
            # 基线时间戳仅接受字符串（防御非标对象/桩），不可解析时标签降级为 ""
            _raw_ts = _old.timestamp if isinstance(_old.timestamp, str) else ""
            _baseline_td, _baseline_gen = _baseline_labels(_raw_ts)
            # 首次运行无基线：QDII 分项无意义，计算只在有环比时进行
            _qdii_value_diff, _qdii_lagged = _classify_qdii_value_diff(details, _old)
            pipeline_data = {
                "diff": {
                    "is_first_check": False,
                    "total_value_diff": _diff.total_value_diff,
                    "total_value_diff_pct": _diff.total_value_diff_pct,
                    "qdii_value_diff": _qdii_value_diff,
                    "qdii_lagged": _qdii_lagged,
                    "total_pnl_diff": _diff.total_pnl_diff,
                    "total_pnl_pct_diff": _diff.total_pnl_pct_diff,
                    "days_since_last_report": _diff.days_since_last_report,
                    "baseline_timestamp": _raw_ts,
                    "baseline_generated_at": _baseline_gen,
                    "baseline_trading_day": _baseline_td,
                    "added": [
                        {
                            "name": a.name,
                            "code": a.code,
                            "action": a.action,
                            "shares_diff": a.shares_diff,
                            "value_diff": a.value_diff,
                        }
                        for a in _diff.added
                    ],
                    "removed": [
                        {
                            "name": r.name,
                            "code": r.code,
                            "action": r.action,
                            "shares_diff": r.shares_diff,
                            "value_diff": r.value_diff,
                        }
                        for r in _diff.removed
                    ],
                    "increased": [
                        {
                            "name": i.name,
                            "code": i.code,
                            "action": i.action,
                            "shares_diff": i.shares_diff,
                            "value_diff": i.value_diff,
                        }
                        for i in _diff.increased
                    ],
                    "decreased": [
                        {
                            "name": d.name,
                            "code": d.code,
                            "action": d.action,
                            "shares_diff": d.shares_diff,
                            "value_diff": d.value_diff,
                        }
                        for d in _diff.decreased
                    ],
                },
                "data_degradation": _get_degradation_tracker().get_log(),
            }
            # 透传额外扩展字段（调用方 kwargs，如测试注入 risk_metrics）
            if extra:
                pipeline_data.update(extra)
        reporter.ok("环比对比数据准备完成")
    except Exception:
        logger.info("[环比] 数据准备跳过（首次运行或异常）", exc_info=True)
    return pipeline_data


def fetch_history_data(
    holdings: list,
    config: dict | None,
    reporter: ProgressReporter,
    fetch: bool = True,
) -> dict | None:
    """获取组合历史走势数据（as-if 模拟），纯业务逻辑，不含用户交互。

    Args:
        holdings: 持仓列表
        config: 配置字典（含 history 子段）
        reporter: 进度报告接口
        fetch: 是否执行获取，False 直接返回 None

    Returns:
        history_data 字典，获取失败或不可用时返回 None。
    """
    if not fetch:
        # 醒目警示：history 关闭时不得静默跳过，否则下游只剩误导性的
        # "尾部风险：无历史 bars" 占位警告，用户无法判断原因
        logger.warning(
            "组合历史走势获取已跳过（history off）：历史走势/回撤、尾部风险、累计收益率等章节将显示“数据不可用”占位"
        )
        reporter.warn(
            "组合历史走势获取已跳过（history off）：历史走势/回撤章节与尾部风险指标将显示“数据不可用”占位；"
            "如需完整历史分析请开启 history（CLI 使用 --history auto）"
        )
        return None

    reporter.info("正在获取组合历史走势数据（as-if 模拟）...")
    from src.python.report.portfolio_history import PortfolioHistoryCalculator

    _history_cfg = (config or {}).get("history", {})

    try:
        _coverage = _history_cfg.get("coverage_threshold", 0.8)
        _benchmark_indices = _history_cfg.get("benchmark_indices", {})
        # 取数窗口：默认 90（≥ drawdown MIN_SPAN 60 个交易日），保证回撤分析可用
        _lookback_days = _history_cfg.get("lookback_days", 90)
        _calc = PortfolioHistoryCalculator(
            coverage_threshold=_coverage,
            benchmark_indices=_benchmark_indices,
        )
        _holdings_tuples = [(h.code, h.name, h.shares) for h in holdings]
        history_data = _calc.get_combined_timeseries(_holdings_tuples, days=_lookback_days)
        if history_data and history_data.get("status") != "unavailable":
            reporter.ok("组合历史走势数据获取完成")
        else:
            reporter.warn("组合历史走势数据获取失败（部分持仓可能不支持历史数据）")
        return history_data
    except Exception:
        logger.info("[历史走势] 数据获取跳过", exc_info=True)
        return None


# ── 子块独立长窗与危机回放指数层取数（风险调整超额 / 危机回放开关专用） ──────

_EXTENDED_HISTORY_DAYS = 365
"""风险调整超额/危机回放子块的长窗下限（交易日）——A 股历史 K 线单次可得上限 365。"""

_CRISIS_INDEX_DAYS_MAX = 3650
"""危机回放指数日线取数上限（fetch_index_history 源上限 3650）。"""


def _crisis_index_days() -> int:
    """危机回放指数层所需交易日数——按静态危机表最早区间起点动态推算。

    自然日跨度 × 252/365 + 60 交易日缓冲，封顶源上限 3650；未来静态表
    增补更早区间时自动延长取数窗口，无需手工调参。
    """
    from datetime import date as _date

    from src.python.analysis.crisis_annotation import CRISIS_INTERVALS

    try:
        earliest = min(_date.fromisoformat(iv["start"]) for iv in CRISIS_INTERVALS)
    except (KeyError, TypeError, ValueError):
        return _CRISIS_INDEX_DAYS_MAX
    span = (_date.today() - earliest).days
    return max(0, min(_CRISIS_INDEX_DAYS_MAX, int(span * 252 / 365) + 60))


def fetch_extended_history(
    holdings: list,
    config: dict | None,
    reporter: ProgressReporter,
) -> dict | None:
    """获取子块独立长窗历史（as-if），供风险调整超额/危机回放计算。

    与主走势窗口（``history.lookback_days``）解耦：主窗不动，子块自取
    ``max(lookback_days, 365)`` 窗口。取数走与主历史同一条 chain 与文件缓存
    （``history_*`` CACHE_WEEKLY），首次全量补齐、其后命中，网络成本受控；
    两开关（风险调整超额/危机回放）共享同一次取数。开关关闭时本函数不会
    被编排层调用（关态零新增请求）。

    Args:
        holdings: 持仓列表（code/name/shares 属性）
        config: 配置字典（含 history 子段）
        reporter: 进度报告接口

    Returns:
        history_data 契约 dict；不可用/异常返回 None（子块落 §1.4.5 降级）。
    """
    if not holdings:
        return None
    _cfg = (config or {}).get("history", {}) or {}
    if not isinstance(_cfg, dict):
        _cfg = {}
    try:
        _days = max(int(_cfg.get("lookback_days", 90) or 90), _EXTENDED_HISTORY_DAYS)
    except (TypeError, ValueError):
        _days = _EXTENDED_HISTORY_DAYS
    try:
        reporter.info("正在获取子块长窗历史（风险调整超额/危机回放）...")
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        _calc = PortfolioHistoryCalculator(
            coverage_threshold=_cfg.get("coverage_threshold", 0.8),
            benchmark_indices=_cfg.get("benchmark_indices", {}) or {},
        )
        _tuples = [(h.code, h.name, h.shares) for h in holdings]
        data = _calc.get_combined_timeseries(_tuples, days=_days)
        if data and data.get("status") != "unavailable":
            reporter.ok("子块长窗历史获取完成")
            return data
        reporter.warn("子块长窗历史获取失败，相关子块将显示数据不足占位")
        return None
    except Exception:
        logger.info("[子块长窗] 历史获取跳过", exc_info=True)
        return None


def fetch_crisis_index_series(config: dict | None) -> dict | None:
    """危机回放指数层：主基准指数长窗日线（覆盖全部预设危机区间）。

    只取 ``benchmark_indices`` 的第一个代码（回放表单指数列）；未配置基准
    或获取失败返回 None（契约标未配置/指数层不可用，组合层不受影响）。

    Args:
        config: 配置字典（含 history.benchmark_indices）

    Returns:
        ``{"name": str, "bars": [{"date", "close"}, ...]}`` 或 None。
    """
    _cfg = (config or {}).get("history", {}) or {}
    if not isinstance(_cfg, dict):
        return None
    indices = _cfg.get("benchmark_indices") or {}
    if not isinstance(indices, dict) or not indices:
        return None
    code = next(iter(indices))
    try:
        from src.python.report.benchmark import fetch_benchmarks

        raw = fetch_benchmarks({code: indices[code]}, days=_crisis_index_days())
        if raw and (raw.get(code) or {}).get("bars"):
            return raw[code]
        return None
    except Exception:
        logger.info("[危机回放] 指数长窗获取跳过", exc_info=True)
        return None


def assemble_history_augmented_data(
    holdings: list,
    config: dict | None,
    reporter: ProgressReporter,
    history_data: dict | None,
    pipeline_data: dict | None,
) -> None:
    """装配历史增强契约：危机区间标注（含回放态）+ 风险调整超额。

    full（``_prepare_full_risk_metrics``）与 both（``_generate_report_both``）
    两条报告路径的唯一装配实现——开关判定、子块长窗取数、指数层取数与契约
    构建集中于此，避免双路径行为漂移。

    行为：
    - ``pipeline_data`` 为 None 时跳过（与历史行为一致）。
    - 开关全关（默认）：仅写 crisis 关态契约（基于既有 bars，零新增取数），
      ``risk_adjusted_excess_data`` 键不写入——关态产物逐字节不变。
    - 任一开关开启：子块自取长窗历史（主走势窗口 ``history.lookback_days``
      不动），两开关共享同一次取数；回放态另取主基准指数长窗日线。

    Args:
        holdings: 持仓列表（code/name/shares 属性）
        config: 配置字典（含 history 子段）
        reporter: 进度报告接口
        history_data: 主窗口历史走势契约（可为 None）
        pipeline_data: 管线数据字典（就地写入 crisis_annotation_data /
            risk_adjusted_excess_data）；None 时直接返回
    """
    if pipeline_data is None:
        return
    from src.python.analysis.crisis_annotation import build_crisis_annotation
    from src.python.config.features import is_feature_enabled

    crisis_replay_on = is_feature_enabled("crisis_replay")
    excess_on = is_feature_enabled("risk_adjusted_excess")

    extended_history = None
    if (crisis_replay_on or excess_on) and history_data and history_data.get("status") != "unavailable":
        extended_history = fetch_extended_history(holdings, config, reporter)

    if crisis_replay_on:
        pipeline_data["crisis_annotation_data"] = build_crisis_annotation(
            extended_history or history_data,
            replay=True,
            index_series=fetch_crisis_index_series(config),
        )
    else:
        pipeline_data["crisis_annotation_data"] = build_crisis_annotation(history_data)

    if excess_on:
        from src.python.analysis.benchmark_excess import build_risk_adjusted_excess

        pipeline_data["risk_adjusted_excess_data"] = build_risk_adjusted_excess(extended_history or history_data)
