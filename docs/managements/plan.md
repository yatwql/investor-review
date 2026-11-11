# 投资复盘助手 — 实现计划

> 文档版本：0.17.9-dev
> **编号源**：`plan-next = 252`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-251，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

在办 11 项：P1 2 项（**plan-238**、**plan-239**）、P2 1 项（**plan-92**）、P3 7 项（**plan-70**、**plan-233**、**plan-243**、**plan-248**~**plan-251**）、P4 1 项（**plan-55**）。命名与实现纪律见 `CLAUDE.md`（单一事实位，本表不重复）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先                    级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选、历史报告归档索引导航——理由与清单见各版归档。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

#### `plan-238` TUI 渠道持仓录入（待真机动线验收）

首页「持仓维护」组的 `[U]` 面板提供列持仓 / 录买入 / 录卖出 / 保存 / 撤销 / 继续录上一笔；录入只改内存变更清单，单笔仅回显，保存为一次输入表达意图（回车写入并自动 `.bak` / `f` 记流水后写入 / `2` 丢弃 / `0` 返回）后原子写回。设计与写回契约见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md)；需求条目 R-HLD-06~14。

**真机验收**：执行步骤、判定标准与记录表见 [`holdings-entry-acceptance.md`](../plan/holdings-entry-acceptance.md)（隔离演示工作区跑，不碰真实持仓）。**验收清单**（六条动线全部勾选后方可归档）：

- [ ] 进入与列持仓：`[U]` 进面板键位齐全，`L` 按账户分块列出、未保存行行首标红 `*` 且底部有图例
- [ ] 场内买入：`P` 选账户 → 标的 → 份额 / 价格 / 交易日，回显含「共 N 笔待保存」，持仓文件 mtime 未变
- [ ] 场外买入：按金额与按份额两种口径各录一笔；当日净值未公布时本笔不成立并提示改用其他口径
- [ ] 继续录上一笔：`C` 跳过账户与标的选择、只重填份额 / 价格；菜单项仅在录过一笔后出现
- [ ] 撤销与退出守卫：`U` 连续撤销到空；`Esc` 退出守卫三选一逐项验证（默认继续编辑）
- [ ] 保存一次输入：`W` 下先 `0` 取消（草稿保留）、再回车写入（`.bak` 生成 + 回读校验通过）、`f` 记流水路径、`2` 丢弃草稿各走一次

#### `plan-239` WEB 渠道持仓录入（待真机验收）

Web 工作台提供录入表单与保存确认，复用 `holdings_editor` / `nav_lookup`，校验与写回语义与 TUI 一致（不各自实现写入逻辑）；前置 plan-238。设计见 [`holdings-entry-design.md`](../plan/holdings-entry-design.md) §9。

**真机验收**：同上一份执行指引的 §2（Web 动线，含 `HOLDINGS_STALE` 复现方法）。**验收清单**（六项行为全部勾选后方可归档）：

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

**状态**：实验项（默认关），已达裁决资格线，裁决结论：**暂不转正**（命中率未达统计显著，且 `alpha_mean` 为负——摘 `experimental` 会给出虚高能力暗示）。读数以 `fold_ledger` 账本折叠口径为准：启用 118 次（已停增长）、已结算 90 / 待结算 11、5 日视界 `directional_total=68`、准确率 57.4%、`alpha_mean=−0.37%`、`sample_sufficient=true`；20 日视界 9 条，不构成第二证据。
**判据**：`directional_total ≥ 20` 时命中率可采信；`≥ 40` 赋**裁决资格**；转正另需同时满足 5 日视界 `directional_total ≥ 100` **且** `alpha_mean > 0`——据账本摘除 `experimental`（面板 ⚗ 消失，页脚自述转常规口径）。撤销：启用次数停止增长且后续报告停止产生新决策，或已结算 <10 条且无达标趋势（含 `decision_llm_capture`、行动章复盘块与对应需求条目一并撤除）。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按其迭代计划执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**事实位**：判据、门槛与进度在本条维护；已落地机制与观测数据源见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)。

#### `plan-233` `report_qa` 转正评估（按埋点数据裁决）

**状态**：实验项（默认关，唯一新增 LLM 费用的实验项），未达转正判据——账本 `data/state/qa_usage.jsonl` 尚无记录（零提问），三项判据均不可评估；观测期内维持 `experimental=True`。
**判据**（`qa/telemetry.py` 常量，`doctor` 逐条上屏）：提问量 `attempts ≥ 30`、无回答占比 `≤ 15%`、事实核对降级率 `≤ 30%`——三项同时满足才判「可评估转正」（`summarize_qa_usage(days=30).verdict.ready`），随后据账本摘除 `experimental`（面板 ⚗ 消失、页脚实验自述移除）。
**数据源**：`qa/telemetry.py` 每次提问记一行账本（只记字数不记正文、滚动上限 5000 行），`doctor` 汇总最近 30 天；`experiment_stats.report_qa` 只记开关启用次数（当前 63 次），不构成效果判据。
**撤销死线**：最近 90 天新增提问 <10 条（用户不用）或质量指标连续两个观测窗口越线且提示词/上下文一轮整改后仍不改善（质量不达标）→ 连同 `qa/` 子包、`report_qa` 开关、报告页追问区块、TUI `[Q]` 入口与 R-QA-01~10 需求条目一并撤除。
**机制**：`qa/` 会话层与 `QaSession`、`record_attempt` 记账、报告页区块与 TUI `[Q]` 入口，机制登记见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)；需求条目 R-QA-01~10。
**事实位**：判据常量在 `qa/telemetry.py`；转正/撤销条款与当前态在本条维护，技术机制见 §6.9。

#### `plan-243` 决策依据章与 LLM 章职责切分（已收口，仅留观察项）
**结论**：R0~R7、R9 已落地（含提示词两刀与版本盐递增、R9 约束标注默认关），R8 未启动即收口。
**已定调**：估值分位/因子目录信号按「已回测未通过」「样本不足」**归档**（三态标注照常呈现；真实 PE/PB 口径不入管线；`scripts/eval-decision-quality.py` 保留，供样本累积后一次性复跑，日常不排期）；独立章节形态 B 不启用；LLM 章维持解读层。
**长期观察（不排期，触发条件满足时再评估）**：① R8 纪律规则重构——前置 V5 成熟样本 ≥100（现 2 条）；② V7 相关性约束启用——前置样本期 ≥250 交易日（现 146）；③ 讨论稿优先级 6 与 V4/V6/V7 模型 A/B（人工采样，不入自动化）。以上任一前置达成前，资源投向其他任务。
**事实位**：轮次明细、验收记录与回测读数见设计稿 [`investment-decision-basis-design.md`](../plan/investment-decision-basis-design.md) §4/§5 及[归档讨论稿](../archive/v0.16.x/investment-decision-quality/investment-decision-quality.md) §8.1；本表不复述。

### P4 — 实验候选（先决门槛未过，暂缓）
入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-248` HTML 报告装配拆分（先定结构契约）

**现状**：`report/html_writer.py::write_html_report` 397 行——19 个章节区块装配 + 模板绑定 + 渲染后三步后处理（资产内嵌/匿名化/落盘）+ 4 处阶段计时混在一处。**契约缺口**：区块装配顺序 = 报告目录顺序，但这条对应关系只存在于函数体的调用顺序里，改顺序无任何结构信号、也无断言能发现改坏。
**结构契约**（6 条，含守护方式）：[`html-writer-stage-contract.md`](../plan/html-writer-stage-contract.md) —— 顺序以显式有序表表达、区块返回元组形状不变、阶段名集合固定（perf 口径）、匿名化在渲染后落盘前、原子落盘、渲染期单区块异常隔离。
**目标形态**：编排壳 ≤ 90 行，区块按主题拆到 `html_sections_*.py`，顺序表与模板变量映射成为单一事实位。
**验收**：结构用例（顺序表↔实调顺序 / 阶段名集合）+ 生成一份真实报告逐章 diff 为空。

#### `plan-249` both 报告路径拆分（先定结构契约）

**现状**：`report/_generation_both.py::_generate_report_both` 388 行——五个 perf 阶段串行、一份 report_run 生命周期、后台健康检查、HTML/Excel 双产物各自成败混在一处。**契约缺口**：阶段名与顺序是 `perf_history` 跨版本可比性的口径，却只以 `perf.start("…")` 字面量存在。
**结构契约**（6 条）：[`report-both-stage-contract.md`](../plan/report-both-stage-contract.md) —— 阶段名与顺序固定且以阶段表表达、start/stop 必配对（含异常路径）、report_run 生命周期单点、HTML/Excel 成败互不连带、健康检查不阻塞主路径、快照捕获走 `capture_snapshot`（不自行判定）。
**目标形态**：编排壳 ≤ 100 行，五阶段各成 `_stage_*.py`，阶段表 `_BOTH_STAGES` 唯一。
**验收**：阶段表名字序列 == 实跑 `perf.phases` 键序列；`test-perf-report.py --gate` 不退化。

#### `plan-250` LLM 并行编排拆分（先定结构契约）

**现状**：`llm/generators_orchestrator.py::generate_all_llm` 392 行——五类上下文块装配、缓存预检、并行派发、事实锚定、生成后自检、跨模块核对、8（辩论 9）元组返回。**契约缺口**：「同一块实例既进指纹又进提示词」这条最容易静默错的不变式没有断言；返回元组按位置解包。
**结构契约**（6 条）：[`generate-all-llm-stage-contract.md`](../plan/generate-all-llm-stage-contract.md) —— 返回位序固定（第 9 位仅辩论）、块只渲染一次（身份断言）、阶段顺序不变（自检在模块产出之后串行）、单模块失败隔离、强刷范围归一单点、空块与缺省逐字节等价（黄金值基线）。
**目标形态**：编排壳 ≤ 100 行，块装配整组移 `_llm_context_blocks.py`（返回块快照结构体），生成后一遍移 `_llm_post_pass.py`。
**既往拆分**：文件级已由 rf-582（`f0f18601`）下沉 worker 分发到 `_llm_dispatch.py`（798→480 行，此后因自检/跨模块核对/数据质量块增至 863 行）；本项是函数级续拆，不重复论证拆不拆。
**验收**：结构用例（位序/块身份/阶段顺序）+ 缓存矩阵与黄金值基线不变。

#### `plan-251` LLM worker 派发拆分（先定结构契约）

**现状**：`llm/_llm_dispatch.py::_dispatch_llm_workers` 256 行、6 个嵌套闭包——并发上限与 thinking 闸门、worker 包装（HTTP/2 降级、等待记账）、辩论槽位替换、线程池执行、结果归集。**契约缺口**：「提交哪些模块 / 返回什么形状 / 失败如何沉淀」全靠读闭包。
**结构契约**（6 条）：[`llm-dispatch-stage-contract.md`](../plan/llm-dispatch-stage-contract.md) —— 结果键集合 == 提交集合、worker 返回 `(content, from_cache)`、失败不外抛且只登记一次、并发上限与 thinking 闸门不被二次放宽、辩论为槽位替换（键名不变、失败回退原实现）、client 复用与降级判定单点。
**目标形态**：提交与归集壳 ≤ 80 行，拆出 `_worker_runner.py` 与 `_debate_router.py`，闭包捕获改显式参数。
**既往拆分**：本文件即 rf-582 的下沉产物（文件体量已解），本项只解函数内部分界；rf-582 的门面 re-export 与 patch 点纪律继续有效。
**验收**：结构用例（键集合/返回形状/失败登记）+ 并发与辩论用例全绿。

> **P3 大型函数拆分四连项（plan-248~251）共同约束**：四项均为「只动结构、不动行为」的重构，开工前**先定结构契约、再动代码**；每项按契约表逐条写成可断言的结构用例（不写死条数/清单，断言结构关系），既有行为用例全绿后才准提交；四项互不依赖、可各自单独立项推进。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测（三方对照评测脚本未建立）。该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

### 已完成（待发布归档）

## 归档

- [`archived_plan.0.17.x.md`](../archive/v0.17.x/archived_plan.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-08）
- [`archived_plan.0.16.x.md`](../archive/v0.16.x/archived_plan.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
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
