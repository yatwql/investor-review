"""依赖声明单源契约：`pyproject` 运行时依赖 ↔ `requirements.txt` 逐字一致。

背景（回归场景）：两份清单长期各自演进——`akshare` 在 requirements.txt 是
`>=1.16,<2.0`、在 pyproject 是 `==1.18.64`；`pdfplumber` 同理（`>=0.11,<1.0` vs
固定补丁版）；`h2` 只在 requirements.txt 出现。于是「启动脚本装环境」与
「`pip install .`」得到两套依赖解析结果，行为差异无法复现也无法归因。

本文件锁三件事：

① `[project].dependencies` 的每条依赖都在 requirements.txt 同名存在，且版本说明符
   **逐字相同**（区间/钉死策略不得各写一套）；
② requirements.txt 里不在运行时依赖表中的包必须在 `_EXTRAS_ONLY` 白名单内并写明
   归属（传递依赖锁定 / 开发工具 / extras），新增运行时直接依赖只改一处即被拦下；
③ requirements.txt 仍为 UTF-8 with BOM（pip ≤24.x 在 cp936 locale 的解析前提）。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = REPO_ROOT / "pyproject.toml"
_REQUIREMENTS = REPO_ROOT / "requirements.txt"

#: 允许只出现在 requirements.txt 的包 → 归属说明（新增条目必须先判断属于哪一类）。
_EXTRAS_ONLY = {
    "werkzeug": "flask 传递依赖锁定",
    "itsdangerous": "flask 传递依赖锁定",
    "click": "flask 传递依赖锁定",
    "blinker": "flask 传递依赖锁定",
    "colorama": "pyproject extras「color」",
    "pillow": "pyproject extras「svg」（scripts 的 SVG 像素审查）",
    "pytest": "开发/工具依赖（pyproject extras「test」）",
    "pytest-mock": "开发/工具依赖（pyproject extras「test」）",
    "pytest-xdist": "开发/工具依赖（pyproject extras「test」）",
    "pytest-html": "开发/工具依赖（pyproject extras「test」）",
}

_REQ_LINE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$")

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _canonical(name: str) -> str:
    """PEP 503 规范名：大小写/下划线/点归一，避免 `pytest-mock` 与 `pytest_mock` 误判不同包。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement_line(raw_line: str) -> tuple[str, str] | None:
    """解析一行 requirement → (规范名, 说明符)；注释/空行/选项行返回 None。"""
    line = raw_line.split("#", 1)[0].strip()
    if not line or line.startswith("-"):
        return None
    match = _REQ_LINE.match(line)
    if not match:
        return None
    return _canonical(match.group("name")), match.group("spec").strip()


def _requirements_entries() -> dict[str, str]:
    """requirements.txt → {规范名: 说明符}。"""
    text = _REQUIREMENTS.read_bytes().decode("utf-8-sig")
    entries: dict[str, str] = {}
    for raw_line in text.splitlines():
        parsed = _parse_requirement_line(raw_line)
        if parsed is not None:
            entries[parsed[0]] = parsed[1]
    return entries


def _pyproject_runtime_entries() -> dict[str, str]:
    """`[project].dependencies` → {规范名: 说明符}。"""
    with open(_PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    entries: dict[str, str] = {}
    for spec in data["project"]["dependencies"]:
        parsed = _parse_requirement_line(spec)
        assert parsed is not None, f"pyproject 依赖项无法解析：{spec!r}"
        entries[parsed[0]] = parsed[1]
    return entries


def test_runtime_dependency_specs_match_requirements() -> None:
    """运行时直接依赖的说明符必须两侧逐字一致（区间/钉死策略不得各写一套）。"""
    runtime = _pyproject_runtime_entries()
    requirements = _requirements_entries()
    assert runtime, "pyproject 未声明任何运行时依赖，本契约失去意义"

    drift = []
    for name, spec in sorted(runtime.items()):
        if name not in requirements:
            drift.append(f"{name}: 仅见于 pyproject（{spec}），requirements.txt 缺失")
        elif requirements[name] != spec:
            drift.append(f"{name}: pyproject={spec!r} vs requirements.txt={requirements[name]!r}")
    assert not drift, "运行时依赖约束漂移：\n  " + "\n  ".join(drift)


def test_requirements_extras_are_whitelisted() -> None:
    """requirements.txt 的额外包必须显式归类（新增运行时直接依赖只改一处即被拦下）。"""
    runtime = _pyproject_runtime_entries()
    unclassified = sorted(name for name in _requirements_entries() if name not in runtime and name not in _EXTRAS_ONLY)
    assert not unclassified, (
        "requirements.txt 出现未分类的包："
        f"{unclassified}\n  若是运行时直接依赖 → 同步写进 pyproject 的 [project].dependencies；"
        "若是传递锁定/开发工具 → 加进本用例的 _EXTRAS_ONLY 并写明归属"
    )


def test_extras_whitelist_has_no_stale_entries() -> None:
    """白名单不得挂空条目（包已移出 requirements.txt 后必须同步清理）。"""
    requirements = _requirements_entries()
    stale = sorted(name for name in _EXTRAS_ONLY if name not in requirements)
    assert not stale, f"_EXTRAS_ONLY 存在已不在 requirements.txt 的条目：{stale}"


def test_requirements_keeps_utf8_bom() -> None:
    """requirements.txt 必须是 UTF-8 with BOM（中文注释在 cp936 locale 的解析前提）。"""
    assert _REQUIREMENTS.read_bytes().startswith(b"\xef\xbb\xbf"), (
        "requirements.txt 丢失 BOM：pip ≤24.x 在中文 Windows 上会按 cp936 解码含中文注释的"
        "文件并抛 UnicodeDecodeError，启动脚本装依赖中断"
    )
