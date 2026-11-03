# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.16]**（2026-11-03）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.16.17-dev] - 开发中（未发布）

### 变更

- **兼容面整改（rf-1025 / rf-1029 / rf-1031 / rf-1032 / rf-1033）**：
  - **缓存键版本残留（rf-1025）**：实测本机缓存目录 344 个文件全部为当前戳 `v4`、旧戳残留 0 个——TTL 兜底确实能清掉换代残留，故不必新增扫除动作；实际缺陷在 `cache_key_from_file_name` 只剥**当前**戳：旧戳文件反推出的逻辑键带 `_v3` → 精确键 TTL 表命不中 → 退成前缀默认 TTL（`sector_flow_` 仅 900s），有效期内的负缓存/回退基准被提前删。改为剥任意 `_v{N}` 戳，旧戳文件与当前文件同口径判龄。
  - **同阈值双名收敛（rf-1029）**：`core/perf.py` 删除 `SLOW_WRITE_WARN_SECONDS` 别名（模块内两处与测试统一到 `SLOW_SPAN_WARN_SECONDS`），消除「改一处漏一处」的两个名字并存。
  - **旧配置键处置口径单源（rf-1032）**：新增 `config/_legacy_keys.py`（`RENAMED` / `REMOVED` 登记表 + `format_unknown_keys` 归一文案）；`report_section_order` 的无效键与 `features.json` 的无消费开关改为**同一条归并告警**，逐键注明「已删除的原因 / 应改用的新键 / 疑似拼写错误」，两站点各自的处置动作（内存剔除 / 照常加载）保持不变。用户手册 `how-to-config.md` 新增「已删除 / 已改名的配置键」对照表（随登记表派生）。
  - **门面 re-export 面与形状容错归属（rf-1031 / rf-1033）**：`technical.md` 新增 §9.1「模块门面 re-export 面与退出条件」（永久面 vs 迁移期面 + 实测消费者数：`fetcher/chain.py` 53、`llm/generators_orchestrator.py` 39、`llm/holding_change_review.py` 15、`llm/depth_profile.py` 9、`report/_report_generation.py` 6，迁移期面写明下线判据）与 §9.2「形状容错归属」（第三方变体 / 本方输入形状 / 本方旧结构三分，逐分支给判据与处置——当前无「本方旧结构」待下线项）。
- **兼容面盘点（旧配置项 / 配置文件 / 数据文件 / 数据结构 / 缓存结构 / 缓存文件 / 内部 API）**：逐类核查后登记 9 项待评估（`review-findings.md` P3，rf-1025~rf-1033）——缓存键版本换代后的旧版本文件无主动清扫、决策账本旧结算事件按 5 日口径归属的读取分支、持仓明细双内部表示（DetailRow / dict）、`compute_purchase_status_data` 的未使用形参、`core/perf.py` 同阈值双名常量、`settle_pending_decisions` 单视界缺省、模块拆分 re-export 面缺退出条件、旧配置键静默处置口径不统一、上游返回形状容错与本方旧结构兼容混类。**核对为无兼容面**的部分：各配置文件的 `schema_version`/`version` 硬闸门（不符即拒载并提示重建）、`features.json` 无旧文件名回退、缓存读取路径不保留旧文件兼容（损坏即删）、`replay_schedule` 旧版本规则序列按未命中丢弃。
- **脚本层优化（`scripts/` 目录审计）**：
  - **并行扫描**：`check-code-traces --ci` 的逐文件扫描改进程池（默认 `min(4, CPU)`，不取满核以免与钩子内其它守护抢核；`CHECK_TRACES_JOBS=1` 可退串行复现）。结果按输入顺序回排，`--ci` 输出与结论缓存回放逐字不变；冷缓存全量扫描 7.9s → 2.4s，十项守护冷缓存合计 12.0s → 7.2s（其余九项均 ≤1.1s，无需并行化）。
  - **子进程超时**：守护/钩子/编排类脚本对 `git`、`pytest`、子脚本的调用统一补 `timeout=`，超时按「环境不可用」走明确分支——结论缓存指纹退全量重算（方向安全）、pre-commit 钩子放行并告警、发布编排抛 `ReleaseError`，不再把提交钩子或 CI `guards` job 挂成无输出等待。
  - **文档**：`scripts-reference.md` 的 `check-code-traces` 段删掉重复的 AST 守卫表（同表出现两次），并补「性能与并行」「子进程一律设超时」两条公有约定。
  - **审计结论**：`scripts/` 下 143 个 `.py` 未发现死代码与重复实现（同名函数经核对均属入口 re-export 或语义不同）；`open()` 全部显式 `encoding=`；仅 2 处 `except Exception: pass`，均为 stdout 重编码兜底与调试日志写入。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.16（2026-10-25 ~ 2026-11-03）
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
