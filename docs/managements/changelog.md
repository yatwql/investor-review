# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.0]**（2026-11-04）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.1-dev] - 开发中（未发布）

### 修复

- **LLM 缓存指纹分界：只锁结构与口径，行情/时效类交 TTL（`rf-1040`）**：连续两轮「持仓与市值完全相同」的报告仍 4/4 全 miss，预检归因 `fingerprint_changed=4`（不是 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、A/美股指数、竞争语境块、量化指标、历史风险信号、穿透市值与占比）与时效数据（事件窗分歧例块、调仓纪律回放块：新闻 15 分钟一刷且每行带收益/超额浮点）全数锁进键，使 4h（`expert_review`/`health_check`/`penetration_deep`）与 24h（`global_macro`）TTL 实际退化为分钟级。改法：`build_llm_fingerprint` 入键收窄到持仓成本（`name/code/cost`）+ 分类**结构**（新增 `extract_stable_categories`：类型→排序品种集，不含市值/盈亏）+ 穿透品种集与 `sector`（新增 `extract_stable_penetration(include_sector=True)`，`full` 口径保留为诊断专用，`risk_signals_of` 降为诊断口径）+ 两个版本盐；行情类参数保留形参但不再参与哈希。四个模块构造器同步剔除竞争语境/量化指标/风险信号，`global_macro` 改为持仓+分类结构（并补传 `holdings_details` 保证预检/写两侧同源）；事件窗分歧例块与调仓纪律回放块出键（仍进提示词），自检与辩论三键同口径；`skeleton` 新增 `_APPENDIX_EXCLUDED_SECTIONS`，`global_macro` 不注入事件窗分歧例块。文档同步：requirements（R-HCR-05/R-SR-04/R-EW-06 改「口径类进键、时效类交 TTL」）、technical §3.4 指纹分界与失效语义；单测七份同步（`test_module_fingerprint` / `test_cache_fingerprint_alignment` / `test_cache_matrix` / `test_cache_sequence_matrix` / `test_report_sequence_cache` / `test_fingerprint_baseline` / `test_fingerprint`），事件窗与回放注入用例改为断言「时效块不换键」，并新增 `test_market_derived_inputs_do_not_change_fingerprint` ×4 与 `test_structural_inputs_change_fingerprint` ×4 锁定分界。


### 新增

- **判断依据块章首三行摘要（`plan-245`）**：块默认折叠、summary 只有一行，多数读者不展开 → 该需求体感为零。改为行动建议章首固定三行：① 有效信号数与可信度档 ② 风险预算超限项 ③ 纪律触发数（无超限/无触发写否定态，三段全不可用压成一行空态），明细仍折叠；`build_headline()` 单源产出，HTML 渲染在折叠块之前、Excel 写在块首，两端逐字一致；`headline` 进 `decision_basis_data` 契约，Excel 旧契约无该键时回落单行 summary。
- **「我的建议历史表现（按视界）」表（`plan-244`）**：结算能力早已在（`settle-decisions` + 账本 5/20/60 `settlements`），但报告只露出「结算批数」，用户读不到「我的建议历史上准不准」。在判断依据的结算摘要下补按视界聚合表（已结算数 / 方向性样本 / 命中数 / 命中率 / 均值超额），命中判定复用 `decision_ledger.classify_direction_outcome`（含 ±1.5% 平盘不判定），命中率仅在方向性样本 ≥ 20 时给结论值，否则「命中/方向性（样本不足）」；只读账本、不依赖 `decision_reflection` 开关，口径与 `settle-decisions` / `doctor` 同源；双端同表，数据缺口行计入 gap 不再静默丢样本。
- 测试：新增 `TestDecisionBasisHeadline`（三行规则 / 否定态 / 空态压缩 / 章首位置在折叠块之前 / 双端同文）与`TestPerformanceByHorizon`（命中-未命中-平盘-缺口计数 / 样本门槛口径 / 基准缺失不入超额均值 / 双端渲染）；`test_action_sheet` 与双端同源用例改按 headline 断言。

### 变更

- **plan-243 收口：决策依据链路停止加码，剩余价值拆为独立任务**：自家回测把这条链路的卖点判掉了（V1 5 日成熟 61 条命中率 0.5385、均值超额 −0.0053；V3 两口径 5 日 IC +0.0399 / −0.0267 均无三分位单调；V5 成熟样本 2 条、V7 样本期 146 交易日 < 250）——五类信号三家证伪、两家样本不足，链路只能如实摆事实、不产生预测力。据此 **R8 纪律规则重构不启动**，估值分位/因子目录按「已回测未通过」「样本不足」归档（保留三态标注呈现，`eval-decision-quality.py` 留待样本累积后一次性复跑），形态 B 独立章节不启用；观察项（V5 成熟样本 ≥100、V7 样本期 ≥250）只在触发条件满足时再看。剩余用户价值拆为 **plan-244**（「我的建议历史表现」可见视图：5/20/60 视界命中率与均值超额，只读账本）与 **plan-245**（依据块章首默认展开三行摘要，解决「默认折叠 → 体感为零」）。

- **both 路径申购限购取数接线修错（`rf-1041`）**：`_generation_both` 把 `config` 当 `holdings_details` 传给 `build_purchase_status_data`，开启「基金申购限购」（默认开）且全量表取数成功时，构建期渲染约束块迭代 dict 得到键名（str）→ `h.get("code")` 抛 `AttributeError`，HTML+Excel 双产物整条中断（`report` 命令直接失败）。改传持仓明细最小形态 `[{"name": d.name, "code": d.code} for d in details]`（与 full 路径同源同形，受阻标的口径不变）；补回归用例（`test_both_path_passes_holdings_details_not_config_to_purchase_status`）。

- **智囊团复盘方向约束收敛为一句（去掉叠用的对冲措辞）**：情景段原有三处同义且互相抵消的指令——条件化动作要求、随情景段追加的「不操作是合法结论」出口、以及品种引用段「除非不对具体品种动手…无需勉强引用品种」的口子，与系统提示 Phase 3「给出量化调仓方案」并存时只能产出官样回避口吻。改为单源一句：`MANDATE_CONDITIONAL` 写清「满足什么条件动手、动什么」，条件不成立或信息不足则直接写「不操作」并点明所缺数据；`scenario_mandate()` 改由两条情景路径（标准 fallback / 配置条件情景）共用一处追加，品种引用口子压成一句、不再复述「不操作」；系统提示 Phase 3 补「结论为不操作时写明理由与触发条件」使两处口径同向。
- **智囊团专家须具名**：召集令只要求「挑 5 位流派对立专家并标明立场」，模型常以 A/B/C/D/E 或「专家1/2」占位，可读性差。系统提示补「姓名式称呼 + 机构/头衔，禁止 A/B/C/D/E、「专家1/2」或「多/空」这类占位名，同一专家全篇用同一称呼」。
- 上述两项均为提示词静态文案改动，`PROMPT_SCHEMA_VERSION` 递增 `rate-caliber-2 → 3` 一次性换键（四可回写模块与自检键同步重算，属预期）；`test_module_fingerprint` 的接线前基线随盐刷新；单测补「对冲措辞只出现一处」「专家具名禁止占位名」断言。
- **`decision_basis` 开关从 `[C]` 章节内选项移到 `[S]` 机制与质量组**：判断依据是行动建议章的**章内内容增强**、不增删章节，放在章节显隐面板的 5.1 子项位置与语义不符。注册表 `group` 改 `mechanism`（`[S]` 新增 15 号，其后四项顺延 16~20），`chapter_registry` 的 `enable_action.sub_items` 清空（`[C]` 5.1 消失，章节内选项只剩智囊团 7.1/7.2，组内计数 3→2）。**报告产物与开关语义不变**（装配点/默认值 true/`_ms` 回退口径/缓存键都只读开关值，不看 group；`enable_action` 关闭时整章不生成，块仍不可见）；**入口与联动确实变了三处**——① `[C]` 5.1 子项消失，连带「父章关闭 → 子项置灰拒写入」的闸门一并消失（`handlers_report_chapters` 按 `entry.sub_items` 判父子），该开关现在可与章节状态独立改；② `GROUP_DOMAIN` 由 `report_content` 改 `presentation_mechanism`，Web 配置面板该项从「报告内容」段移到「呈现与机制」段（`web/config_edit.py` 按域分段）；③ `[S]` 编号 15~20 整体位移。
（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0（2026-11-04）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
