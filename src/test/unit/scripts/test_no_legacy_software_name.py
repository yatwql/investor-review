"""软件名/仓库名残留守卫：旧名 `investor-util` / `investor_util` 不得出现在运行面。

口径：运行面与现行文档统一使用 `investor-review`（`investor-util` / `investor_util`
仅允许出现在历史归档与 changelog 这类记录里）。旧名若残留在运行时字符串
（localStorage 键、User-Agent、egg-info）或代码/文档，会表现为「旧路径 traceback /
旧存储键 / 旧包名」，排查时误导。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

REPO_ROOT = Path(__file__).resolve().parents[4]
_LEGACY = ("investor-util", "investor_util")


def _candidate_files() -> list[Path]:
    files: list[Path] = [REPO_ROOT / "README.md", REPO_ROOT / "pyproject.toml"]
    for sub in ("src", "scripts", "docs/manuals", "docs/managements"):
        files.extend(p for p in (REPO_ROOT / sub).rglob("*") if p.is_file())
    return [
        p
        for p in files
        if p.suffix in {".py", ".js", ".md", ".ps1", ".sh", ".toml", ".html", ".css", ".json"}
        and "docs/archive" not in p.as_posix()
        and p.name != "changelog.md"
        and "__pycache__" not in p.parts
        and p.name != Path(__file__).name  # 本用例自身含旧名字面量
    ]


class TestNoLegacySoftwareName:
    def test_runtime_surface_has_no_legacy_name(self):
        offenders = []
        for path in _candidate_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(token in text for token in _LEGACY):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
        assert offenders == [], "旧软件名残留（运行时/文档面）：\n" + "\n".join(f"  - {x}" for x in offenders)
