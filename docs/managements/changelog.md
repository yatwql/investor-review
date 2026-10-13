# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.12.13]**（2026-10-13）——已发布版本段随发布移入 [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.12.14-dev] - 开发中（未发布）

### Fixed

- 智囊团深度复盘：结构化决策头机器载荷（`决策头：{...}` 单行 JSON）不再直出 HTML 报告正文与 Excel「智囊团深度复盘」页签——报告装配点在决策登记完成后对 LLM 内容四元组单点剥离（`strip_structured_header`，与解析侧共用标记常量与括号配对扫描），缓存保留原始内容；补正常形态/畸形矩阵单测与装配接线测试。

- 报告图表图注（图注纪律）：corrRollingChart 补 `.chart-caption` 图注；新增 `.note-caption` 类承载表格/统计口径说明附注（与图注同视觉档位、语义分离），回撤区 4 处误用图注类名的说明块改用——`.chart-caption` 现专属图表，由结构契约测试全量机检。
- 东方财富行业/概念接口（push2）：请求前节流从自建随机 sleep 迁移为 `RateLimiter` 原语（登记键 + 最小间隔 0.1s + 抖动 0.5，惰性单例 + 测试隔离 reset），节流算式纳入 C27 单源纪律，与 cninfo/datasink/eastmoney 分页同模式。
- 新闻抓取预算：`per_source = max(500, top_n×2)` 折算收敛为 `fetcher/news.py::news_fetch_limits` 单源函数（抓取预算单源纪律），缓存层与报告层两处内联计算收编，调用方不再各自复制算式。
- 调仓 What-if 回测窗口：`compute_backtest_days` 的自然日×5/7 近似折算替换为交易日历精确计数（交易日历单源 `count_trading_days_elapsed`，日历不可用时内部回退排除周六日），长假前后的窗口请求天数不再偏差。
- 代码形态判定：A 股六位代码/美股字母代码判定收敛为 `core/code_utils` 语义原语（`is_six_digit_code` / `is_letter_based_code`），配置校验、天天基金申购、因子指标、组合历史、费用估算五处内联判定收编（代码形态判定中心化）。

### Changed

- 技术设计文档：架构约束表增「env 初始化期注册」例外脚注（`html_jinja_env.py` 无状态过滤器注册与 fail-closed 默认值合法，渲染期数据仍禁入全局）；新闻抓取预算/交易日历约束行补单源指引与 whatif 回测接入点；`schemas/history.py` 模块 docstring 修正为数据契约职责（原子写入由 `report/history_snapshot.py::save` 经 `core/atomic_write` 承担）。
- 自审挂账：style 护栏观察项（裸色值/圆角档位外，E 级不判 finding）纳入 `plan-121` 治理——退出判据为观察期（≥2 个发布版本）观察数不再增长 + 存量收敛计划或逐条白名单。

（本次发布内容见下方归档索引）

## 归档

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
