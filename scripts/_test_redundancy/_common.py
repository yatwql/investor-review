"""共用常量与 AST 解析原语（用例抽取、断言/打桩识别、夹具暴露名）。

八类检查共享这一层——检查模块只写判定逻辑，不重复 AST 遍历样板。
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import REPO_ROOT  # noqa: E402


_TEST_ROOT = REPO_ROOT / "src" / "test"


_LIVE_DIR = REPO_ROOT / "src" / "test" / "live"


_MOCK_ASSERT = re.compile(r"^assert_(called|any_call|has_calls|not_called)")


_PYTEST_ASSERT = frozenset({"raises", "warns", "fail", "deprecated_call"})


_SUT_ATTRS = frozenset({"_call", "_run", "fn", "r", "sut", "proc", "target", "_target"})


class TestCase(NamedTuple):
    """一个测试用例（AST 视角）。"""

    path: Path
    class_name: str
    name: str
    lineno: int
    node: ast.FunctionDef | ast.AsyncFunctionDef
    cls: ast.ClassDef | None = None
    module: ast.Module | None = None


def _iter_test_files(include_live: bool) -> list[Path]:
    files = sorted(_TEST_ROOT.rglob("test_*.py"))
    if not include_live:
        files = [p for p in files if _LIVE_DIR not in p.parents]
    return files


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def _class_attr_binding(cls: ast.ClassDef | None, attr: str) -> str | None:
    """解析类内 ``self.<attr>`` 的绑定目标（赋值式 / 方法返回式 / setUp 赋值式 / staticmethod）。

    第 3 档 setUp 解析：类体内无绑定、也无同名方法时，扫 ``setUp``/``setUpClass`` 里的
    ``self.<attr> = <值>`` 赋值，取其值的归一化 dump。这是 62 个盲区里最大的一类
    （``self.r``/``self.fn`` 在 setUp 里构造），解析后才能参与重复比对而非被跳过。
    """
    if cls is None:
        return None
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            if stmt.targets[0].id == attr:
                return _dump(stmt.value)
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == attr:
            for inner in stmt.body:
                if isinstance(inner, ast.Return) and inner.value is not None:
                    return _dump(inner.value)
            return None
    # 第 3 档：setUp / setUpClass 里的 self.<attr> = <值>
    for stmt in cls.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name not in ("setUp", "setUpClass"):
            continue
        for sub in ast.walk(stmt):
            if (
                isinstance(sub, ast.Assign)
                and len(sub.targets) == 1
                and isinstance(sub.targets[0], ast.Attribute)
                and isinstance(sub.targets[0].value, ast.Name)
                and sub.targets[0].value.id == "self"
                and sub.targets[0].attr == attr
            ):
                return _dump(sub.value)
    return None


def _method_body_hash(cls: ast.ClassDef | None, attr: str) -> str | None:
    """类内定义但无单一 return 的分支型 helper（如 ``_run``/``_call``）→ 方法体哈希。

    分支型 helper 的行为由整个方法体决定，无法压成单个 return 表达式。取「去掉
    docstring 后的方法体 AST dump 的 sha1」作为其绑定指纹：同名 helper 不同实现 →
    不同哈希 → 不误判为重复；同名同实现（继承或复制）→ 相同哈希 → 正常比对。
    """
    if cls is None:
        return None
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == attr:
            core = _strip_docstring(stmt.body)
            payload = _dump(ast.Module(body=core, type_ignores=[]))
            return f"method-body:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"
    return None


def _self_attrs(node: ast.AST) -> set[str]:
    return {
        n.attr
        for n in ast.walk(node)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
    }


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")


def _assertion_in(node: ast.AST) -> tuple[bool, bool]:
    """本节点（含嵌套语句）内是否含断言式证据 / mock 断言。"""
    has_assert = False
    has_mock = False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            has_assert = True
        elif isinstance(sub, ast.Call):
            name = _call_name(sub)
            if _MOCK_ASSERT.match(name):
                has_assert = True
                has_mock = True
            elif name.startswith("assert") or name in _PYTEST_ASSERT:
                # unittest/numpy/mock 风格：assertEqual/assertTrue/assertIsNone/assert_called_* 与 fail/raises 等
                has_assert = True
    return has_assert, has_mock


def _same_scope_helpers(case: TestCase) -> dict[str, ast.AST]:
    """本文件/本类（含模块内基类）可解析的同名辅助函数：``name -> 函数节点``。"""
    helpers: dict[str, ast.AST] = {}
    if case.module is not None:
        for stmt in case.module.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                helpers[stmt.name] = stmt
        for cls in [n for n in ast.walk(case.module) if isinstance(n, ast.ClassDef)]:
            if (
                case.cls is None
                or cls is case.cls
                or any((isinstance(b, ast.Name) and b.id == cls.name) for b in case.cls.bases)
            ):
                for stmt in cls.body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        helpers.setdefault(stmt.name, stmt)
    return helpers


def _assertions(case: TestCase) -> tuple[bool, bool]:
    """返回 (是否有断言式证据, 是否有 mock 断言)。

    断言可以落在被测用例本体，也可以落在同文件/同类（含模块内基类）的辅助方法里
    （如 ``self._assert_pairs_contain(...)`` / ``self.fail(...)``）——两种情况都算有断言。
    """
    has_assert, has_mock = _assertion_in(case.node)
    if not has_assert:
        helpers = _same_scope_helpers(case)
        for name in {_call_name(c) for c in ast.walk(case.node) if isinstance(c, ast.Call)}:
            helper = helpers.get(name)
            if helper is not None and helper is not case.node:
                helper_assert, helper_mock = _assertion_in(helper)
                if helper_assert:
                    has_assert = True
                    has_mock = has_mock or helper_mock
                    break
    return has_assert, has_mock


def _patch_targets(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str]]:
    """装饰器里的 ``@patch("a.b.c")`` → [(mock 参数名, 目标点分路径)]（按装饰器顺序对应参数尾）。"""
    targets: list[tuple[str, str]] = []
    params = [a.arg for a in node.args.args if a.arg != "self"]
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call) or not dec.args:
            continue
        func = dec.func
        fname = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if fname != "patch":
            continue
        arg = dec.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            targets.append(("", arg.value))
    # patch 装饰器自下而上注入 → 参数表末尾起倒序对应
    for idx, (_, target) in enumerate(targets):
        param_index = len(params) - 1 - idx
        targets[idx] = (params[param_index] if 0 <= param_index < len(params) else "", target)
    return targets


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _mock_return_literals(node: ast.AST, mock_name: str) -> set[str]:
    """``<mock>.return_value = <字面量>`` 收集（只认单层，``mock.now.return_value`` 不算）。"""
    values: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign) or len(sub.targets) != 1:
            continue
        tgt = sub.targets[0]
        if (
            isinstance(tgt, ast.Attribute)
            and tgt.attr == "return_value"
            and isinstance(tgt.value, ast.Name)
            and tgt.value.id == mock_name
            and isinstance(sub.value, ast.Constant)
        ):
            values.add(repr(sub.value.value))
    return values


def _asserted_literals(node: ast.AST) -> set[str]:
    """断言里出现的字面量（assert x == lit / assertEqual(x, lit)）。"""
    literals: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert) and isinstance(sub.test, ast.Compare):
            for comp in sub.test.comparators:
                if isinstance(comp, ast.Constant):
                    literals.add(repr(comp.value))
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr
            in (
                "assertEqual",
                "assertEquals",
            )
        ):
            for arg in sub.args[1:]:
                if isinstance(arg, ast.Constant):
                    literals.add(repr(arg.value))
    return literals


def cases_in_module(path: Path, tree: ast.Module) -> list[TestCase]:
    """从单个已解析模块中提取全部测试用例（含所在类）。

    单次 BFS：`ast.walk` 层序保证类先于其直属语句被访问，类登记与用例提取合并为一遍。
    """
    cls_of: dict[ast.AST, ast.ClassDef] = {}
    cases: list[TestCase] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                cls_of[stmt] = node
            continue
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")):
            continue
        cls = cls_of.get(node)
        cases.append(
            TestCase(
                path=path,
                class_name=cls.name if cls else "",
                name=node.name,
                lineno=node.lineno,
                node=node,
                cls=cls,
                module=tree,
            )
        )
    return cases
