"""测试：check-doc-links.py 的 CLI 编排与中文序号/不可读目标分支。

覆盖：
  - 中文数字序号解析：整十（十/二十）与十位带个位（十一/二十一）连续放行、跳变检出
  - 跨文件死锚点、目标 .md 不可解码（死文件链接）、§ 引用归属不在扫描集内时跳过
  - 受检文档自身不可读 → finding「无法读取文档」（不中断其余检查）
  - `main`：默认/详细（-v）/`--ci` 缓存命中回放/缓存未命中写回 的退出码契约
  - `if __name__ == "__main__"` 入口（按 __main__ 执行真实文档集，退出码 0）

夹具全在 tmp_path 造最小文档集，`default_targets` 与结论缓存读写均替换为替身。
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def links():
    return load_script("check-doc-links.py")


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def cache_stub(links, monkeypatch):
    """结论缓存读写替身：缺省不命中，记录写回结论。"""

    class _Cache:
        replay: dict | None = None
        saved: list[dict] = []

    cache = _Cache()
    monkeypatch.setattr(links, "conclusion_cache_load", lambda *a, **k: cache.replay)
    monkeypatch.setattr(links, "conclusion_cache_save", lambda *a, **k: cache.saved.append(a[3]))
    return cache


def _run(links, monkeypatch, capsys, *argv: str) -> tuple[int, str]:
    rc = links.main(list(argv))
    return rc, capsys.readouterr().out


class TestChineseNumbering:
    """中文数字序号：整十/十位带个位的解析（无法解析才跳过校验）。"""

    @pytest.mark.parametrize(
        "headings",
        [
            ["九、甲", "十、乙", "十一、丙"],
            ["十、甲", "十一、乙", "十二、丙"],
            ["二十、甲", "二十一、乙"],
        ],
    )
    def test_tens_sequence_continuous_passes(self, links, tmp_path, headings):
        doc = _write(tmp_path, "a.md", "".join(f"## {h}\n" for h in headings))
        assert links.run_checks([doc]) == []

    def test_tens_jump_reported(self, links, tmp_path):
        """十 → 二十 跳变（十一~十九 缺章）检出，证明十位解析非「无法解析跳过」。"""
        doc = _write(tmp_path, "a.md", "## 十、甲\n\n## 二十、乙\n")
        findings = links.run_checks([doc])
        assert [f for f in findings if "中文序号跳变" in f]


class TestUnreadableTargets:
    """不可读文档与死锚点的边界分支。"""

    def test_undecodable_target_with_anchor_is_dead_file(self, links, tmp_path):
        """目标 .md 存在但解码失败（_load 返回 None）→ 按死文件链接报出。"""
        (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00broken")
        doc = _write(tmp_path, "a.md", "# 甲\n\n[坏](bad.md#锚点)\n")
        findings = links.run_checks([doc])
        assert any("死文件链接" in f and "bad.md" in f for f in findings)

    def test_cross_file_dead_anchor_reported(self, links, tmp_path):
        doc = _write(tmp_path, "a.md", "# 甲\n\n[乙](other.md#不存在锚点)\n")
        other = _write(tmp_path, "other.md", "# 另一份\n")
        findings = links.run_checks([doc, other])
        assert any("跨文件死锚点" in f and "other.md" in f for f in findings)

    def test_unreadable_doc_reported_not_fatal(self, links, tmp_path):
        """受检文档不可读 → finding「无法读取文档」，同批其余文档照检。"""
        (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00broken")
        good = _write(tmp_path, "good.md", "# 甲\n\n[缺](nowhere.md)\n")
        findings = links.run_checks([tmp_path / "bad.md", good])
        assert any("无法读取文档" in f for f in findings)
        assert any("死文件链接" in f and "nowhere.md" in f for f in findings)

    def test_section_ref_to_unscanned_file_skipped(self, links, tmp_path):
        """§ 引用归属的文件名不在扫描集内 → 跳过（死文件链接由链接检查覆盖）。"""
        doc = _write(tmp_path, "a.md", "# 甲\n\n说明见 missing.md §3。\n")
        assert links.run_checks([doc]) == []

    def test_section_ref_to_unloadable_file_skipped(self, links, tmp_path):
        """§ 引用目标在扫描集内但不可解码 → 跳过该引用（不连带误报失配）。"""
        (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00broken")
        doc = _write(tmp_path, "a.md", "# 甲\n\n说明见 bad.md §3。\n")
        assert [f for f in links.run_checks([doc, tmp_path / "bad.md"]) if "§" in f] == []


class TestMain:
    """CLI 编排：扫描集注入 + 退出码与缓存契约。"""

    @pytest.fixture
    def targets(self, links, monkeypatch, tmp_path):
        doc = _write(tmp_path, "a.md", "# 甲\n\n见 [乙](b.md)。\n")
        other = _write(tmp_path, "b.md", "# 乙\n")
        monkeypatch.setattr(links, "default_targets", lambda: [doc, other])
        return [doc, other]

    def test_clean_exit_zero(self, links, targets, cache_stub, monkeypatch, capsys):
        rc, out = _run(links, monkeypatch, capsys)
        assert rc == 0
        assert "[OK]" in out
        # 未命中也要写回（通过与发现都缓存）
        assert len(cache_stub.saved) == 1
        assert cache_stub.saved[0]["findings"] == []

    def test_findings_exit_two(self, links, targets, cache_stub, monkeypatch, capsys):
        _write(targets[0].parent, "a.md", "# 甲\n\n[缺](nowhere.md)\n")
        rc, _out = _run(links, monkeypatch, capsys)
        assert rc == 2

    def test_verbose_lists_targets(self, links, targets, cache_stub, monkeypatch, capsys):
        rc, out = _run(links, monkeypatch, capsys, "-v")
        assert rc == 0
        assert "扫描" in out and "b.md" in out

    def test_ci_cache_hit_replays(self, links, targets, cache_stub, monkeypatch, capsys):
        cache_stub.replay = {"findings": []}
        rc, out = _run(links, monkeypatch, capsys, "--ci")
        assert rc == 0
        assert "[OK]" in out
        assert cache_stub.saved == []  # 命中不回写

    def test_ci_cache_miss_saves_and_reports(self, links, targets, cache_stub, monkeypatch, capsys):
        _write(targets[0].parent, "a.md", "# 甲\n\n[缺](nowhere.md)\n")
        rc, out = _run(links, monkeypatch, capsys, "--ci")
        assert rc == 2
        assert "nowhere.md" in out
        assert len(cache_stub.saved) == 1
        assert any("nowhere.md" in f for f in cache_stub.saved[0]["findings"])


class TestMainEntrypoint:
    """`if __name__ == "__main__"` 入口（真实文档集冒烟，退出码经 sys.exit 传递）。"""

    def test_main_guard_exits_with_report_code(self, monkeypatch):
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        monkeypatch.setattr(sys, "argv", ["check-doc-links.py"])
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(SCRIPTS_DIR / "check-doc-links.py"), run_name="__main__")
        assert excinfo.value.code == 0
