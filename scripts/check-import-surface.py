#!/usr/bin/env python3
"""导入面契约检查：兼容注释 / 私有 __all__ / 跨包私有导入 / 动态导入字面量 / 例外表自审。

规则对应 `docs/managements/technical.md` 的「导入面所有权」表与
`docs/archive/v0.15.x/import-surface/import-surface-rename.md` 的 compat-comment / private-all / cross-private / dynamic-target 规格：

  compat-comment 兼容注释      `兼容既有导入面` 等四类关键词出现在 `src/python/`
  private-all 公共 __all__  包 `__init__.py` 的 `__all__` 含 `_` 私有名
  cross-private 跨包私有导入  跨包 `from src.python.<pkg>._x import ...`（同包与测试私有导入除外）
  dynamic-target 动态导入字面量 `importlib.import_module("...")` 的直接字符串目标不可解析
  exception-table 例外表自审   每条例外须齐 owner/reason/expiry/replacement；`expiry` 到期即
                            finding（续期须显式改日期并复核理由），且登记项须仍命中违规
                            （规则已修复却留着例外 → 腐化成永久豁免，须清理）

例外表在 `scripts/_import_surface_exceptions.json`。已入域为第 11 条守护：本地只随
`src/python/` 变更由 pre-commit 触发，CI `guards` job 与 P2 门禁恒全量覆盖（观察期
结束条件——真实树上零 finding、零例外，误报为零）。

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
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402

PY_ROOT = REPO_ROOT / "src" / "python"
EXCEPTIONS_FILE = Path(__file__).resolve().parent / "_import_surface_exceptions.json"
COMPAT_MARKERS = ("兼容既有导入面", "兼容既有引用", "公开别名", "私有名保留")

#: 例外条目必填字段（缺一即无法追责或无法自动到期）
_REQUIRED_FIELDS = ("owner", "reason", "expiry", "replacement")

#: 到期日格式（ISO 日历日，无时区歧义；`YYYY-MM-DD` 之外的写法一律判元数据违规）
_EXPIRY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


class _ExceptionTable(dict):
    """例外表：`{规则: {(相对路径, 符号)}}`，附带原始条目与命中记录。

    `used` 记下 `_excepted` 实际查询过的 `(规则, 路径, 符号)`：查询由违规候选驱动，
    没命中说明该规则早已修复，留下的例外只是永不到期的豁免。
    """

    def __init__(self, raw: dict[str, list[dict]] | None = None) -> None:
        super().__init__()
        self.raw: dict[str, list[dict]] = dict(raw or {})
        self.used: set[tuple[str, str, str]] = set()
        #: 读表失败原因（非空时整张表作废，由 `collect` 转成一条 finding）
        self.load_error: str = ""
        for rule, entries in self.raw.items():
            self[rule] = {(str(e.get("path", "")), str(e.get("name", ""))) for e in entries}


def _load_exceptions() -> _ExceptionTable:
    """返回例外表；文件缺失视为无例外，解析失败落在 `load_error` 上。"""
    if not EXCEPTIONS_FILE.exists():
        return _ExceptionTable()
    try:
        return _ExceptionTable(json.loads(EXCEPTIONS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        table = _ExceptionTable()
        table.load_error = f"{rel(EXCEPTIONS_FILE)} 无法解析：{exc}"
        return table


def _excepted(exceptions: dict[str, set[tuple[str, str]]], rule: str, path: Path, name: str) -> bool:
    rel_path = rel(path)
    if (rel_path, name) not in exceptions.get(rule, set()):
        return False
    used = getattr(exceptions, "used", None)
    if used is not None:
        used.add((rule, rel_path, name))
    return True


def audit_exceptions(exceptions: _ExceptionTable) -> list[str]:
    """exception-table：例外条目元数据齐全 + 未到期 + 仍命中违规。"""
    findings: list[str] = []
    today = date.today()
    for rule, entries in exceptions.raw.items():
        for entry in entries:
            path = str(entry.get("path", ""))
            name = str(entry.get("name", ""))
            where = f"{rel(EXCEPTIONS_FILE)} {rule}:{path}::{name}"
            missing = [field for field in _REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
            if missing:
                findings.append(f"[exception-metadata] {where} 缺少字段 {'/'.join(missing)}")
                continue
            expiry_raw = str(entry["expiry"]).strip()
            if not _EXPIRY_RE.match(expiry_raw):
                findings.append(f"[exception-metadata] {where} expiry 须为 YYYY-MM-DD，实为「{expiry_raw}」")
                continue
            if date.fromisoformat(expiry_raw) < today:
                findings.append(f"[exception-expiry] {where} 已于 {expiry_raw} 到期，须删除例外或续期并复核理由")
            elif (rule, path, name) not in exceptions.used:
                findings.append(f"[exception-stale] {where} 未命中任何违规（规则已修复），须删除该例外")
    return findings


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
    if exceptions.load_error:
        # 例外表是受检资产：解析失败按 finding 报（退出 2），不让 JSONDecodeError
        # 以 traceback 窜出（退出 1 不在契约码域内）
        return [f"[exception-metadata] {exceptions.load_error}"], {"exception-table": 1}
    groups = {
        "compat-comment": scan_compat(root, exceptions),
        "private-all": scan_private_all(root, exceptions),
        "cross-private": scan_cross_private(root, exceptions),
        "dynamic-target": scan_dynamic(root, exceptions),
    }
    # 例外表自审放在扫描之后：`used` 已由上述四条规则填满，才能判出失效例外
    groups["exception-table"] = audit_exceptions(exceptions)
    findings = [finding for group in groups.values() for finding in group]
    return findings, {rule: len(items) for rule, items in groups.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="导入面契约检查")
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
