"""决策书（主张/证据/判决）装配与呈现契约测试。

覆盖：
  - 开关关闭 / 无契约 / 匿名化模式非 off → 不装配（契约键缺席，产物零变化）
  - 有契约 → 汇总模块判决与主张（证据/失效条件如实透传）
  - 双端同源：HTML 模板与 Excel 写入都读同一契约字段（结构断言）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.python.config.anonymizer import build_report_alias_map
from src.python.config.features import reset_feature_flags, set_feature_enabled
from src.python.llm import research_contract as rc
from src.python.report import decision_book as book

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _clean_state():
    rc.reset_contract_state()
    reset_feature_flags()
    yield
    rc.reset_contract_state()
    reset_feature_flags()


def _contract(*, verdict: str = rc.VERDICT_READY) -> dict:
    return {
        "claims": [
            {
                "id": "c1",
                "statement": "长江电力现金流稳健",
                "evidence": ["ev:hold:600900"],
                "invalidations": ["净利同比转负"],
            }
        ],
        "verdict": verdict,
        "verdict_label": rc.VERDICT_LABELS[verdict],
    }


class TestBuildDecisionBook:
    """装配口径：只在开关开、有契约、匿名化关闭时才出块。"""

    def test_flag_off_returns_none(self):
        rc.record_module_contract("expert_review", _contract())
        assert book.build_decision_book() is None

    def test_no_contract_returns_none(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        assert book.build_decision_book() is None

    def test_contract_present_builds_modules(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", _contract())
        result = book.build_decision_book()
        assert result is not None
        assert result["title"] == book.BLOCK_TITLE
        module = result["modules"][0]
        assert module["key"] == "expert_review"
        assert module["verdict"] == rc.VERDICT_READY
        claim = module["claims"][0]
        assert claim["statement"] == "长江电力现金流稳健"
        assert claim["evidence"] == ["ev:hold:600900"]
        assert claim["invalidations"] == ["净利同比转负"]

    def test_contract_without_claims_skipped(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", {"claims": [], "verdict": rc.VERDICT_READY})
        assert book.build_decision_book() is None

    def test_anonymized_mode_hides_block(self, monkeypatch):
        """匿名化模式下不出块（证据 id 内代码脱敏未实现，宁可不显示也不泄露）。"""
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", _contract())
        monkeypatch.setattr(
            "src.python.config.anonymizer.get_anonymization_mode",
            lambda: "full_anonymous",
        )
        assert book.build_decision_book() is None

    def test_alias_map_not_required_when_mode_off(self):
        """off 模式不构造别名映射也能正常出块（零额外依赖）。"""
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", _contract())
        result = book.build_decision_book()
        assert result is not None
        assert build_report_alias_map([], "off") == {}


class TestDualChannelWiring:
    """双端同源：HTML 模板与 Excel 写入都读同一契约字段。"""

    def test_action_section_template_renders_book(self):
        html = (_REPO_ROOT / "src" / "static" / "tmpl" / "partials" / "action_section.html").read_text(encoding="utf-8")
        assert "decision_book" in html
        assert "决策书" in html or '{{ _book.get("title")' in html

    def test_action_sheet_reads_same_contract_fields(self):
        source = (_REPO_ROOT / "src" / "python" / "report" / "action_sheet.py").read_text(encoding="utf-8")
        assert 'data.get("decision_book")' in source
        for field in ("verdict_label", "statement", "evidence", "invalidations"):
            assert field in source


class TestRenderTimeAttachment:
    """渲染期补挂：判断依据块装配早于 LLM 契约，故渲染入口幂等补一次。"""

    def test_attach_injects_when_contract_present(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", _contract())
        basis = {"enabled": True, "settlement": {}}
        result = book.attach_decision_book(basis)
        assert result is not None
        assert result["decision_book"]["modules"][0]["key"] == "expert_review"

    def test_attach_idempotent(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_module_contract("expert_review", _contract())
        once = book.attach_decision_book({"enabled": True})
        twice = book.attach_decision_book(once)
        assert twice == once

    def test_attach_noop_without_contract_or_flag(self):
        assert book.attach_decision_book({"enabled": True}) == {"enabled": True}
        set_feature_enabled(rc.FEATURE_FLAG, True)
        assert book.attach_decision_book({"enabled": True}) == {"enabled": True}
        assert book.attach_decision_book(None) is None
