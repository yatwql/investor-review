"""启动脚本解释器选择：不得依赖 `.venv/*/activate`（venv 移动后激活静默失效）。

回归场景：`.venv` 由外部环境软链而来后目录被改名/搬家，而 `activate` 内烘焙的是
**创建时**的绝对 `VIRTUAL_ENV` 路径。`source .venv/bin/activate` 只是把这个不存在的
目录前置进 PATH——激活「成功」但 PATH 实际未变，随后脚本里裸 `python3` 落到系统
解释器（无 pandas），表现为跑到数据准备阶段才 `ModuleNotFoundError: No module
named 'pandas'`，整份 full 报告失败。

修复口径：脚本直接调用 `.venv` 内解释器（路径与 venv 位置无关），并在启动前用该
解释器 import 重依赖做硬闸（缺依赖立即给可读错误，不进入报告管线）。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LAUNCH_SH = _REPO_ROOT / "scripts" / "launch.sh"
_BASH = shutil.which("bash") or "/bin/bash"

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _stub_interpreter(passthrough: bool = True) -> str:
    """构造 .venv 解释器桩：记录被调用路径后转交真实解释器。

    Args:
        passthrough: True 时把 ``-c`` 原样转交真实解释器；False 时让 pandas 探测失败
            （模拟「.venv 半装」现场）。

    为什么用 shell 桩而非符号链接：符号链接进一个没有 ``pyvenv.cfg`` 的目录时，
    CPython 按「可执行文件所在目录」找 pyvenv.cfg，找不到即退回系统模式（不认宿主
    venv），桩会真的缺 pandas，用例就测不出解释器选择。
    """
    if not passthrough:
        return (
            '#!/bin/sh\nexport LAUNCH_INTERPRETER="$0"\n'
            'if [ "$1" = "-c" ]; then\n'
            '  case "$2" in\n    *pandas*) echo "No module named pandas" >&2; exit 1 ;;\n  esac\n'
            'fi\nexec __REAL__ "$@"\n'
        )
    return '#!/bin/sh\nexport LAUNCH_INTERPRETER="$0"\nexec __REAL__ "$@"\n'


def _project(tmp_path: Path, *, interpreter_wrapper: str | None = None) -> None:
    """构造 tmp 项目：.venv 内的解释器桩 + 依赖标记 + 打印解释器的 tui 入口。

    Args:
        interpreter_wrapper: shell 解释器桩内容（``__REAL__`` 由真实解释器替换）；
            缺省用「记录调用路径后转交真实解释器」的桩。
    """
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("packaging>=20\n", encoding="utf-8")

    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_py = venv_bin / "python"
    venv_py.write_text(
        (interpreter_wrapper or _stub_interpreter()).replace("__REAL__", sys.executable), encoding="utf-8"
    )
    venv_py.chmod(0o755)
    # activate 桩：烘焙一个已不存在的 VIRTUAL_ENV（模拟 venv 被移动后的现场）
    (venv_bin / "activate").write_text(
        'export VIRTUAL_ENV="/nonexistent/moved/venv"\nPATH="$VIRTUAL_ENV/bin:$PATH"\nexport PATH\n',
        encoding="utf-8",
    )
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    (tmp_path / ".venv" / ".deps_installed").write_text(digest, encoding="utf-8")

    entry = tmp_path / "src" / "python" / "tui"
    entry.mkdir(parents=True)
    (entry / "tui.py").write_text(
        # 不用 f-string：表达式中含引号在 Python 3.11（PEP 701 之前）是 SyntaxError
        "import os\nprint('LAUNCHED_BY=' + os.environ.get('LAUNCH_INTERPRETER', ''))\n",
        encoding="utf-8",
    )


def _run(tmp_path: Path) -> subprocess.CompletedProcess:
    """在 tmp 项目里执行 launch.sh；PATH 前置的系统 python 桩一旦被用即留痕。"""
    stub_bin = tmp_path / "system_bin"
    stub_bin.mkdir(exist_ok=True)
    for name in ("python", "python3"):
        stub = stub_bin / name
        stub.write_text("#!/bin/sh\necho SYSTEM_PYTHON_USED\nexit 3\n", encoding="utf-8")
        stub.chmod(0o755)
    env = {"PATH": f"{stub_bin}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(tmp_path)}
    return subprocess.run(
        [_BASH, str(_LAUNCH_SH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )


class TestLaunchUsesVenvInterpreter:
    def test_stale_activate_does_not_fall_back_to_system_python(self, tmp_path):
        """activate 烘焙的 VIRTUAL_ENV 已失效时，仍须用 .venv 解释器启动入口。"""
        _project(tmp_path)
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert "SYSTEM_PYTHON_USED" not in combined, f"启动路径回退到了系统解释器：\n{combined}"
        assert "虚拟环境解释器: .venv/bin/python" in result.stdout, combined
        assert "LAUNCHED_BY=.venv/bin/python" in result.stdout, f"入口应由 tmp 项目的 .venv 解释器执行：\n{combined}"


class TestLaunchDependencyGate:
    def test_missing_heavy_dependency_aborts_before_pipeline(self, tmp_path):
        """`.venv` 解释器缺 pandas/numpy：启动前硬闸给出可读错误并中止。"""
        _project(tmp_path, interpreter_wrapper=_stub_interpreter(passthrough=False))
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 1, combined
        assert "缺少关键依赖" in result.stderr, combined
        assert "requirements.txt" in result.stderr, f"错误提示须给出修复命令：\n{combined}"
        assert "LAUNCHED_BY" not in result.stdout, f"缺依赖时不得进入应用管线：\n{combined}"
