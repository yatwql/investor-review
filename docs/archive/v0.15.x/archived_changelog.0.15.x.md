# 变更日志归档 — v0.15.x

> 归档时间：2026-10-25（v0.15.8 发布并入；已并入 9 段：v0.15.0（10-24）、v0.15.1（10-24）、v0.15.2（10-24）、v0.15.3（10-24）、v0.15.4（10-24）、v0.15.5（10-25）、v0.15.6（10-25）、v0.15.7（10-25）、v0.15.8（10-25））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.15.0 ~ v0.15.8（2026-10-24 ~ 2026-10-25）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.15.0] - 2026-10-24

### Changed

- **`rf-842` 日志动线场景用例长期失效（TUI 动线驱动器覆盖缺口）**：`_cmd_diagnose_menu` 等处函数内局部导入 `input_choice`，驱动器只 patch 模块属性无效，非 TTY 下回退内置 `input()` 直接读真实 stdin；该动线因此从未真正跑通（仅在 P2 regression 档暴露）。修复：驱动器增补 `builtins.input` 兜底（不 patch 源头，避免跨用例永久绑定），动线按键按菜单分层更新为 `[D]→[V]→级别→按键→[0]→[X]`，契约快照同步并在用例 docstring 说明「击键加长来自菜单分层、不是新增确认屏」。
- **`rf-841` changelog 指针行跨小版本时指向旧档**：`apply_changelog_release` 只重写反引号内的归档文件名，链接目标 `(../archive/<minor>.x/...)` 保持原样——文件存在所以死链检查不报，读者点进去看到的是上一系列的归档。修复：指针行正则同时改写链接文本与目标路径；补回归用例 `test_pointer_line_target_path_follows_minor`（跨小版本场景）。

- **`rf-840` 发布工具链契约不一致（新小版本首版发布硬失败）**：`release.py archive-init` 生成的 changelog 归档索引行是占位形态 `— v0.15.x（date ~ date）`，而 `prepare` 的索引改写正则只接受 `vX.Y.Z`（`v[\d.]+`）→ 0.15.0 首发在 prepare 阶段报「归档索引行改写失败（格式与预期不符）」，必须先手工改索引行才能继续。修复：`apply_changelog_release` 的索引正则接受占位形态 `vX.Y.x` 并按「该 minor 首个版本」语义归一为 `v{release}（date）`；真实仓库契约测试（批次标题/完成节）对「刚 init、尚未发布」的空骨架放宽为「有则同形」；补回归用例 `test_archive_init_placeholder_line_is_accepted`（占位行直接交给首版发布）。
- **全量核对管理文档与用户文档（内容过期 / 组织顺序）**：按「事实对码 + 陈旧标记扫描 + 目录覆盖」三路核对 10 份管理文档与 12 份用户文档，修正 6 类问题——① **`llm-technical.md` 计价章节仍写 `llm_settings.json → pricing`**（第 6 轮已迁出）：10.1 合并规则、10.4 配置覆盖、10.5 货币、12.1 配置归属表与 12.2 全局键名清单统一改为 `llm_pricing_ref.json`（含缺失/非法/版本不符的降级口径与结构设计文档链接）；② **`data-and-backup.md` 「三个文件含敏感信息」不实**（实为两份密钥 `llm_key.json`/`data_key.json`，其余六份可共享）：改正并补全 8 份文件清单；新增「结构版本不符怎么办」——三个带 `version` 的文件只认当前结构、需删档重建（原文档只说「缺键回落默认」）；③ **`faq.md` 备份问答只列 3 个文件**：改为「持仓 Excel + 整个 `data/config/` + `data/history/`」并列全 8 份配置、指向备份手册的现成命令；④ **`how-to-config.md` 缺 `llm_pricing_ref.json`**：A 节补「`data/config/` 的 8 个文件」一句话索引；⑤ `reports-instruction.md` 两处开关归属仍写「`[S]` 独立章节与回放块」→ 改为 `[C]` 面板「默认关闭的整章」/「关联产物」块；⑥ **组织顺序**：`testplan.md` 新增目录（列全部顶级节与两道门禁子节）、`developer-guide.md` 目录补「概述 / 文档地图 / 新人 30 分钟路径」、`how-to-config.md` 目录补「S. 日志配置」、`how-to-config-llm.md` 目录补「参数合法范围」。另清理两处过期信息：`test-coverage.md` 的 2026-09-29 一次性采集说明改为耗时口径说明、`scripts-reference.md` 的版本示例改 `X.Y.Z-dev`。代码侧同步一处易漂计数：`_test_runner/machine_info.py` docstring「14 行」与字段数（15）不符，改为按字段表长度表述。
- **技术债登记：事实校验评估函数参数收敛**（`rf-839` / `plan-201`，P2 待办）：`llm/fact_checker/_numerical.py::_evaluate_percent_value` 单函数 22 个参数（7 基础值 + 10 语境开关布尔 + 5 数据映射），新增一种语境要同步改签名/文档串/调用点与全部直接用例，语境判定的隐式顺序只体现在函数体里。修复方向已写入台账：收进上下文对象、签名收敛为单参，语境优先级在构造侧单源声明；前置是先补「语境词 → 期望结果」对照表测试作为等价判据（现有 30+ 用例散在 5 个测试文件），生产调用点唯一（`check_numerical_consistency`），回归面可圈定。
- **近 48 小时变更技术债核查与修复**：逐项核对本轮配置重构（第 1~13 轮）与两处缺陷修复留下的债，发现 4 处并全部消解——① `scripts/_doc_drift/_format.py` 因面板编号重写涨到 671 行（越过脚本警告线 600，且 review-findings P3 仍写「当前无登记项」）：把面板编号族（`[C]`/`[S]` 编号派生、组/块区间、features 键名映射）拆到新模块 `_doc_drift/_format_panels.py`，两份均落回警告线内（521 + 158），门面与原面 re-export 不变；② `src/python/config/__init__.py` 202 行越过薄壳警告线：docstring 里与 `folders.md` 重复的子模块清单收敛为一行指引（→ 194 行）；③ `static/web/main.js` 的 `makeConfigDesc(text, indent)` 参数语义含混（传 `'0'` 表 flush、传 `'24px'` 表默认）：改为布尔 `flush`；④ `llm/fact_checker/_utils.py` 简称归一化逻辑在 `_has_subject_candidate` 与 `_locate_subject_in` 各写一遍：抽出 `_alias_normalized()` 单源。复查结果：超警告线文件 0 个、无 TODO/FIXME、`ruff check`/`format --check` 零告警、`dev-verify` 7993 通过；`scripts-reference.md` 第 8 条与实现口径同步（双面板派生 + 新模块落点）。
- **`rf-836` 事实校验自动修正器产出畸形数值（`持仓收益率+-9.0%`）**：三条同修——① **数值前文语义**：新增局部窗口判定（`_is_non_rate_pre_word_context` + `_NON_RATE_PRE_WORDS`），数值紧邻前文是「占比 / 最大持仓 / 份额 / 市值 / 仓位 / 集中度」等度量时不参与收益率修正（整句级判定在「最大持仓 12.3%，持仓收益率 +4.55%」共现句里必然失效）；② **主体归属改为三级作用域**：括号内持仓代码 > 本分句内可识别主体（代码 / 全名 / 简称 / 尾名）> 全句四来源，修复同句多代码时「最近者」被括号闭合符带偏（+4.55% 被判给后一个品种并改写成 -9.0%）；③ **符号归一**：替换时连同原值前导 `+`/`-` 一并吃掉，新值符号优先（正值且原文显式 `+` 时延续），并在修正后做畸形自检（`[+-]{2,}` 命中则整批放弃写回，保留原文）。回归用例 6 例（`TestNonReturnMetricAndSignNormalization`：占比不修 / 括号作用域 / 分句作用域 / 符号归一 / 畸形拦截 / 整链路无连续符号）。
- **`plan-198` 配置体系重构第 13 轮：质量门禁全量**：五道闸口全绿——`verify` 11318 通过 / 0 失败；十守护零 finding；性能门禁 basic **0.48s ≤ 60s**；`portability` 两探针通过（`LC_ALL=C` 下 `pip` 解析 `requirements.txt` + 隐式编码严格档）；`ruff check` / `ruff format --check` 零告警。门禁暴露并修正两处真实缺陷：① `rf-837` 计价模块显式重载被懒加载覆盖（详见上条）；② `rf-838` `test_json_comments` 子进程缺少显式编码（portability 探针拦截）。同批按实测刷新 `plan.md` 各任务状态：`plan-185` 收益口径验收给出近三轮真实观测（3 / 9 / 2 处，基线 10，尚未稳定达标）、`plan-70` 账本数据更新为已结算 16 / 待结算 42、`directional_total = 12`、`plan-55` 显式标注「评测脚本未建、对照未开跑」，`plan-198` 转为「已实施，待发布归档」。
- **`rf-837` 计价模块显式重载后定价被懒加载覆盖**：`llm/pricing.py::reload_pricing()` 装载新价后未置 `_PRICING_LOADED`，进程内首次计费仍会再读一次配置文件，把调用方刚装载的定价换回文件值——表现为「先 reload 后计费」的调用顺序里定价自己变回去，且只在首次计费时发生（回归用例单独执行失败、整文件执行通过）。修复：`reload_pricing()` 在 `finally` 置 `_PRICING_LOADED = True`（显式重载即「已加载」）；补回归用例 `test_explicit_reload_is_not_undone_by_lazy_init` 锁定「显式重载后计费直接使用已装载的定价」。
- **`review-findings.md` 收敛为最新状态**：`rf-836` 去掉「根因链（2026-10-23 运行复现）+ 模型原文摘录 + 把…改写」的复盘叙事，改为当前缺陷事实（三类错误并列）与三条修法；`rf-257` 去掉旧任务编号引用与旧临时目录名（`docs/tmp/rf257/` → `docs/tmp/browser-verify/`），保留待验 4 类项与复跑命令；P3 文件膨胀登记的四段解释压缩为「单一事实源 + 入表规则」两行，档位数字不再与 `check-file-length` 脚本重复罗列；P1/P2 入选标准由引用块改单行。46 → 45 行，待处理项与编号源不变。
- **`plan.md` 收敛为最新状态**：删掉与 `CLAUDE.md` / `developer-guide.md` 重复的「命名纪律」段（改为一行指引，避免三处维护）；三项已实施条目（`plan-195/196/197`）的实现过程记录压缩为「落地要点 + 机检载体 + changelog 指向」各一句，不再保留已失效的「现状与问题 / 动作」原文；待办条目（`plan-92/93/185/198/199/200/70/55`）的「现状与问题」统一改为「现状 / 问题」，去掉过程性描述与冗余限定（如「自上次发布以来」「按触点清单逐份核对」这类实施叙述），只留判断所需的现状事实与动作；P1 空档、各档入选标准改为单行说明。文档 131 → 124 行，在办项与编号源不变。
- **`plan-197` 配置体系重构第 12 轮：文档与契约登记收口**：按触点清单逐份核对手册与管理文档，修正配置重构遗留的陈旧表述——主菜单项数与旧顶层键（`README.md` 两处「19 项」→ 14 项四组、`manuals/README.md`、`testplan.md` 三处「18/19 选项」与已下沉的 `[M]/[I]/[A]/[V]/[H]/[T]` 顶层键描述）；Web 配置面板「11 组 / 八组分块」在 `how-to-start.md` 与 `how-to-config.md` §Q 改为「五域分区 + 块分组」，表内键位同步（目录三项 `[G]`→`H`/`F`/`O`、线路优先级 `[G]`→`L` 第 7 项、诊断项改 `[D]`→`V`/`H`/`T`/`L`）；`how-to-use-cli-mode.md` 的配置类菜单与诊断项列表按新层级重写；`how-to-use-web-mode.md` 开关类表述改为「六组章内内容 + 独立整章/关联产物 + 智囊团子项」。抽检三处与代码逐字一致：`[D]` 四项（L/V/H/T）、`[G]` 七项四组（H/F/O · L · I/A · M）、`[S]` 20 项与 `[C]` 16 项（含子项 `7.1`/`7.2`）；契约档结构守卫（`test_design_doc` / `test_design_tui_doc` / `test_prompt_contract`）与台账统计刷新均绿。
- **Jev 设计/评测文件命名与状态补齐**：`jev-news-correlation-{design,evaluation}.md` → `jev-news-judgment-{design,evaluation}.md`——两份文件讲的是「判定迁移」，与同族 `config-*-design.md` 一样按内容取名；设计文件头部补「**当前态**：待评测——三方对照未开跑，处于已定稿待闸，评测结论为维持现状/放弃即归档」，读者不必翻计划表即可知道进度。评测文件里的脚本拟名按仓库脚本命名约定更正为 `eval-jev-news-judgment.py`（活动类型前缀 `eval-`；原拟名缺前缀且与评测内容不对应）。引用面（`plan.md` 先决门槛与待实施条目、`folders.md` 目录树）同步。
- **配置文件族命名对齐**：`llm-settings-nesting-design.md` → `config-llm-settings-design.md`、`logging-config-design.md` → `config-logging-design.md`——与同族 `config-tui-design.md` / `config-web-design.md` / `config-files-design.md` 统一为 `config-<范围>-design.md`，从文件名即可看出「属于配置体系设计」；两份文件标题同步为「LLM 配置设计（`llm_settings.json` 纵切，模块为第一层）」与「日志配置设计（`logger.json` 独立成文件）」。引用面（`config-files-design` 关联行与职责表、`config-tui-design` 日志设置段、`config-web-design` 运行与诊断域、配置重构计划依据行、`folders.md` 目录树描述、changelog）同步。
- **配置面设计按渠道拆成三份独立文件**：`config-panel-design.md`（679 行，四类内容混排）拆为 [`config-tui-design.md`](../plan/config-tui-design.md)（共用概念：组/条目名/标记/文案来源 + 四组菜单层级、七项四组、`[C]`/`[S]` 面板、键位与分组标题纪律 + 终端契约 + TUI 影响面与验证）、[`config-web-design.md`](../plan/config-web-design.md)（五域分区、块与控件、保存语义、状态与反馈、无障碍与响应式 + `DESIGN.md` 契约 + Web 影响面与验证）、[`config-files-design.md`](../plan/config-files-design.md)（八份文件职责边界、不做旧版兼容的演进策略、`config.json` 取舍、书写与读取约定、架构约束遵从 + 配置文件影响面与验证）。三份各自带「影响面与验证」（代码触点 / 文档同步点 / 自动验证 / 人工验证）与图样指向，章节号从 1 连续重编，跨文件引用改为按章节标题指引；原合并文件删除，`folders.md` 目录树与全仓引用（`web/config_edit.py`、`test_config_surface_contract`、`web_mock_build.py`、`llm-settings-nesting-design`、`logging-config-design`、配置重构计划）同步新路径。
- **`docs/plan/` 设计与计划文件梳理（文件名语义化 + 内容只留最新状态）**：`config-panel-taxonomy-design.md` → `config-panel-design.md`（内容已覆盖 TUI 三层面板 / Web 五域 / 配置文件边界，原 "taxonomy" 只描述其中一节）；`decision-reflection-shadow-design.md` → `decision-reflection-design.md`（去掉外部参照实现名 "shadow"）。内容清理：配置重构计划把已完成 11 轮的完整交付/验收压缩为状态表（细节随发布归档），§1 总览去掉"预估人日"列、§0.4 回滚策略改为按轮类型表述；`web-browser-verification.md` 去任务编号（标题、脚本目录 `docs/tmp/browser-verify/`、环境变量前缀）与过程叙述（"首版脚本"、"复测并入收尾"）；`decision-reflection-design.md` 去任务编号与「死线未过」过程措辞；`jev-news-judgment-design.md` 去「草案」稿态词；`config-panel-design.md` §8.4「待登记事项」改为「契约登记位置」。`folders.md` 目录树描述按最新内容重写，全仓引用（代码注释、测试文档串、手册、台账）同步新文件名。
- **`plan-196` 配置体系重构第 11 轮：Web 配置面交互与状态**：新增配置工具条（`共 N 项 · 已改 M 项`，基准取服务端 `defaults`）、关键词筛选（按标签 / 说明 / 键名实时过滤，空块与空域自动隐藏、清空即恢复）、域导航 chips 与滚动高亮（`IntersectionObserver`，不支持时降级不亮）、深链 `#domain-<域键>`（与页签 hash 共存：`domain-` 前缀先切配置页再定位）、块计数 `N 项 · M 开`、≤768px 单列断点（工具条纵向 / 导航横滚 / 输入占满行宽）。保存语义按契约 §4.5 校正：即时保存类失败回滚勾选并就地报错；显式保存类（文本 / 数字）失败**保留输入值**供重试（原实现误回滚，本轮修正）。机检：`src/test/unit/web/test_web_config_interaction.py` 17 例（回滚与就地报错、显式保存保留输入、筛选匹配范围与空块隐藏、计数取 defaults、chips 由 domains 派生、深链与页签 hash 共存、滚动高亮降级、720px 断点、无 `innerHTML` 赋值）；手册 `how-to-use-web-mode.md` 配置面板章按五域重写。
- **`plan-195` 配置体系重构第 10 轮：Web 配置面契约**：`web/config_edit.py` 新增 `domains` 编排契约（五域：报告内容 / 呈现与机制 / 数据与线路 / LLM 运行 / 运行与诊断，每域带标题、域说明、TUI 导引与**有序块清单**，块 id 含 `features.<组键>`）+ 元数据面 `labels`/`descriptions`/`defaults`/`needs_hint`（覆盖白名单全部可编辑键，由注册表与共享白名单派生）+ `logging`（日志设置六项，含枚举与范围）+ `reference`（只读计价参考）+ 独立整章/关联产物两块（键集取自章节注册表）。`static/web/main.js` 改为按域分区渲染与块渲染器分派（`BLOCK_RENDERERS`，`features.` 前缀分支统一承接），删除前端 `CONFIG_LABELS`/`ANON_LABELS` 中文表——标签、说明、出厂默认（`✻ 已改` 基准）与匿名化档位描述全部服务端下发，前端零中文表；新增日志设置块（下拉/数字框 + 显式保存）与只读参考块；域内块全空则该域不出现，域锚点 `#domain-<key>` 就位。共享编辑层新增 `logging.*` 六键（`write_logger_config`，枚举/范围与 TUI `[D]→[L]` 同源，非法值不落盘）。样式：新增域分区与域标题（结构色 `--primary`，与 TUI 分组标题同色调）与项说明副行，间距/字号全部取档内值。机检：`src/test/unit/web/test_config_surface_contract.py` 17 例（块↔渲染器双向相等、元数据覆盖、无中文表、无 `innerHTML` 赋值、日志写入与拒绝、参考面只读）；`technical.md` Web 配置面三处、`folders.md` 目录树、`test-coverage.md` 计数同步。
- **TUI 图样采集去抖与脱敏**：`docs/plan/config-panel-mockup/tui_capture.py` 新增 `_sanitize` 归一通道——日志正文按级别替换为同形态示例行（保留级别配色与长短差异），计数/体积/日期/本地路径/真实线路名/缓存清单一律归一为固定值；真实线路名从 `llm_providers.json` 只读派生后脱敏为「示例线路A/B」。效果：① 图样**可重复生成**（同代码状态连续两次采集逐字节一致，此前日志屏、费用摘要、缓存统计屏每次重拍都有噪声 diff）；② 图样**不含用户真实数据**（持仓品种名与代码、真实缓存键、端点名、机器绝对路径、真实日期均已替换）。TUI 图样按新通道重拍（30 屏）。
- **配置重构迭代计划与 Web 设计同步到当前分层**：迭代计划（15 轮）第 8 轮交付/验收改为「主菜单配置组 C/S/G/R、`[G]` 七项四组（目录与文件 H/F/O · LLM 调优 L · 基准与脱敏 I/A · 索引 M）、`[D]` 子菜单归 `handlers_log`」，并新增两条验收（`[G]` 四组标题经 `group_heading` 产出；`[G]` 长标签折行不溢出）；第 9 轮验收补「两面板分组标题同款」；第 10 轮交付明确五域与块划分、跨域示例（`[G]`「基准与脱敏」跨数据与线路/呈现与机制两域）、块标题取结构色与对应验收；§3 架构约束映射补「分组标题单源」「结构色单源」。Web 设计（`config-panel-design.md` §4）补「结构色同源」原则、`domains` 五域完整示例（含 `tui` 导引与块清单）、§4.10 分区轴改 C/S/G/D 并补「分组标题表达」行、§5.1 影响面标注 `.config-group-title` 取结构色；Web 图样按新契约重生成。
- **`[G]` 第三组定名「基准与脱敏」**：该组两项为「对比基准指数」（基准）与「持仓匿名化」（脱敏），组名同时点到两个成员，比「基准与指数」更贴合内容（后者只覆盖其一）。手册 `[G]` 节标题、渲染样例、分组列、需求菜单表、技术菜单行、目录树描述与设计文件（分类设计 §3.0/§3.1/§3.2/§3.7、图样生成器）同步；TUI 图样重拍。
- **`[G]` 第三组更名为「基准与指数」**：原「基准与呈现」名不副实——该组两项（对比基准指数 / 持仓匿名化）里匿名化并非「基准」，而「指数」正是该组的主项；同批把手册 `[G]` 节标题由「目录与文件 / LLM / 基准与呈现」更正为「七项四组：目录与文件 / LLM 调优 / 基准与指数 / 索引」，与面板实况一致。
- **分组标题样式全局统一（TUI 与 Web 同色调）**：新增 `text_layout.group_heading()` 作为分组标题的**唯一产出点**——形态固定 `── 组名 ──`、结构色（蓝 + 粗）、按传入列宽折行；主菜单四组、`[C]` 四块、`[S]` 六组、`[G]` 四组全部改为经它产出（`[G]` 原为裸色组名，现与首页同款），组间以空行分隔。`[G]` 的组名同步为「目录与文件 / LLM 调优 / 基准与指数 / 索引」。修正两处旧缺口：`[S]` 组标题此前无 `──` 装饰、`[C]` 组标题未走统一折行预算（窄屏可能撑破右边框）；`[G]` 条目行过长时改为折行而非溢出（40 列下 `LLM 设置（运行参数 / 多链线路）` 此前超宽 1 列）。Web 侧 `.config-group-title` 改用结构色 `var(--primary)`，与终端同色调（表达形态随渠道：浏览器用分隔线 + 结构色，终端用 `──` 装饰）。契约同步：`DESIGN-TUI.md` 新增「分组标题全局同款」条、`DESIGN.md` 护栏新增第 12 条（分组标题取结构色、禁用状态色）、`docs/plan/config-panel-design.md` 新增 §3.7 与 §4.9 块标题规格、TUI/Web 图样重拍。- **主菜单键位与分组调整（`[P]`→`[C]`、追问归入生成组、调仓标签点明独立报告）**：配置组的章节显隐入口由 `[P]` 改为 `[C]`（`C`=Chapter），与「配置 `C`/`S`/`G`/`R`」的字母语义对齐；`[Q]` 报告对话式追问由「数据与查看」移入「生成报告」——该组真实语义是「产生或消费报告产物的动作」，`Q` 消费已生成报告且消耗 LLM、受 `report_qa` 门控会整项消失，与零成本、恒在的缓存维护（`1`/`2`/`3`）不同族；`[W]` 标签补「（独立报告）」（17→29 显示宽，仍低于 48 列不折行上限），点明它产出的是独立 diff 报告、不受章节配置面板支配。同批更新两份手册主菜单块与 `[W]` 章节、`requirements.md` §3.2 菜单表（分组标题与组内顺序由 `check-doc-drift` 第 19 项逐项校验）、`technical.md` 菜单行、`DESIGN-TUI.md` 键位纪律（配置组取 `C`/`S`/`G`/`R`）、`docs/plan/` 四份设计文档与 TUI 图样（按新菜单重拍）；面板编号校验同步改为双面板派生（`[C]` 章节块 + `[S]` 内容组）。`[G]` 二级的 `C`（持仓信息目录）与主菜单 `C` 同字母不同层级，按既有键位纪律放行。
- **`[G]`→`[D]` 子面板持仓信息目录键位 `C`→`H`**：主菜单 `C` 让给章节显隐后，二级/三级面板里的 `C`（持仓信息目录）与新主菜单键同字母，虽有「层级间互不冲突」先例，但读者按提示找入口时仍易混淆。该子面板键位改为 `H`（Holdings），与同层 `F`（文件名）/`O`（输出目录）/`M`（入口地图）对齐；`[D]` 诊断面板的 `H`（数据源健康历史）父层不同，层级间仍互不冲突。同批把手册「配置与目录信息」三级面板块对齐真实渲染（去掉块内已不存在的 `[L]` 调优项、返回项写作「返回全局设置」）、把陈旧的父键写法 `菜单 D → X` 更正为 `菜单 G → D → X`、`faq`/`how-to-config` 目录相关表格同步；`docs/plan/` 分类设计文档的 `[G]` 二级树按代码实况重写（`D` 为「查看配置与目录信息」并挂三级 `H`/`F`/`O`/`M`），键位纪律补三级字母清单；TUI 图样重拍。
- **`plan-194` 配置系统重构第 9 轮：`[C]` 章节显隐与 `[S]` 章内内容分层**：新增 `config/chapter_registry.py` 作为 `[C]` 的唯一事实来源——16 项按四块连续排列（顶层章节 5 写 `config.json` 的 `enable_*`、LLM 章节 7 写 `llm_settings.json` 的 `enabled_llm`、默认关闭的整章 3 与关联产物 1 写 `features.json`），编号与智囊团子项 `7.1`/`7.2` 全部由注册表顺序派生；每个章节的写键经 `chapter_edit_key()` 派生并落在共享编辑层白名单内。新增 `tui/handlers_report_chapters.py`：`[C]` 四块排版、键名恒显（宽/中档行内列、窄档第二行）、`?编号`/`?键名` 展示来源文件与默认值、行尾 `*` 标漂移、LLM 章节保留近 7 日费用摘要、子项在父章节关闭时置灰并提示原因且拒绝写入。`[S]` 面板重写为 `PANEL_GROUPS["[S]"]` 六组 20 项（持仓与交易 4 / 市场与估值 4 / 基金与风格 3 / 事件与摘要 4 / 呈现与交互 2 / 机制与质量 3），编号改由 `features.panel_option_numbers("[S]")` 按组序派生（增删开关自动重排），不再混排 LLM 模块、独立整章与关联产物。同批更新 `how-to-use-tui-menu.md` 两面板章节与 26 项键名映射、`how-to-config.md`/`how-to-config-llm.md` 面板归属与编号、`requirements.md` 菜单行与 §11.5、`technical.md` 菜单行/模块表/写入分派、`DESIGN-TUI.md` 子项编号键义与四块标题、`folders.md` 目录树。测试新增章节注册表结构 13 例（四块划分/编号派生/来源注册表同源/写键可达）与 `[C]` 面板 19 例（四块渲染/四来源写入/子项闸门/只读详情）；`[S]` 导航、布局、窄屏与矩形用例按新分层重写。
- **`plan-193` 配置系统重构第 8 轮：TUI 菜单与分层**：主菜单收敛为 **14 项**（生成 E/B/L/W · 数据 Q/1/2/3 · 配置 P/S/G/R · 诊断 D · 退出 X），顶层 M/I/A/V/H/T 全部下沉；新增 `[G] 全局设置` 七项（D/F/O/L/I/A/M，数字为主入口、字母为别名）与 `[D] 诊断与排查` 四级（L 日志设置 / V 运行日志 / H 健康历史 / T 系统自检，缺省选中 T，`0` 返回主菜单）；`[D]→[L]` 日志设置六项（级别/轮转/查看器，越界拒绝）。`[G]→L` 调优面板补第 7 项「多链线路优先级」。菜单标签统一收敛到 ≤48 显示宽；`_CONFIG_ENTRY_MAP`、目录信息子菜单返回文案同步新层级。文档同批更新 `how-to-start.md`/`how-to-use-tui-menu.md` 菜单块与章节层级、`requirements.md` §3.2、`how-to-config.md` 路由、`datasource-reliability.md`/`how-to-config-llm.md`/`how-to-use-cli-mode.md`/`scripts-reference.md`/`technical.md` 菜单键引用与 `folders.md` 目录树。回归 13 例：菜单 14 项与分组序、标签宽度、[G]/[D] 路由/双通道/返回语义、日志设置写入与非法拒绝。
- **`plan-192` 配置系统重构第 7 轮：日志配置独立成 logger.json**：新增 `data/config/logger.json`（`version=1` + `file`/`console`/`viewer`）与 `config/_logging.py`（读取/校验/写入，加载与面板共用范围表；写回文本 patch 保注释）；`core/logger.py` 启动时内联读取（不导入 config 包），按配置创建控制台/轮转文件 handler（路径、级别、maxBytes、backupCount、颜色），`INVEST_LOG_FILE_LEVEL` / `INVEST_LOG_CONSOLE_LEVEL` 环境变量优先级更高；日志目录不可写时告警并降级为仅控制台。非法级别/越界数值/含 `..` 路径：加载告警回落默认、保存拒绝且不落盘；`version` 不符拒绝并提示重新生成。同批更新 `how-to-config.md` §S、`requirements.md` §11.1.2、`technical.md` 配置矩阵、`developer-guide.md` 环境变量说明与 `folders.md` 目录树。回归 16 例：默认生成/加载回落/保存拒绝/环境变量优先/轮转参数/不可写降级/颜色关闭。
- **`plan-191` 配置系统重构第 6 轮：计价参考独立成文件**：新增 `data/config/llm_pricing_ref.json`（`version=1` + 策略 + `models` 逐模型覆盖）与 `config/_llm_pricing.py`（读取/校验/逐模型合并/mtime 缓存/默认生成器，含中文注释模板）；`llm/pricing.py::reload_pricing()` 数据源切换为该文件，`PRICING_MERGED` / `reload_pricing` 接口不变。合并口径：内置 `MODEL_PRICING` 为基础价，文件只覆盖出现的模型与字段；文件缺失 → 仅内置价；单条非法 → 告警跳过；`version` 不符 → 拒绝加载并提示重新生成（内置价兜底，报告仍可生成）。`pricing` 从 `llm_settings.json` 移除（混入按未知键告警），仓库内 `data/config/llm_settings.json` 已重建为 v2。同批更新 `how-to-config-llm.md` 覆盖方式、`requirements.md` §11.1.1、`technical.md` 配置矩阵与 `folders.md` 目录树。回归 10 例：缺失回退/部分覆盖/非法跳过/策略回落/版本拒绝/计费等价（浮点容差）。
- **`plan-190` 配置系统重构第 5 轮：生成参数入指纹**：`llm/module_fingerprint.py` 新增 `generation_params_suffix(module)`，把模块的温度 / 输出上限 / 思考开关、预算与强度统一并入指纹；`cache`、并发、重试等与生成无关的项不参与（避免无谓失效）。七个构造器（global_macro / expert_review / health_check / penetration_deep / self_review / debate_procon / debate_synthesis）全部接入；辩论综合另并入 `debate.procon.synthesis_temperature`。预检侧与写侧继续共用同一构造器，同源由结构保证；`get_llm_config()` 不可用时后缀为空，存量缓存不整体失效。同批更新 `technical.md` 指纹说明与 `folders.md` 目录树。回归 15 例（参数变化换键 / 无关项不变 / 两次调用一致 / 配置不可用保持原键）。
- **`plan-189` 配置系统重构第 4 轮：LLM 参数校验**：`config/_validation_llm.py` 新增 `LLM_PARAM_RANGES`（temperature 0–2 / max_tokens 1–200000 / timeout 5–600 / thinking.budget 1024–100000 / effort 枚举 / 辩论合成温度 0–2 / 辩论单报告预算 1024–500000 / 辩论单次超时 5–600）与 `param_violation()`（文案含键名/当前值/合法范围）。加载路径经 `sanitize_document()` 越界回落出厂默认并逐条告警（只改内存视图、不改写用户文件）；面板写入统一拒绝（`edit_ops` 数值越界文案改为「取值 X 超出范围 [min, max]」），非法值不落盘。同批更新 `how-to-config-llm.md` 参数合法范围表、`requirements.md` §11 引言、`technical.md` 校验说明与 `folders.md` 目录树。回归 17 例：八参数合法/越界/类型错误表驱动、加载回落与不改写文件、面板拒绝与写后原值。
- **`plan-188` 配置系统重构第 3 轮：LLM 配置 v2 结构与默认生成器**：`llm_settings.json` 落盘改为 schema v2 嵌套结构（`defaults` / `modules` / `runtime` / `advanced`），新增 `config/_llm_schema.py` 负责版本校验（缺失或 ≠2 拒绝加载并提示删除重生成）、三层缺省合并（模块值 → `defaults` → 内置默认）、`flatten()` 展平与 `apply_flat_updates()` 反展平、未知段/键保留，以及写回用的 v2 文本 patch（保注释）。对外契约仍为扁平键（`model_*` / `thinking_*` / `enabled_llm` / `llm_max_*` / `debate` / `fact_check` / `pricing`），`llm/` 包零改动。`_llm_settings_defaults.py` 生成器改为输出 v2 JSONC（分类注释 + 逐项中文说明），扁平默认值 `_DEFAULT_LLM_SETTINGS` 由 v2 展开派生；`write_llm_settings()` 接受扁平更新、反展平后写盘（值变化走文本 patch 保注释，结构变化才重排）；`read_llm_settings_file()` 返回展平视图。`DataModuleDef.llm_settings_keys()` 取消 news_correlation 的 output_brief 例外（v2 参数面对所有模块统一）。同批更新 `how-to-config-llm.md` 结构参考、`requirements.md` §11 引言、`technical.md` 解析矩阵与 `folders.md` 目录树。回归 17 例：生成器与扁平默认互展、版本拒绝（含文件名与重生成指引）、三层优先级矩阵、展平契约键、未知段/键保留。
- **`plan-187` 配置系统重构第 2 轮：注释契约**：新增叶子模块 `core/json_comments.py`（`strip_json_comments` / `loads` / `load`，仅标准库），`config/_comments.py` 改为再导出——`core/logger.py`、计价等 core 级读取方不必导入 `config` 包（依赖不成环）。`features.json` 读取改经统一剥离器；写入改为**键级文本 patch**（改值替换、恢复默认删键、紧凑单行自动重排），读—改—写后分类注释与逐项说明保留；文件缺失时首次写入以中文说明模板（`_FEATURES_TEMPLATE`）为底。同批更新 `technical.md` 配置解析矩阵/注释段、`requirements.md` §11 引言、`how-to-config.md` 注释说明与 `folders.md` 目录树。回归 18 例：注释剥离（字符串内 `//`、`/* */` 与转义引号不误伤）、五份配置文件注释样本读取、features round-trip（保存/恢复默认/模板生成/紧凑重排）、叶子模块导入边界（不拉入 config）与 `core/logger.py` 无 config 导入。
- **`plan-186` 配置系统重构第 1 轮：注册表与域模型**：功能开关从「四组作用域」改为**八组内容位置**（持仓与交易 4 / 市场与估值 4 / 基金与风格 3 / 事件与摘要 4 / 呈现与交互 2 / 机制与质量 3 / 独立章节与回放 4 / 章节内选项 2，共 26 项），新增 `GROUP_DOMAIN`（组→五域）、`DOMAIN_ORDER`/`DOMAIN_LABELS`/`DOMAIN_HINTS`（Web 五域编排与提示）、`PANEL_GROUPS`（`[S]` 六内容组 / `[C]` 独立章＋章节选项）与 `FeatureSwitchDef.needs_hint`；`crisis_replay` 归市场与估值、`prosperity_framework` 归市场与估值、`report_qa` 归呈现与交互、辩论两项归 `chapter_options`（由 `[C]` 作章节子项渲染，不占 `[S]` 编号）。**系统自检转恒上屏**：移除 `doctor_check` 开关（TUI `[T]`、Web 自检卡与 `GET /api/doctor` 恒可用，`doctor` 子命令不变），`FEATURE_GATED_ITEMS` 只保留 `Q → report_qa`。同批同步 `how-to-config.md` 开关表与面板归属表、`how-to-use-tui-menu.md` 的 `[S]` 编号表（8-33）与键名映射、`requirements.md` §11.5/§3.6、`technical.md` 注册表与自检段、`developer-guide.md` 分组表、`scripts-reference.md`/`testplan.md` 描述。回归：注册表不变式/门控用例按 `GROUP_DOMAIN` 与八组重写。
- **`plan-182`（决策不做）迁入归档 + `plan.md` 收敛为最新状态**：`release.py` 的「已完成任务节」识别口径扩到 `❌ 决策不做`（与 ✅ 同为「不再在办」，标记保留以区分做完/不做），plan-182 按机械规则迁入 `archived_plan.0.14.x.md`（标题降为二级）；`plan.md` 去掉流转叙述（「均已实施」「已落地」「已由」一类），plan-185 与 plan-70 的现状改写为可直接执行的态与判据（含 plan-185 实测验收数据），归档索引的 0.14.x 覆盖区间校正为实际日期。回归 2 例（决策不做节被收集 / 「当前迭代」不计入该节）。
- **TUI 追问的报告选择默认项改为本期主报告**：候选列表按「档位优先 + 修改时间倒序」排序——`个人投资分析报告.html` 恒为第 1 项（回车默认），其它报告居中，`调仓模拟.html` 排末档；首项标注「← 回车默认」使默认目标可见，提示语同步为「回车=本期主报告」。根因：调仓模拟每跑一次即覆盖自己的固定名产物、把 mtime 顶到最新，纯按时间排序会把回车默认项落到模拟报告上（同目录并列产物，但语义上属少数派）。同批把 `调仓模拟.xlsx/.html` 与归档名前缀收敛为 `core/constants` 常量（`WHATIF_FILE_BASE` / `LATEST_WHATIF_*`），写入器不再写字面量。

## [0.15.1] - 2026-10-24

- **`rf-862` 发布 prepare 的 changelog 指针路径缺 `v` 前缀**：跨小版本发布把指针目标写成 `../archive/0.15.x/...`，死链检查拦下并中止 prepare。改为从归档文件名派生 `vX.Y.x` 目录；回归用例只截「最近发布」指针行断言目标路径（原用例靠整篇文本命中，索引行掩盖了错误）。


- **`plan-207` 清理旧配置形参兼容**：功能开关迁入 `features.json` 后，10 个 `is_enable_*` 访问器仍保留已不参与取值的 `config` 形参（旧调用签名）；本次移除形参并更新 26 处调用点/测试，删除「传旧 config 也不影响取值」的兼容用例。保留当前规格内的降级逻辑（快照缺市值回退成本口径 R-EVO-02、LLM flat 单凭据格式）——属现行契约而非旧数据兼容。

- **`plan-206` 报告运行观测三项整改**（对应台账 rf-858 / rf-859 / rf-860 / rf-861）：① **去重锚点采集保持默认开启、写侧零读取**——锚点不参与去重判定，39MB 文件的加载+自动压缩（实测约 18.5s，占管线 42%）移出报告主流程：写侧只追加（`write`+`fsync`）、批内去重，跨轮重复由校准工具 `load_anchors` 按键去重（保留最早一条），诊断数据持续积累且报告零读取开销；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关闭采集，压缩改由 `eval-dedup-threshold.py` 评估后默认执行（`--no-compact` 关闭）或 `INVEST_DEDUP_MAINTENANCE=1` 显式触发。② **性能归因细化**——`数据准备` 增加九项子阶段（行情与明细/指数获取/穿透/风格与因子/覆盖与新鲜度/估值与温度/财报摘要与指标/申购与成本位置/明细装配与建议），`LLM+新闻` 增加新闻源抓取/去重与关联/锚点维护/事件窗装配子项。③ **full 显式提示**——`core.system_info.llm_report_unavailable_reason()` 统一判定「未配置 / 章节全关」，full 生成开始时提示「按不含 LLM 内容生成（full 等同 both）」，三渠道同源。回归 7 例；需求 R-DATA-09 / R-PERF-09 与技术/脚本/手册同步。

- **`plan-205` CLI 配置面补齐（config 子命令 + 章节/匿名化一次性覆写）**：新增 `config list/get/set`——白名单键的查看与持久化编辑，复用 `config/edit_ops.py` 同一校验/`.bak`/注释保留/缓存失效路径；`--dry-run` 只校验不落盘；`scheduler.*` 四字段走 `config/_scheduler.py` 严格校验（与 Web 面板归一化分离）。新增全局 `--chapter KEY=on|off`（按章节注册表分派 `config.json` / `enabled_llm.*` / features 三类来源）与 `--anonymize {off,code_display,full_anonymous,summary}`，均为进程内覆写（`config/_runtime_overrides.py`，不写盘、不进缓存）。报告追问按决策不进入 CLI。回归 43 例（`test_cli_config_command` 32 / `test_config_scheduler_spec` 11）；文档同步 CLI 手册 §2/§10.1/§14、配置手册、脚本参考、技术设计（§1.5.3 / §1.8.11 / 语义表：配置编辑改为 TUI/Web/CLI 同一编辑层，白名单实测 9 组 56 条键 / 26 功能开关）与需求追溯（新增 `R-CON-09`）；`rf-856` 修 `[M]` 过期指代与 §10.1 覆盖说明，`rf-857` 修技术文档白名单计数与渠道表述。

- **`plan-204` 测试用例全量审计与整改**：机检补位四类人工判据（自证式用例 / 双结果放行 / 弱断言 / 名称与内容不一致），扫描 586 个测试文件、11,111 个 `def test_`，整改 23 例——安全基线 3 例自证式改触生产（`cache.set` 产物扫描 / LLM 源码禁止日志含 `api_key` / HTML 模板绝对路径扫描）、文件系统边缘 4 例双结果放行改按 `reader` 契约断言、配置崩溃清理补 `assertRaises`、弱断言 11 例补足语义（行业映射锁定指数代码、分位阈值、警告文案、参数校验原因、cassette 响应体、凭据声明字段）、启动向导 2 例合并、2 处死变量清理。对应台账 rf-851（自证式安全用例）、rf-852（双结果放行）、rf-853（崩溃清理），以及 rf-854（弱断言）、rf-855（重复用例与死变量）。

- **`plan-203` 发布流程四处改进（v0.15.0 复盘落地）**：① **失败前移**——`[C]` 日志动线改标 `scenario_basic`（dev-verify 也跑），动线驱动器新增「打点矩阵自证」（`builtins.input` 与各消费方读取入口必须都指向 feeder，局部导入绕过 patch 时直接报错）；② **bench 顺序**——发布子集调整为 `regression → integration → unit → dev-verify`，让 `--fail-fast` 在场景失败时立刻中止长尾 `unit`（实测曾白等约 45s）；③ **台账自证**——失败命令写 `failure`（失败步 / rc / 报告目录 / 失败用例名 / 输出尾部，保留第一现场），复盘不必再按 mtime 反查测试报告归档；④ **预检与记账**——`check` 增加 changelog 派生预演（只算不写，prepare 的文档手术问题在动文件前暴露）；publish 的提交/合并/tag/推送分段入账，gate 戳增存逐文件代码哈希，指纹不一致时点名「gate 后改动的代码文件」并说明将实跑 P1 verify。回归 9 例（发布工具 5 / 打点矩阵 2 / 无效编号提示 2）。对应台账 rf-844（publish 记账与重跑提示）、rf-845（check 派生预演）、rf-846（bench 顺序）、rf-847（台账失败字段）、rf-848（打点矩阵自证）、rf-849（无效编号提示派生）。

- **`rf-850` 概述行与归档完成标记口径对齐**：「当前迭代」重算的排除集并入「已完成」（原只认 ✅/❌），与 `plan_completed_sections` 的归档判据单源——台账里写「已完成，待发布归档」的任务不再被算作在办；回归 1 例。同时梳理 `plan.md`：已完成项只留状态摘要与归档去向，在办项只留现状与动作/判据，概述行按现存在办节重算。

- **`plan-202` 演示截图生成器入库**：README/手册配图的生成过程从 `docs/tmp/` 的一次性脚本收进仓库——入口 `scripts/make-screenshots.py`（`demo` / `report` / `tui` / `web` 四子命令）+ 实现包 `scripts/_screenshots/`（`demo_workspace.py` / `tui_frame.py` / `web_shot.py` + `cdp_shot.mjs`）。演示工作区两账户 6 只公开品种 + 明显占位凭据，配置用绝对路径、上屏路径由渲染端抹掉演示目录前缀，真实 `data/` 零接触；TUI 取帧走生产渲染函数（非真实 TTY，文本与配色同源），超宽行折行时在续行重新打开配色；Web 档按「导航 → 文本替换 → 滚动 → 截视口」取图（固定侧栏不丢），浏览器从 `--chrome` / `CHROME_BIN` / Playwright 缓存 / 系统路径依次解析。16 例回归覆盖演示持仓与配置口径、报告命令装配、折行保色与路径瘦身、渲染尺寸、浏览器解析次序、入口分发；`scripts-reference.md` / `developer-guide.md` 按域索引 / `folders.md` 目录树同步登记。

- **`plan-201` 事实校验评估函数参数收敛（`rf-839` 技术债）**：`llm/fact_checker/_numerical.py::_evaluate_percent_value` 的 22 个参数（7 基础值 + 10 语境开关 + 5 数据映射）收进冻结 dataclass `PercentContext`——字段即语义，新增一种语境只需加字段并在调用点赋值，不必再改签名/文档/全部直接用例；函数签名收敛为 `_evaluate_percent(ctx)`，语境判定优先级（非收益率早退 → 回撤 → 收益语境）仍在函数体内单源维持。行为零变化：`src/test/unit/llm` 1326 例全绿（含 rf-836 的 6 例回归）。

- **`plan-200` 配置体系重构第 15 轮：稳态观测与回退演练**（配置重构 15 轮到齐）：新增 `src/test/unit/config/test_config_resilience_contract.py`（10 例，全部 `tmp_path` 隔离）把四类路径变成可复跑断言——① **非法配置不静默**：非法 `schema_version` 返回 None 且日志含文件名 + 键 + 原因；`logger.json` 单键非法只回落该键（其余键按文件生效）；② **删除后重建**：`llm_settings.json` v2 模板、`logger.json` 幂等 `ensure_logger_file`、`llm_pricing_ref.json` 默认模板（23 个模型价）重建后均可加载；③ **缓存首轮重算**：首轮未命中 → 写入 → 次轮命中（目录隔离统一由 conftest 提供）；④ **非当前结构拒绝**：消息含「删除该文件后重新生成」。实测（临时目录）：非法配置 0.1ms 内检出并拒绝、三份重建即用、无静默降级。观测项复用现有日志与 `perf_history`，未新增面板。

- **`rf-843` Web 配置面板块标题显示内部 id + 调优块渲染报错**：块标题曾用 `labels[blockKey]` 取，而 `labels` 只登记可编辑键，`sections` / `llm` / `standalone_*` 等块直接显示英文 id；重拍截图时又发现 `renderTuningGroup` 与块标题取源不一致（引用未定义 `surface`），整个配置面板渲染失败。修复：新增 `block_titles` 随面下发（单一来源，11 个块 id 全覆盖），前端一律取服务端下发的标题（不回退到块 id、不写死中文）；`renderAnonGroup` / `renderTuningGroup` 改为接收 `surface`；契约测试补「每块都有中文标题且标题≠块 id」两例。

## [0.15.2] - 2026-10-24

- **`plan-210` 新闻去重快速上界**：`_dedup_by_title` 先用 `SequenceMatcher.quick_ratio` 判断候选门槛，低于门槛不做完整双向 ratio；合并判定不变，新闻 TTL 仍保持 900s（不为提速放宽时效）。

- **`plan-211` 数据源状态接入报告矩阵**：行业资金流向失败经 `mark_data_unavailable` 写入 DegradationTracker，数据源可用性矩阵可见；provider 暴露公开失败状态访问器，`fetcher`/`cache` 不再读取私有 `_SECTOR_FLOW_FAILURE`/`_DIVIDEND_FAILURE`。


- **`plan-211` 数据源路由与降级状态**：hithink 不再把场内 ETF 送入 A 股价格/历史槽，并归一 A 股错误交易所后缀；行业资金流向失败类型写回模块状态（连接失败/暂无数据），缓存提示可区分。

- **`plan-211` 首片：K 线风控页日志降噪**：腾讯/新浪逐代码「返回非 JSON」从 WARNING 降为 DEBUG；源失败仍计入 registry，熔断汇总保持 WARNING。

- **`rf-865` 持仓集中度 Excel 恒占位修复**：`excel_module_loader` 补注册 `compute_concentration`，Excel 与 HTML 同源；新增装配键/可调用回归。
- **`rf-866` 自检截断语义修复**：`max_tokens_self_review` 默认 2048→3072；首次截断记 WARNING，自动放大后仍截断才记 ERROR，重试成功不再污染 `errors`。

- **`plan-208` 跨模块导入面收窄完成**：`config/cache/cli/providers` 公共面移除私有 `__all__`；兼容转发注释清零；生产代码跨包私有导入清零；`code_utils`/`doctor`/`cache.operations` 等转发按 owner 收口；`providers/_utils.py`→`providers/utils.py`、`analysis/_prosperity_inputs.py`→`analysis/prosperity_inputs.py`；测试 patch 点对齐 owner；新增观察期 `scripts/check-import-surface.py`（compat-comment / private-all / cross-private / dynamic-target）与 owner 表（`technical.md` §9）。

- **`plan-209` TUI 显示模式统一（完成）**：状态标签收敛到 `switch_panel.status_text`（关闭恒红，父项关闭的子项不再退化为无色）；`truncate_display` 改为 ANSI 感知并补 `RESET`，修复窄档蓝色分组标题颜色泄漏；`DESIGN-TUI.md` 新增「Display Modes」契约；立项设计见 `docs/plan/tui-display-modes.md`。

- **`rf-863` 发布流程写前校验与失败回滚**：`apply_changelog_release` 现在在纯文本阶段校验「最近发布」指针行与归档索引行的目标路径（跨小版本目录缺 `v` 等错误在 `check` 预演即中止），并把索引行目录一并归一；`prepare` 在预检干净树的前提下，写盘后任一步失败自动 `git reset --hard HEAD` 回滚（未跟踪文件只提示不删除），不再留半途状态。

## [0.15.3] - 2026-10-24

- **发布刷新稳定性修复**：全局测试 fixture 隔离 `llm.pricing` 模块状态，避免临时定价配置泄漏到后续用例（修复 `test_peak_periods_defaults` 并行偶发失败）；`refresh` 失败台账在 stdout 只有摘要时回读归档 `*_debug.log`，保留失败用例名与首因。

## [0.15.4] - 2026-10-24

- **持仓变动提示词去计数漂移**：复盘窗口行不再输出「原始快照文件数」（每跑一次报告 +1），改按日去重口径；指纹审计组件改为与生产同口径的渲染文本/风险信号子集，消除虚报的组件变化。

- **数据质量块误报修复**：成功取用事件不再按 `failure_type` 计入「连接失败」，质量块只统计失败事件；此前正常取数会被写成「连接失败 N 次」，并使缓存冷热不同的两次报告产出不同文本。

- **报告级 LLM 缓存状态隔离**：新增报告运行边界（清本轮降级事件、重置自检载体、取 LLM 用量基线），`perf` 的 token/调用数改为按报告 delta 记账，TUI 会话累计不变。
- **指纹组件审计**：新增组件级哈希与变化定位，DEBUG 下自动记录「相对上次报告哪些组件变了」，用于定位缓存未命中来源。

- **LLM 默认值对齐本地偏好**：`self_review` 默认开启；`reasoning_effort` 默认值调整为 global_macro/health_check/news_correlation/penetration_deep=`low`、expert_review=`medium`。生成模板、用户手册与需求默认值描述同步。

- **东方财富 push2 告警降噪**：单代码失败日志 DEBUG，批量失败按源聚合一条 WARNING；registry 熔断汇总保留，减少行业接口断连时的 per-code 噪声。
- **事件窗取数复用**：`build_event_rows` 对同批 bars/index 做局部 memo；基金基准文本同批去重，避免重复链路取数。

- **报告收尾远程/无图形会话指引**：远程 SSH、手机远端或无 GUI 环境不再询问 `y/N` 并调用无效的服务器文件管理器；直接打印产物路径并提示 Web 下载或 `scp`/`sftp` 获取。本地桌面仍保留单键打开。

- **交付文档与本地配置**：仓库内 `CLAUDE.md` 固定交互纪律（与全局 `AGENTS.md` 同源）；本地 `llm_settings.json` 恢复被误覆盖的模块启用状态（`global_macro`/`expert_review`/`health_check`/`penetration_deep`/`self_review`/`holding_change` 开启，`news_correlation` 保持关闭）。

## [0.15.5] - 2026-10-25

- **缓存节省费用可见**：命中模块的 token/费用都是 0，报告里原本只看得到「无新增调用」，看不到省了多少钱。现在按历史逐模块付费均价估算 `cache_saved_cost` 写入 perf，并打一条「[LLM 缓存] 命中 N 个模块，估算节省 ≈¥X」日志；无付费样本的模块不参与估算（不虚报）。

- **截断 gzip 缓存不再抛异常**：半写的 `.json.gz`（磁盘满/进程被杀）此前会让 `cache.get` 抛 `EOFError` 直冲调用方；现按「损坏即未命中」清理重取。

- **报告收尾本机打开判定收紧**（rf-873）：手机/远端跑完报告仍弹「是否打开报告」(y/N)，按 `y` 只能拿到「打开失败」再跳回主菜单——因为 `DISPLAY` 是建立会话时的残留/桥接环境变量（tmux/screen、Catlink、Xpra），桌面其实在客户端。现在除 SSH/mosh 外，Linux 上还要求对应 X socket 真实存在、`xdg-open` 可执行，且桥接会话一律按无图形处理；`xdg-open` 自身报错不写回终端（只记日志）；打开失败一次后本会话直接打印产物路径与 Web/scp 指引。

- **LLM 预检缓存键与写侧同源**（plan-216）：多链模式下预检键滞后 provider 后缀，导致每份报告四模块全判 miss、全量派发进线程池（真实命中在 skeleton 的第二次预检），`cache_misses` 恒为 4。现在两侧共用 `_build_provider_cache_key` 构造完整键；不链式配置不加后缀，旧缓存不整体失效。

- **数据质量文本去计数漂移**（plan-218）：【数据质量详细状态】与【数据质量降级】段不再写失败出现次数/跨会话累计次数，改去重后按源列出——次数由重试轮次与网络抖动决定、每轮都变，会把 `health_check` / `expert_review` 的缓存键无谓翻新；模型要判断的只是「哪些源本次不可用」。同时修正指纹审计基线被报告边界误清的问题（审计恢复输出「相对上次报告哪些组件变了」），预检新增一行「命中 N/M；未命中：…；重新生成跳过：…」概况日志。

- **历史取数单轮复用与空结果短路**（plan-217）：同一份报告内多个消费方按不同窗口重复取同一代码的历史（实测单轮 110 次尝试、99 次空），现在按（chain, code）复用本轮已取到的最大窗口，并让同一 provider 连续 5 次空结果后在本轮直接跳过（结构性不覆盖与网络故障区分，不计熔断）。
- **LLM 缓存未命中可归因**：`cache.get` 未命中不再静默——「无此缓存文件」与「已过期（含 age/max）」各自打一条 **INFO**（每进程每 key 首见一次）；预检遇不可缓存（重新生成/强制刷新范围）也打 INFO「跳过缓存读」。此前两种原因在默认日志级别下完全不可见，用户只能看到「又调了一遍 LLM」，分不清是缓存被清、TTL 到期还是自己选了重新生成。

- **指纹变化归因日志恒开**：预检侧每次报告打一行 INFO「指纹组件变化（相对上次报告）」，默认日志级别即可定位 LLM 缓存未命中来源（此前只在 DEBUG 下记录，远程/默认配置实测拿不到）；报告收尾遇远程/桥接会话时也落一条 INFO，便于事后核对收尾行为。

- **发布流程三项改进**：`publish --title` 自带的裸版本前缀（`vX.Y.Z —— `）自动剥离，不再拼出重复版本号；`devbump` 补分步耗时埋点（版本改写/一致性收敛/切版提交/推送/闭环校验）；`devbump` 收尾新增**发布闭环校验**（tag 在 master 历史内、master 为发布版、本分支为下一开发版，不符硬失败）。

## [0.15.6] - 2026-10-25

- **缓存 TTL 收敛为「默认 + 稀疏覆盖」两层**：生成的 `config.json` 里 `cache_ttl` 改为空对象（默认值唯一来源 = 缓存注册表），只有用户显式加键才构成覆盖、删键即回默认——消除「改默认值后配置副本继续生效」的漂移；`cache_ttl` 中未注册的键（如已删除模块的 `fund_overlap`）改为告警。

- **配置文件 TTL 段清空**：`data/config/config.json` 中等于注册表默认值的 37 个 `cache_ttl` 键已移除（值本无差异，行为不变），配置文件与「稀疏覆盖」口径一致；需要调优时再添加单个键即可。

- **移除按 key 的 TTL 抖动**：TTL 与缓存键无关后，读侧与清理侧天然同值。此前抖动只在「传了 key 的读点」生效，LLM 读侧全都不传 → 约一半 LLM 缓存会被清理侧最多提前 15% 删除（4h TTL 下最多 36 分钟）。另把 `bond_yield` / `fund_manager` 的同值重复常量改为直读注册表，`index`/`index_valuation` 的宽松常量补注为「陈旧兜底读，刻意不用新鲜期 TTL」。

- **清理侧精确键映射修复**：`cleanup_expired` 按剥离版本戳后的**逻辑键**查类型（此前带 `_v{N}` 查精确键表必 miss，退化为前缀/日级兜底）。

- **缓存 TTL 取消读侧独立配置**：`get_cache_ttl_llm` 不再维护「模块 → 缓存键」映射表与回退默认值字典，改为「模块键 → `llm_<模块>` → 直读 `cache.get_ttl`」——读侧、启动清理、统计、配置模板同源于 `data_registry`，运行时只剩 `config.json` 一层覆盖；未登记模块打 WARNING 并按日级兜底（不再静默借用 `global_macro` 的 24h）。

- **新闻关联分析缓存 TTL 调至 4h**：`llm_news_correlation`（逐条缓存，键含标题前 80 字 + 持仓指纹）由 1h 改为 4h；同一批新闻在同一天内的关联判定不再按小时重算。代码默认值、缓存注册表、生成配置的模板与文档同步。

- **三个分析模块缓存 TTL 统一为 4h**：`expert_review`（2h→4h）、`health_check`（24h→4h）、`penetration_deep`（24h→4h）。取数侧默认值、缓存注册表（清理/配置派生同源）、生成配置的模板与文档全部同步；4h 在「日内变化要看得到」与「每次重算都是钱」之间取平衡，仍可在 `config.json → cache_ttl` 逐项覆盖。

- **新闻去重提速（判定不变）**：比较串与字符多重集按标题缓存，并先用「字符多重集上界」跳过不可能命中的标题对（不再为每个远低门槛的对构造两个 `SequenceMatcher`）；等价性由「换回旧实现跑同一语料、保留集合逐条一致」的回归锁定。

- **财报章节探测负缓存**：带 section 的探测遇 404 后记 12h 负缓存（`datasink_probe_miss_*`），同一天的后续报告不再逐章节重发请求（7 只标的 × 多候选章节的 404 曾占十余秒）；文档级 404 仍按告警处理、不进负缓存。

- **缓存 TTL 读侧与清理侧对齐**：`self_review` / `holding_change` 的读侧 TTL 此前未登记映射、静默回落到 `llm_global_macro`（24h），而缓存清理按注册表 7200s 判定——2h 后启动清理把读侧仍认为有效的文件删掉，下一份报告白重算一次自检/归因。现两侧统一为 24h（内容寻址：键含上游正文，输入未变即命中），并由逐模块校验用例锁死「读侧 TTL == 注册表 TTL」。

- **财报正文缺失不再每份报告重走链路**：某标的在章节阶 + 备源两阶都取不到正文时，按标的记 6h 负缓存（`report_symbol_miss_*`），同一天的后续报告直接复用同一原因、跳过索引与候选探测（此前 5 只标的约占 3s/份报告）；索引为空/网络失败不入缓存。

- **行业资金流向失败负缓存**：源不可达/返回空后本会话 5 分钟内不再重试（akshare 内部本已重试 2 次），后续报告直接按「不可用」降级，失败原因仍如实上报、不复用过期成功数据。

## [0.15.7] - 2026-10-25

- **检查命令输出归位**：`check-sources` 的排版与退出码处置从 `core/check_sources.py` 移入 CLI 层（core 只返回文本 + 退出码），core 层不再直接 `print`/`sys.exit`。

- **架构约束整改（重试/节流原语、Provider Chain 边界、代码判定中心化）**：① LLM 全链失败重试改走 `core.retry.retry_transient`（不再分支内 `time.sleep` 自建重试）；② 新增 `core.throttle.wait_interval` 作为「429/限速窗口一次性等待」唯一原语，cninfo/datasink 的 `interval_delay + sleep` 改经该原语；③ 行业资金流向失败状态访问器下沉 `fetcher/akshare.py`，report/cache 层不再直连 `providers`；④ A 股指数交易所判定收敛为 `code_symbols.index_exchange_of`，同花顺 provider 内自建的 399/932 判定删除。

- **删除旧结构与旧接口的兼容层**（不保留向后兼容）：① `get_ttl` 去掉历史 `key` 参数（30 处调用点同步）；② 删除历史序列的「载荷语义版本戳」闸门（`_payload_ver` / `write_stale_with_version` / `payload_version_current`）；③ **缓存键版本 `v3`→`v4`**，整体作废旧缓存，替代逐载荷 `rank_schema`/`hold_schema`/`purchase_schema`/`fee_schema` 字段与 `rank_payload_is_current` 判据（排名/持仓归一化不再盖版本字段）；申购/费率的读侧**形状**准准入（防截断载荷）保留；④ 功能开关注册表旧名别名 `GROUP_ANALYSIS` 统一为 `GROUP_FUND_STYLE`；⑤ 删除 `fetcher/batch` 对旧 registry 对象的 duck-typing 守卫；⑥ 清理 `code_symbols`/`datasink` 注释中「`code_utils` 仍转出派生符号」的过期兼容声明。

- **新闻去重比较成本下降**（rf-872）：比较串与字符多重集按标题缓存，并先用字符多重集上界跳过不可能命中的标题对（不再为每个远低门槛的对构造两个 `SequenceMatcher`）；判定结果不变，基准语料约 1.17×。

- **行业资金流向降级收敛**（rf-871）：失败后 5 分钟内不再重试（akshare 内部本已重试 2 次），后续报告直接按「不可用」降级并只留一条告警；备用源评估结论为「免 key 场景无可靠第二源」，故保留显式不可用、不引入过期缓存。

- **事实校验口径**（plan-185）：口径标签与提示词版本号已生效，最近多轮 `fact_fix_total` 稳定为 1（目标 ≤3），收益率指标口径错挂问题收敛。

- **报告内容可复现**：历史走势的并发取数改为「并发抓、按输入持仓顺序汇总」。此前按 `as_completed` 完成顺序追加，导致同数据两次报告的「已纳入走势计算」清单顺序抖动、逐日市值浮点累加顺序漂移（极端时影响四舍五入后的展示值）。

## [0.15.8] - 2026-10-25

- **观测绑定时机与计数口径修正**：观测汇聚器原在「LLM+新闻」阶段内、预检**之后**才绑定，导致每次进程重启后首份报告的 `cache_hits` / `cache_misses` / `recompute_reasons` 整体缺失——而首跑恰是最贵一份（实测 ¥0.108 占三份合计 88%），缺它会让 TTL 决策统计系统性偏差。现绑定前移至该阶段开始前。同时骨架路径（`self_review` / `holding_change` 等）的命中/未命中计入同一汇聚器：此前「基础模块命中 4/4」实为 6/6 全命中，命中率被低估；预检摘要行文案改为「基础模块命中 N/M」以区分口径（该行不代表本次无 LLM 调用）。
- **重算归因覆盖骨架路径（补 plan-227 观测完整性）**：`self_review` 等「缓存键在上游产出后才确定」的模块走骨架生成（`skeleton.generate_llm_content`），此前不参与重算归因——而它每次重算且费用占比可达三成，会让 `ttl_expired` 占比统计系统性低估。现骨架路径同样记录原因，并按「本轮键与上一轮是否相同」细分 `ttl_expired`（内容没变、纯到点）/ `fingerprint_changed`（内容寻址换键）；无上轮记录时如实记 `cache_miss`，不臆断。上一轮键随报告边界复位（跨报告比对才成立）。命中时不写归因，防命中/重算统计互相污染。
- **Web 成本预检弹层修复**：多币种改造后前端仍在读已移除的 `forecast.low/high/symbol` 与 `budget.spent/limit`，`undefined.toFixed()` 抛 `TypeError`——表现为点「生成」后弹层不出现、按钮无反应（无日志无提示）。现前端只消费后端格式化好的展示串（`cost_display` / `forced_cost_display` / `display`），新增契约测试静态扫描 JS，禁止回读已移除字段。
- **日预算状态收敛为真实消费面**：`budget_status()` 由 8 键收敛为 `{enabled, exceeded, display}`（三渠道读 `exceeded` 作硬闸、前端读 `display` 整行直出）；金额明细并入摘要，不再单列 `currency`/`symbol`/`limit`/`spent`/`spent_converted`/`unconvertible` 等无人消费字段。
- **文档 TTL 表核对纳入守护**：`check-doc-drift` 新增第 22 项——`technical.md` 缓存各表与 `how-to-config.md`「cache_ttl 可调参数」逐类型对账缓存注册表，改默认值漏同步即拦截（表内新增类型自动纳入）。
- **决策/信号账本按龄保留（plan-228）**：`core/jsonl_store` 新增 `prune_jsonl_by_age`（按龄裁剪 + `keep` 谓词），决策账本与信号账本追加后按 **730 天** 裁剪；决策账本的**已结算事件永久保留**（跨期反思样本）。不使用行数上限——账本一行一份状态，按行数截断会连最旧已结算样本一起裁掉。坏行不裁（不替读取侧吞掉损坏证据），缺日期的行保留。
- **LLM 缓存重算归因观测（plan-227）**：缓存未命中时记录原因——`forced`（重新生成/缓存关闭）/ `fingerprint_changed`（内容变了）/ `ttl_expired`（内容没变、纯到点），按次数聚合进 perf 的 `llm.recompute_reasons` 并在预检摘要行显示分布。观测为纯旁路（命中判定/调用次数/费用不变），用于回答「4h TTL 是否把内容未变的调用也重算了」——这是决定能否放宽到 8~12h 的唯一依据（**观察期任务，结论待约一周数据**，见 plan-227）。`news_correlation` 维持 ≤4h。
- **财报类缓存节奏对齐披露周期（plan-226）**：`report`（财报索引/章节清单）与 `fin_indicator`（财务指标）TTL 30 天 → **1 天**，`dividend` 30 天 → **7 天**；`report_doc`（正文）保持 30 天。两类 symbol 级键过去在新一期财报披露后可能整月沿用上一期口径（定时运行无手动刷新兜底）。配额影响有界：每标的每天至多 1 次索引请求（20 标的 ≈ 免费档日配额 0.24%），且报告次数不放大。
- **缓存畸形载荷不再抛异常**：`cache.get` 读到顶层非对象（如文件被写成 `[]`）时此前按 `data.get("_ts")` 判定会抛 `AttributeError` 中断报告链路；现按损坏处理——告警、删除该文件、按未命中返回（缓存契约是「坏了就当没缓存」）。
- **缓存 TTL 机制收敛（plan-225）**：盘中敏感性改为注册表数据属性 `DataModuleDef.market_ttl`（`price`/`index` = 30s），`config.market_hour_aware` 退役（写入时校验告警并忽略），配置只保留 `market_hour_ttl` 数值覆盖；`get_ttl` 在"盘中覆盖与 `cache_ttl` 冲突"时打一次性 INFO，把静默失效变可见。两个缺失探测负缓存（`datasink_probe_miss` 12h / `report_symbol_miss` 6h）登记为正式缓存类型，读侧 TTL 与 `cleanup_expired` 判定同源。契约测试覆盖：盘中 30s/盘后静态 TTL 双向、盘后不白打上游、退役键无扩权、负缓存按 6h/12h 清理、全量类型 TTL 为正；另补六份缓存契约测试——TTL 业务矩阵（时段 × 类型 × 覆盖层、读写清理同源、同日两次报告/收盘后/LLM 边界）、价格缓存新鲜度门禁（盘中价不得当收盘价、QDII T-1）、版本戳迁移与逐类型清理、**缓存引擎契约**（往返类型保真/100KB 压缩阈值两侧/损坏 gzip 与畸形载荷恢复/命中率统计/分组前缀清除/preload 与 refresh 组互不波及/并发读写不出现半写）、**报告级缓存隔离**（报告用量增量不吞上一份、试算与正式输入域隔离、强制重生成范围、内存复位后磁盘仍可命中、盘中→盘后 TTL 跃变）、**LLM 缓存 TTL × 指纹矩阵**（7 模块 × 默认/覆盖/非法覆盖 × 未过期+指纹变/过期+指纹未变四象限）、**指纹同源与失效最小化**（预检侧与写侧同一函数、成本/风险信号变化必换键、行情价与涨跌幅等抗噪字段不换键、空块不追加 part、与生成无关的开关不进后缀、组件级归因只报真实变化）、**缓存 × 降级/熔断交互**（快照类全链路失败用过期缓存兜底、历史序列不把陈旧曲线当最新、失败结果不写缓存、代码级空结果不计入熔断、熔断中的源不再被调用、形状准入拒绝畸形载荷、同轮窗口复用不重复打源）、**端到端报告序列命中矩阵**（真实 `generate_all_llm` + 仅 mock 网络层：指数/成本/风险信号/降级源/指标/穿透资产/分类/温度/模型覆写 × 命中模块粒度、全量与模块级强制、命中运行的 LLM 调用次数少于未命中、预检归因日志）。
- **缓存过期时间（TTL）专项核查与立项**：盘点 37 个缓存类型与 10 处保留/陈旧窗口后立项 `plan-225`（TTL 机制收敛：注册两处未注册负缓存类型、校验 `market_hour_aware`、让 `cache_ttl` 盘中失效可观测）、`plan-226`（财报索引 30d→1d、财务指标 30d→1d、分红 30d→7d，配额测算 +10~20 请求/日）、`plan-227`（先观测 LLM 模块"重算原因"再决定 4h 是否放宽）、`plan-228`（决策/信号账本加保留上限）。核查中撤回两项原拟议：`sentiment` 含盘中实时更新的连板梯队，1h TTL 属盘中时效设计；两个负缓存只在**确定性** 404（已发布静态文档、章节与备源均无正文）时写入，瞬时网络错误不会污染当日结果——两条均无需调整。
- **模型定价表按官方价目刷新（2026-10-25 核验）**：补入现役型号——Claude `5.5` 家族（Fable 5.1 / Opus 5.5 / Sonnet 5.5 / Haiku 5.5）与 legacy Sonnet 5；OpenAI `gpt-6.1-sol` / `gpt-6-luna` / `gpt-6-astra` / `gpt-5.6-sol`；Gemini `3.8-flash` / `3.1-pro`；Kimi `k3.1-pro` / `k3.1-pro-highspeed`。移除已下线或不在官方价目表的 `gemini-2.0-flash` / `gemini-3.5-flash`。DeepSeek 单价经核验未变。
- **费用展示改为按模型原生币种**：`MODEL_PRICING` 每条带 `currency`（Anthropic/OpenAI/Google 为 USD，DeepSeek/Kimi 为 CNY），`estimate_cost` 出对应符号（`$`/`¥`），代码内**不再有任何用于展示的汇率折算**。模型同时提供多币种价时以配置币种（`llm_pricing_ref.json → currency`，默认 CNY）为主，用条目 `alt` 子表提供该币种价即可切换。
- **跨币种金额分组并列、永不相加**：会话累计与报告合计改用「币种 → 金额」桶（`llm.pricing.add_cost/merge_costs/format_costs`），显示形如 `¥0.0123 + $0.0045`；`session_usage` 的 `total_cost`/`currency` 字段由 `costs` 取代，perf 记录写 `cost_by_currency`。
- **币种配置收敛为一处开关**：`llm_pricing_ref.json → currency`（默认 CNY）只回答「模型提供多币种价时选哪套」与「日预算以哪个币种判定」，不再充当条目缺省币种——`MODEL_PRICING` 每条显式声明 `currency`（含 DeepSeek/Kimi 的 CNY），条目缺 `currency` 时回落常量缺省。此前把配置改成 `USD` 会让人民币标价的模型显示成 `$`，现已被结构排除；顶层 `currency` 非法取值告警并回退默认。
- **日预算回到单值**：`daily_cost_limit` 为**本地主币种金额**（默认 `0` 不启用）；判定超限时按内部汇率表 `FX_TO_CNY` 把各币种支出折算到本币（**仅用于判定，不影响展示金额**）；缺内部汇率的币种列入 `unconvertible` 并在摘要点名 + 告警，不静默按 0 计。
- **历史费用摘要按币种分组**：`perf.module_cost_summary` 返回 `{模块: {runs, costs: {币种: {total, avg}}}}`；`[S]` 面板行尾摘要、缓存节省估算与事前预估都按币种分组，跨币种样本不混算。
- **发布台账不再折算金额**：`logs/release.jsonl` 的 `session_usage` 去掉 `cost` 字段，终端尾行只报 token 数（in/out/cache r/w）与执行环境（provider/model/thinking）。原因：金额只能来自 pi 的逐模型单价表，而订阅制/转发端点（如 opencode）的单价并非实际账单口径，折算出来的「费用」既不可核对也容易被当成账单。
