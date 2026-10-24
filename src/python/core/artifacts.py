"""报告产物定位与「用系统程序打开」（三渠道共用）。

职责边界：
- **只读定位**：``output_dir`` 下最新的 HTML / Excel 产物，存在才收（不生成、不写盘）；
- **打开动作**平台分派（Windows ``os.startfile`` / macOS ``open`` / Linux ``xdg-open``），
  失败不抛异常、由调用方回退为「手动访问路径」提示。

渠道差异只体现在**怎么用**：TUI 询问单键 ``y/N`` 打开、CLI 打印清单（可选打开）、
Web 提供下载与可复制路径——定位与打开语义单源在此，避免各渠道各写一份。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from src.python.core.constants import LATEST_HTML_NAME, LATEST_XLSX_NAME

logger = logging.getLogger("invest")

#: 打开动作的超时（秒）：守卫系统命令缺失/挂起，失败按「未打开」降级
OPEN_TIMEOUT = 5.0


def collect_artifacts(config: dict | None, output_dir: str | None = None) -> tuple[Path, ...]:
    """收集输出目录下已存在的最新产物（先 HTML 后 Excel，缺失者跳过）。

    Args:
        config: 配置快照（读 ``output_dir``）。
        output_dir: 显式覆盖（如 CLI ``--output``）；None/空串按配置解析。

    Returns:
        存在的产物路径元组；一个都没有时为空元组（调用方据此跳过展示）。
    """
    from src.python.config import resolve_output_dir

    output_dir = Path(resolve_output_dir(config, output_dir))
    candidates = (output_dir / LATEST_HTML_NAME, output_dir / LATEST_XLSX_NAME)
    return tuple(path for path in candidates if path.is_file())


#: 透过客户端桥接的远程会话环境变量（画面在用户设备上，服务端 "桌面" 只是桥）
_BRIDGED_SESSION_ENV = ("CATLINK_SESSION_DIR", "CATLINK_SOCKET_DIR", "XPRA_DISPLAY", "XPRA_SESSION")


def _x11_socket_present(display: str) -> bool:
    """`DISPLAY` 声称有桌面时，确认对应 X socket 真的存在。

    残留环境变量比缺失更常见：手机上连服务器时，进程继承的是**建立会话时**的
    环境（tmux/screen 服务端、后台常驻启动器），`DISPLAY=:0` 还在、桌面早已不在。
    只凭环境变量判定会让收尾去跑 `xdg-open` 而后失败（用户看到「打开失败」）。
    远端 X（X forwarding，`host` 非空的形式）由客户端承载，不查本地 socket。
    """
    host, _, screen = display.rpartition(":")
    if not screen:
        return False
    if host and host != "unix":
        return True
    number = screen.split(".")[0]
    if not number.isdigit():
        return False
    return Path(f"/tmp/.X11-unix/X{number}").exists()


def _opener_present() -> bool:
    """`xdg-open` 是否可执行（没有它时 `open_path` 必然失败，不如不问）。"""
    return shutil.which("xdg-open") is not None


def local_open_supported() -> bool:
    """当前会话能否在**本机桌面**打开文件管理器/默认程序。

    远程 SSH/mosh、无 DISPLAY/WAYLAND 的服务端无法把文件管理器投到手机或远端
    客户端；此时调用 xdg-open/open 只会失败，调用方应展示路径与传输指引。

    判定比「看环境变量是否有值」更严：Linux 上除 `DISPLAY`/`WAYLAND_DISPLAY`
    非空，还要求 X socket 真实存在且 `xdg-open` 可执行——残留的 `DISPLAY`
    （tmux/screen 服务端保留的旧桌面环境）与缺工具都不算可开。手机/云桌面
    桥接会话（Catlink / Xpra 类）同样不算：画面在用户设备上，服务端的
    “桌面”只是桥，`xdg-open` 转发到客户端经常无响应或报错。
    """
    if any(os.environ.get(key) for key in ("SSH_CONNECTION", "SSH_TTY", "MOSH_CONNECTION")):
        return False
    if any(os.environ.get(key) for key in _BRIDGED_SESSION_ENV):
        return False
    if sys.platform.startswith("linux"):
        if os.environ.get("WAYLAND_DISPLAY"):
            return _opener_present()
        display = os.environ.get("DISPLAY") or ""
        if not display:
            return False
        if not _x11_socket_present(display):
            logger.info("[artifacts] DISPLAY=%s 但无对应 X socket（残留环境变量），按无图形会话处理", display)
            return False
        return _opener_present()
    return True


def open_path(path: Path) -> bool:
    """用系统默认程序打开路径；成功返回 True，任何失败（含命令缺失）返回 False。

    子进程 stdout/stderr 一律丢弃：TUI 是逐行刷新的文本界面，把 `xdg-open`
    包装脚本/桌面转发器的报错直接写回终端会打乱布局（远程桥接会话常见），
    失败只记日志并由调用方给一行中文提示。
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]  # Windows 专用
            return True
        command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        completed = subprocess.run(
            command,
            check=False,
            timeout=OPEN_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            logger.warning("[artifacts] %s 返回码 %s，未能打开 %s", command[0], completed.returncode, path)
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:  # 无图形环境/命令缺失/超时
        logger.warning("[artifacts] 打开失败 %s: %s", path, e)
        return False


def open_artifacts(paths: tuple[Path, ...], *, opener: Callable[[Path], bool] | None = None) -> list[Path]:
    """逐个打开路径，返回**成功**打开的清单（失败者由调用方提示手动访问）。"""
    open_one = opener or open_path
    return [path for path in paths if open_one(path)]
