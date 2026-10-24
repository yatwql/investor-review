"""配置稳态与回退演练契约（配置面稳态要求的机检载体）。

设计文档「配置面演进策略」的落地要求：四类路径必须有可复跑的证据，
且**不得静默回落**——

1. **非法配置**：报错含「文件名 + 键 + 原因」，程序不静默改用默认值；
2. **删除配置文件**：生成器按当前模板重建，重建后加载正常（三份逐一验证：
   `llm_settings.json` / `logger.json` / `llm_pricing_ref.json`）；
3. **清空缓存**：首轮未命中 → 计算后写入 → 次轮命中（观测数值由 `cache` 统计接口给出）；
4. **非当前结构**：明确拒绝并给出「删除后重新生成」指引（只认当前 schema）。

全部用例使用 `tmp_path` 重定向配置/缓存路径，不触碰 `data/config/`、`data/cache/`。
"""

from __future__ import annotations

import json
import logging

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestInvalidConfigNotSilent:
    def test_llm_settings_version_mismatch_reports_file_and_reason(self, tmp_path, monkeypatch, caplog):
        """非法 schema_version → 日志含文件名与原因，且加载返回 None（不静默用默认值）。"""
        import src.python.config._llm_settings as ls

        path = tmp_path / "llm_settings.json"
        path.write_text(json.dumps({"schema_version": 1, "modules": {}}), encoding="utf-8")
        monkeypatch.setattr(ls, "get_llm_settings_path", lambda: str(path))

        with caplog.at_level(logging.ERROR):
            snapshot = ls.read_llm_settings_file()

        assert snapshot is None, "结构不符必须拒绝加载，不得静默回落默认值"
        text = caplog.text
        assert "llm_settings.json" in text and "schema_version" in text, text

    def test_logger_invalid_value_logs_key_and_range(self, tmp_path, caplog):
        """logger.json 非法取值 → 告警含键名与合法取值，单键回落默认（其余键不受影响）。"""
        from src.python.config._logging import read_logger_config

        path = tmp_path / "logger.json"
        path.write_text(
            json.dumps({"version": 1, "file": {"level": "NOISY"}, "console": {"level": "WARNING"}}),
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            values = read_logger_config(str(path))

        assert values["level"] == "INFO", "非法键回落默认值"
        assert values["console_level"] == "WARNING", "其余键按文件生效（只降级受影响键）"
        assert "level" in caplog.text and "NOISY" in caplog.text, caplog.text

    def test_pricing_version_mismatch_logs_and_falls_back(self, tmp_path, monkeypatch, caplog):
        """计价参考 version 不符 → 记录错误并回退内置价（报告仍可生成，不静默吞掉原因）。"""
        import src.python.config._llm_pricing as lp

        path = tmp_path / "llm_pricing_ref.json"
        path.write_text(json.dumps({"version": 9, "models": {}}), encoding="utf-8")
        monkeypatch.setattr(lp, "_cache", None)
        monkeypatch.setattr(lp, "get_llm_pricing_path", lambda: str(path))

        with caplog.at_level(logging.ERROR):
            config = lp.load_pricing_config()
        assert config["models"], "版本不符时回退内置价（不阻断报告）"
        assert "llm_pricing_ref.json" in caplog.text and "version" in caplog.text, caplog.text


class TestDeletedConfigRebuilds:
    def test_llm_settings_template_rebuilds_and_loads(self, tmp_path, monkeypatch):
        from src.python.config._llm_settings import read_llm_settings_file
        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

        path = tmp_path / "llm_settings.json"
        path.write_text(_get_default_llm_settings_template(), encoding="utf-8")
        import src.python.config._llm_settings as ls

        monkeypatch.setattr(ls, "get_llm_settings_path", lambda: str(path))
        snapshot = read_llm_settings_file()
        assert snapshot is not None, "生成器重建后必须能加载"
        assert "enabled_llm" in snapshot[0], "展平视图应含模块启停键（模板三层缺省合并生效）"

    def test_logger_file_recreated_and_loadable(self, tmp_path):
        from src.python.config._logging import ensure_logger_file, read_logger_config

        path = tmp_path / "logger.json"
        assert ensure_logger_file(str(path)) is True, "缺失时应写入默认模板"
        values = read_logger_config(str(path))
        assert values["level"] == "INFO" and values["path"].startswith("/")
        assert ensure_logger_file(str(path)) is False, "已存在时不重复写（幂等）"

    def test_pricing_template_rebuilds_and_loads(self, tmp_path, monkeypatch):
        import src.python.config._llm_pricing as lp

        path = tmp_path / "llm_pricing_ref.json"
        path.write_text(lp.render_default_pricing_ref(), encoding="utf-8")
        monkeypatch.setattr(lp, "PRICING_FILE", str(path))
        config = lp.load_pricing_config()
        assert config["models"], "默认模板应可加载（含内置模型价）"
        assert config["currency"] == "CNY"


class TestCacheFirstRunThenHit:
    def test_first_access_misses_then_second_hits(self, tmp_path, monkeypatch):
        """清空缓存 → 首轮未命中（全量重算）→ 写入后次轮命中。"""
        import src.python.cache as cache

        # 缓存目录隔离由 conftest 的 _isolate_sensitive_paths 统一提供（_paths/_stats/_store 各持
        # 一份 _CACHE_DIR 常量，逐处重定向易与 conftest 冲突）；此处只验证「未命中 → 写入 → 命中」语义
        key = "llm_unit_demo_key"
        assert cache.get(key, 3600) is None, "首轮应为未命中（触发计算）"
        cache.set(key, [{"demo": 1}])
        assert cache.get(key, 3600) == [{"demo": 1}], "写入后次轮应命中"
        stats = cache.get_cache_stats()
        assert stats["total_files"] >= 1


class TestNonCurrentStructureRejected:
    @pytest.mark.parametrize(
        "payload, expect",
        [
            ({"defaults": {}, "modules": {}}, "schema_version"),
            ({"schema_version": 3, "modules": {}}, "只接受 2"),
            ([], "不是 JSON 对象"),
        ],
    )
    def test_llm_settings_rejects_non_current_structure(self, payload, expect, tmp_path, monkeypatch):
        """非当前结构一律拒绝，并在消息里给出「删除后重新生成」指引。"""
        import src.python.config._llm_settings as ls

        path = tmp_path / "llm_settings.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(ls, "get_llm_settings_path", lambda: str(path))

        assert ls.read_llm_settings_file() is None
        with pytest.raises(Exception) as exc:
            from src.python.config._llm_schema import validate_document

            validate_document(json.loads(path.read_text(encoding="utf-8")), filename="llm_settings.json")
        message = str(exc.value)
        assert expect in message, message
        assert "重新生成" in message, message
