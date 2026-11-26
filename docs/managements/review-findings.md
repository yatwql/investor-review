# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.18.7-dev
> **编号源**：`rf-next = 1208`（新增问题提出后更新为 +1；已用最大 rf-1207，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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
| `src/python/core/perf.py` 799 行 | 采集器与台账落盘可拆（`perf` 采集 / `perf_history` 读写两文件） |
| `src/python/core/doctor.py` 789 行 | 检查项按域分文件（环境 / 配置 / 数据源 / 报告产物），入口只留编排 |
| `src/python/llm/fact_checker/_numerical.py` 764 行 | 数值校验按规则族拆（金额 / 比率 / 计数），共享解析原语上提包内 `_common` |
| `src/python/tui/handlers_config.py` 743 行 | 配置面板按域拆（内容选项 / 全局设置 / 目录与文件名） |
| `scripts/_doc_drift/_format.py` 742 行 | 格式化规则按文档类型拆（章节 / 表格 / 树 / 统计） |
| `src/python/core/degradation.py` 768 行 | 状态词与事件模型、登记面与持久化可拆两文件 |
| `src/python/report/action_sheet.py` 753 行 | 行动页签内各块（建议表 / 判断依据 / 决策书 / 复盘）拆子模块 |
| `src/python/fetcher/financial_report.py` 725 行 | 按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/python/providers/akshare_extras.py` 718 行 | 按接口族拆（指数 / 行业 / 分红 / 盈利预测） |
| `src/python/core/provider_registry.py` 710 行 | 熔断与会话缓存各自独立文件 |
| `src/python/llm/skeleton.py` 909 行 | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染） |
| `src/python/cli/_handlers.py` 890 行 | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄 |
| `src/python/tui/handlers_holdings.py` 825 行 | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于风险，暂不拆 |
| `src/static/tmpl/report_template.html` 278 行 | 样式已抽到 `partials/_report_styles.html`，各自单一关注点，均未触 1000 行 |
| `src/static/tmpl/whatif_template.html` 543 行 | **不在行数守护域内**（`check-file-length` 只扫 `.py`）；样式已抽到 `partials/_whatif_styles.html` |

## 已解决问题

### 开发期已修复（0.18.7-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-1187** | 发布台账只能读「至今累计 token」（跨会话累加），无法回答「这一版发布花了多少墙钟 / 多少 token」：`logs/release.jsonl` 每命令一行、`session_usage` 为 agent 会话累计值，靠人工翻 465 行对不出单版成本 | 新增只读汇总脚本 `scripts/probe-release-ledger.py`（按 `version` 去 `-dev` 切段 → 每版墙钟/分步耗时/会话 token 增量/失败步，`--last`、`--version`、`--json`、`-v`；只读，不改台账写入路径与发布步骤）；配 11 条用例（切段口径/跨版本不串账/同会话取前后差/新会话首行记 0/累计回退记 0/脏行与缺失容错/JSON 与选择器） |
| **rf-1188** | `config/_llm_schema.apply_flat_updates` 的 runtime 扁平键查表必须与 `flatten` 正向表同向（扁平键 → 字段）：键向若相反，`max_retries` / `daily_cost_limit` 因字段名恰等于扁平键而命中，`llm_max_concurrency` / `llm_max_thinking_concurrency` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` 永不命中 → 落到「未映射键原样保留在顶层」，v2 的 `runtime` 段不更新，随后 `flatten()` 用 runtime 段的值压过顶层透传 → 用户设置**静默丢失**（触发：`write_llm_settings` 在 `llm_settings.json` 缺失、`_DEFAULTS_NESTED` 兜底，或同批含 `debate`/`fact_check` dict 更新时走 `apply_flat_updates`） | 反向表改为按扁平键建 `{flat_key: field for field, flat_key in RUNTIME_FIELDS}`（查表方向与 `flatten` 正向表对齐）；补落点敏感回归——`runtime` 段落值 + 顶层无扁平键残留 + 六个运行时字段从 `RUNTIME_FIELDS` 参数化派生 + 写盘级直接解析落盘 JSON（`llm_settings.json` 缺失路径）；既有往返用例补落点位断言（`runtime` 段取值 + 顶层无扁平键残留） |
| **rf-1189** | 敏感缓存清理遇畸形 `_ts` 中断整轮：`cache/_cleanup.clean_sensitive` 用 `ts = payload.get("_ts", 0)` 直接参与 `now - ts`，任何字符串/None 时间戳抛 `TypeError` 并被导入期兜底吞掉 → 该轮清理中止，盘上其余过期持仓/穿透/基金缓存全部漏清（`cleanup_expired` 同期已有类型容错，两入口口径不一致） | 抽出共享 `_payload_ts(payload)`（缺失/非数值一律归 0.0），两入口同源；敏感缓存按「无法判定年龄 = 极旧」处理（宁可多清不可留存），单文件畸形不影响后续扫描；补 1 条回归（畸形 `_ts` + 正常过期文件同目录，断言两者都被处理）＋ 补齐清理/存储/运行边界/管线构建 5 个模块故障分支的 78 条用例 |
| **rf-1190** | 后置模块的重算原因归因恒判 `ttl_expired`：`llm/skeleton.generate_llm_content` 先把本轮键写入 `_PREV_MODULE_CACHE_KEY` 再做原因判定，判定读到的「上一轮键」永远等于本轮键 → 「无上轮记录 → cache_miss」与「换键 → fingerprint_changed」两个分支不可达，内容变化被系统性误标成「TTL 到期」，据此决策放宽 TTL 会得出错误结论 | 归因改取**写基线之前**的上一轮键（`_prev_key_before`），并把归因块抽成 `_attribute_recompute_reason()`（单一职责 + 降低骨架圈复杂度）；补 6 条回归（三态归因、已归因不覆盖、无汇聚器、端到端两轮判 `fingerprint_changed`） |
| **rf-1191** | 穿透表「行业分类不可用」降级在生产里不可达：`report/penetration._compute_penetration_top10_uncached` 第三阶段的 `remaining_data` 只在 `if remaining:` 内赋值，判据 `not prefetched and not remaining` 中 `remaining` 为「未预取覆盖的代码集」——行业链路熔断（`fetcher/industry.py` 直接回空）或批量全败（只回填成功项）时 `prefetched={}`、`remaining` 非空 ⇒ 判据恒假，`industry_success` 恒 True、`industry_failure_type` 永不写入，`penetration_sheet.build_penetration_data_status` 的降级分支在生产中永不触发；另外 `no_a_share` 只写 `industry_failure_type` 未联动 `industry_success`，同函数 220 行的 `no_a_share` 分支因此也不可达 | `remaining_data: dict = {}` 提到 `if remaining:` 之前初始化，判据改为「预取与补取均为空」（`not prefetched and not remaining_data`），保持既有 `industry_success=False` + `failure_type="empty"` 语义；无 A 股代码时一并置 `industry_success=False` 并写 `no_a_share`，使上游按类型区分「预期不降级」与真实失败有统一入口；补 3 条回归（预取+补取双空判 `empty` / 补取部分命中仍算可用 / 无 A 股不改降级结论） |
| **rf-1192** | `report/penetration_sheet.build_penetration_data_status` 的 `no_a_share` 分支不复位 `penetration_industry` 降级追踪器上遗留的 `empty` 计数——跨报告序列「有 A 股且行业取数为空」→「全为非 A 股」→「再切回有 A 股」时，T3 阈值判断读到的仍是上一轮累积的 `empty`，可能提前一次触发「行业分类不可用」降级 | `no_a_share` 与 `ok` 两态各调一次 `_tracker().reset("penetration_industry")` 清空该通道计数；展示语义不变（无 A 股仍不记降级、`build_penetration_data_status` 仍返回空字典） |
| **rf-1193** | `report/_generation_full.py` 的 `_fetch_sector_flow` 三态里，空载荷分支登记 `mark_data_unavailable("fund_flow", …)`，而陈旧回退与异常两态登记 `"ff_sector_flow"` → 同一「行业资金流向不可用」信号的失败态按原因分裂成两个 `source_key`，且 `fund_flow` 匹配不上矩阵任何行前缀（「资金流向」行前缀为 `ff_`）⇒ 空载荷降级事件在数据源矩阵里彻底失联，用户看不到「资金流向不可用」 | 空载荷分支改登记 `ff_sector_flow`（`failure_type` 仍由 `sector_flow_failure()` 推导、message 与告警不变），三态同键；补 2 条回归——空载荷与异常两态登记键相等且非 `fund_flow`、登记键经 `data_source_matrix` 归属落到「资金流向」行（`fund_flow`） |
| **rf-1194** | `analysis/_math_utils._t_cdf` 在 `t == 0` 处 `x = df/(df+t²)` 恰为 1，命中 `if x >= 1: return 0.0` → 中位数处 CDF 返回 0.0 而非 0.5，与 t→0⁺（0.5004）不连续：`correlation` 的 `2*(1-CDF)` 与 `metrics_risk` 的 p 值在「无相关 / Beta 恰为 0」这一最不显著的取值上给出 p=2.0 这类越界读数 | `x >= 1` 分支返回 0.5（该支只在 t==0 命中，语义即中位数）；补 1 条回归断言 `_t_cdf(0.0, 10) == 0.5`，并保留 `_t_cdf(±10, 100)` 的尾部极限断言确保两侧连续性未变 |
| **rf-1195** | `doctor._probe_targets` 在测试中从未被执行：`src/test/_path_isolation.py` 的 autouse 隔离 fixture 把 `doctor._probe_targets` 替换成固定替身，而 `test_doctor_branch_faults.TestProbeTargets` 仍经 `doctor._probe_targets()` 断言，实际断言的是隔离替身（`doctor_probe0/reports`）——生产实现「配置了 output_dir 就取它」这一被调用方依赖的行为在测试里既未被验证，也让该函数整段（try/except 兜底 + 返回）实测零覆盖 | 用例改为在收集期捕获真实函数引用（`_REAL_PROBE_TARGETS`）并按实现断言：`get_config` 返回 `output_dir` 时目标即该目录、异常时回落 `_DEFAULT_OUTPUT_DIR`；并补目录探针空目录态与账本概览导入失败兜底两条用例 |
| **rf-1196** | `analysis/_math_utils._t_cdf` 在 `t = -inf` 时 `x = df/(df+t²)` 下溢为 0，命中 `if x <= 0: return 1.0`，-∞ 处 CDF 返回 1.0 | 该分支按 `t` 符号取两侧极限（`t < 0` → 0.0，否则 1.0）；相关性/风控 p 值在 t 统计量负向溢出时取左侧极限 |
| **rf-1197** | `llm/fact_checker/_context._is_breakdown_sum_context` 判据恒假：「合计 = 分项之和」正则的括号前缀上限写 3 字符，而合计值自身文本（`18.3%`）就有 5 字符 ⇒ 实盘形态「18.3%（12.5% + 5.8%）」永不命中，自洽的占比口径被当成单品种收益率改写（实盘事故原文即该句），`_BREAKDOWN_SUM_TOLERANCE` 与文档声明的保护实际未生效 | 前缀上限放到 8 字符（仍要求括号紧邻合计值，覆盖带负号/两位整数/小数的常规写法）；补 2 条回归——实盘形态判为占比口径、分项与合计不自洽时仍不判 |
| **rf-1198** | 后置模块（`self_review` / `holding_change` 等）的重算原因跨报告恒判 `cache_miss`：`llm/skeleton._attribute_recompute_reason` 的「上一轮键」只取进程内 `_PREV_MODULE_CACHE_KEY`，而 `report/_run_scope.start_report_run()` 在每份报告边界清空该字典、`generators_orchestrator._finalize_llm_run` 落基线又只写预检 `cache_info` 的四个基础模块键 → 同键未命中也被记 `cache_miss`、`ttl_expired` 分支对后置模块不可达；同一场景预检路径（`_key_changed_from_baseline`）却记 `ttl_expired`，一个 `recompute_reasons` 计数器混进两种含义，据此判断「放宽 TTL 能省钱」会系统性低估 | 「与上一轮比对」的取数收敛到 `llm/cache_policy.previous_module_key`（跨报告基线优先、无基线回落进程内记录），预检与生成骨架共用同一取数点；报告收尾的基线快照并入 `llm/skeleton.module_cache_keys()`（后置模块真实键）；补 6 条回归（同键→`ttl_expired`、换键→`fingerprint_changed`、无基线→`cache_miss`、无基线时进程内回落、基线含后置模块键且保留基础模块键） |
| **rf-1199** | `report/penetration` 用「`industry_success` 成功标志 + `industry_failure_type` 失败类型」两字段表述行业分类的四种状态，`no_a_share`（全为非 A 股，预期行为）靠失败类型字段兼表「非失败」，消费处要靠该类型特判才没把预期行为记成降级——任何只看成功标志的新消费方都会把「无 A 股穿透资产」记成数据降级 | 合并为单字段 `industry_status: ok / empty / no_a_share / unreachable`，产出侧（`_compute_penetration_top10_uncached`）与消费侧（`build_penetration_data_status`）一次改齐，`no_a_share` 作为枚举值而非失败标志 |
| **rf-1200** | `src/test/unit/providers/` 的数据源用例各自定义 HTTP 替身（6 文件 12 份、三种命名 `_FakeResp/_FakeClient`、`_FakeResponse/_FakeClient`、`_Resp/_Client`），行为假设随用随加而分叉：巨潮要 `content` 字节 + 按 URL 后缀分派、同花顺/数据源只回单个 JSON、天天基金要 `raise_for_status` 与 `text`，新增数据源用例须再抄一份才能凑齐 | 新建 `src/test/_fixtures/http.py`：`FakeResponse`（`text` / `content` / `status_code` / `encoding` / `json()` / `raise_for_status()`）与 `FakeClient`（上下文管理器、`get` / `post`、`by_url` 后缀或包含分派、`error` 注入、`calls` / `posts` / `gets` 记录）表述行为契约；六个文件改用共享替身并删除本地定义，各文件断言与 patch 目标不变 |
| **rf-1201** | `src/test/unit/ui/test_tui_main_loop_branches.py` 用 `runpy.run_path(tui_mod.__file__, run_name="__main__")` 在进程内重跑整套 TUI 验「Ctrl+C → 告别语 + 退出码 0」，模块级代码（logger 装配、退出钩子注册、启动边界日志）逐条用例重复执行，且改写本进程的 `sys.modules` / `sys.path` | 包入口用例改 `importlib` 断言 `src.python.tui.__main__` 绑定 `tui.main`；`__main__` 收尾用例移入子进程（`sys.executable -c`，子进程内摘掉项目根后经 runpy 执行入口，断言 `returncode == 0` 与 stdout 告别语），本进程 `sys.path` / `sys.modules` 不被改动 |
| **rf-1202** | `logs/release.jsonl` 的解析同域实现在三处各写一遍——`scripts/probe-release-ledger.py` 的读取（跳过损坏行/非 dict/无 `command`）、`scripts/_release/_commands_base._finish_timing` 的内联逐行 `json.loads`、`scripts/_release/_timing.release_token_usage` 的会话快照差量；台账行口径（必填字段、损坏行容忍）改一次要同步三处 | `_release/_timing.read_ledger_records(path)` 作为唯一台账读取入口（含损坏行/非 dict/缺 `command` 跳过口径），probe 与 `_finish_timing` 改调它；probe 的输出格式与 `--last`/`--version`/`--json` CLI 面不变 |
| **rf-1203** | 死码删除安全评审把 `analysis/rebalance.py:200` 的 ETF 名称维度判为「被误删的可达分支」（反例 `classify_holding("天弘沪深300ETF联接A", "000961")` 声称应为 `equity`），并要求据此回滚；同时 `analysis/rebalance.py` / `analysis/metrics_risk.py` 残留零调用的 `import logging` 与 `logger` 对象 | 以 `git worktree` 拉出删除前版本对 20 名称 × 19 代码共 380 组逐一比对 `classify_holding`，差异 0 组：被删的 `is_etf_by_name_or_code` 内层判断原本嵌在 `if is_exchange_fund_code(code):` 内（代码必 5/1 前缀 ⇒ 内层恒真），`return "alternative"` 从未可达 ⇒ 分支保持删除态（评审误报），补 `test_etf_name_with_otc_code_is_fund_equity` 与 `test_exchange_fund_code_prefix_is_equity` 钉住真实口径（前者在「名称维度独立」的错误实现下变红）；两处死 `import logging`／`logger` 一并清掉 |
| **rf-1204** | 两处「依赖运行期断言/字典直取」的隐性契约：① `report/decision_llm_capture.py` 用 `assert code is not None` 收紧「该行必含 6 位代码」，而 `python -O` 会剥离 assert ⇒ 优化模式下 None 会被当代码继续往下走；② `cli/cli.py` 用 `handlers[args.command]` 直取需 config 的命令分发表，subparsers 与表不同域时抛 `KeyError` 而不是按用法错误收口 | ① 改为在 `elif` 条件里用 walrus 取值（`elif (line_code := extract_code(line)) is not None`），体内直接用该值，删除断言与二次取值；② 新增 `_config_required_handlers()` 单点定义分发表，`main` 用 `.get()` 判定并把漏挂情形收口为 `[ERR] 未知命令` + `_EXIT_SEVERE`；补 2 条回归（未知命令收口、决策抽取在两模式下行为一致） |
| **rf-1205** | `core/doctor.py` 的目录探针把「缓存目录」硬编码为 `PROJECT_ROOT/data/cache`：缓存目录的唯一解析器是 `cache/_paths.py`（`INVEST_CACHE_DIR` 覆盖是演示/基准的缓存隔离入口），隔离 run 下自检探测并可能写入真实 `data/cache`，且上屏路径与实际生效目录不符（违反「缓存统一管理」架构约束：缓存目录只经缓存层解析器取得） | 探针内取 `from src.python.cache import get_cache_dir` 的解析结果（core→cache 属同层依赖，函数级导入即满足导入面契约），上屏路径与哨兵写入目录同源；补 1 条回归（隔离目录下上屏路径 = 解析器结果、哨兵落在隔离目录、真实 `data/cache` 无哨兵残留） |
| **rf-1206** | 日志配置默认值三处镜像：`core/logger.py` 全量复制 7 项默认值、`core/doctor_logs.py` 另带 `or "INFO"`，而缺省值事实位 `config/_logging.py::DEFAULTS` 未登记进 `_DEFAULT_TABLE_FILES`（违反架构约束「配置默认值单源」）；core 侧不得导入 config（叶子模块边界守卫），单源须落在 core | 新增 `core/logging_defaults.py` 承载 `DEFAULTS`/`LEVELS`/`RANGES` 唯一事实位，`config/_logging.py` re-export 同一对象（config→core 为合法依赖方向），`core/logger.py` 与 `core/doctor_logs.py` 从同包取用，`_DEFAULT_TABLE_FILES` 登记该路径；补 2 条回归（配置回落值等于缺省值表、`config._logging.DEFAULTS is core.logging_defaults.DEFAULTS`） |
| **rf-1207** | 三份同名 `_fmt_pct` 语义分叉：`report/decision_basis.py` 吃百分数点数（`%g`）、`report/event_impact_panel.py` 吃小数比例且带符号、`report/schedule_replay_panel.py` 吃小数比例不带符号且非数值直接抛 `ValueError`——同名不同义使调用点无法自证口径 | 抽出 `report/_format.py`，按口径分 `fmt_pct_points()` 与 `fmt_pct_fraction(value, *, signed=False)`，三处调用点按各自语义替换对应函数（既有输出字符串不变），非数值入参统一回「—」占位（取值失败按缺失呈现，不抛异常）；补 1 个单测覆盖 None/字符串/负数/0 边界 |

### 归档档案
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-19）
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
