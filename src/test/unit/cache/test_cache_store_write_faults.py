"""缓存引擎写侧故障路径（`cache/_store`）：目录不可建 / 临时文件失败 / 目录被外删重试。

这些分支只在权限变更、磁盘满、目录被外部删除时出现，共同受一条硬契约约束——
**缓存是旁路**：任一环节失败都必须「告警 + 不写 + 不抛」，不得把异常抛给报告链。
"""

from __future__ import annotations

import os
import types

import pytest

from src.python.cache import _paths, _store

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _os_stub(**overrides):
    """构造只替换个别函数的 `os` 替身，避免 monkeypatch 改动全局 os 模块。"""
    namespace = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
    for name, value in overrides.items():
        setattr(namespace, name, value)
    return namespace


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    return tmp_path


class TestWriteFaults:
    def test_makedirs_failure_skips_write(self, cache_env, monkeypatch):
        """缓存目录建不出来（权限不足/磁盘满）→ 告警并跳过，不抛异常也不留下文件。"""

        def _raise(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(_store, "os", _os_stub(makedirs=_raise))
        _store.set("k_mkdir", {"v": 1})

        assert not list(cache_env.iterdir()), "目录不可建时不得写出任何文件"
        assert _store.get("k_mkdir", 60) is None

    def test_unremovable_corrupt_payload_still_misses(self, cache_env, monkeypatch):
        """顶层非对象载荷的删除失败（只读挂载）仍按未命中返回，不抛异常。"""
        shape_path = _paths._cache_path("k_shape")
        with open(shape_path, "w", encoding="utf-8") as f:
            f.write("[]")

        def _raise(*args, **kwargs):
            raise OSError("read-only file system")

        monkeypatch.setattr(_store, "os", _os_stub(remove=_raise))

        assert _store.get("k_shape", 60) is None
        assert os.path.exists(shape_path), "删除失败时文件应留存（不掩盖故障）"


class TestAtomicWriteRetry:
    """目录在 makedirs 之后被外部删除的「重试一次」分支。"""

    def test_retry_after_dir_vanished_writes_successfully(self, cache_env, monkeypatch):
        real_write = _store._write_atomic
        calls: list[int] = []

        def _flaky(fd, tmp_path, final_path, path, json_str, raw_bytes, use_gzip):
            calls.append(1)
            if len(calls) == 1:
                raise FileNotFoundError("directory vanished")
            return real_write(fd, tmp_path, final_path, path, json_str, raw_bytes, use_gzip)

        monkeypatch.setattr(_store, "_write_atomic", _flaky)
        _store.set("k_retry", {"v": 7})

        assert len(calls) == 2, "目录消失后应重试一次"
        assert _store.get("k_retry", 60) == {"v": 7}, "重试成功后必须可读回"

    def test_retry_write_failure_is_swallowed(self, cache_env, monkeypatch):
        calls: list[int] = []

        def _flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise FileNotFoundError("directory vanished")
            raise OSError("disk full")

        monkeypatch.setattr(_store, "_write_atomic", _flaky)
        _store.set("k_retry_fail", {"v": 1})

        assert len(calls) == 2, "重试一次即止，不得无限重试"
        assert _store.get("k_retry_fail", 60) is None

    def test_retry_tempfile_creation_failure_is_swallowed(self, cache_env, monkeypatch):
        import tempfile as tempfile_mod

        real_mkstemp = tempfile_mod.mkstemp
        calls: list[int] = []

        def _flaky_mkstemp(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return real_mkstemp(*args, **kwargs)
            raise OSError("no space left on device")

        def _raise_fnf(*args, **kwargs):
            raise FileNotFoundError("directory vanished")

        monkeypatch.setattr(_store.tempfile, "mkstemp", _flaky_mkstemp)
        monkeypatch.setattr(_store, "_write_atomic", _raise_fnf)
        _store.set("k_retry_mkstemp", {"v": 1})

        assert len(calls) == 2, "重试分支必须重新创建临时文件"
        assert _store.get("k_retry_mkstemp", 60) is None

    def test_non_retryable_write_error_removes_temp_file(self, cache_env, monkeypatch):
        seen: list[str] = []

        def _raise_os(*args, **kwargs):
            seen.append(args[1])
            raise OSError("input/output error")

        monkeypatch.setattr(_store, "_write_atomic", _raise_os)
        _store.set("k_io", {"v": 1})

        assert len(seen) == 1, "非 FileNotFoundError 不重试"
        assert not any(cache_env.glob("*.tmp")), "失败的临时文件必须清理"


class TestClearFaults:
    def test_remove_failure_does_not_raise(self, cache_env, monkeypatch):
        """清除缓存失败（只读挂载/并发删除）→ 只告警，不打断调用方。"""
        _store.set("k_clear", {"v": 1})
        cache_file = _paths._cache_path("k_clear")
        assert os.path.exists(cache_file)

        def _raise(*args, **kwargs):
            raise OSError("read-only file system")

        monkeypatch.setattr(_store, "os", _os_stub(remove=_raise))
        _store.clear("k_clear")

        assert os.path.exists(cache_file), "删除失败时文件应留存"

    def test_clear_removes_both_formats(self, cache_env):
        """`.json` 与同名 `.json.gz` 残留一并清除（读侧优先读，gz 残留会回灵）。"""
        _store.set("k_both", {"v": 1})
        gz_path = _paths._cache_path("k_both") + _paths._GZIP_SUFFIX
        with open(gz_path, "w", encoding="utf-8") as f:
            f.write("x")

        _store.clear("k_both")

        assert not os.path.exists(_paths._cache_path("k_both"))
        assert not os.path.exists(gz_path), "`.json.gz` 同键残留也必须清掉"
