"""check-doc-traces 文档域专项测试：目录树行豁免收窄、文件名任务编号、
任务记录域复盘痕迹（NARRATIVE）、结构性冗余（DUPLICATE）。

与 test_trace_check_scripts.py 同源（doc_traces fixture），按检查域拆分
文件——单测试文件行数红线 1200 行。
"""

from __future__ import annotations

import re
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


def _doc_hit(mod, line: str, task_record: bool = False) -> str | None:
    """返回 check-doc-traces 命中的 desc；未命中返回 None。

    与 scan_file 行为一致：对 CHAPTER/ROUND 应用计数/序数豁免；
    目录树行（│ ├ └ 开头）跳过通用豁免且仅 ARCHIVE 类豁免、STATUS
    仅在目录树行检出（正文当前状态叙述不检）；NARRATIVE 复盘叙事
    仅任务记录域检出（task_record=True）。
    """
    is_tree = bool(mod._TREE_LINE.match(line))
    if not is_tree and mod._is_excluded(line):
        return None
    for pat, cat, desc in mod._DOC_PATTERNS:
        if is_tree and cat == "ARCHIVE":
            continue
        if cat == "STATUS" and not is_tree:
            continue
        if cat == "NARRATIVE" and not task_record:
            continue
        if cat == "CHAPTER" and mod._is_chapter_excluded(line):
            continue
        if cat == "ROUND" and mod._is_round_excluded(line):
            continue
        if re.search(pat, line):
            return desc
    return None


class TestDocTreeLineNarrowing:
    """目录树行豁免收窄：仅 ARCHIVE 类豁免；任务编号（CODE）与进度状态
    词（STATUS）在树行照检，正文状态叙述不检（全类别树行豁免使目录树
    描述中的任务号与进度类措辞整体过闸）。"""

    def test_task_id_in_tree_line_flagged(self, doc_traces):
        assert _doc_hit(doc_traces, "│   ├── foo.py # 设计（plan-123）") is not None
        assert _doc_hit(doc_traces, "│   ├── foo.py # 设计（rf-456 关联）") is not None

    def test_status_word_in_tree_line_flagged(self, doc_traces):
        for line in (
            "│   ├── foo.py # 设计（已实施，验收记录）",
            "│   ├── foo.py # 设计（完成态）",
            "│   ├── foo.py # 设计（随任务完成移入）",
            "│   ├── foo.py # 设计（随功能落地移入）",
            "│   ├── foo.py # 设计（§8 转正迁移演练记录）",
            "│   ├── foo.py # 设计（4 迭代验收）",
            "│   ├── foo.py # 设计（立项依据）",
            "│   ├── foo.py # 设计（观察中）",
            "│   ├── foo.py # 设计（已归档）",
            "│   ├── foo.py # 设计（已核实，机制已具备）",
            "│   ├── foo.py # 设计（NaN 不再经 or 0.0 渗入）",
            "│   ├── foo.py # 设计草案（判定通道/降级矩阵）",
        ):
            assert _doc_hit(doc_traces, line) is not None, f"树行进度状态词未检出: {line}"

    def test_marker_enum_in_tree_line_exempt(self, doc_traces):
        """测试标记违规类别枚举（未注册/已移除/edge）属语义名，树行合法不检。"""
        line = "│   ├── test_check.py # 测试标记脚本测试（未注册·已移除·edge·目录期望四类违规）"
        assert _doc_hit(doc_traces, line) is None

    def test_migration_source_in_prose_flagged(self, doc_traces):
        """来源叙述补强：无后缀模块名的迁入/移入（带后缀文件模式覆盖不到）。"""
        assert _doc_hit(doc_traces, "归因生成器（自 generators 迁入，彼处 re-export）") is not None
        assert _doc_hit(doc_traces, "从 analysis 移入 core 的判定原语") is not None

    def test_archive_in_tree_line_exempt(self, doc_traces):
        """目录树行的 archive/ 与归档文件名指向仍豁免（结构记录合法指向）。"""
        assert _doc_hit(doc_traces, "│   ├── archived_x.md # 归档文件") is None
        assert _doc_hit(doc_traces, "│   ├── v0.9.x/ # 归档目录") is None

    def test_status_in_prose_not_flagged(self, doc_traces):
        """正文当前状态叙述（已实施/完成态）不检——进度词仅目录树域。"""
        assert _doc_hit(doc_traces, "因子暴露分析已实施，现为周期性复核工具") is None
        assert _doc_hit(doc_traces, "页面完成态按钮复位") is None


class TestDocFileNameTaskId:
    """文件名任务编号：受检域 .md 文件名含 rf-N/plan-N 即检出（语义命名
    补位——目录树比对只管存在性不管命名语义）。"""

    def test_plan_id_in_filename_flagged(self, doc_traces):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / "plan-123-design.md"
            fpath.write_text("# 设计\n", encoding="utf-8")
            hits = doc_traces.scan_file(fpath, verbose=False)
        code = [h for h in hits if h[1] == "CODE" and h[0] == 0]
        assert len(code) == 1, f"文件名任务编号未检出: {hits}"

    def test_rf_id_in_filename_flagged(self, doc_traces):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / "rf-456-notes.md"
            fpath.write_text("# 记录\n", encoding="utf-8")
            hits = doc_traces.scan_file(fpath, verbose=False)
        assert any(h[1] == "CODE" and h[0] == 0 for h in hits), f"未检出: {hits}"

    def test_semantic_filename_clean(self, doc_traces):
        """语义文件名（含 archived_plan.0.13.x.md 等含 plan 但非任务号形式）不检。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            for name in ("design-notes.md", "archived_plan.0.13.x.md"):
                fpath = Path(tmp) / name
                fpath.write_text("# 说明\n", encoding="utf-8")
                assert doc_traces.scan_file(fpath, verbose=False) == [], name


class TestDocTaskRecordDomain:
    """任务记录域（plan.md/review-findings/docs/plan）：NARRATIVE 复盘痕迹
    禁用（前后对比叙事/相对既有实现的否定句/历史归因），任务内容只反映
    最新状态；changelog 不适用（记录变化是其职责）；常规文档正文不检
    （手册操作指引语境）。"""

    def _scan_text(self, doc_traces, name: str, body: str):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / name
            fpath.write_text(body, encoding="utf-8")
            return doc_traces.scan_file(fpath, verbose=False, task_record=True)

    def test_before_after_comparison_flagged(self, doc_traces):
        hits = self._scan_text(doc_traces, "design.md", "断言修复前 33 过，修复后 35 过\n")
        assert any(h[1] == "NARRATIVE" for h in hits), f"前后对比未检出: {hits}"

    def test_negation_toward_old_implementation_flagged(self, doc_traces):
        hits = self._scan_text(doc_traces, "notes.md", "进度卡自动出现（不再 hidden）\n")
        assert any(h[1] == "NARRATIVE" for h in hits), f"不再未检出: {hits}"

    def test_history_attribution_flagged(self, doc_traces):
        for body in ("根因：历史原因导致超时\n", "照搬之前版本的口径\n"):
            hits = self._scan_text(doc_traces, "design.md", body)
            assert any(h[1] == "NARRATIVE" for h in hits), f"未检出: {body}"

    def test_latest_status_and_root_cause_legal(self, doc_traces):
        """最新状态标记与根因定位引用是内容，不属复盘叙事。"""
        for body in (
            "状态：已修复，断言 35 过 / 0 不过\n",
            "状态：进行中，见任务表\n",
            "根因见 §4 发现 1，取证文件保留\n",
        ):
            assert self._scan_text(doc_traces, "design.md", body) == [], body

    def test_table_row_narrative_flagged(self, doc_traces):
        """任务域不走表格豁免：断言表行内的前后对比叙事必须检出。"""
        hits = self._scan_text(doc_traces, "verify.md", "| 4.1 | 自动化 | 过（修复后复跑） |\n")
        assert any(h[1] == "NARRATIVE" for h in hits), f"表格行叙事未检出: {hits}"

    def test_changelog_domain_not_scanned_for_narrative(self, doc_traces):
        """changelog 走 chapter_only：复盘叙事不检（记录变化是其职责）。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / "changelog.md"
            fpath.write_text("### Changed\n- 由 A 改为 B，修复后全过\n", encoding="utf-8")
            hits = doc_traces.scan_file(fpath, verbose=False, chapter_only=True)
        assert not any(h[1] == "NARRATIVE" for h in hits), hits

    def test_regular_doc_narrative_not_scanned(self, doc_traces):
        """常规文档正文不检 NARRATIVE（手册操作指引语境）。"""
        assert _doc_hit(doc_traces, "变更后请重启服务再验证") is None


class TestDocStructuralDuplicates:
    """结构性冗余（DUPLICATE）：重复标题全域（路径感知）、重复长行/区块
    台账三文件 + 归档域。

    拦「同一区块/条目粘贴两遍」类复制粘贴残留（任务域小节整块重复、
    归档合并的重复版本节）；代码样本/键值任务卡/验证清单/围栏豁免。
    """

    def _write(self, tmp_path: Path, content: str, name: str = "doc.md") -> Path:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_repeated_heading_flagged_at_second_occurrence(self, doc_traces, tmp_path):
        """同级同文标题出现两次，第 2 次报出（首现行为合法不报）。"""
        doc = self._write(tmp_path, "## 开发期已修复\n\n正文\n\n## 开发期已修复\n\n重复节\n")
        hits = doc_traces.scan_structural_duplicates(doc)
        assert [(h[0], h[1]) for h in hits] == [(5, "DUPLICATE")]

    def test_cross_parent_repeated_subsection_ok(self, doc_traces, tmp_path):
        """路径感知判重：不同父标题下的同名小节（各版本块 Added）合法。"""
        doc = self._write(tmp_path, "## [1.0.0]\n\n### Added\n\n- a\n\n## [1.1.0]\n\n### Added\n\n- b\n")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_same_parent_repeated_subsection_flagged(self, doc_traces, tmp_path):
        """同父标题下同名小节复现（版本节两波 Added）即真重复，报出。"""
        doc = self._write(tmp_path, "## [1.0.0]\n\n### Added\n\n- a\n\n### Fixed\n\n- x\n\n### Added\n\n- b\n")
        hits = doc_traces.scan_structural_duplicates(doc)
        assert any(h[0] == 11 and "重复标题" in h[2] for h in hits), hits

    def test_heading_in_code_fence_excluded(self, doc_traces, tmp_path):
        """围栏代码块内 `#` 注释非标题，不得误报。"""
        doc = self._write(tmp_path, "# 查看帮助\n\n```bash\n# 检查全部\n# 检查全部\n```\n")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_repeated_long_line_flagged_only_in_ledger_docs(self, doc_traces, tmp_path):
        """≥40 字符重复行仅台账文件检出；常规手册同内容不检（域限定防误报）。"""
        row = "| **rf-1** | " + "冗长条目内容" * 8 + " |"
        body = f"| # | 摘要 |\n|---|---|\n{row}\n{row}\n"
        ledger = self._write(tmp_path / "ledgers", body, name="plan.md")
        hits = doc_traces.scan_structural_duplicates(ledger)
        assert any(h[1] == "DUPLICATE" and "重复内容行" in h[2] for h in hits), hits
        regular = self._write(tmp_path, f"说明段\n\n{row}\n{row}\n", name="manual.md")
        assert doc_traces.scan_structural_duplicates(regular) == []

    def test_repeated_block_flagged(self, doc_traces, tmp_path):
        """连续 5 行窗口逐字重复且内容 ≥100 字符，第 2 块报出。"""
        block = "## 节\n\n| # | 摘要 |\n|---|---|\n| **rf-9** | " + "内容" * 40 + " |\n"
        doc = self._write(tmp_path, block + "\n" + block, name="review-findings.md")
        hits = doc_traces.scan_structural_duplicates(doc)
        assert any(h[1] == "DUPLICATE" and "重复区块" in h[2] for h in hits), hits

    def test_short_template_and_separator_lines_excluded(self, doc_traces, tmp_path):
        """短模板行与分隔行重复是正常结构，不报。"""
        doc = self._write(
            tmp_path,
            "|---|------|----------|\n\n（本次发布内容见下方归档索引）\n\n|---|------|----------|\n\n（本次发布内容见下方归档索引）\n",
            name="changelog.md",
        )
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_checklist_lines_excluded_from_line_dedup(self, doc_traces, tmp_path):
        """验证清单命令跨阶段复跑属结构，长行判重豁免。"""
        cmd = "- [ ] `[全] python scripts/test_runner.py --mode regression --jobs 1`"
        doc = self._write(tmp_path, f"步骤\n\n{cmd}\n\n后续\n\n{cmd}\n", name="plan.md")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_task_card_window_excluded_from_block_dedup(self, doc_traces, tmp_path):
        """键值任务卡（- **键**: 值）跨任务同构，行与区块判重均豁免。"""
        card = (
            "- **估时**: 8h\n- **文件**: `src/python/analysis/rebalance.py`\n- **阻塞**: 否\n"
            "- **依赖**: P3-02（阈值系统）\n- **状态**: ✅ 已完成（2026-07-20）\n"
        )
        doc = self._write(tmp_path, f"### A\n\n{card}\n### B\n\n{card}", name="plan.md")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_code_sample_window_excluded_from_block_dedup(self, doc_traces, tmp_path):
        """未围栏代码样本跨节重复属图示，行与区块判重均豁免。"""
        sample = (
            "   from src.python.llm.api_base import (\n"
            "       _AUTO_INCREASE_FACTOR, _CACHE_LINE_HTML,\n"
            "   )\n   __all__ = [\n"
            '       "get", "set", "clear",\n'
        )
        doc = self._write(tmp_path, f"方案\n\n{sample}\n结果\n\n{sample}", name="plan.md")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_fenced_repeated_block_excluded(self, doc_traces, tmp_path):
        """围栏内容置空不入窗，两段相同围栏块不报。"""
        inner = "| # | 摘要 |\n|---|---|\n| **x** | " + "内容" * 40 + " |\n"
        doc = self._write(tmp_path, f"```text\n{inner}```\n说明\n\n```text\n{inner}```\n", name="plan.md")
        assert doc_traces.scan_structural_duplicates(doc) == []

    def test_archive_scope_line_dedup(self, doc_traces, tmp_path, monkeypatch):
        """归档域路径纳入长行/区块判重（REPO_ROOT 指向临时根）。"""
        monkeypatch.setattr(doc_traces, "REPO_ROOT", tmp_path)
        row = "| **rf-1** | " + "冗长条目内容" * 8 + " |"
        doc = self._write(tmp_path / "docs" / "archive", f"说明段\n\n{row}\n{row}\n", name="old.md")
        hits = doc_traces.scan_structural_duplicates(doc)
        assert any("重复内容行" in h[2] for h in hits), hits


class TestDocArchiveDomain:
    """归档域（archive=True）：NARRATIVE 复盘痕迹检出，模式面收窄。"""

    def _scan(self, doc_traces, tmp_path, content: str):
        p = tmp_path / "doc.md"
        p.write_text(content, encoding="utf-8")
        return doc_traces.scan_file(p, False, archive=True)

    def test_archive_narrative_flagged(self, doc_traces, tmp_path):
        """归档设计/迭代文档的前后对比与否定句报出（只表述最新状态）。"""
        hits = self._scan(doc_traces, tmp_path, "回归清单：修复后全过。\n")
        assert any(h[1] == "NARRATIVE" for h in hits), hits

    def test_archive_not_scanning_history_ciphers(self, doc_traces, tmp_path):
        """归档域不查 CIPHER/章节/轮次（历史文档性质，仅 DUPLICATE+NARRATIVE）。"""
        assert self._scan(doc_traces, tmp_path, "按 C20 约束设计，详见第 3 章与第 2 轮。\n") == []

    def test_archive_current_capability_exclusion(self, doc_traces, tmp_path):
        """当前能力描述豁免（支持类否定前缀）在归档域生效；变体仍报出。"""
        assert self._scan(doc_traces, tmp_path, "该源不再支持增量拉取。\n") == []
        hits = self._scan(doc_traces, tmp_path, "峰谷价不再区分。\n")
        assert any(h[1] == "NARRATIVE" for h in hits), hits

    def test_inline_code_token_not_flagged(self, doc_traces, tmp_path):
        """行内代码技术令牌（词表条目 `不再`）不误报；裸词仍报。"""
        assert self._scan(doc_traces, tmp_path, "词表条目 `不再` 属技术令牌。\n") == []
        hits = self._scan(doc_traces, tmp_path, "词表含不再条目。\n")
        assert any(h[1] == "NARRATIVE" for h in hits), hits
