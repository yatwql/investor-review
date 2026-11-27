"""浮点求和口径单源守卫（check-code-traces 的 FLOATSUM 扫描支路）。

纪律源：浮点的**均值/方差**求和一律走 `math.fsum`——它做正确舍入，结果只取决于
元素集合、与相加顺序和解释器版本无关；内建 `sum()` 对浮点的累加策略随解释器演进
（3.11 朴素顺序累加 → 3.12 起改用补偿求和），同一份数据在两个解释器上末位可能
不同。后果不是「最后一位不好看」，而是**判据翻转**：零方差序列在朴素累加下会累出
极小的非零残差，`ssx > 0` 这类判定于是通过，算出天文数字的标准误（Beta 标准误
已因此暴雷一次），且只在一个解释器版本上复现。

判定（AST 静态，只看生产面 `src/python/**` 与 `scripts/**`）：

  1. **均值模式**：内建 `sum(...)` 直接充当除法的被除数（`sum(xs) / len(xs)`）——
     求和结果随即被当成均值使用。
  2. **偏差模式**：内建 `sum(...)` 的实参是推导式/字面量序列，且元素里出现 `** 2`
     或减法——平方和 / 离差和 / 协方差这些统计量的公有形态。

不报（避免把整数计数与已收敛的写法一起扫进来）：

  - 实参可静态判定为整数（整数字面量、`len()`/`int()` 及其加减乘组合）——整数加法
    在任意解释器上都是精确的，无需 `fsum`；`sum(1 for x in ...)` 这类计数同理。
  - 已被 `math.fsum(...)`（或任意 `*.fsum(...)`）包裹——那就是目标形态本身。
  - `sum` 在**任一外围作用域**被重新绑定（赋值/参数/`import ... as sum`）——此时
    该名字不是内建函数，判定不成立。

确属整数求均值/方差、但形态上无法静态证明是整数的（例如对 `bool` 命中列表求和），
在 `scripts/_code_traces_exceptions.json` 的 `float-sum` 规则键下登记：条目按
`<仓库相对路径>::<外围限定名>::<sum 调用源码>` 定位（不用行号，改写行不会让登记失效），字段与
`_test_redundancy_exceptions.json` 同风格（owner / reason / expiry / replacement），
并由 :func:`audit_exceptions` 自审（字段齐全 / 未到期 / 仍命中违规）。
"""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path
from typing import NamedTuple

from _shared.checklib import repo_relative_posix as _rel_posix

from _traces_code.config import REPO_ROOT

#: 守卫面（生产代码 + 脚本；`src/test` 由测试冗余检查管辖，不在本规则内）
_NUMERIC_SURFACE = ("src/python/", "scripts/")

#: 例外表路径（与检查入口同目录，便于随检查一起评审）
EXCEPTIONS_FILE = Path(__file__).resolve().parents[1] / "_code_traces_exceptions.json"

#: 例外表里的规则键（一个键一族例外，便于逐族到期与追责）
RULE_KEY = "float-sum"

#: 例外条目必填字段（缺一即无法追责或无法自动到期）
REQUIRED_FIELDS = ("owner", "reason", "expiry", "replacement")

_EXPIRY_LEN = len("YYYY-MM-DD")

#: 判定分类 → 提示语（分类只用于 finding 文案，两者都进 CODE 桶）
_KIND_MEAN = "浮点均值用内建 sum() 求和"
_KIND_DEVIATION = "浮点离差/平方和用内建 sum() 求和"

#: 内建作用域节点：`sum` 是否被重绑定按**逐个外围作用域**判，不整文件连坐
_SCOPE_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

#: 整数结果的白名单调用（返回值必为 int）
_INT_CALLS = frozenset({"len", "int"})

#: 整数封闭的算术运算（两侧都是整数时结果为整数）
_INT_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)


class _ExceptionTable(NamedTuple):
    """例外表：允许的定位键集合 + 原始条目 + 读表失败原因。"""

    allowed: set[str]
    raw: list[dict]
    load_error: str = ""


def _scope_bindings(scope: ast.AST) -> set[str]:
    """某作用域**直接**绑定的名字集合（不进入嵌套函数/类体，只收它们的名字）。"""

    names: set[str] = set()

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
                continue
            if isinstance(child, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                # 推导式/lamdba 自带作用域：其变量既不绑定到外层，也不遮蔽外层
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                names.add(child.id)
            elif isinstance(child, ast.alias):
                names.add((child.asname or child.name).split(".")[0])
            elif isinstance(child, ast.arg):
                names.add(child.arg)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                names.add(child.name)
            visit(child)

    visit(scope)
    return names


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """子节点 → 父节点（判定「调用处在什么位置」需要向上看）。"""
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _enclosing_sum_is_shadowed(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """`sum` 是否在外围任一作用域被重新绑定（是则不是内建函数，不判）。"""
    cur = parents.get(call)
    while cur is not None:
        if isinstance(cur, _SCOPE_NODES) and "sum" in _scope_bindings(cur):
            return True
        cur = parents.get(cur)
    return False


def _wrapped_in_fsum(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """该 `sum` 调用是否已被 `math.fsum(...)`（或任意 `*.fsum(...)`）包裹。"""
    cur = parents.get(call)
    while cur is not None:
        if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Attribute) and cur.func.attr == "fsum":
            return True
        cur = parents.get(cur)
    return False


def _is_integer_operand(node: ast.AST) -> bool:
    """该表达式是否可静态判定为整数（整数字面量 / `len()`、`int()` / 其整数封闭运算）。"""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int)  # bool 也是 int，计数求和不涉浮点
    if isinstance(node, ast.Call):
        func = node.func
        return isinstance(func, ast.Name) and func.id in _INT_CALLS
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, _INT_BINOPS) and _is_integer_operand(node.left) and _is_integer_operand(node.right)
    return False


def _is_integer_sequence(node: ast.AST) -> bool:
    """`sum()` 的实参是否整体是整数序列（字面量序列全为整数 / 推导式元素为整数）。"""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return bool(node.elts) and all(_is_integer_operand(elt) for elt in node.elts)
    if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
        return _is_integer_operand(node.elt)
    return False


def _summed_elements(node: ast.AST) -> list[ast.expr]:
    """`sum()` 实参里**被逐项累加**的表达式（推导式元素或字面量序列各项）。"""
    if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
        return [node.elt]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return list(node.elts)
    return []


def _is_deviation_expr(node: ast.AST) -> bool:
    """元素表达式是否为离差/平方和形态：出现 `** 2` 或减法。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Pow):
            exp = sub.right
            if isinstance(exp, ast.Constant) and exp.value == 2:
                return True
        elif isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Sub):
            return True
    return False


def _sum_kind(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> str | None:
    """该 `sum()` 调用属于哪类均值/方差模式（不属任何一类返 None）。"""
    parent = parents.get(call)
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
        return _KIND_MEAN
    if call.args and any(_is_deviation_expr(elt) for elt in _summed_elements(call.args[0])):
        return _KIND_DEVIATION
    return None


def _enclosing_qualname(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """最近的外围函数/类限定名（例外定位键用；同一函数里重复出现的同形调用合并计一条）。"""
    parts: list[str] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(cur.name)
        cur = parents.get(cur)
    return ".".join(reversed(parts)) or "<module>"


def _call_source(call: ast.Call) -> str:
    """`sum(...)` 调用的单行源码（例外定位键与 finding 文案共用，空白归一）。"""
    try:
        return " ".join(ast.unparse(call).split())
    except (AttributeError, ValueError):  # 节点无法反解（unparse 缺字段/节点损坏）
        return "sum(...)"


def _float_sum_hits(fpath: Path) -> list[tuple[int, str, str]]:
    """单文件的**原始**命中：[(行号, 分类说明, 例外定位键)]（不套例外表）。

    例外表按定位键过滤放在 :func:`_scan_float_sum`，故本函数可被例外自审复用：
    自审要问的正是「这个已登记的点现在还会不会命中」。
    """
    if fpath.suffix.lower() != ".py":
        return []
    try:
        tree = ast.parse(fpath.read_text(encoding="utf-8-sig"), filename=str(fpath))
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        return []

    rel_path = _rel_posix(fpath)
    parents = _parents(tree)
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "sum"):
            continue
        kind = _sum_kind(node, parents)
        if kind is None:
            continue
        if node.args and _is_integer_sequence(node.args[0]):
            continue
        if _wrapped_in_fsum(node, parents) or _enclosing_sum_is_shadowed(node, parents):
            continue
        hits.append((node.lineno, kind, f"{rel_path}::{_enclosing_qualname(node, parents)}::{_call_source(node)}"))
    return hits


_HITS_CACHE: dict[str, list[tuple[int, str, str]]] = {}


def _cached_hits(fpath: Path) -> list[tuple[int, str, str]]:
    """按（路径, 尺寸, mtime）记忆化单文件原始命中（例外自审会重跑同一批文件）。"""
    try:
        st = fpath.stat()
        key = f"{fpath.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        return _float_sum_hits(fpath)
    cached = _HITS_CACHE.get(key)
    if cached is None:
        cached = _float_sum_hits(fpath)
        _HITS_CACHE[key] = cached
    return cached


def load_exceptions(path: Path | None = None) -> _ExceptionTable:
    """读 `float-sum` 例外（文件缺失视为无例外，解析失败落在 `load_error`）。"""
    path = path or EXCEPTIONS_FILE
    if not path.exists():
        return _ExceptionTable(set(), [])
    try:
        raw_table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _ExceptionTable(set(), [], f"{_rel_posix(path)} 无法解析：{exc}")
    raw = [entry for entry in raw_table.get(RULE_KEY, []) if isinstance(entry, dict)]
    return _ExceptionTable({str(entry.get("name", "")) for entry in raw}, raw)


def _scan_float_sum(
    fpath: Path,
    exceptions: _ExceptionTable | None = None,
    repo_root: Path | None = None,
) -> list[tuple[int, str, str, str]]:
    """扫描单文件的浮点均值/方差求和，返回 [(行号, 分类, 说明, 调用片段)]。

    ``repo_root`` 只用于判定守卫面（`src/python/**` 与 `scripts/**`），合成目录的单测
    要能按自己的根判豁免。
    """
    root = repo_root or REPO_ROOT
    if fpath.suffix.lower() != ".py" or not _rel_posix(fpath, root).startswith(_NUMERIC_SURFACE):
        return []
    table = exceptions if exceptions is not None else load_exceptions()
    hits: list[tuple[int, str, str, str]] = []
    for lineno, kind, key in _cached_hits(fpath):
        if key in table.allowed:
            continue
        snippet = key.split("::", 2)[2]
        hits.append(
            (
                lineno,
                "FLOATSUM",
                f"{kind}（朴素累加在 3.11/3.12 末位不一致，零方差判定会失效）→ 改用 math.fsum(...)",
                snippet[:120],
            )
        )
    return hits


def audit_exceptions(table: _ExceptionTable, repo_root: Path | None = None) -> list[str]:
    """例外表自审：字段齐全 + expiry 合法未到期 + 仍命中违规（防长期免死金牌）。"""
    root = repo_root or REPO_ROOT
    findings: list[str] = []
    if table.load_error:
        findings.append(table.load_error)
    today = date.today()
    for entry in table.raw:
        name = str(entry.get("name", ""))
        where = f"{_rel_posix(EXCEPTIONS_FILE)} {RULE_KEY}::{name}"
        missing = [field for field in REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
        if missing:
            findings.append(f"[exception-metadata] {where} 缺少字段 {'/'.join(missing)}")
            continue
        expiry_raw = str(entry["expiry"]).strip()
        if not _is_iso_date(expiry_raw):
            findings.append(f"[exception-metadata] {where} expiry 须为 YYYY-MM-DD，实为「{expiry_raw}」")
            continue
        if date.fromisoformat(expiry_raw) < today:
            findings.append(f"[exception-expiry] {where} 已于 {expiry_raw} 到期，须删除例外或续期并复核理由")
            continue
        rel_path, _, _rest = name.partition("::")
        target = root / rel_path
        if not target.is_file():
            findings.append(f"[exception-stale] {where} 目标文件不存在，须删除该例外")
            continue
        if name not in {key for _lineno, _kind, key in _cached_hits(target)}:
            findings.append(f"[exception-stale] {where} 未命中任何违规（规则已修复），须删除该例外")
    return findings


def _is_iso_date(text: str) -> bool:
    try:
        return len(text) == _EXPIRY_LEN and date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False
