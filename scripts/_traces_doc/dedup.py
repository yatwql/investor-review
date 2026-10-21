"""结构性冗余（DUPLICATE）检查实现：重复标题路径感知判重（全域）+ 重复长
行/区块（台账三文件与归档域，同小节限定）。

阈值、豁免与规则口径见 check-doc-traces.py 模块 docstring 规则 7；CLI 面
（输出格式、退出码、结论缓存）位于 check-doc-traces.py（薄 CLI，本包为其
扫描后端之一，原面 re-export——测试与调用方仍按原脚本名访问）。

实现要点：标题判重、小节路径、规范行与逐行豁免标记在**一次遍历**内完成
（原实现为标题/路径/长行/区块四趟独立遍历，同一文档扫四遍）；区块比对用
「空白归一 + 窗口哈希键」，同一重复块只报首个窗口（原实现 N 行块会按滑窗
报 N-基准窗口数条，同一粘贴残留被重复计数）。
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
#: 含行首命令前缀（python/pytest/git/bash/.venv/bin/python 等）——计划文档常把
#: 复跑命令顶格写在验证清单里，属命令样本而非叙述（空白对齐差异不应算重复）
_CODEISH_RE = re.compile(
    r"^(?:from\s|import\s|def\s|class\s|return\s|elif\s|except\s|"
    r"(?:\.?/?(?:\.venv/bin/)?(?:python3?|pytest|pip3?|git|bash|sh|npm|npx|node|docker|curl|wget))\b\s|"
    r"[A-Za-z_][\w.]*\s*=[^=]|\w+\s*\(|__\w+__|[\"'`(\[{])"
)
#: 键值任务卡行（- **键**: 值——卡片跨条目必然同构，结构性重复豁免）
_CARD_LINE_RE = re.compile(r"^- \*\*[^*]+\*\*\s*[:：]")
#: 内容归一：折叠空白（含全角空格/零宽字符/BOM）——仅空白差异的重复仍属粘贴残留
_WS_RE = re.compile(r"[\s\u3000\u200b\ufeff]+")
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


def _normalize(line: str) -> str:
    """内容归一（折叠空白）：``a  b`` 与 ``a b`` 视为同一内容。

    先做字面量快判：绝大多数文档行只含单空格，无需正则替换（该函数在
    行/区块判重中逐行调用，是结构冗余扫描的热点）。
    """
    s = line.strip()
    if "  " not in s and "\t" not in s and "\u3000" not in s and "\u200b" not in s and "\ufeff" not in s:
        return s
    return _WS_RE.sub(" ", s)


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


def _window_is_structural(card_prefix: list[int], code_prefix: list[int], start: int) -> bool:
    """滑窗是否为结构性重复（键值任务卡 / 代码样本）——是则豁免区块判重。

    逐行形态标记（键值卡/代码样本）在遍历期一次算好并做前缀和，窗口判定
    是两次减法（O(1)），避免同一行在 O(n) 个滑窗里被反复正则匹配/求和。
    """
    end = start + _DUP_BLOCK_WINDOW
    if card_prefix[end] - card_prefix[start] >= _DUP_BLOCK_WINDOW - 1:
        return True
    return code_prefix[end] - code_prefix[start] >= 3


def scan_structural_duplicates(doc: Path, text: str | None = None) -> list[tuple[int, str, str, str]]:
    """结构性冗余检查：重复标题（全部受检文档，路径感知）+ 重复长行/区块
    （台账三文件 + 归档域）。

    防「同一区块/条目在文档中出现两次」类复制粘贴残留（如任务域小节
    整块重复、条目行粘贴两遍、归档合并产生的重复版本节/索引节）。豁免
    与阈值见模块 docstring 规则 7。

    ``text``：调用方已读取的正文（省一次磁盘读）；默认自行读取。
    """
    if text is None:
        try:
            text = doc.read_text(encoding="utf-8")
        except OSError:
            return []
    lines = text.splitlines()
    if not lines:
        return []

    # ── 单次遍历：标题判重 + 小节路径 + 规范行 + 逐行形态标记 ──
    # 标题去重（全域；路径感知——同级+同文本+同父标题才算重复；代码围栏内
    # `#` 注释非标题，跳过。跨父级同名小节（各版本块/各任务节下）合法）
    hits: list[tuple[int, str, str, str]] = []
    seen_titles: dict[tuple[int, str, str], int] = {}
    # 小节路径预计算（行/区块同小节限定：跨小节共享行/表属结构，仅同小节
    # 内重复才算粘贴残留；围栏内 # 注释不改变路径，围栏行占位置不入路径）
    parents: dict[int, str] = {}
    section_paths: list[tuple[str, ...]] = []
    norm: list[str] = []
    #: 归一内容（折叠空白）——行/区块判重键一次算好，避免区块滑窗 O(n×窗口)
    #: 反复调用 _normalize（原实现每窗口重归一 5 行，热点在正则替换）
    content: list[str] = []
    #: 前缀和：窗口有效内容长度 / 键值卡 / 代码样本计数 O(1) 取窗（避免逐窗
    #: 切片求和，该处是区块判重的 O(n×窗口) 开销）
    content_prefix: list[int] = [0]
    card_prefix: list[int] = [0]
    code_prefix: list[int] = [0]
    #: 长行判重豁免（结构行/空行/围栏/命令续行；长度另判）
    line_exempt: list[bool] = []
    in_fence = False
    prev_continued = False
    for lineno, raw in enumerate(lines, 1):
        s = raw.rstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            section_paths.append(tuple(parents[lv] for lv in sorted(parents)))
            norm.append("")
            content.append("")
            content_prefix.append(content_prefix[-1])
            card_prefix.append(card_prefix[-1])
            code_prefix.append(code_prefix[-1])
            line_exempt.append(True)
            prev_continued = False
            continue
        if in_fence:
            section_paths.append(tuple(parents[lv] for lv in sorted(parents)))
            norm.append("")
            content.append("")
            content_prefix.append(content_prefix[-1])
            card_prefix.append(card_prefix[-1])
            code_prefix.append(code_prefix[-1])
            line_exempt.append(True)
            prev_continued = False
            continue
        heading = _HEADING_RE.match(s)
        section_paths.append(tuple(parents[lv] for lv in sorted(parents)))
        if heading:
            lvl, title = len(heading.group(1)), heading.group(2).strip()
            parent = ""
            for pl in range(lvl - 1, 0, -1):
                if pl in parents:
                    parent = parents[pl]
                    break
            key = (lvl, title, parent)
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
            parents[lvl] = title
            for dl in list(parents):
                if dl > lvl:
                    del parents[dl]
        card = bool(_CARD_LINE_RE.match(s.strip()))
        codeish = _is_codeish_sample(s)
        norm.append(s)
        body = _normalize(s)
        content.append(body)
        content_prefix.append(content_prefix[-1] + len(body))
        card_prefix.append(card_prefix[-1] + card)
        code_prefix.append(code_prefix[-1] + codeish)
        line_exempt.append(
            bool(
                not s.strip()
                or heading
                or _SEPARATOR_LINE_RE.match(s)
                or card
                or _CHECKLIST_LINE_RE.match(s.strip())
                or codeish
                or prev_continued
            )
        )
        prev_continued = s.endswith("\\")

    if not _in_dup_strict_scope(doc):
        return sorted(hits, key=lambda h: h[0])

    # ── 长行去重（台账三文件 + 归档域；同小节限定；空白归一后比对） ──
    seen_lines: dict[tuple[tuple[str, ...], str], int] = {}
    for idx, body in enumerate(content):
        if line_exempt[idx] or len(body) < _DUP_MIN_LINE_LEN:
            continue
        key = (section_paths[idx], body)
        first = seen_lines.get(key)
        if first is None:
            seen_lines[key] = idx + 1
        else:
            hits.append(
                (
                    idx + 1,
                    "DUPLICATE",
                    f"重复内容行（同小节首现于 L{first}，疑似复制粘贴残留）",
                    norm[idx].strip()[:120],
                )
            )

    # ── 区块去重（台账三文件 + 归档域；同小节限定；滑窗含空行占位，归一后
    #    逐行比对；围栏内容已置空不入窗，代码样本/键值任务卡窗口豁免） ──
    window = _DUP_BLOCK_WINDOW
    seen_blocks: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
    start = 0
    while start <= len(norm) - window:
        if content_prefix[start + window] - content_prefix[start] < _DUP_BLOCK_MIN_CHARS or _window_is_structural(
            card_prefix, code_prefix, start
        ):
            start += 1
            continue
        key = (section_paths[start], tuple(content[start : start + window]))
        first = seen_blocks.get(key)
        if first is None:
            seen_blocks[key] = start + 1
            start += 1
            continue
        hits.append(
            (
                start + 1,
                "DUPLICATE",
                f"重复区块（{window} 行窗口，同小节首现于 L{first}）",
                next((x.strip() for x in norm[start : start + window] if x.strip()), "")[:120],
            )
        )
        # 同一重复块只报首个窗口：整块跳过，避免 N 行块按滑窗数重复计数
        start += window

    return sorted(hits, key=lambda h: h[0])
