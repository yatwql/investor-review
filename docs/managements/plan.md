# 投资复盘助手 — 实现计划
> 文档版本：0.16.6-dev
> **编号源**：`plan-next = 234`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-233，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

在办 5 项：P2 1 项（**plan-92**）、P3 3 项（**plan-70**、**plan-232**、**plan-233**）、P4 1 项（**plan-55**）。命名与实现纪律见 `CLAUDE.md`（单一事实位，本表不重复）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选、历史报告归档索引导航——理由与清单见各版归档。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

当前无 P1 立项任务。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条，趋势列加迷你折线（openpyxl 原生）；先做持仓明细 / 量化指标 / 集中度 2~3 个页签，验证后再扩。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-232` 数据质量仪表盘恒真参数清理

**现状**：`data_quality` 开关已内置（仪表盘恒开），但渲染管道仍保留 `enable_data_quality` 布尔参数——跨 4 层（`_generation_full` / `_generation_both` / `orchestrator` → `_report_output` → `excel_generator` / `html_writer`），默认值已改为 `True` 并注明「技术债，参数待清理」。
**动作**：删除该参数与三处调用点传参，把「仪表盘恒渲染」写进渲染函数本身；同步删 `_report_output` 两处 docstring 的旧口径，并确认 `data_quality_sheet` 无隐藏分支。
**验收**：全仓 `grep enable_data_quality` 为 0；报告三条生成路径的输出与现在逐字节一致（用同持仓生成前的 Excel/HTML 对比块数）。

#### `plan-70` 决策跨期反思闭环（decision_reflection）转正判据

**状态**：观察中，样本未达阈值（以 `doctor` 账本概览为准）。
**判据**：启用停增，或已结算 <10 条且无达标趋势 → 撤销该实验功能（含 `decision_llm_capture`、行动章复盘块与对应需求条目）；已结算 ≥10 条按 `doctor` 账本概览评估转正，`directional_total` 达 40+ 再评估。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按该文档迭代计划执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**单一事实位**：[technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)「决策跨期反思闭环」行。

#### `plan-233` `report_qa` 转正评估（按埋点数据裁决）

**现状**：报告追问仍为实验项（⚗、默认关）。转正判据已机检化——`qa/telemetry.py` 每次提问记一行账本，`doctor` 的「报告追问效果」卡片按三条判据给出结论：**提问量 ≥ 30**、**无回答占比 ≤ 15%**、**事实核对降级率 ≤ 30%**。
**动作**：积累到判据满足后（或观察到某条判据长期不达），按数据决定：转正（摘 ⚗、`doctor` 卡片转为常规统计）/ 调整判据阈值（需说明理由）/ 保持实验。
**验收**：`doctor` 卡片三判据逐条 `[OK]`；`features.py` 中 `report_qa.experimental` 相应调整；`plan.md` 记录裁决依据（实测数值 + 时段）。

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
- [`archived_plan.0.8.x.md`](../archive/v0.8.x/archived_plan.0.8.x.md) — v0.8.0 ~ v0.8.10
- [`archived_plan.0.7.x.md`](../archive/v0.7.x/archived_plan.0.7.x.md) — v0.7.x
- [`archived_plan.0.6.x.md`](../archive/v0.6.x/archived_plan.0.6.x.md) — v0.6.x
- [`archived_plan.0.5.x.md`](../archive/v0.5.x/archived_plan.0.5.x.md) — v0.5.x
- [`archived_plan.0.4.x.md`](../archive/v0.4.x/archived_plan.0.4.x.md) — v0.4.x
- [`archived_plan.0.3.x.md`](../archive/v0.3.x/archived_plan.0.3.x.md) — v0.3.x
- [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) — v0.2.x
- [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md) — 早期版本
