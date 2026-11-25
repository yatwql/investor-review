"""缓存文件 IO 的降级支路：清理失败、replace 被锁、chmod 不支持与旧格式残留文件清理。

缓存 IO 的契约是「坏了就当没缓存、写不进去才报错」：清理/权限类失败一律吞掉，
只有真正的写入失败才上抛，因此逐条按「不抛异常且文件状态符合预期」断言。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from src.python.cache._io import _read_cache_data, _write_atomic

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _mkstemp(tmp_path) -> tuple[int, str]:
    return tempfile.mkstemp(dir=str(tmp_path))


def test_corrupt_cache_cleanup_failure_still_returns_none(tmp_path):
    """删除损坏文件失败（被占用/权限）→ 仍按无缓存返回 None，不把 OSError 抛给调用方。"""
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")

    with patch("src.python.cache._io.os.remove", side_effect=OSError("busy")):
        assert _read_cache_data(str(corrupt), "test_key") is None

    assert corrupt.exists(), "删除失败时文件保持原状，由下次读取重试"


def test_write_atomic_locked_target_falls_back_to_remove_and_rename(tmp_path):
    """``os.replace`` 被锁（Windows 常见）→ 先删目标再 rename，内容仍写入。"""
    final = tmp_path / "cache.json"
    final.write_text("old", encoding="utf-8")
    fd, tmp_path_str = _mkstemp(tmp_path)

    with patch("src.python.cache._io.os.replace", side_effect=PermissionError("locked")):
        _write_atomic(fd, tmp_path_str, str(final), str(tmp_path / "cache"), '{"a": 1}', b'{"a": 1}', False)

    assert final.read_text(encoding="utf-8") == '{"a": 1}'
    assert not os.path.exists(tmp_path_str), "临时文件须被移走，不留残留文件"


def test_write_atomic_ignores_chmod_failure(tmp_path):
    """``chmod`` 不支持（Windows）→ 忽略权限设置继续，写入结果不受影响。"""
    final = tmp_path / "cache.json"
    fd, tmp_path_str = _mkstemp(tmp_path)

    with patch("src.python.cache._io.os.chmod", side_effect=OSError("not supported")):
        _write_atomic(fd, tmp_path_str, str(final), str(tmp_path / "cache"), '{"b": 2}', b'{"b": 2}', False)

    assert final.read_text(encoding="utf-8") == '{"b": 2}'


def test_write_atomic_removes_stale_other_format_file(tmp_path):
    """写纯文本格式时清掉同键的旧 ``.gz``（两种格式不得并存）。"""
    final = tmp_path / "cache.json"
    stale_gz = tmp_path / "cache.gz"
    stale_gz.write_bytes(b"stale")
    fd, tmp_path_str = _mkstemp(tmp_path)

    _write_atomic(fd, tmp_path_str, str(final), str(tmp_path / "cache"), '{"c": 3}', b'{"c": 3}', False)

    assert final.read_text(encoding="utf-8") == '{"c": 3}'
    assert not stale_gz.exists()
