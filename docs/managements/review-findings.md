# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.11-dev
> **编号源**：`rf-next = 791`（新增问题取此编号，完成后更新为 +1；已用最大 rf-790，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）
| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-790** | 时间戳helper三份拷贝：`core/decision_ledger.py::_now_iso` 与 `core/signal_ledger.py::_now_iso` 逐字相同（2 行），`scripts/_release/_timing.py::now_iso` 语义略异（带时区偏移，供发布台账跨时区对拍）——与 `core/jsonl_store.py` 当时抽出「避免第三份拷贝」的动机同类 | **维持现状**（记录理由）：两处均为 1 行表达式，且 `_timing` 那份**不能**合并（偏移有无是有意区分）；为 1 行表达式新开 `core/timeutil.py` 会引入新模块与目录树/文档改动，收益低于成本。若将来出现第三份 naive 版本再统一 |

### P3 — 持续监控：文件膨胀登记（逼近红线档：主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000；按距红线余量升序）

> **单一事实源**：行数以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序 / >400 行脚本 / >800 行测试）。本表是**逼近红线档的处置登记**——主程序 ≥700、脚本 ≥600、测试 ≥1000（余量 ≤30% 才入表），行数快照随复核刷新；警告级全集不逐项登记，复核以 `-v` 为准。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件拆分」。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线）；≥1000 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

| # | 文件 | 行数 | 距红线 | 状态与处置 |
|---|------|------|--------|-------------|
| 1 | `scripts/perf-view.py` | 983 | 17 | **最先触线**（脚本域）：采集 / 渲染 / CLI 三段下沉，逼近 1000 前必须拆（rf-774） |
| 2 | `src/test/unit/cli/test_cli.py` | 1175 | 25 | 按子命令切兄弟分片（report / cache / whatif / check-sources）（rf-775） |
| 3 | `src/test/unit/web/test_handlers.py` | 1138 | 62 | 按接口族切分（生成 / 配置 / 运行状态 / 日志）（rf-775） |
| 4 | `scripts/check-test-redundancy.py` | 934 | 66 | 八类检查各成子模块（与 finding 分类同构），入口只留编排（rf-774） |
| 5 | `src/test/unit/ui/test_tui_menu.py` | 1131 | 69 | 按菜单块切分（主菜单 / 配置子菜单 / 开关面板）（rf-775） |
| 6 | `src/test/unit/scripts/test_trace_check_scripts.py` | 1122 | 78 | 按守护拆分（code / doc / 日志支路）（rf-775） |
| 7 | `src/python/web/handlers.py` | 910 | 90 | 生成执行体可下沉 `web/run_generation.py`，逼近 980 行启动（rf-711） |
| 8 | `src/test/unit/handlers/test_handlers_config.py` | 1102 | 98 | 按配置域切分（标量 / LLM / 章节 / 开关）（rf-775） |
| 9 | `scripts/check-doc-traces.py` | 901 | 99 | 入口已薄（实现拆 `_traces_doc/`），再增检查按族下沉（rf-774） |
| 10 | `src/test/unit/report/test_fund_performance.py` | 1091 | 109 | 按能力切分（评级 / 业绩 / 持仓）（rf-775） |
| 11 | `src/test/unit/report/test_html_report_structure_content.py` | 1076 | 124 | 按章节段落切分（rf-775） |
| 12 | `src/test/unit/core/test_reader.py` | 1064 | 136 | 按读取 / 列校验 / 异常分片（rf-775） |
| 13 | `src/test/unit/scripts/test_check_doc_drift.py` | 1061 | 139 | 按机检项族切兄弟分片（trace / redundancy / crosscheck 已有先例：本章节测试与实现模块同源拆分）（rf-787） |
| 14 | `src/test/unit/report/test_summary.py` | 1057 | 143 | 按汇总块切分（rf-775） |
| 15 | `src/test/unit/llm/test_fact_checker.py` | 1047 | 153 | 按校验规则族切分（rf-775） |
| 16 | `src/python/config/features.py` | 840 | 160 | 注册表逐开关增长（每项约十行）；逼近 980 时把注册表条目与定义下沉（rf-665） |
| 17 | `src/test/unit/analysis/test_rebalance.py` | 1039 | 161 | 按成本分档 / 偏离度 / 告警切分（rf-775） |
| 18 | `src/test/unit/report/test_orchestrator_generate_report.py` | 1036 | 164 | 按管线阶段切分（rf-775） |
| 19 | `src/test/unit/fetcher/test_chain.py` | 1025 | 175 | 按链路 / 熔断 / 回退切分（rf-775） |
| 20 | `src/python/report/html_writer.py` | 799 | 201 | 域下沉 + 门面 re-export（测试 patch 改指持有子模块）（rf-626） |
| 21 | `src/python/core/code_utils.py` | 788 | 212 | 非核心判定函数（`estimate_market_cap_by_prefix` 等）可移出；当前维持（rf-79） |
| 22 | `src/python/llm/api_base.py` | 770 | 230 | 端点构造 / 请求发送 / 响应解析三段，逼近 900 首选下沉端点族（rf-773） |
| 23 | `src/python/analysis/rebalance.py` | 751 | 249 | 按「成本分档 / 偏离度 / 告警」下沉（rf-626） |
| 24 | `src/python/report/_report_generation.py` | 751 | 249 | 按「数据装配 / Excel 落盘 / HTML 落盘」下沉（rf-773） |
| 25 | `src/python/cache/operations.py` | 739 | 261 | 五职责待下沉（数据结构 / 基金刷新 / 公共缓存 / 持仓缓存 / 清理）（rf-86） |
| 26 | `src/python/report/orchestrator.py` | 734 | 266 | 按「章节调度 / LLM 编排 / 产物落盘」下沉（rf-773） |
| 27 | `src/python/config/_validation.py` | 723 | 277 | 校验规则族按「标量 / LLM / 章节」三域分文件（rf-773） |
| 28 | `src/python/report/fund_performance.py` | 722 | 278 | 按「评级 / 业绩计算 / 持久化」下沉（rf-773） |
| 29 | `src/python/report/holdings_detail_sheet.py` | 716 | 284 | 页签写入器，按分区块下沉（rf-773） |
| 30 | `src/python/analysis/prosperity_scoring.py` | 711 | 289 | 按「阈值表 / 评分 / 诊断」下沉（rf-773） |
| 31 | `src/python/providers/news_dedup_rules.py` | 710 | 290 | 去重规则表按来源分文件（rf-773） |
| 32 | `scripts/release.py` | 709 | 291 | 已拆 `_release/` 包；入口为 CLI 壳 + 命令编排，维持（rf-774） |
| 33 | `scripts/check-style-guardrails.py` | 636 | 364 | E / W 两级检查可分层（rf-774） |
| 34 | `scripts/perf-test-report.py` | 635 | 365 | 场景构造 / 指标计算 / 报告渲染三段（rf-774） |

> **已决策「维持现状」（已降到逼近档以下，不拆理由保留，行数随 `-v` 复核）**：`report/excel_generator.py`（rf-89，页签编排后续可下沉）、`report/data_status.py`（rf-80，DegradationTracker 单类内聚）、`report/html_renderers.py`（rf-81，渲染域同源）、`fetcher/fund.py`（rf-85，排名 / 持仓 / 基准三职责择机拆）、`fetcher/batch.py`（rf-78，BatchDispatcher 内聚）、`tui/handlers_config.py` 与 `scripts/_doc_drift/_format.py`（rf-665，随 `features.py` 注册表增长但各自域内聚）、`llm/prompts_core.py`、`llm/generators.py`（rf-626，提示词/生成器按模块分文件）。

## 已解决问题

### 开发期已修复（0.13.11-dev）
| # | 问题 | 处理 |
|---|------|------|
| **rf-756** | 发布归档迁移（人工步骤）无机检：占位声明「已随 vX.Y.Z 发布迁入」与归档正文脱钩（rf-755 即由此漏掉第八批 11 条），删台账行与写归档两动作零一致性校验 | `_ledger` 族（check-doc-drift）新增迁档占位↔归档节断言（第二十项）：review-findings 每个 `已随 vN.N.N 发布迁入` 占位，对应 archived_review-findings.{N.N}.x.md 必须存在含该版本号的二级标题归档节——占位已写而归档正文缺失即当场报出；用例覆盖缺节/缺归档文件/旧式 -dev 节标题/同版本多占位去重/真实仓库一致性 |
| **rf-757** | folders.md 树描述写死易漂移计数（开关项数/菜单项数/测试文件数等 14 处）且无机检——实现演进（加开关/菜单/文件）时描述静默过时 | 已改定性措辞；`check-doc-drift` 新增第二十一项「树描述计数禁令」（阿拉伯数字+量词入检、docs/archive 记录域豁免、中文数词设计常量不入检），用例覆盖文件行/目录行/豁免域/中文数词放行/真实仓库一致性 |
| **rf-763** | 代码类型判定中心化约束违反：`core/holding_status.py::classify_code_format` 自建 `("sh", "sz", "bj")` 前缀元组剥离交易所前缀——与 `code_utils.py` 前缀知识重复，新增交易所前缀时必漏改一处（两处口径一致故无行为缺陷） | `code_utils.py` 新增 `EXCHANGE_PREFIXES` 常量与公开 `strip_exchange_prefix()`（只剥前缀不校验码位，供需自行判定形态的调用方复用），`_strip_prefix` / `to_fmp_symbol` / `holding_status` 三处改为复用；反向机检由 `TestExchangePrefixCentralized` 钉住「前缀元组唯一定义点」（全仓扫描非 code_utils 模块不得自建该元组） |
| **rf-764** | 原子写入边界外的健壮性缺口：`report/whatif_writer.py` 写「调仓模拟.html」最新版与归档版均直写 `open("w")`，未复用同包原子写原语——进程中断会留下半写截断的 HTML | whatif_writer 双产物改用 `html_save._write_html_atomic`（tmp + `os.replace` + 中断收口登记），与主报告口径对齐；新增中断场景回归用例（替换抛 `KeyboardInterrupt` 时既有最新版不被截断、只残留 `.tmp`）与「两次落盘均经原子原语」断言 |
| **rf-758** | 演进对照「当前开发版」列新鲜度无机检：数据行与列头日期均无校验（evolution 为发布链人工步骤，跳过即以过期快照发布——会话内两次标记为已知缺口） | `release.py gate` 前置断言：列头「本次重跑时的工作区」日期须等于当日——evolution 原子同写表头与数据行，日期一致即传递性关闭数据行新鲜度缺口；过期报出并指路重跑 evolution；纯函数 + 三用例（当日放行/过期报出/列头模式缺失报出），CLAUDE/testplan/developer-guide 发布编排描述同步 |
| **rf-759** | rf-758 的 gate 新鲜度断言直读真实 folders.md + 墙钟，TestGate 编排用例在不同时区/日期的 CI 上随机红（本地 UTC+8 已过零点、CI UTC 仍是前一日 → 新鲜度先行拦截返回 2，回归/守护一个不跑）——测试未与仓库文件状态/时钟隔离 | TestGate 增加 autouse 夹具将新鲜度视为通过（编排用例只验序列）；新增 `test_gate_stops_on_stale_evolution` 单独覆盖新鲜度失败即中止且不触发子进程；新鲜度纯函数行为仍由 TestEvolutionFreshness 覆盖 |
| **rf-760** | folders.md 目录树描述残留架构约束代号（新闻召回解耦/pipeline_data 契约两类共 4 处）/来源叙述（从 X 拆出共 6 处）/§ 引用/第三方版本号与体积计数共 14 处；根因是机检盲区——目录树整块在围栏代码块内，`scan_file` 先跳过围栏再判树行，声称「树行照检」的规则从未生效 | `check-doc-traces` 围栏内 folders.md 树行照检（围栏跳过仅针对非树行内容）；树行按路径分域（docs/archive/ 子树=归档记录域仅复盘叙事、docs/plan/ 子树=任务记录域照检章节+约束代号）；树行专属无后缀来源叙述补强（「从 framework 拆出」类）；14 处描述改语义化（只讲文件职责）；单测覆盖围栏树行检出/非 folders.md 围栏维持跳过/两子树分域/来源叙述补强，developer-guide 同步 |
| **rf-761** | folders.md 归档子树版本目录块乱序：0.9.x 后直接接 0.13→0.12→0.11→0.10 倒序——三次发布（v0.11/v0.12.1/v0.13.4 的归档落盘）均把新块插到同一锚点（v0.9.x 块尾、0.10.x 块首之间），且 `check_dir_tree` 仅做条目集合双向比对不看顺序，顺序错误零机检 | 四块重排为版本升序（`└──` 末块标记随迁 0.13.x）；`check-doc-drift` 目录树检查新增「版本目录块升序」断言（同父目录 vN.N.x/ 按 (major,minor) 数值升序、兼出重复块），用例覆盖升序放行/倒序报出/字典序陷阱/多父目录独立/真实仓库一致性 |
| **rf-762** | developer-guide「check-doc-drift 十六项检查」清单停留在 16 项（脚本实际 21 项，17 章节-区块矩阵/18 手册菜单块与返回键/19 需求菜单表/20 迁档占位/21 树描述计数缺列）；technical.md 约束外参照句同源陈旧（「十项逐条对账」）——项清单为手工维护、无机检 | developer-guide 清单补齐至 21 项并把「十六项」措辞改为与脚本 docstring 同源；technical.md 句改「逐项对账」（项数改派生措辞）；后续如再增检查项须同步此三处（脚本 docstring / developer-guide 清单 / 守护描述括号） |
| **rf-765** | review-findings 分区顺序失效：三个「开发期已修复」节（0.13.11 / 0.13.10 / 0.13.9）夹在「当前待处理问题」的 P2 与 P3 之间，0.13.8 占位又落在「归档档案」索引之后——已修复项被读成待处理、归档索引被切在两段占位中间；另 P3 登记表表头与首行之间多一空行，整表在渲染上断裂为「空表头 + 裸行」 | 重排为待处理（P1 → P2 → P3）→ 已解决（开发期已修复 0.13.11 → 0.13.8，再归档档案）；去掉空行，表恢复正常渲染 |
| **rf-766** | P3「文件过长登记表」与其声明的派生源 `check-file-length.py -v` 脱节：一是行数陈旧（html_writer 796→799、code_utils 766→788、features 737→840、handlers_config 534→573、web/handlers 852→910）；二是声称登记「>500 行主程序 / >400 行脚本」全集，实际只有 10 行，而实测主程序 >500 有 44 个、脚本 >400 有 14 个；三是表头写「按距红线余量升序」而实际行序既不升也不降 | 登记口径改为「逼近红线档」（主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000，余量 ≤30% 才入表），警告级全集明确指向 `-v` 不逐项登记；一张表逐文件、按距红线余量升序重排，行数按 `-v` 快照刷新（rf-773/774/775 补登三域漏登文件） |
| **rf-767** | `plan-169`（日志统一约束机检守护）已随实现同批完成并从 plan.md 移除，但归档缺失：编号已消耗（`plan-next` 已推至 170），`archived_plan.0.13.x.md` 无该条——已完成项无从追溯，违反「完成态归入 archived_plan.*」 | 在 v0.13.x 归档补 plan-169 条目（动机/动作/落地形态），与 changelog 日志守卫段对齐 |
| **rf-768** | plan-92「Excel 纯数字呈现」现状句写「17 页签全为静态数字与文字」，与报告章节注册表实际 19 项不符（README 同处写 19）——同一事实两处不一致 | 改为「19 页签」，与注册表/README 对齐 |
| **rf-769** | testplan §6.4「补充自动化门禁」列表编号重复：`15.` 出现两次（TUI 人因门禁、whatif CLI），其后 16~18 全部错位——引用该清单某一项必然指错 | 重排为 15~19 连续编号 |
| **rf-770** | llm-technical.md 目录把「附录 A/B/C」错缩进一层挂在「13. 集成点」下，且缺「附录」父项——与正文 `## 附录` → `### 附录 A…` 的真实层级不符；另目录深度不一致（仅 API 调用层列子节，其余按章级条目呈现） | 补「附录」父项、把三个附录条回退到与章同级缩进；目录统一按「章级条目 + 附录子项」两级深度 |
| **rf-771** | 发布链无耗时埋点：prepare/refresh/evolution/gate/publish 每步只在终端打印、不落盘，整改（结论缓存 / 门禁并行 / bench 并行采集）的效果无法跨版本对拍，只能现场重测 | 新增 `_release/_timing.py`（分步计时 + JSON 记录），`release.py` 每命令尾行打印摘要并追加 `logs/release.jsonl`（git 忽略域，写失败只提示不改退出码）；gate 回归/十守护/护栏、refresh bench/collect/sync、publish P1 verify、evolution 快照与同步均记为分步 |
| **rf-772** | `release.py refresh` 的 bench 跑全量 14 档（串行 5.5 min、2 路采集 3.2 min），占单次发布机器时间约 75%，而门禁本身（regression 13s + 十守护 0.3s + 设计护栏 0.1s）已降到秒级——时间花在与发布判定无关的重复模式上 | refresh 默认只测发布口径四档 `unit` / `dev-verify` / `regression` / `integration`（未测模式按 `--update-docs` 既有口径保留上次实测，不写脏），新增 `--full-bench` 全量入口；计数由 `collect-test-coverage.py --update-docs` 独立回写不受影响 |
| **rf-773** | 主程序逼近红线档（≥700 行）新增八文件未登记：`llm/api_base.py`、`report/_report_generation.py`、`report/orchestrator.py`、`config/_validation.py`、`report/fund_performance.py`、`report/holdings_detail_sheet.py`、`analysis/prosperity_scoring.py`、`providers/news_dedup_rules.py` | 入 P3 逐文件登记并给处置方向（域下沉口径），非立即拆分 |
| **rf-774** | 脚本逼近红线档（≥600 行）四文件未登记：`perf-view.py`（983，距红线 17 行）、`check-test-redundancy.py`、`check-doc-traces.py`、`release.py` | 入 P3 逐文件登记；`perf-view.py` 标为最先触线、拆分前置 |
| **rf-775** | 测试逼近红线档（≥1000 行）十三文件未登记，而 P3 原注称「当前无挂账项」——测试域已实际进入余量 ≤200 行区间 | 入 P3 逐文件登记（按职责/段落分片的拆分方向），并修正 P3 测试档口径说明 |
| **rf-776** | 正文「菜单 `X`」引用与 `tui_menu.MENU_ITEMS` 脱钩（doc-drift #18 只校验手册 code block）：缓存管理由 `[4]` 改为 `[3]` 后 12 处正文仍写 `[4]`（faq 6 / how-to-config 1 / how-to-use-cli-mode 1 / how-to-use-web-mode 2 / technical 1 / testplan 1 / requirements 1）；持仓目录·文件名·输出目录三项收进 `[D]` 二级面板后 3 处仍写裸「菜单 `C`/`F`/`O`」；faq 机制与诊断块序号写「第 37 项」（真值 34，开关增删后静默过期）。读者按提示在主菜单找不到入口 | 12 处改 `[3]`（区间改 `[1]~[3]`）、3 处改「菜单 `D` → `C`」、序号改 34；`check-doc-drift` 第 18 项扩「正文菜单键引用」分支（合法域 `MENU_ITEMS` 键 ∪ `0`，`[D]` 二级键改由 `handlers_config.CONFIG_DIR_INFO_KEYS` 单一登记并要求 `D` → 写法），裸键形态须跟空白/标点以免误捕「主菜单 code block」的 `c`（自审 rf-776） |
| **rf-777** | `reports-instruction.md` 可见性规则总览表 type 行错配：表中 `financial_report` / `financial_indicator` 并非 type（是 `fundamental_snapshot` 型下两个章节键），真正存在的 `schedule_replay` 反而漏行——行数恰好仍为 10，故「划分为 10 组」计数断言与注册表 10 个 type 都不露馅，doc-drift #1 只比章节表不碰此表 | 两行合并为一行 `fundamental_snapshot`（注明两章各自按数据契约判定）、补 `schedule_replay` 行、下注同步改写；`check-doc-drift` 第 1 项扩「可见性表 type 行 ↔ 注册表 type 集合」双向对账（缺行/多行/重复三型），新增 4 例单测（自审 rf-777） |
| **rf-778** | `how-to-config.md` §O 缓存分组表两组清单均不全（真值 `core/data_registry.py`：`preload` 组实际 11 项、`refresh` 组 18 项）：`preload` 漏「生成后自检」「持仓变动复盘归因」两项 LLM 模块，`refresh` 漏「基金申赎费率」「指数估值历史」——按表清缓存会留下陈旧条目。该表无机检（项名为中文自由文本，与注册表名多有无害差异如「基金经理」↔「基金经理数据」） | 两组清单按注册表补齐；机检暂不引入（需中文名别名表，误报风险高于收益），在改表处与注册表键 `cache_groups` 双向核对，登记为下次动该表时的核对点（自审 rf-778） |
| **rf-779** | 历史快照保留期在三处写成 60 天 / 12 个（`reports-instruction.md` 生命周期行、`how-to-use-tui-menu.md` B/L 快照说明、`report/history_snapshot.py` 参数 docstring），真值 `constants.HISTORY_SNAPSHOT_RETENTION_DAYS = 180` / `MAX_COUNT = 365`——文档承诺 60 天清理、实际保留 180 天，用户按文档会误判目录体积与清理时机 | 三处改 180 天 / 365 个，docstring 与常量对齐（自审 rf-779） |
| **rf-780** | 同一个缓存分组（`preload`：价格 + 指数）三种称呼并存：TUI 菜单标签「行情类缓存」、TUI 上屏输出「持仓缓存更新完成」与函数名 `update_position_cache`、FAQ 与 LLM 手册「持仓缓存」、CLI 选项 `--update position`——菜单说 A、按下后打印 B，用户无从判断是否同一动作 | 上屏词与 docstring（`handlers_cache.py` / `cache/operations.py`）统一为「行情类缓存」；FAQ 4 处、`how-to-config-llm.md` 2 处、CLI 手册 `position` 说明与 requirements 菜单表 1 处同改，`position` 选项名作为历史命名在图注说明（自审 rf-780） |
| **rf-781** | 配置类文档四处与实现不符：①`how-to-config-llm.md` pricing 示例两块都缺 `holiday_always_idle`（代码默认 `true`，正文却提到）；②faq 称 `.gitignore` 仅 `config.json`/`llm_settings.json` 特例放行，实际还有 `llm_providers.json` 与 `data/knowledge/`；③`how-to-use-cli-mode.md`「Provider Chain 已内置三次重试 / 自动重试（3 次）」——`fetcher/chain.py::_TRANSIENT_RETRY_ATTEMPTS = 1`（同源额外 1 次），整链源数 1~4 不等；④`config/features.py` 分组注释「呈现与体验（2 项全默认开）」，摘除 `enable_interactive_charts` 后该组仅 `metrics_enabled` 一项 | ①②③④ 逐项改正（示例补 `holiday_always_idle`、gitignore 描述补全、重试语义按代码表述、注释改「1 项」）（自审 rf-781） |
| **rf-782** | 定价表口径缺一句兜底说明：文档称「内置所有支持模型的定价」，而 `core/constants.py::MODEL_PRICING` 另有 6 条模型族前缀价（`claude-sonnet-4-` / `gemini-2.5-` 等）供带日期后缀的未列变体自动计价——读者按表核价遇未列模型会以为无定价 | 定价表后补一句族前缀兜底说明（不单列、不覆盖具体模型价）（自审 rf-782） |
| **rf-783** | Web「配置编辑」面板分组数三处说法互不相同且漏一组：`how-to-use-web-mode.md` 写「9 组」（表内只有 9 行、缺「LLM 多链线路」组，而后端 `web/config_edit.py` 实际下发 `llm_providers` 面、前端 `main.js` 也渲染该组）、`how-to-start.md` 写「8 组」并仍按「实验性功能/常规开关」两分（开关面按作用域四组下发后该二分已不存在）、`testplan.md` 写「8 块可编辑项（7 个可编辑面，功能开关面拆成两块）」。用户照文档找多链线路排序组会找不到 | 三处统一为「10 组 = 7 个可编辑面（路径/章节/匿名化/指数池/LLM 开关/LLM 多链线路/功能开关面）+ 功能开关面的作用域四组」，web 手册分组表补「LLM 多链线路 ↔ `[M]`」行（自审 rf-783） |
| **rf-784** | `requirements.md` §3.2 菜单表 P 行称「报告章节与增强的 **8 项**开关归菜单 `[S]`」——分析增强 16 + 独立章节与回放 5，实为 21 项（TUI 手册同一处写 21），8 是两组拆分前的口径 | 改为「21 项（分析增强 16 + 独立章节与回放 5）」，与 TUI 手册同步（自审 rf-784） |
| **rf-785** | 文档点名了代码中已不存在的符号（散文层陈旧，断言扫描与路径扫描都不覆盖）：`technical.md` 把「报告章节与增强开关」的分组写作 `GROUP_REPORT`——该常量已随作用域四分组下线（单测 `test_handlers_config` 明确断言 `features.py` 不得含 `GROUP_REPORT`），现为 `GROUP_ANALYSIS` / `GROUP_STANDALONE` 两组；`DESIGN.md` 称样式护栏存量白名单登记于 `_W1_EXEMPTIONS`，实际常量为 `_RAW_COLOR_EXEMPTIONS`（条目数 15 与文档一致，仅名不符） | 两处符号名改按现行代码；以「文档反引号标识符 ↔ 代码符号索引」做一轮全量对码（23 份文档，53 个未解析候选逐条人工判读：环境变量/模板占位/外部项目引用属合法，其余 2 处即本条）（自审 rf-785） |
| **rf-786** | 文档核对方法论缺口：一次完整核查该按什么层次分工、机检覆盖不到的部分用什么手段替代、发现该往哪记——均无成文，导致每次核查靠临场发挥，且中间底稿（`docs/tmp/` 抽取清单）与正式台账可能各存一份同一批发现，日后两边不一致 | `developer-guide.md`「check-doc-drift」节后新增「文档核对方法」段：四层分工表（机械/结构/断言/散文）、未绑定断言的抽取对码写法与四类对码表、散文层标识符对码与豁免域、两条输出纪律（同类漂移二次即落成 doc-drift 子分支且挂现有编号不加项数；台账唯一、`docs/tmp/` 底稿闭环即删）、以及「不得笼统宣称已全核，按层说明覆盖范围」的边界声明（自审 rf-786） |
| **rf-787** | `test-coverage.md` 覆盖项数陈旧且无本地拦截：计数是 pytest 收集派生量，只有 `check-doc-drift --with-test-count` 会校验（CI master 档），而 pre-commit 的 `--sync` 只回写 folders 统计行——每次「加完测试就提交」都会把计数写旧，到 CI 才红（本次实测差 8：7394→7402 / 10797→10805）；该状态在本次核查前已存在 | 计数按收集快照回写（7 处）；pre-commit 分域调度补一条：暂存含 `src/test/` 时 `--sync` 追加 `--with-test-count`，把「测试变更加了用例没刷计数」变成提交期可读到 action 的 finding（热缓存 0.8s，仅在测试变更时付出）（自审 rf-787） |
| **rf-788** | 发布耗时台账 `logs/release.jsonl` 三处不符既有约定：① **无界增长**（每跑一次 release 子命令追加一行，永不裁剪）；② 直接 `open(..., "a")` 写**违反原子写入约束**（崩溃可留半行，同类问题此前已在调仓报告落盘上修过）；③ 全仓已有 JSONL 原子追加单一原语 `core/jsonl_store.append_jsonl_atomic`（该模块 docstring 明确写「避免第三份拷贝」），此处却自写一份 | `append_record` 改为委托共享原语并加 `max_lines=500`（一次发布约 7 条，覆盖数十次发布），写盘失败如实抛出让调用方打 `[!]`；`_finish_timing` 捕获面补 `ValueError`（序列化失败同属观测面降级）；新增 2 例单测（有界+原子、失败上报）（自审 rf-788） |
| **rf-789** | `[D]` 面板二级键双处登记：显示名/处理器写在函数内的 `_handlers` 字典，键集合另写成 `CONFIG_DIR_INFO_KEYS` 元组供 doc-drift 校验——增删子项只改一处即静默漂移（面板少一项，或机检认为某键不存在而误报正文） | 收敛为模块级单一登记表 `DIR_INFO_ITEMS`（键 → 显示名 + **处理器属性名**）并派生 `CONFIG_DIR_INFO_KEYS`；处理器按名在分发时从模块全局取（直接登记函数对象会让 `@patch` 对模块属性的打桩静默落空——本次重构首版即踩中，用例当场红）；新增 2 例单测（登记表单源 + `M` 只读索引入口分发）（自审 rf-789） |

### 开发期已修复（0.13.10-dev）

（本版开发期已修复项已随 v0.13.10 发布迁入上方归档档案）

### 开发期已修复（0.13.9-dev）
（本版开发期已修复项已随 v0.13.9 发布迁入上方归档档案）

### 开发期已修复（0.13.8-dev）
（本版开发期已修复项已随 v0.13.8 发布迁入上方归档档案）

### 归档档案
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-20）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) 
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md)
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md)
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md)
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md)
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md)
