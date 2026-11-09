"""`core.path_utils.resolve_project_path` 单源原语测试。

覆盖两件事：① 解析口径（绝对原样 / 相对拼项目根并归一 / 空串落项目根）；
② **不再出现第二份实现**——产品代码里除本模块外不得再写
``x if os.path.isabs(x) else os.path.join(PROJECT_ROOT, x)`` 这类同构副本
（否则口径又会分叉，形同没有单源）。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from src.python.core import path_utils
from src.python.core.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_PRODUCT_ROOT = Path(PROJECT_ROOT) / "src" / "python"
_SINGLE_SOURCE = Path(PROJECT_ROOT) / "src" / "python" / "core" / "path_utils.py"


class TestResolveProjectPath:
    def test_absolute_path_kept_verbatim(self, tmp_path):
        absolute = str(tmp_path / "app.log")
        assert path_utils.resolve_project_path(absolute) == absolute

    def test_relative_path_joined_to_project_root(self):
        expected = os.path.join(PROJECT_ROOT, "logs", "app.log")
        assert path_utils.resolve_project_path("logs/app.log") == expected

    def test_relative_path_normalized(self):
        assert path_utils.resolve_project_path("./logs//app.log") == os.path.join(PROJECT_ROOT, "logs", "app.log")

    def test_empty_path_resolves_to_project_root(self):
        assert path_utils.resolve_project_path("") == PROJECT_ROOT
        assert path_utils.resolve_project_path("   ") == PROJECT_ROOT

    def test_resolved_path_is_absolute_for_relative_input(self):
        assert os.path.isabs(path_utils.resolve_project_path("data/cache"))


def _is_project_root_join(node: ast.AST) -> bool:
    """是否是 `os.path.join(PROJECT_ROOT, ...)` 形态的调用。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "join"):
        return False
    if not node.args:
        return False
    first = node.args[0]
    return isinstance(first, ast.Name) and first.id == "PROJECT_ROOT"


def _iter_isabs_ternaries(tree: ast.Module):
    """产出 `A if os.path.isabs(x) else B` 形态（含 if/else 语句版的 join 分支）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp):
            test = node.test
            if (
                isinstance(test, ast.Call)
                and isinstance(test.func, ast.Attribute)
                and test.func.attr == "isabs"
                and (_is_project_root_join(node.body) or _is_project_root_join(node.orelse))
            ):
                yield node.lineno
        elif isinstance(node, ast.If):
            test = node.test
            if not (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute) and test.func.attr == "isabs"):
                continue
            assigned = [n for n in ast.walk(ast.Module(body=node.body, type_ignores=[])) if _is_project_root_join(n)]
            if assigned and [
                n for n in ast.walk(ast.Module(body=node.orelse, type_ignores=[])) if _is_project_root_join(n)
            ]:
                yield node.lineno


class TestNoDuplicateImplementation:
    def test_only_single_source_builds_project_root_paths(self):
        offenders: list[str] = []
        for path in sorted(_PRODUCT_ROOT.rglob("*.py")):
            if path == _SINGLE_SOURCE:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for lineno in _iter_isabs_ternaries(tree):
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{lineno}")
        assert offenders == [], f"请在 core.path_utils.resolve_project_path 收口，勿各自实现：{offenders}"
