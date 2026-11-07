# 自审记录归档 — v0.17.x

> 归档时间：2026-11-04（v0.17.0 发布，本系列首批已修复批次并入）；2026-11-04 v0.17.0 本批原表搬运；2026-11-05 v0.17.1 本批原表搬运；2026-11-05 v0.17.2 本批原表搬运；2026-11-06 v0.17.3 本批原表搬运；2026-11-08 v0.17.4 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.17.x 已修复项（按发布版号批次，v0.17.0 → ）（含 v0.17.4）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 已修复（0.17.0）

> 完整复盘见 `changelog.md` 0.17.0 段；此处为台账原表搬运（无损），本批发布日 2026-11-04。

| # | 问题 | 处置 |
| --- | --- | --- |
| **rf-1036** | 财报源挂起型超时预算偏长（单次 23~25s，7 日 26 次） | `providers/datasink.py` 预算分档：正文档 20s / 章节清单探测 8s，预算经 `_request`/`_get_with_transient_retry` 透传（+3 用例） |
| **rf-1037** | 美股指数行情无会话级复用（同键一轮记 3~4 次未命中并重复请求上游） | `fetcher/index.py` 的 `fetch_indices`/`fetch_us_indices` 增加 `index_quote` 会话缓存包装；陈旧兜底读改 `record_stats=False`，未命中只记一次（+6 用例） |
| **rf-1038** | 流水页签日期为 Excel 原生日期单元格时整行被判无效静默丢弃（`2026-11-04 00:00:00` 过不了 `_DATE_RE`，该笔卖出在 XIRR/成本分档/分红里消失） | `core/reader.py` 新增 `_coerce_flow_date`（`date`/`datetime` → `YYYY-MM-DD`，文本补零 ISO），交易/分红两处解析改用它；`_valid_date` 补日历校验（拒 `2026-13-01`/`2026-02-30`）；+5 用例 |
| **rf-1039** | 基金经理主页失败无负缓存：同一轮穿透/基金经理分析/菜单预热各调一次都重走 HTTP 并各记一次未命中（实测 `fund_manager_017730×4`） | `fetcher/fund_manager.py` 增两级 `NegativeCache`：确定性解析不出 12h（`fund_manager_miss_`）/ 不可达 1h 短退避（`fund_manager_backoff_`），命中即跳过取数且不计缓存未命中；注册表与三份文档表格同步；+4 用例 |

## 已修复（0.17.1）

> 完整复盘见 `changelog.md` 0.17.1 段；此处为台账原表搬运（无损），本批发布日 2026-11-05。

| # | 问题 | 修复 |
|---|------|------|
| **rf-1041** | both 路径把 `config` 当持仓明细传给 `build_purchase_status_data`：开启「基金申购限购」（默认开）且取数成功时，`build_purchase_constraint_block` 迭代 config 得到键名（str）→ `h.get("code")` 抛 `AttributeError`，HTML+Excel 双产物整条中断 | 改传持仓明细最小形态 `[{"name": d.name, "code": d.code} for d in details]`（与 full 路径 `_orchestrator_data.compute_purchase_status_data` 同源同形）；补回归用例锁定「传 list 而非 dict」 |
| **rf-1040** | LLM 四模块缓存 TTL 4h/24h 形同虚设：连续两轮「持仓与市值完全相同」仍 4/4 全 miss（预检归因 `fingerprint_changed`，非 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、指数、竞争语境、量化指标、风险信号、穿透市值占比）与时效数据（事件窗分歧例块、调仓纪律回放块，新闻 15 分钟刷新且含浮点）全数锁进键 | 指纹改为「**只锁结构与口径**」：入键仅持仓成本、分类结构（`extract_stable_categories`，无市值/盈亏）、穿透品种集与行业、版本盐、生成参数、口径类附录块；行情/时效类只进提示词、时效由 TTL 兜底。`global_macro` 另按 `_APPENDIX_EXCLUDED_SECTIONS` 不注入事件窗分歧例块（口径不符 + 省 token），自检/辩论键同步剔除时效块。同步改 requirements（R-HCR-05/R-SR-04/R-EW-06）、technical §3.4 分界说明与七份单测（含新增 `test_market_derived_inputs_do_not_change_fingerprint` / `test_structural_inputs_change_fingerprint`） |

## 已修复（0.17.2）

> 完整复盘见 `changelog.md` 0.17.2 段；此处为台账原表搬运（无损），本批发布日 2026-11-05。

| # | 问题 | 修复 |
| --- | --- | --- |
| **rf-1051** | `providers/tiantian_nav._parse_nav_trend` 按 `timezone.utc` 解 `Data_netWorthTrend[].x`（实为当日 00:00 UTC+8 的毫秒数），整条历史净值日期前移一天：录入「按交易日取净值」永远取不到 T 日、把 T-1 的值当成 T-1（实测 240012 卖出提示「2026-11-05 无净值」而缓存刷新标 11-05，两条路径矛盾） | 改按 `BEIJING_TZ` 解析（与 `tiantian_ranking`、`providers/utils.ts_to_str` 同口径）；已缓存历史按 provider 全量返回的替换分支自动更正。补 3 例单测（北京时间解毫秒戳、整数 YYYYMMDD 不受影响、相邻时间戳→相邻日期） |
| **rf-1050** | 分市场取价口径判定用明细自带的 `name` 识别 QDII，但场外净值接口（东财/新浪）不回名称——QDII 全部被判成「国内场外」，`price_update_status` 因此要求 T 日净值，把正常的 T-1 官方净值误报为未更新（实测 4/4 全误报） | `_market_breakdown_after_refresh` 构造明细行时名称以持仓名为准、取数名仅作兜底；补 2 例单测（无名称时 QDII T-1 计最新、国内场外 T-1 仍计未更新） |
| **rf-1049** | 行情类缓存刷新后的新鲜度判定直接吃取数层明细，而取数层日期字段是 `price_date`、报告侧 `DetailRow` 才映射为 `nav_date`——判据读不到日期，把全部品种报成「过期」并显示「无净值日期」（实测 12/12 全误报，含收市价齐全的 A 股） | `_judge_after_refresh` 先给明细补 `nav_date` 别名（`price_date` → `nav_date`）再交同一判据；TUI 侧日期回退链同步接受 `price_date`。补 2 例单测（别名后判为实时、过期行给出净值日与落后天数） |
| **rf-1048** | TUI 持仓录入的卖出第一步口径读不出：面板买入项说明写「份额或金额」（金额实际只在场外买入口径可选），相邻卖出项只写份额，对照读像卖出也能选金额；帧头提示只写「金额单位元」「多数提示回车取默认值」，而卖出份额那步回车是取消本笔，且不显示单位与可卖份数 | 三处同源改写：买入项说明限定「份额（场外买入可按金额）」、卖出项写明「卖出份额（份，a=全部）」，帧头提示改为「份额按份录入，金额仅场外买入可用（元）……每步回车的作用见该行提示」；`_ask_shares` 卖出提示补单位与可卖份数（`卖出份额（份，可卖 500；a=全部）`），买入仍为「买入份额（份）」。口径未变（卖出始终按份额）。补 3 例单测（卖出提示含单位与可卖、买入提示不含可卖/金额、面板说明把金额限定在场外买入） |
| **rf-1047** | 报告模板把 Jinja 写进 CSS 值位置，HTML 语言服务据此对每个模板报 28 条解析误报；此前用 `.pi-lens.json` 的 `lsp.disabledServers: [html]` 整体关掉该服务止声，代价是非模板页也失去 HTML LSP，且章节顺序分裂成「include 顺序 + CSS order 值」两处 | 按「颜色→语义 class、顺序→DOM 顺序、几何量→HTML/SVG 属性」改写：64 处动态内联样式清零（20 `order` + 40 颜色/字号/字重 + 1 配置分布条改 SVG 属性宽度），新增 `profit_class`/`price_type_class` 过滤器与 11 个工具类（色值引用既有 token）；include 顺序对齐 `_REPORT_SECTION_DEFAULT`；`.pi-lens.json` 删除、HTML LSP 恢复。守卫 3 条单测（模板静态扫描 / 渲染产物 style 无残留 / `div.section` 无 inline order 且 DOM 顺序与编号一致） |
| **rf-1046** | 走势终点由滞后净值构成（QDII T-1/T-2）时，口径差异只在日志 WARNING 与数据源状态章可见；读者在「组合历史走势与回撤」章看到的末端日收益/最大回撤仍会被当准确值 | `STATUS_MESSAGES["history_nav_stale"]` 补上口径后果（末端日收益与最大回撤会偏低、终点附近数字仅供参考）；HTML 该章首与 Excel 页签顶部各加一块「读数口径提示」（逐标的滞后交易日数与占比）；手册报告说明同步。**口径文案单一源**：标题句/后果句/明细行在 `report/_history_quality` 定常量与拼装函数，生产侧写入契约（`headline`/`consequence`/`caveat`/`assets[].detail`），Excel 与数据状态词直接取用，HTML 副本由渲染用例按同一常量逐字断言（防三处静默漂移）。补 4 例单测（HTML 正反向渲染、Excel 提示行与无滞后不写） |
| **rf-1045** | 缓存清理与读侧共用盘中 30s TTL，行情类缓存刚写入即被判过期删除，下一轮再写一遍——每轮启动与收尾反复预览 22~63 个待删文件，删除对读侧无收益，只放大未命中统计并制造「缓存反复失效」假象 | 新增 `cache/_ttl.get_cleanup_ttl(data_type, written_at)`：盘中一律按静态 TTL；**盘后**对盘中敏感类型额外回收**盘中写入**的快照（按写入时刻判定，TTL 归 0），收盘后写入的保留；读侧 `get_ttl` 不变。新增 `core/market_hours.is_intraday_timestamp()` 单一承接交易时段判定。technical 接口表与 TTL 章补「读写两侧判据不同（设计意图）」。补 4 例单测（盘中不快删、盘后回收盘中快照、盘后保留收盘快照、读侧仍判过期） |
| **rf-1044** | 「刷新基础缓存」`clear_by_group("refresh")` 清整组 19 个模块，但流程只回填其中 10 个——财报索引/正文、财务指标、市场情绪、新闻逐条分析、费率、估值、无风险利率被连坐作废，要等下一次出报告才逐只回源（实测一次刷新后紧接的报告多付 267 次请求、墙钟 134s、命中率 35%，同日前序运行均 95~99%） | `clear_by_group()` 新增 `only` 参数（按缓存前缀/精确键名限定域），`update_basic_cache` 传 `_BASIC_REFRESHED_CACHE_KEYS`（本流程真回填的 10 个域）；手册 `[1]` 段落区分「会清」与「未连带清」两清单，technical 接口表与菜单表同步。补 2 例单测（only 限定保留未列域、编排层只清回填域） |
| **rf-1043** | 批量 LLM 全批失败与「全缓存命中」同形（用量字典零值），批次级成败不回传、日志只到 WARNING——实测一次 provider 双链熔断后 3/3 批全失败、41 条新闻 0 条含分析，日志仍写「生成完成」，报告侧模块状态无从判定；全链不可用也只到 WARNING，12 天日志 0 条 ERROR | `_execute_and_merge_batch` 回传本批解析条数，`run_batch_mode` 聚合 `ok_batches`/`failed_batches`/`total_batches` 入用量字典并分级留痕（全失败 ERROR、部分失败 WARNING）；`_finalize_news_token_usage` 按批次成败区分「完成」与「全部批次失败」并显式声明该模块将标为失败；`api.py` 全 provider 失败升 ERROR 并带已尝试链。补 3 例单测（全失败零 ok 批、有产出零失败批、全失败不落模块用量行） |
| **rf-1042** | 事件窗行降级主因是「映射交易日不在行情轴」——索引扩面后能匹配到更多新闻，但行情取数窗口写死 365 天，事件日更早的新闻整条降级（实测一轮 23 条降级中占 19 条） | 新增 `history_days_for()` 按**最早事件日**推导窗口（回看天数 + 后窗余量 + 30 天缓冲，夹在 [365, 1095] 内），默认股票与基准取数器改用该窗口，短窗新闻仍按 365 不额外拉数；补 3 例单测锁定基线/放大/夹上限与默认取数器请求值。同时修另一半成因：事件日晚于行情轴末日（当日 K 线未落地）时原本整条降级，改为按末日对齐并标注（`anchor_shifted`/`align_note` + 视图计数行），实测一轮降级 23→4、可出行 36→50（触 50 行上限 capped 4） |

## 已修复（0.17.3）

> 完整复盘见 `changelog.md` 0.17.3 段；此处为台账原表搬运（无损），本批发布日 2026-11-06。

| # | 问题 | 修复 |
|---|------|------|
| **rf-1054** | 缓存 TTL 业务矩阵用例用 `now.replace(hour=8/10)` 构造时间戳：跑在 00:00–08:00 时戳落在**未来**，年龄为负，「超过静态 TTL 必须回收」「盘中快照盘后回收」两类断言失真——实测 01:01 跑出 14 例假失败（HEAD 上同样失败，与业务改动无关） | 抽 `_recent(hour, minute)` 取「今天该时刻的过去最近一次」，时段语义不变且与运行时刻无关；105 例全通过 |
| **rf-1053** | 基金经理主页与档案页都解析不出时，日志只有「基金经理全部解析失败 [code]」：既没说明本轮会按缺数据降级，也没给下一步方向——实测连续两天 SSL 握手超时后该章直接占位，读者无从判断是否要处理 | 告警补「本轮按缺数据降级（报告该章写占位），下次运行会自动重试；若连续多日出现，先查档案页链路是否可达（SSL/超时）」；补 1 例单测 |
| **rf-1052** | LLM 模块结果行把 provider 全挂 / 开关关闭 / 预算跳过三种情况都打成同一条 `INFO 生成失败（跳过）`；`llm/skeleton.py` 的失败行只有缓存键、无模块与原因——实测 11-03 四模块全跳过，事后要翻十几行 WARNING 才能复原 | 新增 `_log_module_outcome()`：成功 / 关开关 / 预算跳过走 INFO，其余 ERROR + 可读原因 + 降级后果；`skeleton` 失败行补模块名与原因；文案收敛到 `FAIL_REASON_LABELS` 单源并被报告模块状态复用。补 9 例单测 |

## 已修复（0.17.4）

> 完整复盘见 `changelog.md` 0.17.4 段；此处为台账原表搬运（无损），本批发布日 2026-11-08。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1055** | 新闻关联批量「响应不可解析」被当成功：解析器给整批填 `("低","中性","")` 占位 → 批次计 ok、占位写进逐条缓存、报告把 20/30 条占位算成「含 LLM 分析」，连带事件窗极性缺失（91% 不可判） | 解析器改为返回 `None`（LLM 部分作答仍填默认值）；批量骨架按失败收口：不写结果、不写缓存、计 `failed_batches`、已耗 token 照常计费 |
| **rf-1056** | 批量用量行恒为「输入 0 + 输出 0」：把 provider 条目名（`deepseek-main`）当协议名传给 `_log_token_usage`，claude 形 usage 落进 openai 分支读 `prompt_tokens` | 归一化协议改按 usage 形状判定（含 `input_tokens` 即 claude），与逐条调用同一口径 |
| **rf-1057** | 逐模块费用丢精度：`estimate_cost` 展示串（≥0.01 只到 3 位小数）回读成 float，0.0646 记成 0.0650，用量页签逐模块合计 ¥0.1325 ≠ 表头 ¥0.1320 | 逐模块费用改用 `compute_cost_value` 数值口径（news 批量与标准模块两处） |
| **rf-1058** | 「页面写入」段名实不符：实际含模板渲染/JS 资产内嵌/匿名化/落盘四件事，凭总值无法归因（告警还指向「排查磁盘/挂载与 fsync」） | `write_html_report` 增 `stage_recorder` 逐段记细分（并保留总值供跨版本比对）；full/both 两条路径均接线；慢告警按段分流（渲染→模板，落盘→磁盘） |
| **rf-1059** | Jinja 模板渲染被当成渲染热点：实为**模板编译**（18 个模板编译占 HTML 生成阶段绝大部分），冷缓存还要从挂载盘读 18 个文件，是该阶段耗时抖动的来源 | `html_jinja_env` 接入字节码缓存（落 `<缓存根>/jinja/`，键含模板源码校验和，改模板自动失效；目录按需解析以尊重测试隔离与 `INVEST_CACHE_DIR`），并新增回归用例 |
| **rf-1060** | 四处技术债：①`generators_news._first_provider_name` 无任何调用方；②`_render_template` 的 `self_review_block` 形参不被函数体使用（渲染时自行取值，调用方传入不生效）；③`write_html_report` 的 `force_llm` 形参无任何调用方；④HTML 阶段收口（总值记录 + 慢段告警）在 full/both 两条路径各写一份，两处口径不一致（both 侧无慢段告警） | 删除死函数/死形参并同步收敛调用点；收口逻辑抽到 `html_writer.close_html_generation_stage` 单源共用 |
| **rf-1061** | `excel_writer.mask_workbook_text` 遍历 `ws.iter_rows()` 时未跳过 `MergedCell`：被合并吞掉的从属单元格 `value` 只读，清扫命中一处带笔名的合并行即抛 `AttributeError`，整份报告生成失败（匿名化 full 模式 + 含合并单元格页签的组合必现） | 清扫前 `isinstance(cell, MergedCell)` 跳过从属单元格（锚点本身会被遍历到，不漏清扫）；新增合并区域回归用例 |
| **rf-1062** | 六处同构副本散在不同模块，改一处另一处易漏（口径漂移）：①`atomic_write` 文本/二进制写入本体逐字重复；②`excel_writer` 小计/总计行仅底色不同；③`text_layout` 终端列/行探测同构；④`_json_patch` dict/array 区块括号平衡替换同构；⑤`_report_helpers` 组合演进/快照差异注入同构；⑥`providers/sina` 与 `report/summary` 的 A 股/美股指数取数与渲染同构 | 各抽一份参数化本体（`_write_atomic` / `_write_summary_row` / `_terminal_dimension` / `_replace_value_block` / `_inject_optional_section` / `_fetch_sina_indices` / `_write_index_group`），对外的公开函数签名与输出逐字不变 |
| **rf-1063** | 截图演示工作区的 `src/` 软链指向旧仓库路径时不自愈：仓库挪位置后旧链仍在，`_link_repo_src` 把「链接存在」当作就绪直接返回，报告渲染跑到废路径（`TemplateNotFound: report_template.html`），重跑 `demo` 也修不回来，只能手工删链 | 软链目标与当前 `REPO_ROOT/src` 不一致时先删链再重指（读不到目标则不动）；补「旧指向→重跑 demo→自愈」回归用例 |
| **rf-1064** | 文档与实现/文档自身不一致（机检未覆盖的部分）：①Web 手册标题写「六区」而正文写「5 个工作区」且页签表缺「持仓录入」行；②Web 手册目录把 §5 持仓录入排在 §8/§9 之后（序号乱序）；③`requirements.md` 写「24 项全部 affects_report」与「前六组在 `[S]`」，而注册表是 26 项且 `[S]` 只含五组（6+2≠7 组，与同文件另一处自相矛盾）；④定价附录缺 `claude-opus-4-6`、多出注册表已无的 `claude-sonnet-5` | 逐项对齐注册表真值：六区 + 补持仓录入行、目录按 §1~§11 重排、开关数与面板分组改正、定价表按 `MODEL_PRICING` 增删一进一出 |
