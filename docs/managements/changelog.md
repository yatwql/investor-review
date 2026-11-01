# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.15]**（2026-11-01）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.16.16-dev] - 开发中（未发布）

### 变更

- **投资决策质量讨论稿定稿（plan-242）**：成稿 `docs/plan/investment-decision-quality.md`——归因结论（建议方向胜率≈随机、组合略弱于基准、纪律建议方向不稳）、7 条结构性事实（无执行回执、结算依赖跑报告频率、3/5 信号零区分度、估值信号丢失口径、纪律规则结构偏空、提示语强制方向且无可信度、无硬性风险约束）、6 项优先级建议与 7 项待验证清单。不实施任何代码/配置/提示语改动。
- **实施任务立项（plan-243）**：`plan.md` 新增 `plan-243` 决策依据章与 LLM 章职责切分（实施），承接 plan-242 讨论稿「章节归属结论」与设计稿 [`investment-decision-basis-design.md`](../plan/investment-decision-basis-design.md) 的 R0~R7 迭代计划；前置为讨论稿 V1/V3 回测；plan-242 保持仅探讨定位，`plan-next` 更新为 244。纯文档变更，无代码/配置/提示语改动。
- **决策质量首批回测（plan-243 前置）**：新增 `scripts/eval-decision-quality.py`（决策视界命中率 / 因子单因子 IC / 估值两口径区分度；判据预注册：视界 5/20/60 交易日、样本门槛 100、|IC| 拒绝线 0.05、三分位单调）+ 单元测试；结论回写讨论稿 §8.1/§8.2——V1/V2 样本不足仅记录不裁决，V3 5 日视界两口径（n=117）均判「叙述性维度」；plan-243 实施前置 V1/V3 完成。
- **迭代设计按首批回测修订（plan-243）**：设计稿 `investment-decision-basis-design.md` 接入回测结论——§2.1 `discrimination` 升为三态契约（未回测 / 样本不足 / 已回测通过·未通过）并更新信号与可信度示例，R0 补 V1 复跑触发与固定/动态视界对拍口径，R2 补回测结论登记机制（模块常量、不新增配置键）与首版渲染态，§5 红线与 §6 风险表同步；`plan.md` plan-243 条目同步（前置改为 V1~V3 同批完成 + 新增「回测接入」行）。
- **plan-243 设计 80 轮复盘**：设计稿新增 §7 复盘记录（33 轮发现 → 18 项整改：confidence 四枚举规则重写〔有效信号定义/short-circuit 仲裁/首版不产 high/unknown→暂不可判〕、配置与文件实名（`rebalance.threshold`、`discipline.*`、`analysis/trade_discipline.py`、`action_section.html`/`action_sheet.py`）、§3 冗余行合并与 `enable_action` 容器联动、R1 Excel 无折叠概念与验收重编号、门禁补十守护/edge/浮点/LLM mock/移动档核验、术语统一「信号可信度」）；plan-243 条目门禁行同步。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.15（2026-10-25 ~ 2026-11-01）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
