# 投资复盘助手 — 技术设计
> 文档版本：0.16.1-dev

## 目录

- [1. 总体技术架构与概要设计](#1-总体技术架构与概要设计)
  - [1.1 系统分层](#11-系统分层)
  - [1.2 核心数据流](#12-核心数据流)
  - [1.3 模块职责总览](#13-模块职责总览)
  - [1.4 概要设计 — 核心架构决策](#14-概要设计--核心架构决策)
  - [1.5 交互渠道体系（CLI / TUI / Web）](#15-交互渠道体系cli--tui--web)
  - [1.6 TUI 渠道详细设计（主要渠道）](#16-tui-渠道详细设计主要渠道)
  - [1.7 CLI 渠道详细设计](#17-cli-渠道详细设计)
  - [1.8 Web 渠道详细设计](#18-web-渠道详细设计)
- [2. 数据获取层详细设计](#2-数据获取层详细设计)
  - [2.1 Provider Chain 路由与 fallback](#21-provider-chain-路由与-fallback)
  - [2.2 三层熔断架构](#22-三层熔断架构)
  - [2.3 Fetcher 调度架构](#23-fetcher-调度架构)
  - [2.4 关键机制](#24-关键机制)
  - [2.5 数据源适配契约（内置，不可关闭）](#25-数据源适配契约内置不可关闭)
  - [2.6 数据源记录-回放（测试基建，无开关）](#26-数据源记录-回放测试基建无开关)
  - [2.7 数据源凭据就绪指引（内置，不可关闭）](#27-数据源凭据就绪指引内置不可关闭)
- [3. 缓存层详细设计](#3-缓存层详细设计)
  - [3.1 子模块结构](#31-子模块结构)
  - [3.2 核心接口与 TTL 分辨率](#32-核心接口与-ttl-分辨率)
  - [3.3 原子写入与并发安全](#33-原子写入与并发安全)
  - [3.4 指纹驱动失效机制](#34-指纹驱动失效机制)
  - [3.5 缓存分组](#35-缓存分组)
  - [3.6 缓存操作共享层](#36-缓存操作共享层)
- [4. 报告生成层详细设计](#4-报告生成层详细设计)
  - [4.1 管线总览](#41-管线总览)
  - [4.2 报告编排器](#42-报告编排器)
  - [4.3 Excel 管线](#43-excel-管线)
  - [4.4 HTML 管线](#44-html-管线)
  - [4.5 章节可见性两层模型](#45-章节可见性两层模型)
  - [4.6 报告序号可配置](#46-报告序号可配置)
  - [4.7 组合历史走势计算算法](#47-组合历史走势计算算法)
  - [4.8 基金深度分析](#48-基金深度分析)
  - [4.9 资产穿透 TOP10](#49-资产穿透-top10)
  - [4.10 财经新闻热点与持仓关联分析](#410-财经新闻热点与持仓关联分析)
  - [4.11 数据降级治理体系](#411-数据降级治理体系)
  - [4.12 组合演进（多快照趋势）](#412-组合演进多快照趋势)
  - [4.13 调仓 What-if 模拟](#413-调仓-what-if-模拟)
  - [4.14 HTML 暗色模式](#414-html-暗色模式)
  - [4.15 决策头结构化与决策词归一解析](#415-决策头结构化与决策词归一解析)
  - [4.16 确定性数值信号沉淀与实时/非实时标签纪律](#416-确定性数值信号沉淀与实时非实时标签纪律)
  - [4.17 健壮性三件套（数值归一防线 / 失败原因可读 / 系统自检）](#417-健壮性三件套数值归一防线--失败原因可读--系统自检)
  - [4.18 决策跨期反思闭环](#418-决策跨期反思闭环)
  - [4.19 持仓基本面（财务指标 + 持仓个股财报摘要）](#419-持仓基本面财务指标--持仓个股财报摘要一章两区块)
  - [4.20 景气度框架诊断（常规功能 prosperity_framework）](#420-景气度框架诊断常规功能-prosperity_framework)
  - [4.21 正文大块默认折叠（HTML 报告）](#421-正文大块默认折叠html-报告)
  - [4.22 章节-区块矩阵](#422-章节-区块矩阵)
  - [4.23 测试域归属与门禁纳入纪律](#423-测试域归属与门禁纳入纪律)
- [5. LLM 集成层（概要设计）](#5-llm-集成层概要设计)
  - [5.1 架构总览](#51-架构总览)
  - [5.2 调用链概览](#52-调用链概览)
  - [5.3 模块清单](#53-模块清单)
  - [5.4 多 Provider 链模式](#54-多-provider-链模式)
  - [5.5 关键机制](#55-关键机制)
- [6. 辅助模块详细设计](#6-辅助模块详细设计)
  - [6.1 配置管理](#61-配置管理)
  - [6.2 中央注册表](#62-中央注册表)
  - [6.3 市场时段判断](#63-市场时段判断)
  - [6.4 持仓读取与列校验](#64-持仓读取与列校验)
  - [6.5 代码类型判定中心化](#65-代码类型判定中心化)
  - [6.6 HTTP 客户端统一](#66-http-客户端统一)
  - [6.7 功能语义命名表](#67-功能语义命名表)
  - [6.8 报告对话式追问](#68-报告对话式追问)
  - [6.9 实验项生命周期表](#69-实验项生命周期表)
- [7. 模块间依赖关系](#7-模块间依赖关系)
- [8. 架构设计约束](#8-架构设计约束)
  - [8.1 数据获取层约束](#81-数据获取层约束)
  - [8.2 缓存层约束](#82-缓存层约束)
  - [8.3 报告层约束](#83-报告层约束)
  - [8.4 LLM 集成层约束](#84-llm-集成层约束)
  - [8.5 基础设施约束](#85-基础设施约束)
  - [8.6 测试约束](#86-测试约束)
- [附录](#附录)
  - [附录 A：目录结构](#附录-a目录结构)
  - [附录 B：数据源一览](#附录-b数据源一览)
  - [附录 C：缓存 TTL 明细](#附录-c缓存-ttl-明细)
  - [附录 D：降级层级与阈值定义](#附录-d降级层级与阈值定义)
  - [附录 E：线程池分布](#附录-e线程池分布)
  - [附录 F：指标降级依赖矩阵](#附录-f指标降级依赖矩阵)
  - [附录 G：报告生成降级路径矩阵](#附录-g报告生成降级路径矩阵)
  - [附录 H：pipeline_data Schema 定义](#附录-hpipeline_data-schema-定义)
  - [附录 I：配置文件矩阵](#附录-i配置文件矩阵)

---

## 1. 总体技术架构与概要设计

### 1.1 系统分层

系统按数据流向分为五层，由贯穿层串联。整体架构如下：

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                        输入层                                      │
  │             持仓 xlsx ──→ reader.py ──→ models.Holding             │
  └──────────────────────────────────┬────────────────────────────────┘
                                     │ holdings
                                     ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │                       数据获取层 (fetcher/)                        │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
  │  │ price.py │ │ index.py │ │ fund.py  │ │industry  │ │ 其他    │ │
  │  │腾讯→新浪  │ │ 指数直调  │ │天天解析  │ │ push2    │ │ ...    │ │
  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
  │       │            │            │            │            │       │
  │  Provider Chain 路由+fallback+熔断器 (core/provider_registry.py) │
  └──────────────────────────────────┬────────────────────────────────┘
                                     │
                                     ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │                        缓存层 (cache/)                              │
  │        泛用 JSON KV · TTL · 指纹失效 · 分组 · 原子写入             │
  │        大文件 gzip · 路径安全 · 文件损坏自恢复                      │
  │        缓存操作共享层 (operations.py — 三渠道共用)                 │
  └──────────────────────────────────┬────────────────────────────────┘
                                     │
                                     ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │                      报告编排层 (orchestrator.py)                  │
  │  数据准备 → 快照 → 历史走势 → LLM+新闻并取 → 双管线  │
  │              内部管理 orch_prep / orch_llm_news 线程池             │
  └──────────────────────────────────┬────────────────────────────────┘
                                     │ info 字典
                                     ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │                        报告生成层 (report/)                         │
  │  ┌─────────────────────────┐   ┌───────────────────────────────┐  │
  │  │   Excel 管线            │   │   HTML 管线                   │  │
  │  │   openpyxl              │   │   Jinja2 模板                 │  │
  │  │   双端共享 data_status   │   │   CSS order 视觉排序          │  │
  │  └─────────────────────────┘   └───────────────────────────────┘  │
  └───────────────────────────────────────────────────────────────────┘
```

**三入口：TUI、CLI 与 Web**

| 入口 | 通道 | 入口文件 | 用户交互层 | 业务逻辑层 | 进度报告 |
|:-----|:-----|:---------|:----------|:----------|:---------|
| TUI | 交互菜单 | `tui/tui.py` | `tui/tui_menu.py` + `tui/handlers_*.py` | `report/orchestrator.py` + `cache/operations.py` | `TuiProgressReporter` |
| CLI | 命令行参数 | `cli/cli.py` | argparse（不经过 tui/handlers_*） | `report/orchestrator.py` + `cache/operations.py` | `CliProgressReporter` |
| Web | 浏览器界面 | `web/server.py` | `web/handlers.py` + `web/run_generation.py` + `web/upload.py` + `web/progress.py` + `web/runs.py` | `report/orchestrator.py` + `cache/operations.py` | `WebProgressReporter` |

**共享模块**（三种入口均直接使用）：

| 共享层 | 位置 | 用途 |
|:-------|:-----|:------|
| 报告编排器 | `report/orchestrator.py` | 三路径报告生成（basic/both/full） |
| 缓存操作 | `cache/operations.py` | 缓存刷新/清理/统计 |
| 进度接口 | `report/progress.py` | `ProgressReporter` 基类 |
| 持仓读取 | `core/reader.py` | xlsx 解析 |
| 配置管理 | `config/` | 三文件分层配置 |

**分层差异**：TUI 的 `tui/handlers_report.py` / `tui/handlers_cache.py` 是极薄包装层（仅保留交互逻辑如文件选择、结果格式化），CLI 通过 argparse 直接调用共享层，不经过 handlers_*；Web 通过 `web/handlers.py` API 路由与 `web/runs.py` 单 worker 串行队列调用共享层，进度经 `web/progress.py` 的 WebProgressReporter 事件缓冲输出。三种入口共用同一套业务逻辑——三渠道的**体系化视角**（渠道定位/统一架构模式/差异对照/并发与产物治理）见 [§1.5](#15-交互渠道体系cli--tui--web)，各渠道实现细节分别见 [§1.6 TUI](#16-tui-渠道详细设计主要渠道)（主要渠道）/ [§1.7 CLI](#17-cli-渠道详细设计) / [§1.8 Web](#18-web-渠道详细设计)。

**贯穿层**：`config/` · `core/registry.py` · `core/provider_registry.py` · `core/code_utils.py` · `core/market_hours.py` · `core/perf.py`

**关键分层原则**：
- 每一层只能依赖其下层和贯穿层，禁止反向依赖
- 数据获取层通过 Provider Chain 解耦数据源，新增数据源无需修改调用方
- 缓存层作为数据获取层和报告层之间的缓冲，提供 TTL、指纹和分组管理
- 报告编排层统筹数据准备和双管线生成，消除 TUI、CLI 与 Web 间的逻辑重复
- 贯穿层提供全局共享的基础设施（配置、注册表、熔断器、代码类型判定）

### 1.2 核心数据流

从持仓文件到报告产出的完整数据流转：

```
持仓 xlsx
    │
    ▼
core/reader.py ──→ core/models.Holding / DetailRow（持仓数据模型）
    │
    ├─────────── 获取层（并行）──────────────┐
    │                                        │
    ▼                                        ▼
fetcher/price.py ──→ cache/     fetcher/fund.py ──→ cache/
fetcher/index.py ──→ cache/     fetcher/industry.py ──→ cache/
providers/news_*.py ──→ cache/  fetcher/fund_manager.py ──→ cache/
llm/generators_orchestrator.py ──→ cache/（可选）
    │                                        │
    └─────────────────┬──────────────────────┘
                      │
                      ▼
          报告编排层（orchestrator.py）
              合并为 info 字典
    {
      market_data:     {code: {price, yesterday_close, ...}}
      index_data:      {index_code: {price, change_pct, ...}}
      fund_data:       {code: {rank, holdings, benchmarks, ...}}
      penetration_data:{top10, classification, sector, ...}
      news_data:       [{title, source, summary, correlation, ...}]
      llm_data:        {global_macro, expert_review, health_check, ...}
      history_data:    {timeseries, drawdown, return_pct, benchmarks, ...}
      ...
    }
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
   Excel 管线    HTML 管线    (或两者同时)
   .xlsx 报告    .html 报告
```

**报告类型与对应路径**：

| 报告类型 | 菜单 | 数据准备深度 | 输出格式 | LLM |
|:---------|:----|:------------|:---------|:----|
| `basic` | E | 行情+指数（无穿透/分类/新闻） | Excel 单格式 | ❌ |
| `both` | B | 轻量行情 + 快照 + 历史走势（条件） | HTML + Excel | ❌ |
| `full` | L | 完整行情 + 穿透 + 快照 + 历史走势 + 资金流向 | HTML + Excel | ✅ |

> 三种报告类型同样可由 CLI `--type basic/both/full` 与 Web 报告格式下拉（基础/标准/完整）触发，Web 侧可选「获取历史走势」「强制 LLM」两个选项（勾选强制 LLM 后可展开模块多选，默认全选=全量，子集经 `llm_modules` 参数下传）。

### 1.3 模块职责总览

| 层次 | 模块 | 职责 | 文件 |
|:-----|:-----|:------|:-----|
| **用户交互** | TUI 主循环 | 菜单编排、用户交互流 | `tui/tui.py` / `tui/tui_menu.py` |
| **用户交互** | CLI 命令行 | argparse 解析、共享层直调、定时任务驱动 | `cli/cli.py` |
| **用户交互** | Handler 命令 | TUI 命令 → 委托编排层或共享层 | `tui/handlers_*.py` |
| **用户交互** | 进度报告 | ProgressReporter 解耦进度输出 | `report/progress.py` |
| **用户交互** | CLI 进度报告 | CliProgressReporter（logging 输出 / verbose stderr） | `report/cli_progress.py` |
| **用户交互** | Web 服务层 | Flask 工厂/路由、生成执行体、单 worker 串行队列、上传安全、报告格式与选项选择 | `web/server.py` / `web/app.py` / `web/handlers.py` / `web/run_generation.py` / `web/upload.py` / `web/runs.py` |
| **用户交互** | Web 进度报告 | WebProgressReporter（事件缓冲、进度查询） | `web/progress.py` |
| **输入** | 持仓读取 | xlsx 解析、列校验、多账户 | `core/reader.py` |
| **配置** | 配置管理层 | 三文件分层配置 | `config/` |
| **注册** | 中央注册表 | 数据模块 + 报告模块注册（两域子模块下沉，门面单入口再导出） | `core/data_registry.py` + `core/report_section_registry.py`（`core/registry.py` 门面） |
| **数据获取** | 数据源注册中心 | 熔断器、会话缓存、策略、审计 | `core/provider_registry.py` |
| **数据获取** | Fetcher 调度 | Provider Chain 路由、数据获取 | `fetcher/price.py` 等 |
| **数据获取** | 数据源 Provider | 外部 API 封装 | `providers/*.py` |
| **缓存** | 缓存引擎 | 泛用 JSON KV、TTL、指纹、分组 | `cache/` |
| **缓存** | 缓存操作共享层 | 三渠道共用的业务级缓存操作 | `cache/operations.py` |
| **编排** | 报告编排器 | 数据准备 → 管线编排 | `report/orchestrator.py` |
| **报告** | Excel 管线 | openpyxl 写入 | `report/excel_generator.py` |
| **报告** | HTML 管线 | Jinja2 模板渲染 | `report/html_writer.py` |
| **报告** | 内容模块 | 各页签写入器 | `report/*.py` |
| **LLM** | 智能分析 | 三类协议（claude / openai / gemini）调用与厂商模型路由（含 DeepSeek、Kimi 等走兼容端点的第三方厂商）、Provider Chain 策略路由、Multi-Provider 多链切换、fingerprint 指纹缓存、Extended Thinking、骨架流程、并行编排、费用估算 | `llm/` |
| **贯穿** | 代码类型判定 | 资产识别原语 | `core/code_utils.py` |
| **贯穿** | 交易时段判断 | A 股时段、午间休市 | `core/market_hours.py` |
| **贯穿** | HTTP 客户端 | 统一工厂 | `core/http_client.py` |
| **贯穿** | 性能收集 | PerfCollector 三路径计时 + 子阶段 `breakdown`（数据准备：行情与明细/指数获取/穿透/风格与因子/覆盖与新鲜度/估值与温度/财报摘要与指标/申购与成本位置/明细装配与建议；LLM+新闻：新闻源抓取/去重与关联/锚点维护/事件窗装配/LLM 模块）+ perf_history.jsonl 持久化 + 数据源健康历史聚合 `summarize_health_history()`；`counters` 除 warnings/errors 外含**事实校验自动修正计数**（`fact_fix_total` / `fact_fix_numeric` / `fact_fix_code` / `fact_fix:<模块>`，由 `llm/fact_checker` 线程安全累加、报告层 LLM 阶段前清零后汇入——修正次数是模型口径偏差的直接信号，单次只进日志时无法跨期对拍）；另有 `llm_thinking_wait_ms`（thinking 并发槽串行等待累计——默认上限已为 2；配回 1 时据此量化串行代价） | `core/perf.py` + `llm/fact_checker/_corrections.py` |
| **贯穿** | 运行一致性 | 生成中断收口（KeyboardInterrupt 安全落点：临时产物清扫 + `status=interrupted` 运行记录 + 已写盘/已丢弃明细）+ HTML/Excel 产物原子落盘登记 | `report/run_integrity.py` |
| **贯穿** | 日志可视化 | 结构化日志读取（parse_log/tail_log/read_log），CLI/TUI/Web 三端共享 | `core/log_reader.py` |
| **贯穿** | 系统自检 | 运行环境/配置/目录/日志与缓存/功能开关/数据源适配/数据源凭据/数据源八组一次性盘点（恒上屏，无开关），CLI/TUI/Web 三端共享；自身永不抛异常、零重依赖 | `core/doctor.py` |
| **贯穿** | 数值归一 | 非有限值（NaN/±inf）防线收敛点：`safe_num` / `strict_num` / `finite_or` / `is_finite_number`；纯 stdlib、零项目内依赖，providers/analysis/report 任一侧可安全导入 | `core/num_utils.py` |
| **贯穿** | 文本安全边界 | 孤立代理项净化（合法代理对折叠为星平面字符、孤立项 → U+FFFD）：stdin 的 `surrogateescape` 与 JSON `\udXXX` 产物在进入 LLM 请求体 / 响应正文 / 追问输入前统一过关，避免 `UnicodeEncodeError` 被误分类为 provider 故障 | `core/text_safety.py` |
| **贯穿** | 任务完成通知 | CLI/Web 报告收尾按 `notify` 配置分发 webhook/邮件/桌面三通道（失败必发、成功需 `on_success`；尽力而为：单通道失败隔离、永不改退出码、未配置静默跳过；降级摘要单源 `report/data_status.degradation_summary()`） | `core/completion_notify.py` |

### 1.4 概要设计 — 核心架构决策

以下五项跨模块架构决策贯穿系统全局，是所有新增/修改代码的设计基础。

#### 1.4.1 代码类型判定中心化

**决策**：所有资产代码类型判定集中到 `src/python/core/code_utils.py`，禁止任何模块自行实现判定逻辑。

**动机**：系统 20+ 处需要判断资产类型（A 股/ETF/基金/QDII/港股/债券等），分散判定导致代码前缀知识散落、新增资产类型时需全局搜索替换。

**原语体系**（详见 [§6.5](#65-代码类型判定中心化)）：

```
判定维度：
  代码前缀 → is_a_share_code() / is_exchange_fund_code() / is_hk_stock_code() / ...
  名称关键词 → is_qdii_by_name() / is_etf_by_name() / is_bond_fund_by_name() / ...
  复合判定 → is_otc_fund_by_name(name, code) / is_etf_by_name_or_code() / ...
```

#### 1.4.2 Provider Chain 必经

**决策**：大多数数据获取必须通过 `fetcher/chain.py` 的 `fetch_with_fallback()`，不得直接调用 Provider 函数。

**动机**：跳过 Chain 直接调用 Provider 会导致三方面失效：
1. **熔断器不被激活** — 故障后无冷却恢复
2. **fallback 链路断路** — Provider 失败时不会自动递补
3. **日志审计缺失** — 故障记录无法集中追踪

**唯一例外**：`fetcher/index.py` 直调 Provider（双链路 fallback 硬编码在模块内），原因是指数数据不适用熔断器的单股票级粒度。

#### 1.4.3 缓存统一管理

**决策**：所有持久化缓存必须通过 `cache/` 子包的 `get()`/`set()` 接口读写，写入必须使用 `tempfile.mkstemp` + `os.replace` 原子写入模式。

**动机**：直接操作 `data/cache/` 文件系统导致 TTL 失效、分组清理遗漏、路径穿越等隐患。直接覆写文件在断电/崩溃时产生半写损坏文件。

#### 1.4.4 报告配置化

**决策**：报告 19 个模块的序号、显示名称、章节可见性由配置驱动，消除硬编码。渲染期数据通过模板 context 传递，禁止写入模块级全局变量。

**两层可见性模型 + 章级维度**：

```
section_visible = board_enabled(section.type) AND data_available(section.data_flag) AND NOT module_disabled(section.key)
```

| 层级 | 含义 | 来源 |
|:-----|:------|:------|
| board 层 | 用户配置的章节开关 | `config.json`（`enable_fund_deep_analysis`/`enable_news`/`enable_history`/`enable_portfolio_evolution`） |
| data 层 | 运行时数据可用性 | 各子模块返回值非 None 判定 |
| 章级 | LLM 分析章逐模块启停 | `llm_settings.json → enabled_llm.<key>`（禁用的分析章整章隐藏而非显示「待生成」占位；集合 `core.registry.LLM_MODULE_GATED_SECTIONS` 单一来源，HTML/Excel 两端同调 `llm.skeleton.get_llm_chapter_disabled()` 同配置同逻辑推导；新闻关联（LLM 仅二次增强）与 API 用量章不入集合） |

#### 1.4.5 数据降级治理体系

**决策**：数据获取过程中任何环节失败都应静默降级而非中断报告生成，降级状态在报告中可视化呈现。

```
                          ┌──────────────────────┐
                          │   数据获取请求         │
                          ▼                      │
              Provider Chain 遍历                │
              ↓ 成功 → 返回最新数据               │
              ↓ 失败 → 递补下一 Provider          │
                          ▼                      │
              ┌──────────────────────┐           │
              │ 全链均失败？          │           │
              └──────┬───────┬───────┘           │
                    Yes       No                 │
                     ▼                           │
              ┌──────────────────────┐           │
              │ 尝试过期缓存降级      │──继续遍历→─┘
              │ (CACHE_WEEKLY=7天)   │
              └──────┬───────┬───────┘
                  有缓存      无缓存
                     ▼           ▼
              ┌──────────┐ ┌──────────────┐
              │返回旧数据 │ │抛异常         │
              │+降级标记  │ │调用方写入占位 │
              └──────────┘ └──────────────┘
```

**双重降级系统**：

| 系统 | 层级 | 管什么 | 粒度 | 恢复方式 |
|:-----|:-----|:-------|:-----|:---------|
| DataSourceRegistry | 熔断层（HTTP 级） | 这个 Provider 能不能调用 | per-provider | 指数退避冷却（60s→300s→900s→3600s） |
| DegradationTracker | 降级决策层（数据质量级） | 这批数据能不能信任 | per-source | 跨会话持久化 |

[↑ 回到顶部](#目录)

---

### 1.5 交互渠道体系（CLI / TUI / Web）

系统提供 **CLI / TUI / Web 三种交互渠道**，共用同一套业务管线。三渠道不是三套独立实现，而是同一共享层的三种**薄入口外壳**——差异仅停留在「交互范式、参数传递、进度传输、并发模型、产物治理」五个维度，业务逻辑（数据获取 → 缓存 → 报告编排 → 双管线生成）零重复。

#### 1.5.1 渠道定位

| 渠道 | 交互范式 | 典型场景 | 入口文件 | 进程模型 |
|:-----|:---------|:---------|:---------|:---------|
| TUI | 交互菜单（终端） | 桌面终端内菜单导航、逐项配置后生成 | `tui/tui.py` | 前台进程，菜单循环 + handler 同步执行 |
| CLI | 命令行参数（脚本/定时） | 定时任务（cron）、脚本化批量生成、what-if 调仓 | `cli/cli.py` | 前台进程，解析参数单次执行后退出 |
| Web | 浏览器界面（HTTP） | 浏览器内上传持仓 → 选格式 → 生成 → 预览/下载 | `web/server.py` | 常驻服务进程，单 worker 串行队列 + 后台 worker 线程 |

> 三渠道的入口文件/用户交互层/业务逻辑层/进度报告器对照见 [§1.1](#11-系统分层) 的三入口表。

#### 1.5.2 统一架构模式

三渠道遵循同一「**薄入口 + 共享管线 + 进度抽象 + 配置快照**」模式：

- **薄入口**：渠道层只保留交互外壳（菜单 / argparse / HTTP 路由），不承载业务逻辑。TUI 的 `tui/handlers_*`、CLI 的 argparse 直调、Web 的 API 路由均委托共享层（`report/orchestrator.py` + `cache/operations.py`）。展示与校验类共性规则同样单源：LLM 配置状态经 `core/system_info.llm_status()` 组装（三渠道状态行只渲染不判定），空持仓门经 `core/reader.require_holdings()`（各渠道捕获后映射自身错误通道）。
- **共享管线**：`generate_report()`（报告编排器，§4.2）为同步函数，通过可注入的 `ProgressReporter` 接口输出阶段消息，与终端/浏览器完全解耦——三渠道注入各自的 reporter 子类即可，**管线代码零改动**。
- **进度抽象**：`report/progress.py` 定义 `ProgressReporter` 基类（info/ok/warn/error/add_error/timer），三渠道各实现子类：`TuiProgressReporter`（菜单区刷新）、`CliProgressReporter`（logging + verbose stderr）、`WebProgressReporter`（事件缓冲 → 浏览器轮询）。
- **配置快照**：生成任务执行时取一次 `get_config()` 快照，run 期间不受外部配置修改影响（Web 侧在任务**出队时**取快照，见 §1.8.5）。

**渠道共性规则的单源清单**（渠道层不得各写一份）：报告输出目录 `config.resolve_output_dir`、尺寸格式化 `core.num_utils.format_size`、异常→用户提示 `core.error_hints.hint_for`、原始 `llm_settings.json` 读取 `config.read_llm_settings_file`、doctor 网络预算 `core.doctor.NETWORK_TIMEOUT_*`、产物定位/打开 `core.artifacts`、页头新鲜度 `core.data_freshness.header_freshness`。

#### 1.5.3 渠道差异对照

| 维度 | TUI | CLI | Web |
|:-----|:----|:----|:----|
| 参数传递 | 菜单交互逐步选择 | argparse 参数 + `--type basic/both/full` | 前端表单提交（报告格式下拉 + 获取历史走势/强制 LLM 复选 + 强制模块多选） |
| 配置编辑 | 主菜单改项即写即存（写前 .bak） | `config set` 持久化（同一白名单/校验/.bak）；`--chapter` / `--anonymize` 仅本次运行 | 配置编辑面板（§1.8.11 白名单 9 组）即改即存 + 写前 .bak + 同源守卫 |
| 进度传输 | 终端区实时刷新 | stdout/stderr 文本 | 事件缓冲 seq 增量轮询（`/api/runs/{id}/events`） |
| 并发模型 | 单线程同步 | 单线程同步 | 单 worker 串行队列（HTTP 线程提交、worker 线程执行） |
| 产物输出 | `output_dir` 最新版 + `YYYYMMDD/` 归档 | 同左 | 同左；产物定位基于 run 快照 output_dir，`/api/reports` 预览/下载 |
| 启动防护 | 无 | 无 | 端口占用检测（bind 探测）+ output_dir 写锁检测（§1.8.2） |
| 生命周期 | 会话式，退出即结束 | 单次执行退出 | 常驻服务（Ctrl+C 退出，daemon worker 丢弃进行中任务） |

#### 1.5.4 并发与产物治理

三渠道均可能向同一 `output_dir` 写报告产物（最新版固定文件名 + 日期归档），**并发写入会互相覆盖最新版**。治理分三层：

| 层 | 机制 | 适用范围 |
|:---|:-----|:---------|
| 进程内 | Web 单 worker 串行队列（同一时刻仅执行一个生成任务） | Web 进程内多请求 |
| 进程间 | `output_dir` 写锁检测（启动时原子抢占锁文件，被占用则警告） | Web 与 TUI/CLI 并行、或多开 Web 实例 |
| 存储 | 缓存层原子写入（`os.replace`）+ 报告归档按 `YYYYMMDD` 分目录 | 全部渠道 |

> 设计原则：并发治理以「**警告优先、不阻塞**」为度——「同一 `output_dir` 仅一个入口运行」属文档约定，冲突时提示用户自行决策，而非强制互斥。

[↑ 回到顶部](#目录)

---

### 1.6 TUI 渠道详细设计（主要渠道）

TUI（Text User Interface）是系统**主要交互渠道**：桌面终端内的**交互菜单**形态，用户通过方向键/快捷键逐项导航、配置后生成报告。TUI 承担了最完整的交互面——报告生成、配置管理、缓存管理、调仓模拟、LLM 模块配置全部有对应菜单项，是功能覆盖度最高的渠道。设计遵循「薄入口 + 共享管线」：`tui/handlers_*` 仅保留交互外壳（文件选择、参数询问、结果格式化），业务全部委托共享层。

#### 1.6.1 模块划分

| 模块 | 职责 | 关键内容 |
|:-----|:-----|:---------|
| `tui/tui.py` | 主入口/主循环 | sys.path 注入、init_config、_bind_callbacks、启动清理/隐私提示/首次引导、方向键导航循环、LLM 会话统计 |
| `tui/tui_menu.py` | 菜单定义与渲染 | MENU_ITEMS 列表、MENU_GROUPS（任务分组：生成报告 E/B/L/W · 数据与查看 Q/1/2/3 · 配置 P/S/M/I/A/D/R · 诊断与排查 V/H/T）、render_menu/print_header/show_config、_apply_feature_gates（开关门控裁剪）、index_by_key、match_menu_items/next_matching（`/` 筛选与筛选内导航）、press_any_key/exit_app |
| `tui/tui_keys.py` | 键盘封装 | 跨平台（Windows msvcrt / Linux tty+termios+select），标准化键名 KEY_UP/DOWN/ENTER/CTRL_C |
| `tui/handlers_report.py` | 报告生成外壳 | `_run_generate` 骨架、`_prompt_generate_confirm` 合并单屏一次确认（full：费用预估上屏 + 回车/`Y`/`N`/`q`/`h` 单问，默认侧 `Y`=用已有结果，`N`（同义 `f`）触发 `_select_force_modules` 模块多选，含日预算超限安全网）/`_prompt_history`（委托 resolve_fetch_history + 注入 y/N 询问，仅 both）、E/B/L 三命令 |
| `tui/handlers_config.py` | 配置管理外壳 | 目录/文件名/输出目录/章节显隐/指数池/匿名化/章内内容开关/刷新等配置命令（面板本体按域拆分：`[C]`→`handlers_report_chapters.py`、`[S]`→`handlers_switch.py`，本文件只留菜单入口与共享写路径 `_apply_edit`） |
| `tui/handlers_report_chapters.py` | `[C]` 章节显隐面板本体 | 四块章节 + 智囊团生成子项（条目与编号由注册表派生）：清单/编号/来源全部取自 `config/chapter_registry.py`；写路径统一经 `handlers_config._apply_edit`（config/llm_settings/features 四来源），子项闸门（父章节关闭时名称/键名置灰并提示，状态字仍红色「关」），`?编号`/`?键名` 富详情，LLM 章节行尾费用摘要；键名恒显（宽/中档行内列、窄档第二行） |
| `tui/handlers_cache.py` | 缓存管理外壳 | 更新基础/行情类缓存、清理过期、查看统计 4 项命令 |
| `tui/handlers_whatif.py` | 调仓模拟外壳 | What-if 对话流程，委托 `report/whatif_operations.py`（§4.13） |
| `tui/handlers_log.py` | 诊断外壳 | `[V]` 运行日志查看（按级别筛选）/ `[H]` 数据源健康历史 / `[T]` 系统自检（doctor，§4.17）三命令 |
| `tui/handlers_qa.py` | 报告追问外壳 | `[Q]` 入口：输出目录报告选择 + 文本输入循环，委托 `qa/session.ask_report_qa`（§6.8）；`report_qa` 门控 |
| `tui/text_layout.py` | 终端排版原语 | `display_width`（东亚宽度，剥离 ANSI）/`pad_right`/`truncate_display`（按列截断带省略号）/`wrap_display`（按列折行）/`wrap_hanging`（续行悬挂缩进，逐行扣减缩进宽度）/`wrap_with_prefix`（前缀不参与断行，续行对齐正文列）/`render_panel`（盒线面板，统一定宽）/`terminal_columns`（实时尺寸 > `COLUMNS` > 兜底，下限 40）；TUI 所有打印型输出按它折行，窄屏（手机）不硬折 |
| `tui/switch_panel.py` | `[S]` 面板响应式排版 | `layout_tier()` 按终端列数分三档（≥96 宽 / 64~95 中 / <64 窄）、`status_text()` 状态唯一实现（关闭恒红）、`format_item()` 逐档生成「编号·名称·键名(淡色)·状态·备注」行、`legend_lines()` 页脚图例折行、`format_item(reveal_key=)` 窄屏按 `k` 追加键名行；终端宽度探测与折行原语在 `tui/text_layout.py`（本模块 re-export `terminal_columns`）；**只排版不取数**，不变式「任意档位每行 ≤ 面板内宽」由单测锁定 |
| `tui/panel_runtime.py` | TUI 统一交互运行时 | `NavState`（游标 + engaged 导航态，语义真值取自主循环 `sel`）/ `PanelItem`（key/label/kind/action 派发项）/ `panel_loop`（读键→导航→派发→反馈/重绘单源循环：方向键回绕且跳过 return 项、Enter 防误触 engaged 门控、直达键游标同步不置 engaged、Esc/return 退出、`pick>1` 收集、`on_text` 词法、Ctrl+C/EOF/render 异常原样上抛）；全列表面板（`[C]/[A]/[D]/[I]/[S]/[M]`/缓存）与主循环 `sel` 收敛于此，导航态为实例态、模块内零可变全局（C14）；只统一「怎么到达一次派发」，不改「派发什么」 |
| `tui/status_line.py` | 页头状态行 | `build_status_line()` 五项常驻状态（上次报告时间/缓存过期数/数据新鲜度/备用源数/LLM 状态点），全本地取数、逐项降级、TTL 记忆化 |
| `report/progress.py` | 进度报告 | TuiProgressReporter（`[..]`/`[OK]`/`[!]`/`[ERR]` 前缀 + 耗时排行） |

#### 1.6.2 主循环与键盘导航

`tui/tui.py:main()` 主循环——每轮迭代**重绘**完整界面并等待一个按键：

```text
while True:
    print_header()    # 标题 + 首次使用指引
    show_config()     # 持仓/输出目录/新闻上限/LLM 状态
    render_menu(sel)  # 带选择指示器的菜单（> 标记当前项）
    key = get_key()   # 跨平台读键
```

按键路由（`tui_keys.py` 标准化键名）：

| 按键 | 行为 |
|:-----|:-----|
| ↑ / ↓ | `nav`（`NavState`）在 MENU_ITEMS 上循环移动（`panel_runtime` 单源回绕，等价原 `(sel ± 1) % len`） |
| Enter | `execute_item(sel)` 执行当前选中项 |
| 字母/数字（A-Z/0-9） | `index_by_key(key.upper())` 直达并执行对应快捷键菜单项 |
| Ctrl+C | `exit_app()` 退出 |

**统一交互运行时**：列表型子菜单的「读键 → 导航态 → 派发 → 反馈/重绘」循环控制流单源于 `tui/panel_runtime.py`（`NavState`/`PanelItem`/`panel_loop`）——语义真值取自主循环 `sel`；`[C]/[A]/[D]/[I]/[S]/[M]`/缓存管理等全列表面板与主循环均收敛到 `NavState`/`panel_loop`，方向键导航不再逐面板手写（修复「上下键仅首页生效」）。主循环 Enter 无条件派发（`render_menu` 自带高亮、`engaged` 不门控），子菜单 Enter 经 `engaged` 门控防误触，二者导航回绕共用 `NavState.move` 单源。

键盘封装跨平台：Windows 用 `msvcrt`（方向键 `\xe0` 前缀 + 第二字节映射 H/P），Linux/macOS 用 `tty.setraw` + `termios` + `select` 读 ESC 序列（`\x1b[A`/`\x1b[B` 与 O 前缀变体 `\x1bOA`/`\x1bOB` 方向键；ESC 后首段共聚窗口 `_ESC_FIRST_TIMEOUT=0.5`s + 续读窗口 `_ESC_TIMEOUT=0.3$s`；拆包防护三件套：孤 Esc 后迟到前缀吸收映射、半途序列（前缀已消费末字节未到）下一字节强制按补全处理不进字母分派、主菜单 Esc 连按两次确认——误判方向键不致退出或误触发直达；**读取一律 `os.read(fd, 1)` 原始字节与 select 同 fd**——禁止 `sys.stdin.read`（用户态缓冲会把整包吞走，此后 select(fd) 谎报「无数据」，整包方向键被误判为孤 ESC：首按挂退出确认态、次按误退出，缓冲时代电脑上亦 100% 触发）；**任何非 Esc 按键解除主菜单退出确认态**（拆包孤 ESC 挂起的确认不被后续按键引爆），宽/窄档方向键均原地重绘）；`input_choice(prompt, arrows=True)` 供列表面板（`[S]`）返回 ↑/↓（行内已有内容时序列仍吞掉保行编辑），非 Esc 按键同样解除退出确认态的对偶语义由各提示的 Esc 取消承接）。所有读键路径统一返回标准化键名，菜单层不感知平台差异；非交互 stdin（非 tty）返回 `KEY_UNKNOWN`，保证管道/重定向环境不阻塞。

#### 1.6.3 菜单体系

`tui/tui_menu.py:MENU_ITEMS` —— 每项 `(快捷键, 显示标签, 回调, 是否退出)`，回调由 `_bind_callbacks()` 在**运行时**从 handlers 模块填入（定义时不直接 import，避免启动即加载全部处理器）。静态清单共 **19 项**（下表按菜单实际排列顺序）；首页按键分派分两档（`layout_tier`，<64 列为 narrow）：方向键移动选中态 + `Enter` 执行当前项**全档可用**；narrow 档直达主路径（字母/数字键即执行，未登记键给**单行反馈**不整屏重绘——「分档只改版式不改语义」约束 C29）与导航并存——方向键移动后**原地重绘**（`_render_menu_frame` 帧行数计数代理 + ANSI 光标上移/清屏，POSIX+TTY 门控，管道/测试/旧控制台回退整屏追加），页脚为「窄屏直达 + ↑↓ 选择」双提示。字母/数字键按 `index_by_key` 直达（未登记键无反应）、`Esc`/`0` 与 `[X]` 同为退出通道（`0` 在子菜单语义为「返回」，故首页保持一致习惯；`[X]` 标签写明「退出（0 亦可）」，页脚提示同为「Esc / 0 / X 退出」）、`Ctrl+C` 退出。菜单项长标签与页脚提示经 `wrap_with_prefix` 按终端宽度折行（续行对齐标签起始列），窄屏不会硬折。渲染按 `MENU_GROUPS`（生成报告 / 数据与查看 / 配置 / 诊断与排查）分组并印组标题，未入组的退出项列在末尾（分组覆盖完整性由 `test_tui_menu.TestMenuGroups` 守护：全项恰好一次、退出项在外）。主菜单支持 `/` 关键词筛选：`tui._read_filter_keyword` 读一行关键词（空=清除、Esc 保持原筛选），`match_menu_items` 按键精确命中优先、否则按标签子串匹配；筛选态只渲染命中项与命中分组，`↑↓` 在命中集内回绕（`next_matching`），按到被隐藏项的键给单行反馈而不静默吞键，`0` 先清筛选（无筛选时才是退出）。`[T]`/`[Q]` 登记于 `FEATURE_GATED_ITEMS`（菜单键 → Feature Flag），`main()` 启动时在绑定回调**之前**执行 `tui_menu._apply_feature_gates()` 按 `is_feature_enabled` 就地裁剪（裁剪后索引才与渲染一致）：`report_qa`（⚗ 实验项，默认关）关闭时移除 `[Q]`，`doctor_check`（默认开）关闭时移除 `[T]`——默认配置下实际渲染 **18 项**。

| 分组 | 快捷键 | 功能 |
|:-----|:------|:-----|
| 报告生成 | `[E]` | 生成基础报告（仅 Excel，basic） |
| | `[B]` | 生成标准报告（Excel+HTML，按章节配置，both） |
| | `[L]` | 生成完整报告（Excel+HTML，含 LLM，full；`config.default_menu_key` 缺省指向本项） |
| | `[W]` | 调仓 What-if 模拟（对比两份持仓，独立报告） |
| | `[Q]` | 报告对话式追问（选择已生成 HTML 报告进入多轮文本输入循环，委托 `qa/session.ask_report_qa`，§6.8；`report_qa` 门控） |
| 配置管理 | `[G]` | 全局设置七项（`GLOBAL_SETTINGS_ITEMS` 单源登记：键 / 显示名 / 处理器 / 分组），数字为主入口、字母为别名：`H` 持仓信息目录、`F` 持仓信息文件名、`O` 报告输出目录、`L` LLM 设置（运行参数 1-6 + 第 7 项多链线路）、`I` 对比基准指数、`A` 持仓匿名化、`M` 配置入口地图（`_CONFIG_ENTRY_MAP` 只读索引）；目录三项直挂二级、无中间子面板（同一配置只有一条入口路径） |
| 缓存管理 | `[1]`/`[2]` | 更新基础类缓存（基金业绩/持仓/经理/基准等，`clear_by_group("refresh")` 先清后取）/ 行情类缓存（价格/指数等，`clear_by_group("preload")` 先清后取） |
| | `[3]` | 缓存管理**子菜单**（统计首屏 → 子菜单内 `3` 清理过期 / `B`/回车 返回；合并原清理与统计两个平级入口，`handlers_cache.py::_cmd_cache_management`） |
| 配置管理 | `[C]` | 报告章节显隐（四块：顶层 / LLM / 默认关闭的整章 / 关联产物，另含智囊团生成子项；清单、编号、分块与来源由 `config/chapter_registry.py` 派生，四来源写入统一经共享编辑层 `config/edit_ops.py`；面板只切显隐、不增删章节不改顺序；子项在父章节关闭时名称/键名置灰并提示原因、状态字仍红色「关」；`?编号`/`?键名` 查看来源文件/写键/默认值，行尾 `*` 标漂移，LLM 行附近 7 日费用摘要） |
| | `[I]` | 对比指数池管理（自定义基准指数） |
| | `[A]` | 持仓匿名化模式（off / code_display / full_anonymous / summary 四种） |
| | `[S]` | 报告章节内容呈现（`PANEL_GROUPS["[S]"]` 六组：持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 呈现与交互 / 机制与质量；条目与编号由 `features.panel_option_numbers("[S]")` 按组序派生，增删开关自动重排；**不混排** LLM 章节/整章/关联产物——它们在 `[C]`；面板每行显式展示键名（淡色列），版面按终端宽度自适应三档（`tui/switch_panel.py`：<64 列去盒线、写路径切换后即时重绘且反馈带编号，只读查询/失败路径窄屏一行反馈（`p` 重绘）、所有提示按宽折行）；写路径三通道：`r 编号`/`ra`/`x`、裸键名、`键名=on|off`，实验项行首 ⚗ 标记） |
| | `[R]` | 刷新配置（config.json + llm_settings.json + llm_key.json，附带重载定价与批量限速器） |
| 诊断 | `[V]` | 查看最近运行日志（可按级别筛选，`handlers_log.py::_cmd_view_logs`） |
| | `[H]` | 查看数据源健康历史（`handlers_log.py::_cmd_view_health_history`） |
| | `[T]` | 系统自检（环境/配置/目录/数据源一键体检，`handlers_log.py::_cmd_run_doctor`；恒上屏，无开关） |
| 退出 | `[X]` | 退出程序 |

面板交互运行时 `tui/panel_runtime.py`：`PanelItem(key, label, kind, action, detail)` + `panel_loop` 统一承接导航/派发/反馈/重绘与帮助——`?` 打印本面板可用键一览、`?键` 打印单项详情（详情文案取 `PanelItem.detail`，面板各写业务含义、渲染单源；`on_help` 可整面板接管）。菜单渲染层与状态面板：`print_header`（标题 + 页头常驻状态行 `status_line.build_status_line()`——上次报告时间/缓存过期数/数据新鲜度/备用源数/LLM 状态点五项，全本地取数、单项异常降级为 `—`、TTL 记忆化——+ 首次运行指引：缺持仓文件/缺 LLM 配置提示）、`show_config`（持仓目录/持仓文件、输出目录、新闻抓取上限、文件就绪状态 `[OK]`/`[!!]`、匿名化状态、隐私声明、LLM 配置状态单链/多链两视图）。LLM 状态面板支持多 Provider 链式模式（策略、各 provider 后端/模型/优先级/自动重试状态、模块级偏好）；上屏词按 `DESIGN-TUI` 术语表转用户词——端点状态由 `core.system_info.circuit_display` **唯一归一**（`熔断中`→`暂时失败`，未知上游文案透传），TUI/CLI/Web 三渠道共用同一词，各渠道不得自带映射表；面板数据消费 `core/system_info.llm_status()` 单源（configured 判定与多链/flat 分支唯一在共享层，渠道只做终端渲染）；多链 `providers` 出口按链序排列——排序口径唯一实现在 `config/_llm_providers.order_providers_by_chain`（`priority` 升序、同值保持数组原序），`llm_status()` 与 `[M]` 面板同经此函数，`chain_head` 恒等于 `providers[0]`，保证首页编号 / 状态行链首 / 面板编号三处不会出现相反顺序（数组物理顺序不作数：reorder 只改 priority 值、不改数组项位置）。**配色一色一职责**（角色表见 `DESIGN-TUI` Colors）：品牌橙=应用名与版本号、结构蓝粗=分组标题（`text_layout.style_heading` 单源，首页与 `[S]` 同步改色）、焦点青=选中标记/面板游标、状态色按值给（绿正常/黄注意/红错误）、DIM=分隔线与页脚图例；非 TTY 与 `NO_COLOR` 下全量退化无色。

#### 1.6.4 报告生成流程

`handlers_report.py` —— 三条生成命令（E/B/L）共用 `_run_generate(report_type, fetch_history, force_llm, force_llm_modules)` 骨架：

1. **持仓准备**：`prepare_holdings()` → `select_holdings_file()`（交互式文件选择）→ `read_holdings_with_flows()`（主表 + 交易/分红流水）→ `warm_new_asset_caches()`（新资产缓存预热，委托 §3.6 缓存操作共享层）。
2. **交互询问**（TUI 专属，CLI/Web 用参数/表单表达；`E`/basic 无询问直连）：
   - `_prompt_generate_confirm()`（仅 `L`/full）：**合并单屏一次确认**——先上屏事前费用预估与今日已花费/日预算，随后**问句**「是否用已有的 AI 分析结果生成？（`Y`=用已有结果，免费但可能不是最新；`N`=重新生成，会产生费用）」+ 键位行「回车/`Y`=用已有结果生成 / `N`=重新生成（可选模块） / `q`=中止」（回答键 Y/N 一看即懂，默认侧 `Y` 即回车）（`history.fetch_mode=prompt` 且 `enable_history` 开时多一个 `h`=含历史走势选项）；历史三态仍委托 `report/history_policy.resolve_fetch_history` 单源解析（`ask` 回调返回本屏 `h` 是否按下），渠道层不自行分支 `fetch_mode`；日预算超限走**独立安全网确认**（用已有结果继续 / 中止），Esc 即时取消返回主菜单。提示按键按**词**精确匹配（空格/逗号分隔，支持 `n h` 组合，`f` 为 `N` 同义键，`of`/`on`/`faq` 这类子串不误触发）；安全网降级路径**不追加历史询问**（`ask` 恒 False：prompt 模式回落为不获取、auto 仍自动获取，交互最小化），该路径且 prompt 模式时输出一行「本次用已有结果，不获取历史走势」提示保证可感知（告知后覆盖，不追加提问）。返回 `(force_llm, force_llm_modules, fetch_history)`，`None` 表示中止。
   - `_select_force_modules()`（`L` 按 `N`/`f` 触发）：模块多选（列出 FORCEABLE_LLM_MODULES 编号/键名，逗号分隔，回车=全部；仅指定子集时传 `force_llm_modules`，粒度优先于全量）；选后按所选范围**重打更新预估行**（`forecast_run_cost(force_llm/force_modules)` 三渠道同源：范围内模块静态单价口径、范围外历史口径，摘要行「其中 N 个模块重新生成」拆行）。
   - `_prompt_history()`（仅 `B`/both）：同样委托 `resolve_fetch_history` 单源三态，`prompt` 时注入「是否获取组合历史走势数据（as-if 模拟）？」y/N 询问。
3. **委托共享层**：`orchestrator.generate_report(holdings, config, reporter, report_type, ...)`（§4.2）——reporter 注入 `TuiProgressReporter`，管线代码零改动。
4. **收尾**：`finish_report()` → `print_error_summary()`（非致命错误汇总）+ `print_timing_summary()`（耗时排行）+ `press_any_key()`（等待返回菜单）。

#### 1.6.5 TuiProgressReporter 进度输出

`report/progress.py:TuiProgressReporter`（`ProgressReporter` 基类子类，§1.5.2）：

- **前缀语义**：`[..]`（进行中，CYAN）/ `[OK]`（成功，GREEN）/ `[!]`（告警，YELLOW）/ `[ERR]`（错误，RED）——四态前缀与 UI 输出前缀约定一致。
- **call_sheet 页签粒度**：`info("正在生成X...")` → 执行 → `ok("X生成完成")`，页签级进度可视。
- **耗时排行**：`print_timing_summary()` 汇总各模块耗时（合并同名 label），画 `┌──48──┐` 边框 + `█░` 百分比条形图，输出「模块耗时排行（总计 N.Ns）」。
- **错误收集**：`add_error` 收集非致命错误，`print_error_summary` 汇总输出（「不影响已有结果」），输出后清空。

#### 1.6.6 启动流程

`tui/tui.py:main()` 启动序列：

1. **配置初始化**：`init_config()` → `_bind_callbacks()` 运行时注入菜单回调。
2. **过期缓存清理**：`cleanup_expired()` 静默后台执行——逐文件明细走 DEBUG，INFO 只留汇总（数量 + 释放字节，age/TTL 按量级自适应单位）；仅按 `_ts` 判龄，**无 `_ts` 的文件不属缓存引擎托管、跳过不删**（脚本自管的性能缓存在 `data/cache/` 下写入时必须带 `_ts` 包封）。
3. **隐私提示**：`show_privacy_notice_if_needed()` 首次运行显示隐私声明。
4. **首次运行引导**：`show_startup_wizard_if_needed()` 检测缺失资源并交互式提示。
5. **缺省菜单定位**：读 `config.default_menu_key`（默认 `"L"` 完整报告）→ `index_by_key()` 定位初始选中项，未命中回退 0。
6. **主循环**：进入 1.6.2 的导航循环；退出时 `atexit` 注册 `_print_session_usage_on_exit()` 打印本次会话 LLM 累计用量（模型、分模块调用、tokens、缓存命中、累计费用）。

[↑ 回到顶部](#目录)

---

### 1.7 CLI 渠道详细设计

CLI 渠道是**命令行参数**形态，面向脚本化与自动化场景：定时任务（cron/计划任务）、批量生成、what-if 调仓、数据源健康检查。`cli/cli.py` 为 argparse 主入口，单次执行后退出，退出码供外部脚本判定成败。**模块职责拆分**（守住单文件 1000 行红线）：`cli/_parser.py` 承载解析器构建与 type 回调，`cli/_handlers.py` 承载子命令处理器、持仓读入辅助与 `_EXIT_*` 退出码契约，`cli/cli.py` 为门面——保留 `main()`/`run_cli()` 主流程与命令行功能开关应用，并 re-export 上述符号（`__all__` 显式声明），保证 `src.python.cli` 包导入与测试 patch 点（`cli.cli._handle_*`）稳定。与 TUI 差异在**无交互**——持仓通过 config 定位而非文件选择器，进度默认写日志（`--verbose` 才输出到 stderr）。

#### 1.7.1 退出码约定

| 退出码 | 含义 |
|:------|:-----|
| 0 | 成功 |
| 1 | 部分失败（非致命错误，如个别数据源失败、LLM 部分模块失败） |
| 2 | 严重错误（持仓缺失、参数错误、未处理异常） |

#### 1.7.2 argparse 结构

`_build_parser()`（`cli/_parser.py`）：`prog="investor-review"`，全局参数 + 7 个子命令。

- **全局参数**：`--config`（备用配置文件路径）、`--output`（报告输出目录，覆盖 config 的 output_dir）、`--verbose`（进度同步到 stderr，默认仅写 logs/app.log）、`--non-interactive`（跳过首次运行交互式引导，定时任务/脚本使用）、`--experiment NAME`（可重复；启用实验性功能且**仅本次运行生效、不写盘**。NAME 取开关名或显示名，`all` = 全部启用。取值经 `_experiment_name` argparse type 回调即时校验：空串/未知名即报错，可选值由 `features.describe_experiment_flags()` 生成）、`--feature NAME=VALUE`（可重复；**全部**功能开关的双向一次性开关，同样是仅本次运行、不写盘。VALUE 取 `on/off/true/false/1/0`（大小写不敏感），NAME 取注册表键名。取值经 `_feature_override` argparse type 回调即时校验：非 `NAME=VALUE` 形态、未知开关名、不可识别取值均即报错并列出可选值；同名后者覆盖前者。两者共用一个应用原语，`--feature` 在 `--experiment` 之后应用，故显式取值可覆盖 `--experiment` 的隐式「置开」）、`--version`。
- **`report`**：`--type basic/both/full`（默认 basic）、`--history auto/off`（未指定回退配置层 `history.fetch_mode`，仅 both/full 有效）、`--force-llm`（全量强刷）、`--llm-module KEY`（可重复传参，仅强刷指定模块，粒度优先于 `--force-llm`；可选键见 `llm/force_scope.py::FORCEABLE_LLM_MODULES`）、`--prefer-source NAME`（可重复；本次运行优先数据源，仅排到链首，不绕过熔断与凭据就绪预检，不写配置）、`--exclude-source NAME`（可重复；排障复现排除数据源，未知名即报错并列出可用源名）、`--yes`（跳过生成前 LLM 费用预估确认，仅 full 有预估；日预算超限仍直接中止）。
- **`cache`**：互斥组 `--update basic/position/all` / `--clean` / `--stats`。
- **`whatif`**：`--candidate`（目标持仓，必填）、`--base`（基准持仓，缺省用 config 持仓）、`--effective-date`（调仓生效日，opt-in 联网取历史做时序回测）。
- **`cassettes`**：数据源记录-回放维护（`core/cassette.py`），无参数列出已录制响应，`--verify` 逐条离线回放并交当前解析器解析（不联网）；**无需 config 且只读离线**（main() 中特殊前置分派）。
- **`check-sources`**：数据源健康检查，**无需 config**（main() 中特殊前置分派）。
- **`view-logs`**：结构化运行日志查看（`core/log_reader.py::read_log`），`--level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`（最小级别阈值）、`--lines N`（默认 5000，读取末尾行数上限）、`--since/--until`（时间前缀过滤）；**无需 config**（main() 中特殊前置分派，配置损坏时仍可查日志诊断）。
- **`doctor`**：系统自检（`core/doctor.py`，§4.17.3），`--offline`（跳过数据源联网检查）、`--timeout SECONDS`（默认 8.0，联网检查总预算）；**无需 config**（main() 中特殊前置分派——配置损坏正是它要诊断的场景，若被开关拦住即成死锁）。

#### 1.7.3 主流程

`main()`：`setup_logger` → `_build_parser` → `parse_args` → `check-sources` / `view-logs` / `doctor` / `cassettes` 特殊处理（均不 init_config，经 `_prepare_early_exit_switches(groups, pairs)` 先加载 `features.json` 覆写再叠加 `--experiment` / `--feature` 增量）→ `init_config` + `get_config` → `_apply_cli_experiments(args.experiment)` + `_apply_cli_switches(args.feature)`（命令行功能开关，须在配置初始化**之后**——覆写加载已完成，此处只做本次运行的增量 `set_feature_enabled`，绝不 `save_feature_overrides` 写盘；顺序为 `--experiment`（只开实验项）在前、`--feature` 显式取值在后，故后者可覆盖前者）→ `startup_wizard(non_interactive)`（非交互/CI 环境自动跳过，不阻塞命令）→ 按 `args.command` 分派 `_handle_report` / `_handle_cache` / `_handle_whatif`。

**持仓定位差异**：CLI 不经过 TUI 文件选择器——`_cli_resolve_holdings_file()` 通过 config 的 `holdings_dir + holdings_filename` 直接定位；若该路径为目录则自动选第一个 `.xlsx`（多个时告警）。`_cli_read_holdings()` / `_cli_read_holdings_with_flows()` 分别读主表与「主表+流水」，与 TUI 读取路径对齐。

#### 1.7.4 子命令处理器（`cli/_handlers.py`）

- **`_handle_report`**：`CliProgressReporter(verbose)` 注入 `generate_report`（§4.2）；`--output` 覆盖 `output_dir`，`--history` 为 None 时回退配置层解析；收尾经 `_notify_report_completion()` 按 `notify` 配置分发完成/失败通知（`core/completion_notify.py`，尽力而为不改退出码；无配置静默跳过）；返回 `result.exit_code`。
- **`_handle_cache`**：三分支——`--clean` 委托 `cleanup_cache`；`--stats` 委托 `get_cache_stats` + 打印 LLM 配置状态（消费 `core/system_info.llm_status()` 单源，仅日志渲染）；`--update` 委托 `update_basic_cache`/`update_position_cache`（§3.6），`--update all` 委托 `update_all_cache` **最大努力模式**（basic 失败仍继续 position，退出码取两者 max）。
- **`_handle_whatif`**：解析 `--base`/`--candidate` 两份持仓 → `run_whatif_simulation()`（§4.13）→ 结果 `ok` 判定，失败返回 2；`--effective-date` 触发时序回测扩展。
- **`_handle_cassettes`**：无参数时经 `core/cassette.py::list_cassettes()` 列出已录制响应（来源/录制时间/交互数/大小）；`--verify` 时经 `fetcher/cassette_checks.py::CASSETTE_CHECKS` + `verify_cassettes()` 离线回放，有解析失败返回 `_EXIT_SEVERE`。纯只读展示层，不联网、不碰用户配置。
- **`_handle_check_sources`**：`collect_check_sources_report()`（内部 `sys.exit`）。
- **`_handle_view_logs`**：调 `core/log_reader.py::read_log(limit, level, since, until)`，输出每条 `time [LEVEL] message`（多行 body 缩进）；无匹配 → 提示并返回 0；ValueError/OSError → 记录日志 + 返回 `_EXIT_SEVERE`。**薄展示层，无解析逻辑**（解析/过滤全在 `core/log_reader.py`）。
- **`_handle_doctor`**：调 `core/doctor.py::run_doctor_checks(include_network=not offline, max_timeout=timeout)` → `format_doctor_report(results, use_color=_use_ansi_color())` → 按 `summarize_doctor_results()` 返回 `_EXIT_SUCCESS`（全通过）/ `_EXIT_PARTIAL`（有失败项）。`_use_ansi_color()` 遵循 `NO_COLOR` + `isatty` + UTF-8 三项判据，终端不支持颜色时自动降级为纯文本（§4.17.3）。

#### 1.7.5 CliProgressReporter

`report/cli_progress.py:CliProgressReporter`（`ProgressReporter` 子类）：默认进度写入 `invest` logger（`logs/app.log`），`--verbose` 时同步打印到 stderr——**静默为默认**，适合定时任务不污染 stdout；`print_timing_summary` 复用耗时汇总能力（与 TUI 同构，输出走日志/verbose）。

#### 1.7.6 便捷入口包装脚本

`scripts/cli.sh`（Linux/macOS，Bash）与 `scripts/cli.ps1`（Windows PowerShell）为 CLI 的**便捷入口外壳**：自动定位项目虚拟环境解释器（`.venv/bin/python` / `.venv\Scripts\python.exe`）并 `cd` 到项目根目录后执行。**无参数调用时默认注入 `report --type both`**（Excel+HTML 双格式、不含 LLM、全部页签有数据），传入参数时原样透传给 `cli/cli.py`。属纯分发层（不新增业务逻辑），供交互式使用与脚本速查；Windows 侧 `cli.ps1` 保持 UTF-8 with BOM + CRLF 编码约束（见 CLAUDE.md 编码/BOM 说明）。

[↑ 回到顶部](#目录)

---

### 1.8 Web 渠道详细设计

Web 渠道是第三种交互入口：**浏览器内完成「上传持仓 Excel → 选择报告格式 → 生成 → 预览/下载」全流程**。设计定位「薄入口 + 共享管线零改动」，仅在 Web 层实现 HTTP 通道、上传安全、后台任务与进度缓冲四类差异化逻辑。

#### 1.8.1 模块划分

| 模块 | 职责 | 关键内容 |
|:-----|:-----|:---------|
| `web/server.py` | 启动入口 | sys.path 注入、参数解析、端口检测、output_dir 写锁检测、init_config、app.run |
| `web/app.py` | Flask 应用工厂 | 统一 JSON 错误处理、request_id 访问日志、注入 run_manager |
| `web/handlers.py` | API 路由 | 页面/上传/生成/轮询/预览/下载/历史/健康/日志/缓存统计与清理/What-if/报告追问/配置编辑；`_run_generation` 薄包装器（委托 `_run_generation_impl` + `result_box` 回传产物标志，收尾经 `_notify_web_completion` 按 `notify` 配置门控派发完成通知——Web 手动 + 内置定时调度共用，与 CLI 同构尽力而为不改退出码）；`_build_system_info` 委托 `core/system_info.build_system_info` 单源组装状态区系统信息（版本/本机 IP/持仓输出摘要/LLM 含多链/自检卡片可见性，与 TUI 同组展示原语）；`_handle_logs`/`_handle_health_history` 薄展示（委托 `core/log_reader.py` + `core/perf.py`，无解析逻辑）；`_handle_doctor` 薄展示（委托 `core/doctor.py`）；`_handle_config_edit` 同源守卫（`_is_same_origin`）；`_build_artifacts` 委托 `orchestrator.artifacts_for_report_type` 类型语义与 `core/constants` 最新产物名（不镜像 CLI --type 规则与文件名字面量）；空持仓门经 `core/reader.require_holdings` 单源（HTTP 端不带服务端路径） |
| `web/run_generation.py` | Web 生成执行体 | `_run_generation` 薄入口（委托 `_run_generation_impl` + `result_box` 回传产物标志，收尾经 `_notify_web_completion` 按 `notify` 配置门控派发完成通知——Web 手动 + 内置定时调度共用，与 CLI 同构尽力而为不改退出码）；`_run_generation_impl` 读持仓/输入模式分派（试算→`web/` 隔离域、正式→共享主目录）/LLM 日预算硬闸/`generate_report` 调用/退出码映射/上传临时文件清理；`_build_artifacts` 委托 `orchestrator.artifacts_for_report_type` 类型语义与 `core/constants` 最新产物名；`_web_input_mode_snapshot_domain` 模式↔隔离域唯一事实来源 |
| `web/upload.py` | 上传安全 | 服务端 uuid 重命名、扩展名白名单、大小上限、PK 魔数、原子落盘、TTL 清理 |
| `web/config_edit.py` | 配置编辑 | 薄外观：再导出共享层 `config/edit_ops.py` 符号（`apply_config_edit`/`config_edit_whitelist`/`config_backup_file`）+ `get_config_edit_surface` 组装呈现面：`domains`（五域 → 块清单，块 id 含 `features.<组键>`）、`labels`/`descriptions`/`defaults`/`needs_hint` 元数据（全部由注册表与共享白名单派生，前端零中文表）、`logging`（六项含枚举/范围）、`reference`（只读计价参考）；规则与写入单源在共享层，与 TUI/CLI 同一函数 |
| `web/runs.py` | 运行管理 | RunManager 单 worker 串行队列 + run 状态/事件注册表（Lock 保护） |
| `web/progress.py` | 进度报告 | WebProgressReporter（ProgressReporter 子类 → RunState 事件缓冲） |
| `src/static/web/` | 前端单页 | 原生 ES6 无框架、上传表单/进度事件/状态区/历史记录/配置编辑面板 |

#### 1.8.2 启动流程与启动防护

`web/server.py` 启动序列（`launch.sh web` / `.venv/bin/python -m src.python.web` / 直接执行均兼容）：

1. **sys.path 注入**：直接执行 `.venv/bin/python src/python/web/server.py` 时确保项目根在 `sys.path`（`_project_root` 三级目录上溯）。
2. **参数解析**：`--host`（默认 127.0.0.1 仅本机；局域网显式用 0.0.0.0）、`--port`（默认 8000）、`--config`（备用配置文件路径）。
3. **配置初始化**：`init_config(config_path)`，缺失自动生成默认配置。
4. **端口占用检测**：`socket` bind 探测（立即释放）——端口被占用则报错退出（返回码 2），避免服务静默失败/多实例混用产物。
5. **output_dir 写锁检测**：`ensure_output_dir_lock(output_dir)`——原子抢占 `.investor_output.lock`（`os.open` `O_CREAT|O_EXCL` 防多进程抢占竞态，内容记录 entry/pid）；锁已被其他入口持有则记录警告「该输出目录可能正被其他入口占用，产物可能互相覆盖」；**仅告警不阻塞启动**（产物竞态交由用户决策）；抢占成功则持有至进程退出 `finally` 释放。锁文件为点文件，不参与 `YYYYMMDD` 归档扫描与历史枚举。
6. **应用构建**：`create_app(run_manager)` → 注册路由 → 清理残留上传 → `app.run(host, port, threaded=True)` 常驻。

#### 1.8.3 Flask 应用工厂与统一错误处理

`web/app.py:create_app(run_manager)`：

- 支持注入 `run_manager`（默认全局单例；测试传内存 fake 免 patch 全局），注入时绑定默认执行器 `_run_generation`。
- `MAX_CONTENT_LENGTH` = 10MB 兜底；`app.json.ensure_ascii = False` 中文 JSON 不转义。
- **统一错误信封**：成功 `{"ok": true, "data": ...}`；错误 `{"ok": false, "error_code", "error": 中文文案}`——`error_code` 为机器可判定短标识（`UPLOAD_*` / `FILE_EXPIRED` / `SERVER_ERROR` / `NOT_FOUND` 等），前端按 code 分支动作，不解析中文。500 记录 error 日志但**不回显绝对路径/内部细节**；413 中文上传超限提示；404 中文接口不存在提示。
- **request_id 访问日志**：`before_request` 生成 8 位 uuid 注入 `g.request_id`；`after_request` 记一行 `method/path/status/耗时`——**不记录**上传文件名、持仓内容、绝对路径全文（日志隐私边界）；关闭 werkzeug 默认访问日志统一走 invest logger（防双通道噪音）。

#### 1.8.4 路由全景

| 方法 | 路由 | 处理 | 说明 |
|:-----|:-----|:-----|:-----|
| GET | `/` | index | 单页 UI |
| POST | `/api/upload` | 上传持仓 | 校验 → 落盘 → 预检 → file_id |
| POST | `/api/runs` | 创建生成任务 | 单 worker 队列；队列满 429；full + 日预算超限且未确认（`budget_ack`）→ 409 `BUDGET_EXCEEDED` |
| GET | `/api/runs` | 运行列表 | 最近 run（时间倒序，limit 10） |
| GET | `/api/runs/history` | 历史记录 | `core.perf.load_history()` perf 快照（5s 短缓存） |
| GET | `/api/runs/cost-preflight` | 生成前费用预估（full 弹层数据源） | 只读：`cost_forecast` forecast + budget；`llm_modules` 查询参数（逗号分隔）透传重新生成范围（与 `POST /api/runs` 的 `resolve_force_scope` 同源，预估按所选范围重估；非法键 `ok:false` 数据面降级不 500）；预估失败以数据面表达（`ok:false`）不报错 |
| GET | `/api/runs/{id}` | run 详情 | 状态快照（不含事件） |
| GET | `/api/runs/{id}/events?after=N` | 增量事件 | seq 单调递增，`seq > after` 增量轮询 |
| GET | `/api/reports/<path>` | 产物预览/下载 | `send_from_directory`（内置 `..` 净化）+ 扩展名白名单 |
| POST | `/api/whatif` | 调仓 What-if 模拟 | `_is_same_origin()` 同源守卫（失败 403）；双持仓 diff → 独立 Excel+HTML 产物 |
| GET | `/api/health` | 数据源健康 | 60s 结果缓存；`?fresh=1` 强制重测 |
| GET | `/api/health/history` | 数据源健康历史 | `core/perf.py::summarize_health_history()` 最近 N 次运行摘要（含 ok/total、失败源）；读取失败 500 HEALTH_HISTORY_READ_FAILED |
| GET | `/api/logs` | 结构化日志查看 | `core/log_reader.py::read_log()`；`?level=` 校验（非法 400 BAD_PARAM）、`?lines=` clamp [1,5000]、`?since/until` 透传；读取失败 500 LOG_READ_FAILED |
| GET | `/api/doctor` | 系统自检（恒可用，无开关） | `core/doctor.py::run_doctor_checks()`，返回 `{results, ok_count, bad_count}`；`?network=0` 跳过联网检查、`?timeout=` clamp 上限 15s（非法值回落 12s 默认）；不与其它的健康缓存共享（预算不同） |
| GET | `/api/cache` | 缓存统计 | 只读：总量/前缀分布/命中率/过期预估（过期数以 dry_run 预扫描不删除） |
| POST | `/api/cache/cleanup` | 清理过期缓存 | `_is_same_origin()` 同源守卫；删除 TTL 过期文件，有效缓存不受影响 |
| POST | `/api/qa/ask` | 报告对话式追问 | 开关 `report_qa`（默认关，关闭时 403），见 §6.8 |
| GET | `/api/config/edit` | 配置编辑面板 | 无守卫；返回 `domains` 编排契约（五域：报告内容 / 呈现与机制 / 数据与线路 / LLM 运行 / 运行与诊断，每域带 `title`/`hint`/`tui` 导引 + 有序块清单）+ 各块数据面（`paths` / `sections` / `standalone_chapters` / `standalone_related` / `anonymization`（含四档 `labels`）/ `comparison_indices` / `llm` / `llm_tuning` / `llm_providers` / `features`（`groups` + `labels` + `experimental` + `report_affecting`）/ `logging` / `reference`）+ 元数据面（`labels` / `descriptions` / `defaults` / `needs_hint`，覆盖白名单全部可编辑键）；块 id ↔ 渲染器契约由 `test_config_surface_contract.py` 双向断言 |
| POST | `/api/config/edit` | 应用配置编辑 | `_is_same_origin()` 同源守卫（失败 403）；校验失败 400 BAD_PARAM；写共享配置异常 500 CONFIG_WRITE_FAILED |

#### 1.8.5 RunManager 单 worker 串行队列

`web/runs.py` —— 管线为同步阻塞，Web 层用**单 worker 串行队列**消除进程内并发产物覆盖竞态：

- **队列**：`submit(params)` → 生成 run_id（`secrets.token_urlsafe(8)` 不可预测）→ 入队 → worker 串行出队执行。队列容量 `_QUEUE_LIMIT=3`（含运行中），超出返回 None（前端 429「已有任务在跑，排队或稍后再试」）。
- **快照语义**：每个 run 在**出队执行时**取一次 `get_config()` 快照（参数 file_id/report_type/fetch_history/force_llm/llm_modules + output_dir），run 期间不受外部配置修改影响；产物定位基于 run 快照而非实时 config（外部改 output_dir 时指向不错目录）。
- **状态机**：`queued → running → done/failed`；worker `try/except` 兜底——异常转 failed + error 日志（不崩溃服务、不静默挂起）；`exit_code` 对齐 CLI（0/1/2），前端按 exit_code 映射成功/部分失败/严重。
- **内存权衡**：run 状态/事件为**内存态**（MVP），服务重启即丢进行中 run；历史记录页数据源 = `core.perf.load_history()`（管线自动落盘的 perf 快照）。
- **内存上限**：run 记录保留 `_RUN_KEEP=20`（worker 完成时 trim 最旧）；事件缓冲每 run `_EVENT_LIMIT=500`（滚动丢弃最旧）。
- **线程安全**：注册表/队列/worker 状态均 `threading.Lock` 保护；事件读取做快照避免遍历中变更。模块单例 `get_run_manager()` + `reset_run_manager()`（测试隔离）。

#### 1.8.6 上传安全

`web/upload.py` 上传链路：

- **文件名净化**：弃用 `secure_filename`（剥离中文，不符合中文持仓文件名常态），改**服务端 uuid 重命名**为 `data/holdings/uploads/{uuid}.xlsx`——丢弃原始文件名，内容即身份，天然防路径穿越/中文问题。
- **扩展名白名单**：仅 `.xlsx`（`.lower()` 归一化后校验；拒绝 .xls/.xlsm/宏文件，openpyxl 不支持 xls）。
- **大小上限**：10MB（读流计数超限即拒 + Flask `MAX_CONTENT_LENGTH` 兜底）。
- **内容校验**：读前 4 字节校验 PK zip 魔数（`PK\x03\x04`）防改扩展名伪装（伪装 zip 预检兜底转 `UPLOAD_BAD_FILE` 400）；zip-bomb 由大小上限兜底。
- **原子落盘**：`tempfile.mkstemp` 到 `_UPLOAD_DIR` + `os.replace` 原子写。
- **内容预检**：立即内容预检（行数上限 5000 + 空持仓/无有效账户即拒），避免「上传成功、生成失败」的坏体验；预检通过才注册 file_id。
- **file_id 生命周期**：`secrets.token_urlsafe(16)`；内存映射 `file_id → path`，TTL 1h；生成任务结束立即删除（discard_file）；未消费文件下次上传时惰性清理过期项；服务启动时清理全部残留。

#### 1.8.7 WebProgressReporter 事件缓冲

`web/progress.py` —— 与 `ProgressReporter` 基类接口同构（管线零改动，只注入 reporter 子类）：

- `info/ok/warn/error` → `RunState.push_event(level, msg)` 写入 run 事件缓冲，前端轮询增量读取；不 print（日志统一约束）。
- 事件 `seq` 用**单调递增整数**（非时间戳），保证轮询增量与测试确定性；`/api/runs/{id}/events?after=N` 返回 `seq > N` 增量事件。
- `call_sheet(label, fn)` 对齐 TuiProgressReporter 语义：info「正在生成X...」/ ok「X生成完成」/ error「X生成失败」，使前端进度事件可观察页签粒度。
- `add_error` 同步进事件缓冲 + run 错误列表 + logger（非致命错误收集，映射 exit_code=1 部分失败）。

#### 1.8.8 前端单页与进度可视化

`src/static/web/index.html` + `main.js` / `style.css`（原生 ES6 无框架、无 `innerHTML`，Flask `template_folder`/`static_folder` 由 `PROJECT_ROOT` 派生指向；`/static/main.js` URL 契约不变）：

- **配置回填**：页面加载取一次 `get_config()`，报告格式/历史走势（`history.fetch_mode`）/强制 LLM 默认值跟随配置；强制模块多选候选由 `_handle_index` 经 `force_scope.FORCEABLE_LLM_MODULES` + 注册表中文名派生注入（渠道不自持副本），全选/全不选均归一为不传（后端等价全量）。
- **进度事件**：事件按 seq 编号渲染，进度条显示「当前阶段（第 N 步）：消息」，完成置 100%；轮询节流（防刷接口）。
- **配置编辑面板**：`loadConfigEdit()` 拉取 `/api/config/edit` 全量可编辑面，按 `domains` **五域分区**渲染（域内按块清单顺序，块 id → `BLOCK_RENDERERS` 分派；`features.<组键>` 由统一分支承接，域内块全空则该域不出现）；域标题与块标题取结构色 `--primary`（`DESIGN.md` 护栏 12），块内每项说明取自 `descriptions`、`✻ 已改` 由 `defaults` 比较得出——文案与基准全部服务端下发，前端**零中文表**（实验项 ⚗ 与「（影响报告）」后缀由 `features.experimental` / `report_affecting` 同源下发）；保存语义**即改即存**（与 TUI「改一项存一项」一致）——checkbox/radio 改动即 POST，自由文本路径经各自「保存」按钮提交，对比指数池经添加/删除/重置动作提交；提交期间控件禁用，成功回读该项最新值，失败恢复改动前值并显示错误。`error_code` 驱动分支（BAD_PARAM 400 / 同源 403 / CONFIG_WRITE_FAILED 500），中文文案直显服务端不前端硬编码。
- **状态区**：健康卡片（`/api/health` 60s 缓存 + 「重新检测」`?fresh=1` 强制重测）+ 历史运行记录卡片（最近 10 条，5s 短缓存）。
- **日志查看卡**：⑦ 日志查看（级别 `<select>` + 「加载日志」按钮）——**手动加载不自动轮询**（对齐设计文档「自动刷新高 IO → 手动刷新」）；`loadLogs()` fetch `/api/logs`，每条 `<details class="log-entry log-{level}">` 原生折叠 + `<pre class="log-body">` 展开 body；`is_decorative` 置灰；**全程 `textContent`/DOM API**（XSS 纪律，日志 body 含外部数据源名不可信）。
- **结果映射**：按 exit_code 映射展示（0 成功 / 1 部分失败黄色告警 + 通用建议 / 2 严重红色 + 提示看日志）；failed/exit_code=2 隐藏无效产物按钮；失败提供「重新生成」（上传文件已消费，引导重新上传）。
- **静态服务分离**：web 只服务自身 `static/`；报告资产（chart.min.js 等）经 `/api/reports` 从 output_dir 提供。`main.js`/`style.css` 带 `?v={APP_VERSION}` 版本查询串防浏览器缓存旧 JS。

#### 1.8.9 安全防护矩阵

| 威胁 | 防护 |
|:-----|:-----|
| 路径穿越（预览/下载） | `send_from_directory` 内置 `..` 净化 + 扩展名白名单 |
| 伪装 xlsx（改扩展名） | PK zip 魔数校验 + 预检兜底转 400 |
| 超大文件 / zip-bomb | 10MB 上限（读流计数 + `MAX_CONTENT_LENGTH` 兜底） |
| 路径穿越（上传文件名） | 服务端 uuid 重命名，丢弃原始文件名 |
| 恶意/损坏文件 | 内容预检（行数上限 5000 + 空持仓拒绝） |
| 拒绝服务 | 单 worker 队列 + 队列满 429；健康检查 60s 缓存；前端轮询节流 |
| 日志隐私 | 访问日志不记录文件名/持仓内容/绝对路径 |
| 局域网暴露 | 默认仅 127.0.0.1；全零监听时启动警告（无内建认证） |
| 跨站写请求（副作用写操作） | `/api/runs`、`/api/config/edit`、`/api/whatif`、`/api/cache/cleanup` 四个 POST 复用 `_is_same_origin()`（Sec-Fetch-Site + Origin 校验），失败 403；无 CSRF token 依赖 |

#### 1.8.10 与 TUI/CLI 的差异要点

| 差异 | TUI/CLI | Web |
|:-----|:--------|:-----|
| 业务逻辑 | `report/orchestrator.py` + `cache/operations.py` | 同左（复用，管线零改动） |
| 进度 | 终端输出 | 事件缓冲 + 浏览器轮询 |
| 并发 | 单线程同步 | 单 worker 串行队列（HTTP 线程 + worker 线程） |
| 参数默认 | 菜单选择 / argparse | 表单回填 config 快照 |
| 配置编辑 | TUI 主菜单改项即写即存 | 配置编辑面板（白名单 9 组）即改即存，写前 .bak 备份，同源守卫 |
| 产物定位 | 直接写 output_dir | run 快照 output_dir + `/api/reports` 服务 |
| 启动防护 | 无 | 端口检测 + output_dir 写锁 |
| 生命周期 | 会话 / 单次 | 常驻服务 |

#### 1.8.11 配置编辑（TUI / Web / CLI 同一编辑层）

配置编辑的职责边界：**「能改什么」由白名单唯一确定，「怎么改」由共享编辑层单源执行**（含日志设置六项 `logging.*` → `write_logger_config`，与 TUI `[D]→[L]` 面板同一批键与同一校验）——Web `POST /api/config/edit`、TUI 配置面板（`_apply_edit` 外壳）与 CLI `config set` 同走 `config/edit_ops.py::apply_config_edit`，三渠道同一函数、同一强度；不引入任何白名单之外的新配置项。CLI 的动作型键（`comparison_indices` / `llm_providers.priority`）与密钥文件不在 `config set` 入口内（前者指向 TUI/Web 或 `--llm-provider-order`，后者按手册维护）；`scheduler.*` 走 `apply_scheduler_block` 单写入原语（校验在 `config/_scheduler.py`，Web 面板与 CLI 共用）。核心实现 `config/edit_ops.py`（`web/config_edit.py` 仅保留 `get_config_edit_surface` 呈现面组装）：

- **白名单 `config_edit_whitelist`**（定义于 `config/edit_ops.py`，小写模块级 dict，唯一事实来源）：点分键 → `{"kind", "target", "writer"}`。`kind` 取 `str`/`bool`/`enum`/`action`；`target` 取 `config`/`llm_settings`/`features`/`llm_providers`/`logging`（落盘目标文件）；`writer` 取 `scalar`/`anonymization`/`llm`/`llm_scalar`/`llm_providers`/`features`/`comparison_indices`/`logging`（写入分派器）。全集 9 组 56 条键（前端把「功能开关」组按 surface 下发的 `groups` 渲染成四块，故界面共 11 块）：自由文本路径 3（holdings_dir / holdings_filename / output_dir）、报告章节开关 5、匿名化 1 键 4 档、对比指数池 1 键（增/删/重置默认）、LLM 多链线路优先级 1（llm_providers）、LLM 调优参数 6（`LLM_TUNING_SPECS`：thinking 并发 / 模块并发 / 重试 / 整链重试等待 / 总时间预算 / 日费用上限）、LLM 分析章节开关 7（enabled_llm，键域=注册表 LLM 模块全集）、功能开关 26（features.json 全注册表：呈现与体验 1 + 分析增强 16 + 独立章节与回放 5 + 机制与诊断 4；分组、默认值与显示名同源，面板显示名与「影响报告」标记由 surface 下发，前端不写字典）、日志设置 6（`logging.*`）。`scheduler.*` 四字段不在白名单内，走独立写入原语 `apply_scheduler_block`（校验在 `config/_scheduler.py`）。
- **写入分派（共享层 `_dispatch_write` 单点，三渠道无各自实现）**：config.json 顶层标量 → `set_config`（`_PATH_CONFIG_KEYS` 路径键自动反绝对化）；嵌套 dict（comparison_indices）→ 读合并后 `set_config` 整块写；`anonymization.mode` → `set_anonymization_mode`；`enabled_llm.*` → 共享 `write_llm_settings`（`config/_llm_settings.py` 公开原语，自 `tui/handlers_config.py` 抽取，TUI 改委托、行为零变化；保留注释 + mkstemp + `os.replace` 原子写 + `get_llm_config()` 缓存刷新）；功能开关全注册表（含独立整章与关联产物）→ `save_feature_overrides`（features.json）。`[C]` 四块来源不同但写路径同源——顶层 `config`、LLM `llm_settings`、整章/关联产物 `features`，目标键由 `chapter_registry.chapter_edit_key()` 派生。
- **类型/枚举校验（共享层 `_normalize_plain_value`/`_apply_comparison_action`，Web 400 / TUI 黄色提示行同一规则）**：`set_config` 不做值类型/模式验证，规则集中在共享编辑层——kind=str 须非空字符串（trim 后判空），`holdings_filename` 额外拒绝路径分隔符（防破坏文件定位）；kind=bool 仅接受 `True`/`False`（`1`/`"true"`/`0.0` 等一律拒绝）；kind=enum 严格匹配合法枚举值（大小写/空白/非字符串拒绝）；对比指数池 code 非空且长度 ≥3、拒绝路径分隔符（防 `../` 穿越）、拒绝重复入池，name 非空。校验失败 Web 统一 400 BAD_PARAM（服务端中文文案）。
- **写前备份 `config_backup_file`**：写目标文件前单槽 `.bak` 备份（`core/atomic_write.copy_file_atomic` 原子复制），原文件不存在时返回 None（不备份）；单槽轮转——第二次写覆盖上一版 `.bak`，供手动还原（`.bak` 改回原名）。
- **同源守卫**：`_handle_config_edit` POST 复用 `_is_same_origin()`（Sec-Fetch-Site + Origin 校验，同源或非浏览器放行）——Web 无内建认证/无 CSRF token，副作用写操作以此兜底跨站写请求，失败 403。
- **匿名化读路径一致性**：TUI 隐私安全状态（`tui_menu._show_privacy_and_security_status`）与 Web 系统信息（`core/system_info.build_system_info`）读顶层 `anonymization.mode`（非不存在的 `features.anonymization.mode`），两个面板匿名化状态显示与 `set_anonymization_mode` 写入键一致。

[↑ 回到顶部](#目录)

---

## 2. 数据获取层详细设计

### 2.1 Provider Chain 路由与 fallback

Provider Chain 采用**职责链（Chain of Responsibility）模式**：每个数据类型定义一条优先级链路，`fetch_with_fallback()` 依次尝试，失败则递补下一 Provider。

#### 数据的默认链路

```
                           Provider Chain 结构
 ┌──────────────────────────────────────────────────────────────────┐
 │  price_stock:   腾讯财经 (qt.gtimg.cn)  →  新浪财经 (hq.sinajs.cn)│
 │  price_fund_otc: api.fund.eastmoney.com → 新浪场外净值（跨厂商标）  │
 │  price:         腾讯财经 → 东方财富（行情策略链：开盘状态判断）      │
 │  history_stock:  腾讯财经 K 线          →  新浪财经 K 线          │
 │  history_index:  腾讯财经 K 线          →  新浪财经 K 线          │
 │  history_index_us: 新浪财经 K 线（端点取空） → 腾讯财经 K 线       │
 │  history_fund_otc: 天天基金 pingzhongdata → 东方财富净值分页       │
 │  industry:       东方财富 push2          →  行情页 quotedata      │
 │  fund_rank:      天天基金（直达）                                   │
 │  fund_hold:      天天基金 → 同花顺官方（需 key）                   │
 │  bond_yield:     akshare bond_zh_us_rate（国债收益率，无风险利率）│
 └──────────────────────────────────────────────────────────────────┘
```

`preferred_provider` 可在 `config.json` 中手动将某类型的首选 Provider 调整到链首。

#### 失败检测

以下情况均视为 Provider 失败，触发递补：
- 返回空数据（`None` 或空列表）
- HTTP 错误（4xx/5xx）
- JSON 解析异常
- 超时/断连/DNS 解析失败
- 数据验证未通过（如名称不匹配、price_date 非当前交易日）

#### fetch_with_fallback() 完整流程

```
请求 data_type + code
     │
     ▼
┌─────────────────┐
│ cache_get(key)  │─── 命中且未过期 ───→ 直接返回缓存数据
│ （先检查缓存）   │
└────────┬────────┘
    未命中或过期
         │
         ▼
┌─────────────────┐
│ 获取 chain 列表  │←── _DEFAULT_CHAINS[data_type] + preferred_provider 覆盖
└────────┬────────┘
         │
         ▼
    ┌────┴────┐  ←── 对 chain 中每个 provider_name 循环
    │         │
    ▼         │
┌──────────────────────┐
│ is_circuit_broken()  │─── 已熔断 → 跳过，尝试下一个 Provider
└────────┬─────────────┘
    未熔断
         │
         ▼
┌──────────────────────┐
│ _try_provider_fetch  │
│  → catch 异常         │
│  → 调用 fetch_fn()    │
│  → validate()         │
│  → transform()        │
└────────┬──────────────┘
         │
    ┌────┴────────────┐
    │                 │
    成功              失败
    │                 │
    ▼                 ▼
┌──────────┐   ┌──────────────┐
│success() │   │ 传输级异常?   │
│cache_set │   ├─────┬───────┤
│返回数据   │   │ YES │  NO   │
└──────────┘   │     │       │
               ▼     │       │
          ┌────────┐ │       │
          │failure │ │       │
          │熔断计数 │ │       │
          └────────┘ │       │
                     ▼       ▼
                ┌──────────────┐
                │ 不计入熔断   │
                │ 继续下一链路  │
                └──────────────┘
                         │
                    ┌────┘
                    ▼
           全部 Provider 失败?
           ┌──────┴──────┐
          YES              NO（回到循环顶）
            │
            ▼
    ┌─────────────────┐
    │ 过期缓存降级      │─── cache_get(key, CACHE_WEEKLY=7 天)
    │ (stale fallback) │     命中? → 返回旧数据
    └────────┬────────┘     未命中? → 返回 None
             │
             ▼
    ┌─────────────────┐
    │ 全链路不可用      │─── 调用方处理（占位文本/异常）
    └─────────────────┘
```

**消费方透明设计**：市场行情批量请求时（如 `report/market_value.py`），每个代码独立触发 Chain，失败资产在汇总日志中列出，不影响其他资产获取。

#### 传输级瞬时失败的同源重试

`fetcher/chain.fetch_with_fallback` 在**落到下一槽之前**，对**传输级**失败（超时 / 连接错误 / 远端断开「Server disconnected」）做一次**同源退避重试**（`_TRANSIENT_RETRY_ATTEMPTS = 1`，基础退避 `_TRANSIENT_RETRY_BACKOFF = 0.6s` 指数增长 + 抖动）。

- **只重试传输级**：这类错误多为瞬时抖动，同源重试常即成功，避免过早降级到质量更低的槽位、也避免把偶发抖动累计成熔断（行业分类 push2 的 `Server disconnected`、DataSinking 的偶发断连即属此类）
- **不重试代码级空结果**：Provider 正常返回但无该代码数据（`None`）时重试毫无意义（同一请求同一答案），且会白耗第三方日配额（DataSinking 免费档 8191 篇/日）
- **传输级失败必须上抛给链路（provider 层不得自行吞成返回值）**：链路的传输级判据**只认异常**（`_try_provider_fetch` 捕获异常 → `TRANSPORT_FAILURE`），若 provider 把超时/断连 `return None`，链路会当成「代码级空结果」——同源重试不触发、``record_failure`` 不计、诊断文案把「握手超时」报成「返回空」（实测事故：DataSinking SSL 握手超时被记为返回空，既不重试也不熔断，单标的每篇白等 20s）。故 provider 的代码级结果（401/403/404/非 200/非 JSON）返回 `None`，传输级失败**重试耗尽后上抛**；弱链路承装的直连调用方需自行试/except 降级（如 `fetcher/financial_report._fetch_index` → 转备源）
- **provider 自陈失败原因（「返回空」不再笼统）**：provider 返回 `None` 前可经 `providers/utils.set_last_reason("原因")` 写下一行可读短句，链路（`chain._try_provider_fetch`）读到后**替换笼统的「返回空」**并同步进失败诊断（`FailureDiagnostics` → 报告数据源矩阵）。二者在运维上是完全不同的信号——「源故障」要排查网络/凭据（如 `HTTP 500`、`凭据无效`），而「该文档确实没这一节」（如 DataSinking 对没有「管理层讨论与分析」的季报返回 404）是正常业务结果（实测：该场景被笼统记成「返回空」，排查时被误读为源不可用）。载体**按线程隔离**（批量取数多线程）且**消费即清**（不串到下一次调用）；provider 未设置时措辞逐字不变。
- **挂起型不重试（避免放大等待）**：区分**快速失败**（连接被拒/重置/DNS 立即失败 → 重试有效）与**挂起**（等到超时 → 重试只会把等待放大成 N × 超时）。判据：本次尝试耗时 ≥ 超时预算 × `HANG_ELAPSED_RATIO`（0.5）即视为「主机不可达」，不再重试、直接交链路失败（计入熔断）；实测：20s 预算下挂起型单请求从 63s（3 次）降到 20s（1 次），持续不可用时靠熔断快速跳过。判据由 `providers/utils.build_transient_retry_judge` 统一提供，`datasink` / `hithink` / `cninfo` 三者共用
- **连接级重试脚手架单源**：`providers/utils.with_connect_retry(request_fn, timeout=…, log_tag=…, label=…, before_attempt=…)` 收敛 `datasink` / `hithink` / `cninfo` 三处的连接级重试（共用 `providers/utils.CONNECT_RETRY_POLICY`：线性 1s/2s、共 3 次尝试）——耗时统计、挂起判据与警告、重试日志、每次尝试前的限速许可统一在此，各来源差异只用 `log_tag` / `label` / `before_attempt` 表达（避免同一约束复制三份、改一处漏两处）。**无链路承装的直连调用方**在调用点吞异常返回 `None`（如 `cninfo` 三条直连路径）维持降级契约；经链路的 provider 槽由链路承接上抛。**cninfo 直连路径的额外护栏**：公告 PDF 用独立的更宽超时（60s，年报原文几十 MB，与元数据接口共用 20s 必然失败）；挂起型失败后**本会话短路该主机**（`_mark_host_unreachable`，后续请求不发 HTTP 直接失败），把「N 篇文档 × 超时预算」降为 1 次
- **次数有界**：每个 Provider 每次调用最多 1 + 1 次请求；仍失败才计入熔断计数器并落下一槽
- **口径单一来源**：退避算式（固定/线性/指数 + 抖动 + 上限）、尝试次数与「哪些异常算瞬时」由 `core/retry.py` 统一提供（`RetryPolicy` / `is_transient_exception` / `retry_transient`）——链路、各 provider 的连接级重试、akshare 超时重试与 HTTP 429 退避共用同一执行器，差异只用策略参数表达（约束 C26）；「两次请求至少间隔多久」见 `core/throttle.py`（约束 C27）

### 2.2 三层熔断架构

> **术语约定（熔断体系双维命名）**：本项目熔断体系分两维描述——**熔断器组件**（数据源熔断器 `core/provider_registry.py` / 指标熔断器 `analysis/circuit_breaker_wrapper.py::IndicatorBreaker` / LLM 端点熔断器 `llm/circuit_breaker.py`，三者构成「三级熔断体系」）+ **DataSourceRegistry 流程层**（本节三层：熔断预检 / Provider 级 / 冷却试探恢复）。本节聚焦 DataSourceRegistry 内部流程层；指标/LLM 熔断器参数见下方对比表及各自模块说明。

由 `DataSourceRegistry` 单例（`src/python/core/provider_registry.py`）统一管理，采用**双锁设计**（`_provider_lock` + `_cache_lock`）使熔断操作和会话缓存互不阻塞。

```
┌──────────────────────────────────────────────────────────────────┐
│  DataSourceRegistry（单例）                                       │
│                                                                   │
│  ┌─ 第 1 层：熔断预检 ──────────────────────────────────────┐   │
│  │  get_effective_strategy(code_type, chain, market_open)      │   │
│  │  → QDII/港股恒为 LIVE_FETCH                                 │   │
│  │  → 非交易时段 → CACHE_ONLY（只读缓存，不发起 HTTP）           │   │
│  │  → 全链熔断 → CACHE_ONLY 降级                               │   │
│  │  → 正常盘中 → LIVE_FETCH                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ 第 2 层：Provider 级熔断 ───────────────────────────────┐   │
│  │                                                              │   │
│  │  ┌─────────┐    连续 3 次     ┌──────────┐    冷却期满      │   │
│  │  │  正常    │ ───────────────→ │  熔断中   │ ─────────────→ │   │
│  │  │ (Closed) │                 │ (Open)   │                 │   │
│  │  └────┬────┘                 └────┬─────┘                 │   │
│  │       │                           │                        │   │
│  │       │ record_success()          │ 冷却期满自动解除       │   │
│  │       │ ← 重置熔断计数             │ 重置 failures=0       │   │
│  │       │                           │ 放行一次试探           │   │
│  │       │                           │                        │   │
│  │  仅传输级异常（超时/断连/DNS/5xx）触发 record_failure()      │   │
│  │  代码级空结果（API 正常返回 None）不计入熔断计数器            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ 第 3 层：冷却试探恢复 ─────────────────────────────────┐   │
│  │  cooldown_secs 期满后 is_circuit_broken() 自动             │   │
│  │  1. 设置 is_skipped = False                               │   │
│  │  2. 重置 consecutive_failures = 0                         │   │
│  │  3. 返回 False（未熔断），下次调用即为试探                  │   │
│  │  试探成功 → record_success() → 恢复正常                    │   │
│  │  试探失败 → 重新熔断                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ 会话级缓存（C4 约束） ──────────────────────────────────┐   │
│  │  domain = "industry" / "industry_rest" / "extended" / ...   │   │
│  │  session_cache_get/set(domain, code)                        │   │
│  │  NOT_FOUND sentinel 区分 None vs 未缓存                     │   │
│  │  2000 条/domain O(1) 淘汰                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

#### 熔断参数对比

| 维度 | 单股票 API | 批量 API（eastmoney_industry） | LLM 熔断器 | 指标熔断器（IndicatorBreaker） |
|:-----|:----------|:-----------------------------|:----------|:------------------------------|
| 实现位置 | `core/provider_registry.py` | `core/provider_registry.py` | `llm/circuit_breaker.py` | `analysis/circuit_breaker_wrapper.py` |
| 熔断阈值 | 连续 3 次传输级失败 | 连续 6 次传输级失败 | 连续 3 次 | 单指标连续 3 次异常（除零/空数据/置信度不足） |
| 冷却时长 | 指数退避 60s→300s→900s→3600s | 120s | 60s | 24h（静默，不阻塞其他指标） |
| 试探次数 | 冷却期满放行一次 | 冷却期满放行一次 | 半开状态放行一次 | 冷却期满后自动复位重试 |
| 恢复条件 | 试探成功 → record_success | 试探成功 → record_success | 半开成功 → 关闭熔断 | record_success → 复位计数 |
| 持久化 | `data/state/circuit_breaker.json` | `data/state/circuit_breaker.json` | 会话级（无持久化） | `data/state/metrics_breaker.json` |

**指数退避**：单股票 API 熔断器冷却时间采用指数退避策略（60s→300s→900s→3600s），每次连续失败冷却时长按退避等级递增，成功恢复后重置为基础值。

**跨会话持久化**：熔断器状态持久化到 `data/state/circuit_breaker.json`，与 `data/cache/` 隔离，避免缓存清理误删。会话重启后恢复熔断记忆。

**统一熔断网关**：`core/circuit_breaker.py` 的 `CircuitBreakerGateway` 聚合 Provider 级熔断（`provider_registry.py`，HTTP 传输层，管"某个数据源能不能调用"）、LLM 端点熔断（`llm/circuit_breaker.py`）和指标熔断器（`analysis/circuit_breaker_wrapper.py`，业务层，管"某类数据是否跳过"）三者的状态查询与管理，`gateway.summary()` / `get_all_breaker_status()` 统一返回三类状态报告，单入口消除运维复杂度。

#### Chain 自动注册

`fetcher/chain_config.py`（模块加载注册，符号经 `fetcher/chain.py` 门面 re-export）在模块加载时自动调用 `get_registry().register_default_chains()`，从 `_DEFAULT_CHAINS` 配置注册所有 provider 和 chain。在 `register_default_chains()` 中 per-provider 配置 tier/timeout/failure_threshold/cooldown_secs（如 eastmoney_industry 阈值 6 次/冷却 120s）。

#### 策略选择器

`DataSourceRegistry.get_effective_strategy()` 根据代码类型、熔断状态、市场时段返回获取策略：

```
输入: code_type, chain, market_open
           │
           ▼
    ┌──────────────┐
    │ 代码类型感知   │
    ├──────────────┤
    │ QDII/港股?   │─── YES ──→ LIVE_FETCH（不受 A 股时段限制）
    └──────┬───────┘
           NO
           ▼
    ┌──────────────┐
    │ 交易时段检测   │
    ├──────────────┤
    │ 非交易时段?   │─── YES ──→ CACHE_ONLY
    └──────┬───────┘
         交易时段中
           ▼
    ┌──────────────┐
    │ 全链熔断?     │
    ├──────────────┤
    │ is_chain_   │─── YES ──→ CACHE_ONLY（降级）
    │ broken()?   │
    └──────┬───────┘
           NO
           ▼
      LIVE_FETCH
```

#### 统一获取入口 `fetch_or_cached()`

`DataSourceRegistry.fetch_or_cached()` 封装了策略选择 → 执行获取 → 会话缓存的完整流程：

```
fetch_or_cached(code, code_type, fetch_fn, chain, cache_domain, cache_key_fn)
    │
    ▼
get_effective_strategy(code_type, chain)
    │
    ├── LIVE_FETCH: 执行 fetch_fn(code) → session_cache_set(domain, code, result)
    │
    └── CACHE_ONLY:
        ① session_cache_get(domain, code) → 命中则返回
        ② 文件缓存 cache_get(cache_key_fn(code), 7 天)
           → 设置 _cache_date_mismatch 标记
           → 写入 session cache → 返回
```

#### 数据获取全局超时 `phase_timeout()`

`core/provider_registry.py` 提供 `phase_timeout` 上下文管理器，用于数据获取阶段超时保护：

```
with phase_timeout(seconds=120, phase_name="data_fetch") as ctx:
    for code in codes:
        if ctx.expired: break          # 超时退出
        fetch_market_data(code)        # 已获取的数据保留
        ctx.check()                    # 超时抛 TimeoutError
    # 超时后：已完成的数据保留，未完成的以占位处理
```

- 超时不影响正在运行的 HTTP 线程（Python 无法 kill 线程），结果被丢弃
- 不支持嵌套（检测到嵌套时抛 RuntimeError）
- Context 提供 `expired`、`elapsed`、`remaining`、`check()` 四个接口

#### 审计报告

`DataSourceRegistry.generate_status_report()` 输出所有 Provider 的运行时状态（可用性、连续失败次数、熔断状态、冷却剩余时间、总成功/失败次数等），供调试和监控使用。

### 2.3 Fetcher 调度架构

`src/python/fetcher/` 各模块按数据类型独立封装：

```
fetcher/
├── price.py            股票/ETF 最新价 + 场外基金净值 + 00 代码降级
├── index.py            A 股/美股指数（直调 Provider，不走 Chain）
│                       + fetch_index_history 历史日线（走 Chain，C6 约束）
├── fund.py             基金排名/持仓/基准（天天基金数据 + 同花顺官方备源）
├── fund_manager.py     基金经理数据（天天基金 HTML 解析）
├── industry.py         行业分类+概念板块（push2 双链路）
├── chain.py            fallback 路由执行 + 对外门面（子模块符号经此 re-export）
├── chain_config.py     Provider 优先链定义 + 覆盖（preferred/exclude）+ 链健康判定
├── chain_diagnostics.py  链路失败诊断（失败原因短句）+ 命中归属登记
├── chain_incremental.py  历史序列增量合并（payload 版本闸门 + 按日合并/连续性校验）
├── batch.py            批量并行调度（BatchDispatcher；间隔限速实现见 core/throttle.py）
├── akshare.py          AKShare 数据获取（备用数据源）
├── bond_yield.py       债券收益率数据（Rf 单值 + 10Y 历史序列双键）
├── index_valuation.py  指数估值历史（乐咕 PE/PB 月频，市场温度估值因子）
├── news.py             新闻数据获取
└── history_diff.py     持仓快照差异计算（纯计算，无 I/O）
```

**并行预热**：`preload_cache()` 对 preload 组使用 `ThreadPoolExecutor` 并行获取，减少串行等待。

**菜单驱动**：菜单 [1] 清除 + 重拉 refresh 组，菜单 [2] 清除 + 重拉 preload 组，均复用 fetcher 模块的预热入口。

### 2.4 关键机制

#### 2.4.1 00 代码降级

**问题**：OTC 基金代码与 A 股代码前缀重叠（均以 `00` 开头），`is_a_share_code()` 无法区分。`price.py` 和 `portfolio_history.py` 需要「先按名称消歧，再降级」。

**判定支持函数**（`core/code_utils.py`）：

| 函数 | 策略 | 用途 |
|:-----|:------|:------|
| `is_otc_code_overlap(code)` | 仅前缀检测（00 开头） | 快速预筛——是否值得尝试基金净值 API |
| `is_otc_fund_by_name(name, code)` | 名称+代码双维度 | 00 代码+名称含基金关键词→确认为场外基金 |
| `is_a_share_stock(name, code)` | 名称+代码双维度 | **持仓路由统一入口**：A 股个股（排除 00 重叠区场外基金），历史/分红/行业/估值/扩展数据均以此过滤，禁止只用 `is_a_share_code(code)` |

`_OTC_FUND_NAME_KW = ("混合", "纯债", "短债", "中短债", "利率债", "信用债", "债券", "指数", "股票", "货币", "联接", "增利")`

**price.py 降级流程**：

```
fetch_market_data(code, expected_name)
    │
    ▼
┌──────────────────────────────────────┐
│ 代码类型路由（名称优先消歧）           │
│ if is_otc_code_overlap(code) and     │
│    is_otc_fund_by_name(name, code):  │
│   data_type = "price_fund_otc"       │←── 直达: eastmoney → sina_fund
│ elif is_exchange_fund or is_a_share: │
│   data_type = "price_stock"          │←── 主链路: tencent → sina
│ else:                                │
│   data_type = "price_fund_otc"       │
│                                      │
│ _needs_degrade = (data_type=="price_stock" AND code.startswith("00"))
└────────────┬─────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ price_stock 链路   │──→ 成功? ──→ 返回结果
    │ tencent → sina    │
    └────────┬───────────┘
        失败（返回 None）
             │
       ┌─────┴─────┐
       │ 需要降级?  │──→ NO ──→ 返回 None（最终失败）
       │（00 代码?）│
       └─────┬─────┘
           YES
             │
             ▼
    ┌────────────────────┐           ┌──────────────────┐
    │ price_fund_otc 链路 │──→ 成功? ──→ 记录"降级成功"  │
    │ eastmoney 净值     │           └──────────────────┘
    └────────┬───────────┘
        失败（返回 None）
             │
             ▼
    记录"降级也失败"
    返回 None
```

**关键设计保障**：
- **价格缓存键按路由分域**：`price_stock_{code}` / `price_fund_otc_{code}`。00 重叠区同一代码可能是两只不同证券（`002943` 既是深市股票「宇晶股份」也是场外基金「广发多因子」），共用键会让先取到的路由污染另一路由；而收市后基金走 CACHE_ONLY 只读缓存，一旦串味即成持久错误值（实测：基金成分股取扩展数据时把宇晶股份 28.98 写进共享键，基金被读成 28.98）。
- **持仓路由统一以名称消歧**：历史 K 线（`portfolio_history` / `_report_factor_metrics`）、分红（`category` / `html_builders` / `cache.operations`）、行业（`batch_fetch_industry_data` 调用方预过滤 / `_get_industry_avg_pe` / `news_correlation`）、估值分位（`orchestrator`）、风格扩展数据（`fund_style_classify`）、资产构成图兜底（`chart_data_builder`）一律用 `is_a_share_stock(name, code)` 过滤，不再只用代码前缀。
- 主链路成功时永不触达降级，零误判风险
- 降级成功/失败均有日志区分（含资产名称和期望名称）
- `portfolio_history.py` 中 `fetch_with_incremental_fallback()` 对返回空列表的首个 provider 同样执行递补，非简单返回

**`_price_cache_fresh` 收市后新鲜度验证**：

```
_fetch_with_cache_refresh() 返回数据后
    │
    ▼
┌─────────────────────┐
│ is_market_open()?   │── YES → 盘中，短 TTL 已保证实时性，无需验证
└────────┬────────────┘
        NO（盘后/盘前/午间休市）
         │
         ▼
┌─────────────────────┐
│ price_date ≥ 该路由  │── NO（跨日残留）
│ 允许的最新日期?      │
└────────┬────────────┘
        YES
         │
         ▼
┌──────────────────────────────┐
│ 场内且 T 日已收盘(now ≥ 15:00) │── YES（盘中残留）
│ 而缓存写于 T 日 15:00 之前?     │
└────────┬──────────────────────┘
        NO（午间休市等 T 未收盘）
         │
         ▼
      新鲜缓存，返回

残留路径 → cache_clear(cache_key) → 强制刷新 → 重新走 Provider Chain → 成功后自动写回缓存；
强制刷新后全链仍不可用 → 退回刷新前那份过时缓存（不因清缓存反而丢数据）
```

两道门禁的语义分工：

- **日期门禁**：`price_date` 早于「该路由允许的最新日期」→ 跨日残留（例如盘中因 Tencent 不可用降级写入 EastMoney 的上一交易日净值），收市后清除重取。阈值按路由分域——场内须等于最近交易日；场外官方净值中 QDII 合法为 T-1，国内场外 T 日当晚披露、盘后须到 T（用 `is_qdii_extended` 按持仓名细分，与「价格更新状态」同源）。
- **收盘时点门禁**：`price_date == T` 只说明「数据属于 T 日」，但 T 日收盘价只在 15:00 之后才成形。若缓存在 T 日盘中写入（如 13:01 的 29.35），盘后或次日盘前仅凭日期相等就沿用，会把盘中价当成 T 日收盘价，使「本日盈亏」与「快照环比」系统性偏离真实涨跌。故当 T 日已收盘（`now ≥ T 15:00`）时，要求缓存写入时刻 ≥ T 日 15:00；午间休市（T 日尚未收盘）不施加此约束——上午收盘价即当时最新价。缓存写入时刻由 `_cache_captured_at()` 经 `cache.get_cache_age()` 反推（`cache.get` 只返回 `_data`，不暴露 `_ts`）。
- **调用点接线**：`report/market_value.py` 的 `CACHE_ONLY` 分支与 `_fetch_price_with_cache_refresh` 均须传 `cache_key`（不传则跳过收盘时点门禁，兼容旧调用）。

#### 2.4.2 指数独立获取

指数数据由 `fetcher/index.py` 直调 Provider，**不走 Provider Chain**：

```
fetch_index_data(code)
    │
    ├── A 股指数 (000001/399001/...)
    │     腾讯财经 (qt.gtimg.cn)
    │         ↓ 失败
    │     新浪财经 (hq.sinajs.cn)
    │         ↓ 均失败
    │     过期缓存降级
    │
    └── 美股指数 (.DJI/.IXIC/.INX)
          新浪财经 (hq.sinajs.cn, JS 变量解析)
              ↓ 失败
          腾讯财经 (qt.gtimg.cn)
              ↓ 均失败
          过期缓存降级
```

**不走 Chain 的原因**：
- 指数无熔断器适用的"故障单元"概念（单指数失败不意味所有指数都失败）
- 双链路 fallback 硬编码在 index.py 内部，双向链路（A 股腾讯→新浪，美股新浪→腾讯）
- 双链路均失败时降级过期缓存

#### 2.4.3 Fallback 日志增强

所有 Provider Chain 的 fallback/降级日志均包含资产 `[code]` 和名称标签：

| 日志类型 | 示例 |
|:---------|:------|
| API 返回空 | `[price_stock] [002943] 新浪财经 返回空，尝试下一链路` |
| 链路切换 | `[price_stock] [002943] 新浪财经 成功` |
| 全链路降级过期缓存 | `[price_stock] [002943] 全部 Provider 不可用，降级使用过期缓存` |
| 00 代码降级触发 | `[price] [002943 广发多因子] 股票链路全部失败，降级尝试东方财富净值链路` |
| 00 代码降级成功 | `[price] [002943 广发多因子] 降级成功——通过场外基金链路获取到净值` |
| 汇总失败资产 | `市场行情获取：14 成功，1 失败；失败资产: ['广发多因子(002943)']` |

### 2.5 数据源适配契约（内置，不可关闭）

接入一个数据源要做的三件事被拆成三个可独立检验的小函数，**声明在前、代码在后**：

| 契约环节 | 实现位置 | 本项目的落地方式 |
|:---------|:---------|:-----------------|
| 参数转译 `transform_query` | `SourceAdapter.transform_query` | 默认恒等；子类可补默认值/拼查询参数 |
| 抓取 `extract_data` | 各子类 | **委托既有 provider 函数**，不复制任何 HTTP 与解析逻辑 |
| 映射到标准字段 `transform_data` | `SourceAdapter` 默认实现 | 声明式 alias 归一（见下），子类可覆写 |

默认映射由三样**数据**驱动，不含逐字段的手写赋值：

| 声明 | 位置 | 语义 |
|:-----|:-----|:-----|
| 标准字段记录类 | `schemas/datasource_fields.py`（`DOMAIN_RECORDS` 登记） | 字段名与类型的唯一来源；`float` 缺失取 `0.0`、`float \| None` 取 `None`（该源不提供此字段）、`str` 取空串；数值一律经 `core.num_utils.safe_num` 归一（防 NaN/±inf 污染下游） |
| `aliases` | 适配器类属性 | `{上游字段名: 标准字段名}`——字段改名的唯一表达处（如净值源 `nav` → `price`） |
| `defaults` | 适配器类属性 | `{标准字段: 该源在上游未提供或取值不可用时的缺省}`；未声明则按类型注解推导。合法的 `0.0` 不被缺省覆盖 |

**输出恒为全部标准字段**：同一域的不同源产出同键同构 dict，下游无需为「某源少两个键」写分支。
源身份字段（`source`/`source_api`）由适配器强制提供，上游自报的来源不参与映射——否则「来源」会与「实际生效链路」脱钩（如东方财富回落到天天基金时自报`天天基金`）。

**接入链路的方式**：`adapter_chain_slots(domain)` 把某域的适配器映射为 Provider Chain 的两个入参
（`provider_fn_map` / `transform`），因此链路顺序、缓存键、熔断、降级全部复用
`fetcher/chain.fetch_with_fallback`，**不新造第二条获取路径**。行情域试点见
`fetcher/price.py::_price_chain_slots()`——恒返回适配器映射（已内置不可关闭）；
适配器不可用（导入失败等）时保守回落既有手写映射对象本身（逐字节行为不变）。

**试点范围与等价性**：仅行情域三源（腾讯/新浪/东方财富），与既有转换函数逐源等价，
唯一有意差异是东方财富既有转换函数不含 `market_cap`/`pe` 两个键而契约恒为全字段（补 `None`）——
下游消费方一律 `.get()` 读取，取值语义不变。等价性由 `test_quote_adapter_parity.py` 锁定。
**存量 provider 不回改**：新数据源/新字段先走契约，既有源维持现状。

**自检与体检**：`survey_adapters()` 离线核验（域登记、alias/defaults 指向真实标准字段、
`transform_data` 对合成样本输出恰好标准字段集），自身不抛异常；`doctor` 的「数据源适配」组
（`--offline` 可用）报告适配器数量、各域与自检结论，并标注契约路径是否已由开关启用——
**契约未启用时声明与自检仍可核验**，这正是接入新数据源前要看的。

[↑ 回到顶部](#目录)

---

### 2.6 数据源记录-回放（测试基建，无开关）

把**上游真实响应体**录进仓库、此后离线回放，用来回归「真实响应体的解析/归一路径」——
既有单元测试全部喂**手工构造的假响应**，那是「我以为上游长什么样」；字段改名、加前后缀、
换分隔符、返回 HTML 错误页这类真实回归测不出来（实施设计文档「数据源记录-回放测试实施设计」）。

| 组成 | 位置 | 职责 |
|:-----|:-----|:-----|
| 回放引擎 | `core/cassette.py` | 请求键归一、cassette 存取（原子写盘）、回放/录制传输、解析校验；**只依赖 stdlib + httpx + `core.http_client`**，不 import providers/fetcher/report/llm |
| 解析器绑定表 | `fetcher/cassette_checks.py` | cassette 名 → 当前解析器调用。绑在 fetcher 层是为了让 `core/` 不反向依赖 providers |
| 传输注入点 | `core/http_client.py` | `use_transport_factory()` / `make_transport()`——**C5 的唯一 HTTP 构造点**即注入点 |
| 已录制响应 | `src/test/data/cassettes/*.json` | git 跟踪的真实响应体（行情/K 线/基金净值/基金持仓） |

**注入方式**：`make_http_client()` 在未显式传 `transport` 时取当前工厂产出的传输，因此
全项目 provider **零改动**即可被替换为回放源；工厂每次调用必须返回**新**传输实例
（`httpx.Client.close()` 会连带关闭其传输，复用同一实例会让后续请求打到已关闭的传输上）。
未安装工厂时行为与没有本机制时逐字节相同。

**离线保证**：回放未命中抛 `CassetteMissError`，**绝不回落真实网络**；该异常刻意**不继承
`httpx.HTTPError`**——provider 的异常处理会捕获 httpx 错误并降级到下一个源，若继承之，
「回放漏录」会被静默改写成「换个源重试」，掩盖夹具缺失。**录制保证**：需 `--run-live` 与
`--record-cassettes` 双显式开关，非 live 用例的真实请求已被 conftest 阻断，机制上不可能产生录制。

**存储口径**：存**解码后的响应体文本 + 字符集**（真实响应为 gzip + GBK/GB18030/utf-8 混用），
回放时按录制字符集重新编码，并丢弃 `content-encoding`/`content-length`/`transfer-encoding`——
否则 httpx 会按已解压内容再解一次（`zlib.error`）或按旧长度截断。请求键归一剥离易变查询参数
（`VOLATILE_QUERY_PARAMS`：防缓存与 JSONP 惯用名），只对查询参数生效、不动路径。

**维护入口**：`cassettes`（列出）与 `cassettes --verify`（离线回放 + 交当前解析器解析，有失败则退出码 2）
为早返回命令，与 `doctor` 同例——**无需 config、不受任何实验开关约束**。录制刷新是显式联网动作：
`test-runner --mode live --record-cassettes`。

**不设功能开关**：cassette 只在测试进程与维护命令中被读写，报告管线不读它，不产生任何运行时
行为分支——一个不控制任何功能的开关纯属注册负担（理由见设计文档「为何不设开关」）。

**与 C5 的关系**：回放机制完全寄生于 C5「所有 HTTP 请求必须使用 `core/http_client.py` 工厂」。
任何 provider 若绕过工厂自建客户端，其请求既不受回放替换，也就**不会被未命中保护**——
回放用例会真实联网且静默通过。

[↑ 回到顶部](#目录)

---

### 2.7 数据源凭据就绪指引（内置，不可关闭）

把「此源需要什么凭据」**声明在数据里**，缺失时给出「缺什么 → 去哪申请」的可读指引，而不是等
运行期拿到 HTTP 401 再当作「源不可达」反复重试（借鉴 OpenBB `Provider(credentials=[...])`；
设计见实施设计文档「数据源凭据声明与就绪指引实施设计」）。

**现状**：多数数据源免费无需凭据；首个需凭据的源为 **DataSinking 全文本财报**
（`providers/datasink.py` 导入即登记 `CredentialSpec`，凭据取通用密钥文件
`data/config/data_key.json` 的 `datasink` 节或环境变量 `DATASINK_API_KEY`）。**未声明的源**
照常尝试；已声明未就绪的源由链路主动跳过并给可读指引。

| 组成 | 位置 | 职责 |
|:-----|:-----|:-----|
| 声明与判定 | `core/datasource_credential.py` | `CredentialSpec` 冻结 dataclass + `CREDENTIAL_SPECS` 注册表（声明即数据：源模块导入即注册，未声明的源免凭据）；`missing_credential` 判定就绪（**空白串视为缺失**，源未声明 → `None` 即不需凭据）；`credential_hint` 可读指引；`credential_readiness` 就绪矩阵（**自身不抛异常**，供体检复用）；就绪解析顺序「环境变量优先 → 密钥文件」（密钥文件以 provider 名为节，见 `data_key_file`） |
| 链路预检跳过 | `fetcher/chain.py` + `fetcher/chain_incremental.py` | `fetch_with_fallback` 的 provider 循环内、熔断检查之后；历史 chain 的 `_try_providers` 遍历循环同样受控——两处都是「能取数的路径」，只堵一处等于机制半应用 |
| 健康检查跳过 | `core/check_sources.py` | `_checks` 由三元组扩为 `(source_id, 显示名, 用途, 探测函数)`；缺失凭据**不发起探测**，直接产出 `skipped` 项（复用既有 `_SKIP` 符号 `⏭️`），末尾追加就绪摘要行 |
| 体检分组 | `core/doctor.py` | 新增 `GROUP_CREDENTIAL`「数据源凭据」组，插在「数据源适配」与「数据源」之间 |

**跳过语义与既有两处 `continue` 同例**：缺凭据是**配置级**问题而非源不可达，因此
**不计入熔断失败计数**；仅以可读原因进入 `FailureDiagnostics`，随降级事件上屏到数据源可用性
矩阵。`check-sources` 中跳过项计入 `skipped` 而非 `err`/`warn`，**不改变退出码**；`doctor` 的
「数据源」组据此过滤掉跳过项（该组只报真实探测结果），避免同一问题被两个组重复计为失败。

**安全口径**：凭据从声明的密钥文件或环境变量读取（环境变量优先），**值永不落日志、永不写入报告/缓存**——日志与就绪矩阵只报告**来源类型 + 是否就绪**，以及申请地址。

**不设凭据交互式配置向导**：凭据由用户在密钥文件/环境变量自行填写，界面只报告就绪状态；
新增需 key 的源时补 `register_credential_spec(...)` 一行声明即可，四面上屏
（链路/健康检查/体检/Web 健康页）均由既有面自动生效。

[↑ 回到顶部](#目录)

---

## 3. 缓存层详细设计

### 3.1 子模块结构

缓存统一存放在 `data/cache/` 目录，由 `cache/` 子包提供泛用键值对存储接口：

```
cache/
├── __init__.py        公开 API 导出（__all__ 精简形态）
├── _store.py          核心存取：get()、set()、clear()
├── _ttl.py            TTL 查询：get_ttl()、get_cache_age()
├── _io.py             文件 I/O：_read_cache_data()、_write_atomic()
├── _paths.py          路径管理：_cache_path()、_GZIP_THRESHOLD（100KB）
├── _groups.py         分组清理：clear_by_group()、clear_by_prefix()
├── _cleanup.py        过期清理：cleanup_expired()
├── _stats.py          统计：缓存命中率、命中/未命中计数
├── operations.py      缓存操作共享层（三渠道共用业务逻辑）
└── services/
    └── holdings_tracker.py  持仓跟踪、指纹比对、增量刷新
```

### 3.2 核心接口与 TTL 分辨率

#### 核心接口

| 函数 | 签名 | 说明 |
|:-----|:------|:------|
| `get(key, max_age_seconds)` | `(str, float) → Any\|None` | 先查 `.json.gz`，不存在时回退 `.json`；超龄返回 None |
| `set(key, data)` | `(str, Any) → None` | `{"_ts": now, "_data": data}` 序列化 + 原子写入；≥100KB 自动 `.json.gz` |
| `clear(key)` | `(str) → None` | 同时删除 `.json` 和 `.json.gz` |
| `get_ttl(data_type)` | `(str) → float` | TTL 分辨率（见下方流程图）；只由数据类型决定（无按 key 抖动、无兼容参数） |
| `clear_by_group(group)` | `(str) → None` | 按 preload/refresh 分组清除 |
| `cleanup_expired()` | `() → int` | 扫描全量缓存，删除超龄项（逐文件明细只进 DEBUG，INFO 留汇总行 + 释放字节；age/TTL 按量级自适应单位——盘中 30s 的 price TTL 不再印成 `ttl=0.0h`；**无 `_ts` 包封的文件跳过 TTL 判定**，见下） |

#### TTL 分辨率流程

```
get_ttl(data_type)
    │
    ▼
┌──────────────────────────────────────┐
│ 注册表声明 market_ttl？               │── NO ─┐
│ （DataModuleDef.market_ttl，仅价/指） │       │
└────────────┬─────────────────────────┘       │
            YES                                │
             │                                 │
             ▼                                 │
┌──────────────────────────────┐               │
│ is_market_open()?            │               │
├──────────────────────────────┤               │
│ YES → market_hour_ttl 覆盖    │               │
│   （config，缺省 30s，钳制    │               │
│     [30, 86400]）             │               │
│ NO  → 静态 TTL 分支            │               │
└────────────┬─────────────────┘               │
             │                                 │
             ▼                                 ▼
    ┌──────────────────────────────────────────┐
    │ config.json → cache_ttl.{data_type}       │
    │ 用户显式覆盖（正数）?                      │
    ├────────────┬─────────────────────────────┤
    │ YES → 返回  │ NO → 注册表默认             │
    │ 用户配置值   │ get_cache_ttl_defaults     │
    └────────────┘         │                   │
                           ▼                   │
                  ┌──────────────────┐         │
                  │ 类型未注册?       │         │
                  ├──────┬───────────┤         │
                  │ YES  │ NO        │         │
                  │ 回退  │ 返回默认值 │         │
                  │86400s│           │         │
                  └──────┘           │         │
```

**盘中敏感性由注册表声明**（`DataModuleDef.market_ttl`，当前只有 `price`/`index` = 30s）：这是数据属性而非用户偏好——价格/指数分钟级变化，盘中必须短 TTL 才能避免把盘中价当收盘价（否则"本日盈亏/快照环比"系统性偏离），而非行情数据（新闻 900s、情绪 3600s 等）不得因盘中被降频、白打上游。`config.json → market_hour_aware` 已退役：写入该项只会在配置校验时告警并被忽略。

**盘中覆盖可见**：若用户同时配了 `cache_ttl.{type}` 而该类型盘中敏感，`get_ttl` 会打一条 INFO（每类型一次）说明"盘中以 `market_hour_ttl` 为准，`cache_ttl` 仅盘后生效"——把静默失效变成可观测。

**负缓存同源**：缺失探测类负缓存（`datasink_probe_miss_` 12h、`report_symbol_miss_` 6h）登记为正式缓存类型，读侧 TTL、`cleanup_expired` 判定、`cache_ttl` 覆盖与文档表格共用同一注册表条目（未登记时会被按未注册默认 24h 判定，滞留更久且配置不可见）。

### 3.3 原子写入与并发安全

**原子写入模式**（C3 约束，`cache/` 和 `config/` 子包共享）：

```
tempfile.mkstemp(dir=cache_dir) → fd, tmp_path
    write(fd, data)
    close(fd)
    os.replace(tmp_path, target_path)  ← 原子替换
```

#### set() 写入细节

```
set(key, data)
    │
    ▼
payload = {"_ts": time.time(), "_data": data}
    │
    ▼
json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    │
    ▼
┌────────────────────────────┐
│ len(raw_bytes) > 100KB?   │
├────────────┬───────────────┤
│ YES → .gz  │ NO → .json   │
└────────────┴───────────────┘
    │
    ▼
tempfile.mkstemp(dir=...) → fd, tmp_path
    │
    ▼
_write_atomic(fd, tmp_path, final_path)
    │
    ├── 成功 → os.replace(tmp_path, final_path)
    ├── FileNotFoundError → 目录被删除? 重试一次
    ├── OSError → 日志 WARNING
    └── PermissionError → 降级到直接写入（Windows 兼容）
```

#### 并发安全

- `os.replace` 保证读取方不会看到半写文件（文件系统级原子操作）
- 多线程同时 `get()` 同一 key 可能产生 TOCTOU 空窗（两线程均认为缓存过期，均拉取 API），但通过 `_write_atomic` 保证同时写入时只有一个生效
- `clear()` 操作使用 `_cache_lock` 互斥

#### 路径安全

- `_cache_path(key)` 对 key 做 `replace("..", "_")` 防目录穿越
- 缓存目录不存在时 `os.makedirs(dir, exist_ok=True)` 自动创建

**项目根路径查找**（`core/constants.py:_find_project_root()`）：

```
从 src/python/core/constants.py 所在目录
    → 向上逐层搜索 pyproject.toml 或 .git
    → 找到即停，完全不依赖目录树深度
    → 安全上限 20 层，未找到时按当前文件所在目录兜底
```

所有需定位项目根路径的模块统一从 `constants.PROJECT_ROOT` 导入。

**文件损坏恢复**：`_read_cache_data()` 解析失败时自动 `os.remove` 损坏文件，记录 WARNING 日志，下次调用时重新拉取。

### 3.4 指纹驱动失效机制

**问题**：部分缓存依赖外部输入源（如持仓列表、指数收盘价），输入变化时需重新拉取。但基于名称的缓存键无法感知"数据变了"，只能依赖 TTL 等待过期。

**方案**：缓存文件名中内嵌 MD5 前 12 位十六进制摘要，输入源数据变化时摘要改变，缓存键自动不匹配。

```
文件名模式: {prefix}_{digest}.json
示例:       profit_forecast_a1b2c3d4e5f6.json

读取流程:
    │
    ▼
读取缓存文件 → 提取文件名中的 digest
    │
    ▼
根据输入源数据实时重算 MD5 摘要
    │
    ▼
┌──────────────────────┐
│ digest == 重算值?    │
├────────┬─────────────┤
│ YES →  │ NO →        │
│ 缓存有效│ 缓存未命中   │
│ 返回   │ 跳过读取     │
└────────┘ 触发重新拉取 │
           └────────────
```

#### 指纹类型

| 指纹类型 | 计算位置 | 输入源 | 作用范围 |
|:---------|:---------|:-------|:---------|
| **指数指纹** | `akshare_extras.py:_compute_index_fingerprint()` | A 股+美股指数收盘价（列表拼接→MD5） | `profit_forecast_*`、`sector_flow_*` |
| **代码列表指纹** | `holdings_tracker.py:compute_holdings_fingerprint()` | 持仓+穿透 A 股代码（去重排序→MD5） | `dividend_*` |
| **输入参数指纹** | `news_aggregator.py:_compute_cache_key()` | 新闻源参数+关键词（拼接→MD5） | `news_*` |
| **输入数据指纹** | `llm/fingerprint.py` | LLM 模块依赖数据（持仓汇总/结构序列化→MD5） | `llm_global_macro_*`、`expert_review_*`、`health_check_*`、`penetration_deep_*`、`news_item_*` |

**LLM 指纹筛选**：expert_review / health_check / penetration_deep 的 `compute_fingerprint()` 在序列化前排除行情波动字段（`price`、`change_pct`），仅品种/份额/成本变化时指纹改变。

**精确键名**：`fund_benchmarks.json`、`fund_concentration_snapshot.json`、`holdings_tracking.json` 等无指纹后缀，仅依赖标准 TTL 过期刷新。

**双保险**：指纹机制与 TTL 互补——指纹未变但 TTL 到期同样触发刷新（TTL 优先，指纹为辅助手段）。

### 3.5 缓存分组

通过 `core/registry.py` 的 `cache_groups` 字段定义分组，由 `clear_by_group()` 统一管理（分组归属以注册表为唯一事实来源）：

| 分组 | 包含模块（registry 注册名） | 触发 |
|:-----|:---------------------------|:-----|
| `preload` | 股票价格、市场指数、LLM 全球政经局势、LLM 智囊团深度复盘、LLM 持仓体检报告、LLM 穿透深度分析、LLM 辩论三段（白脸 pro / 黑脸 con / 综合 synthesis） | 菜单 `[2]` |
| `refresh` | 基金业绩排名、基金持仓、行业分类、市场情绪、财报索引、财报正文、财务指标、新闻聚合、LLM 新闻关联分析、机构盈利预测、行业资金流向、股票历史分红、基金业绩基准、基金经理、基金风格扩展数据、无风险利率 | 菜单 `[1]` |
| 无分组 | 历史股票日线、历史基金净值、指数历史日线、集中度快照、风格快照、持仓跟踪、交易日历 | 不被菜单缓存命令误删（仅缓存管理子菜单 `[3]` → `3` 过期清理） |

**缓存分组设计原则**：
- **preload 组**：换持仓文件后应重取的基础行情和 LLM 分析
- **refresh 组**：可手动刷新的基金/行业/新闻等
- **无分组**：历史走势（per-code 缓存，不因切换持仓文件而清除）和基金深度分析快照（精确键名，独立管理）

### 3.6 缓存操作共享层

`cache/operations.py` 封装了 TUI 和 CLI 共用的缓存操作业务逻辑，通过 `ThreadPoolExecutor` 并行执行缓存刷新任务，消除 `tui/handlers_cache.py` 中的逻辑重复。

#### 数据结构

```python
@dataclass
class CacheUpdateResult:
    total_funds: int = 0
    perf_ok: int = 0        # 基金业绩数
    hold_ok: int = 0        # 基金持仓数
    bm_ok: int = 0          # 基准成功数
    pf_ok: int = 0          # 盈利预测
    sf_ok: int = 0          # 资金流向
    ind_ok: int = 0         # 行业分类数
    div_ok: int = 0         # 分红数据
    errors: list[str] = field(default_factory=list)
    # exit_code: 0=全成功 / 1=部分失败 / 2=全无数据

@dataclass
class PositionCacheResult:
    total: int = 0           # 持仓总数
    price_ok: int = 0        # 价格成功数
    a_index_count: int = 0
    us_index_count: int = 0
    errors: list[str] = field(default_factory=list)

@dataclass
class CacheStats:
    total_files: int = 0
    total_size_bytes: int = 0
    expired: int = 0
    hit_rate: float = 0.0
    # 快照目录 + 运行时状态统计
    snapshot_files: int = 0
    state_files: int = 0
```

#### 对外接口

| 函数 | 说明 |
|:-----|:------|
| `update_basic_cache(holdings, reporter) → CacheUpdateResult` | 基金缓存 + 公共缓存（盈利预测/资金流向/行业/分红）并行刷新 |
| `update_position_cache(holdings, reporter) → PositionCacheResult` | 持仓价格 + 指数并行获取 |
| `cleanup_cache(reporter) → int` | 扫描清理过期缓存 |
| `get_cache_stats(reporter) → CacheStats` | 三目录统计（cache + snapshots + state） |
| `get_cache_stats_payload() → dict` | GET /api/cache 结构化载荷单源组装（保序数组/top 截断/命中率/过期预估，Web 只做传输封装） |
| `update_all_cache(holdings, reporter) → int` | 基础 + 持仓全量更新（最大努力：basic 失败仍继续 position，退出码取 max；CLI `--update all` 委托） |
| `warm_new_asset_caches(holdings, reporter) → list[str]` | 持仓变更预热：检测新增资产并预取行情/基金业绩与持仓/行业分类（TUI 生成前入口，异常不阻断） |

#### 内部线程池（缓存操作共享层）

`operations.py` 管理独立的 `cache_ops` 线程池（`max_workers=4`），与 orchestrator 的 `orch_prep`、`orch_llm_news` 池隔离：

```python
_POOL: ThreadPoolExecutor | None = None

def _get_pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache_ops")
    return _POOL
```

**关键设计**：`cache/operations.py` 是缓存层内 `ThreadPoolExecutor` 的唯一宿主，`tui/handlers_cache.py` 和其他调用方通过调用 `operations.py` 的函数间接使用线程池，不直接持有池引用。

[↑ 回到顶部](#目录)

---

## 4. 报告生成层详细设计

### 4.1 管线总览

`src/python/report/` 采用**编排器 + 内容模块**架构，Excel 和 HTML 双端共享 `data_status.py` 降级状态基础设施。顶层由 `orchestrator.py` 统一调度，TUI 的 `tui/handlers_report.py` 仅作为"薄壳"委托编排器。

```
                                       tui/handlers_report.py
                                              │
                                              ▼
                                     orchestrator.generate_report()
                                      │
                                      ├── basic: 仅 Excel（无数据准备）
                                      ├── both:  HTML+Excel（无 LLM）
                                      └── full:  HTML+Excel+LLM
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
          历史走势可选分支               Excel 管线                HTML 管线
          (菜单 L/B)                    │                      │
            │                           ▼                      ▼
            ▼                  excel_generator.py       html_writer.py
      ┌──────────┐                 (编排器)                │
      │ 快照对比 │                     │                   ▼
      │          │                     ▼           html_builders.py
      │          │           excel_sheet_factory.py   (数据构建器)
      │ 历史走势 │                     │                   │
      │ 计算     │                     ▼                   ▼
      └──────────┘           excel_module_loader.py  tmpl/report_template.html
            │                 (动态加载写入器)         (Jinja2 模板)
            ▼                       │
     注入 info →                内容模块写入器:
     Excel/HTML                  summary / holdings_detail /
                                 penetration /
                                 fund_performance /      共享: data_status.py
                                 news_correlation /       (STATUS_MESSAGES/
                                 llm_content /            TIER_PREFIX/
                                                          DegradationTracker)
                                 基金深度分析 6 个 /
                                 excel_writer.py +
                                 styles.py
                                 基金业绩分析候选比较子表:
                                 fund_candidate.py
                                 (candidate_compare 默认关,
                                 Excel/HTML 双端渲染)
```

### 4.2 报告编排器

`report/orchestrator.py` 是 TUI 和 CLI 共用的报告编排共享层，负责：

1. **数据准备**：行情获取、指数获取、资产穿透 TOP10
2. **快照创建与差异计算**：持仓快照 + 环比差异
3. **历史走势计算**：组合 as-if 走势 + 基准指数对比
4. **行业资金流向获取**
5. **LLM + 新闻并行获取**（4 分支统一处理）
6. **双管线生成**：HTML + Excel

#### pipeline_data 数据上下文

`report/pipeline_data_builder.py` 集中组装传递给 LLM 的数据上下文 `pipeline_data`。包含 `build()`（A 通道：快照环比差异组装）和 `build_prep()`（B 通道：行情/持仓/指标数据组装）两个构造器，入口统一做类型断言（C19 约束）。

`pipeline_data` 遵循 C19 Schema 契约：所有键必须在 pipeline_data Schema 定义集中存放处预定义类型、版本号和写入/消费模块后，才能在代码中使用该键（详见附录 H）。

#### 三种报告路径

**basic 路径**（菜单 E）：最简路径，仅生成 Excel，不调编排器数据准备层（`prepare_report_data()`），但汇总页签内部通过 fetcher 独立获取指数行情数据：

```
generate_report("basic")
    → 读取章节顺序配置
    → generate_excel_report()
    → 返回 ReportResult
```

**both 路径**（菜单 B）：生成 HTML+Excel，不含 LLM：

```
_generate_report_both()
    → _compute_details()           轻量行情获取（无指数/穿透/分类）
    → capture_snapshot()           快照对比
    → fetch_history_data()         条件：enable_history=True
    → write_html_report()          HTML 管线
    → generate_excel_report()      Excel 管线
```

**full 路径**（菜单 L）：生成 HTML+Excel+LLM：

```
_generate_report_full()
    → prepare_report_data()        完整数据准备（含指数/穿透/分类/明细）
    → capture_snapshot()           快照对比
    → fetch_history_data()         条件：enable_history=True
    → get_sector_fund_flow()       行业资金流向
    → _fetch_llm_and_news()        LLM+新闻并行（4 分支：均开/仅 LLM/仅新闻/均关）
    → write_html_report()
    → generate_excel_report()
```

#### 进度报告接口

编排器通过 `ProgressReporter` 接口输出进度消息，不直接依赖 TUI 或 `print()`：

```python
class ProgressReporter:
    def info(self, msg: str)       # ℹ️ 进行中
    def ok(self, msg: str)         # ✅ 成功
    def warn(self, msg: str)       # ⚠️ 告警
    def error(self, msg: str)      # ❌ 错误
    def add_error(self, msg: str)  # 累计错误
```

TUI 环境使用 `TuiProgressReporter`（输出到终端），CLI 环境使用 `CliProgressReporter`。

**CliProgressReporter**（`report/cli_progress.py`）行为：

| 模式 | info/ok | warn | error | 输出目标 |
|:-----|:--------|:-----|:------|:---------|
| 常规（verbose=False，默认） | `logging.INFO` | `logging.WARNING` | `logging.ERROR` | logs/app.log |
| verbose（verbose=True） | `logging.INFO` + stderr `[..]/[OK]` | `logging.WARNING` + stderr `[!]` | `logging.ERROR` + stderr `[ERR]` | app.log + stderr |

verbose 模式颜色由 `stderr.isatty()` + `NO_COLOR` 环境变量控制，使用本地颜色常量（不依赖 `ansi_colors` 模块级常量，后者基于 `stdout.isatty()`）。

#### 内部线程池（报告编排器）

| 池名称 | 位置 | max_workers | 用途 |
|:-------|:-----|:-----------|:------|
| `orch_prep` | `prepare_report_data()` | 2 | 并行获取 A 股/美股指数 |
| `orch_factor` | `orchestrator.py` 风格因子回归 | `min(6, n)` | 并行拉取持仓 as-if 日收益 |
| `orch_factor_idx` | `orchestrator.py` 风格因子回归 | 4 | 并行拉取因子指数 K 线 |
| `orch_ind` | `orchestrator.py` 行业 Beta | `min(6, n)` | 并行拉取持仓 K 线 |
| `orch_ind_idx` | `orchestrator.py` 行业 Beta | 4 | 并行拉取映射行业的指数 K 线 |
| `orch_val` | `orchestrator.py` 估值分位 | `min(6, len(pairs))` | 并行拉取 PE/PB + 价格分位 |
| `orch_corr` | `orchestrator.py` 相关性矩阵 | `min(6, n)` | 并行拉取持仓 K 线 |
| `orch_llm_news` | `_fetch_llm_and_news()` | 2 | 并行获取 LLM + 新闻 |
| `orch_health` | `_report_health.py` 数据源健康检查 | 1 | 后台并行执行数据源健康检查 |

### 4.3 Excel 管线

**编排器职责**（`excel_generator.py`）：
1. 调用 `create_sheets()` 创建 workbook 和页签
2. 迭代 `excel_module_loader.py` 动态加载的内容模块
3. 每个模块接收 `(ws, info, writer)` → 独立写入页签内容和样式

**页签写入器约定**：`_write_*_sheet()` 接收 `info` 字典 + `writer`，独立负责单个页签的内容和样式，互不依赖。

**内容模块动态加载**：`excel_module_loader.py` 通过模块注册表发现并加载写入函数，新增模块只需在注册表中添加条目，无需修改编排器。

### 4.4 HTML 管线

| 组件 | 文件 | 职责 |
|:-----|:-----|:------|
| 编排器 | `html_writer.py` | 调用 builders → 渲染 → 保存 |
| 数据构建器 | `html_builders.py` | 原始数据 → 结构化渲染对象 |
| 渲染器 | `html_renderers.py` | Markdown→HTML 转换、格式处理 |
| 模板 | `tmpl/report_template.html` + `tmpl/partials/` | Jinja2 模板 + 宏 + 章节级 partial（主模板经 include 按组拆入） |
| 环境 | `html_jinja_env.py` | Jinja2 环境初始化、过滤器注册 |
| 保存 | `html_save.py` | HTML 文件写入 |
| JS 资产 | `html_writer_assets.py` | `_copy_js_assets` 复制 Chart.js bundle 到输出目录；`_inline_js_assets` 保存前内嵌为行内脚本（单文件自包含） |

**渲染期通信**（C14 约束）：所有渲染期数据（`section_visible_dict` 等）必须通过模板 `render()` 的 context 参数传递，不得写入 `_ENV.globals` 或模块级 dict 作为跨函数通信渠道。单次会话中不变的数据（如 `_ENV` 过滤器注册）不受此限。

### 4.5 章节可见性两层模型

报告模块按两层模型决定是否在最终报告中显示：

```
                         section[key]
                              │
                              ▼
                    ┌─────────────────────┐
                    │ board 层预过滤        │
                    │ board_flags[type]?   │
                    ├──────────┬──────────┤
                    │ False    │ True     │
                    │ (关闭)   │ (开启)   │
                    └──────────┴──────────┘
                         │          │
                    隐藏整个         ▼
                    type       ┌─────────────────────┐
                               │ data 层判断          │
                               │ data_flag 在         │
                               │ data_availability 中 │
                               ├──────────┬──────────┤
                               │ None     │ 有值     │
                               │ (always/ │ (bool)   │
                               │ history) │          │
                               └──────────┴──────────┘
                                    │          │
                                始终可见    True=可见
                                           False=隐藏
```

#### Excel 端实现

`excel_sheet_factory.py:create_sheets()` 分成两步：
1. board 层预过滤：`board_flags` 关闭的 section → `continue`
2. data 层判断：`should_create_sheet(sec, data_availability)` → 按 `sec["data_flag"]` 在 `data_availability` 中查询

#### HTML 端实现

`html_writer_nav.py:_compute_section_visibility()` 集中实现两层合并：

```python
board_flags = {
    "always":             True,
    "fund_deep_analysis": enable_fund_deep_analysis,
    "news":               enable_news,
    "history":            enable_history,
    "evolution":          enable_portfolio_evolution,
    "action":             enable_action,  # ← board 层：行动建议（config 默认开）
    "llm":                enable_llm,
}

for sec in section_order:
    board_ok = board_flags.get(sec["type"], True)
    if not board_ok: continue
    flag_name = sec.get("data_flag")
    if not flag_name:
        section_visible_dict[sec["key"]] = True
    else:
        section_visible_dict[sec["key"]] = data_flags.get(flag_name, False)
```

#### data_flag 定义

| data_flag | 判定依据 | 对应 section.type | 说明 |
|:----------|:---------|:-----------------|:------|
| `None` | 始终可见 | `always` / `history` | 不依赖数据状态 |
| `position_relationship_data` | `overlap_matrix is not None or position_relationship_data is not None` | `fund_deep_analysis` | 持仓结构与集中度·区块一/二（重合度 + 相关性） |
| `concentration_data` | `concentration_analysis is not None` | `fund_deep_analysis` | 持仓结构与集中度·区块三（集中度） |
| （`position_structure` 用 `data_flag_any`） | 上述两者任一就绪（OR，悲观判定） | `fund_deep_analysis` | 合并章节：任一区块有数据即显示（见「持仓结构与集中度」） |
| `style_factor_data` | `style_factor_data is not None or style_analysis is not None` | `fund_deep_analysis` | 风格与因子分析（风格表 + 因子回归 + 行业 Beta + 因子目录，一章四区块） |
| `evolution_data` | `evolution_data is not None` | `evolution` | 组合演进（多快照趋势） |
| `news_data_available` | `include_news` flag（新闻数据可用） | `news` | 新闻关联分析 |
| `llm_data_available` | `llm_enabled_flag`（LLM 生成成功） | `llm` | LLM 全部 5 模块 |
| `financial_report_digest_data` | `financial_report_digest_data is not None` | `fundamental_snapshot` | 持仓基本面·区块二（财报摘要，功能开关 `stock_fundamentals`） |
| `financial_indicator_data` | `financial_indicator_data is not None` | `fundamental_snapshot` | 持仓基本面·区块一（财务指标，功能开关 `financial_indicator`） |
| （`fundamental_snapshot` 用 `data_flag_any`） | 上述两者任一就绪（OR，悲观判定） | `fundamental_snapshot` | 合并章节：任一块就绪即显示；两块由同一功能开关 `stock_fundamentals` 同开同关 |

`always` 类型模块（summary / holdings_detail / penetration / fund_performance / data_source_status）无 data_flag，始终显示。`evolution` 类型模块（`portfolio_evolution` 组合演进）由独立开关 `enable_portfolio_evolution` 控制，带 `evolution_data` 标志——聚合数据存在（`evolution_data is not None`）才渲染章节，`available=False` 时章节内写占位文本（与持仓关系矩阵·相关性区块降级模式一致）。`action` 类型模块（`action` 行动建议）由独立顶层开关 `enable_action`（默认开，菜单 C 可切换）控制，`data_flag` 为 `None`（纯算法计算，basic/both/full 均可见，无数据可用性判定）——开关关闭或无持仓数据时不渲染章节，落 §1.4.5 降级占位。`fundamental_snapshot` 类型模块（`fundamental_snapshot` 持仓基本面）为**合并章**：board 层 `enable_fundamental_snapshot`（= 单一功能开关 `stock_fundamentals`，两块同开同关）与 data 层 `data_flag_any` 双契约 OR 共同决定，章内两个区块各按自己的数据契约渲染（契约 None = 该块无数据，整块不渲染）。

### 4.6 报告序号可配置

报告 19 个模块的序号/显示名称由 `core/registry.py` 的 `_REPORT_SECTION_DEFAULT` 注册表驱动，支持用户通过 `config.json` 自定义。

#### 注册表结构

每条记录包含 5 个字段：

```python
{
    "key": "position_structure",   # 模块标识
    "name": "持仓结构与集中度",     # 显示名称
    "number": 5,                   # 默认序号
    "type": "fund_deep_analysis",   # 可见性类型
    "data_flag_any": ("position_relationship_data", "concentration_data"),  # 多契约 OR
}
```

19 个模块分布：`always`×5、`fund_deep_analysis`×2、`news`×1、`llm`×5、`history`×1、`evolution`×1、`action`×1、`fundamental_snapshot`×1、`holding_change`×1、`schedule_replay`×1。

#### 合并规则流程

```
get_report_section_order(config)
    │
    ▼
┌────────────────────────┐
│ config 中有             │
│ report_section_order?  │── NO ──→ 返回完整 19 项默认顺序
└───────────┬────────────┘
           YES
            │
            ▼
分离已配置/未配置模块（llm_usage 除外）
    │
    ├── 已配置 → 使用配置序号，收集到 configured[]
    └── 未配置 → 保持默认序号，收集到 unconfigured[]
    │
    ▼
configured.sort(key=lambda x: x["number"])   ← 按配置序号升序
result = configured + unconfigured            ← 已配置在前，未配置在后
    │
    ▼
找到 llm_usage，从当前位置删除 → 追加到 result 末尾 ← 强制末位
    │
    ▼
返回 result（19 项，key/number/type/data_flag）
```

#### 渲染实现

**连续重新编号**：
1. 从 section_order 筛选所有可见模块（board+data 双层过滤）
2. 将 llm_usage 从可见列表分离，强制追加到末尾
3. 按新顺序从 1 开始分配连续序号

**HTML 端**：导航栏使用 `section_order` 动态循环（只渲染可见模块），CSS `order` 属性视觉排序，章节标题使用 `{{ section_numbers['key'] }}` 动态显示。

**Excel 端**：页签标题采用 `f"{visible_count}.{sec['name']}"` 格式。

### 4.7 组合历史走势计算算法

`portfolio_history.py` 的 `get_combined_timeseries()` 实现 5 步算法链。

#### 算法流程总览

```
输入：各只持仓的历史数据 {holding: [{date, value}, ...]}
    │
    ▼
┌─────────────────────────────────────────────┐
│ ① LOCF 合并                                  │
│ 全程集合并 → 每只持仓沿用上次已知值             │
│ 输出：{date: total_value}                     │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ ② 有效区间双向截断                             │
│ 正向找 valid_start_idx ≥ 覆盖阈值              │
│ 反向找 valid_end_idx ≥ 覆盖阈值                │
│ 截断后区间用于收益率/回撤计算                    │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ ③ 回撤算法 (Peak-to-Trough)                  │
│ 遍历日期，新高更新 peak，记录最深回撤            │
│ 输出：max_drawdown_val, max_drawdown_pct       │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ ④ 累计收益率                                  │
│ first_val = bars[0]["total_value"]            │
│ last_val  = bars[-1]["total_value"]           │
│ total_return_pct = (last-first)/first × 100   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ ⑤ 年化波动率                                  │
│ daily_returns = [(curr-prev)/prev ...]        │
│ annualized_vol = std(daily_returns, ddof=1)   │
│                   × √252                      │
└───────────────────────────────────────────────┘
```

#### ① LOCF（Last Observation Carried Forward）合并

**问题**：每只持仓的历史数据日期集合不同（股票有完整日 K 线、QDII 净值 T-1 滞后、债券基金更新频率更低）。简单地对交集日期求和会丢失大量数据。

**方案**：对全部出现过的日期做全程集合并合并，某基金在某日无新净值时沿用上次已知值：

```
all_dates = sorted(∪ {dates_of_each_holding})
for each_holding:
    last_val = 0
    for d in all_dates:
        if d in holding_data: last_val = holding[d]
        if last_val > 0: total_value[d] += last_val
```

**效果**：避免 QDII 净值滞后、场外基金更新慢导致当日组合市值骤降、收益率虚低。

#### ② 有效区间双向截断

**问题**：不同基金数据起止日期不同，直接用全部日期计算收益率会失真（边界上只有部分基金有数据）。

**方案**：
- **起算点（valid_start_idx）**：正向遍历，找第一天 ≥ 覆盖阈值
- **终止点（valid_end_idx）**：反向遍历，找最后一天 ≥ 覆盖阈值
- 截断后锁定的区间才是收益率计算的"有效区间"
- 走势图仍显示完整时间线（含边界数据），但累计收益率和回撤指标只以有效区间为基准
- **覆盖阈值**：默认 `0.8`（80%），可通过 `config.json` 的 `history.coverage_threshold` 配置（0~1）

#### ③ 回撤算法（Peak-to-Trough）

```
peak = 0
for each date in sorted_dates:
    tv = total_value[date]
    if tv > peak:
        peak = tv                         # 新高 → 更新峰值
        current_dd_start = date            # 记下潜在回撤起算日
    drawdown = peak - tv                   # 当前回撤金额
    drawdown_pct = drawdown / peak × 100   # 回撤百分比
    if drawdown > max_drawdown_val:        # 追踪最大回撤
        max_drawdown_val = drawdown
        max_drawdown_pct = drawdown_pct
        drawdown_end = date                # 回撤最深日
        drawdown_start = current_dd_start  # 该段回撤的峰值日
```

#### ④ 累计收益率

```
first_val = bars[0]["total_value"]    # 有效区间第一日市值
last_val  = bars[-1]["total_value"]   # 有效区间最后一日的市值
total_return_pct = (last_val - first_val) / first_val × 100
```

#### ⑤ 年化波动率

```
daily_returns = [(curr - prev) / prev for adjacent days]
annualized_vol = std(daily_returns, ddof=1) × √252
```

使用样本标准差（`ddof=1`），交易日假设 252 天。

#### 走势数据获取：增量合并 Fallback

`fetch_with_incremental_fallback()` 与 `fetch_with_fallback()` 的对比：

| 维度 | `fetch_with_fallback` | `fetch_with_incremental_fallback` |
|:-----|:-----------------------|:----------------------------------|
| 用途 | 单次价类数据（价格/行业） | 时序数据（历史走势） |
| 缓存策略 | 先读缓存→命中直接返回 | 先读缓存做底座→增量获取新数据→合并 |
| 过期缓存降级 | 全链路失败时降级 7 天内过期缓存 | 全链路失败时返回空列表 `[]`（显示占位文本） |
| 数据修正感知 | 无感知 | 重叠检测→自动全量刷新（应对除权除息） |

#### 基准指数对比

基准指数历史走势的并行获取与归一化对齐，在 5 步算法链基础上叠加显示。

**配置接口**（`config.json`）：

```json
{
  "history": {
    "benchmark_indices": { "sh000300": "沪深300", "gb_inx": "标普500" },
    "fetch_mode": "auto"
  }
}
```
> 上例为**配置示例**（含自定义 `gb_inx`），非默认值；默认 `benchmark_indices` 仅含 `{"sh000300": "沪深300"}` 单条。

**技术流程**：

```
get_combined_timeseries()
    │
    ▼ (5 步算法链完成后)
    ┌─────────────────────────────────────┐
    │ self._benchmark_indices 非空?       │── NO → benchmarks = []
    └──────────────┬──────────────────────┘
                   YES
                   ▼
    ┌─────────────────────────────────────┐
    │ fetch_benchmarks(indices, days)     │
    │ (ThreadPoolExecutor 并行获取，       │
    │  走 fetch_index_history → chain)     │
    └──────────────┬──────────────────────┘
                   ▼
    ┌─────────────────────────────────────┐
    │ normalize_benchmarks(bars, raw)     │
    │ LOCF合并→起算日对齐→归一化至100基点  │
    └──────────────┬──────────────────────┘
                   ▼
             benchmarks 列表
```

**防御性编程**：
- `bar.get("date")` 防御性检查（防止 KeyError）
- 每次 index bar 的 close 校验：`isinstance(close, (int, float)) and close > 0`
- 每个基准完成归一化后输出 `logger.info(...)` 
- 异常捕获在 try/except 中，不阻塞主流程

**HTML 渲染**：全部图表由 Chart.js 渲染（唯一渲染器；离线内嵌单文件，引擎缺失/数据不足时画布显示占位文案、数据表格照常），组合 as-if 曲线（实线）+ 基准指数（虚线，颜色循环），右侧图例显示。

**Excel 渲染**：`portfolio_history_drawdown`（组合历史走势与回撤）页签分「走势表 + 回撤矩阵 + 危机区间标注 + 月度收益日历 + 风险调整超额」五区块——走势表每基准一列（归一化值）+ 指标汇总矩阵（累计收益/最大回撤/年化波动率/起止日，仅一份），回撤矩阵为独立回撤事件明细（含恢复耗时）+ 尾部风险统计（VaR(95/99)/最大单日跌幅/最长连续下跌/最大跌幅后恢复五行，百分比按 FMT_PERCENT 存小数，样本不足写「样本不足」占位），危机区间标注为静态日期表（2015 股灾/2018 贸易摩擦/2020 疫情/2022 调整/2025 关税冲击，`CRISIS_INTERVALS` 单一来源）+ 区间统计——回放态（开关 `crisis_replay`）升级为双层列（组合区间收益/指数区间收益/指数区间最大回撤，组合窗内才算组合层，窗外行状态标「组合窗口外」），月度收益日历为年 × 月红绿格（正值红字/负值绿字，`return_pct/100` 配 FMT_PERCENT）+ 口径与胜亏平统计说明行（数据源 `history_data.monthly_returns`，as-if 口径、双口径并排预留），风险调整超额块（开关 `risk_adjusted_excess`）为基准 IR/TE/年化超额 + 12/24 月胜率 + 完整月数表 + 滚动 250 日超额序列 + 口径说明行，样本不足逐项落「数据不足」占位、整块不随开关写。

#### 持仓快照存储与清理（history_snapshot.py）

```
save():
    data/history/snapshots/snapshot_{timestamp}.json
    tempfile.mkstemp + os.replace（符合 C3 约束）

load_comparison_baseline(current_ts, namespace)：环比比对基线（跨交易日）
    取「所属交易日 < 本次交易日」的最新一份快照（同一交易日多次运行跳过）
    交易日归属 trading_day_as_of（盘前 <9:30 归前一交易日、节假日按日历回溯、
    日历不可用回退排除周六日）；current_ts 不可解析回退 load_latest（退化旧口径）

prune()：两阶段自动清理
    ① 时间优先：删除超过 HISTORY_SNAPSHOT_RETENTION_DAYS（默认 180d）
                 可通过 config.json history.snapshot_retention_days 配置
    ② 数量兜底：剩余文件超过 HISTORY_SNAPSHOT_MAX_COUNT（默认 365）
                 可通过 config.json history.snapshot_max_count 配置
                 时删最旧超出部分
```

### 4.8 基金深度分析

基金深度分析 4 个模块通过 `enable_fund_deep_analysis` 标志控制条件渲染，跟随 `include_news`（菜单 B/L 时触发）。

```
                    基金深度分析模块架构
                         │
           enable_fund_deep_analysis = True?
                         │
              ┌──────────┴──────────┐
              │                     │
        持仓结构与集中度      风格与因子分析
        重合度+相关性+集中度   一章三区块
        Jaccard/重叠率/Pearson 风格表+因子回归+行业Beta
              │
        基金经理变更块
        （基金业绩章末尾块）   一章两区块
              │              风格表+因子回归+行业Beta
              │              OLS 回归风格画像
```

#### 基金经理变更监控块（「基金业绩分析」章末尾区块）

基于快照比对检测基金经理变更：

```
天天基金 fundf10 基金经理列表 HTML 解析
    │ 获取当前经理姓名 + 任职起始日
    ▼
fund_manager_snapshot 快照（精确键名，每日更新）
    │ 与历史快照比对
    ▼
窗口期计算（任职起始日距今天数）：
    ≤30天   → 🔴 紧急
    ≤90天   → ⚠️ 关注
    ≤180天  → ⚠️ 关注（91~180天范围）
    首次运行 → 📋 首检（自下次起跟踪）
    无变更   → ✅ 正常
```

- 每个基金独立判断，互不干扰
- 快照使用精确键名（`fund_manager_snapshot`），无指纹后缀，每日 TTL 过期自动刷新

#### 持仓结构与集中度

一章三区块合一页签（`report/position_structure_sheet.py::write_position_structure_sheet`）：**一、持仓重合度矩阵**（基金×基金 Jaccard + 配对明细）；**二、持仓相关性矩阵**（品种×品种 Pearson 下三角矩阵 + 配对明细 + 滚动趋势子块（组合平均 60/120 折线 + 重点品对滚动 r + 口径句） + 说明）；**三、持仓集中度监控**（前3/5/10 占比 + 环比变化 + 三级预警）。任一区块数据不足时该区块独立降级（§1.4.5），互不影响。章节可见性由注册表 `data_flag_any=("position_relationship_data","concentration_data")` 判定（OR，悲观：两契约都未登记时不建页签/不渲染章节）。

重合度计算（`position_overlap.py::compute_overlap_matrix`，双指标）：

```
Jaccard 系数 = |A ∩ B| / |A ∪ B|
重叠率      = |A ∩ B| / min(|A|, |B|)
最终重合度  = max(Jaccard, 重叠率)
    │
    ▼
Excel 热力图着色：
    ≥50%  → 红底白字
    30~50% → 橙底白字
    15~30% → 黄底黑字
    >0     → 绿底黑字
    0%     → 无着色
```

触发条件：持仓中基金数量 ≥ 2 只（区块一）；区块三由 `report/fund_concentration.py::compute_concentration` 计算。相关性区块数据契约见附录 H（C19 契约）（`position_relationship_data`，11 键）。

**报告期时效**：重合度按市值加权，陈旧快照的权重与当期脱节最重，故**报告期陈旧的基金不进入矩阵**（口径见 `report/holdings_freshness.py`），被剔除者逐只在矩阵上方标注报告期与已过季度数——读者若发现某只基金缺席矩阵而无说明，只会以为矩阵算错了。风格分析与候选比较按模块语义保留陈旧数据并标注报告期（比例/分类口径不受市值时点影响）。

#### 持仓结构与集中度·区块三（持仓集中度监控）

基于持仓 TOP N 占比 + 环比变化（`fund_concentration.py`）：

```
取每只基金权重最大的前 3/5/10 只标的
    → 加总占比
    → fund_concentration_snapshot 环比比对
    │
    ▼
预警规则（与环比独立叠加）：
    · 前 10 占比环比 +20%  → 🔴 紧急
    · 前 10 占比环比 +10%  → ⚠️ 关注
    · 当前前 10 占比 >80%  → ⚠️ 关注
    · 首次运行               → 📋 首次
```

- 环比变化箭头：↑/↓ 标识方向
- **环比以报告期推进为前提**：快照增记 `period`（基金持仓报告期）。本次报告期与上期相同时，两次读的是同一份报告，环比恒为 0——报 0 会被读成「持仓结构没变化」，实为「没有新数据可比」，故改标「无对比意义」并注明原因，快照条目**原样沿用**（含 `check_date`），不刷新成一次新观察；报告期推进时照常对比。旧快照无 `period` 字段时维持原对比行为。页签含「报告期」列，陈旧者带「（陈旧）」后缀（保留数据 + 标注，区别于重合度矩阵的剔除口径）。
- 快照使用精确键名（`fund_concentration_snapshot`），月级 TTL

#### 风格与因子分析（一章四区块：风格表 + 因子回归 + 行业 Beta + 因子目录）

> **章节结构说明**：「风格与因子分析」章节（section key=`style_factor`，type=`fund_deep_analysis`、data_flag=`style_factor_data`）一章三区块：一、基金风格表（每只基金截面分类）；二、风格因子回归（组合整体时间序列回归）；三、行业 Beta 子表（组合对各行业指数敏感性，功能开关 `industry_beta` 默认关）；四、因子目录（25 因子五来源族池内横截面与评级，功能开关 `factor_catalog` 默认关、数据契约 `factor_catalog_data`）。区块间数据独立降级，任一块无数据不影响其余区块。C7 注册见 §8.3，序号为注册表 19 模块之一（连续编号）。

##### 区块一：基金风格表

基于持仓个股市值 + PE 数据的加权风格判定（`fund_style_classify.py` / `fund_style_report.py`）：

```
三级降级链路：
 push2 (精确) → Tencent 扩展字段 (可靠) → 代码前缀估算 (兜底)
    │
    ▼
市值判定：总市值 >500亿=大盘  100~500亿=中盘  <100亿=小盘
估值判定：PE/行业平均PE  <70%=价值  >130%=成长  其余=混合
    │
    ▼
加权投票 → 最终风格 = 市值权重最大的 size + 估值权重最大的 style
    │
    ▼
漂移检测：网格曼哈顿距离 |Δsize| + |Δstyle|（0~4）
    0=无  1=轻度  2=中度  ≥3=严重
```

**性能优化**：
- 会话级缓存委托 DataSourceRegistry session_cache（domain="extended"），同一股票仅首次 HTTP
- Tencent 二级降级基于 registry 熔断器（provider="tencent_style"），避免网络不可达时逐只等待超时
- 独立快照 `fund_style_snapshot` 精确键名，月级 TTL，不受菜单缓存命令影响

##### 区块二：风格因子回归

基于组合整体时间序列回归估算组合在价值/成长/质量因子上的暴露（β），输出"组合风格画像"（`analysis/style_factor_regression.py` / `report/_report_factor_metrics.py::compute_factor_exposure_data`，编排入口 `report/orchestrator.py`）。

> **与区块一（基金风格表）的差异化**：基金风格表是**每只基金的截面分类**（六宫格：市值×风格，基于 PE/市值阈值），回答"这只基金长什么样"；因子回归是**组合整体的时间序列回归**（因子收益回归组合收益得 β），回答"组合收益由什么风格因子驱动"。方法论与粒度均不同，报告 UI 文案需注明差异（"分类" vs "回归估算"），避免混淆"风格归属柱状图"与六宫格。

```
R_p = β₁R_value + β₂R_growth + β₃R_quality + α + ε
                          ↑ MVP 固定 3 因子（价值/成长/质量）
    结果输出为"风格归属柱状图"（价值/成长/质量各一根柱）
```

**模块分层（C14 依赖）**：

```
analysis/style_factor_regression.py   # 纯计算：接收(组合收益序列+因子收益序列) → OLS → 输出
    ↑ 无数据获取、无报告依赖，纯 pandas/numpy
analysis/industry_beta.py      # 纯计算：复用 compute_factor_exposure 单因子调用算行业 β（不重复实现）
report/orchestrator.py         # 编排：拉取组合收益(独立拉持仓历史 days=60 算 as-if) + 因子K线 + 行业指数K线
    │                           (fetch_index_history，走 chain) → 对齐 → 调纯计算
    ↓                           → 写 pipeline_data['style_factor_data']（C19，内嵌 industry_beta 子键）
report/ 渲染                   # 模板 context 传递（C14）→ 风格表 + 因子回归 + 行业 Beta（style_factor_sheet.py）
```

**候选因子代理指数（probe 判定依据，`scripts/_probes/csi.py` 内置候选表；统一入口 `scripts/probe.py csi`）**：

| 因子 | 中证指数代码 | 说明 | 数据可用性（365 天窗口探测，Tencent 主链路） |
|:----|:-----------:|:-----|:-----|
| 大盘价值 | 000919（300 价值） | 沪深 300 中价值因子得分最高 | ✅ 365 条，新鲜 |
| 大盘成长 | 000920（300 成长） | 沪深 300 中成长因子得分最高 | ❌ **停更**（自 2023-02-17 无数据，距今 >120 天）→ 成长因子采用 500 成长代理 |
| 小盘价值 | 000922（500 价值） | 中证 500 中价值因子得分最高 | ✅ 365 条，新鲜 |
| 小盘成长 | 000925（500 成长） | 中证 500 中成长因子得分最高 | ✅ 365 条，新鲜 |
| 质量因子 | 000930（中证 300 质量） | 沪深 300 中 ROE/杠杆/盈利稳定性高 | ✅ 365 条，新鲜 |
| 低波因子 | 000931（中证低波） | 扩展位，不进 MVP | ✅ 365 条，新鲜（附加候选） |

- 候选代码均带上证前缀（`sh`）与 `_A_INDICES` 既有指数同格式；主候选仅作**探测候选**，正式因子集合见下方 `FACTOR_INDICES`。
- 动量因子 A 股无标准 CSI 指数代码，MVP 不纳入。

**因子集合（分析模块常量 `FACTOR_INDICES`，不注册 `_A_INDICES`，见 C1 行）**：

| 因子 | 代理指数 | 代码 | 说明 |
|:----|:--------|:-----|:-----|
| 价值 | 300 价值 | sh000919 | 大盘价值代理 |
| 成长 | 500 成长 | sh000925 | 中盘成长代理，报告中注明代理口径 |
| 质量 | 300 质量 | sh000930 | 全指质量代理 |

- 低波（sh000931）不进 MVP 因子集合（保留为扩展位）
- `FACTOR_STALE_TRADING_DAYS=86` 新鲜度校验：最后一根 bar 距今 > 86 个**交易日**（约 4 个月）的因子从集合剔除并告警（`stale_factors`），剩余因子 < 2 时落 §1.4.5 数据不足分支。距离以交易日而非自然日计——长假（春节/国庆）会以十数个自然日拉开两个相邻交易日，按自然日差会把正常因子误判为停更。计数由 `core/trading_calendar.py::count_trading_days_elapsed` 提供，日期无法解析时按「未知」视为未停更（宁可不剔除也不误剔除）
- 基准对照 `baseline_betas`：沪深300（sh000300）在同一回归窗口的因子暴露，用于风格漂移判断（复用既有指数链路）

**数据新鲜度判定标准（`scripts/_probes/csi.py::evaluate`；因子暴露分析已实施，该脚本现为**周期性复核**工具（新机器/新窗口验证链路可用 + 停更预警），研究期曾充当前置决策闸门；按**自然日**计，与运行时守护的 `FACTOR_STALE_TRADING_DAYS`（交易日）口径有意不同）**：

- **有效** = K 线条数 ≥ `threshold` **且** 最新日期距今 ≤ `stale` 天。仅看条数会把停更指数误判为有效（如 300 成长仅有 2023 年旧数据）→ 双维度联合判定。
- **判定分级**：全部 5 个主候选有效 → `5f` 全量 5 因子可行；≥3 个有效 → `3f` MVP 3 因子可行（停更因子需找替代代理）；仅 1-2 个有效 → `infeasible` 不可实现。
- **默认参数**：`--days 365`（回归建议 ≥365）、`--threshold 60`、`--stale 120`（自然日口径，与运行时的 86 个交易日同为「约 4 个月」，见上）。

**计算方案**：

- **R_p 来源（重要）**：不能复用 `PortfolioHistoryCalculator.get_combined_timeseries().daily_returns`——该方法的 `days` 参数只传给基准，持仓历史走 chain 默认 `days=30`，组合收益序列固定 30 期不满足 ≥36 期需求。编排层独立拉取每只持仓历史（`fetch_with_incremental_fallback("history_stock"|"history_fund_otc", code, days=60)`，C4 会话缓存复用已拉 30 天、增量补至 60 天），按 as-if 语义（当前份额 × 历史价格）计算组合日收益序列，与 `portfolio_history` 章节口径一致。
- **回归序列对齐（关键）**：OLS 要求 R_p 与各因子收益严格按交易日对齐。pandas 构造 DataFrame 后 `merge`（on=`date`，inner join）对齐——因子收益由 CSI 指数 K 线 `close` 计算 pct_change，天然带日期索引；复用 `analysis/correlation.py` 的日期对齐思路，不另造机制。
- **NaN 处理**：持仓品种停牌/缺数据时 `daily_returns` 含 NaN，对 R_p 用 `dropna()` 剔除无效日后再 merge，记录实际有效样本数。
- **动态窗口（数据量自适应）**：回归窗口 = `min(60, 有效样本 - 自由度余量)`，优先满足 ≥36 下限，不足则数据不足分支。
- **OLS 实现**：`statsmodels` 未安装，用 `numpy.linalg.lstsq` 手写 OLS + t 检验，复用 `_math_utils.py` 的 t 分布函数（`_t_critical_95`/`_beta_se`），**不新增依赖**。
- **因子共线性**（500价值/500成长同源指数高度相关）：MVP 不做正交化/岭回归，仅输出**因子相关矩阵**作为诊断展示，并在风格归属图中对高相关因子的并列 β 给出文案提示。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| **C1** (代码类型判定中心化) | 因子代理指数代码统一走 `core/code_utils.py::is_index_code()` 判定；因子指数**不作为 `_A_INDICES` 成员**（避免污染实时指数行情循环与报告"指数对比"章节噪声），代码集合定义为分析模块内部常量 |
| **C6** (Provider Chain 必经) | 指数历史 K 线经 `fetcher/index.py::fetch_index_history()` 复用 `history_index` chain（`["tencent", "eastmoney", "sina", "hithink"]`），不绕过 Chain 直调 Provider。Sina 备用链路当前 404（降级接受），故补东方财富 push2his 为实际可用的第二源；腾讯与东方财富均故障时因子章节落 §1.4.5 数据不足分支 |
| **C7** (报告序号可配置) | 在 `core/registry.py` 的 `_REPORT_SECTION_DEFAULT` 注册条目（type=`fund_deep_analysis`、data_flag=`style_factor_data`），支持用户通过 `config.json` 自定义序号与开关，不硬编码序号。注册表 19 个模块序号连续（1~19），`style_factor` 为基金深度分析一章四区块（风格表 + 风格因子回归 + 行业 Beta 子表 + 因子目录区块） |
| **C14** (渲染期数据不可写入模块级全局变量) | 风格与因子数据通过模板 `render()` 的 context 参数传递，不写入 `_ENV.globals` 或模块级 dict |
| **C19** (pipeline_data Schema 契约) | 新增 `style_factor_data` 键（类型 `dict`，内嵌 `industry_beta` 子键），键结构见附录 H，先定义类型再使用 |
| **§1.4.5** (数据降级治理) | 区分两分支：① **数据不足**——因子指数历史不足 36 期或有效样本 < 36，标记 `style_factor_data.available=false`，显示"数据不足"占位文本，**不走 DegradationTracker**（系数据量不足，非故障）；② **数据源故障**——`fetch_index_history` 返回空（chain 全失败），走 DegradationTracker 记录 T2 降级事件，显示"数据源暂不可用"，与数据不足文案区分。行业 Beta 子表独立降级（`industry_beta=None` 开关关闭隐藏 / `available=false` 标题+占位），**绝不输出误导性数字** |

##### 区块三：行业 Beta 子表

组合对主要行业指数的敏感性分析（功能开关 `industry_beta` 默认关，`analysis/industry_beta.py`）：

```
持仓 A 股明细 → batch_fetch_industry_data → 行业市值聚合（暴露占比）
持仓历史 K 线 → as-if 组合日收益 + 行业指数 K 线（INDUSTRY_INDEX_MAP，中证行业指数）
    → compute_industry_beta_analysis（复用 compute_factor_exposure 单因子 OLS，不重复实现）
    → exposure / index_codes / betas / t_stats / significant / correlations / unmapped_industries
```

- **行业分类**：复用 `fetcher/industry.py::batch_fetch_industry_data` 返回的 `industry` 字段，按行业聚合持仓市值得暴露占比；行业名不在 `INDUSTRY_INDEX_MAP` 时归入 `unmapped_industries` 表尾展示（占位列）。
- **行业指数**：`INDUSTRY_INDEX_MAP`（银行=sh000986、证券=sz399975、白酒/食品饮料=sz399997、半导体/电子=sz399995、有色/贵金属=sz399996、煤炭=sz399998、医药/医药生物=sz399989、钢铁=sz399994、房地产=sh000980、能源=sh000928、环保=sz399973、保险=sz399983），K 线经 `fetcher/index.py::fetch_index_history` 复用 `history_index` chain（C6 必经）。
- **C1 合规**：行业指数代码统一走 `core/code_utils.py::is_index_code()` 判定；A 股持仓判定走 `is_a_share_code()`。
- **降级分支**：开关关闭 → `industry_beta=None` → 区块隐藏不渲染；开关开启但数据不足/指数拉取失败 → `available=false` + 标题 + 占位文本，不影响区块一/二。

### 4.9 资产穿透 TOP10

`compute_penetration_top10()` 纯计算函数，不依赖 openpyxl。

**分类逻辑**：QDII / ETF / 联接 / 债券 / 主动 / 直接持股，基于代码前缀 + 名称规则，所有底层判定委托至 `code_utils`。

**基金持仓取数阶梯（次序即陈年数据隔离）**：`providers/tiantian_holdings.py::fetch_fund_holdings` 按三跳取值——

| 跳 | 通道 | 产物 | 到达条件 |
|:--|:--|:--|:--|
| 第 1 跳 | 季报接口（年份域，最近 4 个完整季度回溯） | 当期持仓 + **真实报告期** | 总是先试 |
| 第 2 跳 | 基金主页面 HTML | 前十大；报告期**不从此处取**（页面无带语义标注的报告期，盲扫会误抓导航/日历控件里的当天，比空值更危险）；联接基金在此带回 `feeder_target_code` | 第 1 跳无当期持仓 |
| 第 3 跳 | 季报接口（**无年份**兜底） | 最早可得报告，**通常已陈旧** | 第 2 跳既无持仓也无目标 ETF 锚点 |

次序本身就是隔离手段：无年份兜底被压到第 3 跳、且联接基金在第 2 跳即返回，故它无法遮蔽联接基金。**取数层不做时效判定**——陈旧判据唯一归属 `report/holdings_freshness.py`（`is_stale_report` / `STALE_QUARTERS`），复制到取数层即「判据复制」，两者日后必然漂移；第 3 跳的陈年报告照常上送，由报告层时效闸门裁决并标注「报告期 X，距今 N 个完整季度」。

**联接基金穿透（内置恒开，无功能开关）**：ETF 联接基金的资产就是目标 ETF、本身不持有股票，故其季报股票表按构造为空（实测 `016055` 四个近季度的响应体均为 59/50 字节空内容）——修复前它在报告里恒为「持仓不可用」，QDII 联接基金因此拿不到任何底层暴露。穿透做法：目标 ETF 由基金主页面锚点**动态解析**（`parse_feeder_target_etf`，不维护「联接基金 → 目标 ETF」映射表，基金公司更换标的 ETF 时锚点随页面同步更新），再由 `fetcher/fund.py::with_feeder_penetration` 以目标 ETF 的持仓与报告期代理该基金的底层暴露，并在结果中记 `feeder_penetration = {target_code, target_name}` 供报告层标注来源。两处要点：①**幂等**——该函数在单条取数与批量两个接缝都调用，因为批量路径的 `execute_with_cache_check` 缓存命中时会跳过任务、穿透若只在网络路径做则热缓存下静默失效，故以「已带 `feeder_penetration` 即原样返回」保证重复调用无副作用；②**结构深度恒为 1**——只有名称含「联接」的基金才产出 `feeder_target_code`，而 ETF 名称不含「联接」，故目标基金永不产出新的目标，无需运行时深度计数。联动判定复用既有 `core/code_utils.py::is_index_link_by_name`（不新增第二份「是否联接」关键词表）；锚点两重区分（标签须止于「ETF」`(?!联)` + 目标须为场内代码）用于排除常规 ETF 页的**反向**链接（回指其场外联接基金）。归因口径为 **100%（不折算持有比例）**——联接基金约 95% 投向目标 ETF，未折算会轻微高估底层权重，报告中标「穿透自目标 ETF `XXXXXX`（未折算持有比例）」把该已知偏差公开；折算需解析联接基金自身的基金投资明细，当前无对应取数通道。


**板块分类（双层策略）**：

```
板块 = API 数据优先 (fetch_industry_data(code).industry)
         or 关键词回退 (classify_sector(name, code))
```

**行业/概念数据流**（与新闻关键词体系共享）：

```
持仓列表 + 穿透资产
    │ 提取所有唯一代码
    ▼
batch_fetch_industry_data(codes)
    │ API / 缓存
    ▼
industry_{code}.json
    │
    ├──→ 穿透模块：注入 sector 字段 → 板块列显示 API 数据
    │
    └──→ build_news_data()：行业名/概念名 → 追加到关键词列表
                             → 提高新闻匹配率
                             → 显示 "XX[概念]"
```

### 4.10 财经新闻热点与持仓关联分析

#### 整体流程

```
 五源并行获取
 ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────┐
 │新浪  │ │东财  │ │财联社 │ │华尔街见闻│ │akshare│
 └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘ └──┬───┘
    └────────┴────┬───┴─────┬─────┴──────────┘
                  │         │
                  ▼         ▼
           news_aggregator.py   每个源 per_source = max(500, news_top_count×2)
           (多源聚合去重)        news_{md5}.json 缓存，15 分钟 TTL
                  │             MD5 指纹含关键词/参数
                  ▼
           news_keywords.py
           关键词提取：持仓名称片段 + 代码 + 穿透资产 + 行业 + 概念
           4 种类型富化：持仓(0) → 穿透(1) → 概念(2) → 行业(3)
                  │
                  ▼
           news_correlator.py ←── news_correlation(持仓, 新闻) → 关联度评分
           按关联度排序 → 截取 news_top_count 条输出
                  │
           ┌─────┴─────┐
           │           │
           ▼           ▼
       HTML 渲染    LLM 二次关联（可选）
       (蓝/紫/橙/灰 着色)  enabled_llm.news_correlation
```

#### 订阅源端点

| 源 | API | 端点 |
|:----|:-----|:------|
| 新浪财经 | RSS + JSON | `feed.mix.sina.com.cn` |
| 东方财富 | 快讯列表 | `np-weblist.eastmoney.com/comm/web/getFastNewsList` |
| 财联社 | 滚动列表 | `www.cls.cn/v1/roll/get_roll_list` |
| 华尔街见闻 | 直播流 | `api-one.wallstcn.com/apiv1/content/lives`（无鉴权） |
| akshare | 封装 | 财新网 + CCTV |

#### 关键词体系

**4 种类型富化**：

| 类型编号 | 类型 | 来源 | HTML 着色 |
|:--------|:-----|:------|:---------|
| 0 | 持仓 | 持仓名称片段 | 蓝色 |
| 1 | 穿透 | 穿透资产名称 | 紫色 |
| 2 | 概念 | 东方财富 push2 概念板块 | 橙色 |
| 3 | 行业 | 东方财富 push2 行业分类 | 灰色 |

#### 召回策略

`per_source = max(500, news_top_count × 2)` — 每源原始获取量动态计算，保证去重后候选充足。最终截取 `news_top_count` 条按关联度排序输出。

#### 新闻去重算法

`_dedup_by_title()` 采用**多档模糊去重 + 实体 bigram + 英数 token 辅助判定 + 方向对立防护**策略，阈值基于 42560 条锚点分层采样校准（2026-08-17，误合并率从 ~70-80% 压降至可控区间）。判定口径（阈值常量 / 模板词表与掩码 / 标题归一化 / 实体 bigram 提取 / 相似度 / 方向词对 / 规则指纹）的唯一实现在 `providers/news_dedup_rules.py`；主流程模块 `providers/news_dedup.py` 只留锚点采集与比较循环，并原面 re-export 规则原语（既有引用面不变）。

##### 比较成本（判定不变的两层省算）

- **比较串缓存**：`_ratio_ready(norm)`（去通用日期 + 英文专名按长度分桶）与 `_char_multiset(norm)` 按标题字符串 `lru_cache`——同一「已保留项」在循环里被比较数十次，避免重复跑正则。
- **字符多重集上界预筛**：`2·Σ_c min(count_a, count_b) / (len_a + len_b)` 是 `SequenceMatcher.ratio` 的严格上界；上界低于候选门槛时连 `SequenceMatcher` 都不构造（省去成对 `quick_ratio` 的对象开销）。上界只用于跳过**不可能命中**的对。

等价性由 `src/test/unit/news/test_news_dedup_perf.py` 锁定：以「无预筛的完整 ratio 判定」为对照组跑同一语料，保留集合逐条一致。

##### 标题去重判定流程

```
_dedup_by_title(items)
    │
    ▼
遍历每篇新闻，对其已保留列表逐条比较：
    │
    ├── ① 同源判定（same_source = True）
    │       提取中文实体 bigram，≥ 4 即合并
    │       （同源不会出现方向对立报道，不依赖比率阈值）
    │
    ├── ② 跨源安全区（ratio ≥ 0.50）
    │       ratio 计算前剥离通用日期模式 + 英文词按长度分桶占位
    │       （_tk2_/_tk4_/_tk6_）+ 双向取 max 消除贪心方向不对称
    │       ├── ratio ≥ 0.65 且专名 bg ≥ 1 → 直接合并（改写型重复）
    │       └── 0.50 ≤ ratio < 0.65 → 需专名 bg ≥ 2 才合并
    │           （防"XX 签算力服务合同"模板骨架把 ratio 推到 0.5+ 的误合并）
    │
    ├── ③ 跨源候选区（0.35 ≤ ratio < 0.50）阶梯判定
    │       ├── 共享实体 bigram ≥ 3 → 合并（高实体重叠，低 ratio 门槛）
    │       ├── 共享 ≥ 2 且 ratio ≥ 0.375 且含**真专名** token → 合并
    │       │   （英数 token 需含字母且不在泛词否决表，纯数字不算："纳斯达克100
    │       │   vs KSE-100" 类共享数字、"两只 ETF 各自行情" 类跨主体泛词共现不再
    │       │   合并；CPI/PPI、荣耀IPO 仍靠此捕获）
    │       ├── 方向对立（上涨vs下跌/加息vs降息/站稳vs跌破分属两标题）且共享实体 → 不合并
    │       └── 否则跳过
    │
    └── ④ 子串包含降级
           短标题（≥6 字）被长标题完全包含 → 判定为重复
```

##### 核心概念

| 概念 | 含义 | 默认值 |
|:-----|:------|:-------|
| **ratio**（模糊匹配率） | `difflib.SequenceMatcher.ratio()` — 基于标准化标题的字符级相似度，双向取 max | — |
| **cross_threshold**（跨源阈值） | 跨源新闻触发候选区判定的最低 ratio 门槛 | `_CROSS_CANDIDATE_RATIO` = **0.35** |
| **直接合并区** | ratio ≥ 0.65，且专名 bg ≥ 1，直接合并（改写型重复） | `_CROSS_DIRECT_RATIO` = 0.65 |
| **安全区** | 0.50 ≤ ratio < 0.65，需专名 bg ≥ 2 才合并 | [`_CROSS_SAFE_RATIO`, 0.65) |
| **候选区** | 0.35 ≤ ratio < 0.50，阶梯判定（bg≥3 / bg=2+真专名token / 方向对立） | [0.35, 0.50) |
| **bigram（字符二元组）** | 中文标题的连续 2 字切片，用于提取实体身份 | — |
| **实体 bigram** | 掩码模板词后的 bigram 集合 + 英数 token + 长英文专名虚拟位 | STOP 集含 334 个词 |
| **bigram_overlap** | 两标题实体 bigram 交集大小 | 同源≥4/跨源≥3 判定重复 |
| **同源（same_source）** | 两新闻来自同一源头（如新浪 vs 新浪） | 仅依赖 bigram，不依赖 ratio |
| **跨源（cross_source）** | 两新闻来自不同源头 | 依赖 ratio + bigram + 方向对立多重判定 |

##### SequenceMatcher 比率

`difflib.SequenceMatcher.ratio()` 计算两个标准化标题的相似度（0.0~1.0），值越高表示字符级匹配越强。ratio 计算前经三重降噪：

1. `_normalize_title()` 预处理（去标点/过滤百分比 `\d+(?:\.?\d+)?%` 和金额 `\d+(?:\.?\d+)?[万亿]` 数字模式），并**保留空格**防英文 token 粘连（"Blackwell AI" → `blackwell ai`，不粘成 `blackwellai`）
2. 剥离 `\d{4}年|\d+月|\d+日` 通用日期模式（防止不同新闻因共享日期格式虚高 ratio，如"2026年7月票房破25亿" vs "2026年7月经营质量因子"）
3. 英文词按长度分桶占位（`_tk2_`/`_tk4_`/`_tk6_`）——统一占位符会让任意英文 token（msci/vn、ETF/CPI）共享同一占位虚高 ratio，分桶后仅同长度段英文词共享，恢复真实相似度

`SequenceMatcher` 贪心匹配存在方向不对称（含多个英文占位块的串上 `ratio(a,b)≠ratio(b,a)`，实测差异可达 0.18），取**双向 max** 消除方向偏差，保证同一对标题相似度判定与比较顺序无关。

- **0.65 以上**：大概率同一事件（改写型重复，如"英国央行如期维持利率不变" vs "英国央行以6比3票数维持利率不变"）
- **0.50~0.65**：可能同一事件，但需专名 bg ≥ 2 防模板骨架误合并（"行云科技签算力合同" vs "亿田智能签算力合同"）
- **0.35~0.50**：话题相关或弱重复，需实体 bigram 阶梯判定
- **0.35 以下**：不太可能同一事件

##### 实体 bigram 提取

`_extract_entity_bigrams()` 提取标题中的实体特征（中文 bigram + 英数 token + 长英文专名虚拟位）：

```python
步骤：
  ① 英数 token：提取 [a-zA-Z]+ 和 [0-9]+，长度 ≥ 2 过滤单字符噪声；
     孤立 4 位年份数字（19xx/20xx）不作专名 token；
     长度 ≥ 4 的英文专名（Anthropic/Meta/Helios）额外插入 _tk: 前缀
     虚拟 bigram 加权（共享专名在 bigram 计数中获得权重加成）
  ② 中文 bigram：正则去除非中文字符 → 先整体掩码 STOP 模板词（□ 占位）
     → 滑动窗口取连续 2 字，跳过含占位符的窗口
```

**STOP 词列表**（334 个，含财报/回购/指数/预警/地震/目标价/货币单位/通用业务词等模板词，不参与实体判定）。模板词在提取**前**被整体掩码替换（`_mask_stop`），杜绝跨词边界 bigram（"累计回购" → `□□`，不再产生"计回/购股"）泄漏——此前不同公司同类新闻天然共享 3-6 bigram（如"美的集团累计回购A股股份" vs "中远海控累计回购A股股份" bg=5 被误合并）。

**示例**：标题"英伟达Blackwell AI芯片发布" → 英数 token：`{"blackwell", "ai"}`（blackwell ≥4 字符另插 `_tk:blackwell`）；中文 bigram：掩码"发布"后 → 英伟、伟达、芯片、片发 → **实体集合：`{"blackwell", "ai", "_tk:blackwell", "英伟", "伟达", "芯片", "片发"}`**

##### 五档阈值策略

| 情境 | 判定规则 | 设计依据 |
|:-----|:---------|:---------|
| 同源（same_source） | 实体 bigram ≥ 4 判定重复 | 同源不会出现"突破3万亿"vs"跌破3万亿"对立报道，bigram 足以识别 |
| 跨源直接合并（ratio ≥ 0.65） | 需专名 bg ≥ 1 才合并 | 高相似改写重复（"英国央行如期维持利率不变" vs "英国央行以6比3票数维持利率不变"）；但不同公司同模板（"XX：2026年半年度净利润同比增长N%"）ratio 可高达 0.7+，掩码后 bg=0（公司名不同），不能当改写重复 |
| 跨源安全区（0.50 ≤ ratio < 0.65） | 需专名 bg ≥ 2 才合并 | 旧规则直接合并导致 40-50% 误合并（"行云科技签算力合同" vs "亿田智能签算力合同" 共享模板骨架 ratio 0.542） |
| 跨源候选区（0.35 ≤ ratio < 0.50） | bg ≥ 3 合并；bg = 2 且 ratio ≥ 0.375 且含**真专名** token 合并 | 纯中文公司名共享（"英伟达/伟达"）不代表同一事件；CPI/PPI、荣耀IPO 类共享专名 token 的真重复靠 bg=2 梯度捕获；**英数 token 需含字母且不在泛词否决表**（`_GENERIC_TOKENS`：ai/etf/cm/gb/ce/pcb——锚点实测靠这些词过闸的 bg=2 合并绝大多数为跨主体误合并，词表随校准回访扩充），纯数字（100/50/4000）不算专名证据——实测旧判定使 24 对共享数字的无关标题被合并（"纳斯达克100 vs KSE-100"、"F-35战机坠毁 vs 摧毁3架F35"） |
| 方向对立（候选区内） | 共享实体 + 相反方向词分属两标题 → 不合并（含价格方向对：站稳/跌破、走高/走低、上探/下探、回升/回落、走软/走强） | 跨源会同时出现"美联储或暂缓加息"vs"城堡证券预计美联储将加息"对立报道，同源假设不成立，必须显式防护；**不扩到安全区**——高相似对常在同一标题内同时提到两个方向词（"49股涨停2股跌停"）或对立方词属于另一主体（"标普500创纪录新高"+"油价下跌"），扩到安全区会误拦真重复（实测 6 对里 4 对属真重复） |
| 子串包含 | 短标题（≥6 字）被长标题完整包含 | 兜底，捕获大标题含小标题的极端情况 |

##### 锚点采集体系

去重判定边界案例**默认采集**写入 `data/calibration/dedup_anchors.jsonl`（append-only），供 `eval-dedup-threshold.py` 分析阈值合理性；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可显式关闭。锚点不参与去重判定，写侧只追加、**不读旧文件**（跨轮重复由校准工具按键去重），因此采集本身不增加报告耗时；39 MB 文件的加载与压缩已移出报告主流程（详见下）。

| 锚点规则 | 采集条件 | 用途 |
|:---------|:---------|:------|
| `same_src` | 同源 bigram 2~5 | 评估同源阈值是否过紧/过松 |
| `cross_safe` | 跨源安全区合并/跳过样本（含擦边 0.50~0.65） | 验证安全区分级（0.65 直接 / 0.50~0.65 需 bg≥2）是否合理 |
| `cross_merge` | 跨源候选区合并成功（bg≥3） | 验证候选区判定正确性 |
| `cross_merge_bg2` | 跨源候选区 bg=2 梯度合并成功（ratio≥0.375 + 非否决英数 token） | 验证专名 token 梯度规则 |
| `cross_skip` | 跨源候选区但 bigram 不足 | 评估是否需要降低阈值 |
| `cross_opposite` | 共享实体但方向对立被拦截 | 验证方向对立防护不误伤 |

**锚点记录字段**：`ts / title_a / title_b / source_a / source_b / ratio / bigram_overlap / merged / rule / anchor_rules_version`。

**规则时代指纹（`anchor_rules_version`）**：锚点文件跨规则时代累积（append-only），
而规则一调整旧样本就成了「另一个时代的产物」——实测混代会使校准报告严重失真
（收紧前存量里 46% 的 `cross_skip` 样本 ratio 低于当前候选区入口、`cross_safe` 中
508 条 `merged` 但 `bg=0`，是 0.50 直合时代留下的误合并样例）。故每条锚点写入
`news_dedup._rules_fingerprint()` 的结果（阈值/模板词表/方向词对/归一化正则 + 行为
探针的 SHA1 前 10 位）——**规则一改指纹自动变**，不依赖人工维护版本号；校准工具据此
区分时代，并拿标题用当前代码重算判定（详见下）。

**体积治理**：文件 append-only，跨轮同一标题对会重复追加；校准工具 `load_anchors` 按键去重（保留最早一条），故重复行不改变诊断结论，只影响体积。分层治理：① **写侧真追加**（`_append_anchor_lines`：单次 `write` + `fsync`，
写盘成本只与本次新增条数相关，与文件体积无关；读侧本就逐行容错，崩溃留下的半行不污染既有记录）；
② 体积只 stat 检查：超过 32 MB 时记录提示，压缩**默认不在报告路径执行**，由
`eval-dedup-threshold.py --compact` 或 `INVEST_DEDUP_MAINTENANCE=1` 显式触发（压缩按「每标题对保留最新一条 + **仅保留近
120 天**」双条件（`INVEST_DEDUP_ANCHOR_RETENTION_DAYS` 可覆盖，0 = 退回纯去重）——
实测仅按 key 去重压不动（标题对高度唯一，压后仍 37.9 MB），保留期才是体积上限，
压缩后 `.bak` **默认不保留**（与主文件等大、白占磁盘）——新文件经「非空 + 首行可解析」校验且 `os.replace` 原子替换后才删备份，`INVEST_DEDUP_KEEP_BACKUP=1` 可要求保留；
③ `scripts/eval-dedup-threshold.py` 评估后默认顺带压缩（分析用完整样本，随后按同一双条件幂等维护；`--no-compact` 只读、`--dry-run` 演练）；`--compact` 仍可单独压缩。

##### 校准工具

`.venv/bin/python scripts/eval-dedup-threshold.py` 分析 `data/calibration/dedup_anchors.jsonl`。

**口径（关键）**：工具**不信任锚点里的 `ratio`/`bigram_overlap`/`rule`**（它们是各次记录
当时的规则产物），而是拿 `title_a`/`title_b` 用当前代码重算并按当前阈值重判——阈值从
`news_dedup` 的 `_CROSS_*` / `_SAME_SRC_BIGRAM_MIN` 读取，相似度口径的唯一实现是
`news_dedup._pair_similarity`（与链路内判定同源，由等价性用例保证）。因此结论始终反映
**当前**规则；记录时指纹与当前不同的样本单列「历史规则时代」作参照。此前工具自写一套
硬编码阈值（候选区 0.30 vs 代码 0.35）与建议文本，长期输出误导性结论。

输出：

- 文件体积/唯一标题对/规则时代分布/与记录时判定不一致条数
- 按当前规则重判的分支分布（同源合并/未达、跨源安全合并/保留、主规则合并、专名梯度合并、方向对立、候选区跳过、未进候选区）
- 边界分析：`cross_skip` 的实体重叠分档与「降 `_CROSS_BG2_RATIO` 会新增多少合并」（含真专名的才是漏判候选）；`cross_merge` 的 bg=3 边界；`cross_safe` 的 0.50~0.65 擦边区；同源未达阈值的重叠分布
- 边界样本明细（默认前 10 条）与当前阈值规则摘要（数字均取自常量）

`--compact` 压缩锚点文件（每标题对保留最新一条，原子替换，幂等）；`--dry-run` 兼容保留
（仅 `--compact` 会写盘）。

> **已评估但未采纳的候选（避免重复讨论）**：把方向对立防护从候选区扩到安全区。实测安全区
> （ratio ≥ 0.50）命中方向词的 6 对样本中 4 对是**真重复**——高相似对常常在同一标题里同时
> 提到两个方向词（"49股涨停2股跌停"）、或对立方词属于另一主体（"标普500创纪录新高" + "油价
> 下跌"）——扩到安全区会误拦真重复，故防护仍只在候选区生效。

### 4.11 数据降级治理体系

#### 降级状态基础设施（`report/data_status.py`）

```
┌─────────────────────────────────────────────────────────────┐
│                    DataStatusItem（TypedDict）               │
│  { "available": bool,   数据是否可用                         │
│    "tier": "T2"/"T3"/"T4",  层级                             │
│    "message": str }      最终展示文本，直接渲染               │
│                                                             │
│  STATUS_MESSAGES（常量字典，Excel/HTML 两端共享）             │
│  rank_unavailable:       "基金业绩排名数据不可用，排名列显示 --"│
│  industry_unavailable:   "行业分类数据暂不可用（push2 不稳定）"│
│  profit_forecast:        "盈利预测数据不可用，EPS 列显示 --"  │
│  news_all_failed:        "新闻数据暂不可用，请检查网络连接"   │
│  history_correction:     "检测到历史数据修正，走势可能已重算" │
│  ...（共 24 条，覆盖价格/排名/行业/穿透/盈利/分红/指数/      │
│        基金深度分析/新闻/预警/历史走势）                            │
│                                                             │
│  TIER_PREFIX = {"T2": "⚠", "T3": "ℹ", "T4": "ℹ"}           │
└─────────────────────────────────────────────────────────────┘
```

**与 HTML 端 `raw_data_flags` 的交互边界**：
- `raw_data_flags = False` → 模块隐藏（不显示占位）
- `raw_data_flags = True` 且 `_data_status` 有失败项 → 页签底部显示状态摘要
- `raw_data_flags = True` 且 `_data_status` 全成功 → 一切正常，不渲染摘要

#### Excel 端

| 辅助函数 | 用途 |
|:---------|:------|
| `_write_placeholder(ws, message)` | 数据为空时写入灰色占位文本（合并单元格） |
| `_write_data_status_foot(ws, status)` | 页签底部追加数据源状态摘要行，按 tier 自动匹配前缀 |

#### HTML 端

| 机制 | 用途 |
|:-----|:------|
| `_safe_build_data_status(builder_fn, *args)` | 异常安全构建包装器，构建失败返回空状态 |
| `render_data_status(status)` Jinja2 宏 | 在 `report_template.html` 中条件渲染状态摘要 |

#### DegradationTracker 双信号降级

| 信号 | 默认阈值 | 说明 |
|:-----|:---------|:------|
| 连续失败计数 | T2: 2 次 / T3: 2 次 / T4: 1 次 | 累计失败次数达阈值后触发降级 |
| 缓存陈旧天数 | T2: 3 天 / T3: 14 天 / T4: 14 天 | 距上次成功获取的天数超阈值后触发降级 |

> **注**：以上为 `config.json` 的 `degradation` 出厂默认值（T4 为 14 天）。代码内兜底常量 `report/data_status.py::_DEFAULT_STALE_DAYS`（T4=7 天）仅在用户配置缺少该键时生效，不作为默认值口径。

可配置于 `config.json` 的 `degradation` 字段。支持跨会话持久化到 `data/state/.degradation_state.json`。

**报告运行边界（`report/_run_scope.py`）**：每份报告入口 `start_report_run()` 只重置**轮次语义**的观测状态，不动跨报告事实——① `DegradationTracker.begin_report()` 清空**事件日志**（数据质量块 / 可用性矩阵 / 降级摘要的语义都是「本次报告期间发生了什么」），但保留 `_counts` 与 `_last_success`（降级判定与跨会话陈旧的事实来源）；② 重置 `self_review` 全局载体，上一轮自检区块不得残留到本轮；③ 取 `get_session_usage()` 深拷贝作**用量基线**，收尾 `_record_llm_context` 按基线算 delta 写入 perf（TUI「本会话累计」仍跨报告累计，单份报告的 token/调用数不翻倍）。任一步失败只记 DEBUG——观测隔离不得阻断报告生成。

**与 DataSourceRegistry 的职责边界**：

```
DataSourceRegistry（熔断层）  ─  管"这个 Provider 能不能调用"
    HTTP 层面的快速跳过
    per-provider 粒度
    固定阈值（连续 3 次失败）+ 指数退避冷却
    自动冷却恢复

DegradationTracker（降级决策层） ─  管"这批数据能不能信任"
    数据质量层面的占位/降级决策
    per-data_source 粒度
    双信号（失败计数+缓存陈旧），配置可调阈值
    跨会话持久化
```

#### LLM 输出侧质量分级（`report/llm_quality.py`，开关 `module_quality_gate` 默认开）

上节的降级治理面向**数据源侧（输入）**；本模块把同一「降级披露」思路扩展到 **LLM 输出侧**——回答「这段模型输出能不能信」。借鉴外部 `quality_gate` 的 A~F 分级，但**只标注不阻断**：劣级不重试、不改生成流程、不影响缓存读写。

| 评级 | 触发条件（自上而下首个命中者胜出） |
|:----:|:-----------------------------------|
| F | 剥离 HTML 标签后正文为空 |
| D | 命中降级占位（`llm/fallback.py::is_placeholder_content`）/ 截断标记（`TRUNCATION_MARKER`），或正文短于该模块下限 |
| C | 缺失该模块提示词要求的必需章节标记 |
| B | 结构与必需章节齐备，但正文短于该模块参考篇幅 |
| A | 结构与篇幅均达标 |

- **上屏策略**：A/B 视为健康输出，**零噪音**；C/D（「内容在但存在缺陷」）在模块 HTML 字符串**头部拼接**一条 `【内容质量提示】` 内联样式横幅（含评级 + 具体原因 + 「仅供降级参考」提示），并向 reporter 汇总告警一次。内容缺失型（F 空内容 / D 占位与截断）已有各自的醒目提示（占位文本写明「当前无法生成」、空内容由模板兜底），**不叠加横幅**，避免同一件事说两遍。
- **载体复用**：横幅直接拼进模块 HTML 字符串，与既有的截断标记、缓存命中行、事实校验摘要同一套载体——不新增 `pipeline_data` 契约键（附录 H 无需变更）、不扩展报告生成函数的参数表，HTML（`{{ global_macro | safe }}` 等）与 Excel（`_write_content_sheet` 按块标签分段 + `_strip_html` 渲染）**两条输出路径同时生效**。
- **横幅前缀刻意避开 `⚠ `**：Excel 侧按行首 `⚠ ` 识别事实校验告警块（`_FACT_CHECK_FAIL_RE` 无 MULTILINE 的 `^⚠ `），故横幅以 `【内容质量提示】` 起首，避免被误判为校验告警行着色。
- **只读分级**：判定依据全部来自内容本身（正文长度、必需章节标记、占位签名），无额外数据依赖；读的是缓存**之后**的内容，**不写回缓存**（缓存始终保持 LLM 原始输出）。
- **阈值与标记的维护纪律**：各模块长度双阈值 (降级下限, 参考篇幅) 按 `data/cache/` 真实健康输出实测标定（取实测篇幅约 25%~40% / 60%~65%，只拦截「明显残缺」而非「写得比其他模块短」）；必需章节标记只收录「提示词明文规定固定章节清单」的模块（持仓体检 7 项 / 穿透深度 5 项），纯散文模块（全球政经）与结构随辩论模式变化的模块（智囊团复盘）只做长度分级。标记与提示词章节规定**须同步**——由 `test_module_markers_match_prompts` 直接比对 `prompts_core` 的 System Prompt 常量，改提示词而标记未跟随即报错，防分级静默误判。
- **接线**：经报告管线实验挂载点 `report/_experimental_seams.py::apply_module_quality_banners` 接入，调用点位于决策登记之后、`perf.stop()` 之前——横幅会改变内容文本，须避开操作建议表的解析。异常守护由挂载点统一提供（分级逻辑自身异常只降级为一条告警），不打断报告主链路。

### 4.12 组合演进（多快照趋势）

聚合 `data/history/snapshots/snapshot_{timestamp}.json` 多期快照，输出组合市值/HHI/TOP 持仓占比的趋势数据（`analysis/portfolio_evolution.py` / `report/orchestrator.py` 组装），供 Excel「组合演进」页签与 HTML「组合演进」章节消费（3 张 Chart.js 图：总市值与总盈亏 / HHI / TOP 持仓占比变迁）。

**数据口径**：快照为历史时点截图（含持仓结构 + 总市值），演进数据纯本地计算、零网络请求。历史快照可能缺市值（`market_value=0.0`），权重回退到成本口径（`cost=份额×每份成本`）。

**模块分层（C14 依赖）**：

```
analysis/portfolio_evolution.py   # 纯计算：读快照 JSON → 趋势聚合 → C19 契约 evolution_data
    ↑ 无数据获取、无报告依赖
report/orchestrator.py            # 编排：聚合快照 → 写 pipeline_data['evolution_data']（C19）
report/ 渲染                      # Excel 页签 + HTML 章节（模板 context 传递，C14）
```

**并发取数、顺序汇总**：历史走势的并发只用于**取数**，汇总按输入持仓顺序（不按 `as_completed` 完成顺序）——完成顺序随网络/线程调度抖动，按它追加会让两次同数据报告的「已纳入走势计算」清单顺序不同、逐日浮点累加顺序漂移。同类实现（任何线程池汇总）都应遵守该纪律：结果集按稳定键（输入顺序/代码）排列后再参与计算与展示。

**快照数下限**：`MIN_SNAPSHOTS=3`，有效快照不足时 `evolution_data.available=false`，展示层写「组合演进数据不足」占位（§1.4.5 降级）。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| **C3** (缓存原子写入) | 快照写入沿用既有原子写（temp + rename），聚合读取对缺文件/损坏 JSON 容错跳过 |
| **C7** (报告序号可配置) | `portfolio_evolution` 注册于 `_REPORT_SECTION_DEFAULT`（type=`evolution`、data_flag=`evolution_data`、number=14），序号/名称可配置，不硬编码；独立开关 `enable_portfolio_evolution` 控制 board 层可见性。本仓库 `config.json` 的 `report_section_order` 显式列出完整 18 项（`llm_usage` 强制末位、不列入本表；合计 19 个模块）且与出厂默认同序（`action`=7、组合演进=14、持仓变动复盘=15、调仓纪律回放=16） |
| **C14** (渲染期数据不可写入模块级全局变量) | evolution_data 通过模板 `render()` context 传递，不写 `_ENV.globals` |
| **C19** (pipeline_data Schema 契约) | 新增 `evolution_data` 键（类型 `dict`），键结构见附录 H，先定义类型再使用 |
| **C20** (HTML 图表图下说明强制) | 3 张 Chart.js 图各配 `.chart-caption` 图下说明，随 canvas 渲染分支同步出现 |
| **§1.4.5** (数据降级治理) | 有效快照 < MIN_SNAPSHOTS → `available=false`，章节写占位（数据量不足，非故障，不走 DegradationTracker）；快照文件缺失/损坏时逐文件跳过并告警 |

### 4.13 调仓 What-if 模拟

双持仓（基准 base / 目标 candidate）**成本口径截面比较**，输出 diff 报告（`analysis/whatif.py` 计算 → `report/whatif_operations.py` 编排 → `report/whatif_writer.py` 输出 Excel + HTML 独立报告）。

**设计边界（数据源可行性约束）**：
- **成本口径**：candidate 无市场历史，无法取实时市值/净值，所有指标（权重/集中度）基于 `成本 = 份额 × 每份成本`，纯结构层、**零网络请求**（"只能做截面比较"）。
- **回测 opt-in**：默认不产出任何回测类结论；仅当指定**调仓生效日**（CLI `--effective-date` / TUI 生效日提示）时，opt-in 联网取生效日后行情做时序回测（`report/whatif_operations.py::build_whatif_backtest` 取历史 → `analysis/whatif_backtest.py` 纯计算）。
- **回测为假设推演**：回测结果（区间/年化收益、波动率、夏普、最大回撤）为 as-if 市值模拟、**不构成收益承诺**；数据不足/不可对齐 → 回测 `available=false` 降级，**不阻塞主报告**。
- **双份数据内存**：同时加载 base + candidate 两份持仓计算，内存与缓存用量约为单份的 2 倍；未指定生效日时不做时间序列比较。
- **勿用于回测误用**：用户不得把 What-if 的截面量化指标当作回测结果——它没有真实交易数据支撑，仅反映结构差异。

**变动类型**（复用 `schemas/history.py _DiffAction` 语义）：新增 / 清仓 / 加仓 / 减仓 / 不变。

**模块分层（C14 依赖 + analysis 单向依赖纪律）**：

```
analysis/whatif.py               # 纯计算：_merge_holdings(按 code 合并多账户) → 成本权重/HHI → 变动分类
analysis/whatif_backtest.py      # 纯计算（不联网、不 import report/）：生效日→请求天数、并集+LOCF 对齐、
                                 #   归一化到 100、区间/年化收益/波动率/夏普/最大回撤、回撤序列
    ↑ 复用 analysis/metrics.py 的 sharpe_ratio/annualized_return/max_drawdown_pct、analysis/whatif.py 的 _arrow
report/portfolio_history.py      # as-if 时序引擎：close×shares 综合走势（days 已透传到持仓历史链路）
report/whatif_operations.py      # 共享层编排：build_whatif_data → build_whatif_backtest（联网取历史）→ 写报告
report/whatif_sheet.py           # Excel 3 页签 + 条件第 4 页签「时序回测」（指定生效日时）
report/whatif_writer.py          # 编排双产物：调仓模拟.xlsx / .html（最新版固定名 + 日期目录归档版）+ Chart.js 资产复制/内嵌（单文件自包含）
cli/_handlers.py               # whatif 子命令处理器（_handle_whatif）：--candidate 必填、--base 可选（缺省用 config 持仓）、--effective-date 透传（argparse 定义与类型钩子在 cli/_parser.py，钩子经共享层 normalize_effective_date 前置校验）
tui/handlers_whatif.py           # [W] 入口：文件选择 + 生效日交互提示（_prompt_effective_date，校验委托共享层、非法重新询问）
```

**C19 契约 `whatif_data`（独立报告，非 pipeline_data 键）**：`{"available", "status", "base_file", "candidate_file", "base", "candidate", "summary", "categories", "changes", "stats", "reason", "backtest"?}`（`backtest` 仅指定生效日时存在）。两侧均为空 → `available=false` 降级；单侧为空视为合法的「全部清仓/全部新增」对比，仍可计算。`backtest` 子契约：`{"available", "status("ok"/"degraded"/"unavailable"), "reason", "effective_date", "metrics":[{key,label,unit("pct"/"ratio"),base,candidate,delta,arrow}]（5 行）, "series":{labels, base, candidate, base_drawdown, candidate_drawdown}}`，净值归一化到 100、回撤为负百分比。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| **C7** (报告序号可配置) | whatif 为**独立报告产物**（调仓模拟.xlsx/.html，最新版固定名 + 日期目录归档版），不注册进主报告 `_REPORT_SECTION_DEFAULT` |
| **C14** (渲染期数据不可写入模块级全局变量) | whatif_data 通过模板 `render()` context 传递，不写 `_ENV.globals`；回测图表负载经 `_trim_whatif_backtest_chart_data` 裁剪 |
| **C19** (pipeline_data Schema 契约) | `whatif_data` 契约独立于主报告管线（不经 `pipeline_data_builder.build()`），本报告自建契约并在模块 docstring 声明 |
| **C20** (HTML 图表图下说明强制) | 资产配置对比双环形图 + 时序回测 2 张线图（归一化净值/回撤）各配 `.chart-caption` 图下说明，随 canvas 渲染分支同步出现 |
| **§1.4.5** (数据降级治理) | 两侧为空 → `available=false`，Excel 摘要页/HTML 写「调仓对比数据暂不可用」占位；回测不可用 → 回测区隐藏/占位、不阻塞主报告；CLI 层对空持仓文件直接报错返回 `_EXIT_SEVERE` |

### 4.14 HTML 暗色模式

主报告与调仓 What-if 报告支持深/浅色主题切换。右上角浮动按钮切换，偏好经 `localStorage`（键 `investor-theme-dark`，'1'/'0'）持久化；**首次默认浅色**（不跟随系统，避免与用户打印/系统偏好耦合）。

**CSS 变量体系**：页面级颜色统一为 CSS 变量，`:root` 定义浅色默认值，`[data-theme="dark"]` 覆盖深色值；语义色提亮（浅色 `--profit:#CC0000 / --loss:#009900`；深色 `--profit:#ff6b6b / --loss:#4caf50`，红涨绿跌惯例保持）。品牌蓝 `#2E75B6`（header/section-title/toc/按钮）与 Chart.js 数据调色板（drawSimpleChart、热力图图例色）为数据/品牌色，不随主题变化。Jinja 过滤器（`profit_color`/`price_type_color`/`sentiment_colorize`）输出 `var(--xxx)` 表达式，模板内联 style 自动适配主题。

**Chart.js 重绘**：`window.ChartTheme` 在脚本加载时一次性烘焙进图表配置。`theme.js::refreshChartTheme()` 切换时重读 CSS 变量原位更新 `ChartTheme`，`applyThemeToCharts()` 用 **`Chart.getChart(canvas)`**（Chart.js v4 全局 API）+ `querySelectorAll('canvas')` 遍历收集图表，更新 `legend.labels.color` 与各 `scales.*` 的 `ticks/grid/angleLines/pointLabels` 后 `chart.update()`（`animation=false` 下同步渲染）。对 report（经 ChartPrint 注册）与 whatif（未加载 chart-print.js）通用，非 Chart.js canvas 自然跳过。

**打印协调**：暗色下 `@media print` 的 CSS 覆盖只影响非 canvas 部分，canvas 像素仍暗色。`theme.js` 用**捕获阶段**监听 `beforeprint`（`addEventListener('beforeprint', fn, true)`——捕获先于 chart-print.js 的冒泡阶段快照执行）：若暗色，先移除 `data-theme` + 重读变量 + 遍历图表 `update()`（同步渲染浅色像素）→ chart-print.js 快照抓到浅色；`afterprint` 捕获阶段恢复暗色 + 重绘（`restoreAfterPrint` 标志记录状态）。`@media print` 同时隐藏 `.theme-toggle-btn`。

**JS 资产**：`html_writer_assets.py::JS_ASSETS` 资产清单（9 个本地 bundle，含主题 `theme.js` 与正文折叠 `fold.js`），whatif 复用同一复制函数；两模板均在 `toc.js` 之后以 `defer` 加载（DOMContentLoaded 前执行，无 FOUC）。**单文件自包含**：`html_writer_assets.py::_inline_js_assets` 在保存前把 9 个资产内容内嵌——移除 head 区 `<script defer src="X.js">` 外链标签，按 bundle 依赖顺序追加为行内 `<script>` 到 `</body>` 前（复刻 defer 时序：DOM 解析完后、DOMContentLoaded 前按序执行，chart-init 能取到已解析 canvas/chart-data、toc.js/theme.js 内部 DOMContentLoaded 监听仍触发），报告 HTML 单文件完全自包含（Web 下载到其他目录/单发移动端浏览不依赖同目录松散 JS）；`_copy_js_assets` 保留作兜底（资产缺失/读取失败/含 `</script` 序列时该资产外链标签保留原位，松散文件仍可加载）。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| **C14** (渲染期数据不可写入模块级全局变量) | 暗色模式为前端静态资源 + Jinja 过滤器变更：过滤器为纯函数（`profit_color`/`price_type_color` 返回 CSS 变量表达式），不写 `_ENV.globals`，渲染数据仍经模板 context 传递 |
| **C20** (HTML 图表图下说明强制) | 主题不改变图表 DOM 结构与图下说明（`.chart-caption`）渲染分支 |
| **§1.4.5** (数据降级治理) | `window.Chart` 缺失时 `theme.js` 守卫跳过图表重绘（仅切换页面 CSS 变量），不崩溃；离线降级（drawSimpleChart 回退渲染）不受影响 |

### 4.15 决策头结构化与决策词归一解析

决策词（减仓/加仓/持有）此前只存在于提示词契约与展示层，唯一消费方是决策账本的抽取模块，且以**子串包含**判方向——`不建议加仓` 会被判成 `+1`、`加仓或减仓` 会取靠前词判成 `-1`。误判后果不是显示错一行，而是**按相反方向写入 `data/state/decision_ledger.jsonl`**，日后用真实行情结算时污染命中率统计。本项把决策词从「展示文本」升格为「可解析数据」。

**分层（`core/` 为共享层，两个消费方向都无环）**：

```
core/decision_header.py          # 词表 + 归一解析 + 结构化头解析 + 缓存后缀；零项目内业务依赖
    ↑ 单向依赖（仅取 core.decision_ledger 的方向常量作单一事实来源）
llm/prompts_action.py            # 提示词契约段（开关门控）  ← llm/ 不得依赖 report/
report/decision_llm_capture.py   # 抽取：结构化优先 → 表格兜底
```

方向常量复用 `core.decision_ledger` 的 `DIRECTION_LONG/SHORT/FLAT`，不另立一套 int 常量。

**归一判据（`parse_decision_word`）**：

| 判据 | 说明 |
|:-----|:-----|
| 标签优先于裸词 | 先对整格做精确匹配（剥离 emoji/符号/空白后），命中即返回；未命中才降级全文扫描 |
| 长词优先 | 词表按长度降序，避免短词劫持 |
| 否定前缀守卫 | 命中词**左侧**同子句内出现 `NEGATION_PREFIXES`（不建议/不宜/暂不/暂缓/无需/不必/不用/不再/不要/不应/避免/防止/切勿/切忌/切莫）或单字 `不/勿` → 判未命中。仅看左侧：右侧限定语（`建议加仓不必追高`）不构成否定 |
| 复合词左边界 | 命中词紧邻左字符若属 `COMPOUND_PREFIX_CHARS`（`加减增`）→ 判为复合词片段而跳过（`加减仓位`/`增减持`）。中文无词间空格，无法照搬 `\b`，故取**窄字符集**：只有这三字能与其后的 `仓/持` 组成方向二义的复合短语；不收 `持/买/卖/清/观/止/建`，否则误杀「坚持持有」「逢低买入」等正常表述（已编码为回归矩阵） |
| 二义不猜 | 扫描命中多个不同方向 → 返回 None（不做「取第一个」的静默选择） |
| 默认值 = None | 判不出即 None 且**不登记**。不落「持有」或任何方向默认值 |

词表分**规范词**（减仓/加仓/持有，提示词契约固定三值）与**扩展词**（清仓·减持·卖出·止损 / 增持·买入·建仓 / 观望），只收语义单向词——`止盈`（可能部分落袋也可能清仓）、`调仓`（方向不明）**不入词表**：宁可判不出，不可判错。

**结构化决策头（已内置）**：提示词末尾恒追加一行 `决策头：{"decisions":[{"code","action","priority"}]}` 契约；抽取侧先 `parse_structured_header` 读结构化头，逐字段归一校验（`action` 必须经上述判据归一为方向，否则丢弃该条；`code` 必须 6 位数字），全批不可用 → 回落确定性表格解析。两路产物形状统一为 `{code, name, direction, magnitude, detail, …}`（结构化头的 `priority` 在解析侧即归一为 `magnitude`），`_collect_decision` 对两路走同一段登记纪律（持有剔除 / code 白名单 / 名称回填 / detail 空串回补 / 同码取高）。

- **载荷提取用花括号配平扫描**（字符串/转义感知），而非 `find("{")`/`rfind("}")`——后者在同一行出现两个 JSON 对象时会把跨度拉通成非法 JSON；`决策头：` 后为空行时以空串兜底，不抛 `IndexError`。
- **缓存键同源**：开关影响提示词 → **写侧指纹**与**预检指纹**都取自 `llm/module_fingerprint.py::expert_review_fingerprint()` 内无条件调用的 `structured_header_cache_suffix()`（开关判定收敛在函数内部）。关闭返回 `""`（键不变、不误伤旧缓存）；开启两侧同步换键，避免预检命中旧键而跳过重生成使开关形同虚设。关闭时提示词**逐字节不变**。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| 分层 / 无环依赖 | `core/decision_header.py` 零项目内业务依赖；`report/`、`llm/` 单向依赖 `core/`，解析器不 import `report/` |
| 不引入新依赖 | 纯标准库（`re` / `json`）；明确不引入 pydantic/langchain/SDK |
| 实验项默认关 | 缺省 `False`；关闭时提示词逐字节不变、缓存不扰动 |
| 无静默默认值 | 判不出返回 None 且不登记（拒绝「失败丢默认值填充」） |
| 持久化隔离 | 不新增持久化文件（账本路径沿用既有 conftest 隔离） |

[↑ 回到顶部](#目录)

### 4.16 确定性数值信号沉淀与实时/非实时标签纪律

市场温度、估值分位、尾部风险、风格因子、再平衡超限这五类评级由确定性算法算出，此前只活在一次报告生成的内存里与当页展示中——报告落盘即散失，跨期无法回答「上期判高估，事后对不对」。本项把这五类评级沉淀为追加型账本 `data/state/signal_ledger.jsonl`（因子目录随功能开关 `factor_catalog` 追加为第 6 类），并给每条记录附**实时/非实时**来源标签，统计与提示词摘要**默认只算实时记录**（借鉴 augur `backtest.py` 的 `data_source` 标签与排行榜默认 `live_only` 纪律），防非实时数据算出的评级冒充真实战绩。

**分层（`core/` 为共享层，两个消费方向都无环）**：

```
core/jsonl_store.py        # 原子追加 + 容错读取 + 按龄裁剪原语（零项目内依赖）
    ↑ 委托（各自保持 prefix/日志标签，行为逐字不变）
core/perf.py               # 性能历史
core/decision_ledger.py    # 决策账本（序列化口径：键排序 + ensure_ascii=False）
core/signal_ledger.py      # 信号账本：登记/幂等/折叠/摘要；不 import analysis
    ↑ 单向依赖（仅借 core.decision_ledger 的方向常量作单一事实来源）
report/signal_record.py    # 适配器：各信号类型评级 → 记录（唯一持有 analysis 词表映射的一侧）
llm/skeleton.py            # 摘要注入 expert_review 提示词（开关门控）
```

评级→方向词表映射（`低估/便宜 → +1`、`高估/超限 → -1` 等）与尾部风险分档阈值落在 `report/signal_record.py`：`core/` 不得依赖 `analysis/`，故语义映射不下沉到账本层，账本只存通用整数方向。

**实时/非实时判据（`signal_record` 侧）**：

| 信号 | 判定依据 | 说明 |
|:-----|:---------|:-----|
| 持仓级（估值分位、再平衡超限） | 该 code 的 `data_freshness` 条目 | `fresh` → 实时；非 fresh 或未识别取值 → 非实时并回显原始新鲜度文案 |
| 指数级（市场温度、风格因子） | 降级事件 `source_key` 以 `index_history_` 开头 | 命中即本次降级 → 非实时 |
| 组合级（尾部风险） | 降级事件 `source_key` 以 `price_` / `fund_` 开头 | 命中即本次降级 → 非实时 |
| 组合级/指数级无逐品种新鲜度 | 乐观缺省「实时」并注明理由 | 无逐品种条目可证伪时取实时，理由字段显式记录，不静默 |

「非实时」不引入新的合成数据开关，直接复用既有数据质量设施（逐品种 `data_freshness` + 降级事件），避免另立一套与既有降级治理并行的标签体系。仅可证明为实时才算实时：未识别的新鲜度取值一律判非实时（除 `FRESHNESS_FRESH` 外全部保守处理），文案取自 `core.data_freshness.FRESHNESS_LABELS`，不另写一份。

**记录与幂等**：`id = {report_date}|{signal_type}|{subject}`；`append_signals` 批量读一次 → 按 id 去重（含批内重复）→ 一次原子写。同日重跑不重复入账（`registered` 归零、`skipped` 计数），次日照常入账。非有限数值（`NaN`/`±inf`）经 `_safe_number` 归一为 `None` 后才落盘，防写出非法 JSON。

**摘要与缓存键同源**：`summary_block()` 在开关关闭、或实时样本不足 `MIN_SUMMARY_SAMPLE` 时返回 `""`（判定无条件执行，故「开关关闭 → 全链路无感」在注入路径同样成立）；输出逐类一行 + 非实时备注。开关影响提示词 → **写侧指纹**与**预检指纹**都取自 `llm/module_fingerprint.py::expert_review_fingerprint()` 内无条件调用的 `signal_ledger.summary_cache_suffix()`（无块返回 `""`，有块返回 `_sg` + 摘要 md5 前 12 位），开关判定收敛在函数内部。

**报告挂载点（末位）**：登记经 `report/_experimental_seams.py::record_deterministic_signals` 接入，置于决策头结构化之后、`perf.stop()` 之前，而非更早的分析阶段——尾部风险等键在 LLM 生成阶段才注入 `pipeline_data`，过早登记会漏采。适配器对缺失键逐项跳过，故不构成硬依赖；异常守护由挂载点统一提供，异常只告警不中断报告生成。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| 分层 / 无环依赖 | `core/signal_ledger.py` 不 import `analysis/`；词表映射在 `report/` 适配器；`llm/` 单向依赖 `core/` |
| 不重复实现（DRY） | 原子追加原语抽为 `core/jsonl_store.py`，`perf`/`decision_ledger`/`signal_ledger` 三处共用，不新增第三份拷贝 |
| 实验项默认关 | 缺省 `False`；关闭时提示词逐字节不变、不写账本、摘要返回空 |
| 无静默默认值 | 判不出来源即非实时（保守）；无逐品种条目时乐观取实时但**显式记录理由**；非有限数值归一为 `None` 而非写出 |
| 持久化隔离 | 账本路径 `data/state/signal_ledger.jsonl` 已纳入测试隔离（conftest 重定向到 tmp） |
| 不引入新依赖 | 纯标准库（`json` / `hashlib` / `math`） |

[↑ 回到顶部](#目录)

---

### 4.17 健壮性三件套（数值归一防线 / 失败原因可读 / 系统自检）

借鉴 augur 的健壮性实践识别出三项独立改进，按「A 真缺陷修复（无开关，默认路径生效）+ B 新增能力（开关门控）」拆分：**A1 数值归一防线**、**A2 失败原因可读** 属缺陷修复，**B1 系统自检** 是只读诊断（开关 `doctor_check`，默认开启）。三者互不依赖，各自独立生效。

#### 4.17.1 A1 数值归一防线（无开关）

**缺陷**：`float("nan")` / `float("±inf")` **不抛异常**，故各 provider 解析器里 `try: float(x) / except (TypeError, ValueError)` 形态的兜底对它们完全无效——脏值经 `fetcher/` 一路穿透到市值核算、收益序列与绘图数据，且在比较运算中表现得像正常数值（`nan > 0` 为假、`inf > 0` 为真），下游只能靠逐处判空补救。

改动前的实际形态是**约 10 个互不一致的私有解析器 + 4 种失败口径**：有的返 `0.0`、有的返 `None`、有的抛异常；且被依赖最广的 `providers/utils.safe_float`（基金净值/排名链路）恰是 NaN/±inf 防线最弱的一个。另有一类更隐蔽的漏点——形如 `value or 0.0` 的「空值兜底」对 **NaN 完全失效**（`nan or 0.0` 求值为 `nan`，因 NaN 是 truthy），脏值借此绕过判空直入聚合。

**修复**共三层，合法输入的返回**逐字不变**（仅脏值路径改变）：

**① 新建归一原语 `core/num_utils.py`**（`core/` 层，无跨层依赖）：

| 函数 | 语义 |
|:-----|:-----|
| `safe_num(value, *, default=None)` | **宽容**归一：数值字符串先尝试解析（对接 JSON/网页脏字段），失败或非有限 → `default`；**`int` 原样返回**（不强行转 `float`，避免整数份额/ID 被改写）；拒绝 `bool` |
| `strict_num(value, *, default=None)` | **严格**归一：只接受有限 `int`/`float`，字符串一律视为非数值（对接账本落盘等类型契约敏感场景） |
| `finite_or(value, fallback=0.0)` | `value or fallback` 的 NaN 安全替代，始终返回 `float`，便于直接参与算术 |
| `is_finite_number(value)` | 判定谓词（等同 `strict_num(value) is not None`，但读起来不会误写成 `if not value`——`0` 是合法数值却为假） |

**② 收敛既有私有实现**（约 10 处，全部改为委托原语）：

| 模块 | 归一函数 | 兜底语义（保持不变） |
|:-----|:---------|:---------------------|
| `providers/utils.py` | `safe_float` | 失败 → `0.0`（命中面最广：基金净值/排名链路） |
| `providers/tencent.py` | `_parse_float` / `_parse_float_field` | 失败 → `0.0`（保留负数钳零的既有口径） |
| `providers/sina_kline.py` | `_parse_sina_kline_float` | 失败 → `0.0` |
| `providers/akshare_extras.py` | `_safe_float` | 失败 → `None` |
| `providers/eastmoney_industry.py` | `_extract_number` | 失败 → `None`（并拒绝 `bool`） |
| `core/reader.py` | `_safe_float` | 追加**有限性检查**——脏行不再当合法值进入持仓读取 |
| `core/signal_ledger.py` | `_safe_number` | 委托 `strict_num`，账本数值不外泄非有限值 |

**③ 消除 `or 0.0` 空防线**：`report/` / `analysis/` / `core/` 下 28 处真 bug 站点改用 `finite_or(...)`（`market_value`（领域计算）/ `holdings_detail_sheet` / `category`（分类领域）/ `chart_data_builder` / `decision_record` / `decision_llm_capture` / `html_writer_display` / `portfolio_evolution` / `snapshot_diff` / `whatif` / `data_freshness` 等），NaN 不再渗透进市值、盈亏、涨幅与档位判定。

**明确不做**：**不统一各层的 dirty 默认值语义**（`0.0` vs `None` 是各调用方既有的契约，强行统一会改变合法输入路径的行为）。本次只保证「非有限值一定被拦下」，默认值口径维持原状。

回归锁定：`core/test_num_utils.py` + `test_num_utils_edge.py`（原语契约）、`providers/test_numeric_guard_regression.py`（provider 层双向不变量）、`report/test_numeric_guard_regression.py` + `_edge.py`（报告层「单个 NaN 不污染整列合计与档位判定」）。

#### 4.17.2 A2 失败原因可读（无开关）

**缺陷**：provider 链路失败此前只把 `failure_type` 短标识（`transport` / `empty` / `invalid`）写进降级事件，用户在「数据源可用性矩阵」里看到的是 `tencent: transport`——既不知道是哪个源的展示名，也不知道具体为什么失败。

**修复**：新增 `fetcher/chain.FailureDiagnostics`（采集「展示名(原因)」条目，`summary()` 渲染为 `腾讯财经(连接超时)；新浪财经(返回空)`，单条原因按 `_REASON_MAX_LEN` 截断），由 `fetcher/{price,fund,industry,index}.py` 在调用链路时构造并随 `DegradationEvent.detail.message` 透传；`report/data_source_matrix._failure_entry()` 渲染时**优先取该人类可读原因**，无原因时回落原 `failure_type` 短标识。

**向后兼容**：`DegradationTracker.record()` / `_record_unsafe()` 新增 `message` 参数默认 `None` → `detail` 保持 `None` → 矩阵输出与改动前**逐字相同**，由显式测试锁定。复用既有 `detail` 字典而非新增字段，与聚合路径（`record_aggregated()` 亦把 `message` 放在 `detail` 内）形状一致，`get_log()` 无需改动。

**展示名一致性**：熔断跳过与未注册两条分支原先写原始 provider id，与其它分支的展示名不一致；现统一把 `entry = provider_fn_map.get(provider_name)` 提到熔断检查之前，取 `label = entry[0] if entry else provider_name`，使同一条降级事件不因失败类型不同而时好时坏地不可读。

#### 4.17.3 B1 系统自检（恒上屏，无开关）

`core/doctor.py` 一次性盘点运行环境，输出分组结果（`环境` / `配置` / `目录` / `日志与缓存` / `功能开关` / `数据源适配` / `数据源凭据` / `数据源` 八组，分组顺序由 `GROUP_ORDER` 锁定），**失败项附可执行修复建议**（`hint`）。

**两条不可让步的设计约束**：

1. **自检自身永不抛异常**——任何检查项的异常都转成该组的失败结果行。配置损坏正是它最需要诊断的场景，此处抛 traceback 等于在最需要用它的时刻失效。
2. **零重依赖**——不 import `reader.py`（pandas）；持仓文件检查用 `os.listdir`。pandas 缺失/损坏本身就是它要报告的一类失败。

| 检查项 | 判据 | 失败提示 |
|:-------|:-----|:---------|
| Python 版本 | `>= MIN_PYTHON (3, 10)` | 升级解释器 |
| 虚拟环境 | `sys.prefix != sys.base_prefix` | 改用 `.venv/bin/python` |
| 项目根 / 配置加载 | 惰性 `init_config()` / `get_config()` | 定位损坏的配置文件 |
| LLM 凭据 | `get_llm_config()`（兼容多链 `_provider_list` 与扁平 `provider`/`api_key`） | 配置 llm_key.json / llm_providers.json |
| 目录可写性 | 写探测哨兵文件后**立即删除**（不留残留） | 权限/路径修正 |
| 持仓 / 输出 / 缓存 / 日志目录 | 存在性 + 可写性 | 建目录或改 `config.json` |
| 功能开关清单 | `is_feature_enabled` 逐项（信息性，不改结论） | — |
| 数据源连通性 | 复用 `core/check_sources.run_health_checks`（可按 `include_network=False` 跳过） | 网络/代理排查 |

**三面上屏**（默认全部可见）：

| 面 | 入口 | 是否受开关约束 |
|:---|:-----|:---------------|
| CLI | `doctor` 子命令（`--offline` 跳过联网、`--timeout` 预算秒数） | **否**（见下） |
| TUI | 菜单 `D` → `T` 系统自检（`MENU_ITEMS` 常驻，无门控） | 否（恒上屏） |
| Web | 运行状态区「系统自检」卡片 + `GET /api/doctor`（`network=0` / `timeout`，上限 15s） | 否（`system_info["doctor_enabled"]` 恒为 True） |

**无开关**：本项是只读诊断，不改产物、不写文件，联网检查每次由调用方显式确认；三面恒可用，省去「诊断入口被开关关掉」的失效路径。

**`doctor` 子命令与 TUI/Web 同源**（有意为之）：它与 `view-logs` 同样在 `init_config` **之前**分派——配置损坏正是它要诊断的场景，若因开关未开而拒绝执行，用户就陷入「开开关要先读配置、读配置失败又要开开关」的死锁。开关只约束 TUI `[T]` 与 Web 卡片这两个「日常会看见」的入口。

**退出码语义**：`_EXIT_SUCCESS`=全部通过、`_EXIT_PARTIAL`=命令跑完但有失败项（**不是** `_EXIT_SEVERE`——命令本身没失败，只是结论不佳），供 CI/脚本判定环境是否可用——脚本据以区分「命令本身失败」与「命令跑完但检查未通过」。

**架构约束遵从**：

| 约束 | 适配方式 |
|:-----|:---------|
| 分层 / 无环依赖 | `core/doctor.py` 只依赖 `core/` + 惰性函数内 import `config`（与 `market_hours` / `decision_header` / `signal_ledger` 同款），不触及 `report/` / `analysis/` |
| 不重复实现（DRY） | 约 10 个分散的私有解析器收敛到本项新建的 `core/num_utils.py` 单一实现；网络检查复用既有 `check_sources.run_health_checks`，不另写探测 |
| 无静默默认值 | 每个检查项都带 `message`；失败项额外带 `hint`；开关清单逐项回显 |
| 向后兼容 | A1 合法输入行为不变、A2 `message=None` 时矩阵输出逐字不变，均有显式测试 |
| 无开关门控 | TUI `[T]` 与 Web 自检卡恒上屏，注册表中不含自检开关；诊断入口不会因配置错误而消失 |
| 产物自述不含 | 不进 `enabled_experimental_features()`——它不改变报告任何字节，列进报告自述会误导读者 |
| 三面同源 | CLI `doctor` / TUI `[T]` / Web 卡与 `GET /api/doctor` 共用 `core/doctor.py` 一套检查 |
| 只读诊断 | 写探测哨兵文件后立即删除；自检不改任何配置或缓存 |

[↑ 回到顶部](#目录)

---

### 4.18 决策跨期反思闭环

LLM 的操作建议与确定性调仓信号此前「当次即评、事后无对账」——看多看空的判断无法用真实后续行情验证，判断质量既不沉淀也无从回灌后续分析。本项把决策登记为追加型账本 `data/state/decision_ledger.jsonl`，到期用真实行情结算命中率，再把教训回灌专家复盘提示词，形成「登记 → 结算 → 回灌」闭环（实验开关 `decision_reflection`，默认关）。

**分层（`core/` 零 report/llm 依赖，两个消费方向都无环）**：

```
core/jsonl_store.py             # 原子追加 + 容错读取 + 按龄裁剪原语（零项目内依赖）
    ↑
core/decision_ledger.py         # 决策账本：追加/折叠/结算原语 + 教训区块；is_active() 单源开关
    ↑
report/decision_record.py       # 确定性载体登记（再平衡/调仓卖出建议，仅带基线价入账）
report/decision_llm_capture.py  # LLM 操作建议表结构化解析 → 逐代码方向登记
report/decision_settlement.py   # 到期 pending 结算（真实行情对账：方向命中 + 超额 alpha）
report/decision_review_block.py # 行动章「历史决策复盘」区块装配（HTML + Excel 两端）
    ↑
llm/skeleton.py                 # 教训区块注入专家复盘提示词（开关门控）
```

**账本口径**：结算作为**独立追加事件**写入（决策事件恒为 `pending`），读取时 `fold_ledger` 按 `decision_id` 折叠出当前态——账本层只提供追加原语、无原地改写路径，避免已落盘事件被覆盖。**「入账必可结算」**：只有带基线价的决策才登记，无基线价者不入账，避免产生永远无法结算的悬空 pending；同日重复登记按 `decision_id` 去重。

**命中率与样本守门**：方向命中与超额 alpha 由真实后续行情对账得出；**命中率在小样本下不出结论**（样本数不足时只列明细、不报百分比），防「1 次命中 = 100%」的假精确。

**缓存指纹同源**：开关影响专家复盘提示词，故教训区块经 `lessons_cache_suffix()`（内容 md5 前若干位）进入 `llm/module_fingerprint.py`（生成参数经 `generation_params_suffix()` 并入指纹；`cache` 等无关项不参与） 中写侧与预检侧**共用的同一个**构建函数，开关与内容判定收敛在函数内部（无教训时返回空后缀）。

**报告挂载点**：结算与确定性登记经 `report/_experimental_seams.py::record_deterministic_decisions` 置于 LLM 拉取**之前**（当次教训含本批结算结果，须在 LLM 注入前落档，否则提示词读不到新结算）；LLM 登记与复盘装配经 `record_llm_decisions_and_review_block` 置于 LLM 回退**之后**。两处异常守护由挂载点统一提供，实验特性故障绝不打断报告主链路。

### 4.19 持仓基本面（财务指标 + 持仓个股财报摘要，一章两区块）

**定位**：合并章「持仓基本面」（sheet key `fundamental_snapshot`，type `fundamental_snapshot`），一章两区块：**区块① 财务指标** + **区块② 持仓个股财报摘要**，两块由**同一功能开关 `stock_fundamentals`**（个股基本面，默认关）同开同关。单块渲染由各自数据契约判定（契约 dict 为 None 表示该块无数据 → 该块整体不渲染），章节整体可见性按注册表 `data_flag_any` 的 OR 口径（任一块就绪即显示；Excel 侧 `excel_generator` 同步登记两条契约 flag）。对持仓 + 穿透中的 **A 股个股**标的（场外基金排除，见 §4.19 取数链路），取目标章节的**原文摘要**，与「拿行情/拿持仓」互补：前者提供公司经营层叙事与财务口径原文。两区块均含「标的来源」列（直接持有 / 穿透：来源基金），穿透标的名称由穿透层回填中文名。

**数据源与鉴权**：DataSinking（`https://api.datasink.ing`）提供全文本财报 Markdown，仅覆盖 A 股（SSE/SZSE/BSE，代码经 `core/code_symbols.py::to_fmp_symbol` 映射为 FMP 风格）。**需用户自备 API key**：凭据取通用密钥文件 `data/config/data_key.json` 的 `datasink` 节（`{"datasink": {"api_key": "..."}}`），环境变量 `DATASINK_API_KEY` 可覆盖；缺 key 时链路主动跳过并给申请指引，章节写占位。

**标的级正文缺失负缓存**：章节阶 + 备源两阶都试过仍无正文（`REASON_SECTIONS_MISSING`）时，按标的写 6h 负缓存（`report_symbol_miss_{symbol}`），同一天的后续报告直接复用同一原因文案、不再读索引与走候选；**索引为空/网络失败不入负缓存**（可能是瞬时不可用，缓存会无谓延长恢复期）。

**探测负缓存**：带 `section` 的章节探测与 `/sections` 清单探测遇 404 时，把「该（文档, 章节）缺失」写入 12h 负缓存（`datasink_probe_miss_` 前缀，键 = path + section 的 md5）；同一天的后续报告直接走降级路径，不再逐章节重发请求（实测 7 只标的 × 多候选章节的 404 占十余秒）。文档级 404（`/documents/{id}`、`/documents` 列表）属真缺失，仍按 WARNING 处置且**不进**负缓存。

**取数链路**：`fetcher/financial_report.py` 逐标的取元数据（`/documents`，**不带文种过滤**取最近若干篇后本地按「报告期 → 披露时间」倒序取最新一篇，故半年报/季报优先于年报；`doc_types` 非空时作白名单；**主源索引为空时切巨潮备源**，同一元数据形状）→ 取该文档**实际章节名清单**（`/documents/{id}/sections`，缓存于 `report_datasink_sections_`；备源无章节清单，直接落偏好名直取）→ 按 `sections` 偏好子串匹配出**精确章节名**逐个取正文（每节独立缓存、命中者按声明顺序以空行拼接；首选项 404 时继续试下一候选；清单不可得**或非空但残缺**时回退偏好名直取；**清单命中缓存但该批章节全部取不到正文时失效该文档的清单缓存**——清单是 14 天缓存，源侧若重新解析过文档，旧章节名会持续 404 且永不恢复，失效一次的代价只是下次多一次 `/sections` 探测）→ 仍无正文则**按报告期回溯上一份报告**（`_REPORT_CANDIDATE_LIMIT=3`，**年报/半年报优先于季报**：`_order_report_candidates` 稳定分组，季报无「管理层讨论与分析」只作最后兜底；标题含「公告」的信息披露条目跳过；命中即止，报告期/文种如实写入）→ **全文阶**：章节阶全失败时整篇下载后按偏好关键词定位片段（`_locate_from_fulltext`，跳过目录点线行/行内省略号，最多 `_FULLTEXT_FALLBACK_LIMIT=2` 篇，记录标 `section_source=fulltext`）→ 按 `datasink.max_chars` 截断为摘要。单篇正文经 `fetch_with_fallback` + 财报域适配器两槽（主：DataSinking；备：巨潮资讯网），复用缓存/熔断/降级；两源以 `source_hint` 做命名空间隔离（异源 doc_id 互不服务，备源候选进独立缓存键段），主源可用时备源零调用。关键词定位（目录行跳过）收敛于 `fetcher/report_locate.py`（全文兜底与备源切片共用同一规则）。**标的清单**由 `collect_a_share_targets(holdings, penetrated)` 生成：持仓场外基金经 `is_otc_fund_by_name` 剔除（`00` 重叠区），穿透标的带 `name`/`sources`（来源基金）用于展示层回填与来源标注；失败原因由 `fetch_symbol_report_detailed` 返回（索引无报告 / 目标章节缺失 + 已试报告期）。

**限速与配额护栏**：每次 HTTP 请求前经 `RateLimiter`（`core/throttle.py`）以「间隔 = 1/每秒上限」限速（免费档 3 请求/秒；付费档 31）；日配额计数存 `data/state/datasink_quota.json`，超限即停并告警。**免费档无批量端点、必然逐篇请求**，故限速必须落在 provider 每次请求前（批量调度器层挡不住单条调用）。并发取数由 `batch.datasink_workers` 控制（**默认 2**，免费档批量上限 ≤3），速率仍由 provider 兜底。

**降级与合规**：**传输级**失败（网络不可达/连接超时）经连接级重试（线性 1s/2s，共 3 次）后**上抛**，由链路计入同源重试与熔断；**代码级**结果（401/403/429 重试后仍非 200/非 JSON）返回空、不计传输级熔断。单标的失败进失败清单；`available=False` 时写占位。返回对象含披露平台归属字段 `source`，报告逐行标注（再分发时保留）。

**缓存**：索引/章节清单 1 天、正文 30 天（`report` / `report_doc`）——索引是 symbol 级键，日频才能让**新披露最迟次日可见**；正文按 `doc_id` 不可变，月度复用不重复消耗配额。随菜单缓存命令与 TTL 管理。**数据契约** `financial_report_digest_data`（附录 H）；语义命名行见 §6.7。

**数据源说明表**：「数据源可用性矩阵」章在健康度表后附「数据源说明（实际使用清单）」表——逐数据类别列实际链路、用途、计费（财报全文随 `datasink.plan` 动态展示免费/付费档）与凭据要求（是否需 key + 就绪状态），并标本次运行是否实际使用（`report/data_source_matrix.py::build_data_source_catalog`，前缀取自 `_SOURCE_CATEGORIES`、计费取自 provider 套餐表，单一事实来源）。**「本次使用」判定口径**：该类别的取数链路在**取得数据时**（含命中缓存的返回）经 `report/data_status.py::mark_data_used()` 记一条成功事件，说明表据事件前缀判定 `used`；**只记成功、不记降级**——章节名 fuzzy 未命中、标的不在源覆盖范围等预期内空结果不计入 T2 连续失败阈值（否则会把预期内空结果误报为源故障），失败与降级仍由 provider 日志、章节失败清单与链路 FailureDiagnostics 披露。因此 `未使用` 的含义是「本次未取到该类数据」，**不等于**源故障；对 DataSinking 类源另注明「需开启哪些功能开关才会取用」。类别清单含 `financial_report`（`report_datasink_`）与 `financial_indicator`（`fin_indicator_`），两者同时进入可用性矩阵与说明表；含同花顺兜底槽位的类别（`price` / `fund_hold` / `history` / `financial_indicator`）在「实际数据源（链路）」列显式列出「→ 同花顺金融数据（…，需 key）」，市场情绪（`sentiment`，同花顺**唯一源**）单列一行并附 key 就绪态。

**矩阵「命中源」列（provider 级归属）**：矩阵行除了类别健康度，还叠加一层 provider 级归属，回答使用者最常问的「我配的 key 到底被用上了吗」——类别健康度事件（`price_price_stock_600900` 这类键）只含代码不含 provider，**同花顺作为兜底槽接管时旧口径在报告里一字未提**，导致使用者误以为 key 未生效。修复：链路在某个 provider 成功返回时经 `report/data_status.py::mark_provider_used(data_type, provider_id, 展示名)` 登记（`fetcher/chain.py` 的 `fetch_with_fallback` 与 `_try_providers` 两处成功分支 + 同花顺独占的 `report/market_sentiment.py`、`fetcher/financial_indicator.py` 多期序列支路），矩阵按 `_SOURCE_CATEGORIES` 各行的 `data_types` 声明映射归入对应行并渲染为 `名称 ×次数`（按次数降序；无归属显示 `—`）。登记表存放于 `data_status.py` 模块级字典而非 DegradationTracker——归属是纯观测事实，既不参与降级计数，也不在 `.degradation_state.json` 里堆积 provider 键；归属只反映**本次网络取数**，命中缓存时该列为 `—` 而说明表「本次使用」仍为已使用（两列并读即得「用了谁的数」与「有没有取到」）。历史日 K 等类别只登记缓存键、不记降级事件，其矩阵行由 provider 归属单独成立（详情写「取数 N 次（无降级事件）」）。链路的 data_type 必须全部有归属类别，否则命中源静默丢失——`UNMAPPED_CHAIN_DATA_TYPES` 登记有意不进矩阵者（如 `bond_yield`），由 `test_data_source_matrix.py` 的不变式用例强制。附带修复：矩阵类别补齐 `history`（历史走势）与 `sentiment`（市场情绪），与 `datasource.md` 已登记的类别口径一致。

[↑ 回到顶部](#目录)

---

### 4.20 景气度框架诊断（常规功能 `prosperity_framework`）

**定位**：把开源项目 **zhengxi-views**（郑希观点库，MIT；<https://github.com/lyra81604/zhengxi-views>）从公开采访蒸馏的「景气度投资」方法骨架——全球视野找技术/需求变化 → 顺产业链找「正在涨价（通胀）」的环节 → 落到中国有比较优势的环节 → 选「流动性够 + ROE 低位有修复弹性」的标的 → 多维跟踪、周期拼接 → 组合分散 + 行业比例调整 + 想好退出——转成对本仓**持仓组合**的可计算诊断。**只借鉴其可计算骨架与评分口径**（其语料库、基金快照、全市场检索均不引入），设计文档随该功能一并归档（索引见 `docs/managements/folders.md` 目录树）。

**六维评分卡（满分 100）**：

| 维度 | 权重 | 计算口径（全部取自既有能力） | 数据缺失时 |
|:--|:--:|:--|:--|
| ① 景气方向 / 通胀属性 | 25 | **两视角叠加 + 归一 + 类型兜底**（`_sector_weight_items`）：视角一 = 穿透底层（按 `ratio_pct`）；视角二 = 每个直接持仓按自身权重（`classify_sector` 板块；识别失败用 `_fund_type_fallback_label` 类型标签兜底：固收→防御侧、境外/宽基/主动权益→中性且只按标签参与判定）；直接持有的证券视角二跳过；命中 `boom_keywords` 按 60% 满分档折算、`defensive_keywords` 反向扣减（防御优先互斥）；证据披露叠加合计与兜底只数 | 不依赖外部数据 |
| ② ROE 低位弹性 | 20 | `financial_indicator_data` 的 ROE 分布：低 ROE（<10%）权重按 50% 满分档折算，年度趋势改善加分；**基金层扩展（阶段一）**：无直接 ROE 的权益类基金按 `fund_roe_estimates`（前十大重仓股 ROE 加权推演值，`report/fund_roe_estimate.py`）补入计分，证据与持仓视角均标注「按框架推演」（框架原意是选股层 ROE 弹性，基金层为推演口径） | `unverified`（提示开启 `financial_indicator`） |
| ③ 全球视野 / 中国比较优势 | 15 | 命中 `global_edge_keywords` 的权重（口径同维度①并集归一，40% 满分档）+ 非 A 股/港股等境外资产占比加分（上限 5 分） | 不依赖外部数据 |
| ④ 流动性 | 10 | `analysis/liquidity.py::check_liquidity` 的最差变现/赎回天数分档（<1 日 10 / <3 日 7 / <5 日 4 / 否则 2）；计入池 = 场内（近 20 日成交额推算）+ 场外配置赎回上限（用户口径）+ 场外类型默认档（`core/code_utils.otc_redemption_days_default`：货币/短债 T+1、纯债 T+2、其他场外 T+3、QDII T+7；非实测，证据标注） | 全无可计算项或数据缺失 → `unverified` |
| ⑤ 集中度与周期拼接 | 15 | 前十大集中度（`concentration_target_pct` 目标档）+ 换手代理（最近两期历史快照持仓集合变动率 1−Jaccard；高换手为加分项） | 无第二期快照 → 换手子项 `unverified`（`partial`） |
| ⑥ 业绩与回撤印证 | 15 | `history_data` 区间收益与最大回撤（正收益 8 分 / 跑赢最强基准 +4 / 回撤 ≤15% +3、≤25% +1）；`benchmarks` 兼容 `list[dict]`（生产）与 `dict[str, dict]`（注入），无法解析的基准跳过不计 | `status=unavailable` / 无收益字段 → `unverified`；仅回撤样本不足 → `partial` |

**总分与评级口径**：只累计 `status != unverified` 的维度（`scored_weight`），`total_score_pct = total_score / scored_weight`；评级四档 ≥80 高度契合 / 60–79 较契合 / 40–59 部分契合 / <40 不契合。**红线**：缺数据维度**不计分、不臆造**（进 `unverified` 清单），渲染固定带免责句（衡量「组合与框架的契合度」，非组合优劣、非投资建议）。

**数据流（市场情绪与持仓热点）**：`providers/hithink.py`（官方龙虎榜 + 连板梯队）→ `analysis/market_sentiment.py::build_market_sentiment`（纯装配：只保留命中持仓/穿透标的**代码**的事件行，金额换算亿元）→ `report/_report_aux_metrics.py::compute_market_sentiment_data`（开关门禁 + 异常兜底；取数缓存 1h）→ `pipeline_data["market_sentiment_data"]`（both/full 由 `_report_generation` 注入；basic 由 `excel_generator` 就地兜底）→ 行动建议章内嵌块（HTML `partials/action_section.html` ⑦ / Excel `report/action_sheet.py::_write_market_sentiment_block`）。

**数据流**：权益类基金重仓 ROE 推演由 `report/fund_roe_estimate.py::estimate_fund_roe_batch`（复用 `fetch_fund_holdings_batch` 基金持仓链路 + `fetch_latest_indicator` 个股财务指标链路，报告期陈旧闸门与穿透层同口径）在编排层计算 →（**首次运行**涉及重仓股名单的一次财务指标取数：未命中缓存时按 `batch.akshare_workers` 并发、受东方财富限速档约束，命中后按财务指标日频缓存复用；取数失败只缺席该基金，不阻断诊断）→ `analysis/prosperity_framework.py::build_prosperity_framework_data`（装配入口；打分内核在 `analysis/prosperity_scoring.py`，市价读取经 `finite_or` 归一）→ `report/_report_aux_metrics.py::compute_prosperity_framework_data`（组装：穿透优先取 `prep.penetrated_assets`、缺失按需计算；流动性/快照取数失败降级为该维未验证；开关关闭返回 None）→ `pipeline_data["prosperity_framework_data"]`（both/full 由 `_report_generation` 注入；basic 由 `excel_generator` 就地兜底）→ 行动建议章内嵌块（HTML `partials/action_section.html` ⑥ / Excel `report/action_sheet.py::_write_prosperity_block`）。

**配置**：顶层键 `prosperity_framework`（`boom_keywords` / `global_edge_keywords` / `defensive_keywords` / `concentration_target_pct`，手动编辑）。

**开关**：市场与估值组 `prosperity_framework`（默认开、`affects_report=True`；实验转正：降级矩阵/真实样本/口径认可判据达成，评分口径不变）；关闭时报告与未引入时逐字节一致。

### 4.21 正文大块默认折叠（HTML 报告）

**定位**：长内容章节的正文整体包进原生 `<details class="section-fold">`，章标题与「回到顶部」留在折叠块外常显；`summary.section-fold-summary` 提示条携带该章关键摘要并自带「点击展开/收起」指引（原生键盘可达，无 JS 也能收放）。折叠覆盖章节（结构回归 `test_html_report_structure.py` 的 `_FOLD_KEYS` 为单源，后续新增折叠章只需改清单即逐章生效；历史章由 `TestSectionFold` 单测覆盖）：

| 章节 | sheet key | 提示条关键摘要 |
|:--|:--|:--|
| 组合历史走势与回撤 | `portfolio_history_drawdown` | 累计收益/最大回撤/年化波动 |
| 财经新闻热点与持仓关联分析 | `news_correlation` | 关联新闻条数 |
| 组合演进 | `portfolio_evolution` | 快照数与观察日数 |
| 持仓基本面 | `fundamental_snapshot` | 财务指标/财报摘标的数 |
| 持仓结构与集中度 | `position_structure` | 基金数与组合对数 |
| 风格与因子分析 | `style_factor` | 基金风格数 |
| 数据源可用性矩阵 | `data_source_status` | 数据源数 |
| 持仓变动复盘 | `holding_change` | `title_summary`（事件清单与结构演变） |
| 调仓纪律回放 | `schedule_replay` | `title_summary`（回放对照） |
| 行动建议 | `action` | 行动摘要（调仓信号与建议清单；降级占位分支不折叠） |

- **缺省一律收起**：模板不写 `open` 属性（收起是原生行为、不依赖 JS）；`fold.js` 初始 load 不执行锚点展开——打开报告（地址带 `#sec-…` / 浏览器恢复会话）全部收起，仅会话内 `hashchange`（点击目录原生锚点链接）自动展开目标章折叠块保证跳转后可见；回归用例 `test_fold_js_keeps_collapsed_on_initial_load` 锁死初始不展开。
- **打印**：`beforeprint` 以捕获阶段注册（先于 chart-print.js 快照）全展开 + 同步 resize 内部 Chart.js 图表（收起态 canvas 为 0 尺寸），`afterprint` 恢复用户原折叠状态；`@media print` 隐藏 `summary` 提示条并去边框/背景，打印稿不显示提示条。
- **手动展开**：`details` 的 `toggle` 事件逐块绑定，展开时对内部 canvas `resize()`（ResizeObserver 兜底）。
- **载体**：`details.section-fold` 共 11 处，全部位于章节 partial（模板拆分后主模板仅剩 CSS 注释与 fold.js 装配）：10 个章节各 1 处（`portfolio_history_drawdown_section` / `news_correlation_section` / `holding_change_section` / `schedule_replay_section` / `position_structure_section` / `style_factor_section` / `data_source_status_section` / `evolution_section` / `fundamental_snapshot_section` / `action_section`）+ 章内块级 1 处（`event_impact_section` 事件窗对照块）；结构回归 `TestSectionFold`（历史章）+ `TestSectionFoldMoreChapters`（`_FOLD_KEYS` 八个章节逐章遍历五类断言：包裹收起/summary 首元素/标题回顶在外/关键摘要/初始收起）+ `test_action_html.py::TestActionSectionFold`（行动建议章折叠，含降级占位不折叠与回顶在外）。需求 `R-OUT-12`。

### 4.22 章节-区块矩阵

**用途**：在章级一致性（名称/顺序/集合）之上固化**区块级**双端契约。真值在 `src/python/core/section_block_registry.py` 的 `SECTION_BLOCK_SPECS`（每章 `html`/`excel` 归一化区块名清单 + `partials`/`modules` 提取载体），本矩阵是它的派生视图；`check-doc-drift` 第 17 项三向对账——文档行 ↔ 注册表逐列相等、注册表键集 ↔ 章节注册表双向、双端实现提取 ↔ 注册表集合相等，任一端增/删/改名区块在提交前暴露。两端标题共用归一化口径（去 HTML 标签与 span 副标题、去序号头 `一、`/`①`、去括号段与【】外框），契约名与展示文案解耦。

**提取口径**（与 `report/section_block_extraction.py` 模块说明同源，改口径须同步两处）：

- **HTML 端**——`class="block-title"` 元素（全部计为区块）+ 内联加粗 div 中**带序号头**者（不带序号的加粗行是块内小标签，不计）+ `<!-- ── 一、…` 框式结构注释兜底（其序号/标题已被可见区块占用时丢弃，可见优先）；归一化标题集合大小即矩阵「HTML 区块数」，无区块记「—」（流式章/单表章）。
- **Excel 端**——`write_block_title` 调用点（含 `_write_sub_block` 类参数直通包装的调用位参）的静态字面量/模块常量，归一化集合即清单真值；非区块小节标题（说明/配对明细/基准对照等）仍走 `write_title_row`，不入契约；清单多模块用 ` + ` 分隔、多区块用 ` / ` 分隔，「—」为该端无子块。
- **备注**记录条件（开关门控）区块与双端差异；矩阵首列序号无语义（仅行标），章节集合与顺序以注册表为准（缺行/多行由检查报出）。

| # | 章节（key） | HTML 区块数 | HTML 载体（`src/static/tmpl/partials/`） | Excel 区块清单 | Excel 载体（`src/python/report/`） | 备注 |
|---|---|---|---|---|---|---|
| 1 | `summary` | — | summary_section.html | 持仓概况 / 盈亏汇总 / 市场温度 / 市场指数 | summary.py | 流式章：HTML 端数字卡非区块；「本期要点」块随开关 `summary_highlights`（默认关，快照 diff 单源派生；无上期快照整块隐藏） |
| 2 | `holdings_detail` | 2 | holdings_detail_section.html | 市值核算明细 / 持仓分类汇总 | holdings_detail_sheet.py + _holdings_detail_blocks.py | 双端对等 |
| 3 | `penetration` | — | penetration_section.html | — | penetration_sheet.py | 单表章 |
| 4 | `fund_performance` | 2 | fund_performance_section.html | 候选基金比较 / 基金经理变更监控 | fund_performance.py | 候选比较为开关门控区块（两态标题去重后计 1） |
| 5 | `position_structure` | 3 | position_structure_section.html | 持仓重合度矩阵 / 持仓相关性矩阵 / 持仓集中度监控 | position_structure_sheet.py | 双端对等 |
| 6 | `style_factor` | 4 | style_factor_section.html | 基金风格表 / 风格因子回归 / 行业 Beta / 因子目录 | style_factor_sheet.py | 行业 Beta 子表与因子目录默认关（条件区块，归一化去重计 4） |
| 7 | `action` | 7 | action_section.html | 再平衡信号 / 交易纪律 / 调仓建议清单 / 收益归因 / 历史决策复盘 / 景气度框架诊断 / 市场情绪与持仓热点 | action_sheet.py | ⑤⑥⑦ 门控（决策复盘/景气度/市场情绪，默认关） |
| 8 | `news_correlation` | 2 | news_correlation_section.html + event_impact_section.html | 事件窗量化对照 / 事件窗对照表 | news_correlation.py + event_impact_panel.py | 量化对照为章内块级、对照表为其折叠子块（双端同构）；新闻主表为章主体 |
| 9 | `global_macro` | — | global_macro_section.html | — | llm_content.py | LLM 流式章；事实校验块为内容内嵌（无标题行，契约外） |
| 10 | `expert_review` | — | expert_review_section.html | — | llm_content.py | 同上 |
| 11 | `health_check` | — | health_check_section.html | — | llm_content.py | 同上 |
| 12 | `penetration_deep` | — | penetration_deep_section.html | — | llm_content.py | 同上 |
| 13 | `portfolio_history_drawdown` | 5 | portfolio_history_drawdown_section.html | 走势表 / 回撤矩阵 / 危机区间标注 / 月度收益日历 / 风险调整超额 | portfolio_history_drawdown_sheet.py | 双端对等（5 对 5；风险调整超额块随开关 `risk_adjusted_excess`，危机回放列随 `crisis_replay`） |
| 14 | `portfolio_evolution` | 5 | evolution_section.html | 自上次快照变化摘要 / 总市值与总盈亏趋势 / 持仓集中度趋势 / TOP 持仓占比变迁 / 账户配置流 | evolution_sheet.py | 双端对等（5 对 5；Excel 端标题已对齐 HTML 端） |
| 15 | `holding_change` | 4 | holding_change_section.html | 变动事件清单 / 频率与结构演变 / 意图对账 / 变动动因 LLM 归因 | holding_change_panel.py | LLM 归因块条件写入（HTML `\| safe` 原文直出 / Excel 纯文本块 + 标识行），双端四对四 |
| 16 | `schedule_replay` | 2 | schedule_replay_section.html | 纪律回放 vs 买入持有 / 规则 A 逐期调仓与成本 | schedule_replay_panel.py | 双端对等 |
| 17 | `data_source_status` | — | data_source_status_section.html | 源健康 / 数据源说明 / 品种覆盖 / 可信度 | data_quality_sheet.py | HTML 端表格直排无序号标记；Excel 端四子块 |
| 18 | `fundamental_snapshot` | 2 | fundamental_snapshot_section.html | 财务指标 / 持仓个股财报摘要 | fundamental_snapshot_sheet.py | 两区块各由功能开关门控 |
| 19 | `llm_usage` | — | llm_usage_section.html | — | excel_llm_usage.py | 单表章 |

### 4.23 测试域归属与门禁纳入纪律

**决策**：测试目录的 marker 归域以 `scripts/check-test-markers.py` 的 `EXPECTED_DIR_MARKERS` 期望表为单一事实来源，且**归域即进门禁**——期望表声明的每一个 `unit_*` 域必须出现在 P1（`--mode verify`）选择器中，`dev-verify`（P0）域集必须 ⊆ P1；快速门禁与合入门禁的差集只允许是「域内子集」维度（`and not (edge or data)`、`scenario_basic`），不允许是「域」维度。

**动机**：门禁档位按 marker 表达式筛选，「改域=门禁搬家」——归域调整若与选择器漂移，用例会静默脱离回归覆盖（审计中实际发现两例：`unit` 曾在 `pytest_configure` 漏注册致 `unit` 通配表达式匹配全空，unit_* 全集 10,136 条不进任何档位；TUI/CLI 域曾不在 `verify` 选择器）。另需防止「为进门禁而蹭域」的语义漂移反弹——归域特例必须显式登记。

**已登记归域特例**：`unit/handlers`（TUI 处理层）与 `unit/cache`（存储/IO 基础设施）取 `unit_core`（无专属域，归核心域搭车门禁，子集语义「至少命中其一」）；`unit/startup`（首次运行交互引导）取 `unit_ui`。conftest 缺标记警告文案同步指向期望表，新增/调整特例须同批更新期望表与本节。

**守护**：`test_check_test_markers.py::TestP1GateCoversDeclaredDomains` 双结构锁（期望表全部 unit_* 域 ∈ verify 选择器；P0 域集 ⊆ P1）——域集合从期望表/模式注册表动态派生，不写死域数（测试真值单一来源纪律）。场景侧同源机制：`scenario` 目录×裸 `scenario` marker 收集期双向硬拦截（见 conftest）。

[↑ 回到顶部](#目录)

## 5. LLM 集成层（概要设计）

### 5.1 架构总览

`src/python/llm/` 包按调用层次分为四层，共 46 个子模块（顶层 37 + fact_checker/ 子包 9，均不含 `__init__.py`；`prompts.py` 为统一导出入口，实际逻辑在 prompts_core/tables/action/signals/data_blocks/review 6 文件中）：

```
入口层         generators_orchestrator.py    4+1 模块并行编排 + 缓存预检 + 生成后一遍（事实锚定/自检）
                  │
编排层         skeleton.py                   标准/批量模式共享骨架
               _llm_dispatch.py              worker 装配/线程池分发/辩论路由（经门面 re-export，patch 点不变）
               _batch_mode.py                批量模式分块执行（10 条/批、≤3 批并行）
               self_review.py                生成后自检（串行后置，不经并行调度）
               holding_change_review.py      持仓变动复盘归因（串行后置，不经并行调度）
                  │
API 层         api.py        Provider 路由 + Multi-Provider Chain 遍历
               api_base.py   HTTP 调用 + 重试骨架
               strategy.py   多 Provider 切换策略引擎
               _api_claude.py / _api_gemini.py / _api_openai.py  各 Provider 单次调用实现
               pacing.py     端点级节流（PacingGate）
                  │
共享层         generators.py         辩论/自检生成门面（单例四函数下沉 generators_singletons.py 再导出）
               generators_news.py   新闻 LLM 批量关联分析
               _llm_news_correlation.py  新闻关联闭包/结果缓存/安全直调
               prompts.py           统一导出入口（逻辑在 prompts_core/tables/action/signals/data_blocks/review 6 文件）
               depth_profile.py     报告深度档位表（brief/standard/deep 唯一事实来源）
               force_scope.py       模块级强刷范围（可强刷键清单 + 粒度优先归一）
               fingerprint.py       缓存指纹计算（模块级见 module_fingerprint.py，C21 同源）
               session.py           会话用量追踪
               cost_tracker.py      Token 预算管理
               pricing.py           费用估算（含 DeepSeek 峰谷定价）
               compliance.py        System Prompt 尾部合规声明注入（call_llm 单一漏斗，幂等）
               failure_reasons.py   模块失败原因常量（LLM_MODULE_FAILURE）
               markdown.py          Markdown→HTML 转换
               circuit_breaker.py   LLM API 熔断器
               fact_checker/        LLM 输出伪代码/幻觉过滤（子包 9 模块，__init__ 重导出 4 公开函数）
               _hallucination_filter.py  虚构品种代码过滤（行内句段粒度删除）
               fallback.py          全失败降级占位模板
```

**LLM 模块配置化**：每个 LLM 模块（global_macro / expert_review / health_check / penetration_deep / news_correlation）在 `core/registry.py` 中通过 `settings_suffix` 注册，自动派生 `llm_settings.json` 的所有合法键名。

**辩论模式（报告章节与增强路由）**：当 Feature Flag `llm_debate_procon` 启用时，`_llm_dispatch.py` 中的 `_debate_wrapper` 闭包替换 `_MODULE_FNS["expert_review"]`；`llm_debate_conditional`（同组、默认开）仅叠加模式组合，不触发路由。辩论模式与标准模式互斥（辩论优先），路由后 `skeleton.generate_llm_module()` 走辩论三段缓存（`llm_debate_pro_` / `llm_debate_con_` / `llm_debate_synthesis_`）而非标准 expert_review 缓存。三段缓存由缓存专属登记 `_CACHE_ONLY_REGISTRY`（`core/data_registry.py`）承载——不在模块注册表内，故菜单/配置编辑/`llm_settings` 键域均不含其键；缓存侧访问器 `get_cache_registry()` 合并输出前缀/TTL/组归属（preload 组，24h TTL），缓存 key 与既有磁盘缓存不变。

各子模块的详细设计见 `llm-technical.md` §1~§4（架构总览、模块清单、骨架流程、并行编排）。

### 5.2 调用链概览

LLM 分析从编排入口到最终 HTML 输出，经过缓存检查 → API 调用 → 内容转换 → 缓存写入的完整链路：

```
generators_orchestrator（并行调度 4+1 模块）
    │
    └── skeleton.generate_llm_module()
            │ ① 缓存检查（指纹+TTL）→ 命中则直接返回
            │ ② 乐观预检链首 Provider 缓存键
            │ ③ API 调用（走 Provider Chain）
            ├── api.call_llm()
            │      ├── strategy.resolve_provider_chain() → 策略排序
            │      ├── api._call_provider_entry() × N（逐链尝试）
            │      │      └── _resolve_entry_credentials()（credentials_ref 解析）
            │      └── api_base._attempt_api_call()
            │              └── core.http_client.post_with_deadline()（墙钟截止：总时长=timeout，防滴流骗过 read 超时）
            │                      ├── Claude/DeepSeek(Claude 端点) → HTTP POST {endpoint}/v1/messages
            │                      └── OpenAI/DeepSeek(OpenAI 端点) → HTTP POST {endpoint}/v1/chat/completions
            │ ④ 空内容处理（仅服务端正常返回的无正文：thinking 耗尽/偶发空 content→关闭 thinking 同 provider 重试一次；服务侧故障——error 信封/传输失败/熔断——直接切换 provider）
            │ ⑤ Markdown→HTML（markdown.py）
            │ ⑥ 写入缓存（Provider 感知键名，记录实际 Provider 名）
            └── 返回 (result, usage, provider_name) 三元组
```

完整调用链含重试、熔断、截断重试、缓存写入的各分支流程，详见 `llm-technical.md` §3（骨架流程）和 §6（重试与容错）。

### 5.3 模块清单

LLM 集成层提供 5 个分析模块，通过 `llm_settings.json` 的 `enabled_llm` 逐模块独立开关：

| 模块 | 标识 | 功能概要 | 缓存分组 | 默认 TTL |
|:-----|:-----|:---------|:---------|:--------|
| 全球政经局势 | `global_macro` | A 股/美股指数+持仓汇总 → 宏观判断 | preload | 24h |
| 智囊团深度复盘 | `expert_review` | 持仓明细+穿透 → 专业分析师多视角辩论 | preload | 2h |
| 持仓体检报告 | `health_check` | 持仓明细（排除行情波动）→ 5 维健康度评分 | preload | 24h |
| 穿透深度分析 | `penetration_deep` | 穿透 TOP10 → 行业/品种/国家集中度分析 | preload | 24h |
| 新闻二次关联 | `news_correlation` | 逐条新闻 → LLM 深度关联评分（批量模式） | refresh | 4h |

每个模块的详细参数（model、temperature、timeout、max_tokens 等）通过 `{参数}_{标识}` 命名约定在 `llm_settings.json` 中配置。

**辩论模式路由**：当 Feature Flag 开启时，expert_review 模块的生成入口被 `_debate_wrapper` 接管，输出路径变为 debate 三段式。辩论模式使用独立的缓存键（`llm_debate_pro_`/`llm_debate_con_`/`llm_debate_synthesis_`）和 Token 预算守卫，三段缓存共用 expert_review 的持仓指纹（排除行情波动），默认 TTL 24h。辩论模式启用时，HTML 的模块状态标签与 Excel 用量页对 expert_review 显示模式标识：`llm_debate_procon` 启用 → "辩论模式"，仅条件推理启用 → "情景推理模式"。

各模块的详细配置参数、System Prompt 设计、User Prompt 构建逻辑见 `llm-technical.md` §8（提示词管理）。辩论模式相关生成器见 `llm-technical.md` §2.1（子模块总览）。

### 5.4 多 Provider 链模式

LLM API 调用支持多 Provider 链式容错，与数据获取层的 Provider Chain（§2.1）采用相同设计理念，但策略引擎独立：

- **配置分离**：Provider 路由配置在 `llm_providers.json`，敏感凭据通过 `credentials_ref` 引用 `llm_key.json` 中的凭据块
- **策略引擎**：`strategy.py` 支持 4 种链切换策略 — priority（优先级排序）、weighted（加权随机）、cost_first（成本优先）、fallback_only（仅递补）
- **逐链尝试**：`api.call_provider_entry()` 按策略排序后逐链调用，成功即返回，全链失败后降级为占位文本
- **Provider 感知缓存**：缓存键格式 `llm_{module}_{provider_name}_{fingerprint}`，不同 Provider 的缓存互不冲突
- **失败追踪**：`LLM_MODULE_FAILURE` 字典记录每个模块的 attempted Provider 列表及 final_status，供报告展示
- **端点级节流**：每个 provider 条目可声明 `pacing`（`min_interval` / `jitter` / `max_concurrency`）对该端点单独限速与限并发；缺省即无约束（零开销直通）。与全局 `llm_max_concurrency`（线程池）两级叠加，见 `llm-technical.md` §4.2.1
- **重试与退避委托统一原语**：重试循环、尝试次数（`max_retries` + 1）与退避数值全部来自 `core/retry.py`（策略为**显式退避序列** `[1s, 3s, 5s, 10s, 15s]`，超出末位锁定末位值）；`llm/api_base.py` 只保留失败分类、每次尝试前的端点节流门与终态副作用（断路器计数 / 失败原因码）
- **配额/风控拒绝不重试**：端点返回 403（如订阅制端点的 5 小时窗口、并发上限）时取 `quota` 分支直接降级到下一 provider，失败原因记 `FAIL_REASON_QUOTA_EXCEEDED`——这类限制按时间窗口滚动，重试无益且会加剧风控画像；503 仍按 `max_retries` 重试，429 归 `quota` 终态不重试（首试即长冷却熔断）

4 种策略的详细排序逻辑和 credentials_ref 解析流程见 `llm-technical.md` §5（API 调用层）。

### 5.5 关键机制

| 机制 | 实现 | 说明 |
|:-----|:------|:------|
| Extended Thinking | Claude: `thinking.budget_tokens`；DeepSeek: `output_config.effort` | 与 `temperature` 互斥 |
| Prompt Caching | Anthropic 专属，system prompt 数组 + `cache_control: ephemeral` | 5 分钟内复用免全价 |
| 截断重试 | 检测 `TRUNCATION_MARKER` 后自动 1.5× max_tokens 重试一次 | 修复内容被截断的情况 |
| 空内容处理 | `_extract_content` 无 text block（DeepSeek 思考耗尽/偶发空 content）→ 先关闭 thinking 同 provider 重试一次（安全网，仅服务端正常返回时触发；error 信封/传输失败/熔断等服务侧故障直接切换）；仍无正文再切换 provider；真正空字符串 `""` 追加安抚指令重试一次 | 应对思考预算耗尽 + 内容审查误杀，且不对已故障端点无效重试 |
| 墙钟总超时 | `core/http_client.post_with_deadline()` — POST 以独立 daemon 线程执行、主线程 join(timeout) 到点放弃并归一为 httpx.ReadTimeout | read 超时是块间间隔会被服务端滴流骗过（实测挂足 900s），墙钟兜底总时长，故障期快速切换 provider |
| 会话用量追踪 | `session.py` 维护线程安全 `session_usage` 字典 + `cost_tracker.py` 报告级预算管理 | 按模块粒度追踪 token/费用/缓存命中/耗时；报告写 perf 时按入口基线取 delta（`_run_scope`），会话累计不受影响 |
| Token 预算告警 | `cost_tracker.check_input_budget()` — 累计输入 Token 超 8K 时日志告警（不截断） | 为模型分层提供基线数据 |
| 调用耗时记录 | `skeleton.py` `time.monotonic()` 计时 → `record_per_module(duration=)` → HTML 页脚展示 | 每次 call_llm() 记录实际耗时 |
| LLM 熔断 | `llm/circuit_breaker.py` — 连续 N 次失败 → 60s 冷却 → 半开状态试探 | 防止无效调用浪费 token |
| 指纹缓存 | `fingerprint.py` — 依赖数据指纹过滤（排除行情波动字段） | 仅品种/份额/成本变化时重新调用 |
| 乐观缓存预检 | 从 Provider 链中取链首 Provider 优先检查缓存，命中即返回 | 减少链遍历开销 |
| 辩论路由 | `_debate_wrapper` 闭包替换 `_MODULE_FNS["expert_review"]`，Feature Flag 控制启停（默认关闭） | 辩论模式与标准模式互斥，辩论优先 |
| Token 预算守卫 | pro+con 累计输出字符数 > `int(max_total_tokens_per_report)`（1 字符 ≈ 1 token，默认预算 72000）时触发保护：1× 超限→跳过 synthesis 阶段并拼接 pro+con；2× 超限→回退标准模式。配合 `per_call_max_tokens`（默认 18432，经 `max_tokens_override` 生效）单段上限双闸保护 | 防止辩论模式过度消耗 token |
| 虚构代码过滤 | `_filter_hallucinated_codes()` 正则句段级过滤，经 `skeleton.py` 的 `raw_filter_fn` 钩子在 markdown_to_html 之前作用于 LLM 原始 Markdown；按"行→句末标点"两级切分精确删除，`TOP\d` 排名表述 + 英文白名单豁免误报 | 消除 LLM 产生的虚构证券代码，且不因 HTML 单行拼接误删整段 |

各项机制的详细实现见 `llm-technical.md` §5~§11（API 调用层、重试与容错、缓存与指纹失效、提示词管理、会话级 Token 追踪、模型定价、熔断器）。

[↑ 回到顶部](#目录)

---

## 6. 辅助模块详细设计

### 6.1 配置管理

#### 配置分层

```
config.json (基础配置)       → get_config() 内存缓存，按 mtime 自动失效
llm_settings.json (非敏感)    → get_llm_config() 三文件合并读取，判据 = 三文件 mtime+size；
                                 写原语写后主动失效 + TUI [R] 显式失效（手工改/互换免重启）
llm_key.json (敏感凭据)       → 覆盖 llm_settings.json 的同名字段；多凭据块供 credentials_ref 引用
llm_providers.json (链配置)   → _load_llm_providers() 读取，_inject_provider_chain_data 注入
                                 （同入 get_llm_config 合并缓存判据；页头状态行显示链首线路）
local_state.json (机器本地)   → get_flag()/set_flag() 读写
```

`config/` 子包结构：

```
config/
├── __init__.py                   # 公开 API 导出
├── _comments.py                  # 再导出 core/json_comments（配置包既有导入面）
├── _config_defaults.py           # config.json 默认值定义 + 模板生成
├── _core.py                      # 核心读写：get_config()、set_config()、del_config()、init_config()
├── _local_state.py               # 机器本地状态读写（get_flag/set_flag，data/state/local_state.json）
├── _json_patch.py                # JSON 字段级文本替换（_update_json_raw_text/_replace_dict_block；缩进单位经 _detect_indent_unit 沿用文件风格）
├── _validation.py                # 配置校验：validate_config()、_absolutize_paths()
├── _llm_settings.py              # llm_settings.json 读取/合并/缓存与 LLM 配置入口
├── _llm_settings_defaults.py     # llm_settings.json 默认模板生成
├── _llm_providers.py             # llm_providers.json 多链解析/凭据注入
└── _llm_providers_defaults.py    # llm_providers.json 默认模板生成
```

#### 机器本地状态

`data/state/local_state.json`（git 忽略）存放仅本机有意义的状态标志——首次运行引导（`_startup_wizard_shown`）、隐私提示已读（`_privacy_notice_shown`）。不混入 config.json，避免 config.json 跨机器同步时各机器写入个性化差异。`config/_local_state.py` 提供 `get_flag`/`set_flag`，直接读写 `data/state/local_state.json`，不做任何旧键迁移。

#### JSON 注释支持

`core/json_comments.py` 是叶子模块（仅标准库）：`strip_json_comments()` 逐字符扫描，支持 `//` 单行注释和 `/* */` 多行注释，正确处理字符串内的转义引号，不会将字符串内的 `//` / `/*` 误伤；`loads()` / `load()` 是统一读取入口。配置包与 core 级读取方统一从该叶子模块导入，因此不必导入 `config` 包（依赖不成环）。

#### 原子写入

配置文件（`set_config`）和缓存写入（`_write_atomic`）均使用 `tempfile.mkstemp` + `os.replace` 模式。

> **各配置文件的缺省/模板/解析/消费矩阵见 [附录 I：配置文件矩阵](#附录-i配置文件矩阵)**（含消费方与消费模式）。

### 6.2 中央注册表

**设计目标**：消除 `config/` / `cache/_ttl.py` / `core/constants.py` 三处分散维护的遗漏风险，做到"一处注册，全局生效"。

#### DataModuleDef 条目结构

```python
@dataclass(frozen=True)
class DataModuleDef:
    name: str                # 人类可读名称
    data_type: str           # 数据类型键，用于 TTL 查找和路由
    cache_prefixes: tuple    # 缓存前缀，如 ("price_",)
    exact_cache_keys: tuple  # 精确缓存键名
    cache_ttl: float         # 默认缓存过期时间（秒）
    settings_suffix: str|None# LLM settings 键后缀，None=非 LLM 模块
    cache_groups: tuple      # 分组
```

当前注册 **28 个数据模块**：

| 分类 | 数量 | 模块 |
|:-----|:----:|:-----|
| 基础行情（preload） | 2 | price、index |
| 基金数据（refresh） | 2 | rank、hold |
| 行业 | 1 | industry |
| 新闻（refresh） | 1 | news |
| LLM 分析（preload/refresh） | 5 | global_macro、expert_review、news_correlation、health_check、penetration_deep |
| 辩论缓存（preload，缓存专属登记） | 3 | llm_debate_pro、llm_debate_con、llm_debate_synthesis |
| 补充数据（refresh） | 3 | profit_forecast、sector_flow、dividend |
| 基金深度分析（refresh/无分组） | 4 | fund_manager、fund_concentration、fund_style_snapshot、**extended** |
| 无风险利率（refresh） | 1 | **bond_yield** |
| 精确键名（refresh/无分组） | 3 | benchmark、tracking、calendar |
| 历史走势（无分组） | 3 | history_stock、history_fund_otc、history_index |

> 注：`position_structure`（持仓结构与集中度）为报告章节（#6，运行时从 fund_hold 推导），**非**缓存数据模块，故不计入上表。

#### 计算模块注册表（`_COMPUTATION_REGISTRY`）

除数据模块注册外，系统维护独立的计算模块注册表 `_COMPUTATION_REGISTRY`，记录所有分析/指标计算模块的元信息。

```python
@dataclass(frozen=True)
class ComputModuleDef:
    name: str           # 中文名称
    module_key: str     # 键名（如 "analytics_metrics"）
    label: str          # 短标签
    dependencies: tuple # 前置数据依赖
    description: str    # 功能说明
    status: str         # planned / implemented
```

当前注册 7 个计算模块：

| module_key | name | 状态 | 说明 |
|:-----------|:-----|:----:|:-----|
| `analytics_metrics` | 量化指标计算 | ✅ | 夏普比率、卡玛比率、HHI 集中度、组合 Beta、持仓胜率、换手率、波动率、最大回撤 |
| `analytics_liquidity` | 流动性分析 | ✅ | 场内/场外比例、停牌风险、基金封闭期分析 |
| `analytics_fx_exposure` | 外汇敞口分析 | ✅ | A股/港股/美股 国别分布与外汇风险敞口判断 |
| `analytics_fact_checker` | 事实锚定校验器 | ✅ | LLM 输出的事实校验：数值一致性、品种存在性、排名正确性（纯算法层） |
| `analytics_scenario` | 情景分析 | ✅ | 市场涨跌情景模拟、3 情景表、置信区间传播 |
| `analytics_alignment` | 组合校准分析 | ✅ | 费率估算/现金剥离/TWR 计算 |
| `analytics_inferrer` | 用户画像推断 | ⏳ | 持仓结构→风险偏好推断 |

计算模块与报表层保持单向依赖，禁止反向导入 report/。

#### 派生产出接口

| 接口 | 用途 |
|:-----|:------|
| `get_cache_ttl_defaults()` | data_type → TTL 默认值 |
| `get_prefix_type_map()` | 缓存前缀 → data_type |
| `get_exact_type_map()` | 精确键名 → data_type |
| `get_known_llm_settings_keys()` | `llm_settings.json` 合法键名 |
| `get_report_section_order()` | 用户配置+默认顺序合并 |
| `get_llm_module_names()` | suffix → 中文名称 |

### 6.3 市场时段判断

**三层 fallback 架构**（`core/market_hours.py`）：

```
is_market_open()
    │
    ▼
┌─────────────────────────────────────────────┐
│ 第 1 层：config.json 手动覆盖                 │
│ market_hours.start / end                    │
│ 支持午间不中断模式（连续时段）                  │
├─────────────────────────────────────────────┤
│ 成功? → 返回 True/False                      │
│ 未配置? → 进入下一层                          │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 第 2 层：东方财富 push2 API 实时交易状态      │
│ 上证指数 secid=1.000001, f100 字段          │
│   0=未开盘 / 1=交易中 / 2=收盘 / 3=午间休市   │
│ 缓存策略：盘中 60s，盘后 7 天                 │
├─────────────────────────────────────────────┤
│ 成功? → 返回 True/False                      │
│ API 不可用? → 进入下一层                      │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 第 3 层：内置默认值                           │
│ 北京时区工作日 09:30-11:30 + 13:00-15:00     │
├─────────────────────────────────────────────┤
│ 固定返回 True/False                          │
└─────────────────────────────────────────────┘
```

**时区安全**：所有 `datetime.now()` 调用均使用 `timezone(timedelta(hours=8))` 北京时区，防止 UTC 服务器上时段判断全错。异常时保守返回 `False`。

**消费方**：
- `cache/_ttl.py:get_ttl()` — 交易时段内注册表声明 `market_ttl` 的类型（价/指）自动使用短 TTL（30s）
- `report/market_value.py:is_market_open()` — 取价方式标签判断
- `report/market_value.py:is_midday_break()` — 午间休市识别（11:30-13:00）

### 6.4 持仓读取与列校验

基于 openpyxl 解析持仓 xlsx（`core/reader.py`）：

```
load_holdings(filepath)
    │ 遍历所有 worksheet
    │ 每个 worksheet = 一个账户
    ▼
列校验规则：
    必须存在且恰好 4 列
    列名匹配忽略首尾空格
    列顺序：名称、代码、持仓份额、每份成本
    │
    ▼
数据清洗：
    代码自动去除后缀（.SH / .SZ / .OF）
    份额/成本转为 float
    空行跳过
    │
    ▼
返回：list[Holding]（每行一个 Holding）
```

### 6.5 代码类型判定中心化

所有资产代码类型判定集中到 `src/python/core/code_utils.py`，以纯技术原语形式提供。

#### 原语清单

| 维度 | 函数 | 判定依据 | 用途 |
|:-----|:------|:---------|:------|
| 代码前缀 | `is_a_share_code(code)` | 60/68/00/30/8 开头 | A 股股票识别 |
| | `is_exchange_fund_code(code)` | 5/1 开头 | 场内基金/ETF |
| | `is_hk_stock_code(code)` | 5 位纯数字 | 港股通标的 |
| | `is_otc_code_overlap(code)` | 00 开头 | A 股/OTC 基金代码重叠区检测 |
| | `get_exchange_prefix(code)` | 前缀规则 | sh/sz/bj 交易所前缀 |
| | `is_index_code(code)` | sh/sz 前缀或 000/399/932 开头或 gb_ 前缀 | 指数代码识别 |
| | `is_us_index_code(code)` | gb_ 前缀 | 美股指数识别 |
| | `get_index_exchange_prefix(code)` | sh/sz 前缀 | 指数所属交易所前缀 |
| | `get_push2_secid(code)` | 前缀规则 | push2 API secid 参数 |
| 名称关键词 | `is_qdii_by_name(name)` | "QDII" | QDII 标识 |
| | `is_qdii_extended(name)` | QDII + 隐式关键词 | QDII + 隐式海外基金 |
| | `is_etf_by_name(name)` | "ETF" | ETF 标识 |
| | `is_bond_related_by_name(name)` | 纯债/短债/利率债等（不含单字"债"） | 债券基金（严格） |
| | `is_bond_fund_by_name(name)` | 含"债" | 债券基金（宽松，含可转债） |
| | `is_money_fund_by_name(name)` | 货币/现金/增利/宝 | 货币基金 |
| | `is_index_fund_by_name(name)` | 指数/ETF 联接/中证/沪深 300 等 | 场外指数基金 |
| | `is_index_link_by_name(name)` | ETF 联接/联接/链接 | 指数联接基金 |
| 复合 | `is_etf_by_name_or_code(name, code)` | 名称+代码双维度 | ETF 增强识别 |
| | `is_a_share_stock(name, code)` | 名称+代码双维度（`is_a_share_code` 且非 00 重叠区场外基金） | 持仓路由「按 A 股个股处理」统一入口 |
| | `is_otc_fund_by_name(name, code)` | 00 代码+名称含基金关键词 | 00 代码重叠区→场外基金 |
| | `is_offsite_fund(account)` | 关键词匹配 | 场外基金账户 |
| | `is_fund_holding(name, code, account)` | 三者联合 | 持仓是否需要基金业绩分析 |

#### 内部工具

`strip_to_digits(code)`（派生量模块 `core/code_symbols.py`，旧名 _strip_prefix）— 去除 `sh/sz/bj` 前缀，返回纯净 6 位数字代码，非 6 位数字时返回空字符串。所有前缀型判定函数均先调用此函数再匹配。

#### 关键词常量

| 常量名 | 值 | 用途 |
|:-------|:----|:------|
| `FUND_ACCOUNT_KEYWORDS` | `("基金", "支付宝", "微信", "银行")` | 场外基金账户判定 |
| `MONEY_KEYWORDS` | `("货币", "现金", "增利", "宝")` | 货币基金识别 |
| `INDEX_KEYWORDS` | `("指数", "ETF联接", "中证", "沪深300", ...)` | 指数基金判定 |

### 6.6 HTTP 客户端统一

所有 HTTP 请求必须使用 `core/http_client.py` 工厂方法创建客户端实例（C5 约束），统一 SSL 配置、超时策略、连接池管理。

```python
make_http_client(timeout=10.0) → httpx.Client
```

默认超时 10s，支持 per-call 覆盖，所有 provider 模块统一使用此接口。

### 6.7 功能语义命名表

> **纪律**：英文 slug 即**代码/配置标识符**（函数名、变量名、功能开关名如 `stock_fundamentals`），中文名即**文档/UI 描述**。语义名即代码名——任务代号不进入实现层（禁止用任何任务编号/F 系列/`plan-N`/`rf-N` 命名），函数/变量/模块/注释/文档一律用语义名；任务编号仅作为内部计划表（`plan.md`/`review-findings.md`）链接锚点。新增功能**先定语义名再设计**。该纪律由双脚本强制——`scripts/check-code-traces.py --ci`（负面禁止 IDENT/CODE，退出码 2）+ `scripts/check-semantic-index.py --ci`（正面校验本表与代码正反向一致），并已纳入「架构设计约束」章节的约束外参照（见该章节开头）。注：小写短局部名（`h1/t1/f1`）与 Excel 单元格（`A1:B1`）等结构性记号属合法豁免。
>
> 以下为当前已实现功能/合并章的语义命名索引（活索引），以本表为唯一现状基准。

<!-- semantic-index:start -->
| 语义 slug | 中文名（文档/UI） | 归入章节 | 决策链环节 | config 开关 |
|:--|:--|:--|:--|:--|
| `report_qa` | 报告对话式追问（报告页内对本期报告的会话式问答；独立 `qa/` 子包 + 实验开关，三端同源、默认关） | 报告对话式追问 | 内容生成 | `features.json → report_qa` |
| `report_qa_context` | 追问上下文提取（报告 HTML → 分层截断文本 + 表头名映射持仓基线 + 生成条件声明；锚点单文件收敛、零取数） | 报告对话式追问 | 内容生成 | 无 |
| `report_qa_session` | 追问会话服务（内存会话表带上限淘汰 / 轮数与输入双上限 / 用量独立记账；`QaSession` + `create_report_qa_session`，编排入口 `ask_report_qa`） | 报告对话式追问 | 内容生成 | 无 |
| `report_qa_ask` | 追问问答路由（POST /api/qa/ask 校验矩阵与信封，`_handle_report_qa_ask`，开关关 403） | 报告对话式追问 | 报告输出 | 无 |
| `chain_overrides` | 调用级数据源覆盖上下文（本次运行指定首选/排除源；只排序与过滤，不绕过熔断与凭据就绪预检） | 数据源 | 数据获取 | 无 |
| `load_comparison_baseline` | 环比比对基线（跨交易日最新一份快照：同一交易日多次运行跳过，环比 diff 与快照差异摘要共用） | 投资分析汇总 | 监控 | 无 |
| `trading_day_as_of` | 时点交易日归属（盘前 <9:30 归前一交易日、节假日按日历回溯；`get_last_trading_day` 委托同口径） | 数据源 | 数据获取 | 无 |
| `depth_profile` | 报告深度档位表与解析（brief/standard/deep：只收窄模块集合与新闻采集规模，缺省档与既有行为逐字节一致） | LLM 智能分析 | 内容生成 | `config.json → llm_report_depth` |
| `force_scope` | 模块级强刷范围（可强刷键清单 FORCEABLE_LLM_MODULES / resolve_force_scope 粒度优先归一与未知键校验 / is_module_forced；全局 force 与模块子集合并为模块键集合，强刷不改缓存键构造） | LLM 智能分析 | 内容生成 | 无（CLI `--llm-module` / TUI 多选 / Web 勾选，命令行一次性参数） |
| `llm_providers.priority` | LLM 多链线路优先级（降级顺序三渠道调序：共享编辑层 reorder 动作归一化写盘，CLI `--llm-provider-order` / TUI [M] 面板 / Web 配置面 ▲▼） | LLM 智能分析 | 内容生成 | `llm_providers.json → providers[].priority` |
| `self_review` | 生成后自检（模型层复核各模块产出与数据是否自洽；分层于确定性事实校验之上，出厂默认开） | LLM 智能分析 | 内容生成 | `llm_settings.json → enabled_llm.self_review` |
| `quarter_walk_anchor` | 季报回溯窗口的时间锚点上下文（记录-回放时固定为 cassette 录制时点，去时间依赖而保留请求形状漂移信号） | 数据源 | 数据获取 | 无 |
| `apply_compliance_guardrails` | 合规声明集中注入（在 system prompt 尾部幂等叠加「仅供复盘参考、不构成投资建议」，窄判定角色可追加专属约束） | LLM 智能分析 | 内容生成 | 无 |
| `cost_forecast` | 事前费用预估与日预算（计划参与模块×模型单价区间预估：历史实际费用优先、静态包络兜底、无法定价降级不阻塞；重新生成范围感知——`force_llm`/`force_modules` 与创建运行同源 `resolve_force_scope` 归一，范围内模块按静态单价口径、范围外维持历史口径，摘要行拆分显示；日预算超限交互询问降级/中止、非交互硬闸——TUI/CLI/Web 三渠道同源数据面） | LLM 智能分析 | 内容生成 | `llm_settings.json → daily_cost_limit` |
| `print_llm_cost_summary` | CLI 收尾 LLM 成本摘要行（调用次数/输入输出 token/模型名，无调用时静默） | CLI 命令行 | 运行收尾 | 无 |
| `print_cache_hit_summary` | CLI 收尾缓存命中率行（命中/总数/命中率，无缓存读写时静默，0% 亦输出） | CLI 命令行 | 运行收尾 | 无 |
| `hithink` | 同花顺金融数据服务 provider（A 股行情/财务/基金/情绪面；凭据声明/qps 限速/信封错误码） | 数据源 | 数据获取 | 需凭据源（`data_key.json` 的 `hithink` 节或 `HITHINK_FINANCE_API_KEY`） |
| `fund_thscode_candidates` | 基金代码 → thscode 候选（补零 + 场内/场外后缀，逐个试到命中） | 基金业绩分析 | 数据获取 | 无 |
| `HithinkQuoteAdapter` | 同花顺官方行情适配器（行情域第三槽；`last_price`→`price`、`prev_price`→`yesterday_close`，不提供总市值 → None） | 持仓明细 | 数据获取 | 需凭据源（`hithink` 节） |
| `fetch_price` | 单只 A 股/场内基金官方行情快照（链路槽形态：`{name, code, price, yesterday_close, open, high, low, volume, turnover, price_date}`） | 持仓明细 | 数据获取 | 需凭据源 |
| `fetch_kline` | 官方历史日 K（前复权；`date_ms` 字段、支持 `start_from` 增量，对齐既有 provider 形态） | 流动性分析 | 数据获取 | 需凭据源 |
| `fetch_index_kline` | 指数历史日 K provider 槽（腾讯/新浪/东方财富 push2his/同花顺；前复权，对齐既有 provider 形态） | 数据源 | 数据获取 | 东方财富免 key；同花顺需凭据源（`hithink` 节） |
| `to_index_thscode` | 指数代码 → 同花顺 thscode（`sh000300` → `000300.SH`，`sz399001` → `399001.SZ`；与 A 股 `to_thscode` 同后缀口径） | 数据源 | 数据获取 | 需凭据源（`hithink` 节） |
| `holdings_detail` | 持仓明细与分类（合并章：市值核算明细区块 + 持仓分类汇总区块同页签呈现） | 持仓明细与分类 | 报告输出 | 始终显示（type=always） |
| `holdings_detail_sheet` | 合并章 Excel 写入器（`write_holdings_detail_sheet`；区块写入器 `_write_market_value_block` / `_write_category_block`） | 持仓明细与分类 | 报告输出 | 无（渲染） |
| `position_structure` | 持仓结构与集中度（合并章：重合度区块 + 相关性区块 + 集中度区块同页签呈现；可见性 `data_flag_any` OR） | 持仓结构与集中度 | 报告输出 | 基金深度分析（`enable_fund_deep_analysis` 控制） |
| `position_structure_sheet` | 合并章 Excel 写入器（`write_position_structure_sheet`；区块写入器 `_write_overlap_block` / `_write_correlation_block` / `_write_concentration_block`） | 持仓结构与集中度 | 报告输出 | 无（渲染） |
| `candidate_compare` | 候选基金比较 | 基金业绩分析 | 买入/选基 | 功能开关 `candidate_compare`（默认关） |
| `valuation_percentile` | 估值分位 | 资产穿透TOP10 | 买入/选基 | 功能开关 `valuation_percentile`（默认关） |
| `market_temperature` | 市场温度 | 投资分析汇总 | 买入/选基 | 功能开关 `market_temperature`（默认开） |
| `summary_highlights` | 本期要点与环比对照 | 投资分析汇总 | 监控 | 功能开关 `summary_highlights`（默认关；首屏执行摘要卡 = 关键指标环比行（总市值/总收益率/持仓数/集中度 HHI） + 本期关键变化 Top 5（按市值变化绝对值降序）；快照 diff 单源派生零新增取数，无上期快照时整块隐藏） |
| `compute_rolling_correlations` | 滚动相关性趋势（组合平均 60/120 端点窗 + 重点品对滚动 r；历史不足按可得区间截断并在 notes 标注口径，downsample 下采样在编排层） | 持仓结构与集中度·区块二（相关性） | 分析 | `analysis/correlation.py` 纯计算，随静态矩阵同底座数据 |
| `feeder_penetration` | 取数结果中的穿透来源标注字段（记录联接基金穿透自哪个目标 ETF，供报告层标注「穿透自目标 ETF」；**无对应功能开关**——穿透为内置恒开口径，原开关已移除） | 资产穿透TOP10 | 数据获取 | `fetcher/fund.py::with_feeder_penetration`（结果标注键，非开关） |
| `with_feeder_penetration` | 穿透后处理（fetcher 层幂等后处理，目标 ETF 的持仓代理该基金的底层暴露） | 资产穿透TOP10 | 数据获取 | 随 `feeder_penetration` |
| `parse_feeder_target_etf` | 目标 ETF 解析（联接基金主页面锚点 → 目标 ETF 代码，两重区分反向链接） | 资产穿透TOP10 | 数据获取 | 无（解析原语） |
| `feeder_target_code` | 目标 ETF 标识（联接基金在第 2 跳的取数结果字段） | 资产穿透TOP10 | 数据获取 | 无（结果字段） |
| `period_entry_label` | 报告期明细条目措辞（带穿透来源时补注目标 ETF 与「未折算持有比例」） | 资产穿透TOP10 | 报告配置 | 无（渲染原语） |
| `cache_validate` | 缓存载荷准入判据（`fetch_with_fallback` 参数：载荷未通过判据即视为未命中、清缓存重取） | 资产穿透TOP10 | 数据获取 | 无（链路原语） |
| `financial_report_digest` | 持仓个股财报摘要（持仓基本面章区块二：A 股标的取最新年报章节原文摘要；数据源 DataSinking，需用户自备 key） | 持仓基本面 | 数据获取 | 功能开关 `stock_fundamentals`（默认关） |
| `financial_indicator` | 财务指标（数据域 + 持仓基本面章区块一：上市公司单报告期结构化指标 + 质量档 + 年度趋势 + 当前 PE/PB） | 持仓基本面 | 数据获取 | 功能开关 `stock_fundamentals`（默认关） |
| `stock_fundamentals` | 个股基本面独立章（单一开关控持仓基本面两块：财务指标 + A 股财报章节摘要；原 `financial_indicator`/`financial_report_digest` 两开关并入，旧键读写迁移并告警） | 持仓基本面 | 报告输出 | 功能开关 `stock_fundamentals`（默认关，独立章节与回放组） |
| `financial_indicator_data` | 财务指标数据契约（C19：available/reason/rows/failures/entry_count） | 持仓基本面 | 数据获取 | 无（契约） |
| `fund_purchase_limit` | 基金申购限购状态列（持仓明细两端——Excel 市值明细/分类汇总两区块末列 + HTML 市值明细/持仓分类表条件列：申购状态 + 日限额/下一开放日，天天基金渠道口径；数据不可用静默隐列） | 持仓明细与分类 | 数据获取 | 功能开关 `fund_purchase_limit`（默认开） |
| `purchase_status_data` | 申购限购状态数据契约（C19：available/reason/rows/fetched_at/source） | 持仓明细与分类 | 数据获取 | 无（契约） |
| `purchase_status` | 申购状态展示装配与展示单源（`report/purchase_status.py`：契约构建/陈旧阶梯分档/单元格文案/口径脚注，Excel 与 HTML 共用） | 持仓明细与分类 | 报告输出 | 无（单源模块） |
| `cost_position` | 持仓成本区间位置列（持仓明细两端——Excel 市值明细/分类汇总两区块末列两列：每份成本相对近 20/260 交易日价格区间百分位，≈1 追涨嫌疑；纯计算 `analysis/cost_position.py` + 编排 `report/cost_position.py`，行情缺失静默隐列） | 持仓明细与分类 | 数据获取 | 功能开关 `cost_position`（默认开） |
| `cost_position_data` | 持仓成本区间位置数据契约（available/positions/footnote） | 持仓明细与分类 | 数据获取 | 无（契约） |
| `whatif_trade_cost` | What-if 交易成本对比（回放计入申赎成本：FIFO 快照批次交易日持有期阶梯 + 金额分档申购；t0 一次性扣费成本前/后差 + 业绩基准三线；费率未知/场内品种显式标注不出成本后数字） | 调仓 What-if | 报告输出 | 报告章节与增强开关 `whatif_trade_cost`（默认关） |
| `trade_cost_model` | 调仓交易成本模型唯一实现（快照事件 FIFO 批次重放：期初批首见日下界 + 逐批判档加权 + 腿级费用聚合 → `trade_cost` 契约，纯计算零 I/O；表选档下沉 `fee_schedule_model`） | 调仓 What-if | 分析计算 | 随 `whatif_trade_cost` |
| `fee_schedule_model` | 申赎费率表模型唯一实现（F10 费用表文本解析 / 单档与配置构建 / 金额与交易日持有期选档，边界左闭右开） | 调仓 What-if | 数据获取 | 随 `whatif_trade_cost` |
| `benchmark_index_resolver` | 业绩基准指数映射（config 覆盖 → 持仓基准文本反查对比指数池 → 宽基默认，源标注零 I/O） | 调仓 What-if | 分析计算 | 随 `whatif_trade_cost` |
| `whatif_cost_panel` | 交易成本面板装配（成本本体 + t0 扣费成本前/后差 + 基准曲线 LOCF 对齐归一 + 图表负载裁剪，分阶段降级） | 调仓 What-if | 报告输出 | 随 `whatif_trade_cost` |
| `fund_fee` | 基金申赎费率取数编排（F10 费用页 → akshare 备链 → 过期缓存 → 配置兜底；`FEE_SCHEMA` 载荷准入） | 调仓 What-if | 数据获取 | 随 `whatif_trade_cost` |
| `fetch_fee_index` | 持仓级费率索引装配（仅非未建模腿经链取数、会话复用；未知侧计数 → `fees_complete` 判据） | 调仓 What-if | 数据获取 | 随 `whatif_trade_cost` |
| `fundamental_snapshot` | 持仓基本面（合并章：财务指标区块 + 财报摘要区块同页签/同章节呈现；两块由同一功能开关同开同关，单块渲染由各自数据契约判定；可见性 `data_flag_any` OR） | 持仓基本面 | 报告输出 | `enable_fundamental_snapshot`（= 功能开关 `stock_fundamentals`） |
| `fundamental_snapshot_sheet` | 合并章 Excel 写入器（`write_fundamental_snapshot_sheet`；区块写入器 `_write_indicator_block` / `_write_digest_block`） | 持仓基本面 | 报告输出 | 无（渲染） |
| `compute_real_valuation` | 真实历史估值分位（TTM 口径：多期每股收益差分 × 历史收盘价 → 历史 PE/PB 序列 → 当前值分位） | 资产穿透TOP10 | 分析计算 | 无（纯计算） |
| `_fundamental_signal` | 持仓基本面信号（质量档与年度趋势同向才给方向，逐只指标聚合为分布） | LLM 提示词信号 | LLM 注入 | 随 `deterministic_signal`（默认开） |
| `_narrative_divergence_signal` | 叙事与数字背离信号（摘要语气词频 × 指标趋势/同比确定性比对，只列依据不下结论） | LLM 提示词信号 | LLM 注入 | 随 `deterministic_signal`（默认开） |
| `datasink_feature_ready` | DataSinking 数据底座就绪判定（配置位 `datasink.enabled` 开启 且 凭据就绪；纯本地、零请求）——门禁持仓基本面章区块二与真实历史估值分位 | 持仓基本面 | 数据获取 | `datasink.enabled`（默认开） |
| `FinancialIndicatorFields` | 财务指标标准字段记录（金额单位元；比率为小数比例；可选数值缺失取 None） | 资产穿透TOP10 | 数据获取 | 无（契约） |
| `akshare_financial` | akshare 财务指标（指标域主源，无需凭据；一条调用多股） | 资产穿透TOP10 | 数据获取 | 无（provider） |
| `derive_indicator_records` | 三张合并报表 → 标准财务指标记录（纯派生：营收/归母净利/毛利·负债·ROE 派生、同比对上年同期、报告期按 fiscal_period 归一到季末） | 持仓基本面·区块① | 数据获取 | 无（纯函数） |
| `HithinkIndicatorAdapter` | 财务指标域第三链路适配器（同花顺官方报表派生；需凭据） | 持仓基本面·区块① | 数据获取 | 需凭据源（`hithink` 节 / `HITHINK_FINANCE_API_KEY`） |
| `datasink_indicator` | DataSinking 指标解析（备用支路：从「公司简介和主要财务指标」章节压平正文按锚点提取指标） | 资产穿透TOP10 | 数据获取 | 无（provider / 适配器） |
| `financial_indicator_extract` | 财务指标提取（压平正文 → 标准字段的纯解析层：锚点 + 取值窗口 + 精度模式 + 合理性校验） | 资产穿透TOP10 | 数据获取 | 无（纯解析） |
| `rebalance_advice` | 调仓建议 | 行动建议 | 调仓 | `enable_action`（默认开） |
| `trade_discipline` | 交易纪律 | 行动建议 | 调仓 | `enable_action`（默认开） |
| `return_attribution` | 收益归因（大类 → 品种两级贡献分解） | 行动建议 | 调仓 | `enable_action`（默认开） |
| `classify_holding_tier` | 持仓分类单源（资产属性 × 投资分类；报告分类页签与收益归因大类分解共用） | 持仓分类 / 收益归因大类层 | 分类 | 无（`core/code_utils.py` 纯函数，关键词原语同居一处） |
| `fund_flow` | 资金流水与资金加权收益 | 「投资分析汇总」/「持仓明细与分类」章 + 输入扩展 | 成本/现金流 | 功能开关 `cost_lots`（默认关；有交易/分红流水走精确计算，无流水触发快照近似，可选 `holdings_start_date` 开近似年化） |
| `cost_lots` | 成本流水（成本分档 + XIRR + 分红累计） | 「投资分析汇总」/「持仓明细与分类」章 | 成本/现金流 | 功能开关 `cost_lots`（默认关；无流水时由 `build_approximate_fund_flow_data` 快照近似兜底） |
| `holdings_start_date` | 组合建仓日期（可选，近似年化基准） | 输入扩展 | 成本/现金流 | 顶层配置键 `holdings_start_date`（YYYY-MM-DD，默认空=不计算近似年化，仅成本分档近似） |
| `industry_beta` | 行业 Beta 暴露 | 风格与因子分析 | 风险/暴露 | 功能开关 `industry_beta`（默认关） |
| `crisis_annotation` | 危机区间标注 | 组合历史走势与回撤 | 风险/暴露 | 始终渲染（样本不足时占位，R-TAIL 强制） |
| `crisis_replay` | 危机区间双层回放 | 组合历史走势与回撤 | 报告输出 | 功能开关 `crisis_replay`（默认关；指数层覆盖全部静态危机区间，组合层仅子块扩展窗内区间，窗外行标「组合窗口外」） |
| `risk_adjusted_excess` | 风险调整超额与基准对照 | 组合历史走势与回撤 | 报告输出 | 功能开关 `risk_adjusted_excess`（默认关；第五区块 IR/TE/年化超额 + 12/24 月胜率 + 滚动 250 日超额） |
| `build_risk_adjusted_excess` | 风险调整超额计算（IR/TE/年化超额/滚动胜率，样本不足逐项降级） | 组合历史走势与回撤 | 数据获取 | 随开关 `risk_adjusted_excess` 消费（`risk_adjusted_excess_data` 契约） |
| `assemble_history_augmented_data` | 历史增强契约装配（危机回放与风险调整超额共用子块扩展窗取数，full/both 双路径同源） | 组合历史走势与回撤 | 报告输出 | 随开关 `crisis_replay` / `risk_adjusted_excess` 消费 |
| `tail_risk` | 尾部风险 | 组合历史走势与回撤 | 风险/暴露 | 始终渲染（样本不足时占位，R-TAIL 强制） |
| `monthly_returns` | 月度收益日历 | 组合历史走势与回撤 | 监控 | 历史数据可用时渲染（样本不足不出区块，as-if 口径、双口径并排预留） |
| `snapshot_diff` | 快照差异 | 组合演进 | 监控 | 随 `enable_portfolio_evolution` |
| `data_quality` | 数据质量仪表盘 | 数据源可用性矩阵 | 监控 | 功能开关 `data_quality`（默认开） |
| `snapshot_namespace` | 快照隔离命名空间（试算域 `web` / 共享主目录） | 快照存储/Web 输入 | 输入隔离 | 无（run 级参数） |
| `web_input_mode` | Web 输入模式（试算/正式） | Web 输入 | 输入隔离 | 无（run 级参数 `mode`） |
| `use_existing` | 直接用正式持仓文件 | Web 输入 | 输入隔离 | 无（run 级参数） |
| `holdings_update` | 正式持仓更新（备份 + 提升） | Web 输入 | 输入隔离 | 无 |
| `config_edit` | Web 配置编辑外观（再导出共享编辑层符号 + `get_config_edit_surface` 呈现面） | Web 配置 | 配置编辑 | 无（功能面） |
| `config_edit_whitelist` | 可编辑配置项白名单（键→类型/枚举→目标文件→写入原语；定义于共享编辑层，TUI/Web/CLI 同源） | 配置管理 | 配置编辑 | 无（校验面） |
| `edit_ops` | 配置编辑共享层（白名单 + 值规则 + 写入分派 + 写前备份，TUI/Web/CLI 唯一编辑通道） | 配置管理 | 配置编辑 | 无（校验面） |
| `system_info` | 系统状态组装与展示原语（Web 状态卡 / TUI 首页共用数据源：熔断/路由/凭据回填/匿名化标签） | 核心基础设施 | 状态展示 | 无（展示面） |
| `history_policy` | 历史走势获取策略解析（off/auto/prompt 单源，三渠道共用，TUI 注入询问回调） | 报告生成 | 组合历史走势 | `history.fetch_mode` |
| `run_integrity` | 生成运行一致性守卫（`guard_run` 装饰 `generate_report` 中断收口：临时产物清扫/已写盘登记/`status=interrupted` 运行记录/健康检查收敛；ContextVar 按线程隔离，写盘方 `note_temp`·`note_artifact` 登记） | 报告生成 | 报告输出 | 无（设施模块，中断时经 reporter 输出明细） |
| `config_backup` | 配置写前备份（`.bak` 单槽轮转） | Web 配置 | 配置编辑 | 无（安全面） |
| `report_section_order` | 报告模块序号配置（键=模块标识，值=序号；空对象用默认 19 项顺序） | 报告编排 | 报告配置 | 顶层配置键 `report_section_order`（`get_report_section_order()` 读取，`llm_usage` 强制末位） |
| `generators_news` | 财经新闻 LLM 关联分析（新闻热词→持仓关联二次生成） | 财经新闻热点与持仓关联分析 | LLM 生成 | 随 `enable_news` + LLM 启用 |
| `_pair_similarity` | 标题相似度口径的唯一实现（归一化 → 日期剥离 → 英文分桶占位 → 双向 ratio + 实体 bigram 交集；链路判定与校准工具共用，防两套口径漂移） | 财经新闻热点与持仓关联分析 | 数据获取 | 随 `enable_news` |
| `anchor_rules_version` | 锚点规则时代指纹字段（`_rules_fingerprint()` 由阈值/模板词表/方向词对/正则 + 行为探针派生，规则一改自动变，供校准工具区分时代） | 财经新闻热点与持仓关联分析 | 数据获取 | 随 `enable_news` |
| `news_dedup_rules` | 去重规则原语模块（阈值常量 / 模板词表与掩码 / 标题归一化 / 实体 bigram / 相似度口径 / 方向词对 / 规则指纹的唯一实现） | 财经新闻热点与持仓关联分析 | 数据获取 | 随 `enable_news` |
| `record_prosperity_diagnosis` | 景气度框架诊断挂载点（市场与估值组开关；守卫 + 契约注入 `pipeline_data` 由 `_experimental_seams` 统一提供） | 行动建议（章内嵌块） | 报告输出 | 分析增强开关 `prosperity_framework`（默认开） |
| `inject_holding_change_data` | 持仓变动复盘挂载点（独立章节与回放组开关；守卫 + 契约注入 `pipeline_data` 由 `_experimental_seams` 统一提供） | 持仓变动复盘（报告独立章，type=holding_change） | 报告输出 | 独立章节与回放开关 `holding_change_review`（默认关） |
| `inject_event_impact_data` | 事件窗量化对照挂载点（事件与摘要组开关；守卫 + 契约注入 `pipeline_data` 由 `_experimental_seams` 统一提供；新闻先行串行段内注入，供分歧例附录块同轮进 LLM） | 事件窗量化对照（财经新闻章内区块，随父章；注册表无独立条目） | 报告输出 | 报告章节与增强开关 `event_window_impact`（默认关） |
| `inject_schedule_replay_data` | 调仓纪律回放挂载点（守卫 + 契约注入 `pipeline_data` 由 `_experimental_seams` 统一提供；快照与持仓变动注入后串行装配，回放引用 `prompt_block` 经统一附录进 LLM） | 调仓纪律回放（报告独立章，type=schedule_replay） | 报告输出 | 功能开关 `rebalance_schedule_replay`（默认关，独立章节与回放组） |
| `event_impact_panel` | 事件窗对照表数据编排与双端单源展示（事件行/降级/占位 + view 与页签同文 + 分歧例附录块） | 事件窗量化对照 | 报告输出 | 随 `event_window_impact` |
| `event_window_impact` | 事件窗量化对照（新闻事件 → 交易日映射的 ±5 交易日窗收益 vs 文本极性方向比对；行情轴右端不足 5 日时按可用交易日截断并标未满窗，分歧例进 LLM 统一附录） | 事件窗量化对照 | 报告输出 | 报告章节与增强开关 `event_window_impact`（默认关） |
| `schedule_replay_panel` | 调仓纪律回放数据装配与双端单源展示（回放契约 + view 与页签同文 + 回放引用 prompt_block） | 调仓纪律回放 | 报告输出 | 随 `rebalance_schedule_replay` |
| `rebalance_schedule_replay` | 调仓纪律回放（月度定期/阈值偏离纪律多期回放 vs 买入持有，双线图与逐期成本表，回放结论进 LLM 统一附录） | 调仓纪律回放 | 报告输出 | 功能开关 `rebalance_schedule_replay`（默认关，独立章节与回放组） |
| `factor_catalog` | 因子目录注册表（25 因子五来源族冻结清单：slug/族/类别/所需字段/中性点/出处，版本随代码；含中性点字典与字段类型路由常量） | 风格与因子分析（章内区块四） | 数据契约 | 功能开关 `factor_catalog`（默认关，分析增强组） |
| `factor_catalog_loader` | 因子目录装载与冻结校验（拒载降级）+ 四类输入备数（日K/基准指数/估值/财务指标，逐类型失败入 unavailable 不外抛） | 风格与因子分析 | 数据获取 | 随 `factor_catalog` |
| `factor_evaluator` | 因子目录计算编排（池构造：直接持仓 ∪ 穿透 A 股 → 逐因子池内横截面 → 中性相对与评级摘要，全链 fail-soft） | 风格与因子分析 | 报告输出 | 随 `factor_catalog` |
| `_factor_formulas` | 25 因子公式纯计算原语（技术族逐因子序列与基本面标量分发，无 I/O、不进报告层） | 风格与因子分析 | 数据获取 | 随 `factor_catalog` |
| `holding_change_review` | 持仓变动复盘（快照事件级：差分事件清单 + 频率/结构/贡献分解 + 意图对账 + 账户结构重排标注 + LLM 归因） | 持仓变动复盘 | 报告输出 | 独立章节与回放开关 `holding_change_review`（默认关） |
| `module_fingerprint` | LLM 模块缓存指纹唯一事实来源（预检侧与写侧同源） | LLM 生成 | LLM 生成 | 无（模块级） |
| `decision_reflection` | 决策跨期反思闭环（登记决策 → 真实行情结算命中率 → 教训回灌专家复盘提示词） | 行动建议 | 监控 | 实验开关 `decision_reflection`（默认关） |
| `decision_ledger` | 决策账本（append-only JSONL，pending/settled 折叠统计） | 行动建议 | 监控 | 随 `decision_reflection` |
| `decision_record` | 确定性卖出建议登记（仅带持仓基线者落账，入账必可结算） | 行动建议 | 监控 | 随 `decision_reflection` |
| `decision_settlement` | 到期决策结算（幂等：同 decision 只结一次，行情不可得保持 pending） | 行动建议 | 监控 | 随 `decision_reflection` |
| `decision_llm_capture` | LLM 操作建议表解析登记（误导性操作格不登记） | 行动建议 | 监控 | 随 `decision_reflection` |
| `decision_review_block` | 「历史决策复盘」区块数据契约（结构稳定，HTML/Excel 双端消费） | 行动建议 | 监控 | 随 `decision_reflection` |
| `build_structured_header_instruction` | 决策头结构化契约构建（提示词侧追加 `决策头：…` 行，与解析器口径锁定） | 行动建议 | 监控 | 已内置（缓存后缀 `_dh` 常驻） |
| `decision_header` | 决策词归一解析器（标签优先/长词优先/否定守卫/复合词左边界/二义不猜） | 行动建议 | 监控 | 已内置（A 通道无开关） |
| `deterministic_signal` | 确定性信号模块（实时注入 + 跨期沉淀双面：温度/分位/尾部风险预消化信号行 + 确定性评级账本沉淀，内置五类、因子目录随实验开关追加第 6 类；原 `signal_pre_digest`/`signal_ledger` 两开关合并转正） | LLM 生成 | LLM 生成 | 开关 `deterministic_signal`（默认开，机制与诊断组） |
| `prompts_signals` | 信号预消化提示词块（开关判定收敛于缓存后缀函数） | LLM 生成 | LLM 生成 | 随 `deterministic_signal` |
| `signal_ledger` | 确定性数值信号沉淀（各信号类型评级登记 + live/demo 来源标签，排行榜默认 live_only） | LLM 生成 | 监控 | 随 `deterministic_signal` |
| `signal_record` | 确定性信号登记适配器（唯一持有语义词表映射，`core/` 不依赖 `analysis/`） | LLM 生成 | 监控 | 随 `deterministic_signal` |
| `experiment_stats` | 实验功能使用统计（启用计数/最近启用日期，data/state/experiment_stats.json；报告入口自动记录，doctor 上屏；为转正/撤销决策提供客观数据） | 诊断 | 监控 | 无（观测设施） |
| `module_quality_gate` | 模块级质量分级（4 个 LLM 模块按完整性/篇幅评 A~F，低评级注入质量横幅，只标注不阻断） | LLM 生成 | LLM 生成 | 开关 `module_quality_gate`（默认开，非实验项） |
| `llm_quality` | 质量分级实现（口径判定 + 横幅注入 + Excel 载体契约） | LLM 生成 | LLM 生成 | 随 `module_quality_gate` |
| `log_reader` | 日志读取（read_log/tail_log/parse_log） | 日志可视化 | 诊断 | 无（模块级） |
| `view_logs` | 查看日志（CLI view-logs 子命令） | 日志可视化 | 诊断 | 无（子命令） |
| `health_history` | 数据源健康历史（load_health_history/summarize_health_history） | 日志可视化 | 监控 | data/state/datasource_health.jsonl |
| `jsonl_store` | JSONL 原子追加 + 按龄裁剪原语（`perf`/`decision_ledger`/`signal_ledger` 共同委托的唯一拷贝；`prune_jsonl_by_age` 供业务账本按保留窗口裁剪，`max_lines` 仅限遥测类） | 诊断 | 监控 | 无（模块级） |
| `num_utils` | 数值归一原语（`safe_num` 显式拦下 NaN/±inf，替代失效的 `try: float()` 兜底） | 诊断 | 数据获取 | 无（模块级，A 通道无开关） |
| `retry` | 重试与退避唯一原语（`RetryPolicy` 策略算式——固定/线性/指数/**显式序列**、`is_transient_exception` 瞬时判据、`retry_transient` 执行器；取数链路、各 provider 与 LLM 调用骨架共用） | 诊断 | 数据获取 | 无（模块级） |
| `throttle` | 按名最小间隔节流唯一原语（`RateLimiter` + `interval_delay` 抖动算式 + `wait_interval` 一次性等待；数据层限速/批量调度/LLM 端点节流/429 退避窗口共用） | 诊断 | 数据获取 | 无（模块级） |
| `completion_notify` | 任务完成通知（CLI/Web 报告收尾按 `notify` 配置分发 webhook/邮件/桌面三通道事件——失败必发、成功需 `on_success`；无配置静默跳过；单通道失败隔离、永不抛出不改退出码；webhook URL 日志只记域名；降级摘要单源 `report/data_status.degradation_summary()`） | 诊断 | 报告 | 随 `notify` 配置节 |
| `degradation_summary` | 通知降级摘要单源（数据状态跟踪器事件日志 → 摘要行，最新在前按源去重；CLI/Web 收尾共用，渠道层不再各自镜像） | 诊断 | 报告 | 随 `notify` 配置节 |
| `doctor` | 系统自检（环境/配置/目录/日志与缓存/功能开关/数据源适配/数据源凭据/数据源八组，失败项附可执行建议，自身永不抛异常） | 诊断 | 诊断 | 恒上屏（无开关） |
| `datasource_fields` | 数据域标准字段记录（`schemas/datasource_fields.py`，类型注解即缺省语义） | 数据源适配 | 数据获取 | 随 `adapter_chain_slots` |
| `source_adapter` | 数据源适配契约（`SourceAdapter` 基类 + 注册表 + 自检报告 `survey_adapters`） | 数据源适配 | 数据获取 | 已内置（适配契约） |
| `quote_adapters` | 行情域适配器（腾讯/新浪/东方财富三源） | 数据源适配 | 数据获取 | 已内置（适配契约） |
| `adapter_chain_slots` | 适配器映射为 Provider Chain 两槽（provider_fn_map / transform） | 数据源适配 | 数据获取 | 已内置（适配契约） |
| `feature_switch_registry` | 功能开关注册表（全部开关的唯一登记点，每条五字段：显示名/说明/分组/默认值/产物影响） | 功能开关 | 配置编辑 | 无（注册点自身；`features.json` 的键名即注册表键名） |
| `switches_in_group` | 分组取数（功能开关面板分块与实验清单的唯一来源，顺序即注册表声明顺序） | 功能开关 | 配置编辑 | 无（查询助手） |
| `is_experimental_switch` | 开关是否为实验项（`experimental` 字段——面板 ⚗ 标识与「转正」判定的唯一判据） | 功能开关 | 配置编辑 | 无（查询助手） |
| `parse_switch_override` | `--feature NAME=VALUE` 取值解析与即时校验（未知开关名/不可识别取值报错并列出可选值） | 功能开关 | 配置编辑 | 无（命令行一次性开关，不写盘） |
| `resolve_switch_values` | 命令行开关增量的归并去重（同名后写覆盖先写） | 功能开关 | 配置编辑 | 无（命令行一次性开关，不写盘） |
| `describe_switches` | 全注册表开关名清单（CLI 报错提示的可选值来源） | 功能开关 | 配置编辑 | 无（提示文案来源） |
| `cassette` | 数据源记录-回放（真实响应体离线录制/回放引擎，`Cassette`/`cassette_replay`/`cassette_record`） | 数据源记录-回放 | 数据获取（测试基建） | 无（测试基建，不控制运行时行为） |
| `get_cache_registry` | 缓存域注册表访问器（常规模块 + 注册表外**缓存专属**项：辩论三段缓存的前缀/TTL/preload 组归属） | 缓存引擎 | 缓存治理 | 无（缓存基础设施，不控制运行时行为；运行时开关由 `llm_debate_procon` 控制） |
| `cassette_checks` | 已录制响应 → 当前解析器的绑定表（录制自检与 `cassettes --verify` 共用） | 数据源记录-回放 | 数据获取（测试基建） | 无（测试基建） |
| `use_transport_factory` | 传输工厂注入点（`make_http_client` 的响应来源替换，C5 唯一构造点上的挂载） | 数据源记录-回放 | 数据获取（测试基建） | 无（测试基建） |
| `credential_spec` | 数据源凭据声明（`CredentialSpec` 冻结 dataclass + `CREDENTIAL_SPECS` 注册表） | 数据源可用性矩阵 | 监控 | 已内置（不可关闭） |
| `credential_readiness` | 凭据就绪矩阵与缺失指引（`missing_credential` / `credential_hint` / `credential_readiness`） | 数据源可用性矩阵 | 监控 | 已内置（不可关闭） |
| `mark_provider_used` | provider 级归属登记（链路成功时记「本数据类别由此 provider 服务」；矩阵「命中源」列数据来源） | 数据源可用性矩阵 | 监控 | 无（观测记录，不改产物判定） |
| `get_provider_usage` | provider 归属登记表快照（`{data_type: {provider_id: {count, label}}}`） | 数据源可用性矩阵 | 监控 | 无 |
| `reset_provider_usage` | 清空 provider 归属登记表（测试隔离） | 数据源可用性矩阵 | 监控 | 无 |
| `llm_debate_procon` | 辩论-正反辩论（三段式：白脸 → 黑脸 → 综合；集中度问答段内建于流程） | 智囊团深度复盘 | LLM 注入 | 功能开关（默认关，分析增强组） |
| `llm_debate_conditional` | 辩论-条件推理（上涨 / 下跌 / 震荡情景注入） | 智囊团深度复盘 | LLM 注入 | 功能开关（默认开，分析增强组；与正反辩论相邻） |
| `concentration_qa` | 集中度问答段（辩论流程内建：单品种占比超 `debate.concentration_qa.threshold` 时白脸/黑脸/综合各附集中度量化评估；原实验开关 `llm_debate_qa_concentration` 已撤销并入） | 智囊团深度复盘 | LLM 注入 | 无独立开关（随 `llm_debate_procon` 流程内建） |
| `metrics_enabled` | 量化指标显示（原 metrics_sharpe / calmar / hhi / winrate / turnover / risk_contribution / beta 七项并入；指标始终全量计算） | 量化指标雷达图画像（含降级 3 轴） + 指标熔断联动 | 报告输出 / 分析计算 | 常规开关（默认开） |

> **子功能并入说明**：以下语义已并入其他功能，不作为独立标识符参与本表校验——`dividend_flow`（分红现金流，并入 `fund_flow`）、`holding_diagnosis`（品种覆盖诊断，并入 `data_quality`）。

| `prosperity_framework` | 景气度框架诊断（六维评分卡：景气方向/ROE 低位弹性/全球视野与比较优势/流动性/集中度与周期拼接/业绩与回撤印证；缺数据维度标记需核实、不计分） | 行动建议（章内嵌块） | 调仓 | 分析增强开关 `prosperity_framework`（默认开） |
| `market_sentiment` | 市场情绪与持仓热点（行动建议章内嵌块：龙虎榜/连板梯队 ∩ 持仓与穿透标的；功能开关，默认关） | 行动建议（章内嵌块） | 报告输出 | 功能开关 `market_sentiment`（默认关） |
| `build_market_sentiment` | 市场情绪纯装配（龙虎榜/连板梯队 × 持仓与穿透标的 → 事件行契约；只按代码精确匹配，不猜概念） | 行动建议（章内嵌块） | 分析计算 | 随 `market_sentiment` |
| `market_sentiment_data` | 市场情绪与持仓热点数据契约（available/trade_date/summary/rows/failures；类型 dict） | 行动建议（章内嵌块） | 报告输出 | 无（契约） |
| `build_market_sentiment_data` | 市场情绪取数与装配入口（开关关闭返回 None；缺凭据/两源不可用返回降级契约；取数带 1h 缓存） | 行动建议（章内嵌块） | 数据获取 | 随 `market_sentiment` |
| `build_prosperity_framework_data` | 景气度框架诊断装配入口（纯计算；输入市值明细/穿透/基本面/流动性/快照/历史走势 → 契约） | 行动建议（章内嵌块） | 分析计算 | 随 `prosperity_framework` |
| `prosperity_framework_data` | 景气度框架诊断数据契约（available/reason/六维明细/持仓视角/未验证清单；类型 dict） | 行动建议（章内嵌块） | 报告输出 | 无（契约） |
| `estimate_fund_roe_batch` | 基金重仓股 ROE 加权估算入口（取数编排：基金持仓批量 + 个股 ROE 补齐 → 推演值；报告期陈旧闸门与穿透层同口径；任一基金失败只缺席该基金） | 行动建议（章内嵌块） | 数据获取 | 随 `prosperity_framework` |
| `cninfo` | 巨潮资讯网财报备源（公开免费无需凭据；公告列表 → 文种归类 → PDF 解析 → 章节切片；固定礼貌限速 + 429 退避；缺 pdfplumber 时降级为空文本） | 持仓基本面（区块②） | 数据获取 | 随 `stock_fundamentals`（仅主源无该标的时接管） |
| `fetch_report_listings` | 巨潮公告列表归一入口（元数据形状对齐主源索引，供编排层候选排序/报告期回溯零改动复用） | 持仓基本面（区块②） | 数据获取 | 随 `stock_fundamentals` |
| `CninfoReportAdapter` | 财报域备源适配器（`source_hint` 命名空间隔离；章节关键词切片走共用定位规则） | 持仓基本面（区块②） | 数据获取 | 随 `stock_fundamentals` |
| `locate_keyword_excerpt` | 财报正文关键词定位（跳过目录行；全文兜底与备源切片共用，单一实现） | 持仓基本面（区块②） | 分析计算 | 无 |
| `fund_roe_estimates` | 基金 ROE 推演值映射（{基金代码: {roe/covered_pct/top_n/basis/report_period}}；`basis=top10_holdings` 为阶段一前十大重仓口径，全量持仓口径落地后新增取值） | 行动建议（章内嵌块） | 报告输出 | 无（契约） |
| `roe_by_code_from_rows` | ROE 行解析唯一事实来源（财务指标契约行 → {代码: ROE}，含非数值过滤；评分维度/推演集合判定/编排层免重取三处共用） | 行动建议（章内嵌块） | 分析计算 | 无 |
| `estimated_fund_codes` | 推演集合判定唯一事实来源（有可用推演值且无直接 ROE 的基金代码集；评分侧与契约说明/持仓视角标注侧共用，两侧不得各自实现） | 行动建议（章内嵌块） | 分析计算 | 无 |
| `otc_redemption_days_default` | 场外基金赎回天数类型默认档（货币/短债 T+1、纯债 T+2、其他场外 T+3、QDII T+7；非实测口径，未识别返回 None；供流动性维与场外赎回标签共用） | 行动建议（章内嵌块）/ 流动性风险 | 分析计算 | 无 |
> **合并章代码标识符**：合并章 sheet key 统一为语义名——`holdings_detail`（持仓明细与分类，合并 `market_value` + `category`）、`position_structure`（持仓结构与集中度，合并 `position_relationship` + `fund_concentration`）、`fundamental_snapshot`（持仓基本面，合并 `financial_indicator` + `financial_report_digest`）、`portfolio_history_drawdown`（组合历史走势与回撤，合并 `portfolio_history` + `drawdown_analysis`）、`style_factor`（风格与因子分析，合并 `fund_style` + `factor_exposure`）；实现层（模块、函数、变量、注释）一律用语义名，禁止沿用旧 key、禁止用任务编号命名。
| `purchase_status_data` | 申购限购状态数据契约（C19：available/reason/rows/fetched_at/source/restricted_index） | 持仓明细与分类 | 数据获取 | 无（契约） |
| `restricted_index` | 受限标的预格式化索引（code → 状态/日限额数值与文案/下一开放日/时效档；准入不满足 → 空索引 = 消费方回退） | 持仓明细与分类 | 数据获取 | 无（契约字段） |
| `build_restricted_index` | 受限标的预格式化索引渲染（持仓 ∩ 受限状态集，字段值与单元格同源格式化） | 持仓明细与分类 | 数据获取 | 无 |
| `_filter_restricted_rows` | 受限行筛选共享单源（准入 + 格式化字段值，建议层只读消费） | 持仓明细与分类 | 数据获取 | 无 |
| `evaluate_purchase_feasibility` | 申购可行性判定（限大额天数估算 / 暂停引用下一开放日 / 金额或限额未知不给天数，超阈值判不可行） | 行动建议 | 调仓 | 无 |
| `FEASIBILITY_MAX_DAYS` | 可行性天数阈值（交易日；超阈值判路径不可行） | 行动建议 | 调仓 | 无 |
| `describe_feasibility` | 受限提示话术（静态模板 + 索引字段值，含估算口径；Excel/HTML 单源） | 行动建议 | 报告输出 | 无 |
| `feasibility` | What-if 契约受限提示字段组（仅受限存在时追加的条件键，降级缺席 = 逐字节回退） | 行动建议 | 报告输出 | 无（契约字段） |
| `_purchase_restricted_index` | What-if 路径受限索引单点挂载（经缓存链取契约，异常兜底空索引） | 行动建议 | 数据获取 | 无 |
| `_build_feasibility_notes` | What-if 买入腿提示生成（新增/加仓判定，金额口径目标成本/成本增量；卖出腿不判定） | 行动建议 | 调仓 | 无 |
| `build_purchase_constraint_block` | 申购限购约束块单源渲染器（准入四条任一不过 → ""；行序 = 持仓序、缺名回退代码、陈旧附标、尾行硬约束声明） | 申购限购 | LLM 生成 | 无 |
| `constraint_block` | 契约条件字段（构建期渲染一次，llm 层只读数据，both/basic/What-if 路径恒空零开销） | 申购限购 | LLM 生成 | 无 |
| `purchase_constraint_block` | 约束块透传形参（提取同一实例交统一附录 / 指纹 / 新闻批量 hooks，全程不重拼） | 申购限购 | LLM 生成 | 无 |
| `purchase_block` | 指纹输入字段（条件并入：进提示词必进指纹，块空不追加 part 逐字节回退，接线前基线锁定） | 申购限购 | LLM 生成 | 无 |
| `extract_purchase_constraint_block` | 约束块提取唯一单源（编排层与新闻链两侧共用，契约键/嵌套调整只改此处） | 申购限购 | LLM 生成 | 无 |
<!-- semantic-index:end -->

> **registry.number 重排**：`registry._REPORT_SECTION_DEFAULT` 的 `number` 连续编号 1~19（历次章节合并与新增后整体重排；`llm_usage` 强制末位）。

[↑ 回到顶部](#目录)

---

### 6.8 报告对话式追问

> 定位：读者在 HTML 报告页内对**本期报告**的会话式问答（实验开关 `report_qa`，默认关，见 requirements.md §6.17）；入口两个——报告页尾区块（阶段 1-3）与 TUI 主菜单 [Q] 文本输入循环（阶段 4），同一会话服务承载。独立子包 `qa/` 而非并入 `llm/`——追问是「面向报告的服务」而非 LLM 报告模块：不进 `_MODULE_FNS`/模块注册（无模块缓存条目、无指纹、不参与报告模块状态标签），但其调用仍经 `llm/api.call_llm` 的 Provider Chain 路由与合规漏斗。依赖方向单向 `qa → llm`（api / markdown / fact_checker），`llm` 不感知 `qa`；回答用量独立记账，不写报告周期 LLM 用量统计。

- **模块划分**：`qa/context.py`（`extract_report_qa_context`：`sec-*` 锚点分章 + 汇总/LLM 章全文、数据章摘要、整体字符上限三层截断 + 表头名映射持仓基线 + 生成条件声明；解析锚点收敛单文件，模板契约变更唯一同步点，失败显式报错不静默给错误上下文）；`qa/session.py`（`QaSession` 会话态 + `create_report_qa_session` 会话表登记/淘汰 + `ask_report_qa` 唯一编排入口：历史折叠、轮数与输入双上限、用量记账、事实核对、Markdown 渲染）；`web/handlers.py::_handle_report_qa_ask`（POST /api/qa/ask 校验矩阵与状态码映射）；`tui/handlers_qa.py`（主菜单 [Q] 入口：输出目录报告选择 + `input()` 多轮输入循环 + 回答纯文本化展示 + 会话续传；`FEATURE_GATED_ITEMS` 与 Web/报告区块同源裁剪；零业务副本——会话/上下文/记账/降级全部经 `ask_report_qa`）；`partials/report_qa_section.html`（报告尾部区块，JS 内嵌自包含，同源 fetch + `file://` 降级引导，样式全取报告既有 token）。
- **数据流**：报告文件名（前端取自当前页 URL basename）→ 上下文（只读报告 HTML，零新增取数）→ system（边界规则 + 生成条件声明 + 本期报告内容）+ 最近 6 次问答历史（更早折叠为问题清单）+ 当前问题 → `call_llm` → `markdown_to_html` → `run_fact_check`（只检不改，警示不阻断）→ 统一信封返回。
- **渲染期纪律**：会话态只活在 `qa/session.py` 服务内（进程内存、线程锁保护）；开关态经 `_render_template` 的 render context（`report_qa_enabled`）传递，不写 `_ENV.globals`；关闭时主模板 include 整体处于条件分支内，报告字节不变（实验项默认关、关闭时产物不变）。
- **安全与日志**：report 参数三层同语义净化（路由/会话/上下文：basename + `.html` + 禁 `..` 与路径分隔符）；上下文在内存传递不落盘；日志只记会话 id、轮数、问题前 20 字与 token 数，不含上下文与回答正文。
- **设计定稿与验证**：设计定稿已随功能完成归入版本归档（历史快照）；测试载体见 testplan.md §2.1（R-QA-01~10，批 13/14）。

[↑ 回到顶部](#目录)

---

### 6.9 实验项生命周期表

> 定位：全部 ⚗ 实验项（`experimental=True` 的功能开关）的**单一事实位**——判据、转正/撤销条件与当前态只在本表维护；计划死线条目与版本归档的评估记录是其**双向引用入口**（各自回链本节，本表不复制其全文）。**纪律：实验项立项（新增 `experimental=True` 条目）、转正（摘除 `experimental`）、撤销（删除注册表条目与机制）任一发生时，必须同步刷新本表。** 面板 ⚗ 标记、页脚实验功能清单与 `--experiment` 取值域均派生自注册表 `experimental` 字段，本表解释其「为什么在此态、何时变」。

| flag | 实验目的 | 判据来源 | 转正条件 | 撤销条件 | 观察数据源 | 当前态 |
|:-----|:---------|:---------|:---------|:---------|:-----------|:-------|
| `decision_reflection`（决策跨期反思闭环） | 用真实行情结算历史决策命中率，并把教训回灌专家复盘提示词——验证「教训回灌」对复盘质量的真实增益 | 计划管理文档「决策跨期反思闭环（`decision_reflection`）验证死线」条目（判据与观测手段在该条目维护） | 已结算样本 ≥10 条且命中率可采信 → 据 doctor 账本概览评估转正（摘除 `experimental`，面板 ⚗ 消失、页脚不再随产物自述） | 启用次数停止增长（无真实使用），**或** 已结算样本 <10 且无达标趋势 → 撤销实验（含 LLM 决策登记 `decision_llm_capture`、行动章复盘块注入与对应需求条目） | `experiment_stats` 启用计数、`data/state/decision_ledger.jsonl` 已结算样本、`doctor` 复盘账本概览 | 观察中（2026-10-23：启用 63 次／已结算 11 条／directional 9 条，命中率样本未达可信阈值；37 条 LLM 决策待到期结算） |
| `report_qa`（报告对话式追问） | 报告页内会话式追问，验证「零新增取数的报告内问答」的可用性与回答忠实度 | 版本归档「`report_qa` 转正评估挂账」记录（首轮评估已执行，判据与执行清单固化在该记录） | 真实使用样本充分（启用频次达标）**且** 问答样本留痕可抽检（`QaSession` 持久化）**且** 费用留痕接入 perf → 按转正清单摘 `experimental`、复核 `affects_report`、三端文档同步、收窄 `--experiment` 取值域 | 长期无人使用触发撤销条件，或忠实度不可接受 → 按撤销清单摘注册表条目与页内区块 | `experiment_stats` 启用计数、`QaSession.usage`（token 口径，费用口径待接）、问答样本抽检 | 实验观察（转正判据挂账中） |

**行维护约定**：新增实验项时按上表七列补行（列结构固定，行随实验项增长）；判据/清单的详文留在各自的计划或归档文档，本表只收结构化的「条件—数据—态」三元组，避免两处口径漂移。

[↑ 回到顶部](#目录)

---

## 7. 模块间依赖关系

```
core/reader.py (持仓解析)
  → core/models.py (Holding/DetailRow 数据模型)
  → fetcher/price.py (价格获取)
  → fetcher/index.py (指数获取)
  → fetcher/fund.py (基金数据获取)
  → fetcher/industry.py (行业分类)
  → providers/* (各数据源 API 实现)
  → cache/ (缓存读写)
    → core/market_hours.py (交易时段感知 TTL)
    → core/registry.py (TTL 默认值、缓存分组)

cache/operations.py (缓存操作共享层)
  → cache/ (缓存引擎核心)
  → providers/akshare_extras.py (盈利预测/资金流向/分红)
  → fetcher/industry.py (行业分类)
  → fetcher/fund_manager.py (基金经理)
  → fetcher/fund.py (基金业绩)
  → fetcher/price.py / index.py (持仓缓存)

report/orchestrator.py (报告编排层)
  → report/market_value.py (行情获取)
  → fetcher/index.py (指数)
  → report/penetration.py (资产穿透)
  → report/history_snapshot.py (持仓快照)
  → report/portfolio_history.py (历史走势)
  → report/news_correlation.py (新闻关联)
  → llm/generators_orchestrator.py (LLM 编排)
  → report/html_writer.py (HTML 管线)
  → report/excel_generator.py (Excel 管线)
  → config/ (开关配置)
  → core/registry.py (报告模块注册)

report/excel_generator.py (Excel 编排器)
  → report/excel_module_loader.py (模块动态加载)
  → report/excel_sheet_factory.py (页签创建/可见性)
  → report/*.py (各页签写入器)
  → report/excel_writer.py + styles.py
  → report/data_status.py (降级状态)

report/html_writer.py (HTML 编排器)
  → report/html_builders.py (数据构建器)
  → report/html_renderers.py (Markdown→HTML)
  → report/html_jinja_env.py (Jinja2 环境)
  → report/html_save.py (文件写入)
  → tmpl/report_template.html (Jinja2 模板)
  → report/data_status.py

llm/ (LLM 集成)
  → llm/generators_orchestrator.py → skeleton.py → api.py → api_base.py
  → llm/prompts.py / fingerprint.py / pricing.py / session.py
  → cache/ (LLM 结果缓存)

qa/ (报告对话式追问，依赖方向 qa → llm 单向)
  → qa/context.py → 报告 HTML 文件（只读，零取数）
  → qa/session.py → llm/api.py (call_llm) / llm/markdown.py / llm/fact_checker.py
  → web/handlers.py::_handle_report_qa_ask (POST /api/qa/ask 开关门与校验矩阵)

tui/handlers_*.py (TUI 命令)
  → orchestrator.py 或 cache/operations.py (委托业务逻辑)
  → report/progress.py (TuiProgressReporter)

config/ → core/registry.py
core/code_utils.py → 各 fetcher/report/llm 模块（跨层依赖，无环）

web/ (Web 服务层，薄入口)
  → web/server.py (启动入口：端口探测 + output_dir 写锁检测 + init_config)
  → web/app.py (Flask 工厂 → web/handlers.py 注册路由)
  → web/runs.py (RunManager 单 worker 串行队列，模块单例)
  → web/upload.py (上传校验/原子落盘/TTL 清理 → core/reader.py 预检)
  → web/progress.py (WebProgressReporter → report/progress.py 基类)
  → report/orchestrator.py + cache/operations.py (报告与缓存共享层)
  → config/ / core/registry.py (配置与注册)
```

[↑ 回到顶部](#目录)

---

## 8. 架构设计约束

本节定义系统架构层面的**设计约束**。所有新增或修改的代码必须遵守，违反即视为架构违规。
约束按职责域分组，每个约束包含：设计目的（为何存在）、违反后果（不遵守的影响）、适用范围（哪些模块/场景受约束）。

> **约束外参照（语义命名纪律）**：除上表 C1~C29 编号约束外，**语义命名纪律**以 [「功能语义命名表」](#67-功能语义命名表) 为唯一现状基准——代码/配置标识符（函数/变量/模块/config 键）必须与表中语义 slug 一致，禁止用任务代号（`plan-N`/`rf-N`/系列代号）命名；新增功能先定语义名再设计。该纪律属全局代码卫生，与编号约束并列遵守，由双脚本强制：`scripts/check-code-traces.py --ci`（负面禁止 IDENT/CODE）+ `scripts/check-semantic-index.py --ci`（正面双向校验本表与代码一致）。

> **约束外参照（文档与实现一致性纪律）**：除上表 C1~C29 编号约束外，**文档中的事实断言**（章节表与数量、功能开关表与分组计数、默认值表、LLM 缓存 TTL 行、TUI 面板编号、目录树、项目统计表）必须与代码/配置文件/文件系统一致，由 `scripts/check-doc-drift.py --ci` 强制（逐项对账，`changelog.md`/`review-findings.md` 与版本快照类文档按设计豁免）；历史痕迹类约束另由 `scripts/check-doc-traces.py --ci` 强制。

> **约束外参照（脚本结构）**：`scripts/` 顶层只放可直接运行的入口；共享库进 `_shared/`（`checklib.py` / `traces_common.py`），单入口实现包用 `_<语义名>/`，评测实现包用 `_eval_<x>/` 与 `eval-<x>.py` 对应（详见 `scripts-reference.md`「命名约定」的结构约定）。
>
> **约束外参照（脚本 CLI 契约）**：`scripts/` 下的检查脚本统一 `-v/--verbose` + `--ci`（仅输出 `文件:描述`）与退出码语义（0=通过 / 2=发现 finding，`check-code-traces.py` 保留 HIGH=1、LOW=3 分级）；共享设施集中在 `scripts/_checklib.py`（CLI/输出/路径/文档区间解析）；历史痕迹检查内部实现拆在 `scripts/_traces_code/` 包内（共享排除模式在 `exemptions.py`，`_shared/traces_common.py` 已并入其中删除）；检查脚本内部实现普遍拆 `前置横线包`pattern（`_doc_drift/` / `_traces_code/` / `_traces_doc/` / `_test_runner/` / `_eval_halluc_sampler/`，入口仅留 CLI 与原面 re-export）；连通性探测统一入口 `scripts/probe.py`（target registry，实现在 `scripts/_probes/`，新探针登记即用）；发布编排分步 CLI `scripts/release.py`（check/prepare/refresh/evolution/gate/publish/devbump，每步独立可审阅、失败即停，内部实现同为入口薄 CLI + 单模块）。

> **约束外参照（测试有效性纪律）**：测试用例不得是「死用例 / 无断言 / 完全重复 / 自证用例」——分别指：pytest 永不收集或同名覆盖的用例、没有任何断言（也不经含断言的同类辅助方法）、函数体与参数装饰器归一化后彼此完全一致的用例、以及 patch 掉被测函数后又把其 `return_value` 断言回原值的用例。由 `scripts/check-test-redundancy.py --ci` 强制；删除/合并用例后须同步刷新 `test-coverage.md` 与 `folders.md` 计数（`check-doc-drift.py --with-test-count` 兜底）。

### 8.1 数据获取层约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C1** | **代码类型判定中心化** — 所有资产代码类型判定必须使用 `core/code_utils.py` 提供的函数，禁止任何模块自行实现判定逻辑 | 系统 20+ 处需要判断资产类型（A 股/ETF/基金/QDII/港股/债券等），分散判定导致代码前缀知识散落，"魔法判定"遍地，新增资产类型时需全局搜索替换 | 代码评审不通过；新增资产类型时遗漏大量散落判定点 | 所有涉及代码类型判定的模块（fetcher/、report/、llm/、config/ 等）；含「按代码前缀分类资产类型」与「判定代码是否合法」两类判定，一律复用 `core/code_utils.py` 的判定函数，不得自建前缀表或白名单 |
| **C4** | **会话级 API 复用** — 同次会话内同一 API 返回的数据必须通过 `DataSourceRegistry.session_cache` 复用，禁止重复 HTTP 请求 | 避免同一资产在多个模块中重复请求相同 API 数据，降低 API 限频风险，提升性能 | API 调用量膨胀、触发限频、报告生成时间增长 | 所有通过 Provider 获取数据的模块 |
| **C5** | **HTTP 客户端统一** — 所有 HTTP 请求必须使用 `core/http_client.py` 工厂方法创建客户端实例 | 统一 SSL 配置、超时策略、连接池管理；防止各模块自行构造 request 导致配置散落、连接池泄漏。该工厂同时是**数据源记录-回放（cassette）的唯一注入点**（§2.6）：绕过工厂自建客户端的 provider 不受回放替换，回放用例会**真实联网并静默通过**——离线保证随之失效 | SSL 配置不一致、连接泄漏、重试策略不统一；绕过工厂的请求使 cassette 回放静默失效（测试实际联网而无人察觉） | 所有发起 HTTP 请求的模块（providers/、llm/） |
| **C6** | **Provider Chain 必经** — 大多数数据获取必须通过 `fetch_with_fallback()` 走 Chain 路由，不得直接调用 Provider 函数 | 跳过 Chain 直接调用 Provider 会导致熔断器不被激活（故障后无冷却恢复）、fallback 链路断路（某 Provider 失败时不会自动递补）、日志审计缺失 | 熔断器失效、fallback 断路、故障记录缺失 | fetcher/ 各模块（例外：index.py 直调 Provider 的双链路 fallback 硬编码，熔断器不适用于指数场景）；report/ 与 analysis/ 层取估值/行业等外部数据必须经 fetcher 网关入口（如 `fetcher/industry.py::fetch_valuation_fields`），不得 import `providers.*` 直连 |
| **C24** | **凭据值不落日志与产物** — 需要凭据的数据源必须经 `core/datasource_credential.py` 登记声明（源标识 + 环境变量名 + 申请地址），凭据值只从环境变量读取；对外一律只暴露「环境变量名 + 是否就绪」，**凭据值永不落日志、永不写入报告/缓存**。未就绪的源由链路主动跳过并给出「缺什么、去哪申请」，不得当作「源不可达」反复重试或计入熔断 | 凭据一旦出现在日志/报告/缓存中，即随日志文件、报告产物、问题反馈与截图外泄，且事后无法区分「是否已泄露」；把配置级缺失（key 没配）混入可用性统计，会污染数据源可用性矩阵的语义——用户看到的是「源不稳定」而非「你没配 key」 | 凭据泄露（日志/报告被复制、上传、粘贴即泄露）；用户据失真的可用性矩阵排查错误方向，反复重试注定失败的请求 | providers/ 各数据源、`fetcher/chain.py`（未就绪主动跳过且不计熔断）、`core/check_sources.py`、`core/doctor.py`、`core/datasource_credential.py`（唯一声明点） |

### 8.2 缓存层约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C2** | **缓存统一管理** — 所有持久化缓存必须通过 `cache/` 子包的 `get()`/`set()` 接口读写，禁止直接操作 `data/cache/` 文件系统 | 直接操作文件系统导致 TTL 失效（缓存无法感知过期时间）、分组清理遗漏（菜单命令无法清除对应缓存）、路径穿越隐患 | 缓存不一致、TTL 失效、分组清理遗漏、路径安全风险 | 所有读写 data/cache/ 的模块 |
| **C3** | **缓存原子写入** — 所有缓存/配置文件写入必须使用 `tempfile.mkstemp` + `os.replace` 原子写入模式；**实现收敛到唯一原语** `core/atomic_write.py`（`write_text_atomic` / `write_json_atomic`，成败如实布尔返回），各调用点不得自留第二份 mkstemp + os.replace 拷贝 | 直接覆写文件在断电/崩溃时产生半写损坏文件，导致后续读取解析失败；多份拷贝各自演化会让「原子」语义在其中一份上悄悄失效（修了 A 漏了 B），且调用点无法据成败判定后续动作（如写失败后误删唯一数据源） | 半写文件损坏、数据不完整、崩溃后无法自恢复；迁移类逻辑在写失败时误删数据源 | cache/ 子包（`cache/_io.py`+`_store.py`）、config/ 子包（`config/_core.py`）、`core/atomic_write.py` 及其调用方（`core/jsonl_store.py`、`core/provider_registry.py`、`report/history_snapshot.py`、`config/features.py`、`analysis/_silence.py`、`analysis/circuit_breaker_wrapper.py`、`report/data_status.py`）。例外（契约相反，有意不合并）：`cache/` 需 gzip 分支与文件锁；`config/_core.py::_atomic_write` 契约是「失败即抛且保留异常类型」（`init_config()` 的 `except PermissionError` 并发容忍分支、TUI 的权限不足提示依赖类型） |

> **缓存载荷语义版本（词条外，非编号约束）**：当修复改变缓存**载荷字段的含义**而非键结构时，不得只靠 TTL 自然过期——旧条目在 TTL 内会被新代码误读，使修复在缓存未过期的机器上完全失效（已发生：QDII 联接穿透修复被 7 天旧 `fund_hold_*` 条目遮蔽）。规则：生产者在载荷里盖语义版本字段，读侧把「版本不符」当未命中（丢弃重取），判据接在**每一处读缓存接缝**（含批量缓存预检与过期降级）。通用原语：`fetch_with_fallback(cache_validate=...)`。

### 8.3 报告层约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C7** | **报告序号与显示名不可硬编码** — 报告 19 个模块的章节顺序/可见性由 `core/registry.py` 的 `_REPORT_SECTION_DEFAULT` 注册表驱动，页签显示名由同文件的派生视图 `_REPORT_SHEET_NAMES` 驱动（键集 = 章节注册表减 LLM 章差集 `_LLM_SHEET_NAME_KEYS`：非 LLM 章键值由注册表条目派生、LLM 章显示名显式登记，值同源由测试锁定，页签名一律经 `get_report_sheet_name()` 取用），均支持 `config.json` 自定义覆盖 | 硬编码序号使得用户无法通过配置调整报告章节顺序，且新增/删除模块时需要全局修改序号；显示名散落在写入层则重命名页签必须全局搜索，两处清单一旦不同步便出现「配置里叫一个名、页签上叫另一个名」 | 序号配置失效、用户自定义顺序不生效；页签显示名与注册表/配置脱节 | report/ 编排器与写入层（excel_generator.py、html_writer.py、fund_style_classify.py 等）；任何写入页签名的模块均须经 `get_report_sheet_name()`，不得直接写中文字面量 |
| **C10** | **新闻召回策略可配置** — `per_source` 每源获取数量必须与 `news_top_count` 最终截取数量解耦，`per_source` 动态计算为 `max(500, news_top_count × 2)`（单源实现 `fetcher/news.py::news_fetch_limits`，调用方不得各自内联），不可写死 | 固定值会导致去重后候选新闻不足，最终截取数不满足用户配置 | 新闻候选不足、用户配置不生效 | `providers/news_aggregator.py` + `fetcher/news.py` |
| **C14** | **渲染期数据不可写入模块级全局变量** — 所有渲染期数据（如 `section_visible_dict`）必须通过模板 `render()` 的 context 参数传递，不得写入 `_ENV.globals` 或模块级 dict | 模块级全局变量在并发/多次渲染场景下产生状态污染，且难以追踪数据流向 | 并发不安全、渲染状态污染、数据流向不可追踪 | report/html_writer.py、模板渲染相关模块 |
| **C19** | **pipeline_data Schema 契约** — 所有 pipeline_data 键必须先在附录 H（pipeline_data Schema 定义）中预定义类型、可选性、写入/消费模块后，才能在代码中使用该键 | 无 schema 定义的键在管线中类型不匹配时引发难调试的 KeyError，且多人并行开发时互相不知道对方新增的键 | 违反时集成测试不通过 | report/orchestrator.py、所有向 pipeline_data 注入数据的模块 |
| **C20** | **HTML 图表图下说明强制** — HTML 报告中每张图表下方必须渲染图下说明（`.chart-caption`），明确标注该图表是什么、用途是什么；说明必须跟随对应图表 canvas 的渲染分支一同出现（图表有数据 → 说明出现，图表空数据 → 说明不出现） | 图表无说明时用户无法快速理解该图的含义与用途，可读性下降；屏幕阅读器等无障碍场景无法获得图表意图 | 代码评审不通过；图下说明缺失或与图表渲染分支不一致 | 模板 `report_template.html`（所有 chart canvas 渲染处，含净值/回撤/资产构成/行业分布/穿透 TOP10/量化指标 radar 共 6 处）、`chart-*` 前端图表模块 |
| **C25** | **时间距离一律以交易日计** — 凡「距今多久」用于判定**数据新鲜度/停更/跳空/持仓期/观察期**的场景，一律以**交易日**计数，禁止用自然日差；交易日来源唯一为 `core/trading_calendar.py`（`count_trading_days_elapsed` / `get_last_trading_day` / `get_prev_trading_day`），各模块不得自建日历或另写自然日差。自然日差仅可用于本身就以自然日定义的量（如静默期天数、缓存 TTL） | 交易日与自然日在长假/周末处相差十数个自然日：按自然日差判定，长假前后的两个相邻交易日会被判为「延迟」「停更」「数据跳空」；在非交易日运行报告时，运行时刻与最近交易日天然相差一个自然日，会把正常的 T-1 净值误报为滞后 | 报告在长假后/非交易日运行即出现成批假告警（数据质量「延迟」、因子被误剔除、K 线被误判跳空、新仓观察期被误判已过），用户据假告警排查错误方向 | `core/trading_calendar.py`（唯一实现，`report/market_value.py` 按原公共名重新导出保持既有导入路径）、`fetcher/chain.py`（跳空判定）、`analysis/style_factor_regression.py`（停更因子剔除）、`analysis/rebalance.py`（新仓观察期）、`analysis/whatif_backtest.py`（回测窗口折算）、`core/data_freshness.py` 及其消费方（报告「数据质量」维度、提示词新鲜度基准） |
| **C22** | **报告管线实验挂载点集中** — 接入报告管线的实验功能必须经 `report/_experimental_seams.py` 的挂载点函数接入，禁止在 `_generate_report_full` 内联 `try/except` 守护；所有挂载点共享同一契约「**实验功能自身的异常绝不中断报告主链路**」（降级为一条告警 + 一条异常日志），且**挂载点工序顺序固定**——结算先于 LLM 拉取、质量横幅晚于决策登记、信号沉淀晚于 LLM 生成、景气度框架诊断晚于基本面契约与历史走势就绪 | 守护判据复制即漂移：四处内联 try/except 时改一处必漏三处（与缓存指纹「读写两份拼接」同一病根）；顺序调换会使当次教训读不到新结算结果、横幅改写文本污染决策表解析、尾部风险等迟到键漏采 | 实验功能异常中断整条报告链路；实验结论静默失真（结算/沉淀漏采、解析污染）且无异常可循 | `report/_report_generation.py`（唯一调用点，仅按序调用挂载点）、`report/_experimental_seams.py`（唯一守护实现，四条挂载点在 `_generate_report_full` 工序内、`record_prosperity_diagnosis` 在两条 HTML 生成路径内）、所有向 `pipeline_data` 注入数据的实验功能 |

### 8.4 LLM 集成层约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C9** | **LLM 模块注册** — 新增 LLM 分析模块时，必须在 `llm/_llm_dispatch.py`（`_build_module_fns` 返回的 `_MODULE_FNS` 字典）和 `core/registry.py` 的 `DataModuleDef` 注册表中同时注册（详见 `llm-technical.md` §12）；注册项必须有真实调用方——模块运行所需配置项、显示名等同样由中央注册表提供，不在别处建副本；编排注册仅对确经编排线程池调度的模块生效，无人调用或无独立调度语义的注册分支属注册漂移，应移除而非保留 | 仅在 orchestrator 注册会导致缓存/TTL/统计遗漏；仅在 registry 注册会导致编排调度遗漏；无人调用的注册分支会误导后续维护者按「已被编排」去推断调度与并发行为，并让统计口径把未编排项计入 | LLM 调度遗漏、缓存 TTL 未定义、用量统计缺失；显示名/配置项副本漂移；统计口径失真 | llm/ 包 + core/registry.py + config/（LLM 模块相关默认值） |
| **C17** | **Multi-LLM Provider Chain** — 所有 LLM API 调用必须通过 Provider Chain（`strategy.py` + `api.py`）路由，`call_llm()` 返回 `(result, usage, provider_name)` 三元组，provider_name 记录实际使用的 Provider 条目名（详见 `llm-technical.md` §5.2） | 手动切换 Provider 导致配置散落、失败无法递补、Provider 名称不可追踪 | API 调用不经过 Chain → 无法自动递补、Provider 名称缺失 → 缓存键冲突、用量统计不准确 | llm/api.py、llm/skeleton.py、llm/strategy.py |
| **C18** | **credentials_ref 凭据分离** — API 凭据（api_key）必须通过 `llm_key.json` 的 `credentials_ref` 引用，禁止在 `llm_providers.json` 中直接存储敏感凭据；`credentials_ref` 为**必填**、内联 `api_key` 为**硬校验拒绝**（非仅告警，详见 `llm-technical.md` §5.3） | 凭据与路由配置混存导致凭据泄露风险；凭据变更时需同时修改两份配置 | 凭据泄露风险、凭据变更需多处修改、凭据复用困难 | data/config/llm_providers.json、data/config/llm_key.json、config/_core.py、config/_llm_providers.py、llm/api.py |
| **C21** | **LLM 模块缓存指纹与缓存键唯一事实来源** — 各 LLM 模块的缓存指纹必须由 `llm/module_fingerprint.py` 的 `MODULE_FINGERPRINT_BUILDERS` 统一构造；**完整缓存键的键尾也必须两侧共用同一函数**（chain 模式的 `_{provider}` 后缀由 `skeleton._build_provider_cache_key` 唯一构造，预检侧 `_compute_module_cache_info` 同样调用它，禁止自行拼字串）。写侧（`generators.py`/`generators_singletons.py` 各生成器）与预检侧（`generators_orchestrator.py::_compute_module_cache_info`）只允许调用同一构建函数，禁止任一环节自行拼接指纹片段；指纹的覆盖判据是「该模块的提示词实际承载了哪些入参」——提示词正文里出现哪一段（含 `pipeline_data` 派生的环比差异段、数据质量降级段），对应入参就必须进指纹；辩论三键（白脸/黑脸/综合）仅写侧使用、不进 `MODULE_FINGERPRINT_BUILDERS`，但构造同样由本模块的函数提供，综合键须覆盖白脸/黑脸两段完整正文而非提示词模板文本（详见 `llm-technical.md` §13.1） | 指纹决定缓存键，缓存键必须读写同源。两侧各自拼接时，任一侧新增一个影响提示词的入参/开关后缀而未同步另一侧，两侧计算结果即永久不等——写侧照常写入，预检侧却永不命中，表现为「开关/参数看似生效但每次仍全量调用 LLM」的静默性能退化与日志噪声，且因无异常而极难察觉 | 预检缓存恒不命中 → 每次报告重复调用 LLM（费用与耗时翻倍）、日志噪声；反向漂移则命中过期键导致提示词开关形同虚设 | llm/module_fingerprint.py（唯一构造点）、llm/generators.py、llm/generators_singletons.py、llm/generators_orchestrator.py |

### 8.5 基础设施约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C8** | **日志统一** — 所有模块必须使用 `logging.getLogger("invest")` 获取日志器，禁止直接使用 `print()` 输出运行时诊断信息 | 统一日志名称使日志过滤、级别控制、格式管理集中生效；`print()` 无法控制日志级别，污染 stdout | 日志碎片化、日志级别失控、`print()` 干扰输出流 | 全模块（交互式 print 如进度提示不受此限）；机检：`check-code-traces.py` 日志统一支路（交互呈现层白名单） |
| **C15** | **控制台日志着色** — WARNING 级别使用黄色输出、ERROR 级别使用红色输出；当 `NO_COLOR` 环境变量设置或输出非 TTY 时自动降级为无颜色 | 着色提升控制台日志的辨识度，便于快速定位告警和错误；降级保证日志导出、管道重定向时无转义字符污染输出 | 日志可读性降低、非 TTY 环境下转义字符污染 | `core/logger.py`（_ColoredFormatter） |
| **C23** | **功能开关注册表唯一事实来源** — **全部**功能开关的枚举、显示名、说明、分组、默认值与产物影响必须来自 `config/features.py` 的 `feature_switch_registry`（`_FEATURE_FLAGS_DEFAULT` 是它的派生投影，非独立登记点）；TUI 功能开关面板、Web 配置面板、CLI `--experiment` / `--feature` 取值校验与提示文案、用户文档与管理文档的开关清单**一律由该注册表驱动**，禁止任何渠道层另写一份清单 | 渠道各写清单时，新增/改名/删除开关必漏改某渠道——用户在该渠道看不到、改不了，或文档与实际开关对不上；清单是静态字面量，编译期与运行期均无任何提示，只会在用户报障时暴露。**可见性若与「是否实验项」绑定**，则转正（默认值改 `true`）会连带摘掉面板入口，关闭途径只剩手改 `features.json`——可见性由**分组属性**表达，与默认值解耦 | 开关在部分渠道缺失或名称不一致；文档承诺的开关在界面中不存在（或反之）；新增开关的接入成本从「改一处」膨胀为「逐个渠道找清单」；转正即失去界面入口 | `config/features.py`（唯一注册点）、`tui/`（功能开关面板）、`web/`（配置面板）、`cli/`（`--experiment` / `--feature` 校验与报错提示）、`docs/manuals/` 与 `docs/managements/` 的开关清单 |
| **C16** | **路径绝对化** — 配置层输出的路径型键（`holdings_dir`、`output_dir`、`llm_key_file`、`llm_providers_file`、`llm_settings_file`）必须为绝对路径，在 `get_config()` 返回前经 `_absolutize_paths()` 统一转换；下游消费者不得依赖 CWD | `tui/tui.py`/`cli/cli.py` 去掉了 `os.chdir`，相对路径无法被正确解析 | 路径查找失败、配置文件/持仓文件/报告输出找不到 | `config/_core.py`（转换点），所有消费路径型配置的模块 |
| **C26** | **重试与退避唯一原语** — 凡「失败后重试」必须经 `core/retry.py`（`RetryPolicy` 策略 / `is_transient_exception` 瞬时判据 / `retry_transient` 执行器），禁止各模块自建重试循环与退避算式；各来源差异只用策略参数表达 | 退避数值与「可重试」口径各写一处必然漂移：最坏时延无法估算、策略调整需改 N 处、测试钉住的次数与等待量随之失真 | 全部「失败后重试」路径：数据获取层（Provider Chain 同源重试、provider 连接级重试、akshare 超时重试、HTTP 429 退避）+ LLM 调用链（`llm/api_base.py` 的 503/超时/网络重试（429/403 归 quota 终态不重试），退避用显式序列策略表达；其**失败分类**（内容级/配额级判定）与终态副作用仍属 LLM 层职责，见 §5.4） |
| **C27** | **间隔节流唯一原语** — 凡「两次请求至少间隔多久」必须经 `core/throttle.py`（`RateLimiter` / `interval_delay` / 一次性等待 `wait_interval`），禁止自建「间隔 + 睡眠」与抖动算式 | 同一约束在数据层/调度层/LLM 层各写一份 → 抖动幅度与等待语义不一致；通用原语若住在某一上层模块，会被其他层反向依赖（层次倒置） | 数据源 qps 限速、`batch_rate_limit`、LLM 端点级节流（`pacing`） |
| **C28** | **大文件红线体系（主程序/脚本/测试）** — 单文件行数按域执行固定红线：主程序（`src/python/`）> 1000 行、脚本（`scripts/` 递归含包内子模块）> 1000 行、测试（`src/test/`）> 1200 行即 finding；警戒区（`-v` 清单：主程序 700 / 脚本 600 / 测试 900，`__init__.py` 薄壳 200）为可选优化区间且即登记线，`-v` 另按「行数 × 近 90 天改动次数」输出拆分优先级；超限必须拆分，或在 `check-file-length` 的 `EXEMPTIONS` 登记并与 review-findings 挂账同步 | 行数无红线时文件无限膨胀（`scripts/` 未入守护域时 `eval-factor-zoo.py` 达 1595 行而无发现渠道）；阈值只写在文档不进守护脚本会改一处漏一处；无警戒区则只能在破线后才察觉，拆分时机失去观察缓冲 | 所有 py 源文件：`src/python/`、`scripts/`（含包内子模块）、`src/test/`；阈值与清单由 `scripts/check-file-length.py --ci` 单源强制（`_LIMIT_BY_KIND` / `_WARN_BY_KIND`），口径同步 developer-guide「文件膨胀阈值」表与 review-findings 文件膨胀登记表 |
| **C29** | **TUI 分档只改版式不改语义** — `layout_tier` 的 wide/medium/narrow 分支只允许改**版式与密度**（列宽/盒线/折行/图例详略/重绘机制），不得改**按键语义、反馈有无、写路径可见性**：同一按键在各档必须产生相同的语义动作与可观察反馈（执行/退出/选中移动/单行提示），分档至多改变反馈的呈现方式 | 分档分支改语义曾三次造成用户可见缺陷：写路径窄屏不重绘（切换无结果）、方向键在窄屏解析漂移为孤 Esc（误退程序）、窄屏导航被整体删除（按键无反应）；语义随宽度漂移违反「同键同果」预期，且每档分支都是独立回归面 | `src/python/tui/` 全部 `layout_tier`/`narrow` 分支点（主循环、菜单渲染、各面板）；守护 = `test_tui_menu.py::TestTierSemanticParity`（同按键两档同语义/同反馈）+ `_print_hint` 单行反馈原语；**本次重构后**导航/派发控制流单源于 `tui/panel_runtime.py::panel_loop`——同一读键→导航→派发→反馈循环全列表面板共用一份实现，「同键同果」由构造性成立（分档只改 render 版式、不改派发），从「测试逐处兜底」升级为运行时单源** |

> **C14 例外：env 初始化期注册（非渲染期）** — `_ENV.globals` 与模板过滤器仅允许在 `report/html_jinja_env.py` 的**工厂初始化期**（进程/工厂单次建立）注册为**无状态纯函数**（如 `profit_color`、`price_type_color`、`money`、`fmt_bps`、`dt`——只依赖入参生成 CSS 变量表达式/格式化文本）。约束禁止的是**渲染期数据**（section 可见性、业务字典等随每次运行变化的值）写入全局；过滤器注册与 Jinja 环境构建属于模板基础设施装配，不构成渲染态状态污染（并发/多次渲染下各 `render()` 仍只经 context 传数据）。

> **C28 阈值调整记录（2026-10-23）**：按实测分布把「警告 / 登记 / 红线」三套数字收敛为两套——警告线即登记线（主程序 500 → 700、脚本 400 → 600、测试 800 → 900），红线维持 1000/1000/1200 不动：实测三域最大文件 734 / 906 / 999，红线并未误伤，真正的问题是 40 个主程序 + 22 个测试文件长期挂在旧警告线以上、warning 清单与 rf-829 登记表各说各话（表内还留着 477 行早已回落的条目）。同时新增 `__init__.py` 薄壳独立警告线 200 行（包标记/门面应收薄），并在 `-v` 输出「行数 × 近 90 天改动次数」优先级排序（改得越勤越先拆）；review-findings P3 表按该排序重建（入表线 = 警告线）。
> **C28 阈值定档记录（2026-10-09）**：三域阈值一次定档——主程序 800 → 1000（实测 343 文件中位 226 / P90 535 / 最大 783，阈值须给内聚大文件留出拆分触发缓冲；警告线 500 维持观察密度）、`scripts/` 纳入守护（实测 P90 520，警戒 400 / 红线 1000，与主程序同值统一口径）、测试 800/1200 维持。同批把域内最大单文件 `eval-factor-zoo.py`（1595 行）按「评测核心 / 阶段编排 / 判定书」拆为 `scripts/_eval_factor_zoo/` 包（入口仅留 CLI 与原面 re-export，既有测试零改动）；`EXEMPTIONS` 保持空集（拆分后无挂账破线）。

### 8.6 测试约束

| # | 约束 | 设计目的 | 违反后果 | 适用范围 |
|:---|:-----|:---------|:---------|:---------|
| **C11** | **测试标记强制** — 新增/修改的测试用例（测试类或测试方法）必须标注对应的 pytest marker（如 `@pytest.mark.unit_providers`），marker 定义在 `src/test/conftest.py` 的 `pytest_configure` 中 | 未标记的测试用例无法被分层测试命令精确选择，也无法纳入回归/验证门禁范围 | CI 门禁不通过、测试分类失效 | src/test/ 所有测试文件 |
| **C12** | **边缘测试文件隔离** — `@pytest.mark.edge` 标记的测试用例必须放置在 `*_edge.py` 文件中，不得与普通测试混放在同一文件 | edge 场景测试对运行环境有特殊要求（预期失败、网络不可达等），混放会导致普通测试运行被 edge 场景的 fixture 干扰 | 测试收集失败、`pytest_collection_modifyitems` 校验报错 | src/test/ 边缘测试文件 |
| **C13** | **测试敏感路径隔离** — 运行测试时不得修改用户的配置文件（`data/config/`）、持仓文件（`data/holdings/`）、机器本地状态（`data/state/`）等敏感数据；`conftest.py` 的 `_isolate_sensitive_paths` autouse fixture 会自动将 `config.json`、`local_state.json`、缓存目录等重定向到临时目录 | 测试污染用户数据导致不可逆的配置丢失或持仓文件损坏 | 用户数据被污染、配置丢失 | src/test/ 所有测试用例 |

[↑ 回到顶部](#目录)

---

## 9. 导入面所有权

> **单一 owner 规则**：一个公开符号只有一个实现模块；包 `__init__` 只做已文档化公共 API 的门面，私有实现模块不跨包导入。测试为验证门面行为可 patch 门面，其余 patch 点必须指向实际查询/调用该符号的模块。

| 符号 / 公共面 | owner | 兼容/门面路径 | 主要消费方 | 处置 |
|:--|:--|:--|:--|:--|
| `get_config` / `set_config` / 章节可见性 | `config/_core.py` | `config/__init__.py` | 全渠道 | 公开门面保留；私有缓存变量不再导出 |
| `get_llm_config` / `validate_config` / LLM 默认值 | `config/_llm_settings.py`、`config/_validation.py`、`config/_llm_settings_defaults.py` | `config/__init__.py` | llm / web / tui / analysis | 公开函数保留；私有实现按域导入 |
| `get_cache_path` / `get/set/clear` | `cache/_paths.py`、`cache/_store.py` | `cache/__init__.py` | core / 报告 / 渠道 | 仅公开入口跨包；`_io`/`_store` 私有 |
| `is_a_share_code` 等资产判定 | `core/code_utils.py` | — | analysis / fetcher / report | 判定与派生量分离；派生量走 `core/code_symbols.py` |
| 派生符号（交易所前缀/代码归一） | `core/code_symbols.py` | 原 `code_utils` 转发已删除 | fetcher / providers / report | 调用方直接导入 owner |
| 日志与缓存自检探针 | `core/doctor_logs.py` | `core/doctor.py` 仅入口调用 | cli / tui / web | 私有探针不再经 `doctor` 转发 |
| 缓存刷新族 | `cache/_cache_refresh.py` | `cache/operations.py` 编排入口 | tui / cli / web | 刷新函数由编排层内部导入；测试直接 patch owner |
| 量化指标算法 | `analysis/metrics_returns.py`、`analysis/metrics_risk.py` | `analysis/metrics.py` 聚合 `compute_all_metrics` | report / analysis | 公开聚合保留；私有 `_t_cdf` 等走 `_math_utils` |
| 景气度输入/权重 | `analysis/prosperity_inputs.py` | `analysis/prosperity_scoring.py` 评分 | report / analysis | 模块名去下划线，跨包直接导入 |
| provider 共享原语/失败原因 | `providers/utils.py` | 原 `providers/utils.py` 已改名 | fetcher / providers | `set/take/clear_last_reason` 经公开模块 |
| 基金评级 / 持仓区块 / HTML 状态 | `report/_fund_rating.py`、`report/_holdings_detail_blocks.py`、`report/html_writer_status.py` | `report/fund_performance.py` 等入口 | report / tui | 私有实现只在报告包内使用；测试 patch owner |
| LLM 响应解析 | `llm/_api_responses.py` | `llm/api_base.py` 公共 API | llm / report | 公共常量/函数保留；内部 helper 直接导入 owner |
| Web 生成 / 健康路由 | `web/run_generation.py`、`web/handlers_health.py` | `web/handlers.py` 仅路由聚合 | web / tests | 测试 patch 指向 owner；门面不再转出私有实现 |

**登记例外**（保留理由见代码注释与 `check-import-surface` 观察期）：

- `analysis/__init__.py`、`core/registry.py`、`llm/__init__.py`、`llm/fact_checker/__init__.py`：包级公共聚合面，`__all__` 只列公共 API；其中 `noqa: F401` 为门面再导出。
- `providers/sina.py` 的 `fetch_kline` / `fetch_index_kline`：`fetcher/chain_incremental.py` 按 provider 名动态 `getattr`，属动态调度面而非普通转发。
- `web/scheduler.py` 的 `normalize_schedule_block` / `validate_schedule_block`：Web 面板与测试共用入口，实现在 `config/_scheduler.py`。
- 测试对私有模块的导入/patch：只允许指向 owner（如 `cache/_paths.py`、`report/_fund_rating.py`），不得再经转发模块。

**存量导入环（不新增）**：当前包级顶层导入环 3 组，均已复核为有意设计，不再扩大：

- `config` ↔ `config._core` / `_config_api` / `_llm_settings`：包门面公开 API 与内部实现互引，属公开面装配，不引入反向业务依赖。
- `core.doctor` ↔ `core.doctor_logs`：自检入口与日志/缓存探针分组互引，`doctor` 在模块底部延迟导入以避开导入期环。
- `llm.api` ↔ `llm._api_claude` / `_api_openai` / `_api_gemini`：API 分派根据 provider 名调用实现，实现共用 `api_base` 原语；新增 provider 时不得让实现反向导入 `llm.api`。

**`noqa: F401` 保留口径**：包级公共聚合面（`analysis/__init__.py`、`core/registry.py`、`llm/__init__.py`、`llm/fact_checker/__init__.py`）的公开 API 再导出；动态调度面（`providers/sina.py` 的 K 线函数供 chain 按 provider 名 `getattr`）；显式副作用/类型导入。新增 `noqa: F401` 须在行内写明理由；测试私有导入只允许指向 owner。

**机检**：`scripts/check-import-surface.py`（观察期，规则 compat-comment / private-all / cross-private / dynamic-target）；包 `__all__` 私有名、兼容注释、跨包私有导入当前均为 0。

## 附录

### 附录 A：目录结构

```
investor-review/
├── src/
│   ├── __init__.py
│   ├── python/                   # 源代码
│   │   ├── __init__.py
│   │   ├── startup_wizard.py    #   首次运行引导向导
│   │   ├── analysis/            # 业务分析计算层（再平衡、量化指标）
│   │   ├── cache/               # 缓存引擎（TTL/清理/统计/分组/IO）
│   │   ├── cli/                 # CLI 命令行模式入口
│   │   │   ├── __init__.py      #   子包标记，re-export cli 符号
│   │   │   ├── __main__.py      #   python -m 入口
│   │   │   └── cli.py           #   argparse + 共享层路由
│   │   ├── config/              # 配置管理（含 features.py + anonymizer.py）
│   │   ├── core/                # 核心基础设施
│   │   │   ├── __init__.py      #   子包标记
│   │   │   ├── ansi_colors.py   #   ANSI 颜色常量
│   │   │   ├── check_sources.py #   数据源健康检查（CLI/报告共享）
│   │   │   ├── circuit_breaker.py #  统一断路器网关
│   │   │   ├── code_utils.py    #   代码类型判定中心化
│   │   │   ├── constants.py     #   共享常量 + 项目根路径
│   │   │   ├── http_client.py   #   HTTP 客户端工厂
│   │   │   ├── retry.py         #   重试与退避唯一原语（策略/瞬时判据/执行器）
│   │   │   ├── throttle.py      #   按名最小间隔节流唯一原语（含抖动算式）
│   │   │   ├── logger.py        #   日志模块
│   │   │   ├── market_hours.py  #   交易时段判断
│   │   │   ├── models.py        #   数据模型
│   │   │   ├── perf.py          #   性能收集
│   │   │   ├── provider_registry.py # 数据源注册中心
│   │   │   ├── reader.py        #   持仓 Excel 解析
│   │   │   └── registry.py      #   中央注册表
│   │   ├── fetcher/             # 数据获取调度
│   │   ├── llm/                 # LLM 集成
│   │   ├── providers/           # 数据源提供商（各 API 封装）
│   │   ├── report/              # 报告生成
│   │   ├── schemas/             # 数据模式
│   │   ├── tmpl/                # HTML 报告模板
│   │   └── tui/                 # TUI 交互模式入口
│   │       ├── __init__.py      #   子包标记
│   │       ├── __main__.py      #   python -m 入口
│   │       ├── handlers_cache.py #   缓存管理命令
│   │       ├── handlers_config.py #  配置管理命令
│   │       ├── handlers_report.py #  报告生成命令
│   │       ├── tui.py           #   主循环入口
│   │       ├── tui_handlers.py  #   键盘/事件处理
│   │       ├── tui_keys.py      #   键盘输入封装
│   │       ├── panel_runtime.py  #   统一交互运行时（NavState/panel_loop，列表面板导航态单源）
│   │       └── tui_menu.py      #   菜单交互
│   │   ├── web/                # Web 浏览器模式入口
│   │   │   ├── __init__.py     #   子包标记
│   │   │   ├── __main__.py     #   python -m 入口
│   │   │   ├── app.py          #   Flask 应用工厂 + 路由注册
│   │   │   ├── handlers.py     #   API 处理（上传/运行/进度/产物）
│   │   │   ├── progress.py     #   WebProgressReporter 事件缓冲
│   │   │   ├── runs.py         #   RunManager 单 worker 串行队列
│   │   │   ├── server.py       #   启动入口（--host/--port/--config、端口 + output_dir 写锁检测）
│   │   │   ├── upload.py       #   上传校验、原子落盘、TTL 清理
│   │   │   ├── static/         #   前端资产（main.js / style.css）
│   │   │   └── templates/      #   页面模板（index.html）
│   ├── static/                   # 前端静态资产（Chart.js 本地 bundle + 图表初始化/导出/打印 + TOC）
│   └── test/                    # 测试（按标记分组）
│       ├── conftest.py          # pytest 配置 + 分层标记注册
│       ├── helpers.py           # 测试辅助工具
│       ├── unit/                # 单元测试
│       ├── integration/         # 集成测试
│       └── scenario/            # 场景测试
├── data/                        # 运行时数据（config/holdings/cache/state/snapshots）
├── reports/                     # 生成报告
├── logs/                        # 程序日志
├── docs/                    # 项目管理文档（含 managements/、plan/、manuals/）
├── scripts/                     # 启动/测试脚本
├── pyproject.toml
└── CLAUDE.md
```

### 附录 B：数据源一览

| 用途 | 链路方案 | Provider 文件 |
|:-----|:---------|:-------------|
| 场内 A 股/ETF 实时价 | 腾讯财经 → 新浪财经（双链路 fallback） | `tencent.py` / `sina.py` |
| 场外基金净值 | 东方财富 `api.fund.eastmoney.com`（主）→ 新浪财经 `hq.sinajs.cn/list=f_{code}`（跨厂商备源；东财内部另有 `fundf10.eastmoney.com` 兜底） | `eastmoney.py` / `sina.py` |
| 基金业绩排名 | 天天基金 JS 变量解析（直达） | `tiantian_ranking.py` |
| 基金持仓数据 | 天天基金 HTML 解析（直达） | `tiantian_holdings.py` |
| A 股指数 | 腾讯财经 → 新浪财经（双链路 fallback） | `tencent.py` / `sina.py` |
| 美股指数 | 新浪财经 → 腾讯财经（双链路 fallback） | `sina.py` |
| 财经新闻 | 5 源并行：新浪/东方财富/财联社/华尔街见闻/akshare | 各 `*_news.py` |
| 行业分类/概念板块 | 东方财富 push2（主）→ quotedata 回退 | `eastmoney_industry.py` / `eastmoney_industry_rest.py` |
| 机构盈利预测 | akshare 全量获取（直达） | `fetcher/akshare.py`（封装 `akshare_extras.py`） |
| 行业资金流向 | akshare 今日排名（直达） | `fetcher/akshare.py`（封装 `akshare_extras.py`） |
| 股票历史分红 | akshare 无参全量拉取后按代码过滤（直达） | `fetcher/akshare.py`（封装 `akshare_extras.py`） |
| 基金经理数据 | 天天基金 HTML 解析（主）→ 档案页回退 | `fetcher/fund_manager.py` |
| 无风险利率（Rf） | akshare `bond_zh_us_rate`（Sina 国债收益率，单值 + 历史序列双键）→ 手动配置兜底 | `fetcher/bond_yield.py` |
| 指数估值历史（PE/PB 月频，温度估值因子） | akshare 乐咕 `stock_index_pe_lg`/`stock_index_pb_lg`（单源，30 天旧缓存兜底） | `fetcher/index_valuation.py` |
| 个股/ETF 历史 K 线 | 腾讯财经 K 线 → 新浪财经 K 线（双链路 fallback） | `fetcher/chain_incremental.py`（`tencent.py` / `sina.py`） |
| 场外基金历史净值 | 天天基金 `pingzhongdata` → 东方财富净值分页 | `fetcher/chain_incremental.py` |
| 指数历史 K 线（A 股指数） | 腾讯财经 K 线 → 东方财富 push2his 指数 K 线 → 新浪财经 K 线 → 同花顺官方（需 key） | `fetcher/index.py` |
| 指数历史 K 线（美股指数） | 新浪财经 K 线 → 腾讯财经 K 线 | `fetcher/index.py` |

新闻数据处理模块：`news_aggregator.py`（聚合去重）、`news_correlator.py`（关联分析）、`news_keywords.py`（关键词提取）、`news_sources.py`（源元数据定义），均位于 `providers/` 下。

### 附录 C：缓存 TTL 明细

#### 行情/数据类

| 键名 | 文件名模式 | TTL | 盘中特殊 | 指纹 | 分组 |
|:-----|:----------|:---:|:--------:|:----|:-----|
| `price` | `price_{route}_{code}.json` | 24h | 交易时段 30s | — | preload |
| `index` | `index_{code}.json` | 24h | 交易时段 30s | — | preload |
| `news` | `news_{md5}.json` | 15 分钟 | — | 新闻源参数+关键词 | refresh |
| `sector_flow` | `sector_flow_{fingerprint}.json` | 15 分钟 | — | A 股+美股指数 | refresh |
| `rank` | `fund_perf_{code}.json` | 24h | — | — | refresh |
| `profit_forecast` | `profit_forecast_{fingerprint}.json` | 24h | — | A 股+美股指数 | refresh |
| `hold` | `fund_hold_{code}.json` | 7 天 | — | — | refresh |
| `industry` | `industry_{code}.json` | 14 天 | — | — | refresh |
| `sentiment` | `sentiment_dragon_tiger.json` + `sentiment_ladder.json` | 1h | — | — | refresh |
| `report` | `report_datasink_index_{symbol}.json` + `report_datasink_sections_{doc_id}.json` + `report_cninfo_index_*` | 24h | — | — | refresh |
| `report_doc` | `report_datasink_doc_{doc_id}_{section}.json` | 30 天 | — | — | refresh |
| `fin_indicator` | `fin_indicator_{code}.json` + `fin_indicator_hist_{code}.json` | 24h | — | — | refresh |
| `dividend` | `dividend_{fingerprint}.json` | 7 天 | — | 持仓+穿透 A 股代码 | refresh |
| `benchmark` | `fund_benchmarks.json` | 30 天 | — | — | refresh |

#### LLM 分析类

| 键名 | 文件名模式 | TTL | 盘中特殊 | 指纹 | 分组 |
|:-----|:----------|:---:|:--------:|:----|:-----|
| `llm_expert_review` | `llm_expert_review_{fingerprint}.json` | 4h | — | 持仓汇总+分类+穿透+明细 | preload |
| `llm_debate_pro` | `llm_debate_pro_{fingerprint}.json` | 24h | — | 复用 expert_review 持仓指纹（排除行情波动） | preload |
| `llm_debate_con` | `llm_debate_con_{fingerprint}.json` | 24h | — | 复用 expert_review 持仓指纹（排除行情波动） | preload |
| `llm_debate_synthesis` | `llm_debate_synthesis_{fingerprint}.json` | 24h | — | 复用 expert_review 持仓指纹（排除行情波动） | preload |
| `llm_news_correlation` | `llm_news_item_{hash}.json`（逐条） | 4h | — | 标题前 80 字+持仓指纹 | refresh |

> **TTL 两层模型**：① **默认值唯一来源** = `core/data_registry.py` 的 `DataModuleDef.cache_ttl`（清理/统计/读侧同源）；② **可选覆盖** = `config.json → cache_ttl.<类型>`，生成的配置里该段为空对象，只在用户显式添加键时生效。`cache.get_ttl` 的优先级为「盘中特例（注册表 `market_ttl` 声明的 price/index）→ 配置覆盖（`cache_ttl`，仅盘后对盘中敏感类型生效）→ 注册表默认 → `CACHE_DAILY` 兜底（未注册类型，并打 WARNING）」；**不做 per-key 抖动**——TTL 只由「类型」决定、与 key 无关，因此读侧与清理侧天然同值。按 key 抖动要求每个读点都传 key 才能与清理侧一致，属无机制保障的隐式契约；而本应用缓存逐资产写入、过期时刻天然分散，抖动的收益低于该维护成本。
| `llm_global_macro` | `llm_global_macro_{fingerprint}.json` | 24h | — | A 股/美股指数+持仓汇总 | preload |
| `llm_health_check` | `llm_health_check_{fingerprint}.json` | 4h | — | 持仓明细（排除行情波动） | preload |
| `llm_penetration_deep` | `llm_penetration_deep_{fingerprint}.json` | 4h | — | 持仓明细（排除行情波动） | preload |

#### 基金深度分析类

| 键名 | 文件名模式 | TTL | 盘中特殊 | 指纹 | 分组 |
|:-----|:----------|:---:|:--------:|:----|:-----|
| `fund_manager` | `fund_manager_{code}.json` + `fund_manager_snapshot.json` | 24h | — | — | refresh |
| —（持仓重合度） | 运行时推导（复用 `fund_hold_{code}.json`，无独立缓存） | — | — | — | — |
| `fund_concentration` | `fund_concentration_snapshot.json` | 30 天 | — | — | 无分组 |
| `fund_style_snapshot` | `fund_style_snapshot.json` | 30 天 | — | — | 无分组 |
| `extended` | `extended_{code}.json` | 24h | — | — | refresh |

#### 历史走势类

| 键名 | 文件名模式 | TTL | 盘中特殊 | 指纹 | 分组 |
|:-----|:----------|:---:|:--------:|:----|:-----|
| `history_stock` | `history_stock_{code}.json` | 7 天 | — | — | 无分组 |
| `history_fund_otc` | `history_fund_otc_{code}.json` | 30 天 | — | — | 无分组 |
| `history_index` | `history_index_{code}.json` | 30 天 | — | — | 无分组 |

#### 系统类

| 键名 | 文件名模式 | TTL | 盘中特殊 | 指纹 | 分组 |
|:-----|:----------|:---:|:--------:|:----|:-----|
| `tracking` | `holdings_tracking.json` | 30 天 | — | — | 无分组 |
| `calendar` | `trading_calendar.json` | 14 天 | — | — | 无分组 |
| `bond_yield` | `bond_yield_rf` / `bond_yield_history`（精确键名） | 1 天 | — | — | refresh |
| `idx_valuation` | `idx_valuation_`（前缀，当前仅 sh000300） | 7 天 | — | — | refresh |
| `datasink_probe_miss` | `datasink_probe_miss_{hash}.json` | 12h | — | — | 无分组 |
| `report_symbol_miss` | `report_symbol_miss_{hash}.json` | 6h | — | — | 无分组 |

> `—` 表示精确键名（无指纹后缀），TTL 到期后刷新。
> **缺失探测负缓存**（`datasink_probe_miss` / `report_symbol_miss`）：只在**确定性**缺失时写入（已发布静态文档的章节 404、章节阶与备源均无正文），瞬时网络错误不写；TTL 短于「当天多次报告」周期、长于单次链路重试。
> **非缓存引擎托管的文件**：`data/cache/` 下还存在脚本自管的性能缓存（`scripts/_doc_drift` 的用例收集快照、`scripts/_test_redundancy` 的逐文件事实缓存）。它们由脚本直接写 JSON，历史上没有 `_ts` 包封 —— 而清理器按 `now - payload.get("_ts", 0)` 算龄，等于把它们算成 **57 年陈货**并每轮启动删掉（缓存优化白做，日志里还留下荒谬条目）。两侧同时修：脚本写入补 `_ts`（缓存引擎的写入时间包封），清理器对**仍无 `_ts` 的文件一律跳过**（托管边界之外，不按 epoch 虚龄删，只留 DEBUG 痕迹）。
>
> **交易日历进程内 memo**：`core/trading_calendar._get_trading_calendar()` 被逐事件/逐持仓高频调用（实测单次报告 600+ 次），每次都 `cache.get` 等于读盘 + JSON 解析 600 次。现按「缓存文件指纹（mtime_ns+size）不变且剩余 TTL 未到」进程内复用同一份日历；文件被重写/清理/到期即回落磁盘缓存，语义不变；与 `market_hours` memo 同习语（`reset` 由 conftest autouse fixture 复位，防跨用例串味）。


### 附录 D：降级层级与阈值定义

| 层级 | 含义 | 显示前缀 | 连续失败阈值 | 缓存陈旧阈值 |
|:-----|:------|:---------|:------------|:------------|
| T2 | 数据不可用 | ⚠ | 2 次 | 3 天 |
| T3 | 数据部分可用 | ℹ | 2 次 | 14 天 |
| T4 | 数据临时不可用 | ℹ | 1 次 | 14 天 |

降级配置位于 `config.json` 的 `degradation` 字段，支持 per-source 覆盖。表中为出厂默认值；代码内兜底常量（`report/data_status.py::_DEFAULT_STALE_DAYS`，T4=7 天）仅在配置缺键时生效。

### 附录 E：线程池分布

| 池名称 | 所在模块 | max_workers | 线程名前缀 | 用途 |
|:-------|:---------|:-----------|:----------|:------|
| `orch_prep` | `report/orchestrator.py`（`prepare_report_data`） | 2 | `orch_prep` | 并行获取 A 股/美股指数 |
| `orch_llm_news` | `report/_llm_news.py`（`_fetch_llm_and_news`） | 2 | `orch_llm_news` | 并行获取 LLM + 新闻 |
| `cache_ops` | `cache/operations.py` | 4 | `cache_ops` | 并行刷新基金/行业/公共缓存 |

各线程池互不共享，职责隔离。

### 附录 F：指标降级依赖矩阵

| 指标 | 依赖数据 | K 线完全不可用 | K 线部分缺失 | 说明 |
|:-----|:---------|:--------------|:-----------|:------|
| 夏普比率 | Rf + 组合日收益率 + 波动率 | None（显示 --） | 置信度降为 low | 依赖 Rf 获取器 |
| 卡玛比率 | 组合日收益率 + 最大回撤 | None（显示 --） | 置信度降为 low | — |
| HHI | 持仓权重（不依赖行情） | 正常计算 | 正常计算 | 仅需权重数据 |
| 胜率 | 盈亏品种数（不依赖行情） | 正常计算 | 正常计算 | 仅需盈亏数据 |
| 换手率 | 期间变动金额 + 均值市值（不依赖 K 线） | 正常计算 | 正常计算 | 期间变动数据仅快照支持 |
| 风险贡献 | 品种波动率 + 权重 | 仅权重等比例分配 | 部分品种用等比例替代 | 简化版非 Euler 分解 |
| Beta | 组合日收益率 + 基准日收益率 | None（显示 --） | 置信度降为 low | 252 日窗口 |
| 回撤分位(1年) | 组合日收益率（约 250 交易日） | None（显示 --） | 数据不足 60 日则不计算 | — |
| 回撤分位(全历史) | 组合日收益率 | None（显示 --） | 数据不足 60 日则不计算 | 1 年/3 年/全历史三档 |

> K 线数据通过腾讯/新浪 API 获取，两者均为已知不可靠来源。熔断时降级行为由 DegradationTracker 记录并传递至 pipeline_data['data_degradation']，LLM prompt 据此展示"部分指标因行情数据不全暂时无法计算"。

### 附录 G：报告生成降级路径矩阵

| 故障场景 | basic 路径 | both 路径 | full 路径 | LLM 分析章节 |
|:---------|:----------|:---------|:---------|:---------|
| 行情数据全熔断 | 显示 -- | 生成但注明行情缺失 | 生成但注明行情缺失 | LLM 跳过行情相关部分 |
| 概念数据熔断 | N/A | N/A | 概念板块段落显示占位文本 | 引用 DegradationTracker |
| Rf 数据不可用 | N/A | N/A | 夏普等 Rf 依赖指标显示 -- | 注明'无风险利率数据不可用' |
| LLM API 全部不可用 | 正常 | 正常（无 LLM） | 自动降级为 both 路径 | 显示'智能分析暂时不可用' |
| 单一 LLM 模块失败 | 正常 | 正常 | 仅该模块显示占位文本 | 其余 LLM 模块正常 |
| 多源并发故障 | 正常 | 生成但注明大面积降级 | 生成但注明大面积降级 | 所有不可用数据源标注降级 |
| 文件系统写失败 | 报告生成失败 | 报告生成失败 | 报告生成失败 | — |

> 基本原则：任何数据获取失败均不得阻止报告生成（文件系统写失败除外）。降级状态下生成的报告必须在页脚注明降级摘要。

### 附录 H：pipeline_data Schema 定义

> 下表列出 `pipeline_data` 全部键；各键的完整结构契约、计算链路与消费方见下方逐键说明及对应模块章节。

| 键名 | 类型 | Optional | 写入阶段 |
|:-----|:----|:---------|:--------|
| market_data | dict | 否 | prepare_report_data |
| index_data | dict | 是 | prepare_report_data |
| fund_data | dict | 是 | prepare_report_data |
| penetration_data | dict | 是 | prepare_report_data |
| news_data | list | 是 | fetch_news |
| llm_data | dict | 是 | generate_all_llm |
| history_data | dict | 是 | fetch_history_data |
| risk_metrics | dict | 是 | prepare_report_data |
| data_degradation | list[dict] | 是 | capture_snapshot |
| llm_status | str | 是 | generate_all_llm |
| rebalance_signals | list[dict] | 是 | prepare_report_data |
| liquidity_warnings | list[dict] | 是 | capture_snapshot |
| fx_exposure | dict | 是 | fx_exposure (analysis/) |
| scenario_analysis | dict | 是 | prepare_report_data |
| style_factor_data | dict | 是 | prepare_report_data |
| position_relationship_data | dict | 是 | prepare_report_data |
| evolution_data | dict | 是 | prepare_report_data |
| position_status | dict | 是 | prepare_report_data |
| data_freshness | dict | 是 | prepare_report_data |
| action_data | dict | 是 | prepare_report_data；basic 路径由 generate_excel_report 就地构建 |
| crisis_annotation_data | dict | 是 | assemble_history_augmented_data（full/both 双路径同源装配，`report/_snapshot.py`；危机标注关态恒写、回放态加 replay 层；风险调整超额同点按开关注入 risk_adjusted_excess_data） |
| risk_adjusted_excess_data | dict | 是 | build_risk_adjusted_excess（报告章节与增强开关 risk_adjusted_excess，默认关） |
| tail_risk_data | dict | 是 | prepare_report_data |
| snapshot_diff_data | dict | 是 | prepare_report_data |
| fund_flow_data | dict | 是 | prepare_report_data |
| valuation_data | dict | 是 | prepare_report_data |
| market_temperature_data | dict | 是 | prepare_report_data |
| financial_report_digest_data | dict | 是 | prepare_report_data；both 路径由 _generate_report_both 就地构建 |
| financial_indicator_data | dict | 是 | prepare_report_data；both 路径由 _generate_report_both 就地构建 |
| purchase_status_data | dict | 是 | prepare_report_data；both 路径由 _generate_report_both 就地构建 |
| diff | dict | 是 | capture_snapshot |
| decision_review_data | dict | 是 | record_llm_decisions_and_review_block |
| holding_change_data | dict | 是 | inject_holding_change_data（报告章节与增强开关 holding_change_review，默认关） |
| event_impact_data | dict | 是 | inject_event_impact_data（报告章节与增强开关 event_window_impact，默认关） |
| schedule_replay_data | dict | 是 | inject_schedule_replay_data（功能开关 rebalance_schedule_replay，默认关） |
| factor_catalog_data | dict | 是 | prepare_report_data（功能开关 factor_catalog，默认关；键值可为 None，None/缺失均不渲染区块） |
| prosperity_framework_data | dict | 是 | prepare_report_data（full/both）；basic 路径由 generate_excel_report 就地构建 |
| market_sentiment_data | dict | 是 | 行动建议章内嵌块（full/both 由编排层注入；basic 路径由 generate_excel_report 就地构建） |
| summary_highlights_data | dict | 是 | build_summary_highlights（报告章节与增强开关 summary_highlights，默认关；无上期快照时缺失，模板整块隐藏） |

> `diff`（环比对比差异，C19 契约，12 键）：`{"is_first_check": bool, "total_value_diff": float, "total_value_diff_pct": float, "total_pnl_diff": float, "days_since_last_report": int, "baseline_timestamp": str, "baseline_trading_day": str, "baseline_generated_at": str, "added": list[dict], "removed": list[dict], "increased": list[dict], "decreased": list[dict]}`。四组明细每项含 `name`/`code`/`action`/`shares_diff`/`value_diff`（新增/清仓/加仓/减仓）。`baseline_timestamp`/`baseline_trading_day`/`baseline_generated_at` 为基线快照标识（文件名时间戳 / 所属交易日 / 报告生成时间，展示格式 `YYYY-MM-DD HH:MM`），供展示层标注**对比基准**（HTML 本期要点标题下、Excel 环比对比块、LLM 环比上下文【对比基准】行）；标注不可解析时为空串，展示层省略标注行。由 `capture_snapshot()`（`report/_snapshot.py`）基于**同快照域上一有报告交易日的最新一份快照**（`report/history_snapshot.load_comparison_baseline`，同一交易日多次运行不互比）用 `fetcher/history_diff.HistoryDiff` 计算；首次运行（`is_first_check`）或异常时整个 `pipeline_data` 为 None（键缺席，下游按 `.get()` 判空）。校验入口 `report/pipeline_data_builder.py::build(diff=...)`（`_validate_diff` 子键深层类型校验）。消费方：汇总 Excel 环比 δ 列（`report/excel_generator.py`）、行动章环比上下文（`report/_report_helpers.py`）、LLM 环比差异段落（`llm/prompts_data_blocks.py`，facade `llm/prompts_core.py`）。

> `decision_review_data`（决策复盘区块，C19 契约，实验功能「决策跨期反思闭环」开启时才有）：行动章内嵌复盘表数据，由 `report/decision_review_block.py::build_review_block(report_date=...)` 从决策账本（`core/decision_ledger`）装配，在 `report/_experimental_seams.py::record_llm_decisions_and_review_block` 注入（开关关闭或区块为空 → 键缺席，两条输出路径保持既有输出）。消费方：HTML `partials/action_section.html` 与 Excel `report/action_sheet.py`（均按 `.get()` 消费，键缺席即不渲染）。类型校验：`report/pipeline_data_builder.py::_PIPELINE_DATA_TYPE_MAP`。

> `holding_change_data`（持仓变动复盘，C19 契约，报告章节与增强开关 `holding_change_review` 默认关）：快照差分事件清单 + 频率/结构/贡献分解指标 + 意图对账（决策账本只读对照）+「区间净额推断、非逐笔」局限标注，由 `report/holding_change_panel.py::build_holding_change_panel` 装配（事件抽取 `analysis/holding_change_events.py` + 纯计算 `analysis/holding_change_metrics.py`），在 `report/_experimental_seams.py::inject_holding_change_data` 注入（开关关闭 → 键缺席 → 注册表 `holding_change` 章 data_flag False → 整章隐藏，两条输出路径保持既有输出）。消费方：HTML `partials/holding_change_section.html` 与 Excel `report/holding_change_panel.py::write_holding_change_sheet`（均经 `build_holding_change_view` 取双端单源预格式化行）；归因块例外取三键 `_llm_review_view` 单源拆分——`llm_review_html`（HTML 端 `\| safe` 原文直出，含尾部标识行，标签不被 autoescape 转义）、`llm_review_paragraphs`（Excel 端纯文本块，复用 `llm_content` 的 `_split_html_blocks`/`_strip_html`）、`llm_review_footer`（标识行纯文本，页签尾部灰色小字与其余 LLM 页签一致）。类型校验：`report/pipeline_data_builder.py::_PIPELINE_DATA_TYPE_MAP`。

> `factor_catalog_data`（因子目录，C19 契约，实验开关 `factor_catalog` 默认关）：25 因子五来源族逐因子横截面（`slug`/`family`/`family_label`/`label`/`value`/`neutral`/`above`/`codes_ok`/`computable`/`reason`）+ 池与评级摘要（`pool_size`/`computed`/`neutral_above`/`neutral_total`/`rating`/`version`/`catalog_size`）+ 逐类型不可得原因 `unavailable`，由 `analysis/factor_evaluator.py::build_factor_catalog_data` 编排（冻结目录 `schemas/factor_catalog.py` + 装载 `fetcher/factor_catalog_loader.py` + 公式原语 `analysis/_factor_formulas.py`），在 `report/orchestrator.py::prepare_report_data` 注入（开关关闭 → 键为 None → 区块不渲染、信号零记录；计算失败降级 `available=false` 占位，两条输出路径保持既有输出）。消费方：HTML `report_template.html` 风格与因子分析区区块四与 Excel `report/style_factor_sheet.py::write_style_factor_sheet`（`_write_catalog_block`）；信号消费方 `report/signal_record.py`（每日单条快照）。类型校验：`report/pipeline_data_builder.py::_PIPELINE_DATA_TYPE_MAP`。

> `valuation_data`（估值分位，C19 契约，4 键 + 内嵌 `by_code` 子键）：`{"available": bool, "status": str, "by_code": {code: {"pe": float\|None, "pb": float\|None, "price_percentile": float\|None, "tier": str\|None, "sample_count": int, "percentile_available": bool, "real": dict, "real_available": bool}}, "basis_mode": "real_ttm"\|"proxy_only"}`。当前 PE/PB 由 `fetcher/industry.py::fetch_valuation_fields`（网关入口；东财 push2 扩展字段 f9/f23 与行业分类同属一次请求，经 Provider Chain + 文件/会话缓存取用，报告层不得直连 provider）；`price_percentile` 为历史 K 线价格分位代理（0~100，`analysis/valuation_percentile.py`，MIN_SAMPLES=60），非真实历史估值分位（盈利增长未纳入，渲染层必须展示 `DISCLAIMER`"价格分位代理，非真实历史估值分位"）。由 `report/orchestrator.py::compute_valuation_data` 计算（功能开关 `valuation_percentile` 默认关；关闭 → None → 「资产穿透TOP10」估值列隐藏；PE/PB 与 K 线皆不可得 → available=False 落 §1.4.5 占位）。消费方：穿透 TOP10 Excel `penetration_sheet` 估值分位列（ncols 10→11 + 表尾免责）与 HTML `report_template.html` 条件列（`valuation_enabled`）。**真实历史估值分位（TTM 口径，后续增强）**：`by_code` 另含 `real`（子契约：`available`/`pe_ttm`/`pb`/`pe_percentile`/`pb_percentile`/`tier`/`basis`/`sample_count`/`report_period`/`reason`）与 `real_available`，由 `analysis/valuation_percentile.py::compute_real_valuation` 用「多期 TTM 每股收益（年报直取、季报累计差分）× 该日已生效最新一期基本面 × 历史收盘价」构造历史 PE/PB 序列后取当前值分位（生效日取法定披露截止日以避免前视偏差；PE 优先、PB 兜底；样本下限 60）。多期基本面来自 `fetcher/financial_indicator.py::fetch_indicator_series`；渲染层**优先展示真实分位并标注 basis，无基本面覆盖时回落价格分位代理**（分别对应 `DISCLAIMER_REAL` / `DISCLAIMER_PROXY`，两者不得混口径展示）。**数据底座门禁**：真实分位以 `config.datasink_feature_ready`（`datasink.enabled` 开启 且 凭据就绪，纯本地判定）为前提——未就绪时 `_fetch_valuation_for_code` 不做任何取数与计算，`compute_valuation_data` 置 `basis_mode="proxy_only"`，估值列文案与免责语**逐字回退到引入前的原样**（Excel `penetration_sheet.valuation_footer_note` / HTML `valuation_real_basis` 同一判据）；就绪时为 `basis_mode="real_ttm"`。

> `market_temperature_data`（市场温度，市场温度数据契约字段语义，16 键）：`{"available": bool, "status": str, "index_code": str, "index_name": str, "price_percentile": float\|None, "valuation_percentile": float\|None, "valuation_components": dict\|None, "first_factor": str\|None, "ma_deviation": float\|None, "volatility": float\|None, "score": float\|None, "tier": str\|None, "sample_count": int, "components": dict\|None, "reason": str\|None, "disclaimer": str}`。**第一因子为估值分位**（PE/PB/ERP 各自历史分位等权，样本下限 60；`fetcher/index_valuation.py` 乐咕月频 PE/PB + `bond_yield` 10Y 国债收益率历史序列 → `build_erp_series` 按日期 asof 对齐成股债性价比）；估值序列不可得时回落**点位分位**（`first_factor="price_proxy"`，行为=升级前口径；降级链：实时 → 30 天旧缓存兑底 → 点位分位，防源时好时坏导致档位翻跳）。第一因子 + 均线偏离 + 年化波动率三因子合成温度分（0~100，`analysis/market_temperature.py`，权重 0.5/0.3/0.2，各分量 clamp；**波动率分量反向**——A 股高波动多现于恐慌下跌，波动越高分量越低，“越波动越冷”）；回看窗口 2000 交易日（实测腾讯/东财源上限 ≈8 年；链路文件缓存短于请求窗口时自动清缓存全量重取——窗口缩水自愈）。`price_percentile` 始终计算（双轨保留，展示/回落用）；**温度计只给刻度、无仓位指令**（`TEMPERATURE_DISCLAIMER` 渲染层必须展示）。`ma_deviation`/`volatility` 为小数比例（0.032=3.2%），渲染层须 ×100 转百分数展示。由 `report/_report_aux_metrics.py::compute_market_temperature_data` 计算（编排入口 `report/orchestrator.py`；指数 K 线 `fetch_index_history` 沪深300 走 Chain + session_cache；功能开关 `market_temperature` 默认开；关闭 → None → 「投资分析汇总」温度行隐藏；K 线不足 → `insufficient` 占位）。消费方：汇总 Excel `summary._write_market_temperature`（三因子行首项按 `first_factor` 动态展示「估值分位/价格分位」）与 HTML kv-table（`first_label`/`first_value` 展示映射；展示映射另含 `methodology`/`tier_scale` 说明行字段，由权重/阈值常量单源派生，温度行下渲染「计算逻辑」与「分级标准」两行，展示构建器缺字段时静默省略——旧契约兼容）。

> `financial_report_digest_data`（持仓个股财报摘要，C19 契约，5 键）：`{"available": bool, "reason": str, "rows": list[dict], "failures": list[dict], "entry_count": int}`。`rows` 每项含 `code`/`name`/`symbol`/`report_period`/`doc_type`（中文标签）/`title`/`announcement_date`/`summary`/`source`/`adjunct_url`；`failures` 每项含 `code`/`name`/`reason`。对持仓 + 穿透中的 A 股标的，取最新年报（无年报退半年报）的目标章节正文并按 `datasink.max_chars` 截断，由 `report/financial_report_digest.py::build_financial_report_digest` 装配（数据源 `providers/datasink.py`，取数编排 `fetcher/financial_report.py`）。功能开关 `stock_fundamentals` 默认关（关闭 → None → 区块不写）；缺凭据/无 A 股标的/全部无覆盖 → `available=False` 降级。合规：`source` 为披露平台归属，渲染层须保留。C7 注册：该契约并入合并章 `fundamental_snapshot` 的 `data_flag_any`（无独立 type）。消费方：Excel `report/fundamental_snapshot_sheet.py::_write_digest_block` 与 HTML `partials/fundamental_snapshot_section.html`（区块二）。
>
> `financial_indicator_data`（财务指标，C19 契约，5 键）：`{"available": bool, "reason": str, "rows": list[dict], "failures": list[dict], "entry_count": int}`。`rows` 每项含 `code`/`name`/`report_period`/`doc_type`/`doc_type_label`/`source_api`/`source`/`revenue`/`net_profit`/`revenue_yoy`/`net_profit_yoy`/`gross_margin`/`roe`/`debt_ratio`/`operating_cash_flow`/`eps`/`bvps`/`pe`/`pb`/`quality_grade`/`quality_score`/`trend`/`series`/`period_count`；`failures` 每项含 `code`/`name`/`reason`。对持仓 + 穿透中的 A 股标的取多期指标（`fetcher/financial_indicator.py`：主源 akshare 一次调用得多期；主源不可用时先由**同花顺官方合并报表派生多期**（`analysis/financial_statement_derive.py`，三张报表各一次请求即得多期），再退化为链路单期记录），由 `analysis/financial_indicator.py::quality_grade`/`trend_label`/`current_valuation` 派生质量档（ROE/毛利率/资产负债率/经营现金流对净利覆盖 四维均值启发式，**非投资建议、非评级**，阈值不区分行业）、年度趋势（相邻年报营收与净利）与当前 PE/PB（**官方 TTM/MRQ 口径优先**：数据源提供 `pe_ttm`/`pb_mrq` 时直接采用；缺失才回退「现价 ÷ 该报告期每股收益/每股净资产」，亏损或净资产非正留空——自算口径在半年报/季报上会明显虚高，两者混用会误导估值判断），由 `report/financial_indicator.py::build_financial_indicator` 装配（现价来自行情明细，经 `fetcher/financial_indicator.py::collect_price_map`）。功能开关 `stock_fundamentals` 默认关（关闭 → None → 区块不写）；无 A 股标的/数据源不可用 → `available=False` 降级。历史 PE/PB 分位（TTM 口径）属后续阶段，本章只给当前值。C7 注册：该契约并入合并章 `fundamental_snapshot` 的 `data_flag_any`（无独立 type）。消费方：Excel `report/fundamental_snapshot_sheet.py::_write_indicator_block` 与 HTML `partials/fundamental_snapshot_section.html`（区块一）。

> `purchase_status_data`（申购限购状态，C19 契约，7 键）：`{"available": bool, "reason": str\|None, "rows": dict, "fetched_at": str\|None, "source": str\|None, "constraint_block": str, "restricted_index": dict}`。`constraint_block` 为构建期渲染的申购限购约束块（`purchase_status.py::build_purchase_constraint_block` 单源：准入四条任一不过 → `""`；行序 = 持仓明细顺序、字段值与单元格同源；`holdings_details` 缺省不传 → `""`——both/basic/What-if 取契约路径块恒空零开销），消费方为 LLM 分析章提示词（`generate_all_llm` 从 `pipeline_data` 提取同一实例 → `llm/prompts_tables.py::_build_prompt_appendix` 统一附录第 4 段，`skeleton` 单点注入，进提示词必进指纹；新闻批量路径由 `_llm_news.py::_fetch_llm_and_news` 同源读取交 `generators_news` 批量 hooks 的提示词与缓存指纹）。`restricted_index` 为受限标的预格式化索引（code → status/limit/limit_text/next_open_text/level，由 `purchase_status.py::build_restricted_index` 经 `_filter_restricted_rows` 单源筛选与格式化、`report/orchestrator.py` 编排层注入；准入不满足 → `{}`，消费方按缺席回退；What-if 路径经 `whatif_operations._purchase_restricted_index` 单点就地构建同名索引）。`rows` 为 `{代码: {purchase_status, redemption_status, next_open_date, daily_limit, min_purchase}}`（0 元/缺失限额在解析层已单点转 `daily_limit=None` → 展示「限额未知」）；由 `fetcher/fund_purchase.py::fetch_fund_purchase_status_cached` 取天天基金全量表（Provider Chain + 形状/值域准入 + 会话复用），`report/purchase_status.py::build_purchase_status_data` 装配。功能开关 `fund_purchase_limit` 默认开（关闭 → None → 列隐藏）；全链失败 → `available=False` 静默隐列（不阻断主链路）。时效分档由 `purchase_status.py::stale_level` 按交易日历计（≤3 正常 / 4~7 展示并标数据陈旧 / >7 显示「—」，宁缺毋错，长假不计入）。单元格文案、口径脚注、列可见判据均单源于 `report/purchase_status.py`（Excel 与 HTML 共用，不发散）。消费方：HTML `report_template.html` 持仓市值明细与持仓分类表条件列（同一 `purchase_status_display` 上下文——cells/level/footnote——明细行取 cells 映射、小计/总计空 td）与 Excel `report/holdings_detail_sheet.py`（市值明细与分类汇总两区块末列追加——明细行渲染、小计/总计留空——+ 区块①下方口径脚注，该行位于两区块之间覆盖两块）；What-if 目标持仓受限提示（`analysis/whatif.py::build_whatif_data` 的 `restricted_index` 形参 → 契约条件键 `feasibility` → Excel 持仓变动明细尾部区块 + HTML⑦申购受限提示节）。

> `style_factor_data`（风格与因子分析，C19 契约，13 键 + 内嵌 `industry_beta` 子键）：主键 `{"available": bool, "status": str, "betas": {factor: float}, "t_stats": {factor: float}, "significant": {factor: bool}, "style_allocation": {factor: float}, "baseline_betas": {factor: float}, "factor_correlations": {pair: float}, "correlation_note": str, "alpha": float, "window": int, "sample_count": int, "stale_factors": list[str]}`。MVP 3 因子（价值/成长/质量），由 `analysis/style_factor_regression.py` 计算、`report/orchestrator.py` 组装。子键 `industry_beta`（行业 Beta，`industry_beta.py::compute_industry_beta_analysis`，功能开关 `industry_beta` 默认关；关闭 → None → 区块隐藏）：`{"available": bool, "exposure": {industry: float}, "index_codes": {industry: str}, "betas": {industry: float}, "t_stats": {industry: float}, "significant": {industry: bool}, "correlations": {industry: float}, "unmapped_industries": list[str]}`——行业暴露占比按持仓市值聚合，行业指数为中证行业指数（`INDUSTRY_INDEX_MAP`），β 复用 `compute_factor_exposure` 单因子 OLS。C7 注册见 §8.3（type=`fund_deep_analysis`、data_flag=`style_factor_data`），计算方案/架构约束/降级分支见 §4.8 风格与因子分析。

> `position_relationship_data`（持仓关系矩阵·相关性区块数据，C19 契约，12 键）：`{"available": bool, "status": str, "window": int, "sample_count": int, "codes": list[str], "names": {code: str}, "matrix": list[list[float\|None]], "p_values": list[list[float\|None]], "pairs": list[dict], "insufficient_codes": list[str], "note": str, "rolling": dict\|None}`。下三角矩阵（row>col 有值、对角=1.0、上三角 None），配对明细含 code_a/name_a/code_b/name_b/pearson/p_value/significant/samples。第 12 键 `rolling` 为滚动趋势子块（就绪时 dict：`portfolio` 60/120 端点窗组合平均序列 + `focus_pairs` 重点品对滚动序列 + `coverage` 完整窗起始 + `notes` 口径句单源；失败/数据不足为 None，消费方一律 `.get`），由 `analysis/correlation.py::compute_rolling_correlations` 计算、编排层经 `report/downsample::downsample_bars` 下采样后注入（拉取条数 `FETCH_DAYS` 覆盖最长滚动窗，缓存短于窗口时增量链路自动全量补齐），静态矩阵不依赖此键。由 `analysis/correlation.py` 计算、`report/_report_aux_metrics.py::compute_correlation_data` 注入（编排入口 `report/orchestrator.py`），作为「持仓结构与集中度」的区块二（相关性）数据源（一章三区块，见 §4.8 持仓结构与集中度）。C7 注册见 §8.3（type=`fund_deep_analysis`；旧条目 data_flag=`position_relationship_data` 现并入合并章 `position_structure` 的 `data_flag_any`，章节可见性 = 重合度/相关性/集中度任一就绪），数据不足（重叠样本 <60 / 品种 <2）落 §1.4.5 降级。

> `evolution_data`（组合演进，C19 契约，多快照趋势聚合）：`{"available": bool, "snapshot_count": int, "min_snapshots": int, "periods": list[str], "total_value": list[float], "total_cost": list[float], "total_pnl": list[float], "holding_counts": list[int], "account_flows": {account: list[float]}, "hhi": list[float\|None], "top_holdings": list[dict], "reason": str}`。`top_holdings` 每项含 code/name/weights（各期占比 %）/present_count（出现期数）；历史快照 `market_value=0.0` 时权重回退成本口径。由 `analysis/portfolio_evolution.py` 计算、`report/orchestrator.py` 注入（C7 注册 type=`evolution`、data_flag=`evolution_data`，见 §4.12），有效快照 < MIN_SNAPSHOTS=3 时 `available=false` 落 §1.4.5 降级。

> `history_data`（组合历史走势 + 回撤，C19 契约，供组合历史走势与回撤章复用）：`{"bars": list[dict], "max_drawdown": float, "max_drawdown_pct": float, "drawdown_events": list[dict], "recovery_times": list[dict], "drawdown_available": bool, "annualized_volatility": float, "total_return": float, "daily_returns": list[float], "monthly_returns": dict, "warnings": list[str], "benchmarks": list[dict], "successful_holdings": list}`。`drawdown_events`（独立回撤事件）含 peak_date/trough_date/recovery_date/drawdown_pct/duration_days/recovery_days/recovered；`recovery_times`（恢复耗时明细）含 start_date/end_date/days。由 `report/portfolio_history.py` 组装（C7 注册 type=`history`），`drawdown_available` 表示有效交易日 ≥ MIN_SPAN 才渲染回撤明细，否则落 §1.4.5 降级。消费方为「组合历史走势与回撤」（`portfolio_history_drawdown`，一章多区块，Excel 见 `report/portfolio_history_drawdown_sheet.py`、HTML 见模板 `report_template.html`），区块数据由本契约 + 下方 `crisis_annotation_data`/`tail_risk_data` 提供。

> `crisis_annotation_data`（危机区间标注，C19 契约，关态 2 键 + 回放态 4 键）：`{"available": bool, "intervals": list[dict]}`，回放态（开关 `crisis_replay`）顶层追加 `"replay": true` 与可选 `"index_reason"`（指数层不可用原因）。`intervals` 每项含 name/start/end/desc/in_range/interval_drawdown_pct/trough_date/recovery_days/recovered——基于 `history_data.bars` 对预设历史危机区间（2015 股灾 / 2018 贸易摩擦 / 2020 疫情 / 2022 调整 / 2025 关税冲击，`analysis/crisis_annotation.py::CRISIS_INTERVALS` 静态历史事实表，新增区间只改该表、全端清单动态跟随）做窗口重叠裁剪与区间统计：`in_range` 表示与报告数据窗口重叠；`interval_drawdown_pct` 为区间内 running-peak 最大回撤（正数 %，窗口内无 bar 时为 None）；`trough_date` 为区间最深日；`recovery_days` 为最深日→首个回到峰值的恢复耗时（数据窗口内未恢复为 None）；`recovered` 为是否已恢复。回放态每区间另含 `portfolio_return_pct`（组合窗内区间首尾净值收益，窗外 None）、`index_return_pct`/`index_drawdown_pct`（指数层区间收益与区间最大回撤，来自基准长窗日线 LOCF 序列，不可用 None）与 `index_available`——**双层回放**：指数层覆盖全部静态区间（指数源可回溯 3650 交易日），组合层仅覆盖子块扩展窗（`max(lookback_days, 365)`）内区间，窗外行状态标「组合窗口外」。由 `analysis/crisis_annotation.py::build_crisis_annotation(history_data, replay, index_series)` 计算（纯标准库、analysis 层隔离，无 report/llm 依赖），full/both 两路径统一由 `report/_snapshot.py::assemble_history_augmented_data` 注入 pipeline_data（回放开关开时指数层随 `_crisis_index_days()`（按静态表最早起点动态推算、封顶 3650）经 `fetch_benchmarks` 取数），Chart.js 净值图阴影带（`chart_data_builder.py` 计算起止索引 → `chart-init.js::buildCrisisBandPlugin`）与 HTML 危机表/Excel 危机区块消费。危机标注净值图必须 C20 图下说明（`.chart-caption` 跟随是否有 in_range 区间数据）。

> `tail_risk_data`（尾部风险统计，C19 契约，12 键）：`{"available": bool, "sample_size": int, "var95": float\|None, "var99": float\|None, "max_single_day_drop": float\|None, "max_single_day_drop_date": str\|None, "consecutive_down_days": int\|None, "consecutive_down_start": str\|None, "consecutive_down_end": str\|None, "recovery_days_after_drop": int\|None, "recovery_state": str\|None, "warnings": list[str]}`。VaR(95/99) 用历史模拟法（日收益升序排序取 (1-置信度) 分位损失，正数 %）；`max_single_day_drop` 为最大单日跌幅（%）；`consecutive_down_days` 为最长连续下跌天数（区间 start/end 日期）；`recovery_days_after_drop` 为自最大单日跌幅日收复跌幅前水平所需交易日，`recovery_state` 取值 `recovered`/`unrecovered`/`none`（无下跌日）。日收益与 `report/portfolio_history._compute_daily_returns` 同口径（(curr-prev)/prev，小数），复用 `history_data.bars`，不额外拉长 lookback。由 `analysis/tail_risk.py::compute_tail_risk(bars)` 计算（纯标准库、analysis 层隔离，无 report/llm 依赖），both 路径在 `report/_report_generation.py` 以 `compute_tail_risk(history_data["bars"])` 注入 pipeline_data，「组合历史走势与回撤」消费（Excel `report/portfolio_history_drawdown_sheet.py::_write_tail_risk_rows`、HTML 尾部风险卡 `report_template.html`，C20 图下说明）。日收益样本 < MIN_SAMPLE=20 时 available=False、各指标 None，落 §1.4.5 降级占位。

> `snapshot_diff_data`（快照差异摘要，C19 契约，12 键）：`{"available": bool, "snapshot_count": int, "previous_date": str\|None, "current_date": str\|None, "added": list[dict], "removed": list[dict], "hhi_previous": float\|None, "hhi_current": float\|None, "hhi_change": float\|None, "over_limit": list[dict], "summary": str, "reason": str}`。`added`/`removed` 每项含 code/name（本期新增/上期清仓品种，复用 `fetcher/history_diff.HistoryDiff` 引擎按 code 跨账户合并比对）；`hhi_previous`/`hhi_current` 为上期/最新期集中度 HHI（Σ权重²，市值口径优先、市值为 0 回退成本口径，与 `evolution_data` 同口径），`hhi_change` = 本期-上期；`over_limit` 为最新期权重 > 15% 警戒线的品种（含 code/name/weight_pct/threshold_pct，按权重降序，阈值复用 `analysis/simple_rebalance._THRESHOLD`）；`summary` 为一段中文变化摘要（新增/移除品种 + HHI 变化方向 + 超限项），直接供展示层渲染。由 `analysis/snapshot_diff.py::build_snapshot_diff()` 计算（纯标准库、analysis 层隔离，无 report/llm 依赖；复用 `analysis/portfolio_evolution` 的 `_compute_hhi`/`_holding_weight` 与 `simple_rebalance._THRESHOLD`；基线由 `report/history_snapshot.load_comparison_baseline` 提供——**分属不同交易日**的最近两份快照，同一交易日多次运行比对无意义不互比），both/full 路径在 `report/_report_generation.py` 以 `_inject_snapshot_diff_data` 注入 pipeline_data（与 `evolution_data` 同开关：组合演进章节开启才计算），「组合演进」顶部「自上次快照变化摘要」消费（Excel `report/evolution_sheet.py`、HTML 模板 `partials/evolution_section.html`）。有效快照 < 2 期或无更早交易日快照可对比时 available=False、`reason` 说明（含「同一交易日」口径），落 §1.4.5 降级占位。

> `summary_highlights_data`（本期要点与环比对照，C19 契约，功能开关 `summary_highlights` 默认关）：`{"days_since_last_report": int, "total_value_diff": float, "total_value_diff_pct": float, "total_pnl_diff": float, "total_pnl_pct_diff": float, "holding_count_delta": int, "added_count": int, "removed_count": int, "hhi_change": float\|None, "changes": list[dict], "change_total": int}`。`changes` 每项含 code/name/action（added/removed/increased/decreased）/value_diff/shares_diff，按 |value_diff| 降序截断至 Top N（默认 5），`change_total` 为全量变动条数（溢出时模板写「等共 N 项变动」提示）；`holding_count_delta` = added−removed 派生（零新数据）；`hhi_change` 复用 `snapshot_diff_data.hhi_change`（不可得时 None → 模板省略该行，行级降级）；`baseline_trading_day`/`baseline_generated_at` 为基线标注（透传 diff 同名键，展示「对比基准：交易日 … · 报告生成 …」行，缺省空串 → 省略行）；`total_pnl_pct_diff` 为新扩展字段（`DiffSummary.total_pnl_pct_diff`，快照双端已持久化 `total_pnl_pct` 的自然差值）。由 `report/summary_highlights.py::build_summary_highlights(pipeline_data)` 纯派生装配（消费 `pipeline_data.diff` + `snapshot_diff_data`，零新增取数零计算重复），编排 2b4 注入（full/both 双路径），HTML `partials/summary_section.html` 基本信息表后「本期要点」块消费；Excel 既有环比对比块同步追加「对比基准」标注行（`report/excel_generator.py`，基线标注为空时省略）。降级：`diff` 缺席或 `is_first_check` → None → 模板整块隐藏不写占位（首跑产物零变化）。

> `position_status`（品种覆盖诊断，C19 契约）：`{"available": bool, "items": list[dict], "abnormal_count": int, "summary": str}`。`items` 每项含 code/name/account/status/status_label/reason；status 取值 `ok`/`nav_missing`/`possibly_delisted`/`bad_code_format`/`name_mismatch`（本地信号=代码格式+名称比对，数据信号=行情/净值可用性，见 `core/holding_status.py`）。由 `core/holding_status.py::build_coverage_summary` 计算、`report/orchestrator.py::prepare_report_data` 组装，both 路径在 `_report_generation.py` 直接以 `build_coverage_summary` 注入。消费方：数据质量仪表盘（功能开关 `data_quality`，「品种覆盖」区块，Excel 见 `report/data_quality_sheet.py`、HTML 见模板 `report_template.html`）；basic 路径无行情数据时 available=False，品种覆盖区块落降级占位。

> `data_freshness`（数据可信度诊断，C19 契约）：`{"available": bool, "items": list[dict], "abnormal_count": int, "summary": str, "trading_day": str, "prev_trading_day": str}`。`trading_day`/`prev_trading_day` 为本次判定所依据的最近交易日与其前一交易日，随契约一并回传——消费方判断新鲜度必须以其为基准，不得以运行时刻替代（报告可在非交易日运行，运行时刻与最近交易日天然相差一个自然日，用自然日差会把正常的 T-1 净值误报为延迟）；体检报告「数据质量」维度即消费此二字段构造基准行。`items` 每项含 code/name/account/freshness/freshness_label/reason/jump/jump_label/change_pct；freshness 取值 `fresh`（净值=当日）/`cached`（=上一交易日，正常 T-1）/`stale`（更早或缺失）/`degraded`（无有效行情）。单日跳变仅对 fresh/cached 品种判定（|涨跌幅| ≥ ±20% 标记 jump，label「疑似数据错误（单日 +X.XX%）」），stale/degraded 跳过以免跨非交易日累计涨跌误报。由 `core/data_freshness.py`（`classify_freshness`/`detect_price_jumps`/`build_freshness_summary`）计算，交易日依据 `core/trading_calendar.py::get_last_trading_day/get_prev_trading_day`（akshare 日历缓存；`report/market_value.py` 按原公共名重新导出保持既有导入路径，实现已下沉至 `core/` 供各层共用）。由 `report/orchestrator.py::prepare_report_data` 组装，both 路径在 `_report_generation.py` 直接以 `build_freshness_summary` 注入。消费方：数据质量仪表盘（功能开关 `data_quality`，「可信度」区块 + 报告头部「N 个品种数据异常」摘要行，Excel 见 `report/data_quality_sheet.py`、HTML 见模板 `report_template.html`）；basic 路径无行情数据时 available=False，可信度区块落降级占位。

> `fund_flow_data`（成本流水，C19 契约，功能开关 `cost_lots` 默认关）：`{"available": bool, "xirr": dict\|None, "cost_tiers": dict\|None, "dividends": dict\|None}`。`xirr` 含 `{"rate": float\|None, "ok": bool, "message": str}`（资金加权收益率，Newton-Raphson + bisection 回退，natural-day 年化 `t=days/365`，投资者视角现金流）；`cost_tiers` 含 `{"available": bool, "per_code": {code: {"low"/"high"/"unpriced": {"shares", "cost"}}}}`（成本分档，批次成本价 ≤ 市价 → 低成本档、> 市价 → 高成本档、无市价单列未分档，由 `analysis/cost_flow.compute_cost_tiers` 计算）；`dividends` 含 `{"available": bool, "per_code": {code: 分红累计金额}}`（分红现金流累计）。由 `analysis/cost_flow.py::build_fund_flow_data(transactions, dividends, holdings, current_prices)` 计算（纯计算层，不依赖 report/），在 Excel 渲染层 `report/excel_market_data.py::_build_flow_data` 基于交易/分红流水组装（开关关闭或流水为空 → None，汇总/持仓明细与分类页签保持既有输出）。消费方（Excel 汇总/市值/分类页签，开关开启时）：「投资分析汇总」盈亏汇总末尾追加「资金加权收益率 (XIRR)」行（无可用现金流写「未录入流水/无法计算」占位）、「持仓明细与分类」区块①追加「资金加权成本」列（批次成本价按份额加权，`report/holdings_detail_sheet.py::_weighted_avg_cost`）、区块②追加「成本分档」「分红累计」子列（`report/category.py::_tier_label` + `div_sum` 小计/总计）。数据入口：持仓 Excel 可选「交易流水」「分红流水」页签（`core/reader.py::read_holdings_with_flows`，不破坏既有 4 列），经 `report/orchestrator.generate_report(transactions=..., dividends=...)` 贯穿。

> `prosperity_framework_data`（景气度框架诊断，C19 契约，常规功能 `prosperity_framework` 默认开）：`{"available": bool, "reason": str, "total_score": int, "scored_weight": int, "max_score": int, "total_score_pct": int, "rating": str, "rating_label": str, "dimensions": list[dict], "holdings_view": list[dict], "concentration_pct": float\|None, "turnover_proxy_pct": float\|None, "unverified": list[str], "partial_notes": list[str], "notes": list[str]}`。`dimensions` 每项含 `key`/`name`/`score`/`max_score`/`status`（scored/partial/unverified）/`evidence`/`unverified`；六维 = 景气方向/通胀属性 25 + ROE 低位弹性 20 + 全球视野/中国比较优势 15 + 流动性 10 + 集中度与周期拼接 15 + 业绩与回撤印证 15。**总分口径**：只累计 `status != unverified` 的维度（`scored_weight`），`total_score_pct = total_score / scored_weight`，评级四档（≥80 高度契合 / 60–79 较契合 / 40–59 部分契合 / <40 不契合）；缺数据维度进 `unverified` 且**不计分、不臆造**。输入全部取自既有能力（`penetration_data` 板块/概念、`financial_indicator_data` ROE、`check_liquidity` 变现天数、历史快照换手代理、`history_data` 收益与回撤；②维基金层扩展另取 `fund_roe_estimates`（基金重仓股 ROE 加权推演值，仅对无直接 ROE 的权益类基金生效，证据/持仓视角/契约 notes 均标注「按框架推演」）。由 `analysis/prosperity_framework.py::build_prosperity_framework_data` 计算、`report/_report_aux_metrics.py::compute_prosperity_framework_data` 组装（开关关闭返回 None → 契约缺席）。消费方：行动建议章内嵌块（HTML `partials/action_section.html` ⑥ / Excel `report/action_sheet.py::_write_prosperity_block`）。方法骨架借鉴开源项目 zhengxi-views（MIT），设计文档随该功能一并归档（索引见 `docs/managements/folders.md` 目录树）。
>
> `market_sentiment_data`（市场情绪与持仓热点，C19 契约，报告增强开关 `market_sentiment` 默认关）：`{"available": bool, "reason": str, "trade_date": str, "summary": {"board_caps": dict[str, int|None], "lhb_stock_count": int|None, "ladder_date": str}, "rows": list[dict], "failures": list[dict], "entry_count": int}`。`rows` 每项含 `code`/`name`/`holding_kind`（直接持有/穿透）/`event_type`（龙虎榜/连板梯队）/`event_date`/`net_value_yi`/`hot_money_net_value_yi`/`org_net_value_yi`/`hot_rank`/`range_days`/`limit_reason`/`concepts`/`board_label`/`board_num`/`seal_nextday`；**只保留命中持仓/穿透标的代码的事件行**（不做概念联想）。数据来源为同花顺官方（龙虎榜 `dragon-tiger-list` + 连板梯队 `limit-up-ladder`），取数带 1 小时缓存（`sentiment_dragon_tiger` / `sentiment_ladder`）；缺凭据/两源不可用/无命中 → `available=False` 降级。消费方：行动建议章内嵌块（Excel `report/action_sheet.py::_write_market_sentiment_block` / HTML `partials/action_section.html` ⑦）。

> `action_data`（行动建议，C19 契约，单源计算两处呈现）：`{"available": bool, "summary": str, "rebalance_signals": list[dict], "discipline_signals": list[dict], "rebalance_advice": list[dict], "attribution": dict\|None}`。`rebalance_signals` 每项含 code/name/weight/threshold/action（超警戒线品种再平衡信号）；`discipline_signals` 每项含 code/name/rule/value/status_label/triggered/distance_pct/action（止盈/止损/回撤触发信号，输出「触发 + 距触发幅度 + 建议动作」，由 `analysis/trade_discipline.py::compute_discipline_signals` 计算，复用 `analysis/_silence.py` 静默期机制）；`rebalance_advice` 每项含 code/name/operation/shares/amount/fee/cash_after（可执行调仓建议清单，由 `analysis/rebalance_advisor.py::build_rebalance_advice` 可行化层计算——把再平衡/纪律触发信号转成订单，份额取整一手（A 股/场内基金 100 份，场外基金整数份，复用 `core/code_utils.py` 判定，并按持仓渠道 channel 优先——场外渠道强制整数份、覆盖 16/11 开头代码被场内前缀误判的场外持有场景，C1 合规）、费用估算（本地静态费率表：佣金/印花税仅 A 股/赎回费仅场外基金，场外渠道优先计收赎回费）、现金缓冲防负值、按优先级 止损 > 部分止盈 > 卖出减仓 排序）；`attribution` 为收益归因结果 `{"available": bool, "盈利来源": list[dict], "亏损来源": list[dict], "大类贡献": list[dict], "summary": str, "note": str}`——「大类 → 品种」两级同口径：大类层按 `core/code_utils.py::classify_holding_tier` 单源分类（报告分类页签 `_categorize_holding` 薄包装共用，分类判定唯一事实来源）聚合为权益/固收/现金（未知二元组兑底「其他」），品种层为 TOP5 按贡献占比（pp，非收益率）排序、正负分列 + 净额合计摘要；两层共用 Σ|profit| 分母（Σ大类 ≡ Σ品种），每项含 name/code/profit/contribution_pp（品种层）或 asset_class/profit/contribution_pp（大类层，|profit| 降序），`note` 为口径脚注句单源（`ATTRIBUTION_NOTE`，成本口径，非严格区间收益归因，HTML/Excel 同句消费），由 `analysis/return_attribution.py::build_return_attribution` 适配（复用共享纯计算 `compute_return_attribution`，与智囊团深度复盘提示词段落 `llm/prompts_core._build_profit_attribution_block` 同一数据两处呈现，零新增外部依赖）；无盈亏（Σ|profit|==0）或无持仓时 attribution=None，渲染层写「待生成」占位。由 `analysis/action_advisor.py::build_action_data` 计算（纯计算层，不依赖 report/），`report/orchestrator.py::prepare_report_data` 组装（full 路径 holdings_details 含 shares/price/channel/account——渠道上下文与账户名原值，按账户关键词 `is_offsite_fund` 判定场外/场内——供可行化层计算卖出份额与费用、收益归因大类分解单源分类），both 路径在 `_report_generation.py` 直接以 `build_action_data` 注入。三路径的组装口径：both/full 由编排层在历史走势就绪后组装（可带组合历史峰值市值），basic 不经编排层，由 `report/excel_generator.py` 在行情明细落成后就地构建——持仓明细统一经 `report/_report_helpers.py::_action_holdings_details` 投影（basic/both 共用同一字段子集，含 shares/price/channel/account），basic 无历史走势故 `portfolio_peak_mv` 缺省（组合级回撤纪律按「峰值未知」处理，不激活；止盈/止损等其余纪律不受影响）。消费方（同一对象两处呈现，C14/C19）：行动建议（HTML `partials/action_section.html`，Excel `report/action_sheet.py`）+ 智囊团深度复盘「行动摘要」子块；无持仓数据或开关关闭时 available=False / 不渲染，落 §1.4.5 降级占位。C7 注册：`action` 注册于 `_REPORT_SECTION_DEFAULT`（type=`action`、data_flag=`None`、number=7），独立顶层开关 `enable_action`（默认开，菜单 C 可切换）控制 board 层可见性，序号/名称可配置，不硬编码。本仓库 `config.json` 的 `report_section_order` 显式列出完整 18 项（`llm_usage` 强制末位、不列入本表；合计 19 个模块）且与出厂默认同序（`action`=7）；清空为 `{}` 效果相同。

### 附录 I：配置文件矩阵

> 与 §6.1 配置管理配套。按「5 个配置文件 × 缺省/模板 × 解析/读取 × 缺失时行为 × 写入方 × 消费方/消费模式」组织；各文件的「dict 缺省 + 模板函数」双结构模式见下文「模式小结」。

#### I.1 主矩阵

| 配置文件 | 缺省定义模块 | 模板生成 | 解析/读取入口 | 缺失时行为 | 写入方 | 主要消费方 |
|:---------|:------------|:---------|:-------------|:-----------|:-------|:-----------|
| `config.json`（基础配置） | `_config_defaults._DEFAULT_CONFIG`（A~M 共 13 组，含全部业务键默认值） | `_config_defaults._get_default_config_template()`（`_build_template_from_defaults()` 逐行手拼，保留分组注释） | `_core.get_config()`：mtime+size 双键缓存失效、null 过滤（不允许 null 覆盖默认）、嵌套 dict 子键浅合并、`_absolutize_paths()` 相对→绝对 | `init_config()` 自动创建（模板原子写入），并级联 `_ensure_llm_settings_file()` + `_ensure_llm_providers_file()` | `_core.set_config()`/`del_config()`（原子写，`_json_patch` 字段级文本替换保留注释）；TUI `handlers_config.py`（菜单改配置）；`config/anonymizer.py` | 全模块（`get_config()` 取合并后整表）。章节开关 `is_enable_*()` 系列 → `report/_report_generation.py`/`orchestrator.py`；`cache_ttl` → `cache/_ttl.py`；`degradation` → `report/data_status.py`；`market_hours`/`market_hour_ttl` → `core/market_hours.py`；`rebalance` → `analysis/rebalance.py`；`discipline` → `analysis/trade_discipline.py`；`anonymization` → `config/anonymizer.py`；`batch`/`batch_rate_limit` → `fetcher/batch.py`；`risk_free_rate` → `fetcher/bond_yield.py`；`preferred_provider` → `fetcher/chain.py`；`history` → `report/portfolio_history.py`；`default_menu_key` → `tui/tui_menu.py` |
| `llm_settings.json`（非敏感 LLM 设置） | `_llm_settings_defaults._DEFAULT_LLM_SETTINGS`（全局 2 项 + 5 模块块 + 辩论 + 事实校验 + 计价） | `_llm_settings_defaults._get_default_llm_settings_template()`（逐行手拼，与 dict 深等，见一致性测试） | `_llm_settings.get_llm_config()`：合并 settings+key+providers 三文件，联合 mtime/size 失效；`_merge_llm_defaults()` 运行时按 `_DEFAULT_LLM_SETTINGS` 补齐缺失键 | `_ensure_llm_settings_file()` 自动创建（`init_config()` 级联） | 无程序化写入（用户手动编辑；`_ensure_llm_settings_file` 仅首次创建） | `llm/pricing.py`（计价覆盖）、`llm/generators.py`、`llm/generators_orchestrator.py`、`llm/prompts_action.py`、`llm/skeleton.py`、`report/news_correlation.py`、`cli/cli.py`、`tui/tui_menu.py` + `tui/handlers_config.py`、`config/_validation.py` |
| `llm_key.json`（敏感凭据） | 无（**C18 凭据分离**，代码默认值禁止内置 api_key） | 无模板 | `_llm_providers._load_llm_key_credentials()`（多凭据块字典；单凭据 flat 自动升级为 `_default`）；`get_llm_config()` 内联读取并合并覆盖同名字段（provider/endpoint 合法性告警） | 不自动创建；缺失时 `get_llm_config()` 回退判断 providers 链模式，两者皆无则 LLM 不可用（`generators_orchestrator` 降级占位） | `startup_wizard._write_llm_key_flat()`（首次引导交互式写入，C3 原子写） | `get_llm_config()` 合并主体；`_load_llm_key_credentials()` → providers 链 `credentials_ref` 凭据注入 |
| `llm_providers.json`（多 Provider 链） | `_llm_providers_defaults._DEFAULT_LLM_PROVIDERS`（strategy=priority + 2 条示例链） | `_llm_providers_defaults._get_default_llm_providers_template()` | `_llm_providers._load_llm_providers()`（原始 JSON，根非 object/解析失败返回 None）；`get_llm_config()` 链模式（无 llm_key.json 时直接注入链数据）；`_inject_provider_chain_data()` 注入多链路由结果 | `_core._ensure_llm_providers_file()` 自动创建（`init_config()` 级联） | 无程序化写入（用户手动编辑 / init 自动创建） | `get_llm_config()`（链模式无 key 依赖）；`startup_wizard.py`（就绪检查：key 存在 或 providers 有链）；`_inject_provider_chain_data` |
| `features.json`（Feature Flag 覆写） | `features.feature_switch_registry`（26 项声明，每条含显示名 + 说明 + 作用域分组 + 默认值 + 是否改变产物 + 实验身份六项；`_FEATURE_FLAGS_DEFAULT` 是其**派生投影**，非独立登记点）。八组：💼 持仓与交易 4（成本流水 / 基金申购限购 / 持仓成本区间位置 / 风险调整超额） + 📈 市场与估值 4（估值分位 / 市场温度 / 危机回放 / 景气度框架诊断） + 🧩 基金与风格 3（因子目录 / 行业Beta子表 / 候选基金比较子表） + 📰 事件与摘要 4（事件窗量化对照 / 数据质量仪表盘 / 市场情绪与资金热点 / 本期要点与环比对照） + 🧭 呈现与交互 2（报告对话式追问 / 量化指标显示） + ⚙ 机制与质量 3（决策跨期反思闭环 / 确定性信号模块 / 模块级质量分级） + 📑 独立章节与回放 4（调仓纪律回放 / 持仓变动复盘 / What-if 交易成本对比 / 个股基本面） + 🧩 章节内选项 2（辩论-正反辩论 / 辩论-条件推理，由 `[C]` 作章节子项渲染）；**面板归属**：前六组在 `[S]`（`PANEL_GROUPS["[S]"]`，编号由 `features.panel_option_numbers` 派生），后两组在 `[C]`（分块与子项编号由 `config/chapter_registry.py` 派生）；含默认关的实验项 2 项（decision_reflection / report_qa）；联接基金穿透已内置恒开、无开关；分组即面板分块，是否进产物自述由（`experimental` ∧ `affects_report`）决定；**只登记有消费者的开关**——LLM 模块启停与基金深度分析归 `llm_settings.json` 的 `enabled_llm`，新闻源 / 历史走势 / 匿名化归 `config.json`，这些能力不再在 features.json 另立同义开关，由 `test_features.py::TestRegistryLiveness` 逐项守住；命令行一次性开关见 `features.resolve_experiment_flags` / `describe_experiment_flags`（`--experiment`，只开全部实验项）与 `features.parse_switch_override` / `resolve_switch_values` / `describe_switches`（`--feature NAME=VALUE`，全域、双向），两者与注册表同源 | `features._FEATURES_TEMPLATE`（中文说明 + 空对象；首次写入时落盘，只存覆写子集） | `features.load_feature_overrides()`（模块导入时自动调用，经 `core/json_comments.strip_json_comments` 剥离注释后解析，覆写合并进内存 `FEATURE_FLAGS`；无消费者键仍加载、但合并为一条 WARNING 列出键名——这类配置不驱动任何行为，静默忽略会让用户以为已生效；非 bool 值忽略） | **惰性创建**：缺失不创建、直接走代码默认；仅 `save_feature_overrides()` 时才写盘（以 `_FEATURES_TEMPLATE` 为底，含中文注释） | `features.save_feature_overrides()`（文本 patch 保注释：改值替换、恢复默认删键；`merge=True` 默认合并同名覆写）；TUI `handlers_config.py`（菜单开关持久化）+ Web `web/config_edit.py`（配置面板写入，白名单由注册表生成） | `is_feature_enabled()` 遍布：`llm/generators_singletons.py` + `generators_orchestrator.py`（辩论模式）、`report/_report_generation.py` + `report/_chart_dataset_factory.py`（量化指标总开关 / 本期要点与环比对照）、`report/_debate_utils.py`、`core/decision_ledger.py`（决策跨期反思闭环）、`llm/prompts_signals.py`（信号预消化，开关判定收敛于缓存后缀函数）、`report/llm_quality.py`（模块质量分级，§4.11）、`core/decision_header.py`（决策头结构化缓存后缀，§4.15）、`core/signal_ledger.py`（确定性信号沉淀，开关判定收敛于摘要函数，§4.16）、`core/doctor.py`（系统自检功能清单上屏，§4.17.3）、`web/handlers.py`（自检卡片可见性，§4.17.3 + 报告对话式追问路由门 `_handle_report_qa_ask`）、`analysis/circuit_breaker_wrapper.py`（量化指标总开关联动的熔断特性开关）、`tui/handlers_config.py`（菜单状态）、`tui/tui_menu.py`（菜单项门控）、`web/config_edit.py`（面板状态） |

##### I.1.1 解析职责归属（协调者 vs 委托）

> **config.json 的解析中枢在 `_core.py`，但不是独占解析器**：`_core.get_config()` 是 config.json 的唯一读取入口，注释剥离、路径绝对化分别委托 `_comments`/`_validation`，默认值合并以 `_config_defaults._DEFAULT_CONFIG` 为基准，null 过滤/嵌套子键合并由自身内联完成；其余 4 个配置文件各有独立解析器，`_core.py` 仅触发文件存在性（`_ensure_llm_settings_file()` / `_ensure_llm_providers_file()`），**不代解析**。

| 配置文件 | 解析协调者（入口） | 注释剥离 | 主要委托/依赖 |
|:---------|:-------------------|:---------|:--------------|
| `config.json` | `_core.get_config()` | `_comments._strip_json_comments()` | `_config_defaults._DEFAULT_CONFIG`（合并基准）；`_validation._absolutize_paths()`（相对→绝对）；null 过滤、嵌套 dict 子键浅合并由自身内联 |
| `llm_settings.json` | `_llm_settings.get_llm_config()` | `core/json_comments.strip_json_comments()` | **schema v2**（`defaults`/`modules`/`runtime`/`advanced`）：`_llm_settings._load_settings_document()` 版本校验 → `_llm_schema.merge_defaults()` 三层缺省 → `flatten()` 展平为消费方契约；写入经 `_llm_schema.apply_flat_updates()` + `_render_v2()`（值变化优先文本 patch 保注释） |
| `llm_key.json` | `_llm_providers._load_llm_key_credentials()` | `_comments._strip_json_comments()` | 单凭据 flat 自动升级为 `_default` 块（自持）；`get_llm_config()` 内联读取合并覆盖同名字段 |
| `llm_providers.json` | `_llm_providers._load_llm_providers()` | `_comments._strip_json_comments()` | 根非 object / 解析失败返回 None 判定（自持）；`_inject_provider_chain_data()` 链模式注入 |
| `logger.json` | `core/logger.py::_read_logger_config_file()`（启动时）/ `config/_logging.read_logger_config()`（面板） | `core/json_comments.loads()` | 日志级别/路径/轮转/查看器；`core/logger.py` 不导入 config 包（内联读取），面板经 `config/_logging` 同表校验；级别可被 `INVEST_LOG_*_LEVEL` 覆盖 |
| `llm_pricing_ref.json` | `_llm_pricing.load_pricing_config()` | `core/json_comments.loads()` | 参考数据：策略 + `models` 逐模型覆盖内置 `MODEL_PRICING`；缺失→内置价、版本不符→拒绝并回退、单条非法→告警跳过；不进编辑面 |
| `features.json` | `features.load_feature_overrides()` | `core/json_comments.strip_json_comments()` | 模块导入时自动调用；文件仅存需覆写的子集，首次写入以中文注释模板为底 |

> **参数范围校验**：`config/_validation_llm.py::LLM_PARAM_RANGES` 是模块参数合法范围的唯一来源
> （temperature 0–2 / max_tokens 1–200000 / timeout 5–600 / thinking.budget 1024–100000 / effort 枚举 /
> debate 合成温度 0–2 / 辩论单报告预算 1024–500000 / 辩论单次超时 5–600）。加载路径经
> `sanitize_document()` 越界回落到 `defaults` 或内置默认并逐条告警（只改内存视图，不改写用户文件）；
> 面板写入经 `edit_ops` 拒绝（文案含键名/当前值/合法范围），非法值不落盘。

> **注释契约**：五份配置文件（config / llm_settings / llm_key / llm_providers / features）均支持 `//` 与 `/* */` 注释，读取一律经叶子模块 `core/json_comments.strip_json_comments()`；写入走文本 patch（config 用 `_json_patch`、features 用键级 patch），保留既有分类注释与项说明。

#### I.2 消费模式

- **config.json — 全局整表共享**：所有模块经 `get_config()` 取合并后整表，按需读键；单入口缓存 + 双键（mtime+size）自动失效，无 per-key 订阅。章节可见性走 `_core.is_enable_*()` 读取器封装（缺失键返回各自默认值，语义见 §4.5 两层模型）。
- **LLM 三件套 — 合一层**：`get_llm_config()` 是唯一 LLM 配置入口，将 settings（非敏感主体）+ key（凭据覆盖）+ providers（链注入）合并为**单份 dict** 下发给生成器/计价/提示词层；消费方不直接读文件。settings 读取时 `_merge_llm_defaults()` 运行时补默认，避免消费端 `.get()` 硬编码兜底与模板默认值两套值漂移。
- **features — 全局内存开关 + 覆写文件**：默认值全量在代码内（`feature_switch_registry` 的 `default` 字段，`_FEATURE_FLAGS_DEFAULT` 是其派生投影），`features.json` 只存覆写子集；模块导入时自动加载覆写，消费方只调 `is_feature_enabled(flag)`，不感知文件存在与否。
- **凭据读写分离**：llm_key.json 是唯一「只写不自动读模板、无缺省」的文件——凭据由启动向导交互写入（C3 原子写），运行时由 providers 链 `credentials_ref` 或 `get_llm_config()` 合并引用，遵守 C18 凭据分离。

#### I.3 模式小结

| 模式 | 说明 | 应用文件 |
|:-----|:-----|:---------|
| **dict 缺省 + 模板函数 双结构** | 缺省值定义在 dict，模板函数逐行手拼 `"key": value,  // comment`；模板经 `strip_json_comments()` 剥离后 `json.loads` 与 dict **深等**（有一致性测试保证，防模板坏 JSON） | config / llm_settings / llm_providers 三家 `*_defaults.py` |
| 注释友好 JSON | `core/json_comments.strip_json_comments()` 剥离 `//` 与 `/* */`（正确处理字符串内转义），模板与真实文件均带中文分组注释；写入保留注释 | 全部配置文件 |
| 原子写入 | `tempfile.mkstemp` + `os.replace`，Windows 并发安全 | `set_config` / `save_feature_overrides` / `startup_wizard` / 缓存 `_write_atomic` |
| 路径绝对化 | `_DEFAULT_CONFIG` 存绝对路径（不依赖 CWD），模板存相对路径；运行时 `_validation._absolutize_paths()` 相对→绝对（模板生成前 `_deabsolutize_paths()` 反绝对化） | config.json 路径键 |
| 运行时补默认 | 读取时按缺省 dict 补齐缺失键，消除「消费端 `.get()` 兜底」与「模板默认值」两套默认值漂移 | llm_settings（`_merge_llm_defaults`）、config.json（`get_config` 合并） |
| 缺失时自动创建 vs 惰性创建 | config/llm_settings/llm_providers 缺失时由 `init_config()` 级联自动创建（C13 路径 seed）；features.json **不自动创建**（无文件即默认值，仅写入时才产生文件）；llm_key.json 永不自动创建（C18） | 见主矩阵「缺失时行为」列 |

[↑ 回到顶部](#目录)
