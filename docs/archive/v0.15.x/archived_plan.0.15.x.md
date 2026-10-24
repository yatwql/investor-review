# 计划归档 — v0.15.x

> 归档时间：2026-10-24（v0.15.0 发布，本系列首份）；2026-10-24 v0.15.0 本批原表搬运；2026-10-24 v0.15.1 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.15.x 开发期完成项（含 v0.15.1）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## ✅ `plan-195` Web 配置面契约（domains / labels / blocks）——已实施，待发布归档

服务端下发 `domains`（五域 → 有序块清单）与 `labels`/`descriptions`/`defaults`/`needs_hint` 元数据、`logging`、`reference`；前端按域渲染 + 块渲染器分派，零中文表。机检：`test_config_surface_contract`（17 例）；记录见 changelog 配置重构第 10 轮。

## ✅ `plan-196` Web 配置面交互与状态——已实施，待发布归档

工具条统计（基准 = 服务端 `defaults`）、关键词筛选、域导航与 `#domain-<key>` 深链、块计数、窄屏单列；保存语义分即时（失败回滚）与显式（失败保留输入）两类。机检：`test_web_config_interaction`（17 例）；记录见 changelog 配置重构第 11 轮。

## ✅ `plan-197` 配置重构的文档与契约登记收口——已实施，待发布归档

手册与管理文档全量对齐当前结构（主菜单 14 项四组、Web 五域分区、`[G]` 七项四组、`[D]` 四项），抽检 `[D]`/`[G]`/`[S]`+`[C]` 三处与代码逐字一致；契约档结构守卫绿。记录见 changelog 配置重构第 12 轮。

## ✅ `plan-198` 配置重构质量门禁全量——已实施，待发布归档

五道闸口全绿：`verify` 11318 通过 / 0 失败、十守护零 finding、性能门禁 basic **0.48s ≤ 60s**、`portability` 2 探针通过（`LC_ALL=C` + 隐式编码严格档）、`ruff check` / `format --check` 零告警。本轮修正两处真实缺陷：计价懒加载覆盖显式重载（`rf-837`）、`test_json_comments` 子进程缺显式编码（portability 探针拦下）。记录见 changelog。

## `plan-199` 配置重构发布编排——已完成，待发布归档

**状态**：v0.15.0 已走通 `release.py` 全链（`prepare` → `refresh` → `evolution --release` → `gate` → `publish` → `devbump`）；gate 全绿、版本一致性 15 项全绿、tag 已推送、master 已合并、devbump 后版本头一致。配置体系设计文档随本版迁入 `docs/archive/v0.15.x/config-rework/`。

## `plan-200` 配置稳态观测与回退演练——已完成，待发布归档

**状态**：四类路径（非法配置 / 删除重建 / 缓存首轮重算 / 非当前结构拒绝）由 `test_config_resilience_contract`（10 例，`tmp_path` 隔离）机检；观测复用现有日志与 `perf_history`，未新增面板。记录见 changelog。

## `plan-201` 事实校验评估函数参数收敛（技术债）——已完成，待发布归档

**状态**：`_evaluate_percent_value` 的 22 参收进冻结 dataclass `PercentContext`，签名收敛为 `_evaluate_percent(ctx)`；行为零变化（`src/test/unit/llm` 1326 例）。记录见 changelog。

## `plan-202` 演示截图生成器入库——已完成，待发布归档

**状态**：入口 `scripts/make-screenshots.py`（`demo` / `report` / `tui` / `web`）+ 实现包 `scripts/_screenshots/`；16 例回归；参考文档与目录树三处登记。记录见 changelog。

## `plan-207` 清理旧配置形参兼容——已完成，待发布归档

**状态**：移除 10 个功能开关访问器（`is_enable_data_quality` / `candidate_compare` / `stock_fundamentals` / `market_sentiment` / `cost_lots` / `valuation_percentile` / `market_temperature` / `industry_beta` / `fund_purchase_limit` / `cost_position`）的 `config` 形参——该参数在功能开关迁入 `features.json` 后已不参与取值，仅为旧调用签名保留；同步更新 26 处调用点与测试，删除「旧 config 入参被忽略」的兼容用例。保留当前规格内的降级回退（快照缺市值按 R-EVO-02 回退成本口径、LLM flat 单凭据模式）——它们不是旧数据兼容。

## `plan-206` 报告运行观测三项整改（锚点开销 / 归因粒度 / full 提示）——已完成，待发布归档

**状态**：按最近一次真实运行（44.4s 管线，去重锚点占 18.5s）落地三项——① **rf-858** 锚点**采集保持默认开启**、写侧改为纯追加（不读旧文件；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关），跨轮重复交给校准工具按键去重，39MB 文件的加载/压缩移出报告主流程（采集、诊断数据持续积累，报告零读取开销）；② **rf-859** `perf_history.breakdown` 补数据准备九项与新闻源抓取/去重与关联/锚点维护/事件窗装配子计时；③ **rf-860** 新增 `llm_report_unavailable_reason()`，full 在 LLM 未配置或章节全关时显式提示「按不含 LLM 内容生成（full 等同 both）」。回归覆盖锚点默认采集/批内去重/跨轮由校准去重、新闻子阶段、LLM 不可用判定与 full 提示；评估默认顺带压缩锚点（`--no-compact` 关闭）；文档同步技术设计、需求（R-DATA-09 / R-PERF-09）、脚本参考与 CLI/TUI 手册。

## `plan-205` CLI 配置面补齐（config 子命令 + 章节/匿名化一次性覆写）——已完成，待发布归档

**状态**：CLI 补齐与 TUI/Web 配置面同源的命令行入口——新增 `config list/get/set`（白名单 + 校验 + `.bak`，复用 `config/edit_ops.py`；`--dry-run` 只校验；调度四个字段走严格校验）与全局 `--chapter KEY=on|off` / `--anonymize MODE`（进程内覆写，不写盘，覆盖 `config.json` / `enabled_llm.*` / features 三类来源）。`--chapter` 的运行时叠加层为 `config/_runtime_overrides.py`，`get_config()` / `get_llm_config()` 返回前叠加；scheduler 归一化/严格校验上收 `config/_scheduler.py`（Web 面板与 CLI 共用）。报告追问 `[Q]` 按决策不提供 CLI 入口（对话式交互不适合命令行）。文档同步 CLI 手册 §2/§10.1/§14、配置手册与脚本参考。

## `plan-204` 测试用例全量审计与整改——已完成，待发布归档

**状态**：扫描 586 个测试文件 / 11,111 个 `def test_` 定义，机检覆盖「完全重复、死用例、无断言、自证、弱 mock」之外的四类人工判据（自证式用例、双结果放行、弱断言、命名与内容不一致）；整改 23 例（1 例重复合并）：安全基线 3 例自证式改为触生产（缓存写入器 / LLM 源码静态守卫 / HTML 模板扫描）、文件系统边缘 4 例双结果放行改为按契约断言、配置崩溃清理 1 例补 `assertRaises`、弱断言 11 例补足语义、启动向导 2 例合并、2 处死变量清理。记录见 changelog / 台账 rf-851~rf-855。

## `plan-203` 发布流程四处改进（失败前移 / 台账自证 / 预检前移 / 记账补全）——已完成，待发布归档

**状态**：日志动线进 dev-verify + 打点矩阵自证；bench 场景档前置；台账失败写 `failure`；`check` 预演 changelog 派生；publish 分段计时并在 gate 戳失效时点名改动的代码文件；`[C]` 无效编号提示由注册表派生。回归 9 例。记录见 changelog。
