"""both 报告路径的五个阶段实现（编排壳见 `_generation_both`）。

拆出来的原因：阶段名与顺序是 `perf_history` 跨版本可比性的口径，而阶段内部又各自
带开关判定、契约装配与失败隔离。放在一个 388 行的函数里时，「哪个阶段含哪些副作用」
「start/stop 是否成对」只能逐行读。现在：

  - 阶段表 :data:`BOTH_STAGES` 是**唯一**的阶段定义处（名字 + 实现 + 是否执行的判定）；
  - 每个阶段只接收 :class:`BothRun`（运行上下文）并写回其中字段，不自行开关 perf；
  - perf 的 start/stop 配对由 `stage_runner` 统一保证（含异常路径）。

本模块不做报告落盘之外的 IO 编排，也不创建 PerfCollector / 运行边界。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ── 可 patch 的接缝（模块级集中导入）─────────────────────────
# 这些函数在拆分前是 `_generation_both` 的模块级名字，测试按「patch 消费模块」纪律打桩；
# 消费点移入本模块后，名字随之在此集中，测试目标同步迁移（漏迁即 AttributeError）。
from src.python.report._chart_dataset_factory import _build_chart_datasets_for_report  # noqa: F401
from src.python.report._report_helpers import (  # noqa: F401
    _compute_details,
    _inject_evolution_data,
    _inject_snapshot_diff_data,
)

logger = logging.getLogger("invest")


@dataclass(frozen=True)
class BothOptions:
    """both 路径的开关与输出参数（一次解析、整轮只读）。"""

    enable_fund_deep_analysis: bool
    enable_news: bool
    enable_history: bool
    enable_portfolio_evolution: bool
    enable_action: bool
    enable_cost_lots: bool
    enable_stock_fundamentals: bool
    enable_summary_highlights: bool
    section_order: list[dict]
    output: str
    news_top_count: int


@dataclass
class BothRun:
    """一次 both 运行的上下文（阶段之间只经此对象传递，不靠局部变量）。"""

    holdings: list
    config: dict
    reporter: Any
    fetch_history: bool
    transactions: list | None
    dividends: list | None
    snapshot_namespace: str | None
    options: BothOptions
    perf: Any
    result: Any
    details: list = field(default_factory=list)
    pipeline_data: dict | None = None
    history_data: dict | None = None
    #: 数据契约（估值/温度/财报摘要/财务指标/申购状态），阶段 1 产出、阶段 4/5 消费
    contracts: dict[str, Any] = field(default_factory=dict)

    @property
    def _pipeline(self) -> dict:
        """pipeline_data 的非空视图（阶段内只读访问用；None 时给空字典）。"""
        return self.pipeline_data or {}


def resolve_both_options(config: dict, output_dir: str | None) -> BothOptions:
    """解析 both 路径的开关与输出参数（配置读取单点）。"""
    from src.python.config import (
        get_default,
        is_enable_action,
        is_enable_cost_lots,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_news,
        is_enable_portfolio_evolution,
        is_enable_stock_fundamentals,
        resolve_output_dir,
    )
    from src.python.config.features import is_feature_enabled
    from src.python.core.registry import get_report_section_order
    from src.python.llm.depth_profile import effective_news_limit, resolve_depth_profile

    return BothOptions(
        enable_fund_deep_analysis=is_enable_fund_deep_analysis(config),
        enable_news=is_enable_news(config),
        enable_history=is_enable_history(config),
        enable_portfolio_evolution=is_enable_portfolio_evolution(config),
        enable_action=is_enable_action(config),
        enable_cost_lots=is_enable_cost_lots(),
        enable_stock_fundamentals=is_enable_stock_fundamentals(),
        enable_summary_highlights=is_feature_enabled("summary_highlights"),
        section_order=get_report_section_order(config),
        output=output_dir or resolve_output_dir(config),
        news_top_count=effective_news_limit(
            int(config.get("news_top_count", get_default("news_top_count"))), resolve_depth_profile(config)
        ),
    )


def stage_quotes(run: BothRun) -> None:
    """阶段 1：行情获取（轻量，无指数/穿透/分类）+ 首屏数据契约装配。"""
    from src.python.report.orchestrator import (
        compute_market_temperature_data,
        compute_valuation_data,
    )

    run.details = _compute_details(run.holdings, run.reporter)

    # 估值分位 + 市场温度：both 路径同样渲染「资产穿透TOP10」估值列与「投资分析汇总」温度行；
    # 开关关闭时编排函数返回 None（保持既有输出）
    contracts: dict[str, Any] = {
        "valuation_data": compute_valuation_data(run.details, run.config, run.reporter),
        "market_temperature_data": compute_market_temperature_data(run.config, run.reporter),
        "financial_report_digest_data": None,
        "financial_indicator_data": None,
    }

    # 持仓个股财报摘要 + 财务指标：both 路径不计算穿透，仅按持仓 A 股标的取数；
    # 关闭/无 key 时为 None（章节隐藏/写占位）。现价取自行情明细（PE/PB 用）。
    if run.options.enable_stock_fundamentals:
        from src.python.fetcher.financial_indicator import collect_price_map
        from src.python.report.financial_indicator import build_financial_indicator
        from src.python.report.financial_report_digest import build_financial_report_digest

        contracts["financial_report_digest_data"] = build_financial_report_digest(
            run.holdings, run.config, run.reporter
        )
        contracts["financial_indicator_data"] = build_financial_indicator(
            run.holdings, run.config, run.reporter, prices=collect_price_map(run.details)
        )

    # 申购限购状态：开关 `fund_purchase_limit` 开启时取全量表（会话内单次）；关闭为 None。
    # holdings_details 传最小形态（name/code，与 full 路径同源同形）——误传 config 时
    # 迭代 dict 只会得到键名，`h.get("code")` 当场 AttributeError 中断本路径。
    from src.python.report.purchase_status import build_purchase_status_data

    contracts["purchase_status_data"] = build_purchase_status_data(
        [{"name": d.name, "code": d.code} for d in run.details]
    )
    run.contracts = contracts


def stage_snapshot(run: BothRun) -> None:
    """阶段 2：快照捕获与对比 + 组合演进/差异/持仓变动/首页摘要 + 覆盖与新鲜度契约。"""
    from src.python.core.data_freshness import build_freshness_summary
    from src.python.core.holding_status import build_coverage_summary
    from src.python.report._experimental_seams import inject_holding_change_data
    from src.python.report._snapshot import capture_snapshot
    from src.python.report.market_value import get_last_trading_day, get_prev_trading_day
    from src.python.report.pipeline_data_builder import merge_pipeline_data

    pipeline_data = capture_snapshot(
        run.holdings,
        run.details,
        run.config,
        run.reporter,
        snapshot_namespace=run.snapshot_namespace,
    )

    # 组合演进数据（聚合多期快照）：开关关闭时跳过计算；快照差异摘要与演进同开关
    if run.options.enable_portfolio_evolution:
        pipeline_data = _inject_evolution_data(pipeline_data, snapshot_namespace=run.snapshot_namespace)
        pipeline_data = _inject_snapshot_diff_data(pipeline_data, snapshot_namespace=run.snapshot_namespace)

    # 持仓变动复盘（独立开关）：事件清单差分须晚于本次快照捕获；开关关闭时键缺席 → 整章隐藏
    inject_holding_change_data(pipeline_data, run.config, run.reporter, snapshot_namespace=run.snapshot_namespace)

    # 首页执行摘要卡（快照 diff 单源纯内存派生；无上期快照时键为 None → 首屏整块隐藏）
    if run.options.enable_summary_highlights and pipeline_data is not None:
        from src.python.report.summary_highlights import build_summary_highlights

        pipeline_data["summary_highlights_data"] = build_summary_highlights(pipeline_data)

    # 品种覆盖诊断 + 可信度摘要：逐品种数据状态/新鲜度标注
    pipeline_data = merge_pipeline_data(
        pipeline_data,
        position_status=build_coverage_summary(run.holdings, run.details),
        data_freshness=build_freshness_summary(
            run.holdings,
            run.details,
            trading_day=get_last_trading_day(),
            prev_trading_day=get_prev_trading_day(),
        ),
        valuation_data=run.contracts.get("valuation_data"),
        market_temperature_data=run.contracts.get("market_temperature_data"),
    )
    run.pipeline_data = pipeline_data

    # [checkpoint] pipeline_data 类型校验（异常只告警，不中断报告）
    if not isinstance(pipeline_data, dict):
        if pipeline_data is not None:
            logger.warning("[checkpoint] pipeline_data 类型异常(both): %s", type(pipeline_data).__name__)
    else:
        _diff = pipeline_data.get("diff")
        if _diff is not None and not isinstance(_diff, dict):
            logger.warning("[checkpoint] pipeline_data.diff 类型异常(both): %s", type(_diff).__name__)


def stage_history_fetch(run: BothRun) -> None:
    """阶段 3：历史走势取数（开关关闭时该阶段不启停 perf，跳过提示见 `_skip_history`）。

    行情明细作「最新估值」来源：历史净值链路 T+1~T+2 滞后时回填终点 bar，
    令走势终值与报告头总市值同口径。
    """
    from src.python.report._snapshot import fetch_history_data, latest_quotes_from_detail_rows

    run.history_data = fetch_history_data(
        run.holdings,
        run.config,
        run.reporter,
        fetch=run.fetch_history,
        latest_quotes=latest_quotes_from_detail_rows(run.details),
    )


def stage_history_assembly(run: BothRun) -> None:
    """历史之后的装配段（**不单独计时**，与拆分前口径一致：只在历史取数阶段计时）。

    含历史增强契约、尾部风险、行动建议与判断依据块、决策跨期反思、景气度诊断、市场情绪。
    """
    from src.python.analysis.action_advisor import build_action_data
    from src.python.analysis.metrics import compute_portfolio_peak_mv
    from src.python.analysis.tail_risk import compute_tail_risk
    from src.python.report._experimental_seams import record_prosperity_diagnosis
    from src.python.report._report_aux_metrics import compute_market_sentiment_data
    from src.python.report._report_helpers import _action_holdings_details
    from src.python.report._snapshot import assemble_history_augmented_data, latest_quotes_from_detail_rows

    # 历史增强契约装配（危机区间标注 + 风险调整超额）：full/both 共用唯一实现
    assemble_history_augmented_data(
        run.holdings,
        run.config,
        run.reporter,
        run.history_data,
        run.pipeline_data,
        latest_quotes=latest_quotes_from_detail_rows(run.details),
    )

    # 尾部风险统计：复用历史日收益序列，样本不足时 available=False
    tail_risk_data = compute_tail_risk((run.history_data or {}).get("bars"))
    if run.pipeline_data is not None:
        run.pipeline_data["tail_risk_data"] = tail_risk_data

    # 行动建议单一数据源（action_data）：both 路径唯一构建点（历史已就绪）——
    # 组合回撤纪律以组合历史峰值市值为基准；历史关闭时峰值取 None（组合级回撤不激活）
    if run.pipeline_data is not None:
        peak_mv = compute_portfolio_peak_mv((run.history_data or {}).get("bars"))
        holdings_details = _action_holdings_details(run.details, run.transactions)
        total_mv = sum(d.market_value for d in run.details)
        action_data = build_action_data(holdings_details, total_mv, portfolio_peak_mv=peak_mv)
        run.pipeline_data["action_data"] = action_data

        # 判断依据块随峰值与纪律触发条就绪重装配（幂等）；纯内存组装，单独计时
        from src.python.report.decision_basis import PERF_PHASE_ASSEMBLY, build_decision_basis_data

        run.perf.start(PERF_PHASE_ASSEMBLY)
        try:
            run.pipeline_data["decision_basis_data"] = build_decision_basis_data(
                holdings_details,
                total_mv,
                portfolio_peak_mv=peak_mv,
                discipline_signals=action_data.get("discipline_signals"),
            )
        finally:
            run.perf.stop()

        # 决策跨期反思闭环（实验功能，默认关）：与 full 路径同一挂载点，只换入参来源——
        # both 路径无 prep 契约，按挂载点所需键构最小入参。结算必须先于产出：
        # 两侧（HTML 行动章 / Excel 行动页签）消费的复盘区块在此写入 pipeline_data。
        from datetime import datetime

        from src.python.report._experimental_seams import (
            record_deterministic_decisions,
            record_llm_decisions_and_review_block,
        )

        decision_input = {
            "today_str": datetime.now().strftime("%Y-%m-%d"),
            "holdings_details": holdings_details,
        }
        record_deterministic_decisions(decision_input, action_data, run.reporter)
        record_llm_decisions_and_review_block(decision_input, (), False, run.pipeline_data, run.reporter)

    # 景气度框架诊断（实验功能）：依赖已算好的基本面契约（ROE）与历史走势，故置于两者之后
    record_prosperity_diagnosis(
        run.holdings,
        run.details,
        None,
        run.config,
        run.reporter,
        financial_indicator_data=run.contracts.get("financial_indicator_data"),
        history_data=run.history_data,
        pipeline_data=run.pipeline_data,
    )

    # 市场情绪与持仓热点（增强开关 market_sentiment）：关闭返回 None（零行为变化）
    market_sentiment_data = compute_market_sentiment_data(run.holdings, None, run.config, run.reporter)
    if market_sentiment_data is not None and run.pipeline_data is not None:
        run.pipeline_data["market_sentiment_data"] = market_sentiment_data


def stage_html(run: BothRun) -> None:
    """阶段 4：HTML 报告（失败隔离：只置 html_ok=False 与 errors，不中断 Excel）。"""
    from src.python.report.html_writer import close_html_generation_stage, write_html_report

    opts = run.options
    news_label = "含新闻" if opts.enable_news else "无新闻"
    run.reporter.info(f"正在生成 HTML 报告（{news_label}）...")
    html_rec = run.perf.recorder("HTML 生成")
    phase_t0 = time.perf_counter()
    html_path: str | None = None
    pipeline = run._pipeline
    try:
        chart_datasets = _build_chart_datasets_for_report(history_data=run.history_data, details=run.details)
        if html_rec is not None:
            # 图表数据装配与后续渲染/落盘分开记：整段偏慢时先分清是哪一段
            html_rec.record("图表数据装配", time.perf_counter() - phase_t0)

        # 成本流水数据：复用 excel_market_data 组装逻辑，开关关闭返回 None（模板保持既有输出）
        from src.python.report.excel_market_data import _build_flow_data

        fund_flow_data = _build_flow_data(
            opts.enable_cost_lots, run.transactions, run.dividends, run.holdings, run.details
        )
        path = write_html_report(
            run.holdings,
            output_dir=opts.output,
            news_top_count=opts.news_top_count,
            include_news=opts.enable_news,
            details=run.details,
            section_order=opts.section_order,
            history_data=run.history_data,
            progress=run.reporter,
            enable_fund_deep_analysis=opts.enable_fund_deep_analysis,
            enable_news=opts.enable_news,
            enable_history=opts.enable_history,
            enable_portfolio_evolution=opts.enable_portfolio_evolution,
            enable_action=opts.enable_action,
            enable_llm=False,
            chart_datasets=chart_datasets,
            evolution_data=pipeline.get("evolution_data"),
            position_status=pipeline.get("position_status"),
            data_freshness=pipeline.get("data_freshness"),
            action_data=pipeline.get("action_data"),
            decision_basis_data=pipeline.get("decision_basis_data"),
            decision_review_data=pipeline.get("decision_review_data"),
            prosperity_framework_data=pipeline.get("prosperity_framework_data"),
            market_sentiment_data=pipeline.get("market_sentiment_data"),
            crisis_annotation_data=pipeline.get("crisis_annotation_data"),
            tail_risk_data=pipeline.get("tail_risk_data"),
            snapshot_diff_data=pipeline.get("snapshot_diff_data"),
            fund_flow_data=fund_flow_data,
            valuation_data=run.contracts.get("valuation_data"),
            market_temperature_data=run.contracts.get("market_temperature_data"),
            enable_fundamental_snapshot=opts.enable_stock_fundamentals,
            financial_report_digest_data=run.contracts.get("financial_report_digest_data"),
            financial_indicator_data=run.contracts.get("financial_indicator_data"),
            purchase_status_data=run.contracts.get("purchase_status_data"),
            holding_change_data=pipeline.get("holding_change_data"),
            event_impact_data=pipeline.get("event_impact_data"),
            schedule_replay_data=pipeline.get("schedule_replay_data"),
            risk_adjusted_excess_data=pipeline.get("risk_adjusted_excess_data"),
            summary_highlights_data=pipeline.get("summary_highlights_data"),
            stage_recorder=html_rec,
        )
        run.reporter.ok(f"HTML 报告已生成: {path}")
        html_path = path
        run.result.html_ok = True
    except Exception:
        run.reporter.add_error("HTML 报告生成失败（详情请查看日志文件 logs/app.log）")
        logger.exception("HTML 报告写入失败")
        run.result.errors.append("HTML 报告生成失败")
    # 收口与慢段告警与 full 路径共用同一实现（both 侧不得缺少告警）
    close_html_generation_stage(html_rec, time.perf_counter() - phase_t0, html_path)


def stage_excel(run: BothRun) -> None:
    """阶段 5：Excel 报告（失败隔离：只置 excel_ok=False 与 errors）。"""
    from src.python.report.excel_generator import generate_excel_report

    opts = run.options
    run.reporter.info("正在生成 Excel 报告...")
    try:
        generate_excel_report(
            run.holdings,
            include_news=opts.enable_news,
            output_dir=opts.output,
            news_top_count=opts.news_top_count,
            details=run.details,
            section_order=opts.section_order,
            pipeline_data=run.pipeline_data,
            history_data=run.history_data,
            progress=run.reporter,
            enable_fund_deep_analysis=opts.enable_fund_deep_analysis,
            enable_news=opts.enable_news,
            enable_history=opts.enable_history,
            enable_portfolio_evolution=opts.enable_portfolio_evolution,
            enable_action=opts.enable_action,
            enable_llm=False,
            enable_cost_lots=opts.enable_cost_lots,
            transactions=run.transactions,
            dividends=run.dividends,
            valuation_data=run.contracts.get("valuation_data"),
            market_temperature_data=run.contracts.get("market_temperature_data"),
            enable_fundamental_snapshot=opts.enable_stock_fundamentals,
            financial_report_digest_data=run.contracts.get("financial_report_digest_data"),
            financial_indicator_data=run.contracts.get("financial_indicator_data"),
            purchase_status_data=run.contracts.get("purchase_status_data"),
        )
        run.reporter.ok("Excel 报告已生成")
        run.result.excel_ok = True
    except Exception:
        run.reporter.add_error("Excel 报告生成失败（详情请查看日志文件 logs/app.log）")
        logger.exception("Excel 报告生成失败")
        run.result.errors.append("Excel 报告生成失败")


def _always(_run: BothRun) -> bool:
    return True


def _skip_history(run: BothRun) -> None:
    """历史走势关闭时的跳过提示（该阶段不启停 perf，与拆分前口径一致）。"""
    run.history_data = None
    run.reporter.info("[章节配置] 历史走势已关闭，跳过")


#: 阶段表：**名字即 perf 口径**（改名等于改 `perf_history` 可比性），顺序即执行顺序。
#: 五元组：名字 / 实现 / 是否执行 / 跳过提示 / 是否单独计时。
#: 装配段（历史之后的装配）不计时——与拆分前一致：只有历史**取数**阶段进 perf。
BOTH_STAGES: tuple[
    tuple[
        str,
        Callable[[BothRun], None],
        Callable[[BothRun], bool],
        Callable[[BothRun], None] | None,
        bool,
    ],
    ...,
] = (
    ("行情获取", stage_quotes, _always, None, True),
    ("快照对比", stage_snapshot, _always, None, True),
    ("历史走势", stage_history_fetch, lambda run: run.options.enable_history, _skip_history, True),
    ("", stage_history_assembly, _always, None, False),
    ("HTML 生成", stage_html, _always, None, True),
    ("Excel 生成", stage_excel, _always, None, True),
)


def stage_runner(run: BothRun) -> None:
    """按阶段表执行，保证每个 `perf.start` 都有配对的 `stop`（异常路径同样收口）。"""
    for name, stage, should_run, on_skip, timed in BOTH_STAGES:
        if not should_run(run):
            if on_skip is not None:
                on_skip(run)
            continue
        if not timed:
            stage(run)
            continue
        run.perf.start(name)
        try:
            stage(run)
        finally:
            run.perf.stop()


__all__ = [
    "BOTH_STAGES",
    "BothOptions",
    "BothRun",
    "resolve_both_options",
    "stage_runner",
]
