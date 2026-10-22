"""检查 1-2：死用例（同名覆盖 / 非 Test 类里的 test_* / Test 类带 __init__）与无断言用例。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
    _assertions,
)

import ast
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


def check_dead_tests(cases: list[TestCase], modules: dict[Path, ast.Module]) -> list[str]:
    findings: list[str] = []
    per_file: dict[Path, Counter[tuple[str, str]]] = defaultdict(Counter)
    for case in cases:
        per_file[case.path][(case.class_name, case.name)] += 1
    for case in cases:
        key = (case.class_name, case.name)
        if per_file[case.path][key] > 1 or case.class_name.startswith("非Test"):
            continue
        if case.class_name and not case.class_name.startswith("Test"):
            findings.append(
                f"{rel(case.path)}:{case.lineno}: 用例 {case.class_name}::{case.name} 所在类名不以 Test 开头，pytest 不会收集（死用例）"
            )
    # 同名重复（后者覆盖前者）
    for path, counter in per_file.items():
        for (cls, name), n in counter.items():
            if n > 1:
                findings.append(
                    f"{rel(path)}: {cls + '::' if cls else ''}{name} 在同一文件重复定义 {n} 次，仅最后一次会执行（其余为死用例）"
                )
    # Test* 类带 __init__
    for path, tree in modules.items():
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.startswith("Test")]:
            has_init = any(
                isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name == "__init__" for b in cls.body
            )
            n_tests = sum(
                1
                for b in cls.body
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name.startswith("test")
            )
            if has_init and n_tests:
                findings.append(
                    f"{rel(path)}: Test 类 {cls.name} 定义了 __init__，pytest 整类跳过（{n_tests} 个用例为死用例）"
                )
    return findings


def check_assertion_free(cases: list[TestCase]) -> list[str]:
    findings: list[str] = []
    for case in cases:
        has_assert, _ = _assertions(case)
        if not has_assert:
            findings.append(
                f"{rel(case.path)}:{case.lineno}: 用例 {case.name} 无任何断言（assert / pytest.raises / mock 断言均无）"
            )
    return findings
