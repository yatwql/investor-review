# 计划归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布后开发期完成项并入，0.13 系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.13.x 开发期完成项
> 归档内容：由各任务完成后人工迁入

---

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
