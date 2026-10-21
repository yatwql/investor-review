# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.0]**（2026-10-21）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.1-dev] - 开发中（未发布）

### Changed

- **时间戳 helper 三份拷贝维持现状（`rf-790`，已决策）**：`core/decision_ledger.py::_now_iso` 与 `core/signal_ledger.py::_now_iso` 逐字相同（各 1 行表达式），`scripts/_release/_timing.py::now_iso` 带时区偏移（跨机/跨时区对拍用，不能合并）。复核确认全仓无第三份语义相同的 naive 实现，为 1 行表达式新开 `core/timeutil.py` 需同步目录树与文档，收益低于成本 → **保持两处各写一行，不排期**；重访条件：出现第三份 naive 拷贝，或任一处要改精度/格式时统一。

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
