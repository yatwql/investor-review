# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.10]**（2026-10-20）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.11-dev] - 开发中（未发布）

### Added

- `check-doc-drift` 新增第二十项检查「迁档占位↔归档节」：review-findings 每个「已随 vX.Y.Z 发布迁入」占位，对应 `archived_review-findings.{X.Y}.x.md` 必须存在含该版本号的二级标题归档节——占位已写、归档正文缺失（发布归档迁移只删不写）即当场报出；doc-drift 项目清单五处文档同步（自审 rf-756）
- `check-doc-drift` 新增第二十一项「树描述计数禁令」：folders.md 目录树描述禁写「阿拉伯数字+量词」的易漂移计数（开关项数/菜单项数/文件数类，与「测试真值单一来源」同源纪律）；docs/archive 记录域豁免、中文数词设计常量不入检；现存 6 处 src 域违规改定性措辞（自审 rf-757）
### Changed

- `release.py gate` 新增演进对照新鲜度断言（P2 前置）：「当前开发版」列头「本次重跑时的工作区」日期须为当日——evolution 为发布链人工步骤，跳过即以过期快照发布的缺口由此闭合（表头与数据行同命令原子刷新，日期一致即数据行同步）；发布编排描述三处文档同步（自审 rf-758）

### Fixed

- TestGate 门禁编排用例与演进新鲜度断言隔离：新鲜度直读真实 folders.md + 墙钟，编排用例在不同时区/日期的 CI 上随机红（本地已过零点、CI 仍是前一日 → 先行拦截返回 2，回归/守护一个不跑）；新增 autouse 夹具将新鲜度视为通过（编排用例只验序列），并新增新鲜度失败即中止且不触发子进程的专项用例（自审 rf-759）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.10（2026-10-13 ~ 2026-10-20）
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
