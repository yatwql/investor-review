# 自审记录归档 — v0.13.x

> 归档时间：2026-10-21（v0.13.11 发布，第十批开发期已修复批次追加；此前 2026-10-20 v0.13.10 第九批、同批补录第八批 rf-740~751；前批 v0.13.9/v0.13.8 同日、2026-10-19 v0.13.7、2026-10-18 v0.13.6、2026-10-17 v0.13.5、2026-10-16 v0.13.4、2026-10-15 v0.13.3、首批 2026-10-14 v0.13.2）
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.13.x 开发期已修复项（v0.13.1 → v0.13.11）
> 归档内容：早期批次为人工摘要行；v0.13.12 起台账表格经 `release.py prepare` 整块搬运（无损）

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
- rf-113 已修复（2026-10-16）：Iter 7 全链路浏览器人工验证六项全部完成——headless 自动化回归（① 6 图 badge / ② 2.4 afterprint / ③ 3.1 断网渲染 / ⑤ 375px 报告+调试页 / ⑥ 禁 Canvas 兜底，复跑 5 PASS + ⑥ 表现记录口径）+ 人工抽验（② 真实 Ctrl+P 打印预览、④ 微信真机 4.3+4.4、Safari 90+ iPad 抽验、Windows Chrome/Firefox；4.1 链接访问维护者豁免）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与证据见 `docs/archive/v0.13.x/report-browser-verification/report-browser-verification.md`，勾选清单归档留存；rf-114 前置随之满足。
- rf-698 已处置（2026-10-17，用户裁决口径清理）：按「不对旧配置项/旧缓存文件/旧数据结构做兼容」移除 5 处残留兼容分支——① `config/anonymizer.py` 的 `profit_rate_pct`「旧键兼容」注释修正（经核该键实为汇总取数/渲染的现役键，同步分支保留防残留原精度，仅删误导口径）；② `core/perf.py` `_phase_seconds` 早期 list 形状死分支（ETA 仅采样最近 20 条，旧形状自然出窗）；③ `fetcher/industry.py` 缓存载荷 schema 迁移清理链全删（函数 + 3 处调用，迁移窗口≤两周已过）；④ `datasource_credential._read_key_file` 顶层平铺回退（生产调用点恒传非空 section，旧单源文件形态失效）；⑤ `deepseek-chat`/`deepseek-reasoner` 停用别名全部兼容移除（价目两条目 + thinking 三名单；旧名历史费用改显 `-`、存量旧配置不获思考安全网，均经用户确认）。手册与 `llm-technical.md` 价目/峰谷枚举/effort 名单同源刷新；别名价格锁改负向锁（锁定移除行为防回填）、删 3 个旧形状/旧载荷正测、凭据测试改写节结构；dev-verify 6,975 通过。
- rf-699 已处置（2026-10-17，设计契约审计）：全量 UI/报告样式人工比对 DESIGN.md，按基线对拍（契约落稿 commit a17b26f5 → HEAD）定位新增违规仅 3 行（均在 `summary_section.html`：市场温度两行内联 `#888` 裸色值 + QDII 注 `opacity:0.75` 档外），已修（→`var(--text-muted)`/0.7 档内，顺手消同模式存量 1 行）；护栏盲区增设 W3 内联色值/W4 档外字号/W5 档外间距三维观察（W1 引号整行豁免为 JS 图表配置设计、测试钉死不可收窄，W3 按位置级找回 HTML 内联色值盲区——原「裸色值 0」对内联域属假零），实测存量 40/8/175 入 `TestBaselineNoGrowth` 只减不增基线并入契约 Known Gaps；DESIGN.md 基线数字刷新（700 存量 3→9、600 25→63、工作台旧 `--color-*` 描述改角色名体系），`--color-*` 兼容映射到期删除（实测零消费者）并由 `TestLegacyMappingRemoved` 负向锁防回填；新增护栏测试 5 用例，unit_report/unit_web/scenario_basic 全绿。

## 开发期已修复（0.13.6-dev）

> 完整复盘见 `changelog.md` 0.13.6-dev 段；此处仅摘要行。

> rf-708 已修复（2026-10-18）：完成通知 Web 渠道接线——`_run_generation` 改薄包装器（委托 `_run_generation_impl` + `result_box` 回传产物标志），收尾经 `_notify_web_completion` 按 `notify` 配置门控派发（Web 手动生成 + 内置定时调度共用，无人值守定时失败不静默）；降级摘要单源下沉 `report/data_status.degradation_summary()`，CLI `_collect_degradation_summary` 改委托
>
> rf-709 已修复（2026-10-18）：报告模板 tooltip XSS 纪律——`drawSimpleChart` hover 内容改 DOM API 构建（`createElement` + `textContent`/`createTextNode`，色点走 `style.backgroundColor` 属性赋值），全文 `innerHTML` 清零，模板源结构测试断言防回归
>
> rf-710 已修复（2026-10-18）：遥测 JSONL 保留上限——`jsonl_store` 追加原语增 `max_lines` 尾部保留参数（超限丢最旧行，原子写语义不变）；perf 历史 5000 行 / 健康检查历史 2000 行上限（账本/去重锚点等业务态文件不设，避免丢失跨会话状态）
> rf-712 已修复（2026-10-18）：`prosperity_framework` 转正后未迁组——作用域复核为行动章内嵌评分卡区块，注册表分组机制与诊断 → 分析增强（面板编号/手册分组表/文档归属随迁同步）；requirements R-PF-01 引用的已废弃 `GROUP_STANDARD` 常量改现行 `GROUP_ANALYSIS`，how-to-config 分组计数残留同步修正（详见 changelog）
> rf-713 已修复（2026-10-18）：technical.md「写入分派」段残留 `GROUP_REPORT` 分组名与「三组同一路径」过期表述——改写为「注册表四组同一路径」并删已废弃分组名（详见 changelog）
> rf-718 已修复（2026-10-18）：`[S]` 窄屏（手机）仍引导用户输入键名，而键名放不进行、打起来也费劲——改为**编号为主路径**、`k` 按需展开键名行，键名输入保留但不作引导（详见 changelog）
> rf-717 已修复（2026-10-18）：`[S]` 面板「开启/关闭」失去着色（重构排版时状态标签退化为纯文本，关闭项不醒目标红）——恢复 GREEN/RED 着色（含窄档短标签），3 单测锁定（详见 changelog）
> rf-716 已修复（2026-10-18）：`[S]` 面板「键名」只出现在提示语里、用户无从得知（人机交互缺陷），且窄终端（手机 SSH）下 98 列面板被硬折——键名改为行内淡色列显式展示，排版抽 `tui/switch_panel.py` 做宽/中/窄三档响应式（附不越界不变式单测），另修编号两位数错位与页脚超宽（详见 changelog）
> rf-715 已修复（2026-10-18）：渠道层私引配置私有符号——`[S]` 只读详情与写路径三通道直引 `_DEFAULT_LLM_SETTINGS` / `_SWITCH_TRUE_TOKENS` / `_SWITCH_FALSE_TOKENS`（`test_channel_layering` 红）→ 新增公开面 `config.default_enabled_llm()` 与 `features.SWITCH_*_TOKENS` + `features.parse_switch_value()`，渠道改走公开 API（详见 changelog）
> rf-714 已修复（2026-10-18）：`[S]` 面板页脚/帮助/报错含开发者术语「slug」用户不可理解——用户可见文案统一改「键名」（与手册既有术语一致，提示行同步去 CLI 字样），源码级回归断言禁回潮（详见 changelog）
> rf-114 已修复（2026-10-18）：双渲染路径收敛——删除 Canvas `drawSimpleChart` 定义块与全部 Feature Flag 条件分支（主模板 + 5 个 partial），Chart.js 成唯一渲染器；`enable_interactive_charts` 开关随消费者消失一并摘除（面板 31 项、其后编号前移）；滚动超额与持仓重合度滚动相关两张 Canvas-only 存活图移植 Chart.js（`excess_rolling`/`corr_rolling` 数据集 + 初始化器，对齐与降级语义不变）；单渲染器结构回归锚点已补（详见 changelog）
>
> rf-706 已修复（2026-10-18）：Web 进度事件通道完整性——`pollOnce` 增在途互斥（pollBusy，成功/异常/同步抛三路复位）+ 按 `seq > lastSeq` 过滤重复回放；服务端 events 载荷补 `first_seq`（`RunState.oldest_seq`），前端缺口时渲染「中间已省略 N 条」占位行，不静默跳号
>
> rf-707 已修复（2026-10-18）：Web 生成进度断点续传——活动 run 写 sessionStorage（提交成功/流程重置/轮询完成/任务失效四点闭环清理），页面加载 `resumeActiveRun()` 重建进度视图从 `after=0` 续轮询；run 已随服务重启消失时走既有任务不存在终态收口，不空转重试
>
> rf-704 已修复（2026-10-18）：过期缓存生成路径自动清理——`cache.auto_cleanup_expired()` 尽力而为包装（任何异常吞掉返回 0，绝不影响主流程），`report/orchestrator.generate_report` 入口调用（CLI/TUI/Web 三渠道共用入口）；无人值守 CLI 定时任务不只增不减地堆积过期缓存
>
> rf-705 已修复（2026-10-18）：Web 进度轮询任务丢失终态——`main.js pollOnce` catch 识别 404/`NOT_FOUND` 为终态：停止轮询 + 复用 `restoreGenerateBtn()` 单源复位生成按钮 + 进度阶段落「任务已失效」+ 结果区渲染失败态提示刷新，不被当瞬时错误无限重试；其余瞬时错误保持静默重试
>
> rf-702 已修复（2026-10-17）：LLM 计费口径统一——归一层把 claude 协议 `input_tokens` 补 `cache_read_input_tokens` 归一为总输入（兼容端点命中大于未命中不产生负费用），`estimate_cost` 补 `max(…, 0)` 下限（详见 changelog）
>
> rf-703 已修复（2026-10-17）：会话/报告费用统计与单次估算口径统一——报告页脚、批处理汇总、新闻相关性估值均改走 `_normalize_usage_tokens` 归一层，会话累计费用与单次 `estimate_cost` 同参等值
>
> rf-701 已修复（2026-10-17）：openai 分支补读 DeepSeek 原生端点顶层 `prompt_cache_hit_tokens`（优先于 `prompt_tokens_details.cached_tokens`；详见 changelog）
>
> rf-700 已修复（2026-10-17）：LLM 模型定价表多处偏离官方现价——逐家官方定价页核实后统一修正，并同步 `llm-technical.md` 附录 B 与 `how-to-config-llm.md` 定价表（明细详见 changelog）

## 开发期已修复（0.13.7-dev）

> > 完整复盘见 `changelog.md` 0.13.7-dev 段；此处仅摘要行。
>
> rf-719 已修复（2026-10-18）：用户文档残留不存在的交互图表开关 `enable_interactive_charts` 与静态回退描述（FAQ 图表空白排查建议、CLI 手册 `--feature` 示例注释），与「Chart.js 唯一渲染、单文件自包含」口径自相矛盾——FAQ 排查项改按文件完整性/单文件自包含口径，示例注释改按实际开关（数据质量仪表盘）
> rf-720 已修复（2026-10-19）：窄屏直达改造重写首页主循环时宽/中档 `KEY_ENTER` 分支被静默丢弃（Enter 不执行选中项，宽屏回归）——自审 diff 当场捕获并补回分支；`TestNarrowMainLoopDirectNav` 的宽/窄两档驱动用例锁住重绘次数，同类分派遗漏不可能静默过审
> rf-721 已修复（2026-10-19）：用户实测报告三连——[S] 面板按数字切换后窄屏不重绘（须再按 `p` 才见结果）、`?4` 说明被写反的重绘标志立刻顶走（宽屏还误提示「状态已更新」）、提示语「? 编号 看说明」占位符写法无示例看不懂；改版为写路径所有宽度即时重绘+反馈带编号、`?` 只读查询窄屏留屏、提示语一句话教主路径（如 3 / ?3 / 0 返回），rf-595「一行反馈」收敛为只读/失败路径
> rf-722 已修复（2026-10-19）：峰谷计价用例 `test_llm_token_usage` 未声明离线——`pricing._is_holiday` 周末短路、仅工作日触达交易日历（缓存空时 akshare 联网），此前 CI 隐式编码探针恰逢北京时间周末从未点燃，周一夜间（7e77c913）首燃被网络守卫拦截（表现为 CI 单点失败、与当批改动无关）；该文件测计量口径而非节假日判定，按「不依赖外部数据的用例显式声明离线」补文件级 `offline_external_sources`
> rf-723 已修复（2026-10-19）：用户实测反馈「主菜单按方向键直接退出程序」——终端把 `ESC [ A` 拆包分节到达时首段 0.3s 窗口超时即判孤 Esc，而孤 Esc 是首页退出别名；首段共聚窗口独立加大为 `_ESC_FIRST_TIMEOUT=0.5s`（续读仍 0.3s），并补 SS3 应用光标序列（`OA`/`OB`）映射（此前落未知键），回归用例锁两窗口下限与 SS3 解析
> rf-724 已修复（2026-10-19）：`_update_json_raw_text` 对 list 值静默不替换——字段级替换只处理 dict（brace 平衡）与标量（正则匹配原文），list 走标量分支匹配不到即无声跳过，写入看似成功实则落空（多链重排首测时 priority 未变即此因）；新增 `_replace_array_block`（bracket 平衡，与 dict 版同构）接入分派，区块内注释随区块刷新、区块外保留
> rf-725 已修复（2026-10-19）：rf-723 加大首段共聚窗口后用户复测「按上下箭头仍退出界面」——更高延迟链路仍可击穿 0.5s 窗口，且孤 ESC 立即退出的语义本身不安全（误判代价 = 退出程序）；改为主菜单 Esc 连按两次确认（3 秒窗口，首按单行提示）+ 拆包残留吸收（迟到 `[` / `O` 前缀由下一次读键读完整段映射回方向键，`input_choice` 同源），误判代价降为「多按一次」且方向键拆包后仍能导航
> rf-726 已修复（2026-10-19）：rf-725 后用户再报「按一次向下键启动了 B 报告」——序列末字节在第二续读窗口（0.3s）超时后迟到，被当成独立字母键 `B` 进入直达分派；新增**半途序列前缀**状态（`_seq_prefix_pending`）：前缀已消费而末字节未到时，下一个字节一律按序列补全处理（能拼出已知序列映射回方向键，否则吞掉为 KEY_UNKNOWN），**永不进入字母分派**——迟到一键最多丢一手，不会误触发功能。拆包防护自此三件套（孤 Esc 迟到前缀吸收 / 半途序列强制补全 / 主菜单 Esc 连按两次确认）
> rf-727 已修复（2026-10-19）：「同键同语义」输入层缺口——报告链 y/N 确认、日志级别筛选、自检联网询问、What-if 日期录入、持仓文件编号等处为裸 `input()`，Esc 字节被行缓冲吞掉毫无反应；新增统一取消信号（提示处 Esc 抛出、`execute_item` 单点捕获打印「已取消，返回主菜单」即时返回），上述各处全部换 `input_choice` 接 Esc 语义（QA 长文本提问保留 `q`/回车取消）；回归测试 10 例 + 旧用例 patch 点同步
> rf-729 已修复（2026-10-19）：用户连续复测「首页两次方向键第二次退出」「[S] 面板方向键完全无导航」「宽窄适配失败」——根因为读键层 `sys.stdin.read(1)` 用户态缓冲令 `select(fd)` 谎报，整包方向键被误判孤 ESC（电脑上亦 100% 触发，此前拆包三件套全在治标）；改 `os.read(fd,1)` 与 select 同源 + 非 Esc 按键解除退出确认态 + 宽档原地重绘 + `input_choice(arrows=True)` 给 `[S]` 面板 ↑↓/Enter 导航（未导航裸回车语义不变）；pty 整包 <0.4s 解析断言锚死根因
> rf-730 已修复（2026-10-19）：用户实测「上下键导航仅首页完整生效」（[S] 游标只在临时反馈行重绘即失、[P] 等子菜单完全无导航）——根因是导航控制流在 13 处面板各自手写未单源；新建 TUI 统一交互运行时 `tui/panel_runtime.py`（`NavState`/`PanelItem`/`panel_loop`，plan-155），全部列表面板（`[P]/[A]/[D]/[I]/[S]/[M]`/缓存）+ 主循环收敛到单源导航，C29「同键同果」由测试逐处兜底升级为构造性成立；dev-verify 7202 通过 / 0 失败
> rf-728 已修复（2026-10-19）：按 `[L]` 生成前连过三次确认（强刷 y/N → 选模块 → 费用预估 y/N 默认中止），每步读屏等键、默认值组合下几乎无信息量（主路径打断）——`_cmd_generate_full` 提示链改为**合并单屏一次确认**：先上屏费用预估，单条提示「回车=生成（走缓存）/ `f`=强制刷新（再选模块）/ `q`=中止」，历史走势 `h` 选项并入（仅 `fetch_mode=prompt` 展示，其余由共享层 `resolve_fetch_history` 单源解析），默认路径由 2~3 问降为 1 问；日预算超限的降级/中止安全网确认独立保留（费用保护不受合并影响）、Esc 即时取消语义不变；测试 26 例覆盖合并屏各键分支/模块选择/预算安全网/接线
> rf-732 已修复（2026-10-19）：用户反馈「`[L]` 生成确认的提示像要记密码，还得用户猜测」——rf-728 把三问合并成单条键位图例「回车=生成 / f=强制刷新 / q=中止」，语义与后果（走缓存不花钱 vs 强刷重新计费、`f` 之后才进入模块选择）全部丢失，用户既读不出两者差别，也看不出「想选模块」该按哪个键；改为**问句式**：先上屏问句讲清代价差异，再以按键行作答，`f` 标注「（可选模块）」恢复可发现性，问句走 `wrap_hanging` 悬挂折行保证窄屏不溢出；新增回归用例锁「问句含计费/不产生新费用 + 问句先于按键行 + 按键行含语义词」

## v0.13.8 开发期已修复（2026-10-20）

- **rf-731**：LLM 费用预估接入重新生成范围——`forecast_run_cost(force_llm/force_modules)`（与 `POST /api/runs` 同源 `resolve_force_scope` 归一；范围内模块保证重新调用、按静态单价口径，范围外维持历史实际费用口径），摘要行新增「其中 N 个模块重新生成」拆行；TUI `[L]` 屏 `N`/选模块/全量后按所选范围重打更新预估行，Web `cost-preflight` 透传 `llm_modules` 查询参数（非法键 `ok:false` 数据面降级不 500）、确认弹层显示拆行，CLI `--yes` 确认透传 `--force-llm`/`--llm-module`。日预算硬闸维持「当日累计」判定不改为按次预测（按投影拦截会误伤「用已有结果」路径；本次费用预测由更新预估在展示层承担）。
- **rf-733**：删除 `tui/prompt_text.confirm_prompt`（问句+选项+默认项单行模板，`src/python/` 零生产调用）——确认类屏已按「问句行 + 键位行」两行式落地（生成确认 Y/N 化），单行模板失去挂点；其专属用例与 prompt 契约清单 `_DISPLAY_CALLS` 中的登记同步删除，`panel_prompt`（列表面板四成分模板）保留。plan-159「剩余：input_choice 类提示迁移到 confirm_prompt」方向随之关闭（不迁，两行式为准）。
- **rf-734**：LLM 配置热生效链路——`get_llm_config()` 合并缓存判据补入 `llm_providers.json`（mtime+size）；`write_llm_providers` 写后主动失效；`[M]` 换序/任意配置编辑成功与 `[R]` 刷新清页头状态行记忆（45s TTL 不吞重绘）；`llm_status()` 新增 `chain_head` 且首页状态行 `LLM ●` 后显示链首线路（窄终端弃「详情」指引守宽）。手工改 LLM 三文件均免重启生效，同会话生成用新链序。
- **rf-735**：`llm_providers.json` 头注释「主：/备：」在 reorder 互换后不更新——新增 `write_llm_providers` 写盘前 `_neutralize_chain_labels`（标注改写为中性「线路：」+「顺序即 priority 升序」归正为链序口径；幂等、仅动注释行），默认模板改为只写稳定事实；存量文件已一次性迁移。回归：中性化 / 幂等 / 无关注释不动 / 模板无主备标注 / 顺序误称归正。
- **rf-736**：`_json_patch` 硬编码 `INNER_INDENT = 4` 致 2 空格风格文件重写后变 4 空格——新增 `_detect_indent_unit`（取首个缩进内容行前导空格数），`_replace_dict_block` 与 `_replace_array_block` 同修。回归：reorder 后条目 4 / 字段 6 缩进保持、嵌套 dict 子键 4 缩进保持。
- **rf-737**：多链线路顺序两处相反——排序上提为共享 `config/_llm_providers.order_providers_by_chain`（priority 升序、同值保持数组原序），`llm_status()` 与 `[M]` 面板同经此函数，`chain_head` 恒等于 `providers[0]`。回归：数组序与链序相反时 llm_status 按链序输出、面板编号与之一致（跨渠道同序断言）、同 priority 保持数组原序、排序不修改入参。
- **rf-738**：测试隔离缺口——`tui_menu.MENU_ITEMS` 为模块级可变列表，`_apply_feature_gates()` 用切片赋值原地裁剪且不恢复，任一用例关掉 `doctor_check`/`report_qa` 后，同进程后续用例看到项数不足的菜单；单进程顺序下通常不暴露，xdist 分片改变顺序后表现为随机失败（实测 `test_footer_documents_both_exit_keys`）。修复：`conftest.py` 新增 `_restore_menu_items` autouse fixture 逐例快照/还原；同时把页脚收敛到 80 列内，避免键名改「回车」后折行拆断退出提示。
- **rf-739**：功能开关门控不可逆——`_apply_feature_gates()` 用切片过滤 `MENU_ITEMS` **本体**（无母本），且只在启动时调用一次。用户实测路径：启动时 `report_qa` 关 → `[Q]` 被裁掉 → 在 `[S]` 开启 → 回首页仍无 `[Q]`（须重启才能出现）；`doctor_check` 的 `[T]` 同病。修复：新增 `_ALL_MENU_ITEMS` 母本，门控改为**从母本重建**（幂等可逆、切片赋值保持列表对象），主循环重绘点每帧重建并同步 `nav.count`（裁剪后游标夹紧）。回归：先关后开完整恢复、列表对象同一、主循环重绘点接线断言。

## v0.13.9 开发期已修复（2026-10-20 · 补录）

> 本节为补录：v0.13.9 发布时本批仅从主台账删除、摘要未写入归档（占位已写），随 v0.13.10 发布从迁移提交父本恢复（自审见 rf-755）。

- **rf-740**：`market_hours.is_market_open()` 进程内分钟级 memo +「市场时段」DEBUG 仅状态变化输出（消除 7 天 12 万行重复 DEBUG）
- **rf-741**：解析/数据形状类异常（TypeError/KeyError/AttributeError/IndexError）不按传输级失败退避重试，fail-fast 转下一源
- **rf-742**：`chain_incremental` 历史修正全量刷新连续触发冷却（源结构性回看时跳过多拉全量，无重叠合并成功重置计数）
- **rf-743**：perf 基准禁网桩在连接级/链路级重试判据中按确定性失败 fail-fast，不逐次白等退避
- **rf-745**：requirements.md R-OUT-12 行内两份「覆盖章节」清单不一致（前份缺持仓变动复盘/调仓纪律回放/行动建议三个章节）——已删除残留份，保留与实现折叠章节全集一致的清单
- **rf-746**：requirements.md R-LLM-01「仅在菜单 L 中触发」过时（与 §3.4 Web 同管线、CLI full 同管线不一致）——已改为三渠道完整报告口径
- **rf-747**：requirements.md R-CON-07 通用降级原则未声明 R-CCH-08 联网必需模块（新闻/资金流向）例外边界——已补例外引用消除歧义
- **rf-748**：设计护栏 W3 内联色值观察项完成误报归类（40 处全为真实存量，0 误报），批量 token 化收口任务已登记 plan.md `plan-167`（含入域条件）
- **rf-749**：`write_llm_providers` 写盘后将 `llm_providers.json` 权限收紧为 0o600（与 cache 域敏感文件同标准，Windows 静默跳过），补新写/重写收紧两用例
- **rf-750**：新闻去重 bg=2 泛词否决表补 `gdp`（跨经济体 GDP 数据发布实证误合并；cpi/ppi 按既有定档维持）；bg=3 下限档收口为 plan-168（事件一致性判据）
- **rf-751**：校准工具锚点超线告警按重复行占比分流：零重复行数据集不建议 `--compact`（去重无收益），改指上调告警线；compact 零收益时输出成因说明

## v0.13.10 开发期已修复（2026-10-20）

> 完整复盘见 `changelog.md` [0.13.10] 段；此处仅摘要行。

- **rf-752**：`check-doc-drift` 结论缓存键未含 `--with-test-count` 维度——普通 `--ci` 写缓存后，`--ci --with-test-count` 会命中回放、丢「测试用例数」核对段并掩盖其漂移（反向则回放多出该段）。处理：缓存条件排除 `--with-test-count`（该模式含 pytest 收集，为独立输出面，不读不写缓存），补回放接线用例「绕过且不污染缓存」
- **rf-753**：任务台账文档存在「同一区块/条目重复出现」类冗余风险且无机检。处理：`check-doc-traces` 新增结构性冗余机检（DUPLICATE 类：重复标题全域 + 台账三文件重复长行/区块），专项测试覆盖（判重口径与域范围随后完善见 rf-754）
- **rf-754**：`docs/archive/` 全量核查发现归档残留 349 处（重复标题/内容行/区块与 NARRATIVE 复盘痕迹）+ 7 份任务代号文件名；检查器同时存在规则缺口。处理：归档内容逐类清理至复扫 0 处；7 份文件语义化改名并同步 folders.md 目录树与三份归档 changelog 引用；检查器回填（路径感知标题判重、归档域 NARRATIVE+DUPLICATE 收录、行/区块判重同小节限定、缩进 # 与命令续行豁免、文件名系列代号形态），专项测试 36 例
- **rf-755**：v0.13.9 发布归档迁移遗漏——第八批 rf-740~751 十一条仅从主台账删除、摘要未写入归档（占位已写、归档为零），且归档头部照常声明覆盖（删未写零校验）。处理：从迁移提交父本恢复十一条随本批补录（见下方补录节），头部覆盖声明更正并标注补录；防复发机检（占位↔归档节断言）登记 rf-756 随下一工作批实施

## v0.13.11 开发期已修复（2026-10-21）

> 完整复盘见 `changelog.md` 0.13.11-dev 段；此处仅摘要行。

- **rf-756**：发布归档迁移（人工步骤）无机检——占位声明「已随 vX.Y.Z 发布迁入」与归档正文脱钩（曾整批 11 条只删不写）。处理：`check-doc-drift` 新增第 20 项「迁档占位↔归档节」断言，占位已写而归档缺节即当场报出
- **rf-757**：`folders.md` 树描述写死易漂移计数（开关项数/菜单项数/文件数等 14 处），实现演进时静默过时。处理：改定性措辞 + 第 21 项「树描述计数禁令」（docs/archive 记录域豁免、中文数词常量不入检）
- **rf-763**：代码类型判定中心化违反——`holding_status.classify_code_format` 自建交易所前缀元组，与 `code_utils` 前缀知识重复。处理：上提 `EXCHANGE_PREFIXES` 与 `strip_exchange_prefix()` 供三处复用，反向机检钉住「前缀元组唯一定义点」
- **rf-764**：`report/whatif_writer.py` 双产物直写 `open("w")`，进程中断留半写文件。处理：改用 `html_save._write_html_atomic`，补中断场景回归（既有版本不被截断、只残留 `.tmp`）
- **rf-758**：演进对照「当前开发版」列新鲜度无机检（evolution 属人工步骤，跳过即以过期快照发布）。处理：`release.py gate` 前置断言列头「本次重跑时的工作区」日期须为当日
- **rf-759**：上条断言直读真实 `folders.md` + 墙钟，`TestGate` 编排用例在不同时区 CI 上随机红。处理：编排用例 autouse 夹具将新鲜度视为通过，过期分支单独覆盖（不走子进程）
- **rf-760**：`folders.md` 树描述残留约束代号/来源叙述/§ 引用/第三方版本号共 14 处，根因是围栏内树行实际从未入检。处理：围栏内树行照检 + 树行按路径分域（归档子树仅复盘叙事、计划子树查章节与约束代号）+ 无后缀来源叙述补强，14 处描述改语义化
- **rf-761**：归档子树版本目录块乱序（三次发布均插到同一锚点形成倒序），顺序零机检。处理：重排为版本升序 + 目录树检查新增「版本目录块升序」断言
- **rf-762**：developer-guide「check-doc-drift 十六项检查」清单停留在 16 项（脚本实际 21 项）。处理：清单补齐并与脚本 docstring 同源，项数改派生措辞
- **rf-791**：两守护的历史叙述词表双份维护——31 条正则逐字节相同，新增同义词须两处同步（漏改即某域静默漏检）。处理：抽 `_traces_common` 单一来源（分类/描述仍按域定义）+ 文档域模式表迁入 `_traces_doc/patterns.py`（CLI 981→708 行）+ 规则载体豁免扩面 + 结论缓存指纹纳入新文件，新增单源用例四断言
- **rf-765**：`review-findings` 分区顺序失效（三个开发期已修复节夹在待处理 P2/P3 之间，归档索引被切两段）。处理：重排为待处理 → 已解决 → 归档档案，去掉断裂空行
- **rf-766**：P3 文件过长登记表与声明派生源 `check-file-length.py -v` 脱节（行数陈旧、漏项）。处理：按脚本输出重刷登记表，行数口径统一以脚本为准
- **rf-767**：`plan-169` 已完成并从 plan.md 移除，但归档缺失且编号已消耗。处理：补录 `archived_plan` 对应条目
- **rf-768**：`plan-92` 现状句写「17 页签」与章节注册表实际 19 项不符。处理：改 19，与 README 同处口径一致
- **rf-769**：`testplan` §6.4 自动化门禁清单编号重复（`15.` 出现两次，其后全部错位）。处理：重排编号，引用即指向正确条目
- **rf-770**：`llm-technical.md` 目录把附录 A/B/C 错缩进挂在「集成点」下且缺父项。处理：按正文真实层级修 TOC
- **rf-771**：发布链无耗时埋点，整改效果无法跨版本对拍。处理：新增 `scripts/_release/_timing.py`，每命令打印摘要并追加 `logs/release.jsonl`（分步耗时）
- **rf-772**：`release.py refresh` 的 bench 跑全量 14 档，占单次发布机器时间约 75%。处理：默认只测发布口径四档，全量降为 `--full-bench` 显式入口
- **rf-773**：主程序逼近红线档（≥700 行）新增八文件未登记。处理：补登记并注明拆分方向
- **rf-774**：脚本逼近红线档（≥600 行）四文件未登记。处理：补登记（含 `check-doc-traces.py` 等）
- **rf-775**：测试逼近红线档（≥1000 行）十三文件未登记，而 P3 原注称无挂账。处理：补登记，测试域进入余量监控
- **rf-776**：正文「菜单 `X`」引用与 `MENU_ITEMS` 脱钩（主菜单键变化时十余处正文失效，code block 校验护不住正文）。处理：`check-doc-drift` 第 18 项扩「正文菜单键引用」分支，二级选项改由 `CONFIG_DIR_INFO_KEYS` 单一登记
- **rf-777**：`reports-instruction.md` 可见性规则总览表 type 行错配（表内值并非 type，行数恰好相等致计数断言全绿）。处理：第 1 项扩「表 type 行 ↔ 注册表 type 集合」双向对账
- **rf-778**：`how-to-config.md` §O 缓存分组表两组清单均不全（真值在 `core/data_registry.py`）。处理：按注册表补齐两组项
- **rf-779**：历史快照保留期在三处写成 60 天 / 12 个，与实现不符。处理：统一为真值口径
- **rf-780**：同一缓存分组三种称呼并存（菜单标签/上屏输出/函数名）。处理：术语统一为「行情类缓存」，TUI 上屏词、函数 docstring 与手册同源
- **rf-781**：配置类文档四处与实现不符（缺字段示例、口径陈述相反等）。处理：逐处按实现改写
- **rf-782**：定价表口径缺兜底说明（另有 6 条模型族前缀价）。处理：补一句前缀兜底规则
- **rf-783**：Web「配置编辑」面板分组数三处说法互不相同且漏一组。处理：按后端实际分组统一口径（含多链线路组）
- **rf-784**：`requirements.md` 菜单表 P 行开关数写 8，实为 21。处理：订正，与 TUI 手册同口径
- **rf-785**：文档点名了代码中已不存在的符号（散文层陈旧，断言与路径扫描均不覆盖）。处理：改语义描述，散文层标识符对码纳入核对方法
- **rf-786**：文档核对方法论缺口（分层分工/机检替代手段/底稿归属均无成文）。处理：developer-guide 新增「文档核对方法」四层分工 + 两条输出纪律
- **rf-787**：`test-coverage.md` 覆盖项数陈旧且无本地拦截（仅 master 档校验）。处理：提交期拦截 + `collect-test-coverage --update-docs` 回写
- **rf-788**：`logs/release.jsonl` 三处不符既有约定（无界增长、非原子写、无保留上限）。处理：改走 `core/jsonl_store` 原子追加 + 保留上限
- **rf-789**：`[D]` 面板二级键双处登记（函数内 `_handlers` 与 `CONFIG_DIR_INFO_KEYS` 各一份）。处理：键集合收敛为单一登记，`doc-drift` 校验同源
