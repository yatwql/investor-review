# 投资复盘助手 — 实现计划
> 文档版本：0.15.8-dev
> **编号源**：`plan-next = 229`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-228，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 5 项——P2 2 项（**plan-92/93**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）、P1 1 项观测挂账（**plan-227** 待一周数据后定值，观测部分已完成）。

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

**验收**：新增缓存契约测试四面——`test_ttl_business_matrix.py`（8 时段 × 7 类型 × 覆盖层矩阵 + 读/清理同源 + 同日两次报告/收盘后/负缓存/LLM 边界）、`test_price_freshness_gate.py`（收盘时点门禁：盘中价盘后不得当收盘价、QDII T-1、盘后写入可复用）、`test_cache_stamp_and_cleanup.py`（非当前版本戳不可读但仍按类型 TTL 清理、LLM 逐类型 TTL 不退化为默认）、`test_cache_edge.py::TestGetTTLIntraday` + `test_ttl_alignment.py::TestIntradayAndNegativeCacheTTL`（退役键无扩权、覆盖提示仅一次、负缓存 12h/6h 判定）；`technical.md` TTL 流程、`datasource.md` 负缓存表与盘中口径、`requirements.md`/`how-to-config.md` 配置表同步。

#### `plan-226` 财报索引与财务指标 TTL 对齐披露节奏（来源 rf-876）✅

**完成**：`report`（索引/章节清单）与 `fin_indicator`（财务指标）30d → **1d**，`dividend` 30d → **7d**；`report_doc`（正文）保持 30d——正文按 `doc_id` 不可变，索引负责"发现新披露"、正文负责"取一次即定型"。

**依据**：两类都是 symbol 级缓存键，30d 窗口下新一期财报披露后报告可能整月沿用上一期口径；TUI `[C]` 基础缓存刷新只在人为操作时生效，定时运行无兜底。配额影响有界——每标的每天至多 1 次索引请求，20 标的 ≈ 免费档日配额 8191 的 0.24%，且报告次数不放大（TTL 而非调用数决定）。

**验收**：`test_disclosure_cache_cadence.py` 14 例——日频/月频/周频节奏、跨 TTL 边界"新披露次日可见"、同日四份报告共用一份索引（不重复打源）、巨潮备源与主源同组、清理侧同 TTL、日请求量 = 标的数（用真实缓存行为验证，非算术断言）；`technical.md` 缓存表与财报段、`datasource.md` 披露类节奏表同步。

#### `plan-227` LLM 模块 TTL 取值决策所需观测（来源 rf-879）✅

**完成（只加观测，未改 TTL 值）**：缓存未命中时记录**重算原因**——`forced`（重新生成/模块缓存关闭）/ `fingerprint_changed`（内容变了）/ `ttl_expired`（内容没变、纯到点）。归因按模块依赖的指纹组件判定（`_MODULE_FINGERPRINT_COMPONENTS`，只用于归因、不参与键构造）；原因按次数聚合写入 perf 的 `llm.recompute_reasons`（逐模块明细亦保留，全命中时不写该字段），预检摘要行同步显示分布。

**为什么先观测**：4h 是否放宽取决于「`ttl_expired` 在未命中里的占比」——占比高说明放宽能省钱且不损时效；占比低说明重算都是内容真变了，放宽无意义。该分布只能靠真实运行积累，不能凭推断。

**验收**：`test_cache_recompute_attribution.py` 18 例——三分归因口径、模块→组件映射只认真正影响该模块的组件、观测是纯旁路（命中判定/调用次数不变）、预检摘要带原因分布、perf 落盘与"全命中不写字段"。**后续动作**：积累约一周数据后按 `ttl_expired` 占比决定是否把内容型模块放到 8~12h（`news_correlation` 维持 ≤4h）。

#### `plan-228` 决策/信号账本保留上限（来源 rf-880）✅

**完成**：`jsonl_store` 新增 `prune_jsonl_by_age`（按龄裁剪 + 可选 `keep` 谓词），决策账本与信号账本追加后按 **730 天**裁剪。决策账本对 `settlement` 事件**永久保留**（结算样本是跨期反思的核心证据，`plan-70` 依赖它）。

**为什么按龄而非按行数**：账本一行一份状态，按行数截断会把最旧的已结算样本一起裁掉；「超出保留期的历史不参与反思」这一语义只能靠按龄表达。该边界已写入原语 docstring（业务账本禁止使用 `max_lines`），由文档承载而非口头约定。

**其他边界**：坏行不裁（不得替读取侧吞掉损坏证据）；缺日期字段的行保留（宁留不误删）；`retention_days<=0` 关闭裁剪；信号账本幂等去重不受裁剪影响。

**验收**：`test_ledger_retention.py` 12 例——窗口内外、`keep` 保护、坏行保留、缺字段保留、零值关闭、两本账的集成写入路径与幂等性。

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
