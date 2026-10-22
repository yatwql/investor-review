"""检查 5：硬编码演进总数（对可增长集合写死条数）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
)

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


def check_hardcoded_evolving_totals(cases: list[TestCase]) -> list[str]:
    """E. **硬编码「会演进的总数」** —— 把需求/章节/开关等**可增长集合的条数**写死在断言里。

    为何是缺陷：这类总数是**文档真值来源的派生量**，随正常开发（新增一条需求/章节/开关）
    必然变化。写死后，良性变更会把测试打红（而它捕捉不到任何真实缺陷），反而阻碍演进；
    且它与门禁脚本（如 `check-requirement-trace` 的全域覆盖断言）**职责重复**。
    正确写法是断言**结构关系**（集合双向相等 / 域覆盖 / 序号连续），而非绝对条数。

    判定（保守，宁少报不误报）：
      - 仅看 `assert` 语句中形如 ``len(<x>) == <数字>`` 或 ``len(<x>) > <大数>`` 的比较；
      - 仅当**同一文件**内该 `len()` 实参名与需求 ID / 总数类语义相关时报告：
        实参名含 ``req_ids`` / ``requirement`` / ``section`` / ``switch`` / ``chapter`` 等，
        或断言所在文件路径含 ``requirement`` / ``registry`` / ``section``；
      - 忽略小数字（<= 3）：小集合的精确条数常为有意断言（如「两个 provider」）。
    """
    _SEMANTIC = (
        "requirement",
        "req_ids",
        "reqs",
        "section",
        "sections",
        "switch",
        "switches",
        "chapter",
        "chapters",
        "module",
        "modules",
        "domain",
        "domains",
        "panel",
        "panels",
    )
    findings: list[str] = []
    for case in cases:
        path_hint = "requirement" in str(case.path).lower() or "registry" in str(case.path).lower()
        for node in ast.walk(case.node):
            if not isinstance(node, ast.Assert):
                continue
            for cmp_node in ast.walk(node.test):
                if not isinstance(cmp_node, ast.Compare):
                    continue
                left = cmp_node.left
                if not (
                    isinstance(left, ast.Call)
                    and isinstance(left.func, ast.Name)
                    and left.func.id == "len"
                    and left.args
                ):
                    continue
                arg = left.args[0]
                arg_name = arg.id if isinstance(arg, ast.Name) else ast.unparse(arg)
                lowered = arg_name.lower()
                if not (path_hint or any(tok in lowered for tok in _SEMANTIC)):
                    continue
                for op, right in zip(cmp_node.ops, cmp_node.comparators):
                    if not isinstance(op, (ast.Eq, ast.Gt, ast.GtE)):
                        continue
                    if not isinstance(right, ast.Constant) or not isinstance(right.value, int):
                        continue
                    if right.value <= 3:
                        continue
                    findings.append(
                        f"{rel(case.path)}:{node.lineno}: 用例 {case.name} 断言硬编码会演进的总数 "
                        f"`len({arg_name}) {type(op).__name__.replace('GtE', '>=').replace('Gt', '>').replace('Eq', '==')} {right.value}`"
                        "——应改为结构关系断言（集合双向相等 / 域覆盖 / 序号连续），否则新增条目必红且职责与门禁重复"
                    )
    return findings
