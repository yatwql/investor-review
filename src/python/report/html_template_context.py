"""HTML 模板上下文 —— Jinja 模板变量契约的唯一载体。

`_render_template(ctx)` 只做 `render(**asdict(ctx))` + 章节顺序 CSS 注入；模板变量名即字段名，
顺序即契约。守卫：`src/test/unit/report/test_html_template_context.py` 锁定字段集合（与拆分前
`render(...)` 的 94 个关键字逐一对应），新增/改名模板变量必须先改本 dataclass。

不走 `dict` 而走 dataclass 的理由：字段名拼错、漏传、重名都能被静态检查与守卫用例拦住；
`**{...}` 字面量只能靠人眼核对。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TemplateContext:
    """模板变量集合（字段名 = 模板变量名；值域由调用方装配）。"""

    flow_display: Any = None
    purchase_status_display: Any = None
    section_groups: Any = None
    anon_code_map: Any = None
    llm_supported_sections: Any = None
    valuation_enabled: Any = None
    valuation_real_basis: Any = None
    market_temperature: Any = None
    now: Any = None
    today: Any = None
    trading_day: Any = None
    total_mv: Any = None
    total_cost: Any = None
    total_profit: Any = None
    total_profit_rate: Any = None
    total_today_profit: Any = None
    today_profit_rate: Any = None
    categories: Any = None
    update_status: Any = None
    a_indices: Any = None
    us_indices: Any = None
    accounts: Any = None
    account_totals: Any = None
    cat_data: Any = None
    penetration: Any = None
    perf_data: Any = None
    candidate_data: Any = None
    news_data: Any = None
    news_llm_meta: Any = None
    has_llm_analysis: Any = None
    manager_analysis: Any = None
    overlap_matrix: Any = None
    concentration_analysis: Any = None
    style_analysis: Any = None
    llm_enabled: Any = None
    global_macro: Any = None
    expert_review: Any = None
    health_check: Any = None
    penetration_deep: Any = None
    self_review_block: Any = None
    llm_session_usage: Any = None
    module_labels: Any = None
    module_disabled: Any = None
    llm_module_info: Any = None
    llm_endpoint: Any = None
    cache_stats: Any = None
    app_name: Any = None
    app_version: Any = None
    debate_mode_label: Any = None
    debate_info: Any = None
    debate_mode_combination: Any = None
    enabled_experiments: Any = None
    report_qa_enabled: Any = None
    section_order: Any = None
    section_numbers: Any = None
    section_visible_dict: Any = None
    section_visible: Any = None
    data_status_summary: Any = None
    degradation_line: Any = None
    data_status_penetration: Any = None
    data_status_perf: Any = None
    data_status_category: Any = None
    history_data: Any = None
    data_status_history: Any = None
    data_source_matrix: Any = None
    data_source_catalog: Any = None
    report_year: Any = None
    data_unavailable: Any = None
    chart_datasets: Any = None
    style_factor_data: Any = None
    factor_catalog_data: Any = None
    factor_names: Any = None
    industry_beta: Any = None
    position_relationship_data: Any = None
    evolution_data: Any = None
    evolution_chart_data: Any = None
    drawdown_min_span: Any = None
    position_status: Any = None
    data_freshness: Any = None
    action_data: Any = None
    decision_basis_data: Any = None
    prosperity_framework_data: Any = None
    market_sentiment_data: Any = None
    crisis_annotation_data: Any = None
    risk_adjusted_excess_data: Any = None
    tail_risk_data: Any = None
    snapshot_diff_data: Any = None
    decision_review_data: Any = None
    holding_change_view: Any = None
    event_impact_view: Any = None
    schedule_replay_view: Any = None
    financial_report_digest_data: Any = None
    financial_indicator_data: Any = None
    summary_highlights_data: Any = None
