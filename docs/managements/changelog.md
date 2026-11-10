# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.8]**（2026-11-10）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.9-dev] - 开发中（未发布）

### 修复

- 台账归档静默跳过加诊断（rf-1117）：`apply_rf_archive()` 在「节在、表也在、但行首编号未加粗」时返回 0，表现为「该版本已迁档，跳过」，发布漏搬无迹可寻——现留 `logging` 告警点名「编号需加粗」；补一条 `caplog` 用例
- 基准跑不再污染真实持仓快照历史（rf-1118）：`test-perf-report.py` 的状态隔离漏了 `HISTORY_SNAPSHOT_DIR`，合成持仓（23 只/2 账户）落进共享主目录后按日去重当权当天最后一个快照，`holding_change_events` / `portfolio_evolution` / `trade_cost_model` 把真实序列判成「基线切换」（代码重合度 0.09，两段区间交易事件被永久跳过且 180 天内不自愈）——现补快照目录隔离 + `snapshot_namespace="bench"` 双保险，补 3 条回归；已删除 2026-11-06 那条污染快照（跳过区间归零）
- 自检的百分比核对支持算术核验（rf-1118）：`_unverified_percentages` 原为纯子串匹配，把「18.43%+13.17%=31.60%」这类合法合计判成幻觉并在报告尾部追加「无法核实」注记——现允许 1~3 项加减组合（容差 0.02pp），分项推不出的合计仍照旧标出
- 事实校验修正值与真值同精度（rf-1118）：修正值原按一位小数上屏（20.66→20.7），与摘要/其它模块的两位小数口径互斥，模型层自检随即把修正本身报成「同一实体被赋予不同收益率」——现与提示词真值块同取两位小数并剥掉精度零（`FACT_CHECK_RULES_VERSION` → `fact-rules-7`）
- 自检持仓摘要补 `收益率` 维度（rf-1118）：摘要只给市值/盈亏/占比时，自检无法核验收益率声称，只能写「摘要未给无法核实」，事实校验改出的错值也就无从对账

- 测试基建去重与诊断留痕（rf-1119）：`_freeze_market_bucket_for_cache_asserts` 原在 11 个缓存测试文件各一份，收口到 `_cache_fixtures.py`（导入即生效）；`test_perf_history*.py` 分片的 `fixture_mod`/`_records` 收口到新增 `_perf_history_fixtures.py`；`scripts/_test_runner/runner.py` 失败详情落盘失败不再 `except Exception: pass`，改为上报路径与原因（补回归：留痕且不改判定）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.8（2026-11-04 ~ 2026-11-10）
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
