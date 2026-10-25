# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.7]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.8-dev] - 开发中（未发布）

- **模型定价表按官方价目刷新（2026-10-25 核验）**：补入现役型号——Claude `5.5` 家族（Fable 5.1 / Opus 5.5 / Sonnet 5.5 / Haiku 5.5）与 legacy Sonnet 5；OpenAI `gpt-6.1-sol` / `gpt-6-luna` / `gpt-6-astra` / `gpt-5.6-sol`；Gemini `3.8-flash` / `3.1-pro`；Kimi `k3.1-pro` / `k3.1-pro-highspeed`。移除已下线或不在官方价目表的 `gemini-2.0-flash` / `gemini-3.5-flash`。DeepSeek 单价经核验未变。
- **费用展示改为按模型原生币种**：`MODEL_PRICING` 每条带 `currency`（Anthropic/OpenAI/Google 为 USD，DeepSeek/Kimi 为 CNY），`estimate_cost` 出对应符号（`$`/`¥`），代码内**不再有任何用于展示的汇率折算**。模型同时提供多币种价时以配置币种（`llm_pricing_ref.json → currency`，默认 CNY）为主，用条目 `alt` 子表提供该币种价即可切换。
- **跨币种金额分组并列、永不相加**：会话累计与报告合计改用「币种 → 金额」桶（`llm.pricing.add_cost/merge_costs/format_costs`），显示形如 `¥0.0123 + $0.0045`；`session_usage` 的 `total_cost`/`currency` 字段由 `costs` 取代，perf 记录写 `cost_by_currency`。
- **日预算改为逐币种上限**：`daily_cost_limit` 支持对象形态（`{"CNY": 5, "USD": 1}`，默认 `{}` 不启用）；判定超限时按内部汇率表 `FX_TO_CNY` 把各币种支出折算到预算币种（**仅用于判定，不影响展示金额**）。单值写法视为只对显示币种生效并记 INFO 提示。
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
