"""llm_settings v2 结构模块的分支覆盖：展平/反展平映射、结构校验、文本级 patch 扫描器。

覆盖三组契约：
  一、`validate_document` 的四类结构拒绝（非对象根 / 版本不符 / 段非对象 / modules 缺失或非对象）
  二、`flatten` / `apply_flat_updates` 的扁平键双向映射（含未知键原样透传、未知模块不映射）
  三、`flat_key_path` + 文本 patch 扫描器（`_find_matching_close` / `_find_child_value_span` /
     `_locate_path_span`）：注释与转义下的括号配对、叶子定位、不可定位时返回 None
"""

from __future__ import annotations

import pytest

from src.python.config import _llm_schema
from src.python.config._llm_schema import (
    RUNTIME_FIELDS,
    LLMSchemaError,
    _find_child_value_span,
    _find_matching_close,
    _locate_path_span,
    apply_flat_updates,
    flat_key_path,
    flatten,
    patch_document_text,
    validate_document,
)
from src.python.config._llm_settings import write_llm_settings
from src.python.core.json_comments import loads as loads_jsonc
from src.python.core.registry import get_llm_module_names

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


def _module() -> str:
    """任一注册模块名（映射测试用；模块清单由注册表派生，不写死）。"""
    return next(iter(get_llm_module_names()))


# ── 一、结构校验拒绝分支 ──────────────────────────────────


class TestValidateDocumentRejections:
    def test_root_not_object(self):
        with pytest.raises(LLMSchemaError) as exc:
            validate_document([], filename="llm_settings.json")
        assert "根元素不是 JSON 对象" in str(exc.value)
        assert "llm_settings.json" in str(exc.value)

    def test_section_not_object(self):
        doc = {"schema_version": 2, "modules": {_module(): {"enabled": True}}, "runtime": []}
        with pytest.raises(LLMSchemaError) as exc:
            validate_document(doc)
        assert "runtime 段应为 JSON 对象" in str(exc.value)

    def test_modules_missing(self):
        with pytest.raises(LLMSchemaError) as exc:
            validate_document({"schema_version": 2})
        assert "缺少 modules 段" in str(exc.value)

    def test_modules_empty(self):
        with pytest.raises(LLMSchemaError) as exc:
            validate_document({"schema_version": 2, "modules": {}})
        assert "缺少 modules 段" in str(exc.value)

    def test_module_not_object(self):
        with pytest.raises(LLMSchemaError) as exc:
            validate_document({"schema_version": 2, "modules": {_module(): "x"}})
        assert f"modules.{_module()} 应为 JSON 对象" in str(exc.value)

    def test_enabled_not_bool(self):
        with pytest.raises(LLMSchemaError) as exc:
            validate_document({"schema_version": 2, "modules": {_module(): {"enabled": 1}}})
        assert f"modules.{_module()}.enabled 应为布尔" in str(exc.value)


# ── 二、展平 / 反展平映射 ────────────────────────────────


class TestFlattenBranches:
    def test_non_dict_module_skipped_and_unknown_top_level_kept(self):
        """modules 段的非对象条目直接跳过；未知顶层键原样透传（不参与展平）。"""
        doc = {
            "schema_version": 2,
            "modules": {_module(): {"enabled": True, "model": "m1"}, "broken": "not-a-dict"},
            "custom_extension": {"a": 1},
        }
        flat = flatten(doc)
        assert flat[f"model_{_module()}"] == "m1"
        assert flat["enabled_llm"][_module()] is True
        assert set(flat["enabled_llm"]) == set(get_llm_module_names())  # 未出现的模块补 False
        assert "model_broken" not in flat
        assert flat["custom_extension"] == {"a": 1}

    def test_thinking_and_debate_and_runtime_and_advanced(self):
        """thinking 三级 / debate 深拷贝 / runtime 六字段 / debate_limits 折算 / advanced 两段。"""
        doc = {
            "schema_version": 2,
            "defaults": {"thinking": {"budget": 100}},
            "modules": {
                _module(): {
                    "enabled": False,
                    "thinking": {"enabled": True, "effort": "high"},
                    "debate": {"max_total_tokens_per_report": 5000},
                }
            },
            "runtime": {
                "max_concurrency": 3,
                "thinking_concurrency": 2,
                "max_retries": 1,
                "full_fail_retry_delay_sec": 7,
                "time_budget_sec": 900,
                "daily_cost_limit": 12.5,
                "debate_limits": {"max_tokens_per_report": 6000, "call_timeout_override_sec": 120},
            },
            "advanced": {"fact_check": {"enabled": True}, "news_correlation": {"top_n": 9}},
        }
        flat = flatten(doc)
        assert flat[f"thinking_enabled_{_module()}"] is True
        assert flat[f"thinking_budget_{_module()}"] == 100  # defaults 兜底
        assert flat[f"reasoning_effort_{_module()}"] == "high"
        assert flat["enabled_llm"][_module()] is False
        assert flat["llm_max_concurrency"] == 3
        assert flat["llm_max_thinking_concurrency"] == 2
        assert flat["max_retries"] == 1
        assert flat["llm_full_fail_retry_delay"] == 7
        assert flat["llm_total_time_budget_sec"] == 900
        assert flat["daily_cost_limit"] == 12.5
        assert flat["debate"]["max_total_tokens_per_report"] == 6000
        assert flat["debate"]["per_call_timeout_override"] == 120
        assert flat["fact_check"] == {"enabled": True}
        assert flat["news_correlation_top_n"] == 9


class TestApplyFlatUpdatesBranches:
    def test_debate_dict_maps_to_expert_review_module_and_limits(self):
        doc = apply_flat_updates(
            {},
            {"debate": {"max_total_tokens_per_report": 5000, "per_call_timeout_override": 90}},
        )
        module = doc["modules"]["expert_review"]
        assert module["debate"] == {"max_total_tokens_per_report": 5000, "per_call_timeout_override": 90}
        assert doc["runtime"]["debate_limits"] == {"max_tokens_per_report": 5000, "call_timeout_override_sec": 90}
        assert "debate" not in doc

    def test_fact_check_and_news_correlation_and_enabled_llm(self):
        doc = apply_flat_updates(
            {},
            {
                "fact_check": {"enabled": False},
                "news_correlation_top_n": 5,
                "enabled_llm": {_module(): True},
            },
        )
        assert doc["advanced"]["fact_check"] == {"enabled": False}
        assert doc["advanced"]["news_correlation"]["top_n"] == 5
        assert doc["modules"][_module()]["enabled"] is True
        assert doc["schema_version"] == _llm_schema.SCHEMA_VERSION

    def test_runtime_flat_keys_round_trip_through_flatten(self):
        """runtime 扁平键写回：落进 `runtime` 段，顶层不留扁平键残留，`flatten` 读回守恒。"""
        doc = apply_flat_updates({}, {"llm_max_concurrency": 2, "llm_total_time_budget_sec": 600})
        # 落点断言（只测 flatten 读回会在「写顶层被 runtime 值压掉」时假绿）
        assert doc["runtime"]["max_concurrency"] == 2
        assert doc["runtime"]["time_budget_sec"] == 600
        assert "llm_max_concurrency" not in doc
        assert "llm_total_time_budget_sec" not in doc
        flat = flatten(doc)
        assert flat["llm_max_concurrency"] == 2
        assert flat["llm_total_time_budget_sec"] == 600

    def test_module_suffix_and_thinking_prefix_map_known_module(self):
        name = _module()
        doc = apply_flat_updates(
            {},
            {
                f"model_{name}": "gpt-x",
                f"cache_enabled_{name}": True,
                f"thinking_enabled_{name}": True,
                f"thinking_budget_{name}": 2048,
                f"reasoning_effort_{name}": "medium",
            },
        )
        module = doc["modules"][name]
        assert module["model"] == "gpt-x"
        assert module["cache"] is True
        assert module["thinking"] == {"enabled": True, "budget": 2048, "effort": "medium"}

    def test_unknown_module_and_unmapped_key_pass_through_to_top_level(self):
        """未知模块名不写入 modules（保留原名到顶层）；未映射键（api_key 等）同样原样保留。"""
        doc = apply_flat_updates({}, {"model_no_such_module": "m", "thinking_enabled_no_such": True, "api_key": "k"})
        assert "no_such_module" not in doc["modules"]
        assert doc["model_no_such_module"] == "m"
        assert doc["thinking_enabled_no_such"] is True
        assert doc["api_key"] == "k"

    def test_non_dict_module_replaced_when_mapping(self):
        """modules.<name> 为非对象残留时，写入前替换为空对象（不抛错）。"""
        name = _module()
        doc = apply_flat_updates({"modules": {name: "broken"}}, {f"model_{name}": "m2"})
        assert doc["modules"][name] == {"model": "m2"}


# ── 三、扁平键 → v2 路径 ────────────────────────────────


class TestFlatKeyPath:
    def test_prefix_families_map_to_module_paths(self):
        name = _module()
        assert flat_key_path(f"enabled_llm.{name}") == ("modules", name, "enabled")
        assert flat_key_path("debate") == ("modules", "expert_review", "debate")
        assert flat_key_path(f"model_{name}") == ("modules", name, "model")
        assert flat_key_path("daily_cost_limit") == ("runtime", "daily_cost_limit")
        assert flat_key_path("news_correlation_top_n") == ("advanced", "news_correlation", "top_n")
        assert flat_key_path(f"thinking_budget_{name}") == ("modules", name, "thinking", "budget")
        assert flat_key_path(f"reasoning_effort_{name}") == ("modules", name, "thinking", "effort")

    def test_unmappable_keys_return_none(self):
        assert flat_key_path("api_key") is None
        assert flat_key_path("provider") is None


# ── 四、文本 patch 扫描器 ────────────────────────────────


class TestMatchingClose:
    def test_skips_escaped_quote_and_trailing_object(self):
        text = '{"a": "b\\"}c", "n": 1}'
        assert _find_matching_close(text, 0) == len(text)

    def test_line_comment_containing_closer(self):
        text = '{"a": 1 // } 注释\n, "b": 2}'
        assert _find_matching_close(text, 0) == len(text)

    def test_block_comment_containing_closer(self):
        text = '{"a": /* } */ 2}'
        assert _find_matching_close(text, 0) == len(text)

    def test_array_closer(self):
        text = "[1, [2], 3]"
        assert _find_matching_close(text, 0) == len(text)

    def test_unterminated_returns_none(self):
        assert _find_matching_close('{"a": 1', 0) is None


class TestChildValueSpan:
    def test_object_value_span(self):
        text = '{"k": {"x": 1}}'
        assert _find_child_value_span(text, 1, len(text) - 1, "k") == (6, 14)

    def test_string_value_with_escape(self):
        text = '{"k": "a\\"b"}'
        assert _find_child_value_span(text, 1, len(text) - 1, "k") == (6, 12)

    def test_scalar_value_trimmed(self):
        text = '{"k": 12  , "j": 1}'
        assert _find_child_value_span(text, 1, len(text) - 1, "k") == (6, 8)

    def test_missing_key(self):
        assert _find_child_value_span('{"a": 1}', 1, 7, "zz") is None

    def test_value_start_past_end(self):
        assert _find_child_value_span('{"k":   }', 1, 8, "k") is None

    def test_unterminated_string(self):
        assert _find_child_value_span('{"k": "abc }', 1, 12, "k") is None


class TestLocatePathSpan:
    def test_empty_path(self):
        assert _locate_path_span("{}", ()) is None

    def test_missing_top_level_key(self):
        assert _locate_path_span('{"a": 1}', ("zz",)) is None

    def test_intermediate_not_object(self):
        assert _locate_path_span('{"a": 1}', ("a", "b")) is None

    def test_leaf_is_container(self):
        assert _locate_path_span('{"a": {"b": [1]}}', ("a", "b")) is None


class TestPatchDocumentText:
    RAW = (
        "{\n"
        "  // 保持注释\n"
        '  "schema_version": 2,\n'
        '  "runtime": {"max_concurrency": 4},\n'
        '  "modules": {"expert_review": {"model": "old"}}\n'
        "}\n"
    )

    def test_nested_runtime_scalar_patched(self):
        out = patch_document_text(self.RAW, {"llm_max_concurrency": 8})
        assert out is not None
        assert '"max_concurrency": 8' in out
        assert "// 保持注释" in out

    def test_module_suffix_patched(self):
        out = patch_document_text(self.RAW, {"model_expert_review": "new"})
        assert out is not None
        assert '"model": "new"' in out

    def test_top_level_fallback_when_nested_path_absent(self):
        """v2 路径不可定位时回落到同名顶层键（旧扁平残留文件可继续 patch）。"""
        raw = '{"api_key": "old", "model_expert_review": "flat"}'
        out = patch_document_text(raw, {"model_expert_review": "patched"})
        assert out == '{"api_key": "old", "model_expert_review": "patched"}'

    def test_unlocatable_key_returns_none(self):
        assert patch_document_text(self.RAW, {"model_no_such_module": "x"}) is None

    def test_non_path_key_and_container_value_return_none(self):
        assert patch_document_text(self.RAW, {"api_key": "x"}) is None
        assert patch_document_text(self.RAW, {"debate": {"max_total_tokens_per_report": 1}}) is None


# ── 五、runtime 扁平键的写回落点 ────────────────────────


class TestRuntimeFlatKeyLanding:
    """runtime 扁平键必须落进 `runtime` 段——落到顶层会被 `flatten` 的 runtime 值覆盖（用户设置丢失）。

    映射表 ``RUNTIME_FIELDS`` 是 ``(字段, 扁平键)``；查表方向用扁平键，逐字段参数化派生保证
    六个字段都被覆盖（`max_retries` / `daily_cost_limit` 的字段名恰等于扁平键，会掩盖反向建表缺陷）。
    """

    @staticmethod
    def _landing_value(flat_key: str) -> int:
        """取一个与落盘默认值不同的整数（同值会在「无变化即跳过」处提前 return，测不到写入路径）。"""
        from src.python.config._llm_settings_defaults import _DEFAULTS_NESTED

        default_value = flatten(_DEFAULTS_NESTED).get(flat_key, 0)
        return int(default_value) + 1

    @pytest.mark.parametrize(("field", "flat_key"), RUNTIME_FIELDS)
    def test_flat_key_writes_into_runtime_section_only(self, field, flat_key):
        value = self._landing_value(flat_key)
        doc = apply_flat_updates({}, {flat_key: value})
        assert doc["runtime"][field] == value
        assert flat_key not in doc
        assert flatten(doc)[flat_key] == value

    @pytest.mark.parametrize(("field", "flat_key"), RUNTIME_FIELDS)
    def test_write_to_missing_file_lands_in_runtime_section(self, tmp_path, field, flat_key):
        """写盘级：llm_settings.json 不存在（走 `_DEFAULTS_NESTED` 兜底）时落盘值须在 runtime 段。"""
        path = tmp_path / "llm_settings.json"
        value = self._landing_value(flat_key)
        assert not path.exists()

        write_llm_settings({flat_key: value}, str(path))

        doc = loads_jsonc(path.read_text(encoding="utf-8"))
        assert doc["runtime"][field] == value
        assert flat_key not in doc
        assert flatten(doc)[flat_key] == value
