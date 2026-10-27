# 配置字段详解

本文件是 [配置指南](how-to-config.md) 的逐节详解：**每个配置项是什么意思、取值如何判定、写到哪个文件**。只想改值的话看主篇的[字段说明总表](how-to-config.md#字段说明)即可；这里查“这项到底管什么”“边界怎么算”。

## 目录

[A. 路径与文件](#a-路径与文件) · [B. 报告章节可见性](#b-报告章节可见性) · [C. 数据源与提供商](#c-数据源与提供商) · [E. 行为调优](#e-行为调优) · [F. 业绩基准与无风险利率](#f-业绩基准与无风险利率) · [G. 组合历史走势与持仓快照](#g-组合历史走势与持仓快照) · [H. 业绩评价配置](#h-业绩评价配置) · [I. 再平衡配置](#i-再平衡配置) · [J. 交易纪律配置](#j-交易纪律配置) · [K. 流动性配置](#k-流动性配置) · [L. 匿名化配置](#l-匿名化配置) · [M. 批量并行调度](#m-批量并行调度) · [O. 缓存分组](#o-缓存分组) · [P. 机器本地状态（非 config.json）](#p-机器本地状态非-configjson) · [Q. Web 模式配置编辑](#q-web-模式配置编辑) · [R. 任务完成通知（notify）](#r-任务完成通知notify) · [S. 日志配置（logger.json）](#s-日志配置loggerjson) · [与菜单命令的对应关系](#与菜单命令的对应关系)

## A. 路径与文件

> **`data/config/` 的 8 个文件**：`config.json`（本文件主文档）、`features.json`（功能开关覆写，见 [§N](how-to-config.md#n-功能开关featuresjson)）、`llm_settings.json`（LLM 参数，见 [LLM 配置指引](how-to-config-llm.md)）、`llm_providers.json`（多链线路）、`logger.json`（日志级别与轮转，见 [§S](#s-日志配置loggerjson)）、`llm_pricing_ref.json`（计价参考，见 [LLM 参考附录 §完整模型定价表](how-to-config-llm-reference.md#完整模型定价表)）、`llm_key.json` / `data_key.json`（两份密钥，仅手填）。

路径/文件相关字段（`holdings_dir`、`holdings_filename`、`holdings_start_date`、`output_dir`、`llm_key_file`、`llm_settings_file`、`llm_providers_file`、`data_key_file`）见上方字段总表。

---


## B. 报告章节可见性

`enable_fund_deep_analysis`、`enable_news`、`enable_history`、`enable_portfolio_evolution`、`enable_action` 五个配置项控制报告按章节组显示或隐藏对应的章节。LLM 分析章节的可见性由 `llm_settings.json` 的 `enabled_llm` 字典控制。关闭某个章节组后，该组涉及的所有章节完全隐藏，不留下序号空缺，剩余章节按顺序重新编号。

TUI 主菜单 `[C]`「配置报告章节显隐」把**所有会决定「哪一章出现」的开关**收在一处，按四块排列（编号连续、由章节注册表派生；智囊团章节下另有生成子项）：

| 块 | 编号 | 内容 | 存放 |
|:--|:--|:--|:--|
| 顶层章节 | 1-5 | 基金深度分析 / 市场新闻 / 组合历史走势+回撤 / 组合演进 / 行动建议 | `config.json` → `enable_*`（本节表格） |
| LLM 章节 | 6-12 | 全球政经局势 / 智囊团深度复盘（子项 `7.1`/`7.2`）/ 财经新闻热点与持仓关联 / 持仓体检报告 / 穿透深度分析 / 生成后自检 / 持仓变动复盘归因 | `llm_settings.json` → `enabled_llm` |
| 默认关闭的整章 | 13-15 | 调仓纪律回放 / 持仓变动复盘 / 个股基本面 | `features.json` |
| 关联产物 | 16 | What-if 交易成本对比（仅调仓模拟报告页签） | `features.json` |

> 上表编号为**当前注册表快照**：新增/删除章节后自动顺延，`?键名` 是稳定入口（面板状态行同时显示键名）。

面板只切换显隐：章节集合与顺序由注册表和 `report_section_order` 决定，不提供增删或排序；关闭后该章完全隐藏、其余章节自动连续编号。每行显式展示键名，`?编号` / `?键名` 可查来源文件与出厂默认。

> **内容增强类开关（成本流水/估值分位/市场温度/事件窗量化对照/数据质量仪表盘/行业Beta子表/候选基金比较/市场情绪/申购状态等）不在 `[C]`**——它们不增删章节，只改变章内呈现，统一由功能开关注册表的「持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要」四组管理，在菜单 `[S]` 对应块配置（见 [N. 功能开关](how-to-config.md#n-功能开关featuresjson)）。

| 字段 | 默认值 | 配置来源 | 控制章节 | 说明 |
|:-----|:------:|:---------|:---------|:-----|
| `enable_fund_deep_analysis` | `true` | `config.json` | 持仓结构与集中度、风格与因子分析（+「基金业绩分析」章末尾的基金经理变更监控块） | 基金深度分析章节组 |
| `enable_news` | `true` | `config.json` | 财经新闻热点与持仓关联分析 | 市场新闻章节组 |
| `enable_history` | `true` | `config.json` | 组合历史走势与回撤 | 历史走势章节组（持仓快照不受影响，始终自动执行） |
| `enable_portfolio_evolution` | `true` | `config.json` | 组合演进 | 组合演进章节组（持仓快照不受影响，始终自动执行） |
| `enable_action` | `true` | `config.json` | 行动建议 | 行动建议章节组（再平衡信号/交易纪律/调仓建议/收益归因，纯算法） |
| `enabled_llm`（4 个报告模块 + 1 个实验模块） | 各模块不同（仅 `news_correlation` 默认关） | `llm_settings.json` | 全球政经局势、智囊团深度复盘、持仓体检报告、穿透深度分析、LLM API 用量；`self_review`（生成后自检，**出厂默认 `true`**，开启后每次报告额外调用一次 LLM，对四模块产出做一致性复核并输出【自检清单】附录） | LLM 分析章节组。任一报告模块启用即整体可见，仅 `news_correlation` 开启时不显示 |

> **enable_news 与 news_sources 的区别：** `enable_news` 控制报告章节的可见性——是否在报告中显示新闻相关章节；`news_sources` 控制数据源的启停——报告生成时从哪些新闻提供商获取数据。两者独立配置：`enable_news: true` 并关闭所有 `news_sources` 时章节仍显示但无数据可用；反之开启数据源但 `enable_news: false` 时章节完全隐藏。

---


## C. 数据源与提供商

### news_sources 可调字段

| 子字段 | 默认 | 说明 |
| `sina` | `true` | 新浪财经（财经要闻/国内/国际，正常工作） |
| `eastmoney` | `true` | 东方财富（np-weblist 快讯接口，req_trace 参数，稳定可用） |
| `cls` | `false` | 财联社（API 要求签名鉴权，匿名请求不可用） |
| `wallstreetcn` | `true` | 华尔街见闻（全球财经直播流，JSON API，无需鉴权，推荐开启） |
| `akshare` | `true` | akshare（财新网要闻 + CCTV 财经新闻，开源封装，推荐开启） |

> **用法：** 将值改为 `true` 或 `false` 即可启用/禁用对应新闻源。

### preferred_provider 可调字段

`preferred_provider` 用于手动指定某类数据的首选提供商，将其提到 Provider Chain 第一位。不配置时全部走默认优先级，一个源失败后自动递补备用。

适用场景：某网络环境下特定数据源更稳定、或因 IP 限制某数据源不可用。

| 子字段 | 默认 chain | 可选值 | 说明 |
|--------|-----------|--------|------|
| `price` | `tencent → eastmoney` | `tencent`, `eastmoney` | 股票/ETF 实时收盘价首选源 |
| `fund_rank` | `tiantian`（仅此一个） | `tiantian` | 基金业绩排名首选源 |
| `fund_hold` | `tiantian`（仅此一个） | `tiantian` | 基金持仓穿透首选源 |
| `industry` | `eastmoney_industry → eastmoney_industry_rest` | `eastmoney_industry`, `eastmoney_industry_rest` | 行业分类/概念板块首选源（push2 不稳时可切到 REST 行情页） |

示例 — 将行情首选从腾讯改为东方财富：

```json
{
  "preferred_provider": {
    "price": "eastmoney"
  }
}
```

示例 — 行业 push2 不稳定时直接走行情页 REST 链路（跳过 push2，仅行业分类，无概念板块）：

```json
{
  "preferred_provider": {
    "industry": "eastmoney_industry_rest"
  }
}
```

> `preferred_provider` 为空对象 `{}` 时全部使用默认优先级。
>
> **💡 指数数据说明：** A 股/美股指数由 `fetcher/index.py` 直调 Provider，**不走 Provider Chain**，不受 `preferred_provider` 控制。双链路自动 fallback：
>   - A 股：**腾讯财经→新浪财经→过期缓存**
>   - 美股：**新浪财经（2次重试）→腾讯财经→过期缓存**

---

## E. 行为调优

### degradation 数据降级策略

`degradation` 控制数据降级行为，定义各层级数据在连续失败或空数据返回时切换到降级模式的阈值。

降级机制三层模型：

| 层级 | 含义 | 示例数据 |
|:----|:-----|:---------|
| **T2** | 功能级 — 某个功能模块不可用 | 新闻聚合、行业资金流向 |
| **T3** | 模块级 — 相对独立的数据模块 | 基金业绩排名、基金持仓穿透 |
| **T4** | 核心级 — 影响全局核心功能 | 股票价格、市场指数 |

每层三个参数：

| 参数 | 说明 |
|:-----|:-----|
| `unreachable_threshold` | 连续连接失败次数，达到后标记降级 |
| `empty_data_threshold` | 连续返回空数据的次数，达到后标记降级 |
| `stale_days` | 缓存过期天数，超过此天数的数据视为不可用 |

| 子字段 | `t2` | `t3` | `t4` |
|:-------|:----:|:----:|:----:|
| `unreachable_threshold` | `2` | `2` | `1` |
| `empty_data_threshold` | `3` | `3` | `1` |
| `stale_days` | `3` | `14` | `14` |

> 两个信号（连续失败 / 空数据）任一达到阈值即触发降级，取最低有效阈值。`stale_days` 仅在缓存存在时参与计算——当缓存过期天数超过此值且连续失败计数 ≥ `unreachable_threshold` 时强化降级判定。
> 
> T4 阈值最严格（1 次失败即降级）：核心价格/指数数据需要快速切换降级策略。T2/T3 允许更多容错（2~3 次），避免偶发网络波动触发不必要的降级。
>
> **持久化位置**：降级状态（上次成功时间戳等）跨会话持久化到 `data/state/.degradation_state.json`。该目录独立于 `data/cache/`，不会被菜单 `[3]` 的过期清理删除，确保下次会话启动时降级记忆恢复。

### report_section_order 报告序号配置

`report_section_order` 用于自定义报告各模块的显示序号和排列顺序。

| 子字段 | 格式 | 说明 |
|--------|:----:|------|
| 键 | 模块标识 | 报告模块的唯一标识，见下方列表 |
| 值 | 正整数 | 显示序号（1~99），决定该模块在报告中的视觉位置 |

**19 个模块标识及默认顺序：**

| 默认序号 | 模块标识 | 显示名称 | 类型 |
|:--------:|:---------|:---------|:-----|
| 1 | `summary` | 投资分析汇总 | 始终显示 |
| 2 | `holdings_detail` | 持仓明细与分类 | 始终显示（同页签两区块：市值明细 + 分类汇总） |
| 3 | `penetration` | 资产穿透TOP10 | 始终显示 |
| 4 | `fund_performance` | 基金业绩分析 | 始终显示 |
| 5 | `position_structure` | 持仓结构与集中度 | 基金深度分析（enable_fund_deep_analysis 控制；一章三区块：重合度 + 相关性 + 集中度，任一区块有数据即显示） |
| 6 | `style_factor` | 风格与因子分析 | 基金深度分析（enable_fund_deep_analysis 控制；有数据才显示，一章三区块：基金风格表 + 风格因子回归 + 行业 Beta 子表） |
| 7 | `action` | 行动建议 | 行动建议（enable_action 控制，**默认开**；再平衡信号/交易纪律/调仓建议/收益归因） |
| 8 | `news_correlation` | 财经新闻热点与持仓关联分析 | 市场新闻（enable_news 控制） |
| 9 | `global_macro` | 全球政经局势 | LLM |
| 10 | `expert_review` | 智囊团深度复盘 | LLM |
| 11 | `health_check` | 持仓体检报告 | LLM |
| 12 | `penetration_deep` | 穿透深度分析 | LLM |
| 13 | `portfolio_history_drawdown` | 组合历史走势与回撤 | 历史走势（enable_history 控制；数据不可用时占位，一章两区块：走势表 + 回撤矩阵 + 危机区间标注） |
| 14 | `portfolio_evolution` | 组合演进 | 组合演进（enable_portfolio_evolution 控制；数据不可用时占位） |
| 15 | `holding_change` | 持仓变动复盘 | 持仓变动复盘（`holding_change_review` 控制，**默认关**；快照准入未过时占位） |
| 16 | `schedule_replay` | 调仓纪律回放 | 调仓纪律回放（`rebalance_schedule_replay` 控制，**默认关**；回放不足时占位） |
| 17 | `data_source_status` | 数据源可用性矩阵 | 始终显示 |
| 18 | `fundamental_snapshot` | 持仓基本面 | 单一功能开关 `stock_fundamentals`（个股基本面）控两块（财务指标 / 财报摘要区块；开启即显示，需各自数据就绪） |
| 19 | `llm_usage` | LLM API 用量 | LLM（**始终最后**） |

**使用示例：**

将基金深度分析模块提到最前面：

```json
{
  "report_section_order": {
    "position_structure": 1,
    "style_factor": 2,
    "fundamental_snapshot": 3,
    "summary": 4
  }
}
```

> 效果：持仓结构与集中度 / 风格与因子分析 / 持仓基本面 3 个模块显示序号 1~3 并排在最前，投资分析汇总显示序号 4 紧随其后，其余未配置模块保持默认顺序排在更后。`llm_usage` 强制最后，不受配置影响。
>
> 空对象 `{}` 或缺失此字段时使用上述 19 项默认顺序。
>
> **本仓库配置**：`config.json` 的 `report_section_order` 显式列出完整 18 项（`llm_usage` 自动置末位，故合计 19），取值与上表默认顺序**完全一致**（`action`=7、`news_correlation`=8、`global_macro`=9、`expert_review`=10、`health_check`=11、`penetration_deep`=12、`portfolio_history_drawdown`=13、`portfolio_evolution`=14、`holding_change`=15、`schedule_replay`=16、`data_source_status`=17、`fundamental_snapshot`=18）。因两者同序，清空为 `{}` 效果相同。

**实用示例** — 将组合历史走势与回撤提到前面，关注回撤风险：

```json
{
  "report_section_order": {
    "portfolio_history_drawdown": 1,
    "summary": 2
  }
}
```

> 效果：组合历史走势与回撤（走势表 + 回撤矩阵 + 危机区间标注）排在第 1 位，投资分析汇总排在第 2 位，其余模块保持默认顺序。适合关注历史表现的用户。

---

## F. 业绩基准与无风险利率

### user_fund_benchmarks 自定义基准

`user_fund_benchmarks` 用于覆盖部分基金的业绩比较基准。代码内置了主流宽基/行业指数（沪深 300、中证 500、纳斯达克 100 等），遇到不在内置库中的基金时，可通过此字段手动指定。

格式：`{"基金代码": "基准代码"}`，键值均为六位基金代码（字符串或数字均可）。

```json
{
  "user_fund_benchmarks": {
    "000001": "000300",
    "005827": "399001",
    "110011": "000300"
  }
}
```

> 内置基准库实时自动补充，`user_fund_benchmarks` 仅在置信度不足时作为兜底。空对象 `{}` 表示不添加自定义覆盖。

### risk_free_rate 无风险利率

`risk_free_rate` 控制无风险利率的取值方式：

| 值 | 说明 |
|:---|:-----|
| `null` | 默认。自动从 akshare `bond_zh_us_rate` 获取中国 10Y 国债收益率 |
| 小数 | 如 `0.0174`，手动指定 1.74% |
| 百分数 | 如 `1.74`，自动识别为百分比（1.74%） |

> 无风险利率用于夏普比率、卡玛比率等量化指标的计算。

---

## G. 组合历史走势与持仓快照

### history.fetch_mode 历史走势获取模式

`history.fetch_mode` 控制组合历史走势的获取行为：

| 模式 | 说明 |
|:----|:------|
| `"off"` | 关闭。不获取历史走势数据，报告中的"组合历史走势与回撤"章节显示占位文本 |
| `"prompt"` | 询问用户是否需要获取历史走势数据（耗时约 15s）；仅 TUI 交互式询问，Web / CLI 等非交互场景按 `"auto"` 直接获取 |
| `"auto"` | 自动获取，不询问用户（默认） |

> **数据获取链路**：股票/ETF 走腾讯 K 线历史 → 新浪备用；OTC 基金走天天基金历史净值 → 东方财富备用（空结果递补）。东方财富净值 API 使用 `pageSize=20` 分页获取（最多约 200 条≈10 个月），增量缓存逐步积累更久数据。
>
> **累计收益率起算**：从 `history.coverage_threshold` 比例持仓覆盖的日期起算（**双向截断**：起算点正向扫描 ≥阈值，截止点反向扫描 ≥阈值），避免因 QDII/债券基金数据起点较晚导致早期组合市值偏低、收益率虚高，也避免尾端部分基金净值未更新导致收益率虚低。早期数据保留在走势图上但排除出收益率计算。阈值默认 `0.8`（80%），可在 `config.json` 的 `history.coverage_threshold` 中调整。

### history.lookback_days 取数窗口

`history.lookback_days` 控制组合历史走势往回取多少根 K 线/净值（交易日）：
- **股票/ETF**：向 K 线源请求最近 `lookback_days` 根日 K（腾讯/新浪，上限 365 根）
- **OTC 基金**：净值源全量返回后按最近 `lookback_days` 条截取

**与回撤矩阵的关系**：回撤矩阵需要 ≥60 个交易日（`MIN_SPAN`）才能计算独立回撤事件与最大回撤。若取数窗口低于 60，回撤矩阵将显示"有效交易日不足 60 天，暂不计算回撤事件"占位文本。默认 `90` 确保取数窗口超过门槛；配置值低于 60 或超过 365 时，配置校验会告警提示。

### 持仓快照（快照对比）

快照对比不受 `history.fetch_mode` 配置影响，在 B/L 菜单生成报告时**始终自动执行**。每次生成报告时自动保存持仓快照到 `data/history/snapshots/`，供下次环比对比。

> **持仓快照自动清理**：保存新快照后自动清理旧文件。清理规则由 `history` 块中的以下字段控制：

| 字段 | 默认值 | 说明 |
|:-----|:------:|:-----|
| `snapshot_retention_days` | `180` | 超过此天数的快照自动删除（时间优先）；默认 180 天覆盖持仓变动复盘 ≥12 周观察期门槛 |
| `snapshot_max_count` | `365` | 安全上限，超过此数量删除最旧的（数量兜底） |

可在 `config.json` 中设置：
```json
"history": {
    "fetch_mode": "auto",
    "lookback_days": 90,
    "snapshot_retention_days": 180,
    "snapshot_max_count": 365,
    "coverage_threshold": 0.8,
    "benchmark_indices": {"sh000300": "沪深300"}
}
```

> **基准指数对比**：`benchmark_indices` 配置需要在历史走势图上叠加对比的基准指数。格式为 `{指数代码: 显示名称}`，支持 A 股指数（如 `sh000300`）。获取方式走 `history_index` chain（腾讯/新浪双链路）。配置为空对象 `{}` 时不获取基准数据。

> **数据获取链路**：基准指数通过 `fetch_index_history()` → `history_index` chain → 腾讯 K 线 / 新浪 K 线（与组合持仓的个股 K 线共享熔断器）。数据写入缓存键 `history_index_{code}.json`。

---

## H. 业绩评价配置

### performance_evaluation 基金业绩评级

`performance_evaluation` 段控制基金业绩评级的超额收益阈值，用于 `fund_performance.py` 对持仓基金进行业绩评级判定。

| 键 | 默认值 | 说明 |
|:---|:------:|:-----|
| `performance_evaluation.excess_threshold_up` | `80` | 超额收益 ≥ 此值（百分点）时评级上调一级 |
| `performance_evaluation.excess_threshold_down` | `40` | 超额收益 < 此值（百分点）时评级下调一级 |

超额收益 = 基金区间收益率 - 基准指数区间收益率。评级调整分为五档（低→较低→中等→较高→高），每个百分点差距触发一次调整。

---


## I. 再平衡配置

### threshold 品种权重超限阈值

单品种持仓市值占总市值比例超过此阈值时，触发再平衡建议。默认 `0.15`（15%），可通过 `rebalance.threshold` 调整。

### deviation_threshold 大类配置偏离阈值

权益/固收等大类配置偏离目标比例超过此阈值时，触发调整建议。默认 `0.05`（5%），可通过 `rebalance.deviation_threshold` 调整。

### profile 预设阈值集

`rebalance.profile` 提供四套预设阈值组合：

| 预设 | threshold | deviation_threshold | 适用场景 |
|:-----|:---------:|:-------------------:|:---------|
| `conservative` | 10% | 3% | 保守型投资者，严格约束单品种暴露 |
| `moderate`（默认） | 15% | 5% | 稳健型投资者，允许适度集中 |
| `aggressive` | 25% | 8% | 进取型投资者，容忍较高集中度 |
| `custom` | 手动配置 | 手动配置 | 自定义阈值，profile 仅作标识 |

### silence_days 再平衡静默期

同一品种触发再平衡后 `silence_days` 天内不再重复报警，避免频繁调仓。默认 `30` 天。

### target_allocation 目标配置 Schema

`rebalance.target_allocation` 定义品种级目标配置范围，格式如下：

```json
{
  "equity": {"min": 30, "max": 70, "target": 50},
  "bond": {"min": 10, "max": 40, "target": 25}
}
```

空对象 `{}` 表示不启用此项检查。

### equity_fixed_income 权益/固收大类配置

`rebalance.equity_fixed_income` 定义权益与固收超大类目标配置，格式如下：

```json
{
  "equity": {"min": 30, "max": 70},
  "fixed_income": {"min": 10, "max": 40}
}
```

空对象 `{}` 表示不启用此项检查。

---


## J. 交易纪律配置

交易纪律信号（止盈 / 止损 / 控回撤）的触发阈值与静默期共四个 `discipline.*` 字段，见上方字段总表；无 TUI 菜单入口，需手动编辑。触发信号作用于报告「行动建议」章的交易纪律板块。

---


## K. 流动性配置

### redemption_limits 场外基金赎回上限

`redemption_limits` 配置场外基金的单日赎回上限，格式 `{基金代码: 金额}`：

```json
{
  "redemption_limits": {
    "000001": 50000,
    "005827": 10000
  }
}
```

配置后程序可计算场外品种全量赎回所需天数（**用户配置口径优先**）。未配置的品种按**类型默认档**估算：货币/短债 T+1、纯债 T+2、其他场外基金（主动权益/混合/指数/联接等）T+3、QDII T+7；此类估算在报告与评分中一律标注「类型默认档（非实测）」。仅当基金类型无法识别时才标记"需手动确认赎回上限"。

---

## L. 匿名化配置

### anonymization.mode 匿名化模式

`anonymization.mode` 控制报告中的持仓信息匿名化显示层级：

| 模式 | 名称 | 代码 | 盈亏 |
|:-----|:----|:----|:-----|
| `off`（默认） | 真实名称 | 真实代码 | 真实金额 |
| `code_display` | "品种X" | 保留代码 | 保留金额 |
| `full_anonymous` | "品种X" | "000XXX"（全报告代码列 + 演进图表 JSON + LLM 提示词 + Excel 单元格清扫） | 金额千位模糊，盈亏/收益率由模糊值派生（行内恒等）；**调仓模拟数值面（成本/回测）保留原值，不做千位模糊** |
| `summary` | 明细按大类折叠为"基金汇总/股票汇总"行 | 明细无代码列；派生章节代码同样折叠为 "000XXX" | — |

> **调仓模拟（What-if）例外口径**：差异行不适配大类折叠键位，`summary` 下调仓模拟单条持仓面改为拦截（HTML 明细区空态 / Excel 明细页占位，分类配置对比承载大类汇总），不展示单条持仓——与本节「仅显示大类汇总」同义。

生效层次：明细装配（HTML/Excel 明细与 LLM 提示词持仓块同源脱敏；**调仓 What-if 双产物物化点（Excel 写入 / HTML 渲染）同层注入**）→ 明细渲染层（summary 账户组内折叠、full 代码列显示；调仓模拟代码列同走渲染点折叠）→ 产物输出（HTML 名称文本清扫、Excel 字符串单元格清扫，代号编号三层同源；**调仓模拟 Excel 代码面走边界安全替换**——字符串单元格内嵌数值，全分子串换码会命中金额）。新闻关键词标签与申购限购约束块文本按同一代号映射掩码；行情取数、新闻检索等取数链始终使用真实值，仅显示层脱敏。

**代码面在渲染点结构化折叠**（不在 HTML 自由文本里做数字替换）：各章节代码列由模板过滤器按真码精确键控替换、演进图表 JSON 在数据层折叠、LLM 提示词组装点折叠（真码不进提示词，代码白名单块相应改写为「真码一律不写」的反幻觉约束）。产物自由文本清扫**只扫名称**——代码是纯数字串，全文子串替换会误伤金额与 JSON 数值；代码面另以**边界安全**（相邻非数字/小数点/冒号）的精确键替换兑底，命中独立代码 token 而跳过同数字片段。非持仓代码（指数、基准）不在映射内、始终原样。

**数值面**：明细层 full 千位模糊、summary 大类聚合；派生章节（财报摘要、估值分位、风格因子、基金业绩等）的数值全部来自公开市场与财报数据，与持仓身份/仓位无关，**保留原值**以维持指标口径可复核。

通过 TUI 主菜单 `G` → `A` 配置持仓匿名化可交互切换。

---

## M. 批量并行调度

### batch 池配置

`batch` 段控制批量数据获取的线程池参数：

| 键 | 默认值 | 说明 |
|:---|:------:|:-----|
| `batch.max_total_workers` | `15` | 全局 batch 线程硬上限，超过时自动钳位 |
| `batch.fund_workers` | `3` | 基金排名/持仓批量并发数 |
| `batch.industry_workers` | `8` | 行业分类批量并发数 |
| `batch.datasink_workers` | `2` | 财报全文取数并发数（DataSinking 免费档批量上限 ≤3） |
| `batch.akshare_workers` | `2` | akshare 财务指标取数并发数（财务指标章 + 景气度框架②维基金重仓 ROE 推演共用） |

```json
"batch": {
  "max_total_workers": 15,
  "fund_workers": 3,
  "industry_workers": 8,
  "datasink_workers": 2,
  "akshare_workers": 2
}
```

### batch_rate_limit Provider 请求间隔

`batch_rate_limit` 控制各数据源的请求间隔（秒），防止并发过高触发反爬限制：

| 键 | 默认值 | 说明 |
|:---|:------:|:-----|
| `tencent` | `0.0` | 腾讯行情（不限速） |
| `sina` | `0.0` | 新浪行情（不限速） |
| `eastmoney` | `0.1` | 东方财富行情（100ms） |
| `tiantian` | `0.5` | 天天基金（500ms） |
| `eastmoney_industry` | `0.05` | 东方财富行业（50ms） |

值为 0 表示不限速。配置后可通过菜单 `R` 刷新配置立即生效，无需重启程序。

---

## O. 缓存分组

所有缓存模块归入两个分组，控制菜单命令的缓存清除范围：

| 分组 | 包含模块 | 使用场景 |
|------|---------|----------|
| `preload` | 股票价格、市场指数、LLM 全球政经局势、LLM 智囊团深度复盘、LLM 持仓体检报告、LLM 穿透深度分析、LLM 生成后自检、LLM 持仓变动复盘归因、LLM 辩论三段（正/反/综合） | **切换持仓文件后必须重取的数据。** 价格/指数随持仓变动，LLM 基础分析依赖持仓内容，切换到新持仓文件时必须清除旧缓存 |
| `refresh` | 基金业绩排名、基金持仓、行业分类、市场情绪、财报索引、财报正文、财务指标、新闻聚合、LLM 新闻关联分析、机构盈利预测、行业资金流向、股票历史分红、基金业绩基准、基金经理数据、基金风格扩展数据、无风险利率（持仓重合度复用基金持仓缓存，随其一并清除，无独立缓存键）、基金申赎费率、指数估值历史 | **可随时独立刷新的补充数据。** 不依赖持仓文件切换，任何时候都可以主动刷新 — 如盘中更新行业资金流向、拉取最新基金排名 |

**无分组的模块**（`tracking` 持仓跟踪、`calendar` 交易日历、`fund_concentration` 集中度历史快照、`fund_style_snapshot` 风格快照、`history_stock` 历史 K 线、`history_fund_otc` 历史净值、`history_index` 指数历史日线）：未被任何分组覆盖，不会被菜单缓存命令误删。对应 TTL 可通过 `cache_ttl.{key}` 自行调整。


## P. 机器本地状态（非 config.json）

以下状态**不存放于 config.json**，而是存于 `data/state/local_state.json`（git 忽略，仅本机可见）：

| 状态键 | 说明 |
|:-------|:-----|
| `_startup_wizard_shown` | 首次运行引导是否已显示 |
| `_privacy_notice_shown` | 隐私声明是否已显示 |

**为什么独立存放：** config.json 受 git 跟踪、用于跨机器同步。若把"本机是否已看过引导"这类个性化标志写入 config.json，每台机器会写入各自不同的值，导致 config.json 难以同步。故机器个性化状态统一放 `data/state/` 目录（与熔断器状态、再平衡静默期等同目录），不参与同步。这两个键仅由 `config/_local_state.py` 在 `data/state/local_state.json` 中读写，不做任何 config.json 迁移。

---


## Q. Web 模式配置编辑

Web 模式（浏览器界面）提供「配置编辑」面板，可修改的配置项与 TUI 主菜单**完全一致**（完整镜像）。面板按**五个意图域**分区（报告内容 / 呈现与机制 / 数据与线路 / LLM 运行 / 运行与诊断），域内再按块分组；域与 TUI 菜单不一一对应，两渠道共用同一批条目名与标记口径：

| 组 | 配置项 | 对应 TUI 菜单 |
|:--|:--|:--|
| 路径与文件 | `holdings_dir` / `holdings_filename` / `output_dir` | `[G]` → `H` / `F` / `O` |
| 报告章节 | `enable_fund_deep_analysis` / `enable_news` / `enable_history` / `enable_portfolio_evolution` / `enable_action` | `[C]` 1~5 |
| 持仓与交易 | `cost_lots`（默认关）/ `fund_purchase_limit` / `cost_position` / `risk_adjusted_excess`（默认关） | `[S]` 1-4 |
| 市场与估值 | `valuation_percentile`（默认关）/ `market_temperature` / `crisis_replay`（默认关）/ `prosperity_framework` | `[S]` 5-8 |
| 基金与风格 | `factor_catalog` / `industry_beta` / `candidate_compare`（默认关） | `[S]` 9-11 |
| 事件与摘要 | `event_window_impact`（默认关）/ `data_quality` / `market_sentiment`（默认关）/ `summary_highlights`（默认关） | `[S]` 12-15 |
| 呈现与交互 | `report_qa`（默认关）/ `metrics_enabled` | `[S]` 16-17 |
| 机制与质量 | `decision_reflection`（默认关）/ `deterministic_signal` / `module_quality_gate` | `[S]` 18-20 |
| 独立章节与回放 | `rebalance_schedule_replay`（默认关）/ `holding_change_review`（默认关）/ `whatif_trade_cost`（默认关）/ `stock_fundamentals`（默认关） | `[C]` 整章与关联产物块 |
| 章节内选项 | `llm_debate_procon`（默认关）/ `llm_debate_conditional` | `[C]` 7.1 / 7.2（智囊团复盘子项） |
| 持仓匿名化 | `anonymization.mode`（off / code_display / full_anonymous / summary） | `[G]` → `A` |
| 对比指数池 | `comparison_indices`（增 / 删 / 重置默认） | `[G]` → `I` |
| LLM 多链线路优先级 | `llm_providers.providers[].priority`（各条目 ▲▼ 调序） | `[G]` → `L` 第 7 项 |
| LLM 调优参数 | `llm_max_thinking_concurrency` / `llm_max_concurrency` / `max_retries` / `llm_full_fail_retry_delay` / `llm_total_time_budget_sec` / `daily_cost_limit` | `[G]` → `L` |
| LLM 分析章节 | `enabled_llm.global_macro` / `expert_review` / `health_check` / `penetration_deep` / `news_correlation` / `self_review` / `holding_change` | `[C]` LLM 章节块 |

**写入行为**：
- 面板修改**立即写入**共享配置文件（`config.json` / `llm_settings.json` / `features.json`），TUI / CLI 下次读取即生效（缓存按文件修改时间自动失效，无需手动刷新）。
- 写共享配置文件**前自动备份**为 `{文件}.bak`（单槽轮转，仅保留最近一份），可手动还原：将 `.bak` 改回原文件名即可。
- Web 与 TUI / CLI 编辑的是**同一份配置**。请避免 Web 与 TUI 同时修改配置（两者属不同进程，跨进程并发读-改-写可能互相覆盖）；`.bak` 提供最近一份回滚。
- 说明：辩论白脸/黑脸/综合三段的运行时开关是「章节内选项」组的辩论-正反辩论（`llm_debate_procon`）与辩论-条件推理（`llm_debate_conditional`），不作为独立模块出现在 LLM 模块清单里；三段的磁盘缓存（`llm_debate_*` 前缀）登记在缓存域，随「更新行情类缓存」一并清除。

---


## R. 任务完成通知（notify）

无人值守（cron / 任务计划）运行只有退出码与日志，成功/失败都要人工翻日志。`notify` 节配置报告生成完成后的通知推送：**失败（退出码非 0）必发、成功需 `on_success: true`**；缺省全关 = 静默跳过（不配置该节完全不影响其他功能）。

| 键 | 默认值 | 说明 |
|:---|:------:|:-----|
| `notify.on_success` | `false` | 成功也发送（失败/部分失败必发，不受此开关影响） |
| `notify.webhook_url` | `""` | webhook 地址（HTTP POST JSON 事件），空=不启用；URL 常含路径凭据，日志只记域名 |
| `notify.email.smtp_host` / `to` | `""` | SMTP 服务器与收件人（**两者均非空**才启用邮件通道）；`to` 支持逗号/分号多地址 |
| `notify.email.smtp_port` / `use_ssl` | `465` / `true` | 端口与加密（`false` 时走 STARTTLS） |
| `notify.email.username` / `password` | `""` | 登录凭据（留空 = 匿名发信；口令不入任何日志） |
| `notify.desktop` | `false` | 桌面通知（Linux notify-send；未安装记日志跳过） |
| `notify.timeout_seconds` | `10` | 通道超时（秒） |

```jsonc
"notify": {
  "on_success": false,
  "webhook_url": "",
  "email": {"smtp_host": "", "smtp_port": 465, "use_ssl": true, "username": "", "password": "", "to": ""},
  "desktop": false,
  "timeout_seconds": 10
}
```

**载荷**：报告类型 / 退出码 / 产物路径（`LATEST_XLSX_NAME`/`LATEST_HTML_NAME` 命名单源，按结果标志列示）/ 错误数（全量）与明细（截断 20 条）/ 数据降级摘要（数据状态跟踪器，最新在前按源去重 10 条）。

**可靠性**：单次尝试无重试（收尾路径不引入退避等待）；单通道失败隔离，任何通道失败只记日志（`[notify]` 前缀）、**绝不改变退出码**（尽力而为）；webhook URL 异常消息落日志前掩码只留域名。CLI 用法见 [how-to-use-cli-mode.md](how-to-use-cli-mode.md)「13.4 任务完成通知（notify）」。**接线范围**：CLI 报告收尾 + Web 报告收尾（手动生成与 Web 内置定时调度共用同一执行体）——Web 定时生成失败同样按此配置推送。

---


## S. 日志配置（logger.json）

日志是**运行诊断域**的独立配置，不与持仓/报告/数据源混在一起；文件缺失时全默认，不报错。

| 键 | 类型 | 默认 | 范围 | 说明 |
|:--|:--|:--|:--|:--|
| `file.path` | str | `logs/app.log` | 非空、不含 `..` | 写盘目标（相对项目根或绝对路径；测试进程固定 `logs/test.log`） |
| `file.level` | enum | `INFO` | DEBUG / INFO / WARNING / ERROR / CRITICAL | 写盘级别 |
| `file.max_bytes` | int | `10485760` | 1024 ~ 1073741824 | 单文件上限（字节） |
| `file.backup_count` | int | `5` | 0 ~ 50 | 备份份数（0 = 不轮转） |
| `console.level` | enum | `INFO` | 同上 | 控制台级别 |
| `console.color` | bool | `true` | — | 允许颜色（`NO_COLOR` / 非 TTY 自动降级） |
| `viewer.default_level` | enum | `INFO` | 同上 + `ALL` | 日志查看器默认筛选级别 |
| `viewer.tail_lines` | int | `500` | 50 ~ 10000 | 查看器首屏读取行数 |

```jsonc
{
  "version": 1,
  "file": {"path": "logs/app.log", "level": "INFO", "max_bytes": 10485760, "backup_count": 5},
  "console": {"level": "INFO", "color": true},
  "viewer": {"default_level": "INFO", "tail_lines": 500}
}
```

> - **优先级**：环境变量 `INVEST_LOG_FILE_LEVEL` / `INVEST_LOG_CONSOLE_LEVEL` > `logger.json` > 内置默认（仅级别可被环境变量临时覆盖，其余键只由文件决定）。
> - **校验**：非法级别/越界数值/含 `..` 的路径在**保存时拒绝**（文案含键名、当前值、合法范围）；加载时告警并回落默认，不阻断启动。
> - `version` 不符 → 拒绝加载并提示删除后重新生成（不做旧结构转换）。
> - 日志目录不可写 → 启动告警并降级为仅控制台输出，主流程继续。


## 与菜单命令的对应关系

- **菜单 `[1]` 更新基础类缓存** → 清除 `refresh` 组全部缓存，然后重新拉取。适合：启动后先刷新补充数据，再生成报告。纯股票组合时自动跳过基金排名/持仓/基准刷新，仍主动重拉行业分类、分红、盈利预测、资金流向。新闻缓存清除后由后续报告生成按需重建。
- **菜单 `[2]` 更新行情类缓存** → 清除 `preload` 组全部缓存，然后并行拉取新持仓的价格和指数。适合：切换到另一份持仓文件时一键清理依赖旧持仓的缓存。

两组互不重叠：`[1]` 不会误删价格/指数缓存，`[2]` 不会误删基金排名/行业分类缓存。

> **调整建议：** 持仓变动少可将 `hold` 的 TTL 调大为 30 天，减少基金持仓的重复拉取。
>
> **交易时段短 TTL：** `price` 和 `index` 在 A 股交易时段（09:30–11:30 + 13:00–15:00）自动使用 `market_hour_ttl`（默认 30s）替代常规 TTL，确保盘中实时行情。收盘后自动回落长 TTL 保持收盘价。可通过 `market_hours` 配置手动调整。
> **哪些类型盘中敏感由程序声明**（不是配置项）：只有行情价与指数是分钟级变化，它们会随盘中降频；新闻（15 分钟）、情绪（1 小时）、财报索引（24h）等数据不因盘中被降频——否则只是把上游请求翻几倍而拿回同一份数据。若你同时配了 `cache_ttl.price`，盘中仍以 `market_hour_ttl` 为准（日志会提示一次），`cache_ttl.price` 只在盘后生效。

---

---

**相关手册**：[← Web 浏览器模式](how-to-use-web-mode.md) · [LLM 配置指引 →](how-to-config-llm.md) · [手册总索引](README.md)
同主题：[TUI 菜单操作手册](how-to-use-tui-menu.md) · [数据源一览](datasource.md)

---

**相关手册**：[← 配置指南](how-to-config.md) · [LLM 配置指引](how-to-config-llm.md) · [手册总索引](README.md)

