# 自审记录归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.0 发布，本系列首批开发期已修复批次并入）；2026-10-25 v0.16.1 本批原表搬运；2026-10-26 v0.16.3 本批原表搬运；2026-10-27 v0.16.4 本批原表搬运；2026-10-28 v0.16.7 本批原表搬运；2026-10-29 v0.16.8 本批原表搬运；2026-10-29 v0.16.9 本批原表搬运；2026-10-30 v0.16.11 本批原表搬运；2026-10-30 v0.16.13 本批原表搬运；2026-10-30 补录 changelog-only 条目 10 条（rf-902、rf-903、rf-904、rf-905、rf-906、rf-907、rf-908、rf-910、rf-911、rf-943）；2026-10-30 v0.16.14 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.16.x 开发期已修复项（v0.16.0 → ）（含 v0.16.14）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 已修复（0.16.1）

> 完整复盘见 `changelog.md` 0.16.1 段；此处为台账原表搬运（无损），本批发布日 2026-10-25。

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

## 已修复（0.16.2）

> 补录（2026-10-30）：本批条目原先只随 changelog 变更记录留痕、未逐条登记台账；此处按 v0.16.2 changelog 段回填，问题描述未单独留存（修复列即当日变更摘要，发布日期 2026-10-26）。

| # | 问题 | 修复 |
|---|------|------|
| **rf-902** | 原问题描述未单独留存（回填自 changelog 段） | 内部兼容层沉淀为 rf-901（旧单 Provider 配置簇）、rf-902（旧凭据文件格式） |
| **rf-903** | 原问题描述未单独留存（回填自 changelog 段） | **配置默认值/结构单源续修**：`llm_settings` 渲染路径的 `schema_version` 改必填严格校验（缺失/不为 2 即报错，与加载侧同口径，rf-903） |
| **rf-904** | 原问题描述未单独留存（回填自 changelog 段） | 辩论缓存键前缀改取 `CACHE_PREFIX_LLM` 共享常量（rf-904） |
| **rf-905** | 原问题描述未单独留存（回填自 changelog 段） | `fetcher/price._price_cache_fresh` 的 `cache_key` 改必填（收盘时点校验转为必经，rf-905） |
| **rf-906** | 原问题描述未单独留存（回填自 changelog 段） | **测试离线隔离补全**（rf-906）：9 个 llm 价格/缓存用例文件补 `offline_external_sources`，消除本地「交易日历缓存过期即 62 例连带失败」的假红（CI 与本地口径对齐） |
| **rf-907** | 原问题描述未单独留存（回填自 changelog 段） | **持仓渠道判定单源**（rf-907）：新增 `core/holding_status.classify_channel(account)`，报告层两处明细组装改调它（原各自内联账户关键词判定） |
| **rf-908** | 原问题描述未单独留存（回填自 changelog 段） | **快照形态单一化**（rf-908）：`analysis/prosperity_signals` 提取持仓代码只认 `accounts[].holdings`（与 `schemas/history.SnapshotData` 一致），删除顶层 `holdings`/`details` 兜底 |
| **rf-910** | 原问题描述未单独留存（回填自 changelog 段） | **指数历史源上限可达时不触发重取**（rf-910）：`fetcher/index.py` 的「窗口缩水自愈」判据补源单次上限（约 2000 根）排除——请求 2927 天而上游给 2001 根时属源限制，此前每次运行都会清链路缓存并整段重取一遍（近 24h 6/6 次运行均命中，白打一次大请求且缓存反复失效） |
| **rf-911** | 原问题描述未单独留存（回填自 changelog 段） | **重算归因落盘口径拆分**（rf-911）：perf 的 `llm.recompute_reasons` 只放「按原因聚合计数」，逐模块明细改 `llm.module_recompute_reasons`（原实现同名覆盖，聚合计数丢失、判据无法统计） |
## 已修复（0.16.3）

> 完整复盘见 `changelog.md` 0.16.3 段；此处为台账原表搬运（无损），本批发布日 2026-10-26。

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

## 已修复（0.16.4）

> 完整复盘见 `changelog.md` 0.16.4 段；此处为台账原表搬运（无损），本批发布日 2026-10-27。
| # | 问题 | 修复 |
|---|------|------|
| **rf-919** | 页头状态行的「详情」指引指向已不存在的菜单键：写死 `〔详情 [4][H][S]〕`，而主菜单把缓存管理收到 `[3]`、持仓信息目录下沉为 `[G]` 子项，`[4]` 与顶层 `[H]` 均已不存在——按指引按键只会落空 | 指引键收敛为常量 `status_line.DETAIL_HINT_KEYS = ("3", "D", "S")`（缓存统计 / 数据源与运行日志 / 功能开关与 LLM 模块），渲染由 `_detail_hint()` 单源派生；新增守护用例对主菜单键做子集校验（菜单改键即红），并在 DESIGN-TUI 页头状态行契约写明出处。回归 2 例（指引键 ⊆ 主菜单 / 渲染文本逐键出现） |
| **rf-920** | 页头「新鲜度」自首版起恒为「—」：反推缓存键未剥 `_{版本}` 戳（拼出 `_v4_v4`）且 `cache.get` 的 `max_age_seconds` 未传（TypeError 被兜底吞掉） | 反推口径收为 `cache_key_from_file_name` 单源，`get(key, inf)`（要报的就是偏旧数据）；回归 1 例走真实读档（不 patch `get`） |
| **rf-921** | 缓存包启动清理在异常路径崩：`del _logger, _cleaned` 在 `try` 外，`clean_sensitive` 抛异常时 `_cleaned` 未绑定即删；`os.listdir` 无容错 | 初值 0 + `_cache_file_names()` 容错列举（清理尽力而为，不中断主流程） |
| **rf-922** | 用户文档与配图滞后于页头状态行改动：手册无状态行读法、`README` 仍写「缓存过期/备用源/五项」、目录树描述滞后，且「菜单分组」段落组成员写的是已不存在的键（`P/S/M/I/A/D/R`、`V/H/T`） | 手册补「页头状态行读法」+ 分组归属按 `MENU_GROUPS` 纠偏；README/`folders`/`developer-guide`/`test-coverage` 同步；配图重生成 |
| **rf-923** | 截图工具逐段步进按「字号 × 0.62」估算，等宽 CJK 字体实际步进不符 → 配色段起点累积偏移（README 配图状态行彩色段前一大段空白） | 改 `ImageDraw.textlength` 实测推进 + 画布按实测宽度；回归 1 例断言偏移 ≤4px |
| **rf-924** | cninfo orgId 反查单次挂 40.2s：20s 预算在 httpx 分阶段超时下放大成 2 倍，且失败结果不留痕——同一网络条件下每次重跑都重付一遍（实测报告 167.7s vs 上轮 121.1s，数据准备 52.7s vs 6.5s） | 该路径改端到端墙钟 8s（`post_with_deadline` 加表单编码支持）+ 1h 负缓存并区分「连接失败/源侧无该代码档案」；回归 3 例 |
| **rf-925** | 主源财报正文的「确定性空结果」未缓存：5 只 A 股均无「管理层讨论与分析」章节，每份报告逐只重走链路（合计约 10s），属可避免的重复请求 | 按 `(doc_id, section)` 记 1 天负缓存 `report_datasink_doc_miss_`（各槽原因均为确定性拒绝才写：该文档无/异源候选拒服务；任一传输失败不写）；登记进「财报索引」缓存类型；命中按轮计数并打一行 INFO 汇总（无需 DEBUG）；回归 5 例 |
| **rf-926** | 截图脚本的演示报告污染真实运行状态：`make-screenshots.py report` 会向 `data/state/perf_history.jsonl`、`datasource_health.jsonl`、`data/calibration/dedup_anchors.jsonl` 追加演示数据（实测 1 条 perf + 1 条健康），违背脚本自述的「真实 data/ 零接触」 | 跑前快照 `data/state` 与 `data/calibration`、跑后原样还原（含删除运行期新增文件）；已清理本次污染记录；补 2 例回归 |

## 已修复（0.16.7）

> 完整复盘见 `changelog.md` 0.16.7 段；此处为台账原表搬运（无损），本批发布日 2026-10-28。

| # | 问题 | 修复 |
|---|------|------|
| **rf-927** | 持仓变动复盘误报新增/清仓：演示快照污染真实快照目录，逐对差分把整批标的当真实调仓 | 事件抽取加基线切换守卫（相邻期代码 Jaccard < 0.5 跳过并标注）+ 截图护栏补 `data/history` + 隔离并删除 7 个污染快照；回归 6 例 |
| **rf-928** | 行业资金流向每份报告重复撞超时：失败负缓存只在进程内存，而每份报告是新进程 | 负缓存落盘（30 分钟、跨进程）+ 失败回退最近成功载荷（≤3 天，标 `stale`）；回归 4 例 |
| **rf-929** | 场内基金（LOF/ETF）行情被源侧简称误杀后无兜底：`_name_matches` 汉字集合重叠 0.7 阈值拒掉「白酒基金LOF」vs「招商中证白酒」，且场内基金不在降级名单 → 该持仓永久缺价 | 名称判据加「连续 2 汉字公共段」一档 + 股票链路失败后场内基金也降级净值链路；回归 3 例（含反例：不同标的仍拒） |
| **rf-930** | 演示/基准运行与真实运行共享 `logs/app.log` 与 `data/cache`：演示告警混进真实日志分析、缓存互串 | 新增 `INVEST_LOG_PATH` / `INVEST_RUN_CONTEXT` / `INVEST_CACHE_DIR` 三通道，截图工具自动注入；回归 9 例 |
| **rf-931** | 演示工作区凭据块与 provider 引用漂移：`llm_key.json` 只有旧格式 `default`，providers 引用 `deepseek-main`/`opencode-go` → 每次演示 run 刷 2 行告警 | `build()` 同源写入凭据块与 providers（同名 `demo-main`）；回归 2 例 |
| **rf-932** | 残留输出目录锁被当作持续占用：只判存在不判持有者，4 天前残留锁让每次启动刷一条告警 | 锁加陈旧判据（pid 存活 / 文件年龄 12h）并支持接管；回归 5 例 |
| **rf-933** | LLM 缓存冷启动未命中被归因为 `ttl_expired`：无上轮快照时误判「内容没变只是到点」，据此放宽 TTL 省钱是错的 | 归因补 `cache_miss` 三态（冷启动）；回归 1 例 |
| **rf-934** | `llm_settings.json` 读取失败吞掉异常原因，面板只报「读取失败按默认展示」 | 日志带异常类型/消息与路径；回归 1 例 |
| **rf-935** | 输出目录锁的 pid 探活在 Windows 上会杀进程（`os.kill(pid, 0)` 在 Windows 走 `TerminateProcess`，探测即杀） | 改 `OpenProcess` 查询句柄，无法判定退化为文件年龄判据；回归 4 例 |
| **rf-936** | 行业资金流向「陈旧回退」未标新鲜度：源不可达回退上次成功载荷后，报告与 LLM 提示词把它当今日数据 | `mark_data_used` 新增 `freshness` 通道（进事件 `detail`、不进降级计数）+ 质量块新增「陈旧回退」行 + 取数侧如实标注与告警；回归 7 例 |
| **rf-937** | 兼容层技术债：为旧形态保留的迁移/回退/再导出分支（llm_key 扁平文档自动改写、`market_hour_aware` 退役告警、穿透 `funds` 回退、TUI 再导出壳） | 全量移除并存纪律入 developer-guide「兼容层纪律」；`llm_key.json` 旧形态改为拒绝加载 + 改写指引（不迁移、不写 `.bak`）；测试同步重写/收窄（净 +5 例） |

## 已修复（0.16.8）

> 完整复盘见 `changelog.md` 0.16.8 段；此处为台账原表搬运（无损），本批发布日 2026-10-29。

| # | 问题 | 修复 |
|---|------|------|
| **rf-945** | `self_review` 缓存键随「运行元信息」漂移：自检输入含 LLM 用量页脚与事实校验摘要段落——页脚在新生成（含 Token/耗时/费用）与缓存命中（含"使用缓存"）间必然不同，校验摘要的检查项计数又随缓存态变化（命中时排名校验跳过）。结果是上游每次重算后，下一次运行的自检键必然变化，多付一次 10~15s | 自检输入改为「纯分析正文」：新增 `strip_llm_footer`（页脚，`llm/skeleton.py`）与 `strip_fact_check_blocks`（校验摘要/建议/修正明细，`fact_checker`），编排层组装自检输入时依次剥离；报告渲染仍用完整正文（校验结论与用量信息对读者有用）。同时补分段诊断日志（未命中时打印六段输入摘要，8 位），使「哪一段变了」可直接读日志判定。实测：强制重算 `global_macro` 后下一次运行自检直接命中（0.0s，6/6 模块命中，总 24.7s），此前该场景必多一次 12.8s
| **rf-946** | 事实校验自动修正不回写缓存：完全命中缓存的运行里 `counters` 仍记 `fact_fix:智囊团深度复盘=2`（连续多轮恒为 2），修正只作用于当轮输出 → 同一缓存内容每轮都要重做一次修正，且报告展示正文与缓存存储正文口径不一致（不可复现） | 修正后**回写缓存**（`skeleton.write_back_module_cache`，键取预检/写侧同源的 `cache_info[mk]["key"]`，不改指纹、不新开键）：缓存正文 = 展示正文，下一轮命中即零修正；摘要属当轮元信息不写入。摘要拼接前回写，写失败只记日志不中断；回归 6 例（含幂等：命中轮次零修正） |
| **rf-947** | 全缓存运行时数据准备占 89%，其中「财报摘要与指标」单独 5~8s（6 次 2.5~10.4s 波动）：实测日志显示每份报告都为同一批文档重发 `/documents/{id}/sections`（源侧 200 但无可用清单），5 篇 × 0.3~1.4s ≈ 5s，是快速复跑的绝对瓶颈 | 章节清单不可得记**负缓存**（`report_sections_miss_`，注册表 6h；传输级失败仍不缓存），并覆盖「非空但不可用」清单（按清单取正文全空 → 先失效再记，恢复窗口 6h），`_invalidate_sections_cache` 同清正负两键；计时拆分为「财报摘要」「财务指标」两段（原合并段无法归因）；批量取数评估为不可行（DataSinking 索引/正文均按单标的请求，akshare 多期指标按单代码）。回归 6 例（含传输失败不缓存、失效可恢复、命中计数） |
| **rf-948** | `providers/news_dedup.py` 795 行三簇混装（分片 gzip 读写 / 保留期·体积目标·采样策略 / 统计），与 `cache/` 包「存储层拆 `_io`/`_paths`」先例不一致，本批一次 +459 行后逼近 1000 红线 | 按层拆分：字节动作 → `providers/news_dedup_anchor_store.py`；保留期/体积目标/同源采样/裁剪编排 → `providers/news_dedup_anchor_policy.py`；`news_dedup.py` 保留判定主流程并原面 re-export（`compact_anchor_file` 仍单一实现）。顺带修正测试隔离：锚点路径 patch 打到实际持有者（此前打门面 → 测试追写真实 `data/calibration/`），并清理 30 行被污染样本；回归 296 例全绿 |
| **rf-949** | 负缓存探针样板复制到第 3 份：`_miss_key` 的 lock + 命中计数 + `reset_*` + get/set 在「标的正文缺失」「章节清单不可得」「某文档无该章节」各写一遍，新增一类就要再抄一遍，命名与日志口径还会漂移 | 抽 `cache/_negative.py::NegativeCache`（`probe`/`is_missing`/`mark`/`clear`/`hits`/`summary_text`；TTL 强制取注册表类型）+ 可枚举清单 `negative_cache_entries()`/`nonzero_summaries()`/`reset_all_negative_hits()`；四处调用点改为只声明「标签 + 键前缀 + TTL 类型」，报告级汇总改为遍历清单（新增类零分支）；回归 12 例 |
| **rf-950** | `perf_history.jsonl` 历史记录的 `breakdown["数据准备"]["财报摘要与指标"]` 在新版被拆成「财报摘要」「财务指标」两键，跨版本对拍时旧键孤立存在、与新键混算会让均值失真 | 读取侧加别名归一 `_LEGACY_BREAKDOWN_ALIASES`（旧合并段 → `财报摘要+财务指标（旧·合并段）` **单列**，不与新子项混算），scripts-reference 的阶段细分表标注版本分界；回归 1 例 |
| **rf-951** | 历史 K 线主机不可达时按标的白等：腾讯 K 线单标的耗时 2 分钟级（超时预算 60s × 同源重试 3 次，且挂起也算可重试失败）→ 「历史走势」阶段十余个持仓累计二十分钟；日志实证 `Tencent K 线 sz300502 传输级失败（ConnectTimeout）` 连续出现 | 分两档收敛：provider 内 `_KLINE_TIMEOUT` 60s→10s、attempts 3→2 且挂起（≥ 预算一半）不重试；链级新增 `_HANG_ELAPSED_SECONDS=20s` 判据，挂起型直接落下一槽（不重试）。回归 3 例（挂起不重试 / 快速失败仍重试） |
| **rf-952** | `/documents/{id}/sections` 传输级失败不留状态：每份报告都为同一篇文档再付一次超时预算（实测 817432 单篇挂起 20.7s，`财报摘要` 阶段 30.5s 中占 2/3），而探测本身只是取数优选路径 | 新增 30min **短退避**负缓存（`report_sections_backoff_{doc_id}`，注册表类型 `report_sections_backoff`），探测成功即清；与「确定性缺失 6h 负缓存」语义分离。回归 3 例（开退避不进确定性缓存 / 成功解除 / 失效可恢复） |
| **rf-954** | LLM 缓存换键归因跨进程不可见：指纹/键基线只存进程内存（`_LAST_FP_COMPONENTS` / `_PREV_MODULE_CACHE_KEY`），重启后无上轮基线 → 键变了也只能落进 `ttl_expired`（实测 22:52 四模块被记 ttl_expired，实际 expert_review 键 `bb5e0593dabe…` → `d86f4195c09f…`），「哪一段输入变了」无据可查 | 新增 `llm/fingerprint_baseline.py`：编排收尾落盘「各模块键 + 指纹组件哈希」到 `data/state/llm_fingerprint_snapshot.json`，下次预检读作基线；归因主信号改为「键是否变化」（键变 ⇒ `fingerprint_changed` 并打出变化组件；键未变而读不到内容 ⇒ `ttl_expired`；无基线 ⇒ `cache_miss`）。快照读写失败降级为无基线，不参与键构造；测试隔离加基线路径重定向 + 进程内复位。回归 10 例 |
| **rf-944** | LLM 关键路径：`expert_review` 独占 57–110s（≈6.1ms/输出 token），串行尾再叠加 `self_review` 11s + 归因 4–25s；且台账无逐模块耗时，关键路径只能靠日志时间戳反推 | ① 逐模块耗时入台账（`perf_history.llm.modules[*].duration_seconds`，命中记 0）；② 归因并入并行批（`_MODULE_FNS["holding_change"]` + 共享客户端 + 异常隔离，`self_review` 仍后置）；③ 注释/文档同步为并行口径并由用例机检。实测 4 次完整报告：串行尾残差 0.02/0.01/0.04s（阈值 5s）、`expert_review` p50 61.5s（阈值 83.6s）、归因 5.7–6.5s 全在并行批内、缓存全命中运行归因 0.0s；设计见归档 `llm-critical-path-instrumentation-design.md`。评估后不实施：TTL 调值、输出预算削减、thinking 降档、并发 3→4
| **rf-938** | 去重锚点 61% 是零信息量记录（`same_src` 57,899/94,706，`ratio` 恒 0.0、`merged` 恒 false），主导体积增长 | 写侧按标题对 SHA-256 哈希 **1/50 确定性采样**同源锚点（同一样本对恒定入选，`_SAME_SRC_ANCHOR_SAMPLE` 可调，1=全量）；实测存量 94,706 → 37,913 条（40%）；回归 4 例 |
| **rf-939** | 锚点保留期 120 天大于数据实际年龄（59 天）→ 压缩保留 100%，零缩减，自检压缩建议无效 | 保留期默认降到 **30 天**；保留判定改为 `ts`（发布时间）**或** `written_at`（写入时刻）任一在窗口内即保留——补录/回溯老新闻不被秒裁；回归 5 例 |
| **rf-940** | 锚点体积无确定性上限：键全唯一 + 保留期未触发，越 32 MB 只告警不回缩（约 3 个月到 100 MB） | 压缩加**体积目标 24 MB**（`_ANCHOR_SIZE_TARGET_BYTES`，与告警线分离）：超目标按最旧裁剪到 ≤24 MB，**每分支保留最新 50 条**防小分支整类消失；读取前后比对 `(size, mtime)`，并发追加则放弃本次压缩；无行可裁不重写；回归 6 例 |
| **rf-941** | 21%（20,306 条）锚点缺 `anchor_rules_version`，与在用指纹混算 | 压缩时对无指纹旧行补 `ANCHOR_LEGACY_ERA` 标注并计数；校准报告分「当前指纹 / 历史指纹 / 未标注」三桶并列出历史指纹 Top3；回归 5 例 |
| **rf-942** | 锚点维护段文档与实现漂移（写 120 天可压小、未写缺省压缩与体积上限口径） | 按三重条件重写 developer-guide / technical / requirements R-DATA-09 / scripts-reference / testplan 与自检提示；压缩结果打印超期/体积裁剪（含分支分布）/补标注/并发放弃四类计数 |
| **rf-955** | 缓存清理器按文件名前缀统一取 TTL，把同前缀下的异构寿命键一并裁掉：`sector_flow_last_good`（设计 3 天）与 `sector_flow_negative`（设计 30 分钟）都落到 900s → 陈旧回退基准活不过一次启动清理，R-BRK-09 的回退条款结构性不可达 | 注册表新增 `exact_key_ttls` 单源声明 + `get_exact_ttl_map()`，清理器按精确键覆盖前缀默认值；取数侧 TTL 同源读取；回归 6 例（对应 `plan-237`） |
| **rf-956** | `scripts/probe.py` 子探针 import 失败被静默当成「探测失败」：入口只把 `scripts/` 加进 `sys.path`，子探针的 `from src.python…` 全部 ImportError——`csi` 因此长期输出「无可用代码」的错误结论 | 入口补仓库根 `sys.path`；`_probes` 登记表加 Protocol 契约面；`sector-flow` target 实测双通道（主 0/4、备 4/4） |
| **rf-957** | `test_fingerprint_baseline.py` 两个用例依赖执行顺序：单跑通过、整目录跑必红（同目录其他用例写过内存键基线后未复位，`reset_baseline_cache()` 只清文件侧） | `reset_baseline_cache()` 同时清 `skeleton._PREV_MODULE_CACHE_KEY`（上轮基线本就是「快照 + 进程内」两个来源）；回归 1 例断言 reset 后归因为冷启动而非「键变了」 |
| **rf-953** | `HTML 生成` 阶段耗时分化（同机同持仓 0.3s ↔ 17.3s，日志内找不到对应耗时动作） | **根因**：该阶段夹带了惰性补数据（基金排名/业绩/基金经理/风格），而卡顿源是基金经理页面的 SSL 握手超时——它以 `ConnectError` 抛出而非 `TimeoutException`，未被识别成「站点不可达」，于是又去撞档案页，同一只基金连等两次（各 ~6.9s）。**修复**：连接阶段单独封顶（`httpx.Timeout(6.0, connect=3.0)` / `(4.0, connect=3.0)`），`ConnectError` 归入「站点不可达」并跳过档案页回退；回归 2 例（握手失败不赌回退 / 连接预算封顶） |
| **rf-958** | `plan.md` 概述与正文可脱钩且无告警：`plan-70` 小节被删而概述仍引用（有编号无正文的孤儿），随后压缩概述又把唯一引用删掉，任务静默消失 | P3 恢复该小节并保留单一事实位（technical §6.9）；`check-doc-drift` 新增「概述引用的 plan-N ⇒ 正文小节或计划归档存在」断言（`_PLAN_ANY_HEADING_ID` 认无状态标记的在办小节），回归 2 例（孤儿报出 / 正文存在不误报） |
| **rf-943** | 原问题描述未单独留存（回填自 changelog 段） | **去重锚点按月 gzip 分片**（rf-943）：写入改为 `data/calibration/dedup_anchors-YYYYMM.jsonl.gz`（multi-member gzip 追加，不重写既有压缩块），读取侧 `gzip.open` 透明解压、坏分片只跳过其余内容 |

## 已修复（0.16.9）

> 完整复盘见 `changelog.md` 0.16.9 段；此处为台账原表搬运（无损），本批发布日 2026-10-29。

| # | 问题 | 修复 |
|---|------|------|
| **rf-959** | 事实校验把**正确的**占比/目标权重与正确收益率改错：①「把低风险资产从当前的 18.3%（012325 12.5% + 240012 5.8%）提到 25% 附近」——18.3% 是占比、25% 是目标权重，被按最近邻改写成 012325 的 4.6% 与 240012 的 -8.0%，句子变成「从 4.6%（…12.5%+5.8%）提到 -8.0% 附近」自相矛盾；②「纳指联接 016055 +18.66%、建信装备 +21.91%」——「建信装备」是 011506 的口语简称，未解析 → 回退同句代码 016055，把正确的 +21.91% 换成 18.7%。改错后的矛盾随后被 `self_review` 当模型错误报出（矛盾由校验器制造）。根源：`_REBALANCE_TARGET_KEYWORDS` 只收「降至/升至」式、占比无「占比」字样、简称解析失败即全局最近邻兜底 | 新增三条非收益率守卫（与既有胜率/权重/止盈目标守卫同层）：①`_is_target_value_context`（数值后「附近/左右」或前 6 字「提到/提至/提高到」→ 目标位）；②`_is_breakdown_sum_context`（数值后括号内分项百分比之和 ≈ 该数值 → 合计/占比）；③`_unresolved_attached_subject`（数值紧贴的名称解析不出持仓 → 归属不可知，宁漏改不误改；时间/范围填充词与度量词先剥离）。另将 `FACT_CHECK_RULES_VERSION`（`fact-rules-2`）并入四可回写模块指纹——修正会回写模块缓存且键不变，规则语义变化须换键，否则旧缓存里被旧规则改错的正文继续复用。回归 7 例（含「守卫不过度」：可解析主体的错值仍纠正、时间填充词不遮蔽主体） |
| **rf-960** | 括号内并列多品种时数值归**首个**代码，把后一个品种的正确收益率改错：「（240012 -8.03%、561910 -36.20%）」里 561910 的 -36.20% 被改写成 240012 的 -8.0%；叠加「按数值去重（每轮只判一处）+ 修正回写缓存」，逐轮把同一事实的其余句子逐个改错，最终同一份报告与缓存里并存 -8.0% 与 -36.20%，且下游自检把矛盾当模型错误报出 | ①`_locate_subject_code` 括号作用域取**最近**代码（原来取括号内首个）；②去重粒度改为「(数值, 所在句)」——跨句各自判定，后续句里的同一数值同样受检；③改写改「全有或全无」：同一 wrong_value 的全部出现处都判错才整体替换，同句同值多义（止盈 30% 与收益率 30%）或仅部分判错则整值跳过（一处也不改）；④同句同品种只可能有一个持仓收益率——该品种收益率已确认后，句内它的第二个百分数按非收益率跳过（括号里的占比 7.3% 曾被改写成 -36.2%）；⑤`FACT_CHECK_RULES_VERSION` → `fact-rules-3` 一次性换键。回归 8 例（括号并列两品种各自的正确值都不改、错值仍按自身收益率纠正、同值多义不改、全判错才整体替换） |
| **rf-961** | 权重类表述被按收益率改写：①「它现在仍占 7.3%」——中文最常见的权重表达「占 X%」，`_NON_RATE_PRE_WORDS` 只收「占比」，裸「占」未识别，7.3% 被改成 561910 的 -36.2%；②表格行「| 建设银行 | 601939 | 8.8% | 6.5% | 减仓 | …持仓收益率 −8.03%…」——权重列与目标列是裸百分比、单元格内无任何语境词，按就近代码归因把 8.8%/6.5% 都改成 241.5%（实测单轮 9 处「修正」全是这一类）；③「已修正明细」按**判定**列表生成而非按**实际生效**，归属不可知被跳过的项仍被宣称已修正，读者无法判断正文是否真被改过；④负缓存探测（`probe()` 读不到记录 = 该缺失不存在，属正常预期）计入全局缓存未命中，虚计每轮 7~13 次并误触发「同前缀未命中 ≥5 次」告警 | ①`_NON_RATE_PRE_WORDS` 增「占」「仓位占比」；②新增 `_is_table_weight_cell_context`——数值是独立表格单元格且同行还有另一个独立百分比单元格时整体跳过（单列百分比仍校验）；③`apply_numerical_corrections` 增 `applied` 出参，runner 只把真正替换的计入明细/计数/摘要，被跳过项也不列为告警；④`cache.get` 增 `record_stats` 参数，`NegativeCache.probe` 传 False。`FACT_CHECK_RULES_VERSION` → `fact-rules-4`。回归 10 例 |
| **rf-962** | 兼容层存量清理：按本项目「不承诺兼容旧数据文件 / 旧数据结构 / 旧缓存（结构）/ 旧内部 API」的口径，代码里仍留有多处纯兼容分支，增加理解与维护成本：①`analysis/metrics.py` 重复声明 4 个常量（仅供外部直接引用，实际实现与唯一使用点都在 `metrics_returns.py`）；②`get_rate_limiter` 上被挂了一个`cache_clear` 属性（兼容旧调用点，已有模块级 `clear_rate_limiter_cache()`）；③`_benchmark_returns` 同时接 list 与 dict 两种形态（生产只有 list）；④锚点读取/压缩/体积统计/doctor 检查都额外接纳「未分片的早期单文件」（`dedup_anchors.jsonl`），含把它并入分片后删除、以及「含旧版单文件」的提示文案 | 全部移除并按新契约收紧：①删重复常量（`whatif_backtest` 改从 `metrics_returns` 取）；②`get_rate_limiter` 上的属性已移除，调用方统一走 `clear_rate_limiter_cache()`，测试相应改写并新增断言「该属性不存在」；③只接 list；④`anchor_shard_paths` 只认 `dedup_anchors-YYYYMM.jsonl.gz`（不读、不并入、不统计单文件）；相关测试改为写按月分片，并把「旧单文件仍可读」反转为「旧单文件被忽略」。**保留项（经判定不属旧格式兼容）**：`.json`/`.json.gz` 双缓存编码（均为现行格式，按体积阈值切换）、`_detail_value` 的 dict/对象双形态（两种形态均在生产使用）、`tiantian_holdings` 的季度接口回退（数据源备用通道，非我方格式）、`_llm_schema` 保留未知模块（前向兼容，防新版配置被旧代码截断）、`holding_status` 归一 Excel 浮点假象 `"600900.0"`（属现行输入形态）。回归 4 例 |
| **rf-963** | 缓存命中率被**状态探针**污染：历史数据增量链路对每只标的多读一次 `{cache_key}_correction_streak`（连续触发计数），读不到即「未连续触发」属正常预期，却按缓存未命中统计——单轮虚计 17 次，命中率从 100% 掉到 94%，并触发「同前缀未命中 ≥5 次」告警（告警本身正确，但指向的是计数口径而非真问题） | 两处 streak 读取改传 `record_stats=False`（与负缓存同一口径：状态量探针不计入命中率，其值另由自身写入路径维护）。实测同机连续两次运行：`[cache] 本次命中 157 / 未命中 0（100%）`，此前为 `555 / 38（94%）`，未命中前缀 `history_history 17 / report_datasink 13 / report_symbol 7` 全部归零 |
| **rf-964** | ①**板块/指数涨跌被改写成品种收益率**：「银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%」被全局最近邻兜底改写为某品种收益率（先 102.0%、后 4.6%，随最近邻漂移）；更贵的是它**回写缓存** → 下一轮自检输入段变化 → 每轮多付一次 11~17s 自检调用（长驻进程连跑三份报告稳定复现）。②**缓存命中率汇总按进程累计而非按轮**：`reset_cache_stats` 只有定义与导出口，生产侧从不调用，长驻进程连跑时「本次命中 X / 未命中 Y」累计成进程累计值（实测未命中前缀 5→10→15 递进），「同前缀未命中 ≥5 次」告警随之失真 | ①新增 `_MARKET_SCOPE_NOUNS` + `_is_market_scope_no_subject`：分句含板块/指数/大盘类名词**且**分句内出现不了任何持仓主体（代码/全名/简称/尾名）时跳过改写（归属不可知）；②`report/_run_scope.start_report_run()` 增 `reset_cache_stats()`，与降级事件、自检载体重置同处；③`FACT_CHECK_RULES_VERSION` → `fact-rules-5`（缓存里已被改错的正文需失效重算）。回归 5 例（板块涨跌不改、指数涨跌不改、含持仓主体的错值仍纠正、报告边界清零计数） |
| **rf-965** | ①**指数涨跌被改写成基金收益率**：`纳斯达克100涨1.18%、标普500涨0.60%` 里的 1.18% 被改成 016055 的 18.7%——指数中文名与基金名重叠（「纳斯达克100」同是 016055 名称的一部分），「分句内有无持仓主体」的判据在此失效；改错后同样回写缓存，使下一轮 `self_review` 重算（实测 16.4s）。②**自检输出上限过低反复触顶**：`max_tokens_self_review=3072`，实测输出恰好 3072 被截断 → 自动以 4608 重生成，同一份自检付两次调用且多等 5~8s。③**版本盐在日志里不可见**：两个版本号都会整批换键，但运行日志无痕迹，模块整批重算时只能翻代码比对指纹。④「同前缀未命中」告警只说前缀不说键，看到还得回 DEBUG 翻 | ①市场口径判据由「分句内有无主体」升级为「市场名词与持仓主体谁更近」，并按**位置重叠**排除「市场名词其实属于某持仓简称」（`_subject_spans` 代码/全名/简称三级区间 + `_alias_normalized` 位置回映）；词表补 纳斯达克/道琼斯/富时/科创50/创业板指/北证；②默认上限 3072→4608；③新增 `fingerprint.cache_key_salts()` / `log_cache_key_salts()`，报告边界打「本轮开始」、收尾 `[cache]` 汇总行带版本盐尾注；④告警追加该前缀下未命中次数最多的 5 个具体键（键名计数有界 500）。`FACT_CHECK_RULES_VERSION` → `fact-rules-6`。回归 9 例 |
| **rf-966** | 近 24 小时变更的技术债核查发现 6 项：①**分层越界**——`cache/_stats.log_cache_summary` 反向 `import llm.fingerprint` 取版本盐（cache 是基础层，只能依赖下层与贯穿层；该 import 无环但方向错，且 check-import-surface 查不出）；②**运行收尾日志分散**——缓存汇总由 `core/perf.save()` 打、版本盐由报告层打，同一「本轮结束」信息分两处；③**主体匹配三份实现**——`_locate_subject_in`（取代码）/ `_has_subject_candidate`（取布尔）/ 数值检查器本地 `_subject_spans`（取区间）各写一遍同一套「代码→全名→简称归一」匹配，口径一分叉就出现「主体解析得到、距离算不出」的内部不一致；④**规则版本注释写成逐版沿革**——代码注释列 v2~v6 变更史，与「注释只述现状、沿革归 changelog/review-findings」的纪律冲突（守护反复报痕迹）；⑤`_key_prefix` 文档示例输入输出不符；⑥`chain_incremental` 连续触发计数两处重复同注释读法，且 `int()` 遇非数值（脏数据）会中断取数主链、日期缺失时 `.get("date")` 比较抛 TypeError | ①`log_cache_summary(top, salts_note="")` 由调用方传入版本盐，cache 侧只依赖 cache；②新增 `report._run_scope.finish_report_run(perf)` 统一收尾（落台账 + 版本盐 + 缓存汇总），缓存汇总由该 hook 统一打，`perf.save()` 只负责落台账，4 处调用点改走该 hook；③`_subject_spans` 下沉 `_utils` 作单源，`_has_subject_candidate` 由它派生（描述性尾名单独兜底），数值检查器改为 import；④版本注释只留「递增判据 + 现状口径位置」；⑤示例改为 `llm_expert_review_…` → `llm_expert_review`；⑥抽出 `_correction_streak_key` / `_read_correction_streak`（非数值按 0），日期比较加字符串前置判定。回归：`unit/llm`+`unit/fetcher`+`unit/cache`+`unit/core` 全绿，新增/改写 3 例（版本盐由调用方传入、计数键脏数据按 0、日期缺失不比较） |
| **rf-967** | dev 连续 8 次推送在 GitHub CI 的 `portability` job 变红，本地三档门禁全绿：`test_ruff_exclude_contract.py` 两例用 `subprocess.run(..., text=True)` 未传 `encoding=`，在 `PYTHONWARNDEFAULTENCODING=1` + `pytest.ini` 的 `error::EncodingWarning` 下直接抛异常。本地不设该环境变量故无从暴露，属典型「本地绿、CI 红」环境差异 | ①两处调用补 `encoding="utf-8"`；②新增静态回归守卫 `src/test/unit/test_subprocess_text_encoding_contract.py`——AST 扫描 `src/python`/`scripts`/`src/test` 全部 `subprocess.*` 调用，凡开了文本模式（`text=True` / `universal_newlines=True`）而缺 `encoding=` 即失败，并附扫描器自检 4 例（能抓到缺 encoding / 接受显式 encoding / 认 `universal_newlines` 别名 / 不误报二进制模式），避免用例恒真。**本地验证口径**：`PYTHONWARNDEFAULTENCODING=1 pytest src/test/unit` 全量通过（12327 通过），与 CI 该 job 同源 |

## 已修复（0.16.11）

> 完整复盘见 `changelog.md` 0.16.11 段；此处为台账原表搬运（无损），本批发布日 2026-10-30。

| # | 问题 | 修复 |
|---|------|------|
| **rf-973** | 演示截图隔离不完整：`isolation_env` 只改日志/缓存/运行上下文，而配置与持仓路径由 `PROJECT_ROOT`（代码位置）解析 → `web`/`cli` 子命令读到真实 `data/config` 与真实持仓，截图里出现真实账户名、文件名与市值 | `core/constants.PROJECT_ROOT` 支持 `INVEST_PROJECT_ROOT` 覆盖（把 data/reports 整体搬到演示根，缺省行为不变）；`isolation_env` 注入该变量；`make-screenshots.py` 各子命令入口加 `assert_demo_holdings()` 护栏（演示持仓必须存在且位于演示目录内，否则拒绝截图） |
| **rf-971** | 「同前缀未命中 ≥5 次」告警每轮都误报：判据按前缀累计，把「冷启动 20 只基金各取 1 次」和「负缓存/纠偏计数探测」（`report_symbol_miss_*`、`*_correction_streak`，未命中才是正常）都算成故障 | 判据改为**同键重复**（≥3 次/轮）并点出具体键；`_miss_` / `_correction_streak` 探测键不进未命中分桶（全局命中率计数不变）；回归 4 例（同键告警 / 分散首次取数不告警 / 探测键不计 / 键计数有界） |
| **rf-970** | 自检输出上限再次触顶：`max_tokens_self_review=4608`（3072→4608 已是上一轮修复值）在满编持仓下仍被截断 → 自动放大重生成，同一份自检付两次 LLM 调用并多等 5~8s | 默认抬到 8192（常见模型输出上限区间，只封顶不预扣费）；`llm-technical.md` 默认值同步；自检输出长度随持仓与事件表单调整单调增长，故一次抬足余量 |
| **rf-972** | 同花顺 provider 把「该源无此标的」也记 WARNING：中证 800 行业指数（000919/000925/000930）thscode 不被识别返回 `code=1002`，每份报告刷 18 条告警，看起来像链路故障 | 业务错误码分级：`_EXPECTED_ABSENCE_CODES = {1002, 3001, 3002, 3004}` 只记 INFO（链路照常递补下一源），其余错误码仍 WARNING；回归 1 例（4 个缺失码均不产生 WARNING） |
| **rf-969** | 每次读取持仓都刷一条 `[WARNING] 工作表 '交易流水' 表头不匹配 …跳过`：主表解析把「交易流水」「分红流水」页签也按账户四列校验，必然不匹配；流水页签由 `read_flow_sheets` 另行解析，该告警纯属误导（用户会以为流水记录损坏） | `_parse_workbook` 在解析前跳过已知流水页签名（不校验、不告警，仅 DEBUG），未知页签的告警行为保持不变；回归 2 例（流水页签不告警 / 未知页签仍告警） |
| **rf-968** | 持仓录入入口初版占用顶层字母 `T`，与 `[D]` 二级的系统自检同字母：为实现它须放宽四处既有守卫，属「改守卫迁就键位」的倒置 | 入口键改为未占用的 `U` 并独立成「持仓维护」组，四处守卫原样保留（`T` 仍只在 `[D]` 二级）；顺带把 `len(MENU_ITEMS) == 14` 改为唯一性与非空结构断言（写死条数属良性新增即红的假回归） |

## 已修复（0.16.13）

> 完整复盘见 `changelog.md` 0.16.13 段；此处为台账原表搬运（无损），本批发布日 2026-10-30。

| # | 问题 | 修复 |
|---|------|------|
| **rf-974** | 熔断退避被「单批并发失败」瞬间打满：`eastmoney_industry` 在 0.79 秒内连续 6→12 次失败，退避 60s→300s→900s→3600s 全在同一秒内升完，主通道因此离线 1 小时 | `record_failure` 加熔断期闸门：已熔断期间到达的在途失败只计数、不升级退避（升级只发生在冷却期满后重新熔断）；回归 3 例（同批 10 连败仍停级别 0 / 跨批重熔才逐级升 / 冷却期满放行） |
| **rf-975** | 基金持仓冷路径单只标的长尾 + 重试不可见：`jjcc` 对 159632 抛 SSL handshake timeout（22s）后重试 47s 才成功，日志上表现为一段无解释空白 | 季报请求改分阶段超时（connect 8s，读写 15s）；季报回溯与 `jjcc→zqcc` 通道递补各打一行 INFO（`[fund_hold] … 无持仓，回溯上一季度` / `jjcc 无数据，改用 zqcc`）；回归 3 例（超时值有界 / 递补上屏 / 回溯上屏且末季不上屏） |
| **rf-976** | 单次运行内重复装配刷屏：「批量行业数据就绪」8 次、事件窗装配与新闻关联各 3 次，同一行日志重复 N 份掩盖阶段边界 | 新增 `core/log_dedupe.py::log_throttled`（同 key 时间窗 60s 内折叠为 DEBUG，窗口外照常上屏），接入行业批量 / 事件窗装配 / 新闻关联三处；回归 6 例（窗口内折叠 / 窗口外再上屏 / 键独立 / 重置 / 级别透传） |
| **rf-977** | 新闻源空渠道静默 + 汇总标签误导：07–17 点运行 CCTV 恒 0 条无任何提示，汇总行却写「财新网 / CCTV: 100 条」（实际只有财新命中） | `fetch_news` 给条目打 `_channel`（单一漏斗打标），空渠道单独成行 `CCTV: 0 条（空源）`；聚合器标签改按本次真正出条目的渠道拼接（`财新网` / `财新网 + CCTV`），`get_last_source_status` 同步；回归 4 例（空源上屏 / 打标 / 单渠道标签 / 双渠道标签） |
| **rf-978** | 事件窗丢弃率高且成因不可归因：26 条关联新闻 `unmatched` 13–17、可出行恒 5 条，日志只有合并计数；`分歧例块` 5/5 次 0 字符也无从判断 | 跳过原因拆分 `no_keywords`（新闻关联召回为 0）与 `not_in_holdings`（索引未覆盖）并保留 `unmatched` 合计；装配行新增「跳过明细 + 比对分布」，视图摘要同步；回归 2 例（两类分别计数且互不串） |
| **rf-979** | 热路径墙钟与成本主体不可归因于日志：`[perf] LLM+新闻` 只给总秒数，看不出慢在哪个模块（台账里其实有细分） | 阶段行附带最慢三项子耗时（`[perf] LLM+新闻: 94.3s（智囊团深度复盘 75.7s / 持仓体检报告 40.2s / …）`），复用既有 breakdown 记录器；回归 2 例（前三上屏且第四不带 / 无子项时不追加空括号）。`reasoning_effort_{module}` 与模块级耗时台账本已存在，无需新增开关 |
| **rf-981** | CI 在 dev/master/tag 四条流水线上连红（matrix 三档 + portability 均挂）：`test_make_screenshots.py::TestEntry::test_report_subcommand_returns_underlying_exit_code` 在 CI 抛 `RuntimeError: 演示持仓文件不存在`——用例只 mock 了 `run_report`，入口护栏 `assert_demo_holdings()` 仍读默认 `docs/tmp/screenshots/demo`（git 忽略域），本地因跑过 `make-screenshots.py demo` 而假绿 | 用例改为 hermetic：`DEFAULT_ROOT` 指向 `tmp_path` 并先跑 `demo` 子命令真建工作区，再断言退出码透传；另补回归用例「工作区缺失时入口拒绝且不调用 `run_report`」（守住隔离护栏本身） |

## 已修复（0.16.14）

> 完整复盘见 `changelog.md` 0.16.14 段；此处为台账原表搬运（无损），本批发布日 2026-10-30。

| # | 问题 | 修复 |
|---|------|------|
| **rf-982** | 已解决台账整批漏搬：v0.16.5 起的 9 个发布周期里 53 条 rf 条目全部堆在 `## 已解决问题` 直属层（未写 `### 开发期已修复（X-dev）` 节头），而 `apply_rf_archive` 把「本版无该节」当成「本版无待迁档」、`gate` 同口径判 `absent` 跳过断言——归档文件停在 v0.16.4，10 次发版零告警 | ① `apply_rf_archive` 回落：本版节缺失时把直属层表按本版归位并补出节头（缺节时按直属层表归位）；② `rf_archive_status` 新增 `unfiled` 态（直属层有台账行即报数），`gate` 对 `unfiled` 直接 ERR；③ `check-doc-drift` 分区纪律新增 E 条：已解决区版本节之外出现台账行即提交期报错（`prepare` 之前就拦住）；④ 按 git 首次包含 tag 反查归属版本，补齐 0.16.7/0.16.8/0.16.9/0.16.11/0.16.13 五个批次归档；回归 4 例（直属层归位/幂等/unfiled 状态/真实台账无漏写 + 分区纪律正反例） |
| **rf-983** | 归档批次标题沿用了开发周期号（`## 开发期已修复（0.16.11-dev）`），而归档记录的是**已发布**版本：v0.16.11 已打 tag 发布，读者会把已发布批次读成「开发中」状态；说明行同指 `changelog.md 0.16.11-dev 段`（该段在发布时已改为 `## [0.16.11]`） | 批次标题改为 `## 已修复（X.Y.Z）`（发布版号）、说明行改为「`changelog.md` X.Y.Z 段」；v0.13.x~v0.16.x 既有归档 26 个批次节按同规则迁移（旧式 `## vX.Y.Z 开发期已修复（日期）` 属更早历史形态，保留）；`has_archive_section` / 回归断言 / 脚本文档同步；新增用例断言批次标题用发布版号且不含 `-dev` |
| **rf-984** | 历史台账引用残迹：归档 changelog 段提及的 62 个 `rf` 编号在 rf 台账与归档中无对应条目（rf-37~50、rf-480~508、rf-516、rf-565、rf-711、rf-790、rf-822/823/829、rf-863~866、rf-901~911、rf-943）——这些批次当时以「审查报告」形态记录、未逐条登记台账，编号只散见于 changelog | 按 changelog 段回填 62 条到对应版本归档（v0.8.10 / v0.11.10 / v0.11.11 / v0.12.2 / v0.14.1 / v0.14.5 / v0.14.6 / v0.15.2 / v0.16.2 / v0.16.8），每个批次节标注「补录（2026-10-30）」并说明问题描述未单独留存（修复列即当日变更摘要）；归档头部「归档时间」追加补录戳记 |
| **rf-985** | 台账段序无统一口径也无断言：归档追加与人工补录混用后，review-findings 归档把 0.16.2 批次排到 0.16.13 之后，changelog 归档 v0.2~v0.11 多为倒序（新→旧）、v0.12 起为正序，plan 归档按 plan-N 乱序——同一事实在不同文件里读法相反 | 定口径：version 段（`## 已修复（X.Y.Z）` / `## [X.Y.Z]` / `### 开发期已修复（X-dev）`）与 plan 条目自带完成版本，在**同一文件内**一律升序（旧→新），现行文件与归档文件同口径；① 归一现存文件（changelog 归档 9 份、review-findings 归档 4 份、plan 归档 7 份按口径重排）② `check-doc-drift` 新增第 23 项 `check_ledger_order` 每次提交守卫（现行 + 归档全扫） |
| **rf-986** | 章节改名后未同步配置面板显示名：报告章节已改「财经热点关联分析」，而 `[C]` 面板第 2 项仍叫「市场新闻」，同一章两处叫法不一致（用户按 C 一眼即见） | `config/chapter_registry` 的 `enable_news` 显示名改为报告章节名；同一章的 LLM 增强行（`news_correlation`）显式标「（LLM）」区分本体与增强；config 模板行尾注释、CLI 示例、手册（配置参考/配置手册/FAQ/报告说明/TUI 菜单）同步；回归 1 例锁定「面板章节名 == 报告产物章节名」 |
| **rf-987** | `[C]` 面板长章名把开关状态挤出屏幕：行排版先拼 `名称 + 状态 + 键名` 再整行截断，窄屏（手机终端 34~40 列）上「是否开启」被切掉，用户看不到开关态 | `_format_row` 先按剩余宽度截断名称（预留 光标 + 编号前缀 + 间距 + 状态 + `*`），状态与 `*` 永不被截；同一报告章的 LLM 增强行标签缩短为「财经热点关联分析（LLM）」；回归 1 例按多种列宽 × 置灰 × `*` 断言状态可见 |
| **rf-988** | 状态条中止键与文档相反：`LiveStatusBar` 的 `cancel_hint` 缺省值是已撤回的「q 中止」（有序中止键当前无渠道监听），而 `progress._draw` 直接取该缺省值拼状态条——TTY 上实显「… · q 中止」，用户按 `q` 无任何反应；而 DESIGN-TUI 与两本手册统一写 `Ctrl+C 中断`，且 `status_bar_text` 的 docstring 参数名（`cancel_hint`）与形参（`hint`）不符 | 新增模块常量 `CANCEL_HINT` 作单一来源，`status_bar_text` 与 `LiveStatusBar` 两处缺省同取该常量，docstring 参数名对齐；回归 3 例（状态条缺省 == 文档口径 / 报告器拼接走同一常量 / 模块源码不含无监听方的键） |
| **rf-989** | 配置面板会话是模块级单例，但 conftest 无 autouse 复位：`handlers_config._session` 非空时 `_apply_edit` 必然把写盘记入撤销栈，而直接调 `_apply_edit` 的用例不进面板、不复位——上一用例遗留的会话让本用例的写入记入别人的栈（部分用例靠手写 `_session = None` 绕开，即该缺口的旁证） | conftest 新增 `_auto_reset_config_session`（进/出两侧均关闭会话），与 `_auto_reset_provider_registry` 同习语；回归 2 例（进入用例时会话恒为空 / fixture 进出两侧都复位污染态） |
| **rf-990** | 截图入口 `xlsx` 的 `--rows` 缺省写死 26，与渲染模块 `DEFAULT_MAX_ROWS` 双源（改一处即漂）；同文件里列上限 `26` 以裸数字在判定与文档串各写一遍 | 入口缺省改取 `xlsx_frame.DEFAULT_MAX_ROWS`，列上限收敛为模块常量 `_MAX_COLUMNS`；回归 1 例（解析缺省值 == 渲染常量） |
| **rf-991** | `tui_menu._config_cache` 同为模块级单例且无测试复位（与 rf-989 同类）：首次 `refresh_config()` 后缓存常驻，而页头/菜单渲染走 `get_config_cache()`——不主动 `refresh` 的用例会读到上一条用例 monkeypatch 过的配置快照，断言随执行顺序漂移 | `tui_menu` 新增 `reset_config_cache()`（只丢缓存、不读盘、不动首用检测记忆），conftest 新增 `_auto_reset_config_cache` autouse（进/出两侧复位），与 `_restore_menu_items` 同习语；回归 3 例（进入用例缓存恒未载入 / reset 不触发读盘 / fixture 双侧清污染态） |
| **rf-992** | `[C]` 面板可读性债：`run_report_chapters_panel` 单函数 247 行（项表拼装 + 快照读取 + 开关派发 + 帮助解析 + 整屏渲染 + 主循环混在一起，定位任一行为都要滚完整段），`_format_row` 声明 13 个关键字参数（排版预算与逐行内容混在同一签名，调用点两处各写 13 行） | 拆为 `_ChaptersPanel`（会话态：llm 快照 / 费用摘要 / 撤销会话；方法 `status`·`toggle_chapter`·`toggle_sub`·`build_items`·`on_text`·`help`·`layout`·`render`·`run`），入口函数只剩两行编排；排版预算与行内容分家——`_RowLayout`（整屏不变）+ `_ChapterRow`（逐行变），`_format_row(row, layout)` 两参数。行为不变：既有渲染/写盘/闸门/帮助 113 例全过 |
| **rf-993** | 模块级会话态大量存在但复位口径靠人记：21 类运行期状态（注入的传输层工厂、适配器巡检函数、熔断展示判定、因子目录缓存、新闻源命中快照、季度回放锚点、按键解析残留、防连按保护位、惰性注册标记、各类限速器与统计计数器等）分散在各模块，其中 13 类连复位入口都没有，conftest 仅覆盖了少数早先暴露的那几个——漏接的后果是测试顺序相关（上一条用例注入的桩或残留标志带到下一条，xdist 换分片即随机红），而本地单进程顺序常常看不出来 | ① 补 13 个复位入口（`tui_keys.reset_key_parser_state` / `tui_handlers.reset_busy_state` / `report_artifacts.reset_open_failure_memo` / `fund_style_base.reset_tencent_registration` / `news_aggregator.reset_last_source_results` / `tiantian_holdings.reset_quarter_walk_anchor` / `doctor.reset_adapter_survey` / `http_client.reset_transport_factory` / `source_adapter.reset_adapter_registry` / `factor_catalog_loader.invalidate_catalog_cache` / `eastmoney.reset_eastmoney_pager_limiter` / `akshare_extras.reset_failure_state` / `circuit_breaker.reset_circuit_text`）；② conftest 新增 `_auto_reset_module_state`（进/出两侧，共 21 项，含已有 API 的 8 项）；③ `circuit_breaker` 复位到**导入期基线**而非 `None`（装配期接线不可被测试隔离清掉，否则展示退化成「正常」）；④ 新增契约用例 `test_module_state_reset`：反向枚举 `src/python` 全部 `global` 改写变量，要求所在模块有复位入口**且**被 conftest 调用，导入期常量走带理由的豁免表（并对豁免项做陈旧校验） |
| **rf-994** | `core/logger` 六个生效值（`_LOG_FILE` / `_LOG_MAX_BYTES` / `_LOG_BACKUP_COUNT` / `_CONSOLE_COLOR` / `_CONFIG_FILE_LEVEL` / `_CONFIG_CONSOLE_LEVEL`）无测试隔离：它们由 `_apply_logger_config` 从 env + `logger.json` 推导后**原地改写**，而 `test_logging_config` monkeypatch 的只是输入（临时配置路径）——推导结果不回退，临时日志路径与 DEBUG 级别留在同 worker 给后续用例（与 `_restore_llm_pricing_state` 记录过的定价事故同一模式：单跑绿、并行偶发红）。另：rf-993 的豁免表把 `llm/pricing` 误标为「导入期常量」，而它实际已由 `_restore_llm_pricing_state` 快照回填，属误豁免 | conftest 新增 `_restore_logger_state`（会话内快照 6 个常量、`yield` 后回填，零 I/O、不重配 handler——不接 `reload_logger_config()` 是因为那每条用例都要读盘且会与 pytest 捕获 handler 抢位）；契约用例判据补「属性级快照回填也算接线」（原判据只认 `reset_*()` 调用，认不出定价那类），并从豁免表删除 `logger` / `pricing` 两项（豁免表现在只剩无线程池语义的 `_cache_refresh` 与靠专用 setter 的 `_config_defaults`）；回归 1 例（污染后回填到基线） |
