"""ruff 排除域契约：`docs/`（归档快照）冻结，显式传路径也不得被重排。

背景（回归场景）：`pyproject.toml` 早已声明 `extend-exclude = [".venv", "docs"]`，
但 ruff 的 `exclude` 只在**整树扫描**时生效；命令行显式给出目录（如
`ruff format docs`）会绕过它，把 `docs/archive/` 下的历史脚本一并重排，使归档快照
漂移（实测曾误改 7 个文件，只能靠 `git checkout` 还原）。修复是在配置里加
`force-exclude = true`——让 exclude 对显式路径同样生效。

本文件锁两件事：① 配置声明仍是「docs 排除 + force-exclude」；② 行为上
`ruff format <docs>` 找不到任何 Python 文件（即归档真的没被纳入格式化域）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = REPO_ROOT / "pyproject.toml"

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _ruff_cfg() -> dict:
    with open(_PYPROJECT, "rb") as f:
        return tomllib.load(f)["tool"]["ruff"]


class TestRuffExcludeContract:
    """配置面：docs 在排除域内，且对显式路径强制生效。"""

    def test_docs_is_excluded(self):
        excluded = _ruff_cfg().get("extend-exclude") or []
        assert "docs" in excluded, "docs/ 下为归档快照，必须排除在 lint/format 之外"

    def test_force_exclude_enabled(self):
        """缺 force-exclude 时 `ruff format docs` 会绕过 exclude 重排归档脚本。"""
        assert _ruff_cfg().get("force-exclude") is True


class TestRuffArchiveBehaviour:
    """行为面：显式传 docs 路径时 ruff 认不到任何 Python 文件。"""

    @staticmethod
    def _ruff() -> str | None:
        candidate = REPO_ROOT / ".venv" / "bin" / "ruff"
        if candidate.is_file():
            return str(candidate)
        if (REPO_ROOT / ".venv" / "Scripts" / "ruff.exe").is_file():
            return str(REPO_ROOT / ".venv" / "Scripts" / "ruff.exe")
        return shutil.which("ruff") or (sys.executable and None)

    def test_format_with_explicit_docs_path_finds_nothing(self):
        ruff = self._ruff()
        if not ruff:
            pytest.skip("未找到 ruff 可执行文件")
        completed = subprocess.run(
            [ruff, "format", "docs"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        combined = completed.stdout + completed.stderr
        assert "No Python files found" in combined, f"归档脚本被纳入格式化域：{combined.strip()[:200]}"

    def test_check_with_explicit_docs_path_passes_clean(self):
        ruff = self._ruff()
        if not ruff:
            pytest.skip("未找到 ruff 可执行文件")
        completed = subprocess.run(
            [ruff, "check", "docs"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert completed.returncode == 0, completed.stdout[-400:]
