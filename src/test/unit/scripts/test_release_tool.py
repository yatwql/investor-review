"""测试：发布流程分步编排脚本 — release.py

覆盖：
  - 版本纯函数：开发版→发布版推导、补丁位递增、constants/README 行渲染、异常输入
  - changelog 发布段迁移：指针改写、归档索引区间延展、开发段清空与下一开发段生成、
    正文迁出（尾注不随迁）、版本不一致拒绝、索引缺失拒绝、归档文件追加
  - 预检：分支/工作树/版本形态/tag 条件与发布形态（publish 允许待提交改动）的行为
  - 版本演进：工作区口径统计（分类/行数/用例计数）、表两列写入与增长比、
    比值注释与用例口径注释、缺行拒绝、发布列仅在 --release 写入
  - 门禁：守护清单与 scripts/ 实体同源且互异、regression 先行、失败即停、
    最坏退出码传递
  - refresh：三步顺序执行、首步失败即停
  - publish：提交→verify→合并→tag 顺序与合并信息含 verify 项数、verify 失败中止、
    已提交时跳过、--push 才执行推送
  - prepare / devbump：文件手术落盘与预检失败中止（不落盘）
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest
from src.test._script_loader import load_script

_REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_tool")


def ns(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class FakeRunner:
    """脚本化子进程替身：按「命令片段全部出现」匹配应答，记录全部调用。"""

    def __init__(self, responses=None, default=(0, "", "")):
        self.responses = list(responses or [])
        self.default = default
        self.calls: list[list[str]] = []

    def run(self, cmd, root, capture=True):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        for matcher, resp in self.responses:
            if all(m in cmd for m in matcher):
                return resp
        return self.default


def _mode_arg(cmd: list[str]) -> str:
    """取命令中 `--mode` 的取值（无则空串）——bench 范围断言用。"""
    return cmd[cmd.index("--mode") + 1] if "--mode" in cmd else ""


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


def _sample_changelog(archive_name: str = "archived_changelog.0.12.x.md") -> str:
    return (
        "# 变更日志\n\n"
        "> **最近发布 [0.12.5]**（2026-10-07）——已发布版本段随发布移入 "
        f"[`{archive_name}`](../archive/v0.12.x/{archive_name})；本文件只保留当前开发版本段与归档索引。\n\n"
        "---\n\n\n"
        "## [0.12.6-dev] - 开发中（未发布）\n\n"
        "- **条目一**：内容甲 | rf-1\n"
        "- **条目二**：内容乙\n\n"
        "（本次发布内容见下方归档索引）\n\n"
        "## 归档\n\n"
        f"- [`{archive_name}`](../archive/v0.12.x/{archive_name}) — v0.12.1 ~ v0.12.5"
        "（2026-10-03 ~ 2026-10-07）\n"
        "- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md)"
        " — v0.11.0 ~ v0.11.12（2026-09-15 ~ 2026-10-03）\n"
    )


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


_EVOLUTION_SAMPLE = (
    "| 指标 | 最初版本（首个提交 · 2026-06-27） | 最新发布（最近发布 tag v0.12.5 · 2026-10-07）"
    " | 当前开发版（0.12.6-dev · 本次重跑时的工作区 · 2026-10-07） | 增长（最初 → 当前） |\n"
    "| 主程序（`src/**/*.py`，不含测试） | 30 文件 / 7,258 行 | 335 文件 / 88,669 行"
    " | 335 文件 / 88,669 行 | 12.2×\n"
    "| 测试（`src/test/**/*.py`） | 13 文件 / 6,108 行 | 484 文件 / 140,058 行"
    " | 484 文件 / 140,058 行 | 22.9×\n"
    "| 辅助脚本（`scripts/*.py`） | 0（当时仅 `launch.sh` / `launch.ps1`） | 57 文件 / 13,990 行"
    " | 57 文件 / 13,990 行 | 新增\n"
    "| HTML 报告模板（`src/static/tmpl/*.html`） | 0（当时为 `src/tmpl/`：1 个 / 469 行）"
    " | 22 文件 / 4,874 行 | 22 文件 / 4,874 行 | 1 → 22\n"
    "| 架构图示（SVG） | 0 | 3 文件 / 337 行 | 3 文件 / 337 行 | 新增\n"
    "| 文档（`.md`） | 7 文件 / 1,355 行 | 176 文件 / 66,469 行 | 176 文件 / 66,469 行 | 49.1×\n"
    "| **代码文件合计**（前 5 项） | **43** | **901** | **901** | 21.0×\n"
    "| **代码行合计**（前 5 项） | **13,366** | **247,928** | **247,928** | 18.5×\n"
    "| **测试用例数**（`def test_` 行数口径） | **491** | **8,833** | **8,833** | 18.0×\n"
    "| 仓库文件总数 | 56 | 1,126 | 1,126 | 20.1×\n"
    "| 仓库总行数（全部跟踪文件） | 15,600 | 322,464 | 322,464 | 20.7×\n"
    '> - **测试用例数**采 `git grep -c "def test_"` 的**行数口径**（含注释/文档串中的 `def test_` 提及）：'
    "最初 491 → 当前 8,833；按更严格的「以 `def test_` 开头的定义行（含类方法缩进）」口径为 8,792；"
    "按 pytest 实际收集（含参数化展开）为 **9,259** 项（另 20 项 opt-in live 反选，全量 9,279）。\n"
    "> - **测试 / 主程序行数比**由 0.84:1（6,108 / 7,258）升至 **1.58:1**（140,058 / 88,669，最新发布点），"
    "当前工作区为 **1.58:1**（140,058 / 88,669）。\n"
)


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


# ─────────────────────────── 门禁 ───────────────────────────


class TestGate:
    @pytest.fixture(autouse=True)
    def _fresh_evolution(self, rel, monkeypatch):
        """门禁编排用例不读真实 folders.md 新鲜度：新鲜度断言依赖「列头日期 =
        运行当日」（墙钟 + 仓库文件状态），用例在不同时区/日期的 CI 上会因
        本地未重跑 evolution 而随机红——编排用例将其视为通过，新鲜度拦截
        行为由 TestEvolutionFreshness（纯函数）与 test_gate_stops_on_stale_
        evolution（门禁中止）单独覆盖。"""
        monkeypatch.setattr(rel, "check_evolution_freshness", lambda *_a, **_k: [])

    def test_gate_workers_converge_with_cpu(self, rel, monkeypatch):
        """并行度随核数收敛：弱机器降路、4 核+ 封顶、缺核信息取封顶、单核不下 1 路。"""
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 2)
        assert rel._gate_workers() == 2
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 8)
        assert rel._gate_workers() == 4
        monkeypatch.setattr(rel.os, "cpu_count", lambda: None)
        assert rel._gate_workers() == 4
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 1)
        assert rel._gate_workers() == 1

    def test_guard_scripts_exist_and_unique(self, rel):
        assert len(rel.GUARD_SCRIPTS) == len(set(rel.GUARD_SCRIPTS))
        for script in rel.GUARD_SCRIPTS:
            path = _REPO_ROOT / script
            assert path.is_file(), script
            assert script.startswith("scripts/check-"), script

    def test_gate_records_step_timings(self, rel):
        """门禁三步（回归 / 十守护 / 设计护栏）入计时器：发布耗时台账靠它们归因。"""
        rel._reset_timer()
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        labels = [entry["step"] for entry in rel._timer().steps]
        assert labels == ["P2 场景回归", "P2 十守护", "P2 设计护栏"]
        assert all(entry["elapsed_s"] >= 0 for entry in rel._timer().steps)

    def test_gate_stops_on_stale_evolution(self, rel):
        """演进对照新鲜度过期 → gate 返回 2 且不触发任何子进程（前置拦截）。"""
        stale = ["当前开发版列头 2026-10-20 ≠ 今日，先执行 scripts/release.py evolution 刷新"]
        rel.check_evolution_freshness = lambda *_a, **_k: list(stale)
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 2
        assert runner.calls == []  # 新鲜度失败即中止，回归/守护一个不跑

    def test_gate_runs_regression_then_guards(self, rel):
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        first = runner.calls[0]
        assert "test-runner" in first[1]
        assert "--mode" in first and "regression" in first
        guard_calls = [
            c
            for c in runner.calls
            if any("check-" in part for part in c) and not any("style-guardrails" in part for part in c)
        ]
        assert len(guard_calls) == len(rel.GUARD_SCRIPTS)
        assert all("--ci" in c for c in guard_calls)

    def test_gate_runs_style_guardrail(self, rel):
        """发布门禁包含设计护栏（E 级拦 / W 级观察统计；不并入十守护清单）。"""
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        guardrail_calls = [c for c in runner.calls if any("style-guardrails" in part for part in c)]
        assert len(guardrail_calls) == 1
        assert "--ci" in guardrail_calls[0]
        # 护栏在十守护之后执行（守护清单语义独立）
        guard_idx = max(i for i, c in enumerate(runner.calls) if any("check-doc-links" in part for part in c))
        assert runner.calls.index(guardrail_calls[0]) > guard_idx

    def test_gate_stops_on_style_guardrail_failure(self, rel):
        """设计护栏 E 级 finding → gate 非零退出并中止。"""
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            (["scripts/check-style-guardrails.py"], (2, "强调色越权", "")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2

    def test_gate_stops_on_regression_failure(self, rel):
        runner = FakeRunner(responses=[(["scripts/test-runner.py"], (1, "", "boom"))])
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 1
        assert len(runner.calls) == 1  # 回归失败 → 十守护一个不跑

    def test_gate_returns_worst_guard_code(self, rel):
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            ([rel.GUARD_SCRIPTS[3]], (2, "finding: x", "")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2


# ─────────────────────────── refresh / evolution 命令 ───────────────────────────


class TestRefresh:
    """refresh 条件化：自上一 release tag 起仅文档变更 → 跳过 bench/collect
    （doc-drift --sync 恒跑）；有程序/测试变更或 --force-refresh → 三步全跑。"""

    _TAG = (["describe"], (0, "v0.13.9", ""))
    _PROGRAM_CHANGE = (["diff", "--name-only"], (0, "src/python/x.py\n", ""))
    _DOCS_ONLY = (["diff", "--name-only"], (0, "README.md\ndocs/plan/y.md\n", ""))

    def test_three_steps_in_order_when_program_changed(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._PROGRAM_CHANGE])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[3:]  # 前 3 个调用：describe / diff / ls-files
        assert len(steps) == 3
        assert "--update-docs" in steps[0]
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("collect-test-coverage" in p for p in steps[1])
        assert any("check-doc-drift" in p for p in steps[2])

    def test_docs_only_skips_bench_and_collect(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._DOCS_ONLY])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[3:]
        assert len(steps) == 1  # 仅 sync
        assert any("check-doc-drift" in p for p in steps[0])

    def test_force_refresh_runs_all_steps(self, rel):
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True), runner=runner)
        assert rc == 0
        assert len(runner.calls) == 3  # 无 git 判定，直接三步
        assert "--update-docs" in runner.calls[0]
        assert _mode_arg(runner.calls[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("collect-test-coverage" in p for p in runner.calls[1])

    def test_missing_tag_conservatively_refreshes(self, rel):
        runner = FakeRunner(responses=[(["describe"], (128, "", "no tag here"))])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[1:]
        assert len(steps) == 3  # 无 tag → 保守全刷
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)

    def test_untracked_program_file_triggers_refresh(self, rel):
        """未跟踪程序文件（git diff 不含）也计入变更 → 必跑。"""
        runner = FakeRunner(
            responses=[
                self._TAG,
                (["diff", "--name-only"], (0, "README.md\n", "")),
                (["ls-files", "--others"], (0, "src/python/new_mod.py\n", "")),
            ]
        )
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[3:]
        assert len(steps) == 3
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)

    def test_full_bench_flag_runs_all_modes(self, rel):
        """`--full-bench` 走 bench 别名（全量 14 档）——重测全表耗时的手动入口。"""
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True, full_bench=True), runner=runner)
        assert rc == 0
        assert _mode_arg(runner.calls[0]) == "bench"

    def test_release_bench_modes_are_real_modes(self, rel):
        """子集模式必须是 test-runner 的真实模式键：拼错会让 bench 直接报错退出，
        表不回填、发布链在 refresh 就断（结构与实现双向对齐）。"""
        runner_mod = load_script("test-runner.py", module_name="test_runner_bench_modes")
        assert set(rel.RELEASE_BENCH_MODES) <= set(runner_mod.MODES)
        assert "bench" not in rel.RELEASE_BENCH_MODES  # 别名不得混入子集

    def test_first_step_failure_stops_chain(self, rel):
        runner = FakeRunner(
            responses=[
                self._TAG,
                self._PROGRAM_CHANGE,
                (["scripts/test-runner.py"], (5, "", "x")),
            ]
        )
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 5
        assert len(runner.calls) == 4  # 3 git + 首步即止


class TestTimingTelemetry:
    """发布耗时台账：`_finish_timing` 写 `logs/release.jsonl`（观测面，不得阻断发布）。"""

    def _log(self, tmp_path: Path, rel, monkeypatch) -> Path:
        log = tmp_path / "logs" / "release.jsonl"
        monkeypatch.setattr(rel, "RELEASE_LOG_FILE", log)
        constants = tmp_path / "constants.py"
        constants.write_text('APP_VERSION = "1.2.3-dev"\n', encoding="utf-8")
        monkeypatch.setattr(rel, "CONSTANTS_FILE", constants)
        return log

    def _last_record(self, log: Path) -> dict:
        lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return json.loads(lines[-1])

    def test_record_carries_command_steps_and_version(self, rel, tmp_path, monkeypatch):
        log = self._log(tmp_path, rel, monkeypatch)
        timer = rel._reset_timer()
        with timer.step("P2 场景回归"):
            pass
        rel._finish_timing("gate", 0)
        record = self._last_record(log)
        assert record["command"] == "gate"
        assert record["ok"] is True
        assert record["version"] == "1.2.3-dev"
        assert [entry["step"] for entry in record["steps"]] == ["P2 场景回归"]
        assert record["elapsed_s"] >= record["steps"][0]["elapsed_s"] >= 0
        assert timer.step_seconds("P2 场景回归") is not None
        assert "P2 场景回归" in timer.summary()
        assert timer.steps_total >= 0

    def test_failed_command_recorded_as_not_ok(self, rel, tmp_path, monkeypatch):
        """非零退出码如实入账（发布链折在哪一步，台账能看出来）。"""
        log = self._log(tmp_path, rel, monkeypatch)
        rel._reset_timer()
        rel._finish_timing("gate", 2)
        assert self._last_record(log)["ok"] is False

    def test_appends_one_line_per_command(self, rel, tmp_path, monkeypatch):
        log = self._log(tmp_path, rel, monkeypatch)
        rel._reset_timer()
        rel._finish_timing("check", 0)
        rel._reset_timer()
        rel._finish_timing("gate", 0)
        commands = [json.loads(ln)["command"] for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert commands == ["check", "gate"]

    def test_log_is_bounded_and_atomic(self, rel, tmp_path, monkeypatch):
        """台账有上限且走原子追加原语：不因长期反复发布无界增长，也不留半行。"""
        from _release import _timing

        log = tmp_path / "logs" / "release.jsonl"
        for i in range(8):
            _timing.append_record(log, {"command": f"cmd{i}"}, max_lines=5)
        lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 5
        assert json.loads(lines[-1])["command"] == "cmd7"
        assert all(ln.startswith("{") and ln.endswith("}") for ln in lines)

    def test_log_write_failure_raises_for_caller_decision(self, rel, tmp_path):
        """写盘失败以异常如实上报（调用方据以打 [!]），不静默当成已写入。"""
        from _release import _timing

        blocker = tmp_path / "logs"
        blocker.write_text("占位文件", encoding="utf-8")
        with pytest.raises(OSError):
            _timing.append_record(blocker / "release.jsonl", {"command": "gate"})

    def test_unwritable_log_does_not_break_release(self, rel, tmp_path, monkeypatch, capsys):
        """台账写不进去（父路径被文件占位）只打 [!]，不得抛异常改写发布退出码。"""
        blocker = tmp_path / "logs"
        blocker.write_text("占位文件", encoding="utf-8")
        monkeypatch.setattr(rel, "RELEASE_LOG_FILE", blocker / "release.jsonl")
        rel._reset_timer()
        rel._finish_timing("gate", 0)  # 不抛即通过
        assert "耗时记录未写入" in capsys.readouterr().out


class _ToolRepoFixture:
    """把 release 模块的输出路径重定向到临时目录，并构造最小文件集。"""

    def __init__(self, rel_mod, tmp_path: Path):
        self.mod = rel_mod
        self.root = tmp_path
        core = tmp_path / "src" / "python" / "core"
        core.mkdir(parents=True)
        docs = tmp_path / "docs" / "managements"
        docs.mkdir(parents=True)
        archive = tmp_path / "docs" / "archive" / "v0.12.x"
        archive.mkdir(parents=True)
        (core / "constants.py").write_text('APP_VERSION = "0.12.6-dev"\n', encoding="utf-8")
        (tmp_path / "README.md").write_text(
            "> 当前版本：0.12.6-dev（[版本历史](docs/managements/changelog.md)）\n", encoding="utf-8"
        )
        (docs / "changelog.md").write_text(_sample_changelog(), encoding="utf-8")
        (archive / "archived_changelog.0.12.x.md").write_text("# 归档\n", encoding="utf-8")
        (docs / "folders.md").write_text(_EVOLUTION_SAMPLE, encoding="utf-8")
        paths = {
            "REPO_ROOT": tmp_path,
            "CONSTANTS_FILE": core / "constants.py",
            "README_FILE": tmp_path / "README.md",
            "CHANGELOG_FILE": docs / "changelog.md",
            "FOLDERS_FILE": docs / "folders.md",
            "_MANAGEMENTS_DIR": docs,
            "_ARCHIVE_DOCS_DIR": tmp_path / "docs" / "archive",
        }
        for name, value in paths.items():
            setattr(rel_mod, name, value)
            setattr(self, name, value)


def _ok_runner(overrides: list | None = None) -> FakeRunner:
    """预检/一致性/git 默认全过（工作树干净）；各测试按需覆写单条。"""
    pairs: list[tuple] = [
        (["git", "branch", "--show-current"], (0, "dev\n", "")),
        (["git", "status", "--porcelain"], (0, "", "")),
        (["git", "rev-parse"], (1, "", "")),
        (["scripts/check-version-consistency.py"], (0, "[OK] 15/15\n", "")),
        (["git", "status", "--short"], (0, " M docs/x.md\n", "")),
    ]
    for matcher, resp in overrides or []:
        pairs = [p for p in pairs if p[0] != matcher] + [(matcher, resp)]
    return FakeRunner(responses=pairs)


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

    def test_preflight_failure_leaves_files_untouched(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner([(["git", "branch", "--show-current"], (0, "master\n", ""))])
        rc = rel.cmd_prepare(ns(version=None, date=None), runner=runner)
        assert rc == 2
        assert "0.12.6-dev" in fx.CONSTANTS_FILE.read_text(encoding="utf-8")
        assert "内容甲" in fx.CHANGELOG_FILE.read_text(encoding="utf-8")


class TestPublish:
    def _fixture(self, rel_mod, tmp_path, version: str):
        fx = _ToolRepoFixture(rel_mod, tmp_path)
        fx.CONSTANTS_FILE.write_text(f'APP_VERSION = "{version}"\n', encoding="utf-8")
        return fx

    @staticmethod
    def _dirty_runner(verify_out="— 8,621 通过, 0 失败\n", verify_rc=0) -> FakeRunner:
        return _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["scripts/test-runner.py"], (verify_rc, verify_out, "")),
            ]
        )

    def test_normalize_release_title_variants(self, rel):
        # 带前缀 / 单破折号前缀 → 纯描述；纯描述不变；剥离后为空回退原值
        assert rel.normalize_release_title("release: v0.12.6 —— 发布主题") == "发布主题"
        assert rel.normalize_release_title("release: v0.12.6 — 发布主题") == "发布主题"
        assert rel.normalize_release_title("纯描述") == "纯描述"
        assert rel.normalize_release_title("release: v0.12.6 ——") == "release: v0.12.6 ——"

    def test_title_prefix_normalized_to_single_subject(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        rc = rel.cmd_publish(ns(title="release: v0.12.6 —— 发布主题", push=False), runner=runner)
        assert rc == 0
        commit = next(c for c in runner.calls if len(c) > 2 and c[1] == "commit")
        assert commit[-1] == "release: v0.12.6 —— 发布主题"
        assert commit[-1].count("release: v0.12.6 ——") == 1  # 不得双前缀

    def test_commit_verify_merge_tag_order(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        rc = rel.cmd_publish(ns(title="主题", push=False), runner=runner)
        assert rc == 0
        commit_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "commit")
        verify_idx = next(i for i, c in enumerate(runner.calls) if any("test-runner.py" in p for p in c))
        merge_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "merge")
        tag_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "tag")
        assert "release: v0.12.6 —— 主题" in runner.calls[commit_idx][-1]
        assert commit_idx < verify_idx < merge_idx < tag_idx
        merge_msg = runner.calls[merge_idx][runner.calls[merge_idx].index("-m") + 1]
        assert "8621 项已全绿" in merge_msg
        assert not any("push" in c for c in runner.calls)  # 默认不推送

    def test_verify_failure_aborts_before_merge(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner(verify_out="", verify_rc=1)
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 1
        heads = [c[1] for c in runner.calls if c[0] == "git"]
        assert "merge" not in heads and "tag" not in heads and "checkout" not in heads

    def test_skips_commit_when_tree_clean(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = _ok_runner([(["scripts/test-runner.py"], (0, "— 10 通过, 0 失败\n", ""))])
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 0
        assert not any(len(c) > 2 and c[1] in {"add", "commit"} for c in runner.calls)

    def test_push_flag_gates_push_calls(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = _ok_runner([(["scripts/test-runner.py"], (0, "— 10 通过, 0 失败\n", ""))])
        rc = rel.cmd_publish(ns(title="t", push=True), runner=runner)
        assert rc == 0
        pushed = [c for c in runner.calls if "push" in c]
        assert len(pushed) == 3  # dev / master / --tags


class TestDevBump:
    def test_writes_next_dev_and_commits(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 0
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.7-dev"
        commit = next(c for c in runner.calls if len(c) > 2 and c[1] == "commit")
        assert commit[-1] == "chore: 切 0.12.7-dev 开发版本（v0.12.6 发布后）"
        assert not any("push" in c for c in runner.calls)

    def test_rejects_non_dev_branch(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "branch", "--show-current"], (0, "master\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 2
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.6"


class TestCliSurface:
    def test_parser_and_handler_tables_agree(self, rel):
        parser = rel.build_parser()
        sub_actions = [a for a in parser._subparsers._group_actions if hasattr(a, "choices")]
        parser_cmds = set(sub_actions[0].choices) if sub_actions else set()
        handlers = {"check", "prepare", "refresh", "evolution", "gate", "publish", "devbump"}
        assert parser_cmds == handlers  # 两张内部表双向一致（结构断言，不写死条数）
        assert all(hasattr(rel, f"cmd_{name}") for name in handlers)
