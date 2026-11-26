"""子进程入口执行器：`__main__` 守卫只能在新解释器里跑，覆盖数据需并回本进程。

入口守卫（``if __name__ == "__main__":``）在本进程内重跑会污染 ``sys.path``/
``sys.modules``（并可能重复注册 atexit 钩子），故一律子进程执行。但子进程的行
默认不计入本进程的覆盖量测——入口行于是恒显示「未覆盖」。本模块在子进程前加
一层 ``coverage run``，跑完把子进程数据 ``update`` 进当前 Coverage（若正在量测）。

`coverage` 不是运行时依赖（CI 测试 job 不装它），故缺失时静默退回「只执行不量测」：
用例断言照常生效，仅少了覆盖率归并。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _coverage_available() -> bool:
    try:
        import coverage  # noqa: F401
    except ImportError:
        return False
    return True


def _merge_child_data(data_file: Path) -> None:
    """把子进程覆盖数据并入本进程当前量测（未在量测中则什么都不做）。"""
    import coverage

    current = coverage.Coverage.current()
    if current is None or not data_file.exists():
        return
    child_data = coverage.CoverageData(str(data_file))
    child_data.read()
    current.get_data().update(child_data)


def run_entry_child(code: str, *, cwd: Path, timeout: float = 180) -> subprocess.CompletedProcess:
    """在子进程里以脚本方式执行 ``code``（``__main__`` 入口的等价跑法）。

    Args:
        code: 子进程脚本正文（自行决定如何调用入口）。
        cwd: 子进程工作目录（通常为项目根）。
        timeout: 超时秒数。

    Returns:
        子进程结果（stdout/stderr 为 utf-8 文本）。

    子进程的 ``PYTHONPATH`` 指向 ``cwd``，故脚本可在摘下项目根之前完成导入；
    入口自身的「自动补项目根」分支由脚本自行 `sys.path` 摘除后触达。
    """
    measured = _coverage_available()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "entry_child.py"
        script.write_text(code, encoding="utf-8")
        data_file = Path(tmp) / "child.coverage"
        argv = [sys.executable]
        if measured:
            # --source 限定到项目源码：子进程临时脚本本身不进覆盖数据，
            # 否则临时目录被清掉后本进程 report 会报 No source for code
            argv += [
                "-m",
                "coverage",
                "run",
                "--data-file",
                str(data_file),
                "--source",
                str(Path(cwd) / "src"),
            ]
        argv.append(str(script))
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(cwd)},
        )
        if measured:
            _merge_child_data(data_file)
        return completed
