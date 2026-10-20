"""结构性冗余（DUPLICATE）检查实现：重复标题路径感知判重（全域）+ 重复长
行/区块（台账三文件与归档域，同小节限定）。

阈值、豁免与规则口径见 check-doc-traces.py 模块 docstring 规则 7；CLI 面
（输出格式、退出码、结论缓存）位于 check-doc-traces.py（薄 CLI，本包为其
扫描后端之一，原面 re-export——测试与调用方仍按原脚本名访问）。
"""

from __future__ import annotations

import re
from pathlib import Path


# ── DUPLICATE：结构性冗余（重复标题/长行/区块，防复制粘贴残留） ──
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
#: 分隔/装饰行（表格分隔、分割线、制表线 ─ 等，重复属正常结构，长行去重豁免）
_SEPARATOR_LINE_RE = re.compile(r"^[\s|:\-=_*#>─━═]+$")
#: 验证清单项（- [ ] 命令——计划各阶段复跑同一命令属结构性重复，
#: 不入长行判重；整段清单/区块粘贴仍由区块判重兑底）
_CHECKLIST_LINE_RE = re.compile(r"^- \[[ xX]\]\s", re.IGNORECASE)
#: 未围栏代码/命令样本的 ASCII 代码形态（缩进样本见 _is_codeish_sample）
_CODEISH_RE = re.compile(
    r"^(?:from\s|import\s|def\s|class\s|return\s|elif\s|except\s|"
    r"[A-Za-z_][\w.]*\s*=[^=]|\w+\s*\(|__\w+__|[\"'`(\[{])"
)
#: 键值任务卡行（- **键**: 值——卡片跨条目必然同构，结构性重复豁免）
_CARD_LINE_RE = re.compile(r"^- \*\*[^*]+\*\*\s*[:：]")
#: 台账三文件：重复长行/区块基础域（任务/自审/变更记录最易出现复制粘贴残留）；
#: 归档域 docs/archive/ 与其并集，见 _in_dup_strict_scope
_LEDGER_DOCS = {"plan.md", "review-findings.md", "changelog.md"}
_DUP_MIN_LINE_LEN = 40  # 长行去重的最小长度（短模板行如归档索引提示行豁免）
_DUP_BLOCK_WINDOW = 5  # 区块去重滑窗行数
_DUP_BLOCK_MIN_CHARS = 100  # 区块有效内容下限（纯结构行/空窗不检）


def _in_dup_strict_scope(doc: Path) -> bool:
    """重复长行/区块判重适用域：台账三文件 + 归档域（路径尾含 docs/archive
    段——按路径形态判定，不依赖 REPO_ROOT 绑定，临时根下可直接验证）。"""
    if doc.name in _LEDGER_DOCS:
        return True
    parts = doc.parts
    return any(parts[i : i + 2] == ("docs", "archive") for i in range(len(parts) - 1))


def _is_codeish_sample(line: str) -> bool:
    """未围栏代码/命令样本行（缩进非结构内容或 ASCII 代码形态；中文叙述不匹配）。"""
    s = line.strip()
    if not s or s[0] in "-*>|" or re.match(r"^\d+[.)]\s", s):
        return False  # 列表/表格/标题/引用/有序编号 = 结构行
    if line[:1] in (" ", "\t"):
        return True  # 缩进非结构（含 # 代码注释）= 代码/命令样本
    if s[0] == "#":
        return False  # 顶格 # = 标题（缩进情形已在上支判定）
    return bool(_CODEISH_RE.match(s))


def _window_is_structural(win: list[str]) -> bool:
    """滑窗是否为结构性重复（键值任务卡 / 代码样本）——是则豁免区块判重。"""
    if sum(1 for x in win if _CARD_LINE_RE.match(x.strip())) >= _DUP_BLOCK_WINDOW - 1:
        return True
    return sum(1 for x in win if x.strip() and _is_codeish_sample(x)) >= 3


def scan_structural_duplicates(doc: Path) -> list[tuple[int, str, str, str]]:
    """结构性冗余检查：重复标题（全部受检文档，路径感知）+ 重复长行/区块
    （台账三文件 + 归档域）。

    防「同一区块/条目在文档中出现两次」类复制粘贴残留（如任务域小节
    整块重复、条目行粘贴两遍、归档合并产生的重复版本节/索引节）。豁免
    与阈值见模块 docstring 规则 7。
    """
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    hits: list[tuple[int, str, str, str]] = []

    # 标题去重（全域；路径感知——同级+同文本+同父标题才算重复；代码围栏内
    # `#` 注释非标题，跳过。跨父级同名小节（各版本块/各任务节下）合法）
    seen_titles: dict[tuple[int, str, str], int] = {}
    parents: dict[int, str] = {}
    in_code = False
    for lineno, raw in enumerate(lines, 1):
        s = raw.rstrip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _HEADING_RE.match(s)
        if not m:
            continue
        lvl, heading = len(m.group(1)), m.group(2).strip()
        parent = ""
        for pl in range(lvl - 1, 0, -1):
            if pl in parents:
                parent = parents[pl]
                break
        key = (lvl, heading, parent)
        if key in seen_titles:
            hits.append(
                (
                    lineno,
                    "DUPLICATE",
                    f"重复标题（同父标题「{parent or '文首'}」下同级同名，同文首现于 L{seen_titles[key]}）",
                    s[:120],
                )
            )
        else:
            seen_titles[key] = lineno
        parents[lvl] = heading
        for dl in list(parents):
            if dl > lvl:
                del parents[dl]

    if not _in_dup_strict_scope(doc):
        return sorted(hits, key=lambda h: h[0])

    # 小节路径预计算（行/区块同小节限定：跨小节共享行/表属结构，仅同小节
    # 内重复才算粘贴残留；围栏内 # 注释不改变路径，围栏行占位置不入路径）
    section_paths: list[tuple[str, ...]] = []
    path_parents: dict[int, str] = {}
    in_fence = False
    for raw in lines:
        s = raw.rstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            section_paths.append(())
            continue
        if in_fence:
            section_paths.append(())
            continue
        section_paths.append(tuple(path_parents[lv] for lv in sorted(path_parents)))
        m = _HEADING_RE.match(s)
        if m:
            lvl, heading = len(m.group(1)), m.group(2).strip()
            path_parents[lvl] = heading
            for dl in list(path_parents):
                if dl > lvl:
                    del path_parents[dl]

    # 长行去重（台账三文件 + 归档域；同小节限定；围栏不入窗、代码样本/
    # 键值卡/清单/命令续行豁免）
    seen_lines: dict[tuple[tuple[str, ...], str], int] = {}
    in_code = False
    norm: list[str] = []
    for lineno, raw in enumerate(lines, 1):
        s = raw.rstrip()
        if s.startswith("```"):
            in_code = not in_code
            norm.append("")
            continue
        if in_code:
            norm.append("")
            continue
        norm.append(s)
        if (
            not s.strip()
            or _HEADING_RE.match(s)
            or _SEPARATOR_LINE_RE.match(s)
            or _CARD_LINE_RE.match(s.strip())
            or _CHECKLIST_LINE_RE.match(s.strip())
            or _is_codeish_sample(s)
            or (lineno > 1 and lines[lineno - 2].rstrip().endswith("\\"))
        ):
            continue
        if len(s.strip()) >= _DUP_MIN_LINE_LEN:
            key = (section_paths[lineno - 1], s)
            if key in seen_lines:
                hits.append(
                    (lineno, "DUPLICATE", f"重复内容行（同小节首现于 L{seen_lines[key]}，疑似复制粘贴残留）", s[:120])
                )
            else:
                seen_lines[key] = lineno

    # 区块去重（台账三文件 + 归档域；同小节限定；滑窗含空行占位，逐字
    # 比对；围栏内容已置空不入窗，代码样本/键值任务卡窗口豁免）
    seen_blocks: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
    for start in range(len(norm) - _DUP_BLOCK_WINDOW + 1):
        win = norm[start : start + _DUP_BLOCK_WINDOW]
        if sum(len(x.strip()) for x in win) < _DUP_BLOCK_MIN_CHARS:
            continue
        if _window_is_structural(win):
            continue
        key = (section_paths[start], tuple(win))
        if key in seen_blocks:
            hits.append(
                (
                    start + 1,
                    "DUPLICATE",
                    f"重复区块（{_DUP_BLOCK_WINDOW} 行窗口，同小节首现于 L{seen_blocks[key]}）",
                    win[0][:120],
                )
            )
        else:
            seen_blocks[key] = start + 1

    return sorted(hits, key=lambda h: h[0])
