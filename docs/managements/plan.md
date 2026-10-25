# 投资复盘助手 — 实现计划
> 文档版本：0.15.10-dev
> **编号源**：`plan-next = 229`（新增计划项取此编号，完成后更新为 +1；已用最大 plan-228，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 概述

本文档只保留**在办任务的最新状态**：已完成项随发布迁入版本归档，此处不留实现过程记录。命名与实现纪律见 `CLAUDE.md` 与 `developer-guide.md`（单一事实位，本表不重复）。

**当前迭代**：在办 5 项——P1 1 项观察期挂账（**plan-227** 等数据定值）、P2 2 项（**plan-92/93**）、P3 1 项（**plan-70**）、P4 1 项（**plan-55**）。

---

## 当前迭代待办

> **P0** = 必须完成才能发布 · **P1** = 当前待办 · **P2** = 下一阶段就绪 · **P3** = 预期实施，有空时安排 · **P4** = 实验功能（缺省关闭，需显式启用）；编号不表达优先级，分档不改号。

> **归档放弃项边界（禁止重提）**：Brinson 业绩归因、MC 蒙特卡洛情景模拟、Euler 精确风险贡献、申万行业分类迁移、全量行业指数 K 线、仓位硬建议、全市场基金筛选等已放弃项禁止立项（放弃理由与清单见各版归档）。

### P1 — 当前待办（立即执行）

入选标准：立即可执行且价值/风险最高——数据完整性、费用风险、核心量化缺口。

当前无 P1 立项任务。

#### `plan-227` LLM 模块 TTL 调值决策（观察期）

**状态**：观测件已完工，**等真实数据定值**；结论产出前不归档（标题不带完成标记，`prepare` 不会搬走）。

**观测件（已落地）**：缓存未命中记录原因——`forced`（重新生成/缓存关闭）/ `fingerprint_changed`（内容变了）/ `ttl_expired`（内容没变、纯到点）/ `cache_miss`（无上轮可比对）。两条路径都计数（预检四基础模块 + 骨架 `self_review`/`holding_change`），观测汇聚器在 LLM 阶段**之前**绑定（否则重启首跑整体丢样本）。聚合进 perf 的 `llm.recompute_reasons` 与 `cache_hits`/`cache_misses`。

**判据**：跑满约一周真实报告（≥10 次，覆盖同日连跑与跨天两种节奏）后看 `ttl_expired` 占比——占比高 ⇒ 内容型模块 4h 放到 8~12h（`news_correlation` 维持 ≤4h）；占比低 ⇒ 维持现值，本条转为「观测支持维持」结论后归档。

**聚合命令**：

```bash
.venv/bin/python -c "
import json, pathlib, collections
rows=[json.loads(l) for l in pathlib.Path('data/state/perf_history.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
c=collections.Counter()
for r in rows[-30:]:
    for k in ((r.get('llm') or {}).get('recompute_reasons') or {}): c[k]+=1
print(dict(c))"
```

**验收**：`test_cache_recompute_attribution.py`（26 例：三分归因、双路径计数、绑定时机源码断言、报告边界复位、perf 落盘）。

### P2 — 下一阶段就绪（满足条件即开工）

入选标准：价值明确、成本可控，条件满足即开工。

#### `plan-92` Excel 纯数字呈现，缺可视化辅助

**现状**：19 页签为静态数字与文字，收益率高低、集中度偏离需逐格读数。
**动作**：高价值数值列加色阶/数据条、趋势列加迷你折线（openpyxl 原生）；先试点持仓明细 / 量化指标 / 集中度 2~3 个页签，认可后再扩。

#### `plan-93` 历史报告归档无索引导航

**现状**：HTML 按日期归档到子目录但不生成索引；TUI 无「最近报告」入口；Web 运行历史不含归档目录。
**动作**：生成 / 刷新 `output_dir/index.html`（按日期列出 Excel/HTML 产物与打开链接），TUI 加「打开输出目录 / 最近报告」入口；只列路径信息，匿名化口径与报告一致。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需等待时机或数据积累。

#### `plan-70` 决策跨期反思闭环（decision_reflection）验证死线

**状态**：观察中，样本未达判据阈值（以 `doctor` 账本概览为准）。
**判据**：启用停增或已结算 <10 条且无达标趋势 → 撤销该实验功能（含 `decision_llm_capture`、行动章复盘块与对应需求条目）；已结算 ≥10 条按 `doctor` 账本概览评估转正，`directional_total` 达 40+ 再评估。
**设计**：[`decision-reflection-design.md`](../plan/decision-reflection-design.md)（转正后按四迭代执行）；与持仓变动复盘构成「意图 vs 成交」对账（只读，不互写）。
**单一事实位**：[technical §6.9 实验项生命周期表](technical.md#69-实验项生命周期表)「决策跨期反思闭环」行。

### P4 — 实验候选（先决门槛未过，暂缓）

入选标准：接入前有硬性先决门槛，门槛未过不排期。

#### `plan-55` 新闻关联判定接入 Jev（对照评测先决）

**状态**：待评测——三方对照评测脚本未建立；该模块属窄判断（批量、选项有限、需校准概率），是类型化判定接口的适用场景。
**先决门槛**：按 [`jev-news-judgment-evaluation.md`](../plan/jev-news-judgment-evaluation.md) 跑三方对照（关键词确定性 / 现网生成模型 / Jev），主指标与预注册阈值见该文档 §2 / §7；未达阈值则归档为已评估未采纳。
**实施设计**：[`jev-news-judgment-design.md`](../plan/jev-news-judgment-design.md)。
**约束与红线**：① 不作为用户可选对话模型（不生成文本）；② 不做「生成 + 判定」双供应商级联；③ 语料冻结产物落 `docs/tmp/`，仅脱敏样例可入库；④ 类型化通道故障不得拖垮生成链（熔断实例分离）；⑤ 新增配置键按开关注册表纪律登记，默认值保持 `chat`。


## 归档

- [`archived_plan.0.15.x.md`](../archive/v0.15.x/archived_plan.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_plan.0.14.x.md`](../archive/v0.14.x/archived_plan.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_plan.0.13.x.md`](../archive/v0.13.x/archived_plan.0.13.x.md) — v0.13.x 已完成项
- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md) — v0.12.x 已完成项
- [`archived_plan.0.11.x.md`](../archive/v0.11.x/archived_plan.0.11.x.md) — v0.11.x 已完成项
- [`archived_plan.0.10.x.md`](../archive/v0.10.x/archived_plan.0.10.x.md) — v0.10.x 已完成项
- [`archived_plan.0.9.x.md`](../archive/v0.9.x/archived_plan.0.9.x.md) — v0.9.x 已完成项
- [`archived_plan.0.8.x.md`](../archive/v0.8.x/archived_plan.0.8.x.md) — v0.8.0 ~ v0.8.10
- [`archived_plan.0.7.x.md`](../archive/v0.7.x/archived_plan.0.7.x.md) — v0.7.x 已完成项
- [`archived_plan.0.6.x.md`](../archive/v0.6.x/archived_plan.0.6.x.md) — v0.6.x 已完成项
- [`archived_plan.0.5.x.md`](../archive/v0.5.x/archived_plan.0.5.x.md) — v0.5.x 已完成项
- [`archived_plan.0.4.x.md`](../archive/v0.4.x/archived_plan.0.4.x.md) — v0.4.x 已完成项
- [`archived_plan.0.3.x.md`](../archive/v0.3.x/archived_plan.0.3.x.md) — v0.3.x 已完成项
- [`archived_plan.0.2.x.md`](../archive/v0.2.x/archived_plan.0.2.x.md) — v0.2.x 已完成项
- [`archived_plan.0.1.x.md`](../archive/v0.1.x/archived_plan.0.1.x.md) — 早期版本已完成项
