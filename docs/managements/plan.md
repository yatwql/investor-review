# 投资复盘助手 — 实现计划
> 文档版本：0.15.5-dev
> **编号源**：`plan-next = 213`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-212，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 8 项——P2 6 项（**plan-92/93/185/210/211/212**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

当前无 P1 项。入选标准：立即可执行且价值/风险最高（数据完整性、费用风险、核心量化缺口）。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生）；先试点持仓明细 / 量化指标 / 集中度 2~3 个页签，认可后再扩。

#### `plan-93` 历史报告归档无索引导航

**现状**：HTML 按日期归档到子目录但不生成索引；TUI 无「最近报告」入口；Web 运行历史不含归档目录。
**动作**：生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；只列路径信息，匿名化口径与报告一致。

#### `plan-185` 收益率指标缺口径标签，模型反复写错

**现状**：口径标签已落地（`llm/rate_caliber.py` 唯一声明点，并入 `PROMPT_SCHEMA_VERSION` 指纹），**余验收**——事实校验只把数值改对，句意与修饰语仍可能挂错口径。当前 `fact_fix_total` 为 5 / 4，未达到连续 ≤3。
**验收**：`perf_history.counters.fact_fix_total` 连续若干轮稳定 ≤3 处即归档。

#### `plan-210` 报告重复运行耗时优化（LLM / 新闻）

**当前状态**：完整报告（LLM 开启）约 140–153s，其中专家复盘 71–75s、新闻获取 19–23s；无 LLM 基线约 44–52s。新闻缓存保持 900s，专家/健康指纹含市值/盈亏字段，行情变化即失效，不做跨报告复用；新闻去重 `quick_ratio`、事件窗 bars/index 同批 memo 已落地。

**当前验证**：最新完整报告 35.7s，`LLM+新闻` 20.2s；事件窗 bars/index memo 后装配降至 0.43s（此前 18.3s），新闻获取 19.7s/去重 12.0s。LLM 未实际调用，缓存/专家耗时仍需在 LLM 开启下复测两次同条件报告。

**验收**：连续两次同条件报告的第二次 `LLM+新闻` 耗时下降 ≥50%，或专家复盘命中应用缓存；报告内容与首次一致（除生成时间）；补缓存键失效/命中的回归用例。

#### `plan-211` 数据源降级与告警分级（行业资金流向 / hithink / K 线）——进行中

**当前状态**：K 线风控页逐代码日志使用 DEBUG，源失败仍计入 registry、熔断汇总保留 WARNING；hithink 过滤场内 ETF 的 A 股价格/历史槽，并归一错误交易所后缀；行业资金流向暴露公开失败状态访问器，报告层经 `mark_data_unavailable` 写入 DegradationTracker，数据源矩阵显示不可用；`fetcher` / `cache` 统一经公开访问器读取状态。最新报告 `warnings_count=2`（仅行业资金流向：akshare 重试 + 获取失败），`Unknown thscode=0`，push2 per-code 告警为零；告警目标 ≤10 已达标。

**剩余**：同条件复测 `warnings_count` 与 `Unknown thscode`；行业资金流向备用源或缓存方案（当前先保证状态可见）。

**不做**：不伪造数据、不把外部源失败静默当成功；不扩大年报/财报抓取范围。

**验收**：同条件报告 `warnings_count` 从 35 降至 ≤10 且无 `Unknown thscode` 无效请求；行业资金流向有明确可用/不可用状态；补数据源路由与降级回归。

#### `plan-212` 报告级 LLM 缓存状态隔离与指纹审计——进行中

**现状**：同一非交易日、同持仓、新闻缓存命中时连续两次报告，LLM 模块仍全部缓存 miss；总市值/盈亏相同，说明不是 TTL 到期，而是报告级状态或指纹输入变化。设计见 [`llm-cache-state-isolation.md`](../plan/llm-cache-state-isolation.md)。

**已落地**：`report/_run_scope.py` 报告边界（清本轮降级事件、重置自检载体、取用量基线）；`_usage_delta` 按报告记账；`fingerprint_components` / `diff_fingerprint_components` 组件级审计（DEBUG 下自动记录相对上次的变化，与生产指纹同口径）；数据质量块只统计失败事件；持仓变动窗口行按日去重口径，不输出原始快照文件数。

**不做**：不为命中缓存忽略行情/指数/数据质量/账本变化；不跨日缓存；不改变现有缓存 TTL。

**剩余**：实跑两次同条件报告确认命中（已排除快照计数、降级事件、用量累计、审计口径四类伪变化）。

**验收**：同非交易日、同持仓/指数/新闻连续两次报告，基础模块第二次命中；perf LLM token/call_count 为单次报告值；无上一轮 degradation/self_review 残留；补同进程双报告与失效回归。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**状态**：维持观察——启用 75 次、账本已结算 16 条 / 待结算 47 条；`directional_total = 12`、命中率 75%、样本仍不足（阈值 40）。
**判据**：① 启用次数停止增长（无真实使用），或 ② 已结算样本 <10 条且无达标趋势 → 撤销该实验功能（含 `decision_llm_capture`、行动章复盘块注入与对应需求条目）；已结算 ≥10 条则按 `doctor` 账本概览评估转正，`directional_total` 达 40+ 时评估转正。
**落地设计（转正后启动）**：按 [`decision-reflection-design.md`](../plan/decision-reflection-design.md) 四迭代执行，以 Vibe-Trading `shadow_account` 为参照；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**单一事实位**：[technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)「决策跨期反思闭环」行。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测——评测脚本 `eval-jev-news-judgment.py` 未建立，三方对照未开跑；该模块属窄判断（批量、选项有限、需校准概率），是 Jev 类型化判定接口的适用场景。
**先决门槛（未过不接入）**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标、预检收窄结论与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**待评测后实施部分**：见 [`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不得作为用户可选对话模型（不生成文本）；② 不得做成「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

## 归档

- [`archived_plan.0.15.x.md`](../archive/v0.15.x/archived_plan.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-24）
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
