"""HTML 渲染前置装配：面板视图 / 数据源状态 / 渲染上下文。

`write_html_report` 需要的派生数据都在此一次备好（视图拼装 → 数据源状态 → 章节可见性与掩码），
与模板渲染分开：这些量各自独立、可单测，混在写出函数里只会把它撑成一张长赋值表。

入参按**来源域**分组（`_VisibilityInputs` / `_DataSourceInputs`）：组的边界即派生量的边界，
新增一项可见性输入只需在组里加字段、不必同时改签名与调用点顺序；`details`（渲染点掩码的
首选来源，缺席时回退 `data_source.holdings`）单独入参，因为它不是任一组的前置事实。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("invest")


def _build_panel_views(
    holding_change_data: Any, event_impact_data: Any, schedule_replay_data: Any
) -> tuple[Any, Any, Any]:
    """装配三个面板视图（持仓变动 / 事件窗 / 纪律回放），契约缺席时为 ``None``。

    与 Excel 端消费同一份预格式化字符串（双端单源）；键缺席 → ``None`` → 章内区块隐藏，
    逐字节回退既有输出。
    """
    holding_change_view = None
    if holding_change_data:
        from src.python.report.holding_change_panel import build_holding_change_view

        holding_change_view = build_holding_change_view(holding_change_data)
    # 事件窗对照视图（双端单源）：与 Excel 新闻页签尾部区块消费同一份预格式化字符串；
    # 契约缺席（开关关闭/未注入）→ None → 新闻章内区块隐藏，逐字节回退既有输出
    event_impact_view = None
    if event_impact_data:
        from src.python.report.event_impact_panel import build_event_impact_view

        event_impact_view = build_event_impact_view(event_impact_data)
    # 调仓纪律回放视图（双端单源）：与 Excel 页签消费同一份预格式化字符串；
    # 契约缺席（开关关闭/未注入）→ None → 章隐藏，逐字节回退既有输出
    schedule_replay_view = None
    if schedule_replay_data:
        from src.python.report.schedule_replay_panel import build_schedule_replay_view

        schedule_replay_view = build_schedule_replay_view(schedule_replay_data)
    return holding_change_view, event_impact_view, schedule_replay_view


@dataclass
class _VisibilityInputs:
    """章节可见性装配的入参（章节序号 / 可见性 / LLM 模块禁用判定的全部前置事实）。

    字段即 ``_compute_section_visibility`` 的入参面（除 ``order`` 外均原样透传）：
    改签名时只需维护「组 → 调用点」一处映射，调用方不再逐参对齐位置。
    """

    order: list
    manager_analysis: Any
    overlap_matrix: Any
    concentration_analysis: Any
    style_analysis: Any
    include_news: bool
    llm_enabled_flag: bool
    enable_llm: bool
    enable_news: bool
    enable_fund_deep_analysis: bool
    enable_history: bool
    enable_portfolio_evolution: bool
    enable_action: bool
    style_factor_data: Any
    position_relationship_data: Any
    evolution_data: Any
    holding_change_data: Any
    schedule_replay_data: Any
    enable_fundamental_snapshot: bool
    financial_report_digest_data: Any
    financial_indicator_data: Any


@dataclass
class _DataSourceInputs:
    """数据源状态装配的入参（摘要四元组 / 历史状态 / 可用性矩阵与说明表）。"""

    a_indices: Any
    us_indices: Any
    penetration: Any
    penetration_profit_ok: bool
    penetration_dividend_ok: bool
    perf_data: Any
    holdings: list
    cat_dividend_ok: bool
    history_data: Any


@dataclass
class _DataSourceBundle:
    """数据状态摘要 + 历史走势状态 + 数据源可用性矩阵/说明表（渲染期一次性装配）。"""

    status: tuple[Any, Any, Any, Any]
    history: Any
    matrix: Any
    catalog: Any


def _build_data_source_bundle(inputs: _DataSourceInputs) -> _DataSourceBundle:
    """装配数据源状态摘要、历史走势数据状态与可用性矩阵（HTML 数据状态块消费）。"""
    from src.python.report.html_writer_status import _build_data_status_sections, _build_history_data_status

    # ── 10b) 数据源状态摘要 ──
    (data_status_summary, data_status_penetration, data_status_perf, data_status_category) = (
        _build_data_status_sections(
            inputs.a_indices,
            inputs.us_indices,
            inputs.penetration,
            inputs.penetration_profit_ok,
            inputs.penetration_dividend_ok,
            inputs.perf_data,
            inputs.holdings,
            inputs.cat_dividend_ok,
        )
    )

    # ── 10c) 组合历史走势数据状态 ──
    data_status_history = _build_history_data_status(inputs.history_data)

    # ── 10d) 数据源可用性矩阵 ──
    from src.python.report.data_source_matrix import build_data_source_catalog, build_data_source_matrix

    data_source_matrix = build_data_source_matrix()
    data_source_catalog = build_data_source_catalog()
    return _DataSourceBundle(
        status=(data_status_summary, data_status_penetration, data_status_perf, data_status_category),
        history=data_status_history,
        matrix=data_source_matrix,
        catalog=data_source_catalog,
    )


@dataclass
class _RenderContext:
    """渲染前一次性算好的派生上下文（可见性/数据源状态/因子名/代码掩码）。"""

    section_numbers: dict
    section_visible_dict: dict
    sv_fn: Any
    status: tuple[Any, Any, Any, Any]
    data_status_history: Any
    data_source_matrix: Any
    data_source_catalog: Any
    factor_names: dict
    code_display_map: dict
    degradation_line: str


def _prepare_render_context(
    *,
    visibility: _VisibilityInputs,
    data_source: _DataSourceInputs,
    details: Any = None,
) -> _RenderContext:
    """装配渲染前置上下文：章节序号/可见性、数据源状态、因子名映射、代码掩码。

    这些量都在「渲染之前」一次算好且互不依赖输出顺序，集中在此以免主流程被
    25+ 个装饰性赋值切碎；任一环节失败都按原语义降级（空映射/空集）。

    Args:
        visibility: 可见性域入参（章节序号 / 各开关 / 契约载体）。
        data_source: 数据源域入参（指数 / 穿透 / 业绩 / 历史走势）。
        details: 代码掩码的首选来源；``None`` 时回退 ``data_source.holdings``
            （与掩码构造的历史口径一致：明细缺位时按持仓行折叠代码）。

    Returns:
        ``_RenderContext``：九项派生量一次装齐。
    """
    from src.python.report.html_writer_nav import _compute_section_visibility

    from src.python.llm.skeleton import get_llm_chapter_disabled

    llm_module_disabled = get_llm_chapter_disabled() if visibility.enable_llm else None
    section_numbers, section_visible_dict, _sv_fn = _compute_section_visibility(
        visibility.order,
        visibility.manager_analysis,
        visibility.overlap_matrix,
        visibility.concentration_analysis,
        visibility.style_analysis,
        visibility.include_news,
        visibility.llm_enabled_flag,
        llm_module_disabled=llm_module_disabled,
        enable_news=visibility.enable_news,
        enable_fund_deep_analysis=visibility.enable_fund_deep_analysis,
        enable_history=visibility.enable_history,
        enable_portfolio_evolution=visibility.enable_portfolio_evolution,
        enable_action=visibility.enable_action,
        enable_llm=visibility.enable_llm,
        style_factor_data=visibility.style_factor_data,
        position_relationship_data=visibility.position_relationship_data,
        evolution_data=visibility.evolution_data,
        holding_change_data=visibility.holding_change_data,
        schedule_replay_data=visibility.schedule_replay_data,
        enable_fundamental_snapshot=visibility.enable_fundamental_snapshot,
        financial_report_digest_data=visibility.financial_report_digest_data,
        financial_indicator_data=visibility.financial_indicator_data,
    )

    _ds = _build_data_source_bundle(data_source)
    data_status_history = _ds.history
    data_source_matrix, data_source_catalog = _ds.matrix, _ds.catalog

    # 因子中文名映射（单一数据源：analysis 层常量，经 context 传递）
    _factor_names: dict = {}
    if visibility.style_factor_data:
        try:
            from src.python.analysis.style_factor_regression import FACTOR_NAMES

            _factor_names = FACTOR_NAMES
        except Exception:  # noqa: BLE001 — 因子名映射缺失只影响因子名回显，不阻断渲染
            logger.debug("[html_context] 因子中文名映射不可用，按原样回显因子键", exc_info=True)
            _factor_names = {}

    # 匿名化：代码列渲染点掩码映射（真码 → 显示掩码）。渲染前一次性构造，
    # 经模板全局变量注入，各章节以 {{ x | anon_code }} 精确键控折叠代码。
    from src.python.config.anonymizer import build_code_display_map, get_anonymization_mode

    _mask_source = details if details is not None else data_source.holdings
    _code_display_map = build_code_display_map(_mask_source, get_anonymization_mode())
    # 本轮降级汇总（无降级时为空串 → 模板不出该行，产物逐字节不变）
    from src.python.core.degradation import report_degradation_summary

    _degradation = report_degradation_summary()
    return _RenderContext(
        section_numbers=section_numbers,
        section_visible_dict=section_visible_dict,
        sv_fn=_sv_fn,
        status=_ds.status,
        data_status_history=data_status_history,
        data_source_matrix=data_source_matrix,
        data_source_catalog=data_source_catalog,
        factor_names=_factor_names,
        code_display_map=_code_display_map,
        degradation_line=str(_degradation.get("text") or ""),
    )
