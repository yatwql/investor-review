# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.0]**（2026-11-04）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.1-dev] - 开发中（未发布）

### 修复

- **LLM 缓存指纹分界：只锁结构与口径，行情/时效类交 TTL（`rf-1040`）**：连续两轮「持仓与市值完全相同」的报告仍 4/4 全 miss，预检归因 `fingerprint_changed=4`（不是 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、A/美股指数、竞争语境块、量化指标、历史风险信号、穿透市值与占比）与时效数据（事件窗分歧例块、调仓纪律回放块：新闻 15 分钟一刷且每行带收益/超额浮点）全数锁进键，使 4h（`expert_review`/`health_check`/`penetration_deep`）与 24h（`global_macro`）TTL 实际退化为分钟级。改法：`build_llm_fingerprint` 入键收窄到持仓成本（`name/code/cost`）+ 分类**结构**（新增 `extract_stable_categories`：类型→排序品种集，不含市值/盈亏）+ 穿透品种集与 `sector`（新增 `extract_stable_penetration(include_sector=True)`，`full` 口径保留为诊断专用，`risk_signals_of` 降为诊断口径）+ 两个版本盐；行情类参数保留形参但不再参与哈希。四个模块构造器同步剔除竞争语境/量化指标/风险信号，`global_macro` 改为持仓+分类结构（并补传 `holdings_details` 保证预检/写两侧同源）；事件窗分歧例块与调仓纪律回放块出键（仍进提示词），自检与辩论三键同口径；`skeleton` 新增 `_APPENDIX_EXCLUDED_SECTIONS`，`global_macro` 不注入事件窗分歧例块。文档同步：requirements（R-HCR-05/R-SR-04/R-EW-06 改「口径类进键、时效类交 TTL」）、technical §3.4 指纹分界与失效语义；单测七份同步（`test_module_fingerprint` / `test_cache_fingerprint_alignment` / `test_cache_matrix` / `test_cache_sequence_matrix` / `test_report_sequence_cache` / `test_fingerprint_baseline` / `test_fingerprint`），事件窗与回放注入用例改为断言「时效块不换键」，并新增 `test_market_derived_inputs_do_not_change_fingerprint` ×4 与 `test_structural_inputs_change_fingerprint` ×4 锁定分界。


### 变更

- **智囊团复盘方向约束收敛为一句（去掉叠用的对冲措辞）**：情景段原有三处同义且互相抵消的指令——条件化动作要求、随情景段追加的「不操作是合法结论」出口、以及品种引用段「除非不对具体品种动手…无需勉强引用品种」的口子，与系统提示 Phase 3「给出量化调仓方案」并存时只能产出官样回避口吻。改为单源一句：`MANDATE_CONDITIONAL` 写清「满足什么条件动手、动什么」，条件不成立或信息不足则直接写「不操作」并点明所缺数据；`scenario_mandate()` 改由两条情景路径（标准 fallback / 配置条件情景）共用一处追加，品种引用口子压成一句、不再复述「不操作」；系统提示 Phase 3 补「结论为不操作时写明理由与触发条件」使两处口径同向。
- **智囊团专家须具名**：召集令只要求「挑 5 位流派对立专家并标明立场」，模型常以 A/B/C/D/E 或「专家1/2」占位，可读性差。系统提示补「姓名式称呼 + 机构/头衔，禁止 A/B/C/D/E、「专家1/2」或「多/空」这类占位名，同一专家全篇用同一称呼」。
- 上述两项均为提示词静态文案改动，`PROMPT_SCHEMA_VERSION` 递增 `rate-caliber-2 → 3` 一次性换键（四可回写模块与自检键同步重算，属预期）；`test_module_fingerprint` 的接线前基线随盐刷新；单测补「对冲措辞只出现一处」「专家具名禁止占位名」断言。
- **`decision_basis` 开关从 `[C]` 章节内选项移到 `[S]` 机制与质量组**：判断依据是行动建议章的**章内内容增强**、不增删章节，放在章节显隐面板的 5.1 子项位置与语义不符。注册表 `group` 改 `mechanism`（`[S]` 新增 15 号，其后四项顺延 16~20），`chapter_registry` 的 `enable_action.sub_items` 清空（`[C]` 5.1 消失，章节内选项只剩智囊团 7.1/7.2，组内计数 3→2）；消费点、默认值、回滚语义与缓存键不变。
（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0（2026-11-04）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
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
