# 投资复盘助手 — 实现计划
> 文档版本：0.14.2-dev
> **编号源**：`plan-next = 171`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-170，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档记录项目的实现计划。已完成的版本计划已归档，此处仅跟踪当前迭代中的工作。

**当前迭代**：在办 6 项——P1 1 项（**plan-95**）、P2 3 项（**plan-92/93/128**）、P3 1 项（**plan-70** 死线观察）、P4 1 项（**plan-55** 评测先决未过，暂缓）。

> **命名纪律（强制）**：重构/新增的变量名、函数名、注释与文档表述必须与新章节语义相关（如 `position_relationship`/`portfolio_history_drawdown`/`style_factor`/`action`），**绝对禁止用任务编号命名**（F 系列、plan-N、rf-N 等）。任务编号仅在本表作链接锚点，不进入实现层。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

> 入选标准：立即可执行且价值/风险最高——数据完整性与费用风险、核心量化缺口与报告首屏呈现。

#### `plan-95` 生成完成后无一键打开

**现状与问题**：`finish_report` 仅错误摘要 + 耗时排行 + 按任意键；全仓无 `webbrowser`/`os.startfile`/`xdg-open`——生成完仍要手动进目录找文件（HTML 路径虽有打印但不可直接操作）

**动作**：收尾打印本次产物路径清单 + 询问「按 O 打开输出目录」（跨平台 start/explorer/xdg-open，失败回退打印路径不报错）；Web 侧已有下载入口不受影响

### P2 — 下一阶段就绪（满足条件即开工）

> 入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状与问题**：19 页签全为静态数字与文字，无条件格式（ColorScale/DataBar）/迷你图/openpyxl 原生图表——收益率高低、集中度偏离、偏离度优劣需逐格读数

**动作**：对高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生能力）；先试点 2~3 个页签（持仓明细/量化指标/集中度），避免全表泛滥、样式膨胀与体积增长，试点认可后再扩

#### `plan-93` 历史报告归档无索引导航

**现状与问题**：`html_save` 按日期归档到子目录但不生成 index；TUI 无「最近报告」菜单项（grep 历史报告/报告列表 = 0）；Web 有运行历史但 HTML 归档目录本身不可浏览——找上期报告靠翻文件系统

**动作**：生成/刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口（与 rf-636 联动）；索引页不泄漏路径以外的本地信息，匿名化口径与报告一致

### P3 — 预期实施，有空时安排

> 入选标准：收益明确但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**动机**：实验功能默认靠「真实数据验证后择机转正」，但 decision_reflection 的真实账本积累极少，闭环从未被真实数据跑通；长期挂着默认关的开关是纯维护成本。

**动作**：以 `experiment_stats` 启用计数与账本结算数跨发布周期观察两条判据：① 启用次数停止增长（无真实使用），或 ② `data/state/decision_ledger.jsonl` 已结算样本 <10 条（折叠统计 `direction_accuracy` 无法给出可信命中率）**且已结算无达标趋势** → 撤销该实验功能（含 LLM 决策登记（`decision_llm_capture`）/行动章复盘块注入与对应需求条目）；满足可信样本（已结算 ≥10）则据 doctor 账本概览评估转正。观测手段：`experiment_stats` 启用计数 + `doctor` 复盘账本概览。

**单一事实位**：本实验的「条件—数据—态」结构化口径见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)（决策跨期反思闭环行）；立项/转正/撤销时双方同步刷新。

**落地设计**：若判定转正，按 [`decision-reflection-shadow-design.md`](../plan/decision-reflection-shadow-design.md) 四迭代执行（决策条目结构化 → 到期结算器 → doctor 概览增强 → 报告内反思块），该设计以 Vibe-Trading `shadow_account`（extract→backtest→render）为参照；死线未过前不实施。plan-76 持仓变动复盘已落地，与其构成「意图 vs 成交」对账（只读，不互写）。

**当前状态**：撤销与转正条件均不满足，**维持观察**（不撤销、不转正、不实施设计）。下个观察点：下个发布周期重跑 `fold_ledger`——已结算 ≥10 → 据 doctor 账本概览评估转正（正式命中率另需 `directional_total ≥ 20`，flat 占比高时可信度由人工裁定）；仍 <10 且无新增结算 → 撤销（含 `decision_llm_capture`、行动章复盘块注入与对应需求条目）。

### P4 — 实验候选（先决门槛未过，暂缓）

> 入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**动机**：该模块的关联度/情绪判定属典型**窄判断**（批量、选项有限、需校准概率），恰是 Jev 类型化判定接口的适用场景；而其他四个模块是长文生成，不适用。

**先决门槛（未过不接入）**：按 `docs/plan/jev-news-correlation-evaluation.md` 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标选取、预检收窄结论与预注册阈值见该文档 §2/§7。**未达阈值则归档为已评估未采纳。**

**待评测结论确认后再实施的部分**：见 `docs/plan/jev-news-correlation-design.md`。

**约束与红线**：① 不得作为用户可选的对话模型（该模型不生成文本）；② 不得做成「生成 + 判定」双供应商级联（无信息增量且多一个中间失败态）；③ 语料含真实持仓与新闻，冻结产物必须落 `docs/tmp/`（git 忽略），仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键须按开关注册表统一纪律登记，默认值保持 `chat` 使缺省行为逐字节不变。

**预估成本**：低（评测脚本 + 模板渲染 + 一个独立客户端模块）；**价值**：中（仅影响一个出厂默认关闭的模块，收益以「更稳的解析 + 可校准概率」为主，不以成本节约为卖点）。

## 归档

- [`archived_plan.0.14.x.md`](../archive/v0.14.x/archived_plan.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-21）
- [`archived_plan.0.13.x.md`](../archive/v0.13.x/archived_plan.0.13.x.md) — v0.13.x 已完成项
- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md) — v0.12.x 已完成项
- [`archived_plan.0.11.x.md`](../archive/v0.11.x/archived_plan.0.11.x.md) — v0.11.x 已完成项
- [`archived_plan.0.10.x.md`](../archive/v0.10.x/archived_plan.0.10.x.md) — v0.10.x 已完成项
- [`archived_plan.0.9.x.md`](../archive/v0.9.x/archived_plan.0.9.x.md) — v0.9.x 已完成项
- [`archived_plan.0.8.x.md`](../archive/v0.8.x/archived_plan.0.8.x.md) — v0.8.0 ~ v0.8.10
- [`archived_plan.0.7.x.md`](../archive/v0.7.x/archived_plan.0.7.x.md)
- [`archived_plan.0.6.x.md`](../archive/v0.6.x/archived_plan.0.6.x.md)
- [`archived_plan.0.5.x.md`](../archive/v0.5.x/archived_plan.0.5.x.md)
- [`archived_plan.0.4.x.md`](../archive/v0.4.x/archived_plan.0.4.x.md)
- [`archived_plan.0.3.x.md`](../archive/v0.3.x/archived_plan.0.3.x.md)
- [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md)
- [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md)
