# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.1]**（2026-11-05）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.2-dev] - 开发中（未发布）

### 修复
- **事件窗行情窗口按最早事件日自适应（`rf-1042`）**：索引扩面后能匹配到更多新闻，但行情取数窗口写死 365 天，事件日更早的新闻整条按「映射交易日不在行情轴」降级（实测一轮 23 条降级里 19 条属此类）。新增 `history_days_for()`：按最早事件日回推回看天数 + 后窗余量 + 30 天缓冲并夹在 365~1095 天内，默认股票与基准取数器同用该窗口；短窗新闻仍按 365 天，不额外拉数。另一半成因同修：事件日**晚于行情轴末日**（当日 K 线尚未落地）时原按「映射交易日不在行情轴」整条降级，改为按行情轴末日对齐并在视图计数标注（`anchor_shifted`/`align_note`），仅剩轴首缺日与关键位缺失仍降级。实测一轮：降级 23→4、可出行 36→50（当时触 50 行上限 capped 4，上限随后提到 80 后 capped 归零）。补 6 例单测（窗口基线/放大/夹上限、默认取数器请求值、末日对齐正反向）。
- **删掉旧配置键兼容层（`config/_legacy_keys.py`）**：`RENAMED` 早已为空、`REMOVED` 仅剩 `llm_usage` 一条，维护它只为给「旧键→新键/已删除」出一句处置建议。既然不保留跨版本配置兼容，整表与两处派生告警一并删除：`features.json` 未登记开关与 `config.json` 未登记章节键各自归并成一条告警（带条数与键名），手册「已删除 / 已改名的配置键」节改为「未登记的配置键」并删掉对照表。净删 1 个模块 + 1 份单测。

### 变更
- **「我的建议历史表现」补结论列与涨跌色**：原来只给命中率与均值超额两组数字，读者要自己合成判断。新增 `performance_verdict()` 按「命中率 × 均值超额」两轴出一句人话（方向有效且跑赢基准 / 方向命中但跑输基准 / 方向偏错但选品仍跑赢基准 / 方向与超额双弱），缺任一轴时只说可得轴（如「仅有超额：跑输基准」），方向性样本 < 20 时结论加「（样本不足，仅参考）」；HTML 单列展示并按超额涨跌上色，Excel 行动页签列宽 5→6 让超额（结论）列完整可见。补 4 例单测（四象限 / 缺轴降级 / 样本不足后缀 / 双端渲染）。
- **事件表行数上限 50 → 80**：事件窗索引扩面后单轮可命中 60+ 条事件行（行业级关联占大头），50 行上限会把有效行计入 `capped` 截断（实测一轮 capped 4 条、可出行止于 50）；提高到 80 留出余量又不失控，超限仍按原口径计入 `skipped.capped`，视图合计行不变。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.1（2026-11-04 ~ 2026-11-05）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
