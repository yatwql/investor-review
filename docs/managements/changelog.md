# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.17]**（2026-11-03）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.16.18-dev] - 开发中（未发布）

### 变更

- **持仓录入缺省记入交易流水**：TUI 保存（`4`/`W`）与 Web「确认写入持仓文件」的「记入交易流水」由**需要显式指定**改为**缺省开启**——买入与卖出走同一保存出口，回车/默认勾选即写入并留痕（TUI `n` 显式跳过，Web 取消勾选后记住选择）。改因：流水既是 XIRR/成本分档/分红的唯一数据来源，也是卖出重算成本的依据，缺省不记会让后续分析静默缺数据。
- **指数行情会话级复用（rf-1037）**：`fetcher/index.py` 的 `fetch_indices`/`fetch_us_indices` 外挂 `index_quote` 会话缓存（`DataSourceRegistry.session_cache`，与 `fetch_index_history` 同口径）——同一轮运行内重复调用只取一次上游、未命中只记一次（此前一份报告里行情页与渲染层各调一次，`gb_dji`/`gb_inx`/`gb_ixic` 各记 3~4 次未命中并重复请求）；陈旧兜底读取改用 `cache_get(..., record_stats=False)`，不再把「同一键的第二次读」计成新的未命中（命中率与未命中前缀分布不再失真）。空结果同样入会话缓存，避免一轮内为「无数据」重复等重试。新增 6 例回归（美股/ A 股复用、空包缓存、载荷隔离、两处陈旧探针不计数）。
- **成本分档改净成本口径（与卖出录入同源）**：`analysis/cost_flow.py` 的 `build_cost_lots`（FIFO 批次）替换为 `build_net_cost_positions`——按代码合并为**净成本 = Σ(买入金额+费用) − Σ(卖出金额−费用)**，单位净成本 = 净成本/净份额，回收超成本时钳 0；`compute_cost_tiers` 改为按**净成本单价**与市价比较整码归档（不再按批次拆档）。口径理由：卖方不保证录入完整流水，批次追踪在流水缺失时会给出与持仓表不一致的成本；净成本只依赖已录的买卖金额，缺流水时退化为快照近似。用例：5 例净成本原语（含费用摊薄/卖出冲减/超额钳 0/清空/无买入）+ 2 例分档口径（整码归档、卖出回收可翻转档位）；`reports-instruction.md` 与 `requirements.md` R-CFL-01 同步。
- **持仓录入：卖出改为净成本法重算（R-HLD-08 口径调整）**：原先「卖出保留原每份成本、只减份额」，卖出回收的资金不影响剩余持仓成本；现按 `剩余成本 = 原成本总额 − 卖出份额×卖出价`、`剩余每份成本 = 剩余成本 / 剩余份额` 重算（回收金额超过原成本总额时钳制为 0，不产生负成本）。改动点：`core/holdings_editor.py` 卖分支 + 模块成本口径注释；用例改为断言净成本重算并新增「超额回收钳 0」一例；`requirements.md` R-HLD-08 与 TUI 手册「写回规则」同步。
- **财报源超时预算分档（rf-1036）**：`providers/datasink.py` 把单一 20s 预算拆为**正文档 20s / 探测档 8s**——章节清单 `/documents/{id}/sections` 只回小 JSON，SSL 握手挂起即主机不可达，用正文预算会让一次挂起白等 20s+（实测单次 23~25s、7 日 26 次，使 full 报告「数据准备」从 1.5s 涨到 59s 量级）。预算经 `_request(..., timeout=)` / `_get_with_transient_retry(..., timeout=)` 透传（晚绑定默认值，运行期可覆盖），挂起判据与连接级重试沿用同一 `with_connect_retry` 脚手架。新增 3 例回归（探测档预算生效 / 正文档仍走长预算 / 两档关系固定）；`datasource-reliability.md` 的 DataSinking 节补「超时设定」行。

## 归档

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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
