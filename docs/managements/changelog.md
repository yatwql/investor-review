# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.11]**（2026-10-21）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.12-dev] - 开发中（未发布）

### 新增

- **发布归档迁移固化进脚本**：新增 `scripts/_release/_ledger_archive.py`（台账与设计文档归档的纯文本变换），`release.py` 增加 `archive` 子命令并**内置于 `prepare`**——① review-findings 该版本「开发期已修复」表**原表逐行搬入**归档新节（不做摘要改写）+ 主台账留迁档占位 + 归档头部「涵盖版本 / 归档时间」与主文件归档索引区间派生；② plan.md 标题带完成标记的节整节搬入计划归档；③ `docs/plan/` 中引用编号**全部已归档**的设计文件（强信号才自动判）`git mv` 迁入版本归档子目录 `<stem>/`，并改写 changelog/plan/rf/folders/README/CLAUDE 引用与 folders 目录树条目；收尾自动 `doc-drift --sync` + `check-doc-traces` + `check-doc-links`。`--dry-run` 只报告动作、`--skip-design-docs` 只做台账、`--no-archive` 跳过。**分工**：机械动作归脚本，条目归属 / 完成标记 / 设计文件是否真完成仍由人复核（未引用任何任务编号的设计文件只列提示、不自动迁档；本版无自审条目时归档步自动放行）
- **`gate` 归档前置断言**：P2 门禁在跑 regression **之前**断言「该版本 rf 已解决表已搬空 + 归档存在对应批次节 + 版本已切发布形态」，漏做归档即刻中止（不再靠人记，也省掉一次 20s 白跑）

### 测试

- 新增 `src/test/unit/scripts/test_release_archive.py`（台账归档纯函数：原表搬运无损与幂等、占位/头部/索引派生、plan 完成节判定与在办节不外溢、docs-plan 完成判定三分支、目录树搬迁与未知条目拒绝）
- `test_release_tool.py` 扩展：prepare 自动归档端到端（台账/计划/设计文件/目录树）、`--no-archive` 跳过、`archive` 子命令（迁移+收尾守护、dry-run 零写入、开发版拒绝）、gate 归档前置三类拦截（未迁档 / 缺归档节 / 仍是开发版）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.11（2026-10-13 ~ 2026-10-21）
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
