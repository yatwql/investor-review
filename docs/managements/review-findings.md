# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.4-dev
> **编号源**：`rf-next = 1065`（新增问题提出后更新为 +1；已用最大 rf-1064，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

**盘点口径**：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」，结论是**七类均无兼容面**，因此下面没有条目：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属第三方变体（见 rf-1033 边界）。

> 下次盘点时：只有「旧版本产物能让当前版本**行为不正确**」才算本类待办；仅仅是「旧文件还能读」不列入。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1155 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 905 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 830 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 852 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 855 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 729 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.4-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

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

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-06）
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
