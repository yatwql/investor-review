# LLM 关键路径测量与调度调整设计

> **关联任务**：`rf-944`（详见 `docs/managements/review-findings.md`）
> **状态**：已完成 —— 代码/测试/注释落地，A1~A6 六条运行判定全部通过（4 次完整报告实测）；「范围外选项」列出的主收益项经决策不实施
> **范围外评估**：[`llm-critical-path-design.md`](../llm-expression-budget/llm-critical-path-design.md)（表达预算 / TTL 提升 / 指纹瘦身三组实测均不采纳，本文沿用其结论，不重复评估）

## 0. 术语

| 术语 | 含义 |
|---|---|
| 归因模块 | 持仓变动复盘归因，`llm/holding_change_review.py`，模块键 `holding_change`，缓存前缀 `llm_holding_change_`，开关 `enabled_llm.holding_change` + feature `holding_change_review` |
| 基础四模块 | `global_macro` / `expert_review` / `health_check` / `penetration_deep` |
| 串行尾 | LLM 阶段中在并行批结束之后才开始、且与并行批不重叠的调用段 |
| 关键路径 | `LLM+新闻` 阶段墙钟中由单次调用延迟或不可重叠段决定的部分 |

## 1. 基线

### 1.1 单次运行拆解（2026-10-28 14:52，LLM+新闻 = 123.0s，n=1）

| 模块 | 起→止（相对 LLM 阶段起点） | 耗时 | 调度位置 |
|---|---|---|---|
| global_macro | +37 → +41 | 4s | 并行批 |
| penetration_deep | +37 → +49 | 12s | 并行批 |
| health_check（thinking） | +37 → +61 | 24s | 并行批 |
| **expert_review（thinking, medium）** | +37 → +119 | **82s** | 并行批内最长项，输出 14,783 token |
| self_review | +119 → +130 | 11s | 串行尾（输入是四模块产出） |
| **归因模块** | +130 → +155 | **24.6s** | 串行尾（只读持仓变动契约） |

并行批由 `_llm_dispatch._dispatch_llm_workers` 提供：`ThreadPoolExecutor` + `max_concurrency=3`，thinking 模块另受 `llm_max_thinking_concurrency`（2）约束。由此 `LLM+新闻 = max(并行批) + 串行尾`，提高并发度不影响 `max(并行批)`。

**串行尾消除的判定依据**：归因模块与四模块无数据依赖，其 24.6s 属可消除段；`self_review` 的 11s 不可消除（依赖四模块产出）。

### 1.2 跨运行回归（13 次完整报告，2026-10-25 ~ 2026-10-28）

| 模块 | 单次耗时 | 输出 token | 速率 |
|---|---|---|---|
| expert_review | 57–110s（p50 ≈76s） | 9,789–14,783 | ≈164 tok/s |
| health_check | 22–72s | 3,168–8,653 | ≈157 tok/s |
| penetration_deep | 11–44s | 1,465–2,110 | ≈116 tok/s |
| global_macro | 4s（1 次 111s 端点异常） | 500–801 | ≈125 tok/s |
| self_review | 11s | ~1,600–2,100 | ≈180 tok/s |
| 归因模块 | 4–25s | 668–914 | 8–25 tok/s（含排队） |

`expert_review` 单变量线性拟合：`延迟 ≈ 6.08 ms/输出 token`（R²=0.52）。该拟合只用于判断「延迟主因是输出长度」这一量级关系，不用于预测单次耗时；残差 48% 来自端点峰时（同 token 量闲时 57s、峰时 82s）。

正文长度对照：`expert_review` 缓存正文剥离标签后 **10,001 字**；`report/llm_quality.py` 对该模块的参考篇幅为 **1,000 字**（降级下限 400 字）。来源：`data/cache/llm_expert_review_*` 的 `_data` 字段与 `_LENGTH_THRESHOLDS`。

### 1.3 与既有台账的口径对账（n=1，2026-10-28 14:52）

`perf_history` 的 `breakdown["LLM+新闻"]` 已按模块记 span：新闻源抓取 3.08s、去重与关联 2.13s、锚点维护 0.01s、新闻获取 5.23s（含前三者）、事件窗装配 0.13s、全球政经局势 3.87s、穿透深度分析 7.89s、持仓体检报告 23.70s、智囊团深度复盘 81.60s。

| 对账项 | 数值 |
|---|---|
| `LLM+新闻` 阶段墙钟 | 123.00s |
| 并行批最长 span（智囊团深度复盘） | 81.60s |
| 差值 = 串行段 + 非 LLM 段 | 41.40s |
| 非 LLM 段（新闻获取 5.23 + 事件窗 0.13） | 5.36s |
| 串行尾（`self_review` 11s + 归因 24.6s） | 35.6s |
| 残差 | 0.44s（阶段边界与计时取整） |

结论：串行尾模型与台账自洽（残差 <0.5s），A1 的扣除项因此可精确列出。

### 1.4 由基线得到的设计约束

1. 单次调用延迟由输出长度与端点状态决定 —— 并发度不是压缩 `max(并行批)` 的杠杆。
2. 串行尾（归因模块 + `self_review`）可消除性不同，只有归因模块可入批。
3. 并行批模块的耗时已有事实源（`breakdown["LLM+新闻"]` 的模块 span），**缺口在串行尾模块**：`self_review` 与归因不在 span 记录范围内，且 `llm.modules` 不记耗时。度量补齐要补的是这一块，不是重复 span 已有的数据。

## 2. 设计

### 2.1 逐模块耗时入台账

`perf_history.llm.modules[*]` 记 `duration_seconds`（秒，保留 3 位小数）。两个写点，二者互补：

| 调用形态 | 写点 | duration 取值 |
|---|---|---|
| 缓存未命中（真实调用） | `llm/skeleton.py::_run_standard_mode` → `session.record_per_module(duration=...)` | 本次调用墙钟 |
| 缓存命中 | `llm/api_base.py::_cached_hit_html` → `session.record_per_module(cached=True)` | `0.0`（无调用） |

读点：`report/_generation_shared.py::_record_llm_context` 把 `modules[*]` 投影进 perf（新增 `duration_seconds` 字段）。落盘走既有 `core/jsonl_store` 原子追加原语（复用既有落盘设施，不自写文件）。

两个耗时口径的分工（不可混用比较）：

| 指标 | 来源 | 覆盖范围 | 用途 |
|---|---|---|---|
| 模块 span | `perf.breakdown["LLM+新闻"][模块名]` | worker 全生命周期（含客户端创建/关闭、缓存读取） | 关键路径判定（A1/A2/A5） |
| `duration_seconds` | `session.record_per_module(duration=)` | 仅 provider 真实调用 | 单次调用与端点速率分析（A3/A4） |

聚合口径：统计耗时**只取 `cached=false` 的样本**；`cached=true` 记 `0.0`（`record_per_module` 的 `duration` 缺省值），仅表示「无调用」，不参与均值/分位计算。

### 2.2 归因模块并入并行批

| 项 | 设计 |
|---|---|
| 依赖 | 只读 `pipeline_data["holding_change_data"]`（契约由实验挂载点 `inject_holding_change_data` 在数据准备阶段写入）与 `holdings_details` / `purchase_constraint_block`，不读写基础四模块产出 |
| 注册 | 双点登记：`llm/_llm_dispatch.py::_build_module_fns` 的 `_MODULE_FNS["holding_change"]` + `core/data_registry.py` 的 `llm_holding_change` 条目（缓存前缀 / TTL / settings_suffix 单源） |
| 适配 | `run_holding_change_in_worker()` 把 `run_holding_change_review()` 的 `bool` 结果转换为调度层 `(result, from_cache)`；`result="ok"` 表示契约已写入 |
| 客户端 | 透传分发层为本次任务经 `core/http_client.make_http_client` 创建的客户端（统一 HTTP 客户端工厂；与基础四模块同一装配路径），任务结束由分发层关闭 |
| 缓存语义 | 键与指纹不变，仍由 `llm/module_fingerprint.py::holding_change_review_fingerprint` 唯一构造；调度位置不影响缓存命中判定 |
| 失败隔离 | 异常、契约缺席、开关关闭、无有效内容四种情形均在模块内部降级为「无归因」，契约字段保持 `None`，报告归因块隐藏 |
| 日志 | 走 `logging.getLogger("invest")`；异常记 WARNING + `exc_info`，不进 ERROR（不阻断报告） |
| 串行保持 | `self_review` 不登记进 `_MODULE_FNS`：其入参是基础四模块产出，入批会读到 `None` |

### 2.3 并发配置维持 `max_concurrency=3`

基础四模块 + 归因共 5 个任务在 3 worker 下只有 2 个排队位置（实测第 4 个任务在 +4s 才拿到 worker，第 5 个在 +5s 左右）。thinking 模块另受信号量 2 约束（强制推理端点并发 thinking 时会出现 HTTP 200 空内容）。提至 4 的收益上限约 4s，与端点空响应的风险不对称，配置维持现值。

### 2.4 开关与档位

| 判定 | 位置 | 说明 |
|---|---|---|
| feature `holding_change_review` | 报告层（`inject_holding_change_data`） | 关闭时契约键缺席 → 归因模块内部即时短路，不产生 LLM 调用 |
| `enabled_llm.holding_change` | 归因模块内部 | 关闭时即时短路 |
| 深度档位 `depth_gate` | 不参与 | 归因只由上面两条决定，不受 `brief` / `standard` 档收窄（与既有语义一致） |
| 总时间预算 `llm_total_time_budget_sec` | 分发层 `make_budget_guard` | 入批后归因受预算约束（超预算则跳过并记 WARNING）；串行调用期不受该闸约束 |

开关枚举与默认值的唯一事实来源仍是 `core/registry.py`，本设计不新增开关键。

### 2.5 实验挂载点顺序

`inject_holding_change_data` 位于数据准备阶段（`report/_generation_full.py` 2b2、`report/_generation_both.py` 2b2），早于 `LLM+新闻` 阶段（同一文件的 `perf.start("LLM+新闻")` 之后）。因此派发时契约已就绪，归因入批不改变「实验功能经挂载点接入」的顺序约束。

### 2.6 行数与拆分

本次改动落点行数：`llm/_llm_dispatch.py` 534 行（警告线 700）、`llm/generators_orchestrator.py` 842 行（已在文件膨胀登记表）、`report/_generation_shared.py` 143 行。均在红线以内，`generators_orchestrator` 的拆分观察维持既有登记。

## 3. 架构约束合规

约束清单见 `technical.md`「架构设计约束」；下表按语义名逐条给出本设计的结论。

| 约束（语义） | 结论 | 依据/落点 |
|---|---|---|
| 缓存统一管理 / 缓存原子写入 | 合规 | 归因缓存仍走 `cache.get/set`；perf 落盘复用 `core/jsonl_store` 原子追加 |
| HTTP 客户端统一 | 合规 | 分发层经 `core/http_client.make_http_client` 单工厂创建；provider 层自建一次性客户端的兜底分支保留给仍串行的 `self_review` |
| 日志统一 | 合规 | `logging.getLogger("invest")`，异常 WARNING + `exc_info` |
| LLM 模块注册 | 合规 | `_MODULE_FNS` + `data_registry` 双点登记；「无独立并行调度语义不得登记」由 `self_review` 仍不登记体现 |
| Provider Chain 必经 | 合规 | worker 内仍经 `call_llm()` → 策略/API 链式路由，无直接 provider 调用 |
| pipeline_data 数据契约 | 合规 | 只读既有 `holding_change_data` 键，契约 Schema 不变 |
| 缓存指纹唯一事实来源 | 合规 | 仍由 `holding_change_review_fingerprint` 构造，调度位置不参与指纹 |
| 实验挂载点集中 | 合规 | 契约由 `inject_holding_change_data` 注入，见「实验挂载点顺序」 |
| 功能开关注册表唯一事实来源 | 合规 | 不新增开关键 |
| 重试与退避唯一原语 | 合规 | 仍经 `core/retry`；未引入自定义重试 |
| 间隔节流唯一原语 | 合规 | 仍经 `llm/pacing`；thinking 信号量不适用于归因（非 thinking 模块） |
| 大文件红线 | 合规 | 见「行数与拆分」 |
| 代码类型判定 / 会话缓存复用 / 取数链路由 / 新闻召回策略 / 渲染期全局 / 控制台着色 / 路径绝对化 / 凭据分离 / 图表图下说明 / 交易日口径 / TUI 分档 | 不涉及 | 本次不改资产判定、会话缓存、取数链、新闻召回、渲染全局、配色、路径、凭据、图表说明、交易日、终端版式 |

## 4. 可度量验收

### 4.1 单测（通过判据 = 断言对象成立，且 `check-test-redundancy` 无 finding）

| # | 判定对象 | 用例 |
|---|---|---|
| T1 | 归因在非主线程执行，且收到非 `None` 的 `http_client` | `unit/llm/test_holding_change_injection.py::test_holding_change_runs_in_worker_thread_and_writes_contract` |
| T2 | 归因抛异常时调度结果为 `None`、契约字段仍为 `None`、不抛到调用方 | 同文件 `test_holding_change_failure_isolated` |
| T3 | `holding_change` ∈ `_build_module_fns`；`self_review` ∉ | 同文件 `TestRegistryAlignment::test_registered_in_dispatch_module_fns` / `test_self_review_stays_serial` |
| T4 | 同一输入经分发层二次调用只触发 1 次真实调用（缓存命中不破） | 同文件新增 `test_cache_hit_through_dispatch` |
| T5 | `modules[*].duration_seconds` 非命中记实际值、命中记 `0.0` | `unit/llm/test_cache_recompute_attribution.py::TestPerfModuleLatency` |
| T6 | `api.call_llm` 在归因执行路径上被调用（证明走 chain 而非直连 provider） | `test_holding_change_injection.py::test_routes_through_provider_chain` |
| T7 | 契约键缺席 / `enabled_llm.holding_change=false` 时无 LLM 调用（短路） | 同文件 `test_short_circuits_without_contract` / `test_short_circuits_when_disabled` |
| T8 | 登记说明与 docstring 的调度表述与实现一致：必须不含「无独立并行调度语义」「刻意不进」；必须含「同批并行调度」 | 同文件 `test_registry_notes_match_parallel_dispatch`（读生产源码断言，非 mock 回读） |

### 4.2 运行验收（判定式，机检可复算）

样本要求：**≥3 次完整报告**（`report_type=full`），同深度档、同持仓数，取 p50。A1 / A2 / A6 只用「至少一个基础模块非命中」的运行（缓存全命中的运行无法判定关键路径）；A3 另需一次缓存全命中运行验证其 `cached=true` 分支。

绝对时长（如基线 123.0s）随峰谷时段变化（高峰单价与时延均为闲时的约 2 倍），故判定式取**窗口归一化**形式，不设跨时段绝对区间。

| # | 判定式（全部取 p50） | 通过判据 / 失败处置 |
|---|---|---|
| A1 | `LLM+新闻` − max(`breakdown["LLM+新闻"]` 模块 span) − (新闻获取 + 事件窗装配) − `self_review` ≤ **5s** | 串行尾已消除（归因耗时与并行批重叠）。失败 → 判定未真正重叠 |
| A2 | `expert_review` p50 ≤ **83.6s**（基线 p50 76s × 1.10） | 失败 → 判定入批引入负作用 → 回滚 |
| A3 | 该次运行归因 `cached=false` 时 `duration_seconds` ≤ max(基础四模块 span)；`cached=true` 时要求基础四模块也全部命中 | 双条件避免把「未测到」当作「测到通过」 |
| A4 | 抽 1 次运行：`duration_seconds` 与日志「生成完成」时间差偏差 ≤ **1s** | 失败 → 度量失真，先修度量再看 A1~A3 |
| A5 | 入批后 `breakdown["LLM+新闻"]` 不出现「归因耗时落在智囊团 span 之外」的额外段（即差值项只剩新闻段 + `self_review`） | 重叠性的可复算版本；与 A1 互补 |
| A6 | 每次运行满足 `LLM+新闻` ≤ max(非命中模块 span) × 1.15 + 新闻段 + `self_review` | 防「只要比基线小就算通过」的假通过；系数 1.15 为装配开销余量 |

**口径说明**：

- A1/A5 用 `breakdown` 的模块 span（覆盖 worker 全生命周期，含客户端创建与关闭）；`duration_seconds` 只覆盖 provider 调用时长，两者不可混用比较。
- `self_review` 在 `llm.modules` 中有 `duration_seconds`（`record_per_module` 以模块键记账），但不在 `breakdown["LLM+新闻"]` 的 span 里（它不经 `_MODULE_FNS` 调度）。A1 的扣除项直接取 `modules.self_review.duration_seconds`，无需读时间戳。
- 复算命令：`.venv/bin/python -c "import json;p=[json.loads(l) for l in open('data/state/perf_history.jsonl',encoding='utf-8')];print([r['breakdown']['LLM+新闻'] for r in p[-3:]])"`

### 4.3 实测结果（2026-10-28 19:45 ~ 19:49，4 次完整报告）

| 运行 | 时刻 | 时段 | `LLM+新闻` | max(非命中模块 span) | 新闻段 | `self_review` | 归因 | A1 残差 | A6 上界 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 19:45:38 | 闲时 | 88.30s | 71.60s（智囊团） | 7.58s | 9.10s | 6.51s | **0.02s** | 99.02s ✅ |
| 2 | 19:47:10 | 闲时 | 74.11s | 61.49s（智囊团） | 0.11s | 12.50s | 5.80s | **0.01s** | 83.32s ✅ |
| 3 | 19:48:27 | 闲时 | 61.58s | 48.53s（智囊团） | 0.11s | 12.90s | 5.67s | **0.04s** | 68.82s ✅ |
| 4 | 19:49:35 | 闲时 | 12.51s | 0s（六模块全命中） | 0.11s | 12.40s | 0s（命中） | 不适用 | 不适用（A3 专用样本） |

| 判定 | 结果 | 依据 |
|---|---|---|
| A1 | 通过 | 残差 0.02 / 0.01 / 0.04s，均 ≤ 5s：归因耗时完全与并行批重叠 |
| A2 | 通过 | `expert_review` 非命中样本 71.6 / 61.5 / 48.5s，p50 = 61.5s ≤ 83.6s |
| A3 | 通过 | 归因 6.51 / 5.80 / 5.67s 均远小于同次 max span；运行 4 中归因 `cached=true` 且基础四模块全部 `cached=true` |
| A4 | 通过 | 运行 3：归因日志 19:47:22.640 → 19:47:28.313 = 5.673s vs `duration_seconds` 5.67（Δ0.003s）；`expert_review` 48.538s vs 48.5（Δ0.04s） |
| A5 | 通过 | 差值项仅剩新闻段 + `self_review`，无其它额外段 |
| A6 | 通过 | 三次运行的 `LLM+新闻` 均低于各自上限（99.02 / 83.32 / 68.82s） |

附带观测：

- 归因 span（`breakdown["LLM+新闻"]["持仓变动复盘归因"]`）在运行 1~3 为 6.51 / 5.80 / 5.67s，运行 4 为 0.0s（缓存命中）。
- 墙钟：四次运行 100.6 / 82.3 / 68.2 / 21.7s；`LLM+新闻` 占比 88.3 / 74.1 / 61.6 / 12.5s。
- 成本：四次合计 ¥0.359（闲时单价；三次强制重算 + 一次缓存命中）。
- 缓存全命中运行仍提交归因任务（风险 R5 预期行为）：其耗时 0.0s、成本计入命中侧，无额外调用。

### 4.4 劣化保护线

任一条件触发即回滚归因入批（从 `_MODULE_FNS` 摘除、恢复编排层串行调用）：
- A2 失败（`expert_review` p50 劣化 >10%）；
- A3 失败（归因未与基础模块重叠）；
- 运行日志出现归因异常 WARNING（同一条重复出现 ≥2 次）。

## 5. 质量管控

### 5.1 影响面

| 面 | 受影响项 | 处置 |
|---|---|---|
| 生产代码 | `llm/_llm_dispatch.py`（+包装与登记）、`llm/generators_orchestrator.py`（去串行调用、置 `needs`）、`llm/holding_change_review.py`（+`http_client` 透传）、`report/_generation_shared.py`（+字段） | 已实现 |
| 既有测试 | `test_holding_change_injection.py::TestRegistryAlignment` 原断言「不得进线程池」 | 改写为双向不变量（T3） |
| 注释/文档 | `core/data_registry.py` 条目说明、`holding_change_review.py` 模块 docstring 中「串行取用」表述 | 同步为并行口径（T8 机检） |
| 设计文档 | `llm-technical.md` 模块表 / 客户端兜底小节 / 注册清单；`technical.md` 目录树注释；`changelog.md` | 已同步 |

### 5.2 负向断言（禁止项，纳入 T1~T8 的断言面）

- 归因路径上不得出现直接 provider 调用（由 T6 从 chain 侧证明）。
- worker 内不得写模块级全局（`_debate_info_container` / 渲染期全局），归因只写 `pipeline_data` 契约。
- 不得用 `print` 输出运行时信息（日志统一走 `invest` logger）。
- 不得在归因模块内二次登记缓存键或指纹。
- `offline_external_sources` 只作用于声明它的用例：本文件的端到端兜底客户端用例依赖真实客户端构造，fixture 提到模块级会让该用例失真。
- 调度表述类用例读生产源码（`PROJECT_ROOT` 下的固定路径），文件搬迁时须同步用例路径。

### 5.3 观测三面

| 面 | 载体 | 可见内容 |
|---|---|---|
| 日志 | `invest` logger | 「正在生成：持仓变动复盘归因…」/「…生成完成」、预算跳过 WARNING、异常 WARNING + `exc_info` |
| 台账 | `perf_history.llm.modules.holding_change.duration_seconds` + `cached` | 耗时与命中态；报告 LLM 用量页签按既有字段渲染，新增字段为纯增量、不改变表结构 |
| 契约 | `pipeline_data.holding_change_data.llm_review` | 有内容 = 产出成功；`None` = 未产出（原因见 `_register_skip_reason` 三态：契约缺席 / 开关关 / 无有效内容） |

### 5.4 度量产物对下游消费者的影响

`llm.modules[*]` 的既有消费者与字段依赖：`llm/cost_forecast.py`（`costs`）、`llm/cost_tracker.py`（`per_module` 用量）、报告 LLM 用量页签（`model`/`thinking`/`cached`/`input_tokens`/`output_tokens`/`costs`）。`duration_seconds` 为新增键，上述消费者按键取值，不做严格 schema 校验，故为纯增量。

## 6. 风险登记

| # | 风险 | 影响 | 缓解 | 回滚/触发 |
|---|---|---|---|---|
| R1 | 归因入批后抢占 worker 槽 | 基础模块延后启动（实测 ≤5s） | 归因单次耗时（4–25s）远小于 `expert_review`（57–110s），不构成新关键路径；A2 监控 | A2 失败即回滚 |
| R2 | 归因异常外溢拖垮并行批 | 报告整体失败 | 包装层 `try/except` 全覆盖 → 降级为「无归因」；T2 断言 | 异常 WARNING 重复 ≥2 次即回滚 |
| R3 | 预算闸跳过归因 | 归因块隐藏（超预算时） | 预算本是全局保护闸，归因属可缺省内容；跳过记 WARNING 可见 | 无需回滚（配置项可调大预算） |
| R4 | 契约写入的线程安全 | 报告层读到半写状态 | 唯一写者（归因 worker）+ `as_completed` join 屏障后才返回；报告层在 `generate_all_llm` 返回后读取 | 无需回滚 |
| R5 | 全命中运行仍提交归因任务 | 「全模块命中快速返回」路径多一次任务调度 | `needs` 中归因恒真；全命中时归因自身走缓存（`cached=true`），代价为一次缓存读取 | 无需回滚（耗时增量在毫秒级） |
| R6 | 进度日志措辞被误读 | 读者以为归因是独立 LLM 章节 | 沿用注册表标签（`持仓变动复盘归因`），与章节名区分 | 无需回滚 |
| R7 | 包装层恒返回 `from_cache=false` | 依赖该标志的读者读到不准确值 | 缓存命中态由 `session.record_per_module(cached=True)` 记账，包装层不承载 | 如需精确，可让调度层返回三元组承载命中态（登记为可选优化） |
| R8 | `duration_seconds` 口径被误读为「含排队」 | 关键路径判断偏差 | 该值取自调用墙钟（不含 worker 排队）；排队时间由 A3 与日志时间戳判定 | 无需回滚 |
| R9 | 端点峰时波动使 A2 误判 | 误触发回滚 | 样本 ≥3 次、取 p50、同时段可比；A2 阈值留 10% 余量 | 复核后再触发 |
| R10 | 深度档 `brief` 下归因仍执行 | 多一次 LLM 调用 | 与既有语义一致（不受 `depth_gate` 收窄），开关可关 | 如需档位收窄，另立需求 |

## 7. 范围外选项

| 选项 | 结论 | 依据 |
|---|---|---|
| 输出预算 / 表达压缩（14.8k → 8k token，约省 40s） | 不实施 | 以正文篇幅减半 + 结构补写接缝为代价，绝对收益小、维护复杂度高；详见归档 `llm-critical-path-design.md`「评估结论（不采纳）与量化结果」 |
| 缓存 TTL 提升（4h → 12~24h） | 不实施 | 归档同文「缓存 TTL 提升（不采纳）」小节已评估；需另行给出依据 |
| 指纹瘦身 | 不实施 | 归档同文「指纹瘦身（不采纳）」小节已评估 |
| thinking `effort` medium → low | 不实施 | 以推理质量下降换时延 |
| `max_concurrency` 3 → 4 | 不实施 | 收益上限约 4s，见「并发配置维持」 |
| `self_review` 并行化 | 不实施 | 入参依赖基础四模块产出；如需压缩需先改契约形态，属独立课题 |

## 8. 交付项与结项条件

### 8.1 交付清单

- [x] 生产代码四项（见「影响面」）
- [x] 注释同步：`core/data_registry.py` 条目说明、`holding_change_review.py` 模块 docstring 为并行口径
- [x] 测试：T1~T8 全部实现（T7 在 `run_holding_change_review` 层覆盖两条短路；T4/T6 经分发层，T8 读生产源码）
- [x] 注释/文档同步（`data_registry` 条目、模块 docstring、`llm-technical.md`、`technical.md`、`changelog.md`）
- [x] 运行验收 A1~A6（4 次完整报告，2026-10-28 19:45~19:49）

### 8.2 待补测试

| # | 判定对象 | 补测理由 |
|---|---|---|
| T4 | 经分发层二次调用同输入只触发 1 次真实调用 | 既有缓存矩阵用例直接调 `run_holding_change_review`，未覆盖「经 worker 调用」的键一致性 |
| T6 | `api.call_llm` 在归因路径上被调用 | 证明入批后仍走 Provider Chain，而非因透传客户端绕开链路 |
| T8 | `core/data_registry.py` 与模块 docstring 不含「串行/不并行」表述 | 注释与实现口径一致，机检防止漂移 |

### 8.3 结项条件

A1~A6 全部成立（见「实测结果」）→ `rf-944` 移入 `review-findings.md` 已解决表，本文件迁入版本归档。任一失败 → 按上文「劣化保护线」回滚，并把实测数字回写基线章节与「范围外选项」结论后重新评审。
