# -*- coding: utf-8 -*-
"""跨平台 import 守卫：POSIX 专属模块不得在**模块级**无条件导入。

回归背景：`test_live_status_edge.py` 曾在模块顶层 `import pty` / `import termios`，
在 Windows 上直接导致收集失败（`ERROR collecting ...`），把整档 `unit`/`regression` 拖垮——
CI 与本地均跑 Linux，结构性看不见。

规则：`src/test/**` 的模块级语句中，若出现 POSIX 专属模块（`pty`/`termios`/`fcntl`/`pwd`/
`grp`/`tty`/`resource`）的 `import`，即 finding。允许的写法：

  - 放进 `try/except ImportError`（降级路径）
  - 用 `pytest.importorskip(...)`（本平台缺失则整模块跳过）
  - 写在函数/方法体内（用到时才导入，天然只在该平台执行）

只扫 `src/test`：生产代码的同类导入一律在 `try/except ImportError` 或惰性导入里（由
`check-import-surface` 与各模块自述约束）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

TEST_ROOT = Path(__file__).resolve().parents[1]  # src/test

#: POSIX 专属（Windows 标准库不提供）
POSIX_ONLY = frozenset({"pty", "termios", "fcntl", "pwd", "grp", "tty", "resource"})


def _top_level_posix_imports(path: Path) -> list[str]:
    """模块顶层（Module.body 直系）里的 POSIX 专属导入（含 `import a, b` 形式）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        for name in names:
            if name in POSIX_ONLY:
                hits.append(f"{name}（L{node.lineno}）")
    return hits


def _test_modules() -> list[Path]:
    return sorted(p for p in TEST_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_module_level_posix_imports():
    """全测试树：模块级不得无条件导入 POSIX 专属模块（否则 Windows 上整档收集失败）。"""
    findings: list[str] = []
    for path in _test_modules():
        for hit in _top_level_posix_imports(path):
            rel = path.relative_to(TEST_ROOT.parent.parent)
            findings.append(f"{rel}: 模块级导入 POSIX 专属模块 {hit}")
    assert findings == []


def test_detects_module_level_import(tmp_path: Path):
    """守卫自身有效性：造一个违规模块能被检出（防「扫了个寂寞」）。"""
    sample = tmp_path / "sample.py"
    sample.write_text("import pty\n", encoding="utf-8")
    assert _top_level_posix_imports(sample) == ["pty（L1）"]


def test_allows_guarded_and_lazy_imports(tmp_path: Path):
    """允许的三类写法不误报：try 包裹 / importorskip / 函数体内。"""
    sample = tmp_path / "ok.py"
    sample.write_text(
        "try:\n"
        "    import pty\n"
        "except ImportError:\n"
        "    pty = None\n"
        "\n"
        "\n"
        "def later():\n"
        "    import termios\n"
        "    return termios\n",
        encoding="utf-8",
    )
    assert _top_level_posix_imports(sample) == []
