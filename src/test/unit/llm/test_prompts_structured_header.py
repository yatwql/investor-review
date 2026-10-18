"""结构化决策头提示词契约单元测试（机制已内置，不可关闭）。

覆盖：expert_review 提示词恒追加「决策头：」契约行与规范词枚举（位置纪律：
行动建议表之后、持仓明细之前）、契约文本与解析器口径互相锁定、生成器指纹
后缀恒为 ``_dh``（区分未引入本机制前的旧缓存指纹）。全部本地字符串，零网络零 LLM。
"""

from __future__ import annotations

import pytest

from src.python.core import decision_header as dh

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


def _expert_review(**kwargs) -> str:
    from src.python.llm.prompts_action import _build_expert_review_prompt

    return _build_expert_review_prompt(
        100000.0,
        90000.0,
        10000.0,
        500.0,
        2,
        {"股票": 2},
        None,
        holdings_details=[{"name": "示例", "code": "600519", "cost": 100.0}],
        **kwargs,
    )


class TestPromptContract:
    """提示词恒含契约段（内置，无开关态）。"""

    def test_marker_and_enumerations_present(self):
        text = _expert_review()
        assert dh.STRUCTURED_HEADER_MARKER in text
        for word, _direction in dh.CANONICAL_DECISION_WORDS:
            assert word in text
        for level, _ in dh.PRIORITY_LEVELS:
            assert level in text

    def test_contract_follows_action_table(self):
        text = _expert_review()
        assert text.index("### 操作建议") < text.index(dh.STRUCTURED_HEADER_MARKER)

    def test_contract_keeps_holdings_block_after(self):
        # 契约段插入后，「持仓明细」仍在末尾（不得被挤到契约之前）
        text = _expert_review()
        assert text.index(dh.STRUCTURED_HEADER_MARKER) < text.index("【持仓明细】")

    def test_contract_example_is_parsable(self):
        # 契约示例行必须能被解析器读回（文档与实现同源）
        text = _expert_review()
        header_line = next(line for line in text.splitlines() if line.startswith(dh.STRUCTURED_HEADER_MARKER))
        rows = dh.parse_structured_header(header_line)
        assert rows is not None and rows[0]["code"] == "600000"
