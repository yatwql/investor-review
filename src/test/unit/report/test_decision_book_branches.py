"""report/decision_book.py 的注册表/配置不可用降级分支。

锁住的契约：
  - 模块中文名不可用时回退模块键名（块照常装配，不阻断报告）；
  - 匿名化模式读取失败按 off 处理（与其余报告口径一致），继续装配决策书。
"""

from __future__ import annotations

import pytest

from src.python.report import decision_book as db

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_module_label_falls_back_to_key_when_registry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_key: str) -> str:
        raise RuntimeError("注册表不可用")

    monkeypatch.setattr("src.python.core.registry.get_llm_module_name", _boom)
    assert db._module_label("summary") == "summary"


def test_build_decision_book_survives_anonymization_read_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> str:
        raise RuntimeError("配置不可读")

    monkeypatch.setattr("src.python.llm.research_contract.is_enabled", lambda: True)
    monkeypatch.setattr("src.python.config.anonymizer.get_anonymization_mode", _boom)
    monkeypatch.setattr(
        "src.python.llm.research_contract.get_module_contracts",
        lambda: {"summary": {"verdict": "pass", "claims": [{"statement": "主张一", "evidence": ["e1"]}]}},
    )

    book = db.build_decision_book()

    assert book is not None
    assert book["modules"][0]["label"] == "summary"
    assert book["modules"][0]["claims"][0]["statement"] == "主张一"
