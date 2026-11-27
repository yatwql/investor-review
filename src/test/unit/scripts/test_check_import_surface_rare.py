"""check-import-surface.py 的长尾分支：例外表缺失、`__all__` 非字面量、
同包私有导入、动态导入目标解析，以及 `main()` 的 CLI 输出与退出码。

断言走 finding 的有无与规则前缀（不写死可增长集合条数），退出码按
「0 = 通过 / 2 = finding」契约校验。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="surface")
def fixture_surface():
    return load_script("check-import-surface.py", module_name="_check_import_surface_rare")


def _package(root, name: str, body: str):
    """在临时根下建包：`name/__init__.py` 写入 `body`，返回包目录。"""
    pkg = root / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(body, encoding="utf-8")
    return pkg


class TestExceptionTableLoading:
    def test_missing_file_yields_empty_table(self, surface, monkeypatch, tmp_path):
        monkeypatch.setattr(surface, "EXCEPTIONS_FILE", tmp_path / "absent.json")
        table = surface._load_exceptions()
        assert table.load_error == ""
        assert all(not entries for entries in table.entries.values())


class TestPrivateAllLiteral:
    def test_non_literal_dunder_all_is_skipped(self, surface, tmp_path):
        root = tmp_path / "py"
        _package(root, "pkg", "__all__ = [name for name in ('_private',)]\n")
        assert surface.scan_private_all(root) == []

    def test_private_name_is_reported(self, surface, tmp_path):
        root = tmp_path / "py"
        _package(root, "pkg", "__all__ = ['_private']\n")
        findings = surface.scan_private_all(root)
        assert len(findings) == 1
        assert "[private-all]" in findings[0]


class TestCrossPackagePrivate:
    def test_same_package_private_import_allowed(self, surface, tmp_path):
        root = tmp_path / "py"
        pkg = _package(root, "pkg", "")
        (pkg / "_impl.py").write_text("X = 1\n", encoding="utf-8")
        (pkg / "user.py").write_text("from src.python.pkg._impl import X\n", encoding="utf-8")
        assert surface.scan_cross_private(root) == []

    def test_cross_package_private_import_reported(self, surface, tmp_path):
        root = tmp_path / "py"
        alpha = _package(root, "alpha", "")
        (alpha / "_impl.py").write_text("X = 1\n", encoding="utf-8")
        beta = _package(root, "beta", "")
        (beta / "user.py").write_text("from src.python.alpha._impl import X\n", encoding="utf-8")
        findings = surface.scan_cross_private(root)
        assert any("[cross-private]" in finding and "src.python.alpha._impl" in finding for finding in findings)


class TestDynamicTarget:
    def test_resolvable_literal_is_accepted(self, surface, tmp_path):
        root = tmp_path / "py"
        root.mkdir()
        (root / "ok.py").write_text("import importlib\nimportlib.import_module('json')\n", encoding="utf-8")
        assert surface.scan_dynamic(root) == []

    def test_unresolvable_literal_is_reported(self, surface, tmp_path):
        root = tmp_path / "py"
        root.mkdir()
        (root / "bad.py").write_text(
            "import importlib\nimportlib.import_module('_no_such_module_for_surface_check')\n", encoding="utf-8"
        )
        findings = surface.scan_dynamic(root)
        assert len(findings) == 1
        assert findings[0].startswith("[dynamic-target]")
        assert "_no_such_module_for_surface_check" in findings[0]

    def test_variable_target_is_ignored(self, surface, tmp_path):
        root = tmp_path / "py"
        root.mkdir()
        (root / "dyn.py").write_text("import importlib\nname = 'x'\nimportlib.import_module(name)\n", encoding="utf-8")
        assert surface.scan_dynamic(root) == []

    def test_exception_suppresses_dynamic_finding(self, surface, monkeypatch, tmp_path):
        root = tmp_path / "py"
        root.mkdir()
        target_file = root / "bad.py"
        target_file.write_text(
            "import importlib\nimportlib.import_module('_no_such_module_for_surface_check')\n", encoding="utf-8"
        )
        monkeypatch.setattr(surface, "rel", lambda path: "bad.py")
        exceptions = surface._load_exceptions()
        exceptions = surface.ExceptionTable(
            exceptions.path,
            exceptions.rules,
            {"dynamic-target": [{"path": "bad.py", "name": "_no_such_module_for_surface_check"}]},
        )
        assert surface.scan_dynamic(root, exceptions) == []


class TestMainCli:
    def _run(self, surface, monkeypatch, *argv: str) -> int:
        monkeypatch.setattr(sys, "argv", ["check-import-surface.py", *argv])
        return surface.main()

    def test_clean_run_exits_zero(self, surface, monkeypatch, capsys):
        monkeypatch.setattr(surface, "collect", lambda: ([], {"dynamic-target": 0}))
        assert self._run(surface, monkeypatch) == 0
        assert "[OK] 导入面契约通过" in capsys.readouterr().out

    def test_findings_exit_two(self, surface, monkeypatch, capsys):
        monkeypatch.setattr(surface, "collect", lambda: (["[dynamic-target] a.py:1 x"], {"dynamic-target": 1}))
        assert self._run(surface, monkeypatch) == 2
        assert "须修正或登记例外表" in capsys.readouterr().out

    def test_verbose_prints_rule_counts(self, surface, monkeypatch, capsys):
        monkeypatch.setattr(surface, "collect", lambda: ([], {"dynamic-target": 0}))
        assert self._run(surface, monkeypatch, "-v") == 0
        assert "规则计数" in capsys.readouterr().out

    def test_ci_mode_prints_bare_finding(self, surface, monkeypatch, capsys):
        monkeypatch.setattr(surface, "collect", lambda: (["[dynamic-target] a.py:1 x"], {"dynamic-target": 1}))
        assert self._run(surface, monkeypatch, "--ci") == 2
        out = capsys.readouterr().out
        assert out.strip() == "[dynamic-target] a.py:1 x"
