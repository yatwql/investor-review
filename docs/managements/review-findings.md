# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.18.5-dev
> **编号源**：`rf-next = 1176`（新增问题提出后更新为 +1；已用最大 rf-1175，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

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

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线（主程序 700 / 脚本 600 / 测试 900）即登记。下表为存量监控项（红线：主程序 1000 / 测试 1200，触线必须拆分）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/conftest.py` 1199 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 与装配 |
| `src/python/core/perf.py` 799 行 | 采集器与台账落盘可拆（`perf` 采集 / `perf_history` 读写两文件） |
| `src/python/core/doctor.py` 787 行 | 检查项按域分文件（环境 / 配置 / 数据源 / 报告产物），入口只留编排 |
| `src/python/llm/fact_checker/_numerical.py` 764 行 | 数值校验按规则族拆（金额 / 比率 / 计数），共享解析原语上提包内 `_common` |
| `src/python/tui/handlers_config.py` 743 行 | 配置面板按域拆（内容选项 / 全局设置 / 目录与文件名） |
| `scripts/_doc_drift/_format.py` 742 行 | 格式化规则按文档类型拆（章节 / 表格 / 树 / 统计） |
| `src/python/core/degradation.py` 768 行 | 状态词与事件模型、登记面与持久化可拆两文件 |
| `src/python/report/action_sheet.py` 752 行 | 行动页签内各块（建议表 / 判断依据 / 决策书 / 复盘）拆子模块 |
| `src/python/fetcher/financial_report.py` 719 行 | 按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/python/providers/akshare_extras.py` 716 行 | 按接口族拆（指数 / 行业 / 分红 / 盈利预测） |
| `src/python/core/provider_registry.py` 710 行 | 熔断与会话缓存各自独立文件 |
| `src/python/llm/skeleton.py` 877 行 | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染） |
| `src/python/cli/_handlers.py` 890 行 | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄 |
| `src/python/tui/handlers_holdings.py` 825 行 | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于风险，暂不拆 |
| `src/static/tmpl/report_template.html` 277 行 | 样式已抽到 `partials/_report_styles.html`，各自单一关注点，均未触 1000 行 |
| `src/static/tmpl/whatif_template.html` 543 行 | **不在行数守护域内**（`check-file-length` 只扫 `.py`）；样式已抽到 `partials/_whatif_styles.html` |

## 已解决问题

### 开发期已修复（0.18.5-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。
| **rf-1167** | `prepare` 的 plan 归档只认「完成标记」标题，而本周期 9 个已完成节写成 `` `plan-N` 标题 `` 无标记 → **静默漏档**：既不进 `archived_plan.*`、也不报错，靠发布时人工复核才捞出（否则这批完成项永久留在主台账） | 归档前兜底：新增 `unmarked_completed_plan_sections()`，`apply_plan_archive` 发现缺标记即抛 `ReleaseError` 并点名 `plan-N` + 给出可照抄写法；配 3 条用例（只报未标记 / 报错点名 / 全标记正常归档）；`developer-guide` 发布流程首段写明该硬约束 |
| **rf-1168** | 截断重试丢首次调用用量：`_handle_truncation` 返回重试那次 `usage`，覆盖了被截断那次真实花费（截断模块可低估近 2 倍）；重试失败时 `return result, None` 连首次用量一并丢 → 成本台账少算 | 新增 `_merge_usage()`（按 key 递归累加，缺失一侧取另一侧），重试成功/失败均返回两次合计；配 2 条用例（合并求和且不改写首次对象 / 重试失败仍留首次用量） |
| **rf-1169** | 性能门禁只卡 basic（Phase 1 Excel 一段），而实际使用最多的是 full 档（数据准备+新闻+穿透+双输出）——full 退化（数据准备中位 24s → 尾部 40s）无任何门槛拦截 | `test-perf-report.py` 新增 Phase 4（full 全链路，LLM 已 mock、其余离线桩同源）；`_perf_report/report.py` 增 `_TARGET_FULL_SECONDS`（300s，待 CI 基线收紧）与报告行/结论段；`--gate` 改为双口径任一超标即退出 2 |
| **rf-1170** | `llm_settings.json` 里 `max_tokens_*` 低于本版出厂默认时静默生效（实例：`max_tokens_self_review=2048` vs 默认 8192）——满编持仓必然触顶，触顶会**自动放大重生成一次 = 多一次计费调用**，用户在报告里只看到 WARNING，根因无从追溯 | `_validation_llm` 新增 `_below_default_advisory()`：加载期点名「当前值 / 本版默认 / 代价」，合法值不回落不改写；配 2 条用例（低于默认保留原值并出提示 / ≥默认不产生提示噪声） |
| **rf-1171** | 多处 `except Exception` 无任何日志的静默降级：`core/concurrency.py` 配置读失败 → 并发档位静默变 high；`core/data_freshness.py` 交易日历/阈值回落无痕；`report/_report_factor_metrics.py` 单品种 K 线失败与「真无数据」不可区分 | 逐处补日志（并发档位回落用 WARNING + exc_info，其余用 DEBUG + exc_info）；其余仅探针性质（doctor 健康检查等把失败当结果返回）不动 |
| **rf-1172** | 持仓文件缺失只报「文件不存在（路径: X）」：目录本身不存在（旧机器/旧版本配置残留，本机曾实测指向一个已不存在的路径）与「目录在、文件名对不上」两种情形修法完全不同（改 `holdings_dir` 还是改 `holdings_filename`），原提示两者都说，用户会在错误的配置键上来回试 | 新增 `_missing_holdings_hint()` 分三种情形给可执行修法（目录不存在 → 点名 `holdings_dir` 且提示旧配置残留；目录在 → 列出该目录现有 xlsx 并点名 `holdings_filename`；空目录 → 提示放文件）；配 3 条用例 |

| **rf-1173** | `test-perf-report.py`（及真实报告）本机必崩/挂死：`Segmentation fault`（退出 139）与退出期死锁。`-X faulthandler` 原栈先指向 akshare 财务指标链，实为**栈顶 `py_mini_racer.MiniRacer.__del__` → `dll.mr_free_context`**；`git stash` 后在 `HEAD` 上同样复现。逐层定位出三种崩法（两条线程先后 init V8 / 上下文跨线程 GC / 上下文活到退出期）——都是原生崩溃，`try/except` 与 pytest 一律拦不住；且实测**主进程内无论专用线程、全局锁、就地回收都留活口**（异常栈帧与第三方内部引用会把上下文留到下一次 GC） | 改为**子进程隔离**：新增 `core/v8_subprocess.py`（白名单接口 + JSON 契约 + 超时杀子进程 + 离线开关），`tool_trade_date_hist_sina`（交易日历）与 `stock_fund_flow_industry`（同花顺资金流备用通道）改走子进程，主进程只收 records；配 12 条用例（白名单/JSON 契约/子进程错误与超时降级/日历与资金流接线/主进程禁直调契约）与离线契约（基准与测试都把「子进程也离线」传下去，防止测试偷偷走真实网络）；基准连续两轮退出码 0 |

| **rf-1175** | 近 213 小时变更审计发现两处结构性重复（同一套口径写了两份，改一处漏一处即口径分叉）：① `fetcher/fund.py` 的 `fetch_fund_rankings_cached` / `fetch_fund_holdings_cached` 是同一会话缓存包装的两份拷贝；② `core/perf.py` 的 `load_health_history` / `load_history` 是同一 JSONL 台账读取的两份拷贝 | ① 抽出 `_session_cached(namespace, code, fetch)`，两处各留一行调用（`NOT_FOUND` 命中语义与 `source="api"` 来源标注集中在一处）；② 抽出 `_load_jsonl_records(path, label)`（不存在→空 / `OSError` 不上抛 / 坏行 WARNING 三口径单源），两条台账共用。既有 fund/perf 用例全绿（2490 条） |

| **rf-1174** | 近 213 小时变更审计：5 个超长函数到「改一处要通读全文」的程度（`write_html_report` 349 / `generate_debate_procon` 311 / `_generate_report_full` 303 / `_write_decision_basis_block` 275 / `prepare_report_data` 270 行） | 全部按阶段拆分，入口只留编排：`write_html_report` 349→185（`_prepare_page_state` + `_build_template_context`）；`prepare_report_data` 270→176（8 段数据准备各自成函数，perf span 与调用序不变）；`_generate_report_full` 303→191（数据准备/快照注入/峰值重建/LLM 后处理各自成阶段函数）；`generate_debate_procon` 311→233（白脸黑脸收敛到 `_run_debate_side` 消掉两份逐字重复、配置解析与综合段各自成函数、删掉随之失效的会话缓存闭包）；`_write_decision_basis_block` 275→41（信号/风险预算/纪律/结算四子节各自成函数）。三处按源码位置/条数断言的测试改为结构性定位（装配点动态查找、挂载点按主编排调用序展开、缓存键按「是否用共享常量」判定），使重构搬动函数时守卫仍成立 |

### 归档档案
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-18）
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-10）
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
