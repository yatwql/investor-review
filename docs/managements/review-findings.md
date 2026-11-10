# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.8-dev
> **编号源**：`rf-next = 1114`（新增问题提出后更新为 +1；已用最大 rf-1113，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

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

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1187 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 863 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 847 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 856 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 825 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 719 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.8-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复 |
| --- | --- | --- |
| rf-1107 | 基金经理变更监控常显「首次运行」：跟踪基线快照被按上报域 24h TTL 的清理器删除（报告生成入口每次先自动清理），且「刷新基础缓存」只清不重建该键 | 快照键登记近永久精确键 TTL（`CACHE_NEAR_PERMANENT`）+ `clear_by_group` 新增 `exclude_keys` 供刷新流程点名保留；补「隔 48h 二次报告仍非首检」等回归用例 |
| rf-1113 | 事实校验只报「告警/检查项」，从不报覆盖率：与真值不符的声称一旦落进「无主体/无收益语境」就被静默跳过，统计上与「通过」无法区分（实测整份报告 276 条声称仅 52 条被比对，19%）；评测脚本也没有重放既有报告的能力，修复效果无法在固定样本上验证 | 新增覆盖率统计 `_coverage.py`（已比对/不符/跳过+原因分桶）；`--from-report <html>` 默认关的可选重放模式（零 LLM、持仓取自报告自身表格）；补覆盖率与重放解析用例 |
| rf-1112 | 前缀缩写主体解析不出 → 与持仓真值矛盾的收益率（017730 一处 -8.5%）被当「无主体」跳过、长期留在正文；修正明细沿用组合盈亏，把亏损品种标成「盈利」；离线评测 dry-run 对提示词做事实校验，产出假幻觉率（9 项 / 22%） | 新增第五主体来源 `_match_name_prefix`（前缀 ≥4 字且唯一）+ 「名称包含」判据加严格闸；方向标注取品种自身盈亏；dry-run 跳过事实校验并在报告注明 |
| rf-1111 | 生成后自检定位不清：作为默认开启项，它是单份报告输入最大的一遍 LLM 调用，产物只是尾部清单，且会把模块里的错值当事实转述（017730 亏损 -8.5% vs 摘要 -5.06%）；上屏仍透传内部模块键，离线也没法被程序解析 | 降级为实验能力（默认关）+ 离线抽样 `--self-review`；提示词与产物改「中文名（内部键）」双写（上屏剥离内部键、离线保留）；把可判定的跨模块收益率冲突做成确定性检查器（零 token）并置于复核区块最前 |
| rf-1110 | 生成后自检直接透传内部模块键名（`global_macro`/`penetration_deep`），上屏不可读；自检引用模块里的错值（017730 亏 -8.5%，摘要真值 -5.06%）时无任何核对，读者会把模型复核当结论 | 提示词按中文模块名投喂 + 禁止输出内部键 + 摘要为数值真值来源；输出侧兜底替换残留键名；引用百分比做语料核对，未定位追加「无法核实」注记 |
| rf-1109 | 近 40h 实施遗留：机器 IP 探测原语放在 `core/logger.py`（与 `core/system_info.py` 声明的「机器信息单源」相悖），且 logger 内一段函数文档失去绑定成孤立字符串；`pytest_env` 四个插件探针各写一份 | 迁到 `core/system_info.py` 并更新全部消费方/测试 patch 点；删除孤立字符串；探针收敛为 `_has_plugin()` |
| rf-1108 | 增量历史缓存键拼成 `history_history_{chain}_{code}`，未命中任何注册表前缀 → 按 default 日档 24h 清理：K 线文件每日全量重取，`_correction_streak` 计数每日重置导致「连续检出→跳过全量刷新」冷却永不触发；`market_hours` 未登记落 default；`{cache_key}_correction_flag` 只写不读 | 新增唯一键构造器 `history_cache_key()`（`{chain_name}_{code}`）并替换 `index.py`/`clear_incremental_cache` 的手工拼接；`market_hours` 登记入 `calendar` 精确键；删除死写；新增键形状 ↔ 注册表覆盖契约测试 |

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-09）
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
