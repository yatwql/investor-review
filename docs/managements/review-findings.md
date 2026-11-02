# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.16-dev
> **编号源**：`rf-next = 1025`（新增问题提出后更新为 +1；已用最大 rf-1024，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1006** | 弱证据断言（一个用例的全部断言只有 `is not None` / `isinstance` / `len>0` / 裸真值，只证明「不崩/非空」）。**口径**：计入 `unittest` 断言后 143 例、再扣除 `assert_called*` 等 mock 断言后**真弱 75 例**（`self.assertEqual` 与 `assert_called_once_with` 不属无断言） | 统一以「用例名承诺了什么」为判据：**已强化 28 例**——trace 守卫 4 文件 24 例改为断言命中的**规则分类**（`_code_cat`/`_doc_cat`；`_code_hit`/`_doc_hit` 收敛为兄弟模块单源导入）、熔断网关 4 例改为同一实例/稳定快照断言；**判读接受 47 例**（`isinstance` 类型契约 15、`not-none` 对象存在契约 15、非空集合/健壮性 17——名字只承诺类型或存在，现断言即其正确强度，再加强只是换写法）。不入门禁（弱断言与合法 smoke 难静态区分） |
| **rf-1004** | 全量时间炸弹筛查余量：`probe-date-bombs.py --all` 扫出 48 个 rot-suspect 文件，账本族 5 个已修（rf-1002 / rf-1003 / 判别式加固）；余 43 个多为**变异伪信号**（测试日期绑生产侧锚点/跨模块 fixture/星期-财季语义），但未逐个人工判读，不能断言全清 | 逐文件人工判读：`python scripts/probe-date-bombs.py --files <file> -v` 看失败断言，再判断是「日期需近期」还是「语义位移」。**自动化重定基已证伪**——三种策略（锚点 = 当天−30d / 当天 / 周对齐平移）分别只通过 4 / 0 / 2 个文件，说明失败主因不是「距 now 变远」，批量改写不安全。静态守卫（`check-test-redundancy` 第 9 类）只覆盖账本日期实参，其余类不入门禁 |

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1024** | both 路径（HTML+Excel 同跑）未接线 `decision_review_data`：`_generation_both.py` 既不装配该契约、也未向 `write_html_report` 转发，`decision_reflection`（实验、默认关）开启时行动章「决策跨期反思」块在该路径整块不渲染（full 路径正常；同类缺口：判断依据块双路径漏传已修复） | 参照 full 路径 `record_deterministic_decisions` 后取值接线；落地前先确认 both 路径 Excel 端是否同缺。属实验功能，排期跟随 `decision_reflection` 启用决策 |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 9 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 781 行（主程序登记线 700） |形态 A 章内块装配已含信号清单/可信度/风险预算/纪律/结算/约束六段；拆分方向：信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可下沉 `decision_basis_signals.py`，风险预算/纪律/结算各成一簇（均只读输入、互不依赖） |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 782 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；余量约 6 行，下一项报告页改动即触线 |

## 已解决问题

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-01）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
