# 投资复盘助手 — 实现计划
> 文档版本：0.14.9-dev
> **编号源**：`plan-next = 202`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-201，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 8 项——P2 6 项（**plan-92/93/185**、配置体系重构剩余 2 轮 **plan-199/200**、技术债收敛 **plan-201**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）；另有 4 项已实施待随发布归档（**plan-195/196/197/198**）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

当前无 P1 项。入选标准：立即可执行且价值/风险最高（数据完整性、费用风险、核心量化缺口）。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状**：19 页签全为静态数字与文字，无条件格式 / 迷你图 / 原生图表——收益率高低、集中度偏离需逐格读数。

**动作**：高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生能力）；先试点 2~3 个页签（持仓明细 / 量化指标 / 集中度），认可后再扩，避免样式膨胀与体积增长。

#### `plan-93` 历史报告归档无索引导航

**现状**：`html_save` 按日期归档到子目录但不生成 index；TUI 无「最近报告」入口；Web 的运行历史不含 HTML 归档目录——找上期报告只能翻文件系统。

**动作**：生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；只列路径信息，匿名化口径与报告一致。

#### `plan-185` 收益率指标缺口径标签，模型反复写错

**现状**：标签已落地（`llm/rate_caliber.py` 为唯一声明点，`PROMPT_SCHEMA_VERSION` 已并入模块指纹），**余验收**。模型对收益口径（累计 / 持仓 / 区间 / 年化）判定仍不稳定——事实校验只能把数值改对，句意与修饰语可能挂错口径。

**验收口径**：看 `perf_history.counters.fact_fix_total` 是否稳定低于基线 10 处。近三次实跑为 **3 / 9 / 2 处**（2026-10-23 07:55 / 18:58、10-24 00:20），波动明显、尚未稳定达标；连续若干轮 ≤3 处即归档。

#### `plan-195` Web 配置面契约（domains / labels / blocks）——已实施，待发布归档

服务端下发 `domains`（五域 → 有序块清单）与 `labels`/`descriptions`/`defaults`/`needs_hint` 元数据、`logging`、`reference`；前端按域渲染 + 块渲染器分派，零中文表。机检：`test_config_surface_contract`（17 例）；记录见 changelog 配置重构第 10 轮。

#### `plan-196` Web 配置面交互与状态——已实施，待发布归档

工具条统计（基准 = 服务端 `defaults`）、关键词筛选、域导航与 `#domain-<key>` 深链、块计数、窄屏单列；保存语义分即时（失败回滚）与显式（失败保留输入）两类。机检：`test_web_config_interaction`（17 例）；记录见 changelog 配置重构第 11 轮。

#### `plan-197` 配置重构的文档与契约登记收口——已实施，待发布归档

手册与管理文档全量对齐当前结构（主菜单 14 项四组、Web 五域分区、`[G]` 七项四组、`[D]` 四项），抽检 `[D]`/`[G]`/`[S]`+`[C]` 三处与代码逐字一致；契约档结构守卫绿。记录见 changelog 配置重构第 12 轮。

#### `plan-201` 事实校验评估函数参数收敛（技术债）

**问题**：`llm/fact_checker/_numerical.py::_evaluate_percent_value` 单函数 22 个参数（7 基础值 + 10 语境开关布尔 + 5 数据映射），新增一种语境要同步改签名/文档/调用点与全部直接用例；语境判定的隐式顺序只体现在函数体里。登记见 `review-findings.md` 的 `rf-839`。

**动作**：收进上下文对象（基础值 + 持仓映射 + 语境开关），签名收敛为单参；语境判定优先级在构造侧单源声明。前置：先补「语境词 → 期望结果」对照表测试，作为两种实现等价的判定依据；生产调用点唯一（`check_numerical_consistency`），回归面可圈定。

#### `plan-198` 配置重构质量门禁全量——已实施，待发布归档

五道闸口全绿：`verify` 11318 通过 / 0 失败、十守护零 finding、性能门禁 basic **0.48s ≤ 60s**、`portability` 2 探针通过（`LC_ALL=C` + 隐式编码严格档）、`ruff check` / `format --check` 零告警。本轮修正两处真实缺陷：计价懒加载覆盖显式重载（`rf-837`）、`test_json_comments` 子进程缺显式编码（portability 探针拦下）。记录见 changelog。

#### `plan-199` 配置重构发布编排

**现状**：配置结构已变更（v2 嵌套、日志与计价独立文件），需按「不做旧版兼容」策略发布，并留下可追溯台账。

**动作**：走通 `release.py` 全链——`prepare`（版本全链 + changelog / plan / review-findings / docs-plan 归档迁移）、`refresh`（bench + 覆盖率 + 统计同步）、`evolution --release`、`gate`（含前置断言）、`publish`（`--no-ff` 合并 + tag）、`devbump`。验收：gate 全绿、版本一致性 15 项全绿、tag 已推送、`master` 已合并、`devbump` 后开发版本号与文档版本头一致。

#### `plan-200` 配置稳态观测与回退演练

**现状**：「加载失败 / 生成器重建 / 缓存首轮全量重算 / 结构不符」四类路径缺现场验证与观测接入，出问题时难判是配置错配还是程序缺陷。

**动作**：观测项接入现有日志与 `perf_history`（配置加载失败日志、日志配置生效记录、计价覆盖告警、指纹变化后的缓存命中率，不新增面板）；回退演练按「不做旧版兼容」验证重建路径。验收：① 制造非法配置 → 启动日志含文件名 + 键 + 原因且不静默回落；② 删除配置文件 → 生成器重建后启动正常（`llm_settings.json` / `logger.json` / `llm_pricing_ref.json` 逐一验证）；③ 清空缓存 → 首轮全量重算、第二轮起命中率恢复（数值记录在案）；④ 把配置目录整体置为非当前结构样本 → 明确拒绝并给出重建指引。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**问题**：实验开关靠「真实数据验证后择机转正」，但账本积累慢、闭环缺真实数据；长期挂一个默认关闭的开关是纯维护成本。

**判据**：以 `experiment_stats` 启用计数与账本结算数跨发布周期观察两条判据——① 启用次数停止增长（无真实使用），或 ② `data/state/decision_ledger.jsonl` 已结算样本 <10 条（折叠统计 `direction_accuracy` 无法给出可信命中率）**且已结算无达标趋势** → 撤销该实验功能（含 LLM 决策登记 `decision_llm_capture`、行动章复盘块注入与对应需求条目）；已结算 ≥10 条则据 doctor 账本概览评估转正。观测手段：`experiment_stats` 启用计数 + `doctor` 复盘账本概览。

**当前状态**：维持观察。启用 67 次（最近 2026-10-24）、账本已结算 16 条 / 待结算 42 条；`directional_total = 12`、命中率 75%、`sample_sufficient = False`（样本仍不足）。待结算条目由 `settle_pending_decisions` 到期自动结算（A 股 kline 与场外基金 nav 已覆盖）；`directional_total` 达 40+ 时评估转正，若长期 <20 且无新增则按撤销条件 ② 处置。

**单一事实位**：本实验的「条件—数据—态」结构化口径见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)（决策跨期反思闭环行）；立项/转正/撤销时双方同步刷新。

**落地设计（转正后启动）**：按 [`decision-reflection-design.md`](../plan/decision-reflection-design.md) 四迭代执行（决策条目结构化 → 到期结算器 → doctor 概览增强 → 报告内反思块），以 Vibe-Trading `shadow_account`（extract→backtest→render）为参照；判据未过前不实施。与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**现状**：该模块的关联度/情绪判定属**窄判断**（批量、选项有限、需校准概率），是 Jev 类型化判定接口的适用场景；其余四个模块为长文生成，不适用。

**状态**：待评测——评测脚本（`eval-jev-news-judgment.py`）尚未建立，三方对照未开跑。

**先决门槛（未过不接入）**：按 `docs/plan/jev-news-judgment-evaluation.md` 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标选取、预检收窄结论与预注册阈值见该文档 §2/§7。**未达阈值则归档为已评估未采纳。**

**待评测结论确认后再实施的部分**：见 `docs/plan/jev-news-judgment-design.md`。

**约束与红线**：① 不得作为用户可选的对话模型（该模型不生成文本）；② 不得做成「生成 + 判定」双供应商级联（无信息增量且多一个中间失败态）；③ 语料含真实持仓与新闻，冻结产物必须落 `docs/tmp/`（git 忽略），仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键须按开关注册表统一纪律登记，默认值保持 `chat` 使缺省行为逐字节不变。

**成本 / 价值**：成本低（评测脚本 + 模板渲染 + 一个独立客户端模块）；价值中（仅影响一个出厂默认关闭的模块，收益是更稳的解析与可校准概率，不以省钱为卖点）。

## 归档

- [`archived_plan.0.14.x.md`](../archive/v0.14.x/archived_plan.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
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
