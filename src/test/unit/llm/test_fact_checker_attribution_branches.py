"""事实核对「主体归因」残余分支：短尾候选择优与短核心名跳过。

覆盖目标：
  - `_match_descriptive_tail`：LLM 只写「核心名+数字代号」（"华安纳斯达克100"）时
    由短尾候选命中持仓，避免回退全局最近邻误路由
  - `_subject_spans` / `_locate_subject_in`：核心名不足 2 字（如纯类型名 "ETF"）的
    持仓不参与简称匹配——短核心名会把句中任意同字串当主体，属噪声来源
  - `_claimed_code`：表格声称为所在行内首见的代码之后 / 行内确无代码时，分别按
    「行内就近」「整句就近」兜底
"""

from __future__ import annotations

import re

import pytest

from src.python.llm.fact_checker._ranking import _claimed_code
from src.python.llm.fact_checker._utils import (
    _locate_subject_in,
    _match_descriptive_tail,
    _subject_spans,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_FULL_NAME = "华安纳斯达克100ETF联接基金A"


# ── 短尾候选（核心名 + 数字代号）────────────────────────────


def test_descriptive_tail_matches_core_name_with_numeric_alias():
    """「华安纳斯达克100」缩写 → 短尾候选命中持仓全名，不落空到全局最近邻。"""
    match = _match_descriptive_tail("华安纳斯达克100 占比 11.3%", {_FULL_NAME: "040046"}, 0)

    assert match is not None, "「核心名+数字代号」缩写须能归因到持仓"
    assert match[0] == "040046"


def test_descriptive_tail_without_alias_returns_none():
    """句中只出现泛词（无「核心名+数字」或完整候选）→ 不归因（防误路由）。"""
    assert _match_descriptive_tail("纳斯达克指数整体上涨", {_FULL_NAME: "040046"}, 0) is None


# ── 短核心名不参与简称匹配 ─────────────────────────────────


def test_subject_spans_skips_holding_with_too_short_core_name():
    """核心名 <2 字的持仓不进简称归一匹配：span 只应来自正常持仓。"""
    text = "纳指联接 016055 +18.66%"
    name_to_code = {"ETF": "000001", "华安纳斯达克100ETF联接基金A": "016055"}

    spans = _subject_spans(text, {"016055"}, name_to_code)

    codes = {code for _start, _end, code in spans}
    assert codes == {"016055"}, "短核心名持仓（ETF）不得产出主体 span"


def test_locate_subject_skips_holding_with_too_short_core_name():
    """同一守卫在 `_locate_subject_in`：简称命中的仍是正常持仓，短核心名被跳过。"""
    sentence = "纳指联接 016055 +18.66%"
    name_to_code = {"ETF": "000001", "华安纳斯达克100ETF联接基金A": "016055"}

    assert _locate_subject_in(sentence, {"016055"}, name_to_code, anchor=sentence.index("+18")) == "016055"


# ── 排名声称的表格归因 ─────────────────────────────────────


def _claim(sentence: str) -> re.Match:
    match = re.search("第一重仓", sentence)
    assert match is not None, "前置：构造句须含声称词"
    return match


def test_claimed_code_uses_row_scope_when_code_follows_claim():
    """表格行内代码在声称词**之后** → 行内就近兜底（前段无代码）取该代码。"""
    sentence = "|| 第一重仓是 040046 华安纳斯达克100ETF联接A"

    assert _claimed_code(sentence, _claim(sentence)) == "040046"


def test_claimed_code_falls_back_to_sentence_when_row_has_no_code():
    """表格行内确无代码 → 退回整句就近（防漏检），仍归到同句代码。"""
    sentence = "040046 华安纳斯达克100ETF联接A || 已是第一重仓"

    assert _claimed_code(sentence, _claim(sentence)) == "040046"
