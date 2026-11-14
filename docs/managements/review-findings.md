# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.18.1-dev
> **编号源**：`rf-next = 1141`（新增问题提出后更新为 +1；已用最大 rf-1135，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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
| `src/test/conftest.py` 1191 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 656 行（主程序登记线 700） | 块装配与生成后一遍已下沉（`_llm_context_blocks` / `_llm_post_pass`）；预检键/指纹段后续可再下沉 `generators_orchestrator_cache.py` |
| `src/python/llm/skeleton.py` 847 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 858 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 825 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 719 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.18.1-dev）

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1140** | 报告管线单测未声明离线桩：`generate_report()` 会起数据源健康检查线程（真实网络 + akshare `py_mini_racer` V8 初始化），xdist worker 里并发初始化 V8 会段错误崩溃（CI：3 个 worker crashed，整套 1.5min → 12min，且偶发才出现、难定位） | 三个报告管线测试文件统一声明 `offline_external_sources`（探针即时失败、零退避、不触发 V8）；并新增契约守卫 `test_offline_pipeline_contract.py`（真实调用管线入口却漏声明离线桩即红，防同类复发） |
| **rf-1139** | akshare 1.19+ 把 `bond_zh_us_rate` 改名为 `bond_zh_us_yield_em`（数据集/中文列名不变），而取数只认旧名：CI 装到 1.20.42 后 11 条无风险利率用例在 `@patch("akshare.bond_zh_us_rate")` 处 AttributeError 直接失败；生产侧还把「属性不存在」当调用异常，白记一次 akshare 熔断失败（新版用户每份报告都误报数据源故障） | 新增 `_resolve_bond_yield_api()` 按版本探测两代 API（旧名优先，探测结果进程内记忆，缺失只降级不记熔断），两处调用点改走 `_bond_yield_frame()`；用例改为 patch 本方 seam（版本无关），新增 4 条探测/降级用例；文档四处口径同步 |
| **rf-1138** | 全仓扫描发现 4 组「跨模块各写一份」的常量（注释里还写着「与 X 同值」）：退出码 `_EXIT_*`（CLI / Web worker 各一份）、push2 快照接口 URL（`core/market_hours` / `providers/eastmoney_industry`）、年化交易日数 252（3 个 analysis 模块）、最小样本 20 与份额容差 1e-3（各 2 个模块）——改一处漏改另一处会让两条路径口径分叉 | 单源归位：退出码与 push2 URL 进 `core/constants.py`（`EXIT_*` / `EASTMONEY_PUSH2_BASE`），统计/容差常量进 `analysis/_math_utils.py`（`TRADING_DAYS_PER_YEAR` / `_MIN_SAMPLE_DAYS` / `SHARES_EPS`），各调用点保留原名做别名；新增 `test_cross_layer_constants.py` 7 条守卫断言各处值等于单源值 |
| **rf-1137** | 18h 自查发现两处新代码缺直接覆盖：`market_hours.is_otc_nav_disclosed` 在所有用例里都被 patch 掉（边界/时区换算没测过），`ProviderState.cooldown_override` 新增的持久化字段无落盘往返用例（重启后自定义冷却期会丢） | 补 6 条用例：披露时点边界（19:59/20:00/早间）、naive 视为北京时区、跨时区换算、自定义冷却期落盘回读 |
| **rf-1136** | 「代码类型判定中心化」纪律被违反：`report/news_correlation._index_holdings` 自建 `"ETF" in name` 判定，既绕过 `core/code_utils.is_etf_by_name`，又因大小写敏感导致小写 `etf` 的品种不进 ETF 关键词扩展分支、且 `replace("ETF","")` 剥不掉，关键词召回与该品种的资产类型口径分叉 | 改为 `is_etf_by_name(name)` 判定 + `re.sub(r"(?i)etf", "", name)` 剥离，补 3 条回归用例（小写扩展 / 大写保持 / 判定单源） |
| **rf-1135** | `developer-guide.md` 把 HTML 生成细分写成「四步」且断言「模板编译占绝大多数」——实测 `模板渲染` 约 0.0s、`面板视图装配` 2.1s of 2.13s，该结论会把优化方向指向 jinja；同时 `面板视图装配` 这一步（本轮新增的计时点）文档未列 | 两处文档同步为实际细分与实测结论（`developer-guide.md` 慢段排查表、`technical.md` 编排器职责链） |
| **rf-1134** | `check-doc-drift` 的已解决台账行只认 `| **rf-N** |` 加粗形态，未加粗时既不进已解决集合、归档步也按「本版无待迁档」跳过（0.18.0 发布时实际发生：已修项主台账未被搬运） | 新增 `_RF_ROW_UNBOLD` 分支：已解决区出现 `| rf-N |` 未加粗行即报 finding + 2 条回归用例（报/不报各一）；归档识别口径不变 |

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

### 归档档案
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-12）
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
