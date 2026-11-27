"""检查 10：patch 面打在 re-export 上（真实调用点可能不在被 patch 的模块）。

测试长期写 ``patch("<入口模块>.<符号>")``，而该符号在入口模块里**只是被 import 进来**的
（re-export 面）：生产侧的调用点在持有实现的模块里，patch 入口属性对真实调用点毫无影响，
用例于是「绿而生产走真实绑定」。同时为了迁就这类 patch，生产代码被迫保留未用 import /
re-export 并加 ``# noqa: F401``——本规则即为拦住这一形态而设。

判定（AST 静态，不执行测试）：
  1. 从测试文件里取 patch 目标——``patch("a.b.c")`` / ``patch.object(<模块>, "name")`` /
     ``monkeypatch.setattr(<模块>|"a.b.c", ...)``（含 ``mock.`` / ``mocker.`` 前缀形态）；
     装饰器与函数体调用同窗扫描，``<模块>`` 经测试文件的 import 表解析成点分路径。
  2. 把点分路径解析成（生产模块文件, 属性名）：从右往左缩，取第一个能在包根或
     ``src/python``（扁平入 sys.path 的形态）下命中的模块文件；属性链深于模块层
     （如 ``pkg.mod.Class.method``）不静态判定，跳过。
  3. 若该属性名在被解析出的模块里**只由 import 带入**（from-import / import-as，或该模块
     有 ``from x import *``），且模块体内没有任何其它引用（不是本模块定义的函数/类/赋值，
     也没被读取）→ 报 finding：patch 打在 re-export 面。

判据是「纯 re-export 面」而非「被 import 过」：模块自己 import 后真的用了（``get_config``
被本模块函数调用）属**合法** patch 面，不报。属合法场景（如刻意验证门面的导出同名）走
例外表登记：表与定位键 schema 见 `_shared.exceptions` 的 `test-redundancy` 表（`patch-surface`
规则），字段 owner / reason / expiry / replacement 由该设施统一校验。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import REPO_ROOT, rel
from _shared.exceptions import (
    ExceptionTable,
    load_exception_table,
    table_spec,
)


#: 生产模块搜索根：包形态（`src.python.x`）与 `src/python` 入 sys.path 后的扁平形态（`x`）
_MODULE_ROOTS = (REPO_ROOT, REPO_ROOT / "src" / "python")


#: 例外表路径与规则 schema 取自 `_shared.exceptions` 的登记表（`test-redundancy` 表）
_TABLE_SPEC = table_spec("test-redundancy")

#: 例外表路径（与被检入口同目录，便于随检查一起评审）
EXCEPTIONS_FILE = _TABLE_SPEC.path

#: 例外表里本检查的规则键
RULE_KEY = "patch-surface"


def _chain_src(node: ast.AST) -> str:
    """``mock.patch.object`` 这类接收者链的源文本（解析不了返空串）。"""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return ""
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _string_arg(call: ast.Call, index: int) -> str | None:
    if len(call.args) <= index:
        return None
    arg = call.args[index]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _test_module_imports(tree: ast.Module) -> dict[str, str]:
    """测试模块内「本地名 → 点分模块路径」（供 ``<别名>.<属性>`` 与 ``<别名>`` 形态解析）。

    相对导入（``from .helpers import x``）不解析：它指测试自己的辅助模块，不属 re-export 面。
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    aliases[head] = head
        elif isinstance(node, ast.ImportFrom):
            if node.module is None or node.level:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _dotted_of(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """把 ``<别名>`` / ``<别名>.<属性>`` 解析成点分路径（解析不出返 None）。"""
    chain = _chain_src(node)
    if not chain:
        return None
    head, _, rest = chain.partition(".")
    base = aliases.get(head)
    if base is None:
        return None
    return f"{base}.{rest}" if rest else base


def _call_target(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """一次调用是否构成 patch 面目标，是则返点分路径。"""
    chain = _chain_src(call.func)
    if not chain:
        return None
    # patch("a.b.c") / mock.patch("a.b.c") / mocker.patch("a.b.c")
    if chain == "patch" or chain.endswith(".patch"):
        return _string_arg(call, 0)
    # patch.object(<模块|"a.b">, "name") / mock.patch.object(...)
    if chain == "patch.object" or chain.endswith(".patch.object"):
        owner = call.args[0] if call.args else None
        name = _string_arg(call, 1)
        if owner is None or not name:
            return None
        if isinstance(owner, ast.Constant) and isinstance(owner.value, str):
            return f"{owner.value}.{name}"
        base = _dotted_of(owner, aliases)
        return f"{base}.{name}" if base else None
    # monkeypatch.setattr(<模块|"a.b.c">, <新值>) / monkeypatch.setattr("a.b.c", "name", <新值>)
    if chain.endswith("setattr") and "monkeypatch" in chain.split(".")[0].lower():
        if not call.args:
            return None
        target = call.args[0]
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            return target.value
        name = _string_arg(call, 1)
        if not name:
            return None
        base = _dotted_of(target, aliases)
        return f"{base}.{name}" if base else None
    return None


def extract_patch_targets(tree: ast.Module) -> list[list]:
    """文件内事实：``[[行号, 点分目标], ...]``（装饰器与调用同窗，重复目标只取首个）。"""
    aliases = _test_module_imports(tree)
    seen: set[str] = set()
    targets: list[list] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _call_target(node, aliases)
        if dotted and dotted not in seen:
            seen.add(dotted)
            targets.append([node.lineno, dotted])
    return targets


def resolve_target(dotted: str) -> tuple[Path, str] | None:
    """点分路径 → （目标模块文件, 属性名）；解析不出（含属性链深于模块层）返 None。"""
    parts = dotted.split(".")
    for split in range(len(parts) - 1, 0, -1):
        prefix = parts[:split]
        for root in _MODULE_ROOTS:
            candidates = (root.joinpath(*prefix).with_suffix(".py"), root.joinpath(*prefix, "__init__.py"))
            for candidate in candidates:
                if not candidate.is_file():
                    continue
                rest = parts[split:]
                return (candidate, rest[0]) if len(rest) == 1 else None
    return None


def _imported_names(tree: ast.Module) -> tuple[set[str], bool]:
    """模块里由 import 带入的名字集合 + 是否含 ``from x import *``。"""
    names: set[str] = set()
    star = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    star = True
                else:
                    names.add(alias.asname or alias.name)
    return names, star


def _bound_or_read_names(tree: ast.Module) -> set[str]:
    """模块体内「自己定义 / 被读取」的名字（含参数名，保守取多不取少）。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


class _ModuleFacts(NamedTuple):
    """一个被 patch 的目标模块的静态事实（按文件缓存，跨用例复用）。"""

    imported: set[str]
    has_star: bool
    bound_or_read: set[str]
    declared_all: set[str]


def _declared_all(tree: ast.Module) -> set[str]:
    """模块顶层 ``__all__`` 声明的名字（含 ``__all__ += [...]`` 形式；解析不出则空集）。"""
    declared: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AugAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.AnnAssign):
            if node.value is None:
                continue
            targets, value = [node.target], node.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        try:
            items = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
        if not isinstance(items, (list, tuple)):
            continue
        declared.update(str(item) for item in items)
    return declared


def _module_facts(module_file: Path, cache: dict[Path, _ModuleFacts]) -> _ModuleFacts:
    facts = cache.get(module_file)
    if facts is None:
        tree = ast.parse(module_file.read_text(encoding="utf-8"))
        imported, has_star = _imported_names(tree)
        facts = _ModuleFacts(imported, has_star, _bound_or_read_names(tree), _declared_all(tree))
        cache[module_file] = facts
    return facts


def _public_export_surface(module_file: Path, name: str, cache: dict[Path, _ModuleFacts]) -> bool:
    """该目标是否落在「刻意维持的公开导入面」：包门面 ``__init__.py`` 或 ``__all__`` 声明项。

    这两种面本就是设计上的统一入口（调用方按包门面导入，``__all__`` 是明确对外承诺），
    在其上 patch 属公开 API 面的合法替身，不属本检查要抓的「为测试保留的死 import」。
    """
    return module_file.name == "__init__.py" or name in _module_facts(module_file, cache).declared_all


def _reexport_only(module_file: Path, name: str, cache: dict[Path, _ModuleFacts]) -> bool:
    """该模块里的 ``name`` 是否「只由 import 带入、模块体内无任何其它引用」。"""
    facts = _module_facts(module_file, cache)
    if facts.has_star:
        # 星号导入带来的名字不可枚举，按「可能由 import 带入」处理
        return name not in facts.bound_or_read
    return name in facts.imported and name not in facts.bound_or_read


def load_exceptions() -> ExceptionTable:
    """读 ``patch-surface`` 例外（文件缺失视为无例外，解析失败落在 ``load_error``）。"""
    return load_exception_table(EXCEPTIONS_FILE, _TABLE_SPEC.rules)


def check_patch_surface(
    targets_by_file: dict[Path, list[list]],
    exceptions: ExceptionTable | None = None,
) -> list[str]:
    """K：patch 打在 re-export 面——目标属性在被 patch 的模块里只由 import 带入。

    Args:
        targets_by_file: ``{测试文件: [[行号, 点分目标], ...]}``（由本模块的
            :func:`extract_patch_targets` 逐文件产出，经事实缓存传递）。
        exceptions: 例外表；缺省读 ``_test_redundancy_exceptions.json``。
    """
    table = exceptions if exceptions is not None else load_exceptions()
    findings: list[str] = []
    module_cache: dict[Path, _ModuleFacts] = {}
    for path, targets in sorted(targets_by_file.items()):
        for lineno, dotted in targets:
            resolved = resolve_target(dotted)
            if resolved is None:
                continue
            module_file, name = resolved
            if _public_export_surface(module_file, name, module_cache):
                continue
            if not _reexport_only(module_file, name, module_cache):
                continue
            if table.is_excepted(RULE_KEY, dotted):
                continue
            findings.append(
                f"{rel(path)}:{lineno}: patch 打在 re-export 面「{dotted}」——{rel(module_file)} 里的 {name} 仅由 import"
                " 带入、模块体内无其它引用，真实调用点很可能不在该模块（用例绿而生产走原实现）；"
                "应改 patch 到该符号真实被使用的模块，或登记例外"
            )
    return findings


def audit_exceptions(table: ExceptionTable) -> list[str]:
    """例外表自审：字段齐全 + 未到期 + 仍命中违规（防长期免死金牌）。"""
    audit = table.audit(RULE_KEY)
    findings: list[str] = [table.load_error] if table.load_error else []
    findings += audit.findings
    findings += table.stale_findings(audit)
    return findings
