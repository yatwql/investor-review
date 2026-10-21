# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.1-dev
> **编号源**：`rf-next = 810`（新增问题取此编号，完成后更新为 +1；已用最大 rf-809，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 当前无待办项（rf-790 已决策「维持现状」并归档至已解决）。

### P3 — 持续监控：文件膨胀登记（按任务号组织；逼近红线档 主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000）

> **单一事实源**：行数以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序 / >400 行脚本 / >800 行测试）。本表是**逼近红线档的处置登记**——主程序 ≥700、脚本 ≥600、测试 ≥1000（余量 ≤30% 才入表），行数快照随复核刷新；警告级全集不逐项登记，复核以 `-v` 为准。
> **组织方式**：按**任务号（`rf-N`）**分组——一个处置任务涉及多个文件时归在同一行，文件与行数/余量列在该行的「涉及文件」列里（同一文件只出现一次，行内按任务清单顺序）。行内余量取该任务内**最紧**那个文件，表按此升序——即「哪个任务最先触线」排最前，与逐文件排序给出的先后判断一致。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件拆分」。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线）；≥1000 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

| # | 任务 | 涉及文件（行数 / 距红线） | 处置与备注 |
|---|------|--------------------------|-------------|
| 2 | **rf-665** `config/features.py` 注册表下沉 | `src/python/config/features.py` 840/160 | 注册表逐开关增长（每项约十行）；逼近 980 时把注册表条目与定义下沉（同族：`tui/handlers_config.py`、`scripts/_doc_drift/_format.py` 各自域内聚，维持） |
| 3 | **rf-626** 报告域按职责下沉（含已决策维持的两处） | `src/python/report/html_writer.py` 799/201、`src/python/analysis/rebalance.py` 751/249 | `html_writer`：域下沉 + 门面 re-export（测试 patch 改指持有子模块）；`analysis/rebalance`：按「成本分档 / 偏离度 / 告警」下沉 |
| 4 | **rf-773** 模块内三段/多域拆分（**进行中：3/8 完成**） | 已拆：`report/orchestrator.py` 734→255（数据装配与派生计算 → `_orchestrator_data.py` 519）、`report/_report_generation.py` 751→52（both/full 两路径 → `_generation_both.py` 356 / `_generation_full.py` 368 / 共用步骤 `_generation_shared.py` 85）、`report/fund_performance.py` 728→595（评级内核 → `_fund_rating.py` 166）。**剩余 5 个**：`llm/api_base.py` 770（端点构造/请求发送/响应解析三段）、`config/_validation.py` 723（标量/LLM/章节三域）、`report/holdings_detail_sheet.py` 716（页签分区块）、`analysis/prosperity_scoring.py` 711（阈值表/评分/诊断）、`providers/news_dedup_rules.py` 710（去重规则表按来源） |
| 5 | **rf-86** `cache/operations.py` 五职责下沉 | `src/python/cache/operations.py` 739/261 | 五职责待下沉（数据结构 / 基金刷新 / 公共缓存 / 持仓缓存 / 清理） |

**已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：

| 任务 | 文件 | 行数 | 决策依据 |
|------|------|------|----------|
| **rf-89** | `src/python/report/excel_generator.py` | 659 | 维持现状：页签编排后续可下沉 |
| **rf-80** | `src/python/report/data_status.py` | 649 | 维持现状：DegradationTracker 单类内聚 |
| **rf-81** | `src/python/report/html_renderers.py` | 577 | 维持现状：渲染域同源 |
| **rf-85** | `src/python/fetcher/fund.py` | 553 | 维持现状：排名 / 持仓 / 基准三职责择机拆 |
| **rf-78** | `src/python/fetcher/batch.py` | 520 | 维持现状：BatchDispatcher 内聚 |
| **rf-665** | `src/python/tui/handlers_config.py`、`scripts/_doc_drift/_format.py` | 593 / 595 | 维持现状：随 `features.py` 注册表增长但各自域内聚 |
| **rf-626** | `src/python/llm/prompts_core.py`、`src/python/llm/generators.py` | 350 / 444 | 维持现状：提示词 / 生成器按模块分文件 |

## 已解决问题

### 开发期已修复（0.14.1-dev）

| # | 问题 | 处理 |
|---|------|------|
| **rf-773**（部分） | 报告域三个模块内职责混杂、逼近 700 行登记线：`orchestrator`（编排 + 数据装配 + 派生计算）、`_report_generation`（聚合门面 + both/full 双路径实现）、`fund_performance`（页签写入 + 评级内核） | 已拆三处：① orchestrator 734→**255**（`prepare_report_data` + `compute_*` 五域 → `_orchestrator_data.py` 519）；② `_report_generation` 751→**52**（`_generation_both.py` 356 / `_generation_full.py` 368 / `_generation_shared.py` 85，门面 re-export）；③ `fund_performance` 728→**595**（评级/格式化内核 → `_fund_rating.py` 166）。测试 patch 与结构断言按「调用点所在模块」改指新模块。**剩余 5 个模块**（api_base / _validation / holdings_detail_sheet / prosperity_scoring / news_dedup_rules）仍登记在 P3 的 rf-773 行内 |
| **rf-787** | `src/test/unit/scripts/test_check_doc_drift.py` 1061 行（测试红线 1200，余量 139）：机检项族全塞一个文件 | 已修复：按机检项族切三个兄弟分片——`_partitions`（台账分区纪律 / 归档索引 / 迁档占位）、`_sections`（章节-区块矩阵 / 手册菜单块与键引用 / 返回键不变式 / 可见性类型行）、`_tree`（目录树解析 / 说明计数 / 版本目录顺序）；基片 410 行、分片 118~289 行，用例数不变（130 passed），共享夹具仍由基片提供（分片按名导入） |
| **rf-774** | 脚本域两个文件逼近脚本红线（1000）：`scripts/perf-view.py` 983 行（余量 17，**必须拆**）、`scripts/check-test-redundancy.py` 934 行（余量 66，八类检查混在一个文件） | 已修复：① perf-view 采集/渲染/CLI 三段下沉 `scripts/_perf_view/`——`data.py`（派生）/ `report.py`（渲染 + build_trend_report）/ `cli.py`（argparse→输出），入口 983 → **102 行**（docstring + sys.path 引导 + re-export）；② check-test-redundancy 八类检查各成子模块 `scripts/_test_redundancy/`（`_common` 共用 AST 原语 + `cases`/`duplicates`/`similar`/`self_fulfilling`/`hardcoded`/`trivial`/`weak_mock`/`dead_fixtures`/`facts_cache` + `runner` 编排），入口 934 → **150 行**。两者均保留 `load_script` 直调面的 re-export；测试 patch 目标按「调用点所在模块」改指实现模块（`_test_redundancy._common` 的扫描根、`ast.parse` 打桩仍经入口） |
| **rf-79** | `src/python/core/code_utils.py` 788 行：把「资产类型判定」与「派生量」（交易所前后缀归一 / FMP·东财·cninfo 符号与参数 / 市值粗估）混在一个模块，逼近 700 行登记线 | 已修复：派生量下沉 `core/code_symbols.py`（227 行，前缀常量 `EXCHANGE_PREFIXES` / `_INDEX_EXCHANGE_PREFIXES` 真值迁入其中）；`code_utils.py` **608 行**，保留同名 re-export 维持既有导入面；`_strip_prefix` 更名 `strip_to_digits`（公开原语，`is_six_digit_code` 调它，避免互相递归）；两处「单点定义」守卫同步允许新模块并加 `is` 同源断言。同步 folders 目录树、technical 模块说明 |
| **rf-807** | `prepare --version` 跨版本发布不可用且提示误导：要求 changelog 开发段 == `X.Y.Z-dev`，而失败前打印的是入参而非推导值（两次都显示同一版本号），执行者读不出该做什么；旧行为还「按推导执行」继续跑到中途才报错 | 已修复：与开发链推导值不一致时**立即中止**（exit 2），并给出四步可执行指引（改 `APP_VERSION` → `check-version-consistency --fix` → 同步 changelog 段头与 rf 节头 → archive-init/check/prepare）；回归用例 `test_release_tool_gate.py::TestPrepareVersionMismatchGuidance`（中止 + 指引关键词 + 零写入） |
| **rf-808** | 新小版本首发缺归档骨架且构建知识隐含：需手工建三份归档 + folders 目录树块 + plan/rf/changelog 三处索引行，每补一处都要重跑 `check`（实测一次发布 4 次 check、4 次 prepare）；索引行还需区间口径，格式不符时只在 prepare 阶段报错且不附期望格式 | 已修复：新增 `release.py archive-init [--version] [--date] [--dry]`（`_release/_archive_init.py`），一次建齐三类空位并幂等；建完自动跑 `check-doc-drift --sync`；回归用例 `test_release_tool_gate.py::TestArchiveInit` 2 例（建齐文件/目录树/索引且前置就绪 / 二次运行零改动） |
| **rf-809** | 真实仓库契约测试断言了「随开发周期变化」的仓库状态：`test_real_rf_sections_are_migrated_or_absent` 要求主台账「至少有一节开发期已修复」，而 `devbump` 清空占位后新周期台账为空 → v0.14.0 发版当日的 `dev` 提交 CI 全红（test 3.11/3.12/3.13 + portability；本地因已补 rf-806 节而侥幸通过） | 已修复：该用例只约束「存在的每一节」（当前开发版待迁/已迁、更早批次只允许已迁档），空台账合法；同批把 `TestCliSurface` 的处理器集合改为从 `cmd_*` 派生（新增子命令无需改测试） |
| **rf-806** | changelog 指针行的归档链接不随小版本换名：`apply_changelog_release` 只写版本号与日期，归档文件名沿上一系列的值（v0.14.0 指针指向 `archived_changelog.0.13.x.md`，而该版段落实入 0.14.x）——指针仅在本系列首个版本恰好正确，其余每版都留一处失准链接 | 已修复：改写指针行时同步换名为 `archive_name_for(release_version)`，格式不符即报错中止；主文件指针已校正。回归用例 `test_release_tool.py::TestChangelogPointerLinkFollowsArchive` 2 例 |

### 归档档案
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-21）
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
