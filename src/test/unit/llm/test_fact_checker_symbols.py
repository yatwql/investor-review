"""test_fact_checker 兄弟分片（symbols）：代码/名称存在性校验。"""

from __future__ import annotations
import pytest
from src.python.llm.fact_checker import (
    check_symbol_existence,
)

# 夹具按名注入（由测试签名消费），代码里无引用

# ruff: noqa: F811 — 参数与模块级夹具同名（pytest 按名注入），非重定义
from src.test.unit.llm.test_fact_checker import (
    sample_holdings,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.llm,
]


class TestCheckSymbolExistence:
    """品种存在性校验测试。"""

    def test_empty_text(self):
        """空文本 → 无检查项。"""
        issues, checked, passed, suggestions = check_symbol_existence("", None)
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert suggestions == []

    def test_no_codes_mentioned(self, sample_holdings):
        """无代码提及 → 无检查项。"""
        text = "本季度组合以消费和金融板块为主。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert suggestions == []

    def test_all_codes_in_holdings(self, sample_holdings):
        """提及的代码全部在持仓中 → 全部通过。"""
        text = "贵州茅台（600519）本季度表现突出。招商银行（600036）保持稳定。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert checked == 2
        assert passed == 2
        assert issues == []
        assert suggestions == []

    def test_index_code_skipped(self, sample_holdings):
        """常见指数代码（沪深300:000300）跳过大盘指数。"""
        text = "组合收益在本季度跑赢沪深300（000300）指数。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []

    def test_code_not_in_holdings(self, sample_holdings):
        """提及的代码不在持仓中 → 告警。"""
        text = "中国平安（601318）作为金融龙头值得关注。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "601318" in issues[0]
        assert "不在当前持仓" in issues[0]
        assert suggestions == []

    def test_suggestion_context_does_not_alert(self, sample_holdings):
        """建议语境提及的非持仓代码 → 归入 suggestion 而非 issues。"""
        text = "建议关注511010国债ETF作为配置补充"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert issues == [], "建议语境不应进入幻觉告警"
        assert len(suggestions) == 1
        assert "511010" in suggestions[0]

    def test_suggestion_keywords_disabled(self, sample_holdings):
        """suggestion_keywords=None 时建议语境也告警。"""
        text = "建议关注511010国债ETF"
        issues, checked, passed, suggestions = check_symbol_existence(
            text,
            sample_holdings,
            suggestion_keywords=None,
        )
        assert len(issues) == 1, "关闭建议检测后应正常告警"
        assert suggestions == []

    def test_mixed_valid_and_invalid(self, sample_holdings):
        """混合持仓中和非持仓代码。"""
        text = "贵州茅台（600519）和宁德时代（300750）表现良好。恒瑞医药（600276）需关注。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert checked == 3
        assert passed == 2
        assert len(issues) == 1
        assert "600276" in issues[0]
        assert suggestions == []

    def test_penetration_codes_as_extra_valid(self, sample_holdings):
        """穿透 TOP10 代码作为 extra_valid_codes → 不报"不在当前持仓中"。

        阳光电源（300274）非直接持仓但属组合穿透范围，智囊团/持仓体检引用
        其代码时传入 extra_valid_codes 视为有效。
        """
        text = "宁德时代（300750）与阳光电源（300274）是组合穿透中的新能源核心持仓。"
        issues, checked, passed, suggestions = check_symbol_existence(
            text,
            sample_holdings,
            extra_valid_codes={"300274"},
        )
        assert checked == 2
        assert passed == 2  # 300750 持仓 + 300274 穿透有效
        assert issues == []
        assert suggestions == []

    def test_penetration_code_alerts_without_extra(self, sample_holdings):
        """未传 extra_valid_codes 时穿透代码仍告警（参数是唯一豁免来源）。"""
        text = "阳光电源（300274）作为组合穿透核心持仓值得关注。"
        issues, checked, passed, suggestions = check_symbol_existence(text, sample_holdings)
        assert len(issues) == 1
        assert "300274" in issues[0]

    def test_holdings_none(self):
        """holdings_details 为 None → 直接返回。"""
        issues, checked, passed, suggestions = check_symbol_existence("代码 600519 表现良好", None)
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert suggestions == []

    def test_holdings_empty_list(self):
        """holdings_details 为空列表 → 直接返回。"""
        issues, checked, passed, suggestions = check_symbol_existence("代码 600519 表现良好", [])
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert suggestions == []
