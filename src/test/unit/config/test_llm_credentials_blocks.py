"""扁平密钥文档规范化回归 — 顶层四字段 → 命名凭据块 + provider 条目。

覆盖：
  - 规范化结果：llm_key.json 改写为 `default` 凭据块、原文件备份 `.bak`、
    llm_providers.json 追加引用同名凭据的条目（凭据分离：条目不含密钥）
  - 幂等：再次读取不重复追加条目、不再改写
  - 规范化不可用时凭据加载直接拒绝（不得静默走单 Provider 直连）
  - 已是命名凭据块的文档不被误改写

运行：pytest src/test/unit/config/test_llm_credentials_blocks.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.python.config import _llm_providers as providers_mod
from src.python.config import _llm_settings as settings_mod
from src.python.config._llm_providers import DEFAULT_CREDENTIALS_REF, _load_llm_key_credentials

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "llm_key.json", tmp_path / "llm_providers.json"


@pytest.fixture(name="flat_env")
def fixture_flat_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """临时目录下的扁平密钥文档（顶层 provider/api_key/model/endpoint）。"""
    key_path, providers_path = _paths(tmp_path)
    key_path.write_text(
        json.dumps(
            {"provider": "openai", "api_key": "  sk-legacy  ", "model": "gpt-x", "endpoint": "https://e/v1"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(providers_mod, "_get_llm_key_path", lambda: str(key_path))
    monkeypatch.setattr(providers_mod, "_get_llm_providers_path", lambda: str(providers_path))
    return key_path, providers_path


class TestFlatKeyDocumentConversion:
    """扁平密钥文档读取时一次性规范化。"""

    def test_key_file_rewritten_to_named_block(self, flat_env: tuple[Path, Path]) -> None:
        key_path, _ = flat_env
        assert providers_mod.ensure_credential_blocks(json.loads(key_path.read_text(encoding="utf-8"))) is True

        doc = json.loads(key_path.read_text(encoding="utf-8"))
        assert list(doc) == [DEFAULT_CREDENTIALS_REF]
        assert doc[DEFAULT_CREDENTIALS_REF]["api_key"] == "sk-legacy", "迁移后密钥应去除首尾空格"
        assert doc[DEFAULT_CREDENTIALS_REF]["model"] == "gpt-x"

    def test_original_file_backed_up(self, flat_env: tuple[Path, Path]) -> None:
        key_path, _ = flat_env
        providers_mod.ensure_credential_blocks(json.loads(key_path.read_text(encoding="utf-8")))
        backup = Path(str(key_path) + ".bak")
        assert backup.exists()
        assert json.loads(backup.read_text(encoding="utf-8"))["api_key"] == "  sk-legacy  "

    def test_provider_entry_appended_with_ref_only(self, flat_env: tuple[Path, Path]) -> None:
        key_path, providers_path = flat_env
        providers_mod.ensure_credential_blocks(json.loads(key_path.read_text(encoding="utf-8")))

        raw = json.loads(providers_path.read_text(encoding="utf-8"))
        entry = next(e for e in raw["providers"] if e.get("credentials_ref") == DEFAULT_CREDENTIALS_REF)
        assert entry["provider"] == "openai", "后端类型取自旧配置的 provider 字段"
        assert "api_key" not in entry, "providers 文件不得内联密钥（凭据分离）"

    def test_idempotent(self, flat_env: tuple[Path, Path]) -> None:
        key_path, providers_path = flat_env
        providers_mod.ensure_credential_blocks(json.loads(key_path.read_text(encoding="utf-8")))
        first_raw = providers_path.read_text(encoding="utf-8")
        # 再次规范化不应追加重复条目（文件内容应逐字不变）
        providers_mod.ensure_credential_blocks(json.loads(key_path.read_text(encoding="utf-8")))
        assert providers_path.read_text(encoding="utf-8") == first_raw

    def test_named_block_not_migrated(self, tmp_path: Path) -> None:
        doc = {"probe": {"api_key": "sk-1"}}
        assert providers_mod.is_flat_key_document(doc) is False


class TestConversionFailureIsExplicit:
    """规范化失败时不得回退单 Provider 直连：凭据加载直接拒绝。"""

    def test_flat_document_rejected_by_loader(self, flat_env: tuple[Path, Path]) -> None:
        assert _load_llm_key_credentials() is None
        # 文件保持原样（不因拒绝而破坏用户配置）
        key_path, _ = flat_env
        assert json.loads(key_path.read_text(encoding="utf-8"))["api_key"] == "  sk-legacy  "


class TestGetLlmConfigNormalizesOnRead:
    """读取路径自动规范化：规范化后配置具备 provider 链与凭据块。"""

    def test_get_llm_config_returns_chain_after_conversion(
        self, flat_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        key_path, providers_path = flat_env
        settings_path = tmp_path / "llm_settings.json"
        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

        settings_path.write_text(_get_default_llm_settings_template(), encoding="utf-8")
        monkeypatch.setattr(settings_mod, "get_llm_settings_path", lambda: str(settings_path))
        settings_mod._llm_config_cache = None

        cfg = settings_mod.get_llm_config()

        assert cfg is not None
        chain = cfg.get("_provider_list") or []
        assert any(e.get("credentials_ref") == DEFAULT_CREDENTIALS_REF for e in chain), "规范化后应走 provider 链"
        assert (cfg.get("_llm_credentials") or {}).get(DEFAULT_CREDENTIALS_REF, {}).get("api_key") == "sk-legacy"
        assert "api_key" not in cfg, "密钥不得出现在合并后的顶层配置里"
        settings_mod._llm_config_cache = None
