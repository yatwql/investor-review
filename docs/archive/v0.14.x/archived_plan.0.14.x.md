# 计划归档 — v0.14.x

> 归档时间：2026-10-21（v0.14.0 发布，0.14 系列首份）；2026-10-21 v0.14.0 本批原表搬运；2026-10-22 v0.14.2 本批原表搬运；2026-10-22 v0.14.5 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.14.x 开发期完成项（含 v0.14.5）
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
