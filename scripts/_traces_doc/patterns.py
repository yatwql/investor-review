"""文档历史痕迹模式表与行级豁免（check-doc-traces 薄 CLI 的扫描后端）。

模式按作用域分组：
  - `DOC_PATTERNS`：受检文档正文全量模式（ARCHIVE / CODE / CIPHER / HIGH /
    CHAPTER / ROUND / LOW / STATUS / NARRATIVE）——分类门禁由 CLI 的域矩阵
    决定，本模块只负责"文本命中什么"。
  - `TREE_ONLY_PATTERNS`：目录树行专属补强（无后缀模块名的拆出/拆分来源叙述）。
  - `EXCLUDE_PATTERNS` / `is_excluded`：合法当前状态/流程描述行豁免。

与 `check-code-traces` 逐字节相同的历史叙述正则由 `_traces_common` 单一来源
提供（常量引用，分类与描述仍按本域定义）；本模块只保留文档域特有的模式
（归档指向、约束代号定义处豁免措辞、复盘叙事、进度状态词等）。
"""

from __future__ import annotations

import re

from _shared.traces_common import (  # 共享词表（与 check-code-traces 同源）
    CHAPTER_CN_BARE,
    CHAPTER_CN_NTH,
    CHAPTER_DIGIT,
    CIPHER_CONSTRAINT,
    CODE_SERIES_CN,
    CODE_SERIES_EN,
    HISTORY_CONTRACT_RENAME,
    HISTORY_DECISION_CONSIDERED,
    HISTORY_FROM_LEGACY,
    HISTORY_IMPLEMENTATION_PAST,
    HISTORY_ITERATION_MARK,
    HISTORY_LEGACY_LABEL,
    HISTORY_MIGRATED,
    HISTORY_PHYSICAL_MERGE,
    HISTORY_REFACTOR_BEFORE,
    HISTORY_REPLACE_LEGACY,
    HISTORY_STATE_EARLY,
    HISTORY_STATE_PREVIOUS,
    HISTORY_VERSION_COMPARE,
    LOW_DEPRECATED,
    LOW_FUTURE_PLAN,
    LOW_NOT_YET,
    LOW_PASSIVE_PAST,
    LOW_REFACTOR_TO,
    LOW_TODO,
    LOW_TRANSITIONAL,
    ROUND_CN_PREFIX,
    ROUND_N,
    ROUND_N_PREFIX,
    ROUND_NTH,
    ROUND_NTH_CN,
)


def _multi_domain(pattern: str, *variants: tuple[str, str]) -> list[tuple[str, str, str]]:
    """同一正则在多个域各登记一条（分类/描述按域定义，避免正则字面量写两遍）。"""
    return [(pattern, cat, desc) for cat, desc in variants]


#: 历史实现叙述：前缀（新旧/时序）× 中心词（实现类名词）的组合式单条模式，
#: 取代原先「原逻辑/原实现/旧逻辑/此前的逻辑/原始版本/历史版本…」逐对穷举的
#: 五条模式——新增同义前缀或名词只改此处，避免同一语义散落多处、漏改即漏检。
#: 各前缀保留原有覆盖面（不做无差别并集）：「历史代码」「旧格式」在本项目属
#: 当前语义（测试名、缓存格式兼容用例），并入会误伤。
_HISTORY_IMPL_RE = (
    "(?:"
    + "|".join(
        (
            r"(?:原|旧)(?:的)?(?:逻辑|实现|方案|代码|写法|做法|设计|架构|版本)",
            r"历史(?:的)?(?:版本|实现|逻辑|方案|做法)",
            r"(?:之前|此前|以前|先前)(?:的)?(?:逻辑|实现|方案|做法|判定|版本|代码|判断)",
            r"原始(?:的)?(?:版本|实现|方案|逻辑)",
        )
    )
    + ")"
)


def _doc_patterns() -> list[tuple[str, str, str]]:
    """文档历史痕迹模式（针对 .md 全文语义）。"""
    return [
        # ── ARCHIVE：归档引用（指向仓库 docs/archive/ 的历史记录） ──
        #  仓库归档路径引用（docs/archive/、../archive/、裸 archive/）
        (r"(?:docs/|\.\./)?archive/", "ARCHIVE", "归档目录引用（archive/）"),
        #  归档文件名引用（archived_*.md）
        (r"archived_[A-Za-z0-9._-]+", "ARCHIVE", "归档文件引用（archived_*）"),
        #  归档路径说明（"归档文件：`../archive/...`"）
        (r"归档文件\s*[:：]?\s*[`]?archive/", "ARCHIVE", "归档路径说明"),
        #  无显式 archive/ 前缀的归档引用（已/可/应 归档至 某目录），如
        #  "已归档至 archive/"、"归档至 docs/archive/"——须含"归档"动词 + 归档目标
        (
            r"归档\s*(?:至|到|于|在|入|完成|处理)\s*[`]?(?:docs/|\.\./)?archive",
            "ARCHIVE",
            "归档引用（归档至 archive/ 等）",
        ),
        #  明确指向归档文件的叙述（"归档文件：archived_x.md" / "归档于 archived_*"）
        (r"(?:归档文件|归档于|归档到|归档至)\s*[:：]?\s*[`]?archived_", "ARCHIVE", "归档文件引用（归档至 archived_*）"),
        #  完成态归档动作（"已归档至 X" / "归档完成"），指向历史归档行为。
        #  收紧判定：仅匹配"已归档至/到/于 + 非运行时产物目标"——归档目标不是
        #  reports/、YYYYMMDD/ 等运行时产物（如"报告已归档到 reports/"、"归档至
        #  YYYYMMDD/ 子目录"为当前功能描述，应豁免）。孤立的"已归档"不命中
        #  （"已归档版报告"是运行时产物描述）。
        #  lookahead 内部带 (?:\s*)：外层的贪婪 \s* 在回溯为 0 个空白时，
        #  视线会落在空格字符上导致排除失败，故让 lookahead 自身也能跳过空白。
        #  排除的运行时产物目标：reports?/（报告输出目录）、报告输出目录（中文写法）、
        #  `?\d{8}`?（纯数字日期目录）、`?YYYYMMDD（日期模板）、日期子目录。
        (
            r"归档\s*(?:至|到|于|在|完成|处理)\s*(?!(?:\s*)(?:reports?/|报告输出目录|`?\d{8}`?|`?YYYYMMDD|日期子目录))",
            "ARCHIVE",
            "归档引用（归档至某处/归档完成）",
        ),
        # ── CODE：任务编号引用 ──
        (r"\brf-\d+", "CODE", "任务编号引用（rf-N）"),
        (r"\bplan-\d+", "CODE", "任务编号引用（plan-N）"),
        (r"\bR-\d+(?!-?[A-Z])", "CODE", "任务编号引用（R-N）"),
        (CODE_SERIES_CN, "CODE", "任务批次系列别名（如 B系列/F系列/G系列）"),
        (CODE_SERIES_EN, "CODE", "任务批次系列别名英文形式（如 b_series）"),
        # ── CIPHER：架构约束代号（C1~C25）──
        #  约束定义处（technical.md/llm-technical.md，CIPHER_EXEMPT_FILES）豁免；
        #  其余文档正文出现 C1~C25 属"暗号"，须改写为语义描述（原子写入/会话缓存/
        #  数据契约/图下说明/指纹同源等）。按约束表实际编号精确匹配，避免误伤十六
        #  进制色值（C00000）、C25+ 等；前限非 ASCII 字母/数字，避免 AB14/MC19
        #  内嵌命中。约束表新增编号时必须同步放开此处范围。
        (
            CIPHER_CONSTRAINT,
            "CIPHER",
            "架构约束代号（C1~C25，须用语义描述替代，如原子写入/会话缓存/数据契约）",
        ),
        # ── HIGH：来源叙述 / 历史实现 / 变更节点 / 迭代 / 版本号 ──
        (
            r"(?:自|从|由)\s*[`\w./_-]+\.(?:py|js|html|md)\`*\s*(?:提取|拆分|拆出|迁移|合并|复用|分离)",
            "HIGH",
            "来源叙述（从XX.py提取/拆分/拆出/迁移）",
        ),
        (r"(?:拆分|拆出|提取|分离)(?:自|到|成)\s*[A-Za-z_][\w.-]*", "HIGH", "来源叙述（拆分自/拆出自/分离为XX）"),
        (r"(?:合并|迁移|提取)自\s*[`\w._-]+", "HIGH", "来源叙述（合并自/迁移自/提取自）"),
        # 来源叙述补强：无后缀模块名的迁入/移出（如"自 generators 迁入"），
        # 带后缀文件模式覆盖不到；正文合法当前面描述（如 re-export 兼容面）
        # 不含迁入系动词不受影响
        (r"(?:自|从)\s*[`\w./_-]+\s*(?:迁入|迁出|迁移|移入|移出)", "HIGH", "来源叙述（自/从 XX 迁入/移入）"),
        (HISTORY_MIGRATED, "HIGH", "迁移痕迹（已迁移）"),
        #  历史实现叙述（组合式，见 _HISTORY_IMPL_RE：原/旧/历史/此前/原始 × 名词）
        (_HISTORY_IMPL_RE, "HIGH", "历史实现叙述（原/旧/历史/此前的逻辑、实现、版本…）"),
        (
            HISTORY_CONTRACT_RENAME,
            "HIGH",
            "原X迁移/改称（历史契约/命名变更叙述）",
        ),
        (r"旧\s*[`\w._-]+\s*(?:逻辑|实现|方案|要求|做法|方式|判定|分类)", "HIGH", "旧XX逻辑/要求（历史实现叙述）"),
        (r"旧(?:接口|字段|行为|约定)|历史遗留", "HIGH", "旧接口/旧字段/历史遗留（历史结构叙述）"),
        (r"历史上(?:曾|是|为|使用|采用|遗留)", "HIGH", "历史上曾/是（历史状态叙述）"),
        (HISTORY_LEGACY_LABEL, "HIGH", "旧版/未升级版（版本对比痕迹）"),
        (r"曾(?:经)?(?:用|作为|属于|采用|以)", "HIGH", "曾用/曾作为（历史实现叙述）"),
        (r"原为[\w._-]+", "HIGH", "原为XX（历史来源叙述）"),
        (r"(?:后来|之后|随后)\s*(?:改[为成]|换[为成]|引入|移除|新增)", "HIGH", "变更痕迹（后来改为/之后引入）"),
        (r"已更名|已重命名|改名为|重命名为|重新命名|更名为|改称|曾用名|旧称", "HIGH", "重命名/改称痕迹"),
        (r"\bIter(?:ation)?\s*\d+\b", "HIGH", "Iter 迭代标记"),
        (HISTORY_ITERATION_MARK, "HIGH", "迭代/任务标记"),
        (r"\bv\d+\.\d+\.\d+(?:-dev)?\b", "HIGH", "版本号标记"),
        #  无 v 前缀的裸版本号（本项目版本号为 0.x.y；限 0 开头避免误伤章节号 6.4.1、包版本 1.16.0 等）
        (r"\b0\.\d+\.\d+(?:-dev)?\b", "HIGH", "版本号标记（无 v 前缀）"),
        #  历史状态叙述：需后接状态动词才命中，避免误伤"早期数据仍保留"
        #  （当前运行时行为）等合法描述。
        (HISTORY_STATE_EARLY, "HIGH", "原先/最初/早期（历史状态叙述）"),
        # ── 时序历史叙述补强（与 check-code-traces 同步的"自我进化"）──
        #  "之前/此前/以前/曾经/原始/历史/旧逻辑/重构前/替代旧"等高频文档
        #  历史叙述词。仅时间词不足判历史（"之前缓存过"是运行时描述），
        #  故需后接动作/状态动词或"逻辑/实现/方案"等名词。
        (
            HISTORY_STATE_PREVIOUS,
            "HIGH",
            "此前/之前是（历史状态叙述）",
        ),
        (HISTORY_IMPLEMENTATION_PAST, "HIGH", "曾经的实现/逻辑（历史实现叙述）"),
        (HISTORY_DECISION_CONSIDERED, "HIGH", "曾考虑（历史决策/备选方案叙述）"),
        (HISTORY_VERSION_COMPARE, "HIGH", "旧/历史版本号（版本对比痕迹）"),
        (HISTORY_FROM_LEGACY, "HIGH", "由旧XX（历史来源/改造叙述）"),
        (r"由旧[^\s。，;]{0,8}(?:改造|改来|升级而来|改写)", "HIGH", "由旧XX改造/改来（历史变更叙述）"),
        (
            r"(?:迁移|移到|移至|搬到|转入|迁往|搬至|挪到)\s*(?:到|至)?\s*新(?:模块|文件|目录|位置|路径|函数|类|包|命名空间)",
            "HIGH",
            "迁移/移到新位置（迁移痕迹）",
        ),
        (HISTORY_REFACTOR_BEFORE, "HIGH", "重构前（重构历史叙述）"),
        (r"(?:废弃|移除|删除|弃用)于\s*(?:v?\d|第|此|本次)", "HIGH", "废弃/移除于XX（历史变更节点）"),
        (HISTORY_REPLACE_LEGACY, "HIGH", "替代旧/替换旧（历史变更叙述）"),
        (HISTORY_PHYSICAL_MERGE, "HIGH", "物理合并（章节/模块合并历史痕迹，须用语义描述当前结构）"),
        # ── CHAPTER：章节编号引用（用数字章节号指代报告具体章节） ──
        #  "N 章" / "第 N 章"（N=1~99）指代报告具体章节时用户无法识别，须改
        #  用语义章节名（「X」章）。中文数字同理：第X章（第一章~第二十章）与裸
        #  "三章"式（三章/二章/四章…）均检出；唯"一章"在本项目均为计数表述
        #  （一章三区块/一章两区块），不纳入裸数字模式以免误伤计数语义。章节
        #  数量/序数表述（共 N 章、N 章基线、减至 N 章、出现第 N 章、N→M 章、
        #  引号内"N 章"）由 _chapter_excludes() 豁免。负向前瞻 (?!节) 排除
        #  "章节"一词；[1-9]\d? 限 1~99、[一二三四五六七八九十]{1,2} 限 1~20，
        #  小节号"4.2"（数字后非"章"）不匹配。
        (CHAPTER_DIGIT, "CHAPTER", "章节编号引用（N 章/第 N 章，须用语义章节名）"),
        (CHAPTER_CN_NTH, "CHAPTER", "章节编号引用（第X章，中文数字，须用语义章节名）"),
        (CHAPTER_CN_BARE, "CHAPTER", "章节编号引用（X章，中文数字，须用语义章节名）"),
        # ── ROUND：迭代轮次引用（用"第 N 轮"/"N 轮"/"轮 N"指代开发迭代历史） ──
        #  "第 14 轮" / "经 8 轮" / "轮 8" 是开发迭代痕迹（计划分轮实施，
        #  changelog 记"轮 N 落地"），面向读者文档正文不应记录迭代轮次，
        #  须改用语义描述。中文数字同理：第X轮（第三轮~第二十轮）与"轮X"
        #  （轮三）均检出；唯"第一轮/第二轮"多为运行时序数（LLM 圆桌会两轮
        #  辩论、两段式抓取的首/次轮），不纳入"第X轮"模式以免误伤正常行为。
        #  轮次数量/序数表述（共 N 轮、计划分 N 轮、N 轮每轮、轮询、轮动/
        #  轮换/轮番/轮涨/轮跌、第 N 轮循环）是合法计数或业务/运行时概念，
        #  由 _round_excludes() 豁免；`[1-9]\d?` 限 1~99、
        #  [一二三四五六七八九十]{1,2} 限 1~20，中文"一轮/两轮/三轮/二十轮"
        #  为计数表述（一轮行情是业务表述，非迭代轮次），不纳入裸"X轮"模式。
        (ROUND_NTH, "ROUND", "迭代轮次引用（第 N 轮，属开发迭代痕迹）"),
        (ROUND_N, "ROUND", "迭代轮次引用（N 轮，属开发迭代痕迹）"),
        (ROUND_N_PREFIX, "ROUND", "迭代轮次引用（轮 N，属开发迭代痕迹）"),
        (ROUND_NTH_CN, "ROUND", "迭代轮次引用（第X轮，中文数字，属开发迭代痕迹）"),
        (ROUND_CN_PREFIX, "ROUND", "迭代轮次引用（轮X，中文数字，属开发迭代痕迹）"),
        # ── LOW：需人工判断的变更/过渡/待办描述（可能是当前能力也可能是痕迹） ──
        (LOW_REFACTOR_TO, "LOW", "重构为/重构到（变更描述，需判断）"),
        (LOW_DEPRECATED, "LOW", "废弃/弃用标注（当前指引或历史，需判断）"),
        (LOW_PASSIVE_PAST, "LOW", "曾被/曾经被（历史被动叙述）"),
        (LOW_NOT_YET, "LOW", "尚未完成/实现（待办性质）"),
        (LOW_TODO, "LOW", "待办/待处理"),
        (LOW_FUTURE_PLAN, "LOW", "后续版本/迭代（未来计划）"),
        # 英文废弃/过时标记（中文文档中夹带的英文遗留标注；legacy 在本项目属
        # 当前语义（legacy 兼容路径、TestLegacyMappingRemoved），不纳入）
        (r"\b(?:deprecated|obsolete)\b", "LOW", "英文废弃/过时标记（需判断）"),
        (LOW_TRANSITIONAL, "LOW", "过渡性方案说明"),
        # ── STATUS：目录树描述域的进度状态痕迹（仅树行检出；正文中的当前
        #    状态叙述如"该功能已实施"属合法用法不检，见 scan_file 分支） ──
        #    注："已移除"不入表——测试标记脚本的违规类别枚举（未注册/已移除/
        #    edge/目录期望）属语义名，树行合法
        (
            r"已(?:实施|评测|定稿|转正|验收|完成|归档|废弃|收口|核实|具备)",
            "STATUS",
            "进度状态词（已实施/已归档/已核实等）",
        ),
        *_multi_domain(
            r"不再",
            ("STATUS", "相对旧实现对比措辞（不再XX，描述只讲内容）"),
            ("NARRATIVE", "相对旧实现的否定句（不再XX，复盘痕迹）"),
        ),
        (r"完成态", "STATUS", "完成态标注（进度状态痕迹）"),
        (r"随(?:任务|功能)(?:完成|落地)", "STATUS", "任务流转措辞（随任务完成/随功能落地移入）"),
        (r"(?:验收|判定|实施|演练)记录", "STATUS", "验收/判定/实施记录指引（历史痕迹）"),
        (r"迭代验收|门槛与验收", "STATUS", "验收措辞（目录树描述只讲内容）"),
        (r"立项依据", "STATUS", "立项依据标注（流转痕迹）"),
        (r"观察中", "STATUS", "观察状态标注（进度状态痕迹）"),
        (r"§\s*\d", "STATUS", "章节验收指引（目录树描述不应含 § 章节引用）"),
        (r"(?:设计)?(?:草案|初稿|终稿|草稿)", "STATUS", "稿态词（设计草案/初稿等，描述只讲内容）"),
        # ── NARRATIVE：任务记录域（plan.md / review-findings.md / docs/plan/*）
        #    的历史复盘痕迹——任务内容只反映最新状态，禁止修复/改造前后对比、
        #    相对旧实现的否定句、历史归因（仅任务域检出：常规手册的「修复后
        #    重启」是操作指引、变更日志记录变化是其职责，均不适用） ──
        (
            r"(?:修复|改造|重构|调整|修改|变更|上线|迁移|替换|回退|部署|发布)[前后]",
            "NARRATIVE",
            "修复/改造前后对比（任务内容只反映最新状态）",
        ),
        (r"历史原因|之前版本", "NARRATIVE", "历史归因/版本对比（复盘痕迹）"),
    ]


def _exclude_lines() -> list[re.Pattern]:
    """文档合法内容豁免模式（命中则跳过该行）。"""
    return [
        # ── 管理文档版本头（版本号一致性要求） ──
        # 行首锚定（可带 > 引用块或 ## 标题符）：仅豁免版本头本身，
        # 不豁免行中叙述（如"该功能于版本：v0.8.9 中引入"应命中版本号模式）。
        re.compile(r"^\s*[#>]*\s*(?:文档|当前|文档内容|主文档)\s*版本\s*[:：]\s*v?\d"),
        re.compile(r"文档版本号"),
        # ── 版本演进对照「最新发布」列（folders.md 滚动读数） ──
        # tag 名与日期同为「按需重跑刷新」的滚动读数（表头已声明），属当前状态；
        # 上下文锚定「最近(一次)发布 tag」+ 版本号，不豁免行中叙述
        # （如"该缺陷在 v0.12.0 中修复"仍命中版本号模式）。
        re.compile(r"最近(?:一次)?发布\s*`?tag`?\s*[（(]?\s*`?v?\d+\.\d+\.\d+"),
        # ── 版本演进对照「当前开发版」列（folders.md 滚动读数） ──
        # 列头版本号由 check-version-consistency 的 evolution_head 断言强制
        # 与 APP_VERSION 同步（发版漏改即报错），非写死后放任过期的历史痕迹；
        # 上下文锚定「当前开发版（」+ 版本号，不豁免行中叙述。
        re.compile(r"当前开发版（\s*`?v?\d+\.\d+\.\d+(?:-dev)?"),
        # ── 门禁 / 发布流程描述 ──
        re.compile(r"发布版本前"),
        re.compile(r"发布前|发布后|提交前|合并前|提交后"),
        re.compile(r"版本控制"),
        re.compile(r"\bP[0-3]\b"),
        re.compile(r"--mode\s+verify"),
        re.compile(r"--mode\s+regression"),
        re.compile(r"test-runner\.py"),
        re.compile(r"check-version-consistency\.py"),
        re.compile(r"check-code-traces\.py"),
        re.compile(r"git tag|git pull|打 tag"),
        # ── 当前能力 / 限制描述（组合限定，避免"暂不采用A改用B"等变更描述被豁免） ──
        re.compile(r"暂不(?:支持|提供|纳入|实现|处理|参与|显示|包含|在|可用|属于|单独)"),
        re.compile(r"不正式支持"),
        re.compile(r"不再支持"),
        re.compile(r"已不再(?:支持|推荐|使用|提供)"),
        re.compile(r"仍不"),
        # ── 工具使用场景 ──
        re.compile(r"--ff\b|--failed-first"),
        re.compile(r"修复后确认修复"),
        # ── 环境 / 模型名 ──
        re.compile(r"旧版 Python|旧版 Win|Windows 7|Gemini 旧版"),
        # ── 测试场景 / 需求条目 / 导航项名 ──
        re.compile(r"版本兼容"),
        re.compile(r"^\s*R-[A-Z]+-\d+"),  # requirements 需求条目 ID（行首）
        re.compile(r"迭代计划"),  # README 导航项（指向 plan.md）
        re.compile(r"子文件"),  # 测试组织规范（拆分到子文件 test_xxx_partN.py）
        # ── folders.md 统计表行（如 | ├ archive/ | 版本归档 |）──
        re.compile(r"archive/\s*\|"),  # 统计表行（如 | ├ archive/ | 版本归档 |）
        # ── 工具自身说明（描述脚本跳过/豁免/禁止归档目录引用，而非引用归档内容） ──
        #  匹配"豁免/跳过/不扫描/排除/检查/不得/禁止 归档目录或归档引用"的工具说明行
        #  （含"正文不得引用 docs/archive/"这类规则叙述）；
        #  可能只写"归档文件引用"而不含 archive/ 路径，故用"归档(?:目录|文件|引用|路径)"兼容
        re.compile(r"(?:豁免|跳过|不扫描|排除|检查|不得|禁止).*(?:archive/|归档(?:目录|文件|引用|路径))"),
        re.compile(r"版本头豁免"),  # 工具自身说明（描述版本头豁免规则，含示例版本号）
        # 工具说明行豁免：描述"检查哪些历史痕迹/来源叙述/原旧实现"的元描述，
        # 而非文档实际含历史痕迹（如 developer-guide.md 的检查规则说明）。
        # 命中"检查/检测/扫描 + 痕迹/来源/原旧/迁移/重命名/迭代 + 描述"组合才豁免。
        re.compile(
            r"(?:检查|检测|判定|扫描|检出|识别|不得带|不得包含|不得出现|不应记录|禁止出现).{0,12}(?:历史痕迹|来源叙述|原旧实现|迁移重命名|变更痕迹|迭代标记|版本号标记|归档引用|任务编号)"
        ),
        # ── 补强模式的误报排除（当前状态/运行时语义，非历史痕迹） ──
        re.compile(r"历史数据|历史(?:序列|区间|值|曲线|走势|数据点|K线|回撤)"),  # 运行时历史序列/指标
        re.compile(r"当前版本"),  # 当前版本是运行时状态描述
        re.compile(r"之前缓存|此前已|以前端|以前台"),  # 运行时缓存行为/方位描述
        re.compile(r"历史日期|历史[^。\n]{0,4}(?:快照|抓取|收盘|数据源)"),  # 数据范围/数据源历史
        # IP 地址 / 端口（运行时访问语义，如 Web 界面 http://127.0.0.1:8000）。
        #   IPv4 内嵌 0.x.x 子串（127.0.0.1→0.0.1）会被裸版本号模式误匹配，整行豁免。
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b(?::\d{1,5})?"),  # IPv4 地址（含端口）
    ]


# 模块级缓存（模式列表固定，避免逐行重复构建）
DOC_PATTERNS = _doc_patterns()
EXCLUDE_PATTERNS = _exclude_lines()
#: 豁免并集：任一豁免命中 ⇔ 并集命中——逐行只扫一遍而非 N 条逐一 search
EXCLUDE_UNION = re.compile("|".join(f"(?:{p.pattern})" for p in EXCLUDE_PATTERNS))


def is_excluded(line: str) -> bool:
    """检查该行是否命中豁免（合法当前状态/流程描述）。"""
    return EXCLUDE_UNION.search(line) is not None


# 目录树行专属来源叙述补强：无文件后缀的模块名（"从 framework 拆出"类）
# 带后缀模式覆盖不到。仅树行入检——正文的"从 X 提取"可为运行时数据流语义
# （如"从 pipeline_data.diff 提取环比"），树行描述只讲文件职责、来源模块名
# 一律属历史痕迹
TREE_ONLY_PATTERNS = [
    (
        r"(?:自|从|由)\s*[`\w./_-]+\s*(?:拆出|拆分|提取|分离|合并|复用|迁移)",
        "HIGH",
        "来源叙述（从XX拆出/拆分——树行描述只讲文件职责）",
    ),
]
