"""测试：check-test-redundancy 第 10 类——patch 面打在 re-export 上。

覆盖：
  - 目标抽取：``patch("a.b.c")`` 装饰器/调用、``patch.object(<模块>, "name")``、
    ``monkeypatch.setattr(<模块>, "name", …)`` 与 ``monkeypatch.setattr("a.b.c", …)``
  - 判定正例：patch 真调用点（模块自己定义 / 自己调用该符号）→ 不报
  - 判定反例：patch 纯 re-export 面（只由 import 带入、模块体内无引用）→ 报
  - 公开导出面不报：包门面 ``__init__.py`` 与模块 ``__all__`` 声明项
  - 解析边界：``from x import *`` 门面、属性链深于模块层、点分路径解析到包 ``__init__``
  - 例外表：登记后不报、缺字段/到期/未命中的自审 finding

判定函数与抽取原语直接从实现包 ``scripts/_test_redundancy/patch_surface`` 导入（入口不
为测试 re-export 这些符号）。测试用临时目录构造「生产模块 + 测试文件」小树，不碰真实仓库
的 patch 面规模，也不依赖真实生产模块内容。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    # 实现包内部是扁平 import（`_test_redundancy.*`），注入 scripts/ 才能加载
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _shared.exceptions import ExceptionTable, table_spec  # noqa: E402
from _test_redundancy import patch_surface  # noqa: E402


def _table(entries: list[dict]) -> ExceptionTable:
    """合成一张只含 ``patch-surface`` 规则的例外表（不读仓库文件）。"""
    spec = table_spec("test-redundancy")
    return ExceptionTable(spec.path, spec.rules, {patch_surface.RULE_KEY: entries})


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """把「生产模块搜索根」指到临时树：``<tmp>/src/python/...`` 即包形态模块。"""
    py_root = tmp_path / "src" / "python"
    py_root.mkdir(parents=True)
    monkeypatch.setattr(patch_surface, "_MODULE_ROOTS", (py_root,))
    return py_root


def _targets(src: str) -> list[str]:
    """从源码字符串抽取 patch 目标（按出现顺序）。"""
    return [dotted for _, dotted in patch_surface.extract_patch_targets(ast.parse(src))]


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _findings(py_root: Path, test_src: str, exceptions=None) -> list[str]:
    """在临时树上跑判定：``py_root`` 下已铺好生产模块，测试源取自 ``test_src``。"""
    test_file = py_root.parent.parent / "test_fake.py"
    tree = ast.parse(test_src)
    targets = {test_file: patch_surface.extract_patch_targets(tree)}
    return patch_surface.check_patch_surface(targets, exceptions or _table([]))


# ═══ 目标抽取 ═══


class TestExtractTargets:
    def test_patch_call_and_decorator(self):
        src = """\
import pytest
from unittest.mock import patch

@patch("pkg.mod.inner")
def test_a(mock_inner):
    with patch("pkg.mod.outer"):
        pass
"""
        assert _targets(src) == ["pkg.mod.inner", "pkg.mod.outer"]

    def test_mock_and_mocker_prefix(self):
        src = """\
from unittest import mock

def test_a(mocker):
    mock.patch("pkg.mod.a")
    mocker.patch("pkg.mod.b")
"""
        assert _targets(src) == ["pkg.mod.a", "pkg.mod.b"]

    def test_patch_object_resolves_module_alias(self):
        src = """\
from unittest.mock import patch
import pkg.mod as mod

def test_a():
    patch.object(mod, "fetch")
"""
        assert _targets(src) == ["pkg.mod.fetch"]

    def test_monkeypatch_setattr_string_form(self):
        src = """\
def test_a(monkeypatch):
    monkeypatch.setattr("pkg.mod.flag", True)
"""
        assert _targets(src) == ["pkg.mod.flag"]

    def test_monkeypatch_setattr_module_alias_form(self):
        src = """\
from src.python.pkg import mod

def test_a(monkeypatch):
    monkeypatch.setattr(mod, "fetch", lambda: None)
"""
        assert _targets(src) == ["src.python.pkg.mod.fetch"]

    def test_relative_import_alias_not_resolved(self):
        """相对导入指测试自己的辅助模块，不属 re-export 面，不产出目标。"""
        src = """\
from .helpers import mod

def test_a(monkeypatch):
    monkeypatch.setattr(mod, "fetch", lambda: None)
"""
        assert _targets(src) == []


# ═══ 判定：正例（真调用点，不报） ═══


class TestRealCallSiteNotReported:
    def test_module_defines_symbol(self, fake_tree):
        _write(fake_tree / "pkg" / "mod.py", "def fetch():\n    return 1\n")
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n') == []

    def test_module_imports_then_calls_symbol(self, fake_tree):
        """模块自己 import 后真的调用 → 合法 patch 面（调用时按模块全局解析，patch 生效）。"""
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", "from pkg.impl import fetch\n\n\ndef run():\n    return fetch()\n")
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n') == []


# ═══ 判定：反例（纯 re-export 面，报） ═══


class TestReexportFaceReported:
    def test_import_only_symbol_reported(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", "from pkg.impl import fetch  # noqa: F401\n")
        findings = _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n')
        assert len(findings) == 1
        assert "pkg.mod.fetch" in findings[0]
        assert "re-export" in findings[0]

    def test_star_import_facade_reported(self, fake_tree):
        """``from x import *`` 门面：符号不可枚举，按「可能由 import 带入」判。"""
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", "from pkg.impl import *\n")
        findings = _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n')
        assert len(findings) == 1

    def test_star_import_facade_own_symbol_not_reported(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", "from pkg.impl import *\n\n\ndef fetch():\n    return 2\n")
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n') == []


# ═══ 判定：公开导出面不报（C 口径） ═══


class TestPublicExportSurface:
    def test_package_facade_init_not_reported(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "__init__.py", "from pkg.impl import fetch\n")
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.fetch", None)\n') == []

    def test_declared_all_not_reported(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", '__all__ = ["fetch"]\n\nfrom pkg.impl import fetch\n')
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n') == []

    def test_all_augmented_assignment_recognised(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(
            fake_tree / "pkg" / "mod.py",
            'from pkg.impl import fetch\n\n__all__ = []\n__all__ += ["fetch"]\n',
        )
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n') == []


# ═══ 解析边界 ═══


class TestResolveBoundary:
    def test_attribute_chain_below_module_level_skipped(self, fake_tree):
        """``pkg.mod.Cls.method`` 深于模块层：不静态判定，不报。"""
        _write(fake_tree / "pkg" / "mod.py", "class Cls:\n    def method(self):\n        pass\n")
        assert (
            _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.Cls.method", None)\n')
            == []
        )

    def test_unresolvable_target_skipped(self, fake_tree):
        """目标模块不在搜索根（第三方库等）：无从判定，不报。"""
        assert _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("requests.get", None)\n') == []

    def test_resolve_prefers_deepest_module(self, fake_tree):
        """``pkg.mod.fetch`` 里 ``pkg/mod.py`` 与 ``pkg/mod`` 包并存时，优先最深的模块文件。"""
        _write(fake_tree / "pkg" / "mod.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod" / "__init__.py", "from pkg.impl import fetch\n")
        resolved = patch_surface.resolve_target("pkg.mod.fetch")
        assert resolved is not None
        module_file, name = resolved
        assert module_file == fake_tree / "pkg" / "mod.py"
        assert name == "fetch"


# ═══ 例外表 ═══


class TestExceptionTable:
    def test_registered_target_not_reported(self, fake_tree):
        _write(fake_tree / "pkg" / "impl.py", "def fetch():\n    return 1\n")
        _write(fake_tree / "pkg" / "mod.py", "from pkg.impl import fetch\n")
        table = _table([{"name": "pkg.mod.fetch"}])
        assert (
            _findings(fake_tree, 'def test_a(monkeypatch):\n    monkeypatch.setattr("pkg.mod.fetch", None)\n', table)
            == []
        )
        assert table.used == {("patch-surface", "pkg.mod.fetch")}

    def test_missing_metadata_field_reported(self):
        table = _table([{"name": "pkg.mod.fetch", "owner": "x", "reason": "y", "expiry": "2027-06-30"}])
        table.used.add(("patch-surface", "pkg.mod.fetch"))
        findings = patch_surface.audit_exceptions(table)
        assert len(findings) == 1
        assert "replacement" in findings[0]

    def test_expired_entry_reported(self):
        table = _table(
            [
                {
                    "name": "pkg.mod.fetch",
                    "owner": "x",
                    "reason": "y",
                    "expiry": "2020-01-02",
                    "replacement": "z",
                }
            ]
        )
        table.used.add(("patch-surface", "pkg.mod.fetch"))
        findings = patch_surface.audit_exceptions(table)
        assert len(findings) == 1
        assert "到期" in findings[0]

    def test_stale_entry_reported(self):
        """登记了但不再命中任何违规 → 说明规则已修复，例外成了免死金牌。"""
        table = _table(
            [
                {
                    "name": "pkg.mod.gone",
                    "owner": "x",
                    "reason": "y",
                    "expiry": "2027-06-30",
                    "replacement": "z",
                }
            ]
        )
        findings = patch_surface.audit_exceptions(table)
        assert len(findings) == 1
        assert "未命中" in findings[0]

    def test_load_exceptions_reads_repo_table(self, tmp_path, monkeypatch):
        table_file = tmp_path / "exceptions.json"
        table_file.write_text(
            json.dumps({"patch-surface": [{"name": "pkg.mod.fetch", "owner": "x"}]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(patch_surface, "EXCEPTIONS_FILE", table_file)
        table = patch_surface.load_exceptions()
        assert table.allowed("patch-surface") == {("pkg.mod.fetch",)}
        assert table.entries_of("patch-surface")[0]["owner"] == "x"

    def test_load_exceptions_parse_error_reported(self, tmp_path, monkeypatch):
        table_file = tmp_path / "exceptions.json"
        table_file.write_text("{ 不是 JSON", encoding="utf-8")
        monkeypatch.setattr(patch_surface, "EXCEPTIONS_FILE", table_file)
        table = patch_surface.load_exceptions()
        assert patch_surface.audit_exceptions(table) != []


# ═══ 与编排面的接线 ═══


class TestRunnerWiring:
    def test_repo_run_reports_no_patch_surface_findings(self):
        """真实仓库冒烟：patched 面存量已整改/登记，第 10 类应为 0。"""
        findings, stats = load_script("check-test-redundancy.py").run_checks(include_live=False)
        assert stats["patch_surface"] == 0, [f for f in findings if "re-export" in f]
