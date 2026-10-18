# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.5]**（2026-10-17）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.6-dev] - 开发中（未发布）

### Added

- HTML 报告右上角浮动「打印 / 导出 PDF」按钮（plan-127）：`window.print()` 唤起浏览器打印/另存 PDF，44×44 触控目标、`--primary` 语义色、打印稿自隐藏（独立 `@media print` 规则）；补模板结构/可访问性/触控尺寸/打印隐藏回归用例，`reports-instruction.md` 同步入口说明
- Web 内置定时生成（plan-130）：配置页签新增「定时生成」调度面板（执行日/时刻/报告类型/启用开关），保存写入 `config.json` 的 `scheduler` 块；服务端 daemon 调度线程到点自动读正式持仓生成（正式-用存量），与手动生成同队列串行互斥、宽限 30 分钟内顺延、超时登记错过，触发账本落 `data/state/scheduler_fired.json` 防重启重复；缺省关闭零行为变化，面板改配置 30s 内生效无需重启（`GET/POST /api/scheduler`，校验 400 + 同源守卫 403）；补解析/触发窗/账本/API/面板接线回归用例，配置默认值模板与 `how-to-config.md`/`how-to-use-web-mode.md` 同步
- LLM 运行事前费用预估与日预算（plan-99）：full 生成前三渠道上屏费用区间——计划参与模块（`enabled_llm` ∩ 深度档位收窄）× 生效模型单价，perf 历史逐模块实际费用优先、静态 token 包络兜底、全部无法定价时降级「不阻塞」（渠道跳过确认继续）；TUI y/N 确认、Web 提交前弹层（预检失败/无模块直接放行）、CLI 交互确认 + `--yes` 跳过（`--non-interactive`/非 TTY 同样跳过）。`llm_settings.json` 新增 `daily_cost_limit`（默认 0=不启用）为日费用硬闸：今日已花费（perf 当日 `llm.total_cost` 汇总，与事后统计同源）达上限时交互询问「降级走缓存继续 / 中止」（降级清空强刷范围），非交互链路直接中止——CLI 退出码 2、Web 创建 409 `BUDGET_EXCEEDED` + 执行体兜底（定时调度/直连 API 同拦）；计费数学抽 `pricing.compute_cost_value()` 数值单源（`estimate_cost` 格式化契约不变）；补 4 个测试文件（预估三态/辩论口径/预算边界/三通道接线/弹层源结构），需求登记 R-LLM-13，配置/CLI/Web/TUI 手册与语义命名表同步
- TUI [S] 面板只读信息面（plan-132）：`? 编号` 查看该项说明（注册表 desc）/当前值/出厂默认值/存储键（纯只读）；行尾 `*` 标记与出厂默认不一致项（LLM 模块按 enabled_llm 出厂值、功能开关按注册表 default 比对，页脚释义）；⚗ 实验项行尾附 experiment_stats 启用统计（启用 N 次 · 最近 MM-DD，读取失败静默省略）；补 6 个单测
- 配置入口地图（plan-141）：`[D]` 子菜单新增 `[M]` **配置入口地图**——`_CONFIG_ENTRY_MAP` 只读索引，逐行列出「功能开关与 LLM 模块启停 / 报告章节取舍 / 对比指数池 / 匿名化 / 配置文件与目录 / 刷新配置 / 缓存管理 / 健康历史与日志 / 系统自检」各在哪个菜单键下（含条件可见提示：`doctor_check` 关闭时 `[T]` 不可见），零行为变化、不写配置；配置二级页与 `[P]` 排序并入 `[S]` 明确不做（平铺编号与拖拽排序不相容）；新增 5 单测（键位对主菜单真实性兜底 / 条目唯一三列齐备 / 子菜单 M→B 动线不改配置 / 无效选择提示含 M / 渲染零副作用）
- 辩论三模块双重映射消除（plan-140）：辩论白脸/黑脸/综合三段从 LLM 模块注册表移出，改由**缓存专属登记** `_CACHE_ONLY_REGISTRY`（`core/data_registry.py`）承载其缓存前缀/TTL（24h）/preload 组归属，新增缓存域访问器 `get_cache_registry()`（常规模块 + 缓存专属项）供缓存引擎消费（组清除/TTL 解析/前缀与类型分类）；模块清单域（菜单、`enabled_llm` 键域、配置编辑白名单、成本预估、系统信息）统一走 `_MODULE_REGISTRY`，隐藏层整体删除（`LLM_HIDDEN_KEYS` / `LLM_MENU_HIDDEN_KEYS` / `visible_llm_module_names` / Web surface `hidden_modules` 载荷），运行开关单点收敛为功能开关 `llm_debate_procon`/`llm_debate_conditional`；缓存 key 与既有磁盘缓存不变（无兼容窗口）；technical/手册/前端提示同步（含白名单计数 48→44 与功能开关 31→27 的陈旧数字修正）；新增回归用例 6 项（缓存域三表覆盖三段、缓存域=注册表∪缓存专属、缓存专属项非 LLM 类型、preload 组清除三段缓存、管理器恒等门面）
- TUI 缓存管理子菜单：`[3]` 清理与 `[4]` 统计两平级入口合并（plan-139）——主菜单仅保留 `[4]` 缓存管理（统计与清理），动线**先统计后清理**（进入即见统计 → 子菜单内 `3` 清理过期、执行后回统计刷新 / `B`·回车 返回）；原 `[3]` 收敛为子菜单内命令，主菜单不再单列；统计渲染拆 `_render_cache_stats`（首屏只读不等待）+ `_cmd_cache_management` 命令循环；双手册菜单块与 7 处 faq / Web 模式 / 数据源可靠性 / 配置手册 / requirements / technical 引用随键位同步，路由与子菜单动线新增 4 单测（键集、4 路由、统计-清理-刷新闭环、未知命令不清理）
- `[S]` 面板文案白话化（rf-714）：页脚（`输入编号或键名切换`）、`?` 帮助、批量/赋值提示与三处报错中的开发者术语「slug」统一改为**键名**（即说明标题括号中的英文名，与手册既有术语一致）；赋值提示去「按 CLI 词表设置」改为「直接设置」；手册 [S] 三处同步；新增源码级回归断言（面板用户输出与渲染源码均无 'slug' 回潮）
- `[S]` LLM 模块区历史费用显示（plan-138）：`perf.module_cost_summary(days, path)` 新增——按模块汇总近 N 日 `llm.modules.*.cost`（与事前费用预估/日预算同记录同字段同计费数学，三处口径同源不打架）；LLM 行尾附「近7日 累计（次数 · 单次均值）」摘要、无样本不带、读取失败静默省略（面板照常渲染）；逐模块费用链已核实为既有能力（api_base/skeleton/news/orchestrator 调用点 → session per_module → perf `llm.modules`），本次补齐的是归集读取与展示；5 单测（窗口归集/过期剔除/空文件/行尾摘要/静默降级）
- 持仓变动复盘双入口面板互指标注（plan-137）：`[S]` LLM 区「持仓变动复盘归因」行尾与独立组「持仓变动复盘」行尾互相指出对方入口（`· 章本体在「独立组」` / `· 归因在「LLM 区」`），标注常量展示层单点、清单仍由注册表派生；纯只读零行为变化，2 单测锁定（互指唯一出现 + 不触发写入），手册 [S] 补双入口说明
- 实验项生命周期表落地为单一事实位（plan-136）：technical.md 新增 §6.9（功能语义命名表邻域）——七列结构（flag/实验目的/判据来源/转正条件/撤销条件/观察数据源/当前态）覆盖现有 2 个 ⚗ 实验项（决策跨期反思闭环、报告对话式追问）；判据详文留在计划死线条目与版本归档评估记录（双向回链本节，不复制全文防两处口径漂移）；纪律入表头：立项/转正/撤销必须同步刷新本表
- TUI `[S]` 面板写路径三通道增强（plan-135）：①批量恢复默认——`r 编号或slug` 恢复本组、`ra` 恢复全部（新原语 `features.clear_feature_overrides`：恢复默认=删覆写键+运行时回出厂默认，批量原子写，返回实际移除键数上屏）；②实验项一键全关 `x`（experimental 集合回默认，便于 bisect）；③编号/slug 双通道——裸 slug 切换、`slug=on|off` 与 CLI `--feature` 同一解析器与词表（旧键别名过渡一致）、`? slug` 查详情；LLM 模块拒绝 `r`（仅功能开关分组可恢复）。编号派发与 Web 面板派生不变；新增 10 单测（临时 features.json 隔离）39/39 绿，手册 [S] 操作面同步
- 财报基本面两开关合并为单一「个股基本面」开关（plan-134）：`financial_report_digest` + `financial_indicator` 并入新键 `stock_fundamentals`（默认关，独立章节与回放组），单开关同控持仓基本面两块（财务指标 + A 股财报章节摘要）；旧键读写双路径一版过渡（load/save 按并集迁移并告警、新键并存时以新键为准；`--feature` 旧键别名告警映射）；面板 28→27 项（独立章节与回放 6→5、面板编号单次重排：独立 25-29 / 机制 30-34）；报告层两处 `or` 门控收敛为单一变量，章级细分由既有报告章节配置（`fundamental_snapshot` 章整体显隐）承接、不另设子开关；数据源矩阵/模板占位指引/手册与管理文档同步，本地 features.json 已迁移
- 机制类三开关内置化（plan-133）：`datasource_adapter` / `decision_header_parse` / `datasource_credential_ready` 三开关经 parity、跨版本稳定期（2026-09-10 引入、09-11 转正默认开、历时月余无回退）与无关态覆写证据评估后删除注册表条目与关态死分支——行情链路恒走适配器（不可用时回落既有映射的安全网与 parity 锁定保留）、结构化决策头恒追加（`_dh` 指纹后缀常驻，回落表格解析保留）、凭据就绪预检恒执行；面板 31→28 项（机制与诊断 8→5，面板重排一次），features.json 残留旧键按「无消费者开关」告警提示清理；OFF 态专属用例随行为退役，回退/兜底等价用例改由强制回落路径锁定
- report_qa 转正评估首轮执行并挂账判据（plan-131）：`experiment_stats` 实测启用 5 次（最近 2026-10-13）→ 未达转正样本亦未触发撤销，维持实验观察；质量抽检（会话仅内存态）与费用留痕（usage 有 token 口径、无费用口径）两个缺口固化进转正前置清单，判据与转正/撤销执行清单的长期单一事实位交由实验项生命周期表承接
- perf-view 费用趋势（plan-129）：`--by day|week|hour` 时段聚合表新增「费用合计/费用环比」列（耗时与 `llm.total_cost` 同表交叉，零数据新增，无费用样本自动省列，末档附环比提示行）；`--json` 汇总新增 `llm_cost` 费用块（runs/合计/均值/中位/单次最高）与 `--by` 时的 `by_period` 时段费用序列；补 9 个回归用例（费用列/环比/省列/机读字段/整链渲染）

### Fixed

- 完成通知 Web 渠道接线（rf-708）：`_run_generation` 改薄包装器（委托执行体 + `result_box` 回传产物标志），收尾按 `notify` 配置门控派发完成/失败通知——Web 手动生成与内置定时调度共用（无人值守定时失败不再静默，与 CLI 同构：门控前置、尽力而为不改退出码/不改 run 状态）；降级摘要单源下沉 `report/data_status.degradation_summary()`，CLI 原函数改委托；补门控/载荷/吞异常/接线回归用例
- 景气度框架诊断迁组（rf-712）：`prosperity_framework` 作用域复核为行动章内嵌评分卡区块（属「既有章内追加分析块」），注册表分组由机制与诊断迁至分析增强——面板编号、TUI 手册分组表、how-to-config/technical 归属描述随迁同步；requirements R-PF-01 引用的已废弃 `GROUP_STANDARD` 常量改现行 `GROUP_ANALYSIS`，并修正 how-to-config「31 项」与分组计数残留
- 双渲染路径收敛（rf-114）：删除模板 Canvas 回退渲染器 `drawSimpleChart` 与全部 `enable_interactive_charts` Feature Flag 条件分支（主模板 2 处 + 组合演进/持仓明细/穿透/纪律回放/组合历史回撤 5 个 partial），Chart.js 成唯一渲染器（引擎缺失/数据不足时画布占位、数据表格照常，逐图独立 try/catch 不连锁）；开关随消费者消失一并摘除（功能开关 32→31 项、面板其后编号前移，Web/TUI/CLI 三端与文档同源同步）；滚动超额曲线与持仓重合度滚动相关图原为 Canvas-only，移植为 `excess_rolling`/`corr_rolling` Chart.js 数据集（`write_html_report` 权威重建，对齐/降级语义不变）；补单渲染器结构回归锚点与两 builder 回归用例
- 报告模板 tooltip XSS 纪律（rf-709）：`drawSimpleChart` hover 内容改 DOM API 构建（`createElement` + `textContent`/`createTextNode`，色点走 `style.backgroundColor` 属性赋值），全文 `innerHTML` 清零；模板源结构测试断言无注入 sink 防回归
- 遥测 JSONL 保留上限（rf-710）：`jsonl_store` 追加原语增 `max_lines` 尾部保留参数（超限丢最旧行，原子写语义不变），perf 历史 5000 行 / 健康检查历史 2000 行上限；账本/去重锚点等业务态文件不设（避免丢失跨会话状态）；补裁剪/批量/缺省行为回归用例

- LLM 计费口径统一修复（rf-701/702/703）：`_normalize_usage_tokens` claude 分支把 `input_tokens` 归一为总输入（补 `cache_read_input_tokens`，兼容端点命中大于未命中不再产生负费用），openai 分支补读 DeepSeek 原生端点顶层 `prompt_cache_hit_tokens`（优先于 `prompt_tokens_details.cached_tokens`）；`estimate_cost` 的 `cache_miss` 下限 0 防御；报告页脚/批处理汇总/新闻相关性费用估值统一走归一层，会话累计费用与单次估算同参等值；补 5 个回归用例
- LLM 模型定价表按官方定价页核实修正（rf-700）：Claude Opus 4.x 15/75→5/25、Haiku 4.5 0.25/1.25→1/5、Fable 5 3/15→10/50、Gemini 3.5 Flash 0.15/0.6→1.5/9、Gemini 2.5 Flash 0.15/0.6→0.30/2.50、2.5 Pro 输出 5→10、GPT-4o/mini 缓存命中补 50% 折扣；同步 `llm-technical.md` 附录 B 与 `how-to-config-llm.md` 定价表。DeepSeek 峰谷价与 Kimi 价经核实无偏差，不影响现有费用估算
- 过期缓存生成路径自动清理（rf-704）：`cache.auto_cleanup_expired()` 尽力而为包装（任何异常吞掉返回 0），`generate_report` 入口调用（CLI/TUI/Web 三渠道共用入口），无人值守 CLI 定时任务不再只增不减地堆积过期缓存文件；补委托与吞异常回归用例
- Web 进度轮询任务丢失终态处理（rf-705）：`pollOnce` 识别 404/`NOT_FOUND` → 停止轮询 + `restoreGenerateBtn()` 单源复位 + 结果区渲染失败态（提示任务已失效请刷新），不再被当瞬时错误无限重试；补 main.js 源结构回归用例
- Web 进度事件通道完整性（rf-706）：`pollOnce` 增在途互斥（pollBusy，成功/异常/同步抛三路复位）+ 按 `seq > lastSeq` 过滤重复回放；服务端 events 载荷补 `first_seq`（`RunState.oldest_seq`），前端缺口时渲染「中间已省略 N 条」占位行不再静默跳号；补 RunState 边界/载荷字段/main.js 源结构回归用例
- Web 生成进度断点续传（rf-707）：活动 run 写 sessionStorage（提交成功/流程重置/轮询完成/任务失效四点闭环清理），页面加载 `resumeActiveRun()` 重建进度视图从 `after=0` 续轮询；run 已随服务重启消失时走任务不存在终态收口不空转；补 main.js 源结构回归用例

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.5（2026-10-13 ~ 2026-10-17）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
