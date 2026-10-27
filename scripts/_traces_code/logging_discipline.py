"""日志统一约束守卫（check-code-traces 的 AST 级 LOG 扫描支路）。

约束口径：生产代码的诊断输出统一走 ``logging``（落 ``logs/app.log`` + console），
``print()`` 只允许出现在**直接面向终端的交互呈现层**。理由：
``print()`` 绕过日志级别过滤、落盘与统一格式，非交互路径（数据获取/分析/报告
生成）用它会让诊断信息既不可追溯也无法集中治理（重定向、告警、脱敏）。

豁免域是封闭白名单：交互呈现层整目录（TUI 菜单、CLI 入口）+ 逐文件列举的
交互输出模块（进度条、一次性终端检查报告、首启向导）。新增 ``print()`` 必须
落在白名单内，否则应改用 ``logging``——白名单扩张属预审行为，须在设计文档
声明，不允许就地扩散。

第二条支路（C8 前半句）：模块日志器名称必须统一为 ``"invest"``——各模块自取
``__name__`` 或自定名称会落到另一棵 logger 树上，``invest`` 的 handler / 级别 /
格式与落盘全部不生效（日志静默丢失，且无法入 ``logs/app.log``）。唯一豁免是
``core/logger.py`` 的构造函数（它以变量名称建链，是“invest”的唯一定义点）。
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

#: 整目录豁免（交互呈现层：终端 UI 与命令行入口，其输出即终端交互本身）
_PRINT_EXEMPT_DIR_PREFIXES = (
    "src/python/tui/",
    "src/python/cli/",
)

#: 逐文件豁免（均为直接面向终端的一次性输出：进度反馈 / 检查报告 / 向导对话）
_PRINT_EXEMPT_FILES = frozenset(
    {
        "src/python/report/progress.py",
        "src/python/report/cli_progress.py",
        "src/python/report/privacy_notice.py",
        "src/python/core/check_sources.py",
        "src/python/core/doctor.py",
        "src/python/startup_wizard.py",
    }
)


def _rel_posix(fpath: Path, repo_root: Path) -> str:
    """仓库相对 POSIX 路径（不在仓库内时退回绝对形态，避免误判豁免）。"""
    try:
        return fpath.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return fpath.as_posix()


def _is_print_exempt(rel_path: str) -> bool:
    """判断仓库相对路径是否落在 ``print()`` 豁免白名单内。"""
    return rel_path in _PRINT_EXEMPT_FILES or rel_path.startswith(_PRINT_EXEMPT_DIR_PREFIXES)


def _is_print_call(node: ast.AST) -> bool:
    """是否为对内置 ``print`` 的直接调用（排除 ``obj.print()`` / 别名覆盖情形）。"""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"


#: 模块日志器的常见绑定名（只有绑定到这些名字才算“本模块日志器”）
_LOGGER_BINDING_NAMES = frozenset({"logger", "_logger"})

#: 日志器名称豁免文件（``core/logger.py`` 是 ``"invest"`` 的唯一创建点）
_LOGGER_NAME_EXEMPT_FILES = frozenset({"src/python/core/logger.py"})


def _is_getlogger_call(node: ast.AST) -> bool:
    """是否为 ``logging.getLogger(...)`` 调用（含 ``logging.getLogger`` 属性链）。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "getLogger"
        and isinstance(func.value, ast.Name)
        and func.value.id == "logging"
    )


def _logger_binding_targets(node: ast.stmt) -> list[str]:
    """返回赋值语句绑定的名字（``logger = ...`` / ``logger: T = ...`` / ``a = b = ...``）。"""
    if isinstance(node, ast.Assign):
        names: list[str] = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
        return names
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _scan_logger_calls(fpath: Path, repo_root: Path) -> list[tuple[int, str, str, str]]:
    """扫描生产代码中名称不统一的模块日志器（C8：一律 ``logging.getLogger("invest")``）。

    仅约束“绑定到模块级 ``logger`` / ``_logger`` 名字”的调用——第三方日志器
    静音（如 ``logging.getLogger("werkzeug").setLevel(...)``）与 ``core/logger.py``
    的构造链不在纪律内。AST 解析失败时静默跳过（同 ``print()`` 支路）。
    """
    if fpath.suffix.lower() != ".py":
        return []
    rel = _rel_posix(fpath, repo_root)
    if not rel.startswith("src/python/") or rel in _LOGGER_NAME_EXEMPT_FILES:
        return []
    try:
        tree = ast.parse(fpath.read_text(encoding="utf-8-sig"), filename=str(fpath))
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        return []
    hits: list[tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if not _LOGGER_BINDING_NAMES.intersection(_logger_binding_targets(node)):
            continue
        value = node.value
        if value is None or not _is_getlogger_call(value):
            continue
        call = cast(ast.Call, value)
        args = call.args
        name_arg = args[0] if args else None
        if isinstance(name_arg, ast.Constant) and name_arg.value == "invest":
            continue
        hits.append(
            (
                getattr(node, "lineno", 0),
                "LOG",
                '模块日志器名称须为 logging.getLogger("invest")（自取名称会脱离统一 handler 与落盘）',
                f"getLogger(...) @ {rel}",
            )
        )
    return hits


def _scan_print_calls(fpath: Path, repo_root: Path) -> list[tuple[int, str, str, str]]:
    """扫描生产代码中的非豁免 ``print()`` 调用。

    仅约束 ``src/python`` 生产层（测试夹具打印、脚本工具输出不在纪律内）；
    豁免判定以仓库相对路径为准（目录前缀 + 文件白名单），AST 解析失败时静默
    跳过（语法错误由 ruff/编译阶段拦截，不应在此处二次报警）。
    """
    if fpath.suffix.lower() != ".py":
        return []
    rel = _rel_posix(fpath, repo_root)
    if not rel.startswith("src/python/"):
        return []
    if _is_print_exempt(rel):
        return []
    try:
        tree = ast.parse(fpath.read_text(encoding="utf-8-sig"), filename=str(fpath))
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        return []
    hits: list[tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if _is_print_call(node):
            hits.append(
                (
                    getattr(node, "lineno", 0),
                    "LOG",
                    "非交互层 print()（诊断输出应走 logging 落盘）",
                    f"print(...) @ {rel}",
                )
            )
    return hits
