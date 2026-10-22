"""已删除函数残留检查（CODE）：文档反引号引用的函数当前无 def、但 git 历史有。

本模块自带 git 历史/当前 def 两套进程级缓存与其实现，入口 `check-doc-traces.py`
只做扫描编排并按原面 re-export。测试若要重置缓存或替换 `subprocess`，patch 必须
指向本模块（调用点在此），指向入口模块不会生效。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from _shared.checklib import REPO_ROOT

from _traces_doc import _read_doc_impl


_DELETED_CAND_RE = re.compile(r"`([a-z_][a-z0-9_]{7,})(?:\([^)`]*\)|`)")
_HIST_DEFS: set[str] | None = None
_CUR_DEFS: set[str] | None = None


def _historical_defs() -> set[str]:
    """git 历史中曾定义过的 def 名全集（单 pass `git log -p` 新增行提取，约 1s）。

    仅 src/ 与 scripts/（文档引用的都是生产/脚本函数）。git 不可用或**浅克隆**
    （fetch-depth=1：HEAD 被视作根提交，输出全部现存代码，历史集≈当前集导致
    全漏报）时返回空集并 stderr 告警（不静默假绿）。模块级缓存，同次进程只算一次。
    """
    global _HIST_DEFS
    if _HIST_DEFS is None:
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=REPO_ROOT,
        )
        if shallow.returncode != 0 or shallow.stdout.strip() == "true":
            print("[!] 浅克隆/git 不可用环境：已删函数残留检查跳过（需 fetch-depth=0 全历史）", file=sys.stderr)
            _HIST_DEFS = set()
        else:
            result = subprocess.run(
                ["git", "log", "--format=", "-p", "--unified=0", "--", "src", "scripts"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=REPO_ROOT,
            )
            _HIST_DEFS = (
                {
                    m.group(1)
                    for line in result.stdout.splitlines()
                    if (m := re.match(r"^\+ *(?:async )?def ([a-z_]\w*)\(", line))
                }
                if result.returncode == 0
                else set()
            )
    return _HIST_DEFS


def _current_defs() -> set[str]:
    """当前代码 def 名全集（src/ 与 scripts/，含缩进方法）。模块级缓存。"""
    global _CUR_DEFS
    if _CUR_DEFS is None:
        defs: set[str] = set()
        for root in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
            for p in root.rglob("*.py"):
                try:
                    defs.update(
                        re.findall(
                            r"^[ \t]*(?:async )?def (\w+)\(", p.read_text(encoding="utf-8", errors="replace"), re.M
                        )
                    )
                except OSError:
                    continue
        _CUR_DEFS = defs
    return _CUR_DEFS


def scan_deleted_symbol_refs(
    doc: Path, *, historical_defs: set[str] | None = None, current_defs: set[str] | None = None
) -> list[tuple[int, str, str, str]]:
    """单文档已删除函数残留：反引号引用的函数名当前无 def 但 git 历史有 → CODE。

    覆盖「函数删除后文档未同步」类残留。候选须含下划线且总长 ≥8（文档引用函数
    必为多段蛇形；`append`/`read_text` 类单段常用词不误伤）。仅常规文档适用
    （历史记录类文档由调用方限定，天然豁免）。
    结论缓存仅随文档/脚本变更失效——纯代码提交中删除的函数，其残留可能延至下次
    文档变更才被检出（自愈窗口，可接受）。

    ``historical_defs`` / ``current_defs``：测试注入（默认走 git 与全仓扫描，进程级缓存）。
    """
    hist = historical_defs if historical_defs is not None else _historical_defs()
    if not hist:
        return []  # git 不可用/历史为空 → 静默跳过
    cur = current_defs if current_defs is not None else _current_defs()
    text = _read_doc_impl(doc)
    if text is None:
        return []
    hits: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name in set(_DELETED_CAND_RE.findall(line)):
            if "_" not in name or name in cur or name not in hist:
                continue
            hits.append((lineno, "CODE", "已删除函数残留（当前代码无定义，函数删除后文档未同步）", line.strip()[:120]))
    return hits


__all__ = [
    "_DELETED_CAND_RE",
    "_HIST_DEFS",
    "_CUR_DEFS",
    "_historical_defs",
    "_current_defs",
    "scan_deleted_symbol_refs",
]
