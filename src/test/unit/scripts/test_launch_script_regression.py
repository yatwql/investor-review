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

import os
import shutil
import subprocess
import sys
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
        assert "unbound variable" not in combined, f"launch.sh 在 set -u 下引用了未定义变量（裸 $1）：\n{combined}"
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
        assert "unbound variable" not in combined, f"launch.sh 在 set -u 下引用了未定义的 VENV_PATH：\n{combined}"
        assert "正在创建本地虚拟环境" in result.stdout, f"应越过 VENV_PATH 判断进入本地创建分支：\n{combined}"

    @pytest.mark.parametrize("arg", ["web", "tui"])
    def test_entry_args_parse_with_python_missing(self, tmp_path, arg):
        """显式传 web/tui 时参数解析段同样不得 unbound（路径与无参一致，仅验证不崩）。"""
        (tmp_path / "emptybin").mkdir()
        result = self._run(tmp_path, args=(arg,))
        combined = result.stdout + result.stderr
        assert "unbound variable" not in combined
        assert "未找到 Python" in result.stderr


@pytest.mark.unit
@pytest.mark.unit_scripts
class TestLaunchScriptReadOnlyVenvRegression:
    """只读外部虚拟环境下启动不得因「依赖标记写不进去」而中止。

    回归场景：`.venv` 符号链接到他人所有（或只读挂载）的外部环境时，依赖标记
    `.venv/.deps_installed` 不可写——requirements.txt 一旦变更，脚本会先跑 pip
    （依赖已满足时不写盘、正常退出），随后 `echo "$REQ_HASH" > "$DEPS_MARKER"`
    报 `Permission denied` 并因 `set -e` 中断启动。本组用例锁定契约：标记须退回
    项目本地 `data/cache/`，只读环境按 `requirements.txt` 校验已装版本而不跑 pip。
    """

    def _make_readonly_venv_project(self, tmp_path: Path, requirement: str) -> dict[str, str]:
        """构造 tmp 项目：只读 `.venv`（含 activate 桩）+ 可执行的 python 桩（真解释器）。"""
        venv = tmp_path / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "activate").write_text("# stub\n", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text(requirement + "\n", encoding="utf-8")
        # python/python3 桩指向当前测试解释器：版本检查与依赖校验均需真实执行
        for name in ("python", "python3"):
            (tmp_path / "stub_bin").mkdir(exist_ok=True)
            (tmp_path / "stub_bin" / name).symlink_to(sys.executable)
        venv.chmod(0o555)
        return {
            "PATH": f"{tmp_path / 'stub_bin'}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(tmp_path),
        }

    def test_readonly_venv_writes_marker_to_project_cache(self, tmp_path):
        """只读 venv + 依赖已满足：标记落到 data/cache，启动越过依赖段（无 Permission denied）。"""
        if os.geteuid() == 0:
            pytest.skip("root 无视目录权限，只读场景不可构造")
        env = self._make_readonly_venv_project(tmp_path, "packaging>=20")
        try:
            result = subprocess.run(
                [_BASH, str(_LAUNCH_SH)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=120,
            )
        finally:
            (tmp_path / ".venv").chmod(0o755)
        combined = result.stdout + result.stderr
        assert "Permission denied" not in combined, f"只读 venv 不应因写标记中止启动：\n{combined}"
        assert "依赖校验通过" in result.stdout, f"应走到依赖版本校验分支：\n{combined}"
        marker = tmp_path / "data" / "cache" / ".deps_installed"
        assert marker.is_file(), f"依赖标记应回退到 data/cache：\n{combined}"

    def test_readonly_venv_reports_missing_dependency_explicitly(self, tmp_path):
        """只读 venv + 依赖缺失：给出可读报错与安装命令，而非 pip 权限失败。"""
        if os.geteuid() == 0:
            pytest.skip("root 无视目录权限，只读场景不可构造")
        env = self._make_readonly_venv_project(tmp_path, "definitely-absent-pkg-xyz==1.0.0")
        try:
            result = subprocess.run(
                [_BASH, str(_LAUNCH_SH)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=120,
            )
        finally:
            (tmp_path / ".venv").chmod(0o755)
        combined = result.stdout + result.stderr
        assert "Permission denied" not in combined, f"应报依赖缺失而非权限失败：\n{combined}"
        assert "依赖不满足 requirements.txt" in result.stderr, combined
        assert "definitely-absent-pkg-xyz" in result.stderr, combined
        assert result.returncode == 1
