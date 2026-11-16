# 计划归档 — v0.18.x

> 归档时间：2026-11-12（v0.18.0 发布，本系列首份）；2026-11-16 v0.18.2 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.18.x 开发期完成项（含 v0.18.2）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-256` ✅ 交易日原语单点化（消除 fetcher → report 反向依赖）

**现状**：`fetcher/price.py` 的价格新鲜度判定沿用 `report/market_value` 的交易日函数再导出（运行期与测试共用一个改动点），
分层规则把它登记为冻结例外（`check-import-surface` 的 `layer-inversion`，到期 2027-06-30）。
**动作**：`report/market_value` 内部改为按模块属性调用 `core/trading_calendar`；测试 patch 点随之迁到 core 单点；`fetcher/price`
直连 core 后删除该 re-export 依赖与例外登记。
**验收**：`check-import-surface --ci` 无 fetcher→report 命中；`report/market_value` 相关单测（含 patch 点）全绿。

**结果**：`report/market_value` 内部改为按属性调用 `core/trading_calendar`，`fetcher/price` 与 `report/_holding_detail_rows`、`report/excel_module_loader` 直连 core；测试 patch 点统一迁到 `core.trading_calendar` 单点（22 个测试文件、136 处）；例外表与「存量分层例外」表删除该行，`check-import-surface --ci` 零命中。

## `plan-257` ✅ 报告生成编排函数拆分

**动机**：`report/excel_generator.generate_excel_report` 479 行 / 92 分支、`_generation_full._generate_report_full` 410 行、
`report/html_writer.write_html_report` 357 行——文件行数未触红线，但改动一处需通读全函数。
**做法**：按页签族与阶段提取子函数，逻辑逐行搬运、产物不变；产出阶段入参收敛为上下文对象。
**结果**：

| 函数 | 拆分前 | 拆分后 | 拆出的子函数 |
|:---|:---|:---|:---|
| `generate_excel_report` | 479 行 / 92 分支 | **216 行 / 20 分支** | 行动建议兜底 / 市场情绪 / 景气度诊断 / 可选明细页签 / 环比对比摘要 / 收尾保存 |
| `_generate_report_full` | 410 行 / 47 分支 | **304 行 / 17 分支** | 行业资金流向（三态降级登记）/ LLM+新闻阶段（`_LlmStageResult`）/ 双端产出与收尾（`_FullEmitContext`） |
| `write_html_report` | 357 行 / 10 分支 | **312 行 / 6 分支** | 三面板视图装配 / 数据源状态装配（`_DataSourceBundle`）/ 渲染前置上下文（`_RenderContext`） |

**验收**：产物同输入对拍不变（`test_excel_generator` / `report` 2926 用例全绿）；P0/P1 门禁全绿。
**边界**：拆分止于当前粒度——剩余主体是 `_render_template` 的 80 个关键字实参与 50+ 入参，更深一层需改渲染契约（见 `plan-258`），收益在可读性而非行数。
**存量超长函数（非本项范围）**：`analysis/schedule_replay.run_schedule_replay`（335）、`llm/generators.generate_debate_procon`（312）、
`cli/_parser._build_parser`（277）、`report/_orchestrator_data.prepare_report_data`（271）——按需另立。
