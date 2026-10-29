# 投资复盘助手 — 实现计划
> 文档版本：0.16.11-dev
> **编号源**：`plan-next = 240`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-239，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

在办 6 项：P1 2 项（**plan-238**、**plan-239**）、P2 1 项（**plan-92**）、P3 2 项（**plan-70**、**plan-233**）、P4 1 项（**plan-55**）。命名与实现纪律见 `CLAUDE.md`（单一事实位，本表不重复）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选、历史报告归档索引导航——理由与清单见各版归档。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

#### `plan-238` TUI 渠道持仓录入（已落地，待真机动线验收）

首页「持仓维护」组新增 `[U] 持仓录入（买入 / 卖出 / 保存）`（二级 `1`/`L` 查看持仓、`2`/`P` 录入买入、`3`/`S` 录入卖出、`4`/`W` 保存、`0` 返回）；录入只改内存变更清单，保存回显确认后原子写回持仓文件。设计、录入与成本口径、写回契约、验收载体全文见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md)；需求条目 R-HLD-06~11。

#### `plan-239` WEB 渠道持仓录入（已落地，待真机验收）

在 plan-238 落地的 `holdings_editor` / `nav_lookup` 之上提供 Web 录入表单与保存确认，校验与写回语义与 TUI 一致（不得各自实现一份写入逻辑）；前置 plan-238。设计见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md) §9。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条，趋势列加迷你折线（openpyxl 原生）；先做持仓明细 / 量化指标 / 集中度 2~3 个页签，验证后再扩。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）转正判据

**状态**：观察中（实验项，默认关），样本进度以 `doctor` 账本概览为准。
**判据**（两级门槛）：`directional_total ≥ 20` 时命中率可采信（该门槛上的首次读数即正式读数，未达时仅按命中/总数并列观察）；`directional_total ≥ 40` 才做**转正裁决**——据 `doctor` 账本概览摘除 `experimental`（面板 ⚗ 消失，页脚自述改为常规口径）。撤销：启用次数停止增长，**或**已结算 <10 条且无达标趋势（含 `decision_llm_capture`、行动章复盘块与对应需求条目一并撤除）。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按该文档迭代计划执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**事实位**：判据、两级门槛与观察进度在本条维护（本表即唯一事实位）；已落地机制、挂载点与观测数据源见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)。

#### `plan-233` `report_qa` 转正评估（按埋点数据裁决）

**现状**：报告追问仍为实验项（⚗、默认关）；转正判据已机检化——提问量 ≥ 30、无回答占比 ≤ 15%、事实核对降级率 ≤ 30%，由 `doctor` 卡片按账本给出结论。
**动作**：判据满足后按数据裁决：转正（摘 ⚗、`doctor` 卡片转常规统计）/ 调整阈值（须说明理由）/ 维持实验。
**验收**：`doctor` 卡片三判据逐条 `[OK]`；`features.py` 的 `report_qa.experimental` 相应调整；`plan.md` 记录裁决依据（数值 + 时段）。
**事实位**：判据与裁决在本条维护；已落地机制、挂载点与观测数据源见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测（三方对照评测脚本未建立）。该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

## 归档

- [`archived_plan.0.16.x.md`](../archive/v0.16.x/archived_plan.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-25）
- [`archived_plan.0.15.x.md`](../archive/v0.15.x/archived_plan.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_plan.0.14.x.md`](../archive/v0.14.x/archived_plan.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_plan.0.13.x.md`](../archive/v0.13.x/archived_plan.0.13.x.md) — v0.13.x
- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md) — v0.12.x
- [`archived_plan.0.11.x.md`](../archive/v0.11.x/archived_plan.0.11.x.md) — v0.11.x
- [`archived_plan.0.10.x.md`](../archive/v0.10.x/archived_plan.0.10.x.md) — v0.10.x
- [`archived_plan.0.9.x.md`](../archive/v0.9.x/archived_plan.0.9.x.md) — v0.9.x
- [`archived_plan.0.8.x.md`](../archive/v0.8.x/archived_plan.0.8.x.md) — v0.8.x
- [`archived_plan.0.7.x.md`](../archive/v0.7.x/archived_plan.0.7.x.md) — v0.7.x
- [`archived_plan.0.6.x.md`](../archive/v0.6.x/archived_plan.0.6.x.md) — v0.6.x
- [`archived_plan.0.5.x.md`](../archive/v0.5.x/archived_plan.0.5.x.md) — v0.5.x
- [`archived_plan.0.4.x.md`](../archive/v0.4.x/archived_plan.0.4.x.md) — v0.4.x
- [`archived_plan.0.3.x.md`](../archive/v0.3.x/archived_plan.0.3.x.md) — v0.3.x
- [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) — v0.2.x
- [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md) — 早期版本
