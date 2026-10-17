# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.6-dev
> **编号源**：`rf-next = 704`（新增问题取此编号，完成后更新为 +1；已用最大 rf-703，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题


### P1 — 高优先：不做的风险高（尽快执行）

> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过（修复后 35/0/2 + smoke 11/11；④ 375px 经 rf-644 修复后全过；结论与复跑方式见验证文档；脚本与证据在 git 忽略的 `docs/tmp/rf257/`，重跑即建） | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单；勾选清单留存 [`docs/archive/v0.10.x/web-ui/web-ui-verification-checklist.md`](../archive/v0.10.x/web-ui/web-ui-verification-checklist.md)）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 入选标准：修复路径清晰、成本可控；rf-114 须待 rf-113 人工验证完成后执行（**已满足**：rf-113 已于 2026-10-16 完成）。

| # | 问题 | 修复方向 |
|---|------|----------|

| **rf-114** | 双渲染路径共存——模板保留 Canvas `drawSimpleChart()`（265 行内联 JS）+ Chart.js 渲染器，Feature Flag OFF 时回退 Canvas 路径 | 删除 `drawSimpleChart()` + Canvas 回退分支 + Feature Flag 条件分支，Chart.js 成唯一渲染器；**前置已满足：rf-113 人工验证完成（2026-10-16，确认 Chart.js 真机渲染可靠）**；触发条件：plan-1 稳定 2 版本（阶段 2→3 切换，判定标准见 upgrade.md §4.15） |


### P3 — 持续监控：文件过长登记表（>500 行观察，脚本域 >400 即入观察 / **>1000 行为硬上限必须拆分**（主程序与脚本）；按距红线余量升序）

> **派生源**：行数与全集以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序、>400 行脚本、>800 行测试文件）；红线（主程序/脚本 >1000 行、测试 >1200 行）由 `check-file-length.py --ci` 自动拦截（豁免路径与本表挂账同步），不依赖本表人工发现新破线者。本表仅登记需跟踪/决策的文件，**触发式处理**：未逼近红线不排期，逼近时按本表拆分建议执行。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件红线体系（主程序/脚本/测试）」决策记录。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线），**当前无挂账项**；警告级全集以 `scripts/check-file-length.py -v` 为派生源，逼近红线（1200 行 / 120 项）时按「被测函数 / 场景类型」拆分为同目录兄弟分片，并同步刷新 `test-coverage.md` / `folders.md` 用例计数。

| # | 文件 | 行数 | 状态 | 拆分建议 |
|---|------|------|------|----------|

| **rf-626** | `llm/prompts_core.py`、`llm/generators.py`、`report/html_writer.py`、`analysis/rebalance.py` | 350 / 444 / 796 / 751 | **临界带四文件登记项**：`html_writer`(796)/`rebalance`(751) 距 1000 红线余量 204/249，`-v` 月度复核 | `html_writer`/`rebalance` 逼近 980 行启动拆分（域下沉 + 门面 re-export + 测试 patch 改指持有子模块） |
| **rf-86** | `cache/operations.py` | 739 | 500-1000 可选优化区间，增长偏快，`-v` 按月复核 | 数据结构定义/基金刷新/公共缓存/持仓缓存/缓存清理 5 个职责 |
| **rf-79** | `core/code_utils.py` | 766 | 500-1000 可选优化区间，维持现状，`-v` 按月复核 | 可考虑将 `estimate_market_cap_by_prefix()` 等非核心判定函数移出（不拆） |
| **rf-665** | `config/features.py`、`_doc_drift/_format.py`、`tui/handlers_config.py` | 737 / 558 / 534 | 500-1000 可选优化区间，`-v` 按月复核 | `features.py` 随注册表逐开关增长（每项 ~10 行），逼近 980 行时考虑将 `FeatureSwitchDef` 字段声明/注册表条目下沉独立子模块；另两文件由 `-v` 月度复核 |
| **rf-89** | `report/excel_generator.py` | 659 | 500-1000 可选优化区间，增长偏快，暂维持现状，`-v` 按月复核 | 页签编排可进一步下沉到独立 writer（后续择机） |
| **rf-80** | `report/data_status.py` | 622 | 维持现状（DegradationTracker 单类，内部职责内聚） | DegradationTracker 单类偏大（不拆） |
| **rf-81** | `report/html_renderers.py` | 577 | 维持现状（render 函数同属渲染域） | 所有 HTML render 函数揉合一体（不拆） |
| **rf-85** | `fetcher/fund.py` | 553 | 500-1000 可选优化区间，暂维持现状，若再增则按职责拆分 | 排名/持仓/基准三职责可拆分为子模块（后续择机） |
| **rf-78** | `fetcher/batch.py` | 520 | 维持现状（BatchDispatcher 内聚，复核确认不拆） | BatchDispatcher 本身内聚，可维持现状（不拆） |

## 已解决问题

### 归档档案

- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-17）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x 已修复批次与开发期追加（2026-10-03 ~ 2026-10-12）
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

### 开发期已修复（0.13.6-dev）

> rf-702 已修复（2026-10-17）：LLM 计费口径统一——Anthropic 兼容端点 `input_tokens` 仅计未命中，与 `cache_miss = input − hit` 公式相减产生负费用；`estimate_cost` 补 `max(…, 0)` 下限，归一层把 claude 协议 `input_tokens` 补 `cache_read_input_tokens` 归一为总输入（详见 changelog）
>
> rf-703 已修复（2026-10-17）：会话/报告费用统计与单次估算口径统一——报告页脚、批处理汇总、新闻相关性估值均改走 `_normalize_usage_tokens` 归一层，会话累计费用与单次 `estimate_cost` 同参等值（回归用例已补）
>
> rf-701 已修复（2026-10-17）：openai 分支补读 DeepSeek 原生端点顶层 `prompt_cache_hit_tokens`（优先于 `prompt_tokens_details.cached_tokens`）；字段名以官方 API 文档核实（顶层 hit/miss 且 `prompt_tokens = hit + miss`），回归用例已补
>
> rf-700 已修复（2026-10-17）：LLM 模型定价表 5 处偏离官方现价——`MODEL_PRICING` 的 Claude Opus 4.x 仍按旧旗舰价 15/75（官方 $5/$25）、Haiku 4.5 仍按 Haiku 3 价 0.25/1.25（官方 $1/$5）、Fable 5 误植 Sonnet 价 3/15（官方 $10/$50）、Gemini 3.5/2.5 Flash 仍按预览期价 0.15/0.60（GA 价 $1.5/$9.0、$0.30/$2.50）、2.5 Pro 输出价 5.00（官方 $10.00）、OpenAI 缓存命中无折扣（官方 50% 折扣）——逐家官方定价页核实后统一修正，并同步 `llm-technical.md` 附录 B 与 `how-to-config-llm.md` 定价表（用户实际在用的 DeepSeek 峰谷价与 Kimi 价经核实无偏差）

### 开发期已修复（0.13.3-dev）

> 本批摘要已随 v0.13.3 发布迁入 [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md)；此处不再保留。

### 开发期已修复（0.13.4-dev）

> 本批摘要已随 v0.13.4 发布迁入 [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md)；此处不再保留。

### 开发期已修复（0.13.5-dev）

> 本批摘要已随 v0.13.5 发布迁入 [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md)；此处不再保留。
