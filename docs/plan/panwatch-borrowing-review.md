# PanWatch 借鉴分析（来源盘点 + 采纳/不采纳结论）

> 状态：**仅分析，不排期**。采纳项已分别立项为 [`plan-252`](../managements/plan.md) / [`plan-253`](../managements/plan.md)，实施须另行指令。
> 分析对象：`https://github.com/TNT-Likely/PanWatch`，commit `97f1813`（2026-11-08，MIT 许可）。
> 本地副本：`docs/tmp/PanWatch/`（`docs/tmp/` 属 git 忽略域，副本与本次分析不进入仓库产物，也不改动本方程序/配置/文档目录）。

## 1. 对方项目定位

**盯盘侠 PanWatch**：自托管 **AI 盯盘服务**（Docker 单镜像 + Web 工作台 + PWA），管 A 股/港股/美股持仓，围绕「**盯盘 + 提醒 + 定时 Agent 投研 + 消息推送**」做常驻服务：

| 能力 | 说明 |
|:---|:---|
| 多账户持仓 | 多券商账户、盈亏、交易风格 |
| AI 投研（TradingAgents） | 分析师（技术/情绪/新闻/基本面）→ 多空辩论 → 风控审查 → PM 决策书，3~5 分钟一条完整推理链 |
| 定时 Agent | 按交易日跑盘前/盘中/盘后工作流 |
| 价格提醒 | AND/OR 条件组合 + 冷却时间 + 日上限 + 到期 + 多渠道推送 |
| 机会发现 / 模拟盘 | AI 评分候选 + 入场/目标/风险；模拟建仓与净值绩效 |
| 工程形态 | Python（FastAPI + 业务模块）+ 5 个内部包（marketdata / agent-runtime / token-meter / tool-research / investment-research）+ React 前端 |

**与我方差异**：本方（投资复盘助手）是**离线报告生成器**——读持仓 Excel → 出 Excel/HTML 报告 → 决策账本 + LLM 复盘；无常驻服务、无提醒、无推送、无前端登录。因此借鉴只取「**决策质量可验证**」与「**LLM 结论可审计**」两条主线，其余能力受形态差异限制不予采纳。

## 2. 可借鉴点（已立项）

### 2.1 建议的**后验评估政策**是公开单源，且「不动作类」也评估

对方 `src/modules/automation/agent_prediction_evaluation.py` 把「什么算命中」收敛成一份公开政策：

```python
EVALUATION_POLICY = {
    "horizon_unit": "trading_days",
    "flat_threshold_pct": 2.0,
    "actions": {
        "buy": "后续收益大于 0 记为命中",
        "sell": "后续收益小于 0 记为命中",
        "hold": "后续绝对收益小于 2% 记为命中",   # 不动作类同样可评估
        "watch": "后续绝对收益小于 2% 记为命中",
    },
}
classify_prediction_hit(action, return_pct) -> bool | None   # 无可判定返回 None
group_prediction_outcomes(rows)   # 多视界 pivot 成单行复盘
summarize_prediction_groups(...)  # 覆盖/命中/均值收益 + pending 计数
```

POINT：**规则集中 + 可判定性显式（None 表示不可判定）**，API 与前端都读同一份，不各自复制。

**我方缺口**：`core/decision_ledger.classify_direction_outcome()` 对 `DIRECTION_FLAT`（持有/观望/不操作）直接返回 `(flat, None)`——即**不动作类建议从不进入命中统计**，而模型输出里「不操作」占比不低（本次运行日志：`无方向 4 条（含「不操作」）`）。同时「什么算命中」的口径散在 `decision_ledger` / `decision_basis_settlement` / `decision_review_block` / `scripts/eval-decision-quality.py` 四处，文档口径另写一遍。

→ 立项 **`plan-252`**：评估政策单源化 + 不动作类命中评估（设计见 [`decision-eval-policy-design.md`](decision-eval-policy-design.md)）。

### 2.2 LLM 结论的**结构化契约**（主张 / 证据 / 判决）与硬门禁

对方 `packages/pan-investment-research/.../contracts.py` 用 Pydantic 把一次投研结论钉成可机检结构：

| 契约 | 关键字段（节选） | 借鉴价值 |
|:---|:---|:---|
| `Evidence` | 证据 id、来源、`available_at` | 证据可溯源、可校验时点 |
| `Claim` | `statement` + `evidence_ids`(≥1) + `inference` + `invalidations` | 每个主张必须挂证据；写清**何时该推翻** |
| `Issue` | 域（technical/flow/events）+ `claim_ids` + 答辩方（bull/bear） | 争点可追踪到主张 |
| `Recommendation` | outlook / `confidence` / action / `evidence_ids` / triggers / invalidations / risks / `execution_status` / `execution_constraints` | 建议自带触发与失效条件、执行态 |
| `RoleReport` | claims / issues / `verdict`（ready/pass/revise/**evidence_needed**/rebuttal/reject） | 角色可「要求补证」而非硬答 |
| `ResearchResult` | `completion`（complete/skipped/**timeout**/**budget_exhausted**/**validation_failed**/risk_rejected） | 完成态细分，便于统计与降级 |
| `ResearchPolicy` | profile / graph / debate / `max_attempts` / `max_tools` / `max_tool_rounds` / budget | 流程与成本单点可配 |

配套门禁（`engine.py`）：`ready/pass` 的报告中不得残留未决阻塞 issue；`risk` 要求补证必须给具体 issue；`review_required/blocked` 的建议**不得带 quantity**（复核态不能授权数量）。

**我方缺口**：LLM 复盘是自由 markdown + `fact_checker` 只校验数值 + `decision_llm_capture` 靠表格/决策头解析；没有「主张→证据→判决」链，也没有「证据时点 ≤ 分析截止」这类可机检约束；建议里的 triggers/invalidations 只有提示词层面的口头要求。

→ 立项 **`plan-253`**：LLM 复盘结构化契约（分期，默认关开关，设计见 [`llm-research-contract-design.md`](llm-research-contract-design.md)）。

### 2.3 附带借鉴（并入上面两项，不单独立项）

- **角色级预算预留**：对方按 role 预留预算槽（`reserve = {...}.get(role, 4)`），预算耗尽记 `budget_exhausted` 完成态而非直接失败。我方预算闸是「全局日预算 + 中止」两态，可借鉴到 plan-253 的补证循环（每轮预留额度）。
- **评测框架组织**：对方 `tests/eval/`（cases + `judge.py` + `test_structured_golden.py`）把「用例集 → 判定器 → 结构化 golden」分层；我方 `scripts/eval-*` 偏脚本化，缺 golden 快照回归。并入 plan-253 的验收方案。

## 3. 不采纳清单（含理由）

| 对方能力 | 不采纳理由 |
|:---|:---|
| 价格提醒引擎（AND/OR + 冷却 + 日上限 + 到期） | 需常驻进程与逐笔行情轮询，与本方「离线出报告」形态冲突；本方已用「决策账本 + 结算 + 纪律静默」覆盖「事后复核」诉求 |
| 消息推送多渠道（Telegram/企微/钉钉/飞书/Bark） | 本方已有 `notify`（webhook/email）且推送粒度是「报告完成」；多渠道路由价值低于维护成本，暂不引入 |
| 定时 Agent（盘前/盘中/盘后工作流） | 需守护进程 + 交易日调度 + 幂等/补跑语义；本方由用户手动触发报告，调度价值不成立 |
| 模拟盘（成交建模 / 净值曲线 / 绩效） | 与「决策账本结算」功能重叠且更重（持仓/资金/成交模型）；若将来要做，前置是 plan-252 的评估政策先稳定 |
| 机会发现 + AI 评分选股 | 本方以**持仓复盘**为中心，候选基金比较（`candidate_compare`）已覆盖小范围同类比较；全市场评分需全市场数据底座，超出范围 |
| 多市场行情（A/港/美股个股）+ 登录/多租户 + PWA | 本方数据结构与渠道（Excel/TUI/CLI/Web 工作台）已定，引入会牵动权限与数据层，无对应需求 |
| TradingAgents 式 9-agent 图与工具调用循环 | 本方已有「智囊团辩论 + 持仓体检 + 穿透深度」并在离线报告内串行；引入 agent 图会带来多轮工具调用成本与不确定性，收益低于 plan-253 的契约化 |

## 4. 复用纪律

- 对方为 MIT 许可，但本方一律**只借鉴设计意图**，代码自行按本方语义名重写（禁止带入 `plan-*`/对方模块名/对方术语进代码标识符，遵守本方语义命名与痕迹纪律）。
- 对方术语与本方口径冲突时以本方为准（例：对方 `flat_threshold_pct=2.0` 与我方 `DIRECTION_THRESHOLD=1.5%`——**不改现有方向性口径**，仅为不动作类单独设阈值，见设计稿）。
- 本地副本仅作分析用；如需保留引用证据，只在本文件记录「文件路径 + 关键片段摘要」，不拷贝源码入仓。
