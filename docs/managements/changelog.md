# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.3]**（2026-11-06）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.4-dev] - 开发中（未发布）

### 修复

- **新闻关联批量解析失败不再冒充成功**（rf-1055）：响应整体不可解析时解析器返回 `None`，批量骨架按「本批
  失败」收口——不写结果、不写逐条缓存（占位入缓存会被后续轮次当命中复用）、计入 `failed_batches` 并触发
  「部分批次失败」告警，已消耗 token 照常计费；LLM 部分作答仍按正常产出处理（缺失项填默认值）。此前 3 批中
  2 批不可解析时，20/30 条占位被算成「含 LLM 分析」，并连带事件窗极性缺失（91% 事件不可判）。
- **批量用量行显示真实 token**（rf-1056）：归一化协议改按 usage 形状判定，不再把 provider 条目名
  （如 `deepseek-main`）当协议名传进 `_log_token_usage`，消除「输入 0 + 输出 0 = 0 tokens」的假账。
- **逐模块费用改用数值口径**（rf-1057）：不再回读 `estimate_cost` 的展示串（≥0.01 只到 3 位小数），
  消除 0.0646→0.0650 的精度丢失与「逐模块合计 ≠ 页签总计」。
- **HTML 生成阶段拆出子步骤耗时**（rf-1058）：模板渲染 / JS 资产内嵌 / 匿名化 / 落盘四步分别记入阶段细分
  （保留「页面写入」总值供跨版本比对），慢写告警只针对「落盘」段，慢的时候能直接定位到底是渲染、内嵌、
  匿名化还是磁盘 IO（同尺寸产物实测 0.02s / 6.15s / 21.0s 三档）。
- **慢段告警按段分流**（rf-1058）：`warn_slow_write` 支持自定义事件名与排查提示，渲染慢报「HTML 模板渲染 渲染
  偏慢 → 排查模板内逐行循环/过滤器」，落盘慢才报「排查磁盘/挂载与 fsync」；full/both 两条路径均接线。
  实测 0.98MB 产物**落盘仅 0.003s**，此前 6.15s 的「页面写入」实为模板渲染——告警方向原先指错了磁盘。
- **Jinja 模板字节码缓存**（rf-1059）：HTML 生成阶段的耗时实为**模板编译**（18 个模板 0.65s ≈ 97%，渲染仅 ~0.02s、落盘 0.003s），接入字节码缓存到 `<缓存根>/jinja/` 后**冷 0.654s → 热 0.027s（≈24×）**；键含模板源码校验和（改模板自动失效），缓存目录按需解析以尊重测试隔离与 `INVEST_CACHE_DIR`。

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.3（2026-11-04 ~ 2026-11-06）
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
