"""both 路径：HTML+Excel（不含 LLM 章节）生成编排。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


from src.python.report._experimental_seams import (
    inject_holding_change_data,
    record_prosperity_diagnosis,
)

if TYPE_CHECKING:  # ReportResult 定义在编排门面，运行期从生成入口传入（避免循环导入）
    from src.python.report.orchestrator import ReportResult
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
from src.python.report._report_helpers import (  # noqa: F401
    _action_holdings_details,
    _compute_details,
    _inject_evolution_data,
    _inject_snapshot_diff_data,
    _validate_pipeline_snapshot,
    _validate_prep_completeness,
)

logger = logging.getLogger("invest")


def _generate_report_both(
    holdings: list,
    config: dict,
    reporter: ProgressReporter,
    fetch_history: bool = False,
    output_dir: str | None = None,
    transactions: list | None = None,
    dividends: list | None = None,
    *,
    snapshot_namespace: str | None = None,
) -> "ReportResult":
    """both 报告路径：生成 HTML + Excel，不含 LLM 分析章节。

    流程：_compute_details() → capture_snapshot() → fetch_history_data()
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
        is_enable_news,
        is_enable_portfolio_evolution,
        is_enable_stock_fundamentals,
    )
    from src.python.config.features import is_feature_enabled
    from src.python.core.perf import PerfCollector
    from src.python.core.registry import get_report_section_order
    from src.python.llm.depth_profile import effective_news_limit, resolve_depth_profile
    from src.python.report._snapshot import capture_snapshot, fetch_history_data
    from src.python.report.excel_generator import generate_excel_report
    from src.python.report.html_writer import write_html_report
    from src.python.report.orchestrator import ReportResult

    perf = PerfCollector(report_type="both", holdings=holdings, stage_announcer=reporter.stage_progress)
    bind_perf(perf)
    result = ReportResult()
    result.holdings_ok = True

    # 后台启动健康检查（与数据获取并行）
    _health_fut = _spawn_health_checks()
    bind_health(_health_fut, "both", holdings)

    _enable_fund_deep_analysis = is_enable_fund_deep_analysis(config)
    _enable_news = is_enable_news(config)
    _enable_history = is_enable_history(config)
    _enable_portfolio_evolution = is_enable_portfolio_evolution(config)
    _enable_action = is_enable_action(config)
    _enable_data_quality = is_enable_data_quality(config)
    _enable_cost_lots = is_enable_cost_lots(config)
    _enable_stock_fundamentals = is_enable_stock_fundamentals(config)
    _enable_summary_highlights = is_feature_enabled("summary_highlights")
    sec_order = get_report_section_order(config)
    output = output_dir or config.get("output_dir", "reports")
    news_top_count = effective_news_limit(int(config.get("news_top_count", 300)), resolve_depth_profile(config))

    # ── 1. 行情获取（轻量级，无指数/穿透/分类） ──
    perf.start("行情获取")
    details = _compute_details(holdings, reporter)
    perf.stop()

    # 估值分位 + 市场温度（数据契约）：both 路径同样渲染「资产穿透TOP10」估值列
    # 与「投资分析汇总」温度行；开关关闭时编排函数返回 None（保持既有输出）
    from src.python.report.orchestrator import (
        compute_market_temperature_data,
        compute_valuation_data,
    )

    valuation_data = compute_valuation_data(details, config, reporter)
    market_temperature_data = compute_market_temperature_data(config, reporter)
    # 持仓个股财报摘要（数据契约）：both 路径不计算穿透，仅按持仓 A 股标的取数；
    # 关闭 / 无 key 时为 None（章节隐藏/写占位）
    financial_report_digest_data = None
    if _enable_stock_fundamentals:
        from src.python.report.financial_report_digest import build_financial_report_digest

        financial_report_digest_data = build_financial_report_digest(holdings, config, reporter)

    # 财务指标（数据契约）：both 路径同样只按持仓 A 股标的取数（无穿透），
    # 现价取自行情明细（PE/PB 用）；关闭时为 None（章节隐藏）
    financial_indicator_data = None
    if _enable_stock_fundamentals:
        from src.python.fetcher.financial_indicator import collect_price_map
        from src.python.report.financial_indicator import build_financial_indicator

        financial_indicator_data = build_financial_indicator(
            holdings, config, reporter, prices=collect_price_map(details)
        )

    # 申购限购状态（数据契约 purchase_status_data）：功能开关 `fund_purchase_limit`
    # 开启时取全量表（会话内单次）；关闭时为 None（申购状态列隐藏），
    # 全链失败为 available=False（静默隐列，不阻断报告生成）
    from src.python.report.purchase_status import build_purchase_status_data

    purchase_status_data = build_purchase_status_data(config)

    # ── 2. 快照对比（始终执行） ──
    perf.start("快照对比")
    pipeline_data = capture_snapshot(
        holdings,
        details,
        config,
        reporter,
        snapshot_namespace=snapshot_namespace,
    )
    # 2b. 组合演进数据（聚合多期快照，evolution_data；开关关闭时跳过计算）
    if _enable_portfolio_evolution:
        pipeline_data = _inject_evolution_data(pipeline_data, snapshot_namespace=snapshot_namespace)
        # 2b1. 快照差异摘要（snapshot_diff_data）：组合演进章顶部变化摘要，
        #      与演进数据同开关（同属组合演进章节）
        pipeline_data = _inject_snapshot_diff_data(pipeline_data, snapshot_namespace=snapshot_namespace)
    # 2b2. 持仓变动复盘（报告章节与增强开关 holding_change_review，默认关；独立于演进开关）：
    #      事件清单差分须晚于本次快照捕获；开关关闭时键缺席 → 整章隐藏（见 seams）
    inject_holding_change_data(pipeline_data, config, reporter, snapshot_namespace=snapshot_namespace)
    # 2b4. 摘要区本期要点与环比对照（报告章节与增强开关 summary_highlights，默认关）：
    #      快照 diff 单源纯内存派生；无上期快照时键值为 None → 首屏整块隐藏
    if _enable_summary_highlights and pipeline_data is not None:
        from src.python.report.summary_highlights import build_summary_highlights

        pipeline_data["summary_highlights_data"] = build_summary_highlights(pipeline_data)
    # 2c. 品种覆盖诊断 + 可信度摘要：逐品种数据状态/新鲜度标注，注入 pipeline_data
    #    （position_status + data_freshness）
    from src.python.core.data_freshness import build_freshness_summary
    from src.python.core.holding_status import build_coverage_summary
    from src.python.report.market_value import get_last_trading_day, get_prev_trading_day
    from src.python.report.pipeline_data_builder import merge_pipeline_data

    pipeline_data = merge_pipeline_data(
        pipeline_data,
        position_status=build_coverage_summary(holdings, details),
        data_freshness=build_freshness_summary(
            holdings,
            details,
            trading_day=get_last_trading_day(),
            prev_trading_day=get_prev_trading_day(),
        ),
        # 估值分位 + 市场温度（数据契约）：both 路径此处组装，开关关闭时为 None
        valuation_data=valuation_data,
        market_temperature_data=market_temperature_data,
    )
    # 行动建议单一数据源（action_data）在「3. 历史走势」之后统一注入
    # （组合回撤纪律需组合历史峰值市值，见 tail_risk_data 注入点）。
    perf.stop()
    # [checkpoint] pipeline_data 类型断言
    if pipeline_data is not None:
        assert isinstance(pipeline_data, dict), "capture_snapshot(both) pipeline_data 类型异常"
        _diff = pipeline_data.get("diff")
        if _diff is not None and not isinstance(_diff, dict):
            logger.warning("[checkpoint] pipeline_data.diff 类型异常(both): %s", type(_diff).__name__)

    # ── 3. 历史走势（条件获取） ──
    if _enable_history:
        perf.start("历史走势")
        history_data = fetch_history_data(holdings, config, reporter, fetch=fetch_history)
        perf.stop()
    else:
        history_data = None
        reporter.info("[章节配置] 历史走势已关闭，跳过")

    # 历史增强契约装配（危机区间标注[含回放态] + 风险调整超额）：full/both 两路径
    # 共用 _snapshot.assemble_history_augmented_data 唯一实现——开关判定与子块长窗
    # 取数集中，开关全关时仅写 crisis 关态契约（零新增取数，关态产物逐字节不变）
    from src.python.report._snapshot import assemble_history_augmented_data

    assemble_history_augmented_data(holdings, config, reporter, history_data, pipeline_data)

    # 尾部风险统计（tail_risk_data）：复用历史日收益序列，样本不足时 available=False
    from src.python.analysis.tail_risk import compute_tail_risk

    tail_risk_data = compute_tail_risk((history_data or {}).get("bars"))
    if pipeline_data is not None:
        pipeline_data["tail_risk_data"] = tail_risk_data

    # 行动建议单一数据源（action_data）：行动建议板块 + 智囊团深度复盘行动摘要共享。
    # 此处为 both 路径唯一构建（历史已就绪）：组合回撤纪律以组合历史峰值市值
    # 为基准，峰值自 history_data.bars 计算；历史走势关闭时峰值取 None，
    # 回撤纪律按「峰值未知」处理（组合级回撤不激活），其余纪律不受影响。
    from src.python.analysis.action_advisor import build_action_data
    from src.python.analysis.metrics import compute_portfolio_peak_mv

    if pipeline_data is not None:
        pipeline_data["action_data"] = build_action_data(
            _action_holdings_details(details, transactions),
            sum(d.market_value for d in details),
            portfolio_peak_mv=compute_portfolio_peak_mv((history_data or {}).get("bars")),
        )

    # 景气度框架诊断（实验性功能 prosperity_framework）：经实验挂载点接入（守护与
    # 注入语义见 `_experimental_seams`）。依赖已算好的基本面契约（ROE）与历史走势
    # （收益/回撤印证），故置于两者之后。
    record_prosperity_diagnosis(
        holdings,
        details,
        None,
        config,
        reporter,
        financial_indicator_data=financial_indicator_data,
        history_data=history_data,
        pipeline_data=pipeline_data,
    )

    # 市场情绪与持仓热点（报告增强开关 market_sentiment）：开关关闭返回 None（零行为变化）
    from src.python.report._report_aux_metrics import compute_market_sentiment_data

    _ms_data = compute_market_sentiment_data(holdings, None, config, reporter)
    if _ms_data is not None and pipeline_data is not None:
        pipeline_data["market_sentiment_data"] = _ms_data

    # ── 4. HTML 报告 ──
    _news_label = "含新闻" if _enable_news else "无新闻"
    reporter.info(f"正在生成 HTML 报告（{_news_label}）...")
    perf.start("HTML 生成")
    try:
        chart_datasets = _build_chart_datasets_for_report(
            history_data=history_data,
            details=details,
        )
        # 成本流水数据（fund_flow_data）：复用 excel_market_data 组装逻辑，
        # 开关关闭返回 None（HTML 模板保持既有输出）。
        from src.python.report.excel_market_data import _build_flow_data

        fund_flow_data = _build_flow_data(_enable_cost_lots, transactions, dividends, holdings, details)
        path = write_html_report(
            holdings,
            output_dir=output,
            news_top_count=news_top_count,
            include_news=_enable_news,
            details=details,
            section_order=sec_order,
            history_data=history_data,
            progress=reporter,
            enable_fund_deep_analysis=_enable_fund_deep_analysis,
            enable_news=_enable_news,
            enable_history=_enable_history,
            enable_portfolio_evolution=_enable_portfolio_evolution,
            enable_action=_enable_action,
            enable_llm=False,
            chart_datasets=chart_datasets,
            evolution_data=(pipeline_data or {}).get("evolution_data"),
            enable_data_quality=_enable_data_quality,
            position_status=(pipeline_data or {}).get("position_status"),
            data_freshness=(pipeline_data or {}).get("data_freshness"),
            action_data=(pipeline_data or {}).get("action_data"),
            prosperity_framework_data=(pipeline_data or {}).get("prosperity_framework_data"),
            market_sentiment_data=(pipeline_data or {}).get("market_sentiment_data"),
            crisis_annotation_data=(pipeline_data or {}).get("crisis_annotation_data"),
            tail_risk_data=tail_risk_data,
            snapshot_diff_data=(pipeline_data or {}).get("snapshot_diff_data"),
            fund_flow_data=fund_flow_data,
            valuation_data=valuation_data,
            market_temperature_data=market_temperature_data,
            enable_fundamental_snapshot=_enable_stock_fundamentals,
            financial_report_digest_data=financial_report_digest_data,
            financial_indicator_data=financial_indicator_data,
            purchase_status_data=purchase_status_data,
            holding_change_data=(pipeline_data or {}).get("holding_change_data"),
            event_impact_data=(pipeline_data or {}).get("event_impact_data"),
            schedule_replay_data=(pipeline_data or {}).get("schedule_replay_data"),
            risk_adjusted_excess_data=(pipeline_data or {}).get("risk_adjusted_excess_data"),
            summary_highlights_data=(pipeline_data or {}).get("summary_highlights_data"),
        )
        reporter.ok(f"HTML 报告已生成: {path}")
        result.html_ok = True
    except Exception:
        reporter.add_error("HTML 报告生成失败（详情请查看日志文件 logs/app.log）")
        logger.exception("HTML 报告写入失败")
        result.errors.append("HTML 报告生成失败")
    perf.stop()

    # ── 5. Excel 报告 ──
    reporter.info("正在生成 Excel 报告...")
    perf.start("Excel 生成")
    try:
        generate_excel_report(
            holdings,
            include_news=_enable_news,
            output_dir=output,
            news_top_count=news_top_count,
            details=details,
            section_order=sec_order,
            pipeline_data=pipeline_data,
            history_data=history_data,
            progress=reporter,
            enable_fund_deep_analysis=_enable_fund_deep_analysis,
            enable_news=_enable_news,
            enable_history=_enable_history,
            enable_portfolio_evolution=_enable_portfolio_evolution,
            enable_action=_enable_action,
            enable_llm=False,
            enable_data_quality=_enable_data_quality,
            enable_cost_lots=_enable_cost_lots,
            transactions=transactions,
            dividends=dividends,
            valuation_data=valuation_data,
            market_temperature_data=market_temperature_data,
            enable_fundamental_snapshot=_enable_stock_fundamentals,
            financial_report_digest_data=financial_report_digest_data,
            financial_indicator_data=financial_indicator_data,
            purchase_status_data=purchase_status_data,
        )
        reporter.ok("Excel 报告已生成")
        result.excel_ok = True
    except Exception:
        reporter.add_error("Excel 报告生成失败（详情请查看日志文件 logs/app.log）")
        logger.exception("Excel 报告生成失败")
        result.errors.append("Excel 报告生成失败")
    perf.stop()

    result.report_generated = result.html_ok or result.excel_ok
    perf.save()
    _collect_health_checks(_health_fut, "both", holdings)
    return result
