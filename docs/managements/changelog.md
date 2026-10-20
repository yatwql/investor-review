# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.8]**（2026-10-20）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.9-dev] - 开发中（未发布）

### Added

- 调仓 What-if 对比页右上角「打印 / 导出 PDF」按钮：与主报告同参（44×44 触控、语义 token、打印稿自隐藏），双页入口一致（plan-128）

### Changed

- 报告模板 40 处内联 `style=` 色值全部 token 化归零：新增组件派生 token `--heat-*`/`--corr-*`/`--cell-na-bg`/`--alloc-*`/`--danger-text`（DESIGN.md Colors 登记，暗色配对同步）；设计护栏 W3 内联色值归零并由观察升为 E 级 finding（W4 字号/W5 间距保持观察）（plan-167）

### Fixed

- 新闻去重同主体不同事件误合并治理（两处）：bg=2 梯度泛词否决表补 `gdp`（跨经济体 GDP 数据发布实证误合并）；bg=3 下限档新增事件信号词组一致性判据（`_EVENT_GROUPS` 17 组，组内互认，锚点回放拦截 2,566 条、合并侧真重复无误杀；≥4 实体证据更强档维持现状）
- 校准工具锚点超线告警按重复行占比分流：重复率低于 5% 不再建议 `--compact`（去重无收益），改指上调告警线；`--compact` 零收益时输出成因说明
- `write_llm_providers` 写盘后将 `llm_providers.json` 权限收紧为 0o600（含 api_key 的凭据文件与 cache 域敏感文件同标准；Windows 静默跳过），补新写/重写收紧两用例
- 设计护栏 W3 内联色值观察项完成误报归类（40 处全为真实存量），批量 token 化收口任务登记 plan.md `plan-167`（含入域条件）
- 需求文档核查修正：R-OUT-12 删除行内重复的「覆盖章节」残留清单（与实现折叠章节全集不一致）、R-LLM-01 触发范围更新为三渠道完整报告口径（原「仅菜单 L」过时）、R-CON-07 补充 R-CCH-08 联网必需模块例外边界
- `market_hours`：`is_market_open()` 增加进程内分钟级 memo，「市场时段」DEBUG 日志仅在判定结果变化时输出——消除 TUI 常驻轮询下 7 天 12 万行重复 DEBUG（占 app.log 总量 60%）
- 数据源重试：解析/数据形状类异常与 perf 基准禁网桩不再走传输级退避重试——`core/retry.py` 新增 `is_parse_failure_exception` / `is_deterministic_failure` 判据，`with_connect_retry` / `run_with_timeout` / `tencent` K 线与价格 / `financial_indicator` 多期直连同口径接入（前者是确定性数据缺陷，重试必然重复；后者是设计使然的禁网）
- `chain_incremental`：历史修正全量刷新增加连续触发冷却——检出重叠达到阈值后判定为源结构性回看，跳过全量刷新沿用按日合并结果；无重叠合并成功即重置计数（消除每运行多拉一次全量 260 天）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.8（2026-10-13 ~ 2026-10-20）
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
