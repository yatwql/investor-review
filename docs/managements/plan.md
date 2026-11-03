# 投资复盘助手 — 实现计划

> 文档版本：0.16.17
> **编号源**：`plan-next = 244`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-243，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

在办 7 项：P1 2 项（**plan-238**、**plan-239**）、P2 1 项（**plan-92**）、P3 3 项（**plan-70**、**plan-233**、**plan-243**）、P4 1 项（**plan-55**）。命名与实现纪律见 `CLAUDE.md`（单一事实位，本表不重复）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选、历史报告归档索引导航——理由与清单见各版归档。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

#### `plan-238` TUI 渠道持仓录入（待真机动线验收）

首页「持仓维护」组的 `[U]` 面板提供列持仓 / 录买入 / 录卖出 / 保存 / 撤销 / 继续录上一笔；录入只改内存变更清单，单笔仅回显，保存为一次输入表达意图（回车写入并自动 `.bak` / `f` 记流水后写入 / `2` 丢弃 / `0` 返回）后原子写回。设计与写回契约见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md)；需求条目 R-HLD-06~14。

**真机验收清单**（六条动线全部勾选后方可归档）：

- [ ] 进入与列持仓：`[U]` 进面板键位齐全，`L` 按账户分块列出、未保存行行首标红 `*` 且底部有图例
- [ ] 场内买入：`P` 选账户 → 标的 → 份额 / 价格 / 交易日，回显含「共 N 笔待保存」，持仓文件 mtime 未变
- [ ] 场外买入：按金额与按份额两种口径各录一笔；当日净值未公布时本笔不成立并提示改用其他口径
- [ ] 继续录上一笔：`C` 跳过账户与标的选择、只重填份额 / 价格；菜单项仅在录过一笔后出现
- [ ] 撤销与退出守卫：`U` 连续撤销到空；`Esc` 退出守卫三选一逐项验证（默认继续编辑）
- [ ] 保存一次输入：`W` 下先 `0` 取消（草稿保留）、再回车写入（`.bak` 生成 + 回读校验通过）、`f` 记流水路径、`2` 丢弃草稿各走一次

#### `plan-239` WEB 渠道持仓录入（待真机验收）

Web 工作台提供录入表单与保存确认，复用 `holdings_editor` / `nav_lookup`，校验与写回语义与 TUI 一致（不各自实现写入逻辑）；前置 plan-238。设计见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md) §9。

**真机验收清单**（六项行为全部勾选后方可归档）：

- [ ] 页签加载：文件与持仓条数正确，并提示「未保存的变更不会写入文件」
- [ ] 表单口径：加入一笔后保留账户与标的、只清份额 / 金额；清单内单笔可「移除」
- [ ] 清空清单：二次确认后清空且持仓文件字节不变
- [ ] 保存自动预览：确认框含写回后条数与新增 / 更新 / 移除计数、逐笔清单、`.bak` 提示；写入成功提示含备份文件名
- [ ] 空态禁用与流水记忆：清单为空时保存 / 预览 / 清空按钮禁用、预览框隐藏；勾「同时记入交易流水」后刷新页面仍保留
- [ ] 并发闸门：外部改过持仓文件后保存 → `HOLDINGS_STALE` 提示并自动刷新总览

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条，趋势列加迷你折线（openpyxl 原生）；先做持仓明细 / 量化指标 / 集中度 2~3 个页签，验证后再扩。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）转正判据

**状态**：实验项（默认关），未达采信门槛（有方向 18 条 < 20）。读数以 `doctor` 账本概览为准：启用 118 次、已结算 27 / 待结算 63、命中率 72.2%、`sample_sufficient=false`。
**判据**：`directional_total ≥ 20` 时命中率可采信（该门槛上的首次读数即正式读数，未达时按命中/总数并列观察）；`≥ 40` 才做转正裁决——据账本摘除 `experimental`（面板 ⚗ 消失，页脚自述转常规口径）。撤销：启用次数停止增长，或已结算 <10 条且无达标趋势（含 `decision_llm_capture`、行动章复盘块与对应需求条目一并撤除）。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按其迭代计划执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**事实位**：判据、门槛与进度在本条维护；已落地机制与观测数据源见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)。

#### `plan-233` `report_qa` 转正评估（按埋点数据裁决）

**状态**：实验项（默认关，唯一新增 LLM 费用的实验项），未达转正判据——账本 `data/state/qa_usage.jsonl` 尚无记录（零提问），三项判据均不可评估；观测期内维持 `experimental=True`。
**判据**（`qa/telemetry.py` 常量，`doctor` 逐条上屏）：提问量 `attempts ≥ 30`、无回答占比 `≤ 15%`、事实核对降级率 `≤ 30%`——三项同时满足才判「可评估转正」（`summarize_qa_usage(days=30).verdict.ready`），随后据账本摘除 `experimental`（面板 ⚗ 消失、页脚实验自述移除）。
**数据源**：`qa/telemetry.py` 每次提问记一行账本（只记字数不记正文、滚动上限 5000 行），`doctor` 汇总最近 30 天；`experiment_stats.report_qa` 只记开关启用次数（当前 63 次），不构成效果判据。
**撤销死线**：最近 90 天新增提问 <10 条（用户不用）或质量指标连续两个观测窗口越线且提示词/上下文一轮整改后仍不改善（质量不达标）→ 连同 `qa/` 子包、`report_qa` 开关、报告页追问区块、TUI `[Q]` 入口与 R-QA-01~10 需求条目一并撤除。
**机制**：`qa/` 会话层与 `QaSession`、`record_attempt` 记账、报告页区块与 TUI `[Q]` 入口，机制登记见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)；需求条目 R-QA-01~10。
**事实位**：判据常量在 `qa/telemetry.py`；转正/撤销条款与当前态在本条维护，技术机制见 §6.9。

#### `plan-243` 决策依据章与 LLM 章职责切分（实施）

**现状**：R0~R7 已落地（含提示词两刀与版本盐递增）；R9 约束标注已实现（开关 `portfolio_constraints` 默认关，阈值待按需配置）；R1 契约补完「双路径 HTML 透传」与「回测产物日期随产物派生（`backtest_as_of`）」并补独立 perf 阶段；R8 待 V5 样本门槛满足；承接已归档讨论稿「章节归属结论」，设计稿 [`investment-decision-basis-design.md`](../plan/investment-decision-basis-design.md)。
**前置**：讨论稿待验证清单 V1/V2/V3 已有回测结论（`scripts/eval-decision-quality.py`，见 [归档讨论稿](../archive/v0.16.x/investment-decision-quality/investment-decision-quality.md) §8.1——V1/V2 样本不足仅记录、V3 两口径 5 日视界均无区分度）；实施门禁 V1/V3 满足。
**回测接入**：估值分位按「已回测未通过」接入（`report/decision_basis.py` 模块常量登记、不新增配置键；两口径均无区分度 → 不在管线内计算真实 PE/PB 口径）；因子目录信号按「样本不足」态；V1 复跑触发（20 日成熟样本 ≥100，固定视界与账本动态视界对拍后切换）见设计稿 R0。
**章节归属**：先以「行动建议」章内块形态（形态 A）落地「判断依据」（纯规则、零 LLM），LLM 章退回解读层；独立章节（形态 B）留作升级路径。
**迭代计划**：R0~R9 十轮（设计稿 §4），每轮独立可验收、任一失败即停；LLM 章改造拆为 R6 语义增量与 R7 冲突措辞替换两刀，前后脚同版本发布；R8 纪律规则重构、R9 集中度/相关性硬约束承接归档讨论稿优先级 3/5（算法层，与决策依据块的只读呈现分开，首发默认关、可回退）。
**质量门禁**：跨轮门禁见设计稿 §4——每轮 `dev-verify` 全绿 + 守护全绿 + 设计护栏 E 级 0 + 文档同步（`technical.md` 附录 H 契约与语义命名表、`test-coverage.md`、`folders.md`、`changelog.md`；R1 起补 `requirements.md` 的 R-OUT 条目与 `core/section_block_registry.py` 区块登记，R2 起在 `src/python/config/_feature_registry.py` 与 `how-to-config-reference.md` 登记 `decision_basis`，R8/R9 起补 `requirements.md` 的 R-DIS-06~09、`config/_config_defaults.py` 新键与功能语义命名表条目）；累计完成后走 `release.py gate`。
**验收**：R0~R9 逐轮验收全过；跨轮汇总口径见设计稿 §5（含回归：`enable_llm` 两态下该块输出逐字节一致、`decision_basis.enabled=false` 与基线快照逐字节一致）；回滚通道 `decision_basis.enabled` 可用。
**挂账（未排期）**：① R8 纪律规则重构（前置：V5 回测门槛——已跑、20 日成熟样本 2 条、两口径触发 0，未达样本门槛故阈值口径维持默认）；R9 已实现默认关，启用待配置 `constraints` 阈值（相关性项待 V7：已跑，样本期 146 交易日 < 250、窗口 5 个、IC −0.36，样本期不足不采信）；② 归档讨论稿优先级 6（模型同输入 A/B）与待验证项 V4（执行回执来源）、V6（模型 A/B）、V7；③ R6/R7 真机采样清单（基线/新提示词各 5 次、同输入 A/B 各 10 次的方向陈述比例与人判读，人工执行不入自动化）。
**事实位**：轮次计划与验收口径在设计稿维护，本表不重复。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测（三方对照评测脚本未建立）。该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

## 归档

- [`archived_plan.0.16.x.md`](../archive/v0.16.x/archived_plan.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-30）
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
