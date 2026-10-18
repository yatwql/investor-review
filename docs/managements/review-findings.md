# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.6-dev
> **编号源**：`rf-next = 715`（新增问题取此编号，完成后更新为 +1；已用最大 rf-714，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

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
| **rf-713** | technical.md「写入分派」段残留已删除的 `GROUP_REPORT` 分组名与「功能开关（三组同一路径）」过期表述（注册表现为作用域四分组，doc-drift 未覆盖该行） | 改写为「功能开关（注册表四组同一路径）→ `save_feature_overrides`」并删 `GROUP_REPORT` 名；同类登记表自述行纳入 doc-drift 巡检范围可一并考虑 |


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

- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-17）
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

> rf-708 已修复（2026-10-18）：完成通知 Web 渠道接线——`_run_generation` 改薄包装器（委托 `_run_generation_impl` + `result_box` 回传产物标志），收尾经 `_notify_web_completion` 按 `notify` 配置门控派发（Web 手动生成 + 内置定时调度共用，无人值守定时失败不再静默）；降级摘要单源下沉 `report/data_status.degradation_summary()`，CLI `_collect_degradation_summary` 改委托
>
> rf-709 已修复（2026-10-18）：报告模板 tooltip XSS 纪律——`drawSimpleChart` hover 内容改 DOM API 构建（`createElement` + `textContent`/`createTextNode`，色点走 `style.backgroundColor` 属性赋值），全文 `innerHTML` 清零，模板源结构测试断言防回归
>
> rf-710 已修复（2026-10-18）：遥测 JSONL 保留上限——`jsonl_store` 追加原语增 `max_lines` 尾部保留参数（超限丢最旧行，原子写语义不变）；perf 历史 5000 行 / 健康检查历史 2000 行上限（账本/去重锚点等业务态文件不设，避免丢失跨会话状态）
> rf-712 已修复（2026-10-18）：`prosperity_framework` 转正后未迁组——作用域复核为行动章内嵌评分卡区块，注册表分组机制与诊断 → 分析增强（面板编号/手册分组表/文档归属随迁同步）；requirements R-PF-01 引用的已废弃 `GROUP_STANDARD` 常量改现行 `GROUP_ANALYSIS`，how-to-config 分组计数残留同步修正（详见 changelog）
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
