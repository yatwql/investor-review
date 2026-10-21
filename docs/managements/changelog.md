# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.12]**（2026-10-21）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.0-dev] - 开发中（未发布）

### Changed

- **测试文件切分（`rf-775`）**：13 个逼近红线的测试文件（1017~1175 行）按职责切兄弟分片，原文件保留一组并承载跨组共享夹具（分片按名导入，`# noqa: F401` + 文件级 `# ruff: noqa: F811` 注明夹具按名注入）；切分后单文件 140~715 行、最大分片 876 行，用例数与断言强度不变（逐文件 `--collect-only` 对拍一致）。顺带把 `_DATASET_KEYS` 从测试类属性提到模块级（原被两处跨类引用，切分后成为跨文件共享常量）。

- **降级跟踪器单例缓存缺陷（`rf-804`，切分验证期暴露）**：`report/{fund_performance,penetration_sheet,summary}.py` 曾在导入期 `_tracker = get_tracker()` 缓存实例——`reset_tracker()` 只销毁工厂内当前实例，缓存引用仍指旧对象，测试隔离与运行期重置双双失效；重排执行顺序后 `test_all_funds_fail` 因前序用例累计的降级计数而写出状态脚注。现改为 `_tracker()` 惰性取当前单例，并由 `report/test_data_status.py::TestTrackerNotCachedAtModuleLevel` 2 例守护（全仓禁止模块级缓存 + 重置后取用点跟随新单例）。

- **切开发版清空迁档占位（`rf-803`）**：占位文案去掉方向词（原写「上方」与版面不符）；`devbump` 之后台账已属新周期，上一版「本版已随 vX 发布迁入归档档案」属过期信息——`release.py devbump` 现调用 `drop_migration_placeholders` 清掉全部占位节（含空节头），存量 0.13.12 占位节已一次性清除；「占位↔归档节」doc-drift 断言随占位消失自然收敛。回归用例 4 例（文案无方向词 / 清空全部占位 / 带散文节只摘占位行 / devbump 落盘清理）。

- **提交期门禁提速（`plan-170`）**：`offline_external_sources` 离线桩新增 `_NoWaitClock`（`time` 模块代理：`sleep` 变空操作、`monotonic`/`perf_counter` 原样透传），在 `apply_offline_stubs` 中接管 `core.throttle` / `core.retry` / `providers.cninfo` / `providers.datasink` 的模块级 `time`——间隔节流、多策略退避与 429 限速重试窗口不再白等“注定取不到的源”，分支照常覆盖、断言强度不变。作用域限于声明离线桩的文件（测试自身 `time.sleep` 与验证等待语义的用例不受影响）。实测 P0 `dev-verify` 墙钟中位 **37.3s → 24.0s（−36%）**；同时复核并行度：`-n 12` 反而更慢（user CPU 235s vs 145s），维持“每核 50%”口径不加并发。

- 新增回归用例 `unit/core/test_network_guard.py` 4 例（间隔节流零等待且算式返回值不变 / 退避零等待且重试次数不变 / 代理保留真实 `monotonic`·`perf_counter` / 未声明离线时等待语义原样），桩目标存在性断言补四个模块的 `time.sleep`。

- **台账迁档占位收敛（`rf-801`）**：`review-findings.md` 的「开发期已修复」占位节原来每版新增一节、旧版不收敛（已累积 5 段单行同构节），而三守护均拦不住——重复标题按路径感知判重（各节标题版本号不同）、长行阈值 40 字符 vs 占位行 33、区块需 5 行/100 字符。现 `_release/_ledger_archive.py` 新增 `_collapse_superseded_placeholders`，在 `apply_rf_archive` 末步只保留本版占位节：旧版占位行删除，节内若只剩占位与空行则节头一并删除，仍有表外散文（人工备注）则保节保散文只摘占位行；存量 5 节已一次性收敛为 1。回归用例 4 例（只留本版 / 散文节保留 / 单占位幂等 / `apply_rf_archive` 接线）。

- **统计快照写者顺序与钩子触发面（`rf-802`）**：pre-commit 的 `--sync` 触发面扩到**全部被统计的域**（`docs/managements/` 文档行数 / `src/test/` 测试行数与用例数 / `src/python/` 主程序行数 / `scripts/` 脚本行数）——此前只覆盖前两域，纯 `src/python`/`scripts` 改动会以「行数不一致」finding 拦下提交、逼人工 sync 再重提。同时把「写者顺序」写进纪律：`--sync` 必须是**收尾的最后一个写者**，`ruff format` / `collect-test-coverage --update-docs` 等写者全部在它之前，sync 之后只做只读校验（`dev-verify`/守护回放），否则统计表数字会因后续写入重归陈旧。守护：`unit/scripts/test_shell_contract.py::TestPreCommitSyncTriggerCoverage` 3 例。


## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0（2026-10-21）
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
