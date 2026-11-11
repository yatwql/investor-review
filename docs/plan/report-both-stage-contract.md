# both 报告路径拆分 —— 结构契约（plan-249）

> 状态：立项（未开工）
> 对象：`src/python/report/_generation_both.py::_generate_report_both`（388 行）
> 关联：`plan.md` → `plan-249`

## 1. 立项背景

`both` 路径是「HTML + Excel、不含 LLM」的完整管线：五个 perf 阶段串行、一份 report_run 生命周期、后台健康检查、两份产物各自成败。当前 388 行把「阶段编排」「阶段实现」「成败收口」混在一处，最贵的信息——**阶段名与顺序**——只体现在 `perf.start("…")` 的字面量里，改动没有任何结构信号，而它恰恰是 `perf_history` 跨版本对比的口径。

## 2. 现状结构（阶段与生命周期）

| 顺序 | perf 阶段 | 说明 |
|---|---|---|
| 0 | — | `PerfCollector(...)` 构造 → `bind_perf` → `start_report_run` |
| 1 | `行情获取` | 轻量行情，无指数/穿透/分类 |
| 2 | `快照对比` | 始终执行（含首次运行降级） |
| 3 | `历史走势` | 条件获取（`fetch_history`） |
| 3b | `PERF_PHASE_ASSEMBLY` | 判断依据块装配（与 3 同段内） |
| 4 | `HTML 生成` | 含「图表数据装配」子记录与 `close_html_generation_stage` |
| 5 | `Excel 生成` | 独立成败 |
| 收尾 | — | `finish_report_run(perf)`，返回 `ReportResult` |

## 3. 结构契约

| # | 契约 | 违反后果 | 守护方式 |
|---|---|---|---|
| 阶段表 | **阶段名与顺序固定**，且以显式阶段表表达；新增阶段只能在表中插入 | perf 历史断档：同版本前后耗时不可比、门禁阈值失义 | 结构用例断言阶段表名字序列与实跑 `perf.phases` 键序列一致 |
| 阶段配对 | 每个 `perf.start(X)` 必有配对的 `perf.stop()`，异常路径也要收口 | 阶段耗时被漏记或串到下一阶段 | 用例：注入阶段内异常，断言所有已开阶段均被 stop |
| 运行生命周期 | report_run 生命周期单点：`start_report_run` 最先、`finish_report_run` 最后（失败/中断同样落 status） | 运行记录缺头或缺尾 → 运行历史与实际不符 | 既有运行记录用例 + 异常路径用例 |
| 双产物成败 | HTML 与 Excel **成败互不连带**：任一失败仍产出另一份，`ReportResult` 的 `html_ok` / `excel_ok` 各自准确 | 一份失败导致两份都不出，或标志位谎报 | `test_orchestrator_generate_report_both` 现有用例 + 单侧失败用例 |
| 健康检查不阻塞 | 后台健康检查 spawn 后**不阻塞主路径**，其结果收集失败不影响报告 | 健康检查慢源拖住整份报告 | 现有 `_spawn_health_checks` 用例 |
| 快照捕获口径 | 快照捕获走 `capture_snapshot`（含正式源守卫与命名空间闭环），不在本函数内自判 | 合成/演示持仓写入真实快照历史（历史事故） | `test_snapshot_namespace_consumers` 现有用例 |

## 4. 拆分方案（目标形态）

- 保留 `_generate_report_both` 为**编排壳**（阶段表遍历 + 生命周期 + 成败汇总），目标 ≤ 100 行；
- 五个阶段各自成 `_stage_*.py` 函数模块（`_stage_quotes` / `_stage_snapshot` / `_stage_history` / `_stage_html` / `_stage_excel`），输入输出用显式小契约（阶段只返回本阶段产物与成败）；
- 阶段表 `_BOTH_STAGES` 成为唯一阶段定义处（名字 + 实现 + 是否条件执行）。

## 5. 验收口径

1. 结构用例：阶段表名字序列 == 实跑 `perf.phases` 键序列；异常路径不遗留未 stop 阶段；
2. `basic` / `both` 两条路径的既有场景用例全绿；`perf_history` 记录的阶段名与拆分前逐字一致；
3. `_generate_report_both` ≤ 100 行；
4. `test-perf-report.py --gate` 达标（basic ≤ 60s，拆分为纯结构调整，不得引入耗时回归）。

## 6. 风险与回滚

- 风险：「阶段配对」的收口（异常路径遗漏 stop）与 report_run 生命周期收尾。缓解：先写「阶段须成对」的用例，再改代码。
- 按阶段逐个提交，harness 不变；任一阶段出问题只回退该阶段。

## 7. 非目标

- 不改行情/快照/历史/HTML/Excel 各阶段内部实现；
- 不动 `_generation_full.py`（含 LLM 的 full 路径）与 `_generation_basic.py`；
- 不改 perf 记录格式与门禁阈值。
