# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.5-dev
> **编号源**：`rf-next = 1077`（新增问题提出后更新为 +1；已用最大 rf-1076，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1155 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 919 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 848 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 852 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 855 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 729 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.5-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1065** | 用例审计（四维）发现 4 处名实不符/断言强度不足：①幻觉采样 `test_wrong_profit_rate_vs_portfolio` / `test_mixed_correct_and_wrong` / `test_missing_code` 只断言 `len(issues) >= 1`，任意无关告警都能转绿，测不出「对照的是组合收益率/涉事个股/涉事代码」这一口径；②`test_intraday_written_cache_expired_right_after_close_gate` 名称称「已过期」而断言「仍可读」，方向相反 | ①三处补点名断言（`累计收益率`+实际值 / `600036` / `002837` in issues[0]），与仓内已有 `test_wrong_stock_return` 同标准；②用例改名为 `..._survives_static_ttl_after_close` 并在 docstring 写明只验读侧（收盘门禁由同文件 TTL 口径用例覆盖） |
| **rf-1066** | `test-coverage.md` 蹿入历史复盘痕迹与失真导语：①两条带日期的「门禁口径变更」告示（变更记录，已在 changelog/归档）；②其中一条把上方耗时表的 `dev-verify`/`verify` 行标为「并入前快照」，而该表已重测，属错误导语；③「两机差距」段内联绝对耗时与紧邻其上的表相互矛盾；④旧采集事故叙事带当日数字 | 删除两条变更告示、改指口径真源 `technical.md` §4.23；两机差距只保留按表重算的比例区间；事故叙事改写成不带日期的排查口径（先查未 mock 外部访问） |
| **rf-1067** | 8 份文档正文残留历史复盘痕迹（带日期的「已采纳/已落地/收紧」告示、「曾经的写法」「曾占…现口径」对照叙事、「此前只存在于…」式缺陷描述）。这类内容与当前状态无关，且会随演进腐化为错误导语（读者据此判断「表不可信/行为待变」） | 全部改写为当前状态陈述：告示去掉日期与「已采纳」口吻只留规则；对照叙事改为风险机制陈述（若…则…）；缺陷描述改为要求陈述；指针类内容（口径、判据）改指真源 |
| **rf-1068** | 程序注释里的历史复盘叙事：`src/python` 47 处、`scripts` 19 处、`src/test` 44 处（「此前 X 现在 Y」「原先各写一份」「曾占…」式对照，以及带日期的校准/收紧告示）。这类注释随演进腐化：读者据此以为行为待变或表不可信 | 除「回归背景/回归场景」元描述（`CLAUDE.md` 明确豁免、用于说明断言存在理由）外，全部改写为当前状态：对照句改「若/不得 X，否则 Y」，告示去日期留规则，重命名史改「不得沿用旧称」 |
| **rf-1069** | 静态类型检查暴露的真缺陷与类型债：①`scripts/_eval_halluc_sampler/llm_call.py` 调 `_build_global_macro_prompt` / `generate_global_macro` 少传 `total_cost`，`categories` 落在 `total_cost` 位、`categories` 缺参——该评测脚本 global_macro 路径运行时必抛 TypeError；②6 文件存量 Pyright 错误：`_is_number` 非 `TypeGuard` 致 11 处数值运算报 Unknown、`get_llm_setting_default` 返回 object 直取键、`_max_tokens`/`_LAST_FP_COMPONENTS` 可能为 None、`wb.active`/`find()` 返回 Optional 直接下标、`cached` 可能未绑定、`json.loads`/`os.makedirs` 未包 try | ①补 `total_cost` 实参并初始化 `cached=False`；②`_is_number` 改 `TypeGuard[float]`、默认值取键前 `isinstance(..., dict)` 收窄、`_max_tokens` 显式兜底 18432、测试侧 `_require_section()` 断言取节点、`wb.worksheets[0]` 替代 `wb.active`、I/O 调用包 try 并保留原异常语义 |
| **rf-1070** | 近 96h 变更残留两处技术债：①去 Jinja 化批次加了三组工具类，但只有 `.fill-alloc-*` 被 SVG 用上，`.bg-primary`/`.bg-alloc-mid`/`.bg-alloc-low` 无任何引用（死样式，规则集哈希把它当既定事实）；②`close_html_generation_stage`（rf-1060 抽出的full/both 共用收口）只被端到端用例间接触及，自身的三个分支（无 recorder / 无分段 / 有分段分流）无直测 |①删 3 条死规则并重标定 CSS 规则集哈希（评审动作）；②补 4 条直测：无 recorder 静默返回、有分段时按「落盘」告警、渲染慢指向模板而非磁盘、无分段回落总值 |
| **rf-1071** | 违背「控制台着色单源 + NO_COLOR/TTY 降级」约束（架构约束表内条目）：`core/doctor.py` 与 `report/cli_progress.py` 各自硬写 `\033[...` 转义码并各自复制 `NO_COLOR`/`isatty` 判定——`core/ansi_colors` 已是唯一色源与降级实现，两处却另写一份，改配色或降级口径时会漏改 |`ansi_colors` 增 `RAW_CODES`（原样码表）与 `supports_color(stream)` / `codes_for(stream)`（按**指定流**判定着色能力，解决「stdout 被重定向致 stderr 失色」）；两模块改调前者，删掉各自的转义码字面量与 `NO_COLOR` 判断 |
| **rf-1072** | 兼容面盘点（七类：旧配置项/旧配置文件/旧数据文件/旧数据结构/旧缓存结构/旧缓存文件/旧内部接口）发现 1 处**旧内部接口门面**：`core/data_freshness._detail_value` 是 `core/detail_view.detail_value` 的一行转发（docstring 自述「本函数仅保留旧名」），`holding_status` 也经它取值——改名后保留旧名属多余的兼容残留 |删旧名门面，`data_freshness` 内部与 `holding_status` 一律直调 `detail_value`（单源在 `core/detail_view`）；顺带把 `detect_price_jumps(details)` 形参放宽为 `list \| None`（实现本就以 `details or []` 容忍空入参）并给 3 处 `header_freshness` 调用补 `is not None` 断言 |
| **rf-1073** | 裸解释器启动的 full 报告整份失败：系统 Python（无 pandas/numpy）生成报告时 `ModuleNotFoundError: No module named 'pandas'` 一路冒泡到 `generate_report`，用户只得到「生成失败」。三处根因：①`scripts/launch.sh`/`launch.ps1` 依赖 `activate`，而激活脚本内烘焙的是创建时的绝对 `VIRTUAL_ENV`——venv 目录搬家后 PATH 前置失效、激活静默无效，脚本里的裸 `python3` 落到系统解释器；②`pandas`/`numpy` 从未在 `requirements.txt`/`pyproject.toml` 声明（仅经 akshare 传递安装）；③`analysis/style_factor_regression.py` 在模块顶层 `import pandas`，而 `report/_report_factor_metrics.py` 的导入语句在 `try` 之外，ImportError 直接击穿数据准备阶段，违反 §1.4.5（该区块应 available=False 降级） | ①两个启动脚本改为直接调用 `.venv` 内解释器（与 venv 位置无关）并在启动前用该解释器 import 重依赖做硬闸，缺依赖给可读错误与修复命令；②两库补进依赖清单（单源契约测试同步）；③计算层重依赖惰性导入（`_numeric_stack()` + `TYPE_CHECKING` 类型注释），编排层把计算层导入纳入 `try` 并捕获 `ImportError` → `available=False` 降级；④`core/doctor.py` 增「关键依赖」自检行与 `interpreter_preflight_error()`，TUI/Web 入口启动即拦截 |
| **rf-1074** | 空数据契约键集三处维护（本轮修复留下的债）：`style_factor_regression.unavailable_result`、`industry_beta.unavailable_result` 与 `report/_report_factor_metrics` 的降级兜底各写一份字面量键集，且兜底版 `window` 由 `DEFAULT_WINDOW` 退化成 `0`——加一个契约键就要改三处，漏改即渲染期 KeyError 或契约字段缺失。另 `tui.main()` 的前置检查失败只 `print` + `return`，直连 `python src/python/tui/tui.py` 时退出码仍为 0 | 新增 `analysis/unavailable_contracts.py`（纯字典装配、无 numpy/pandas，正因它是「重依赖坏掉时仍须可用」的那层），两个计算模块与编排层兜底全部委托该工厂（`window` 回到 `DEFAULT_WINDOW` 单源）；补三条单源断言（键集逐键相等 / 契约模块无第三方依赖 / 计算层委托）。`tui.main()` 前置失败改 `raise SystemExit(1)` |
| **rf-1075** | 运行观测三处口径债（`per_module.duration` 含排队、批量模块耗时恒 0、`market_sentiment` 零命中不可判读）：①逐模块 `duration` 记的是 `call_llm` 墙钟，串行端点（`max_concurrency=1`）的排队被算进模型耗时——实测 `expert_review` 记 88.2s 而日志时间戳墙钟约 62s（高估 ~40%），且 `PacingGate` 只记 `min_interval` 等待、不记并发许可等待；②`news_correlation` 走批量骨架，`record_per_module` 未传 `duration`，用量页签恒记 0.0s（实际约 3s），该模块无法归因；③`market_sentiment` 只打「命中 0 条」，事后无法区分「源无条目 / 跟踪标的为空 / 当日确无交集」 | ①`PacingGate` 测量整段过闸等待（含并发许可）并按线程记账（`pop_thread_pacing_wait`），骨架从 `elapsed` 扣除后落 `duration`；观测汇聚器仍记全局白等总量，并新增 `pacing_wait_seconds()` 读口；②`run_batch_mode` 回传本段墙钟（扣排队）→ `batch_usage["duration"]` → 用量落账；③日志补「龙虎榜 N 只 / 连板梯队 M 只 ∩ 跟踪标的 K 只」，并把交易日做成龙虎榜→连板梯队双源兜底（单源缺失时仍给出可读交易日）；补 11 条断言 |
| **rf-1076** | LLM 缓存无时间口径区分：指纹里含行情派生块（申购限购 / 持仓变动 / 环比降级），盘中逐分钟变、收盘后冻结，但缓存判定只看内容与 TTL——盘中反复出报告等于每次全量重算（实测 4 个基础模块 0/4 命中、9 次调用约 130s/¥0.13），而「一律复用」又会让交易时段内的读者拿到十分钟前的盘中结论 | `core/market_hours.py` 新增行情口径桶 `market_snapshot_bucket()`（盘中 / 上午收盘 / 当日收盘 / 上一交易日收盘四档，每轮报告判定一次并由 `generate_report` 入口重置）：盘中档在预检与骨架两处跳过缓存读（归因 `intraday_no_reuse`），其余档同档内可复用；桶键作为后缀进四个基础模块与辩论键的指纹，统一 prompt 附录后追加 `【数据口径】…` 声明，预检摘要旁固定打印本轮口径；补 15 条断言（分档/每轮一次/提示词口径/进键/盘中断复用/收盘复用） |
### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-08）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-13 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-13）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-15 ~ 2026-10-02）
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
