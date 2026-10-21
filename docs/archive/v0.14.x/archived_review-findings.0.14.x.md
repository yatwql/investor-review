# 自审记录归档 — v0.14.x

> 归档时间：2026-10-21（v0.14.0 发布，0.14 系列首批开发期已修复批次并入）；2026-10-21 v0.14.0 本批原表搬运；2026-10-22 v0.14.1 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.14.x 开发期已修复项（v0.14.0 → ）（含 v0.14.1）
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

## 开发期已修复（0.14.1-dev）

> 完整复盘见 `changelog.md` 0.14.1-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-22。

| # | 问题 | 处理 |
|---|------|------|
| **rf-773**（部分） | 报告域三个模块内职责混杂、逼近 700 行登记线：`orchestrator`（编排 + 数据装配 + 派生计算）、`_report_generation`（聚合门面 + both/full 双路径实现）、`fund_performance`（页签写入 + 评级内核） | 已拆三处：① orchestrator 734→**255**（`prepare_report_data` + `compute_*` 五域 → `_orchestrator_data.py` 519）；② `_report_generation` 751→**52**（`_generation_both.py` 356 / `_generation_full.py` 368 / `_generation_shared.py` 85，门面 re-export）；③ `fund_performance` 728→**595**（评级/格式化内核 → `_fund_rating.py` 166）。测试 patch 与结构断言按「调用点所在模块」改指新模块。**剩余 5 个模块**（api_base / _validation / holdings_detail_sheet / prosperity_scoring / news_dedup_rules）仍登记在 P3 的 rf-773 行内 |
| **rf-787** | `src/test/unit/scripts/test_check_doc_drift.py` 1061 行（测试红线 1200，余量 139）：机检项族全塞一个文件 | 已修复：按机检项族切三个兄弟分片——`_partitions`（台账分区纪律 / 归档索引 / 迁档占位）、`_sections`（章节-区块矩阵 / 手册菜单块与键引用 / 返回键不变式 / 可见性类型行）、`_tree`（目录树解析 / 说明计数 / 版本目录顺序）；基片 410 行、分片 118~289 行，用例数不变（130 passed），共享夹具仍由基片提供（分片按名导入） |
| **rf-774** | 脚本域两个文件逼近脚本红线（1000）：`scripts/perf-view.py` 983 行（余量 17，**必须拆**）、`scripts/check-test-redundancy.py` 934 行（余量 66，八类检查混在一个文件） | 已修复：① perf-view 采集/渲染/CLI 三段下沉 `scripts/_perf_view/`——`data.py`（派生）/ `report.py`（渲染 + build_trend_report）/ `cli.py`（argparse→输出），入口 983 → **102 行**（docstring + sys.path 引导 + re-export）；② check-test-redundancy 八类检查各成子模块 `scripts/_test_redundancy/`（`_common` 共用 AST 原语 + `cases`/`duplicates`/`similar`/`self_fulfilling`/`hardcoded`/`trivial`/`weak_mock`/`dead_fixtures`/`facts_cache` + `runner` 编排），入口 934 → **150 行**。两者均保留 `load_script` 直调面的 re-export；测试 patch 目标按「调用点所在模块」改指实现模块（`_test_redundancy._common` 的扫描根、`ast.parse` 打桩仍经入口） |
| **rf-79** | `src/python/core/code_utils.py` 788 行：把「资产类型判定」与「派生量」（交易所前后缀归一 / FMP·东财·cninfo 符号与参数 / 市值粗估）混在一个模块，逼近 700 行登记线 | 已修复：派生量下沉 `core/code_symbols.py`（227 行，前缀常量 `EXCHANGE_PREFIXES` / `_INDEX_EXCHANGE_PREFIXES` 真值迁入其中）；`code_utils.py` **608 行**，保留同名 re-export 维持既有导入面；`_strip_prefix` 更名 `strip_to_digits`（公开原语，`is_six_digit_code` 调它，避免互相递归）；两处「单点定义」守卫同步允许新模块并加 `is` 同源断言。同步 folders 目录树、technical 模块说明 |
| **rf-807** | `prepare --version` 跨版本发布不可用且提示误导：要求 changelog 开发段 == `X.Y.Z-dev`，而失败前打印的是入参而非推导值（两次都显示同一版本号），执行者读不出该做什么；旧行为还「按推导执行」继续跑到中途才报错 | 已修复：与开发链推导值不一致时**立即中止**（exit 2），并给出四步可执行指引（改 `APP_VERSION` → `check-version-consistency --fix` → 同步 changelog 段头与 rf 节头 → archive-init/check/prepare）；回归用例 `test_release_tool_gate.py::TestPrepareVersionMismatchGuidance`（中止 + 指引关键词 + 零写入） |
| **rf-808** | 新小版本首发缺归档骨架且构建知识隐含：需手工建三份归档 + folders 目录树块 + plan/rf/changelog 三处索引行，每补一处都要重跑 `check`（实测一次发布 4 次 check、4 次 prepare）；索引行还需区间口径，格式不符时只在 prepare 阶段报错且不附期望格式 | 已修复：新增 `release.py archive-init [--version] [--date] [--dry]`（`_release/_archive_init.py`），一次建齐三类空位并幂等；建完自动跑 `check-doc-drift --sync`；回归用例 `test_release_tool_gate.py::TestArchiveInit` 2 例（建齐文件/目录树/索引且前置就绪 / 二次运行零改动） |
| **rf-809** | 真实仓库契约测试断言了「随开发周期变化」的仓库状态：`test_real_rf_sections_are_migrated_or_absent` 要求主台账「至少有一节开发期已修复」，而 `devbump` 清空占位后新周期台账为空 → v0.14.0 发版当日的 `dev` 提交 CI 全红（test 3.11/3.12/3.13 + portability；本地因已补 rf-806 节而侥幸通过） | 已修复：该用例只约束「存在的每一节」（当前开发版待迁/已迁、更早批次只允许已迁档），空台账合法；同批把 `TestCliSurface` 的处理器集合改为从 `cmd_*` 派生（新增子命令无需改测试） |
| **rf-806** | changelog 指针行的归档链接不随小版本换名：`apply_changelog_release` 只写版本号与日期，归档文件名沿上一系列的值（v0.14.0 指针指向 `archived_changelog.0.13.x.md`，而该版段落实入 0.14.x）——指针仅在本系列首个版本恰好正确，其余每版都留一处失准链接 | 已修复：改写指针行时同步换名为 `archive_name_for(release_version)`，格式不符即报错中止；主文件指针已校正。回归用例 `test_release_tool.py::TestChangelogPointerLinkFollowsArchive` 2 例 |
