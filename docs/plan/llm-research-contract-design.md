# LLM 复盘结论结构化契约（claim / evidence / verdict）（plan-253 设计）

> 状态：**P1、P3（硬约束 + 决策书渲染）已实施（默认关）；P2 补证循环按门槛暂缓**。立项见 [`plan.md`](../managements/plan.md) 的 `plan-253`；
> 借鉴来源与取舍见 [`panwatch-borrowing-review.md`](panwatch-borrowing-review.md)。

## 1. 背景与缺口

四个基础 LLM 模块（全球政经局势 / 智囊团深度复盘 / 持仓体检 / 穿透深度）目前输出 **markdown 自由文本**，机检有三层：

| 现有机制 | 覆盖 | 缺口 |
| :--- | :--- | :--- |
| `fact_checker`（数值校验 + 改写护栏 + 覆盖率） | 数字是否与语料一致 | 只校验数值，不校验「结论从哪来」 |
| `decision_llm_capture`（操作建议表 + 决策头 `{code,action,priority}`） | 建议可否入账 | 无证据、无失效条件、无置信度 |
| `llm_quality`（章节齐备 / 篇幅评级） | 形态 | 不评「结论是否有据」 |

目标：补一条**可机检的链路** —— 主张（claim）→ 证据（evidence，可回指提示词输入）→ 判决（verdict）→ 建议（含触发与失效条件），
让「复盘」这个产品承诺可验证（读者能点回证据，事后能对账）。

## 2. 借鉴点（PanWatch）

契约层与门禁：`Evidence{id, available_at}`、`Claim{statement, evidence_ids≥1, inference, invalidations}`、
`RoleReport{claims, issues, verdict}`（`ready/pass/revise/evidence_needed/rebuttal/reject`）、
`Recommendation{outlook, confidence, action, evidence_ids, triggers, invalidations, risks, execution_status, execution_constraints}`；
硬门禁：`ready/pass` 不得残留未决阻塞 issue；要求补证须给具体 issue；`review_required/blocked` 不得带 quantity；
`ResearchResult.completion` 细分完成态；角色级预算预留。

**不照搬**：不引入 Pydantic 契约模型（本仓契约以 dict + 校验函数为事实位，见 pipeline_data 契约附录 H 口径）、不引入 agent 图与工具调用循环。

## 3. 设计（三期，全程默认关）

### 3.1 总原则

- 新增开关 **`llm_research_contract`**，默认关：关闭时提示词与产物**逐字节不变**；
  注册点固定为 `config/_feature_registry.py`（`panel_visible=True`，分组=「机制与质量」，与既有 LLM 质量类开关同组）
  + `requirements.md` 需求条目 + `technical.md` 功能语义命名表（功能开关枚举/默认值/分组单源）。
- 契约层落 `llm/research_contract.py`：**纯校验 + 解析**（零 I/O、零取数、零 LLM 调用）。
- 证据池**由该模块提示词的输入块生成**（不是复用 `fact_checker` 的内部语料结构）：模型只能引用它真正看到的内容，
  两处共用同一批**数据**、不共用内部结构。
- 所有校验失败一律**降级不阻断**：报告照常产出，标注「未验证」。

### 3.2 P1：主张 + 证据（最小可用）

**证据池**：`llm/evidence_index.py::build_evidence_index(prompt_blocks)`，对提示词里已装配的块逐条产出稳定 id：

| 证据种类 | id 形态 | 来源块（提示词内） |
| :--- | :--- | :--- |
| 持仓行 | `ev:hold:<code>` | 【持仓明细】行 |
| 行情/估值 | `ev:quote:<code>` | 【持仓明细】行情列 / 估值分位块 |
| 收益归因 | `ev:attr:<code>` | 【收益归因】行 |
| 结算/评估 | `ev:settle:<horizon>` | 【建议历史表现】行 |
| 新闻 | `ev:news:<8 位内容哈希>` | 【财经热点】/【事件窗】行 |
| 组合指标 | `ev:metric:<name>` | 【量化指标】行（beta/夏普/回撤等） |

- id 规则：`ev:<kind>:<稳定键 | 8 位内容哈希>`，长度固定、与缓存键命名（`llm_*`/`price_*`）**不同前缀**，避免混淆；
- 每个 id 附**一行摘要**（不给全文），索引整体控制在 ≤ 输入块长度的 15%，避免 token 膨胀。

**提示词追加段**（仅开关开时）：

```text
【结构化主张】
在回复正文之后追加一行机器可读 JSON（仅一行）：
契约头：{"claims":[{"id":"c1","statement":"…","evidence":["ev:hold:561910"],"inference":true,"invalidations":["…"]}],"verdict":"ready"}
规则：每条主张至少引用 1 个 evidence id，且只能取自下方【证据索引】；推断性结论 inference=true；
      invalidations 写清「什么情况推翻这条」；宁少勿滥（2~6 条）。
```

**解析与校验**（`llm/research_contract.py`）：

- `parse_claims(text)`：复用既有 `core/decision_header._match_json_end` 括号配对扫描（与决策头同一实现，不新写解析器）；
- `validate_claims(claims, index, as_of)`：
  - 未知 evidence id / 空证据 / 缺 invalidations ⇒ 该条标「未验证」，并计入模块 `validation_errors`；
  - **证据时点 ≤ as_of**：`as_of` 取「本次报告的数据口径」——即 `market_snapshot_bucket().as_of`（行情口径桶基准日），
    场外净值滞后（T-1/T-2）按我们已有的披露分档口径**放行到该品种的净值日**，不因滞后判为越界；
  - `inference` 缺省视为 true（不因缺失判错）。

**落点**：`llm_content[module]["claims"]` 附在既有内容旁（不改 markdown 主体）。渲染层在**该模块章节末尾**加折叠块
「主张与证据」（默认收起）。

**缓存兼容（必须写进实现）**：

- 旧缓存 payload 无 `claims` 键 ⇒ 渲染层按「无契约」处理（不报错、不显示折叠块）；
- 提示词文本变更 ⇒ 递增 `PROMPT_SCHEMA_VERSION`（既有纪律，换键重算）；
- 契约头的字段演进只做**加字段**，不做改名（避免旧缓存 payload 解析失败）。

### 3.3 P2：判决枚举 + 一次补证

- 模块级 `verdict ∈ {ready, revise, evidence_needed, reject}`：
  - `ready`：全部主张通过校验且无未决争点；
  - `evidence_needed`：模型自陈缺证据，或校验发现未知 evidence id 且声明需补数；
  - `revise`：数值校验改写护栏触发后仍存疑；
  - `reject`：主张与证据矛盾（数值冲突 ≥ 2 处）。
- 与既有闸门分工：**数值真伪归 `fact_checker`**，证据归属/时点归本契约；冲突以数值为准（数值是硬事实）。
- 补证循环（**上限 1 次**，预算闸预留额度）——**当前暂缓实施**，启动门槛：开关实际运行 ≥2 周后，`evidence_needed` 判决占模块次 ≥20% 且其中过半为「模型确缺数据」而非「未按格式输出」；门槛未达则不做：
  - 仅当 `evidence_needed` 且预算允许时，用同一份证据索引做一次窄重问（提示词明确「只补证据，不重写全文」）；
  - **缓存键盐**：补证轮请求必须带 `supplement=1` 键盐（或在补证轮禁用读取），否则会命中上一轮正文缓存；
  - 记账：每模块 `verdict` 分布、补证次数、补证后转 `ready` 比例进 `llm_usage`/`perf_history`（不新增账本文件）；
  - 预算耗尽 ⇒ 模块 `completion=budget_exhausted`（沿用现有 LLM 模块状态口径），呈现为「未验证」。

### 3.4 P3：决策书（并入行动建议章 LLM 解读位）+ 建议硬约束

**位置（硬约束）**：决策书**不并入判断依据块**——该块契约是「纯确定性、零 LLM、`enable_llm` 两态输出一致」
（`report/decision_basis.py` docstring 与 R-OUT-17 均如此声明），塞入 LLM 主张会破坏其契约与回滚通道。
落地位置：**行动建议章内的 LLM 解读段**（其章节内、紧邻判断依据块之后），由 `llm_research_contract` 开关控制；
不新增章节、不新增 Excel 页签。

- 呈现：主张 → 证据（可展开摘要）→ 判决 → 建议（triggers / invalidations / risks）；HTML 用既有折叠块样式，
  Excel 在同一页签内以「块标题 + 若干行」呈现（复用 `write_block_title`/`write_data_row`，不改列数）；
- 建议硬约束下沉到 `analysis/rebalance_advisor.py` 与 `decision_llm_capture`（**已部分实施**：`validate_recommendation()` 校验期拒绝 review/blocked 带数量；判决 `reject` 不入账、未验证降级标注）：
  - `execution_status ∈ {conditional, blocked, not_applicable}`；
  - `review_required` 或 `blocked` 的建议**不得带 quantity**（校验期拒绝，等价于对方 `review_is_not_a_trade`）；
  - 已暂停申购/限购品种：建议自动带 `execution_constraints`（复用 `purchase_status_data`）。
- 匿名化：`full_anonymous` 下主张文本同样过 `mask_display_text(alias_map)`（与明细/提示词同一映射），
  否则决策书会泄露真值（证据 id 中的代码按同一规则掩码，仅展示层处理）。

### 3.5 成本与性能上限

| 项 | 上限 |
| :--- | :--- |
| 证据索引 token | ≤ 输入块的 15% |
| 补证调用次数 | 每模块 ≤ 1 次/报告（4 模块 ⇒ 最多 +4 次调用） |
| 解析耗时 | ≤ 5ms/模块（纯正则 + json） |

埋点：`claims` 条数、`validation_errors` 数、`verdict` 分布、补证次数、索引字节数进 `llm_usage` 明细（只增字段）。

### 3.6 契约与文档触点（每期同步，缺一即视为未完成）

| 触点 | 动作 |
| :--- | :--- |
| `config/_feature_registry.py` | 注册 `llm_research_contract`（默认关、分组、`panel_visible=True`） |
| `requirements.md` | 新增需求条目（claim/evidence/verdict 口径、开关、成本上限） |
| `technical.md` | 功能语义命名表 + LLM 层职责链补 `research_contract` / `evidence_index` |
| `llm-technical.md` | 模块表新增两模块；提示词结构头说明；`PROMPT_SCHEMA_VERSION` 递增说明 |
| 附录 H（若涉 pipeline 键） | `llm_content` 不属 pipeline_data 键；若将来落 `pipeline_data` 再登记 |
| `test-coverage.md` / `folders.md` | 新测试文件与用例计数（采集器回写） |

### 3.7 分期与验收

| 阶段 | 交付 | 验收 |
| :--- | :--- | :--- |
| P1 | 证据索引 + 主张契约 + 校验 + 章节末尾折叠块（开关关=零变化）——**已实施** | 契约矩阵（未知 id/空证据/越界/缺 invalidations）；开关关逐字节回归；证据 id 可回指提示词块；旧缓存无 claims 不报错 |
| P2 | verdict 枚举（已在 P1 派生）+ 一次补证（键盐）+ 统计——**补证循环未实施** | verdict 分布可读；补证后转 ready 比例可读；预算耗尽记 `budget_exhausted`；补证达上限收口「未验证」 |
| P3 | 决策书（行动建议章 LLM 解读位）**已实施**（`report/decision_book.py`，匿名化模式非 off 时不出块）；建议硬约束**已实施** | review/blocked 带数量被拒（单测）；HTML/Excel 同源；`purchase_status` 联动；匿名化掩码一致 |

## 4. 测试方案

- **契约校验矩阵**：evidence 未知 / 空 / 越界 / 缺 invalidations / verdict 非法值 / claims 为空；
- **解析器复用**：断言与决策头共用 `_match_json_end`（不新增解析实现）；
- **证据可回指**：随机取 claim 的 evidence id，断言能在**该模块提示词输入块**里找到；
- **时点校验**：构造 `available_at > as_of` 与「场外净值 T-2 放行」两类样本；
- **缓存兼容**：注入无 `claims` 的旧 payload，渲染不抛错且不显示折叠块；
- **开关回归**：关闭时提示词哈希与产物逐字节一致；
- **golden 回归**：输入为**冻结的模型输出样本文件**（不是实时调用），断言「解析 + 校验 + 渲染」三段结果稳定；
- **成本守卫**：断言证据索引字节数 ≤ 输入块 15%（构造大输入样本）；
- **硬约束**：`review_required`/`blocked` 带 quantity 被拒。

## 5. 风险与对策

| 风险 | 对策 |
| :--- | :--- |
| 提示词变长 ⇒ token 成本 | 索引只给 id + 一句摘要；默认关；预算闸；补证 ≤1 次 |
| 模型不遵从 JSON 头 | 复用决策头同一解析器 + 失败降级「无契约」 |
| 与 `fact_checker` 重复 | 分工写死：数值归 fact_checker，证据归属/时点归本契约，冲突以数值为准 |
| 缓存错配（命中旧正文 / 补证命中上一轮） | 递增 `PROMPT_SCHEMA_VERSION`；补证轮加键盐 |
| 报告信息膨胀 | 折叠默认收起；`reject` 不渲染决策书 |
| 匿名化泄露 | 主张与证据展示同走 `alias_map` 掩码 |
| 「未验证」被读成「错误」 | 文案口径统一「未验证（证据不足）」，不染状态色 |

## 6. 不做

- 不做多 agent 辩论图 / 工具调用循环（已有辩论，离线报告无回环需求）；
- 不引入 Pydantic 契约模型与数据库表；
- 不自动改写正文（改写仍归 `fact_checker` 护栏链路）；
- 不做证据置信度加权与权重回灌（等 `plan-252` 评估链路稳定后再议）；
- 不新增独立「决策书」章节/页签，也不并入**判断依据块本体**（该块零 LLM 契约，见 §3.4）。

## 7. 依赖顺序

`plan-252` 先于本项：252 的评估口径与报告呈现位用于 P3 决策书的验收对照；两者互不改对方的开关与阈值。

## 8. 术语表

| 术语 | 代码标识 | 说明（中文口径，不音译） |
| :--- | :--- | :--- |
| 主张 | `claim` | 一句可判真伪的结论，必须挂证据 |
| 证据 | `evidence` | 提示词输入块里的一个可回指片段（id + 摘要） |
| 判决 | `verdict` | 模块级结论状态：ready / revise / evidence_needed / reject |
| 失效条件 | `invalidations` | 推翻该主张的具体情形 |
| 补证 | `supplement` | 仅针对证据缺口的一次窄重问（上限 1 次） |
| 未验证 | — | 校验未通过但报告照常产出时的标注（非错误） |

## 9. 实施验证（真机）

启用态全量报告（`--feature llm_research_contract=true report --type full`）验证结论：

- HTML：各模块正文后出现「主张与证据」折叠块（判决 + 证据 id + 失效条件）；行动建议章内出现「决策书（主张与证据）」块；
- Excel：「行动建议」页签落决策书小节，各 LLM 模块页签落「主张与证据」小节（同一契约字段）；
- 判决分布：本次四模块均为「证据齐备」（`evidence_needed` 占比 0，尚未触发补证门槛）；
- 成本：本轮 8 次 LLM 调用、¥0.1005（含契约段后的提示词增量）。

## 10. 事实位索引

- 开关：`config/_feature_registry.py`（`llm_research_contract`，默认关）
- 证据池：`llm/evidence_index.py::build_evidence_index`
- 契约解析/校验：`llm/research_contract.py`
- 解析原语：`core/decision_header._match_json_end`（唯一）
- 提示词追加段：各模块 prompt builder（`llm/prompts_*.py`）
- 渲染：该模块章节末尾折叠块（HTML）/ 行动建议页签内块（Excel）
- 时点基准：`core/market_hours.market_snapshot_bucket().as_of` + 场外披露分档