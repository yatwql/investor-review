"""文档域模式子集与并集预筛（扫描热循环用）。

与 `patterns.py` 的分工：那边只声明「有哪些模式」（字符串元组，公开面契约），
这边负责**编译镜像与按域取子集**——编译一次、按（分类集, CIPHER 开关, 树行）
缓存预筛正则，避免逐行 `re.search(字符串)` 走 `re` 模块内部缓存。

`DOC_PATTERNS` 公开面仍是 `(pattern, category, description)` 字符串元组（测试与
调用方契约不变），编译镜像只在扫描热路径内部使用。
"""

from __future__ import annotations

import re
from functools import lru_cache

from _traces_doc.patterns import DOC_PATTERNS, TREE_ONLY_PATTERNS

#: 编译镜像：热循环用，省掉 re.search(str) 每次的内部缓存查找
COMPILED_DOC_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (re.compile(p), c, d) for p, c, d in DOC_PATTERNS
)
#: 目录树行专属补强（仅树行入检；由 bundle 拼入）
COMPILED_TREE_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (re.compile(p), c, d) for p, c, d in TREE_ONLY_PATTERNS
)
#: 模式表里出现过的全部分类（顺序按首次出现，稳定可断言）
ALL_CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(c for _, c, _ in DOC_PATTERNS))
#: 常规文档非树行：NARRATIVE/STATUS 由域门禁逐行剔除（树行才用全集）
REGULAR_CATEGORIES: tuple[str, ...] = tuple(c for c in ALL_CATEGORIES if c not in ("NARRATIVE", "STATUS"))


@lru_cache(maxsize=None)
def pattern_bundle(
    categories: tuple[str, ...], include_cipher: bool = True, include_tree_only: bool = False
) -> tuple[tuple[tuple[re.Pattern[str], str, str], ...], re.Pattern[str]]:
    """取分类子集的编译模式 + 并集预筛正则（缓存，模式表进程内固定）。

    ``include_cipher``：CIPHER 独立于域模式选择（除约束定义处/归档域外处处禁），
    故不写进各域分类列表，由本开关统一增删——避免「任务域/变更日志域额外拼
    CIPHER」在调用处重复三份。

    ``include_tree_only``：拼入目录树行专属补强模式（仅树行分支置 True）——
    树行分支因此不必单独拼表或跳过预筛，预筛面与精确面同源。

    并集预筛不改变判定结果：命中后仍走逐一精确分支，未命中的行必然无 finding
    ——大批普通行由此一次扫描直通，而非 N 条模式逐条试。
    """
    wanted = set(categories)
    if include_cipher:
        wanted.add("CIPHER")
    else:
        wanted.discard("CIPHER")
    picked = tuple(pt for pt in COMPILED_DOC_PATTERNS if pt[1] in wanted)
    if include_tree_only:
        picked += COMPILED_TREE_PATTERNS
    prefilter = re.compile("|".join(f"(?:{rx.pattern})" for rx, _c, _d in picked))
    return picked, prefilter
