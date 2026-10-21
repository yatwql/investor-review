# 变更日志归档 — v0.13.x

> 归档时间：2026-10-20（v0.13.10 发布并入；已并入 11 段：v0.13.0（10-13）、v0.13.1（10-14）、v0.13.2（10-15）、v0.13.3（10-15）、v0.13.4（10-16）、v0.13.5（10-17）、v0.13.6（10-18）、v0.13.7（10-19）、v0.13.8（10-20）、v0.13.9（10-20）、v0.13.10（10-20））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.13.0 ~ v0.13.10（2026-10-13 ~ 2026-10-20）
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

- **持仓成本区间位置列（plan-90）**：「持仓明细与分类」页签市值明细与分类汇总两区块末列追加「成本区间位置」两列（近 20 / 260 交易日价格区间百分位，≈1 追涨嫌疑、≈0 低位布局），填补只维护持仓、无流水时「买入时机相对历史区间」的量化空白。纯计算 `analysis/cost_position.py`（clamp/中性值/窗口切片）+ 编排 `report/cost_position.py`（复用既有行情历史链，不新增数据源；长窗口一次取数、短窗口同源切片）；功能开关 `cost_position`（默认开，`GROUP_ANALYSIS`），行情缺失静默隐列不阻断报告；口径脚注随呈现（成本均价近似买入价 + 窗口参数 + 公式）。新增 44 例（纯计算/契约/渲染 + 边缘退化序列/非有限值）。落地设计 `docs/archive/v0.13.x/holding-cost-position/holding-cost-position-design.md`（随本次发布归档迁入）。

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
- **perf-view 拆分子包与管理文档最新状态同步**：① `perf-view.py` 拆出 `scripts/_perf_view/`（`stats.py` 承载分位/离群/稳健统计与记录过滤分组纯函数，主入口 re-export 保 `load_script` 直调测试可达）——主文件回落 1000 行红线内，`check-file-length` 的 `EXEMPTIONS` 豁免与 review-findings rf-688 挂账同步移除；② **管理文档对齐最新状态**：plan.md 移除已完成的 plan-123~126 四个待办块与概述计数（11→7 项），四项完成摘要迁入 `archived_plan.0.13.x.md`；review-findings P3 文件过长登记表按 `check-file-length -v` 真值刷新 6 处行数（html_writer/code_utils/features/excel_generator/operations 等）；`perf-observability/perf-observability-design.md` 头部与 §7 标注四步已实施（保留为现行口径参考）。
- **perf-view 分组节排序改为真实时间序**：逐版本分组详情（`## 版本 / 类型` 各节）原按版本号**字符串字典序**——`0.9.9` 会排在 `0.13.4` 之后、最新开发版卡在中间，与真实先后不符；改为按各组**首次运行时间**升序（与版本演进总表同口径），最新版本组在最末；组内明细行仍按时间戳升序，同时首次运行时间相同时按组键稳定排序（可复现）。
- **perf-view 视图输出增强（版本演进 / 漂移检测 / 归一化 / 机读信封）**：① **版本演进总表**——每个（版本, 报告类型）一行（同类型按该版本首现时间排序）：样本数 / 中位 / P95 / **中位秒每品种**（总耗时 ÷ 持仓数，跨持仓规模可比）/ 较上一版中位 delta（|变化| ≥10% 标注 ⚠变慢/变快），一眼看出哪个版本开始变慢；② **机读输出升级**——`--json` 改为信封 `{record_count, records, summary}`（summary 与 Markdown 段同源：分位/按类型/离群/异常/演进/漂移；原为裸记录数组，仓库内无程序化消费方，语义变更安全），`--csv` 增 `per_holding_seconds`/`outlier`/`slowest_phase`/`interrupted_stage`/`errors_count` 列；③ **归一化与小样本提示**——总体分位概览增「中位秒/品种」列，n<20 的口径/分组附「最近秩分位趋近最大值，参考性有限」提示（不改分位算法，保历史可比）；④ **异常运行专区**——中断（`interrupted_stage`）/非完成状态/带错误的运行单独成表（状态/中断阶段/错误数/首条摘要；当前历史无此类记录时整段省略），离群表同增错误数列；⑤ **同版本漂移检测**——同（版本, 类型）按时间对半比较前后半中位（样本 ≥6 参与），显著性与版本对比同噪声带口径（两半变异系数之和 × 较大中位），检出同版本内渐进劣化且不受换版混杂，与演进总表（看换版跳变）互补。
- **性能门禁可靠性：压测脚本网络无关性与状态隔离**：`perf-test-report.py` 两层离线——① 传输层 `_install_offline_network()`：socket 出口瞬时抛 `OSError`（各抓取器按常规失败类型走既有降级，不崩溃）+ `time.sleep` 置零（同源重试/退避不再真等；全仓无 `from time import sleep`，一处补丁全覆盖），对一切外部抓取（穿透/基金经理/分红/情绪/财报/新闻等，随配置开关增减）兜底；② 咽喉桩保留热点路径真实计算：行情（`fetch_market_data` 两处绑定）、K 线历史链（`chain`/`chain_incremental.fetch_with_incremental_fallback`，流动性/风格因子/事件面板逐仓拉历史都经它）、交易日历（`trading_calendar._get_trading_calendar`，模块唯一网络出口）。使基准与「网络状况/冷热缓存/配置开关组合」无关——冷缓存断网下全流程 58s→2.8s（此前 CI 门禁红正是因为冷缓存下重试退避拖过 60s 阈值，测成了网络状况而非代码性能）。同时 `_isolate_state_writes()` 把 perf 历史/数据源健康快照/熔断状态一并重定向到临时目录，不再污染 `perf-view` 的统计样本与真实运行的供应商熔断状态。

- **性能门禁归属修正 + 视图输出精简**：① 性能门禁改由**主动压测**脚本承担——`perf-test-report.py` 新增 `--gate`（未达标退出码 2，与检查脚本契约一致），CI 新增阻塞型 `perf-gate` job（basic 模式 ≤ 60s，并上传性能报告产物）；② `perf-view.py` **移除 `--gate`**——它是运行历史查看（被动统计既有记录），样本取决于最近跑过什么、不可复现，不适合做门禁（同一份代码跑 10 次与跑 3 次的 P95 不同，且混入 LLM 服务端延迟/网络/机器负载等与提交无关的因素）；③ `perf-view.py` 新增 `--summary`（仅输出概览段，略去逐版本分组详情，记录多时避免输出过长）与 `--outlier-k`（自定义离群判定系数，默认 3.5）；④ 稳健均值改为**仅在存在离群点时**与普通均值并列展示（无离群时两者相同，并列属冗余）。

- **性能对比、机读输出与阈值门禁（plan-126）**：`perf-view.py` 新增 `--compare 旧版本 新版本`（阶段级中位 delta / 倍数 / 变异系数判显著——变化幅度需超过两版本各自变异系数之和 × 较大中位值，避免把运行抖动当回归）、`--json` / `--csv` 机读输出（完整记录 / 逐运行一行）、`--gate 秒` 阈值门禁（P95 总耗时超限退出码 2，与检查脚本契约一致，可挂 CI 拦截真实运行的性能回归；P95 口径对单条离群不敏感，配合 `--exclude-outlier` 可只看正常运行）。

- **运行上下文维度采集（plan-125）**：`perf_history.jsonl` 记录新增 `llm` 字段（provider/model/thinking、重试次数与退避等待秒数、端点节流等待秒数、provider 降级次数、模块级缓存命中/未命中、逐模块 tokens 与费用）。新增 `llm/observation.py` 运行观测汇聚器（`bind_llm_observation`/`current_llm_observation`，线程安全），在调用链上归集：重试退避（`core/retry.py` 的 `on_retry`）、端点节流等待（`llm/pacing.py` 的 `PacingGate`）、provider 命中与降级（`llm/api.py` provider 链）、模块级缓存命中（编排层预检）、逐模块 model/tokens/费用（`llm/session.py` 单源）；未绑定汇聚器时所有记录调用为空操作（单测直调 LLM 层行为零变化）。`perf-view.py` 新增「LLM 运行上下文」段（等待/重试/降级/缓存/费用与 provider/模型分布），回答「时间花在白等还是真推理」。

- **性能视图稳健统计与归因（plan-124）**：`perf-view.py` 新增离群运行段（总耗时 > 中位 + 3.5 × 1.4826 × MAD 判离群，MAD 为 0 时不判；显式列出而非静默剔除）、稳健均值（剔除离群后均值，与普通均值并列）、阶段级分位（阶段表增中位与 P95）、尾部归因（最慢一次运行逐阶段 z 分数与相对历史中位倍数，直给哪一步超常）、时段聚合（`--by day|week|hour`）；新增 `--exclude-outlier` 按稳健口径剔除离群后重算全部统计。实测：126 条历史中自动标出 6636s 那条服务端超时运行，尾部归因定位到 `LLM+新闻` 22.37× / z=+6.14，剔除后均值由 519.7s 降至 362.9s。

- **运行观测面扩充（plan-123）：LLM 模块级细分 + full 埋点补回 + 诊断落盘**：`perf_history.jsonl` 记录新增 `breakdown`（父阶段下的子项自身耗时）与 `counters`（运行期诊断计数）两个旁路观测面，**不参与 `total_seconds`**（保历史可比与 ETA 口径稳定）。`core/perf.py` 新增线程安全 `PhaseBreakdownRecorder`（`PerfCollector.recorder(父阶段)` 取用，四模块在线程池并发写不丢计数）；`LLM+新闻` 阶段细分到四个 LLM 模块与新闻获取（`_llm_dispatch` 逐模块计时、`_llm_news` 新闻获取计时，`span_recorder` 为可选参数，None 时行为零变化）；full 路径 `_report_output.py` 两个 helper 经 `run_integrity.current_perf()` 补回 `HTML 生成`/`Excel 生成` 阶段计时（此前 full 运行丢失这两个阶段，实测 126 条历史中二者各仅 6 条且均早期版本）；`errors`/`warnings_count` 由「恒空」改为自动采集——首个阶段计时时挂只计数日志 handler、`save()` 摘除，WARNING/ERROR 自动入 `counters`（错误消息封顶保留，计数照常累加）。`perf-view.py` 分组段新增「阶段细分」表（旧记录无 `breakdown` 时不渲染空表）。方案与口径见 [`perf-observability/perf-observability-design.md`](perf-observability/perf-observability-design.md)。

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
- **报告浏览器验证六项收口（rf-113）**：Iter 7 全链路浏览器人工验证全部完成并移入已解决——自动化回归（headless Chrome 148 一键复跑 `node docs/tmp/rf113/run-rf113.mjs`：① 6 图 badge、② afterprint 快照恢复、③ 断网渲染、⑤ 375px 报告+调试页、⑥ 禁 Canvas 兜底，5 PASS + ⑥ 已知表现记录口径）+ 人工抽验（真实 `Ctrl+P` 打印预览 2x/浅色/不跨页、微信 X5 file:// 表格兜底 + 横竖屏、iPad Safari 90+ 抽验、Windows Chrome/Firefox）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与结论见 `docs/archive/v0.13.x/report-browser-verification/report-browser-verification.md`，勾选清单归档 `docs/archive/v0.9.x/chartjs-upgrade/iter7-verification-checklist.md`；rf-114 前置解锁

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

## [0.13.7] - 2026-10-19

- **优化**：`[L]` 生成确认改**问句式**（用户反馈「提示像要记密码」）——rf-728 合并单屏后只剩键位图例「回车=生成 / f=强制刷新 / q=中止」，语义（走缓存 vs 重新调模型计费、`f` 之后还能选模块）一个字没带，用户须自行推断，且「选模块」看起来像被砍掉了；现先上屏**问句**「是否强制刷新 LLM？（强刷=重新调模型计费；默认=用已有缓存生成，不产生新费用）」，再以按键行作答「回车=用缓存生成 / f=强制刷新（可选模块）/ q=中止」——恢复「问句讲语义、按键只作答」的旧 y/N 读题体验；问句经 `wrap_hanging` 按终端宽度悬挂折行（窄屏不溢出、不挤爆光标）；回归用例锁三点：问句讲清代价差异、问句**先于**按键行上屏、按键行保留「用缓存生成/可选模块」语义词
- **新增**：TUI 统一交互运行时 `panel_runtime`（plan-155，用户反馈 rf-730「上下键仅首页生效」）——「读键 → 导航态 → 派发 → 反馈/重绘」的循环控制流此前在 13 处面板各自手写（`input_choice(arrows=True)` 逐面板按需接、导航态是面板内联变量），导致方向键导航仅首页完整生效：`[S]` 游标只落临时反馈行、重绘后无行内标记（视觉「像没反应」），`[P]` 等其余子菜单完全无导航。新抽 `panel_runtime.py`（`NavState`/`PanelItem`/`panel_loop`）为单一导航语义（语义真值取自主循环），全部列表面板收敛到 `panel_loop`：`[P]` 报告章节 / `[A]` 匿名化 / `[D]` 目录信息 / `[I]` 对比指数 / 缓存管理 / `[S]` 功能开关 / `[M]` 多链优先级（pick=2 + 文本双通道）全量迁移，主循环 `sel` 亦 NavState 化（机械等价替换）；直达键游标同步但不置 engaged（保「键入切换后回车不误触」）、`kind=return` 项不参与导航回绕（保 ↑ 回绕到末开关的原语义）。回归：运行时级测试 28 例 + P/A/D 子菜单导航 4 例 + 主循环 parity 5 例全绿
- **优化**：`[L]` 生成前三次确认合并为**单屏一次确认**（rf-728，用户反馈主路径打断）——原链路「①强刷 y/N → ②选模块 → ③费用预估 y/N（默认 N=中止）」每步读屏等键、默认值组合几乎无信息量；现 `_cmd_generate_full` 先上屏费用预估，随后**单条提示**「回车=生成（走缓存）/ `f`=强制刷新（再选模块）/ `q`=中止」，历史走势 `h` 选项并入（仅 `history.fetch_mode=prompt` 时展示，`auto`/`off` 由共享层 `resolve_fetch_history` 单源解析不另问），默认路径由 2~3 问降为 1 问；日预算超限的「降级走缓存继续 / 中止」安全网确认**独立保留**（费用保护不受合并影响），Esc 即时取消（返回主菜单）语义不变；测试 26 例（合并屏各键分支 / 模块选择 / 预算安全网 / 接线）
- **补刀**（rf-728 合并屏收尾）：按键改**词级精确匹配**（空格/逗号分隔，`f h` 组合生效，`of`/`faq` 这类子串不再误触发强刷/中止）；日预算超限降级路径 `prompt` 模式输出「本次不获取历史走势」提示（告知后覆盖、不追加提问，费用保护与交互最小化兼顾；auto/off 无此输出）
- **守护能力**：`check-doc-traces` 新增「已删除函数残留」检查——常规文档反引号引用的函数当前无定义但 git 历史存在过（单 pass `git log -p` 预计算历史 def 全集约 1s，候选经「含下划线 + 总长 ≥8 + 当前无 def」多重过滤防误报；CODE 级进 HIGH 组），一并清理检出的 6 处历史残留（developer-guide ×2 / llm-technical ×3 / technical ×1，函数改名或删除后文档未同步）；同批补**浅克隆防护**——guards job 全历史克隆（fetch-depth=0：浅克隆下 HEAD 被视作根提交、输出全部现存代码为新增行致历史集≈当前集全漏报，实证伪历史 15752 vs 全史 19924），守护检测到浅克隆/git 不可用时 stderr 告警跳过（不静默假绿）
- **守护能力**：`check-test-redundancy` 新增三类机检（**恒真断言** `assert True`/`x == x`、**死 fixture** 定义后全仓无引用、**弱 mock 断言** `assert <mock>.属性` 真值——Mock 恒真不验证行为）+ `--audit` 建议性骨架审计（同名同骨架分组找复制粘贴嫌疑，默认仅跨文件高信号、`--audit-all` 连带文件内，恒不参与退出码不拦提交）
- **守护能力**：`check-doc-drift` 第 18 项域扩展「返回键不变量」——全部受检文档「返回主菜单」行的键必须为 0（code block/列表项/表格行结构化校验，自由 prose 叙述豁免），拦住人工 grep 会漏的表格内 `` `[B]` 返回 `` 形态；修复 requirements/technical 两处表格残留
- **CI**：test job 恒跑 `-m integration`（42 例纯集成契约，5.5s）——三档按分支分流时代跨模块契约测试不被任何档覆盖（此前菜单键用例陈旧未被发现即为此缺口实证），现恒跑兜底
- **方向键失效根因修复（读键层）+ 交互补齐**：`sys.stdin.read(1)` 用户态缓冲把整包方向键吞入 Python 缓冲，`select(fd)` 此后谎报「无数据」→ 整包 `ESC[B` 被误判为孤 ESC（**与网速无关，电脑上 100% 触发**：首按挂退出确认态并拖慢 0.9s、次按 3 秒窗口内撞确认态即误退出）——读取全部改 `os.read(fd, 1)` 原始字节、select 同 fd；主菜单**任何非 Esc 按键解除退出确认态**（拆包孤 ESC 不被后续按键引爆）；宽档方向键改**原地重绘**（与窄档同手感，不滚屏堆积）；`[S]` 面板行输入新增 `arrows` 参数：↑/↓ 移动 `▸` 选中、Enter 按选中项走既有派发、未导航裸回车语义不变（此前方向键被设计性吞掉=完全无导航）。回归：pty 子进程整包方向键 <0.4s 解析断言 + 确认态解除 + 宽档 TTY 原地重绘 + 面板导航/防误触/纯导航反馈 3 例- **Esc 取消语义补齐提示层缺口**：菜单项内**所有选择类提示**（y/N 确认、级别筛选、日期/编号录入）原为裸 `input()`，Esc 字节被行缓冲吞掉毫无反应——统一换 `input_choice` + 新增统一取消信号（提示处 Esc 抛出、调度层单点捕获打印「已取消，返回主菜单」即时返回，不再等待按键）；QA 长文本提问保留 `q`/回车取消。防误触后无法撤回、以及「同键在不同提示处行为不一致」回退

- **新增**：TUI「分档只改版式不改语义」落地（架构约束 **C29**，窄/宽交互审计后用户确认的统一纪律）——窄屏未登记字母/未知键从静默忽略改为**单行反馈**（`_print_hint`，不整屏重绘；反馈行并入原地重绘清除范围），与宽档「重绘即反馈」语义对齐：任何按键都有可观察结果；新增守护测试 `TestTierSemanticParity` 5 例（登记键/方向键+Enter/未登记键/未知键/Esc 两档同语义同反馈）。历次「互动不一致」缺陷（写路径窄屏不重绘、方向键漂移为孤 Esc、窄屏导航被删、未登记键零反馈）全部收敛进一条可守护的约束

- **修复**：方向键拆包末字节泄漏为独立字母键（rf-726，用户实测「按一次向下键启动了 B 报告」）——`ESC [` 已到但末字节 `B` 在第二续读窗口（0.3s）超时后迟到时，会被当成独立按键 `B` 进入直达分派；新增**半途序列前缀**状态：前缀已消费而末字节未到，下一个字节一律按序列补全处理（拼得出已知序列映射回方向键，否则吞掉为 KEY_UNKNOWN），**永不进入字母分派**——迟到一键最多丢一手，不会误触发功能。测试：末字节迟到映射回方向键 / 无关字节吞掉后恢复正常分派 2 例

- **修复**：主菜单 Esc 退出改**连按两次确认**（3 秒窗口）+ 拆包残留吸收（rf-725，用户两轮复测「按方向键仍退出界面」）——首段 0.5s 共聚窗口仍可能被更高延迟链路击穿，孤 ESC 一到主菜单即触发退出别名；现首按只给单行提示「再按一次 Esc 退出（0 / X 亦可）」，且孤 ESC 后迟到的序列前缀（`[` / `O`）由下一次读键按序列续读吸收并**映射回方向键**（残留字节不再被当成普通按键误触发直达键），`input_choice` 同源置标志/吸收；反馈行并入窄屏原地重绘清除范围（防清帧错位）。测试：双按退出/单按提示/反馈行计入清帧/迟到序列映射/普通键清标志/子菜单残留吞段 6 例

- **新增**：TUI 窄屏恢复方向键导航（用户要求）——窄屏（<64 列）在直达主路径之外恢复 ↑↓/Enter 选中导航：`>` 选中指示器全档渲染，选中移动后**原地重绘**（ANSI 光标上移+清屏，手机短屏菜单不被顶出可视区；POSIX+TTY 门控，管道/测试/旧控制台回退整屏追加），页脚改「窄屏直达：按菜单 [键] 执行 · ↑↓ 选择 · Enter 执行」；原地重绘以帧行数计数代理实现。测试：窄屏主循环 6 例（导航重绘/Enter 执行/原地 vs 回退分支/清帧助手）+ 渲染 3 例

- **新增**：LLM 多链线路优先级三渠道可调（CLI/TUI/Web 同源编辑层）——降级顺序真值 `llm_providers.json → providers[].priority` 此前只能手改 JSON 文件；共享编辑层新增 `llm_providers.priority` 动作写通道（order 置换校验、priority 按新序归一化 10/20…、注释保留写入、写前 .bak），CLI `--llm-provider-order NAME,…`（持久化写盘后退出，区别于 `--feature` 仅本次运行不写盘）、TUI 新菜单 `[M]`（编号交换面板，Esc 返回）、Web 配置面板「LLM 多链线路优先级」块（▲▼ 调序即存，失败恢复原序）。测试：`test_config_llm_providers_priority` 11 例 + CLI/面板/Web 8 例
- **修复**：高延迟链路方向键被误判为主菜单退出（用户实测反馈，rf-723）——终端把 `ESC [ A` 拆包分节到达时，首段 0.3s 窗口超时即判孤 Esc，而孤 Esc 是首页退出别名，按方向键直接退出程序；首段共聚窗口独立加大为 `_ESC_FIRST_TIMEOUT=0.5s`（续读仍 0.3s），并补 SS3 应用光标序列（`OA`/`OB`，部分终端 smkx 后发送）映射（此前落未知键）
- **修复**：`_update_json_raw_text` 对 list 值静默不替换（rf-724）——字段级文本替换只处理 dict（brace 平衡）与标量（正则），list 值匹配不到原文即无声跳过，写入看似成功实则落空；新增 `_replace_array_block`（bracket 平衡，与 dict 版同构）接入分派

- **新增**：子菜单 **Esc 即时返回上一步**（用户实测反馈：误按直达键进入子菜单后只能找「0 返回」）——新增 `tui_keys.input_choice` 菜单行输入（raw 模式逐字节读行、回显自理、孤立 Esc 超时判定即时返回 None，Ctrl+C 转发 KeyboardInterrupt 与既有 except 衔接；非 TTY 回退 `input()`，既有测试驱动方式不变），接入 [S] 面板 / 配置菜单 / 对比指数 / 报告章节 / 匿名化 / 目录信息 / 编辑录入 / 缓存管理 / 问答报告选择 / What-if 选择与路径录入共 14 处；长文本（QA 提问）与 y/N 确认仍走 `input()`（q/回车取消）。测试：`TestInputChoice` 7 例（回退/Esc/回车/退格/Ctrl+C/Windows 两档）+ [S] 与缓存菜单 Esc 返回用例
- **修复**：峰谷计价用例补离线声明（rf-722）——交易日历仅工作日触达（周末短路），周末跑的 CI 探针从未覆盖该路径，周一首燃被网络守卫拦截（CI 单点失败，与当批代码无关）；`test_llm_token_usage` 文件级 `offline_external_sources`
- **优化**：[S] 面板人机交互按「主路径零学习成本」重做（用户实测反馈驱动，rf-721）——提示语从占位符写法「? 编号 看说明」改为一句话教学「输入编号切换开关（如 3）· ?3 查看说明 · 0 返回」；切换/恢复默认等写路径所有宽度**成功即重绘面板**（反馈行带编号 `[OK] 3 名称 已关闭`，手机端不再要求再按 `p`）；`?` 说明查询窄终端留屏不被重绘顶走、宽/中档照常重绘且不再出现「状态已更新」误导提示；r/ra/x/k 高级命令退居页脚图例；`?` 说明入口兼容全角 `？`（中文输入法默认输出全角问号，原实现只认半角）。契约测试 `TestRepaintAndHelpVisible` 三例 + 全角入口只读用例
- **新增**：TUI 首页窄屏（<64 列）「免导航直达」模式——方向键/Enter/未登记字母在窄屏静默忽略且不重绘（此前每按一次整屏追加一屏，手机短屏菜单被顶出可视区），页脚改「窄屏直达：按菜单 [键] 执行」，宽/中档方向键导航不变；`Esc` 加入首页退出通道（与 `0`/`[X]` 并列，页脚统一「Esc / 0 / X 退出」）；ESC 序列分节读取超时 0.15s→0.3s（手机蜂窝网/高延迟 SSH 下方向键序列不被拆散）；新增 `text_layout.wrap_prompt` 折行助手并接入 `tui/` 全部 10 处超窄屏基准的 `input()` 提示（费用确认/级别筛选/报告选择/What-if 输入等），AST 机检守护裸字面量提示 ≤40 列。测试：`test_tui_menu`/`test_tui_keys`/`test_text_layout` 新增 14 例（含宽/窄两档重绘次数断言与提示折行机检），既有「孤 ESC → 未知键」用例按刻意变更改 KEY_ESC。修复（rf-720）：主循环重写时宽/中档 Enter 分支一度丢弃，自审捕获并由两档驱动用例锁回归
- **新增**：HTML 报告与 What-if 页每张交互图表提供「导出CSV」按钮（与「导出PNG」并排，`.chart-export-actions` 组容器浮于图卡右上角）——CSV 取自 `chart.data` 屏显同源数据（Python 数据层已按匿名化口径脱敏，与悬停值一致），UTF-8 BOM + CRLF、RFC 4180 引号转义，`Blob` 纯前端本地下载（零后端），读者可直接做透视/二次分析；按钮定位样式三处模板同步（主报告 / What-if / 调试页）；`test_feature_interactive.py` 新增 4 用例
- **修复**：用户文档残留不存在的交互图表开关描述（rf-719）——FAQ「HTML 报告打开显示不正常」排查项与 CLI 手册 `--feature` 示例注释不再引导 `enable_interactive_charts`/静态回退，改按「Chart.js 唯一渲染、图表引擎与数据内嵌单文件」的当前口径
- 发布编排自动化：`release.py prepare` 现在同时重写 changelog 归档头部——`> 涵盖版本：v{首段} ~ v{末段}（{起} ~ {止}）` 与 `> 归档时间：{发行日}（v{版本} 发布并入；已并入 N 段：v…（MM-DD）、…）`，两行的真值是归档文件自身各 `## [版本] - 日期` 段列表（追加后派生，不会与正文漂移）；早期归档（如 v0.1.x）缺这两行时原样跳过不补写；此前这两行需人工补写，v0.13.6 发布时即漏改过一次；新增 4 单测（区间/并入记录派生、单段形态、无头部行跳过、有头部但无段报错）

## [0.13.8] - 2026-10-20

### 新增

- **doc-drift 新增第 19 项「需求菜单表」检查**：`requirements.md` §3.2 菜单表 ↔ `tui/tui_menu.py`（`MENU_ITEMS` 键集合 / `MENU_GROUPS` 分组标题与组内顺序，退出项归「系统」组）逐项对账——历史漂移（配置组重排未跟、`M`/`Q` 整行缺失、缓存编号写成 `4`）此前完全无机检。实现 `scripts/_doc_drift/_requirements_menu.py`，单测 8 例（解析 / 真库一致 / 缺行·多行·组序·组名漂移检出）
- **TUI 交互契约（`DESIGN-TUI.md`）+ 契约结构守卫**（plan-156）：把设计稿定稿为 TUI 侧唯一判据，与 `DESIGN.md` 对称——键分工总表（含每键"禁止用法"）/ 提示三段式四成分 / 默认项与取消标注语法 / 配色一色一职责 / 术语表与四档适用范围 / 反馈与空态口径 / 按键闸门白名单 / 护栏 / Known Gaps；结构测试由 9 例扩到 19 例（必需节含 Colors、四张表列集合、关键口径句成句存在、闸门白名单文档↔代码双向一致）。CLAUDE.md「设计契约」拆为 Web/HTML 与 TUI 两份及各自守卫；developer-guide 触点清单新增「TUI 交互改动」行
- **`?` 帮助全面板可用 + `?键` 单项详情**（plan-158）：`?`（本面板可用键一览）与 `?键`（第 N 项详情）由 `panel_runtime` 统一承接（此前仅 `[S]` 面板有）；`PanelItem` 新增 `detail` 字段，`_emit_help` 以 `hint=item.detail` 渲染，`[P]`（章节切换影响）/`[A]`（模式切换效果）/`[I]`（增删重置作用）/`[M]`（模型·优先级·端点）/缓存面板（清理范围）已填文案，`[S]` 保留 `on_help` 富详情——面板各写业务含义、渲染单源
- **主菜单按任务分组 + `/` 关键词筛选**（plan-164）：19 项平铺改为四组渲染（生成报告 / 数据与查看 / 配置 / 诊断与排查），退出项单列，组标题只降低扫读成本、不改任何按键；`/` 筛选先比按键再比标签文字，筛选态只渲染命中项、`↑↓` 在命中集内回绕、按到隐藏项给单行反馈、`0` 先清筛选
- **击键数与屏幕语义纳入门禁**（plan-165）：三条主路径 E2E 动线（生成完整报告且只重新生成指定模块 / 改一个功能开关并确认生效 / 按级别筛日志）同时断言「击键数不增」+「关键用户词上屏」，契约快照 `tui_flow_contract.json`；击键基线 6 条动线（含 `/` 筛选动线），P0 跑生成主路径 1 条、P2 跑全 3 条
- **FAQ 新增「手机与移动端」章节**（plan-147）：推荐动线（完整报告交定时任务生成、手机看 Web/HTML、TUI 只做轻操作）、客户端建议（Termux / Termius / JuiceSSH / Blink，含方向键失效与 `Esc` 双按要点）、断线后果（生成中断但已完成报告与缓存不受影响）、窄屏可见性；TUI 手册窄屏节互链
- **`switch_panel.render_titled_panel` 共享原语**（plan-148）：宽/中档画盒线、窄档退化为「结构标题行 + 无边框行 + 行内截断」，供所有盒线面板按档位渲染

### 变更

- **Web 配置面板与 TUI 配置组的关系写清**：`how-to-use-web-mode.md` 原只写「9 组与 TUI 可编辑项完全一致」，易被读成顺序也一致——补说明：9 组按配置数据类型编排，TUI「配置」组按使用频次编排，两者只保证「可编辑项集合相同、写同一份配置文件」，顺序差异属设计选择。Web 前端零 TUI 菜单文案，无需改代码
- **「配置」组内顺序调整为 P → S → M → I → A → D → R**：常用操作前置（报告章节 / 功能开关 / LLM 多链），低频操作在后（对比指数 / 匿名化 / 目录信息），刷新配置仍收尾。键位与行为不变；文档同步：两个手册的主菜单块与分组成员说明、用户手册「配置管理类」章节次序、`requirements.md` §3.2 菜单表（顺带补齐遗漏的 `M`/`Q` 行、缓存管理编号 `4`→`3`、分组改为与实际菜单一致）与 R-TUI-08 面板清单、`testplan.md` 菜单枚举
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

- **功能开关门控可逆 + 返回首页即生效**（rf-739）：`_apply_feature_gates()` 原先切片过滤 `MENU_ITEMS` **本体**（无母本）且只在启动调用一次——运行时在 `[S]` 打开 `report_qa`/`doctor_check`，被裁掉的 `[Q]`/`[T]` 仍不出现，必须重启。现改为**从 `_ALL_MENU_ITEMS` 母本重建**（幂等可逆，切片赋值保持列表对象），主循环重绘点每帧重建门控并同步 `nav.count`（裁剪后游标夹紧），开关改完返回首页即生效。回归：先关后开完整恢复 / 列表对象同一 / 主循环接线断言
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

## [0.13.9] - 2026-10-20

### Added

- 调仓 What-if 对比页右上角「打印 / 导出 PDF」按钮：与主报告同参（44×44 触控、语义 token、打印稿自隐藏），双页入口一致（plan-128）

### Changed

- 报告模板 40 处内联 `style=` 色值全部 token 化归零：新增组件派生 token `--heat-*`/`--corr-*`/`--cell-na-bg`/`--alloc-*`/`--danger-text`（DESIGN.md Colors 登记，暗色配对同步）；设计护栏 W3 内联色值归零并由观察升为 E 级 finding（W4 字号/W5 间距保持观察）（plan-167）

### Fixed

- 新闻去重同主体不同事件误合并治理（两处）：bg=2 梯度泛词否决表补 `gdp`（跨经济体 GDP 数据发布实证误合并）；bg=3 下限档新增事件信号词组一致性判据（`_EVENT_GROUPS` 17 组，组内互认，锚点回放拦截 2,566 条、合并侧真重复无误杀；≥4 实体证据更强档维持现状）
- 校准工具锚点超线告警按重复行占比分流：重复率低于 5% 不再建议 `--compact`（去重无收益），改指上调告警线；`--compact` 零收益时输出成因说明
- `write_llm_providers` 写盘后将 `llm_providers.json` 权限收紧为 0o600（含 api_key 的凭据文件与 cache 域敏感文件同标准；Windows 静默跳过），补新写/重写收紧两用例
- 设计护栏 W3 内联色值观察项完成误报归类（40 处全为真实存量），批量 token 化收口任务登记 plan.md `plan-167`（含入域条件）
- 需求文档核查修正：R-OUT-12 删除行内重复的「覆盖章节」残留清单（与实现折叠章节全集不一致）、R-LLM-01 触发范围更新为三渠道完整报告口径（原「仅菜单 L」过时）、R-CON-07 补充 R-CCH-08 联网必需模块例外边界
- `market_hours`：`is_market_open()` 增加进程内分钟级 memo，「市场时段」DEBUG 日志仅在判定结果变化时输出——消除 TUI 常驻轮询下 7 天 12 万行重复 DEBUG（占 app.log 总量 60%）
- 数据源重试：解析/数据形状类异常与 perf 基准禁网桩不再走传输级退避重试——`core/retry.py` 新增 `is_parse_failure_exception` / `is_deterministic_failure` 判据，`with_connect_retry` / `run_with_timeout` / `tencent` K 线与价格 / `financial_indicator` 多期直连同口径接入（前者是确定性数据缺陷，重试必然重复；后者是设计使然的禁网）
- `chain_incremental`：历史修正全量刷新增加连续触发冷却——检出重叠达到阈值后判定为源结构性回看，跳过全量刷新沿用按日合并结果；无重叠合并成功即重置计数（消除每运行多拉一次全量 260 天）

## [0.13.10] - 2026-10-20

### Added

- `check-doc-traces` 结构性冗余机检（DUPLICATE 类）+ 归档域痕迹加固：重复标题全域检出且路径感知（同级+同标题+同父标题才算重复，各版本块/任务节下同名小节跨父级合法，同父复现即真重复）；台账文件（plan.md / review-findings.md / changelog.md）与 docs/archive/ 归档域另检 ≥40 字符重复内容行与连续 5 行重复区块——拦截「同一区块/条目粘贴两遍」类复制粘贴残留与冗余信息；豁免：围栏与未围栏代码样本、命令续行、键值任务卡、验证清单项（- [ ] 命令跨阶段复跑）、分隔/装饰行与短模板行；长行/区块判重同小节限定（跨小节共享行/表属结构，同小节内自第 2 次起报出）。归档域（docs/archive/**）另检 NARRATIVE 复盘痕迹——归档设计/迭代计划同样只表述最新状态（changelog 归档仅 DUPLICATE，记录变化是其职责；CIPHER/版本痕迹/章节轮次属历史文档性质不入检）；NARRATIVE 匹配剔除行内代码段（词表令牌 `不再` 不误报），结论缓存输入纳入归档文档。归档全量核查 386 处按文件×类型分桶定位（DUPLICATE 177 / NARRATIVE 209）并全部清理归零（复扫 0 处）；7 份任务代号文件名语义化改名（B1-/A5-/r178-/r197-/r198_/task91- 前缀剥离，folders.md 目录树与三份归档 changelog 引用同步）；文件名任务编号检查扩展系列代号形态（task\d/系列字母+数字/P3-04 全形，phase 词形如 p1-optimization 不误伤）。脚本行数红线拆分：`check-doc-traces` 收归薄 CLI，DUPLICATE 扫描实现拆于 `scripts/_traces_doc/` 包（原面 re-export，行为不变）。新增专项测试（路径感知跨父/同父复现/台账与归档域限定/同小节正向与跨节豁免/续行豁免/区块重复/清单/任务卡/代码样本/围栏/归档模式面/行内令牌/系列代号文件名）；管理文档同源描述与实现对齐（check-doc-traces 能力含结构性冗余、doc-drift 清单补需求菜单表与手册菜单块、file-length 阈值 1000/1000/1200、_traces_doc 入共享设施与技术约束包清单、testplan 补发布数据文档刷新项）
- `check-code-traces` / `check-requirement-trace` / `check-doc-drift` 接入结论缓存（`--ci` 且非 verbose，doc-drift 另排除 `--sync` 写路径、非 git 环境不缓存）：逻辑与全集输入指纹未变时逐字回放上次输出与退出码（冷/热输出一致，仅多一行缓存注释），同树重复（发布门禁 → 提交钩子 / 失败重试）命中省全仓扫描；与既有接入面合计六个 namespace（缓存目录经 `CHECK_CONCLUSION_CACHE_DIR` 测试隔离）。新增回放接线测试（回放不重扫/输入失效重扫/退出码分级保持）与机制矩阵同步更新；`--with-test-count` 为含 pytest 收集的独立输出面，不入缓存（防止跨模式回放丢核对段/污染结论）
- `check-doc-traces` 目录树描述纪律机检：树行（│├└）豁免收窄为仅归档引用类（此前全类别豁免使任务编号与历史痕迹整体过闸）；新增 STATUS 进度状态词类（已实施/已完成/完成态/随任务完成移入/验收·判定·实施记录指引/§N 章节指引/已归档/已核实/树行「不再」/稿态词（草案/初稿/终稿）等，仅目录树域检出，正文当前状态叙述合法不检）；新增受检域 .md 文件名任务编号检查（rf-N/plan-N，语义命名补位）；HIGH 来源叙述补强（无后缀模块名的迁入/移入）。测试 115 passed
- `check-doc-traces` 任务记录域复盘痕迹机检（NARRATIVE 类）：plan.md / review-findings.md / docs/plan/* 的任务内容只反映最新状态——禁修复/改造前后对比、相对旧实现的否定句（不再XX）、历史归因；任务状态标记（已修复/待处理）、根因定位引用、迭代轮次与设计文档旧格式兼容是内容合法；changelog 仍仅章节编号（记录变化是其职责），常规手册不检（「修复后重启」是操作指引）；任务域不走表格豁免（断言表行内叙事必检）。存量 10 处清理（计划页放弃项边界句改「禁止重提」、浏览器验证文档去修复前后对比数字）。测试 122 passed

### Changed

- 发布编排提速：`release.py refresh` 条件化——上次发布 tag 以来的变更仅 `.md`/图片文件时自动跳过 bench + collect（测试计数无变化，下一含程序/测试变更的发布自动补齐；`--force-refresh` 强制恒跑，取不到 tag 或存在未跟踪程序文件时保守恒跑），docs-stats sync 恒跑；`gate` 十守护并行且并发度随核数收敛（4 路封顶、2 核机自动 2 路；守护均只读 `--ci`，结论缓存每 namespace 独立文件、事实缓存均为原子 temp+rename 写，无互踩）；`test-runner` 新增 `--jobs` 多档模式并行采集（优先级 CLI > `TEST_RUNNER_JOBS` 环境变量 > 自适应——4 核+ 为 2，弱机/缺核信息/核数采集异常一律取 1 不超订；环境表新增「采集并行度」行，跨并行度不直接可比），`machine_info` 同步携带采集并行度
- pre-commit 调度：`check-doc-drift` 纯 `--ci` 分支改为后台并行（与快集守护重叠，回放前统一等待），`--sync` 写路径保持串行先行避免 folders.md 写读竞态；回放段同步顺序不变
- `folders.md` 目录树描述全面去任务号与历史痕迹（三轮共 60+ 处）：任务编号（plan-N/rf-N）改为语义描述；已实施/验收记录指引/阶段进度/随任务完成移入等状态与流转措辞全部移除，描述仅保留文件内容简要；归档设计文件语义化改名（`plan-4-brinson-attribution-abandoned.md` → `brinson-attribution-abandoned.md`、`plan-11-dark-mode-plan.md` → `dark-mode-plan.md`，引用同步）
### Fixed

- 发布归档迁移补录：v0.13.9 批 rf-740~751 十一条此前仅从台账删除、摘要未落归档（自审 rf-755），已从迁移提交父本恢复补录；防复发的占位↔归档节机检已登记（rf-756，随下一工作批实施）
