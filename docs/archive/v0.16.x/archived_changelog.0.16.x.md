# 变更日志归档 — v0.16.x

> 归档时间：2026-10-30（v0.16.12 发布并入；已并入 13 段：v0.16.0（10-25）、v0.16.1（10-25）、v0.16.2（10-26）、v0.16.3（10-26）、v0.16.4（10-27）、v0.16.5（10-27）、v0.16.6（10-28）、v0.16.7（10-28）、v0.16.8（10-29）、v0.16.9（10-29）、v0.16.10（10-29）、v0.16.11（10-30）、v0.16.12（10-30））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.16.0 ~ v0.16.12（2026-10-25 ~ 2026-10-30）
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

## [0.16.5] - 2026-10-27

### 修复

- **模块日志器名称统一**（日志统一约束：模块日志器名称）：`report/holding_change_panel.py`、`tui/status_line.py` 用 `getLogger(__name__)` 自取名称，日志落到另一棵 logger 树——`invest` 的 handler / 级别 / 格式与落盘全部不生效，这两个模块的诊断信息**静默丢失**（不进 `logs/app.log`）；改为 `getLogger("invest")`
- **LLM 缓存键写侧回归单源**（LLM 缓存键单源约束）：`llm/skeleton.py` 落盘路径自拼 `f"{cache_key}_{provider_name}"`，绕过唯一构造点 `_build_provider_cache_key`——写侧与预检侧任一侧改后缀格式即永久不等，表现为「开关/参数看似生效但每次仍全量调用 LLM」（费用与耗时翻倍、无异常难察觉）；改为调用共享构建函数
- **预检取数空链时的未绑定变量**：`llm/skeleton._resolve_first_provider` 在 provider 链为空时 `first_model` / `first_endpoint` 从未赋值，`return` 处抛 `UnboundLocalError` 只能由外层 `except Exception` 兑成「无预检」——真实异常与空链无法区分且 debug 日志被常态污染；三个返回值改为显式初值
- **TUI 首次使用指引指向错误入口**：持仓缺失提示原写「通过菜单 `[D]` 配置持仓目录/文件名」（`[D]` 是诊断与排查，无此入口），LLM 未配置提示原写「菜单 `[S]` 查看状态」（`[S]` 是章节内容呈现）——均改为实际路径 `[G]`（`[H]`/`[F]`）与 `[G] → [L]`，并补页头 `LLM ○` 状态说明
- **用户手册菜单路径与实现对齐**：`faq.md` 三处把 LLM 调优入口写成「主菜单 `[D]` → `[L]`」（实为 `[G]` → `[L]`，`[D]`→`[L]` 是日志设置）、把 `[T]` 系统自检说成「恒出现在主菜单中」（实为 `[D]` 的二级项）；`requirements.md` 的 R-DIAG-05 同步改写为「`[D]` 二级恒提供」；手册术语按上屏口径统一（「强刷」→「重新生成」、`Enter`→「回车」）
- **LLM 多链面板横幅缺结构色**：`handlers_llm_providers.py` 单线路分支的横幅裸 `truncate_display("── … ──")`，与同文件多线路分支不一致（一处有色一处无色），违反「结构色统一经 `style_heading` 产出」

- **基金经理抓取时间预算收紧（plan-230）**：主页请求 15s→6s、档案页回退 8s→4s，且主页**网络级超时后不再赌档案页**（同站群多半同样不通，实测两段超时串联把单个代码拖到 27.3s、占数据准备阶段 40%，最终仍解析失败）——单代码最坏耗时收敛到 ≤10s，缺数据按占位降级；`_request_fund_html` 保留原签名（tiantian 侧仍在用），新增 `_request_fund_html_status` 返回超时标记
- **历史数据重叠判据改为「数值变化」而非「日期重叠」（plan-231）**：增量参数是「从某日起最近 N 条」，N 大于缓存覆盖时必然整段重叠——旧口径把正常衔接当除权修正，一次运行触发两次全量重拉（个股 400 天 + 沪深300 2928 天）。改为：重叠日期上价格变化超 0.01% 才算修正，数值一致则按日合并（同日覆盖已能吸收窗口内修正）；末位舍入差（1e-6 级）不误报

### 变更

- **日志器名称纳入机检**：`check-code-traces.py` 日志统一支路新增 AST 判定「绑定到 `logger` / `_logger` 且名称非 `invest`」（第三方日志器静音与 `core/logger.py` 的构造链豁免），此前该守卫只查 `print()`，日志器名称长期无人守
- **测试标记合规检查收口两处空洞**：① 目录期望原为「至少命中其一」且期望集含通用 `unit`——任何只标 `unit` 的文件都能通过，域绑定形同虚设；改为「通用标记不计域归属，域标记必须命中其一」。② 标记提取只认 `pytestmark = [...]` 列表写法，`pytestmark = pytest.mark.x` 单值与元组写法被漏读；抽出 `_markers_from_value` 统一三种形态
- **手册菜单引用机检扩两条规则**（`check-doc-drift` 第 18 项域）：① **主菜单归属**——分句内把二级项说成在主菜单里即报（已声明「二级 / 不在 / 箭头路径」的分句豁免），上线即检出 `requirements.md` 的一处残留错误陈述；② **箭头路径合法性**——`[X] → [Y]` 要求 `X` 为 `[G]`/`[D]` 且 `Y` 属其二级项，杜绝把无二级项的键写成路径
- **`unit/handlers` 目录期望表修正**：原声明 `{unit, unit_core}` 与实况不符（TUI 处理层实际标 `unit_ui`），改为 `{unit, unit_core, unit_ui}`；`unit/web/test_cost_preflight_contract.py` 补 `unit_web`（原只标 `unit_llm`，`-m unit_web` 选不到它）

### 文档

- **统计口径与数字去写死**（`folders.md`）：文档总数分项由 `managements 12 / manuals 10 / plan 8 / archive 160` 校正为实测 `13 / 12 / 3 / 183`（合计 216 与统计表对齐），并删去写死的 pytest 收集项数（改指向 `test-coverage.md`「模式对应测试量」的 `all` 行）与 `README.md（211 行）`、`CLAUDE.md（89 行）`、`157 md 50,492 行` 等与受检列重复的过期数字
- **失效路径与错误陈述**（`CLAUDE.md` / `developer-guide.md` / `technical.md` / `docs/plan/`）：`scripts/_checklib.py` → `scripts/_shared/checklib.py`（3 处）；`technical.md` 更正「`_shared/traces_common.py` 已并入删除」（该文件仍在，由两个痕迹脚本共同 import）；集成契约「42 例 / 5.5s」改为「50+ 例 / ~5s」
- **`src/static/README.md` 结构归一**：单文件两个 H1 合并为一（后半降为 `##` 分组），清理 9 处任务代号（改为语义表述），`chart-init.js`「6 张图表初始化」校正为实测 12 张
- **菜单描述与实现对齐**（`README.md` / `how-to-use-tui-menu.md`）：`[Q]` 受功能开关控制、`[T]` 系统自检恒上屏（原 README 两处称 `[Q]`/`[T]` 均由开关控制且「在 `[S]` 里开启」）；`[D]` 二级项补 `L 日志设置`（原文漏写）；`/` 筛选示例由不存在的 `T` 改为 `Q` 并注明二级项不在筛选域；手册内「`[Q]` 与 `[T]` 同机制裁剪」与「`[T]` 恒上屏」的自相矛盾改正
- **手册新增「界面词与技术词对照」并试点术语本地化**：总索引新增 10 行对照表（降级→备用/失败标记、熔断→健康面板「失败 N」、退避→「等久一点才出结果」、强刷→`--force-llm` 强制重新生成、游标→行首 `>` 选中项、配置漂移→行尾 `*` 等），说明手册保留技术词但界面按右列说法；`datasource-reliability.md` §1 的失败路径流程追加「在界面上是什么样」五步对照（切换备用/熔断/退避/过期缓存/占位），把运维视角落回用户可见信号
- **TUI 手册补三端对照表**：新增「同一个操作在三端的位置」10 行表（生成报告 / 调仓模拟 / 章节显隐 / 章内开关 / 全局设置 / 缓存管理 / 系统自检 / 健康历史 / 运行日志 / 报告追问），与 Web 手册既有的「TUI 入口对照」形成双向；同时点明报告追问无 CLI 子命令
- **代码注释中的过期菜单引用**：`handlers_cache.py`「菜单 `[1][2][3][4]`」→ 实际 `[1]/[2]/[3]`；`status_line.py`「LLM 状态与 `[S]` 同源」→ `[G] → [L]`

- **超长配置手册拆篇**：`how-to-config.md` 979 → **426 行主篇**（目录 / 出厂 `config.json` 样例 / 字段总表 / D 市场时段与缓存 / N 功能开关 / 随版本更新）+ **`how-to-config-reference.md` 596 行参考**（A/B/C/E…S 逐节逐键，顺带改正 R 与 S 的错序）；`how-to-config-llm.md` 1138 → **746 行主篇** + **`how-to-config-llm-reference.md` 414 行参考**（逐家 provider 配置示例、完整模型定价表）。主篇保留「照抄改值」入口，详解篇承担「这项到底管什么」
- **命名对齐**：`how-to-config-fields.md` 改名为 **`how-to-config-reference.md`**（标题「配置参考：逐项详解」）——与 `how-to-config-llm-reference.md` 同后缀成对，读者一眼看出「主篇 how-to-config*.md ↔ 参考附录 *-reference.md」的关系；常量同步为 `_HOW_TO_CONFIG_REF_MD`，7 处引用与目录树一并改指
- **拆篇后机检不断档**：`check-doc-drift` 配置默认值支路改为**双文件扫描**（B/C/E/G/M 节的默认值行随内容迁入详解篇，仍逐行对账，未静默丢 34 行覆盖）；目录树补两文件、总索引补两条；`faq`/`developer-guide`/TUI 手册中 4 处指向已迁移锚点的引用改指新文件
- **新增「错误信息索引」附录**（`faq.md`）：三渠道共用的 7 类提示（取自 `core/error_hints.py` 单一映射）、Web 的 15 个 `error_code`（含 HTTP 状态与处置）、CLI 四个退出码，整理成「按消息原文反查」表——此前只能按「我想……」进入，拿到报错无从下手。内容按代码调用点（`_err(...)`、退出码分支）逐条核对而非手写
- **界面用词对照表去重合并**：总索引原有两节（「界面用词对照」5 行、「界面词与技术词对照」10 行）语义重叠，合并为「界面用词与技术词对照」两层——界面上的词（含义/代价）+ 手册日志里的技术词（→ 界面说法），锚点与引用同步

- **全仓索引与链接核对**：逐篇比对「目录 ↔ 实际标题」与「场景表直达章节 ↔ 目标节名」，修四处：`faq` 目录补错误信息索引的 3 个子节、`how-to-use-tui-menu` 目录补「页头状态行读法」、`technical` 目录补「9. 导入面所有权」、总索引场景表把「§五区工作台」改为实际节名「§2 首页布局（五区标签页工作台）」。核对结论：14 份手册全部被总索引收录、均有页脚回链、无孤儿文档；changelog/plan/review-findings 三份归档索引各覆盖 16 个归档文件无缺漏；跨文件死链/死锚点 0

### 测试

- 新增回归 13 例：日志器名称 8 例（检出 / 豁免 / 全仓基线自洽）、缓存键单源 3 例（写侧与预检侧同源结构断言 / 键一致 / 空链不走异常分支）、测试标记 4 例（单值与元组 `pytestmark` 提取 / 通用标记不足以满足域期望 / 真实测试树全域绑定）与 TUI 指引 2 例（持仓必须指向 `[G]`+`[H]`/`[F]`、LLM 必须指向 `[G]`+`[L]`，且不得出现旧键）

## [0.16.6] - 2026-10-28

### 修复

- **发布期类型/容错清理（发布当天自查）**：`tui/handlers_switch` 的分组块元素类型由 `object` 收窄为 `FeatureSwitchDef`（面板渲染参数的静态类型不再是 object）；`tui/handlers_config` 的对比指数池归一为 dict（非 dict 形态按空表，与 Web 面板同口径）、限速器刷新改用公开入口 `clear_rate_limiter_cache()`（原调用依赖挂在函数对象上的 `cache_clear` 属性，静态不可见）；`fetcher/batch` 补该公开入口并保留旧属性兼容；截图链路 `cdp_shot.mjs` 对非 JSON 事件容错（不再因一条干扰消息中断整个 CDP 客户端）、`tui_frame` 的 finally 还原分支改为前置初始化（Pyright 报告的「可能未绑定变量」）

- **复用 gate 戳时的提示文案拼接**：`release.py publish` 在 gate 通过戳缺「用例数」字段时打印出「…，项数见 gate 输出 项」（多一个悬空「项」）——改为缺值时整段省略，不再拼出残句

### 变更

- **`[S]` 面板措辞与归类清理**：① `module_quality_gate` 标签「模块级质量分级」→「**LLM 输出评级**」（与 `data_quality` 的「质量」解歧，后者描述补「数据侧质量，与 LLM 输出评级无关」）；② `event_window_impact`「事件窗量化对照」→「**事件窗对照**」、`summary_highlights`「本期要点与环比对照」→「**首页执行摘要卡**」——标签同步注册表/区块注册表/HTML 模板/Excel/手册，报告区块标题随之一致（区块名不带括号：`normalize_block_title` 会剥离括号注解）；③ 描述白话化：`valuation_percentile` 改「有历史 PE/PB 就用真分位，没有就用价格分位近似」、`report_qa` 补「按量计费」、`prosperity_framework` 明说评估对象是「持仓组合」
- **`data_quality` 内置为恒开**：数据质量仪表盘不再有开关（数据本就在收集，关掉只是「看不见可信度」）；渲染管道参数保留并标注技术债（清理项见 `plan.md`）
- **`report_qa` 归入「机制与质量」**：它是唯一新增 LLM 费用与用量记账的项，放在「呈现与交互」会误导；随之**删除空的「呈现与交互」组**（`[S]` 六组 → **五组**、20 → **18 项**），编号 12-18 重排，CLI/Web/报告三渠道随注册表自动收敛
- **报告追问埋点（转正判据数据底座）**：`qa/telemetry.py` 每次提问记一行到 `data/state/qa_usage.jsonl`（渠道/成败/错误码/轮数/tokens/费用/耗时/事实核对降级，**只记问题字数不记正文**，滚动 5000 行）；`summarize_qa_usage` 汇总提问量/无回答占比/失败码/渠道/平均轮数/费用，并按三条判据（提问量 ≥ 30、无回答 ≤ 15%、降级率 ≤ 30%）给出「可评估转正 / 维持实验」；`doctor` 新增「报告追问效果」卡片，`ask_report_qa` 单点接线（Web/TUI 传渠道，返回体不暴露内部字段），埋点异常一律吞掉
- **归还「恒真参数」技术债（plan-232）**：`data_quality` 内置后遗留的 `enable_data_quality` 布尔参数从 4 层链路（`_generation_full` / `_generation_both` / `orchestrator` → `_report_output` → `excel_generator` / `html_writer`）彻底删除，模板 `data_quality_enabled` 恒真条件一并移除（`{% if %}` 包裹的两个区块改为无条件渲染）；不可达的旧样式写入器 `_write_data_source_matrix_sheet` 与其 2 个用例、`get_report_sheet_name` 孤儿导入同步清掉——全仓 `grep enable_data_quality|data_quality_enabled` 归零
- **两处类型标注纠偏（顺带）**：`report/_llm_news._fetch_llm_and_news` 返回标注由四元组补成五元组（实际一直返回五元组、调用侧解包五值）；`force_llm_modules` / `force_modules` 参数由 `set|frozenset` 放宽为 `Collection`（调用侧传 list），线程池 future 列表补 `Future` 标注

- **`metrics_enabled` 内置为恒开（去掉显示开关）**：报告量化指标始终全量计算与渲染，`[S]` 面板 20 → **19 项**（呈现与交互组剩 `report_qa`）。原开关是纯展示项却并联了跨层副作用——关闭会让**指标级断路器暂停失败计数**并自动解熔，即「改报告观感」影响「熔断统计」，属设计债；本次一并删除 `analysis/circuit_breaker_wrapper` 的 Feature Flag 联动分支（`_check_feature_flag` / `_log_ff_event` / `_ff_was_off` 残留计数），`chart_data_builder` 去掉 `metrics_enabled` 参数与「全轴 N/A」分支；三渠道随注册表自动收敛（CLI 已拒绝旧键、Web 面板不再出该行）

## [0.16.7] - 2026-10-28

### 修复

- **移除兼容层（rf-937）**：旧数据结构/旧数据文件/旧缓存载荷/旧配置键/旧配置文件/旧内部 API 一律不再保留支持，破坏性变更统一走「换键换字段 + 版本戳整体作废」。本次清掉四处存量兼容分支：① `llm_key.json` 顶层 `api_key` 扁平旧形态不再自动改写（去掉了 `default` 块迁移与 `.bak` 备份），改为拒绝加载并给出改写指引；② 配置校验中 `market_hour_aware` 的退役告警分支删除（该键已无任何消费方，静默忽略）；③ 穿透标的来源只认契约真值键 `sources`，不再回退合并层内部键 `funds`；④ TUI `handlers_config` 的 `filter_menu_llm_modules` 兼容再导出删除，调用点直连 `tui_menu`。兼容层纪律（含「兼容」与「健壮性」的判据）写入 developer-guide「兼容层纪律」。

- **行业资金流向「陈旧回退」带新鲜度标注（rf-936）**：源不可达时回退上次成功载荷后，报告与 LLM 提示词把它当今日数据用——模型会把 1~3 天前的资金流向当当下评。`mark_data_used` 新增 `freshness` 通道（进事件 `detail`、**不进降级计数**，避免把自己算成一次失败），数据质量块新增「陈旧回退（源不可达，用上次成功数据）: <源>」行，取数侧同时如实告警。回归 7 例（事件 detail / 无标注时不添行 / 不污染失败计数 / 与失败降级共存）。
- **输出目录锁的 pid 探活在 Windows 上会杀进程（rf-935）**：`os.kill(pid, 0)` 在 Windows 对非控制台信号直接走 `TerminateProcess`，探测锁持有者等于把它杀掉。改 `OpenProcess` 查询句柄，无法判定时退化为文件年龄判据；回归 4 例。

- **行业资金流向不再每份报告重复撞超时（rf-928）**：失败负缓存原先只在进程内存，而每份报告是独立进程——实测 30 次真实运行 38 次 akshare 异常，且失败后该块数据整块消失。改为负缓存落盘（30 分钟、跨进程生效）+ 失败回退最近一次成功载荷（≤3 天，失败原因标 `stale`、提示「使用上次成功数据（源不可达）」），超过 3 天仍留空，绝不复用旧数据。回归 4 例（磁盘负缓存短路取数 / 失败落盘 / 陈旧回退 / 成功清负缓存并刷新基准）。
- **场内基金（LOF/ETF）行情不再永久缺价（rf-929）**：`截取名称判据` 以汉字集合重叠 0.7 为阈值，把源侧简称「白酒基金LOF」与持仓全称「招商中证白酒」判成两只不同标的（重叠仅 0.5）→ 有效报价被拒；同时场内基金不在 00 重叠区降级名单，股票链路失败后无任何兜底。改为：名称判据增加「连续 2 汉字公共段」一档（代码已由路由确定身份，名称只作二次防错），并让场内基金在股票链路失败后同样降级净值链路。不同标的（「宇晶股份」vs「广发多因子」）仍被拒。回归 3 例。
- **演示/基准运行与真实运行彻底隔离（rf-930、rf-931）**：原先两者共享 `logs/app.log` 与 `data/cache`，演示持仓的告警（名称对不上/缺凭据/陈旧锁）混进真实日志、按「读了哪个持仓文件」事后反推才能区分。新增三通道：`INVEST_LOG_PATH`（改落盘文件）、`INVEST_RUN_CONTEXT`（启动一行上下文标记，落哪都能归属）、`INVEST_CACHE_DIR`（缓存改落）；`scripts/make-screenshots.py` 自动注入。演示工作区的凭据块与 `providers` 引用也改为 `build()` 同源写入（旧实现凭据块叫 `default`、providers 却引用 `deepseek-main`/`opencode-go`，每次演示 run 刷 2 行告警）。回归 11 例。
- **残留输出目录锁不再被当成持续占用（rf-932）**：原先只判「锁文件存在」，`kill -9`/容器重启后的残留锁让每次启动都刷一条「可能正被其他入口占用」告警，既误报又让人对真实抢占告警脱敏。锁现在带陈旧判据（pid 已不存在 / 无 pid 且超 12 小时未更新）并支持接管；活进程持有的锁仍正常拦截。回归 5 例。
- **LLM 缓存冷启动不再误归因为 `ttl_expired`（rf-933）**：新进程首轮四模块全 miss 时，日志记 `ttl_expired=4`——据此判定「放宽 TTL 能省钱」是错的（实际无上轮缓存可命中）。归因补 `cache_miss` 三态：无上轮指纹快照时记冷启动。回归 1 例。
- **`llm_settings.json` 读取失败带出原因（rf-934）**：原先静默返回 None，面板只报「读取失败，按默认展示」，现场无法区分文件被占/半写/JSONC 解析失败/编码问题。现日志带异常类型、消息与文件路径。回归 1 例。

- **持仓变动复盘误报「新增/清仓」（rf-927）**：截图/演示报告运行曾把 23 只演示持仓的快照写进真实 `data/history/snapshots/`（快照目录是 `PROJECT_ROOT` 常量、不随配置走，截图护栏又漏了 `data/history`），真实报告逐对差分后把整批演示标的报成「新增」、并把本人持仓报成「清仓」。三重修复：① 事件抽取新增**基线切换守卫**——相邻两期持仓代码 Jaccard 重合度 < 0.5 即跳过该区间推断并在表尾标注（单侧为空不触发，保留「全清→回补」账户重排的既有识别）；② 截图工具护栏补 `data/history`；③ 已产生的 7 个污染快照移出快照目录隔离并删除。回归 6 例（不相交/正常变动/仅跳过切换对/双侧为空/视图透传/无说明常态）

## [0.16.8] - 2026-10-29

### 修复
- **行业资金流向换通道**（plan-234 / rf-955）：主通道东财 `push2` 在本机出口被配额型限流（TLS 层 `RemoteDisconnected`，实测连续 20 次 0 成功、仅罕见短窗口放行），新增**同花顺行业资金流备用通道**（金额亿元→元、净占比由净额/成交额派生），两通道共用同一结构契约与 `sector_flow_failure()` 语义；负缓存改**按通道分别落盘**（主通道限流不得锚死备用）；新增只读探针 `scripts/probe.py sector-flow`（逐通道成功率与判读）。
- **「无回退基准」与「陈旧回退」分开披露**（plan-235）：取数层新增降级三态（正常 / `stale` / `no_baseline`），源不可达且本机无历史载荷时，报告文案与 LLM 数据质量块单独成行标注「无回退基准、区块留空」，不再与「陈旧回退（用上次成功数据）」共用同一句话。
- **缓存清理器吞掉同前缀异构 TTL 键**（plan-237 / rf-955）：清理器按文件名前缀取 TTL，`sector_flow_last_good`（设计 3 天）与 `sector_flow_negative`（设计 30 分钟）被 900s 前缀默认值一并裁掉——3 天陈旧回退基准实际从存活不下来，回退链路形同虚设。注册表新增 `exact_key_ttls` 单源声明 + `get_exact_ttl_map()`，清理器按精确键覆盖；取数侧 TTL 从同一处读，不再两处各写一份。
- **`scripts/probe.py` 子探针 import 失败静默**（rf-956）：入口只把 `scripts/` 加进 `sys.path`，子探针的 `from src.python…` 在直接运行入口时全部 ImportError 并被当作探测失败——`csi` 因此长期输出「无可用代码」。入口补仓库根路径，子探针契约面加 Protocol 类型。
- **去重锚点体积治理三项**（rf-938 / rf-939 / rf-940）：
  - **同源样本 1/50 确定性采样**：`same_src` 样本按标题对 SHA-256 哈希采样（同一对恒定入选），存量 94,706 → 37,913 条（40%），校准样本量仍远超「≥50 条」建议值。
  - **保留期 120 → 30 天**，且保留判定改为 `ts`（发布时间）**或** `written_at`（写入时刻）任一在窗口内即保留——补录/回溯抓到的老新闻 `ts` 很老但刚写入，不再在首次压缩就被裁掉。
  - **体积目标 24 MB**（与 32 MB 告警线分离）：超目标按最旧裁剪到 ≤24 MB，每分支保留最新 50 条（小分支不被整类裁光）；读取前后比对 `(size, mtime)`，期间被并发追加则放弃本次压缩；无行可裁时不重写文件。
- **锚点规则时代口径**（rf-941）：压缩时给无规则指纹的早期行补 `legacy` 标注，校准报告分「当前指纹 / 历史指纹 / 未标注」三桶并列出历史指纹 Top3。
- **文档同步**（rf-942）：developer-guide / technical / requirements R-DATA-09 / scripts-reference / testplan 按三重压缩条件重写，自检提示指向评估脚本并说明会裁到体积目标内。
- **新闻去重锚点按层拆分**（rf-948）：`providers/news_dedup.py` 795 行三簇混装收口——字节动作（分片命名/路径/汇总体积/容错读取/追加/校验后原子替换）下沉 `news_dedup_anchor_store.py`，保留期·体积目标·同源采样·裁剪编排下沉 `news_dedup_anchor_policy.py`，`news_dedup.py` 保留判定主流程并原面 re-export（`compact_anchor_file` 仍是唯一裁剪实现，生产维护与 `eval-dedup-threshold.py` 共用）。
- **负缓存探针收口为单一样板**（rf-949）：新增 `cache/_negative.py::NegativeCache`——四类确定性缺失（标的正文 / 章节清单 / 该文档无该章节 / provider 404 探测）只声明「标签 + 键前缀 + TTL 类型」，锁/命中计数/汇总文案（`nonzero_summaries()`）统一承接；新增一类负缓存不再复制 lock+counter+reset 样板。
- **事实校验自动修正回写缓存**（rf-946）：修正后正文写回该模块缓存（键沿用预检/写侧同源的 `cache_info[mk]["key"]`，不改指纹、不新开键），缓存正文与展示正文口径对齐——此前同一缓存内容每轮都要重做同一批修正（`counters.fact_fix:*` 恒为同一数），且报告展示值与缓存值不一致。校验摘要属当轮元信息，仍在回写之后拼接、不入缓存。
- **章节清单不可得负缓存**（rf-947）：源侧 200 但无可用章节清单时，`/documents/{id}/sections` 每份报告都重探一次（实测 5 篇 × 0.3~1.4s ≈ 5s，全缓存运行的绝对瓶颈）；现按确定性结论记负缓存（`report_sections_miss_`，6h，传输级失败仍不缓存）：覆盖空清单与「非空但不可用」（源侧只解析出封面/目录几项、按清单取正文全空）两种形态，后者先失效清单再重记负缓存；清单失效时正负两键同清。计时同时拆为「财报摘要」「财务指标」两段，`breakdown` 可直接区分逐篇网络探测与单次取数；批量取数评估为不可行（两源均按单标的请求）。
- **生成后自检缓存键去噪**（rf-945）：自检输入剔除 LLM 用量页脚与事实校验摘要段落（后者检查项计数随缓存态变化），报告渲染保持完整正文不变；补未命中时的分段诊断日志。实测强制重算上游模块后，下一次运行自检即命中（此前该场景必多一次 10~15s 调用）。

- **去重锚点按月 gzip 分片**（rf-943）：写入改为 `data/calibration/dedup_anchors-YYYYMM.jsonl.gz`（multi-member gzip 追加，不重写既有压缩块），读取侧 `gzip.open` 透明解压、坏分片只跳过其余内容；压缩按记录月份重新分片并清理整月被裁空的分片，旧版未压缩单文件首次压缩时自动并入并删除。实测存量迁移：34.0 MB / 94,706 行 → 2.7 MB / 62,716 行（2 个分片，0 行解析失败）。

### 性能
- **概述↔正文编号双向校验 + `plan-70` 归位**（rf-958）：`plan.md` 概述引用的 `plan-N` 若在正文与计划归档中都不存在，`check-doc-drift` 现在直接报 finding（认无状态标记的在办小节）；同时把此前被误删的 `plan-70`（decision_reflection 转正判据）恢复到 P3。
- **基金经理取数握手超时不再翻倍等待**（rf-953）：SSL 握手超时以 `ConnectError` 抛出，原先只把 `TimeoutException` 当「站点不可达」，于是同一只基金又走一次档案页回退、连等两次 ~6.9s（HTML 阶段因此从 0.3s 变成 17s+）。现把连接阶段单独封顶（`httpx.Timeout(6.0, connect=3.0)` / 档案页 `(4.0, connect=3.0)`），`ConnectError` 与超时同归「站点不可达」并跳过回退。
- **换键归因的 reset 补清进程内基线**（rf-957）：`reset_baseline_cache()` 只清跨进程快照，进程内上轮键残留会让冷启动被误判成「键变了」；改为一次清两处（快照 + `skeleton._PREV_MODULE_CACHE_KEY`），修掉「单跑绿、整目录红」的用例顺序依赖。
- **新浪分类抓取加超时与整源预算**（plan-236）：单请求由 15s 整段超时改为连接 3s / 读取 6s 分档，整源加 20s 预算并按剩余收紧每请求超时；超预算保留已取条目后收尾，单类挂起不再把新闻阶段从 5s 拖到 15s+。
- **历史 K 线挂起不再放大等待**（rf-951）：腾讯 K 线单次超时预算 60s→10s、同源重试 3→2 次且**挂起型不重试**（单次 ≥ 预算一半即判主机不可达）；链级新增 `_HANG_ELAPSED_SECONDS=20s` 判据，挂起不再触发同源重试。实测主机不可达时单标的从 ≈2 分钟（60s+36s+31s）收敛到 10s 内，十余持仓的报告不再被卡二十分钟。
- **章节清单探测加短退避**（rf-952）：`/sections` 传输级失败（挂起/断连）此前不留任何状态，每份报告都为同一篇文档再白等一次超时预算（实测单篇 20.7s）；现记 30min 短退避（`report_sections_backoff`，注册表类型同源），探测成功即清。与「确定性缺失 6h 负缓存」语义分离：一个说源侧没有清单，一个只说这次探测挂起。
- **持仓变动复盘归因并入并行批**（rf-944 ②）：该模块只吃持仓变动契约、不依赖四模块产出，原先串行后置把单次 4–25s 完整叠加在 `expert_review` 之后的关键路径上；现经 `_MODULE_FNS["holding_change"]` 由工作线程调度并复用共享 HTTP 客户端，失败/契约缺席照旧降级为「无归因」。`self_review` 因输入是四模块产出，仍串行后置。
- **逐模块耗时写入 perf**（rf-944）：`perf_history.llm.modules[*]` 新增 `duration_seconds`（缓存命中记 0），作为「关键路径卡在哪个模块」的机器可读证据。
- **实测收益**（4 次完整报告，2026-10-28 19:45~19:49，闲时）：串行尾残差 0.02 / 0.01 / 0.04s（判定阈值 5s）；`expert_review` p50 61.5s（阈值 83.6s）；归因 5.7–6.5s 完全落在并行批内；`LLM+新闻` 88.3 / 74.1 / 61.6s（缓存全命中运行 12.5s、归因 0.0s）。

### 变更
- **LLM 换键归因跨进程可见**（rf-954）：新增 `llm/fingerprint_baseline.py`——编排收尾把「各模块本轮缓存键 + 指纹组件哈希」落盘 `data/state/llm_fingerprint_snapshot.json`，下次预检读取作基线；归因主信号改为「键是否变化」（键变 ⇒ `fingerprint_changed` 并打出变化组件；键未变而读不到内容才是 `ttl_expired`；无基线 ⇒ `cache_miss`）。此前基线只在进程内存，重启后换键只能记成 `ttl_expired`（实测 expert_review 键 `bb5e0593dabe…` → `d86f4195c09f…` 被误归因），且「哪一段输入变了」无据可查。
- **`perf-history` 跨版本键名归一**（rf-950）：`breakdown` 的历史合并段「财报摘要与指标」在读取侧别名为 `财报摘要+财务指标（旧·合并段）` 单列，**不与拆分后的新子项混算**（合并段一次计时覆盖两子项，与逐子项均值量级不等价）；scripts-reference 的阶段细分表标注版本分界。
- 测试隔离补正：锚点路径隔离打在实际持有者 `news_dedup_anchor_store._ANCHOR_PATH` 上（此前打在门面 `news_dedup` 上只换同名变量，测试仍会追写真实 `data/calibration/`）；批内缓冲与「已告警」标记改由 `news_dedup_anchor_policy` 的单例复位，不再改门面副本。
- 压缩实现收口为 `news_dedup.compact_anchor_file` 单一份（生产维护与 `eval-dedup-threshold.py` 共用），工具侧只打印结果，不再自带第二份裁剪逻辑。
- 自检「去重锚点」改按分片汇总体积与行数（`2.6 MB / 62716 行 / 2 个分片`），提示语指向评估脚本的默认压缩。

## [0.16.9] - 2026-10-29

### 修复
- **括号内并列品种的数值归属**（rf-960）：实时报告把 561910（招商中证电池主题ETF）**正确**的 `-36.20%` 改写成 240012 的 `-8.0%`——`_locate_subject_code` 的括号作用域取括号内**首个**代码，同一括号并列两只品种时后续数值全归第一个；再叠加「按数值去重每轮只判一处 + 修正回写缓存」，逐轮把同一事实的其余句子逐个改错，最终报告与缓存里并存 `-8.0%` 与 `-36.20%`（自相矛盾，自检还会把矛盾当模型错误报出）。修法：括号内按**最近代码**归因；去重粒度改为「(数值, 所在句)」；改写改「全有或全无」（同值异义或仅部分判错则整值跳过，避免只改一处留其余）；同句同品种的收益率确认后，该品种在本句的下一个百分数按非收益率跳过（括号里的占比 `7.3%` 曾被改写成 `-36.2%`）。
- **权重表述不再被当作收益率改写**（rf-961）：智囊团模块单轮曾产生 9 处「修正」，全部是把权重改写成收益率——「它现在仍占 7.3%」→ 561910 的 `-36.2%`（中文最常见的权重表达「占 X%」未识别，词表只收了「占比」）；表格行「| 建设银行 | 601939 | 8.8% | 6.5% | 减仓 |」的权重列与目标列 → `241.5%`（单元格内无语境词，按就近代码归因）。新增「占」识别与「表格并列裸百分比单元格」整体跳过判据（单列百分比仍校验）；同时「已修正明细」改为只列**实际生效**的改写——此前按判定列表生成，归属不可知而被跳过的项仍被宣称已修正。
- **负缓存探测不再计入缓存命中率**（rf-961）：负缓存里没有记录 = 该确定性缺失不存在（正常预期，应照常取数），计入未命中会让命中率虚低、虚计每轮 7~13 次，并误触发「同前缀未命中 ≥5 次」告警。`cache.get` 增 `record_stats` 参数，负缓存探测器传 `False`（其命中另有自身计数与报告级汇总）。
- **缓存逐键日志降级 + 收尾一行汇总**：`缓存未命中（无此缓存文件）` / `缓存已过期` 逐键行降为 DEBUG（每进程每 key 首见一次），运行收尾由 `cache._stats.log_cache_summary()` 打一行 INFO——命中/未命中总量 + 未命中前缀 Top5；同前缀未命中 ≥5 次另升一条 WARNING（「每轮重取同一批键」的真实信号）。缓存清理「共 0 个文件」同样降 DEBUG。实测把单次运行日志里的逐键行（曾占 10%~30%）压到零。
- **事实校验误伤正确文本**（rf-959）：实时报告里出现「把低风险资产从当前的 **4.6%**（012325 12.5% + 240012 5.8%）提到 **-8.0%** 附近」——原文是占比 18.3% 与目标权重 25%，被校验器按最近邻改写成两个品种的收益率，句子随即自相矛盾；另一处把 011506（建信高端装备）**正确**的 +21.91% 换成同句 016055 的 18.7%（口语简称「建信装备」未解析 → 回退同句代码）。修正直接进用户可见正文，矛盾还被下游自检当成模型错误报出。新增三条非收益率守卫：目标位（`提到 X 附近`）、合计=分项之和（`18.3%（12.5%+5.8%）`）、主体不可解析（紧贴的名称解析不出持仓 → 宁漏改不误改，先剥离时间/度量填充词）。
- **事实校验规则版本并入缓存指纹**（rf-959）：修正后的正文会回写模块缓存且键不变，规则语义变而键不换时，旧缓存里被旧规则改错的正文会继续被复用（修复对存量缓存无效）。新增 `fact_checker.FACT_CHECK_RULES_VERSION`（当前 `fact-rules-6`），并入四可回写模块与辩论键的指纹；规则语义变化时递增即一次性换键重算。
- **状态探针不再计入缓存命中率**（rf-963）：历史增量链路对每只标的多读一次 `{key}_correction_streak`（连续触发计数），读不到即「未连续触发」属正常预期，却被记为缓存未命中——单轮虚计 17 次、命中率由 100% 掉到 94%，并触发「同前缀未命中 ≥5 次」告警。该读取改传 `record_stats=False`（与负缓存同口径）。实测连续两次运行命中率回到 157/157（100%），未命中前缀全部归零。
- **板块/指数涨跌不再被改写成品种收益率**（rf-964）：实时报告里「银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%」被全局最近邻兜底改写成某品种收益率（先 `102.0%`、后 `4.6%`，随最近邻漂移）；改完还回写缓存，导致每轮自检输入变化、多付一次 11~17s 的自检调用。新增「市场/板块口径且分句内无持仓主体」跳过判据（含持仓主体的错值仍照常纠正）。
- **缓存命中率汇总改为按轮口径**（rf-964）：`reset_cache_stats` 此前只有定义与导出口、生产侧从不调用，长驻进程连跑多份报告时「本次命中 X / 未命中 Y」累计成进程累计值（未命中前缀实测 5→10→15 递进），「同前缀未命中 ≥5 次」告警随之失真。现于报告边界（`start_report_run`）清零，与降级事件、自检载体重置同处。
- **指数涨跌不再被改写成基金收益率**（rf-965）：`纳斯达克100涨1.18%、标普500涨0.60%` 里的 1.18% 曾被改成 016055（博时纳斯达克100联接A）的 18.7%——指数中文名与基金名重叠，使上一版「分句内有无持仓主体」的判据失效。判据升级为「市场名词与持仓主体谁更近」，并按位置重叠识别「市场名词其实属于某持仓简称」（如「华安纳指」里的「纳指」指 040046）；词表补纳斯达克/道琼斯/富时/科创50/创业板指/北证。
- **版本盐进运行日志首尾**（rf-965）：提示词文本版本与事实校验规则版本都会整批更换 LLM 缓存键，此前日志里无痕迹，模块整批重算只能靠翻代码比对指纹判断。现于报告边界打「本轮开始」一行，收尾 `[cache]` 汇总行带尾注（`；缓存键版本盐：提示词=… 校验规则=…`）。
- **自检输出上限 3072 → 4608**（rf-965）：实测自检输出恰好触顶 3072 被截断，自动以 4608 重生成——同一份自检付两次调用并多等 5~8s。
- **「同前缀未命中」告警带具体键**（rf-965）：告警此前只说前缀与次数，还得回 DEBUG 翻逐键明细；现追加该前缀下未命中次数最多的 5 个键（键名计数有界 500，不无界增长）。
- **CI portability 档连红 8 次**（rf-967）：`test_ruff_exclude_contract.py` 两例用 `subprocess.run(..., text=True)` 未传 `encoding=`，在 `PYTHONWARNDEFAULTENCODING=1` + `error::EncodingWarning` 下直接抛异常；本地门禁不设该环境变量故全绿，属环境差异型缺陷。两处补 `encoding="utf-8"`，并新增 AST 静态守卫 `test_subprocess_text_encoding_contract.py`——`src/python`/`scripts`/`src/test` 下凡开文本模式而缺 `encoding=` 即失败（含扫描器自检 4 例，防用例恒真）。

### 重构
- **运行收尾日志收口到单一 hook**（rf-966）：新增 `report._run_scope.finish_report_run(perf)`，一次完成「落耗时台账 + 本轮结束版本盐 + 缓存命中汇总」；`core/perf.save()` 不再打缓存汇总，4 处调用点改走该 hook。同时 `cache._stats.log_cache_summary()` 的版本盐改由调用方传入——`cache` 是基础层，不再反向 `import llm.fingerprint` 取版本号（分层纪律：只能依赖下层与贯穿层）。
- **持仓主体匹配收敛为单源**（rf-966）：`_locate_subject_in`（取代码）/ `_has_subject_candidate`（取布尔）/ 数值检查器的 `_subject_spans`（取区间）此前各写一遍同一套「代码→全名→简称归一」匹配，口径一分叉就会出现「主体解析得到、距离算不出」的内部不一致。现 `_subject_spans` 下沉 `_utils` 作单源，`_has_subject_candidate` 由它派生（描述性尾名单独兜底）。
- **规则版本注释只述现状**（rf-966）：`FACT_CHECK_RULES_VERSION` 上方原先逐版列举 v2~v6 的变更史，与「代码注释不写历史沿革（沿革归 changelog / review-findings）」的纪律冲突；改为只留「递增判据 + 当前口径所在位置」。
- **连续触发计数与日期比较加固**（rf-966）：`chain_incremental` 抽出 `_correction_streak_key` / `_read_correction_streak` 消除两处重复读法，计数键遇非数值按 0（脏数据不中断取数主链）；重叠判定在 `.get("date")` 缺失时不再做字符串比较。

### 清理
- **移除旧格式/旧内部 API 兼容层**（rf-962）：本项目不承诺兼容旧数据文件、旧数据结构、旧缓存结构与旧内部 API，据此清理四处只为兼容而存在的分支——`analysis/metrics.py` 中仅供外部引用的重复常量（实现与唯一使用点都在 `metrics_returns.py`）、`get_rate_limiter` 上挂的 `cache_clear` 属性（改用模块级 `clear_rate_limiter_cache()`）、`_benchmark_returns` 对 dict 形态的接纳（生产只有 list）、以及去重锚点对「未分片早期单文件」的读取/并入/体积统计与 doctor 提示（锚点只认 `dedup_anchors-YYYYMM.jsonl.gz`，旧单文件被忽略）。保留 `.json`/`.json.gz` 双缓存编码、dict/对象双形态行情明细、天天基金季度接口回退等——它们属现行格式或数据源备用通道，不是旧格式兼容。

## [0.16.10] - 2026-10-29

### 文档
- **目录树描述确立「父行述动机、子行述内容」分工**：`folders.md` 中归档目录原先写作「名称 + 归档」（复述目录名），与子行的「XX 设计（…）」形成同义重复，两行读不出这篇文档存在的理由。现统一为：父行陈述动机与目标（补哪个缺口、替代什么现状），子行以「主题：内容构成」给出章节与产物，单看任一行均可判断其事由。
- **表述规范化**：描述一律采用名词短语式书面表达，去掉设问与口语结构（如「还看得清吗」「点得动、看得对吗」）；分隔符统一为顿号，`+` 与 `/` 不再混用。
- **覆盖范围**：`docs/archive/v0.1.x~v0.16.x` 共 32 处归档目录（含 4 篇借鉴研究、3 份申购限购设计、2 处浏览器验证归档）及其 39 处子行描述，逐篇依据各自「背景与目标」段改写，未引入文档外的内容；描述以「归档」结尾的父行清零。

## [0.16.11] - 2026-10-30

### 新增

- TUI 长任务可观测与可中止：报告生成期末行常驻**状态条**（阶段 · 已耗时 · 预计剩余 · 中止键，单行原地刷新），阶段文案复用 `core.perf.format_stage_status` 三渠道同源；按 `q` 为**有序中止**——在下一阶段边界生效、回主菜单，已完成产物与缓存保留并提示「重跑只补缺失」（`core/cancel.py` 的 `CancelToken` + `StageCancelled`，`PerfCollector.start` 为唯一生效点，编排层复用既有中断收口）。键不可用时状态条降级提示 `Ctrl+C 中断`。
- TUI 长输出分页查看器：运行日志 / 数据源健康历史 / 系统自检超出一屏时进分页视图（`空格`·`↓`·`j` 下翻、`↑`·`k`·`b` 上翻、`g`/`G` 首末、`/` 搜索命中置顶并计数、`q`/`Esc`/`0` 退出）；不足一屏或非 TTY 整段直打且不读键，「按任意键」闸门由 5 处收敛为 2 处。新增 `tui/pager.py` 与 `text_layout.terminal_rows()`。
- TUI 可发现性：首页 `?` 键位速查（菜单键一览 + 分组索引 + 三条常用动线 + 首用未就绪详情）；`/` 筛选从主菜单扩到列表面板（`NavState` 可见集合协议，`[S]` 18 项与 `[M]` 线路表已接入，帧顶显示 `筛选「x」：N/M 项`，`0` 先清筛选）；`j`/`k` 与 `↑`/`↓` 同义；未登记键与未知键在全档统一为一行反馈。
- TUI 面板覆盖补齐：`/` 筛选接入全部项目列表型面板（`[S]`/`[M]`/`[C]`/`[G]` 调优/`[G]` 匿名化），`u`/`U` 退回接入全部写配置面板（含 `[M]` 线路重排的动作型逆操作回放）；动作菜单型面板与对比指数增删按设计不接（项数少、逆操作语义重）。
- TUI 配置面板「可试可退」：`ConfigSession` 记录每个键的变更前值，`[S]` 面板 `u` 撤销上次、`U` 还原到进入面板时，页脚出现「本次改动 N 项」事实行；改动仍即时写盘（不做草稿态）。
- TUI 反馈闭环：错误行统一为「原因 → 下一步动作」（新增 `tui/action_hints.py` + `tui/error_tail.py`，短语与页头状态行同源，按终端宽度折行）；页头首用未就绪项折叠为一行（检测移出渲染路径并 TTL 记忆，详情进 `?`）。
- TUI 环境适配：`TUI_ASCII=1` 把装饰符号降级为 ASCII（一字符换一字符，**列宽按定义不变**，`tui/symbols.py`）、`TUI_PLAIN=1` 关闭原地重绘与状态条（整屏追加，便于日志抓取/朗读/录屏）。

- 持仓录入（TUI）：首页新增「持仓维护」组 `[U] 持仓录入（买入 / 卖出 / 保存）`，二级菜单编号为主入口、字母为别名（`1`/`L` 查看持仓、`2`/`P` 录入买入、`3`/`S` 录入卖出、`4`/`W` 保存到持仓文件、`5`/`U` 撤销上一笔、`0` 返回）。录入只进内存变更清单（不动文件），保存回显本次全部变更并确认后原子写回持仓文件（写前校验文件未被其他程序改动、留 `.bak`，可选记入交易流水页签）。查看持仓时本次未保存的行行首标红 `*`（账户标题同标、底部给图例），已落盘的行不标。
- 买入按份额加权平均成本、卖出保留原每份成本并校验超卖；场内必填成交价（回车可取当前行情），场外按交易日取官方净值并回显实际净值日期。
- 录入期校验：`00` 重叠区先按行情源反推场内/场外、仍不确定再问一次（避免场外基金被当股票要求录成交价）；价格与参考价偏离 > 20% 需确认（防小数点位错）；与本次已录笔完全相同的重复提交需确认。写盘后回读文件逐行核对份额/成本，不一致即报错并保留变更。
- 二级菜单含 `5`/`U` 撤销上一笔（以文件为基线重放剩余变更）；退出面板有未保存变更时为三选一（保存后退出 / 丢弃退出 / 继续编辑，默认继续编辑）。
- 场外买入区分「按金额 / 按份额」：交易日当天只允许按金额（份额 = 金额 / 当日官方净值），当日净值未公布时本笔不成立并提示净值公布后再录，不使用估算净值写入持仓文件。
- 新增模块 `core/holdings_editor.py`（读→内存变更清单→原子写回单源，含写后回读校验与撤销重放）、`fetcher/nav_lookup.py`（交易日→官方净值、金额→份额）、`tui/handlers_holdings.py`（录入面板）；新增需求 R-HLD-06~13 与对应需求追溯映射。

### 文档

- 管理文档同步（TUI 三批）：`DESIGN-TUI.md`（Keys 表补 `?`/`j k`/`u U`/分页键位块、Feedback 补长任务状态条与错误单源、新增「分页视图」节、Known Gaps 更新闸门处数与部分覆盖项）、`requirements.md`（R-TUI-05 扩写 + 新增 R-TUI-11~20）、`testplan.md`（追溯映射补 10 条 + 第 14/15 项补新机检与击键说明）、`technical.md`（语义命名表登记 `pager` / `live_status` / `symbols` / `error_tail` / `action_hints` / `first_run_notices` / `ConfigSession` / `apply_filter` / `cancel_token`）、`folders.md` 与 `test-coverage.md` 计数同步。
- 用户文档同步：`README.md`（五组菜单表述 + 状态条/中止/分页/筛选/退回/环境变量）、`how-to-use-tui-menu.md`（`j`/`k`、`?` 速查、长输出分页、面板内筛选、`u`/`U`、生成中状态条与 `q` 中止、`TUI_PLAIN`/`TUI_ASCII`）。
- 设计文档：新增 `docs/plan/tui-interaction-design.md`（议题稿，含 7 节迭代状态与决策结果）与三份批次实施方案（`tui-interaction-batch1-plan.md` / `batch2-plan.md` / `batch3-plan.md`）。

- 管理文档同步：`requirements.md`（§3.2 菜单表新增「持仓维护」组 + R-HLD-06~13，R-HLD-06 键位按最终编号/字母表述）、`testplan.md`（新增三条需求追溯映射）、`technical.md`（功能语义命名表新增 `holdings_editor` / `price_kind` / `nav_lookup` / `resolve_nav_on_trade_date` / `resolve_purchase_shares` / `ambiguous_price_kind` / `price_kind_from_quote` / `revert_last`）、`folders.md`（新增 3 个源码 + 4 个测试 + 设计文件条目）、`test-coverage.md` 与统计行、`plan.md`（plan-238 / plan-239 仅留任务号与简述，设计细节归 `docs/plan/holdings-entry-design.md`）。
- 用户文档同步：`README.md`（主菜单四组 14 项 → 五组 15 项，补 `[U]` 说明）、`how-to-start.md` 与 `how-to-use-tui-menu.md` 主菜单块 + 「持仓录入类」详解（别名、未保存标记、撤销、三选一退出、三项录入期校验、保存后回读校验）、`how-to-use-web-mode.md`（在线改持仓当前仅 TUI，Web 走上传覆盖）、`faq.md`（新增 2 问：能否不手改 Excel 改持仓 / 改完为何报告仍是旧数据）。

- Web 渠道持仓录入（`plan-239`）：新增「持仓录入」页签与 `GET /api/holdings`、`POST /api/holdings/preview`、`POST /api/holdings/save`；与 TUI `[U]` 共用 `core/holdings_editor` + `fetcher/nav_lookup`，支持账户/新代码/场内场外/份额或申购金额/价格留空取行情或净值；预览不落盘，写回走 mtime 闸门（409 `HOLDINGS_STALE`）+ `.bak` + 原子写 + 回读校验，可选记入交易流水。

- 演示截图流水线可重复执行：`demo` 工作区补 `src/` 软链（`PROJECT_ROOT` 搬到演示根后模板/静态资产仍可解析，报告 HTML 不再 `TemplateNotFound`）；`make-screenshots.py web --serve-demo` 自起演示服务（环境统一走 `isolation_env`，不再手工拼 env）；README 配图按虚构持仓重拍（TUI / Web 工作台·持仓录入·配置 / 报告首屏·汇总·图表 / CLI），新增 `web-holdings.png`。
- 截图/演示隔离补全（rf-973）：`PROJECT_ROOT` 支持 `INVEST_PROJECT_ROOT` 覆盖，演示工作区整体搬根（配置/持仓/产物同在演示目录）；`make-screenshots.py` 增加 `assert_demo_holdings()` 护栏，环境没带上即拒绝出图，杜绝真实持仓入图。

### 重构

- 持仓录入两日的技术债清理：① 主表表头判定（四列 + 跳过流水页签）上收为 `reader.match_holdings_header` / `reader.is_holdings_sheet` 公开单源，编辑层不再跨模块引私有 `_match_header`/`_EXPECTED_HEADER`，也不再自带一份重复判定；② 交易流水表头提为 `reader.TRADE_HEADER` 公开常量，写回侧不再复制字面量；③ 「按行情源反推品种形态」从 `core/holdings_editor` 下沉到 `fetcher/price.price_kind_from_quote`（`source_api` 属取数层内部标识，core 不解析 provider 名）；④ 三个测试文件各自的持仓 xlsx 构造器收敛为 `src/test/_holdings_fixture.py`（表头/账户/流水页签单源）；⑤ `list_xlsx_files` 的文件枚举加目录与 mtime 容错（并发删除不再抛错打断枚举）。

- 技术债清理：① 品种形态判定抽为 `core/holdings_editor.resolve_entry_kind` 单源（显式声明优先 / 歧义区统一抛错），TUI 与 Web 不再各写一份；② 测试持仓构造器复用 `reader.HOLDINGS_HEADER` / `TRADE_HEADER`（不再复制字面量）；③ Web 路由的请求体解析收敛为 `_json_payload()`（新增路由复用，非对象统一 400）；④ 补 `INVEST_PROJECT_ROOT` 覆盖回归 2 例（未设置回落仓库根 / 设置后持仓与产物随根切换）。

### 修复

- TUI 自查技术债：`KeyWatcher` 双实例导致 `q` 中止在真实终端不生效（保留的轮询器从未进入 cbreak）、状态条阶段文案与 `format_stage_status` 双源、配置会话在面板退出后仍存活（后续面板写盘记进旧会话）、分页器 `_start_rendered` 隐式属性；四项均补回归用例。

- 历史走势终点回填（消除「走势终值 vs 报告头市值」口径差）：`get_combined_timeseries` 新增 `latest_quotes`（由 `_snapshot.latest_quotes_from_detail_rows` 从持仓明细派生，无估值日不入表），某标的历史末条早于最新行情日时按最新价追加一条终点 bar——回填走副本不改会话缓存序列，as-if 份额语义不变。实测上轮残留的 1,608 元差异（011506 历史停在 10-27、实时已到 10-29）随之归零，末端日收益与回撤不再被低估。
- 终点滞后的双端呈现与日志去重：Excel「数据质量仪表盘」把源健康「历史走势」行转降级并列出滞后标的（`_apply_history_staleness`），品种覆盖行写「净值数据滞后 N 个交易日」——此前只有 HTML 数据状态有提示，Excel 仍写「✅ 正常 / 行情净值正常」，同一份报告双端说法相反；子块长窗（同一次运行的第二次全量计算）改传 `warn_on_terminal_staleness=False`，同一事实不再在日志里报两遍。
- 指数历史日线会话缓存复用补 INFO 标注（`[index] … 会话缓存复用（已有 N 根，请求 M 天）`）：此前基准归一化无论是否真取数都打「获取完成」，日志看起来像同一指数被取了 3 次。
- 历史走势终点口径校验（`history_data.terminal_staleness`）：LOCF 合并会把未刷新的标的沿用上次净值，此前只有「净值落后组合终点 ≥2 个交易日」时也静默混用不同日期的估值——实测某次报告走势终值 272,424.45 与报告头总市值 269,163.02 相差 3,261 元（1.2%），末端日收益与回撤同步偏低，而同数据重跑此前 10 次两者差额恰为 0。现在按「落后 ≥2 个交易日」判定（T-1 属常态不提示），命中即追加 `warnings`、写 WARNING 日志并给出滞后标的/滞后日/占比，同时在数据状态区渲染新增状态 `history_nav_stale`。
- 指数历史日线会话缓存复用判据补三条（`fetcher/index.py`）：记下的请求窗口 ≥ 需求、已存序列长度 ≥ 需求天数（日线是截至今日的连续序列，根数 ≥ 天数即覆盖窗口）、或已存序列达源单次上限（约 2000 根）。此前只比「请求窗口天数」，同一份报告内先用 90 天取过、再按 730 天/3650 天取会各重发一次请求（实测沪深300 一轮被取 3 次，且第二、三次拿到 2000/2002 根不同长度的序列，各面板口径可能不一致）。
- 生成后自检输出上限默认 `max_tokens_self_review` 4608 → 8192（rf-970）：满编持仓下 4608 仍被截断触发自动重生成，同一份自检付两次 LLM 调用。
- 缓存未命中告警判据从「同前缀 ≥5 次」改为「同键 ≥3 次」（rf-971）：冷启动一批资产各取一次不再误报；负缓存/纠偏计数探测键（`_miss_`、`_correction_streak`）不进未命中分桶。
- 同花顺 provider 的「该源无此标的/能力」错误码（1002/3001/3002/3004）降为 INFO（rf-972）：中证 800 行业指数不再每轮刷十几条告警，其余业务错误仍按 WARNING。
- 读取持仓不再对「交易流水」「分红流水」页签刷「表头不匹配，跳过」告警（rf-969）：主表解析在解析前跳过已知流水页签名，流水页签仍由 `read_flow_sheets` 正常解析；未知页签的告警行为不变。
- 持仓录入入口键位从借用的字母 `T` 改为 `U`（rf-968）：`T` 原属 `[D]` 二级系统自检，借用需改动既有守卫；改用未占用的 `U` 后四处守卫原样保留、无需放宽。同时把主菜单「14 项」写死条数断言改为唯一性结构断言（良性新增不再误判回归），并同步 `requirements.md` 菜单表新增「持仓维护」组。

## [0.16.12] - 2026-10-30

### 变更

- 持仓录入（TUI `[U]`）交互减负：单笔录入去掉「确认加入本次变更」二次确认，改一行回显（保护点仍在保存与「撤销上一笔」）；保存两问合一为一次输入（`回车`=写入·自动 `.bak` / `f`=记入交易流水后写入 / `2`=丢弃草稿 / `0`=返回）；新增 `6`/`C`「继续录上一笔」复用账户与标的；提示行去掉重复示例（口径集中在面板头）。新增需求 R-HLD-14 与追溯映射。

### 修复

- TUI 状态条收敛（撤回上一版的后台心跳与中止键）：状态条只报当前阶段（`[..] 「阶段」 · Ctrl+C 中断`），阶段切换时刷新一帧；不再启后台线程、不读 stdin、不改终端属性——后台轮询会与生成前的交互提示抢输入，cbreak 泄漏会让终端失去回显；中止回到 `Ctrl+C`（即时中断，产物与缓存同样保留）。状态条改为在持仓就绪后启用，收尾放进 `finally`，异常/中断路径也清条。
- TUI 首页 `?` 压缩为两行摘要（键位 + 分组索引 + 待配置项），详细键位留在手册；菜单页脚恢复原样（不再加长窄屏页脚）。
- 配套：`status_bar_text` 支持只报阶段；删除 `KeyWatcher` 与心跳用例，新增真实伪终端用例（写入可达、termios 不变、不读 stdin）。
