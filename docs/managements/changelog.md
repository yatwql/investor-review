# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.5]**（2026-10-27）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.6-dev] - 开发中（未发布）


### 修复

- **复用 gate 戳时的提示文案拼接**：`release.py publish` 在 gate 通过戳缺「用例数」字段时打印出「…，项数见 gate 输出 项」（多一个悬空「项」）——改为缺值时整段省略，不再拼出残句

### 变更

- **`[S]` 面板措辞与归类清理**：① `module_quality_gate` 标签「模块级质量分级」→「**LLM 输出评级**」（与 `data_quality` 的「质量」解歧，后者描述补「数据侧质量，与 LLM 输出评级无关」）；② `event_window_impact`「事件窗量化对照」→「**事件窗对照**」、`summary_highlights`「本期要点与环比对照」→「**首页执行摘要卡**」——标签同步注册表/区块注册表/HTML 模板/Excel/手册，报告区块标题随之一致（区块名不带括号：`normalize_block_title` 会剥离括号注解）；③ 描述白话化：`valuation_percentile` 改「有历史 PE/PB 就用真分位，没有就用价格分位近似」、`report_qa` 补「按量计费」、`prosperity_framework` 明说评估对象是「持仓组合」
- **`data_quality` 内置为恒开**：数据质量仪表盘不再有开关（数据本就在收集，关掉只是「看不见可信度」）；渲染管道参数保留并标注技术债（清理项见 `plan.md`）
- **`report_qa` 归入「机制与质量」**：它是唯一新增 LLM 费用与用量记账的项，放在「呈现与交互」会误导；随之**删除空的「呈现与交互」组**（`[S]` 六组 → **五组**、20 → **18 项**），编号 12-18 重排，CLI/Web/报告三渠道随注册表自动收敛
- **两处类型标注纠偏（顺带）**：`report/_llm_news._fetch_llm_and_news` 返回标注由四元组补成五元组（实际一直返回五元组、调用侧解包五值）；`force_llm_modules` / `force_modules` 参数由 `set|frozenset` 放宽为 `Collection`（调用侧传 list），线程池 future 列表补 `Future` 标注

- **`metrics_enabled` 内置为恒开（去掉显示开关）**：报告量化指标始终全量计算与渲染，`[S]` 面板 20 → **19 项**（呈现与交互组剩 `report_qa`）。原开关是纯展示项却并联了跨层副作用——关闭会让**指标级断路器暂停失败计数**并自动解熔，即「改报告观感」影响「熔断统计」，属设计债；本次一并删除 `analysis/circuit_breaker_wrapper` 的 Feature Flag 联动分支（`_check_feature_flag` / `_log_ff_event` / `_ff_was_off` 残留计数），`chart_data_builder` 去掉 `metrics_enabled` 参数与「全轴 N/A」分支；三渠道随注册表自动收敛（CLI 已拒绝旧键、Web 面板不再出该行）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.5（2026-10-25 ~ 2026-10-27）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
