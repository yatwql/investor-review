# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.15-dev
> **编号源**：`rf-next = 1000`（新增问题提出后更新为 +1；已用最大 rf-999，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 8 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 782 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板已收口到 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；余量约 6 行，下一项报告页改动即触线 |

## 已解决问题

### 开发期已修复（0.16.15-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-995** | 设计护栏 W4 字号档外 8 处：`font-size: 0.95rem`（15.2px），折算后不在字阶 11/12/13/14/16/17/18/20/22px 上 | 统一取 `1rem`（16px），行高与间距不变；护栏 W4 归零 |
| **rf-996** | 设计护栏 W5 间距档外 172 处：实现停在 6/10/14/18/20 等中间档，与 DESIGN.md 间距阶 0/4/8/12/16/24/32 不符 | 全部吸附到间距阶（等距取小值）；侧栏 220px 收敛为 `--toc-width` token、`.sr-only` 与汇总片负值归零；护栏 W5 归零 |
| **rf-997** | 单次运行写盘相位异常：HTML 18.1s / Excel 10.6s（同口径中位 0.2 / 0.3s），产物尺寸与历史一致 | 同环境复跑两次均 0.03 / 0.23s，宿主 I/O 探针（顺序写 2905 MB/s、905K 落盘 1.1ms）正常 → 瞬时宿主负载、非代码缺陷，观察关闭 |
| **rf-998** | 命中内容缓存的模块仍带费用、「使用缓存」标记失真：会话累计值未按本次裁剪，逐模块 `costs` 整字典照搬，汇总表与用量页签同源失真 | `_usage_delta` 逐模块 `costs` 按币种做差、`cached` 按本次有无 token 增量判定；`record_per_module` 真调用时翻回 `False`；历史台账按各次真实花费重分配；回归 1 例 |
| **rf-980** | 版切首跑「明细装配与建议」长尾：10.5s vs 常规 0.45s | 两次版切首跑 0.544s / 0.948s 不复现；该阶段长尾散见多版本、与版切无关 → 观察关闭 |
| **rf-999** | 报告层结构性债：单函数 >120 行 57 个（最大 `generate_excel_report` 466 行、`_generate_report_full` 391、`write_html_report` 378、`generate_all_llm` 372），签名 ≥13 参数 31 个（最劣 `_render_template` 80 个关键字参数、`write_html_report` 49、`_generate_full_html_report` 44、`generate_excel_report` 32）——参数镜像模板上下文，改一个字段要动签名与调用两侧；`check-file-length` 只看文件行数，函数级/签名级阈值不在守护域内，故长期未被拦 | 分两刀走：① 先给 `_render_template` 引入 `RenderContext` 数据类（单调用点：`html_writer` + 用例内 `_build_minimal_render_data`），把 80 参数收成一个入参；② 再按域拆 `generate_excel_report` / `write_html_report`（页签族上下沉），每刀以「模板 golden hash 不变」为验收；拆完补一条函数级行数与签名参数数的守护（阈值待定，先观察） |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-30）
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
