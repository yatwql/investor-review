# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.2-dev
> **编号源**：`rf-next = 812`（新增问题取此编号，完成后更新为 +1；已用最大 rf-811，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

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

> 当前无逼近红线档的文件（主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000 均无在册项；警告级全集以 `check-file-length.py -v` 为准）。

**已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：

| 任务 | 文件 | 行数 | 决策依据 |
|------|------|------|----------|
| **rf-89** | `src/python/report/excel_generator.py` | 659 | 维持现状：页签编排后续可下沉 |
| **rf-80** | `src/python/report/data_status.py` | 649 | 维持现状：DegradationTracker 单类内聚 |
| **rf-81** | `src/python/report/html_renderers.py` | 577 | 维持现状：渲染域同源 |
| **rf-85** | `src/python/fetcher/fund.py` | 553 | 维持现状：排名 / 持仓 / 基准三职责择机拆 |
| **rf-78** | `src/python/fetcher/batch.py` | 520 | 维持现状：BatchDispatcher 内聚 |
| —（同批决策） | `src/python/llm/prompts_core.py`、`src/python/llm/generators.py` | 350 / 444 | 维持现状：提示词 / 生成器按模块分文件 |

## 已解决问题

### 开发期已修复（0.14.2-dev）

| # | 问题 | 处理 |
|---|------|------|
| **rf-811** | 开发者指南与辅助脚本参考核对出 4 类不一致：① 指南「按域索引」启动行列了**不存在的** `dev-verify.sh` / `web.sh`（实际包装脚本仅 `launch.sh`/`launch.ps1`/`cli.sh`/`llm.sh` 及 `.ps1` 版）；② `factor_zoo_eval.py`（顶层脚本）在两份文档中**零提及**（一览缺行、无详情小节）；③ 拆包实现未点名（`_perf_view` / `_test_redundancy` / `_factor_zoo` 未提，`_doc_drift` 在脚本参考里缺失）；④ 指南 CLI 子命令行漏 `cassettes`（脚本参考的 CLI 分节有） | 已修复：启动行改为实际包装脚本；`factor_zoo_eval.py` 补一览行 + 诊断类详情小节（三指标判据 / 六个子命令 / 四条纪律 / `_factor_zoo/` 实现包）；`check-test-redundancy` / `perf-view` 一览行点名 `_test_redundancy/` 与 `_perf_view/` 拆分，`check-doc-drift` 条目点名 `_doc_drift/`，`probe.py` 小节补旧入口垫片说明；CLI 子命令行补 `cassettes`；「60+ 个辅助脚本」改为非数字表述（顶层 33 个 + 内部实现包）。**复核口径已机检化**：新增 `unit/scripts/test_scripts_reference_coverage.py` 5 例——一览覆盖全部顶层脚本（含 .ps1 变体）/ 一览无虚指 / 指南按域索引点名的脚本必须存在 / 七域行各自点名条目 / 内部实现包逐个被参考文档点名（包清单从文件系统派生，不写死） |
| **rf-810** | `rf-808` 的修复方向只落了前半（`archive-init` 骨架生成），后半「报错附期望格式样例」未做：`prepare` 的 changelog 归一步四类格式失败（缺开发段 / 缺归档章节 / 缺指针行 / 索引行改写失败）原本只报「格式与预期不符」，执行者须去读正则才能猜出正确写法 | 已修复：`_release/_changelog_archive.py` 新增 `_fmt_hint()` 与三个格式样例常量（指针行 / 索引行 / 开发段），四处报错统一附「期望：<样例>」+「下一步：先跑 `release.py archive-init`」；回归 3 例 （缺开发段 / 缺指针行 / 索引行格式不符各自断言样例与提示文案） |
| **rf-86** | `src/python/cache/operations.py` 739 行：五职责混在一处——数据结构（3 个 dataclass）、缓存刷新族（公共缓存/新闻/基金经理/扩展缓存，13 个私有函数）、更新编排（basic/position/all）、清理、统计与预热 | 已修复：刷新族下沉 `cache/_cache_refresh.py`（282 行）——`_get_pool`、基金/行业/分红/盈利预测/行业资金流各刷新器与提示、`_refresh_common_caches`、新闻与基金经理/扩展缓存；`operations.py` **489 行**，只留数据类、更新编排（`update_basic_cache`/`update_position_cache`/`update_all_cache`）、清理、统计、预热。单向依赖：编排 → 刷新（`CacheUpdateResult` 用 TYPE_CHECKING + 函数内延迟导入避免与入口成环）；测试 patch 按调用点区分：直接调用刷新器的用例指向 `_cache_refresh`，经 `update_basic_cache` 的用例留在 `operations`。P3 登记表随之清空（无逼近红线档文件） |
| **rf-626** | 报告域两模块内职责混杂：`report/html_writer.py` 799 行（模板渲染 + 落盘 + 数据状态块装配）、`analysis/rebalance.py` 751 行（配置解析/分类入口 + 偏离度信号族） | 已修复：① `html_writer` 799 → **689 行**（数据状态块装配 → `html_writer_status.py` 901 行：自述块 / 降级状态安全构建 / 时间串 / 三处状态区块）；② `rebalance` 751 → **243 行**（偏离度信号族 → `_rebalance_deviation.py` 565 行：目标偏离 / 股债偏离 / 单品种超限 / 信号汇总 + 分类权重与误报保护，常量 `MIN_NEW_POSITION_TRADING_DAYS` / `_CATEGORY_ORDER` / `_CATEGORY_LABELS` / `_EQUITY_FI_GROUPS` 随迁）。依赖方向单向（渲染 → 状态装配；信号 → 分类/配置，后者用**函数内延迟导入**避免与入口 re-export 成环）；测试 patch 目标按「调用点所在模块」改指（`build_*_data_status` 系列 → `html_writer_status`）。同族两文件维持（`llm/prompts_core.py` / `llm/generators.py` 按模块分文件） |
| **rf-665** | `src/python/config/features.py` 840 行：功能开关注册表（`feature_switch_registry` 206 行 + `FeatureSwitchDef` + 分组常量 + 纯注册表视图）与运行时状态（features.json 读写/迁移/日志）混在一处，每个新开关约十行、持续挤压余量 | 已修复：注册表与定义下沉 `config/_feature_registry.py`（298 行）——分组常量 / `GROUP_LABELS` / `GROUP_ORDER` / `FeatureSwitchDef` / `feature_switch_registry` / `_FEATURE_FLAGS_DEFAULT` / `switches_in_group` / `experimental_flags` / `is_experimental_switch` / `EXPERIMENT_ALL`；`features.py` **574 行**，只留运行时状态（覆写读写、合并键迁移、开关解析与日志）并 re-export 注册表符号。单向依赖：运行时 → 注册表，`feature_switch_registry is ...` 同一对象（无副本）。同族两文件维持（`tui/handlers_config.py` / `scripts/_doc_drift/_format.py` 各自域内聚） |
| **rf-773**（完成） | 8 个模块内职责混杂、逼近 700 行登记线（LLM / 配置 / 报告 / 分析 / 数据源五域） | 已全部拆分：`llm/api_base` 770→**501**（响应解析 → `_api_responses.py` 314）、`config/_validation` 723→**119**（三域 `_validation_scalars/sections/llm` + 共用原语 `_validation_common`）、`report/holdings_detail_sheet` 716→**171**（分区块写入器 → `_holdings_detail_blocks.py` 632）、`analysis/prosperity_scoring` 711→**476**（输入与权重 → `_prosperity_inputs.py` 270）、`providers/news_dedup_rules` 710→**331**（纯词表 → `_news_dedup_tables.py` 404）。另前一批已拆 `orchestrator` 734→255 / `_report_generation` 751→52 / `fund_performance` 728→595。全部保留门面 re-export；测试 patch 与结构断言按「调用点所在模块」改指（含区块注册表载体列、章节-区块矩阵同步）。 |
### 归档档案
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-22）
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
