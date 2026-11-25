"""config/_core 读写路径的故障分支补齐测试。

覆盖点：
  - `_load_config` 的 mtime 读取失败降级与 `_strict` 重抛
  - `set_config` / `del_config` / `_persist_config_patch` 的读失败、坏 JSON、目录不可建
  - `init_config` 的路径覆写、目录不可建、并发创建（PermissionError）三分支
  - 「缺失即默认开」开关族在 `config=None` 时读全局配置的取值
  - `is_enable_candidate_compare` 的功能开关关闭与候选池为空两种关闭理由

所有读写都落在 conftest 重定向后的 tmp 配置路径上，不触碰真实 ``data/config/``。
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from src.python.config import _config_defaults
from src.python.config import _core

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


def _write_config(text: str) -> str:
    path = _config_defaults.get_config_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ── _load_config 降级 / 严格 ────────────────────────────────────


def test_load_config_survives_mtime_lookup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """mtime/size 读不到（文件被占用等）不应影响已解析的配置值。"""
    _write_config('{"news_top_count": 123}')
    _core.invalidate_config_cache()
    monkeypatch.setattr(_core.os.path, "getmtime", lambda path: (_ for _ in ()).throw(OSError("busy")))

    assert _core._load_config()["news_top_count"] == 123


def test_load_config_strict_reraises_on_broken_json() -> None:
    """`_strict=True` 且文件存在但内容非法 → 重抛，调用方（写侧）据此中止。"""
    _write_config("{not json")
    _core.invalidate_config_cache()
    with pytest.raises(json.JSONDecodeError):
        _core._load_config(_strict=True)


# ── 写入收尾 _persist_config_patch ─────────────────────────────


def test_persist_patch_rejects_invalid_json(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(json.JSONDecodeError):
        _core._persist_config_patch("{oops", "单键 patch")
    assert any("后结果非法，拒绝写入" in rec.message for rec in caplog.records)


def test_persist_patch_raises_when_config_dir_uncreatable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(path, *args, **kwargs):
        raise OSError("read-only fs")

    monkeypatch.setattr(_core.os, "makedirs", _boom)
    with pytest.raises(OSError, match="read-only fs"):
        _core._persist_config_patch('{"a": 1}', "删除键")


# ── set_config / del_config 读失败 ─────────────────────────────


def test_set_config_aborts_when_file_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    """读不到原文件时中止写入，避免基于空内容覆盖掉用户已有配置。"""
    _write_config('{"a": 1}')

    def _raise_open(*args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(builtins, "open", _raise_open)
    with pytest.raises(OSError, match="locked"):
        _core.set_config("a", 2)


def test_del_config_returns_when_file_absent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    missing = tmp_path / "data" / "config" / "absent.json"
    monkeypatch.setattr(_config_defaults, "get_config_path", lambda: str(missing))
    _core.del_config("a")  # 不抛异常即为通过（无文件 = 无键可删）
    assert not missing.exists()


def test_del_config_aborts_when_file_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config('{"a": 1}')

    def _raise_open(*args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(builtins, "open", _raise_open)
    with pytest.raises(OSError, match="locked"):
        _core.del_config("a")


def test_del_config_aborts_on_corrupt_file() -> None:
    """内容损坏时中止删除：不能把「解析不出来」当成「没有该键」。"""
    _write_config("{broken")
    with pytest.raises(json.JSONDecodeError):
        _core.del_config("a")


# ── init_config ────────────────────────────────────────────────


def test_init_config_honors_path_override(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    target = tmp_path / "custom" / "config.json"
    seen: list[str] = []
    monkeypatch.setattr(_config_defaults, "set_config_path_override", seen.append)
    monkeypatch.setattr(_config_defaults, "get_config_path", lambda: str(target))

    _core.init_config(str(target))

    assert seen == [str(target)]
    assert target.exists()


def test_init_config_raises_when_dir_uncreatable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    target = tmp_path / "nope" / "config.json"
    monkeypatch.setattr(_config_defaults, "get_config_path", lambda: str(target))

    def _boom(path, *args, **kwargs):
        raise OSError("read-only fs")

    monkeypatch.setattr(_core.os, "makedirs", _boom)
    with pytest.raises(OSError, match="read-only fs"):
        _core.init_config()


def test_init_config_tolerates_concurrent_creation(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Windows 并发：写默认模板时 PermissionError，但文件已被他方创建 → 视为成功。"""
    target = tmp_path / "config.json"
    monkeypatch.setattr(_config_defaults, "get_config_path", lambda: str(target))
    exists_calls = {"n": 0}

    def _exists(path):
        exists_calls["n"] += 1
        return exists_calls["n"] > 1

    monkeypatch.setattr(_core.os.path, "exists", _exists)

    def _deny(filepath, content):
        raise PermissionError("in use")

    monkeypatch.setattr(_core, "_atomic_write", _deny)
    monkeypatch.setattr(_core, "get_config", lambda: dict(_config_defaults._DEFAULT_CONFIG))
    validated: list[dict] = []
    monkeypatch.setattr(_core, "validate_config", validated.append)

    _core.init_config()

    assert len(validated) == 1


def test_init_config_reraises_permission_error_when_file_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    target = tmp_path / "config.json"
    monkeypatch.setattr(_config_defaults, "get_config_path", lambda: str(target))
    monkeypatch.setattr(_core.os.path, "exists", lambda path: False)

    def _deny(filepath, content):
        raise PermissionError("denied")

    monkeypatch.setattr(_core, "_atomic_write", _deny)
    with pytest.raises(PermissionError, match="denied"):
        _core.init_config()


# ── 开关族：config=None 时读全局配置 ──────────────────────────

_DEFAULT_ON_SWITCHES = (
    ("is_enable_fund_deep_analysis", "enable_fund_deep_analysis"),
    ("is_enable_portfolio_evolution", "enable_portfolio_evolution"),
    ("is_enable_action", "enable_action"),
    ("is_enable_news", "enable_news"),
    ("is_enable_history", "enable_history"),
)


@pytest.mark.parametrize(("func_name", "key"), _DEFAULT_ON_SWITCHES)
def test_switch_reads_global_config_when_none(monkeypatch: pytest.MonkeyPatch, func_name: str, key: str) -> None:
    """不传 config 时取全局配置的对应键；显式关闭 → False。"""
    monkeypatch.setattr(_core, "get_config", lambda: {key: False})
    assert getattr(_core, func_name)() is False


@pytest.mark.parametrize(("func_name", "key"), _DEFAULT_ON_SWITCHES)
def test_switch_defaults_to_enabled_when_key_missing(monkeypatch: pytest.MonkeyPatch, func_name: str, key: str) -> None:
    monkeypatch.setattr(_core, "get_config", lambda: {})
    assert getattr(_core, func_name)() is True


def test_datasink_switch_reads_global_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_core, "get_config", lambda: {"datasink": {"enabled": False}})
    assert _core.is_enable_datasink() is False
    monkeypatch.setattr(_core, "get_config", lambda: {"datasink": {"enabled": True}})
    assert _core.is_enable_datasink() is True


def test_candidate_compare_needs_feature_switch_and_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """功能开关关闭时直接 False（不读候选池）；开启但候选池为空仍视为关闭。"""
    import src.python.config.features as features

    monkeypatch.setattr(features, "is_feature_enabled", lambda name: False)
    assert _core.is_enable_candidate_compare({"comparison_candidates": ["011506"]}) is False

    monkeypatch.setattr(features, "is_feature_enabled", lambda name: True)
    monkeypatch.setattr(_core, "get_config", lambda: {"comparison_candidates": []})
    assert _core.is_enable_candidate_compare() is False
