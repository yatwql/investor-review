# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.9]**（2026-10-20）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.10-dev] - 开发中（未发布）

### Added

- `check-code-traces` / `check-requirement-trace` / `check-doc-drift` 接入结论缓存（`--ci` 且非 verbose，doc-drift 另排除 `--sync` 写路径、非 git 环境不缓存）：逻辑与全集输入指纹未变时逐字回放上次输出与退出码（冷/热输出一致，仅多一行缓存注释），同树重复（发布门禁 → 提交钩子 / 失败重试）命中省全仓扫描；与既有接入面合计六个 namespace（缓存目录经 `CHECK_CONCLUSION_CACHE_DIR` 测试隔离）。新增回放接线测试（回放不重扫/输入失效重扫/退出码分级保持）与机制矩阵同步更新
- `check-doc-traces` 目录树描述纪律机检：树行（│├└）豁免收窄为仅归档引用类（此前全类别豁免使任务编号与历史痕迹整体过闸）；新增 STATUS 进度状态词类（已实施/已完成/完成态/随任务完成移入/验收·判定·实施记录指引/§N 章节指引/已归档/已核实/树行「不再」/稿态词（草案/初稿/终稿）等，仅目录树域检出，正文当前状态叙述合法不检）；新增受检域 .md 文件名任务编号检查（rf-N/plan-N，语义命名补位）；HIGH 来源叙述补强（无后缀模块名的迁入/移入）。测试 115 passed
- `check-doc-traces` 任务记录域复盘痕迹机检（NARRATIVE 类）：plan.md / review-findings.md / docs/plan/* 的任务内容只反映最新状态——禁修复/改造前后对比、相对旧实现的否定句（不再XX）、历史归因；任务状态标记（已修复/待处理）、根因定位引用、迭代轮次与设计文档旧格式兼容是内容合法；changelog 仍仅章节编号（记录变化是其职责），常规手册不检（「修复后重启」是操作指引）；任务域不走表格豁免（断言表行内叙事必检）。存量 10 处清理（计划页放弃项边界句改「禁止重提」、浏览器验证文档去修复前后对比数字）。测试 122 passed

### Changed

- 发布编排提速：`release.py refresh` 条件化——上次发布 tag 以来的变更仅 `.md`/图片文件时自动跳过 bench + collect（测试计数无变化，下一含程序/测试变更的发布自动补齐；`--force-refresh` 强制恒跑，取不到 tag 或存在未跟踪程序文件时保守恒跑），docs-stats sync 恒跑；`gate` 十守护并行且并发度随核数收敛（4 路封顶、2 核机自动 2 路；守护均只读 `--ci`，结论缓存每 namespace 独立文件、事实缓存均为原子 temp+rename 写，无互踩）；`test-runner` 新增 `--jobs` 多档模式并行采集（优先级 CLI > `TEST_RUNNER_JOBS` 环境变量 > 自适应——4 核+ 为 2，弱机/缺核信息/核数采集异常一律取 1 不超订；环境表新增「采集并行度」行，跨并行度不直接可比），`machine_info` 同步携带采集并行度
- pre-commit 调度：`check-doc-drift` 纯 `--ci` 分支改为后台并行（与快集守护重叠，回放前统一等待），`--sync` 写路径保持串行先行避免 folders.md 写读竞态；回放段同步顺序不变
- `folders.md` 目录树描述全面去任务号与历史痕迹（三轮共 60+ 处）：任务编号（plan-N/rf-N）改为语义描述；已实施/验收记录指引/阶段进度/随任务完成移入等状态与流转措辞全部移除，描述仅保留文件内容简要；归档设计文件语义化改名（`plan-4-brinson-attribution-abandoned.md` → `brinson-attribution-abandoned.md`、`plan-11-dark-mode-plan.md` → `dark-mode-plan.md`，引用同步）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.9（2026-10-13 ~ 2026-10-20）
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
