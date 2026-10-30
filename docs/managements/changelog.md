# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.14]**（2026-10-30）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.15-dev] - 开发中（未发布）

### 修复

- **跨渠道共用文案与取价枚举单源化**：调仓不可用提示在 CLI/TUI/Web 三处各写一份字面量（含 Web 的错误码重复），收敛为 `whatif_operations.WHATIF_UNAVAILABLE` + `whatif_unavailable_message()`；取价方式「官方净值(T-1)」原本在 `market_value` 产出、`html_jinja_env` 与 `_holdings_detail_blocks` 各自比较字面量，收敛为 `market_value.PRICE_TYPE_OFFICIAL_NAV_T1` 并由消费方引用；行情获取进度提示 4 处收敛为 `progress.MSG_FETCHING_MARKET*`。新增跨渠道单源契约用例 2 例（字面量不得在渠道层复现）。**另登记 rf-999**：报告层 57 个函数 >120 行、31 个签名 ≥13 参数，按「RenderContext → 按页签族拆分」两刀走，本轮未动结构
- **版切首跑长尾观察关闭（rf-980）**：两次版切首跑「明细装配与建议」分别 0.544s、0.948s（同版本后续 med 0.48~0.56s），连续两次不复现；92 个样本显示该阶段长尾散见于多个版本且与版切无关，判为阶段偶发、非版本切换引入，台账按判据关闭
- **缓存命中的费用与标记按本次裁清（rf-998）**：`_usage_delta` 只对顶层按币种做差，逐模块 `costs` 整字典照搬、`cached` 标记直接沿用会话累计——同一会话第二份报告整块命中缓存时，明细仍带上一份的模块费用（实测虚高到 CNY 0.061，本次真实花费 CNY 0.0119），汇总表/用量页签同源一起失真；真跑的模块又因标记粘着继续显示「使用缓存」。现在逐模块费用按币种做差，`cached` 按「本次无 token 增量」判定，`record_per_module` 在真调用时翻回 False。回归 1 例；**历史台账同步清洗**（`data/state/perf_history.jsonl`，原文件备份为 `.bak-20261031-010242`）：13 条不一致记录按该次 `cost_by_currency` 真实花费重分配、38 条本就一致的保留原记账、59 条早于费用统计的只刷 `cached` 口径；清洗后「逐模块费用和 vs 该次真实花费」不一致记录 0 条
- **写盘相位耗时异常（rf-997，环境侧关闭）**：2026-10-30T23:04 一次运行 HTML 生成 18.1s / Excel 生成 10.6s（同口径中位 0.2 / 0.3s）。当日两次空闲复跑（23:35、次日 00:52）分别 0.03/0.23s 与 0.03/0.23s 连续不复现；宿主 I/O 探针正常（顺序写 2905 MB/s、单次 905K 落盘 1.1ms），产物尺寸与历史一致，判为瞬时宿主负载、非代码缺陷，台账按判据关闭。

### 变更

- **设计护栏 W 级清零**（rf-995 / rf-996）：模板与工作台 CSS 的间距、字号字面量全部吸附到 DESIGN.md 契约阶梯——间距 254 处（阶外 6/10/14/18/20 与零星值 → 4/8/12/16/24/32，等距取小档）、字号 8 处 `0.95rem`（15.2px）→ `1rem`（16px）；三处语义特例单独收敛：报告侧栏让位与栏宽的重复魔术数 `220px` 提取为 `--toc-width` token（顺带消除两处同值漂移风险）、`.sr-only` 的 `margin: -1px` 改 `0`（裁剪 hack 不依赖该值）、汇总片内联 `margin: -2px 0 6px` 改 `0 0 8px`。护栏观察项归零（裸色值 0 / 圆角 0 / 内联色值 0 / 字号 0 / 间距 0）；README 六张配图按新样式重出；whatif 关态零改动基线哈希按评审记录更新，宽屏让位用例改为断言 token 单源。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.14（2026-10-25 ~ 2026-10-30）
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
