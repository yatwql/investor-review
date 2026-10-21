"""full 路径：HTML+Excel+LLM 生成编排（含实验挂载点与 LLM 章节装配）。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


from src.python.report._experimental_seams import (
    apply_module_quality_banners,
    inject_holding_change_data,
    inject_schedule_replay_data,
    record_deterministic_decisions,
    record_deterministic_signals,
    record_llm_decisions_and_review_block,
    record_prosperity_diagnosis,
)

if TYPE_CHECKING:  # ReportResult 定义在编排门面，运行期从生成入口传入（避免循环导入）
    from src.python.report.orchestrator import ReportResult
from src.python.core.decision_header import strip_structured_header
from src.python.report.progress import ProgressReporter
from src.python.report._report_output import (  # noqa: F401  # 产物落盘子模块（消费方在本门面，patch 点不变）
    _generate_full_excel_report,
    _generate_full_html_report,
)

# ── 子模块 re-export ────────────────────────────────────
from src.python.report._chart_dataset_factory import _build_chart_datasets_for_report  # noqa: F401
from src.python.report._full_risk_metrics import _prepare_full_risk_metrics  # noqa: F401
from src.python.report._report_health import _collect_health_checks, _spawn_health_checks  # noqa: F401
from src.python.report.run_integrity import bind_health, bind_perf
from src.python.report._generation_shared import _record_llm_context
from src.python.report._report_helpers import (  # noqa: F401
    _action_holdings_details,
    _compute_details,
    _inject_evolution_data,
    _inject_snapshot_diff_data,
    _validate_pipeline_snapshot,
    _validate_prep_completeness,
)

logger = logging.getLogger("invest")


def _generate_report_full(
    holdings: list,
    config: dict,
    reporter: ProgressReporter,
    fetch_history: bool = False,
    force_llm: bool = False,
    force_llm_modules: list[str] | None = None,
    output_dir: str | None = None,
    transactions: list | None = None,
    dividends: list | None = None,
    *,
    snapshot_namespace: str | None = None,
) -> "ReportResult":
    """full 报告路径：生成 HTML + Excel + LLM 分析章节。

    流程：prepare_report_data() → capture_snapshot() → _prepare_full_risk_metrics()
          → get_sector_fund_flow() → _fetch_llm_and_news()
          → write_html_report() → generate_excel_report()

    Args:
        snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域）。
            快照对比/组合演进/快照差异均在本域内闭环，不污染共享时间线。
    """
    from src.python.config import (
        is_enable_action,
        is_enable_cost_lots,
        is_enable_data_quality,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_llm,
        is_enable_news,
        is_enable_portfolio_evolution,
        is_enable_stock_fundamentals,
    )
    from src.python.fetcher.akshare import get_sector_fund_flow
    from src.python.core.perf import PerfCollector
    from src.python.core.registry import get_report_section_order
    from src.python.report._llm_news import _fetch_llm_and_news
    from src.python.report._snapshot import capture_snapshot
    from src.python.report.orchestrator import ReportResult, prepare_report_data

    perf = PerfCollector(report_type="full", holdings=holdings, stage_announcer=reporter.stage_progress)
    bind_perf(perf)
    result = ReportResult()
    result.holdings_ok = True
    _health_fut = _spawn_health_checks()
    bind_health(_health_fut, "full", holdings)

    _enable_fund_deep_analysis = is_enable_fund_deep_analysis(config)
    _enable_news = is_enable_news(config)
    _enable_history = is_enable_history(config)
    _enable_portfolio_evolution = is_enable_portfolio_evolution(config)
    _enable_action = is_enable_action(config)
    _enable_llm = is_enable_llm(config)
    _enable_data_quality = is_enable_data_quality(config)
    _enable_cost_lots = is_enable_cost_lots(config)
    _enable_stock_fundamentals = is_enable_stock_fundamentals(config)
    from src.python.config.features import is_feature_enabled

    _enable_summary_highlights = is_feature_enabled("summary_highlights")
    sec_order = get_report_section_order(config)

    # ── 1. 完整数据准备（含指数/穿透/分类） ──
    perf.start("数据准备")
    prep = prepare_report_data(holdings, reporter, config, transactions=transactions)
    _validate_prep_completeness(prep)
    perf.stop()

    # ── 2. 快照对比 ──
    perf.start("快照对比")
    pipeline_data = capture_snapshot(
        holdings,
        prep["details"],
        config,
        reporter,
        snapshot_namespace=snapshot_namespace,
    )
    # 风格与因子 / 持仓关系矩阵 / 品种覆盖诊断：prep 中已组装（数据契约），
    # 注入 pipeline_data 供 HTML/Excel 消费；capture_snapshot 在降级路径可能返回 None，需判空
    if pipeline_data is not None:
        pipeline_data["style_factor_data"] = prep.get("style_factor_data")
        pipeline_data["factor_catalog_data"] = prep.get("factor_catalog_data")
        pipeline_data["position_relationship_data"] = prep.get("position_relationship_data")
        pipeline_data["position_status"] = prep.get("position_status")
        pipeline_data["data_freshness"] = prep.get("data_freshness")
        pipeline_data["action_data"] = prep.get("action_data")
        # 估值分位 + 市场温度（数据契约，prep 中已组装；开关关闭时为 None）
        pipeline_data["valuation_data"] = prep.get("valuation_data")
        pipeline_data["market_temperature_data"] = prep.get("market_temperature_data")
        # 持仓个股财报摘要（数据契约，prep 中已组装；开关关闭/无 key 时为 None）
        pipeline_data["financial_report_digest_data"] = prep.get("financial_report_digest_data")
        # 财务指标（数据契约，prep 中已组装；开关关闭时为 None）
        pipeline_data["financial_indicator_data"] = prep.get("financial_indicator_data")
        # 申购限购状态（数据契约，prep 中已组装；开关关闭时为 None、
        # 全链失败时 available=False——渲染层据此静默隐列）
        pipeline_data["purchase_status_data"] = prep.get("purchase_status_data")
    _validate_pipeline_snapshot(pipeline_data)
    # 2b. 组合演进数据（聚合多期快照，evolution_data；开关关闭时跳过计算）
    if _enable_portfolio_evolution:
        pipeline_data = _inject_evolution_data(pipeline_data, snapshot_namespace=snapshot_namespace)
        # 2b1. 快照差异摘要（snapshot_diff_data）：组合演进章顶部变化摘要，
        #      与演进数据同开关（同属组合演进章节）
        pipeline_data = _inject_snapshot_diff_data(pipeline_data, snapshot_namespace=snapshot_namespace)
    # 2b2. 持仓变动复盘（报告章节与增强开关 holding_change_review，默认关；独立于演进开关）：
    #      事件清单差分须晚于本次快照捕获；开关关闭时键缺席 → 整章隐藏（见 seams）
    inject_holding_change_data(pipeline_data, config, reporter, snapshot_namespace=snapshot_namespace)
    # 2b3. 调仓纪律回放（实验开关 rebalance_schedule_replay，默认关）：多期规则回放
    #     装配（持仓 + 历史净值 + 成本两态）；开关关闭时键缺席 → 整章隐藏（见 seams）
    inject_schedule_replay_data(pipeline_data, reporter, holdings=holdings)
    # 2b4. 摘要区本期要点与环比对照（报告章节与增强开关 summary_highlights，默认关）：
    #      快照 diff 单源纯内存派生；无上期快照时键值为 None → 首屏整块隐藏
    if _enable_summary_highlights and pipeline_data is not None:
        from src.python.report.summary_highlights import build_summary_highlights

        pipeline_data["summary_highlights_data"] = build_summary_highlights(pipeline_data)
    perf.stop()

    # ── 3. 历史走势 + 全量量化指标 ──
    history_data, _metrics = _prepare_full_risk_metrics(
        holdings,
        config,
        reporter,
        perf,
        fetch_history,
        _enable_history,
        prep,
        pipeline_data,
    )

    # 3.5 行动建议回填（历史走势就绪后注入组合历史峰值市值，激活回撤纪律）。
    # prepare_report_data 的 action_data 为「中间占位构建」（persist_silence=False，
    # 不读写静默文件）：彼时历史时序未就绪、峰值未知。此处用 history_data.bars
    # 计算组合历史峰值并重建 action_data（默认 persist_silence=True），作为管线
    # 中纪律静默的唯一写入方——同时保证单品信号不被占位构建抢占静默而误抑制。
    from src.python.analysis.action_advisor import build_action_data
    from src.python.analysis.metrics import compute_portfolio_peak_mv

    _peak_mv = compute_portfolio_peak_mv((history_data or {}).get("bars"))
    _action_data = build_action_data(
        prep.get("holdings_details") or [],
        prep.get("total_mv", 0),
        portfolio_peak_mv=_peak_mv,
    )
    prep["action_data"] = _action_data
    if pipeline_data is not None:
        pipeline_data["action_data"] = _action_data

    # ── 3.6 决策跨期反思闭环（decision_reflection 实验功能，默认关）──
    # 结算必须先于 LLM 拉取：否则当次教训（含本批结算结果）在 LLM 注入前未落档，
    # 注入读不到新结算。挂载点实现与异常守护见 `_experimental_seams`。
    record_deterministic_decisions(prep, _action_data, reporter)

    # ── 4. 行业资金流向 ──
    reporter.info("正在获取行业资金流向...")
    perf.start("行业资金流向")
    try:
        sector_flow = get_sector_fund_flow()
        if sector_flow:
            reporter.ok("行业资金流向获取完成")
    except Exception:
        sector_flow = None
        reporter.warn("行业资金流向获取失败，将继续生成报告")
    perf.stop()

    # ── 5. 并行获取 LLM + 新闻 ──
    _comparison_indices = config.get("comparison_indices", None)
    perf.start("LLM+新闻")
    from src.python.llm.observation import LlmObservation, bind_llm_observation

    _llm_sink = LlmObservation()
    bind_llm_observation(_llm_sink)
    try:
        llm_content, news_data, news_llm_meta, news_ok, debate_info = _fetch_llm_and_news(
            holdings,
            prep,
            sector_flow,
            force_llm,
            pipeline_data,
            _enable_news,
            _enable_llm,
            reporter,
            force_llm_modules=force_llm_modules,
            history_data=history_data,
            comparison_indices=_comparison_indices,
            metrics=_metrics,
            span_recorder=perf.recorder("LLM+新闻"),
        )
    finally:
        bind_llm_observation(None)
    if _enable_llm:
        from src.python.llm.fallback import build_fallback_llm_content

        llm_content = build_fallback_llm_content(llm_content)

    # ── 5b. 决策跨期反思闭环（LLM 载体登记 + 复盘区块装配）──
    # ③ 登记 LLM 操作建议 ④ 复盘区块数据契约注入 pipeline_data（HTML/Excel 行动章
    # 内嵌块消费）。挂载点实现与异常守护见 `_experimental_seams`。
    record_llm_decisions_and_review_block(prep, llm_content, _enable_llm, pipeline_data, reporter)

    # ── 5b'. 结构化决策头渲染剥离 ──
    # 决策头是给上方登记解析的机器载荷（单行 JSON，用户不可读）；登记完成后从
    # 四元组整体剥离——HTML/Excel 双端写出共用本元组，单点剥离即双端干净；
    # 缓存保留原始内容不回写（登记与剥离每次运行重新执行）。
    if llm_content:
        llm_content = tuple(strip_structured_header(_item) for _item in llm_content)

    # ── 5c. 模块级质量分级（实验开关，默认关闭）──
    # 只标注不阻断、不重试、不写回缓存。置于决策登记之后：横幅会改变内容文本，
    # 须避开操作建议表的解析。
    llm_content = apply_module_quality_banners(llm_content, reporter)

    # ── 5d. 确定性数值信号沉淀（实验开关，默认关闭）──
    # 置于此处而非 3.6：尾部风险等 A 通道键在 LLM 生成阶段才注入 pipeline_data，
    # 过早登记会漏采；适配器对缺失键逐项跳过，故不构成硬依赖。
    record_deterministic_signals(pipeline_data, prep, reporter)
    perf.stop()

    # 景气度框架诊断（实验性功能 prosperity_framework）：经实验挂载点接入。
    # full 路径 prep 已含穿透重仓（`penetrated_assets`），基本面与历史走势亦已就绪。
    record_prosperity_diagnosis(
        holdings,
        prep["details"],
        prep,
        config,
        reporter,
        financial_indicator_data=(pipeline_data or {}).get("financial_indicator_data")
        or prep.get("financial_indicator_data"),
        history_data=history_data,
        pipeline_data=pipeline_data,
    )

    # 市场情绪与持仓热点（报告增强开关 market_sentiment）：开关关闭返回 None（零行为变化）。
    # 须在写 HTML 之前取数——本契约既是行动建议章内嵌区块的数据源，也是「数据源可用性矩阵」
    # 「市场情绪」行与说明表「本次使用」的登记时机（mark_data_used/mark_provider_used 在此
    # 链路内触发）；置于 HTML 之后会让两端产物口径不一致。
    from src.python.report._report_aux_metrics import compute_market_sentiment_data

    _ms_data = compute_market_sentiment_data(holdings, prep, config, reporter)
    if _ms_data is not None and pipeline_data is not None:
        pipeline_data["market_sentiment_data"] = _ms_data

    # ── 6. HTML 报告 ──
    # 成本流水数据（fund_flow_data）：复用 excel_market_data 组装逻辑，
    # 开关关闭返回 None（HTML 模板保持既有输出）。
    from src.python.report.excel_market_data import _build_flow_data

    fund_flow_data = _build_flow_data(_enable_cost_lots, transactions, dividends, holdings, prep["details"])
    result.html_ok = _generate_full_html_report(
        holdings,
        prep,
        output_dir,
        sec_order,
        llm_content,
        news_data,
        news_llm_meta,
        news_ok,
        history_data,
        reporter,
        _enable_fund_deep_analysis,
        _enable_news,
        _enable_history,
        _enable_llm,
        debate_info,
        result,
        _metrics,
        prep.get("style_factor_data"),
        prep.get("factor_catalog_data"),
        prep.get("position_relationship_data"),
        (pipeline_data or {}).get("evolution_data"),
        _enable_portfolio_evolution,
        _enable_action,
        _enable_data_quality,
        (pipeline_data or {}).get("position_status"),
        (pipeline_data or {}).get("data_freshness"),
        (pipeline_data or {}).get("action_data"),
        (pipeline_data or {}).get("crisis_annotation_data"),
        (pipeline_data or {}).get("tail_risk_data"),
        (pipeline_data or {}).get("snapshot_diff_data"),
        fund_flow_data,
        (pipeline_data or {}).get("valuation_data"),
        (pipeline_data or {}).get("market_temperature_data"),
        (pipeline_data or {}).get("decision_review_data"),
        prosperity_framework_data=(pipeline_data or {}).get("prosperity_framework_data"),
        enable_fundamental_snapshot=_enable_stock_fundamentals,
        financial_report_digest_data=(pipeline_data or {}).get("financial_report_digest_data"),
        financial_indicator_data=(pipeline_data or {}).get("financial_indicator_data"),
        purchase_status_data=(pipeline_data or {}).get("purchase_status_data"),
        market_sentiment_data=(pipeline_data or {}).get("market_sentiment_data"),
        holding_change_data=(pipeline_data or {}).get("holding_change_data"),
        event_impact_data=(pipeline_data or {}).get("event_impact_data"),
        schedule_replay_data=(pipeline_data or {}).get("schedule_replay_data"),
        risk_adjusted_excess_data=(pipeline_data or {}).get("risk_adjusted_excess_data"),
        summary_highlights_data=(pipeline_data or {}).get("summary_highlights_data"),
    )

    # ── 7. Excel 报告 ──
    result.excel_ok = _generate_full_excel_report(
        holdings,
        prep,
        output_dir,
        news_ok,
        llm_content,
        news_data,
        news_llm_meta,
        sec_order,
        pipeline_data,
        history_data,
        reporter,
        _enable_fund_deep_analysis,
        _enable_news,
        _enable_history,
        _enable_llm,
        debate_info,
        result,
        _enable_portfolio_evolution,
        _enable_action,
        _enable_data_quality,
        _enable_cost_lots,
        transactions,
        dividends,
        enable_fundamental_snapshot=_enable_stock_fundamentals,
    )

    result.news_ok = news_ok
    result.report_generated = result.html_ok or result.excel_ok
    _record_llm_context(perf, _llm_sink)
    perf.save()
    _collect_health_checks(_health_fut, "full", holdings)
    return result
