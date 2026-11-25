"""功能开关覆写文件的降级支路：畸形文档、非法补丁与未登记开关。

覆写文件的容错口径是「坏了不阻断启动、写坏的补丁拒绝落盘、未登记开关只告警不
生效」；三条各自有唯一可观察产物（空覆写 / 文件未变 / 默认值保持），逐条断言。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.config import features as fx

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


def test_load_overrides_non_object_document_returns_empty_overrides(tmp_path):
    """覆写文件是合法 JSON 但不是对象 → 按空覆写处理（保留原文供覆写）。"""
    target = tmp_path / "features.json"
    target.write_text("[1, 2]", encoding="utf-8")

    with patch("src.python.config.features.FEATURES_FILE", str(target)):
        raw, overrides = fx._load_overrides_document()

    assert overrides == {}
    assert raw.strip() == "[1, 2]", "原文须原样返回，写入路径据此覆写"


def test_persist_overrides_rejects_illegal_patch(tmp_path):
    """补丁后结果非法 JSON → 拒绝写入（不覆盖掉用户原文件）。"""
    target = tmp_path / "features.json"

    with patch("src.python.config.features.FEATURES_FILE", str(target)):
        fx._persist_overrides("{not json", "测试")

    assert not target.exists()


def test_is_feature_enabled_unknown_flag_is_off():
    """未登记的开关名视为关闭（不因拼写错误而意外打开功能）。"""
    assert fx.is_feature_enabled("no_such_flag_at_all") is False


def test_set_feature_enabled_unknown_flag_is_ignored(monkeypatch):
    """未登记的开关名不可写入运行时表（避免自造出无消费者的键）。"""
    ghost = "no_such_flag_at_all"
    monkeypatch.delitem(fx.FEATURE_FLAGS, ghost, raising=False)

    fx.set_feature_enabled(ghost, True)

    assert ghost not in fx.FEATURE_FLAGS


def test_load_overrides_ignores_non_bool_value(tmp_path, monkeypatch):
    """覆写值不是 bool → 告警并忽略，开关保持当前值。"""
    flag = next(iter(fx._FEATURE_FLAGS_DEFAULT))
    target = tmp_path / "features.json"
    target.write_text('{"%s": "yes"}' % flag, encoding="utf-8")
    expected = fx._FEATURE_FLAGS_DEFAULT[flag]
    monkeypatch.setitem(fx.FEATURE_FLAGS, flag, expected)

    with patch("src.python.config.features.FEATURES_FILE", str(target)):
        fx.load_feature_overrides()

    assert fx.FEATURE_FLAGS[flag] is expected


def test_clear_all_overrides_drops_runtime_only_keys(tmp_path, monkeypatch):
    """「恢复全部默认」清空覆写后，运行时表里无代码默认的残留键一并移除。"""
    ghost = "runtime_only_switch"
    monkeypatch.setitem(fx.FEATURE_FLAGS, ghost, True)

    with patch("src.python.config.features.FEATURES_FILE", str(tmp_path / "features.json")):
        removed = fx.clear_feature_overrides()

    assert removed == 0, "文件不存在时无覆写键可移除"
    assert ghost not in fx.FEATURE_FLAGS
