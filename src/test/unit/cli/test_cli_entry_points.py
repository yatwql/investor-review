"""CLI 两个进程入口的行为契约：退出码传回 shell、直跑脚本自补项目根到 sys.path。

`python -m src.python.cli` 与 `python src/python/cli/cli.py` 都必须
  - 以 ``run_cli()`` 的退出码结束进程（脚本化调用靠它判成败）；
  - 直跑脚本时把项目根插入 ``sys.path``（否则 `from src.python.…` 直接 ImportError）。

两条入口用 ``runpy`` 在进程内以 ``__main__`` 身份执行，既覆盖到入口守卫，
又不必另起解释器（子进程覆盖不计入本进程覆盖率）。
"""

from __future__ import annotations

import os
import runpy
import sys

import pytest

from src.python.core.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]

_CLI_SCRIPT = os.path.join(PROJECT_ROOT, "src", "python", "cli", "cli.py")


@pytest.mark.parametrize(
    ("argv", "expected_code"),
    [
        (["cli.py", "--help"], 0),
        (["cli.py"], 2),
    ],
)
def test_direct_script_entry_propagates_exit_code(monkeypatch, argv, expected_code):
    """直跑 cli.py：入口守卫触发 run_cli()，argparse 退出码原样传回。"""
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(_CLI_SCRIPT, run_name="__main__")
    assert exc.value.code == expected_code


def test_direct_script_inserts_project_root_into_sys_path(monkeypatch):
    """项目根不在 sys.path 时，脚本自身补插——后续 `from src.python…` 才成立。"""
    root = str(PROJECT_ROOT)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if os.path.abspath(p or ".") != root])
    monkeypatch.setattr(sys, "argv", ["cli.py", "--help"])
    assert root not in sys.path

    with pytest.raises(SystemExit):
        runpy.run_path(_CLI_SCRIPT, run_name="__main__")

    assert root in sys.path


def test_module_entry_runs_cli(monkeypatch):
    """`python -m src.python.cli` 等价路径：run_name=__main__ → run_cli() 执行。"""
    monkeypatch.setattr(sys, "argv", ["src.python.cli", "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("src.python.cli", run_name="__main__")
    assert exc.value.code == 0
