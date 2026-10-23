"""JSONC 读取契约：五份配置文件都支持中文注释，读—改—写保留注释。"""

from __future__ import annotations

import json

import pytest

from src.python.config._comments import strip_json_comments
from src.python.core.json_comments import loads

pytestmark = pytest.mark.unit_config

_LLM_KEY_SAMPLE = """// LLM 凭据（单凭据格式）
{
  "api_key": "sk-test",   // 本机密钥
  "model": "claude-sonnet-4"
}
"""

_LLM_PROVIDERS_SAMPLE = """// 多链线路
{
  "providers": []   /* 空列表：走扁平 provider/api_key */
}
"""

_LLM_SETTINGS_SAMPLE = """// LLM 运行设置
{
  "enabled_llm": {"global_macro": false}   // 关掉全球政经
}
"""


@pytest.mark.unit
class TestConfigJsonComments:
    def test_config_json_with_comments_reads(self, tmp_path, monkeypatch):
        from src.python.config import _core, _config_defaults

        template = _config_defaults._get_default_config_template()
        raw = "// 分组说明：测试用\n/* 块注释\n   第二行 */\n" + template
        path = tmp_path / "config.json"
        path.write_text(raw, encoding="utf-8")
        monkeypatch.setattr(_config_defaults, "_CONFIG_PATH_OVERRIDE", str(path))
        monkeypatch.setattr(_core, "_config_cache", None)

        config = _core.get_config()

        assert "holdings_dir" in config

    def test_features_json_with_comments_reads(self, tmp_path, monkeypatch):
        import src.python.config.features as features

        path = tmp_path / "features.json"
        path.write_text(
            '// 分组：成本\n{\n  // 成本流水\n  "cost_lots": true\n}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(features, "FEATURES_FILE", str(path))
        features.reset_feature_flags()
        features.load_feature_overrides()

        assert features.is_feature_enabled("cost_lots") is True

    def test_llm_settings_file_with_comments_reads(self, tmp_path, monkeypatch):
        from src.python.config import _llm_settings

        path = tmp_path / "llm_settings.json"
        path.write_text(_LLM_SETTINGS_SAMPLE, encoding="utf-8")
        monkeypatch.setattr(_llm_settings, "get_llm_settings_path", lambda: str(path))

        loaded = _llm_settings.read_llm_settings_file()

        assert loaded is not None
        settings, shown_path = loaded
        assert settings["enabled_llm"]["global_macro"] is False
        assert shown_path == str(path)

    def test_llm_providers_with_comments_reads(self, tmp_path, monkeypatch):
        from src.python.config import _llm_providers

        path = tmp_path / "llm_providers.json"
        path.write_text(_LLM_PROVIDERS_SAMPLE, encoding="utf-8")
        monkeypatch.setattr(_llm_providers, "_get_llm_providers_path", lambda: str(path))

        config = _llm_providers._load_llm_providers()

        assert config == {"providers": []}

    def test_llm_key_with_comments_reads(self, tmp_path, monkeypatch):
        from src.python.config import _llm_providers

        path = tmp_path / "llm_key.json"
        path.write_text(_LLM_KEY_SAMPLE, encoding="utf-8")
        monkeypatch.setattr(_llm_providers, "_get_llm_key_path", lambda: str(path))

        creds = _llm_providers._load_llm_key_credentials()

        assert creds == {"_default": {"api_key": "sk-test", "model": "claude-sonnet-4"}}


@pytest.mark.unit
class TestFeaturesWritePreservesComments:
    def _seed(self, tmp_path, monkeypatch, raw: str):
        import src.python.config.features as features

        path = tmp_path / "features.json"
        path.write_text(raw, encoding="utf-8")
        monkeypatch.setattr(features, "FEATURES_FILE", str(path))
        features.reset_feature_flags()
        features.load_feature_overrides()
        return features, path

    def test_save_keeps_group_and_item_comments(self, tmp_path, monkeypatch):
        features, path = self._seed(
            tmp_path,
            monkeypatch,
            '// 分组：成本\n{\n  // 成本流水（逐笔买卖）\n  "cost_lots": false\n}\n',
        )

        features.save_feature_overrides({"cost_lots": True, "data_quality": False})

        raw = path.read_text(encoding="utf-8")
        assert "// 分组：成本" in raw
        assert "// 成本流水（逐笔买卖）" in raw
        assert loads(raw) == {"cost_lots": True, "data_quality": False}
        assert features.is_feature_enabled("cost_lots") is True

    def test_clear_removes_key_but_keeps_comments(self, tmp_path, monkeypatch):
        features, path = self._seed(
            tmp_path,
            monkeypatch,
            '// 分组：成本\n{\n  // 成本流水\n  "cost_lots": false,\n  "data_quality": true\n}\n',
        )

        removed = features.clear_feature_overrides(["cost_lots"])

        raw = path.read_text(encoding="utf-8")
        assert removed == 1
        assert "// 分组：成本" in raw
        assert "// 成本流水" in raw
        assert loads(raw) == {"data_quality": True}
        assert features.is_feature_enabled("cost_lots") is False  # 回出厂默认（默认关）

    def test_missing_file_created_with_chinese_comments(self, tmp_path, monkeypatch):
        features, path = self._seed(tmp_path, monkeypatch, "")
        path.unlink()
        features.reset_feature_flags()

        features.save_feature_overrides({"cost_lots": True})

        raw = path.read_text(encoding="utf-8")
        assert "// 功能开关覆写" in raw
        assert any("\u4e00" <= ch <= "\u9fff" for ch in raw)
        assert loads(raw) == {"cost_lots": True}

    def test_compact_single_line_file_is_rewritten_legibly(self, tmp_path, monkeypatch):
        features, path = self._seed(tmp_path, monkeypatch, '{"cost_lots": false, "data_quality": true}')

        features.clear_feature_overrides(["cost_lots"])

        raw = path.read_text(encoding="utf-8")
        assert "// 功能开关覆写" in raw
        assert loads(raw) == {"data_quality": True}

    def test_repo_default_template_is_valid_jsonc(self, tmp_path):
        """模板注释剥离后仍是合法 JSON（写入路径不会产出坏文件）。"""
        from src.python.config.features import _FEATURES_TEMPLATE

        assert json.loads(strip_json_comments(_FEATURES_TEMPLATE)) == {}
