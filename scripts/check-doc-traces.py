#!/usr/bin/env python3
"""文档历史变更痕迹与结构性冗余检查脚本。

检查面向读者的仓库文档是否残留历史痕迹，保证正文只反映最新状态；并拦截
复制粘贴残留（同一标题/条目/区块在文档中出现两次）类结构性冗余。

本文件为薄 CLI（模式表/扫描/输出/退出码/结论缓存）：结构性冗余（DUPLICATE）
扫描实现位于同目录 `_traces_doc/` 包（原面 re-export，行为不变）。

七条核心规则：
  1. 文档正文内容不得带有历史痕迹和历史变更（版本号标记、来源叙述、
     原/旧实现、迁移/重命名、任务编号引用、迭代标记等），只描述
     "当前是什么/做什么"。changelog.md 例外（变更日志的职责即记录变化，
     版本号等历史痕迹合法）。
  2. 除上述三个例外文档外，其他管理文档与用户文档的正文内容不得引用
     归档文件（docs/archive/ 下的目录或 archived_*.md）。
     例外：folders.md 的目录树（│ ├ └ 行）可引用 archive 目录及其
     文件名——目录树记录项目结构，archive/ 条目是结构的一部分。
  3. 章节编号引用：任何面向读者文档的正文不得用数字章节号（"N 章" /
     "第 N 章"）指代报告具体章节，须用语义章节名（「X」章），用户才能
     看懂。章节数量/序数表述（共 N 章 / N 章基线 / 减至 N 章 / 出现
     第 N 章等）是合法计数，豁免。该检查**同样适用于** changelog.md /
     plan.md / review-findings.md 与 docs/plan/ 目录——它们虽是
     历史/计划记录（豁免版本号等历史痕迹），但数字章节暗号同样影响
     可读性，仅对它们应用本条章节编号检查。
  4. 迭代轮次引用：任何面向读者文档的正文不得用数字轮次（"第 N 轮" /
     "经 N 轮" / "N 轮" / "轮 N"）指代开发迭代历史，须改为语义描述。
     轮次数量/运行时表述（共 N 轮 / 计划分 N 轮 / N 轮每轮 / 轮询 /
     轮动/轮换/轮番/轮涨/轮跌 / 第 N 轮循环）是合法计数或业务/运行时
     概念，豁免。该检查**不适用于** changelog.md / plan.md /
     review-findings.md 与 docs/plan/——它们作为历史/计划记录，
     "轮 N"是正式记录载体（changelog 记"轮 N 落地"、迭代计划按轮排期）。
  5. 架构约束代号（C1~C25）：任何文档正文不得以代号引用架构约束（如
     "C19 契约""C20 图下说明""C21 指纹同源"），须用语义描述（数据契约/图下
     说明/缓存指纹同源等）。
     约束定义处（technical.md / llm-technical.md，CIPHER_EXEMPT_FILES）
     正文大量引用 C1~C25 属定义载体，豁免；其余受检文档（含 changelog.md /
     plan.md / review-findings.md 与 docs/plan/）一律禁；docs/archive/
     归档域不入本条（历史约束表属当时设计内容，见受检范围）。
  6. 任务记录域复盘痕迹（NARRATIVE）：plan.md / review-findings.md /
     docs/plan/*.md 的任务内容只反映最新状态，禁止历史复盘痕迹——
     修复/改造/重构等前后对比、相对旧实现的否定句（"不再XX"）、
     历史归因（"历史原因"/"之前版本"）。待处理任务的问题现状、已修复
     任务的状态标记（已修复/待处理）、根因定位引用是内容不属复盘，
     合法。仅任务记录域检出：常规手册的"修复后重启"是操作指引、
     变更日志记录变化是其职责，均不适用（changelog 仍仅章节编号）。
     迭代轮次（"轮 N"）是任务记录的正式载体，本条不适用；设计文档的
     "旧格式兼容"等是合法设计内容（历史实现叙述类不入任务域）。
     归档域 docs/archive/（changelog 归档除外）同样检出——归档设计/
     迭代计划同样只表述最新状态，复盘痕迹不留存。
  7. 结构性冗余（DUPLICATE）：标题去重全域适用且路径感知——同级+同标题
     且处于同一父标题下才算重复（各版本块/各任务节下的同名小节属合法
     结构，跨父级不报，第 2 次出现起报出）；重复长行与重复区块见于台账
     三文件（plan.md / review-findings.md / changelog.md）与 docs/archive/
     归档域——空白归一（仅对齐差异视为同一内容）后 ≥40 字符的重复内容行与
     连续 5 行、有效内容 ≥100 字符的重复区块（同小节限定：跨小节共享行/表属
     结构，同小节内第 2 次出现起报出；同一重复块只报首个窗口，不按滑窗数
     重复计数），拦截「同一区块/条目粘贴两遍」类复制粘贴残留与冗余信息。
     豁免：围栏代码块内 `#` 注释与示例、未围栏的缩进或顶格命令样本（python/
     pytest/git 等）与命令续行、键值任务卡（- **键**: 值，跨条目同构）、验证
     清单项（- [ ] 命令跨阶段复跑）、分隔/装饰行与短模板行（重复长行豁免）；
     重复任务由同父标题判重兜底，整段清单/区块粘贴由区块判重兜底。

受检范围：
  - 项目根 README.md
  - docs/managements/（排除 changelog.md / review-findings.md / plan.md）
  - docs/manuals/
  - 章节编号检查另覆盖 changelog.md（仅章节编号模式）；
    任务记录域检查覆盖 review-findings.md / plan.md 与 docs/plan/
    （章节编号 + NARRATIVE 复盘痕迹 + CIPHER）
  - 结构性冗余（DUPLICATE）：标题去重全域适用；重复长行与重复区块
    于台账三文件（plan.md / review-findings.md / changelog.md）
  - docs/archive/ 归档域（DUPLICATE + NARRATIVE；changelog 归档仅
    DUPLICATE——变更日志记录变化是其职责，与 changelog.md 同口径）

豁免范围（运行时产物性质 / 归档历史引用）：
  - docs/tmp/ 运行时临时产物
  - 归档域的 CIPHER（历史约束表属当时设计内容）、版本痕迹与章节/轮次
    编号（历史文档性质）——该域仅查 DUPLICATE 与 NARRATIVE

豁免内容（当前状态 / 流程描述 / 结构记录，非历史痕迹）：
  - 管理文档版本头（"文档版本：0.9.10-dev"，版本号一致性要求，仅行首锚定豁免）
  - folders.md 版本演进对照「最新发布」列（"最近发布 tag v0.12.0 · 2026-10-03"，
    与日期同为随发布重跑刷新的滚动读数，上下文锚定豁免、行中叙述仍检出）
  - folders.md 版本演进对照「当前开发版」列（"当前开发版（0.12.1-dev · ..."，
    由 check-version-consistency 的 evolution_head 断言强制与 APP_VERSION 同步）
  - Markdown 围栏代码块（``` 包裹）内命令/配置示例，非文档叙述；未围栏的
    缩进代码/命令样本同理（重复行与重复区块豁免）
  - 行内代码（`...`）内的技术令牌（如词表条目 `不再`）——NARRATIVE 匹配
    前剔除行内代码段
  - 需求编号（requirements.md 的 R-LLM-ER-01 等需求条目 ID）
  - folders.md 目录树行（│ ├ └ 开头，记录目录结构，可含 archive/ 指向——仅
    ARCHIVE 类豁免；任务编号（CODE）与进度状态词（STATUS）在树行照检）。
    目录树整块位于围栏代码块内，围栏内树行同样照检（围栏跳过仅针对非树行
    内容）；树行按路径分域：docs/archive/ 子树行=归档记录域（仅复盘叙事
    检出，版本号/迭代轮次是归档文件的当时记录）、docs/plan/ 子树行=任务
    记录域（章节编号+约束代号照检，HIGH/STATUS 不入）
  - folders.md 统计表行（如 | ├ archive/ | 版本归档 |，记录目录计数）
  - 当前能力描述（暂不支持 / 不再支持 / 不正式支持）
  - 运行时产物归档描述（"归档版" / "归档目录" / "历史归档至 YYYYMMDD/"——
    指 reports/ 下的报告文件按日期归档，非仓库 docs/archive/）
  - 门禁与发布流程描述（发布版本前 / P0~P3 / --mode / git tag / git pull）
  - 工具使用场景（pytest --ff 等）
  - 模型/环境名（Gemini 旧版 / 旧版 Python）
  - 工具自身说明（描述脚本跳过/豁免归档目录与归档引用）
  - 分隔/装饰行与短模板行（重复长行豁免）

用法：
  python scripts/check-doc-traces.py           # 检查全部
  python scripts/check-doc-traces.py -v        # 详细输出（含豁免行信息）
  python scripts/check-doc-traces.py --ci      # CI 模式（仅输出 文件:行号，非零退出码）

退出码：
  0 — 全部通过（无可疑痕迹）
  1 — 发现高置信度痕迹（HIGH/ARCHIVE/CODE/CIPHER/CHAPTER/ROUND/STATUS/NARRATIVE/DUPLICATE），应修复后再提交
  2 — 仅 LOW 级别痕迹，建议人工复核
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享包（_traces_code）
from _traces_code.exemptions import (  # noqa: E402
    _COMPILED_CHAPTER_EXCLUDE,
    _COMPILED_ROUND_EXCLUDE,
    _chapter_excludes,
    _is_chapter_excluded,
    _is_round_excluded,
    _round_excludes,
)

#: 共享排除模式原面 re-export：测试与调用方仍按原脚本名访问（实现见 _traces_code.exemptions）
__all__ = [
    "_COMPILED_CHAPTER_EXCLUDE",
    "_COMPILED_ROUND_EXCLUDE",
    "_chapter_excludes",
    "_is_chapter_excluded",
    "_is_round_excluded",
    "_round_excludes",
]

from _checklib import (  # noqa: E402
    MANAGEMENTS_DIR,
    MANUALS_DIR,
    PLAN_DOCS_DIR,
    REPO_ROOT,
    add_common_args,
    conclusion_cache_load,
    conclusion_cache_save,
    rel,
)

#: 结构性冗余（DUPLICATE）扫描后端原面 re-export：实现位于 scripts/_traces_doc/，
#: 测试与调用方仍按本脚本名访问——见 _traces_doc 包文档
from _traces_doc import scan_structural_duplicates  # noqa: E402

README_PATH = REPO_ROOT / "README.md"
#: 结论缓存的逻辑版本指纹面：CLI 自身 + 扫描后端模块。只列 CLI 会让后端实现
#: 变更不使缓存失效（判定调整仍回放旧结论，缓存不降级反成"假绿"面）：
#:   - `_traces_doc/patterns.py`：文档痕迹模式表与行级豁免（判定面）
#:   - `_traces_doc/dedup.py`：结构性冗余（DUPLICATE）扫描实现
#:   - `_traces_common.py`：两脚本共享历史叙述词表（正则单一来源）
#:   - `_traces_code/exemptions.py`：章节/轮次计数豁免（两脚本共用）
#: `_checklib` 由 `_logic_fingerprint` 内部固定纳入，无需重复列出。
_LOGIC_FILES = [
    Path(__file__),
    Path(__file__).resolve().parent / "_traces_doc" / "patterns.py",
    Path(__file__).resolve().parent / "_traces_doc" / "dedup.py",
    Path(__file__).resolve().parent / "_traces_common.py",
    Path(__file__).resolve().parent / "_traces_code" / "exemptions.py",
]
DOC_DIRS = [
    MANAGEMENTS_DIR,
    MANUALS_DIR,
]
# 豁免文档：历史/计划记录性质（changelog/review-findings/plan 记录变更、自审与计划）
SKIP_FILES = {"changelog.md", "review-findings.md", "plan.md"}
# 不扫描目录：archive（归档本身）/ plan（中间计划）/ tmp（运行时临时）
SKIP_DIRS = {"archive", "plan", "tmp"}
# 架构约束代号（C1~C25）豁免文件：约束定义处正文大量引用 C1~C25（技术名称表），
# 属定义载体而非"暗号残留"，允许使用代号。其余文档正文一律不得出现约束代号。
CIPHER_EXEMPT_FILES = {"technical.md", "llm-technical.md"}
# ── 本工具自身豁免（结构性 + 文档化） ──
# 本脚本只扫描 .md（见 _iter_docs），不扫描 .py，故自身天然豁免——这是
# "结构性豁免"（扫描范围不含自身文件类型）。docstring 与 _doc_patterns()
# 模式说明区包含被检测类别的特征字面量（版本号、任务编号、迁移/重命名
# 描述词等），属于"检查规则的元描述"，不是文档历史痕迹。
# 若将来扩展扫描范围至 .yaml/.conf 等，需为这些类型补充 docstring/说明区
# 的结构性跳过（参考 check-code-traces.py 的 _is_tool_self 模式豁免）。


# ═══════════════════════════════════════════════════════════════
#  匹配模式定义
# ═══════════════════════════════════════════════════════════════
#  每项：(pattern, category, description)
#    pattern      — 正则表达式（在文档行中匹配）
#    category     — 置信度/分类
#    description  — 简短说明
#
# 分类说明：
#   ARCHIVE   — 归档文件/目录引用，面向读者文档不应指向已归档内容
#   CODE      — 任务编号引用（rf-N / plan-N / R-N），历史记录标识
#   CIPHER    — 架构约束代号（C1~C25，technical.md 定义）——约束定义处
#               （technical.md/llm-technical.md）豁免，其余文档正文须用语义描述
#   HIGH      — 高置信度历史痕迹（来源叙述/历史实现/变更节点/迭代/版本号）
#   CHAPTER   — 章节编号引用（"N 章"/"第 N 章"指代报告具体章节，须用语义章节名）
#   ROUND     — 迭代轮次引用（"第 N 轮"/"N 轮"/"轮 N"指代开发迭代历史，须用语义描述）
#   STATUS    — 进度状态痕迹（已实施/完成态/随任务完成移入/验收记录等）——
#               仅在目录树行检出：目录树描述只讲文件内容简要，不记录进度状态；
#               正文中的当前状态叙述（如"该功能已实施"）属合法用法不检
#   LOW       — 需人工判断的变更/过渡/待办描述（可能是当前能力也可能是痕迹）


# ── 模式表 / 行级豁免 ──
# 实现位于同目录 `_traces_doc/patterns.py`（原面 re-export：测试与调用方仍按本
# 脚本名访问 _DOC_PATTERNS / _is_excluded；共享历史叙述词表见 `_traces_common`）。
from _traces_doc.patterns import (  # noqa: E402
    DOC_PATTERNS as _DOC_PATTERNS,
    EXCLUDE_PATTERNS as _COMPILED_EXCLUDE,  # noqa: F401  原面 re-export（测试按脚本名访问）
    TREE_ONLY_PATTERNS,
    is_excluded as _is_excluded,
)


# 目录树行（│ ├ └ 开头）：仅 ARCHIVE 类豁免（目录结构记录含 archive/ 条目属
# 合法指向），任务编号/进度状态词等照检——树行描述只讲文件内容简要
_TREE_LINE = re.compile(r"^\s*[│├└]")
# 目录树条目：前导缩进（│/空格，每层 4 字符）+ ├──/└── + 名字——用于按路径
# 分域（docs/archive/ 子树=归档记录域、docs/plan/ 子树=任务记录域）
_TREE_ENTRY = re.compile(r"^([\s│]*)(?:├──|└──)\s+(\S+)")
# 文件名任务编号/系列代号（目录树比对 check-doc-drift 只管存在性，语义命名由本检查补位）：rf-N/plan-N、task\d、系列字母+数字（B1/A5/r198/D17 类）与 P3-04 全形；phase 词形（p1-optimization）不误伤
_NAME_CODE = re.compile(
    r"(?:^|[_-])(?:rf|plan)-\d+"
    r"|(?:^|[_-])task\d+"
    r"|(?:^|[_-])[BAGFD]\d+(?=[_-])"
    r"|(?:^|[_-])r-?\d{2,3}(?=[_-])"
    r"|(?:^|[_-])P\d-\d+",
    re.IGNORECASE,
)

# ═══════════════════════════════════════════════════════════════
#  编译镜像 / 模式子集（扫描热循环用）
# ═══════════════════════════════════════════════════════════════
#  公开面 `_DOC_PATTERNS` 仍保持 (pattern, category, description) 字符串元组
#  （测试/调用方契约不变）；热循环用编译镜像，省掉 re.search(str) 每次的
#  内部缓存查找。模式子集与并集预筛按（分类集, 是否含 CIPHER）缓存——同一
#  文档内逐行复用，不重建。
_COMPILED_DOC_PATTERNS = tuple((re.compile(p), c, d) for p, c, d in _DOC_PATTERNS)
#: 目录树行专属补强（仅树行入检；视为附加分类域 "TREE" 由 bundle 拼入）
_COMPILED_TREE_PATTERNS = tuple((re.compile(p), c, d) for p, c, d in TREE_ONLY_PATTERNS)
#: 行内代码段（技术令牌如词表条目 `不再`——NARRATIVE 匹配前剔除，非叙述）
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_ALL_CATEGORIES = tuple(dict.fromkeys(c for _, c, _ in _DOC_PATTERNS))
#: 常规文档非树行：NARRATIVE/STATUS 由域门禁逐行剔除（树行才用全集）
_REGULAR_CATEGORIES = tuple(c for c in _ALL_CATEGORIES if c not in ("NARRATIVE", "STATUS"))


@lru_cache(maxsize=None)
def _pattern_bundle(
    categories: tuple[str, ...], include_cipher: bool = True, include_tree_only: bool = False
) -> tuple[tuple[tuple[re.Pattern[str], str, str], ...], re.Pattern[str]]:
    """取分类子集的编译模式 + 并集预筛正则（缓存，模式表进程内固定）。

    ``include_cipher``：CIPHER 独立于域模式选择（除约束定义处/归档域外处处禁），
    故不写进各域分类列表，由本开关统一增删——避免“任务域/变更日志域额外拼
    CIPHER”在调用处重复三份。
    ``include_tree_only``：拼入目录树行专属补强模式（仅树行分支置 True）——
    原先树行分支需特殊处理（单独拼表 + 跳过预筛），现统一进 bundle，预筛面
    与精确面同源。

    并集预筛不改变判定结果：命中后仍走逐一精确分支，未命中的行必然无 finding
    ——大批普通行由此一次扫描直通，而非 N 条模式逐条试。
    """
    wanted = set(categories)
    if include_cipher:
        wanted.add("CIPHER")
    else:
        wanted.discard("CIPHER")
    picked = tuple(pt for pt in _COMPILED_DOC_PATTERNS if pt[1] in wanted)
    if include_tree_only:
        picked += _COMPILED_TREE_PATTERNS
    prefilter = re.compile("|".join(f"(?:{rx.pattern})" for rx, _c, _d in picked))
    return picked, prefilter


def _read_doc(fpath: Path) -> str | None:
    """文档正文（进程内缓存）：历史痕迹/已删函数/结构冗余三次扫描共用一次读取。"""
    try:
        return fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


#: 高置信度分类（命中即退出码 1）；LOW 仅建议复核（退出码 2）
HIGH_CATEGORIES = ("HIGH", "ARCHIVE", "CODE", "CIPHER", "CHAPTER", "ROUND", "STATUS", "NARRATIVE", "DUPLICATE")


def scan_file(
    fpath: Path,
    verbose: bool,
    chapter_only: bool = False,
    task_record: bool = False,
    archive: bool = False,
) -> list[tuple[int, str, str, str]]:
    """扫描单个文档，返回 [(行号, 分类, 模式说明, 行内容), ...]

    Markdown 围栏代码块（``` 包裹）内是命令/配置示例，非文档叙述，
    不参与历史痕迹匹配（避免 `git tag v0.9.9`、`APP_VERSION` 示例误报）。

    chapter_only=True：仅应用 CHAPTER 章节编号模式（用于 changelog——变更
    日志记录变化是其职责，历史痕迹与复盘叙事均合法）。
    task_record=True：任务记录域（plan.md / review-findings.md / docs/plan/*）
    ——查 CHAPTER + NARRATIVE（复盘叙事：任务内容只反映最新状态）+ CIPHER；
    不查 HIGH（设计文档的旧格式兼容等是合法内容）、不查 ROUND（迭代轮次
    是记录文档的正式载体）、不查 STATUS（仅树行域）；不走 _is_excluded
    表格豁免（任务表/断言表行内的复盘叙事必须检出）。
    archive=True：归档域（docs/archive/*）——查 NARRATIVE 复盘痕迹（归档
    设计/迭代计划同样只表述最新状态；走 _is_excluded 表豁免——发布流程等
    描述合法）；不查 HIGH/CHAPTER/ROUND/STATUS/CIPHER（历史文档性质，
    见模块 docstring 受检范围）。
    架构约束代号（CIPHER）独立于模式选择：除约束定义处（technical.md /
    llm-technical.md）与归档域豁免外，所有受检文档正文均不得出现 C1~C25——
    约束代号属"暗号"，与历史痕迹/章节暗号不同层，受检域内处处禁。
    """
    hits: list[tuple[int, str, str, str]] = []
    # 文件名任务编号（文件级 finding，line=0）：受检域 .md 文件名含 rf-N/plan-N
    # 或系列代号（B1/r198/task91 类）即任务代号残留，须用语义命名（语义命名全域
    # 适用，归档/中间计划文档历史文件名已改名，归档文件名同样入检）
    if _NAME_CODE.search(fpath.name):
        hits.append((0, "CODE", "文件名含任务编号（须用语义命名）", fpath.name))
    text = _read_doc(fpath)
    if text is None:
        return hits

    cipher_ok = fpath.name not in CIPHER_EXEMPT_FILES
    # 模式子集 + 并集预筛按域取一次（缓存），行内只做并集快筛 + 精确分支
    base_patterns: tuple[tuple[re.Pattern[str], str, str], ...]
    base_prefilter: re.Pattern[str] | None
    if archive:
        base_patterns, base_prefilter = _pattern_bundle(("NARRATIVE",), False)
    elif task_record:
        base_patterns, base_prefilter = _pattern_bundle(("CHAPTER", "NARRATIVE"), cipher_ok)
    elif chapter_only:
        base_patterns, base_prefilter = _pattern_bundle(("CHAPTER",), cipher_ok)
    else:
        # 常规域：非树行不用 NARRATIVE/STATUS（域门禁本就不放行，省掉预筛噪声）；
        # 树行用全集（folders.md 树描述照检 STATUS，子树另按路径分域）；folders.md
        # 普通树行再拼树行专属补强（无后缀模块名的拆出/拆分来源叙述）
        plain_bundle = _pattern_bundle(_REGULAR_CATEGORIES, cipher_ok)
        tree_bundle = _pattern_bundle(_ALL_CATEGORIES, cipher_ok)
        folders_tree_bundle = _pattern_bundle(_ALL_CATEGORIES, cipher_ok, include_tree_only=True)
    in_code_block = False
    tree_stack: list[str] = []  # folders.md 目录树目录栈（按深度维护，行分域用）
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        # 围栏代码块：``` 开闭（含可选的 ```lang 标记）
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if verbose:
                print(f"    (codeblock) L{lineno}: {stripped[:60]}")
            continue
        if in_code_block:
            # folders.md 目录树整块位于围栏内——围栏内树行仍照检（树行描述
            # 只讲文件职责，属结构记录域）；其余文档围栏内容（命令/配置示例、
            # 章节大纲图示）维持跳过
            if not (fpath.name == "folders.md" and _TREE_LINE.match(stripped)):
                if verbose:
                    print(f"    (codeblock) L{lineno}: {stripped[:60]}")
                continue
        is_tree = bool(_TREE_LINE.match(stripped))
        if chapter_only or task_record:
            # 任务/变更日志域不走 _is_excluded（表格/链接行豁免会吃掉复盘叙事），
            # 但章节计数豁免是整行语义（暗号不算暗号）——命中则整行跳过
            if _is_chapter_excluded(stripped):
                if verbose and chapter_only:
                    print(f"    (ch-excluded) L{lineno}: {stripped[:80]}")
                continue
            line_patterns, prefilter = base_patterns, base_prefilter
        else:
            if not is_tree and _is_excluded(stripped):
                if verbose:
                    print(f"    (excluded) L{lineno}: {stripped[:80]}")
                continue
            if archive:
                line_patterns, prefilter = base_patterns, base_prefilter
            else:
                line_patterns, prefilter = tree_bundle if is_tree else plain_bundle
        eff_task, eff_archive = task_record, archive
        # folders.md 树行按路径分域：docs/archive/ 子树=归档记录域（仅复盘
        # 叙事检出，版本号/迭代轮次是归档文件的当时记录）；docs/plan/ 子树=
        # 任务记录域（章节编号+约束代号照检）；其余树行=常规域 + 树行专属
        # 来源叙述补强（无后缀模块名的拆出/拆分）
        if fpath.name == "folders.md" and is_tree:
            entry = _TREE_ENTRY.match(stripped)
            if entry:
                depth = len(entry.group(1)) // 4
                del tree_stack[depth:]
                tree_stack.append(entry.group(2))
            subtree = "".join(tree_stack)
            if subtree.startswith("docs/archive/"):
                eff_archive = True
                line_patterns, prefilter = _pattern_bundle(("NARRATIVE",), False)
            elif subtree.startswith("docs/plan/"):
                eff_task = True
                line_patterns, prefilter = _pattern_bundle(("CHAPTER", "NARRATIVE", "CIPHER"), True)
            else:
                line_patterns, prefilter = folders_tree_bundle
        if not prefilter.search(stripped):
            continue  # 并集预筛未命中：必然无 finding，跳过逐条精确匹配
        narr_subject: str | None = None
        for rx, cat, desc in line_patterns:
            if is_tree and cat == "ARCHIVE":
                continue  # 目录树行记录项目结构，archive/ 条目属合法指向
            if cat == "STATUS" and not is_tree:
                continue  # 进度状态词仅目录树描述域（正文当前状态叙述合法）
            if cat == "NARRATIVE" and not (eff_task or eff_archive):
                continue  # 复盘叙事仅任务记录域/归档域（手册操作指引/变更日志合法）
            if cat == "NARRATIVE":
                if narr_subject is None:
                    narr_subject = _INLINE_CODE_RE.sub(" ", stripped)
                subject = narr_subject
            else:
                subject = stripped
            if not rx.search(subject):
                continue
            # 计数/序数豁免只影响本类别，不影响其他模式
            if cat == "CHAPTER" and _is_chapter_excluded(stripped):
                continue
            if cat == "ROUND" and _is_round_excluded(stripped):
                continue
            hits.append((lineno, cat, desc, stripped[:120]))
            break  # 每行仅报告首个匹配

    return hits


def _iter_docs(trace_exempt: bool = False) -> list[Path]:
    """收集受检文档。

    trace_exempt=False（默认）：常规文档——README + managements/manuals 中
    未被豁免的 .md（历史痕迹全量检查）。

    trace_exempt=True：仅章节编号检查的文档——changelog.md / plan.md /
    review-findings.md（SKIP_FILES）+ docs/plan/ 目录。它们虽是历史/计划
    记录（版本号等历史痕迹豁免），但数字章节暗号影响可读性，需单独检查。
    不包含 archive/ 与 tmp/（归档/临时产物，历史痕迹与章节编号均不检查）。
    """
    docs: list[Path] = []
    if trace_exempt:
        for doc_dir in DOC_DIRS:
            if not doc_dir.exists():
                continue
            for fpath in sorted(doc_dir.rglob("*.md")):
                if fpath.name in SKIP_FILES:
                    docs.append(fpath)
        plan_dir = PLAN_DOCS_DIR
        if plan_dir.exists():
            docs.extend(sorted(plan_dir.rglob("*.md")))
        return docs
    if README_PATH.exists():
        docs.append(README_PATH)
    for doc_dir in DOC_DIRS:
        if not doc_dir.exists():
            continue
        for fpath in sorted(doc_dir.rglob("*.md")):
            if fpath.name in SKIP_FILES:
                continue
            if any(part in SKIP_DIRS for part in fpath.relative_to(REPO_ROOT).parts):
                continue
            docs.append(fpath)
    return docs


def _iter_archive_docs() -> list[Path]:
    """收集归档域文档（docs/archive/**/*.md）——DUPLICATE + NARRATIVE 域。"""
    archive_dir = REPO_ROOT / "docs" / "archive"
    if not archive_dir.exists():
        return []
    return sorted(archive_dir.rglob("*.md"))


#: 已删函数候选：反引号内总长 ≥8 的 snake_case（`name` / `name()` / `name(args)`
#: 三种引用形态；过滤 join/read_text 等单段常用词）
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
    text = _read_doc(doc)
    if text is None:
        return []
    hits: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name in set(_DELETED_CAND_RE.findall(line)):
            if "_" not in name or name in cur or name not in hist:
                continue
            hits.append((lineno, "CODE", "已删除函数残留（当前代码无定义，函数删除后文档未同步）", line.strip()[:120]))
    return hits


def _render_summary(total: int, high: int, low: int, summary: dict[str, int]) -> int:
    """结论汇总输出（全量与缓存回放两路共用，保证输出逐字一致）。"""
    print()
    if total == 0:
        print("[OK] 未发现历史变更痕迹，文档干净")
        return 0
    cat_stats = ", ".join(f"{k}={v}" for k, v in sorted(summary.items()))
    print(f"[!] 发现 {total} 处可疑痕迹（{cat_stats}）")
    if high > 0:
        print(f"    {high} 处高置信度（{'/'.join(HIGH_CATEGORIES)}），应从文档中移除")
        return 1
    print(f"[!] 仅 {low} 处 LOW 级别痕迹（需人工判断），建议复核")
    return 2


def _replay_conclusion(conclusion: dict | None) -> tuple[list[str], int, int, int, dict] | None:
    """校验缓存结论结构 → 回放元组；结构不完整 → None（全量重算）。"""
    if not isinstance(conclusion, dict):
        return None
    lines = conclusion.get("findings")
    try:
        total = int(conclusion["total"])
        high = int(conclusion["high"])
        low = int(conclusion["low"])
        cat_summary = conclusion["summary"]
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(lines, list) or not isinstance(cat_summary, dict):
        return None
    return lines, total, high, low, cat_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描文档中的历史变更痕迹")
    add_common_args(parser)
    args = parser.parse_args()

    # 结论缓存（仅 --ci 加载）：命中则逐字回放上次结论（通过与发现都缓存）
    # 受检文档两态列表一次构造，指纹与扫描循环复用（避免同次运行 4 遍目录走查）
    regular_docs = _iter_docs(trace_exempt=False)
    exempt_docs = _iter_docs(trace_exempt=True)
    archive_docs = _iter_archive_docs()
    cache_inputs = [*regular_docs, *exempt_docs, *archive_docs]
    if args.ci:
        replay = _replay_conclusion(conclusion_cache_load("doc_traces", _LOGIC_FILES, cache_inputs))
        if replay is not None:
            cached_lines, cached_total, cached_high, cached_low, cached_summary = replay
            for line in cached_lines:
                print(line)
            return _render_summary(cached_total, cached_high, cached_low, cached_summary)

    total_hits = 0
    high_count = 0
    low_count = 0
    summary: dict[str, int] = {}
    ci_lines: list[str] = []

    def report_doc(doc: Path, hits: list[tuple[int, str, str, str]]) -> None:
        """报告单个文档的命中（非 local，作为闭包读取/修改外层统计）。"""
        nonlocal total_hits, high_count, low_count
        if not hits:
            return
        rel_path = rel(doc)
        if not args.ci:
            print(f"\n  {rel_path}")

        for lineno, cat, desc, text in hits:
            total_hits += 1
            summary[cat] = summary.get(cat, 0) + 1
            is_high = cat in HIGH_CATEGORIES
            if is_high:
                high_count += 1
            else:
                low_count += 1

            ci_lines.append(f"{rel_path}:{lineno} [{cat}] {desc} — {text}")
            if args.ci:
                print(ci_lines[-1])
            else:
                marker = "[ERR]" if is_high else "[!]"
                print(f"    {marker} L{lineno:>4} [{cat}] {desc}")
                if args.verbose:
                    print(f"           {text}")

    # 常规文档：历史痕迹 + 章节编号全量检查
    for doc in regular_docs:
        report_doc(doc, scan_file(doc, args.verbose, chapter_only=False))

    # trace-exempt 文档分两域：
    # · changelog（变更日志）：仅章节编号——记录变化是其职责，历史痕迹合法
    # · 任务记录域（plan/review-findings/docs/plan）：章节编号 + NARRATIVE
    #   复盘叙事——任务内容只反映最新状态，禁止修复前后对比/不再/历史归因
    for doc in exempt_docs:
        if doc.name == "changelog.md":
            report_doc(doc, scan_file(doc, args.verbose, chapter_only=True))
        else:
            report_doc(doc, scan_file(doc, args.verbose, task_record=True))

    # 已删除函数残留：文档反引号引用的函数，当前代码无定义但 git 历史存在过（常规文档）
    for doc in regular_docs:
        report_doc(doc, scan_deleted_symbol_refs(doc))

    # 归档域：非 changelog 归档查 NARRATIVE（归档设计/迭代计划只表述最新状态）；
    # changelog 归档与 changelog.md 同口径不查复盘叙事（记录变化是其职责）
    for doc in archive_docs:
        if "changelog" not in doc.name:
            report_doc(doc, scan_file(doc, args.verbose, archive=True))

    # 结构性冗余（DUPLICATE）：重复标题全域 + 重复长行/区块（台账三文件 + 归档域）
    for doc in [*regular_docs, *exempt_docs, *archive_docs]:
        report_doc(doc, scan_structural_duplicates(doc, _read_doc(doc)))

    conclusion_cache_save(
        "doc_traces",
        _LOGIC_FILES,
        cache_inputs,
        {"findings": ci_lines, "total": total_hits, "high": high_count, "low": low_count, "summary": summary},
    )
    return _render_summary(total_hits, high_count, low_count, summary)


if __name__ == "__main__":
    sys.exit(main())
