# 投资复盘助手 — 实现计划

> 文档版本：0.18.4-dev
> **编号源**：`plan-next = 266`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-265，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

在办 13 项：P1 3 项（**plan-238**、**plan-239**、**plan-259**）、P2 3 项（**plan-92**、**plan-252**、**plan-253**）、P3 6 项（**plan-70**、**plan-233**、**plan-243**、**plan-254**、**plan-255**、**plan-258**、**plan-265**）、P4 1 项（**plan-55**）。命名与实现纪律见 `CLAUDE.md`（单一事实位，本表不重复）。

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

#### `plan-259` 持仓录入三渠道能力对齐收口

**现状**：录入能力三渠道推进节奏不一——CLI 已闭环，TUI/WEB 两侧实现已落地但真机验收未完成（`plan-238`/`plan-239`），是目前唯一「用户可感知但未收口」的功能面；验收后又需要一次口径对账，避免三渠道各自漂移（校验文案、写回语义、流水记入、并发闸门）。
**前置**：`plan-238` 与 `plan-239` 验收清单全部勾选。
**动作**：① 按三渠道对账表逐项比对（账户/标的输入、份额与金额口径、撤销与清空、`.bak` 与回读校验、流水开关状态、并发闸门错误码）；② 差异项定为「渠道限定」写进手册或修成一致，不允许无声明差异；③ 把对账表落 `docs/managements/test-coverage.md` 的能力矩阵与手册；④ 两档验收记录归档。
**验收**：三渠道对账表无未声明差异；手册三渠道录入流程口径一致；TUI/WEB 验收记录归档、本项转「已完成」。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条，趋势列加迷你折线（openpyxl 原生）；先做持仓明细 / 量化指标 / 集中度 2~3 个页签，验证后再扩。

#### `plan-252` 建议后验评估政策单源化 + 不动作类命中评估

**来源**：PanWatch 借鉴分析（[`panwatch-borrowing-review.md`](../plan/panwatch-borrowing-review.md) §2.1），commit `97f1813`。
**缺口**：账本对 `DIRECTION_FLAT`（持有/观望/不操作）只记平盘不判命中，模型输出里「不操作」占比不低却从不被评估；「什么算命中」的口径散在 `decision_ledger` / `decision_basis_settlement` / `decision_review_block` / `eval-decision-quality` 四处。
**动作**：新增 `core/decision_eval_policy.py` 作评估口径唯一事实位（方向阈值沿用 1.5%、不动作容忍带 2.0%、样本门槛沿用 20、视界单位声明；**零依赖**，账本单向导入并保留原名导出），判定入口仍只有 `classify_direction_outcome` 一个（不新增第二套判定），结算新增 `flat_hit: bool|None` 字段（旧账本无字段按未判、不回填），折叠汇总新增 `flat` 分项与 `by_carrier.flat_*`，报告/`doctor` 并列呈现不动作命中率；同步附录 H 的 `decision_basis_data` 行与 R-OUT-17 口径。
**不做**：不改方向性阈值与样本门槛；不做置信度加权；不参与 `plan-70` 转正判据。
**设计**：[`decision-eval-policy-design.md`](../plan/decision-eval-policy-design.md)（三期：政策与结算 → 呈现 → 自检提示）。

#### `plan-253` LLM 复盘结论结构化契约（claim / evidence / verdict）

**来源**：PanWatch 借鉴分析（[`panwatch-borrowing-review.md`](../plan/panwatch-borrowing-review.md) §2.2 与 §2.3）。
**缺口**：LLM 输出是自由 markdown；`fact_checker` 只校验数值，`decision_llm_capture` 只抽表格；没有「主张→证据→判决」链，也没有「证据时点 ≤ 分析截止」这类可机检约束，建议的 triggers/invalidations 只停留在提示词口头要求。
**动作**：新增开关 `llm_research_contract`（默认关，关闭逐字节不变）。P1 由**该模块提示词输入块**生成内容寻址 `evidence_id` 池（不直接复用 fact_checker 内部语料结构）并追加结构头 `{claims[{id,statement,evidence[],inference,invalidations}],verdict}`；P2 引入 verdict 枚举（ready/revise/evidence_needed/reject）+ 一次预算受限补证（补证轮加缓存键盐，避免命中上一轮正文）；证据时点按报告行情口径 `as_of` 校验、场外滞后净值按披露分档放行；P3「决策书」并入**行动建议章的 LLM 解读位**（紧邻判断依据块；不新增章节/页签，也不写进零 LLM 的判断依据块本体）+ 建议硬约束（review/blocked 不得带数量、限购品种自动带执行约束）。
**不做**：不做 agent 图与工具调用循环；不引入 Pydantic 契约模型；不自动改写正文。
**设计**：[`llm-research-contract-design.md`](../plan/llm-research-contract-design.md)（三期与验收、golden 回归方案）。

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

#### `plan-258` 深层渲染契约收敛（`_render_template` 收上下文对象）

**现状**：`report/html_writer._render_template` 声明 80 个关键字形参并原样转发给 Jinja 渲染；`write_html_report` 有 50+ 入参，
两侧都是长参数表。`plan-257` 已把编排逻辑切完，剩下的纯粹是「参数搬运」。
**动作（条件性）**：`_render_template` 改为接收单个 `_RenderContext` 上下文对象（内部 `render(**vars(ctx))`），
`write_html_report` 的入参分族收敛为该上下文，再逐层下传到调用方；渲染契约（模板变量键集合）由新增守卫用例锁死，
`report_template.html` 不改。
**为何暂不做**：触碰模板变量装配面 + 10 余个调用方，须按字节对拍产物；收益是可读性而非缺陷风险，等下次确有「改渲染入参」需求时一并做，避免为拆而拆。
**已备范式**：同文件链上的 `_prepare_render_context` 已按「来源域 → dataclass」分组把 30 个关键字入参收为 3 个（`rf-1157`），本项沿用同一分族口径即可，无需另立风格。
**验收**：模板变量键集合与拆分前完全一致（守卫用例比对）；同输入产物 SHA 一致；P0/P1 门禁全绿。

#### `plan-254` 不动作建议命中率的真机读数（等样本成熟）

**前置**：账本内不动作类决策（`direction=0`，来源：LLM 表里的持有/观望/不操作行）已登记，当前 7 条；结算需报告日之后 ≥5 个交易日。
**动作**：**距登记日满 5 个交易日后的首次报告运行**即为读数点——无需额外操作，报告自动呈现；届时核对三处：
① 判断依据块「我的建议历史表现」表下方「不动作建议」行（应为 命中 x/y 或 命中率 xx% 的数值形态）；
②「历史决策复盘」块状态取值（判对 / 判偏 / 未到期）；
③ `doctor` 账本概览的「不动作类…」段（样本 ≥20 才给百分比）。
**判据**：三处数值互相一致且与 `fold_ledger()['inaction']` 相符即为通过；若仍为 `—`，查账本是否有 `flat_hit`（结算未跑到该视界）。
**若届时发现登记/结算缺口**：按缺陷流程修（补回归用例 + `review-findings` 登记），不得只改文档。

#### `plan-255` 结构化契约的补证门槛裁决（观察 ≥2 周后）

**前置**：`plan-253` P1/P3 已落地、开关 `llm_research_contract` 默认关；P2 埋点已在「LLM API 用量」页签输出契约统计。
**动作**：开关实际启用运行 ≥2 周后，按用量页签的「结构化契约」行取判决分布，裁决是否启动补证循环（设计见 [`llm-research-contract-design.md`](../plan/llm-research-contract-design.md) §3.3）。
**判据**（两条同时满足才做）：`evidence_needed` 判决 ≥ 模块次 20%；且抽样其中过半属「模型确缺数据」而非「未按格式输出」。
**不做**：门槛未达则永久不做补证（避免为默认关的实验功能引入 dispatch/缓存改动）。
**数据源**：用量页签契约行（`contract_metrics`）+ `data/state/perf_history.jsonl`。

### P4 — 实验候选（先决门槛未过，暂缓）
入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测（三方对照评测脚本未建立）。该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

### 已完成（待发布归档）

#### `plan-265` 守护项价值复核（零命中项降频）

**结果**：`_shared/checklib.report()` 每次运行追加一行命中台账（脚本级 + 可选「子项 → finding 数」），`check-doc-drift` 通过给模块内 `check_*` 函数套计数壳提供子项粒度（不改调用点）；新增 `scripts/probe-guard-hits.py` 输出「守护项 × 运行次数 × 命中次数 × 处置」表，处置三态为「保留 / 建议降频（CI 恒跑兜底）/ 样本不足」。
**边界**：本项只提供读数与建议，**不改任何守护的启用状态与 CI 阻塞语义**；降频动作需人工复核后落 `scripts-reference.md`。
**样本**：台账从本版开始积累，首次有意义的复核门槛是每项 ≥5 次运行（`--min-runs`）。
**守卫**：`test_probe_guard_hits.py`（9 条：聚合/处置判据/损坏行容错/表格与 CLI 退出码）+ `test_checklib_guard_ledger.py`（4 条：记录形态/默认 details/写入失败静默/report 退出码不受影响）。

#### `plan-264` 缓存命中率提升（同事实单键）

**归因**：本轮未命中数居首的是 `fin_indicator`（42 次）——同一 A 股 code 在同一轮里被两条路径各取一次：`report/financial_indicator.py` 取多期序列（键 `fin_indicator_hist_{code}`），基金 ROE 估算与因子目录探测取单期（键 `fin_indicator_{code}`）。两种键并存且互不复用，故每轮每 code 多一次回源。`price_stock` 未命中属正常（行情每次都要最新）。
**动作**：`fetch_latest_indicator` 先读多期缓存：命中即返回头部记录（多期按报告期降序，头部即最新一期），仅未命中时才走链路取数。未改 TTL——财务指标按报告期发布虽可延长 TTL，但会牵动新鲜度/陈旧判定口径，收益小于风险，留作后续按需评估。
**效果**：同一 code 的单期取数由「必回源」降为「多期已取则不回源」（守卫用例以「多期缓存命中时不得调用链路」断言）。
**守卫**：`test_financial_indicator.py::TestSingleFetchReusesSeriesCache`（命中不回源 / 未命中回落链路 / 非 A 股不读缓存）。

#### `plan-263` 本轮降级清单汇总出口

**结果**：新增 `core/degradation.report_degradation_summary(max_items=3)`——按「源 + 失败类型」去重计数本轮 `degraded` 事件（`begin_report()` 已把事件日志限定在本轮，故不另算一套轮次边界），输出 `{count, events, lines, text}`；`_RenderContext.degradation_line` 经模板 `summary_section.html` 在数据状态块尾输出一行（无降级 → 空串 → 该行不渲染，产物逐字节不变），CLI 产物清单尾部同源追加同一行。
**边界**：正文只列前 `max_items` 项，其余以「等 N 项」概括；`count` 为去重项数、`events` 为原始事件数，两者都给出（验收要求的「计数与事件数一致」由此可核）。
**未做**：TUI 收尾未单独加行——TUI 走同一报告渲染器与完成通知，显式打印项留待 TUI 文案批次统一处理（避免单渠道措辞漂移）。
**守卫**：`test_degradation_report_summary.py` 10 条（口径/排序/溢出/读取失败降级/渲染上下文透传/模板条件块/CLI 空与非空两态）。

#### `plan-261` 零直测模块补测（高风险纯函数优先）

**结果**：按风险排序的两批共 5 个模块补齐直测——① `config/_json_patch`（`test_json_patch.py` 34 条 + `_edge.py` 10 条，期间修 `rf-1159`/`rf-1160`/`rf-1161` 三个写回缺陷）；② `analysis/_fee_estimation`（18 条）、`analysis/metrics_risk`（29 条）、`config/_feature_registry`（15 条，只断言结构关系不写死开关条数）、`providers/_news_dedup_tables`（7 条词表不变量 + 判定语义）。
**残余**：剩余模块经模块名检索未命中，但行为由门面用例覆盖（如 `analysis/prosperity_scoring` 经 `prosperity_framework` 用例、`llm/_hallucination_filter` 经辩论用例）；这批不单独立项，后续改动扫到的模块就地补测。

#### `plan-260` 实验项转正判据自动裁决 + 到期提醒

**结果**：新增 `core/experiment_verdicts.py`——项清单由注册表 `experimental_flags()` 派生，逐项把判据收成表（`report_qa` 取 `qa/telemetry.py` 的判据条目，`decision_reflection` 取账本折叠的方向性样本量与超额符号），输出「可转正 / 继续观察 / 撤销候选 / 无读数」四态；`doctor` 新增「实验项裁决」行（判据名 + 实测值 + 结论）与「已达判据 → 请按计划裁决」提醒行。不改开关、不摘 `experimental`（转正/撤销仍人工）。
**边界**：注册表 `experimental=True` 的项共 2 项（`decision_reflection` / `report_qa`）——`signal_ledger` / `prosperity_framework` / `llm_research_contract` / `rebalance_schedule_replay` 是默关闭的功能开关、不属实验生命周期，其判据仍走各自计划条目；未接读数适配器的实验项明说「判据未接读数源」。
**未达项**：原定「达资格同时在报告运行日志出提醒」改为只在 `doctor` 上屏——`doctor` 在启动早期可能先于日志系统建立运行，从那里打 warning 会污染命令行输出（转正提醒属周期性人工核对，无需哏时）。
**守卫**：`test_experiment_verdicts.py` 13 条（项集合与注册表派生相等、四态判定、撤销优先于观察、无读数不臆造、doctor 行接线）。

#### `plan-262` 新闻去重近线性化（标题 blocking 前置）

**结果**：`_dedup_by_title` 的比较范围由两层候选索引给出——实体 bigram → 已保留下标（所有合并规则都要求 overlap ≥ 1）；标题 `_SUBSTRING_MIN_LEN` 窗口 → 已保留下标（「短串 ⊂ 长串」必共享窗口）。两层均未命中的对不进入比较；判定结果逐条一致（保留集合标题序列 SHA 对拍相同，首个命中对下标升序不变）。锚点语料收录范围为实体重叠 ≥ 1 的对（零重叠对恒不合并）。
**实测**（合成语料 1275 条 → 保留 768 条，不依赖网络）：比较对 69,712 → 38,524（−45%），耗时 3.18s → 1.13s（2.8×）；生产语料（单对成本更低、零重叠对占比更高）受益面不小于此值。
**未达项**：原定「降一个量级」未达成——剩余成本在候选对的相似度计算本身（`_ratio_of_norms_bounded`），需改判定口径（拆窗口粒度）才能进一步压低。
**守卫**：`test_news_dedup_perf.py::TestEntityFirstGate`（零重叠对不做重叠/相似度计算、与基线对照逐条一致、子串路径不被连带跳过）。

## 归档

- [`archived_plan.0.18.x.md`](../archive/v0.18.x/archived_plan.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-12）
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
