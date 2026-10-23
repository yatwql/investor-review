# 计划归档 — v0.14.x

> 归档时间：2026-10-21（v0.14.0 发布，0.14 系列首份）；2026-10-24 v0.14.9 配置体系重构已完成轮次（plan-186~194）迁入；2026-10-21 v0.14.0 本批原表搬运；2026-10-22 v0.14.2 本批原表搬运；2026-10-22 v0.14.5 本批原表搬运；2026-10-23 v0.14.6 本批原表搬运；2026-10-23 v0.14.9 决策不做项（plan-182）迁入
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.14.x 已完成项与决策不做项（含 v0.14.9 配置体系重构各完成轮次）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-170` 提交期 dev-verify 墙钟治理（离线桩接管等待型 sleep）✅

**完成（2026-10-21，v0.13.13-dev）**：P0 `dev-verify` 中位 37.3s 里，跨 worker `time.sleep` 累计 104.9s 全属「离线桩已声明、却仍在白等注定取不到的源」——`core/throttle.py:102` 间隔节流 31.9s、`core/retry.py:182/191` 多策略退避 26.2s、`providers/{cninfo,datasink}` 429 限速窗口 3s。动作：`_network_guard` 新增 `_NoWaitClock`（`time` 模块代理，只接管 `sleep`，`monotonic`/`perf_counter` 原样透传），`apply_offline_stubs` 用它替换 `core.throttle` / `core.retry` / `providers.cninfo` / `providers.datasink` 的**模块级 `time`**——作用域限于声明 `offline_external_sources` 的文件，测试自身 `time.sleep` 与验证等待语义的用例（`test_throttle` / `test_phase_timeout` / `test_batch::TestRateLimiter` / `test_handlers::test_queue_full_429`）不受影响，未声明离线的文件等待语义逐字节不变。效果（16 核/load 3~5 交替 3 轮）：**37.3s → 24.0s（−13.3s / −36%）**，用例数与断言强度不变（7481 passed）；并行度复核 `-n 12` 反而更慢（墙钟 27.4~29.4s、user CPU 235s vs 145s）→ 维持 `medium=50% 核数`、不加并发。剩余睡眠 57.8s 中 30s 在 daemon 线程、22.2s 属未声明离线的 provider/fetcher 用例；全局禁睡上限实测中位 22.2s，即剩余可压缩空间 ≤2s，无性价比。测试：`unit/core/test_network_guard.py` 新增 4 例（节流零等待且算式返回值不变 / 退避零等待且重试次数不变 / 代理保留真实 monotonic·perf_counter / 未声明离线时等待语义原样）+ 桩目标存在性补四个模块的 `time.sleep` 断言。

## `plan-171` 发布编排补 token 采集与统计（成本可对拍）✅

**完成（2026-10-22，v0.14.2-dev）**：发布台账此前只记墙钟，回答不了「这次发布烧了多少 token」。现每条命令记录执行环境身份（`agent`：provider/model/thinking/session_id，取自 `PI_*` 变量）与 agent 会话**累计** token 快照（`session_usage`：in/out/cache read/cache write/total/cost，取自 `PI_SESSION_FILE` 会话 JSONL 的 assistant 消息 + 非消息用量（cache_warm 等）+ compaction 三类条目，与 pi 自身统计同口径；非 agent 环境省略字段、旧台账行形状不变），命令尾行打印「本次发布累计 token」。窗口口径 = 上一次 `devbump` 之后的行，用量 = 末行累计 − 边界累计，跨会话（agent 重启归零）按正增量分段累加；采集全程容错（文件缺失/坏行只跳过），不阻断发布。测试：`test_release_archive.py::TestReleaseTokenAccounting` 6 例 + `TestReleaseAgentIdentity` 4 例。

## `plan-172` 事件窗盘中运行 100% 降级（面板长期空白） ✅

**现状与问题**：盘中运行是常态（实测 2026-10-22 三次跑均在盘中），`事件窗事件表: 可出行 0 条、降级 14 条`，14 条原因全部为「窗口超出行情范围」——`WINDOW_AFTER=5` 交易日要求事件日后尚有 5 个交易日，而新闻事件日就是当日/昨日，行情轴止于当日，右界必然越界，整条被丢弃。结果是开启 `event_window_impact` 也拿不到任何事件行，功能等于空缺。

**动作**：右界不足时按**行情轴实际可用交易日**截断计算（左右不对称即标注），事件日后可用日数为 0 才降级；事件行与口径标注显式写「事件日后 N/5 日（未满窗）」，避免读者误当完整 ±5 窗口；同步更新 `R-EW-01/02` 与双端测试

**对旧裁决的取代**：v0.12.x 设计归档 §14 曾判定「半窗截断引入第二口径」而否决，当时前提是严格口径下仍有 23 条事件可出行；现状已变（盘中运行 14/14 全空、事件表恒空）。本次不引入第二口径——统一一条规则「右端按行情轴可用交易日截断」+ 每行回显实际日数，与已采纳的「LOCF + 标注」同构；若日后严格窗前需求回升，可再评估按行过滤。

## `plan-173` thinking 模块并发 1 造成 LLM 段 88s 串行 ✅

**现状与问题**：`llm_settings.json` 的 `llm_max_thinking_concurrency=1`，而 `expert_review`(实测 51s) 与 `health_check`(37s) 均开启 thinking → 二者被信号量完全串行（日志时间轴：穿透 13:22:21 释放线程槽后体检 13:22:59 才起跑，空转 38s）。占单次报告总墙钟 183.6s 的约 20%；且信号量等待完全静默，只有看时间轴才能发现。

**动作**：① 信号量等待超过阈值（5s）时打一条 INFO（模块/已等待秒数/上限），使串行可观测；② 等待累计 ≥20s 时给出「提到 2 约可省该时长」的可执行提示，并把累计毫秒数写入 `perf_history.counters.llm_thinking_wait_ms`

**实施结果（默认值 1 → 2）**：先落地可观测（等待日志 / `llm_thinking_wait_ms` / ≥20s 提示），随后第二次真机运行给出决定性数据——智囊团 68.7s、体检 28.5s，`等待 thinking 并发槽 68.7s` 占该次墙钟 154s 的 **44%**。据此把默认值提到 2（代码默认 + 配置生成器注释 + `requirements`/`how-to-config-llm`/`llm-technical` 同步），回滚条件＝端点出现空内容重试或内容质量下降（配置改回 1，无需改码）；空内容既有「关闭 thinking 同 provider 重试一次」兜底。

## `plan-174` 发布门禁缺 changelog 待归档段非空断言 ✅

**现状与问题**：v0.14.4 归档段 `docs/archive/v0.14.x/archived_changelog.0.14.x.md` 只有 `## [0.14.4] - 2026-10-22` 一行标题、正文为空——开发期 changelog 停留于占位句「（本次发布内容见下方归档索引）」，`prepare` 把占位原样归档，`gate` 未察觉，发布记录永久缺失该版内容。

**动作**：`release.py prepare` 归档前 + `gate` 前置断言：待归档版本段必须含至少一条实际条目（`### ` 分类或 `- ` 条目），命中占位句即中止并提示先补 changelog

**实施结果**：prepare 侧（`apply_changelog_release`）拦「占位句原样归档」；gate 侧另加一道（`release_section_has_entries` 扫归档文件该版本段 + 缺文件/空段即前置中止，未跑子进程），拦旁路/人工归档。回归 4 例（有条目/只有标题/占位句/版本缺失）+ gate 2 例（空段/缺文件）。

## `plan-175` 新闻去重锚点文件只增不减（37.9 MB 且每轮全文重写） ✅

**现状与问题**：`data/calibration/dedup_anchors.jsonl` 已达 37.9 MB，越过 34 MB 自动压缩线压缩后仍 37.9 MB（键本就高度唯一）→ 压缩形同无效；而 flush 走 `append_jsonl_atomic_many`（读全文 → 整文件替换），每轮报告都要把 38 MB 读进内存再整体重写，随使用时长线性恶化。

**动作**：真 append-only 追加（进程内已加载 key 集合判重，单次 write + fsync）+ 定期 compaction（保留每组最新一条 + 近 120 天保留期）；`.bak` 备份与失败不阻断语义保持不变，补「追加写不改 inode」「压缩后体积下降」回归

## `plan-176` 数据准备阶段两处硬等待（46s 中约 47s 花费在等超时） ✅

**现状与问题**：实测 `数据准备: 46.117s`，其中 ① 基金经理档案页单请求 SSL 握手超时 **17s**（`017730` 一失败就整只「全部解析失败」）；② 东财 push2 连续 11 个代码 `Server disconnected`，逐码各自重试，13:20:42→13:21:12 累计约 **30s**。两类都是「同一源已不可用仍逐个撞超时」。

**动作**：① 基金经理档案页单请求 timeout 收紧为 8s（独立常量 `_ARCHIVE_TIMEOUT`，实测 SSL 握手挂起单请求 17s）；② push2 遇「对端主动断开」直接回落下一链路（实测断连重试只白等 0.6s，而 `eastmoney_industry_rest` 秒回）

**实施与调整**：③ 原计划的「失败码按品种类型前置过滤」经排查**不成立**——`collect_a_share_targets` 已按名称+代码双维过滤场外基金，那 5 条 `[financial_report]` 失败的真因是**章节清单缓存指向已失效文档号**（缓存自身 7.7 天陈货，datasink 404 + cninfo 拒异源），已另立 **rf-822** 跟踪（失效清单 + 告警降级），不在本项内做

## `plan-177` 缓存清理日志逐文件 INFO 刷屏且 TTL 显示失真 ✅

**现状与问题**：`cache/_cleanup.py:61` 对每个文件打 INFO，单日 **257 行**（占全天日志 7.2%），同一批文件「删除 + 预览」各打一遍，退出时那次预览（实测 35 行）无人消费；`ttl=%.1fh` 对盘中 30s 的 price TTL 打成 `0.0h`，配 `age=0.1h` 读起来像配置错误。

**动作**：逐文件明细落 DEBUG，INFO 只留汇总（含释放字节数）；TTL/age 按量级自适应单位（<60s 用 s、<60min 用 min、其余 h），盘中 30s 的 price TTL 显示为 `30.0s`

## `plan-178` 脚本性能缓存缺 `_ts` 包封被缓存引擎当古董删除 ✅

**现状与问题**：`data/cache/test_coverage_snapshot.json`（doc-drift 用例收集快照）与 `test_redundancy_facts.json`（测试冗余事实缓存）由脚本直接写裸 JSON、无 `_ts`；缓存引擎按 `now - payload.get("_ts", 0)` 算龄 → **age≈497959h（57 年）**，每轮启动清理都当过期删除，缓存优化形同虚设，并在日志里制造荒谬条目。

**动作**：脚本侧写入时补 `_ts` 包封（或在缓存引擎侧对「非 envelope 文件」跳过 TTL 判定只告警一次，二者择一并说明理由）；两条清理日志路径补回归用例（有 `_ts` 不删 / 无 `_ts` 不按 57 年虚龄删）

## `plan-179` 交易日历每次调用都读盘反序列化 ✅

**现状与问题**：`core/trading_calendar._get_trading_calendar()` 命中缓存时仍逐次 `cache.get()` → 读盘 + JSON 解析；单次报告运行实测触发 600+ 次（日志去重后仍可见密度：每条 LLM 结果行前后各一次）。开销虽单次小而累计可观，且是日志噪声的根源。

**动作**：进程内按「缓存文件 token（mtime/size）+ TTL 未过期」做 memo，命中直接返回同一 `set`；缓存文件被重写或跨日自动失效；并发路径沿用既有 `_TRADING_CALENDAR_AKSHARE_LOCK` 语义，补「二次调用不重复读盘」回归

## `plan-180` 事实校验自动修正次数无跨期观测 ✅

**现状与问题**：单次运行 `事实校验自动修正 5 处`（智囊团 3、体检 1、穿透 1，如 `29.6%→12.5%`、`5%→-32.2%`、`101.75%→237.4%`），说明模型对「收益率口径」的理解偏差稳定复现；但修正次数与模块分布未进 `perf_history`，无法看趋势、也无法判断提示词改动是否有效。

**动作**：修正次数（按模块）计入 `perf_history.counters`（`fact_fix_total` / `fact_fix_numeric` / `fact_fix_code` / `fact_fix:<模块>`），并在自检/视图里可见

**实施结果**：报告层 LLM 阶段前清零、结束后汇入 counters；`doctor` 运行台账行在最近运行有修正时追加「事实校验自动修正中位 N 处」（为 0 时不刷噪声）。回归 3 例（累计/无修正不计数/清零）+ doctor 2 例（中位可见/无修正不刷）。

## `plan-95` 生成完成后无一键打开 ✅

**现状与问题**：`finish_report` 仅错误摘要 + 耗时排行 + 按任意键；全仓无 `webbrowser`/`os.startfile`/`xdg-open`——生成完仍要手动进目录找文件（HTML 路径虽有打印但不可直接操作）

**动作**：收尾打印本次产物路径清单 + 询问「按 O 打开输出目录」（跨平台 start/explorer/xdg-open，失败回退打印路径不报错）；Web 侧已有下载入口不受影响

## `plan-183` 报告产物「定位/打开」能力三渠道不一致 ✅

**现状与问题**：TUI 生成后打印产物清单并支持 `y` 打开目录与报告（`tui/report_artifacts`）；CLI 生成完**不打印**产物路径（只有 `--output` 参数），用户需自行拼路径；Web 只有下载链接、无「打开输出目录」入口。三个渠道对「产物在哪、怎么看」说法不一。

**动作**：① CLI 收尾打印产物清单（定位下沉 `core/artifacts`，与 TUI 同一事实；不做「是否打开」交互，避免脚本场景被阻塞）；② Web 结果区每个产物旁给出可点击复制的服务端绝对路径（浏览器与报告不同机，「打开目录」无意义）；③ 补「CLI 打印 / TUI 可打开 / Web 可复制」的渠道差异说明

## `plan-184` `llm_settings.json` 关键调优项无任何渠道可编辑 ✅

**现状与问题**：本轮把 `llm_max_thinking_concurrency` 默认改为 2，并把「端点偶发空内容 → 改回 1」写成回滚手段；但 Web 配置面板与 TUI `[S]` 只暴露 `enabled_llm` 与 features，**调优项（thinking 并发/总时间预算/日预算/重试/超时）只能手改 JSON**——用户按提示回滚时要开编辑器找键，且无校验。

**动作**：把这批「用户可以合理调整」的键纳入 `config/edit_ops` 共享白名单（含取值范围与非法值提示），Web 面板与 TUI 配置面板同时出现（同一白名单驱动，与功能开关注册表的「唯一事实来源」纪律同源）；每项带一句「什么时候该改」的说明（如 thinking 并发：端点偶发空响应时改回 1）；补「三渠道都能改同一键且校验一致」用例

## `plan-181` CLI 缺「数据源健康历史」视图（TUI `[H]` / Web `/api/health/history` 已有） ✅

**现状与问题**：健康历史（最近 10 次采集的成功/失败源与降级原因）在 TUI 是 `[H]`、Web 是 `GET /api/health/history`，CLI 只有 `check-sources`（当前态快照）——同一事实在 CLI 侧不可得，排查「昨天那次为什么降级」只能靠翻 `data/state/` JSON 或日志。

**动作**：CLI 增 `health-history` 子命令（`--limit` 默认 10、`--json`），渲染委托 `core/perf.summarize_health_history`（TUI/Web 同源，不新写聚合）；无需 config（配置损坏仍可查）

## `plan-182` CLI 缺「报告对话式追问」入口 ❌ 决策不做

**现状与问题**：`report_qa` 的会话内多轮追问在 TUI（`[Q]` 文本循环）与 Web（`POST /api/qa/ask`）可用，CLI 无入口——自动化/脚本场景无法对当期报告提问，三渠道能力不一致（该功能默认关，开关与用量口径已在 `qa/session.py` 统一）。

**决策（不做）**：追问的产品形态是「看报告 → 就地追问 → 连续追问」，CLI 的一次性命令/管道范式与之不匹配——要复刻就得引入交互式 REPL（与 TUI 重复）或把多轮状态塞进命令行参数（用户负担反而更大）。保留 TUI/Web 两个自然入口，CLI 侧不提供；如需脚本化问答，走 Web 的 `/api/qa/ask`。

## `plan-186` 功能开关按内容位置分八组并转出域模型 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 1 轮）**：功能开关从「四组作用域」改为**八组内容位置**（持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 呈现与交互 / 机制与质量 / 独立章节与回放 / 章节内选项），注册表条目与纯视图（分组过滤、实验清单、默认值派生）从 `config/features.py` 转出为 `config/_feature_registry.py`（单向依赖：运行时 → 注册表，原模块 re-export 保持导入面不变）；新增 `GROUP_DOMAIN`（组 → 五域）、`DOMAIN_ORDER`/`DOMAIN_LABELS`/`DOMAIN_HINTS`、`PANEL_GROUPS`（每面板只渲染自己的组、每组恰属一个面板）与 `FeatureSwitchDef.needs_hint`；`doctor_check` 开关移除（系统自检恒上屏）。验收：`GROUP_DOMAIN` 键集 = `GROUP_ORDER`、`PANEL_GROUPS` 覆盖完整性、组归属逐项断言。

## `plan-187` JSONC 注释契约（统一剥离器 + 写入保注释） ✅

**完成（2026-10-24，v0.14.9-dev，重构第 2 轮）**：新增叶子模块 `core/json_comments.py`（`strip_json_comments` / `loads` / `load`，仅标准库），`config/_comments.py` 改为再导出——core 级读取方（logger、计价）不必导入 `config` 包，依赖不成环；五份配置文件的读取统一经该剥离器，写入改为**键级文本 patch**（改值替换、恢复默认删键、紧凑单行自动重排），读—改—写后中文分类注释与逐项说明保留。回归 18 例：字符串内 `//` 与 `/* */`、转义引号不误伤、五份样本读取、round-trip 保注释、叶子模块导入边界。

## `plan-188` LLM 配置 v2 嵌套结构与默认生成器 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 3 轮）**：`llm_settings.json` 落盘改为 schema v2 嵌套结构（`defaults` / `modules` / `runtime` / `advanced`），新增 `config/_llm_schema.py` 负责版本校验（缺失或 ≠2 拒绝加载并提示删除重生成）、三层缺省合并、`flatten()` 展平与 `apply_flat_updates()` 反展平、未知段/键保留与保注释写回；对外契约仍为扁平键，`llm/` 包零改动；默认生成器输出带分类注释的 v2 JSONC，扁平默认值由 v2 展开派生（单一来源）。

## `plan-189` LLM 参数范围校验 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 4 轮）**：`config/_validation_llm.py` 新增 `LLM_PARAM_RANGES`（temperature / max_tokens / timeout / thinking.budget / effort 枚举 / 辩论合成温度与预算超时）与 `param_violation()`（文案含键名 / 当前值 / 合法范围）；加载路径经 `sanitize_document()` 越界回落出厂默认并逐条告警（只改内存视图、不改写用户文件）；面板写入统一拒绝，非法值不落盘。回归 17 例：八参数表驱动（合法 / 越界 / 类型错）、加载回落且不改写文件、面板拒绝与写后不落盘。

## `plan-190` 生成参数入指纹 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 5 轮）**：`llm/module_fingerprint.py` 新增 `generation_params_suffix(module)`，把模块温度 / 输出上限 / 思考开关与预算强度并入指纹，缓存 / 并发 / 重试等与生成无关项不参与（避免无谓失效）；七个构造器（含辩论正反与综合）全部接入，辩论综合另并入合成温度；预检侧与写侧共用同一构造器（同源由结构保证），配置不可用时后缀为空、存量缓存不整体失效。回归 15 例。

## `plan-191` 计价参考独立成文件 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 6 轮）**：新增 `data/config/llm_pricing_ref.json`（`version` + 策略 + 逐模型覆盖）与 `config/_llm_pricing.py`（读取 / 校验 / 逐模型合并 / mtime 缓存 / 中文注释默认生成器），`llm/pricing.py` 数据源切为该文件且 `PRICING_MERGED` / `reload_pricing` 接口不变；合并口径为「内置价为基础价、文件只覆盖出现的模型与字段」，文件缺失仅用内置价、单条非法告警跳过、版本不符拒绝加载并提示重新生成（内置价兜底，报告仍可生成）；`pricing` 从 `llm_settings.json` 移除。

## `plan-192` 日志配置独立成 logger.json ✅

**完成（2026-10-24，v0.14.9-dev，重构第 7 轮）**：新增 `data/config/logger.json`（`version` + `file` / `console` / `viewer`）与 `config/_logging.py`（读取 / 校验 / 写入，加载与面板共用范围表，写回文本 patch 保注释）；`core/logger.py` 启动时内联读取（不导入 config 包），按配置创建控制台 / 轮转文件 handler；环境变量优先级更高；日志目录不可写时告警并降级为仅控制台；非法级别 / 越界数值 / 含 `..` 路径一律加载告警回落、保存拒绝且不落盘。

## `plan-193` TUI 菜单与分层 ✅

**完成（2026-10-24，v0.14.9-dev，重构第 8 轮）**：主菜单收敛为 14 项四组（生成 E/B/L/W · 数据 Q/1/2/3 · 配置 P/S/G/R · 诊断 D · 退出 X），原顶层 M/I/A/V/H/T 全部下沉；新增 `[G] 全局设置` 七项（数字为主入口、字母为别名）与 `[D] 诊断与排查`（日志设置 / 运行日志 / 健康历史 / 系统自检，缺省选中系统自检，`0` 返回）；`[D]→[L]` 日志设置六项落地并即时生效（级别与轮转下次启动生效）；菜单标签统一收敛到 ≤48 显示宽，返回文案与配置入口地图同步新层级。

## `plan-194` TUI 面板内容（章节显隐与章内内容分层） ✅

**完成（2026-10-24，v0.14.9-dev，重构第 9 轮）**：新增 `config/chapter_registry.py` 作为 `[P]` 唯一事实来源（顶层章节 / LLM 章节 / 默认关闭的整章 / 关联产物四块，编号与智囊团子项 `7.1`/`7.2` 全部派生、写键经 `chapter_edit_key()` 派生并落在共享编辑层白名单内）；新增 `tui/handlers_report_chapters.py`（四块排版、键名恒显、`?编号`/`?键名` 展示来源文件与默认值、漂移标记、LLM 行费用摘要、子项闸门置灰并拒绝写入）；`[S]` 重写为六组 20 项、编号由 `features.panel_option_numbers("[S]")` 派生，只呈现章内内容组（LLM 章节与整章在 `[P]`）。同批把 `check-doc-drift` 的面板编号校验改为双面板派生校验（`[S]` 组区间 + `[P]` 块区间与子项编号 + 键名映射）。回归：章节注册表结构 13 例 + 面板 19 例。
