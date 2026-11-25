# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.6]**（2026-11-19）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.7-dev] - 开发中（未发布）


（本次发布内容见下方归档索引）

- **第三批故障分支补齐（Jinja 缓存与过滤器 · 中断收口 · 调仓产物）**：3 个模块补 53 条用例——`report/html_jinja_env`（字节码缓存读/写/清理失败一律降级为「下次再编译」；过滤器遇 None/非数值/对象输出 `--`；匿名代码折叠上下文未命中保持原值）、`report/run_integrity`（中断收口五步各自 best-effort：预清扫、删临时文件、登记去重、落 status=interrupted、组装提示、收敛健康检查单步失败不影响其余步骤与异常传播；写失败提示带目标路径）、`report/whatif_writer`（匿名模式缺省解析与 off 恒等零拷贝、派生容器改名、最新/归档写失败抛带路径 OSError、归档清理失败仅告警）。三模块 → 100%，单位套件行覆盖率 95.0% → 95.1%。
- **第二批故障分支补齐（TUI 诊断/状态条 · 天天基金 HTTP · 健康检查 · 新闻页签降级 · 缓存目录权限）**：6 个模块补 68 条用例——`tui/handlers_log`（无效键留守面板 / 配置读失败 / 数值字段应为整数 / 窄档健康历史两行渲染 / 自检执行异常指向日志）、`tui/progress`（状态条启用判据、绘制失败只留 DEBUG 不打断进度流、落地行挂起-恢复序列、错误汇总清空）、`providers/tiantian_base`（超时 / 429 状态码 / 连接错误 / JS 转义解析失败各归 None，连接超时严于总超时）、`report/_report_health`（启动失败、结果非 list、条目非 dict、收集异常均不阻断报告）、`report/excel_news_warning`（可选模块缺失与取数失败仍占位写页签并留 [ERR]）、`cache/_paths`（权限过宽收紧到 0o700，chmod/makedirs 失败降级；`INVEST_CACHE_DIR` 覆盖解析）。上述 6 模块 76%→100%，单位套件行覆盖率 94.8% → 95.0%。
- **缓存清理畸形时间戳修复 + 故障分支补齐**：`cache/_cleanup.clean_sensitive` 的时间戳未做类型容错，`_ts` 为字符串/None 时抛 `TypeError` 并（被导入期兜底吞掉）中断整轮敏感缓存清理，盘上其余过期持仓/穿透/基金缓存全部漏清；抽出共享 `_payload_ts()` 让清理与敏感清理两入口同口径，敏感性归档按「无法判定年龄 = 极旧」清理且单文件畸形不再打断后续扫描（`rf-1189`）。另补齐 5 个模块的故障与注册分支（78 条用例）：`cache/_store`（目录不可建/临时文件失败/目录被外删重试/清除失败）、`cache/_cleanup`（目录不可读/畸形 `_ts`/gz 与 json 同口径/自动清理兜底）、`providers/news_dedup_anchor_store`（分片读失败跳过/追加失败归 False/压缩自检拒绝/ts 解析）、`report/_run_scope`（九步观测复位各自失败均不阻断 + 单轮复用并发/跨轮失效）、`report/pipeline_data_builder`（未知键告警自注册/类型不符只告警/prep 缺省值/merge 四路径），单位套件行覆盖率 94.7% → 94.8%，上述 5 模块 92% → 99%（3 个 100%）。

- **修复 llm_settings 运行约束静默丢失**：`config/_llm_schema.apply_flat_updates` 的 runtime 扁平键查表按「字段名」而不是「扁平键」建反向表——`llm_max_concurrency` / `llm_max_thinking_concurrency` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` 写回时落到顶层、v2 `runtime` 段不更新，随后 `flatten()` 用 runtime 段的值压过顶层透传 → 用户在配置面板/编辑层改的并发、重试延后、时间预算设置**静默丢失**（`llm_settings.json` 缺失走默认兜底、或同批含 `debate`/`fact_check` 更新时走该路径即触发）；改按扁平键建反向表，配 12 条落点敏感回归（`runtime` 段落值 + 顶层无扁平键残留 + 六个字段从 `RUNTIME_FIELDS` 参数化派生 + 写盘级解析残留 JSON），并修掉既有「只经 `flatten()` 回读」的假绿往返用例（`rf-1188`）。
- **发布台账按版本汇总**：新增只读脚本 `scripts/probe-release-ledger.py`（`--last N` / `--version` / `--json` / `-v`），按版本切段输出每版墙钟、分步耗时、会话 token 增量与失败步；token 列口径明确标注为「相邻台账行之间的会话增量」，不是发布命令本身的成本；配 11 条用例（`rf-1187`）。
- **覆盖率接入与测试缺口补齐**：`requirements.txt` 增 `pytest-cov`（此前项目只有测试规模快照、没有行覆盖率数据）；据首轮实测（`src/test/unit`，90.7%）补齐 9 个薄弱文件的分支覆盖——`report/excel_module_loader`（53.9%→100%）、`llm/_debate_router`（60.0%→100%）、`report/excel_fund_deep_analysis`（28.9%→97.4%）、`providers/tiantian_nav`（50.7%→94.0%）、`tui/handlers_config`（58.2%→96.3%）、`tui/tui_keys`（61.5%→91.9%）、`tui/handlers_holdings`（64.7%→93.6%）、`web/server`（59.5%→83.5%）、`report/_report_factor_metrics`（50.9%→88.3%），整体 90.7%→92.1%，`<60%` 文件由 6 个降为 0 个；新增 9 个测试文件共 184 条用例，聚焦降级链路（ImportError 逐模块兜底 / 数据源故障 vs 数据不足 / 辩论两级回退清空容器）、序列拆包与 UTF-8 解码、持仓录入撤销与保存防线。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.6（2026-11-12 ~ 2026-11-19）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
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
