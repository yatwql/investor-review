"""report/llm_contract_block.py 的「无契约」空返回分支。

锁住的契约：开关关闭或该模块无契约载体时，HTML 折叠块与 Excel 小节行都必须为空产物，
一层不改动既有报告。
"""

from __future__ import annotations

import pytest

from src.python.report import llm_contract_block as lcb

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_contract_html_empty_when_module_has_no_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lcb, "get_module_contracts", lambda: {})
    assert lcb.contract_html("summary") == ""


def test_contract_rows_empty_when_module_has_no_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lcb, "get_module_contracts", lambda: {})
    assert lcb.contract_rows("summary") == []


def test_contract_without_claims_renders_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lcb, "get_module_contracts", lambda: {"summary": {"verdict": "pass"}})
    assert lcb.contract_html("summary") == ""
    assert lcb.contract_rows("summary") == []
