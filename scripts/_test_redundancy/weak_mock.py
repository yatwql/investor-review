"""检查 7：弱 mock 断言（断言 Mock 属性真值 / assertIsNotNone(Mock)）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
)

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


def _is_mock_name(node: ast.AST) -> bool:
    """变量名是否 mock 形态（含 mock / m_ 前缀）。"""
    if not isinstance(node, ast.Name):
        return False
    low = node.id.lower()
    return "mock" in low or low.startswith("m_")


def check_weak_mock_assertions(cases: list[TestCase]) -> list[str]:
    """H：弱 mock 断言——`assert <mock>.<属性>` 真值 / `assertIsNotNone(<mock>)`（含 unittest 方法形态）。"""
    findings: list[str] = []
    for case in cases:
        for sub in ast.walk(case.node):
            if isinstance(sub, ast.Assert):
                t = sub.test
                if (
                    isinstance(t, ast.Attribute)
                    and _is_mock_name(t.value)
                    and not t.attr.startswith(("called", "call_", "assert_", "reset"))
                ):
                    findings.append(
                        f"{rel(case.path)}:{case.lineno}: 用例 {case.name} 弱 mock 断言（assert {t.value.id}.{t.attr} 真值"
                        "——Mock 恒真，应改断言具体值/调用参数）"
                    )
            elif (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in ("assertIsNotNone", "assertTrue")
                and len(sub.args) == 1
                and _is_mock_name(sub.args[0])
            ):
                findings.append(
                    f"{rel(case.path)}:{case.lineno}: 用例 {case.name} 弱 mock 断言（{sub.func.attr}(<mock>)"
                    "——Mock 恒真且不为 None，应改断言具体值/调用参数）"
                )
    return findings
