"""测试：发布台账归档纯函数 — `_release/_ledger_archive.py`

覆盖（判定与搬运口径，落盘编排见 test_release_tool.py）：
  - review-findings 已解决表**原表搬运**：表头/数据行逐字节无损、占位生成、幂等、
    归档头部「涵盖版本」延展与主文件归档索引区间延展、缺节拒绝
  - 门禁口径：`pending_rf_rows` 搬空即 0、`has_archive_section` 只认本版批次
  - plan 已完成节：仅标题带完成标记者搬迁、在办节不外溢、批次头追加、幂等
  - docs/plan 完成判定三分支：引用编号均已归档 / 仍有开放引用 / 无任何引用
  - 路径引用改写计数与目录树条目搬迁（含连接符重排、未知条目拒绝）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from src.test._script_loader import load_script

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ARCHIVE_ROOT = _REPO_ROOT / "docs" / "archive"

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]

_SAMPLE_RF = (
    "# 自审记录\n\n## 已解决问题\n\n"
    "### 开发期已修复（0.12.6-dev）\n\n"
    "| # | 问题 | 处理 |\n|---|------|------|\n"
    "| **rf-901** | 问题甲 | 处理甲 |\n"
    "| **rf-902** | 问题乙 | 处理乙 |\n\n"
    "### 归档档案\n\n"
    "- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md)"
    " — v0.12.x 开发期已修复批次（2026-09-01 ~ 2026-10-05）\n"
)

_SAMPLE_RF_ARCHIVE = (
    "# 自审记录归档 — v0.12.x\n\n"
    "> 归档时间：2026-10-05（v0.12.5 发布）\n"
    "> 涵盖版本：v0.12.x 开发期已修复项（v0.12.1 → v0.12.5）\n\n---\n\n"
    "## 开发期已修复（0.12.5-dev）\n\n> 完整复盘见 `changelog.md` 0.12.5-dev 段；此处仅摘要行。\n\n"
    "- rf-900 已修复（2026-10-05）：旧条目\n"
)

_SAMPLE_PLAN = (
    "# 计划\n\n"
    "## plan-77 在办任务\n\n- [ ] 待做\n\n"
    "## plan-42 已完成任务 ✅\n\n**完成（2026-09-20，v0.12.3）**：已做\n\n"
    "## plan-43 另一完成项 ✅\n\n**完成（2026-09-25，v0.12.4）**：已做\n"
)

_SAMPLE_TREE = """
````
├── docs/
│   ├── archive/
│   │   └── v0.12.x/                          # 版本归档
│   │       ├── archived_changelog.0.12.x.md # 变更日志归档
│   │       └── tui-runtime/                  # 某设计归档
│   │           └── tui-runtime.md # 设计
│   ├── managements/
│   │   └── plan.md # 计划
│   └── plan/                                 # 中间设计文件（在办）
│       ├── design-done.md # 已完成设计
│       └── design-open.md # 在办设计
└── README.md
````
"""


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_tool_archive")


# ─────────────────────────── 台账归档纯函数 ───────────────────────────


class TestLedgerArchive:
    def test_rf_table_extracted_verbatim(self, rel):
        text = _SAMPLE_RF
        body = text[text.index("### 开发期已修复（0.12.6-dev）") :]
        table = rel.extract_rf_table(body)
        assert table is not None
        assert table.splitlines()[0].startswith("| # | 问题 | 处理 |")
        rows = [line for line in table.splitlines() if line.startswith("| **rf-")]  # 数据行逐行原样
        assert rows == ["| **rf-901** | 问题甲 | 处理甲 |", "| **rf-902** | 问题乙 | 处理乙 |"]
        assert rel.count_rf_rows(body) == len(rows)  # 结构关系，不写死条数

    def test_placeholder_body_yields_no_table(self, rel):
        """已迁档（只剩占位）时不再有表 → 计数 0，重复归档不会二次搬运。"""
        body = "\n\n（本版开发期已修复项已随 v0.12.5 发布迁入上方归档档案）\n"
        assert rel.extract_rf_table(body) is None
        assert rel.count_rf_rows(body) == 0

    def test_apply_rf_archive_is_idempotent(self, rel):
        main, arch, moved = rel.apply_rf_archive(_SAMPLE_RF, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert moved == 2
        again_main, again_arch, moved_again = rel.apply_rf_archive(main, arch, "0.12.6", "2026-10-08")
        assert moved_again == 0
        assert again_main == main and again_arch == arch  # 幂等：二次运行零改动

    def test_apply_rf_archive_noops_without_section(self, rel):
        """本版无「开发期已修复」节（无自审条目）时不得报错中断发布——原样返回。"""
        main, arch, moved = rel.apply_rf_archive("# 空台账\n", _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert moved == 0
        assert main == "# 空台账\n" and arch == _SAMPLE_RF_ARCHIVE

    def test_archive_status_three_states(self, rel):
        assert rel.rf_archive_status("# 空台账\n", "0.12.6")[0] == "absent"
        assert rel.rf_archive_status(_SAMPLE_RF, "0.12.6")[0] == "pending"
        main, _arch, _n = rel.apply_rf_archive(_SAMPLE_RF, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert rel.rf_archive_status(main, "0.12.6")[0] == "archived"

    def test_table_block_moved_verbatim_with_separator(self, rel):
        """表块逐行原样搬（含原分隔行），非 rf 起头的行也在块内不被落下。"""
        body = "\n\n| # | 问题 | 处理 |\n|:--|:--|:--|\n| **rf-901** | 甲 | 处理甲 |\n| — | 汇总行 | 未分类 |\n"
        table = rel.extract_rf_table(body)
        assert table is not None
        assert "|:--|:--|:--|" in table  # 原分隔行（非脚本合成的 `|---|`）
        assert "| — | 汇总行 | 未分类 |" in table  # 非 rf 行随块搬运
        assert rel.count_rf_rows(body) == 1  # 计数只认 rf 标识行

    def test_section_prose_preserved_in_main(self, rel):
        """表外散文（说明/备注）不随表迁走，留在主台账。"""
        main = _SAMPLE_RF.replace(
            "### 开发期已修复（0.12.6-dev）\n\n",
            "### 开发期已修复（0.12.6-dev）\n\n> 备注：本节按批次处理。\n\n",
        )
        new_main, _arch, moved = rel.apply_rf_archive(main, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert moved == 2
        assert "> 备注：本节按批次处理。" in new_main
        assert "rf-901" not in new_main

    def test_archive_heading_follows_existing_convention(self, rel):
        """批次标题/说明行随既有归档格式（`## 开发期已修复（X-dev）` + changelog 指路）。"""
        _main, arch, _n = rel.apply_rf_archive(_SAMPLE_RF, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert "## 开发期已修复（0.12.6-dev）" in arch
        assert "> 完整复盘见 `changelog.md` 0.12.6-dev 段" in arch


class TestPlaceholderCollapse:
    """迁档占位节只保留本版，更早批次占位随迁档收敛（防单行同构节累积）。"""

    @staticmethod
    def _ledger(*versions: str) -> str:
        sections = [
            f"### 开发期已修复（{v}-dev）\n\n（本版开发期已修复项已随 v{v} 发布迁入上方归档档案）\n" for v in versions
        ]
        return "# 台账\n\n## 已解决问题\n\n" + "\n".join(sections) + "\n### 归档档案\n- 索引行\n"

    def test_only_latest_placeholder_survives(self, rel):
        text = self._ledger("1.0.1", "1.0.2", "1.0.3")
        out = rel._collapse_superseded_placeholders(text, keep_version="1.0.3")

        assert out.count("发布迁入上方归档档案") == 1
        assert "### 开发期已修复（1.0.3-dev）" in out
        for older in ("1.0.1", "1.0.2"):
            assert f"（{older}-dev）" not in out  # 更早批次节头随空占位节一并删除
        assert "### 归档档案" in out  # 归档索引不受影响

    def test_section_with_prose_keeps_heading(self, rel):
        """节内还有表外散文时只摘占位行，节与散文均保留（不丢人工备注）。"""
        text = (
            "# 台账\n\n## 已解决问题\n\n"
            "### 开发期已修复（1.0.1-dev）\n\n> 人工备注：本节已人工复核\n\n"
            "（本版开发期已修复项已随 v1.0.1 发布迁入上方归档档案）\n\n"
            "### 开发期已修复（1.0.2-dev）\n\n"
            "（本版开发期已修复项已随 v1.0.2 发布迁入上方归档档案）\n"
        )
        out = rel._collapse_superseded_placeholders(text, keep_version="1.0.2")

        assert "### 开发期已修复（1.0.1-dev）" in out
        assert "> 人工备注：本节已人工复核" in out
        assert "v1.0.1 发布迁入" not in out
        assert "v1.0.2 发布迁入" in out

    def test_single_placeholder_is_noop(self, rel):
        text = self._ledger("1.0.1")
        assert rel._collapse_superseded_placeholders(text, keep_version="1.0.1") == text

    def test_apply_rf_archive_collapses_previous_release(self, rel):
        """接线：迁档后更早批次的占位节被收敛（只留本次版本）。"""
        main = _SAMPLE_RF.replace(
            "### 开发期已修复（0.12.6-dev）",
            "### 开发期已修复（0.12.5-dev）\n\n（本版开发期已修复项已随 v0.12.5 发布迁入上方归档档案）\n\n"
            "### 开发期已修复（0.12.6-dev）",
        )
        new_main, _arch, moved = rel.apply_rf_archive(main, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")

        assert moved == 2
        assert len(re.findall(r"（本版开发期已修复项已随[^）]*）", new_main)) == 1
        assert "（0.12.5-dev）" not in new_main
        assert "（0.12.6-dev）" in new_main
        assert "本批发布日 2026-10-08" in _arch
        assert "v0.12.6）" in _arch  # 涵盖版本区间尾
        assert "；2026-10-08 v0.12.6 本批原表搬运" in _arch  # 归档时间追加（既有叙述保留）
        assert "v0.12.5 发布" in _arch  # 既有历史叙述未被改写

    def test_pending_rows_and_archive_section_detection(self, rel):
        assert rel.pending_rf_rows(_SAMPLE_RF, "0.12.6") == 2
        main, arch, _ = rel.apply_rf_archive(_SAMPLE_RF, _SAMPLE_RF_ARCHIVE, "0.12.6", "2026-10-08")
        assert rel.pending_rf_rows(main, "0.12.6") == 0  # 门禁断言口径：搬空即通过
        assert rel.has_archive_section(arch, "0.12.6") is True
        assert rel.has_archive_section(arch, "0.12.7") is False

    def test_apply_plan_archive_moves_only_completed(self, rel):
        main, arch, n = rel.apply_plan_archive(
            _SAMPLE_PLAN, "> 涵盖版本：v0.12.x（v0.12.1 → v0.12.5）\n", "0.12.6", "2026-10-08"
        )
        assert n == 2
        assert "plan-77 在办任务" in main and "plan-42" not in main
        assert "## plan-42 已完成任务 ✅" in arch and "## plan-43 另一完成项 ✅" in arch
        assert "v0.12.6）" in arch  # 头部涵盖版本区间尾延展
        assert rel.apply_plan_archive(main, arch, "0.12.6", "2026-10-08")[2] == 0  # 幂等

    def test_plan_completed_sections_need_marker(self, rel):
        """标题不带完成标记的在办节不得被判为已完成（判定不外溢）。"""
        heads = [head for _s, _e, head in rel.plan_completed_sections(_SAMPLE_PLAN)]
        assert all("✅" in head for head in heads)
        assert not any("plan-77" in head for head in heads)

    def test_design_doc_candidates_only_strong_signal(self, rel):
        """候选只认「引用编号均已归档」；仍有开放引用者留原处，无引用者不自动判定。"""
        docs = {
            "done.md": "依据 plan-42 落地",
            "open.md": "依据 plan-77 展开",
            "bare.md": "没有引用任何任务编号",
        }
        got = dict(rel.design_doc_candidates(docs, {"plan-77"}))
        assert set(got) == {"done.md"}
        assert "plan-42" in got["done.md"]
        assert rel.unreferenced_docs(docs) == ["bare.md"]  # 仅提示，不进候选
        assert rel.design_doc_candidates(docs, {"plan-77", "plan-42"}) == []  # 引用仍开放即不搬

    def test_archive_header_findings_report_missing_lines(self, rel):
        """头部缺行会让区间/日期无法派生——报 finding 而非静默放行。"""
        assert rel.archive_header_findings(_SAMPLE_RF_ARCHIVE) == []
        bare = "# 归档\n\n## 开发期已修复（0.12.5-dev）\n"
        findings = rel.archive_header_findings(bare)
        assert len(findings) == 2
        assert any("涵盖版本" in f for f in findings) and any("归档时间" in f for f in findings)

    def test_rewrite_doc_refs_counts_replacements(self, rel):
        text = "见 `docs/plan/a.md` 与 [a](../plan/a.md)，另 `docs/plan/b.md`"
        new, n = rel.rewrite_doc_refs(text, "docs/plan/a.md", "docs/archive/v0.12.x/a/a.md")
        assert n == 1 and "docs/archive/v0.12.x/a/a.md" in new and "docs/plan/b.md" in new
        assert rel.rewrite_doc_refs(text, "docs/plan/zzz.md", "x") == (text, 0)  # 无引用不改写

    def test_move_tree_entry_relocates_group(self, rel):
        moved = rel.move_tree_entry(_SAMPLE_TREE, "design-done", "0.12")
        assert "design-done.md # 已完成设计" not in moved.split("│   └── plan/")[1]  # 已离开 plan 子树
        assert "design-done/ #" in moved
        assert "design-open.md # 在办设计" in moved  # 在办项不动
        assert moved.count("└──") >= _SAMPLE_TREE.count("└──")  # 新目录组保留末项连接符

    def test_move_tree_entry_comment_survives_refs_rewrite(self, rel):
        """新插目录树注释不带文件路径——否则随后的引用改写会把注释改指到归档路径（实测缺陷）。"""
        moved = rel.move_tree_entry(_SAMPLE_TREE, "design-done", "0.12")
        new_lines = [ln for ln in moved.splitlines() if "design-done" in ln]
        assert new_lines
        for line in new_lines:
            assert "docs/plan/design-done.md" not in line, line  # 不含可被改写命中的路径
        # 模拟引用改写：注释行不受影响（无命中）
        rewritten, hits = rel.rewrite_doc_refs(moved, "docs/plan/design-done.md", "docs/archive/v0.12.x/x.md")
        assert hits == 0 and rewritten == moved

    def test_stale_reference_files_lists_archive_hits(self, rel, tmp_path):
        """历史归档里仍指向旧路径的文件被列出（按设计不改写历史快照，只提示）。"""
        archive = tmp_path / "docs" / "archive" / "v0.12.x"
        archive.mkdir(parents=True)
        (archive / "old.md").write_text("见 [设计](../../plan/design-done.md)", encoding="utf-8")
        (archive / "other.md").write_text("无关内容", encoding="utf-8")
        found = rel.stale_reference_files(tmp_path / "docs" / "archive", "plan/design-done.md")
        assert found == ["docs/archive/v0.12.x/old.md"]
        assert rel.stale_reference_files(tmp_path / "nope", "plan/design-done.md") == []

    def test_move_tree_entry_rejects_unknown_stem(self, rel):
        with pytest.raises(rel.ReleaseError):
            rel.move_tree_entry(_SAMPLE_TREE, "no-such-doc", "0.12")


# ─────────────── 真实仓库契约：脚本格式必须与磁盘上的既有归档一致 ───────────────
class TestRealArchiveContract:
    """脚本产出的格式「尺子」须量得住真实归档——否则自动迁移会与既有归档两套并存。

    这些用例直接读仓库内真实文件（只读，不改动），把「脚本自说自话」的假绿风险钉住：
    格式常量一旦与既有归档漂移，这里先红，而不是等下次发布产出半套格式。
    """

    @pytest.fixture
    def real(self, rel):
        """读真实台账与归档（只读）；只取**最新 train**做格式契约——更早的归档是冻结快照。"""

        def _newest(pattern: str) -> tuple[str, str]:
            files = sorted(_ARCHIVE_ROOT.glob(pattern))
            assert files, f"仓库内应有已安装归档：{pattern}"

            def _key(path: Path) -> tuple[int, ...]:
                nums = re.search(r"\.(\d+)\.(\d+)\.x\.md$", path.name)
                return tuple(int(n) for n in nums.groups()) if nums else (0, 0)

            newest = max(files, key=_key)
            return newest.name, newest.read_text(encoding="utf-8")

        return {
            "rf_main": (_REPO_ROOT / "docs" / "managements" / "review-findings.md").read_text(encoding="utf-8"),
            "plan_main": (_REPO_ROOT / "docs" / "managements" / "plan.md").read_text(encoding="utf-8"),
            "rf_archive": _newest("v*/archived_review-findings.*.md"),
            "plan_archive": _newest("v*/archived_plan.*.md"),
            "rel": rel,
        }

    def test_batch_heading_matches_real_archives(self, real):
        """真实归档的批次标题全部是脚本产出的那一种形态（`## 开发期已修复（X-dev）`）。"""
        rel = real["rel"]
        name, text = real["rf_archive"]
        fmt_pattern = re.escape(rel._RF_ARCHIVE_HEAD_FMT).replace(r"\{version\}", r"\d+\.\d+\.\d+")
        headings = [line for line in text.splitlines() if line.startswith("## 开发期已修复")]
        assert headings, f"{name} 应含批次标题"
        for heading in headings:
            assert re.fullmatch(fmt_pattern, heading), f"{name}: {heading}"

    def test_placeholder_template_matches_real_ledger(self, real):
        """主台账若存在占位句，必须与脚本模板同形（不引入第二种写法）。

        新开发周期台账**允许没有占位**（`devbump` 会清掉上一版的占位）——
        因此这里断言的是「有则同形」，而非「必须有」。
        """
        rel = real["rel"]
        pattern = re.escape(rel.RF_PLACEHOLDER).replace(r"\{version\}", r"\d+\.\d+\.\d+")
        found = re.findall(r"（本版开发期已修复项已随[^）]*）", real["rf_main"])
        for line in found:
            assert re.fullmatch(pattern, line), f"真实台账占位句与模板不同形：{line}"

    def test_active_archive_headers_parseable(self, real):
        """脚本会写入的两份归档头部两行齐备（区间/日期派生有落点）。"""
        rel = real["rel"]
        for name, text in (real["rf_archive"], real["plan_archive"]):
            assert rel.archive_header_findings(text) == [], name

    def test_real_index_entry_extends_to_new_date(self, real):
        """主台账「归档档案」索引行被区间模式识别，且延展真落到最新 train 那一条。"""
        rel = real["rel"]
        name, _ = real["rf_archive"]
        assert rel._INDEX_RANGE_RE.search(real["rf_main"]), "索引行格式与区间模式不符"
        bumped = rel._bump_index_range(real["rf_main"], "2099-01-01")
        line = next(ln for ln in bumped.splitlines() if name in ln)
        assert line.endswith("2099-01-01）"), line

    def test_real_rf_sections_are_migrated_or_absent(self, real):
        """主台账各批次节只能是「本版待迁」或「已迁档」；空台账（新周期首日）合法。

        注意：新开发周期开张时「已解决问题」区可以**没有任何批次节**（`devbump` 会清掉
        上一版占位），所以这里不能断言「至少有一节」——那是随周期变化的仓库状态，
        不是脚本契约。契约只约束「存在的每一节」：当前开发版之外只允许已迁档/缺失。
        """
        rel = real["rel"]
        versions = re.findall(r"^### 开发期已修复（(\d+\.\d+\.\d+)-dev）", real["rf_main"], re.M)
        if not versions:
            return  # 新周期台账为空：合法状态，无批次节可校验

        def _key(v: str) -> tuple[int, ...]:
            return tuple(int(n) for n in v.split("."))

        current = max(versions, key=_key)
        states = {v: rel.rf_archive_status(real["rf_main"], v)[0] for v in versions}
        # 当前开发版批次：待迁（有表格）或已迁（只有占位）都合法
        assert states.pop(current) in {"pending", "archived"}, current
        # 更早批次：只允许已迁档（发布后不得残留待迁表格）
        assert set(states.values()) <= {"archived", "absent"}, states

    def test_real_plan_headings_roundtrip(self, real):
        """真实计划归档的完成节标题能被脚本的完成判定识别（反向：判定尺子有效）。"""
        rel = real["rel"]
        name, text = real["plan_archive"]
        headings = [line for line in text.splitlines() if line.startswith("## ") and "plan-" in line]
        done = [h for h in headings if "✅" in h]
        assert done, f"{name} 应含带完成标记的任务节"
        for heading in done:
            matched = rel.plan_completed_sections(heading + "\n\n正文\n")
            assert matched, heading


class TestPlaceholderLifecycle:
    """切开发版即清空迁档占位（上一版提示属过期信息）+ 文案不带方向词。"""

    @staticmethod
    def _ledger(*versions: str) -> str:
        sections = [
            f"### 开发期已修复（{v}-dev）\n\n（本版开发期已修复项已随 v{v} 发布迁入归档档案）\n" for v in versions
        ]
        return "# 台账\n\n## 已解决问题\n\n" + "\n".join(sections) + "\n### 归档档案\n- 索引行\n"

    def test_placeholder_has_no_direction_word(self, rel):
        """占位文案不写「上方/下方」——版面变化不该让提示失准。"""
        text = rel.RF_PLACEHOLDER.format(version="1.2.3")
        assert "归档档案" in text
        assert "上方" not in text and "下方" not in text

    def test_drop_clears_every_placeholder_section(self, rel):
        out = rel.drop_migration_placeholders(self._ledger("1.0.1", "1.0.2"))
        assert "发布迁入归档档案" not in out
        for version in ("1.0.1", "1.0.2"):
            assert f"（{version}-dev）" not in out  # 空占位节的节头一并删除
        assert "### 归档档案" in out  # 归档索引不受影响

    def test_drop_keeps_prose_sections(self, rel):
        text = (
            "# 台账\n\n## 已解决问题\n\n### 开发期已修复（1.0.1-dev）\n\n"
            "> 人工备注：本版已人工复核\n\n"
            "（本版开发期已修复项已随 v1.0.1 发布迁入归档档案）\n\n### 归档档案\n- 索引行\n"
        )
        out = rel.drop_migration_placeholders(text)
        assert "> 人工备注：本版已人工复核" in out
        assert "发布迁入归档档案" not in out


class TestPlanArchiveHeadingLevels:
    """plan 已完成节可能嵌在 `### P1~P4` 分组下（`####`）——须同样被搬入并扁平为 `##`。

    否则台账里的完成项永远搬不走（清单只认二级时，`####` 节在主台账积压）。
    """

    _LEDGER = (
        "# 计划\n\n### P1 — 当前待办\n\n"
        "#### `plan-201` 某已完成任务 ✅\n\n**完成（2026-10-21）**：已做\n\n"
        "#### `plan-202` 在办任务\n\n- [ ] 待做\n"
    )

    def test_nested_completed_section_detected(self, rel):
        sections = rel.plan_completed_sections(self._LEDGER)
        assert len(sections) == 1
        assert "plan-201" in sections[0][2]

    def test_moved_and_flattened_to_level_two(self, rel):
        main, archive, moved = rel.apply_plan_archive(self._LEDGER, "> 涵盖版本：v0.14.x\n", "0.14.0", "2026-10-21")
        assert moved == 1
        assert "plan-201" not in main  # 已搬离主台账
        assert "plan-202" in main  # 在办节不外溢
        assert "## `plan-201` 某已完成任务 ✅" in archive  # 入档统一降为二级
        assert "#### `plan-201`" not in archive


class TestReleaseTokenAccounting:
    """发布台账 token 采集与统计：会话 JSONL 累计用量 → 台账字段 → 发布窗口增量。

    口径（与 pi 的 session token 统计一致）：assistant 消息、非消息 usage（如
    cache_warm）、compaction 摘要三类条目都计入会话累计；窗口用量以「上一次
    devbump」为界，跨会话（agent 重启、累计归零）按正增量分段累加。
    """

    @staticmethod
    def _session_file(tmp_path, entries):
        import json

        path = tmp_path / "session.jsonl"
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
        return path

    def test_sums_three_entry_kinds(self, rel, tmp_path):
        path = self._session_file(
            tmp_path,
            [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input": 100,
                            "output": 20,
                            "cacheRead": 300,
                            "cacheWrite": 10,
                            "totalTokens": 420,
                            "cost": {"total": 0.05},
                        },
                    },
                },
                {"type": "message", "message": {"role": "user"}},  # 用户消息无 usage，跳过
                {
                    "type": "usage",
                    "kind": "cache_warm",
                    "usage": {"input": 0, "output": 0, "cacheRead": 50, "totalTokens": 50, "cost": {"total": 0.001}},
                },
                {"type": "compaction", "usage": {"input": 5, "output": 5, "totalTokens": 10, "cost": {"total": 0.002}}},
            ],
        )
        usage = rel.session_usage(path)
        assert usage["input"] == 105 and usage["output"] == 25
        assert usage["cache_read"] == 350 and usage["cache_write"] == 10
        assert usage["total"] == 480
        assert abs(usage["cost"] - 0.053) < 1e-9

    def test_missing_file_and_bad_lines_are_tolerated(self, rel, tmp_path):
        assert rel.session_usage(None) == {}
        assert rel.session_usage(tmp_path / "nope.jsonl") == {}
        bad = tmp_path / "bad.jsonl"
        bad.write_text("{not json}\n\n[1,2]\n", encoding="utf-8")
        assert rel.session_usage(bad) == {}  # 无可解析用量 → 空（调用方据此省略字段）

    def test_record_carries_cumulative_usage(self, rel):
        usage = {"input": 1, "output": 2, "cache_read": 3, "cache_write": 4, "total": 10, "cost": 0.01}
        record = rel.build_record(command="gate", elapsed_s=1.0, ok=True, version="1.0.0", session_usage=usage)
        assert record["session_usage"] == usage
        bare = rel.build_record(command="gate", elapsed_s=1.0, ok=True, version="1.0.0")
        assert "session_usage" not in bare  # 非 agent 环境下省略，保持旧台账形状

    def test_window_usage_uses_last_devbump_as_boundary(self, rel):
        rows = [
            {"command": "devbump", "session_usage": {"input": 100, "output": 10, "total": 110, "cost": 0.1}},
            {"command": "check", "session_usage": {"input": 300, "output": 50, "total": 350, "cost": 0.5}},
            {"command": "publish", "session_usage": {"input": 600, "output": 90, "total": 690, "cost": 0.9}},
        ]
        used = rel.release_token_usage(rows)
        assert used["input"] == 500 and used["output"] == 80
        assert used["total"] == 580
        assert abs(used["cost"] - 0.8) < 1e-9

    def test_window_usage_handles_session_reset(self, rel):
        """agent 重启后累计归零：按正增量分段累加，不出现负数。"""
        rows = [
            {"command": "devbump", "session_usage": {"input": 100, "output": 10, "total": 110, "cost": 0.1}},
            {"command": "check", "session_usage": {"input": 40, "output": 5, "total": 45, "cost": 0.04}},
            {"command": "publish", "session_usage": {"input": 70, "output": 9, "total": 79, "cost": 0.07}},
        ]
        used = rel.release_token_usage(rows)
        assert used["input"] == 70 and used["total"] == 79

    def test_no_window_after_latest_devbump(self, rel):
        rows = [{"command": "devbump", "session_usage": {"total": 10}}]
        assert rel.release_token_usage(rows) == {}
        assert rel.format_tokens({}) == ""


class TestReleaseAgentIdentity:
    """发布台账记录执行环境身份（provider / model / thinking / session）。

    回答「这版是哪个模型、什么思考档发的」——跨模型对比发布成本与质量时需要它；
    非 agent 环境（CI / 手动 shell）变量缺失时字段整体省略，台账形状不变。
    """

    def test_identity_from_env(self, rel):
        env = {
            "PI_PROVIDER": "deepseek",
            "PI_MODEL": "deepseek-flash",
            "PI_REASONING_LEVEL": "high",
            "PI_SESSION_ID": "abc-123",
        }
        assert rel.agent_identity(env) == {
            "provider": "deepseek",
            "model": "deepseek-flash",
            "thinking": "high",
            "session_id": "abc-123",
        }

    def test_identity_absent_in_non_agent_env(self, rel):
        assert rel.agent_identity({}) == {}
        # 空白值同样视为缺失（不写空串进台账）
        assert rel.agent_identity({"PI_MODEL": "   "}) == {}

    def test_record_carries_agent_and_omits_when_absent(self, rel):
        agent = {"provider": "p", "model": "m", "thinking": "low", "session_id": "s"}
        record = rel.build_record(command="gate", elapsed_s=1.0, ok=True, version="1.0.0", agent=agent)
        assert record["agent"] == agent
        assert "agent" not in rel.build_record(command="gate", elapsed_s=1.0, ok=True, version="1.0.0")

    def test_format_agent_label(self, rel):
        assert rel.format_agent({"provider": "deepseek", "model": "deepseek-flash", "thinking": "high"}) == (
            "deepseek/deepseek-flash（thinking=high）"
        )
        assert rel.format_agent({"model": "m"}) == "m"  # 无 provider/thinking 时的退化形态
        assert rel.format_agent({}) == ""


class TestCurrentIterationRecompute:
    """归档后「当前迭代」概述行自动重算（在办项数 + P1~P4 分档编号）。

    回归背景：归档搬走已完成节后该行必然过期（实测每版都写「在办 15 项…已实施待归档」），
    且 doc-drift 不校验这句——按**现存任务节**重算，口径自愈。
    """

    _PLAN = (
        "# 计划\n\n"
        "**当前迭代**：在办 9 项——P1 9 项（**plan-1/2/3/128**）。\n\n"
        "---\n\n"
        "### P1 — 当前待办（立即执行）\n\n"
        "#### `plan-1` 甲任务 ✅\n\n- 已完成\n\n"
        "#### `plan-2` 乙任务\n\n- 在做\n\n"
        "### P2 — 下一阶段就绪\n\n"
        "#### `plan-3` 丙任务\n\n- 在做\n\n"
        "#### `plan-4` 丁任务 ✅\n\n- 已完成\n\n"
        "### P3 — 预期实施\n\n"
        "### P4 — 实验候选\n\n"
        "#### `plan-5` 戊任务\n\n- 在做\n"
    )

    def test_recomputed_after_archive(self, rel):
        main, _arch, n = rel.apply_plan_archive(self._PLAN, "> 涵盖版本：v1.0.x\n", "1.0.1", "2026-10-21")
        assert n == 2
        line = next(ln for ln in main.splitlines() if ln.startswith("**当前迭代**"))
        assert line == "**当前迭代**：在办 3 项——P1 1 项（**plan-2**）、P2 1 项（**plan-3**）、P4 1 项（**plan-5**）。"

    def test_done_marked_sections_not_counted(self, rel):
        """已完成待归档（标题带 ✅）不计入「在办」——归档前后同一口径。"""
        line = next(
            ln for ln in rel.recompute_current_iteration(self._PLAN).splitlines() if ln.startswith("**当前迭代**")
        )
        # 样例共 5 节，其中两节已标 ✅ → 在办 3
        assert "在办 3 项" in line
        assert "plan-1/2" not in line and "plan-1、" not in line

    def test_phantom_id_in_summary_dropped(self, rel):
        """概述里残留的已归档/不存在编号随重算消失。"""
        line = next(
            ln for ln in rel.recompute_current_iteration(self._PLAN).splitlines() if ln.startswith("**当前迭代**")
        )
        assert "plan-128" not in line
        assert "在办 3 项" in line  # 5 节中 2 节已标 ✅

    def test_no_items_left(self, rel):
        text = "**当前迭代**：在办 2 项——P1 2 项（**plan-1/2**）。\n\n### P1 — 当前待办\n\n### P2 — 下一阶段就绪\n"
        line = next(ln for ln in rel.recompute_current_iteration(text).splitlines() if ln.startswith("**当前迭代**"))
        assert line == "**当前迭代**：当前无在办任务（新任务取 `plan-next` 编号登记）。"

    def test_flat_plan_without_tiers_untouched(self, rel):
        """无 `### P1~P4` 分层时不动该行（保守：无法判档就不猜）。"""
        text = "**当前迭代**：在办 1 项（plan-9）。\n\n## plan-9 在做\n"
        assert rel.recompute_current_iteration(text) == text


class TestEmptyBatchSectionAfterDevbump:
    """devbump 后「已解决问题」区不得残留指向已归档版本的空节（回归）。

    背景：迁档时批次节内的标准说明行（`> 完整复盘见 changelog.md X-dev 段…`）属散文，
    占位行被摘掉后该节只剩这一行说明——`devbump` 之后主台账仍在已解决区顶部
    显示一个空节，误导读者以为本周期还有已修复项待看。
    """

    _LEFTOVER = (
        "# 台账\n\n## 已解决问题\n\n"
        "### 开发期已修复（1.0.1-dev）\n\n"
        "> 完整复盘见 `changelog.md` 1.0.1-dev 段；此处为台账原表（发布时随 `release.py prepare` 迁入版本归档）。\n\n"
        "### 归档档案\n- 索引行\n"
    )

    def test_empty_batch_section_dropped_on_devbump(self, rel):
        """只剩标准说明行的批次节 → 整节删除（说明已随归档记录）。"""
        out = rel.drop_migration_placeholders(self._LEFTOVER)
        assert "### 开发期已修复（1.0.1-dev）" not in out
        assert "完整复盘见" not in out
        assert "### 归档档案" in out

    def test_human_remark_keeps_section(self, rel):
        """非模板散文（人工备注）仍保留节头——收敛不得静默丢备注。"""
        text = self._LEFTOVER.replace(
            "> 完整复盘见",
            "> 人工备注：本批已复核\n\n> 完整复盘见",
        )
        out = rel.drop_migration_placeholders(text)
        assert "> 人工备注：本批已复核" in out
        assert "完整复盘见" not in out
