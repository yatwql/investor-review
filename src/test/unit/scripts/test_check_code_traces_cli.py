"""check-code-traces.py 的分级退出码与输出面（`_scan_all` / `main`）。

覆盖非 CI 的逐条命中打印（含 `-v` 文本行）、HIGH 与 LOW 两个桶的汇总与
退出码（1 = 高置信度、3 = 仅 LOW）、并行扫描分支的**顺序保序**契约，
以及 `main()` 非 CI 路径的直通。
"""

from __future__ import annotations

import argparse
import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SUPPORTED_SUFFIX = ".py"


@pytest.fixture(name="traces")
def fixture_traces():
    return load_script("check-code-traces.py", module_name="_check_code_traces_cli")


def _args(ci: bool = False, verbose: bool = False) -> argparse.Namespace:
    return argparse.Namespace(ci=ci, verbose=verbose)


def _hit(category: str, lineno: int = 1) -> tuple[int, str, str, str]:
    return (lineno, category, "描述", "原始注释文本")


class TestScanAllBuckets:
    def _patch_hits(self, traces, monkeypatch, tmp_path, hits_by_file: dict[str, list[tuple]]):
        files = []
        for name in hits_by_file:
            fpath = tmp_path / name
            fpath.write_text("", encoding="utf-8")
            files.append(fpath)
        monkeypatch.setattr(traces, "_collect_scan_files", lambda: files)
        monkeypatch.setattr(traces, "_scan_files", lambda fs, verbose, jobs=1: [hits_by_file[p.name] for p in fs])

    def test_clean_scan_exits_zero(self, traces, monkeypatch, tmp_path, capsys):
        self._patch_hits(traces, monkeypatch, tmp_path, {"a.py": []})
        assert traces._scan_all(_args(), jobs=1) == 0
        assert "未发现历史变更痕迹" in capsys.readouterr().out

    def test_high_category_exits_one(self, traces, monkeypatch, tmp_path, capsys):
        high = traces.HIGH_CATEGORIES[0]
        self._patch_hits(traces, monkeypatch, tmp_path, {"a.py": [_hit(high)]})
        assert traces._scan_all(_args(), jobs=1) == 1
        out = capsys.readouterr().out
        assert "高置信度" in out
        assert "[ERR]" in out

    def test_code_category_exits_two(self, traces, monkeypatch, tmp_path, capsys):
        code = traces.CODE_CATEGORIES[0]
        self._patch_hits(traces, monkeypatch, tmp_path, {"a.py": [_hit(code)]})
        assert traces._scan_all(_args(), jobs=1) == 2
        assert "应改写为语义描述" in capsys.readouterr().out

    def test_low_category_exits_three(self, traces, monkeypatch, tmp_path, capsys):
        low = traces.LOW_CATEGORIES[0]
        self._patch_hits(traces, monkeypatch, tmp_path, {"a.py": [_hit(low)]})
        assert traces._scan_all(_args(), jobs=1) == 3
        out = capsys.readouterr().out
        assert "LOW 级别痕迹" in out
        assert "[!]" in out

    def test_high_bucket_wins_over_code_and_low(self, traces, monkeypatch, tmp_path):
        hits = [
            _hit(traces.HIGH_CATEGORIES[0]),
            _hit(traces.CODE_CATEGORIES[0]),
            _hit(traces.LOW_CATEGORIES[0]),
        ]
        self._patch_hits(traces, monkeypatch, tmp_path, {"a.py": hits})
        assert traces._scan_all(_args(), jobs=1) == 1


class TestOutputShape:
    def _one_low_hit(self, traces, monkeypatch, tmp_path):
        files = [tmp_path / "a.py"]
        files[0].write_text("", encoding="utf-8")
        monkeypatch.setattr(traces, "_collect_scan_files", lambda: files)
        monkeypatch.setattr(
            traces, "_scan_files", lambda fs, verbose, jobs=1: [[_hit(traces.LOW_CATEGORIES[0], lineno=42)]]
        )

    def test_non_ci_prints_file_header_and_hit_line(self, traces, monkeypatch, tmp_path, capsys):
        self._one_low_hit(traces, monkeypatch, tmp_path)
        traces._scan_all(_args(), jobs=1)
        out = capsys.readouterr().out
        assert "a.py" in out
        assert "[!]" in out
        assert "描述" in out

    def test_non_ci_verbose_prints_raw_text(self, traces, monkeypatch, tmp_path, capsys):
        self._one_low_hit(traces, monkeypatch, tmp_path)
        traces._scan_all(_args(verbose=True), jobs=1)
        assert "原始注释文本" in capsys.readouterr().out

    def test_ci_prints_single_line_per_hit(self, traces, monkeypatch, tmp_path, capsys):
        self._one_low_hit(traces, monkeypatch, tmp_path)
        traces._scan_all(_args(ci=True), jobs=1)
        lines = [line for line in capsys.readouterr().out.splitlines() if "描述" in line]
        assert len(lines) == 1
        assert lines[0].endswith("a.py:42 [TODO] 描述 — 原始注释文本")
        assert " — 原始注释文本" in lines[0]


class TestParallelScan:
    def test_parallel_matches_serial_order(self, traces, monkeypatch, tmp_path):
        """并行分支结果按输入顺序回排（与串行逐字相同）。"""
        files = []
        for index in range(65):
            fpath = tmp_path / f"f{index}{_SUPPORTED_SUFFIX}"
            fpath.write_text("", encoding="utf-8")
            files.append(fpath)

        class _InlinePool:
            def __init__(self, max_workers=None):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def map(self, func, iterable, flags, chunksize=1):
                items = list(iterable)
                results: list = []
                for start in range(0, len(items), chunksize):
                    results.extend(func(item, flags[0]) for item in items[start : start + chunksize])
                return results

        import concurrent.futures

        monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", _InlinePool)
        monkeypatch.setattr(traces, "scan_file", lambda fpath, verbose=False: [[fpath.name]])
        result = traces._scan_files(files, False, jobs=2)
        assert [item[0][0] for item in result] == [path.name for path in files]

    def test_single_job_stays_serial(self, traces, monkeypatch, tmp_path):
        calls: list[str] = []
        monkeypatch.setattr(traces, "scan_file", lambda fpath, verbose=False: calls.append(fpath.name) or [])
        files = [tmp_path / "a.py"]
        assert traces._scan_files(files, False, jobs=1) == [[]]
        assert calls == ["a.py"]


class TestCollectScanFiles:
    def test_non_source_and_directory_entries_are_skipped(self, traces, monkeypatch, tmp_path):
        scan_root = tmp_path / "src"
        (scan_root / "sub").mkdir(parents=True)
        (scan_root / "keep.py").write_text("x = 1\n", encoding="utf-8")
        (scan_root / "notes.md").write_text("文档\n", encoding="utf-8")
        monkeypatch.setattr(traces, "SCAN_DIRS", [scan_root, tmp_path / "absent"])
        names = [path.name for path in traces._collect_scan_files()]
        assert names == ["keep.py"]


class TestMainNonCiPath:
    def test_main_without_ci_scans_and_exits(self, traces, monkeypatch):
        monkeypatch.setattr(traces, "_collect_scan_files", lambda: [])
        monkeypatch.setattr(sys, "argv", ["check-code-traces.py"])
        with pytest.raises(SystemExit) as excinfo:
            traces.main()
        assert excinfo.value.code == 0
