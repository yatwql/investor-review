# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.4]**（2026-11-08）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.5-dev] - 开发中（未发布）

### 修复

- **幻觉采样三处断言只看「有告警」**（rf-1065）：`test_wrong_profit_rate_vs_portfolio` / `test_mixed_correct_and_wrong` /
  `test_missing_code` 原本只断言 `len(issues) >= 1`——检测器把任意无关数值判成偏离也能转绿，测不出「对照的是组合
  累计收益率 / 涉事个股 600036 / 涉事代码 002837」这一核心口径。现补点名断言（含实际值 9.7% 与代码）；
  与仓内已有的 `test_wrong_stock_return`（已断言 `issues[0]` 含代码）同标准。
- **缓存边界用例名实不符**（rf-1065）：`test_intraday_written_cache_expired_right_after_close_gate` 名称称
  「盘后已过期」，断言却是「仍可读」（本用例只验读侧，收盘时点门禁由同文件 TTL 口径用例覆盖）。
  改名为 `test_intraday_written_cache_survives_static_ttl_after_close`，docstring 直接写明验证的是「静态 TTL 下仍可读」。

### 清理

- **`test-coverage.md` 揟掉历史复盘痕迹与失真导语**（rf-1066）：两条带日期的「门禁口径变更」告示（含「修复前匹配全空」
  「台账旧值 10,136」「9,800→10,145」）已在 `changelog`/归档，不再在统计页重复；其中「上方 `dev-verify`/`verify`
  两行为并入前快照」已是错误导语（该表已重测），删除后条目只留当前口径并指向 `technical.md` §4.23。「两机差距」
  段内联的绝对耗时（`unit ~28s`/`all ~39s`/`data ~3s`）与紧邻其上的表（`~1min`/`~28s`/`~5s`）相矛盾，改为只陈述
  按表重算的比值区间；旧采集事故叙事改为不带日期的排查口径（先查未 mock 外部访问，再谈负载与并行度）。
- **8 份文档正文清掉历史复盘痕迹**（rf-1067）：`DESIGN.md` / `developer-guide.md` / `technical.md` / `llm-technical.md` /
  `scripts-reference.md` / `testplan.md` / `datasource-reliability.md` / `how-to-config-llm-reference.md` 里的带日期告示
  （「已采纳 / 已落地 / 收紧」）、「曾经的写法」「曾占…现口径」「历史漂移」等对照叙事，统一改写为**当前状态陈述**：
  告示去日期与「已采纳」口吻只留规则；对照叙事改为「若…则…」的风险机制；缺陷描述改为要求陈述；口径类内容指向真源
  （如 `technical.md` §4.23 / §9.2）。实测确认：仅保留实测数据点的日期（取值快照），不保留变更公告式日期。
- **程序注释清掉历史复盘叙事**（rf-1068）：`src/python` 47 处、`scripts` 19 处、`src/test` 44 处「此前 X 现在 Y」
  「原先各写一份」「曾占…」式对照与带日期的校准告示，统一改写为**当前状态陈述**：对照句改「若/不得 X，否则 Y」，
  告示去日期只留规则，重命名史改「不得沿用旧称」。保留「回归背景 / 回归场景」元描述（`CLAUDE.md` 明确豁免，
  用于说明断言为何存在）。顺带修 `edit_ops`/`_ymd` 两处入参类型收窄（Pyright 报 Unknown|None 赋给 str）。
- **评测脚本 global_macro 漏传 `total_cost`**（rf-1069）：`scripts/_eval_halluc_sampler/llm_call.py` 调用
  `_build_global_macro_prompt` / `generate_global_macro` 时少传 `total_cost`——`categories` 落在 `total_cost` 位置、
  `categories` 缺参，该评测路径运行时必抛 `TypeError`。补实参；顺带初始化 `cached=False`（未命中任何分支时不再未绑定）。
- **6 文件静态类型债清理**（rf-1069）：`prompts_signals._is_number` 改 `TypeGuard[float]`（11 处数值运算不再报
  Unknown）、`generators` 的默认值取键前 `isinstance(..., dict)` 收窄且 `_max_tokens` 显式兜底 18432、
  `generators_orchestrator` 的基线组件 `or {}`、`test_correlation_html` 用 `_require_section()` 断言取节点并
  去掉 Optional 下标、`test-smoke-web`/`metrics.py`/`_llm_settings`/`atomic_write` 的 Optional 与 I/O 调用收口。
- **96h 变更技术债收口**（rf-1070）：去 Jinja 化批次留下的 `.bg-primary` / `.bg-alloc-mid` / `.bg-alloc-low`
  三条工具类无任何引用（SVG 用的是 `.fill-alloc-*`），按死样式删除并重标定报告页 CSS 规则集哈希；
  `close_html_generation_stage`（full/both 共用收口）此前只有端到端间接触及，补 4 条直测锁住其分支——
  无 recorder 静默返回、有分段时按「落盘」耗时告警、渲染慢指向模板而非磁盘、无分段时回落总值。
- **控制台着色回归「色源单源」约束**（rf-1071）：`core/ansi_colors` 新增 `RAW_CODES` 与
  `supports_color(stream)` / `codes_for(stream)`（按**指定流**判定着色能力），`core/doctor.py` 与
  `report/cli_progress.py` 改为调用前者——此前两模块各自硬写 `\033[...` 转义码并各自复制
  `NO_COLOR`/`isatty` 判定，改配色或降级口径必漏改一处。
- **删掉最后一处「旧内部接口」门面**（rf-1072）：`core/data_freshness._detail_value` 只是
  `core/detail_view.detail_value` 的一行转发（自述「仅保留旧名」），`holding_status` 也经它取值；
  现已统一直调 `detail_value`。兼容面七类复核结论保持不变：旧配置项/旧配置文件/旧数据文件/
  旧数据结构/旧缓存结构/旧缓存文件均无兼容分支（结构变更一律硬闸门拒绝或整体作废，见 `technical.md` §9.2）。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.4（2026-11-04 ~ 2026-11-08）
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
