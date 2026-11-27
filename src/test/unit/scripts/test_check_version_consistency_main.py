"""`scripts/check-version-consistency.py` 主流程（`main`）覆盖。

既有用例覆盖各 `_check_*` / `_auto_fix_*` 判定与写回细节，这里补**编排层**：
CHECKS 逐项遍历、七种断言类型的分派、缺文件跳过、`--ci` 与人类可读两种输出形态、
`--fix` 后的退出码三态（0 已全修 / 0 修了但仍有残留 / 2 无可修项）。

夹具用 tmp_path 现造一棵最小文档树（并把脚本的 `REPO_ROOT` 指向它），因此
断言的是「分派到哪个判定、输出哪句口径、退出码几名」，而不是把受检文件清单
条数写死——清单本身是随文档演进的可增长集合。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "check-version-consistency.py"
_VERSION = "1.2.3-dev"

_CHANGELOG_PTR = "> **最近发布 [0.12.0]**（2026-10-03）——已发布版本段随发布移入归档。\n"


def _header_doc(version: str = _VERSION) -> str:
    return f"# 计划\n\n> 文档版本：{version}\n\n正文\n"


def _evolution_doc(version: str = _VERSION, release: str = "0.12.0", date: str = "2026-10-03") -> str:
    return (
        f"> **三个读数**：最新发布 = 最近一次发布 tag（v{release} · {date}）；"
        f"**当前开发版 = 本次重跑时的 HEAD**。\n"
        f"| 指标 | 最初版本 | 最新发布（最近发布 tag v{release} · {date}） | 当前开发版（{version}） |\n"
    )


def _rf_doc(version: str = _VERSION) -> str:
    return f"# 自审台账\n\n### 开发期已修复（{version}）\n\n| 摘要 | 状态 |\n"


@pytest.fixture
def version_cli(monkeypatch, tmp_path):
    """加载脚本、把仓库根与事实源指向 tmp_path，并清空注册好的 CHECKS。"""
    mod = load_script(_SCRIPT, module_name="check_version_consistency_cli")
    constants = tmp_path / "src" / "python" / "core" / "constants.py"
    constants.parent.mkdir(parents=True, exist_ok=True)
    constants.write_text(f'APP_VERSION = "{_VERSION}"\n', encoding="utf-8")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "CONSTANTS_FILE", constants)
    monkeypatch.setattr(mod, "CHECKS", [])
    return mod


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _run(mod, monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", [_SCRIPT, *argv])
    mod.main()


class TestAppVersionSource:
    """版本事实源只有一处：constants.py 的 APP_VERSION 行。"""

    def test_reads_app_version_from_constants(self, version_cli):
        assert version_cli._get_app_version() == _VERSION

    def test_dev_suffix_is_preserved(self, version_cli, tmp_path):
        """开发期版本号必须原样带 `-dev`（截断成发布形态会让节头校验错批次）。"""
        assert version_cli._get_app_version().endswith("-dev")


class TestPyprojectAssertion:
    """pyproject.toml 用独立的 `pyproject_version` 断言（不是全文 contains）。"""

    def test_version_line_must_match_exactly(self, version_cli):
        assert version_cli._check_pyproject_version(f'version = "{_VERSION}"\n', _VERSION) is True

    @pytest.mark.parametrize("text", ['version = "1.2.2"\n', "无版本行\n", 'version = "1.2.3-dev.1"\n'])
    def test_other_shapes_are_rejected(self, version_cli, text):
        assert version_cli._check_pyproject_version(text, _VERSION) is False

    def test_auto_fix_rewrites_first_version_line_only(self, version_cli, tmp_path):
        path = _write(tmp_path, "pyproject.toml", 'other = "1.0.0"\nversion = "1.2.2"\n[deps]\nversion = "9.9.9"\n')
        assert version_cli._auto_fix_pyproject(path, _VERSION) is True
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[1] == f'version = "{_VERSION}"'
        assert lines[3] == 'version = "9.9.9"', "只改第一处（依赖块的 version 不属于本项目版本）"

    def test_auto_fix_is_noop_when_already_matching(self, version_cli, tmp_path):
        path = _write(tmp_path, "pyproject.toml", f'version = "{_VERSION}"\n')
        assert version_cli._auto_fix_pyproject(path, _VERSION) is False


class TestMainAllPass:
    """全部一致时退出码为 0（无 sys.exit / 隐含 None）并报总项数。"""

    def _register_all_types(self, mod, root: Path) -> None:
        changelog = _write(root, "docs/changelog.md", _CHANGELOG_PTR)
        mod.CHECKS.extend(
            [
                (_write(root, "pyproject.toml", f'version = "{_VERSION}"\n'), "pyproject_version", ()),
                (_write(root, "README.md", f"> 当前版本：{_VERSION}\n"), "exact", (r"> 当前版本：{v}",)),
                (_write(root, "docs/changelog2.md", f"## [{_VERSION}] - 开发中\n"), "contains", ("[{v}]",)),
                (_write(root, "docs/plan.md", _header_doc()), "header", ()),
                (_write(root, "docs/folders.md", _evolution_doc()), "evolution_head", ()),
                (root / "docs/folders.md", "release_tag", (changelog,)),
                (_write(root, "docs/rf.md", _rf_doc()), "rf_dev_section", ()),
            ]
        )

    def test_all_types_pass_returns_zero(self, version_cli, monkeypatch, tmp_path, capsys):
        self._register_all_types(version_cli, tmp_path)

        _run(version_cli, monkeypatch)

        out = capsys.readouterr().out
        assert f"APP_VERSION = {_VERSION}" in out
        assert f"全部 {len(version_cli.CHECKS)} 项通过" in out
        assert "[ERR]" not in out

    def test_ci_mode_prints_no_progress_banner(self, version_cli, monkeypatch, tmp_path, capsys):
        self._register_all_types(version_cli, tmp_path)

        _run(version_cli, monkeypatch, "--ci")

        out = capsys.readouterr().out
        assert "[..]" not in out, "--ci 只输出 finding，不播报进度"
        assert "[OK] 全部" in out, "--ci 静默通过项（只留汇总行）"
        assert f"全部 {len(version_cli.CHECKS)} 项通过" in out

    def test_verbose_prints_each_passing_entry(self, version_cli, monkeypatch, tmp_path, capsys):
        self._register_all_types(version_cli, tmp_path)

        _run(version_cli, monkeypatch, "--ci", "--verbose")

        out = capsys.readouterr().out
        assert out.count("  [OK] ") == len(version_cli.CHECKS)

    def test_missing_file_is_skipped_not_failed(self, version_cli, monkeypatch, tmp_path, capsys):
        version_cli.CHECKS.append((tmp_path / "docs" / "ghost.md", "header", ()))

        _run(version_cli, monkeypatch)

        out = capsys.readouterr().out
        assert "文件不存在，跳过" in out
        assert f"全部 {len(version_cli.CHECKS)} 项通过" in out

    def test_ci_mode_stays_silent_about_missing_file(self, version_cli, monkeypatch, tmp_path, capsys):
        version_cli.CHECKS.append((tmp_path / "docs" / "ghost.md", "header", ()))

        _run(version_cli, monkeypatch, "--ci")

        assert "跳过" not in capsys.readouterr().out


class TestMainFindings:
    """不一致时按类型给出可操作口径，退出码恒为 2（契约：发现 finding → 2）。"""

    @pytest.mark.parametrize(
        ("assert_type", "text", "expected_hint"),
        [
            ("header", "# 计划\n\n> 文档版本：1.0.0\n", "头部版本行未同步"),
            ("evolution_head", _evolution_doc("1.0.0"), "「当前开发版」列头版本号未同步"),
            ("rf_dev_section", _rf_doc("1.0.0"), "「开发期已修复」节头未同步"),
            ("release_tag", _evolution_doc(release="0.11.12", date="2026-10-01"), "与 changelog 发布指针不一致"),
            ("contains", "无版本号\n", "版本号未同步"),
        ],
    )
    def test_each_type_has_its_own_err_wording(
        self, version_cli, monkeypatch, tmp_path, capsys, assert_type, text, expected_hint
    ):
        changelog = _write(tmp_path, "docs/changelog.md", _CHANGELOG_PTR)
        target = _write(tmp_path, "docs/target.md", text)
        args = (changelog,) if assert_type == "release_tag" else ()
        if assert_type == "contains":
            args = ("[{v}]",)
        version_cli.CHECKS.append((target, assert_type, args))

        with pytest.raises(SystemExit) as exc:
            _run(version_cli, monkeypatch)

        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert expected_hint in out
        assert "[ERR]" in out
        assert "发布流程：" in out

    @pytest.mark.parametrize(
        ("assert_type", "text", "expected_hint"),
        [
            ("header", "# 计划\n", "头部版本行未同步"),
            ("evolution_head", "无演进表\n", "「当前开发版」列头版本号未同步"),
            ("rf_dev_section", _rf_doc("1.0.0"), "「开发期已修复」节头未同步"),
            ("release_tag", _evolution_doc(release="0.11.12", date="2026-10-01"), "与 changelog 发布指针不一致"),
            ("exact", "无版本号\n", "版本号未同步"),
        ],
    )
    def test_ci_mode_emits_bare_finding_lines(
        self, version_cli, monkeypatch, tmp_path, capsys, assert_type, text, expected_hint
    ):
        """`--ci` 输出给守护脚本解析：无 `[ERR]` 前缀、无发布流程指引。"""
        changelog = _write(tmp_path, "docs/changelog.md", _CHANGELOG_PTR)
        target = _write(tmp_path, "docs/target.md", text)
        args = (changelog,) if assert_type == "release_tag" else ()
        pattern_args = (r"> 当前版本：{v}",) if assert_type == "exact" else args
        version_cli.CHECKS.append((target, assert_type, pattern_args))

        with pytest.raises(SystemExit) as exc:
            _run(version_cli, monkeypatch, "--ci")

        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert expected_hint in out
        assert "[ERR]" not in out
        assert "发布流程" not in out


class TestMainFix:
    """`--fix` 的可修类型逐项写回；退出码取决于是否真改动了文件。"""

    @pytest.mark.parametrize(
        ("assert_type", "stale_text", "expected_snippet"),
        [
            ("header", "# 计划\n\n> 文档版本：1.0.0\n", f"> 文档版本：{_VERSION}"),
            ("evolution_head", _evolution_doc("1.0.0"), f"当前开发版（{_VERSION}）"),
            ("rf_dev_section", _rf_doc("1.0.0"), f"### 开发期已修复（{_VERSION}）"),
        ],
    )
    def test_fixable_types_are_rewritten_on_disk(
        self, version_cli, monkeypatch, tmp_path, capsys, assert_type, stale_text, expected_snippet
    ):
        target = _write(tmp_path, "docs/target.md", stale_text)
        version_cli.CHECKS.append((target, assert_type, ()))

        _run(version_cli, monkeypatch, "--fix")

        assert expected_snippet in target.read_text(encoding="utf-8")
        out = capsys.readouterr().out
        assert "已自动修正" in out
        assert f"全部 {len(version_cli.CHECKS)} 项通过" in out, "修完即全部通过（不留残留）"

    def test_release_tag_fix_syncs_to_changelog_pointer(self, version_cli, monkeypatch, tmp_path, capsys):
        changelog = _write(tmp_path, "docs/changelog.md", _CHANGELOG_PTR)
        target = _write(tmp_path, "docs/folders.md", _evolution_doc(release="0.11.12", date="2026-10-01"))
        version_cli.CHECKS.append((target, "release_tag", (changelog,)))

        _run(version_cli, monkeypatch, "--fix")

        text = target.read_text(encoding="utf-8")
        assert "v0.12.0 · 2026-10-03" in text
        assert "已自动同步「最近发布 tag」" in capsys.readouterr().out

    def test_pyproject_fix_via_main(self, version_cli, monkeypatch, tmp_path, capsys):
        target = _write(tmp_path, "pyproject.toml", 'version = "0.0.1"\n')
        version_cli.CHECKS.append((target, "pyproject_version", ()))

        _run(version_cli, monkeypatch, "--fix")

        assert f'version = "{_VERSION}"' in target.read_text(encoding="utf-8")
        assert "已自动修正为" in capsys.readouterr().out

    def test_fix_that_cannot_apply_falls_through_to_exit_2(self, version_cli, monkeypatch, tmp_path, capsys):
        """无可修锚点（文档里根本没有版本头）→ fixed=0 → 仍按 finding 退出 2。"""
        target = _write(tmp_path, "docs/target.md", "# 无版本头\n")
        version_cli.CHECKS.append((target, "header", ()))

        with pytest.raises(SystemExit) as exc:
            _run(version_cli, monkeypatch, "--fix")

        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "已自动修正" not in out
        assert "版本号不一致 — 请先手动更新后重试" in out

    def test_partial_fix_exits_zero_with_manual_residue_notice(self, version_cli, monkeypatch, tmp_path, capsys):
        """可修项修完即退出 0，残留的手工项由提示句交接（不是静默忽略）。"""
        fixable = _write(tmp_path, "docs/plan.md", "# 计划\n\n> 文档版本：1.0.0\n")
        manual = _write(tmp_path, "docs/readme.md", "无版本号\n")
        version_cli.CHECKS.extend([(fixable, "header", ()), (manual, "contains", ("[{v}]",))])

        with pytest.raises(SystemExit) as exc:
            _run(version_cli, monkeypatch, "--fix")

        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "已自动修正 1 项" in out
        assert "其他文件需手动更新" in out
        assert "版本号未同步" in out, "残留项仍要报出来"
