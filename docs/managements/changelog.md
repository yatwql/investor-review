# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.7]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.8-dev] - 开发中（未发布）

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


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.7（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
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
