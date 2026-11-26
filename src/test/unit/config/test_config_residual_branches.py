"""config 域残余分支：防御容器重建 / 注册表未登记 / 本地状态损坏 / 覆盖路径。

这些分支都只在「输入不合约」时才走到（非法槽位、未知键、损坏文件），正常路径的用例
覆盖不到，故集中在此补齐；每条都断言分支的对外行为（返回值或异常），不依赖日志文案。
"""

from __future__ import annotations

import pytest

from src.python.config import _config_defaults, _llm_settings_defaults, _local_state, _validation_llm
from src.python.config import _validation_sections
from src.python.config.anonymizer import _blur_shares
from src.python.config.chapter_registry import (
    SOURCE_LLM,
    chapter_label,
    chapter_number,
    chapter_registry,
)
from src.python.core.models import Holding

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestSanitizeDocumentDefensiveContainers:
    """模块段里的 debate/procon 不是对象时，回落要在原处重建容器而不是崩掉。"""

    def test_non_dict_debate_and_procon_are_rebuilt(self, monkeypatch):
        # 真实判据下 debate 非对象 ⇒ 取值恒 None ⇒ 不构成越界，故用判据桩强制进入回落分支
        monkeypatch.setattr(_validation_llm, "param_violation", lambda param, value: "越界")
        document = {"modules": {"m": {"debate": "不是对象"}}}

        sanitized, issues = _validation_llm.sanitize_document(document, {})

        debate = sanitized["modules"]["m"]["debate"]
        assert isinstance(debate, dict) and isinstance(debate["procon"], dict)
        assert "synthesis_temperature" in debate["procon"]
        assert any("已回落出厂默认" in issue for issue in issues)


class TestChapterRegistryLookups:
    def test_unknown_chapter_key_raises_key_error(self):
        with pytest.raises(KeyError, match="未登记"):
            chapter_number("no_such_chapter")

    def test_llm_chapter_without_label_resolves_from_module_names(self):
        entry = next(e for e in chapter_registry if e.source == SOURCE_LLM and not e.label)

        label = chapter_label(entry)

        assert label != entry.key  # 取自 LLM 模块名注册表，而不是退回键名


class TestLocalStateCorruption:
    def test_corrupt_state_file_reads_as_empty_dict(self, monkeypatch, tmp_path):
        state_file = tmp_path / "local_state.json"
        state_file.write_text("{不是 JSON", encoding="utf-8")
        monkeypatch.setattr(_local_state, "_LOCAL_STATE_FILE", str(state_file))

        assert _local_state.get_local_state() == {}


class TestLlmSettingsDefaultsEdges:
    def test_missing_path_returns_none(self):
        assert _llm_settings_defaults.get_llm_setting_default("runtime.no_such_key") is None

    def test_dump_block_renders_empty_dict_on_one_line(self):
        assert _llm_settings_defaults._dump_block({}, 2) == ["  {}"]


class TestAnonymizerMinimumUnit:
    def test_nonzero_shares_below_minimum_bump_to_one_unit(self):
        holdings = [Holding(account="a", name="某基金", code="005827", shares=120.0, cost_price=1.0)]

        _blur_shares(holdings)

        assert holdings[0].shares == 100


class TestValidationSectionsNonDictSection:
    def test_non_dict_history_section_keeps_issue_count(self):
        assert _validation_sections._validate_history_lookback_days({"history": "坏段"}, 2) == 2


class TestConfigPathOverride:
    def test_override_wins_over_default_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_config_defaults, "_CONFIG_PATH_OVERRIDE", None)
        target = tmp_path / "custom.json"

        _config_defaults.set_config_path_override(str(target))

        assert _config_defaults.get_config_path() == str(target)

    def test_seed_isolation_clears_leaked_override(self, monkeypatch, tmp_path):
        """路径覆写优先于 _CONFIG_FILE：上一条用例遗留的覆写必须被隔离 seed 清掉，
        否则本轮读写落到别的用例的目录（跨用例配置串读）。"""
        from src.python.config import get_config_path
        from src.test._path_isolation import seed_sensitive_path_isolation

        monkeypatch.setattr(_config_defaults, "_CONFIG_PATH_OVERRIDE", "/leaked/config.json")
        probe_targets = [
            ("输出目录", str(tmp_path / "reports")),
            ("缓存目录", str(tmp_path / "data/cache")),
            ("日志目录", str(tmp_path / "logs")),
        ]

        seed_sensitive_path_isolation(monkeypatch, tmp_path, probe_targets)

        assert _config_defaults._CONFIG_PATH_OVERRIDE is None
        assert get_config_path().startswith(str(tmp_path)), "有效路径须回到本轮隔离目录"
