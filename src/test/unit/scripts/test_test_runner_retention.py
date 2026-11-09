"""测试：test-reports 归档保留期清理 —— 次数闸门 / 体积闸门 / 失败降级。

回归背景：`test-reports/archives/` 每跑一次测试就多一份归档，实测累积 31 份 ≈ 17G，
仓库无任何轮转机制。本文件锁死两个闸门的语义：

  - 次数闸门：只留最近 N 次运行（按 `<YYYYMMDD>/<HHMMSS>` 名字升序 = 时间升序）；
  - 体积闸门：保留集仍超上限时，从最旧开始继续删；
  - 两侧均可关（<=0）；
  - 删除失败只告警、不抛（归档清理是旁路，不得让测试跑不起来），且不计入已删数。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

from src.test._script_loader import load_script  # noqa: E402

retention = load_script("_test_runner/retention.py", module_name="test_runner_retention_probe")


def _make_run(archives: Path, date: str, clock: str, size_bytes: int = 10) -> Path:
    """造一份运行归档（日期/时刻两层目录 + 一个占位字节文件）。"""
    run = archives / date / clock
    run.mkdir(parents=True)
    (run / "report.html").write_bytes(b"x" * size_bytes)
    return run


class TestKeepRunsGate:
    """次数闸门：保留最近 N 次。"""

    def test_keeps_latest_n(self, tmp_path: Path):
        """5 次运行 + keep=2 → 只留最新两次，旧的连日期层一起回收。"""
        archives = tmp_path / "archives"
        for idx in range(1, 6):
            _make_run(archives, f"2026010{idx}", "100000")

        result = retention.prune_archives(str(archives), keep=2, cap_mb=0)

        remaining = sorted(p.parent.name + "/" + p.name for p in archives.glob("*/*"))
        assert remaining == ["20260104/100000", "20260105/100000"]
        assert result["removed"] == 3
        assert result["kept"] == 2

    def test_same_day_multiple_runs_ordered_by_clock(self, tmp_path: Path):
        """同日多次运行按时刻排序（不能只看日期层的名字）。"""
        archives = tmp_path / "archives"
        for clock in ("090000", "120000", "180000"):
            _make_run(archives, "20260101", clock)

        retention.prune_archives(str(archives), keep=1, cap_mb=0)

        assert [p.name for p in sorted(archives.glob("*/*"))] == ["180000"]

    def test_zero_keep_disables_gate(self, tmp_path: Path):
        """keep<=0 = 不启用次数闸门（体积闸门仍可独立生效）。"""
        archives = tmp_path / "archives"
        for idx in range(1, 4):
            _make_run(archives, f"2026010{idx}", "100000")

        result = retention.prune_archives(str(archives), keep=0, cap_mb=0)

        assert result["removed"] == 0
        assert result["kept"] == 3


class TestSizeGate:
    """体积闸门：保留集超上限时从最旧继续删。"""

    def test_prunes_oldest_until_under_cap(self, tmp_path: Path):
        """3 份各 1 MiB、上限 2 MiB → 删最旧一份即达标。"""
        archives = tmp_path / "archives"
        for idx in range(1, 4):
            _make_run(archives, f"2026010{idx}", "100000", size_bytes=1024 * 1024)

        result = retention.prune_archives(str(archives), keep=10, cap_mb=2)

        assert result["removed"] == 1
        assert result["kept"] == 2
        assert result["total_mb"] <= 2.0

    def test_zero_cap_disables_gate(self, tmp_path: Path):
        """cap<=0 = 不启用体积闸门。"""
        archives = tmp_path / "archives"
        _make_run(archives, "20260101", "100000", size_bytes=3 * 1024 * 1024)

        result = retention.prune_archives(str(archives), keep=10, cap_mb=0)

        assert result["removed"] == 0
        assert result["kept"] == 1


class TestDegradation:
    """旁路契约：不存在的目录 / 删除失败都不得抛。"""

    def test_missing_archives_dir_is_noop(self, tmp_path: Path):
        """归档目录不存在 → 各项为零，不抛。"""
        result = retention.prune_archives(str(tmp_path / "absent"), keep=1, cap_mb=1)
        assert result == {"removed": 0, "freed_mb": 0.0, "kept": 0, "total_mb": 0.0}

    def test_remove_failure_is_skipped_not_counted(self, tmp_path: Path, monkeypatch):
        """删除失败（权限/占用）→ 该份计入保留、不计数为已删，整体不抛。"""
        archives = tmp_path / "archives"
        for idx in range(1, 4):
            _make_run(archives, f"2026010{idx}", "100000")

        def _boom(_path: str) -> None:
            raise OSError("permission denied")

        monkeypatch.setattr(retention.shutil, "rmtree", _boom)

        result = retention.prune_archives(str(archives), keep=1, cap_mb=0)

        assert result["removed"] == 0
        assert len(list(archives.glob("*/*"))) == 3
        assert os.path.isdir(archives / "20260101" / "100000")

    def test_volume_gate_remove_failure_still_counted_as_kept(self, tmp_path: Path, monkeypatch):
        """体积闸门删不掉时：该份仍算保留（否则 kept/total_mb 比磁盘实际值小，统计虚报）。"""
        archives = tmp_path / "archives"
        mib = 1024 * 1024
        _make_run(archives, "20260101", "100000", size_bytes=2 * mib)
        _make_run(archives, "20260102", "100000", size_bytes=2 * mib)

        def _boom(_path: str) -> None:
            raise OSError("permission denied")

        monkeypatch.setattr(retention.shutil, "rmtree", _boom)

        result = retention.prune_archives(str(archives), keep=0, cap_mb=1)

        assert result["removed"] == 0
        assert result["kept"] == 2
        assert result["total_mb"] == pytest.approx(4.0)
        assert len(list(archives.glob("*/*"))) == 2
