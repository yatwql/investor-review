# LLM 复盘结论结构化契约（claim / evidence / verdict）（plan-253 设计）

> 状态：**设计稿，未实施**。立项见 [`plan.md`](../managements/plan.md) 的 `plan-253`；借鉴来源与取舍见 [`panwatch-borrowing-review.md`](panwatch-borrowing-review.md)。

## 1. 背景与缺口

本方 LLM 侧现状：四个基础模块（全球政经局势 / 智囊团深度复盘 / 持仓体检 / 穿透深度）输出 **markdown 自由文本**，另有三层机检在跑：

| 现有机制 | 覆盖 | 缺口 |
|:---|:---|:---|
| `fact_checker`（数值校验 + 改写护栏 + 覆盖率统计） | 数字是否与语料一致 | 只校验数值；不校验「结论从哪来」 |
| `decision_llm_capture`（操作建议表 + 结构化决策头 `{code,action,priority}` 解析） | 建议可否入账 | 无证据、无失效条件、无置信度 |
| `llm_quality`（章节齐备/篇幅评级） | 形态 | 不评「结论是否有据」 |
| `self_review`（自检） | 内部一致性 | 自检本身也是自由文本 |

需要一条**可机检的链路**：主张（claim）→ 证据（evidence，可回指语料/契约字段）→ 判决（verdict）→ 建议（recommendation，含触发与失效条件）。它让「复盘」这个产品承诺可验证：读者能点回证据，事后能对账。

## 2. 借鉴点（来自 PanWatch）

契约层（`packages/pan-investment-research/.../contracts.py`）与门禁（`engine.py`）：

- `Evidence{id, source, available_at}`：证据有身份、有可用时点；
- `Claim{statement, evidence_ids(≥1), inference, invalidations}`：**主张必须挂证据**，且写明何时失效；
- `RoleReport{claims, issues, verdict}`，`verdict ∈ {ready, pass, revise, evidence_needed, rebuttal, reject}`：**允许「要求补证」而非硬答**；
- `Recommendation{outlook, confidence, action, evidence_ids, triggers, invalidations, risks, execution_status, execution_constraints}`；
- 硬门禁：`ready/pass` 不得残留未决阻塞 issue；`risk` 要求补证须给具体 issue；`review_required / blocked` 的建议**不得带 quantity**；
- `ResearchResult.completion ∈ {complete, skipped, timeout, budget_exhausted, validation_failed, risk_rejected}`：完成态细分，便于统计与降级；
- 角色级预算预留（`reserve`）与 `max_attempts / max_tool_rounds` 单点配置。

**不照搬**：不用 Pydantic 模型作为本仓事实位（本仓契约以 dict + 校验函数表达，见「pipeline_data Schema 契约」）；不引入 agent 图与工具调用循环。

## 3. 设计（三期，全程默认关开关）

### 3.1 总原则

- **新增开关** `llm_research_contract`（默认关）：关闭时提示词与产物**逐字节不变**（回滚通道）；
- 契约层落在 `llm/research_contract.py`（纯校验 + 结构化输出解析，零 I/O）；
- 证据池来自既有语料装配：`fact_checker` 的 corpus（持仓/行情/归因/新闻块）**已是单一事实源**，只需为每个块生成稳定 `evidence_id`（内容寻址短哈希），不新增取数；
- 所有校验失败一律**降级不阻断**：报告照常产出，标注「未验证」。

### 3.2 P1：主张 + 证据（最小可用）

提示词侧（仅开关开时追加一段）：

```text
### 结构化主张
在回复正文之后追加一行机器可读 JSON（仅一行）：
契约头：{"claims":[{"id":"c1","statement":"...","evidence":["ev:holdings:561910"],"inference":true,"invalidations":["..."]}],"verdict":"ready"}
规则：每条主张必须至少引用 1 个 evidence id；evidence id 只能取自下方【证据索引】；
      推断性结论 inference 必须为 true；invalidations 写「什么情况推翻这条」。
```

- 【证据索引】由 `evidence_ids_for_corpus()` 生成：`ev:holdings:<code>` / `ev:quote:<code>` / `ev:attribution:<code>` / `ev:news:<n>` / `ev:settlement:<horizon>`，附一行摘要，让模型只能「引用」不能「虚构」；
- 解析与校验（`llm/research_contract.py`）：
  - `parse_claims(text)` → `[{id, statement, evidence, inference, invalidations}]`；
  - `validate_claims(claims, allowed_ids)`：未知 evidence id、空证据、缺 invalidations ⇒ 记 `validation_error`（该条主张标「未验证」，不进 `ready`）；
  - 时点校验：`evidence.available_at <= 报告 as_of`（沿用 `market_snapshot_bucket` 口径），越界即判无效——**这是对方最有价值的一条**：防止模型引用「未来数据」或用盘后数据描述盘中结论。

产物：`llm_content[module]["claims"]` 附在既有内容旁（不改变 markdown 主体），渲染层在章节末尾加折叠块「主张与证据」。

### 3.3 P2：判决枚举 + 一次补证

- 模块级 `verdict ∈ {ready, revise, evidence_needed, reject}`：
  - `ready`：全部主张通过校验且无未决争点；
  - `evidence_needed`：模型自陈「缺某证据」，或校验发现未知 evidence id 且模型声明需补数；
  - `revise`：数值校验触发改写护栏后仍存疑；
  - `reject`：主张与证据矛盾（数值冲突 ≥N 处）。
- 补证循环（上限 1 次，预算闸预留）：
  - 只在 `evidence_needed` 且预算允许时，用**同一份证据索引**做一次窄重问（提示词里明确「只补证据，不重写全文」）；
  - 记账：`llm_research_contract` 统计每模块 `verdict` 分布、补证次数、补证后转 ready 比例（进 `perf_history`/`llm_usage`，不新增账本文件）。
- 与既有闸门的关系：不替代 `fact_checker`，而是**并列**；两处结论冲突时以数值校验为准（数值是硬事实）。

### 3.4 P3：决策书区块 + 建议硬约束

- 报告新增（或并入判断依据块）「决策书」：主张 → 证据（可展开摘要）→ 判决 → 建议（triggers / invalidations / risks），HTML 与 Excel 同源；
- 建议硬约束下沉到 `analysis/rebalance_advisor.py` 与 `decision_llm_capture`：
  - `execution_status ∈ {conditional, blocked, not_applicable}`；
  - `review_required` 或 `blocked` 的建议**不得带 quantity**（校验期拒绝，等价于对方 `review_is_not_a_trade`）；
  - 已暂停申购/限购品种：建议自动带 `execution_constraints`（复用现有 `purchase_status_data`）。

### 3.5 分期与验收

| 阶段 | 交付 | 验收 |
|:---|:---|:---|
| P1 | 证据索引 + 主张契约 + 校验 + 报告折叠块（开关关=零变化） | 契约解析/校验单测（未知 id、空证据、时点越界、缺 invalidations）；开关关逐字节回归；证据 id 可回指语料 |
| P2 | verdict 枚举 + 一次补证 + 统计 | verdict 分布与补证转化率可读；预算耗尽记 `budget_exhausted`；补证达上限即收口为「未验证」 |
| P3 | 决策书区块 + 建议硬约束 | review/blocked 带数量被拒（单测）；双端同源；`purchase_status` 联动 |

## 4. 测试方案

- **契约校验矩阵**：evidence 未知/空/越界、inference 缺省、invalidations 空、verdict 非法值；
- **开关回归**：关闭时提示词哈希与产物逐字节一致（沿用现有开关回归形态）；
- **golden 回归**（借鉴对方 `test_structured_golden`）：同一份语料 + 同一份模型输出文本 ⇒ 同一解析结果与同一 verdict；
- **证据可回指**：随机抽 claim 的 evidence id，断言能在语料装配产物里找到对应块；
- **时点校验**：构造 `available_at > as_of` 的证据，断言判无效；
- **降级不阻断**：校验失败仍产出报告，模块状态标「未验证」。

## 5. 风险与对策

| 风险 | 对策 |
|:---|:---|
| 提示词变长 ⇒ token 成本上升 | 证据索引只给 id + 一句摘要（不给全文）；默认关，用户显式开启；预算闸预留 |
| 模型不遵从 JSON 头 | 与既有决策头同机制（`_match_json_end` 括号配对解析 + 失败降级为「无契约」），不引入新解析器 |
| 契约与既有 `fact_checker` 重复 | 分工写死：数值真伪归 `fact_checker`，证据归属/时点归本契约；冲突以数值为准 |
| 缓存键失效 | 提示词文本变更 ⇒ 递增 `PROMPT_SCHEMA_VERSION`（既有纪律） |
| 报告信息膨胀 | P1 折叠块默认收起；P3 区块仅在开关开且 verdict ≠ reject 时渲染 |

## 6. 不做

- 不做多 agent 辩论图/工具调用循环（本方已有辩论，且离线报告无工具回环需求）；
- 不把契约落成 Pydantic/数据库模型（本仓契约以 dict + 校验函数为事实位）；
- 不做「按 verdict 自动改写正文」（改写仍归 `fact_checker` 的护栏链路）；
- 不做证据置信度加权与自动权重回灌（缺校准数据，等 plan-252 的评估链路稳定后再议）。
