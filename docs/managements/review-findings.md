# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.3-dev
> **编号源**：`rf-next = 916`（新增问题提出后更新为 +1；已用最大 rf-915，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-913** | **原子写入单源偏离**（架构约束表「缓存原子写入」条）：`web/scheduler.py::_save_fired` 自建 `tmp + os.replace`，且临时文件名固定为 `scheduler_fired.json.tmp`（非 `tempfile.mkstemp`）——同目录 `web/upload.py`、`web/holdings_update.py` 都已显式走 `core/atomic_write`；固定 tmp 名下并发写会互相截断，落盘实现也成了第二份。其余手写 tmp+replace 均有正当理由且在 docstring 注明（`config/_core._atomic_write` 要抛原异常类型、`cache/_io` 需 gzip 与 Windows 锁重试、`providers/news_dedup` 带 .bak 校验、`excel_writer`/`html_save` 是产物且经 `note_temp` 登记） | 改 `core.atomic_write.write_json_atomic`（保留 prune 与失败记 ERROR 行为）；回归：并发写不互相截断（两线程各写 50 条后账本完整）、写失败只记日志不抛 |
| **rf-915** | `docs/plan/` 三份在办设计无 `plan-XXXX` 任务追溯：`decision-reflection-design.md`、`jev-news-judgment-design.md`、`jev-news-judgment-evaluation.md`——`release.py prepare` 每轮都提「未引用任何任务编号，人工确认是否完成」，状态只能靠读文档头自行判断 | 为在办项补 plan 任务（含关联设计文件路径与完成判据）；若已判定不做/已评估未采纳，迁入版本归档并删除在办状态 |
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。当前无登记项。

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。当前无登记项。

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。

| # | 文件 | 现状与拆分方向 |
|---|------|----------------|
| **rf-914** | `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| **rf-914** | `src/test/conftest.py` 999 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| **rf-914** | `src/python/llm/generators_orchestrator.py` 827 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐） |
| **rf-914** | `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| **rf-914** | `src/python/llm/skeleton.py` 739 行（主程序登记线 700） | 骨架模板与占位渲染可分（模板数据 vs 渲染逻辑） |

## 已解决问题

### 开发期已修复（0.16.3-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-909** | 持仓明细行组装两份拷贝：`report/_orchestrator_data.py`（编排路径，10 字段 + `change_pct`/`nav_date`/`source_api`）与 `report/_report_helpers._action_holdings_details`（行动建议路径，同 10 字段子集）各写一遍，`profit_rate` 百分号换算与 `channel` 渠道判定在两处重复；字段增删需同时改两处，漏改即出现「同一持仓在行动建议与编排数据里字段不同」 | 抽 `report/_holding_detail_rows.py::build_holding_detail_rows(details, *, with_market_fields, transactions=None)`：共有 10 字段（`profit_rate` 百分号口径、`channel` 经 `classify_channel` 单源、`account` 原值）集中构造，`with_market_fields=True` 追加行情三字段（`change_pct` 零昨收兜底），尾部统一 `attach_holding_trading_days`；`_action_holdings_details` 改为其薄封装，编排路径改为同名调用（顺带把 `changed_code_files`/`penetrated_targets` 等既有类型摩擦就地收窄）。回归 9 例（两路径共有字段逐项一致/键序固定/行动建议字段子集不变/百分号与 None/零昨收 0.0/渠道单源/两侧同时附加 holding_days） |
| **rf-912** | 发布 `refresh` 的 bench 偶发退出码 1 而台账 `failed_tests` 为空，看不出哪个用例红——真因有两处：① `unit/web/test_runs.py::TestConcurrency::test_concurrent_submits_isolated` 的 `_wait_done` 用 3s 真实墙钟等后台线程，8 路 xdist 满载时线程迟迟不被调度即超时（时序脆弱，同文件另有 `test_retention_trim_oldest` 同类）；② `_run_phased` 的关键词过滤只留小写 `failed`，pytest 短摘要的 `FAILED 路径::用例` 行被丢弃，`_summarize_failure` 的 debug.log 兜底又只看 stdout 归档行指向的目录（那是**上一次**运行的报告目录，本次失败档的 debug.log 还在 `test-reports/latest/`）→ 连续三次发布（0.15.2/0.15.8/0.16.2）各多花一轮人工重跑与翻归档定位 | 等待预算改 `_WAIT_TIMEOUT_S = 30.0`（等到就绪而非时延断言，注释写明满载场景）；`_run_phased` 过滤补 `FAILED`；新增 `_failure_debug_text()`：归档目录未命中时按 mtime 倒序搜 `test-reports/latest/<模式>/` 的 debug.log，且 stdout 已有 FAILED 行则不读（防旧失败被当本次）。回归 4 例（假时钟下慢调度仍等到、预算耗尽报时长与末态、latest 兜底点名用例、stdout 优先于 latest） |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-25）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.0 ~ v0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
