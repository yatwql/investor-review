# 变更日志归档 — v0.17.x

> 归档时间：2026-11-05（v0.17.1 发布并入；已并入 2 段：v0.17.0（11-04）、v0.17.1（11-05））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.17.0 ~ v0.17.1（2026-11-04 ~ 2026-11-05）
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
