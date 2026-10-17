# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.4]**（2026-10-16）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.5-dev] - 开发中（未发布）

### Fixed

- **`unit` 标记漏注册致全量单元测试脱离一切门禁（rf-697）**：门禁档位按 `unit` 通配（`unit` 档、P2 预检）与 `unit_*` 域集（`dev-verify`/`verify`）筛选，但 conftest `pytest_configure` 从未注册裸 `unit` marker——`-m "unit"` 表达式匹配为空，10,136 条 unit 用例（含全部域）实际不在任何门禁收集范围（P0/P1 实跑 6,969/9,800 与台账吻合即实证）。补注册行后 conftest 注释同步标记体系口径；`verify` 档 9,800→10,145（含同批纳入的 TUI/CLI 域），域集同源性由 `TestP1GateCoversDeclaredDomains` 结构锁钉死。
- **scenario 门禁佩戴无硬校验（rf-696）**：全仓测试语义审计发现 scenario/regression（P2）/integration 三模式按裸 `scenario` marker 筛选，而仓内裸 marker 全靠基类/模块级隐式继承佩戴——只带子域 marker（`scenario_security` 等，不被任何选择器消费）的新场景文件会静默漏出回归门禁且连缺标记警告都不触发。conftest `pytest_collection_modifyitems` 增「scenario 目录×裸 marker」双向收集期拦截（与 edge 隔离同范式）；新增 `test_conftest_scenario_gate.py` 5 个钩子直驱回归用例。审计初判的「22 用例已漏」经 `-m scenario` 全目录收集对拍证实为静态扫描未计 MRO 继承佩戴的误报，现行门禁覆盖实际完整。
- **结构化决策头缺 `detail` 键 → LLM 建议登记整批失效（rf-693）**：结构化决策头优先路（开关 `decision_header_parse` 默认开）的产物仅 `{code, action, priority}` 三字段，而 `register_llm_decisions` 直取 `row["detail"]` → `KeyError: 'detail'`，被实验功能挂载点守护吞成一条告警（perf 运行明细「错误」计数即此），导致当批全部 LLM 操作建议不入决策账本（跨期反思闭环对这轮建议失效）。按技术设计 §4.15「两路产物形状统一」在登记纪律统一入口 `_collect_decision` 回补 `detail`（契约无理由列 → 空串；账本 `append_decision` 的 detail 缺省为空，不阻结算）；同步修正 `parse_structured_header`「与表格解析同形状」的误导 docstring；`test_decision_llm_capture.py` 新增 2 个回归用例（形状回补断言 + 登记链路缺陷场景复现）。
- **LLM 观测未写入性能记录（rf-692）**：full 路径在 LLM 阶段结束的 `finally` 中解绑全局 sink 后，收尾 `_record_llm_context(perf)` 仍取全局 → 取到 None，重试/节流等待/降级/缓存/thinking 观测整段丢失（性能台账只剩会话用量）。改为显式传入本次绑定的 sink（`_record_llm_context(perf, _llm_sink)`）；新增 2 个回归用例。

- **盘前/盘后价格缓存误用盘中价（rf-691）**：`_price_cache_fresh` 此前只比 `price_date`，把交易日 T 盘中写入的场内缓存（如 10-15 13:01 的 29.35）当作 T 日收盘价（真实 29.60）在盘后/次日盘前沿用，使「本日盈亏」与「快照环比」系统性偏离真实涨跌。现增加收盘时点校验：T 日已收盘（now ≥ 15:00）时要求缓存写入时刻 ≥ T 日 15:00（午间休市不施加），`report/market_value.py` 的 `CACHE_ONLY` 分支与 `_fetch_price_with_cache_refresh` 两处传入 `cache_key`；强制刷新失败时退回刷新前的过时缓存（不再因清缓存反而丢数据）。新增 `test_fetcher_price.py` 8 个回归用例。
- **Web 生成完成后按钮复位（rf-690）**：run 完成后「生成报告」按钮停在「生成中...」禁用态、无法再次生成或换格式再生成（rf-257 真机 basic 实测揭示）——根因是 `pollOnce` 完成分支只移除 `aria-busy`、未复位文案与禁用态、未清已消费的 `file_id`；完成分支与 `resetFlow` 共用 `restoreGenerateBtn()` 单源复位（清 `state.fileId` → `updateGenerateBtn()` → 文案还原 +「请重新上传」提示；正式-用存量免上传立即可再生成），新增 `test_web_generate_flow.py` 源结构回归 3 用例。

### Changed

- **设计契约审计与护栏观察维度增设（rf-699）**：全量 UI/报告样式人工比对 DESIGN.md + 基线对拍定位契约落稿后新增违规仅 3 行（`summary_section.html` 内联 `#888` 裸色值×2、`opacity:0.75` 档外×1），已修并顺手消同模式存量 1 行；护栏 `check-style-guardrails` 增设 W3 内联色值/W4 档外字号/W5 档外间距三维观察（W1 引号整行豁免为 JS 图表配置设计，HTML 内联色值盲区按位置级找回；存量 40/8/175 入只减不增基线并入契约 Known Gaps）；DESIGN.md 基线数字刷新（700 存量 3→9、600 25→63）；工作台旧 `--color-*` 兼容映射到期删除（零消费者，`TestLegacyMappingRemoved` 负向锁）。
- **旧配置/旧缓存/旧模型名兼容代码清理（rf-698，用户裁决口径）**：移除 5 处残留兼容分支——perf 阶段 ETA 的早期 list 形状 `phases` 死分支（旧记录已自然出 20 条采样窗）；行业缓存缺扩展字段载荷的 schema 迁移清理链（迁移窗口≤两周已过）；数据源密钥文件顶层平铺 `{"api_key": ...}` 回退（生产调用点恒传非空 section）；停用别名 `deepseek-chat`/`deepseek-reasoner` 在价目表与 Extended Thinking 三名单的全部收录（旧名历史调用费用改显 `-`、存量旧配置不再获思考安全网，已经用户确认接受）；另修正 anonymizer `profit_rate_pct`「旧键兼容」误导注释（实为现役汇总键，同步分支保留）。手册/`llm-technical.md` 价目与峰谷枚举同源刷新；测试侧别名价格锁改负向锁（锁定移除行为防回填）并删 3 个旧形状/旧载荷正测。

- **P1 门禁域范围纳入 TUI/CLI，确立「归域即进门禁」不变式（rf-694/rf-695/rf-697，`technical.md` §4.23）**：`verify`（P1）选择器增 `unit_ui`/`unit_cli`；目录归域特例（`unit/handlers`·`unit/cache`→`unit_core`、`unit/startup`→`unit_ui`）在期望表注释/conftest 缺标警告/技术设计三处同源登记；新增 `TestP1GateCoversDeclaredDomains` 双结构锁（期望表全部 unit_* 域 ∈ verify；P0 域集 ⊆ P1）防「改域=门禁搬家」回退。审计改域迁移方案废弃：`unit_ui` 入门禁后 handlers 挂 `unit_core` 与挂 `unit_ui` 门禁结果恒同，迁移改动面 ~20 处且零覆盖收益，故保留期望表已登记口径。
- **perf-view 统计分组去重（技术债）**：`_version_evolution_data` 与 `_drift_data` 各自重复实现「按（类型, 版本）分组 + 首次运行时间排序键」，`build_trend_report` 又对同一批记录重复过滤两次；抽出 `_group_by_version_type` / `_group_filtered` 共用，`_group_records` 复用之；`_compare_versions` 的 `_summary` 改用显式版本参数（原靠对象 identity 判分支）。
- **快照/取价微清理**：`capture_snapshot` 的 QDII 分项改为仅在存在环比时计算（首次运行不再为丢弃的结果调用交易日历）；`market_value` 的 `CACHE_ONLY` 分支复用已算好的缓存键，避免同一键重复计算两次。

- **环比 QDII 口径可见（R-OUT-15 增强）**：QDII 官方净值滞后一个交易日，其市值差实际是上一交易日的净值变动，与当日 A 股涨跌混在同一个「总市值环比」里易被误读（用户实测：本日盈亏 −808.44 与环比 −530.73 差额中 +557.29 来自 QDII 口径差）。摘要区「本期要点」总市值环比行下新增 QDII 口径注：显示环比含有的 QDII 官方净值变动金额，滞后一日时标注「T-1 口径，滞后一个交易日」；无 QDII 或变动为 0 时省略。`_snapshot.capture_snapshot` 经 `_classify_qdii_value_diff` 注入 `qdii_value_diff`/`qdii_lagged`，`summary_highlights` 透传，`summary_section.html` 渲染；新增 `test_summary_highlights.py` 6 个回归用例。
- **发布流程分层纪律补充（rf-689）**：developer-guide 发布流程段增加「归档迁移/管理文档改动后、进 `gate` 前必跑便宜守护（`check-doc-traces` 等）」——守护发现前置，防止 P2 门禁因文档级 finding 双跑全量 regression（v0.13.4 发布时实际发生一次：管理文档引用归档路径触发 ARCHIVE 痕迹拦截，gate 第二轮才过）。
- **报告浏览器验证六项收口（rf-113）**：Iter 7 全链路浏览器人工验证全部完成并移入已解决——自动化回归（headless Chrome 148 一键复跑 `node docs/tmp/rf113/run-rf113.mjs`：① 6 图 badge、② afterprint 快照恢复、③ 断网渲染、⑤ 375px 报告+调试页、⑥ 禁 Canvas 兜底，5 PASS + ⑥ 已知表现记录口径）+ 人工抽验（真实 `Ctrl+P` 打印预览 2x/浅色/不跨页、微信 X5 file:// 表格兜底 + 横竖屏、iPad Safari 90+ 抽验、Windows Chrome/Firefox）；附带发现两处已由 rf-645 修复并复跑确认（⑤-testchart 转 PASS）。方法与结论见 `docs/plan/report-browser-verification.md`，勾选清单归档 `docs/archive/v0.9.x/chartjs-upgrade/iter7-verification-checklist.md`；rf-114 前置解锁


## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.4（2026-10-13 ~ 2026-10-16）
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
