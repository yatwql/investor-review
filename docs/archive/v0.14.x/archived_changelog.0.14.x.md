# 变更日志归档 — v0.14.x

> 归档时间：2026-10-23（v0.14.7 发布并入；已并入 8 段：v0.14.0（10-21）、v0.14.1（10-22）、v0.14.2（10-22）、v0.14.3（10-22）、v0.14.4（10-22）、v0.14.5（10-22）、v0.14.6（10-23）、v0.14.7（10-23））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.14.0 ~ v0.14.7（2026-10-21 ~ 2026-10-23）
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

## [0.14.3] - 2026-10-22

### Added

- **`--mode portability`：CI portability job 本地等价复现**：新增非 pytest 探针模式（`scripts/_test_runner/portability.py`），一条命令跑 CI 的阻塞探针——①`PYTHONWARNDEFAULTENCODING=1` 隐式编码严格档（单元套件）；②需求文件 BOM/PEP263 **确定性判定** + `LC_ALL=C` 下 `pip install --dry-run` 烟测（pip ≥25 起默认 UTF-8，输出提示「完整判定需 pip ≤24.x」，确定性判定始终生效）。探针模式无 marker、不进 bench 与三档门禁，计数量按探针项数；配套纪律「本地门禁通过后不逐提交轮询 CI」写入 CLAUDE.md 与 developer-guide。回归 13 例（BOM/cookie 四态、两道探针环境与失败回传、聚合口径、注册表接线）。

- **Social Preview 生成脚本入库**：`scripts/make-social-preview.py` 把 1200×630 品牌预览图的画布模板（猫头鹰「守望」左卡 + 品牌文案右栏 + 夜空渐变）与渲染流程固化进仓库——素材复用 `src/static/owl-mascot.svg`，改文案/换色后重跑即就地刷新入库资产 `src/static/social-preview.jpg`（默认输出，`-o` 可改道临时目录），提交后由人工上传到仓库 Settings。`cairosvg` 为维护期可选依赖（不入 requirements：无 cairo 系统库的环境装不上），缺依赖或素材不可读时打印指引并以退出码 1 结束。回归 13 例（画布尺寸/品牌文案/素材内嵌一致/宽高比/入库资产定位/成品尺寸/栅格化参数/中间 PNG 去留/真实导入装配/两条退出码路径）。

### Changed

- **流程文档同步脚本命名规范（前缀 ↔ 域）**：`scripts-reference.md` 新增「命名约定」小节（前缀 ↔ 域 ↔ 契约的判定表，含「`check-` 仅限可入门禁的检查」这条硬边界），`developer-guide.md`「新增脚本时」与 `CLAUDE.md`「scripts 共享设施与契约」同步为「先选前缀再归域」；顺带清理陈旧引用（`pyproject.toml` 的 svg extra 注释、`eval-factor-zoo` 测试 docstring）。

- **视觉资产工具收口为 `make-assets.py`**：`check-svg.py`（架构图渲染体检）与 `make-social-preview.py`（社交预览图生成）合并为单一入口 `scripts/make-assets.py`（子命令 `social-preview` / `svg-geom` / `svg-pixel` / `svg-text-overflow`，实现拆 `scripts/_assets/` 包）。`check-*` 前缀此后专指**可入门禁的检查脚本**，不再混入按需资产工具；退出码统一 0/1/2（1=环境缺失、2=发现越界），`social-preview` 重跑与入库图逐字节一致。

- **`scripts/` 顶层脚本命名规范化**：非 `check-*` 脚本按活动类型统一前缀，看文件名即知归属——`test-`（测试执行与测试工程：`test-collect-coverage` / `test-extract-failures` / `test-find-order-dependent` / `test-smoke-web` / `test-perf-report`）、`eval-`（评测与校准：`eval-llm-hallucination` / `eval-factor-zoo` / `eval-dedup-threshold`）、`perf-`（运行性能观测：`perf-history`）、`hook-`（钩子接线：`hook-install-claude`）；`check-*` 专门指「可入门禁的检查脚本」，`factor_zoo_eval.py` 的下划线命名一并修正为连字符。同步改名 10 个文件与全部引用（文档/CI/钩子/测试/sentinel 字符串），历史归档与 changelog 已发布段保持原名。

  **旧→新对照**（已有 cron / 脚本引用需同步）：`collect-test-coverage`→`test-collect-coverage`、`extract-test-failures`→`test-extract-failures`、`find-order-dependent-test`→`test-find-order-dependent`、`smoke-web`→`test-smoke-web`、`perf-test-report`→`test-perf-report`、`perf-view`→`perf-history`、`llm-hallucination-sampler`→`eval-llm-hallucination`、`factor_zoo_eval`→`eval-factor-zoo`、`calibrate-dedup-threshold`→`eval-dedup-threshold`、`install-claude-hook`→`hook-install-claude`、`check-svg`/`make-social-preview`→`make-assets`。测试文件同步改名（`test_perf_view`→`test_perf_history` 等 10 个），保持「一个脚本一个同名测试文件」的可发现性。

- **脚本分类重整（七域 + CLI 入口）**：原「诊断」是杂物袋（连通性探针 / 性能基准 / 能力评测 / 渲染检查 / 用户子命令混坐），且同族脚本分落不同域（`llm-hallucination-sampler` 在测试、`factor_zoo_eval` 在诊断，sampler 另有独立章节）。现按**活动类型**重划：拆出「运维观测」（`probe*` / `perf-view` / CLI 的 `check-sources`·`doctor`·`view-logs`·`cassettes`）与「评测与基准」（`perf-test-report` / `llm-hallucination-sampler` / `factor_zoo_eval` / `calibrate-dedup-threshold`）；`check-svg` 归「文档」（检 README 架构图）、`whatif` 归「CLI 子命令」（用户功能，非维护工具）、需求追溯与任务编号四件归「代码与文件质量」（门禁职责）。`scripts-reference.md` 一览/小节/目录与 `developer-guide.md` 按域索引（7→8 行）同步，域行数断言同源更新。

- **README 实景截图全面刷新**：报告三图（首屏品牌标记与目录导航 / 盈亏汇总与市场指数 / 穿透行业分布与 TOP10 持仓交互图表）与 TUI 主菜单、Web 工作台、Web 配置三图按当前版本（v0.14.3-dev）重拍，并新增 **CLI 渠道回显图**（产物路径 / 盈亏汇总 / 模块耗时排行）；样例持仓为虚构两账户 10 只（个股 / ETF / 场外基金 / 债券基金 / 货币 ETF），在隔离目录内生成，真实持仓、缓存与报告目录零接触；README 图说与 folders 目录树/统计行同步（截图 6→7 张）。

- **品牌标记补用（`rf-818`）**：猫头鹰「守望」此前只活在 README 与 Web favicon，报告与 Excel 首页没有标记。现 `DESIGN.md` 契约收窄为「拒绝 hero 大图、装饰性插画」并新增「品牌标记」条款（≤40px 身份识别、Excel ≤48px、不做装饰）+ 护栏 11；报告 favicon 由折线图换猫头鹰头像、页头加 32px 标记（窄屏 26px）、Web 工作台页头 36px、Excel 首页 40px（cairosvg 栅格化，失败静默跳过）；新增 `--brand-mark-ink` token 并登记 Colors 表。回归 5 例。

- **仓库更名 `investor-util` → `investor-review`（`rf-817`）**：`util` 后缀与产品定位（完整工作流的应用，非脚本合集）矛盾，且与中文名「投资复盘助手」语义不对应。同步 14 个文件 47 处引用：README 徽章与 clone 命令、`pyproject.toml` 包名、目录树根名、四份用户手册路径示例、CLI/Web `prog` 显示名、三个 provider 的 HTTP `User-Agent`、通知邮件 `From` 兜底。GitHub 侧旧 URL 永久 301 重定向，外部引用不断。

### Removed

- **`scripts/` 旧探测入口垫片移除**：`probe-csi-factor-indices.py` / `probe-push2.py`（各 12 行薄委托）删除——统一入口 `probe.py csi` / `probe.py push2` 已稳定多版，脚本非安装型入口（无外部调用方、无发布契约），兼容垫片只剩维护面。用法改由参考文档「`probe.py` — 探测统一入口」一节承载。

### Fixed

- **报告域重复实现清理（`rf-821`）**：`report/html_writer_status.py` 里与 `report/html_writer.py` 逐字相同的 `_render_template`/`write_html_report`（约 591 行）与文件内重复定义的状态构建辅助一并删除，模块回归「数据状态装配」单一职责（901 → 134 行）；核心渲染保持 `html_writer.py` 单实现，失效的 re-export/import 与失真导览注释同步清理。
- **文档分类重整遗留漂移清理（`rf-820`）**：`scripts-reference.md` 组标题归位（「测试质量机检」误迁入评测类、「冒烟与采样」剩单条改「冒烟验证」）、质量类条目读序改为「痕迹 → 需求追溯 → 编号/钩子 → 行数/契约/护栏」；`README.md` 去掉会随开发演进的硬编码计数（22 项开关 → 全部开关含实验项、六个 LLM 模块 → 全部模块、10 张图表 → 实测 12 张）；删除 `docs/tmp/github/` 中与入库资产重复的预览图副本。
- **Social Preview 脚本默认输出与装配修正（`rf-819`）**：`_load_render_deps` 仍按旧字段名 `image_cls` 构造 `RenderDeps`，真机执行即 `TypeError`（回归只走注入替身，未覆盖真实导入装配）——改为 `image_module` 并补「真实导入装配」用例；默认输出改为入库资产 `src/static/social-preview.jpg`（受 git 管控，重跑即就地刷新），`-o` 可改道；重跑产物与已提交图片逐字节一致。

- **`publish` 提交前同步统计快照（`rf-816`）**：钩子对含 `src/test` 变更的提交走 `--sync --ci --with-test-count`，而 `publish` 原先不校验，只跑 `--sync` 时 `test-coverage.md` 收集计数陈旧不被发现——本地通过、钩子仍红，v0.14.2 连败两次 publish。现 `publish` 在提交前自动按同源参数同步，失败即中止；补 2 例回归。

- **浮点断言容差化（`rf-815`）**：v0.14.2 的 `test_unequal_lengths_uses_shorter` 用逐位相等比较「对齐到较短者」与「显式截断」两条路径（末位差 1.6e-17，3.13 恰好相等、3.11 不等）→ 改 `pytest.approx(abs=1e-12)`，长度敏感反例改 `> 1e-6`。同时把纪律落进三处文档：根 `CLAUDE.md` 测试纪律、`developer-guide.md` 测试写作规范（正反例）、`testplan.md` 的「浮点比较边界」边界行——判据是「语义等价就带容差，精确可表示值才用 `==`」，容差取「远大于 ulp、远小于真正区分的量级」。

## [0.14.4] - 2026-10-22

## [0.14.5] - 2026-10-22

### Fixed

- **事件窗盘中运行 100% 降级（面板长期空白）**：`WINDOW_AFTER=5` 要求事件日后尚有 5 个交易日，而新闻事件日就是当日/昨日、行情轴止于当日 —— 实测单次运行 `可出行 0 / 降级 14`，14 条全是「窗口超出行情范围」，开启开关也拿不到任何事件行。改为右界按**行情轴实际可用交易日截断**计算（`window_after_actual` 回显、`window_partial` 标注），事件日后 0 个可用交易日才降级；视图摘要写明「N 条后窗未满（最短 M/5 日）」；需求 `R-EW-01/02` 同步。注：v0.12.x 曾否决「半窗截断」，当时前提是严格口径下仍有 23 条可出行，本次不引入第二口径（统一一条规则 + 逐行回显实际日数）。
- **发布门禁放过空 changelog 段**：v0.14.4 的开发段停在占位句，`prepare` 把占位原样归档 → 归档文件只有 `## [0.14.4] - 2026-10-22` 一行标题、正文永久丢失。`apply_changelog_release` 现前置断言「开发段必须含实际条目（`###` 分类或 `- ` 条目）」，命中占位即中止并提示先补 changelog。
- **缓存清理按虚龄删脚本性能缓存**：`data/cache/test_coverage_snapshot.json` / `test_redundancy_facts.json` 由脚本裸 JSON 写入、无 `_ts`，清理器按 `now - 0` 算出 **57 年陈龄**并每轮启动删掉（缓存优化白做 + 日志荒谬）。脚本写入补 `_ts` 包封，清理器对仍无 `_ts` 的文件一律跳过（托管边界之外）。
- **数据源硬等待**：基金档案页（回退链路）超时 15s → 8s（实测 SSL 握手挂起单请求 17s）；东财 push2 遇「对端主动断开」不再退避重试、直接回落下一链路（实测每个断连代码白等 0.6s，而 `eastmoney_industry_rest` 秒回）。

- **章节清单缓存持久化失效章节名**（rf-822，诊断经日志复核后收窄）：原判断「陈旧 doc-id 导致 `全链路失败` WARNING」不成立——该 WARNING 分支已随日志治理改为按传输级失败分级（`各源均无可用结果` 走 INFO），且 404 落在**章节探测**（`?section=`）而非文档级、每个 doc id 仅 2 次尝试（主/备各一，无重复探测）。真实残留缺陷是：章节名清单为 14 天缓存，命中后若该批章节全部取不到正文，旧名字会持续 404 且永不恢复（实测单轮 5 例 × 约 1.3s 无效往返）。修法：取正文全空时失效该文档的清单缓存（`_invalidate_sections_cache`），下次重取 `/sections` 买回恢复机会；取到正文或无清单可清时不动缓存（防每篇都清、清单缓存形同虚设）。

- **thinking 串行等待可量化**：除「等待超 5s 记 INFO」外，段末在累计等待 ≥20s 时给出「提到 2 约可省该时长」的可执行提示（含配置键降级路径），并把累计毫秒数写入 `perf_history.counters.llm_thinking_wait_ms`（每轮清零）。默认仍为 1——提到 2 的前提（并发两个 thinking 请求无空响应）本机缺稳定性样本，判据与操作步骤见 `llm-technical.md`，由数据决定而非改默认值。
- **gate 兜底 changelog 归档段非空**（plan-174 收尾）：`prepare` 已拦「占位句原样归档」，`gate` 再加一道——归档文件缺该版本段、或该段只有标题/占位句即前置中止（未跑任何子进程），防旁路/人工归档写出的空发布记录。
- **事实校验修正数上屏**（plan-180 收尾）：`doctor` 运行台账行在最近运行存在修正时追加「事实校验自动修正中位 N 处」，把 `fact_fix_*` 从「写进台账但没人看」变成自检可见。

- **K 线风控页不再当「解析失败」重试**：被限流时上游返回 200 + HTML/纯文本 → 今按「非 JSON 载荷」判定，记该源失败（驱动熔断冷却）并立即交下一链路，不重试。实测腾讯/新浪每轮各 4 条 `Expecting value` 的无效重试与退避等待由此消除；判定收敛于 `providers/_utils.looks_like_block_page`（两源共用）。
- **去重锚点告警文案与备份策略**：警告不再声称「flush 需读写全文」（写侧已是追加、成本与体积无关，只有加载与压缩随体积增长）；压缩已执行仍超线记 INFO（锚点本身多属正常），压缩被禁用/失败才 WARNING；压缩成功后 `.bak` 默认清理（校验 + 原子替换后删除），`INVEST_DEDUP_KEEP_BACKUP=1` 可保留。

### Changed

- **新闻去重锚点改真追加写**：flush 原走「读全文 → 整文件替换」，而锚点已 37.9 MB、每轮只新增数十条 —— 写盘成本与文件体积成正比、与新增量无关。改单次 `write` + `fsync` 追加（读侧本就逐行容错）；压缩条件从「仅每 key 最新」扩为「每 key 最新 + **仅保留近 120 天**」（`INVEST_DEDUP_ANCHOR_RETENTION_DAYS` 可覆盖，0 = 纯去重）——仅按 key 去重压不动（标题对高度唯一，压后仍 37.9 MB），保留期才是体积上限。
- **缓存清理日志降噪**：逐文件明细 INFO → DEBUG（单日 257 行、占全天日志 7.2%），INFO 只留汇总行 + 释放字节；age/TTL 按量级自适应单位，盘中 30s 的 price TTL 不再印成 `ttl=0.0h`。
- **交易日历进程内 memo**：`_get_trading_calendar()` 单次报告被调用 600+ 次、每次都读盘解析 JSON；改为按「缓存文件指纹 + 剩余 TTL」进程内复用，文件重写/到期即回落磁盘（语义不变），conftest 加 autouse 复位。
- **事实校验自动修正计数入 `perf_history.counters`**：新增 `fact_fix_total` / `fact_fix_numeric` / `fact_fix_code` / `fact_fix:<模块>`（LLM 阶段前清零、结束后汇入）——单次实测 5 处修正，此前只进日志无法跨期判断提示词改动是否有效。
- **thinking 模块默认并行（`llm_max_thinking_concurrency` 1 → 2）**：上限 1 时两个 thinking 模块完全串行——两次实测分别等待 38s 与 **68.7s（占该次墙钟 154s 的 44%）**，体检全程排在智囊团之后。默认值提到 2（代码默认 + 配置生成器注释 + `requirements`/`how-to-config-llm`/`llm-technical` 同步），回滚条件是端点出现空内容重试或内容质量下降（改回 1 即可，配置侧生效）。同时保留可观测性：单模块等待超 5s 记 INFO、累计毫秒数进 `perf_history.counters.llm_thinking_wait_ms`、上限 <2 且累计 ≥20s 时给出「提到 2 约可省该时长」提示。

## [0.14.6] - 2026-10-23

### Added

- **CLI `health-history` 子命令（plan-181）**：查看最近 N 次数据源健康记录（`--limit` 默认 10、`--json`），聚合单源 `core.perf.summarize_health_history`（与 TUI `[H]` / Web `/api/health/history` 同字段）；无需 config（配置损坏也能查），无记录为友好空态、读取失败退出码 2。至此 CLI/Web/TUI 的健康历史信息面一致。
- **CLI 收尾打印产物路径（plan-183）**：报告生成后输出「产物目录 + 各产物绝对路径」（定位下沉 `core/artifacts`，与 TUI 同一事实；不做交互，脚本不被阻塞）。
- **Web 产物路径可复制（plan-183）**：结果区每个产物旁显示服务端绝对路径，点击即复制（浏览器与报告不同机，「打开目录」无意义）。
- **LLM 调优参数面板（plan-184）**：`config/edit_ops.LLM_TUNING_SPECS` 声明 6 个可调键（thinking 并发 / 模块并发 / 重试 / 整链重试等待 / 总时间预算 / 日费用上限）及范围与说明；Web 配置面板新增「LLM 调优参数」组、TUI 新增 `[D]→[L]` 子项，保存走同一编辑层（超范围明确拒绝）；此前只能手改 JSON。
- **报告收尾列出产物并支持一键打开**：E/B/L 生成完成后打印报告目录与已生成的 HTML / Excel，问一句「是否打开报告目录与报告？(y/N)」——`y`/`Y` 打开，**默认 N**（其余任何键含 `n`/回车/`Esc`/未知键均按 N），`Esc` 只跳过回菜单、`Ctrl+C` 沿用 TUI 约定退出，非 TTY 只列清单不询问。打开动作平台分派（`startfile`/`open`/`xdg-open`），失败不报错、降级为手动路径提示。取代原「按任意键返回菜单」：同样是按一下回菜单，但键义明确、不多一步（`R-TUI-09`）。

### Fixed

- **发布期失败不可见（`rf-833`）**：`test-runner.py` 的摘要过滤关键字只含小写 `failed`，pytest 的 `FAILED <用例>` 行被整行吞掉——`refresh` 失败时输出只剩一行计数，定位必须手工重跑全量单元（与「禁止重跑全量」纪律冲突）。补 `FAILED` / `ERROR` 两个大写关键字，失败用例名随 runner 输出直达。同批修一处补丁目标：`is_formal_holdings_source` 下沉 `config/_config_api.py` 后，边缘用例仍 patch 包入口同名符号（调用点已绑定在下沉模块）→ 异常分支恒不触发、用例假绿；改指 `_config_api.resolve_holdings_path`。

- **拆分批次自身的 4 类技术债（rf-832）**：`test-perf-report.py` 与 `_perf_report/report.py` 各持一份基准目标秒数（`--gate` 退出码与报告达标判定各读一份，改一处即「报告说达标、门禁判超标」）→ 收敛为渲染模块单一声明、入口按名导入；`release.py` 的 docstring / `_Env` 注释仍指向已删除的 `_release/_commands.py` → 改指 `_commands_prep` / `_commands_ship`；`_commands_prep.py` 两处 `# noqa: F401` 死导入（含「prepare/check 共用」的误导注释）→ 删除；`_Env._ALIAS` 死别名 `MANAGEMENTS_DIR` 与拆分时丢失的 4 处返回类型标注 → 一并补齐。
- **近 12h 实施变更技术债核查（rf-831）**：清掉两处重复实现与一处渠道层重复模板——评测工具 `_eval_factor_zoo/metrics.py` 的 `_pearson`/`_ema` 改为直接导入生产 `analysis._factor_formulas`（不再本地留副本遮蔽「同源」导入）；`core/holding_status` 的 `_detail_value`/`_has_effective_quote` 改为复用 `core.data_freshness` 单一实现；`TuiProgressReporter` / `WebProgressReporter` 的 `call_sheet` 上提为 `AnnouncingProgressReporter` 唯一实现（补结构断言两渠道同一函数对象）。另修两处台账/文档漂移：README「HTML 10 图」→ 12 图（与模板实测一致）；恢复被误删的已完成 `plan-181` 节并清掉其孤儿正文。复核：全仓重复函数体 0 组、`check-style-guardrails` E 级与 `check-test-markers` / `check-script-contract` 无新增 finding。
- **TUI 报告追问首字为孤立代理项→整条 provider 链误判失败（rf-830）**（实机复现：按 `Q` 提问返回「服务暂不可用」）：POSIX 下 `sys.stdin` 的 `errors=surrogateescape` 会把终端传入的非法 UTF-8 字节解成 U+D800~U+DFFF，问题首字恰好命中时，httpx 以 `ensure_ascii=False` 序列化请求体在 `.encode("utf-8")` 抛 `UnicodeEncodeError`，又被 `_attempt_api_call` 的 `ValueError` 分支归为「响应解析失败/api_error」——所有 provider 同败，与实际网络/配额无关。新增 `core.text_safety` 统一口径（合法代理对折叠为星平面字符、孤立项→U+FFFD），并在 LLM 请求体（`call_llm_with_retry` 入口递归净化）、LLM 响应正文（`_process_success_response`）与追问问题入口（`qa.session`）三处过关；回归用例锁「带孤立代理项的请求体能正常发出」「响应正文能落 HTML」「问题/历史存净化后文本」。
- **CLI 产物清单不再在失败时误导**：仅在非严重失败（有产物可交付）时打印；`core.artifacts.collect_artifacts` 增加显式 `output_dir` 入参，CLI 不再靠「复制 config 字典改键」传覆盖值（`--output` 语义直连）。
- **异常提示的 JSON 判定改类型判断**：`core.error_hints` 不再用异常类名字符串匹配 JSON 解析错误（类名一改即静默失效），改用 `isinstance(exc, json.JSONDecodeError)`。
- **`gate → publish` 的 verify 复用按构造永不命中**（v0.14.5 发版实测，等于每次白跑约 27s）：`code_fingerprint` 原用 `git diff HEAD` + `git status` 哈希，而 publish 会先提交 prepare 的改动再算指纹——HEAD 一变，同一份代码就得到两个指纹。改为 `CODE_PATHS`（`src` / `scripts` / `pyproject.toml` / `pytest.ini` / `requirements.txt`）下 **tracked + 未忽略未跟踪文件的内容 sha256**，提交前后一致；回归用例锁「提交前后同指纹 / 内容变化变指纹」。
- **单测改写仓库真实发布戳**（v0.14.5 发版期间发现 `logs/release-gate-stamp.json` 被写成夹具版本 `0.13.12`）：`TestGateArchivePrecondition` 沙箱漏隔离 `GATE_STAMP_FILE`，gate 成功用例走完尾部写入真实路径；现该测试模块统一 autouse 重定向「通过戳 / bench 戳 / 耗时台账」，并加回归断言「跑完 gate 成功用例后仓库真实戳字节不变」。
- **`prepare` 归档后「当前迭代」概述行失准**：归档搬走 ✅ 节后该行仍写「在办 15 项…已实施待归档」（doc-drift 不校验这句，每版都要人工改）。`apply_plan_archive` 现按**现存 `#### plan-N` 节**重算在办项数与 P1~P4 分档编号，残留/幻影编号（如已不存在的 `plan-128`）一并纠正；无分层标题时保守不动。
- **渠道层常量/回退链/展示规则单源化（rf-823~828）**：
  - `config.resolve_output_dir(config, override)` 取代 12 处各自为政的 `output_dir` 回退链（含 3 处 `"reports"` 字面量），统一绝对化；
  - `core.num_utils.format_size` 取代 TUI 三处 + CLI 一处的 KB/MB 格式化（此前取整位数已不一致）；
  - `core.error_hints.hint_for` 成为「异常→用户提示」唯一映射：TUI 上屏、CLI 未处理异常行取同一句话（Web 可并入信封），类型判定优先于关键词、内部异常标 `log_detail` 记堆栈；
  - `config.read_llm_settings_file` 成为「原始落盘值」唯一读取入口（TUI 配置面板 / Web 配置面板共用），不再各自 open+strip+parse；
  - doctor 网络检查预算收敛到 `core.doctor`（`NETWORK_TIMEOUT_DEFAULT`/`NETWORK_TIMEOUT_WEB`/`CEILING` + `normalize_network_timeout`），CLI/TUI 用默认档、Web 用 Web 档，渠道不再写数字；CLI 查询串超上限按 15s 截断；
  - TUI 页头「新鲜度」改用 `core.data_freshness.header_freshness`：阈值取 `degradation` 分层最严档（默认 3 天）、偏旧判定取交易日口径（日历只读缓存、不触网），与报告内数据质量同一结论（此前 TUI 自定 `_STALE_DAYS=7` 且用自然日）。

### Changed

- **文件膨胀登记逐项处置（rf-829）落地**：按「行数 × 近 90 天改动次数」优先级把三域全部拉回警告线以内——**主程序** `web/handlers.py` 709 → 616（只读观测路由 → `handlers_health.py`）、`core/doctor.py` 734 → 608（日志与缓存探针 → `doctor_logs.py`）、`config/__init__.py` 269 → 195（渠道共享 API → `_config_api.py`）；**脚本** `release.py` 992 → 331（argparse 装配 → `_cli.py`，命令实现 → `_commands_prep.py` / `_commands_ship.py`，共用原语 → `_commands_base.py`，路径常量与 `env` 属性投影留入口）、`check-doc-traces.py` 692 → 575（已删函数残留 → `_traces_doc/deleted_refs.py`、结论输出 → `findings.py`）、`check-style-guardrails.py` 636 → 543（规则声明 → `_guardrails/rules.py`）、`test-perf-report.py` 635 → 544（报告渲染 → `_perf_report/report.py`）、`_doc_drift/__init__.py` 237 → 136（冗余 `__all__` 清单退役）；**测试** 7 个文件分片至警告线以下（详见 review-findings P3 出登记清单）。全部保留原面 re-export，测试用例数逐文件对拍不变（例：`test_orchestrator` 38 = 24 + 14）；patch 目标按「调用点所在模块」同步改指（`_perf_report.report` / `_traces_doc.deleted_refs` / `doctor_logs`）。
- **收益率口径标签 + 提示词文本版本进指纹（plan-185）**：进提示词的数据表统一带口径标签（`持仓收益率（自买入，未年化）` / `组合持仓收益率（成本口径，未年化）` / `区间收益率（窗口内，未年化）`）并附一次口径说明，覆盖持仓行 / TOP3 / 数据槽 / 竞争语境 / 智囊团 / 体检 / 穿透 / 全球政经；新增 `llm/rate_caliber` 单一声明点，`PROMPT_SCHEMA_VERSION` 并入模块指纹，静态文案改动也能让旧口径缓存失效。不改正数与取数链路。
- **文件膨胀处置登记（rf-829）**：`scripts/release.py` 与其余逼近红线文件在 `review-findings` 登记拆分方案与处置方向；release.py 优先项已完成（见上），其余文件继续按登记表逐个处置。
- **测试文件分片**：`test_news_sources.py` 1054 行 → 拆分出 `test_news_dedup.py`（标题判定算法/锚点写入去重/追加写与保留期），两文件均回落到红线以下；同步 folders 目录树。
- **LLM 调优项默认值单源**：`LLM_TUNING_SPECS` 不再各写一份默认值，改为构造时从 `_DEFAULT_LLM_SETTINGS` 取（新增 `config.get_llm_setting_default`）——避免改出厂默认时两处漂移。
- **plan-182 决策不做**：CLI 的「一次命令 + 管道」形态不适合多轮追问，保留 TUI `[Q]` / Web `/api/qa/ask` 两个自然入口；脚本化场景走 Web API。
- **`devbump` 默认推送 `origin dev`**：发布闭环的收尾就是「切版 + 同步远端」两步——上一版（v0.14.5）实测需人工补 `git push origin dev`，漏做会让本地领先远端一个提交。现 `devbump` 默认执行推送，需要本地先复核时用 `--no-push`（`--push` 保留为兼容别名、与省略等效）；推送失败**不回滚**已落盘的切版提交，但会报错并给出重试命令。CLI 默认值由用例锁定（`devbump` ⇒ push=True / `--no-push` ⇒ False）。

## [0.14.7] - 2026-10-23

### Changed

- **`devbump` 后主台账残留空壳批次节（rf-835）**：迁档时保留的标准说明行（`> 完整复盘见 changelog.md X-dev 段…`）被当成人工备注，占位行清掉后该节只剩说明行 → 「已解决问题」区长期挂一个指向已归档版本的空节。现按正则识别标准说明行为机器生成内容（非本版即摘除），批次节摘除后若已无台账行则整节删除；人工备注仍保留节头。回归 2 例。
- **`test-runner --fail-fast`（rf-834）**：多档运行首个失败即中止并取消尚未启动的档，摘要显式列出被跳过的档（已启动的档不打断——强杀 pytest 会丢失败详情）；串行与并行共用同一调度器，`release.py refresh` 的 bench 步默认启用。
