# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.2]**（2026-11-05）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.3-dev] - 开发中（未发布）

### 修复
- **缓存 TTL 矩阵用例在凌晨不再假失败（`rf-1054`）**：这些用例原先用 `now.replace(hour=8)` / `now.replace(hour=10, minute=5)` 造时间戳——跑在 00:00–08:00 时戳落在未来，年龄为负，「超过静态 TTL 必须回收」「盘中快照盘后回收」两类断言随之失真（实测 01:01 出现 14 例失败，HEAD 上复现，与业务改动无关）。现抽 `_recent()` 取「今天该时刻的过去最近一次」，时段语义不变、与运行时刻无关，105 例全通过。
- **LLM 模块结果行不再把「失败」写成「生成失败（跳过）」（`rf-1052`）**：provider 全挂、用户关开关、预算到点三种情况过去都打成同一条 INFO，事后按日志无法区分「内容为什么缺」。现按 `LLM_MODULE_FAILURE` 分四级：成功 / 开关关闭 / 预算跳过走 INFO，**其余一律 ERROR** 并带可读原因（如「LLM API 网络连接失败」）与「报告对应章节将降级/占位」；`llm/skeleton.py` 的失败行补上模块名与原因（此前只有一个缓存键）。失败原因文案收敛到 `llm/failure_reasons.FAIL_REASON_LABELS` 单源，报告模块状态直接引用同一表（原 `report/llm_module_info._DISPLAY_REASON` 副本删除）。补 9 例单测（四条分级分支 + 文案单源身份断言 + 未知/缺失原因回退）。
- **基金经理全部解析失败时给出下一步（`rf-1053`）**：实测连续两天（10-30、11-02）档案页 SSL 握手超时，日志只有一句「基金经理全部解析失败」，读者无从判断要不要处理。现告警写明「本轮按缺数据降级（报告该章写占位），下次运行会自动重试；若连续多日出现，先查档案页链路是否可达（SSL/超时）」。补 1 例单测（告警须含降级与重试方向）。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.2（2026-11-04 ~ 2026-11-05）
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
