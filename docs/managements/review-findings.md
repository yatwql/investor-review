# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.15.8-dev
> **编号源**：`rf-next = 881`（新增问题取此编号，完成后更新为 +1；已用最大 rf-880，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 **4 类人工项**：真实 basic/full 进度观察（3.1c / 3.2 / 3.3 / 3.4）、结果区按钮（4.5）、提交即禁用（5.3）、真实拖拽与 Tab / Enter 抽验（2.5 / 2.6） | 判定标准见 [`../archive/v0.15.x/web-browser-verification/web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)（启动 / 收尾命令 + 复验清单）；复跑 `.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全部通过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定，且不与在办功能争抢同一批文件。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-876** | 财报索引（`report`）与财务指标（`fin_indicator`）都是 **symbol 级键 + 30 天 TTL**：新披露的季报/半年报最长要等 30 天才被取到，报告可能整月沿用上一期数据 | 拆 TTL：索引 `report` 30d→1d（正文 `report_doc` 保持 30d，正文按 doc_id 不可变）；`fin_indicator` 30d→1d（或键含最新报告期，由索引发现新期后失效） |
| **rf-879** | LLM 模块 TTL 统一 4h（`expert_review` / `health_check` / `penetration_deep` / `news_correlation`）：同一份持仓一天跑 2~3 次报告时会重复调用最贵模块。指纹已覆盖持仓/数据变化，4h 只是"内容不变时的强制重算上限" | 待数据决策：内容型模块放到 8~12h（成本约降一半），新闻关联保持 ≤4h。建议先统计一周"指纹未变但 TTL 到期"的模块分布再定值 |
| **rf-880** | `decision_ledger.jsonl` / `signal_ledger.jsonl` 无保留上限（现 26KB / 127KB，按日增长），与 perf（5000 行）/health（2000 行）/dedup anchors（120 天 + 压缩）不一致 | 加按龄保留（决策反思需跨期样本，可 730 天）或行上限，写入复用 `jsonl_store` 的 `max_lines` |

### P3 — 持续监控：文件膨胀登记

> **单一事实源**：行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（主程序 >700 警告 / >1000 红线；`scripts/` >600 / >1000；测试 >900 / >1200；`__init__.py` >200）；口径见 `technical.md` C28。
> **入表规则**：达警告线即登记（登记线 = 警告线），破线豁免当前为 0。

**当前无登记项**（三域均在登记线以下）。

## 已解决问题

### 归档档案
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x 开发期已修复批次
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x 开发期已修复批次
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x 开发期已修复批次
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x 开发期已修复批次
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x 开发期已修复批次
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x 开发期已修复批次
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本记录
