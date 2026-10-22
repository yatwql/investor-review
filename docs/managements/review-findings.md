# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.6-dev
> **编号源**：`rf-next = 829`（新增问题取此编号，完成后更新为 +1；已用最大 rf-828，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-823** | **TUI 页头「新鲜度」阈值自定且用自然日**：`tui/status_line.py:36` `_STALE_DAYS = 7`、`:101-103` 用 `(now.date() - date).days` 判黄——既绕过配置（`report/data_status.py:113` 默认 T2=3 / T3=14 / T4=7，可按 `degradation.*.stale_days` 覆盖），也绕过交易日口径（架构约束要求「数据新鲜度/观察期」以交易日计，自然日在长假处会被放大）。后果：页头显示「正常」而报告内数据质量已判「延迟」，同一份数据两处结论不一致 | 下沉 core：新增 `core/data_freshness`（或既有模块）的「页头新鲜度摘要」函数——阈值取配置分层值、距离取交易日（`get_last_trading_day`/`count_trading_days_elapsed`），TUI 只负责着色；补「T2=3 天已告警时页头同样告警」与「长假不误报」两例回归 |
| **rf-824** | **同一 doctor 检查在三渠道各有不同耗时预算**（渠道层字面量）：CLI `--timeout` 默认 8（`cli/_parser.py:248-251`）、Web `run_health_checks(max_timeout=12.0)` 与 `run_doctor_checks(...)`（`web/handlers.py:549/580`）、TUI `_DOCTOR_NETWORK_TIMEOUT = 6.0`（`tui/handlers_log.py`）。同一环境同一检查，三渠道结论可能不同（慢源在 6s 判超时、在 12s 通过），且改预算要改三处 | 预算单源：在 `core/doctor.py`（或 `config` 默认值）声明 `doctor_network_timeout` 默认与下限，三渠道只允许「覆盖」不允许「另立默认」；Web 前端 abort 余量由同一常量推导。补「三渠道默认预算一致」的结构回归 |
| **rf-825** | **`output_dir` 回退链在渠道层重复 12 处**：`cli/_handlers.py:329/437`、`web/handlers.py:394/531`、`web/run_generation.py:166/203`、`web/server.py:149`、`web/config_edit.py:82`、`tui/handlers_qa.py:82`、`tui/handlers_whatif.py:179`、`tui/tui_menu.py:215`、`tui/report_artifacts.py:43`——其中 `"reports"` 字面量 3 处（`cli/_handlers.py:329`、`web/run_generation.py:203`、`tui/report_artifacts.py:43`）与 `get_default("output_dir")` 混用，改出厂默认或加「相对路径转绝对」规则时必漏改 | 下沉 config 层唯一解析器（如 `config.resolve_output_dir(config, override=None)`，内部含默认值 + 绝对化），三渠道一律调用；补「缺键/相对路径/CLI 覆盖」三例回归 |
| **rf-826** | **`llm_settings.json` 原始读取在渠道层有两份**：`tui/handlers_config._read_llm_settings`（自行解析 JSONC 供面板展示）与 `web/config_edit.py` 内联读文件（`enabled_llm` 直读源文件，缺失键当默认开）。配置层已有 `get_llm_config()`（合并默认）与 `config/edit_ops`（编辑面读取）——渠道各读一份易与默认合并规则分叉（如新增键后某渠道仍显示旧值） | 由 config 层提供唯一「原始值 + 有效值」读取入口（如 `load_llm_settings_raw()` / `get_llm_config()` 明确分工），渠道只消费；补「缺键时三渠道展示一致」回归 |
| **rf-827** | **KB/MB 尺寸格式化 4 处重复**：`tui/handlers_whatif.py:49`、`tui/tui_handlers.py:178`、`tui/handlers_cache.py:235-271`（另含 `1024` 多份判定）、`cli/_handlers.py:554`——同一「KB/MB 取整规则」各写一遍，改精度或单位要改四处（且四处的取整位数已不一致：`:.0f` vs `:.1f`） | 收敛到 core 单函数（如 `core/num_utils.format_size(bytes, *, unit_hint="auto")`），三渠道共用；补边界（1023.9B / 1.0MB / 0B）回归 |
| **rf-828** | **TUI「异常→用户提示」映射在渠道层**：`tui/tui_handlers.py:62 print_error_with_hint` 用关键词（connect/timeout/permission/config…）把异常翻成「检查网络/检查权限」提示——属共性诊断规则，Web/CLI 无同等能力（Web 走 error_code 信封、CLI 直接打印异常串），同一故障三渠道说法不一 | 下沉 `core/error_hints.py`（纯函数 `hint_for(exception/text) -> str|None`），TUI 只负责上屏、Web 可并入信封 message、CLI 可用于 stderr 提示；补映射表全表用例（每条关键词 → 提示语） |

### P3 — 持续监控：文件膨胀登记（按任务号组织；逼近红线档 主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000）

> **单一事实源**：行数以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序 / >400 行脚本 / >800 行测试）。本表是**逼近红线档的处置登记**——主程序 ≥700、脚本 ≥600、测试 ≥1000（余量 ≤30% 才入表），行数快照随复核刷新；警告级全集不逐项登记，复核以 `-v` 为准。
> **组织方式**：按**任务号（`rf-N`）**分组——一个处置任务涉及多个文件时归在同一行，文件与行数/余量列在该行的「涉及文件」列里（同一文件只出现一次，行内按任务清单顺序）。行内余量取该任务内**最紧**那个文件，表按此升序——即「哪个任务最先触线」排最前，与逐文件排序给出的先后判断一致。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件拆分」。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线）；≥1000 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

> 当前无逼近红线档的文件（主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000 均无在册项；警告级全集以 `check-file-length.py -v` 为准）。

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
