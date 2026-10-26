# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.2]**（2026-10-26）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.3-dev] - 开发中（未发布）

### 变更

- **文件膨胀登记清单落表**（rf-914）：`check-file-length -v` 实测 5 个文件越过登记线（测试 >900：`test_release_tool_gate.py` 1147、`conftest.py` 999；主程序 >700：`generators_orchestrator.py` 827、`cli/_handlers.py` 789、`llm/skeleton.py` 739），而 P4 原写「当前无登记项」——按文件逐条登记为 P4 存量监控清单（不占用 rf 编号，拆分后逐行删除）
- **在办设计补任务反引**（rf-915）：`jev-news-judgment-design.md` / `jev-news-judgment-evaluation.md` 头部补「关联任务：`plan-55`」，与 `plan.md` 的正向引用构成双向追溯；`release.py prepare` 的「未引用任何任务编号」提示随之归零

- **持仓明细行装配单源**（rf-909）：新增 `report/_holding_detail_rows.py::build_holding_detail_rows()`——编排路径（`_orchestrator_data.prepare_report_data`，全量含行情三字段）与行动建议路径（`_report_helpers._action_holdings_details`，basic/both 共享的 10 字段子集）过去各写一份字面量，`profit_rate` 百分号换算与 `channel` 渠道判定重复实现，字段增删漏改一处即出现「同一持仓在两处字段不同」；现共有 10 字段集中构造、`with_market_fields=True` 追加 `change_pct`/`nav_date`/`source_api`、尾部统一附加 `holding_days`，`_action_holdings_details` 降为其薄封装。回归 9 例（两路径共有字段逐项一致、键序固定、字段子集不变、百分号与 None、零昨收 `0.0`、渠道单源、`holding_days` 两侧一致）

### 修复

- **定时生成账本落盘走唯一原子写原语**（rf-913）：`web/scheduler.py::_save_fired` 原自建 `tmp + os.replace` 且临时名固定为 `scheduler_fired.json.tmp`（并发写互相截断、与同目录 `upload.py`/`holdings_update.py` 的做法分叉），改 `core.atomic_write.write_json_atomic`（保留剪除超保留期条目、「失败只记 ERROR 不外抛」）；顺带修 `status_payload` 的 `next_fire_at(...).strftime` 空值访问。回归 2 例（落盘失败只记 ERROR 且不产半文件、3 线程各写 20 轮后账本完整可解析且无残留 `.tmp`）

- **发布 bench 不再随机假红**（rf-912）：`unit/web/test_runs.py` 的 `_wait_done` 原本用 3s 真实墙钟等后台线程，8 路 xdist 满载时线程几十次调度才被唤醒即超时（`test_concurrent_submits_isolated` 已实测假红，同文件 `test_retention_trim_oldest` 同类）；等待预算改为 `_WAIT_TIMEOUT_S = 30.0`——这是「等到就绪」而非时延断言，注释写明满载场景。回归 2 例（假时钟下第 5 次轮询才就绪仍须等到、预算耗尽须报等待时长与末态）
- **发布台账能自证「哪个用例红」**（rf-912）：两处诊断盲区——`_test_runner.runner._run_phased` 的关键词过滤只留小写 `failed`，pytest 短摘要的 `FAILED 路径::用例` 行被丢弃；`release._commands_base._summarize_failure` 的 debug.log 兜底只看 stdout 归档行指向的目录（那是**上一次**运行的报告目录，本次失败档的 debug.log 还在 `test-reports/latest/`）。前者过滤补 `FAILED`，后者新增 `_failure_debug_text()`：归档目录未命中时按 mtime 倒序搜 `test-reports/latest/<模式>/` 的 debug.log，且 stdout 已有 `FAILED` 行则不读（防旧失败被当成本次）。回归 2 例（latest 兜底点名用例、stdout 优先于 latest）；连带修复 `_changed_code_files` 的 `dict | None` 入参与超时分支的 `float(None)`

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.2（2026-10-25 ~ 2026-10-26）
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
