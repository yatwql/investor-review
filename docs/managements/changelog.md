# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.1]**（2026-10-24）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.2-dev] - 开发中（未发布）

- **`plan-210` 新闻去重快速上界**：`_dedup_by_title` 先用 `SequenceMatcher.quick_ratio` 判断候选门槛，低于门槛不做完整双向 ratio；合并判定不变，新闻 TTL 仍保持 900s（不为提速放宽时效）。

- **`plan-211` 数据源状态接入报告矩阵**：行业资金流向失败经 `mark_data_unavailable` 写入 DegradationTracker，数据源可用性矩阵可见；provider 暴露公开失败状态访问器，`fetcher`/`cache` 不再读取私有 `_SECTOR_FLOW_FAILURE`/`_DIVIDEND_FAILURE`。


- **`plan-211` 数据源路由与降级状态**：hithink 不再把场内 ETF 送入 A 股价格/历史槽，并归一 A 股错误交易所后缀；行业资金流向失败类型写回模块状态（连接失败/暂无数据），缓存提示可区分。

- **`plan-211` 首片：K 线风控页日志降噪**：腾讯/新浪逐代码「返回非 JSON」从 WARNING 降为 DEBUG；源失败仍计入 registry，熔断汇总保持 WARNING。

- **`rf-865` 持仓集中度 Excel 恒占位修复**：`excel_module_loader` 补注册 `compute_concentration`，Excel 与 HTML 同源；新增装配键/可调用回归。
- **`rf-866` 自检截断语义修复**：`max_tokens_self_review` 默认 2048→3072；首次截断记 WARNING，自动放大后仍截断才记 ERROR，重试成功不再污染 `errors`。

- **`plan-208` 跨模块导入面收窄完成**：`config/cache/cli/providers` 公共面移除私有 `__all__`；兼容转发注释清零；生产代码跨包私有导入清零；`code_utils`/`doctor`/`cache.operations` 等转发按 owner 收口；`providers/_utils.py`→`providers/utils.py`、`analysis/_prosperity_inputs.py`→`analysis/prosperity_inputs.py`；测试 patch 点对齐 owner；新增观察期 `scripts/check-import-surface.py`（compat-comment / private-all / cross-private / dynamic-target）与 owner 表（`technical.md` §9）。

- **`plan-209` TUI 显示模式统一（完成）**：状态标签收敛到 `switch_panel.status_text`（关闭恒红，父项关闭的子项不再退化为无色）；`truncate_display` 改为 ANSI 感知并补 `RESET`，修复窄档蓝色分组标题颜色泄漏；`DESIGN-TUI.md` 新增「Display Modes」契约；立项设计见 `docs/plan/tui-display-modes.md`。

- **`rf-863` 发布流程写前校验与失败回滚**：`apply_changelog_release` 现在在纯文本阶段校验「最近发布」指针行与归档索引行的目标路径（跨小版本目录缺 `v` 等错误在 `check` 预演即中止），并把索引行目录一并归一；`prepare` 在预检干净树的前提下，写盘后任一步失败自动 `git reset --hard HEAD` 回滚（未跟踪文件只提示不删除），不再留半途状态。



（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.1（2026-10-24）
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
