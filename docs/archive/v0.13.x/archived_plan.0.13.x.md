# 计划归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布后开发期完成项并入，0.13 系列首份）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.13.x 开发期完成项
> 归档内容：由各任务完成后人工迁入

---

## plan-142 首页窄屏「免导航直达」重绘策略 ✅

**完成（2026-10-19，v0.13.7-dev）**：narrow 档（<64 列，`layout_tier`）交互主路径改为「按字母/数字键直达」——`tui.main` 拆出内层按键循环：直达键（快捷键）执行后回重绘点刷新首页，方向键/Enter/未登记字母在窄屏**静默忽略且不重绘**（此前每按一次整屏追加一屏，手机短屏上菜单被顶出可视区）；`render_menu` narrow 档不渲染 `>` 选中指示器（无导航则指示器误导），页脚换「窄屏直达：按菜单 [键] 执行」文案，宽/中档方向键导航与「方向键移动 | Enter 确认…」页脚不变。测试：`test_tui_menu.py` 新增 `TestRenderMenuNarrowDirect`（narrow 无指示器/直达页脚、宽屏保留选中态）与 `TestNarrowMainLoopDirectNav`（窄屏三类非直达键零重绘、宽屏方向键重绘、Esc 退出）。文档：tui-menu 手册键盘操作表补 Esc 行与窄屏说明、FAQ 无响应排查措辞同步、requirements R-TUI-07 与 technical 按键分派描述同步。

## plan-143 ESC 序列读取超时适配高延迟链路 ✅

**完成（2026-10-19，v0.13.7-dev）**：`tui_keys._ESC_TIMEOUT` 0.15s → 0.3s——手机蜂窝网/高延迟 SSH 下方向键三字节序列可能分节到达，0.15s 会把序列拆散误判成孤 ESC（方向键时灵时不灵）；回归用例断言超时 ≥0.3s。

## plan-144 Esc 键作为首页退出别名 ✅

**完成（2026-10-19，v0.13.7-dev）**：`tui_keys` 新增 `KEY_ESC`（Linux 孤 ESC：序列读取超时无后继字节；Windows `b"\x1b"`），`tui.main` 将 Esc 与 `0`/`[X]` 同列为退出通道（手机 SSH 客户端普遍提供 Esc 键）；页脚退出提示统一为「Esc / 0 / X 退出」。测试：`test_tui_keys.py` 常量/Windows/Linux 孤 ESC 三例 + 主循环 Esc 退出例，既有「孤 ESC → KEY_UNKNOWN」用例改为 KEY_ESC（刻意行为变更）。

## plan-145 input() 提示窄屏折行纪律与机检 ✅

**完成（2026-10-19，v0.13.7-dev）**：`text_layout.wrap_prompt`——提示宽 ≤ 终端宽原样返回（宽屏零开销），超宽按显示宽度折行并以「  >  」输入位短尾缀收尾（窄屏提示与光标不脱节）；`handlers_report`（5 处费用/确认提示，最宽 68 列）、`handlers_log`（级别筛选/联网自检）、`handlers_qa`（报告选择）、`handlers_whatif`（路径/生效日）共 10 处长提示接入。机检守护：`test_text_layout.py::TestInputPromptNarrowContract` AST 扫描 `tui/*.py` 全部 `input()`——裸字面量提示 >40 列（与 `terminal_columns` 下限一致）未包 `wrap_prompt` 即红；具名提示 `_QA_PROMPT` 显式锚定 ≤40 列。测试：`TestWrapPrompt` 4 例（宽内原样/折行不越界/末行输入位/不丢字）。

## plan-149 [S] 面板主路径零学习成本交互 ✅

**完成（2026-10-19，v0.13.7-dev）**：提示语从占位符写法「输入编号或键名 (0-34)，? 编号 看说明」改为一句话主路径教学「输入编号切换开关（如 3）· ?3 查看说明 · 0 返回」（r/ra/x/k 高级命令退居页脚图例，窄屏图例去掉与提示重复的主路径行）；写路径（编号/键名直取、赋值、r/ra/x 恢复默认）所有宽度成功后即时重绘面板、反馈行带编号（`[OK] 3 名称 已关闭`）——手机端不再要求按 `p` 才见结果；修复 `?` 说明分支写反的重绘标志（此前窄屏说明被整屏重绘顶走、宽屏误提示「状态已更新」），只读查询窄屏留屏、宽/中档照常重绘；失败路径窄屏保持一行反馈（`p` 重绘）。契约测试 `TestRepaintAndHelpVisible` 三例（写后重绘带编号 / 窄屏说明留屏 / 宽屏重绘且无误导提示）+ 白话化测试改锚新提示；手册 [S] 用法段与 technical 面板描述同步。

## plan-150 `?` 说明入口兼容全角问号 ✅

**完成（2026-10-19，v0.13.7-dev）**：[S] 面板说明查询入口同时收半角 `?` 与全角 `？`——中文输入法下用户直接敲出的就是全角问号，原实现只认半角导致全角输入落到「未知编号或键名」分支；说明分支判断与详情剥前缀两处放行 `？`，回归用例 `test_full_width_question_mark_shows_detail` 锁「全角同效 + 只读不写配置」。

## plan-151 子菜单 Esc 即时返回上一步 ✅

**完成（2026-10-19，v0.13.7-dev）**：新增 `tui_keys.input_choice(prompt) -> str | None`——菜单选择行输入：raw 模式逐字节读行（回显自理、退格按 UTF-8 字符回剥），孤立 Esc 经 `_ESC_TIMEOUT` 判定即时返回 None（手机 SSH 误入子菜单直接回上一步，不必找「0 返回」）；回车提交并 strip，Ctrl+C 转发 KeyboardInterrupt 与各调用方既有 except 分支衔接；非 TTY（测试/管道）回退 `input()` 且同样 strip，既有测试驱动方式不变。接入 14 处选择/录入点（[S] 面板、配置菜单、对比指数池、报告章节、匿名化、目录信息、字段编辑、指数代码/名称录入、缓存管理、问答报告选择、What-if 文件编号/选项/路径）；QA 长文本提问与 y/N 确认保留 `input()`（q/回车取消）。Windows 分支 msvcrt 同语义。测试：`TestInputChoice` 7 例 + [S] Esc 返回不写配置 + 缓存菜单 Esc 不重提示；既有 17 处 `<module>.input` patch 改靶 `builtins.input`（模块内已无直调）。

## plan-154 TUI「分档只改版式不改语义」统一纪律（C29 + 守护） ✅

**完成概要**（2026-10-19，窄/宽交互审计后用户确认方案）：审计列全 `layout_tier` 分支点，确认历次「互动不一致」缺陷同源——分档分支改掉了按键语义/反馈。落地：① 架构约束 **C29**（分档只允许改版式与密度，不得改按键语义、反馈有无、写路径可见性；适用 `src/python/tui/` 全部分档分支点）；② 窄屏未登记字母/未知键从静默忽略改为单行反馈（`_print_hint` 原语，并入原地重绘清除范围），与宽档「重绘即反馈」对齐；③ 守护测试 `TestTierSemanticParity` 5 例锁「同按键两档同语义同反馈」。R-TUI-07 / technical 菜单段 / changelog 同步

## plan-153 TUI 窄屏恢复方向键导航（原地重绘） ✅

**完成概要**（2026-10-19，用户直接要求）：窄屏（<64 列）在直达主路径外恢复 ↑↓/Enter 导航——`>` 选中指示器全档渲染（render_menu 去除窄屏特判），选中移动后原地重绘（`_render_menu_frame` 用 `_FrameLineCounter` 计数帧行数 + `_clear_last_frame` ANSI 光标上移/清屏，`_can_repaint_inplace` POSIX+TTY 门控，不可用回退整屏追加），Enter 全档执行当前项；页脚双提示（直达 + ↑↓ 选择）。R-TUI-07 / technical 菜单架构段（顺带修正项数 18→19）/ tui 手册窄屏注同步。测试：`TestNarrowMainLoopDirectNav` 6 例（含原地 vs 回退分支 spy 区分、清帧助手 ANSI 输出）+ 渲染 3 例

## plan-152 LLM 多链 Provider 优先级三渠道可调（CLI/TUI/Web） ✅

**完成概要**（2026-10-19）：共享编辑层 `llm_providers.priority` 动作写通道（order 置换校验 + priority 归一化 10/20… + 注释保留 + 写前 .bak）；CLI `--llm-provider-order` 持久化写盘后退出；TUI `[M]` 编号交换面板（`input_choice` Esc 返回）；Web 配置面「LLM 多链线路优先级」块 ▲▼ 调序即存。实现中连带修复 `_update_json_raw_text` 对 list 值静默不替换（新增 `_replace_array_block`，rf-724）。测试：config 11 例（置换校验/归一化/注释保留/备份/缺失回退/损坏回退）+ CLI 5 例 + 面板 5 例 + Web 3 例

## plan-94 图表数据无导出通道 ✅

**完成（2026-10-18，v0.13.7-dev）**：选型为**前端每图导出**（不做整份 `chart_data.csv` 产物）——`src/static/chart-export.js` 为每张 Chart.js 图表注入 `.chart-export-actions` 组容器（「导出PNG」+「导出CSV」并排，浮于图卡右上角、存在 `.chart-title` 时进标题栏右侧，按组容器幂等判重）；CSV 读 `chart.data`（与屏显/悬停值同源，Python 数据层已按匿名化口径脱敏），首列表头取 x/r 轴标题（缺省「标签」）、系列列取 dataset label（单系列缺省「数值」），RFC 4180 引号转义 + CRLF + UTF-8 BOM 后 `Blob` 纯前端本地下载（零后端，`URL.createObjectURL` 用后释放），文件名 `<key>.csv`；模板定位样式三处同步（主报告 `report_template.html` / What-if `whatif_template.html` / 调试页 `test-chart.html`：绝对定位移到组容器、按钮静态排布不重叠、打印态隐藏组容器），what-if 关态金样基线随模板 CSS 与内联脚本字节变化显式复核更新。测试：`test_feature_interactive.py` 新增 `TestChartExportCsv` 4 例（双按钮注入与组容器幂等 / Blob MIME+BOM+ObjectURL 释放 / 行列取自 chart.data 与 RFC 4180+CRLF / 三模板组容器定位且按钮不绝对定位）。文档：reports-instruction 交互图表特性补双按钮与 CSV 口径、README 能力表补 CSV、folders 目录树说明。

## plan-141 配置入口地图（[D] 子菜单只读索引）✅

按计划「①先行」落地（只读索引，零行为变化；②③明确不做并记录理由）：`handlers_config` 新增 `_CONFIG_ENTRY_MAP` 常量（9 行三元组：配置项 / 菜单键 / 补充说明）与 `_render_config_entry_map()`（按 `display_width` 对齐的只读渲染，不等待按键、不写配置），`[D]` 子菜单新增 `[M] 配置入口地图` 项（items 表 + 无效选择提示改 C/F/O/M/B + docstring 更新）。地图覆盖：功能开关与 LLM 模块启停 `[S]`（含行尾费用摘要/启用统计）、报告章节取舍 `[P]`、对比指数池 `[I]`、匿名化 `[A]`、配置文件与目录 `[D]`（C/F/O）、刷新配置 `[R]`、缓存管理 `[4]`、健康历史与日志 `[H]/[V]`、系统自检 `[T]`（标注 `doctor_check` 关闭时不可见）。测试 5 例：键位真实性兜底（地图每个键均存在于 `MENU_ITEMS`——键位调整/菜单合并时自动红）、条目唯一且三列齐备且键带方括号、`[D]`→`M`→`B` 动线（断言 C/F/O 三个写入处理器均未被调用）、无效选择提示含 M、渲染零副作用（refresh_config / save_feature_overrides 均未触发）。handlers_config 50/50 绿。文档：tui-menu [D] 节标题与样例块加 M 并补说明、requirements D 行、technical 菜单表 [D] 行。

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

## plan-156 TUI 交互契约文档化 + 契约结构测试 ✅

**完成（2026-10-20，v0.13.8-dev）**：把设计稿 `docs/archive/v0.13.x/tui-interaction-hci-design.md` §5 定稿为常驻管理文档 `docs/managements/DESIGN-TUI.md`——TUI 侧唯一判据，与 `DESIGN.md`（Web/报告视觉契约）对称：Overview 五原则（识别优于回忆 / 一键一义 / 屏幕自解释 / 专家快路不牺牲可发现性 / 可机检优先）、Keys 键分工总表（数字/回车/`?`/`0`/`Esc`/字母/`/`/方向键 + 每键「禁止用法」）、Prompts 提示三段式四成分模板、Defaults 默认项与取消标注语法（含「回车=取消须置句首」「危险操作默认安全侧」）、Colors 一色一职责角色表、Vocabulary 术语对照表 + 适用范围四档、Feedback 反馈与空态口径（含页头状态行与按键闸门白名单）、Do/Don't 护栏、Iteration Guide、Known Gaps。契约结构测试 `src/test/unit/ui/test_design_tui_doc.py` 由 9 例扩到 19 例：必需节（含 Colors）子集、键表必备键、四张表的列集合、关键口径句成句存在、护栏编号连续且 DO/DON'T 对偶、术语表覆盖内部词、Known Gaps 逐条带状态、契约内禁任务代号、闸门白名单文档与代码双向一致、引用实现文件存在。同步 CLAUDE.md「设计契约」条目（拆分为 Web/HTML 与 TUI 两份契约及其守卫）与 developer-guide「计划收尾：文档触点清单」（新增「TUI 交互改动」行）。

## plan-157 回车语义唯一化 + 默认项标注 ✅

**完成（2026-10-20，v0.13.8-dev）**：回车一键多义收敛为「回车 = 本行提示标注的默认项」，默认项必须带动作名。改造：追问屏问句「回车=结束追问返回主菜单」、报告选择屏「回车=最新报告 / 编号=指定报告 / q=取消」、What-if 生效日「回车=跳过，不做时序回测」、启动向导「回车=跳过」；**屏幕键名统一**——页脚与手册里的英文 `Enter` 全部改为「回车」（同键两名会让用户以为是两个键）。机检 `test_prompt_contract.py` 新增两条硬规则：规则 5「屏上禁英文 `Enter`」（扫 TUI 全量字面量、排除 docstring）、规则 6「回车必须带动作名」（`回车=<动作名>` / `回车跳过` / `回车/q` / `空回车=` 等声明形式）+「取消/中止/跳过类语义须置于首句」（按 `/` 分句定位回车所在分句）。契约 `DESIGN-TUI` Keys 表补「屏上不得写作英文 `Enter`」、Vocabulary 表补 `Enter → 回车`。回归：QA 选择屏与提问屏、What-if 生效日提示的声明断言 3 例 + 页脚断言同步。

## plan-158 `?` 帮助全覆盖（下沉 `panel_runtime`）✅

**完成（2026-10-20，v0.13.8-dev）**：`?`（无参=本面板可用键一览）与 `?键`（第 N 项详情）此前已下沉 `panel_runtime` 统一承接；本轮补齐**详情文案**——`PanelItem` 新增 `detail` 字段，`_emit_help` 以 `hint=item.detail` 渲染。各面板落文案：`[P]`（章节切换影响 + 增强子模块改由 `[S]` 配置的说明）、`[A]`（切换到该匿名化模式、立即写盘）、`[I]`（添加/删除/重置各自作用）、`[M]`（模型 + 优先级 + 端点）、缓存面板（清理只删过期项、清理后统计刷新）；`[S]` 保留 `on_help` 富详情。测试：`test_panel_runtime` 新增「`?键` 渲染 item.detail」，面板级新增 `[A] ?3`、`[M] ?1` 两例真实渲染断言。手册键盘操作表补 `?` 行（含全角 `？` 与各面板详情差异）。

## plan-159 提示行模板化（禁裸提示）✅

**完成（2026-10-20，v0.13.8-dev）**：`tui/prompt_text.py`（`panel_prompt` / `keys_help_lines` / `item_detail_lines`）建成后，7 处 `panel_loop` 提示全部由模板产出，机检（AST）断言「`panel_loop` 的 prompt 必须是 `panel_prompt` 调用」，裸字面量即红；模板自带 `wrap_prompt` 折行守住 40 列窄屏基准。「`input_choice` 提示迁移到单行确认模板」方向经评估关闭——确认屏已改为「问句行 + 键位行」两行式（生成确认 Y/N 化），单行模板失去挂点，`confirm_prompt` 随之删除（详见 review-findings 已解决条目）；`input_choice` 提示改由机检规则 3/6 约束（必须声明回车动作名），白名单只减不增。

## plan-160 主菜单编号连续化 — 已评估不采纳（前提消失）❌

**结论（2026-10-20，v0.13.8-dev）**：原问题「数字键为 `1/2/4`，没有 3」已不存在——现主菜单数字键为 `1/2/3`（1=基础缓存、2=行情缓存、3=缓存管理），连续无断层。更根本的是该任务把「首页」与「面板」当成同一种编号体系：首页 19 项中 16 个是字母键（主入口），`1/2/3` 只是数据类操作的别名，不构成序列；全量重编号为 `1..19` 会改约 200 处文档键位、放宽菜单块机检正则，且与 `DESIGN-TUI` Known Gaps 已作的「编号为主入口：已评估未采纳」结论直接冲突。**替代交付**（真正有价值的不变量）两条守卫：① `test_tui_menu.py::test_numeric_keys_are_contiguous`——首页数字键必须 1..N 连续区间（允许字母项任意，禁止跳号）；② `test_prompt_contract.py::TestPanelNumberingContiguous`——面板手写数字编号须补齐 1..N（0 为返回项，字母型面板的单个数字项不参与）+ `test_handlers_config_nav.py::TestPanelNumberingRendered`——`[P]/[S]/[M]` 渲染级编号前缀恰为 1..N、末项 0（按结构关系断言，不写死总数）。

## plan-161 `press_any_key()` 收敛 ✅

**完成（2026-10-20，v0.13.8-dev）**：强制闸门从 28 处收敛为 **5 处长输出闸门**（运行日志详情 / 数据源健康历史 / 系统自检结果 / 报告收尾摘要 / 缓存更新结果摘要），其余 22 处（配置面板收尾、缓存清理、What-if 完成、持仓读取错误、调度层取消与异常）一律直接回菜单——取消与错误反馈不再多按一次键。白名单由 `test_prompt_contract.py::TestPressAnyKeyGateWhitelist` 与代码实际调用点双向机检（新增闸门即红、失效条目即红），契约 `DESIGN-TUI` Feedback 节列明 5 处与理由。击键基线同步收紧：`[S]` 只读动线 5→4、缓存面板动线 4→3。

## plan-162 术语改写 + 禁用词机检 ✅

**完成（2026-10-20，v0.13.8-dev）**：上屏文案全量改写——强刷→「重新生成（会调用 AI，计费）」、走缓存→「用已有结果（免费，可能不是最新）」、降级源→「备用源」、配置漂移→「与出厂默认不一致」、降级顺序→「备用顺序」、熔断→「自动重试: 正常/暂时失败」。机检 `test_prompt_contract.py::TestForbiddenVocabulary` 三条：CJK 术语扫全量字面量（排除 docstring 与日志消息）、英文术语仅扫展示型调用（避免命中程序标识符）、内部值白名单须仍被需要（防挂账腐烂）。三渠道同词由 `core.system_info.circuit_display` 唯一归一，守卫 `integration/test_channel_vocabulary.py`；契约 `DESIGN-TUI` Vocabulary 节含四档适用范围（TUI 状态面 / Web-CLI 决策屏 / 报告数据降级 / 日志与机制文档）。存量清零。

## plan-163 Esc 策略复核 — 已评估未采纳（维持双按确认）❌

**结论（2026-10-20，v0.13.8-dev）**：读键层已由 `os.read` + 同 fd `select` 重写（rf-729），常规链路方向键不再拆包；但**极高延迟链路**（手机蜂窝 + SSH 多跳）下三字节序列仍可能跨读分节、超过 `_ESC_TIMEOUT` 后表现为孤 Esc，若恢复单按退出，一次方向键误按即退出程序（丢失当前面板上下文，比多按一次代价高）。故**维持「Esc 连按两次确认（3 秒窗口）」**，与 `0`/`X` 单次退出三通道并存。回归已齐：`test_tui_menu.py` 四例——`test_esc_single_press_shows_confirm_hint`（单按不退出，拆包残留场景）、`test_esc_double_press_exits`（连按退出）、`test_esc_armed_cancelled_by_navigation_key`（任何非 Esc 键解除确认态，挂起确认不被后续按键引爆）、`test_esc_exit_parity`（窄/宽两档同语义）。首按提示文案「再按一次 Esc 退出」。

## plan-164 主菜单按任务重组 + `/` 过滤搜索 ✅

**完成（2026-10-20，v0.13.8-dev）**：主菜单由 19 项平铺改为四组渲染（生成报告 E/B/L/W · 数据与查看 Q/D/1/2/3 · 配置 P/I/A/S/M/R · 诊断与排查 V/H/T，退出项单列），组标题只降低扫读成本、不改任何按键；新增 `/` 关键词筛选（先比按键再比标签文字；筛选态只渲染命中项、`↑↓` 在命中集内回绕、按到隐藏项给单行反馈、`0` 先清筛选）。机检：分组覆盖全项一次（退出项除外）、筛选命中与筛选内回绕、分组标题与筛选态渲染。**「编号为主入口」已评估未采纳**（键位已在三渠道文档与肌肉记忆中稳定，全量重编号需改约 200 处文档并放宽菜单块机检），理由记入 `DESIGN-TUI` Known Gaps；替代方案即分组 + 筛选。手册与 `check-doc-drift` 菜单块同步。

## plan-165 击键数与屏幕语义纳入门禁 ✅

**完成（2026-10-20，v0.13.8-dev）**：三条主路径 E2E 动线落地（`src/test/scenario/basic/test_tui_flow_semantics.py`）：①生成完整报告且只重新生成指定模块 ②改一个功能开关并确认生效 ③按级别筛日志——每条同时断言「击键数不增」与「关键用户词上屏」，契约快照 `src/test/data/fixtures/tui_flow_contract.json`。基线快照 `src/test/data/fixtures/tui_keystroke_baseline.json` 共 6 条动线（`exit_via_x` / `exit_via_zero` / `switch_panel_readonly` / `cache_panel_return` / `generate_full_default_path` / `filter_then_cache_panel`），分组与 `/` 筛选改造未改变任何既有动线击键数（1/1/4/3/3 保持），筛选动线新增 6 键。分层：P0 `dev-verify` 只跑生成主路径 1 条、P2 `regression` 跑全 3 条、P1 `verify` 覆盖击键基线；驱动器统一在 `src/test/_tui_flow.py`（两处断言共用同一动线定义）。

## plan-155 TUI 统一交互运行时（panel_runtime）✅ 主体交付

**完成（2026-10-20，v0.13.8-dev 归档）**：按 [`tui-panel-runtime-design.md`](tui-panel-runtime-design.md) 实施完成——新建 `tui/panel_runtime.py`（`NavState` / `PanelItem(key, label, kind, action, detail)` / `panel_loop`：导航态单源，语义真值取自主循环），`test_panel_runtime.py` 31 例；全部列表面板（`[P]/[A]/[D]/[I]/[S]/[M]` + 缓存管理）迁移到 `panel_loop`——方向键导航全面板生效、Enter 防误触 engaged 门控、直达键游标同步不置 engaged、`kind=return` 项不参与回绕；主循环 `sel` 亦 NavState 化。`[S]` 匹配/详情辅助抽出至 `handlers_switch.py`。文档触点同步（technical 模块表 + C29 升级为「构造性成立」、folders 目录树、requirements R-TUI-08、testplan §2.1、how-to 键位表、changelog）。

**本轮补充**：`[M]` 多链优先级面板整体迁出为 `tui/handlers_llm_providers.py`（`handlers_config` 仅留菜单入口薄包装）——原文件曾达 1017 行、超单文件 1000 行硬上限（由 `check-file-length` 拦截），拆分后 899 行，红线恢复。

**残值（转 plan-166）**：`[S]` 功能开关面板主循环仍在 `handlers_config`，「域拆分 <800 行」设计目标未达成——因几十处测试 patch 点耦合，单独立项推进。

## plan-148 窄屏 40 列设计基准纪律化 ✅

**完成（2026-10-20，v0.13.8-dev）**：原计划「成本高则退化为验收清单」，实测后判定**成本不高且必须先修**——`COLUMNS=40` 逐面板量宽发现真实溢出：`[P]` 56 列、`[A]` 57 列、`[I]` 49 列（三者无条件调用 `render_panel`，而该函数的宽度是内容驱动、下限 41 列内容 + 边框，完全不看终端宽度）。修复：`switch_panel` 新增共享原语 `render_titled_panel(title, rows, *, columns)`——宽/中档画盒线，窄档退化为「结构标题行 + 无边框行 + 行内截断」（对齐既有「窄档不画盒线，先让装饰再让信息」约定），`[P]/[A]/[I]` 三处接线。守护：`src/test/unit/ui/test_narrow_panel_render.py` 全景机检（11 例）——`COLUMNS=40` 驱动主菜单与全部面板渲染路径，逐行断言 `display_width(line) ≤ 40`；新增面板登记即纳入底线，忘了降级立刻变红。触点纪律写入 `developer-guide`。

## plan-146 长输出面板窄屏卡片化 ✅

**完成（2026-10-20，v0.13.8-dev）**：实测四个长输出面板在 40 列下大面积超宽（`[V]` 运行日志 202/205 行超宽、最宽 103；`[D]` 配置入口地图 11/11 行超宽、最宽 117；`[H]` 健康历史 12/15；`[3]` 缓存统计 10/33）。修复按「窄档不硬折」逐面板降级：`[D]` 改「菜单键 + 标签」一行 + 说明悬挂折行；`[H]` 每条记录压成「时间 / 结果」两行 + 失败源悬挂折行；`[V]` 日志按内宽悬挂折行（**先折行后上色**，ANSI 不被截断）；`[3]` 长路径/统计统一经 `_emit` 折行、分隔标题宽度自适应（`_rule`）。四个面板全部由 `test_narrow_panel_render.py` 的 40 列断言兜底（修复前该 4 例为红）。

## plan-147 手机使用动线文档化 ✅

**完成（2026-10-20，v0.13.8-dev）**：FAQ 新增「手机与移动端」章节（目录同步）：①**分工动线**——完整报告交给定时任务（`scheduler`）在电脑生成、手机上用 Web/HTML 查看，TUI 只做轻操作（开关/清缓存/自检/追问）；②**客户端建议**（Termux / Termius / JuiceSSH / Blink）与三个落地要点（窄屏自动换版面、方向键在部分客户端失效改用快捷键 + `Esc` 双按退出、复制模式）；③**断线后果**（生成中断、已完成报告与缓存不受影响，故推荐重活交给定时任务）；④**窄屏是否看得全**（三档版面 + 40 列底线机检）。TUI 手册窄屏节加互链指向该章节。

## plan-166 `handlers_config` 域拆分收尾（[S] 主循环迁出 + <800 行）✅

**完成（2026-10-20，v0.13.8-dev）**：`[S]` 功能开关面板主循环（343 行，原 `handlers_config.py:242-584`）整体迁入 `handlers_switch.py` 为 `run_llm_modules_panel()`，`handlers_config` 仅留菜单入口薄包装。行数：`handlers_config` **911 → 567 行**（目标 <800 ✓，距 1000 硬上限 433 余量）、`handlers_switch` **107 → 468 行**（目标 <600 ✓）——一次迁移同时命中两条验收阈值。

**Patch 点零改动的关键手法**：迁出代码对 `handlers_config` 的内部符号统一走**函数内局部导入 + 模块属性访问**（`hc._read_llm_settings` / `hc.filter_menu_llm_modules` / `hc._apply_edit` / `hc.refresh_config` / `hc.input_choice`），因此 `src/test/` 里 142 处 `handlers_config.<符号>` 的 patch 目标继续有效，无需像 `[M]` 拆分那样逐用例改指新模块；`handlers_config` 侧显式保留 `filter_menu_llm_modules` 兼容再导出（`# noqa: F401` 并注明用途）。

**同步项**：`handlers_switch` 模块 docstring 改为「面板本体 + 辅助」（原写「主循环仍在 handlers_config」）；`test_handlers_config.py` 的结构断言（分组由 `GROUP_ORDER` 派生）随实现位置改读 `handlers_switch.py`；folders 目录树与 technical 模块表描述更新。


## plan-128 调仓对比页无打印/PDF 入口 ✅

**完成（2026-10-20，v0.13.9-dev）**：`whatif_template.html` 补 `.report-print-btn`（与主报告同参：fixed right 64px / 44×44 触控目标、`--primary`/`--primary-hover` 语义 token、`onclick="window.print()"`、`@media print` 自隐藏），按钮与主题切换并排位于页首右上；`test_whatif_html.py` 新增 `TestWhatifPrintButton`（元素同参 + CSS 规则/44px 触控/token 引用/hover/打印稿隐藏），关态黄金基线 sha256 随渲染产物更新。

## plan-167 报告模板内联色值 token 化收口（W3 观察项） ✅

**完成（2026-10-20，v0.13.9-dev）**：40 处内联 `style=` 色值全部 token 化归零——报告侧新增组件派生 token `--heat-*`（相关系数分档四档）/ `--corr-*`（相关性方向×强度六档 + 文字色）/ `--cell-na-bg` / `--alloc-*` / `--danger-text`（DESIGN.md Colors 组件派生面登记，暗色配对同步：饱和语义块小面积刻意保持、中性面与警示文字按暗色世界调整）；次级灰/占位/边框类改引 `--text-muted`/`--text-faint`/`--surface`/`--border-strong`/`--success`/`--warn-text` 既有 token。W3 由观察升为 E 级 finding（`check-style-guardrails` 收口，`TestInlineColors` 补 finding 断言用例；W4 字号/W5 间距保持观察）。

## plan-168 跨源候选区 bg=3 档事件一致性判据（误合并治理） ✅

**完成（2026-10-20，v0.13.9-dev）**：`news_dedup_rules` 新增 `_EVENT_GROUPS` 事件信号词组（17 组，组内互认：立案/调查/留置/被查同组；刻意排除职务/身份词与泛状态词）+ `share_event_group` 判定；`news_dedup` 主规则 bg=3 下限档要求事件组交集非空才合并（≥4 维持现状，不一致落 cross_skip 保留且不转入 bg=2 梯度防绕过）；词组表入规则指纹（改动自动分锚点时代）；校准工具 `classify_pair` 同步。锚点回放（104,012 对）：bg≥3 域仍合并 4,589 条，bg=3 下限档拦截 2,566 条——拦截样本 10/10 为同主体不同事件（中际旭创暗盘跌 vs 资金抢筹、可口可乐目标价 vs 股价新高、SK海力士盘前跌 vs 上调目标价），合并侧伊朗制裁组/兆易回购/Kimi 融资/熊本地震等真重复无误杀；测试 83 passed（生产判据用校准实证样本 + 工具分类同步用例）。
