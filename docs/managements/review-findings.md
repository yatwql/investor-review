# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.2-dev
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
| 1 | **rf-626** 报告域按职责下沉（含已决策维持的两处） | `src/python/report/html_writer.py` 799/201、`src/python/analysis/rebalance.py` 751/249 | `html_writer`：域下沉 + 门面 re-export（测试 patch 改指持有子模块）；`analysis/rebalance`：按「成本分档 / 偏离度 / 告警」下沉 |
| 2 | **rf-86** `cache/operations.py` 五职责下沉 | `src/python/cache/operations.py` 739/261 | 五职责待下沉（数据结构 / 基金刷新 / 公共缓存 / 持仓缓存 / 清理） |

**已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：

| 任务 | 文件 | 行数 | 决策依据 |
|------|------|------|----------|
| **rf-89** | `src/python/report/excel_generator.py` | 659 | 维持现状：页签编排后续可下沉 |
| **rf-80** | `src/python/report/data_status.py` | 649 | 维持现状：DegradationTracker 单类内聚 |
| **rf-81** | `src/python/report/html_renderers.py` | 577 | 维持现状：渲染域同源 |
| **rf-85** | `src/python/fetcher/fund.py` | 553 | 维持现状：排名 / 持仓 / 基准三职责择机拆 |
| **rf-78** | `src/python/fetcher/batch.py` | 520 | 维持现状：BatchDispatcher 内聚 |
| **rf-626** | `src/python/llm/prompts_core.py`、`src/python/llm/generators.py` | 350 / 444 | 维持现状：提示词 / 生成器按模块分文件 |

## 已解决问题

### 开发期已修复（0.14.2-dev）

| # | 问题 | 处理 |
|---|------|------|
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
