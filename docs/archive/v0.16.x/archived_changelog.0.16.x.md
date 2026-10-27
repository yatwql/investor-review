# 变更日志归档 — v0.16.x

> 归档时间：2026-10-27（v0.16.4 发布并入；已并入 5 段：v0.16.0（10-25）、v0.16.1（10-25）、v0.16.2（10-26）、v0.16.3（10-26）、v0.16.4（10-27））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.16.0 ~ v0.16.4（2026-10-25 ~ 2026-10-27）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.16.0] - 2026-10-25

- **LLM 调用日志行单独上品红（TUI / 控制台）**：报告运行时每次真实 LLM API 调用都以 `[LLM]` 开头（`[LLM] <模块>: 输入/输出 tokens`、`[LLM] 正在调用 …`），控制台格式器与 `[D]→[V]` 日志查看器凭此前缀上品红，滚屏进度行里一眼能看出“真的花钱调用了”；`[LLM 预检]`、`缓存命中`、`已禁用` 等判定/跳过行不上色——颜色只承诺“这里真的调用了”。级别色优先：`[LLM]` 行若同时是 WARNING/ERROR 仍按状态色。判据单点实现在 `core/logger.is_llm_call_message`，配色角色已登记 `DESIGN-TUI.md`（新增「事件（LLM 调用）」一行）；回归用例 9 例（前缀判据 / 品红上色 / 级别色优先 / 无色模式 / 查看器同源）。

## [0.16.1] - 2026-10-25

- **归还 360 小时（15 天）实施变更的技术债（rf-889 / rf-890 / rf-891 / rf-892）**：① 删掉评测包 `llm_call.py` 里三处与 `holdings.py` 逐字重复的持仓侧函数（其中一份引用已搬走的 `fact_checker._calc_portfolio_values`，被调即 ImportError，属潜在哑弹）——rf-889；② 三家行情源（sina / sina_kline / tencent）各自一份逐字相同的 `_add_prefix` 收敛为 `providers/utils.with_exchange_prefix`，改一处即三处同步，不再能静默取错代码——rf-890；③ 因子动物园评测脚本内联的 3 个公式（有意避开 src 私有名）加同源数值测试，公式漂移即红——rf-891；④ 生产代码 6 处拿 `assert` 当类型收窄/入参校验（`python -O` 下会被剥离，炸点后移且信息更差）改为显式分支/告警，现全仓生产代码 `assert` 清零——rf-892。
- **归还 36 小时实施变更的技术债（rf-882 / rf-883 / rf-884 / rf-885 / rf-886 / rf-887 / rf-888）**：① 注释混入西里尔字母已改正（rf-882）；② 配置时效自检把「文件解析失败」与「缺新键」分开报，原先语法错会被说成「缺全部 40 个新键」（rf-883），非 UTF-8 文件不再冒泡异常（rf-884），`import json` 提到模块顶部（rf-885）；③ 删掉零调用的 `core/costs.add_cost_bucket`（rf-886）；④ 重算原因改为引用 `observation.RECOMPUTE_*` 常量（此前字符串字面量散在预检/骨架两路），并对域外值告警一次（rf-887）；⑤ 补 provider 默认模板与路线说明的对齐回归，新增线路漏写说明会红（rf-888）。
- **`llm_providers.json` 出厂默认换成 DeepSeek + OpenCode Go**：`_DEFAULT_LLM_PROVIDERS` 由通用示例（`deepseek-main` + `gemini-fallback`）改为两条 Anthropic 兼容线路——`deepseek-main`（priority 10，按量付费、不限速）与 `opencode-go`（priority 20，订阅制编码中转，带 `pacing` 限速：间隔 ≥5s / 在途 ≤1）；模板注释也改成针对这两条线写（各自配哪个凭据块、pacing 为何只加在第二条、调序入口），不再是通用说明（新增 `_PROVIDER_NOTES` 按线路名对齐注释，改线路只动 dict）。配置指南同步给出两套配法示例（DeepSeek + OpenCode Go / DeepSeek + Gemini）。
- **系统自检新增「配置说明时效」**（`[D]`→`[T]` / CLI `doctor` 的「配置」组）：对比 `config.json` / `llm_settings.json` / `llm_providers.json` 与当前生成器模板——**缺新键**判失败（新功能开关在用户文件里不存在），**仅缺说明**判通过但建议重生成（注释可能指向已改名的菜单键）。背景：菜单键从 P 改到 C、新增 `notify`/`scheduler` 等键后，用户持有的旧文件不会自动跟随，只会照着旧注释找不到入口（实现 `config/_config_freshness.py`，注释抽取对字符串内的 `//` 免疫——`https://…` 不会被当成注释）。
- **`features.json` 重建带逐项说明**：紧凑单行文件将被重排版时，每行尾部自动附上注册表的「显示名：一句话说明」，用户手工编辑不必回查文档；末项不带尾逗号、整体可被注释剥离器解析。
- **配置指南新增「配置文件随版本更新」节**：说清键与注释只在生成时写入、自检怎么提示、各文件重生成前需要抄回哪段自定义值。

## [0.16.2] - 2026-10-26

### 新增

- **配置默认值单源守卫（DEFAULTDUP）**：`check-code-traces.py` 增第四条 AST 支路，检出与默认值表同值同键的字面量兜底（`x.get("<键>", <默认值>)`）；默认表自身与测试不在扫描域，退出码归 CODE 桶（2）。回归 12 例（`test_trace_config_defaults.py`：检出/豁免/类型敏感/真实仓库零 finding）

### 变更

- **配置项默认值收敛**：`get_default()` / `get_llm_setting_default()` 支持点分嵌套路径（`a.b.c`）与逐层传参；生产代码 47 处「默认表同值字面量兜底」改走单一入口，`output_dir` 五处回退链统一走 `resolve_output_dir()`（相对串随 CWD 漂移）
- **debate 段默认值单源**：`_DEBATE_CONFIG_DEFAULTS` 由 `_DEFAULT_LLM_SETTINGS["debate"]` 深拷派生，删除原第二份字面量（`procon.per_call_max_tokens` 曾一处 `None` / 一处 `18432` 不一致；`max_total_tokens_per_report` / `per_call_timeout_override` 另有三套兜底）
- **provider 缺省优先级统一**：提取 `DEFAULT_PROVIDER_PRIORITY` 到 `_llm_providers_defaults.py` 并经 `config` 公开导出，替换排序/展示 9 处字面量（`llm_module_info.py` 原用 999 与其余 99 不一致）
- **报告深度档位常量下沉**：`REPORT_DEPTH_LEVELS` / `REPORT_DEPTH_DEFAULT` 迁入 `core/constants.py`（config 默认表与 llm 档位解析共用），`llm/depth_profile.py` 保留原面 re-export
- **持仓渠道判定单源**（rf-907）：新增 `core/holding_status.classify_channel(account)`，报告层两处明细组装改调它（原各自内联账户关键词判定）；`analysis/rebalance_advisor` 只消费 `channel` 字段，不再自行按 `account` 解析（渠道字段缺失即按证券类型判定）。回归 3 例（场外/场内/空值 + 「仅带 account 不生效」）
- **快照形态单一化**（rf-908）：`analysis/prosperity_signals` 提取持仓代码只认 `accounts[].holdings`（与 `schemas/history.SnapshotData` 一致），删除顶层 `holdings`/`details` 兜底；测试 fixture 与用例改为 accounts 形态 + 「顶层摊开不再被采纳」回归
- **LLM 模块 TTL 维持 4h**（plan-227 结案）：实测同日 ≤4h 间隔运行全部命中（15/16）、唯一 4~8h 间隔样本为 `ttl_expired`、跨夜运行任何 TTL 都过期 → 无客观依据支持调值；复核触发条件见 `plan.md`
- **移除单 Provider 配置形态，只保留 provider 链**（rf-901/902）：`llm/api.py` 删除 `_call_llm_legacy()` 与「无 `_provider_list` 即单 Provider 直连」回退（现在显式失败并告警，不再绕开链路由/熔断/端点节流）；`get_llm_config()` 不再把 `llm_key.json` 整份并进顶层配置；`core/system_info` 与 `core/doctor` 的 flat 展示/凭据分支随之删除；`llm_key.json` 顶层四字段（旧单 Provider 形态）不再被接受。单 provider 场景改用「一条 provider 条目」，能力不减（自动获得链路由治理）
- **旧配置自动迁移**：新增 `config._llm_providers.ensure_credential_blocks()`——读取到顶层四字段时自动改写为 `default` 命名凭据块（原文件备份 `llm_key.json.bak`，首尾空格去除）并在 `llm_providers.json` 追加引用它的条目（幂等）；迁移失败不改原文件、日志给明确指引，LLM 章节按未配置占位
- **首次引导与交互配置写链形态**：新增公共入口 `config.write_llm_credentials()`（凭据块 + provider 条目原子写入，凭据分离），`startup_wizard._write_llm_credentials` 改为其薄封装
- **手册同步**：`docs/manuals/how-to-config-llm.md` 快速配置改为两步（凭据块 + 线路条目）、7 个 provider 示例改写为链形态、新增「旧版配置迁移」节并删除 flat/多链「并存兼容」表述


### 技术债归还

- `llm/api_base` 缓存命中路径的模型/端点记录改为复用 `api._resolve_first_provider_model_endpoint`（删自建凭据解析，链解析保持单源）
- `config/_llm_providers` 抽出 `_write_key_document()` / `_attach_credentials_provider()` 两个原语，`ensure_credential_blocks()` 与 `write_llm_credentials()` 共用（消除「写凭据块 + 追加 provider 条目」两份拷贝）
- 陈旧引用清理：`doctor` 迁移提示与 changelog 中的旧块名/旧函数名对齐为 `default` / `ensure_credential_blocks()` / `_write_llm_credentials`；`core/system_info` 与相关用例注释去掉已不存在的「flat 模式」「model_route_labels」表述；手册重号 Step 3 修正为 Step 4
- 规范化回归的弱断言（断言首次快照非空）改为「二次规范化后文件逐字不变」

### 修复

- **重算归因落盘口径拆分**（rf-911）：perf 的 `llm.recompute_reasons` 只放「按原因聚合计数」，逐模块明细改 `llm.module_recompute_reasons`（原实现同名覆盖，聚合计数丢失、判据无法统计）；骨架路径不再对预检已归因的模块二次归因（进程重启后无「上一轮键」记忆时会把 `ttl_expired` 改判成 `cache_miss`，污染 TTL 判据）。回归 3 例（双字段落盘、不二次归因、聚合计数单条）

- **指数历史源上限不再触发无谓重取**（rf-910）：`fetcher/index.py` 的「窗口缩水自愈」判据补源单次上限（约 2000 根）排除——请求 2927 天而上游给 2001 根时属源限制，此前每次运行都会清链路缓存并整段重取一遍（近 24h 6/6 次运行均命中，白打一次大请求且缓存反复失效）；达上限即接受短序列。回归 1 例（上限场景只取一次且不清缓存，钉死场景仍自愈）

- **配置默认值/结构单源续修**：`llm_settings` 渲染路径的 `schema_version` 改必填严格校验（缺失/不为 2 即报错，与加载侧同口径，rf-903）；辩论缓存键前缀改取 `CACHE_PREFIX_LLM` 共享常量（rf-904）；`fetcher/price._price_cache_fresh` 的 `cache_key` 改必填（不再允许跳过收盘时点校验，rf-905）
- **测试离线隔离补全**（rf-906）：9 个 llm 价格/缓存用例文件补 `offline_external_sources`，消除本地「交易日历缓存过期即 62 例连带失败」的假红（CI 与本地口径对齐）

### 审查

- 完成「架构设计约束 / 设计契约 / 内部兼容适配」全面审查：约束表逐条机检未见违背（缓存统一与原子写入、HTTP 客户端统一、章节顺序不硬编码、日志统一、渲染期数据经 context、路径绝对化、LLM 缓存指纹单源、交易日计、重试与节流原语、TUI 分档只改版式——抽查表内各域代表条目；DESIGN.md / DESIGN-TUI.md 机检通过）；内部兼容层沉淀为 rf-901（旧单 Provider 配置簇）、rf-902（旧凭据文件格式）；rf-907（持仓渠道双输入）、rf-908（快照双形态字段）已同批结案

## [0.16.3] - 2026-10-26

### 变更

- **文件膨胀登记清单落表**（rf-914）：`check-file-length -v` 实测 5 个文件越过登记线（测试 >900：`test_release_tool_gate.py` 1147、`conftest.py` 999；主程序 >700：`generators_orchestrator.py` 827、`cli/_handlers.py` 789、`llm/skeleton.py` 739），而 P4 原写「当前无登记项」——按文件逐条登记为 P4 存量监控清单（不占用 rf 编号，拆分后逐行删除）
- **在办设计补任务反引**（rf-915）：`jev-news-judgment-design.md` / `jev-news-judgment-evaluation.md` 头部补「关联任务：`plan-55`」，与 `plan.md` 的正向引用构成双向追溯；`release.py prepare` 的「未引用任何任务编号」提示随之归零

- **持仓明细行装配单源**（rf-909）：新增 `report/_holding_detail_rows.py::build_holding_detail_rows()`——编排路径（`_orchestrator_data.prepare_report_data`，全量含行情三字段）与行动建议路径（`_report_helpers._action_holdings_details`，basic/both 共享的 10 字段子集）过去各写一份字面量，`profit_rate` 百分号换算与 `channel` 渠道判定重复实现，字段增删漏改一处即出现「同一持仓在两处字段不同」；现共有 10 字段集中构造、`with_market_fields=True` 追加 `change_pct`/`nav_date`/`source_api`、尾部统一附加 `holding_days`，`_action_holdings_details` 降为其薄封装。回归 9 例（两路径共有字段逐项一致、键序固定、字段子集不变、百分号与 None、零昨收 `0.0`、渠道单源、`holding_days` 两侧一致）

### 修复
- **基金同类百分位口径不再取反**（rf-918）：上游 `Data_rateInSimilarPersent` 越高越好（恒等于 `100 − rank/total×100`），评级侧按 `(100 − 值)/100` 取补后套阈值——仅百分位可用时不再好坏颠倒，也不再每次运行刷「百分位与排名评级不一致」告警（此前日志累计 16 条）。回归 3 例（实测样本两侧评级一致 / 仅百分位 98.5 → 优秀 / 档位边界）
- **调仓建议清单空态不再与交易纪律表矛盾**（rf-917）：组合级纪律（回撤线/超警戒线）触发时信号不带 `code`、可行化层不产生个股订单，空态文案需区分「真无触发」与「有触发但无订单」——Excel 与 HTML 各自按同一文案分支渲染，回归 2 例
- **峰谷计费等价用例与运行时刻解耦**（rf-916）：`test_llm_pricing.py` 的价格覆盖用例两侧峰谷策略不一致（基线内置双高峰窗 vs 覆盖文件单窗口），且计费时刻取当前时间，特定钟点（如 14:06 CST）会落在两侧不同的峰谷分支上算出 2 倍价差；计费调用统一传 `at_time` 钉死时刻、`_base_ref()` 的 `peak_periods` 对齐内置默认，并补「周末恒闲时 = 基础价之和」非空校验

- **定时生成账本落盘走唯一原子写原语**（rf-913）：`web/scheduler.py::_save_fired` 原自建 `tmp + os.replace` 且临时名固定为 `scheduler_fired.json.tmp`（并发写互相截断、与同目录 `upload.py`/`holdings_update.py` 的做法分叉），改 `core.atomic_write.write_json_atomic`（保留剪除超保留期条目、「失败只记 ERROR 不外抛」）；顺带修 `status_payload` 的 `next_fire_at(...).strftime` 空值访问。回归 2 例（落盘失败只记 ERROR 且不产半文件、3 线程各写 20 轮后账本完整可解析且无残留 `.tmp`）

- **发布 bench 不再随机假红**（rf-912）：`unit/web/test_runs.py` 的 `_wait_done` 原本用 3s 真实墙钟等后台线程，8 路 xdist 满载时线程几十次调度才被唤醒即超时（`test_concurrent_submits_isolated` 已实测假红，同文件 `test_retention_trim_oldest` 同类）；等待预算改为 `_WAIT_TIMEOUT_S = 30.0`——这是「等到就绪」而非时延断言，注释写明满载场景。回归 2 例（假时钟下第 5 次轮询才就绪仍须等到、预算耗尽须报等待时长与末态）
- **发布台账能自证「哪个用例红」**（rf-912）：两处诊断盲区——`_test_runner.runner._run_phased` 的关键词过滤只留小写 `failed`，pytest 短摘要的 `FAILED 路径::用例` 行被丢弃；`release._commands_base._summarize_failure` 的 debug.log 兜底只看 stdout 归档行指向的目录（那是**上一次**运行的报告目录，本次失败档的 debug.log 还在 `test-reports/latest/`）。前者过滤补 `FAILED`，后者新增 `_failure_debug_text()`：归档目录未命中时按 mtime 倒序搜 `test-reports/latest/<模式>/` 的 debug.log，且 stdout 已有 `FAILED` 行则不读（防旧失败被当成本次）。回归 2 例（latest 兜底点名用例、stdout 优先于 latest）；连带修复 `_changed_code_files` 的 `dict | None` 入参与超时分支的 `float(None)`

## [0.16.4] - 2026-10-27

### 变更

- **README/手册配图按当前界面重生成**（自造演示持仓，不涉真实数据）：TUI 主菜单（新状态行：数据源失败 0 / 动作提示）、Web 生成页与配置页、HTML 报告首屏 / 盈亏汇总 / 穿透图表 / CLI 生成输出共 6 张（新增 `cli` 子命令：伪终端采集，含进度、耗时排行与产物路径；CLI 手册新增该图），另重生成 GitHub 社交预览图；文件名保持不变，README 与手册链接无需改动（已逐条校验可达）

- **新增离线评测脚本 `eval-llm-budget.py`**（`plan-229` 阶段 1）：冻结持仓样本 × 4 档预算 × 4 种模式，测量墙钟/输出 tokens/分段字数/要素机检/操作建议行数，输出判定与报告到 `docs/tmp/llm-budget/`；`freeze` 离线建样本、`run --dry-run` 零费用自检；实现拆在 `scripts/_eval_llm_budget/` 包（预算文案/提示词替换/样本/度量/编排/报告/CLI），22 例单测

- **`plan-229` LLM 关键路径时延治理（表达预算）：评估后不采纳并归档**（未改生产代码）：离线评测 12 只持仓样本，4000 字档 p50 64.5s→45.0s（−30%）、输出 tokens −41%，但正文篇幅减半且纯提示词约束下 **8/8 次丢失「操作建议」表**（补写接缝可 9/9 补齐，+2~6.5s）；同期评估的 TTL 提升（理论 51%→63%、实际命中恒为 8%）与指纹瘦身（可至 36%，但最多陈旧 3.7h 且违反指纹契约）均不采纳。设计与量化数据归档至 `docs/archive/v0.16.x/llm-expression-budget/`；评测器 `scripts/eval-llm-budget.py` 保留为度量资产。立项时记录（背景）：：`expert_review` 40 个生成样本均值 65.3s / p50 64.5s / p90 85.5s，恒为报告关键路径，而时延与输出 token 数线性相关（156~163 tok/s）、提示词全篇无篇幅上界（对照 `global_macro` 有「500字内」）。设计文档 [`llm-critical-path-design.md`](../archive/v0.16.x/llm-expression-budget/llm-critical-path-design.md) 给出归因模型、四方案取舍（选定「分节表达预算」，拒绝并行拆分与模块合并，thinking 默认不动）、四阶段实施计划、质量守门与回滚口径；**本文档阶段不实施**

- **用户文档与配图同步状态行新形态**（rf-922）：`how-to-use-tui-menu.md` 新增「页头状态行读法」（四项常驻 + `缓存过期 N` 仅 >0 出现 + 第二行动作提示；`数据源失败` 明确标注「与 LLM 多链无关」），并纠正「菜单分组」段落的组成员（原写 `P/S/M/I/A/D/R`、`V/H/T` 等已不存在的归属，改为与 `MENU_GROUPS` 一致）；`README.md` 界面描述、`folders.md` 目录树描述、`developer-guide.md` 菜单触点行（「页脚指引」→ `ACTION_TEMPLATES` 动作短语）、`test-coverage.md` TUI 域用例清单同步；`requirements.md` 补 `R-TUI-10`（页头状态行此前无需求行，只有零散提及）+ `testplan.md` 追溯行；README/手册配图 `src/static/tui-menu.png` 按当前界面重生成

- **页头不再常驻「缓存过期 0」**：启动已自动清理过期缓存，常态的 0 反而引人追问「是不是没清理」——该段改为**仅 N>0 时上屏**（取数失败同样静默，改由 `[3]` 缓存管理查看），出现即意味着本轮运行期间确实积了过期文件
- **页头状态行：静态「详情」括注 → 异常态动作提示**：`〔详情 [3][D][S]〕` 是 5 个指标配 3 个键的目录式指路（用户需自行猜「哪个键对应哪一项」），且它自己承认最不重要（窄终端第一时间丢弃）；改为状态驱动——异常段自带一句带键的动作短语（`[3] 清理过期缓存` / `[2] 更新行情缓存` / `[D]→V 看数据源记录` / `[G]→L 配置 LLM`），汇总为第二行 `└ …` 缩进提示并按列宽折行；全部正常时行尾干净、无第二行。短语单源 `status_line.ACTION_TEMPLATES`，首键受主菜单子集守护（`TestActionHintKeys`），DESIGN-TUI 页头状态行契约同步重写；「备用源」段改名「数据源失败」（它数的是取数源失败个数，紧挨 `LLM ●` 时被误读成 LLM 备用线路数）

### 修复

- **截图脚本的演示报告会污染真实运行状态**（rf-926）：`make-screenshots.py report` 跑真实生成流程，会向 `data/state/perf_history.jsonl`、`datasource_health.jsonl` 与 `data/calibration/dedup_anchors.jsonl` 追加演示数据，与「真实 data/ 零接触」承诺不符（实测污染了 1 条 perf 记录与 1 条健康记录，已清理）。改为跑前快照、跑后原样还原两个目录（含删除运行期新增文件），并补 2 例回归

- **主源正文的确定性空结果不再每轮重复请求**（rf-925）：实测 5 只 A 股在 DataSinking 侧均无「管理层讨论与分析」章节，每份报告逐只重走链路约 10s，而结论是确定性的。改为按 `(doc_id, 章节)` 记 **1 天负缓存** `report_datasink_doc_miss_`（判定依据：各槽原因均为确定性拒绝——「该文档无」或「异源候选拒服务」；任一槽为传输级失败则不写），登记进「财报索引」缓存类型随 TTL 清理；命中次数按轮计数，报告级打**一行 INFO 汇总**（「正文空结果命中负缓存 N 次」），无需 DEBUG 即可确认生效。回归 5 例（命中 / 传输失败不缓存 / 章节隔离 / 计数与重置 / 汇总日志）

- **cninfo orgId 反查挂 40.2s 拖慢报告**（rf-924）：该路径原用 20s 预算，而 httpx 的 timeout 按阶段计、read 又度量「相邻两次收数据间隔」，实测单请求挂到 **40.2s** 才判主机不可达——orgId 只是财报备源的元数据前置，卡在报告主路径上。改为**端到端墙钟 8s**（`post_with_deadline` 支持表单编码后复用）+ 失败入 **1h 负缓存** `report_cninfo_orgid_miss_`（区分「连接失败」与「源侧无该代码档案」；此前失败不留痕，同一网络条件下每次重跑都重付一遍）。实测影响：该轮报告 167.7s → 预计回到 ~130s 量级。回归 3 例（墙钟生效 / 负缓存命中不再发请求 / 两种失败原因分开记）

- **截图配图的配色段前留大段空白**（rf-923）：`scripts/_screenshots/tui_frame.py` 逐段绘制时用「字号 × 0.62」估算步进，而等宽 CJK 字体里拉丁与全角的实际步进与估算不一致，偏差随段落长度累积（页头状态行长行最明显）；改为 `ImageDraw.textlength` 按字体实测推进、画布宽同口径取实测宽度。回归 1 例断言彩色末段起点与实测偏移 ≤4px

- **页头状态行「详情」指引对齐主菜单**（rf-919）：指引键写死为 `[4][H][S]`，而缓存管理已收为 `[3]`、持仓信息目录下沉为 `[G]` 子项，`[4]` 与顶层 `[H]` 均已不存在；改由 `DETAIL_HINT_KEYS = ("3", "D", "S")` 单源派生，并加「指引键 ⊆ 主菜单」守护（菜单改键即红），DESIGN-TUI 页头状态行契约同步写明出处
- **页头「新鲜度」自首版起恒为「—」**（rf-920）：两处叠加——① 从缓存文件名反推键时未剥 `_{版本}` 戳，`get()` 拼出 `{key}_v4_v4.json` 必然未命中；② `cache.get` 的 `max_age_seconds` 未传，TypeError 被兜底 `except` 吞掉只剩「—」。反推口径收为 `cache.cache_key_from_file_name` 单源（清理侧同步改用它），读档改传 `inf`（要报的就是「数据偏旧」）；回归 1 例不 patch `get` 走真实读档
- **缓存包启动清理在异常路径抛 NameError**（rf-921）：`del _logger, _cleaned` 在 `try` 外，`clean_sensitive` 抛异常时 `_cleaned` 未绑定即删，导入期崩；另一处 `os.listdir` 无容错，目录不可读同样中断。改为初值 0 + `_cache_file_names()` 容错列举（清理是尽力而为，不得影响主流程）
