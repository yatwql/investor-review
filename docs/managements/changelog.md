# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.6]**（2026-11-19）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.7-dev] - 开发中（未发布）

### 修复

- **自检的缓存目录探针取缓存层唯一解析器（rf-1205）**：`core/doctor.py` 的目录探针把「缓存目录」交给 `cache.get_cache_dir()` 解析——`INVEST_CACHE_DIR` 覆盖（演示/基准运行的缓存隔离入口）生效时，自检上屏的路径、哨兵文件的写入目录就是实际生效目录，隔离 run 的探针不触碰真实 `data/cache`。补 1 条回归（隔离目录下上屏路径 = 解析器结果、哨兵落在隔离目录、真实 `data/cache` 无哨兵残留）。

- **日志配置缺省值单源（rf-1206）**：`core/logging_defaults.py` 承载唯一一张日志缺省值表（`DEFAULTS`/`LEVELS`/`RANGES`），`config/_logging.py` re-export 同一对象，`core/logger.py` 与 `core/doctor_logs.py` 从同包取用——「启动读取 / 面板校验 / 自检回显」三处取的是同一份事实；`_DEFAULT_TABLE_FILES` 的登记同步指向该文件。补 2 条回归（配置回落值等于缺省值表、`config._logging.DEFAULTS is core.logging_defaults.DEFAULTS`）。

- **报告百分比格式化口径单一来源（rf-1207）**：`report/_format.py` 提供 `fmt_pct_points()`（入参是百分数点数）与 `fmt_pct_fraction(value, *, signed=False)`（入参是小数比例），决策依据 / 事件窗对照 / 调仓纪律回放三处调用点按各自口径显式引用对应函数，既有输出字符串保持一致；非数值入参统一回「—」占位，取值失败按缺失呈现而不中断渲染。补 1 个单测（None / 字符串 / 负数 / 0 边界）。

- **两处运行期断言/字典直取的隐性契约（rf-1204）**：`report/decision_llm_capture.py` 原用 `assert code is not None` 收紧「该行必含 6 位代码」——`python -O` 会剥离 assert，优化模式下 None 会被当代码继续往下走；改为在 `elif` 条件里用 walrus 取值、体内直接用，断言与二次取值一并去掉。`cli/cli.py` 原用 `handlers[args.command]` 直取需 config 的命令分发表，subparsers 与表不同域时抛 `KeyError`；改为 `_config_required_handlers()` 单点定义 + `.get()` 判定，漏挂时收口为 `[ERR] 未知命令` 与 `_EXIT_SEVERE`。补 2 条回归（未知命令按用法错误收口、决策抽取在两种模式下取值一致）。

- **再平衡分类的 ETF 名称维度与两处死 logger（rf-1203）**：`analysis.rebalance.classify_holding` 只在场内区间（`is_exchange_fund_code(code)` 为真，即代码 5/1 前缀）内消费 ETF 判定的名称半区——场外 ETF 联接基金（`天弘沪深300ETF联接A`/`000961`）按场外基金口径归 `fund_equity`，代码 5/1 前缀的场内品种归 `equity`，`test_rebalance.py::TestClassifyHolding` 的两条用例分别钉住这两种口径（名称维度独立化的实现会让前者变红）；`analysis/rebalance.py` 与 `analysis/metrics_risk.py` 的 `import logging` 与 `logger` 对象无调用点，一并删除

- **数据源 HTTP 替身单源（rf-1200）**：`src/test/_fixtures/http.py` 提供 `FakeResponse` / `FakeClient`——`FakeResponse(text, status_code, *, json_body, raise_status, encoding, content, json_error)` 覆盖 `.text` / `.content` / `.status_code` / `.encoding` / `.json()` / `.raise_for_status()`，`FakeClient(response, *, by_url, error)` 覆盖上下文管理器、`get` / `post`、按 URL 后缀或包含匹配分派、传输级异常注入与逐次请求记录（`calls` / `posts` / `gets`）。`test_cninfo` / `test_hithink` / `test_datasink` / `test_tiantian_fund_fee` / `test_tiantian_purchase` / `test_tiantian_base_faults` 六个用例文件共用这一份替身，本地 12 类替身定义删除，各文件断言与被 patch 目标保持一致；巨潮用例的「慢 post」时序桩由 3 行 `FakeClient` 子类表达。

- **TUI 入口覆盖以委托断言与子进程表达（rf-1201）**：`test_tui_main_loop_branches.py` 的入口覆盖分两处——包入口用例经 `importlib.import_module("src.python.tui.__main__")` 断言 `__main__` 直接绑定 `tui.main`；`__main__` 的 Ctrl+C 收尾用例在子进程里执行（`sys.executable -c`，子进程内摘掉项目根后经 runpy 走真实入口，断言 `returncode == 0` 与 stdout 告别语），本进程的 `sys.path` / `sys.modules` 在用例前后保持一致。

- **发布台账读取面单源（rf-1202）**：`logs/release.jsonl` 的读取统一由 `scripts/_release/_timing.read_ledger_records(path)` 提供（文件缺失视为空台账；空行、损坏 JSON、非 dict、缺 `command` 的行跳过，单行损坏只影响自己那一行）；`scripts/probe-release-ledger.py` 与发布编排尾行的 token 统计（`_release/_commands_base._finish_timing`）同调该入口，两边的台账行口径只剩一处定义，probe 的输出格式与 `--last` / `--version` / `--json` / `-v` CLI 面不变。

- **穿透行业分类状态以单字段表述（rf-1199）**：`report/penetration._compute_penetration_top10_uncached` 的结果用 `industry_status` 一个字段表达四种状态——`ok`（取到行业数据）、`empty`（有 A 股代码但预取与补取均为空）、`no_a_share`（穿透资产全为非 A 股，预期行为）、`unreachable`（取数异常，产出侧当前不写该值）；消费处 `report/penetration_sheet.build_penetration_data_status` 按枚举一次分流（`empty` / `unreachable` 登记降级，`ok` / `no_a_share` 不登记），任何新消费方读同一字段即得正确口径，「全为非 A 股」不会被记成数据降级。

- **行业降级计数在预期行为后复位（rf-1192）**：`report/penetration_sheet.build_penetration_data_status` 在 `ok` / `no_a_share` 两态对 `penetration_industry` 调一次 `DegradationTracker.reset`；本域失败计数跨报告累积（T3 空数据阈值 3 次），预期行为与非预期行为交替出现时历史计数不参与下一次判定，故「取数为空 ×2 → 全为非 A 股 → 再取数为空」不会因遗留两轮而提前报「行业分类不可用」。

- **后置模块的重算原因与预检同源（rf-1198）**：`self_review` / `holding_change` 等在上游产出后才定键的模块，「上一轮键」经 `llm/cache_policy.previous_module_key` 取（跨报告基线优先、无基线回落进程内记录），与预检共用同一取数点；报告收尾的基线快照一并落这些模块的键（`llm/skeleton.module_cache_keys`），故同键未命中记 `ttl_expired`、换键记 `fingerprint_changed`、无基线记 `cache_miss`，与四个基础模块口径一致，`recompute_reasons` 不再混入两种含义。

- **「合计 = 分项之和」占比口径保护未生效（rf-1197）**：`llm/fact_checker/_context._is_breakdown_sum_context` 识别「合计值（分项 + 分项）」的正则把括号前缀限制在 3 字符，而合计值文本本身（如 `18.3%`）就有 5 字符，该判据对实盘形态恒返回假——「把低风险资产从 18.3%（12.5% + 5.8%）提到 25% 附近」这类自洽占比会被当成单品种收益率改写，句子随即自相矛盾；现把前缀上限放到 8 字符（仍要求括号紧邻合计值），分项与合计不自洽时照旧不判为占比口径，并补 2 条回归（实盘形态命中 + 不自洽不命中）。

- **t 分布 CDF 在 t=-∞ 处返回 0.0（rf-1196）**：`analysis/_math_utils._t_cdf` 的`if x <= 0` 分支（仅在 `|t|` 溢出为无穷时命中）恒返回 1.0，-∞ 处 CDF 应归 0；现按 `t` 符号取两侧极限（`t < 0` → 0.0，否则 1.0），`correlation` 的 `2*(1-CDF)` 与 `metrics_risk` 的 p 值在 t 统计量负向溢出时取左侧极限（0）。

- **自检目录探针的用例断言到隔离替身（rf-1195）**：`test_doctor_branch_faults.TestProbeTargets` 改为在收集期捕获真实 `_probe_targets` 引用并按其实现断言——`get_config` 给出 `output_dir` 时探针目标即该目录，配置读取失败时回落 `_DEFAULT_OUTPUT_DIR`；附目录探针「空 `.xlsx` 目录」与复盘账本概览「依赖模块导入失败」两态降级用例。

- **t 分布 CDF 在 t=0 处返回 0.0（rf-1194）**：`analysis/_math_utils._t_cdf` 的 `x >= 1` 分支（仅在 `t == 0` 命中）返回 0.5，中位数处 CDF 与 `t→0⁺`（0.5004）连续；`correlation` 的 `2*(1-CDF)` 与 `metrics_risk` 的 p 值在「无相关 / Beta 恰为 0」时读到 0.5 对应的 p=1.0，不再出现 p=2.0 这类越界读数。

- **资金流向不可用信号在数据源矩阵里无行可落（rf-1193）**：`report/_generation_full._fetch_sector_flow` 的空载荷与异常两态统一登记 `source_key="ff_sector_flow"`，故「行业资金流向不可用」这一信号无论因空载荷还是调用异常退化，都归入矩阵「资金流向」行（该行前缀为 `ff_`，匹配规则 `key == prefix or key.startswith(prefix)`）；配 2 条回归：两态登记键相等且非 `fund_flow`、登记键经矩阵归属落到 `fund_flow` 行。
- **穿透表「行业分类不可用」降级在行业取数全空时可触发（rf-1191）**：`report/penetration._compute_penetration_top10_uncached` 第三阶段把 `remaining_data` 提到 `if remaining:` 之外初始化为 `{}`，判据改为「预取与补取均为空」（`not prefetched and not remaining_data`）——行业链路熔断（`fetcher/industry.batch_fetch_industry_data` 回空）或批量全败（只回填成功项）时写入 `industry_status="empty"`，`penetration_sheet.build_penetration_data_status` 的降级分支由此可触发；无 A 股代码时写 `industry_status="no_a_share"`，让消费方按枚举值区分「预期不降级」与真实失败（该值在状态构建处按预期行为跳过，不记降级）。补 3 条回归：预取+补取双空判 `empty`、补取部分命中仍算可用、无 A 股不改降级结论。
- **后置模块的重算原因归因恒判 `ttl_expired`（rf-1190）**：`llm/skeleton.generate_llm_content` 先把本轮键写入 `_PREV_MODULE_CACHE_KEY` 再做原因判定，判定读到的「上一轮键」永远等于本轮键 → 「无上轮记录 → `cache_miss`」与「换键 → `fingerprint_changed`」两个分支不可达，内容变化被系统性误标成「TTL 到期」，据此判断「放宽 TTL 能省钱」会得出错误结论；归因改取写基线**之前**的键，并把该块抽为 `_attribute_recompute_reason()`（单一职责，同时降低骨架圈复杂度），补 6 条回归（三态归因 / 已归因不覆盖 / 无汇聚器 / 端到端两轮判 `fingerprint_changed`）。
- **敏感缓存清理遇畸形 `_ts` 中断整轮（rf-1189）**：`cache/_cleanup.clean_sensitive` 的时间戳直接参与减法，`_ts` 为字符串或 None 时抛 `TypeError` 并被导入期兜底吞掉 → 该轮清理中止，盘上其余过期持仓/穿透/基金缓存全部漏清（`cleanup_expired` 同期已有类型容错，两入口口径不一致）；抽出共享 `_payload_ts()` 让两入口同源，敏感缓存按「无法判定年龄 = 极旧」处理（宁可多清不可留存），单文件畸形不再打断后续扫描。
- **llm_settings 运行约束静默丢失（rf-1188）**：`config/_llm_schema.apply_flat_updates` 的 runtime 扁平键查表按「字段名」而不是「扁平键」建反向表——`llm_max_concurrency` / `llm_max_thinking_concurrency` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` 写回时落到顶层、v2 `runtime` 段不更新，随后 `flatten()` 用 runtime 段的值压过顶层透传 → 用户在配置面板/编辑层改的并发、重试延后、时间预算设置**静默丢失**（`llm_settings.json` 缺失走默认兜底、或同批含 `debate`/`fact_check` 更新时走该路径即触发）；改按扁平键建反向表，配 12 条落点敏感回归（`runtime` 段落值 + 顶层无扁平键残留 + 六个字段从 `RUNTIME_FIELDS` 参数化派生 + 写盘级解析残留 JSON），并修掉既有「只经 `flatten()` 回读」的假绿往返用例。

### 新增

- **发布台账按版本汇总（rf-1187）**：新增只读脚本 `scripts/probe-release-ledger.py`（`--last N` / `--version` / `--json` / `-v`），按版本切段输出每版墙钟、分步耗时、会话 token 增量与失败步；token 列口径明确标注为「相邻台账行之间的会话增量」，不是发布命令本身的成本；配 11 条用例（切段口径/跨版本不串账/同会话取前后差/新会话首行记 0/累计回退记 0/脏行与缺失容错/JSON 与选择器）。

### 测试

- **测试覆盖率 92.1% → 99.996%（十四个批次）**：接入 `pytest-cov` 后按「失败路径优先、只值一测的分支也不放过」逐批补齐；本轮收尾时 `cli/_handlers`、`report/news_correlation`、`cache/operations`、`report/llm_content`、`report/summary`、`report/_orchestrator_data`、`report/html_jinja_env`、`report/whatif_writer`、`report/pipeline_data_builder`、`report/_run_scope`、`providers/news_dedup_anchor_store`、`tui/handlers_log`、`tui/progress`、`providers/tiantian_base`、`report/_report_health`、`report/excel_news_warning`、`cache/_paths`、`cache/_store`、`cache/_cleanup` 等模块均达 100%（`llm/skeleton` 99%，保留 1 行早退后的不可达防御分支）。逐批口径：
  - **第 1 批（92.1% → 92.9%）**：可靠性/边界类零散守卫与接口回显分支（首轮补齐后的收尾段）。
  - **第 2 批（92.9% → 93.5%）**：analysis guard 分支、缓存刷新编排、config 写路径/校验分区、pricing 解析、akshare 扩展、东财净值历史、回撤页签、HTML 构建阶段埋点、TUI 入口分支。
  - **第 3 批（93.5% → 93.9%）**：Excel 页签写入隔离、HTML 渲染降级、新浪解析回落、提示词表格分支、CLI 命令簇。
  - **第 4 批（93.9% → 94.7%）**：医生检查项故障、行情时段官方层、因子目录探测、缓存面板分支、API 响应解析、提示词数据块、新闻去重锚点策略、基金业绩、穿透页签、调度回放面板、LLM 用量小结、Web 错误分支与持仓编辑校验。
  - **第 5 批（94.7% → 94.8%）**：`cache/_store` 写侧故障、`cache/_cleanup` 清理故障与敏感缓存、锚点存储容错、运行边界九步复位故障注入、pipeline_data 注册与校验分支。
  - **第 6 批（94.8% → 95.0%）**：TUI 诊断面板与状态条接线、天天基金公共 HTTP 故障面、健康检查收口容错、新闻页签降级、缓存目录权限自检。
  - **第 7 批（95.0% → 95.1%）**：Jinja 字节码缓存与过滤器兜底、中断收口五步逐步容错、调仓 What-if 产物写出与匿名装配。
  - **第 8 批（95.1% → 95.2%）**：LLM 内容写入边角（游离文本分段/占位文案/契约小节）、编排数据逐域降级、汇总页降级渲染。
  - **第 9 批（95.2% → 95.5%）**：缓存编排分市场明细与预热、LLM 骨架边角（空输出/用量合并/凭据回落/原始输出过滤/账本回灌）、新闻关联关键词扩展与费用口径、CLI 配置面（set/list/源名校验/非 UTF-8 禁彩）。
  - **第 10 批（95.5% → 97.97%，缺口 2249 → 1012 行）**：core 与 config 残余不可达分支——provider 注册表与健康态、性能计时器与阈值、持仓读取容错、LLM 设置/提供方/定价解析边角、json patch 逐层失败、配置校验分区、降级追踪器通道统计、日志配置落盘失败、持仓追踪器清洗、TUI 与 CLI 入口分支。
  - **第 11 批（97.97% → 98.12%，缺口 1012 → 942 行）**：六个模块的 69 行目标缺口全部补齐——`tui/handlers_config` 15 行（Esc 改配置不落盘、调优项输入中断、调优/匿名化面板筛选态跳行、页脚随改动计数上屏、指数池面板中断）、`tui/handlers_report_chapters` 12 行（费用摘要无金额明细时省略、窄档备注行、`u` 撤回消费、`?<键名>` 直取子项详情、实验子项用量备注、面板中断收会话、章节详情费用行）、`core/cassette` 11 行（读取不可读文件转 `CassetteError`、写盘失败上抛、索引遇并发删除按空/零降级、录制传输读全响应体后再录）、`core/jsonl_store` 10 行（既有文件不可读时重建、读取/裁剪不可读按空处理、裁剪保留非对象行）、`cache/_io` 10 行（损坏文件删除失败仍当无缓存、`replace` 被锁走删除+rename、`chmod` 不支持时忽略、写纯文本格式时清旧 `.gz`）、`config/features` 11 行（覆写文件非对象、非法补丁拒绝落盘、未登记开关不生效、非 bool 值只告警、恢复默认清掉运行时残留键）；新增 6 个测试文件共 37 条用例，全仓缺口由 1012 行降到 942 行（49972 语句 / 942 未覆盖 / 98.12%）。
  - **第 12 批（98.12% → 99.4%）**：`analysis._math_utils`（t 分布端点、样本不足与基准零方差）、`analysis._factor_formulas`（非法收盘价、有效对不足、标量 NaN 铺满、量价背离符号、60 日收益偏度、横截面日均值成分数下限） 等模块的残差分支补测；相邻改动修 `_t_cdf` 两端取值（`t=0` 取中位数 0.5、`t=-inf` 取 0.0、`t=inf` 取 1.0），自检目录探针用例改取真实实现断言并补降级用例。
- **第 13 批（99.4% → 99.6%，残差分支收尾）**：`llm`（熔断状态展示面、盘中复用归因、证据索引、档位解析降级）等模块的不可达/降级分支补测。
- **第 14 批（99.6% → 99.996%，残差收口）**：204 行缺口逐行定性——能由合法输入触达的补真用例（约 60 行，含 `__main__` 入口改子进程执行 + 覆盖归并），可证明不可能执行的删死码（40 余处，每处附类型/契约/数学证明与「异常面不变」论证：`rebalance` 四处冗余守卫、`text_layout` 硬切互斥分支与恒非空循环、`skeleton` 早退后的 else、`anonymizer` 恒假份额下限、`liquidity` 已判场外却档位未知的分支），不确定的保留上报。最终仅剩 2 行保留未覆盖（`schedule_replay` 注入面护栏、`news_dedup_rules` 性能分支，构造条件与理由见 `test-coverage.md`）。期间顺带修 3 个问题：`classify_holding` 名称维度被误判为死码（380 组新旧对照证明删除正确，补钉住用例，`rf-1203`）、`liquidity` 的档位未知状态与 R-LIQ-03 口径冲突（删分支 + 需求口径对齐）、子进程覆盖归并把 `src/test` 并入导致 TOTAL 语句数翻三倍（量测域收紧到 `src/python` 单源）。
- **覆盖率接入与首轮缺口补齐**：`requirements.txt` 增 `pytest-cov`（此前项目只有测试规模快照、没有行覆盖率数据）；据首轮实测（`src/test/unit`，90.7%）补齐 9 个薄弱文件的分支覆盖——`report/excel_module_loader`（53.9%→100%）、`llm/_debate_router`（60.0%→100%）、`report/excel_fund_deep_analysis`（28.9%→97.4%）、`providers/tiantian_nav`（50.7%→94.0%）、`tui/handlers_config`（58.2%→96.3%）、`tui/tui_keys`（61.5%→91.9%）、`tui/handlers_holdings`（64.7%→93.6%）、`web/server`（59.5%→83.5%）、`report/_report_factor_metrics`（50.9%→88.3%），整体 90.7%→92.1%，`<60%` 文件由 6 个降为 0 个；新增 9 个测试文件共 184 条用例，聚焦降级链路（ImportError 逐模块兜底 / 数据源故障 vs 数据不足 / 辩论两级回退清空容器）、序列拆包与 UTF-8 解码、持仓录入撤销与保存防线。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.6（2026-11-12 ~ 2026-11-19）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
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
