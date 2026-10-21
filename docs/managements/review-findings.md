# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.11
> **编号源**：`rf-next = 792`（新增问题取此编号，完成后更新为 +1；已用最大 rf-791，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）
| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-790**（已决策） | 时间戳helper三份拷贝：`core/decision_ledger.py::_now_iso` 与 `core/signal_ledger.py::_now_iso` 逐字相同（2 行），`scripts/_release/_timing.py::now_iso` 语义略异（带时区偏移，供发布台账跨时区对拍）——与 `core/jsonl_store.py` 当时抽出「避免第三份拷贝」的动机同类 | **维持现状**（**已决策，不排期**；理由如下）：两处均为 1 行表达式，且 `_timing` 那份**不能**合并（偏移有无是有意区分）；为 1 行表达式新开 `core/timeutil.py` 会引入新模块与目录树/文档改动，收益低于成本。若将来出现第三份 naive 版本再统一 |

### P3 — 持续监控：文件膨胀登记（逼近红线档：主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000；按距红线余量升序）

> **单一事实源**：行数以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序 / >400 行脚本 / >800 行测试）。本表是**逼近红线档的处置登记**——主程序 ≥700、脚本 ≥600、测试 ≥1000（余量 ≤30% 才入表），行数快照随复核刷新；警告级全集不逐项登记，复核以 `-v` 为准。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件拆分」。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线）；≥1000 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

| # | 文件 | 行数 | 距红线 | 状态与处置 |
|---|------|------|--------|-------------|
| 1 | `scripts/perf-view.py` | 983 | 17 | **最先触线**（脚本域）：采集 / 渲染 / CLI 三段下沉，逼近 1000 前必须拆（rf-774） |
| 2 | `src/test/unit/cli/test_cli.py` | 1175 | 25 | 按子命令切兄弟分片（report / cache / whatif / check-sources）（rf-775） |
| 3 | `src/test/unit/web/test_handlers.py` | 1138 | 62 | 按接口族切分（生成 / 配置 / 运行状态 / 日志）（rf-775） |
| 4 | `scripts/check-test-redundancy.py` | 934 | 66 | 八类检查各成子模块（与 finding 分类同构），入口只留编排（rf-774） |
| 5 | `src/test/unit/ui/test_tui_menu.py` | 1131 | 69 | 按菜单块切分（主菜单 / 配置子菜单 / 开关面板）（rf-775） |
| 6 | `src/test/unit/scripts/test_trace_check_scripts.py` | 1122 | 78 | 按守护拆分（code / doc / 日志支路）（rf-775） |
| 7 | `src/python/web/handlers.py` | 910 | 90 | 生成执行体可下沉 `web/run_generation.py`，逼近 980 行启动（rf-711） |
| 8 | `src/test/unit/handlers/test_handlers_config.py` | 1102 | 98 | 按配置域切分（标量 / LLM / 章节 / 开关）（rf-775） |
| 9 | `scripts/check-doc-traces.py` | 901 | 99 | 入口已薄（实现拆 `_traces_doc/`），再增检查按族下沉（rf-774） |
| 10 | `src/test/unit/report/test_fund_performance.py` | 1091 | 109 | 按能力切分（评级 / 业绩 / 持仓）（rf-775） |
| 11 | `src/test/unit/report/test_html_report_structure_content.py` | 1076 | 124 | 按章节段落切分（rf-775） |
| 12 | `src/test/unit/core/test_reader.py` | 1064 | 136 | 按读取 / 列校验 / 异常分片（rf-775） |
| 13 | `src/test/unit/scripts/test_check_doc_drift.py` | 1061 | 139 | 按机检项族切兄弟分片（trace / redundancy / crosscheck 已有先例：本章节测试与实现模块同源拆分）（rf-787） |
| 14 | `src/test/unit/report/test_summary.py` | 1057 | 143 | 按汇总块切分（rf-775） |
| 15 | `src/test/unit/llm/test_fact_checker.py` | 1047 | 153 | 按校验规则族切分（rf-775） |
| 16 | `src/python/config/features.py` | 840 | 160 | 注册表逐开关增长（每项约十行）；逼近 980 时把注册表条目与定义下沉（rf-665） |
| 17 | `src/test/unit/analysis/test_rebalance.py` | 1039 | 161 | 按成本分档 / 偏离度 / 告警切分（rf-775） |
| 18 | `src/test/unit/report/test_orchestrator_generate_report.py` | 1036 | 164 | 按管线阶段切分（rf-775） |
| 19 | `src/test/unit/fetcher/test_chain.py` | 1025 | 175 | 按链路 / 熔断 / 回退切分（rf-775） |
| 20 | `src/python/report/html_writer.py` | 799 | 201 | 域下沉 + 门面 re-export（测试 patch 改指持有子模块）（rf-626） |
| 21 | `src/python/core/code_utils.py` | 788 | 212 | 非核心判定函数（`estimate_market_cap_by_prefix` 等）可移出；当前维持（rf-79） |
| 22 | `src/python/llm/api_base.py` | 770 | 230 | 端点构造 / 请求发送 / 响应解析三段，逼近 900 首选下沉端点族（rf-773） |
| 23 | `src/python/analysis/rebalance.py` | 751 | 249 | 按「成本分档 / 偏离度 / 告警」下沉（rf-626） |
| 24 | `src/python/report/_report_generation.py` | 751 | 249 | 按「数据装配 / Excel 落盘 / HTML 落盘」下沉（rf-773） |
| 25 | `src/python/cache/operations.py` | 739 | 261 | 五职责待下沉（数据结构 / 基金刷新 / 公共缓存 / 持仓缓存 / 清理）（rf-86） |
| 26 | `src/python/report/orchestrator.py` | 734 | 266 | 按「章节调度 / LLM 编排 / 产物落盘」下沉（rf-773） |
| 27 | `src/python/config/_validation.py` | 723 | 277 | 校验规则族按「标量 / LLM / 章节」三域分文件（rf-773） |
| 28 | `src/python/report/fund_performance.py` | 722 | 278 | 按「评级 / 业绩计算 / 持久化」下沉（rf-773） |
| 29 | `src/python/report/holdings_detail_sheet.py` | 716 | 284 | 页签写入器，按分区块下沉（rf-773） |
| 30 | `src/python/analysis/prosperity_scoring.py` | 711 | 289 | 按「阈值表 / 评分 / 诊断」下沉（rf-773） |
| 31 | `src/python/providers/news_dedup_rules.py` | 710 | 290 | 去重规则表按来源分文件（rf-773） |
| 32 | `scripts/release.py` | 709 | 291 | 已拆 `_release/` 包；入口为 CLI 壳 + 命令编排，维持（rf-774） |
| 33 | `scripts/check-style-guardrails.py` | 636 | 364 | E / W 两级检查可分层（rf-774） |
| 34 | `scripts/perf-test-report.py` | 635 | 365 | 场景构造 / 指标计算 / 报告渲染三段（rf-774） |

> **已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：`report/excel_generator.py`（rf-89，页签编排后续可下沉）、`report/data_status.py`（rf-80，DegradationTracker 单类内聚）、`report/html_renderers.py`（rf-81，渲染域同源）、`fetcher/fund.py`（rf-85，排名 / 持仓 / 基准三职责择机拆）、`fetcher/batch.py`（rf-78，BatchDispatcher 内聚）、`tui/handlers_config.py` 与 `scripts/_doc_drift/_format.py`（rf-665，随 `features.py` 注册表增长但各自域内聚）、`llm/prompts_core.py`、`llm/generators.py`（rf-626，提示词/生成器按模块分文件）。

## 已解决问题

### 开发期已修复（0.13.11-dev）

（本版开发期已修复项已随 v0.13.11 发布迁入上方归档档案）

### 开发期已修复（0.13.10-dev）

（本版开发期已修复项已随 v0.13.10 发布迁入上方归档档案）

### 开发期已修复（0.13.9-dev）
（本版开发期已修复项已随 v0.13.9 发布迁入上方归档档案）

### 开发期已修复（0.13.8-dev）
（本版开发期已修复项已随 v0.13.8 发布迁入上方归档档案）

### 归档档案
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) 
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md)
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md)
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md)
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md)
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md)