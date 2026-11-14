"""LLM 复盘结构化契约（claim / evidence / verdict）单元测试。

覆盖：
  - 证据索引：由提示词输入块生成、id 形态稳定、摘要只给一行
  - 契约解析：复用决策头括号扫描（无标记 / JSON 非法 / 缺 claims 一律 None）
  - 契约校验：未知证据 / 空证据 / 缺失效条件 / 条数上限 / 模型自证 ready 不被采信
  - 提示词：开关关闭时提示词逐字节不变；开启时含证据索引
  - 运行作用域：报告边界清空、索引按并集累积
"""

from __future__ import annotations

import pytest

from src.python.config.features import reset_feature_flags, set_feature_enabled
from src.python.llm import evidence_index, research_contract as rc

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


@pytest.fixture(autouse=True)
def _clean_state():
    rc.reset_contract_state()
    reset_feature_flags()
    yield
    rc.reset_contract_state()
    reset_feature_flags()


_HOLDINGS = [
    {"code": "600900", "name": "长江电力", "profit_rate": 65.4, "price": 28.1},
    {"code": "561910", "name": "电池ETF", "profit_rate": -13.22, "price": 1.02},
]


class TestEvidenceIndex:
    """证据索引：来源块 → 稳定 id + 一行摘要。"""

    def test_ids_and_summaries(self):
        index = evidence_index.build_evidence_index(holdings_details=_HOLDINGS)
        assert "ev:hold:600900" in index
        assert "ev:quote:561910" in index
        assert "长江电力" in index["ev:hold:600900"]
        assert "+65.40%" in index["ev:hold:600900"]

    def test_metrics_and_penetration(self):
        index = evidence_index.build_evidence_index(
            penetrated_assets=[{"name": "纳指100ETF", "codes": ["513390", "016055"]}],
            metrics={"beta": 0.92, "sharpe": "n/a"},
        )
        assert "ev:pen:513390" in index
        assert "ev:metric:beta" in index
        assert "ev:metric:sharpe" not in index  # 非数值不进索引

    def test_news_id_is_content_addressed(self):
        a = evidence_index.build_evidence_index(news_items=[{"title": "降准", "media_name": "财新"}])
        b = evidence_index.build_evidence_index(news_items=[{"title": "降准", "media_name": "财新"}])
        assert list(a) == list(b)  # 同内容 → 同 id（不随顺序/时间漂移）
        assert list(a)[0].startswith("ev:news:")

    def test_empty_inputs_yield_empty_index(self):
        assert evidence_index.build_evidence_index() == {}

    def test_index_lines_truncate_explicitly(self):
        index = {f"ev:hold:{i}": f"标的{i}" for i in range(5)}
        lines = evidence_index.render_index_lines(index, limit=3)
        assert len(lines) == 4
        assert "另有 2 条证据未列出" in lines[-1]


class TestInstruction:
    """提示词追加段。"""

    def test_instruction_contains_marker_and_index(self):
        index = {"ev:hold:600900": "长江电力（600900）"}
        text = rc.build_instruction(index)
        assert rc.STRUCTURED_CLAIMS_MARKER in text
        assert "ev:hold:600900" in text
        assert "invalidations" in text

    def test_instruction_without_index_has_no_index_section(self):
        text = rc.build_instruction({})
        assert "【证据索引】" not in text
        assert rc.STRUCTURED_CLAIMS_MARKER in text


class TestParseAndValidate:
    """解析 + 校验矩阵。"""

    def _text(self, payload: str) -> str:
        return "正文段落。\n\n" + rc.STRUCTURED_CLAIMS_MARKER + payload

    def test_parse_plain_marker(self):
        payload = '{"claims":[{"id":"c1","statement":"x","evidence":["ev:hold:600900"],"invalidations":["y"]}]}'
        parsed = rc.parse_contract(self._text(payload))
        assert parsed is not None
        assert parsed["claims"][0]["id"] == "c1"

    @pytest.mark.parametrize(
        "text",
        [
            "没有任何契约标记",
            rc.STRUCTURED_CLAIMS_MARKER + "{不是 JSON}",
            rc.STRUCTURED_CLAIMS_MARKER + '{"claims":"not-a-list"}',
            rc.STRUCTURED_CLAIMS_MARKER + "",
        ],
    )
    def test_parse_invalid_returns_none(self, text):
        assert rc.parse_contract(text) is None

    def test_validate_ready_when_all_evidence_known(self):
        index = {"ev:hold:600900": "长江电力"}
        payload = {
            "claims": [
                {
                    "id": "c1",
                    "statement": "长江电力现金流稳健",
                    "evidence": ["ev:hold:600900"],
                    "invalidations": ["净利同比转负"],
                }
            ],
            "verdict": "ready",
        }
        result = rc.validate_contract(payload, index, as_of="2026-11-13")
        assert result is not None
        assert result["verdict"] == rc.VERDICT_READY
        assert result["errors"] == []
        assert result["as_of"] == "2026-11-13"

    def test_unknown_evidence_downgrades_to_revise(self):
        payload = {
            "claims": [{"id": "c1", "statement": "s", "evidence": ["ev:hold:999999"], "invalidations": ["i"]}],
            "verdict": "ready",
        }
        result = rc.validate_contract(
            payload,
            {},
        )
        assert result is not None
        assert result["verdict"] == rc.VERDICT_REVISE
        assert any(err.startswith("evidence_unknown") for err in result["errors"])

    def test_missing_evidence_or_invalidations_recorded(self):
        payload = {
            "claims": [
                {"id": "c1", "statement": "s", "evidence": [], "invalidations": []},
            ]
        }
        result = rc.validate_contract(payload, {"ev:hold:1": "x"})
        assert result is not None
        assert any(err.startswith("evidence_missing") for err in result["errors"])
        assert any(err.startswith("invalidations_missing") for err in result["errors"])
        assert result["verdict"] == rc.VERDICT_EVIDENCE_NEEDED

    def test_claim_without_statement_dropped(self):
        payload = {"claims": [{"id": "c1", "statement": "", "evidence": ["ev:hold:1"]}]}
        result = rc.validate_contract(payload, {"ev:hold:1": "x"})
        assert result is not None
        assert result["claims"] == []
        assert any(err.startswith("statement_missing") for err in result["errors"])

    def test_claims_truncated_to_limit(self):
        claims = [
            {"id": f"c{i}", "statement": "s", "evidence": [], "invalidations": ["i"]} for i in range(rc.MAX_CLAIMS + 2)
        ]
        result = rc.validate_contract({"claims": claims}, {})
        assert result is not None
        assert len(result["claims"]) == rc.MAX_CLAIMS
        assert any(err.startswith("claims_truncated") for err in result["errors"])

    def test_none_payload_returns_none(self):
        assert rc.validate_contract(None, {}) is None

    def test_model_cannot_self_certify_ready_with_errors(self):
        payload = {"claims": [{"id": "c1", "statement": "s", "evidence": [], "invalidations": []}], "verdict": "ready"}
        result = rc.validate_contract(payload, {})
        assert result is not None
        assert result["verdict"] != rc.VERDICT_READY


class TestRunScopeStore:
    """运行作用域载体：索引并集累积、契约记录与清空。"""

    def test_evidence_index_accumulates_by_union(self):
        rc.record_evidence_index({"ev:hold:1": "a"})
        rc.record_evidence_index({"ev:hold:2": "b"})
        assert set(rc.get_evidence_index()) == {"ev:hold:1", "ev:hold:2"}

    def test_module_contracts_record_and_reset(self):
        rc.record_module_contract("expert_review", {"verdict": rc.VERDICT_READY})
        assert "expert_review" in rc.get_module_contracts()
        rc.record_module_contract("health_check", None)  # None 不落载体
        assert "health_check" not in rc.get_module_contracts()
        rc.reset_contract_state()
        assert rc.get_module_contracts() == {}
        assert rc.get_evidence_index() == {}

    def test_flag_off_contract_state_stays_empty(self):
        assert rc.is_enabled() is False
        assert rc.get_module_contracts() == {}

    def test_flag_on_reports_enabled(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        assert rc.is_enabled() is True


class TestPromptGating:
    """提示词开关：关闭逐字节不变，开启追加契约段。"""

    def _prompt(self):
        from src.python.llm.prompts_action import _build_expert_review_prompt

        return _build_expert_review_prompt(
            250000.0,
            205000.0,
            45000.0,
            1000.0,
            2,
            {"股票": 1, "基金": 1},
            penetrated_assets=[{"name": "纳指100ETF", "codes": ["513390"]}],
            holdings_details=_HOLDINGS,
        )

    def test_disabled_prompt_has_no_contract(self):
        off = self._prompt()
        assert rc.STRUCTURED_CLAIMS_MARKER not in off

    def test_enabled_prompt_has_contract_and_index(self):
        set_feature_enabled(rc.FEATURE_FLAG, True)
        on = self._prompt()
        assert rc.STRUCTURED_CLAIMS_MARKER in on
        assert "ev:hold:600900" in on
        # 索引同时登记到运行作用域，供生成后一遍校验
        assert "ev:hold:600900" in rc.get_evidence_index()


class TestStripContractLine:
    """展示前剥离机器可读行（缓存原文保留）。"""

    def test_strip_removes_only_marker_line(self):
        text = "第一段\n" + rc.STRUCTURED_CLAIMS_MARKER + '{"claims":[]}' + "\n第二段"
        stripped = rc.strip_contract_line(text)
        assert stripped is not None
        assert rc.STRUCTURED_CLAIMS_MARKER not in stripped
        assert "第一段" in stripped and "第二段" in stripped

    def test_strip_without_marker_is_noop(self):
        assert rc.strip_contract_line("纯正文") == "纯正文"
        assert rc.strip_contract_line(None) is None


class TestRenderingAndPostPass:
    """展示层与生成后一遍接线（开关关闭时零行为）。"""

    @staticmethod
    def _valid_contract() -> dict:
        return {
            "claims": [
                {
                    "id": "c1",
                    "statement": "长江电力现金流稳健",
                    "evidence": ["ev:hold:600900"],
                    "invalidations": ["净利同比转负"],
                }
            ],
            "verdict": rc.VERDICT_READY,
            "verdict_label": rc.VERDICT_LABELS[rc.VERDICT_READY],
        }

    def test_html_block_rendered_when_contract_present(self):
        from src.python.report.llm_contract_block import contract_html

        rc.record_module_contract("expert_review", self._valid_contract())
        html = contract_html("expert_review")
        assert "主张与证据" in html
        assert "长江电力现金流稳健" in html
        assert "ev:hold:600900" in html
        assert "失效条件" in html

    def test_excel_rows_rendered_when_contract_present(self):
        from src.python.report.llm_contract_block import contract_rows

        rc.record_module_contract("expert_review", self._valid_contract())
        rows = contract_rows("expert_review")
        assert rows[0][0].startswith("主张与证据")
        assert any("长江电力现金流稳健" in cell for row in rows for cell in row)

    def test_no_block_when_state_empty(self):
        from src.python.report.llm_contract_block import contract_html, contract_rows

        assert contract_html("expert_review") == ""
        assert contract_rows("expert_review") == []

    def test_post_pass_records_contract_when_enabled(self):
        from src.python.llm import _llm_post_pass

        set_feature_enabled(rc.FEATURE_FLAG, True)
        rc.record_evidence_index({"ev:hold:600900": "长江电力"})
        text = (
            "正文\n"
            + rc.STRUCTURED_CLAIMS_MARKER
            + '{"claims":[{"id":"c1","statement":"s","evidence":["ev:hold:600900"],"invalidations":["i"]}],'
            + '"verdict":"ready"}'
        )
        _llm_post_pass._record_research_contracts({"expert_review": text})
        contracts = rc.get_module_contracts()
        assert "expert_review" in contracts
        assert contracts["expert_review"]["verdict"] == rc.VERDICT_READY

    def test_post_pass_noop_when_disabled(self):
        from src.python.llm import _llm_post_pass

        text = rc.STRUCTURED_CLAIMS_MARKER + '{"claims":[]}'
        _llm_post_pass._record_research_contracts({"expert_review": text})
        assert rc.get_module_contracts() == {}


class TestRecommendationHardConstraint:
    """建议级硬约束：需复核 / 不可执行不得携带可执行数量（校验期拒绝）。"""

    def test_review_required_forbids_quantity(self):
        errors = rc.validate_recommendation(review_required=True, quantity=100)
        assert "quantity_forbidden_when_review_required" in errors

    def test_blocked_forbids_quantity(self):
        errors = rc.validate_recommendation(execution_status=rc.EXECUTION_BLOCKED, quantity=100)
        assert "quantity_forbidden_when_not_executable" in errors

    def test_conditional_with_quantity_passes(self):
        assert rc.validate_recommendation(execution_status=rc.EXECUTION_CONDITIONAL, quantity=100) == []

    def test_no_quantity_always_passes(self):
        assert rc.validate_recommendation(review_required=True, quantity=None) == []

    def test_invalid_status_and_non_positive_quantity(self):
        errors = rc.validate_recommendation(execution_status="weird", quantity=0)
        assert "execution_status_invalid:weird" in errors
        assert "quantity_not_positive" in errors


class TestAcceptanceGuards:
    """P1 验收缺项：旧缓存 payload 兼容 + 证据索引体积上限。"""

    def test_legacy_payload_without_claims_renders_nothing(self):
        """旧缓存正文无契约头 → 解析 None、载体空、渲染无块且不抛错（向后兼容）。"""
        from src.python.report.llm_contract_block import contract_html, contract_rows

        legacy_text = "<p>旧版正文：没有结构化契约</p>"
        assert rc.parse_contract(legacy_text) is None
        rc.record_module_contract("expert_review", rc.validate_contract(None, {}))
        assert rc.get_module_contracts() == {}
        assert contract_html("expert_review") == ""
        assert contract_rows("expert_review") == []

    def test_index_budget_capped_to_ratio(self):
        """索引体积按输入块的 15% 截断（超出时给「其余 N 条未列出」说明）。"""
        index = {f"ev:hold:{i:06d}": f"标的{i}持仓收益率 +{i % 90}.00%" for i in range(200)}
        input_chars = 2000
        text = rc.build_instruction(index, input_chars=input_chars)
        index_part = text.split("【证据索引】", 1)[1]
        assert len(index_part) <= int(input_chars * rc.MAX_INDEX_RATIO) + 200
        assert "因体积上限未列出" in index_part

    def test_index_budget_default_when_input_unknown(self):
        index = {f"ev:hold:{i:06d}": "摘要" for i in range(2000)}
        text = rc.build_instruction(index)
        assert len(text) <= rc.DEFAULT_INDEX_BUDGET + 600
