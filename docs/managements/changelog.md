# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.4]**（2026-11-18）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.5-dev] - 开发中（未发布）


（本次发布内容见下方归档索引）

- **发布归档兜底**：`apply_plan_archive` 在归档前检查「已完成（待发布归档）」区是否有关闭标记，缺标记即中止并点名 `plan-N`（此前漏标记会被静默跳过、完成项永久留在主台账）；配 3 条用例（`rf-1167`）。
- **LLM 成本台账纠正**：截断重试的两次真实计费调用用量改为**累加**（此前只留重试那次，被截断那次的花费凭空消失，重试彻底失败时更直接记为无用量）；配 2 条用例（`rf-1168`）。
- **性能门禁补 full 档**：`test-perf-report.py` 新增 Phase 4（full 全链路，LLM 已 mock），门禁改为 basic ≤60s **且** full ≤300s 双口径，填补「只卡 Excel 一段、full 退化无门槛」的缺口（`rf-1169`）。
- **max_tokens 偏低不再静默**：`llm_settings.json` 中 `max_tokens_*` 低于本版出厂默认时，加载期点名「当前值 / 默认值 / 代价（触顶会追加一次计费调用）」，不回落、不改写用户值；配 2 条用例（`rf-1170`）。
- **静默降级补痕**：并发档位配置读失败（`core/concurrency.py`）、交易日历/阈值回落（`core/data_freshness.py`）、逐品种 K 线取数失败（`report/_report_factor_metrics.py`）不再无声（`rf-1171`）。
- **长函数拆分（前 2 个）**：`write_html_report` 349→185 行（拆出 `_prepare_page_state` / `_build_template_context`，模板上下文装配点由源码扫描测试动态定位）、`prepare_report_data` 270→176 行（8 段数据准备各自成函数，perf span 名与调用顺序不变；`rf-1174`）。
- **去重（213 小时变更审计）**：`fetcher/fund.py` 两条会话缓存包装合并为 `_session_cached()`；`core/perf.py` 两条 JSONL 台账读取合并为 `_load_jsonl_records()`（`rf-1175`）。
- **V8 崩溃/退出死锁修复**：akshare 的交易日历与同花顺资金流会在函数内建 `py_mini_racer(V8)` 上下文，主进程内无论专用线程/全局锁/就地回收都实测段错误或退出死锁（原生崩溃，`try/except` 拦不住）；新增 `core/v8_subprocess.py` 把这两类取数放进子进程（白名单 + JSON 契约 + 超时杀进程 + 离线开关），父进程只收 records 并按源不可用降级，配 12 条用例与离线契约（`rf-1173`）。
- **持仓文件缺失提示可执行**：`_missing_holdings_hint()` 区分「目录不存在（旧配置残留，改 `holdings_dir`）」与「文件名对不上（列出目录现有 xlsx，改 `holdings_filename`）」两神情形；配 3 条用例（`rf-1172`）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.4（2026-11-12 ~ 2026-11-18）
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
