# 自审记录归档 — v0.18.x

> 归档时间：2026-11-12（v0.18.0 发布，本系列首批已修复批次并入）；2026-11-12 v0.18.0 本批原表搬运；2026-11-15 v0.18.1 本批原表搬运；2026-11-16 v0.18.2 本批原表搬运；2026-11-17 v0.18.3 本批原表搬运；2026-11-18 v0.18.4 本批原表搬运；2026-11-18 v0.18.5 本批原表搬运；2026-11-19 v0.18.6 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.18.x 已修复项（按发布版号批次，v0.18.0 → ）（含 v0.18.6）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 已修复（0.18.0）

> 完整复盘见 `changelog.md` 0.18.0 段；此处为台账原表搬运（无损），本批发布日 2026-11-12。

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1133** | `core/atomic_write.py` 声称「集中 mkstemp + os.replace 原语」，但只登记了 2 处有意例外；全仓实际另有 4 处自留原子写实现（报告 HTML / Excel 产物、模板字节码缓存、锚点分片），后三项属域外但注释未声明边界，读者无法判断是漏收还是刻意 | 注释补齐为 6 处例外并逐条写明契约理由（中断收口登记 / 字节码缓存与回收成对 / gzip 追加 + 旁文件哈希），不动实现 |
| **rf-1131** | plan.md 的 `## 归档` 标题被拼到 plan-249 行尾（原文为「…第 8 节。## 归档」，标题与上一句粘成一行），归档索引段失去标题——`_doc_section(plan, "## 当前迭代待办", "## 归档")` 找不到边界，待办区被静默拉长到文件末尾；同批四个已完成项（plan-248~251）与其四份结构契约文档跨 v0.17.9 发布仍未迁档 | 标题断行修复；四个已完成项按其标题形态迁入 `archived_plan.0.17.x.md`，四份契约文档 `git mv` 进 `docs/archive/v0.17.x/`；`folders.md` 目录树与统计行同步（契约见各文档第 8 节） |
| **rf-1132** | `check-doc-drift` 的 plan 分区检查只认 `## ✅ plan-N` 标题形态，粗体 `**plan-N …**：已完成` 完全扫不到，已完成项可长期滞留待办区（rf-1131 的四条即由此漏检） | 新增 `_PLAN_BOLD_DONE_ID` 分支（只匹配「已完成」结论句，在办进度句不误报）+ 2 条回归用例（报/不报各一） |
| **rf-1130** | 智囊团深度复盘 `timeout` 与实测生成时长几乎相等（116 / 119 / 201s vs 120s），周期性撞 `core.http_client` 端到端墙钟硬截止：请求被放弃后整条原样重发，同一份内容付费两次并多等一整轮 | `timeout_expert_review` 120 → 240（按 `max_tokens`/实测速率 ≈215s 留余量），默认值表/代码兜底/用户配置/文档同步；新增 `TestTimeoutCoversFullGeneration` 回归用例 |

## 已修复（0.18.1）

> 完整复盘见 `changelog.md` 0.18.1 段；此处为台账原表搬运（无损），本批发布日 2026-11-15。

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1143** | 62h 自审发现两处新债：①不动作类决策按日重复登记（每轮报告为每只持仓各记一条，730 天保留期下账本与结算事件按「持仓数 × 天数」膨胀）；②`build_evidence_index(news_items=…)` 生产从不传参（投机 API），并留下随之变死的 `_hash8` | ①新增 `decision_ledger.pending_inaction_exists()`，登记侧对 `direction=0` 行按「同 code 未结算」跨日去重（结算后可登记新一期），补 2 条用例；②删除该参数、对应新闻用例与 `_hash8`/`hashlib` 依赖 |
| **rf-1142** | 120h 自审发现三处「设计已写、实现未接」的债：①`evidence_index.render_index_lines` 与 `EVIDENCE_KIND_LABELS` 只有定义与测试引用，属投机 API；②建议硬约束 `validate_recommendation()` 仅测试调用，生产零调用（硬约束形同注释）；③契约校验记录的 `as_of` 存进结果却无人消费 | ①删除两个无生产引用的符号与其用例；②在 `rebalance_advisor` 每条建议上显式落 `execution_status`/`review_required` 并调用校验器做不变量守卫（违规行丢弃并告警），补 2 条用例；③决策书前言改为「数据口径 <as_of>；…」，补 2 条用例 |
| **rf-1141** | 决策书（`decision_book`）在启用态报告里不出现：判断依据块在数据准备阶段装配，而结构化契约要到 LLM 生成后一遍才落载体——`build_decision_basis_data` 里挂的 `decision_book` 恒为空，HTML/Excel 两端整块缺失（单测只直接构造契约，看不出时序问题） | 改为渲染期幂等补挂 `decision_book.attach_decision_book()`（HTML 上下文装配与 Excel 判断依据块写入各补一次），补 3 条挂载用例；并用 `--feature llm_research_contract=true` 真机跑通全量报告，HTML/Excel 均出现「决策书」块、判决=证据齐备、主张均带 evidence id 与失效条件 |
| **rf-1140** | 报告管线单测未声明离线桩：`generate_report()` 会起数据源健康检查线程（真实网络 + akshare `py_mini_racer` V8 初始化），xdist worker 里并发初始化 V8 会段错误崩溃（CI：3 个 worker crashed，整套 1.5min → 12min，且偶发才出现、难定位） | 三个报告管线测试文件统一声明 `offline_external_sources`（探针即时失败、零退避、不触发 V8）；并新增契约守卫 `test_offline_pipeline_contract.py`（真实调用管线入口却漏声明离线桩即红，防同类复发） |
| **rf-1139** | akshare 1.19+ 把 `bond_zh_us_rate` 改名为 `bond_zh_us_yield_em`（数据集/中文列名不变），而取数只认旧名：CI 装到 1.20.42 后 11 条无风险利率用例在 `@patch("akshare.bond_zh_us_rate")` 处 AttributeError 直接失败；生产侧还把「属性不存在」当调用异常，白记一次 akshare 熔断失败（新版用户每份报告都误报数据源故障） | 新增 `_resolve_bond_yield_api()` 按版本探测两代 API（旧名优先，探测结果进程内记忆，缺失只降级不记熔断），两处调用点改走 `_bond_yield_frame()`；用例改为 patch 本方 seam（版本无关），新增 4 条探测/降级用例；文档四处口径同步 |
| **rf-1138** | 全仓扫描发现 4 组「跨模块各写一份」的常量（注释里还写着「与 X 同值」）：退出码 `_EXIT_*`（CLI / Web worker 各一份）、push2 快照接口 URL（`core/market_hours` / `providers/eastmoney_industry`）、年化交易日数 252（3 个 analysis 模块）、最小样本 20 与份额容差 1e-3（各 2 个模块）——改一处漏改另一处会让两条路径口径分叉 | 单源归位：退出码与 push2 URL 进 `core/constants.py`（`EXIT_*` / `EASTMONEY_PUSH2_BASE`），统计/容差常量进 `analysis/_math_utils.py`（`TRADING_DAYS_PER_YEAR` / `_MIN_SAMPLE_DAYS` / `SHARES_EPS`），各调用点保留原名做别名；新增 `test_cross_layer_constants.py` 7 条守卫断言各处值等于单源值 |
| **rf-1137** | 18h 自查发现两处新代码缺直接覆盖：`market_hours.is_otc_nav_disclosed` 在所有用例里都被 patch 掉（边界/时区换算没测过），`ProviderState.cooldown_override` 新增的持久化字段无落盘往返用例（重启后自定义冷却期会丢） | 补 6 条用例：披露时点边界（19:59/20:00/早间）、naive 视为北京时区、跨时区换算、自定义冷却期落盘回读 |
| **rf-1136** | 「代码类型判定中心化」纪律被违反：`report/news_correlation._index_holdings` 自建 `"ETF" in name` 判定，既绕过 `core/code_utils.is_etf_by_name`，又因大小写敏感导致小写 `etf` 的品种不进 ETF 关键词扩展分支、且 `replace("ETF","")` 剥不掉，关键词召回与该品种的资产类型口径分叉 | 改为 `is_etf_by_name(name)` 判定 + `re.sub(r"(?i)etf", "", name)` 剥离，补 3 条回归用例（小写扩展 / 大写保持 / 判定单源） |
| **rf-1135** | `developer-guide.md` 把 HTML 生成细分写成「四步」且断言「模板编译占绝大多数」——实测 `模板渲染` 约 0.0s、`面板视图装配` 2.1s of 2.13s，该结论会把优化方向指向 jinja；同时 `面板视图装配` 这一步（本轮新增的计时点）文档未列 | 两处文档同步为实际细分与实测结论（`developer-guide.md` 慢段排查表、`technical.md` 编排器职责链） |
| **rf-1134** | `check-doc-drift` 的已解决台账行只认 `| **rf-N** |` 加粗形态，未加粗时既不进已解决集合、归档步也按「本版无待迁档」跳过（0.18.0 发布时实际发生：已修项主台账未被搬运） | 新增 `_RF_ROW_UNBOLD` 分支：已解决区出现 `| rf-N |` 未加粗行即报 finding + 2 条回归用例（报/不报各一）；归档识别口径不变 |

## 已修复（0.18.2）

> 完整复盘见 `changelog.md` 0.18.2 段；此处为台账原表搬运（无损），本批发布日 2026-11-16。

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1144** | 分层门禁只覆盖 5 层：`cache` / `config` 的向上依赖无人看守，其中 `cache/operations.py` 判定基金经 `report.fund_performance.is_fund` 转发纯 `core` 谓词，属真实越界 | 规则扩到 `cache → report/llm/tui/web/cli` 与 `config → report/llm/analysis/tui/web/cli`（`cache → fetcher` 显式允许）；基金判定改直调 `core.code_utils.is_fund_holding`；存量 7 处入例外表并写明下沉方向，`technical.md` 例外表重生成 |
| **rf-1145** | `report/html_writer.py` 因拆函数涨到 959 行，逼近 1000 行红线 | 渲染前置装配（面板视图 / 数据源状态包 / 章节可见性与掩码上下文）下沉 `report/_html_render_context.py`，写出函数回到 751 行 |
| **rf-1146** | `DESIGN.md` 组件矩阵声称字段错误态 `.has-error` / `.field-error` 已落地，实际全仓无代码挂载（只有 CSS 定义） | Web 显式保存失败处接线（行挂 `.has-error` + 行内 `.field-error` 原因，成功即清）；`.field-error` 补 `flex-basis:100%` 避免与输入框挤同一 flex 行 |
| **rf-1147** | 文件膨胀登记表（P4）8 条多已过期（含已降到 656 行的一条），实际 >700 行文件 16 个 | 按实测重写登记表，补登 10 个越线文件与拆分方向 |
| **rf-1148** | `test-chart.html` 调试页只覆盖 6 图，而生产 `chart-init.js` 已初始化 12 图——Chart.js 升级验收会漏一半图 | 补 6 张图与配套数据段，自检基数改为派生（`KEYS.length`）；`chart-init.js` 头注、`folders.md`、`src/static/README.md` 的「6 图 / 9 张图」口径统一为 12 图 |
| **rf-1149** | `docs/archive/v0.17.x/` 顶层散落四份设计契约，与 v0.15/v0.16「顶层只放三份台账 + 专题子目录」的归档布局不符 | 收进语义子目录 `stage-split-contracts/`；`check-doc-drift` 新增归档布局校验（第 28 项，守护脚本数量不变）并配 2 条用例 |
| **rf-1150** | `DESIGN.md` / `DESIGN-TUI.md` 残留复盘痕迹（「旧 `--color-*` 已删映射」「存量 9 处」「原 `placeholder-note` 归并」「机检落地/观察期」等） | 全量改写为当前状态陈述；两份契约新增守卫用例（出现复盘式用词即红）；`test_report_empty_states` 的「应记录归并历史」断言反转 |
| **rf-1151** | 用户/管理文档多处口径过期：`[S]` 仍写五组、Web 配置编号 1-5/6-9/10-11/12-14、Web 面板「10 块」、行业 Beta 仍挂已删除的 `industry_beta` 开关、进度抽象仍写 `report/progress.py` 里的 `TuiProgressReporter` | 逐份校正到实测（六组 14 项 / 16 块 / `factor_catalog` / `tui/progress.py`），`DESIGN.md` 护栏观察项数字改实测，features.json 示例改用上屏开关 |
| **rf-1152** | 「缓存命中率 39%」与「`llm_news` 30 条全 miss」易被误判为缓存失效（实际是 TTL 到期与 refresh 组清空） | `datasource-reliability.md` §4.3 补判读口径：命中率按距上次运行间隔分层、真异常看同键重复未命中；说明 `llm_news_item_*` 属行情类缓存组会被整组清 |
| **rf-1153** | `release.py verify` 只跑核心单元，未覆盖 integration 档：渲染前置装配下沉后 3 处集成用例仍从 `html_writer` 导入 `_compute_section_visibility`，本地全绿而 CI 三版本全红 | 用例改从 owner 模块（`html_writer_nav`）导入；收尾前本地跑全量 `src/test` 覆盖 integration 档 |

## 已修复（0.18.3）

> 完整复盘见 `changelog.md` 0.18.3 段；此处为台账原表搬运（无损），本批发布日 2026-11-17。

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1154** | 「自查发现问题先登记台账」纪律只有人工执行，无机器兜底：本轮 0.18.2 周期把 10 项修复直接改完、台账零条目，直到 `release.py gate` 的归档前置断言才暴露，返工补录整批 rf 行 | `check-doc-drift` 新增第 29 项「自审修复须先登记」：本周期 changelog 出现「自审/自查/整改/审计/核对」类条目而台账「开发期已修复」表零 rf 行时报 finding（只判零条这一确定形态），配 3 条用例；另修台账头部编号源陈旧值（「已用最大 rf-1135」→ 实际值） |
| **rf-1157** | `report/_html_render_context._prepare_render_context` 有 30 个关键字入参，新增派生量须同时改定义、调用点、上下文字段三处，位置对错只能靠阅读 | 入参按来源域收为两组 dataclass（`_VisibilityInputs` 21 字段 / `_DataSourceInputs` 9 字段）+ `details`，签名 30 → 3；`_build_data_source_bundle` 同收为单组入参；`write_html_report` 调用点改按域构造；配「可见性域按位序 + 关键字透传」用例（11 条全绿） |
| **rf-1155** | 近 83 小时内新增/改动的静默降级处无任何日志痕迹（`report/decision_book.py` 两处、`llm/session.py` 两处、`report/_html_render_context.py` 因子名回退、`providers/utils.py`、`providers/eastmoney_industry.py`）——降级语义对，但线上出问题无法从日志定位到具体环节 | 逐处补 `logger.debug(..., exc_info=True)`（降级行为与返回值一字不改）；`decision_book.py` 另建模块 logger（原本无 `logging` 导入） |
| **rf-1156** | `report/_html_render_context.py`（渲染前置装配抽取）无任何直测文件——装配契约（哪三个视图槽位、四元组位序、因子名降级）只能从 `write_html_report` 的用例间间接推断，改装配即无人拦截 | 新增 `src/test/unit/report/test_html_render_context.py`：三层装配各一组阶段契约用例（面板视图缺席→`None` 且槽位互不牵连 / 数据源四元组位序与转发入参 / 上下文四类派生量装齐 + `details` 优先于 `holdings` + 因子名导入失败降级升 debug） |

## 已修复（0.18.4）

> 完整复盘见 `changelog.md` 0.18.4 段；此处为台账原表搬运（无损），本批发布日 2026-11-18。

| **rf-1159** | `config/_json_patch._replace_value_block` 的括号平衡扫描不跳过字符串与注释——数组/对象成员里含 `]` 或 `}`（如标题、正则、模板片段）时区块被提前截断，写出非法 JSON（`_find_value_end` 早已正确处理这类形态，两处口径不一致） | 改为复用 `_find_value_end`（注释/字符串感知），`end-1` 必须是目标闭括号否则原样返回；配 `test_array_with_bracket_in_string_replaced_intact` 与 `_find_value_end` 两条例外用例 |
| **rf-1160** | `config/_json_patch._find_top_level_value_span` 对每个字符串片段直接 `json.loads`，人工改坏的转义（如 `"a"b"`）会抛 `JSONDecodeError` 中断整个 patch——配置损坏时不是降级找键，而是崩在写回路径 | 片段解析失败视为「不是目标键」继续扫描（`try/except ValueError`），失败仍返回 `None`→调用方走「找不到键」语义；配合法转义键与损坏转义两条用例 |
| **rf-1161** | `config/_json_patch` 两处版式假设过强：① `_remove_top_level_key` 对单行（压缩）对象 `entry_start` 回退到 0，删掉整行对象只剩 `}`；② `_patch_config_key` 追加键时硬编码 LF，CRLF 文件变成混行尾 | ① 无行结构时按「上一个分隔符之后」截取条目；② 换行符沿用文件现有风格（有 `\r\n` 则用 `\r\n`）；尾逗号清理抽成 `_drop_trailing_member_comma` 供两路共用 |
| **rf-1162** | 守护命中台账（本版新增）只追加不设上限——每次守护运行写一行，单日实测已 121 行/18KB，长期会膨胀到几十 MB 且拖慢读取 | `record_guard_run` 追加前按体积上限（4MB）截断为最近 5000 行（临时文件 + `os.replace` 原子替换，失败静默同写入口径）；配「超限截断 / 未超限只追加」两用例 |
| **rf-1163** | `core/decision_ledger.py` 与 `core/signal_ledger.py` 各自复制 `is_active()`（4 行）与 `_now_iso()`（1 行）——同名同体，改「开关收敛方式」或「时间戳精度」要动两处，漏一处就静默漂移（一个账本按秒、另一个按微秒） | 新增 `core/ledger_common.py`（`feature_active(flag)` + `now_iso()` 秒级 ISO），两个账本的 `is_active` / `_now_iso` 改为薄封装并保留原名（导入面与既有 patch 点不变）；配 `test_ledger_common.py` 8 条（委托判定 / 秒级格式 / 单调不降 / 两账本薄封装同口径） |
| **rf-1164** | 4 处用例命名与断言语义不精确：`test_low` / `test_no` / `test_etf` / `test_esc` —— 名字只说输入的一半（low / no / etf / esc），不表达「期望结果是什么」，跨文件检索时无法判断该用例守的是哪条语义 | 改为「输入 + 期望」双段式：`test_low_percentile_tier` / `test_env_no_returns_false` / `test_pure_etf_hint_is_index` / `test_esc_maps_to_key_esc`；同批核对 22 组「常量归一后同体」用例，确认属按 provider/契约并行的覆盖（各自 mock 与固件不同），保留不合并 |
| **rf-1165** | 两处模块级循环 import：`core/doctor ↔ core/doctor_logs`（后者反向取 `GROUP_*`/`_item`）、`llm/api ↔ llm/_api_*`（子模块反向取默认模型与 Extended Thinking 装配）——靠「先定义、末尾延迟 import」勉强可用，改一行定义位置即 ImportError，且依赖方向读不出来 | 共用面下沉基座：新增 `core/doctor_common.py`（分组常量 + `_item`），provider 默认模型与 `_resolve_thinking_budget` / `configure_extended_thinking` 迁入 `llm/api_base.py`（门面与子模块双向取用改为单向）；依赖图机检 `test_module_graph.py`（顶层 import 无环 + 基座不反向依赖）落地，当前环数 0 |
| **rf-1166** | 锚点语料（阈值校准数据）四项治理缺口：① 测试未隔离 `data/calibration/`，采集默认开 → 测试标题写进真实分片；② 校准工具把**三个规则时代**的样本混算（当前指纹仅占约三分之二）；③ 30 天保留期只在压缩触发时生效，近三成行超期；④ 规则名 `cross_*` 被同源对复用，记录无处表达源关系 | ① `_path_isolation` 重定向锚点基路径 + 隔离断言用例；② 校准工具按指纹只把当前时代样本纳入判定分布（旧样本仅计数对照），补 `test_analyze_only_buckets_current_era`；③ 清理残留行并按保留期压缩一次（87,540 → 66,847 行，3.5 → 2.6 MB，原分片留 `.bak`）；④ 锚点记录新增 `same_source` 字段（旧记录按源名反推，向后兼容），校准侧优先采用记录值 |

## 已修复（0.18.5）


> 完整复盘见 `changelog.md` 0.18.5 段；此处为台账原表搬运（无损），本批发布日 2026-11-18。

| **rf-1167** | `prepare` 的 plan 归档只认「完成标记」标题，而本周期 9 个已完成节写成 `` `plan-N` 标题 `` 无标记 → **静默漏档**：既不进 `archived_plan.*`、也不报错，靠发布时人工复核才捞出（否则这批完成项永久留在主台账） | 归档前兜底：新增 `unmarked_completed_plan_sections()`，`apply_plan_archive` 发现缺标记即抛 `ReleaseError` 并点名 `plan-N` + 给出可照抄写法；配 3 条用例（只报未标记 / 报错点名 / 全标记正常归档）；`developer-guide` 发布流程首段写明该硬约束 |
| **rf-1168** | 截断重试丢首次调用用量：`_handle_truncation` 返回重试那次 `usage`，覆盖了被截断那次真实花费（截断模块可低估近 2 倍）；重试失败时 `return result, None` 连首次用量一并丢 → 成本台账少算 | 新增 `_merge_usage()`（按 key 递归累加，缺失一侧取另一侧），重试成功/失败均返回两次合计；配 2 条用例（合并求和且不改写首次对象 / 重试失败仍留首次用量） |
| **rf-1169** | 性能门禁只卡 basic（Phase 1 Excel 一段），而实际使用最多的是 full 档（数据准备+新闻+穿透+双输出）——full 退化（数据准备中位 24s → 尾部 40s）无任何门槛拦截 | `test-perf-report.py` 新增 Phase 4（full 全链路，LLM 已 mock、其余离线桩同源）；`_perf_report/report.py` 增 `_TARGET_FULL_SECONDS`（300s，待 CI 基线收紧）与报告行/结论段；`--gate` 改为双口径任一超标即退出 2 |
| **rf-1170** | `llm_settings.json` 里 `max_tokens_*` 低于本版出厂默认时静默生效（实例：`max_tokens_self_review=2048` vs 默认 8192）——满编持仓必然触顶，触顶会**自动放大重生成一次 = 多一次计费调用**，用户在报告里只看到 WARNING，根因无从追溯 | `_validation_llm` 新增 `_below_default_advisory()`：加载期点名「当前值 / 本版默认 / 代价」，合法值不回落不改写；配 2 条用例（低于默认保留原值并出提示 / ≥默认不产生提示噪声） |
| **rf-1171** | 多处 `except Exception` 无任何日志的静默降级：`core/concurrency.py` 配置读失败 → 并发档位静默变 high；`core/data_freshness.py` 交易日历/阈值回落无痕；`report/_report_factor_metrics.py` 单品种 K 线失败与「真无数据」不可区分 | 逐处补日志（并发档位回落用 WARNING + exc_info，其余用 DEBUG + exc_info）；其余仅探针性质（doctor 健康检查等把失败当结果返回）不动 |
| **rf-1172** | 持仓文件缺失只报「文件不存在（路径: X）」：目录本身不存在（旧机器/旧版本配置残留，本机曾实测指向一个已不存在的路径）与「目录在、文件名对不上」两种情形修法完全不同（改 `holdings_dir` 还是改 `holdings_filename`），原提示两者都说，用户会在错误的配置键上来回试 | 新增 `_missing_holdings_hint()` 分三种情形给可执行修法（目录不存在 → 点名 `holdings_dir` 且提示旧配置残留；目录在 → 列出该目录现有 xlsx 并点名 `holdings_filename`；空目录 → 提示放文件）；配 3 条用例 |
| **rf-1173** | `test-perf-report.py`（及真实报告）本机必崩/挂死：`Segmentation fault`（退出 139）与退出期死锁。`-X faulthandler` 原栈先指向 akshare 财务指标链，实为**栈顶 `py_mini_racer.MiniRacer.__del__` → `dll.mr_free_context`**；`git stash` 后在 `HEAD` 上同样复现。逐层定位出三种崩法（两条线程先后 init V8 / 上下文跨线程 GC / 上下文活到退出期）——都是原生崩溃，`try/except` 与 pytest 一律拦不住；且实测**主进程内无论专用线程、全局锁、就地回收都留活口**（异常栈帧与第三方内部引用会把上下文留到下一次 GC） | 改为**子进程隔离**：新增 `core/v8_subprocess.py`（白名单接口 + JSON 契约 + 超时杀子进程 + 离线开关），`tool_trade_date_hist_sina`（交易日历）与 `stock_fund_flow_industry`（同花顺资金流备用通道）改走子进程，主进程只收 records；配 12 条用例（白名单/JSON 契约/子进程错误与超时降级/日历与资金流接线/主进程禁直调契约）与离线契约（基准与测试都把「子进程也离线」传下去，防止测试偷偷走真实网络）；基准连续两轮退出码 0 |
| **rf-1174** | 近 213 小时变更审计：5 个超长函数到「改一处要通读全文」的程度（`write_html_report` 349 / `generate_debate_procon` 311 / `_generate_report_full` 303 / `_write_decision_basis_block` 275 / `prepare_report_data` 270 行） | 全部按阶段拆分，入口只留编排：`write_html_report` 349→185（`_prepare_page_state` + `_build_template_context`）；`prepare_report_data` 270→176（8 段数据准备各自成函数，perf span 与调用序不变）；`_generate_report_full` 303→191（数据准备/快照注入/峰值重建/LLM 后处理各自成阶段函数）；`generate_debate_procon` 311→233（白脸黑脸收敛到 `_run_debate_side` 消掉两份逐字重复、配置解析与综合段各自成函数、删掉随之失效的会话缓存闭包）；`_write_decision_basis_block` 275→41（信号/风险预算/纪律/结算四子节各自成函数）。三处按源码位置/条数断言的测试改为结构性定位（装配点动态查找、挂载点按主编排调用序展开、缓存键按「是否用共享常量」判定），使重构搬动函数时守卫仍成立 |
| **rf-1175** | 近 213 小时变更审计发现两处结构性重复（同一套口径写了两份，改一处漏一处即口径分叉）：① `fetcher/fund.py` 的 `fetch_fund_rankings_cached` / `fetch_fund_holdings_cached` 是同一会话缓存包装的两份拷贝；② `core/perf.py` 的 `load_health_history` / `load_history` 是同一 JSONL 台账读取的两份拷贝 | ① 抽出 `_session_cached(namespace, code, fetch)`，两处各留一行调用（`NOT_FOUND` 命中语义与 `source="api"` 来源标注集中在一处）；② 抽出 `_load_jsonl_records(path, label)`（不存在→空 / `OSError` 不上抛 / 坏行 WARNING 三口径单源），两条台账共用。既有 fund/perf 用例全绿（2490 条） |
| **rf-1176** | 近 125 小时变更审计（88 提交）：三处新函数用 `-> Any` 掩盖真实返回类型（`_prepare_page_state` 实为 `_RenderContext`、`_emit_full_reports` 实为 `ReportResult`、`_fetch_sector_flow` 实为 `list[dict] \| None`），类型检查因此对这三处的使用方全盲；辩论三段（白脸/黑脸/综合）参数表膨胀到 21/16 项、会话缓存读写同一段代码抄了三遍 | ① 三处标注真实返回类型（`_RenderContext` 直接导入，`ReportResult` 走 TYPE_CHECKING 前向引用）；② 引入 `_DebateCall`（模型/附录块/持仓口径/幻觉白名单/会话缓存一张表），三段签名降到「上下文 + 各自差异项」，附录块从三处签名里消失；③ 会话缓存读写收敛为 `_session_get` / `_session_put`。其余核对项无需改动：无可变默认参数、无 `except: pass`、无 TODO/FIXME、结构重复仅 1 组 5 行（薄包装属合理）、25 处新增 `print` 均在 TUI 进度与脚本/子进程输出侧；judge 用例全绿 |
| **rf-1177** | 全仓架构约束与设计契约核查：5 处代码注释把开关门禁指向**已不存在或已合并的功能开关**（`industry_beta` / `financial_report_digest` / `financial_indicator`——三者已分别并入 `factor_catalog` / `stock_fundamentals`），注释与环境实际判据相反，排障会改错开关（违背功能开关注册表唯一事实来源）；`data/config/features.json` 残留无消费者的 `industry_beta` 键（每次 `check-doc-drift` 都报未登记开关）；`action_section.html` 决策书标题/列表用 2px/6px **间距阶外值**（DESIGN.md 禁新增阶外值） | ① 五处注释改为真实门禁开关（`factor_catalog` / `stock_fundamentals`），并补「基金深度分析关闭时同样返回 None」；② 删除 `features.json` 中无消费者的 `industry_beta` 键（已按「未登记键不生效」静默失效）；③ 间距改 8/4 与 4/8，`check-style-guardrails` 阶外值由 1 降为 0；④ `technical.md` 渲染期全局禁令的例外补记「由章节注册表现场派生的静态常量 `section_names`」（与 §4.4「单次会话不变的数据不受此限」对齐） |

## 已修复（0.18.6）

> 完整复盘见 `changelog.md` 0.18.6 段；此处为台账原表搬运（无损），本批发布日 2026-11-19。

| **rf-1178** | `release.py archive` 对同一版本不幂等、且只搬节内**首个**表格块：主台账表格被空行/散文切块后，每轮 `archive` 只搬首块并在归档追加一个 `## 已修复（X.Y.Z）`，余行既滞留主台账、又因 `count_rf_rows` 只看首块被门禁误判「已搬空」；实测 v0.18.5 发布时归档长出两个同名批次节，被 `check-doc-traces`（重复标题）拦下 | ① `apply_rf_archive` 改为节内**逐块全搬**（`_table_blocks` 枚举全部 `|` 块，首块连表头、后续块只取数据行），表外散文按原序留主台账；② `count_rf_rows` 改按节内全量清点（门禁据实测判定）；③ 新增 `_merge_rf_into_archive`：归档已有本版批次节时按 rf 编号去重升序**并入同一节**（同版只留一个批次节）；④ 配 2 条回归用例（多块一次搬全并留散文 / 既有批次节并入且二次运行零改动） |
| **rf-1179** | GitHub CI 三条 job 红：① akshare 1.20.65（CI 依赖解析落点）**就地重命名了四个导出接口**且不留别名（`tool_trade_date_hist_sina`→`calendar_trade_date_hist_sina`、`stock_fund_flow_industry`→`stock_fund_flow_industry_ths`、`news_cctv`→`alternative_news_cctv`、`stock_sector_fund_flow_rank`→`stock_fund_flow_sector_rank_em`），依赖声明是区间 `>=1.16,<2.0` → 新装机器上交易日历/行业资金流/央视新闻三条链路 `AttributeError` 被降级吞掉、数据静默缺失，本机 1.20.42 因旧名仍在而全程未暴露；② `test_v8_call_sites` 的「已知 V8 接口」断言写死旧名，在 CI 假红；③ `ruff format --check` 有 14 个文件早已漂移（CI `format` job 长期红） | ① 新增 `core/akshare_compat.py`（逻辑名→候选链，`resolve()` 取第一个存在的接口；旧名与改名后名字并存时优先走旧名，行为不变），`core/v8_subprocess.py` 子进程按候选链解析、`providers/akshare_news.py`/`providers/akshare_extras.py` 改走 `resolve()`；② 该断言改为按候选链整条判定，另加「合成模块」确定性用例（判定不依赖 akshare 当前实现）；③ 新增 `test_akshare_compat.py`（10 例：候选链/旧名优先/改名回落/不可调用跳过/调用点不得硬引旧名）；④ 14 个漂移文件 `ruff format` 归位，全仓 `format --check` 恢复零告警 |
| **rf-1180** | 全仓核查「旧结构兼容」残留（旧数据结构/旧数据文件/旧缓存结构/旧缓存文件/旧配置/旧配置项/旧内部 API）：运行期仍有三处为旧形态留分支——① `fetcher/index.py` 的 `history_index` 会话缓存对裸列表（旧条目形态）按「窗口未知」放行；② `providers/akshare_extras.py` 的通道失败负缓存把整源单字符串当作「全通道同源失败」；③ `report/_snapshot.capture_snapshot` 的 `**extra` 是无调用方的扩展透传口。其余「兼容」注释均为第三方变体容错（§9.2 形状容错归属）或单据版本拒载护栏，不属跳版本兼容 | ① 会话缓存只认 `(days, bars)` 二元组，其它形态一律当未命中重新取数（写回形态固定）；② 负缓存只认 `{通道: 失败类型}`，非 dict 载荷按空处理；③ 删 `**extra` 与 `pipeline_data.update(extra)`；④ 配 4 条回归用例（裸列表当未命中并回写二元组 / 窗口不足重取 / 窗口足够复用 / 单字符串负缓存按空） |
| **rf-1181** | 近 8 小时变更审计（14 提交）：① `scripts/_release/_ledger_archive.py` 的 `split_section_table` / `extract_rf_table` 在迁档改为「逐块全搬」后已无生产调用方，只剩 3 条用例引用——死生产码靠测试续命，且用例断言的是内部辅助而非真实产出；② `core/akshare_compat.resolve` 的 `# type: ignore[no-any-return]` 在该返回注解下并不触发，属新增噪音；③ `core/v8_subprocess.py` 模块 docstring 把两个 V8 接口写成具体名，未标「逻辑名，实际名经候选链解析」，与同文件的 `_ALLOWED_FUNCTIONS` 注释口径不一 | ① 删除两个死辅助与 `release.py` 的再导出，3 条用例改写为断言 `apply_rf_archive` 的真实产出（表头/分隔行/非 rf 行随块搬入归档、占位台账零改动）；② 去掉多余的 `type: ignore`（类型检查仍零错）；③ docstring 补「逻辑名 + 候选链解析」口径 |
| **rf-1182** | `test_cache_core.py` 的等值断言依赖缓存目录里的**实际文件条数**：`os.remove` 用固定长度 `side_effect=[OSError, None]`，并行档下目录里 `price_` 文件多于 2 个时第三次调用抛 `StopIteration`（本轮 dev-verify 即因此单点假红，单跑必过）；同文件另有三处 `len(os.listdir(...)) == 5` / `count == 2` 绝对值断言，属同类脆弱写法 | `os.remove` 改函数式 side_effect（首个失败、其余成功，不看文件数）；计数断言改为由前置清单派生（`count == len(expected)` / 前后条数不变 / `count == len(attempts)-1` 且 `len(attempts) >= 2`）——断言结构关系而非绝对值 |
| **rf-1183** | `src/test/conftest.py` 单文件 1199 行（顶到测试域 1200 行红线），且内容跨五类互不相关的职责——敏感路径隔离、33 个模块状态自动复位、cassette 回放、外网阻断、收集期校验混在一处，新增任一域都要在千行文件里定位。 | 按域拆为 `src/test/_conftest_{isolation,state_reset,cassette,network,hooks}.py`，入口只留标记注册与会话级兜底、把夹具/钩子显式 import 回来注册（pytest 只认入口命名空间，故 import 不可删）；`test_module_state_reset.py` 的复位接线判据改按 `conftest.py` + `_conftest_*.py` 全量汇总（glob 派生，新增实现模块自动纳入）；conftest.py 1199 → 176 行 |
| **rf-1184** | 近 6 小时变更审计（13 提交）：conftest 拆分后 `src/test` 内的兄弟模块导入在编辑器/LSP 侧持续报「Import 无法解析」——`[tool.pyright]` 的 `exclude` 只把测试域移出受检程序，不静默打开文件时的解析诊断，每次改动都会在测试域刷出 5~7 条假红（命令行 pyright 与 `check-types.py` 均为 0 错）。其余核对无新增债务：窗口内无死私有函数（全仓 0）、无近重复函数（5 组同形对均为不同输入/不同 SUT 的并行覆盖）、拆分前后 conftest 的 53 个顶层函数零丢失零重复 | `pyproject.toml [tool.pyright]` 增 `ignore = ["src/test"]`（只静默诊断、不改受检域），并在 `scripts/check-types.py` 文档与 developer-guide 类型检查行同步说明该键的作用与边界 |
| **rf-1185** | 实测报告（128.8s/11 持仓）日志分析出两处浪费：① 财报摘要 25.1s（数据准备 55%）里，`_locate_from_fulltext` 在全文**无任一偏好关键词**时退化为 `content[:max_chars]`（封面/目录/公司简介）——既把无关文本当摘要展示，又因「有正文」绕过 `SYMBOL_MISS` 负缓存，下一轮继续逐篇白探；② `portfolio_history` 把 `00` 前缀但名称不含基金关键词的场外基金（实测 `005827 易方达蓝筹精选`）按 A 股派给 K 线链，必空后才降级净值链，同一轮多处消费该代码即重复白试（每次 0.4~2s） | ① 全文阶只认关键词命中，无命中即返回空并落 DEBUG 说明，使该标的走「确定性缺失」负缓存；② 实例内记忆「已确认只能走净值链路」的代码集合，后续调用直接走净值链（首次仍保留既有优先序）；③ 配 2 条回归用例（无关键词全文判缺失 / 二次调用只走净值链），并同步 `technical.md` 的两阶取数口径 |
| **rf-1186** | 近 35 小时变更审计（40 提交）：`compute_valuation_data` 的并发 futures 循环 `except Exception: _val = None` 把单只标的的估值取数异常静默吞掉——报告里只是少一行，排障时与「该标的本来无估值」不可区分（与 rf-1171 已修的逐品种 K 线同一类）：窗口内 105 个改动 py 文件逐项扫过，其余维度未见债务（全仓无引用私有函数 0、无新近重复函数、无未测新模块、新公开函数无死引用） | 异常分支补一行 WARNING（点名代码 + `exc_info`）再按无估值剔除；配 1 条回归用例（一只异常、另一只照常计入，且日志点名异常代码） |
