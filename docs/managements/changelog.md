# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.4]**（2026-10-24）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.5-dev] - 开发中（未发布）

- **报告收尾本机打开判定收紧**（rf-873）：手机/远端跑完报告仍弹「是否打开报告」(y/N)，按 `y` 只能拿到「打开失败」再跳回主菜单——因为 `DISPLAY` 是建立会话时的残留/桥接环境变量（tmux/screen、Catlink、Xpra），桌面其实在客户端。现在除 SSH/mosh 外，Linux 上还要求对应 X socket 真实存在、`xdg-open` 可执行，且桥接会话一律按无图形处理；`xdg-open` 自身报错不写回终端（只记日志）；打开失败一次后本会话直接打印产物路径与 Web/scp 指引。

- **LLM 缓存未命中可归因**：`cache.get` 未命中不再静默——「无此缓存文件」与「已过期（含 age/max）」各自打一条 **INFO**（每进程每 key 首见一次）；预检遇不可缓存（重新生成/强制刷新范围）也打 INFO「跳过缓存读」。此前两种原因在默认日志级别下完全不可见，用户只能看到「又调了一遍 LLM」，分不清是缓存被清、TTL 到期还是自己选了重新生成。

- **指纹变化归因日志恒开**：预检侧每次报告打一行 INFO「指纹组件变化（相对上次报告）」，默认日志级别即可定位 LLM 缓存未命中来源（此前只在 DEBUG 下记录，远程/默认配置实测拿不到）；报告收尾遇远程/桥接会话时也落一条 INFO，便于事后核对收尾行为。

- **发布流程三项改进**：`publish --title` 自带的裸版本前缀（`vX.Y.Z —— `）自动剥离，不再拼出重复版本号；`devbump` 补分步耗时埋点（版本改写/一致性收敛/切版提交/推送/闭环校验）；`devbump` 收尾新增**发布闭环校验**（tag 在 master 历史内、master 为发布版、本分支为下一开发版，不符硬失败）。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.4（2026-10-24）
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
