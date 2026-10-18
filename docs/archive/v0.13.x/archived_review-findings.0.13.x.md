# 自审记录归档 — v0.13.x

> 归档时间：2026-10-18（v0.13.6 发布，第五批开发期已修复批次追加；前批 2026-10-17 v0.13.5、2026-10-16 v0.13.4、2026-10-15 v0.13.3、首批 2026-10-14 v0.13.2）
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.13.x 开发期已修复项（v0.13.1 → v0.13.6）
> 归档内容：由各版本发布时人工迁入

---

## 开发期已修复（0.13.2-dev）

> 完整复盘见 `changelog.md` 0.13.2-dev 段；此处仅摘要行。

- rf-680 已修复（2026-10-14）：technical.md §1.6.3 TUI 菜单体系与实现对齐（含 TUI 手册同步）
- rf-681 已修复（2026-10-14）：technical.md §1.7/§1.8 与 Web/CLI 手册的路由、配置面板、LLM 章节对齐
- rf-682 已修复（2026-10-14）：`scripts/launch.sh` 无参启动 unbound variable 崩溃（默认展开修复 + 4 回归用例）
- rf-683 已修复（2026-10-14）：`launch.sh` 死代码 `$?` 清理 + `test_shell_contract.py` 静态机检，封堵 shell 行为门禁盲区（含豁免集遇 shift 清空的漏报精度补丁）
- rf-684 已修复（2026-10-14）：`check-test-redundancy.py` 完全重复比对三档绑定解析，根治 62 例跳过盲区
- rf-685 已修复（2026-10-14）：`cost_position` 收盘价提取消除同名二次实现——复用 `valuation_percentile.extract_closes` 共享单一事实来源，区间有效性过滤收敛至 `compute_window_position`

## 开发期已修复（0.13.3-dev）

> 完整复盘见 `changelog.md` 0.13.3-dev 段；此处仅摘要行。

- rf-686 已修复（2026-10-15）：release 编排 `prepare`/`evolution` 改文档后未同步 folders.md 统计表，导致 refresh 的 bench 因 crosscheck 过期红而重跑整套——两步各补收尾 `check-doc-drift --sync`，从源头消除发布期重复 bench
- rf-687 已修复（2026-10-15）：LLM provider 故障切换迟滞（read 超时被服务端滴流骗过挂足 900s + 错误信封误判安全网对死端点无效重试，最坏 15~30 分钟才切备用）——新增 `post_with_deadline` 墙钟原语 + 信封标志让安全网只对服务端正常返回的空响应触发

## 开发期已修复（0.13.4-dev）

> 完整复盘见 `changelog.md` 0.13.4-dev 段；此处仅摘要行。

- rf-688 已修复（2026-10-16）：`scripts/perf-view.py` 行数破线豁免——拆分 `_perf_view/` 子包（stats 纯函数先行）后主文件回落 1000 行红线内，`check-file-length.py` 的 `EXEMPTIONS` 豁免登记与 P3 挂账行同步移除

## 开发期已修复（0.13.5-dev）

> 完整复盘见 `changelog.md` 0.13.5 段；此处仅摘要行。

- rf-689 已修复（2026-10-16）：发布归档迁移改动后便宜守护未跑 `check-doc-traces` 即进 gate，P2 门禁因文档级 finding 双跑全量 regression——developer-guide 发布流程段已补「进 gate 前必跑便宜守护」分层纪律。
- rf-690 已修复（2026-10-16）：run 完成后「生成报告」按钮停在「生成中...」禁用态、无法再次/换格式生成（rf-257 真机 basic 实测揭示）——`pollOnce` 完成分支只移除 `aria-busy`、未复位文案与禁用态、未清已消费 `file_id`；完成分支与 `resetFlow` 共用 `restoreGenerateBtn()` 单源复位（清 `state.fileId` → `updateGenerateBtn()` → 文案还原 +「请重新上传」提示，正式-用存量免上传立即可再生成），新增 `test_web_generate_flow.py` 3 个源结构回归用例；真机复测并入 rf-257 收尾确认。
- rf-691 已修复（2026-10-17）：盘前/盘后「价格缓存新鲜度门禁」只比 `price_date`，把 T 日盘中写入的场内缓存（如 10-15 13:01 的盘中价 29.35）当作 T 日收盘价（真实 29.60）沿用——「本日盈亏」与「快照环比」因此系统性偏离（实例：2026-10-17 03:56 报告两值差 −277.71 中 −835.00 来自 4 只 A 股/ETF 基线取到盘中价）。`_price_cache_fresh` 增加收盘时点校验（T 日已收盘时要求缓存写入时刻 ≥ T 日 15:00，午间休市不施加），report `CACHE_ONLY` 分支与 `_fetch_price_with_cache_refresh` 两处传 `cache_key`；刷新失败退回刷新前的过时缓存避免丢数据；新增 `test_fetcher_price.py` 8 个回归用例。
- rf-692 已修复（2026-10-17）：full 路径 LLM 观测整段丢失——LLM 阶段结束的 `finally` 已 `bind_llm_observation(None)` 解绑全局 sink，收尾 `_record_llm_context(perf)` 仍从 `current_llm_observation()` 取，取到 None → 重试/节流等待/降级/缓存/thinking 全部未写入 perf 记录（只剩会话用量）。改为 `_record_llm_context(perf, sink)` 显式传入本次绑定的 sink，full 路径调用点传 `_llm_sink`；新增 `test_report_output_spans.py` 2 个回归用例（传入 sink 生效 + 结构锁定调用点）。
- rf-693 已修复（2026-10-17）：LLM 决策登记整批失效——结构化决策头（`decision_header_parse` 默认开）优先路产物仅 `{code, direction, magnitude}` 三字段，`register_llm_decisions` 直取 `row["detail"]` → `KeyError: 'detail'` 被实验挂载点守护吞成告警（perf 运行明细「错误 1」即此），当批 LLM 操作建议不入决策账本。按技术设计 §4.15「两路产物形状统一」在登记纪律统一入口 `_collect_decision` 回补 `detail` 空串（契约无理由列，账本 detail 缺省为空不阻结算）；修正 `parse_structured_header`「与表格解析同形状」误导 docstring；新增 2 个回归用例。
- rf-696 已修复（2026-10-17）：全仓测试语义审计初判「scenario 三子域约 22 用例静默漏出 P2 回归门禁」，复核实证为静态 AST 扫描未计入类装饰器沿基类 MRO 继承的佩戴（pytest 标记解析走继承链），六子目录 `-m scenario` 收集对拍命中=总数、零遗漏。真实薄弱点：裸 `scenario` 门禁佩戴全靠隐式继承、收集期无硬校验（缺标记警告只查「无任何自定义 marker」，只挂子域 marker 的新文件仍会静默漏出回归）。修复：conftest `pytest_collection_modifyitems` 增 scenario 目录×裸 `scenario` marker 双向收集期拦截（与 edge 隔离同范式；scenario_* 子域 marker 不受约束），新增 `test_conftest_scenario_gate.py` 5 个钩子直驱回归用例（违规拦截/合规放行/反斜杠路径归一/子域不豁免）；全仓 10,467 用例收集零报错。
- rf-694/rf-695 已处置（2026-10-17，与 rf-697 同批收口）：复核发现两类「目录↔域不互恰」实为 `check-test-markers.py` 期望表**已登记的刻意归域**（子集语义：`unit/handlers`/`unit/cache`→`unit_core`、`unit/startup`→`unit_ui`），非漂移；用户裁决 TUI/CLI 进 P1 后，「归域即进门禁」成为全局不变式（`verify` 选择器纳入 `unit_ui`/`unit_cli`，P1 实测 10,145 条），改域迁移方案废弃（改动面大且零门禁收益）。本批新增防回退机制：`TestP1GateCoversDeclaredDomains` 结构锁（期望表全部 unit_* 域必在 verify 内 + P0 域集 ⊆ P1）+ 期望表/conftest 缺标警告/`technical.md` §4.23 决策登记三处口径同源。
- rf-697 已修复（2026-10-17）：P1（`verify`）/P2（`regression`）/P0 预检均按 `unit` 通配或 `unit_*` 域集筛选，conftest 的 `pytest_configure` 曾漏注册 `unit`——10,136 条 unit 用例全部不在任何门禁收集范围（P0/P1 实跑数与 test-coverage 台账 6,969/9,800 吻合即为实证；`unit` 档单跑 10,136 为对照实证）。conftest 注册行补齐，域选择器与期望表经测试锁死同源；dev-verify 6,969→6,978、verify 9,800→10,145（P1 +345，≈+1s）。
- rf-697 登记待决（2026-10-17，rf-694 处置调研附带发现）：`verify`（P1 合入门禁）与 `dev-verify`（P0）选择器均不含 `unit_cli`（137 用例）与 `unit_ui`（187 用例）——若属「交互层不进快速门禁」的既定口径应在 testplan 显式登记；若非故意即 P1 覆盖缺口（典型：TUI/CLI 改动可绕 P1 入 master）。与 rf-694 同批定口径。
- rf-113 已修复（2026-10-16）：Iter 7 全链路浏览器人工验证六项全部完成——headless 自动化回归（① 6 图 badge / ② 2.4 afterprint / ③ 3.1 断网渲染 / ⑤ 375px 报告+调试页 / ⑥ 禁 Canvas 兜底，复跑 5 PASS + ⑥ 表现记录口径）+ 人工抽验（② 真实 Ctrl+P 打印预览、④ 微信真机 4.3+4.4、Safari 90+ iPad 抽验、Windows Chrome/Firefox；4.1 链接访问维护者豁免）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与证据见 `docs/plan/report-browser-verification.md`，勾选清单归档留存；rf-114 前置随之满足。
- rf-698 已处置（2026-10-17，用户裁决口径清理）：按「不再对旧配置项/旧缓存文件/旧数据结构做兼容」移除 5 处残留兼容分支——① `config/anonymizer.py` 的 `profit_rate_pct`「旧键兼容」注释修正（经核该键实为汇总取数/渲染的现役键，同步分支保留防残留原精度，仅删误导口径）；② `core/perf.py` `_phase_seconds` 早期 list 形状死分支（ETA 仅采样最近 20 条，旧形状自然出窗）；③ `fetcher/industry.py` 缓存载荷 schema 迁移清理链全删（函数 + 3 处调用，迁移窗口≤两周已过）；④ `datasource_credential._read_key_file` 顶层平铺回退（生产调用点恒传非空 section，旧单源文件形态失效）；⑤ `deepseek-chat`/`deepseek-reasoner` 停用别名全部兼容移除（价目两条目 + thinking 三名单；旧名历史费用改显 `-`、存量旧配置不再获思考安全网，均经用户确认）。手册与 `llm-technical.md` 价目/峰谷枚举/effort 名单同源刷新；别名价格锁改负向锁（锁定移除行为防回填）、删 3 个旧形状/旧载荷正测、凭据测试改写节结构；dev-verify 6,975 通过。
- rf-699 已处置（2026-10-17，设计契约审计）：全量 UI/报告样式人工比对 DESIGN.md，按基线对拍（契约落稿 commit a17b26f5 → HEAD）定位新增违规仅 3 行（均在 `summary_section.html`：市场温度两行内联 `#888` 裸色值 + QDII 注 `opacity:0.75` 档外），已修（→`var(--text-muted)`/0.7 档内，顺手消同模式存量 1 行）；护栏盲区增设 W3 内联色值/W4 档外字号/W5 档外间距三维观察（W1 引号整行豁免为 JS 图表配置设计、测试钉死不可收窄，W3 按位置级找回 HTML 内联色值盲区——原「裸色值 0」对内联域属假零），实测存量 40/8/175 入 `TestBaselineNoGrowth` 只减不增基线并入契约 Known Gaps；DESIGN.md 基线数字刷新（700 存量 3→9、600 25→63、工作台旧 `--color-*` 描述改角色名体系），`--color-*` 兼容映射到期删除（实测零消费者）并由 `TestLegacyMappingRemoved` 负向锁防回填；新增护栏测试 5 用例，unit_report/unit_web/scenario_basic 全绿。

## 开发期已修复（0.13.6-dev）

> 完整复盘见 `changelog.md` 0.13.6-dev 段；此处仅摘要行。

> rf-708 已修复（2026-10-18）：完成通知 Web 渠道接线——`_run_generation` 改薄包装器（委托 `_run_generation_impl` + `result_box` 回传产物标志），收尾经 `_notify_web_completion` 按 `notify` 配置门控派发（Web 手动生成 + 内置定时调度共用，无人值守定时失败不再静默）；降级摘要单源下沉 `report/data_status.degradation_summary()`，CLI `_collect_degradation_summary` 改委托
>
> rf-709 已修复（2026-10-18）：报告模板 tooltip XSS 纪律——`drawSimpleChart` hover 内容改 DOM API 构建（`createElement` + `textContent`/`createTextNode`，色点走 `style.backgroundColor` 属性赋值），全文 `innerHTML` 清零，模板源结构测试断言防回归
>
> rf-710 已修复（2026-10-18）：遥测 JSONL 保留上限——`jsonl_store` 追加原语增 `max_lines` 尾部保留参数（超限丢最旧行，原子写语义不变）；perf 历史 5000 行 / 健康检查历史 2000 行上限（账本/去重锚点等业务态文件不设，避免丢失跨会话状态）
> rf-712 已修复（2026-10-18）：`prosperity_framework` 转正后未迁组——作用域复核为行动章内嵌评分卡区块，注册表分组机制与诊断 → 分析增强（面板编号/手册分组表/文档归属随迁同步）；requirements R-PF-01 引用的已废弃 `GROUP_STANDARD` 常量改现行 `GROUP_ANALYSIS`，how-to-config 分组计数残留同步修正（详见 changelog）
> rf-713 已修复（2026-10-18）：technical.md「写入分派」段残留 `GROUP_REPORT` 分组名与「三组同一路径」过期表述——改写为「注册表四组同一路径」并删已废弃分组名（详见 changelog）
> rf-718 已修复（2026-10-18）：`[S]` 窄屏（手机）仍引导用户输入键名，而键名放不进行、打起来也费劲——改为**编号为主路径**、`k` 按需展开键名行，键名输入保留但不作引导（详见 changelog）
> rf-717 已修复（2026-10-18）：`[S]` 面板「开启/关闭」失去着色（重构排版时状态标签退化为纯文本，关闭项不再醒目标红）——恢复 GREEN/RED 着色（含窄档短标签），3 单测锁定（详见 changelog）
> rf-716 已修复（2026-10-18）：`[S]` 面板「键名」只出现在提示语里、用户无从得知（人机交互缺陷），且窄终端（手机 SSH）下 98 列面板被硬折——键名改为行内淡色列显式展示，排版抽 `tui/switch_panel.py` 做宽/中/窄三档响应式（附不越界不变式单测），另修编号两位数错位与页脚超宽（详见 changelog）
> rf-715 已修复（2026-10-18）：渠道层私引配置私有符号——`[S]` 只读详情与写路径三通道直引 `_DEFAULT_LLM_SETTINGS` / `_SWITCH_TRUE_TOKENS` / `_SWITCH_FALSE_TOKENS`（`test_channel_layering` 红）→ 新增公开面 `config.default_enabled_llm()` 与 `features.SWITCH_*_TOKENS` + `features.parse_switch_value()`，渠道改走公开 API（详见 changelog）
> rf-714 已修复（2026-10-18）：`[S]` 面板页脚/帮助/报错含开发者术语「slug」用户不可理解——用户可见文案统一改「键名」（与手册既有术语一致，提示行同步去 CLI 字样），源码级回归断言禁回潮（详见 changelog）
> rf-114 已修复（2026-10-18）：双渲染路径收敛——删除 Canvas `drawSimpleChart` 定义块与全部 Feature Flag 条件分支（主模板 + 5 个 partial），Chart.js 成唯一渲染器；`enable_interactive_charts` 开关随消费者消失一并摘除（面板 31 项、其后编号前移）；滚动超额与持仓重合度滚动相关两张 Canvas-only 存活图移植 Chart.js（`excess_rolling`/`corr_rolling` 数据集 + 初始化器，对齐与降级语义不变）；单渲染器结构回归锚点已补（详见 changelog）
>
> rf-706 已修复（2026-10-18）：Web 进度事件通道完整性——`pollOnce` 增在途互斥（pollBusy，成功/异常/同步抛三路复位）+ 按 `seq > lastSeq` 过滤重复回放；服务端 events 载荷补 `first_seq`（`RunState.oldest_seq`），前端缺口时渲染「中间已省略 N 条」占位行，不再静默跳号
>
> rf-707 已修复（2026-10-18）：Web 生成进度断点续传——活动 run 写 sessionStorage（提交成功/流程重置/轮询完成/任务失效四点闭环清理），页面加载 `resumeActiveRun()` 重建进度视图从 `after=0` 续轮询；run 已随服务重启消失时走既有任务不存在终态收口，不空转重试
>
> rf-704 已修复（2026-10-18）：过期缓存生成路径自动清理——`cache.auto_cleanup_expired()` 尽力而为包装（任何异常吞掉返回 0，绝不影响主流程），`report/orchestrator.generate_report` 入口调用（CLI/TUI/Web 三渠道共用入口）；无人值守 CLI 定时任务不再只增不减地堆积过期缓存
>
> rf-705 已修复（2026-10-18）：Web 进度轮询任务丢失终态——`main.js pollOnce` catch 识别 404/`NOT_FOUND` 为终态：停止轮询 + 复用 `restoreGenerateBtn()` 单源复位生成按钮 + 进度阶段落「任务已失效」+ 结果区渲染失败态提示刷新，不再被当瞬时错误无限重试；其余瞬时错误保持静默重试
>
> rf-702 已修复（2026-10-17）：LLM 计费口径统一——归一层把 claude 协议 `input_tokens` 补 `cache_read_input_tokens` 归一为总输入（兼容端点命中大于未命中不再产生负费用），`estimate_cost` 补 `max(…, 0)` 下限（详见 changelog）
>
> rf-703 已修复（2026-10-17）：会话/报告费用统计与单次估算口径统一——报告页脚、批处理汇总、新闻相关性估值均改走 `_normalize_usage_tokens` 归一层，会话累计费用与单次 `estimate_cost` 同参等值
>
> rf-701 已修复（2026-10-17）：openai 分支补读 DeepSeek 原生端点顶层 `prompt_cache_hit_tokens`（优先于 `prompt_tokens_details.cached_tokens`；详见 changelog）
>
> rf-700 已修复（2026-10-17）：LLM 模型定价表多处偏离官方现价——逐家官方定价页核实后统一修正，并同步 `llm-technical.md` 附录 B 与 `how-to-config-llm.md` 定价表（明细详见 changelog）
