"""模块级导入环守卫 — 顶层 import 不得形成环。

守卫方式：解析 `src/python/` 全部模块的**顶层** import（含 `try` 块内的条件导入），
按模块建图并求强连通分量；任一分量含 >1 个模块即视为环。

为什么只查顶层：函数体内的延迟导入是刻意用来打断环的手段（`from x import y` 放到
调用期），把它们算进来会把「刻意延迟」误判成缺陷。真正的脆弱点是包 `__init__` 与
其子模块在顶层互相导入——此时能否导入成功取决于包初始化走到第几行，换导入顺序或
中途新增一个顶层导入就会变成 `ImportError`，且报错点与病因相距很远。

守卫只断言**结构关系**（无环），不写死模块数/环数：拆包、新增模块、新增顶层导入都
应自动跟随。
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_SOURCE_ROOT = Path(__file__).resolve().parents[3] / "python"
_PACKAGE_ROOT = "src.python"


def _module_name(path: Path) -> str:
    """文件路径 → 相对 `src/python` 的点分模块名（`__init__` 归到包名）。"""
    rel = path.relative_to(_SOURCE_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _iter_top_level_imports(tree: ast.Module) -> list[tuple[str, int]]:
    """返回 [(被导入的模块名, 行号)]，只看顶层语句与 `try` 块内的顶层导入。"""
    out: list[tuple[str, int]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ImportFrom):
                if child.module and child.level == 0:
                    out.append((child.module, child.lineno))
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    out.append((alias.name, child.lineno))

    visit(tree)
    return out


def _collect_graph() -> dict[str, set[str]]:
    """建模块级导入图；仅保留指向 `src/python` 内部模块的边。"""
    known = {_module_name(path) for path in _SOURCE_ROOT.rglob("*.py") if "__pycache__" not in path.parts}
    graph: dict[str, set[str]] = defaultdict(set)
    for path in _SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path)
        graph[module]  # 确保孤立模块也出现在图里
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for target, _line in _iter_top_level_imports(tree):
            if not target.startswith(f"{_PACKAGE_ROOT}."):
                continue
            inner = target[len(_PACKAGE_ROOT) + 1 :]
            # `from pkg import name` 中的 name 可能是子模块：逐个前缀向上找已知模块
            candidates = [inner]
            parts = inner.split(".")
            candidates += [".".join(parts[:i]) for i in range(len(parts), 0, -1)]
            for candidate in candidates:
                if candidate in known:
                    graph[module].add(candidate)
                    break
    return graph


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan 求强连通分量，返回所有含 >1 个模块的分量。"""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []
    counter = 0

    def strongconnect(node: str) -> None:
        nonlocal counter
        index[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)
        for succ in graph.get(node, ()):
            if succ not in index:
                strongconnect(succ)
                low[node] = min(low[node], low[succ])
            elif succ in on_stack:
                low[node] = min(low[node], index[succ])
        if low[node] == index[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                cycles.append(sorted(component))

    for node in list(graph):
        if node not in index:
            strongconnect(node)
    return cycles


class TestNoTopLevelImportCycles:
    """顶层导入图必须无环。"""

    def test_module_graph_has_no_cycles(self):
        cycles = _find_cycles(_collect_graph())
        assert cycles == [], "顶层 import 形成环（把共享符号下移到叶子模块，或用函数内延迟导入）：\n" + "\n".join(
            "  ← " + " ← ".join(component) for component in cycles
        )

    def test_package_facades_do_not_form_cycles_with_submodules(self):
        """包 `__init__` 与其子模块的顶层互导单独再断言一次（最容易反复引入的形态）。"""
        graph = _collect_graph()
        offenders = [
            (package, member)
            for package, imports in graph.items()
            for member in imports
            if member.startswith(f"{package}.") and package in graph.get(member, set())
        ]
        assert offenders == [], f"包门面与子模块顶层互导：{offenders}"
