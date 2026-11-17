# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.3]**（2026-11-17）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.4-dev] - 开发中（未发布）

### 变更

- **渲染前置装配入参按来源域分组**：`_prepare_render_context` 的 30 个关键字入参收为 `_VisibilityInputs` / `_DataSourceInputs` 两组 dataclass 加 `details`，签名降至 3，`_build_data_source_bundle` 同收为单组入参；配 `test_html_render_context.py` 11 条阶段契约用例（`rf-1157`、`rf-1156`）。
- **降级可观测**：6 处按设计降级但无日志痕迹的 `except` 补 `logger.debug(exc_info=True)`，降级语义与返回值不变（`rf-1155`）。
- **新闻去重比较成本**：`_dedup_by_title` 由两层候选索引给出候选超集（实体 bigram / 标题窗口），两层未命中的对不进入比较；判定结果逐条一致（保留集合 SHA 对拍相同），实测比较对 −45%、耗时 2.8×（`plan-262`）。
- **实验项转正判据自动裁决**：新增 `core/experiment_verdicts.py`（项清单由注册表派生，四态结论：可转正 / 继续观察 / 撤销候选 / 无读数），`doctor` 新增「实验项裁决」行与「已达判据 → 请按计划裁决」提醒；不改开关、不摘 `experimental`（`plan-260`）。
- **零直测模块补测**：`config/_json_patch`、`analysis/_fee_estimation`、`analysis/metrics_risk`、`config/_feature_registry`、`providers/_news_dedup_tables` 补齐直测（共 103 条）；补测期间修掉三个写回缺陷——区块括号平衡未跳过字符串/注释（`rf-1159`）、不可解析字符串切片让 patch 抛异常（`rf-1160`）、单行对象删除吞整行与 CRLF 文件混行尾（`rf-1161`）（`plan-261`）。
- **本轮降级清单汇总出口**：新增 `core/degradation.report_degradation_summary()`（按「源 + 失败类型」去重计数，同时给出项数与次数），报告「数据状态」块尾与 CLI 产物清单尾部同源输出一行；无降级时不出该行，产物逐字节不变（`plan-263`）。
- **缓存同事实单键**：`fetch_latest_indicator` 先复用多期缓存（`fin_indicator_hist_{code}` 头部即最新一期），同一 code 每轮少一次回源（`plan-264`）。
- **守护命中台账与统计**：`checklib.report()` 每次运行追加 `logs/guard-hits.jsonl`（`check-doc-drift` 另给子项粒度），新增 `probe-guard-hits.py` 输出「运行次数 / 命中次数 / 处置（保留 / 建议降频 / 样本不足）」表，不改守护启用状态与 CI 阻塞语义；台账超 4MB 截断为最近 5000 行，防长期膨胀（`plan-265`、`rf-1162`）。
- **账本级原语单源**：新增 `core/ledger_common.py`（`feature_active` 开关收敛判定 / `now_iso` 秒级时间戳），两个账本的同名函数改为薄封装，导入面与既有 patch 点不变（`rf-1163`）。
- **台账收口**：`plan-252`（评估政策单源 + 不动作类命中评估）与 `plan-253`（LLM 复盘结论结构化契约，补证循环归 `plan-255` 裁决）迁入已完成待归档。
- **文档触点**：`DESIGN.md` 登记「降级汇总行」口径（位置 / 句式 / 无降级不出行），`reports-instruction.md` 与 `how-to-use-cli-mode.md` 同步该行，`technical.md` 补渲染前置装配与账本原语模块行。

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
