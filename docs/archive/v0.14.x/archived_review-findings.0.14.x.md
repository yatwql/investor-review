# 自审记录归档 — v0.14.x

> 归档时间：2026-10-21（v0.14.0 发布，0.14 系列首批开发期已修复批次并入）；2026-10-21 v0.14.0 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.14.x 开发期已修复项（v0.14.0 → ）（含 v0.14.0）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 开发期已修复（0.14.0-dev）

> 完整复盘见 `changelog.md` 0.14.0-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-21。

| # | 问题 | 处理 |
|---|------|------|
| **rf-801** | 台账迁档占位节随发布累积（每版新增一节、旧版占位不收敛）：5 段单行同构占位节同时存在；三守护均拦不住（重复标题按路径感知判重；长行阈值 40 字符 vs 占位行 33；区块需 5 行/100 字符），占位↔归档节 1:1 由 doc-drift 只校验“存在”不校验“累积” | 已修复：`_release/_ledger_archive.py` 新增 `_collapse_superseded_placeholders`，在 `apply_rf_archive` 末步只保留本版占位节、收敛旧版（节内若还有表外散文则只摘占位行、保节与散文）；存量 5 节已一次性收敛为 1；详情见 changelog 0.13.13-dev |
| **rf-802** | pre-commit 的 `--sync` 触发面只覆盖 `docs/managements/` 与 `src/test/`，而统计表同时统计 `src/python/`（主程序行数）与 `scripts/`（脚本行数）——纯这两域改动会走 `--ci` 分支、以「行数不一致」finding 拦下提交，逼人工 sync 再重提；另「`ruff format` / `collect-test-coverage --update-docs` 在 `--sync` 之后跑会把刚回写的数字重新写陈旧」这条写者顺序，文档只写了「编辑 vs sync」，未覆盖其它写者 | 已修复：钩子触发面扩到四个被统计域（任一变更即自动 `--sync` 回写并 `git add`）；developer-guide「`--sync` 统计快照口径」补「写者顺序：`--sync` 须为收尾最后一个写者」+「触发面 = 全部被统计域」，收尾红线与 CLAUDE.md 同步；新增 `test_shell_contract.py::TestPreCommitSyncTriggerCoverage` 3 例（触发面覆盖全部被统计域 / 样例路径命中 / 非统计路径不触发） |
| **rf-803** | 切开发版后台账仍显示上一版的迁档占位节（过期信息）：`devbump` 只改版本号，`### 开发期已修复（0.13.12-dev）`「本版已随 v0.13.12 发布迁入**上方**归档档案」在 0.13.13-dev 周期仍挂在「已解决问题」区顶部——既是过期提示，文案里的「上方」也与实际版面不符（归档索引在下方） | 已修复：`RF_PLACEHOLDER` 文案去掉方向词；`_ledger_archive` 新增 `drop_migration_placeholders`（`keep_version=None` 清空全部占位节），由 `release.py devbump` 在切版时调用并打印清理结果；存量 0.13.12 占位节已一次性清除。回归用例：`test_release_archive.py`（清空全部占位 / 带散文节只摘占位行）与 `test_release_tool_gate.py::TestDevBump`（devbump 落盘清理） |
| **rf-775** | 13 个测试文件逼近 1000 行（1017~1175 行，红线 1200），按职责切分以留出余量 | 已修复：按「顶层测试类/函数」切兄弟分片，原文件保留一组并承载跨组共享夹具（分片按名导入，`# noqa: F401` + 文件级 `# ruff: noqa: F811` 说明夹具按名注入）；切分后各文件 140~715 行、最大分片 876 行，用例数与断言强度不变（逐文件 collect 对拍 94→94 等）。切割面：cli/report·cache_whatif·main、web/system·runs、ui/status·loop、scripts/doc、handlers/switch、fund_performance/sheet、html_content/charts·blocks、reader/workbook·flows、summary/sheet、fact_checker/symbols·ranking、rebalance/deviation·signals、orchestrator/both·full（方法级切分）、chain/fallback·recovery |
| **rf-804** | 降级跟踪器在模块级缓存单例实例（`report/{fund_performance,penetration_sheet,summary}.py` 的 `_tracker = get_tracker()`）——`reset_tracker()` 只销毁工厂内的当前实例，缓存引用仍指向旧对象，测试隔离失效、运行期重置同样失效；表现：切分后重排执行顺序，`test_all_funds_fail` 因前序用例累计的降级计数而写出状态脚注（原断言 `ws.cell.call_count == 0` 失败 2≠0） | 已修复：三处改为 `_tracker()` 惰性取当前单例（不缓存引用）；回归用例 `report/test_data_status.py::TestTrackerNotCachedAtModuleLevel` 2 例（全仓 AST 扫描禁止模块级 `= get_tracker()` 缓存 + 三模块取用点必须落在 reset 后的新单例） |
| **rf-805** | plan 台账已完成节永远搬不走：归档清单只认 `^## `（二级）标题，而台账里的任务节嵌在 `### P1~P4` 分组下、实际是 `####` —— 本次发布 prepare 报「plan：0 个已完成任务节」而 plan.md 仍残留 `plan-170 … ✅`（人工不核对就会漏归档，且 doc-drift 只查「归档节存在」不查「主台账残留」） | 已修复：`_PLAN_DONE_HEAD_RE` / `_PLAN_ANY_HEAD_RE` 支持 2~4 级标题；入档时把节头统一降为 `## plan-N … ✅`（归档按版本批次堆叠，不需要优先级分层）；同时把归档完成提示里的「上方」方向词去掉。回归用例 `test_release_archive.py::TestPlanArchiveHeadingLevels` 2 例（`####` 完成节被识别 / 搬离主台账并入档降为二级） |
