"""模块依赖图无环（`src/python` 顶层 import 层面）。

背景：循环 import 在 Python 里"能用"，但只在「先定义 A 再延迟 import B」这种**导入顺序**
成立时才不炸——改一行定义位置就会 ImportError，且阅读时看不出依赖方向。修法是让两侧共用面
落在同一个基座模块（如 `core/doctor_common.py`），依赖方向因此单向可读。

口径：只看**模块顶层** import（函数内惰性 import 是本项目既有的解耦手段，不算环）；
`from src.python.x import y` 只算对模块 `src.python.x` 的依赖（符号级展开不改变方向）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_PY_ROOT = Path(__file__).resolve().parents[3] / "src" / "python"


def _module_deps() -> dict[str, set[str]]:
    dotted = {
        path: "src.python." + ".".join(path.relative_to(_PY_ROOT).with_suffix("").parts)
        for path in _PY_ROOT.rglob("*.py")
    }
    names = set(dotted.values())
    deps: dict[str, set[str]] = {}
    for path, name in dotted.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        targets: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.python"):
                targets.add(node.module)
            elif isinstance(node, ast.Import):
                targets.update(alias.name for alias in node.names if alias.name.startswith("src.python"))
        deps[name] = {target for target in targets if target in names and target != name}
    return deps


def _find_cycles(deps: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """DFS 三色法找环（返回闭合路径，空列表 = 无环）。"""
    white, gray, black = 0, 1, 2
    color = {module: white for module in deps}
    cycles: list[tuple[str, ...]] = []

    def _visit(module: str, stack: list[str]) -> None:
        color[module] = gray
        stack.append(module)
        for nxt in sorted(deps.get(module, ())):
            if color.get(nxt, white) == gray:
                cycles.append(tuple(stack[stack.index(nxt) :]))
            elif color.get(nxt, white) == white:
                _visit(nxt, stack)
        stack.pop()
        color[module] = black

    for module in sorted(deps):
        if color[module] == white:
            _visit(module, [])
    return cycles


def test_no_module_level_import_cycles():
    """顶层 import 图必须无环（有环时按报错提示把共用面下沉到基座模块）。"""
    cycles = _find_cycles(_module_deps())
    rendered = [" → ".join(chain) for chain in cycles]
    assert cycles == [], "存在循环 import（把两侧共用面下沉到基座模块，如 core/doctor_common.py）：\n" + "\n".join(
        rendered
    )


def test_doctor_common_does_not_depend_on_doctor():
    """基座模块不得反向依赖上层（否则环会以另一种形态复活）。"""
    deps = _module_deps()
    assert not any("core.doctor" in dep for dep in deps.get("src.python.core.doctor_common", set()))
