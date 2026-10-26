# 自审记录归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.0 发布，本系列首批开发期已修复批次并入）；2026-10-25 v0.16.1 本批原表搬运；2026-10-26 v0.16.3 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.16.x 开发期已修复项（v0.16.0 → ）（含 v0.16.3）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 开发期已修复（0.16.1-dev）

> 完整复盘见 `changelog.md` 0.16.1-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-25。

| # | 问题 | 修复 |
|---|------|------|
| **rf-882** | `cache/_cleanup._fmt_span` docstring 混入西里尔字母（应为「两」），全文扫描仅此一处非中文外文字符 | 改为「两」，并反向核对希腊字母使用均为公式符号（Σ/σ/Π）属合法 |
| **rf-883** | `config/_config_freshness._keys_of` 解析失败返回空集 → 自检把「文件语法坏」报成「缺全部 40 个新键」，误导修复方向 | 返回 `None` 表示不可比较；`_diff` 增加 `parse_error` 字段；自检单独报「无法解析」并给编码/语法提示；回归 2 例 |
| **rf-884** | 同模块 `check_config_freshness` 只捕 `OSError`，非 UTF-8 配置文件解码失败时冒泡成「对比失败」 | 同时捕 `UnicodeDecodeError`（跳过，由配置加载检查负责报错）；回归 1 例 |
| **rf-885** | 同模块 `import json` 写在函数体内（风格与分层不一致） | 提到模块顶部 |
| **rf-886** | 审计误判：把 `core/costs.add_cost_bucket` 判为「死代码」（只 grep 了 `src/`，漏掉 `scripts/_perf_history` 两处调用），删除后 dev-verify 才暴露 | 已恢复并补 docstring 调用方说明（core / llm / scripts 三方共用）；教训：死代码判定必须扫全仓（含 `scripts/`），且以门禁实跑兜底 |
| **rf-887** | 重算原因（forced/fingerprint_changed/ttl_expired/cache_miss）以字符串字面量散落在预检与骨架两条路径，新增的 `RECOMPUTE_REASONS` 取值域无人使用 | 两处改引用 `observation.RECOMPUTE_*` 常量；`note_recompute_reason` 对域外值告警一次（仍计数，避免静默多出无人认识的统计桶）；回归 3 例 |
| **rf-888** | `_llm_providers_defaults._PROVIDER_NOTES` 与默认线路未配对时静默无注释（新增线路漏写说明不会被发现） | 补对齐回归 2 例：每条默认线路必须有非空说明 + 模板可被注释剥离器解析且订阅制线路保留 `pacing` |
| **rf-889** | 360h 核查：`scripts/_eval_halluc_sampler/llm_call.py` 与 `holdings.py` 有三处逐字重复（`_compute_categories` / `_compute_portfolio_values` / `_load_datasets`），其中一份引用已搬走的 `fact_checker._calc_portfolio_values`，被调即 ImportError | 删除 llm_call 内副本（本模块未使用），唯一实现留在 holdings；模块 docstring 记明原因 |
| **rf-890** | 360h 核查：三家行情源（sina / sina_kline / tencent）各持一份逐字相同的 `_add_prefix`，改一处长度判据或前缀表会让另两处静默取错代码 | 收敛为 `providers/utils.with_exchange_prefix`（规则本体仍在 `core/code_symbols`），三处改为别名；语法断言纯函数行为不变 |
| **rf-891** | 360h 核查：`scripts/_eval_factor_zoo/metrics.py` 内联副本了 `_closes` / `_daily_returns` / `_rolling_beta`（离线评测不依赖 src 私有名，属有意为之），但无任何机制阻止两份公式漂移 | 加同源数值测试：同一段 bars/指数在两侧逐步对比（NaN 位与浮点均带容差）——公式一改即红，而非静默出不同因子值 |
| **rf-892** | 360h 核查：生产代码 6 处 `assert` 承担类型收窄与入参校验职责（LLM 三客户端 `client is not None`、报告两处 checkpoint 类型断言），`python -O` 下会被剥离——真出错时炸点推到更晚且信息更差 | LLM 三处改显式 `if client is None: raise ValueError`；报告 checkpoint 改告警不中断（与同函数内其他校验口径一致）；现全仓生产代码 `assert` 清零 |

## 开发期已修复（0.16.3-dev）

> 完整复盘见 `changelog.md` 0.16.3-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-26。

| # | 问题 | 修复 |
|---|------|------|
| **rf-909** | 持仓明细行组装两份拷贝：`report/_orchestrator_data.py`（编排路径，10 字段 + `change_pct`/`nav_date`/`source_api`）与 `report/_report_helpers._action_holdings_details`（行动建议路径，同 10 字段子集）各写一遍，`profit_rate` 百分号换算与 `channel` 渠道判定在两处重复；字段增删需同时改两处，漏改即出现「同一持仓在行动建议与编排数据里字段不同」 | 抽 `report/_holding_detail_rows.py::build_holding_detail_rows(details, *, with_market_fields, transactions=None)`：共有 10 字段（`profit_rate` 百分号口径、`channel` 经 `classify_channel` 单源、`account` 原值）集中构造，`with_market_fields=True` 追加行情三字段（`change_pct` 零昨收兜底），尾部统一 `attach_holding_trading_days`；`_action_holdings_details` 改为其薄封装，编排路径改为同名调用（顺带把 `changed_code_files`/`penetrated_targets` 等既有类型摩擦就地收窄）。回归 9 例（两路径共有字段逐项一致/键序固定/行动建议字段子集不变/百分号与 None/零昨收 0.0/渠道单源/两侧同时附加 holding_days） |
| **rf-918** | 基金同类百分位口径取反：上游 `Data_rateInSimilarPersent` 是「越高越好」（实测 9 只基金恒等于 `100 − rank/total×100`，如 240012 的 1765/1792 → 1.51、096001 的 51/362 → 85.91），而评级计算把原值直接当作「越低越好」的排名分位套阈值——仅百分位可用时好坏颠倒（前 1.5% 判「较差」），两侧都在时则每次运行都刷「百分位评级与排名评级不一致」告警（日志累计 16 条），真问题被噪音淹没 | 评级路径按 `(100 − 值) / 100` 取补后套阈值（用减法式而非 `1 − 值/100`，避免 70 这类档位得 0.30000000000000004 越过 0.30 阈值把「良好」误判「稳定」）；解析层保留上游原值并在 docstring 写明方向。回归 3 例（三组实测样本两侧评级一致、仅百分位时 98.5 → 优秀、71.84/15.91 等档位边界） |
| **rf-917** | 调仓建议清单的空态文案与数据矛盾：组合级纪律（回撤线/超警戒线）触发时，交易纪律表已写「触发」，而下方调仓建议清单写「无再平衡/纪律触发信号，暂无调仓建议」——组合级信号不带 `code`，可行化层不产生个股订单，空的原因是「有触发但无订单」而非「无触发」 | 空态分两支：真无触发 → 原文案；有触发无订单 → 「已触发信号但无可执行单品订单（组合级回撤不落到个股），暂无调仓建议」。Excel（`action_sheet.py` 两支常量）与 HTML（`action_section.html` 同文案）同步；回归 2 例（Excel/HTML 各一，断言新文案出现且旧文案缺席） |
| **rf-916** | 峰谷计费等价用例的时刻依赖缺陷：`test_llm_pricing.py::TestCostEquivalence::test_same_prices_produce_same_cost` 两侧策略不同（基线走内置双高峰窗、覆盖文件用单窗口）且计费时刻未固定，两侧落在不同峰谷分支时价差正好 2 倍——特定钟点（如 14:06 CST）必红的时刻依赖假红 | 计费调用统一传 `at_time` 钉死时刻，`_base_ref()` 的 `peak_periods` 与内置默认对齐（价格覆盖用例不改变峰谷策略）；另补「周末恒闲时 = 基础价之和」非空校验，防两侧同为 0 也通过。回归 1 例 |
| **rf-913** | **原子写入单源偏离**（架构约束表「缓存原子写入」条）：`web/scheduler.py::_save_fired` 自建 `tmp + os.replace`，且临时文件名固定为 `scheduler_fired.json.tmp`（非 `tempfile.mkstemp`）——同目录 `web/upload.py`、`web/holdings_update.py` 都已显式走 `core/atomic_write`；固定 tmp 名下并发写会互相截断，落盘实现也成了第二份 | 改 `core.atomic_write.write_json_atomic`（保留剪除超保留期条目与「失败只记 ERROR 不外抛」行为），并顺带修 `status_payload` 的 `next_fire_at(...).strftime` 空值访问。回归 2 例（落盘失败只记 ERROR 不抛且不产半文件、3 线程各写 20 轮后账本完整可解析且无残留 `.tmp`） |
| **rf-914** | 文件膨胀登记簿与事实不符：`check-file-length -v` 实测 5 个文件越过登记线（测试 >900：`test_release_tool_gate.py` 1147、`conftest.py` 999；主程序 >700：`generators_orchestrator.py` 827、`cli/_handlers.py` 789、`llm/skeleton.py` 739），而 P4 原写「当前无登记项」 | 5 个文件按拆分方向逐条登记进 P4 存量监控清单（不占用 rf 编号，拆分后逐行删除）；红线本身 0 违规、0 豁免 |
| **rf-915** | `docs/plan/` 在办设计无任务追溯：`jev-news-judgment-design.md`、`jev-news-judgment-evaluation.md` 不引用任何 `plan-XXXX`，`release.py prepare` 每轮都提「未引用任何任务编号，人工确认是否完成」，状态只能靠读文档头自判 （`decision-reflection-design.md` 已引 `plan-70`/`plan-71`，属正常） | 两份文档头部补「关联任务：`plan-55`」反向引用，追溯双向可达；`_ledger_archive.unreferenced_docs()` 复核由 2 项归零 |
| **rf-912** | 发布 `refresh` 的 bench 偶发退出码 1 而台账 `failed_tests` 为空，看不出哪个用例红——真因有两处：① `unit/web/test_runs.py::TestConcurrency::test_concurrent_submits_isolated` 的 `_wait_done` 用 3s 真实墙钟等后台线程，8 路 xdist 满载时线程迟迟不被调度即超时（时序脆弱，同文件另有 `test_retention_trim_oldest` 同类）；② `_run_phased` 的关键词过滤只留小写 `failed`，pytest 短摘要的 `FAILED 路径::用例` 行被丢弃，`_summarize_failure` 的 debug.log 兜底又只看 stdout 归档行指向的目录（那是**上一次**运行的报告目录，本次失败档的 debug.log 还在 `test-reports/latest/`）→ 连续三次发布（0.15.2/0.15.8/0.16.2）各多花一轮人工重跑与翻归档定位 | 等待预算改 `_WAIT_TIMEOUT_S = 30.0`（等到就绪而非时延断言，注释写明满载场景）；`_run_phased` 过滤补 `FAILED`；新增 `_failure_debug_text()`：归档目录未命中时按 mtime 倒序搜 `test-reports/latest/<模式>/` 的 debug.log，且 stdout 已有 FAILED 行则不读（防旧失败被当本次）。回归 4 例（假时钟下慢调度仍等到、预算耗尽报时长与末态、latest 兜底点名用例、stdout 优先于 latest） |
