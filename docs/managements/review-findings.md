# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.18.7-dev
> **编号源**：`rf-next = 1192`（新增问题提出后更新为 +1；已用最大 rf-1191，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线（主程序 700 / 脚本 600 / 测试 900）即登记。下表为存量监控项（红线：主程序 1000 / 测试 1200，触线必须拆分）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/python/core/perf.py` 799 行 | 采集器与台账落盘可拆（`perf` 采集 / `perf_history` 读写两文件） |
| `src/python/core/doctor.py` 785 行 | 检查项按域分文件（环境 / 配置 / 数据源 / 报告产物），入口只留编排 |
| `src/python/llm/fact_checker/_numerical.py` 764 行 | 数值校验按规则族拆（金额 / 比率 / 计数），共享解析原语上提包内 `_common` |
| `src/python/tui/handlers_config.py` 743 行 | 配置面板按域拆（内容选项 / 全局设置 / 目录与文件名） |
| `scripts/_doc_drift/_format.py` 742 行 | 格式化规则按文档类型拆（章节 / 表格 / 树 / 统计） |
| `src/python/core/degradation.py` 768 行 | 状态词与事件模型、登记面与持久化可拆两文件 |
| `src/python/report/action_sheet.py` 753 行 | 行动页签内各块（建议表 / 判断依据 / 决策书 / 复盘）拆子模块 |
| `src/python/fetcher/financial_report.py` 725 行 | 按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/python/providers/akshare_extras.py` 718 行 | 按接口族拆（指数 / 行业 / 分红 / 盈利预测） |
| `src/python/core/provider_registry.py` 710 行 | 熔断与会话缓存各自独立文件 |
| `src/python/llm/skeleton.py` 896 行 | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染） |
| `src/python/cli/_handlers.py` 890 行 | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄 |
| `src/python/tui/handlers_holdings.py` 825 行 | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于风险，暂不拆 |
| `src/static/tmpl/report_template.html` 277 行 | 样式已抽到 `partials/_report_styles.html`，各自单一关注点，均未触 1000 行 |
| `src/static/tmpl/whatif_template.html` 543 行 | **不在行数守护域内**（`check-file-length` 只扫 `.py`）；样式已抽到 `partials/_whatif_styles.html` |

## 已解决问题

### 开发期已修复（0.18.7-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| **rf-1187** | 发布台账只能读「至今累计 token」（跨会话累加），无法回答「这一版发布花了多少墙钟 / 多少 token」：`logs/release.jsonl` 每命令一行、`session_usage` 为 agent 会话累计值，靠人工翻 465 行对不出单版成本 | 新增只读汇总脚本 `scripts/probe-release-ledger.py`（按 `version` 去 `-dev` 切段 → 每版墙钟/分步耗时/会话 token 增量/失败步，`--last`、`--version`、`--json`、`-v`；只读，不改台账写入路径与发布步骤）；配 11 条用例（切段口径/跨版本不串账/同会话取前后差/新会话首行记 0/累计回退记 0/脏行与缺失容错/JSON 与选择器） |
| **rf-1188** | `config/_llm_schema.apply_flat_updates` 的 runtime 扁平键查表必须与 `flatten` 正向表同向（扁平键 → 字段）：键向若相反，`max_retries` / `daily_cost_limit` 因字段名恰等于扁平键而命中，`llm_max_concurrency` / `llm_max_thinking_concurrency` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` 永不命中 → 落到「未映射键原样保留在顶层」，v2 的 `runtime` 段不更新，随后 `flatten()` 用 runtime 段的值压过顶层透传 → 用户设置**静默丢失**（触发：`write_llm_settings` 在 `llm_settings.json` 缺失、`_DEFAULTS_NESTED` 兜底，或同批含 `debate`/`fact_check` dict 更新时走 `apply_flat_updates`） | 反向表改为按扁平键建 `{flat_key: field for field, flat_key in RUNTIME_FIELDS}`（查表方向与 `flatten` 正向表对齐）；补落点敏感回归——`runtime` 段落值 + 顶层无扁平键残留 + 六个运行时字段从 `RUNTIME_FIELDS` 参数化派生 + 写盘级直接解析落盘 JSON（`llm_settings.json` 缺失路径）；既有往返用例补落点位断言（`runtime` 段取值 + 顶层无扁平键残留） |
| **rf-1189** | 敏感缓存清理遇畸形 `_ts` 中断整轮：`cache/_cleanup.clean_sensitive` 用 `ts = payload.get("_ts", 0)` 直接参与 `now - ts`，任何字符串/None 时间戳抛 `TypeError` 并被导入期兜底吞掉 → 该轮清理中止，盘上其余过期持仓/穿透/基金缓存全部漏清（`cleanup_expired` 同期已有类型容错，两入口口径不一致） | 抽出共享 `_payload_ts(payload)`（缺失/非数值一律归 0.0），两入口同源；敏感缓存按「无法判定年龄 = 极旧」处理（宁可多清不可留存），单文件畸形不影响后续扫描；补 1 条回归（畸形 `_ts` + 正常过期文件同目录，断言两者都被处理）＋ 补齐清理/存储/运行边界/管线构建 5 个模块故障分支的 78 条用例 |

| **rf-1191** | 穿透表「行业分类不可用」降级在生产里不可达：`report/penetration._compute_penetration_top10_uncached` 第三阶段的 `remaining_data` 只在 `if remaining:` 内赋值，判据 `not prefetched and not remaining` 中 `remaining` 为「未预取覆盖的代码集」——行业链路熔断（`fetcher/industry.py` 直接回空）或批量全败（只回填成功项）时 `prefetched={}`、`remaining` 非空 ⇒ 判据恒假，`industry_success` 恒 True、`industry_failure_type` 永不写入，`penetration_sheet.build_penetration_data_status` 的降级分支在生产中永不触发；另外 `no_a_share` 只写 `industry_failure_type` 未联动 `industry_success`，同函数 220 行的 `no_a_share` 分支因此也不可达 | `remaining_data: dict = {}` 提到 `if remaining:` 之前初始化，判据改为「预取与补取均为空」（`not prefetched and not remaining_data`），保持既有 `industry_success=False` + `failure_type="empty"` 语义；无 A 股代码时一并置 `industry_success=False` 并写 `no_a_share`，使上游按类型区分「预期不降级」与真实失败有统一入口；补 3 条回归（预取+补取双空判 `empty` / 补取部分命中仍算可用 / 无 A 股不改降级结论） |

| **rf-1190** | 后置模块的重算原因归因恒判 `ttl_expired`：`llm/skeleton.generate_llm_content` 先把本轮键写入 `_PREV_MODULE_CACHE_KEY` 再做原因判定，判定读到的「上一轮键」永远等于本轮键 → 「无上轮记录 → cache_miss」与「换键 → fingerprint_changed」两个分支不可达，内容变化被系统性误标成「TTL 到期」，据此决策放宽 TTL 会得出错误结论 | 归因改取**写基线之前**的上一轮键（`_prev_key_before`），并把归因块抽成 `_attribute_recompute_reason()`（单一职责 + 降低骨架圈复杂度）；补 6 条回归（三态归因、已归因不覆盖、无汇聚器、端到端两轮判 `fingerprint_changed`） |

### 归档档案
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-19）
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-10）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-13 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-13）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-15 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
