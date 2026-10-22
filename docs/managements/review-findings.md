# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.6-dev
> **编号源**：`rf-next = 831`（新增问题取此编号，完成后更新为 +1；已用最大 rf-830，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 当前无待办项（rf-790 已决策「维持现状」并归档至已解决）。

### P3 — 持续监控：文件膨胀登记（按任务号组织；逼近红线档 主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000）

> **单一事实源**：行数以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序 / >400 行脚本 / >800 行测试）。本表是**逼近红线档的处置登记**——主程序 ≥700、脚本 ≥600、测试 ≥1000（余量 ≤30% 才入表），行数快照随复核刷新；警告级全集不逐项登记，复核以 `-v` 为准。
> **组织方式**：按**任务号（`rf-N`）**分组——一个处置任务涉及多个文件时归在同一行，文件与行数/余量列在该行的「涉及文件」列里（同一文件只出现一次，行内按任务清单顺序）。行内余量取该任务内**最紧**那个文件，表按此升序——即「哪个任务最先触线」排最前，与逐文件排序给出的先后判断一致。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件拆分」。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线）；≥1000 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

**逼近红线档处置登记**（余量 ≤30% 才入表；按「哪个任务最先触线」排序）：

| 任务 | 文件 | 行数 / 余量 | 处置方向 |
|------|------|------------|----------|
| **rf-829** | `scripts/release.py` | 992 / **8**（红线 1000） | **优先**：把 `build_parser()`（约 77 行）+ `main()` 的 argparse 装配抽到 `_release/_cli.py`，常量随之下沉并 re-export；在拆分前**禁止**再向该文件加逻辑（任何新增都可能直接破线） |
| **rf-829** | `src/python/core/doctor.py` | 734 / 266 | 日志与缓存探针（`_check_logs_and_cache`）可独立成 `core/doctor_logs.py`，主模块只保留分组与渲染 |
| **rf-829** | `src/python/web/handlers.py` | 709 / 291 | 路由按域拆分（`handlers_health.py`：health/doctor/logs；`handlers_reports.py`：生成/下载/历史），蓝图注册保持单源 |
| **rf-829** | `src/test/unit/news/test_news_sources.py` | 477 / 723 | 已分片出 `test_news_dedup.py`（本次完成）；后续按「源元数据 / 抓取行为 / 标题判定」继续切 |
| **rf-829** | `scripts/check-doc-traces.py` | 692 / 308 | 结构性冗余扫描已下沉 `_traces_doc/`，CLI 侧再收薄（参数与输出归 `_checklib`） |
| **rf-829** | `scripts/check-style-guardrails.py` | 636 / 364 | 规则表与渲染分离（规则声明 → `_guardrails/rules.py`） |
| **rf-829** | `scripts/test-perf-report.py` | 635 / 365 | 采样/统计/上屏三段拆分，采样复用 `core/perf` |

**已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：

| 任务 | 文件 | 行数 | 决策依据 |
|------|------|------|----------|
| **rf-89** | `src/python/report/excel_generator.py` | 659 | 维持现状：页签编排后续可下沉 |
| **rf-80** | `src/python/report/data_status.py` | 649 | 维持现状：DegradationTracker 单类内聚 |
| **rf-81** | `src/python/report/html_renderers.py` | 577 | 维持现状：渲染域同源 |
| **rf-85** | `src/python/fetcher/fund.py` | 553 | 维持现状：排名 / 持仓 / 基准三职责择机拆 |
| **rf-78** | `src/python/fetcher/batch.py` | 520 | 维持现状：BatchDispatcher 内聚 |
| —（同批决策） | `src/python/llm/prompts_core.py`、`src/python/llm/generators.py` | 350 / 444 | 维持现状：提示词 / 生成器按模块分文件 |

## 已解决问题

### 开发期已修复（0.14.6-dev）

> 完整复盘见 `changelog.md` 0.14.6-dev 段；此处为台账原表（发布时随 `release.py prepare` 迁入版本归档）。

| # | 问题 | 处理 |
|---|------|------|
| **rf-830** | TUI 按 `Q` 追问稳定返回「服务暂不可用」：日志为 `'utf-8' codec can't encode characters … surrogates not allowed`，且两个 provider 的失败位置只差模型名长度（`55414` / `55410`）→ 失败发生在建连前的请求体序列化，**不是**网络/配额。根因：POSIX 下 `sys.stdin.errors == 'surrogateescape'`，终端送入的非法 UTF-8 字节被 `input()` 解成孤立代理项（U+D800~U+DFFF），问题首字命中时 httpx 以 `ensure_ascii=False` 序列化请求体，`.encode("utf-8")` 抛 `UnicodeEncodeError`；该异常是 `ValueError` 子类，被 `_attempt_api_call` 的 `except (ValueError, KeyError)` 归为「响应解析失败 / api_error」，导致整条 provider 链无谓失败 | 已修复：新增 `core/text_safety.py`（合法代理对折叠为星平面字符、孤立代理项→U+FFFD，与 UTF-8 `errors="replace"` 同口径），在 **LLM 请求体**（`call_llm_with_retry` 入口递归净化全部字符串）、**LLM 响应正文**（`_process_success_response`，防响应 `\udXXX` 写 HTML 时再炸）与**追问入口**（`qa.session` 问题入库/入日志前净化）三处过关。回归用例：`test_text_safety`（净化口径/递归载荷）+ `TestLoneSurrogateBoundary`（真实 `httpx.MockTransport` 下带孤立代理项的请求体能发出、响应正文可编码）+ `TestQuestionSurrogateSafety`（问题与历史存净化后文本） |

### 归档档案
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-22）
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
