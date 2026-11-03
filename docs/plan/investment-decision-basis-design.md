# 迭代设计：决策依据章与 LLM 章职责切分

> 关联：`plan.md` → `plan-243`（实施任务）· 已归档讨论稿 [`investment-decision-quality.md`](../archive/v0.16.x/investment-decision-quality/investment-decision-quality.md) 的「章节归属结论」
> 状态：**迭代实施中**——当前待办 R3 风险预算块（轮次与产出见 §4）；实施前置 V1/V3 已满足（回测结论见归档讨论稿 `investment-decision-quality.md` §8.1：V1/V2 样本不足仅记录、V3 两口径 5 日视界均判「叙述性维度」；三态契约见 §2.1，V1 复跑触发见 R0）
> 红线：本稿只陈述契约与轮次，不在此处改代码、改配置、改提示语；落地动作均在对应轮次内完成。

## 1. 定位

把报告的「决策相关内容」拆成两章，职责不重叠：

| 章 | 键 | 性质 | 可控性来源 |
|:---|:---|:---|:---|
| 「决策依据」 | `decision_basis` | 纯规则 / 确定性，**零 LLM 生成** | 可回测、可追责、可单测 |
| 「LLM 分析」 | 既有 `llm` 章 | 解读 / 论辩 / 反方证据 | 只能靠提示语与自检约束 |

> 边界：讨论稿负责归因与选型，本稿负责契约与落地，两稿互引不重复。
> 术语：块名固定「判断依据」（形态 A 落在行动章内）；若升级形态 B，独立章名用「决策依据」——两者是同一数据契约 `decision_basis_data` 的两种呈现位，不并存。

**为什么必须拆**（讨论稿「章节归属结论」）：讨论稿 7 条结构性事实中，属机制与数据层的 5 条（信号零区分度、估值口径丢失、
纪律规则结构偏空、结算频率与执行回执缺失〔合 2 条〕、无硬性风险约束）没有一条能靠改措辞解决；
另 2 条（提示语强制方向且无置信度/失效条件）须在 LLM 章出口契约就地改。
两章合并会让读者无法区分「模型推断」与「规则硬约束」。

## 2. 输出契约

### 2.1 决策依据（`decision_basis_data`）

> 示例为**节选**（完整字段以模块 docstring 与附录 H 为准）：`risk_budget` / `discipline` / `settlement`
> 均为对象（结构见 R3 / R4 / R5 行的「数据字段」）；`enabled=false`（开关关）时装配返回 `{"enabled": false}`、双端整块不渲染。
> 数值单位取**百分数数值**（与 `discipline.*_pct` 同口径：20.0 / −15.0 / −10.0），不使用小数比例。

```json
{
  "enabled": true,
  "available": true,
  "reason": "",
  "title": "判断依据",
  "summary": "判断依据：有效信号 0/5 · 信号可信度：暂不可判",
  "signals": [
    {"name": "估值分位", "direction": "bearish", "direction_label": "看空",
     "basis": "price_proxy", "basis_label": "价格代理", "n_obs": 365,
     "n_backtest": 117, "ic": 0.0399, "monotonic": false,
     "discrimination": "failed", "discrimination_label": "回测未通过（仅参考）",
     "in_axis": false,
     "note": "价格分位代理；5 日视界回测未通过（叙述性维度），不进方向轴"}
  ],
  "risk_budget": {},
  "discipline": {},
  "confidence": {"level": "unknown", "level_label": "暂不可判",
                 "level_class": "data-status-info", "reason": "no_valid_signal",
                 "detail": "有效信号 0/5（回测未通过 1、样本不足 1、未回测 3）"},
  "settlement": {"available": true, "horizons": [5, 20, 60], "batches": [],
                 "note": "暂无结算样本"}
}
```

**硬约束**：
- 任何字段的数值必须来自确定性计算（信号账本 / 持仓 / 配置），**不得由 LLM 生成或改写**。
- **字段键恒存在**：`basis`、`n_obs`、`ic`/`monotonic` 四组键必出现，值可 `null`（账本未提供即显式 `null`，不得省略键）；缺任一非 `null` 值即视为该信号不可进方向轴。
- **可用性与空态分开表达**：`available` 描述块能否渲染（`false` 仅在装配异常时出现，`reason` 给失败原因）；「信号清单为空」是**正常空态**（`available=true` + `signals=[]` + `confidence.reason=no_signal`），不得用 `available=false` 表达。
- `confidence` 由规则仲裁给出，**不是模型自评**，且**只描述「信号可信度」，不描述「建议胜率」**（后者属结算统计，不进该字段，避免用一个数混合两种语义）。**四枚举**：`high` / `medium` / `low` / `unknown`（本稿定义的四档，对应讨论稿「置信度分级」示意；页面展示名「信号可信度」，展示映射 高/中/低/暂不可判；`level_class` 由 level 映射到 `data-status-*` 语义类，不落色值）。
  - **有效信号**：`discrimination` 为「回测通过」的信号；「未回测」「样本不足」「回测未通过」均只在清单展示、**不计入有效数**（按现有回测结论，有效信号为 0/5，见归档讨论稿 `investment-decision-quality.md` §8.1）。
  - **仲裁规则（按序短路）**：清单为空 → `unknown`（`reason=no_signal`）；有效信号 = 0 → `unknown`（`reason=no_valid_signal`，空态不得显示「可信度高」）；全部为口径代理 → `low`（`reason=all_proxy`）；方向分裂 → `low`（`reason=split_direction`）；有效信号 <3 → `low`（`reason=insufficient_signals`）；≥3 且方向一致 → `medium`（`reason=direction_aligned`）。**首版不产出 `high`**（留给后续「回测通过 ≥5 且口径全真实」的演进，防高置信幻觉）。不做加权投票（权重无依据）。
- `basis` 取值域：`valuation_real` / `price_proxy` / `rule_based` / `stat_model` / `unknown`；`unknown` 不得进方向轴。
- `discrimination` 由 `ic`（数值）+ `monotonic`（布尔）表达，**三态如实标注，不得用主观先验填充**：①「未回测」——`ic`/`monotonic` 为 `null`，`note` 标「未回测」；②「样本不足」——仍为 `null`，`note` 标「样本不足 n=X（<100 不裁决）」（因子目录信号即此态，V2 回测已跑、单因子最大 n=19）；③「已回测」——填实测值并二分：通过（进方向轴）/ 未通过（`note` 标「回测未通过（叙述性维度）」，不进方向轴——估值分位两口径即此态，见归档讨论稿 `investment-decision-quality.md` §8.1）。回测结论登记机制见 R2。
- **渲染层零计算**：`direction_label` / `basis_label` / `basis_sample_label` / `discrimination_label` / `level_label` / `level_class` 等展示字段由装配层算好，模板只做插值。
- **禁止读取任何 LLM 产出文本**（只读账本字段与确定性计算），保证与 LLM 章节开关零联动。

### 2.2 LLM 章（解读层契约）

- **移除**「必须给出方向性判断」类要求（原句：两个情景必须给出方向性判断和具体品种建议，避免「视情况而定」这类模棱两可的表述；原文位置 `llm/prompts_action.py` 情景段，行号随改版漂移，以句子为锚）；
- **新增**三项强制项：反方证据、失效条件、下一个观察指标；
- 「必须引用具体品种」开口子：允许「不对具体品种动手 + 说明理由」；
- 新增可信度引用要求，且**只能引用判断依据块的 `confidence`（展示名「信号可信度」）**，不得自行升级；该字段描述「信号可信度」而非「建议胜率」。

### 2.3 呈现形态：行动章内块（推荐）与独立章节

「决策依据」有两种落地位置，**数据契约（`decision_basis_data`）完全相同**，只是渲染位置不同。

#### 形态 A：放入「行动建议」章头部（推荐先做）

```
行动建议（章，key=action，序号 7）
└─ ▸ 判断依据  [默认折叠]
     summary：有效信号 0/5 · 集中度超限（纳指系 42%）· 信号可信度：暂不可判
     内容：信号清单（口径/样本/区分度）｜风险预算 vs 上限｜纪律触发与距阈值｜可信度理由｜结算（5/20/60 日）
```

| 项 | 评价 |
|:---|:---|
| 改动面 | **小**：复用行动章既有「章内块」模式（历史决策复盘 / 景气度诊断 / 市场情绪三块即按此挂，传 `None` 即不渲染）；HTML 用既有 `details.section-fold`，Excel 用 `write_data_row` 顺序写入 |
| 注册表 | **零改动**（不新增 key、不改 `report_section_order`、序号不顺延） |
| 开关 | 复用 `enable_action`（章级）+ 配置项 `decision_basis.enabled`（默认 true，控制数据是否注入） |
| 优点 | 判断链连贯（先看依据再看动作）；与「行动建议」同生共死，语义自洽 |
| 代价 | ① 章节名不变，可发现性弱（由固定块名「判断依据」与副行文案缓解）② 章首变重（默认折叠 + 一句话 summary）③ 关掉行动章即失去依据（已知取舍，独立读取需求出现时升级形态 B） |

#### 形态 B：独立章节（`decision_basis`，序号插在 action 之后）

| 项 | 评价 |
|:---|:---|
| 改动面 | **大**：注册表新增 key + 序号顺延 + `report_section_order` 同步 + 独立开关 + 双端 partial/页签 |
| 优点 | 可独立开关与排序；可被单独引用；不受 `enable_action` 影响 |
| 代价 | 与行动建议内容可能重复，需文案互引；注册/顺序/配置三处同步易漂（已有防漂移测试兜底） |

#### 选型结论

**先做形态 A**，理由是成本低、可逆、判断链连贯；若后续观测到「用户频繁单独读依据」或需要独立排序，再升级为形态 B——
**数据契约与渲染函数可原样复用**，升级只涉及注册表、模板位置与 `html_writer` 的章级参数（装配层不动）。

## 3. 与既有架构的衔接

| 关注点 | 做法 |
|:---|:---|
| 章节注册 | **形态 A 不触碰本注册表**（判断依据是块不是章，经 `core/section_block_registry.py` 登记区块，行动章区块清单现为 8 项，与 `technical.md` §4.22 章节-区块矩阵同一真值）；形态 B 立项时在 `core/report_section_registry.py` 增 `decision_basis`（`type` 取值届时依注册表现有三态语义定），默认序号由序号可配置机制给出、不硬编码，并同步 `_REPORT_SECTION_DEFAULT` |
| 双端渲染 | HTML partial + Excel 页签各一，数据同源（`pipeline_data["decision_basis_data"]`） |
| 功能开关 | `decision_basis`（默认**开**：纯事实不增加风险），登记在 `src/python/config/_feature_registry.py`（开关唯一事实源）；R8/R9 的新增开关属**行为变更类**，默认**关**（`discipline.vol_normalized`、`portfolio_constraints`），默认值分别登记该文件与 `src/python/config/_config_defaults.py` |
| 与「行动建议」章的关系 | 形态 A 下作为其**章内块**（不合并语义、只共用容器）；形态 B 下为独立章 |
| LLM 开关联动 | **零联动**：本块只读 `signal_ledger` / 持仓 / 配置 / `decision_ledger`，关掉任一 LLM 模块或整章 LLM 均不影响本块；LLM 章写「请引用决策依据」时，若该块缺失则**该段提示词不注入**（不阻断、不出占位噪音） |
| 章节容器开关联动 | 形态 A 下本块随行动章容器开关 `enable_action`（`src/python/config/_config_defaults.py`，默认开）显隐——`enable_action=false` 时整章（含本块）不呈现；`decision_basis.enabled` 只控制块自身，两开关独立取值 |
| 降级 | 任一数据块缺失 → 该块「数据不足（缺 X）」占位，不隐藏整块容器（整块不可用时 `available=false` + `reason`）；信号可信度由有效信号数与口径质量决定，**不因 LLM 关闭而升级** |
| 渠道范围 | 首版仅 HTML + Excel（basic/both/full 均呈现）；CLI/TUI 不加 |
| 性能与缓存 | 源数据均为本地账本/持仓，毫秒级；**不新增缓存类型**、不做阶段计时 |
| 呈现细节 | 首版不配图（超限用 DESIGN.md 既有语义色；若后续加图须遵守图下说明强制约束）；HTML 加 `id="decision-basis"` 锚点；Excel 行数 ≤12 行、明细引用既有页签；不新增 CSS——全部复用既有折叠组/`data-status`/`tabular-nums`/`empty-note` 类，故暗色无需额外覆盖；打印态随正文折叠块展开（与 `technical.md`「正文大块默认折叠」同一口径） |
| 与既有块分工 | 纪律块=动作与阈值，本块=上下文与是否应执行；再平衡块=超线动作，本块=上限 vs 现状；历史决策复盘块=归因分析，本块=事实数字 |
| 一致性 | 不强制信号与动作一致——差异本身即信息 |
| 与可用性矩阵/降级事件 | 不进数据源可用性矩阵；信号层故障沿用既有降级记录，不新增类别 |
| 算法层归属（R8/R9） | R8 改 `analysis/trade_discipline.py`（阈值口径与触发条件）、R9 新建 `analysis/portfolio_constraints.py`（单品种/行业/相关性上限判定）；两者结论以**只读**形式被 `report/decision_basis.py` 消费，不反向依赖报告层；不走 `report/_experimental_seams.py`（非管线实验功能，由配置/开关门控） |
| 文件归属 | 数据装配新建 `report/decision_basis.py`；渲染并入既有行动章双端载体（形态 A）：HTML `static/tmpl/partials/action_section.html` + Excel `report/action_sheet.py`；**数据经独立 render 参数 `decision_basis_data` 传递**（`report/html_writer.py` 显式参数、`report/excel_generator.py` 自 `pipeline_data` 取值），不塞进 `action_data`——两者生命周期与开关不同源 |

## 4. 多轮迭代计划（每轮独立可验收，任一失败即停）

> 总原则：**每轮都可独立发布**（未完成的后续轮不得留半成品在主干）；每轮结束跑
> `scripts/test-runner.py --mode verify`（P1 口径）+ 十守护（提交时由 pre-commit 钩子按暂存域执行，不手动重复跑），
> 跨轮累计不得让守护变红；每轮收尾按 `developer-guide.md`「计划收尾：文档触点清单」逐项枚举文档触点。
> LLM 章改造分两刀：**R6 语义增量**（只加不改）与 **R7 冲突措辞替换 + 解析兜底**，理由见 R6 表头。
> R0 只做前置数据能力，不含报告呈现；R1 起逐块上线。
> 前置未满足的轮次（R8 的 V5 回测门槛、R9 的约束强度确认与相关性样本期）**停留该轮**、不阻塞其他轮次排期；
> 每轮可独立回滚（各自开关或配置键），R6/R7 必须同一发布版本内落地（便于同输入对照），但两刀各自可单独回退。

### R0. 前置：结算视界扩展（不动报告，只补数据能力）

| 项 | 内容 |
|:---|:---|
| 目标 | 让「建议准不准」可判定——结算支持 5/20/60 多视界，并与报告频率解耦（计划任务结算） |
| 改动面 | `core/decision_ledger.py`（结算事件带 `target_horizon` 字段，判重键为 `(decision_id, target_horizon)`；缺该字段的事件按 5 日归属且不改写）、`report/decision_settlement.py`（按视界分别结算）、`fold_ledger` 的 `settlements`/`by_horizon` 统计与 doctor 账本概览适配多条结算、CLI 子命令 `settle-decisions`（结算不依赖报告生成）；**不碰章节与模板** |
| 验收 | ① 同一决策可产出 3 条结算（5/20/60），`target_horizon` 各自正确；② **结算事件按 `(decision_id, target_horizon)` 唯一**——重复结算幂等、不产生重复行（判重只看 `(decision_id, target_horizon)`；若只按「该决策是否已有 settlement」判重，5 日结算会让 20/60 日无法落账）；③ 5 日与 20 日之间不得互相「认领」已结算状态；④ 账本向后兼容（旧记录仍可按 5 日读，缺失的长视界显示「未到期」）；⑤ 保留期：长视界样本（60 日 ≈ 3 个月）在 730 天保留期内不受影响，但**滑动窗口会挤掉早期批次**——须在摘要里标注样本窗口；⑥ 结算不依赖报告生成（脚本可独立触发）；⑦ 单测覆盖多视界幂等与旧记录兼容；⑧ `perf_history` 无新增阶段 |
| 风险与回滚 | 低：只增字段与结算路径；回滚=停止新视界写入，旧字段不受影响（旧读取方遇多条结算事件按 5 日取首条，不误读长视界） |

> **V1 复跑触发（回测侧）**：`scripts/eval-decision-quality.py horizon` 已固化判据（样本门槛 100、|IC| 0.05、三分位单调；改判据须全量重跑）。20 日视界成熟样本 ≥100 时复跑，结论按 R2 口径写回 `report/decision_basis.py` 的 `BACKTEST_CONCLUSIONS` 常量并在 changelog 记录；账本多视界结算（R0）与脚本侧固定视界为两套终点口径——基线同源（决策登记 `baseline_close`），账本取结算时点最新收盘、脚本取第 h 根 bar 收盘，以对拍一致为数据切换前提。既有读数见归档讨论稿 `investment-decision-quality.md` §8.1（5 日 n=61 命中率 0.5385、20 日 n=2、60 日 n=0，均未达裁决门槛）。

### R1. 骨架：行动章内块 + 契约空态（不含真实数据）

| 项 | 内容 |
|:---|:---|
| 目标 | 跑通「形态 A」容器与双端空态，**不接真实数据** |
| 改动面 | 新建 `report/decision_basis.py`（返回 `available=false` 的规范空契约）；`section_block_registry` 的 `action` 块追加「判断依据」；`action_section.html` 折叠块；`action_sheet.py` 顶部子块（顶部子块注释与 `technical.md` §4.22 矩阵同源计数，当前 8 项） |
| 架构约束 | **章节序号与显示名不硬编码**（块不新增章节，序号不顺延）、**渲染数据走模板 context**、**pipeline_data Schema 契约**（`decision_basis_data` 已登记附录 H，字段变更须同步该表）；不涉 LLM 模块与链路路由 |
| 设计契约 | `DESIGN.md` Data States：空态用 `empty-note` 与「数据不可用：<原因>」口径；无裸色值、字号/间距取档（W3 已 E 级） |
| 验收 | ① HTML 出现「判断依据」折叠块且默认折叠（复用既有折叠组组件，移动档触控 44×44），Excel 在行动页签顶部出现同名子块（Excel 无折叠概念，以分节标题呈现）；② **双端同源**：同一份 `decision_basis_data` 渲染出的区块标题与 summary 文案一致（契约用例对比两端输出，防止一处写死文案）；③ 空态文案与 Data States 口径一致（契约测试）；④ `check-doc-drift` 章节-区块矩阵三向对账通过（注册表↔文档↔实现）；⑤ `check-style-guardrails` E 级 0；⑥ 行为零变化（未接数据时其余区块输出逐字节不变） |
| 风险与回滚 | 极低：`decision_basis.enabled=false` 即完全隐藏 |

### R2. 首版数据：信号可信度 + 信号清单（只读确定性来源）

| 项 | 内容 |
|:---|:---|
| 目标 | 让读者看到「凭什么」与「可信吗」 |
| 改动面 | `report/decision_basis.py` 接 `signal_ledger`（`basis` 判定规则：`detail.pe`/`pb` 均为 null ⇒ `price_proxy`，与账本事实一致，见归档讨论稿 `investment-decision-quality.md` §8.1）；`confidence` 仲裁（四枚举，规则见 §2.1）；HTML/Excel 渲染两小节；开关登记 `src/python/config/_feature_registry.py`（开关唯一事实源，`check-semantic-index` 强制）+ `docs/manuals/how-to-config-reference.md`；`pipeline_data` 键入 `technical.md` 附录 H（已登记 `decision_basis_data`） |
| 架构约束 | **代码类型判定中心化**（行业/品种判定走 `core/code_utils.py`）、**账本读取走既有加载函数**（追加式 JSONL，不新增缓存类型、不直读文件）、**日志统一走 invest logger**、**渲染数据走模板 context**、**pipeline_data Schema 契约**、**时间距离按交易日计** |
| 设计契约 | 信号可信度用 `data-status` 组件（ok/warn/info 语义色，不用涨跌域色）；数值列 `tabular-nums` 右对齐；无效信号标「仅参考」用中性态，不染状态色 |
| 验收 | ① 信号字段 `basis`/`n_obs`/`ic`/`monotonic` 齐全，缺任一则该信号**不进方向轴**（负向用例）；② 「未回测」「样本不足」各显示对应标注而非先验值（契约测试）；③ 可信度四枚举（含 `reason`）各有单测；④ **零 LLM 依赖**：装配函数签名不含 LLM 参数，且 `enable_llm=True/False` 输出逐字节一致（注：生成层在 `enable_llm=False` 时走 both 路径，该块不参与任何 LLM 门控判断）；⑤ 三渠道：HTML/Excel 呈现，CLI/TUI 不出现（断言）；⑥ **回测结论接入**：回测结论以 `report/decision_basis.py` 模块常量登记（含来源脚本、回测日期、归档讨论稿 `investment-decision-quality.md` §8.1 指针），不新增配置键、不写运行时账本、不硬编码散落各处——估值分位按「已回测未通过」态渲染（`n_backtest=117`、`ic≈0.04`、`monotonic=false`，两口径同判无区分度故**不在管线内计算真实 PE/PB 口径**，口径透明由 `basis=price_proxy` 表达）、因子目录信号按「样本不足」态（`null` + note），复跑回测出新结论后随代码常量更新（changelog 记录） |
| 风险与回滚 | 中：信号口径若标注错误会误导 → 未回测一律「未回测」，宁可空着；回测结论与账本事实不一致时以账本为准（`basis` 由 `detail.pe/pb` 判定，不看常量） |

### R3. 风险预算块（上限 vs 现状）

| 项 | 内容 |
|:---|:---|
| 目标 | 让「超没超限」一眼可见 |
| 改动面 | `decision_basis.py` 读编排层已装配持仓 + 约束配置：单品种上限取 `rebalance.threshold`（经 `resolve_rebalance_config` 应用 profile 预设，默认 15%）、回撤上限取 `discipline.drawdown_pct`（经 `resolve_discipline_config`，默认 −10%）、行业上限**无配置键**（显示「未配置上限」，不臆造键）；单品种现状取明细行最大市值占比，回撤现状按历史峰值算（市值创新高时归零，不出现负回撤）；basic 路径由 `excel_generator` 就地同源构建（不经编排层），full/both 在峰值就绪后重装配一次 |
| 数据字段（R9） | `constraints = {enabled, available, reason, items[{item, kind, limit_pct, current_pct, breached, limit_label, current_label, status_label, status_class, note}], breached_count, breached_codes}`；开关关闭时该键**不出现**（输出与未接线逐字节一致） |
| 拦截强度（R9） | **只标注不阻断**：超限只进判断依据块「集中度约束」小节与账本 `constrained=true`，不改动作清单、不改 LLM 提示词；阈值需显式配置，缺省未配置 |
| 数据字段 | `risk_budget = {available, reason, items[], breached_count}`；`items` 三行 `{item, max_pct, current_pct, breached, max_label, current_label, note, status_label, status_class}`——`max_label`/`current_label`/`status_*` 均由装配层算好（渲染层零计算），缺失项显式「未配置上限」/「未评估」而非 0 |
| 架构约束 | **渲染数据走模板 context** |
| 设计契约 | 超限用既有 warning/danger 语义色，**不新增色值**；与「再平衡信号」块不重复动作 |
| 验收 | ① 三项上限/现状/是否超限字段齐全，**单位为百分数数值**（20.0 / −10.0，与 `discipline.*_pct` 同口径，禁止小数比例混用）；② 超限着色只用语义角色（设计护栏 E 级 0）；③ 与再平衡块无重复动作（文案互引断言）；④ 缺配置时显示「未配置上限」而非 0 |
| 风险与回滚 | 中：错误标注超限会造成误判 → 配置缺失一律「未配置」不臆造；持仓与分类复用 `prepare_report_data` 已装配数据（`market_data` / 既有分类函数），不重复读盘 |

### R4. 纪律明细块（上下文与是否应执行）

| 项 | 内容 |
|:---|:---|
| 目标 | 补「为什么这条纪律此刻该/不该执行」 |
| 改动面 | `decision_basis.py` 读纪律信号（来源 `analysis/trade_discipline.py`，规则键 `discipline.stop_loss_pct`/`take_profit_pct`/`drawdown_pct`，默认值 `config/_config_defaults.py` 单源）；渲染距阈值与 regime 说明 |
| 架构约束 | **pipeline_data Schema 契约**、**渲染数据走模板 context**、**日志统一走 invest logger**；不改 `trade_discipline` 的触发逻辑（只读） |
| 设计契约 | 距阈值数值列右对齐 `tabular-nums`，单位与 `discipline.*_pct` 同口径（百分数数值）；说明文案走 Data States 豁免表（字段内拼接缀） |
| 验收 | ① 每条约纪律含规则名/当前值/距阈值/说明；② **不动触发逻辑**（触发条数与基线一致）；③ 与既有纪律块分工清晰（动作 vs 上下文） |
| 风险与回滚 | 低：只读展示 |

### R5. 结算摘要块（最近 5 批次 × 多视界）

> 依赖：需要 R0 的多视界数据；若 R0 尚未发布，只显示 5 日单视界并在块内标注「多视界未启用」。

| 项 | 内容 |
|:---|:---|
| 目标 | 让用户看到「最近建议的实际结果」（批次 = 交易日；与「历史决策复盘」块同一聚合口径与数据源 `report/decision_review_block.py`，不另算一套） |
| 改动面 | `decision_basis.py` 读 R0 产出的多视界结算（`fold_ledger().decisions[].settlements`，与「历史决策复盘」块同源）；批次 = 结算交易日，取最近 5 批 |
| 数据字段 | `settlement = {available, reason, horizons[5,20,60], batches[{date, n, cells[{horizon, n, state, mean_return_pct, mean_excess_pct, value_label, excess_label, color_var}]}], note}`；`state=pending` 表示该批次该视界未到期（`value_label="未到期"`，均值恒 `null`，不按 0 呈现）；`color_var` 取涨跌域变量（`--profit` / `--loss`，零值空串），与状态域互斥；超额 = 原始收益 − 同期基准，基准缺失只计收益均值 |
| 架构约束 | 不涉模块注册与链路路由；**pipeline_data Schema 契约**、**渲染数据走模板 context**、**时间距离按交易日计**（结算批次按交易日聚合） |
| 设计契约 | 结果正负用涨跌域色（红涨绿跌），不用状态域色；数值右对齐 |
| 验收 | ① 展示 5/20/60 日三列，到期前显示「未到期」而非 0；② 批次上限 5，超出的看「历史决策复盘」块（该块展示 pending/settled 各 ≤5 条，`report/decision_review_block.py`）；③ 无数据时「暂无结算样本」；④ 正负着色域正确（涨跌域 vs 状态域不混用，护栏 4） |
| 风险与回滚 | 低 |

### R6. LLM 章改造 · 第一步：语义增量，不改现有措辞

> 设计理由：提示语改动会**连锁触发指纹变更 → 缓存全量重算 → 输出观感变化**，同时触碰
> 「裁决文本 → 决策账本登记」的解析契约。故按「先增量、后替换」两刀，每刀可独立回滚。

| 项 | 内容 |
|:---|:---|
| 目标 | 只**新增**输出要求（反方证据、失效条件、下一个观察指标、可信度引用），不触碰既有指令 |
| 改动面 | `src/python/llm/prompts_action.py` 的情景段尾部**追加**一小段；`src/python/llm/prompts_review.py` 自检项**追加**一条（结论是否附条件） |
| 增量位置 | 情景段末尾新增：「如你认为信息不足以支撑方向判断，请明确写出『不操作』及所缺数据」——与同段既有指令并存；仅在情景段实际出现时追加（条件推理未配置情景或辩论跳过情景时不留无托指令） |
| 自检换键 | `prompts_review.py` 的自检清单文案不在任何换键盐覆盖范围内（`self_review_fingerprint` 内容寻址），故本轮的「结论是否附条件」自检项须同时把 `PROMPT_SCHEMA_VERSION` 并入自检指纹分段构成——静态清单文案改动同样换键，否则旧自检结论按旧清单复用最多 30 天 |
| 换键节奏 | 本刀**不递增**版本盐（同版本内两刀合并为一次重算，见 R7「发布」行），故 TTL 内旧缓存仍服务旧文本；源码级契约测试不受影响 |
| 架构约束 | 提示词变更即指纹变更（须在 changelog 说明重算影响）、LLM 模块注册表唯一、日志统一 invest |
| 设计契约 | 术语统一（信号可信度〔讨论稿称「置信度分级」〕/ 判断依据）；提示词不写任务编号 |
| 验收 | ① 契约测试：提示词**新增**四类要素存在（反方证据/失效条件/观察指标/不操作）；② 既有指令逐字不变（快照断言）；③ 指纹变更已在 changelog 说明「本版首轮重算」；④ 输出采样 5 次：出现「不操作」表述，且不出现「无依据的强方向」；⑤ **对照口径**：固定持仓与新闻（同一份输入），基线提示词与新提示词各 5 次，人工判读只统计「是否给方向 / 是否附条件」两个二元项，不做主观质量评分（样本不足以支持质量判断） |
| 风险与回滚 | 中：只增不减，回滚=删除追加段（指纹再次变更，可接受） |

### R7. LLM 章改造 · 第二步：替换冲突措辞 + 决策解析兜底

| 项 | 内容 |
|:---|:---|
| 目标 | 使提示语与 R6 的增量要求一致，并确保决策登记解析不被新表述打破 |
| 改动面 | ①`src/python/llm/prompts_action.py` 情景段要求为「**必须给出条件化动作 + 触发条件 + 若不满足则不操作**」，不保留强制方向表述；②「每个建议必须引用具体品种」开口子（允许「不对具体品种动手 + 理由」）；③`report/decision_llm_capture.py` 解析**兜底**：表格缺行/缺方向时跳过登记并记 INFO，不抛错 |
| 为什么必须同轮 | 只改措辞不改解析 → 「不操作」可能被当成可解析建议写进账本，污染决策数据 |
| 架构约束 | 提示词变更即指纹变更、时间距离按交易日计（如有「N 日内」表述）、渠道文案单源；回滚窗口内「回退提示词」与现提示词两套常量共存为**刻意的限时例外**，回滚确认后收敛回单源 |
| 设计契约 | 术语统一；禁止在提示词里出现内部代号 |
| 验收 | ① 契约测试：强制方向句**不出现**、条件化动作与触发条件句存在；② 解析兜底用例：「不操作」行 → 不登记 + INFO 一次；③ 端到端采样 10 次：`decision_ledger` 无新增脏记录（方向为空/表头行）；④ 同输入 A/B 各 10 次：新提示词下方向陈述比例低于基线，且无「无依据方向」 |
| 风险与回滚 | **中高**：影响输出观感与账本 → 开关 `decision_basis.enabled=false` 走回退提示词路径（两套文本常量共存一版）；回滚=切换常量。回滚验证：回退提示词与解析兜底组合下既有登记结果不变（兜底仅在解析失败时生效） |
| 口径变体换键 | 回退口径下专家复盘指纹追加 `_ms` 后缀（`scenario_mandate_cache_suffix`），保证「关掉判断依据块 → 提示词回退」当次即生效，不会命中新口径缓存；默认口径不加后缀（存量键形态不变） |
| 换键与重算 | 本刀落地时把 `src/python/llm/rate_caliber.py` 的 `PROMPT_SCHEMA_VERSION` 递增一次（`rate-caliber-1` → `rate-caliber-2`），四主模块与辩论键同批换键（R6 的增量与 R7 的替换一次生效）；`news_item`（独立后缀）与 `holding_change`（提示词未动）不受影响；changelog 声明「本版首轮重算」 |
| 观察项（每轮结束后 10 次运行） | `carrier=expert_review` 决策条数、方向分布、解析跳过次数；超出预期区间即回退。记录载体：观察结论写入 `docs/tmp/` 下的一次性记录，不长期留存 |

### R8. 纪律规则重构（算法层，承接讨论稿优先级 3）

> 与 R1~R5 的界限：R4 只**读**纪律状态做呈现，R8 才动规则本身（触发条件与阈值口径），两者互不替代。

| 项 | 内容 |
|:---|:---|
| 前置 | V5（品种波动率归一化后的止损阈值效果）先跑回测——`scripts/eval-decision-quality.py` 的 `discipline` 阶段已就绪（判据预注册：固定 −15% vs −2.5σ、触发窗口 5 日、效果窗口第 6~20 日、样本 ≥100、差值门槛 ±1%）；当前读数 20 日视界成熟样本仅 2 条、两条口径触发均为 0 → 样本不足不裁决，阈值口径维持默认（与既有 `horizon`/`factor-ic`/`valuation` 同风格），判据预注册同归档讨论稿 `investment-decision-quality.md` §2.2 口径并在 `scripts-reference.md` 同步阶段说明；未达样本门槛前只做默认关的规则实现，不改默认阈值 |
| 目标 | 消除「只卖不买」的结构性偏空：阈值按品种波动率归一化、止损与回撤合并为单一风险预算、增反向再评估 |
| 改动面 | `analysis/trade_discipline.py` 新增语义函数 `normalize_discipline_thresholds`（波动率归一化阈值）与反向再评估判定 `evaluate_reentry`；`src/python/config/_config_defaults.py` 新键单源登记：`discipline.vol_normalized`（bool，默认 `false`）、`discipline.reentry_window_days`（int，默认 `10`，按交易日计）；需求条目 R-DIS-08（归一化阈值口径）、R-DIS-09（反向再评估）；语义名同步 `technical.md` 功能语义命名表 |
| 架构约束 | 配置默认值单源（`_config_defaults.py`）；日志统一 invest；不改 `decision_review_block` 等下游消费者字段 |
| 设计契约 | 报告内纪律文案只讲当前口径（不出现「归一化」类实现术语）；阈值展示单位与现有百分比一致（百分数数值）；与既有交易纪律块同源同一阈值来源，文案互引不重复 |
| 验收 | ① 新键关闭时触发条数与报告输出与基线逐字节一致；② 归一化开启后高波动品种不被打穿（负向用例：同一跌幅在低/高波动品种上判定不同）；③ 止损与回撤同向时只减一次（不双重减仓）；④ 反向再评估只产出提示、不自动反向交易，窗口按交易日计；⑤ V5 回测结论按 R2 同口径登记（未达门槛则「样本不足」，禁用归一化阈值）；⑥ 配置含未知新键时读取侧不报错（回退默认，`config/_config_defaults.py` 单源）；⑦ 用例落 `src/test/unit/analysis/`（marker `unit_analysis`），阈值对比用 `approx` 容差 |
| 风险与回滚 | **高**（直接影响行为）：默认关；回滚=关归一化开关，阈值回默认值，账本既有条目不改写 |

### R9. 集中度与相关性硬约束（算法层，承接讨论稿优先级 5）

> 与 R3 的界限：R3 只把「上限 vs 现状」摆出来（不拦截），R9 才把超限变成可配置的拦截；两者上限表同源，不得各算一套。

| 项 | 内容 |
|:---|:---|
| 前置 | 用户确认可接受的约束强度（阈值与拦截方式需显式配置，不内置硬编码默认值）；相关性口径需样本期 ≥1 年（V7）——`eval-decision-quality.py correlation` 已就绪（预注册：窗口 60 日/步长 20 日、样本期门槛 250 交易日、样本 ≥100、|IC| ≥0.05、方向须为正）；当前读数样本期 146 交易日、窗口 5 个、IC −0.36（样本期不足不采信），故该项维持「未评估」，不足时该项显示「未评估」且不参与拦截 |
| 目标 | 集中度/相关性超限从「只提醒」变为「可配置拦截」，避免单主题集中（纳指系 42%）放大亏损 |
| 改动面 | 新建 `analysis/portfolio_constraints.py`（语义名 `portfolio_constraints`：单品种/行业/相关性上限判定，输入取持仓与 R3 同一上限表；相关性复用 `position_relationship_data` 既有计算，不另算矩阵）；`src/python/config/_feature_registry.py` 登记开关 `portfolio_constraints`（默认关）、`src/python/config/_config_defaults.py` 登记 `constraints` 段（`single_max_pct`/`industry_max_pct`/`correlation_max`，缺省 `null`=未配置=不拦截）；需求条目 R-DIS-06（硬约束判定）、R-DIS-07（拦截标注）；`decision_ledger.append_decision` 增可选参数 `constrained`（缺省 `None`，历史事件按未拦截读） |
| 架构约束 | 配置默认值单源；章节序号与显示名不硬编码；品种/行业判定走 `core/code_utils.py` 与既有分类函数；账本写入走既有追加原语（`core/jsonl_store.py` 的原子追加，禁直写文件）；拦截结论只进规则层，不进 LLM 提示词（避免模型自行「代理」约束） |
| 设计契约 | 被拦下的建议在判断依据块用状态域语义色标注并附「触发的约束项」，不与涨跌域混用 |
| 验收 | ① 拦截关闭时账本写入与报告输出与基线逐字节一致；② 开启后超限建议**照常登记账本**并置 `constrained=true`，同时在建议清单与判断依据块标注约束项名称（不静默丢弃，避免结算统计口径断裂）；③ 与 R3 上限同源（同一配置项改一处两边同步，断言）；④ 相关性样本不足时显示「未评估」不拦截；⑤ 旧账本事件无 `constrained` 字段时按未拦截读（兼容用例）；⑥ 需求条目 R-DIS-06/07 与 `how-to-config-reference.md`、`technical.md` 命名表同步；⑦ 用例落 `src/test/unit/analysis/`（marker `unit_analysis`） |
| 风险与回滚 | **高**（触及配置与使用习惯）：默认关，阈值只能显式配置；回滚=关拦截开关，历史账本不改写 |

### 跨轮质量门禁（每轮必过）

| 门禁 | 内容 |
|:---|:---|
| 测试 | 每轮新增用例并标 pytest marker；`dev-verify` 全绿；涉及契约的加 `integration` 契约用例；edge 场景入 `*_edge.py` 并标 `edge`（R8/R9 的极端阈值/空配置场景同此）；浮点断言容差化（`approx`）；不写死可增长集合条数；账本/输出目录用例重定向 `tmp_path`；**自动化用例一律 mock LLM——R6/R7 的「采样 N 次」为真机人工验收步骤，不入自动化套件** |
| 守护 | 十守护全绿（pre-commit 钩子自动执行全量；此列为每轮重点复核：`check-doc-drift` 章节-区块矩阵/契约字段/文档表格、`check-code-traces`、`check-test-redundancy`、`check-file-length`） |
| 设计护栏 | `check-style-guardrails` E 级 0；新增 token 须先登记 `DESIGN.md` 两面（亮/暗）；新增报告样式过移动档核验（≤480px，`DESIGN.md` 一等场景） |
| 文档同步 | 每轮必改：`technical.md`（附录 H 契约 + 语义命名表 + §4.22 区块矩阵）、`testplan.md`（测试载体登记）、`test-coverage.md`、`folders.md`、`changelog.md`；R1 起补 `requirements.md` 的 R-OUT 条目与 `core/section_block_registry.py` 区块登记；R2 起在 `config/_feature_registry.py`（开关唯一事实源）与 `how-to-config-reference.md` 登记 `decision_basis.enabled`；R8/R9 另需 `requirements.md` 的 R-DIS-06~09 条目、`how-to-config-reference.md` 对应键与 `technical.md` 功能语义命名表（`normalize_discipline_thresholds` / `evaluate_reentry` / `portfolio_constraints`） |
| 发布 | 累计完成后走 `release.py gate`；R0~R5 可分散在不同版本发布，R6/R7 建议同版本发布（前后脚，便于对照），R8/R9 单独版本发布且首发即默认关（行为变更类，需单版本对照观察） |
| 回滚演练 | 每轮合并前演练一次「开关关闭」路径（`decision_basis.enabled=false` 或删追加段），确认回到基线且无残留契约字段被消费 |

## 5. 验收（跨轮汇总口径）

单轮验收见各 R 轮「验收」行；本节给出**全局判定**：

| 维度 | 判定标准 |
|:---|:---|
| 功能 | R1 起行动章出现「判断依据」块（空态契约），R2~R5 逐节充实，R5 后信号可信度/信号清单/风险预算/纪律/结算五节齐；默认折叠，summary 一句话结论；R8/R9 为算法层（不改块内呈现），默认关时不影响上述输出 |
| 架构 | 代码类型判定中心化 / 章节序号与显示名不硬编码 / 日志统一走 invest logger / 渲染数据走模板 context / pipeline_data Schema 契约 / 提示词变更即指纹变更 / 时间距离按交易日计 —— 逐轮落实（见各轮「架构约束」行）；形态 A 不新增章节 key；形态 B 新增时注册表三向对账通过 |
| 设计 | Data States 三档空态口径、语义色、字阶/间距档、涨跌域与状态域分离、暗色同步、打印展开——均按 `DESIGN.md` 验收 |
| 质量 | `dev-verify` 全绿；十守护全绿；`check-style-guardrails` E 级 0；新增 token 两面登记（本节为**全局判定口径**，逐轮检查项见「跨轮质量门禁」） |
| 红线 | 信号区分度三态如实标注（未回测 / 样本不足 / 回测未通过均不进方向轴）；空态不得显示「可信度高」；块内零 LLM 文本；R8/R9 默认关且不得修改历史账本条目 |
| 回归 | `enable_llm=False` 与 `True` 时该块输出逐字节一致；`decision_basis.enabled=false` 时全报告与其基线快照逐字节一致 |

## 6. 风险与回滚

| 风险 | 缓解 |
|:---|:---|
| 新章与「行动建议」章内容重复、用户困惑 | 明确分工：行动建议=算法动作，决策依据=材料与约束；文案互引 |
| `discrimination` 需回测才可信 | 无结论一律「未回测/样本不足」不填先验；估值分位已有回测结论（两口径均无区分度，归档讨论稿 `investment-decision-quality.md` §8.1）按「已回测未通过」接入，复跑达到裁决门槛后随 R2 的模块常量更新 |
| LLM 章转为解读层后「没结论」被用户视为退步 | 决策依据章承担「结论」职责；LLM 章定位为「为什么与什么时候会错」 |
| 章首过重（形态 A） | 默认折叠 + summary 一句话结论；只放一块，详情引用既有章节数据 |
| 可发现性弱（形态 A） | 块标题固定为「判断依据」，并在行动章标题副行补「依据 · 信号 · 纪律 · 调仓 · 归因」 |
| 低可信度引发焦虑 | summary 附「下一步观察指标」，不只报坏消息 |
| R8 归一化阈值误伤低波动品种 | 阈值按波动率归一后用**相对波动率**而非绝对值放大；默认关 + V5 回测门槛；开启后观察首批触发条数偏移并留回滚开关 |
| R8/R9 与既有静默期叠加 | 归一化不改静默期口径（同 `discipline.silence_days`）；再评估窗口与静默期互不覆盖，避免「静默中提示回补」的双向噪音 |
| R9 拦截导致建议清单与账本不一致 | 账本照常登记并置 `constrained=true`，拦截只影响呈现与动作清单；结算统计仍按原口径 |
| R9 相关性口径样本不足 | 相关性矩阵需样本期 ≥1 年（V7）；不足时显示「未评估」且只按单品种/行业上限判定 |
| 回滚 | 形态 A 由 `decision_basis.enabled` 关闭；形态 B 由独立开关关闭；R8/R9 由各自开关关闭（阈值回默认）；数据结构不删除，只隐藏渲染 |

---
