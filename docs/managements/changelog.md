# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.1]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.2-dev] - 开发中（未发布）

### 新增

- **配置默认值单源守卫（DEFAULTDUP）**：`check-code-traces.py` 增第四条 AST 支路，检出与默认值表同值同键的字面量兜底（`x.get("<键>", <默认值>)`）；默认表自身与测试不在扫描域，退出码归 CODE 桶（2）。回归 12 例（`test_trace_config_defaults.py`：检出/豁免/类型敏感/真实仓库零 finding）

### 变更

- **配置项默认值收敛**：`get_default()` / `get_llm_setting_default()` 支持点分嵌套路径（`a.b.c`）与逐层传参；生产代码 47 处「默认表同值字面量兜底」改走单一入口，`output_dir` 五处回退链统一走 `resolve_output_dir()`（相对串随 CWD 漂移）
- **debate 段默认值单源**：`_DEBATE_CONFIG_DEFAULTS` 由 `_DEFAULT_LLM_SETTINGS["debate"]` 深拷派生，删除原第二份字面量（`procon.per_call_max_tokens` 曾一处 `None` / 一处 `18432` 不一致；`max_total_tokens_per_report` / `per_call_timeout_override` 另有三套兜底）
- **provider 缺省优先级统一**：提取 `DEFAULT_PROVIDER_PRIORITY` 到 `_llm_providers_defaults.py` 并经 `config` 公开导出，替换排序/展示 9 处字面量（`llm_module_info.py` 原用 999 与其余 99 不一致）
- **报告深度档位常量下沉**：`REPORT_DEPTH_LEVELS` / `REPORT_DEPTH_DEFAULT` 迁入 `core/constants.py`（config 默认表与 llm 档位解析共用），`llm/depth_profile.py` 保留原面 re-export
- **持仓渠道判定单源**（rf-907）：新增 `core/holding_status.classify_channel(account)`，报告层两处明细组装改调它（原各自内联账户关键词判定）；`analysis/rebalance_advisor` 只消费 `channel` 字段，不再自行按 `account` 解析（渠道字段缺失即按证券类型判定）。回归 3 例（场外/场内/空值 + 「仅带 account 不生效」）
- **快照形态单一化**（rf-908）：`analysis/prosperity_signals` 提取持仓代码只认 `accounts[].holdings`（与 `schemas/history.SnapshotData` 一致），删除顶层 `holdings`/`details` 兜底；测试 fixture 与用例改为 accounts 形态 + 「顶层摊开不再被采纳」回归
- **移除单 Provider 配置形态，只保留 provider 链**（rf-901/902）：`llm/api.py` 删除 `_call_llm_legacy()` 与「无 `_provider_list` 即单 Provider 直连」回退（现在显式失败并告警，不再绕开链路由/熔断/端点节流）；`get_llm_config()` 不再把 `llm_key.json` 整份并进顶层配置；`core/system_info` 与 `core/doctor` 的 flat 展示/凭据分支随之删除；`llm_key.json` 顶层四字段（旧单 Provider 形态）不再被接受。单 provider 场景改用「一条 provider 条目」，能力不减（自动获得链路由治理）
- **旧配置自动迁移**：新增 `config._llm_providers.migrate_flat_key_config()`——读取到旧版顶层四字段时自动改写为 `legacy-default` 命名凭据块（原文件备份 `llm_key.json.bak`，首尾空格去除）并在 `llm_providers.json` 追加引用它的条目（幂等）；迁移失败不改原文件、日志给明确指引，LLM 章节按未配置占位
- **首次引导与交互配置写链形态**：新增公共入口 `config.write_llm_credentials()`（凭据块 + provider 条目原子写入，凭据分离），`startup_wizard._write_llm_key_flat` 改为其薄封装
- **手册同步**：`docs/manuals/how-to-config-llm.md` 快速配置改为两步（凭据块 + 线路条目）、7 个 provider 示例改写为链形态、新增「旧版配置迁移」节并删除 flat/多链「并存兼容」表述


### 修复

- **配置默认值/结构单源续修**：`llm_settings` 渲染路径的 `schema_version` 改必填严格校验（缺失/不为 2 即报错，与加载侧同口径，rf-903）；辩论缓存键前缀改取 `CACHE_PREFIX_LLM` 共享常量（rf-904）；`fetcher/price._price_cache_fresh` 的 `cache_key` 改必填（不再允许跳过收盘时点校验，rf-905）
- **测试离线隔离补全**（rf-906）：9 个 llm 价格/缓存用例文件补 `offline_external_sources`，消除本地「交易日历缓存过期即 62 例连带失败」的假红（CI 与本地口径对齐）

### 审查

- 完成「架构设计约束 / 设计契约 / 内部兼容适配」全面审查：约束表逐条机检未见违背（缓存统一与原子写入、HTTP 客户端统一、章节顺序不硬编码、日志统一、渲染期数据经 context、路径绝对化、LLM 缓存指纹单源、交易日计、重试与节流原语、TUI 分档只改版式——抽查表内各域代表条目；DESIGN.md / DESIGN-TUI.md 机检通过）；内部兼容层沉淀为 rf-901（旧单 Provider 配置簇）、rf-902（旧凭据文件格式）；rf-907（持仓渠道双输入）、rf-908（快照双形态字段）已同批结案

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.1（2026-10-25）
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
