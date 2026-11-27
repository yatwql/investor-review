"""测试：doc-traces 已删除函数残留检查（scan_deleted_symbol_refs）。

覆盖：已删函数引用检出（带括号/无括号反引号形态）/ 现存函数不误报 /
从未存在（第三方名）不误报 / 短名与无下划线名过滤 / 同行多残留 /
git 不可用（历史集为空）静默跳过。

historical/current 集合由测试注入，不依赖真实 git 历史（确定性）。
"""

from __future__ import annotations

import contextlib
import io
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from src.test._script_loader import load_script


@pytest.fixture(scope="module")
def doc_traces():
    return load_script("check-doc-traces.py")


@pytest.fixture(scope="module")
def deleted_refs():
    """已删函数残留检查的实现模块（缓存与 git 调用点在此，patch 必须指向它）。"""
    return load_script("_traces_doc/deleted_refs.py", module_name="doc_traces_deleted_refs")


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


class TestHistoricalDefsEnvironment:
    """历史 def 全集的环境防护（浅克隆不静默假绿）。"""

    def test_shallow_clone_skips_with_warning(self, deleted_refs):
        """浅克隆 → 空集 + stderr 告警（防 CI 浅克隆下历史集≈当前集全漏报）。"""
        deleted_refs._HIST_DEFS = None
        try:
            with patch.object(deleted_refs, "subprocess") as msub:
                msub.run.return_value = SimpleNamespace(returncode=0, stdout="true\n", stderr="")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    assert deleted_refs._historical_defs() == set()
            assert "浅克隆" in err.getvalue()
        finally:
            deleted_refs._HIST_DEFS = None  # 复位进程级缓存防污染后续用例

    def test_full_clone_parses_added_defs(self, deleted_refs):
        """全历史 → 解析 +def 新增行（含 async）。"""
        deleted_refs._HIST_DEFS = None
        shallow = SimpleNamespace(returncode=0, stdout="false\n", stderr="")
        log = SimpleNamespace(
            returncode=0,
            stdout="+def _sample_added_fn(a):\n+    pass\n+async def _sample_async_fn():\n",
            stderr="",
        )
        try:
            with patch.object(deleted_refs, "subprocess") as msub:
                msub.run.side_effect = [shallow, log]
                hist = deleted_refs._historical_defs()
            assert "_sample_added_fn" in hist
            assert "_sample_async_fn" in hist
        finally:
            deleted_refs._HIST_DEFS = None

    def test_git_unavailable_skips_with_warning(self, deleted_refs):
        """git 不可用（OSError）→ 空集 + stderr 告警，不抛错。"""
        deleted_refs._HIST_DEFS = None
        try:
            with patch.object(deleted_refs.subprocess, "run") as mrun:
                mrun.side_effect = OSError("git 缺失")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    assert deleted_refs._historical_defs() == set()
            assert "git 不可用" in err.getvalue()
        finally:
            deleted_refs._HIST_DEFS = None

    def test_git_log_timeout_skips_with_warning(self, deleted_refs):
        """`git log` 超时（大仓历史提取超时）→ 空集 + stderr 告警。"""
        deleted_refs._HIST_DEFS = None
        shallow = SimpleNamespace(returncode=0, stdout="false\n", stderr="")
        try:
            with patch.object(deleted_refs.subprocess, "run") as mrun:
                mrun.side_effect = [shallow, subprocess.TimeoutExpired("git log", 600)]
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    assert deleted_refs._historical_defs() == set()
            assert "git log 超时" in err.getvalue()
        finally:
            deleted_refs._HIST_DEFS = None


class TestCurrentDefsScan:
    """当前 def 全集（真实库存扫描，模块级缓存）。"""

    def test_scans_repository_definitions(self, deleted_refs):
        """扫描 src/ 与 scripts/ 得到当前 def 名（含本模块自身的函数）。"""
        deleted_refs._CUR_DEFS = None
        try:
            defs = deleted_refs._current_defs()
        finally:
            deleted_refs._CUR_DEFS = None  # 复位进程级缓存
        assert "scan_deleted_symbol_refs" in defs  # scripts/ 下的函数
        assert "run_checks" in defs  # src/python 下的函数

    def test_cache_returns_same_set(self, deleted_refs):
        """二次调用命中缓存（同一集合对象，不重复走盘）。"""
        deleted_refs._CUR_DEFS = None
        try:
            first = deleted_refs._current_defs()
            assert deleted_refs._current_defs() is first
        finally:
            deleted_refs._CUR_DEFS = None

    def test_unreadable_file_skipped(self, deleted_refs, monkeypatch, tmp_path):
        """个别文件读不开（如以 .py 结尾的目录）→ 跳过该条目，其余照收。"""
        repo = tmp_path / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "good.py").write_text("def alpha_fn():\n    pass\n", encoding="utf-8")
        (repo / "scripts" / "bad.py").mkdir()
        monkeypatch.setattr(deleted_refs, "REPO_ROOT", repo)
        deleted_refs._CUR_DEFS = None
        try:
            assert deleted_refs._current_defs() == {"alpha_fn"}
        finally:
            deleted_refs._CUR_DEFS = None


class TestUnreadableDoc:
    """文档读取失败（路径不存在/解码失败）→ 静默跳过。"""

    def test_unreadable_doc_skipped(self, doc_traces, tmp_path):
        """读取失败 → 空命中（前缀名仍按文件名规则判，但无正文可查）。"""
        hits = doc_traces.scan_deleted_symbol_refs(
            tmp_path / "missing.md", historical_defs={"_old_helper_fn"}, current_defs=set()
        )
        assert hits == []
