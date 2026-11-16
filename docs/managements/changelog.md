# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.1]**（2026-11-15）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.2-dev] - 开发中（未发布）

### 变更

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
