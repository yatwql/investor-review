# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.0]**（2026-11-12）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.1-dev] - 开发中（未发布）

### 测试

- **发布编排测试按命令域拆分**：`test_release_tool_gate.py` 1147 行（测试登记线 900）按域拆为三份——`gate` 保留门禁编排与归档前置、`test_release_tool_publish.py` 收 publish/devbump 与 check 本地门禁前置、`test_release_tool_refresh.py` 收 refresh 条件化与 archive-init/prepare 文档手术命令；运行态路径隔离夹具下沉 `_release_fixtures.isolate_release_runtime_paths`（三份共用，断言与用例数不变）。P4 存量监控清单对应行随之删除。

### 重构

- **判断依据模块按关注点拆为聚合门面 + 两子模块**：`report/decision_basis.py` 962 行（主程序登记线 700）拆为聚合门面（风险预算 / 纪律明细 / 信号可信度仲裁 / 装配入口 524 行）+ `decision_basis_signals.py`（信号清单装配与回测结论登记）+ `decision_basis_settlement.py`（结算摘要与按视界历史表现）；子模块符号由门面原路径 re-export，导入面与 `decision_basis_data` 契约不变。P4 存量监控清单对应行随之删除。

- **滞后净值品种的「本日盈亏」不再静默归零**：原实现里场外行只有净值日等于当日才算本日盈亏，否则记 0.0——QDII/国内场外滞后时报告显示「本日盈亏 0」，读者会误以为当天没涨没跌。现改为照实呈现该净值日的涨跌并标「参考」（HTML 行内小字 + Excel 明细脚注），组合合计只累加当日已更新品种（`market_value.sum_today_profit`），避免把 T-1/T-2 涨跌混进「今日」。
- **场外净值缓存门禁按披露时点分档（消除白天重复取数）**：`_price_cache_fresh` 原口径要求国内场外缓存到 T、QDII 到 T-1，而场外 T 日净值当晚才披露，白天运行这一条件永不可能满足 → 每次运行把场外基金判为过期并全量重取（实测单次浪费约 12s），重取回来仍是同一份滞后净值，写回后下次再判过期。现按 `market_hours.is_otc_nav_disclosed`（默认 20:00）分档：披露前只要求最近可得的一档（国内场外 T-1 / QDII T-2），披露后收紧回 T / T-1。

- **HTML 生成细分文档与实际不符（rf-1135）**：`developer-guide.md` 原写「四步 + 模板编译占绝大多数」，收益测量显示 `模板渲染` 约 0.0s、`面板视图装配` 占 2.1s of 2.13s；现补上 `面板视图装配` 计时点并改写排查口径，`technical.md` 编排器职责链同步。
- **已解决台账行加粗缺失的静默漏搬（rf-1134）**：`check-doc-drift` 只以 `| **rf-N** |` 识别已解决条目，写成 `| rf-N |` 时既不进已解决集合、归档步也按「本版无待迁档」放行——0.18.0 发布时实际发生（已修项主台账未被搬运，仅一行日志）。现已在已解决区检出未加粗台账行并报 finding，归档识别口径不变；新增 2 条回归用例（报/不报各一）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0（2026-11-12）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
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
