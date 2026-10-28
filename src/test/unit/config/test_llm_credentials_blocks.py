"""命名凭据块契约 — llm_key.json 只接受 ``{ref: {api_key, ...}}`` 形态。

覆盖：
  - 命名凭据块正常加载（含 model / endpoint 可选字段）
  - 顶层 ``api_key``（单凭据旧形态）**直接拒绝**：不做迁移、不写备份、不改原文件
  - 拒绝时给出可执行的改写指引（错误日志含目标形态与 credentials_ref）
  - 非对象值（块内值不是 dict）逐项忽略，不拖垮整份凭据

运行：pytest src/test/unit/config/test_llm_credentials_blocks.py -v
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.python.config import _llm_providers as providers_mod
from src.python.config import _llm_settings as settings_mod
from src.python.config._llm_providers import DEFAULT_CREDENTIALS_REF, _load_llm_key_credentials

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "llm_key.json", tmp_path / "llm_providers.json"


@pytest.fixture(name="key_env")
def fixture_key_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """临时目录下的 llm_key.json / llm_providers.json 路径（内容由用例自行写）。"""
    key_path, providers_path = _paths(tmp_path)
    monkeypatch.setattr(providers_mod, "_get_llm_key_path", lambda: str(key_path))
    monkeypatch.setattr(providers_mod, "_get_llm_providers_path", lambda: str(providers_path))
    return key_path, providers_path


class TestNamedBlocksLoad:
    """命名凭据块是唯一受支持的形态。"""

    def test_named_blocks_loaded_verbatim(self, key_env: tuple[Path, Path]) -> None:
        key_path, _ = key_env
        key_path.write_text(
            json.dumps(
                {
                    "main": {"api_key": "sk-a", "model": "m1", "endpoint": "https://e/v1"},
                    "fallback": {"api_key": "sk-b"},
                }
            ),
            encoding="utf-8",
        )
        creds = _load_llm_key_credentials()
        assert creds is not None
        assert set(creds) == {"main", "fallback"}
        assert creds["main"]["model"] == "m1"
        assert creds["fallback"] == {"api_key": "sk-b"}

    def test_missing_file_returns_none(self, key_env: tuple[Path, Path]) -> None:
        assert _load_llm_key_credentials() is None

    def test_non_object_block_ignored_not_fatal(self, key_env: tuple[Path, Path], caplog) -> None:
        key_path, _ = key_env
        key_path.write_text(json.dumps({"main": {"api_key": "sk-a"}, "junk": "sk-b"}), encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="invest"):
            creds = _load_llm_key_credentials()
        assert creds is not None and "main" in creds
        assert any("不是 JSON 对象" in r.getMessage() for r in caplog.records)


class TestFlatDocumentRejected:
    """顶层 api_key 旧形态：拒绝加载，且不留任何迁移痕迹。"""

    def _write_flat(self, key_path: Path) -> None:
        key_path.write_text(
            json.dumps(
                {"provider": "openai", "api_key": "  sk-flat  ", "model": "gpt-x", "endpoint": "https://e/v1"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_loader_returns_none(self, key_env: tuple[Path, Path]) -> None:
        key_path, _ = key_env
        self._write_flat(key_path)
        assert _load_llm_key_credentials() is None

    def test_original_file_untouched_and_no_backup(self, key_env: tuple[Path, Path]) -> None:
        """不迁移：原文件逐字不变，也不产生 .bak 备份。"""
        key_path, _ = key_env
        self._write_flat(key_path)
        before = key_path.read_text(encoding="utf-8")
        _load_llm_key_credentials()
        assert key_path.read_text(encoding="utf-8") == before
        assert not Path(str(key_path) + ".bak").exists()

    def test_providers_file_not_modified(self, key_env: tuple[Path, Path]) -> None:
        """不追加 provider 条目：providers 文件不因凭据形态非法而被改写。"""
        key_path, providers_path = key_env
        self._write_flat(key_path)
        raw = {"providers": [{"name": "main", "provider": "claude", "credentials_ref": "main"}]}
        providers_path.write_text(json.dumps(raw), encoding="utf-8")
        before = providers_path.read_text(encoding="utf-8")
        _load_llm_key_credentials()
        assert providers_path.read_text(encoding="utf-8") == before

    def test_error_message_points_to_target_shape(self, key_env: tuple[Path, Path], caplog) -> None:
        """拒绝必须可执行：日志说明目标形态 + credentials_ref 字段名。"""
        key_path, _ = key_env
        self._write_flat(key_path)
        with caplog.at_level(logging.ERROR, logger="invest"):
            _load_llm_key_credentials()
        errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert any("顶层 api_key" in m for m in errors), errors
        assert any(DEFAULT_CREDENTIALS_REF in m for m in errors), errors
        assert any("credentials_ref" in m for m in errors), errors


class TestMergedConfigRejectsFlatDocument:
    """合并读取路径同样不迁移：扁平文档下 get_llm_config 无可用凭据。"""

    def test_get_llm_config_has_no_credentials(
        self, key_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        key_path, _ = key_env
        key_path.write_text(json.dumps({"api_key": "sk-flat", "model": "gpt-x"}), encoding="utf-8")
        settings_path = tmp_path / "llm_settings.json"
        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

        settings_path.write_text(_get_default_llm_settings_template(), encoding="utf-8")
        monkeypatch.setattr(settings_mod, "get_llm_settings_path", lambda: str(settings_path))
        settings_mod._llm_config_cache = None

        cfg = settings_mod.get_llm_config()
        assert cfg is not None, "配置文件本身可读，合并结果仍应产出"
        assert not (cfg.get("_llm_credentials") or {}), "扁平文档不得被当成凭据块加载"
        settings_mod._llm_config_cache = None
