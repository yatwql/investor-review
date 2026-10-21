"""check-code-traces / check-doc-traces 共用的历史痕迹正则词表（单一来源）。

两个脚本面向不同作用面（代码注释/docstring vs 面向读者的文档），但**历史叙述
词表高度重合**——迁移、旧实现、时序叙述、重命名、版本对比、章节/轮次暗号、
任务系列代号等 31 条正则在两处逐字节相同。此前两份各维护一份，新增同义词时
容易「改一处忘另一处」，形成漂移面（漏改的一侧静默漏检）。

本模块只收敛**正则字面量**：分类（HIGH/LOW/CHAPTER/ROUND/CODE/CIPHER）与
描述仍由各脚本按自身域定义——代码注释与用户文档的措辞、置信度分级并不相同
（例如代码侧把 `曾考虑` 归 HIGH、文档侧归 HIGH 但描述不同；轮次/章节暗号在
两域的中文表述一致）。新增同义模式时**先加此处**，两侧表各自引用常量。

命名即语义：常量名描述该正则捕捉的历史痕迹类型，不使用任务编号/批次代号。
"""

from __future__ import annotations

# ── 任务编号 / 架构约束代号 ──
#: 任务批次系列别名中文（如 B系列/F系列/G系列）
CODE_SERIES_CN = r"[A-Za-z]系列"
#: 任务批次系列别名英文（如 b_series；前限非字母避免 drawdown_series 误伤）
CODE_SERIES_EN = r"(?<![A-Za-z])[A-Za-z]_series\b"
#: 架构约束代号（C1~C25；前限非字母数字避免 AB14/MC19 内嵌、十六进制色值误伤）
CIPHER_CONSTRAINT = r"(?<![A-Za-z0-9])C(?:[1-9]|1[0-9]|2[0-5])\b"

# ── 历史实现 / 变更节点叙述 ──
#: 迁移痕迹（已迁移）
HISTORY_MIGRATED = r"已迁移"
#: 历史契约改名/并入叙述（原 X 契约迁移为主键）
HISTORY_CONTRACT_RENAME = r"原\s*[`A-Za-z_][A-Za-z0-9_.]*(?:\s*(?:契约|dict|数据|结构|结果))?\s*(?:迁移|改称|并入)"
#: 旧版/未升级版对比标签
HISTORY_LEGACY_LABEL = r"未升级版|旧版|老版"
#: 迭代/任务标记（迭代 3 / 迭代任务 / 迭代计划）
HISTORY_ITERATION_MARK = r"迭代\s*(?:\d+|任务|计划)"
#: 早期状态叙述（原先/最初/早期 + 状态动词）
HISTORY_STATE_EARLY = r"(?:原先|最初|早期)(?:是|为|使用|采用|属于)"
#: 时序历史叙述（之前/此前/以前/先前 + 动作/状态动词）
HISTORY_STATE_PREVIOUS = r"(?:之前|此前|以前|先前)\s*(?:是|为|直接|就|采用|使用|用|读取|实现|判断|属于|放在|在)"
#: 曾经的实现/逻辑（历史实现叙述）
HISTORY_IMPLEMENTATION_PAST = r"曾经的?[^\s。，;]{0,6}(?:实现|逻辑|方案|做法|版本|代码)"
#: 曾考虑（历史决策/备选方案叙述）
HISTORY_DECISION_CONSIDERED = r"曾考虑[过]?"
#: 版本对比（之前/旧/原/历史 + 版本为/号/是/中）
HISTORY_VERSION_COMPARE = r"(?:之前|此前|以前|旧|原|历史)(?:的)?版本\s*(?:为|号|是|中)"
#: 由旧 XX（历史来源叙述）
HISTORY_FROM_LEGACY = r"由\s*旧(?:文件|版本|逻辑|方案|实现)"
#: 重构前（重构历史叙述）
HISTORY_REFACTOR_BEFORE = r"重构\s*前"
#: 替代旧/替换旧（历史变更叙述）
HISTORY_REPLACE_LEGACY = r"替代(?:了|掉|原有|旧的)?旧|替换旧"
#: 物理合并（章节/模块合并历史痕迹）
HISTORY_PHYSICAL_MERGE = r"物理合并"

# ── 章节编号暗号 ──
#: N 章 / 第 N 章（数字；负向前瞻排除「章节」）
CHAPTER_DIGIT = r"第?\s*[1-9]\d?\s*章(?!节)"
#: 第 X 章（中文数字）
CHAPTER_CN_NTH = r"第\s*[一二三四五六七八九十]{1,2}\s*章(?!节)"
#: X 章（中文数字裸写；「一章」多为计数表述，不纳入）
CHAPTER_CN_BARE = r"[二三四五六七八九十]{1,2}\s*章(?!节)"

# ── 迭代轮次暗号 ──
#: 第 N 轮
ROUND_NTH = r"第\s*[1-9]\d?\s*轮"
#: N 轮
ROUND_N = r"[1-9]\d?\s*轮"
#: 轮 N
ROUND_N_PREFIX = r"轮\s*[1-9]\d?\b"
#: 第 X 轮（中文数字；「第一/二轮」多为运行时序数，不纳入）
ROUND_NTH_CN = r"第\s*[三四五六七八九十]{1,2}\s*轮"
#: 轮X（中文数字）
ROUND_CN_PREFIX = r"轮\s*[一二三四五六七八九十]{1,2}"

# ── 需人工判断的变更/待办描述（LOW） ──
#: 重构为/到（变更描述）
LOW_REFACTOR_TO = r"重构[为成到]"
#: 废弃/弃用标注
LOW_DEPRECATED = r"已废弃|已弃用"
#: 曾被/曾经被（历史被动叙述）
LOW_PASSIVE_PAST = r"曾(?:经)?被"
#: 尚未完成/实现（待办性质）
LOW_NOT_YET = r"尚未[实现处理支持完成覆盖]"
#: 待办/待处理
LOW_TODO = r"待[办做处补充修复]"
#: 后续版本/迭代（未来计划）
LOW_FUTURE_PLAN = r"后续\s*(?:版本|迭代|优化|需要|再处理)"
#: 过渡性方案说明
LOW_TRANSITIONAL = r"过渡方案|过渡期|过渡性"

#: 全部共享正则（正反向校验用：两侧模式表必须各自引用这里的每一条）
SHARED_REGEXES: tuple[str, ...] = (
    CODE_SERIES_CN,
    CODE_SERIES_EN,
    CIPHER_CONSTRAINT,
    HISTORY_MIGRATED,
    HISTORY_CONTRACT_RENAME,
    HISTORY_LEGACY_LABEL,
    HISTORY_ITERATION_MARK,
    HISTORY_STATE_EARLY,
    HISTORY_STATE_PREVIOUS,
    HISTORY_IMPLEMENTATION_PAST,
    HISTORY_DECISION_CONSIDERED,
    HISTORY_VERSION_COMPARE,
    HISTORY_FROM_LEGACY,
    HISTORY_REFACTOR_BEFORE,
    HISTORY_REPLACE_LEGACY,
    HISTORY_PHYSICAL_MERGE,
    CHAPTER_DIGIT,
    CHAPTER_CN_NTH,
    CHAPTER_CN_BARE,
    ROUND_NTH,
    ROUND_N,
    ROUND_N_PREFIX,
    ROUND_NTH_CN,
    ROUND_CN_PREFIX,
    LOW_REFACTOR_TO,
    LOW_DEPRECATED,
    LOW_PASSIVE_PAST,
    LOW_NOT_YET,
    LOW_TODO,
    LOW_FUTURE_PLAN,
    LOW_TRANSITIONAL,
)
