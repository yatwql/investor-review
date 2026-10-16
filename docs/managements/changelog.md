# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.4]**（2026-10-16）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.5-dev] - 开发中（未发布）

### Fixed

- **盘前/盘后价格缓存误用盘中价（rf-691）**：`_price_cache_fresh` 此前只比 `price_date`，把交易日 T 盘中写入的场内缓存（如 10-15 13:01 的 29.35）当作 T 日收盘价（真实 29.60）在盘后/次日盘前沿用，使「本日盈亏」与「快照环比」系统性偏离真实涨跌。现增加收盘时点校验：T 日已收盘（now ≥ 15:00）时要求缓存写入时刻 ≥ T 日 15:00（午间休市不施加），`report/market_value.py` 的 `CACHE_ONLY` 分支与 `_fetch_price_with_cache_refresh` 两处传入 `cache_key`；强制刷新失败时退回刷新前的过时缓存（不再因清缓存反而丢数据）。新增 `test_fetcher_price.py` 8 个回归用例。
- **Web 生成完成后按钮复位（rf-690）**：run 完成后「生成报告」按钮停在「生成中...」禁用态、无法再次生成或换格式再生成（rf-257 真机 basic 实测揭示）——根因是 `pollOnce` 完成分支只移除 `aria-busy`、未复位文案与禁用态、未清已消费的 `file_id`；完成分支与 `resetFlow` 共用 `restoreGenerateBtn()` 单源复位（清 `state.fileId` → `updateGenerateBtn()` → 文案还原 +「请重新上传」提示；正式-用存量免上传立即可再生成），新增 `test_web_generate_flow.py` 源结构回归 3 用例。

### Changed

- **发布流程分层纪律补充（rf-689）**：developer-guide 发布流程段增加「归档迁移/管理文档改动后、进 `gate` 前必跑便宜守护（`check-doc-traces` 等）」——守护发现前置，防止 P2 门禁因文档级 finding 双跑全量 regression（v0.13.4 发布时实际发生一次：管理文档引用归档路径触发 ARCHIVE 痕迹拦截，gate 第二轮才过）。
- **报告浏览器验证六项收口（rf-113）**：Iter 7 全链路浏览器人工验证全部完成并移入已解决——自动化回归（headless Chrome 148 一键复跑 `node docs/tmp/rf113/run-rf113.mjs`：① 6 图 badge、② afterprint 快照恢复、③ 断网渲染、⑤ 375px 报告+调试页、⑥ 禁 Canvas 兜底，5 PASS + ⑥ 已知表现记录口径）+ 人工抽验（真实 `Ctrl+P` 打印预览 2x/浅色/不跨页、微信 X5 file:// 表格兜底 + 横竖屏、iPad Safari 90+ 抽验、Windows Chrome/Firefox）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与结论见 `docs/plan/report-browser-verification.md`，勾选清单归档 `docs/archive/v0.9.x/chartjs-upgrade/iter7-verification-checklist.md`；rf-114 前置解锁


## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.4（2026-10-13 ~ 2026-10-16）
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
