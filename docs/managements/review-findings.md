# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.6-dev
> **编号源**：`rf-next = 1085`（新增问题提出后更新为 +1；已用最大 rf-1081，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

### P3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1170 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 843 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 847 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 852 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 825 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 719 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.6-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| 编号 | 问题 | 修复 |
|:--|:--|:--|
| **rf-1079** | `[S]` 面板混排两类语义（章内内容 vs 机制/入口）：6 项机制类里「报告对话式追问」其实只是主菜单 `Q` 的入口开关；`decision_basis` / `module_quality_gate` 默认常开却占面板编号；`candidate_compare` 候选池为空也渲染空表；`whatif_trade_cost` 挂在 `[C]`「关联产物」但不新增章节；`market_sentiment` 需凭据却未标 `needs_hint` | 注册表新增 `panel_visible` 并据此派生编号：前两者不上面板（默认常开，仍可用 `features.json` 覆写关闭）；`candidate_compare` 改自动项（不上面板、补空池判定）；`summary_highlights` 转正默认开；`market_sentiment` 补 `needs_hint`；`whatif_trade_cost` 迁入 `[S]` 持仓与交易，`[C]` 回归纯章节；守护与夹具补「空块」容忍 |
| **rf-1080** | 成本流水「近似分支」缺数值防护：`_build_flow_data` 把明细里的 `price` 原样收进 `current_prices`，一旦是非数值（旧缓存/残缺明细/测试桩），下游 `sum(... * prices[code])` 与 `final_value > 0` 即抛 `TypeError` ——异常冒泡到 HTML 写入，整份报告 `html_ok=False`。该分支此前只有mock 级用例（只验传参），真实执行路径从未被跑到 | `current_prices` 改为只收「正数值」市价（`isinstance(price, (int, float))` 且 > 0），缺价品种只是少一个估值锚；补两条真实现回归：无流水 + 开关开跑通近似契约、非数值/字符串市价被过滤不抛 |
| **rf-1081** | 面板可见性须跨渠道同源：`panel_visible=False` 的开关（判断依据 / LLM 输出评级 / 候选基金比较）若只按 TUI 过滤，Web 配置面仍按 `switches_in_group` 全量下发，两渠道开关清单即分叉；另有两处同批清理：`tui/handlers_holdings` 里单笔回显函数已无调用点（死代码），以及「行情口径桶」的测试冻结逻辑在 3 个文件里各写一份 `MarketSnapshot` 字面量（档位 label 会各处漂移） | 新增 `_feature_registry.panel_switches(panel)`（组序 + 可见性过滤）作为面板类渠道的唯一取数口，`panel_option_numbers` 复用、Web 配置面改用它过滤；删除死函数；新增 `src/test/_market_clock.py`（`freeze_market_bucket` / `freeze_intraday`）替换各处字面量桩 |
| **rf-1082** | `init_config` 新增「缺失即按模板铺出 `logger.json` / `llm_pricing_ref.json`」，但无用例锁定该行为（新行为无回归）；另 `test_init_template_writes_relative_paths` 只屏蔽了原本两处写盘入口，新增两处在它临时还原真实路径的分支里会把文件写进仓库 `data/config/`（测试隔离漏洞，文件被删时静默恢复） | 补两条用例：缺失即铺出且有注释模板、已存在不改写（幂等）；该用例的写盘屏蔽补齐到四处 `_ensure_llm_settings_file` / `_ensure_llm_providers_file` / `ensure_logger_file` / `ensure_llm_pricing_file` |
| **rf-1083** | 归因口径收口为「只看模块键是否变化」后，`llm-technical.md` 仍在描述已不存在的「模块→组件映射表」（文档与实现分叉）；同批拆分用例时丢了 `TestSkeletonPathAttribution` 类头（骨架路径归因的来由注释），且 `_cache_fixtures.degradation_events` 构造器无人调用（死测试设施） | 文档改为「唯一判据是键变化，组件哈希只服务诊断可读性」；恢复类头；补回归：降级事件变化只让 `health_check` 归因为 `fingerprint_changed`（数据质量变了不得计作「只是到点」），顺带重新启用该构造器 |
| **rf-1084** | 面板分块口径漂移：rf-1079 把 `whatif_trade_cost` 从 `[C]`「关联产物」迁入 `[S]`「持仓与交易」后，注册表已无 `artifact` 条目、`[S]` 编号整体重排，但 8 份文档仍按旧口径描述（`[C]`「四块含关联产物」/`[S]` 1-4·5-8·9-11·15-20 旧编号/「四组章内内容」/`--chapter` 可覆盖关联产物/R-WIF-13 分组），读者会按错面板找入口 | 全量核对后按实现单源重写：`[C]` 统一为三块（顶层 / LLM / 整章，并注明 `artifact` 分块位保留、空块自动跳过）；`[S]` 编号改为 1-5 / 6-9 / 10-11 / 12-14 / 15-18（`decision_basis` / `module_quality_gate` 内置常开不占编号）；关联产物入口统一指向 `[S]` 持仓与交易组（含 `--chapter` 与 R-WIF-13 表述） |

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-08）
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
