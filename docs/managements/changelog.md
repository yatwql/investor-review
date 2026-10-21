# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.11]**（2026-10-21）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.12-dev] - 开发中（未发布）

### 新增

- **发布归档迁移固化进脚本**：新增 `scripts/_release/_ledger_archive.py`（台账与设计文档归档的纯文本变换），`release.py` 增加 `archive` 子命令并**内置于 `prepare`**——① review-findings 该版本「开发期已修复」表**原表逐行搬入**归档新节（不做摘要改写）+ 主台账留迁档占位 + 归档头部「涵盖版本 / 归档时间」与主文件归档索引区间派生；② plan.md 标题带完成标记的节整节搬入计划归档；③ `docs/plan/` 中引用编号**全部已归档**的设计文件（强信号才自动判）`git mv` 迁入版本归档子目录 `<stem>/`，并改写 changelog/plan/rf/folders/README/CLAUDE 引用与 folders 目录树条目；收尾自动 `doc-drift --sync` + `check-doc-traces` + `check-doc-links`。`--dry-run` 只报告动作、`--skip-design-docs` 只做台账、`--no-archive` 跳过。**分工**：机械动作归脚本，条目归属 / 完成标记 / 设计文件是否真完成仍由人复核（未引用任何任务编号的设计文件只列提示、不自动迁档；本版无自审条目时归档步自动放行）
- **`_release/` 拆分**：归档命令编排下沉 `_archive_flow.py`（`ArchiveContext` 显式路径入参、落盘顺序与前置缺件清单），`release.py` 只留 CLI 壳与路径常量（958 → 851 行，红线余量恢复）；纯文本变换仍全在 `_ledger_archive.py`（按拆包纪律只收显式参数）
- **`check` 归档前置校验**：预检阶段即校验该发布版本的两份台账归档文件与 folders 目录树 `vX.Y.x/` 块，新小版本缺件在入口暴露（不再等 `prepare` 改完版本全链中途撞上）；`prepare` 的归档步耗时分项记入 `logs/release.jsonl`
- **`gate` 归档前置断言**：P2 门禁在跑 regression **之前**断言「该版本 rf 已解决表已搬空 + 归档存在对应批次节 + 版本已切发布形态」，漏做归档即刻中止（不再靠人记，也省掉一次 20s 白跑）

### 修复（自查，随归档自动化同批落地）

- **rf-792** 归档批次标题/说明行改用既有归档格式（`## 开发期已修复（X.Y.Z-dev）` + `> 完整复盘见 changelog.md …`）
- **rf-793** rf 表块改为**整块原样搬**（含原分隔行与所有行），表外散文留在主台账
- **rf-794** 归档头部 `归档时间` 行改为追加本批戳记，既有逐批叙述只读
- **rf-795** plan 归档去掉自造版本包装节，沿用既有扁平 `## plan-N … ✅`
- **rf-796** `run_archive` 改为「先算后写」：设计文件先迁（`git mv` 失败回滚目录树），台账最后落盘，异常转 `[ERR]` 提示
- **rf-797** 设计文件迁档后一并改写 `docs/plan/` 同级文档引用
- **rf-798** plan 完成节判定放宽到「标题内含完成标记」（`✅` 后带「主体交付」等后缀不再漏判）
- **rf-800** 设计文件迁档落盘改「引用改写 → 目录树 → `git mv`」三连 + 全目标文件快照整体回滚（此前 `git mv` 失败后引用已改指到不存在的路径）；目录树新条目注释不再携带路径文本（避免被引用改写误改）；历史归档内旧路径引用改为 `[!]` 提示不改写
- **rf-799** 新增真实归档格式契约用例（只读真实归档对表）：批次标题/占位句/头部两行/索引行/计划完成节判定，脚本格式漂移即红

### 重构

- **`release` 测试拆片**：`test_release_tool.py` 1182 → 591 行，门禁/refresh/publish/devbump 与归档前置拆入 `test_release_tool_gate.py`（450 行），共享设备（子进程替身 / 临时仓库夹具 / 台账与目录树样例）提为 `_release_fixtures.py`（195 行）——红线余量从 34 行恢复到 609 行，后续加用例不再受阻

### 测试

- 新增 `src/test/unit/scripts/test_release_archive.py`（台账归档纯函数：原表搬运无损与幂等、占位/头部/索引派生、plan 完成节判定与在办节不外溢、docs-plan 完成判定三分支、目录树搬迁与未知条目拒绝）
- `test_release_tool.py` 扩展：prepare 自动归档端到端（台账/计划/设计文件/目录树）、`--no-archive` 跳过、`archive` 子命令（迁移+收尾守护、dry-run 零写入、开发版拒绝）、gate 归档前置三类拦截（未迁档 / 缺归档节 / 仍是开发版）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.11（2026-10-13 ~ 2026-10-21）
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
