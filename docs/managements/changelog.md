# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.1]**（2026-11-05）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.2-dev] - 开发中（未发布）

### 修复
- **走势/回撤章就地标出「读数口径」与 QDII 滞后明细（`rf-1046`）**：走势终点由滞后净值构成时（QDII T-1/T-2 常态，落后 ≥2 个交易日才报），口径差异原先只在数据源状态章与日志 WARNING 里说，读者在本章读到的末端日收益与最大回撤仍会被当准确值。现 HTML 该章首与 Excel 页签顶部各加一块「读数口径提示」：逐标的列出最新净值日/滞后交易日数/占比，并明写「末端日收益与最大回撤会偏低，终点附近数字只作参考」；`STATUS_MESSAGES.history_nav_stale` 同步补上后果。补 4 例单测。
- **清理侧不再拿盘中 30s TTL 判行情缓存过期（`rf-1045`）**：清理与读侧共用 `get_ttl`，盘中行情类 TTL 是 30s，于是每轮启动与收尾都把 30s 前刚写入的价格/指数缓存判死删掉、下一轮再写一遍（实测反复预览 22~63 个待删文件）；删掉的部分对读侧本就没有价值。现清理侧改走 `cache/_ttl.get_cleanup_ttl`：**交易时段内**一律按静态 TTL（不拿读侧口径删文件）；**盘后**另回收**盘中写入**的副本——盘中价只是当时的快照，盘后读侧会按静态 TTL 把它当收盘价沿用 24h，因此按**写入时刻**是否落在交易时段判定并回收，收盘后（如 15:30）写入的当日收盘值保留。交易时段判定新增 `core/market_hours.is_intraday_timestamp()` 单一承接。读侧 `get_ttl` 与新鲜度判据不变。补 4 例单测。
- **「刷新基础缓存」不再连坐作废财报/财务指标缓存（`rf-1044`）**：`[1]` 走 `clear_by_group("refresh")` 清整组 19 个模块，但该流程只回填其中 10 个，财报索引/正文、财务指标、市场情绪、新闻逐条分析、申赎费率、指数估值历史、无风险利率被一并作废，要等下一次出报告才逐只回源。实测现场：同一天前几次运行命中率 95~99%，一次刷新后紧接的报告掉到 35%（price_stock 45 / fin_indicator 42 / report_datasink 35 全未命中）、多付 267 次请求、墙钟 134s。`clear_by_group()` 新增 `only` 参数（按缓存前缀/精确键名限定域），`update_basic_cache` 传本流程真回填的域名集合 `_BASIC_REFRESHED_CACHE_KEYS`；手册 `[1]` 段落分开列「会清」与「不再连带清」两份清单。补 2 例单测。
- **批量 LLM 失败与全缓存命中不再同形（`rf-1043`）**：批量路径的用量字典在「全批失败」与「全命中」下都是零值，批次级成败完全没回传，日志只到 WARNING——现场一次 deepseek 与 opencode 双链相继熔断，3/3 批全失败、41 条新闻 0 条含分析，日志仍写「生成完成」，报告里该模块判别不出残缺；全链不可用也只发 WARNING，攒了 12 天日志 0 条 ERROR。`_execute_and_merge_batch` 改为回传本批解析条数，`run_batch_mode` 聚合 `ok_batches`/`failed_batches`/`total_batches` 入用量字典并按成败分级留痕（全失败 ERROR、部分失败 WARNING）；`_finalize_news_token_usage` 区分「完成」与「全部批次失败」并明说该模块将标为失败；`llm/api.py` 全 provider 失败升 ERROR 并打印已尝试的链路。补 3 例单测。
- **事件窗行情窗口按最早事件日自适应（`rf-1042`）**：索引扩面后能匹配到更多新闻，但行情取数窗口写死 365 天，事件日更早的新闻整条按「映射交易日不在行情轴」降级（实测一轮 23 条降级里 19 条属此类）。新增 `history_days_for()`：按最早事件日回推回看天数 + 后窗余量 + 30 天缓冲并夹在 365~1095 天内，默认股票与基准取数器同用该窗口；短窗新闻仍按 365 天，不额外拉数。另一半成因同修：事件日**晚于行情轴末日**（当日 K 线尚未落地）时原按「映射交易日不在行情轴」整条降级，改为按行情轴末日对齐并在视图计数标注（`anchor_shifted`/`align_note`），仅剩轴首缺日与关键位缺失仍降级。实测一轮：降级 23→4、可出行 36→50（当时触 50 行上限 capped 4，上限随后提到 80 后 capped 归零）。补 6 例单测（窗口基线/放大/夹上限、默认取数器请求值、末日对齐正反向）。
- **删掉旧配置键兼容层（`config/_legacy_keys.py`）**：`RENAMED` 早已为空、`REMOVED` 仅剩 `llm_usage` 一条，维护它只为给「旧键→新键/已删除」出一句处置建议。既然不保留跨版本配置兼容，整表与两处派生告警一并删除：`features.json` 未登记开关与 `config.json` 未登记章节键各自归并成一条告警（带条数与键名），手册「已删除 / 已改名的配置键」节改为「未登记的配置键」并删掉对照表。净删 1 个模块 + 1 份单测。
- **删掉两处纯兼容代码：决策头缓存后缀 `_dh` 与指纹的四个「仅为调用兼容」入参**：① 决策头缓存后缀函数恒返回 `_dh`，唯一用途是区分「未引入决策头前」的历史缓存条目——缓存不兼容后连函数与两处调用点一并删除；② `build_llm_fingerprint()` 的 `total_mv/total_cost/total_profit/total_today_profit` 早已不进哈希、只为调用兼容保留，从签名与 4 个调用点、5 处单测一并删除（行情派生量本就不该入键，注释同步改写）。两处都会让 LLM 模块缓存键一次性变化（旧条目按 TTL 自然退场），属预期。
- **兼容层复核：两处「疑似兼容」代码确认不可删，一处命名改正**：① `cache/_io.py` 的「清理另一格式文件」不是旧格式兼容——gzip 与否按**当次载荷是否超 100KB** 逐次决定，同一键可能先后落 `.json` 与 `.json.gz`，清理是防读到陈旧副本的正确性保障，保留；② `tiantian_holdings` 的「第 3 跳」不是旧接口兼容，而是「不指定年份的默认请求」取数阶梯兜底（覆盖 QDII/联接/债券），保留；其历史命名 `_fetch_legacy_quarterly` 易被误读为兼容代码，按语义化命名改为 `_fetch_default_quarter`（含 13 处引用与语义表行）。

### 变更
- **技术债清理（测试夹具下沉 + 常量单一源）**：缓存类测试里「写指定写入时刻/年龄的缓存载荷」样板散在 3 个文件各一份（改清理口径就要同步改三处），收敛到 `src/test/unit/cache/_cache_fixtures.py`（`write_cache` / `write_cache_at` / `today_at` / `pre_open_ts`）；`core/market_hours.py` 的官方交易状态缓存 TTL 由 `86400 * 7` 字面量改用 `CACHE_WEEKLY`，与缓存注册表同源。
- **报告模板内联样式去 Jinja 化（class 驱动，`rf-1047`）**：模板原把 Jinja 写进 CSS 值位置（`style="order: {{ n }}"`、`style="color: {{ x | profit_color }}"`），HTML 语言服务把属性值当 CSS 扫、单模板稳定报 28 条解析误报（此前靠 `.pi-lens.json` 关掉该服务止声）。现按「颜色→语义 class、顺序→DOM 顺序、几何量→HTML/SVG 属性」三条改写：64 处动态内联样式清零（20 处 `order` 由 DOM 顺序承载、40 处颜色/字号/字重改 class、1 处配置分布条改 SVG 属性宽度），新增 `profit_class` / `price_type_class` 过滤器与 11 个工具类（色值全部引用既有 token，暗色自动跟随）；`report_template.html` 的 include 顺序对齐 `_REPORT_SECTION_DEFAULT`（`action` 与 `data_source_status` 归位，渲染顺序与改动前一致）。`.pi-lens.json` 删除，HTML 语言服务恢复。守卫 3 条（模板静态扫描 / 渲染产物断言 / DOM 顺序与编号）；下线已无模板使用的 `profit_color` / `price_type_color` 两个内联颜色过滤器（保留并单测覆盖 `profit_class` / `price_type_class`），报告套件 2834 通过。
- **48h 变更技术债清理（口径文案单一源 / 交易日时段判定补测 / 声明清单守卫）**：① 「读数口径提示」的标题句、后果句与逐标的明细原在 HTML 模板、Excel 写入器、数据状态词三处各写一份，现由 `report/_history_quality` 定常量与拼装函数，生产侧写入 `history_data.terminal_staleness`（`headline`/`consequence`/`caveat`/`assets[].detail`），Excel 与状态词直接取用，HTML 副本由渲染用例按同一常量逐字断言；② `core/market_hours.is_intraday_timestamp()` 补边界测试（09:30/11:30/13:00/15:00 含端点，分钟外不算）并把入参放宽为 `float | str | None`（它本就容忍脏值，签名与实现对齐）；③ `_BASIC_REFRESHED_CACHE_KEYS` 增注册表守卫用例——手写域名清单一旦遇到前缀改名会静默变成空操作，现逐项断言登记存在。
- **「我的建议历史表现」补结论列与涨跌色**：原来只给命中率与均值超额两组数字，读者要自己合成判断。新增 `performance_verdict()` 按「命中率 × 均值超额」两轴出一句人话（方向有效且跑赢基准 / 方向命中但跑输基准 / 方向偏错但选品仍跑赢基准 / 方向与超额双弱），缺任一轴时只说可得轴（如「仅有超额：跑输基准」），方向性样本 < 20 时结论加「（样本不足，仅参考）」；HTML 单列展示并按超额涨跌上色，Excel 行动页签列宽 5→6 让超额（结论）列完整可见。补 4 例单测（四象限 / 缺轴降级 / 样本不足后缀 / 双端渲染）。
- **事件表行数上限 50 → 80**：事件窗索引扩面后单轮可命中 60+ 条事件行（行业级关联占大头），50 行上限会把有效行计入 `capped` 截断（实测一轮 capped 4 条、可出行止于 50）；提高到 80 留出余量又不失控，超限仍按原口径计入 `skipped.capped`，视图合计行不变。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.1（2026-11-04 ~ 2026-11-05）
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
