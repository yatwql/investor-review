"""HTML 装配期分支：单图补齐失败降级、辩论模式覆盖模块状态标签。

`html_sections` 的两个分支只在这一层可见，渲染函数本身的用例覆盖不到：
  - 单张 Chart.js 数据集补齐失败 → 只跳过该图并告警，其余图照常覆盖
  - 辩论模式命中 → `expert_review` 模块的状态标签取辩论组合名（其余模块保持渲染层标签）
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.python.report.html_sections import HtmlAssembly, _group_llm, _group_penetration_and_perf

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _assembly(chart_datasets: dict | None, **overrides) -> HtmlAssembly:
    """装配期上下文（只填必需入参，其余取默认值）。"""
    kwargs: dict = {
        "holdings": [],
        "details": [],
        "prog": MagicMock(),
        "today_str": "2026-01-05",
        "trading_day": "2026-01-05",
        "a_indices": None,
        "us_indices": None,
        "include_news": False,
        "news_data": None,
        "news_top_count": 0,
        "news_llm_meta": None,
        "enable_llm": False,
        "llm_content": None,
        "chart_datasets": chart_datasets,
        "enable_fund_deep_analysis": False,
        "risk_adjusted_excess_data": None,
        "position_relationship_data": None,
        "debate_info": None,
    }
    kwargs.update(overrides)
    return HtmlAssembly(**kwargs)


class TestChartDatasetFillDegrade:
    """单图补齐失败：只该图缺席，其余图仍用权威数据重建。"""

    def test_failed_builder_skips_only_that_chart(self, caplog):
        state = _assembly({})
        penetration = {"items": [{"name": "股票", "value": 100.0}]}
        with (
            patch(
                "src.python.report.html_sections._render_penetration_section",
                return_value=(penetration, True, True),
            ),
            patch(
                "src.python.report.html_sections._render_fund_performance_section",
                return_value=([], None),
            ),
            patch(
                "src.python.report.chart_data_builder._build_category_doughnut_dataset",
                side_effect=RuntimeError("构建失败"),
            ),
            patch(
                "src.python.report.chart_data_builder._build_industry_bar_dataset",
                return_value={"labels": ["股票"], "datasets": []},
            ),
            patch(
                "src.python.report.chart_data_builder._build_penetration_bar_dataset",
                return_value={"labels": ["股票"], "datasets": []},
            ),
            patch(
                "src.python.report.chart_data_builder._build_excess_rolling_dataset",
                return_value={"labels": [], "datasets": []},
            ),
            patch(
                "src.python.report.chart_data_builder._build_corr_rolling_dataset",
                return_value={"labels": [], "datasets": []},
            ),
            caplog.at_level(logging.WARNING, logger="invest"),
        ):
            _group_penetration_and_perf(state)

        # 失败图不写入（保留调用侧原数据集，此处为空 dict 中的「缺席」）
        assert "category_doughnut" not in state.chart_datasets
        assert {"industry_bar", "penetration_bar", "excess_rolling", "corr_rolling"} <= set(state.chart_datasets)
        # 告警带图名，便于定位是哪张图的数据源出了问题
        assert "category_doughnut" in caplog.text
        assert "数据补齐失败" in caplog.text
        # 穿透数据仍按装配结果落到上下文
        assert state.penetration == penetration


class TestDebateModeOverridesReviewStatus:
    """辩论模式标签覆盖 expert_review 状态标签（其他模块不受影响）。"""

    def test_label_overrides_only_expert_review(self):
        modules = [
            {"key": "expert_review", "status": "success", "status_label": "生成"},
            {"key": "global_macro", "status": "cached", "status_label": "缓存"},
            {"key": "health_check", "status": "skipped", "status_label": "跳过"},
        ]
        state = _assembly({})
        with (
            patch(
                "src.python.report.html_sections._render_llm_content_section",
                return_value=(True, "宏观", "专家", "体检", "穿透"),
            ),
            patch(
                "src.python.report.html_sections._render_llm_module_info",
                return_value=(modules, "https://api.example.com", {}, None),
            ),
            patch(
                "src.python.report._debate_utils.detect_debate_mode",
                return_value=("辩论模式 · 三方", "global_macro+expert_review+health_check"),
            ),
        ):
            _group_llm(state)

        assert state.debate_mode_label == "辩论模式 · 三方"
        assert state.debate_mode_combination == "global_macro+expert_review+health_check"
        assert modules[0]["status_label"] == "辩论模式 · 三方"
        # 非 expert_review 模块的标签保持渲染层给出的值
        assert modules[1]["status_label"] == "缓存"
        assert modules[2]["status_label"] == "跳过"
