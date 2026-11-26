# 计划归档 — v0.18.x

> 归档时间：2026-11-12（v0.18.0 发布，本系列首份）；2026-11-16 v0.18.2 本批原表搬运；2026-11-18 v0.18.4 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.18.x 开发期完成项（按发布版号批次，v0.18.0 → v0.18.4）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-256` ✅ 交易日原语单点化（消除 fetcher → report 反向依赖）

**现状**：`fetcher/price.py` 的价格新鲜度判定沿用 `report/market_value` 的交易日函数再导出（运行期与测试共用一个改动点），
分层规则把它登记为冻结例外（`check-import-surface` 的 `layer-inversion`，到期 2027-06-30）。
**动作**：`report/market_value` 内部改为按模块属性调用 `core/trading_calendar`；测试 patch 点随之迁到 core 单点；`fetcher/price`
直连 core 后删除该 re-export 依赖与例外登记。
**验收**：`check-import-surface --ci` 无 fetcher→report 命中；`report/market_value` 相关单测（含 patch 点）全绿。

**结果**：`report/market_value` 内部改为按属性调用 `core/trading_calendar`，`fetcher/price` 与 `report/_holding_detail_rows`、`report/excel_module_loader` 直连 core；测试 patch 点统一迁到 `core.trading_calendar` 单点（22 个测试文件、136 处）；例外表与「存量分层例外」表删除该行，`check-import-surface --ci` 零命中。

## `plan-257` ✅ 报告生成编排函数拆分

**动机**：`report/excel_generator.generate_excel_report` 479 行 / 92 分支、`_generation_full._generate_report_full` 410 行、
`report/html_writer.write_html_report` 357 行——文件行数未触红线，但改动一处需通读全函数。
**做法**：按页签族与阶段提取子函数，逻辑逐行搬运、产物不变；产出阶段入参收敛为上下文对象。
**结果**：

| 函数 | 拆分前 | 拆分后 | 拆出的子函数 |
|:---|:---|:---|:---|
| `generate_excel_report` | 479 行 / 92 分支 | **216 行 / 20 分支** | 行动建议兜底 / 市场情绪 / 景气度诊断 / 可选明细页签 / 环比对比摘要 / 收尾保存 |
| `_generate_report_full` | 410 行 / 47 分支 | **304 行 / 17 分支** | 行业资金流向（三态降级登记）/ LLM+新闻阶段（`_LlmStageResult`）/ 双端产出与收尾（`_FullEmitContext`） |
| `write_html_report` | 357 行 / 10 分支 | **312 行 / 6 分支** | 三面板视图装配 / 数据源状态装配（`_DataSourceBundle`）/ 渲染前置上下文（`_RenderContext`） |

**验收**：产物同输入对拍不变（`test_excel_generator` / `report` 2926 用例全绿）；P0/P1 门禁全绿。
**边界**：拆分止于当前粒度——剩余主体是 `_render_template` 的 80 个关键字实参与 50+ 入参，更深一层需改渲染契约（见 `plan-258`），收益在可读性而非行数。
**存量超长函数（非本项范围）**：`analysis/schedule_replay.run_schedule_replay`（335）、`llm/generators.generate_debate_procon`（312）、
`cli/_parser._build_parser`（277）、`report/_orchestrator_data.prepare_report_data`（271）——按需另立。

## `plan-258` ✅ 深层渲染契约收敛（`_render_template` 收上下文对象）

**结果**：新增 `report/html_template_context.py::TemplateContext`（94 个字段 = 模板变量契约），`_render_template(context)` 收敛为「`render(**asdict(context))` + 章节顺序 CSS 注入」两行；81 个关键字形参与 94 行 `render(...)` 关键字表在 `write_html_report` 侧改为一次性装配（派生量就地算好），`html_writer.py` 760 → 596 行（退出 P4 膨胀登记）。模板文件零改动。
**验收**：模板变量键集合与拆分前逐一对应（`test_html_template_context.py` 锁 94 字段集合 + 「渲染键 == 字段集合」）；同输入产物**逐字节一致**（freeze 时间与缓存统计后对拍 `write_html_report` 产物 SHA：`8d4736b7…` 拆分前后相同，358,960 字节）；`unit/report` 2944 项全绿。
**额外收益**：模板变量拼错/漏传从「人眼核对 94 行」变成静态可查（字段存在性 + 装配处 grep 守卫）。

## `plan-252` ✅ 建议后验评估政策单源化 + 不动作类命中评估

**结果**：新增 `core/decision_eval_policy.py` 作「什么算命中」的唯一事实位（方向命中阈值 1.5%、不动作容忍带 2.0%、样本门槛 20、视界单位；零依赖，账本单向导入并保留原名导出）；不动作类（`DIRECTION_FLAT`，持有/观望/不操作）由 `classify_flat_hit` 判对/判偏/不可判，结算落 `flat_hit`（旧账本无字段按未判、不回填），折叠汇总新增 `flat` 分项，报告判断依据块与 `doctor` 并列呈现不动作命中率。
**不做**：未改方向性阈值与样本门槛、未做置信度加权、不进 `plan-70` 转正判据。
**设计**：[`decision-eval-policy-design.md`](../plan/decision-eval-policy-design.md)。

## `plan-253` ✅ LLM 复盘结论结构化契约（claim / evidence / verdict）

**结果**：新增开关 `llm_research_contract`（默认关，关时逐字节不变）——P1 由模块提示词输入块生成内容寻址 `evidence_id` 池并追加结构头（主张/证据/推论/失效条件/判决）；P2 埋点进「LLM API 用量」页签（判决分布与 `evidence_needed` 占比）；P3 判决枚举 + 建议硬约束（review/blocked 不带数量、限购品种带执行约束）与「决策书」并入行动建议章 LLM 解读位（`report/decision_book.py`，不新增章节/页签）。
**暂缓**：P2 补证循环按门槛暂缓，裁决归 `plan-255`（观察期 ≥2 周后用用量页签读数判定）。
**设计**：[`llm-research-contract-design.md`](../plan/llm-research-contract-design.md)。

## `plan-265` ✅ 守护项价值复核（零命中项降频）

**结果**：`_shared/checklib.report()` 每次运行追加一行命中台账（脚本级 + 可选「子项 → finding 数」），`check-doc-drift` 通过给模块内 `check_*` 函数套计数壳提供子项粒度（不改调用点）；新增 `scripts/probe-guard-hits.py` 输出「守护项 × 运行次数 × 命中次数 × 处置」表，处置三态为「保留 / 建议降频（CI 恒跑兜底）/ 样本不足」。
**边界**：本项只提供读数与建议，**不改任何守护的启用状态与 CI 阻塞语义**；降频动作需人工复核后落 `scripts-reference.md`。
**样本**：台账从本版开始积累，首次有意义的复核门槛是每项 ≥5 次运行（`--min-runs`）。
**守卫**：`test_probe_guard_hits.py`（9 条：聚合/处置判据/损坏行容错/表格与 CLI 退出码）+ `test_checklib_guard_ledger.py`（4 条：记录形态/默认 details/写入失败静默/report 退出码不受影响）。

## `plan-264` ✅ 缓存命中率提升（同事实单键）

**归因**：本轮未命中数居首的是 `fin_indicator`（42 次）——同一 A 股 code 在同一轮里被两条路径各取一次：`report/financial_indicator.py` 取多期序列（键 `fin_indicator_hist_{code}`），基金 ROE 估算与因子目录探测取单期（键 `fin_indicator_{code}`）。两种键并存且互不复用，故每轮每 code 多一次回源。`price_stock` 未命中属正常（行情每次都要最新）。
**动作**：`fetch_latest_indicator` 先读多期缓存：命中即返回头部记录（多期按报告期降序，头部即最新一期），仅未命中时才走链路取数。未改 TTL——财务指标按报告期发布虽可延长 TTL，但会牵动新鲜度/陈旧判定口径，收益小于风险，留作后续按需评估。
**效果**：同一 code 的单期取数由「必回源」降为「多期已取则不回源」（守卫用例以「多期缓存命中时不得调用链路」断言）。
**守卫**：`test_financial_indicator.py::TestSingleFetchReusesSeriesCache`（命中不回源 / 未命中回落链路 / 非 A 股不读缓存）。

## `plan-263` ✅ 本轮降级清单汇总出口

**结果**：新增 `core/degradation.report_degradation_summary(max_items=3)`——按「源 + 失败类型」去重计数本轮 `degraded` 事件（`begin_report()` 已把事件日志限定在本轮，故不另算一套轮次边界），输出 `{count, events, lines, text}`；`_RenderContext.degradation_line` 经模板 `summary_section.html` 在数据状态块尾输出一行（无降级 → 空串 → 该行不渲染，产物逐字节不变），CLI 产物清单尾部同源追加同一行。
**边界**：正文只列前 `max_items` 项，其余以「等 N 项」概括；`count` 为去重项数、`events` 为原始事件数，两者都给出（验收要求的「计数与事件数一致」由此可核）。
**未做**：TUI 收尾未单独加行——TUI 走同一报告渲染器与完成通知，显式打印项留待 TUI 文案批次统一处理（避免单渠道措辞漂移）。
**守卫**：`test_degradation_report_summary.py` 10 条（口径/排序/溢出/读取失败降级/渲染上下文透传/模板条件块/CLI 空与非空两态）。

## `plan-261` ✅ 零直测模块补测（高风险纯函数优先）

**结果**：按风险排序的两批共 5 个模块补齐直测——① `config/_json_patch`（`test_json_patch.py` 34 条 + `_edge.py` 10 条，期间修 `rf-1159`/`rf-1160`/`rf-1161` 三个写回缺陷）；② `analysis/_fee_estimation`（18 条）、`analysis/metrics_risk`（29 条）、`config/_feature_registry`（15 条，只断言结构关系不写死开关条数）、`providers/_news_dedup_tables`（7 条词表不变量 + 判定语义）。
**残余**：剩余模块经模块名检索未命中，但行为由门面用例覆盖（如 `analysis/prosperity_scoring` 经 `prosperity_framework` 用例、`llm/_hallucination_filter` 经辩论用例）；这批不单独立项，后续改动扫到的模块就地补测。

## `plan-260` ✅ 实验项转正判据自动裁决 + 到期提醒

**结果**：新增 `core/experiment_verdicts.py`——项清单由注册表 `experimental_flags()` 派生，逐项把判据收成表（`report_qa` 取 `qa/telemetry.py` 的判据条目，`decision_reflection` 取账本折叠的方向性样本量与超额符号），输出「可转正 / 继续观察 / 撤销候选 / 无读数」四态；`doctor` 新增「实验项裁决」行（判据名 + 实测值 + 结论）与「已达判据 → 请按计划裁决」提醒行。不改开关、不摘 `experimental`（转正/撤销仍人工）。
**边界**：注册表 `experimental=True` 的项共 2 项（`decision_reflection` / `report_qa`）——`signal_ledger` / `prosperity_framework` / `llm_research_contract` / `rebalance_schedule_replay` 是默关闭的功能开关、不属实验生命周期，其判据仍走各自计划条目；未接读数适配器的实验项明说「判据未接读数源」。
**未达项**：原定「达资格同时在报告运行日志出提醒」改为只在 `doctor` 上屏——`doctor` 在启动早期可能先于日志系统建立运行，从那里打 warning 会污染命令行输出（转正提醒属周期性人工核对，无需哏时）。
**守卫**：`test_experiment_verdicts.py` 13 条（项集合与注册表派生相等、四态判定、撤销优先于观察、无读数不臆造、doctor 行接线）。

## `plan-262` ✅ 新闻去重近线性化（标题 blocking 前置）

**结果**：`_dedup_by_title` 的比较范围由两层候选索引给出——实体 bigram → 已保留下标（所有合并规则都要求 overlap ≥ 1）；标题 `_SUBSTRING_MIN_LEN` 窗口 → 已保留下标（「短串 ⊂ 长串」必共享窗口）。两层均未命中的对不进入比较；判定结果逐条一致（保留集合标题序列 SHA 对拍相同，首个命中对下标升序不变）。锚点语料收录范围为实体重叠 ≥ 1 的对（零重叠对恒不合并）。
**实测**（合成语料 1275 条 → 保留 768 条，不依赖网络）：比较对 69,712 → 38,524（−45%），耗时 3.18s → 1.13s（2.8×）；生产语料（单对成本更低、零重叠对占比更高）受益面不小于此值。
**未达项**：原定「降一个量级」未达成——profile 显示剩余成本集中在候选对的**双向** `SequenceMatcher`（占约 70%），而两条看似可行的后续路径实测均无效：①「仅窗口命中、无共享 bigram 的候选跳过重叠计算」收益为 0（24,414 次 ratio 调用中这类候选的重叠交集本身只需亚微秒级），已回退不加该分支；②「单向 ratio 达标即跳过反向」仅 0.05%（11/24,414）能命中（绝大多数对落在 0.375~0.50 档，反向值会跨档、改动判定）。因此进一步加速必须先改判定口径（阈值/比较粒度），属口径变更，不在本项范围。
**守卫**：`test_news_dedup_perf.py::TestEntityFirstGate`（零重叠对不做重叠/相似度计算、与基线对照逐条一致、子串路径不被连带跳过）。
