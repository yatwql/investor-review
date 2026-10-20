# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.7]**（2026-10-19）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.8-dev] - 开发中（未发布）

### 新增

- **TUI 交互契约（`DESIGN-TUI.md`）+ 契约结构守卫**（plan-156）：把设计稿定稿为 TUI 侧唯一判据，与 `DESIGN.md` 对称——键分工总表（含每键"禁止用法"）/ 提示三段式四成分 / 默认项与取消标注语法 / 配色一色一职责 / 术语表与四档适用范围 / 反馈与空态口径 / 按键闸门白名单 / 护栏 / Known Gaps；结构测试由 9 例扩到 19 例（必需节含 Colors、四张表列集合、关键口径句成句存在、闸门白名单文档↔代码双向一致）。CLAUDE.md「设计契约」拆为 Web/HTML 与 TUI 两份及各自守卫；developer-guide 触点清单新增「TUI 交互改动」行
- **`?` 帮助全面板可用 + `?键` 单项详情**（plan-158）：`?`（本面板可用键一览）与 `?键`（第 N 项详情）由 `panel_runtime` 统一承接（此前仅 `[S]` 面板有）；`PanelItem` 新增 `detail` 字段，`_emit_help` 以 `hint=item.detail` 渲染，`[P]`（章节切换影响）/`[A]`（模式切换效果）/`[I]`（增删重置作用）/`[M]`（模型·优先级·端点）/缓存面板（清理范围）已填文案，`[S]` 保留 `on_help` 富详情——面板各写业务含义、渲染单源
- **主菜单按任务分组 + `/` 关键词筛选**（plan-164）：19 项平铺改为四组渲染（生成报告 / 数据与查看 / 配置 / 诊断与排查），退出项单列，组标题只降低扫读成本、不改任何按键；`/` 筛选先比按键再比标签文字，筛选态只渲染命中项、`↑↓` 在命中集内回绕、按到隐藏项给单行反馈、`0` 先清筛选
- **击键数与屏幕语义纳入门禁**（plan-165）：三条主路径 E2E 动线（生成完整报告且只重新生成指定模块 / 改一个功能开关并确认生效 / 按级别筛日志）同时断言「击键数不增」+「关键用户词上屏」，契约快照 `tui_flow_contract.json`；击键基线 6 条动线（含 `/` 筛选动线），P0 跑生成主路径 1 条、P2 跑全 3 条
- **FAQ 新增「手机与移动端」章节**（plan-147）：推荐动线（完整报告交定时任务生成、手机看 Web/HTML、TUI 只做轻操作）、客户端建议（Termux / Termius / JuiceSSH / Blink，含方向键失效与 `Esc` 双按要点）、断线后果（生成中断但已完成报告与缓存不受影响）、窄屏可见性；TUI 手册窄屏节互链
- **`switch_panel.render_titled_panel` 共享原语**（plan-148）：宽/中档画盒线、窄档退化为「结构标题行 + 无边框行 + 行内截断」，供所有盒线面板按档位渲染

### 变更

- **「配置」组内顺序调整为 P → S → M → I → A → D → R**：常用操作前置（报告章节 / 功能开关 / LLM 多链），低频操作在后（对比指数 / 匿名化 / 目录信息），刷新配置仍收尾。键位与行为不变，两个手册的主菜单块同步
- **`[D]` 查看配置与目录信息归入「配置」组**：该面板改的是持仓目录/文件名/输出目录（写配置），原分组放在「数据与查看」按功能性质归错了类；现为「配置」组首位（先定目录，再改报告章节/开关等行为），键位与行为不变（`D` 仍是直达键）。两个手册的主菜单块与分组成员说明同步
- **`handlers_config` 域拆分收尾**（plan-166）：`[S]` 功能开关面板主循环（343 行）迁入 `handlers_switch.run_llm_modules_panel`，`handlers_config` 只留菜单入口薄包装——**911 → 567 行**（<800 目标达成）、`handlers_switch` 107 → 468 行（<600 目标达成）。迁出代码对 `handlers_config` 内部符号走函数内局部导入 + 模块属性访问（`hc._apply_edit` 等），142 处既有 patch 点零改动继续有效
- **窄屏口径单源化**（技术债）：`text_layout.MIN_TERMINAL_COLUMNS = 40` 取代 3 处魔法数字（契约与两个机检都引用同一基准）；`switch_panel.narrow_rule(columns)` 收拢长输出面板的分隔线口径（`[V]`/`[H]`/`[3]` 三处各写一遍 → 单源），顺带清掉缓存面板一处 `if False else` 死表达式
- **提示行模板化**（plan-159）：`tui/prompt_text.py`（`panel_prompt` / `keys_help_lines` / `item_detail_lines`）建成后，7 处 `panel_loop` 提示全部由模板产出——「选择 > 」「缓存管理> 」这类连返回键都不说的裸提示消失，提示恒含「动作+示例 · 默认项 · 帮助入口 · 返回键」；机检（AST）断言 `panel_loop` 的 prompt 必须是 `panel_prompt` 调用，模板自带 `wrap_prompt` 折行守住窄屏基准。确认屏维持「问句行 + 键位行」两行式，单行确认模板方向关闭
- **回车语义唯一化 + 屏上键名统一**（plan-157）：回车收敛为「执行本行提示标注的默认项」且必须带动作名——追问屏「回车=结束追问返回主菜单」、报告选择屏「回车=最新报告 / 编号=指定报告 / q=取消」、What-if 生效日「回车=跳过，不做时序回测」、启动向导「回车=跳过」；屏幕上英文 `Enter` 全部改「回车」（同键两名会让用户以为是两个键）。机检新增两条硬规则：屏上禁英文 `Enter`、回车必须带动作名且取消/中止/跳过类语义须置于首句
- **术语改写 + 三渠道同词**（plan-162）：上屏文案去工程内部词——强刷→「重新生成（会调用 AI，计费）」、走缓存→「用已有结果（免费，可能不是最新）」、降级源→「备用源」、配置漂移→「与出厂默认不一致」、降级顺序→「备用顺序」、熔断→「自动重试: 正常/暂时失败」；端点状态由 `core.system_info.circuit_display` 唯一归一，TUI/CLI/Web 共用同一词；日预算超限确认三渠道统一「用已有结果继续」。机检 `TestForbiddenVocabulary`（CJK 术语扫全量字面量剔除 docstring/日志、英文术语仅扫展示型调用、内部值白名单须仍被需要）+ `integration/test_channel_vocabulary.py`。契约写明边界：报告/Web 的「数据降级」指数据质量，日志/注释/FAQ 保留技术词
- **TUI 配色体系（一色一职责）**：首页应用名与版本号橙色粗体（品牌色）、分组标题蓝色粗体（结构色，首页与 `[S]` 经 `text_layout.style_heading` 同源产出）、选中标记焦点青、页头状态行按值着色（正常绿 / 数据偏旧·备用源失败·LLM 未配置黄）、`[OK]`/`[!!]` 补语义色、分隔线与页脚 DIM 降权；非 TTY / `NO_COLOR` 下全量退化无色，语义不依赖颜色。守卫 `TestHeaderBrandColor` + 分组标题着色断言
- **生成确认屏 Y/N 化**：`[L]` 确认屏问句改「是否用已有的 AI 分析结果生成？（`Y`=用已有结果，免费但可能不是最新；`N`=重新生成，会产生费用）」，键位行「回车/`Y`=用已有结果生成 / `N`=重新生成（可选模块） / `q`=中止」——回答键从暗语 `f` 换成一看即懂的 Y/N，默认侧 `Y`（回车即用已有结果）；`f` 保留为 `N` 同义键，词级匹配不变（`of`/`on`/`faq` 不误触）
- **主菜单页脚收敛到 80 列内**：键名改「回车」后页脚变长，会在 80 列终端把「Esc / 0 / X 退出」拆成两行（读起来像两种退出方式）——宽档 `↑↓ 移动 | 回车执行 | 字母/数字键直达 | / 筛选 | Esc / 0 / X 退出 | Ctrl+C 退出`（78 列）、窄档 `窄屏直达 · ↑↓ 选择 · 回车执行 | / 筛选 | Esc / 0 / X 退出 | Ctrl+C 退出`（71 列）
- **`[M]` 多链面板迁出为独立模块**（plan-155 残值交付）：`handlers_config.py` 曾达 1017 行、超单文件 1000 行硬上限，`[M]` 面板整体迁出为 `tui/handlers_llm_providers.py`（菜单入口留薄包装、写盘仍经 `_apply_edit` 局部导入保持 patch 点有效），现 899 行；「`[S]` 主循环域拆分（<800 行）」残值转 plan-166

### 修复

- **LLM 配置热生效链路**（rf-734，P1）：`get_llm_config()` 合并缓存判据补入 `llm_providers.json`（mtime+size——priority 10↔20 等长改写时 size 不变，mtime 为主证据）；`write_llm_providers` 写后主动失效合并缓存；`[M]` 换序及任意配置编辑成功、`[R]` 刷新均清页头状态行记忆（此前 45s TTL 直接吞掉重绘，表现为「换完回首页 / 按 R 都不更新」）。`llm_status()` 新增 `chain_head`（链首线路名，仅 `priority`/`fallback_only` 策略），首页状态行 `LLM ●` 后实时显示当前链首，窄终端自动弃「详情」指引保五语义段不折行。手工改 LLM 三文件均免重启生效，同会话下一次生成即用新链序
- **多链线路顺序三处统一**（rf-737）：排序上提为共享 `config/_llm_providers.order_providers_by_chain`（`priority` 升序、同值保持数组原序），`llm_status()` 与 `[M]` 面板同经此函数，`chain_head` 恒等于 `providers[0]`——此前 `llm_status()` 按数组物理顺序输出、面板按 priority 排序，reorder 后首页 `[1]` 可能是链尾，还与状态行链首自相矛盾；现在首页配置块 / 状态行链首 / 面板编号 / Web 配置面四处一致
- **多链配置文件写回保真**（rf-735 / rf-736）：①缩进不再漂移——`_json_patch` 新增 `_detect_indent_unit`，数组/对象整块重写沿用文件现有缩进单位（此前硬编码 4 空格把 2 空格风格文件写成 4 空格，字段无损但版式跳变）；②头注释不再说谎——`write_llm_providers` 写盘前经 `_neutralize_chain_labels` 把「主：/备：/辅：/次：」线路标注改写为中性「线路：」，并把「顺序即 priority 升序」归正为「链序按 priority 升序，数值小者靠前，与数组项顺序无关」（幂等、仅动注释行），默认模板同步只写稳定事实
- **LLM 费用预估接入重新生成范围**（rf-731，P1）：`llm/cost_forecast.forecast_run_cost` 新增 `force_llm`/`force_modules`（与 `POST /api/runs` 同源 `resolve_force_scope` 归一，非法模块键抛 ValueError）——范围内模块保证重新调用、历史样本含缓存折扣不再适用，按**静态单价口径**计价；范围外维持历史实际费用口径；结果附 `force_scope`/`forced_count`/`forced_low`/`forced_high`，摘要行新增「其中 N 个模块重新生成：¥a ~ ¥b」拆行（默认路径文案不变）。三渠道同源：TUI `[L]` 确认屏选范围后**重打更新预估行**、Web `cost-preflight` 透传 `llm_modules`（非法键 `ok:false` 数据面降级不 500）、CLI `--yes` 透传 `--force-llm`/`--llm-module`；日预算硬闸维持当日累计判定（按投影拦截会误伤「用已有结果」路径）
- **按键闸门收敛**（plan-161）：`press_any_key()` 从 27 处调用点收敛为 5 处长输出闸门（运行日志详情 / 数据源健康历史 / 系统自检结果 / 报告收尾摘要 / 缓存更新结果摘要），其余 22 处（配置面板收尾、缓存清理、What-if 完成、持仓读取错误、调度层取消与异常）一律直接回菜单——取消与错误反馈不再多按一次键。白名单由 `TestPressAnyKeyGateWhitelist` 双向机检（新增闸门即红、失效条目即红）；击键基线同步收紧（`[S]` 只读动线 5→4、`[3]` 缓存面板 4→3）
- **窄屏 40 列底线：修复 + 全景机检**（plan-148）：根因是 `render_panel` 宽度**内容驱动**（下限 41 列内容 + 边框）、不看终端宽度，而 `[P]/[A]/[I]` 无条件调用——40 列手机终端上撑出 49~57 列被硬折成锯齿。三处改经 `render_titled_panel` 按档位渲染；新增全景机检 `test_narrow_panel_render.py`（11 例，`COLUMNS=40` 驱动主菜单与全部面板，逐行断言 `display_width ≤ 40`），新增面板登记即纳入底线
- **长输出面板窄屏降级**（plan-146）：`[D]` 配置入口地图改「菜单键 + 标签」行 + 说明悬挂折行；`[H]` 健康历史压成「时间 / 结果」两行 + 失败源悬挂折行；`[V]` 运行日志按内宽折行（**先折行后上色**，ANSI 不被截断）；`[3]` 缓存统计路径/统计统一折行、分隔标题自适应内宽。修复前四者在 40 列下分别有 11 / 12 / 202 / 10 行超宽（`[D]` 最宽 117 列、`[V]` 最宽 103 列）
- **测试隔离：`MENU_ITEMS` 快照还原**（rf-738）：该模块级可变列表被功能开关裁剪用切片赋值**原地改且不恢复**，任一用例关掉 `doctor_check`/`report_qa` 后，同进程后续用例看到项数不足的菜单——单进程顺序下不暴露，xdist 分片改变顺序后表现为随机失败（实测页脚断言缺退出键）。`conftest.py` 新增 `_restore_menu_items` autouse fixture 逐例快照/还原
- **删除零调用提示模板 `confirm_prompt`**（rf-733，P2）：该单行模板在 `src/python/` 零生产调用（确认类屏已改两行式），删除模板、专属用例与 prompt 契约清单登记（`panel_prompt` 保留）

### 评估未采纳

- **主菜单编号连续化**（plan-160）：原问题「数字键缺 3」已不存在（现为 `1/2/3` 连续）；首页 19 项里 16 项是字母键（主入口），`1/2/3` 只是数据类操作的别名，不构成序列；全量重编号需改约 200 处文档键位并放宽菜单块机检，与 `DESIGN-TUI` Known Gaps 已作的「编号为主入口：未采纳」结论冲突。替代为两条真不变量守卫：首页数字键须 1..N 连续不跳号、面板编号须 1..N 连续（含 `[P]/[S]/[M]` 渲染级断言）
- **Esc 单按退出**（plan-163）：读键层已由 `os.read` + 同 fd `select` 重写，常规链路方向键不再拆包；但极高延迟链路（手机蜂窝 + SSH 多跳）下三字节序列仍可能跨读分节，恢复单按退出会让一次方向键误按就退出程序。**维持「Esc 连按两次确认（3 秒窗口）」**，与 `0`/`X` 单次退出三通道并存；四例回归（单按不退出 / 连按退出 / 确认态解除 / 两档一致）在案

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.7（2026-10-13 ~ 2026-10-19）
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
