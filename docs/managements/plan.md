# 投资复盘助手 — 实现计划
> 文档版本：0.15.1-dev
> **编号源**：`plan-next = 209`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-208，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 7 项——P2 5 项（**plan-92/93/185/199/208**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）。

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

**现状**：口径标签已落地（`llm/rate_caliber.py` 唯一声明点，并入 `PROMPT_SCHEMA_VERSION` 指纹），**余验收**——事实校验只把数值改对，句意与修饰语仍可能挂错口径。
**验收**：`perf_history.counters.fact_fix_total` 连续若干轮稳定 ≤3 处即归档。

#### `plan-199` 配置重构发布编排

**现状**：配置结构（v2 嵌套、日志与计价独立文件）按「不做旧版兼容」策略发布，需留下可追溯台账。
**动作**：走通 `release.py` 全链——`prepare`、`refresh`、`evolution --release`、`gate`、`publish`、`devbump`。验收：gate 全绿、版本一致性 15 项全绿、tag 已推送、master 已合并、devbump 后版本头一致。

#### `plan-200` 配置稳态观测与回退演练——已完成，待发布归档

**状态**：四类路径（非法配置 / 删除重建 / 缓存首轮重算 / 非当前结构拒绝）由 `test_config_resilience_contract`（10 例，`tmp_path` 隔离）机检；观测复用现有日志与 `perf_history`，未新增面板。记录见 changelog。

#### `plan-201` 事实校验评估函数参数收敛（技术债）——已完成，待发布归档

**状态**：`_evaluate_percent_value` 的 22 参收进冻结 dataclass `PercentContext`，签名收敛为 `_evaluate_percent(ctx)`；行为零变化（`src/test/unit/llm` 1326 例）。记录见 changelog。

#### `plan-202` 演示截图生成器入库——已完成，待发布归档

**状态**：入口 `scripts/make-screenshots.py`（`demo` / `report` / `tui` / `web`）+ 实现包 `scripts/_screenshots/`；16 例回归；参考文档与目录树三处登记。记录见 changelog。

#### `plan-208` 跨模块导入面重命名（去兼容 re-export）——待办

**现状**：历次拆分留下 23 行「兼容既有导入面」类转发（17 文件）、103 行 `noqa: F401`（41 文件），`config/__init__.py` 的 `__all__` 60 项中仍含 22 个私有名；另有 31 处跨包私有导入、995 处函数内局部导入、6 处动态导入与 7 组包级候选环（详见分析稿基线表）。同一符号存在实现模块 / 转发模块 / 包门面多条导入路径，测试 patch 点可能与 owner 不一致。

**动作**：按 [`import-surface-rename.md`](../plan/import-surface-rename.md) 先建立「符号 → 唯一 owner」清单，再分四阶段（config → core/cache → analysis/report/llm/web → 测试与文档）收窄公共面、更新调用点与 patch 点、删除兼容转发；护栏与验收口径见该分析稿 §7。

**不做**：不修改运行时行为、配置/缓存/数据格式；不借重命名调整模块职责。

**前置**：分析稿见 [`import-surface-rename.md`](../plan/import-surface-rename.md)；待 owner 表与阶段顺序评审后实施。

#### `plan-207` 清理旧配置形参兼容——已完成，待发布归档

**状态**：移除 10 个功能开关访问器（`is_enable_data_quality` / `candidate_compare` / `stock_fundamentals` / `market_sentiment` / `cost_lots` / `valuation_percentile` / `market_temperature` / `industry_beta` / `fund_purchase_limit` / `cost_position`）的 `config` 形参——该参数在功能开关迁入 `features.json` 后已不参与取值，仅为旧调用签名保留；同步更新 26 处调用点与测试，删除「旧 config 入参被忽略」的兼容用例。保留当前规格内的降级回退（快照缺市值按 R-EVO-02 回退成本口径、LLM flat 单凭据模式）——它们不是旧数据兼容。

#### `plan-206` 报告运行观测三项整改（锚点开销 / 归因粒度 / full 提示）——已完成，待发布归档

**状态**：按最近一次真实运行（44.4s 管线，去重锚点占 18.5s）落地三项——① **rf-858** 锚点**采集保持默认开启**、写侧改为纯追加（不读旧文件；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关），跨轮重复交给校准工具按键去重，39MB 文件的加载/压缩移出报告主流程（采集、诊断数据持续积累，报告零读取开销）；② **rf-859** `perf_history.breakdown` 补数据准备九项与新闻源抓取/去重与关联/锚点维护/事件窗装配子计时；③ **rf-860** 新增 `llm_report_unavailable_reason()`，full 在 LLM 未配置或章节全关时显式提示「按不含 LLM 内容生成（full 等同 both）」。回归覆盖锚点默认采集/批内去重/跨轮由校准去重、新闻子阶段、LLM 不可用判定与 full 提示；评估默认顺带压缩锚点（`--no-compact` 关闭）；文档同步技术设计、需求（R-DATA-09 / R-PERF-09）、脚本参考与 CLI/TUI 手册。

#### `plan-205` CLI 配置面补齐（config 子命令 + 章节/匿名化一次性覆写）——已完成，待发布归档

**状态**：CLI 补齐与 TUI/Web 配置面同源的命令行入口——新增 `config list/get/set`（白名单 + 校验 + `.bak`，复用 `config/edit_ops.py`；`--dry-run` 只校验；调度四个字段走严格校验）与全局 `--chapter KEY=on|off` / `--anonymize MODE`（进程内覆写，不写盘，覆盖 `config.json` / `enabled_llm.*` / features 三类来源）。`--chapter` 的运行时叠加层为 `config/_runtime_overrides.py`，`get_config()` / `get_llm_config()` 返回前叠加；scheduler 归一化/严格校验上收 `config/_scheduler.py`（Web 面板与 CLI 共用）。报告追问 `[Q]` 按决策不提供 CLI 入口（对话式交互不适合命令行）。文档同步 CLI 手册 §2/§10.1/§14、配置手册与脚本参考。

#### `plan-204` 测试用例全量审计与整改——已完成，待发布归档

**状态**：扫描 586 个测试文件 / 11,111 个 `def test_` 定义，机检覆盖「完全重复、死用例、无断言、自证、弱 mock」之外的四类人工判据（自证式用例、双结果放行、弱断言、命名与内容不一致）；整改 23 例（1 例重复合并）：安全基线 3 例自证式改为触生产（缓存写入器 / LLM 源码静态守卫 / HTML 模板扫描）、文件系统边缘 4 例双结果放行改为按契约断言、配置崩溃清理 1 例补 `assertRaises`、弱断言 11 例补足语义、启动向导 2 例合并、2 处死变量清理。记录见 changelog / 台账 rf-851~rf-855。

#### `plan-203` 发布流程四处改进（失败前移 / 台账自证 / 预检前移 / 记账补全）——已完成，待发布归档

**状态**：日志动线进 dev-verify + 打点矩阵自证；bench 场景档前置；台账失败写 `failure`；`check` 预演 changelog 派生；publish 分段计时并在 gate 戳失效时点名改动的代码文件；`[C]` 无效编号提示由注册表派生。回归 9 例。记录见 changelog。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**状态**：维持观察——启用 67 次、账本已结算 16 条 / 待结算 42 条；`directional_total = 12`、命中率 75%、样本仍不足。
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
