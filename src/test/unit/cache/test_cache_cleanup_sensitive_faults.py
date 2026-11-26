"""缓存清理故障与敏感缓存清理路径（`cache/_cleanup`）。

覆盖两类「清理是尽力而为」的契约面：
  - 扫描期异常（目录不可读、文件已消失、`_ts` 非法）必须降级为跳过，
    不得中断整轮清理，更不得把非缓存引擎托管的文件当过期删掉；
  - 敏感缓存（持仓/穿透/基金持仓/基金经理）按保留期清理：损坏文件计入删除、
    删除失败跳过、`.json` 与 `.json.gz` 两种格式同口径。
"""

from __future__ import annotations

import gzip
import json
import os
import time

import pytest

from src.python.cache import _cleanup

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

#: 保留期之外的写入时刻（任何 TTL 都判过期）
_STALE_TS = 400 * 86400


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    return tmp_path


def _write_plain(path, ts, data=None):
    path.write_text(json.dumps({"_ts": ts, "_data": data if data is not None else {"v": 1}}), encoding="utf-8")


def _write_gzip(path, ts, data=None):
    payload = json.dumps({"_ts": ts, "_data": data if data is not None else {"v": 1}})
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(payload)


class TestScanFaults:
    def test_unreadable_dir_returns_no_files(self, cache_dir, monkeypatch):
        """缓存目录列举失败（权限）→ 空列表 + 清理计 0，不抛异常。"""

        def _raise(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(_cleanup.os, "listdir", _raise)

        assert _cleanup._cache_file_names() == []
        assert _cleanup.cleanup_expired() == 0

    def test_non_cache_extension_is_skipped(self, cache_dir):
        """非 `.json`/`.json.gz` 文件不参与 TTL 判定（同目录可能放着脚本自管产物）。"""
        (cache_dir / "notes.txt").write_text("x", encoding="utf-8")

        assert _cleanup._process_cache_file("notes.txt", False, {}, {}) == 0

    def test_non_numeric_ts_is_treated_as_unmanaged(self, cache_dir):
        """`_ts` 非数值 → 不按 epoch 当陈旧文件删掉，只留 DEBUG 并跳过。"""
        (cache_dir / "performance_probe.json").write_text(
            json.dumps({"_ts": "not-a-timestamp", "_data": {"v": 1}}), encoding="utf-8"
        )

        assert _cleanup.cleanup_expired() == 0
        assert (cache_dir / "performance_probe.json").exists()

    def test_size_lookup_failure_does_not_block_cleanup(self, cache_dir, monkeypatch):
        """`getsize` 失败（并发删除）只让空间统计记 0，不影响过期删除本身。"""
        _write_plain(cache_dir / "price_600900_v1.json", time.time() - _STALE_TS)

        def _raise(*args, **kwargs):
            raise OSError("vanished")

        monkeypatch.setattr(_cleanup.os.path, "getsize", _raise)

        assert _cleanup.cleanup_expired() == 1
        assert not (cache_dir / "price_600900_v1.json").exists()

    def test_missing_dir_returns_zero(self, tmp_path, monkeypatch):
        """缓存目录不存在（首次运行尚未写缓存）→ 计 0，不打红色告警。"""
        monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path / "absent"))

        assert _cleanup.cleanup_expired() == 0

    def test_gzip_cache_file_is_cleaned(self, cache_dir):
        """`.json.gz` 与 `.json` 两种现行格式同口径参与 TTL 清理。"""
        _write_gzip(cache_dir / "price_600900_v1.json.gz", time.time() - _STALE_TS)

        assert _cleanup.cleanup_expired() == 1
        assert not (cache_dir / "price_600900_v1.json.gz").exists()

    def test_unrecognized_key_name_is_skipped(self, cache_dir, monkeypatch):
        """扩展名是缓存格式但逻辑键还原失败（防御分支）→ 跳过，不做 TTL 猜测。"""
        monkeypatch.setattr(_cleanup, "cache_key_from_file_name", lambda fname: None)

        assert _cleanup._process_cache_file("price_600900_v1.json", False, {}, {}) == 0

    def test_corrupt_file_counts_as_cleaned(self, cache_dir):
        """损坏缓存计入清理数（否则坏文件会永远留在盘上占位）。"""
        (cache_dir / "price_600900_v1.json").write_text("{broken", encoding="utf-8")

        assert _cleanup.cleanup_expired() == 1
        assert not (cache_dir / "price_600900_v1.json").exists()

    def test_remove_failure_is_not_counted(self, cache_dir, monkeypatch):
        """删除失败（只读挂载）不计入清理数，扫描照常继续。"""
        _write_plain(cache_dir / "price_600900_v1.json", time.time() - _STALE_TS)

        def _raise(*args, **kwargs):
            raise OSError("read-only file system")

        monkeypatch.setattr(_cleanup.os, "remove", _raise)

        assert _cleanup.cleanup_expired() == 0
        assert (cache_dir / "price_600900_v1.json").exists()


class TestAutoCleanup:
    """无人值守入口 `auto_cleanup_expired`：成功透传 / 失败静默归 0。"""

    def test_returns_cleanup_count(self, cache_dir):
        _write_plain(cache_dir / "price_600900_v1.json", time.time() - _STALE_TS)

        assert _cleanup.auto_cleanup_expired() == 1

    def test_failure_is_swallowed(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise RuntimeError("probe fault")

        monkeypatch.setattr(_cleanup, "cleanup_expired", _raise)

        assert _cleanup.auto_cleanup_expired() == 0


class TestSensitiveCleanup:
    def test_missing_dir_returns_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path / "absent"))

        assert _cleanup.clean_sensitive() == 0

    def test_removes_expired_sensitive_files_both_formats(self, cache_dir):
        """`.json` 与 `.json.gz` 两种敏感缓存都按保留期删除；非缓存扩展名不动。"""
        _write_plain(cache_dir / "holding_600900_v1.json", time.time() - _STALE_TS)
        _write_gzip(cache_dir / "penetration_top_v1.json.gz", time.time() - _STALE_TS)
        (cache_dir / "holding_notes.txt").write_text("x", encoding="utf-8")

        assert _cleanup.clean_sensitive(older_than_days=90) == 2
        assert not (cache_dir / "holding_600900_v1.json").exists()
        assert not (cache_dir / "penetration_top_v1.json.gz").exists()
        assert (cache_dir / "holding_notes.txt").exists()

    def test_fresh_sensitive_file_is_kept(self, cache_dir):
        _write_plain(cache_dir / "fund_hold_000001_v1.json", time.time())

        assert _cleanup.clean_sensitive(older_than_days=90) == 0
        assert (cache_dir / "fund_hold_000001_v1.json").exists()

    def test_dry_run_reports_without_deleting(self, cache_dir):
        _write_plain(cache_dir / "fund_manager_000001_v1.json", time.time() - _STALE_TS)

        assert _cleanup.clean_sensitive(older_than_days=90, dry_run=True) == 1
        assert (cache_dir / "fund_manager_000001_v1.json").exists()

    def test_malformed_ts_does_not_abort_sweep(self, cache_dir):
        """畸形 `_ts`（字符串）不得抛 TypeError 打断整轮清理。

        缺陷回归：之前 `ts = payload.get("_ts", 0)` 直接参与减法，遇到字符串立即
        TypeError，被导入期 try/except 吞掉后整轮敏感缓存清理中止——后面的文件再也
        不被处理。现在按「无法判定年龄」当 0（极旧）清理，且继续扫完。
        """
        _write_plain(cache_dir / "holding_bad_ts_v1.json", "not-a-timestamp")
        _write_plain(cache_dir / "holding_600900_v1.json", time.time() - _STALE_TS)

        assert _cleanup.clean_sensitive(older_than_days=90) == 2, "两个文件都应被处理到"
        assert not (cache_dir / "holding_bad_ts_v1.json").exists()
        assert not (cache_dir / "holding_600900_v1.json").exists()

    def test_corrupt_sensitive_file_counts_as_removed(self, cache_dir):
        """损坏文件由读取层删除并计入清理数（否则坏文件会永远留在盘上）。"""
        (cache_dir / "holding_broken_v1.json").write_text("{not json", encoding="utf-8")

        assert _cleanup.clean_sensitive(older_than_days=90) == 1
        assert not (cache_dir / "holding_broken_v1.json").exists()

    def test_remove_failure_is_skipped(self, cache_dir, monkeypatch):
        """删除失败（只读挂载）跳过该文件且不计入删除数，继续处理其余文件。"""
        _write_plain(cache_dir / "holding_600900_v1.json", time.time() - _STALE_TS)

        def _raise(*args, **kwargs):
            raise OSError("read-only file system")

        monkeypatch.setattr(_cleanup.os, "remove", _raise)

        assert _cleanup.clean_sensitive(older_than_days=90) == 0
        assert (cache_dir / "holding_600900_v1.json").exists()
        assert os.path.exists(cache_dir / "holding_600900_v1.json")
