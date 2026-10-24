# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.5]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.6-dev] - 开发中（未发布）

- **缓存 TTL 收敛为「默认 + 稀疏覆盖」两层**：生成的 `config.json` 里 `cache_ttl` 改为空对象（默认值唯一来源 = 缓存注册表），只有用户显式加键才构成覆盖、删键即回默认——消除「改默认值后配置副本继续生效」的漂移；`cache_ttl` 中未注册的键（如已删除模块的 `fund_overlap`）改为告警。

- **配置文件 TTL 段清空**：`data/config/config.json` 中等于注册表默认值的 37 个 `cache_ttl` 键已移除（值本无差异，行为不变），配置文件与「稀疏覆盖」口径一致；需要调优时再添加单个键即可。

- **移除按 key 的 TTL 抖动**：TTL 与缓存键无关后，读侧与清理侧天然同值。此前抖动只在「传了 key 的读点」生效，LLM 读侧全都不传 → 约一半 LLM 缓存会被清理侧最多提前 15% 删除（4h TTL 下最多 36 分钟）。另把 `bond_yield` / `fund_manager` 的同值重复常量改为直读注册表，`index`/`index_valuation` 的宽松常量补注为「陈旧兜底读，刻意不用新鲜期 TTL」。

- **清理侧与读侧 TTL 同源**：`cleanup_expired` 按剥离版本戳后的**逻辑键**查类型与抖动因子，与读侧 `get_ttl(type, key)` 取值一致（此前读侧 ±15% 抖动、清理按 1.0×判定，约一半 key 会被提前最多 15% 删除）；精确键映射也随之能命中。

- **缓存 TTL 取消读侧独立配置**：`get_cache_ttl_llm` 不再维护「模块 → 缓存键」映射表与回退默认值字典，改为「模块键 → `llm_<模块>` → 直读 `cache.get_ttl`」——读侧、启动清理、统计、配置模板同源于 `data_registry`，运行时只剩 `config.json` 一层覆盖；未登记模块打 WARNING 并按日级兜底（不再静默借用 `global_macro` 的 24h）。

- **新闻关联分析缓存 TTL 调至 4h**：`llm_news_correlation`（逐条缓存，键含标题前 80 字 + 持仓指纹）由 1h 改为 4h；同一批新闻在同一天内的关联判定不再按小时重算。代码默认值、缓存注册表、生成配置的模板与文档同步。

- **三个分析模块缓存 TTL 统一为 4h**：`expert_review`（2h→4h）、`health_check`（24h→4h）、`penetration_deep`（24h→4h）。取数侧默认值、缓存注册表（清理/配置派生同源）、生成配置的模板与文档全部同步；4h 在「日内变化要看得到」与「每次重算都是钱」之间取平衡，仍可在 `config.json → cache_ttl` 逐项覆盖。

- **新闻去重提速（判定不变）**：比较串与字符多重集按标题缓存，并先用「字符多重集上界」跳过不可能命中的标题对（不再为每个远低门槛的对构造两个 `SequenceMatcher`）；等价性由「换回旧实现跑同一语料、保留集合逐条一致」的回归锁定。

- **财报章节探测负缓存**：带 section 的探测遇 404 后记 12h 负缓存（`datasink_probe_miss_*`），同一天的后续报告不再逐章节重发请求（7 只标的 × 多候选章节的 404 曾占十余秒）；文档级 404 仍按告警处理、不进负缓存。

- **缓存 TTL 读侧与清理侧对齐**：`self_review` / `holding_change` 的读侧 TTL 此前未登记映射、静默回落到 `llm_global_macro`（24h），而缓存清理按注册表 7200s 判定——2h 后启动清理把读侧仍认为有效的文件删掉，下一份报告白重算一次自检/归因。现两侧统一为 24h（内容寻址：键含上游正文，输入未变即命中），并由逐模块校验用例锁死「读侧 TTL == 注册表 TTL」。

- **财报正文缺失不再每份报告重走链路**：某标的在章节阶 + 备源两阶都取不到正文时，按标的记 6h 负缓存（`report_symbol_miss_*`），同一天的后续报告直接复用同一原因、跳过索引与候选探测（此前 5 只标的约占 3s/份报告）；索引为空/网络失败不入缓存。

- **行业资金流向失败负缓存**：源不可达/返回空后本会话 5 分钟内不再重试（akshare 内部本已重试 2 次），后续报告直接按「不可用」降级，失败原因仍如实上报、不复用过期成功数据。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.5（2026-10-24 ~ 2026-10-25）
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
