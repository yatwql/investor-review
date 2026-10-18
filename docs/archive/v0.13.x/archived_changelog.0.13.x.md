# 变更日志归档 — v0.13.x

> 归档时间：2026-10-18（v0.13.6 发布并入第六段；历次并入 2026-10-13 v0.13.0 首份、10-14 v0.13.1、10-15 v0.13.2/v0.13.3、10-16 v0.13.4、10-17 v0.13.5）
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.13.0 ~ v0.13.6（2026-10-13 ~ 2026-10-18）
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

## [0.13.5] - 2026-10-17

### Fixed

- **`unit` 标记漏注册致全量单元测试脱离一切门禁（rf-697）**：门禁档位按 `unit` 通配（`unit` 档、P2 预检）与 `unit_*` 域集（`dev-verify`/`verify`）筛选，但 conftest `pytest_configure` 从未注册裸 `unit` marker——`-m "unit"` 表达式匹配为空，10,136 条 unit 用例（含全部域）实际不在任何门禁收集范围（P0/P1 实跑 6,969/9,800 与台账吻合即实证）。补注册行后 conftest 注释同步标记体系口径；`verify` 档 9,800→10,145（含同批纳入的 TUI/CLI 域），域集同源性由 `TestP1GateCoversDeclaredDomains` 结构锁钉死。
- **scenario 门禁佩戴无硬校验（rf-696）**：全仓测试语义审计发现 scenario/regression（P2）/integration 三模式按裸 `scenario` marker 筛选，而仓内裸 marker 全靠基类/模块级隐式继承佩戴——只带子域 marker（`scenario_security` 等，不被任何选择器消费）的新场景文件会静默漏出回归门禁且连缺标记警告都不触发。conftest `pytest_collection_modifyitems` 增「scenario 目录×裸 marker」双向收集期拦截（与 edge 隔离同范式）；新增 `test_conftest_scenario_gate.py` 5 个钩子直驱回归用例。审计初判的「22 用例已漏」经 `-m scenario` 全目录收集对拍证实为静态扫描未计 MRO 继承佩戴的误报，现行门禁覆盖实际完整。
- **结构化决策头缺 `detail` 键 → LLM 建议登记整批失效（rf-693）**：结构化决策头优先路（开关 `decision_header_parse` 默认开）的产物仅 `{code, action, priority}` 三字段，而 `register_llm_decisions` 直取 `row["detail"]` → `KeyError: 'detail'`，被实验功能挂载点守护吞成一条告警（perf 运行明细「错误」计数即此），导致当批全部 LLM 操作建议不入决策账本（跨期反思闭环对这轮建议失效）。按技术设计 §4.15「两路产物形状统一」在登记纪律统一入口 `_collect_decision` 回补 `detail`（契约无理由列 → 空串；账本 `append_decision` 的 detail 缺省为空，不阻结算）；同步修正 `parse_structured_header`「与表格解析同形状」的误导 docstring；`test_decision_llm_capture.py` 新增 2 个回归用例（形状回补断言 + 登记链路缺陷场景复现）。
- **LLM 观测未写入性能记录（rf-692）**：full 路径在 LLM 阶段结束的 `finally` 中解绑全局 sink 后，收尾 `_record_llm_context(perf)` 仍取全局 → 取到 None，重试/节流等待/降级/缓存/thinking 观测整段丢失（性能台账只剩会话用量）。改为显式传入本次绑定的 sink（`_record_llm_context(perf, _llm_sink)`）；新增 2 个回归用例。

- **盘前/盘后价格缓存误用盘中价（rf-691）**：`_price_cache_fresh` 此前只比 `price_date`，把交易日 T 盘中写入的场内缓存（如 10-15 13:01 的 29.35）当作 T 日收盘价（真实 29.60）在盘后/次日盘前沿用，使「本日盈亏」与「快照环比」系统性偏离真实涨跌。现增加收盘时点校验：T 日已收盘（now ≥ 15:00）时要求缓存写入时刻 ≥ T 日 15:00（午间休市不施加），`report/market_value.py` 的 `CACHE_ONLY` 分支与 `_fetch_price_with_cache_refresh` 两处传入 `cache_key`；强制刷新失败时退回刷新前的过时缓存（不再因清缓存反而丢数据）。新增 `test_fetcher_price.py` 8 个回归用例。
- **Web 生成完成后按钮复位（rf-690）**：run 完成后「生成报告」按钮停在「生成中...」禁用态、无法再次生成或换格式再生成（rf-257 真机 basic 实测揭示）——根因是 `pollOnce` 完成分支只移除 `aria-busy`、未复位文案与禁用态、未清已消费的 `file_id`；完成分支与 `resetFlow` 共用 `restoreGenerateBtn()` 单源复位（清 `state.fileId` → `updateGenerateBtn()` → 文案还原 +「请重新上传」提示；正式-用存量免上传立即可再生成），新增 `test_web_generate_flow.py` 源结构回归 3 用例。

### Changed

- **设计契约审计与护栏观察维度增设（rf-699）**：全量 UI/报告样式人工比对 DESIGN.md + 基线对拍定位契约落稿后新增违规仅 3 行（`summary_section.html` 内联 `#888` 裸色值×2、`opacity:0.75` 档外×1），已修并顺手消同模式存量 1 行；护栏 `check-style-guardrails` 增设 W3 内联色值/W4 档外字号/W5 档外间距三维观察（W1 引号整行豁免为 JS 图表配置设计，HTML 内联色值盲区按位置级找回；存量 40/8/175 入只减不增基线并入契约 Known Gaps）；DESIGN.md 基线数字刷新（700 存量 3→9、600 25→63）；工作台旧 `--color-*` 兼容映射到期删除（零消费者，`TestLegacyMappingRemoved` 负向锁）。
- **旧配置/旧缓存/旧模型名兼容代码清理（rf-698，用户裁决口径）**：移除 5 处残留兼容分支——perf 阶段 ETA 的早期 list 形状 `phases` 死分支（旧记录已自然出 20 条采样窗）；行业缓存缺扩展字段载荷的 schema 迁移清理链（迁移窗口≤两周已过）；数据源密钥文件顶层平铺 `{"api_key": ...}` 回退（生产调用点恒传非空 section）；停用别名 `deepseek-chat`/`deepseek-reasoner` 在价目表与 Extended Thinking 三名单的全部收录（旧名历史调用费用改显 `-`、存量旧配置不再获思考安全网，已经用户确认接受）；另修正 anonymizer `profit_rate_pct`「旧键兼容」误导注释（实为现役汇总键，同步分支保留）。手册/`llm-technical.md` 价目与峰谷枚举同源刷新；测试侧别名价格锁改负向锁（锁定移除行为防回填）并删 3 个旧形状/旧载荷正测。

- **P1 门禁域范围纳入 TUI/CLI，确立「归域即进门禁」不变式（rf-694/rf-695/rf-697，`technical.md` §4.23）**：`verify`（P1）选择器增 `unit_ui`/`unit_cli`；目录归域特例（`unit/handlers`·`unit/cache`→`unit_core`、`unit/startup`→`unit_ui`）在期望表注释/conftest 缺标警告/技术设计三处同源登记；新增 `TestP1GateCoversDeclaredDomains` 双结构锁（期望表全部 unit_* 域 ∈ verify；P0 域集 ⊆ P1）防「改域=门禁搬家」回退。审计改域迁移方案废弃：`unit_ui` 入门禁后 handlers 挂 `unit_core` 与挂 `unit_ui` 门禁结果恒同，迁移改动面 ~20 处且零覆盖收益，故保留期望表已登记口径。
- **perf-view 统计分组去重（技术债）**：`_version_evolution_data` 与 `_drift_data` 各自重复实现「按（类型, 版本）分组 + 首次运行时间排序键」，`build_trend_report` 又对同一批记录重复过滤两次；抽出 `_group_by_version_type` / `_group_filtered` 共用，`_group_records` 复用之；`_compare_versions` 的 `_summary` 改用显式版本参数（原靠对象 identity 判分支）。
- **快照/取价微清理**：`capture_snapshot` 的 QDII 分项改为仅在存在环比时计算（首次运行不再为丢弃的结果调用交易日历）；`market_value` 的 `CACHE_ONLY` 分支复用已算好的缓存键，避免同一键重复计算两次。

- **环比 QDII 口径可见（R-OUT-15 增强）**：QDII 官方净值滞后一个交易日，其市值差实际是上一交易日的净值变动，与当日 A 股涨跌混在同一个「总市值环比」里易被误读（用户实测：本日盈亏 −808.44 与环比 −530.73 差额中 +557.29 来自 QDII 口径差）。摘要区「本期要点」总市值环比行下新增 QDII 口径注：显示环比含有的 QDII 官方净值变动金额，滞后一日时标注「T-1 口径，滞后一个交易日」；无 QDII 或变动为 0 时省略。`_snapshot.capture_snapshot` 经 `_classify_qdii_value_diff` 注入 `qdii_value_diff`/`qdii_lagged`，`summary_highlights` 透传，`summary_section.html` 渲染；新增 `test_summary_highlights.py` 6 个回归用例。
- **发布流程分层纪律补充（rf-689）**：developer-guide 发布流程段增加「归档迁移/管理文档改动后、进 `gate` 前必跑便宜守护（`check-doc-traces` 等）」——守护发现前置，防止 P2 门禁因文档级 finding 双跑全量 regression（v0.13.4 发布时实际发生一次：管理文档引用归档路径触发 ARCHIVE 痕迹拦截，gate 第二轮才过）。
- **报告浏览器验证六项收口（rf-113）**：Iter 7 全链路浏览器人工验证全部完成并移入已解决——自动化回归（headless Chrome 148 一键复跑 `node docs/tmp/rf113/run-rf113.mjs`：① 6 图 badge、② afterprint 快照恢复、③ 断网渲染、⑤ 375px 报告+调试页、⑥ 禁 Canvas 兜底，5 PASS + ⑥ 已知表现记录口径）+ 人工抽验（真实 `Ctrl+P` 打印预览 2x/浅色/不跨页、微信 X5 file:// 表格兜底 + 横竖屏、iPad Safari 90+ 抽验、Windows Chrome/Firefox）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与结论见 `docs/plan/report-browser-verification.md`，勾选清单归档 `docs/archive/v0.9.x/chartjs-upgrade/iter7-verification-checklist.md`；rf-114 前置解锁

## [0.13.6] - 2026-10-18

### Added

- HTML 报告右上角浮动「打印 / 导出 PDF」按钮（plan-127）：`window.print()` 唤起浏览器打印/另存 PDF，44×44 触控目标、`--primary` 语义色、打印稿自隐藏（独立 `@media print` 规则）；补模板结构/可访问性/触控尺寸/打印隐藏回归用例，`reports-instruction.md` 同步入口说明
- Web 内置定时生成（plan-130）：配置页签新增「定时生成」调度面板（执行日/时刻/报告类型/启用开关），保存写入 `config.json` 的 `scheduler` 块；服务端 daemon 调度线程到点自动读正式持仓生成（正式-用存量），与手动生成同队列串行互斥、宽限 30 分钟内顺延、超时登记错过，触发账本落 `data/state/scheduler_fired.json` 防重启重复；缺省关闭零行为变化，面板改配置 30s 内生效无需重启（`GET/POST /api/scheduler`，校验 400 + 同源守卫 403）；补解析/触发窗/账本/API/面板接线回归用例，配置默认值模板与 `how-to-config.md`/`how-to-use-web-mode.md` 同步
- LLM 运行事前费用预估与日预算（plan-99）：full 生成前三渠道上屏费用区间——计划参与模块（`enabled_llm` ∩ 深度档位收窄）× 生效模型单价，perf 历史逐模块实际费用优先、静态 token 包络兜底、全部无法定价时降级「不阻塞」（渠道跳过确认继续）；TUI y/N 确认、Web 提交前弹层（预检失败/无模块直接放行）、CLI 交互确认 + `--yes` 跳过（`--non-interactive`/非 TTY 同样跳过）。`llm_settings.json` 新增 `daily_cost_limit`（默认 0=不启用）为日费用硬闸：今日已花费（perf 当日 `llm.total_cost` 汇总，与事后统计同源）达上限时交互询问「降级走缓存继续 / 中止」（降级清空强刷范围），非交互链路直接中止——CLI 退出码 2、Web 创建 409 `BUDGET_EXCEEDED` + 执行体兜底（定时调度/直连 API 同拦）；计费数学抽 `pricing.compute_cost_value()` 数值单源（`estimate_cost` 格式化契约不变）；补 4 个测试文件（预估三态/辩论口径/预算边界/三通道接线/弹层源结构），需求登记 R-LLM-13，配置/CLI/Web/TUI 手册与语义命名表同步
- TUI [S] 面板只读信息面（plan-132）：`? 编号` 查看该项说明（注册表 desc）/当前值/出厂默认值/存储键（纯只读）；行尾 `*` 标记与出厂默认不一致项（LLM 模块按 enabled_llm 出厂值、功能开关按注册表 default 比对，页脚释义）；⚗ 实验项行尾附 experiment_stats 启用统计（启用 N 次 · 最近 MM-DD，读取失败静默省略）；补 6 个单测
- TUI 首页 `0` 增加为退出别名：与各子菜单「`0` = 返回」的习惯一致（首页没有上层，返回即退出），页脚提示同步为「方向键移动 | Enter 确认 | 字母/数字键直达 | 0 或 X 退出 | Ctrl+C 退出」，菜单项标签也写明「退出（0 亦可）」；页脚与长菜单标签按终端宽度折行（续行对齐标签列），手机窄屏不硬折；此前菜单无 `[0]` 项、按 `0` 静默无反应。新增 4 单测（`0` 退出 / `X` 退出 / 未映射键不误退 / 页脚含 `0 退出`）
- `[S]` 窄屏以编号为主路径、键名改为按需展开（rf-718）：手机窄屏一行放不下 17~25 字符的键名，且打长键名远比按编号费劲——窄屏条目行默认只显示「编号 名称 [状态]」，按 `k` 才在当前版面上追加缩进的键名行（可抄写/粘贴），图例同步提示 `k 显示键名` / `k 隐藏键名`；**键名输入不取消**（`键名`、`? 键名`、`键名=on|off` 窄屏照常生效，供熟练用户与脚本化操作），宽/中档键名恒显、按 `k` 给说明性提示不改变版面；新增 5 单测（默认隐藏/`k` 展开/键名输入仍生效/宽档 k 无效提示/图例随态切换）
- `[S]` 状态着色回归修复（rf-717）：响应式排版重构时状态标签退化为无色纯文本——恢复**开启绿 / 关闭红**（颜色落在方括号内，`NO_COLOR`/非 TTY 自动降级，宽度计算剥离 ANSI 不受影响），窄档的「开/关」短标签同样着色；新增 3 单测锁定（强制着色下 GREEN/RED 位置、窄档短标签、无色环境纯文本），并补手册 [S]「状态着色」说明
- `[S]` 面板可读性与响应式重做（rf-716）：①**键名显式上屏**——每行都带淡色的键名列（`DIM` 新增于 `core/ansi_colors.py`），用户不必再猜「键名是什么」，`? 键名` / `键名=on|off` / 裸键名切换直接照抄行内文字；②**三档响应式版面**（新模块 `tui/switch_panel.py`，只排版不取数）：≥96 列四列单行、64~95 列两行（名称+状态 / 缩进键名+备注）、<64 列压缩为「编号 名称 [开/关]」并提示 `? 编号` 查键名——手机 SSH 窄终端不再被硬折成锯齿；③**对齐修复**：编号列按最大编号右对齐（此前两位数编号会把后续各列整体推右 1 列）、⚗ 占位按显示列补齐；④**页脚图例**改为按面板内宽折行 + 悬挂缩进（不再出现 130 列超宽行），并删掉面板下方重复打印的四行分组标题；⑤费用摘要压成 `· 6次 ¥X 均¥Y`（窗口天数移到图例）、分组标题改为「组名（N/M 开）」；`? 编号` 详情同样按宽折行；⑥不变式由单测锁定：任意档位、任意宽度下每行 ≤ 面板内宽（`test_switch_panel_layout.py` 26 例）+ 面板用例固定 `COLUMNS` 消除环境漂移（dev-verify 非 TTY 下曾因宽度不定而红）
- 近 72 小时技术债核对与修复（rf-713 + 文档/注释陈旧表述）：① technical「写入分派」段残留已废弃分组名 `GROUP_REPORT` 与「三组同一路径」→ 改「注册表四组同一路径」；② 主菜单项数陈旧表述随 `[3]` 合并同步（technical 模块表与菜单架构段 19→18 项、默认渲染 18→17 项；folders 目录树注释两处、README 两处）；③ testplan 两处菜单清单仍列 `[3]` 独立项与「19 项计数」断言 → 改为 `[1][2][4]`（`[4]` 子菜单内含清理）、`[D]` 二级补 `[M]`，并注明用例改为「键集合完整/索引相对位、由 `MENU_ITEMS` 派生不写死条数」；④ 两处代码注释仍称「辩论三模块在注册表内保留/为隐藏项」→ 改为「不在模块注册表内、缓存登记在缓存域」；⑤ `cost_forecast._DEBATE_KEYS` 注释对齐缓存域口径
- 渠道层私引配置私有符号修复（rf-715）：`[S]` 面板的只读详情与写路径三通道此前直引 `config._llm_settings_defaults._DEFAULT_LLM_SETTINGS` 与 `features._SWITCH_TRUE_TOKENS`/`_SWITCH_FALSE_TOKENS`（违反渠道薄壳纪律，`test_channel_layering` 检出）——新增公开面：`config.default_enabled_llm()`（出厂默认副本）、`features.SWITCH_TRUE_TOKENS`/`SWITCH_FALSE_TOKENS`（词表转公开）与 `features.parse_switch_value(text)`（单值解析器，与 `parse_switch_override` 同词表）；渠道改走公开 API，两处口径不再可能漂移；新增 4 单测（词表全覆盖解析 / 两解析器一致 / 默认副本不污染全局 / 默认覆盖注册表模块）
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
