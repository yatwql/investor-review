"""检查 4：自证用例（patch 被测函数后又把 return_value 断言回原值）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
    _patch_targets,
    _called_names,
    _asserted_literals,
    _mock_return_literals,
)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import rel  # noqa: E402


def check_self_fulfilling(cases: list[TestCase]) -> list[str]:
    findings: list[str] = []
    for case in cases:
        targets = _patch_targets(case.node)
        if not targets:  # 绝大多数用例无 @patch 装饰器：早退，免两次全量 walk
            continue
        called = _called_names(case.node)
        asserted = _asserted_literals(case.node)
        if not called or not asserted:
            continue
        for mock_name, target in targets:
            short = target.split(".")[-1]
            if short not in called:
                continue
            mock_returns = _mock_return_literals(case.node, mock_name) if mock_name else set()
            if mock_returns & asserted:
                findings.append(
                    f"{rel(case.path)}:{case.lineno}: 用例 {case.name} patch 了被测函数 {target} 又把其 return_value 断言回原值（{sorted(mock_returns & asserted)}），断言恒真"
                )
    return findings
