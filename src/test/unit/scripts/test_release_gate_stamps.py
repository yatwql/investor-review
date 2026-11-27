"""发布门禁戳的三个纯函数：git 查询失败与戳条件不满足时的降级返回值。

`tree_fingerprint` / `code_file_hashes` 以注入的 `exec_fn` 取 git 结果——
git 不可用（非仓库、索引损坏）时必须返回中性值（空串 / None）而不是抛异常，
否则 gate 在异常工作区直接崩。「没有任何代码文件」与「查询失败」必须可区分。
"""

from __future__ import annotations

import json

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="gate_mod")
def fixture_gate_mod():
    load_script("release.py")  # 导入期把 scripts/ 接入 sys.path，_release 子包才可解析
    return load_script("_release/_gate.py", module_name="_release_gate_rare")


def _exec_with(rc: int, out: str = ""):
    return lambda cmd, root, runner=None: (rc, out, "")


class TestTreeFingerprint:
    def test_git_failure_yields_empty_string(self, gate_mod, tmp_path):
        assert gate_mod.tree_fingerprint(_exec_with(1), tmp_path) == ""

    def test_dirty_status_changes_fingerprint(self, gate_mod, tmp_path):
        clean = gate_mod.tree_fingerprint(_exec_with(0, "same"), tmp_path)
        dirty = gate_mod.tree_fingerprint(_exec_with(0, "same"), tmp_path)
        assert clean == dirty  # 同一输入同一指纹
        other = gate_mod.tree_fingerprint(_exec_with(0, "changed"), tmp_path)
        assert len(other) == len(clean)
        assert other != clean


class TestCodeFileHashes:
    def test_git_failure_returns_none(self, gate_mod, tmp_path):
        assert gate_mod.code_file_hashes(_exec_with(1), tmp_path) is None

    def test_no_files_returns_empty_dict(self, gate_mod, tmp_path):
        assert gate_mod.code_file_hashes(_exec_with(0, ""), tmp_path) == {}

    def test_tracked_files_are_hashed(self, gate_mod, tmp_path):
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
        hashes = gate_mod.code_file_hashes(_exec_with(0, "mod.py\0"), tmp_path)
        assert set(hashes) == {"mod.py"}
        assert len(hashes["mod.py"]) == 64


class TestBenchCoversVerify:
    def _stamp(self, tmp_path, **overrides):
        data = {"version": "v1", "covers_unit": True, "code_fingerprint": "fp", "modes": ["unit"]}
        data.update(overrides)
        path = tmp_path / "stamp.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_matching_stamp_is_returned(self, gate_mod, tmp_path):
        path = self._stamp(tmp_path)
        loaded = gate_mod.bench_covers_verify(path, "v1", "fp")
        assert loaded is not None
        assert loaded["version"] == "v1"

    def test_missing_fingerprint_returns_none(self, gate_mod, tmp_path):
        path = self._stamp(tmp_path)
        assert gate_mod.bench_covers_verify(path, "v1", "") is None

    def test_version_mismatch_returns_none(self, gate_mod, tmp_path):
        path = self._stamp(tmp_path)
        assert gate_mod.bench_covers_verify(path, "v2", "fp") is None

    def test_without_unit_coverage_returns_none(self, gate_mod, tmp_path):
        path = self._stamp(tmp_path, covers_unit=False)
        assert gate_mod.bench_covers_verify(path, "v1", "fp") is None

    def test_fingerprint_mismatch_returns_none(self, gate_mod, tmp_path):
        path = self._stamp(tmp_path)
        assert gate_mod.bench_covers_verify(path, "v1", "other") is None

    def test_unreadable_stamp_returns_none(self, gate_mod, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        assert gate_mod.bench_covers_verify(path, "v1", "fp") is None
