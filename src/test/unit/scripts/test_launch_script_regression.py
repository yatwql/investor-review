"""测试：`scripts/launch.sh` 无参/缺省环境变量启动回归 — `set -u` 下不得引用未定义变量

回归场景：脚本在 `set -euo pipefail` 下裸引用 `$1`（无参调用）与 `$VENV_PATH`
（用户未设置该环境变量且无 `.venv`），bash 直接报 `unbound variable` 中止启动。
曾发生：参数解析段先于硬化提交存在（当时无 `set -u`，裸 `$1` 展开为空串无害），
后续「脚本加固」批次补 `set -euo pipefail` 时未实跑无参路径，缺陷穿过全部门禁
（十守护/CI 均为静态检查，从不执行启动脚本）。

用例策略：不真正创建虚拟环境——把 PATH 收窄到空目录（Python 探测失败、脚本
提前退出）或指向一次性 python 桩（使脚本推进到 venv 分支后被 `set -e` 终止），
在 tmp 工作目录中断言「已越过缺陷行」且 stderr 无 unbound variable。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LAUNCH_SH = _REPO_ROOT / "scripts" / "launch.sh"
_BASH = shutil.which("bash") or "/bin/bash"


@pytest.mark.unit
@pytest.mark.unit_scripts
class TestLaunchScriptUnboundVariableRegression:
    """`launch.sh` 在 `set -u` 下对可缺省变量的引用必须带默认值。"""

    def _run(
        self,
        tmp_path: Path,
        extra_env: dict[str, str] | None = None,
        args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess:
        env = {"PATH": str(tmp_path / "emptybin"), "HOME": str(tmp_path)}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [_BASH, str(_LAUNCH_SH), *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=30,
        )

    def test_no_args_without_python_does_not_hit_unbound_variable(self, tmp_path):
        """无参调用 + 无 Python：应报「未找到 Python」，而非 `$1` unbound variable。"""
        (tmp_path / "emptybin").mkdir()
        result = self._run(tmp_path)
        combined = result.stdout + result.stderr
        assert "unbound variable" not in combined, (
            f"launch.sh 在 set -u 下引用了未定义变量（裸 $1）：\n{combined}"
        )
        assert "未找到 Python" in result.stderr, f"应走到 Python 探测失败分支：\n{combined}"
        assert result.returncode == 1

    def test_no_venv_path_unset_does_not_hit_unbound_variable(self, tmp_path):
        """无 `.venv` + VENV_PATH 未设置：应进入本地 venv 创建分支，而非 `$VENV_PATH` unbound。"""
        bin_dir = tmp_path / "emptybin"
        bin_dir.mkdir()
        stub = bin_dir / "python3"
        stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        stub.chmod(0o755)
        result = self._run(tmp_path)  # 显式不传 VENV_PATH
        combined = result.stdout + result.stderr
        assert "unbound variable" not in combined, (
            f"launch.sh 在 set -u 下引用了未定义的 VENV_PATH：\n{combined}"
        )
        assert "正在创建本地虚拟环境" in result.stdout, (
            f"应越过 VENV_PATH 判断进入本地创建分支：\n{combined}"
        )

    @pytest.mark.parametrize("arg", ["web", "tui"])
    def test_entry_args_parse_with_python_missing(self, tmp_path, arg):
        """显式传 web/tui 时参数解析段同样不得 unbound（路径与无参一致，仅验证不崩）。"""
        (tmp_path / "emptybin").mkdir()
        result = self._run(tmp_path, args=(arg,))
        combined = result.stdout + result.stderr
        assert "unbound variable" not in combined
        assert "未找到 Python" in result.stderr
