"""发布编排共享原语：命令异常与子进程执行。"""

from __future__ import annotations

import subprocess
from pathlib import Path


class ReleaseError(RuntimeError):
    """命令无法继续（预检不过 / 输入不符合契约）；消息即用户可读原因。"""


def exec_command(cmd: list[str], root: Path, runner=None, capture: bool = True) -> tuple[int, str, str]:
    """执行外部命令（显式 UTF-8 解码，避免非 UTF-8 locale 下的隐式编码）。"""
    if runner is not None:
        return runner.run(cmd, root, capture=capture)
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(root),
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""
