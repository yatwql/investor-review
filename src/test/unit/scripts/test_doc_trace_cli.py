"""测试：check-doc-traces.py CLI 编排（受检文档收集 / 退出码契约 / 结论缓存回放）。

覆盖：
  - `_iter_docs` 两态清单（常规域排除归档/plan/tmp 与豁免三文档；豁免域取
    豁免三文档 + docs/plan）与 `_iter_archive_docs`（归档域缺目录时为空）
  - `main` 退出码契约：无痕迹=0 / 含高置信度痕迹=1 / 仅 LOW=2
  - `--ci` 结论缓存命中逐字回放（不进全量扫描）、未命中时写回汇总结构
  - `-v` 详细输出（命中行正文与报告项）
  - `scan_file` 的读取失败短路、空行/围栏行跳过、verbose 旁注、
    章节与轮次计数豁免（整行语义豁免优先于分类命中）

夹具全在 tmp_path 造最小文档树，扫描目录/README 均指向临时目录；已删函数
残留扫描（依赖真实 git 历史）在 CLI 用例中替换为空实现，保持确定性。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def doc_traces():
    return load_script("check-doc-traces.py")


@pytest.fixture
def doc_tree(doc_traces, monkeypatch, tmp_path):
    """最小受检文档树：README + 管理/手册/计划目录 + docs/archive。"""
    repo = tmp_path / "repo"
    managements = repo / "docs" / "managements"
    manuals = repo / "docs" / "manuals"
    plan = repo / "docs" / "plan"
    for d in (managements, manuals, plan):
        d.mkdir(parents=True)
    (repo / "README.md").write_text("# 入口\n\n当前能力说明。\n", encoding="utf-8")
    (managements / "technical.md").write_text("# 技术\n\n当前结构。\n", encoding="utf-8")
    (managements / "changelog.md").write_text("# 变更\n\n## 1. 记录\n", encoding="utf-8")
    (managements / "plan.md").write_text("# 计划\n\n## 1. 事项\n", encoding="utf-8")
    (managements / "review-findings.md").write_text("# 自审\n\n## 1. 条目\n", encoding="utf-8")
    (managements / "archive").mkdir()
    (managements / "archive" / "old.md").write_text("# 归档\n", encoding="utf-8")
    (manuals / "how-to-start.md").write_text("# 上手\n\n命令如下。\n", encoding="utf-8")
    (plan / "design-draft.md").write_text("# 设计\n\n## 1. 目标\n", encoding="utf-8")
    monkeypatch.setattr(doc_traces, "REPO_ROOT", repo)
    monkeypatch.setattr(doc_traces, "README_PATH", repo / "README.md")
    monkeypatch.setattr(doc_traces, "DOC_DIRS", [managements, manuals])
    monkeypatch.setattr(doc_traces, "PLAN_DOCS_DIR", plan)
    # 已删函数残留依赖真实 git 历史：CLI 用例注入空实现保确定性
    monkeypatch.setattr(doc_traces, "scan_deleted_symbol_refs", lambda doc: [])
    return repo


@pytest.fixture
def cache_stub(doc_traces, monkeypatch):
    """结论缓存读写替身：记录写回调用（结论结构断言），缺省不命中。"""

    class _Cache:
        def __init__(self) -> None:
            self.saved: list[dict] = []
            self.replay: dict | None = None

    cache = _Cache()
    monkeypatch.setattr(doc_traces, "conclusion_cache_load", lambda *a, **k: cache.replay)
    monkeypatch.setattr(doc_traces, "conclusion_cache_save", lambda *a, **k: cache.saved.append(a[3]))
    return cache


def _run(doc_traces, monkeypatch, capsys, *argv: str) -> tuple[int, str]:
    """跑一次 CLI，返回 (退出码, stdout)。"""
    monkeypatch.setattr(sys, "argv", ["check-doc-traces.py", *argv])
    rc = doc_traces.main()
    return rc, capsys.readouterr().out


def _set_doc(repo: Path, name: str, text: str) -> None:
    (repo / "docs" / "managements" / name).write_text(text, encoding="utf-8")


class TestIterDocs:
    """受检文档收集两态清单与归档域。"""

    def test_regular_scope_excludes_history_and_skipped_dirs(self, doc_traces, doc_tree):
        """常规域：README + 未豁免文档；豁免三文档与 archive/ 子树、docs/plan 不入列。"""
        names = [p.name for p in doc_traces._iter_docs()]
        assert "README.md" in names
        assert "technical.md" in names
        assert "how-to-start.md" in names
        assert set(names) & {"changelog.md", "plan.md", "review-findings.md"} == set()
        assert "old.md" not in names
        assert "design-draft.md" not in names

    def test_trace_exempt_scope_takes_history_and_plan_docs(self, doc_traces, doc_tree):
        """豁免域：仅豁免三文档 + docs/plan 下的计划文档。"""
        names = [p.name for p in doc_traces._iter_docs(trace_exempt=True)]
        assert set(names) == {"changelog.md", "plan.md", "review-findings.md", "design-draft.md"}

    def test_archive_scope_empty_without_archive_dir(self, doc_traces, doc_tree):
        """归档域目录缺失 → 空清单（不抛错）。"""
        assert doc_traces._iter_archive_docs() == []

    def test_archive_scope_lists_archive_docs(self, doc_traces, doc_tree):
        """归档域存在时列出全部归档 .md。"""
        archive = doc_tree / "docs" / "archive" / "v1"
        archive.mkdir(parents=True)
        (archive / "archived_plan.1.md").write_text("# 归档计划\n", encoding="utf-8")
        assert [p.name for p in doc_traces._iter_archive_docs()] == ["archived_plan.1.md"]

    def test_missing_doc_dir_skipped_in_both_modes(self, doc_traces, doc_tree, monkeypatch):
        """受检目录不存在时不抛错（两态清单均跳过）。"""
        monkeypatch.setattr(doc_traces, "DOC_DIRS", [*doc_traces.DOC_DIRS, doc_tree / "nowhere"])
        assert [p.name for p in doc_traces._iter_docs()]
        assert [p.name for p in doc_traces._iter_docs(trace_exempt=True)]


class TestExitCodeContract:
    """main 的退出码契约（0=干净 / 1=高置信度 / 2=仅 LOW）。"""

    def test_clean_docs_exit_zero(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 0
        assert "文档干净" in out

    def test_high_confidence_trace_exit_one(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """高置信度痕迹样本 → 退出码 1。"""
        _set_doc(doc_tree, "technical.md", "# 技术\n\n原实现直接读取缓存。\n")
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 1
        assert "[HIGH]" in out

    def test_low_only_exit_two(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """仅 LOW 级别痕迹 → 退出码 2（人工复核）。"""
        _set_doc(doc_tree, "technical.md", "# 技术\n\n待后续迭代补强。\n")
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 2
        assert "[LOW]" in out

    def test_changelog_scanned_for_chapter_only(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """changelog 仅查章节编号：版本号类历史痕迹合法，章节暗号照检。"""
        _set_doc(doc_tree, "changelog.md", "# 变更\n\nv0.9.9 记录。\n\n见第 3 章。\n")
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 1
        assert "[CHAPTER]" in out
        assert "changelog.md" in out

    def test_verbose_prints_hit_text(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """-v 输出命中行正文（非 CI 的详细形态）。"""
        _set_doc(doc_tree, "technical.md", "# 技术\n\n原实现直接读取缓存。\n")
        rc, out = _run(doc_traces, monkeypatch, capsys, "-v")
        assert rc == 1
        assert "原实现直接读取缓存" in out

    def test_ci_mode_prints_file_line_form(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """--ci 只输出「文件:行号 [分类] 说明 — 正文」形态行。"""
        _set_doc(doc_tree, "technical.md", "# 技术\n\n原实现直接读取缓存。\n")
        rc, out = _run(doc_traces, monkeypatch, capsys, "--ci")
        assert rc == 1
        hit_lines = [ln for ln in out.splitlines() if "[HIGH]" in ln]
        assert hit_lines and ":3 " in hit_lines[0]


class TestArchiveDomain:
    """归档域：非 changelog 归档查复盘叙事，changelog 归档不查（记录变化是其职责）。"""

    def test_archive_narrative_flagged(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        archive = doc_tree / "docs" / "archive" / "v1"
        archive.mkdir(parents=True)
        (archive / "archived_design.md").write_text("# 设计\n\n不再使用旧调度。\n", encoding="utf-8")
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 1
        assert "[NARRATIVE]" in out
        assert "archived_design.md" in out

    def test_archive_changelog_not_scanned_for_narrative(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        archive = doc_tree / "docs" / "archive" / "v1"
        archive.mkdir(parents=True)
        (archive / "archived_changelog.1.md").write_text("# 变更\n\n不再使用旧调度。\n", encoding="utf-8")
        rc, out = _run(doc_traces, monkeypatch, capsys)
        assert rc == 0
        assert "archived_changelog.1.md" not in out


class TestConclusionCache:
    """--ci 结论缓存：命中逐字回放、未命中写回汇总结构。"""

    def test_cache_hit_replays_without_scan(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        cache_stub.replay = {
            "findings": ["README.md:1 [HIGH] 缓存行 — 回放"],
            "total": 1,
            "high": 1,
            "low": 0,
            "summary": {"HIGH": 1},
        }
        rc, out = _run(doc_traces, monkeypatch, capsys, "--ci")
        assert rc == 1
        assert "README.md:1 [HIGH] 缓存行 — 回放" in out
        assert cache_stub.saved == []  # 命中不再写回

    def test_cache_miss_saves_summary(self, doc_traces, doc_tree, cache_stub, monkeypatch, capsys):
        """未命中 → 全量扫描后写回（总数/高/低/分类统计与输出同源）。"""
        _set_doc(doc_tree, "technical.md", "# 技术\n\n原实现直接读取缓存。\n")
        _run(doc_traces, monkeypatch, capsys, "--ci")
        assert len(cache_stub.saved) == 1
        conclusion = cache_stub.saved[0]
        assert conclusion["total"] == conclusion["high"] + conclusion["low"]
        assert sum(conclusion["summary"].values()) == conclusion["total"]
        assert len(conclusion["findings"]) == conclusion["total"]


class TestScanFileGaps:
    """scan_file 的短路/跳过/verbose 旁注与整行语义豁免。"""

    def test_unreadable_doc_short_circuits(self, doc_traces, tmp_path):
        """文档读取失败（不存在）→ 立即返回（无正文可查）。"""
        assert doc_traces.scan_file(tmp_path / "missing.md", verbose=False) == []

    def test_blank_and_fence_lines_skipped(self, doc_traces, tmp_path):
        """空行与围栏行（开关标记）不计入痕迹扫描。"""
        doc = tmp_path / "sample.md"
        doc.write_text("# 标题\n\n```bash\ngit tag v0.9.9\n```\n\n原实现直接读取缓存。\n", encoding="utf-8")
        hits = doc_traces.scan_file(doc, verbose=False)
        assert [h[1] for h in hits] == ["HIGH"]
        assert hits[0][0] == 7  # 仅围栏外的叙述行命中

    def test_verbose_annotates_skipped_lines(self, doc_traces, tmp_path, capsys):
        """-v 时打印围栏内跳过与整行豁免旁注（不改变命中结果）。"""
        doc = tmp_path / "sample.md"
        doc.write_text("# 标题\n\n```\ngit tag v0.9.9\n```\n\n暂不支持该模式。\n", encoding="utf-8")
        assert doc_traces.scan_file(doc, verbose=True) == []
        out = capsys.readouterr().out
        assert "(codeblock)" in out
        assert "(excluded)" in out

    def test_verbose_annotates_chapter_exclusion(self, doc_traces, tmp_path, capsys):
        """-v 且 changelog 域时打印章节计数豁免旁注（整行语义豁免）。"""
        doc = tmp_path / "changelog.md"
        doc.write_text("# 变更\n\n本报告共 19 章。\n", encoding="utf-8")
        assert doc_traces.scan_file(doc, verbose=True, chapter_only=True) == []
        assert "(ch-excluded)" in capsys.readouterr().out

    def test_count_exempt_chapter_and_round_skipped(self, doc_traces, tmp_path):
        """章节/轮次计数表述整行豁免；同形暗号（第 N 章 / 经 N 轮）照检。"""
        doc = tmp_path / "sample.md"
        doc.write_text("本报告共 19 章。\n验收分共 12 轮。\n", encoding="utf-8")
        assert doc_traces.scan_file(doc, verbose=False) == []
        doc.write_text("见第 3 章。\n经 8 轮迭代。\n", encoding="utf-8")
        hits = doc_traces.scan_file(doc, verbose=False)
        assert sorted(h[1] for h in hits) == ["CHAPTER", "ROUND"]
