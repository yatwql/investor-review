"""HTML 模板上下文契约（`report/html_template_context.py` + `_render_template`）。

模板渲染的关键字形参与 `render(...)` 关键字表收敛成一个 dataclass：
**字段名即模板变量名**，渲染侧只做 `render(**asdict(ctx))`。本用例锁三件事：

  1. 字段集合与拆分前 `render(...)` 的 94 个关键字逐一对应且顺序稳定（增删改名必须先改契约）；
  2. 渲染时传给模板的键集合 == 上下文字段集合（不多不少，防漏传/夹带）；
  3. 章节顺序 CSS 仍由 `section_numbers` 注入（上下文对象不得吞掉这一步）。
"""

from __future__ import annotations

import dataclasses

from unittest.mock import MagicMock, patch

import pytest

from src.python.report import html_writer as hw

from src.python.report.html_template_context import TemplateContext

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

#: 拆分前 `render(...)` 的关键字序列（模板变量契约；顺序即契约）
TEMPLATE_VARIABLES: tuple[str, ...] = (
    "flow_display",
    "purchase_status_display",
    "section_groups",
    "anon_code_map",
    "llm_supported_sections",
    "valuation_enabled",
    "valuation_real_basis",
    "market_temperature",
    "now",
    "today",
    "trading_day",
    "total_mv",
    "total_cost",
    "total_profit",
    "total_profit_rate",
    "total_today_profit",
    "today_profit_rate",
    "categories",
    "update_status",
    "a_indices",
    "us_indices",
    "accounts",
    "account_totals",
    "cat_data",
    "penetration",
    "perf_data",
    "candidate_data",
    "news_data",
    "news_llm_meta",
    "has_llm_analysis",
    "manager_analysis",
    "overlap_matrix",
    "concentration_analysis",
    "style_analysis",
    "llm_enabled",
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "self_review_block",
    "llm_session_usage",
    "module_labels",
    "module_disabled",
    "llm_module_info",
    "llm_endpoint",
    "cache_stats",
    "app_name",
    "app_version",
    "debate_mode_label",
    "debate_info",
    "debate_mode_combination",
    "enabled_experiments",
    "report_qa_enabled",
    "section_order",
    "section_numbers",
    "section_visible_dict",
    "section_visible",
    "data_status_summary",
    "degradation_line",
    "data_status_penetration",
    "data_status_perf",
    "data_status_category",
    "history_data",
    "data_status_history",
    "data_source_matrix",
    "data_source_catalog",
    "report_year",
    "data_unavailable",
    "chart_datasets",
    "style_factor_data",
    "factor_catalog_data",
    "factor_names",
    "industry_beta",
    "position_relationship_data",
    "evolution_data",
    "evolution_chart_data",
    "drawdown_min_span",
    "position_status",
    "data_freshness",
    "action_data",
    "decision_basis_data",
    "prosperity_framework_data",
    "market_sentiment_data",
    "crisis_annotation_data",
    "risk_adjusted_excess_data",
    "tail_risk_data",
    "snapshot_diff_data",
    "decision_review_data",
    "holding_change_view",
    "event_impact_view",
    "schedule_replay_view",
    "financial_report_digest_data",
    "financial_indicator_data",
    "summary_highlights_data",
)


class TestFieldContract:
    def test_field_names_match_template_variables(self):
        assert tuple(f.name for f in dataclasses.fields(TemplateContext)) == TEMPLATE_VARIABLES

    def test_field_names_are_unique(self):
        names = [f.name for f in dataclasses.fields(TemplateContext)]
        assert len(names) == len(set(names))

    def test_all_fields_default_to_none(self):
        ctx = TemplateContext()
        assert all(getattr(ctx, name) is None for name in TEMPLATE_VARIABLES)


class TestRenderForwarding:
    def _capture_render_keys(self, context: TemplateContext) -> dict:
        captured: dict = {}

        def _fake_render(**kwargs):
            captured.update(kwargs)
            return "RENDERED"

        template = MagicMock()
        template.render.side_effect = _fake_render
        with patch.object(hw._ENV, "get_template", return_value=template):
            html = hw._render_template(context)
        assert html == "RENDERED"
        return captured

    def test_render_receives_exactly_context_fields(self):
        context = TemplateContext()
        context.now = "2026-01-02 03:04:05"  # 抽取一个字段验证透传
        captured = self._capture_render_keys(context)

        assert set(captured) == set(TEMPLATE_VARIABLES)
        assert captured["now"] == "2026-01-02 03:04:05"

    def test_section_order_css_still_injected(self):
        """章节顺序 CSS 仍按 `section_numbers` 注入（占位符被替换，其余字节不变）。"""
        context = TemplateContext()
        context.section_numbers = {"summary": 1}

        with patch.object(
            hw._ENV,
            "get_template",
            return_value=MagicMock(render=MagicMock(return_value=f"X{hw._SECTION_ORDER_PLACEHOLDER}Y")),
        ):
            html = hw._render_template(context)

        assert html == "X<style>#sec-summary{order:1}</style>Y"

    def test_no_injection_without_section_numbers(self):
        context = TemplateContext()
        context.section_numbers = {}
        with patch.object(
            hw._ENV,
            "get_template",
            return_value=MagicMock(render=MagicMock(return_value=f"X{hw._SECTION_ORDER_PLACEHOLDER}Y")),
        ):
            assert hw._render_template(context) == f"X{hw._SECTION_ORDER_PLACEHOLDER}Y"
