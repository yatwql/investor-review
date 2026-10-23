# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.8]**（2026-10-23）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.9-dev] - 开发中（未发布）

### Changed

- **`plan-182`（决策不做）迁入归档 + `plan.md` 收敛为最新状态**：`release.py` 的「已完成任务节」识别口径扩到 `❌ 决策不做`（与 ✅ 同为「不再在办」，标记保留以区分做完/不做），plan-182 按机械规则迁入 `archived_plan.0.14.x.md`（标题降为二级）；`plan.md` 去掉流转叙述（「均已实施」「已落地」「已由」一类），plan-185 与 plan-70 的现状改写为可直接执行的态与判据（含 plan-185 实测验收数据），归档索引的 0.14.x 覆盖区间校正为实际日期。回归 2 例（决策不做节被收集 / 「当前迭代」不计入该节）。
- **TUI 追问的报告选择默认项改为本期主报告**：候选列表按「档位优先 + 修改时间倒序」排序——`个人投资分析报告.html` 恒为第 1 项（回车默认），其它报告居中，`调仓模拟.html` 排末档；首项标注「← 回车默认」使默认目标可见，提示语同步为「回车=本期主报告」。根因：调仓模拟每跑一次即覆盖自己的固定名产物、把 mtime 顶到最新，纯按时间排序会把回车默认项落到模拟报告上（同目录并列产物，但语义上属少数派）。同批把 `调仓模拟.xlsx/.html` 与归档名前缀收敛为 `core/constants` 常量（`WHATIF_FILE_BASE` / `LATEST_WHATIF_*`），写入器不再写字面量。


（本次发布内容见下方归档索引）

## 归档

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
