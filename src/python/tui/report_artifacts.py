"""报告产物定位与「一键打开」（TUI 收尾）。

语义名：`report_artifacts`（收尾产物清单 + 是否打开）。

职责边界：
- **只读定位**：``output_dir`` 下最新的 HTML / Excel 产物，存在才收（不生成、不写盘）；
- **打开动作**平台分派（Windows ``os.startfile`` / macOS ``open`` / Linux ``xdg-open``），
  失败不抛异常、由调用方回退为「手动访问路径」提示；
- **交互**：单键读取——``y`` / ``Y`` = 打开报告目录与报告；**默认 N**，其余任何键
  （含 ``n`` / 回车 / Esc / 未知键）都按默认值处理，不额外追问；``Ctrl+C`` 沿用 TUI
  既有约定（退出程序）；非 TTY（脚本/管道）不问、只打印产物清单，避免阻塞；
  远程 SSH/无图形会话不发起本机打开动作，只打印路径与传输指引。

设计契约（`DESIGN-TUI.md`）：提示形态用二选一确认 ``(y/N)``（大写一侧为默认）；
反馈带 ``[OK]`` / ``[!]`` 前缀并给出可核对路径；Esc 只取消当前提示、不退出程序。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger("invest")

#: 打开动作的键（单键读取；大写一侧为默认 N —— 与提示 `(y/N)` 同源）
_YES_KEYS = frozenset({"Y", "y"})

#: 本会话内已试过打开且失败：不再重复询问（手机/远端反复跑报告时不重复撞壁）
_OPEN_FAILED_IN_SESSION = False


def _remote_hint(echo: Callable[[str], None]) -> None:
    """打印远端/无图形会话的传输指引（两处分支共用，文案只声明一次）。"""
    echo("      产物已保存在上方路径；请使用 Web 工作台下载，或通过 scp/sftp 获取。")


def collect_artifacts(config: dict | None) -> tuple[Path, ...]:
    """产物定位委托 core（三渠道同一事实）：``output_dir`` 下存在的最新 HTML / Excel。"""
    from src.python.core.artifacts import collect_artifacts as core_collect

    return core_collect(config)


def open_artifacts(paths: tuple[Path, ...], *, opener: Callable[[Path], bool] | None = None) -> list[Path]:
    """打开动作委托 core（平台分派与失败降级同源）。"""
    from src.python.core.artifacts import open_artifacts as core_open

    return core_open(paths, opener=opener)


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
    open_supported: Callable[[], bool] | None = None,
) -> str:
    """打印产物清单并询问是否打开（目录 + 报告）。

    Args:
        artifacts: :func:`collect_artifacts` 的结果（空则不做任何事）。
        key_reader: 键读取（测试注入；缺省 ``tui_keys.get_key``）。
        opener: 打开动作（测试注入；缺省平台分派）。
        echo: 输出函数（测试注入）。
        open_supported: 本机桌面打开能力探测（测试注入；缺省看 SSH/DISPLAY）。

    Returns:
        ``"skipped"``（非 TTY / 无产物 / 用户选默认 N）、``"opened"``（至少打开一项）、
        ``"failed"``（用户选了是但一项都没打开）、``"unsupported"``（远程/无图形会话
        或本会话已试过打开失败，服务器无法在客户端打开文件管理器）。
    """
    global _OPEN_FAILED_IN_SESSION
    if not artifacts:
        return "skipped"
    output_dir = artifacts[0].parent
    echo("  [OK] 本次产物：")
    echo(f"       报告目录  {output_dir}")
    for path in artifacts:
        echo(f"       产物文件  {path}")
    if _OPEN_FAILED_IN_SESSION or not (open_supported or _local_open_supported)():
        logger.info("[report_artifacts] 本机打开不可用（远程/桥接/无图形会话），只打印产物路径")
        echo("  [!] 当前为远程/无图形终端，服务器无法在手机或远端打开文件管理器。")
        _remote_hint(echo)
        return "unsupported"
    if not sys.stdin.isatty():
        return "skipped"  # 脚本/管道不阻塞：只列清单，交回菜单

    echo("  是否打开报告目录与报告？(y/N): ")
    if not _ask_open(key_reader or _get_key):
        echo("  未打开：可手动访问上方路径")
        return "skipped"

    targets = (output_dir, *artifacts)
    opened = open_artifacts(targets, opener=opener)
    if not opened:
        _OPEN_FAILED_IN_SESSION = True
        logger.warning("[report_artifacts] 本机打开失败，本会话不再尝试（后续报告只打印路径）")
        echo("  [!] 本机没有可用的图形桌面/未安装 xdg-open，打开失败——本会话不再询问。")
        _remote_hint(echo)
        return "failed"
    for path in opened:
        echo(f"  [OK] 已打开：{path}")
    return "opened"


def _local_open_supported() -> bool:
    """延迟导入本机桌面能力探测，避免非 TUI 场景加载 core.artifacts。"""
    from src.python.core.artifacts import local_open_supported

    return local_open_supported()


def _get_key() -> str:
    """读一个键（延迟导入，避免 TUI 键位模块在非终端环境被提前加载）。"""
    from src.python.tui.tui_keys import get_key

    return get_key()
