# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.9]**（2026-11-11）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.10-dev] - 开发中（未发布）

### 修复

- **原子写「唯一原语」边界声明补全（rf-1133）**：模块注释原只登记 `cache/_io.py` 与 `config/_core.py` 两处有意例外，实际仓库另有 4 处自留原子写（报告 HTML / Excel 产物、模板字节码缓存、锚点分片）。补全为 6 处并逐条写明契约理由，消除「漏收还是刻意」的判断成本。
- **计划台账标题粘连 + 已完成项/契约文档滞留（rf-1131）**：`plan.md` 里 `## 归档` 被拼到 `plan-249` 行尾，归档索引段失去标题——`_doc_section` 找不到边界，待办区被静默拉长到文件末尾，四个已完成项（plan-248~251）因此跨 v0.17.9 发布仍留在待办区，其四份结构契约文档也滞留在 `docs/plan/`。现标题断行修复，四项按标题形态迁入 `archived_plan.0.17.x.md`，契约文档 `git mv` 进 `docs/archive/v0.17.x/`，`folders.md` 目录树与统计行同步。
- **已完成项识别盲区（rf-1132）**：`check-doc-drift` 的 plan 分区检查只认 `## ✅ plan-N` 标题形态，粗体 `**plan-N …**：已完成` 扫不到，已完成项可长期滞留待办区（本轮四条即由此漏检）。现补粗体分支 + 2 条回归用例（结论句报、在办进度句不报）。
- **智囊团超时与实测生成时长对齐（rf-1130）**：`timeout_expert_review` 原为 120s，而实测生成时长 116 / 119 / 201s（`perf_history` 的 `llm.modules.expert_review.duration_seconds`）——`core.http_client` 的端到端墙钟到点即放弃请求，调用方随即原样重发，同一份内容付两次费并多等一整轮（实测一次 201.4s 中有 120s 是被丢弃那次的服务端生成）。现按 `max_tokens` 36000 / 实测速率 ≈168 tok/s（用满需 ≈215s）留余量，默认值改 240s：`config/_llm_settings_defaults.py`（事实位）、`llm/generators_singletons.py`（缺键兜底同值，不再回落旧值）、`data/config/llm_settings.json` 与实际生效值三处同步；`llm-technical.md` / `how-to-config-llm.md` 的模块参数表与取值范围同步，新增 `TestTimeoutCoversFullGeneration` 回归用例（断言满额输出所需时长落在 timeout 之内）。

## 归档

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
