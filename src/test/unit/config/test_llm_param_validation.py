"""llm_settings 参数范围：加载回落默认、面板写入拒绝（含键名/当前值/范围）。"""

from __future__ import annotations

import copy
import json

import pytest

from src.python.config._llm_settings_defaults import _DEFAULTS_NESTED
from src.python.config._validation_llm import LLM_PARAM_RANGES, param_violation, sanitize_document

pytestmark = pytest.mark.unit_config


@pytest.mark.unit
class TestParamViolationTable:
    @pytest.mark.parametrize(
        ("param", "valid", "invalid"),
        [
            ("temperature", 0.7, 2.5),
            ("max_tokens", 4096, 0),
            ("timeout", 60, 601),
            ("thinking.budget", 12000, 1023),
            ("thinking.effort", "medium", "extreme"),
            ("debate.procon.synthesis_temperature", 0.5, -0.1),
            ("runtime.debate_limits.max_tokens_per_report", 72000, 100),
            ("runtime.debate_limits.call_timeout_override_sec", 90, 4),
        ],
    )
    def test_valid_and_out_of_range(self, param, valid, invalid):
        assert param_violation(param, valid) is None
        message = param_violation(param, invalid)
        assert message is not None
        assert param in message
        assert repr(invalid) in message
        bounds = LLM_PARAM_RANGES[param]
        if isinstance(bounds[0], str):
            enum_text = " / ".join(str(item) for item in bounds)
            assert enum_text in message
        else:
            assert f"[{bounds[0]}, {bounds[1]}]" in message

    def test_type_error_reports_value_and_range(self):
        message = param_violation("temperature", "hot")
        assert message is not None
        assert "'hot'" in message
        assert "[0.0, 2.0]" in message

    def test_none_is_inherit(self):
        for param in LLM_PARAM_RANGES:
            assert param_violation(param, None) is None

    def test_bool_rejected_for_numeric(self):
        message = param_violation("max_tokens", True)
        assert message is not None
        assert "max_tokens" in message and "应为数值" in message


@pytest.mark.unit
class TestLoadSanitize:
    def _doc(self) -> dict:
        return {
            "schema_version": 2,
            "modules": {
                "global_macro": {"enabled": True, "temperature": 9.0, "max_tokens": 0},
                "expert_review": {
                    "enabled": True,
                    "thinking": {"enabled": True, "budget": 10, "effort": "extreme"},
                    "debate": {"procon": {"synthesis_temperature": 5.0}},
                },
            },
            "runtime": {"debate_limits": {"max_tokens_per_report": 10, "call_timeout_override_sec": 1}},
        }

    def test_invalid_values_fall_back_to_defaults(self):
        doc, issues = sanitize_document(self._doc(), _DEFAULTS_NESTED)

        assert doc["modules"]["global_macro"]["temperature"] == 0.3
        assert doc["modules"]["global_macro"]["max_tokens"] == 3072
        assert doc["modules"]["expert_review"]["thinking"]["budget"] == 24000
        assert doc["modules"]["expert_review"]["thinking"]["effort"] == "medium"
        assert doc["modules"]["expert_review"]["debate"]["procon"]["synthesis_temperature"] == 0.5
        assert doc["runtime"]["debate_limits"]["max_tokens_per_report"] == 72000
        assert doc["runtime"]["debate_limits"]["call_timeout_override_sec"] == 90
        assert len(issues) == 7
        assert all("已回落出厂默认" in issue for issue in issues)

    def test_below_default_max_tokens_kept_but_flagged(self):
        """max_tokens 合法但低于出厂默认 → 不改值，但给出「当前 / 默认 / 代价」提示。

        偏低会导致满编持仓下触顶截断，而截断会自动放大重生成一次（多一次计费调用），
        加载时不说，就等于把额外费用与「内容不完整」的根因藏起来。
        """
        from src.python.config._llm_settings_defaults import get_llm_setting_default

        factory = get_llm_setting_default("max_tokens_self_review")
        assert isinstance(factory, int)
        doc = {"schema_version": 2, "modules": {"self_review": {"enabled": True, "max_tokens": factory // 4}}}
        sanitized, issues = sanitize_document(doc, _DEFAULTS_NESTED)

        assert sanitized["modules"]["self_review"]["max_tokens"] == factory // 4  # 合法值不被回落
        assert len(issues) == 1
        assert f"当前 {factory // 4}" in issues[0]
        assert f"出厂默认 {factory}" in issues[0]
        assert "多一次计费调用" in issues[0]

    def test_at_or_above_default_max_tokens_not_flagged(self):
        """max_tokens ≥ 出厂默认（含不配置）→ 不产生提示，避免噪声稀释真告警。"""
        doc = {"schema_version": 2, "modules": {"self_review": {"enabled": True, "temperature": 0.3}}}
        _sanitized, issues = sanitize_document(doc, _DEFAULTS_NESTED)
        assert issues == []

    def test_original_document_not_mutated(self):
        original = self._doc()
        snapshot = copy.deepcopy(original)
        sanitize_document(original, _DEFAULTS_NESTED)
        assert original == snapshot

    def test_loader_uses_sanitized_values(self, tmp_path, monkeypatch):
        from src.python.config import _llm_settings

        path = tmp_path / "llm_settings.json"
        path.write_text(json.dumps(self._doc()), encoding="utf-8")
        monkeypatch.setattr(_llm_settings, "get_llm_settings_path", lambda: str(path))

        flat = _llm_settings._load_settings_document(path.read_text(encoding="utf-8"), str(path))

        assert flat["temperature_global_macro"] == 0.3
        assert flat["thinking_budget_expert_review"] == 24000

    def test_file_untouched_by_load(self, tmp_path, monkeypatch):
        """加载只回落内存视图，不改写用户文件（非法值原样留在盘上待人工修）。"""
        from src.python.config import _llm_settings

        path = tmp_path / "llm_settings.json"
        raw = json.dumps(self._doc())
        path.write_text(raw, encoding="utf-8")
        monkeypatch.setattr(_llm_settings, "get_llm_settings_path", lambda: str(path))

        _llm_settings._load_settings_document(raw, str(path))

        assert path.read_text(encoding="utf-8") == raw


@pytest.mark.unit
class TestPanelWriteRejects:
    def test_out_of_range_rejected_with_value_and_range(self):
        from src.python.config.edit_ops import ConfigEditError, apply_config_edit

        with pytest.raises(ConfigEditError) as err:
            apply_config_edit({"key": "llm_max_concurrency", "value": 99})

        message = str(err.value)
        assert "llm_max_concurrency" in message
        assert "99" in message
        assert "[1, 8]" in message

    def test_invalid_write_leaves_file_unchanged(self, tmp_path, monkeypatch):
        from src.python.config import _llm_settings
        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template
        from src.python.config.edit_ops import ConfigEditError, apply_config_edit

        path = tmp_path / "llm_settings.json"
        raw = _get_default_llm_settings_template()
        path.write_text(raw, encoding="utf-8")
        monkeypatch.setattr(_llm_settings, "get_llm_settings_path", lambda: str(path))

        with pytest.raises(ConfigEditError):
            apply_config_edit({"key": "max_retries", "value": -1})

        assert path.read_text(encoding="utf-8") == raw
