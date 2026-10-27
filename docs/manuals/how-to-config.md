# 配置指南

主配置文件 `data/config/config.json`，程序首次启动时自动创建。

## 目录

- [配置项总览（出厂 config.json）](#配置项总览出厂-configjson) —— 带注释的完整样例，照抄改值即可
- [字段说明](#字段说明) —— 键 / 默认值 / 一句话说明 / 改它的入口（90% 的需求在这一张表里）
- [D. 市场时段与缓存](#d-市场时段与缓存) · [N. 功能开关（features.json）](#n-功能开关featuresjson)
- [配置文件随版本更新](#配置文件随版本更新)
- [配置字段详解（独立参考）](how-to-config-fields.md) —— A/B/C/E…S 逐节逐键说明（含 JSON 片段与判定口径）

## 配置项总览（出厂 config.json）

```json
{
  // ── A. 路径与文件 ──
  "holdings_dir": "data/holdings",
  "holdings_filename": "个人投资持仓信息.xlsx",
  "holdings_start_date": "",  // 组合建仓日期（YYYY-MM-DD，可选）：未录入交易/分红流水时按「建仓日一次性买入」近似年化；空=仅成本分档近似
  "output_dir": "reports",
  "llm_key_file": "data/config/llm_key.json",
  "llm_settings_file": "data/config/llm_settings.json",
  "llm_providers_file": "data/config/llm_providers.json",
  "data_key_file": "data/config/data_key.json",  // 数据源密钥文件（通用；以 provider 名为节，如 {"datasink": {"api_key": "..."}, "hithink": {"api_key": "..."}}）

  // ── B. 报告章节可见性 ──
  "enable_fund_deep_analysis": true,  // 基金深度分析+因子暴露+相关性
  "enable_news": true,      // 市场新闻
  "enable_history": true,   // 组合历史走势与回撤
  "enable_portfolio_evolution": true,  // 组合演进
  "enable_action": true,     // 行动建议（默认开，可在菜单 C 关闭）
  // 报告章节与章内增强开关见 data/config/features.json（功能开关注册表；章内内容在菜单 [S]、独立整章与关联产物在菜单 [C]）
  "comparison_candidates": [],  // 候选基金比较子表候选（6 位基金代码列表，≤10；配合 candidate_compare）

  // ── C. 数据源与提供商 ──
  "news_top_count": 300,
  "llm_report_depth": "standard",
  "news_sources": {
    "sina": true,
    "eastmoney": true,
    "cls": false,
    "wallstreetcn": true,
    "akshare": true
  },
  "preferred_provider": {},
  "datasink": {
    "enabled": true,               // 数据底座总开关：关闭后依赖它的分析（财务指标章/真实估值分位）静默回原样
    "plan": "free",                 // free / yearly；决定限速与日配额的默认值
    "requests_per_second": 0,       // 0=按 plan 自动（free=3，yearly=31）
    "daily_quota": 0,               // 0=按 plan 自动（free=8191，yearly=131071）
    "sections": ["管理层讨论与分析"],  // 取用章节：按顺序在文档实际章节名中子串匹配（fuzzy 标题匹配），命中即取
    "max_chars": 2000,             // 单股摘要截断长度
    "doc_types": []               // 文种白名单：空 = 不限文种（取最新报告期，半年报/季报通常比年报新）
  },

  // ── D. 市场时段与缓存 ──
  "market_hour_ttl": 30,
  "market_hours": {
    "start": "09:30",
    "end": "15:00",
    "official_source": true
  },
  // cache_ttl：稀疏覆盖位。默认值见下方「cache_ttl 可调参数」表（来自缓存注册表）；
  // 仅需调整某个类型时在此添加该键，如 { "llm_expert_review": 21600 }；删键即回默认。
  "cache_ttl": {},

  // ── E. 行为调优 ──
  "default_menu_key": "L",
  "report_section_order": {},
  "degradation": {
    "t2": {"unreachable_threshold": 2, "empty_data_threshold": 3, "stale_days": 3},
    "t3": {"unreachable_threshold": 2, "empty_data_threshold": 3, "stale_days": 14},
    "t4": {"unreachable_threshold": 1, "empty_data_threshold": 1, "stale_days": 14}
  },

  // ── F. 业绩基准与无风险利率 ──
  "risk_free_rate": null,
  "user_fund_benchmarks": {},
  "comparison_indices": {"sh000300": "沪深300", "sh000905": "中证500", "sh000012": "中证全债"},

  // ── G. 组合历史走势与持仓快照 ──
  "history": {
    "fetch_mode": "auto",  // 历史走势获取模式: off=关闭 / prompt=报告后询问 / auto=自动获取
    "lookback_days": 90,  // 历史走势取数窗口（K 线条数/交易日），需≥60（回撤矩阵最少交易日）才计算回撤矩阵，上限 365
    "snapshot_retention_days": 180,
    "snapshot_max_count": 365,
    "coverage_threshold": 0.8,
    "benchmark_indices": {"sh000300": "沪深300"}
  },

  // ── H. 业绩评价配置 ──
  "performance_evaluation": {
    "excess_threshold_up": 80,      // 超额收益 >= 此值 -> 上调一级
    "excess_threshold_down": 40     // 超额收益 < 此值 -> 下调一级
  },

  // ── I. 再平衡配置 ──
  "rebalance": {
    "threshold": 0.15,
    "deviation_threshold": 0.05,
    "profile": "moderate",
    "silence_days": 30,
    "target_allocation": {},
    "equity_fixed_income": {}
  },

  // ── J. 交易纪律配置 ──
  "discipline": {
    "take_profit_pct": 20.0,
    "stop_loss_pct": -15.0,
    "drawdown_pct": -10.0,
    "silence_days": 30
  },

  // ── K. 流动性配置 ──
  "redemption_limits": {},

  // ── L. 匿名化配置 ──
  "anonymization": {
    "mode": "off"
  },

  // ── M. 批量并行调度 ──
  "batch": {
    "max_total_workers": 15,
    "fund_workers": 3,
    "industry_workers": 8,
    "datasink_workers": 2,
    "akshare_workers": 2
  },
  "batch_rate_limit": {
    "tencent": 0.0,
    "sina": 0.0,
    "eastmoney": 0.1,
    "tiantian": 0.5,
    "eastmoney_industry": 0.05
  }
}
```

## 字段说明

以下字段可通过 TUI 主菜单的对应命令修改（运行 `.venv/bin/python -m src.python.tui` 进入主菜单）。标有"手动编辑"的字段需直接修改 JSON 文件。

| 字段 | 默认值 | 说明 | TUI 修改 |
|------|--------|------|----------|
| `holdings_dir` | `data/holdings` | 持仓 xlsx 文件所在目录 | 菜单 `G` → `H` |
| `holdings_filename` | `个人投资持仓信息.xlsx` | 要读取的持仓文件名 | 菜单 `G` → `F` |
| `holdings_start_date` | `""` | 组合建仓日期（YYYY-MM-DD，可选）。持仓 Excel 未录入交易/分红流水时，成本流水子模块按「建仓日一次性买入」近似年化；空=不计算近似年化，仅成本分档近似（每份成本 vs 市价）。须配合功能开关 `cost_lots` 开启 | 手动编辑 |
| `output_dir` | `reports` | 报告输出目录（最新版+按日期存档） | 菜单 `G` → `O` |
| `llm_key_file` | `data/config/llm_key.json` | LLM 密钥文件路径（4 个必填字段 + 4 个可选回退字段） | 手动编辑 |
| `llm_settings_file` | `data/config/llm_settings.json` | LLM 非敏感配置文件路径 | 手动编辑 |
| `llm_providers_file` | `data/config/llm_providers.json` | LLM 多 Provider 链式服务配置文件路径，参见 [LLM 配置指引](how-to-config-llm.md) | 手动编辑 |
| `data_key_file` | `data/config/data_key.json` | 数据源密钥文件路径（**通用**：以 provider 名为节，节内字段默认 `api_key`，如 `{"datasink": {"api_key": "..."}, "hithink": {"api_key": "..."}}`；一个文件容纳多个数据源的 key。各源申请地址见数据源可用性矩阵。环境变量如 `DATASINK_API_KEY` / `HITHINK_FINANCE_API_KEY` 可覆盖对应源） | 手动编辑 |
| `news_top_count` | `300` | 财经新闻热点与持仓关联分析输出条目上限（各源原始获取量 = max(500, news_top_count × 2)，华尔街见闻硬上限 100 条除外） | 手动编辑 |
| `llm_report_depth` | `"standard"` | 报告深度档位：`brief`（仅全球政经，采集与调用最少）/ `standard`（按各模块开关参与）/ `deep`（全模块 + 新闻采集不少于 500 条）。档位只**收窄**模块集合与新闻采集规模，**不得打开已关闭的模块**；`brief` 下若与开关交集为空则 LLM 章节以占位呈现。取值非法时按 `standard` 处理并告警 | 手动编辑 |
| `news_sources` | 见下方 | 各新闻数据源启停开关 | 手动编辑 |
| `preferred_provider` | `{}` | 各数据类型的首选提供商覆写 | 手动编辑 |
| `datasink.*` | `{enabled: true, plan: "free", ...}` | DataSinking 数据底座配置：`enabled`（**总开关，默认开**；关闭后所有依赖该底座的分析——财务指标章、真实历史估值分位——**静默回到引入前的报告形态**，不产生任何可感知变化）、`plan`（free/yearly，决定限速与日配额默认值）、`requests_per_second` / `daily_quota`（0=按 plan 自动）、`sections`（取用章节偏好：按顺序在文档实际章节名中子串匹配，命中即取；季报会自动落到「主要财务数据/主要会计数据」）、`max_chars`（摘要截断）、`doc_types`（**文种白名单，空数组 = 不限文种**，默认取最新报告期——半年报/季报通常比年报新）。免费档 3 请求/秒（触发 429 时自动退避重试一次）、8191 篇/日；仅覆盖 A 股 | 手动编辑 |
| `market_hour_ttl` | `30` | 交易时段内**价/指**的缓存有效期（秒），最短 30s，最长 86400s。盘中敏感类型由注册表声明（`price`/`index`），原 `market_hour_aware` 已退役（写入会告警并被忽略）；低于 30s 的值在配置校验时告警，运行时自动钳制到 30s | 手动编辑 |
| `market_hours` | `{start: "09:30", end: "15:00", official_source: true}` | 市场时段配置（见 §market_hours 章节） | 手动编辑 |
| `cache_ttl.*` | 见下方 | 各缓存类型有效期（秒） | 手动编辑 |
| `default_menu_key` | `L` | TUI 菜单缺省选项的快捷键（E/B/L/W/Q/D/1/2/4/P/I/A/S/R/V/H/T/X；其中 `T`（系统自检）恒上屏，`Q`（报告追问）受 `report_qa` 开关门控）。取值未命中时回落到 `L` |
| `prosperity_framework` | 见默认值 | 景气度框架诊断（常规功能 `prosperity_framework`）：`boom_keywords` / `global_edge_keywords` / `defensive_keywords`（板块与概念关键词表）+ `concentration_target_pct`（前十大集中度目标 %） | 手动编辑 |
| `report_section_order` | `{}` | 报告模块序号配置。空对象使用默认顺序（19 项）。键=模块标识，值=序号；已配置模块按序号升序在前，未配置模块按默认顺序在后。`llm_usage` 强制末位 | 手动编辑 |
| `degradation` | `{...}` | 数据降级策略（T2/T3/T4 各层的连续失败阈值、空数据阈值、缓存过期天数，见 §degradation 章节） | 手动编辑 |
| `user_fund_benchmarks` | `{}` | 自定义基金业绩基准覆盖（键=基金代码，值=基准代码） | 手动编辑 |
| `comparison_indices` | `{"sh000300": "沪深300", "sh000905": "中证500", "sh000012": "中证全债"}` | 竞争语境对比指数池。智囊团深度复盘中对比组合 vs 多指数的今日涨跌幅、区间累计收益和指标（夏普/波动率/最大回撤）。格式 `{指数代码: 显示名称}`。禁用时设为空对象 `{}` | 手动编辑 |
| `risk_free_rate` | `null` | 无风险利率手动配置（null=自动从国债收益率获取，填小数如0.0174或百分比如1.74）。程序默认通过 akshare `bond_zh_us_rate` 获取中国 10Y 国债收益率 | 手动编辑 |
| `history.fetch_mode` | `"auto"` | 组合历史走势获取模式：`"off"`=关闭、`"prompt"`=报告后询问、`"auto"`=自动获取（默认）。设为 `"off"` 时章节**仍显示**，但历史走势/回撤、尾部风险、累计收益率等章节内容以「数据不可用」占位醒目警示（区别于 `enable_history=false` 的整章隐藏） | 手动编辑 |
| `history.lookback_days` | `90` | 组合历史走势取数窗口（K 线条数/交易日）。需 ≥60（回撤矩阵所需最少交易日）才计算回撤矩阵，上限 365（K 线源最多返回条数）。股票/ETF 按此取 K 线条数，OTC 基金全量净值截取最近 N 条 | 手动编辑 |
| `history.snapshot_retention_days` | `180` | 持仓快照保留天数（`data/history/snapshots/`），超期自动删除；需覆盖持仓变动复盘复盘窗口门槛（≥12 个周频观察期，跨季度）故默认 180 天 | 手动编辑 |
| `history.snapshot_max_count` | `365` | 持仓快照最大数量上限，超限删除最旧的（安全兜底） | 手动编辑 |
| `history.coverage_threshold` | `0.8` | 有效区间覆盖比例阈值（0~1）。有效区间起算日和截止日均要求 ≥此比例×总持仓 有数据，否则向前/向后递延截断。提高该值可增加起算日市值真实性，但会缩短有效区间 | 手动编辑 |
| `history.benchmark_indices` | `{"sh000300": "沪深300"}` | 基准指数配置，格式 `{指数代码: 显示名称}`。组合历史走势图上叠加显示这些指数的归一化曲线。禁用时可设为空对象 `{}` | 手动编辑 |
| `whatif_benchmark_index` | `""` | What-if 业绩基准指数覆盖（如 `"sh000905"`）。空 = 自动映射：目标持仓成本降序逐只取基金业绩基准文本，与 `comparison_indices` 池反查，全不命中回落 `sh000300`（沪深300）。仅服务 `whatif_trade_cost` 开关的业绩基准三线；非法指数代码校验告警并回落自动映射 | 手动编辑 |
| `performance_evaluation.excess_threshold_up` | `80` | 超额收益 ≥ 此值（百分点）时基金业绩评级上调一级 | 手动编辑 |
| `performance_evaluation.excess_threshold_down` | `40` | 超额收益 < 此值（百分点）时基金业绩评级下调一级 | 手动编辑 |
| `rebalance.threshold` | `0.15` | 单品种权重超限阈值（15%），超限触发再平衡建议 | 手动编辑 |
| `rebalance.deviation_threshold` | `0.05` | 大类/品种配置偏离阈值（5%），权益/固收偏离超限时触发调整建议 | 手动编辑 |
| `rebalance.profile` | `"moderate"` | 预设阈值集：conservative（保守 10%/3%）/ moderate（稳健 15%/5%）/ aggressive（进取 25%/8%）/ custom（自定义） | 手动编辑 |
| `rebalance.silence_days` | `30` | 再平衡信号静默期天数。同一品种触发再平衡后 N 天内不再重复 | 手动编辑 |
| `rebalance.target_allocation` | `{}` | 目标配置 Schema（空=不启用）。格式 `{"equity":{"min":30,"max":70,"target":50}, "bond":{...}}` | 手动编辑 |
| `rebalance.equity_fixed_income` | `{}` | 权益/固收超大类目标配置（空=不启用）。格式 `{"equity":{"min":30,"max":70}}` | 手动编辑 |
| `discipline.take_profit_pct` | `20.0` | 止盈线（%）：单品种收益率 ≥ 此值 → 建议部分止盈 | 手动编辑 |
| `discipline.stop_loss_pct` | `-15.0` | 止损线（%）：单品种收益率 ≤ 此值 → 建议止损/减仓 | 手动编辑 |
| `discipline.drawdown_pct` | `-10.0` | 回撤线（%）：组合相对历史峰值回撤 ≥ 此绝对值 → 建议控回撤（需组合历史估值数据提供峰值） | 手动编辑 |
| `discipline.silence_days` | `30` | 交易纪律信号静默期天数。同一品种触发纪律后 N 天内不再重复告警 | 手动编辑 |
| `redemption_limits` | `{}` | 场外基金单日赎回上限，格式 `{基金代码: 金额}`。配置后程序可计算场外品种全量赎回所需天数（配置口径优先）；未配置品种按类型默认档估算（货币/短债 T+1、纯债 T+2、其他场外 T+3、QDII T+7，标「非实测」），类型无法识别才标记"需手动确认赎回上限" | 手动编辑 |
| `fund_fee_fallback` | `{}` | 申赎费率配置兑底（键=6 位基金代码，值=`{purchase_rate: 0≤r<1 小数单档申购费率, redemption_tiers: [{"max_days": 上界交易日\|null, "rate": 0≤r<1 小数}]}`；档位按交易日上界严格递增、末档 `max_days` 为 `null`）。**仅当在线来源（F10 费用页/申购状态全量表）不可得时生效，不覆盖在线结果**；仅服务 What-if 交易成本估算（`whatif_trade_cost` 开关），条目非法时告警忽略 | 手动编辑 |
| `anonymization.mode` | `"off"` | 匿名化模式：`off`（关闭，显示真实名称代码）/ `code_display`（名称→"品种X"，保留代码和盈亏）/ `full_anonymous`（名称→"品种X"，代码→"000XXX"（明细页/Excel 单元格），盈亏金额千位模糊）/ `summary`（明细按大类汇总折叠） | 菜单 `G` → `A` |
| `enable_fund_deep_analysis` | `true` | 基金深度分析章节可见性，关闭后对应章节完全隐藏，不产生序号空缺 | 菜单 `C` |
| `enable_news` | `true` | 市场新闻章节可见性，关闭后对应章节完全隐藏。与 `news_sources` 区别：前者控制章节在报告中的显示/隐藏，后者控制数据源启停 | 菜单 `C` |
| `enable_history` | `true` | 历史走势章节可见性（组合历史走势与回撤，一章两区块：走势表 + 回撤矩阵 + 危机区间标注），关闭后对应章节完全隐藏。持仓快照不受影响，始终自动执行 | 菜单 `C` |
| `enable_portfolio_evolution` | `true` | 组合演进章节可见性，关闭后对应章节完全隐藏。持仓快照仍照常记录，仅影响报告展示 | 菜单 `C` |
| `enable_action` | `true` | 行动建议章节可见性，**默认开启**，关闭后隐藏 再平衡信号/交易纪律/调仓建议/收益归因 行动板块（纯算法，basic/both/full 均可见）。智囊团深度复盘同步隐藏「行动摘要」子块 | 菜单 `C` |
| `comparison_candidates` | `[]` | 候选基金比较子表的候选基金代码列表（6 位基金代码，≤10 只）。需配合功能开关 `candidate_compare` 开启；非法代码自动忽略，超过 10 只仅比较前 10 只 | 手动编辑 |
| `notify.on_success` | `false` | 任务完成通知：成功也发送（失败/部分失败必发，不受此开关影响）；缺省全关=静默跳过 | 手动编辑 |
| `notify.webhook_url` | `""` | 任务完成通知 webhook 地址（HTTP POST JSON 事件），空=不启用；URL 常含路径凭据，日志只记域名 | 手动编辑 |
| `notify.email` | `{smtp_host:"",...}` | 任务完成通知邮件通道（`smtp_host` 与 `to`均非空才启用；`use_ssl` 切 SSL/STARTTLS；`to` 支持逗号/分号多地址） | 手动编辑 |
| `notify.desktop` | `false` | 任务完成通知桌面通道（Linux notify-send；未安装时记日志跳过） | 手动编辑 |
| `scheduler` | `{...}` | 内置定时生成（Web 专属）：`enabled` 启用开关（缺省 `false`）/ `time` 触发时刻 HH:MM（本机时区）/ `weekdays` 执行日（0=周一 … 6=周日）/ `report_type` 报告格式（basic/both/full）；到点自动读正式持仓生成（正式-用存量），与手动生成同队列串行互斥、宽限 30 分钟内顺延 | Web 调度面板（配置页签） / 手动编辑 |

> 以上两条同样作用于 **Web 试算快照域**（`data/history/snapshots/web/`）：Web「临时试算」的快照按相同保留天数与上限在试算域内独立清理，与共享主目录互不影响。Web 模式除定时生成 `scheduler` 块（Web 专属，见上方字段总表与 Web 手册「定时生成调度面板」）外无新增配置键。

---

> **逐节详解**：A（路径与文件）、B（报告章节可见性）、C（数据源与提供商）、E（行为调优）、F（业绩基准）、G（组合历史）、H（业绩评价）、I（再平衡）、J（交易纪律）、K（流动性）、L（匿名化）、M（批量并行）、O（缓存分组）、P（本地状态）、Q（Web 编辑）、R（通知）、S（日志）与「与菜单命令的对应关系」见 [配置字段详解](how-to-config-fields.md)；本节只保留 D（市场时段与缓存）与 N（功能开关）——两者的表由门禁逐行核对。

### D. 市场时段与缓存

#### market_hours 可调参数

`market_hours` 控制 A 股交易时段判断，用于盘中实时行情（短 TTL）和盘后收盘价（长 TTL）的自动切换。

判断逻辑为三层逐级 fallback：

1. **config.json 手动覆盖** — 以下 `start`/`end` 优先级最高
2. **东方财富 push2 API** — 实时交易状态（缓存 TTL：盘中 60s，盘后 7 天）
3. **内置默认值** — 北京时区工作日 09:30–11:30 + 13:00–15:00，自动排除午餐和周末

| 子字段 | 默认值 | 说明 |
|--------|:------:|------|
| `start` | `"09:30"` | 手动覆盖开盘时间（HH:MM），覆盖内置默认值 09:30 |
| `end` | `"15:00"` | 手动覆盖收盘时间（HH:MM），覆盖内置默认值 15:00 |
| `official_source` | `true` | 是否尝试从东方财富 push2 API 获取实时交易状态。设为 `false` 时跳过本层直接 fallback 内置默认值 |

`official_source` 启用时，程序通过东方财富 push2 API 获取实时交易状态，根据开/午休/收盘状态自动切换缓存 TTL：盘中 60 秒高频刷新，盘后 7 天长效缓存。

> **午餐休市：** 实际交易分为 09:30–11:30（上午）和 13:00–15:00（下午）两段。即使 `start`/`end` 覆盖为 `"09:30"`/`"15:00"`，午餐时段（11:30–13:00）自动视为非交易时段并回落长 TTL。`official_source: true` 时 API 返回 `status=3`（午间休市）也会让系统识别午餐休市。

#### cache_ttl 可调参数

> **默认值只存在于代码注册表**（`core/data_registry.py` 的 `DataModuleDef.cache_ttl`）；本节表格是它的**只读参考**。
> 生成的 `config.json` 里 `cache_ttl` 是**空对象**——需要调某个类型时再添加该键（如 `"llm_expert_review": 21600`），删掉该键即回到默认值。
> 这样「默认值」只有一处：代码改默认值即对所有未覆盖的安装生效，配置文件不会留下与之不一致的旧副本。

> `—` 表示该缓存类型文件名为精确键名（无指纹后缀），不受持仓变化影响，仅在 TTL 到期后刷新。

快速定位：— [行情/数据类](#行情数据类) — [LLM 分析类](#llm-分析类) — [基金深度分析类](#基金深度分析类) — [系统类](#系统类) — [历史走势类](#历史走势类)

##### 行情/数据类

| 键名 | 文件名模式 | 默认 TTL | 指纹来源 | 说明 |
|------|-----------|:--------:|----------|------|
| `price` | `price_{route}_{code}.json` | 24h（交易时段 30s） | — | 股票/基金最新价、昨收（route=stock/fund_otc） |
| `index` | `index_{code}.json` | 24h（交易时段 30s） | — | 市场指数行情 |
| `news` | `news_{md5}.json` | 15 分钟 | 新闻源参数 + 关键词 | 多源新闻聚合结果 |
| `sector_flow` | `sector_flow_{fingerprint}.json` | 15 分钟 | A股+美股指数 | 行业资金流向排名 |
| `rank` | `fund_perf_{code}.json` | 24h | — | 基金同类排名+区间收益率 |
| `profit_forecast` | `profit_forecast_{fingerprint}.json` | 24h | A股+美股指数 | 机构盈利预测全量数据 |
| `hold` | `fund_hold_{code}.json` | 7 天 | — | 基金前 10 持仓明细 |
| `industry` | `industry_{code}.json` | 14 天 | — | 行业分类/概念板块 |
| `sentiment` | `sentiment_dragon_tiger.json` + `sentiment_ladder.json` | 1h | — | 市场情绪（龙虎榜 + 连板天梯，同花顺唯一源） |
| `report` | `report_datasink_index_{symbol}.json` + `report_datasink_sections_{doc_id}.json` + `report_cninfo_index_*` | 24h | — | 财报索引/章节清单（DataSinking 主源 + 巨潮备源）；symbol 级键，日频让**新披露最迟次日可见** |
| `report_doc` | `report_datasink_doc_{doc_id}_{section}.json`（备源 `report_cninfo_text_*`） | 30 天 | — | 财报正文（主源全文 / 备源 PDF 解析） |
| `fin_indicator` | `fin_indicator_{code}.json` + `fin_indicator_hist_{code}.json` | 24h | — | 结构化财务指标（akshare 主源 + 同花顺合并报表兜底）；同索引口径 |
| `dividend` | `dividend_{fingerprint}.json` | 7 天 | 持仓+穿透 A 股代码列表 | 股票历史分红汇总（公告不定期，周频兼顾可见性与请求量） |
| `benchmark` | `fund_benchmarks.json` | 30 天 | — | 业绩比较基准对照表 |

##### LLM 分析类

| 键名 | 文件名模式 | 默认 TTL | 指纹来源 | 说明 |
|------|-----------|:--------:|----------|------|
| `llm_expert_review` | `llm_expert_review_{fingerprint}.json` | 4h | 持仓汇总 + 分类计数 + 穿透 TOP10 + 持仓明细 | 智囊团深度复盘 |
| `llm_news_correlation` | `llm_news_item_{hash}.json`（逐条） | 4h | 标题前 80 字 + 持仓指纹 | 财经新闻热点与持仓关联分析 |
| `llm_global_macro` | `llm_global_macro_{fingerprint}.json` | 24h | A股/美股指数 + 持仓汇总 | 全球政经局势 |
| `llm_health_check` | `llm_health_check_{fingerprint}.json` | 4h | 持仓明细（排除行情波动） | 持仓体检报告 |
| `llm_penetration_deep` | `llm_penetration_deep_{fingerprint}.json` | 4h | 持仓明细（排除行情波动） | 穿透深度分析 |
| `llm_self_review` | `llm_self_review_{fingerprint}.json` | 24h | 四个分析模块的产出文本摘要 + 持仓/穿透摘要（**内容寻址**：产出不变即命中） | 生成后自检（⚗ 默认开） |
| `llm_holding_change` | `llm_holding_change_{fingerprint}.json` | 24h | 变动事实块 + 信号对账块 + 持仓摘要 + 申购限购约束块（**内容寻址**：进提示词必进指纹） | 持仓变动复盘归因（章本体 `holding_change_review` 默认关，开启后归因默认开） |
| `llm_debate_pro` | `llm_debate_pro_{fingerprint}.json` | 24h | 复用 expert_review 持仓指纹（排除行情波动） | 辩论白脸（实验功能） |
| `llm_debate_con` | `llm_debate_con_{fingerprint}.json` | 24h | 复用 expert_review 持仓指纹（排除行情波动） | 辩论黑脸（实验功能） |
| `llm_debate_synthesis` | `llm_debate_synthesis_{fingerprint}.json` | 24h | 复用 expert_review 持仓指纹（排除行情波动） | 辩论综合（实验功能） |

##### 基金深度分析类

| 键名 | 文件名模式 | 默认 TTL | 指纹来源 | 说明 |
|------|-----------|:--------:|----------|------|
| `fund_manager` | `fund_manager_{code}.json` + `fund_manager_snapshot.json` | 24h | — | 基金经理数据 + 快照（refresh 组） |
| `fund_concentration` | `fund_concentration_snapshot.json` | 30 天 | — | 集中度历史快照（精确键名，无分组） |
| `fund_style_snapshot` | `fund_style_snapshot.json` | 30 天 | — | 风格快照（精确键名，无分组） |
| `extended` | `extended_{code}.json` | 24h | — | 基金风格扩展数据（市值/PE），refresh 组 |

##### 系统类

| 键名 | 文件名模式 | 默认 TTL | 指纹来源 | 说明 |
|------|-----------|:--------:|----------|------|
| `tracking` | `holdings_tracking.json` | 30 天 | — | 持仓跟踪数据（精确键名，无指纹） |
| `calendar` | `trading_calendar.json` | 14 天 | — | A 股交易日历（精确键名，无指纹） |
| `bond_yield` | `bond_yield_rf` | 24h | — | 无风险利率（国债收益率；精确键名，无指纹） |

##### 历史走势类

| 键名 | 文件名模式 | 默认 TTL | 指纹来源 | 说明 |
|------|-----------|:--------:|----------|------|
| `history_stock` | `history_stock_{code}*.json` | 7 天 | — | 股票/ETF 历史 K 线（腾讯/新浪），历史走势计算输入 |
| `history_fund_otc` | `history_fund_otc_{code}*.json` | 30 天 | — | 场外基金历史净值（天天基金→东方财富备用链路），历史走势计算输入 |
| `history_index` | `history_index_{code}*.json` | 30 天 | — | 指数历史 K 线（腾讯/新浪），基准指数走势计算输入 |

> **指纹驱动失效：** 文件名中的 `{fingerprint}` 是输入数据的 MD5 哈希。持仓/指数数据变化时指纹自动改变，原缓存失效，无需手动清除。
> 
> **TTL 兜底：** 即使指纹未变，缓存文件仍有 TTL 兜底到期自动刷新，防止数据"永久有效"。

---

### N. 功能开关（features.json）

`data/config/features.json` 提供 **26 项功能开关**的运行时覆写（持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 呈现与交互 / 机制与质量 / 独立章节与回放 / 章节内选项八组，统一登记于功能开关注册表）。文件仅需列出需覆写的开关，未列出的保持代码内置默认值：

```json
{
  "metrics_enabled": false,
  "data_quality": false
}
```

> **文件不必须存在** — 全部使用代码默认值时无需此文件。首次在菜单 **[S]** / **[C]** 切换相关开关或手动创建后自动生效。
> **功能开关的入口**：TUI 菜单（章内内容组在 **[S]**，独立整章/关联产物/智囊团子项在 **[C]**）/ Web 配置面板（同一批条目，按五个意图域分区）/ CLI——一次性参数 `--experiment NAME`（只开全部实验项的简写，取值支持开关名、显示名或 `all`）与 `--feature NAME=VALUE`（**全部**功能开关、双向可控，取值写 `on`/`off`，**仅本次运行、不写盘**），持久化用 `config set <开关名> on|off`。详见 [CLI 命令行模式使用指南](how-to-use-cli-mode.md) §2 与 §14。同源同一注册表，新增开关自动各处可用。
>
> **报告会自述生成条件**：生成报告时，已启用的实验功能随产物一并标注——HTML 报告页脚、Excel「LLM API 用量」页签各列一行开关清单与「输出质量可能不稳定」提示；**LLM 分析章节关闭时该页签不生成**，清单改落到 Excel「投资分析汇总」页脚（`include_llm=False` 下的兜底落点），故无论 LLM 章节开关与否，Excel 产物上都能看到清单；实验开关全关时各处均不出现，报告与默认配置下的产物一致。报告导出流转后，读者据此即可判断手中的内容是否为非默认开关下的产物。章节/页签类开关转正（摘除实验身份）后不再进入该自述——其开合改由所在作用域组的章节可见性表达（默认关，开启即出章）。
> **注意**：features.json 支持 `//` 与 `/* */` 注释（读取时统一剥离；改—存后既有分类注释与项说明保留）。所有开关的默认值与完整说明见下表，或直接查看源码 `src/python/config/features.py` 的 `feature_switch_registry`（唯一登记点，每条含显示名/说明/分组/默认值/是否影响报告/实验身份）。
> **本表只收录「有消费者」的开关**——每一项在本程序内都确有一处读取其取值。**LLM 模块启停、基金深度分析、新闻源、历史走势、匿名化、启动缓存清理不在此文件**，它们各有归属配置：LLM 模块与基金深度分析走 `llm_settings.json` 的 `enabled_llm`（TUI 菜单 **[C]** LLM 章节块、Web 面板「LLM 分析章节」组），新闻源走 `config.json` 的 `news_sources`，历史走势与回撤走 `config.json` 的 `enable_history`，匿名化模式走 `config.json` 的 `anonymization.mode`（两侧面板均已上屏）。写在这些开关上的覆写不产生任何效果——程序启动时会在日志中告警列出，请据告警核对。

全部 26 项开关分八组（持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 呈现与交互 / 机制与质量 / 独立章节与回放 / 章节内选项）。**TUI 按「改了会怎样」分两个面板呈现**：前六组（章内内容）在 `[S]`；独立章节与回放、章节内选项在 `[C]`（编号与分块由注册表派生）。Web 配置面板与 CLI（`--feature` 一次性 / `config set` 持久化）覆盖全部功能开关；**章节显隐**另走 CLI `--chapter`（一次性）/ `config set enable_*`（持久化），TUI 与 Web 面板同源。

**持仓与交易（4 项；成本、申赎状态、成本收益与风险调整）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `cost_lots` | **false** | 汇总/市值/分类页签渲染成本分档 + XIRR + 分红累计（需持仓 Excel 含交易/分红流水） |
| `fund_purchase_limit` | **true** | 持仓明细与分类的 Excel 两区块（市值明细/分类汇总）末列与 HTML 两表（市值明细/持仓分类表）条件列追加「申购状态」（天天基金渠道口径，含日限/下一开放日；数据不可用时静默隐列）；同源供调仓 What-if 申购受限提示与全部 LLM 分析章的申购限购约束上下文（关＝三者同时失效，报告其余部分不受影响） |
| `cost_position` | **true** | 持仓明细与分类的 Excel 两区块末列追加「成本区间位置」两列（每份成本相对近 20/260 交易日价格区间百分位，≈1 追涨嫌疑；复用既有行情历史链，行情缺失时静默隐列，不阻断报告） |
| `risk_adjusted_excess` | **false** | 「组合历史走势与回撤」章新增第五区块「风险调整超额」：逐基准年化 IR / 跟踪误差 / 几何年化超额 + 近 12/24 个完整月跑赢胜率 + 滚动 250 日超额折线（HTML）与序列（Excel）；IR/TE 需 ≥60 对齐交易日、滚动需 ≥250，样本不足逐项「数据不足」占位；未配置业绩基准时整块「数据不可用」占位（开启会新增子块扩展窗取数 `max(lookback, 365)` 交易日，与 `crisis_replay` 共享一次取数） |

**市场与估值（4 项；温度、估值分位、景气度与危机回放）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `valuation_percentile` | **false** | 「资产穿透TOP10」章渲染估值分位列（真实历史 PE/PB 分位，无覆盖回落价格分位代理） |
| `market_temperature` | **true** | 「投资分析汇总」章渲染市场温度刻度行（三因子合成；数据不足时该行静默省略）；温度行下附**计算逻辑**（第一因子分位 50% + 20日均线偏离 30% + 20日年化波动率 20%，波动率反向：越波动越冷）与**分级标准**（低估＜30 / 合理 30~70 / 高估＞70，边界值归合理档）两行说明，文案由计算层常量单源派生 |
| `crisis_replay` | **false** | 「危机区间标注」区块升级为双层回放：组合层统计子块扩展窗内静态危机区间的组合收益/回撤（窗外行标「组合窗口外」），指数层覆盖全部静态区间（2015/2018/2020/2022/2025，指数长窗日线按静态表最早起点动态取数、封顶 3650 交易日）给出指数区间收益与区间最大回撤；未配置业绩基准时指数层静默缺席（图下说明标注原因）、组合层照常 |
| `prosperity_framework` | **true** | 景气度框架诊断（六维评分卡评估组合与景气度框架的契合度：景气方向/通胀属性、ROE 低位弹性、全球视野/中国比较优势、流动性、集中度与周期拼接、业绩与回撤印证；数据缺失维度标「需核实」且**不计分**；其中 ROE 维的基金层值按重仓股加权**推演**、流动性维的场外值按类型**默认档**估算，两者均上屏「非实测/推演」标识；行动建议章内嵌块；实验转正，评分口径不变） |

**基金与风格（3 项；候选比较、行业 Beta 与因子目录）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `factor_catalog` | **false** | 因子目录（25 因子五来源族横截面信号入账 + 「风格与因子分析」章内区块四：池内逐因子最新横截面/中性点相对/可算码数，不可算因子带原因；信号每日单条快照入 `signal_ledger`（类型「因子目录」），横截面 = 池内各码最新有效因子值均值（有效码数 <3 不出值）；目录冻结于 `schemas/factor_catalog.py`（与门槛判定书同源），估值/财务字段不可得时逐因子降级） |
| `industry_beta` | **false** | 「风格与因子分析」章渲染行业 Beta 子表（行业暴露 + β/t 值/显著性/相关性） |
| `candidate_compare` | **false** | 「基金业绩分析」章渲染候选基金横向比较子表（候选来自 `comparison_candidates`） |

**事件与摘要（4 项；事件窗、情绪热点、数据质量与本期要点）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `event_window_impact` | **false** | 财经新闻章内区块「事件窗量化对照」（区块级可见性，不占章号）：当日/近期财经新闻按品种关键词匹配 → 事件日映射交易日 → ±5 交易日窗内标的/宽基超额收益 vs 文本极性方向比对（一致/分歧/中性不判）；行情轴右端不足 5 个交易日时按实际可用日截断并标注「后窗未满」（盘中运行常态），行情/基准缺失或事件日后无可用交易日才逐事件降级；新闻为空或全无命中时区块占位；分歧例（文本判利好而窗口方向下等）随同源口径进全部 LLM 分析章统一提示词附录（文本判定复用新闻 LLM 关联分析极性，本模块不做文本判定） |
| `data_quality` | **true** | 「数据源可用性矩阵」章渲染数据质量仪表盘区块（覆盖/时效/降级状态） |
| `market_sentiment` | **false** | 行动建议章内嵌块「市场情绪与持仓热点」：持仓/穿透标的命中当日龙虎榜或连板梯队的事件行（需同花顺 key；**只显示命中项，零命中时写市场概览与「当日无持仓/穿透标的命中」说明行——区块仍渲染，分得清「无事件」与「取数失败」**；排查是否已取到数据：可用性矩阵的「市场情绪」行与「命中源（本次取数）」列、`logs/app.log` 的 `[market_sentiment] 命中 N 条`，`N=0` 表示已取到但当日无事件行） |
| `summary_highlights` | **false** | 「投资分析汇总」首屏新增「本期要点」执行摘要卡：关键指标环比行（总市值环比金额与比率 / 总收益率环比百分点 / 持仓数环比（新增-清仓） / 集中度 HHI 环比（行级降级，演进开关关闭时省略该行）） + 本期关键变化 Top 5（新增/清仓/加减仓合并按市值变化绝对值降序，超上限写「等共 N 项变动」提示）；取数快照 diff 单源派生（零新增取数零计算）；无上期快照时整块隐藏不写占位 |

**呈现与交互（2 项；图表轴值与报告页追问）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `report_qa` | **false** | 报告页试点验证中；报告对话式追问（读者在 HTML 报告页内对**本期报告**发起会话式提问：上下文只读当期报告、零新增取数；会话轮数与输入 token 双上限显式报错，用量独立记账不进报告 LLM 用量页签；回答附「基于报告生成时数据」尾注与事实核对警示） |
| `metrics_enabled` | **true** | 量化指标显示（原 `metrics_sharpe`/`metrics_calmar`/`metrics_hhi`/`metrics_winrate`/`metrics_turnover`/`metrics_risk_contribution`/`metrics_beta` 七项已并入）：指标始终全量计算，关闭即量化指标雷达图各轴显示 N/A（含降级 3 轴）、断路器暂停该组指标的失败计数；智囊团复盘指标表不受影响 |

**机制与质量（3 项；提示词注入与输出质量分级）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `decision_reflection` | **false** | 验证死线执行中；决策跨期反思闭环（登记决策 → 真实行情结算命中率 → 教训回灌专家复盘提示词；行动建议章内嵌「历史决策复盘」块） |
| `deterministic_signal` | **true** | 确定性信号模块（**实时注入 + 跨期沉淀双面**：①市场温度/估值分位/尾部风险预消化为 `信号：…` 方向行注入智囊团复盘与持仓体检提示词，减少模型读裸数值的误判；②同一批确定性评级（含风格因子/再平衡超限）沉淀为 `data/state/signal_ledger.jsonl` 账本，每条附**实时/非实时**来源标签，统计与摘要**默认只算实时记录**防降级行情冒充真实战绩，同日重跑不重复入账，摘要回灌提示词；`doctor` 自检上屏账本概览与各实验功能启用次数统计）。**默认开启**（读侧注入 + 跨期沉淀双面）；无可用信号时静默跳过、缓存键逐字节不变。features.json 写入的开关名以现行注册表为准 |
| `module_quality_gate` | **true** | 模块级质量分级（对 4 个 LLM 模块输出按完整性/篇幅评 A~F，低评级中「内容在但存在缺陷」者随内容头部注入 `【内容质量提示】` 横幅——只标注、不阻断、不重试、不写回缓存）。**默认开启**——纯只读分级，A/B 级健康输出零噪音 |

**独立章节与回放（4 项；新增整页签或多期回放）**——前 3 项在 `[C]`「默认关闭的整章」块，`whatif_trade_cost` 在 `[C]`「关联产物」块（仅调仓模拟报告）：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `rebalance_schedule_replay` | **false** | 独立章「调仓纪律回放」（type=`schedule_replay`）：在历史窗口逐期执行月度定期/阈值偏离纪律（含成本两态）与买入持有对比——双线图（纪律回放 vs 买入持有净值）+ 指标对照表 + 规则 A 逐期调仓与成本表；回放不足（窗口跨度/净值日/行情缺口验收失败）时章节占位；回放结论经 `prompt_block` 随同源口径进全部 LLM 分析章统一提示词附录（只读引用，不改写报告数值） |
| `holding_change_review` | **false** | 独立章「持仓变动复盘」（type=`holding_change`）：本地滚动快照差分的变动事件清单（**区间净额推断、非逐笔**）+ 变动频率/结构计数/区间贡献分解 + 决策账本意图对账（只读）+ 账户结构重排标注（同日跨品种清仓次日同名新增按账户/数据结构变更解读）；LLM 归因块随契约同页展示（由 `llm_settings.json → enabled_llm.holding_change` 独立控制，失败时隐藏）。快照准入未过（观察期 <12 或事件 <10）时章节占位 |
| `whatif_trade_cost` | **false** | 调仓 What-if「交易成本对比」（`调仓模拟.xlsx` 交易成本对比页签 + HTML⑧区）：回放计入申赎成本（申购按金额分档、赎回按 FIFO 快照批次的交易日持有期阶梯加权，费率 F10/全量表/配置兑底三级可得）+ 生效日 t0 一次性扣费的成本前/后收益差 + 业绩基准三线参照（配置覆盖→持仓基准文本→宽基默认映射）；费率未知/场内品种显式标注**不出成本后数字**；无回测时仅出成本块 |
| `stock_fundamentals` | **false** | 持仓基本面章两块同开同关：区块① 个股基本面（指标/质量档/趋势/当前 PE·PB，需数据底座就绪）+ 区块② A 股标的财报章节摘要（需 DataSinking key）；原两开关并入本单一开关 |

**章节内选项（2 项；由 [C] 作为章节子项渲染）**：

| 开关名 | 默认值 | 说明 |
|:--|:--|:--|
| `llm_debate_procon` | **false** | 辩论-正反辩论（三段式：白脸→黑脸→综合；**集中度问答段已内建**——单品种占比超阈值时白脸/黑脸/综合各追加集中度量化评估段，阈值由 `debate.concentration_qa.threshold` 控制，不再单独设开关。三段式换调用次数，故实验转正后默认保持关） |
| `llm_debate_conditional` | **true** | 辩论-条件推理（情景化分析：涨/跌/震荡；与正反辩论相邻，保持辩论开关同组可查。**默认开启**——情景段与既有输出在同一次调用内产出，不换调用次数） |


> 以上 26 项为**全部**功能开关清单（默认值与代码 `features.py::feature_switch_registry` 一致）。features.json 仅需列出需覆写的开关，未列出的保持默认值。
> 该文件不包含敏感信息，可安全纳入版本控制。

---

## 配置文件随版本更新

配置文件里的**键与注释只在生成那一刻写入**，之后文件就冻结——升级程序不会改动你手上那份文件。如果代码侧调了菜单键、补了新键或改写了说明，旧文件里的注释会与当前程序对不上：注释里提到的菜单字母可能已不是当前键位，照着注释找就会找不到，新功能的开关也不会出现在文件里。

**系统自检会提示**：`[D]` → `[T]`（或 CLI `doctor`）的「配置」组有一项「配置说明时效」。

| 提示内容 | 含义 | 怎么处理 |
|---|---|---|
| `配置文件落后于当前版本：config.json 缺 N 个新键（…）` | 新功能的配置项在你文件里根本不存在（功能仍按默认值运行） | 按下文重生成，并把自定义值回填 |
| `注释落后于当前版本（不影响运行）：llm_providers.json 缺 N 条说明` | 键齐全但说明是旧版，可能指向已改名的菜单键/旧口径 | 可忽略；想对齐就重生成后回填自定义值 |

**重生成方法**：备份 → 删除目标文件 → 重新运行程序（或 CLI `config init`），即按当前模板重新生成。注意不同文件的自定义值处理方式不同：

| 文件 | 重启后处理 | 重生成前必做 |
|---|---|---|
| `config.json` | 回填你改过的值（如 `report_section_order`、`batch` 并发数、`enable_*`） | 从备份中抄回这些项 |
| `llm_settings.json` | 回填模块开关/参数（区块结构升级时需对照注释） | 抄回 `modules` 等定制段 |
| `llm_providers.json` | 回填你的多链线路（`providers[]` 与 `priority`） | 抄回完整 `providers` 数组 |
| `features.json` | 重生成只会保留**与默认值不同**的项，并自动带上级注释（开关显示名 + 一句话说明，取自功能开关注册表） | 想保留的开关先记下 |
| `logger.json` | 回填日志级别/轮转/查看器设置 | 抄回你调过的项 |

以上都是你自己机器上的运行时配置文件（`data/config/`，不进版本库）；程序每次启动都会重新校验，改坏了最多回落默认值，不会阻断启动。

---

**相关手册**：[← 快速开始](how-to-start.md) · [配置字段详解 →](how-to-config-fields.md) · [LLM 配置指引](how-to-config-llm.md) · [手册总索引](README.md)

