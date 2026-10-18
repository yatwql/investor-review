# 计划归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布后开发期完成项并入，0.13 系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.13.x 开发期完成项
> 归档内容：由各任务完成后人工迁入

---

## plan-140 辩论三模块双重映射消除（缓存依赖改挂）✅

深层重构完成：辩论白脸/黑脸/综合三段从 LLM 模块注册表（`_MODULE_REGISTRY`）**移出**，迁入注册表外常量 `_CACHE_ONLY_REGISTRY`（`core/data_registry.py`，`settings_suffix` 为空=不进 enabled_llm/llm_settings 键域），新增 `get_cache_registry()` 返回「常规 + 缓存专属」并集供**缓存引擎**消费——`get_cache_ttl_defaults` / `get_prefix_type_map` / `get_exact_type_map` / `get_registered_data_types` 与 `cache/_groups.clear_by_group` 五个缓存侧消费点全部改走该访问器（`get_registry()` 保持「模块清单」语义不变）；缓存 key（`llm_debate_pro_` 等）、TTL 24h、preload 组归属**完全不变**，磁盘既有同名缓存持续被识别与清理，故无需兼容窗口。隐藏层整体删除：`data_registry.LLM_HIDDEN_KEYS` + `visible_llm_module_names()`、`tui_menu.LLM_MENU_HIDDEN_KEYS`（`filter_menu_llm_modules` 收敛为恒等门面保留调用面）、Web surface 的 `llm.hidden_modules` 载荷；五个消费点（`config/edit_ops` 白名单派生、`core/system_info` 模型路由、`llm/cost_forecast` 计划模块、`web/config_edit` surface）统一改 `get_llm_module_names()`——双重映射彻底消失，运行开关单点收敛为 features 的 `llm_debate_procon`/`llm_debate_conditional`。测试：`test_tui_menu` 两例语义改写（恒等门面 + 「模块清单不含辩论 / 缓存域登记且含三段」双向断言），`test_registry` 新增 `TestCacheOnlyDebateRegistry` 3 例（三张缓存表覆盖三段 + TTL=24h + 前缀自映射 / 缓存域=注册表∪缓存专属且常规项无重复 / 缓存专属项非 LLM 类型），`test_cache_cleanup` 新增 preload 组清除三段缓存回归例，`test_edit_ops`/`test_system_info`/`test_cost_forecast` 改真值来源，`test_tui_menu` 位序断言改造为 `index_by_key` 结构相对位（E 首 / X 末 / W 紧跟 L）并去掉写死条数（19→键集合），`test_handlers.TestSystemInfo` 去掉辩论键 mock 注入。定向：core+config+web+ui+llm 相关 2116 passed。文档：technical 菜单表/白名单段（顺带修正陈旧数字 **48→44 条键、功能开关 31→27** 与四组分解 1/16/5/5）/缓存统计表标签/两处辩论路由段（注册表→缓存专属登记）/语义表新增 `get_cache_registry` 行、how-to-config 与 web-mode 隐藏项说明改写、tui-menu 缓存节、main.js 前端提示改写。

## plan-139 缓存管理子菜单（[3]+[4] 合并动线）✅

按计划二选一「原快捷键保留其一作入口」落地——保留 `[4]` 作**缓存管理（统计与清理）**子菜单入口（与状态行 `〔详情 [4][H][S]〕` 既有指引一致，零状态行改动），原 `[3]` 清理收敛为子菜单内命令。实现：`handlers_cache` 统计体拆 `_render_cache_stats`（首屏只读、去掉尾部按键等待、过期行改「输入 3 可清理」）+ `_cmd_cache_management` 命令循环（首屏统计一次 → `3` 清理并回统计刷新 / `B`·回车·`0` 返回 / 未知行内提示不重刷统计）；`tui_menu.MENU_ITEMS` 删 `[3]` 元组、`[4]` 改标签（标签头「缓存管理」）；`tui._bind_callbacks` 改绑 `_cmd_cache_management`。测试：`test_tui_routing` 键集去 3 + 新增 4 路由用例，doc-drift 括号豁免用例改挂 `[4]`（原挂 3 会静默失义），`TestCacheManagementSubmenu` 3 例（统计-清理-刷新闭环 stats=2 / 未知命令不清理 stats=1 / 回车直返），60 passed。文档 8 触点：双手册菜单块（含 how-to-start 两列样例重排）、tui-menu 缓存节合并重写、faq 7 处、datasource-reliability、how-to-config、Web 模式 `[3][4]`→`[4]`、requirements 菜单表与 R-CCH-33、technical 两行；残留扫描 0。

## plan-138 LLM 模块区历史费用显示✅

①核实为既有能力——`record_per_module` 调用点齐全（api_base 调用链/skeleton/generators_news/orchestrator 缓存命中），session per_module → `_report_generation` 建 `context["modules"]` → perf `llm.modules`，本次新增的是**归集读取**（真正支撑逐模块累计的读取端）：`perf.module_cost_summary(days=7, path=None)` 按窗口过滤 timestamp 并汇总 total/runs/avg，损坏行/缺 llm 块/非数值 cost 均容错；②`[S]` LLM 模块行尾附「· 近7日 ¥X（N 次 · 均 ¥Y）」，无样本模块不带摘要，读取异常 logger.debug + 静默省略（面板照常渲染）；③口径对齐——helper 与事前费用预估（cost_forecast 读同一 `llm.modules.*.cost`）、日预算（同记录 `llm.total_cost`）同记录同字段同 `compute_cost_value` 单价数学，模块费用为总额子集，三处数字不打架（helper docstring 与手册双写）。测试：`TestModuleCostHistory` 3 例（窗口内归集/空文件/窗口过滤）+ `TestLlmRowCostSuffix` 3 例（行尾摘要/异常静默/未打桩走真实数据），perf 241 + handlers 72 全绿。手册 [S] 费用摘要说明；顺带修正 handlers 注释陈旧编号（标准 LLM 模块 1-5 → 1-7）。

## plan-137 持仓变动复盘双入口标注（面板混淆点）✅

按优先项「只读标注（零行为变化）」落地，二选一取 A——`handlers_config` 新增展示层常量 `_DUAL_ENTRY_CROSS_HINTS`（holding_change → 「· 章本体在「独立组」」、holding_change_review → 「· 归因在「LLM 区」」），两渲染环行尾各查一次挂提示；清单仍由注册表派生（标注不入注册表、不动编号派发、不改 Web）。廉价联动（B 项条件告示）不采用，避免展示层引入状态判定。新增 `TestDualEntryCrossHints` 2 例（互指两行且仅两行携带、纯只读不触发 save）——夹具补 holding_change 模块（共享五模块夹具不含归因模块）；handlers_config 41/41 绿。手册 [S] 补双入口解耦说明段。

## plan-136 实验项生命周期表（technical 单一事实）✅

technical.md 新增 §6.9「实验项生命周期表」（功能语义命名表邻域，TOC 同步）——七列结构（flag/实验目的/判据来源/转正条件/撤销条件/观察数据源/当前态）覆盖当前全部 2 个 ⚗ 实验项：`decision_reflection`（死线条目维护判据①②，表收「已结算≥10 可信 / 启用停止增长或样本<10 无趋势即撤销」三元组）与 `report_qa`（归档评估记录固化判据④⑤与执行清单，表收「样本充分+留痕可抽检+费用接入 perf 才转正」三元组）。详文不复制、双向回链防口径漂移：plan-70 条目与归档 plan-131 记录各补「单一事实位」链接指向 §6.9；纪律入表头——立项（新增 experimental=True）/转正（摘 experimental）/撤销（删条目与机制）任一发生必须同步刷新本表。doc-links（死锚/序列）与 doc-drift 全绿。

## plan-135 S 面板操作增强（批量恢复默认 / 实验项一键全关 / slug 切换）✅

三项写路径增强落地（编号派发与 Web 面板派生零改动）——①批量恢复默认：新原语 `features.clear_feature_overrides(flags|None)`（恢复默认=删除 features.json 覆写键而非写入同值，批量原子写走 save 同一 write_json_atomic，运行时经 _FEATURES_FLAGS 锁回 `_FEATURE_FLAGS_DEFAULT`、None 时顺带清掉无消费者残留键），面板 `r 编号或slug`（按注册表派生该条目所在分组键集）/ `ra`（全部）上屏实际移除键数；②实验项一键全关 `x`：experimental 集合回默认并删覆写，回到无实验态做 bisect；③slug 双通道：裸 slug 与编号等价切换、`slug=on|off` 走 CLI `parse_switch_override` 同一解析器与词表（旧键别名过渡一致，LLM 模块用同词表常量本地校验）、`? slug` 查详情（`_match_switch_item` 辅助定位）。LLM 条目拒绝 `r`（恢复默认仅限功能开关分组）。新增 10 单测（`TestSwitchPanelOperations`，monkeypatch FEATURES_FILE 到临时文件 + 种子载入同源），handlers_config 39/39 绿；手册 [S] 新增写路径三通道段并顺带修复 [P] 报告章节与增强清单（并两财务项、补景气度、默认开清单补景气度）。

## plan-134 财报基本面两开关合并（个股基本面单一开关）✅

两开关合并为单一 `stock_fundamentals`（「个股基本面」，默认关，独立章节与回放组）——①单开关控持仓基本面两块：`is_enable_financial_indicator`/`is_enable_financial_report_digest` 收敛为 `is_enable_stock_fundamentals`（_report_generation 两处 `or` 门控与 orchestrator 两个 compute 门改读同键）；章级细分不另设子开关，由既有报告章节配置承接（`fundamental_snapshot` 章整体显隐，`report_section_order` 不动）；②旧键一版过渡：`_migrate_merged_switch_keys` 在 load/save 双路径按并集迁移（任一旧键 True 即 True；新键并存时以新键为准；迁后旧键不入内存不落盘），`--feature` 旧键别名告警映射，本地 features.json 已迁（21 键）；③注册表/面板/Web 白名单/TUI 由注册表派生自动生效，面板 28→27 单次重排（独立 25-29 / 机制 30-34），测试改造（helpers/置位键/矩阵 note/模板指引断言/实验文案）+ 定向 305+235 绿，同步触点 12 份文档（矩阵/模板占位/4 手册/管理 5）；④不合并对照照案登记：`llm_debate_procon`×`llm_debate_conditional`（默认值与风格正交）、`market_temperature`×`market_sentiment`（跨章）保持现状。

## plan-133 机制类开关内置化评估（逃生分支清理）✅

逐项评估执行完毕，三开关全部内置化（删注册表条目 + 关态死分支）——证据：①parity 先行（`test_quote_adapter_parity` 七源等价 + 回退态强制回落用例改写后继续锁定两套映射；结构化头「整批不可用 → 表格兜底」等价锁；凭据预检在「全部数据源免费无需凭据」现状下两态同为直通）；②跨版本稳定期：2026-09-10 引入、09-11 转正默认开，历时月余、横跨 v0.12.12→v0.13.5 多个发布无回退提交；③本地真实 `features.json` 无关态覆写（残留旧键由「无消费者开关」告警提示清理）。落地：`datasource_adapter` 链路恒走适配器（适配器不可用回落既有映射的安全网与 doctor 自检保留）、`decision_header_parse` 提示词恒追加结构化决策头（`_dh` 指纹后缀常驻、解析双路与回落保留）、`datasource_credential_ready` 凭据预检恒执行（`check_sources`/`chain`/`chain_incremental`/`doctor`/`data_source_matrix` 六处闸门删净，doctor 凭据组恒产出）；面板 31→28 项（机制与诊断 8→5）单次重排，手册/requirements/technical（§2.5/§2.7 改内置标题、语义命名表重键、统计行按注册表动态重算）/developer-guide 转正判据同步；OFF 态专属用例随行为退役（-8 例），回归总量不降。不内置清单照案确认：关态有真实场景的七项保持现状，`deterministic_signal`/`prosperity_framework` 观察期未过不评，`module_quality_gate` 弱候选暂缓。

## plan-132 S 面板信息增强（说明查看 / 非默认标记 / 实验统计上屏）✅

三项只读信息面落地——①`? 编号` 查看说明与当前值/出厂默认值/存储键（功能开关取注册表 `desc`，LLM 模块取 `enabled_llm` 键；`_show_switch_detail` 只读，不写配置不改编号派发）；②行尾 `*` 标记与出厂默认不一致项（LLM 模块按 `_DEFAULT_LLM_SETTINGS` 出厂值、功能开关按 `FeatureSwitchDef.default` 比对，页脚释义）；③⚗ 实验项行尾附 `experiment_stats` 启用统计（启用 N 次 · 最近 MM-DD，每轮渲染实时读取、读取失败静默省略）。手册 [S] 节同步，新增 6 单测。

## plan-131 report_qa 转正评估挂账（判据与执行清单） ✅

首轮评估执行并落定判据——①观察数据：`experiment_stats` 实测 report_qa 启用 5 次（最近 2026-10-13，对照 decision_reflection 51 次），非零启用 → 未触发撤销条件⑤，频次偏低 → 未满足转正条件④的「真实使用」充分样本；②质量抽检：`QaSession` 仅内存态不持久化，无历史问答样本可抽检 → 判据挂账保留（样本留痕为转正前置）；③成本实测：`QaSession.usage` 已有 token 口径（API 载荷带出）但未接费用口径、不入 perf 记录 → 费用留痕缺口同挂账；④转正清单（摘 experimental、入报告增强组并复核 `affects_report`、三端文档同步、`--experiment` 取值域收窄）与⑤撤销清单（注册表条目 + 页内区块摘除）固化为执行清单；结论：维持实验观察，判据与清单的长期单一事实位由「实验项生命周期表」承接（report_qa 行双向引用本条）。**单一事实位**：条件—数据—态结构化口径见 [technical §6.9 实验项生命周期表](../../managements/technical.md#69-实验项生命周期表)；转正/撤销执行时双方同步刷新。

## plan-99 LLM 运行事前无成本预估与预算上限 ✅

**完成（2026-10-18，v0.13.6-dev）**：`llm/cost_forecast.py` 事前费用预估——计划参与模块（`visible_llm_module_names()` ∩ `enabled_llm` ∩ `depth_gate` 档位收窄）× 生效模型单价（`model_<模块>` → 多链首链 → 顶层默认）给区间：perf 历史逐模块实际费用优先（最近 30 次运行，辩论特征开启时标准样本 ×3、辩论三键并入 expert_review 口径）、无历史回落静态 token 包络（8K~48K 输入 × `max_tokens_<模块>` 输出）；全部无法定价 → `ok=False` **不阻塞**（渠道跳过确认）。日预算 `llm_settings.json → daily_cost_limit`（默认 0=不启用），今日已花费 = perf 当日 `llm.total_cost` 汇总（与事后统计同源）；超限交互询问「降级走缓存继续 / 中止」（降级清空强刷范围），非交互硬闸：CLI `--yes`/`--non-interactive`/非 TTY 直接中止退出码 2，Web 创建 409 `BUDGET_EXCEEDED`（`budget_ack` 显式确认放行）+ `_run_generation_impl` 执行体兜底（定时调度/直连 API 同拦）。三渠道接线：TUI `_prompt_cost_forecast`（`[L]` full 前）、Web `GET /api/runs/cost-preflight` + `main.js` 提交前弹层（预检失败放行）、CLI `_confirm_cost_forecast` + `--yes`。计费数学抽 `pricing.compute_cost_value()` 数值单源（`estimate_cost` 字符串契约不变）。需求登记 R-LLM-13；回归用例 `test_cost_forecast.py` / `test_cli_cost_forecast.py` / `test_cost_forecast_flow.py` / `test_handlers_report.py::TestPromptCostForecast|TestCmdGenerateFullForecastWiring`。

## plan-129 LLM 费用无跨运行趋势视图 ✅

**完成（2026-10-18，v0.13.6-dev）**：perf-view `--by day|week|hour` 时段聚合表在耗时列外新增**费用合计/费用环比**列（数据源既有 `llm.total_cost`，零新增；时段键升序即时间序；首档环比为 —、末档附「费用环比（末档 vs 前档）」提示行；范围内无费用样本自动省列）；`--json` 汇总新增 `llm_cost` 费用块（runs/total/mean/median/max，沿用既有均值/中位/极值 helper，无样本为 null）与 `--by` 时的 `by_period` 时段费用序列（bucket 升序可直接相邻差分，未传 `--by` 为 null）；CSV 列不变。回归用例 `test_perf_view.py::TestBucketCostAggregation / TestLlmCostMachineData`（9 例）。

## plan-130 应用内定时生成（免外部任务计划） ✅

**完成（2026-10-18，v0.13.6-dev）**：Web 工作台配置页签新增「定时生成」调度面板（执行日/时刻/报告类型/启用开关），保存写入 `config.json` 的 `scheduler` 块（缺省关闭；`_DEFAULT_CONFIG`/配置模板/`how-to-config.md` 字段总表同步）；服务端新增 `web/scheduler.py` daemon 调度线程每 30s 重读配置评估触发窗（宽限 30 分钟内顺延活动任务、超时登记错过），触发即向 RunManager 提交「正式-用存量」生成——与手动生成同队列同 worker 串行，复用生成入口自动清理与完成链路；触发账本按「计划签名+日期」原子写 `data/state/scheduler_fired.json`（损坏兜底 + `_path_isolation` 重定向）；`GET/POST /api/scheduler`（校验 400 / 同源守卫 403 / 写失败 500）；服务器/容器场景的 CLI cron 替代方案见 Web 手册 §5.4。回归用例：`src/test/unit/web/test_scheduler.py`（解析/触发窗/账本/API/面板接线 + 前端源结构断言），需求登记 R-WEB-12。

## plan-127 HTML 报告无打印/PDF 导出入口 ✅

**完成（2026-10-18，v0.13.6-dev）**：报告右上角新增浮动「打印 / 导出 PDF」按钮（`report-print-btn`，主题切换 🌙 左侧，44×44 触控目标、`--primary`/`--primary-hover` 语义 token、`window.print()` 唤起浏览器打印/另存 PDF），打印稿经独立 `@media print` 规则自隐藏（不动既有浮动控件隐藏清单）；补模板结构/可访问性/触控尺寸/打印自隐藏回归用例（`test_html_template.py::TestHtmlPrintButton`），`reports-instruction.md` 交互功能清单同步入口说明。

## plan-126 性能对比、机读输出与阈值门禁 ✅

**完成（2026-10-15，v0.13.4-dev）**：`perf-view.py` 获得 `--compare A B`（阶段级中位 delta/倍数 + 变异系数判显著，噪声带内不判回归）、`--json`/`--csv` 机读输出、`--gate` 阈值判定（退出码 0/2）。**门禁归属修正**：CI `perf-gate` 门禁由主动压测 `perf-test-report.py --gate` 承担（同条件可比），历史视图不做门禁——样本不可控、不可复现、测环境不测代码。后续增强：`--json` 升级信封 `{record_count, records, summary}`（与 Markdown 各段同源）、CSV 增归一/离群/最慢阶段列。

**落地设计**：[`perf-observability-design.md`](perf-observability-design.md) §9（门禁归属决策）· §10（输出增强）——设计文档已随 v0.13.4 发布归档于本目录。

## plan-125 运行上下文维度采集（provider/缓存/等待/用量） ✅

**完成（2026-10-15，v0.13.4-dev）**：`perf_history.jsonl` 记录增 `llm` 字段（provider/model/thinking 档、重试与退避等待秒数、端点节流等待、provider 降级、模块级缓存命中、逐模块 tokens/费用）。`llm/observation.py` 汇聚器（`bind_llm_observation`/`current_llm_observation`，线程安全）在调用链归集：`core/retry.py` 退避观察点、`llm/pacing.py` 节流门、`llm/api.py` provider 链、编排层预检、`llm/session.py` 单源用量；未绑定时全链空操作。`perf-view.py` 增「LLM 运行上下文」段——直给「时间花在白等还是真推理」。

## plan-124 性能视图稳健统计与归因 ✅

**完成（2026-10-15，v0.13.4-dev）**：离群点标注（中位 + k × 1.4826 × MAD，`--outlier-k` 可调）与 `--exclude-outlier` 稳健口径、稳健均值（仅存在离群点时与普通均值并列）；阶段级 P50/P95/P99；尾部归因（最慢一次运行逐阶段 z 分数直给「哪步超常、超多少倍」）；`--by day|week|hour` 时段聚合。

## plan-123 运行观测打点补齐（LLM 模块级细分 + full 埋点补回 + 诊断落盘） ✅

**完成（2026-10-15，v0.13.4-dev）**：`core/perf.py` 增线程安全 `PhaseBreakdownRecorder`，快照带 `breakdown`/`counters`（**不参与 `total_seconds`**，保历史可比与 ETA 口径）；LLM 四模块与新闻获取逐子项耗时入 `breakdown["LLM+新闻"]`；full 路径 `_report_output.py` 两个 helper 补 HTML/Excel 阶段埋点；首个阶段计时时挂只计数日志 handler、`save()` 摘除，WARNING/ERROR 自动入 `warnings_count`/`errors`/`counters`（根因修复「诊断字段恒空」）；`perf-view.py` 增阶段细分表。

## plan-122 脚本目录优化批次（审计落地） ✅

**完成（2026-10-13）**：scripts 全目录审计（67 文件/16,397 行）后六项优化全部落地：

1. **release.py 拆 `_release/` 内部实现包**（869→517 行，距 1000 行红线余量充足）：`_common`（ReleaseError / 子进程执行原语）、`_versioning`（版本号解析/渲染纯函数 + 归档名派生）、`_changelog_archive`（发布段迁出与归档追加，纯文本变换）、`_evolution`（演进快照统计与表格回写）。入口保留 CLI 面、命令壳与路径常量——下沉模块只收显式参数，测试对入口模块属性的重定向始终生效；测试引用的符号（`_SECTION_NOTE`/`_line_count` 等）经原名 re-export 保持可达。
2. **文档路径常量上收 `_checklib`**（`MANAGEMENTS_DIR`/`MANUALS_DIR`/`PLAN_DOCS_DIR`/`ARCHIVE_DOCS_DIR`）：check-doc-traces / check-version-consistency（13 处）/ check-requirement-trace / check-semantic-index / check-task-numbering 与 `_doc_drift` 内部包的内联拼路径收编；各脚本的受检清单与豁免策略仍归各自持有。
3. **契约规则② 消费侧盲区封堵**：`check-script-contract` 增加 `args.verbose` 被消费的 AST 检查（防空开关）；`check-svg.py` 空 -v 实现消费（geom 逐文件 finding 计数、pixel/text 检查参数回显）。
4. **同次运行双扫消除**：check-doc-traces 受检文档两态列表一次构造复用（四遍 rglob → 一遍）；check-doc-drift `-v` 模式扫描结果复用首轮（二次全量读消除）；check-semantic-index 指纹输入面与 run_checks 扫描面同源（双 rglob 收敛）。
5. **演进统计二次读消除**：`build_evolution_stats` 首轮读文件时顺带累计 `def test_` 计数，测试文件全量二次读删除。
6. **sh 启动垫片加固**：cli.sh / launch.sh / llm.sh 加 `set -euo pipefail`。

**验收**：`check-script-contract -v` 全绿（15 顶层脚本）；守护五脚本（doc-traces/version-consistency/requirement-trace/semantic-index/task-numbering）冒烟全绿；`test_release_tool.py` 56 例 + 守护测试全绿；ruff 零告警。

**审计同时确认的不建议动项**（风险 > 收益，留档备查）：钩子脚本接入 `_checklib`（无 CLI 面，退出码语义不同）、sys.path 样板（1 行鸡生蛋解）、各脚本表格行解析上收（行级正则列语义各异）、分级退出码归一（动门禁语义）、`_checklib` 结论缓存重构（stat 指纹成本近零）、check-doc-traces 与两个 ~560 行文件拆分（离红线远，拆包只换行数不换复杂度）。

---

## plan-90 持仓成本相对历史价格区间位置 ✅

**完成（2026-10-14，v0.13.2）**：复用既有行情缓存补齐「只维护持仓、无交易流水」下 `每份成本` 相对历史价格区间的量化呈现（高位≈追涨 / 低位≈布局），填补此前只能逐格读数人工判断的空白。指标 `cost_position_pct = clamp((每份成本 − 窗口最低价)/(窗口最高 − 窗口最低), 0, 1)`，近 20 交易日 / 260 交易日（≈52 周）双窗口；`high==low`（停牌/极窄波动）取 0.5 中性值，成本越界 clamp。

**落地**（不新增报告章节，在「持仓明细与分类」页签两区块末列追加条件列）：

- 纯计算 `src/python/analysis/cost_position.py`（clamp / 中性值 / 窗口切片，无 I/O）
- 编排 `src/python/report/cost_position.py`（复用 `PortfolioHistoryCalculator.calculate_for_holding`，长窗口一次取数 + 短窗口同源切片；行情缺失静默隐列不阻断报告）
- 功能开关 `cost_position`（`GROUP_ANALYSIS`，默认开，`affects_report`）；口径脚注随呈现（成本均价近似买入价 + 窗口参数 + 公式）
- Excel 条件列接线 `holdings_detail_sheet`（`_MV_COST_POS_HEADERS`/`_CAT_COST_POS_HEADERS`/`FMT_PERCENT`）；44 例测试（纯计算/契约/渲染 + 边缘退化/非有限值）

**落地设计**：`docs/archive/v0.13.x/holding-cost-position-design.md`（随本次归档迁入）

**自审去重（rf-685）**：`extract_closes` 收敛复用 `valuation_percentile.extract_closes` 共享单一事实来源，区间有效性过滤统一到 `compute_window_position`。
