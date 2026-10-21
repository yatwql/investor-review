"""测试：check-code-traces / check-doc-traces 共享历史叙述词表（单一来源）。

两脚本作用面不同（代码注释 vs 面向读者文档），但历史叙述正则高度重合。
`_traces_common` 把**逐字节相同**的正则收敛为常量，两侧模式表引用常量、
各自保留分类与描述。本文件锁三件事：

  1. 共享词表无重复登记，且两侧模式表**都**实际引用每一条（漏接即漏检）；
  2. 两表交集恰等于共享词表（新增同源模式必须收编，不得再复制一份）；
  3. 字面量不再出现在两侧模式源码里（防有人图省事重新写死，漂移面回归）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]

#: 仓库根 `scripts/`（本文件位于 src/test/unit/scripts/，向上 4 级即仓库根）
_SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"


@pytest.fixture(scope="module")
def vocabulary():
    """共享词表模块（独立实例，避免与 CLI 加载时的模块状态耦合）。"""
    return load_script("_traces_common.py", module_name="_traces_common_vocabulary")


@pytest.fixture(scope="module")
def code_traces():
    return load_script("check-code-traces.py")


@pytest.fixture(scope="module")
def doc_traces():
    return load_script("check-doc-traces.py")


class TestSharedVocabularyWiring:
    def test_shared_regexes_are_unique(self, vocabulary):
        """共享词表不得重复登记同一条正则（重复即说明有两个语义名指向同一模式）。"""
        assert len(vocabulary.SHARED_REGEXES) == len(set(vocabulary.SHARED_REGEXES))

    def test_both_pattern_tables_reference_every_shared_regex(self, vocabulary, code_traces, doc_traces):
        """两侧模式表都必须引用共享词表的每一条（漏接的一侧会静默漏检）。"""
        shared = set(vocabulary.SHARED_REGEXES)
        code_patterns = {pat for pat, _cat, _desc in code_traces.PATTERNS}
        doc_patterns = {pat for pat, _cat, _desc in doc_traces._DOC_PATTERNS}
        assert shared <= code_patterns
        assert shared <= doc_patterns

    def test_pattern_table_intersection_equals_shared_vocabulary(self, vocabulary, code_traces, doc_traces):
        """两表交集必须恰为共享词表：新增同源模式未收编即报出（漂移面回归）。"""
        code_patterns = {pat for pat, _cat, _desc in code_traces.PATTERNS}
        doc_patterns = {pat for pat, _cat, _desc in doc_traces._DOC_PATTERNS}
        assert (code_patterns & doc_patterns) == set(vocabulary.SHARED_REGEXES)

    @pytest.mark.parametrize("module_file", ["_traces_code/patterns.py", "_traces_doc/patterns.py"])
    def test_no_hardcoded_duplicate_of_shared_literals(self, vocabulary, module_file):
        """模式源码不得再出现共享词表的字面量（一律走常量引用）。"""
        source = (_SCRIPTS_DIR / module_file).read_text(encoding="utf-8")
        hardcoded = sorted(lit for lit in vocabulary.SHARED_REGEXES if f'r"{lit}"' in source)
        assert hardcoded == []


class TestMultiDomainPattern:
    def test_not_used_regex_registered_in_both_domains(self, doc_traces):
        """同一正则多域登记（`不再`）：分类按域区分，正则只写一份。"""
        entries = [(cat, desc) for pat, cat, desc in doc_traces._DOC_PATTERNS if pat == "不再"]
        assert {cat for cat, _desc in entries} == {"STATUS", "NARRATIVE"}

    def test_pattern_tables_have_no_duplicate_entries(self, doc_traces, code_traces):
        """模式表内不得出现完全重复条目（同正则+分类+描述写两遍）。"""
        assert len(set(doc_traces._DOC_PATTERNS)) == len(doc_traces._DOC_PATTERNS)
        assert len(set(code_traces.PATTERNS)) == len(code_traces.PATTERNS)


class TestDocDomainMatrix:
    """文档类型 → 检查分类矩阵：**管控差异**必须显式且不空转。

    共享词表只统一"词汇"，不同类型文档查哪些分类是各自口径（常规域禁复盘叙事/
    进度词、任务记录域查章节+叙事、归档域只查叙事…）。这里钉住矩阵的两端：
    启用的分类必须已声明且至少有一条模式（否则分域静默停检），以及最关键的
    差异口径不被"顺手统一"掉。
    """

    _DOMAIN_NAMES = (
        "DOMAIN_ARCHIVE",
        "DOMAIN_TASK_RECORD",
        "DOMAIN_CHANGELOG",
        "DOMAIN_TREE_ARCHIVE",
        "DOMAIN_TREE_PLAN",
    )

    def test_domain_categories_are_declared(self, doc_traces):
        declared = set(doc_traces._ALL_CATEGORIES)
        for name in self._DOMAIN_NAMES:
            unknown = set(getattr(doc_traces, name)) - declared
            assert unknown == set(), f"{name} 启用未声明分类 {sorted(unknown)}"

    def test_domain_category_has_patterns(self, doc_traces):
        pattern_categories = {cat for _pat, cat, _desc in doc_traces._DOC_PATTERNS}
        for name in self._DOMAIN_NAMES:
            empty = set(getattr(doc_traces, name)) - pattern_categories
            assert empty == set(), f"{name} 启用了无模式的分类 {sorted(empty)}（该域静默停检）"

    def test_regular_domain_excludes_narrative_and_status(self, doc_traces):
        """常规文档不查复盘叙事/进度词（手册的当前状态叙述合法），差异口径不可统一。"""
        assert "NARRATIVE" not in doc_traces._REGULAR_CATEGORIES
        assert "STATUS" not in doc_traces._REGULAR_CATEGORIES

    def test_archive_domain_is_narrative_only(self, doc_traces):
        """归档文档的性质是历史记录：版本/章节/轮次/约束代号均不入检。"""
        assert set(doc_traces.DOMAIN_ARCHIVE) == {"NARRATIVE"}


class TestCodeSeverityBucket:
    """代码域分类 → 退出码分桶：桶必须是**划分**，且覆盖模式表全部分类。

    未登记的分类会落进 LOW 兜底（静默降级为"仅建议复核"），CI 仍绿而高置信度
    痕迹被吞——故双向量化：三桶互斥、模式表分类 ⊆ 三桶之并。
    """

    def test_buckets_are_disjoint(self, code_traces):
        high = set(code_traces.HIGH_CATEGORIES)
        code = set(code_traces.CODE_CATEGORIES)
        low = set(code_traces.LOW_CATEGORIES)
        assert not (high & code)
        assert not (high & low)
        assert not (code & low)

    def test_pattern_categories_are_all_bucketed(self, code_traces):
        covered = set(code_traces.HIGH_CATEGORIES) | set(code_traces.CODE_CATEGORIES) | set(code_traces.LOW_CATEGORIES)
        pattern_categories = {cat for _pat, cat, _desc in code_traces.PATTERNS}
        assert pattern_categories - covered == set()

    def test_scan_emitted_categories_are_bucketed(self, code_traces, tmp_path):
        """标识符/分层/日志等非模式表通道产出的分类同样必须在桶内。"""
        sample = tmp_path / "sample_bad.py"
        sample.write_text(
            "# 已迁移到新模块\n"
            "# 第 3 章 与 第 2 轮\n"
            "# B系列 批次代号与 C1 约束代号\n"
            "r11_magic = 1\n"
            "def f():\n"
            "    print('诊断输出')\n",
            encoding="utf-8",
        )
        hits = code_traces.scan_file(sample, verbose=False)
        covered = set(code_traces.HIGH_CATEGORIES) | set(code_traces.CODE_CATEGORIES) | set(code_traces.LOW_CATEGORIES)
        emitted = {cat for _line, cat, _desc, _text in hits}
        assert emitted - covered == set()
