"""LLM 三份配置文件（settings / providers / pricing）的解析与落盘容错测试。

覆盖契约：
  - `_llm_settings`：`is_enable_llm` 只看 4 个 LLM 报告模块；debate 段非法值回退
    出厂默认并告警；设置文件自动创建失败只告警；写盘遇结构不符（schema 错误）须
    `raise` 让调用方看到，目录不可建转 OSError
  - `_llm_providers`：配置路径取值异常回退默认路径；凭据目录不可建须报错而非
    静默留半成品；chmod 不支持时忽略；`llm_key.json` 根非对象/读取失败返回 None；
    线路必填字段类型非法只告警；providers 数组为空判为无效
  - `_llm_pricing`：币种白名单、非法 peak 段、非法时段文本、根元素非对象、
    读取失败均回退内置价且不阻断报告生成
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from src.python.config import _llm_pricing, _llm_providers, _llm_settings

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


@pytest.fixture(autouse=True)
def _reset_pricing_cache():
    """用例前后清空计价缓存（模块级全局状态，mtime+size 命中会跨用例复用）。"""
    _llm_pricing.invalidate_pricing_cache()
    yield
    _llm_pricing.invalidate_pricing_cache()


# ══════════════════════════════════════════════════════════════
# _llm_settings
# ══════════════════════════════════════════════════════════════


class TestIsEnableLlm:
    def test_report_modules_all_disabled_disables_section(self, monkeypatch):
        """4 个 LLM 报告模块全部关闭时 LLM 分析章节整体不启用。"""
        monkeypatch.setattr(
            _llm_settings,
            "get_llm_config",
            lambda: {"enabled_llm": {"global_macro": False, "news_correlation": True}},
        )

        assert _llm_settings.is_enable_llm() is False, "news_correlation 不参与章节可见性判定"


class TestLoadDebateConfigFaults:
    def test_missing_debate_section_returns_defaults(self):
        """llm_settings 无 debate 段时直接返回出厂默认（不报错）。"""
        merged = _llm_settings._load_debate_config({})

        assert merged == _llm_settings._DEBATE_CONFIG_DEFAULTS

    def test_procon_values_out_of_range_fall_back_with_warning(self):
        """per_call_max_tokens 非正数、synthesis_temperature 越界时回退出厂默认。"""
        settings = {
            "debate": {
                "procon": {"per_call_max_tokens": 0, "synthesis_temperature": 5.0},
            }
        }

        merged = _llm_settings._load_debate_config(settings)

        assert merged["procon"]["synthesis_temperature"] == 0.5
        assert (
            merged["procon"]["per_call_max_tokens"]
            == _llm_settings._DEBATE_CONFIG_DEFAULTS["procon"]["per_call_max_tokens"]
        )

    def test_conditional_scenarios_partially_invalid_keeps_valid_ones(self):
        """情景列表里格式非法项被跳过，合法项照常生效。"""
        settings = {
            "debate": {
                "conditional": {
                    "scenarios": [
                        {"name": "降息", "desc": "宽松", "change": 0.1},
                        {"name": "缺 desc"},
                        "not-a-dict",
                    ]
                }
            }
        }

        merged = _llm_settings._load_debate_config(settings)

        assert merged["conditional"]["scenarios"] == [{"name": "降息", "change": 0.1, "desc": "宽松"}]

    def test_conditional_scenarios_all_invalid_keeps_defaults(self):
        """情景全部非法时回退出厂默认情景列表。"""
        settings = {"debate": {"conditional": {"scenarios": [{"bad": 1}]}}}

        merged = _llm_settings._load_debate_config(settings)

        assert merged["conditional"]["scenarios"] == _llm_settings._DEBATE_CONFIG_DEFAULTS["conditional"]["scenarios"]

    def test_clamped_procon_temperature_is_reported(self):
        """越界温度回落时留下告警，其余合法子项照常生效。"""
        settings = {"debate": {"procon": {"synthesis_model": "claude-sonnet", "synthesis_temperature": 9.0}}}

        merged = _llm_settings._load_debate_config(settings)

        assert merged["procon"]["synthesis_model"] == "claude-sonnet"
        assert merged["procon"]["synthesis_temperature"] == 0.5

    def test_concentration_threshold_out_of_range_falls_back(self):
        """集中度问答阈值越出 (0, 1) 时回退出厂默认。"""
        settings = {"debate": {"concentration_qa": {"threshold": 1.5}}}

        merged = _llm_settings._load_debate_config(settings)

        assert (
            merged["concentration_qa"]["threshold"]
            == _llm_settings._DEBATE_CONFIG_DEFAULTS["concentration_qa"]["threshold"]
        )


class TestCheckUnknownKeys:
    def test_unknown_key_is_warned(self, caplog):
        """未知键名告警点名具体键（帮用户找出拼写错误）。"""
        with caplog.at_level("WARNING", logger=_llm_settings.logger.name):
            _llm_settings._check_unknown_llm_keys({"bogus_settings_key": 1})

        assert any("bogus_settings_key" in record.getMessage() for record in caplog.records)


class TestEnsureLlmSettingsFile:
    def test_existing_file_is_left_untouched(self, tmp_path, monkeypatch):
        """设置文件已存在时不做任何创建动作。"""
        target = tmp_path / "llm_settings.json"
        target.write_text("{}", encoding="utf-8")
        writer = mock.Mock()
        monkeypatch.setattr("src.python.config._core.get_config", lambda: {"llm_settings_file": str(target)})
        monkeypatch.setattr("src.python.config._core._atomic_write", writer)

        _llm_settings._ensure_llm_settings_file()

        writer.assert_not_called()

    def test_create_failure_only_warns(self, tmp_path, monkeypatch, caplog):
        """自动创建失败（目录不可建）只告警，不阻断启动。"""
        target = tmp_path / "sub" / "llm_settings.json"
        monkeypatch.setattr("src.python.config._core.get_config", lambda: {"llm_settings_file": str(target)})
        monkeypatch.setattr(_llm_settings.os, "makedirs", mock.Mock(side_effect=OSError("read-only")))

        with caplog.at_level("WARNING", logger=_llm_settings.logger.name):
            _llm_settings._ensure_llm_settings_file()

        assert any("无法自动创建" in record.getMessage() for record in caplog.records)


class TestWriteLlmSettingsFaults:
    def test_schema_error_is_reraised(self, tmp_path):
        """落盘文件 schema 不符时记错误并向上抛（不得静默覆盖用户文件）。"""
        target = tmp_path / "llm_settings.json"
        target.write_text('{"schema_version": 999}', encoding="utf-8")

        with pytest.raises(_llm_settings._llm_schema.LLMSchemaError):
            _llm_settings.write_llm_settings({}, str(target))

    def test_directory_creation_failure_becomes_os_error(self, tmp_path, monkeypatch):
        """配置目录不可建时转成带目录名的 OSError。"""
        target = tmp_path / "sub" / "llm_settings.json"
        monkeypatch.setattr(_llm_settings.os, "makedirs", mock.Mock(side_effect=OSError("read-only")))

        with pytest.raises(OSError, match="无法创建配置目录"):
            _llm_settings.write_llm_settings({}, str(target))

    def test_structural_value_bypasses_text_patch(self, tmp_path):
        """dict/list 型设置走结构重排（不做文本 patch），且值确实落盘。"""
        target = tmp_path / "llm_settings.json"
        target.write_text(_llm_settings._get_default_llm_settings_template(), encoding="utf-8")

        _llm_settings.write_llm_settings({"debate": {"procon": {"synthesis_temperature": 0.7}}}, str(target))

        flat = _llm_settings._load_settings_document(target.read_text(encoding="utf-8"), str(target))
        assert flat["debate"]["procon"]["synthesis_temperature"] == pytest.approx(0.7)

    def test_invalid_patched_text_falls_back_to_structural_rewrite(self, tmp_path, monkeypatch):
        """文本 patch 结果非法时放弃 patch，改走结构重排（不得写入坏文本）。"""
        target = tmp_path / "llm_settings.json"
        target.write_text(_llm_settings._get_default_llm_settings_template(), encoding="utf-8")
        monkeypatch.setattr(_llm_settings._llm_schema, "patch_document_text", lambda raw, updates: "{broken")

        _llm_settings.write_llm_settings({"debate": {"procon": {"synthesis_temperature": 0.6}}}, str(target))

        flat = _llm_settings._load_settings_document(target.read_text(encoding="utf-8"), str(target))
        assert flat["debate"]["procon"]["synthesis_temperature"] == pytest.approx(0.6)

    def test_illegal_patch_candidate_is_discarded(self, tmp_path, monkeypatch):
        """标量 patch 结果非合法 JSON 时丢弃 candidate，走结构重排。"""
        target = tmp_path / "llm_settings.json"
        target.write_text(_llm_settings._get_default_llm_settings_template(), encoding="utf-8")
        monkeypatch.setattr(_llm_settings._llm_schema, "patch_document_text", lambda raw, updates: "{broken")

        _llm_settings.write_llm_settings({"model_claude": "claude-sonnet-test"}, str(target))

        flat = _llm_settings._load_settings_document(target.read_text(encoding="utf-8"), str(target))
        assert flat["model_claude"] == "claude-sonnet-test"

    def test_unchanged_scalar_is_not_rewritten(self, tmp_path):
        """值未变化时不进入 patch 列表（二次写入幂等）。"""
        target = tmp_path / "llm_settings.json"
        target.write_text(_llm_settings._get_default_llm_settings_template(), encoding="utf-8")
        _llm_settings.write_llm_settings({"model_claude": "claude-sonnet-test"}, str(target))
        before = target.read_text(encoding="utf-8")

        _llm_settings.write_llm_settings({"model_claude": "claude-sonnet-test"}, str(target))

        assert target.read_text(encoding="utf-8") == before


# ══════════════════════════════════════════════════════════════
# _llm_providers
# ══════════════════════════════════════════════════════════════


class TestProviderPathFallback:
    def test_config_failure_falls_back_to_default_providers_path(self, monkeypatch):
        """config.json 取值异常时回退内置默认路径（配置层损坏不阻断读凭据）。"""
        monkeypatch.setattr("src.python.config.get_config", mock.Mock(side_effect=TypeError("bad config")))

        assert _llm_providers._get_llm_providers_path() == _llm_providers._LLM_PROVIDERS_FILE_DEFAULT

    def test_config_failure_falls_back_to_default_key_path(self, monkeypatch):
        """config.json 取值异常时凭据文件回退内置默认路径。"""
        monkeypatch.setattr("src.python.config.get_config", mock.Mock(side_effect=KeyError("llm_key_file")))

        assert _llm_providers._get_llm_key_path() == _llm_providers._LLM_KEY_FILE_DEFAULT


class TestWriteKeyDocumentFaults:
    def test_unwritable_directory_raises(self, monkeypatch):
        """凭据目录不可建时报错（交互式配置最后一环，不能留半成品）。"""
        monkeypatch.setattr(_llm_providers, "_get_llm_key_path", lambda: "/nonexistent-dir/llm_key.json")
        monkeypatch.setattr(_llm_providers.os, "makedirs", mock.Mock(side_effect=OSError("read-only")))

        with pytest.raises(OSError):
            _llm_providers._write_key_document({"default": {"api_key": "k"}})

    def test_chmod_unsupported_is_ignored(self, tmp_path, monkeypatch):
        """chmod 失败（如 Windows 不支持完整权限位）时忽略，凭据照常写出。"""
        key_path = tmp_path / "llm_key.json"
        monkeypatch.setattr(_llm_providers, "_get_llm_key_path", lambda: str(key_path))
        monkeypatch.setattr(_llm_providers.os, "chmod", mock.Mock(side_effect=OSError("not supported")))

        _llm_providers._write_key_document({"default": {"api_key": "sk-test"}})

        assert json.loads(key_path.read_text(encoding="utf-8"))["default"]["api_key"] == "sk-test"


class TestLoadKeyCredentialsFaults:
    def test_non_object_root_returns_none(self, tmp_path, monkeypatch):
        """llm_key.json 根元素不是对象时忽略文件（返回 None）。"""
        key_path = tmp_path / "llm_key.json"
        key_path.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(_llm_providers, "_get_llm_key_path", lambda: str(key_path))

        assert _llm_providers._load_llm_key_credentials() is None

    def test_read_failure_returns_none(self, tmp_path, monkeypatch):
        """凭据文件读取/解析失败时返回 None（调用方按无凭据处理）。"""
        key_path = tmp_path / "llm_key.json"
        key_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(_llm_providers, "_get_llm_key_path", lambda: str(key_path))
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("locked")))

        assert _llm_providers._load_llm_key_credentials() is None


class TestProviderEntryValidation:
    def test_optional_field_type_errors_are_warned(self):
        """model/endpoint 类型非法只告警（可选字段错误不拒收整条线路）。"""
        warnings = _llm_providers._validate_provider_entry(
            {
                "name": "p1",
                "provider": "claude",
                "credentials_ref": "default",
                "model": 123,
                "endpoint": 456,
            }
        )

        assert len(warnings) == 2, "必填字段齐备时只剩两个可选字段的类型告警"
        assert any("model" in message for message in warnings)
        assert any("endpoint" in message for message in warnings)


class TestParseProvidersList:
    def test_empty_provider_array_is_invalid(self):
        """providers 数组为空时判为无效（无线路可用）。"""
        assert _llm_providers._parse_providers_list({"providers": []}) is None


class TestWriteLlmProvidersChmod:
    def test_chmod_unsupported_is_ignored(self, tmp_path, monkeypatch):
        """线路文件 chmod 失败时忽略（Windows 不支持完整权限位），写入照常完成。"""
        target = tmp_path / "llm_providers.json"
        monkeypatch.setattr(_llm_providers.os, "chmod", mock.Mock(side_effect=OSError("not supported")))

        _llm_providers.write_llm_providers({"schema_version": 2, "providers": []}, str(target))

        assert target.exists()


# ══════════════════════════════════════════════════════════════
# _llm_pricing
# ══════════════════════════════════════════════════════════════


class TestMergeModelFaults:
    def test_supported_currency_is_upper_cased(self):
        """受支持币种归一为大写后写入。"""
        merged = _llm_pricing._merge_model({"input_price": 1.0, "currency": " usd "}, "m")

        assert merged["currency"] == "USD"

    def test_unsupported_currency_keeps_builtin(self):
        """非白名单币种只告警，沿用内置币种。"""
        merged = _llm_pricing._merge_model({"currency": "BTC"}, "m")

        assert merged.get("currency") != "BTC"

    def test_non_object_peak_is_ignored(self):
        """peak 段不是对象时忽略，基础价照常合并。"""
        merged = _llm_pricing._merge_model({"input_price": 2.0, "peak": "8-10"}, "m")

        assert merged["input"] == 2.0
        assert "peak" not in merged or merged["peak"] != "8-10"


class TestMergedModels:
    def test_non_object_models_section_keeps_builtin_prices(self):
        """models 段不是对象时告警并只用内置价。"""
        merged = _llm_pricing._merged_models({"models": ["bad"]})

        assert merged == {model: dict(prices) for model, prices in _llm_pricing.MODEL_PRICING.items()}


class TestParsePeriodsFaults:
    def test_non_list_returns_none(self):
        """时段入参不是列表时返回 None（调用方沿用默认时段）。"""
        assert _llm_pricing._parse_periods("09:30-11:30") is None

    def test_item_without_separator_returns_none(self):
        """单个时段文本缺连字符时整体非法。"""
        assert _llm_pricing._parse_periods(["09:30-11:30", "13:00"]) is None

    def test_non_numeric_text_returns_none(self):
        """时段文本数值段无法解析时返回 None（不抛异常）。"""
        assert _llm_pricing._parse_periods(["aa:30-bb:00"]) is None


class TestPolicyFromRef:
    def test_unsupported_top_level_currency_warns(self):
        """顶层币种不在白名单时告警并沿用默认币种。"""
        policy = _llm_pricing._policy_from_ref({"currency": "BTC"}, _llm_pricing._default_policy())

        assert policy["currency"] == _llm_pricing._default_policy()["currency"]

    def test_invalid_idle_periods_keeps_default(self):
        """idle_periods 格式非法时告警并沿用默认时段。"""
        policy = _llm_pricing._policy_from_ref({"idle_periods": ["bad"]}, _llm_pricing._default_policy())

        assert policy["idle_periods"] == _llm_pricing._default_policy()["idle_periods"]


class TestLoadPricingConfigFaults:
    def test_non_object_root_falls_back_to_builtin(self, tmp_path, monkeypatch):
        """根元素不是对象时回退内置价，不抛出（报告生成不受阻）。"""
        target = tmp_path / "llm_pricing_ref.json"
        target.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(_llm_pricing, "PRICING_FILE", str(target))

        config = _llm_pricing.load_pricing_config()

        assert config["models"] == {model: dict(prices) for model, prices in _llm_pricing.MODEL_PRICING.items()}

    def test_unreadable_file_falls_back_to_builtin(self, tmp_path, monkeypatch):
        """文件读取期 JSON 解析失败时回退内置价并告警。"""
        target = tmp_path / "llm_pricing_ref.json"
        target.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(_llm_pricing, "PRICING_FILE", str(target))

        config = _llm_pricing.load_pricing_config()

        assert config["models"] == {model: dict(prices) for model, prices in _llm_pricing.MODEL_PRICING.items()}
