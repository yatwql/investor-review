# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.0]**（2026-10-21）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.1-dev] - 开发中（未发布）

### Changed

- **Web 生成执行体下沉（`rf-711`）**：`src/python/web/handlers.py` 910 → **710 行**，生成链路（执行体 / 产物清单 / 完成通知 / 输入模式→快照域映射 / 退出码）拆到 `src/python/web/run_generation.py`（235 行）。`handlers.py` 保留同名 re-export 维持既有导入面，`app.py` 改为从新模块注入 `RunManager.executor`；测试 patch 目标按「调用点所在模块」改指新模块。纯结构调整，零行为变化（`unit/web` 347 passed）。

- **时间戳 helper 三份拷贝维持现状（`rf-790`，已决策）**：`core/decision_ledger.py::_now_iso` 与 `core/signal_ledger.py::_now_iso` 逐字相同（各 1 行表达式），`scripts/_release/_timing.py::now_iso` 带时区偏移（跨机/跨时区对拍用，不能合并）。复核确认全仓无第三份语义相同的 naive 实现，为 1 行表达式新开 `core/timeutil.py` 需同步目录树与文档，收益低于成本 → **保持两处各写一行，不排期**；重访条件：出现第三份 naive 拷贝，或任一处要改精度/格式时统一。

- **开发者指南重构（A~E 五批）**：① 加锚点目录 + 新增「文档地图」（本指南 / CLAUDE.md / technical / requirements / testplan / DESIGN* / folders / test-coverage / 台账 各自管什么、真源级别）+ 「新人 30 分钟路径」，章节按新人路径重排（环境 → 门禁 → 测试 → 调试 → 扩展 → 注册表 → 编号 → 发布 → 脚本 → 纪律来源）；② 把 1124 行的「辅助脚本速查」拆为独立 [`scripts-reference.md`](scripts-reference.md)（60+ 脚本按用途分类，每条含设计逻辑与使用逻辑；参考型文档无版本头），本指南只留「最常用十条 + 按域索引」，正文 2343 → 1481 行；③ 新增「调试与剖析」章（日志三读法 / 交互式调试 / 性能三件套 / **测试慢或挂住的诊断**（`-p` 插件统计 sleep、禁睡上限法、测量纪律）/ Web 端 CDP / `data/state` 状态文件排查）；④ 新增「开发新功能：扩展清单」（新增数据源/Provider、报告章节/页签、Web 接口/面板 三张端到端清单）；⑤ 版本发布流程补「CI 失败排查」（job → 症状 → 本地复现，含「本地绿 CI 红」三类根因）、「回滚与热修」、「依赖升级流程」。同步：folders 目录树与统计、CLAUDE.md 管理文档清单、README 开发者参考表、FAQ 一处死锚点改指新文档。

### Fixed

- **发布编排易用性（`rf-807` / `rf-808`）**：`prepare --version` 与开发链推导值不一致时立即中止并给出四步指引（不再「按推导执行」跑到中途报错，提示也不再误打印入参）；新增 `release.py archive-init`——新小版本首发的三份归档文件、folders 目录树块、三处「归档档案」索引行一次建齐（幂等、可 `--dry`，建完自动 doc-drift sync），把「补一处 → 重跑 check」的往返收敛为一条命令。

- **真实仓库契约测试断言周期相关状态（`rf-809`）**：`test_real_rf_sections_are_migrated_or_absent` 曾要求主台账「至少有一节」，与 `devbump` 清空占位后的空台账冲突 → v0.14.0 后 `dev` 提交 CI 全红（三版本 test + portability）。现改为只约束「存在的每一节」，空台账合法；`TestCliSurface` 的处理器集合改为从 `cmd_*` 派生。

- **changelog 发布指针链接跨小版本失准（`rf-806`）**：`apply_changelog_release` 只改指针的版本号与日期、归档文件名写死在上一系列——v0.14.0 发布后指针仍指向 `archived_changelog.0.13.x.md`（实际段落已进 0.14.x）。现改写指针时同步换名，格式不符即报错中止；已发布后的主文件指针已校正。回归 2 例（链接改指目标归档 / 指针格式不符拒绝）。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0（2026-10-21）
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
