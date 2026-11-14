# 建议后验评估政策单源化 + 不动作类命中评估（plan-252 设计）

> 状态：**设计稿，已过 50 轮自评审（见 §8），未实施**。立项见 [`plan.md`](../managements/plan.md) 的 `plan-252`；
> 借鉴来源与取舍见 [`panwatch-borrowing-review.md`](panwatch-borrowing-review.md)。

## 1. 背景与缺口

本方已有完整链路：`core/decision_ledger.py`（登记/结算/折叠）→ `report/decision_basis_settlement.py`（按视界命中率与超额）
→ `report/decision_review_block.py`（复盘块）→ `scripts/eval-decision-quality.py`（离线评测）。三个缺口：

| # | 缺口 | 表现 |
| :--- | :--- | :--- |
| 1 | **不动作类建议从不被评估** | `classify_direction_outcome()` 对 `DIRECTION_FLAT` 直接返回 `(flat, None)`，`directional` 只统计 ±1 方向；模型输出里「持有/观望/不操作」占比不低（运行日志：`无方向 4 条（含「不操作」）`），事后无法回答「叫你别动，事后看对不对」 |
| 2 | **「什么算命中」散在多处** | 方向阈值、样本门槛、平盘归类、按视界聚合分别落在 4 个消费方，文档再写一遍；新增一类建议要逐个改 |
| 3 | **没有可对外声明的评估政策** | 报告与 CLI 只能各自解释算法，无法像公开政策常量那样被测试与文档直接引用 |

## 2. 借鉴点（PanWatch）

`EVALUATION_POLICY` 作为公开 dict 声明「什么算命中」；`classify_prediction_hit(action, return_pct) -> bool | None`
把**可判定性显式化**（None ≠ False）；不动作类用绝对收益阈值判命中；多视界 pivot 后汇总覆盖/命中/均值/待结算。

**不照搬**其动作词表（buy/sell/…）：本方账本以 `direction`(+1/0/−1) + `carrier`（来源载体）表达，动作词只存在于 LLM 表解析层。

## 3. 设计

### 3.1 新增单源模块 `core/decision_eval_policy.py`

只放**口径**（阈值/单位/政策文案），不放业务逻辑，也不放判定函数：

```python
#: 方向性命中阈值（分数口径；政策对外暴露 pct）
DIRECTION_HIT_THRESHOLD = 0.015
#: 不动作类（持有/观望/不操作）判对的容忍带（分数口径）
FLAT_HIT_TOLERANCE = 0.02
#: 有效样本门槛（与既有口径一致）
MEANINGFUL_SAMPLE = 20
#: 视界单位（本方结算即按交易日）
HORIZON_UNIT = "trading_days"

#: 对外声明（报告脚注 / doctor / 文档同源引用；此处按 pct 展示）
EVAL_POLICY: dict[str, object] = {
    "horizon_unit": HORIZON_UNIT,
    "direction_hit_threshold_pct": DIRECTION_HIT_THRESHOLD * 100,
    "flat_hit_tolerance_pct": FLAT_HIT_TOLERANCE * 100,
    "directional_rules": "方向性：>+阈值判看多命中、<-阈值判看空命中、带宽内记平盘不判定",
    "flat_rules": "不动作类：|区间收益| < 容忍带 ⇒ 命中；越带 ⇒ 未命中；无收益数据 ⇒ 不可判定",
    "units": "代码常量用分数（0.015）；对外文案用百分比（1.5%）",
}
```

**依赖方向（硬约束）**：本模块**零依赖**（不 import 账本、不 import 报告）；`core/decision_ledger.py` 从本模块导入
`DIRECTION_HIT_THRESHOLD` / `MEANINGFUL_SAMPLE` 并以**原名重新导出**（`DIRECTION_THRESHOLD = DIRECTION_HIT_THRESHOLD`、
`MEANINGFUL_SAMPLE = MEANINGFUL_SAMPLE`），保持既有导入面不变。**禁止反向依赖**（policy → ledger 会成环）。

### 3.2 判定入口：只扩展既有函数，不新增第二套判定

`classify_direction_outcome()` 是唯一判定入口（签名不变），仅对 `direction == DIRECTION_FLAT` 增加不动作判定：

| 输入 | 现在 | 改后 |
| :--- | :--- | :--- |
| `raw_return is None` | `(gap, None)` | `(gap, None)`（不变） |
| `direction == ±1`，`\|r\| < 0.015` | `(flat, None)` | `(flat, None)`（不变） |
| `direction == ±1`，越带 | `(hit/miss, bool)` | 不变 |
| `direction == 0`，`\|r\| < 0.02` | `(flat, None)` | `(flat, None)` + 不动作判对 |
| `direction == 0`，`\|r\| ≥ 0.02` | `(flat, None)` | `(flat, None)` + 不动作判偏 |

**不动作判定不新增 outcome 枚举**：`outcome` 列仍是 `flat`（历史口径与既有折叠不改），命中与否落到**独立字段**
`flat_hit: bool | None`（None = 无收益数据不可判）。这样：历史账本读侧零影响、`directional_total` 不被稀释、
「outcome」列表不需要迁移。

返回值改为三元组会破坏既有 8 处消费点，因此**保持二元返回**，`flat_hit` 由 `classify_flat_hit(raw_return, tolerance)` 单独提供，
由结算写入方（`append_settlement` 调用点）计算后落字段。

### 3.3 结算记录扩展（向后兼容）

```json
{"target_horizon": 5, "raw_return": 0.012, "outcome": "flat", "flat_hit": true, "settle_date": "…", "horizon_bars": 5}
```

- 仅 `direction == 0` 的结算写 `flat_hit`（±1 方向不写，避免噪声字段）；
- 历史记录无该字段 ⇒ 读侧 `None`（未判），**不回填、不改历史统计**；
- `backfill_settlement_horizons` 一类的写侧回填**不扩到本字段**（无原始收益可复原的不动作决策无法回算）。

### 3.4 折叠与汇总（只增不改）

- 顶层新增 `flat`：`{total, hit, hit_rate, sample_sufficient}`；`hit_rate` 在 `total < MEANINGFUL_SAMPLE` 时为 None，
  消费方统一按「命中/总数（样本不足）」呈现；
- `by_carrier` 每项新增 `flat_total` / `flat_hit`；
- **既有键语义不变**（`directional_total`、`accuracy`、`alpha_mean` 等），消费点逐个核对一遍：`decision_review_block`
  句文案、`doctor._check_review_ledger_overview()`、`decision_basis_settlement.build_performance()`。

### 3.5 呈现（不新增章节 / 页签 / 区块）

| 渠道 | 位置 | 内容 |
| :--- | :--- | :--- |
| HTML/Excel | 判断依据块「我的建议历史表现（按视界）」表格**下方一行** | `不动作建议：命中 x/y（样本不足）` 或 `不动作建议命中率 xx%（n=y）`；无样本显式 `—` |
| HTML/Excel | 历史决策复盘块 | 逐条状态多一个取值：`判对` / `判偏` / `未到期`（沿用既有状态列，不新增列） |
| CLI | `doctor` 账本概览 | 与方向性命中率**并列一行** |

口径约束（设计契约）：
- 数值行不引入新 CSS 类（复用既有表格/`text-muted`），不染状态色（涨跌域与状态域不混用）；
- 文案不是空态句，走既有数值行惯例；空/无样本用哨兵 `—`（Data States 豁免表已含哨兵值）；
- Excel 侧只加一行文本（跨列合一行，复用块内既有行书写方式，不改列数）。

### 3.6 契约与文档触点（P1 必做，缺一即视为未完成）

| 触点 | 动作 |
| :--- | :--- |
| 附录 H（pipeline_data 契约） | `decision_basis_data` 行补 `settlement.flat` 子结构与 `flat_hit` 字段 |
| `report/pipeline_data_builder.py` | schema 校验不动（顶层键不变），但注释列明子结构新增字段 |
| `requirements.md` | R-OUT-17 补「不动作类命中」口径与展示位；必要时新增一条需求 |
| `technical.md` | 评估政策模块登记（功能语义命名/依赖方向）+ 口径单位说明 |
| `developer-guide.md` | 若涉及慢段/性能无变化则不改 |
| changelog / review-findings | 实施时按纪律登记 |

### 3.7 分期

| 阶段 | 内容 | 验收 |
| :--- | :--- | :--- |
| P1 | policy 模块（阈值单源 + 政策声明）+ `flat_hit` 写入 + fold 汇总 + 契约文档 | 判定矩阵；单源守卫；旧账本兼容；附录 H 与需求同步 |
| P2 | 报告一行 + 复盘块取值 + `doctor` 一行 | 双端同源用例；样本不足文案；无样本 `—` |
| P3 | 结果进 `self_review` 输入（仅提示，不改权重） | 指纹换键验证；再生成本可接受 |

P3 明确**只呈现不调权**：样本不足时按命中率调提示词权重会引入过拟合。

## 4. 测试方案

- **判定矩阵**（表驱动，`classify_direction_outcome` + `classify_flat_hit` 两函数各一组）：
  `raw_return ∈ {None, −5%, −2.1%, −2%, −1.5%, −1%, 0, +1%, +1.5%, +2%, +2.1%, +5%}` × `direction ∈ {+1, 0, −1}`；
- **政策单源守卫**：断言 `decision_ledger.DIRECTION_THRESHOLD == decision_eval_policy.DIRECTION_HIT_THRESHOLD`（值引用，不断言字面量）；
- **旧账本兼容**：无 `flat_hit` 的历史行不计入 `flat.total`；
- **折叠结构**：`directional_total` / `accuracy` 在加入不动作样本后**不发生变化**（同输入同值）；
- **双端同源**：同一数据在 HTML/Excel 渲染出的不动作行逐字一致；
- **样本不足**：`flat.total < 20` 时不给百分比。

## 5. 风险与对策

| 风险 | 对策 |
| :--- | :--- |
| 不动作阈值（2%）主观 | 公开政策常量 + 文档口径；调整走 changelog「政策变更」，不静默改 |
| 「不操作」登记口径不一 | 复用 `decision_llm_capture` 的 `no_direction` 判定，不新增解析路径 |
| 与 `plan-70` 转正判据冲突 | plan-70 只用方向性口径裁决；本项产出**并列**呈现，不参与裁决 |
| 报告信息量膨胀 | 只加一行/一个取值，不新增区块；无样本不出行 |
| 阈值单位混淆 | 代码分数 / 文案百分比，政策 dict 显式声明 `units` |

## 6. 不做

- 不改方向阈值（1.5%）与样本门槛（20）；
- 不新增第二套判定函数（`classify_flat_outcome` 这类双入口一律不要）；
- 不引入置信度加权命中率、不做按动作词（buy/add/…）的第二套枚举；
- 不新增章节/页签/区块，不改 Excel 列数。

## 7. 依赖顺序

本项（252）先于 `plan-253`：253 的「判决（verdict）」验收要用到本项稳定的评估口径与报告呈现位。

## 8. 评审记录（50 轮自评审：架构约束 / 设计契约 / 质量）

> 每轮一个观察面；「发现」列写实际查到的问题与处置（已在本稿整改），无发现则记录核对结论。

| 轮次 | 观察面 | 发现与处置 |
| :--- | :--- | :--- |
| 1 | 分层依赖（架构约束：分析层/核心层不得反向依赖） | `policy` 若 import 账本会与「账本 import 政策」成环 → 改为 policy 零依赖、账本单向导入（§3.1 已锁定） |
| 2 | 既有导入面 | 阈值/门槛改名会破坏既有 8 处导入 → 账本保留原名重新导出（§3.1） |
| 3 | 判定入口数量（单一事实位） | 原稿同时提出 `classify_flat_outcome` 与改 `classify_direction_outcome` → 双入口，删后者，只留一个入口 + 一个纯函数（§3.2） |
| 4 | 返回签名兼容 | 改三元组会破 8 处消费点 → 保持二元返回，`flat_hit` 由独立函数提供（§3.2） |
| 5 | outcome 枚举兼容 | 「平盘带宽」与「不动作」若共用 `flat` 会歧义 → 明确 outcome 不变、命中落 `flat_hit`（§3.2） |
| 6 | 字段语义自明 | `flat_judged` 只表达「判过没」不含结论 → 改 `flat_hit: bool \| None`（§3.3） |
| 7 | 旧账本兼容 | 无新字段的行不能算进 `flat.total` → 读侧 None 即跳过（§3.3/§4） |
| 8 | 回填边界 | 回填函数不得扩到 `flat_hit`（无收益不可复原）→ §3.3 写明 |
| 9 | 折叠契约（pipeline_data 契约） | 新子结构必须进附录 H → 补契约触点表（§3.6） |
| 10 | pipeline schema | 顶层键不变，仅子结构增字段 → 校验表不动、注释列明（§3.6） |
| 11 | 需求条目（文档与实现一致） | R-OUT-17 未含不动作口径 → 列入 P1 触点（§3.6） |
| 12 | 功能语义命名 | 新模块需进技术设计语义表 → 列入 P1 触点（§3.6） |
| 13 | 单位口径 | 常量分数 / 文案百分比混用 → 政策 dict 增加 `units`（§3.1） |
| 14 | 阈值来源唯一 | 两处阈值不可各写一份 → 账本引用政策常量（§3.1） |
| 15 | 与既有口径一致性 | 不得改 1.5%/20 → §6 明确不改 |
| 16 | 设计契约：不新增颜色/类 | 新行复用既有表格样式与 `text-muted`，不染状态色（§3.5） |
| 17 | 空态/哨兵口径 | 无样本用 `—`（豁免表已含哨兵），不新造空态句（§3.5） |
| 18 | 双端同源 | HTML/Excel 文案同源一处产出（§3.5） |
| 19 | Excel 结构影响 | 只加一行文本、不改列数/合并（§3.5） |
| 20 | 章节/页签不可硬编码 | 不新增章节/页签（§3.5/§6） |
| 21 | 报告性能 | 纯账本折叠、无取数，不新增 IO（§3.5 末尾） |
| 22 | doctor 消费点 | 概览函数存在（`_check_review_ledger_overview`），并列一行可落（§3.4） |
| 23 | 复盘块消费点 | 状态列已存在，加取值不等价于加列（§3.5） |
| 24 | 结算字段消费点 | `accuracy_label` 等既有字段不变，避免破坏 `build_performance`（§3.4） |
| 25 | 视界口径 | 统一 `trading_days`（§3.1 `HORIZON_UNIT`） |
| 26 | 多视界一致性 | 5/20/60 同一判定函数、同一容忍带（§3.2 矩阵覆盖） |
| 27 | 样本门槛边界 | `total == 20` 视为达标（`>=` 语义写进 §4） |
| 28 | 边界收益值 | 恰好等于阈值（0.015/0.02）时的取值方向需固定 → 测试矩阵含边界值（§4） |
| 29 | 缺失数据 | `raw_return is None` 一律不可判（gap），不猜（§3.2） |
| 30 | 异常处理 | 折叠纯计算无 IO，异常面为零；写侧仍走原子追加（既有原语） |
| 31 | 测试可执行性 | 矩阵按整改后签名写；断言值引用常量（§4） |
| 32 | 测试有效性（无恒真） | 单源守卫断言「相等」而非「存在」；结构断言不写死总数（§4） |
| 33 | 测试隔离 | 纯函数 + 临时账本路径，不碰 `data/state`（§4） |
| 34 | 契约文档同步 | 附录 H / 需求 / technical 三处列进 P1 触点（§3.6） |
| 35 | 与 plan-70 边界 | 不参与转正裁决（§5） |
| 36 | 与 plan-253 边界 | 253 的 verdict 用本项口径做验收（§7） |
| 37 | 回滚通道 | 无开关（只增字段/行），历史数据可读即回滚安全（§3.3） |
| 38 | 发布影响 | 无版本头/归档影响；changelog 实施时登记（§3.6） |
| 39 | 性能埋点 | 折叠耗时随账本行数线性，纳入既有 perf 观察，不加新埋点 |
| 40 | 隐私 | 只处理数值与载体，不含名称/代码 → 匿名化模式无影响 |
| 41 | 术语统一 | 「不动作类」= 持有/观望/不操作；与 `flat`（平盘带宽）区分（§3.2 注） |
| 42 | 文案可读性 | 括号样本不足沿用既有「命中 x/y（样本不足）」形态（§3.5） |
| 43 | 数字格式 | 百分比两位小数、`—` 为无值，与判断依据块其余数值一致 |
| 44 | 配置/开关 | 不新增开关（纯口径与呈现），故不涉及功能开关注册 |
| 45 | 日志口径 | 不新增日志；折叠异常不吞（无 IO 无异常） |
| 46 | 依赖顺序 | P1→P2→P3 严格串行，P2 不得先于契约同步（§3.7） |
| 47 | 验收可判性 | 每阶段验收列具体断言（§3.7） |
| 48 | 范围收敛 | 删去「按载体加权」「按置信度加权」等扩项（§6） |
| 49 | 文档一致性复检 | 本稿 §3.1~§3.6 与 plan.md 条目逐句对齐 |
| 50 | 终检 | 全文通读：无「新增章节」「新增判定入口」「改动既有阈值」三类违禁；契约触点齐备 |

## 9. 事实位索引

- 阈值/门槛唯一事实位：`core/decision_eval_policy.py`
- 判定入口：`core/decision_ledger.classify_direction_outcome`（唯一）
- 折叠：`core/decision_ledger.fold_ledger`（`flat` / `by_carrier.flat_*`）
- 呈现：`report/decision_basis_settlement.py`（历史表现表一行）、`report/decision_review_block.py`（状态取值）、`core/doctor.py`（概览一行）
- 契约：`technical.md` 附录 H（`decision_basis_data.settlement.flat`）、`requirements.md` R-OUT-17
