"""缓存目录权限自检（`cache/_paths.check_cache_dir_permissions`）。

缓存目录可能含持仓/穿透明细，权限过宽（组/其他可读）时应收紧到 0o700。自检本身是
尽力而为：目录建不出来、chmod 不支持（Windows/FAT）都只记警告，不得中断启动。
"""

from __future__ import annotations

import os
import stat
import types

import pytest

from src.python.cache import _paths

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _patch_os(monkeypatch, **overrides):
    """替换 `_paths` 模块看到的 os 函数（不污染全局 os）。"""
    namespace = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
    for name, value in overrides.items():
        setattr(namespace, name, value)
    monkeypatch.setattr(_paths, "os", namespace)
    return namespace


class TestCreateAndTighten:
    def test_missing_dir_is_created(self, tmp_path, monkeypatch):
        target = tmp_path / "cache" / "nested"
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(target))

        _paths.check_cache_dir_permissions()

        assert target.is_dir()

    @pytest.mark.skipif(os.name != "posix", reason="POSIX 才有完整 chmod 语义")
    def test_loose_mode_is_tightened_to_owner_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(tmp_path))
        os.chmod(tmp_path, 0o755)

        _paths.check_cache_dir_permissions()

        assert stat.S_IMODE(os.stat(tmp_path).st_mode) & 0o077 == 0, "组/其他权限须清零"

    @pytest.mark.skipif(os.name != "posix", reason="POSIX 才有完整 chmod 语义")
    def test_already_tight_mode_is_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(tmp_path))
        os.chmod(tmp_path, 0o700)

        _paths.check_cache_dir_permissions()

        assert stat.S_IMODE(os.stat(tmp_path).st_mode) == 0o700


class TestFaults:
    def test_chmod_failure_is_swallowed(self, tmp_path, monkeypatch, caplog):
        """chmod 不受支持（FAT/网络盘）→ 静默跳过，不影响其它检查。"""
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(tmp_path))

        def _raise(*args, **kwargs):
            raise OSError("operation not supported")

        _patch_os(monkeypatch, chmod=_raise)

        _paths.check_cache_dir_permissions()

        assert "缓存目录权限检查失败" not in caplog.text, "chmod 不受支持属预期，不得记成权限检查失败"

    def test_stat_failure_is_swallowed(self, tmp_path, monkeypatch):
        """`os.stat` 失败（并发删除/权限）→ 静默跳过权限收紧。"""
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(tmp_path))

        def _raise(*args, **kwargs):
            raise OSError("stat failed")

        chmod_calls: list[str] = []
        _patch_os(monkeypatch, stat=_raise, chmod=lambda *args, **kwargs: chmod_calls.append("chmod"))

        _paths.check_cache_dir_permissions()

        assert chmod_calls == [], "取不到当前权限时不做无依据的收紧"

    def test_makedirs_failure_logs_warning(self, tmp_path, monkeypatch, caplog):
        """目录建不出来（权限/只读盘）→ 警告一行，不抛异常、不影响启动。"""
        monkeypatch.setattr(_paths, "get_cache_dir", lambda: str(tmp_path / "blocked"))

        def _raise(*args, **kwargs):
            raise OSError("permission denied")

        _patch_os(monkeypatch, makedirs=_raise)

        _paths.check_cache_dir_permissions()

        assert "缓存目录权限检查失败" in caplog.text


class TestCacheDirOverride:
    def test_env_override_is_resolved_against_project_root(self, monkeypatch):
        """`INVEST_CACHE_DIR` 相对路径按项目根解析（演示/基准 run 的缓存隔离入口）。"""
        monkeypatch.setenv("INVEST_CACHE_DIR", "docs/tmp/demo-cache")

        resolved = _paths._resolve_cache_dir()

        assert resolved.endswith(os.path.join("docs", "tmp", "demo-cache"))

    def test_empty_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("INVEST_CACHE_DIR", "   ")

        assert _paths._resolve_cache_dir() == _paths._ROOT_CACHE_DIR
