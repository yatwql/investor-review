# 变更日志归档 — v0.18.x

> 归档时间：2026-11-12（v0.18.0 发布并入；已并入 1 段：v0.18.0（11-12））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.18.0（2026-11-12）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.18.0] - 2026-11-12

### 修复

- **原子写「唯一原语」边界声明补全（rf-1133）**：模块注释原只登记 `cache/_io.py` 与 `config/_core.py` 两处有意例外，实际仓库另有 4 处自留原子写（报告 HTML / Excel 产物、模板字节码缓存、锚点分片）。补全为 6 处并逐条写明契约理由，消除「漏收还是刻意」的判断成本。
- **计划台账标题粘连 + 已完成项/契约文档滞留（rf-1131）**：`plan.md` 里 `## 归档` 被拼到 `plan-249` 行尾，归档索引段失去标题——`_doc_section` 找不到边界，待办区被静默拉长到文件末尾，四个已完成项（plan-248~251）因此跨 v0.17.9 发布仍留在待办区，其四份结构契约文档也滞留在 `docs/plan/`。现标题断行修复，四项按标题形态迁入 `archived_plan.0.17.x.md`，契约文档 `git mv` 进 `docs/archive/v0.17.x/`，`folders.md` 目录树与统计行同步。
- **已完成项识别盲区（rf-1132）**：`check-doc-drift` 的 plan 分区检查只认 `## ✅ plan-N` 标题形态，粗体 `**plan-N …**：已完成` 扫不到，已完成项可长期滞留待办区（本轮四条即由此漏检）。现补粗体分支 + 2 条回归用例（结论句报、在办进度句不报），`scripts-reference.md` 分区纪律与 `developer-guide.md` 发布步骤②同步写明「完成项须用标题形态」。
- **智囊团超时与实测生成时长对齐（rf-1130）**：`timeout_expert_review` 原为 120s，而实测生成时长 116 / 119 / 201s（`perf_history` 的 `llm.modules.expert_review.duration_seconds`）——`core.http_client` 的端到端墙钟到点即放弃请求，调用方随即原样重发，同一份内容付两次费并多等一整轮（实测一次 201.4s 中有 120s 是被丢弃那次的服务端生成）。现按 `max_tokens` 36000 / 实测速率 ≈168 tok/s（用满需 ≈215s）留余量，默认值改 240s：`config/_llm_settings_defaults.py`（事实位）、`llm/generators_singletons.py`（缺键兜底同值，不再回落旧值）、`data/config/llm_settings.json` 与实际生效值三处同步；`llm-technical.md` / `how-to-config-llm.md` 的模块参数表与取值范围同步，新增 `TestTimeoutCoversFullGeneration` 回归用例（断言满额输出所需时长落在 timeout 之内）。
