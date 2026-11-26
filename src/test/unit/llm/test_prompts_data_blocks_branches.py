# -*- coding: utf-8 -*-
"""数据块提示词段落（prompts_data_blocks）：环比明细、降级清单、归因/概念/再平衡、
竞争语境与数值守卫。

锁定「有数据才出行、无数据出固定空态文案」的契约：这些段落直接进 LLM 提示词，
空态文案变了会改变缓存指纹，行内容变了会改变模型读到的口径。

归因与再平衡的计算侧经替身注入（本文件只验格式化段落）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.llm import prompts_data_blocks as blocks

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestDiffPipelineBlock:
    def test_lists_added_removed_increased_decreased(self):
        pipeline = {
            "diff": {
                "days_since_last_report": 7,
                "baseline_generated_at": "2026-10-22 20:00",
                "baseline_trading_day": "2026-10-22",
                "total_value_diff": 12345.0,
                "total_value_diff_pct": 1.234,
                "total_pnl_diff": -600.0,
                "added": [{"name": "新增甲", "code": "600900"}, {"name": "新增乙", "code": "000001"}],
                "removed": [{"name": "清仓丙", "code": "601398"}],
                "increased": [{"name": "加仓丁", "shares_diff": 100.0}],
                "decreased": [{"name": "减仓戊", "shares_diff": -200.0}],
            }
        }
        text = blocks._build_difpipeline_data_block(pipeline)
        assert "【环比对比】距上次报告 7 天" in text
        assert "【对比基准】交易日 2026-10-22，报告生成于 2026-10-22 20:00" in text
        assert "总市值变化: +12,345 (+1.23%)" in text
        assert "总盈亏变化: -600" in text
        assert "新增持仓: " in text and "新增乙" in text
        assert text.count("清仓: ") == 1
        assert "加仓: 加仓丁+100份" in text
        assert "减仓: 减仓戊-200份" in text

    def test_no_diff_returns_empty(self):
        assert blocks._build_difpipeline_data_block(None) == ""
        assert blocks._build_difpipeline_data_block({"diff": "not-a-dict"}) == ""


class TestDegradationBlock:
    def test_no_degraded_events_returns_empty(self):
        assert blocks._build_data_degradation_block({"data_degradation": [{"degraded": False}]}) == ""

    def test_degraded_events_listed_without_counts(self):
        pipeline = {
            "data_degradation": [
                {"degraded": True, "source_key": "industry", "tier": "T3", "failure_type": "unreachable", "count": 4},
                {"degraded": False, "source_key": "news", "tier": "T4", "failure_type": "empty"},
            ]
        }
        text = blocks._build_data_degradation_block(pipeline)
        assert "- industry: T3 降级 (unreachable)" in text
        assert "count" not in text
        assert "news" not in text
        assert text.endswith("分析建议时请考虑数据缺失的影响）")


class TestProfitAttributionBlock:
    def _data(self, **overrides):
        data = {
            "大类贡献": [{"asset_class": "股票", "contribution_pp": 1.5}],
            "盈利来源": [{"name": "长江电力", "contribution_pp": 2.0}],
            "亏损来源": [{"name": "某某基金", "contribution_pp": -1.0}],
            "pos_total": 20000.0,
            "neg_total": -5000.0,
        }
        data.update(overrides)
        return data

    def test_mixed_profit_and_loss(self):
        with patch("src.python.analysis.return_attribution.compute_return_attribution", return_value=self._data()):
            text = blocks._build_profit_attribution_block([{"code": "600900"}])
        assert "大类贡献: 股票(+1.5pp)" in text
        assert "主要盈利来源: 长江电力(+2.0pp)" in text
        assert "主要亏损来源: 某某基金(-1.0pp)" in text
        assert "盈利品种合计 +2.0万，亏损品种合计 -5,000（净1.5万）" in text

    def test_all_loss(self):
        data = self._data(pos_total=0.0, neg_total=-80000.0, 盈利来源=[])
        with patch("src.python.analysis.return_attribution.compute_return_attribution", return_value=data):
            text = blocks._build_profit_attribution_block([{"code": "600900"}])
        assert "全部品种亏损，合计 -8.0万" in text
        assert "主要盈利来源" not in text


class TestConceptSectorBlock:
    def test_high_concentration(self):
        assets = [{"mv": 900.0, "concepts": [" 水电 "]}, {"mv": 100.0, "concepts": ["核电"]}]
        text = blocks._build_concept_sector_block(assets)
        assert text.startswith("【概念板块分布】")
        assert "- 水电: 900 (90.0%)" in text  # 概念名首尾空白被归一
        assert "集中度判断: 高" in text

    def test_medium_and_low_concentration(self):
        medium = [{"mv": 400.0, "concepts": ["甲"]}, {"mv": 80.0, "concepts": ["乙"]}]
        medium += [{"mv": 75.0, "concepts": [f"尾部{i}"]} for i in range(7)]
        # top1 40%（不超 40）+ top3 55%（超 50 未超 70）→ 中
        assert "集中度判断: 中" in blocks._build_concept_sector_block(medium)

        low = [{"mv": 100.0, "concepts": [f"概念{i}"]} for i in range(8)]
        assert "集中度判断: 低" in blocks._build_concept_sector_block(low)  # top1 12.5% / top3 37.5%

    def test_empty_and_non_string_concepts(self):
        assert blocks._build_concept_sector_block(None) == "暂无概念板块数据"
        assert blocks._build_concept_sector_block([{"mv": 10.0, "concepts": [1, None, "  "]}]) == "部分品种无概念分类"


class TestRebalanceBlock:
    def test_summary_and_threshold_lines(self):
        signals = [
            {"summary": "已超限多时", "message": "某基金占比过高"},
            {"name": "长江电力", "code": "600900", "weight": 0.25, "threshold": 0.2, "action": "建议减仓"},
        ]
        with patch("src.python.analysis.simple_rebalance.compute_simple_rebalance_signals", return_value=signals):
            text = blocks._build_rebalance_block([{"code": "600900"}], 100000.0)
        assert "⚠ 某基金占比过高" in text
        assert "持仓占比 25.0%，超出建议上限 20%，建议减仓" in text


class TestCompetitiveContextBlock:
    def test_skips_index_without_change_pct(self):
        a_indices = {"sh000300": {"change_pct": 0.5}, "sh000905": {}, "sh000012": {"change_pct": None}}
        text = blocks._build_competitive_context_block(a_indices, 100000.0, 1200.0)
        assert "组合 +1.20% vs 沪深300 +0.50%" in text
        assert "中证500" not in text
        assert "相对沪深300 跑赢 0.70%" in text

    def test_metrics_wide_vol_and_drawdown_scales(self):
        metrics = {
            "sharpe_ratio": 1.234,
            "annualized_volatility": 18.5,  # >1 → 按百分数原样输出
            "max_drawdown": -0.085,  # 小数 → 百分比
            "calmar_ratio": float("nan"),  # 非有限 → 跳过
        }
        text = blocks._build_competitive_context_block(None, 0.0, 0.0, metrics=metrics)
        assert "夏普 1.23" in text
        assert "年化波动率 18.50%" in text
        assert "最大回撤 -8.5%" in text
        assert "卡玛" not in text

    def test_no_data_returns_fixed_text(self):
        assert blocks._build_competitive_context_block(None, 0.0, 0.0) == "暂无足够历史数据进行竞争语境对比"


class TestValidNumber:
    def test_rejects_none_and_strings(self):
        assert blocks._is_valid_number(None) is False
        assert blocks._is_valid_number("1.5") is False
        assert blocks._is_valid_number(float("inf")) is False
        assert blocks._is_valid_number(0.0) is True
