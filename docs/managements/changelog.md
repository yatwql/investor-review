# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.10]**（2026-10-20）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.11-dev] - 开发中（未发布）

### Added

- `developer-guide.md` 新增「文档核对方法」段：核查按机械层/结构层/断言层/散文层四层分工，给出未绑定断言的抽取对码写法、散文层「反引号标识符 ↔ 代码符号索引」与豁免域、以及「同类漂移出现第二次即落成 `check-doc-drift` 子分支（挂现有编号不加项数）」与「台账唯一、`docs/tmp/` 底稿闭环即删」两条输出纪律（自审 rf-786）
- `check-doc-drift` 第 1 项扩「可见性规则总览表 `type` 行 ↔ 注册表 `type` 集合」双向对账（缺行 / 多行 / 重复三型）：该表此前仅人工维护，注册表把财报两章合为 `fundamental_snapshot` 并新增 `schedule_replay` 后，表里仍写两个不存在的 type 且漏一行——行数恰好相等，任何计数断言都不露馅（自审 rf-777）

- 发布链耗时埋点：新增 `scripts/_release/_timing.py`（分步计时 + JSON 记录），`release.py` 每命令尾行打印耗时摘要并追加 `logs/release.jsonl`（`command` / `ok` / `elapsed_s` / `version` / `steps[]`）——gate 的回归/十守护/设计护栏、refresh 的 bench/collect/sync、publish 的 P1 verify、evolution 的快照与统计同步均记为分步；`logs/` 为 git 忽略域，写入失败只打 `[!]` 且不改退出码（自审 rf-771）
- `release.py refresh` 新增 `--full-bench`：bench 默认只测发布口径四档 `unit` / `dev-verify` / `regression` / `integration`（未测模式按 `--update-docs` 既有口径保留上次实测，不写脏），全量十四档降为显式入口（自审 rf-772）

- `check-doc-drift` 新增第二十项检查「迁档占位↔归档节」：review-findings 每个「已随 vX.Y.Z 发布迁入」占位，对应 `archived_review-findings.{X.Y}.x.md` 必须存在含该版本号的二级标题归档节——占位已写、归档正文缺失（发布归档迁移只删不写）即当场报出；doc-drift 项目清单五处文档同步（自审 rf-756）
- `check-doc-drift` 新增第二十一项「树描述计数禁令」：folders.md 目录树描述禁写「阿拉伯数字+量词」的易漂移计数（开关项数/菜单项数/文件数类，与「测试真值单一来源」同源纪律）；docs/archive 记录域豁免、中文数词设计常量不入检；现存 6 处 src 域违规改定性措辞（自审 rf-757）
- `check-code-traces` 新增「日志统一」AST 级守卫（`_traces_code/logging_discipline.py`）：生产层 `print()` 白名单制——豁免域为 `tui/`、`cli/` 整目录（终端交互即其输出本体）与进度反馈 / 一次性终端检查报告 / 首启向导六个模块，白名单外调用即报 LOG 并返回退出码 2；developer-guide 退出码表与三家 AST 守卫说明同步，technical.md 日志统一约束登记机检载体；用例覆盖检出（函数体内嵌套/多行/报告层）、豁免（目录/文件）、不误伤（`sys.stdout.write`/`obj.print()`/字符串字面量/测试层/非 py）、语法错误容错与白名单完整性（条目存在 + 现存 print 全部落在豁免域）

### Changed

- 检查脚本词表收敛为单一来源：31 条逐字节相同的「历史变更叙述」正则从两脚本模式表抽入 `scripts/_traces_common.py`（只登记字面量，分类/描述仍按域定义，`_multi_domain()` 支持同正则多域登记）；文档域模式表整体迁入 `_traces_doc/patterns.py`（`check-doc-traces.py` 981→708 行，保留原面 re-export 故调用方零改动）；`RULE_CARRIER_DIRS` 扩至 `_traces_doc` + 新增 `RULE_CARRIER_FILES`（词表/模式表属尺子本身，不被 code-traces 自查误报），结论缓存 `_LOGIC_FILES` 纳入两新文件防止判定面搬家后缓存假绿；新增 `test_trace_shared_vocabulary` 锁「两表交集==共享词表 / 两侧都引用每一条 / 源码内无写死字面量」，设计说明见 `docs/plan/trace-vocabulary-single-source.md`（自审 rf-791）

- `logs/release.jsonl` 耗时台账改走 `core/jsonl_store` 原子追加原语并加保留上限（原为直接 append 写且无界增长；一次发布约 7 条，上限 500 条覆盖数十次发布）（自审 rf-788）
- `check-doc-drift` 第 18 项扩「正文菜单键引用」分支：正文「菜单 `X`」须为主菜单键（`MENU_ITEMS` ∪ 返回键 `0`），`[D]` 二级选项（C/F/O/M）改由 `tui/handlers_config.py::CONFIG_DIR_INFO_KEYS` 单一登记、正文须写作「菜单 `D` → `C`」；裸键形态要求后接空白/标点，避免「主菜单 code block」里的英文词首字母误报（历史漂移：code block 校验护不住正文，`[4]`→`[3]` 与 `[D]` 二级化后十余处正文失效）（自审 rf-776）
- 缓存分组术语统一为「行情类缓存」：TUI 上屏词与 `handlers_cache`/`cache/operations` docstring 对齐菜单标签，手册与需求菜单表同步（`--update position` 选项名作为历史命名在图注说明）（自审 rf-780）
- `check-doc-drift` 分区纪律检查新增第 D 条「节归属」：「开发期已修复」节只允许出现在已解决区、P 档标题只允许出现在待处理区——原第 A 条按 rf 标识比对，标题（节）错位时完全静默（rf-765 即由此产生）（自审 rf-765）

- `release.py gate` 新增演进对照新鲜度断言（P2 前置）：「当前开发版」列头「本次重跑时的工作区」日期须为当日——evolution 为发布链人工步骤，跳过即以过期快照发布的缺口由此闭合（表头与数据行同命令原子刷新，日期一致即数据行同步）；发布编排描述三处文档同步（自审 rf-758）
- `check-doc-traces` 围栏内 folders.md 目录树行照检（围栏代码块跳过仅针对非树行内容——目录树整块位于围栏内，原跳过逻辑使「树行照检」规则从未生效）；树行按路径分域（docs/archive/ 子树=归档记录域仅复盘叙事检出、docs/plan/ 子树=任务记录域照检章节+约束代号）；树行专属无后缀来源叙述补强（「从 framework 拆出」类带后缀模式覆盖不到）；folders.md 现存 14 处违规描述改语义化；developer-guide 树行纪律描述同步（自审 rf-760）
- 交易所代码前缀改为 `code_utils` 单点定义：新增 `EXCHANGE_PREFIXES` 常量与公开 `strip_exchange_prefix()`（只剥前缀、不校验码位，供 5/6 位形态自判等场景复用），`_strip_prefix` / `to_fmp_symbol` / `holding_status.classify_code_format` 三处自建前缀表或元组字面量收编复用；`to_fmp_symbol` 带前缀输入的透传分支此前因大小写不匹配而不可达，随常量复用一并修正；反向机检由单测钉住「前缀元组唯一定义点」（自审 rf-763）
- folders.md 归档子树版本目录块重排为版本升序（0.9.x 后原接 0.13→0.12→0.11→0.10 倒序——归档落盘三次均插入同一锚点且 `check_dir_tree` 仅集合双向比对、顺序零机检）；`check-doc-drift` 目录树检查新增「版本目录块升序」断言（自审 rf-761）
- developer-guide「check-doc-drift」项清单补齐至 21 项（16 项陈旧：17~21 五项缺列）并改与脚本 docstring 同源措辞；technical.md 约束外参照句「十项逐条对账」改「逐项对账」（自审 rf-762）
- 架构设计约束（代码类型判定/缓存/原子写入/HTTP 工厂/日志统一/开关注册表等全部编号约束）与设计契约（DESIGN.md / DESIGN-TUI.md）全量审计：机械扫描 + 逐约束对照适用范围裁决——无直连 `requests`（统一 httpx 工厂）、报告层无 `call_llm` 直调、开关单源派生、DESIGN.md 护栏 E 级通过且 W 基线（字号 8/间距 172/W1 白名单 15）与契约声明一致、DESIGN-TUI 无 hex 字面量与 GitHub 系色残留；登记 rf-763（holding_status 自建 sh/sz/bj 前缀元组，判定中心化约束违反）/ rf-764（whatif_writer HTML 直写未复用原子写原语）与日志统一约束无机检守护（该缺口已由同期新增的日志统一支路闭合）（自审 rf-763/rf-764）

### Fixed

- `test-coverage.md` 覆盖项数按收集快照回写（8 例差：dev-verify 7394→7402 / unit 10797→10805 / 总收集 11139→11147 / unit_scripts 1226→1234）；git pre-commit 在暂存含 `src/test/` 时对 `check-doc-drift` 追加 `--with-test-count`，测试变更未刷计数在提交期即拦（此前只由 CI master 档兜底）（自审 rf-787）
- `[D]` 查看配置与目录信息 面板二级键收敛为单一登记表 `DIR_INFO_ITEMS`（键 → 显示名 + 处理器属性名）并派生 `CONFIG_DIR_INFO_KEYS`，消除面板与 doc-drift 校验的两处手工同步；处理器按名分发以保持模块属性打桩有效（自审 rf-789）
- 文档点名的代码符号按现行实现订正：`technical.md` 的报告章节与增强开关分组由已下线的 `GROUP_REPORT` 改为 `GROUP_ANALYSIS` / `GROUP_STANDALONE`，`DESIGN.md` 的样式护栏白名单常量由 `_W1_EXEMPTIONS` 改为 `_RAW_COLOR_EXEMPTIONS`（条目数 15 不变）（自审 rf-785）
- Web「配置编辑」面板分组表述统一为「10 组 = 7 个可编辑面 + 功能开关面作用域四组」，web 手册分组表补「LLM 多链线路 ↔ `[M]`」行（原 9 组漏该组、how-to-start 的 8 组仍按已不存在的「实验性功能/常规开关」二分、testplan 的 8 块同源）（自审 rf-783）
- `requirements.md` 菜单表 P 行「报告章节与增强的 8 项开关」改为 21 项（分析增强 16 + 独立章节与回放 5），与 TUI 手册同口径（自审 rf-784）
- 正文菜单键引用 16 处改正：`[4]`→`[3]`（faq 6 / how-to-config / cli / web-mode 2 / technical / testplan / requirements，区间写作 `[1]~[3]`）、持仓目录·文件名·输出目录三项改「菜单 `D` → `C`/`F`/`O`」、faq 机制与诊断块序号「第 37 项」→ 34（自审 rf-776）
- 报告可见性规则总览表重写：`financial_report`/`financial_indicator` 两行并非 `type`，合并为 `fundamental_snapshot` 一行并补 `schedule_replay` 行（自审 rf-777）
- `how-to-config.md` §O 缓存分组表按 `core/data_registry.py` 补齐：`preload` 组补「生成后自检」「持仓变动复盘归因」，`refresh` 组补「基金申赎费率」「指数估值历史」（自审 rf-778）
- 历史快照保留期 60 天 / 12 个 → 180 天 / 365 个（`reports-instruction.md` 生命周期行、`how-to-use-tui-menu.md` 快照说明、`history_snapshot.py` 参数 docstring 三处与 `constants` 对齐）（自审 rf-779）
- `how-to-config-llm.md` pricing 示例两块补 `holiday_always_idle`、faq `.gitignore` 特例描述补 `llm_providers.json` 与 `data/knowledge/`、`how-to-use-cli-mode.md` 重试语义改按 `_TRANSIENT_RETRY_ATTEMPTS = 1`（同源额外 1 次）+ 落槽说明、`config/features.py` 分组注释「2 项」→「1 项」（自审 rf-781）
- 定价表补模型族前缀兜底价说明（`MODEL_PRICING` 六条前缀供带日期后缀变体计价，表内不单列、不覆盖具体模型价）（自审 rf-782）
- review-findings 分区顺序恢复：三个「开发期已修复」节（0.13.11 / 0.13.10 / 0.13.9）原夹在待处理区 P2 与 P3 之间、0.13.8 占位落在归档索引之后——重排为 待处理（P1→P2→P3）→ 已解决（开发期已修复 0.13.11→0.13.8，再归档档案）；同时去掉 P3 表头与首行间的空行（该表原在渲染上断裂为「空表头 + 裸行」）（自审 rf-765）
- P3 文件膨胀登记表与 `check-file-length.py -v` 真值对齐：登记口径改为逼近红线档（主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000，余量 ≤30%），警告级全集明确指向 `-v` 不逐项登记；表改为逐文件、按距红线余量升序，行数按 `-v` 快照刷新，并补登主程序八文件（rf-773）/ 脚本四文件（rf-774）/ 测试十三文件（rf-775）；原表 10 行中 5 个行数陈旧且声称的「全登记」实际只覆盖 10/58（自审 rf-766）
- `plan-169`（日志统一约束机检守护）补归档：已完成并从 plan.md 移除但 `archived_plan.0.13.x.md` 无该条，编号已消耗却无从追溯（自审 rf-767）
- plan-92 现状句「17 页签」改为 19（与报告章节注册表及 README 对齐）（自审 rf-768）
- testplan §6.4「补充自动化门禁」列表编号重复（`15.` 出现两次，16~18 连带错位）重排为 15~19 连续编号（自审 rf-769）
- llm-technical.md 目录层级修正：附录 A/B/C 原错缩进挂在「13. 集成点」下且缺「附录」父项，改为与章同名同级的「附录」父项 + 回退一级缩进（自审 rf-770）
- 调仓模拟报告 HTML 双产物（最新版 + 归档版）改经 `_write_html_atomic` 原子落盘（tmp + `os.replace` + 中断收口登记），与主报告口径对齐——原直写 `open("w")` 在进程中断时留下半写截断的 HTML；补中断场景与原子原语调用面回归用例（自审 rf-764）

- TestGate 门禁编排用例与演进新鲜度断言隔离：新鲜度直读真实 folders.md + 墙钟，编排用例在不同时区/日期的 CI 上随机红（本地已过零点、CI 仍是前一日 → 先行拦截返回 2，回归/守护一个不跑）；新增 autouse 夹具将新鲜度视为通过（编排用例只验序列），并新增新鲜度失败即中止且不触发子进程的专项用例（自审 rf-759）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.10（2026-10-13 ~ 2026-10-20）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
