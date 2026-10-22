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
import subprocess
import sys
from pathlib import Path
from typing import Callable

from src.python.core.constants import LATEST_HTML_NAME, LATEST_XLSX_NAME

logger = logging.getLogger("invest")

#: 打开动作的超时（秒）：守卫系统命令缺失/挂起，失败按「未打开」降级
OPEN_TIMEOUT = 5.0


def collect_artifacts(config: dict | None) -> tuple[Path, ...]:
    """收集 ``output_dir`` 下已存在的最新产物（先 HTML 后 Excel，缺失者跳过）。

    Returns:
        存在的产物路径元组；一个都没有时为空元组（调用方据此跳过展示）。
    """
    from src.python.config import resolve_output_dir

    output_dir = Path(resolve_output_dir(config))
    candidates = (output_dir / LATEST_HTML_NAME, output_dir / LATEST_XLSX_NAME)
    return tuple(path for path in candidates if path.is_file())


def open_path(path: Path) -> bool:
    """用系统默认程序打开路径；成功返回 True，任何失败（含命令缺失）返回 False。"""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]  # Windows 专用
            return True
        command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        return subprocess.run(command, check=False, timeout=OPEN_TIMEOUT).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:  # 无图形环境/命令缺失/超时
        logger.debug("[artifacts] 打开失败 %s: %s", path, e)
        return False


def open_artifacts(paths: tuple[Path, ...], *, opener: Callable[[Path], bool] | None = None) -> list[Path]:
    """逐个打开路径，返回**成功**打开的清单（失败者由调用方提示手动访问）。"""
    open_one = opener or open_path
    return [path for path in paths if open_one(path)]
