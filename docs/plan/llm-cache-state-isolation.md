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

## 2. 待审计的状态源

| 状态 | 生命周期 | 是否应进指纹 | 当前问题 |
|:--|:--|:--|:--|
| `DegradationTracker` 事件日志 | 会话级 | 只应进“本次报告”的数据质量块 | `get_log()` 未按报告清空，上一轮告警会进入下一轮 health/expert 提示词 |
| `llm/session.py` 会话用量 | 会话级 | 不进指纹 | perf 读取累计值，第二份报告 token/call_count 看起来翻倍 |
| `self_review` 全局载体 | 会话级 | 网页/Excel 消费，不进指纹 | 报告开始未 reset，上一轮自检块可能残留 |
| `decision_ledger` / `signal_ledger` 回灌块 | 跨报告持久 | 进 expert 指纹（设计如此） | 有新决策/信号时 expert 必然 miss；需确认这是否符合“每次重算”预期 |
| `history_data` 风险摘要 / 指数 / 竞争语境 | 报告数据 | 进基础指纹 | 非交易日应稳定；需 fingerprint audit 确认是否实际变化 |
| `generation_params_suffix` | 配置 | 进指纹 | 配置默认值/思考参数变更会整体换键，需确认两次运行配置未变 |

## 3. 设计候选

### 3.1 报告运行边界（P0）

在报告入口建立显式 run scope：

- `DegradationTracker.begin_report()`：只清空本次事件日志，保留跨会话 `last_success` 与失败计数（或按 run_start 过滤 `get_log`）
- `reset_self_review()`：报告开始/结束清空自检载体
- `LLM session usage`：报告开始记录 baseline，`_record_llm_context` 按 delta 写 perf；不重置全局累计（TUI 会话统计仍需保留）
- 把上述边界放在 full/both 共用入口，异常路径 `finally` 清理

### 3.2 指纹审计（P1）

增加只读诊断（不改变缓存）：

- 对每个模块记录**组件级哈希**（totals、holdings、indices、competitive、pipeline blocks、 ledger blocks、generation params），debug 日志或 `probe-llm-fingerprint.py`
- 连续两次运行输出“哪些组件变化”，避免再凭猜测改指纹
- 只对**语义无关**的组件做归一化；真实数据变化不得剔除

### 3.3 缓存策略

- 不延长新闻 TTL，不缓存跨日/跨行情
- 不为了命中而移除 `total_today_profit`、指数、数据质量等真实字段
- 若 ledger 每次增长导致 expert 必 miss，评估“基础指纹 + 增量上下文”分层，或接受重算并单独计量

## 4. 验收

- 同一非交易日、同持仓/指数/新闻，连续两次报告：基础模块（global/health/penetration/holding）第二次命中应用缓存
- `perf_history` 的 LLM token/call_count 为**单次报告**值，不累加
- 第二轮不包含第一轮 degradation/self-review 残留
- 指纹审计能指出任何仍导致 miss 的真实输入变化
- 新用例：同进程连续两次报告、稳定数据下缓存命中；状态变化时失效
