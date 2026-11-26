"""自动修正通道的守卫分支单元测试（fact_checker/_corrections.py）。

锁住的契约：
  - 修正计数：本次零处修正时不落任何计数器键（不污染跨期对拍分母）
  - 数值改写：同值异义（一个错值对应多个正确值）整值跳过；判定句已不在正文
    （被别的修正改掉）同样跳过；改写会产出畸形数值时整批放弃并清空已记录项
  - 代码纠正候选：空文本/无持仓明细/持仓无代码 → 无候选；
    权重缺失、错码后无权重声称词、百分比不唯一 → 均不纠正；
    空纠正表与「错码已不在正文」两种情况下正文原样返回
"""

from __future__ import annotations

import re

import pytest

from src.python.llm.fact_checker import _corrections as corr

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_HOLDINGS: list[dict] = [
    {"name": "建设银行", "code": "601939", "market_value": 100.0, "profit_rate": 10.0},
    {"name": "长江电力", "code": "600900", "market_value": 100.0, "profit_rate": 5.0},
]


class TestNoteAutoCorrection:
    def test_zero_corrections_records_nothing(self):
        corr.reset_auto_correction_counts()
        try:
            corr.note_auto_correction("智囊团深度复盘", 0, 0)
            assert corr.auto_correction_counts() == {}
        finally:
            corr.reset_auto_correction_counts()


class TestNumericalCorrectionGuards:
    def test_same_wrong_value_with_two_targets_is_skipped(self):
        html = "<p>组合收益 3.70%。</p>"
        corrections = [("3.70", "20.0", "组合收益 3.70%。"), ("3.70", "5.0", "组合收益 3.70%。")]

        assert corr.apply_numerical_corrections(html, corrections) == html

    def test_sentence_absent_from_content_is_skipped(self):
        html = "<p>组合收益 3.70%。</p>"
        corrections = [("3.70", "20.0", "另一句话里的 3.70%。")]

        assert corr.apply_numerical_corrections(html, corrections) == html

    def test_malformed_result_discards_whole_batch(self, monkeypatch):
        """改写结果出现畸形数值 → 整批不写回，且已记录项一并清空。"""
        html = "<p>组合收益 3.70%。</p>"
        monkeypatch.setattr(corr, "_MALFORMED_NUMBER_RE", re.compile(r"MALFORMED"))
        applied: list[str] = []

        result = corr.apply_numerical_corrections(html, [("3.70", "MALFORMED", "组合收益 3.70%。")], applied)

        assert result == html, "保留原文比写入畸形值安全"
        assert applied == [], "放弃写回时必须清空「已修正明细」"


class TestCodeCorrectionCandidates:
    def test_empty_text_or_missing_holdings_yields_no_candidate(self):
        assert corr.detect_code_corrections("", _HOLDINGS) == []
        assert corr.detect_code_corrections("601938 规模达 50.0%", []) == []

    def test_holdings_without_codes_yield_no_candidate(self):
        assert corr.detect_code_corrections("601938 规模达 50.0%", [{"name": "建设银行", "code": ""}]) == []

    def test_missing_weight_evidence_yields_no_candidate(self):
        holdings = [{"name": "建设银行", "code": "601939", "market_value": 0.0}]

        assert corr.detect_code_corrections("601938 规模达 100.0%", holdings) == []

    def test_missing_weight_claim_keywords_yields_no_candidate(self):
        assert corr.detect_code_corrections("601938 收益率 +5.0%", _HOLDINGS) == []

    def test_multiple_percentages_in_window_yields_no_candidate(self):
        assert corr.detect_code_corrections("601938占比 10.2% 到 12.3%", _HOLDINGS) == []


class TestCodeCorrectionApply:
    def test_empty_correction_list_returns_content_unchanged(self):
        html = "<p>601938 规模达 50.0%</p>"

        assert corr.apply_code_corrections(html, []) == html

    def test_bad_code_absent_from_content_is_skipped(self):
        html = "<p>601939 规模达 50.0%</p>"

        assert corr.apply_code_corrections(html, [("601938", "601939", "s", "r")]) == html
