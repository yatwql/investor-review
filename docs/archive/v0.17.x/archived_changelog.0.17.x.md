# 变更日志归档 — v0.17.x

> 归档时间：2026-11-08（v0.17.6 发布并入；已并入 7 段：v0.17.0（11-04）、v0.17.1（11-05）、v0.17.2（11-05）、v0.17.3（11-06）、v0.17.4（11-08）、v0.17.5（11-08）、v0.17.6（11-08））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.17.0 ~ v0.17.6（2026-11-04 ~ 2026-11-08）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.17.0] - 2026-11-04

### 变更

- **基金经理取数增两级负缓存（rf-1039）**：此前主页解析不出或不可达时不落任何结论，同一份报告里穿透 / 基金经理分析 / 菜单预热各调一次 `fetch_fund_manager` 就各重走一遍 HTTP 并再记一次缓存未命中（实测 `fund_manager_017730×4`）。现按「确定性空 12h（`fund_manager_miss_`）/ 不可达 1h 短退避（`fund_manager_backoff_`）」分档登记，命中即跳过取数；缓存注册表、`datasource.md` / `how-to-config.md` / `technical.md` 的负缓存表格同步。新增 4 例回归。
- **流水页签日期接受 Excel 原生日期单元格（rf-1038）**：此前手工在 Excel 里按日期格式填的「交易流水」「分红流水」日期读回带 `00:00:00` 尾巴，被判「日期无效」**整行静默丢弃**（该笔卖出在 XIRR / 成本分档 / 分红里凭空消失）。现读取侧 `_coerce_flow_date` 把 `date`/`datetime` 与文本统一归一为 `YYYY-MM-DD`，且 `_valid_date` 补日历校验（`2026-13-01` 一类形态合法但不存在的日期不再放行）。新增 5 例回归。
- **持仓录入缺省记入交易流水**：TUI 保存（`4`/`W`）与 Web「确认写入持仓文件」的「记入交易流水」由**需要显式指定**改为**缺省开启**——买入与卖出走同一保存出口，回车/默认勾选即写入并留痕（TUI `n` 显式跳过，Web 取消勾选后记住选择）。改因：流水既是 XIRR/成本分档/分红的唯一数据来源，也是卖出重算成本的依据，缺省不记会让后续分析静默缺数据。
- **指数行情会话级复用（rf-1037）**：`fetcher/index.py` 的 `fetch_indices`/`fetch_us_indices` 外挂 `index_quote` 会话缓存（`DataSourceRegistry.session_cache`，与 `fetch_index_history` 同口径）——同一轮运行内重复调用只取一次上游、未命中只记一次（此前一份报告里行情页与渲染层各调一次，`gb_dji`/`gb_inx`/`gb_ixic` 各记 3~4 次未命中并重复请求）；陈旧兜底读取改用 `cache_get(..., record_stats=False)`，不再把「同一键的第二次读」计成新的未命中（命中率与未命中前缀分布不再失真）。空结果同样入会话缓存，避免一轮内为「无数据」重复等重试。新增 6 例回归（美股/ A 股复用、空包缓存、载荷隔离、两处陈旧探针不计数）。
- **成本分档改净成本口径（与卖出录入同源）**：`analysis/cost_flow.py` 的 `build_cost_lots`（FIFO 批次）替换为 `build_net_cost_positions`——按代码合并为**净成本 = Σ(买入金额+费用) − Σ(卖出金额−费用)**，单位净成本 = 净成本/净份额，回收超成本时钳 0；`compute_cost_tiers` 改为按**净成本单价**与市价比较整码归档（不再按批次拆档）。口径理由：卖方不保证录入完整流水，批次追踪在流水缺失时会给出与持仓表不一致的成本；净成本只依赖已录的买卖金额，缺流水时退化为快照近似。用例：5 例净成本原语（含费用摊薄/卖出冲减/超额钳 0/清空/无买入）+ 2 例分档口径（整码归档、卖出回收可翻转档位）；`reports-instruction.md` 与 `requirements.md` R-CFL-01 同步。
- **持仓录入：卖出改为净成本法重算（R-HLD-08 口径调整）**：原先「卖出保留原每份成本、只减份额」，卖出回收的资金不影响剩余持仓成本；现按 `剩余成本 = 原成本总额 − 卖出份额×卖出价`、`剩余每份成本 = 剩余成本 / 剩余份额` 重算（回收金额超过原成本总额时钳制为 0，不产生负成本）。改动点：`core/holdings_editor.py` 卖分支 + 模块成本口径注释；用例改为断言净成本重算并新增「超额回收钳 0」一例；`requirements.md` R-HLD-08 与 TUI 手册「写回规则」同步。
- **财报源超时预算分档（rf-1036）**：`providers/datasink.py` 把单一 20s 预算拆为**正文档 20s / 探测档 8s**——章节清单 `/documents/{id}/sections` 只回小 JSON，SSL 握手挂起即主机不可达，用正文预算会让一次挂起白等 20s+（实测单次 23~25s、7 日 26 次，使 full 报告「数据准备」从 1.5s 涨到 59s 量级）。预算经 `_request(..., timeout=)` / `_get_with_transient_retry(..., timeout=)` 透传（晚绑定默认值，运行期可覆盖），挂起判据与连接级重试沿用同一 `with_connect_retry` 脚手架。新增 3 例回归（探测档预算生效 / 正文档仍走长预算 / 两档关系固定）；`datasource-reliability.md` 的 DataSinking 节补「超时设定」行。

## [0.17.1] - 2026-11-05

### 修复

- **LLM 缓存指纹分界：只锁结构与口径，行情/时效类交 TTL（`rf-1040`）**：连续两轮「持仓与市值完全相同」的报告仍 4/4 全 miss，预检归因 `fingerprint_changed=4`（不是 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、A/美股指数、竞争语境块、量化指标、历史风险信号、穿透市值与占比）与时效数据（事件窗分歧例块、调仓纪律回放块：新闻 15 分钟一刷且每行带收益/超额浮点）全数锁进键，使 4h（`expert_review`/`health_check`/`penetration_deep`）与 24h（`global_macro`）TTL 实际退化为分钟级。改法：`build_llm_fingerprint` 入键收窄到持仓成本（`name/code/cost`）+ 分类**结构**（新增 `extract_stable_categories`：类型→排序品种集，不含市值/盈亏）+ 穿透品种集与 `sector`（新增 `extract_stable_penetration(include_sector=True)`，`full` 口径保留为诊断专用，`risk_signals_of` 降为诊断口径）+ 两个版本盐；行情类参数保留形参但不再参与哈希。四个模块构造器同步剔除竞争语境/量化指标/风险信号，`global_macro` 改为持仓+分类结构（并补传 `holdings_details` 保证预检/写两侧同源）；事件窗分歧例块与调仓纪律回放块出键（仍进提示词），自检与辩论三键同口径；`skeleton` 新增 `_APPENDIX_EXCLUDED_SECTIONS`，`global_macro` 不注入事件窗分歧例块。文档同步：requirements（R-HCR-05/R-SR-04/R-EW-06 改「口径类进键、时效类交 TTL」）、technical §3.4 指纹分界与失效语义；单测七份同步（`test_module_fingerprint` / `test_cache_fingerprint_alignment` / `test_cache_matrix` / `test_cache_sequence_matrix` / `test_report_sequence_cache` / `test_fingerprint_baseline` / `test_fingerprint`），事件窗与回放注入用例改为断言「时效块不换键」，并新增 `test_market_derived_inputs_do_not_change_fingerprint` ×4 与 `test_structural_inputs_change_fingerprint` ×4 锁定分界。


### 新增

- **判断依据块章首三行摘要（`plan-245`）**：块默认折叠、summary 只有一行，多数读者不展开 → 该需求体感为零。改为行动建议章首固定三行：① 有效信号数与可信度档 ② 风险预算超限项 ③ 纪律触发数（无超限/无触发写否定态，三段全不可用压成一行空态），明细仍折叠；`build_headline()` 单源产出，HTML 渲染在折叠块之前、Excel 写在块首，两端逐字一致；`headline` 进 `decision_basis_data` 契约，Excel 旧契约无该键时回落单行 summary。
- **「我的建议历史表现（按视界）」表（`plan-244`）**：结算能力早已在（`settle-decisions` + 账本 5/20/60 `settlements`），但报告只露出「结算批数」，用户读不到「我的建议历史上准不准」。在判断依据的结算摘要下补按视界聚合表（已结算数 / 方向性样本 / 命中数 / 命中率 / 均值超额），命中判定复用 `decision_ledger.classify_direction_outcome`（含 ±1.5% 平盘不判定），命中率仅在方向性样本 ≥ 20 时给结论值，否则「命中/方向性（样本不足）」；只读账本、不依赖 `decision_reflection` 开关，口径与 `settle-decisions` / `doctor` 同源；双端同表，数据缺口行计入 gap 不再静默丢样本。
- 测试：新增 `TestDecisionBasisHeadline`（三行规则 / 否定态 / 空态压缩 / 章首位置在折叠块之前 / 双端同文）与`TestPerformanceByHorizon`（命中-未命中-平盘-缺口计数 / 样本门槛口径 / 基准缺失不入超额均值 / 双端渲染）；`test_action_sheet` 与双端同源用例改按 headline 断言。

### 变更

- **事件窗关键词索引扩面（新闻与持仓匹配率）**：实测一轮 32 条新闻里 24 条因「关键词不在持仓索引」整条丢弃（`not_in_holdings`），而其中多数是行业级新闻（如「白酒动销回暖」）。索引从「名称+代码精确等值」扩为三类键：① 品种直指（名称、剥去 ETF/LOF/指数/联接等产品后缀的简称、代码裸码与 `sh`/`sz` 前缀写法）；② 行业直指（`classify_sector` 板块名）；③ 行业关键词（`penetration.sector_keywords()` 单源 301 词表内指向同板块的词）。行业级命中在关键词列标「（行业）」，读者能分辨是品种新闻还是行业新闻；非 A 股品种（场外基金等）仍不入索引、仍计入 unmatched 不硬算。新增 4 例单测（行业词命中与标注 / 前缀代码变体 / 简称后缀剥离 / 索引层级与基金排除）。

- **穿透深度分析提示词润色（表达拗口 → 白话 + 结构化）**：原 system prompt 只有四行小节清单，模型自由发挥时容易堆括号、先绕口径再给结论。改为三条硬写作约束（中文白话一句一事、结论在前数据在后、只写数据里出现的品种）+ 四节显式阈值（行业 >30% 标「偏高」、单品种 >15% 点名，未超写否定态、分散度 1-5 分附打分依据），user prompt 的收尾指令同步改为按节逐条列出要点；未改输出契约与渲染层。`PROMPT_SCHEMA_VERSION` 递增 `rate-caliber-3 → 4`（四可回写模块与自检键一次性换键，属预期），`test_module_fingerprint` 接线前基线随盐刷新。

- **plan-243 收口：决策依据链路停止加码，剩余价值拆为独立任务**：自家回测把这条链路的卖点判掉了（V1 5 日成熟 61 条命中率 0.5385、均值超额 −0.0053；V3 两口径 5 日 IC +0.0399 / −0.0267 均无三分位单调；V5 成熟样本 2 条、V7 样本期 146 交易日 < 250）——五类信号三家证伪、两家样本不足，链路只能如实摆事实、不产生预测力。据此 **R8 纪律规则重构不启动**，估值分位/因子目录按「已回测未通过」「样本不足」归档（保留三态标注呈现，`eval-decision-quality.py` 留待样本累积后一次性复跑），形态 B 独立章节不启用；观察项（V5 成熟样本 ≥100、V7 样本期 ≥250）只在触发条件满足时再看。剩余用户价值拆为 **plan-244**（「我的建议历史表现」可见视图：5/20/60 视界命中率与均值超额，只读账本）与 **plan-245**（依据块章首默认展开三行摘要，解决「默认折叠 → 体感为零」）。

- **both 路径申购限购取数接线修错（`rf-1041`）**：`_generation_both` 把 `config` 当 `holdings_details` 传给 `build_purchase_status_data`，开启「基金申购限购」（默认开）且全量表取数成功时，构建期渲染约束块迭代 dict 得到键名（str）→ `h.get("code")` 抛 `AttributeError`，HTML+Excel 双产物整条中断（`report` 命令直接失败）。改传持仓明细最小形态 `[{"name": d.name, "code": d.code} for d in details]`（与 full 路径同源同形，受阻标的口径不变）；补回归用例（`test_both_path_passes_holdings_details_not_config_to_purchase_status`）。

- **智囊团复盘方向约束收敛为一句（去掉叠用的对冲措辞）**：情景段原有三处同义且互相抵消的指令——条件化动作要求、随情景段追加的「不操作是合法结论」出口、以及品种引用段「除非不对具体品种动手…无需勉强引用品种」的口子，与系统提示 Phase 3「给出量化调仓方案」并存时只能产出官样回避口吻。改为单源一句：`MANDATE_CONDITIONAL` 写清「满足什么条件动手、动什么」，条件不成立或信息不足则直接写「不操作」并点明所缺数据；`scenario_mandate()` 改由两条情景路径（标准 fallback / 配置条件情景）共用一处追加，品种引用口子压成一句、不再复述「不操作」；系统提示 Phase 3 补「结论为不操作时写明理由与触发条件」使两处口径同向。
- **智囊团专家须具名**：召集令只要求「挑 5 位流派对立专家并标明立场」，模型常以 A/B/C/D/E 或「专家1/2」占位，可读性差。系统提示补「姓名式称呼 + 机构/头衔，禁止 A/B/C/D/E、「专家1/2」或「多/空」这类占位名，同一专家全篇用同一称呼」。
- 上述两项均为提示词静态文案改动，`PROMPT_SCHEMA_VERSION` 递增 `rate-caliber-2 → 3` 一次性换键（四可回写模块与自检键同步重算，属预期）；`test_module_fingerprint` 的接线前基线随盐刷新；单测补「对冲措辞只出现一处」「专家具名禁止占位名」断言。
- **`decision_basis` 开关从 `[C]` 章节内选项移到 `[S]` 机制与质量组**：判断依据是行动建议章的**章内内容增强**、不增删章节，放在章节显隐面板的 5.1 子项位置与语义不符。注册表 `group` 改 `mechanism`（`[S]` 新增 15 号，其后四项顺延 16~20），`chapter_registry` 的 `enable_action.sub_items` 清空（`[C]` 5.1 消失，章节内选项只剩智囊团 7.1/7.2，组内计数 3→2）。**报告产物与开关语义不变**（装配点/默认值 true/`_ms` 回退口径/缓存键都只读开关值，不看 group；`enable_action` 关闭时整章不生成，块仍不可见）；**入口与联动确实变了三处**——① `[C]` 5.1 子项消失，连带「父章关闭 → 子项置灰拒写入」的闸门一并消失（`handlers_report_chapters` 按 `entry.sub_items` 判父子），该开关现在可与章节状态独立改；② `GROUP_DOMAIN` 由 `report_content` 改 `presentation_mechanism`，Web 配置面板该项从「报告内容」段移到「呈现与机制」段（`web/config_edit.py` 按域分段）；③ `[S]` 编号 15~20 整体位移。

## [0.17.2] - 2026-11-05

### 修复
- **天天基金历史净值的日期整条前移一天（`rf-1051`）**：`pingzhongdata` 的 `Data_netWorthTrend[].x` 是「当日 00:00（UTC+8）」的毫秒数，解析时按 `timezone.utc` 解，等于取前一日 16:00 → 每一条净值都被标成前一交易日。后果是录入侧「按交易日取官方净值」永远取不到 T 日：实测卖出一笔 2026-11-05 的 240012，历史链尾部是 11-04=1.5574（真实为 11-05 的值），提示「2026-11-05 无净值，采用 2026-11-04 净值」并要用户确认；而同一份净值走缓存刷新（东方财富最新净值接口）标的是 11-05，两条路径互相矛盾。现按 `BEIJING_TZ` 解析（与 `tiantian_ranking`、`providers/utils` 同一口径），验证 `resolve_nav_on_trade_date("240012","2026-11-05")` 返回 `exact_date=True / 11-05 / 1.5574`，11-04 正确回到 1.5409。契约不变：缓存写入路径不变，已缓存的历史会在下次调用按「provider 全量返回 → 替换」分支自动更正，无需手工清缓存；此前按错日期录入的历史成交需自行核对（用的是前一日净值）。补 3 例单测（毫秒时间戳按北京时间解、整数 YYYYMMDD 不受影响、相邻日时间戳映射到相邻日期）。
- **持仓录入的「份额 / 金额」口径在提示里说清了（`rf-1048`）**：卖出第一步到底录份额还是金额，面板上一度读不出——买入项说明写「份额或金额」（金额实际只在场外买入口径里可选），紧邻的卖出项只写份额，两行对照读像卖出也能选金额；帧头提示又只写「金额单位元」「多数提示回车取默认值」，而卖出份额那步回车是取消本笔。现三处同源改写：买入项说明限定为「份额（场外买入可按金额）」、卖出项写明「卖出份额（份，a=全部）」，帧头提示改为「份额按份录入，金额仅场外买入可用（元）……每步回车的作用见该行提示」；卖出份额提问补上单位「份」与可卖份数（`卖出份额（份，可卖 500；a=全部）`），买入仍写「买入份额（份）」。口径本身未变（卖出始终按份额）。补 3 例单测。
- **走势/回撤章就地标出「读数口径」与 QDII 滞后明细（`rf-1046`）**：走势终点由滞后净值构成时（QDII T-1/T-2 常态，落后 ≥2 个交易日才报），口径差异原先只在数据源状态章与日志 WARNING 里说，读者在本章读到的末端日收益与最大回撤仍会被当准确值。现 HTML 该章首与 Excel 页签顶部各加一块「读数口径提示」：逐标的列出最新净值日/滞后交易日数/占比，并明写「末端日收益与最大回撤会偏低，终点附近数字只作参考」；`STATUS_MESSAGES.history_nav_stale` 同步补上后果。补 4 例单测。
- **清理侧不再拿盘中 30s TTL 判行情缓存过期（`rf-1045`）**：清理与读侧共用 `get_ttl`，盘中行情类 TTL 是 30s，于是每轮启动与收尾都把 30s 前刚写入的价格/指数缓存判死删掉、下一轮再写一遍（实测反复预览 22~63 个待删文件）；删掉的部分对读侧本就没有价值。现清理侧改走 `cache/_ttl.get_cleanup_ttl`：**交易时段内**一律按静态 TTL（不拿读侧口径删文件）；**盘后**另回收**盘中写入**的副本——盘中价只是当时的快照，盘后读侧会按静态 TTL 把它当收盘价沿用 24h，因此按**写入时刻**是否落在交易时段判定并回收，收盘后（如 15:30）写入的当日收盘值保留。交易时段判定新增 `core/market_hours.is_intraday_timestamp()` 单一承接。读侧 `get_ttl` 与新鲜度判据不变。补 4 例单测。
- **「刷新基础缓存」不再连坐作废财报/财务指标缓存（`rf-1044`）**：`[1]` 走 `clear_by_group("refresh")` 清整组 19 个模块，但该流程只回填其中 10 个，财报索引/正文、财务指标、市场情绪、新闻逐条分析、申赎费率、指数估值历史、无风险利率被一并作废，要等下一次出报告才逐只回源。实测现场：同一天前几次运行命中率 95~99%，一次刷新后紧接的报告掉到 35%（price_stock 45 / fin_indicator 42 / report_datasink 35 全未命中）、多付 267 次请求、墙钟 134s。`clear_by_group()` 新增 `only` 参数（按缓存前缀/精确键名限定域），`update_basic_cache` 传本流程真回填的域名集合 `_BASIC_REFRESHED_CACHE_KEYS`；手册 `[1]` 段落分开列「会清」与「不再连带清」两份清单。补 2 例单测。
- **批量 LLM 失败与全缓存命中不再同形（`rf-1043`）**：批量路径的用量字典在「全批失败」与「全命中」下都是零值，批次级成败完全没回传，日志只到 WARNING——现场一次 deepseek 与 opencode 双链相继熔断，3/3 批全失败、41 条新闻 0 条含分析，日志仍写「生成完成」，报告里该模块判别不出残缺；全链不可用也只发 WARNING，攒了 12 天日志 0 条 ERROR。`_execute_and_merge_batch` 改为回传本批解析条数，`run_batch_mode` 聚合 `ok_batches`/`failed_batches`/`total_batches` 入用量字典并按成败分级留痕（全失败 ERROR、部分失败 WARNING）；`_finalize_news_token_usage` 区分「完成」与「全部批次失败」并明说该模块将标为失败；`llm/api.py` 全 provider 失败升 ERROR 并打印已尝试的链路。补 3 例单测。
- **事件窗行情窗口按最早事件日自适应（`rf-1042`）**：索引扩面后能匹配到更多新闻，但行情取数窗口写死 365 天，事件日更早的新闻整条按「映射交易日不在行情轴」降级（实测一轮 23 条降级里 19 条属此类）。新增 `history_days_for()`：按最早事件日回推回看天数 + 后窗余量 + 30 天缓冲并夹在 365~1095 天内，默认股票与基准取数器同用该窗口；短窗新闻仍按 365 天，不额外拉数。另一半成因同修：事件日**晚于行情轴末日**（当日 K 线尚未落地）时原按「映射交易日不在行情轴」整条降级，改为按行情轴末日对齐并在视图计数标注（`anchor_shifted`/`align_note`），仅剩轴首缺日与关键位缺失仍降级。实测一轮：降级 23→4、可出行 36→50（当时触 50 行上限 capped 4，上限随后提到 80 后 capped 归零）。补 6 例单测（窗口基线/放大/夹上限、默认取数器请求值、末日对齐正反向）。
- **删掉旧配置键兼容层（`config/_legacy_keys.py`）**：`RENAMED` 早已为空、`REMOVED` 仅剩 `llm_usage` 一条，维护它只为给「旧键→新键/已删除」出一句处置建议。既然不保留跨版本配置兼容，整表与两处派生告警一并删除：`features.json` 未登记开关与 `config.json` 未登记章节键各自归并成一条告警（带条数与键名），手册「已删除 / 已改名的配置键」节改为「未登记的配置键」并删掉对照表。净删 1 个模块 + 1 份单测。
- **删掉两处纯兼容代码：决策头缓存后缀 `_dh` 与指纹的四个「仅为调用兼容」入参**：① 决策头缓存后缀函数恒返回 `_dh`，唯一用途是区分「未引入决策头前」的历史缓存条目——缓存不兼容后连函数与两处调用点一并删除；② `build_llm_fingerprint()` 的 `total_mv/total_cost/total_profit/total_today_profit` 早已不进哈希、只为调用兼容保留，从签名与 4 个调用点、5 处单测一并删除（行情派生量本就不该入键，注释同步改写）。两处都会让 LLM 模块缓存键一次性变化（旧条目按 TTL 自然退场），属预期。
- **兼容层复核：两处「疑似兼容」代码确认不可删，一处命名改正**：① `cache/_io.py` 的「清理另一格式文件」不是旧格式兼容——gzip 与否按**当次载荷是否超 100KB** 逐次决定，同一键可能先后落 `.json` 与 `.json.gz`，清理是防读到陈旧副本的正确性保障，保留；② `tiantian_holdings` 的「第 3 跳」不是旧接口兼容，而是「不指定年份的默认请求」取数阶梯兜底（覆盖 QDII/联接/债券），保留；其历史命名 `_fetch_legacy_quarterly` 易被误读为兼容代码，按语义化命名改为 `_fetch_default_quarter`（含 13 处引用与语义表行）。

### 变更
- **行情类缓存刷新的判定收敛为一次（技术债清理）**：上一条刚落地时留了三个尾巴——①`core.data_freshness` 与 `report.market_value` 两套「是否最新」判据并存，一次刷新解析两遍交易日历、归一两次明细；②`PositionCacheResult` 的 `price_details` 只有写入方、UI 已改从分市场条目取数，成了半死字段；③`handlers_cache._nav_date_of` 重写输出后无人调用。现合并为 `_judge_after_refresh()`（历法解析一次、明细归一一次 → 直接产出分市场条目），删掉 `price_details`/`freshness` 与死函数，`_market_breakdown()` 改为接收 `trading_day` 参数不再自取历法。行为不变（对外提示文案与计数口径未改），测试同步改写为「单次判定」形态。
- **更新行情类缓存后按市场列出取价口径与「已更新到最新」计数**：原来只报成功/失败条数，但「刷新成功」不等于「数据新鲜」，且笼统一句「实时 8 条」也不准确——场内拿到的是当日收盘价（盘中才是实时价），场外是当日官方净值。现刷新完成后按**报告同源实现**再给一段结论，判据全部引用不重写：`report.market_value.classify_holdings()` 分组（场内 / 国内场外 / QDII）、`price_update_status()` 判「是否已更新到最新」（场内需已收市且日期为 T、国内场外 T、QDII 以 T-1 为最新）、`_determine_price_type()` 出口径文案（「场内收盘价(T)」/「场内实时价」/「官方净值(T)」/「官方净值(T-1)」等），未更新的逐条点名并带落后交易日数（`count_trading_days_elapsed`）。契约上 `PositionCacheResult` 新增 `trading_day`/`market_breakdown` 两个回传字段，TUI 侧格式化；未取到交易日历则只丢判定不影响刷新。接线踩到两个口径差：①取数层日期字段叫 `price_date`、报告侧 `DetailRow` 才映射成 `nav_date`，直接喂原始明细会让全部品种误判「过期」（实测 12/12）；②场外净值接口不回名称，`price_update_status` 靠名称识别 QDII，拿空名会把 QDII 的 T-1 误判为未更新（实测 4/4）——现日期补别名、名称以持仓名为准。（`rf-1049`、`rf-1050`）补 10 例单测（新鲜度四类、日期别名、名称回退、历法不可得降级、刷新流程回传、分市场计数、QDII T-1 计最新、国内场外 T-1 计未更新、点名与 OK 行、无判定时静默）。
- **两套样式表公共面抽成 `_base_styles.html`（plan-247）**：报告页与调仓页有 34 条逐字相同的规则（排版/表格/页头页脚/浮动按钮——早年复制留下的基础面），改为抽到 `partials/_base_styles.html`，两页各 `{% include %}` 引在页面样式之前。**验证方式为「规则集不变」而非肉眼**：改前改后逐项比对① 页内归一化「选择器→声明」多重集哈希、② `@media` 块数、③ 去样式后正文的空白归一化哈希，三项完全相同（报告规则集 9190e9f1… 、正文 5ed41e14…；调仓规则集 505214c4…、正文 82281384…），另用特异性/落点分析确认无「等特异性同落点属性重叠」的级联顺序敏感对。报告页此前没有样式回归网，本次补 `TestReportCssRulesetBaseline`（规则集哈希：搬移不变、增删改必变），与调仓页既有 golden 基线共同承担。`TestSharedStylesheetParity` 重写为聚合口径（公共面 + 页面面）：单页内选择器不得重复、跨页同名规则须同源或入白名单、白名单差异消失即失败。
- **移除结构测试的文件级 pyright 抑制（改 bs4 窄化助手）**：`test_html_report_structure.py` 原用一行 `# pyright: …6 条规则…` 关掉整文件的类型检查，遮的全是 bs4 的宽返回类型（`Tag.get()` → `str | AttributeValueList | None`、`find/select_one` → `Tag | None`、`children` 元素是 `PageElement`），但范围过宽——同文件里将来真正的 None 解引用也会被吞。新增 5 个窄化助手（`_attr` / `_attr_list` / `_text` / `_child_tags` / `_select_one`：缺失即 fail 并带上选择器上下文），替换 30 余处调用点后抑制整段删除，`lens_diagnostics` 对该文件零 finding，43 个结构测试全绿。
- **样式一致性守卫（两套样式表同名规则 / 样式 partial 宿主映射）**：报告页与调仓页的样式表同名选择器 39 条（其中多数是早年复制的基础面），此前没有任何检查——改一处漏一处就会让同一角色两页两种实现。新增两组断言：① 同名规则要么逐字一致（归一化空白），要么在显式差异白名单里（`:root`/`.section-title`/`td`/`th`/`.chart-export-btn`/`.summary-card .meta`，各带「两页为何必须不同」的理由，且白名单出现无差异条目即失败，保证只减不增）；② 每个 `_*_styles.html` 必须登记宿主模板映射，否则 W1 白名单会静默失效。
- **报告样式资产抽成独立 partial（`report_template.html` 1025 → 276 行）**：765 行 CSS 从主模板抽到 `partials/_report_styles.html`、234 行从 `whatif_template.html` 抽到 `_whatif_styles.html`（整块 `<style>` 原样搬运，宏定义先移出到 `<style>` 之前）；主模板经 `{% include %}` 引在 `<style>` 之外，块内保持纯 CSS。收益是关注点分离（改样式不再与改结构挤同一文件/同一份冲突）＋新增守卫「`<style>` 块内零 Jinja」（此前正是宏与表达式混在样式块里，让 CSS 解析器对每个模板报错）。测试读取口径随之分层：`_html_report_fixtures.read_template_css()` 读聚合样式、`read_template_text(with_partials=False)` 读单文件标记（计数类断言不被拼接虚增）。
- **修复自定义报告章节顺序失效（去内联化的回归）**：去 Jinja 化时把章节 `order` 全部移除，DOM 顺序改为按注册表固排，但 `config.json → report_section_order` 是受支持配置——序号变了排版不动。现由 `html_writer._inject_section_order_css()` 在服务端拼 `#sec-x{order:N}` 规则并替换模板占位 `<!--SECTION_ORDER_CSS-->`（HTML 注释承载，CSS 解析器不介入，不违背「Jinja 不进 CSS 值」约束）；附属区块 `#sec-self_review` 与穿透章同号、由 DOM 顺序决胜，观感不变。补 1 例守卫（自定义序号必产对应 order 规则、占位符必被替换）。
- **技术债清理（测试夹具下沉 + 常量单一源）**：缓存类测试里「写指定写入时刻/年龄的缓存载荷」样板散在 3 个文件各一份（改清理口径就要同步改三处），收敛到 `src/test/unit/cache/_cache_fixtures.py`（`write_cache` / `write_cache_at` / `today_at` / `pre_open_ts`）；`core/market_hours.py` 的官方交易状态缓存 TTL 由 `86400 * 7` 字面量改用 `CACHE_WEEKLY`，与缓存注册表同源。
- **报告模板内联样式去 Jinja 化（class 驱动，`rf-1047`）**：模板原把 Jinja 写进 CSS 值位置（`style="order: {{ n }}"`、`style="color: {{ x | profit_color }}"`），HTML 语言服务把属性值当 CSS 扫、单模板稳定报 28 条解析误报（此前靠 `.pi-lens.json` 关掉该服务止声）。现按「颜色→语义 class、顺序→DOM 顺序、几何量→HTML/SVG 属性」三条改写：64 处动态内联样式清零（20 处 `order` 由 DOM 顺序承载、40 处颜色/字号/字重改 class、1 处配置分布条改 SVG 属性宽度），新增 `profit_class` / `price_type_class` 过滤器与 11 个工具类（色值全部引用既有 token，暗色自动跟随）；`report_template.html` 的 include 顺序对齐 `_REPORT_SECTION_DEFAULT`（`action` 与 `data_source_status` 归位，渲染顺序与改动前一致）。`.pi-lens.json` 删除，HTML 语言服务恢复。守卫 3 条（模板静态扫描 / 渲染产物断言 / DOM 顺序与编号）；下线已无模板使用的 `profit_color` / `price_type_color` 两个内联颜色过滤器（保留并单测覆盖 `profit_class` / `price_type_class`），报告套件 2834 通过。
- **48h 变更技术债清理（口径文案单一源 / 交易日时段判定补测 / 声明清单守卫）**：① 「读数口径提示」的标题句、后果句与逐标的明细原在 HTML 模板、Excel 写入器、数据状态词三处各写一份，现由 `report/_history_quality` 定常量与拼装函数，生产侧写入 `history_data.terminal_staleness`（`headline`/`consequence`/`caveat`/`assets[].detail`），Excel 与状态词直接取用，HTML 副本由渲染用例按同一常量逐字断言；② `core/market_hours.is_intraday_timestamp()` 补边界测试（09:30/11:30/13:00/15:00 含端点，分钟外不算）并把入参放宽为 `float | str | None`（它本就容忍脏值，签名与实现对齐）；③ `_BASIC_REFRESHED_CACHE_KEYS` 增注册表守卫用例——手写域名清单一旦遇到前缀改名会静默变成空操作，现逐项断言登记存在。
- **「我的建议历史表现」补结论列与涨跌色**：原来只给命中率与均值超额两组数字，读者要自己合成判断。新增 `performance_verdict()` 按「命中率 × 均值超额」两轴出一句人话（方向有效且跑赢基准 / 方向命中但跑输基准 / 方向偏错但选品仍跑赢基准 / 方向与超额双弱），缺任一轴时只说可得轴（如「仅有超额：跑输基准」），方向性样本 < 20 时结论加「（样本不足，仅参考）」；HTML 单列展示并按超额涨跌上色，Excel 行动页签列宽 5→6 让超额（结论）列完整可见。补 4 例单测（四象限 / 缺轴降级 / 样本不足后缀 / 双端渲染）。
- **事件表行数上限 50 → 80**：事件窗索引扩面后单轮可命中 60+ 条事件行（行业级关联占大头），50 行上限会把有效行计入 `capped` 截断（实测一轮 capped 4 条、可出行止于 50）；提高到 80 留出余量又不失控，超限仍按原口径计入 `skipped.capped`，视图合计行不变。

## [0.17.3] - 2026-11-06

### 修复
- **缓存 TTL 矩阵用例在凌晨不再假失败（`rf-1054`）**：这些用例原先用 `now.replace(hour=8)` / `now.replace(hour=10, minute=5)` 造时间戳——跑在 00:00–08:00 时戳落在未来，年龄为负，「超过静态 TTL 必须回收」「盘中快照盘后回收」两类断言随之失真（实测 01:01 出现 14 例失败，HEAD 上复现，与业务改动无关）。现抽 `_recent()` 取「今天该时刻的过去最近一次」，时段语义不变、与运行时刻无关，105 例全通过。
- **LLM 模块结果行不再把「失败」写成「生成失败（跳过）」（`rf-1052`）**：provider 全挂、用户关开关、预算到点三种情况过去都打成同一条 INFO，事后按日志无法区分「内容为什么缺」。现按 `LLM_MODULE_FAILURE` 分四级：成功 / 开关关闭 / 预算跳过走 INFO，**其余一律 ERROR** 并带可读原因（如「LLM API 网络连接失败」）与「报告对应章节将降级/占位」；`llm/skeleton.py` 的失败行补上模块名与原因（此前只有一个缓存键）。失败原因文案收敛到 `llm/failure_reasons.FAIL_REASON_LABELS` 单源，报告模块状态直接引用同一表（原 `report/llm_module_info._DISPLAY_REASON` 副本删除）。补 9 例单测（四条分级分支 + 文案单源身份断言 + 未知/缺失原因回退）。
- **基金经理全部解析失败时给出下一步（`rf-1053`）**：实测连续两天（10-30、11-02）档案页 SSL 握手超时，日志只有一句「基金经理全部解析失败」，读者无从判断要不要处理。现告警写明「本轮按缺数据降级（报告该章写占位），下次运行会自动重试；若连续多日出现，先查档案页链路是否可达（SSL/超时）」。补 1 例单测（告警须含降级与重试方向）。

### 变更
- **事件表行数上限 80 → 160**：索引扩面后单轮命中量已顶到上限——实测一轮可出行 80 条、`capped` 18 条（另有降级 6 条），说明 80 成了信息瓶颈；提高到 160 既保留「防极端召回爆炸」的护栏，又能把已命中的有效行放进报告。超限仍按原口径计入 `skipped.capped`，视图合计与降级计数不变。

## [0.17.4] - 2026-11-08

### 修复

- **新闻关联批量解析失败不再冒充成功**（rf-1055）：响应整体不可解析时解析器返回 `None`，批量骨架按「本批
  失败」收口——不写结果、不写逐条缓存（占位入缓存会被后续轮次当命中复用）、计入 `failed_batches` 并触发
  「部分批次失败」告警，已消耗 token 照常计费；LLM 部分作答仍按正常产出处理（缺失项填默认值）。此前 3 批中
  2 批不可解析时，20/30 条占位被算成「含 LLM 分析」，并连带事件窗极性缺失（91% 事件不可判）。
- **批量用量行显示真实 token**（rf-1056）：归一化协议改按 usage 形状判定，不再把 provider 条目名
  （如 `deepseek-main`）当协议名传进 `_log_token_usage`，消除「输入 0 + 输出 0 = 0 tokens」的假账。
- **逐模块费用改用数值口径**（rf-1057）：不再回读 `estimate_cost` 的展示串（≥0.01 只到 3 位小数），
  消除 0.0646→0.0650 的精度丢失与「逐模块合计 ≠ 页签总计」。
- **HTML 生成阶段拆出子步骤耗时**（rf-1058）：模板渲染 / JS 资产内嵌 / 匿名化 / 落盘四步分别记入阶段细分
  （保留「页面写入」总值供跨版本比对），慢写告警只针对「落盘」段，慢的时候能直接定位到底是渲染、内嵌、
  匿名化还是磁盘 IO（同尺寸产物实测 0.02s / 6.15s / 21.0s 三档）。
- **慢段告警按段分流**（rf-1058）：`warn_slow_write` 支持自定义事件名与排查提示，渲染慢报「HTML 模板渲染 渲染
  偏慢 → 排查模板内逐行循环/过滤器」，落盘慢才报「排查磁盘/挂载与 fsync」；full/both 两条路径均接线。
  实测 0.98MB 产物**落盘仅 0.003s**，此前 6.15s 的「页面写入」实为模板渲染——告警方向原先指错了磁盘。
- **Jinja 模板字节码缓存**（rf-1059）：HTML 生成阶段的耗时实为**模板编译**（18 个模板 0.65s ≈ 97%，渲染仅 ~0.02s、落盘 0.003s），接入字节码缓存到 `<缓存根>/jinja/` 后**冷 0.654s → 热 0.027s（≈24×）**；键含模板源码校验和（改模板自动失效），缓存目录按需解析以尊重测试隔离与 `INVEST_CACHE_DIR`；旧键按 `BYTECODE_CACHE_TTL_DAYS=14` 在写入时回收（改模板换键后不再只增不减）。
- **Excel 产物清扫遇合并单元格整份报告生成失败**（rf-1061）：`mask_workbook_text` 遍历 `ws.iter_rows()` 时未跳过
  `MergedCell`，而被合并吞掉的从属单元格 `value` 只读——清扫命中一处带笔名的合并行即抛 `AttributeError`。
  `full_anonymous` 模式下只要页签里有一条合并单元格（汇总警示行、指数标题行都是），整份 Excel 报告就写不出来。
  现按单元格类型跳过从属单元格（笔名文本存于锚点单元格，锚点仍在遍历集内，不漏清扫），并补「合并区域不抛异常
  + 锚点被改写 + 非合并行照常改写」的回归用例。

### 清理

- **文档与架构约束同步**（rf-1060）：`technical.md` 把 `data/cache/jinja/` 字节码缓存登记为「缓存统一管理」架构约束的
  唯一例外（二进制非 KV、自管保留期）；`requirements` R-PERF-09 / `technical` / `scripts-reference` 的阶段细分名单补齐
  HTML 生成四步；`developer-guide` 补写盘告警按段分流的判读口径；`data-and-backup` 补 `data/cache/jinja` 删除影响。
- **48h 变更技术债清理**（rf-1060）：删 `_first_provider_name` 死函数、`_render_template(self_review_block=...)`
  被架空的死形参、`write_html_report(force_llm=...)` 无调用方的死参数；HTML 阶段收口（总值记录 + 慢段告警）
  抽成 `html_writer.close_html_generation_stage` 由 full/both 共用——此前 both 路径完全没有慢段告警。
- **七组同构副本收口为单一本体**（rf-1062，覆盖 8 个文件、+342/−274）：这些成对的函数原先逐字重复，改一侧
  另一侧不会跟着变，正是口径漂移的温床。各组现共用一个参数化本体，对外签名与输出**逐字不变**：
  - `core/atomic_write.py` —— 文本/二进制写入共享 `_write_atomic`（临时文件→`os.replace`→Windows 占用回退），
    文本仍走 `os.fdopen(fd, "w")` 以保留换行翻译语义（若改成直接写字节，Windows 产物会从 CRLF 变 LF）；
  - `report/excel_writer.py` —— 小计/总计行共享 `_write_summary_row`，差异只剩底色（黄/绿）；
  - `tui/text_layout.py` —— 终端列/行探测共享 `_terminal_dimension`（实时 ioctl → `COLUMNS`/`LINES` → 下限兜底）；
  - `config/_json_patch.py` —— dict/array 值区块共享 `_replace_value_block`，括号字符参数化（`{}`/`[]`）；
  - `report/_report_helpers.py` —— 组合演进/快照差异注入共享 `_inject_optional_section`，构建函数经惰性导入
    包装传入（不做运行时动态 import），失败降级口径仍是「`available=False` + 不阻断报告」；
  - `providers/sina.py` —— A 股/美股指数拉取共享 `_fetch_sina_indices`，仅解析器、日志称谓与
    「格式异常行是否告警」不同（美股链路保留该告警，A 股原先就没有，不借重构改行为）；
  - `report/summary.py` / `fetcher/index.py` —— 指数渲染共享 `_write_index_group`（当日标题
    「本日」/「最新」参数化，保持两个市场的原有文案）、指数取数共享 `_fetch_with_session_cache`。
- **截图演示工作区重建不再被旧软链卡住**（rf-1063）：仓库换目录后 `demo/src` 的旧指向仍在，`_link_repo_src`
  把「链接存在」当就绪直接跳过，报告渲染于是落到废路径（`TemplateNotFound: report_template.html`），
  重跑 `demo` 也修不好、只能手工删链；现校验链接目标与当前 `REPO_ROOT/src` 是否一致，不一致则重指，
  并补「旧指向 → 重跑 demo → 自愈」回归用例。
- **文档与实现四处不一致对齐**（rf-1064）：①Web 手册标题写「六区」而正文写「5 个工作区」且页签表缺「持仓录入」行；
  ②该手册目录把 §5 排在 §8/§9 之后（序号乱序）；③`requirements.md` 写「24 项全部 affects_report」与
  「前六组在 `[S]`」，而注册表是 26 项且 `[S]` 只含五组；④定价附录缺 `claude-opus-4-6`、多出注册表已无的
  `claude-sonnet-5`。均按注册表真值改正（六区 + 补行、目录 §1~§11 重排、开关数与面板分组、定价表增删一进一出）。

## [0.17.5] - 2026-11-08

### 修复

- **LLM 指纹分两类**（rf-1078）（价格相关 / 价格无关，`cache_policy.PRICE_INDEPENDENT_MODULES` 单源）：价格无关模块（`global_macro` / `news_correlation`）键里不含价格、不带行情口径桶后缀，盘中可复用；其余模块带桶后缀、盘中不复用。分类同时驱动「桶后缀」与「盘中闸门」两处行为，新模块默认按价格相关处理。
- **与价格无关模块的缓存键去掉价格信息**（rf-1077）：`global_macro`（全球政经局势）与 `news_correlation`（财经热点关联）的结论只取决于「持有哪些品种」，此前键里带着持仓变动复盘块（市值/盈亏差）、行情口径桶后缀与穿透 mv/ratio_pct，价格一变就整批换键、TTL 从未生效。现前者只留结构/分类/申购限购块，后者穿透只留 `name/codes`（`news_context_fingerprint()` 单点构造）。另新增 `trading_calendar.trading_day_as_of_cached()`：行情口径桶改用「只读已缓存日历、绝不触网」的判定，指纹相关用例不再隐性依赖取数。
- **LLM 缓存加时间口径：盘中不复用、收盘档可复用**（rf-1076）：LLM 指纹含行情派生块（申购限购/持仓变动/环比降级），盘中逐分钟变、收盘后冻结。新增 `core.market_hours.market_snapshot_bucket()` 把「本次运行依据哪个已完成时点」抽成四档（盘中 / 上午收盘 / 当日收盘 / 上一交易日收盘），每轮报告判定一次；盘中档在预检与骨架两处跳过缓存读（归因 `intraday_no_reuse`），收盘档同档内正常复用；桶键进四个基础模块与辩论键指纹；统一 prompt 附录后追加 `【数据口径】…` 行，预检摘要旁打印本轮口径。文档：`llm-technical.md` §7.6、`technical.md` §3.4、FAQ 同步。
- **运行观测口径回正：逐模块耗时扣排队、批量模块耗时落账、市场情绪零命中可判读**（rf-1075）：`per_module.duration` 改为「模型耗时」（`PacingGate` 现按线程记账整段过闸等待——含此前漏记的并发许可等待——骨架调用前后扣减；实测串行端点曾把 62s 墙钟记成 88.2s）；批量路径（`news_correlation`）由骨架回传阶段墙钟，不再恒记 0.0s；`market_sentiment` 日志补两侧规模（龙虎榜/连板梯队条目数 × 跟踪标的数），交易日改为龙虎榜→连板梯队双源兜底。
- **空数据契约键集收口单源 + TUI 前置失败退出码**（rf-1074）：上一轮修复引入的兜底把 `available=False` 的键集写到第三处（`report/_report_factor_metrics` 字面量），且兜底 `window` 退化为 `0`；现键集单源到新增的 `analysis/unavailable_contracts.py`（无 numpy/pandas，重依赖坏掉时仍可用），两个计算模块与编排层兜底统一委托它，补三条单源断言。`tui.main()` 前置检查失败改为 `raise SystemExit(1)`，直连入口也能被脚本感知。
- **裸解释器启动致 full 报告整份失败**（rf-1073）：系统 Python（无 pandas/numpy）下生成报告，`ModuleNotFoundError: No module named 'pandas'` 从数据准备阶段冒泡到 `generate_report`，用户只看到「生成失败」。三处根因同批修：启动脚本不再依赖 `activate`（venv 搬家后其烘焙的绝对 `VIRTUAL_ENV` 使激活静默失效，裸 `python3` 落到系统解释器），改为直接调用 `.venv` 内解释器并前置「重依赖可导入」硬闸；`pandas`/`numpy` 补进 `requirements.txt`/`pyproject.toml`（此前仅经 akshare 传递安装）；`analysis/style_factor_regression.py` 的 pandas/numpy 改惰性导入、编排层把计算层导入纳入 `try` 并 `ImportError` → `available=False` 降级（§1.4.5，不再拖垮整份报告）。`core/doctor.py` 增「关键依赖」自检行与 `interpreter_preflight_error()`，TUI/Web 入口启动即拦截并给出解释器路径与修复命令。
- **幻觉采样三处断言只看「有告警」**（rf-1065）：`test_wrong_profit_rate_vs_portfolio` / `test_mixed_correct_and_wrong` /
  `test_missing_code` 原本只断言 `len(issues) >= 1`——检测器把任意无关数值判成偏离也能转绿，测不出「对照的是组合
  累计收益率 / 涉事个股 600036 / 涉事代码 002837」这一核心口径。现补点名断言（含实际值 9.7% 与代码）；
  与仓内已有的 `test_wrong_stock_return`（已断言 `issues[0]` 含代码）同标准。
- **缓存边界用例名实不符**（rf-1065）：`test_intraday_written_cache_expired_right_after_close_gate` 名称称
  「盘后已过期」，断言却是「仍可读」（本用例只验读侧，收盘时点门禁由同文件 TTL 口径用例覆盖）。
  改名为 `test_intraday_written_cache_survives_static_ttl_after_close`，docstring 直接写明验证的是「静态 TTL 下仍可读」。

### 清理

- **`test-coverage.md` 揟掉历史复盘痕迹与失真导语**（rf-1066）：两条带日期的「门禁口径变更」告示（含「修复前匹配全空」
  「台账旧值 10,136」「9,800→10,145」）已在 `changelog`/归档，不再在统计页重复；其中「上方 `dev-verify`/`verify`
  两行为并入前快照」已是错误导语（该表已重测），删除后条目只留当前口径并指向 `technical.md` §4.23。「两机差距」
  段内联的绝对耗时（`unit ~28s`/`all ~39s`/`data ~3s`）与紧邻其上的表（`~1min`/`~28s`/`~5s`）相矛盾，改为只陈述
  按表重算的比值区间；旧采集事故叙事改为不带日期的排查口径（先查未 mock 外部访问，再谈负载与并行度）。
- **8 份文档正文清掉历史复盘痕迹**（rf-1067）：`DESIGN.md` / `developer-guide.md` / `technical.md` / `llm-technical.md` /
  `scripts-reference.md` / `testplan.md` / `datasource-reliability.md` / `how-to-config-llm-reference.md` 里的带日期告示
  （「已采纳 / 已落地 / 收紧」）、「曾经的写法」「曾占…现口径」「历史漂移」等对照叙事，统一改写为**当前状态陈述**：
  告示去日期与「已采纳」口吻只留规则；对照叙事改为「若…则…」的风险机制；缺陷描述改为要求陈述；口径类内容指向真源
  （如 `technical.md` §4.23 / §9.2）。实测确认：仅保留实测数据点的日期（取值快照），不保留变更公告式日期。
- **程序注释清掉历史复盘叙事**（rf-1068）：`src/python` 47 处、`scripts` 19 处、`src/test` 44 处「此前 X 现在 Y」
  「原先各写一份」「曾占…」式对照与带日期的校准告示，统一改写为**当前状态陈述**：对照句改「若/不得 X，否则 Y」，
  告示去日期只留规则，重命名史改「不得沿用旧称」。保留「回归背景 / 回归场景」元描述（`CLAUDE.md` 明确豁免，
  用于说明断言为何存在）。顺带修 `edit_ops`/`_ymd` 两处入参类型收窄（Pyright 报 Unknown|None 赋给 str）。
- **评测脚本 global_macro 漏传 `total_cost`**（rf-1069）：`scripts/_eval_halluc_sampler/llm_call.py` 调用
  `_build_global_macro_prompt` / `generate_global_macro` 时少传 `total_cost`——`categories` 落在 `total_cost` 位置、
  `categories` 缺参，该评测路径运行时必抛 `TypeError`。补实参；顺带初始化 `cached=False`（未命中任何分支时不再未绑定）。
- **6 文件静态类型债清理**（rf-1069）：`prompts_signals._is_number` 改 `TypeGuard[float]`（11 处数值运算不再报
  Unknown）、`generators` 的默认值取键前 `isinstance(..., dict)` 收窄且 `_max_tokens` 显式兜底 18432、
  `generators_orchestrator` 的基线组件 `or {}`、`test_correlation_html` 用 `_require_section()` 断言取节点并
  去掉 Optional 下标、`test-smoke-web`/`metrics.py`/`_llm_settings`/`atomic_write` 的 Optional 与 I/O 调用收口。
- **96h 变更技术债收口**（rf-1070）：去 Jinja 化批次留下的 `.bg-primary` / `.bg-alloc-mid` / `.bg-alloc-low`
  三条工具类无任何引用（SVG 用的是 `.fill-alloc-*`），按死样式删除并重标定报告页 CSS 规则集哈希；
  `close_html_generation_stage`（full/both 共用收口）此前只有端到端间接触及，补 4 条直测锁住其分支——
  无 recorder 静默返回、有分段时按「落盘」耗时告警、渲染慢指向模板而非磁盘、无分段时回落总值。
- **控制台着色回归「色源单源」约束**（rf-1071）：`core/ansi_colors` 新增 `RAW_CODES` 与
  `supports_color(stream)` / `codes_for(stream)`（按**指定流**判定着色能力），`core/doctor.py` 与
  `report/cli_progress.py` 改为调用前者——此前两模块各自硬写 `\033[...` 转义码并各自复制
  `NO_COLOR`/`isatty` 判定，改配色或降级口径必漏改一处。
- **删掉最后一处「旧内部接口」门面**（rf-1072）：`core/data_freshness._detail_value` 只是
  `core/detail_view.detail_value` 的一行转发（自述「仅保留旧名」），`holding_status` 也经它取值；
  现已统一直调 `detail_value`。兼容面七类复核结论保持不变：旧配置项/旧配置文件/旧数据文件/
  旧数据结构/旧缓存结构/旧缓存文件均无兼容分支（结构变更一律硬闸门拒绝或整体作废，见 `technical.md` §9.2）。

## [0.17.6] - 2026-11-08

### 变更

- **死代码与重复实现收口**（净 −546 行，删掉的符号均已无生产/测试引用）：LLM 重算归因里那张「模块 → 依赖组件」派生表（判据已收口为「只看模块键是否变化」）、财报负缓存的 `hit` 读取器、eastmoney 行业的两个便捷接口、`report/orchestrator` 的章节开关助手、`tui/handlers_qa` 的 what-if 前缀常量、`market_sentiment` 的行字段契约常量、`fetcher/index` 的腾讯美股代码表；指数裸码的市场号判定改由 `core/code_symbols.index_exchange_of` 单点决定，不再由 provider 自建段前缀表。同时收口两处同构实现：新闻源标签统一走 `news_sources.get_source_label`，开关取值解析复用 `config/features.parse_switch_value`。

### 修复

- **并发用例改事件/屏障判定，消除墙钟抖动**（rf-1087）：`test_slow_jjcc_hedges_to_zqcc`（jjcc `sleep(2.0)` 后断言 `<1.9s`，余量 0.4s）与 `test_categories_fetch_concurrently`（0.05s×3 断言 `<0.12s`，余量 0.03s）在慢 runner 上偶发失败（实测 CI 3.13 红两次）。改为 jjcc 阻塞在事件上、主线程校验「zqcc 起跳时 jjcc 未返回」；新浪分类改三路屏障（串行即超时失败），断言并发语义而非调度运气。
- **配图与面板不再显示本机绝对路径**（rf-1086）：演示工作区配置改为相对项目根（`data/holdings` / `reports`），并新增展示原语 `core/system_info.display_path()`（项目根之下 → 相对形式，越出根目录或跨盘符保持绝对）——系统状态卡与 Web 配置面路径输入框统一走它。此前 Web 工作台「正式更新」提示会把 `/home/<user>/…` 这类本机目录印在面板与 README 配图上。README / 手册全套配图按演示工作区重出（虚构账户 A/B、6 只公开品种）。
- **Web 配置面随 `[S]`/`[C]` 收口同步**（rf-1085）：载荷里那个永远为空的「关联产物」块（`artifact` 分位已无条目）整体删除（域/标题/载荷/前端渲染器），功能开关改为只下发 `[S]` 面板上屏项、经 `panel_switches` 单点取数（不再内联一份上屏判定、不再下发 `[C]` 专属组）；补三条契约用例锁「Web 上屏集合 = TUI `[S]` 面板、`[C]` 项经章节块/子项覆盖、隐藏项不下发」。手册的 Web 域块清单与机制组条目、TUI 面板提示语同步。
- **面板分块与编号全量对齐**（rf-1084）：`whatif_trade_cost` 迁入 `[S]` 后，8 份文档仍按旧口径（`[C]` 四块含关联产物、`[S]` 旧编号、`--chapter` 可覆盖关联产物、R-WIF-13 分组）。文档统一为：`[C]` 三块（顶层 / LLM / 整章，`artifact` 分块位保留但空块跳过）、`[S]` 编号 1-18（机制组内置常开项不占编号）、关联产物入口一律指向 `[S]` 持仓与交易组。

- **归因判据收口后的文档与回归收口**（rf-1083）：未命中归因已改为只看「模块键是否变化」，`llm-technical.md` 仍在描述已不存在的「模块→组件映射表」，且拆分归因用例时丢了 `TestSkeletonPathAttribution` 类头（骨架路径归因的来由注释），`_cache_fixtures.degradation_events` 构造器随之无人调用。文档改为「唯一判据是键变化，组件哈希只服务诊断」；恢复类头并补一条回归：降级事件变化只让 `health_check` 归因为 `fingerprint_changed`（数据质量变了不能当「只是到点」）。
- **初始化铺出的可编辑配置文件补覆盖与写盘防护**（rf-1082）：`init_config` 新增「缺失即按模板铺出 `logger.json` / `llm_pricing_ref.json`」，但无用例锁定该行为；且 `test_init_template_writes_relative_paths` 只屏蔽了原有的两处写盘入口，新增两处在临时还原真实路径的分支里会写进仓库 `data/config/`。补两条用例（缺失即铺出、已存在不改写），并把四处写盘入口一并屏蔽。
- **面板开关清单跨渠道单源 + 两处清理**（rf-1081）：`panel_visible=False` 的开关此前只在 TUI 隐藏，Web 配置面仍全量下发；现统一经新增的 `panel_switches(panel)` 取数（含可见性过滤），`panel_option_numbers` 复用同一入口。顺带删除 `tui/handlers_holdings` 里零引用的单笔回显函数，并把「行情口径桶」测试桩收口到 `src/test/_market_clock.py`（档位 key/label 单源）。
- **成本流水近似分支的数值防护**（rf-1080）：无流水时（开关开）`_build_flow_data` 把明细 `price` 原样收进`current_prices`，非数值会让下游 `final_value > 0` 抛 `TypeError`，异常冒泡导致整份 HTML 报告失败。改为只收正数值市价；并补两条真实现回归（近似分支跑通、非数值市价被过滤）。
- **`[S]` / `[C]` 面板按语义收口**（rf-1079）：判断依据与 LLM 输出评级不再占面板编号（默认常开、日常无需调，仍可用 `features.json` 覆写）；候选基金比较改**自动项**（配置了候选池即生效，不上面板）；首页执行摘要卡转正默认开；市场情绪与资金热点标记「需凭据」。`What-if 交易成本对比` 由 `[C]`「关联产物」迁入 `[S]` 持仓与交易（它只给既有调仓页签加成本层、不新增章节），`[C]` 回归纯章节面板。守护脚本与用例夹具补「空块」容忍。
