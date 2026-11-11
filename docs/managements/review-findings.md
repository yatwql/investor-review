# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.9-dev
> **编号源**：`rf-next = 1125`（新增问题提出后更新为 +1；已用最大 rf-1124，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1187 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 863 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 847 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 856 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 825 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 719 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.9-dev）

| # | 问题 | 修复 |
| --- | --- | --- |


> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。
| **rf-1117** | 发布台账归档在「行首编号未加粗」时静默返回 0（表现为「该版本已迁档，跳过」），v0.17.8 发布因此漏搬 10 条自审条目至归档，gate 前置断言才发现 | `apply_rf_archive()` 增加 `logging` 告警（点名编号需加粗），补 `caplog` 用例；v0.17.8 归档条目已按原表搬运补齐 |
| **rf-1118** | 报告运行日志排查出的四类缺陷：①`test-perf-report.py` 状态隔离漏 `HISTORY_SNAPSHOT_DIR`，合成持仓快照污染真实历史（按日去重当权 2026-11-06 最后一个快照 → 代码重合度 0.09，两段区间交易事件永久跳过，180 天不自愈）；②`_unverified_percentages` 纯子串匹配，把合法的分项合计（18.43+13.17=31.60）判成幻觉并上屏「无法核实」；③事实校验修正值按一位小数上屏，与摘要两位小数口径互斥（20.66 → 20.7），矛盾由修正本身制造；④自检持仓摘要不含收益率，核不了收益率声称 | ①补快照目录隔离 + `snapshot_namespace="bench"` 双保险，删污染快照，补 3 条回归（含命名空间不可见性）；②百分比核对允许 1~3 项加减组合（容差 0.02pp，残差搜索），分项推不出的仍标出；③`_format_rate_pct` 统一两位小数并剥精度零（`FACT_CHECK_RULES_VERSION` → `fact-rules-7`，同步 4 个测试文件的期望值）；④摘要行补 `收益率 {rate:+.2f}%` |
| **rf-1119** | 近 50 小时变更审计的测试基建技术债：①`_freeze_market_bucket_for_cache_asserts`（autouse 夹具）在 11 个缓存相关测试文件各复制一份同名同体，口径调整要改十一遍；②`test_perf_history*.py` 两个分片各复制一份 `fixture_mod` + `_records`（记录形状改一处要改两遍）；③`scripts/_test_runner/runner.py` 失败详情落盘失败时 `except Exception: pass`，诊断链在该步静默断掉 | ①夹具收口到既有 `src/test/unit/llm/_cache_fixtures.py`，11 文件改为顶部导入即生效；②新增 `src/test/unit/scripts/_perf_history_fixtures.py` 承载共享成员；③改 `except OSError` + 上报「详细日志写入失败（原因）」，补回归（落盘失败留痕且不改判定）；④顺手清掉 `test_generate_all_llm.py` 里 5 处以 `[]` 充 `dict` 形参的类型噪声 |
| **rf-1120** | 告警可靠性两处缺陷：①基准跑只隔离了状态文件、未隔离日志路径，按设计禁网的一轮把 **1347 行**「连接失败」告警写进真实 `logs/app.log`，真实告警密度被冲淡到只能逐行筛字才能还原；②巨潮资讯健康探针把「负缓存命中」报成同一句「未解析到 orgId」，使探针失败率虚高（实测 23.7%），把「等窗口过期」的已知降级态读成「源在持续抖动」 | ①`test-perf-report.py` 增 `_isolate_log_writes()`（`INVEST_LOG_PATH` + `INVEST_RUN_CONTEXT=perf`，`setdefault` 尊重外层覆盖，须在导入任何 `src` 模块前调用），补 3 条回归（含子进程端到端验落盘路径）；②`cninfo` 导出 `ORGID_MISS_CACHE_REASON_PREFIX`，探针据此分「近期已失败、本轮按负缓存跳过」与「本轮真失败」两种文案，补 2 条回归 |
| **rf-1121** | 行业资金流向是唯一没有健康探针的数据面（走 akshare 双通道 + 负缓存 + 陈旧回退，不在 Provider Chain 里），退化后只能翻日志发现——上一轮也正是靠日志才看出东财 push2 连续失败 | `akshare_extras.probe_sector_flow_channels()` 逐通道直连探测（**不读不写缓存、不返回陈旧回退**，否则测到的是缓存而非源），`check_sources._check_sector_flow()` 按全通/部分/全挂三态上报，补 3 条回归（三态文案 / 零缓存触碰 / 单通道异常不连坐） |
| **rf-1122** | 近 40 小时变更审计：①百分比 token 在 `llm/` 下有四份写法（`self_review._PCT_RE`、`_cross_module._PCT_RE`、`_context._BREAKDOWN_PART_PATTERN`、`_patterns._PERCENT_PATTERN`），改一处符号/空白容错另一处不跟，两个检查会互相打脸；②`_coverage.reset_numerical_coverage` 的 docstring 声称「每次 `run_fact_check` 前调用」，实际只有离线重放调用、报告主路径不复位也不消费，注释与实现相反 | ①`_patterns` 新增 `_SIGNED_PERCENT_PATTERN`（命名组 sign/num）并让跨模块判定与自检引用核对共用，`_context` 的分项模式改指 `_PERCENT_PATTERN`（语义同为「只需幅度」），补单源结构断言；②docstring 改为现状口径（复位权在调用方，逐报告重放先复位再统计全模块） |
| **rf-1123** | `fact_checker` 三个长函数把语义埋在控制流里：`_evaluate_percent_impl` 246 行（判定顺序=口径，却只存在 in-line if 链中，改顺序无任何结构信号）、`check_numerical_consistency` 133 行、`run_fact_check` 205 行（三项检查+修正+摘要混在一处） | `_evaluate_percent_impl` 拆为 `_GUARD_STEPS` 有序元组（11 个 15~66 行步骤 + `_emit_rate_issue` 终态单点，主函数 20 行；归因中间态用 `_Attribution` 承载）；`check_numerical_consistency` 提取 `_build_detection_refs`/`_make_percent_context`（语境探测单点，23 行→78 行中含 docstring）；`run_fact_check` 提取 `_resolve_tolerance`/`_extract_max_drawdown`/`_run_checks`/`_apply_auto_corrections`/`_build_summary`（205→87 行）；补 3 条结构契约用例（步骤唯一可调用 / 首末锚点与 emit 不在链上 / 每步返回形态） |
| **rf-1124** | 近 96 小时变更审计：`scripts/_eval_factor_zoo/metrics.py` 一边注释声明「因子公式与生产层同源、各拷一份会漂移」，一边保留 `_closes` / `_mean` / `_rolling_beta` / `_daily_returns` 四份本地拷贝——生产口径改了评测仍跑旧公式，评出的通过率是假数 | 四份拷贝删除，改为从 `src.python.analysis._factor_formulas` 导入（与其余 6 个原语同源）；补身份断言用例（`is` 比对，挡住「同名副本」这类漂移）；其余检查项无债：96h 触及的生产代码无死私有函数、无跨文件同体副本（除报告层 `_tracker()` 这一文档化取数接缝）、无静默吞异常（`test-runner.py` 的控制台兜底带注释且发生在日志可用之前） |

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-10）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-13 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-13）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-15 ~ 2026-10-02）
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
