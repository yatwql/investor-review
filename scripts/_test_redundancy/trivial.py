"""检查 6：恒真断言（assert True / x == x）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
)

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import rel  # noqa: E402


def check_trivially_true(cases: list[TestCase]) -> list[str]:
    """F：恒真断言——`assert True` / `assert x == x`，不验证任何行为。"""
    findings: list[str] = []
    for case in cases:
        for sub in ast.walk(case.node):
            if not isinstance(sub, ast.Assert):
                continue
            t = sub.test
            if isinstance(t, ast.Constant) and t.value is True:
                findings.append(
                    f"{rel(case.path)}:{case.lineno}: 用例 {case.name} 恒真断言（assert True，不验证任何行为）"
                )
            elif (
                isinstance(t, ast.Compare)
                and len(t.ops) == 1
                and isinstance(t.left, ast.Name)
                and any(isinstance(c, ast.Name) and c.id == t.left.id for c in t.comparators)
            ):
                findings.append(
                    f"{rel(case.path)}:{case.lineno}: 用例 {case.name} 恒真断言（x == x 恒真，不验证任何行为）"
                )
    return findings
