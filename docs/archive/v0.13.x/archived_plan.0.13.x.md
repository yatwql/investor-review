# 计划归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布后开发期完成项并入，0.13 系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.13.x 开发期完成项
> 归档内容：由各任务完成后人工迁入

---

## plan-130 应用内定时生成（免外部任务计划） ✅

**完成（2026-10-18，v0.13.6-dev）**：Web 工作台配置页签新增「定时生成」调度面板（执行日/时刻/报告类型/启用开关），保存写入 `config.json` 的 `scheduler` 块（缺省关闭；`_DEFAULT_CONFIG`/配置模板/`how-to-config.md` 字段总表同步）；服务端新增 `web/scheduler.py` daemon 调度线程每 30s 重读配置评估触发窗（宽限 30 分钟内顺延活动任务、超时登记错过），触发即向 RunManager 提交「正式-用存量」生成——与手动生成同队列同 worker 串行，复用生成入口自动清理与完成链路；触发账本按「计划签名+日期」原子写 `data/state/scheduler_fired.json`（损坏兜底 + `_path_isolation` 重定向）；`GET/POST /api/scheduler`（校验 400 / 同源守卫 403 / 写失败 500）；服务器/容器场景的 CLI cron 替代方案见 Web 手册 §5.4。回归用例：`src/test/unit/web/test_scheduler.py`（解析/触发窗/账本/API/面板接线 + 前端源结构断言），需求登记 R-WEB-12。

## plan-127 HTML 报告无打印/PDF 导出入口 ✅

**完成（2026-10-18，v0.13.6-dev）**：报告右上角新增浮动「打印 / 导出 PDF」按钮（`report-print-btn`，主题切换 🌙 左侧，44×44 触控目标、`--primary`/`--primary-hover` 语义 token、`window.print()` 唤起浏览器打印/另存 PDF），打印稿经独立 `@media print` 规则自隐藏（不动既有浮动控件隐藏清单）；补模板结构/可访问性/触控尺寸/打印自隐藏回归用例（`test_html_template.py::TestHtmlPrintButton`），`reports-instruction.md` 交互功能清单同步入口说明。

## plan-126 性能对比、机读输出与阈值门禁 ✅

**完成（2026-10-15，v0.13.4-dev）**：`perf-view.py` 获得 `--compare A B`（阶段级中位 delta/倍数 + 变异系数判显著，噪声带内不判回归）、`--json`/`--csv` 机读输出、`--gate` 阈值判定（退出码 0/2）。**门禁归属修正**：CI `perf-gate` 门禁由主动压测 `perf-test-report.py --gate` 承担（同条件可比），历史视图不做门禁——样本不可控、不可复现、测环境不测代码。后续增强：`--json` 升级信封 `{record_count, records, summary}`（与 Markdown 各段同源）、CSV 增归一/离群/最慢阶段列。

**落地设计**：[`perf-observability-design.md`](perf-observability-design.md) §9（门禁归属决策）· §10（输出增强）——设计文档已随 v0.13.4 发布归档于本目录。

## plan-125 运行上下文维度采集（provider/缓存/等待/用量） ✅

**完成（2026-10-15，v0.13.4-dev）**：`perf_history.jsonl` 记录增 `llm` 字段（provider/model/thinking 档、重试与退避等待秒数、端点节流等待、provider 降级、模块级缓存命中、逐模块 tokens/费用）。`llm/observation.py` 汇聚器（`bind_llm_observation`/`current_llm_observation`，线程安全）在调用链归集：`core/retry.py` 退避观察点、`llm/pacing.py` 节流门、`llm/api.py` provider 链、编排层预检、`llm/session.py` 单源用量；未绑定时全链空操作。`perf-view.py` 增「LLM 运行上下文」段——直给「时间花在白等还是真推理」。

## plan-124 性能视图稳健统计与归因 ✅

**完成（2026-10-15，v0.13.4-dev）**：离群点标注（中位 + k × 1.4826 × MAD，`--outlier-k` 可调）与 `--exclude-outlier` 稳健口径、稳健均值（仅存在离群点时与普通均值并列）；阶段级 P50/P95/P99；尾部归因（最慢一次运行逐阶段 z 分数直给「哪步超常、超多少倍」）；`--by day|week|hour` 时段聚合。

## plan-123 运行观测打点补齐（LLM 模块级细分 + full 埋点补回 + 诊断落盘） ✅

**完成（2026-10-15，v0.13.4-dev）**：`core/perf.py` 增线程安全 `PhaseBreakdownRecorder`，快照带 `breakdown`/`counters`（**不参与 `total_seconds`**，保历史可比与 ETA 口径）；LLM 四模块与新闻获取逐子项耗时入 `breakdown["LLM+新闻"]`；full 路径 `_report_output.py` 两个 helper 补 HTML/Excel 阶段埋点；首个阶段计时时挂只计数日志 handler、`save()` 摘除，WARNING/ERROR 自动入 `warnings_count`/`errors`/`counters`（根因修复「诊断字段恒空」）；`perf-view.py` 增阶段细分表。

## plan-122 脚本目录优化批次（审计落地） ✅

**完成（2026-10-13）**：scripts 全目录审计（67 文件/16,397 行）后六项优化全部落地：

1. **release.py 拆 `_release/` 内部实现包**（869→517 行，距 1000 行红线余量充足）：`_common`（ReleaseError / 子进程执行原语）、`_versioning`（版本号解析/渲染纯函数 + 归档名派生）、`_changelog_archive`（发布段迁出与归档追加，纯文本变换）、`_evolution`（演进快照统计与表格回写）。入口保留 CLI 面、命令壳与路径常量——下沉模块只收显式参数，测试对入口模块属性的重定向始终生效；测试引用的符号（`_SECTION_NOTE`/`_line_count` 等）经原名 re-export 保持可达。
2. **文档路径常量上收 `_checklib`**（`MANAGEMENTS_DIR`/`MANUALS_DIR`/`PLAN_DOCS_DIR`/`ARCHIVE_DOCS_DIR`）：check-doc-traces / check-version-consistency（13 处）/ check-requirement-trace / check-semantic-index / check-task-numbering 与 `_doc_drift` 内部包的内联拼路径收编；各脚本的受检清单与豁免策略仍归各自持有。
3. **契约规则② 消费侧盲区封堵**：`check-script-contract` 增加 `args.verbose` 被消费的 AST 检查（防空开关）；`check-svg.py` 空 -v 实现消费（geom 逐文件 finding 计数、pixel/text 检查参数回显）。
4. **同次运行双扫消除**：check-doc-traces 受检文档两态列表一次构造复用（四遍 rglob → 一遍）；check-doc-drift `-v` 模式扫描结果复用首轮（二次全量读消除）；check-semantic-index 指纹输入面与 run_checks 扫描面同源（双 rglob 收敛）。
5. **演进统计二次读消除**：`build_evolution_stats` 首轮读文件时顺带累计 `def test_` 计数，测试文件全量二次读删除。
6. **sh 启动垫片加固**：cli.sh / launch.sh / llm.sh 加 `set -euo pipefail`。

**验收**：`check-script-contract -v` 全绿（15 顶层脚本）；守护五脚本（doc-traces/version-consistency/requirement-trace/semantic-index/task-numbering）冒烟全绿；`test_release_tool.py` 56 例 + 守护测试全绿；ruff 零告警。

**审计同时确认的不建议动项**（风险 > 收益，留档备查）：钩子脚本接入 `_checklib`（无 CLI 面，退出码语义不同）、sys.path 样板（1 行鸡生蛋解）、各脚本表格行解析上收（行级正则列语义各异）、分级退出码归一（动门禁语义）、`_checklib` 结论缓存重构（stat 指纹成本近零）、check-doc-traces 与两个 ~560 行文件拆分（离红线远，拆包只换行数不换复杂度）。

---

## plan-90 持仓成本相对历史价格区间位置 ✅

**完成（2026-10-14，v0.13.2）**：复用既有行情缓存补齐「只维护持仓、无交易流水」下 `每份成本` 相对历史价格区间的量化呈现（高位≈追涨 / 低位≈布局），填补此前只能逐格读数人工判断的空白。指标 `cost_position_pct = clamp((每份成本 − 窗口最低价)/(窗口最高 − 窗口最低), 0, 1)`，近 20 交易日 / 260 交易日（≈52 周）双窗口；`high==low`（停牌/极窄波动）取 0.5 中性值，成本越界 clamp。

**落地**（不新增报告章节，在「持仓明细与分类」页签两区块末列追加条件列）：

- 纯计算 `src/python/analysis/cost_position.py`（clamp / 中性值 / 窗口切片，无 I/O）
- 编排 `src/python/report/cost_position.py`（复用 `PortfolioHistoryCalculator.calculate_for_holding`，长窗口一次取数 + 短窗口同源切片；行情缺失静默隐列不阻断报告）
- 功能开关 `cost_position`（`GROUP_ANALYSIS`，默认开，`affects_report`）；口径脚注随呈现（成本均价近似买入价 + 窗口参数 + 公式）
- Excel 条件列接线 `holdings_detail_sheet`（`_MV_COST_POS_HEADERS`/`_CAT_COST_POS_HEADERS`/`FMT_PERCENT`）；44 例测试（纯计算/契约/渲染 + 边缘退化/非有限值）

**落地设计**：`docs/archive/v0.13.x/holding-cost-position-design.md`（随本次归档迁入）

**自审去重（rf-685）**：`extract_closes` 收敛复用 `valuation_percentile.extract_closes` 共享单一事实来源，区间有效性过滤统一到 `compute_window_position`。
