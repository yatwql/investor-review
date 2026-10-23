"""logger.json：默认生成、加载回落、保存拒绝、env 优先级、轮转参数、不可写降级、颜色降级。"""

from __future__ import annotations

import json
import logging
import os

import pytest

from src.python.config import _logging
from src.python.core import logger as logger_mod

pytestmark = pytest.mark.unit_config


@pytest.fixture
def logger_file(tmp_path, monkeypatch):
    path = tmp_path / "logger.json"
    monkeypatch.setattr(_logging, "LOGGER_CONFIG_PATH", str(path))
    monkeypatch.setattr(_logging, "get_logger_config_path", lambda: str(path))
    return path


@pytest.mark.unit
class TestLoadAndDefaults:
    def test_missing_file_uses_defaults(self, logger_file):
        config = _logging.read_logger_config()

        assert config["level"] == "INFO"
        assert config["max_bytes"] == 10 * 1024 * 1024
        assert config["backup_count"] == 5
        assert config["viewer_level"] == "INFO"
        assert os.path.isabs(config["path"])

    def test_generated_file_has_comments_and_parses(self):
        text = _logging.render_default_logger_config()
        from src.python.core.json_comments import loads

        assert loads(text)["version"] == 1
        assert "写盘" in text and "控制台" in text

    def test_invalid_values_warn_and_fall_back(self, logger_file, caplog):
        logger_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "file": {"level": "LOUD", "max_bytes": 1},
                    "console": {"color": "yes"},
                    "viewer": {"tail_lines": 999999},
                }
            ),
            encoding="utf-8",
        )

        with caplog.at_level("WARNING"):
            config = _logging.read_logger_config()

        assert config["level"] == "INFO"
        assert config["max_bytes"] == 10 * 1024 * 1024
        assert config["console_color"] is True
        assert config["tail_lines"] == 500
        assert caplog.records

    def test_version_mismatch_rejected_with_guidance(self, logger_file):
        logger_file.write_text(json.dumps({"version": 2}), encoding="utf-8")

        with pytest.raises(_logging.LoggerConfigError) as err:
            _logging.read_logger_config()

        assert "logger.json" in str(err.value)
        assert "version=2" in str(err.value)
        assert "重新生成" in str(err.value)


@pytest.mark.unit
class TestWrite:
    def test_write_preserves_comments_and_updates_value(self, logger_file):
        logger_file.write_text(_logging.render_default_logger_config(), encoding="utf-8")

        result = _logging.write_logger_config({"level": "DEBUG", "backup_count": 3})

        raw = logger_file.read_text(encoding="utf-8")
        assert "写盘" in raw and "控制台" in raw
        assert '"level": "DEBUG"' in raw
        assert '"backup_count": 3' in raw
        assert result["level"] == "DEBUG"

    @pytest.mark.parametrize(
        ("updates", "expected"),
        [
            ({"level": "LOUD"}, "level"),
            ({"max_bytes": 10}, "max_bytes"),
            ({"backup_count": 99}, "backup_count"),
            ({"tail_lines": "many"}, "tail_lines"),
            ({"path": "../secret.log"}, "path"),
            ({"console_color": "yes"}, "console_color"),
        ],
    )
    def test_invalid_write_rejected_and_file_unchanged(self, logger_file, updates, expected):
        raw = _logging.render_default_logger_config()
        logger_file.write_text(raw, encoding="utf-8")

        with pytest.raises(_logging.LoggerConfigError) as err:
            _logging.write_logger_config(updates)

        assert expected in str(err.value)
        assert logger_file.read_text(encoding="utf-8") == raw


@pytest.mark.unit
class TestEnvPriority:
    def _prepare(self, tmp_path, monkeypatch, name: str, *, level="WARNING", console="WARNING"):
        path = tmp_path / "logger.json"
        path.write_text(
            _logging.render_default_logger_config()
            .replace('"level": "INFO"', f'"level": "{level}"')
            .replace('"level": "INFO"', f'"level": "{console}"'),
            encoding="utf-8",
        )
        monkeypatch.setattr(logger_mod, "_LOGGER_CONFIG_PATH", str(path))
        logger_mod.reload_logger_config()
        monkeypatch.setattr(logger_mod, "_LOG_FILE", str(tmp_path / "app.log"))
        return logger_mod.setup_logger(name)

    def test_env_overrides_file_level(self, tmp_path, monkeypatch):
        monkeypatch.setenv(logger_mod._LOG_FILE_LEVEL_ENV, "DEBUG")
        logger = self._prepare(tmp_path, monkeypatch, "invest_env_override")
        file_handler = next(h for h in logger.handlers if hasattr(h, "baseFilename"))
        assert file_handler.level == logging.DEBUG

    def test_file_level_used_without_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv(logger_mod._LOG_FILE_LEVEL_ENV, raising=False)
        logger = self._prepare(tmp_path, monkeypatch, "invest_env_no_override")
        file_handler = next(h for h in logger.handlers if hasattr(h, "baseFilename"))
        assert file_handler.level == logging.WARNING


@pytest.mark.unit
class TestRotationAndDegradation:
    def test_rotation_params_from_config(self, tmp_path, monkeypatch):
        path = tmp_path / "logger.json"
        path.write_text(
            _logging.render_default_logger_config()
            .replace('"max_bytes": 10485760', '"max_bytes": 4096')
            .replace('"backup_count": 5', '"backup_count": 2'),
            encoding="utf-8",
        )
        monkeypatch.setattr(logger_mod, "_LOGGER_CONFIG_PATH", str(path))
        logger_mod.reload_logger_config()
        monkeypatch.setattr(logger_mod, "_LOG_FILE", str(tmp_path / "rot.log"))

        logger = logger_mod.setup_logger("invest_rotation")
        handler = next(h for h in logger.handlers if hasattr(h, "baseFilename"))

        assert handler.maxBytes == 4096
        assert handler.backupCount == 2

    def test_unwritable_log_dir_degrades_to_console(self, tmp_path, monkeypatch):
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")
        monkeypatch.setattr(logger_mod, "_LOG_FILE", str(blocker / "app.log"))

        logger = logger_mod.setup_logger("invest_unwritable")

        assert any(isinstance(h, logging.StreamHandler) and not hasattr(h, "baseFilename") for h in logger.handlers)
        assert not any(hasattr(h, "baseFilename") for h in logger.handlers)

    def test_console_color_disabled_uses_plain_formatter(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_mod, "_LOG_FILE", str(tmp_path / "plain.log"))
        monkeypatch.setattr(logger_mod, "_CONSOLE_COLOR", False)

        logger = logger_mod.setup_logger("invest_no_color")
        console = next(h for h in logger.handlers if not hasattr(h, "baseFilename"))

        record = logging.LogRecord("invest", logging.ERROR, __file__, 1, "红色的错误", (), None)
        formatted = console.formatter.format(record)
        assert "\033[" not in formatted
