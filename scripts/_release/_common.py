"""发布编排共享原语：命令异常与子进程执行。"""

from __future__ import annotations

import subprocess
from pathlib import Path


class ReleaseError(RuntimeError):
    """命令无法继续（预检不过 / 输入不符合契约）；消息即用户可读原因。"""


def exec_command(
    cmd: list[str],
    root: Path,
    runner=None,
    capture: bool = True,
    timeout: int = 600,
) -> tuple[int, str, str]:
    """执行外部命令（显式 UTF-8 解码，避免非 UTF-8 locale 下的隐式编码）。

    `timeout` 默认 600s（git push/fetch 走网络，需留裕量）：卡死的命令会把发布
    编排挂成无输出等待，故一律设限，超时将 `ReleaseError` 抛给调用方（消息即原因）。
    """
    if runner is not None:
        return runner.run(cmd, root, capture=capture)
    try:
        proc = subprocess.run(
            [str(c) for c in cmd],
            cwd=str(root),
            encoding="utf-8",
            errors="replace",
            capture_output=capture,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(f"命令超时（{timeout}s）：{' '.join(str(c) for c in cmd)}") from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""
