# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.19.1]**（2026-11-28）——已发布版本段随发布移入 [`archived_changelog.0.19.x.md`](../archive/v0.19.x/archived_changelog.0.19.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.19.2-dev] - 开发中（未发布）

### 修复
- **包门面与子模块的顶层导入环（rf-1268）**：`config` 门面 ↔ `_core`/`_llm_settings`、`llm/fact_checker` 门面 ↔ `_numerical` 两处顶层互相导入，导入成功与否取决于包初始化执行到第几行——调整 `__init__` 顶层导入顺序即可变成 `ImportError`，且报错点与病因相距很远。子模块侧改为 `import 包.子模块 as 名` 直接引子模块，环消除；新增 `src/test/unit/core/test_import_cycles.py` 守卫（按顶层导入图求强连通分量，函数内延迟导入不算——那是刻意打断环的手段），已验证旧形态会被判红

### 变更
- **板块分类原语下沉 `core/sector.py`（rf-1269）**：行业关键词表加载（缺文件/损坏降级）、只读访问器、热重载与「名称 → 板块」判定整块移出报告层，`report/` 与 `analysis/` 两侧共同消费 core——纯计算层不再反向依赖报告层；分层例外表与 `technical.md` 的存量例外表各减 2 行
- **持仓快照存储下沉 `core/snapshot_store.py`（rf-1270）**：保存/加载/列表/清理与命名空间隔离整体迁入 core（只依赖 `core` 与 `schemas`，零报告侧耦合），`analysis/` 三处、`web/`、`scripts/` 的读快照路径改指 core；纯存储用例按被测模块归位 `unit/core` 并按新模块名重命名；分层例外表与存量例外表各减 3 行

- **纯解析/派生原语下沉 `core/`（rf-1271）**：`fee_schedule_model`（申赎费率表）、`financial_statement_derive`（三表合并派生）、`financial_indicator_extract`（财务指标全文解析）、`drawdown_events`（回撤事件与窗口下限常量）四个纯计算模块从 `analysis/` 整块迁入 `core/`——`fetcher/`、`providers/`、`config/`、`report/` 复用同一口径时不再反向依赖纯计算层；用例随之归位 `unit/core`，分层例外表与存量例外表各减 7 行

### 测试
- **新增顶层导入环守卫**：`src/test/unit/core/test_import_cycles.py` 两条用例（全图无环 + 包门面与子模块不互导），只断言结构关系，拆包/新增模块自动跟随

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.19.x.md`](../archive/v0.19.x/archived_changelog.0.19.x.md) — v0.19.0 ~ v0.19.1（2026-11-27 ~ 2026-11-28）
- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.7（2026-11-12 ~ 2026-11-26）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
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
