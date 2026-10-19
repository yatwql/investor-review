"""测试：doc-traces 已删除函数残留检查（scan_deleted_symbol_refs）。

覆盖：已删函数引用检出（带括号/无括号反引号形态）/ 现存函数不误报 /
从未存在（第三方名）不误报 / 短名与无下划线名过滤 / 同行多残留 /
git 不可用（历史集为空）静默跳过。

historical/current 集合由测试注入，不依赖真实 git 历史（确定性）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src.test._script_loader import load_script


@pytest.fixture(scope="module")
def doc_traces():
    return load_script("check-doc-traces.py")


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


def _hits(mod, tmp_path: Path, text: str, *, hist: set[str], cur: set[str] | None = None) -> list:
    """写临时文档并扫描（current 默认空集=当前无任何 def，放大检出面）。"""
    doc = tmp_path / "sample.md"
    doc.write_text(text, encoding="utf-8")
    return mod.scan_deleted_symbol_refs(doc, historical_defs=hist, current_defs=cur if cur is not None else set())


class TestScanDeletedSymbolRefs:
    """已删除函数残留（文档反引号引用当前无 def 但 git 历史有）。"""

    def test_deleted_ref_reported(self, doc_traces, tmp_path):
        """历史存在 + 当前无定义 + 反引号引用（带括号）→ CODE 命中。"""
        hits = _hits(doc_traces, tmp_path, "调用 `_old_helper_fn()` 完成。\n", hist={"_old_helper_fn"})
        assert len(hits) == 1
        assert hits[0][1] == "CODE"
        assert "已删除函数残留" in hits[0][2]

    def test_bare_backtick_no_paren_reported(self, doc_traces, tmp_path):
        """无括号反引号形态（模块表风格）同样检出。"""
        hits = _hits(
            doc_traces, tmp_path, "| 模块 | `_old_helper_fn` 交互询问——已并入新链路 |\n", hist={"_old_helper_fn"}
        )
        assert len(hits) == 1
        assert hits[0][1] == "CODE"

    def test_existing_not_reported(self, doc_traces, tmp_path):
        """当前仍有定义（历史也有）→ 不报。"""
        hits = _hits(
            doc_traces, tmp_path, "调用 `_cur_live_fn()` 完成。\n", hist={"_cur_live_fn"}, cur={"_cur_live_fn"}
        )
        assert hits == []

    def test_never_existed_not_reported(self, doc_traces, tmp_path):
        """从未定义过（第三方/伪代码，历史集不含）→ 不报。"""
        hits = _hits(doc_traces, tmp_path, "配置 `third_party_sdk_fn()` 参数。\n", hist={"_other_gone_fn"})
        assert hits == []

    def test_short_and_underscoreless_filtered(self, doc_traces, tmp_path):
        """短名（is_ok）与无下划线名（abcdefgh）不入候选，即使历史有也不报。"""
        hits = _hits(doc_traces, tmp_path, "用 `abcdefgh` 与 `is_ok` 判断。\n", hist={"abcdefgh", "is_ok"})
        assert hits == []

    def test_multi_hit_same_line(self, doc_traces, tmp_path):
        """同行两个已删函数 → 各报一条。"""
        hits = _hits(
            doc_traces,
            tmp_path,
            "链路 `_alpha_removed_fn()` 与 `_beta_removed_fn()` 串联。\n",
            hist={"_alpha_removed_fn", "_beta_removed_fn"},
        )
        assert len(hits) == 2

    def test_empty_hist_skips(self, doc_traces, tmp_path):
        """历史集为空（git 不可用语义）→ 静默跳过，不误报。"""
        hits = _hits(doc_traces, tmp_path, "调用 `_old_helper_fn()` 完成。\n", hist=set())
        assert hits == []
