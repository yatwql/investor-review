"""`_doc_drift` 共享设施与目录树检查的**罕见分支**补盲用例。

前序用例覆盖主线口径，本文件补：解析原语的边界返回、快照状态的损坏/失配降级、
收集子进程超时与逻辑指纹兜底、目录树幽灵条目与统计回写的格式保护、章节-区块
矩阵的解析错误与三向对账各条 finding 分支。

pytest 子进程一律 mock（此处验判定与降级方向，不验收集器本身）。
"""
# ruff: noqa: F811 — 夹具以参数名注入（与模块级同名导入非重定义）

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from src.python.core.section_block_registry import SECTION_BLOCK_SPECS
from src.test.unit.scripts.test_check_doc_drift import (
    drift,  # noqa: F401
    drift_parts,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


# ═══ 共享解析原语 ═══


class TestParsePrimitivesEdge:
    """`_doc_section` / `_values_equal` 的边界返回。"""

    def test_doc_section_without_end_runs_to_eof(self, drift):
        text = "前言\nBEGIN a\nb\n"
        assert drift._doc_section(text, "BEGIN", None) == "BEGIN a\nb\n"

    def test_doc_section_missing_start_is_empty(self, drift):
        assert drift._doc_section("无关内容\n", "BEGIN", "END") == ""

    def test_values_equal_unparsable_number_is_false(self, drift):
        """文档写非数字（如 `—`）与数字默认值比较 → 不等，不得抛异常。"""
        assert drift._values_equal("—", 10) is False
        assert drift._values_equal("1,024", 1024) is True

    def test_values_equal_string_forms(self, drift):
        assert drift._values_equal('"gpt-4o"', "gpt-4o") is True
        assert drift._values_equal("logs/app.log", "/abs/path/logs/app.log") is True
        assert drift._values_equal("其它名", "gpt-4o") is False


class TestCollectTestCount:
    """`_collect_test_count()` 从快照取 `_总收集`。"""

    def test_reads_total_from_snapshot(self, drift_parts, monkeypatch):
        mod = drift_parts._shared
        monkeypatch.setattr(mod, "_collect_test_snapshot", lambda: {"_总收集": 4321, "unit": 10})
        assert mod._collect_test_count() == 4321


# ═══ 快照状态降级 ═══


class TestSnapshotStateDegradation:
    """`_read_snapshot_state` / `_write_snapshot_state` 的损坏与写失败降级。"""

    def test_broken_json_reads_as_empty(self, drift_parts):
        mod = drift_parts._shared
        path = mod._snapshot_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ 不是合法 JSON", encoding="utf-8")

        assert mod._read_snapshot_state() == {}

    def _seed(self, mod, **overrides) -> None:
        path = mod._snapshot_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "format": mod._SNAPSHOT_FORMAT,
            "logic": mod._logic_key(),
            "shared": mod._shared_signature(),
            "files": {},
            "full": None,
            "shadow_ok": 0,
        }
        state.update(overrides)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def test_logic_mismatch_reads_as_empty(self, drift_parts):
        """收集逻辑变更（脚本/模块/解释器任一变）→ 旧状态整体失效。"""
        mod = drift_parts._shared
        self._seed(mod, logic="上一版逻辑指纹", files={"a.py": {"sig": "x", "total": 1}})

        assert mod._read_snapshot_state() == {}

    def test_non_dict_files_reads_as_empty(self, drift_parts):
        mod = drift_parts._shared
        self._seed(mod, files=["不是字典"])

        assert mod._read_snapshot_state() == {}

    def test_write_failure_cleans_tmp_and_stays_silent(self, drift_parts, monkeypatch, tmp_path):
        """写盘失败（只读/权限）→ 清掉半成品并静默返回（缓存只是加速，不是真值）。"""
        mod = drift_parts._shared
        cache = mod._snapshot_cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)

        def _replace_boom(*_a, **_k):
            raise OSError("只读文件系统")

        def _unlink_boom(*_a, **_k):
            raise OSError("也删不掉")

        monkeypatch.setattr(mod.os, "replace", _replace_boom)
        monkeypatch.setattr(Path, "unlink", _unlink_boom)

        mod._write_snapshot_state({"format": mod._SNAPSHOT_FORMAT})

        assert not cache.exists(), "写失败时不得留下半成品目标文件（且异常不外泄）"

    def test_write_creates_parent_directory(self, drift_parts, tmp_path, monkeypatch):
        mod = drift_parts._shared
        target = tmp_path / "deep" / "dir" / "snapshot.json"
        monkeypatch.setenv(mod._SNAPSHOT_CACHE_ENV, str(target))

        mod._write_snapshot_state({"format": mod._SNAPSHOT_FORMAT, "files": {}})

        saved = json.loads(target.read_text(encoding="utf-8"))
        assert saved["format"] == mod._SNAPSHOT_FORMAT
        assert "_ts" in saved, "写入必须带时间包封（缺它会被当 epoch 立即清理）"


class TestTestFileDiscoveryAndLogicKey:
    """`_current_test_files` / `_logic_key` 的缺目录与读失败兜底。"""

    def test_missing_test_root_yields_nothing(self, drift_parts, monkeypatch, tmp_path):
        mod = drift_parts._shared
        monkeypatch.setattr(mod, "_TEST_ROOT", tmp_path / "no_such_root")
        assert mod._current_test_files() == {}

    def test_metadata_unavailable_degrades_to_placeholder(self, drift_parts, monkeypatch):
        """pytest 元数据取不到 → 指纹用 `?` 占位（降级为不等，偏向全量重收集）。"""
        mod = drift_parts._shared
        baseline = mod._logic_key()

        def _boom(_name):
            raise RuntimeError("元数据缺失")

        monkeypatch.setattr(mod.metadata, "version", _boom)
        degraded = mod._logic_key()

        assert len(degraded) == 40
        assert degraded != baseline, "取不到 pytest 版本须改变指纹，宁可使缓存失效也不陈旧"

    def test_unreadable_collect_script_degrades_to_placeholder(self, drift_parts, monkeypatch):
        """收集脚本/本模块读不到 → 同样用 `?` 占位而非抛错。"""
        mod = drift_parts._shared

        def _boom(_self):
            raise OSError("读不到")

        monkeypatch.setattr(Path, "read_bytes", _boom)
        assert len(mod._logic_key()) == 40


class TestRunCollectFailures:
    """`_run_collect` 的异常路径。"""

    def test_timeout_returns_none(self, drift_parts, monkeypatch):
        """收集超时与「收集失败」同路：返回 None（调用方不回写统计）。"""
        mod = drift_parts._shared

        def _timeout(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="collect", timeout=600)

        monkeypatch.setattr(mod.subprocess, "run", _timeout)
        assert mod._run_collect([]) is None


class TestShadowSwitch:
    """影子双算开关的环境变量与坏值处理。"""

    def test_env_force_on(self, drift_parts, monkeypatch):
        mod = drift_parts._shared
        monkeypatch.setenv("DOC_DRIFT_SNAPSHOT_SHADOW", "1")
        assert mod._shadow_active({"shadow_ok": mod._SHADOW_MATCHES_NEEDED}) is True

    def test_env_force_off(self, drift_parts, monkeypatch):
        mod = drift_parts._shared
        monkeypatch.setenv("DOC_DRIFT_SNAPSHOT_SHADOW", "0")
        assert mod._shadow_active({}) is False

    def test_corrupt_counter_keeps_shadow_on(self, drift_parts, monkeypatch):
        """`shadow_ok` 是垃圾值 → 视为未毕业，影子继续开（退化方向偏向多算）。"""
        mod = drift_parts._shared
        monkeypatch.delenv("DOC_DRIFT_SNAPSHOT_SHADOW", raising=False)
        assert mod._shadow_active({"shadow_ok": "不是数字"}) is True


class TestSnapshotIncrementBranches:
    """`_collect_test_snapshot` 的损坏 full 块、增量缺文件、影子计数坏值。"""

    @staticmethod
    def _store_pristine(mod, **overrides) -> dict:
        files = {rel: {"sig": mod._file_signature(p), "total": 1} for rel, p in mod._current_test_files().items()}
        files.update(overrides.get("files", {}))
        return files

    @classmethod
    def _seed(cls, mod, *, files: dict | None = None, full: dict | None = None, shadow_ok=0) -> None:
        path = mod._snapshot_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "format": mod._SNAPSHOT_FORMAT,
            "logic": mod._logic_key(),
            "shared": mod._shared_signature(),
            "files": cls._store_pristine(mod) if files is None else files,
            "full": full
            if full is not None
            else {"signature": mod._snapshot_signature(), "snapshot": {"_总收集": 4242, "unit": 10}},
            "shadow_ok": shadow_ok,
        }
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def test_corrupt_full_block_falls_back_to_full_collect(self, drift_parts, monkeypatch):
        """full 块里的值不是整数 → 不返回残缺桶，落到真全量收集。"""
        mod = drift_parts._shared
        self._seed(mod, full={"signature": mod._snapshot_signature(), "snapshot": {"unit": "不是数字"}})
        calls: list[list[str]] = []

        def _collect(args):
            calls.append(args)
            return {"_总收集": 2, "unit": 2}, {}

        monkeypatch.setattr(mod, "_run_collect", _collect)

        snap = mod._collect_test_snapshot(full_buckets=True)

        assert snap["unit"] == 2
        assert calls == [[]], "块损坏须重跑全量（且只跑全量）"

    def test_incremental_missing_changed_file_falls_back(self, drift_parts, monkeypatch):
        """逐文件输出缺变更文件 → 增量不可信，以全量为准。"""
        mod = drift_parts._shared
        first = next(iter(mod._current_test_files()))
        store = self._store_pristine(mod)
        store[first] = {"sig": "陈旧签名", "total": 1}
        self._seed(mod, files=store, shadow_ok=mod._SHADOW_MATCHES_NEEDED)
        collected: list[list[str]] = []

        def _collect(args):
            collected.append(args)
            if args:  # 增量：故意不回报变更文件
                return {"_总收集": 1}, {}
            return {"_总收集": 99}, {first: 99}

        monkeypatch.setattr(mod, "_run_collect", _collect)

        snap = mod._collect_test_snapshot()

        assert snap["_总收集"] == 99
        assert collected == [[first], []], "增量产出不全时须叠加全量"

    def test_corrupt_shadow_counter_restarts_from_zero(self, drift_parts, monkeypatch):
        """`shadow_ok` 坏值 → 计为 0，不阻断收集（坏缓存只影响毕业进度）。"""
        mod = drift_parts._shared
        first = next(iter(mod._current_test_files()))
        store = self._store_pristine(mod)
        store[first] = {"sig": "陈旧签名", "total": 1}
        self._seed(mod, files=store, shadow_ok="坏值")
        monkeypatch.setenv("DOC_DRIFT_SNAPSHOT_SHADOW", "1")
        monkeypatch.setattr(mod, "_run_collect", lambda args: ({"_总收集": 5}, {} if not args else {first: 5}))

        snap = mod._collect_test_snapshot()

        assert snap["_总收集"] == 5


# ═══ 目录树 / 统计表 / 区块矩阵 ═══


class TestDirTreeGhostEntries:
    """`check_dir_tree`：受检根内的幽灵条目被报出，根外条目不报。"""

    _TREE = (
        "```\n"
        "investor-review/\n"
        "├── src/\n"
        "│   └── ghost.py                      #   幽灵文件\n"
        "└── docs/\n"
        "    └── 无关.md                       #   受检根之外\n"
        "```\n"
    )

    def test_ghost_inside_tree_root_reported(self, drift, monkeypatch):
        monkeypatch.setattr(drift, "_actual_files", lambda: set())
        findings = drift.check_dir_tree(self._TREE)

        assert any("`src/ghost.py` 在磁盘上不存在" in f for f in findings)

    def test_ghost_outside_tree_roots_silent(self, drift, monkeypatch):
        monkeypatch.setattr(drift, "_actual_files", lambda: set())
        findings = drift.check_dir_tree(self._TREE)

        assert not any("docs/无关.md" in f for f in findings)


class TestSyncCellNumberGuards:
    """`_sync_cell_number` 的结构保护：列不存在 / 单元格无数字时原样返回。"""

    def test_out_of_range_column_returns_line(self, drift_parts):
        tree = drift_parts._tree
        line = "| a | b |\n"
        assert tree._sync_cell_number(line, 5, 3) == line

    def test_cell_without_number_returns_line(self, drift_parts):
        tree = drift_parts._tree
        line = "| 标签 | 说明 | 无数字 | 尾部 |\n"
        assert tree._sync_cell_number(line, 2, 7) == line


class TestBlockMatrixParseErrors:
    """`parse_block_matrix` 的结构性错误（缺表头/缺列/单元格不足/无数据行）。"""

    _HEADER = "| 章节 | HTML 区块数 | HTML 载体 | Excel 区块清单 | Excel 载体 |\n"
    _SEP = "| --- | --- | --- | --- | --- |\n"

    @staticmethod
    def _doc(*lines: str) -> str:
        return "## 4.22 章节-区块矩阵\n\n" + "".join(lines)

    def test_missing_header_column(self, drift_parts):
        rows, findings = drift_parts._tree.parse_block_matrix(
            self._doc("| 章节 | HTML 区块数 | HTML 载体 | Excel 区块清单 |\n", self._SEP)
        )
        assert rows == []
        assert any("矩阵表头缺少列" in f for f in findings)

    def test_no_header_row(self, drift_parts):
        rows, findings = drift_parts._tree.parse_block_matrix(self._doc("| 章节 | 说明 |\n"))
        assert rows == []
        assert any("未找到含「HTML 区块数」列的表头" in f for f in findings)

    def test_short_row_reported_and_skipped(self, drift_parts):
        rows, findings = drift_parts._tree.parse_block_matrix(self._doc(self._HEADER, self._SEP, "| 分析汇总 | 1 |\n"))
        assert rows == []
        assert any("矩阵行单元格数不足" in f for f in findings)
        assert any("表无数据行" in f for f in findings)

    def test_header_only_table_reports_no_rows(self, drift_parts):
        rows, findings = drift_parts._tree.parse_block_matrix(self._doc(self._HEADER, self._SEP))
        assert rows == []
        assert any("表无数据行" in f for f in findings)


class TestBlockMatrixBidirectionalFindings:
    """`check_block_matrix` 的键集与实现提取 finding 分支。"""

    @staticmethod
    def _doc(drift) -> str:
        return drift._TECHNICAL_MD.read_text(encoding="utf-8")

    @staticmethod
    def _rewrite_row(drift, row, *, key: str | None = None, partials: str | None = None) -> str:
        doc = drift._TECHNICAL_MD.read_text(encoding="utf-8")
        lines = doc.splitlines(keepends=True)
        idx = int(row["line"]) - 1
        if key is not None:
            lines[idx] = lines[idx].replace(f"`{row['key']}`", f"`{key}`", 1)
        if partials is not None:
            lines[idx] = lines[idx].replace(row["partials"], partials, 1)
        return "".join(lines)

    def test_parse_error_short_circuits(self, drift):
        """解析期即失败（无数据行）→ 直接返回解析 findings，不进入对账。"""
        findings = drift.check_block_matrix("## 4.22 章节-区块矩阵\n\n无表格\n")
        assert findings and all("章节-区块矩阵" in f for f in findings)

    def test_duplicate_matrix_key_reported(self, drift):
        rows, _ = drift.parse_block_matrix(self._doc(drift))
        lines = self._doc(drift).splitlines(keepends=True)
        lines[int(rows[1]["line"]) - 1] = lines[int(rows[1]["line"]) - 1].replace(
            f"`{rows[1]['key']}`", f"`{rows[0]['key']}`", 1
        )
        findings = drift.check_block_matrix("".join(lines))
        assert any("矩阵表章节 key 重复" in f for f in findings)

    def test_ghost_matrix_key_reported(self, drift):
        rows, _ = drift.parse_block_matrix(self._doc(drift))
        findings = drift.check_block_matrix(self._rewrite_row(drift, rows[0], key="幽灵章节"))
        assert any("不在注册表（删行或改 key）" in f for f in findings)

    def test_ghost_block_contract_reported(self, drift, monkeypatch):
        """区块注册表多出章节注册表没有的条目 → 报「不在章节注册表」。"""
        spec = SECTION_BLOCK_SPECS[next(iter(SECTION_BLOCK_SPECS))]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "幽灵契约章节", replace(spec))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("区块契约 `幽灵契约章节` 不在章节注册表" in f for f in findings)

    def test_partial_carrier_mismatch_reported(self, drift, monkeypatch):
        spec = SECTION_BLOCK_SPECS["summary"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "summary", replace(spec, partials=("holdings.html",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("HTML 载体与区块注册表不一致" in f for f in findings)

    def test_module_carrier_mismatch_reported(self, drift, monkeypatch):
        spec = SECTION_BLOCK_SPECS["summary"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "summary", replace(spec, modules=("excel_sections.py",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("Excel 载体与区块注册表不一致" in f for f in findings)

    def test_missing_partial_file_reported(self, drift, monkeypatch):
        spec = SECTION_BLOCK_SPECS["summary"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "summary", replace(spec, partials=("no_such.html",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("矩阵 HTML 载体不存在" in f for f in findings)

    def test_missing_module_file_reported(self, drift, monkeypatch):
        spec = SECTION_BLOCK_SPECS["summary"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "summary", replace(spec, modules=("no_such_mod.py",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("矩阵 Excel 载体不存在" in f for f in findings)

    def test_html_extraction_failure_reported(self, drift, drift_parts, monkeypatch):
        def _boom(_paths):
            raise ValueError("模板语法坏了")

        monkeypatch.setattr(drift_parts._tree, "extract_html_block_titles", _boom)
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("HTML 区块提取失败" in f for f in findings)

    def test_excel_extraction_failure_reported(self, drift, drift_parts, monkeypatch):
        def _boom(_paths):
            raise SyntaxError("模块语法坏了")

        monkeypatch.setattr(drift_parts._tree, "extract_excel_block_titles", _boom)
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("Excel 区块提取失败" in f for f in findings)
