# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.7]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.8-dev] - 开发中（未发布）

- **缓存 TTL 机制收敛（plan-225）**：盘中敏感性改为注册表数据属性 `DataModuleDef.market_ttl`（`price`/`index` = 30s），`config.market_hour_aware` 退役（写入时校验告警并忽略），配置只保留 `market_hour_ttl` 数值覆盖；`get_ttl` 在"盘中覆盖与 `cache_ttl` 冲突"时打一次性 INFO，把静默失效变可见。两个缺失探测负缓存（`datasink_probe_miss` 12h / `report_symbol_miss` 6h）登记为正式缓存类型，读侧 TTL 与 `cleanup_expired` 判定同源。契约测试覆盖：盘中 30s/盘后静态 TTL 双向、盘后不白打上游、退役键无扩权、负缓存按 6h/12h 清理、全量类型 TTL 为正；另补三份缓存契约测试——TTL 业务矩阵（时段 × 类型 × 覆盖层、读写清理同源、同日两次报告/收盘后/LLM 边界）、价格缓存新鲜度门禁（盘中价不得当收盘价、QDII T-1）、版本戳迁移与逐类型清理（非当前戳不可读但仍按类型 TTL 清理）。
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
