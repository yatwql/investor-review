"""`_shared/checklib.py` 文档区间解析与结论缓存的容错分支。

覆盖：`replace_region` 缺尾标记、指纹对不可读/已消失文件的占位、缓存非法结构一律
重算、写缓存失败静默（缓存只是加速，不是真值）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod(tmp_path: Path, monkeypatch):
    module = load_script("_shared/checklib.py", module_name="_shared_checklib_branches_under_test")
    monkeypatch.setenv(module._CONCLUSION_CACHE_ENV, str(tmp_path / "conclusions"))
    return module


class TestRegionParsing:
    """`replace_region` 只认成对标记：缺尾标记即拒绝改写（不猜区间）。"""

    def test_missing_end_marker_returns_none(self, mod):
        assert mod.replace_region("<!-- start -->body", "<!-- start -->", "<!-- end -->", "x") is None

    def test_missing_start_marker_returns_none(self, mod):
        assert mod.replace_region("body <!-- end -->", "<!-- start -->", "<!-- end -->", "x") is None

    def test_paired_markers_are_replaced(self, mod):
        text = "<!-- start -->old<!-- end -->"
        assert mod.replace_region(text, "<!-- start -->", "<!-- end -->", "new") == ("<!-- start -->new<!-- end -->")


class TestFingerprints:
    """指纹对不可读输入给稳定占位（宁可多失效，不漏失效）。"""

    def test_logic_fingerprint_marks_unreadable_file(self, mod, tmp_path: Path):
        missing = tmp_path / "gone.py"
        present = tmp_path / "here.py"
        present.write_text("# 逻辑\n", encoding="utf-8")
        # 不可读文件给稳定占位：同一输入指纹可复现，且与可读文件区分开
        assert mod._logic_fingerprint([missing]) == mod._logic_fingerprint([missing])
        assert mod._logic_fingerprint([missing]) != mod._logic_fingerprint([present])

    def test_input_fingerprint_marks_absent_file(self, mod, tmp_path: Path):
        missing = tmp_path / "gone.txt"
        assert mod._input_fingerprint([missing])[mod.rel(missing)] == "<absent>"

    def test_input_fingerprint_records_size_and_mtime(self, mod, tmp_path: Path):
        present = tmp_path / "here.txt"
        present.write_text("abc", encoding="utf-8")
        value = mod._input_fingerprint([present])[mod.rel(present)]
        assert value.startswith("3:")


class TestConclusionCache:
    """缓存命中要求逻辑指纹 + 输入指纹 + 结构三者同时成立。"""

    @staticmethod
    def _logic(tmp_path: Path) -> Path:
        logic = tmp_path / "logic.py"
        logic.write_text("# 逻辑\n", encoding="utf-8")
        return logic

    def test_roundtrip_hits(self, mod, tmp_path: Path):
        logic, data = self._logic(tmp_path), tmp_path / "input.txt"
        data.write_text("x", encoding="utf-8")
        mod.conclusion_cache_save("ns", [logic], [data], {"findings": ["a"]})
        assert mod.conclusion_cache_load("ns", [logic], [data]) == {"findings": ["a"]}

    def test_non_dict_payload_is_ignored(self, mod, tmp_path: Path):
        logic, data = self._logic(tmp_path), tmp_path / "input.txt"
        data.write_text("x", encoding="utf-8")
        mod.conclusion_cache_dir().mkdir(parents=True, exist_ok=True)
        (mod.conclusion_cache_dir() / "ns.json").write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        assert mod.conclusion_cache_load("ns", [logic], [data]) is None

    def test_corrupt_payload_is_ignored(self, mod, tmp_path: Path):
        logic, data = self._logic(tmp_path), tmp_path / "input.txt"
        data.write_text("x", encoding="utf-8")
        mod.conclusion_cache_dir().mkdir(parents=True, exist_ok=True)
        (mod.conclusion_cache_dir() / "ns.json").write_text("{ broken", encoding="utf-8")
        assert mod.conclusion_cache_load("ns", [logic], [data]) is None

    def test_changed_input_invalidates_cache(self, mod, tmp_path: Path):
        logic, data = self._logic(tmp_path), tmp_path / "input.txt"
        data.write_text("x", encoding="utf-8")
        mod.conclusion_cache_save("ns", [logic], [data], {"findings": []})
        data.write_text("changed", encoding="utf-8")
        assert mod.conclusion_cache_load("ns", [logic], [data]) is None

    def test_write_failure_is_silent(self, mod, tmp_path: Path, monkeypatch):
        blocker = tmp_path / "blocked"
        blocker.write_text("我是文件，不是目录", encoding="utf-8")
        monkeypatch.setenv(mod._CONCLUSION_CACHE_ENV, str(blocker / "nested"))

        def _unlink_raises(self, **kwargs):
            raise OSError(f"不可删除（{sorted(kwargs)}）")

        monkeypatch.setattr(Path, "unlink", _unlink_raises)
        # 不抛异常即契约：缓存写失败只是「下次重算」
        mod.conclusion_cache_save("ns", [], [], {"findings": []})
        assert not (blocker / "nested").exists()
