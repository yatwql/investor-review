# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.18.0]**（2026-11-12）——已发布版本段随发布移入 [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.18.1-dev] - 开发中（未发布）

### 测试

- **补两处新代码的直接覆盖（rf-1137）**：`is_otc_nav_disclosed` 原先只在别的用例里被 patch，补披露时点边界（19:59 / 20:00 / 早间）与 naive/跨时区换算 5 条；`ProviderState.cooldown_override` 补落盘回读 1 条（否则重启后自定义冷却期会丢）。
- **发布编排测试按命令域拆分**：`test_release_tool_gate.py` 1147 行（测试登记线 900）按域拆为三份——`gate` 保留门禁编排与归档前置、`test_release_tool_publish.py` 收 publish/devbump 与 check 本地门禁前置、`test_release_tool_refresh.py` 收 refresh 条件化与 archive-init/prepare 文档手术命令；运行态路径隔离夹具下沉 `_release_fixtures.isolate_release_runtime_paths`（三份共用，断言与用例数不变）。P4 存量监控清单对应行随之删除。

### 重构

- **判断依据模块按关注点拆为聚合门面 + 两子模块**：`report/decision_basis.py` 962 行（主程序登记线 700）拆为聚合门面（风险预算 / 纪律明细 / 信号可信度仲裁 / 装配入口 524 行）+ `decision_basis_signals.py`（信号清单装配与回测结论登记）+ `decision_basis_settlement.py`（结算摘要与按视界历史表现）；子模块符号由门面原路径 re-export，导入面与 `decision_basis_data` 契约不变。P4 存量监控清单对应行随之删除。

### 性能

- **渲染期取数前置 + 单轮复用加锁**：基金业绩排名与基金风格取数原本发生在 HTML「区块装配」内（冷缓存实测 4~6s），既让该计时点看起来像渲染慢，也把取数算在渲染阶段；现由 `prepare_report_data` 的「渲染前置取数」段预取，并把 `_build_perf_data` / `_fetch_fund_holdings_with_period` 接入 `_run_scope.run_memo`（补 per-key 锁，同 key 并发只算一次），风格预取的开关判定改走 `is_enable_fund_deep_analysis()` 解析器（缺键默认 True）——直接读原始键会把「配置未写」当关闭，预取白做。`technical.md` 编排器职责链与需求侧 breakdown 清单同步。穿透块的附属取数（盈利预测 2000+ 只、股息率）同批纳入预取——此前在渲染阶段载入约 2.5s，实测 `区块装配` 从 6.8s 降到 2.6s 后剩下的主要部分就是它。
- **HTML 生成慢段归因纠正 + 穿透单轮复用**：原 `面板视图装配` 计时点覆盖「函数入口 → 该 mark」，把 `html_sections.assemble_sections` 的取数（穿透 / 基金业绩 / 基金风格 / 财务指标）也算进「视图拼装」，实测 1.4s ~ 6.8s 双峰全落在取数冷热上而非渲染。现拆出 `区块装配` 计时点，并把 `compute_penetration_top10` 接入 `_run_scope.run_memo`（同轮同输入只算一次，HTML 与 Excel 两端共用，报告边界清空），`developer-guide.md` 慢段排查表与 `technical.md` 编排器职责链同步。

### 新增

- **建议级硬约束 + 判决入账口径（plan-253 P3 前半）**：`research_contract.validate_recommendation()` 在校验期拒绝「待复核 / 不可执行（blocked/not_applicable）却带可执行数量」的建议（不依赖提示词自律）；决策登记按模块判决分流——`reject`（主张与证据矛盾）不入账以免污染命中率，`evidence_needed`/`revise` 照常入账但降为低优先并标注「未验证：证据不足，仅参考」。

- **LLM 复盘结论结构化契约（plan-253 P1，开关 `llm_research_contract` 默认关）**：新增 `llm/evidence_index.py`（由该模块提示词输入块生成 `ev:<kind>:<稳定键|8 位哈希>` 证据索引，七类来源、只给摘要）、`llm/research_contract.py`（契约头解析——复用决策头括号扫描；校验证据存在/失效条件必填/主张上限，并给 ready/revise/evidence_needed/reject 判决，模型自证 ready 不被采信）、`report/llm_contract_block.py`（展示层：HTML 折叠块 + Excel 小节，正文机器可读行展示前剥离）；生成后一遍落运行作用域载体，报告边界清空。开关关闭时提示词与产物逐字节不变；提示词文本盐递增 `rate-caliber-6`（一次性换键）。P2（预算受限补证）与 P3（决策书 + 建议硬约束）未实施。

- **建议后验评估：不动作类纳入判定 + 政策单源（plan-252 P1/P2）**：新增 `core/decision_eval_policy.py` 作评估口径唯一事实位（方向阈值 1.5%、不动作容忍带 2.0%、样本门槛 20、视界单位；账本单向引用并保留原名），`direction == 0`（持有/观望/不操作）改为**照常结算**并落 `flat_hit`（此前直接跳过、从不评估），`fold_ledger` 新增 `inaction` 分项与 `by_carrier.inaction_*`（旧账本无字段视为未判、不计样本、不回填）；呈现：判断依据块历史表现表下方一行「不动作建议」（样本不足只给命中/总数、无样本 `—`，双端同源）、历史决策复盘块给「判对 / 判偏 / 未到期」、`doctor` 账本概览并列不动作命中。

### 修复

- **akshare 国债收益率 API 改名兼容（rf-1139）**：1.19+ 把 `bond_zh_us_rate` 改名 `bond_zh_us_yield_em`（数据集与中文列名不变），旧代码只认旧名——CI 装 1.20.42 后 11 条无风险利率用例直接失败，生产侧还会把「属性不存在」误记成 akshare 熔断失败。现按可用性探测两代 API 符号（`bond_zh_us_rate` / `bond_zh_us_yield_em`，探测结果进程内记忆，缺失只降级不记故障），用例改为 patch 本方取数 seam、版本无关。
- **报告管线单测补齐离线桩（rf-1140）**：`test_orchestrator_generate_report` / `test_run_integrity` / `test_stage_cancel` 真实调用 `generate_report` 会顺带起数据源健康检查线程（真实网络 + akshare 的 py_mini_racer V8 初始化），单测里 V8 并发初始化会段错误崩掉 xdist worker（CI 表现为 3 个 worker crashed、整套从 1.5min 拖到 12min）。现统一声明 `offline_external_sources`（探针即时失败、零退避），并新增契约守卫 `test_offline_pipeline_contract.py`：真实调用管线入口却漏声明离线桩即红（防同类复发）。
- **跨模块常量归位单源（rf-1138）：退出码 `_EXIT_*`（CLI / Web worker 各一份）、push2 快照接口 URL、年化交易日数 252（3 处）、最小样本 20 与份额容差 1e-3（各 2 处）改为单源——退出码与 URL 进 `core/constants.py`，统计/容差常量进 `analysis/_math_utils.py`，调用点保留原名别名；新增 7 条单源守卫用例。
- **ETF 名称判定回归 code_utils 单源（代码类型判定集中化，rf-1136）**：`report/news_correlation._index_holdings` 自建 `"ETF" in name` 判定，小写 `etf` 的品种既不进 ETF 关键词扩展、剥离也失效（`replace("ETF","")` 大小写敏感），关键词召回与资产类型口径分叉；现改用 `is_etf_by_name()` + 大小写不敏感剥离，补 3 条回归用例。
- **行业接口节流单源化 + 并发下调**：`providers/eastmoney_industry.py` 只用模块常量喂限速器，配置 `batch_rate_limit.eastmoney_industry` 从未被读取（改配置不生效）；现由 `_push2_interval()` 读该配置、缺失才回落内置 100ms，`batch.industry_workers` 默认 8 → 4（push2 逐只调用，并发过高易被对端主动断连 → 连续失败 6 次熔断、行业数据整段降级）。用户手册两处配置表同步。
- **Provider 自定义冷却期不再被退避表覆盖**：`register_default_chains` 给 `eastmoney_industry` 设的 `cooldown_secs=120` 在熔断时被退避表首档 60s 无条件覆盖、成功后又被重置为全局 300s，配置实际从不生效（日志也打印 60s）。现记为 `ProviderState.cooldown_override`：熔断取「自定义值与退避档的较大者」、成功后回落自定义值，并随熔断状态落盘；新增 3 条回归用例（自定义生效 / 成功后回落 / 默认源仍走退避表）。
- **操作建议表「金额」列符号口径统一为绝对值**：模型自拟该列时用现金流口径（减仓 `+7600`、加仓 `-22000`），与「操作」列方向词冲突，读者容易读反；现将口径单源为 `rate_caliber.MONEY_SIGN_NOTE` 并在专家复盘/持仓体检两处提示词注入（金额写绝对值、方向由操作列承担，与机械建议表的 `amount` 同口径），`PROMPT_SCHEMA_VERSION` 递增至 `rate-caliber-5`。
- **滞后净值品种的「本日盈亏」不再静默归零**：原实现里场外行只有净值日等于当日才算本日盈亏，否则记 0.0——QDII/国内场外滞后时报告显示「本日盈亏 0」，读者会误以为当天没涨没跌。现改为照实呈现该净值日的涨跌并标「参考」（HTML 行内小字 + Excel 明细脚注），组合合计只累加当日已更新品种（`market_value.sum_today_profit`），避免把 T-1/T-2 涨跌混进「今日」。
- **场外净值缓存门禁按披露时点分档（消除白天重复取数）**：`_price_cache_fresh` 原口径要求国内场外缓存到 T、QDII 到 T-1，而场外 T 日净值当晚才披露，白天运行这一条件永不可能满足 → 每次运行把场外基金判为过期并全量重取（实测单次浪费约 12s），重取回来仍是同一份滞后净值，写回后下次再判过期。现按 `market_hours.is_otc_nav_disclosed`（默认 20:00）分档：披露前只要求最近可得的一档（国内场外 T-1 / QDII T-2），披露后收紧回 T / T-1。
- **HTML 生成细分文档与实际不符（rf-1135）**：`developer-guide.md` 原写「四步 + 模板编译占绝大多数」，收益测量显示 `模板渲染` 约 0.0s、`面板视图装配` 占 2.1s of 2.13s；现补上 `面板视图装配` 计时点并改写排查口径，`technical.md` 编排器职责链同步。
- **已解决台账行加粗缺失的静默漏搬（rf-1134）**：`check-doc-drift` 只以 `| **rf-N** |` 识别已解决条目，写成 `| rf-N |` 时既不进已解决集合、归档步也按「本版无待迁档」放行——0.18.0 发布时实际发生（已修项主台账未被搬运，仅一行日志）。现已在已解决区检出未加粗台账行并报 finding，归档识别口径不变；新增 2 条回归用例（报/不报各一）。

## 归档

- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0（2026-11-12）
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
