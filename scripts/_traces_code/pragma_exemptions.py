"""`pragma: no cover` 豁免清单校验（覆盖率口径债的防增长机制）。

纪律源：`docs/managements/test-coverage.md`「不可达行处理原则」——可达分支
一律补真用例覆盖，不以 `# pragma: no cover` 回避；确属**平台分支**（Linux CI
跑不到，如 `os.name == "nt"`）或**可选依赖缺失**（import 失败分支，依赖齐备环境
走不到）的才允许标注，且必须逐条登记在该文档的「`pragma: no cover` 豁免清单」表里。

登记是封闭白名单：清单外出现 `pragma: no cover` 即报 PRAGMA（LOW 级，不升退出码
的 HIGH/CODE 桶），提示走「删分支 / 补测 / 登记」三选一，防止口径债无声增长。

行号口径：按**严格同一行**命中（`文件:行号`），不做区间或 ± 容差——豁免的是
那一行分支，不是整个文件；改代码导致行号漂移时清单须同步改行号，否则报 finding。
"""

from __future__ import annotations

import re
from pathlib import Path

from _shared.checklib import repo_relative_posix as _rel_posix

from _traces_code.config import REPO_ROOT

#: 豁免清单宿主文档（登记表唯一真源）
PRAGMA_EXEMPTION_DOC = REPO_ROOT / "docs" / "managements" / "test-coverage.md"

#: 清单表行：首列是反引号包住的 `路径:行号`（其余列是类别/理由/复审时点，不参与校验）
_EXEMPTION_ROW = re.compile(r"^\|\s*`([^`\s]*\.py:\d+)`")

#: 待查标记（与 coverage.py 的指令写法一致）
_PRAGMA_MARK = "pragma: no cover"

#: 守卫面（生产代码 + 脚本）：`src/test` 内的 pragma 属测试自身豁免面，不在本表管辖
_GUARDED_PREFIXES = ("src/python/", "scripts/")

#: 记忆化槽：((文档路径, 尺寸, mtime_ns), 条目集合)——改表即失效，不多次解析
_memo: tuple[tuple[str, int, int], frozenset[str]] | None = None


def _load_exemptions(doc: Path | None = None) -> frozenset[str]:
    """读豁免清单的 ``文件:行号`` 条目集合（仓库相对 POSIX 路径）。

    文档缺失 / 不可读时返回空集（不豁免任何 pragma）——清单是白名单，
    读不到就当没登记，宁可报 finding 也不静默放行。
    """
    global _memo
    doc = doc or PRAGMA_EXEMPTION_DOC
    try:
        st = doc.stat()
        key = (str(doc), st.st_size, st.st_mtime_ns)
    except OSError:
        return frozenset()
    if _memo is not None and _memo[0] == key:
        return _memo[1]
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    entries = frozenset(m.group(1) for line in text.splitlines() if (m := _EXEMPTION_ROW.match(line)))
    _memo = (key, entries)
    return entries


def _is_guarded_surface(fpath: Path) -> bool:
    """文件是否属本守卫扫描面（``src/python/**`` 与 ``scripts/**``）。"""
    return _rel_posix(fpath).startswith(_GUARDED_PREFIXES)


def _scan_pragma_no_cover(fpath: Path, doc: Path | None = None) -> list[tuple[int, str, str, str]]:
    """扫描单个文件的 `pragma: no cover`：未在豁免清单登记的逐行报 PRAGMA。"""
    if fpath.suffix != ".py":
        return []
    doc = doc or PRAGMA_EXEMPTION_DOC
    rel_ref = _rel_posix(fpath)
    try:
        lines = fpath.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if not any(_PRAGMA_MARK in line for line in lines):
        return []

    exemptions = _load_exemptions(doc)
    hits: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(lines, 1):
        if _PRAGMA_MARK not in line:
            continue
        if f"{rel_ref}:{lineno}" in exemptions:
            continue
        hits.append(
            (
                lineno,
                "PRAGMA",
                "未登记的 pragma: no cover（请在豁免清单登记或删分支）",
                line.strip()[:120],
            )
        )
    return hits
