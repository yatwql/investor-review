# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.7]**（2026-11-09）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.8-dev] - 开发中（未发布）

### 修复

- 增量历史缓存键改为注册表形状（rf-1108）：旧实现拼成 `history_history_{chain}_{code}`，既不命中 `history_stock_` / `history_index_` / `history_fund_otc_` 前缀也不命中精确键，落进 default 日档（24h）被清理——K 线文件每日全量重取，且 `_correction_streak` 计数每日重置，「连续检出→跳过全量刷新」冷却永远到不了阈值；现由唯一构造器 `chain_incremental.history_cache_key()`（`{chain_name}_{code}`）供 `index.py` / `clear_incremental_cache` 共用
- `market_hours`（官方开闭市探测）由未登记改为 `calendar` 模块精确键（清理 14 天 ≥ 读侧 7 天盘后口径）
- 移除 `{cache_key}_correction_flag` 死写（只写不读）
- 新增缓存键形状 ↔ 注册表覆盖契约测试（`test_cache_key_registry_contract.py`）：任何键构造器产出的键都必须命中注册表类型，不得落 default；跟踪基线必须有独立精确键 TTL
- 跨报告对比基线（`fund_manager_snapshot` / `fund_concentration_snapshot` / `fund_style_snapshot`）改为近永久 TTL（`CACHE_NEAR_PERMANENT`，1 年）并在注册表登记精确键 TTL（rf-1107）：此前落入上报域日档（`fund_manager_` → 24h），而报告生成入口每次先跑 `auto_cleanup_expired()`，两次报告相隔超过一天即把基线当过期文件删掉，报告恒定显示「此为首次运行，基金经理变更自下次报告起跟踪」
- 「刷新基础缓存」保留跟踪基线（rf-1107）：`clear_by_group` / `clear_by_prefix` 新增 `exclude_keys`，刷新流程点名保留三个快照键——该流程只清不重建快照，清掉即让下一次报告退化成「首检」


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.7（2026-11-04 ~ 2026-11-09）
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
