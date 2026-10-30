# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.14-dev
> **编号源**：`rf-next = 994`（新增问题提出后更新为 +1；已用最大 rf-993，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-980** | 版切首跑异常长尾（观察项）：v0.16.13-dev 首次生成时「明细装配与建议」10.5s，其余 4 次运行均为 0.45s 量级（同快照其余阶段无异常） | 不构成代码缺陷、暂无复现，保留观察：后续两次版切首跑若再出现则查该阶段内部耗时，连续两次不复现即关闭 |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 7 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐）；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 骨架模板、占位渲染、缓存归因与回写已四簇并存：模板数据/渲染逻辑可下沉子模块（`llm/skeleton_*`） |
| `src/python/tui/handlers_holdings.py` 782 行（红线 1000） | 面板 + 账户/标的选择 + 录入采集 + 价格/净值 + 校验 + 保存写盘六类职责同居一文件：仍在红线内且流程高度耦合（共用 `_Session`），拆分收益暂低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 索引/章节清单/正文三阶取数与负缓存同文件，刚过线：负缓存样板已收口到 `cache/_negative.py`，再涨则按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 再涨即无拦截——要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；当前 6 行余量，下一项报告页改动就会触线 |

## 已解决问题
### 开发期已修复（0.16.14-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-982** | 已解决台账整批漏搬：v0.16.5 起的 9 个发布周期里 53 条 rf 条目全部堆在 `## 已解决问题` 直属层（未写 `### 开发期已修复（X-dev）` 节头），而 `apply_rf_archive` 把「本版无该节」当成「本版无待迁档」、`gate` 同口径判 `absent` 跳过断言——归档文件停在 v0.16.4，10 次发版零告警 | ① `apply_rf_archive` 回落：本版节缺失时把直属层表按本版归位并补出节头（缺节时按直属层表归位）；② `rf_archive_status` 新增 `unfiled` 态（直属层有台账行即报数），`gate` 对 `unfiled` 直接 ERR；③ `check-doc-drift` 分区纪律新增 E 条：已解决区版本节之外出现台账行即提交期报错（`prepare` 之前就拦住）；④ 按 git 首次包含 tag 反查归属版本，补齐 0.16.7/0.16.8/0.16.9/0.16.11/0.16.13 五个批次归档；回归 4 例（直属层归位/幂等/unfiled 状态/真实台账无漏写 + 分区纪律正反例） |
| **rf-983** | 归档批次标题沿用了开发周期号（`## 开发期已修复（0.16.11-dev）`），而归档记录的是**已发布**版本：v0.16.11 已打 tag 发布，读者会把已发布批次读成「开发中」状态；说明行同指 `changelog.md 0.16.11-dev 段`（该段在发布时已改为 `## [0.16.11]`） | 批次标题改为 `## 已修复（X.Y.Z）`（发布版号）、说明行改为「`changelog.md` X.Y.Z 段」；v0.13.x~v0.16.x 既有归档 26 个批次节按同规则迁移（旧式 `## vX.Y.Z 开发期已修复（日期）` 属更早历史形态，保留）；`has_archive_section` / 回归断言 / 脚本文档同步；新增用例断言批次标题用发布版号且不含 `-dev` |
| **rf-984** | 历史台账引用残迹：归档 changelog 段提及的 62 个 `rf` 编号在 rf 台账与归档中无对应条目（rf-37~50、rf-480~508、rf-516、rf-565、rf-711、rf-790、rf-822/823/829、rf-863~866、rf-901~911、rf-943）——这些批次当时以「审查报告」形态记录、未逐条登记台账，编号只散见于 changelog | 按 changelog 段回填 62 条到对应版本归档（v0.8.10 / v0.11.10 / v0.11.11 / v0.12.2 / v0.14.1 / v0.14.5 / v0.14.6 / v0.15.2 / v0.16.2 / v0.16.8），每个批次节标注「补录（2026-10-30）」并说明问题描述未单独留存（修复列即当日变更摘要）；归档头部「归档时间」追加补录戳记 |
| **rf-985** | 台账段序无统一口径也无断言：归档追加与人工补录混用后，review-findings 归档把 0.16.2 批次排到 0.16.13 之后，changelog 归档 v0.2~v0.11 多为倒序（新→旧）、v0.12 起为正序，plan 归档按 plan-N 乱序——同一事实在不同文件里读法相反 | 定口径：version 段（`## 已修复（X.Y.Z）` / `## [X.Y.Z]` / `### 开发期已修复（X-dev）`）与 plan 条目自带完成版本，在**同一文件内**一律升序（旧→新），现行文件与归档文件同口径；① 归一现存文件（changelog 归档 9 份、review-findings 归档 4 份、plan 归档 7 份按口径重排）② `check-doc-drift` 新增第 23 项 `check_ledger_order` 每次提交守卫（现行 + 归档全扫） |
| **rf-986** | 章节改名后未同步配置面板显示名：报告章节已改「财经热点关联分析」，而 `[C]` 面板第 2 项仍叫「市场新闻」，同一章两处叫法不一致（用户按 C 一眼即见） | `config/chapter_registry` 的 `enable_news` 显示名改为报告章节名；同一章的 LLM 增强行（`news_correlation`）显式标「（LLM）」区分本体与增强；config 模板行尾注释、CLI 示例、手册（配置参考/配置手册/FAQ/报告说明/TUI 菜单）同步；回归 1 例锁定「面板章节名 == 报告产物章节名」 |
| **rf-987** | `[C]` 面板长章名把开关状态挤出屏幕：行排版先拼 `名称 + 状态 + 键名` 再整行截断，窄屏（手机终端 34~40 列）上「是否开启」被切掉，用户看不到开关态 | `_format_row` 先按剩余宽度截断名称（预留 光标 + 编号前缀 + 间距 + 状态 + `*`），状态与 `*` 永不被截；同一报告章的 LLM 增强行标签缩短为「财经热点关联分析（LLM）」；回归 1 例按多种列宽 × 置灰 × `*` 断言状态可见 |
| **rf-988** | 状态条中止键与文档相反：`LiveStatusBar` 的 `cancel_hint` 缺省值是已撤回的「q 中止」（有序中止键当前无渠道监听），而 `progress._draw` 直接取该缺省值拼状态条——TTY 上实显「… · q 中止」，用户按 `q` 无任何反应；而 DESIGN-TUI 与两本手册统一写 `Ctrl+C 中断`，且 `status_bar_text` 的 docstring 参数名（`cancel_hint`）与形参（`hint`）不符 | 新增模块常量 `CANCEL_HINT` 作单一来源，`status_bar_text` 与 `LiveStatusBar` 两处缺省同取该常量，docstring 参数名对齐；回归 3 例（状态条缺省 == 文档口径 / 报告器拼接走同一常量 / 模块源码不含无监听方的键） |
| **rf-989** | 配置面板会话是模块级单例，但 conftest 无 autouse 复位：`handlers_config._session` 非空时 `_apply_edit` 必然把写盘记入撤销栈，而直接调 `_apply_edit` 的用例不进面板、不复位——上一用例遗留的会话让本用例的写入记入别人的栈（部分用例靠手写 `_session = None` 绕开，即该缺口的旁证） | conftest 新增 `_auto_reset_config_session`（进/出两侧均关闭会话），与 `_auto_reset_provider_registry` 同习语；回归 2 例（进入用例时会话恒为空 / fixture 进出两侧都复位污染态） |
| **rf-990** | 截图入口 `xlsx` 的 `--rows` 缺省写死 26，与渲染模块 `DEFAULT_MAX_ROWS` 双源（改一处即漂）；同文件里列上限 `26` 以裸数字在判定与文档串各写一遍 | 入口缺省改取 `xlsx_frame.DEFAULT_MAX_ROWS`，列上限收敛为模块常量 `_MAX_COLUMNS`；回归 1 例（解析缺省值 == 渲染常量） |
| **rf-991** | `tui_menu._config_cache` 同为模块级单例且无测试复位（与 rf-989 同类）：首次 `refresh_config()` 后缓存常驻，而页头/菜单渲染走 `get_config_cache()`——不主动 `refresh` 的用例会读到上一条用例 monkeypatch 过的配置快照，断言随执行顺序漂移 | `tui_menu` 新增 `reset_config_cache()`（只丢缓存、不读盘、不动首用检测记忆），conftest 新增 `_auto_reset_config_cache` autouse（进/出两侧复位），与 `_restore_menu_items` 同习语；回归 3 例（进入用例缓存恒未载入 / reset 不触发读盘 / fixture 双侧清污染态） |
| **rf-992** | `[C]` 面板可读性债：`run_report_chapters_panel` 单函数 247 行（项表拼装 + 快照读取 + 开关派发 + 帮助解析 + 整屏渲染 + 主循环混在一起，定位任一行为都要滚完整段），`_format_row` 声明 13 个关键字参数（排版预算与逐行内容混在同一签名，调用点两处各写 13 行） | 拆为 `_ChaptersPanel`（会话态：llm 快照 / 费用摘要 / 撤销会话；方法 `status`·`toggle_chapter`·`toggle_sub`·`build_items`·`on_text`·`help`·`layout`·`render`·`run`），入口函数只剩两行编排；排版预算与行内容分家——`_RowLayout`（整屏不变）+ `_ChapterRow`（逐行变），`_format_row(row, layout)` 两参数。行为不变：既有渲染/写盘/闸门/帮助 113 例全过 |
| **rf-993** | 模块级会话态大量存在但复位口径靠人记：21 类运行期状态（注入的传输层工厂、适配器巡检函数、熔断展示判定、因子目录缓存、新闻源命中快照、季度回放锚点、按键解析残留、防连按保护位、惰性注册标记、各类限速器与统计计数器等）分散在各模块，其中 13 类连复位入口都没有，conftest 仅覆盖了少数早先暴露的那几个——漏接的后果是测试顺序相关（上一条用例注入的桩或残留标志带到下一条，xdist 换分片即随机红），而本地单进程顺序常常看不出来 | ① 补 13 个复位入口（`tui_keys.reset_key_parser_state` / `tui_handlers.reset_busy_state` / `report_artifacts.reset_open_failure_memo` / `fund_style_base.reset_tencent_registration` / `news_aggregator.reset_last_source_results` / `tiantian_holdings.reset_quarter_walk_anchor` / `doctor.reset_adapter_survey` / `http_client.reset_transport_factory` / `source_adapter.reset_adapter_registry` / `factor_catalog_loader.invalidate_catalog_cache` / `eastmoney.reset_eastmoney_pager_limiter` / `akshare_extras.reset_failure_state` / `circuit_breaker.reset_circuit_text`）；② conftest 新增 `_auto_reset_module_state`（进/出两侧，共 21 项，含已有 API 的 8 项）；③ `circuit_breaker` 复位到**导入期基线**而非 `None`（装配期接线不可被测试隔离清掉，否则展示退化成「正常」）；④ 新增契约用例 `test_module_state_reset`：反向枚举 `src/python` 全部 `global` 改写变量，要求所在模块有复位入口**且**被 conftest 调用，导入期常量走带理由的豁免表（并对豁免项做陈旧校验） |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-30）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
