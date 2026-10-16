# 变更日志归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布当日并入，0.13 系列首份）
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.13.0（2026-10-13）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.13.0] - 2026-10-13

### Fixed

- 智囊团深度复盘：结构化决策头机器载荷（`决策头：{...}` 单行 JSON）不再直出 HTML 报告正文与 Excel「智囊团深度复盘」页签——报告装配点在决策登记完成后对 LLM 内容四元组单点剥离（`strip_structured_header`，与解析侧共用标记常量与括号配对扫描），缓存保留原始内容；补正常形态/畸形矩阵单测与装配接线测试。

- 报告图表图注（图注纪律）：corrRollingChart 补 `.chart-caption` 图注；新增 `.note-caption` 类承载表格/统计口径说明附注（与图注同视觉档位、语义分离），回撤区 4 处误用图注类名的说明块改用——`.chart-caption` 现专属图表，由结构契约测试全量机检。
- 东方财富行业/概念接口（push2）：请求前节流从自建随机 sleep 迁移为 `RateLimiter` 原语（登记键 + 最小间隔 0.1s + 抖动 0.5，惰性单例 + 测试隔离 reset），节流算式纳入 C27 单源纪律，与 cninfo/datasink/eastmoney 分页同模式。
- 新闻抓取预算：`per_source = max(500, top_n×2)` 折算收敛为 `fetcher/news.py::news_fetch_limits` 单源函数（抓取预算单源纪律），缓存层与报告层两处内联计算收编，调用方不再各自复制算式。
- 调仓 What-if 回测窗口：`compute_backtest_days` 的自然日×5/7 近似折算替换为交易日历精确计数（交易日历单源 `count_trading_days_elapsed`，日历不可用时内部回退排除周六日），长假前后的窗口请求天数不再偏差。
- 代码形态判定：A 股六位代码/美股字母代码判定收敛为 `core/code_utils` 语义原语（`is_six_digit_code` / `is_letter_based_code`），配置校验、天天基金申购、因子指标、组合历史、费用估算五处内联判定收编（代码形态判定中心化）。

### Changed

- 发布门禁扩展：`release.py gate`（P2）在十守护之后追加 `check-style-guardrails --ci` 设计护栏段（E 级 finding 拦截 / W 级观察统计随发布留档）——开发期快反馈仍由 unit 测试承担，护栏不入十守护清单与 pre-commit/CI guards；gate 测试补护栏调用与失败传播 2 例。
- 样式护栏观察项治理（`plan-121`）：`check-style-guardrails.py` 裸色值 132→0、圆角档外 8→0——修 HTML 数字实体误报（`&#9888;` 等）、豁免域精确化（引号区间行 / var 回退 / print 块 / 暗色 override 块，与契约护栏例外同源）、存量白名单 15 条带理由登记；模板等值收敛（徽章 10px→999 胶囊档、source-tag 3px→4px、whatif hover→var(--table-hover)）；W 级管控三定档（永不自动转阻塞/白名单只减不增/收敛优先于豁免）+ 观察数基线断言机制化（`TestBaselineNoGrowth`）。

- 技术设计文档：架构约束表增「env 初始化期注册」例外脚注（`html_jinja_env.py` 无状态过滤器注册与 fail-closed 默认值合法，渲染期数据仍禁入全局）；新闻抓取预算/交易日历约束行补单源指引与 whatif 回测接入点；`schemas/history.py` 模块 docstring 修正为数据契约职责（原子写入由 `report/history_snapshot.py::save` 经 `core/atomic_write` 承担）。
- 自审挂账：style 护栏观察项（裸色值/圆角档位外，E 级不判 finding）纳入 `plan-121` 治理——退出判据为观察期（≥2 个发布版本）观察数不再增长 + 存量收敛计划或逐条白名单。

## [0.13.1] - 2026-10-14

### Added

- 报告「投资分析汇总」市场温度行下新增**计算逻辑**与**分级标准**两行说明（低估＜30 分 / 合理 30~70 分 / 高估＞70 分，边界值归合理档；三因子权重 50%/30%/20%，波动率反向越波动越冷）——文案由计算层权重/阈值常量单源派生，改常量自动跟随；展示构建器缺字段时两行静默省略（旧契约兼容）。

### Changed

- 脚本目录优化批次：`release.py` 拆 `_release/` 内部实现包（共享原语/版本号纯函数/changelog 归档/演进快照四模块，入口保留 CLI 与命令壳，869→517 行）；文档路径常量上收 `_checklib`（5 检查脚本与 doc-drift 内部包的内联拼路径收编）；`check-script-contract` 规则② 增加 `args.verbose` 消费侧 AST 检查（防空开关，`check-svg.py` 的空 -v 同步实现消费）；三守护同次运行双扫消除（doc-traces 四遍目录走查收敛为一遍 / doc-drift `-v` 模式二次全量读复用首轮 / semantic-index 指纹面与扫描面同源）；演进统计对测试文件的全量二次读消除；三个 sh 启动垫片加 `set -euo pipefail`。

## [0.13.2] - 2026-10-15

### Added

- **持仓成本区间位置列（plan-90）**：「持仓明细与分类」页签市值明细与分类汇总两区块末列追加「成本区间位置」两列（近 20 / 260 交易日价格区间百分位，≈1 追涨嫌疑、≈0 低位布局），填补只维护持仓、无流水时「买入时机相对历史区间」的量化空白。纯计算 `analysis/cost_position.py`（clamp/中性值/窗口切片）+ 编排 `report/cost_position.py`（复用既有行情历史链，不新增数据源；长窗口一次取数、短窗口同源切片）；功能开关 `cost_position`（默认开，`GROUP_ANALYSIS`），行情缺失静默隐列不阻断报告；口径脚注随呈现（成本均价近似买入价 + 窗口参数 + 公式）。新增 44 例（纯计算/契约/渲染 + 边缘退化序列/非有限值）。落地设计 `docs/archive/v0.13.x/holding-cost-position-design.md`（随本次发布归档迁入）。

### Fixed

- **`scripts/launch.sh` 无参启动崩溃（rf-682）**：`set -euo pipefail` 下裸引用 `$1`/`$VENV_PATH`，无参调用（默认 TUI 路径）或未设 `VENV_PATH` 时直接 `unbound variable` 退出；改 `${1:-}`/`${VENV_PATH:-}` 默认展开，新增 `test_launch_script_regression.py` 回归用例 4 例。

- **shell 契约门禁盲区（rf-683）**：`scripts/` 目录全面核查发现——① `launch.sh` 有 4 处 `set -e` 下的死代码 `$?` 检查（`if [ $? -ne 0 ]` 永不触发，失败时脚本已提前退出，错误处理分支是假安全感）；② 十守护/CI 全为 Python 静态检查，从不执行/解析 shell，`.sh` 的「运行行为」在整个质量体系里零覆盖（rf-682 缺陷穿过全部门禁的根因）。修复：`launch.sh` 4 处死代码改 `if ! cmd; then …` 写法；新增 `test_shell_contract.py` 静态机检，已验证必红，封堵回流。后续精度补丁：裸位置参数检测的 `${N:-}` 守卫豁免集原先全程累积不重置——`launch.sh` 在守卫后紧跟 `shift`，`shift` 后 `$1` 语义变为「下一个可能未设置的参数」，会被早期守卫误豁免（漏报）；遇 `shift` 即清空豁免集，并以「shift 后裸 `$1`」探针验证必红、真实脚本保持全绿。

- **测试冗余检查盲区根治（rf-684）**：`check-test-redundancy.py` 完全重复比对对 62 个用例（self 间接调用无法静态解析）长期跳过——占位面集中在 `test_progress.py`（25）与 `test_market_hours.py`（12）。增强三档绑定解析：① `_class_attr_binding` 新增 setUp/setUpClass 内 `self.<attr> = <值>` 赋值解析（覆盖 self.r/self.fn 类 35 例）；② 无单一 return 的分支型 helper（_run/_call 类 27 例）取方法体 sha1 哈希为绑定；③ 三档均失败才跳过（跳过是保底而非默认）。盲区 62→0，全仓 9675 用例仍零重复；红验证：setUp 同体对 / 分支型 helper 同体对均报重复、不同绑定/不同方法体不误报；契约测试 36→40。缓存逻辑版本随脚本哈希自动失效，无需手动 bump。

### Changed

- **`cost_position` 收盘价提取复用共享单一事实来源（rf-685）**：开发期自审（36 小时实现技术债核对）发现 `analysis/cost_position.py` 自建的 `extract_closes` 与既有共享 `valuation_percentile.extract_closes`（`market_temperature` 同源复用）**同名二份实现且语义不同**——自建只读 `close` 键并过滤 0/负，共享做 `close→nav→price` 字段回退且只滤非有限值；正是「第二份实现即为新增技术债」面。按「复用优先于另写」收敛：删除自建副本，`report/cost_position.py` 改引共享提取并以 `bars or []` 防 `None` bars，区间有效性过滤（0/负/NaN/inf 不入极值）统一收敛到 `compute_window_position`（纯数学层职责）并补锁测试 `test_zero_close_excluded_from_range`（0 夹杂序列区间仍正确）；边缘分片的 extract 层用例改写为 `compute_window_position` 层断言（提取覆盖归 `test_valuation_percentile`）。
- **计划/自审文档去历史复盘痕迹**：`plan.md`（plan-55 预检细节收敛为评测方案引用、plan-70 状态行去掉批次快照叙事）、`review-findings.md`（开发期已修复 5 条收敛为摘要行，完整复盘归 changelog；rf-626 出带叙事收敛为当前行数与策略）、`docs/plan/` 六份在办设计/验证文件（仅保留最新状态内容：决策跨期反思设计去借鉴溯源改为直接设计描述、Jev 评测预检段收敛为设计约束、两份浏览器验证文件去另机/日期/迭代号复盘与红线元叙述）；folders.md 同步（docs/plan 行数/描述、移除已归档的报告对话式追问设计残留描述）

- **文档与实现对齐（TUI 菜单体系，rf-680）**：技术设计文档 §1.6.3 按实际菜单重写（静态 19 项实际排列、补 `[Q]` 报告对话式追问、`[T]`/`[Q]` 双门控 `FEATURE_GATED_ITEMS` 语义、`[S]` 面板四组分块取自 `GROUP_ORDER`/`GROUP_LABELS`、`[A]` 四模式键名、`[R]` 重载范围、页头状态行 `build_status_line` 五项），§1.6.1 模块表补 `handlers_log.py`/`handlers_qa.py`/`status_line.py` 三行；TUI 菜单手册同步：主菜单 `[D]`/`[1]`/`[I]` 标签对齐实际显示、[1] 缓存清单补全（refresh 组 18 模块）、[2] 附带清除 LLM 清单补生成后自检/持仓变动复盘归因/辩论三模块、[A] 名称替换表述改「品种X」。

- **文档与实现对齐（CLI/Web 渠道，rf-681）**：技术设计文档 §1.7.2 补 `report --prefer-source/--exclude-source`；§1.8.4 路由表补 `/api/whatif`、`GET /api/cache`、`POST /api/cache/cleanup`、`POST /api/qa/ask` 四行，§1.8.1/§1.8.8/§1.8.9 同步（handlers 路由清单、配置面板 9 块按 `features.groups` 四组分块、同源校验覆盖四个 POST 写路由）；Web 手册 §5 LLM 分析章节行改现行 7 模块名、§5.1 开关分块与「（影响报告）」标记口径对齐 `report_affecting` 下发、自检卡定位改「机制与诊断」区；CLI 手册 §10.1 改生成类菜单对照并声明无 CLI 等价项。

## [0.13.3] - 2026-10-15

### Fixed

- **release 编排：prepare/evolution 收尾补 `check-doc-drift --sync`（rf-686）**：v0.13.2 发布复盘发现 `prepare`（版本全链 + changelog 发布段归档，改写多处文档）与 `evolution`（改写 folders.md 演进表/比率/注释）均改动画布却不同步 folders.md 统计表，而 `refresh` 的 sync 又排在 bench 之后——导致 refresh 的 bench（含 doc-drift crosscheck 单测）因统计过期而红，被迫手动 sync 后整套 bench（14 模式，单遍 ~250s）重跑一遍。修复：两步各自改完文档后立即 sync，从源头保持 folders.md 一致，后续 refresh/publish 的测试不再因统计过期而失败（发布提速，消除重复 bench）。

- **LLM provider 故障切换迟滞修复：墙钟总超时 + 安全网判别服务侧故障（rf-687）**：外部服务事故（DeepSeek 过载）暴露两个缺陷——① httpx read 超时度量「块间间隔」，服务端网关排队滴流时配置的 timeout（120s）完全不生效，单请求挂足服务端 900s 上限；② 200+error 信封被「关闭 thinking」安全网误判为偶发空响应，对同一死端点再白打一轮——最坏 15~30 分钟才切到备用 provider。修复：① 新增 `core/http_client.post_with_deadline` 墙钟原语（POST 以独立 daemon 线程执行、主线程 join(timeout) 到点放弃，归一为 httpx.ReadTimeout 走既有超时分类：退避重试→耗尽后切换）；② `_extract_content` 置「服务端错误信封」线程局部标志，安全网仅对服务端正常返回的空响应触发（传输失败/熔断同理跳过）。故障期单模块切换耗时从 ~15 分钟降至 ~4 分钟（503 重试 + 两个墙钟周期）；同步 technical.md 调用流程图/机制容错表、testplan `llm/` 包覆盖清单、llm-technical 失败追踪表超时口径、how-to-config-llm timeout 语义（端到端墙钟上限）。

## [0.13.4] - 2026-10-16

### Changed

- **perf-view 读数体验升级（--version / 阶段降序与占比 / 数据新鲜度 / 缺数据提示）**：① 新增 `--version` 前缀过滤（`0.13.4` 命中 `0.13.4-dev`，头部明示「版本筛选」行，可与 `--report-type`/`--last` 组合，`_filter_records`/`_group_records`/机读输出同口径）；② 组详情**阶段表按中位降序**（最慢阶段在前，同分按名保持可 diff）并新增**占比**列（阶段均值 ÷ 组平均总耗时，附并行可超 100% 说明），阶段细分子项同改平均耗时降序；③ 头部新增**数据新鲜度**行（最新记录时间戳 + 距今时长，解析失败降级显示原值）——先判断数据是否新鲜再读数；④ **缺数据明示**：完整报告范围无 `breakdown` 时显示「暂无阶段细分」提示行（不再静默省表），无 `llm` 字段时显示「暂无 LLM 上下文」提示段（basic/both 范围不渲染），区分「无数据」与「不适用」。测试 +6（版本过滤/新鲜度/降序语义/占比/双提示正反向）。
- **perf-view 拆分子包与管理文档最新状态同步**：① `perf-view.py` 拆出 `scripts/_perf_view/`（`stats.py` 承载分位/离群/稳健统计与记录过滤分组纯函数，主入口 re-export 保 `load_script` 直调测试可达）——主文件回落 1000 行红线内，`check-file-length` 的 `EXEMPTIONS` 豁免与 review-findings rf-688 挂账同步移除；② **管理文档对齐最新状态**：plan.md 移除已完成的 plan-123~126 四个待办块与概述计数（11→7 项），四项完成摘要迁入 `archived_plan.0.13.x.md`；review-findings P3 文件过长登记表按 `check-file-length -v` 真值刷新 6 处行数（html_writer/code_utils/features/excel_generator/operations 等）；`perf-observability-design.md` 头部与 §7 标注四步已实施（保留为现行口径参考）。
- **perf-view 分组节排序改为真实时间序**：逐版本分组详情（`## 版本 / 类型` 各节）原按版本号**字符串字典序**——`0.9.9` 会排在 `0.13.4` 之后、最新开发版卡在中间，与真实先后不符；改为按各组**首次运行时间**升序（与版本演进总表同口径），最新版本组在最末；组内明细行仍按时间戳升序，同时首次运行时间相同时按组键稳定排序（可复现）。
- **perf-view 视图输出增强（版本演进 / 漂移检测 / 归一化 / 机读信封）**：① **版本演进总表**——每个（版本, 报告类型）一行（同类型按该版本首现时间排序）：样本数 / 中位 / P95 / **中位秒每品种**（总耗时 ÷ 持仓数，跨持仓规模可比）/ 较上一版中位 delta（|变化| ≥10% 标注 ⚠变慢/变快），一眼看出哪个版本开始变慢；② **机读输出升级**——`--json` 改为信封 `{record_count, records, summary}`（summary 与 Markdown 段同源：分位/按类型/离群/异常/演进/漂移；原为裸记录数组，仓库内无程序化消费方，语义变更安全），`--csv` 增 `per_holding_seconds`/`outlier`/`slowest_phase`/`interrupted_stage`/`errors_count` 列；③ **归一化与小样本提示**——总体分位概览增「中位秒/品种」列，n<20 的口径/分组附「最近秩分位趋近最大值，参考性有限」提示（不改分位算法，保历史可比）；④ **异常运行专区**——中断（`interrupted_stage`）/非完成状态/带错误的运行单独成表（状态/中断阶段/错误数/首条摘要；当前历史无此类记录时整段省略），离群表同增错误数列；⑤ **同版本漂移检测**——同（版本, 类型）按时间对半比较前后半中位（样本 ≥6 参与），显著性与版本对比同噪声带口径（两半变异系数之和 × 较大中位），检出同版本内渐进劣化且不受换版混杂，与演进总表（看换版跳变）互补。
- **性能门禁可靠性：压测脚本网络无关性与状态隔离**：`perf-test-report.py` 两层离线——① 传输层 `_install_offline_network()`：socket 出口瞬时抛 `OSError`（各抓取器按常规失败类型走既有降级，不崩溃）+ `time.sleep` 置零（同源重试/退避不再真等；全仓无 `from time import sleep`，一处补丁全覆盖），对一切外部抓取（穿透/基金经理/分红/情绪/财报/新闻等，随配置开关增减）兜底；② 咽喉桩保留热点路径真实计算：行情（`fetch_market_data` 两处绑定）、K 线历史链（`chain`/`chain_incremental.fetch_with_incremental_fallback`，流动性/风格因子/事件面板逐仓拉历史都经它）、交易日历（`trading_calendar._get_trading_calendar`，模块唯一网络出口）。使基准与「网络状况/冷热缓存/配置开关组合」无关——冷缓存断网下全流程 58s→2.8s（此前 CI 门禁红正是因为冷缓存下重试退避拖过 60s 阈值，测成了网络状况而非代码性能）。同时 `_isolate_state_writes()` 把 perf 历史/数据源健康快照/熔断状态一并重定向到临时目录，不再污染 `perf-view` 的统计样本与真实运行的供应商熔断状态。

- **性能门禁归属修正 + 视图输出精简**：① 性能门禁改由**主动压测**脚本承担——`perf-test-report.py` 新增 `--gate`（未达标退出码 2，与检查脚本契约一致），CI 新增阻塞型 `perf-gate` job（basic 模式 ≤ 60s，并上传性能报告产物）；② `perf-view.py` **移除 `--gate`**——它是运行历史查看（被动统计既有记录），样本取决于最近跑过什么、不可复现，不适合做门禁（同一份代码跑 10 次与跑 3 次的 P95 不同，且混入 LLM 服务端延迟/网络/机器负载等与提交无关的因素）；③ `perf-view.py` 新增 `--summary`（仅输出概览段，略去逐版本分组详情，记录多时避免输出过长）与 `--outlier-k`（自定义离群判定系数，默认 3.5）；④ 稳健均值改为**仅在存在离群点时**与普通均值并列展示（无离群时两者相同，并列属冗余）。

- **性能对比、机读输出与阈值门禁（plan-126）**：`perf-view.py` 新增 `--compare 旧版本 新版本`（阶段级中位 delta / 倍数 / 变异系数判显著——变化幅度需超过两版本各自变异系数之和 × 较大中位值，避免把运行抖动当回归）、`--json` / `--csv` 机读输出（完整记录 / 逐运行一行）、`--gate 秒` 阈值门禁（P95 总耗时超限退出码 2，与检查脚本契约一致，可挂 CI 拦截真实运行的性能回归；P95 口径对单条离群不敏感，配合 `--exclude-outlier` 可只看正常运行）。

- **运行上下文维度采集（plan-125）**：`perf_history.jsonl` 记录新增 `llm` 字段（provider/model/thinking、重试次数与退避等待秒数、端点节流等待秒数、provider 降级次数、模块级缓存命中/未命中、逐模块 tokens 与费用）。新增 `llm/observation.py` 运行观测汇聚器（`bind_llm_observation`/`current_llm_observation`，线程安全），在调用链上归集：重试退避（`core/retry.py` 的 `on_retry`）、端点节流等待（`llm/pacing.py` 的 `PacingGate`）、provider 命中与降级（`llm/api.py` provider 链）、模块级缓存命中（编排层预检）、逐模块 model/tokens/费用（`llm/session.py` 单源）；未绑定汇聚器时所有记录调用为空操作（单测直调 LLM 层行为零变化）。`perf-view.py` 新增「LLM 运行上下文」段（等待/重试/降级/缓存/费用与 provider/模型分布），回答「时间花在白等还是真推理」。

- **性能视图稳健统计与归因（plan-124）**：`perf-view.py` 新增离群运行段（总耗时 > 中位 + 3.5 × 1.4826 × MAD 判离群，MAD 为 0 时不判；显式列出而非静默剔除）、稳健均值（剔除离群后均值，与普通均值并列）、阶段级分位（阶段表增中位与 P95）、尾部归因（最慢一次运行逐阶段 z 分数与相对历史中位倍数，直给哪一步超常）、时段聚合（`--by day|week|hour`）；新增 `--exclude-outlier` 按稳健口径剔除离群后重算全部统计。实测：126 条历史中自动标出 6636s 那条服务端超时运行，尾部归因定位到 `LLM+新闻` 22.37× / z=+6.14，剔除后均值由 519.7s 降至 362.9s。

- **运行观测面扩充（plan-123）：LLM 模块级细分 + full 埋点补回 + 诊断落盘**：`perf_history.jsonl` 记录新增 `breakdown`（父阶段下的子项自身耗时）与 `counters`（运行期诊断计数）两个旁路观测面，**不参与 `total_seconds`**（保历史可比与 ETA 口径稳定）。`core/perf.py` 新增线程安全 `PhaseBreakdownRecorder`（`PerfCollector.recorder(父阶段)` 取用，四模块在线程池并发写不丢计数）；`LLM+新闻` 阶段细分到四个 LLM 模块与新闻获取（`_llm_dispatch` 逐模块计时、`_llm_news` 新闻获取计时，`span_recorder` 为可选参数，None 时行为零变化）；full 路径 `_report_output.py` 两个 helper 经 `run_integrity.current_perf()` 补回 `HTML 生成`/`Excel 生成` 阶段计时（此前 full 运行丢失这两个阶段，实测 126 条历史中二者各仅 6 条且均早期版本）；`errors`/`warnings_count` 由「恒空」改为自动采集——首个阶段计时时挂只计数日志 handler、`save()` 摘除，WARNING/ERROR 自动入 `counters`（错误消息封顶保留，计数照常累加）。`perf-view.py` 分组段新增「阶段细分」表（旧记录无 `breakdown` 时不渲染空表）。方案与口径见 [`perf-observability-design.md`](perf-observability-design.md)。

- **perf-view 新增 P95/P99 分位概览**：`scripts/perf-view.py` 输出新增「总体分位概览（跨版本）」表（口径 / 样本数 / 平均 / 中位 / **P95** / **P99** / 最长），并在每个版本分组段直给「95% 的报告在 Xs 内完成，99% 的报告在 Ys 内完成」。分位采**最近秩**（`ceil(pct% × n)` 位样本值）口径，含义即 95% 的报告在该耗时内完成，99% 的报告在该耗时内完成。新增 `_percentile()` / `_total_summary()` / `_overview_lines()`，过滤逻辑抽为 `_filter_records()` 与分组共用（`--report-type` / `--last` 对概览同步生效）；单一报告类型时只渲染合计行，不重复出类型行。同步文档：developer-guide「perf-view」段（分位口径说明 + 脚本清单）与 how-to-use-cli-mode 性能历史小节。回归 = `test_perf_view.py` 新增分位口径 / 汇总字段 / 概览表结构 / 分组完成时间四组用例。

- **developer-guide 核对更新：补发布归档迁移四项 + release 收尾 sync 口径**：对照近期变更核对开发者指南，修复 4 类缺口——① 版本发布流程五步→六步，新增步骤③「发布归档迁移（四项强制）」（rf/plan 完成态/changelog 段/docs-plan 设计文件四项，未完成不得继续 `gate`/`publish`——此前指南完全缺失该强制项），原③④⑤顺延为④⑤⑥并修正步骤间互引用；② 发布类命令注释与编排提示补 `prepare`/`evolution` 收尾自动 `check-doc-drift --sync` 实况（rf-686 后口径同步），并明示归档迁移保留人工且须前置；③ 「② 发布数据文档刷新」补 `evolution --release` 输出「需人工核对注释行」的回填义务（test-coverage 用例收集口径 + folders.md 文档目录分解数）；④ 新增测试指南「新增后必须更新的文件」清单补第 6 条 conftest 隔离 fixture（模块级单例 autouse 复位、持久化/输出路径在 `_isolate_sensitive_paths` 重定向，指向 CLAUDE.md「新增测试隔离要求」细则）。新增段落措辞经 `check-doc-traces` ARCHIVE 规则复核（面向读者文档不写归档目录/文件名）。

- **`perf-report.py` 更名 `perf-test-report.py`**：与「历史趋势查看 `perf-view.py`」对仗，突出其**基准测试**定位（自造模拟持仓跑 basic/both 管线、mock LLM，输出 `docs/tmp/better-investment-performance-test-report.md`）。`git mv` 保留历史，同步更新脚本自引用、`core/perf.py` 分层注释、`_traces_code/patterns.py` 注释、developer-guide 脚本清单与诊断段、folders.md 目录树；配套测试同步更名 `test_perf_test_report.py`（fixture 名与 `load_script` 入参随改），`test_script_loader.py` 的模块名派生断言随新文件名（`perf_test_report`）更新。
