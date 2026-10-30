# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.12]**（2026-10-30）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.13-dev] - 开发中（未发布）

### 变更

- 新增 `core/log_dedupe.py`：同 key 时间窗内折叠重复日志（重复降到 DEBUG），接入行业批量就绪 / 事件窗装配 / 新闻关联三处，单份报告的重复装配不再刷屏（rf-976）。
- `perf` 阶段汇总行附带最慢三项子耗时（如 `[perf] LLM+新闻: 94.3s（智囊团深度复盘 75.7s / 持仓体检报告 40.2s / 穿透深度分析 9.2s）`），日志本身即可归因，不必再翻 perf 台账（rf-979）。

### 修复

- 熔断退避不再被「单批并发失败」瞬间打满（rf-974）：已熔断期间到达的在途失败只计数、不升级退避，升级只发生在冷却期满后重新熔断——一次接口抖动不再把主通道关停一小时。
- 季报取数长尾与重试可追（rf-975）：季报请求改分阶段超时（connect 8s / 读写 15s），季度回溯与 `jjcc→zqcc` 递补各打一行 INFO，失败不再是一段无解释空白。
- 新闻源空渠道不再静默（rf-977）：条目按渠道打标（`_channel`），空渠道单独成行 `CCTV: 0 条（空源）`；源标签按本次真正出条目的渠道拼接（`财新网` / `财新网 + CCTV`），不再把两渠道并写成命中结果。
- 事件窗丢弃原因可归因（rf-978）：跳过计数拆为 `no_keywords`（关联召回 0）与 `not_in_holdings`（索引未覆盖），装配行同时上屏「跳过明细 + 比对分布」，`分歧例块 0 字符` 可据此判断是真无分歧还是判据未触发。
- 截图入口用例改为 hermetic（rf-981）：`test_report_subcommand_returns_underlying_exit_code` 原先只 mock `run_report`，入口护栏仍读默认 `docs/tmp/screenshots/demo`（git 忽略域）——本地跑过 `make-screenshots.py demo` 就假绿，CI 四条流水线（3.11/3.12/3.13 + portability）自 v0.16.11 发布链起连红。现改为把 `DEFAULT_ROOT` 指到 `tmp_path` 并先真建演示工作区，另补回归用例「工作区缺失时入口拒绝且不调用 `run_report`」。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.12（2026-10-25 ~ 2026-10-30）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
