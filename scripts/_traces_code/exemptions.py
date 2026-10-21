"""历史痕迹检查脚本的豁免表（只管「命中后哪些算合法」，与匹配表分离）。

分两部分：

1. **两脚本共享**（check-code-traces.py / check-doc-traces.py）——两个脚本都做
   「历史痕迹」检测，作用面不同（代码注释/docstring vs 面向读者文档）；其中
   **章节计数豁免**与**迭代轮次豁免**两套模式完全一致（逐字节相同，早期各自
   维护一份，存在「改一处忘另一处」的漂移面），故抽到本模块共用：
     - `_chapter_excludes()` / `_COMPILED_CHAPTER_EXCLUDE` / `_is_chapter_excluded(line)`
         「N 章」的合法计数/序数表述（共 18 章、减至 16 章、出现第 3 章…）
     - `_round_excludes()` / `_COMPILED_ROUND_EXCLUDE` / `_is_round_excluded(line)`
         「N 轮」的合法计数/运行时表述（共 21 轮、轮询、行业轮动…）

2. **代码侧行级豁免**（仅 check-code-traces.py）——合法领域值（TOP10 / T-1 /
   A1:B1 / lint 码等）、魔法编号（MAGIC / DASHTASK / UNDERSCORE）的领域值豁免、
   以及测试回归场景元描述豁免（仅 src/test/ 生效；任务编号硬禁止不在此豁免内）：
     - `EXCLUDE_LINE` / `_COMPILED_EXCLUDE` / `_is_excluded(line, test_file)`
     - `TEST_META_EXCLUDE` / `_TEST_META_COMPILED`
     - `_magic_excludes()` / `_dash_excludes()` / `_under_excludes()` 及其编译镜像
       与 `_is_magic_match_excluded` / `_is_dash_excluded` / `_is_under_excluded`

拆开的好处：调「漏检」时只动 `patterns.py`，调「误报」时只动本模块，两者不会
在同一文件里相互淹没；`check-code-traces.py` 的原面 re-export 保持不变。
"""

from __future__ import annotations

import re


def _chapter_excludes() -> list[re.Pattern]:
    """章节数量/序数表述豁免（"N 章"为计数/基线/第 N 个章节，非具体章节引用）。

    这些是合法计数表述，命中的行跳过 CHAPTER 分类检查（不影响其他痕迹检查）：
      - 共/目标/总数/合计/合并后 N 章        —— 章节总数
      - N 章 总数/内容/正文/结构/基线/篇幅/布局/表格 —— N 章的结构性指代
      - 减至/降至/精简至/重排为/缩至 N 章    —— 章节数缩减
      - N→M 章 / N 至 M 章                   —— 章节数过渡
      - 「N 章」                             —— 引号内计数
      - 出现/新增/开启才出现 第 N 章          —— 序数（出现第 N 个章节）
    """
    return [
        re.compile(r"(?:共|总共|合计|目标|总数|章节数|合并后)\s*[1-9]\d?\s*章"),
        re.compile(r"[1-9]\d?\s*章\s*(?:总数|内容|正文|结构|基线|篇幅|布局|表格)"),
        re.compile(r"(?:减至|降至|精简至|重排(?:为|成)?|缩至)\s*[1-9]\d?\s*章"),
        re.compile(r"[1-9]\d?\s*章\s*总数减至\s*[1-9]\d?"),
        re.compile(r"[1-9]\d?\s*(?:→|至)\s*[1-9]\d?\s*章"),
        re.compile(r"「[1-9]\d?\s*章」"),
        re.compile(r"(?:出现|新增|开启才出现|才出现)\s*第\s*[1-9]\d?\s*章"),
        # 中文数字对应（限 1~20；裸"一章"计数如"一章三区块"不在 CHAPTER 模式内，
        # 无需豁免——本组模式只覆盖 二~十）
        re.compile(r"(?:共|总共|合计|目标|总数|章节数|合并后)\s*[一二三四五六七八九十]{1,2}\s*章"),
        re.compile(r"[一二三四五六七八九十]{1,2}\s*章\s*(?:总数|内容|正文|结构|基线|篇幅|布局|表格)"),
        re.compile(r"(?:减至|降至|精简至|重排(?:为|成)?|缩至)\s*[一二三四五六七八九十]{1,2}\s*章"),
        re.compile(r"[一二三四五六七八九十]{1,2}\s*章\s*总数减至\s*[一二三四五六七八九十]{1,2}"),
        re.compile(r"[一二三四五六七八九十]{1,2}\s*(?:→|至)\s*[一二三四五六七八九十]{1,2}\s*章"),
        re.compile(r"「[一二三四五六七八九十]{1,2}\s*章」"),
        re.compile(r"(?:出现|新增|开启才出现|才出现)\s*第\s*[一二三四五六七八九十]{1,2}\s*章"),
    ]


def _round_excludes() -> list[re.Pattern]:
    """迭代轮次计数/运行时表述豁免（"N 轮"为数量或业务/运行时概念，非迭代痕迹）。

    与 `_chapter_excludes()` 同理——这些是合法表述，命中的行跳过 ROUND 分类检查
    （不影响其他痕迹检查）：
      - 共/目标/计划/预计/规划 N 轮       —— 轮次总数
      - N 轮 每轮 …                       —— 每轮计数（如"21 轮每轮量化验收"）
      - 轮询                               —— 轮询是运行时技术概念（轮询超时/循环轮询）
      - 轮动/轮换/轮番/轮涨/轮跌           —— 行业轮动等投资业务术语
      - 第 N 轮 + 循环/遍历/扫描/筛选      —— 运行时处理轮次（第 N 轮循环）
    """
    return [
        re.compile(r"(?:共|总共|合计|总数|目标|设定|预计|规划)\s*[1-9]\d?\s*轮"),
        re.compile(r"计划(?:分|为|约|共)?\s*[1-9]\d?\s*轮"),
        re.compile(r"[1-9]\d?\s*轮\s*每轮"),
        re.compile(r"轮询"),
        re.compile(r"轮动|轮换|轮番|轮涨|轮跌"),
        re.compile(r"第\s*[1-9]\d?\s*轮\s*(?:循环|遍历|扫描|筛选)"),
        # 中文数字对应（限 1~20）：计数/运行时序数豁免
        re.compile(r"(?:共|总共|合计|总数|目标|设定|预计|规划)\s*[一二三四五六七八九十]{1,2}\s*轮"),
        re.compile(r"计划(?:分|为|约|共)?\s*[一二三四五六七八九十]{1,2}\s*轮"),
        re.compile(r"[一二三四五六七八九十]{1,2}\s*轮\s*每轮"),
        re.compile(r"第\s*[一二三四五六七八九十]{1,2}\s*轮\s*(?:循环|遍历|扫描|筛选)"),
    ]


# 模块级缓存（模式列表固定，避免逐行重复构建）
_COMPILED_CHAPTER_EXCLUDE: list[re.Pattern] = _chapter_excludes()
_COMPILED_ROUND_EXCLUDE: list[re.Pattern] = _round_excludes()
# 并集正则：任一豁免命中 ⇔ 并集命中，逐行只扫一遍而非 N 次（条款数随词表增长，
# 逐条 any() 的固定开销是文档/注释扫描的主要耗时来源之一）。
_CHAPTER_UNION = re.compile("|".join(f"(?:{p.pattern})" for p in _COMPILED_CHAPTER_EXCLUDE))
_ROUND_UNION = re.compile("|".join(f"(?:{p.pattern})" for p in _COMPILED_ROUND_EXCLUDE))


def _is_chapter_excluded(line: str) -> bool:
    """检查该行是否命中章节计数/序数豁免（"N 章"为数量而非具体章节引用）。

    先做字面量前置判定：全部豁免条款均含「章」，不含该字的行必然不命中，
    可跳过整组正则（占比极高的普通行由此直通）。
    """
    return "章" in line and _CHAPTER_UNION.search(line) is not None


def _is_round_excluded(line: str) -> bool:
    """检查该行是否命中迭代轮次计数/运行时表述豁免（"N 轮"为数量而非迭代痕迹）。

    同 `_is_chapter_excluded`：全部条款均含「轮」，前置字面量判定即可直通。
    """
    return "轮" in line and _ROUND_UNION.search(line) is not None


# 行内排除模式：即使行命中 PATTERNS，若匹配以下任意模式则跳过
EXCLUDE_LINE: list[str] = [
    # ── 运行时行为描述（合法） ─────────
    r"模拟断电",
    r"模拟\s+\w+\s+崩溃",
    r"无临时文件残留",
    r"临时文件被清理",
    r"原文件不受影响",
    r"原文件应[保留完整存在]",
    r"原文件.*旧值",
    r"原文件完整",
    r"文件可能残留在磁盘",
    r"残留临时文件",
    r"清理.*过期.*归档目录",
    r"清理.*缓存",
    r"清除.*残留.*状态",
    r"前一阶段尚未关闭",  # perf.py
    # ── 运行时功能描述（合法） ─────────
    r"兼容性检查",
    r"兼容性名单",
    r"Thinking 兼容性",
    r"是否支持.*兼容",
    r"跨.*兼容",
    r"仍然可用",
    # ── 运行时回退/降级（合法） ──────
    r"回退[到为].*默认",
    r"回退[到为].*兜底",
    r"降级[到为].*过期缓存",
    r"降级[到为].*普通",
    r"改为降级",
    r"回退到\s*(?:\"|').*?(\"|')",  # 回退到"off"等 valid value
    # ── 运行时归档/版本行为（合法） ──────
    r"旧配置仍可",
    r"旧状态不会残留",
    r"跨日残留缓存清仓",
    r"缓存.*前序测试.*残留",
    r"尚未缓存到 registry session_cache",
    r"尚未重新熔断",
    r"尚未达到新鲜缓存",
    # ── 补强模式的误报排除（运行时语义，非历史痕迹） ──
    r"历史数据",  # 运行时历史序列（如行情历史、持仓历史）
    r"历史(?:序列|区间|值|曲线|走势|数据点|K线)",
    r"当前版本",  # 当前版本是运行时状态描述
    r"之前缓存",  # 之前缓存过是运行时缓存行为
    r"历史日期",  # 历史日期是运行时数据范围
    r"历史回撤",  # 历史回撤是运行时指标
    r"此前.*(?:已|已)",  # 此前已完成是运行时状态
    r"以前端|以前台",  # "以前端为准" 是方位描述非历史
    # ── VERSION 模式误报排除（运行时版本） ──
    r"APP_VERSION",
    r"__version__",
    r"version\s*=?\s*[\"']\d+\.\d+",  # 代码中赋值版本号变量
    r"原版本.*备份",  # 运行时备份逻辑
    r"备份旧版本",
    r"版本不兼容",
    r"版本.*不匹配",
    r"版本.*太低",
    r"版本.*落后",
    r"python.*版本",
    r"min_version",
    r"max_version",
    r"python_version",
    r"version_info",
    r"protobuf.*版本",  # compiler.proto version
    # ── 文档区块名（合法） ─────────
    r"待处理区",  # review-findings 的区块名（挂账位置），非待办标记
    # ── TODO 模式误报排除（XXX 作为掩码占位符） ──
    r"000XXX",
    r"XXX\[",
    r"jQueryXXX",
    # ── 工具自身说明（元描述豁免） ──
    #  描述"检查/检出哪些历史痕迹、来源叙述、原旧实现、迁移/重构、系列/约束/
    #  魔法编号暗号"的规则说明行，而非代码实际残留历史痕迹（如本工具及其测试
    #  的描述性注释）。与 check-doc-traces.py 的"工具说明行豁免"保持一致——
    #  命中"检查/检出/扫描 + 痕迹/来源/旧逻辑 + 类别名词"组合才豁免，防止补强
    #  后的时序模式误伤工具自身的元描述。双向匹配（"检出…暗号"与"暗号…须检出"
    #  两种语序），并覆盖 C1~C24 等约束范围记号（技术名称表）。
    r"(?:检查|检测|判定|扫描|检出|识别|不得带|不得包含|不得出现|不应记录|禁止出现).{0,16}(?:历史痕迹|来源叙述|原旧实现|迁移重命名|变更痕迹|迭代标记|版本号标记|归档引用|任务编号|历史实现|旧逻辑|迁移痕迹|重构前|替代旧|系列代号|约束代号|架构约束|暗号|魔法编号|字母\+数字|疑似任务|无意义)",
    r"(?:历史痕迹|来源叙述|原旧实现|迁移重命名|变更痕迹|迭代标记|版本号标记|归档引用|任务编号|历史实现|旧逻辑|迁移痕迹|重构前|替代旧|系列代号|约束代号|架构约束|暗号|魔法编号|字母\+数字|疑似任务|无意义|定义载体|定义处|C[0-9]+~\s*C[0-9]+).{0,16}(?:须检出|应检出|一律检出|须改写|需改写|豁免|不误伤)",
    # ── 检查规则自身的边界描述（元描述豁免） ──
    #  本工具的测试（test_trace_check_scripts.py）须用"非约束 C+数字""不得误伤/
    #  不误伤""十六进制色值（C0 非 1~25）""超出 C1~C25 范围"等字面量描述豁免边界
    #  （验证哪些 C+数字组合不应被检出），属规则元描述而非源码残留暗号。与上方
    #  "工具说明行豁免"同理，命中即整行豁免。
    r"非约束.{0,16}(?:C\+?数字|色值)",
    r"(?:十六进制|色值).{0,16}C\d+",
    r"不误伤|不得误伤",
    r"超出\s*C\d+~\s*C\d+\s*范围",
]

# ── 测试回归场景元描述豁免（仅 src/test/ 文件生效） ──────────
# 回归测试的 docstring / 注释可描述"旧实现/修复前做错什么"以表达防回退意图
# （如"旧实现把 3.41/4.43 修正成 1.9"），这类描述是测试元数据而非源码历史
# 痕迹残留。与"工具说明行元描述豁免"同理，但仅对 src/test/ 路径生效——避免削弱
# 源码侧检出（源码注释若残留"旧实现/修复前"叙述仍会被 PATTERNS 命中）。
# **任务编号不在此豁免内**：注释/docstring 中残留 rf-/plan-/R- 编号一律检出
# （见 scan_file 的硬禁止分支），测试元描述也不例外。
TEST_META_EXCLUDE: list[str] = [
    r"(?:回归断言|回归场景|回归测试|回归：|回归:)",  # 回归测试 docstring/分隔注释
    r"(?:旧实现|原实现|修复前|修复后).{0,24}(?:误|把|被|会|曾|修正|改为|按|源头|×)",
]
_COMPILED_EXCLUDE = [re.compile(p) for p in EXCLUDE_LINE]
_TEST_META_COMPILED = [re.compile(p) for p in TEST_META_EXCLUDE]


def _magic_excludes() -> list[re.Pattern]:
    """字母+数字魔法编号的合法领域值豁免（"大写字母(+小写)+数字"为运行时语义值）。

    与 _chapter_excludes() / _round_excludes() 同理——这些是合法领域/技术表述，
    命中的 token 跳过 MAGIC 分类检查（不影响其他痕迹检查）：
      - TOP\\d+            —— 前 N 名（TOP10/TOP3…），业务语义
      - MD5/SHA\\d+/AES\\d+ —— 哈希/加密算法名
      - VaR\\d+            —— 尾部风险指标（VaR95/VaR99）
      - [Pp](?:50|75|90|95|99)\\b —— 统计分位记号（P50/P95/P99，性能与风险口径）
      - Jinja2/ES5/ES6/V8/Win32/UTF-\\d —— 技术栈名（V8 为 JS 引擎）
      - [A-Z]{1,3}\\d{3}\\b —— linter/静态检查码（F401/E402/PERF203/F811…）
      - [Qq][1-4]\\b        —— 季度（2026-07（Q3））
      - DeepSeek V\\d       —— 模型版本（DeepSeek V4）
      - 单元格/合并/列 + 字母数字，或 A1:B1/B2~B5 范围 —— Excel 单元格引用
      - [Ss]\\d{1,2}\\b      —— 场景标记（S1~S33，conftest 官方活分类法）
      - S-P\\d+              —— 穿透场景标签（S-P1~S-P10，测试文件内组织编号）
      - [Tt]\\d{1,2}\\b      —— 交易日/场景时序记法（T0 = 事件窗口锚定交易日，T1~T21 场景、T95 分位）
      - F10                  —— 天天基金 F10 交易费率页（基金数据源域名）
      - P0~P4                —— 门禁档位（P0/P1/P2）与价格/事件区间点位（P0~P4）
      - MV\\d                —— 市值时点（MV0 起始市值）
      - [Ee]1~3 / [Ww]1~5    —— 样式护栏编号（DESIGN.md「机检落地」段定义的 E/W 级）
      - [Pp]hase\\d           —— 性能基准阶段（Phase1/2/3，perf-test-report 口径）
      - [Yy]\\d\\b / [Zz]\\d\\b —— 边缘测试组标签（Y1~Y6/Z1，文件内组织编号）
      - 微信\\s*X\\d+         —— 微信浏览器内核（X5）
      - ETF\\d+/主动\\d+/基金\\d+ —— 测试数据标签（基金简称）
    """
    return [
        re.compile(r"TOP\d+"),
        re.compile(r"\b(?:MD5|SHA\d+|AES\d*|DES\d*)\b"),
        re.compile(r"VaR\d+"),
        re.compile(r"\b[Pp](?:50|75|90|95|99)\b"),
        re.compile(r"Jinja2|ES5|ES6|V8|Win32|UTF-\d"),
        re.compile(r"[A-Z]{1,3}\d{3}\b"),
        re.compile(r"[Qq][1-4]\b"),
        re.compile(r"DeepSeek\s*V\d"),
        re.compile(r"(?:单元格|合并|列)\s*[A-Z]\s*[0-9](?:\s*[:~]\s*[A-Z]\s*[0-9])?|[A-Z][0-9]\s*[:~]\s*[A-Z][0-9]"),
        re.compile(r"\b[Ss]\d{1,2}\b"),
        re.compile(r"S\s*-\s*P\d+"),
        re.compile(r"\b[Tt]\d{1,2}\b"),
        re.compile(r"\bF10\b"),
        re.compile(r"\bP[0-4]\b"),
        re.compile(r"\bMV\d\b"),
        re.compile(r"\b[EW][1-5]\b"),
        re.compile(r"(?<![A-Za-z0-9])[Pp][Hh][Aa][Ss][Ee]\s*\d", re.IGNORECASE),
        re.compile(r"\b[Yy]\d\b"),
        re.compile(r"\b[Zz]\d\b"),
        re.compile(r"微信\s*X\d+"),
        re.compile(r"(?:ETF|主动|基金)\d+"),
    ]


def _dash_excludes() -> list[re.Pattern]:
    """字母-数字组合的合法领域值豁免（"字母-数字"为运行时时序/下标/编码/模型名）。

    命中的行跳过 DASHTASK 分类检查（不影响其他痕迹检查）：
      - [Tt]-\\d+           —— 交易日语义（T-1/T-2，QDII 净值日期滞后）
      - [a-z]+-\\d+         —— 小写前缀：数学下标/编码/模型名（i-1/idx-1/utf-8/sonnet-4）
      - UTF-\\d|UTC-\\d      —— 编码/时区（UTF-8/UTC-5）
      - 模型名-\\d          —— AI 模型名（Sonnet-4/Claude-3/GPT-4…）
      - N-\\d+(?:项|个|条)   —— 计数算术（应有 N-2 项）
      - R-\\S+-\\d+          —— 需求编号交叉引用（R-LLM-DB-QA-CONCENTRATION-03/04，
        requirements.md 表格定义的需求 ID，非任务编号；单字母 R-086 仍由 CODE 检出）
    """
    return [
        re.compile(r"[Tt]\s*-\s*\d+"),
        re.compile(r"[a-z]{1,}\s*-\s*\d+"),
        re.compile(r"UTF-\d|UTC-\d"),
        re.compile(r"(?:sonnet|claude|opus|haiku|gpt|deepseek|mistral|llama|qwen|gemini)\s*-\s*[\w.]+", re.IGNORECASE),
        re.compile(r"N\s*-\s*\d+\s*(?:项|个|条)"),
        re.compile(r"R-[A-Za-z0-9_./-]+-\d+(?:/\d+)?"),
    ]


def _under_excludes() -> list[re.Pattern]:
    """字母_数字组合的合法领域值豁免（小写前缀为语义短名）。

    命中的行跳过 UNDERSCORE 分类检查（不影响其他痕迹检查）：
      - [a-z]+_\\d+ —— 小写语义短名（changed_1m/syl_1y/cell_3/holdings_200）
    """
    return [
        re.compile(r"[a-z]{1,}\s*_\s*\d+"),
    ]


_COMPILED_MAGIC_EXCLUDE = [re.compile(p) for p in _magic_excludes()]
_COMPILED_DASH_EXCLUDE = [re.compile(p) for p in _dash_excludes()]
_COMPILED_UNDER_EXCLUDE = [re.compile(p) for p in _under_excludes()]


def _is_magic_match_excluded(line: str, start: int, end: int) -> bool:
    """判断 MAGIC 匹配 token（line[start:end]）是否被合法领域值豁免覆盖。

    逐豁免模式检查其命中区间是否与 token 区间重叠——同一行内既有合法场景
    标记（S1）又有暗号代号（R11）时，只豁免合法的 token，暗号仍会被检出。
    """
    for p in _COMPILED_MAGIC_EXCLUDE:
        for m in p.finditer(line):
            if m.start() < end and m.end() > start:
                return True
    return False


def _is_dash_excluded(line: str) -> bool:
    """检查该行是否命中字母-数字合法领域值豁免（T-1 交易日等为合法值）。"""
    return any(p.search(line) for p in _COMPILED_DASH_EXCLUDE)


def _is_under_excluded(line: str) -> bool:
    """检查该行是否命中字母_数字合法领域值豁免（小写语义短名）。"""
    return any(p.search(line) for p in _COMPILED_UNDER_EXCLUDE)


def _is_excluded(line: str, test_file: bool = False) -> bool:
    """检查该行是否匹配排除模式。

    Args:
        line: 单行注释文本。
        test_file: 该行是否来自 src/test/ 下的测试文件。为 True 时额外应用
            TEST_META_EXCLUDE（回归测试 docstring 描述旧行为属元描述，豁免）。
    """
    for pat in _COMPILED_EXCLUDE:
        if pat.search(line):
            return True
    if test_file:
        for pat in _TEST_META_COMPILED:
            if pat.search(line):
                return True
    return False
