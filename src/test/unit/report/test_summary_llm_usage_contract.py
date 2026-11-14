"""LLM 用量页签：结构化契约埋点行（与 HTML 端同源文案）。

覆盖：有 `contract_display` 时写入「结构化契约」行；无该字段时不出行（开关关闭/无契约零变化）。
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from src.python.report.summary_llm_usage import write_llm_usage_sheet

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_MODULE_INFO = [{"name": "智囊团深度复盘", "status": "成功", "model": "deepseek", "total_tokens": 0}]


def _flat(ws) -> str:
    return " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


def test_contract_row_rendered_when_field_present():
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    write_llm_usage_sheet(
        ws,
        {"has_usage": True, "call_count": 2, "contract_display": "结构化契约：4 模块 · 主张 6 条"},
        _MODULE_INFO,
    )
    assert "结构化契约：4 模块 · 主张 6 条" in _flat(ws)


def test_no_contract_row_without_field():
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    write_llm_usage_sheet(ws, {"has_usage": True, "call_count": 1}, _MODULE_INFO)
    assert "结构化契约" not in _flat(ws)
