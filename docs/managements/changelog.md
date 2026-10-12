# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.12.11]**（2026-10-12）——已发布版本段随发布移入 [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.12.12-dev] - 开发中（未发布）

（本次发布内容见下方归档索引）

### Added

- **功能开关面板分组重构（plan-120）**：功能开关分组从生命周期三组（实验 / 常规 / 报告章节与增强）切换为**作用域四组**——📊 呈现与体验（2）→ 🔍 分析增强·既有章内追加（14）→ 📑 独立章节与回放（6）→ ⚙ 机制与诊断（9，含实验项）；生命周期降为注册表 `FeatureSwitchDef.experimental` 独立字段（`--experiment` 取值域、CLI 帮助清单与页脚实验自述改看该字段，成员不变：决策跨期反思闭环 / 报告对话式追问）。**零行为变化**：31 键、默认值、`affects_report`、产物自述与报告字节全等；转正语义改为「摘除 experimental 身份」（作用域不变则原地留块，面板入口不随转正消失）。TUI `[S]` 面板按四组分块（编号 8-38 连续派生）、Web 配置面板 surface 改发 `groups` 四组（`report_switches` 键移除、实验项 ⚗ 逐行标记）、守护 `_format` 改注册表动态派生并新增旧三组名残留检测；四组文案与面板编号同步 requirements / technical / developer-guide / testplan 及各手册。落地设计见 [`feature-switch-grouping-redesign.md`](../archive/v0.12.x/feature-switch-grouping/feature-switch-grouping-redesign.md)。

### Fixed

- **禁用 LLM 模块误渲染故障占位章节（rf-664）**：`enabled_llm.<模块> = false` 时 HTML 报告仍渲染对应章节且带误导性故障占位（用户实测 `penetration_deep` 关闭仍出「、穿透深度分析」+「⚠️ 当前无法生成…LLM API 服务暂时不可用、API Key 配置错误」）。根因两层：① `report_template.html` 四个 LLM 章 include 共用单一 `section_visible("global_macro")` 守卫，`_compute_section_visibility` 已实现的逐模块章级隐藏 + 连续重编号未落到正文（导航逐模块剔除而正文照渲，序号缺键渲染为空）；② `llm/fallback.py::build_fallback_llm_content` 把禁用（`LLM_MODULE_FAILURE=disabled` 的 None）与生成失败混同，向禁用槽位注入占位。修复：四 include 改逐模块 `section_visible` 守卫（同时修复 global_macro 禁用连带隐藏其余兄弟 LLM 章节的过度隐藏）+ fallback 禁用槽位保持 None（占位只注入「启用但真实失败」的模块，禁用整章隐藏）。回归：模板逐模块隐藏与不过度隐藏反向 2 例 + fallback 禁用感知 4 例。
- **36h 技术债核查批次整改（rf-663）**：`check-doc-drift.py` docstring 检查项 4/8 三组措辞四组化（组名与残留名单以 `_GROUP_DOC_NAMES`/`_RETIRED_GROUP_NAMES` 派生为真值）、`developer-guide.md` check-semantic-index 正向描述改「注册表每个键（全量）」、`main.js` 实验项注释改「实验身份与作用域分组正交」、plan-120 设计文档按先例迁入 `docs/archive/v0.12.x/feature-switch-grouping/`（changelog / archived_plan / archived_changelog / folders 四处链接与目录树同步）、设计文档 §8 补转正迁移演练实测记录（decision_reflection 内存模拟转正：`experimental_flags` 收窄至 report_qa、取值域拒绝、自述与 Web surface 联动、面板编号零变化、还原全复原）、P3 文件过长登记表补登 `features.py`（730）/ `_format.py`（558）/ `handlers_config.py`（534）三行 + 归档文件补 rf-661/662 追加归档行。

## 归档

- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.11（2026-10-03 ~ 2026-10-12）
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
