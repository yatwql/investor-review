"""开发期本地卫生：陈旧字节码清理与统计（不参与任何门禁判定）。

背景：模块改名/删除后，`__pycache__/旧名.cpython-*.pyc` 不会被 Python 回收；
功能上无害（孤立 .pyc 不会被 import），但会让 `rg`/traceback 里出现旧文件名与旧路径，
排查时误导。本模块只做**只读统计**与**显式清理**两件事，调用方决定何时用：

  - `stale_bytecode(root)`：列出「同目录下已无同名 .py 源文件」的 .pyc
  - `clean_stale_bytecode(root)`：删除上述 .pyc（空了连带删目录），返回计数

清理是幂等的；删掉的字节码下次导入时自动重建。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

#: 不扫描的目录（版本库/虚拟环境/运行数据/产物/文档）
SKIP_DIRS = frozenset({".git", ".venv", "data", "logs", "test-reports", ".pytest_cache", "docs"})

#: `name.cpython-313.pyc` / `name.cpython-313-pytest-9.1.1.pyc`
_PYC_RE = re.compile(r"^(?P<stem>.+?)(?:\.cpython-\d+)?(?:-pytest-[\d.]+)?\.pyc$")


def _iter_pycache_dirs(root: Path):
    for d in root.rglob("__pycache__"):
        if d.is_dir() and not (SKIP_DIRS & set(d.parts)):
            yield d


def _source_stems(pycache_dir: Path) -> set[str]:
    parent = pycache_dir.parent
    return {p.stem for p in parent.glob("*.py")} | {p.stem for p in parent.glob("*.pyi")}


def _pyc_stem(name: str) -> str:
    m = _PYC_RE.match(name)
    return m.group("stem") if m else name[: -len(".pyc")]


def stale_bytecode(root: Path) -> list[Path]:
    """返回「同目录已无对应源文件」的 .pyc 路径（按路径排序，便于稳定输出）。"""
    stale: list[Path] = []
    for pycache_dir in _iter_pycache_dirs(root):
        sources = _source_stems(pycache_dir)
        for f in sorted(pycache_dir.glob("*.pyc")):
            if _pyc_stem(f.name) not in sources:
                stale.append(f)
    return stale


def clean_stale_bytecode(root: Path, *, dry_run: bool = False) -> dict[str, int]:
    """删除陈旧 .pyc（空了连带删 `__pycache__` 目录）。

    Args:
        root: 仓库根
        dry_run: True 只统计不删除（doctor/预览用）

    Returns:
        ``{"files": 删除(或待删)文件数, "dirs": 删除(或待删)目录数}``；任何 OSError 静默跳过该项
    """
    files = 0
    dirs = 0
    touched_dirs: set[Path] = set()
    for path in stale_bytecode(root):
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                continue
        files += 1
        touched_dirs.add(path.parent)
    for d in touched_dirs:
        if any(d.glob("*.pyc")):
            continue
        if not dry_run:
            try:
                shutil.rmtree(d)
                # 源目录也空了（模块整体被删/改名）→ 一并收掉；非空则 rmdir 会失败，安全
                try:
                    d.parent.rmdir()
                except OSError:
                    pass
            except OSError:
                continue
        dirs += 1
    return {"files": files, "dirs": dirs}
