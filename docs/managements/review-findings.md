# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.7
> **编号源**：`rf-next = 836`（新增问题取此编号，完成后更新为 +1；已用最大 rf-835，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 当前无待办项（rf-790 已决策「维持现状」并归档至已解决）。

### P3 — 持续监控：文件膨胀登记（按任务号组织；登记线 = 警告线：主程序 >700 / 脚本 >600 / 测试 >900 / 薄壳 >200）

> **单一事实源**：行数与优先级以 `scripts/check-file-length.py -v` 输出为真值（清单 = 主程序 >700 / 脚本 >600 / 测试 >900、薄壳 >200，并按「行数 × 近 90 天改动次数」给出拆分优先级）。本表是**逼近红线档的处置登记**，**入表线 = 警告线**（单一「警告 = 登记」口径，避免「警告 / 登记 / 红线」三套数字），行数快照随复核刷新。
> **红线体系**：主程序警告 >700 / 硬上限 >1000；`scripts/` 警告 >600 / 红线 >1000；测试 >900 警告 / >1200 红线；`__init__.py` 薄壳 >200 警告（同域红线）。体系调整决策与理由见 `docs/managements/technical.md` C28（大文件红线体系）。
> **测试文件口径**：行数 >900 警告 / >1200 红线；测试项 >80 警告 / >120 红线；≥900 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

**当前无登记项**——三域全部回落到登记线以下，`check-file-length.py -v` 的可选优化清单为空（唯一曾长期在册的 `scripts/release.py` 已由 906 → 331 行，见下「已出登记」）。新增文件触线时按上表口径重新登记。

**已出登记（拆至登记线以下，行数随 `-v` 复核）**：本轮按「行数 × 近 90 天改动次数」优先级逐项处置，共拆出 15 个子模块与 8 个测试分片——

- **主程序**：`web/handlers.py` 709 → 616（只读观测路由 → `handlers_health.py`）、`core/doctor.py` 734 → 608（日志与缓存探针 → `doctor_logs.py`）、`config/__init__.py` 269 → 195（薄壳线内；渠道共享 API → `_config_api.py`）
- **脚本**：`release.py` 906 → 331（命令实现 → `_commands_prep.py` / `_commands_ship.py`，共用原语 → `_commands_base.py`，路径常量与 `env` 投影留入口）、`check-doc-traces.py` 692 → 575（已删函数残留 → `_traces_doc/deleted_refs.py`、结论输出 → `findings.py`）、`check-style-guardrails.py` 636 → 543（规则声明 → `_guardrails/rules.py`）、`test-perf-report.py` 635 → 544（报告渲染 → `_perf_report/report.py`）、`_doc_drift/__init__.py` 237 → 136（薄壳线内；冗余 `__all__` 清单退役，re-export 即为面）
- **测试**：`test_html_report_structure.py` 928 → 783（共享夹具 → `_html_report_fixtures.py`）、`test_orchestrator.py` 999 → 560（快照/历史 → `test_orchestrator_snapshot.py`）、`test_excel_generator.py` 995 → 697（LLM 用量页签 → `test_excel_generator_llm_usage.py`）、`test_holdings_detail_sheet.py` 982 → 744（加权成本/申购状态 → `test_holdings_detail_sheet_cost.py`）、`test_market_value_premium.py` 974 → 767（今日盈亏分支 → `test_market_value_premium_branches.py`）、`test_perf_history.py` 950 → 507（报告段落渲染 → `test_perf_history_sections.py`）、`test_generate_all_llm.py` 926 → 696（并发治理 → `test_generate_all_llm_concurrency.py`）

**已移出登记（降回登记线以下，维持现有模块边界）**：rf-89 `src/python/report/excel_generator.py` 659、rf-80 `src/python/report/data_status.py` 649、rf-81 `src/python/report/html_renderers.py` 577、rf-85 `src/python/fetcher/fund.py` 553、rf-78 `src/python/fetcher/batch.py` 520、`src/python/llm/prompts_core.py` 350 / `src/python/llm/generators.py` 444 —— 均在主程序登记线（700 行）以下，移出逐项登记；行数复核以 `-v` 为准。

## 已解决问题

### 开发期已修复（0.14.7-dev）

（本版开发期已修复项已随 v0.14.7 发布迁入归档档案）

### 归档档案
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) 
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md)
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md)
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md)
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md)
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md)
