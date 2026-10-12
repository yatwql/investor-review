# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.12.12]**（2026-10-12）——已发布版本段随发布移入 [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.12.13-dev] - 开发中（未发布）

### Changed

- **TUI 主菜单 8 项描述整体精简**：[E] 生成基础报告（仅 Excel）、[B]/[L] 统一全角括号与产物标注（半角 `()`/`[方括号]` 与快捷键记号冲突消除、含 LLM 补空格）、[D] 改「查看配置与目录信息」（只读语义归位，子菜单横幅/docstring 同步）、[P] 改「配置报告可选章节（顺序与取舍）」（摘除 5 个章节名枚举——菜单与注册表双写漂移隐患）、[S] 改「配置功能开关（作用域四组，含 LLM 章节）」、[4] 改「查看缓存与状态统计」；新增菜单标签显示宽 ≤48 守卫断言（东亚宽度口径，80 列终端不折行，[P] 原 79 宽必折行）；手册双菜单块/详解标题/faq/developer-guide/requirements/technical/testplan（18→19 项）同步；跨渠道收尾（rf-667）：requirements E/B/L 行、technical B/L/[3][4] 行、CLI §10.1 对照表、faq [4] 措辞、web 手册镜像表 8→9 组修正、README（19 项菜单/10,000+ 用例/[D] 措辞）

- **README 截图全面刷新（六图）**：报告实景三图改用**全新虚构多资产样例持仓**（两账户 10 只：个股/场外基金/ETF/债基/货基，编造份额成本，不使用真实持仓）以全量报告（24 开关全开 + 六 LLM 模块全开、真实调用）重拍——`report-overview`（完整目录导航与全部章节入口）/新增 `report-toc`（盈亏汇总与持仓概况）/`report-charts`（交互图表）；新增界面实景三图 `tui-menu`（19 项主菜单 pty 捕获渲染）、`web-workbench`（生成报告页签）、`web-config`（配置编辑面板）；README 新增 🖥️ 界面实景段，`folders.md` 目录树/统计行同步（截图 2→6 张）；样例生成与截图全程隔离（`--config` 副本 + `data/` 运行前备份恢复，快照零残留）

### Fixed

- **自审修复 rf-667 ~ rf-670**：testplan 两处「18 选项」残留与 [Q] 缺列（与 19 项口径统一，人工回归清单不再漏测 Q）；`check-doc-drift` 新增第 18 项「手册主菜单 code block ↔ MENU_ITEMS 逐键一致」机检（双手册键集合+标签头，防手写副本漂移）；QA 错误码收敛 `qa/error_codes.py` 单一来源（会话/上下文生产、Web 状态映射、TUI 退出策略同源引用）；删除只写不读的 `llm_ok` 死字段

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.12（2026-10-03 ~ 2026-10-12）
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
