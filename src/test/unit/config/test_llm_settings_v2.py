"""llm_settings.json schema v2：生成器、版本拒绝、三层缺省、展平契约、未知保留。"""

from __future__ import annotations

import copy

import pytest

from src.python.config import _llm_settings, _llm_schema
from src.python.config._llm_settings_defaults import (
    _DEFAULT_LLM_SETTINGS,
    _DEFAULTS_NESTED,
    _get_default_llm_settings_template,
    _render_v2,
)
from src.python.core.json_comments import loads
from src.python.core.registry import get_llm_module_names

pytestmark = pytest.mark.unit_config


@pytest.mark.unit
class TestGenerator:
    def test_template_is_v2_and_parses(self):
        raw = _get_default_llm_settings_template()
        doc = loads(raw)
        assert doc["schema_version"] == 2
        assert set(doc["modules"]) == set(get_llm_module_names())

    def test_template_has_chinese_category_and_item_comments(self):
        raw = _get_default_llm_settings_template()
        assert raw.count("//") >= 20
        assert "缺省" in raw and "运行约束" in raw
        assert any("\u4e00" <= ch <= "\u9fff" for ch in raw)

    def test_template_flattens_to_flat_defaults(self):
        doc = loads(_get_default_llm_settings_template())
        assert _llm_schema.flatten(doc) == _DEFAULT_LLM_SETTINGS

    def test_every_module_declares_enabled(self):
        doc = loads(_get_default_llm_settings_template())
        for name, module in doc["modules"].items():
            assert isinstance(module.get("enabled"), bool), name


@pytest.mark.unit
class TestVersionRejection:
    def test_missing_version_rejected_with_filename_and_guidance(self):
        with pytest.raises(_llm_schema.LLMSchemaError) as err:
            _llm_schema.validate_document(
                {"modules": {"global_macro": {"enabled": True}}}, filename="llm_settings.json"
            )
        message = str(err.value)
        assert "llm_settings.json" in message
        assert "schema_version" in message
        assert "重新生成" in message

    def test_wrong_version_rejected(self):
        with pytest.raises(_llm_schema.LLMSchemaError):
            _llm_schema.validate_document({"schema_version": 1, "modules": {"global_macro": {}}})

    def test_non_object_rejected(self):
        with pytest.raises(_llm_schema.LLMSchemaError):
            _llm_schema.validate_document([], filename="llm_settings.json")

    def test_loader_refuses_v1_file(self, tmp_path):
        path = tmp_path / "llm_settings.json"
        path.write_text('{"temperature": 0.7}', encoding="utf-8")

        with pytest.raises(_llm_schema.LLMSchemaError):
            _llm_settings._load_settings_document(path.read_text(encoding="utf-8"), str(path))


@pytest.mark.unit
class TestThreeLayerDefaults:
    def _document(self) -> dict:
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc["defaults"]["temperature"] = 0.4
        doc["modules"]["global_macro"]["temperature"] = 0.9
        doc["modules"]["global_macro"].pop("max_tokens", None)
        doc["modules"]["health_check"].pop("temperature", None)
        return doc

    def test_module_value_wins(self):
        flat = _llm_schema.flatten(self._document())
        assert flat["temperature_global_macro"] == 0.9

    def test_defaults_used_when_module_omits(self):
        flat = _llm_schema.flatten(self._document())
        assert flat["temperature_health_check"] == 0.4

    def test_builtin_defaults_fill_missing_defaults_section(self):
        doc = self._document()
        doc["defaults"].pop("max_tokens")
        merged = _llm_schema.merge_defaults(doc, _DEFAULTS_NESTED)
        flat = _llm_schema.flatten(merged)
        assert flat["max_tokens_global_macro"] == 3072

    def test_merge_keeps_unknown_sections(self):
        doc = self._document()
        doc["modules"]["global_macro"]["future_option"] = 7
        merged = _llm_schema.merge_defaults(doc, _DEFAULTS_NESTED)
        assert merged["modules"]["global_macro"]["future_option"] == 7


@pytest.mark.unit
class TestFlattenContract:
    def test_consumer_keys_present(self):
        flat = _llm_schema.flatten(copy.deepcopy(_DEFAULTS_NESTED))
        for key in (
            "enabled_llm",
            "model_global_macro",
            "temperature_expert_review",
            "thinking_enabled_expert_review",
            "thinking_budget_expert_review",
            "reasoning_effort_expert_review",
            "llm_max_concurrency",
            "llm_max_thinking_concurrency",
            "max_retries",
            "llm_full_fail_retry_delay",
            "llm_total_time_budget_sec",
            "daily_cost_limit",
            "debate",
            "fact_check",
        ):
            assert key in flat, key

    def test_debate_limits_flatten_into_debate(self):
        flat = _llm_schema.flatten(copy.deepcopy(_DEFAULTS_NESTED))
        assert flat["debate"]["max_total_tokens_per_report"] == 72000
        assert flat["debate"]["per_call_timeout_override"] == 90

    def test_unknown_top_level_key_passthrough(self):
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc["plugin_section"] = {"x": 1}
        assert _llm_schema.flatten(doc)["plugin_section"] == {"x": 1}


@pytest.mark.unit
class TestUnknownPreservedOnWrite:
    def test_render_keeps_unknown_top_level_and_module_keys(self):
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc["plugin_section"] = {"x": 1}
        doc["modules"]["global_macro"]["future_option"] = 7

        rendered = _render_v2(doc)
        loaded = loads(rendered)

        assert loaded["plugin_section"] == {"x": 1}
        assert loaded["modules"]["global_macro"]["future_option"] == 7

    def test_apply_flat_updates_keeps_unknown(self):
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc["plugin_section"] = {"x": 1}
        updated = _llm_schema.apply_flat_updates(doc, {"max_retries": 5})
        assert updated["plugin_section"] == {"x": 1}
        assert updated["runtime"]["max_retries"] == 5


class TestRenderSchemaVersionStrict:
    """渲染路径与加载侧同口径：schema_version 缺失或不为 2 即拒绝。"""

    def test_missing_version_rejected(self):
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc.pop("schema_version", None)
        with pytest.raises(ValueError, match="schema_version"):
            _render_v2(doc)

    def test_wrong_version_rejected(self):
        doc = copy.deepcopy(_DEFAULTS_NESTED)
        doc["schema_version"] = 1
        with pytest.raises(ValueError, match="schema_version"):
            _render_v2(doc)
