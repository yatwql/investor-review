# 计划归档 — v0.15.x

> 归档时间：2026-10-24（v0.15.0 发布，本系列首份）；2026-10-24 v0.15.0 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.15.x 开发期完成项（含 v0.15.0）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## ✅ `plan-195` Web 配置面契约（domains / labels / blocks）——已实施，待发布归档

服务端下发 `domains`（五域 → 有序块清单）与 `labels`/`descriptions`/`defaults`/`needs_hint` 元数据、`logging`、`reference`；前端按域渲染 + 块渲染器分派，零中文表。机检：`test_config_surface_contract`（17 例）；记录见 changelog 配置重构第 10 轮。

## ✅ `plan-196` Web 配置面交互与状态——已实施，待发布归档

工具条统计（基准 = 服务端 `defaults`）、关键词筛选、域导航与 `#domain-<key>` 深链、块计数、窄屏单列；保存语义分即时（失败回滚）与显式（失败保留输入）两类。机检：`test_web_config_interaction`（17 例）；记录见 changelog 配置重构第 11 轮。

## ✅ `plan-197` 配置重构的文档与契约登记收口——已实施，待发布归档

手册与管理文档全量对齐当前结构（主菜单 14 项四组、Web 五域分区、`[G]` 七项四组、`[D]` 四项），抽检 `[D]`/`[G]`/`[S]`+`[C]` 三处与代码逐字一致；契约档结构守卫绿。记录见 changelog 配置重构第 12 轮。

## ✅ `plan-198` 配置重构质量门禁全量——已实施，待发布归档

五道闸口全绿：`verify` 11318 通过 / 0 失败、十守护零 finding、性能门禁 basic **0.48s ≤ 60s**、`portability` 2 探针通过（`LC_ALL=C` + 隐式编码严格档）、`ruff check` / `format --check` 零告警。本轮修正两处真实缺陷：计价懒加载覆盖显式重载（`rf-837`）、`test_json_comments` 子进程缺显式编码（portability 探针拦下）。记录见 changelog。
