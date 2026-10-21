"""检查 3：完全重复用例（函数体 + 参数 + 装饰器 AST 归一化一致）。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
    _self_attrs,
    _SUT_ATTRS,
    _class_attr_binding,
    _method_body_hash,
    _strip_docstring,
    _dump,
)

import ast
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import rel  # noqa: E402


def body_signature(case: TestCase) -> str | None:
    """归一化指纹；含无法解析的 self 间接调用时返回 None（跳过比对，避免并行覆盖误报）。

    三档绑定解析：类体赋值 / 方法返回值 / setUp 赋值（第 1、3 档）；无单一 return
    的分支型 helper 取方法体哈希（第 2 档扩展）。三档均失败才返回 None 跳过。
    """
    attrs = _self_attrs(case.node) & _SUT_ATTRS
    bindings: list[str] = []
    for attr in sorted(attrs):
        resolved = _class_attr_binding(case.cls, attr)
        if resolved is None:
            resolved = _method_body_hash(case.cls, attr)
        if resolved is None:
            return None
        bindings.append(f"{attr}={resolved}")
    core = _strip_docstring(case.node.body)
    params = [a.arg for a in case.node.args.args]
    decorators = [_dump(d) for d in case.node.decorator_list]
    payload = f"{_dump(ast.Module(body=core, type_ignores=[]))}||{params}||{decorators}||{bindings}"
    return hashlib.sha1(payload.encode()).hexdigest()


def _group_duplicate_entries(entries: list[tuple[str, int, str, str | None]]) -> tuple[list[str], int]:
    """跨全集按指纹归并重复用例：entries = [(rel_path, lineno, name, sig|None)] → (findings, skipped)。

    冷路径（新增/变更文件）从 AST 用例构造 entries，命中缓存的文件直接复用缓存指纹——
    归并始终跨全集，重复比对质量不降。
    """
    findings: list[str] = []
    groups: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    skipped = 0
    for rel_path, lineno, name, sig in entries:
        if sig is None:
            skipped += 1
            continue
        groups[sig].append((rel_path, lineno, name))
    for members in groups.values():
        if len(members) < 2:
            continue
        head_path, head_lineno, head_name = members[0]
        others = "、".join(f"{p}:{ln} {n}" for p, ln, n in members[1:])
        findings.append(
            f"{head_path}:{head_lineno}: 用例 {head_name} 与 {len(members) - 1} 个用例完全重复"
            f"（函数体/参数/装饰器归一化后一致）：{others}"
        )
    return findings, skipped


def check_duplicate_bodies(cases: list[TestCase]) -> tuple[list[str], int]:
    """返回（findings, 被跳过的用例数）。"""
    return _group_duplicate_entries([(rel(c.path), c.lineno, c.name, body_signature(c)) for c in cases])
