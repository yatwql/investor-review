# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.12.10]**（2026-10-11）——已发布版本段随发布移入 [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.12.11-dev] - 开发中（未发布）

### Added
- **实验功能批量转正 + 辩论开关归组（面板重排）**：`factor_catalog`（因子目录，评测三指标过审）与 `rebalance_schedule_replay`（调仓纪律回放，先决门槛三段全过）自实验组转正入「报告章节与增强」组，`llm_debate_procon`（正反辩论，三段式换调用次数）同步转正；三者均追加在报告块**块首**、默认保持关（零行为变化，产物自述随转正退出）。`llm_debate_conditional`（条件推理）自常规组挪入报告组、与正反辩论相邻（**默认开不变**，情景段仍在既有调用内产出），辩论开关同组可查。[S] 面板编号重排：实验 8（仅 `decision_reflection`，2026-10-15 前后按死线终判）/ 常规 9-17 / 报告 18-37（既有报告项 22-37 编号不位移）；辩论模式标签去实验化（`🧪 辩论模式`→`辩论模式`、`🧪 实验模式`→`情景推理模式`），`--experiment` 令牌域随之缩为仅决策反思（转正项改用 `--feature NAME=on`）。Web/TUI 面板由注册表派生自动适配；同步五份手册、需求/技术/测试计划与 llm-technical 文档触点。
- **摘要区「本期要点与环比对照」（plan-91，开关 `summary_highlights`，默认关）**：「投资分析汇总」首屏基本信息表后新增执行摘要卡——关键指标环比行（总市值环比金额与比率 / 总收益率环比百分点 / 持仓数环比（新增-清仓） / 集中度 HHI 环比） + 本期关键变化 Top 5（新增/清仓/加减仓合并按市值变化绝对值降序，超上限写「等共 N 项变动」提示）；取数快照 diff 单源派生（`report/summary_highlights.py::build_summary_highlights`，纯内存零取数零计算重复），HHI 环比复用演进摘要（演进开关关闭时该行省略、整块照常）；无上期快照（首次运行/非正式持仓源）时整块隐藏不写占位；总收益率环比为新扩展字段（`DiffSummary.total_pnl_pct_diff`，快照双端已持久化 `total_pnl_pct` 自然差值）。开关置于报告组块尾（TUI 面板 37，既有项编号不位移），编排 2b4 注入 + 模板 kv/列表双态渲染；关态产物逐字节不变。
- **报告对话式追问立项评估（plan-102，设计定稿未实施）**：新增 [`docs/plan/report-followup-qa-design.md`](../plan/report-followup-qa-design.md)——功能 slug `report_qa`；独立 `src/python/qa/` 子包（报告 HTML 反解析上下文提取 + 线程安全会话服务，与 `llm/` 解耦，依赖单向）；复用 Provider Chain/合规漏斗/事实校验，回答不做缓存、用量独立记账；Web 报告页同源追问（`file://` 降级引导），开关 `report_qa` 实验组默认关；分 5 阶段实施（后端服务 → 报告页区块 → 端到端+文档 → TUI 增量 → 转正评估）每阶段含可验收标准；明确不做仓位硬建议/全市场筛选（守 v0.7 归档边界）
- **LLM 模块级强刷（plan-101）**：`force` 从全局布尔升级为按模块粒度——新增 `llm/force_scope.py`（可强刷键清单 `FORCEABLE_LLM_MODULES`：四并行模块 + 新闻关联 + 生成后自检 + 持仓变动复盘归因；`resolve_force_scope` 粒度优先归一：显式模块列表优先于 `--force-llm` 全量，未知键报错并列可选值）。三端接线：CLI `--llm-module KEY`（可重复传参，argparse choices 校验）、TUI 强制询问后追加模块多选（编号/键名子集，回车=全部）、Web 勾选强制 LLM 后展开模块多选组（全选/全不选归一为不传）。共享层 `generate_all_llm` 入口归一为模块键集合，预检 `can_cache` / worker 闭包 / 串行后置（自检/变动复盘）/ 新闻 LLM 增强均逐模块取 force——仅指定模块绕缓存，其余照常命中；沿用既有模块指纹缓存键，不改缓存键构造。
- **风险调整超额与基准对照（plan-85，开关 `risk_adjusted_excess`，默认关）**：组合历史走势与回撤章新增第五区块「风险调整超额」（Excel + HTML 双端同源）——逐基准年化 IR / 跟踪误差 / 几何年化超额 + 近 12/24 个完整月跑赢胜率 + 滚动 250 日超额序列（HTML 折线图）；IR/TE 需 ≥60 对齐交易日、滚动需 ≥250，样本不足逐项「数据不足」占位（分层降级）；未配置业绩基准整块「数据不可用：<原因>」。度量实现 `analysis/benchmark_excess.py`（纯标准库、analysis 层隔离），装配 `report/_snapshot.py::assemble_history_augmented_data`（full/both 双路径同源，防契约漂移）。
- **危机区间双层回放（plan-88，开关 `crisis_replay`，默认关）**：危机区间标注区块升级——组合层统计子块扩展窗（max(lookback, 365) 交易日）内静态危机区间的组合收益/回撤/恢复（窗外行标「组合窗口外」），指数层覆盖全部静态区间（新增 2025 关税冲击锚点；指数长窗日线按静态表最早起点动态推算天数、封顶 3650）给出指数区间收益与区间最大回撤；未配置业绩基准时指数层静默缺席、组合层照常。`CRISIS_INTERVALS` 静态清单单一来源，全端标题/说明/占位动态跟随（移除 Excel 危机注释、HTML 章标题与占位文案的硬编码年份清单）。
- 两开关共享同一次子块扩展窗取数（未开启时零新增网络请求、产物逐字节一致）；同步区块契约注册表（走势章 4→5 区块）、TUI 面板编号、开关表与附录 H。
- **品牌**：猫头鹰吉祥物「守望」上线——新增 `src/static/owl-mascot.svg`（卡通猫头鹰立于净值增长曲线，底色与 architecture.svg 同源），README 头部嵌入并补定位描述（夜间守望 / 智慧顾问不越位 / 全景视野 / 守口如命）；favicon.svg 改为品牌蓝底 + 猫头鹰头像（16px 可辨）。

### Changed
- **环比对比基线改为跨交易日 + 基线标注三面（HTML/Excel/LLM）**：同一交易日多次运行报告不再互为比对对象——`diff`（本期要点/Excel 环比块/LLM 环比上下文）与 `snapshot_diff`（组合演进「自上次快照变化摘要」）的基线统一取**上一个有报告的交易日的最新一份快照**（新增 `report/history_snapshot.load_comparison_baseline`；交易日归属经 `core/trading_calendar.trading_day_as_of`：盘前 <9:30 归前一交易日、节假日按日历回溯、日历不可用回退排除周六日，与报告头「所属交易日」同口径，`get_last_trading_day` 改为委托该函数保持单源）。`current_ts` 不可解析回退旧「上一份快照」口径不阻塞环比；基线候选文件损坏/时间戳坏自动跳过顺延；无可比基线时按首次运行口径隐藏环比块。同时 diff 契约新增 `baseline_trading_day`（基线报告所属交易日）/ `baseline_generated_at`（报告生成时间，`YYYY-MM-DD HH:MM`）/ `baseline_timestamp` 三个展示键，HTML「本期要点」标题下、Excel【环比对比】区块、LLM 环比上下文分别新增「对比基准」行——写明比对的是哪个交易日、什么时间生成的报告（标注不可解析时为空串，三处均省略该行；首跑/关态产物逐字节不变）。

### Fixed
- **favicon**：旧图标 XML 注释内含 `--` 非法 token，严格 XML 解析器下图标渲染失败——随品牌图标重绘顺带修复。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.10（2026-10-03 ~ 2026-10-11）
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
