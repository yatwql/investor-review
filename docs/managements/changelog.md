# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.3]**（2026-10-15）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.4-dev] - 开发中（未发布）

### Changed

- **perf-view 新增 P95/P99 分位概览**：`scripts/perf-view.py` 输出新增「总体分位概览（跨版本）」表（口径 / 样本数 / 平均 / 中位 / **P95** / **P99** / 最长），并在每个版本分组段直给「95% 的报告在 Xs 内完成，99% 在 Ys 内完成」。分位采**最近秩**（`ceil(pct% × n)` 位样本值）口径，含义即 95% / 99% 的报告生成在该耗时内完成。新增 `_percentile()` / `_total_summary()` / `_overview_lines()`，过滤逻辑抽为 `_filter_records()` 与分组共用（`--report-type` / `--last` 对概览同步生效）；单一报告类型时只渲染合计行，不重复出类型行。同步文档：developer-guide「perf-view」段（分位口径说明 + 脚本清单）与 how-to-use-cli-mode 性能历史小节。回归 = `test_perf_view.py` 新增分位口径 / 汇总字段 / 概览表结构 / 分组完成时间四组用例。

- **developer-guide 核对更新：补发布归档迁移四项 + release 收尾 sync 口径**：对照近期变更核对开发者指南，修复 4 类缺口——① 版本发布流程五步→六步，新增步骤③「发布归档迁移（四项强制）」（rf/plan 完成态/changelog 段/docs-plan 设计文件四项，未完成不得继续 `gate`/`publish`——此前指南完全缺失该强制项），原③④⑤顺延为④⑤⑥并修正步骤间互引用；② 发布类命令注释与编排提示补 `prepare`/`evolution` 收尾自动 `check-doc-drift --sync` 实况（rf-686 后口径同步），并明示归档迁移保留人工且须前置；③ 「② 发布数据文档刷新」补 `evolution --release` 输出「需人工核对注释行」的回填义务（test-coverage 用例收集口径 + folders.md 文档目录分解数）；④ 新增测试指南「新增后必须更新的文件」清单补第 6 条 conftest 隔离 fixture（模块级单例 autouse 复位、持久化/输出路径在 `_isolate_sensitive_paths` 重定向，指向 CLAUDE.md「新增测试隔离要求」细则）。新增段落措辞经 `check-doc-traces` ARCHIVE 规则复核（面向读者文档不写归档目录/文件名）。

- **`perf-report.py` 更名 `perf-test-report.py`**：与「历史趋势查看 `perf-view.py`」对仗，突出其**基准测试**定位（自造模拟持仓跑 basic/both 管线、mock LLM，输出 `docs/tmp/better-investment-performance-test-report.md`）。`git mv` 保留历史，同步更新脚本自引用、`core/perf.py` 分层注释、`_traces_code/patterns.py` 注释、developer-guide 脚本清单与诊断段、folders.md 目录树；配套测试同步更名 `test_perf_test_report.py`（fixture 名与 `load_script` 入参随改），`test_script_loader.py` 的模块名派生断言随新文件名（`perf_test_report`）更新。

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.3（2026-10-13 ~ 2026-10-15）
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
