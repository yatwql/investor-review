# 建议后验评估政策单源化 + 不动作类命中评估（plan-252 设计）

> 状态：**设计稿，未实施**。立项见 [`plan.md`](../managements/plan.md) 的 `plan-252`；借鉴来源与取舍见 [`panwatch-borrowing-review.md`](panwatch-borrowing-review.md)。

## 1. 背景与缺口

本方已有完整的「建议 → 账本 → 结算 → 复盘」链路：`core/decision_ledger.py`（登记/结算/折叠）、`report/decision_basis_settlement.py`（按视界命中率与超额）、`report/decision_review_block.py`（历史决策复盘块）、`scripts/eval-decision-quality.py`（离线评测）。

现存的三个缺口：

| # | 缺口 | 表现 |
|:---|:---|:---|
| 1 | **不动作类建议从不被评估** | `classify_direction_outcome()` 对 `DIRECTION_FLAT` 直接返回 `(flat, None)`，`directional` 只统计 ±1 方向；模型输出里「持有/观望/不操作」占比不低（运行日志：`无方向 4 条（含「不操作」）`），事后无法回答「叫你别动，事后看对不对」 |
| 2 | **「什么算命中」的口径散在多处** | 阈值 `DIRECTION_THRESHOLD`、样本门槛 `MEANINGFUL_SAMPLE`、平盘归类、按视界聚合分别落在 4 个消费方；文档口径另写一遍；新增一类建议时必须逐个改 |
| 3 | **没有可对外声明的评估政策** | 报告与 CLI 只能各自解释「命中率怎么算」，无法像「公开政策常量」那样被测试与文档直接引用 |

## 2. 借鉴点（来自 PanWatch）

- `EVALUATION_POLICY` 作为**公开 dict** 暴露「什么算命中」，含 `horizon_unit` 与平盘阈值；
- `classify_prediction_hit(action, return_pct) -> bool | None`：**可判定性显式**（None ≠ False）；
- 「不动作类」用**绝对收益阈值**判命中（|收益| < 阈值 ⇒ 持有/观望判对）；
- `group_prediction_outcomes` / `summarize_prediction_groups` 把多视界记录 pivot 成单行并汇总（覆盖数 / 命中数 / 命中率 / 均值收益 / pending 计数）。

本方**不照搬**其动作词表（buy/sell 等）：本方账本以 `direction`（+1/0/−1）+ `carrier`（来源载体）表达，动作词只存在于 LLM 表解析层。

## 3. 设计

### 3.1 新增单源模块 `core/decision_eval_policy.py`

只放「评估口径」，不放业务逻辑：

```python
#: 方向性命中口径（沿用既有事实位，不新起一套）
DIRECTION_HIT_THRESHOLD = 0.015     # ← 直接引用 decision_ledger.DIRECTION_THRESHOLD
#: 不动作类平盘阈值（新增：持有/观望「判对」的容忍带）
FLAT_HIT_TOLERANCE = 0.02
#: 有效样本门槛（沿用）
MEANINGFUL_SAMPLE = 20
#: 视界单位（本项目结算即按交易日，写死为常量以便对外声明）
HORIZON_UNIT = "trading_days"

EVAL_POLICY: dict[str, object] = {          # 对外声明（报告/CLI/文档同源引用）
    "horizon_unit": HORIZON_UNIT,
    "direction_hit_threshold_pct": DIRECTION_HIT_THRESHOLD * 100,
    "flat_hit_tolerance_pct": FLAT_HIT_TOLERANCE * 100,
    "directional_rules": "方向性：涨(>+阈值)判看多命中、跌(<-阈值)判看空命中、带宽内记平盘不判",
    "flat_rules": "不动作类：|区间收益| < 容忍带 ⇒ 命中；越带 ⇒ 未命中；无收益数据 ⇒ 不可判定",
}

def classify_flat_outcome(raw_return: float | None) -> tuple[str, bool | None]: ...
```

约束：

- **不改既有方向性口径**（仍是 1.5%），只新增不动作类阈值（2.0%，与对方一致，且明显宽于方向阈值——「别动」判对本来就该更宽容）；
- `decision_ledger` 反向 import 本模块得到阈值常量，保证「阈值只有一个事实位」；
- 本模块零依赖（不 import 账本、不 import 报告），避免形成 `core → report` 反向依赖。

### 3.2 结算口径扩展（账本向后兼容）

`classify_direction_outcome()` 只增不改签名：

| 输入 | 现在 | 改后 |
|:---|:---|:---|
| `direction=0` | `(flat, None)` | 仍返回 `(flat, None)`，但**新增独立字段** `flat_judged`（True/False，None=不可判） |

不把不动作类并入 `directional`（否则「方向命中率」被稀释、历史读数不可比）。落在 settlement 记录上：

```json
{"target_horizon": 5, "raw_return": 0.012, "outcome": "flat", "flat_judged": true, ...}
```

- 旧账本无 `flat_judged` 字段 ⇒ 读侧按 `None`（未判）处理，**不回填、不改变历史统计**；
- 新写入只对 `direction=0` 的决策写该字段（±1 方向不写，避免噪声字段）。

### 3.3 折叠与汇总（`fold_ledger`）

- `by_carrier` 每项新增 `flat_total` / `flat_hit`（不动作类样本与命中数）；
- 顶层新增 `flat`：`{total, hit, hit_rate, sample_sufficient}`，`hit_rate` 在 `flat_total < MEANINGFUL_SAMPLE` 时给「命中/总数（样本不足）」而不是百分比；
- `directional_total` / 既有字段**语义不变**。

### 3.4 呈现

| 渠道 | 位置 | 内容 |
|:---|:---|:---|
| HTML/Excel | 判断依据块「我的建议历史表现（按视界）」表格下方新增一行 | `不动作建议：命中 x/y（样本不足）或 xx%（n=y）`；数据缺失显式 `—` |
| HTML/Excel | 历史决策复盘块 | 逐条显示 `不动作→判对/判偏/未到期` |
| CLI | `doctor` 账本概览 | 与方向性命中率并列一行 |
| 报告口径 | `EVAL_POLICY` 原文 | 折叠块脚注引用政策常量，不写死文字 |

双端同源：文案与数值由 `decision_basis_settlement` 一处产出，模板只拼接（沿用现有「渲染层零计算」约定）。

### 3.5 分期

| 阶段 | 内容 | 验收 |
|:---|:---|:---|
| P1 | `decision_eval_policy` 模块 + 常量单源 + `flat_judged` 写入 + fold 汇总 | 单测：命中/未命中/带宽边界/无收益/旧账本无字段；政策常量单源守卫 |
| P2 | 报告块与 `doctor` 呈现 + 政策脚注 | 双端同源用例；空态与样本不足文案 |
| P3 | 反馈闭环：结果进 `self_review` 输入与提示词（仅诊断信息，不调权重） | 指纹换键验证；再生成本可接受 |

P3 明确**只做呈现与自检提示**，不做「按命中率调提示词权重」——样本量不足时调权重会引入过拟合。

## 4. 测试方案

- **政策单源守卫**：断言 `decision_ledger.DIRECTION_THRESHOLD`、`MEANINGFUL_SAMPLE` 与政策模块常量相等（值引用，不断言字面量）；
- **判定矩阵**：`raw_return ∈ {None, −5%, −2.1%, −2%, −1%, 0, +1%, +2%, +2.1%, +5%}` × `direction ∈ {+1,0,−1}` 全覆盖表驱动；
- **旧账本兼容**：无 `flat_judged` 的历史行不被计入 `flat_total`；
- **报告同源**：同一份数据在 HTML/Excel 渲染出的不动作行逐字一致；
- **样本不足**：`flat_total < 20` 时不给百分比结论。

## 5. 风险与对策

| 风险 | 对策 |
|:---|:---|
| 不动作阈值（2%）主观 | 作为公开政策常量 + 文档口径声明；后续若要调，按「政策变更」记录 changelog，不静默改 |
| 「不操作」登记口径不一（LLM 表 vs 决策头） | 复用既有 `decision_llm_capture` 的 `no_direction` 判定，不新增解析路径 |
| 与 `plan-70` 转正判据冲突 | plan-70 明确只用方向性口径裁决；本项产出**并列**呈现，不参与转正判据 |
| 报告信息量继续膨胀 | 只在既有表格加一行，不新增区块；开关不开（无开关），但可按「无数据不出行」自隐 |

## 6. 不做

- 不改 `DIRECTION_THRESHOLD`（1.5%）与 `MEANINGFUL_SAMPLE`（20）；
- 不引入置信度加权命中率（缺校准数据）；
- 不引入「按动作词（buy/add/sell/reduce/avoid/hold/watch）」的第二套枚举——动作词映射在 LLM 解析层完成，账本仍是方向 + 载体。
