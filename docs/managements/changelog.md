# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.0]**（2026-11-04）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.1-dev] - 开发中（未发布）

### 修复

- **LLM 缓存指纹分界：只锁结构与口径，行情/时效类交 TTL（`rf-1040`）**：连续两轮「持仓与市值完全相同」的报告仍 4/4 全 miss，预检归因 `fingerprint_changed=4`（不是 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、A/美股指数、竞争语境块、量化指标、历史风险信号、穿透市值与占比）与时效数据（事件窗分歧例块、调仓纪律回放块：新闻 15 分钟一刷且每行带收益/超额浮点）全数锁进键，使 4h（`expert_review`/`health_check`/`penetration_deep`）与 24h（`global_macro`）TTL 实际退化为分钟级。改法：`build_llm_fingerprint` 入键收窄到持仓成本（`name/code/cost`）+ 分类**结构**（新增 `extract_stable_categories`：类型→排序品种集，不含市值/盈亏）+ 穿透品种集与 `sector`（新增 `extract_stable_penetration(include_sector=True)`，`full` 口径保留为诊断专用，`risk_signals_of` 降为诊断口径）+ 两个版本盐；行情类参数保留形参但不再参与哈希。四个模块构造器同步剔除竞争语境/量化指标/风险信号，`global_macro` 改为持仓+分类结构（并补传 `holdings_details` 保证预检/写两侧同源）；事件窗分歧例块与调仓纪律回放块出键（仍进提示词），自检与辩论三键同口径；`skeleton` 新增 `_APPENDIX_EXCLUDED_SECTIONS`，`global_macro` 不注入事件窗分歧例块。文档同步：requirements（R-HCR-05/R-SR-04/R-EW-06 改「口径类进键、时效类交 TTL」）、technical §3.4 指纹分界与失效语义；单测七份同步（`test_module_fingerprint` / `test_cache_fingerprint_alignment` / `test_cache_matrix` / `test_cache_sequence_matrix` / `test_report_sequence_cache` / `test_fingerprint_baseline` / `test_fingerprint`），事件窗与回放注入用例改为断言「时效块不换键」，并新增 `test_market_derived_inputs_do_not_change_fingerprint` ×4 与 `test_structural_inputs_change_fingerprint` ×4 锁定分界。


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
