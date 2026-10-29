# 目录结构与项目统计
> 文档版本：0.16.10-dev
>
> 项目目录树 — 新增/重命名任何非排除文件或目录时，必须同步更新此文档。
>
## 项目统计

> **项目统计**
>
> | 类别 | 开发语言 | 文件数 | 代码行数 | 说明 |
> |---|---|---|---|---|
| 主程序代码 | Python | 406 | 109,400 | `src/` 下所有 `.py`（不含测试：`src/__init__.py` 顶层包标记 + `src/python/` 下 15 个 `__init__.py`，含 `web/` 服务层；近期新增 `providers/tiantian_purchase.py` 天天基金申购状态总表 provider + `fetcher/fund_purchase.py` 申购状态取数编排（双链路/准入/会话复用） + `core/jsonl_store.py` JSONL 原子原语 + `core/signal_ledger.py` 确定性信号账本 + `report/signal_record.py` 信号登记适配器 + `core/num_utils.py` 数值归一原语 + `core/doctor.py` 系统自检 + `core/cassette.py` 请求回放引擎 + `core/datasource_credential.py` 数据源凭据声明 + `fetcher/source_adapter.py` 适配契约 + `fetcher/quote_adapters.py` 行情域适配器 + `llm/module_fingerprint.py` 模块指纹唯一事实来源 + `report/_experimental_seams.py` 实验挂载点 + `report/holdings_freshness.py` 持仓报告期时效判定 + `report/experimental_notice.py` 实验功能清单语句单源 + `core/trading_calendar.py` 交易日历原语（时间距离一律以交易日计） + `providers/datasink.py` 全文本财报 provider（密钥/限速/配额） + `providers/hithink.py` 同花顺金融数据服务 provider（A 股行情/财务/基金/情绪面；凭据/qps 限速/信封错误码） + `fetcher/financial_report.py` 财报取数编排 + `fetcher/report_adapters.py` 财报域适配器 + `report/financial_report_digest.py` 财报摘要章节装配 + `providers/akshare_financial.py` 结构化财务指标主源 + `fetcher/financial_indicator_adapters.py` 财务指标域适配器 + `core/code_symbols.py::to_fmp_symbol` 共享符号映射 + `providers/utils.py::run_with_timeout` 共享取数超时原语 + `analysis/financial_indicator_extract.py` 财务指标全文解析（压平正文锚点提取，备用支路） + `fetcher/financial_indicator.py` 财务指标多期取数编排 + `analysis/financial_indicator.py` 财务指标派生（质量档/趋势/当前 PE·PB） + `report/financial_indicator.py` 财务指标章装配 + `report/holdings_detail_sheet.py` 持仓明细与分类 Excel 页签 + `report/position_structure_sheet.py` 持仓结构与集中度 Excel 页签 + `report/fundamental_snapshot_sheet.py` 持仓基本面 Excel 页签（三者均为章节合并写入器） + `llm/compliance.py` 合规声明集中注入（幂等叠加，单一漏斗覆盖全模块）） |
| HTML 报告模板 | HTML | 23 | 5,198 | `src/static/tmpl/report_template.html` + `whatif_template.html`（调仓 What-if 独立 HTML 页）+ `partials/`（章节级/区块级 partial，主模板按 TOC 六组经 Jinja include 拆入，清单见目录树 `partials/` 节点） |
| 架构图示 | SVG | 4 | 396 | `src/static/` README 架构图（architecture 三渠道→引擎→双报告、llm-chain Provider 链式分发、capabilities 九大功能域总览、owl-mascot 吉祥物猫头鹰「守望」）+ 截图 7 张 PNG（报告实景 `report-overview`/`report-toc`/`report-charts` + 界面实景 `tui-menu`/`web-workbench`/`web-config`/`cli-report`，不计入本行） |
| 辅助脚本 | Python | 135 | 26,653 | `scripts/`（启动脚本 + CLI 命令行包装、测试驱动、工具检查、任务编号检查、性能测试、LLM 幻觉率评测与因子目录评测、测试覆盖计数、代码/文档历史痕迹与结构性冗余检查、视觉资产（社交预览图/架构图体检）、语义命名索引校验、Claude Code hook 安装/校验、Web 冒烟脚本、push2 连通性诊断、SVG 架构图检查） |
| 源代码合计 | — | 568 | 141,647 | 主程序 + 模板 + 脚本 + SVG |
| 测试代码 | Python | 672 | 184,491 | `src/test/` 所有 `.py` 文件（含近期 ruff format 全仓重排） |
| 测试用例 | — | — | 12,684 个 | `pytest --collect-only` 统计（`scripts/test-collect-coverage.py` 实时收集快照，不含 opt-in live 套件） |
| 用户文档 | Markdown | 15 | 6,767 | 含 README.md；行数为 README + manuals 之和 |
| ├ manuals/ | 用户手册分册 | 14 | 6,549 | 配置/faq/快速上手/TUI/CLI/Web 三种模式指南等 |
| 项目文档 | Markdown | 202 | 70,369 | 含 CLAUDE.md；md 口径为 CLAUDE.md + `managements/` + `plan/` + 版本归档之和（分项见下方三行），py/txt 不计行 |
| ├ managements/ | 管理文档 | 13 | 13,790 | 变更日志/目录树/测试计划/技术设计/开发者指南等 |
| ├ archive/ | 版本归档 | 185 | 55,983 | 各版本 changelog/plan/review-findings 与设计文档归档（含 Vibe-Trading/gs-quant/TradingAgents 借鉴批候选研究、基金申购限购三份设计与 LLM 成本调节/自检/源指定设计） |
| ├ plan/ | 中间设计文件 | 3 | ~503 | 在办设计文档（扁平存放）：Jev 新闻关联判定（对照评测 + 类型化通道设计）+ 决策跨期反思闭环设计 |
| └ tmp/ | 临时文件 | — | — | 调试产物、迁移暂存（git 忽略，不计入统计） |

## 版本演进对照（最初版本 → 最新发布 → 当前开发版）

> **性质**：点对点快照对照（回答「这个项目从哪来、长到多大」），非门禁校验项——与上方「项目统计」的区别是它有**两个固定基准**：最初版本 vs 最新发布。
> **三个读数**：最初版本 = 仓库首个提交（`项目初始基线`，2026-06-27）；最新发布 = 最近一次发布 tag（v0.16.9 · 2026-10-29）；**当前开发版 = 本次重跑时的工作区**（`git ls-files` 清单 + 直接读磁盘，故含未提交改动）——第三列是**滚动读数**（按需重跑刷新），前两列是固定快照（发布点不动）。
> **复现方法**：与上方「项目统计」同一套分类规则，对每个 revision 各跑一遍下述三步；「当前开发版」一列按需重跑即可刷新（该列省略 `<rev>`、以 `git ls-files` 取清单，即在工作区上统计）。

```bash
# ① 文件清单（某 revision 的全部跟踪文件；统计「当前开发版」时改用 `git ls-files`（工作区））
git ls-tree -r --name-only <rev>

# ② 逐文件精确行数（git 原生、无需 checkout）：
#    把清单喂给 cat-file --batch，按 header 的 size 截取内容后数换行符（末行无换行按 1 行计）
git cat-file --batch            # 输入逐行 <rev>:<path>

# ③ 测试用例数（测试函数定义数）
git grep -c "def test_" <rev> -- 'src/test'
```

> 等价做法（更省事，前两列即以此重跑）：`git archive <rev> | tar -x -C <临时目录>` 导出后本地计数——免去逐文件 `cat-file` 的解析；口径同上（末行无换行按 1 行计）。

| 指标 | 最初版本（首个提交 · 2026-06-27） | 最新发布（最近发布 tag v0.16.9 · 2026-10-29） | 当前开发版（0.16.10-dev · 本次重跑时的工作区 · 2026-10-29） | 增长（最初 → 当前） |
|:-----|:----------------------------------|:-----------------------|:--------------------------|:----:|
| 主程序（`src/**/*.py`，不含测试） | 30 文件 / 7,258 行 | 406 文件 / 109,403 行 | 406 文件 / 109,403 行 | 15.1×
| 测试（`src/test/**/*.py`） | 13 文件 / 6,108 行 | 672 文件 / 184,494 行 | 672 文件 / 184,494 行 | 30.2×
| 辅助脚本（`scripts/*.py`） | 0（当时仅 `launch.sh` / `launch.ps1`） | 135 文件 / 26,655 行 | 135 文件 / 26,655 行 | 新增
| HTML 报告模板（`src/static/tmpl/*.html`） | 0（当时为 `src/tmpl/`：1 个 / 469 行） | 23 文件 / 5,198 行 | 23 文件 / 5,198 行 | 1 → 23
| 架构图示（SVG） | 0 | 5 文件 / 413 行 | 5 文件 / 413 行 | 新增
| 文档（`.md`） | 7 文件 / 1,355 行 | 220 文件 / 77,314 行 | 220 文件 / 77,314 行 | 57.1×
| **代码文件合计**（前 5 项） | **43** | **1,241** | **1,241** | 28.9×
| **代码行合计**（前 5 项） | **13,366** | **326,163** | **326,163** | 24.4×
| **测试用例数**（`def test_` 行数口径） | **491** | **11,891** | **11,891** | 24.2×
| 仓库文件总数 | 56 | 1,535 | 1,535 | 27.4×
| 仓库总行数（全部跟踪文件） | 15,600 | 420,042 | 420,042 | 26.9×

> **口径与读数说明**（避免误读三个"新增/突增"）：
> - **测试用例数**采 `git grep -c "def test_"` 的**行数口径**（含注释/文档串中的 `def test_` 提及）：最初 491 → 当前 11,891；按更严格的「以 `def test_` 开头的定义行（含类方法缩进）」口径为 11,813；pytest 实际执行计数（含参数化展开）不在此写死，以 `test-coverage.md`「模式对应测试量」表的 `all` 行为准（受 opt-in live 反选影响，收集数略高于执行数）——**执行口径见该表**，该表由 `--mode bench --update-docs` 自动回填，本表第三列与之并非同一读数，仅作跨版本可比的历史尺度。
> - **测试 / 主程序行数比**由 0.84:1（6,108 / 7,258）升至 **1.69:1**（184,494 / 109,403，最新发布点），当前工作区为 **1.69:1**（184,494 / 109,403）——测试与文档的投入增速快于主程序，是增长里最显著的结构变化。
> - 「辅助脚本 / 报告模板 / 架构图」显示"新增"含**目录口径差异**：最初版本布局不同（测试平铺为 `src/test_*.py`、模板在 `src/tmpl/`、无 `scripts/*.py`、无 SVG）。按「HTML 模板总数」直接比是 **1 → 22**（若把 Web 首页与图表调试页也计入则 1 → 24）。
> - 「文档」为仓库内全部 `.md` 计数（总数 = 根 2 + `managements` 13 + `manuals` 12 + `plan` 3 + `archive` 183 + `src/` 下 3 个 `.md`〔2 个目录 README + 1 个夹具正文〕，其中 `plan` 为在办设计文档实数；该合计与上方「文档（`.md`）」行一致）；按上方统计表口径的**项目文档**为 CLAUDE.md 1 + 管理文档 13 + 中间设计 3 + 归档 183（不含手册与 README）。分项数字以文件系统实测为准，`plan` 分项随在办任务增减。

### 同口径对照之外的定性差异

| 维度 | 最初版本 | 最新发布 |
|:-----|:---------|:---------|
| 代码组织 | `src/` 平铺 8 个模块 | 分层包：`core` / `providers` / `fetcher` / `analysis` / `report` / `llm` / `cache` / `cli` / `tui` / `web` / `schemas` |
| 测试组织 | 测试与源码同级平铺 | 独立 `src/test/` 树：按域分子目录 + `*_edge.py` 边缘用例文件隔离 + pytest marker 分组 |
| 管理文档 | 5 份（需求 / 测试计划 / 计划 / 变更日志 / 自审记录） | 10 份（新增 目录结构与统计 / 测试覆盖 / 技术设计 / LLM 技术设计 / 开发者指南） |
| 用户手册 | 0 | 10 分册（`manuals/`：上手 / 三种运行模式 / 配置 / 数据源与可靠性 / 报告解读 / FAQ） |
| 版本归档 | 0 | 160 份版本快照（各版本 changelog / 计划 / 自审记录与专题设计） |
| 工程设施 | 2 个启动脚本 | 77 个脚本（测试驱动、10 个一致性守护脚本、LLM 幻觉率评估、测试覆盖计数、连通性诊断、SVG 审查等） |
| 架构图示 | 0 | 5 张 SVG + 7 张界面/报告 PNG（架构图示 + 报告/Web/TUI/CLI 实景截图） |
| 质量门禁 | 无 | 分层门禁：提交前 P0 / 合入前 P1 / 发布前 P2 + 10 个一致性守护脚本 + 三档 CI（含非 UTF-8 locale 可移植性探针） |

## 目录树

```
investor-review/
├── src/                              # 源代码
│   ├── __init__.py                   #   包标记（空文件）
│   ├── python/                       # 主程序代码
│   │   ├── __init__.py               #   包标记（空文件）
│   │   ├── startup_wizard.py         #   首次运行引导向导（检查配置/创建模板/启动模式引导）
│   │   ├── cache/                    # 缓存引擎（TTL/清理/统计/分组/IO）
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── _cleanup.py           #   过期缓存清理（按 TTL 分组删除）
│   │   │   ├── _groups.py            #   缓存分组管理（按前缀路由到不同组）
│   │   │   ├── _io.py                #   缓存序列化/反序列化（JSON/GZip）
│   │   │   ├── _paths.py             #   缓存文件路径生成与管理
│   │   │   ├── _stats.py             #   缓存统计信息（命中率/大小/数量）
│   │   │   ├── _store.py             #   缓存存取核心（get/set/delete/exists）
│   │   │   ├── _negative.py          #   负缓存探针（键族/TTL 取注册表/命中计数/汇总文案）
│   │   │   ├── _ttl.py               #   TTL 策略（含盘中/盘后/非交易日区分）
│   │   │   ├── operations.py             #   缓存操作共享层
│   │   │   ├── _cache_refresh.py   #   缓存刷新族（公共缓存/新闻/基金经理/扩展缓存）
│   │   │   └── services/             # 缓存上层服务
│   │   │       ├── __init__.py       #       子包标记
│   │   │       └── holdings_tracker.py #     持仓快照缓存追踪器
│   │   │
│   │   ├── config/                   # 配置管理
│   │   │   ├── __init__.py           #   子包标记，导出统一配置入口
│   │   │   ├── _config_defaults.py   #   config.json 默认值定义
│   │   │   ├── _config_api.py          #   渠道共享配置 API（默认值查询/持仓与输出路径解析/正式源判定/本地状态标记；三渠道唯一入口）
│   │   │   ├── _config_freshness.py    #   配置文件与生成器模板新旧对比（缺键/缺说明，供自检提示重生成）
│   │   │   ├── _core.py              #   配置加载/保存/校验核心逻辑
│   │   │   ├── _json_patch.py        #   带注释 JSON 顶层键扫描/patch 引擎 + 字段级文本替换
│   │   │   ├── _llm_providers.py     #   LLM 提供程序配置解析
│   │   │   ├── _llm_providers_defaults.py # llm_providers.json 默认值定义
│   │   │   ├── _llm_settings.py      #   llm_settings.json 读取/合并/缓存与 LLM 配置入口
│   │   │   ├── _llm_schema.py          #   llm_settings v2 结构（版本校验/展平反展平/缺省合并/文本 patch）
│   │   │   ├── _llm_pricing.py        #   计价参考（读取/校验/逐模型合并/默认生成器）
│   │   │   ├── _logging.py           #   logger.json 读取/校验/写入（面板与加载共用范围表）
│   │   │   ├── _llm_settings_defaults.py # llm_settings.json 默认值定义
│   │   │   ├── _local_state.py       #   机器本地状态标志读写（首次引导/隐私已读，存 data/state/local_state.json）
│   │   │   ├── _runtime_overrides.py #   运行期配置覆写（CLI --chapter/--anonymize 的进程内叠加，不写盘、不进缓存）
│   │   │   ├── _scheduler.py         #   scheduler 块归一化/严格校验（Web 面板与 CLI config 子命令共用）
│   │   │   ├── _validation.py        #   配置校验函数集
│   │   │   ├── _validation_common.py   #   共用原语（未提及哨兵/分区取值助手/枚举取值表）
│   │   │   ├── _validation_llm.py   #   LLM 域校验（开关/报告深度/板块）
│   │   │   ├── _validation_sections.py   #   章节与内容域校验（章节顺序/基准/对比池/再平衡/纪律/历史）
│   │   │   ├── _validation_scalars.py   #   标量/路径/时长校验（路径/字符串/数值/缓存 TTL/时段/新闻源）
│   │   │   ├── anonymizer.py         #   匿名化模块（4 模式：关闭/代码显示/完全匿名/汇总）
│   │   │   ├── edit_ops.py           #   配置编辑共享层（白名单+值规则+写入分派+写前备份，TUI/Web/CLI 唯一编辑通道）
│   │   │   ├── features.py           #   功能开关注册表（唯一登记点：全量声明的显示名/说明/分组/默认值/产物影响；默认值字典为其派生投影；运行时覆写持久化到 data/config/features.json；按作用域八组划分）
│   │   │   ├── _feature_registry.py #   功能开关注册表与定义（分组常量/FeatureSwitchDef/注册表条目/纯视图）
│   │   │   ├── chapter_registry.py  #   报告章节注册表（[C] 面板唯一来源：四块章节与子项，编号/来源/写键/默认值派生）
│   │   │
│   │   ├── fetcher/                  # 数据获取调度
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── akshare.py            #   akshare 封装层（盈利预测/资金流向/分红）
│   │   │   ├── bond_yield.py         #   无风险利率获取（akshare 国债收益率 + config 手动兜底）
│   │   │   ├── index_valuation.py    #   指数估值历史（乐咕 PE/PB 月频，温度估值因子）
│   │   │   ├── batch.py              #   批量并行调度（BatchDispatcher；间隔限速实现见 core/throttle.py）
│   │   │   ├── chain.py              #   Provider Chain fallback 路由执行 + 对外门面（主→备→过期缓存；子模块符号经此 re-export）
│   │   │   ├── chain_config.py       #   Provider Chain 链定义与覆盖（默认链优先级表 + preferred/exclude 覆盖 + 链健康判定，加载时注入 registry）
│   │   │   ├── chain_diagnostics.py  #   链路失败诊断与命中归属登记（FailureDiagnostics 失败载荷 + 原因短句截断 + 命中归属观测）
│   │   │   ├── chain_incremental.py  #   历史序列增量合并（payload 语义版本闸门 + 按日合并/连续性校验 + 历史 provider 递补调度）
│   │   │   ├── fund.py               #   基金数据获取（净值/业绩排名/持仓）
│   │   │   ├── fund_purchase.py      #   基金申购状态总表取数编排（双链路 + 载荷准入 + 会话复用 + data_status 追踪，单键全量缓存）
│   │   │   ├── fund_fee.py           #   基金申赎费率取数编排（F10 费用页 → akshare 备链 → 过期缓存 → 配置兜底；fetch_fee_index 费率索引）
│   │   │   ├── cassette_checks.py    #   已录制响应 → 当前解析器的绑定表（录制自检与 cassettes --verify 共用）
│   │   │   ├── fund_manager.py       #   基金经理数据获取
│   │   │   ├── history_diff.py       #   历史数据差分同步
│   │   │   ├── factor_catalog_loader.py #  因子目录装载与冻结校验（拒载降级）+ 四类输入备数（日K/指数/估值/财务，逐类型失败入 unavailable 不外抛）
│   │   │   ├── financial_report.py   #   全文本财报取数编排（符号集合 → 元数据 → 章节正文；主源空时切巨潮备源；复用链路缓存/适配器）
│   │   │   ├── index.py              #   指数行情获取（A股/美股，直连 API 不走 Chain）
│   │   │   ├── industry.py           #   行业分类/概念板块数据获取
│   │   │   ├── market_sentiment.py   #   市场情绪/资金热点取数网关（龙虎榜/连板梯队，经 fetch_with_fallback，报告层不直连）
│   │   │   ├── news.py               #   新闻数据获取封装层（聚合器+关键词转发）
│   │   │   ├── price.py              #   行情价格获取（股票/ETF）
│   │   │   ├── quote_adapters.py     #   行情域数据源适配器（腾讯/新浪/东方财富/同花顺，已内置不可关闭）
│   │   │   ├── report_adapters.py    #   财报全文域适配器（两槽：DataSinking 主源 + 巨潮资讯备源，声明式 alias 归一 + source_hint 命名空间隔离）
│   │   │   ├── report_locate.py      #   财报正文关键词定位（跳过目录行；全文兜底与备源章节切片共用）
│   │   │   ├── financial_indicator.py #   财务指标域取数编排（多期指标序列：缓存 + 降级；单期最新记录仍走既有 Provider Chain）
│   │   │   ├── financial_indicator_adapters.py # 财务指标域适配器（akshare 主源，标准字段直出）
│   │   │   └── source_adapter.py     #   数据源适配契约（三段式基类 + 声明式 alias 归一 + 注册表/自检）
│   │   │
│   │   ├── providers/                # 数据源提供商实现
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── utils.py              #   提供商模块共享工具函数（含 run_with_timeout 的 raise_on_failure 上抛开关）
│   │   │   ├── datasink.py           #   DataSinking 全文本财报（A 股；密钥文件/计划感知限速/日配额护栏/连接级重试）
│   │   │   ├── cninfo.py             #   巨潮资讯网财报备源（公开无凭据；公告列表/文种归类/PDF 解析/固定礼貌限速）
│   │   │   ├── hithink.py            #   同花顺金融数据服务（A 股行情/财务/基金/情绪面；凭据/qps 限速/信封错误码/连接级重试）
│   │   │   ├── tencent.py            #   腾讯财经 API（A 股/ETF 实时价）
│   │   │   ├── sina.py               #   新浪财经 API（备用实时价/美股指数）
│   │   │   ├── sina_kline.py          #   新浪财经 API — K 线数据
│   │   │   ├── eastmoney.py          #   东方财富 API（场外基金净值/历史净值）
│   │   │   ├── eastmoney_industry.py #   东方财富行业分类/概念板块
│   │   │   ├── eastmoney_industry_rest.py # 东方财富行业 REST 接口封装
│   │   │   ├── tiantian_base.py        #   天天基金 API — 公共 HTTP 请求解析
│   │   │   ├── tiantian_holdings.py    #   天天基金 API — 基金持仓数据
│   │   │   ├── tiantian_nav.py         #   天天基金 API — 历史净值数据
│   │   │   ├── tiantian_ranking.py     #   天天基金 API — 业绩排名/评级/风险分析
│   │   │   ├── tiantian_purchase.py    #   天天基金 API — 申购状态总表（直连解析 + akshare 备链路 + 载荷形状准入）
│   │   │   ├── tiantian_fund_fee.py    #   天天基金 API — F10 基金费用页（申购/赎回费率表解析 + FEE_SCHEMA 载荷准入）
│   │   │   ├── akshare_extras.py     #   akshare 封装（盈利预测/资金流向/分红）
│   │   │   ├── akshare_financial.py  #   akshare 结构化财务指标（指标域主源；宽表归一为每报告期标准记录）
│   │   │   ├── akshare_news.py       #   akshare 新闻源（财新网/CCTV）
│   │   │   ├── sina_news.py          #   新浪财经新闻源
│   │   │   ├── eastmoney_news.py     #   东方财富新闻源
│   │   │   ├── cls_news.py           #   财联社新闻源（签名鉴权，默认关闭）
│   │   │   ├── wallstreetcn_news.py  #   华尔街见闻新闻源
│   │   │   ├── news_aggregator.py    #   新闻聚合器（多源合并去重）
│   │   │   ├── news_dedup.py         #   新闻标题去重
│   │   │   ├── news_dedup_rules.py   #   去重规则原语（阈值/模板词表/归一化/实体 bigram/相似度/指纹）
│   │   │   ├── news_dedup_anchor_store.py #   锚点存储层（分片 gzip 读写/路径与汇总体积/原子替换）
│   │   │   ├── news_dedup_anchor_policy.py #  锚点策略层（保留期/体积目标/同源采样/裁剪编排）
│   │   │   ├── _news_dedup_tables.py   #   去重规则表（停用二元组/对立词对/事件分组等纯词表）
│   │   │   ├── news_correlator.py    #   新闻与持仓关联分析
│   │   │   ├── news_keywords.py      #   新闻关键词提取与匹配
│   │   │   └── news_sources.py       #   新闻源注册与配置
│   │   │
│   │   ├── analysis/                 # 业务计算层（独立无依赖，不导入 report/）
│   │   │   ├── __init__.py                    #   包标记；导出 check_liquidity 等
│   │   │   ├── _fee_estimation.py             #   组合综合费率估算
│   │   │   ├── _factor_formulas.py            #   因子公式纯计算原语（技术族逐因子序列 + 基本面标量分发，无 I/O）
│   │   │   ├── _math_utils.py                 #   数学工具函数（Beta/t-分布）
│   │   │   ├── _silence.py                    #   再平衡静默期管理
│   │   │   ├── action_advisor.py              #   行动建议（再平衡信号+交易纪律+调仓建议+收益归因 → action_data）
│   │   │   ├── alignment_correction.py        #   口径修正因子计算（估值偏差校准）
│   │   │   ├── circuit_breaker_wrapper.py     #   指标级断路包装器
│   │   │   ├── drawdown_warning.py            #   回撤历史分位预警
│   │   │   ├── drawdown_events.py             #   回撤事件识别（新高/回撤起止/幅度）
│   │   │   ├── style_factor_regression.py     #   风格因子回归（价值/成长/质量三因子 MVP，OLS 回归）
│   │   │   ├── industry_beta.py               #   行业 Beta 分析（纯计算：暴露占比 + 逐行业一元 OLS，复用 factor_exposure）
│   │   │   ├── factor_evaluator.py            #   因子目录计算编排（池构造：直接持仓∪穿透 A 股 → 逐因子池内横截面 → 中性相对与评级，全链 fail-soft）
│   │   │   ├── correlation.py                 #   持仓相关性矩阵（Pearson 相关/显著性/下三角矩阵）
│   │   │   ├── benchmark_excess.py            #   风险调整超额计算（IR/TE/年化超额/12·24 月胜率/滚动 250 日超额 → risk_adjusted_excess_data）
│   │   │   ├── crisis_annotation.py           #   危机区间标注（2015/2018/2020/2022/2025 静态表 + 区间回撤/恢复 + 回放态指数层 → crisis_annotation_data）
│   │   │   ├── prosperity_framework.py        #   景气度框架诊断（六维评分卡：景气/ROE 弹性/全球比较/流动性/集中度与周期拼接/业绩回撤；常规功能）
│   │   │   ├── prosperity_scoring.py     #   景气度评分内核（配置默认值 + 权重常量 + 六维打分器）
│   │   │   ├── prosperity_inputs.py    #   评分输入（配置默认值/板块权重聚合/权重与阈值常量/基金类型回退）
│   │   │   ├── prosperity_signals.py   #   景气度框架本地信号提取原语（持仓/快照/基准 → 数值信号，零网络）
│   │   │   ├── fx_exposure.py                 #   外汇敞口分析（港股/QDII 汇率风险）
│   │   │   ├── financial_indicator_extract.py #   财务指标全文解析（DataSinking 压平正文 → 标准指标：锚点/取值窗口/精度模式/合理性校验）
│   │   │   ├── financial_statement_derive.py # 三张合并报表 → 标准财务指标记录（纯派生：比率派生/同比/报告期季末归一）
│   │   │   ├── market_sentiment.py       #   市场情绪纯装配（龙虎榜/连板梯队 ∩ 持仓与穿透标的 → 事件行；只按代码命中）
│   │   │   ├── financial_indicator.py         #   财务指标派生（质量档四维启发式/年度趋势/当前 PE·PB/趋势点）
│   │   │   ├── liquidity.py                   #   流动性风险评估（场内品种变现天数计算）
│   │   │   ├── market_temperature.py          #   市场温度（价格分位+均线偏离+波动率三因子合成温度计，无仓位指令）
│   │   │   ├── metrics.py                     #   量化指标计算（夏普/卡玛/HHI/Beta 等，聚合门面）
│   │   │   ├── monthly_returns.py             #   月度收益日历（日频 bars 按月聚合，as-if 口径、双口径并排预留）
│   │   │   ├── metrics_returns.py             #   收益类指标子模块（日收益率口径/数值清理/收益回撤）
│   │   │   ├── metrics_risk.py                #   风险类指标子模块（集中度/胜率/换手/风险贡献/波动率/Beta）
│   │   │   ├── portfolio_evolution.py         #   组合演进（多快照聚合 → evolution_data）
│   │   │   ├── rebalance.py                   #   再平衡信号计算（品种偏离度/调整建议）
│   │   │   ├── _rebalance_deviation.py #   偏离度信号（目标偏离/股债偏离/单品种超限/信号汇总 + 分类权重与误报保护）
│   │   │   ├── rebalance_advisor.py           #   调仓建议可行化层（份额取整一手/费用估算/现金缓冲/优先级 → rebalance_advice）
│   │   │   ├── purchase_feasibility.py        #   申购可行性判定（受限索引形参 → 天数估算/阈值/提示话术，What-if 注入面）
│   │   │   ├── return_attribution.py          #   收益归因（TOP5 品种贡献占比/正负分列/净额合计 → attribution，提示词段落与行动建议章表格共用）
│   │   │   ├── cost_flow.py                   #   成本流水分析（XIRR 资金加权收益/成本分档/分红累计 → cost_flow_data）
│   │   │   ├── cost_position.py              #   持仓成本区间位置纯计算（成本价近 20/260 交易日价格区间百分位/clamp/中性值）
│   │   │   ├── scenario.py                    #   情景分析（Beta 推导 → 分档市场情景预期变动）
│   │   │   ├── simple_rebalance.py            #   极简再平衡（单品种超15%警戒线）
│   │   │   ├── snapshot_diff.py               #   快照差异摘要（去重后最近两快照对比：新增/移除 + HHI 变化 + 超限项 → snapshot_diff_data）
│   │   │   ├── holding_change_events.py        #   持仓变动事件抽取（滚动快照逐期差分 → 变动事件清单 + 窗口/样本契约 → holding_change_data）
│   │   │   ├── event_window_impact.py #   事件窗对照纯计算（事件日→交易日映射/T±N 切窗/LOCF 对齐/超额与方向一致标记，零 I/O）
│   │   │   ├── schedule_replay.py #   调仓纪律回放纯计算（规则契约/交易日对齐/LOCF 归一/逐期回放与指标拼装，零 I/O）
│   │   │   ├── holding_change_metrics.py       #   持仓变动纯计算（频率/结构计数/贡献分解/意图对账 + 账户结构重排识别）
│   │   │   ├── tail_risk.py                   #   尾部风险统计（历史模拟法 VaR95/99 + 最大单日跌幅 + 连续下跌 + 恢复天数 → tail_risk_data）
│   │   │   ├── trade_discipline.py            #   交易纪律引擎（止盈/止损/回撤触发检测，复用 _silence 静默机制）
│   │   │   ├── valuation_percentile.py        #   估值分位（东财 push2 当前 PE/PB + 价格分位代理，显式标注局限）
│   │   │   ├── benchmark_index_resolver.py     #   基准指数映射（目标持仓 → 基准指数：配置覆盖/持仓基准文本反查/宽基默认，纯映射零 I/O）
│   │   │   ├── fee_schedule_model.py           #   申赎费率表模型（F10 费用表文本解析/单档与配置构建/金额与交易日持有期选档）
│   │   │   ├── trade_cost_model.py             #   调仓交易成本模型（FIFO 快照批次逐批判档加权 + 腿级费用聚合 → 成本契约，纯计算）
│   │   │   ├── whatif.py                      #   调仓 What-if 模拟（双持仓成本口径对比）
│   │   │   └── whatif_backtest.py             #   调仓 What-if 时序回测（纯计算：生效日折算/序列对齐/5 指标）
│   │   │
│   │   ├── llm/                      # LLM 智能分析
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── api.py                #   LLM API 主入口（自动路由 provider）
│   │   │   ├── api_base.py           #   LLM API 基类（请求/重试/流式）
│   │   │   ├── _api_responses.py   #   LLM 响应解析（截断检测/内容提取/token 用量/成功响应装配）
│   │   │   ├── circuit_breaker.py    #   熔断器（连续失败/冷却恢复）
│   │   │   ├── compliance.py         #   合规声明集中注入（幂等叠加研究辅助定位约束，单一漏斗覆盖全模块）
│   │   │   ├── cost_forecast.py    #   事前费用预估与日预算（区间预估 + 日费用硬闸）
│   │   │   ├── cost_tracker.py       #   Token 成本跟踪与预算管理（会话级 Token 守卫）
│   │   │   ├── depth_profile.py      #   报告深度档位（档位表唯一事实来源；只收窄模块集合与新闻规模，不进提示词正文）
│   │   │   ├── self_review.py        #   生成后自检（模型层复核；运行作用域载体 + 固定非质量保证尾注）
│   │   │   ├── holding_change_review.py #   持仓变动复盘归因（章内 LLM 归因块；编排层串行入口 + 归因生成器 + 窗口信号对账块 + 失败原因登记）
│   │   │   ├── fact_checker/         # LLM 事实锚定校验器（数值/品种/排名一致性校验）
│   │   │   │   ├── __init__.py       #       子包标记，re-export run_fact_check 等公开函数
│   │   │   │   ├── _constants.py     #       关键词词表/指数代码集/默认容差
│   │   │   │   ├── _context.py       #       语境检测（回撤/变化率/贡献度/仓位/假设/建议）
│   │   │   │   ├── _corrections.py   #       数值自动修正
│   │   │   │   ├── _numerical.py     #       数值一致性检查器
│   │   │   │   ├── _patterns.py      #       正则模式
│   │   │   │   ├── _ranking.py       #       排名正确性检查器
│   │   │   │   ├── _runner.py        #       run_fact_check 统一入口（全量校验 + 自动修正）
│   │   │   │   ├── _symbols.py       #       品种存在性检查器
│   │   │   │   └── _utils.py         #       HTML 剥离/句子拆分/持仓映射/组合数值
│   │   │   ├── failure_reasons.py    #   LLM 模块失败原因常量（FAIL_REASON_* + LLM_MODULE_FAILURE，自 prompts_core 域下沉）
│   │   │   ├── fallback.py           #   LLM 故障降级模板（所有模块失败时提供占位内容，防止报告空白）
│   │   │   ├── fingerprint.py        #   缓存指纹（请求去重，避免重复调用）
│   │   │   ├── force_scope.py        #   模块级强刷范围解析（可强刷键清单/粒度优先归一/未知键校验，三端与共享层共用）
│   │   │   ├── generators.py         #   生成门面（辩论 pro/con/合成 + 自检 + 持仓变动归因生成器；单例生成函数下沉 generators_singletons 后 re-export）
│   │   │   ├── generators_news.py    #   新闻分析提示词生成
│   │   │   ├── generators_orchestrator.py # LLM 批量编排门面（缓存预检 + 主编排入口，re-export 分发子模块）
│   │   │   ├── generators_singletons.py #   单例生成函数（global_macro/expert_review/health_check/penetration_deep，自 generators 域下沉，门面再导出；测试 patch 解析点）
│   │   │   ├── _llm_dispatch.py        #   worker 装配与线程池并发分发（_MODULE_FNS 映射/进度回调/辩论路由）
│   │   │   ├── _api_claude.py         #   Claude API 调用实现
│   │   │   ├── _api_gemini.py         #   Gemini API 调用实现
│   │   │   ├── _api_openai.py         #   OpenAI API 调用实现
│   │   │   ├── _hallucination_filter.py #   LLM 幻觉过滤
│   │   │   ├── _llm_news_correlation.py #  新闻关联责任单元（模块级结果缓存/闭包/安全直调，聚合门面 re-export）
│   │   │   ├── markdown.py           #   LLM 输出 Markdown 解析/格式化
│   │   │   ├── module_fingerprint.py #   各 LLM 模块缓存指纹唯一事实来源（预检侧与写侧同源）
│   │   │   ├── fingerprint_baseline.py #   跨进程指纹基线（各模块键+组件哈希落盘，供换键归因）
│   │   │   ├── pacing.py             #   端点级节流/并发治理（pacing 声明解析 + PacingGate 施加点 + 429 诊断建议）
│   │   │   ├── observation.py        #   运行观测汇聚（重试/节流等待、provider 命中与降级、缓存命中，按运行归集入 perf 记录）
│   │   │   ├── pricing.py            #   Token 计费与用量统计
│   │   │   ├── prompts.py            #   提示词模板库
│   │   │   ├── prompts_action.py     #   LLM 分析模块提示词构造（全局政经/智囊团复盘/体检/穿透）
│   │   │   ├── prompts_core.py       #   提示词门面（系统提示常量/辩论 synthesis 构建 + 失败原因/数据块/复盘自审三域再导出）
│   │   │   ├── prompts_data_blocks.py #   上下文数据块（管线差异/数据降级/收益归因/竞争语境/再平衡/概念板块 + 格式化辅助，自 prompts_core 域下沉）
│   │   │   ├── prompts_review.py     #   自审与持仓变动复盘提示词（_SYSTEM_* + 构建器，自 prompts_core 域下沉）
│   │   │   ├── prompts_signals.py    #   信号预消化（资金流方向标注/算法评级信号块/缓存后缀）
│   │   │   ├── prompts_tables.py     #   提示词表格模块（持仓/穿透/场景分析格式化与摘要构造）
│   │   │   ├── rate_caliber.py       #   收益率口径标签单一声明点（持仓/组合/区间标签 + 提示词文本版本进指纹）
│   │   │   ├── session.py            #   LLM 会话管理（上下文窗口/历史）
│   │   │   ├── skeleton.py           #   LLM 内容骨架生成（结构化输出引导）
│   │   │   ├── _batch_mode.py        #   LLM 批量处理（缓存预检/并行调用/合并）
│   │   │   └── strategy.py           #   Provider 多链切换策略引擎
│   │   │
│   │   ├── schemas/                  # 数据模型定义
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── datasource_fields.py  #   数据源标准字段记录（按数据域登记，类型注解即缺省语义）
│   │   │   ├── history.py            #   历史净值/行情数据模型
│   │   │   ├── factor_catalog.py     #   因子目录冻结清单（五来源族 + 中性点 + 字段类型路由）
│   │   │   └── replay_schedule.py     #   调仓纪律回放规则契约（月度定期/阈值偏离解析、权重校验、版本与指纹）
│   │   │
│   │   ├── qa/                      # 报告对话式追问子包（零取数上下文 + 会话服务）
│   │   │   ├── __init__.py          #   子包标记（出口：ask_report_qa / extract_report_qa_context）
│   │   │   ├── context.py           #   报告 HTML → 追问上下文与持仓基线（锚点单源/分层截断/生成条件声明）
│   │   │   ├── error_codes.py      #   追问错误码单一来源（会话/上下文产出，Web 状态映射/TUI 退出策略同源引用）
│   │   │   ├── session.py           #   会话表（轮数/输入上限/用量独立记账/事实核对/Markdown 渲染）
│   │   │   └── telemetry.py         #   追问埋点与效果汇总（账本追加/转正判据/doctor 上屏文本；不落问题正文）
│   │   │
│   │   ├── report/                   # 报告生成引擎
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── benchmark.py          #   业绩基准配置与匹配
│   │   │   ├── excel_generator.py    #   Excel 报告生成总控
│   │   │   ├── excel_module_loader.py #  Excel 页签模块动态加载
│   │   │   ├── excel_sheet_factory.py #  Excel 页签工厂（按配置创建页签）
│   │   │   ├── excel_content_sheets.py #  Excel 内容页签（持仓明细/汇总）
│   │   │   ├── excel_market_data.py  #   Excel 行情数据页签
│   │   │   ├── excel_news_warning.py #   Excel 新闻页签
│   │   │   ├── excel_fund_deep_analysis.py  #   Excel 基金深度分析页签（基金深度分析：经理/重合度/集中度/风格/因子暴露）
│   │   │   ├── excel_llm_usage.py    #   Excel LLM 用量统计页签
│   │   │   ├── excel_writer.py       #   Excel 底层写入器（openpyxl 封装）
│   │   │   ├── experimental_notice.py #  实验功能清单语句单源（HTML 页脚 / Excel 用量页签 / Excel 汇总页脚三处共用）
│   │   │   ├── _debate_utils.py      #   辩论模式检测工具函数（共享 html/excel）
│   │   │   ├── html_writer.py        #   HTML 报告主写入器（聚合门面）
│   │   │   ├── html_writer_status.py   #   数据状态块装配（自述块/降级状态安全构建/时间串/三处状态区块）
│   │   │   ├── html_writer_nav.py    #   章节可见性 + 目录分组导航（board 层×data 层两层可见性）
│   │   │   ├── section_block_extraction.py #   章节区块提取（HTML partial 三源规则 / Excel write_block_title 调用点，归一化与注册表同口径）
│   │   │   ├── html_writer_display.py #  数据契约展示映射（fund_flow/温度/估值 → 模板友好 dict）
│   │   │   ├── html_writer_assets.py #   Chart.js JS 资产复制/内嵌（复制到报告目录 + 保存前内嵌为行内脚本，单文件自包含）
│   │   │   ├── html_builders.py      #   HTML 各区块构建器
│   │   │   ├── html_renderers.py     #   HTML 渲染管线
│   │   │   ├── html_jinja_env.py     #   Jinja2 模板环境配置
│   │   │   ├── html_save.py          #   HTML 保存/导出
│   │   │   ├── penetration.py        #   穿透持仓分析（嵌套基金）
│   │   │   ├── penetration_sheet.py  #   穿透分析 Excel 页签
│   │   │   ├── fund_roe_estimate.py  #   基金重仓股 ROE 加权估算（景气度框架②维基金层扩展，阶段一前十大重仓口径）
│   │   │   ├── pipeline_data_builder.py # 管线数据上下文组装
│   │   │   ├── market_value.py       #   市值计算与盈亏分析
│   │   │   ├── category.py           #   持仓分类领域函数（分类/档位/股息/数据状态）
│   │   │   ├── cost_position.py      #   持仓成本区间位置数据契约（复用行情历史链取数 + 编排装配/可见性/单元格文案/口径脚注）
│   │   │   ├── holdings_detail_sheet.py # 持仓明细与分类 Excel 页签（区块①市值明细 + 区块②分类汇总）
│   │   │   ├── _holdings_detail_blocks.py   #   页签分区块写入器（市值/分类区块 + 行值与格式辅助）
│   │   │   ├── chart_data_builder.py #   Chart.js 6 图数据集预处理器
│   │   │   ├── fund_performance.py   #   基金业绩分析（排名/回撤/超额收益）
│   │   │   ├── _fund_rating.py         #   评级内核（评级判定/超额修正/收益率与排名格式化）
│   │   │   ├── fund_candidate.py     #   候选基金比较（基金业绩分析章候选比较子表数据构建，candidate_compare 默认关）
│   │   │   ├── fund_concentration.py #   基金持仓集中度分析
│   │   │   ├── fund_manager_analysis.py # 基金经理分析
│   │   │   ├── position_overlap.py   #   基金持仓重叠分析（重合度计算引擎）
│   │   │   ├── fund_style_base.py       #   基金风格基础（常量/快照/PECity阈值）
│   │   │   ├── fund_style_classify.py   #   基金风格分类计算（push2→Tencent→兜底降级）
│   │   │   ├── fund_style_report.py     #   基金风格漂移检测与全基金分析入口
│   │   │   ├── style_factor_sheet.py  #   风格与因子分析 Excel 页签（一章三区块：风格表 + 因子回归 + 行业 Beta 子表）
│   │   │   ├── evolution_sheet.py    #   组合演进 Excel 页签（总市值/HHI/TOP 变迁）
│   │   │   ├── holding_change_panel.py #   持仓变动复盘面板（契约装配 + 双端单源视图 + Excel 页签写入 + 提示词块渲染）
│   │   │   ├── event_impact_panel.py #   事件窗对照表数据编排（新闻→event_item 组装/注入式取数/降级计数 → event_impact_data）
│   │   │   ├── schedule_replay_panel.py #   调仓纪律回放面板（回放契约装配 + 双端单源视图 + Excel 页签写入 + 回放引用提示词块）
│   │   │   ├── financial_indicator.py # 持仓基本面章区块①数据装配（多期指标 + 质量档 + 趋势 + 当前 PE/PB，pipeline_data 键契约登记）
│   │   │   ├── purchase_status.py # 申购限购状态展示装配与展示单源（契约构建/时效分档/单元格文案/口径脚注，pipeline_data 键契约登记）
│   │   │   ├── financial_report_digest.py # 持仓基本面章区块②数据装配（A 股标的 → 最新年报章节摘要）
│   │   │   ├── market_sentiment.py       #   市场情绪取数与装配（开关 market_sentiment；缺口即降级契约；取数带 1h 缓存）
│   │   │   ├── fundamental_snapshot_sheet.py # 持仓基本面 Excel 页签（区块①财务指标 + 区块②财报摘要）
│   │   │   ├── action_sheet.py       #   行动建议 Excel 页签（再平衡信号/交易纪律/调仓建议/收益归因）
│   │   │   ├── decision_record.py    #   决策复盘·确定性载体登记（再平衡卖出/调仓卖出建议，仅带基线价入账，同日去重）
│   │   │   ├── decision_llm_capture.py # 决策复盘·LLM 操作建议表结构化解析（表头识别→逐代码方向登记，同日去重）
│   │   │   ├── decision_settlement.py #  决策复盘·结算服务（到期 pending 用真实后续行情结算，方向命中/超额 alpha）
│   │   │   ├── decision_review_block.py # 决策复盘·「历史决策复盘」区块数据组装（available/免责声明/命中率/近期明细）
│   │   │   ├── signal_record.py      #   确定性信号沉淀适配器（各信号类型评级→账本记录，含实时-非实时来源标注，开关 deterministic_signal）
│   │   │   ├── portfolio_history.py  #   组合历史净值走势分析
│   │   │   ├── portfolio_history_drawdown_sheet.py # 组合历史走势与回撤 Excel 页签（一章五区块：走势表 + 回撤矩阵 + 危机区间标注 + 月度收益日历 + 风险调整超额）
│   │   │   ├── position_structure_sheet.py # 持仓结构与集中度 Excel 页签（一章三区块：重合度 + 相关性 + 集中度）
│   │   │   ├── _history_quality.py   #   历史走势数据质量校验
│   │   │   ├── history_snapshot.py   #   持仓快照管理（保留 180 天）
│   │   │   ├── holdings_freshness.py #   基金持仓报告期时效判定（完整季度数口径 + 陈旧阈值）
│   │   │   ├── _snapshot.py          #   快照与历史数据（持仓快照/环比差异/组合历史走势）
│   │   │   ├── summary_highlights.py #   摘要区本期要点派生（快照 diff 单源 → 指标环比行 + 关键变化 Top N，开关 summary_highlights）
│   │   │   ├── news_correlation.py   #   新闻与持仓关联分析报告
│   │   │   ├── orchestrator.py       #   报告编排共享层（TUI/CLI 共用，聚合门面）
│   │   │   ├── _orchestrator_data.py   #   数据装配与派生计算（prepare_report_data + compute_* 五域 + 估值分位取值）
│   │   │   ├── history_policy.py     #   历史走势获取策略解析（off/auto/prompt 单一事实来源，三渠道共用）
│   │   │   ├── _report_factor_metrics.py # 风格因子/行业 Beta 计算族（持仓K线路由 + 因子回归 + 行业Beta）
│   │   │   ├── _report_aux_metrics.py #  辅助指标编排（市场温度 + 持仓相关性矩阵）
│   │   │   ├── _llm_news.py          #   LLM/新闻并行获取（线程池提交/收集/报告）
│   │   │   ├── _report_generation.py #   报告生成实现（both/full 两种路径，聚合门面）
│   │   │   ├── _generation_shared.py   #   两条生成路径共用步骤（LLM 上下文记录与按报告用量基线 delta）
│   │   │   ├── _run_scope.py           #   报告运行边界（本轮降级事件/自检载体重置 + LLM 用量基线）
│   │   │   ├── _generation_both.py     #   both 路径编排（HTML+Excel，不含 LLM）
│   │   │   ├── _generation_full.py     #   full 路径编排（+ LLM 章节与实验挂载点）
│   │   │   ├── _report_output.py         #   full 路径 HTML/Excel 产物落盘包装（章节顺序/开关透传/失败登记/标志位回填）
│   │   │   ├── _experimental_seams.py #  管线实验挂载点（守护语义单份实现 + 按需导入被调子模块）
│   │   │   ├── _report_health.py     #   数据源健康检查（后台并行启动/结果收集持久化）
│   │   │   ├── _report_helpers.py    #   管线辅助函数（轻量行情/演进与快照差异注入/完整性校验/both 明细子集）
│   │   │   ├── _holding_detail_rows.py #  持仓明细行单一装配点（编排/行动建议两路径共用 10 字段 + 行情三字段按需）
│   │   │   ├── _full_risk_metrics.py #   full 路径全量量化指标装配（历史走势+指标+情景分析+口径修正）
│   │   │   ├── _chart_dataset_factory.py # Chart.js 数据集构建（Flag 开关+雷达子开关收集+异常兜底）
│   │   │   ├── privacy_notice.py     #   隐私提示模块（首次运行提示 + 报告脚注）
│   │   │   ├── summary.py            #   报告摘要生成
│   │   │   ├── summary_llm_usage.py  #   LLM 使用情况摘要
│   │   │   ├── data_status.py        #   数据质量状态（缺失/过期/降级标记）
│   │   │   ├── data_source_matrix.py #   数据源可用性矩阵 + 数据源说明表（实际链路/用途/计费/凭据）
│   │   │   ├── data_quality_sheet.py #   数据质量仪表盘页签写入（源健康+品种覆盖，开关 data_quality）
│   │   │   ├── downsample.py         #   服务端下采样（日频→周/月聚合）
│   │   │   ├── llm_content.py        #   LLM 分析结果写入报告（块级 HTML 分段 + 事实校验摘要分块着色）
│   │   │   ├── llm_module_info.py    #   LLM 模块信息构建（共享函数）
│   │   │   ├── llm_quality.py        #   LLM 输出侧质量分级（A~F 评级 + 低评级内容头部「内容质量提示」横幅，常规开关 module_quality_gate）
│   │   │   ├── progress.py           #   报告生成进度跟踪
│   │   │   ├── cli_progress.py         #   CLI 进度报告器（CliProgressReporter）
│   │   │   ├── run_integrity.py     #   生成运行一致性守卫（guard_run 中断收口/临时产物清扫/status=interrupted 落盘）
│   │   │   ├── whatif_cost_panel.py   #   调仓 What-if 交易成本面板装配（成本本体 + 成本前/后差 + 基准三线；开关 whatif_trade_cost 消费点）
│   │   │   ├── whatif_sheet.py       #   调仓 What-if Excel 页签（摘要/分类/变动明细/回测/交易成本对比）
│   │   │   ├── whatif_writer.py      #   调仓 What-if 报告输出编排（Excel+HTML，含 Chart.js 资产复制/内嵌）
│   │   │   ├── whatif_operations.py  #   调仓 What-if 操作共享层（CLI/TUI 共用的业务链）
│   │   │   └── styles.py             #   Excel 样式定义
│   │   │
│   │   ├── core/                     # 核心基础设施
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── _phase_timeout.py     #   数据获取阶段超时管理
│   │   │   ├── ansi_colors.py        #   ANSI 颜色常量（终端输出着色）
│   │   │   ├── artifacts.py          #   报告产物定位与系统程序打开（三渠道共用；收集/打开失败降级）
│   │   │   ├── atomic_write.py       #   原子整文件写入原语（唯一实现，mkstemp + os.replace；jsonl_store/熔断状态/持仓快照/静默期/断路状态/降级状态/功能开关覆写共用，成败如实返回布尔）
│   │   │   ├── cassette.py           #   数据源记录-回放引擎（真实响应体离线录制/回放，经传输工厂注入，不联网）
│   │   │   ├── check_sources.py      #   数据源健康检查命令处理器（CLI/报告共享）
│   │   │   ├── circuit_breaker.py    #   统一断路器网关（Provider + LLM 熔断状态查询）
│   │   │   ├── code_utils.py         #   证券代码/类型判定工具（派生量由 code_symbols.py 单一实现）
│   │   │   ├── code_symbols.py     #   派生量（交易所前后缀归一 / FMP·东财·cninfo 符号与参数 / 市值粗估；前缀常量真值）
│   │   │   ├── costs.py             #   LLM 费用「币种 → 金额」桶读写（perf/core 与 llm/report 共用，避免分层倒置）
│   │   │   ├── completion_notify.py  #   任务完成通知（notify 三通道分发：webhook/邮件/桌面，失败必发成功可选，未配置静默跳过）
│   │   │   ├── constants.py          #   全局常量/版本号
│   │   │   ├── error_hints.py        #   异常→用户提示唯一映射（三渠道同一句话；类型优先于关键词）
│   │   │   ├── http_client.py        #   HTTP 客户端（请求/重试/超时）
│   │   │   ├── jsonl_store.py        #   原子追加 + 容错读取 JSONL 原语（perf/decision_ledger/signal_ledger 共用）
│   │   │   ├── json_comments.py      #   JSONC 注释剥离叶子模块（配置/core 读取统一入口，无私有别名）
│   │   │   ├── num_utils.py          #   数值归一原语（safe_num/strict_num/finite_or/is_finite_number/format_size，非有限值防线与尺寸格式化收敛点）
│   │   │   ├── retry.py              #   重试与退避唯一原语（策略/瞬时判据/执行器，链路与各 provider 共用）
│   │   │   ├── throttle.py           #   按名最小间隔节流唯一原语（数据/调度/LLM 三层共用，含抖动算式）
│   │   │   ├── logger.py             #   日志模块（文件+控制台，自动轮转）
│   │   │   ├── log_reader.py         #   结构化日志读取（read_log/tail_log/parse_log，CLI/TUI/Web 共享）
│   │   │   ├── market_hours.py       #   交易时段判断（A股/港股/QDII）
│   │   │   ├── models.py             #   数据模型（持仓/行情/基金/新闻）
│   │   │   ├── system_info.py        #   系统状态组装与展示原语（Web 状态卡/TUI 首页共用：熔断/路由/凭据回填/匿名化标签）
│   │   │   ├── holding_status.py     #   品种级数据状态标注（品种覆盖诊断，position_status）
│   │   │   ├── data_freshness.py     #   数据可信度诊断（新鲜度分类 + 单日跳变检测，data_freshness）
│   │   │   ├── datasource_credential.py # 数据源凭据声明与就绪判定（CredentialSpec 注册表/缺失判定/可读指引/就绪矩阵；已内置不可关闭，凭据值永不落日志与报告）
│   │   │   ├── doctor.py             #   系统自检（环境/配置/目录/功能开关/数据源适配/数据源凭据/数据源/日志与缓存八组 + 修复建议；零重依赖、自身永不抛异常）
│   │   │   ├── doctor_logs.py        #   自检「日志与缓存」组探针（日志级别/体积与 DEBUG 占比/去重锚点/运行台账；只读）
│   │   │   ├── decision_header.py    #   决策头解析（决策词归一/优先级/代码提取/结构化决策头/缓存后缀），无 report/llm 依赖
│   │   │   ├── decision_ledger.py    #   决策跨期反思账本（事件 JSONL 持久化/结算折叠/教训区块+缓存指纹/开关），无 report/llm 依赖
│   │   │   ├── experiment_stats.py   #   实验功能使用统计（启用计数/最近启用日期，data/state/experiment_stats.json；为转正/撤销决策提供客观数据）
│   │   │   ├── signal_ledger.py      #   确定性信号沉淀账本（各信号类型评级登记/幂等去重/实时-非实时标签折叠/摘要+缓存指纹/开关 deterministic_signal），无 analysis 依赖
│   │   │   ├── perf.py               #   性能收集（PerfCollector 计时 + 数据源健康检查持久化）
│   │   │   ├── provider_registry.py  #   数据源注册中心（熔断器/会话缓存）
│   │   │   ├── trading_calendar.py   #   交易日历原语（唯一实现：交易日判定/最近及前一交易日/交易日区间计数，akshare 日历缓存；各层共用，report/market_value.py re-export 兼容面）
│   │   │   ├── text_safety.py        #   文本安全边界（孤立代理项净化：合法代理对折叠、孤立项→U+FFFD；LLM 请求/响应与用户问题统一过关）
│   │   │   ├── reader.py             #   持仓 xlsx 文件读取
│   │   │   ├── computation_registry.py #   计算模块注册表（纯计算/分析模块元信息，registry.py re-export 保持访问面）
│   │   │   ├── section_block_registry.py #   章节区块注册表（双端章内区块清单单源：html/excel 归一化名 + 载体，区块契约真值）
│   │   │   ├── data_registry.py     #   数据模块注册表（配置键/缓存前缀/默认 TTL/LLM 设置键派生，registry.py 门面再导出）
│   │   │   ├── report_section_registry.py # 报告章节注册表（章节目录序/导航分组/页签名称派生，registry.py 门面再导出）
│   │   │   └── registry.py           #   中央注册表门面（两域子模块 + 计算/区块注册表单入口再导出，导入面不变）
│   │   │
│   │   ├── cli/                      # CLI 命令行模式入口
│   │   │   ├── __init__.py           #   子包标记，re-export cli 符号
│   │   │   ├── __main__.py           #   python -m 入口
│   │   │   ├── _handlers.py          #   子命令处理器 + 持仓读入辅助 + 退出码契约（_EXIT_*）
│   │   │   ├── _parser.py            #   argparse 解析器构建与 type 回调
│   │   │   └── cli.py                #   主入口门面：main/run_cli + 命令行功能开关应用 + re-export
│   │   │
│   │   ├── tui/                      # TUI 交互模式入口
│   │   │   ├── __init__.py           #   子包标记
│   │   │   ├── __main__.py           #   python -m 入口
│   │   │   ├── handlers_cache.py     #   缓存管理命令处理器
│   │   │   ├── handlers_config.py    #   配置管理命令处理器（含 [G] 全局设置七项：目录与文件 / LLM / 基准与脱敏 / 索引；[C]/[S] 面板只留菜单入口与共享写路径 _apply_edit）
│   │   │   ├── handlers_qa.py       #   报告对话式追问入口（[Q] 菜单/文本输入循环，同源 qa/session）
│   │   │   ├── handlers_log.py       #   日志可视化命令处理器（查看日志/数据源健康历史/系统自检）
│   │   │   ├── handlers_report.py    #   报告生成命令处理器
│   │   │   ├── handlers_report_chapters.py # [C] 报告章节显隐面板本体（四块章节 + 智囊团生成子项）
│   │   │   ├── handlers_whatif.py    #   调仓 What-if 模拟命令处理器（对比两份持仓生成独立报告）
│   │   │   ├── text_layout.py        #   终端排版原语（宽度/折行/截断/悬挂缩进/盒线面板/终端列数探测）
│   │   │   ├── report_artifacts.py   #   报告产物定位与单键打开（收尾产物清单，默认 N）
│   │   │   ├── tui.py                #   主循环入口
│   │   │   ├── tui_handlers.py       #   键盘/事件处理
│   │   │   ├── tui_keys.py           #   终端键盘输入封装
│   │   │   ├── status_line.py        #   页头状态行（本地单源取数/TTL 记忆化/异常段附动作提示/逐项降级为 —）
│   │   │   ├── switch_panel.py       #   [S] 面板响应式排版（宽/中/窄三档版面和列对齐，只排版不取数）
│   │   │   ├── panel_runtime.py      #   TUI 统一交互运行时（NavState/PanelItem/panel_loop，列表面板导航态与派发控制流单源）
│   │   │   ├── prompt_text.py   #   提示语模板（提示四成分唯一产出通道：动作+示例 · 默认项 · 帮助入口 · 返回键；`?` 帮助文案）
│   │   │   ├── handlers_switch.py   #   [S] 章节内容面板本体（run_content_options_panel 主循环：按注册表六组分块 + match_switch_item/show_switch_detail）
│   │   │   ├── handlers_llm_providers.py  #  [M] 多链优先级面板（按链序展示 + 交换两编号；写盘经共享 _apply_edit）
│   │   │   └── tui_menu.py           #   菜单系统（菜单定义/门控/渲染）
│   │   │
│   │   └── web/                      # 轻量 Web 模式入口（浏览器内上传/生成/预览/下载）
│   │   │   ├── __init__.py           #   子包标记，re-export main/create_app
│   │   │   ├── __main__.py           #   python -m 入口
│   │   │   ├── server.py             #   服务主入口（sys.path 注入 + 端口检测 + app.run）
│   │   │   ├── app.py                #   Flask 应用工厂（错误处理/请求日志/注入 run_manager）
│   │   │   ├── config_edit.py        #   Web 配置编辑（白名单 config_edit_whitelist + 面板读取 + 应用编辑 + 写前 .bak 备份）
│   │   │   ├── handlers.py           #   路由 handler（页面/上传/生成提交/轮询/预览/下载/历史/配置/追问/whatif/缓存；生成执行体在 run_generation、只读观测路由在 handlers_health）
│   │   │   ├── handlers_health.py    #   只读观测路由（数据源健康 60s 缓存 / 系统自检 / 运行日志 / 健康历史）
│   │   │   ├── run_generation.py     #   生成执行体（RunManager 注入点：读持仓/模式分派/预算硬闸→generate_report；产物清单 + 完成通知）
│   │   │   ├── upload.py             #   上传安全（uuid 重命名/扩展名白名单/魔数校验/原子落盘/TTL）
│   │   │   ├── holdings_update.py    #   正式持仓更新（旧文件备份 .bak + 原子提升上传文件为正式文件）
│   │   │   ├── progress.py           #   Web 进度报告器（事件写入 run 状态缓冲）
│   │   │   ├── runs.py               #   RunManager 单 worker 串行队列 + run 状态/事件注册表
│   │   │   └── scheduler.py          #   内置定时生成调度（scheduler 块解析/触发窗评估/触发账本/daemon 线程）
│   │
│   ├── static/                       # 前端资产（报告图表 bundle + Web UI 前端 + 报告模板）
│   │   ├── chart.min.js              #   Chart.js UMD（本地 bundle，离线自包含）
│   │   ├── chart-print.js            #   打印降级（beforeprint 快照 <img> / afterprint 恢复）
│   │   ├── chart-config.js           #   Chart.js 全局配置（主题色/动画关闭/DPR 限制）
│   │   ├── chart-export.js           #   单图导出 PNG/CSV 按钮（.chart-box 注入组容器；PNG 2x 分辨率 / CSV 屏显数据本地 Blob 下载）
│   │   ├── chart-common.js           #   Chart.js 公共初始化 helper（trackChart/lineOptions/doughnutOptions，chart-init 与 What-if 页共用）
│   │   ├── chart-init.js             #   9 张图初始化（6 核心 + 3 演进；单图异常隔离 + degraded 虚线）
│   │   ├── toc.js                    #   左侧目录 TOC（折叠/展开 + IntersectionObserver 滚动高亮，离线自包含）
│   │   ├── fold.js                   #   正文大块折叠（锚点/打印自动展开 + 图表 resize 兕底，beforeprint 捕获阶段先于图表快照）
│   │   ├── theme.js                   #   主题切换（深/浅色 + localStorage 持久化 + Chart.js 重绘 + 打印浅色协调）
│   │   ├── test-chart.html           #   独立调试页：6 图渲染/降级/离线场景自检（Chart.js 升级验证载体）
│   │   ├── README.md                 #   资产说明 + Chart.js 版本号记录（升级指引：替换引擎后先在此页验证）
│   │   ├── architecture.svg          #   README 首屏主图：三渠道→引擎→双报告
│   │   ├── owl-mascot.svg            #   README 吉祥物「守望」猫头鹰插画（夜间守望/智慧顾问/全景视野定位隐喻）
│   │   ├── llm-chain.svg             #   README LLM 智囊团 Provider 链式分发图
│   │   ├── capabilities.svg          #   README 九大功能域总览图
│   │   ├── report-overview.png       #   README 报告效果截图：首屏品牌标记与完整目录导航（虚构样例持仓实景）
│   │   ├── report-toc.png            #   README 报告效果截图：盈亏汇总与市场指数
│   │   ├── report-charts.png         #   README 报告效果截图：穿透行业分布与 TOP10 持仓资产交互图表
│   │   ├── tui-menu.png              #   README 界面实景：TUI 全键盘主菜单（页头状态行）
│   │   ├── web-workbench.png         #   README 界面实景：Web 工作台生成报告页签（上传→选格式→生成）
│   │   ├── web-config.png            #   README 界面实景：Web 配置编辑面板（与 TUI 菜单同源）
│   │   ├── cli-report.png            #   README 与 CLI 手册共用：CLI 生成回显（产物路径 / 盈亏汇总 / 耗时排行）
│   │   ├── social-preview.jpg        #   GitHub 社交预览图 1200×630（猫头鹰左卡 + 品牌文案；make-assets.py social-preview 生成）
│   │   ├── web/                      #   Web UI 前端（Jinja 模板 + 静态资产，Flask template/static 目录指向此处）
│   │   │   ├── favicon.svg           #   标签页图标（品牌蓝底 + 猫头鹰头像「守望」，link 声明免 /favicon.ico 404）
│   │   │   ├── favicon-mark.png      #   猫头鹰头像 80×80（favicon.svg 栅格化，Excel 首页品牌标记嵌入源）
│   │   │   ├── index.html            #   单页 Web UI 模板（上传/格式选择/进度/结果/状态区三列含系统信息/日志查看卡）
│   │   │   ├── main.js               #   前端逻辑（上传/提交/轮询/渲染/日志加载，原生 ES6，无 innerHTML）
│   │   │   └── style.css             #   样式（CSS 变量/浅色主题/响应式 480px 断点/系统信息卡片/日志列表）
│   │   └── tmpl/                     #   报告 Jinja 模板（report/html_jinja_env 加载）
│   │       ├── report_template.html  #   Jinja2 HTML 报告主模板
│   │       ├── whatif_template.html  #   调仓 What-if 独立 HTML 页（双环图+变动明细）
│   │       └── partials/             #   章节级 partial（report_template.html 按 TOC 六组经 Jinja include 拆入）
│   │           ├── summary_section.html #   投资分析汇总章（指数卡/资产分布/账户小计，无序号区块；首屏「本期要点」块随开关 summary_highlights）
│   │           ├── holdings_detail_section.html #   持仓明细与分类章（区块①市值核算明细 + 区块②分类汇总）
│   │           ├── penetration_section.html #   资产穿透 TOP10 章节（排名表 + 未折算/报告期脚注）
│   │           ├── fund_performance_section.html #   基金业绩分析章（业绩表 + 候选比较/经理变更条件块）
│   │           ├── position_structure_section.html #   持仓结构与集中度章（重合度/相关性/集中度三区块）
│   │           ├── style_factor_section.html #   风格与因子分析章（风格表/因子回归/行业 Beta/因子目录四区块）
│   │           ├── news_correlation_section.html #   财经新闻热点章（新闻匹配表 + LLM 关联，内含事件窗 partial include）
│   │           ├── event_impact_section.html #   事件窗对照区块（并入财经新闻章；口径 banner + 事件表 + 降级行 + 占位分支，双端同源 view）
│   │           ├── global_macro_section.html #   全球政经局势章（LLM 文本 + 未配置占位）
│   │           ├── expert_review_section.html #   智囊团深度复盘章（LLM 圆桌 + 情景分析/自检占位）
│   │           ├── health_check_section.html #   持仓体检报告章（五维评分 + 未配置占位）
│   │           ├── penetration_deep_section.html #   穿透深度分析章（行业/国别暴露 + 未配置占位）
│   │           ├── portfolio_history_drawdown_section.html #   组合历史走势与回撤章（走势/回撤/危机三区块，fold 摘要行）
│   │           ├── evolution_section.html  #   组合演进章节（多快照趋势，含专用图表数据段）
│   │           ├── holding_change_section.html #   持仓变动复盘章节（事件表 + 指标 + 意图对账 + LLM 归因块，fold 摘要行）
│   │           ├── schedule_replay_section.html # 调仓纪律回放章节（双线图 + 指标对照 + 逐期表 + 占位分支，双端同源 view）
│   │           ├── data_source_status_section.html #   数据源可用性矩阵章（源健康/说明/覆盖/可信度四区块，fold 摘要行）
│   │           ├── fundamental_snapshot_section.html # 持仓基本面章节（区块①财务指标 + 区块②财报摘要，单一开关同开同关）
│   │           ├── llm_usage_section.html  #   LLM API 用量章（汇总区 + 模块明细表，菜单 L）
│   │           ├── report_qa_section.html  #   报告对话式追问区块（⚗ 实验：多轮问答/状态四态/轮次与用量，报告尾部条件渲染）
│   │           └── action_section.html     #   行动建议章节（再平衡信号/交易纪律/调仓建议/收益归因 + 门控块，开关 enable_action）
│   │
│   └── test/                         # 测试套件
│       ├── __init__.py               #   包标记（空文件）
│       ├── _network_guard.py         #   测试网络隔离原语（不可吞的断网错误 + offline_external_sources 离线桩）
│       ├── _path_isolation.py        #   敏感路径隔离实现体（config/缓存/快照/输出目录重定向，供 conftest fixture 调用）
│       ├── _script_loader.py         #   共享脚本加载器（scripts/ 按文件名动态加载的唯一实现，样板唯一性有机检）
│       ├── _tui_flow.py              #   TUI 动线驱动骨架（击键数基线 + E2E 语义断言共用：喂键计数/打点/跑动线）
│       ├── conftest.py               #   pytest 全局配置 + 标记注册
│       ├── helpers.py                #   测试辅助工具
│       ├── data/                     #   测试数据集
│       │   ├── cassettes/            #   数据源真实响应录制（git 跟踪，离线回放；刷新需 --run-live --record-cassettes）
│       │   │   ├── tencent_quote.json          #   腾讯行情（个股实时价）
│       │   │   ├── sina_quote.json             #   新浪行情（备用实时价）
│       │   │   ├── tencent_kline.json          #   腾讯 K 线（日线）
│       │   │   ├── fund_nav.json               #   东方财富场外基金净值
│       │   │   ├── fund_holdings.json          #   天天基金持仓明细
│       │   │   └── fund_quarterly_holdings.json #  天天基金季度持仓
│       │   ├── fixtures/             #   上游正文夹具（解析层回归用，与 cassettes/ 互补：锁「已取回正文形态」）
│       │   │   ├── README.md         #   夹具清单与来源/核对值约定
│       │   │   ├── datasink_indicator_section_600900.md # 长江电力 2025 年报「公司简介和主要财务指标」章节全文
│       │   │   ├── fund_purchase_table.txt # 天天基金申购状态总表真实响应样本（var reData= 前缀 + 四类代表行）
│       │   │   ├── tui_flow_contract.json       # 三条 E2E 动线的击键数与必须上屏语义词快照
│       │   │   └── tui_keystroke_baseline.json # 主路径击键数基线快照（TUI_KEYSTROKE_UPDATE=1 重写）
│       │   └── hallucination/        #   幻觉测试数据集
│       │       ├── __init__.py       #       子包标记
│       │       └── datasets.py       #       幻觉评估标准持仓数据
│       ├── unit/                     #   单元测试（16 子目录）
│       │   ├── __init__.py           #   子包标记
│       │   ├── conftest.py           #   单元测试 conftest
│       │   ├── test_channel_layering.py #   三渠道薄壳层纪律扫描（禁私有导入/禁写原语/禁默认值字面量）
│       │   ├── test_ruff_exclude_contract.py #   ruff 排除域契约（docs 归档冻结 / force-exclude 对显式路径生效）
│       │   ├── test_subprocess_text_encoding_contract.py #   子进程文本模式必须显式 encoding（portability 档回归守卫）
│       │   ├── analysis/             #   分析计算单元测试
│       │   │   ├── __init__.py       #       子包标记
│       │   │   ├── test_bond_yield.py         #   无风险利率获取
│       │   │   ├── test_bond_yield_edge.py    #   无风险利率边缘场景
│       │   │   ├── test_circuit_breaker_wrapper.py #   断路器包装器测试
│       │   │   ├── test_fx_exposure.py        #   外汇敞口分析
│       │   │   ├── test_factor_evaluator.py   #   因子目录编排（池构造/逐因子横截面与原因/评级/编排降级三类/口径一致性）
│       │   │   ├── test_factor_evaluator_edge.py # 因子目录边缘场景（全输入不可用/未知字段/NaN·inf 语义/单码池/非 dict 输入）
│       │   │   ├── test_financial_indicator_extract.py # 财务指标全文解析（真实年报夹具逐字段复现/行文变体/单位换算/精度切分/扣非排除/降级）
│       │   │   ├── test_financial_indicator_extract_edge.py # 财务指标解析边缘场景（取值窗口边界/异常幅度/越界比率/零基数同比/截断正文）
│       │   │   ├── test_financial_indicator.py # 财务指标派生（质量档四维阈值/缺维跳过/年度趋势/当前 PE·PB/趋势点）
│       │   │   ├── test_financial_indicator_edge.py # 财务指标派生边缘场景（阈值阶梯边界/脏值不计分/零基数/非正现价）
│       │   │   ├── test_financial_statement_derive.py # 官方合并报表派生（三表→标准指标口径与算术/同比对齐/缺表即空/报告期回退）
│       │   │   ├── test_market_sentiment.py   #   市场情绪纯装配（跟踪标的映射/龙虎榜与连板梯队命中/无命中与无数据降级契约）
│       │   │   ├── test_liquidity.py          #   流动性分析：场内品种变现天数
│       │   │   ├── test_prosperity_framework.py #  景气度框架诊断（六维计分/缺数据降级/评级边界/配置覆盖）
│       │   │   ├── test_prosperity_framework_edge.py # 景气度框架边缘（空/异常值/全防御板块/极端集中度/深回撤）
│       │   │   ├── test_liquidity_edge.py     #   流动性分析：边缘场景
│       │   │   ├── test_liquidity_otc.py      #   流动性分析：场外赎回天数
│       │   │   ├── test_liquidity_otc_edge.py #   流动性分析：场外边缘场景
│       │   │   ├── test_rebalance.py          #   再平衡信号计算
│       │   │   ├── test_rebalance_signals.py                        #   再平衡：信号与误报保护
│       │   │   ├── test_rebalance_deviation.py                      #   再平衡：目标偏离度与股债偏离
│       │   │   ├── test_rebalance_edge.py     #   再平衡边缘场景
│       │   │   ├── test_rebalance_advisor.py    #   调仓建议可行化层（份额取整/费用/现金缓冲/优先级/守卫）
│       │   │   ├── test_purchase_feasibility.py #   申购可行性判定（判定矩阵/阈值两侧/无判定入口/话术）
│       │   │   ├── test_purchase_feasibility_edge.py # 申购可行性边缘样本（非正金额/限额、NaN/Inf、极端量级）
│       │   │   ├── test_return_attribution.py   #   收益归因（TOP5 贡献占比/正负分列/净额合计/复用断言）
│       │   │   ├── test_cost_flow.py            #   成本流水分析（XIRR 资金加权收益/成本分档/分红累计）
│       │   │   ├── test_cost_position.py        #   持仓成本区间位置纯计算（百分位/clamp/中性值/窗口切片/序列提取）
│       │   │   ├── test_cost_position_edge.py   #   持仓成本区间位置边缘场景（退化序列/无效成本/非有限值/越界）
│       │   │   ├── test_scenario_analysis.py       #   情景分析测试
│       │   │   ├── test_alignment_correction.py #   口径修正因子计算
│       │   │   ├── test_action_advisor.py       #   行动建议计算（再平衡信号/交易纪律/调仓建议/收益归因/降级）
│       │   │   ├── test_trade_discipline.py     #   交易纪律引擎（止盈/止损/回撤/距触发幅度/静默期/多品种）
│       │   │   ├── test_drawdown_warning.py   #   回撤历史分位预警
│       │   │   ├── test_drawdown_events.py    #   回撤事件识别
│       │   │   ├── test_drawdown_events_edge.py #  回撤事件识别边缘场景
│       │   │   ├── test_style_factor_regression.py # 风格因子回归（OLS 回归/样本下限/停更剔除）
│       │   │   ├── test_industry_beta.py      #   行业 Beta 分析（暴露占比/已知答案回归/数据不足降级/契约）
│       │   │   ├── test_market_temperature.py #   市场温度纯计算层（三因子合成/刻度映射/免责声明/数据不足）
│       │   │   ├── test_market_temperature_edge.py # 市场温度边缘场景（样本边界/恒平序列/极端波动）
│       │   │   ├── test_metrics.py            #   量化指标计算测试
│       │   │   ├── test_metrics_edge.py       #   量化指标边缘场景
│       │   │   ├── test_monthly_returns.py     #   月度收益日历聚合（月收益算式/截窗基线/inception/统计/口径字段）
│       │   │   ├── test_valuation_percentile.py #  估值分位纯计算层（收盘价提取/分位解析解/三档刻度）
│       │   │   ├── test_valuation_percentile_edge.py # 估值分位边缘场景（样本边界/恒平/极端值）
│       │   │   ├── test_correlation.py        #   持仓相关性矩阵计算（已知答案/矩阵布局/降级）
│       │   │   ├── test_correlation_edge.py   #   相关性矩阵边缘场景（NaN/Inf/日期缺口）
│       │   │   ├── test_crisis_annotation.py   #   危机区间标注（静态表锚点与区间统计 + 回放态双层/指数缺席降级）
│       │   │   ├── test_benchmark_excess.py    #   风险调整超额计算（IR/TE 数值交叉验证 + 胜率/完整月 + 滚动 + 样本不足降级）
│       │   │   ├── test_tail_risk.py           #   尾部风险统计（VaR95/99 固定 fixture 精度 + 最大单日跌幅 + 连续下跌 + 恢复三态）
│       │   │   ├── test_tail_risk_edge.py      #   尾部风险边缘场景（0/负/NaN 跳过、量级、样本边界、持平序列）
│       │   │   ├── test_portfolio_evolution.py #  组合演进聚合计算（多快照趋势/HHI/TOP 变迁）
│       │   │   ├── test_snapshot_diff.py      #   快照差异摘要（新增/移除 + HHI 变化 + 超限项 + 无上次快照占位 + 同日去重）
│       │   │   ├── test_holding_change_events.py #   持仓变动事件抽取（窗口/计数/字段契约/只读零写入）
│       │   │   ├── test_event_window_impact.py #   事件窗纯计算（事件日映射/手算对照/LOCF/方向比对表）
│       │   │   ├── test_event_window_impact_edge.py #   事件窗纯计算边缘（行情缺失/窗口越界/坏日期/关键位不可解析降级）
│       │   │   ├── test_schedule_replay.py #   调仓纪律回放纯计算与规则契约（两规则手算/成本两态/长窗指标对照）
│       │   │   ├── test_schedule_replay_edge.py #   调仓纪律回放边缘（验收下限/阈值边界/空输入/缺日历降级）
│       │   │   ├── test_holding_change_events_edge.py #   持仓变动事件抽取边缘（去重/不足准入/异常快照）
│       │   │   ├── test_holding_change_metrics.py #   持仓变动指标（频率/结构/贡献分解恒等式/意图对账/重排识别）
│       │   │   ├── test_snapshot_diff_edge.py #   快照差异边缘场景（空目录/空持仓/全 0 权重/阈值 0/损坏文件/多账户聚合）
│       │   │   ├── test_benchmark_index_resolver.py #  基准指数映射（三阶优先级/非法覆盖回落/池内非指数码跳过）
│       │   │   ├── test_trade_cost_model.py    #   交易成本模型（FIFO 档位手算/金额分档/批次重放/聚合契约）
│       │   │   ├── test_trade_cost_model_edge.py #  交易成本模型边缘（临界持有期/批次不足判未知/零费率/超长持有）
│       │   │   ├── test_whatif.py             #   调仓 What-if 计算（变动识别/成本权重/HHI/降级）
│       │   │   ├── test_whatif_backtest.py    #   调仓 What-if 时序回测（天数折算/序列对齐/5 指标/降级）
│       │   │   └── test_whatif_backtest_edge.py #  时序回测边缘场景（未来日期/单 bar/首值 0/极端涨跌）
│       │   ├── config/              #   配置单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_anonymizer.py        #   持仓匿名化模块测试（4 模式/回退/配置读写）
│       │   │   ├── test_edit_ops.py          #   配置编辑共享层测试（白名单结构/值规则/写入与备份）
│       │   │   ├── test_config.py            #   配置管理核心测试
│       │   │   ├── test_config_atomic.py     #   配置原子操作测试
│       │   │   ├── test_config_atomic_edge.py #   配置原子操作边缘场景
│       │   │   ├── test_config_consistency.py #   配置模板与声明一致性测试（LLM 设置键/批处理键/报告节顺序/原子写崩溃恢复）
│       │   │   ├── test_config_default_single_source.py # 配置默认值单源收敛（嵌套取值/辩论段与档位默认值同源/provider 优先级一致）
│       │   │   ├── test_config_edge.py       #   配置管理边缘场景
│       │   │   ├── test_config_freshness.py  #   配置文件新旧对比（缺键/缺说明判据、URL 不当注释、用户自加注释不误报）
│       │   │   ├── test_config_feature_gates.py # 功能开关与访问器测试（组合进化/候选比较/动作开关/数据沉降/分组与生命周期开关）
│       │   │   ├── test_config_resilience_contract.py # 配置稳态与回退演练契约（非法不静默/删除重建/缓存重算/结构拒绝）
│       │   │   ├── test_config_scheduler_spec.py # 调度块归一化/严格校验（宽松回显/非法拒绝/单字段归一化）
│       │   │   ├── test_config_firstrun_edge.py #   首次运行配置边缘场景
│       │   │   ├── test_config_llm_multi.py      #   LLM 多配置测试
│       │   │   ├── test_json_comments_contract.py # JSONC 读取契约（五份配置文件注释样本/features 读改写保注释/模板生成）
│       │   │   ├── test_llm_settings_v2.py  #   v2 结构（生成器/版本拒绝/三层缺省/展平契约/未知保留）
│       │   │   ├── test_llm_credentials_blocks.py # 命名凭据块契约（只受支持形态/顶层 api_key 拒绝且不迁移/错误指引）
│       │   │   ├── test_llm_pricing.py      #   计价参考（缺失回退/部分覆盖/非法跳过/版本拒绝/计费等价）
│       │   │   ├── test_logging_config.py   #   日志配置（默认/回落/保存拒绝/env 优先/轮转/不可写与颜色降级）
│       │   │   ├── test_llm_param_validation.py # 参数范围（表驱动合法/越界/类型错/加载回落/写入拒绝与不落盘）
│       │   │   ├── test_config_llm_providers_priority.py#   多链线路优先级写入测试（置换校验/归一化/注释保留/备份/回退）
│       │   │   ├── test_config_llm_multi_edge.py #   LLM 多配置边缘场景
│       │   │   ├── test_config_validation.py     #   配置校验函数测试
│       │   │   ├── test_chapter_registry.py   #   报告章节注册表结构测试（四块划分/编号派生/来源注册表同源/写键可达）
│       │   │   ├── test_features.py           #   功能开关测试（注册表不变量：五字段齐备/分组覆盖全集/默认值遵循分组；实验清单按分组过滤；开关名解析与取值归并）
│       │   │   ├── test_features_edge.py      #   功能开关解析边缘场景（空串/空白/大小写/缺等号/多余等号/取值不可识别）
│       │   │   ├── test_llm_settings.py       #   LLM 定价/时段/时区设置解析测试（峰谷定价时段可配置）
│       │   │   └── test_local_state.py           #   机器本地状态读写测试
│       │   ├── core/                #   核心模块单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_cache_core.py       #   缓存核心功能测试（含 TTL/目录/常量）
│       │   │   ├── test_cache_cleanup.py    #   缓存清理与统计测试
│       │   │   ├── test_cache_format.py     #   缓存格式测试
│       │   │   ├── test_atomic_write.py     #   原子写入原语（新建/覆盖/父目录创建/失败返回 False 且不抛/旧内容保留/临时文件不残留/Windows 占用回退）
│       │   │   ├── test_cache_edge.py       #   缓存边缘场景测试
│       │   │   ├── test_circuit_breaker_gateway.py #   统一熔断网关（Provider/LLM/指标三路聚合）
│       │   │   ├── test_check_sources.py    #   数据源健康检查（整体耗时预算/慢源超时/竞态兜底）
│       │   │   ├── test_check_sources_credential.py # 健康检查凭据预检（缺凭据不探测/跳过态不影响退出码/就绪摘要行）
│       │   │   ├── test_code_utils.py       #   证券代码工具测试
│       │   │   ├── test_code_utils_classification.py # 分类工具测试（ETF/债券基金/QDII/场外判定）
│       │   │   ├── test_completion_notify.py # 任务完成通知测试（载荷/门控/分发隔离/凭据掩码/通道发送器）
│       │   │   ├── test_filesystem_edge.py  #   文件系统边缘场景
│       │   │   ├── test_holding_status.py   #   品种级数据状态标注测试（品种覆盖诊断）
│       │   │   ├── test_data_freshness.py   #   数据可信度诊断测试（新鲜度 + 单日跳变）
│       │   │   ├── test_decision_header.py #   决策头解析核心测试（词表/标签优先/否定守卫/复合词边界/结构化头/缓存后缀）
│       │   │   ├── test_decision_header_edge.py # 决策头解析边缘场景（正常表述不被误杀/畸形载荷/边界值）
│       │   │   ├── test_experiment_stats.py #   实验功能使用统计测试（累计计数/日期刷新/去重幂等/损坏容错/doctor 集成/报告入口接线）
│       │   │   ├── test_decision_ledger.py  #   决策账本核心测试（事件持久化/结算折叠/同日去重/教训区块）
│       │   │   ├── test_ledger_retention.py    # 业务账本按龄保留（窗口外丢弃/已结算永留/坏行不吞/幂等不受影响）
│       │   │   ├── test_decision_ledger_edge.py # 决策账本边缘场景（空账本/损坏行/阈值边界）
│       │   │   ├── test_doctor.py           #   系统自检测试（分组检查/永不抛异常契约/只读探测不留残留/统计与渲染）
│       │   │   ├── test_doctor_health.py  #   自检「日志与缓存」组（日志级别/体积与 DEBUG 占比/锚点阈值/运行台账告警）
│       │   │   ├── test_doctor_credential.py # 体检「数据源凭据」组（受开关约束/无声明报免费源/缺失给变量名建议/网络组不重复计失败）
│       │   │   ├── test_datasource_credential.py # 数据源凭据声明与就绪判定核心测试（声明表/空白串视为缺失/指引措辞/就绪矩阵）
│       │   │   ├── test_datasource_credential_edge.py # 凭据声明边缘场景（空表/缺 env_var/各类空白字符/重复注册/清空回落）
│       │   │   ├── test_cassette.py         #   数据源记录-回放引擎测试（请求键归一/存取/回放未命中/录制会话/校验）
│       │   │   ├── test_cassette_edge.py    #   记录-回放边缘场景（畸形 URL/版本号类型/结构破坏/重复键/空交互）
│       │   │   ├── test_http_client.py      #   HTTP 客户端测试
│       │   │   ├── test_json_comments.py     #   JSONC 注释剥离叶子模块（字符串内标记不误伤/统一解析入口/导入边界）
│       │   │   ├── test_jsonl_store.py      #   JSONL 原子追加/容错读取原语测试（含 perf/decision_ledger 委托行为不变）
│       │   │   ├── test_perf_stage_eta.py   #   阶段状态与 ETA 预估测试（中位数剩余/历史不足/异常静默降级/阶段广播隔离）
│       │   │   ├── test_perf_observation.py #   运行观测面测试（子项累加与并发安全/父阶段归集/诊断计数与错误封顶/日志采集与摘除/口径不参与总耗时）
│       │   │   ├── test_error_hints.py     #   异常→用户提示映射（类型优先/JSON 语法/网络关键词/堆栈标记）
│       │   │   ├── test_num_utils.py        #   数值归一原语（合法输入口径/bool 拒绝/int 原样返回/非有限值归零/尺寸格式化）
│       │   │   ├── test_num_utils_edge.py   #   数值归一边缘场景（非字符串非数值对象/超长字符串/嵌套容器/极端量级）
│       │   │   ├── test_logger.py           #   日志模块测试（文件+控制台，自动轮转）
│       │   │   ├── test_log_reader.py       #   结构化日志读取测试（parse_log/tail_log/read_log）
│       │   │   ├── test_system_info.py      #   系统状态组装与展示原语测试（熔断/路由/凭据回填/build 兜底）
│       │   │   ├── test_market_hours.py     #   交易时段判断测试
│       │   │   ├── test_market_hours_edge.py #   交易时段边缘场景
│       │   │   ├── test_models.py           #   数据模型测试
│       │   │   ├── test_retry.py             #   重试与退避原语（策略算式/瞬时判据/哨兵重试/有界与不重试）
│       │   │   ├── test_throttle.py          #   按名间隔节流原语（抖动算式/等待量/归属断言：实现只在 core）
│       │   │   ├── test_network_guard.py   #   网络隔离原语（断网错误不可被 except Exception 吞 / 建连被阻但构造可用 / 离线桩覆盖面）
│       │   │   ├── test_phase_timeout.py    #   阶段超时测试
│       │   │   ├── test_provider_registry.py #   数据源注册中心测试
│       │   │   ├── test_reader.py           #   持仓文件读取测试
│       │   │   ├── test_reader_flows.py                             #   流水页签解析与空持仓闸门
│       │   │   ├── test_reader_workbook.py                          #   工作簿解析与持仓读取
│       │   │   ├── test_registry.py         #   中央注册表测试
│       │   │   ├── test_registry_edge.py    #   注册表边缘场景
│       │   │   ├── test_signal_ledger.py    #   确定性信号账本测试（登记/幂等去重/实时-非实时折叠/摘要与缓存后缀）
│       │   │   ├── test_signal_ledger_edge.py # 信号账本边缘场景（未识别新鲜度/路径敌意/畸形记录/非有限值）
│       │   │   ├── test_text_safety.py      #   文本安全边界（孤立代理项→U+FFFD/代理对折叠/请求体递归净化）
│       │   │   └── test_trading_calendar.py  #   交易日历原语测试（交易日区间计数/长假与周末不误计/日历不可用回退）
│       │   ├── cache/               #   缓存单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_ttl_alignment.py    # TTL 三处对齐（默认值唯一来源/清理与读侧同值·无抖动/精确键用逻辑键/未注册键告警）
│       │   │   ├── test_ttl_business_matrix.py # 缓存 TTL 业务矩阵（时段 × 类型 × 覆盖层 + 读写清理同源 + 业务场景）
│       │   │   ├── test_cache_stamp_and_cleanup.py # 版本戳迁移（旧戳不可读仍按类型 TTL 清理）+ 逐类型清理判定
│       │   │   ├── test_negative_cache.py   # 负缓存探针原语（键族/命中计数/汇总清单/全量复位）
│       │   │   ├── test_cache_engine_contract.py # 缓存引擎契约（往返/压缩阈值/损坏恢复/命中统计/分组清除/并发）
│       │   │   ├── test_disclosure_cache_cadence.py # 财报类缓存节奏（索引/指标日频、正文月频、分红周频，同日不重复打源）
│       │   │   ├── test_cache_report_boundary.py # 报告级缓存隔离（用量增量/输入域/强制重生成/盘中→盘后跃变）
│       │   │   ├── test_cache_engine_scenarios.py # 缓存引擎场景（TTL 边界/压缩往返/损坏载荷含截断 gzip/原子并发写/键版本升级/目录不可写）
│       │   │   ├── test_cache_io.py         #   缓存 IO 测试
│       │   │   ├── test_cache_operations.py #   缓存编排下沉测试（update_all 最大努力/warm 预热/stats 载荷单源）
│       │   │   ├── test_cache_refresh_routing.py # 缓存刷新路由测试（00 重叠区场外基金不按 A 股取行业/分红/扩展数据）
│       │   │   └── test_holdings_tracker.py #   持仓快照缓存追踪器
│       │   ├── fetcher/             #   数据获取单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_fetcher_api_edge.py  #   API 获取边缘场景
│       │   │   ├── test_batch.py            #   批量调度单元测试
│       │   │   ├── test_chain.py            #   数据链主链路测试
│       │   │   ├── test_chain_recovery.py                           #   链路短缓存重取与纠正连击冷却
│       │   │   ├── test_chain_fallback.py                           #   链路取数回退（全失败/陈旧缓存/熔断跳过）
│       │   │   ├── test_chain_overlap_judgement.py                  #   历史增量重叠判据（数值变化才算修正，整窗重叠不重拉）
│       │   │   ├── test_chain_edge.py       #   数据链边缘场景
│       │   │   ├── test_chain_diagnostics.py #  链路失败原因采集与可读渲染（展示名(原因) 条目/熔断分支展示名一致/无诊断器行为不变）
│       │   │   ├── test_chain_overrides.py  #   调用级源覆盖（preferred/exclude；作用域/边界/优先级/CLI 接入）
│       │   │   ├── test_fetcher.py          #   获取调度核心测试
│       │   │   ├── test_fetcher_index.py    #   指数行情获取测试
│       │   │   ├── test_index_valuation.py  #   指数估值历史获取测试
│       │   │   ├── test_fetcher_industry.py #   行业分类获取测试
│       │   │   ├── test_fetcher_price.py    #   行情价格获取测试
│       │   │   ├── test_price_freshness_gate.py # 价格缓存新鲜度门禁（收盘时点/日期/QDII T-1）
│       │   │   ├── test_cache_degradation_interaction.py # 缓存 × 降级/熔断（过期兜底 vs 历史不兜底/失败不写缓存/形状准入）
│       │   │   ├── test_fund.py             #   基金数据获取测试（含联接基金穿透后处理：幂等/缓存命中补做/开关）
│       │   │   ├── test_fund_purchase.py    #   申购状态取数编排（链注册同构/四级降级阶梯/准入不污染旧缓存/会话复用/data_status）
│       │   │   ├── test_fund_fee.py         #   申赎费率取数编排（链注册/四级降级/载荷准入/会话复用/费率索引装配）
│       │   │   ├── test_factor_catalog_loader.py # 因子目录装载与校验（负例集合/缓存与拒载/注入探针与不可得原因/值键映射）
│       │   │   ├── test_financial_report_miss_cache.py # 负缓存：标的级正文缺失 + 章节清单不可得（传输失败不入/失效可恢复/命中计数）
│       │   │   ├── test_financial_report.py  #   全文本财报取数编排（标的收集/元数据取用/字段装配/摘要截断）
│       │   │   ├── test_report_backup_source.py # 财报域备源（适配器登记/命名空间隔离/巨潮章节切片/主源可用时备源零调用）
│       │   │   ├── test_financial_indicator.py #  财务指标域适配器与链路契约（适配器自检/字段集/链注册/降级/多期序列取数与缓存/价格映射）
│       │   │   ├── test_financial_indicator_hithink.py # 财务指标域「同花顺官方报表派生」链路（三表示例归一/非 A 股跳过/主源不可用时序列回退）
│       │   │   ├── test_fund_edge.py        #   联接基金穿透边缘场景
│       │   │   ├── test_fund_manager.py     #   基金经理数据测试
│       │   │   ├── test_quote_adapter_parity.py # 行情域适配契约等价性（与既有转换函数逐源比对 + 链两槽选择）
│       │   │   ├── test_quote_adapter_hithink.py # 行情域同花顺适配器与第三槽链路顺序（别名归一/契约自检/历史 provider 映射）
│       │   │   ├── test_source_adapter.py       # 数据源适配契约（注册表/三段式/声明式归一）
│       │   │   ├── test_source_adapter_edge.py  # 适配契约边缘场景（非映射响应/不可用取值/别名冲突）
│       │   │   └── test_credential_gate.py       # 链路凭据预检（缺凭据跳过 provider 落到下一链路、不计入熔断、历史遍历循环同样受控）
│       │   ├── handlers/            #   命令处理器单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_handlers_cache.py  #   缓存管理命令处理测试
│       │   │   ├── test_handlers_config.py #   命令处理器配置测试
│       │   │   ├── test_handlers_config_switch.py                   #   [S] 章节内容面板（编号派生/只读信息/切换/实验开关/写路径三通道）
│       │   │   ├── test_handlers_report_chapters.py                #   [C] 章节显隐面板（四块渲染/四来源写入/子项闸门/只读详情）
│       │   │   ├── test_handlers_config_nav.py # 配置面板方向键导航测试（方向键契约/游标反馈/子菜单导航/编号连续）
│       │   │   ├── test_handlers_llm_providers.py#   [M] 多链线路优先级面板测试（交换写盘/Esc/重提示）
│       │   │   ├── test_switch_panel_layout.py #   [S] 面板响应式排版（三档版面/不越界不变式/宽度探测）
│       │   │   ├── test_tui_menu_layering.py # 主菜单项与分组/[G] 全局设置/[D] 诊断路由与数字字母双通道
│       │   │   ├── test_handlers_qa.py #   报告对话式追问入口测试（选择/输入循环/会话续传/菜单门控）
│       │   │   ├── test_handlers_qa_edge.py #   报告追问入口边缘场景测试（EOF/Ctrl+C/目录不可读）
│       │   │   ├── test_handlers_log.py #   [D]→[V] 运行日志查看器着色（级别色优先 / LLM 调用行品红）
│       │   │   ├── test_handlers_report.py #   报告生成命令处理测试
│       │   │   └── test_handlers_whatif.py #   调仓 What-if 命令处理测试
│       │   ├── llm/                 #   LLM 单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── conftest.py      #       目录级 fixture（llm_cache_dir：缓存目录隔离 + 日志去重复位）
│       │   │   ├── test_llm_cache_ttl_single_source.py # 缓存 TTL 单一来源（读侧 == 注册表，逐模块覆盖，内容寻址模块 24h）
│       │   │   ├── test_llm_cache_ttl_matrix.py # LLM 缓存 TTL × 指纹矩阵（7 模块 × 覆盖层 × 四象限）
│       │   │   ├── test_llm_cache_multi.py         #   多 Provider 缓存测试
│       │   │   ├── test_circuit_breaker_edge.py  #   LLM 熔断器边缘场景
│       │   │   ├── test_circuit_breaker_recovery.py # 熔断恢复测试
│       │   │   ├── test_cost_forecast.py    #   事前费用预估与日预算（预估三态/预算边界/摘要分支）
│       │   │   ├── test_cost_tracker.py     #   Token 成本跟踪测试
│       │   │   ├── test_depth_profile.py    #   报告深度档位（档位表结构/非法回落/只收窄不放大/新闻下界）
│       │   │   ├── test_self_review.py      #   生成后自检（开关零调用/失败隔离/注册纪律/指纹内容寻址）
│       │   │   ├── test_force_scope.py       #   模块级强刷范围（键集注册表一致性/粒度优先/未知键校验/共享层接线/CLI 解析）
│       │   │   ├── test_holding_change_injection.py #   持仓变动提示词注入链路 + 章内归因编排（提取同源/附录含块/指纹条件并入/归因准入与写回）
│       │   │   ├── test_event_impact_injection.py #   事件窗分歧例块注入链路（四模块分发/传输层含块/辩论 inputs/指纹条件并入/附录逐字节回退）
│       │   │   ├── test_schedule_replay_injection.py #   调仓纪律回放引用块注入链路（四模块分发/传输层含块/指纹条件并入/附录逐字节回退）
│       │   │   ├── test_compliance.py       #   合规声明注入（幂等/角色追加项/空 prompt 保护/call_llm 漏斗接线）
│       │   │   ├── test_debate_conditional.py #   辩论条件触发测试
│       │   │   ├── test_debate_edge.py        #   辩论边缘场景
│       │   │   ├── test_debate_generators.py  #   辩论提示词生成测试
│       │   │   ├── test_debate_prompts.py     #   辩论提示词模板测试
│       │   │   ├── test_debate_qa.py          #   辩论 Q&A 测试
│       │   │   ├── test_debate_token_budget.py #   辩论 Token 预算测试
│       │   │   ├── test_llm_budget.py      #   LLM 总时间预算闸（make_budget_guard：0=不启用/超预算跳过/回显预算值）
│       │   │   ├── test_fact_checker.py       #   事实校验器测试
│       │   │   ├── test_fact_checker_ranking.py                     #   事实校验：排名正确性与整体运行
│       │   │   ├── test_fact_checker_symbols.py                     #   事实校验：代码/名称存在性
│       │   │   ├── test_fact_checker_context.py #   事实校验器上下文归属与自动纠错测试
│       │   │   ├── test_fact_checker_nonrate_guards.py #   事实校验器非收益率语境守卫（目标位/权重/市场口径/版本盐首尾日志）
│       │   │   ├── test_fact_checker_replay_context.py #   事实校验器回放语境豁免/回撤紧邻窗口/近并列排名注记/历史代码有效集测试
│       │   │   ├── test_fact_check_cache_writeback.py #   事实校验修正回写缓存（键不变/命中轮次零修正/写盘失败不中断）
│       │   │   ├── test_fingerprint.py        #   缓存指纹测试
│       │   │   ├── test_fingerprint_baseline.py #   跨进程指纹基线（键优先归因/无基线不臆测/快照降级）
│       │   │   ├── test_generators.py         #   全局提示词生成测试
│       │   │   ├── test_llm_chain_strategies.py  #   链路调度器全策略端到端
│       │   │   ├── test_module_fingerprint.py  #   模块缓存指纹读写同源测试
│       │   │   ├── test_fingerprint_generation_params.py # 生成参数入指纹（温度/长度/思考变化换键、cache 不变、两侧同源）
│       │   │   ├── test_fingerprint_components.py # 指纹组件级哈希与连续报告变化定位（稳定输入不变/单输入只改单组件/diff 只报变化项）
│       │   │   ├── test_cache_fingerprint_alignment.py # 指纹同源与失效最小化（敏感 vs 抗噪 vs 组件归因 vs 生成参数后缀）
│       │   │   ├── test_cache_recompute_attribution.py # 重算归因观测（forced/fingerprint_changed/ttl_expired、旁路不改行为、写 perf）
│       │   │   ├── test_report_sequence_cache.py # 连续报告缓存实测（同输入第二份预检 4/4 命中、失败条数漂移不换键、行情变化必重算）
│       │   │   ├── test_cache_sequence_matrix.py # 端到端报告序列命中矩阵（变化维度 × 命中模块/参数与模型/强制/成本一致/预检归因）
│       │   │   ├── test_cache_matrix.py # 缓存命中矩阵（逐模块精度/强制与模块级强制/Provider 切换/无链即失败/生成参数/TTL/跨进程/串行后置模块）
│       │   │   ├── _cache_fixtures.py # 缓存测试共用设施（最小自洽输入/编排调用/常量，四文件共用）
│       │   │   ├── test_cache_cost_accounting.py # 缓存成本契约（命中零边际成本/未命中必记账/日预算只算真实花费/节省估算/预估缓存折扣口径）
│       │   │   ├── test_cache_real_config.py # 真实配置链路缓存契约（不 patch 配置：v2 嵌套+多链、键同源、缺链不可用、损坏/gzip/并发/失败不缓存、故障转移写盘、模块开关）
│       │   │   ├── test_llm_analysis.py       #   LLM 分析测试
│       │   │   ├── test_llm_api.py            #   LLM API 主入口测试
│       │   │   ├── test_llm_api_attempt.py    #   单次调用尝试与重试策略表测试（200/429/503/超时/HTTP 异常与 429 诊断回显）
│       │   │   ├── test_llm_api_base.py       #   LLM API 基类测试
│       │   │   ├── test_llm_token_usage.py     #   Token 用量日志计量口径（跨协议归一/缓存命中回显）
│       │   │   ├── test_llm_pacing.py         #   端点级节流/并发治理测试（策略解析/注册/间隔/并发上限/403 不重试/429 诊断归属与行数上限）
│       │   │   ├── test_llm_observation.py    #   运行观测汇聚测试（等待/重试/降级/缓存/选路累加与快照裁剪/并发安全/绑定生命周期）
│       │   │   ├── test_llm_api_base_edge.py  #   API 基类边缘场景
│       │   │   ├── test_llm_api_edge.py       #   API 边缘场景
│       │   │   ├── test_llm_api_multi.py      #   多 Provider API 测试
│       │   │   ├── test_llm_api_multi_edge.py #   多 Provider 边缘场景
│       │   │   ├── test_llm_api_retry_errors.py # call_llm_with_retry 错误分支测试（HTTP/响应/内容过滤/截断与响应桩助手）
│       │   │   ├── test_llm_content.py        #   LLM 内容写入测试
│       │   │   ├── test_llm_fallback.py       #   LLM 降级回退策略
│       │   │   ├── test_generate_all_llm.py     #   generate_all_llm 编排入口
│       │   │   ├── test_generate_all_llm_concurrency.py # 并发治理与派发（thinking 并发上限/等待量化/模块跨度/新闻不并入编排）
│       │   │   ├── test_llm_placeholder.py    #   LLM 占位内容测试
│       │   │   ├── test_llm_placeholder_distinction_edge.py # 占位区分边缘场景
│       │   │   ├── test_llm_prompts.py        #   LLM 提示词测试
│       │   │   ├── test_llm_utils.py          #   LLM 工具函数测试
│       │   │   ├── test_pricing_currency.py    #   多币种计价口径（原生展示/配置优先/分组聚合/预算折算）
│       │   │   ├── test_llm_prompt_builders.py     #   提示词构建器测试
│       │   │   ├── test_purchase_constraint_injection.py  #   申购限购约束块注入链路测试（提取/附录/辩论/自检/新闻批量）
│       │   │   ├── test_prompts_core.py       #   提示词核心测试
│       │   │   ├── test_prompts_signals.py    #   信号预消化测试（资金流方向/信号块/缓存后缀/接线）
│       │   │   ├── test_prompts_signals_edge.py #  信号预消化边缘场景（畸形数据/非有限值）
│       │   │   ├── test_prompts_structured_header.py # 结构化决策头提示词契约（开关关闭逐字节不变/契约可解析/指纹换键）
│       │   │   ├── test_rate_caliber.py      #   收益率口径标签与提示词文本版本进指纹测试
│       │   │   ├── test_llm_session_usage.py       #   会话用量管理测试
│       │   │   ├── test_log_sanitize.py        #   日志清洗测试
│       │   │   ├── test_skeleton.py           #   内容骨架生成测试
│       │   │   └── test_strategy.py           #   策略引擎测试
│       │   ├── news/                #   新闻单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_akshare_news.py       #   akshare 新闻源测试
│       │   │   ├── test_cls_news.py           #   财联社新闻源测试
│       │   │   ├── test_eastmoney_news.py     #   东方财富新闻源测试
│       │   │   ├── test_news_aggregator.py    #   新闻聚合器测试
│       │   │   ├── test_news_fetch_limits.py    #   新闻抓取预算单源算式测试（per_source 预算与最终截取数解耦算式）
│       │   │   ├── test_news_correlator.py    #   新闻关联分析测试
│       │   │   ├── test_news_keywords.py      #   新闻关键词测试
│       │   │   ├── test_news_dedup_perf.py #   去重比较成本（多重集上界预筛/比较串缓存与完整 ratio 判定等价）
│       │   │   ├── test_news_dedup.py       #   新闻去重实现分片（标题判定算法/锚点写入去重/追加写与保留期）
│       │   │   ├── test_news_sources.py       #   新闻源注册测试
│       │   │   ├── test_news_dedup_compact.py #   锚点维护压缩（保留每组最新/备份 .bak/环境变量关闭/阈值下 noop）
│       │   │   ├── test_sina_news.py          #   新浪新闻源测试
│       │   │   └── test_wallstreetcn_news.py  #   华尔街见闻新闻源测试
│       │   ├── providers/           #   数据源提供商单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_datasink.py           #   DataSinking 财报 provider（符号映射/套餐限额/护栏/HTTP 分支/取数原语/传输级重试与上抛契约）
│       │   │   ├── test_datasink_probe_miss.py #  章节探测 404 负缓存（命中直接降级不发请求/文档级 404 不入负缓存）
│       │   │   ├── test_cninfo.py             #   巨潮资讯网备源 provider（orgId 解析/文种归类/报告期推导/PDF 解析接缝/限速与 HTTP 分支）
│       │   │   ├── test_hithink.py            #   同花顺数据服务 provider（凭据门禁/限速/信封错误码/HTTP 分支/thscode 映射/各域接口/传输级重试与上抛契约）
│       │   │   ├── test_akshare_extras.py     #   akshare 封装测试
│       │   │   ├── test_akshare_financial.py  #   akshare 结构化财务指标（宽表归一/百分数换算/同名指标优先/降级）
│       │   │   ├── test_cassette_replay.py    #   已录制真实响应体的解析回归（精确值断言，离线回放）
│       │   │   ├── test_eastmoney.py          #   东方财富 API 测试
│       │   │   ├── test_eastmoney_index_edge.py #   东方财富指数 K 线边缘场景测试
│       │   │   ├── test_eastmoney_industry.py #   东方财富行业分类测试
│       │   │   ├── test_eastmoney_industry_rest.py #   东方财富行业 REST 接口测试
│       │   │   ├── test_sina.py               #   新浪财经 API 测试
│       │   │   ├── test_sina_edge.py          #   新浪财经边缘场景
│       │   │   ├── test_numeric_guard_regression.py # 非有限数值归一防线（各解析器拦截 NaN/±inf + 合法输入行为不变）
│       │   │   ├── test_provider_utils.py    #   providers 共享原语（provider 自陈失败原因载体：消费即清/线程隔离）
│       │   │   ├── test_tencent.py            #   腾讯财经 API 测试
│       │   │   ├── test_tencent_edge.py       #   腾讯财经边缘场景
│       │   │   ├── test_tiantian.py           #   天天基金 API 测试（含基金持仓三跳阶梯次序与目标 ETF 锚点解析）
│       │   │   ├── test_tiantian_holdings_edge.py # 基金持仓取数阶梯与目标 ETF 锚点边缘场景
│       │   │   ├── test_tiantian_fund_fee.py   #   F10 费用页解析（赎回阶梯/优惠费率列/每笔固定费/载荷准入/akshare 备链）
│       │   │   ├── test_tiantian_fund_fee_edge.py # F10 费用页解析边缘（缺表/百分号变体/荒谬费率拒绝/异常输入）
│       │   │   ├── test_tiantian_purchase.py  #   申购状态总表解析（四类代表行契约/akshare 备链路映射/直连抓取传输桩）
│       │   │   └── test_tiantian_purchase_edge.py # 申购状态解析失败与载荷准入值域体检边缘场景
│       │   ├── qa/                 #   报告对话式追问单元测试（4 测试文件 + 1 夹具）
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── conftest.py      #       共享夹具（双样本报告 HTML：锚点/表头映射/噪声/超长数据章）
│       │   │   ├── test_report_qa_context.py # 上下文提取（分章/表头名映射/摘要截断/生成条件声明）
│       │   │   ├── test_report_qa_context_edge.py # 上下文边缘（路径净化/锚点缺失/整体上限钉死）
│       │   │   ├── test_report_qa_session.py # 会话服务（编排/历史折叠/用量记账/事实核对/并发隔离）
│       │   │   ├── test_report_qa_session_edge.py # 会话边缘（轮数硬上限/输入软上限/三层路径防御）
│       │   │   ├── test_report_qa_ask.py #   Web 路由 /api/qa/ask（开关门 403/参数 400/状态码映射/信封契约）
│       │   │   └── test_qa_telemetry.py #   埋点（字段/隐私/容错/汇总口径/转正判据/ask 接线）
│       │   ├── report/              #   报告单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_design_doc.py #   设计语言契约（DESIGN.md 骨架/护栏对偶/引用存在）结构守卫
│       │   │   ├── test_design_tokens.py #   双面设计 token 同名对表（共享角色/旧名映射/品牌蓝 token 化）守卫
│       │   │   ├── test_report_type_scale.py #   报告字阶/行高 token/表格数字排版/正文限宽/WCAG 对比度契约
│       │   │   ├── test_responsive_contract.py #   四档断点/触控 44px/首列冻结/移动阅读防护契约（DESIGN Responsive）
│       │   │   ├── test_report_empty_states.py #   三档空态族/二元文案口径/状态观感分工/DESIGN 同源契约（Data States）
│       │   │   ├── test_anonymize_pipeline.py #   报告管线匿名化接线（装配边界 pair/渲染层折叠/产物清扫/新闻标签脱敏）
│       │   │   ├── test_holding_detail_rows.py #   持仓明细行单源（两路径共有字段一致/字段子集/百分号/零昨收/渠道/观察期）
│       │   │   ├── test_benchmark.py              #   业绩基准测试
│       │   │   ├── test_benchmark_edge.py         #   基准边缘场景
│       │   │   ├── test_category.py               #   持仓分类领域函数测试
│       │   │   ├── test_cost_position.py          #   持仓成本区间位置契约与渲染（开关门控/降级/条件列显隐/脚注）
│       │   │   ├── test_section_type_flag_consistency.py # 章节 type ↔ board_flags ↔ 写入器装配键一致性守卫
│       │   │   ├── test_section_visibility.py    #   章节两层可见性（单契约乐观 + 多契约 data_flag_any OR 悲观）
│       │   │   ├── test_category_edge.py          #   分类边缘场景
│       │   │   ├── test_chart_data_builder.py     #   Chart.js 6 图数据集预处理器测试
│       │   │   ├── test_chart_data_builder_edge.py #   图表数据预处理器边缘场景（行业归"其他"等）
│       │   │   ├── test_data_integrity.py         #   数据完整性测试
│       │   │   ├── test_data_quality_edge.py      #   数据质量边缘场景
│       │   │   ├── test_data_quality_sheet.py     #   数据质量仪表盘页签写入测试（源健康+品种覆盖+可信度区块）
│       │   │   ├── test_data_status_message.py    #   降级事件可读失败原因（record message 透传/不影响降级判定/矩阵渲染优先取原因/无原因逐字回落）
│       │   │   ├── test_numeric_guard_regression.py # 报告层数值归一防线（NaN 防线：市值/盈亏/涨幅不接受 `or 0.0` 渗入，单个脏值不污染整列合计）
│       │   │   ├── test_numeric_guard_regression_edge.py # 报告层数值归一边缘场景（全 NaN 列/档位判定边界/混合合法与脏值）
│       │   │   ├── test_data_source_matrix.py     #   数据源可用性矩阵 + 数据源说明表（用途/计费/凭据/本次使用）测试
│       │   │   ├── test_data_status.py            #   数据状态测试
│       │   │   ├── test_downsample.py             #   服务端下采样测试（日频原样/周聚合/月聚合兜底/末点保留）
│       │   │   ├── test_excel_fund_deep_analysis.py  #   Excel 基金深度分析页签测试
│       │   │   ├── test_excel_format_edge.py      #   Excel 格式边缘场景
│       │   │   ├── test_excel_generator.py        #   Excel 生成测试
│       │   │   ├── test_excel_generator_llm_usage.py # LLM 用量页签状态判定（缓存/成功/禁用/失败四态 + 表头行内容契约）
│       │   │   ├── test_excel_generator_edge.py   #   Excel 生成边缘场景
│       │   │   ├── test_excel_market_data.py      #   成本流水 fund_flow_data 组装 + 注入测试
│       │   │   ├── test_excel_navigation.py       #   Excel 导航三件套（页签分组配色/汇总页章节导航/返回汇总链接 + 双端导航一致性）
│       │   │   ├── test_excel_report_structure.py #   Excel 报告结构测试
│       │   │   ├── test_excel_roundtrip.py        #   Excel 写入读取回环测试
│       │   │   ├── test_excel_writer.py           #   Excel 写入器测试
│       │   │   ├── test_experimental_seams.py     #   管线实验挂载点（开关关闭无感/开启生效/下游异常只告警不外抛 + 顶层导入接线守卫）
│       │   │   ├── test_feature_interactive.py    #   交互图表 Feature Flag + JS 资产复制/内嵌（单文件自包含）测试
│       │   │   ├── test_fund_deep_analysis_sheet_edge.py # 基金深度分析页签边缘场景
│       │   │   ├── test_fund_candidate.py         #   候选基金比较测试（基金业绩分析章候选比较子表）
│       │   │   ├── test_fund_concentration.py     #   基金集中度测试
│       │   │   ├── test_fund_manager_analysis.py  #   基金经理分析测试
│       │   │   ├── test_position_overlap.py       #   持仓重合度计算测试
│       │   │   ├── test_fund_performance.py       #   基金业绩测试
│       │   │   ├── test_fund_performance_sheet.py                   #   业绩分析页签写入器（评级/业绩/候选不可得）
│       │   │   ├── test_fund_style.py             #   基金风格判定测试
│       │   │   ├── test_history_snapshot_namespace.py      #   历史快照命名空间测试
│       │   │   ├── test_history_snapshot_namespace_edge.py #   历史快照命名空间边缘场景
│       │   │   ├── test_holdings_freshness.py      #   持仓报告期时效判定测试（写法兼容/季度数边界/阈值）
│       │   │   ├── test_snapshot_namespace_consumers.py    #   快照命名空间消费方测试
│       │   │   ├── test_snapshot_source_guard.py #   持仓源守卫（正式源判定/非正式源不落盘不比对/正式源行为不变/命名空间域不受限）
│       │   │   ├── test_snapshot_source_guard_edge.py #   持仓源守卫边缘（解析异常 fail-closed/缺省回退/全局配置）
│       │   │   ├── test_snapshot_baseline.py   #   环比比对基线（跨交易日选择/同日跳过/回退最新/域隔离/diff 透传）
│       │   │   ├── test_snapshot_baseline_edge.py #   比对基线边缘（周末/盘前归属/节假日日历/损坏顺延/坏时间戳跳过）
│       │   │   ├── test_style_factor_sheet.py     #   风格与因子分析页签呈现（一章三区块：风格表+因子回归+行业 Beta）
│       │   │   ├── test_correlation_html.py       #   持仓关系矩阵章节（相关性/重合度区块）HTML 呈现
│       │   │   ├── test_position_structure_sheet.py # 持仓结构与集中度页签（三区块 + 合并等价 + OR 可见性）
│       │   │   ├── test_evolution_html.py         #   组合演进章节 HTML 呈现（图表+图下说明）
│       │   │   ├── test_evolution_sheet.py        #   组合演进 Excel 页签呈现
│       │   │   ├── test_holding_change_panel.py    #   持仓变动复盘面板（契约装配/双端单源/关态隐藏/开关注册/模板接线/提示词块与重排标注）
│       │   │   ├── test_report_qa_partial.py #   报告追问区块 partial（Data States/信封消费/token 样式纪律/主模板 guard/开关隔离渲染）
│       │   │   ├── test_event_impact_panel.py #   事件窗对照表编排（极性/日期解析表、品种索引、行组装与降级计数）
│       │   │   ├── test_event_impact_panel_edge.py #   事件窗对照表编排边缘（空输入/坏 ctime/取数异常降级）
│       │   │   ├── test_event_impact_wiring.py #   事件窗接线（开关/seam/注册表并入判定/关态回退/双端单源/分歧例召回/模板并入新闻章/新闻-LLM 串行化）
│       │   │   ├── test_schedule_replay_wiring.py #   调仓纪律回放接线（开关/seam/注册表/关态回退/双端单源/引用块/模板/契约装配）
│       │   │   ├── test_holding_change_panel_edge.py #   持仓变动面板边缘（空快照/字段异常/数值边界）
│       │   │   ├── test_financial_report_digest.py #   持仓个股财报摘要章节装配（降级契约/文种标签/披露日/失败清单）
│       │   │   ├── test_financial_indicator.py #   财务指标章装配与接线（数据契约/质量档·趋势·PE·PB/开关/编排接缝）
│       │   │   ├── test_action_html.py            #   行动建议章节 + 智囊团深度复盘「行动摘要」HTML 呈现（单源计算断言）
│       │   │   ├── test_action_sheet.py           #   行动建议 Excel 页签呈现（含景气度框架诊断块）
│       │   │   ├── test_fund_roe_estimate.py  #   基金重仓股 ROE 加权估算（加权纯计算/陈旧闸门/非 A 股过滤/known_roe 免取数）
│       │   │   ├── test_prosperity_framework_wiring.py # 景气度框架接线（开关门控 + Excel/HTML 块显隐）
│       │   │   ├── test_decision_record.py        #   决策复盘·确定性载体登记（卖出建议入账/基线价守门/同日去重）
│       │   │   ├── test_decision_llm_capture.py   #   决策复盘·LLM 操作建议表解析登记（表头识别/逐代码方向/去重/降级）
│       │   │   ├── test_decision_header_render_wiring.py  #   决策复盘·决策头渲染剥离接线（登记后剥离/双端写出前/元组作用域）
│       │   │   ├── test_decision_settlement.py    #   决策复盘·结算服务（到期结算/方向命中统计/需样本数/基准对齐）
│       │   │   ├── test_decision_review_block.py  #   决策复盘·复盘区块数据组装（available/命中率/近期明细/样本守门）
│       │   │   ├── test_signal_record.py          #   确定性信号沉淀适配器（五类抽取/不可用跳过/实时-非实时判定/幂等与开关）
│       │   │   ├── test_whatif_html.py            #   调仓 What-if 独立 HTML 页呈现
│       │   │   ├── test_whatif_sheet.py           #   调仓 What-if Excel 三页签呈现
│       │   │   ├── test_whatif_operations.py      #   调仓 What-if 操作共享层测试
│       │   │   ├── test_history_policy.py         #   历史走势获取策略解析测试（off/auto/prompt × 有无交互）
│       │   │   ├── test_whatif_writer.py          #   调仓 What-if 报告输出（固定名+日期归档+清理 + 成本页签/裁剪/双端一致）
│       │   │   ├── test_whatif_cost_panel.py      #   交易成本面板装配（成本契约/impact 手算/基准对齐/门控/换手翻转回归）
│       │   │   ├── test_whatif_cost_panel_edge.py #   交易成本面板边缘（空变动/快照缺失/取数异常/比值越界降级）
│       │   │   ├── test_drawdown_html_excel.py    #   回撤明细 HTML/Excel 呈现
│       │   │   ├── test_tail_risk_wiring.py       #   尾部风险统计接线（pipeline 注入 + Excel 五行 + HTML 卡 + 图下说明）
│       │   │   ├── test_html_builders.py          #   HTML 构建器测试
│       │   │   ├── test_html_builders_edge.py     #   HTML 构建器边缘场景
│       │   │   ├── test_html_fund_deep_renderers.py # HTML 基金深度分析渲染器（报告期标注/陈旧剔除同 Excel 口径）
│       │   │   ├── _html_report_fixtures.py   # HTML 结构测试共享夹具（模板路径/章节常量/最小渲染数据构造，不含用例）
│       │   │   ├── test_html_report_structure.py  #   HTML 报告结构测试（导航/锚点/折叠）
│       │   │   ├── test_section_block_contract.py #   章节区块契约测试（注册表键集/双端提取对账/双端对等/归一化与直通包装原语）
│       │   │   ├── test_html_report_structure_content.py # HTML 结构正文内容块与视觉（交互图表/主题/数据质量块/页脚/期间标注）
│       │   │   ├── test_html_report_structure_content_blocks.py     #   HTML 数据质量块与报告期标注
│       │   │   ├── test_html_report_structure_content_charts.py     #   HTML 交互图表（canvas/数据集）
│       │   │   ├── test_html_report_structure_edge.py # HTML 结构边缘场景
│       │   │   ├── test_html_report_structure_toc.py #   HTML 结构返回顶部与目录（TOC）
│       │   │   ├── test_html_template.py          #   HTML 模板测试
│       │   │   ├── test_theme_js.py               #   暗色模式 theme.js 静态断言
│       │   │   ├── test_html_writer.py            #   HTML 写入器测试（Jinja 过滤器/模板渲染/章节顺序）
│       │   │   ├── test_html_writer_contents.py   #   HTML 写入内容与 LLM 模块信息测试
│       │   │   ├── test_html_writer_edge.py       #   HTML 写入器边缘场景
│       │   │   ├── test_market_sentiment.py      #   市场情绪报告层装配（开关门禁/凭据门禁/取数缓存/契约装配）
│       │   │   ├── test_market_sentiment_wiring.py # 市场情绪接线回归（full 路径契约注入与 HTML 透传/双端渲染载体）
│       │   │   ├── test_report_output_spans.py # full 路径 HTML/Excel 阶段埋点回归（阶段计时补回/异常仍收口/无上下文零行为变化）
│       │   │   ├── test_run_scope.py # 报告运行边界（降级事件只清本轮、失败计数/上次成功保留、自检载体重置、用量基线 delta）
│       │   │   ├── test_market_value.py           #   市值计算测试
│       │   │   ├── test_market_value_edge.py      #   市值边缘场景
│       │   │   ├── test_market_value_premium.py   #   市值溢价率与今日盈亏分支测试
│       │   │   ├── test_market_value_premium_branches.py # 今日盈亏来源分支（腾讯恒真/非交易日东财/边界/溢价占位/外币市值）
│       │   │   ├── test_holdings_detail_sheet.py  #   持仓明细与分类页签测试（两区块 + 合并等价）
│       │   │   ├── test_holdings_detail_sheet_cost.py # 资金加权成本与申购状态列取值口径
│       │   │   ├── test_holdings_detail_categories.py # 持仓分类页签与整表写入测试
│       │   │   ├── test_fundamental_snapshot_sheet.py # 持仓基本面页签测试（两区块 + 块级开关门控 + 合并等价）
│       │   │   ├── test_fund_performance_manager_block.py # 基金经理变更块测试（块门控 + 预警着色）
│       │   │   ├── test_market_value_strategy_edge.py # 市值策略边缘场景
│       │   │   ├── test_news_correlation.py       #   新闻关联报告测试
│       │   │   ├── test_news_degradation_edge.py  #   新闻降级边缘场景
│       │   │   ├── test_penetration.py            #   穿透分析测试（合并/排序/TOP10 与比值归一）
│       │   │   ├── test_penetration_classify.py   #   穿透分类与名称判定测试（classify/债券/联接/类型标签/名称归一化）
│       │   │   ├── test_penetration_edge.py       #   穿透分析边缘场景
│       │   │   ├── test_penetration_report_periods.py # 穿透报告期场景测试（不可得剔除/陈旧闸门/联接来源登记）
│       │   │   ├── test_penetration_sheet.py      #   穿透页签写入测试（剔除原因与各基金报告期备注）
│       │   │   ├── test_penetration_sheet_edge.py #   穿透页签写入边缘场景（空数据占位降级不抛错）
│       │   │   ├── test_pipeline_data_builder.py    #   管线数据上下文组装测试（危机/尾部风险/快照差分/风险调整超额等键注册）
│       │   │   ├── test_history_augmented_wiring.py # 历史增强装配接线（开关判定/子块扩展窗取数/full 路径注入/取数 helper）
│       │       ├── test_purchase_status.py          # 申购限购状态展示层测试（契约/陈旧阶梯/单元格/脚注/模板条件渲染）
│       │       ├── test_purchase_status_edge.py     # 申购限购状态边缘场景（0 元限额→限额未知/时间不可解析/过期档）
│       │   │   ├── test_pipeline_utils.py          #   管线工具函数测试
│       │   │   ├── test_portfolio_history_order.py # 历史走势并发取数的汇总顺序（并发抓、按输入持仓顺序汇总/浮点累加顺序固定）
│       │   │   ├── test_portfolio_history.py      #   组合历史走势测试
│       │   │   ├── test_progress.py               #   进度跟踪测试
│       │   │   ├── test_cli_run_summary.py         #   CLI 收尾资源摘要（LLM 成本行/缓存命中率行：有观测才输出）
│       │   │   ├── test_qdii_timezone_edge.py     #   QDII 时区边缘场景
│       │   │   ├── test_security_edge.py          #   证券边缘场景
│       │   │   ├── test_orchestrator.py           #   报告编排器单元测试
│       │   │   ├── test_orchestrator_snapshot.py # capture_snapshot / fetch_history_data 快照与历史走势
│       │   │   ├── test_orchestrator_generate_report.py # 报告生成主流程落盘与快照比对测试
│       │   │   ├── test_orchestrator_generate_report_full.py        #   orchestrator full 路径（含 LLM 编排）
│       │   │   ├── test_orchestrator_generate_report_both.py        #   orchestrator both 路径（HTML+Excel）
│       │   │   ├── test_run_integrity.py      #   运行一致性守卫（中断收口/原子落盘/已中断状态/guard_run）
│       │   │   ├── test_summary.py                #   摘要生成测试
│       │   │   ├── test_summary_sheet.py                            #   汇总页签整体输出（各区块组合）
│       │   │   ├── test_summary_highlights.py     #   摘要区首页执行摘要卡（降级判据/指标派生/排序截断/hhi 行级降级/新字段链路/模板双态）
│       │   │   ├── test_summary_module_rows.py    #   摘要模块数据行与 LLM 用量深度行测试
│       │   │   ├── test_llm_module_info.py         #   LLM 模块信息·Endpoint 汇总展示（主备排序标注/未映射不标注/去重）
│       │   │   ├── test_llm_quality.py            #   LLM 输出质量分级（A~F 口径/横幅注入/开关/章节标记与提示词一致性锁）
│       │   │   ├── test_llm_quality_edge.py       #   LLM 输出质量分级边缘场景（阈值边界/占位优先/非文本输入/幂等）
│       │   │   └── test_valuation_temperature_wiring.py # 估值分位+市场温度报告层接线测试
│       │   ├── scripts/              #   工程脚本单元测试（历史痕迹/版本一致性/任务编号/语义命名索引检查工具自检）
│       │   │   ├── __init__.py       #       子包标记
│       │   │   ├── test_check_version_consistency.py #   版本号一致性检查脚本测试
│       │   │   ├── test_check_style_guardrails.py #   设计护栏机检测试（E1/E2/E3 命中与豁免 + W 级观察语义 + 真仓库冒烟）
│       │   │   ├── test_check_script_contract.py # 脚本契约机检测试（退出码章节解析三格式/规则①②③④命中与豁免/白名单对齐真实声明/真实仓库规则①③④零偏离）
│       │   │   ├── test_check_import_surface.py # 导入面契约检查（真实仓库零 finding/IS1~IS3 合成命中/动态导入目标 smoke）
│       │   │   ├── test_scripts_reference_coverage.py #   文档↔脚本清单覆盖（一览/域索引/内部包点名）
│       │   │   ├── test_conftest_scenario_gate.py #  conftest scenario 门禁双向校验回归（目录内缺裸 marker 拦截/裸 marker 越目录拦截/子域不豁免/反斜杠路径归一）
│       │   │   ├── test_task_numbering_check_scripts.py # 任务编号一致性检查脚本测试
│       │   │   ├── test_task_numbering_hook_scripts.py # 任务编号自动保障 hook 脚本测试
│       │   │   ├── test_trace_check_doc_domains.py # 文档域专项（目录树行豁免收窄/文件名任务编号/任务记录域复盘痕迹三域）
│       │   │   ├── test_trace_shared_vocabulary.py # 两脚本共享历史叙述词表单一来源（交集==词表/两侧都引用/源码无写死字面量/多域登记）
│       │   │   ├── test_trace_check_scripts.py  #   check-code/doc-traces 工具自身豁免+时序模式检出/豁免回归（含测试/源码注释任务编号硬检出）
│       │   │   ├── test_trace_check_scripts_doc.py                  #   文档域痕迹检查（check-doc-traces）
│       │   │   ├── test_trace_domain_exemptions.py #   MAGIC/DASHTASK/UNDERSCORE 合法领域值豁免边界专项覆盖
│       │   │   ├── test_trace_logging_discipline.py #  日志统一守卫（非交互层 print 检出 / 豁免域 / 白名单完整性）
│       │   │   ├── test_trace_config_defaults.py #   配置默认值单源守卫（重复兜底检出/类型敏感/豁免域/真实仓库零 finding）
│       │   │   ├── test_doc_trace_deleted_refs.py #   doc-traces 已删函数残留检查测试（历史 def 注入/引用形态过滤/git 不可用容错）
│       │   │   ├── test_test_quality_regression.py #  测试质量回归守护（静态禁止空测试体=死用例）
│       │   │   ├── test_test_runner_machine_info.py  #  test_runner 机器信息采集/bench 别名/耗时表格渲染测试
│       │   │   ├── test_test_runner_doc_writer.py  #   test_runner 环境耗时对照文档自动更新（标记定位/列增改/round-trip）
│       │   │   ├── test_test_runner_reports.py  #   test_runner 分阶段报告路径与汇总页链接（防两阶段同名覆盖）
│       │   │   ├── test_test_runner_modes.py  #   dev-verify preflight 去重契约（预检仅留编号快检，重量守护不入预检）
│       │   │   ├── test_test_runner_portability.py #   portability 探针模式测试（BOM/PEP263 判定 / 探针环境与失败回传 / 聚合口径 / 注册表接线）
│       │   │   ├── test_extract_failures.py #   失败用例提取 data-jsonblob 解析（HTML 实体引号回归）
│       │   │   ├── test_find_order_dependent.py # 顺序依赖二分工具：前缀二分/收集解析/分类/精简 + 端到端
│       │   │   ├── test_eval_dedup_threshold.py # 去重校准工具：分支重判/锚点压缩幂等/报告口径与过时建议回归
│       │   │   ├── test_script_encoding.py  #   *.ps1/requirements.txt 编码与 *.sh 可执行位约定回归
│       │   │   ├── test_launch_script_regression.py  #   launch.sh 无参/缺省 VENV_PATH 启动回归（set -u 下 unbound variable 拦截）
│       │   │   ├── test_make_assets_social_preview.py #   make-assets social-preview 测试（画布尺寸/品牌文案/素材内嵌/栅格化参数/中间 PNG 去留/依赖缺失退出码）
│       │   │   ├── test_shell_contract.py  #   shell 脚本契约机检（set -e 下死代码 $? / set -u 下裸位置参数 + bash -n 语法）
│       │   │   ├── test_script_loader.py  #   共享脚本加载器测试（加载契约/模块名派生与覆盖/sys.modules 注册/每次新实例/样板唯一性机检）
│       │   │   ├── test_check_semantic_index.py  #   语义命名索引正反向校验脚本测试
│       │   │   ├── test_check_doc_drift.py  #   文档与实现一致性检查脚本测试（章节/开关/默认值/面板编号/目录树/统计表/归档索引/分区纪律/章节-区块矩阵）
│       │   │   ├── test_check_doc_drift_partitions.py #   台账分区纪律 / 归档索引 / 迁档占位 机检
│       │   │   ├── test_check_doc_drift_sections.py   #   章节-区块矩阵 / 手册菜单块与键引用 / 返回键不变式 / 可见性
│       │   │   ├── test_check_doc_drift_tree.py       #   目录树解析、说明计数与版本目录顺序
│       │   │   ├── test_check_doc_drift_crosscheck.py # 文档↔代码交叉校验分片（链路表/Thinking 支持矩阵/收集快照/生成产物/真库冒烟/统计回写/守护同源）
│       │   │   ├── test_check_doc_drift_requirements_menu.py # 需求菜单表检查单测（解析/真库一致/缺行·多行·组序·组名漂移检出）
│       │   │   ├── _release_fixtures.py     #   发布编排测试共享设备（子进程替身/临时仓库夹具/台账与目录树样例，非测试模块不收集）
│       │   │   ├── test_release_tool.py     #   发布流程分步编排单测（版本纯函数/changelog 迁移/预检/演进/prepare 与 archive 编排）
│       │   │   ├── test_release_tool_gate.py #  发布门禁与编排子命令单测（gate/refresh/publish/devbump + 归档前置三类拦截）
│       │   │   ├── test_release_hygiene.py #   陈旧字节码清理（只删无源 .pyc / dry-run / 空目录回收 / 幂等）
│       │   │   ├── test_no_legacy_software_name.py #   旧软件名残留守卫（运行面不得出现旧仓库名）
│       │   │   ├── test_release_archive.py  #   台账归档迁移纯函数单测（rf 表块无损搬运与幂等/头部追加与索引延展/plan 扁平搬入/docs-plan 完成判定/目录树搬迁/头部缺行报错）
│       │   │   ├── test_check_doc_links.py  #   文档链接与结构一致性检查脚本测试（死链/死锚点/重复标题/层级/编号序列/§引用）
│       │   │   ├── test_check_conclusion_cache.py #   守护结论缓存机制测试（冷热 --ci 输出逐字一致/输入·逻辑·结构失配矩阵/通过与发现都缓存/隔离重定向；接入 namespace 见测试文件头）
│       │   │   ├── test_check_file_length.py  #   单文件行数红线守护脚本测试（阈值边界/豁免登记/--ci 退出码契约/-v 清单派生）
│       │   │   ├── test_check_requirement_trace.py  #   需求 ID ↔ 验证载体追溯检查脚本测试（解析/五项断言/真实仓库冒烟）
│       │   │   ├── test_guard_conclusion_replay.py  #   code/requirement/doc-drift 三守护结论缓存回放接线（回放不重扫/输入失效重扫/退出码保持）
│       │   │   ├── test_checklib.py       #   检查脚本共享设施测试（CLI 契约/区间与表格解析/共享排除模式）
│       │   │   ├── test_check_test_redundancy.py # 测试用例冗余检查脚本测试（死用例/无断言/完全重复/自证用例/硬编码演进总数）
│       │   │   ├── test_eval_factor_zoo.py  #   因子目录评测脚本测试（目录冻结/A/B/C 阈值恰等边界/判定三态/基线读取/相关性口径/注入探针离线）
│       │   │   ├── test_eval_factor_zoo_edge.py # 因子目录评测脚本边缘场景（空输入/退化数据/极端值 fail-closed）
│       │   │   ├── test_perf_report.py #   性能基准报告脚本测试（样本规模与池上限/账户口径分类/_verdict 边界/动态测试时间/规模文案同源/LLM mock 目标与收集契约）
│       │   │   ├── test_perf_history.py    #   性能趋势查看脚本测试（均值极值降级/阶段跨记录合并/分组过滤·截尾·排序/趋势报告结构/时间列完整日期）
│       │   │   ├── test_perf_history_sections.py # 趋势报告段落渲染（时间桶/LLM 段落/版本对比/机器可读/异常与漂移段）
│       │   │   ├── test_collect_coverage.py # 覆盖计数脚本测试（收集退出码原样传递/插件记录与清空/目标展开与 live 套件排除/模式与子标记计数/出口退出码）
│       │   │   ├── test_make_assets_svg.py     #   make-assets svg-geom 几何审查测试（字符档位/锚点包围盒/最小面积容器归属/越界·贴边·重叠·越画布/坏元素跳过/退出码）
│       │   │   ├── test_make_screenshots.py    #   演示截图生成器测试（演示工作区持仓与绝对路径配置/报告命令装配/折行保色/路径瘦身/渲染尺寸/浏览器解析/入口分发）
│       │   │   ├── test_eval_llm_budget.py     #   表达预算评测脚本测试（预算分节守卫/度量解析/样本构建/汇总判定/CLI 干跑）
│       │   │   ├── test_check_test_markers.py # 测试标记合规脚本测试（AST 三来源提取/目录期望键/未注册·已移除·edge·目录期望四类违规/干净路径）
│       │   │   └── test_probe_entry.py      #   探测统一入口 registry 分发测试 + sampler 拆包契约测试
│       │   ├── startup/              #   首次运行引导单元测试
│       │   │   ├── __init__.py       #       子包标记
│       │   │   └── test_startup_wizard.py  #   首次运行引导向导测试
│       │   ├── cli/                 #   CLI 命令行模式单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_cli.py               #   CLI 命令行模式单元测试（解析/开关/主流程）
│       │   │   ├── test_cli_main.py                                 #   CLI 入口/主流程/早退开关测试
│       │   │   ├── test_cli_cache_whatif.py                         #   CLI 缓存更新与调仓 What-if 子命令测试
│       │   │   ├── test_cli_report.py                               #   CLI 报告子命令测试（生成/进度通道/降级摘要）
│       │   │   ├── test_cli_cost_forecast.py #   CLI 费用预估/日预算（--yes/交互确认/非交互硬闸/降级清强刷）
│       │   │   ├── test_cli_subcommands.py    #   CLI 子命令测试（view-logs/doctor/cassettes）
│       │   │   ├── test_cli_config_command.py #   CLI config 子命令与一次性覆写测试（白名单读写/--dry-run/--chapter/--anonymize 分派）
│       │   │   └── test_cli_edge.py          #   CLI 边缘场景测试
│       │   │   └── test_cli_llm_provider_order.py#   --llm-provider-order 解析与持久化测试
│       │   └── ui/                  #   UI 单元测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_panel_runtime.py          #   TUI 统一交互运行时（NavState 回绕/Enter 防误触/pick 收集/退出语义矩阵）
│       │   │   ├── test_prompt_text.py #   提示语模板用例（四成分/默认项写动作名/帮助文案）
│       │   │   ├── test_prompt_contract.py #   提示语契约机检（panel_loop 必须模板化 / 禁止回车取消藏括注 / input_choice 须声明回车 / 术语表禁上屏 / 闸门白名单）
│       │   │   ├── test_tui_keys.py              #   TUI 键盘输入测试
│       │   │   ├── test_design_tui_doc.py   #   终端交互契约（DESIGN-TUI.md 骨架/键表/护栏对偶/术语表/引用存在）结构守卫
│       │   │   ├── test_narrow_panel_render.py  #  窄屏 40 列底线全景机检（逐面板逐行断言不超宽）
│       │   │   ├── test_tui_edge.py         #   TUI 边缘场景
│       │   │   ├── test_report_artifacts.py #   报告收尾产物清单与单键确认（默认 N/Esc 跳过/Ctrl+C 退出）
│       │   │   ├── test_tui_handlers.py     #   TUI 事件处理测试
│       │   │   ├── test_tui_menu.py         #   TUI 菜单测试
│       │   │   ├── test_tui_menu_loop.py                            #   TUI 主循环退出通道与窄屏直达导航
│       │   │   ├── test_tui_menu_status.py                          #   TUI 页头状态行与 LLM 状态渲染
│       │   │   ├── test_keystroke_baseline.py #   主路径击键数基线（动线击键数快照守卫；防新增确认屏/闸门把主路径拉长）
│       │   │   ├── test_text_layout.py      #   文本宽度与盒线面板等宽不变式（中英混排行宽一致）
│       │   │   └── test_handlers_log.py     #   日志可视化命令处理测试（查看日志/健康历史）
│       │   └── web/                  #   Web 模式单元测试
│       │   │   ├── __init__.py      #       包标记（空文件）
│       │   │   ├── test_upload.py   #       上传安全模块（校验/生命周期/清理）
│       │   │   ├── test_upload_edge.py #    上传安全边缘（zip-bomb/伪装/路径穿越变体）
│       │   │   ├── test_progress.py #       Web 进度报告器（事件缓冲/seq/增量）
│       │   │   ├── test_runs.py     #       RunManager（状态机/队列/保留/单例重置）
│       │   │   ├── test_handlers.py #       Flask 路由 handler（全链路/错误信封/穿越拒绝/系统信息组装）
│       │   │   ├── test_handlers_runs.py                            #   Web 接口：运行事件流与短缓存并发
│       │   │   ├── test_handlers_system.py                          #   Web 接口：配置回填/健康/系统信息/日志/自检
│       │   │   ├── test_config_edit.py #    Web 配置编辑（白名单完备/写分派/校验守卫/备份）
│       │   │   ├── test_config_edit_edge.py # Web 配置编辑极端输入（edge，*_edge.py 隔离）
│       │   │   ├── test_config_surface_contract.py # Web 配置面契约（块↔渲染器/元数据覆盖/日志可写/无中文表）
│       │   │   ├── test_web_config_interaction.py # Web 配置面板交互结构契约（回滚/筛选/计数/域导航/深链/720px）
│       │   │   ├── test_health_credential.py # 健康接口凭据跳过态透传（skipped 标记到达前端，开关关闭时结构不变）
│       │   │   ├── test_holdings_update.py  #   Web 持仓更新（备份轮转/原子写提升）
│       │   │   ├── test_holdings_update_edge.py # Web 持仓更新失败/回滚边缘场景
│       │   │   ├── test_whatif_api.py #     Web 调仓 What-if 接口（成功链路/参数校验/错误信封/同源）
│       │   │   ├── test_whatif_api_edge.py # Web What-if 边缘（互斥 429/字段类型/生效日容错，edge）
│       │   │   ├── test_cache_api.py #      Web 缓存管理接口（统计只读/前缀保序/清理计数/同源 403）
│       │   │   ├── test_web_responsive.py # Web 窄屏响应式回归（路径断词/表单收缩规则声明 + radio 文案可达性静态断言）
│       │   │   ├── test_cost_forecast_flow.py # Web 费用预估与日预算硬闸（preflight/409/执行体兜底/前端接线）
│       │   │   ├── test_cost_preflight_contract.py # 成本预检字段契约（前端读的字段后端必须提供，防多币种改造后弹层静默崩）
│       │   │   ├── test_web_generate_flow.py # Web 生成流程前端接线回归（完成后按钮单源复位 + resetFlow 共用）
│       │   │   ├── test_web_static_serving.py # Web 静态资产回归（/static/* 固定路径）+ 五区页签/What-if/缓存卡结构契约
│       │   │   ├── test_web_theme.py #   工作台暗色主题与组件状态矩阵静态断言（防闪/同键对表/矩阵选择器/空态挂类）
│       │   │   ├── test_server.py   #       启动防护（output_dir 写锁检测/端口占用）
│       │   │   ├── test_scheduler.py #     Web 定时生成调度（解析/触发窗评估/账本/API/面板接线）
│       │   │   ├── test_web_completion_notify.py # Web 收尾完成通知接线（门控前置/载荷/吞异常/包装器委托）
│       │   │   └── test_smoke_web.py #      Web 冒烟脚本载体（test_client 全链路断言）
│       ├── integration/              #   集成测试（契约/隔离/流水线）
│       │   ├── __init__.py           #   子包标记
│       │   ├── test_cache_consistency.py      #   缓存前缀契约跨模块共享集成测试
│       │   ├── test_channel_vocabulary.py     #   三渠道用户词一致性契约（端点状态唯一归一 / 日预算决策屏同词）
│       │   ├── test_cli_integration.py        #   CLI 命令行模式集成测试
│       │   ├── test_debate_pipeline.py        #   辩论多轮对话管线集成测试
│       │   ├── test_error_isolation.py        #   单模块异常下其余生成链仍可产出集成测试
│       │   ├── test_module_contract.py        #   模块间输入/输出数据契约集成测试
│       │   ├── test_news_pipeline.py          #   新闻聚合到报告数据构建端到端集成测试
│       │   ├── test_report_chapter_consistency.py # 报告章节名称顺序集合契约一致性集成测试
│       │   └── test_tui_routing.py            #   TUI 菜单路由与回调绑定集成测试
│       ├── live/                     #   真实网络验证套件（opt-in，--mode live 才运行，不入门禁）
│       │   ├── __init__.py           #   子包标记
│       │   ├── conftest.py           #   live 子目录 conftest（收集 opt-in 套件）
│       │   ├── test_live_quotes.py   #   真实行情连通性（A股/ETF/场外基金/中美指数）
│       │   ├── test_live_news.py     #   真实新闻源连通性（东方财富/财联社/新浪/华尔街见闻）
│       │   ├── test_live_fund.py     #   真实基金数据源（历史净值/排名/基准）
│       │   ├── test_live_calendar.py #   真实 akshare 交易日历
│       │   └── test_live_cassette_record.py # 录制真实响应进 cassette（--run-live --record-cassettes 双开关，录完即回放自检）
│       └── scenario/                 #   场景测试（basic/datetime/llm/perf/resilience/security 六子组）
│       │   ├── __init__.py           #   子包标记
│       │   ├── basic/               #   基本面场景测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_tui_flow_semantics.py      #   TUI 三条主路径动线（击键不增 + 关键语义词上屏；P0 生成主路径 / P2 全量）
│       │   │   ├── test_scenario_basic_flows.py    #   基础业务链路场景测试
│       │   │   ├── test_pipeline_metrics_injection.py # 管线指标注入测试
│       │       ├── test_pipeline_purchase_status.py # 管线冒烟 — 申购限购状态契约注入 full/both 路径（available=False 静默隐列）
│       │   │   ├── test_pipeline_smoke.py          #   管线冒烟测试
│       │   │   ├── test_scenario_holdings_quality.py # 持仓质量场景测试
│       │   │   ├── test_scenario_operational_behavior.py # 操作行为场景测试
│       │   │   ├── test_scenario_section_order.py  #   报告章节顺序场景测试
│       │   │   ├── test_scenario_penetration_basic.py    #   穿透分析基础场景
│       │   │   ├── test_scenario_penetration_advanced.py #   穿透分析高级场景
│       │   │   ├── test_scenario_penetration_mixed.py   #   穿透分析混合场景
│       │   │   ├── test_scenario_penetration_edge.py    #   穿透分析边缘场景
│       │   │   ├── test_scenario_special_securities.py # 特殊证券场景测试
│       │   │   ├── test_scenario_prosperity_framework.py # 景气度框架诊断场景冒烟（开关开启 + 生产形态快照下报告生成不得失败）
│       │   │   └── test_pipeline_style_factor_regression.py # 风格因子回归管线场景测试
│       │   ├── datetime/            #   日期时间场景测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   └── test_datetime_scenarios.py #   日期时间场景测试
│       │   ├── llm/                 #   LLM 场景测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_llm_disabled.py          #   LLM 不启用
│       │   │   ├── test_llm_disabled_cache.py    #   禁用+缓存混合
│       │   │   ├── test_llm_empty_holdings.py    #   空持仓/全缓存
│       │   │   ├── test_llm_extended_thinking.py #   Extended Thinking 混合
│       │   │   ├── test_llm_hallucination.py     #   LLM 幻觉率采样场景测试
│       │   │   ├── test_llm_mixed_cache.py       #   混合缓存+真实调用
│       │   │   ├── test_llm_module_info.py       #   LLM 模块信息输出契约测试
│       │   │   ├── test_llm_network_error.py     #   断网下 LLM 降级
│       │   │   └── test_llm_partial_cache.py     #   部分缓存超期
│       │   ├── perf/                #   性能场景测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   └── test_e2e_perf.py #   端到端性能场景测试
│       │   ├── resilience/          #   弹性场景测试
│       │   │   ├── __init__.py      #       子包标记
│       │   │   ├── test_chain_resilience.py   #   数据链弹性场景测试
│       │   │   ├── test_scenario_resilience_flows.py # 弹性业务链路场景测试
│       │   │   └── test_scenario_extreme.py      #   极端场景测试
│       │   └── security/            #   安全场景测试
│       │       ├── __init__.py      #       子包标记
│       │       └── test_security.py #   安全场景测试
│
├── data/                             # 运行时数据
│   ├── holdings/                     #   持仓 xlsx 文件（用户放置）
│   ├── knowledge/                    #   知识数据（fund_benchmarks.json / sector_keywords.json，随仓库发布）
│   ├── calibration/                  #   校准数据（dedup_anchors-YYYYMM.jsonl.gz 按月分片，自动生成）
│   ├── cache/                        #   API 响应缓存（自动生成，JSON/GZ）
│   ├── config/                       #   配置文件（config.json / features.json / llm_key.json / llm_settings.json / llm_providers.json / llm_pricing_ref.json / logger.json / data_key.json）
│   ├── state/                        #   运行时状态文件（.degradation_state.json / circuit_breaker.json / local_state.json 等，自动生成，机器本地不随仓库同步）
│   └── history/snapshots/            #   持仓快照（自动生成，保留 180 天）
│
├── reports/                          # 报告输出（最新版 + 按日期归档）
├── logs/                             # 程序日志（app.log，自动轮转）
├── test-reports/                     # 测试报告（自动生成，按 mode 分组；**只应在仓库根**，受检目录下出现即为误落）
├── .githooks/                        # git hooks（任务编号一致性 pre-commit，跨机器需 install-hooks.sh 激活）
│   ├── pre-commit                    #   pre-commit hook（提交涉及 plan.md/review-findings.md 时校验编号）
│   └── install-hooks.sh              #   hooks 激活脚本（clone 后运行一次启用 core.hooksPath）
├── .github/                         # GitHub 配置
│   └── workflows/                      #   CI/CD 配置文件
│       └── ci.yml                   #   CI/CD 流水线（P0/P1/P2 三级门禁 + guards/portability/format 三个独立 job）
├── pytest.ini                       # pytest 全局配置（含 PEP 597 隐式编码严格档 error::EncodingWarning）
├── reason.bat                       # Reasonix AI code editor 启动（`reasonix code`）
├── scripts/                          # 启动脚本 + 工程工具（测试/文档/质量/发布/运维观测/评测/资产）
│   ├── cli.ps1                      #   Windows PowerShell CLI 命令行包装（无参数默认生成报告 --type both）
│   ├── cli.sh                       #   Linux/macOS CLI 命令行包装（无参数默认生成报告 --type both）
│   ├── launch.ps1                   #   Windows PowerShell 启动脚本
│   ├── launch.sh                    #   Linux/macOS 启动脚本
│   ├── llm.ps1                      #   Windows PowerShell 完整报告包装（固定 report --type full，含 LLM）
│   ├── llm.sh                       #   Linux/macOS 完整报告包装（固定 report --type full，含 LLM）
│   ├── test-runner.py               #   测试驱动（pytest 模式封装）
│   ├── release.py                   #   发布流程分步编排（check/prepare/archive/refresh/evolution/gate/publish/devbump）
│   ├── check-test-markers.py        #   测试标记合规检查
│   ├── check-test-redundancy.py     #   测试用例冗余与无效检查（死用例/无断言/完全重复/自证用例/硬编码演进总数）
│   ├── check-requirement-trace.py   #   需求 ID ↔ 验证载体追溯检查（已补全域全覆盖/载体文件存在/ID 双向一致）
│   ├── check-task-numbering.py      #   任务编号（plan-/rf-）全局一致性检查
│   ├── check-task-numbering-hook.py #   Claude Code PostToolUse hook（编辑编号文档后自动校验）
│   ├── hook-install-claude.py       #   Claude Code hook 安装/卸载（跨机器接线）
│   ├── check-version-consistency.py #   版本号一致性检查
│   ├── check-style-guardrails.py #   设计护栏机检（DESIGN 护栏样式面；E 级判 finding，W 级观察——观察期未入钩子/CI）
│   ├── check-script-contract.py  #   scripts 顶层脚本契约机检（退出码声明 ⊆ {0,2} + check-* add_common_args CLI 面 + 文本 I/O 显式 encoding + 脚本↔测试覆盖，四条规则+白名单——观察期未入钩子/CI）
│   ├── eval-dedup-threshold.py #   新闻去重阈值校准 + 锚点压缩（保留期同生产）
│   ├── test-collect-coverage.py     #   测试覆盖计数收集（pytest --collect-only 快照；--update-docs 回写 test-coverage/folders 计数行）
│   ├── check-code-traces.py         #   代码注释历史痕迹 + 任务编号 + 日志统一 + 配置默认值单源检查（AST 支路：core 分层 / print 禁令 / 默认值重复兜底）
│   ├── check-doc-traces.py          #   文档历史痕迹与结构性冗余检查
│   ├── check-semantic-index.py      #   功能语义命名表正反向一致性检查
│   ├── check-doc-drift.py           #   文档与实现一致性检查（章节/开关/默认值/面板编号/目录树/统计表/归档索引/管理文档分区纪律/Thinking 支持矩阵/章节-区块矩阵/手册菜单块）
│   ├── check-doc-links.py           #   文档链接与结构一致性检查（死链/死锚点/重复标题/层级/编号序列/§引用）
│   ├── check-file-length.py         #   单文件行数红线守护（主程序/脚本 >1000 / 测试 >1200；豁免与 review-findings 挂账同步，-v 清单供登记表派生）
│   ├── check-import-surface.py      #   导入面契约检查（兼容注释/私有 __all__/跨包私有导入/动态导入字面量；观察期未入钩子/CI）
│   ├── _import_surface_exceptions.json # 导入面检查例外表（owner/reason/expiry/replacement）
│   ├── eval-factor-zoo.py           #   因子动物园目录评测入口（CLI + 原面 re-export；因子五族目录冻结/字段可得/信号相关/耗时基线/判定汇总，实现在 _eval_factor_zoo/ 包，产物落 docs/tmp/）
│   ├── _eval_factor_zoo/                 #   因子目录评测内部实现包（入口 eval-factor-zoo.py 仅留 CLI 与原面 re-export）
│   │   ├── __init__.py              #       子包标记（原面 re-export）
│   │   ├── catalog.py               #       预注册判定口径与冻结因子目录（门槛常量 + 五族×5 目录 + 冻结校验）
│   │   ├── probe.py                 #       股票池与字段可得性探测（穿透池只读复用 + 逐因子可得性探测）
│   │   ├── metrics.py               #       指标 A/B/C 计算与三态判定（可得率/信号增量相关/耗时比）
│   │   ├── stages.py                #       评测阶段编排（catalog/fields/signals/timing 落盘）
│   │   └── report.py                #       判定书生成（judge 汇总 + 判定书 Markdown 渲染）
│   ├── eval-llm-hallucination.py #   LLM 幻觉率采样 CLI（标准持仓集+事实校验器验证；实现在 _eval_halluc_sampler/）
│   ├── eval-llm-budget.py             #   LLM 表达预算校准入口（冻结样本 × 预算档位 × 模式矩阵；实现在 _eval_llm_budget/，产物落 docs/tmp/）
│   ├── _eval_llm_budget/              #   eval-llm-budget 内部实现包（预算文案/提示词替换/样本/度量/编排/报告）
│   │   ├── __init__.py              #       子包标记（原面 re-export）
│   │   ├── budget.py                #       预算档位与分节上界文案（比例之和守卫）
│   │   ├── prompts.py               #       提示词常量与特性开关的临时替换（退出还原）
│   │   ├── sample.py                #       冻结输入样本（持仓快照 → 明细/分类/合计）
│   │   ├── measure.py               #       分段字数/要素机检/操作建议表解析
│   │   ├── repair.py                #       缺结构补写（评测实验：验证兜底有效性与代价）
│   │   ├── runner.py                #       单次测量编排（会话用量差 + 墙钟 + 模式路由）
│   │   ├── report.py                #       汇总分位、验收判定与 Markdown/JSON 落盘
│   │   └── cli.py                   #       freeze/run 子命令与退出码
│   ├── test-perf-report.py          #   端到端性能基准测试（独立脚本，mock 外部数据源）
│   ├── perf-history.py                 #   性能历史趋势查看（perf_history.jsonl -> 分位/演进/漂移 Markdown + 机读）
│   ├── _perf_history/                  #   perf-history 实现包（入口 perf-history.py 仅留 docstring/sys.path 引导与 re-export）
│   │   ├── __init__.py              #   子包标记（空文件）
│   │   ├── stats.py                 #   分位/离群/稳健统计纯函数 + 记录过滤与分组（入口 re-export 保测试可达）
│   │   ├── data.py                 #   数据派生（版本演进 / 漂移 / 版本对比 / 机读信封 / 成本时段）
│   │   ├── report.py               #   渲染（概览·离群·尾部归因·演进·异常·漂移·时段·对比 + build_trend_report）
│   │   └── cli.py                  #   命令行入口（argparse → build_trend_report → 输出）
│   ├── probe.py                     #   探测统一入口（按 target 分发到 _probes/ 子模块；新探针登记即用）
│   ├── test-extract-failures.py      #   pytest-html 报告失败用例提取
│   ├── test-find-order-dependent.py  #   顺序依赖失败污染源二分定位（单跑绿合跑红 → 前缀二分+配对确认）
│   ├── make-assets.py                #   视觉资产维护入口（social-preview 生成 + svg-geom/svg-pixel/svg-text-overflow 渲染体检）
│   ├── _assets/                      #   视觉资产实现包（入口 make-assets.py 仅留子命令分发）
│   │   ├── __init__.py               #       子包标记（并注入 scripts/ 到 sys.path）
│   │   ├── social_preview.py         #       社交预览图绘制与栅格化（1200×630，猫头鹰左卡 + 品牌文案右栏）
│   │   └── svg_check.py              #       架构图渲染体检（几何 / 像素越界 / 文字色越界）
│   ├── make-screenshots.py           #   演示截图生成入口（demo/report/tui/web 四子命令）
│   ├── _screenshots/                 #   演示截图实现包（入口 make-screenshots.py 仅留子命令分发）
│   │   ├── __init__.py               #       子包标记（空文件）
│   │   ├── demo_workspace.py         #       隔离演示工作区（自造持仓 + 占位凭据 + 绝对路径配置）与报告生成
│   │   ├── tui_frame.py              #       TUI 帧取文本 + SGR 折行保色渲染 PNG + 路径瘦身
│   │   ├── web_shot.py               #       无头 Chromium CDP 截图封装（浏览器解析 + 命令行装配）
│   │   └── cdp_shot.mjs              #       CDP 截图脚本（Node ≥22 内置 WebSocket；导航→替换→滚动→截视口）
│   ├── _doc_drift/                   #   文档漂移检查内部实现包（入口 check-doc-drift.py 仅留 CLI 与编排）
│   │   ├── __init__.py               #       子包标记（并注入仓库根到 sys.path；原面 re-export）
│   │   ├── _shared.py                #       共享设施（文档路径常量 / 扫描面 / 表格与区间解析 / 统计原语）
│   │   ├── _format.py                #       文档格式族检查（章节表 / 开关表 / 默认值 / TTL / 测试覆盖计数）
│   │   ├── _format_panels.py         #       面板编号族检查（[C] 章节显隐与 [S] 内容组的编号派生校验）
│   │   ├── _tree.py                  #       目录树与统计表检查（folders.md 双向比对 + 项目统计表核对）
│   │   ├── _ledger.py                #       台账族检查（归档索引 / 分区纪律 / Thinking 支持矩阵）
│   │   ├── _menu_blocks.py          #       手册菜单块检查（双手册主菜单 code block ↔ MENU_ITEMS 键集合/标签头）
│   │   ├── _requirements_menu.py    #       需求菜单表检查（键集合/分组/组内顺序 ↔ MENU_GROUPS）
│   │   └── _guards.py                #       守护清单同源校验（developer-guide P0/P2 ↔ ci.yml guards ↔ CLAUDE/testplan 四处清单一致）
│   ├── _traces_code/                 #   check-code-traces 内部实现包（入口保留 CLI 与原面 re-export）
│   │   ├── __init__.py               #       子包标记（原面 re-export）
│   │   ├── config.py                 #       扫描域配置（仓库根/扫描目录/跳过文件/工具自身与规则载体识别）
│   │   ├── patterns.py               #       匹配模式表（历史痕迹/标识符/暗号；只管「匹配什么」，共享叙述词表引用 _traces_common）
│   │   ├── exemptions.py             #       豁免表（章节/轮次共享豁免 + 代码侧行级/魔法编号豁免与判定函数）
│   │   ├── extract.py                #       注释抽取（per-language）与标识符提取
│   │   ├── scan.py                   #       scan_file 调度（痕迹/标识符/分层/日志/配置默认值五支路汇聚）
│   │   ├── layers.py                 #       core 反向依赖 AST 守卫
│   │   ├── logging_discipline.py     #       日志统一 AST 守卫（print() 仅限交互呈现层白名单）
│   │   └── config_defaults.py        #       配置默认值单源守卫（与默认表同值的字面量兜底检出）
│   ├── _traces_doc/                  #   check-doc-traces 扫描后端包（入口薄 CLI + 原面 re-export）
│   │   ├── __init__.py               #       子包标记（原面 re-export）
│   │   ├── patterns.py               #       文档痕迹模式表与行级豁免（含目录树行专属补强）
│   │   ├── bundle.py                 #       模式子集与并集预筛（编译镜像 + 按域取子集 + 树行拼表，lru 缓存）
│   │   ├── deleted_refs.py           #       已删除函数残留（git 历史 def × 当前 def 差集；浅克隆告警不假绿）
│   │   ├── findings.py               #       结论汇总行与退出码 + 缓存结论结构校验（全量/回放共用）
│   │   └── dedup.py                  #       重复标题路径感知判重 + 台账/归档域重复长行/区块（同小节限定）
│   ├── _probes/                       #   探测子模块包（target 登记处 + 各探测实现；纯只读无副作用）
│   │   ├── __init__.py               #       子包标记（target 注册表：available_targets/get）
│   │   ├── csi.py                    #       CSI 风格指数可用性探测（因子分析周期性复核，条数+新鲜度双维度）
│   │   ├── sector_flow.py            #       行业资金流向双通道可用性探测（主=东财 push2 / 备=同花顺，只读取数）
│   │   └── push2.py                  #       东方财富 push2 连通性诊断（区分网络拦截/程序缺陷/WAF 拦指纹）
│   ├── _eval_halluc_sampler/              #   eval-llm-hallucination 内部实现包（入口仅留 CLI 与编排）
│   │   ├── __init__.py               #       子包标记（原面 re-export）
│   │   ├── holdings.py               #       品种分类 / 组合核心数值 / 标准数据集加载
│   │   ├── llm_call.py               #       HTTP 客户端工厂 / 模块映射 / prompt 构建与真实调用
│   │   ├── fact_check.py             #       事实校验（独立检查器精准分类）
│   │   └── report.py                 #       幻觉率评估报告生成（Markdown）
│   ├── _test_redundancy/            #   测试冗余检查实现包（入口 check-test-redundancy.py 仅留 CLI 与 re-export）
│   │   ├── __init__.py              #       子包标记（空文件）
│   │   ├── _common.py               #       共用常量与 AST 原语（用例抽取/断言与打桩识别/夹具暴露名）
│   │   ├── cases.py                 #       检查 1-2：死用例 / 无断言
│   │   ├── duplicates.py            #       检查 3：完全重复用例（体+参数+装饰器归一化）
│   │   ├── similar.py               #       相近用例骨架聚类（仅审计，不判 finding）
│   │   ├── self_fulfilling.py       #       检查 4：自证用例
│   │   ├── hardcoded.py             #       检查 5：硬编码演进总数
│   │   ├── trivial.py               #       检查 6：恒真断言
│   │   ├── weak_mock.py             #       检查 7：弱 mock 断言
│   │   ├── dead_fixtures.py         #       检查 8：死 fixture
│   │   ├── facts_cache.py           #       文件事实缓存（脚本+_shared/checklib+解释器版本+逐文件 size:mtime）
│   │   └── runner.py                #       编排（八类检查依次执行 + finding 汇总 + 退出码）
│   ├── _test_runner/                 #   测试驱动内部实现包（入口 test-runner.py 仅留 CLI 与编排）
│   │   ├── __init__.py               #       子包标记（并注入仓库根到 sys.path）
│   │   ├── paths.py                  #       路径常量（项目根 / 报告目录 / 归档目录 / 源码目录）
│   │   ├── modes.py                  #       模式注册表与模式解析（MODES / 基准模式 / 帮助文本）
│   │   ├── pytest_env.py             #       pytest 环境探测与命令构建（插件 / worker 数 / 参数拼装）
│   │   ├── machine_info.py           #       机器信息采集与耗时表格渲染
│   │   ├── doc_writer.py             #       test-coverage.md 环境表与模式计数表自动更新
│   │   ├── report_html.py            #       分阶段测试汇总页渲染
│   │   ├── portability.py            #       CI portability 等价探针（隐式编码严格档 + 需求文件 locale 解码）
│   │   └── runner.py                 #       运行编排（目录准备/归档 / 单模式 / 分阶段执行 / 探针模式分发）
│   ├── _shared/                      #   跨脚本共享设施包（共享库一律在子目录，顶层只留可运行入口）
│   │   ├── __init__.py               #       包标记（说明两模块职责与引用方式）
│   │   ├── checklib.py               #       检查脚本共享设施（统一 CLI 契约 / 输出 / 路径 / 文档区间解析 / 结论缓存）
│   │   └── traces_common.py          #       代码注释域与用户文档域共用的历史叙述正则单一来源
│   ├── _guardrails/                  #   设计护栏规则声明包（入口 check-style-guardrails.py 只留判定与渲染）
│   │   ├── __init__.py               #       包标记（原面 re-export）
│   │   └── rules.py                  #       检查域/圆角·字阶·间距档位/正则/存量豁免表（纯声明，无 I/O）
│   ├── _perf_report/                 #   性能基准报告渲染包（入口 test-perf-report.py 只留采样与门禁判定）
│   │   ├── __init__.py               #       包标记（原面 re-export）
│   │   └── report.py                 #       报告 Markdown 组装 + 达标判定 + PerfSample 样本规模契约
│   ├── _release/                     #   发布编排内部实现包（入口 release.py 只保留路径常量/env 投影/薄包装/main）
│   │   ├── __init__.py               #       子包标记（拆分纪律说明：下沉模块只收显式参数）
│   │   ├── _common.py                #       共享原语（ReleaseError / 子进程执行原语 exec_command）
│   │   ├── _cli.py                   #       argparse 装配（全部子命令与选项）+ 命令分派 run_cli（解析/计时/错误码）
│   │   ├── _commands_base.py          #       命令共用原语（耗时埋点/预检/git 探测/发布戳/归档路径推导）
│   │   ├── _commands_prep.py          #       准备阶段命令（check / archive-init / prepare / archive）
│   │   ├── _commands_ship.py          #       交付阶段命令（refresh / evolution / publish / devbump）
│   │   ├── _versioning.py            #       版本号解析/渲染纯函数（X.Y.Z-dev 推导与改写 / 归档名派生）
│   │   ├── _changelog_archive.py     #       changelog 发布段迁出与归档追加（纯文本变换）
│   │   ├── _archive_flow.py          #       归档迁移命令编排（ArchiveContext 显式路径 / 先算后写 / 前置缺件清单）
│   │   ├── _archive_init.py          #       新小版本归档骨架初始化（三份归档 + 目录树块 + 三处索引行，幂等）
│   │   ├── _ledger_archive.py        #       台账/设计文档归档迁移（rf 表块整块搬运+占位/头部追加/索引延展 / plan 完成节扁平搬入 / docs/plan 强信号候选+引用与目录树搬迁 / 三态门禁判定）
│   │   ├── _timing.py                #       发布耗时埋点（分步计时 + logs/release.jsonl 追加记录）
│   │   ├── _gate.py                  #       P2 门禁编排（verify+regression 并行 / 十守护 / 设计护栏 / gate 通过戳）
│   │   ├── _hygiene.py              #       开发期本地卫生（陈旧 .pyc 统计与清理，refresh 收尾最佳努力调用）
│   │   ├── _local_gate.py           #       check 的本地门禁前置（统计快照核对 + dev-verify 全量，防「只跑局部测试就进 gate」）
│   │   └── _evolution.py             #       版本演进快照统计与表格回写（git 清单 + 逐文件行数）
│   └── test-smoke-web.py                 #   Web 模式 HTTP 冒烟脚本（test_client 全链路验证，可独立运行）
├── docs/                         # 项目文档
│   ├── manuals/                      #   用户手册分册
│   │   ├── README.md                 #     手册总索引（场景导航 + 阅读路径 + 界面用词对照）
│   │   ├── data-and-backup.md        #     数据与备份（目录用途/备份迁移/版本升级核对/重置卸载）
│   │   ├── datasource.md             #     数据源一览
│   │   ├── datasource-reliability.md #     数据源可靠性文档（运维视角）
│   │   ├── faq.md                    #     常见问题解答
│   │   ├── how-to-config-reference.md #    配置参考：逐项详解（A/B/C/E…S 逐节逐键，含默认值与判定口径）
│   │   ├── how-to-config-llm-reference.md #   LLM 参考附录（逐家 provider 配置示例 + 完整模型定价表）
│   │   ├── how-to-config-llm.md      #     LLM 配置指南
│   │   ├── how-to-config.md          #     配置说明（字段总表 + 市场时段/缓存 TTL + 功能开关）
│   │   ├── how-to-use-tui-menu.md    #     TUI 菜单操作指南
│   │   ├── how-to-use-web-mode.md    #     Web 浏览器模式使用指南
│   │   ├── how-to-use-cli-mode.md    #     CLI 命令行模式使用指南
│   │   ├── how-to-start.md           #     快速上手
│   │   └── reports-instruction.md    #     报告使用说明
│   ├── managements/                  #   管理文档
│   │   ├── DESIGN.md                 #     设计语言契约（Web/报告 UI 改动首个读取入口：色彩角色/字阶/组件六态/断点/护栏）
│   │   ├── DESIGN-TUI.md             #     终端交互契约（TUI 改动首个读取入口：键分工总表/提示四成分/默认项标注/术语对照/反馈口径/护栏/Known Gaps）
│   │   ├── changelog.md              #     变更日志
│   │   ├── developer-guide.md        #     开发者指南（开发纪律/门禁/测试/脚本/发布）
│   │   ├── folders.md                #     目录结构
│   │   ├── llm-technical.md          #     LLM 技术设计
│   │   ├── plan.md                   #     总体实现计划
│   │   ├── requirements.md           #     需求规格说明
│   │   ├── scripts-reference.md      #     辅助脚本参考（60+ 脚本按用途分类：设计逻辑 + 使用逻辑；无版本头）
│   │   ├── review-findings.md        #     自审记录
│   │   ├── technical.md              #     技术设计文档
│   │   ├── test-coverage.md          #     测试覆盖率统计
│   │   └── testplan.md               #     测试计划
│   ├── archive/                      #   版本归档（按 minor 版本分区）
│   │   ├── v0.1.x/                            # v0.1.x 版本归档
│   │   │   ├── archived_changelog.0.1.x.md       # 变更日志归档 v0.1.x
│   │   │   ├── archived_plan.0.1.x.md            # 实现计划归档 v0.1.x
│   │   │   └── archived_review-findings.0.1.x.md # 自审记录归档 v0.1.x
│   │   ├── v0.2.x/                            # v0.2.x 版本归档
│   │   │   ├── archived_changelog.0.2.x.md       # 变更日志归档 v0.2.x
│   │   │   ├── archived_plan.0.2.x.md            # 实现计划归档 v0.2.x
│   │   │   ├── archived_review-findings.0.2.x.md # 自审记录归档 v0.2.x
│   │   │   ├── archived-data-source-pre-study.md  # 数据源可行性预研报告
│   │   │   ├── data-degradation/                  # 数据降级处理方案
│   │   │   │   ├── d-iteration-data-degradation-design.md     # 数据降级设计
│   │   │   │   ├── d-iteration-data-degradation-iteration-plan.md # 数据降级迭代计划
│   │   │   │   └── data-degradation-refactoring.md            # 数据降级重构
│   │   │   ├── fund-deep-analysis/                # 基金深度分析
│   │   │   │   └── fund-deep-analysis.md       # 基金持仓深度分析迭代
│   │   │   ├── profit-forecast-sector-flow/          # 盈利预测与资金流向
│   │   │   │   └── profit-forecast-sector-flow-akshare-integration.md # 盈利预测+资金流向 akshare 集成
│   │   │   ├── report-early-warning/              # 预警优化
│   │   │   │   └── early-warning-and-p1-optimization.md # 预警与 P1 优化
│   │   │   ├── report-section-order-config/       # 报告章节顺序
│   │   │   │   └── report-section-order-config.md # 报告章节顺序配置
│   │   │   ├── test-coverage-map/                 # 测试覆盖地图
│   │   │   │   ├── test-coverage-map.md           # 测试覆盖地图文档
│   │   │   │   └── validate_coverage_map.py       # 覆盖地图验证脚本
│   │   │   └── test-runtime-optimization/         # 测试运行优化
│   │   │       └── test-runtime-optimization.md # 测试运行优化
│   │   ├── v0.3.x/                            # v0.3.x 版本归档
│   │   │   ├── archived_changelog.0.3.x.md       # 变更日志归档 v0.3.x
│   │   │   ├── archived_plan.0.3.x.md            # 实现计划归档 v0.3.x
│   │   │   ├── archived_review-findings.0.3.x.md # 自审记录归档 v0.3.x
│   │   │   ├── refactor-cache-engine/             # 缓存引擎重构
│   │   │   │   └── cache-refactor-plan.md         # 缓存引擎重构计划
│   │   │   ├── refactor-excel-generator/          # Excel 生成器重构
│   │   │   │   └── excel-generator-split-plan.md # Excel 生成器拆分计划
│   │   │   ├── refactor-html_writer/              # HTML 写入器重构
│   │   │   │   └── html_writer_split.md      # HTML 写入器拆分
│   │   │   ├── refactor-llm_split_design/         # LLM 拆分重构
│   │   │   │   └── llm_split_design.md       # LLM 拆分设计
│   │   │   ├── refactor-market_value_split_design/ # 市值拆分重构
│   │   │   │   └── market_value_split.md     # 市值拆分设计
│   │   │   ├── refactor-summary-llm-usage/        # LLM 用量摘要重构
│   │   │   │   └── summary-llm-usage-split-plan.md # LLM 用量摘要拆分计划
│   │   │   └── test-verify-mode-optimization/     # 测试 verify 模式运行优化
│   │   │       └── verify_mode_optimization.md # 测试 verify 模式运行优化
│   │   ├── v0.4.x/                            # v0.4.x 版本归档
│   │   │   ├── archived_changelog.0.4.x.md       # 变更日志归档 v0.4.x
│   │   │   ├── archived_plan.0.4.x.md            # 实现计划归档 v0.4.x
│   │   │   ├── archived_review-findings.0.4.x.md # 自审记录归档 v0.4.x
│   │   │   ├── portfolio-history-comparison/      # 组合历史对比
│   │   │   │   ├── F-portfolio-history-comparison.md        # F 迭代计划与技术设计
│   │   │   │   └── html-report-chart-native-canvas-fallback-plan.md # HTML Canvas 渲染修复
│   │   │   └── test-add-config-edge-testcase/     # 边缘测试配置
│   │   │       └── y5-edge-test-config-env.md     # 边缘测试配置环境
│   │   ├── v0.5.x/                            # v0.5.x 版本归档
│   │   │   ├── archived_changelog.0.5.x.md       # 变更日志归档 v0.5.x
│   │   │   ├── archived_plan.0.5.x.md            # 实现计划归档 v0.5.x
│   │   │   ├── archived_review-findings.0.5.x.md # 自审记录归档 v0.5.x
│   │   │   ├── portfolio-benchmark-comparison/    # I 迭代基准指数对比归档
│   │   │   │   ├── I-comparative-benchmark-design.md    # I 迭代基准对比设计
│   │   │   │   ├── I-comparative-benchmark-iteration.md # I 迭代基准对比迭代计划
│   │   │   │   └── plan-iter-8-excel-benchmark-columns.md # I 迭代 Excel 基准指数列
│   │   │   └── report-board-visibility-configable/ # 看板可见性配置
│   │   │       └── g-board-visibility-iteration-plan.md # 看板可见性配置迭代计划
│   │   ├── v0.6.x/                            # v0.6.x 版本归档
│   │   │   ├── archived_changelog.0.6.x.md       # 变更日志归档 v0.6.x
│   │   │   ├── archived_plan.0.6.x.md            # 实现计划归档 v0.6.x
│   │   │   ├── archived_review-findings.0.6.x.md # 自审记录归档 v0.6.x
│   │   │   ├── llm-multi-provider/                # 多 LLM Provider 链式服务归档
│   │   │   │   ├── llm-multi-provider-design.md       # 多 LLM Provider 链式服务技术设计
│   │   │   │   └── llm-multi-provider-iteration-plan.md # 多 LLM Provider 链式服务迭代计划
│   │   │   └── cli-mode/                          # CLI 命令行模式归档
│   │   │       ├── cli-mode-iteration-plan.md     # CLI 迭代计划
│   │   │       └── cli-mode-technical-design.md   # CLI 技术设计
│   │   ├── v0.7.x/                            # v0.7.x 版本归档
│   │   │   ├── archived_changelog.0.7.x.md       # 变更日志归档 v0.7.x
│   │   │   ├── archived_plan.0.7.x.md            # 实现计划归档 v0.7.x
│   │   │   ├── archived_review-findings.0.7.x.md # 自审记录归档 v0.7.x
│   │   │   ├── porting-to-rust-vs-java/           # Rust/Java 移植评估归档
│   │   │   │   └── porting-to-rust-vs-java-analysis.md # 移植技术分析（依赖替代风险 / 两方案成本对比）
│   │   │   └── better-investment-advice/           # 投资建议改进分析讨论
│   │   │       ├── discussion-better-investment-advice.md             # 可行性调研：6 层改进方向与实施路径
│   │   │       ├── better-investment-task.md                          # 最小粒度工作任务分解（86 任务）
│   │   │       ├── data-channels-schema.md                            # 数据通道 Schema 文档
│   │   │       ├── data-source-stability-test-report.md               # 数据源稳定性专项测试报告
│   │   │       ├── better-investment-performance-test-report.md        # 端到端性能基准测试报告
│   │   │       ├── enhanced-llm-strategy.md                    # 增强型 LLM 策略引擎设计
│   │   │       ├── r1-insert-feasibility-audit-into-discussion.py      # R1 数据源可行性审查插入脚本（最终版）
│   │   │       ├── debug-find-insert-anchor_r1.py                     # R1 锚点定位合并调试脚本
│   │   │       ├── llm-hallucination-report_expert-review.md           # LLM 幻觉率采样报告（expert_review 模块）
│   │   │       ├── llm-hallucination-prompts_expert-review.md          # 幻觉采样完整 Prompt 构造（Dry-Run）
│   │   │       └── llm-hallucination-sample-output_expert-review.txt   # 幻觉采样 LLM 原始输出样本
│   │   ├── v0.8.x/                           # v0.8.x 版本归档
│   │   │   ├── archived_changelog.0.8.x.md       # 变更日志归档 v0.8.x
│   │   │   ├── archived_plan.0.8.x.md            # 实现计划归档 v0.8.x
│   │   │   ├── archived_review-findings.0.8.x.md # 自审记录归档 v0.8.x
│   │   │   ├── tiantian-split/               #   tiantian.py 大文件拆分记录
│   │   │   │   └── tiantian-split.md          #     tiantian.py 拆分记录
│   │   │   ├── fundstyle-split/               #   fund_style_analysis.py 大文件拆分记录
│   │   │   │   └── fundstyle-split.md         #     fund_style_analysis.py 拆分记录
│   │   │   ├── datasource-matrix/             #   数据源可用性矩阵实现记录
│   │   │   │   └── datasource-matrix.md       #     数据源可用性矩阵实现记录
│   │   │   ├── datasource-reliability-documentation/   #   数据源可靠性文档
│   │   │   │   └── datasource-reliability-documentation.md # 数据源可靠性文档
│   │   │   ├── perf-benchmark/               #   性能基准体系（自动计时/回归检测/趋势工具）
│   │   │   │   ├── perf-completion-summary.md #     性能基准体系归档摘要
│   │   │   │   └── perf-design-and-verification.md # 性能基准体系设计方案
│   │   │   └── batch-parallel/             #   批量并行调度重构（BatchDispatcher + 线程池配置）
│   │   │   │   ├── batch-parallel-design.md #      批量并行调度技术设计
│   │   │   │   └── batch-parallel-iteration-plan.md # 批量并行调度迭代计划
│   │   ├── v0.9.x/                           # v0.9.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │   │   ├── archived_plan.0.9.x.md            # 实现计划归档 v0.9.x
│   │   │   ├── archived_changelog.0.9.x.md       # 变更日志归档 v0.9.x
│   │   │   ├── archived_review-findings.0.9.x.md # 自审记录归档 v0.9.x
│   │   │   ├── abandoned-design/               #   已放弃的设计方案（Brinson 业绩归因）
│   │   │   │   └── brinson-attribution-abandoned.md # 业绩归因（Brinson）放弃设计
│   │   │   ├── chartjs-upgrade/               #   交互式 HTML 报告升级设计（8 迭代）
│   │   │   │   ├── plan-chartjs-report-upgrade.md   # Chart.js 升级实施方案
│   │   │   │   ├── plan-chartjs-risk-analysis.md    # Chart.js 升级风险/收益/架构分析
│   │   │   │   └── iter7-verification-checklist.md # Iter 7 浏览器人工验证清单
│   │   │   ├── factor-exposure/                 #   因子暴露分析设计
│   │   │   │   └── plan-factor-exposure.md      #     因子暴露分析设计
│   │   │   ├── correlation-drawdown/            #   相关性矩阵 + 回撤/净值设计与实施
│   │   │   │   ├── plan-correlation-drawdown.md #     分析功能基础增强设计
│   │   │   │   └── plan-correlation-drawdown-implementation.md # 实施总纲
│   │   │   ├── first-run-wizard/                #   首次运行引导设计与实施
│   │   │   │   ├── plan-first-run-wizard.md     #     首次运行引导设计
│   │   │   │   └── plan-first-run-wizard-implementation.md # 实施细节
│   │   │   ├── whatif-simulation/               #   调仓 What-if 模拟设计
│   │   │   │   └── plan-whatif-simulation.md    #     调仓 What-if 模拟设计
│   │   │   ├── whatif-backtest/                 #   调仓 What-if 指定生效日时序回测设计
│   │   │   │   └── plan-whatif-backtest.md      #     调仓 What-if 指定生效日时序回测设计
│   │   │   ├── portfolio-evolution/             #   多快照趋势追踪/组合演进设计
│   │   │   │   └── plan-portfolio-evolution.md  #     多快照趋势追踪设计
│   │   │   ├── html-dark-mode/                  # 报告只有浅色且颜色全硬编码、晚间查看刺眼 → 明暗双主题
│   │   │   │   ├── dark-mode-implementation.md  #     暗色模式实施记录
│   │   │   │   └── dark-mode-plan.md    #     暗色模式实施计划
│   │   │   ├── fix-deepseek-thinking/           #   DeepSeek thinking 思考耗尽修复设计
│   │   │   │   └── plan-fix-deepseek-thinking-exhaustion.md # 思考耗尽修复方案
│   │   │   └── qa-concentration-chart-optimization/ # 集中度问答 + 穿透柱状图优化修复设计
│   │   │       └── plan-fix-qa-concentration-and-chart-optimization.md # 集中度问答 + 柱状图优化修复
│   │   ├── v0.10.x/                         # v0.10.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │   │   ├── archived_plan.0.10.x.md            # 实现计划归档 v0.10.x
│   │   │   ├── archived_changelog.0.10.x.md       # 变更日志归档 v0.10.x
│   │   │   ├── archived_review-findings.0.10.x.md # 自审记录归档 v0.10.x
│   │   │   ├── investment-features/         #   投资功能优化 + 章节归并设计文档
│   │   │   │   ├── plan-investment-features.md  #     投资分析功能优化设计（需求×数据源×章节归并）
│   │   │   │   └── plan-investment-iteration.md #     投资功能优化 21 轮迭代实施计划（每轮量化验收）
│   │   │   ├── log-visualization/           #   日志可视化三端设计文档（CLI+TUI+Web）
│   │   │   │   └── plan-log-visualization.md #     CLI+TUI+Web 日志查看与数据源健康历史接线设计
│   │   │   ├── task-code-traces-gate/       #   任务编号标识符/注释门禁增强设计
│   │   │   │   └── plan-task-code-traces-gate.md #     check-code-traces 扩展（IDENT 维度 + 系列代号）
│   │   │   ├── toc-llm-marking/             #   目录 LLM 章节标记设计（橙色加粗 + 🧠 图标）
│   │   │   │   └── plan-toc-llm-marking.md  #     TOC/横向导航 LLM 章节标记（复用 --orange-text）
│   │   │   ├── web-ui/                      #   轻量 Web UI 实施归档（含日志可视化设计）
│   │   │       ├── plan-web-ui.md              #     轻量 Web UI 计划
│   │   │       ├── plan-web-ui-implementation.md # Web UI 实施拆分设计（评估/约束/拆分/安全/API/阶段）
│   │   │       └── web-ui-verification-checklist.md # 浏览器人工走查勾选清单（渲染/上传/进度/响应式/按钮态五类 UX 项）
│   │   │   ├── web-holdings-input-modes/    #   Web 持仓输入模式实施归档
│   │   │   │   └── plan-web-holdings-input-modes.md # Web 持仓输入模式试算隔离/正式共享实现设计
│   │   │   ├── web-config-edit/              #   Web 配置编辑实施归档
│   │   │   │   └── web-config-edit.md        #   Web 配置编辑设计（完整镜像 TUI 可编辑配置全集）
│   │   │   ├── readme-svg-layout/            # README 是纯文字墙、无任何可视化 → SVG 结构图与排版重排
│   │   │   │   └── plan-readme-svg-layout.md #     README 嵌入 SVG 架构图 + 排版优化设计
│   │   │   ├── env-benchmark-doc-update/     #   环境耗时对照文档自动更新
│   │   │   │   └── plan-env-benchmark-doc-update.md # test-coverage.md 环境耗时表按主机名自动回填
│   │   │   ├── datasink-financial-report-digest/ #   DataSinking 财报接入设计归档（持仓个股财报摘要）
│   │   │   │   └── datasink-financial-report-digest-design.md # 凭据/计划感知限速/配额护栏/章节装配与渲染接线
│   │   │   └── dedup-calibration/            #   新闻去重阈值校准分析归档（dedup 逐条样本 + 分布 + 判定）
│   │   │       ├── dedup-calibration-report.md #   dedup 阈值校准计数（锚点总数、跨源跳过分布、阈值依据）
│   │   │       ├── dedup-review.md           #   dedup 灰色带（bg≥2 ratio 0.35~0.40）逐条示例 + 人工判定
│   │   │       └── cross_merge_bg2_review.md #   cross_merge_bg2 30 条去重后独立 pair 分析
│   │   │   ├── tradingagents-borrowing/      #   外部 TradingAgents-astock 借鉴系列（决策反思 + LLM 输入/输出质量治理）
│   │   │   │   ├── reflection-decision-loop-analysis.md # 决策跨期反思闭环机理深入分析
│   │   │   │   ├── decision-reflection-implementation.md # 决策跨期反思闭环实现设计（分层依赖/账本契约/报告接缝）
│   │   │   │   ├── experimental-features-ui-surfacing.md # 实验性功能开关上屏（TUI 菜单 S + Web 配置面板由注册表驱动）
│   │   │   │   ├── llm-quality-signal-analysis.md # 信号预消化/模块质量分级/结构化决策头深入分析
│   │   │   │   ├── signal-pre-digestion-implementation.md # 信号预消化实现设计（资金流修复 + 信号块实验增强/缓存后缀同源）
│   │   │   │   └── decision-header-parse-implementation.md # 决策头结构化实现设计（词表归一/结构化头/缓存后缀同源）
│   │   │   ├── augur-borrowing/              #   外部 augur 借鉴系列（决策结算纪律 + 健壮性）
│   │   │   │   ├── augur-borrowing-analysis.md # augur 借鉴评估（决策-结算学习/确定性信号沉淀/健壮性三件套）
│   │   │   │   ├── signal-ledger-implementation.md # 确定性信号沉淀实现设计（分层共享原语/实时-非实时标签纪律）
│   │   │   │   └── robustness-suite-implementation.md # 健壮性三件套实现设计（数值归一/失败原因可读/系统自检）
│   │   │   ├── openbb-borrowing/             #   外部 OpenBB Platform 借鉴系列（数据层适配 + 测试基建 + 凭据声明）
│   │   │   │   ├── openbb-data-provider-analysis.md # OpenBB 数据层工程借鉴评估（标准字段/Fetcher 三段适配 + 记录-回放）
│   │   │   │   ├── datasource-adapter-contract-design.md # 数据源适配契约设计（标准字段三段适配 + 适配器注册）
│   │   │   │   ├── datasource-cassette-replay-design.md # 数据源记录-回放实现设计（真实响应体录制/离线回放）
│   │   │   │   └── datasource-credential-ready-design.md # 数据源凭据声明与就绪指引设计（凭据声明表/就绪判定/上屏指引）
│   │   │   ├── llm-fingerprint-prompt-coverage/ # LLM 模块缓存指纹提示词覆盖设计（自审缺陷修复）
│   │   │   │   └── llm-fingerprint-prompt-coverage-design.md # 指纹覆盖判据/一次渲染两侧共享/辩论三键口径
│   │   │   ├── feature-switch-registry/ #   功能开关注册表统一设计归档（面板可见性/默认值/产物自述解耦）
│   │   │   │   └── feature-switch-registry-unification-design.md # 单条开关声明 + 分组属性 + 三渠道入口派生
│   │   │   ├── feature-switch-grouping/ #   功能开关面板分组重构设计归档（作用域四分组换轴）
│   │   │   │   └── feature-switch-grouping-redesign.md # 作用域四分组 + 生命周期 experimental 字段解耦（守护先行/四迭代）
│   │   │   ├── feeder-fund-penetration/ #   联接基金穿透与基金持仓取数通道修正设计归档
│   │   │   │   └── feeder-penetration-and-holdings-fetch-design.md # 取数阶梯次序修正 + 目标 ETF 代理底层暴露
│   │   │   ├── financial-indicator-source/ #   基本面数据源主备与财务指标提取设计归档
│   │   │   │   └── financial-indicator-source-design.md # 标准字段契约/全文解析支路/真实估值分位(TTM)/底座门禁/LLM 注入
│   │   │   ├── report-followup-qa/ #   报告对话式追问设计归档（qa 独立子包设计）
│   │   │   │   └── report-followup-qa-design.md # 报告对话式追问设计（上下文从报告 HTML 提取/会话服务/报告页区块/TUI [Q] 入口/转正路径）
│   │   ├── v0.11.x/                         # v0.11.x 版本归档（0.11 系列首份）
│   │   │   ├── archived_changelog.0.11.x.md       # 变更日志归档 v0.11.x
│   │   │   ├── archived_plan.0.11.x.md            # 实现计划归档 v0.11.x
│   │   │   ├── archived_review-findings.0.11.x.md # 自审记录归档 v0.11.x
│   │   │   ├── section-consolidation/     # 报告章节整合设计归档（设计层 + 实施层）
│   │   │   │   ├── section-consolidation-design.md    # 设计层：四项合并/可见性模型扩展/约束对照/验收标准
│   │   │   │   └── section-consolidation-iteration.md # 实施层：命名统一总表/接缝地图/逐批施工单/十轮复盘记录
│   │   │   ├── prosperity-framework/      # 景气度框架诊断设计归档（投资分析方法引入，实验性功能）
│   │   │   │   └── prosperity-framework-design.md # 上游归属与许可/数据可得性映射/六维口径（含两轮修订）/契约/约束对照/验收
│   │   │   ├── hithink-data-source/       # 同花顺官方数据接入设计归档（五阶段接入方案）
│   │   │       └── hithink-financial-data-design.md # 覆盖边界/四域接入方案/实测字段与限流/验证计划/架构约束自查标准
│   │   │   ├── dedup-anchor-calibration/  # 旧样本无规则版本字段、与新样本混算 → 分时代校准复核
│   │   │   │   └── dedup-anchor-calibration.md # 锚点混代证据、规则重判分布、建议处置清单
│   │   │   ├── tradingagents-cn-borrow-research/ # 借鉴批候选研究归档（现状比对 + 终态标注）
│   │   │   │   └── tradingagents-cn-borrow-candidates-research.md # 候选借鉴分析（落地项/未采纳项/共性教训）
│   │   │   └── llm-depth-selfreview-source-override/ # LLM 深度自审来源覆盖整体设计归档
│   │   │       └── report-depth-selfreview-source-override-design.md # 报告深度档位/LLM 生成后自检/调用级源指定设计（形态/分层不重叠/运行作用域/约束对照）
│   │   ├── v0.12.x/                         # v0.12.x 版本归档（0.12 系列首份）
│   │   │   ├── archived_changelog.0.12.x.md       # 变更日志归档 v0.12.x
│   │   │   ├── archived_plan.0.12.x.md            # 实现计划归档 v0.12.x
│   │   │   ├── archived_review-findings.0.12.x.md # 自审记录归档 v0.12.x
│   │   │   ├── awesome-design-md-borrow-research/ # Web 展示借鉴研究归档
│   │   │   │   └── awesome-design-md-borrow-candidates-research.md # 73 份 DESIGN.md 骨架与样板要点 + 我方两面样式差距映射（6 立项 / 5 不采纳）
│   │   │   ├── gs-quant-borrow-research/      # gs-quant 借鉴研究归档
│   │   │   │   └── gs-quant-borrow-candidates-research.md # 高盛量化库剖析与候选清单（2 立项 / 1 参照 / 10 不采纳）
│   │   │   ├── llm-token-optimization/        # token 花在哪、能否省 → 实测画像与计费口径纠正（结论：维持现状）
│   │   │   │   └── llm-token-optimization-research.md # 真实运行画像 + 共享前缀前移评估 + provider/pacing 差异（结论维持现状）
│   │   │   ├── vibe-trading-borrow-research/  # Vibe-Trading 借鉴研究归档
│   │   │   │   └── vibe-trading-borrow-candidates-research.md # 项目剖析与候选清单（4 立项 / 6 不采纳）
│   │   │   ├── fund-purchase-limit/          # 基金申购限购三份设计归档
│   │   │   │   ├── fund-purchase-limit-design.md # 申购限购接入设计（天天基金单口径/四层稳定性保障/持仓展示/合并联动二期）
│   │   │   │   ├── fund-purchase-limit-llm-context-design.md # 限购信息接入 LLM 分析维度设计（全章节单源块/统一附录注入/指纹与降级矩阵）
│   │   │       └── fund-purchase-limit-advice-design.md # 限购接入调仓/建议可行性设计（三真实面重定位/受限索引单源/四迭代验收）
│   │   │   ├── holding-change-review/         # 只有持仓快照、回答不了「这次变了什么、为什么」→ 变动复盘归因
│   │   │   │   └── holding-change-review-design.md # 持仓变动复盘设计（快照事件级：change_event 契约/先决门槛/四迭代）
│   │   │   └── whatif-cost-benchmark/          # 截面比较回答不了「生效日后 as-if 净值怎么走」→ 窗口回测与基准对比
│   │   │       ├── whatif-cost-benchmark-design.md # What-if 回放成本建模与基准对比设计（FIFO 成本模型/费率三级可得/基准三线）
│   │   │   ├── factor-zoo-catalog/             # 确定性信号源全靠手写注册、无法横向评估取舍 → 因子目录化评测
│   │   │       ├── factor-zoo-catalog-design.md    # 因子动物园目录评测设计（25 因子五族 × A/B/C 三指标 go-no-go 评测方案与判定）
│   │   │   ├── event-window-impact/                # 只答「文本上相关」不答「事件后真的动了吗」→ 事件窗对照补数据侧证据
│   │   │       ├── event-window-impact-design.md # 事件窗对照设计（event_study 参照/先决门槛/四迭代）
│   │   │   └── rebalance-schedule-replay/         # 约束检查只答「能不能调」不答「调了会怎样」→ 纪律回放
│   │   │       └── rebalance-schedule-replay-design.md # 调仓纪律回放设计（规则契约/成本软依赖/四迭代）
│   │   ├── v0.13.x/                         # v0.13.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │   │   ├── archived_changelog.0.13.x.md       # 变更日志归档 v0.13.x
│   │   │   ├── archived_plan.0.13.x.md            # 实现计划归档 v0.13.x
│   │   │   ├── archived_review-findings.0.13.x.md # 自审记录归档 v0.13.x
│   │   │   ├── holding-cost-position/      # 4 列持仓看不出「成本买在历史区间什么位置」→ 追涨/摊薄定位
│   │   │   │   └── holding-cost-position-design.md # 持仓成本相对历史价格区间位置设计
│   │   │   ├── llm-cost-optimization/       # LLM 调用成本优化分析归档
│   │   │   │   └── llm-cost-optimization.md # 实测画像 + 行动清单（计费口径/闲时调度/模型映射/output_brief 机制）
│   │   │   ├── perf-observability/          # 让台账能回答「时间花在哪、为什么花、是否退化」（原先只有 8 个阶段名，LLM 单桶占 91%）
│   │   │   │   └── perf-observability-design.md # perf_history 观测面设计（细分/计数/上下文维度/对比门禁）
│   │   │   ├── report-browser-verification/ # 报告产物跨环境可读性验收（自包含/断网/打印/窄屏/微信 X5）：生成的单文件 HTML 到别人机器上还看得清吗
│   │   │   │   └── report-browser-verification.md # 六项拆「可自动化 / 须人工」+ 逐项实测结论与复跑命令（模板或 Chart.js 改动后照此复跑）
│   │   │   ├── trace-vocabulary-single-source/ # 两检查脚本的痕迹词表 31 条正则逐字节重复、判定口径易分叉 → 单源化
│   │   │   │   └── trace-vocabulary-single-source.md # 共享正则与文档域模式表的单一来源（`_traces_common`、`_traces_doc/patterns.py`）
│   │   │   ├── tui-interaction-hci/         # 13 个面板各自手写的「文案↔按键」收敛为可机检契约（与 DESIGN.md 对称）
│   │   │   │   └── tui-interaction-hci-design.md # HCI 原则对照 + 交互契约 v0 + M1~M10 措施与机检载体
│   │   │   └── tui-panel-runtime/           # 13 处面板各自手写的「读键→导航→派发→重绘」抽成单一运行时（C29 构造性成立）
│   │   │       └── tui-panel-runtime-design.md # NavState/PanelItem/panel_loop 契约 + 13 面板清单 + 8 迭代
│   │   ├── v0.14.x/                         # v0.14.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │   │   ├── archived_changelog.0.14.x.md       # 变更日志归档 v0.14.x
│   │   │   ├── archived_plan.0.14.x.md            # 实现计划归档 v0.14.x
│   │   │   └── archived_review-findings.0.14.x.md # 自审记录归档 v0.14.x
│   │   ├── v0.15.x/                         # v0.15.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │   │   ├── archived_changelog.0.15.x.md       # 变更日志归档 v0.15.x
│   │   │   ├── archived_plan.0.15.x.md            # 实现计划归档 v0.15.x
│   │   │   ├── archived_review-findings.0.15.x.md # 自审记录归档 v0.15.x
│   │   │   ├── cache-ttl-layering/                      # 同一条目的有效期由 6 层规则合成、不同调用点取到不同值（已致两次事故）→ 分层收敛
│   │   │   │   ├── cache-ttl-layering.md                # 各 TTL 的决定方、分层必要性、维持四层与只读注册表对比
│   │   │   ├── config-rework/                           # 配置体系重构（文件划分、键名与界面映射、TUI/Web 面板）
│   │   │   │   ├── config-rework-iteration-plan.md      # 分轮推进表（各轮范围、验收基准、门禁与契约）
│   │   │   │   ├── config-tui-design.md                 # TUI 面板设计（四组菜单层级/七项四组/章节显隐与章内内容/键位与分组标题纪律）
│   │   │   │   ├── config-web-design.md                 # Web 配置面设计（五域分区/块与控件/保存语义/无障碍与响应式）
│   │   │   │   ├── config-files-design.md               # 配置文件设计（八份文件边界/演进策略/config.json 取舍/书写与读取约定）
│   │   │   │   ├── config-llm-settings-design.md        # LLM 配置设计（模块为第一层的纵切结构/三层缺省继承/键位映射/升级与回滚）
│   │   │   │   ├── config-logging-design.md             # 日志配置设计（logger.json 键表与默认值/加载优先级/校验与错误/面板入口）
│   │   │   │   ├── config-panel-mockup/                 # 设计图样原型目录（自包含 HTML，数据内联，浏览器直接打开）
│   │   │   │   │   ├── index.html                       # Web 配置面板目标设计（按业务域编排；说明密度/标记/主题可切换）
│   │   │   │   │   ├── web-current.html                 # Web 配置面板现有实现（按存储文件编排）
│   │   │   │   │   ├── tui.html                         # TUI 全层级图样 · 目标设计（[C] 章节总表/[S] 报告呈现与增强/[G] 全局设置）
│   │   │   │   │   ├── tui-current.html                 # TUI 全层级图样 · 现有实现（四组开关/[D] 目录信息/[D]→[L] 调优参数）
│   │   │   │   │   ├── llm-config.html                  # LLM 配置目标设计（模块纵切结构 + 键位映射）
│   │   │   │   │   ├── llm-config-current.html          # LLM 配置现有实现（扁平结构：参数 × 模块平铺）
│   │   │   │   │   ├── tui_render.py                    # TUI 单屏渲染取样（真实处理器 + 伪终端）
│   │   │   │   │   ├── tui_capture.py                   # TUI 逐屏采集（产出帧数据到 docs/tmp，git 忽略）
│   │   │   │   │   ├── tui_build.py                     # ANSI 帧转 HTML 图样构建器
│   │   │   │   │   ├── llm_config_mock.py               # LLM 配置纵切图样生成器（读真实配置推导结构）
│   │   │   │   │   └── web_mock_build.py                # Web 配置面板图样生成器（真实注册表/配置取数，产出目标与现有两份 HTML）
│   │   │   ├── import-surface/                          # 跨模块导入面唯一出处（所有权、转发路径收敛）
│   │   │   │   └── import-surface-rename.md             # 导入所有权总表、四条规则、分批收回旧转发路径
│   │   │   ├── llm-cache-state-isolation/               # 报告级 LLM 缓存状态隔离（现象、实测证据、状态边界）
│   │   │   │   └── llm-cache-state-isolation.md         # 影响缓存键的状态源与三层处理（运行边界、指纹审计、缓存策略）
│   │   │   ├── pricing-native-currency/                 # 多币种计价（原币种展示、分组汇总、预算折算）
│   │   │   │   └── pricing-native-currency.md           # 币种桶存储、金额格式化、展示层不做汇率换算
│   │   │   ├── tui-display-modes/                       # TUI 显示模式统一（行型、状态色、关闭恒红、ANSI 截断）
│   │   │   │   └── tui-display-modes.md                 # 行型判定与分组、颜色语义、关闭恒红与截断规则
│   │   │   └── web-browser-verification/                # Web 工作台真人操作路径验收（上传/拖拽/进度/禁用态/窄屏）：浏览器里点得动、看得对吗
│   │   │       └── web-browser-verification.md         # 五类断言的可复现验证（启动 / HTTP 层证据 / headless CDP 实测 / 人工余项），红线是全程不触发生成
│   │   └── v0.16.x/                         # v0.16.x 版本归档（changelog/plan/review-findings + 设计文档）
│   │       ├── archived_changelog.0.16.x.md       # 变更日志归档 v0.16.x
│   │       ├── archived_plan.0.16.x.md            # 实现计划归档 v0.16.x
│   │       ├── archived_review-findings.0.16.x.md # 自审记录归档 v0.16.x
│   │       ├── dedup-anchor-storage/               # append-only 采集文件单消费者却无限增长 → 分片/体积目标/保留期治理
│   │       │   └── dedup-anchor-storage-design.md  # 采样/保留期+写入时刻/体积目标与分支配额/月 gzip 分片/迁移与回滚
│   │       ├── llm-critical-path-instrumentation/   # LLM 关键路径测量与调度设计归档
│   │       │   └── llm-critical-path-instrumentation-design.md # 逐模块耗时入台账/归因并入并行批/A1~A6 实测与风险
│   │       └── llm-expression-budget/               # LLM 关键路径时延治理（表达预算）评估归档
│   │           └── llm-critical-path-design.md      # 设计与量化评估（结论：不采纳；预算档/补写接缝/TTL/指纹瘦身四组实测）
│   └── plan/                          #   在办设计文档（扁平存放，原型就近建子目录）
│       ├── jev-news-judgment-evaluation.md # 判定通道迁移的对照评测方案（三方对照、语料冻结、预注册阈值）
│       ├── jev-news-judgment-design.md # 判定通道接入设计（独立于对话链、模板理由、降级矩阵）
│       ├── decision-reflection-design.md # 决策跨期反思闭环设计（可结算决策账本/结算器/反思回灌与回滚）
│
├── CLAUDE.md                         # AI 编程助手指引
├── README.md                         # 用户文档总入口（三渠道交互 + 核心亮点总览）
├── LICENSE                           # MIT 开源协议
├── pyproject.toml                    # Python 项目元数据
├── requirements.txt                  # Python 依赖清单
├── .pi/                              # pi 编程助手项目配置（项目级设置，随仓库发布）
│   ├── settings.json                 #   项目级设置：changelog 折叠 / 静默启动 / fullscreen
│   └── models.json                   #   pi 模型配置（DeepSeek 编程档：temperature 0.0 + maxTokens 收窄；需软链到 ~/.pi/agent/ 生效）
├── .editorconfig                     # 编辑器编码规则（*.ps1 + requirements.txt 强制 UTF-8 BOM）
└── .gitignore                        # Git 忽略规则
```

> 注意：目录树为主层级结构，测试文件数和文件行数随版本迭代变化。
