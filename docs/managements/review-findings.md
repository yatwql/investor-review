# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.7-dev
> **编号源**：`rf-next = 727`（新增问题取此编号，完成后更新为 +1；已用最大 rf-726，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题


### P1 — 高优先：不做的风险高（尽快执行）

> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 入选标准：修复路径清晰、成本可控；rf-114 前置（rf-113 人工验证）已满足。

| # | 问题 | 修复方向 |


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

- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-18）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x 已修复批次与开发期追加（2026-10-03 ~ 2026-10-12）
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

### 开发期已修复（0.13.6-dev）

> 本批摘要已随 v0.13.6 发布迁入 [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md)；此处不再保留。

### 开发期已修复（0.13.7-dev）

> 完整复盘见 `changelog.md` 0.13.7-dev 段；此处仅摘要行。

- rf-719 已修复（2026-10-18）：用户文档残留不存在的交互图表开关 `enable_interactive_charts` 与静态回退描述（FAQ 图表空白排查建议、CLI 手册 `--feature` 示例注释），与「Chart.js 唯一渲染、单文件自包含」口径自相矛盾——FAQ 排查项改按文件完整性/单文件自包含口径，示例注释改按实际开关（数据质量仪表盘）
- rf-720 已修复（2026-10-19）：窄屏直达改造重写首页主循环时宽/中档 `KEY_ENTER` 分支被静默丢弃（Enter 不再执行选中项，宽屏回归）——自审 diff 当场捕获并补回分支；`TestNarrowMainLoopDirectNav` 的宽/窄两档驱动用例锁住重绘次数，同类分派遗漏不再可能静默过审
- rf-721 已修复（2026-10-19）：用户实测报告三连——[S] 面板按数字切换后窄屏不重绘（须再按 `p` 才见结果）、`?4` 说明被写反的重绘标志立刻顶走（宽屏还误提示「状态已更新」）、提示语「? 编号 看说明」占位符写法无示例看不懂；改版为写路径所有宽度即时重绘+反馈带编号、`?` 只读查询窄屏留屏、提示语一句话教主路径（如 3 / ?3 / 0 返回），rf-595「一行反馈」收敛为只读/失败路径
- rf-722 已修复（2026-10-19）：峰谷计价用例 `test_llm_token_usage` 未声明离线——`pricing._is_holiday` 周末短路、仅工作日触达交易日历（缓存空时 akshare 联网），此前 CI 隐式编码探针恰逢北京时间周末从未点燃，周一夜间（7e77c913）首燃被网络守卫拦截（表现为 CI 单点失败、与当批改动无关）；该文件测计量口径而非节假日判定，按「不依赖外部数据的用例显式声明离线」补文件级 `offline_external_sources`
- rf-723 已修复（2026-10-19）：用户实测反馈「主菜单按方向键直接退出程序」——终端把 `ESC [ A` 拆包分节到达时首段 0.3s 窗口超时即判孤 Esc，而孤 Esc 是首页退出别名；首段共聚窗口独立加大为 `_ESC_FIRST_TIMEOUT=0.5s`（续读仍 0.3s），并补 SS3 应用光标序列（`OA`/`OB`）映射（此前落未知键），回归用例锁两窗口下限与 SS3 解析
- rf-724 已修复（2026-10-19）：`_update_json_raw_text` 对 list 值静默不替换——字段级替换只处理 dict（brace 平衡）与标量（正则匹配原文），list 走标量分支匹配不到即无声跳过，写入看似成功实则落空（多链重排首测时 priority 未变即此因）；新增 `_replace_array_block`（bracket 平衡，与 dict 版同构）接入分派，区块内注释随区块刷新、区块外保留
- rf-725 已修复（2026-10-19）：rf-723 加大首段共聚窗口后用户复测「按上下箭头仍退出界面」——更高延迟链路仍可击穿 0.5s 窗口，且孤 ESC 立即退出的语义本身不安全（误判代价 = 退出程序）；改为主菜单 Esc 连按两次确认（3 秒窗口，首按单行提示）+ 拆包残留吸收（迟到 `[` / `O` 前缀由下一次读键读完整段映射回方向键，`input_choice` 同源），误判代价降为「多按一次」且方向键拆包后仍能导航
- rf-726 已修复（2026-10-19）：rf-725 后用户再报「按一次向下键启动了 B 报告」——序列末字节在第二续读窗口（0.3s）超时后迟到，被当成独立字母键 `B` 进入直达分派；新增**半途序列前缀**状态（`_seq_prefix_pending`）：前缀已消费而末字节未到时，下一个字节一律按序列补全处理（能拼出已知序列映射回方向键，否则吞掉为 KEY_UNKNOWN），**永不进入字母分派**——迟到一键最多丢一手，不会误触发功能。拆包防护自此三件套（孤 Esc 迟到前缀吸收 / 半途序列强制补全 / 主菜单 Esc 连按两次确认）
