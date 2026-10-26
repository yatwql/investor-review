# 计划归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.0 发布，本系列首份）；2026-10-26 v0.16.2 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.16.x 开发期完成项（含 v0.16.2）
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
