"""快照持久化（`report/snapshot_store.py`）故障与空态分支契约测试。

锁住的契约：
  - 快照目录创建失败抛 OSError 且带目标路径（定位权限/路径问题不靠猜）
  - 原子写入失败还原为 OSError（不得静默吞成「已保存」）
  - 无快照文件时 load_latest 返回 None、prune 返回 0
  - 超保留期文件被删除并计入删除数；删除失败只告警不中断，计数不虚增
  - 数量兜底阶段的删除失败同样不中断
  - 目录列举异常降级为空列表；读取不存在的快照文件返回 None

运行：
  .venv/bin/python -m pytest src/test/unit/core/test_snapshot_store_branches.py -v
"""

from __future__ import annotations

import os
import time

import pytest

from src.python.core import snapshot_store as hs

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _touch_snapshot(directory: str, name: str, mtime_age_days: float = 0.0) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{}")
    if mtime_age_days:
        old = time.time() - mtime_age_days * 86400
        os.utime(path, (old, old))
    return path


def _empty_workspace(monkeypatch, tmp_path) -> str:
    """把快照目录指向独立空目录（避免命中本机既有快照）。"""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    monkeypatch.setattr(hs, "HISTORY_SNAPSHOT_DIR", str(snap_dir))
    return str(snap_dir)


class TestSaveFailures:
    """写盘失败的显式抛出。"""

    def test_directory_create_failure_raises_with_path(self, monkeypatch, tmp_path):
        snap_dir = _empty_workspace(monkeypatch, tmp_path)

        def _boom(_path, exist_ok=False):
            raise OSError("permission denied")

        monkeypatch.setattr(hs.os, "makedirs", _boom)

        with pytest.raises(OSError) as exc:
            hs.save(_snapshot(), namespace="web")

        assert os.path.join(snap_dir, "web") in str(exc.value), "报错须带目标路径以便定位"

    def test_atomic_write_failure_raises(self, monkeypatch):
        monkeypatch.setattr(hs, "write_text_atomic", lambda *a, **k: False)

        with pytest.raises(OSError):
            hs.save(_snapshot())


class TestEmptyStore:
    """空快照目录的返回值口径。"""

    def test_load_latest_without_snapshot_returns_none(self, monkeypatch, tmp_path):
        _empty_workspace(monkeypatch, tmp_path)

        assert hs.load_latest() is None

    def test_prune_without_snapshot_returns_zero(self, monkeypatch, tmp_path):
        _empty_workspace(monkeypatch, tmp_path)

        assert hs.prune() == 0


class TestPruneDeletion:
    """保留期与数量兜底两阶段的删除口径。"""

    def test_expired_snapshot_is_deleted_and_counted(self, monkeypatch, tmp_path):
        snap_dir = _empty_workspace(monkeypatch, tmp_path)
        stale = _touch_snapshot(snap_dir, "snapshot_20250101T090000.json", mtime_age_days=400)

        assert hs.prune(retention_days=180) == 1
        assert not os.path.exists(stale)

    def test_retention_delete_failure_is_swallowed(self, monkeypatch, tmp_path):
        snap_dir = _empty_workspace(monkeypatch, tmp_path)
        _touch_snapshot(snap_dir, "snapshot_20250101T090000.json", mtime_age_days=400)

        def _boom(_path):
            raise OSError("busy")

        monkeypatch.setattr(hs.os, "unlink", _boom)

        assert hs.prune(retention_days=180) == 0, "删除失败不得计入删除数"

    def test_count_cap_delete_failure_is_swallowed(self, monkeypatch, tmp_path):
        snap_dir = _empty_workspace(monkeypatch, tmp_path)
        _touch_snapshot(snap_dir, "snapshot_20260101T090000.json")
        _touch_snapshot(snap_dir, "snapshot_20260102T090000.json")

        def _boom(_path):
            raise OSError("busy")

        monkeypatch.setattr(hs.os, "unlink", _boom)

        assert hs.prune(retention_days=180, max_count=1) == 0


class TestListAndLoadFailures:
    """目录列举与文件读取的降级（经公开入口验证）。"""

    def test_listdir_failure_degrades_to_empty(self, monkeypatch, tmp_path):
        _empty_workspace(monkeypatch, tmp_path)

        def _boom(_path):
            raise OSError("unreadable")

        monkeypatch.setattr(hs.os, "listdir", _boom)

        assert hs.load_latest() is None, "列举异常须按「无快照」处理"
        assert hs.load_all() == []
        assert hs.prune(retention_days=180, max_count=1) == 0

    def test_file_vanishes_between_listdir_and_read_is_skipped(self, monkeypatch, tmp_path):
        _empty_workspace(monkeypatch, tmp_path)
        # 列举到的文件在读取前消失（并发 prune 的真实竞态）
        monkeypatch.setattr(hs.os, "listdir", lambda _p: ["snapshot_20260101T090000.json"])

        assert hs.load_all() == [], "文件在列举与读取之间消失须静默跳过，不得抛出"


def _snapshot():
    """最小合法快照（save 只校验时间戳与可序列化）。"""
    from src.python.schemas.history import SnapshotData

    return SnapshotData(accounts=(), total_value=0.0, total_cost=0.0, total_pnl=0.0, timestamp="20260302T090000")
