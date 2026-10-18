# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.6]**（2026-10-18）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.7-dev] - 开发中（未发布）

- **新增**：HTML 报告与 What-if 页每张交互图表提供「导出CSV」按钮（与「导出PNG」并排，`.chart-export-actions` 组容器浮于图卡右上角）——CSV 取自 `chart.data` 屏显同源数据（Python 数据层已按匿名化口径脱敏，与悬停值一致），UTF-8 BOM + CRLF、RFC 4180 引号转义，`Blob` 纯前端本地下载（零后端），读者可直接做透视/二次分析；按钮定位样式三处模板同步（主报告 / What-if / 调试页）；`test_feature_interactive.py` 新增 4 用例
- **修复**：用户文档残留不存在的交互图表开关描述（rf-719）——FAQ「HTML 报告打开显示不正常」排查项与 CLI 手册 `--feature` 示例注释不再引导 `enable_interactive_charts`/静态回退，改按「Chart.js 唯一渲染、图表引擎与数据内嵌单文件」的当前口径
- 发布编排自动化：`release.py prepare` 现在同时重写 changelog 归档头部——`> 涵盖版本：v{首段} ~ v{末段}（{起} ~ {止}）` 与 `> 归档时间：{发行日}（v{版本} 发布并入；已并入 N 段：v…（MM-DD）、…）`，两行的真值是归档文件自身各 `## [版本] - 日期` 段列表（追加后派生，不会与正文漂移）；早期归档（如 v0.1.x）缺这两行时原样跳过不补写；此前这两行需人工补写，v0.13.6 发布时即漏改过一次；新增 4 单测（区间/并入记录派生、单段形态、无头部行跳过、有头部但无段报错）


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.6（2026-10-13 ~ 2026-10-18）
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
