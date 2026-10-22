# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.4]**（2026-10-22）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.5-dev] - 开发中（未发布）

### Fixed

- **事件窗盘中运行 100% 降级（面板长期空白）**：`WINDOW_AFTER=5` 要求事件日后尚有 5 个交易日，而新闻事件日就是当日/昨日、行情轴止于当日 —— 实测单次运行 `可出行 0 / 降级 14`，14 条全是「窗口超出行情范围」，开启开关也拿不到任何事件行。改为右界按**行情轴实际可用交易日截断**计算（`window_after_actual` 回显、`window_partial` 标注），事件日后 0 个可用交易日才降级；视图摘要写明「N 条后窗未满（最短 M/5 日）」；需求 `R-EW-01/02` 同步。注：v0.12.x 曾否决「半窗截断」，当时前提是严格口径下仍有 23 条可出行，本次不引入第二口径（统一一条规则 + 逐行回显实际日数）。
- **发布门禁放过空 changelog 段**：v0.14.4 的开发段停在占位句，`prepare` 把占位原样归档 → 归档文件只有 `## [0.14.4] - 2026-10-22` 一行标题、正文永久丢失。`apply_changelog_release` 现前置断言「开发段必须含实际条目（`###` 分类或 `- ` 条目）」，命中占位即中止并提示先补 changelog。
- **缓存清理按虚龄删脚本性能缓存**：`data/cache/test_coverage_snapshot.json` / `test_redundancy_facts.json` 由脚本裸 JSON 写入、无 `_ts`，清理器按 `now - 0` 算出 **57 年陈龄**并每轮启动删掉（缓存优化白做 + 日志荒谬）。脚本写入补 `_ts` 包封，清理器对仍无 `_ts` 的文件一律跳过（托管边界之外）。
- **数据源硬等待**：基金档案页（回退链路）超时 15s → 8s（实测 SSL 握手挂起单请求 17s）；东财 push2 遇「对端主动断开」不再退避重试、直接回落下一链路（实测每个断连代码白等 0.6s，而 `eastmoney_industry_rest` 秒回）。

- **章节清单缓存持久化失效章节名**（rf-822，诊断经日志复核后收窄）：原判断「陈旧 doc-id 导致 `全链路失败` WARNING」不成立——该 WARNING 分支已随日志治理改为按传输级失败分级（`各源均无可用结果` 走 INFO），且 404 落在**章节探测**（`?section=`）而非文档级、每个 doc id 仅 2 次尝试（主/备各一，无重复探测）。真实残留缺陷是：章节名清单为 14 天缓存，命中后若该批章节全部取不到正文，旧名字会持续 404 且永不恢复（实测单轮 5 例 × 约 1.3s 无效往返）。修法：取正文全空时失效该文档的清单缓存（`_invalidate_sections_cache`），下次重取 `/sections` 买回恢复机会；取到正文或无清单可清时不动缓存（防每篇都清、清单缓存形同虚设）。

### Changed

- **新闻去重锚点改真追加写**：flush 原走「读全文 → 整文件替换」，而锚点已 37.9 MB、每轮只新增数十条 —— 写盘成本与文件体积成正比、与新增量无关。改单次 `write` + `fsync` 追加（读侧本就逐行容错）；压缩条件从「仅每 key 最新」扩为「每 key 最新 + **仅保留近 120 天**」（`INVEST_DEDUP_ANCHOR_RETENTION_DAYS` 可覆盖，0 = 纯去重）——仅按 key 去重压不动（标题对高度唯一，压后仍 37.9 MB），保留期才是体积上限。
- **缓存清理日志降噪**：逐文件明细 INFO → DEBUG（单日 257 行、占全天日志 7.2%），INFO 只留汇总行 + 释放字节；age/TTL 按量级自适应单位，盘中 30s 的 price TTL 不再印成 `ttl=0.0h`。
- **交易日历进程内 memo**：`_get_trading_calendar()` 单次报告被调用 600+ 次、每次都读盘解析 JSON；改为按「缓存文件指纹 + 剩余 TTL」进程内复用，文件重写/到期即回落磁盘（语义不变），conftest 加 autouse 复位。
- **事实校验自动修正计数入 `perf_history.counters`**：新增 `fact_fix_total` / `fact_fix_numeric` / `fact_fix_code` / `fact_fix:<模块>`（LLM 阶段前清零、结束后汇入）——单次实测 5 处修正，此前只进日志无法跨期判断提示词改动是否有效。
- **thinking 并发槽等待可观测**：`llm_max_thinking_concurrency=1` 下两个 thinking 模块（实测 51s / 37s）被完全串行却全无日志线索；现等待超过 5s 即记 INFO（模块名 / 等待秒数 / 上限）。默认值是否提到 2 待真机实测（配置注释所述「多 thinking 并发偶发空响应」需复现验证）。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.4（2026-10-21 ~ 2026-10-22）
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
