"""`hook-install-claude.py` 的 settings.json 读写与安装/卸载编排。

覆盖：损坏 settings.json 的静默降级、安装幂等、卸载后清理空容器、CLI 分发开关。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod(tmp_path: Path, monkeypatch):
    """加载脚本并把 settings.json 重定向到临时目录（不触碰真实 .claude/）。"""
    module = load_script("hook-install-claude.py", module_name="hook_install_claude_under_test")
    monkeypatch.setattr(module, "_SETTINGS_PATH", tmp_path / ".claude" / "settings.json")
    return module


def _read_settings(mod) -> dict:
    return json.loads(mod._SETTINGS_PATH.read_text(encoding="utf-8"))


class TestLoadExisting:
    """`_load_existing` 的容错口径：缺失与损坏都视为「无既有配置」。"""

    def test_missing_file_yields_empty_dict(self, mod):
        assert mod._load_existing() == {}

    def test_keeps_existing_permissions(self, mod):
        mod._SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod._SETTINGS_PATH.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
        assert mod._load_existing()["permissions"]["allow"] == ["Bash(ls)"]

    def test_broken_json_degrades_to_empty_dict(self, mod):
        mod._SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod._SETTINGS_PATH.write_text("{ not json", encoding="utf-8")
        assert mod._load_existing() == {}


class TestInstallUninstall:
    """安装幂等 + 卸载回收空容器。"""

    def test_install_writes_hook_block(self, mod):
        assert mod.install() == 0
        blocks = _read_settings(mod)["hooks"]["PostToolUse"]
        assert any(h.get("matcher") == "Edit|Write" for h in blocks)

    def test_install_is_idempotent(self, mod):
        mod.install()
        before = _read_settings(mod)["hooks"]["PostToolUse"]
        assert mod.install() == 0
        assert _read_settings(mod)["hooks"]["PostToolUse"] == before

    def test_uninstall_without_hook_is_noop(self, mod):
        assert mod.uninstall() == 0
        assert not mod._SETTINGS_PATH.exists()

    def test_uninstall_keeps_other_post_hooks(self, mod):
        mod._SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        other = {"matcher": "Read", "hooks": [{"type": "command", "command": "true"}]}
        mod._SETTINGS_PATH.write_text(json.dumps({"hooks": {"PostToolUse": [other]}}), encoding="utf-8")
        mod.install()
        assert mod.uninstall() == 0
        assert _read_settings(mod)["hooks"]["PostToolUse"] == [other]

    def test_uninstall_drops_empty_hooks_container(self, mod):
        mod.install()
        assert mod.uninstall() == 0
        assert "hooks" not in _read_settings(mod)


class TestCliDispatch:
    """`main()` 按 `--uninstall` 分发到安装或卸载。"""

    @pytest.mark.parametrize(("argv_extra", "called"), [([], "install"), (["--uninstall"], "uninstall")])
    def test_main_dispatches(self, mod, monkeypatch, argv_extra, called):
        calls: list[str] = []
        monkeypatch.setattr(mod, "install", lambda: calls.append("install") or 0)
        monkeypatch.setattr(mod, "uninstall", lambda: calls.append("uninstall") or 0)
        monkeypatch.setattr(sys, "argv", ["hook-install-claude.py", *argv_extra])
        assert mod.main() == 0
        assert calls == [called]
