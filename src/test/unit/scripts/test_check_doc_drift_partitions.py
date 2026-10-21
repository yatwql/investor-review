"""test_check_doc_drift 兄弟分片（partitions）：台账分区纪律 / 归档索引 / 迁档占位 机检。"""
# ruff: noqa: F811 — 夹具以参数名注入（与模块级同名导入非重定义）

from __future__ import annotations
import pytest

# 夹具按名注入（由测试签名消费），代码里无引用

from src.test.unit.scripts.test_check_doc_drift import (
    drift,  # noqa: F401
    drift_parts,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestArchiveIndex:
    """归档索引完整性：管理文档须列全 ``docs/archive/`` 下对应归档文件。

    历史缺口：changelog 的 `## 归档` 索引曾因「发布切换时整段重写已发布段」被一并删除，
    当时无任何断言拦住；本类即该缺口的回归守卫。
    """

    def test_passes_on_real_repo(self, drift):
        """真实仓库：当前三份管理文档的归档索引与磁盘双向一致。"""
        assert drift.check_archive_index() == []

    def test_detects_real_repo_violation(self, drift, tmp_path, monkeypatch, drift_parts):
        """回归：索引被删时能报出（不依赖 `_scan_docs`——changelog 属历史记录类被其排除）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        broken = tmp_path / "changelog.md"
        broken.write_text(
            doc.read_text(encoding="utf-8").replace("archived_changelog.0.10.x.md", "（已删）"), encoding="utf-8"
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((broken, "archived_changelog."),))
        findings = drift.check_archive_index()
        assert any("archived_changelog.0.10.x.md" in f and "缺少" in f for f in findings)

    def test_reports_missing_index_entry(self, drift, tmp_path, monkeypatch, drift_parts):
        """索引缺失某归档文件 → 报 finding（正向）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        broken = tmp_path / "changelog.md"
        broken.write_text(
            doc.read_text(encoding="utf-8").replace("archived_changelog.0.10.x.md", "（已删）"), encoding="utf-8"
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((broken, "archived_changelog."),))
        assert any("缺少" in f for f in drift.check_archive_index())

    def test_reports_ghost_index_entry(self, drift, tmp_path, monkeypatch, drift_parts):
        """索引引用了不存在的归档文件 → 报 finding（反向）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        ghost = tmp_path / "changelog.md"
        ghost.write_text(
            doc.read_text(encoding="utf-8") + "\n[x](docs/archive/v9.9.x/archived_changelog.9.9.x.md)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((ghost, "archived_changelog."),))
        assert any("archived_changelog.9.9.x.md" in f and "不存在" in f for f in drift.check_archive_index())

    def test_covers_three_management_docs(self, drift):
        """三份带归档的管理文档均在被检面内（changelog / plan / review-findings）。"""
        names = {p.name for p, _ in drift._ARCHIVE_INDEX_PAIRS}
        assert names == {"changelog.md", "plan.md", "review-findings.md"}


class TestManagementPartitions:
    """管理文档分区纪律：未完成/已解决/已归档不得错置（含历史失误的可检特征）。"""

    _CHANGELOG_OK = "## [0.11.3-dev] - 开发中（未发布）\n"

    def test_passes_on_real_repo(self, drift):
        """真实仓库：三份管理文档分区纪律无违规。"""
        assert drift.check_management_partitions() == []

    def test_pending_item_in_resolved_section(self, drift):
        """未完成项被误置已解决区（无 changelog 修复记录）→ 报 finding。"""
        rf = (
            "## 当前待处理问题\n\n### P2C\n\n| # | 问题 |\n| **rf-999** | x |\n\n"
            "## 已解决问题\n\n| # | 问题 |\n| **rf-999** | y |\n\n### 归档档案\n"
        )
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert any("分区互斥" in f for f in findings)
        assert any("无修复记录" in f for f in findings)

    def test_resolved_item_without_changelog_record(self, drift):
        """仅已解决区一条、但 changelog 无记录 → 报 finding（对应「未完成项误置已解决区」类失误）。"""
        rf = "## 已解决问题\n\n| # | 问题 |\n| **rf-998** | y |\n\n### 归档档案\n"
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert any("rf-998" in f and "无修复记录" in f for f in findings)

    def test_resolved_item_backed_by_archived_changelog(self, drift):
        """修复记录在归档 changelog 中亦算有记录（不误报）。"""
        rf = "## 已解决问题\n\n| # | 问题 |\n| **rf-997** | y |\n\n### 归档档案\n"
        findings = drift.audit_management_partitions(
            review_findings=rf,
            plan="",
            changelog=self._CHANGELOG_OK,
            archived_changelogs=["### 修复 rf-997\n"],
        )
        assert findings == []

    def test_fixed_section_inside_pending_area(self, drift):
        """「开发期已修复」节落在待处理区 → 报 finding（已修复项被读成待办）。"""
        rf = (
            "## 当前待处理问题\n\n### P1 — 高优先\n\n| # | 问题 |\n"
            "### 开发期已修复（1.2.3-dev）\n\n| # | 问题 |\n| **rf-996** | y |\n\n"
            "## 已解决问题\n\n### 归档档案\n"
        )
        findings = drift.audit_management_partitions(
            review_findings=rf, plan="", changelog=self._CHANGELOG_OK + "\n修复 rf-996\n"
        )
        assert any("开发期已修复" in f and "节归属错置" in f for f in findings)

    def test_pending_tier_heading_inside_resolved_area(self, drift):
        """P 档标题（P1/P2/P3）落在已解决区 → 报 finding。"""
        rf = (
            "## 当前待处理问题\n\n### P1 — 高优先\n\n## 已解决问题\n\n"
            "### 开发期已修复（1.2.3-dev）\n\n| # | 问题 |\n\n"
            "### P3 — 持续监控：文件膨胀登记\n\n| # | 文件 |\n\n### 归档档案\n"
        )
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert any("P3" in f and "节归属错置" in f for f in findings)

    def test_correct_section_layout_passes(self, drift):
        """待处理区只放 P 档、已解决区只放已修复节 → 无节归属 finding（不误报）。"""
        rf = (
            "## 当前待处理问题\n\n### P1 — 高优先\n\n| # | 问题 |\n| **rf-995** | x |\n\n"
            "## 已解决问题\n\n### 开发期已修复（1.2.3-dev）\n\n| # | 问题 |\n\n### 归档档案\n"
        )
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert [f for f in findings if "节归属错置" in f] == []

    def test_completed_plan_left_in_todo(self, drift):
        """未完成区出现 ✅ 已完成项 → 报 finding。"""
        plan = "## 当前迭代待办\n\n#### ✅ `plan-9` 已做完\n\n## 归档\n"
        findings = drift.audit_management_partitions(review_findings="", plan=plan, changelog=self._CHANGELOG_OK)
        assert any("plan-9" in f and "已完成项须移入归档" in f for f in findings)

    def test_archived_plan_still_in_todo(self, drift):
        """已归档项仍在未完成区 → 报 finding（分区互斥）。"""
        plan = "## 当前迭代待办\n\n#### 🔲 `plan-9` 待做\n\n## 归档\n"
        findings = drift.audit_management_partitions(
            review_findings="",
            plan=plan,
            changelog=self._CHANGELOG_OK,
            archived_plans=["#### ✅ `plan-9` 已完成\n"],
        )
        assert any("分区互斥" in f for f in findings)

    def test_archive_prose_mention_is_not_archived_item(self, drift):
        """归档文件正文里的提及不算已归档项（防误报：如「后续项：某某计划项 …」）。"""
        plan = "## 当前迭代待办\n\n#### 🔲 `plan-49` 待做\n\n## 归档\n"
        findings = drift.audit_management_partitions(
            review_findings="",
            plan=plan,
            changelog=self._CHANGELOG_OK,
            archived_plans=["**后续项（另行登记）**：`plan-47`、`plan-49` 转正评估。\n"],
        )
        assert findings == []

    def test_released_section_still_in_live_changelog(self, drift):
        """现行 changelog 段头非开发版本 → 报 finding（已发布段须归归档）。"""
        findings = drift.audit_management_partitions(
            review_findings="", plan="", changelog="## [0.11.2] - 2026-09-24\n"
        )
        assert any("非开发版本" in f for f in findings)

    def test_multiple_version_headers_in_live_changelog(self, drift):
        """现行 changelog 含多个版本段头 → 报 finding。"""
        findings = drift.audit_management_partitions(
            review_findings="", plan="", changelog="## [0.11.3-dev] - x\n\n## [0.11.2] - 2026-09-24\n"
        )
        assert any("个版本段头" in f for f in findings)

    def test_missing_files_do_not_crash(self, drift):
        """空文本（文件缺失）不抛异常，也不臆造 finding。"""
        assert drift.audit_management_partitions(review_findings="", plan="", changelog="") == []


class TestMigrationPlaceholders:
    """迁档占位↔归档节：占位声明与归档文件对应版本二级标题节的一致性。"""

    def test_real_repo_passes(self, drift):
        """真实仓库当前占位与归档节一致（结构关系断言，不写死版本清单）。"""
        assert drift.check_migration_placeholders() == []

    def test_no_placeholder_no_findings(self, drift, tmp_path):
        """台账无占位 → 无 finding（占位是断言的触发前提）。"""
        assert drift.check_migration_placeholders("无占位文本", archive_root=tmp_path) == []

    def test_reports_placeholder_without_version_section(self, drift, tmp_path):
        """占位存在但归档文件缺该版本二级标题节 → 报出（占位已写、归档正文缺失）。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## 开发期已修复（9.8-dev）\n\n内容\n", encoding="utf-8"
        )
        findings = drift.check_migration_placeholders(
            "（本版开发期已修复项已随 v9.9.9 发布迁入上方归档档案）", archive_root=tmp_path
        )
        assert any("v9.9.9" in f and "无对应版本归档节" in f for f in findings)

    def test_accepts_version_section(self, drift, tmp_path):
        """归档节标题含该版本（v 前缀式）→ 通过。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## v9.9.9 开发期已修复（2026-10-20）\n\n- **rf-x**：条目\n", encoding="utf-8"
        )
        assert drift.check_migration_placeholders("已随 v9.9.9 发布迁入", archive_root=tmp_path) == []

    def test_accepts_legacy_dev_heading(self, drift, tmp_path):
        """旧式节标题（`## 开发期已修复（X.Y.Z-dev）`）同样视为该版本归档节。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## 开发期已修复（9.9.9-dev）\n\n内容\n", encoding="utf-8"
        )
        assert drift.check_migration_placeholders("已随 v9.9.9 发布迁入", archive_root=tmp_path) == []

    def test_reports_missing_archive_file(self, drift, tmp_path):
        """占位存在但对应归档文件不存在 → 报出。"""
        findings = drift.check_migration_placeholders("已随 v8.8.8 发布迁入", archive_root=tmp_path)
        assert any("archived_review-findings.8.8.x.md" in f and "不存在" in f for f in findings)

    def test_duplicate_placeholders_single_finding(self, drift, tmp_path):
        """同一版本多处占位只断言一次（去重后单条 finding）。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        findings = drift.check_migration_placeholders(
            "已随 v9.9.9 发布迁入\n已随 v9.9.9 发布迁入", archive_root=tmp_path
        )
        assert len(findings) == 1
