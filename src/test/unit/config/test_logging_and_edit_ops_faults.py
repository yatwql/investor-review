"""日志配置读写与配置编辑校验的错误路径测试。

覆盖契约（`config/_logging.py`）：
  - `validate_value` / `write_logger_config` 拒绝未知键（不留半写文件）
  - `read_logger_config` 读失败或根元素非对象时回落默认配置（不阻断启动）
  - `write_logger_config` 对 path 写法做绝对化，并在「patch 结果非法」「写盘失败」时报错
  - `_patch_values` 在文本里定位不到键位置时返回 None（调用方改走模板重排）

覆盖契约（`config/edit_ops.py`）：
  - 未知目标文件 / 未知写入原语 / 未知值类型 / 未知键 / 动作型键均抛 ConfigEditError
  - 整数键拒绝非整数浮点（不静默取整）
  - 对比指数删除与线路重排在参数不可用时报错
  - 调度字段校验与设置走专用入口，未知字段报 ValueError
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.python.config import _logging, edit_ops

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


# ══════════════════════════════════════════════════════════════
# _logging
# ══════════════════════════════════════════════════════════════


class TestValidateValueUnknownKey:
    def test_unknown_key_is_rejected(self):
        """未知日志配置键直接拒绝（避免写入无人读取的字段）。"""
        with pytest.raises(_logging.LoggerConfigError, match="未知日志配置键"):
            _logging.validate_value("not_a_logging_key", 1)


class TestReadLoggerConfigFallback:
    def test_unreadable_file_falls_back_to_defaults(self, tmp_path):
        """日志配置读取失败时回落到出厂默认（只告警，不阻断启动）。"""
        target = tmp_path / "logger.json"
        target.write_text("{not json", encoding="utf-8")

        values = _logging.read_logger_config(str(target))

        assert values["level"] == _logging.DEFAULTS["level"]
        assert values["path"]  # 默认路径已绝对化

    def test_non_object_root_falls_back_to_defaults(self, tmp_path):
        """根元素不是 JSON 对象时同按默认处理。"""
        target = tmp_path / "logger.json"
        target.write_text("[]", encoding="utf-8")

        values = _logging.read_logger_config(str(target))

        assert values["level"] == _logging.DEFAULTS["level"]


class TestWriteLoggerConfigFaults:
    def test_unknown_key_is_rejected(self, tmp_path):
        """写入未知键直接拒绝，原文件保持不变。"""
        target = tmp_path / "logger.json"
        target.write_text(_logging.render_default_logger_config(), encoding="utf-8")
        before = target.read_text(encoding="utf-8")

        with pytest.raises(_logging.LoggerConfigError, match="未知日志配置键"):
            _logging.write_logger_config({"not_a_logging_key": 1}, str(target))

        assert target.read_text(encoding="utf-8") == before

    def test_path_update_is_absolutized(self, tmp_path):
        """写入 path 时按项目根绝对化（落盘值可跨 cwd 稳定解析）。"""
        target = tmp_path / "logger.json"
        target.write_text(_logging.render_default_logger_config(), encoding="utf-8")

        values = _logging.write_logger_config({"path": "logs/app.log"}, str(target))

        assert values["path"] == _logging._absolute_path("logs/app.log")

    def test_invalid_patched_text_is_rejected(self, tmp_path, monkeypatch):
        """patch 结果不是合法 JSON 时报错（避免把坏文本写进配置）。"""
        target = tmp_path / "logger.json"
        target.write_text(_logging.render_default_logger_config(), encoding="utf-8")
        monkeypatch.setattr(_logging, "_patch_values", lambda raw, updates: "{broken")

        with pytest.raises(_logging.LoggerConfigError, match="写回结果非法"):
            _logging.write_logger_config({"level": "DEBUG"}, str(target))

    def test_write_failure_is_reported(self, tmp_path, monkeypatch):
        """原子写失败时转成 LoggerConfigError（提示检查目录权限）。"""
        target = tmp_path / "logger.json"
        target.write_text(_logging.render_default_logger_config(), encoding="utf-8")
        monkeypatch.setattr(_logging, "write_text_atomic", mock.Mock(return_value=False))

        with pytest.raises(_logging.LoggerConfigError, match="写入失败"):
            _logging.write_logger_config({"level": "DEBUG"}, str(target))


class TestPatchValuesLocating:
    def test_unlocatable_key_returns_none(self):
        """文本中定位不到键位置时返回 None（调用方改走模板重排）。"""
        assert _logging._patch_values('{\n  "file": {}\n}', {"level": "DEBUG"}) is None


# ══════════════════════════════════════════════════════════════
# edit_ops
# ══════════════════════════════════════════════════════════════


class TestUnknownTargetAndWriter:
    def test_unknown_target_file_is_rejected(self):
        """未知目标配置文件报错（备份/写入都以目标文件为前提）。"""
        with pytest.raises(edit_ops.ConfigEditError, match="未知配置目标文件"):
            edit_ops._target_path("not_a_target")

    def test_unknown_write_primitive_is_rejected(self):
        """白名单条目声明了未知写入原语时报错（不静默跳过写入）。"""
        with pytest.raises(edit_ops.ConfigEditError, match="未知写入原语"):
            edit_ops._dispatch_write({"writer": "not_a_writer", "target": "config"}, "k", 1)


class TestValueNormalizationFaults:
    def test_int_kind_rejects_non_integral_float(self):
        """整数键传 1.5 时报错，不做静默取整。"""
        with pytest.raises(edit_ops.ConfigEditError, match="应为整数"):
            edit_ops._coerce_number("k", 1.5, "int", {})

    def test_unsupported_kind_is_rejected(self):
        """白名单声明了未知值类型时报错（避免漏校验直接落盘）。"""
        with pytest.raises(edit_ops.ConfigEditError, match="不支持的值类型"):
            edit_ops._normalize_plain_value("k", 1, {"kind": "not_a_kind"})


class TestComparisonIndexActionFaults:
    def test_remove_with_empty_code_is_rejected(self):
        """删除对比指数时缺代码报错。"""
        entry = {"actions": ("add", "remove", "reset")}

        with pytest.raises(edit_ops.ConfigEditError, match="代码不能为空"):
            edit_ops._apply_comparison_action({"action": "remove", "code": "  "}, entry)


class TestLlmProviderReorderFaults:
    def test_no_valid_provider_is_rejected(self, monkeypatch):
        """线路配置里没有有效条目时拒绝重排（先修配置再重排）。"""
        monkeypatch.setattr("src.python.config._llm_providers._load_llm_providers", lambda: {"providers": []})

        with pytest.raises(edit_ops.ConfigEditError, match="无有效线路"):
            edit_ops._apply_llm_provider_action({"action": "reorder", "order": ["a"]}, {"actions": ("reorder",)})


class TestPreviewAndReadFaults:
    def test_preview_unknown_key_is_rejected(self):
        """预览未知白名单键报错。"""
        with pytest.raises(edit_ops.ConfigEditError, match="不在白名单"):
            edit_ops.preview_config_edit({"key": "not.a.key", "value": 1})

    def test_preview_action_key_is_rejected(self):
        """动作型键不能当标量赋值（须走专用入口）。"""
        with pytest.raises(edit_ops.ConfigEditError, match="动作型键"):
            edit_ops.preview_config_edit({"key": "comparison_indices", "action": "reset"})

    def test_read_unknown_key_is_rejected(self):
        """读取未知白名单键报错。"""
        with pytest.raises(edit_ops.ConfigEditError, match="不在白名单"):
            edit_ops.read_config_value("not.a.key")

    def test_read_with_unknown_writer_is_rejected(self, monkeypatch):
        """白名单条目声明未知写入目标时读取报错。"""
        monkeypatch.setitem(edit_ops.config_edit_whitelist, "fake.key", {"writer": "not_a_writer"})

        with pytest.raises(edit_ops.ConfigEditError, match="未知写入目标"):
            edit_ops.read_config_value("fake.key")


class TestSchedulerFieldEntryPoints:
    def test_validate_scheduler_value_accepts_known_field(self):
        """已知调度字段经专用校验入口返回归一化值。"""
        assert edit_ops.validate_scheduler_value("report_type", "full") == "full"

    def test_set_unknown_scheduler_field_is_rejected(self):
        """未知调度字段报 ValueError（不做隐式字段创建）。"""
        with pytest.raises(ValueError, match="未知调度字段"):
            edit_ops.set_scheduler_field("not_a_field", 1)
