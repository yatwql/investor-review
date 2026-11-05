# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.2-dev
> **编号源**：`rf-next = 1047`（新增问题提出后更新为 +1；已用最大 rf-1046，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**本轮盘点口径**：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」。**已核对为无兼容面的部分**（不入待办）：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属第三方变体（见 rf-1033 边界）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1155 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 905 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 825 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 852 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 853 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 729 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 997 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；余量约 6 行，下一项报告页改动即触线 |

## 已解决问题

### 开发期已修复（0.17.2-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复 |
|---|------|------|
| **rf-1046** | 走势终点由滞后净值构成（QDII T-1/T-2）时，口径差异只在日志 WARNING 与数据源状态章可见；读者在「组合历史走势与回撤」章看到的末端日收益/最大回撤仍会被当准确值 | `STATUS_MESSAGES["history_nav_stale"]` 补上口径后果（末端日收益与最大回撤会偏低、终点附近数字仅供参考）；HTML 该章首与 Excel 页签顶部各加一块「读数口径提示」（逐标的滞后交易日数与占比）；手册报告说明同步。补 4 例单测（HTML 正反向渲染、Excel 提示行与无滞后不写） |
| **rf-1045** | 缓存清理与读侧共用盘中 30s TTL，行情类缓存刚写入即被判过期删除，下一轮再写一遍——每轮启动与收尾反复预览 22~63 个待删文件，删除对读侧无收益，只放大未命中统计并制造「缓存反复失效」假象 | 新增 `cache/_ttl.get_cleanup_ttl()`：**忽略盘中覆盖**按静态 TTL 判过期，清理侧改用它；读侧 `get_ttl` 不变（新鲜度不受影响）。technical 接口表与 TTL 章补「读写两侧判据不同（设计意图）」。补 2 例单测（盘中 60s 行情不被清、读侧仍判过期） |
| **rf-1044** | 「刷新基础缓存」`clear_by_group("refresh")` 清整组 19 个模块，但流程只回填其中 10 个——财报索引/正文、财务指标、市场情绪、新闻逐条分析、费率、估值、无风险利率被连坐作废，要等下一次出报告才逐只回源（实测一次刷新后紧接的报告多付 267 次请求、墙钟 134s、命中率 35%，同日前序运行均 95~99%） | `clear_by_group()` 新增 `only` 参数（按缓存前缀/精确键名限定域），`update_basic_cache` 传 `_BASIC_REFRESHED_CACHE_KEYS`（本流程真回填的 10 个域）；手册 `[1]` 段落区分「会清」与「未连带清」两清单，technical 接口表与菜单表同步。补 2 例单测（only 限定保留未列域、编排层只清回填域） |
| **rf-1043** | 批量 LLM 全批失败与「全缓存命中」同形（用量字典零值），批次级成败不回传、日志只到 WARNING——实测一次 provider 双链熔断后 3/3 批全失败、41 条新闻 0 条含分析，日志仍写「生成完成」，报告侧模块状态无从判定；全链不可用也只到 WARNING，12 天日志 0 条 ERROR | `_execute_and_merge_batch` 回传本批解析条数，`run_batch_mode` 聚合 `ok_batches`/`failed_batches`/`total_batches` 入用量字典并分级留痕（全失败 ERROR、部分失败 WARNING）；`_finalize_news_token_usage` 按批次成败区分「完成」与「全部批次失败」并显式声明该模块将标为失败；`api.py` 全 provider 失败升 ERROR 并带已尝试链。补 3 例单测（全失败零 ok 批、有产出零失败批、全失败不落模块用量行） |
| **rf-1042** | 事件窗行降级主因是「映射交易日不在行情轴」——索引扩面后能匹配到更多新闻，但行情取数窗口写死 365 天，事件日更早的新闻整条降级（实测一轮 23 条降级中占 19 条） | 新增 `history_days_for()` 按**最早事件日**推导窗口（回看天数 + 后窗余量 + 30 天缓冲，夹在 [365, 1095] 内），默认股票与基准取数器改用该窗口，短窗新闻仍按 365 不额外拉数；补 3 例单测锁定基线/放大/夹上限与默认取数器请求值。同时修另一半成因：事件日晚于行情轴末日（当日 K 线未落地）时原本整条降级，改为按末日对齐并标注（`anchor_shifted`/`align_note` + 视图计数行），实测一轮降级 23→4、可出行 36→50（触 50 行上限 capped 4） |

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-05）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
