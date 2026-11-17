# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.2]**（2026-11-16）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.3-dev] - 开发中（未发布）

### 变更

- **纪律补机检：自审修复须先登记台账**：`check-doc-drift` 新增第 29 项——本周期 changelog 出现「自审/自查/整改/审计/核对」类条目、而 `review-findings`「开发期已修复」表零 rf 行时报 finding，把「改了代码没立 rf」的漏登从发布时提前到提交阶段（配合 3 条用例，对应 `rf-1154`）；另修台账头部编号源「已用最大 rf-1135」的陈旧值（实际 1153）。
- **降级可观测：静默 fallback 补日志**：近 83 小时窗口内 6 处按设计降级但无日志痕迹的 `except` 补 `logger.debug(exc_info=True)`（决策书注册表/匿名化模式、会话用量埋点、渲染因子名映射、push2 限流观测），降级行为与返回值不变，只在排障时能追到环节（`rf-1155`）。
- **渲染前置装配补阶段契约用例**：`report/_html_render_context.py` 先前面板视图/数据源状态/渲染上下文三层装配无直测，新增 `test_html_render_context.py`（10 条：缺席降级、四元组位序与转发入参、`details` 优先于 `holdings`、因子名导入失败升 debug）（`rf-1156`）。
- **评审台账清理**：删除 P2/P3 两处重复的空表头。
- **渲染前置装配入参按来源域分组**：`_prepare_render_context` 的 30 个关键字入参收为两组 dataclass（`_VisibilityInputs` / `_DataSourceInputs`）加 `details`，签名降至 3；`_build_data_source_bundle` 同收为单组入参，`write_html_report` 调用点改按域构造——改派生量的入参不再靠位置对齐，只需在所属组里加字段（`rf-1157`）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.2（2026-11-12 ~ 2026-11-16）
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
