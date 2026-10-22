"""报告产物定位与「一键打开」（TUI 收尾）。

语义名：`report_artifacts`（收尾产物清单 + 是否打开）。

职责边界：
- **只读定位**：``output_dir`` 下最新的 HTML / Excel 产物，存在才收（不生成、不写盘）；
- **打开动作**平台分派（Windows ``os.startfile`` / macOS ``open`` / Linux ``xdg-open``），
  失败不抛异常、由调用方回退为「手动访问路径」提示；
- **交互**：单键读取——``y`` / ``Y`` = 打开报告目录与报告；**默认 N**，其余任何键
  （含 ``n`` / 回车 / Esc / 未知键）都按默认值处理，不额外追问；``Ctrl+C`` 沿用 TUI
  既有约定（退出程序）；非 TTY（脚本/管道）不问、只打印产物清单，避免阻塞。

设计契约（`DESIGN-TUI.md`）：提示形态用二选一确认 ``(y/N)``（大写一侧为默认）；
反馈带 ``[OK]`` / ``[!]`` 前缀并给出可核对路径；Esc 只取消当前提示、不退出程序。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from src.python.core.constants import LATEST_HTML_NAME, LATEST_XLSX_NAME

logger = logging.getLogger("invest")

#: 打开动作的键（单键读取；大写一侧为默认 N —— 与提示 `(y/N)` 同源）
_YES_KEYS = frozenset({"Y", "y"})

#: 子进程打开动作的超时（秒）：守卫系统命令缺失/挂起，失败按「未打开」降级
_OPEN_TIMEOUT = 5.0


def collect_artifacts(config: dict | None) -> tuple[Path, ...]:
    """收集 ``output_dir`` 下已存在的最新产物（先 HTML 后 Excel，缺失者跳过）。

    Returns:
        存在的产物路径元组；一个都没有时为空元组（调用方据此跳过询问）。
    """
    output_dir = Path(str((config or {}).get("output_dir") or "reports"))
    candidates = (output_dir / LATEST_HTML_NAME, output_dir / LATEST_XLSX_NAME)
    return tuple(path for path in candidates if path.is_file())


def _default_opener(path: Path) -> bool:
    """用系统默认程序打开路径；成功返回 True，任何失败（含命令缺失）返回 False。"""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]  # Windows 专用
            return True
        command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        return subprocess.run(command, check=False, timeout=_OPEN_TIMEOUT).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:  # 无图形环境/命令缺失/超时
        logger.debug("[report_artifacts] 打开失败 %s: %s", path, e)
        return False


def open_artifacts(paths: tuple[Path, ...], *, opener: Callable[[Path], bool] | None = None) -> list[Path]:
    """逐个打开路径，返回**成功**打开的清单（失败者由调用方提示手动访问）。"""
    open_one = opener or _default_opener
    opened: list[Path] = []
    for path in paths:
        if open_one(path):
            opened.append(path)
    return opened


def _ask_open(key_reader: Callable[[], str]) -> bool:
    """询问「是否打开」：仅 y/Y 为是；其余（含 Esc / 回车 / 未知键）走默认 N。"""
    from src.python.tui.tui_keys import KEY_CTRL_C

    key = key_reader()
    if key == KEY_CTRL_C:
        from src.python.tui.tui_menu import exit_app

        exit_app()
    return key in _YES_KEYS


def prompt_open_artifacts(
    artifacts: tuple[Path, ...],
    *,
    key_reader: Callable[[], str] | None = None,
    opener: Callable[[Path], bool] | None = None,
    echo: Callable[[str], None] = print,
) -> str:
    """打印产物清单并询问是否打开（目录 + 报告）。

    Args:
        artifacts: :func:`collect_artifacts` 的结果（空则不做任何事）。
        key_reader: 键读取（测试注入；缺省 ``tui_keys.get_key``）。
        opener: 打开动作（测试注入；缺省平台分派）。
        echo: 输出函数（测试注入）。

    Returns:
        ``"skipped"``（非 TTY / 无产物 / 用户选默认 N）、``"opened"``（至少打开一项）、
        ``"failed"``（用户选了是但一项都没打开）。
    """
    if not artifacts:
        return "skipped"
    output_dir = artifacts[0].parent
    echo("  [OK] 本次产物：")
    echo(f"       报告目录  {output_dir}")
    for path in artifacts:
        echo(f"       产物文件  {path}")
    if not sys.stdin.isatty():
        return "skipped"  # 脚本/管道不阻塞：只列清单，交回菜单

    echo("  是否打开报告目录与报告？(y/N): ")
    if not _ask_open(key_reader or _get_key):
        echo("  未打开：可手动访问上方路径")
        return "skipped"

    targets = (output_dir, *artifacts)
    opened = open_artifacts(targets, opener=opener)
    if not opened:
        echo("  [!] 打开失败（可能是无图形界面环境）：请手动访问上方路径")
        return "failed"
    for path in opened:
        echo(f"  [OK] 已打开：{path}")
    return "opened"


def _get_key() -> str:
    """读一个键（延迟导入，避免 TUI 键位模块在非终端环境被提前加载）。"""
    from src.python.tui.tui_keys import get_key

    return get_key()
