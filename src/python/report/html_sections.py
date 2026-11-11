"""HTML 报告的区块装配（按连续区段分组，顺序即契约）。

为什么单独成模块：19 处 `_render_*` 调用原本与模板参数、后处理混在一个函数里，
「哪个装配函数产出哪些模板变量」只能靠读 400 行；而这里最容易静默出错的是**元组解包
顺序**（把 `penetration, profit_ok, dividend_ok` 解错位不会报错，只会让页面显示错数）。

现在：

  - 装配按**连续区段**分组成 :data:`SECTION_BUILDERS`（顺序与抽离前逐行一致，不重排——
    重排会改变 Chart.js 数据补齐所依赖的时序）；
  - 每组只读写 :class:`HtmlAssembly`（运行上下文），不碰模板、不落盘；
  - 产物由 :meth:`HtmlAssembly.bindings` 以 :class:`SectionBindings`（NamedTuple，
    逐字段保留类型）返回，供调用侧一次解包；解包顺序由哨兵归属用例守护。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, NamedTuple

from src.python.report.html_renderers import (
    _render_account_grouping,
    _render_category_info,
    _render_category_table,
    _render_concentration,
    _render_fund_performance_section,
    _render_index_section,
    _render_llm_content_section,
    _render_llm_module_info,
    _render_manager_analysis,
    _render_market_value_section,
    _render_news_section,
    _render_overlap_matrix,
    _render_penetration_section,
    _render_style_analysis,
)

logger = logging.getLogger("invest")


class SectionBindings(NamedTuple):
    """装配产物（**字段顺序即调用侧解包顺序**，哨兵归属用例守护）。"""

    details: list
    total_mv: float
    total_cost: float
    total_profit: float
    total_today_profit: float
    total_profit_rate: float
    today_profit_rate: float
    accounts: dict
    account_totals: dict
    cat_counts: dict
    update_status_dict: dict
    a_indices: dict
    us_indices: dict
    a_indices_list: list
    us_indices_list: list
    cat_data: list
    cat_dividend_ok: bool
    penetration: dict | None
    penetration_profit_ok: bool
    penetration_dividend_ok: bool
    perf_data: list
    candidate_data: dict | None
    manager_analysis: dict | None
    overlap_matrix: dict | None
    concentration_analysis: dict | None
    style_analysis: dict | None
    news_data: list
    news_llm_meta: dict | None
    llm_enabled_flag: bool
    global_macro_content: str | None
    expert_review_content: str | None
    health_check_content: str | None
    penetration_deep_content: str | None
    llm_module_info: list
    llm_endpoint: str | None
    module_disabled: dict
    llm_session_usage: dict | None
    debate_mode_label: str | None
    debate_mode_combination: str | None


@dataclass
class HtmlAssembly:
    """装配期上下文：输入参数 + 逐步累积的产物（产物字段一律非 Optional）。"""

    # ── 输入（允许 None：调用侧可不传，渲染函数自行兜底）──
    holdings: list
    details: list | None
    prog: Any
    today_str: str
    trading_day: str
    a_indices: dict | None
    us_indices: dict | None
    include_news: bool
    news_data: list | None
    news_top_count: int
    news_llm_meta: dict | None
    enable_llm: bool
    llm_content: Any
    chart_datasets: dict | None
    enable_fund_deep_analysis: bool
    risk_adjusted_excess_data: Any
    position_relationship_data: Any
    debate_info: dict | None

    # ── 产物 ──
    details_out: list = field(default_factory=list)
    totals: tuple = ()
    accounts: dict = field(default_factory=dict)
    account_totals: dict = field(default_factory=dict)
    cat_counts: dict = field(default_factory=dict)
    update_status_dict: dict = field(default_factory=dict)
    a_indices_out: dict = field(default_factory=dict)
    us_indices_out: dict = field(default_factory=dict)
    a_indices_list: list = field(default_factory=list)
    us_indices_list: list = field(default_factory=list)
    cat_data: list = field(default_factory=list)
    cat_dividend_ok: bool = True
    penetration: dict | None = None
    penetration_profit_ok: bool = True
    penetration_dividend_ok: bool = True
    perf_data: list = field(default_factory=list)
    candidate_data: dict | None = None
    manager_analysis: dict | None = None
    overlap_matrix: dict | None = None
    concentration_analysis: dict | None = None
    style_analysis: dict | None = None
    news_data_out: list = field(default_factory=list)
    llm_enabled_flag: bool = False
    global_macro_content: str | None = None
    expert_review_content: str | None = None
    health_check_content: str | None = None
    penetration_deep_content: str | None = None
    llm_module_info: list = field(default_factory=list)
    llm_endpoint: str | None = None
    module_disabled: dict = field(default_factory=dict)
    llm_session_usage: dict | None = None
    debate_mode_label: str | None = None
    debate_mode_combination: str | None = None

    def bindings(self) -> SectionBindings:
        """按 :class:`SectionBindings` 字段顺序给出产物（位置契约单源）。"""
        totals = list(self.totals) + [0.0] * (6 - len(self.totals))
        return SectionBindings(
            details=self.details_out,
            total_mv=totals[0],
            total_cost=totals[1],
            total_profit=totals[2],
            total_today_profit=totals[3],
            total_profit_rate=totals[4],
            today_profit_rate=totals[5],
            accounts=self.accounts,
            account_totals=self.account_totals,
            cat_counts=self.cat_counts,
            update_status_dict=self.update_status_dict,
            a_indices=self.a_indices_out,
            us_indices=self.us_indices_out,
            a_indices_list=self.a_indices_list,
            us_indices_list=self.us_indices_list,
            cat_data=self.cat_data,
            cat_dividend_ok=self.cat_dividend_ok,
            penetration=self.penetration,
            penetration_profit_ok=self.penetration_profit_ok,
            penetration_dividend_ok=self.penetration_dividend_ok,
            perf_data=self.perf_data,
            candidate_data=self.candidate_data,
            manager_analysis=self.manager_analysis,
            overlap_matrix=self.overlap_matrix,
            concentration_analysis=self.concentration_analysis,
            style_analysis=self.style_analysis,
            news_data=self.news_data_out,
            news_llm_meta=self.news_llm_meta,
            llm_enabled_flag=self.llm_enabled_flag,
            global_macro_content=self.global_macro_content,
            expert_review_content=self.expert_review_content,
            health_check_content=self.health_check_content,
            penetration_deep_content=self.penetration_deep_content,
            llm_module_info=self.llm_module_info,
            llm_endpoint=self.llm_endpoint,
            module_disabled=self.module_disabled,
            llm_session_usage=self.llm_session_usage,
            debate_mode_label=self.debate_mode_label,
            debate_mode_combination=self.debate_mode_combination,
        )


def _group_holdings(state: HtmlAssembly) -> None:
    """① 市值核算 + 按账户分组 + 分类信息（顺序不可换：后两组都吃市值核算后的明细）。"""
    state.details_out, totals = _render_market_value_section(state.holdings, state.details, state.today_str, state.prog)
    state.totals = tuple(totals)
    state.accounts, state.account_totals = _render_account_grouping(state.details_out, state.prog)
    state.cat_counts, state.update_status_dict = _render_category_info(
        state.holdings, state.details_out, state.trading_day
    )


def _group_index(state: HtmlAssembly) -> None:
    """② 市场指数（A 股 + 美股列表）。"""
    state.a_indices_out, state.us_indices_out, state.a_indices_list, state.us_indices_list = _render_index_section(
        state.prog, state.a_indices, state.us_indices
    )


def _group_category_table(state: HtmlAssembly) -> None:
    """③ 分类表（分红标记随之）。"""
    state.cat_data, state.cat_dividend_ok = _render_category_table(state.holdings, state.details_out, state.prog)


def _group_penetration_and_perf(state: HtmlAssembly) -> None:
    """④ 资产穿透 + 基金业绩对照，并据权威数据补齐 Chart.js 数据集。

    三张图的数据源（cat_data / penetration）只在本装配路径内计算，调用侧传入的
    chart_datasets 拿不到它们，会误显示「暂不可用」；此处用权威数据重建并覆盖，
    保证图表与表格同源（单图失败只跳过该图）。
    """
    state.penetration, state.penetration_profit_ok, state.penetration_dividend_ok = _render_penetration_section(
        state.holdings, state.details_out, state.prog
    )
    state.perf_data, state.candidate_data = _render_fund_performance_section(
        state.holdings, state.details_out, state.prog
    )
    charts = state.chart_datasets
    if charts is None:
        return

    from src.python.report.chart_data_builder import (
        _build_category_doughnut_dataset,
        _build_corr_rolling_dataset,
        _build_excess_rolling_dataset,
        _build_industry_bar_dataset,
        _build_penetration_bar_dataset,
    )

    def _fill(key: str, build: Any) -> None:
        """补齐单张图：失败只跳过该图（图表缺失不该影响整份报告）。"""
        try:
            charts[key] = build()
        except Exception:  # noqa: BLE001
            logger.warning("[chart] %s 数据补齐失败，保留原数据集", key, exc_info=True)

    _fill("category_doughnut", lambda: _build_category_doughnut_dataset(None, state.cat_data))
    _fill("industry_bar", lambda: _build_industry_bar_dataset(state.penetration))
    _fill("penetration_bar", lambda: _build_penetration_bar_dataset(state.penetration))
    _fill("excess_rolling", lambda: _build_excess_rolling_dataset(state.risk_adjusted_excess_data))
    _fill("corr_rolling", lambda: _build_corr_rolling_dataset(state.position_relationship_data))


def _group_fund_deep(state: HtmlAssembly) -> None:
    """⑤ 基金深度四块：经理变更 / 重合度矩阵 / 集中度 / 风格与因子。"""
    state.manager_analysis = _render_manager_analysis(state.holdings, state.enable_fund_deep_analysis, state.prog)
    state.overlap_matrix = _render_overlap_matrix(
        state.holdings, state.details_out, state.enable_fund_deep_analysis, state.prog
    )
    state.concentration_analysis = _render_concentration(state.holdings, state.enable_fund_deep_analysis, state.prog)
    state.style_analysis = _render_style_analysis(state.holdings, state.enable_fund_deep_analysis, state.prog)


def _group_news(state: HtmlAssembly) -> None:
    """⑥ 财经新闻（穿透数据参与关联分析）。"""
    state.news_data_out, state.news_llm_meta = _render_news_section(
        state.include_news,
        state.news_data,
        state.news_llm_meta,
        state.holdings,
        state.news_top_count,
        state.penetration,
        state.prog,
    )


def _group_llm(state: HtmlAssembly) -> None:
    """⑦ LLM 章节内容 + 模块状态，并按辩论模式覆盖 expert_review 状态标签。"""
    (
        state.llm_enabled_flag,
        state.global_macro_content,
        state.expert_review_content,
        state.health_check_content,
        state.penetration_deep_content,
    ) = _render_llm_content_section(state.enable_llm, state.llm_content)

    state.llm_module_info, state.llm_endpoint, state.module_disabled, state.llm_session_usage = _render_llm_module_info(
        state.llm_enabled_flag
    )

    from src.python.report._debate_utils import detect_debate_mode

    state.debate_mode_label, state.debate_mode_combination = detect_debate_mode(state.debate_info)
    if state.debate_mode_label:
        for item in state.llm_module_info:
            if item.get("key") == "expert_review" and item.get("status") in ("success", "cached"):
                item["status_label"] = state.debate_mode_label


#: 区块装配表：**顺序即契约**（与抽离前逐行顺序一致；重排会改变 chart 补齐的时序）。
SECTION_BUILDERS: tuple[tuple[str, Any], ...] = (
    ("持仓与分类", _group_holdings),
    ("市场指数", _group_index),
    ("分类表", _group_category_table),
    ("穿透与基金业绩", _group_penetration_and_perf),
    ("基金深度", _group_fund_deep),
    ("财经新闻", _group_news),
    ("LLM 章节", _group_llm),
)


def assemble_sections(state: HtmlAssembly) -> HtmlAssembly:
    """按 :data:`SECTION_BUILDERS` 顺序执行区块装配。"""
    for _name, builder in SECTION_BUILDERS:
        builder(state)
    return state


__all__ = ["HtmlAssembly", "SECTION_BUILDERS", "SectionBindings", "assemble_sections"]
