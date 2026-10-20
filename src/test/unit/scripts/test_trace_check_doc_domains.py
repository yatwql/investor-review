"""check-doc-traces 文档域专项测试：目录树行豁免收窄、文件名任务编号、
任务记录域复盘痕迹（NARRATIVE）。

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
