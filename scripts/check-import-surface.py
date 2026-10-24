#!/usr/bin/env python3
"""导入面契约检查（观察期）：兼容注释 / 私有 __all__ / 跨包私有导入 / 动态导入字面量。

规则对应 `docs/managements/technical.md` 的「导入面所有权」表与
`docs/archive/v0.15.x/import-surface/import-surface-rename.md` 的 compat-comment / private-all / cross-private / dynamic-target 规格：

  compat-comment 兼容注释      `兼容既有导入面` 等四类关键词出现在 `src/python/`
  private-all 公共 __all__  包 `__init__.py` 的 `__all__` 含 `_` 私有名
  cross-private 跨包私有导入  跨包 `from src.python.<pkg>._x import ...`（同包与测试私有导入除外）
  dynamic-target 动态导入字面量 `importlib.import_module("...")` 的直接字符串目标不可解析

例外表在 `scripts/_import_surface_exceptions.json`；每条须有 owner/reason/expiry/replacement。
本脚本先作观察期检查（未接入 pre-commit/CI 门禁），稳定后按脚本命名约定评估入门禁。

用法：
  python scripts/check-import-surface.py
  python scripts/check-import-surface.py -v       # 打印扫描范围与统计
  python scripts/check-import-surface.py --ci     # 仅输出 文件:描述

退出码：
  0 — 全部通过
  2 — 发现导入面 finding（与 _shared/checklib.report 返回值域一致）
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402

PY_ROOT = REPO_ROOT / "src" / "python"
EXCEPTIONS_FILE = Path(__file__).resolve().parent / "_import_surface_exceptions.json"
COMPAT_MARKERS = ("兼容既有导入面", "兼容既有引用", "公开别名", "私有名保留")


def _module_name(path: Path, root: Path) -> str:
    rel_path = path.relative_to(root).with_suffix("")
    parts = list(rel_path.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return "src.python." + ".".join(parts) if parts else "src.python"


def _module_files(root: Path) -> dict[str, Path]:
    return {_module_name(path, root): path for path in root.rglob("*.py")}


def _package_of(module: str) -> str:
    return ".".join(module.split(".")[:3])


def _load_exceptions() -> dict[str, set[tuple[str, str]]]:
    """返回 {规则: {(相对路径, 符号)}}；文件缺失视为无例外。"""
    if not EXCEPTIONS_FILE.exists():
        return {}
    raw = json.loads(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
    result: dict[str, set[tuple[str, str]]] = {}
    for rule, entries in raw.items():
        result[rule] = {(str(e["path"]), str(e["name"])) for e in entries}
    return result


def _excepted(exceptions: dict[str, set[tuple[str, str]]], rule: str, path: Path, name: str) -> bool:
    return (rel(path), name) in exceptions.get(rule, set())


def scan_compat(root: Path = PY_ROOT, exceptions=None) -> list[str]:
    """compat-comment：兼容历史导入路径的注释关键词。"""
    exceptions = exceptions or {}
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            marker = next((m for m in COMPAT_MARKERS if m in line), None)
            if marker and not _excepted(exceptions, "compat-comment", path, marker):
                findings.append(f"[compat-comment] {rel(path)}:{lineno} 发现兼容导入标记「{marker}」")
    return findings


def scan_private_all(root: Path = PY_ROOT, exceptions=None) -> list[str]:
    """private-all：包门面 `__all__` 不得导出 `_` 私有名。"""
    exceptions = exceptions or {}
    findings: list[str] = []
    for path in sorted(root.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            ):
                continue
            try:
                values = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for name in values:
                if (
                    isinstance(name, str)
                    and name.startswith("_")
                    and not _excepted(exceptions, "private-all", path, name)
                ):
                    findings.append(f"[private-all] {rel(path)}:{node.lineno} __all__ 导出私有名 {name}")
    return findings


def scan_cross_private(root: Path = PY_ROOT, exceptions=None) -> list[str]:
    """cross-private：跨包导入私有模块（同包私有导入是允许的）。"""
    exceptions = exceptions or {}
    modules = _module_files(root)
    findings: list[str] = []
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = node.module or ""
            if target not in modules or not target.split(".")[-1].startswith("_"):
                continue
            if _package_of(module) == _package_of(target):
                continue
            if any(_excepted(exceptions, "cross-private", path, target) for _ in [0]):
                continue
            findings.append(f"[cross-private] {rel(path)}:{node.lineno} 跨包导入私有模块 {target}")
    return findings


def scan_dynamic(root: Path = PY_ROOT, exceptions=None) -> list[str]:
    """dynamic-target：`import_module("字面量")` 的直接目标必须可解析（变量目标由 smoke 用例兜底）。"""
    exceptions = exceptions or {}
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "import_module" or not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue
            target = arg.value
            if _excepted(exceptions, "dynamic-target", path, target):
                continue
            if importlib.util.find_spec(target) is None:
                findings.append(f"[dynamic-target] {rel(path)}:{node.lineno} 动态导入目标不存在 {target}")
    return findings


def collect(root: Path = PY_ROOT) -> tuple[list[str], dict[str, int]]:
    exceptions = _load_exceptions()
    groups = {
        "compat-comment": scan_compat(root, exceptions),
        "private-all": scan_private_all(root, exceptions),
        "cross-private": scan_cross_private(root, exceptions),
        "dynamic-target": scan_dynamic(root, exceptions),
    }
    findings = [finding for group in groups.values() for finding in group]
    return findings, {rule: len(items) for rule, items in groups.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="导入面契约检查（观察期）")
    add_common_args(parser)
    args = parser.parse_args()
    findings, stats = collect()
    if args.verbose:
        print(f"[..] 扫描 {rel(PY_ROOT)}，规则计数：{stats}")
    return report(
        findings,
        "[OK] 导入面契约通过（无兼容注释/私有 __all__/跨包私有导入/动态导入字面量问题）",
        ci=args.ci,
        fail_message="[!] 发现 {n} 处导入面问题，须修正或登记例外表",
    )


if __name__ == "__main__":
    sys.exit(main())
