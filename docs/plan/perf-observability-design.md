# 运行观测与性能归因设计方案（perf_history 观测面扩充）

> 关联计划：`plan-123`（观测打点补齐）· `plan-124`（稳健统计与归因）· `plan-125`（上下文维度采集）· `plan-126`（对比/机读输出/门禁）
> 落地载体：`src/python/core/perf.py`（采集）· `scripts/perf-view.py`（归因视图）· `report/` 与 `llm/`（埋点）

---

## 1. 背景与目标

`perf_history.jsonl` 是「运行时台账」——记录每次**真实**报告生成的耗时，用于回答「线上实际多快、哪一步慢」。它与 `scripts/perf-test-report.py`（合成持仓压测，测管线是否退化）分工不同：前者是事实记录，后者是实验室基准。

**目标**：让台账能定位「时间花在哪、为什么花、是否退化」，从而反向指导程序优化。

## 2. 现状缺口（实测，126 条记录）

| 缺口 | 实测证据 | 影响 |
|:-----|:---------|:-----|
| 阶段粒度过粗 | 全量仅 8 个阶段名；`LLM+新闻` 单桶占 full 总时长中位 **91%** | 无法定位到具体 LLM 模块 |
| full 路径 HTML/Excel 埋点缺失 | `HTML 生成`/`Excel 生成` 各仅 6 条（均早期版本）；当前 full 走 `_report_output.py` 两个 helper，无 `perf` 埋点 | 无法判断渲染是否退化 |
| 诊断字段恒空 | `errors` 126/126 为 `[]`；`warnings_count` 126/126 为 0（日志中 503/超时/降级大量存在） | 失败与降级对统计不可见 |
| 上下文维度为零 | 字段仅 version/report_type/holdings_count | 无法按 provider/模型/缓存冷热/重试分组归因 |
| 无离群处理与对比能力 | 单条 6636s 异常把均值抬高 51s，需人工剔除 | 判断依赖人肉 |
| 无阈值门禁 | 仅合成基准有 60s 目标 | 真实运行退化不会被告警 |

## 3. 记录结构（向后兼容扩展）

`phases` 仍是**唯一**参与 `total_seconds` 的阶段集合（保证与历史可比、ETA 预估口径不变）；新增字段为旁路观测面：

```json
{
  "version": "0.13.4-dev", "timestamp": "...", "report_type": "full",
  "holdings_count": 12,
  "phases": {"数据准备": 9.8, "快照对比": 1.7, "历史走势": 0.3,
             "行业资金流向": 2.0, "LLM+新闻": 160.0, "HTML 生成": 12.0, "Excel 生成": 1.8},
  "total_seconds": 187.6,
  "breakdown": {
    "LLM+新闻": {"全球政经局势": 31.2, "智囊团深度复盘": 48.7,
                 "持仓体检报告": 40.1, "穿透深度分析": 12.0, "新闻获取": 22.4}
  },
  "counters": {"warnings": 7, "errors": 2, "degrade:news": 3, "retry": 4, "fallback": 1},
  "errors": ["..."], "warnings_count": 7, "status": "completed"
}
```

**口径约定**（写入 `perf-view` 表头与 `developer-guide`）：

- `breakdown` 是**子项自身耗时**，父阶段内子项可能并行（LLM 与新闻并行、四模块经线程池并发），故**子项之和可大于父阶段 wall time**，不参与 `total_seconds`。
- `counters` 为运行期诊断计数；`warnings_count` 保留（等于 `counters["warnings"]`），旧视图兼容。

## 4. 采集 API（`core/perf.py`）

```python
class PhaseBreakdownRecorder:
    """父阶段绑定的线程安全子项计时器（LLM 线程池可安全并写）。"""
    def record(self, name: str, seconds: float) -> None: ...
    def count(self, key: str, n: int = 1) -> None: ...

class PerfCollector:
    def recorder(self, parent_phase: str) -> PhaseBreakdownRecorder: ...
```

- 线程安全：`threading.Lock` 保护（LLM 四模块在 `ThreadPoolExecutor` 中并发写）。
- 生命周期：recorder 归 collector 所有，`PerfCollector` 仍为**普通局部对象、非模块级单例**（沿用既有设计约束）。
- 诊断计数：`PerfCollector` 在首个 `start()` 时挂一个只计数不输出的 logging handler（logger `invest`），`save()` 时摘除；WARNING → `counters["warnings"]`，ERROR → `counters["errors"]` 且消息（截断）并入 `errors`。这是「`errors`/`warnings_count` 恒空」的根因修复（调用点分散在 `reporter.add_error`/`logger.warning` 多处，集中采集优于逐点改造）。

## 5. 埋点接线

| 位置 | 内容 |
|:-----|:-----|
| `report/_llm_news.py` | 建立 `collector.recorder("LLM+新闻")`；新闻 future 墙钟 → `record("新闻获取")`；recorder 下传 `generate_all_llm` |
| `llm/generators_orchestrator.py` | 四模块各自耗时 → `record(模块名)`（模块名为既有语义名：全球政经局势/智囊团深度复盘/持仓体检报告/穿透深度分析） |
| `report/_report_output.py` | full 路径 HTML/Excel 两个 helper 补 `perf.start/stop`（经 `run_integrity.current_perf()` 取本次 collector，取不到则静默跳过） |

## 6. 视图层（`scripts/perf-view.py`）

- 步骤 1：分组段增「阶段细分」表（父阶段 → 子项平均/最长/次数），让新数据可见。
- 步骤 2：稳健统计与归因——中位/MAD 离群标注（`--exclude-outlier`）、阶段级分位、尾部归因（最慢运行逐阶段 z 分数）、`--by day|week|hour`。
- 步骤 3：按 provider/模型/缓存命中/重试分组对比。
- 步骤 4：`--compare A B`（阶段级 delta，变异系数判显著）、`--json`/`--csv`、`--gate` 阈值退出码（噪声带取同版本多次运行的离散度）。

## 7. 分步与验收

| 步骤 | 计划项 | 交付 | 验收 |
|:-----|:-------|:-----|:-----|
| 1 | `plan-123` | 细分机制 + LLM/新闻子项 + full 埋点补回 + 诊断计数落盘 + 视图最小展示 | 新记录含 `breakdown`/`counters`；造 WARNING/ERROR 的运行计数非零；旧记录读取不报错 |
| 2 | `plan-124` | 离群标注/稳健均值/阶段分位/尾部归因/时间聚合 | 6636s 异常被自动标注；剔除后均值与人工口径一致 |
| 3 | `plan-125` | provider/模型/thinking/fallback/重试等待/缓存命中/tokens/质量/降级分类 | 能回答「换 provider 或关 thinking 省多少」 |
| 4 | `plan-126` | 对比/机读输出/阈值门禁 | `--compare` 指出版本间退化阶段；`--gate` 可入 CI |

**测试策略**：细分机制与诊断计数为纯内存单测（线程安全用并发子项断言）；埋点接线用「调用后 collector 记录到子项」的集成断言（不真调 LLM，沿用 mock 强制）；视图侧为渲染结构断言（分位/离群/对比表逐项校验，不断言会演进的条数）。

## 8. 风险与取舍

- **不改 `total_seconds` 口径**：避免与历史记录、ETA 预估、既有视图断层。
- **不改 `generate_all_llm` 返回契约**（8 元组被指纹/回退/多处消费）：recorder 以**可选参数**注入，None 时行为逐字节不变。
- **诊断计数依赖 logging 采集**：若某模块直接 print 而非 logging，则不入计数——沿用项目「日志统一」约束，不额外改造。
- **等待/重试与 provider 维度同批（步骤 3）**：二者共用 LLM 调用链触点（`core/retry.py` 退避、`llm/pacing.py` 节流门），分两批改同一段链路会重复返工，故合并。

## 9. 设计决策：性能门禁归属（压测脚本，非历史视图）

**决策**：性能门禁由 `perf-test-report.py --gate` 承担（CI `perf-gate` job），`perf-view.py` **不提供门禁**。

**理由**：两者性质不同——

| | `perf-test-report.py` | `perf-view.py` |
|:--|:--|:--|
| 性质 | 性能测试（主动压测） | 运行历史查看（被动统计） |
| 数据 | 自造模拟持仓，当场跑管线 | 读 `perf_history.jsonl` 既有记录 |
| 条件可控 | 是（固定品种数、mock LLM） | 否（取决于最近跑过什么） |
| 适合门禁 | **是**（同条件可比，退化即回归） | **否** |

历史视图不适合门禁的三条具体原因：① **样本不由 CI 决定**——CI 上 `perf_history.jsonl` 要么不存在，要么是开发者本机带上去的脏数据，门禁结果取决于「最近跑过几次报告」而非代码质量；② **不可复现**——同一份代码，跑 10 次与跑 3 次的 P95 不同，门禁时红时绿；③ **测的是环境不是代码**——P95 里混着 LLM 服务端延迟、网络、机器负载，与本次提交无关。

**推论**：`perf-view.py` 的定位是**本地/发布前人工体检**（看最近 N 次真实运行的分布与归因），其 `--json`/`--csv` 供外部工具消费；阈值判定能力归压测脚本。
