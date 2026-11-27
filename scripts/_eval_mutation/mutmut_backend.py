"""可选后端 mutmut 的适配层（命令拼装 + 输出解析 + 可用性探测）。

默认后端是内置变异器（`runner.py`，无外部依赖）；mutmut 保留为 `--backend mutmut` 的可选
后端，但**需要 3.x 兼容配置**才真能跑（`[tool.mutmut]` 声明路径与测试命令并关掉它在
`mutants/` 子目录里的裸 `pytest`），缺配置时表现为 `collected 0 items` —— 故不默认。

本模块只做三件事，且全是纯函数/只读探测：不写文件、不触发变异。
"""

from __future__ import annotations

import re
import subprocess

from _eval_mutation.results import MutationCounts
from _eval_mutation.targets import MutationTarget

#: 可选后端模块名（未写入 requirements.txt，进入后端的入口负责给出安装提示）
BACKEND_MODULE = "mutmut"

#: 后端缺失时的安装提示（与项目虚拟环境口径一致）
INSTALL_COMMAND = ".venv/bin/python -m pip install mutmut（Windows：.venv\\Scripts\\python.exe -m pip install mutmut）"

#: mutmut 进度行：`3/40  🎉 2  ⏰ 0  🤔 0  🙁 1  🔇 0`
#: 依次为 killed / timeout / suspicious / survived / skipped，每行都是**累计值**
_PROGRESS_RE = re.compile(r"\d+/\d+\s+🎉\s*(\d+)\s+⏰\s*(\d+)\s+🤔\s*(\d+)\s+🙁\s*(\d+)\s+🔇\s*(\d+)")

#: 计数行备用口径：`killed: 12` / `survived = 3`（后端换输出格式或包装输出时仍可解析）
_KILLED_RE = re.compile(r"killed\s*[:=]\s*(\d+)", re.IGNORECASE)
_SURVIVED_RE = re.compile(r"survived\s*[:=]\s*(\d+)", re.IGNORECASE)


def _last_int(pattern: re.Pattern[str], text: str) -> int | None:
    """取最后一次匹配到的整数（多行刷新的输出以末行为准），无匹配返回 None。"""
    matches = pattern.findall(text)
    return int(matches[-1]) if matches else None


def parse_counts(output: str) -> MutationCounts | None:
    """从后端输出解析 killed / survived / timeout / errored 计数；认不出时返回 None。

    优先取**最后一条** mutmut 进度行（行内是累计值，多行刷新时末行才是终态，其中
    `suspicious` 归入 errored——它同样是「这次变异没被评上」）；无进度行时退回
    `killed:` / `survived:` 计数行（任一缺失即视为无数据）。
    """
    parsed: tuple[int, int, int, int] | None = None
    for match in _PROGRESS_RE.finditer(output):
        parsed = (int(match.group(1)), int(match.group(4)), int(match.group(2)), int(match.group(3)))
    if parsed is None:
        killed = _last_int(_KILLED_RE, output)
        survived = _last_int(_SURVIVED_RE, output)
        if killed is None or survived is None:
            return None
        parsed = (killed, survived, 0, 0)
    killed_count, survived_count, timed_out, errored = parsed
    return MutationCounts(
        killed=killed_count,
        survived=survived_count,
        timed_out=timed_out,
        errored=errored,
    )


def mutmut_command(target: MutationTarget, *, python_executable: str | None = None) -> list[str]:
    """目标切片 → mutmut 命令行（同一解释器起 `-m mutmut`，按路径切片逐个跑）。"""
    executable = python_executable or "python"
    return [executable, "-m", BACKEND_MODULE, "run", f"--paths-to-mutate={','.join(target.paths)}"]


def backend_available(*, python_executable: str | None = None, timeout: int = 60) -> bool:
    """后端是否已安装（`-c "import mutmut"` 探测，不触发任何变异、不写任何文件）。"""
    executable = python_executable or "python"
    try:
        completed = subprocess.run(
            [executable, "-c", f"import {BACKEND_MODULE}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0
