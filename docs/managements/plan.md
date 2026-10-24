# 投资复盘助手 — 实现计划
> 文档版本：0.15.6-dev
> **编号源**：`plan-next = 221`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-220，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 10 项——P1 1 项（**plan-219**）、P2 7 项（**plan-92/93/185/210/211/212/220**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P0 — 最高优先（立即执行）

当前无 P0 项（入选标准：直接影响用户可见行为且已验证的缺陷）。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

#### `plan-219` 缓存 TTL 分层收敛（分析完成，待评审实施）

**问题**：同一缓存条目的有效期由多层合成（注册表默认 + `config.json` 全量副本 + 读侧映射表 + 未注册兜底 + 交易时段特例 + 按 key 抖动），已造成两类真实事故：① `self_review`/`holding_change` 读侧与清理侧取值不同（清理先删、读侧仍认为有效 → 白重算）；② 默认值被抄进 `config.json`，改默认值后运行时无感（本次改 4h 即撞）。另发现潜在第三类：抖动只应用于读侧，清理按 1.0×TTL 判定 → 约一半 key 会被最多提前 15% 过期删除。

**分析**：见 [`cache-ttl-layering.md`](../plan/cache-ttl-layering.md)（分层现状、必要性与方案 A/B/C 比较、三个次级口径 D1~D3、影响面与验收）。

**建议**：方案 C——注册表是唯一默认来源，`config.json` 仅存**稀疏覆盖**（模板不写默认值块）；清理侧改用与读侧同一抖动因子；`cache_ttl` 未注册键告警。

**已实施（方案 C + D1 + D2，D3 不做）**：生成配置的 `cache_ttl` 改为空对象（默认值唯一来源 = 注册表）；`cleanup_expired` 按剥离版本戳后的逻辑键查类型并调用 `get_ttl(type, logical_key)`，与读侧同一抖动因子（顺带修好精确键映射：此前带版本戳查表必 miss）；`cache_ttl` 未注册键告警（不自动删）；用户配置中的死键 `fund_overlap` 已删除。契约由 `src/test/unit/cache/test_ttl_alignment.py`（7 例）与 `test_llm_cache_ttl_single_source.py`（17 例）锁定。

**验收记录**：`cleanup_expired(dry_run=True)` 对现有 517 个缓存文件预览 23 个过期（与历史量级一致，拆分见 `logs/app.log` 的 DEBUG 明细）；运行时 `config.json` 的 `cache_ttl` 已收敛为空对象（等于默认值的 37 个键全部移除，行为不变）。

**深度审计追加（同批修复）**：① 移除按 key 的 TTL 抖动——抖动只在部分读点生效，而 LLM 读侧（skeleton/批量/辩论/预检）全都不传 key，导致清理侧按抖动值提前删除（最多 15% TTL）；TTL 与 key 无关后两侧天然同值。② `bond_yield`/`fund_manager` 的同值重复 TTL 常量改为直读注册表；`index`/`index_valuation`/`chain` 的宽松常量补注为「陈旧兜底读」口径；`financial_report` 的两处负缓存常量注为模块自有策略。

**剩余**：① 观察一轮真实报告，核对自检/归因在 TTL 内的第二轮报告均直接命中（日志无「无此缓存文件」）；② 文档里 TTL 数字分散在 5 份（how-to-config/technical/llm-technical/datasource/faq），目前 `check-doc-drift` 只校验前两份的 LLM 行——扩展到 datasource/faq 的防漂移守卫另立任务。

**不做**：不改注册表结构、不改 `get_ttl` 优先级顺序、不自动删除用户既有 config 键。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生）；先试点持仓明细 / 量化指标 / 集中度 2~3 个页签，认可后再扩。

#### `plan-93` 历史报告归档无索引导航

**现状**：HTML 按日期归档到子目录但不生成索引；TUI 无「最近报告」入口；Web 运行历史不含归档目录。
**动作**：生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；只列路径信息，匿名化口径与报告一致。

#### `plan-185` 收益率指标缺口径标签，模型反复写错

**现状**：口径标签已落地（`llm/rate_caliber.py` 唯一声明点，并入 `PROMPT_SCHEMA_VERSION` 指纹），余验收——事实校验只改数值，句意与修饰语仍可能挂错口径。
**验收**：`perf_history.counters.fact_fix_total` 连续若干轮稳定 ≤3 处即归档。

#### `plan-210` 报告重复运行耗时优化（LLM / 新闻）

**现状**：完整报告（LLM 开启）`LLM+新闻` 占大头，专家复盘为主项；新闻缓存 900s；专家/健康指纹含市值盈亏，行情变化即失效（不跨报告复用）。已落地：新闻去重比较串缓存 + 字符多重集上界预筛（判定等价的省算）、事件窗 bars/index 同批 memo、历史取数单轮窗口复用与空结果短路、财报章节探测 404 负缓存（12h）与标的级正文缺失负缓存（6h）。
**剩余**：LLM 实际调用下连跑两份同条件报告，量化第二份的 `LLM+新闻` 降幅（含缓存命中与数据源波动的拆分）。
**验收**：第二份 `LLM+新闻` 下降 ≥50%，或专家复盘命中应用缓存；报告内容与首次一致（除生成时间）；补缓存键失效/命中的回归用例。

#### `plan-211` 数据源降级与告警分级（行业资金流向 / K 线）

**现状**：K 线风控页逐代码日志 DEBUG、源失败计 registry、熔断汇总保留 WARNING；行业资金流向暴露公开失败状态访问器，报告层经 `mark_data_unavailable` 写入 DegradationTracker，数据源矩阵显示不可用；失败后进 5 分钟负缓存（同会话后续报告直接按不可用降级，状态仍如实上报）；hithink 的 A 股历史无效请求由「单轮窗口复用 + 空结果短路」处理（结构性不覆盖的槽位在本轮直接跳过）。
**剩余**：同条件复测 `warnings_count` 与 `Unknown thscode`；行业资金流向备用源评估（负缓存只减少重复代价，不补数据）。
**不做**：不伪造数据、不把外部源失败静默当成功；不扩大年报/财报抓取范围。
**验收**：同条件报告 `warnings_count` ≤10 且无 `Unknown thscode` 无效请求；行业资金流向有明确可用/不可用状态；补数据源路由与降级回归。

#### `plan-212` 报告级 LLM 缓存状态隔离与指纹审计

**已落地**：`report/_run_scope.py` 报告边界（清本轮降级事件、重置自检载体、取用量基线）；`_usage_delta` 按报告记账；`fingerprint_components` / `diff_fingerprint_components` 组件级审计（变化定位恒开打 INFO，与生产指纹同口径）；数据质量块只统计失败事件；缓存未命中/跳过读 INFO 归因；提示词、模型、精简模式并入指纹；预检键与写侧同源。设计见 [`llm-cache-state-isolation.md`](../plan/llm-cache-state-isolation.md)。
**不做**：不为命中缓存忽略行情/指数/数据质量/账本变化；不跨日缓存；不改变现有缓存 TTL。
**剩余**：实跑验收——同非交易日、同持仓/指数/新闻连跑两份，第二份基础模块命中且无指纹组件误变。
**验收**：第二份基础模块命中；perf LLM token/call_count 为单次报告值；无上一轮 degradation/self_review 残留。

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

- [`archived_plan.0.15.x.md`](../archive/v0.15.x/archived_plan.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
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
