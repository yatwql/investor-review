# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.11-dev
> **编号源**：`rf-next = 765`（新增问题取此编号，完成后更新为 +1；已用最大 rf-764，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

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

### 开发期已修复（0.13.10-dev）

（本版开发期已修复项已随 v0.13.10 发布迁入上方归档档案）

### 开发期已修复（0.13.9-dev）

（本版开发期已修复项已随 v0.13.9 发布迁入上方归档档案）


### P3 — 持续监控：文件过长登记表（>500 行观察，脚本域 >400 即入观察 / **>1000 行为硬上限必须拆分**（主程序与脚本）；按距红线余量升序）

> **派生源**：行数与全集以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序、>400 行脚本、>800 行测试文件）；红线（主程序/脚本 >1000 行、测试 >1200 行）由 `check-file-length.py --ci` 自动拦截（豁免路径与本表挂账同步），不依赖本表人工发现新破线者。本表仅登记需跟踪/决策的文件，**触发式处理**：未逼近红线不排期，逼近时按本表拆分建议执行。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件红线体系（主程序/脚本/测试）」决策记录。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线），**当前无挂账项**；警告级全集以 `scripts/check-file-length.py -v` 为派生源，逼近红线（1200 行 / 120 项）时按「被测函数 / 场景类型」拆分为同目录兄弟分片，并同步刷新 `test-coverage.md` / `folders.md` 用例计数。

| # | 文件 | 行数 | 状态 | 拆分建议 |
|---|------|------|------|----------|

| **rf-626** | `llm/prompts_core.py`、`llm/generators.py`、`report/html_writer.py`、`analysis/rebalance.py` | 350 / 444 / 796 / 751 | **临界带四文件登记项**，`-v` 月度复核 | `html_writer`/`rebalance` 逼近 980 行启动拆分（域下沉 + 门面 re-export + 测试 patch 改指持有子模块） |
| **rf-86** | `cache/operations.py` | 739 | 500-1000 可选优化区间，增长偏快，`-v` 按月复核 | 数据结构定义/基金刷新/公共缓存/持仓缓存/缓存清理 5 个职责 |
| **rf-79** | `core/code_utils.py` | 766 | 500-1000 可选优化区间，维持现状，`-v` 按月复核 | 可考虑将 `estimate_market_cap_by_prefix()` 等非核心判定函数移出（不拆） |
| **rf-665** | `config/features.py`、`_doc_drift/_format.py`、`tui/handlers_config.py` | 737 / 558 / 534 | 500-1000 可选优化区间，`-v` 按月复核 | `features.py` 随注册表逐开关增长（每项 ~10 行），逼近 980 行时考虑将 `FeatureSwitchDef` 字段声明/注册表条目下沉独立子模块；另两文件由 `-v` 月度复核 |
| **rf-89** | `report/excel_generator.py` | 659 | 500-1000 可选优化区间，增长偏快，暂维持现状，`-v` 按月复核 | 页签编排可进一步下沉到独立 writer（后续择机） |
| **rf-80** | `report/data_status.py` | 649 | 维持现状（DegradationTracker 单类，内部职责内聚） | DegradationTracker 单类偏大（不拆） |
| **rf-711** | `web/handlers.py` | 852 | 500-1000 可选优化区间，增长较快，`-v` 按月复核 | 生成执行体可下沉 `web/run_generation.py` 子模块（逼近 980 行时启动） |
| **rf-81** | `report/html_renderers.py` | 577 | 维持现状（render 函数同属渲染域） | 所有 HTML render 函数揉合一体（不拆） |
| **rf-85** | `fetcher/fund.py` | 553 | 500-1000 可选优化区间，暂维持现状，若再增则按职责拆分 | 排名/持仓/基准三职责可拆分为子模块（后续择机） |
| **rf-78** | `fetcher/batch.py` | 520 | 维持现状（BatchDispatcher 内聚，复核确认不拆） | BatchDispatcher 本身内聚，可维持现状（不拆） |

## 已解决问题

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


### 开发期已修复（0.13.8-dev）

（本版开发期已修复项已随 v0.13.8 发布迁入上方归档档案）
