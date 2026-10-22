"""开发期本地卫生：陈旧字节码清理（`scripts/_release/_hygiene.py`）。

背景：模块改名/删除后 `__pycache__/旧名.cpython-*.pyc` 不会被回收；功能无害，
但 rg 与 traceback 会露出旧文件名/旧路径。清理只删「同目录已无同名源文件」的 .pyc。
"""

from __future__ import annotations

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("_release/_hygiene.py", module_name="_release_hygiene_under_test")


def _make_tree(tmp_path):
    pkg = tmp_path / "pkg"
    cache = pkg / "__pycache__"
    cache.mkdir(parents=True)
    (pkg / "current.py").write_text("x = 1\n", encoding="utf-8")
    (cache / "current.cpython-313.pyc").write_bytes(b"pyc")
    (cache / "old.cpython-313.pyc").write_bytes(b"pyc")
    (cache / "old.cpython-311-pytest-9.1.1.pyc").write_bytes(b"pyc")
    orphan = tmp_path / "gone" / "__pycache__"
    orphan.mkdir(parents=True)
    (orphan / "gone.cpython-313.pyc").write_bytes(b"pyc")
    return tmp_path


class TestStaleBytecode:
    def test_lists_only_orphaned_pyc(self, mod, tmp_path):
        root = _make_tree(tmp_path)
        names = sorted(p.name for p in mod.stale_bytecode(root))
        assert names == ["gone.cpython-313.pyc", "old.cpython-311-pytest-9.1.1.pyc", "old.cpython-313.pyc"]

    def test_dry_run_reports_without_deleting(self, mod, tmp_path):
        root = _make_tree(tmp_path)
        stats = mod.clean_stale_bytecode(root, dry_run=True)
        assert stats["files"] == 3
        assert (root / "pkg" / "__pycache__" / "old.cpython-313.pyc").exists()

    def test_clean_removes_stale_and_empty_dirs(self, mod, tmp_path):
        root = _make_tree(tmp_path)
        stats = mod.clean_stale_bytecode(root)
        assert stats == {"files": 3, "dirs": 1}
        cache = root / "pkg" / "__pycache__"
        assert cache.is_dir()  # 仍有有效 pyc，目录保留
        assert not (cache / "old.cpython-313.pyc").exists()
        assert (cache / "current.cpython-313.pyc").exists()
        assert not (root / "gone").exists()  # 清空后目录删除

    def test_idempotent(self, mod, tmp_path):
        root = _make_tree(tmp_path)
        mod.clean_stale_bytecode(root)
        assert mod.clean_stale_bytecode(root) == {"files": 0, "dirs": 0}
