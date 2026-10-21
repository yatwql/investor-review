"""相近用例审计：骨架哈希聚类（提示人工复核，不判 finding）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
    _strip_docstring,
    _iter_test_files,
    cases_in_module,
)

import ast
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import rel  # noqa: E402


class _Skeletonizer(ast.NodeTransformer):
    """骨架归一：字面量→占位（True/False/None 保留种类）、参数名→A、私有名→N。"""

    def visit_Constant(self, node: ast.Constant):
        if node.value is True or node.value is False or node.value is None:
            return node
        return ast.copy_location(ast.Constant("<V>"), node)

    def visit_arg(self, node: ast.arg):
        node.arg = "A"
        return node

    def visit_Name(self, node: ast.Name):
        if node.id.startswith("_"):
            node.id = "N"
        return node


def _skeleton_hash(case: TestCase) -> str | None:
    """骨架哈希：同名同骨架 = 复制粘贴嫌疑（仅字面量/局部私有名不同）。"""
    try:
        node = ast.parse(ast.unparse(case.node)).body[0]
    except (ValueError, SyntaxError, MemoryError):
        return None
    node = _Skeletonizer().visit(node)
    fn = ast.FunctionDef(
        name="t", args=node.args, body=_strip_docstring(node.body), decorator_list=[], returns=None, type_comment=None
    )
    return hashlib.sha1(ast.dump(ast.fix_missing_locations(fn), include_attributes=False).encode("utf-8")).hexdigest()[
        :10
    ]


def audit_similar_bodies(include_live: bool = False, include_intra: bool = False) -> tuple[list[str], dict[str, int]]:
    """同名同骨架分组（建议性审计）：默认仅跨文件组（复制粘贴高信号），``include_intra`` 连带文件内组。"""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for path in _iter_test_files(include_live):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for case in cases_in_module(path, tree):
            sk = _skeleton_hash(case)
            if sk is None:
                continue
            cls_name = case.cls.name if case.cls is not None else "(module)"
            groups[(case.name, sk)].append(f"{rel(path)}::{cls_name}")
    lines: list[str] = []
    n_intra = 0
    for (name, sk), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        if len({m.split("::")[0] for m in members}) < 2:
            n_intra += 1
            if not include_intra:
                continue
        lines.append(f"[{name} / {sk}] " + " ; ".join(members))
    return lines, {"groups": len(lines), "intra_groups_total": n_intra}
