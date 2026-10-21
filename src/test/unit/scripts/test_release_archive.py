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

import pytest
from src.test._script_loader import load_script

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
    "## v0.12.5 开发期已修复（2026-10-05）\n\n- **rf-900**：旧条目\n"
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
        assert "并入 v0.12.6 批次" in arch  # 头部涵盖说明追加
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

    def test_move_tree_entry_rejects_unknown_stem(self, rel):
        with pytest.raises(rel.ReleaseError):
            rel.move_tree_entry(_SAMPLE_TREE, "no-such-doc", "0.12")
