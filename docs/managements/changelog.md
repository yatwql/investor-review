# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.6]**（2026-10-28）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.7-dev] - 开发中（未发布）

### 修复

- **移除兼容层（rf-937）**：旧数据结构/旧数据文件/旧缓存载荷/旧配置键/旧配置文件/旧内部 API 一律不再保留支持，破坏性变更统一走「换键换字段 + 版本戳整体作废」。本次清掉四处存量兼容分支：① `llm_key.json` 顶层 `api_key` 扁平旧形态不再自动改写（去掉了 `default` 块迁移与 `.bak` 备份），改为拒绝加载并给出改写指引；② 配置校验中 `market_hour_aware` 的退役告警分支删除（该键已无任何消费方，静默忽略）；③ 穿透标的来源只认契约真值键 `sources`，不再回退合并层内部键 `funds`；④ TUI `handlers_config` 的 `filter_menu_llm_modules` 兼容再导出删除，调用点直连 `tui_menu`。兼容层纪律（含「兼容」与「健壮性」的判据）写入 developer-guide「兼容层纪律」。

- **行业资金流向「陈旧回退」带新鲜度标注（rf-936）**：源不可达时回退上次成功载荷后，报告与 LLM 提示词把它当今日数据用——模型会把 1~3 天前的资金流向当当下评。`mark_data_used` 新增 `freshness` 通道（进事件 `detail`、**不进降级计数**，避免把自己算成一次失败），数据质量块新增「陈旧回退（源不可达，用上次成功数据）: <源>」行，取数侧同时如实告警。回归 7 例（事件 detail / 无标注时不添行 / 不污染失败计数 / 与失败降级共存）。
- **输出目录锁的 pid 探活在 Windows 上会杀进程（rf-935）**：`os.kill(pid, 0)` 在 Windows 对非控制台信号直接走 `TerminateProcess`，探测锁持有者等于把它杀掉。改 `OpenProcess` 查询句柄，无法判定时退化为文件年龄判据；回归 4 例。

- **行业资金流向不再每份报告重复撞超时（rf-928）**：失败负缓存原先只在进程内存，而每份报告是独立进程——实测 30 次真实运行 38 次 akshare 异常，且失败后该块数据整块消失。改为负缓存落盘（30 分钟、跨进程生效）+ 失败回退最近一次成功载荷（≤3 天，失败原因标 `stale`、提示「使用上次成功数据（源不可达）」），超过 3 天仍留空，绝不复用旧数据。回归 4 例（磁盘负缓存短路取数 / 失败落盘 / 陈旧回退 / 成功清负缓存并刷新基准）。
- **场内基金（LOF/ETF）行情不再永久缺价（rf-929）**：`截取名称判据` 以汉字集合重叠 0.7 为阈值，把源侧简称「白酒基金LOF」与持仓全称「招商中证白酒」判成两只不同标的（重叠仅 0.5）→ 有效报价被拒；同时场内基金不在 00 重叠区降级名单，股票链路失败后无任何兜底。改为：名称判据增加「连续 2 汉字公共段」一档（代码已由路由确定身份，名称只作二次防错），并让场内基金在股票链路失败后同样降级净值链路。不同标的（「宇晶股份」vs「广发多因子」）仍被拒。回归 3 例。
- **演示/基准运行与真实运行彻底隔离（rf-930、rf-931）**：原先两者共享 `logs/app.log` 与 `data/cache`，演示持仓的告警（名称对不上/缺凭据/陈旧锁）混进真实日志、按「读了哪个持仓文件」事后反推才能区分。新增三通道：`INVEST_LOG_PATH`（改落盘文件）、`INVEST_RUN_CONTEXT`（启动一行上下文标记，落哪都能归属）、`INVEST_CACHE_DIR`（缓存改落）；`scripts/make-screenshots.py` 自动注入。演示工作区的凭据块与 `providers` 引用也改为 `build()` 同源写入（旧实现凭据块叫 `default`、providers 却引用 `deepseek-main`/`opencode-go`，每次演示 run 刷 2 行告警）。回归 11 例。
- **残留输出目录锁不再被当成持续占用（rf-932）**：原先只判「锁文件存在」，`kill -9`/容器重启后的残留锁让每次启动都刷一条「可能正被其他入口占用」告警，既误报又让人对真实抢占告警脱敏。锁现在带陈旧判据（pid 已不存在 / 无 pid 且超 12 小时未更新）并支持接管；活进程持有的锁仍正常拦截。回归 5 例。
- **LLM 缓存冷启动不再误归因为 `ttl_expired`（rf-933）**：新进程首轮四模块全 miss 时，日志记 `ttl_expired=4`——据此判定「放宽 TTL 能省钱」是错的（实际无上轮缓存可命中）。归因补 `cache_miss` 三态：无上轮指纹快照时记冷启动。回归 1 例。
- **`llm_settings.json` 读取失败带出原因（rf-934）**：原先静默返回 None，面板只报「读取失败，按默认展示」，现场无法区分文件被占/半写/JSONC 解析失败/编码问题。现日志带异常类型、消息与文件路径。回归 1 例。

- **持仓变动复盘误报「新增/清仓」（rf-927）**：截图/演示报告运行曾把 23 只演示持仓的快照写进真实 `data/history/snapshots/`（快照目录是 `PROJECT_ROOT` 常量、不随配置走，截图护栏又漏了 `data/history`），真实报告逐对差分后把整批演示标的报成「新增」、并把本人持仓报成「清仓」。三重修复：① 事件抽取新增**基线切换守卫**——相邻两期持仓代码 Jaccard 重合度 < 0.5 即跳过该区间推断并在表尾标注（单侧为空不触发，保留「全清→回补」账户重排的既有识别）；② 截图工具护栏补 `data/history`；③ 已产生的 7 个污染快照移出快照目录隔离并删除。回归 6 例（不相交/正常变动/仅跳过切换对/双侧为空/视图透传/无说明常态）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.6（2026-10-25 ~ 2026-10-28）
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
