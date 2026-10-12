# 报告对话式追问（report_qa）迭代设计方案与实施计划

> 关联任务：plan-102（`docs/managements/plan.md` P3 预期实施）
> 版本：v0.12.11-dev · 状态：设计定稿
> 语义命名：功能 slug `report_qa`（报告问答追问）；本文所有代码标识符以此为准

---

## 1. 背景与重提条件

### 1.1 历史边界

v0.7 调研（`docs/archive/v0.7.x/better-investment-advice/discussion-better-investment-advice.md` §4.2 不做清单）放弃「反问引导模式」，理由为：

> 当前产品形态为单向报告（PDF/HTML/Excel），无法承载反问-回答的交互流程，放弃。若未来增加交互式报告或对话式 TUI 可重新考虑。

同期放弃的「开户/定投交互式对话」理由为「TUI 无交互承载场景，报告是单向输出」。

### 1.2 重提条件成立判定

| 归档重提条件 | 现状 | 判定 |
|:---|:---|:---|
| 交互式报告渠道 | Web 工作台已落地（Flask `web/app.py`，`/api/reports/<path>` 提供报告页；`runs.py` 任务队列 + 事件轮询） | ✅ 成立 |
| 对话式 TUI | TUI 菜单体系成熟（`tui/` 全套 handler），行输入 `input()` 处处可用，但无「文本输入循环/会话态渲染」设施 | ⚠️ 需新建轻量输入循环 |

结论：重提条件部分成立（Web 侧立即可行，TUI 侧需前置轻量输入循环设施）。plan-102 明确「评估阶段即计入 TUI 输入循环成本」，实现分阶段：Web 先行，TUI 增量接入。

### 1.3 用户痛点

报告生成后读者想追问（「为什么说集中度偏高？」「体检报告里我的波动率为什么上升？」）目前只能：

1. 重跑全量 LLM 模块（烧钱 + 慢，且新内容不回答「本期报告为何如此说」）；
2. 手改缓存文件（无支持路径）。

追问的正确语义是「就**本期已生成的报告**内容答疑」——上下文锚定已产出的报告，而非重新分析。

---

## 2. 目标与明确不做

### 2.1 目标（阶段 1-3：Web 报告页追问）

- 报告页（经工作台 `/api/reports/` 同源打开时）提供「就本期报告追问」输入框，读者提交问题后获得**基于本期报告内容**的多轮对话式回答。
- 回答上下文 = 本期报告全文（HTML 反解析）+ 会话内历史问答 + 报告关键数据摘要。
- 复用既有 LLM 基础设施：合规声明漏斗（`llm/compliance.py`，`call_llm` 入口集中注入）、失败降级、事实校验（`fact_checker.run_fact_check`）、日志/重试/节流唯一原语。
- 成本有界：上下文提取一次、会话内复用；轮数与单轮上下文双上限；回答不做结果缓存（§5）。

### 2.2 阶段 4（TUI 追问入口，随后增量接入）

- TUI 主菜单新增追问入口，进入「文本输入循环（复用 `input()` 的多轮 while 循环 + 退出指令，非全屏 TUI）」，调用与 Web 同一后端会话服务。

### 2.3 明确不做（守归档边界）

- **不做仓位硬建议**（「我该不该加仓 XX」不给操作指令）——v0.7 归档边界延续；
- **不做全市场筛选**（「帮我找低估股票」超出报告范围）；
- **不做报告外数据的实时问答**（追问只锚定本期报告，不引入新取数——追问期间零外部行情/新闻请求，数据链路零压力）；
- **不做跨报告会话持久化**（会话即问即走，服务重启/页面刷新即丢，与 Web run 状态同为内存态——见 §7 风险）；
- **不引入独立 HTTP 服务/CORS 机制**（追问只经工作台同源路径可用，`file://` 直接打开走引导文案，见 §3.5）。

---

## 3. 架构方案

### 3.1 总体数据流

```
报告页追问框（工作台同源打开 → fetch /api/qa/ask；file:// 打开 → 引导文案，不发请求）
    │ POST /api/qa/ask {report, session_id?, question}
    ▼
web/handlers.py::_handle_report_qa_ask        ← 路由层：参数校验 / report 路径净化 / 开关判定
    ▼
qa/session.py::ask_report_qa           ← 会话服务：线程安全会话表 / 轮数上限 / 用量记账
    ├── qa/context.py::extract_report_context   ← 上下文提取（首次提问惰性构建 + 会话内缓存）
    │       └── 报告 HTML → 纯文本 + 关键数据摘要（只读 output_dir 下报告文件，零取数）
    ├── llm/api.py::call_llm()         ← Provider Chain 必经（合规声明漏斗自动生效）
    └── llm/fact_checker::run_fact_check ← 回答数值事实校验（失败降级为原文 + 告警标注）
    ▼
JSON {answer_html, usage, remaining_turns} → 报告页内嵌会话区渲染
```

### 3.2 模块划分与语义命名

| 语义 slug | 落点 | 职责 |
|:---|:---|:---|
| `report_qa` | `src/python/qa/`（新子包） | 追问会话服务（线程安全会话表/轮数上限/用量记账/编排） |
| `report_qa_context` | `src/python/qa/context.py` | 报告上下文提取（HTML → 文本；关键数据摘要；截断策略） |
| `report_qa_ask` | `src/python/web/handlers.py::_handle_report_qa_ask` | Web 问答路由（POST /api/qa/ask） |
| `report_qa_session` | `qa/session.py::QaSession` | 单会话态（历史问答/轮数/用量累计） |

- `qa/` 为**独立子包**而非塞入 `llm/`：追问是「面向报告的服务」而非「LLM 报告模块」——不进 `_MODULE_FNS`、不进 LLM 模块注册（无模块级缓存条目、无指纹）；但其 LLM 调用仍经 `llm/api.py` 的 Provider Chain 路由。`llm/` 现 46 模块已近认知负担上限，新域独立成包降低技术债。依赖方向单向：`qa → llm`（api/fact_checker/markdown），`llm` 不感知 `qa`。
- **开关登记（功能开关注册表唯一事实来源）**：`config/features.py::feature_switch_registry` 新增 `report_qa`（`GROUP_EXPERIMENTAL`，默认关，`affects_report=True`——开关开启会在报告 HTML 追加交互区块，改变产物字节，故开态列入报告自述实验清单；转正时按形态入报告增强组）。TUI 面板/Web 面板/CLI `--experiment` 三端同源。
- **不登记 `core/registry.py::DataModuleDef`**：追问无模块缓存/无 TTL/不参与报告模块状态标签——登记会引入无真实调用方的注册项（违反「LLM 模块注册项必须有真实调用方」的反向要求）。

### 3.3 上下文构建（`qa/context.py`）

**输入**：报告文件名（前端从当前页 URL 提取，即 `_handle_serve_report` 同源路径下的文件名）。

**提取内容**（三段拼接为 system 上下文）：

1. **报告全文文本**：HTML → 纯文本（标准库 `html.parser` 去标签/脚本；保留标题层级与表格行列标记——表格数据是追问高频对象）；超过上下文上限时按「LLM 章全文保留 + 数据章摘要化」截断。
2. **报告关键数据摘要**：报告头部汇总区（持仓计数、总市值/盈亏、报告期、生成时间、开关自述行）——从 HTML 结构化区块提取，**不重新取数**。
3. **生成条件声明**：报告类型、生成时间——支撑「报告生成时的条件」类问题（对齐报告自述生成条件的既有纪律）。

**结构依赖收敛**：HTML 解析锚点（章标题 class、汇总区结构）集中在 `context.py` 单文件；报告模板契约变更时同步点唯一。提取失败（锚点全缺失）→ 显式错误「无法解析该报告结构，追问不可用」，不静默给错误上下文。

**约束遵守**：

- **零新增取数**：只读报告 HTML 文件，不触 `fetch_with_fallback`（数据源链路零压力）、不读 `pipeline_data`（未落盘，见 §5 权衡）；
- **路径净化与绝对路径**：output_dir 走 `get_config()` 绝对路径；report 参数经与 `_handle_serve_report` 同款净化（扩展名白名单 `.html` + `send_from_directory` 语义的 `..` 拒绝）；
- **渲染态数据经 context 传递**：上下文在服务对象内传递，不写模板 `_ENV.globals`；
- **隐私（凭据值不落日志原则延伸）**：上下文在内存传递，不落盘、不进日志正文（日志只记问题前 N 字符与 token 数）。

### 3.4 会话服务（`qa/session.py`）

- **会话表**：内存 dict `{session_id: QaSession}` + `threading.Lock`（Flask `threaded=True` 多线程并发，先例 `llm/session.py::_session_lock`）；上限 `_QA_SESSION_KEEP`（复用 Web run 管理的「内存态 + 上限 trim」先例）；
- **入参**：`report`（必填，报告文件名）、`question`（必填，长度上限校验）、`session_id`（可选，缺省新建）——同 session 必须同 report（换报告即新建会话，防上下文串味）；
- **轮数上限**：每会话 `_QA_MAX_TURNS`（默认 10）**硬界**；超限返回明确提示（「本轮对话已达上限，刷新页面开始新会话」）；
- **用量记账**：追问调用**不写** `llm/session.py::_session_usage`（那是报告周期统计，Web 常驻进程里追问会污染下一报告的 LLM 用量页签）；独立记账于 `QaSession.usage`（input/output tokens + provider），按轮返回前端。追问会话自身另设**输入 token 软上限**（`_QA_INPUT_TOKEN_CAP`，按字符数 × 系数估算），超限提示开启新会话——与既有「告警不截断」的报告预算语义解耦（追问是硬界场景：轮数 + token 双上限，无用户可见的预算配置依赖）；
- **事实校验**：回答 HTML 经 `run_fact_check()`（数值/品种一致性）；校验发现问题**不阻断返回**（降级为原文 + 质量告警标注，对齐既有口径）；
- **回答渲染**：回答 Markdown 经既有 `llm/markdown.py::markdown_to_html` 转 HTML（与报告 LLM 章同口径，不引入新净化机制——净化口径与报告一致是刻意选择，避免两套口径漂移）；
- **失败降级**：LLM 全链失败返回「服务暂不可用」占位（对齐 `fallback.py` 精神，问答不空白）。

### 3.5 Web 前端（报告页内嵌）

- **落点**：新增 partial `src/static/tmpl/partials/report_qa_section.html`（主模板 `report_template.html` 已 1180 行，按单文件行数红线原则只增 partial 不改主模板体量），`html_writer.py::render()` context 显式传 `report_qa_enabled`（渲染态数据经 context 传递，不写 globals）；
- **形态**：报告尾部追问区块——输入框 + 提交按钮 + 会话消息列表（问题/回答/剩余轮数）；JS 内嵌该 partial（报告是自包含可流转产物，不引用工作台 `/static/main.js`）；
- **可用性探测**：报告经工作台打开（同源）→ fetch 相对路径 `/api/qa/ask` 可用；`file://` 打开 → `location.protocol === 'file:'` 时区块显示「经 Web 工作台打开报告可使用追问」引导文案（零后端依赖、零 CORS 机制引入）；
- **开关控制**：`report_qa` 关闭时区块**不渲染**（模板分支，报告字节零变化，对齐「实验项默认关、关闭时产物不变」纪律）；
- **样式遵守** `DESIGN.md` 契约（六态/断点/空态文案 Data States 口径；空态 =「输入问题开始追问」，失败态 =「服务暂不可用」）。

### 3.6 架构约束对照（相关项逐条）

| 约束 | 本设计遵守方式 |
|:---|:---|
| Provider Chain 路由 | `call_llm()` 唯一调用入口（合规声明漏斗 `apply_compliance_guardrails` 自动生效） |
| credentials_ref 凭据分离 | 不触凭据；追问复用 `llm_settings.json` 既有配置与 provider 链 |
| 功能开关注册表唯一事实来源 | `report_qa` 登记 `features.py`（实验组，`affects_report=True`，默认关），三端同源 |
| 日志统一 | `logging.getLogger("invest")`；不 print；追问日志不含问题全文与回答正文 |
| 重试退避/间隔节流唯一原语 | 不自建重试循环与间隔睡眠；`call_llm` 内部既有退避/节流生效 |
| 路径绝对化 | output_dir 绝对路径经 `get_config()`；report 参数净化防穿越 |
| 渲染期数据不写全局 | 会话态在 `qa/session.py` 服务内；开关态经 render context 参数传递 |
| 大文件红线 | `qa/` 拆多文件（`__init__.py` / `context.py` / `session.py`），单文件预估 < 400 行；报告模板只增 partial |
| pipeline_data 契约 | 追问不新增 pipeline_data 键（上下文不进报告管线，零契约负担） |
| 缓存统一管理/原子写入 | 追问无持久化缓存（会话内存态）；报告 HTML 只读不写 |
| 会话级复用/数据链路 | 追问零外部取数（只读报告文件），链路/熔断/session_cache 零交互 |

### 3.7 与既有相似能力的边界

- **self_review（生成后自检）**：作用于生成期、走模块缓存、复核质量；追问作用于**生成后的人机对话**，无缓存、面向用户问题——输入/时机/去向均不同，不合并；
- **LLM 报告模块**（global_macro 等）：报告内单向产出；追问是会话式答疑——追问不触发任何模块重跑（`force_scope` 与追问正交：强刷重生成报告，追问答疑已生成报告）；
- **concentration_qa（集中度问答段）**：辩论流程内建的报告内「反问引导」段（单向输出）；追问是双向对话——两者是归档边界松动后的互补形态，不冲突。

---

## 4. 成本与缓存策略

| 维度 | 策略 | 理由 |
|:---|:---|:---|
| 上下文构建 | 会话内一次构建、多轮复用（`QaSession.context` 惰性字段） | 报告 HTML 不变，重复提取纯浪费 |
| 上下文注入方式 | 每轮「system(边界规则+上下文) + 历史摘要 + 本轮问题」 | 兼容无状态 `call_llm()`；历史仅保留问答纯文本（去 HTML），控 token |
| 历史保留 | 最近 `_QA_HISTORY_TURNS`（默认 6）轮，更早折叠为「已讨论要点」一行 | 防上下文线性膨胀 |
| 回答缓存 | **不做** | 问题空间开放、命中率趋零；缓存键/过期/载荷语义版本全套维护成本负 ROI（省维护债） |
| 成本硬界 | 轮数上限（10）+ 单轮输入 token 上限（估算式）双控 | 追问是交互硬界场景，不依赖可调预算配置 |
| 用量记账 | 独立于 `_session_usage`（不污染报告 LLM 用量页签） | Web 常驻进程，报告周期统计必须纯净 |
| 输出上限 | `call_llm()` 既有 max_tokens 参数 | 无新机制 |

成本估算（单轮）：上下文 8-15K input tokens（报告全文截断后）+ 历史 1-2K + 问题数百；10 轮会话上限 ≈ 100-170K input tokens——有界且仅在用户主动追问时发生（默认关，无静默成本）。

---

## 5. 关键权衡记录

| 决策 | 备选 | 取舍理由 |
|:---|:---|:---|
| 上下文从报告 HTML 提取 | 生成期落盘 pipeline_data 摘要（新持久化产物） | 落盘需管线挂载点 + 新缓存文件 + 失效对齐（报告删了摘要还在）+ pipeline_data 数据契约——技术债显著；HTML 提取零新增持久化、与报告天然同生命周期；结构依赖以单文件收敛 + 失败显式降级对冲 |
| `qa/` 独立子包 | 塞入 `llm/` | 追问非 LLM 报告模块（无缓存/不进 `_MODULE_FNS`/不进 LLM 模块注册）；`llm/` 已 46 模块；独立包降认知负担、依赖方向清晰 |
| 回答不做缓存 | 按问题哈希缓存 | 命中率趋零 + 键/过期/失效语义全套维护——负 ROI |
| 会话内存态 | 会话落盘持久化 | 与 Web run 状态同口径（重启即丢）；持久化引入清理/隔离/隐私面——先内存态，需求出现再评估 |
| 用量独立记账 | 复用 `_session_usage` | 后者是报告周期统计，追问跨周期调用会污染 LLM 用量页签与费用汇总 |
| 不引入 CORS/独立服务 | 报告页跨源调 localhost | 报告常被下载流转/`file://` 打开，跨源方案引入安全面与配置负担；同源路径已覆盖工作台主场景 |
| 开关默认关（实验组） | 默认开 | 追问产生真实 API 成本；实验组口径与既有能力一致，转正走评测先决（阶段 5） |

---

## 6. 分阶段实施计划（每阶段含可验收标准）

### 阶段 0：设计定稿（本文件）

- 交付：本设计文档 + `plan.md` 立项记录。
- **验收标准**：
  - [x] 架构约束逐条对照（§3.6）无遗漏项；
  - [x] 与代码现状事实一致（模板路径/渲染入口/预算语义/用量记账经实现层核对）；
  - [x] 语义命名先定名后设计（slug 无冲突，`report_qa*` 全仓未占用）。

### 阶段 1：后端会话服务 + Web 路由

- 交付：`src/python/qa/`（`__init__.py` / `context.py` / `session.py`）+ `web/handlers.py::_handle_report_qa_ask` + `features.py` 开关登记 + 单元测试（`src/test/unit/qa/`）。
- **验收标准**：
  - [x] `pytest src/test/unit/qa/` 全绿，覆盖：上下文提取（HTML→文本/截断策略/锚点缺失显式失败）、会话轮数上限、同 report 复用/换 report 重建、token 软上限降级、LLM 失败降级占位、事实校验失败不阻断、并发会话隔离（多线程 smoke）；
  - [x] 追问链路零外部取数（网络守卫 `conftest._block_external_network` 下通过，漏 mock 即硬失败）；
  - [x] `_handle_report_qa_ask` 校验矩阵：缺参/非法 report（路径穿越尝试）/开关关闭/question 超长 → 明确错误码（400/404/403）；
  - [x] `call_llm` 在所有测试中 mock（真实调用零容忍）；新测试文件带 marker（`unit_qa` 注册进 `conftest.py`）；
  - [x] ruff check/format 干净、`check-file-length` 通过、无任务编号入代码标识符与注释。

### 阶段 2：报告页前端区块

- 交付：`partials/report_qa_section.html` + `html_writer.py` context 接线 + JS 内嵌（同源 fetch / `file://` 降级探测）+ 样式契约遵守。
- **验收标准**：
  - [x] 开关关 → 区块不渲染、报告 HTML 字节与开关引入前一致（关态不变回归测试）；
  - [x] 开关开 → 区块渲染（模板快照测试）；`report_qa_enabled` 经 render context 传递（无 globals 写入断言）；
  - [x] 问答流程手测项（文档化）：工作台打开 → 提问 → 回答/剩余轮数渲染 → 超限提示；`file://` 打开 → 引导文案；
  - [x] 空态/失败态文案遵守 `DESIGN.md` Data States 口径；`test_design_doc.py` 契约测试通过。

### 阶段 3：端到端接线 + 文档

- 交付：Web 冒烟测试 + `manuals/how-to-use-web-mode.md` 追问章节 + `technical.md`（语义命名表 4 行登记 + 新章节）+ `llm-technical.md` 交叉引用 + `changelog.md` + `folders.md` 目录树 + `testplan.md` 用例计数。
- **验收标准**：
  - [x] Web 冒烟：mock LLM 下完整「提问→回答→多轮→超限提示→刷新重建」流程；
  - [x] 语义命名表登记 4 slug，`check-semantic-index` 正反向一致；
  - [x] 文档十守护（钩子）通过：doc-drift（目录树/统计）/doc-links/version-consistency 全绿。

### 阶段 4：TUI 追问入口（增量）

- 交付：TUI 文本输入循环（复用 `input()` 的多轮 while + 退出指令 `q`/空行，**不引入全屏 TUI 库**）+ 主菜单追问入口 + 调用同一 `qa/session.py` 会话服务。
- **验收标准**：
  - [ ] `pytest src/test/unit/tui/` 全绿：输入循环（提问/回答/继续/退出/EOF 守护）、与 Web 同源调用同一 `ask_report_qa`（无 TUI 私有副本断言）；
  - [ ] TUI 侧零重复实现：会话/上下文/记账/降级全部经 `qa/` 服务；
  - [ ] 手册 `how-to-use-tui-menu.md` 追问章节 + TUI 面板编号同步（doc-drift）。

### 阶段 5：转正评估（先决门槛）

- 触发条件：阶段 1-4 稳定运行后，按实验功能转正纪律评估（对齐既有转正先例）：追问回答质量抽检 + 成本实测 + 开关移出实验组。
- **验收标准**：
  - [ ] 抽检样本 ≥ 20 问（覆盖各章），事实校验通过率与用户可用性达标记录留档；
  - [ ] 转正走 `features.py` 分组变更（`affects_report` 语义复核）+ 三端文档同步。

---

## 7. 风险管理

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| LLM 幻觉（回答引入报告外数值） | 误导读者 | 事实校验复用 + 回答尾注「基于报告生成时数据，非实时」+ 不做仓位硬建议边界（system 规则声明） |
| 上下文提取依赖报告 HTML 结构 | 模板改版时提取退化 | 解析锚点单文件收敛（`context.py`）；锚点全缺失 → 显式报错不静默；模板契约变更同步点唯一 |
| 成本失控（长会话/长上下文） | 费用 | 轮数硬上限 + token 软上限 + 上下文截断 + 历史折叠四层有界；开关默认关 |
| `file://` 打开报告占比高 | 功能不可见 | 引导文案指向工作台打开路径；手册说明入口 |
| 会话内存态丢失 | 刷新丢历史 | 明确提示「刷新开始新会话」；上下文可重提取（惰性重建代价低） |
| 追问被用于索要仓位建议 | 越界 | system 规则声明边界（不做仓位硬建议/全市场筛选），规则随上下文注入 |
| Web 常驻进程内存增长 | 会话表泄漏 | 上限 trim（`_QA_SESSION_KEEP`）+ 会话随重启释放（内存态口径） |
| 报告文件被删/移动后追问 | 报错 | 上下文提取读文件失败 → 明确「报告文件不可用」提示，会话终止引导重新生成 |

---

## 8. 交付物清单总览

| 阶段 | 代码 | 测试 | 文档 |
|:---|:---|:---|:---|
| 1 | `qa/__init__.py` `qa/context.py` `qa/session.py` `web/handlers.py::_handle_report_qa_ask` `config/features.py` 开关 | `src/test/unit/qa/`：`test_report_qa_context.py` `test_report_qa_context_edge.py` `test_report_qa_session.py` `test_report_qa_session_edge.py` `test_report_qa_ask.py` | — |
| 2 | `src/static/tmpl/partials/report_qa_section.html` `report/html_writer.py` context 接线 | `src/test/unit/report/test_report_qa_partial.py`（区块渲染/样式 token 纪律/主模板 guard/关态字节回归） | — |
| 3 | — | Web 冒烟（`test_report_qa_ask.py::TestEndToEndSmoke`：提问→多次问答→超限→刷新重建） | `requirements.md`（§6.17 R-QA-01~09）`testplan.md`（批 13）`how-to-use-web-mode.md`（§3.6）`reports-instruction.md` `faq.md` `technical.md`（§6.8）`llm-technical.md`（§9.1 记账边界）`changelog.md` `folders.md` `test-coverage.md` |
| 4 | `tui/handlers_qa.py`（输入循环 + 菜单入口） | `src/test/unit/tui/test_handlers_qa.py` | `how-to-use-tui-menu.md` |
| 5 | `features.py` 分组变更 | — | 转正记录 + 三端手册同步 |
