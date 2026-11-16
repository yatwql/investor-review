# 变更日志归档 — v0.18.x

> 归档时间：2026-11-16（v0.18.2 发布并入；已并入 3 段：v0.18.0（11-12）、v0.18.1（11-15）、v0.18.2（11-16））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.18.0 ~ v0.18.2（2026-11-12 ~ 2026-11-16）
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
