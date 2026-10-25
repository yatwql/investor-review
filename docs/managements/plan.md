# 投资复盘助手 — 实现计划
> 文档版本：0.15.8-dev
> **编号源**：`plan-next = 229`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-228，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 8 项——P2 5 项（**plan-92/93/225/226/227**）、P3 2 项（**plan-70/228**）、P4 1 项（**plan-55**）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

当前无 P1 项（含 P0）。入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生）；先试点持仓明细 / 量化指标 / 集中度 2~3 个页签，认可后再扩。

#### `plan-225` 缓存 TTL 机制收敛（来源 rf-874 / rf-875）✅

**完成**：盘中敏感性从配置列表下沉为注册表数据属性——`DataModuleDef.market_ttl`（`price`/`index` = 30s）；`config.market_hour_aware` 退役（写入时校验告警并忽略），配置只留 `market_hour_ttl` 全局数值覆盖（钳制 [30, 86400]）；`get_ttl` 对"盘中覆盖与 `cache_ttl` 冲突"打一次性 INFO（静默失效变可见）。两个负缓存类型（`datasink_probe_miss` 12h / `report_symbol_miss` 6h）登记进注册表，读侧与 `cleanup_expired` 同源、`cache_ttl` 可覆盖、文档表格可见。

**验收**：盘中 30s 与盘后静态 TTL 双向契约、退役键无扩权、覆盖提示仅一次、负缓存清理按 12h/6h 判定（不吃 24h 兜底）、全量注册类型 TTL 为正——`test_cache_edge.py::TestGetTTLIntraday`、`test_ttl_alignment.py::TestIntradayAndNegativeCacheTTL`、`test_registry.py` 结构性断言；`technical.md` TTL 流程、`datasource.md` 负缓存表与盘中口径、`requirements.md`/`how-to-config.md` 配置表同步。

#### `plan-226` 财报索引与财务指标 TTL 对齐披露节奏（来源 rf-876）

**现状（实测）**：`report`（财报索引）与 `fin_indicator`（财务指标）都是 **symbol 级缓存键 + 30 天 TTL**（`get_ttl("report")` / `get_ttl("fin_indicator")`）。A 股定期披露按季：新一期财报披露之后，索引最长要等 30 天才重新拉取 → 报告可能整月沿用上一期口径。当前缓解手段是 TUI `[C]` 基础缓存刷新（`clear_by_group("refresh")`），但只在用户主动操作时生效，定时/无人值守运行仍会滞后。

**动作**：`report` 索引 30d → **1d**（正文 `report_doc` 保持 30d：正文按 `doc_id` 不可变，且探测负缓存已保证缺失章节不重复打源）；`fin_indicator` 30d → **1d**（symbol 级键，新报告期靠日刷新被发现）。`dividend` 30d → 7d（分红公告不定期，同属"symbol 级键 + 长 TTL"）。

**配额测算（客观依据）**：DataSinking 生效日配额 `resolve_daily_quota()` = **8191**（免费档），今日已用 121。索引刷新为每标的每日至多 1 次请求，持仓规模 10~20 → **+10~20 请求/日（占配额 0.12%~0.24%）**，一天跑 4 次报告也不放大（TTL 而非调用数决定）。故该调整的对外成本可忽略，收益是"新披露 ≤1 天可见"。

**硬约束**：不改 `price`/`index` 的盘中路径；`report_doc` 与 `sector_flow` 等盘中/日频类型不动；改动须同步 `datasource.md` 缓存表 + `technical.md` 默认值表，并补"新报告期次日可见"的回归用例（用固定时钟 + 假索引验证 TTL 边界）。

#### `plan-227` LLM 模块 TTL 取值决策所需观测（来源 rf-879）

**现状**：`llm_expert_review` / `llm_health_check` / `llm_penetration_deep` / `llm_news_correlation` 统一 4h。指纹（`module_fingerprint`）已覆盖持仓/数据/参数变化，4h 的实际作用只是"内容未变时也强制重算"的上限；一天跑 2~3 次报告会重复调用最贵模块（`how-to-config-llm.md` 估算单次 ¥0.02~0.04）。

**为什么不能凭感觉改**：把 4h 调到 8~12h 直接换成本/时效，取决于真实使用节奏（每天几次报告、指纹是否变化、不同模块的到期分布），当前没有数据。

**动作**：先加**观测**不改值——在生成链路记录每模块"本次重算原因"（`fingerprint_changed` / `ttl_expired` / `no_cache` / `forced`）并累加到 perf（`llm.modules.*.recompute_reason`）；跑满一周后按分布决定是否调值（建议内容型 8~12h、`news_correlation` 维持 ≤4h）。观测本身不改行为、不增加调用。

**硬约束**：观测字段只增不改；`self_review` 为内容寻址（上游重算即换键），不参与本次调值讨论。

#### `plan-228` 决策/信号账本保留上限（来源 rf-880）

**现状**：`decision_ledger.jsonl`（26 KB）、`signal_ledger.jsonl`（127 KB）只追加、无上限；同类历史文件已有策略——perf 5000 行、健康检查 2000 行、去重锚点 120 天 + 超限压缩，三者不一致。

**动作**：两本账加**按龄保留**（建议 730 天：决策跨期反思需跨季度样本）并在写入时复用 `jsonl_store.append_jsonl_atomic(..., max_lines=)` 兜底行数上限；超限压缩保留最近样本与"已结算"记录（防止反思样本被裁光）。

**硬约束**：压缩需幂等、原子（`atomic_write`）；不得改变账本读取接口；`plan-70`（决策跨期反思）依赖结算样本，压缩规则须保证已结算决策不被裁剪。

#### `plan-93` 历史报告归档无索引导航

**现状**：HTML 按日期归档到子目录但不生成索引；TUI 无「最近报告」入口；Web 运行历史不含归档目录。
**动作**：生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；只列路径信息，匿名化口径与报告一致。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**状态**：观察中——启用 75 次、已结算 16 条 / 待结算 47 条，`directional_total = 12`（阈值 40），样本不足。
**判据**：启用停增或已结算 <10 条且无达标趋势 → 撤销该实验功能（含 `decision_llm_capture`、行动章复盘块与对应需求条目）；已结算 ≥10 条按 `doctor` 账本概览评估转正，`directional_total` 达 40+ 再评估。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按四迭代执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**单一事实位**：[technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)「决策跨期反思闭环」行。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测——`eval-jev-news-judgment.py` 未建立，三方对照未开跑；该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。

### 已完成待归档（下次发布迁入版本归档）

## 归档

- [`archived_plan.0.15.x.md`](../archive/v0.15.x/archived_plan.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_plan.0.14.x.md`](../archive/v0.14.x/archived_plan.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_plan.0.13.x.md`](../archive/v0.13.x/archived_plan.0.13.x.md) — v0.13.x 已完成项
- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md) — v0.12.x 已完成项
- [`archived_plan.0.11.x.md`](../archive/v0.11.x/archived_plan.0.11.x.md) — v0.11.x 已完成项
- [`archived_plan.0.10.x.md`](../archive/v0.10.x/archived_plan.0.10.x.md) — v0.10.x 已完成项
- [`archived_plan.0.9.x.md`](../archive/v0.9.x/archived_plan.0.9.x.md) — v0.9.x 已完成项
- [`archived_plan.0.8.x.md`](../archive/v0.8.x/archived_plan.0.8.x.md) — v0.8.0 ~ v0.8.10
- [`archived_plan.0.7.x.md`](../archive/v0.7.x/archived_plan.0.7.x.md) — v0.7.x 已完成项
- [`archived_plan.0.6.x.md`](../archive/v0.6.x/archived_plan.0.6.x.md) — v0.6.x 已完成项
- [`archived_plan.0.5.x.md`](../archive/v0.5.x/archived_plan.0.5.x.md) — v0.5.x 已完成项
- [`archived_plan.0.4.x.md`](../archive/v0.4.x/archived_plan.0.4.x.md) — v0.4.x 已完成项
- [`archived_plan.0.3.x.md`](../archive/v0.3.x/archived_plan.0.3.x.md) — v0.3.x 已完成项
- [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) — v0.2.x 已完成项
- [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md) — 早期版本已完成项
