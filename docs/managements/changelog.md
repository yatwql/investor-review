# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.1]**（2026-10-22）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.2-dev] - 开发中（未发布）

### Changed

- **文档↔脚本清单覆盖机检化（`rf-811` 复核口径固化）**：新增 `unit/scripts/test_scripts_reference_coverage.py` 5 例，把「核对」变成可重跑的断言——① 一览覆盖全部顶层脚本（`.py`/`.sh`/`.ps1`，排除内部共享模块）；② 一览无虚指（指向的脚本必须存在）；③《开发者指南》「按域索引」点名的脚本必须存在（专防 `dev-verify.sh`/`web.sh` 这类幽灵条目）；④ 七域行各自至少点名一个条目；⑤ `scripts/_*/` 每个实现包须在参考文档点名（包清单从文件系统派生）。另补两例内容层检查：**详情小节覆盖**（每条一览条目须有加粗小节标题，薄垫片入白名单）与**旗标真实性**（两份文档提到的 `--flag` 必须能在 `scripts/**` 或 CLI 解析器的 AST 字面量里找到，外部工具旗标走白名单——防旗标改名后文档滞留）。反向验证：删一览行 / 写不存在的脚本 / 去掉包点名 / 注入幽灵旗标四处均能红。

- **开发者指南 / 辅助脚本参考核对梳理（`rf-811`）**：修正 4 类不一致——① 指南启动行去掉不存在的 `dev-verify.sh` / `web.sh`（改为实际包装脚本）；② 顶层脚本 `factor_zoo_eval.py` 补一览行 + 诊断类详情（三指标判据 / 六个子命令 / 四条纪律 / `_factor_zoo/`）；③ 拆包实现点名（`_perf_view` / `_test_redundancy` / `_factor_zoo` / `_doc_drift`）；④ CLI 子命令行补 `cassettes`。另把「60+ 个辅助脚本」改为非数字表述，避免计数漂移。复核口径：一览表 ↔ 实际顶层脚本双向零差集。

- **发布归档报错附期望格式（`rf-810`，补齐 `rf-808` 后半）**：`prepare` 的 changelog 归一步四类格式失败（缺开发段 / 缺归档章节 / 缺指针行 / 索引行改写失败）原本只报「格式与预期不符」，现统一附「期望：<样例行>」+「下一步：先跑 `release.py archive-init`」——指针行、索引行、开发段三种样例都写进提示，不翻代码即可改对。回归 3 例。

- **缓存操作五职责拆分（`rf-86`）**：`cache/operations.py` 739 → **489 行**，缓存刷新族（公共缓存 / 新闻 / 基金经理 / 扩展缓存，13 个私有函数）下沉 `cache/_cache_refresh.py`（282 行）；原模块只留数据类、更新编排、清理、统计与预热。依赖单向（编排 → 刷新），`CacheUpdateResult` 用 TYPE_CHECKING + 函数内延迟导入避免环；测试 patch 按调用点区分（直接调刷新器 → `_cache_refresh`，经 `update_basic_cache` → `operations`）。P3 登记表清空。

- **报告域两模块拆分（`rf-626`）**：`report/html_writer.py` 799 → **689 行**（数据状态块装配 → `html_writer_status.py`）；`analysis/rebalance.py` 751 → **243 行**（偏离度信号族 → `_rebalance_deviation.py`，含分类权重与误报保护、四个常量随迁）。依赖方向单向：渲染 → 状态装配、信号 → 分类/配置（后者函数内延迟导入，避免与入口 re-export 成环）；门面 re-export 保持导入面，测试 patch 目标按调用点改指。

- **功能开关注册表下沉（`rf-665`）**：`config/features.py` 840 → **574 行**，注册表与定义（分组常量 / `FeatureSwitchDef` / `feature_switch_registry` / 纯注册表视图 / `_FEATURE_FLAGS_DEFAULT` / `EXPERIMENT_ALL`）下沉 `config/_feature_registry.py`（298 行）；原模块只留运行时状态（features.json 覆写读写、合并键迁移、开关解析与日志）并 re-export 注册表符号，既有导入面与开关语义不变。注册表仍是唯一事实来源（`is` 同一对象，无副本）。

- **发布台账补 token 采集与统计（`plan-171`）**：`logs/release.jsonl` 每行新增 `session_usage`（agent 会话累计 in/out/cache read/cache write/total/cost，取自 `PI_SESSION_FILE` 的 assistant 消息 + 非消息用量 + compaction，与 pi 统计同口径；非 agent 环境省略、旧行形状不变），命令尾行打印「本次发布累计 token」，窗口以「上一次 devbump」为界、跨会话按正增量分段累加；同时记录**执行环境身份**（`agent`：provider/model/thinking/session_id，取自 `PI_PROVIDER`/`PI_MODEL`/`PI_REASONING_LEVEL`/`PI_SESSION_ID`，非 agent 环境省略）并打印「执行环境：provider/model（thinking=…）」。采集全容错不阻断发布。回归 6 + 4 例。

- **近 36 小时变更的技术债核查与修复**：① 拆分时 `re-export` 块被追加在代码下方（`# noqa: E402` 豁免
  掩盖了「导入不在顶部」）——5 个文件（`llm/api_base`、`config/_validation`、`report/holdings_detail_sheet`、
  `report/fund_performance`、`analysis/prosperity_scoring`）的 re-export 归位到 import 区，豁免减为 `F401`；
  ② 审计出 **3 处拆分后静默失效的打桩**（`_spawn/_collect_health_checks` 的调用已随生成路径迁到
  `_generation_both` / `_generation_full`，测试仍 patch 门面 → 实际未拦截）：basic 分支改为从定义处
  `_report_health` 导入、三路径统一打桩到定义处，`test_run_integrity` 与 orchestrator 生成报告测试同步。
  核查结论：死符号 0（新模块私有符号全仓有引用）、完全同体函数 0、377 个模块导入全通过且无反向依赖、
  门面 re-export 无死面。

- **模块内拆分收尾（`rf-773` 剩余 5 个）**：`llm/api_base.py` 770 → **501**（响应解析 → `_api_responses.py`）、`config/_validation.py` 723 → **119**（标量/章节/LLM 三域 + 共用原语 `_validation_common.py`）、`report/holdings_detail_sheet.py` 716 → **171**（分区块写入器 → `_holdings_detail_blocks.py`）、`analysis/prosperity_scoring.py` 711 → **476**（输入与权重 → `_prosperity_inputs.py`）、`providers/news_dedup_rules.py` 710 → **331**（纯词表 → `_news_dedup_tables.py`）。至此 rf-773 的 8 个模块全部拆完（前批 3 个已随 v0.14.1 发布）；门面 re-export 保持导入面，区块注册表与章节-区块矩阵的载体列同步更新。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0（2026-10-21）
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
