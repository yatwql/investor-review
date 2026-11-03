"""旧配置键登记表（`config/_legacy_keys.py`）与两站点统一告警口径。

背景：用户按旧文档配了键这件事，原先三个站点各说一套——`report_section_order`
逐键告警后剔除、`features.json` 的无消费者开关汇成一条告警但仍写入运行时表、
数据源表只写「未知，将被忽略」。用户看不出「该填什么」。本文件锁定：
① 失效键分类（删掉的 / 换了称呼的 / 拼错的）由登记表单源判定；
② 两站点都经 `format_unknown_keys` 输出**一条**含处置建议的告警；
③ 各站点实际处置动作不被措辞统一改变（剔除 / 仍加载）。
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.python.config._legacy_keys import (
    REMOVED,
    RENAMED,
    classify_legacy_key,
    format_unknown_keys,
)
from src.python.config.features import FEATURE_FLAGS, load_feature_overrides

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestClassifyLegacyKey:
    def test_removed_key_explains_consequence(self):
        """已删除键 → 给出「配了也不生效」的原因（用户据此决定删不删）。"""
        kind, hint = classify_legacy_key("llm_usage")
        assert kind == "removed"
        assert "已删除" in hint and REMOVED["llm_usage"] in hint

    def test_unknown_key_flagged_as_typo(self):
        """未登记键 → 归「疑似拼写错误」（不是「已删除」，避免误导用户去找替代键）。"""
        kind, hint = classify_legacy_key("no_such_key_xyz")
        assert kind == "unknown"
        assert "拼写" in hint

    def test_renamed_key_points_to_new_name(self, monkeypatch):
        """改名的键 → 提示新键名（登记表是唯一来源）。"""
        monkeypatch.setitem(RENAMED, "old_name_demo", "new_name_demo")
        kind, hint = classify_legacy_key("old_name_demo")
        assert kind == "renamed"
        assert "new_name_demo" in hint and "改用" in hint


class TestFormatUnknownKeys:
    def test_single_line_sorted_dedup(self):
        """多键归并为一行、排序去重（日志可逐字比对，不随调用顺序漂移）。"""
        text = format_unknown_keys("features.json", ["b_ghost", "a_ghost", "b_ghost"])
        assert text.count("\n") == 0
        assert text.index("a_ghost") < text.index("b_ghost")
        assert text.count("b_ghost") == 1
        assert text.startswith("features.json 含 2 项无效/旧键：")

    def test_empty_returns_empty_string(self):
        """无无效键 → 空串（调用方据此免打日志）。"""
        assert format_unknown_keys("config.json", []) == ""


class TestReportSectionOrderUsesRegistry:
    """`report_section_order` 的无效键：仍从内存剔除，告警改走登记表文案。"""

    def test_unknown_section_dropped_and_warned_once(self, caplog):
        from src.python.config._validation_sections import _validate_report_section_order

        config = {"report_section_order": {"no_such_section": 3, "summary": 1}}
        with caplog.at_level("WARNING"):
            issues = _validate_report_section_order(config, 0)

        assert issues == 1, "无效键仍计 1 问题（文件层漂移要可见）"
        assert "no_such_section" not in config["report_section_order"], "无效键必须从内存剔除"
        assert config["report_section_order"] == {"summary": 1}
        warnings = [r.getMessage() for r in caplog.records if "无效/旧键" in r.getMessage()]
        assert len(warnings) == 1, "多个无效键合并为一条告警"
        assert "no_such_section" in warnings[0]
        assert "拼写" in warnings[0], "未登记键须给出处置建议（疑似拼写错误）"

    def test_llm_usage_listed_as_removed_not_unknown(self, caplog):
        """`llm_usage` 是已知「不该出现在排序表」的键 → 告警给已删除原因。"""
        from src.python.config._validation_sections import _validate_report_section_order

        config = {"report_section_order": {"llm_usage": 9}}
        with caplog.at_level("WARNING"):
            issues = _validate_report_section_order(config, 0)

        assert issues == 1
        assert config["report_section_order"] == {}
        text = "\n".join(r.getMessage() for r in caplog.records if "无效/旧键" in r.getMessage())
        assert "已删除" in text and REMOVED["llm_usage"] in text


class TestFeaturesUsesSameFormatter:
    """`features.json` 的无效开关：同样一条告警 + 处置建议，值仍加载（不报错）。"""

    def test_ghost_switch_warned_with_hint(self, tmp_path, caplog):
        path = tmp_path / "features.json"
        path.write_text(json.dumps({"no_such_switch_zzz": True}), encoding="utf-8")

        with (
            patch("src.python.config.features.FEATURES_FILE", str(path)),
            patch.dict(FEATURE_FLAGS, {}),
            caplog.at_level("WARNING"),
        ):
            load_feature_overrides()
            # 值仍加载（不报错），但没有任何消费点读取 → 告警是唯一反馈通道。
            # 断言必须在 patch.dict 块内：退出时运行期开关表按快照还原。
            assert FEATURE_FLAGS["no_such_switch_zzz"] is True, "口径统一不改处置动作"

        warnings = [r.getMessage() for r in caplog.records if "无效/旧键" in r.getMessage()]
        assert len(warnings) == 1
        assert "no_such_switch_zzz" in warnings[0] and "拼写" in warnings[0]
