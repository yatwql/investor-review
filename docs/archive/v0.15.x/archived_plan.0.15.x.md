# 计划归档 — v0.15.x

> 归档时间：2026-10-24（v0.15.0 发布，本系列首份）；2026-10-24 v0.15.0 本批原表搬运；2026-10-24 v0.15.1 本批原表搬运；2026-10-25 v0.15.5 本批原表搬运；2026-10-25 v0.15.7 本批原表搬运；2026-10-30 补录 plan-208/209/225/226/228（发布时台账节被直接删除、未入档）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.15.x 开发期完成项（含 v0.15.7）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-185` 收益率指标缺口径标签，模型反复写错 ✅

交付：口径标签生效，`fact_fix_total` 连续 8 轮为 1（≤3 达标）。

## ✅ `plan-195` Web 配置面契约（domains / labels / blocks）——已实施，待发布归档

服务端下发 `domains`（五域 → 有序块清单）与 `labels`/`descriptions`/`defaults`/`needs_hint` 元数据、`logging`、`reference`；前端按域渲染 + 块渲染器分派，零中文表。机检：`test_config_surface_contract`（17 例）；记录见 changelog 配置重构第 10 轮。

## ✅ `plan-196` Web 配置面交互与状态——已实施，待发布归档

工具条统计（基准 = 服务端 `defaults`）、关键词筛选、域导航与 `#domain-<key>` 深链、块计数、窄屏单列；保存语义分即时（失败回滚）与显式（失败保留输入）两类。机检：`test_web_config_interaction`（17 例）；记录见 changelog 配置重构第 11 轮。

## ✅ `plan-197` 配置重构的文档与契约登记收口——已实施，待发布归档

手册与管理文档全量对齐当前结构（主菜单 14 项四组、Web 五域分区、`[G]` 七项四组、`[D]` 四项），抽检 `[D]`/`[G]`/`[S]`+`[C]` 三处与代码逐字一致；契约档结构守卫绿。记录见 changelog 配置重构第 12 轮。

## ✅ `plan-198` 配置重构质量门禁全量——已实施，待发布归档

五道闸口全绿：`verify` 11318 通过 / 0 失败、十守护零 finding、性能门禁 basic **0.48s ≤ 60s**、`portability` 2 探针通过（`LC_ALL=C` + 隐式编码严格档）、`ruff check` / `format --check` 零告警。本轮修正两处真实缺陷：计价懒加载覆盖显式重载（`rf-837`）、`test_json_comments` 子进程缺显式编码（portability 探针拦下）。记录见 changelog。

## `plan-199` 配置重构发布编排——已完成，待发布归档

**状态**：v0.15.0 已走通 `release.py` 全链（`prepare` → `refresh` → `evolution --release` → `gate` → `publish` → `devbump`）；gate 全绿、版本一致性 15 项全绿、tag 已推送、master 已合并、devbump 后版本头一致。配置体系设计文档随本版迁入 `docs/archive/v0.15.x/config-rework/`。

## `plan-200` 配置稳态观测与回退演练——已完成，待发布归档

**状态**：四类路径（非法配置 / 删除重建 / 缓存首轮重算 / 非当前结构拒绝）由 `test_config_resilience_contract`（10 例，`tmp_path` 隔离）机检；观测复用现有日志与 `perf_history`，未新增面板。记录见 changelog。

## `plan-201` 事实校验评估函数参数收敛（技术债）——已完成，待发布归档

**状态**：`_evaluate_percent_value` 的 22 参收进冻结 dataclass `PercentContext`，签名收敛为 `_evaluate_percent(ctx)`；行为零变化（`src/test/unit/llm` 1326 例）。记录见 changelog。

## `plan-202` 演示截图生成器入库——已完成，待发布归档

**状态**：入口 `scripts/make-screenshots.py`（`demo` / `report` / `tui` / `web`）+ 实现包 `scripts/_screenshots/`；16 例回归；参考文档与目录树三处登记。记录见 changelog。

## `plan-203` 发布流程四处改进（失败前移 / 台账自证 / 预检前移 / 记账补全）——已完成，待发布归档

**状态**：日志动线进 dev-verify + 打点矩阵自证；bench 场景档前置；台账失败写 `failure`；`check` 预演 changelog 派生；publish 分段计时并在 gate 戳失效时点名改动的代码文件；`[C]` 无效编号提示由注册表派生。回归 9 例。记录见 changelog。

## `plan-204` 测试用例全量审计与整改——已完成，待发布归档

**状态**：扫描 586 个测试文件 / 11,111 个 `def test_` 定义，机检覆盖「完全重复、死用例、无断言、自证、弱 mock」之外的四类人工判据（自证式用例、双结果放行、弱断言、命名与内容不一致）；整改 23 例（1 例重复合并）：安全基线 3 例自证式改为触生产（缓存写入器 / LLM 源码静态守卫 / HTML 模板扫描）、文件系统边缘 4 例双结果放行改为按契约断言、配置崩溃清理 1 例补 `assertRaises`、弱断言 11 例补足语义、启动向导 2 例合并、2 处死变量清理。记录见 changelog / 台账 rf-851~rf-855。

## `plan-205` CLI 配置面补齐（config 子命令 + 章节/匿名化一次性覆写）——已完成，待发布归档

**状态**：CLI 补齐与 TUI/Web 配置面同源的命令行入口——新增 `config list/get/set`（白名单 + 校验 + `.bak`，复用 `config/edit_ops.py`；`--dry-run` 只校验；调度四个字段走严格校验）与全局 `--chapter KEY=on|off` / `--anonymize MODE`（进程内覆写，不写盘，覆盖 `config.json` / `enabled_llm.*` / features 三类来源）。`--chapter` 的运行时叠加层为 `config/_runtime_overrides.py`，`get_config()` / `get_llm_config()` 返回前叠加；scheduler 归一化/严格校验上收 `config/_scheduler.py`（Web 面板与 CLI 共用）。报告追问 `[Q]` 按决策不提供 CLI 入口（对话式交互不适合命令行）。文档同步 CLI 手册 §2/§10.1/§14、配置手册与脚本参考。

## `plan-206` 报告运行观测三项整改（锚点开销 / 归因粒度 / full 提示）——已完成，待发布归档

**状态**：按最近一次真实运行（44.4s 管线，去重锚点占 18.5s）落地三项——① **rf-858** 锚点**采集保持默认开启**、写侧改为纯追加（不读旧文件；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关），跨轮重复交给校准工具按键去重，39MB 文件的加载/压缩移出报告主流程（采集、诊断数据持续积累，报告零读取开销）；② **rf-859** `perf_history.breakdown` 补数据准备九项与新闻源抓取/去重与关联/锚点维护/事件窗装配子计时；③ **rf-860** 新增 `llm_report_unavailable_reason()`，full 在 LLM 未配置或章节全关时显式提示「按不含 LLM 内容生成（full 等同 both）」。回归覆盖锚点默认采集/批内去重/跨轮由校准去重、新闻子阶段、LLM 不可用判定与 full 提示；评估默认顺带压缩锚点（`--no-compact` 关闭）；文档同步技术设计、需求（R-DATA-09 / R-PERF-09）、脚本参考与 CLI/TUI 手册。

## `plan-207` 清理旧配置形参兼容——已完成，待发布归档

**状态**：移除 10 个功能开关访问器（`is_enable_data_quality` / `candidate_compare` / `stock_fundamentals` / `market_sentiment` / `cost_lots` / `valuation_percentile` / `market_temperature` / `industry_beta` / `fund_purchase_limit` / `cost_position`）的 `config` 形参——该参数在功能开关迁入 `features.json` 后已不参与取值，仅为旧调用签名保留；同步更新 26 处调用点与测试，删除「旧 config 入参被忽略」的兼容用例。保留当前规格内的降级回退（快照缺市值按 R-EVO-02 回退成本口径、LLM flat 单凭据模式）——它们不是旧数据兼容。

## `plan-208` 跨模块导入面收窄 ✅

**完成（2026-10-24，v0.15.2；2026-10-30 补录）**：`config/cache/cli/providers` 公共面移除私有 `__all__`、兼容转发注释清零、生产代码跨包私有导入清零；`providers/_utils.py` → `providers/utils.py`。条目发布时未随节迁档（台账节被直接删除），补录以 `archived_changelog.0.15.x.md` v0.15.2 段为准。

## `plan-209` TUI 显示模式统一 ✅

**完成（2026-10-24，v0.15.2；2026-10-30 补录）**：状态标签收敛到 `switch_panel.status_text`、`truncate_display` 改 ANSI 感知并补 `RESET`、`DESIGN-TUI.md` 新增「Display Modes」契约。同上，发布时未入档，按 v0.15.2 changelog 段补录。

## `plan-210` 报告重复运行耗时优化（LLM / 新闻） ✅

交付：同进程连跑四份，`LLM+新闻` 138.7s → 0.0s；历史走势并发取数改按输入顺序汇总（内容可复现）。

## `plan-211` 数据源降级与告警分级（行业资金流向 / K 线） ✅

交付：`warnings_count` ≤5、`Unknown thscode` 0；行业资金流向失败负缓存 + 单条告警；备用源评估＝免 key 无可靠第二源。

## `plan-212` 报告级 LLM 缓存状态隔离与指纹审计 ✅

交付：报告边界、用量 delta、指纹组件审计落地；连跑三份无指纹误变、无上一轮残留。

## `plan-213` 发布标题剥掉裸版本前缀 ✅

**问题**：`publish --title "v0.15.4 —— …"` 拼出 `release: v0.15.4 —— v0.15.4 —— …`（v0.15.4 发布实测）；`normalize_release_title` 只剥 `release: v… —— ` 一类。
**动作**：补裸版本前缀（含 `-dev` 后缀）剥离；`v2 —— …` 这类非版本数字串不误伤。
**验收**：`normalize_release_title("v0.15.4 —— 主题") == "主题"`，release 提交标题只出现一次版本号。

## `plan-214` devbump 分步耗时埋点 ✅

**问题**：`logs/release.jsonl` 中 devbump 的 `steps` 恒空（只有总墙钟 14.1s），无法区分版本改写 / 一致性收敛 / 推送各占多少，跨版本对拍缺一环。
**动作**：按 `_timer().mark_elapsed()` 补「版本全链改写 + 一致性收敛 / 迁档占位清理 / 切版提交 / 推送 dev / 发布闭环校验」五步，与其余发布命令同口径。
**验收**：devbump 后台账 `steps` 非空且步骤可读；回归用例断言步骤名存在。

## `plan-215` 发布闭环机器校验 ✅

**问题**：CLAUDE.md 的「每次正式发布都必须把 dev 合并入 master 并推送、不得只打 tag 不更新 master」此前只靠人看终端，没有任何机检；tag 打错分支 / master 未跟版都要等到下版才发现。
**动作**：`devbump` 收尾新增闭环校验：`tag vX` 存在且在 master 历史内（`merge-base --is-ancestor`）、`master:<constants>` 的 `APP_VERSION == X`、当前分支为下一开发版；不一致即硬失败并给出逐项修复提示。无 tag 仅告警（`--no-push` 试跑 / 非发布库不误拦）。
**验收**：三类缺口（tag 不在 master、master 版本不符、dev 未切版）均退出 1 且打印具体项；闭合时打印「发布闭环闭合」；回归用例覆盖三种缺口与无 tag 只告警。

## `plan-216` LLM 预检缓存键与写侧不同源（每份报告四模块全判 miss） ✅

**缺陷（已实证）**：chain 模式下写侧（`skeleton._build_provider_cache_key`）会在裸键后追加 `_{provider}`，而编排层预检 `_compute_module_cache_info` 只拼 `llm_{模块}_{指纹}`——预检读的短键文件永远不存在。后果：① 每份报告四模块全判 miss、全部派发进线程池（真正命中发生在 skeleton 的第二次预检）；② perf `cache_misses` 恒为 4，用户看到的就是「缓存没起作用」；③ 节省派发/渲染开销的预检优化完全失效。

**动作**：`_compute_module_cache_info` 的键统一经 `_build_provider_cache_key(...)` 构造（与写侧同一函数），不链式配置时不加后缀（旧缓存不整体失效）。

**验收**：`test_orchestrator_precheck_key_matches_write_side`（链式配置键尾为 `_p1`，单 Provider 配置不带后缀）+ `test_orchestrator_precheck_hits_skeleton_written_cache`（写侧落盘键与预检键逐字节相等）。

## `plan-217` 历史取数单轮复用 + 空结果短路（hithink A 股历史无效请求风暴） ✅
**缺陷（实测）**：单份报告内 `[history_stock] 尝试 hithink` 出现 110 次、其中 99 次「返回空数据」；同一代码按 20/35/90/260/365/400 多窗口分别重走缓存合并与 provider 链路，单轮白耗 30~44s，且 hithink 对 A 股历史结构性不覆盖。

**动作**：`chain_incremental` 新增单轮状态（报告边界清空）——① 窗口复用：按（chain, code）记住本轮已取到的最大窗口，≤ 已取到的直接截尾返回；② 空结果短路：同一（chain, provider）连续 5 次空结果 → 本行余下请求跳过，只留一条汇总 WARNING（与「网络故障熔断」区分：凭据/空结果属结构性不覆盖，不计熔断）。报告入口 `_run_scope.start_report_run` 同时重置。

**验收**：`TestRunHistoryMemo`（小窗口走 memo、大窗口只补取一次、reset 清空）+ `TestEmptyResultStreak`（连续空达阈值后跳过、成功即清零）；conftest 增加 autouse 复位防串味；full 报告复测 hithink 尝试数应从 110 降至 ≤5。

## `plan-218` 提示词中的可变计数导致缓存键每轮翻新 + 审计基线被误清 ✅

**缺陷（日志实证）**：同一进程连续三份 full 报告（同持仓/同交易日），命中数 0/6 → 3/6 → 4/6，未命中的模块键尾差异集中在两处：①【数据质量详细状态】与【数据质量降级】段写入了失败**出现次数**（`连接失败: ff_sector_flow(1次)`、`累计 3 次`）——次数由重试轮次/网络抖动/跨会话累计决定，与模型要判断的「哪些源本次不可用」无关，却每轮都变，使 `health_check` / `expert_review` 键同变；② 指纹组件审计基线被接进报告边界清空，导致审计恒输出「无变化」，把定位能力也一起弄丢了。

**动作**：两段数据质量文本改为**去重后按源排序、不输出次数**（语义保留「哪些源不可用」；次数由重试轮次与网络抖动决定，与本轮可得数据无关）；指纹审计基线保留在进程级（跨报告比对才有意义，报告边界只重置历史取数单轮状态）；预检结束新增一行 INFO「命中 N/M；未命中：…；重新生成跳过：…」。

**验收**：`test_block_stable_when_failure_multiplicity_differs` + `TestDegradationBlockNoCrossSessionCounts`（次数变化不改变块文本）+ `TestPrecheckSummaryLog`（三类可区分）+ `test_keeps_fingerprint_audit_baseline_across_reports`；重启后同一数据连续两份报告的「指纹组件变化」行应为空（除真实行情/账本变化）。

**实测**：`src/test/unit/llm/test_report_sequence_cache.py` 在同一进程内调用真实 `generate_all_llm`（LLM 全 mock、缓存目录隔离）连跑三份——第 2/3 份**预检层** 4/4 命中，第 3 份 self_review 亦命中；失败事件条数与累计次数变化不影响命中；指数变化时 `global_macro` 重算。四例均以缺陷版代码验证过可捕捉（改回旧实现即红）。

**完整矩阵**：`src/test/unit/llm/test_cache_matrix.py`（21 例，含提示词/模型/精简模式入指纹）逐模块变换各模块自己的入参，断言「该重算的必重算、其余必命中」——指数（global_macro + 含竞争语境的 expert_review）/量化指标（expert_review）/穿透资产（expert_review、health_check、penetration_deep 三处）/历史风险信号/新增数据源失败（health_check）；另覆盖强算与模块级强算、Provider 切换不复用他方缓存、单 Provider 配置仍命中、温度变化换键、`cache_enabled=false` 跳过读、TTL 过期重算、跨进程重启后磁盘缓存仍命中、串行后置模块（生成后自检、持仓变动复盘归因）产出未变则命中、产出变则重算。用例已做变异验证（如从 expert 指纹移除 metrics、把失败次数渲染改回旧式）——对应用例必变红。

**缓存测试域归位（标记与抽离口径）**：仓库**没有** `unit_cache` 标记——`unit/cache` 目录按 `scripts/check-test-markers.py` 期望表归 `unit_core`（缓存基础设施无专属域）。故分两层：① `src/test/unit/cache/test_cache_engine_scenarios.py`（14 例，`unit_core`）测缓存引擎硬契约——TTL 边界、压缩往返、损坏载荷（含截断 gzip）、原子并发写、键版本升级、目录不可写；② `src/test/unit/llm/test_{report_sequence_cache,cache_matrix,cache_real_config}.py`（38 例，`unit_llm` + **横切 `unit_core`**）测 LLM 语义。加 `unit_core` 的理由：P0 `dev-verify` 的选择面不含 `unit_llm`，只标 llm 域会让这批回归只在 P1 才跑。

**逐用例实证**：真实配置链路（不 patch 配置读取）验证 v2 嵌套 + 多链 → 预检键与磁盘文件名交叉比对同源；单 Provider 升级兼容；损坏缓存/截断 gzip/大载荷 gzip/并发双报告/调用失败不落缓存；故障转移时按**实际** provider 落盘、下一轮预检不误复用；模块禁用不生成不落盘；命中正文与首次一致（页脚按设计追加缓存标记）。

**遗留（设计使然）**：`self_review` 内容寻址于其余模块产出，任一上游重算即 miss；`health_check` 在当日盈亏或数据源可用集合实际变化时重算。

## `plan-219` 缓存 TTL 分层收敛 ✅

交付：TTL 收敛为「注册表默认 + config 稀疏覆盖」两层，且 TTL 与缓存键无关（读侧/清理侧同值）；契约 24 例。

## `plan-220` 文档 TTL 数字的防漂移守卫 ✅

交付：`datasource.md` 的 LLM 缓存 TTL 行按前缀反查注册表校验；`faq.md` 数字列举改为引用配置文档。

## `plan-225` 缓存 TTL 机制收敛 ✅

**完成（2026-10-25，v0.15.8；2026-10-30 补录）**：盘中敏感性改为注册表数据属性 `DataModuleDef.market_ttl`（`price`/`index` = 30s），`config.market_hour_aware` 退役，配置只保留 `market_hour_ttl` 数值覆盖。按 v0.15.8 changelog 段补录。

## `plan-226` 财报类缓存节奏对齐披露周期 ✅

**完成（2026-10-25，v0.15.8；2026-10-30 补录）**：`report`/`fin_indicator` TTL 30 天 → 1 天、`dividend` 30 天 → 7 天，`report_doc` 保持 30 天。按 v0.15.8 changelog 段补录。

## `plan-228` 决策/信号账本按龄保留 ✅

**完成（2026-10-25，v0.15.8；2026-10-30 补录）**：`core/jsonl_store` 新增 `prune_jsonl_by_age`（按龄裁剪 + `keep` 谓词），决策账本与信号账本追加后按 730 天裁剪，已结算事件永久保留。按 v0.15.8 changelog 段补录。
