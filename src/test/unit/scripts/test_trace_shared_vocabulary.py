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
