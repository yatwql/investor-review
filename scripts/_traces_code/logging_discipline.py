"""日志统一约束守卫（check-code-traces 的 AST 级 LOG 扫描支路）。

约束口径：生产代码的诊断输出统一走 ``logging``（落 ``logs/app.log`` + console），
``print()`` 只允许出现在**直接面向终端的交互呈现层**。理由：
``print()`` 绕过日志级别过滤、落盘与统一格式，非交互路径（数据获取/分析/报告
生成）用它会让诊断信息既不可追溯也无法集中治理（重定向、告警、脱敏）。

豁免域是封闭白名单：交互呈现层整目录（TUI 菜单、CLI 入口）+ 逐文件列举的
交互输出模块（进度条、一次性终端检查报告、首启向导）。新增 ``print()`` 必须
落在白名单内，否则应改用 ``logging``——白名单扩张属预审行为，须在设计文档
声明，不允许就地扩散。
"""

from __future__ import annotations

import ast
from pathlib import Path

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
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    )


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
                    node.lineno,
                    "LOG",
                    "非交互层 print()（诊断输出应走 logging 落盘）",
                    f"print(...) @ {rel}",
                )
            )
    return hits
