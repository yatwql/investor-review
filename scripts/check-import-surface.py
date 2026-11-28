#!/usr/bin/env python3
"""导入面契约检查：兼容注释 / 私有 __all__ / 跨包私有导入 / 动态导入字面量 / 例外表自审。

规则对应 `docs/managements/technical.md` 的「导入面所有权」表与
`docs/archive/v0.15.x/import-surface/import-surface-rename.md` 的 compat-comment / private-all / cross-private / dynamic-target 规格：

  compat-comment 兼容注释      `兼容既有导入面` 等四类关键词出现在 `src/python/`
  private-all 公共 __all__  包 `__init__.py` 的 `__all__` 含 `_` 私有名
  cross-private 跨包私有导入  跨包 `from src.python.<pkg>._x import ...`（同包与测试私有导入除外）
  cross-private-scripts        `scripts/` 侧导入 `src/python` 的私有模块（口径同上：只判模块面；
                            `scripts` 内部互引不受限，典型违规：脚本读 config 的私有模块
                            去改模块全局）
  dynamic-target 动态导入字面量 `importlib.import_module("...")` 的直接字符串目标不可解析
  layer-inversion 分层越界      `core` 函数内反向依赖 `fetcher`/`providers`/…（探针面，逐处登记）；
                            `analysis` 层（纯计算）import `report/` 或 `llm/`（须改由 `core/` 提供共用面）
  exception-table 例外表自审   每条例外须齐 owner/reason/expiry/replacement；`expiry` 到期即
                            finding（续期须显式改日期并复核理由），且登记项须仍命中违规
                            （规则已修复却留着例外 → 腐化成永久豁免，须清理）

例外表在 `scripts/_import_surface_exceptions.json`（文件名与规则 schema 单源登记在
`_shared.exceptions` 的 `import-surface` 表；定位键为「文件路径 + 符号」）。已入域为第 11 条守护：本地只随
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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.checklib import REPO_ROOT, add_common_args, rel, report
from _shared.exceptions import ExceptionTable, load_exception_table, table_spec

PY_ROOT = REPO_ROOT / "src" / "python"
SCRIPTS_ROOT = REPO_ROOT / "scripts"

#: 例外表路径与规则 schema 取自 `_shared.exceptions` 的登记表（`import-surface` 表）
_TABLE_SPEC = table_spec("import-surface")
EXCEPTIONS_FILE = _TABLE_SPEC.path
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


def _load_exceptions() -> ExceptionTable:
    """返回例外表；文件缺失视为无例外，解析失败落在 `load_error` 上。"""
    return load_exception_table(EXCEPTIONS_FILE, _TABLE_SPEC.rules)


def _excepted(exceptions: ExceptionTable, rule: str, path: Path, name: str) -> bool:
    """该（规则, 文件, 符号）是否已登记例外；命中即记入 `used`。"""
    return exceptions.is_excepted(rule, rel(path), name)


def audit_exceptions(exceptions: ExceptionTable) -> list[str]:
    """exception-table：例外条目元数据齐全 + 未到期 + 仍命中违规。"""
    audit = exceptions.audit()
    findings: list[str] = []
    for rule_name, entry in audit.usable:
        key = (rule_name, *exceptions.rule(rule_name).key_of(entry))
        if key not in exceptions.used:
            findings.append(exceptions.stale_finding(rule_name, entry))
    return audit.findings + findings


def _table_or_empty(exceptions: ExceptionTable | None) -> ExceptionTable:
    """扫描函数的缺省例外表：空表（不读盘，合成目录的单测不受仓库例外影响）。"""
    return exceptions if exceptions is not None else ExceptionTable(EXCEPTIONS_FILE, _TABLE_SPEC.rules)


def scan_compat(root: Path = PY_ROOT, exceptions: ExceptionTable | None = None) -> list[str]:
    """compat-comment：兼容历史导入路径的注释关键词。"""
    table = _table_or_empty(exceptions)
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            marker = next((m for m in COMPAT_MARKERS if m in line), None)
            if marker and not _excepted(table, "compat-comment", path, marker):
                findings.append(f"[compat-comment] {rel(path)}:{lineno} 发现兼容导入标记「{marker}」")
    return findings


def scan_private_all(root: Path = PY_ROOT, exceptions: ExceptionTable | None = None) -> list[str]:
    """private-all：包门面 `__all__` 不得导出 `_` 私有名。"""
    table = _table_or_empty(exceptions)
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
                if isinstance(name, str) and name.startswith("_") and not _excepted(table, "private-all", path, name):
                    findings.append(f"[private-all] {rel(path)}:{node.lineno} __all__ 导出私有名 {name}")
    return findings


def scan_cross_private(root: Path = PY_ROOT, exceptions: ExceptionTable | None = None) -> list[str]:
    """cross-private：跨包导入私有模块（同包私有导入是允许的）。"""
    table = _table_or_empty(exceptions)
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
            if _excepted(table, "cross-private", path, target):
                continue
            findings.append(f"[cross-private] {rel(path)}:{node.lineno} 跨包导入私有模块 {target}")
    return findings


def scan_cross_private_scripts(
    root: Path = PY_ROOT,
    exceptions: ExceptionTable | None = None,
    scripts_root: Path = SCRIPTS_ROOT,
) -> list[str]:
    """cross-private-scripts：`scripts/` 侧不得导入 `src/python` 的私有模块。

    口径与 `src/python` 侧 `cross-private` 一致——只判**私有模块**（目标模块路径最后
    一段以下划线开头），公开模块的私有**符号**导入不在本规则内（同源理由：符号级
    展开会把例外表逼成逐符号登记，而分层/所有权看的是模块依赖面）。
    `from src.python.config import _config_defaults` 这类「从包门面直接取私有子模块」
    按解析结果同判（该名确实对应一个模块且其末段私有）。`scripts` 内部互引
    （`_shared/` 等）不受限：受判目标只有 `src.python.*`。
    """
    table = _table_or_empty(exceptions)
    production = set(_module_files(root))
    findings: list[str] = []
    for path in sorted(scripts_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[str] = []
            lineno = 0
            if isinstance(node, ast.ImportFrom) and node.module:
                lineno = node.lineno
                if node.module == "src.python" or node.module.startswith("src.python."):
                    targets.append(node.module)
                    # 包门面取私有子模块的形态（`from src.python.config import _x`）
                    targets.extend(
                        f"{node.module}.{alias.name}"
                        for alias in node.names
                        if alias.name != "*" and f"{node.module}.{alias.name}" in production
                    )
            elif isinstance(node, ast.Import):
                lineno = node.lineno
                targets.extend(alias.name for alias in node.names)
            for target in targets:
                if not (target == "src.python" or target.startswith("src.python.")):
                    continue
                if not target.split(".")[-1].startswith("_"):
                    continue
                if _excepted(table, "cross-private-scripts", path, target):
                    continue
                findings.append(f"[cross-private-scripts] {rel(path)}:{lineno} 导入 src/python 私有模块 {target}")
    return findings


def scan_dynamic(root: Path = PY_ROOT, exceptions: ExceptionTable | None = None) -> list[str]:
    """dynamic-target：`import_module("字面量")` 的直接目标必须可解析（变量目标由 smoke 用例兜底）。"""
    table = _table_or_empty(exceptions)
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
            if _excepted(table, "dynamic-target", path, target):
                continue
            if importlib.util.find_spec(target) is None:
                findings.append(f"[dynamic-target] {rel(path)}:{node.lineno} 动态导入目标不存在 {target}")
    return findings


#: 分层越界规则（层 → 禁止依赖的上层模块）：上层单向依赖下层，两侧共用的业务约束下沉 `core/`
_LAYER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # `core` 是最底层：数据源探针需要在链外直呼具体源实现（见 check_sources.py），
    # 属允许的**函数内**反向依赖，逐处登记例外表；新增探针源走同一形态并补登记
    ("core", ("fetcher", "providers", "analysis", "report", "llm", "tui", "web", "cli")),
    ("analysis", ("report", "llm")),
    ("fetcher", ("report", "llm", "analysis")),
    ("providers", ("report", "llm", "analysis")),
    # 交互层（`tui`/`web`/`cli`）在报告层之上：报告侧不得反向依赖它们的格式化与状态条实现
    ("report", ("tui", "web", "cli")),
    ("llm", ("tui", "web", "cli")),
    # cache 属基础设施层：可编排取数（预热调 fetcher，设计如此），但不得依赖报告/LLM/交互层
    ("cache", ("report", "llm", "tui", "web", "cli")),
    # config 属配置层：校验可读注册表，但不得依赖报告/LLM/分析的计算实现与交互层
    ("config", ("report", "llm", "analysis", "tui", "web", "cli")),
)


def scan_layer_inversion(root: Path = PY_ROOT, exceptions: ExceptionTable | None = None) -> list[str]:
    """layer-inversion：下层不得 import 上层模块（规则见 :data:`_LAYER_RULES`）。

    分层纪律：`core` → `fetcher`/`providers` → `analysis` → `report`/`llm` → `tui`/`web`/`cli`，
    上层单向依赖下层。`core`（最底层）经**函数内**延迟导入取数层属探针职责，允许但须逐处
    登记例外表；取数层（fetcher/providers）反向依赖 `report/`/`llm/`/`analysis/`
    与纯计算层（analysis）反向依赖 `report/`/`llm/` 同属越界；两侧共用的业务约束
    （观测登记面、派生原语）应下沉 `core/`（例：`core/recommendation_policy.py`、
    `core/trading_calendar.py`）。存量越界走例外表（`path` = 违规文件，`name` = 被
    导入的目标模块），到期须收敛。
    """
    table = _table_or_empty(exceptions)
    findings: list[str] = []
    for layer, forbidden in _LAYER_RULES:
        layer_root = root / layer
        if not layer_root.exists():
            continue
        for path in sorted(layer_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                targets: list[str] = []
                lineno = 0
                if isinstance(node, ast.ImportFrom) and node.module:
                    # 只判模块依赖面（`from a.b import c` 的目标是 `a.b`）：符号级展开会把
                    # 例外表逼成逐符号登记，且分层纪律看的是模块依赖方向
                    targets = [node.module]
                    lineno = node.lineno
                elif isinstance(node, ast.Import):
                    targets = [a.name for a in node.names]
                    lineno = node.lineno
                for target in targets:
                    parts = target.split(".")
                    if len(parts) < 3 or parts[0] != "src" or parts[1] != "python" or parts[2] not in forbidden:
                        continue
                    if _excepted(table, "layer-inversion", path, target):
                        continue
                    findings.append(f"[layer-inversion] {rel(path)}:{lineno} {layer} 不得依赖 {target}")
                    break
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
        "cross-private-scripts": scan_cross_private_scripts(root, exceptions),
        "dynamic-target": scan_dynamic(root, exceptions),
        "layer-inversion": scan_layer_inversion(root, exceptions),
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
        print(f"[..] 扫描 {rel(PY_ROOT)} 与 {rel(SCRIPTS_ROOT)}，规则计数：{stats}")
    return report(
        findings,
        "[OK] 导入面契约通过（无兼容注释/私有 __all__/跨包私有导入/动态导入字面量问题）",
        ci=args.ci,
        fail_message="[!] 发现 {n} 处导入面问题，须修正或登记例外表",
    )


if __name__ == "__main__":
    sys.exit(main())
