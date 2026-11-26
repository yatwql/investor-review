"""子进程入口执行器：`__main__` 守卫只能在新解释器里跑，覆盖数据需并回本进程。

入口守卫（``if __name__ == "__main__":``）在本进程内重跑会污染 ``sys.path``/
``sys.modules``（并可能重复注册 atexit 钩子），故一律子进程执行。但子进程的行
默认不计入本进程的覆盖量测——入口行于是恒显示「未覆盖」。本模块在子进程前加
一层 ``coverage run``，跑完把子进程数据 ``update`` 进当前 Coverage（若正在量测）。

`coverage` 不是运行时依赖（CI 测试 job 不装它），故缺失时静默退回「只执行不量测」：
用例断言照常生效，仅少了覆盖率归并。

**量测域必须与 pytest-cov 同域**（``SOURCE_PACKAGE_REL`` = ``src/python``）：域放宽到
``src`` 时子进程导入的 ``src/test`` 文件也会被记进覆盖数据，归并后把测试文件自身计入
语句总数，汇总口径当场失真（实测 TOTAL 语句数翻三倍、百分比降到 30%）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.python.core.constants import SOURCE_PACKAGE_REL


def _coverage_available() -> bool:
    try:
        import coverage  # noqa: F401
    except ImportError:
        return False
    return True


def _measured_source_root(cwd: Path) -> Path:
    """子进程覆盖量测域（源码包根），与 pytest-cov 的 ``--cov`` 同一域。"""
    return (Path(cwd) / SOURCE_PACKAGE_REL).resolve()


def _merge_child_data(data_file: Path, source_root: Path) -> None:
    """把子进程覆盖数据并入本进程当前量测（未在量测中则什么都不做）。

    只归并量测域（``source_root``）内的文件：子进程可能因 ``COVERAGE_*`` 环境变量或
    自身拉起的孙进程而记下域外文件（典型是 ``src/test``），无条件 ``update`` 会把这些
    文件塞进本进程的汇总口径，语句总数与覆盖率百分比同时失真。``CoverageData`` 没有
    「删除文件」接口（``purge_files`` 只清行列、文件仍列在 ``measured_files``），
    因此这里先构造一份只含域内文件的临时数据，再 ``update`` 进本进程。
    """
    import coverage

    current = coverage.Coverage.current()
    if current is None or not data_file.exists():
        return
    child_data = coverage.CoverageData(str(data_file))
    child_data.read()
    domain_prefix = str(source_root) + os.sep
    allowed = [f for f in child_data.measured_files() if f.startswith(domain_prefix)]
    kept: dict[str, object] = {}
    if child_data.has_arcs():
        kept = {f: arcs for f in allowed if (arcs := child_data.arcs(f))}
    else:
        kept = {f: lines for f in allowed if (lines := child_data.lines(f))}
    if not kept:
        return
    filtered = coverage.CoverageData()
    if child_data.has_arcs():
        filtered.add_arcs(kept)
    else:
        filtered.add_lines(kept)
    current.get_data().update(filtered)


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
    source_root = _measured_source_root(cwd)
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "entry_child.py"
        script.write_text(code, encoding="utf-8")
        data_file = Path(tmp) / "child.coverage"
        argv = [sys.executable]
        if measured:
            # --source 限定到源码包（与 pytest-cov 同域）：子进程临时脚本本身不进覆盖
            # 数据（否则临时目录被清掉后本进程 report 会报 No source for code），
            # 测试文件（src/test）也不进——它们是量测者，不是被量测的代码
            argv += [
                "-m",
                "coverage",
                "run",
                "--data-file",
                str(data_file),
                "--source",
                str(source_root),
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
            _merge_child_data(data_file, source_root)
        return completed
