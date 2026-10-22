# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.7]**（2026-10-23）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.8-dev] - 开发中（未发布）

### Changed

- **`plan.md` 收敛为「最新状态」描述**：去掉各任务里的历史复盘痕迹——观测快照的日期与发布周期标记、逐品种实测明细（哪只品种写错成多少）、调查性叙述（`grep … = 0`）、跨任务完成状态叙述（「已落地」），以及 plan-70 的「动机」段（其内容并入「现状与问题」）。任务统一为「现状与问题 → 动作（/决策/先决门槛）」两段结构，plan-70 另留「当前状态」一句；判据、观测手段与落地设计的可执行内容原样保留。
- **`decision_reflection` 生命周期观测（plan-70）**：按死线重跑 `fold_ledger` + `experiment_stats` + doctor 账本概览——启用 63 次（最近 2026-10-22）、已结算 11 条、`directional_total` 9、`sample_sufficient=False`。撤销两条件均不满足（仍在用 / 已结算 ≥10），转正下限（已结算 ≥10）已过但命中率样本未达可信阈值；且已结算 11 条全部来自确定性 `discipline` 载体，`expert_review`（LLM 建议）尚无一条到期——「LLM 决策闭环」仍未获真实数据验证。判定：维持观察，37 条 pending（10-17~10-22，满 5 个交易日后到期）为下个观察点；同步刷新 technical §6.9 生命周期表该行「当前态」。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.7（2026-10-21 ~ 2026-10-23）
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
