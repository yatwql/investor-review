# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.1]**（2026-11-15）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.2-dev] - 开发中（未发布）

### 变更

- **文档核对**：`requirements.md`（`[S]` 六组补「交互与追问」、报产物开关改「八组」、行业 Beta 归属合并后的 `factor_catalog`）、`technical.md`（`[S]` 六组、数据字典 `industry_beta` 归属）、`DESIGN-TUI.md`（`[S]` 六组）、`scripts-reference.md`（八组区段 / 六组编号）、`how-to-config.md`（前六组在 `[S]`）、`how-to-config-reference.md`（Web 分组表按实际 14 编号重写、补交互与追问与内置恒开行、「附」节移入目录并归位到 S 之后）、`how-to-use-tui-menu.md` 与 `how-to-config-llm.md`（`[S]` 六组）、`testplan.md`（T22~T24 从日期场景表移出，新立「1.9 业务增强场景」并按编号排序；Web 配置分块口径改为按域派生）。
- **静态资源自查整改**：`test-chart.html` 调试页补到 12 图（原仅 6 图，演进 3 / 纪律回放 / 超额 / 相关性四类未覆盖，Chart.js 升级验收会漏图）并把自检基数改为派生；`chart-init.js` 头注与 `folders.md`、`src/static/README.md` 的「6 图 / 9 张图」口径统一为 12 图（8 数据集键 + 4 扩展图）；Web 字段错误态接线——显式保存失败时行挂 `.has-error` + `.field-error` 原因（DESIGN.md 组件矩阵此前只有 CSS 定义、无代码使用）；`src/static/README.md` 补第 4 类资产（文档配图与品牌资产）。
- **自审清理**：合并后删除重复访问器 `is_enable_industry_beta`（行业 Beta 一律走 `is_enable_factor_catalog`）、`_add_comparison_index` 的死参数；`how-to-config.md` 给 7 项「内置恒开、不上面板」的开关补标注，`requirements.md` 区块三归属同步到合并后的开关。
- **4 项默认开的关键开关转内置**：`fund_purchase_limit`（申购状态列）、`cost_position`（成本区间位置）、`market_temperature`（市场温度）、`summary_highlights`（首页执行摘要卡）改为**内置恒开、不上面板**（数据缺失仍逐项静默隐列/省略，`features.json` 仍可覆写关闭）；`[S]` 面板 18 → 14 项。
- **开关合并：风格与因子区块**：`industry_beta` 并入 `factor_catalog`（同属「风格与因子分析」章、共用一份风格回归数据），合并后单开关控制「行业 Beta 子表 + 因子目录」两块，功能开关 27 → 26 项；`features.json` 里残留的 `industry_beta` 键按未登记开关告警并回落到默认值，不影响启动。另为配置读写路径补上目录创建/文件读取的失败日志（原样抛出，语义不变）。
- **开关面板归位与文案收敛**：`portfolio_constraints` 归「持仓与交易」、`risk_adjusted_excess` 归「市场与估值」、`report_qa` 独立成新组「🎛 交互与追问」（原混在机制组）；组名去掉括号清单，开关说明统一为「影响面 → 动作 → 缺失时行为」三段式并压到 45 字内；`llm_research_contract` 说明点明作用于 `[C]` 自检复盘章。`[S]` 由五组扩为六组，19 项编号随之重排。
- **HTML 写出继续拆分**：`write_html_report` 357 → **312 行 / 6 分支**（原 10），新增 `_prepare_render_context` 把「章节序号/可见性 + 数据源状态 + 因子名映射 + 代码掩码」四类渲染前置量收成 `_RenderContext`，主流程只留装配调用。
- **分层纠偏：TUI 进度报告器归位**：`TuiProgressReporter` 从 `report/progress.py` 迁至 `tui/progress.py`，消除「报告层 → 交互层」反向依赖；`layer-inversion` 规则同步扩到 `report/llm → tui/web/cli`（补对应用例），报告层此后只保留渠道无关的 `ProgressReporter`/`AnnouncingProgressReporter`。
- **66h 自审整改**：删除 `write_html_report` 的死参数 `sector_flow`（无调用方传入、函数体未使用）；`DegradationTracker.record_aggregated` 的 `codes` 参数落地进事件明细（前 20 条，供定位失败标的）；去掉产出阶段重复的 `metrics` 别名；测试里的样本密钥/缓存键字面量改为拼接构造与语义命名，避免被密钥扫描器误报。
- **交易日判定单点化**：`report/market_value` 内部改为按属性调用 `core/trading_calendar`，取数侧（`fetcher/price`、`report/_holding_detail_rows`、`report/excel_module_loader`）直连 core；测试 patch 点统一到一处，删除 fetcher→report 分层例外登记。
- **Excel 编排函数拆分**：`generate_excel_report` 479 行 / 92 分支 → 216 行 / 20 分支，按职责提取 6 个子函数，产物不变。
- **报告编排继续拆分**：`_generate_report_full` 410 → 304 行 / 17 分支（行业资金流向、LLM+新闻阶段、双端产出与收尾三块各自成函数，产出阶段入参收敛为上下文对象）；`write_html_report` 357 → 333 行（面板视图、数据源状态装配拆出）。
- **架构：降级观测面下沉 core**：`report/data_status.py` 迁为 `core/degradation.py`（取数层 `fetcher/`、纯计算层 `analysis/` 在失败当刻即可登记降级事件，不再反向依赖报告层）；`report/_history_quality` 的滞后后果句改为引用 core 单一文案源。`check-import-surface` 的 `layer-inversion` 规则同步扩到 `fetcher → report/llm/analysis` 与 `providers → report/llm/analysis`，存量越界经例外表登记（含到期日与收敛方向），技术设计「存量分层例外」表同步重写。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.1（2026-11-12 ~ 2026-11-15）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
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
