# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.3]**（2026-10-15）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.4-dev] - 开发中（未发布）

### Changed

- **性能门禁可靠性：压测脚本网络无关性与状态隔离**：`perf-test-report.py` 三阶段的外部网络咽喉全部桩掉——行情（`fetch_market_data` 两处绑定）、K 线历史链（`chain`/`chain_incremental.fetch_with_incremental_fallback`，流动性检查/风格因子/事件面板逐仓拉历史都经它）、交易日历（`trading_calendar._get_trading_calendar`，模块唯一网络出口）；断网实测 Phase1 47.3s→2.3s、Phase3 89.5s→2.1s（此前 CI 门禁红正是因为冷缓存下 K 线重试退避拖过 60s 阈值，测成了网络状况而非代码性能）。同时新增 `_isolate_state_writes()`：基准运行的 perf 历史/数据源健康快照重定向到临时目录，不再污染 `perf-view` 的统计样本；Phase 2 新闻/财报抓取保留真实网络（断网自动降级已验证，且不入门禁判定）。

- **性能门禁归属修正 + 视图输出精简**：① 性能门禁改由**主动压测**脚本承担——`perf-test-report.py` 新增 `--gate`（未达标退出码 2，与检查脚本契约一致），CI 新增阻塞型 `perf-gate` job（basic 模式 ≤ 60s，并上传性能报告产物）；② `perf-view.py` **移除 `--gate`**——它是运行历史查看（被动统计既有记录），样本取决于最近跑过什么、不可复现，不适合做门禁（同一份代码跑 10 次与跑 3 次的 P95 不同，且混入 LLM 服务端延迟/网络/机器负载等与提交无关的因素）；③ `perf-view.py` 新增 `--summary`（仅输出概览段，略去逐版本分组详情，记录多时避免输出过长）与 `--outlier-k`（自定义离群判定系数，默认 3.5）；④ 稳健均值改为**仅在存在离群点时**与普通均值并列展示（无离群时两者相同，并列属冗余）。

- **性能对比、机读输出与阈值门禁（plan-126）**：`perf-view.py` 新增 `--compare 旧版本 新版本`（阶段级中位 delta / 倍数 / 变异系数判显著——变化幅度需超过两版本各自变异系数之和 × 较大中位值，避免把运行抖动当回归）、`--json` / `--csv` 机读输出（完整记录 / 逐运行一行）、`--gate 秒` 阈值门禁（P95 总耗时超限退出码 2，与检查脚本契约一致，可挂 CI 拦截真实运行的性能回归；P95 口径对单条离群不敏感，配合 `--exclude-outlier` 可只看正常运行）。

- **运行上下文维度采集（plan-125）**：`perf_history.jsonl` 记录新增 `llm` 字段（provider/model/thinking、重试次数与退避等待秒数、端点节流等待秒数、provider 降级次数、模块级缓存命中/未命中、逐模块 tokens 与费用）。新增 `llm/observation.py` 运行观测汇聚器（`bind_llm_observation`/`current_llm_observation`，线程安全），在调用链上归集：重试退避（`core/retry.py` 的 `on_retry`）、端点节流等待（`llm/pacing.py` 的 `PacingGate`）、provider 命中与降级（`llm/api.py` provider 链）、模块级缓存命中（编排层预检）、逐模块 model/tokens/费用（`llm/session.py` 单源）；未绑定汇聚器时所有记录调用为空操作（单测直调 LLM 层行为零变化）。`perf-view.py` 新增「LLM 运行上下文」段（等待/重试/降级/缓存/费用与 provider/模型分布），回答「时间花在白等还是真推理」。

- **性能视图稳健统计与归因（plan-124）**：`perf-view.py` 新增离群运行段（总耗时 > 中位 + 3.5 × 1.4826 × MAD 判离群，MAD 为 0 时不判；显式列出而非静默剔除）、稳健均值（剔除离群后均值，与普通均值并列）、阶段级分位（阶段表增中位与 P95）、尾部归因（最慢一次运行逐阶段 z 分数与相对历史中位倍数，直给哪一步超常）、时段聚合（`--by day|week|hour`）；新增 `--exclude-outlier` 按稳健口径剔除离群后重算全部统计。实测：126 条历史中自动标出 6636s 那条服务端超时运行，尾部归因定位到 `LLM+新闻` 22.37× / z=+6.14，剔除后均值由 519.7s 降至 362.9s。

- **运行观测面扩充（plan-123）：LLM 模块级细分 + full 埋点补回 + 诊断落盘**：`perf_history.jsonl` 记录新增 `breakdown`（父阶段下的子项自身耗时）与 `counters`（运行期诊断计数）两个旁路观测面，**不参与 `total_seconds`**（保历史可比与 ETA 口径稳定）。`core/perf.py` 新增线程安全 `PhaseBreakdownRecorder`（`PerfCollector.recorder(父阶段)` 取用，四模块在线程池并发写不丢计数）；`LLM+新闻` 阶段细分到四个 LLM 模块与新闻获取（`_llm_dispatch` 逐模块计时、`_llm_news` 新闻获取计时，`span_recorder` 为可选参数，None 时行为零变化）；full 路径 `_report_output.py` 两个 helper 经 `run_integrity.current_perf()` 补回 `HTML 生成`/`Excel 生成` 阶段计时（此前 full 运行丢失这两个阶段，实测 126 条历史中二者各仅 6 条且均早期版本）；`errors`/`warnings_count` 由「恒空」改为自动采集——首个阶段计时时挂只计数日志 handler、`save()` 摘除，WARNING/ERROR 自动入 `counters`（错误消息封顶保留，计数照常累加）。`perf-view.py` 分组段新增「阶段细分」表（旧记录无 `breakdown` 时不渲染空表）。方案与口径见 [`perf-observability-design.md`](../plan/perf-observability-design.md)。

- **perf-view 新增 P95/P99 分位概览**：`scripts/perf-view.py` 输出新增「总体分位概览（跨版本）」表（口径 / 样本数 / 平均 / 中位 / **P95** / **P99** / 最长），并在每个版本分组段直给「95% 的报告在 Xs 内完成，99% 在 Ys 内完成」。分位采**最近秩**（`ceil(pct% × n)` 位样本值）口径，含义即 95% / 99% 的报告生成在该耗时内完成。新增 `_percentile()` / `_total_summary()` / `_overview_lines()`，过滤逻辑抽为 `_filter_records()` 与分组共用（`--report-type` / `--last` 对概览同步生效）；单一报告类型时只渲染合计行，不重复出类型行。同步文档：developer-guide「perf-view」段（分位口径说明 + 脚本清单）与 how-to-use-cli-mode 性能历史小节。回归 = `test_perf_view.py` 新增分位口径 / 汇总字段 / 概览表结构 / 分组完成时间四组用例。

- **developer-guide 核对更新：补发布归档迁移四项 + release 收尾 sync 口径**：对照近期变更核对开发者指南，修复 4 类缺口——① 版本发布流程五步→六步，新增步骤③「发布归档迁移（四项强制）」（rf/plan 完成态/changelog 段/docs-plan 设计文件四项，未完成不得继续 `gate`/`publish`——此前指南完全缺失该强制项），原③④⑤顺延为④⑤⑥并修正步骤间互引用；② 发布类命令注释与编排提示补 `prepare`/`evolution` 收尾自动 `check-doc-drift --sync` 实况（rf-686 后口径同步），并明示归档迁移保留人工且须前置；③ 「② 发布数据文档刷新」补 `evolution --release` 输出「需人工核对注释行」的回填义务（test-coverage 用例收集口径 + folders.md 文档目录分解数）；④ 新增测试指南「新增后必须更新的文件」清单补第 6 条 conftest 隔离 fixture（模块级单例 autouse 复位、持久化/输出路径在 `_isolate_sensitive_paths` 重定向，指向 CLAUDE.md「新增测试隔离要求」细则）。新增段落措辞经 `check-doc-traces` ARCHIVE 规则复核（面向读者文档不写归档目录/文件名）。

- **`perf-report.py` 更名 `perf-test-report.py`**：与「历史趋势查看 `perf-view.py`」对仗，突出其**基准测试**定位（自造模拟持仓跑 basic/both 管线、mock LLM，输出 `docs/tmp/better-investment-performance-test-report.md`）。`git mv` 保留历史，同步更新脚本自引用、`core/perf.py` 分层注释、`_traces_code/patterns.py` 注释、developer-guide 脚本清单与诊断段、folders.md 目录树；配套测试同步更名 `test_perf_test_report.py`（fixture 名与 `load_script` 入参随改），`test_script_loader.py` 的模块名派生断言随新文件名（`perf_test_report`）更新。

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.3（2026-10-13 ~ 2026-10-15）
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
