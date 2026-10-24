# 投资复盘助手 — 实现计划
> 文档版本：0.14.9-dev
> **编号源**：`plan-next = 201`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-200，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档记录项目的实现计划。已完成项迁入版本归档，此处只保留在办任务的最新状态。

**当前迭代**：在办 9 项——P2 7 项（**plan-92/93/185** 与配置体系重构剩余 4 轮 **plan-197~200**；plan-195/196 已实施待归档）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）。

> **命名纪律（强制）**：重构/新增的变量名、函数名、注释与文档表述必须与新章节语义相关（如 `position_relationship`/`portfolio_history_drawdown`/`style_factor`/`action`），**绝对禁止用任务编号命名**（F 系列、plan-N、rf-N 等）。任务编号仅在本表作链接锚点，不进入实现层。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

> 入选标准：立即可执行且价值/风险最高——数据完整性与费用风险、核心量化缺口与报告首屏呈现。

### P2 — 下一阶段就绪（满足条件即开工）

> 入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状与问题**：19 页签全为静态数字与文字，无条件格式（ColorScale/DataBar）/迷你图/openpyxl 原生图表——收益率高低、集中度偏离、偏离度优劣需逐格读数。

**动作**：对高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生能力）；先试点 2~3 个页签（持仓明细/量化指标/集中度），避免全表泛滥、样式膨胀与体积增长，试点认可后再扩。

#### `plan-93` 历史报告归档无索引导航

**现状与问题**：`html_save` 按日期归档到子目录但不生成 index；TUI 无「最近报告」入口；Web 有运行历史但 HTML 归档目录本身不可浏览——找上期报告只能翻文件系统。

**动作**：生成/刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；索引页不泄漏路径以外的本地信息，匿名化口径与报告一致。

#### `plan-185` 收益率指标缺口径标签，模型反复写错

**现状与问题**：模型对**收益口径**（累计收益率 / 持仓收益率 / 区间收益率 / 年化）判定不稳定——同一列数据被当成不同口径引用；事实校验只能把数值改对，**句意与修饰语仍可能挂错口径**（如把持仓收益率叙述成「近一年涨 X%」）。

**动作（标签已落地，余验收）**：进提示词的收益率一律带口径标签并附口径说明，`PROMPT_SCHEMA_VERSION` 并入模块指纹。验收看可观测量：连跑数轮完整报告，`perf_history.counters.fact_fix_total` 中收益率类修正数应显著低于基线 10 处；最近一轮已降到 3 处（智囊团 / 体检 0 处）。达标即收口归档。

#### `plan-195` Web 配置面契约（domains / labels / blocks）——已实施，待发布归档

**状态**：已实施（2026-10-24）。`web/config_edit.py` 下发 `domains`（五域 → 有序块清单，含 `features.<组键>`）+ `labels`/`descriptions`/`defaults`/`needs_hint` 元数据 + `logging`（六项，枚举/范围）+ `reference`（只读）；`static/web/main.js` 改为按域分区渲染、块 id → `BLOCK_RENDERERS` 分派、删除 `CONFIG_LABELS`/`ANON_LABELS`；共享编辑层新增 `logging.*` 六键写入（`write_logger_config`，与 TUI 日志面板同源）。机检载体 `src/test/unit/web/test_config_surface_contract.py`（17 例：块↔渲染器双向相等 / 元数据覆盖白名单全部可编辑键 / 无中文表 / 无 `innerHTML` 赋值 / 日志写入与非法值拒绝 / 参考面只读）。

#### `plan-196` Web 配置面交互与状态——已实施，待发布归档

**状态**：已实施（2026-10-24）。工具条（`共 N 项 · 已改 M 项`，基准 = 服务端 `defaults`）+ 关键词筛选（标签 / 说明 / 键名，空块与空域隐藏）+ 域导航 chips 与滚动高亮（`IntersectionObserver`，无该 API 时降级）+ 深链 `#domain-<key>`（与页签 hash 共存，`domain-` 前缀先切配置页再定位）+ 块计数 `N 项 · M 开` + ≤720px 单列断点。保存语义按契约 §4.5 分两类：即时保存失败回滚勾选并就地报错；显式保存（文本/数字）失败**保留输入值**供重试（原实现误回滚，本轮按契约修正）。机检载体 `src/test/unit/web/test_web_config_interaction.py`（17 例）。浏览器观感/可达性仍按 `docs/plan/web-browser-verification.md` 人工项复核。

#### `plan-197` 配置重构的文档与契约登记收口

**现状与问题**：配置重构跨 9 轮落地，手册与管理文档已逐轮同步，但仍缺一次整体收口——菜单/配置清单的全量抽检、两份设计契约档（`DESIGN.md` / `DESIGN-TUI.md`）的域标题与术语登记、台账计数刷新。

**动作**：手册全覆盖（起步 / 配置 / LLM 配置 / TUI 菜单 / Web 模式 / CLI 模式 / FAQ / README 界面描述）+ 管理文档（requirements 菜单与配置清单、technical 菜单表与配置矩阵、testplan、两份契约档）+ 台账（folders 目录树与统计、test-coverage 计数）；抽检三处键名/菜单键/项数与代码一致。验收：`check-doc-drift` / `check-doc-links` / `check-doc-traces` 全绿，契约档结构守卫用例绿。

#### `plan-198` 配置重构质量门禁全量

**现状与问题**：跨轮改动需在合入与发版两个闸口一次过——十守护、性能门禁、可移植性与格式零告警同时成立才算收敛。

**动作**：`test-runner.py --mode verify`（P1）+ 十守护全绿 + `test-perf-report.py --gate`（basic ≤60s，且本轮改动未使墙钟增长超 10%）+ `test-runner.py --mode portability`（`LC_ALL=C` + 隐式编码探针）+ `ruff check` / `ruff format --check` 零告警。

#### `plan-199` 配置重构发布编排

**现状与问题**：配置结构变更（v2 嵌套、日志与计价独立文件）需按「不做旧版兼容」策略发布，发布编排链路要能吃下这批变更并留下可追溯账。

**动作**：走通 `release.py` 全链——`prepare`（版本全链 + changelog / plan / review-findings / docs-plan 归档迁移）、`refresh`（bench + 覆盖率 + 统计同步）、`evolution --release`、`gate`（含前置断言）、`publish`（`--no-ff` 合并 + tag）、`devbump`。验收：gate 全绿、版本一致性 15 项全绿、tag 已推送、`master` 已合并、`devbump` 后开发版本号与文档版本头一致。

#### `plan-200` 配置稳态观测与回退演练

**现状与问题**：新配置结构下「加载失败 / 生成器重建 / 缓存首轮全量重算 / 结构不符」四类路径缺一次成体系的现场验证与观测接入，出问题时难判是配置错配还是程序缺陷。

**动作**：观测项接入现有日志与 `perf_history`（配置加载失败日志、日志配置生效记录、计价覆盖告警、指纹变化后的缓存命中率，不新增面板）；回退演练按「不做旧版兼容」验证重建路径。验收：① 制造非法配置 → 启动日志含文件名 + 键 + 原因且不静默回落；② 删除配置文件 → 生成器重建后启动正常（`llm_settings.json` / `logger.json` / `llm_pricing_ref.json` 逐一验证）；③ 清空缓存 → 首轮全量重算、第二轮起命中率恢复（数值记录在案）；④ 把配置目录整体置为非当前结构样本 → 明确拒绝并给出重建指引。

### P3 — 预期实施，有空时安排

> 入选标准：收益明确但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**现状与问题**：实验开关默认靠「真实数据验证后择机转正」，而该功能的账本积累慢、闭环缺真实数据验证；长期挂一个默认关闭的开关是纯维护成本。

**动作（判据与观测）**：以 `experiment_stats` 启用计数与账本结算数跨发布周期观察两条判据——① 启用次数停止增长（无真实使用），或 ② `data/state/decision_ledger.jsonl` 已结算样本 <10 条（折叠统计 `direction_accuracy` 无法给出可信命中率）**且已结算无达标趋势** → 撤销该实验功能（含 LLM 决策登记 `decision_llm_capture`、行动章复盘块注入与对应需求条目）；已结算 ≥10 条则据 doctor 账本概览评估转正。观测手段：`experiment_stats` 启用计数 + `doctor` 复盘账本概览。

**当前状态**：维持观察。启用 63 次、已结算 11 条（过 ≥10 下限），但 `directional_total = 9`、`sample_sufficient = False`，命中率样本不足；已结算条目全部来自确定性 `discipline` 载体，`expert_review`（LLM 建议）尚无到期样本。待结算 37 条（A 股 25 / 基金 12）满 5 个交易日后由 `settle_pending_decisions` 自动结算（A 股 kline 与场外基金 nav 已覆盖），`directional_total` 预计达 40+ 时评估转正；若仍 <20 且无新增，按撤销条件 ② 处置。

**单一事实位**：本实验的「条件—数据—态」结构化口径见 [technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)（决策跨期反思闭环行）；立项/转正/撤销时双方同步刷新。

**落地设计（转正后启动）**：按 [`decision-reflection-design.md`](../plan/decision-reflection-design.md) 四迭代执行（决策条目结构化 → 到期结算器 → doctor 概览增强 → 报告内反思块），以 Vibe-Trading `shadow_account`（extract→backtest→render）为参照；判据未过前不实施。与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。

### P4 — 实验候选（先决门槛未过，暂缓）

> 入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**现状与问题**：该模块的关联度/情绪判定属典型**窄判断**（批量、选项有限、需校准概率），恰是 Jev 类型化判定接口的适用场景；其余四个模块是长文生成，不适用。

**先决门槛（未过不接入）**：按 `docs/plan/jev-news-correlation-evaluation.md` 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标选取、预检收窄结论与预注册阈值见该文档 §2/§7。**未达阈值则归档为已评估未采纳。**

**待评测结论确认后再实施的部分**：见 `docs/plan/jev-news-correlation-design.md`。

**约束与红线**：① 不得作为用户可选的对话模型（该模型不生成文本）；② 不得做成「生成 + 判定」双供应商级联（无信息增量且多一个中间失败态）；③ 语料含真实持仓与新闻，冻结产物必须落 `docs/tmp/`（git 忽略），仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键须按开关注册表统一纪律登记，默认值保持 `chat` 使缺省行为逐字节不变。

**预估成本**：低（评测脚本 + 模板渲染 + 一个独立客户端模块）；**价值**：中（仅影响一个出厂默认关闭的模块，收益以「更稳的解析 + 可校准概率」为主，不以成本节约为卖点）。

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
