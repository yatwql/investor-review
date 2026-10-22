"""检查 8：死 fixture（test 文件内定义且全仓无引用）。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


def _fixture_exposed_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """fixture 暴露名（`name=` 别名优先于函数名）；非 fixture / autouse（机制消费）返回 None。"""
    is_fixture = False
    exposed = node.name
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            pass
        elif isinstance(target, ast.Name) and target.id == "fixture":
            pass
        else:
            continue
        if isinstance(deco, ast.Call):
            if any(kw.arg == "autouse" and getattr(kw.value, "value", None) is True for kw in deco.keywords):
                return None  # autouse 由 pytest 机制自动消费，无参数引用，不判死
            for kw in deco.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    exposed = kw.value.value  # @pytest.fixture(name="别名")：用例参数引用的是别名
        is_fixture = True
    return exposed if is_fixture else None


def check_dead_fixtures(facts: dict[str, dict]) -> list[str]:
    """G：死 fixture——test 文件内定义且暴露名未被本文件任何函数参数 / usefixtures 引用（conftest 定义不判死）。"""
    findings: list[str] = []
    for key, item in facts.items():
        local = set(item.get("params", [])) | set(item.get("usefix", []))
        for name, lineno in item.get("fixtures", []):
            if name not in local:
                findings.append(f"{rel(Path(key))}:{lineno}: fixture {name} 定义后无引用（死 fixture，删除或接入用例）")
    return findings
