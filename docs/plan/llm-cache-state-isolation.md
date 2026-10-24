# 报告级 LLM 缓存状态隔离 — 研究（进行中）

> **状态**：在办（`plan-212`）；先审计指纹变化来源，再做状态边界
> **关联**：`plan-210`（耗时优化）、`technical.md`（原子写入/会话缓存/数据契约约束）、`llm/module_fingerprint.py`

---

## 1. 现象

同一非交易日、同一持仓、新闻缓存命中（900s 内）连续运行两次报告，LLM 模块缓存仍全部 miss：

- expert / health / global / holding_change / penetration / self_review 的 cache key 均变化
- 总市值、总盈亏、当日盈亏相同
- 第二次实际单模块输入 token 与第一次接近，但 key 不同
- 新闻缓存命中，排除新闻 TTL

**结论**：TTL 未到期不是原因；key 是内容寻址的，报告级状态或指纹输入发生了变化。

## 2. 缓存键实测证据（2026-10-24 20:41 / 20:44 两次报告）

模块缓存键由「基础指纹 + 各后缀」拼接，逐段比对可见：

| 模块 | 变化段 | 结论 |
|:--|:--|:--|
| health_check | 第 3 段（pipeline 块）`3a5ead75787a` → `eeddd418edb8` | 数据质量/降级块变了 —— 上一轮告警进入本轮提示词 |
| expert_review | 基础段与 pipeline 段均变 | 同上，且 `holding_change_block` 随上一轮写入的快照变化 |
| global_macro / penetration_deep / holding_change | 仅基础段变，生成参数段不变 | 配置未变，是数据输入变化 |
| self_review | 内容寻址 | 上游产出变则必然变，属设计内 |

同时 `perf_history` 第二份报告的 `input_tokens` 是累计值（expert 11677 = 5805 + 5872），
说明用量侧未按报告取 delta。

## 3. 待审计的状态源

| 状态 | 生命周期 | 是否应进指纹 | 当前问题 |
|:--|:--|:--|:--|
| `DegradationTracker` 事件日志 | 会话级 | 只应进“本次报告”的数据质量块 | `get_log()` 未按报告清空，上一轮告警会进入下一轮 health/expert 提示词 |
| `llm/session.py` 会话用量 | 会话级 | 不进指纹 | perf 读取累计值，第二份报告 token/call_count 看起来翻倍 |
| `self_review` 全局载体 | 会话级 | 网页/Excel 消费，不进指纹 | 报告开始未 reset，上一轮自检块可能残留 |
| `decision_ledger` / `signal_ledger` 回灌块 | 跨报告持久 | 进 expert 指纹（设计如此） | 有新决策/信号时 expert 必然 miss；需确认这是否符合“每次重算”预期 |
| `history_data` 风险摘要 / 指数 / 竞争语境 | 报告数据 | 进基础指纹 | 非交易日应稳定；需 fingerprint audit 确认是否实际变化 |
| `generation_params_suffix` | 配置 | 进指纹 | 配置默认值/思考参数变更会整体换键，需确认两次运行配置未变 |

## 4. 设计候选

### 4.1 报告运行边界（P0，已实施）

在报告入口建立显式 run scope：

- `DegradationTracker.begin_report()`：只清空本次事件日志，保留跨会话 `last_success` 与失败计数（或按 run_start 过滤 `get_log`）
- `reset_self_review()`：报告开始/结束清空自检载体
- `LLM session usage`：报告开始记录 baseline，`_record_llm_context` 按 delta 写 perf；不重置全局累计（TUI 会话统计仍需保留）
- 把上述边界放在 full/both 共用入口，异常路径 `finally` 清理

### 4.2 指纹审计（P1，已实施）

增加只读诊断（不改变缓存）：

- 对每个模块记录**组件级哈希**（totals、holdings、indices、competitive、pipeline blocks、 ledger blocks、generation params），debug 日志或 `probe-llm-fingerprint.py`
- 连续两次运行输出“哪些组件变化”，避免再凭猜测改指纹
- 只对**语义无关**的组件做归一化；真实数据变化不得剔除

### 4.3 缓存策略

- 不延长新闻 TTL，不缓存跨日/跨行情
- 不为了命中而移除 `total_today_profit`、指数、数据质量等真实字段
- 若 ledger 每次增长导致 expert 必 miss，评估“基础指纹 + 增量上下文”分层，或接受重算并单独计量

## 5. 已落地

- `report/_run_scope.py::start_report_run()`：报告入口调用，清本轮降级事件与自检载体，返回用量基线
- `DegradationTracker.begin_report()`：只清事件日志，保留失败计数与上次成功时间
- `_generation_shared._usage_delta()`：perf 按基线写 delta，TUI 会话累计不受影响
- `module_fingerprint.fingerprint_components()` / `diff_fingerprint_components()`：组件级哈希与变化定位，DEBUG 下自动记录「相对上次报告的组件变化」
- 回归：`test_run_scope.py`、`test_fingerprint_components.py`

**实测 diff（21:25 / 21:27 两次报告，DEBUG 组件审计）**：变化的组件只有
`data_quality`、`history_risk`、`holding_change_block`、`pipeline_blocks`；
`totals` / `holdings` / `penetration` / `categories` / `indices` / `competitive_context` /
`metrics` / 各附录块 / `ledger_blocks` / `generation_params` 全部稳定。

由此定位并修复一个事实性缺陷：`mark_data_used` 的成功事件沿用默认 `failure_type="unreachable"`，
数据质量块又按 `failure_type` 计数 → 正常取数被写成「连接失败 N 次」。缓存命中数不同的两次报告
成功事件数不同，质量文本因此不同（既是错误陈述，也是缓存抖动源）。现成功事件写 `failure_type="ok"`，
质量块只统计 `success=False` 的事件。

**第二次实测（21:40 / 21:48）**：变化仅 `history_risk`、`holding_change_block`、`pipeline_blocks`。

- `history_risk`：两次风险信号值完全相同（-15.75 / 0.1751 / -10.07 / ok），是审计组件哈希了整个
  `history_data`（含 bars 载荷）——已改为只哈希风险信号子集，与正式指纹同口径。
- `holding_change_block`：`window_lines` 里带了「N 份快照按日去重」，N 是**原始快照文件数**，
  每跑一次报告 +1；窗口行只保留「按日去重 + 滚动保留」。
- `pipeline_blocks`：审计组件哈希的是契约 dict（含 `snapshot_count` 等展示字段），而生产指纹
  哈希的是渲染文本。已改为与生产同口径（环比块 + 降级块的渲染文本）。

实测确认：同一份快照数据下多写一份同日快照，`snapshot_diff` 只有 `snapshot_count` 变化，
净值/份额/总额/HHI/新增移除全部稳定；环比基线本就按交易日跳过同日快照（`load_comparison_baseline`），
故 `baseline_generated_at` 也不随同日重跑漂移。

## 6. 验收

- 同一非交易日、同持仓/指数/新闻，连续两次报告：基础模块（global/health/penetration/holding）第二次命中应用缓存
- `perf_history` 的 LLM token/call_count 为**单次报告**值，不累加
- 第二轮不包含第一轮 degradation/self-review 残留
- 指纹审计能指出任何仍导致 miss 的真实输入变化
- 新用例：同进程连续两次报告、稳定数据下缓存命中；状态变化时失效
