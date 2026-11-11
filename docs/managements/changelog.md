# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.8]**（2026-11-10）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.9-dev] - 开发中（未发布）

### 修复

- 台账归档静默跳过加诊断（rf-1117）：`apply_rf_archive()` 在「节在、表也在、但行首编号未加粗」时返回 0，表现为「该版本已迁档，跳过」，发布漏搬无迹可寻——现留 `logging` 告警点名「编号需加粗」；补一条 `caplog` 用例
- 基准跑不再污染真实持仓快照历史（rf-1118）：`test-perf-report.py` 的状态隔离漏了 `HISTORY_SNAPSHOT_DIR`，合成持仓（23 只/2 账户）落进共享主目录后按日去重当权当天最后一个快照，`holding_change_events` / `portfolio_evolution` / `trade_cost_model` 把真实序列判成「基线切换」（代码重合度 0.09，两段区间交易事件被永久跳过且 180 天内不自愈）——现补快照目录隔离 + `snapshot_namespace="bench"` 双保险，补 3 条回归；已删除 2026-11-06 那条污染快照（跳过区间归零）
- 自检的百分比核对支持算术核验（rf-1118）：`_unverified_percentages` 原为纯子串匹配，把「18.43%+13.17%=31.60%」这类合法合计判成幻觉并在报告尾部追加「无法核实」注记——现允许 1~3 项加减组合（容差 0.02pp），分项推不出的合计仍照旧标出
- 事实校验修正值与真值同精度（rf-1118）：修正值原按一位小数上屏（20.66→20.7），与摘要/其它模块的两位小数口径互斥，模型层自检随即把修正本身报成「同一实体被赋予不同收益率」——现与提示词真值块同取两位小数并剥掉精度零（`FACT_CHECK_RULES_VERSION` → `fact-rules-7`）
- 自检持仓摘要补 `收益率` 维度（rf-1118）：摘要只给市值/盈亏/占比时，自检无法核验收益率声称，只能写「摘要未给无法核实」，事实校验改出的错值也就无从对账

- 测试基建去重与诊断留痕（rf-1119）：`_freeze_market_bucket_for_cache_asserts` 原在 11 个缓存测试文件各一份，收口到 `_cache_fixtures.py`（导入即生效）；`test_perf_history*.py` 分片的 `fixture_mod`/`_records` 收口到新增 `_perf_history_fixtures.py`；`scripts/_test_runner/runner.py` 失败详情落盘失败不再 `except Exception: pass`，改为上报路径与原因（补回归：留痕且不改判定）
- 文档复核回写（rf-1118/rf-1119）：llm-technical §12.4 补「引用数值核对（逐字 + 1~3 项加减组合）」与摘要收益率维度；requirements R-LLM-12 同步该口径；developer-guide 增「持久化路径必须成套隔离（非 pytest 一次性 CLI + 按值绑定路径改模块属性 + 命名空间双保险）」；scripts-reference 补 `test-perf-report.py` 的状态隔离范围；reports-instruction 的修正明细格式改为语义说明 + 两位小数口径；另清 `test_generate_all_llm.py` 5 处以 `[]` 充 `dict` 形参的类型噪声
- 基准跑日志隔离 + 巨潮探针区分负缓存（rf-1120）：`test-perf-report.py` 新增 `_isolate_log_writes()`（`INVEST_LOG_PATH` 落临时目录 + `INVEST_RUN_CONTEXT=perf`，导入任何 `src` 模块前生效），止住禁网跑把 1347 行告警写进真实 `logs/app.log`；`cninfo` 导出 `ORGID_MISS_CACHE_REASON_PREFIX`，健康探针把「负缓存命中」与「本轮真失败」分开报，不再让失败率虚高误导排查
- 行业资金流向补健康探针（rf-1121）：此前 12 个探针不覆盖这个数据面（走 akshare 双通道 + 负缓存 + 陈旧回退，不进 Provider Chain），退化只能翻日志发现。新增 `probe_sector_flow_channels()` 逐通道直连（不读不写缓存、不返回陈旧回退），探针按全通/部分/全挂三态上报；探针总数 12 → 13
- 百分比 token 单源 + 覆盖率复位口径纠偏（rf-1122）：`llm/` 下原有一份模式四处写法，跨模块冲突判定与自检引用核对各带一份，符号/空白容错改一处漏一处就互相打脸——现统一到 `_patterns._SIGNED_PERCENT_PATTERN`（命名组 sign/num）；`_coverage` 的复位 docstring 按实际（离线重放逐报告复位）改正，补一条单源结构断言
- fact_checker 三个长函数按语义拆分（rf-1123）：`_evaluate_percent_impl` 246 行 → `_GUARD_STEPS` 有序元组（11 个步骤 + `_emit_rate_issue` 终态，主函数 20 行，顺序从控制流变成可断言的数据）；`check_numerical_consistency` 133 → 78 行（语境探测收口到 `_make_percent_context`，映射构建到 `_build_detection_refs`）；`run_fact_check` 205 → 87 行（容差/回撤/三检查/修正/摘要各自成函数）。行为零变化，补 3 条结构契约用例
- 因子评测原语改为与生产同源（rf-1124）：`_eval_factor_zoo/metrics.py` 曾一边声称同源一边保留 `_closes`/`_mean`/`_rolling_beta`/`_daily_returns` 四份本地拷贝，生产公式改动后评测仍跑旧口径；现全部改为导入，并补身份断言用例防止「同名副本」回流
- 大型函数拆分四连项立项（plan-248~251）：HTML 报告装配（397 行）、both 报告路径（388 行）、LLM 并行编排（392 行）、LLM worker 派发（256 行）各自单独立项，**先定结构契约再动代码**——四份契约文档定义不变式（顺序表/返回位序/块实例身份/阶段名与配对/失败隔离/并发闸门）与守护方式（结构用例断言结构关系 + 既有行为用例回归），并列出风险点、逐阶段回滚粒度与非目标
- LLM 并行编排拆分（rf-1125）：`generate_all_llm` 函数体 392 → 101 行，拆出 `llm/_llm_context_blocks.py`（六类上下文块单次渲染/提取 → `LlmContextBlocks` 快照，指纹与提示词共用同一实例）与 `llm/_llm_post_pass.py`（事实锚定 → 自检 → 跨模块核对的顺序落点，含 `review_text` 剥离与按位取结果）；门面保留 `_compute_module_cache_info` / `_precheck_all_modules` / `_dispatch_llm_workers` 等编排水位与全部 re-export，块渲染器与 `run_fact_check` 的 patch 点随消费方迁移。行为零变化：7 条结构契约用例拆分前后均绿，llm+integration 1780 项全过

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.8（2026-11-04 ~ 2026-11-10）
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
