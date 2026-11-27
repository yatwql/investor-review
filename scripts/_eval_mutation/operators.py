"""内置变异器的算子层：AST 定位 + 单点文本替换（纯函数，不读写文件）。

四类算子（与 `targets.OPERATORS` 一一对应）：

  - 比较取反   `<`↔`<=` / `>`↔`>=` / `==`↔`!=` / `in`↔`not in`
  - 布尔取反   `and`↔`or` / `not x` → `(x)`
  - 算术替换   `+`↔`-` / `*`↔`/`
  - 返回值替换 `return X` → `return None`（X 非 None 常量时才变）

**为什么是「AST 定位 + 原文单点替换」而不是 `ast.unparse` 整文件重写**：整文件重写会连带重排
注释、引号风格与换行，变异体与原文的差异不再可读（判读 survived 时看不出到底变了什么），也
容易把一处变异误读成整文件变化。故只用 AST 拿到操作符两侧操作数的位置，就地替换那一段文本；
唯一例外是 `not x`（要把 `not ` 一起削掉，故用 `ast.unparse` 重排操作数本身）。

失败即跳过（宁可少产一个变异体，也不写坏源码）：操作符原文与预期不符、跨行书写无法确定
边界、段落定位越界——一律返回空，不猜。

`col_offset` 在 CPython 里是**UTF-8 字节**偏移而不是字符偏移（源码含中文注释时会分叉），
故所有位置运算都在 UTF-8 字节上做，只在进出时编解码。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

#: 比较算子 → (取反后的算子, 原文, 取反后的原文)
_COMPARE_FLIPS: dict[type[ast.cmpop], tuple[type[ast.cmpop], str, str]] = {
    ast.Lt: (ast.LtE, "<", "<="),
    ast.LtE: (ast.Lt, "<=", "<"),
    ast.Gt: (ast.GtE, ">", ">="),
    ast.GtE: (ast.Gt, ">=", ">"),
    ast.Eq: (ast.NotEq, "==", "!="),
    ast.NotEq: (ast.Eq, "!=", "=="),
    ast.In: (ast.NotIn, "in", "not in"),
    ast.NotIn: (ast.In, "not in", "in"),
}

#: 布尔算子 → 原文（取反即两者互换）
_BOOL_FLIPS: dict[type[ast.boolop], tuple[type[ast.boolop], str, str]] = {
    ast.And: (ast.Or, "and", "or"),
    ast.Or: (ast.And, "or", "and"),
}

#: 算术算子 → 原文（取反即两者互换）
_ARITH_FLIPS: dict[type[ast.operator], tuple[type[ast.operator], str, str]] = {
    ast.Add: (ast.Sub, "+", "-"),
    ast.Sub: (ast.Add, "-", "+"),
    ast.Mult: (ast.Div, "*", "/"),
    ast.Div: (ast.Mult, "/", "*"),
}

#: 算子类别标签（= `targets.OPERATORS` 的同名口径）
OPERATOR_COMPARE = "比较取反"
OPERATOR_BOOL = "布尔取反"
OPERATOR_ARITH = "算术替换"
OPERATOR_RETURN = "返回值替换"


@dataclass(frozen=True)
class Mutant:
    """一个待执行的变异体：一条变异后的整文件文本 + 供判读定位的坐标。"""

    path: str
    line: int
    column: int
    operator: str
    detail: str
    source: str

    @property
    def label(self) -> str:
        """判读用的一行标识：`路径:行:列 算子 变更内容`（列不可省：同一行可有多个同类变异点）。"""
        return f"{self.path}:{self.line}:{self.column} {self.operator} {self.detail}"


def _line_starts(data: bytes) -> list[int]:
    """每行首字节的绝对偏移（行号 1-based，与 `ast` 的 lineno 同口径）。"""
    starts = [0]
    for index, byte in enumerate(data):
        if byte == 0x0A:
            starts.append(index + 1)
    return starts


def _absolute(starts: list[int], line: int, column: int) -> int | None:
    """(行, 列) → 绝对字节偏移；行号越界返回 None。"""
    if line < 1 or line > len(starts):
        return None
    return starts[line - 1] + column


def span_text(source: str, start: tuple[int, int], end: tuple[int, int]) -> str | None:
    """取两坐标之间的原文（含跨行）；坐标越界或起止颠倒返回 None。"""
    data = source.encode("utf-8")
    starts = _line_starts(data)
    begin = _absolute(starts, start[0], start[1])
    finish = _absolute(starts, end[0], end[1])
    if begin is None or finish is None or begin > finish:
        return None
    return data[begin:finish].decode("utf-8")


def splice(source: str, start: tuple[int, int], end: tuple[int, int], replacement: str) -> str | None:
    """把 `[start, end)` 这段原文换成 `replacement`，其余字节原样保留；坐标不可用时返回 None。"""
    data = source.encode("utf-8")
    starts = _line_starts(data)
    begin = _absolute(starts, start[0], start[1])
    finish = _absolute(starts, end[0], end[1])
    if begin is None or finish is None or begin > finish:
        return None
    return (data[:begin] + replacement.encode("utf-8") + data[finish:]).decode("utf-8")


def _node_span(node: ast.AST) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """节点的 [起, 止) 坐标（缺 `end_lineno` 等位置信息时返回 None）。"""
    start_line = getattr(node, "lineno", None)
    start_col = getattr(node, "col_offset", None)
    end_line = getattr(node, "end_lineno", None)
    end_col = getattr(node, "end_col_offset", None)
    if start_line is None or start_col is None or end_line is None or end_col is None:
        return None
    return (start_line, start_col), (end_line, end_col)


def _between(left: ast.AST, right: ast.AST) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """左操作数末尾到右操作数开头的坐标（操作符就夹在这中间）；跨行则放弃。"""
    left_end = _node_span(left)
    right_span = _node_span(right)
    if left_end is None or right_span is None:
        return None
    start = left_end[1]
    end = right_span[0]
    if start[0] != end[0]:
        return None  # 操作符与操作数分处两行：边界不确定，跳过
    return start, end


def _flip_between(
    source: str,
    left: ast.AST,
    right: ast.AST,
    expected: str,
    replacement: str,
) -> tuple[str, tuple[int, int]] | None:
    """把左右操作数之间的操作符从 `expected` 换成 `replacement`（原文须严格匹配）。"""
    span = _between(left, right)
    if span is None:
        return None
    raw = span_text(source, *span)
    if raw is None or raw.strip() != expected:
        return None  # 原文与预期算子不符（含 `not  in` 之类变体）：不猜，跳过
    mutated = splice(source, span[0], span[1], f" {replacement} ")
    if mutated is None:
        return None
    return mutated, span[0]


def _compare_mutants(path: str, source: str, node: ast.Compare) -> list[Mutant]:
    mutants: list[Mutant] = []
    operands = [node.left, *node.comparators]
    for index, op in enumerate(node.ops):
        flip = _COMPARE_FLIPS.get(type(op))
        if flip is None:
            continue
        _, original_text, flipped_text = flip
        changed = _flip_between(source, operands[index], operands[index + 1], original_text, flipped_text)
        if changed is None:
            continue
        mutated, position = changed
        mutants.append(
            Mutant(
                path=path,
                line=position[0],
                column=position[1],
                operator=OPERATOR_COMPARE,
                detail=f"{original_text} → {flipped_text}",
                source=mutated,
            )
        )
    return mutants


def _bool_mutants(path: str, source: str, node: ast.BoolOp) -> list[Mutant]:
    mutants: list[Mutant] = []
    flip = _BOOL_FLIPS.get(type(node.op))
    if flip is None or len(node.values) < 2:
        return mutants
    _, original_text, flipped_text = flip
    for index in range(len(node.values) - 1):
        changed = _flip_between(source, node.values[index], node.values[index + 1], original_text, flipped_text)
        if changed is None:
            continue
        mutated, position = changed
        mutants.append(
            Mutant(
                path=path,
                line=position[0],
                column=position[1],
                operator=OPERATOR_BOOL,
                detail=f"{original_text} → {flipped_text}",
                source=mutated,
            )
        )
    return mutants


def _arithmetic_mutants(path: str, source: str, node: ast.BinOp) -> list[Mutant]:
    flip = _ARITH_FLIPS.get(type(node.op))
    if flip is None:
        return []
    _, original_text, flipped_text = flip
    changed = _flip_between(source, node.left, node.right, original_text, flipped_text)
    if changed is None:
        return []
    mutated, position = changed
    return [
        Mutant(
            path=path,
            line=position[0],
            column=position[1],
            operator=OPERATOR_ARITH,
            detail=f"{original_text} → {flipped_text}",
            source=mutated,
        )
    ]


def _not_mutant(path: str, source: str, node: ast.UnaryOp) -> list[Mutant]:
    """`not x` → `(x)`：整段替换（要用 unparse 重新拼操作数，故只有这一处不保留原文格式）。"""
    if not isinstance(node.op, ast.Not):
        return []
    span = _node_span(node)
    if span is None:
        return []
    replacement = f"({ast.unparse(node.operand)})"
    mutated = splice(source, span[0], span[1], replacement)
    if mutated is None:
        return []
    return [
        Mutant(
            path=path,
            line=span[0][0],
            column=span[0][1],
            operator=OPERATOR_BOOL,
            detail="not → 削除",
            source=mutated,
        )
    ]


def _return_mutant(path: str, source: str, node: ast.Return) -> list[Mutant]:
    """`return X` → `return None`（X 本身就是 None 常量时不变——那不是变异体）。"""
    value = node.value
    if value is None:
        return []
    if isinstance(value, ast.Constant) and value.value is None:
        return []
    span = _node_span(value)
    if span is None:
        return []
    mutated = splice(source, span[0], span[1], "None")
    if mutated is None:
        return []
    return [
        Mutant(
            path=path,
            line=span[0][0],
            column=span[0][1],
            operator=OPERATOR_RETURN,
            detail="返回值 → None",
            source=mutated,
        )
    ]


def iter_mutants(path: str, source: str) -> list[Mutant]:
    """枚举一个源文件里的全部单点变异体（按行、列、算子排序，结果确定可复现）。

    `source` 必须是可解析的整文件文本（解析失败直接抛 `SyntaxError`，由调用方如实报出）。
    """
    tree = ast.parse(source)
    mutants: list[Mutant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            mutants.extend(_compare_mutants(path, source, node))
        elif isinstance(node, ast.BoolOp):
            mutants.extend(_bool_mutants(path, source, node))
        elif isinstance(node, ast.BinOp):
            mutants.extend(_arithmetic_mutants(path, source, node))
        elif isinstance(node, ast.UnaryOp):
            mutants.extend(_not_mutant(path, source, node))
        elif isinstance(node, ast.Return):
            mutants.extend(_return_mutant(path, source, node))
    return sorted(mutants, key=lambda mutant: (mutant.line, mutant.column, mutant.operator, mutant.detail))
