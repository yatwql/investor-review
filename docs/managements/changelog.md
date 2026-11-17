# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.3]**（2026-11-17）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.4-dev] - 开发中（未发布）


（本次发布内容见下方归档索引）
- **新闻去重比较成本**：`_dedup_by_title` 改为「两层候选索引给候选超集 → 逐对判定」，不再全量扫已保留项（`plan-262`）；判定结果逐条不变（保留集合 SHA 对拍一致），实测比较对 −45%、耗时 2.8×；唯一可见差异为锚点语料不再收录实体零重叠对。
- **实验项裁决自动汇编**：新增 `core/experiment_verdicts.py`（项清单由注册表派生，四态：可转正/继续观察/撤销候选/无读数），`doctor` 新增「实验项裁决」行与「已达判据 → 请按计划裁决」提醒行；不改开关不摘 `experimental`（`plan-260`）。
- **零直测模块补测（batch 1）**：`config/_json_patch.py`（含注释 JSON 编辑引擎）与 `analysis/_fee_estimation.py` 首次补齐直测（`test_json_patch.py` 34 条 + `test_json_patch_edge.py` 10 条 + `test_fee_estimation.py` 18 条）；补测过程中修掉三个写回缺陷（`rf-1159`/`rf-1160`/`rf-1161`），`plan-261` 余下模块（`_news_dedup_tables` / `metrics_risk` / `_feature_registry`）待下一批。

- **本轮降级清单汇总出口**：新增 `core/degradation.report_degradation_summary()`（按「源 + 失败类型」去重计数本轮降级，同时给出项数与次数）；报告「数据状态」块尾与 CLI 产物清单尾部同源输出一行，无降级时该行不出现（产物逐字节不变，`plan-263`）。

- **缓存命中率：同事实单键**：`fetch_latest_indicator` 先复用多期缓存（`fin_indicator_hist_{code}` 头部即最新一期），不再让同一 code 走两条键各回源一次（`plan-264`）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.3（2026-11-12 ~ 2026-11-17）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
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
