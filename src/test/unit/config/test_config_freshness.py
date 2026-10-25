"""配置文件新旧对比（config._config_freshness）单元测试。

覆盖判据：模板缺的键/说明才报落后；用户自加注释与 JSON 字符串里的 ``//``
（如 ``https://api…``）不误报；文件不存在视为首次运行不报警。
"""

from __future__ import annotations

import pytest

from src.python.config import _config_freshness as fresh

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]

_TEMPLATE = """// 头部说明
{
  "alpha": 1,  // 甲的说明
  "beta": {"url": "https://example.com/x"}  // 乙的说明
}
"""


class TestCommentExtraction:
    """注释抽取：字符串内的 // 不算注释。"""

    def test_url_in_string_is_not_comment(self):
        assert "//example.com/x" not in fresh._comment_texts(_TEMPLATE)

    def test_doc_and_inline_comments_collected(self):
        texts = fresh._comment_texts(_TEMPLATE)
        assert {"头部说明", "甲的说明", "乙的说明"} <= texts

    def test_multiline_comment_collected(self):
        assert "多行说明" in fresh._comment_texts('{"a": 1}\n/* 多行说明 */\n')


class TestDiff:
    """单文件差异：缺键 / 缺说明分别计数。"""

    def test_missing_key_detected(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text('// 头部说明\n{"alpha": 1}  // 甲的说明\n', encoding="utf-8")
        diff = fresh._diff(str(target), _TEMPLATE)
        assert diff["missing_keys"] == ["beta"]
        assert diff["stale"] is True

    def test_missing_comment_only_detected(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text('{"alpha": 1, "beta": {"url": "https://example.com/x"}}\n', encoding="utf-8")
        diff = fresh._diff(str(target), _TEMPLATE)
        assert diff["missing_keys"] == []
        assert diff["missing_comments"]
        assert diff["stale"] is True

    def test_fresh_file_not_stale(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text(_TEMPLATE, encoding="utf-8")
        assert fresh._diff(str(target), _TEMPLATE)["stale"] is False

    def test_user_added_comment_is_not_staleness(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text(_TEMPLATE + "// 我自己加的备注\n", encoding="utf-8")
        assert fresh._diff(str(target), _TEMPLATE)["stale"] is False


class TestCheckConfigFreshness:
    """整体口径：缺失文件不报警（首次运行），落后文件逐条返回。"""

    def test_missing_files_are_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fresh, "_diff", lambda *a: (_ for _ in ()).throw(OSError("no file")))
        monkeypatch.setattr(
            "src.python.config._core.get_config", lambda: {"llm_settings_file": "", "llm_providers_file": ""}
        )
        monkeypatch.setattr("src.python.config._config_defaults.get_config_path", lambda: str(tmp_path / "none.json"))
        assert fresh.check_config_freshness() == []

    def test_stale_file_reported(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"alpha": 1}\n', encoding="utf-8")
        monkeypatch.setattr("src.python.config._config_defaults.get_config_path", lambda: str(cfg))
        monkeypatch.setattr("src.python.config._config_defaults._build_template_from_defaults", lambda: _TEMPLATE)
        monkeypatch.setattr(
            "src.python.config._core.get_config", lambda: {"llm_settings_file": "", "llm_providers_file": ""}
        )
        stale = fresh.check_config_freshness()
        assert len(stale) == 1
        assert stale[0]["missing_keys"] == ["beta"]
