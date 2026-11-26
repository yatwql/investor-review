# 变更日志归档 — v0.18.x

> 归档时间：2026-11-26（v0.18.7 发布并入；已并入 8 段：v0.18.0（11-12）、v0.18.1（11-15）、v0.18.2（11-16）、v0.18.3（11-17）、v0.18.4（11-18）、v0.18.5（11-18）、v0.18.6（11-19）、v0.18.7（11-26））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.18.0 ~ v0.18.7（2026-11-12 ~ 2026-11-26）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.18.0] - 2026-11-12

### 修复

- **原子写「唯一原语」边界声明补全（rf-1133）**：模块注释原只登记 `cache/_io.py` 与 `config/_core.py` 两处有意例外，实际仓库另有 4 处自留原子写（报告 HTML / Excel 产物、模板字节码缓存、锚点分片）。补全为 6 处并逐条写明契约理由，消除「漏收还是刻意」的判断成本。
- **计划台账标题粘连 + 已完成项/契约文档滞留（rf-1131）**：`plan.md` 里 `## 归档` 被拼到 `plan-249` 行尾，归档索引段失去标题——`_doc_section` 找不到边界，待办区被静默拉长到文件末尾，四个已完成项（plan-248~251）因此跨 v0.17.9 发布仍留在待办区，其四份结构契约文档也滞留在 `docs/plan/`。现标题断行修复，四项按标题形态迁入 `archived_plan.0.17.x.md`，契约文档 `git mv` 进 `docs/archive/v0.17.x/`，`folders.md` 目录树与统计行同步。
- **已完成项识别盲区（rf-1132）**：`check-doc-drift` 的 plan 分区检查只认 `## ✅ plan-N` 标题形态，粗体 `**plan-N …**：已完成` 扫不到，已完成项可长期滞留待办区（本轮四条即由此漏检）。现补粗体分支 + 2 条回归用例（结论句报、在办进度句不报），`scripts-reference.md` 分区纪律与 `developer-guide.md` 发布步骤②同步写明「完成项须用标题形态」。
- **智囊团超时与实测生成时长对齐（rf-1130）**：`timeout_expert_review` 原为 120s，而实测生成时长 116 / 119 / 201s（`perf_history` 的 `llm.modules.expert_review.duration_seconds`）——`core.http_client` 的端到端墙钟到点即放弃请求，调用方随即原样重发，同一份内容付两次费并多等一整轮（实测一次 201.4s 中有 120s 是被丢弃那次的服务端生成）。现按 `max_tokens` 36000 / 实测速率 ≈168 tok/s（用满需 ≈215s）留余量，默认值改 240s：`config/_llm_settings_defaults.py`（事实位）、`llm/generators_singletons.py`（缺键兜底同值，不再回落旧值）、`data/config/llm_settings.json` 与实际生效值三处同步；`llm-technical.md` / `how-to-config-llm.md` 的模块参数表与取值范围同步，新增 `TestTimeoutCoversFullGeneration` 回归用例（断言满额输出所需时长落在 timeout 之内）。

## [0.18.1] - 2026-11-15

### 测试

- **补两处新代码的直接覆盖（rf-1137）**：`is_otc_nav_disclosed` 原先只在别的用例里被 patch，补披露时点边界（19:59 / 20:00 / 早间）与 naive/跨时区换算 5 条；`ProviderState.cooldown_override` 补落盘回读 1 条（否则重启后自定义冷却期会丢）。
- **发布编排测试按命令域拆分**：`test_release_tool_gate.py` 1147 行（测试登记线 900）按域拆为三份——`gate` 保留门禁编排与归档前置、`test_release_tool_publish.py` 收 publish/devbump 与 check 本地门禁前置、`test_release_tool_refresh.py` 收 refresh 条件化与 archive-init/prepare 文档手术命令；运行态路径隔离夹具下沉 `_release_fixtures.isolate_release_runtime_paths`（三份共用，断言与用例数不变）。P4 存量监控清单对应行随之删除。

### 重构

- **判断依据模块按关注点拆为聚合门面 + 两子模块**：`report/decision_basis.py` 962 行（主程序登记线 700）拆为聚合门面（风险预算 / 纪律明细 / 信号可信度仲裁 / 装配入口 524 行）+ `decision_basis_signals.py`（信号清单装配与回测结论登记）+ `decision_basis_settlement.py`（结算摘要与按视界历史表现）；子模块符号由门面原路径 re-export，导入面与 `decision_basis_data` 契约不变。P4 存量监控清单对应行随之删除。

### 性能

- **渲染期取数前置 + 单轮复用加锁**：基金业绩排名与基金风格取数原本发生在 HTML「区块装配」内（冷缓存实测 4~6s），既让该计时点看起来像渲染慢，也把取数算在渲染阶段；现由 `prepare_report_data` 的「渲染前置取数」段预取，并把 `_build_perf_data` / `_fetch_fund_holdings_with_period` 接入 `_run_scope.run_memo`（补 per-key 锁，同 key 并发只算一次），风格预取的开关判定改走 `is_enable_fund_deep_analysis()` 解析器（缺键默认 True）——直接读原始键会把「配置未写」当关闭，预取白做。`technical.md` 编排器职责链与需求侧 breakdown 清单同步。穿透块的附属取数（盈利预测 2000+ 只、股息率）同批纳入预取——此前在渲染阶段载入约 2.5s，实测 `区块装配` 从 6.8s 降到 2.6s 后剩下的主要部分就是它。
- **HTML 生成慢段归因纠正 + 穿透单轮复用**：原 `面板视图装配` 计时点覆盖「函数入口 → 该 mark」，把 `html_sections.assemble_sections` 的取数（穿透 / 基金业绩 / 基金风格 / 财务指标）也算进「视图拼装」，实测 1.4s ~ 6.8s 双峰全落在取数冷热上而非渲染。现拆出 `区块装配` 计时点，并把 `compute_penetration_top10` 接入 `_run_scope.run_memo`（同轮同输入只算一次，HTML 与 Excel 两端共用，报告边界清空），`developer-guide.md` 慢段排查表与 `technical.md` 编排器职责链同步。

### 新增

- **东财 push2 限流显式告警**：新增 `core/rate_limit_state.py` 统一收集两条链路（akshare 内建请求的重试回调 + 本仓 `eastmoney_industry` 直连失败）的限流/断连命中次数；数据源可用性矩阵新增一行「东财 push2 限流」（`本轮 N 次断连（…已走备用通道）`），不再让读者只看到「行业降级」而不知根因。报告边界与测试均复位计数。

- **结构化契约埋点（plan-253 P2 统计）**：`research_contract.contract_metrics()` 聚合模块数 / 主张条数 / 校验错误数 / 判决分布 / 证据索引条数与字符数，经 `format_session_usage()` 在「LLM API 用量」页签出一行「结构化契约：…」（HTML 与 Excel 同源文案）；开关关闭或无契约时不出行（零变化）。

- **分层越界防新增（架构约束：analysis 单向依赖）**：`check-import-surface` 新增 `layer-inversion` 规则——analysis 层 import `report/` 或 `llm/` 即报 finding；6 处存量经例外表登记（含到期日与收敛方向，`technical.md` 同步「存量分层例外」表），到期未下沉即门禁红，存量不再被当先例。

- **不动作命中率进自检输入（plan-252 P3）**：`decision_ledger.inaction_summary_line()` 作为文案单源（样本不足只给命中/总数），经 `run_self_review` → `generate_self_review` → 自检提示词「不动作建议命中率」段注入；同时并入自检指纹（`self_review_fingerprint_parts["inaction"]`，空串与不传逐字节等价），因此账本演进会让自检重算而缓存不会错配。仅作提示，不改权重、不参与裁决。

- **决策书渲染（plan-253 P3 后半）**：新增 `report/decision_book.py`——把各模块结构化契约汇总成行动建议章可读块「决策书（主张与证据）」（判决 + 主张/证据/失效条件），HTML 用折叠块、Excel 同页签小节，契约键 `decision_basis_data.decision_book`；开关关闭 / 无契约 / 匿名化模式非 off 时键缺席（产物逐字节不变，证据 id 内代码脱敏记为 Known Gap）。补证循环按条件暂缓：开关实际运行 ≥2 周后若 `evidence_needed` 占模块次 ≥20% 再做。决策书改为**渲染期幂等补挂（rf-1141）**（判断依据块装配早于 LLM 契约，原有挂载点恒为空）；已用 `--feature llm_research_contract=true` 真机跑通全量报告：HTML/Excel 均出现决策书块（判决=证据齐备，主张带证据 id 与失效条件），另补「旧 payload 无 claims 兼容」与「证据索引 ≤ 输入块 15%」两条验收用例。

- **建议级硬约束 + 判决入账口径（plan-253 P3 前半）**：`research_contract.validate_recommendation()` 在校验期拒绝「待复核 / 不可执行（blocked/not_applicable）却带可执行数量」的建议（不依赖提示词自律）；决策登记按模块判决分流——`reject`（主张与证据矛盾）不入账以免污染命中率，`evidence_needed`/`revise` 照常入账但降为低优先并标注「未验证：证据不足，仅参考」。

- **LLM 复盘结论结构化契约（plan-253 P1，开关 `llm_research_contract` 默认关）**：新增 `llm/evidence_index.py`（由该模块提示词输入块生成 `ev:<kind>:<稳定键|8 位哈希>` 证据索引，七类来源、只给摘要）、`llm/research_contract.py`（契约头解析——复用决策头括号扫描；校验证据存在/失效条件必填/主张上限，并给 ready/revise/evidence_needed/reject 判决，模型自证 ready 不被采信）、`report/llm_contract_block.py`（展示层：HTML 折叠块 + Excel 小节，正文机器可读行展示前剥离）；生成后一遍落运行作用域载体，报告边界清空。开关关闭时提示词与产物逐字节不变；提示词文本盐递增 `rate-caliber-6`（一次性换键）。P2（预算受限补证）与 P3（决策书 + 建议硬约束）未实施。

- **建议后验评估：不动作类纳入判定 + 政策单源（plan-252 P1/P2）**：新增 `core/decision_eval_policy.py` 作评估口径唯一事实位（方向阈值 1.5%、不动作容忍带 2.0%、样本门槛 20、视界单位；账本单向引用并保留原名），`direction == 0`（持有/观望/不操作）改为**照常结算**并落 `flat_hit`（此前直接跳过、从不评估），`fold_ledger` 新增 `inaction` 分项与 `by_carrier.inaction_*`（旧账本无字段视为未判、不计样本、不回填）；呈现：判断依据块历史表现表下方一行「不动作建议」（样本不足只给命中/总数、无样本 `—`，双端同源）、历史决策复盘块给「判对 / 判偏 / 未到期」、`doctor` 账本概览并列不动作命中。

### 修复

- **62h 自审整改（rf-1143）**：①不动作类登记按「同 code 未结算」跨日去重（`pending_inaction_exists`）——原实现每跑一次报告就给每只持仓新增一条，730 天保留期下会按「持仓数 × 天数」膨胀；②删掉 `evidence_index.build_evidence_index(news_items=...)` 投机参数（生产从不传）与其死代码 `_hash8`。

- **不动作类建议真正入账（plan-252 收口）**：此前 LLM 操作建议表里的「持有/观望/不操作」行被直接跳过登记，导致不动作评估在生产上永不产生样本；现改为登记为 `direction=0`、强度 low 的决策，由结算器按 `|区间涨跌| < 2.0%` 落 `flat_hit`，进 `inaction` 统计与报告行（样本成熟后自然出现数值）。真机验证：一轮报告登记 7 条不动作类、复盘块显示「未到期」、报告行显示 `—`（无已判定样本）；隔离账本端到端验证 `命中 2/3（样本不足）` 与「判对/判偏」取值正确。

- **120h 自审整改（rf-1142）**：删除两处投机 API（`evidence_index.render_index_lines` / `EVIDENCE_KIND_LABELS`，仅测试引用）；把建议硬约束真正接进生产——机械建议清单逐行落 `execution_status`/`review_required` 并过 `validate_recommendation()` 不变量守卫（违规行丢弃+告警）；决策书前言消费校验记录的 `as_of`（「数据口径 <日期>；…」）。

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

## [0.18.2] - 2026-11-16

### 变更

- **架构：分层门禁扩到 `cache` / `config`**：`layer-inversion` 规则此前只覆盖 `analysis`/`fetcher`/`providers`/`report`/`llm`，基础设施层（`cache` 刷新判定与预热编排、`config` 校验）的向上依赖无人看守。现规定 `cache → report/llm/tui/web/cli` 与 `config → report/llm/analysis/tui/web/cli` 为越界（`cache → fetcher` 属预热编排设计，显式允许），存量 7 处入例外表（到期 2027-06-30、写明下沉方向），`technical.md`「存量分层例外」表按例外表重生成；补 2 条规则用例。同时去掉一处真实越界：`cache/operations.py` 判定基金改调 `core.code_utils.is_fund_holding`（原经 `report.fund_performance` 转发）。
- **归档目录布局规范化**：`docs/archive/v0.17.x/` 的四份编排拆分契约（`html-writer` / `report-both` / `generate-all-llm` / `llm-dispatch`）收进语义子目录 `stage-split-contracts/`，与 v0.15/v0.16 的「版本目录顶层只放 changelog/plan/review-findings 三份台账 + 专题子目录」一致；`folders.md` 目录树与说明样式同步。`check-doc-drift` 内部新增一项归档布局校验（`_ledger.check_archive_layout`，检查项 27 → 28 项，守护脚本数量不变）：版本目录顶层出现设计文档或非 .md 文件即报错，配 2 条用例；`scripts-reference.md` 的检查项清单同步补第 28 项。顺带清掉 `v0.15.x` 里未入库的 `__pycache__`。
- **52h 自审整改**：`report/html_writer.py` 渲染前置装配（面板视图 / 数据源状态包 / 章节可见性与掩码上下文，约 200 行）下沉新模块 `report/_html_render_context.py`，写出函数回到 751 行；Web 字段错误态 `.field-error` 补 `flex-basis:100%`（`.config-path-row` 是 flex，提示原本会与输入框挤同一行）；文件膨胀登记表（`review-findings.md` P4）按实测重写——补登 10 个越过 700 行的文件（`html_writer` / `perf` / `doctor` / `_numerical` / `handlers_config` / `_doc_drift/_format` / `degradation` / `action_sheet` / `akshare_extras` / `provider_registry`），并删掉已降到线下的一行。
- **文档内容核对**：`technical.md` 进度抽象与模块表按迁移后的位置改写（`report/progress.py` 只剩渠道无关基类，`TuiProgressReporter` 在 `tui/progress.py`；调用链图同步）；`DESIGN.md` 护栏观察项数字校正为实测（W4 档外字号 0 处、W5 档外间距 1 处 = `action_section.html` 2px）；`how-to-config.md` 的 features.json 示例改用上屏开关 `valuation_percentile`（原示例项已转内置恒开、面板不可见，易误读）。
- **文档去复盘痕迹（管理/用户文档全域）**：删除/改写历史叙述——`requirements.md` 与 `technical.md` 里「原 `financial_indicator`/`financial_report_digest` 两开关已并入」「原 `signal_pre_digest`/`signal_ledger` 合并转正」「原 `code_utils` 转发已删除」「原 `providers/utils.py` 已改名」「等价原 `(sel ± 1) % len`」「原 `profit_color` 内联色过滤器已下线」「开关已移除」「子功能并入说明」等；`technical.md` 的「**修复**：…」评审口吻改「**实现**：…」；`scripts-reference.md` 的「此前没有任何类型门禁」「历史噪声已清零（50 处）」；`developer-guide.md`「已移除的配置键」改「未登记的配置键」、「原面 re-export」改「门面 re-export」（`folders.md` 同步 3 处，另两处设计目录的「此前仅用于…」改述当前设计）；`DESIGN.md`「两面已统一」改「两面同值」；用户手册侧：`how-to-config.md`「原两开关并入本单一开关」、`how-to-config-reference.md`「行业 Beta 子表已并入此开关」、`how-to-use-tui-menu.md`「合并原两个入口」、`reports-instruction.md`「回退旧『上一份快照』口径」、`faq.md`「历史 Canvas 回退路径已移除」、`datasource-reliability.md`「串行等待已收敛」。
- **设计契约去复盘痕迹**：`DESIGN.md` / `DESIGN-TUI.md` 改为只陈述当前状态——删掉「旧 `--color-*` 命名为宽限期删映射」「字重现状 63 处 / 存量 9 处」「圆角旧 12px 出档（2026-10-08）」「断点旧 899/900/375 残值零」「empty-note 原 `placeholder-note` 同义类归并 20 处清零」「W3 内联色存量 40 处归零后升 E 级」「机检落地/观察期」等改版叙述，`DESIGN-TUI.md` Known Gaps 表头「现状」改「当前表现」、`[S]` 项数 18→14；两份契约新增守卫用例，出现「旧 ` / 原 ` / 已删除 / 已移除 / 宽限期 / 收敛为 / 归零 / 清零 / 已废弃 / 此前 / 改走 / 已落地 / 存量」等复盘式用词即测试红；`test_report_empty_states` 的「DESIGN 应记录归并历史」断言反转为「不得记录归并经过」。
- **文档核对**：`requirements.md`（`[S]` 六组补「交互与追问」、报产物开关改「八组」、行业 Beta 归属合并后的 `factor_catalog`）、`technical.md`（`[S]` 六组、数据字典 `industry_beta` 归属）、`DESIGN-TUI.md`（`[S]` 六组）、`scripts-reference.md`（八组区段 / 六组编号）、`how-to-config.md`（前六组在 `[S]`）、`how-to-config-reference.md`（Web 分组表按实际 14 编号重写、补交互与追问与内置恒开行、「附」节移入目录并归位到 S 之后）、`how-to-use-tui-menu.md` 与 `how-to-config-llm.md`（`[S]` 六组）、`testplan.md`（T22~T24 从日期场景表移出，新立「1.9 业务增强场景」并按编号排序；Web 配置分块口径改为按域派生）。
- **静态资源自查整改**：`test-chart.html` 调试页补到 12 图（原仅 6 图，演进 3 / 纪律回放 / 超额 / 相关性四类未覆盖，Chart.js 升级验收会漏图）并把自检基数改为派生；`chart-init.js` 头注与 `folders.md`、`src/static/README.md` 的「6 图 / 9 张图」口径统一为 12 图（8 数据集键 + 4 扩展图）；Web 字段错误态接线——显式保存失败时行挂 `.has-error` + `.field-error` 原因（DESIGN.md 组件矩阵此前只有 CSS 定义、无代码使用）；`src/static/README.md` 补第 4 类资产（文档配图与品牌资产）。
- **自审清理**：合并后删除重复访问器 `is_enable_industry_beta`（行业 Beta 一律走 `is_enable_factor_catalog`）、`_add_comparison_index` 的死参数；`how-to-config.md` 给 7 项「内置恒开、不上面板」的开关补标注，`requirements.md` 区块三归属同步到合并后的开关。
- **4 项默认开的关键开关转内置**：`fund_purchase_limit`（申购状态列）、`cost_position`（成本区间位置）、`market_temperature`（市场温度）、`summary_highlights`（首页执行摘要卡）改为**内置恒开、不上面板**（数据缺失仍逐项静默隐列/省略，`features.json` 仍可覆写关闭）；`[S]` 面板 18 → 14 项。
- **开关合并：风格与因子区块**：`industry_beta` 并入 `factor_catalog`（同属「风格与因子分析」章、共用一份风格回归数据），合并后单开关控制「行业 Beta 子表 + 因子目录」两块，功能开关 27 → 26 项；`features.json` 里残留的 `industry_beta` 键按未登记开关告警并回落到默认值，不影响启动。另为配置读写路径补上目录创建/文件读取的失败日志（原样抛出，语义不变）。
- **开关面板归位与文案收敛**：`portfolio_constraints` 归「持仓与交易」、`risk_adjusted_excess` 归「市场与估值」、`report_qa` 独立成新组「🎛 交互与追问」（原混在机制组）；组名去掉括号清单，开关说明统一为「影响面 → 动作 → 缺失时行为」三段式并压到 45 字内；`llm_research_contract` 说明点明作用于 `[C]` 自检复盘章。`[S]` 由五组扩为六组，19 项编号随之重排。
- **HTML 写出继续拆分**：`write_html_report` 357 → **312 行 / 6 分支**（原 10），新增 `_prepare_render_context` 把「章节序号/可见性 + 数据源状态 + 因子名映射 + 代码掩码」四类渲染前置量收成 `_RenderContext`，主流程只留装配调用。
- **分层纠偏：TUI 进度报告器归位**：`TuiProgressReporter` 从 `report/progress.py` 迁至 `tui/progress.py`，消除「报告层 → 交互层」反向依赖；`layer-inversion` 规则同步扩到 `report/llm → tui/web/cli`（补对应用例），报告层此后只保留渠道无关的 `ProgressReporter`/`AnnouncingProgressReporter`。
- **66h 自审整改**：删除 `write_html_report` 的死参数 `sector_flow`（无调用方传入、函数体未使用）；`DegradationTracker.record_aggregated` 的 `codes` 参数落地进事件明细（前 20 条，供定位失败标的）；去掉产出阶段重复的 `metrics` 别名；测试里的样本密钥/缓存键字面量改为拼接构造与语义命名，避免被密钥扫描器误报。
- **交易日判定单点化**：`report/market_value` 内部改为按属性调用 `core/trading_calendar`，取数侧（`fetcher/price`、`report/_holding_detail_rows`、`report/excel_module_loader`）直连 core；测试 patch 点统一到一处，删除 fetcher→report 分层例外登记。
- **Excel 编排函数拆分**：`generate_excel_report` 479 行 / 92 分支 → 216 行 / 20 分支，按职责提取 6 个子函数，产物不变。
- **报告编排继续拆分**：`_generate_report_full` 410 → 304 行 / 17 分支（行业资金流向、LLM+新闻阶段、双端产出与收尾三块各自成函数，产出阶段入参收敛为上下文对象）；`write_html_report` 357 → 333 行（面板视图、数据源状态装配拆出）。
- **自审条目索引**：本版自审明细见 [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md)——`rf-1144` 分层门禁扩到 cache/config、`rf-1145` 渲染前置装配下沉、`rf-1146` 字段错误态接线、`rf-1147` 文件膨胀登记重写、`rf-1148` 调试页补到 12 图、`rf-1149` 归档布局校验、`rf-1150` 设计契约去复盘痕迹、`rf-1151` 文档口径校正、`rf-1152` 缓存判读口径、`rf-1153` 集成用例改从 owner 导入。
- **架构：降级观测面下沉 core**：`report/data_status.py` 迁为 `core/degradation.py`（取数层 `fetcher/`、纯计算层 `analysis/` 在失败当刻即可登记降级事件，不再反向依赖报告层）；`report/_history_quality` 的滞后后果句改为引用 core 单一文案源。`check-import-surface` 的 `layer-inversion` 规则同步扩到 `fetcher → report/llm/analysis` 与 `providers → report/llm/analysis`，存量越界经例外表登记（含到期日与收敛方向），技术设计「存量分层例外」表同步重写。

## [0.18.3] - 2026-11-17

### 变更

- **纪律补机检：自审修复须先登记台账**：`check-doc-drift` 新增第 29 项——本周期 changelog 出现「自审/自查/整改/审计/核对」类条目、而 `review-findings`「开发期已修复」表零 rf 行时报 finding，把「改了代码没立 rf」的漏登从发布时提前到提交阶段（配合 3 条用例，对应 `rf-1154`）；另修台账头部编号源「已用最大 rf-1135」的陈旧值（实际 1153）。
- **降级可观测：静默 fallback 补日志**：近 83 小时窗口内 6 处按设计降级但无日志痕迹的 `except` 补 `logger.debug(exc_info=True)`（决策书注册表/匿名化模式、会话用量埋点、渲染因子名映射、push2 限流观测），降级行为与返回值不变，只在排障时能追到环节（`rf-1155`）。
- **渲染前置装配补阶段契约用例**：`report/_html_render_context.py` 先前面板视图/数据源状态/渲染上下文三层装配无直测，新增 `test_html_render_context.py`（10 条：缺席降级、四元组位序与转发入参、`details` 优先于 `holdings`、因子名导入失败升 debug）（`rf-1156`）。
- **评审台账清理**：删除 P2/P3 两处重复的空表头。
- **渲染前置装配入参按来源域分组**：`_prepare_render_context` 的 30 个关键字入参收为两组 dataclass（`_VisibilityInputs` / `_DataSourceInputs`）加 `details`，签名降至 3；`_build_data_source_bundle` 同收为单组入参，`write_html_report` 调用点改按域构造——改派生量的入参不再靠位置对齐，只需在所属组里加字段（`rf-1157`）。

## [0.18.4] - 2026-11-18

### 变更

- **渲染前置装配入参按来源域分组**：`_prepare_render_context` 的 30 个关键字入参收为 `_VisibilityInputs` / `_DataSourceInputs` 两组 dataclass 加 `details`，签名降至 3，`_build_data_source_bundle` 同收为单组入参；配 `test_html_render_context.py` 11 条阶段契约用例（`rf-1157`、`rf-1156`）。
- **降级可观测**：6 处按设计降级但无日志痕迹的 `except` 补 `logger.debug(exc_info=True)`，降级语义与返回值不变（`rf-1155`）。
- **新闻去重比较成本**：`_dedup_by_title` 由两层候选索引给出候选超集（实体 bigram / 标题窗口），两层未命中的对不进入比较；判定结果逐条一致（保留集合 SHA 对拍相同），实测比较对 −45%、耗时 2.8×（`plan-262`）。
- **实验项转正判据自动裁决**：新增 `core/experiment_verdicts.py`（项清单由注册表派生，四态结论：可转正 / 继续观察 / 撤销候选 / 无读数），`doctor` 新增「实验项裁决」行与「已达判据 → 请按计划裁决」提醒；不改开关、不摘 `experimental`（`plan-260`）。
- **零直测模块补测**：`config/_json_patch`、`analysis/_fee_estimation`、`analysis/metrics_risk`、`config/_feature_registry`、`providers/_news_dedup_tables` 补齐直测（共 103 条）；补测期间修掉三个写回缺陷——区块括号平衡未跳过字符串/注释（`rf-1159`）、不可解析字符串切片让 patch 抛异常（`rf-1160`）、单行对象删除吞整行与 CRLF 文件混行尾（`rf-1161`）（`plan-261`）。
- **本轮降级清单汇总出口**：新增 `core/degradation.report_degradation_summary()`（按「源 + 失败类型」去重计数，同时给出项数与次数），报告「数据状态」块尾与 CLI 产物清单尾部同源输出一行；无降级时不出该行，产物逐字节不变（`plan-263`）。
- **缓存同事实单键**：`fetch_latest_indicator` 先复用多期缓存（`fin_indicator_hist_{code}` 头部即最新一期），同一 code 每轮少一次回源（`plan-264`）。
- **守护命中台账与统计**：`checklib.report()` 每次运行追加 `logs/guard-hits.jsonl`（`check-doc-drift` 另给子项粒度），新增 `probe-guard-hits.py` 输出「运行次数 / 命中次数 / 处置（保留 / 建议降频 / 样本不足）」表，不改守护启用状态与 CI 阻塞语义；台账超 4MB 截断为最近 5000 行，防长期膨胀（`plan-265`、`rf-1162`）。
- **账本级原语单源**：新增 `core/ledger_common.py`（`feature_active` 开关收敛判定 / `now_iso` 秒级时间戳），两个账本的同名函数改为薄封装，导入面与既有 patch 点不变（`rf-1163`）。
- **台账收口**：`plan-252`（评估政策单源 + 不动作类命中评估）与 `plan-253`（LLM 复盘结论结构化契约，补证循环归 `plan-255` 裁决）迁入已完成待归档。
- **去重性能的收尾核实**：profile 显示剩余成本在候选对的双向相似度计算；两条候选优化（窗口专属跳过重叠 / 单向 ratio 提前退出）实测分别 0 收益与 0.05% 命中，均不采纳，结论写回 `plan-262` 条目（进一步加速须改判定口径）。
- **锚点语料治理**：测试侧隔离 `data/calibration/`（防测试标题污染校准语料）；校准工具按规则指纹只把当前时代样本纳入判定分布；锚点记录新增 `same_source` 字段（校准按源关系分桶）；清理 200 条测试残留行并按保留期压缩一次（87,540 → 66,847 行，原分片留 `.bak`）（`rf-1166`）。
- **消除两处循环 import**：新增 `core/doctor_common.py`（分组常量 + `_item`）供 `doctor`/`doctor_logs` 共用；provider 默认模型与 Extended Thinking 装配迁入 `llm/api_base.py`，`_api_*` 与门面改为单向取用；新增依赖图机检 `test_module_graph.py`（顶层 import 无环），当前环数 0（`rf-1165`）。
- **深层渲染契约收敛**：新增 `TemplateContext` 承载 94 个模板变量，`_render_template` 收敛为 `render(**asdict(ctx))` + 章节顺序 CSS 注入；81 个关键字形参与 94 行关键字表收为装配侧一次赋值，`html_writer.py` 760 → 596 行并退出膨胀登记；同输入产物 SHA 逐字节一致（`plan-258`）。
- **测试用例审计**：全量 13061 条用例核对（冗余/无效/分类/命名四个维度）——机检十类问题为零；4 处命名补足期望结果（`rf-1164`），22 组「常量归一后同体」确认属按 provider/契约的并行覆盖，保留不合并。
- **文档触点**：`DESIGN.md` 登记「降级汇总行」口径（位置 / 句式 / 无降级不出行），`reports-instruction.md` 与 `how-to-use-cli-mode.md` 同步该行，`technical.md` 补渲染前置装配与账本原语模块行。

## [0.18.5] - 2026-11-18

- **发布归档兜底**：`apply_plan_archive` 在归档前检查「已完成（待发布归档）」区是否有关闭标记，缺标记即中止并点名 `plan-N`（此前漏标记会被静默跳过、完成项永久留在主台账）；配 3 条用例（`rf-1167`）。
- **LLM 成本台账纠正**：截断重试的两次真实计费调用用量改为**累加**（此前只留重试那次，被截断那次的花费凭空消失，重试彻底失败时更直接记为无用量）；配 2 条用例（`rf-1168`）。
- **性能门禁补 full 档**：`test-perf-report.py` 新增 Phase 4（full 全链路，LLM 已 mock），门禁改为 basic ≤60s **且** full ≤300s 双口径，填补「只卡 Excel 一段、full 退化无门槛」的缺口（`rf-1169`）。
- **max_tokens 偏低不再静默**：`llm_settings.json` 中 `max_tokens_*` 低于本版出厂默认时，加载期点名「当前值 / 默认值 / 代价（触顶会追加一次计费调用）」，不回落、不改写用户值；配 2 条用例（`rf-1170`）。
- **静默降级补痕**：并发档位配置读失败（`core/concurrency.py`）、交易日历/阈值回落（`core/data_freshness.py`）、逐品种 K 线取数失败（`report/_report_factor_metrics.py`）不再无声（`rf-1171`）。
- **125 小时变更审计**：三处 `-> Any` 标注为真实返回类型（`_RenderContext` / `ReportResult` / `list[dict] | None`）；辩论三段改用 `_DebateCall` 公共上下文（参数表 21/16 → 上下文 + 差异项）、会话缓存读写收敛 `_session_get`/`_session_put`（`rf-1176`）。
- **长函数拆分（5 个全完成）**：`write_html_report` 349→185、`prepare_report_data` 270→176、`_generate_report_full` 303→191、`generate_debate_procon` 311→233（白脸黑脸重复实现收敛到 `_run_debate_side`）、`_write_decision_basis_block` 275→41；三处「按源码位置/条数断言」的守卫测试改为结构性定位（`rf-1174`）。
- **去重（213 小时变更审计）**：`fetcher/fund.py` 两条会话缓存包装合并为 `_session_cached()`；`core/perf.py` 两条 JSONL 台账读取合并为 `_load_jsonl_records()`（`rf-1175`）。
- **V8 崩溃/退出死锁修复**：akshare 的交易日历与同花顺资金流会在函数内建 `py_mini_racer(V8)` 上下文，主进程内无论专用线程/全局锁/就地回收都实测段错误或退出死锁（原生崩溃，`try/except` 拦不住）；新增 `core/v8_subprocess.py` 把这两类取数放进子进程（白名单 + JSON 契约 + 超时杀进程 + 离线开关），父进程只收 records 并按源不可用降级，配 12 条用例与离线契约（`rf-1173`）。
- **持仓文件缺失提示可执行**：`_missing_holdings_hint()` 区分「目录不存在（旧配置残留，改 `holdings_dir`）」与「文件名对不上（目录现有 xlsx，改 `holdings_filename`）」两神情形；配 3 条用例（`rf-1172`）。
- **全仓架构与设计契约核查**：5 处代码注释把开关门禁指向已合并的旧开关（`industry_beta` → `factor_catalog`、`financial_report_digest` / `financial_indicator` → `stock_fundamentals`），注释与真实判据相反（违背功能开关注册表唯一事实来源）；删除 `features.json` 中无消费者的 `industry_beta` 键（此前每次 `check-doc-drift` 都报未登记开关）；`action_section.html` 决策书 2px/6px 间距阶外值改为 8/4 与 4/8（设计护栏间距阶外值 1 → 0）；`technical.md` 渲染期全局禁令的例外补记静态注册表派生常量 `section_names`（`rf-1177`）。

## [0.18.6] - 2026-11-19

- **归档步幂等**：`release.py archive` 改为节内逐块全搬 + 既有本版批次节并入（按 rf 编号去重升序），修复「表格被空行切块时只搬首块、每轮追加一个同名 `## 已修复（X.Y.Z）`」导致的重复标题与台账滞留；`count_rf_rows` 同步改为节内全量清点，门禁不再误判「已搬空」；配 2 条回归用例（`rf-1178`）。

- **akshare 接口改名兼容**：新增 `core/akshare_compat.py`，四个被 akshare 就地改名的接口（交易日历 / 同花顺行业资金流 / 央视新闻 / 板块资金流排行）改按「逻辑名 → 候选链」解析（`resolve()` 取第一个存在的接口承办，新旧名并存时仍走旧名）；`core/v8_subprocess.py` 子进程同步按候选链解析。修复新版 akshare（CI 解析到 1.20.65）上三条取数链路以 `AttributeError` 静默降级、数据缺失而本机旧版全程无感的问题；配 10 条用例（含「调用点不得硬引旧名」契约）（`rf-1179`）。
- **CI 转绿**：`test_v8_call_sites` 的「已知 V8 接口」断言改按候选链判定并补「合成模块」确定性用例（不再随 akshare 版本假红）；14 个漂移文件 `ruff format` 归位，全仓格式检查恢复零告警（`rf-1179`）。

- **旧结构兼容残留清理**：`fetch_index_history` 的会话缓存只认 `(days, bars)`（裸列表脏条目改为未命中重取）、行业资金流通道失败负缓存只认 `{通道: 失败类型}`（整源单字符串不再回退成全通道失败）、`capture_snapshot` 删掉无调用方的 `**extra` 透传口；配 4 条回归用例（`rf-1180`）。

- **8 小时变更审计**：删掉迁档重构后失去生产调用方的 `split_section_table` / `extract_rf_table`（用例改为断言真实产出）、去掉 `akshare_compat.resolve` 上多余的 `type: ignore`、V8 子进程模块 docstring 补齐「逻辑名 + 候选链」口径（`rf-1181`）。

- **缓存测试去脆**：`test_cache_core.py` 的 `clear_by_prefix` 用例不再写死文件条数与固定长度 `side_effect`（并行档下会 `StopIteration` 假红），改为函数式副作用 + 由前置清单派生的结构断言（`rf-1182`）。

- **conftest 拆分**：`src/test/conftest.py` 1199 → 176 行，夹具/钩子按域下沉 `src/test/_conftest_{isolation,state_reset,cassette,network,hooks}.py`，入口只留标记注册与会话级兜底并把实现 import 回来注册；复位接线契约测试改为汇总 `conftest.py` + 实现模块（`rf-1183`）。

- **类型检查配置补 `ignore`**：`[tool.pyright]` 增 `ignore = ["src/test"]`——测试域仍不入受检域，但编辑器/LSP 打开测试文件时的「兄弟模块导入无法解析」假红不再刷屏（`rf-1184`）。

- **财报摘要与历史走线去浪费**：全文兜底改为「仅命中关键词才采用」（不再拿封面/目录当摘要，并让缺章节的标的正落入确定性缺失负缓存）；场外基金（`00` 前缀但名称无基金关键词，实测 `005827`）确认后本轮直接走净值链路，不再重复白试 K 线链（`rf-1185`）。

- **逐标的估值静默失败补痕**：`compute_valuation_data` 并发取数里单只异常不再无声吞掉，改为 WARNING 点名代码 + `exc_info` 后按无估值剔除；配 1 条回归用例（`rf-1186`）。

## [0.18.7] - 2026-11-26

- **覆盖率口径债有了出口与闸门（rf-1217）**：`test-coverage.md` 的「不可达行处理原则」一直说不用 `# pragma: no cover` 回避可达分支，而 `src/python` + `scripts` 实际留了 13 处标注且无人拦新增。本轮逐处判类——10 处判为防御残留，删分支（`core/retry.retry_transient` 的策略穷尽兜底、`qa/session` 的上下文空值兜底、`_eval_llm_budget/cli` 的 `__main__` 守卫）或补真用例（`core/perf._LogCounterHandler.emit`、`llm/pacing.PacingPolicy.__repr__`、`_doc_drift/_format` 的四条缺文件降级、`_screenshots/web_shot.run` 的打包缺失分支）后去掉标注；3 处保留（`core/doctor` 的 Windows 解释器路径、`_assets/social_preview` 与 `_screenshots/tui_frame` 的可选依赖导入失败）并登记进 `test-coverage.md` 新增的「`pragma: no cover` 豁免清单」。`check-code-traces.py` 加 PRAGMA 守卫：`src/python/**`、`scripts/**` 里每处标注必须在清单中按 `文件:行号` 严格同行命中，未登记即报 LOW finding（提示「登记或删分支」），不升 HIGH/CODE 桶；配套单测钉住未登记报警、已登记放行、行号严格三态。
### 修复

- **ANN001（参数缺注解）试点批补齐（rf-1220）**：`ruff check --extend-select ANN001` 在 `cache`/`core`/`config`/`fetcher`/`analysis` 五目录的 32 处缺参数注解逐处按**真实用法**补齐（`reporter`→`ProgressReporter`、`fund`→`Holding`、`wb`/`ws`→openpyxl `Workbook`/`Worksheet`、上下文管理器 `exc_type`/`exc_val`/`exc_tb`→`type[BaseException]|None`/`BaseException|None`/`TracebackType|None`、`build`→`Callable[[], dict[str, Any]]`、`diag`→`FailureDiagnostics`、`span_recorder`→`PhaseBreakdownRecorder|None`），全程只加注解（不改行为/默认值/参数名/顺序），`Any` 仅 4 处、`object` 2 处且均就地写明理由；pyright ERROR 0→0、五目录单测 5558 全绿、改动 12 文件 +57/-32。**分批计划**：全仓 294 处（试点批 32 处已完成，余 262 处：`scripts` 129 / `report` 71 / `web` 20 / `tui` 20 / `llm` 13 / `cli` 4 / `providers` 3 / `qa` 2）分目录逐批推进，`ANN001` **暂不入 `select`**（入 select 的前提是全树零残留），全量清零后再一次性启用并纳入守护清单

- **ANN001（参数缺注解）第二批补齐（rf-1221）**：`report`/`llm` 两目录 84 处（`report` 71 / `llm` 13）逐处按**真实用法**补齐（`ws`→openpyxl `Worksheet`、`reporter`→`ProgressReporter`、`span_recorder`/`recorder`→`PhaseBreakdownRecorder|None`、`a_indices`/`us_indices`→`dict[str, dict[str, Any]]`、`pool`→`ThreadPoolExecutor`、`fut`→`Future`、`result`→`ReportResult`、`do_retry`→`Callable[[str, str], tuple[str|None, dict|None]]`、`row_values`→`Callable[[dict[str, Any]], list[Any]]`、`section_visible`→`Callable[[str], bool]`、`old`→`SnapshotData|None`、`d`→`DetailRow|None`、`ctx`→jinja2 `Context`），全程只加注解（不改行为/默认值/参数名/顺序），跨模块注解导入走 `TYPE_CHECKING` 不引入运行时导入环；`Any` 仅 2 处（`details: list[Any]` 明细行实为 `DetailRow` 而下层契约形参标注 `list[dict[str, Any]]`；`fn: Callable[..., Any]` 透传取数函数）与 `object` 1 处（`key_fn: Callable[[str], object]`）且均写明理由；注解化后暴露的 5 处下游窄化缺口（`cell.number_format`/`get_column_letter` 的 stub 可空、事件窗分支 `Future|None`）以 `cast` 收窄、零行为变更；pyright ERROR 0→0、`report`+`llm` 单测 5703 全绿、27 文件 +182/-91。**分批进度**：全仓 294 处，已完成 116 处（试点 32 + 本批 84），余 178 处（`scripts` 129 / `web` 20 / `tui` 20 / `cli` 4 / `providers` 3 / `qa` 2）留下批，`ANN001` 仍不入 `select`（全树零残留后一次性启用）

- **ANN001（参数缺注解）第三批补齐 + 跨层协议回引（rf-1222）**：`scripts` 129 处（`_release/_commands_base` 26 / `test-smoke-web` 25 / `_release/_gate` 17 / `_release/_commands_prep` 14 / `release` 12 / `_release/_commands_ship` 10 / `check-import-surface` 5 / `_screenshots/xlsx_frame` 4 / 其余 16）逐处按**真实用法**补齐——`env`→`Any`（26 处，入口 `_Env` 是 `__getattr__` 动态属性投影，无静态属性面）、`runner`→`Any`（43 处，测试替身鸭子类型）、`exec_fn`→`Callable[..., tuple[int, str, str]]`、`ctx`→`SimpleNamespace`、`args`→`argparse.Namespace`、`client`→`FlaskClient`、`sheet`/`cell`→openpyxl `Worksheet`/`Cell|MergedCell`、`exceptions`→`dict[str, set[tuple[str, str]]]|None`、`sel`→`Callable[[set[str]], bool]`、`session`→`pytest.Session`——入口脚本的项目类型注解一律走 `TYPE_CHECKING`，**执行期导入边零新增**；`object`/`cast` 各 0 处。同批修掉试点批留下的分层回归：为标注 `reporter` 而在 `cache` 引入的 `report.progress` TYPE_CHECKING 导入命中 `layer-inversion`（HEAD 的导入面守护与 `test_real_repo_has_no_import_surface_findings` 已红），按「跨层只读协议定义在 core」口径新增 `core/progress.py::ProgressReporterProtocol`（只描述 `info`/`ok`/`warn`/`error` 四渠道），cache 改引 core 协议、report 侧零改动、**未开例外表**，并补 2 处回归用例；`technical.md` §8.7 增「跨层注解的导入方向」口径。余 49 处（`web` 20 / `tui` 20 / `cli` 4 / `providers` 3 / `qa` 2）留收尾批并在该批启用 `select`。

- **ANN001（参数缺注解）收尾批补齐 + 规则全量启用（rf-1223）**：`web` 20 / `tui` 20 / `cli` 4 / `providers` 3 / `qa` 2 共 49 处逐处按**真实用法**补齐（`run_manager`/`state`→`RunManager`/`RunState`、`app`→`Flask`、`response`→`Response`、errorhandler 的 `_e`/`e`→`Exception`（Flask 回调面要求可接受任意异常）、`_ok` 的 `data`→`object`（JSON 载荷开放域，取超类型而非 `Any`）、`hc`→`types.ModuleType`、`entry`/`parent`/`chapter`→`ChapterEntry`、`llm_names`→`dict[str, str]`、`result`→`CacheUpdateResult`/`PositionCacheResult`、`_run_cache_update` 的 `update_fn`/`print_fn`→`Callable[[list, ProgressReporterProtocol], _ResultT]`/`Callable[[_ResultT], None]`（两族结果配对用 `TypeVar` 保证同型，避免退化成 `Any`）、`attrs`→`list[tuple[str, str | None]]`、`items`/`item`→`Sequence[PanelItem]`/`PanelItem`、`rows`→`Sequence[str | None]`、`stream`→`TextIO`、`args`→`argparse.Namespace`、`reporter`→`ProgressReporterProtocol`、`df_data`→`pd.DataFrame`、`recorder`/`span_recorder`→`PhaseBreakdownRecorder | None`、`http_client`→`httpx.Client | None`），全程只加注解（不改行为/默认值/参数名/顺序），跨层注解一律走 `TYPE_CHECKING`，**执行期导入边零新增**；`Any` 0 处（唯一新增 `Any` 是 `qa/session.ask_report_qa` 返回注解 `dict[str, Any]`——异构结果信封；站点 `web/handlers._err` 用 `cast(str, …)` 表达「失败态必有 error」的契约，未改行为）、`object` 1 处。同批**启用规则**：`pyproject.toml` 的 `select` 追加 `ANN001`（全量 `E4`/`E7`/`E9`/`F`/`RUF100`/`ARG`/`BLE001`/`ANN001`），`src/test/**` 既有 per-file-ignores 条目由 `["ARG"]` 扩为 `["ARG", "ANN001"]`（不新建重复条目）；`technical.md` §8.7 把「注解缺失」从人评审口径改为机检口径，并记明测试域豁免理由。**ANN001 全量收口：294 处**（试点 32 + 第二批 84 + 第三批 `scripts` 129 + 本批 49），分四处批次完成、每批 pyright ERROR 恒 0；整树 `ruff check .` / `ruff check --extend-select RUF100 .` / `ruff format --check .` 三项 0、`check-types --ci` 0 ERROR、五目录单测 2467 全绿。

- **盲 except 纳入机检（rf-1219）**：`pyproject.toml` 的 `[tool.ruff.lint]` `select` 增 `BLE001`（仅此一码，不用 `BLE` 全家），全树 398 处宽捕获分两批清零——第一批 `report`/`core`/`analysis`/`cache`/`config`/`scripts` 共 244 处，第二批 `fetcher`/`llm`/`tui`/`providers`/`qa`/`web`/`cli`/`startup_wizard` + 测试域共 154 处；窄化 9 处（`stdout.reconfigure`、TUI `isatty` 探活 → `(AttributeError, OSError, ValueError)`，urllib 探活 → `OSError`，ctypes 内存查询 → `(AttributeError, OSError)`，函数内导入 → `ImportError`），其余 389 处保留宽捕获并逐处写明降级后果（`# noqa: BLE001 — …`）；规则开关与 noqa 形态同批落地（`RUF100` 恒开，noqa 不得先于规则出现），未用 per-file-ignores 整目录豁免。

- **未用参数纳入机检（rf-1218）**：`pyproject.toml` 的 `[tool.ruff.lint]` `select` 增 `ARG`，测试域（`src/test/**`）经 per-file-ignores 豁免（替身/回调参数天然未用，不属缺陷）；生产域 45 处未用参数逐处定型为「签名契约 → `# noqa: ARG00x — <理由>`」（29 处）、「签名可控 → 改名 `_x`」（15 处）、「死参数 → 删参并同步调用点」（1 处：`_test_runner/runner.run_mode` 的 `phased`）。此后未用参数由 lint 兜底，不再靠评审兜。

- **日期解析口径收口（rf-1215）**：全仓 `strptime`/`fromisoformat` 共 60 处调用、53 处各自包 try/except，失败语义**六种并存**（返回 `None` / `""` / 原串 / 抛错 / 哨兵值 / `pass` 续算），同一格式同一语义被重复实现。新建 `src/python/core/dates.py`，只收拢「同一格式集合 + 同一失败语义 + 同一返回类型」的明确重复组：`parse_datetime_ymd`（`%Y-%m-%d` → `datetime`，`ValueError`/`TypeError` → `None`）、`parse_iso_date`（`date.fromisoformat` → `date`，`TypeError`/`ValueError` → `None`）、`parse_datetime_iso`（`datetime.fromisoformat` → `datetime`，`ValueError` → `None`，非字符串仍抛 `TypeError`，与原口径一致），共替换 16 处调用点，**逐处保留原降级动作**（`return None` / `continue` / `return out` 各留调用点，不统一成一种）。语义确有差异的 33 处**一律不动**——哨兵值（`-1` / `0` / `""` / `'expired'`）、默认态赋值、刻意上抛的用户输入校验、异常路径写 warning 日志、多格式探测链、外层宽 `except Exception`——逐处把差异点写进 `technical.md` §8.7.1「日期解析口径」，作为口径事实位。另固化一条格式宽容度差异：`strptime("%Y-%m-%d")` 接受未零填充月日而 `date.fromisoformat` 不接受，故两个函数口径不通用。补 `test_dates.py` 30 条用例（正常/边界/闰日/非法/空值/非字符串/时区保留），断言即替换前各调用点的原语义。

- **警报字幕层叠收口（rf-1216，承接 rf-1214 登记项）**：`summary_section.html` 行情全不可用提示块的`color: var(--warn-text)` 内联声明改为复合选择器 `_report_styles.html` 的 `.empty-section.t-warn { color: var(--warn-text); }`（2 类 > 1 类，特异性胜过其后 `.empty-section` 的 `--text-muted` 灰字）——单类 `t-warn` 会被压成灰字，这正是该处此前只能停在「内联色」形态的原因；模板侧删该条内联 color、补 `t-warn` 类，`background` / `border-color` 两条声明不动。**等价证明**：从新规则集移除该条后重算哈希恰等于旧基线 `06f31870…`，故规则集变化严格为 +1 条（194 → 195），无删无改、业务字节面零变化；`test_report_type_scale._RULESET_HASH` 重标定并附基线复核记录与层叠等价论证；另补 2 条层叠契约用例（复合选择器形态必须保留 + 提示块不得回退内联色），防止将来被「简化」成单类而静默变灰。`check-style-guardrails` 内联色值仍为 0。

- **拆分两个巨型函数（rf-1213）**：`providers/news_dedup_anchor_policy.compact_anchor_file` 194 行拆出 `_anchor_snapshot`（读前分片快照）/ `_validate_snapshot`（读后并发校验）/ `_select_kept_lines`（每 key 最新 + 保留期 + 规则指纹归因）/ `_trim_to_target`（分支配额体积裁剪）/ `_persist_compact`（分组原子重写 + 备份 + 裁空分片清理）五个同模块私有函数，入口只剩编排与早退；`tui/handlers_switch.run_content_options_panel` 235 行把内嵌的 `_render` / `_on_text` 两个大闭包正文外提为模块级 `_render_switch_panel` / `_dispatch_switch_text`，闭包捕获的静态版面量（分组、编号块、实验项集、名称/键名/编号列宽）收进冻结 dataclass `_SwitchPanelLayout`，`state` / `session` / `apply_toggle` / `emit` 显式传参。只搬不改：两模块既有用例全绿（含 `test_prompt_contract` 的提示文案契约），外提函数的可执行语句与闭包体逐行一致，键位、提示文案与上屏顺序零变化。
- **内联颜色声明复核（rf-1214）**：按审计「余 10 处内联颜色声明」逐处核实，实际是 `color:` 子串匹配——9 处为 `background-color`（`position_structure_section.html` 相关性热力/空态底色，契约登记的 `--corr-*`/`--cell-na-bg`/`--surface` 组件派生 token）与 `border-left-color`（`data_source_status_section.html` / `portfolio_history_drawdown_section.html` 的状态条边框色），改语义文字色类会造成底色变字色或丢边框语义，故登记不改；唯一真字幕声明 `summary_section.html:94` 的 `color: var(--warn-text)` 因 `.empty-section` 规则层叠在后（同为单类选择器、内含 `--text-muted` 字色），纯 class 替换会变成灰字，需复合选择器或调整工具类顺序，同样登记待决策。本轮模板零改动，报告页规则集哈希与 whatif 逐字节基线均未变，`check-style-guardrails` 内联色值仍为 0。
- **模板彩色内联色归位语义 class（rf-1212）**：模板里余下 34 处写在 `style` 属性上的文字颜色声明归位到语义 class——`--profit` 9 处（回撤/VaR/最大单日跌幅/未恢复等风险红字档）用 `.profit`，`--primary` 7 处用 `.text-primary`，`--warn-text` 3 处用 `.text-warn`，`color: var(--text)` 4 处直接删声明（正文默认色）；另新增 `.text-tertiary` / `.text-danger` / `.llm-status-{disabled,failed,cached,success,unknown,thinking}` 共 8 条语义色工具类，承载 `--text-tertiary` 2 处、`--danger-text` 1 处与 `--llm-status-*` 7 处，每条一行、值只引用同名 token。字号/间距等其余内联声明与文案结构不变：8 个章节模板剥除 class/style 后逐字符一致，报告页样式规则多重集 +8 条、无删无改。
- **模板内联灰色内联色归位语义 class（rf-1211）**：报告与 What-if 模板中 58 处 `style="…color: var(--text-muted|--text-faint|--text-secondary)"` 的颜色声明移到元素 class 上，新增 `.text-faint` / `.text-secondary` 两条语义色工具类（`.text-muted` 沿用既有规则），色值只出现在 token 与工具类里，符合 DESIGN.md 的颜色施加契约；字号/间距等其余内联声明与视觉表现不变。
- **抑制清单与启用规则对齐（rf-1208）**：`pyproject.toml` 的 `select` 含 `RUF100`——`noqa` 只在指向真在跑的规则时才有意义，落在未启用规则上的抑制判为死抑制并硬失败。全树 114 处落到未启用规则上的抑制（`BLE001`/`ANN001`/`ARG001`/`PERF203` 等）写成行内说明注释（`有意宽捕获：…` 交代失败后果与不窄化理由，`说明：…` 交代签名契约或入参对象）；6 个脚本门面的 200 个再导出名由 `__all__` 声明（再导出即公开面，行内 `# noqa: F401` 清零），其余冗余/失效指令整条删除，5 处仍会触发的 `E402` 保留抑制并补理由；`[tool.ruff.lint]` 上方写明抑制的生效域与评审口径落点（`technical.md` §8.7「代码质量口径」）。

- **设计契约的图表色值口径收口（rf-1209）**：`DESIGN.md` 的 Do-Don't #1 只豁免 token 兜底默认值（`cssVar('--chart-*', fallback)` 的 fallback、`ChartTheme` 调色板常量、页内脚本 `|| '#…'` 兜底值）与双主题 override 块；#10 要求模板与页内脚本取值一律经 `window.ChartTheme`（半透明填充由 `.alpha()` 派生）；#13 把分类调色板（`doughnutColors`/`benchmarkColors`/`barColors`）定为 `ChartTheme` 常量、随主题切换整组替换。

- **core 反向依赖纳入分层机检并登记（rf-1210）**：`check-import-surface` 的 `layer-inversion` 规则集覆盖 `core`——最底层经函数内延迟导入取数层属探针职责，允许但要逐处登记；`core/check_sources.py` 的 4 个目标模块（5 处调用）登记进 `scripts/_import_surface_exceptions.json` 并带到期日与收敛方向（探针注册表）；`technical.md` §9 同步 core 行、例外行与探针说明。

- **自检的缓存目录探针取缓存层唯一解析器（rf-1205）**：`core/doctor.py` 的目录探针把「缓存目录」交给 `cache.get_cache_dir()` 解析——`INVEST_CACHE_DIR` 覆盖（演示/基准运行的缓存隔离入口）生效时，自检上屏的路径、哨兵文件的写入目录就是实际生效目录，隔离 run 的探针不触碰真实 `data/cache`。补 1 条回归（隔离目录下上屏路径 = 解析器结果、哨兵落在隔离目录、真实 `data/cache` 无哨兵残留）。

- **日志配置缺省值单源（rf-1206）**：`core/logging_defaults.py` 承载唯一一张日志缺省值表（`DEFAULTS`/`LEVELS`/`RANGES`），`config/_logging.py` re-export 同一对象，`core/logger.py` 与 `core/doctor_logs.py` 从同包取用——「启动读取 / 面板校验 / 自检回显」三处取的是同一份事实；`_DEFAULT_TABLE_FILES` 的登记同步指向该文件。补 2 条回归（配置回落值等于缺省值表、`config._logging.DEFAULTS is core.logging_defaults.DEFAULTS`）。

- **报告百分比格式化口径单一来源（rf-1207）**：`report/_format.py` 提供 `fmt_pct_points()`（入参是百分数点数）与 `fmt_pct_fraction(value, *, signed=False)`（入参是小数比例），决策依据 / 事件窗对照 / 调仓纪律回放三处调用点按各自口径显式引用对应函数，既有输出字符串保持一致；非数值入参统一回「—」占位，取值失败按缺失呈现而不中断渲染。补 1 个单测（None / 字符串 / 负数 / 0 边界）。

- **两处运行期断言/字典直取的隐性契约（rf-1204）**：`report/decision_llm_capture.py` 原用 `assert code is not None` 收紧「该行必含 6 位代码」——`python -O` 会剥离 assert，优化模式下 None 会被当代码继续往下走；改为在 `elif` 条件里用 walrus 取值、体内直接用，断言与二次取值一并去掉。`cli/cli.py` 原用 `handlers[args.command]` 直取需 config 的命令分发表，subparsers 与表不同域时抛 `KeyError`；改为 `_config_required_handlers()` 单点定义 + `.get()` 判定，漏挂时收口为 `[ERR] 未知命令` 与 `_EXIT_SEVERE`。补 2 条回归（未知命令按用法错误收口、决策抽取在两种模式下取值一致）。

- **再平衡分类的 ETF 名称维度与两处死 logger（rf-1203）**：`analysis.rebalance.classify_holding` 只在场内区间（`is_exchange_fund_code(code)` 为真，即代码 5/1 前缀）内消费 ETF 判定的名称半区——场外 ETF 联接基金（`天弘沪深300ETF联接A`/`000961`）按场外基金口径归 `fund_equity`，代码 5/1 前缀的场内品种归 `equity`，`test_rebalance.py::TestClassifyHolding` 的两条用例分别钉住这两种口径（名称维度独立化的实现会让前者变红）；`analysis/rebalance.py` 与 `analysis/metrics_risk.py` 的 `import logging` 与 `logger` 对象无调用点，一并删除

- **数据源 HTTP 替身单源（rf-1200）**：`src/test/_fixtures/http.py` 提供 `FakeResponse` / `FakeClient`——`FakeResponse(text, status_code, *, json_body, raise_status, encoding, content, json_error)` 覆盖 `.text` / `.content` / `.status_code` / `.encoding` / `.json()` / `.raise_for_status()`，`FakeClient(response, *, by_url, error)` 覆盖上下文管理器、`get` / `post`、按 URL 后缀或包含匹配分派、传输级异常注入与逐次请求记录（`calls` / `posts` / `gets`）。`test_cninfo` / `test_hithink` / `test_datasink` / `test_tiantian_fund_fee` / `test_tiantian_purchase` / `test_tiantian_base_faults` 六个用例文件共用这一份替身，本地 12 类替身定义删除，各文件断言与被 patch 目标保持一致；巨潮用例的「慢 post」时序桩由 3 行 `FakeClient` 子类表达。

- **TUI 入口覆盖以委托断言与子进程表达（rf-1201）**：`test_tui_main_loop_branches.py` 的入口覆盖分两处——包入口用例经 `importlib.import_module("src.python.tui.__main__")` 断言 `__main__` 直接绑定 `tui.main`；`__main__` 的 Ctrl+C 收尾用例在子进程里执行（`sys.executable -c`，子进程内摘掉项目根后经 runpy 走真实入口，断言 `returncode == 0` 与 stdout 告别语），本进程的 `sys.path` / `sys.modules` 在用例前后保持一致。

- **发布台账读取面单源（rf-1202）**：`logs/release.jsonl` 的读取统一由 `scripts/_release/_timing.read_ledger_records(path)` 提供（文件缺失视为空台账；空行、损坏 JSON、非 dict、缺 `command` 的行跳过，单行损坏只影响自己那一行）；`scripts/probe-release-ledger.py` 与发布编排尾行的 token 统计（`_release/_commands_base._finish_timing`）同调该入口，两边的台账行口径只剩一处定义，probe 的输出格式与 `--last` / `--version` / `--json` / `-v` CLI 面不变。

- **穿透行业分类状态以单字段表述（rf-1199）**：`report/penetration._compute_penetration_top10_uncached` 的结果用 `industry_status` 一个字段表达四种状态——`ok`（取到行业数据）、`empty`（有 A 股代码但预取与补取均为空）、`no_a_share`（穿透资产全为非 A 股，预期行为）、`unreachable`（取数异常，产出侧当前不写该值）；消费处 `report/penetration_sheet.build_penetration_data_status` 按枚举一次分流（`empty` / `unreachable` 登记降级，`ok` / `no_a_share` 不登记），任何新消费方读同一字段即得正确口径，「全为非 A 股」不会被记成数据降级。

- **行业降级计数在预期行为后复位（rf-1192）**：`report/penetration_sheet.build_penetration_data_status` 在 `ok` / `no_a_share` 两态对 `penetration_industry` 调一次 `DegradationTracker.reset`；本域失败计数跨报告累积（T3 空数据阈值 3 次），预期行为与非预期行为交替出现时历史计数不参与下一次判定，故「取数为空 ×2 → 全为非 A 股 → 再取数为空」不会因遗留两轮而提前报「行业分类不可用」。

- **后置模块的重算原因与预检同源（rf-1198）**：`self_review` / `holding_change` 等在上游产出后才定键的模块，「上一轮键」经 `llm/cache_policy.previous_module_key` 取（跨报告基线优先、无基线回落进程内记录），与预检共用同一取数点；报告收尾的基线快照一并落这些模块的键（`llm/skeleton.module_cache_keys`），故同键未命中记 `ttl_expired`、换键记 `fingerprint_changed`、无基线记 `cache_miss`，与四个基础模块口径一致，`recompute_reasons` 不再混入两种含义。

- **「合计 = 分项之和」占比口径保护未生效（rf-1197）**：`llm/fact_checker/_context._is_breakdown_sum_context` 识别「合计值（分项 + 分项）」的正则把括号前缀限制在 3 字符，而合计值文本本身（如 `18.3%`）就有 5 字符，该判据对实盘形态恒返回假——「把低风险资产从 18.3%（12.5% + 5.8%）提到 25% 附近」这类自洽占比会被当成单品种收益率改写，句子随即自相矛盾；现把前缀上限放到 8 字符（仍要求括号紧邻合计值），分项与合计不自洽时照旧不判为占比口径，并补 2 条回归（实盘形态命中 + 不自洽不命中）。

- **t 分布 CDF 在 t=-∞ 处返回 0.0（rf-1196）**：`analysis/_math_utils._t_cdf` 的`if x <= 0` 分支（仅在 `|t|` 溢出为无穷时命中）恒返回 1.0，-∞ 处 CDF 应归 0；现按 `t` 符号取两侧极限（`t < 0` → 0.0，否则 1.0），`correlation` 的 `2*(1-CDF)` 与 `metrics_risk` 的 p 值在 t 统计量负向溢出时取左侧极限（0）。

- **自检目录探针的用例断言到隔离替身（rf-1195）**：`test_doctor_branch_faults.TestProbeTargets` 改为在收集期捕获真实 `_probe_targets` 引用并按其实现断言——`get_config` 给出 `output_dir` 时探针目标即该目录，配置读取失败时回落 `_DEFAULT_OUTPUT_DIR`；附目录探针「空 `.xlsx` 目录」与复盘账本概览「依赖模块导入失败」两态降级用例。

- **t 分布 CDF 在 t=0 处返回 0.0（rf-1194）**：`analysis/_math_utils._t_cdf` 的 `x >= 1` 分支（仅在 `t == 0` 命中）返回 0.5，中位数处 CDF 与 `t→0⁺`（0.5004）连续；`correlation` 的 `2*(1-CDF)` 与 `metrics_risk` 的 p 值在「无相关 / Beta 恰为 0」时读到 0.5 对应的 p=1.0，不再出现 p=2.0 这类越界读数。

- **资金流向不可用信号在数据源矩阵里无行可落（rf-1193）**：`report/_generation_full._fetch_sector_flow` 的空载荷与异常两态统一登记 `source_key="ff_sector_flow"`，故「行业资金流向不可用」这一信号无论因空载荷还是调用异常退化，都归入矩阵「资金流向」行（该行前缀为 `ff_`，匹配规则 `key == prefix or key.startswith(prefix)`）；配 2 条回归：两态登记键相等且非 `fund_flow`、登记键经矩阵归属落到 `fund_flow` 行。
- **穿透表「行业分类不可用」降级在行业取数全空时可触发（rf-1191）**：`report/penetration._compute_penetration_top10_uncached` 第三阶段把 `remaining_data` 提到 `if remaining:` 之外初始化为 `{}`，判据改为「预取与补取均为空」（`not prefetched and not remaining_data`）——行业链路熔断（`fetcher/industry.batch_fetch_industry_data` 回空）或批量全败（只回填成功项）时写入 `industry_status="empty"`，`penetration_sheet.build_penetration_data_status` 的降级分支由此可触发；无 A 股代码时写 `industry_status="no_a_share"`，让消费方按枚举值区分「预期不降级」与真实失败（该值在状态构建处按预期行为跳过，不记降级）。补 3 条回归：预取+补取双空判 `empty`、补取部分命中仍算可用、无 A 股不改降级结论。
- **后置模块的重算原因归因恒判 `ttl_expired`（rf-1190）**：`llm/skeleton.generate_llm_content` 先把本轮键写入 `_PREV_MODULE_CACHE_KEY` 再做原因判定，判定读到的「上一轮键」永远等于本轮键 → 「无上轮记录 → `cache_miss`」与「换键 → `fingerprint_changed`」两个分支不可达，内容变化被系统性误标成「TTL 到期」，据此判断「放宽 TTL 能省钱」会得出错误结论；归因改取写基线**之前**的键，并把该块抽为 `_attribute_recompute_reason()`（单一职责，同时降低骨架圈复杂度），补 6 条回归（三态归因 / 已归因不覆盖 / 无汇聚器 / 端到端两轮判 `fingerprint_changed`）。
- **敏感缓存清理遇畸形 `_ts` 中断整轮（rf-1189）**：`cache/_cleanup.clean_sensitive` 的时间戳直接参与减法，`_ts` 为字符串或 None 时抛 `TypeError` 并被导入期兜底吞掉 → 该轮清理中止，盘上其余过期持仓/穿透/基金缓存全部漏清（`cleanup_expired` 同期已有类型容错，两入口口径不一致）；抽出共享 `_payload_ts()` 让两入口同源，敏感缓存按「无法判定年龄 = 极旧」处理（宁可多清不可留存），单文件畸形不再打断后续扫描。
- **llm_settings 运行约束静默丢失（rf-1188）**：`config/_llm_schema.apply_flat_updates` 的 runtime 扁平键查表按「字段名」而不是「扁平键」建反向表——`llm_max_concurrency` / `llm_max_thinking_concurrency` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` 写回时落到顶层、v2 `runtime` 段不更新，随后 `flatten()` 用 runtime 段的值压过顶层透传 → 用户在配置面板/编辑层改的并发、重试延后、时间预算设置**静默丢失**（`llm_settings.json` 缺失走默认兜底、或同批含 `debate`/`fact_check` 更新时走该路径即触发）；改按扁平键建反向表，配 12 条落点敏感回归（`runtime` 段落值 + 顶层无扁平键残留 + 六个字段从 `RUNTIME_FIELDS` 参数化派生 + 写盘级解析残留 JSON），并修掉既有「只经 `flatten()` 回读」的假绿往返用例。

### 新增

- **发布台账按版本汇总（rf-1187）**：新增只读脚本 `scripts/probe-release-ledger.py`（`--last N` / `--version` / `--json` / `-v`），按版本切段输出每版墙钟、分步耗时、会话 token 增量与失败步；token 列口径明确标注为「相邻台账行之间的会话增量」，不是发布命令本身的成本；配 11 条用例（切段口径/跨版本不串账/同会话取前后差/新会话首行记 0/累计回退记 0/脏行与缺失容错/JSON 与选择器）。

### 测试

- **测试覆盖率 92.1% → 99.996%（十四个批次）**：接入 `pytest-cov` 后按「失败路径优先、只值一测的分支也不放过」逐批补齐；本轮收尾时 `cli/_handlers`、`report/news_correlation`、`cache/operations`、`report/llm_content`、`report/summary`、`report/_orchestrator_data`、`report/html_jinja_env`、`report/whatif_writer`、`report/pipeline_data_builder`、`report/_run_scope`、`providers/news_dedup_anchor_store`、`tui/handlers_log`、`tui/progress`、`providers/tiantian_base`、`report/_report_health`、`report/excel_news_warning`、`cache/_paths`、`cache/_store`、`cache/_cleanup` 等模块均达 100%（`llm/skeleton` 99%，保留 1 行早退后的不可达防御分支）。逐批口径：
  - **第 1 批（92.1% → 92.9%）**：可靠性/边界类零散守卫与接口回显分支（首轮补齐后的收尾段）。
  - **第 2 批（92.9% → 93.5%）**：analysis guard 分支、缓存刷新编排、config 写路径/校验分区、pricing 解析、akshare 扩展、东财净值历史、回撤页签、HTML 构建阶段埋点、TUI 入口分支。
  - **第 3 批（93.5% → 93.9%）**：Excel 页签写入隔离、HTML 渲染降级、新浪解析回落、提示词表格分支、CLI 命令簇。
  - **第 4 批（93.9% → 94.7%）**：医生检查项故障、行情时段官方层、因子目录探测、缓存面板分支、API 响应解析、提示词数据块、新闻去重锚点策略、基金业绩、穿透页签、调度回放面板、LLM 用量小结、Web 错误分支与持仓编辑校验。
  - **第 5 批（94.7% → 94.8%）**：`cache/_store` 写侧故障、`cache/_cleanup` 清理故障与敏感缓存、锚点存储容错、运行边界九步复位故障注入、pipeline_data 注册与校验分支。
  - **第 6 批（94.8% → 95.0%）**：TUI 诊断面板与状态条接线、天天基金公共 HTTP 故障面、健康检查收口容错、新闻页签降级、缓存目录权限自检。
  - **第 7 批（95.0% → 95.1%）**：Jinja 字节码缓存与过滤器兜底、中断收口五步逐步容错、调仓 What-if 产物写出与匿名装配。
  - **第 8 批（95.1% → 95.2%）**：LLM 内容写入边角（游离文本分段/占位文案/契约小节）、编排数据逐域降级、汇总页降级渲染。
  - **第 9 批（95.2% → 95.5%）**：缓存编排分市场明细与预热、LLM 骨架边角（空输出/用量合并/凭据回落/原始输出过滤/账本回灌）、新闻关联关键词扩展与费用口径、CLI 配置面（set/list/源名校验/非 UTF-8 禁彩）。
  - **第 10 批（95.5% → 97.97%，缺口 2249 → 1012 行）**：core 与 config 残余不可达分支——provider 注册表与健康态、性能计时器与阈值、持仓读取容错、LLM 设置/提供方/定价解析边角、json patch 逐层失败、配置校验分区、降级追踪器通道统计、日志配置落盘失败、持仓追踪器清洗、TUI 与 CLI 入口分支。
  - **第 11 批（97.97% → 98.12%，缺口 1012 → 942 行）**：六个模块的 69 行目标缺口全部补齐——`tui/handlers_config` 15 行（Esc 改配置不落盘、调优项输入中断、调优/匿名化面板筛选态跳行、页脚随改动计数上屏、指数池面板中断）、`tui/handlers_report_chapters` 12 行（费用摘要无金额明细时省略、窄档备注行、`u` 撤回消费、`?<键名>` 直取子项详情、实验子项用量备注、面板中断收会话、章节详情费用行）、`core/cassette` 11 行（读取不可读文件转 `CassetteError`、写盘失败上抛、索引遇并发删除按空/零降级、录制传输读全响应体后再录）、`core/jsonl_store` 10 行（既有文件不可读时重建、读取/裁剪不可读按空处理、裁剪保留非对象行）、`cache/_io` 10 行（损坏文件删除失败仍当无缓存、`replace` 被锁走删除+rename、`chmod` 不支持时忽略、写纯文本格式时清旧 `.gz`）、`config/features` 11 行（覆写文件非对象、非法补丁拒绝落盘、未登记开关不生效、非 bool 值只告警、恢复默认清掉运行时残留键）；新增 6 个测试文件共 37 条用例，全仓缺口由 1012 行降到 942 行（49972 语句 / 942 未覆盖 / 98.12%）。
  - **第 12 批（98.12% → 99.4%）**：`analysis._math_utils`（t 分布端点、样本不足与基准零方差）、`analysis._factor_formulas`（非法收盘价、有效对不足、标量 NaN 铺满、量价背离符号、60 日收益偏度、横截面日均值成分数下限） 等模块的残差分支补测；相邻改动修 `_t_cdf` 两端取值（`t=0` 取中位数 0.5、`t=-inf` 取 0.0、`t=inf` 取 1.0），自检目录探针用例改取真实实现断言并补降级用例。
- **第 13 批（99.4% → 99.6%，残差分支收尾）**：`llm`（熔断状态展示面、盘中复用归因、证据索引、档位解析降级）等模块的不可达/降级分支补测。
- **第 14 批（99.6% → 99.996%，残差收口）**：204 行缺口逐行定性——能由合法输入触达的补真用例（约 60 行，含 `__main__` 入口改子进程执行 + 覆盖归并），可证明不可能执行的删死码（40 余处，每处附类型/契约/数学证明与「异常面不变」论证：`rebalance` 四处冗余守卫、`text_layout` 硬切互斥分支与恒非空循环、`skeleton` 早退后的 else、`anonymizer` 恒假份额下限、`liquidity` 已判场外却档位未知的分支），不确定的保留上报。最终仅剩 2 行保留未覆盖（`schedule_replay` 注入面护栏、`news_dedup_rules` 性能分支，构造条件与理由见 `test-coverage.md`）。期间顺带修 3 个问题：`classify_holding` 名称维度被误判为死码（380 组新旧对照证明删除正确，补钉住用例，`rf-1203`）、`liquidity` 的档位未知状态与 R-LIQ-03 口径冲突（删分支 + 需求口径对齐）、子进程覆盖归并把 `src/test` 并入导致 TOTAL 语句数翻三倍（量测域收紧到 `src/python` 单源）。
- **覆盖率接入与首轮缺口补齐**：`requirements.txt` 增 `pytest-cov`（此前项目只有测试规模快照、没有行覆盖率数据）；据首轮实测（`src/test/unit`，90.7%）补齐 9 个薄弱文件的分支覆盖——`report/excel_module_loader`（53.9%→100%）、`llm/_debate_router`（60.0%→100%）、`report/excel_fund_deep_analysis`（28.9%→97.4%）、`providers/tiantian_nav`（50.7%→94.0%）、`tui/handlers_config`（58.2%→96.3%）、`tui/tui_keys`（61.5%→91.9%）、`tui/handlers_holdings`（64.7%→93.6%）、`web/server`（59.5%→83.5%）、`report/_report_factor_metrics`（50.9%→88.3%），整体 90.7%→92.1%，`<60%` 文件由 6 个降为 0 个；新增 9 个测试文件共 184 条用例，聚焦降级链路（ImportError 逐模块兜底 / 数据源故障 vs 数据不足 / 辩论两级回退清空容器）、序列拆包与 UTF-8 解码、持仓录入撤销与保存防线。
