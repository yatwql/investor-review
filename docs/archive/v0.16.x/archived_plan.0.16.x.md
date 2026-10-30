# 计划归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.0 发布，本系列首份）；2026-10-26 v0.16.2 本批原表搬运；2026-10-29 v0.16.8 本批原表搬运；2026-10-30 补录 plan-230/231/232（同上）
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.16.x 开发期完成项（含 v0.16.8）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## 已放弃项

### `plan-93` 历史报告归档无索引导航（放弃）

**原立项内容**：HTML 按日期归档到子目录但不生成索引；TUI 无「最近报告」入口；Web 运行历史不含归档目录。动作拟为生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口。

**结论**：决策不实施，从 `plan.md` 在办清单移除，未产出设计文档与代码改动；重提须给出新理由，按新编号另行立项。

**边界**：该项并入 `plan.md`「归档放弃项边界（禁止重提）」清单。

## `plan-227` LLM 模块 TTL 调值 ✅（结论：维持 4h）

**结论**：维持内容型模块 4h（`news_correlation` ≤4h 不变）。当前无客观依据支持调值。

**依据（实测，非主观判断）**：
- 同日间隔 ≤4h 的运行全部命中缓存（近两日 15/16 次；间隔 0.01~1.9h 均命中，含 6/6 全命中）；
- 唯一一次「4~8h 间隔」样本（10-25 15:09，间隔 5.58h）四个基础模块记 `ttl_expired`——调 8h 只能救这一档；
- 跨夜运行（>12h）无论 4h 还是 12h 都会过期，调值对此无收益。

**复核触发条件**：归因落盘口径已修（聚合计数与逐模块明细分字段），累计出现 ≥10 次「4~8h 间隔」运行且其中 `ttl_expired` 占比 >30% 时，再评估是否提到 8h。

**聚合命令**（`llm.recompute_reasons` 为按原因聚合的计数）：

```bash
.venv/bin/python -c "
import json, pathlib, collections
rows=[json.loads(l) for l in pathlib.Path('data/state/perf_history.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
c=collections.Counter()
for r in rows[-30:]:
    c.update((r.get('llm') or {}).get('recompute_reasons') or {})
print(dict(c))"
```

**验收**：`test_cache_recompute_attribution.py`（归因分类、双路径计数、预检归因不被骨架覆盖、报告边界复位、perf 双字段落盘）。

### 复核记录（2026-10-27，v0.16.4 发布当日）

**触发条件核对**（数据源：`data/state/perf_history.jsonl` 190 轮）：

| 间隔档 | 样本 | 重算 | 其中记 `ttl_expired` |
|---|---|---|---|
| 4–8h | **32**（≥10 ✓） | 32 | **3（9.4%，< 30% ✗）** |
| 8–24h | 35 | 35 | 0 |
| >24h | 20 | 20 | 0 |

→ 复核条件**未满足**（样本量达标，但 `ttl_expired` 占比 9.4% 未达 30% 阈值），维持 4h。

**更关键的一条**：4h 窗口内**理论应命中 95 次、实际命中仅 17 次**，差额 78 次由**输入指纹变化**（持仓 / 行情 / 指标 / 环比差异）驱动，与 TTL 无关。把 TTL 提到 8h 最多只能救 4–8h 档里的那 3 次（占全量 1.6%）。

**结论**：TTL 参数不是这条链路的杠杆；真正的杠杆是「指纹稳定性」（需产品接受「分析文本当天不随行情刷新」的取舍）或「换更快线路/模型」。若将来立项「叙事与数值分离」或「换线路」，随那次评估一并重估本项。

**复核命令**：

```bash
.venv/bin/python - <<'PY'
import json, pathlib
from datetime import datetime
rows=[json.loads(l) for l in pathlib.Path("data/state/perf_history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ev=[]
for r in rows:
    try: ts=datetime.fromisoformat(r["timestamp"])
    except Exception: continue
    llm=r.get("llm") or {}
    mod=(llm.get("modules") or {}).get("expert_review") or {}
    ev.append((ts, bool(mod.get("cached")), (llm.get("module_recompute_reasons") or {}).get("expert_review")))
ev.sort()
gaps=[((b[0]-a[0]).total_seconds()/3600, b[1], b[2]) for a,b in zip(ev,ev[1:])]
for label,lo,hi in (("4-8h",4,8),("8-24h",8,24),(">24h",24,1e9)):
    seg=[g for g in gaps if lo<g[0]<=hi]
    print(label, "n=", len(seg), "命中=", sum(1 for g in seg if g[1]), "ttl_expired=", sum(1 for g in seg if g[2]=="ttl_expired"))
PY
```

## `plan-229` LLM 关键路径时延治理（表达预算）✅（结论：不采纳）

**结论**：不采纳，未改生产代码。离线评测显示「分节表达预算」可省约 30% 时延，但需以正文篇幅减半 + 结构补写接缝为代价；绝对收益小（每次约 19.5 秒、每月约 ¥2.8），不足以承担交付完整性与维护复杂度。

**量化结果**（冻结 12 只持仓样本；`deepseek-v4-flash`；thinking 开；含补写）：

| 预算档 | 次数 | p50 | 输出 tokens | 实际字数 | 超预算 | 建议表行数 / 覆盖 | 补写触发 |
|---|---|---|---|---|---|---|---|
| 基线 | 40 | 64.5s | 12,546 | ≈1.05 万 | — | — | — |
| 3200 字 | 2 | 33.0s（−49%） | 4,636 | 5,136 | +60% | 7.0 / 7.5 | 2/2 |
| 4000 字 | 5 | 45.0s（−30%） | 7,416 | 5,244 | +31% | 6.8 / 8.0 | 5/5 |
| 4800 字 | 2 | 57.1s（−11%） | 8,116 | 5,536 | +15% | 6.5 / 6.5 | 2/2 |

**结构发现**：纯提示词约束下 8/8 次丢失「操作建议」表（含两轮文案加固）；补写接缝可 9/9 补齐（+2.0~6.5 秒、300~1,200 tokens）。

**同期评估的两个替代杠杆**：

- **缓存 TTL 4h→8h**：理论命中 51%→63%，但实际命中仅 8%（16/190）——miss 主因是输入指纹变化而非 TTL 到期，真实收益 ≈0~4% → 不采纳；
- **指纹瘦身**（行情数值移出缓存键）：命中率可 8%→36%（陈旧中位 47 分/最大 3.7 小时）、同日按日模式可 61%（陈旧中位 6.3 小时）；折算每月省约 18 分钟、约 ¥0.9，且违反「指纹与缓存键唯一事实来源」约束 → 不采纳。

**复核触发条件**：白天高频重跑成为常态（≥5 次/天）；或换更快线路后仍需提速；或「叙事与数值分离」改造启动；或模型开始稳定服从字数预算（实际字数进入 ±10%）。

**保留资产**：离线评测器 `scripts/eval-llm-budget.py` + `scripts/_eval_llm_budget/`（22 例单测），可复用于任何提示词/生成参数变更的 A/B 度量。

**设计文档**：[`llm-expression-budget/llm-critical-path-design.md`](llm-expression-budget/llm-critical-path-design.md)（含 §13 评估结论与全部量化数据）。

## `plan-230` 基金经理抓取时间预算收紧 ✅

**完成（2026-10-27，v0.16.5；2026-10-30 补录）**：主页请求 15s→6s、档案页回退 8s→4s，主页网络级超时后跳过档案页回退，单代码最坏耗时收敛到 ≤10s；新增 `_request_fund_html_status` 返回超时标记。按 v0.16.5 changelog 段补录。

## `plan-231` 历史数据重叠判据改为「数值变化」 ✅

**完成（2026-10-27，v0.16.5；2026-10-30 补录）**：重叠日期上价格变化超 0.01% 才算除权修正，数值一致按日合并；末位舍入差（1e-6 级）不误报。按 v0.16.5 changelog 段补录。

## `plan-232` 归还「恒真参数」技术债 ✅

**完成（2026-10-28，v0.16.6；2026-10-30 补录）**：`enable_data_quality` 布尔参数从 4 层链路彻底删除，模板 `data_quality_enabled` 恒真条件一并移除。按 v0.16.6 changelog 段补录。
## `plan-234` 行业资金流向换通道（东财 push2 → 同花顺备用）✅

**实现**：主通道东财 `push2` 在本机出口被配额型限流（TLS 层秒断、偶发短窗口放行），已改为「东财 push2 → 同花顺行业资金流」双通道按序取数；备用通道金额由亿元换算为元、净占比由净额/成交额派生，两通道共用同一结构契约，下游无感。失败负缓存按通道分别落盘（主通道限流不锚死备用通道）。
**验收**：`probe.py sector-flow` 每通道 4 次实测主 0/4、备 4/4；「主失败→备用成功」「两通道皆失败」回归各 1 例（含单位换算与派生口径断言）。

## `plan-235` 「无回退基准」须显式区分于「陈旧回退」✅

**实现**：取数层新增降级三态 `sector_flow_degraded_state()`（`""` / `stale` / `no_baseline`）；失败且无历史载荷时经 `mark_data_unavailable(freshness="no_baseline")` 进事件 detail，报告文案与 `health_check` 数据质量块各自单独成行（「无回退基准…区块留空」vs「陈旧回退…用上次成功数据」），互不吞并；空区块仍不进 LLM 提示词。
**验收**：降级三态回归 3 例（无基准 / 陈旧 / 成功复位）+ 质量块两态区分断言 2 例，全部通过。

## `plan-236` 新浪新闻分类抓取加单请求超时上限 ✅

**实现**：单请求超时改为连接 3s / 读取 6s 分档（原单一 15s 整段预算），新浪整源加 20s 预算——每请求超时按剩余预算收紧，超预算停止翻页并保留已取条目（其他新闻源不受影响）；`fetch_news()` 新增 `timeout` 覆盖参数。
**验收**：预算耗尽收尾 / 预算内正常流程 / 超时按剩余收紧 / 默认分档 / 调用方覆盖，回归 5 例通过。

## `plan-237` 缓存清理器按同前缀统一 TTL，裁掉异构 TTL 键（回退基准 / 负缓存）✅

**实现**：清理器改为「精确键 → 独立 TTL」优先于前缀默认值；`sector_flow_last_good`（3 天）与 `sector_flow_negative`（30 分钟）在缓存域注册表 `exact_key_ttls` 单源声明，取数侧 TTL 从同一处读取。
**验收**：两条异构键在各自窗口内不被 900s 前缀默认值裁掉、超自身窗口才删、常规列表载荷仍按 15 分钟裁（回归 6 例）。

