# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.8]**（2026-10-23）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.9-dev] - 开发中（未发布）

### Changed

- **配置系统重构第 1 轮：注册表与域模型**：功能开关从「四组作用域」改为**八组内容位置**（持仓与交易 4 / 市场与估值 4 / 基金与风格 3 / 事件与摘要 4 / 呈现与交互 2 / 机制与质量 3 / 独立章节与回放 4 / 章节内选项 2，共 26 项），新增 `GROUP_DOMAIN`（组→五域）、`DOMAIN_ORDER`/`DOMAIN_LABELS`/`DOMAIN_HINTS`（Web 五域编排与提示）、`PANEL_GROUPS`（`[S]` 六内容组 / `[P]` 独立章＋章节选项）与 `FeatureSwitchDef.needs_hint`；`crisis_replay` 归市场与估值、`prosperity_framework` 归市场与估值、`report_qa` 归呈现与交互、辩论两项归 `chapter_options`（由 `[P]` 作章节子项渲染，不占 `[S]` 编号）。**系统自检转恒上屏**：移除 `doctor_check` 开关（TUI `[T]`、Web 自检卡与 `GET /api/doctor` 恒可用，`doctor` 子命令不变），`FEATURE_GATED_ITEMS` 只保留 `Q → report_qa`。同批同步 `how-to-config.md` 开关表与面板归属表、`how-to-use-tui-menu.md` 的 `[S]` 编号表（8-33）与键名映射、`requirements.md` §11.5/§3.6、`technical.md` 注册表与自检段、`developer-guide.md` 分组表、`scripts-reference.md`/`testplan.md` 描述。回归：注册表不变式/门控用例按 `GROUP_DOMAIN` 与八组重写。
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
