"""提示词构建的可选段落与降级分支单元测试（prompts_action / prompts_tables）。

锁住的契约：
  - 量化指标表：夏普带置信度、卡玛、HHI 等效只数、换手率、Beta 描述；
    缺 HHI 时回落到 `--`（不抛）
  - 国别分布：非 CNY/HKD/USD 的币种归「其他」（不丢市值）
  - 代码白名单：明细市值全为 0 时返回空串（不输出「共 0 个：」的退化块）
  - 智囊团提示词：情景分析块与口径修正块有内容时才追加；辩论条件情景/集中度
    问答的配置读取失败各按默认阈值继续（不阻断提示词构建）
  - 体检提示词：有降级事件时追加数据质量降级段落
  - 综合提示词：条件情景与集中度问答的配置读取失败均不阻断
"""

from __future__ import annotations

import pytest

from src.python.llm import prompts_action as action
from src.python.llm import prompts_tables as tables

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_DEGRADED_PIPELINE: dict = {
    "data_degradation": [
        {"degraded": True, "source_key": "fund_holdings", "tier": "L2", "failure_type": "timeout"},
    ]
}


def _expert_review(**kwargs) -> str:
    params: dict = {
        "total_mv": 100_000.0,
        "total_cost": 90_000.0,
        "total_profit": 10_000.0,
        "total_today_profit": 500.0,
        "holdings_count": 2,
        "categories": {"股票": 2},
        "holdings_details": [
            {"name": "建设银行", "code": "601939", "market_value": 60_000.0, "cost": 50_000.0},
            {"name": "长江电力", "code": "600900", "market_value": 40_000.0, "cost": 40_000.0},
        ],
    }
    params.update(kwargs)
    return action._build_expert_review_prompt(**params)


def _unreadable_config():
    raise RuntimeError("配置层不可用")


class TestMetricsTableBlock:
    def test_optional_metrics_rendered_when_present(self):
        block = tables._build_metrics_table_block(
            {
                "sharpe_ratio": 1.23,
                "sharpe_confidence": "high",
                "calmar_ratio": 0.85,
                "hhi": 0.15,
                "hhi_equivalent": 6.7,
                "turnover_rate": 0.32,
                "portfolio_beta": 1.35,
            }
        )

        assert "夏普比率: 1.23（置信度: high）" in block
        assert "卡玛比率: 0.85" in block
        assert "等效7只品种" in block
        assert "区间换手率: 32.0%" in block
        assert "组合Beta: 1.35（偏高," in block

    def test_missing_hhi_renders_placeholder(self):
        block = tables._build_metrics_table_block({"sharpe_ratio": None})

        assert "集中度(HHI): --" in block


class TestCountryExposure:
    def test_unknown_currency_grouped_as_other(self, monkeypatch):
        monkeypatch.setattr(tables, "get_currency_by_code", lambda _name, _code: "EUR")

        lines = tables._calc_country_exposure([{"name": "欧洲基金", "code": "000001", "market_value": 10_000.0}])

        assert any(line.startswith("其他:") for line in lines), "未知币种不得丢市值"


class TestCodeWhitelistBlock:
    def test_all_zero_market_value_yields_empty_block(self):
        holdings = [{"name": "建设银行", "code": "601939", "market_value": 0.0}]

        assert tables._build_code_whitelist_block(holdings, 100_000.0) == ""


class TestExpertReviewOptionalBlocks:
    def test_scenario_and_alignment_blocks_appended_when_present(self):
        prompt = _expert_review(
            metrics={
                "scenario_analysis": {"has_data": True, "beta": 1.1, "scenarios": []},
                "alignment_summary": "口径修正：费率影响 +0.12%",
            }
        )

        assert "【情景分析（Beta 置信区间传播）】" in prompt
        assert "口径修正：费率影响 +0.12%" in prompt

    def test_conditional_scenario_config_failure_skips_block(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", _unreadable_config)

        prompt = _expert_review(enable_conditional=True)

        assert "### 情景分析" not in prompt, "配置读取失败时按「无条件情景」跳过，不追加半成品段落"

    def test_concentration_qa_config_failure_uses_default_threshold(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", _unreadable_config)
        seen: dict = {}

        def _capture(_holdings, _total_mv, threshold=None, industry_concentration=None):
            seen["threshold"] = threshold
            return ""

        monkeypatch.setattr(action, "_build_concentration_qa_block", _capture)

        _expert_review(include_concentration_qa=True)

        assert seen["threshold"] == pytest.approx(0.20), "配置不可读时按默认集中度阈值继续"


class TestHealthCheckDegradationBlock:
    def test_degradation_events_appended_to_prompt(self):
        prompt = action._build_health_check_prompt(
            total_mv=100_000.0,
            total_cost=90_000.0,
            total_profit=10_000.0,
            total_today_profit=500.0,
            holdings_count=2,
            categories={"股票": 2},
            holdings_details=[{"name": "建设银行", "code": "601939", "market_value": 100_000.0}],
            pipeline_data=_DEGRADED_PIPELINE,
        )

        assert "【数据质量降级】" in prompt
        assert "fund_holdings: L2 降级 (timeout)" in prompt


class TestDebateSynthesisDegradations:
    def test_conditional_scenario_config_failure_does_not_break_prompt(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", _unreadable_config)

        prompt = action._build_debate_synthesis_prompt("白脸正文", "黑脸正文", enable_conditional=True)

        assert "白脸正文" in prompt and "### 情景分析" not in prompt

    def test_concentration_qa_config_failure_uses_default_threshold(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", _unreadable_config)
        seen: dict = {}

        def _capture(_holdings, _total_mv, threshold=None, industry_concentration=None):
            seen["threshold"] = threshold
            return "集中度问答引导正文"

        monkeypatch.setattr(action, "_build_concentration_qa_block", _capture)

        prompt = action._build_debate_synthesis_prompt("白脸", "黑脸", include_concentration_qa=True)

        assert seen["threshold"] == pytest.approx(0.20)
        assert "集中度问答引导正文" in prompt
