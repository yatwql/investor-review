"""报告管线全量量化指标子模块 — 历史走势 + 指标 + 情景分析 + 口径修正。

承载 full 路径的风险指标装配流程：历史走势获取 → 危机区间标注 / 尾部风险注入
→ 全量指标计算 → 情景分析 → 口径修正，返回 (history_data, metrics)
并就地注入 prep/pipeline_data。

由 `_report_generation.py`（聚合门面）re-export 对外提供。
"""

from __future__ import annotations

import logging

from typing import Any

from src.python.report.progress import ProgressReporter

logger = logging.getLogger("invest")


# ── 全量量化指标（历史走势 + 风险指标 + 情景分析 + 口径修正）──


def _prepare_full_risk_metrics(
    holdings: list,
    config: dict,
    reporter: ProgressReporter,
    perf: Any,
    fetch_history: bool,
    enable_history: bool,
    prep: dict,
    pipeline_data: dict | None,
) -> tuple[dict | None, dict | None]:
    """历史走势获取 + 全量量化指标 + 情景分析 + 口径修正。

    返回 (history_data, metrics)，就地注入 prep 和 pipeline_data 的 risk_metrics。
    enable_history 为 False 或数据不可用时返回 (None, None)。
    """
    from src.python.analysis.alignment_correction import compute_alignment_factors
    from src.python.analysis.metrics import compute_all_metrics
    from src.python.analysis.scenario import scenario_analysis
    from src.python.report._snapshot import fetch_history_data, latest_quotes_from_detail_rows

    if not enable_history:
        reporter.info("[章节配置] 历史走势已关闭，跳过")
        return None, None

    perf.start("历史走势")
    # 明细行（with_market_fields=True）带 price / nav_date：作终点回填的最新估值来源
    _latest_quotes = latest_quotes_from_detail_rows(prep.get("holdings_details"))
    history_data = fetch_history_data(holdings, config, reporter, fetch=fetch_history, latest_quotes=_latest_quotes)
    perf.stop()

    # 历史增强契约装配（危机区间标注[含回放态] + 风险调整超额）：full/both 两路径
    # 共用 _snapshot.assemble_history_augmented_data 唯一实现（开关判定与子块长窗
    # 取数集中；开关全关时仅写 crisis 关态契约，零新增取数）
    if pipeline_data is not None:
        from src.python.report._snapshot import assemble_history_augmented_data

        assemble_history_augmented_data(
            holdings, config, reporter, history_data, pipeline_data, latest_quotes=_latest_quotes
        )

        # 尾部风险统计（tail_risk_data）：复用历史日收益序列计算 VaR/最大单日跌幅/
        # 连续下跌/恢复天数；样本不足时 available=False（§1.4.5 数据降级）
        from src.python.analysis.tail_risk import compute_tail_risk

        pipeline_data["tail_risk_data"] = compute_tail_risk((history_data or {}).get("bars"))

    # 从 history_data 提取风险指标，注入 prep 和 pipeline_data
    if history_data and history_data.get("status") not in ("unavailable",):
        _risk = {
            "annualized_volatility": history_data.get("annualized_volatility", 0),
            "max_drawdown_pct": history_data.get("max_drawdown_pct", 0),
            "total_return_pct": history_data.get("total_return_pct", 0),
            "data_start": history_data.get("data_start", ""),
            "data_end": history_data.get("data_end", ""),
        }
        prep["risk_metrics"] = _risk
        if pipeline_data is not None:
            pipeline_data["risk_metrics"] = _risk

    # [checkpoint] risk_metrics 完整性校验
    _injected = prep.get("risk_metrics", {})
    if not _injected.get("annualized_volatility") and _injected.get("annualized_volatility") != 0:
        logger.warning("[checkpoint] prep.risk_metrics 缺 annualized_volatility")

    # ── 全量量化指标 + 情景分析 + 口径修正 ──
    _daily_returns = history_data.get("daily_returns_portfolio", []) if history_data else None
    if _daily_returns:
        _holdings_details = prep.get("holdings_details", [])
        _total_mv = prep.get("total_mv", 0)

        _portfolio_weights = [
            h["market_value"] / _total_mv for h in _holdings_details if _total_mv > 0 and h.get("market_value", 0) > 0
        ] or None

        _metrics = compute_all_metrics(
            portfolio_daily_returns=_daily_returns,
            portfolio_weights=_portfolio_weights,
            benchmark_daily_returns=None,
            holdings_details=_holdings_details,
            rf_annual=0.02,
        )

        _mdd_pct = (history_data or {}).get("max_drawdown_pct", 0)
        _metrics["annualized_volatility"] = (history_data or {}).get("annualized_volatility")
        _metrics["max_drawdown"] = -(_mdd_pct / 100) if _mdd_pct else None

        _alignment = compute_alignment_factors(
            holdings_details=_holdings_details,
            total_mv=_total_mv,
            portfolio_daily_returns=_daily_returns,
        )
        if _alignment.get("has_any_data"):
            _metrics["alignment_summary"] = _alignment.get("summary_text", "")

        _beta_analysis = _metrics.get("beta_analysis")
        _beta_val = _metrics.get("portfolio_beta")
        if isinstance(_beta_analysis, dict) and _beta_val is not None:
            _scenario = scenario_analysis(
                portfolio_value=_total_mv,
                beta=_beta_val,
                beta_ci_lower=_beta_analysis.get("ci_lower"),
                beta_ci_upper=_beta_analysis.get("ci_upper"),
                beta_se=_beta_analysis.get("std_error"),
            )
            if _scenario.get("has_data") and _scenario.get("scenarios"):
                _metrics["scenario_analysis"] = _scenario
    else:
        _metrics = None

    return history_data, _metrics
