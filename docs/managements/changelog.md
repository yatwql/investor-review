# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.5]**（2026-11-18）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.6-dev] - 开发中（未发布）


（本次发布内容见下方归档索引）

- **归档步幂等**：`release.py archive` 改为节内逐块全搬 + 既有本版批次节并入（按 rf 编号去重升序），修复「表格被空行切块时只搬首块、每轮追加一个同名 `## 已修复（X.Y.Z）`」导致的重复标题与台账滞留；`count_rf_rows` 同步改为节内全量清点，门禁不再误判「已搬空」；配 2 条回归用例（`rf-1178`）。

- **akshare 接口改名兼容**：新增 `core/akshare_compat.py`，四个被 akshare 就地改名的接口（交易日历 / 同花顺行业资金流 / 央视新闻 / 板块资金流排行）改按「逻辑名 → 候选链」解析（`resolve()` 取第一个存在的接口承办，新旧名并存时仍走旧名）；`core/v8_subprocess.py` 子进程同步按候选链解析。修复新版 akshare（CI 解析到 1.20.65）上三条取数链路以 `AttributeError` 静默降级、数据缺失而本机旧版全程无感的问题；配 10 条用例（含「调用点不得硬引旧名」契约）（`rf-1179`）。
- **CI 转绿**：`test_v8_call_sites` 的「已知 V8 接口」断言改按候选链判定并补「合成模块」确定性用例（不再随 akshare 版本假红）；14 个漂移文件 `ruff format` 归位，全仓格式检查恢复零告警（`rf-1179`）。

- **旧结构兼容残留清理**：`fetch_index_history` 的会话缓存只认 `(days, bars)`（裸列表脏条目改为未命中重取）、行业资金流通道失败负缓存只认 `{通道: 失败类型}`（整源单字符串不再回退成全通道失败）、`capture_snapshot` 删掉无调用方的 `**extra` 透传口；配 4 条回归用例（`rf-1180`）。

- **8 小时变更审计**：删掉迁档重构后失去生产调用方的 `split_section_table` / `extract_rf_table`（用例改为断言真实产出）、去掉 `akshare_compat.resolve` 上多余的 `type: ignore`、V8 子进程模块 docstring 补齐「逻辑名 + 候选链」口径（`rf-1181`）。

- **缓存测试去脆**：`test_cache_core.py` 的 `clear_by_prefix` 用例不再写死文件条数与固定长度 `side_effect`（并行档下会 `StopIteration` 假红），改为函数式副作用 + 由前置清单派生的结构断言（`rf-1182`）。

- **conftest 拆分**：`src/test/conftest.py` 1199 → 176 行，夹具/钩子按域下沉 `src/test/_conftest_{isolation,state_reset,cassette,network,hooks}.py`，入口只留标记注册与会话级兜底并把实现 import 回来注册；复位接线契约测试改为汇总 `conftest.py` + 实现模块（`rf-1183`）。

- **类型检查配置补 `ignore`**：`[tool.pyright]` 增 `ignore = ["src/test"]`——测试域仍不入受检域，但编辑器/LSP 打开测试文件时的「兄弟模块导入无法解析」假红不再刷屏（`rf-1184`）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.5（2026-11-12 ~ 2026-11-18）
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
