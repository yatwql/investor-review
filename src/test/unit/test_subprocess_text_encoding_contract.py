"""子进程文本模式的 `encoding=` 契约 — 静态扫描（防 CI portability 档静默变红）。

背景：`subprocess.run(..., text=True)` 不传 `encoding=` 时按 **locale** 解码子进程输出。
本机 UTF-8 locale 下一切正常，而在 `PYTHONWARNDEFAULTENCODING=1` + `pytest.ini` 的
`error::EncodingWarning` 下会直接抛异常（CI `portability` job 正是这一档）——中文
Windows（cp936）与 `LC_ALL=C` 环境同样会解码错乱。实测曾因此让 dev 连续 8 次推送
在 portability 档变红，而本地三档门禁全绿（它们不设该环境变量）。

本用例是该缺陷的回归守卫：静态扫描 `src/python` / `scripts` / `src/test` 里所有
`subprocess.*` 文本模式调用，必须同时给出 `encoding=`。写在代码层而非只靠 CI，是因为
「本地绿、CI 红」只能靠环境差异发现，代价是 8 次推送。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAN_DIRS = ("src/python", "scripts", "src/test")

#: 文本模式开关：任一为真即按 locale 编解码，必须显式给 encoding。
_TEXT_MODE_KWARGS = ("text", "universal_newlines")

#: 受检的子进程入口（`subprocess.run` / `Popen` / `check_output` / `call` / `check_call`）。
_SUBPROCESS_FUNCS = ("run", "Popen", "check_output", "call", "check_call")


def _subprocess_calls(tree: ast.AST) -> list[ast.Call]:
    """收集 `subprocess.<func>(...)` 与 `from subprocess import <func>` 后的直接调用。"""
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == "subprocess":
            imported |= {alias.asname or alias.name for alias in node.names if alias.name in _SUBPROCESS_FUNCS}
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "subprocess":
            if func.attr in _SUBPROCESS_FUNCS:
                calls.append(node)
        elif isinstance(func, ast.Name) and func.id in imported:
            calls.append(node)
    return calls


def _has_text_mode(call: ast.Call) -> bool:
    """调用是否开了文本模式（`text=True` / `universal_newlines=True`）。"""
    for keyword in call.keywords:
        if keyword.arg in _TEXT_MODE_KWARGS and isinstance(keyword.value, ast.Constant) and keyword.value.value:
            return True
    return False


def _has_encoding(call: ast.Call) -> bool:
    """调用是否显式给了 `encoding=`。"""
    return any(keyword.arg == "encoding" for keyword in call.keywords)


def _iter_files() -> list[Path]:
    paths: list[Path] = []
    for relative in SCAN_DIRS:
        paths.extend(sorted((REPO_ROOT / relative).rglob("*.py")))
    return paths


def test_subprocess_text_mode_always_declares_encoding():
    """文本模式的子进程调用必须带 encoding（否则 portability 档按 locale 解码）。"""
    offenders: list[str] = []
    for path in _iter_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # 解析失败由 lint/编译门禁负责
            continue
        for call in _subprocess_calls(tree):
            if _has_text_mode(call) and not _has_encoding(call):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{call.lineno}")
    assert offenders == [], "子进程文本模式缺 encoding=（CI portability 档会抛 EncodingWarning）：\n  " + "\n  ".join(
        offenders
    )


class TestScannerSelfCheck:
    """扫描器自检：确认判据真的能抓到违规形态（否则用例恒真）。"""

    pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

    def _scan(self, source: str) -> list[str]:
        tree = ast.parse(source)
        return [f"L{c.lineno}" for c in _subprocess_calls(tree) if _has_text_mode(c) and not _has_encoding(c)]

    def test_detects_missing_encoding(self):
        source = "import subprocess\nsubprocess.run(['x'], text=True, capture_output=True)\n"
        assert self._scan(source) == ["L2"]

    def test_accepts_explicit_encoding(self):
        source = "import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8')\n"
        assert self._scan(source) == []

    def test_detects_universal_newlines_alias(self):
        source = "from subprocess import check_output\ncheck_output(['x'], universal_newlines=True)\n"
        assert self._scan(source) == ["L2"]

    def test_ignores_binary_mode(self):
        source = "import subprocess\nsubprocess.run(['x'], capture_output=True)\n"
        assert self._scan(source) == []
