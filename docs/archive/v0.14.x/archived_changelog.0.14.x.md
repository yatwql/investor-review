# 变更日志归档 — v0.14.x

> 归档时间：2026-10-22（v0.14.2 发布并入；已并入 3 段：v0.14.0（10-21）、v0.14.1（10-22）、v0.14.2（10-22））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.14.0 ~ v0.14.2（2026-10-21 ~ 2026-10-22）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.14.0] - 2026-10-21

### Changed

- **plan 已完成节归档漏搬（`rf-805`）**：归档清单只认二级标题，台账任务节实际是 `####`（嵌在 `### P1~P4` 下）——发布 prepare 时完成节搬不走、主台账残留 `✅` 项。现支持 2~4 级标题，入档统一降为 `## plan-N … ✅`；归档完成提示去掉「上方」方向词。回归 2 例（`####` 节被识别 / 入档降级）。
- **测试文件切分（`rf-775`）**：13 个逼近红线的测试文件（1017~1175 行）按职责切兄弟分片，原文件保留一组并承载跨组共享夹具（分片按名导入，`# noqa: F401` + 文件级 `# ruff: noqa: F811` 注明夹具按名注入）；切分后单文件 140~715 行、最大分片 876 行，用例数与断言强度不变（逐文件 `--collect-only` 对拍一致）。顺带把 `_DATASET_KEYS` 从测试类属性提到模块级（原被两处跨类引用，切分后成为跨文件共享常量）。

- **降级跟踪器单例缓存缺陷（`rf-804`，切分验证期暴露）**：`report/{fund_performance,penetration_sheet,summary}.py` 曾在导入期 `_tracker = get_tracker()` 缓存实例——`reset_tracker()` 只销毁工厂内当前实例，缓存引用仍指旧对象，测试隔离与运行期重置双双失效；重排执行顺序后 `test_all_funds_fail` 因前序用例累计的降级计数而写出状态脚注。现改为 `_tracker()` 惰性取当前单例，并由 `report/test_data_status.py::TestTrackerNotCachedAtModuleLevel` 2 例守护（全仓禁止模块级缓存 + 重置后取用点跟随新单例）。

- **切开发版清空迁档占位（`rf-803`）**：占位文案去掉方向词（原写「上方」与版面不符）；`devbump` 之后台账已属新周期，上一版「本版已随 vX 发布迁入归档档案」属过期信息——`release.py devbump` 现调用 `drop_migration_placeholders` 清掉全部占位节（含空节头），存量 0.13.12 占位节已一次性清除；「占位↔归档节」doc-drift 断言随占位消失自然收敛。回归用例 4 例（文案无方向词 / 清空全部占位 / 带散文节只摘占位行 / devbump 落盘清理）。

- **提交期门禁提速（`plan-170`）**：`offline_external_sources` 离线桩新增 `_NoWaitClock`（`time` 模块代理：`sleep` 变空操作、`monotonic`/`perf_counter` 原样透传），在 `apply_offline_stubs` 中接管 `core.throttle` / `core.retry` / `providers.cninfo` / `providers.datasink` 的模块级 `time`——间隔节流、多策略退避与 429 限速重试窗口不再白等“注定取不到的源”，分支照常覆盖、断言强度不变。作用域限于声明离线桩的文件（测试自身 `time.sleep` 与验证等待语义的用例不受影响）。实测 P0 `dev-verify` 墙钟中位 **37.3s → 24.0s（−36%）**；同时复核并行度：`-n 12` 反而更慢（user CPU 235s vs 145s），维持“每核 50%”口径不加并发。

- 新增回归用例 `unit/core/test_network_guard.py` 4 例（间隔节流零等待且算式返回值不变 / 退避零等待且重试次数不变 / 代理保留真实 `monotonic`·`perf_counter` / 未声明离线时等待语义原样），桩目标存在性断言补四个模块的 `time.sleep`。

- **台账迁档占位收敛（`rf-801`）**：`review-findings.md` 的「开发期已修复」占位节原来每版新增一节、旧版不收敛（已累积 5 段单行同构节），而三守护均拦不住——重复标题按路径感知判重（各节标题版本号不同）、长行阈值 40 字符 vs 占位行 33、区块需 5 行/100 字符。现 `_release/_ledger_archive.py` 新增 `_collapse_superseded_placeholders`，在 `apply_rf_archive` 末步只保留本版占位节：旧版占位行删除，节内若只剩占位与空行则节头一并删除，仍有表外散文（人工备注）则保节保散文只摘占位行；存量 5 节已一次性收敛为 1。回归用例 4 例（只留本版 / 散文节保留 / 单占位幂等 / `apply_rf_archive` 接线）。

- **统计快照写者顺序与钩子触发面（`rf-802`）**：pre-commit 的 `--sync` 触发面扩到**全部被统计的域**（`docs/managements/` 文档行数 / `src/test/` 测试行数与用例数 / `src/python/` 主程序行数 / `scripts/` 脚本行数）——此前只覆盖前两域，纯 `src/python`/`scripts` 改动会以「行数不一致」finding 拦下提交、逼人工 sync 再重提。同时把「写者顺序」写进纪律：`--sync` 必须是**收尾的最后一个写者**，`ruff format` / `collect-test-coverage --update-docs` 等写者全部在它之前，sync 之后只做只读校验（`dev-verify`/守护回放），否则统计表数字会因后续写入重归陈旧。守护：`unit/scripts/test_shell_contract.py::TestPreCommitSyncTriggerCoverage` 3 例。

## [0.14.1] - 2026-10-22

### Changed

- **报告域模块内拆分（`rf-773` 首批 3/8）**：`report/orchestrator.py` 734 → **255 行**（数据装配与派生计算 → `_orchestrator_data.py`）；`report/_report_generation.py` 751 → **52 行**（both/full 双路径 → `_generation_both.py` / `_generation_full.py`，共用步骤 → `_generation_shared.py`）；`report/fund_performance.py` 728 → **595 行**（评级内核 → `_fund_rating.py`）。全部保留门面 re-export 维持既有导入面；测试 patch 目标与结构断言按「调用点所在模块」改指新模块。剩余 5 个模块（api_base / _validation / holdings_detail_sheet / prosperity_scoring / news_dedup_rules）登记在 P3。

- **脚本域拆分（`rf-774`）**：`scripts/perf-view.py` 983 → **102 行**（采集/渲染/CLI 三段下沉 `scripts/_perf_view/`：`data.py` 367 / `report.py` 562 / `cli.py` 113，入口只留 docstring、sys.path 引导与 re-export）；`scripts/check-test-redundancy.py` 934 → **150 行**（八类检查各成子模块 `scripts/_test_redundancy/`：`_common` 共用 AST 原语 + 8 类检查模块 + `facts_cache` + `runner` 编排）。两处均保持 `load_script` 直调面（re-export），测试 patch 目标改指实现模块。

- **文档机检测试文件拆分（`rf-787`）**：`test_check_doc_drift.py` 1061 → 410 行，按机检项族切 `_partitions` / `_sections` / `_tree` 三个兄弟分片（118~289 行），用例数不变、共享夹具仍由基片提供。

- **代码工具按职责拆分（`rf-79`）**：`core/code_utils.py` 788 → **608 行**——派生量（交易所前后缀归一、FMP 风格符号、东财 push2 secid、cninfo 栏目参数、市值粗估）下沉 `core/code_symbols.py`（227 行），前缀常量的真值随之迁入并由 `code_utils` 引用同一对象（`is` 断言守卫「只存一份」）。`_strip_prefix` 更名公开原语 `strip_to_digits`（`is_six_digit_code` 在其之上构建，避免互相递归）。既有导入面经 re-export 保持不变。

- **Web 生成执行体下沉（`rf-711`）**：`src/python/web/handlers.py` 910 → **710 行**，生成链路（执行体 / 产物清单 / 完成通知 / 输入模式→快照域映射 / 退出码）拆到 `src/python/web/run_generation.py`（235 行）。`handlers.py` 保留同名 re-export 维持既有导入面，`app.py` 改为从新模块注入 `RunManager.executor`；测试 patch 目标按「调用点所在模块」改指新模块。纯结构调整，零行为变化（`unit/web` 347 passed）。

- **时间戳 helper 三份拷贝维持现状（`rf-790`，已决策）**：`core/decision_ledger.py::_now_iso` 与 `core/signal_ledger.py::_now_iso` 逐字相同（各 1 行表达式），`scripts/_release/_timing.py::now_iso` 带时区偏移（跨机/跨时区对拍用，不能合并）。复核确认全仓无第三份语义相同的 naive 实现，为 1 行表达式新开 `core/timeutil.py` 需同步目录树与文档，收益低于成本 → **保持两处各写一行，不排期**；重访条件：出现第三份 naive 拷贝，或任一处要改精度/格式时统一。

- **开发者指南重构（A~E 五批）**：① 加锚点目录 + 新增「文档地图」（本指南 / CLAUDE.md / technical / requirements / testplan / DESIGN* / folders / test-coverage / 台账 各自管什么、真源级别）+ 「新人 30 分钟路径」，章节按新人路径重排（环境 → 门禁 → 测试 → 调试 → 扩展 → 注册表 → 编号 → 发布 → 脚本 → 纪律来源）；② 把 1124 行的「辅助脚本速查」拆为独立 [`scripts-reference.md`](scripts-reference.md)（60+ 脚本按用途分类，每条含设计逻辑与使用逻辑；参考型文档无版本头），本指南只留「最常用十条 + 按域索引」，正文 2343 → 1481 行；③ 新增「调试与剖析」章（日志三读法 / 交互式调试 / 性能三件套 / **测试慢或挂住的诊断**（`-p` 插件统计 sleep、禁睡上限法、测量纪律）/ Web 端 CDP / `data/state` 状态文件排查）；④ 新增「开发新功能：扩展清单」（新增数据源/Provider、报告章节/页签、Web 接口/面板 三张端到端清单）；⑤ 版本发布流程补「CI 失败排查」（job → 症状 → 本地复现，含「本地绿 CI 红」三类根因）、「回滚与热修」、「依赖升级流程」。同步：folders 目录树与统计、CLAUDE.md 管理文档清单、README 开发者参考表、FAQ 一处死锚点改指新文档。

### Fixed

- **发布编排易用性（`rf-807` / `rf-808`）**：`prepare --version` 与开发链推导值不一致时立即中止并给出四步指引（不再「按推导执行」跑到中途报错，提示也不再误打印入参）；新增 `release.py archive-init`——新小版本首发的三份归档文件、folders 目录树块、三处「归档档案」索引行一次建齐（幂等、可 `--dry`，建完自动 doc-drift sync），把「补一处 → 重跑 check」的往返收敛为一条命令。

- **真实仓库契约测试断言周期相关状态（`rf-809`）**：`test_real_rf_sections_are_migrated_or_absent` 曾要求主台账「至少有一节」，与 `devbump` 清空占位后的空台账冲突 → v0.14.0 后 `dev` 提交 CI 全红（三版本 test + portability）。现改为只约束「存在的每一节」，空台账合法；`TestCliSurface` 的处理器集合改为从 `cmd_*` 派生。

- **changelog 发布指针链接跨小版本失准（`rf-806`）**：`apply_changelog_release` 只改指针的版本号与日期、归档文件名写死在上一系列——v0.14.0 发布后指针仍指向 `archived_changelog.0.13.x.md`（实际段落已进 0.14.x）。现改写指针时同步换名，格式不符即报错中止；已发布后的主文件指针已校正。回归 2 例（链接改指目标归档 / 指针格式不符拒绝）。

## [0.14.2] - 2026-10-22

### Fixed

- **changelog 归档索引行区间化（`rf-814`）**：`apply_changelog_release` 的索引改写只在行内已有 `~ v…` 时追加结束版本，导致首版行（`— v0.14.0（2026-10-21）`）在 v0.14.1/v0.14.2 两次发布后仍是单版本，与归档文件头不一致。现起止版本/日期由发布实参直接重算：无尾巴也区间化、同日多版不展开成 `a ~ a`；补 2 例回归。

### Changed

- **测试用例审计（`rf-813`）**：三类口径全量核查（10650 例 / 554 文件）——无效类新增扫描（无条件 skip/空体/测试内调测试/唯一 `is not None` 断言）0 命中；冗余类在八类机检外补「近重复结构指纹」（4 组，均为不同分支镜像，非重复）、跨文件同名（348 组，分属不同模块）、同实现 fixture（8 组，3 行 teardown）。真问题 3 类已修：10 个 `TestSP{n}` 系列编号类名改语义词、两处同名用例点明章节、3 处断言不达意（长度对齐/Beta、尾部风险注入、编译产物身份）改真断言；并给 `check-code-traces` 增 `^Test[A-Z]{2,3}[0-9]+[A-Z]` 规则防系列编号命名回流（含不误伤用例）。

- **修 CI 连红（`rf-812`）**：`unit/news/test_news_fetch_limits.py` 的接线守卫写死调用方路径（`cache/operations.py`），`rf-86` 拆分后新闻刷新移到 `cache/_cache_refresh.py` → 断言恒假，`portability` job 连红 5 次；而 P0 `dev-verify` 不含 `unit_news`，本地与 test job 均未拦住。现守卫改为 **AST 调用关系判据**（调用 `aggregate_news` 的模块必须引用 `news_fetch_limits`，定义体豁免，且「零调用点」也断言以防判据失效），并把 `unit_news` 纳入 `dev-verify` 组合（9 个子模块）。

- **文档↔脚本清单覆盖机检化（`rf-811` 复核口径固化）**：新增 `unit/scripts/test_scripts_reference_coverage.py` 5 例，把「核对」变成可重跑的断言——① 一览覆盖全部顶层脚本（`.py`/`.sh`/`.ps1`，排除内部共享模块）；② 一览无虚指（指向的脚本必须存在）；③《开发者指南》「按域索引」点名的脚本必须存在（专防 `dev-verify.sh`/`web.sh` 这类幽灵条目）；④ 七域行各自至少点名一个条目；⑤ `scripts/_*/` 每个实现包须在参考文档点名（包清单从文件系统派生）。另补两例内容层检查：**详情小节覆盖**（每条一览条目须有加粗小节标题，薄垫片入白名单）与**旗标真实性**（两份文档提到的 `--flag` 必须能在 `scripts/**` 或 CLI 解析器的 AST 字面量里找到，外部工具旗标走白名单——防旗标改名后文档滞留）。反向验证：删一览行 / 写不存在的脚本 / 去掉包点名 / 注入幽灵旗标四处均能红。

- **开发者指南 / 辅助脚本参考核对梳理（`rf-811`）**：修正 4 类不一致——① 指南启动行去掉不存在的 `dev-verify.sh` / `web.sh`（改为实际包装脚本）；② 顶层脚本 `factor_zoo_eval.py` 补一览行 + 诊断类详情（三指标判据 / 六个子命令 / 四条纪律 / `_factor_zoo/`）；③ 拆包实现点名（`_perf_view` / `_test_redundancy` / `_factor_zoo` / `_doc_drift`）；④ CLI 子命令行补 `cassettes`。另把「60+ 个辅助脚本」改为非数字表述，避免计数漂移。复核口径：一览表 ↔ 实际顶层脚本双向零差集。

- **发布归档报错附期望格式（`rf-810`，补齐 `rf-808` 后半）**：`prepare` 的 changelog 归一步四类格式失败（缺开发段 / 缺归档章节 / 缺指针行 / 索引行改写失败）原本只报「格式与预期不符」，现统一附「期望：<样例行>」+「下一步：先跑 `release.py archive-init`」——指针行、索引行、开发段三种样例都写进提示，不翻代码即可改对。回归 3 例。

- **缓存操作五职责拆分（`rf-86`）**：`cache/operations.py` 739 → **489 行**，缓存刷新族（公共缓存 / 新闻 / 基金经理 / 扩展缓存，13 个私有函数）下沉 `cache/_cache_refresh.py`（282 行）；原模块只留数据类、更新编排、清理、统计与预热。依赖单向（编排 → 刷新），`CacheUpdateResult` 用 TYPE_CHECKING + 函数内延迟导入避免环；测试 patch 按调用点区分（直接调刷新器 → `_cache_refresh`，经 `update_basic_cache` → `operations`）。P3 登记表清空。

- **报告域两模块拆分（`rf-626`）**：`report/html_writer.py` 799 → **689 行**（数据状态块装配 → `html_writer_status.py`）；`analysis/rebalance.py` 751 → **243 行**（偏离度信号族 → `_rebalance_deviation.py`，含分类权重与误报保护、四个常量随迁）。依赖方向单向：渲染 → 状态装配、信号 → 分类/配置（后者函数内延迟导入，避免与入口 re-export 成环）；门面 re-export 保持导入面，测试 patch 目标按调用点改指。

- **功能开关注册表下沉（`rf-665`）**：`config/features.py` 840 → **574 行**，注册表与定义（分组常量 / `FeatureSwitchDef` / `feature_switch_registry` / 纯注册表视图 / `_FEATURE_FLAGS_DEFAULT` / `EXPERIMENT_ALL`）下沉 `config/_feature_registry.py`（298 行）；原模块只留运行时状态（features.json 覆写读写、合并键迁移、开关解析与日志）并 re-export 注册表符号，既有导入面与开关语义不变。注册表仍是唯一事实来源（`is` 同一对象，无副本）。

- **发布台账补 token 采集与统计（`plan-171`）**：`logs/release.jsonl` 每行新增 `session_usage`（agent 会话累计 in/out/cache read/cache write/total/cost，取自 `PI_SESSION_FILE` 的 assistant 消息 + 非消息用量 + compaction，与 pi 统计同口径；非 agent 环境省略、旧行形状不变），命令尾行打印「本次发布累计 token」，窗口以「上一次 devbump」为界、跨会话按正增量分段累加；同时记录**执行环境身份**（`agent`：provider/model/thinking/session_id，取自 `PI_PROVIDER`/`PI_MODEL`/`PI_REASONING_LEVEL`/`PI_SESSION_ID`，非 agent 环境省略）并打印「执行环境：provider/model（thinking=…）」。采集全容错不阻断发布。回归 6 + 4 例。

- **近 36 小时变更的技术债核查与修复**：① 拆分时 `re-export` 块被追加在代码下方（`# noqa: E402` 豁免
  掩盖了「导入不在顶部」）——5 个文件（`llm/api_base`、`config/_validation`、`report/holdings_detail_sheet`、
  `report/fund_performance`、`analysis/prosperity_scoring`）的 re-export 归位到 import 区，豁免减为 `F401`；
  ② 审计出 **3 处拆分后静默失效的打桩**（`_spawn/_collect_health_checks` 的调用已随生成路径迁到
  `_generation_both` / `_generation_full`，测试仍 patch 门面 → 实际未拦截）：basic 分支改为从定义处
  `_report_health` 导入、三路径统一打桩到定义处，`test_run_integrity` 与 orchestrator 生成报告测试同步。
  核查结论：死符号 0（新模块私有符号全仓有引用）、完全同体函数 0、377 个模块导入全通过且无反向依赖、
  门面 re-export 无死面。

- **模块内拆分收尾（`rf-773` 剩余 5 个）**：`llm/api_base.py` 770 → **501**（响应解析 → `_api_responses.py`）、`config/_validation.py` 723 → **119**（标量/章节/LLM 三域 + 共用原语 `_validation_common.py`）、`report/holdings_detail_sheet.py` 716 → **171**（分区块写入器 → `_holdings_detail_blocks.py`）、`analysis/prosperity_scoring.py` 711 → **476**（输入与权重 → `_prosperity_inputs.py`）、`providers/news_dedup_rules.py` 710 → **331**（纯词表 → `_news_dedup_tables.py`）。至此 rf-773 的 8 个模块全部拆完（前批 3 个已随 v0.14.1 发布）；门面 re-export 保持导入面，区块注册表与章节-区块矩阵的载体列同步更新。
