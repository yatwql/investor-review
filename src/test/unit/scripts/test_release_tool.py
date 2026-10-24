"""测试：发布流程分步编排脚本 — release.py

覆盖（设备见同目录 `_release_fixtures.py`；门禁/refresh/publish/devbump 编排见
`test_release_tool_gate.py`）：
  - 版本纯函数：开发版→发布版推导、补丁位递增、constants/README 行渲染、异常输入
  - changelog 发布段迁移：指针改写、归档索引区间延展、开发段清空与下一开发段生成、
    正文迁出（尾注不随迁）、版本不一致拒绝、索引缺失拒绝、归档文件追加
  - 预检：分支/工作树/版本形态/tag 条件与发布形态（publish 允许待提交改动）的行为
  - 版本演进：工作区口径统计（分类/行数/用例计数）、表两列写入与增长比、
    比值注释与用例口径注释、缺行拒绝、发布列仅在 --release 写入
  - prepare：文件手术落盘、预检失败中止（不落盘）、内置归档迁移端到端
  - archive 子命令：迁移与收尾守护、dry-run 零写入、开发版拒绝、失败回滚
  - 归档前置：归档文件/目录树缺件在 check 阶段报出
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from src.test._script_loader import load_script
from src.test.unit.scripts._release_fixtures import (
    FakeRunner,
    _EVOLUTION_SAMPLE,
    _ok_runner,
    _sample_changelog,
    _ToolRepoFixture,
    ns,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_tool")


# ─────────────────────────── 版本纯函数 ───────────────────────────


class TestVersionMath:
    def test_release_version_of_accepts_dev(self, rel):
        assert rel.release_version_of("0.12.6-dev") == "0.12.6"

    def test_release_version_of_rejects_release_form(self, rel):
        with pytest.raises(rel.ReleaseError):
            rel.release_version_of("0.12.6")

    def test_next_dev_version_increments_patch(self, rel):
        assert rel.next_dev_version_of("0.12.6") == "0.12.7-dev"
        assert rel.next_dev_version_of("0.12.9") == "0.12.10-dev"

    def test_next_dev_version_rejects_dev_input(self, rel):
        with pytest.raises(rel.ReleaseError):
            rel.next_dev_version_of("0.12.6-dev")

    def test_render_app_version_roundtrip(self, rel):
        text = 'APP_VERSION = "0.12.6-dev"  # 当前版本\nOTHER = "x"\n'
        out = rel.render_app_version(text, "0.12.6")
        assert rel.read_app_version(out) == "0.12.6"
        assert "OTHER" in out

    def test_read_app_version_missing_raises(self, rel):
        with pytest.raises(rel.ReleaseError):
            rel.read_app_version("no version here\n")

    def test_render_readme_version_preserves_suffix(self, rel):
        text = "> 当前版本：0.12.6-dev（[版本历史](docs/managements/changelog.md)）\n"
        out = rel.render_readme_version(text, "0.12.6")
        assert out.startswith("> 当前版本：0.12.6（")
        assert "changelog.md" in out


# ─────────────────────────── changelog 发布段迁移 ───────────────────────────


class TestChangelogRelease:
    def test_pointer_and_next_dev_section_written(self, rel):
        out, _ = rel.apply_changelog_release(_sample_changelog(), "0.12.6", "2026-10-08")
        assert "> **最近发布 [0.12.6]**（2026-10-08）" in out
        assert "## [0.12.7-dev] - 开发中（未发布）" in out
        assert "内容甲" not in out  # 发布段正文迁出主文件

    def test_section_note_kept_in_main(self, rel):
        out, _ = rel.apply_changelog_release(_sample_changelog(), "0.12.6", "2026-10-08")
        assert rel._SECTION_NOTE in out
        assert out.index(rel._SECTION_NOTE) < out.index("## 归档")

    def test_migrated_body_excludes_section_note(self, rel):
        _, body = rel.apply_changelog_release(_sample_changelog(), "0.12.6", "2026-10-08")
        assert "内容甲" in body and "内容乙" in body
        assert rel._SECTION_NOTE not in body

    def test_archive_index_range_extended(self, rel):
        out, _ = rel.apply_changelog_release(_sample_changelog(), "0.12.6", "2026-10-08")
        assert "v0.12.1 ~ v0.12.6（2026-10-03 ~ 2026-10-08）" in out
        assert "v0.11.0 ~ v0.11.12（2026-09-15 ~ 2026-10-03）" in out  # 其余索引不动

    def test_single_version_index_line_becomes_range(self, rel):
        """索引行还是单版本形态（无 `~ v…` 尾巴）时，下一次发布必须区间化。

        回归：`end_v` 只在「已有区间」时才追加，导致首版行永远停在单版本形态
        （连续多次发布都不扩成区间，索引与归档文件头不一致）。
        """
        text = _sample_changelog().replace("— v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）", "— v0.12.5（2026-10-03）")
        out, _ = rel.apply_changelog_release(text, "0.12.6", "2026-10-08")
        assert "v0.12.5 ~ v0.12.6（2026-10-03 ~ 2026-10-08）" in out

    def test_pointer_line_target_path_follows_minor(self, rel):
        """指针行链接的**目标路径**也要随小版本换名（只改文本会继续指向旧档）。

        回归：旧实现只重写反引号里的文件名，`(../archive/v0.12.x/...)` 保持原样——
        文件存在故死链检查不报，人点进去看到的却是上一系列的归档。
        场景：跨小版本发布（开发段与指针所在归档分属不同小版本，索引已含新小版本骨架行）。
        """
        text = (
            "# 变更日志\n\n"
            "> **最近发布 [0.12.5]**（2026-10-07）——已发布版本段随发布移入 "
            "[`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；"
            "本文件只保留当前开发版本段与归档索引。\n\n---\n\n\n"
            "## [0.13.1-dev] - 开发中（未发布）\n\n- **条目一**：内容甲\n\n"
            "（本次发布内容见下方归档索引）\n\n## 归档\n\n"
            "- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)"
            " — v0.13.x（2026-10-08 ~ 2026-10-08）\n"
            "- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)"
            " — v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）\n"
        )
        out, _ = rel.apply_changelog_release(text, "0.13.1", "2026-10-09")
        pointer = next(line for line in out.splitlines() if "最近发布" in line)
        assert "[`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)" in pointer
        assert "../archive/0.13.x/" not in pointer, "指针目标路径不得缺 v 前缀（跨小版本归档目录）"
        assert "../archive/v0.12.x/" not in pointer

    def test_archive_init_placeholder_line_is_accepted(self, rel):
        """`archive-init` 生成的占位索引行（`vX.Y.x`）必须能被首版发布直接改写。

        回归：占位行版本 token 是 `v0.12.x`（不是 `vX.Y.Z`），旧正则只接受
        `v[digits]` 形态 → 新小版本首次发布在 prepare 阶段硬失败（「归档索引行改写失败」），
        必须先手工改索引行才能继续。占位形态语义 = 该 minor 还没有任何正式版本，
        本次发布即首版 → 归一为单版本 + 发布日。
        """
        text = _sample_changelog().replace(
            "— v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）",
            "— v0.12.x（2026-10-01 ~ 2026-10-01）",
        )
        out, _ = rel.apply_changelog_release(text, "0.12.6", "2026-10-08")
        assert "— v0.12.6（2026-10-08）" in out
        # 路径里合法出现 `v0.12.x/`（归档目录名），只看索引行末的版本区间部分
        assert "— v0.12.x" not in out

    def test_same_day_release_keeps_single_date(self, rel):
        """同日多版：日期不重复展开成 `a ~ a`，版本仍区间化。"""
        text = _sample_changelog().replace("— v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）", "— v0.12.1（2026-10-07）")
        out, _ = rel.apply_changelog_release(text, "0.12.6", "2026-10-07")
        assert "v0.12.1 ~ v0.12.6（2026-10-07）" in out

    def test_placeholder_only_section_rejected(self, rel):
        """开发段只剩占位句时发布必须中止。

        判定口径：占位句不是内容——原样归档会得到「只有标题、没有正文」的发布段，
        而归档一旦落盘即无下游断言能发现正文缺失。
        """
        placeholder_only = _sample_changelog().replace("- **条目一**：内容甲 | rf-1\n- **条目二**：内容乙\n\n", "")
        with pytest.raises(rel.ReleaseError, match="没有实际条目"):
            rel.apply_changelog_release(placeholder_only, "0.12.6", "2026-10-08")

    def test_classified_heading_counts_as_entry(self, rel):
        """分类标题 + 条目（Keep a Changelog 形态）视为有内容，不误拦。"""
        text = _sample_changelog().replace(
            "- **条目一**：内容甲 | rf-1\n- **条目二**：内容乙\n",
            "### Changed\n\n- **条目一**：内容甲\n",
        )
        _, body = rel.apply_changelog_release(text, "0.12.6", "2026-10-08")
        assert "### Changed" in body and "内容甲" in body

    def test_version_mismatch_rejected(self, rel):
        with pytest.raises(rel.ReleaseError, match="不一致"):
            rel.apply_changelog_release(_sample_changelog(), "0.12.7", "2026-10-08")

    def test_missing_index_line_rejected(self, rel):
        with pytest.raises(rel.ReleaseError, match="归档索引"):
            rel.apply_changelog_release(_sample_changelog("archived_changelog.0.99.x.md"), "0.12.6", "2026-10-08")

    def test_write_archive_release_appends_and_accumulates(self, rel, tmp_path):
        archive = tmp_path / "archived_changelog.0.12.x.md"
        archive.write_text(
            "# 归档\n\n> 归档时间：2026-10-03（v0.12.1 发布当日并入）\n> 涵盖版本：v0.12.1（2026-10-03）\n> 头部说明\n",
            encoding="utf-8",
        )
        rel.write_archive_release(archive, "0.12.6", "2026-10-08", "- 新条目")
        rel.write_archive_release(archive, "0.12.7", "2026-10-15", "- 次条目")
        text = archive.read_text(encoding="utf-8")
        assert text.count("## [") == 2
        assert text.index("## [0.12.6]") < text.index("## [0.12.7]")
        assert "头部说明" in text
        assert text.endswith("\n") and not text.endswith("\n\n")

    def test_archive_header_span_and_time_derived_from_sections(self, rel, tmp_path):
        """头部两行由归档段列表派生：涵盖版本区间 + 归档时间并入记录（含段数与日期）。"""
        archive = tmp_path / "archived_changelog.0.12.x.md"
        archive.write_text(
            "# 归档\n\n> 归档时间：2026-10-03（首份）\n> 涵盖版本：v0.12.1（2026-10-03）\n",
            encoding="utf-8",
        )
        rel.write_archive_release(archive, "0.12.1", "2026-10-03", "- 甲")
        text = archive.read_text(encoding="utf-8")
        assert "> 涵盖版本：v0.12.1（2026-10-03）" in text
        assert "已并入 1 段：v0.12.1（10-03）" in text

        rel.write_archive_release(archive, "0.12.7", "2026-10-15", "- 乙")
        text = archive.read_text(encoding="utf-8")
        assert "> 涵盖版本：v0.12.1 ~ v0.12.7（2026-10-03 ~ 2026-10-15）" in text
        assert "> 归档时间：2026-10-15（v0.12.7 发布并入；已并入 2 段：v0.12.1（10-03）、v0.12.7（10-15））" in text

    def test_archive_header_untouched_without_header_lines(self, rel, tmp_path):
        """早期归档无这两行（如 v0.1.x）：原样跳过，不补写、不报错。"""
        archive = tmp_path / "archived_changelog.0.1.x.md"
        archive.write_text("# 归档\n\n> 从 changelog 迁移的早期记录。\n", encoding="utf-8")
        rel.write_archive_release(archive, "0.1.9", "2026-07-01", "- 甲")
        text = archive.read_text(encoding="utf-8")
        assert "涵盖版本" not in text and "归档时间" not in text
        assert "## [0.1.9] - 2026-07-01" in text

    def test_archive_header_requires_sections(self, rel, tmp_path):
        """有头部两行却没有任何发布段 → 报错（避免写出无法自证涵盖范围的头）。"""
        archive = tmp_path / "archived_changelog.0.12.x.md"
        archive.write_text("# 归档\n\n> 归档时间：2026-10-03\n> 涵盖版本：v0.12.1\n", encoding="utf-8")
        # 追加本身会带入一个段，故直接对纯函数断言「无段」路径
        with pytest.raises(rel.ReleaseError, match="没有 .*段"):
            rel.render_archive_header("# 归档\n\n> 归档时间：x\n> 涵盖版本：y\n", "0.12.6", "2026-10-08")

    def test_write_archive_release_missing_file_raises(self, rel, tmp_path):
        with pytest.raises(rel.ReleaseError, match="归档文件不存在"):
            rel.write_archive_release(tmp_path / "nope.md", "0.12.6", "2026-10-08", "- x")


# ─────────────────────────── 预检 ───────────────────────────


def _preflight_runner(*, branch="dev", dirty=False, tag_exists=False, version_rc=0, form="-dev"):
    status = " M docs/x.md\n" if dirty else ""
    tag_rc = 0 if tag_exists else 1
    constants_text = f'APP_VERSION = "0.12.6{form}"\n'
    runner = FakeRunner(
        responses=[
            (["git", "branch", "--show-current"], (0, branch + "\n", "")),
            (["git", "status", "--porcelain"], (0, status, "")),
            (["git", "rev-parse"], (tag_rc, "" if tag_exists else "", "")),
            (["scripts/check-version-consistency.py"], (version_rc, "", "")),
        ]
    )
    return runner, constants_text


class TestPreflight:
    def _root(self, tmp_path: Path, constants_text: str) -> Path:
        cdir = tmp_path / "src" / "python" / "core"
        cdir.mkdir(parents=True)
        (cdir / "constants.py").write_text(constants_text, encoding="utf-8")
        return tmp_path

    def test_all_pass_on_clean_dev(self, rel, tmp_path):
        runner, text = _preflight_runner()
        results = rel.run_preflight(self._root(tmp_path, text), expect_release=False, runner=runner)
        assert all(ok for _, ok, _ in results), results
        names = [name for name, _, _ in results]
        assert "工作分支为 dev" in names and "工作树干净" in names

    def test_wrong_branch_fails(self, rel, tmp_path):
        runner, text = _preflight_runner(branch="master")
        results = rel.run_preflight(self._root(tmp_path, text), runner=runner)
        assert [ok for name, ok, _ in results if name == "工作分支为 dev"] == [False]

    def test_dirty_worktree_fails_when_required(self, rel, tmp_path):
        runner, text = _preflight_runner(dirty=True)
        results = rel.run_preflight(self._root(tmp_path, text), runner=runner)
        assert [ok for name, ok, _ in results if name == "工作树干净"] == [False]

    def test_publish_mode_skips_clean_check(self, rel, tmp_path):
        runner, text = _preflight_runner(dirty=True, form="")
        results = rel.run_preflight(self._root(tmp_path, text), expect_release=True, runner=runner, require_clean=False)
        names = [name for name, _, _ in results]
        assert "工作树干净" not in names
        assert all(ok for _, ok, _ in results), results

    def test_release_form_required_for_publish(self, rel, tmp_path):
        runner, text = _preflight_runner(dirty=True)  # 版本仍为 -dev
        results = rel.run_preflight(self._root(tmp_path, text), expect_release=True, runner=runner, require_clean=False)
        assert [ok for name, ok, _ in results if name == "版本为发布形态"] == [False]

    def test_existing_tag_blocks_release(self, rel, tmp_path):
        runner, text = _preflight_runner(form="", tag_exists=True)
        results = rel.run_preflight(self._root(tmp_path, text), expect_release=True, runner=runner, require_clean=False)
        assert [ok for name, ok, _ in results if "tag" in name] == [False]


# ─────────────────────────── 版本演进 ───────────────────────────


class TestEvolutionStats:
    @pytest.fixture
    def repo(self, tmp_path):
        files = {
            "src/python/app.py": "a = 1\nb = 2\n",  # 2 行
            "src/__init__.py": "",  # 空文件：按 1 行计（与 cat-file 口径一致）
            "src/test/test_app.py": "def test_one():\n    assert 1\n\ndef test_two():\n    pass\n",  # 2 用例
            "src/test/helpers.py": "# def test_ 提及应计入 grep 口径\ndef helper():\n    pass\n",
            "scripts/tool.py": "print('x')\n",
            "docs/notes.md": "# 标题\n内容\n",
            "src/static/tmpl/report_template.html": "<html>\n</html>\n",
            "docs/assets/diagram.svg": "<svg/>\n",
            "requirements.txt": "pandas\n",  # 非 md/py/html/svg：只进仓库合计
        }
        for rel_path, content in files.items():
            path = tmp_path / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        return tmp_path

    def test_category_counts(self, rel, repo):
        stats = rel.build_evolution_stats(repo)
        assert stats["main_files"] == 2  # app.py + src/__init__.py
        assert stats["test_files"] == 2
        assert stats["scripts_files"] == 1
        assert stats["tmpl_files"] == 1
        assert stats["svg_files"] == 1
        assert stats["md_files"] == 1

    def test_line_counts_and_repo_totals(self, rel, repo):
        stats = rel.build_evolution_stats(repo)
        assert stats["main_lines"] == 3  # 空 __init__ 1 行 + app 2 行
        assert stats["five_files"] == 2 + 2 + 1 + 1 + 1
        assert stats["repo_files"] == 9
        assert stats["missing"] == 0
        assert stats["repo_lines"] == stats["five_lines"] + stats["md_lines"] + 1  # +requirements.txt

    def test_def_test_line_and_strict_counts(self, rel, repo):
        stats = rel.build_evolution_stats(repo)
        # grep 口径：test_app 2 行 + helpers 注释提及 1 行
        assert stats["def_test_lines"] == 3
        # 严格口径：注释行不算
        assert stats["def_test_strict"] == 2

    def test_line_count_without_trailing_newline(self, rel):
        assert rel._line_count(b"a\nb") == 2
        assert rel._line_count(b"a\nb\n") == 2
        assert rel._line_count(b"") == 1


def _stats(**overrides) -> dict:
    base = {
        "main_files": 400,
        "main_lines": 90_000,
        "test_files": 500,
        "test_lines": 140_000,
        "scripts_files": 58,
        "scripts_lines": 14_100,
        "tmpl_files": 23,
        "tmpl_lines": 4_900,
        "svg_files": 3,
        "svg_lines": 340,
        "md_files": 180,
        "md_lines": 67_000,
        "five_files": 984,
        "five_lines": 249_340,
        "def_test_lines": 8_900,
        "def_test_strict": 8_850,
        "repo_files": 1_200,
        "repo_lines": 330_000,
        "missing": 0,
    }
    base.update(overrides)
    return base


class TestEvolutionTable:
    def test_dev_column_only_when_release_flag_off(self, rel):
        out = rel.update_evolution_table(_EVOLUTION_SAMPLE, _stats(), with_release=False, date="2026-10-09")
        assert "| 335 文件 / 88,669 行 | 400 文件 / 90,000 行 |" in out  # 发布列冻结
        assert "| **901** | **984** |" in out

    def test_release_column_written_with_flag(self, rel):
        out = rel.update_evolution_table(_EVOLUTION_SAMPLE, _stats(), with_release=True, date="2026-10-09")
        assert "| 400 文件 / 90,000 行 | 400 文件 / 90,000 行 |" in out

    def test_growth_ratio_and_specials(self, rel):
        out = rel.update_evolution_table(_EVOLUTION_SAMPLE, _stats(), with_release=False, date="2026-10-09")
        assert "| 12.4×" in out  # 90,000 / 7,258（主程序行）
        assert "| 新增" in out  # 基线 0
        assert "| 1 → 23" in out  # 模板覆盖格式
        assert "2026-10-09）" in out  # 当前开发版列头日期

    def test_bold_cells_preserved(self, rel):
        out = rel.update_evolution_table(_EVOLUTION_SAMPLE, _stats(), with_release=False, date="2026-10-09")
        assert "| **984** |" in out and "| **249,340** |" in out and "| **8,900** |" in out

    def test_missing_row_rejected(self, rel):
        with pytest.raises(rel.ReleaseError, match="缺行"):
            rel.update_evolution_table("| 指标 | x | y | z | w |\n", _stats(), False, "2026-10-09")

    def test_ratio_note_dev_only_updates_workspace_pair(self, rel):
        text = "由 0.84:1 升至 **1.58:1**（140,058 / 88,669，最新发布点），当前工作区为 **1.58:1**（140,058 / 88,669）"
        out = rel.update_ratio_note(text, _stats(), with_release=False)
        assert "升至 **1.58:1**（140,058 / 88,669，最新发布点）" in out  # 发布点不动
        assert "当前工作区为 **1.56:1**（140,000 / 90,000）" in out

    def test_ratio_note_release_updates_both_pairs(self, rel):
        text = "升至 **1.58:1**（140,058 / 88,669，最新发布点），当前工作区为 **1.58:1**（140,058 / 88,669）"
        out = rel.update_ratio_note(text, _stats(), with_release=True)
        assert out.count("1.56:1") == 2
        assert "140,000 / 90,000" in out

    def test_case_note_updates_grep_and_strict(self, rel):
        # 真实排版：短语位于行中（「…提及）：最初 491 → 当前 …」），不得依赖行首锚定
        text = "行数口径（含 `def test_` 提及）：最初 491 → 当前 8,833；按严格口径为 8,792；收集 9,259"
        out = rel.update_case_note(text, _stats())
        assert "提及）：最初 491 → 当前 8,900" in out
        assert "严格口径为 8,850" in out
        assert "9,259" in out  # pytest 收集口径不代写

    def test_case_note_missing_pattern_raises(self, rel):
        with pytest.raises(rel.ReleaseError, match="最初"):
            rel.update_case_note("没有任何口径短语的文本", _stats())
        with pytest.raises(rel.ReleaseError, match="口径为"):
            rel.update_case_note("最初 1 → 当前 2，但缺第二个模式", _stats())

    def test_ratio_note_missing_pattern_raises(self, rel):
        with pytest.raises(rel.ReleaseError, match="当前工作区"):
            rel.update_ratio_note("没有比值短语", _stats(), with_release=False)
        with pytest.raises(rel.ReleaseError, match="最新发布点"):
            rel.update_ratio_note("当前工作区为 **1.58:1**（140,058 / 88,669）", _stats(), with_release=True)

    def test_evolution_table_missing_date_header_raises(self, rel):
        mangled = _EVOLUTION_SAMPLE.replace("· 本次重跑时的工作区 · 2026-10-07", "· 滚动读数")
        with pytest.raises(rel.ReleaseError, match="列头日期"):
            rel.update_evolution_table(mangled, _stats(), False, "2026-10-09")


class TestEvolutionFreshness:
    """演进对照新鲜度断言（gate 前置）：当前开发版列头日期须为今日。"""

    def test_fresh_when_header_date_is_today(self, rel):
        """列头日期 = 当日 → 无 finding。"""
        assert rel.check_evolution_freshness(_EVOLUTION_SAMPLE, "2026-10-07") == []

    def test_stale_date_reported(self, rel):
        """列头日期早于今日 → 报出并给出重跑指引。"""
        findings = rel.check_evolution_freshness(_EVOLUTION_SAMPLE, "2026-10-09")
        assert any("2026-10-07" in f and "2026-10-09" in f and "evolution" in f for f in findings)

    def test_missing_header_pattern_reported(self, rel):
        """列头模式缺失（格式漂移）→ 报出而非静默放行。"""
        mangled = _EVOLUTION_SAMPLE.replace("本次重跑时的工作区", "工作区")
        findings = rel.check_evolution_freshness(mangled, "2026-10-07")
        assert any("列头日期模式缺失" in f for f in findings)


class TestEvolutionCommand:
    def test_command_updates_folders_snapshot(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = FakeRunner(responses=[(["git", "ls-files"], (0, "docs/managements/folders.md\n", ""))])
        rc = rel.cmd_evolution(ns(release=False), runner=runner)
        assert rc == 0
        text = fx.FOLDERS_FILE.read_text(encoding="utf-8")
        import datetime as dt

        today = dt.date.today().isoformat()
        assert f"本次重跑时的工作区 · {today}" in text
        assert "已更新" in capsys.readouterr().out
        # 回归：evolution 改写 folders.md 演进表后必须立即 sync 其统计表，否则后续 publish 的
        # verify（含 doc-drift crosscheck 单测）会因统计过期而红
        assert any(any("check-doc-drift.py" in p for p in c) and any("--sync" in p for p in c) for c in runner.calls)


# ─────────────────────────── prepare / publish / devbump ───────────────────────────


class TestPrepare:
    def test_full_surgery_lands_on_disk(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner()
        rc = rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner)
        assert rc == 0
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.6"
        readme = fx.README_FILE.read_text(encoding="utf-8")
        assert readme.startswith("> 当前版本：0.12.6（")
        changelog = fx.CHANGELOG_FILE.read_text(encoding="utf-8")
        assert "## [0.12.7-dev] - 开发中（未发布）" in changelog
        assert "v0.12.1 ~ v0.12.6（2026-10-03 ~ 2026-10-08）" in changelog
        archived = (fx.root / "docs" / "archive" / "v0.12.x" / "archived_changelog.0.12.x.md").read_text(
            encoding="utf-8"
        )
        assert "## [0.12.6] - 2026-10-08" in archived and "内容甲" in archived
        assert any(any("check-version-consistency.py" in p for p in c) and "--fix" in c for c in runner.calls)
        # 回归：prepare 改写多处文档后必须立即 sync folders.md 统计表，否则后续 refresh 的
        # bench（含 doc-drift crosscheck 单测）会因统计过期而红
        assert any(any("check-doc-drift.py" in p for p in c) and any("--sync" in p for p in c) for c in runner.calls)

    def test_archive_step_runs_inside_prepare(self, rel, tmp_path):
        """归档迁移已固化进 prepare：台账原表搬入归档、主台账留占位、计划完成节搬走、
        已完成设计文件迁档（引用改写 + 目录树搬迁）——过去发布返工的最大来源。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner()
        assert rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner) == 0

        rf_main = fx.RF_FILE.read_text(encoding="utf-8")
        assert "rf-901" not in rf_main
        assert "本版开发期已修复项已随 v0.12.6 发布迁入归档档案" in rf_main
        rf_arch = (fx.root / "docs" / "archive" / "v0.12.x" / "archived_review-findings.0.12.x.md").read_text(
            encoding="utf-8"
        )
        assert "## 开发期已修复（0.12.6-dev）" in rf_arch
        assert "| **rf-901** | 问题甲 | 处理甲 |" in rf_arch  # 原表逐行无损
        assert "（v0.12.1 → v0.12.6）" in rf_arch  # 归档头部涵盖版本延展
        assert "2026-09-01 ~ 2026-10-08" in rf_main  # 归档档案索引区间延展
        assert "## 开发期已修复（0.12.5-dev）" in rf_arch  # 既有批次保留

        plan_main = fx.PLAN_FILE.read_text(encoding="utf-8")
        assert "plan-42" not in plan_main and "plan-77" in plan_main  # 只搬已完成节
        plan_arch = (fx.root / "docs" / "archive" / "v0.12.x" / "archived_plan.0.12.x.md").read_text(encoding="utf-8")
        assert "## plan-42 已完成任务 ✅" in plan_arch and "## plan-43 另一完成项 ✅" in plan_arch

        assert any("mv" in call for call in runner.calls)  # 设计文件经 git mv 迁档
        folders = fx.FOLDERS_FILE.read_text(encoding="utf-8")
        assert "design-done/ #" in folders  # 新目录组出现在归档子树
        assert "design-done.md # 已完成设计" not in folders  # 已从 plan 子树摘除
        assert "design-open.md # 在办设计" in folders  # 在办设计留在 plan 子树

    def test_no_archive_flag_skips_migration(self, rel, tmp_path):
        """--no-archive：台账保持原样（供分批提交/人工迁档场景），gate 仍会兜底拦截。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        rc = rel.cmd_prepare(ns(version=None, date="2026-10-08", no_archive=True), runner=_ok_runner())
        assert rc == 0
        assert "rf-901" in fx.RF_FILE.read_text(encoding="utf-8")
        assert "plan-42" in fx.PLAN_FILE.read_text(encoding="utf-8")

    def test_preflight_failure_leaves_files_untouched(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner([(["git", "branch", "--show-current"], (0, "master\n", ""))])
        rc = rel.cmd_prepare(ns(version=None, date=None), runner=runner)
        assert rc == 2
        assert "0.12.6-dev" in fx.CONSTANTS_FILE.read_text(encoding="utf-8")
        assert "内容甲" in fx.CHANGELOG_FILE.read_text(encoding="utf-8")


class TestArchivePrerequisites:
    """`check` 阶段提前暴露归档前置缺件（别等 prepare 改完版本全链才撞上）。"""

    def test_ready_train_reports_nothing(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        assert rel.archive_prerequisites("0.12.6") == []
        assert fx.FOLDERS_FILE.exists()

    def test_missing_archive_files_reported(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        (fx.root / "docs" / "archive" / "v0.12.x" / "archived_plan.0.12.x.md").unlink()
        findings = rel.archive_prerequisites("0.12.6")
        assert findings and any("archived_plan.0.12.x.md" in f for f in findings)

    def test_missing_tree_block_reported(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.FOLDERS_FILE.write_text(
            "\n".join(ln for ln in fx.FOLDERS_FILE.read_text(encoding="utf-8").splitlines() if "v0.12.x/" not in ln),
            encoding="utf-8",
        )
        findings = rel.archive_prerequisites("0.12.6")
        assert findings and any("目录树缺 `v0.12.x/`" in f for f in findings)

    def test_check_blocks_on_prerequisite_gap(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        (fx.root / "docs" / "archive" / "v0.12.x" / "archived_review-findings.0.12.x.md").unlink()
        assert rel.cmd_check(ns(), runner=_ok_runner()) == 2
        assert "归档前置未就绪" in capsys.readouterr().out


class TestCliSurface:
    def test_parser_and_handler_tables_agree(self, rel):
        parser = rel.build_parser()
        sub_actions = [a for a in parser._subparsers._group_actions if hasattr(a, "choices")]
        parser_cmds = set(sub_actions[0].choices) if sub_actions else set()
        # 处理表由模块内的 `cmd_*` 函数集合派生（不写死命令清单：新增子命令时只改实现）
        # `cmd_archive_init` ↔ 子命令 `archive-init`（下划线→连字符）
        handlers = {name[4:].replace("_", "-") for name in dir(rel) if name.startswith("cmd_")}
        assert parser_cmds == handlers  # 两张内部表双向一致（结构断言，不写死条数）
        assert all(hasattr(rel, f"cmd_{name.replace(chr(45), chr(95))}") for name in handlers)

    def test_cli_assembly_lives_in_internal_package(self, rel):
        """argparse 装配与分派下沉 _release/_cli（入口只 re-export，防 release.py 再逼近红线）。"""
        assert rel.build_parser.__module__ == "_release._cli"
        assert rel.run_cli.__module__ == "_release._cli"


# ─────────────────────────── archive 子命令 ───────────────────────────


class TestArchiveCommand:
    def test_archive_command_migrates_and_reports(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner()
        rc = rel.cmd_archive(ns(date="2026-10-08"), runner=runner)
        assert rc == 0
        out = capsys.readouterr().out
        assert "review-findings" in out and "人工复核" in out
        assert "本版开发期已修复项已随 v0.12.6 发布" in fx.RF_FILE.read_text(encoding="utf-8")
        # 收尾跑了 doc-drift --sync + 两台便宜守护（文档痕迹 / 死链），把文档面问题留在本地而非 gate
        assert any(any("check-doc-drift.py" in p for p in c) and "--sync" in c for c in runner.calls)
        assert any(any("check-doc-traces.py" in p for p in c) for c in runner.calls)
        assert any(any("check-doc-links.py" in p for p in c) for c in runner.calls)
        assert "plan-42" not in fx.PLAN_FILE.read_text(encoding="utf-8")

    def test_dry_run_writes_nothing(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        before = (fx.RF_FILE.read_text(encoding="utf-8"), fx.PLAN_FILE.read_text(encoding="utf-8"))
        assert rel.cmd_archive(ns(date="2026-10-08", dry_run=True), runner=_ok_runner()) == 0
        assert (fx.RF_FILE.read_text(encoding="utf-8"), fx.PLAN_FILE.read_text(encoding="utf-8")) == before
        assert (
            not (fx.root / "docs" / "archive" / "v0.12.x" / "archived_plan.0.12.x.md")
            .read_text(encoding="utf-8")
            .count("plan-42")
        )

    def test_missing_tree_block_aborts_before_ledger_writes(self, rel, tmp_path):
        """目录树缺该小版本归档块 → 中止且台账原样（先算后写：不留半迁移）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        # 去掉目录树里的 v0.12.x 归档块（模拟新小版本首份归档尚未补树）
        tree_wo_block = "\n".join(
            line for line in fx.FOLDERS_FILE.read_text(encoding="utf-8").splitlines() if "v0.12.x/" not in line
        )
        fx.FOLDERS_FILE.write_text(tree_wo_block + "\n", encoding="utf-8")
        before = (fx.RF_FILE.read_text(encoding="utf-8"), fx.PLAN_FILE.read_text(encoding="utf-8"))
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=_ok_runner()) == 2
        assert (fx.RF_FILE.read_text(encoding="utf-8"), fx.PLAN_FILE.read_text(encoding="utf-8")) == before

    def test_git_mv_failure_rolls_back_tree(self, rel, tmp_path):
        """git mv 失败 → 目录树回滚到搬迁前（不指向未移动的位置），台账也保持原样。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        tree_before = fx.FOLDERS_FILE.read_text(encoding="utf-8")
        runner = _ok_runner([(["git", "mv"], (128, "", "fatal: 无法移动"))])
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=runner) != 0
        assert fx.FOLDERS_FILE.read_text(encoding="utf-8") == tree_before
        assert "rf-901" in fx.RF_FILE.read_text(encoding="utf-8")

    def test_stale_archive_reference_is_reported(self, rel, tmp_path, capsys):
        """历史归档残留指向被迁设计文件的旧路径 → 只提示不改写（历史快照原则）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        hist = fx.root / "docs" / "archive" / "v0.11.x"
        hist.mkdir(parents=True)
        (hist / "archived_changelog.0.11.x.md").write_text(
            "见 [`plan/design-done.md`](../plan/design-done.md)", encoding="utf-8"
        )
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=_ok_runner()) == 0
        out = capsys.readouterr().out
        assert "历史归档仍按快照保留旧路径引用" in out
        assert "v0.11.x/archived_changelog.0.11.x.md" in out
        # 历史快照未被改写
        assert "plan/design-done.md" in (hist / "archived_changelog.0.11.x.md").read_text(encoding="utf-8")

    def test_dev_version_refused(self, rel, tmp_path):
        """开发版上跑归档会被拒（版本全链须先切到发布形态，否则归档目录推导不出）。"""
        _ToolRepoFixture(rel, tmp_path)
        assert rel.cmd_archive(ns(date=None), runner=_ok_runner()) == 2


class TestChangelogPointerLinkFollowsArchive:
    """指针行的归档文件名须与目标版本、日期三者同步改写（跨系列时换名）。"""

    def test_link_rewritten_to_target_archive(self, rel):
        """指针链接指向「上一系列」时，发布后必须改指本次目标归档（跨小版本换名）。"""
        sample = _sample_changelog().replace(
            "已发布版本段随发布移入 [`archived_changelog.0.12.x.md`]",
            "已发布版本段随发布移入 [`archived_changelog.0.11.x.md`]",
        )
        out, _ = rel.apply_changelog_release(sample, "0.12.6", "2026-10-08")
        pointer = next(ln for ln in out.splitlines() if ln.startswith("> **最近发布"))
        assert "[`archived_changelog.0.12.x.md`]" in pointer
        assert "archived_changelog.0.11.x.md" not in pointer

    def test_pointer_link_format_violation_rejected(self, rel):
        broken = _sample_changelog().replace("已发布版本段随发布移入", "已发布版本段见")
        with pytest.raises(rel.ReleaseError, match="指针行"):
            rel.apply_changelog_release(broken, "0.12.6", "2026-10-08")


class TestChangelogErrorMessagesCarryFormat:
    """发布跑挂在格式不符时，报错须自带「期望格式样例 + 下一步」——不翻代码也能改对。

    回归背景：`prepare` 的 changelog 归一步有四类格式失败（缺开发段 / 缺归档章节 /
    缺指针行 / 索引行改写失败），原本只报「格式与预期不符」，人得去读正则猜写法。
    """

    def test_missing_dev_section_shows_expected_heading(self, rel):
        with pytest.raises(rel.ReleaseError) as exc:
            rel.apply_changelog_release("# 变更日志\n\n## 归档\n", "0.12.6", "2026-10-08")
        msg = str(exc.value)
        assert "期望：## [X.Y.Z-dev] - 开发中（未发布）" in msg
        assert "archive-init" in msg

    def test_missing_pointer_shows_expected_line(self, rel):
        text = _sample_changelog().replace("> **最近发布 [0.12.5]**", "> 最近发布 [0.12.5]")
        with pytest.raises(rel.ReleaseError) as exc:
            rel.apply_changelog_release(text, "0.12.6", "2026-10-08")
        msg = str(exc.value)
        assert "期望：> **最近发布 [X.Y.Z]**" in msg
        assert "archived_changelog.X.Y.x.md" in msg
        assert "archive-init" in msg

    def test_index_line_mismatch_shows_expected_line(self, rel):
        text = (
            "# 变更日志\n\n"
            "> **最近发布 [0.12.5]**（2026-10-07）——已发布版本段随发布移入 "
            "[`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；"
            "本文件只保留当前开发版本段与归档索引。\n\n"
            "## [0.12.6-dev] - 开发中（未发布）\n\n- 条目\n\n"
            "## 归档\n\n"
            "- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — 格式不符\n"
        )
        with pytest.raises(rel.ReleaseError) as exc:
            rel.apply_changelog_release(text, "0.12.6", "2026-10-08")
        msg = str(exc.value)
        assert "期望：- [`archived_changelog.X.Y.x.md`]" in msg
        assert "vX.Y.Z（YYYY-MM-DD）" in msg
        assert "archive-init" in msg


class TestReleasedSectionEntries:
    """归档发布段非空判据（gate 侧兜底）：分类标题或条目行才算内容。"""

    def test_section_with_entries_passes(self, rel):
        text = (
            "## [0.13.11] - 2026-10-20\n\n### Fixed\n\n- **条目**：内容\n\n"
            "## [0.13.12] - 2026-10-21\n\n- **目标条目**：内容\n"
        )
        assert rel.release_section_has_entries(text, "0.13.12") is True

    def test_title_only_section_rejected(self, rel):
        text = "## [0.13.12] - 2026-10-21\n\n## [0.13.11] - 2026-10-20\n\n- **旧条目**：内容\n"
        assert rel.release_section_has_entries(text, "0.13.12") is False

    def test_placeholder_sentence_rejected(self, rel):
        text = "## [0.13.12] - 2026-10-21\n\n（本次发布内容见下方归档索引）\n"
        assert rel.release_section_has_entries(text, "0.13.12") is False

    def test_absent_version_rejected(self, rel):
        text = "## [0.13.11] - 2026-10-20\n\n- **条目**：内容\n"
        assert rel.release_section_has_entries(text, "0.13.12") is False
