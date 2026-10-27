# 开发者指南

> 文档版本：0.16.6

## 概述

面向本仓库开发者的一站式指南：开发环境与工作流、三级门禁、测试驱动、调试与剖析、扩展清单、注册表、版本发布。从日常编码到发布的全流程在此闭环。

> **纪律唯一来源**：本指南是面向人的"入口版"，代码注释、测试隔离、目录结构同步等完整纪律见 [CLAUDE.md](../../CLAUDE.md)，细节以该文档为准。

### 文档地图（谁管什么，真源在哪）

本仓库文档分工明确——**先看这张表，别在多份文件里找同一件事**：

| 文档 | 管什么 | 什么时候读 | 真源级别 |
|:-----|:-------|:-----------|:---------|
| **本指南** | 怎么开发：环境、门禁、测试、调试、扩展、发布 | 日常编码 / 新人上手 | 面向人（细节指向下列文档） |
| [CLAUDE.md](../../CLAUDE.md) | 工程纪律速查：分支、门禁清单、测试隔离、命名、编码 | 提交前对照 / 写新代码前 | **纪律唯一来源** |
| [technical.md](technical.md) | 架构设计约束（编号约束表）、语义命名表、实验项生命周期 | 改动设计、跨模块改动前 | 架构真源 |
| [requirements.md](requirements.md) | 需求 ID（`R-XXX-NN`）与描述 | 判断「这算不算需求变更」 | 需求真源 |
| [testplan.md](testplan.md) | 门禁完整口径、需求↔验证载体映射、回归清单 | 加/改测试、发布前 | 测试口径真源 |
| [DESIGN.md](DESIGN.md) / [DESIGN-TUI.md](DESIGN-TUI.md) | Web/报告与 TUI 的交互与视觉契约 | 动 UI 之前**必读** | UI 契约真源 |
| [scripts-reference.md](scripts-reference.md) | 每个辅助脚本干什么、怎么跑、何时跑 | 需要跑某个脚本时 | 脚本字典 |
| [folders.md](folders.md) | 目录树与统计快照（`--sync` 自动回写） | 新增文件后核对 | 结构性事实 |
| [test-coverage.md](test-coverage.md) | 各模式/子标记/功能域的用例计数 | 需要实时测试数字 | 派生物 |
| [plan.md](plan.md) / [review-findings.md](review-findings.md) / [changelog.md](changelog.md) | 计划 / 自审问题 / 变更记录 | 开工前、修缺陷后、发布时 | 台账真源 |

### 新人 30 分钟路径

1. **跑通环境**（本节下文 §开发环境与工作流）→ `.venv/bin/python scripts/test-runner.py --mode dev-verify` 能跑绿；
2. **读懂门禁**（§三级门禁）→ 知道「提交/合入/发布」各跑什么、失败了怎么办；
3. **写一个测试**（§新增测试指南）→ 按现有用例的骨架加一条，跑 `--lf` 验证；
4. **看一次发布**（§版本发布流程）→ 不必真发，读一遍命令链与各步断言；
5. **遇到问题**先查 §调试与剖析 与 §CI 失败排查。

> 只想改一个功能？直接跳到 §开发新功能：扩展清单——四类改动各有端到端清单。

## 目录

- [概述](#概述)（[文档地图](#文档地图谁管什么真源在哪) · [新人 30 分钟路径](#新人-30-分钟路径)） · [开发环境与工作流](#开发环境与工作流)（[pi 模型与服务配置（编程档采样 + 订阅端点节流 + 缓存/思考调优）](#pi-模型与服务配置编程档采样--订阅端点节流--缓存思考调优)） · [三级门禁](#三级门禁)（[编码/locale 自检（旧 pip 回退解码 / 隐式编码）](#编码locale-自检旧-pip-回退解码--隐式编码) · [日志回显纪律（要求改配置必给现值）](#日志回显纪律要求改配置必给现值) · [计划收尾：文档触点清单与一次性枚举](#计划收尾文档触点清单与一次性枚举)）
- [测试指南](#测试指南)（[前置条件](#前置条件) · [快速开始](#快速开始) · [只重跑上次失败的测试（`--lf`）](#只重跑上次失败的测试--lf) · [测试模式详解](#测试模式详解)） · [调试与剖析](#调试与剖析)（[日志：先看日志再看代码](#日志先看日志再看代码) · [交互式调试](#交互式调试) · [性能剖析](#性能剖析) · [测试慢或挂住的诊断](#测试慢或挂住的诊断)）
- [开发新功能：扩展清单](#开发新功能扩展清单)（[新增数据源 / Provider](#新增数据源--provider) · [新增报告章节（Excel 页签 / HTML 章节）](#新增报告章节excel-页签--html-章节) · [新增 Web 接口 / 面板](#新增-web-接口--面板) · [新增功能开关 / LLM 模块](#新增功能开关--llm-模块)） · [注册表使用（registry）](#注册表使用registry)（[核心数据结构](#核心数据结构) · [公共 API 速查](#公共-api-速查) · [新增数据模块（非 LLM）](#新增数据模块非-llm) · [新增 LLM 分析模块](#新增-llm-分析模块)）
- [任务编号规范与自动保障](#任务编号规范与自动保障)（[编号规则](#编号规则) · [编号源标记](#编号源标记) · [语义化命名](#语义化命名) · [外部借鉴前置比对清单](#外部借鉴前置比对清单)） · [版本发布流程](#版本发布流程)（[CI 失败排查](#ci-失败排查) · [回滚与热修](#回滚与热修) · [依赖升级流程](#依赖升级流程)）
- [辅助脚本速查](#辅助脚本速查)（[最常用十条](#最常用十条) · [按域索引](#按域索引)） · [关键纪律来源](#关键纪律来源)

## 开发环境与工作流

| 项 | 约定 |
|:---|:-----|
| **默认工作分支** | `dev`（日常开发、提交均在此分支） |
| **发布分支** | `master`（仅从 dev 合并，打版本标签后发布） |
| **语言** | 中文（UI、报错、报告内容） |
| **Python 环境** | 所有 Python 命令一律使用项目虚拟环境解释器——Linux/macOS 用 `.venv/bin/python`，Windows 用 `.venv\Scripts\python.exe`；**禁止**裸 `python3`/`python`/`pytest`（会命中系统解释器，缺失 pandas 等依赖）。运行测试、脚本、CLI 均同 |
| **提交规范** | 约定式提交：`feat`/`fix`/`docs`/`refactor`/`test`/`chore`/`perf`/`ci` + 可选 scope；修复类可在标题标注对应任务编号 |
| **日志** | `logging` → `logs/app.log` + console（INFO / WARNING / ERROR） |
### pi 模型与服务配置（编程档采样 + 订阅端点节流 + 缓存/思考调优）

本项目**版本受控**的 pi 配置分两个文件，作用域机制不同：

| 文件 | 作用域 | 生效条件 |
|---|---|---|
| `.pi/models.json` | 模型覆盖 | 软链到 `~/.pi/agent/models.json`（pi **不读**项目级 models.json） |
| `.pi/settings.json` | 项目设置 | **pi 直接读项目级 settings.json**，但需 `~/.pi/agent/trust.json` 已授予该项目信任 |

`.pi/models.json` 的覆盖分两类：

**① 编程档采样（`deepseek` 按量端点）**

| 覆盖项 | 值 | 为什么 |
|---|---|---|
| `samplingParams.temperature` | `0.0` | DeepSeek 官方建议：**代码生成/数学解题用 0.0**（通用对话 1.3、创意写作 1.5）；低温让补丁/重构更确定、减少格式抖动 |
| `maxTokens` | `65536` | 内置目录值 384K 对编程偏大；收窄到 64K 仍远超常规补丁/文件写入需要，同时给单次响应设成本上限。**注意思考（reasoning）与正文共享该预算**——预算被思考吃满时正文会被截断 |

> **覆盖键必须与目录当前模型 id 精确匹配**：id 不一致时该覆盖**不生效且无任何告警**（pi 侧按 `Unknown override IDs are ignored` 处理，静默忽略）。因此 **`pi --list-models` 是本文件的唯一验收手段**——JSON 已写入不等于生效；目录同步（内置目录升级、`/model` 重载）后须复核各覆盖仍命中，否则 `maxTokens`/`contextWindow` 会悄悄退回目录默认值。

**② 订阅端点节流（`kimi-coding` / `opencode-go`）**

订阅制端点（Kimi Code / OpenCode Go）按**滚动时间窗**计量，窗口额度按「交互式 agentic coding」标定；而 pi 的自动压缩阈值是 `contextTokens > contextWindow − reserveTokens(默认 16K)`，目录里这些端点 `contextWindow` 高达 1M——**压缩几乎不触发，每轮请求要把近百万 tokens 的上下文发出去**，几个轮次就吃掉一个窗口。故对这两类端点统一收窄（**只降不升**，已低于上限的模型不写覆盖）：

| 覆盖项 | 值 | 为什么 |
|---|---|---|
| `maxTokens` | `65536` | 目录值 128K~384K（如 `grok-4.6` 500K）对编程无必要，且思考与正文共享该预算 |
| `contextWindow` | `262144` | 把「压缩触发点」从 ~1M 拉到 ~246K → **单轮输入封顶**，这是降窗口消耗的最大单项；代价是压缩更频繁、跨轮记忆略少 |

**③ 思考档位（全局，不在本文件）**：`~/.pi/agent/settings.json` 的 `defaultThinkingLevel` 设为 `low`（原 `high`）。思考 token 计入 output，实测输出量≈输入量是其主因；需要时用 `/thinking` 临时提升。

**④ 提示缓存保留（`PI_CACHE_RETENTION=long` + `promptCache` 声明）**

缓存命中把重复前缀按缓存读价计费（DeepSeek 缓存读约为标准输入价的 1/10），所以要尽量让前缀「热着」。这条链需要**两个条件同时成立**，缺一即静默无效：

| 环节 | 载体 | 作用 |
|---|---|---|
| 选择保留档 | shell 环境变量 `PI_CACHE_RETENTION=long`（`~/.bashrc`） | `getPromptCacheTtlMs` 按该值选 `long` 档；未设置则恒为 `short`。解析顺序：凭据块 `env` → `process.env` → Bun 沙箱回退 |
| 声明生命周期 | `.pi/models.json` 覆盖项 `promptCache` | **目录里没有任何模型声明 `promptCache`**，未声明时 `getPromptCacheTtlMs` 返回 `undefined` → 该模型**无缓存保活资格**，环境变量设了也白设。故对 pi 实际使用的按量模型（`deepseek-flash`/`deepseek-v4-pro`）显式声明 `{short: 300, long: 3600}`（取已公布区间的保守端） |

缓存保活本身**消耗额度但不占上下文**（保活请求以 1 token 输出重发，用量计入会话统计，不进模型上下文）；pi 仅在「模型声明了生命周期」且「估算避免的未命中成本 ≥ $0.05」时才保活，故不是盲目刷量。

> **刻意不下发到订阅端点**：`kimi-coding`/`opencode-go` 按窗口计量，保活刷新会白吃窗口额度，而收益取决于端点是否真支持提示缓存（未实测）。这是**待测量项**，不在本配置内。

**⑤ 思考预算（`thinkingBudgets`，`~/.pi/agent` 之外的 `.pi/settings.json`）**

内置档位预算为 `minimal:1024 / low:2048 / medium:8192 / high:16384`（`xhigh`/`max` 亦 16384）。合并语义是 `{...内置默认, ...自定义}`（`thinkingBudgetForLevel`），**故只需写要改的档位**，未写档位继续用内置值。当前只压最低两档（`minimal:512`、`low:1024`），**`medium`/`high` 保持内置**——它们承担用 `/thinking` 提升后的复杂推理，压掉会让升档失效。

**⑥ 诊断开关（`showCacheMissNotices: true`）**

开启后上屏显著缓存未命中、缓存保活成功、**压缩用量**、provider 恢复四类通知。这是排查「额度去哪了」的主观测口：压缩一次要读整个上下文，其用量此前完全不可见。

**未改动**：`thinkingLevelMap`（内置 `low/high/max` 已够用，用 `/thinking` 切档）、`compat`（`thinkingFormat` 等由 pi 内置目录提供）、`input`（flash 为纯文本，视觉实验版另有一个模型）、`samplingParams`（仅对 OpenAI 兼容传输生效；订阅端点走 Anthropic/兼容协议时该参数不适用，故未对它们下发）。

**为什么模型覆盖放在 `.pi/` 而要软链生效**：pi CLI **只读** `~/.pi/agent/models.json`（`getModelsPath() = getAgentDir() + "/models.json"`，`getAgentDir()` 只认 `PI_AGENT_DIR` 或 `~/.pi/agent`），**不读项目级 `.pi/models.json`**；项目级 `.pi/` 仅支持 `settings.json`/扩展/技能/主题。因此模型覆盖的仓库文件是**唯一事实来源**，用软链挂到全局路径生效（`settings.json` 走项目级路径，无需软链）：

```bash
ln -sf "$PWD/.pi/models.json" ~/.pi/agent/models.json
```

验证与排查：

- **`timeout 90 pi --list-models | grep -E 'deepseek|kimi|opencode'`**：`deepseek-flash` 应显示 `65.5K`、`kimi-coding`/`opencode-go` 应显示 `262.1K / 65.5K`；仍是 `1M / 384K` 即**覆盖键名已失效**（目录改名），按上文修正键名
- 出现 `Warning: errors loading models.json` 说明 JSON/schema 有问题
- **项目设置是否生效**：`.pi/settings.json` 依赖项目信任（`~/.pi/agent/trust.json` 里该项目为 `true`）；未授予信任时项目设置被整体忽略，而 `.pi/models.json` 因走软链不受影响——两者失效条件不同，排查时分开看
- 订阅端点用量激增时的排查顺序：① `--list-models` 确认覆盖生效 → ② 会话是否超长（`/new` 分任务）→ ③ 思考档位是否被 `/thinking` 提升 → ④ 打开 `showCacheMissNotices` 看压缩用量与缓存命中
- 若 `~/.pi/agent/models.json` 已是实体文件（例如以后 `/login` 或 `pi config` 写过），软链会失败：先备份再决定合并

## 三级门禁

按开发阶段逐级收紧的质量屏障，与测试模式的关系见下：

| 门禁 | 触发点 | 命令 | 说明 |
|:-----|:-------|:-----|:-----|
| **P0** | 提交前 | `.venv/bin/python scripts/test-runner.py --mode dev-verify` + 十守护（`--ci` 全套，钩子自动执行） | 阻塞提交，不得 commit |
| **P1** | 合入 master 前 | `.venv/bin/python scripts/test-runner.py --mode verify`（全部 `unit_*` 目录域，含 TUI/CLI——归域即进门禁，`technical.md` §4.23） | 阻塞合入，不得 merge |
| **P2** | 发布前 | `.venv/bin/python scripts/release.py gate`（= 演进对照新鲜度断言〔当前开发版列头日期须为当日〕+ **verify 与 regression 并行**（verify 提前到合并前拦截）+ 十守护 `--ci` 全套〔并行执行，并发度随核数收敛 ≤4 路〕+ 设计护栏；`--with-portability` 追加 portability 探针，gate 自动编排） | 阻塞发布，不得 release |

**P0 提交前门禁**（全部通过才可 commit；手动项 = dev-verify，下列十守护由 pre-commit 钩子在 `git commit` 时自动执行、CI guards job 同源兜底，本地不手动重复——清单为五处同源引用）：

```bash
.venv/bin/python scripts/test-runner.py --mode dev-verify   # 核心单元 + 基础场景快速验证
.venv/bin/python scripts/check-code-traces.py --ci          # 代码注释历史痕迹 + 任务编号标识符 + 日志统一 + 配置默认值单源检查
.venv/bin/python scripts/check-doc-traces.py --ci           # 文档历史痕迹 + 结构性冗余检查
.venv/bin/python scripts/check-task-numbering.py --ci       # 任务编号全局一致性检查
.venv/bin/python scripts/check-semantic-index.py --ci       # 语义命名索引正反向校验
.venv/bin/python scripts/check-doc-drift.py --ci            # 文档与实现一致性（章节/开关/默认值/面板编号/目录树/统计表/归档索引/分区纪律/占位归档节/树描述计数/Thinking 支持矩阵/章节-区块矩阵/需求菜单表/手册菜单块）
.venv/bin/python scripts/check-test-redundancy.py --ci      # 测试用例冗余与无效（死用例/无断言/完全重复/自证用例/硬编码演进总数/恒真断言/死 fixture/弱 mock 断言）
.venv/bin/python scripts/check-requirement-trace.py --ci   # 需求 ID ↔ 验证载体追溯（已补全域全覆盖 + 载体文件存在）
.venv/bin/python scripts/check-version-consistency.py --ci   # 版本号全局一致性（APP_VERSION ↔ README/pyproject/管理文档 10 份）
.venv/bin/python scripts/check-doc-links.py --ci              # 文档死链/死锚点/重复标题/层级/编号序列/§引用机检
.venv/bin/python scripts/check-file-length.py --ci         # 单文件行数红线（主程序/脚本 >1000 行 / 测试 >1200 行）
```

> **`--sync` 统计快照口径（CI 分叉坑）**：`check-doc-drift --sync`（及 pre-commit 自动回写）按**工作区**实测写入 `folders.md` 行数，而 CI 的 `check-doc-drift` 按 **committed** 树实测——若受检目录存在**长期不提交的修改**（本地游离改动），本地已同步的数字会在 CI 上判「不一致」，连带 guards / test / portability 三个 job 同时红。提交前确认受检文件全部纳入本次提交；有长期游离修改时先提交它们、再 `--sync`。
>
> **写者顺序（`--sync` 必须是收尾的最后一个写者）**：统计表数字是「行数 × 用例数」派生量，**任何改文件的步骤都会让刚同步的数字重归陈旧**。因此 `ruff format` / `ruff check --fix` / `test-collect-coverage.py --update-docs` / 批量编辑等写者**全部在 `--sync` 之前**完成，`--sync` 之后只做**只读**校验（`dev-verify` / 守护回放 / `--ci`）。典型踩坑：先 sync → 再 `test-collect-coverage --update-docs`（改写 `test-coverage.md`，managements 行数又变）→ 跑 `dev-verify` 时 `test_check_doc_drift_crosscheck` 报「行数与实测不一致」。真跑反了也不要紧：重新 sync 一次即可，不是代码问题。
>
> **钩子触发面 = 全部被统计的域**：`docs/managements/`（文档行数）、`src/test/`（测试行数 + 用例数）、`src/python/`（主程序行数）、`scripts/`（脚本行数）任一变更，`git commit` 即走 `--sync` 写路径自动回写并 `git add`。只覆盖部分域时，纯 `src/python`/`scripts` 改动会以「行数不一致」finding 拦下提交、逼人工 sync 再重提（多一轮往返）。

**P1 合入门禁**：`test-runner.py --mode verify`（全部 `unit_*` 目录域单元测试，含 TUI/CLI；目录归域以 `check-test-markers.py` 期望表为准且全部入门禁），否则不得 merge。

**P2 发布门禁**：

```bash
.venv/bin/python scripts/test-runner.py --mode regression              # 场景回归（单元由 P1 合入门禁 + CI master 档覆盖）
.venv/bin/python scripts/check-code-traces.py --ci
.venv/bin/python scripts/check-doc-traces.py --ci
.venv/bin/python scripts/check-task-numbering.py --ci
.venv/bin/python scripts/check-semantic-index.py --ci
.venv/bin/python scripts/check-doc-drift.py --ci
.venv/bin/python scripts/check-test-redundancy.py --ci
.venv/bin/python scripts/check-requirement-trace.py --ci
.venv/bin/python scripts/check-version-consistency.py --ci
.venv/bin/python scripts/check-doc-links.py --ci
.venv/bin/python scripts/check-file-length.py --ci
```

**辅助（非阻塞）**：`.venv/bin/ruff check`（lint 基线，选择项与刻意豁免均在 `pyproject.toml` 显式声明）+ `.venv/bin/ruff format --check`（代码格式一致性）——问题可经 `.venv/bin/ruff check --fix` / `.venv/bin/ruff format` 自动修复，不阻止合并/发布。当前两者均为零告警基线，新增代码应在提交前保持干净。

**CI 同步执行（`.github/workflows/ci.yml`）**：三档测试按分支/标签分流——`dev` 推送跑 P0（`dev-verify`）、`master` 推送或 PR 跑 P1（`verify`）、打 `v*` tag 跑 P2（`regression`），矩阵覆盖 Python 3.11/3.12/3.13；另有三个独立 job：`guards`（**阻塞**，10 个 `--ci` 守护脚本即上方 P0/P2 清单全量——job 内按 pre-commit 同款后台并行回放，任一守护非零退出折叠为 FAIL 分组并使 job 红；守护经 src.python 链依赖项目运行时包（如 check-doc-drift → httpx），故 editable 安装保留）、`portability`（**阻塞**，非 UTF-8 locale + 隐式编码双探针，见下方「编码/locale 自检」）与 `format`（非阻塞，`ruff format --check src/python/ scripts/` + `ruff check`）。

### 编码/locale 自检（旧 pip 回退解码 / 隐式编码）

本机与 CI 的常规三道测试全跑在 **UTF-8 locale** 上，因此「旧 pip 对含非 ASCII 的需求文件回退 locale 解码」与「未显式 `encoding=` 的文本 I/O」这两类缺陷在常规门禁上**结构性不可见**（中文 Windows cp936 用户首启就装不上依赖、报告写盘时静默变 GBK）。两道精确探针已入 CI `portability` job（阻塞），且都能在任意平台本地复现——**一条命令等价复现**：

```bash
# CI portability 等价复现：①隐式编码严格档（单元套件）+ ②需求文件 BOM/PEP263 判定 + LC_ALL=C 解析烟测
.venv/bin/python scripts/test-runner.py --mode portability
```

> 该模式非 pytest 模式，计数量是**探针项数**；不进 bench/门禁清单，按需手动跑（改编码相关代码、动 `requirements.txt` 或 `pytest.ini` 编码选项后建议跑一次）。当前 pip ≥25 起默认按 UTF-8 解码需求文件，`LC_ALL=C` 烟测不再经过旧 pip 的 locale 回退分支，故模式内以**确定性判定（BOM/PEP263）**承担该缺陷类，并提示「完整判定需 pip ≤24.x」。

如需逐条手工复现（排查探针本身是否失效时）：

```bash
# ① 旧 pip（最后一版按「BOM → PEP263 cookie → locale 编码」解码）在非 UTF-8 locale 下真实解析需求文件：
#    LC_ALL=C 是同类 locale 回退的最严档（ASCII 单字节，任何非 ASCII 字节必炸）；
#    去掉 requirements.txt 的 BOM 可复现原缺陷（UnicodeDecodeError）
python -m pip install -q "pip==24.3.1"
LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 python -m pip install --dry-run --no-deps -r requirements.txt

# ② PEP 597 隐式编码严格档：任何未显式 encoding= 的文本 I/O 立即失败（豁免项见 pytest.ini）
PYTHONWARNDEFAULTENCODING=1 .venv/bin/python -m pytest src/test/unit -q
```

> ①号命令在受 PEP 668（externally-managed-environment）系统级管理的解释器上会被拒：装进临时 venv 复现，或追加 `--break-system-packages`（`--dry-run` 不做实际安装，无风险）；CI 的 setup-python 环境不受此限。

> 为何不直接跑 Windows runner：GitHub 的 `windows-latest` 是 en-US/cp1252（单字节，只会乱码不会报错），装不住 GBK 类 locale 回退；为何不在 ubuntu 上装 GB18030 跑全套件：中文**文件名**在 POSIX `fsencoding=ascii` 下会失败（18 处中文报表文件名），而 cp936 Windows 反而正常——那是探测方法的伪影，不是缺陷。两道探针因此取「精确模拟消费方」而非「换整个 locale 跑全套件」。

> **CI 轮询纪律**：本地门禁（P0/P1/P2 + 必要时的 `--mode portability`）通过后，**不逐提交轮询 CI**——本地绿而 CI 红的来源本应只有环境差异（3.11/3.12/3.13 矩阵、`LC_ALL=C` locale 探针、系统库/可选依赖、`perf-gate`/`format` 等 CI 独有档）。为收口这类差集，portability 已可本地等价复现；其余档位仅在改动触及它们时才去看 CI 结果。

> **钩子与守护输出的编码**：pre-commit 以 `export PYTHONUTF8=1` 统一守护子进程的日志编码，`scripts/_shared/checklib.py` 导入时把非 UTF-8 的真实 stdout/stderr 收敛到 UTF-8（`_force_utf8_stream`，已 UTF-8 或 `StringIO` 桩零改写）——中文 Windows 上 stdout 重定向到文件按 locale ANSI（cp936）落盘，UTF-8 终端回放 `run_bg` 守护日志会成乱码；前台直打走控制台 `WriteConsoleW` 本就无损。

> P1/P2 的完整要求（含手动验证项）见 [testplan.md](testplan.md) → 回归测试清单 / 门禁章节。

### 日志回显纪律（要求改配置必给现值）

凡日志 / CLI / TUI 输出**要求读者调整某个配置值**（并发、间隔、上限、超时、重试、开关等），必须**同时回显该项的当前值与配置项名/所在文件**，使读者不翻配置即可知道「从多少调到多少」：

- **回显形态**：`<config_field>=<值>`、`（当前 X → 已试 Y）`、`provider[<条目>] pacing.max_concurrency=<值>、pacing.min_interval=<值>`；配置里**未声明**时标「未配置」而非留空（避免误读为 0/已配）。
- **密钥/凭据类豁免**：涉及 `api_key` / `llm_key.json` / `data_key.json` / token / password 的提示只回显**文件名、条目名、路径**，绝不回显密钥本体或其片段（对齐 `scenario_security` 的「日志不记录完整密钥」基线）。
- **已覆盖点**：429 诊断 `pacing._concurrency_hint`（两级并发 + 间隔，由 `api_base` 重试骨架复用）、截断提示 `api_base._check_*_truncation`、思考耗尽 `api_base._extract_content`（配置上下文由 `_process_success_response` 经线程局部注入）与 `_api_claude` 安全网日志、截断重试耗尽 `skeleton._handle_truncation`、worker 钳位 `fetcher/batch.py`、阈值超限 `providers/news_dedup.py`。
- **回归用例**：`test_llm_api_base.py::TestThinkingExhaustedConfigEcho`、`test_llm_api_attempt.py::TestAttemptApiCall` 429 回显组（含 `test_rate_limit_429_log_echoes_min_interval_value_when_advised`）、`test_llm_api_retry_errors.py` 429 首试熔断零重试 + 503/超时重试链、`test_skeleton.py::test_exhausted_retry_log_names_config_field_and_both_values`、`test_llm_api.py::test_thinking_exhausted_log_echoes_current_budget`。新增此类日志时按本节口径补回显与用例。

### 计划收尾：文档触点清单与一次性枚举

任务收尾的墙钟主因是「文档触点 × 往返轮次」——触点靠守护报错被动驱动时，每轮报错就是一次完整往返。按任务类型对照下表**主动扫一遍触点**，再按三步工作流收敛：

**触点清单（按任务类型）**：

| 任务类型 | 必同步触点 |
|:---------|:-----------|
| 新报告章节 | `registry.py` 注册表 → `reports-instruction.md`（目录/章节表/分组表/可见性总表/页签上限）→ `requirements.md` 章清单 → `technical.md`（结果区计数/`report_section_order`）→ `how-to-use-tui-menu.md`（面板编号段）→ `folders.md`（新 partial/模板）→ `report_template.html` include |
| 新功能开关 | `features.py` 注册表 → `how-to-config.md`（开关表+计数+实验/常规分列+Web 面板行）→ `how-to-use-tui-menu.md`（开关区行与编号）→ `how-to-use-web-mode.md`（Web 面板分组行）→ `technical.md`（语义命名表/开关计数）→ **`experimental=True` 时 `technical.md` §6.9 生命周期表补行** → `testplan.md`（若涉门禁） |
| 开关合并/内置化（删条目） | 本地 `features.json` 旧键清理（本项目不保留跨版本兼容，直接删）→ 注册表计数与四组分解（`how-to-config` / `how-to-use-tui-menu` / `how-to-use-web-mode` / `technical` 语义表与统计行）→ **面板编号单次重排**（`[S]` 各组分块区间在多处手册出现）→ 消费点门控收敛（`config/_core.py` helper 与调用点）→ 关态用例退役 |
| 菜单项增删/合并/重排 | `tui_menu.MENU_ITEMS` + `tui_menu.MENU_GROUPS`（任务分组：新增项必须入组，退出项除外；分组覆盖由用例守护；含页脚键位提示 `render_menu` 与退出别名文案）→ 双手册主菜单 code block（`how-to-start` + `how-to-use-tui-menu`，doc-drift 机检键集合与标签头）→ `how-to-config.md` 的 `default_menu_key` 快捷键清单 → `technical.md` 菜单表 + 项数（静态项数 / 默认门控后渲染项数两处）→ `testplan.md` 菜单清单与二级子菜单 → `status_line.ACTION_TEMPLATES` 动作短语（首键须在主菜单，用例守护）→ README 界面描述 → 子菜单二级键集合（如 `[D]` 的 C/F/O/M/B） |
| 新增终端打印文本（提示/面板/列表） | 一律用 `tui/text_layout.py` 原语折行（`wrap_display` / `wrap_hanging` / `wrap_with_prefix` / `truncate_display`）并按 `terminal_columns()` 取宽——手机窄屏（40~60 列）与笔记本宽屏同一份代码；盒线面板经 `switch_panel.render_titled_panel`（宽/中档画框、窄档无框截断），表格/日志/统计等长输出在窄档折行；**新增或改动任何面板渲染后，必须在 `test_narrow_panel_render.py` 登记同一面板**（`COLUMNS=40` 逐行断言不超宽）；提示语成分与上屏词先对 `DESIGN-TUI.md`（键分工总表 / 提示三段式 / 术语对照）；新增用例须覆盖窄宽两档与「不越界」不变式 |
| 新增/改动 TUI 交互（键义、提示、反馈、配色） | `DESIGN-TUI.md`（唯一判据：键分工总表 / 提示模板 / 默认项标注 / 配色一色一职责 / 术语表）→ 契约结构测试 `test_design_tui_doc.py`（必备小节若扬则同步）→ 机检 `test_prompt_contract.py`（提示成分 / 禁用词 / 闸门白名单）→ `how-to-use-tui-menu.md` 对应面板章 → `test_keystroke_baseline.py` 击键基线（多一次按键即刷新快照）→ `requirements.md` R-TUI |
| 新配置入口（新增面板/子菜单项） | `_CONFIG_ENTRY_MAP`（`[D]` 配置入口地图，键位真实性由单测对 `MENU_ITEMS` 兜底）→ 对应手册章节 → `requirements.md` 菜单表行 |
| 新文件/目录 | `folders.md` 目录树（`check-doc-drift --sync` 回写统计表）→ 若为 `scripts/*`：[scripts-reference.md](scripts-reference.md) 的一览与分类段 |
| 新测试 | `conftest.py` marker 注册（若需）→ `.venv/bin/python scripts/test-collect-coverage.py --update-docs` 回写 `test-coverage.md`/`folders.md` 计数行（不带标志仅输出供人工对照）→ 边缘用例入 `*_edge.py` |
| 新 LLM 模块/seam | `registry.py` + 统一附录（`skeleton._build_prompt_appendix`）+ `technical.md`（语义命名表/seam 表/附录 H）→ 指纹条件并入用例 |
| 每个计划收尾（通用） | `plan.md`（状态翻转+归档 note）→ 当期计划归档文档（归档段+设计文档索引，入 0.12 期归档）→ `review-findings.md`（rf 登记，rf-next 递增）→ `changelog.md`（含 rf token）→ `test-coverage.md`/`folders.md` 计数刷新 → 涉版本时 `check-version-consistency` |

**三步工作流**：

1. **一次枚举**：编辑全部完成后按下方「计划收尾：文档触点清单」主动扫触点批量核对/修复（统计快照回写与十守护校验由提交时的 pre-commit 钩子自动完成，本地不手动重复）。
2. **批量修复**：按上表 + 触点一次性修完，同一文件多处改动合并为一次 edit。
3. **单次复核**：手动只跑 `dev-verify` 测试门禁；ruff 探针（错误类阻塞 + format 非阻塞提示）与十守护一并交由 `git commit` 的 pre-commit 钩子一次收集（失败即中止）→ 批量修复 → 重新提交，不手动重复跑守护。

**红线**：编辑批次与 `--sync`/检查类脚本**永不同批**（sync 写文件，与编辑并行会竞态）；**所有写者（编辑 / `ruff format` / `test-collect-coverage --update-docs`）必须在 `--sync` 之前完成，sync 之后再无写入**（否则刚回写的统计数字又变陈旧，`dev-verify` 报「行数与实测不一致」）；`check-file-length` 随每批代码改动跑，ruff 由钩子在提交时把关（批内可提前手跑），不留到收尾才爆。

## 测试指南

**测试报告布局**：每次运行写入 `test-reports/latest/`——汇总页 `index.html`（各模式的通过/失败/耗时 + 报告链接）与该模式的 pytest-html 详细报告。单轮/非分阶段模式为 `<mode>/report.html`（`dev-verify` 已双阶段合一，单轮报告即此名）；**多阶段模式每阶段一个报告文件**（`<mode>/report_phase_A.html` / `report_phase_B.html`），汇总页逐阶段给链接。早前两阶段曾共用 `report.html`，后跑的阶段会覆盖前者，导致详细报告只剩最后一阶段（排查时看不到真正的失败面）——多阶段逐文件机制即为防此。

测试框架基于 **pytest**，通过标记（marker）分组支持灵活组合运行，使用 `scripts/test-runner.py` 统一驱动并自动输出结构化报告。各 `--mode` 的精确测试项数统计见 [test-coverage.md](test-coverage.md)。

### 前置条件

```bash
# 安装测试依赖
pip install pytest pytest-html pytest-mock pytest-xdist
# 可选：覆盖率报告
pip install pytest-cov coverage
```

> 以上仅安装测试插件。项目主依赖（httpx、openpyxl、akshare 等）见 `requirements.txt`：`pip install -r requirements.txt`。

### 快速开始

```bash
# 查看所有可用选项
.venv/bin/python scripts/test-runner.py --help

# ===== ① 日常常用（快速反馈，提交前验证） =====

# 提交前快速验证（P0 门禁；耗时因机器而异，参考 test-coverage.md）
.venv/bin/python scripts/test-runner.py --mode dev-verify

# 冒烟测试（快速验证核心通路）
.venv/bin/python scripts/test-runner.py --mode smoke

# 仅运行业务场景测试
.venv/bin/python scripts/test-runner.py --mode scenario

# 集成测试（含场景 + 模块间契约/缓存/TUI 路由）
.venv/bin/python scripts/test-runner.py --mode integration

# 全量单元测试（含 edge/data）
.venv/bin/python scripts/test-runner.py --mode unit

# 常规单元测试（排除 edge/data）
.venv/bin/python scripts/test-runner.py --mode standard

# ===== ② 专项验证（定向覆盖） =====

# 仅运行边缘/异常场景测试
.venv/bin/python scripts/test-runner.py --mode edge

# 极限场景（超多持仓/极端值/高精度）
.venv/bin/python scripts/test-runner.py --mode scenario_extreme

# 数据正确性验证
.venv/bin/python scripts/test-runner.py --mode data

# 真实网络验证（opt-in，不入门禁，仅排查数据源连通性时手工运行）
.venv/bin/python scripts/test-runner.py --mode live

# 运行全量 + 行覆盖率报告
.venv/bin/python scripts/test-runner.py --coverage

# ===== ③ 全量/CI 门禁（耗时较长） =====

# 开发期快速验证（6 个 unit 子模块并行 + 基础场景）
.venv/bin/python scripts/test-runner.py --mode dev-verify

# 合入验证 — PR 前检查
.venv/bin/python scripts/test-runner.py --mode verify

# 全量测试（--mode verify,regression 覆盖单元+场景）
.venv/bin/python scripts/test-runner.py --mode verify,regression

# 全量测试（排除单元测试，快速全场景覆盖）
.venv/bin/python scripts/test-runner.py --mode all_no_unit
```

### 只重跑上次失败的测试（`--lf`）

修复代码后验证时，经常只需要重跑**上一次运行失败的那些用例**，而不必等全量通过。pytest 内置的 `--lf`（`--last-failed`）标志专为此场景设计：

```bash
# 只重跑上次 pytest 运行中失败的测试（跳过已通过的）
.venv/bin/python -m pytest src/test/ --lf

# 先收集匹配 marker 的用例，再从其中只重跑上次失败的
.venv/bin/python -m pytest src/test/ -m "unit_providers" --lf
```

**与 `test-runner.py` 的配合**：

`test-runner.py` 使用 `argparse` 管理参数，**不支持** `--` 透传（例如 `.venv/bin/python scripts/test-runner.py --mode all -- --lf` 会报错）。如需 `--lf`，绕过它直接调 pytest，用 `-m` 参数复现目标模式的标记表达式：

```bash
# 先找到目标模式对应的 marker 表达式
# 在 scripts/test-runner.py 的 MODES 字典中查找，例如：
#   regression → "scenario"
#   unit       → "unit"
#   verify     → "unit_core or unit_providers or unit_fetcher or unit_config or unit_news or unit_llm or unit_analysis or unit_scripts or unit_web or unit_qa or unit_report"

# 然后用 pytest -m + --lf 组合运行
.venv/bin/python -m pytest src/test/ -m "scenario" --lf                  # 等价 --mode regression 的失败重跑
.venv/bin/python -m pytest src/test/ -m "unit_providers" --lf            # 等价 --mode unit 下 unit_providers 的失败重跑
.venv/bin/python -m pytest src/test/ -m "unit_core or unit_providers or unit_fetcher or unit_config or unit_news or unit_llm or unit_analysis or unit_scripts or unit_web or unit_qa or unit_report" --lf  # 等价 --mode verify
```

> 各 `--mode` 对应的 `-m` 表达式见下文「模式与覆盖范围说明」章节，或直接查看 `scripts/test-runner.py` 中 `MODES` 字典的 `marker` 字段。

**工作原理**：pytest 在每次运行后，将失败用例记录到 `.pytest_cache/lastfailed` 文件；`--lf` 读取该文件，只收集文件中的用例执行。如果上次运行全部通过，`--lf` 会提示 `no tests ran`（因为没有失败记录）。

**典型工作流**：

```
# 1. 跑全量 → 发现 N 个失败
.venv/bin/python -m pytest src/test/ -m "edge"

# 2. 修复代码

# 3. 仅重跑失败的 N 个（5 秒而非 5 分钟）
.venv/bin/python -m pytest src/test/ -m "edge" --lf

# 4. 全部通过后，再用无 --lf 的全量确认没有回归
.venv/bin/python -m pytest src/test/ -m "edge"
```

> ⚠ **注意**：
> - `--lf` 依赖上次运行生成的 `.pytest_cache/lastfailed` 文件。如果清理了 `.pytest_cache/` 或切换了虚拟环境，`--lf` 不会生效。此时只需先正常跑一次目标模式生成失败记录即可。
> - 另一相关标志 `--ff`（`--failed-first`）会**先跑上次失败、再跑全部**，适合修复后确认修复 + 检查回归一步到位。
> - `test-runner.py` 不支持 `--lf`，是因为它用 `subprocess.run` 调 pytest 且 argparse 不接收未注册的 `--` 参数。建议日常快速验证时直接使用 `pytest`，门禁检查时再用 `test-runner.py`。

### 测试模式详解

测试框架围绕两个概念组织：**pytest 标记（marker）** 是测试用例的固有属性（标注"这是什么测试"）；**`--mode`** 是 `scripts/test-runner.py` 脚本对标记的预定义组合（定义"应该运行哪些测试"）。每个 mode 对应一个或多个标记表达式，脚本解析后传给 `.venv/bin/python -m pytest -m` 执行。

#### 回归测试级别

每个回归项按影响范围分四级，与三级流水线的对应关系：

| 级别 | 定义 | 阻断点 | 对应的流水线阶段 |
|:-----|:-----|:-------|:----------------|
| **P0** | 阻塞提交 — 核心功能不可用 | 不得 commit | ① `dev-verify` |
| **P1** | 阻塞合入 master | 不得 merge | ② `verify` |
| **P2** | 阻塞发布 | 不得 release | ③ `regression` |
| **P3** | 建议修复 | 不阻断 | — |

P0 问题必须在 commit 前解决，否则代码不应进入版本控制。P1 问题允许提交但不允许合入主分支。P2 允许合入主分支但不应发布版本。P3 属于已知缺陷或待优化项，可带缺陷发布。

> 注意：P0-P3 是**问题影响力分级**，regression/verify/all 是**测试范围分级**，两者通过门禁阶段关联但不一一对应。例如 P0 问题恰好在 regression 模式中被检出，但 regression 模式并非仅包含"P0 级别"的测试用例——它覆盖全量业务场景，其中任何一项失败都可能导致 P0 阻断。

> **耗时说明**：测试耗时与硬件/操作系统/并行度强相关，不同机器上可能相差一个数量级，因此本文档不标注具体秒数。各模式耗时对照见 [test-coverage.md](test-coverage.md)（「环境耗时对照」表，按机器分列实测）——需预估耗时先在表中定位本机环境列；耗时表为 bench **多模式采集**（并行度见环境属性表「采集并行度」行；`test-runner --jobs N` 默认 1 串行，显式 N>1 多档并行提速但含模式间 CPU 争抢，跨并行度不与串行基线直接比）。若本机未在表中，可运行 `.venv/bin/python scripts/test-runner.py --mode bench --update-docs` 自动采集回填。

#### 三级验证流水线

项目推荐的四道质量门禁，按开发阶段逐级收紧：

- **提交前门禁（`--mode dev-verify` / P0）** — commit 前必须执行。组合 9 个 unit 子模块（unit_core/unit_providers/unit_fetcher/unit_news/unit_analysis/unit_scripts/unit_web/unit_qa/unit_report，并行）+ 基础业务场景（`scenario_basic`），排除 edge/data 和极限场景。是编辑-验证循环中的正式屏障。
- **全场景回归（`--mode regression`）** — commit 前可选的全场景补充验证。覆盖全部 `scenario` 业务场景测试（S0a/S0b/S0d + S1-S33 + T1-T21），确保端到端用户路径不被破坏。推荐在改动了跨模块路径或数据流后补充运行。
- **合入验证（`--mode verify` / P1）** — 准备合并到 master 前必须执行。覆盖 `unit_core`（核心基础设施：缓存引擎、数据模型、注册表）、`unit_providers`（数据源 Provider：腾讯、东方财富、天天基金等）、`unit_fetcher`（数据获取调度：价格、指数、行业分类）、`unit_config`（配置管理）、`unit_news`（新闻聚合）、`unit_llm`（LLM 模块）、`unit_analysis`（分析计算：流动性/再平衡/汇率/债券收益率等）、`unit_scripts`（工程脚本：历史痕迹/版本一致性/任务编号检查）、`unit_web`（Web 入口：上传/运行/进度/产物）、`unit_qa`（报告对话式追问：上下文提取/会话服务/报告页路由门）、`unit_report`（报告生成：Excel/HTML/模板/管线）十一个单元模块。确保数据从抓取→缓存→计算的整条管道通畅且正确。并行执行。场景测试已在 P0 dev-verify（基础场景）和 P2 verify,regression（全场景）中覆盖，P1 不重复。
- **发布验证（`--mode regression`）** — 发布版本（打 tag/release）前必须执行。覆盖全部场景回归测试。
  > 注：**简化口径已采纳（2026-10-07，详见 [testplan.md](testplan.md) → §6.3 脚注）**：本项目发布流程强制 `dev → merge → tag master`，P1 合入门禁（`--mode verify`）与 CI `master` 档（同提交 verify）已双重覆盖单元验证，tag 档 CI 同步只跑 `regression`；直接从 dev 打 tag（绕过 P1）属流程违规。若流程约束放宽（允许直接发布 dev），须恢复 `--mode verify,regression`。

> `regression` 与 `scenario` 底层使用相同的标记表达式（`-m "scenario"`），前者是语义别名——强调"提交前快速回归"的用途定位；后者是分类名——强调"业务场景测试"的数据性质。两者可互相替代，但建议按使用场合选用对应名称以增强代码意图可读性。

**推荐工作流：**

```
编码 → --mode dev-verify → commit → 多次积累 → merge → P1 --mode verify → release前 → P2 --mode regression
          ↑                                    ↗
    改完代码随时跑                      若改跨模块调用
      提交前必过P0门禁                  先跑 --mode integration
```

在一次典型开发周期中：
1. **提交前门禁验证**：修改代码后运行 `--mode dev-verify` 确认核心单元+基础场景通过（P0 强制）
2. **全场景补充验证**：若改动了跨模块路径/数据流，再跑 `--mode regression` 确保全场景正常
3. 如果改了跨模块调用关系（缓存、新闻流水线、TUI 路由等），再跑 `--mode integration` 确认接口契约和全链路正常（CI test job 对 `-m integration` 标记**恒跑兑底**，本地按需先行可更快反馈）
4. 如果改了 Provider、缓存或数据获取逻辑，再跑 `--mode verify` 确认整条管道通畅
5. 通过后 commit，积累多次提交后准备合并到 master
6. 合并前 CI 自动跑 `--mode verify` 作为合入门禁
7. 发布版本前 CI 自动跑 `--mode regression` 场景回归验证（单元由 P1 master 档覆盖）

#### 模式与覆盖范围说明

每种 `--mode` 对应一组 pytest 标记表达式，由 `scripts/test-runner.py` 转换为 `.venv/bin/python -m pytest -m "<表达式>"` 执行。各模式的覆盖范围存在包含与被包含关系，理解这种关系有助于缩小验证范围以快速反馈：

##### 单元测试系列（`unit` / `standard`）

- **`--mode unit`** 覆盖所有标记为 `unit_*` 的测试（12 个子组：providers、fetcher、llm、news、report、config、core、analysis、ui、cli、scripts、web），不含场景测试。这是对代码库中各独立模块的功能正确性验证，所有网络请求均为 mock，不依赖外部 API。
- **`--mode standard`** 在 `unit` 基础上排除 edge（异常边界）和 data（数据正确性）两个跨类标记，仅保留"常规路径"的单元测试。适用于日常开发中快速验证模块本身逻辑正确，不需要关心边界情况。

##### 场景测试系列（`scenario` / `regression` / `integration` / `verify`）

- **`--mode scenario`** 覆盖带 `scenario` 标记的场景测试（4 个子组：basic、resilience、llm、datetime；`scenario_extreme`、`scenario_perf`、`scenario_security` 不携带该标记，分别由 `--mode scenario_extreme` / `perf` / `security` 单独运行）。这些测试模拟真实用户操作（如菜单 E/B/L 生成报告），组合多个模块进行端到端验证。

  场景测试按职责分为 **7 大类**：

  - **`scenario_basic` — 基础业务链路**：验证正常业务流程，包括纯股票/纯基金/混合多账户的市值穿透计算、缓存首次/命中逻辑、特殊品种（港股通/可转债/REITs/货币基金/科创板/北交所/商品ETF/跨境ETF/纯债）的正确分类和计算，以及持仓质量边界（清仓不计入、同名多份额合并、特殊字符不乱码（超多持仓 S0c 在 scenario_extreme）），以及操作行为场景（S29-S33：分红送转除权/定投成本摊薄/部分调仓卖出/跨账户转仓/新股中签待上市）。
  - **`scenario_resilience` — 异常容错场景**：验证系统在非正常输入或环境下的降级能力，包括纯债券基金组合（穿透无股权覆盖）、网络中断（价格从过期缓存读取）、单账户单持仓、零成本持仓（不除零崩溃），以及数据链路韧性（多源故障级联熔断、冷却期试探、熔断器持久化、LLM 端点独立熔断）。
  - **`scenario_extreme` — 极限场景**：验证极端数据下的正确性，包括超多持仓（S0c，200+ 条批量计算）和极端值（S10，超大/极小份额、高精度净值、零值组合）。标记 `scenario_extreme`，不包含在 `scenario` / `scenario_basic` / `scenario_resilience` 中，需单独运行 `--mode scenario_extreme`。
  - **`scenario_llm` — LLM 场景组合**：验证 LLM 模块在各种状态下的行为，包括缓存/成功/失败混合状态的颜色渲染、五种失败原因独立映射、Extended Thinking 标记、禁用优先原则、断网降级、全缓存无调用、三种输出格式（Excel/HTML/Summary）一致性。
  - **`scenario_datetime` — 日期/时间场景**：验证系统在不同市场时段（盘中/盘前/午休/盘后/非交易日/长假）、产品类型（场外基金/QDII/ETF/股票/混合）、边界条件（时段切换/缝隙/首次启动/断网）以及特殊日历（跨年/季末/汇率故障/调休/港股通假期）下的数据获取正确性和降级表现。
  - **`scenario_perf` — 性能基准场景**：以 mock 持仓与 mock API 跑 20 品种全量报告生成管线，记录各阶段耗时分布建立性能基线（basic 模式目标 <60s，>120s 判失败）。
  - **`scenario_security` — 安全基线场景**：5 项安全基线自动化验证——密钥文件权限不可公开读取、缓存写入器产出的条目不含明文密钥、匿名化模式报告不含真实名称/代码、LLM 调用层源码不把 `api_key` 写进日志语句（静态守卫）、HTML 模板不含绝对文件系统路径（产物扫描）。

- **`--mode regression`** 与 `--mode scenario` 完全相同，但语义定位为"提交前回归验证"。建议在 git hook 或 CI 前置检查中使用此名称，使流水线意图更加清晰。
- **`--mode integration`** 覆盖场景测试 + 集成测试（`scenario or integration`）。在全部业务场景基础上，增加模块间验证：接口契约、错误隔离、新闻流水线、缓存一致性、TUI 路由。用于修改了跨模块调用关系后的定向回归。CI test job 以 `pytest -m integration` 恒跑纯集成契约档（50+ 例 / ~5s，不依赖分支条件），本地改跨模块时仍建议先行 `--mode integration`。
- **`--mode dev-verify`** 提交前门禁模式（P0），组合 9 个 unit 子模块（unit_core/unit_providers/unit_fetcher/unit_news/unit_analysis/unit_scripts/unit_web/unit_qa/unit_report，排除 edge/data）并行 + 基础业务场景（`scenario_basic`）。约 20s，适合开发者改完代码后随时跑。不包含极限场景（scenario_extreme）和 LLM/日期/容错等专项场景。
- **`--mode verify`** 合入门禁模式（`unit_core or unit_providers or unit_fetcher or unit_config or unit_news or unit_llm or unit_analysis or unit_scripts or unit_web or unit_qa or unit_report`），包含核心基础设施 + 数据源 Provider + 数据获取调度 + 配置管理 + 新闻聚合 + LLM 模块 + 分析计算 + 工程脚本 + Web 入口 + 报告对话式追问 + 报告生成的单元测试，共约 10s（并行执行）。场景测试由 P0 dev-verify（基础场景）和 P2 verify,regression（全场景）覆盖。

##### 专项验证系列（`edge` / `data` / `smoke`）

- **`--mode edge`** 仅运行标记为 `edge` 的测试，覆盖各种异常和边界情况：零值、空数据集、并发竞态、Unicode、时区安全、文件系统边界、API 网络异常等。适用于修改了函数内部错误处理逻辑后的针对性验证。
- **`--mode data`** 仅运行标记为 `data` 的测试，覆盖数据精确性：市值=价格×份额、盈亏=市值-成本、收益率=盈亏÷成本（成本>0）、穿透 TOP10 占比归一化等。适用于修改了数值计算逻辑后的回归。
- **`--mode smoke`** 仅运行标记为 `smoke` 的测试，从 6 个全流程关键节点各选 4 项最快基础测试：核心数据模型→入口读取→分类计算→报告输出→启动依赖→数据获取。全部为纯内存计算、无 IO、每项 <0.1s（速度参考见 `test-coverage.md`）。适用于部署后冒烟或极速"通不通"检查。

##### 真实网络验证（`live`，opt-in，不入门禁）

- **`--mode live`** 运行真实外部网络验证套件（`src/test/live/`），用于排查「数据源是否真的可达 / API 是否漂移」时手工验证。**平时（含 dev-verify/verify/all 全量门禁）完全不运行**——由三层机制保证：
  1. `pytest.ini` 的 `addopts = -m "not live"` 在收集期直接排除；
  2. `conftest.py` 的 `_skip_live_unless_requested` autouse fixture 默认跳过（`-m live` 收集到也 skip）；
  3. `_block_external_network` 阻断 fixture 对非 live 项一律拦死真实网络。
- **非 live 用例的断网机制（2026-09-26 收紧）**：守卫只阻断**建连**（`socket.socket.connect`/`connect_ex`、`create_connection`、`getaddrinfo`），**不阻断 `socket.socket()` 构造**——否则会误伤第三方库的**导入期**探测（urllib3 导入期构造 socket 且仅被 `except Exception` 包住，硬化后会直接使库导入失败）。抛出的 `NetworkBlockedInTests` 继承 `BaseException`（而非 `RuntimeError`）：provider/fetcher 普遍用 `except Exception` 降级，用 `Exception` 子类会被静静吞掉，使漏 mock 退化成“验证网络被阻断后的降级”并白等链路瞬时重试退避（实测 unit 模式 1072 次未 mock 尝试 / 300 次退避睡眠 / 累计 149.3s 空等）。
- **不依赖外部数据的文件写 `offline_external_sources`**：报告/编排/集成类用例的**附带依赖**（交易日历/行业数据/行情/健康探针/akshare 直连路径）常在未被 mock 时被真实访问。这类文件在模块级加 `pytest.mark.usefixtures("offline_external_sources")`，由 `src/test/_network_guard.py::apply_offline_stubs` 把仓内 HTTP 出口（`httpx.Client`）、交易日历、akshare（`sys.modules` 级）换成“即时取不到”，并把 `fetcher.chain._TRANSIENT_RETRY_BACKOFF`（链路级）与 provider 级重试策略（腾讯/东方财富 K 线、财务指标多期）退避一并置 0（仓内既有测试惯例）——链路口径仍为“源不可用→降级”，但零网络、零等待。需要验证某源真实行为的用例**必须自行 mock**，不得用本 fixture 遮掩。
- **等待型 `sleep` 由离线桩统一接管（2026-10-21）**：同 fixture 另把 `core.throttle` / `core.retry` / `providers.cninfo` / `providers.datasink` 的**模块级 `time`** 换成 `_NoWaitClock` 代理——`sleep()` 变空操作（间隔节流、多策略退避、429 限速重试窗口不再白等），`monotonic`/`perf_counter` 原样透传（间隔判定与超时判据仍用真实时钟，零等待不等于零判据）。作用域只有这四个模块对象，因此**测试自身的 `time.sleep`**、以及**验证等待语义的用例**（`test_throttle` / `test_phase_timeout` / `test_batch::TestRateLimiter` / `test_handlers::test_queue_full_429` / provider 的退避断言）完全不受影响；未声明离线的文件等待语义原样保留。实测 `dev-verify` 墙钟中位 37.3s → 24.0s（−36%），用例数与断言强度不变。
- **内容**：覆盖行情（A 股/ETF/场外基金/中美指数）、新闻源（东方财富/财联社/新浪/华尔街见闻）、基金（历史净值/排名/基准）、akshare 交易日历共 **14 个用例**（行情 5 / 新闻 4 / 基金 3 / 交易日历 2）。
- **断言原则**：只校验返回「结构」（字段存在、类型、非空），**不校验具体数值**，容忍真实行情波动（休市、涨跌、数据源改字段）。
- **不含 LLM 真实调用**（防费用）——LLM 连通性由运行时数据源健康检查覆盖。
- 触发方式：`.venv/bin/python scripts/test-runner.py --mode live` 或 `.venv/bin/python -m pytest --run-live -m live`。

##### 数据源真实响应录制与回放（cassette）

**要解决的问题**：数据源单元测试全部喂**手工构造的假响应**，测的是「我以为上游长什么样」。上游字段改名、值加前后缀、换分隔符、错误页返回 HTML 这类回归，**只有真实响应体测得出**。cassette 把上游真实响应体录进仓库，此后离线回放——既有真实数据，又不碰网络，且随默认套件入门禁。

| 组成 | 位置 |
|:-----|:-----|
| 回放引擎 | `src/python/core/cassette.py`（只依赖 stdlib + httpx + `core.http_client`） |
| 解析器绑定表 | `src/python/fetcher/cassette_checks.py`（cassette 名 → 当前解析器调用） |
| 已录制响应 | `src/test/data/cassettes/*.json`（git 跟踪） |
| 回放回归用例 | `src/test/unit/providers/test_cassette_replay.py` |
| 录制用例 | `src/test/live/test_live_cassette_record.py` |

**在用例里用已录制响应**——声明所需 cassette，运行期自动离线回放，用例内的 provider 调用照常写：

```python
pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]

@pytest.mark.cassette("tencent_quote", source="腾讯行情")
def test_tencent_quote_parses(self):
    data = tencent.fetch_price("600519")     # 响应来自 cassette，不联网
    assert data["price"] == pytest.approx(1285.13)
```

**刷新/新增录制**（显式联网动作，双开关缺一不可）：

```bash
# 录制全部登记的 cassette 并即时回放自检
.venv/bin/python scripts/test-runner.py --mode live --record-cassettes

# 只录一个
.venv/bin/python -m pytest -m live --run-live --record-cassettes \
    src/test/live/test_live_cassette_record.py -k tencent_quote
```

新增一个 cassette 需要三处同步：绑定表加一条解析器调用（`CASSETTE_CHECKS`）、录制用例加一个 `@pytest.mark.cassette(...)` 测试、回放回归用例加精确值断言。

**离线保证与非目标**：

- 回放**未命中即失败**（`CassetteMissError`），**绝不回落真实网络**——避免「以为在回放、实则在联网」。该异常刻意不继承 `httpx.HTTPError`，否则 provider 会把它当成网络错误降级到别的源，掩盖夹具缺失。
- 非 live 用例的真实请求已被 `conftest.py` 的 `_block_external_network` 拦死，**机制上不可能意外产生录制**。
- 录制产物进 git（每份几 KB ~ 百 KB），**不入门禁的 live 套件**；夹具刷新须走上面的显式开关。
- 维护入口：`cassettes`（列出）/ `cassettes --verify`（离线回放 + 交当前解析器解析，失败退出码 2），见下节「CLI 子命令」。
- 与「HTTP 客户端统一」约束的关系：回放寄生于「所有 HTTP 请求必须经 `core/http_client.py` 工厂」；绕过工厂自建客户端的 provider 不受回放替换，其用例会真实联网且静默通过。设计细节见 `technical.md` §2.6。

##### 可移植性探针（`portability`，非 pytest 模式，不入门禁）

`--mode portability` 复现 CI `portability` job 的两道探针（不是 pytest 套件，故**计数量是探针项数**，不进 bench 与三档门禁清单）：

```bash
.venv/bin/python scripts/test-runner.py --mode portability
```

| 探针 | 做什么 | 判定 |
|:-----|:-------|:-----|
| 隐式编码严格档 | `PYTHONWARNDEFAULTENCODING=1` 跑 `src/test/unit` | 任何缺 `encoding=` 的文本 I/O 立即失败（`pytest.ini` 把 `EncodingWarning` 升 error） |
| 需求文件 locale 解码 | `requirements.txt` 的 BOM/PEP263 判定 + `LC_ALL=C` 下 `pip install --dry-run --no-deps -r` 烟测 | 无 BOM/cookie 即判失败；解析异常即判失败 |

> 改编码相关代码、动 `requirements.txt` 或 `pytest.ini` 编码选项后建议跑一次——本地通即与 CI 该 job 同档；当前 pip ≥25 默认 UTF-8 解码需求文件，模式会提示「完整判定需 pip ≤24.x」，确定性判定（BOM/PEP263）始终生效。

##### 全量（`all`）

- **`--mode verify,regression`** 组合模式，等价于分别运行 verify（单元） + regression（场景）。约 30s，作为发布门禁。
- **`--mode all`** 不设任何标记过滤（`.venv/bin/python -m pytest src/test/`），运行全量测试。需要全覆盖时手动调用。
- **`--mode all_no_unit`** 排除所有单元测试与联网测试（`-m "not unit and not live"`），仅保留场景测试、集成测试和跨类测试。适用于想要全场景覆盖但跳过纯模块逻辑验证的场景。

##### 多模式组合

`--mode` 支持逗号分隔同时运行多个模式：

```bash
# 同时运行场景测试和边缘测试
.venv/bin/python scripts/test-runner.py --mode scenario,edge
```

脚本按 MODES 字典定义的 order 顺序依次执行各模式，结果汇总到同一份 HTML 报告中。适用于 CI 流水线中按阶段逐步收紧的场景。精确实时计数请运行 `.venv/bin/python -m pytest src/test/ --collect-only -q`。

##### `--mode` 与 pytest `-m` 对照

| `--mode` | 等效 `-m` 表达式 | Linux 开发机参考耗时 |
|:---------|:-----------------|:--------:|
| `regression` | `scenario` | ~17s |
| `smoke` | `smoke` | ~2s |
| `unit` | `unit` | ~15s |
| `standard` | `unit and not (edge or data)` | ~16s |
| `edge` | `edge` | ~13s |
| `data` | `data` | ~2s |
| `scenario` | `scenario` | ~18s |
| `integration` | `scenario or integration` | ~14s |
| `verify` | `unit_core or unit_providers or unit_fetcher or unit_config or unit_news or unit_llm or unit_analysis or unit_scripts or unit_web or unit_qa or unit_report` | ~10s |
| `dev-verify` | `((unit_core or unit_providers or unit_fetcher or unit_analysis or unit_scripts or unit_web or unit_qa or unit_report) and not (edge or data)) or scenario_basic`（单轮合一，原两阶段并集，收集数对拍一致） | ~20s |
| `all` | （无过滤，全量） | ~21s |
| `all_no_unit` | `not unit and not live` | ~10s |
| `report` | `unit_report` | ~11s |
| `scenario_extreme` | `scenario_extreme` | ~2s |
| `perf` | `scenario_perf` | 见 test-coverage.md |
| `security` | `scenario_security` | 见 test-coverage.md |
| `live` | `live`（需 `--run-live`） | — |

> 注：**Linux 开发机参考耗时**按 2026-08-05 实测（Linux x86_64，Intel i5-13500H，12 核 16 线程，46.8 GiB 内存；pytest-xdist worker=8 = medium 50% 核数）。耗时与硬件/操作系统/并行度强相关，不同机器上可能相差一个数量级，仅作相对量级参考；完整说明及不同环境下的耗时对照见 [test-coverage.md](test-coverage.md)（顶部注 + 「采集环境属性」/「各模式耗时对照」表）。若需本机实测，运行 `.venv/bin/python scripts/test-runner.py --mode bench --update-docs` 自动采集回填。

##### 跨机器耗时采集与环境耗时对照（`bench` + `--machine-info` / `--update-docs`）

耗时与**硬件配置、操作系统与并行度**强相关。跨机器复现耗时并回填对照表：

```bash
# 仅采集：顺序运行 14 个对照表模式（不含 live），打印环境属性表 + 各模式实测耗时表
.venv/bin/python scripts/test-runner.py --mode bench --machine-info

# 采集并自动更新 test-coverage.md「环境耗时对照」两张表
.venv/bin/python scripts/test-runner.py --mode bench --update-docs   # 隐含 --machine-info
```

- **`--mode bench`** 是 14 个对照表模式的聚合别名（`_MODE_TABLE_ORDER` 除 `live` 外全部），按对照表顺序运行；结果去重保序，非 bench 模式原样透传。
- **`--machine-info`** 采集 15 项环境属性（操作系统/系统版本/架构/主机名/CPU 型号/物理核数/逻辑线程/内存/磁盘类型/文件系统/Python 版本/并行级别/worker 数/采集并行度/采集日期，跨平台容错）并输出两张 Markdown 表格。
- **`--update-docs`** 在跑完后**自动写入** `test-coverage.md` 的两张表（按主机名匹配列：同机覆盖刷新日期、新机器追加列；历史参考列不受影响）。默认**永不写文档**，仅在显式传入该标志时更新；内容未变化则跳过写入（幂等）。
- **`--jobs N`** 多模式并行采集（每档独立 pytest 进程、报告按模式目录隔离）：优先级 **CLI > `TEST_RUNNER_JOBS` 环境变量 > 自适应**——`os.cpu_count()≥4` 取 2，弱机/缺核信息/核数采集异常一律取 1（不超订）；环境表「采集并行度」行记录本次口径，**跨并行度不与串行基线直接可比**。单模式忽略。
- **采集时机（不是提交门禁）**：`bench` 会**跑完全部 14 个模式**（全量套件多轮），耗时以分钟计。它**不进 P0/P1/P2 门禁**，也不必每次提交都重采——仅在两种时机采集：① **发布前**刷新 `test-coverage.md` 数据快照（见 CLAUDE.md「发布数据文档刷新」）；② 换机器 / 需本机耗时参考时。日常提交只需 P0 `dev-verify` + 守护脚本。
- 中断保护：bench 中途 `Ctrl+C` 先打印已采集部分并回填已完成模式，慢机器不丢数据。
- 典型耗时与对照说明见 `test-coverage.md` 顶部注 + 「环境耗时对照」表。

### 查看报告

每次运行后，测试报告输出到（每个子目录对应一个 `--mode` 名称）：

```
test-reports/latest/
├── index.html            # 汇总页（打开此文件查看总览）
├── unit/
│   └── report.html       # 单元测试
├── standard/
│   └── report.html       # 常规单元测试
├── scenario/
│   └── report.html       # 业务场景测试
├── scenario_extreme/
│   └── report.html       # 极限场景测试
├── integration/
│   └── report.html       # 集成测试（场景 + 模块间契约）
├── regression/
│   └── report.html       # 回归测试 / 场景别名
├── dev-verify/
│   └── report.html       # 开发期快速验证
├── verify/
│   └── report.html       # 合入验证
├── edge/
│   └── report.html       # 边缘场景测试
├── data/
│   └── report.html       # 数据正确性验证
├── live/
│   └── report.html       # 真实网络验证（opt-in，--mode live 才生成）
├── all/
│   └── report.html       # 全量测试
├── all_no_unit/
│   └── report.html       # 全量测试（排除单元测试）
├── smoke/
│   └── report.html       # 冒烟测试
```

**打开方式**：直接用浏览器打开 `test-reports/latest/index.html`

### 快速定位失败用例 — `test-extract-failures.py`

运行 `test-runner.py --mode verify,regression` 等全量测试后，直接从 HTML 报告中提取失败/错误用例的详细信息，无需手动翻浏览器：

```bash
# 自动查找 test-reports/latest/ 下的报告
.venv/bin/python scripts/test-extract-failures.py

# 指定报告路径
.venv/bin/python scripts/test-extract-failures.py test-reports/latest/all/report.html

# 仅输出汇总统计（不打印日志）
.venv/bin/python scripts/test-extract-failures.py --summary

# 输出 JSON 格式（便于管道处理）
.venv/bin/python scripts/test-extract-failures.py --json
```

**典型工作流**：

```
# 1. 跑全量测试
.venv/bin/python scripts/test-runner.py --mode verify,regression

# 2. 快速查看哪些用例失败
.venv/bin/python scripts/test-extract-failures.py --summary

# 3. 查看失败详情（含错误堆栈最后 500 字符）
.venv/bin/python scripts/test-extract-failures.py

# 4. 修复后，只重跑之前失败的用例
.venv/bin/python -m pytest src/test/ -m "<对应标记>" --lf
```

> 脚本自动定位 `test-reports/latest/all/report.html` 等常用路径，无需每次指定路径。

### 定位顺序依赖失败 — `test-find-order-dependent.py`

当某个用例**单跑通过、与全套一起跑却失败**（典型：fixture / 模块级 patch 泄漏到后续用例，如日历注入与离线桩的装配栈序错误），手工二分需要 10+ 轮 pytest 往返。本脚本自动完成：单跑确认 → 收集参考顺序 → 复现门（前置合跑必须让目标失败，含无关失败即中止）→ 最小失败前缀二分 → 单文件配对确认（不成立则预算内精简）→ 输出污染源与最小复现命令。

```bash
# 默认在 src/test 收集顺序，对目标之前的全部文件做二分
.venv/bin/python scripts/test-find-order-dependent.py "src/test/unit/report/test_market_value.py::TestClass::test_name"

# 已知大概范围时限定候选（大幅提速，推荐）
.venv/bin/python scripts/test-find-order-dependent.py "<目标>" --candidates "src/test/unit/report/test_event_impact_wiring.py"

# 只做单跑确认与候选枚举（不执行二分）
.venv/bin/python scripts/test-find-order-dependent.py "<目标>" --dry-run
```

退出码：0 = 已定位；1 = 目标单跑即失败（非顺序依赖，请直接调试该用例）；2 = 无法复现/前置含无关失败/用法错误。前置条件：全套除目标外全绿；`--max-runs`（默认 40）限制 pytest 运行次数硬上限。定位后优先修**泄漏方**（fixture 栈序 / 未恢复的 patch），而非给受害用例加隔离。

### 标记选择运行速查

以 `.venv/bin/python -m pytest -m "<表达式>"` 形式快速选取特定标记组合，适合开发调试中定向验证。

**场景标记**：

| 表达式 | 覆盖范围 |
|:-------|:---------|
| `scenario` | 全部业务场景 S0a/S0b/S0d + S1-S33 + T1-T21（S0c 属 `scenario_extreme`，不计入） |
| `scenario_basic` | 基础链路 S0a/S0b/S0d + S1-S5 + S21-S33 |
| ├ `scenario_stock` | S1: 纯股票组合 |
| ├ `scenario_fund` | S2: 纯基金组合 |
| ├ `scenario_mixed_accounts` | S3: 混合多账户 |
| ├ `scenario_new_holdings` | S4: 新持仓无缓存 |
| └ `scenario_cache_hit` | S5: 缓存全命中 |
| `scenario_resilience` | 异常容错场景 S6-S9 |
| ├ `scenario_bond` | S6: 纯债券基金组合 |
| ├ `scenario_network_down` | S7: 网络中断降级 |
| ├ `scenario_single_holding` | S8: 单账户单持仓 |
| └ `scenario_zero_cost` | S9: 零成本持仓 |
| `scenario_extreme` | 极限场景 S0c+S10：超多持仓/极端份额/高精度净值/零值组合 |
| `scenario_llm` | LLM 场景 S11-S20 |
| `scenario_datetime` | 日期/时间场景 T1-T21 |
| `scenario_basic or scenario_datetime` | 基础链路 + 日期场景 |
| `scenario_cache_hit or scenario_zero_cost` | 缓存 + 零成本组合 |

**单元子模块标记**：

| 表达式 | 覆盖范围 |
|:-------|:---------|
| `unit` | 所有单元测试 |
| `unit_providers` | 数据源 Provider（腾讯/东方财富/天天基金等） |
| `unit_fetcher` | 数据获取调度 |
| `unit_llm` | LLM 模块 |
| `unit_news` | 新闻处理 |
| `unit_report` | 报表生成 |
| `unit_config` | 配置管理 |
| `unit_core` | 核心基础设施（缓存/模型/注册表等） |
| `unit_analysis` | 分析计算（流动性/再平衡/汇率/债券收益率/情景） |
| `unit_ui` | TUI 交互 |
| `unit_cli` | CLI 命令行模式 |
| `unit_scripts` | 工程脚本（历史痕迹/版本一致性/任务编号检查） |
| `unit_web` | Web 入口（浏览器模式上传/生成/进度/产物，`src/python/web/`） |
| `unit_qa` | 报告对话式追问（`src/python/qa/`：上下文提取/会话服务/报告页与 TUI 追问入口） |
| `unit_providers or unit_fetcher` | 数据管道（Provider + 调度） |

**横切标记**：

| 表达式 | 覆盖范围 |
|:-------|:---------|
| `smoke` | 冒烟 |
| `edge` | 边缘/异常场景 |
| `data` | 数据正确性验证 |
| `llm` | 全部 LLM（单元 + 场景） |
| `not llm` | 排除 LLM 后的全量 |

**集成测试标记**：

| 表达式 | 覆盖范围 |
|:-------|:---------|
| `integration`（父标记） | 全部集成测试 |
| ├─ `integration_contract` | 模块间接口契约验证 |
| ├─ `integration_isolation` | 错误隔离业务语义验证 |
| ├─ `integration_news_pipeline` | 新闻流水线全链路 |
| ├─ `integration_cache` | 跨模块缓存一致性验证 |
| ├─ `integration_tui` | TUI → Handler 路由集成测试 |
| └─ `integration_cli` | CLI 命令行模式集成测试 |

场景标记表末尾列出了常用的标记组合表达式（如 `scenario_basic or scenario_datetime`、`scenario_cache_hit or scenario_zero_cost`），可在此基础上按需调整。

**组合查询示例**：

```bash
# 查看指定标记下有哪些测试（不执行）
.venv/bin/python -m pytest src/test/ -m "edge" --collect-only

# 运行单个测试文件
.venv/bin/python -m pytest src/test/unit/report/test_category.py -v

# 运行单个测试类
.venv/bin/python -m pytest src/test/unit/report/test_category.py::TestCategoryAggregationConsistency -v

# 冒烟测试（快速验证核心通路）
.venv/bin/python -m pytest src/test/ -m "smoke" -v

# 冒烟 + 边缘测试
.venv/bin/python -m pytest src/test/ -m "smoke or edge" -v

# 除 LLM 外的全部测试
.venv/bin/python -m pytest src/test/ -m "not llm" -v

# 仅 LLM 场景（S11-S20）
.venv/bin/python -m pytest src/test/ -m "scenario_llm" -v

# 基础业务链路 + 日期/时间场景
.venv/bin/python -m pytest src/test/ -m "scenario_basic or scenario_datetime" -v

# 输出 HTML 报告
.venv/bin/python -m pytest src/test/ -m "edge" -v --html=test-reports/latest/edge/report.html
```

### 测试文件规范

- **命名**：`test_<module>.py`
- **类名**：`Test<Feature>`，继承 `unittest.TestCase`
- **方法**：`test_<场景>`
- **单文件上限**：≤ 800 行 / ≤ 80 测试项 / ≤ 15 方法每类
- **标记规则**：单元测试用 `pytestmark` 模块级列表（`[pytest.mark.unit, pytest.mark.<子组>]`），场景测试用类级 `@pytest.mark.scenario + @pytest.mark.<子组>`，edge 测试在 `pytestmark` 中追加 `pytest.mark.edge`
- **真值单一来源**：断言中的「事实」必须从真值来源**动态派生**，禁止写死会随开发演进的派生量（需求/章节/开关/注册表/枚举的**条数**与**逐条清单**）。写死后新增一条需求/章节就会把测试打红（良性变更误判为回归），且与门禁脚本职责重复。
  - ✅ 结构关系断言：`set(a) == set(b)`（双向相等）、`expected <= set(a)`（覆盖）、`numbers == list(range(1, n+1))`（序号连续）、`len(keys) == len(set(keys))`（唯一性）、逐项遍历
  - ❌ 硬编码总数：`assert len(req_ids) == 276`、`assert len(sections) == 17`
  - 需要「条数」语义时用「域覆盖 + 序号连续」等价表达（强度不低于写死条数，且能发现跳号/重号）
  - 由此守：`scripts/check-test-redundancy.py` 第 5 类 `check_hardcoded_evolving_totals`
- **浮点断言容差化**：涉及浮点计算结果的断言用 `pytest.approx(...)`（或显式 `abs=`/`rel=`），**禁止 `==`/`!=` 比较两条计算路径**——「同一函数、不同输入长度或求和顺序」也算两条路径。
  - ❌ `assert beta == portfolio_beta(portfolio[:200], benchmark)`（内部对齐 vs 显式截断，末位差 1 ulp：3.13 相等、3.11 不等）
  - ✅ `assert beta == pytest.approx(portfolio_beta(portfolio[:200], benchmark), abs=1e-12)` + 长度敏感反例 `assert abs(portfolio_beta(portfolio[:100], benchmark) - beta) > 1e-6`
  - 只有整数、`len`、set/list 结构、字符串/指纹等精确可表示的值才用 `==`；容差取「远大于 ulp、远小于真正区分的量级」
- **勿断言「随周期/环境变化的仓库状态」**：读**真实仓库**的契约测试（如 `TestRealArchiveContract`）只能约束「结构的 invariant」，不能要求「某种状态必须存在」——例如「主台账至少有一节开发期已修复」在新开发周期开张时必然不成立（`devbump` 会清空上一版占位），本地恰巧有节、CI 上却是空台账，于是出现「本地全绿、CI 三版本 + portability 全红」。写这类断言时穷举状态并给出各自的合法判据；**能空的状态就要允许空**。同理：新增子命令/新条目的测试优先从实现集合派生（如 `cmd_*` 函数集合），不写死清单。
- 新增文件后运行 `.venv/bin/python scripts/check-test-markers.py` 验证标记合规性

### 新增测试指南

新增测试用例时，按以下流程操作：

**确定测试类型和文件位置**：

| 测试类型 | 放哪里 | 示例 |
|:---------|:-------|:-----|
| **模块单元测试** | 已有对应 `test_<module>.py` 追加 | `test_cache_io.py` 追加 `TestCacheEdgeCases` |
| **新模块测试** | 新建 `test_<新模块>.py` | `test_news_correlator.py` |
| **业务场景测试** | `test_scenario_basic_flows.py`（基础链路 S1-S5）或 `test_scenario_resilience_flows.py`（异常容错 S6-S9）或 `test_scenario_extreme.py`（极限 S0c+S10） | S1 → `test_scenario_basic_flows.py` |
| **持仓质量场景** | `test_scenario_holdings_quality.py` | S0a/S0b/S0d |
| **特殊品种场景** | `test_scenario_special_securities.py` | S21-S28 |
| **操作行为场景** | `test_scenario_operational_behavior.py` | S29-S33 |
| **报告序号场景** | `scenario/basic/test_scenario_section_order.py` | 序号合规性 |
| **LLM 场景测试** | `scenario/llm/` 下 9 个文件：`test_llm_mixed_cache.py` / `test_llm_module_info.py` / `test_llm_extended_thinking.py` / `test_llm_disabled.py` / `test_llm_disabled_cache.py` / `test_llm_network_error.py` / `test_llm_partial_cache.py` / `test_llm_empty_holdings.py` / `test_llm_hallucination.py` | S11-S20 |
| **日期/时间场景** | `test_datetime_scenarios.py` | T1-T21 |
| **辩论模式场景** | `integration/test_debate_pipeline.py` | 端到端管线 |
| **辩论模式单元测试** | `unit/llm/test_debate_*.py` | generators/prompts/edge/token_budget/conditional/qa |
| **缺陷回归测试** | 对应模块的 `test_*.py` 或 `test_regression.py` | Bug fix 的断言 |
| **边缘/异常场景测试** | 对应模块的 `test_<module>_edge.py` | 使用 `@pytest.mark.edge` 标记，放置于模块目录下 |

**命名规范**：

```python
# 测试类名 — 模块/场景名 + 测试维度
class TestCacheEdgeCases:          # 模块 + 测试类型
class TestGetTtlMarketAware:       # 函数名 + 场景
class TestScenarioS21:             # 新业务场景递增

# 测试方法名 — test_ + 场景 + 预期结果
def test_empty_holdings_returns_zero(self):
def test_ttl_during_trading_hours_returns_30s(self):
def test_qdii_nav_date_delayed_t2(self):
```

**加载 `scripts/` 下脚本（动态加载）**：

```python
from src.test._script_loader import load_script

mod = load_script("test-runner.py")                                            # 模块名由文件名派生
mod = load_script("_test_runner/modes.py", module_name="modes_under_test")   # 子路径 + 显式模块名
```

> 唯一实现为 `src/test/_script_loader.py`：按文件名/子路径加载 `scripts/` 下脚本、每次调用重新执行返回新实例、注册进 `sys.modules`（`@dataclass` 按 `cls.__module__` 回查命名空间依赖它）。**禁止**在测试文件里再手写 `importlib.util.spec_from_file_location` 样板或自定义 _load_script 同名加载器——`unit/scripts/test_script_loader.py` 的样板唯一性机检会检出（除 loader 自身外出现动态加载样板、或定义同名本地加载器均判失败）。

**测试文件分片与共享夹具**：

单文件超测试红线（>1200 行）或逼近档（>900 行）时按**被测职责**分片，不按行数机械切。约定：

- 兄弟分片共用 `test_<模块>_<域>.py` 命名（如 `test_excel_generator_llm_usage.py`），并在主分片 docstring 的「兄弟分片」行互相点名——读者从任一文件都能找到全貌；
- **共享构造器（模板路径 / 注册表常量 / 最小渲染数据 / mock 工厂）放 `<包>/_<模块>_fixtures.py`**（下划线前缀，不含 `test_*` 故不被收集），各分片 `from ... import ...` 引用，禁止复制一份到每个分片——改模板契约时漏改分片副本是最常见的静默漂移；
- **不得读真实 `data/`、`reports/`、`logs/` 做断言**：隔离类断言（「测试没有写真实目录」）用注入的隔离目录（`HISTORY_SNAPSHOT_DIR` 等已由 conftest 重定向）即可，不要额外读取 `PROJECT_ROOT/data/...` 的现状——那既引入对开发者本地数据的依赖，也让用例在 CI（无该目录）与本地表现不同。
- **共享 fixture 放目录级 `conftest.py`**：同一目录多文件共用、且需要 `tmp_path`/`monkeypatch` 的装配（如 `src/test/unit/llm/conftest.py::llm_cache_dir` 统一重定向缓存目录并复位日志去重）放这里，而不是在每个测试文件各写一份或塞进 `_fixtures.py`（后者只放纯函数与常量）；
- **分片后 patch 目标须重定向**：实现下沉到子模块（如 `_perf_report/report.py`、`_traces_doc/deleted_refs.py`）后，`monkeypatch.setattr(入口模块, "_常量", ...)` 对写入无效——必须 patch **调用点所在子模块**，并同步迁移该模块的进程级缓存重置点（`_HIST_DEFS = None` 一类）；
- 分片不新增/删除用例：原文件的 `def test_` 总数须等于各分片之和，收尾用 `grep -c 'def test_'` 对拍，并同步 `folders.md` 目录树与 `test-coverage.md` 计数。

**新增后必须更新的文件**：

1. **`test-coverage.md` 场景测试分组表** — 新增 S/T/D 场景时补充条目（含测试类参考列）
2. **`folders.md`** — 新增 test_*.py 文件后更新目录树
3. **`changelog.md`** — 记录新增的测试数量和覆盖场景
4. **`plan.md`** — 如果在迭代中新增的功能，更新对应条目的完成状态
5. **`unit/conftest.py`** — 新增 `unit/` 下测试文件时确认 `pytestmark` 列表包含正确的 `unit_*` 子标记
6. **`conftest.py` 隔离 fixture** — 新增模块级单例时加 autouse 复位 fixture（参照 `_auto_reset_last_reason` 习语，如 `_auto_reset_llm_failure_state`）；新增持久化状态文件/输出目录时在 `_isolate_sensitive_paths` 增加 `monkeypatch.setattr` 重定向——细则见 CLAUDE.md「新增测试隔离要求」，漏加会让用例随执行顺序漂移

**新增后必须执行的验证**：

```bash
.venv/bin/python -m pytest src/test/                                   # 全量通过
.venv/bin/python -m pytest --co                                         # 无 patch 残留污染
.venv/bin/python -m pytest src/test/unit/core/test_registry.py --co -v      # 新文件隔离（示例）
.venv/bin/python scripts/check-test-markers.py                # 标记合规性检查（AST 静态扫描）
```

**文件膨胀阈值**：

| 指标 | 警告线 | 红线 | 措施 |
|:-----|:------:|:----:|:-----|
| 主程序单文件行数（`src/python/`） | > 700 行 | > 1000 行 | 按职责域下沉拆分（域下沉 + 门面 re-export，消费方导入面不变） |
| 脚本单文件行数（`scripts/` 递归含包内子模块） | > 600 行 | > 1000 行 | 按职责拆包（评测核心 / 阶段编排 / CLI 等），入口仅留 CLI 与原面 re-export |
| 测试单文件行数（`src/test/`） | > 900 行 | > 1200 行 | 考虑按被测函数 / 场景类型拆分 |
| 薄壳文件（`__init__.py` 包标记 / 纯门面） | > 200 行 | 同域红线 | 包标记与 re-export 应收薄，逻辑下沉子模块 |
| 单文件测试数 | > 80 项 | > 120 项 | 拆分到子文件 `test_xxx_part1.py` / `test_xxx_part2.py` |
| 单类方法数 | > 15 项 | > 25 项 | 拆为多个 Test 类或拆分文件 |
| 单方法 mock 数 | > 5 个 patch | > 8 个 patch | 重构被测函数以降低耦合 |

> **门禁**：红线列由 `scripts/check-file-length.py --ci` 强制——**主程序 >1000 行**（硬上限，review-findings 文件膨胀登记区）、**脚本 >1000 行**与**测试 >1200 行**即 finding 退出 2；豁免路径须与 review-findings 挂账同步（拆分后自动提示移除豁免）。警告线即**登记线**（不再维护第三套数字）：`-v` 输出的可选优化区间清单（主程序 >700 / 脚本 >600 / 测试 >900、薄壳 >200）就是 review-findings P3 登记表的派生源；`-v` 同时按「行数 × 近 90 天改动次数」给出拆分优先级，回答「先拆哪个」。

### 常见问题

**Q: 运行报错 `no tests collected`？**
A: 确认使用了正确的 marker 名：`.venv/bin/python -m pytest src/test/ -m "edge" --collect-only` 可预览匹配的测试。

**Q: 报告中文乱码？**
A: 确保操作系统编码为 UTF-8。Windows PowerShell：`chcp 65001`；Linux/Mac 默认即可。

**Q: 需要跳过 LLM 测试？**
A: 使用 `--mode edge` 仅跑边缘用例，或 `.venv/bin/python scripts/test-runner.py --mode scenario` 仅跑业务场景（不含 LLM 场景）。若要排除全部 LLM 相关（单元 + 场景），使用 `.venv/bin/python -m pytest src/test/ -m "not llm"`。注意 `--mode unit` **包含** `unit_llm`（均为 mock，无需 API key），不跳过 LLM。

**Q: 新增测试文件后运行报错 `missing unit_* marker`？**
A: `unit/conftest.py` 的验证模式要求每个单元测试文件必须包含 `unit_*` 子标记。在文件顶部添加 `pytestmark = [pytest.mark.unit, pytest.mark.<子组>]`，子组名见 `conftest.py` 注册表（如 `unit_providers`、`unit_report` 等）。

**Q: 如何添加新的测试标记？**
A: 在 `src/test/conftest.py` 的 `pytest_configure` 中注册新标记，然后在测试类前加 `@pytest.mark.<新标记>`。单元测试使用模块级 `pytestmark` 列表，而非类级装饰器。

**Q: 如何验证新增文件的标记是否正确？**
A: 运行 `.venv/bin/python scripts/check-test-markers.py`，脚本会静态扫描所有 `test_*.py` 文件，检查标记完整性、是否有拼写错误、`_edge.py` 是否漏标 `edge` 等。

## 调试与剖析
排查分三条主线：**看日志**（发生了什么）、**交互式调试**（在哪一步错）、**性能剖析**（为什么慢）。
先按下表选主线，别一上来就加 print。

| 现象 | 主线 | 第一步 |
|:-----|:-----|:-------|
| 报告缺章 / 某数据为 `--` | 日志 | `cli view-logs --level WARNING` 看最近降级原因 |
| 用例失败但看不出原因 | 交互式 | `pytest -x --pdb` 就地进断点 |
| 单个用例偶发失败 | 交互式 | `--lf` 重跑 + `-p no:randomly` 排除顺序影响 |
| 全套慢 / 某档耗时涨了 | 性能 | `--durations=20` → `perf_history` 对拍 |
| 测试卡住不动 | 性能 | 见 §测试慢或挂住的诊断 |
| Web 页面行为不对 | 浏览器 | `scripts/test-smoke-web.py` → CDP 脚本 |

### 日志级别与告警语义

**级别可配（默认 INFO）**：文件与控制台默认 INFO；需要逐次取数追踪时用环境变量单独放开，不改代码、不改配置：

```bash
# 级别默认在 data/config/logger.json；下列环境变量仅临时覆盖（优先级更高）
INVEST_LOG_FILE_LEVEL=DEBUG .venv/bin/python -m src.python.cli report --type full   # 文件写 DEBUG
INVEST_LOG_CONSOLE_LEVEL=DEBUG ...                                                # 控制台写 DEBUG
```

非法值回落 INFO 并提示一次。**默认不开 DEBUG** 的原因：日志审计（近一周 107,625 行）显示 DEBUG 占 91%，其中「市场时段」67%、缓存命中 17%，真实告警被埋在噪声里，10MB 轮转只能留约 6 天。

**写日志时的三级语义（新增日志按此选级）**：

| 级别 | 用在哪 | 例子 |
|:-----|:-------|:-----|
| `INFO` | 预期内的「没有数据」——各源都返回空结果、文档无该章节、异源候选拒服务 | 链路全失败但无传输级故障时记「各源均无可用结果（预期缺失，非链路故障）」 |
| `WARNING` | 真实降级/故障——传输级失败、熔断、配置缺失导致的跳过 | 「全链路失败（无过期缓存可用）」「连续失败，熔断 N 秒」 |
| `ERROR` | 需要人工介入的缺陷——输出截断、挂载点异常、数据写盘失败 | 「LLM 输出被截断（建议增大 max_tokens_…）」 |

> 判定实现：链路用「是否出现过 `TRANSPORT_FAILURE`」区分（`fetcher/chain.py`），不靠文案匹配。基准跑（`perf-test-report` 主动禁网）的确定性失败在连接级重试处按 DEBUG 记录，避免把人为断网堆成 WARNING。

**追踪类 DEBUG 的两条纪律**：① 同一状态不重复刷（市场时段判定按「结果变化」记，进程级去重）；② 同一 key 的命中/写入只记首见一次（其余由 `_stats` 命中率与报告「缓存命中率」行承担汇总），否则单周就能刷出万行。

**LLM 总时间预算**：`llm_settings.json → llm_total_time_budget_sec`（秒，`0`=不启用）。超预算后**不再启动新模块**（已在跑的模块不打断），日志回显已用时与预算值，报告按已生成内容呈现。用于兜住「单模块卡住 + 重试叠加」把一次 full 拖成小时级（审计实测曾出现 6,623s 的 LLM+新闻阶段）。

**去重锚点默认采集、写侧零读取**：`data/calibration/dedup_anchors.jsonl` 每次报告只追加边界案例（单次 `write`+`fsync`，不解析旧文件）；跨轮重复由 `eval-dedup-threshold.py::load_anchors` 按键去重（保留最早一条），诊断结论不受重复行影响。`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关闭采集。文件超过 32MB 时只记提示，不自动压缩——压缩由 `scripts/eval-dedup-threshold.py` 评估后**默认顺带执行**（分析用完整样本，随后每 key 最新 + 近 120 天，`--no-compact` 关闭、`--retention-days 0` 只按键去重）或 `INVEST_DEDUP_MAINTENANCE=1` 显式触发；压缩前 `.bak` 与主文件等大，默认校验后清理（`INVEST_DEDUP_KEEP_BACKUP=1` 保留）。

### 日志：先看日志再看代码

- **logger 名**：项目统一 `logging.getLogger("invest")`，`setup_logger()` 落盘到 `logs/app.log`（按大小轮转），控制台同步 INFO/WARNING/ERROR。
- **三种读法**：CLI `python -m src.python.cli view-logs --level WARNING --lines 200`（无需 config，配置损坏也能用）；TUI `[V]`；Web ⑦ 日志卡。三者同一实现（`core/log_reader.py`），级别过滤、时间窗过滤一致。
- **降级线索**：报告里某数据为空先查 `DegradationTracker` 事件（`data_status.degradation_summary()`，也出现在任务完成通知载荷里），它记录「哪个源、连续失败几次、是否已降级」。
- **凭据不落日志**：密钥类字段在落日志前已掩码；**但持仓代码、金额、路径会进日志**——贴日志到 issue 前自行脱敏。
- **级别纪律**：预期内的落空用 DEBUG（如探测章节名未命中），需要人行动的用 WARNING，只有真错误用 ERROR——新增日志前先确认级别，避免把 `[V]` 刷满。

### 交互式调试

```bash
# 失败即停并进断点（最常用）
.venv/bin/python -m pytest src/test/unit/report/test_summary.py -x --pdb

# 只重跑上次失败的（改完立刻验证）
.venv/bin/python -m pytest src/test/ -q --lf

# 看单测耗时排行（找慢用例）
.venv/bin/python -m pytest src/test/unit -q --durations=20

# 收集期确认某用例是否被标记选中（不真跑）
.venv/bin/python -m pytest src/test/ -q --co -m unit_report | grep summary

# 排除随机顺序插件，复现顺序相关失败
.venv/bin/python -m pytest <case> -q -p no:randomly
```

- **顺序依赖失败**用 `scripts/test-find-order-dependent.py`（单跑绿/合跑红时二分定位污染源，见上文测试指南）。
- **测试里不要用 print 调试**：pytest 会捕获输出，失败时用 `-s` 或 `--capture=no` 才看得到；临时排查完记得删。

### 性能剖析

| 关注点 | 工具 | 说明 |
|:-------|:-----|:-----|
| 单次运行时各阶段耗时 | `perf_history.jsonl` + `scripts/perf-history.py` | 每次运行落一条（含 status/阶段/品种数），`perf-history` 出趋势表、P95/P99、离群归因 |
| 端到端报告耗时门禁 | `scripts/test-perf-report.py --gate` | 主动压测 mock 管线，basic ≤60s（CI `perf-gate` job 阻塞） |
| 阶段级耗时 | `PerfCollector.stage_progress` / `reporter.print_timing_summary()` | TUI 报告收尾会打印耗时排行 |
| 测试档位耗时 | `scripts/test-runner.py --mode bench --update-docs` | 14 档实测回填 `test-coverage.md`（发布子集四档见 §refresh） |
| CPU 侧归因 | `time` 的 user/sys + `/proc/loadavg` | **先记环境再采信数字**：loadavg 1 分钟 > 核数/2 时该轮作废 |

### 测试慢或挂住的诊断

实测流程（按顺序做，别跳步）：

1. **先分清「慢」还是「卡」**：`pytest src/test/unit -q --durations=20` 看是某几个用例极慢，还是整体均匀偏慢；
2. **整体偏慢**看并行与等待：`-n` 已按核数自适应（medium=50%），**加大 worker 通常无收益**（实测 8→12 核反而更慢，user CPU 涨 60%）；
3. **等待型睡眠**才是常见大头。用一次性插件统计整轮 `time.sleep` 累计与调用点：

```python
# 存到 docs/tmp/sleepprof.py，用 PYTHONPATH=<dir> pytest -p sleepprof 挂载
import collections, time, traceback
_orig, _stats = time.sleep, collections.Counter()

def _sleep(sec):
    site = "?"
    for f in reversed(traceback.extract_stack(limit=8)[:-1]):
        if "/src/python/" in f.filename:
            site = f"{f.filename.split('/src/python/')[-1]}:{f.lineno}"
            break
    _stats[site] += sec or 0.0
    return _orig(sec)

time.sleep = _sleep
```

4. **量出上限**：把 `time.sleep(>=0.05)` 置空再跑一轮，差值就是可压缩空间（本轮实测 37s → 22s，其中 36% 是白等）；
5. **只在自己负责的层消除等待**：离线桩（`offline_external_sources`）已在 `apply_offline_stubs` 里接管节流与退避等待；**不要全局禁睡**（会破坏验证等待语义的用例）；
6. **卡住不动**（不是慢）：`--timeout` 或 Ctrl+C 拿堆栈；若卡在 daemon 线程上的长 sleep（如健康检查），确认它是否在关键路径——`--deselect` 掉该用例对比墙钟即可判定。

> **测量纪律**：每次采样前先记 `nproc` 与 `cat /proc/loadavg`；对照实验交替执行（基线/改动/基线…）避免负载漂移；每档至少 3 次采样取中位数。高负载机上所有墙钟只能当量级参考。

### Web 端排查

- **HTTP 层**：`scripts/test-smoke-web.py`（Flask test_client 进程内全链路，不占端口、不发外网、mock 管线）先确认接口契约没破；
- **浏览器行为**：headless Chromium + CDP 直连（`docs/plan/web-browser-verification.md` 给了可复跑的启动/断言/收尾命令与「0 次真实 POST /api/runs」红线）；
- **前端调试**：页面所有动态内容用 `textContent`（防 XSS），改 DOM 后先在浏览器 devtools 看 console 与 network；
- **服务端日志**：自行 `nohup … > server.log` 启动时，除 `logs/app.log`（应用日志）外还要看该访问日志（WSGI 层，含 4xx/5xx）；排查脚本与产物建议放 `docs/tmp/`（git 忽略）。

### 状态文件排查

`data/state/` 下的运行时状态会直接影响行为，排查时按需查看（**生产数据，别随手删**）：

| 文件 | 含义 | 排查场景 |
|:-----|:-----|:---------|
| `circuit_breaker.json` | 端点熔断计数与冷却时间 | 「明明网络正常却不用某源」 |
| `datasource_health.jsonl` | 数据源健康检查历史 | `[H]` / Web 健康卡的原始数据 |
| `perf_history.jsonl` | 每次运行的阶段耗时 | 性能回归定位 |
| `experiment_stats.json` | 实验项启用计数 | 判断实验项是否有真实使用（转正/撤销判据） |
| `decision_ledger.jsonl` | 决策登记与结算 | 跨期反思闭环 |
| `local_state.json` | 引导/提示已读状态（仅本机） | 「为什么又弹引导」 |

> 测试里这些路径都被 `conftest._isolate_sensitive_paths` 重定向到临时目录——**测试不会污染你的真实状态**。
## 开发新功能：扩展清单
四类常见改动各自的端到端清单。**按顺序走完整张表**——漏项通常不会立刻报错，而是在 CI 守护或下一版发布时才暴露。

### 新增数据源 / Provider

| 步骤 | 落点 | 要点 |
|:--|:--|:--|
| 1 | `src/python/providers/<name>.py` | 实现取数函数；统一走 `core.http_client.make_http_client`（不要在 provider 里自建 httpx 客户端）；失败必须 `set_last_reason(...)` 自陈原因（「返回空」不算原因） |
| 2 | 重试与限流 | 需要重试就用 `core/retry.RetryPolicy`（瞬时/确定性判据），需要间隔就用 `core.throttle.RateLimiter`（唯一实现，勿自建 sleep） |
| 3 | 注册 | 在 `core/registry.py` 的白名单/注册表登记，并在健康检查探针清单里加一项（`doctor` 与 `[H]` 会用到） |
| 4 | 路由 | 需要按数据类型覆盖首选源时，登记 `preferred_provider` 的键 |
| 5 | 缓存 | 缓存前缀 + TTL 在 `core/data_registry.py` 登记（`cache_ttl` 是**唯一默认来源**；`config.cache_ttl.*` 仅为稀疏覆盖，模板不写默认值）；前缀须在 `datasource.md` 对照表登记 |
| 6 | 契约测试 | `src/test/unit/providers/test_<name>.py`：正常/超时/429/畸形响应/降级；能录真实响应的用 cassette（`scripts/` 录制回放，`--run-live` opt-in） |
| 7 | 文档 | [datasource.md](../manuals/datasource.md)（数据源↔缓存↔章节对照）+ [datasource-reliability.md](../manuals/datasource-reliability.md)（可靠度评级、限流、已知问题）+ 如涉及新密钥：[how-to-config.md](../manuals/how-to-config.md) |
| 8 | 需求与门禁 | `requirements.md` 补需求行（`R-DATA-*`）→ `testplan.md` 补验证载体 → `scripts/check-requirement-trace.py --ci` |

### 新增报告章节（Excel 页签 / HTML 章节）

| 步骤 | 落点 | 要点 |
|:--|:--|:--|
| 1 | `core/registry.py` | 注册模块：key、默认序号、section 类型（always / 开关控制）、可见性依赖 |
| 2 | Excel | 写页签：`report/<xxx>_sheet.py`，遵循页签写入约定（表头/列宽/字号 token 取 `report/styles.py`） |
| 3 | HTML | 模板：`src/static/tmpl/`（章节 partial 或主模板段落）；配色/字号/间距**必须取 `DESIGN.md` 档位**，空态文案用其 Data States 口径；打印与暗色主题要同步 |
| 4 | 可见性 | 新开关按 §新增功能开关检查清单登记（`features.json` 注册表 + TUI `[S]` + Web 配置面 + 手册开关表） |
| 5 | 导航与序号 | HTML 目录锚点、`report_section_order` 默认序号、`llm_usage` 强制末位不受影响 |
| 6 | 测试 | 结构契约测试（章节存在/隐藏/序号连续）、数据侧单测、`src/test/unit/report/test_design_doc.py`（若动样式） |
| 7 | 文档 | [reports-instruction.md](../manuals/reports-instruction.md) 逐章说明 + `requirements.md` §6.3 模块清单 + §6.4 字段定义 + `folders.md` 目录树 |
| 8 | 守护 | `check-doc-drift --ci`（章节-区块矩阵、章节数量、可见性表）、`check-semantic-index --ci`（语义命名登记） |

### 新增 Web 接口 / 面板

| 步骤 | 落点 | 要点 |
|:--|:--|:--|
| 1 | `src/python/web/handlers.py`（或下沉子模块） | 路由实现；返回统一错误信封（`{ok:false, code, message}`），状态码按语义（400/404/409/429/500） |
| 2 | 安全边界 | 写操作校验同源（`Origin`/`Referer`）；上传走既有校验（类型/大小）；**不得**在接口里接受任意路径（防目录穿越） |
| 3 | 单 worker 纪律 | 触发生成/模拟的接口必须走同一串行队列与互斥锁（忙碌返回 429 `*_BUSY`） |
| 4 | 前端 | `src/static/` 下的模板/JS：动态内容一律 `textContent`；图表走 chart 封装（主题切换/打印/导出同步） |
| 5 | 测试 | `src/test/unit/web/`：成功/非法参数/错误信封/同源拒绝；契约测试与 `scripts/test-smoke-web.py` 同步 |
| 6 | 文档 | 手册 [how-to-use-web-mode.md](../manuals/how-to-use-web-mode.md)（五区工作台对应位置）+ `requirements.md` §3.4（`R-WEB-*`）+ `technical.md` 接口表 |

### 新增功能开关 / LLM 模块

已有专门清单，直接照做：

- **功能开关**：见本指南 §新增功能开关检查清单（注册表 → TUI `[S]` → Web 配置面 → 手册开关表 → 实验项准入与转正判据）。
- **LLM 模块**：见本指南 §新增 LLM 模块检查清单（registry + 统一附录 + seam 表 + 指纹条件）。
- **报告章节序号**：改动后跑 `check-doc-drift --ci`（章节-区块矩阵）与 `check-semantic-index --ci`。
## 注册表使用（registry）

`src/python/core/registry.py` 是本项目的**中央注册表**，统一管理所有数据模块的：中文名称（`name`）、缓存前缀（`cache_prefixes`）、缓存 TTL（`cache_ttl`）、精确缓存键（`exact_cache_keys`）、LLM Settings 后缀（`settings_suffix`）、缓存分组（`cache_groups`）。

设计原则：**一处注册，全局生效**。新增数据模块只需在 `_MODULE_REGISTRY` 中添加一行 `DataModuleDef`，所有派生结构自动同步。

> **架构背景**：注册表是数据获取层与报告生成层之间的契约层，详细架构说明见 [technical.md](technical.md)（缓存层 / 报告生成层章节）；当前已注册模块的功能语义清单见其「功能语义命名表」章节。

### 核心数据结构

```python
@dataclass(frozen=True)
class DataModuleDef:
    name: str                    # 中文名称（报告标题、日志、TUI 展示）
    data_type: str               # 数据类型键（用于 TTL 查找）
    cache_prefixes: tuple[str, ...] = ()
    exact_cache_keys: tuple[str, ...] = ()
    cache_ttl: float = CACHE_DAILY
    settings_suffix: str | None = None   # None 表示非 LLM 模块
    cache_groups: tuple[str, ...] = ()
```

- `DataModuleDef` 是不可变的（`frozen=True`），注册后不可修改。
- `is_llm` — 自动判断是否为 LLM 模块（`settings_suffix is not None`）。
- `llm_settings_keys()` — 生成该模块在 `llm_settings.json` 中的所有合法键名，新增 LLM 模块后可用于配置校验。

### 公共 API 速查

**遍历与查询**：

```python
from src.python.core.registry import get_registry
registry = get_registry()          # → tuple[DataModuleDef, ...]
```

**缓存相关**：

```python
from src.python.core.registry import (
    get_cache_ttl_defaults,        # → dict[data_type → ttl]
    get_prefix_type_map,           # → dict[prefix → data_type]
    get_exact_type_map,            # → dict[exact_key → data_type]
    get_registered_data_types,     # → set[data_type]
)
```

`get_cache_ttl_defaults()` 是 TTL 默认值唯一出口（`get_ttl` 的兜底与 `check-doc-drift` 的文档校验都读它；配置模板不抄默认值，留空对象作稀疏覆盖位）；`get_prefix_type_map()` / `get_exact_type_map()` 供 `cache/_cleanup.py` 按文件名前缀 / 精确键名清理过期缓存；`get_registered_data_types()` 用于校验与测试。

**LLM 模块名称查询**：

```python
from src.python.core.registry import (
    get_llm_module_name,           # suffix → 中文名称
    get_llm_module_names,          # → dict[suffix → 名称]
)
```

合法 suffix：`global_macro` / `expert_review` / `health_check` / `penetration_deep` / `news_correlation`（另含缓存管理保留条目 `debate_pro` / `debate_con` / `debate_synthesis`，菜单层已隐藏）。

**LLM Settings 键名查询**：

```python
from src.python.core.registry import get_known_llm_settings_keys   # → set[str]
```

返回 `llm_settings.json` 中所有合法配置键名，用于配置校验。

**enabled_llm 子键查询**：

```python
from src.python.core.registry import get_known_enabled_llm_keys    # → set[str]
```

返回 `enabled_llm` 字典的所有合法子键（即各 LLM 模块的 `settings_suffix`），用于 `_validate_enable_llm()` 的子键拼写校验。

**报表排序与页签名称**：

```python
from src.python.core.registry import (
    get_report_sheet_name,         # sheet_key → 中文标题
    get_report_section_order,      # config → list[dict]（含 key/number/type/data_flag 的完整排序列表）
    get_report_section_number,     # key → 当前配置下的序号
    get_report_section_keys,       # → list[key]
)
```

- `get_report_sheet_name("summary")` → `"投资分析汇总"`
- `get_report_section_order(config)` → 解析 `report_section_order` 配置，返回有序键列表
- `get_report_section_number("position_structure")` → 当前配置下该模块的序号（被基金深度分析各页签写入器调用）
- `get_report_section_keys()` → 全部 19 个模块键名（键名→中文标题对照见 [配置参考 → report_section_order](../manuals/how-to-config-reference.md#report_section_order-报告序号配置)）

**计算模块查询**：

```python
from src.python.core.registry import (
    get_computation_registry,      # → tuple[ComputModuleDef, ...]
    get_computation_module,        # module_key → ComputModuleDef | None
)
```

`get_computation_registry()` 遍历所有计算/分析模块，用于运行时发现和文档生成；`get_computation_module("analytics_metrics")` 按 module_key 查找单个计算模块定义。

### 新增数据模块（非 LLM）

在 `_MODULE_REGISTRY` 中添加一行 `DataModuleDef`：

```python
DataModuleDef("我的中文名称", "my_data_type",
              cache_prefixes=("mydata_",),
              cache_ttl=CACHE_DAILY,
              cache_groups=("refresh",)),
```

- `name` — 中文显示名；`data_type` — 内部标识键，需唯一。
- `cache_prefixes` — 缓存文件名前缀（可多个），清理时按前缀匹配。**注意：长前缀需排在短前缀之前**，否则短前缀可能先匹配（如 `"llm_"` 会误匹配 `"llm_global_macro_"`）。实际声明时所有 LLM 模块均已使用完整长前缀，无歧义。
- `cache_ttl` — 使用 `CACHE_DAILY` / `CACHE_WEEKLY` / `CACHE_MONTHLY` 或自定义秒数；**这是该类型 TTL 的唯一默认来源**（配置文件里的 `cache_ttl.<type>` 只是稀疏覆盖，`get_ttl` 不做按 key 抖动）。
- `cache_groups` — `"preload"`（换持仓需重取）或 `"refresh"`（主动刷新按钮触发）；**留空 `()` 表示不被任何组清除操作命中**（如 `tracking`、`calendar` 等安全设计）。

### 新增 LLM 分析模块

除上述字段外，还需设置 `settings_suffix`：

```python
DataModuleDef("我的 LLM 分析", "llm_my_analysis",
              cache_prefixes=("llm_my_analysis_",),
              cache_ttl=14400,  # 4h；LLM 模块惯例：分析类 4h、内容寻址类 24h
              settings_suffix="my_analysis",
              cache_groups=("preload",)),
```

#### 新增 LLM 模块检查清单

| # | 步骤 | 操作位置 | 产出 |
|---|------|---------|------|
| ① | **注册模块定义** | `core/registry.py` → `_MODULE_REGISTRY` | 添加 `DataModuleDef` 实例，含 `settings_suffix` |
| ② | **配置 JSON 键组** | `llm_settings.json` | 新增 9~10 个 `{key}_{suffix}` 配置键（`news_correlation` 不含 `output_brief`） |
| ③ | **实现生成函数** | `llm/generators.py` | 新增生成函数，通过 `call_llm()` 调用 LLM |
| ④ | **注册调度入口** | `llm/_llm_dispatch.py` + `llm/generators_orchestrator.py` + `llm/module_fingerprint.py` | 在 `_llm_dispatch._build_module_fns()` 返回的 `_MODULE_FNS` 字典中添加新模块条目（键=settings_suffix，值=lambda 调用新函数）；在 orchestrator 的 `_compute_module_cache_info()` 中添加对应的 `info` 条目。**指纹不进 orchestrator**：在 `module_fingerprint.py` 的 `MODULE_FINGERPRINT_BUILDERS` 登记该模块的构造器（输入闭包 `ModuleFingerprintInputs`），预检侧按键取指纹、写侧闭包调用同一函数——两侧都不得自行拼接指纹片段 |
| ⑤ | **添加报告页签** | `report/llm_content.py` | 在 `write_llm_sheets()` 的 `_module_keys` 和 `_module_contents` 列表中添加新模块键名 |
| ⑥ | **暴露导出接口** | `llm/__init__.py` | 将新生成函数加入 `__all__` |
| ⑦ | **运行注册表测试** | 终端 | `.venv/bin/python -m pytest src/test/unit/core/test_registry.py -v` — 验证 TTL/前缀/键名完整性 |
| ⑧ | **验证标记合规** | 终端 | `.venv/bin/python scripts/check-test-markers.py` — 确认测试文件标记无遗漏 |

> **LLM 模块补充步骤**：在上述 registry 清单基础上，新增 LLM 模块还需完成领域特定步骤——`llm/prompts.py` 新增 `_SYSTEM_{MODULE}` 常量与提示词构建函数；`report/html_writer.py`（HTML）+ `report/llm_content.py`（Excel）新章节双渲染；在 `core/data_registry.py` 为该模块登记 `DataModuleDef`（`cache_ttl` 即默认 TTL，LLM 惯例：分析类 4h、内容寻址类 24h；无需改 `config.json`）；`llm_settings.json` 加入推荐默认值并更新 [配置指南](../manuals/how-to-config.md)。
>
> **纳入LLM 输出评级（可选，开关 `module_quality_gate`）**：新模块默认不参与 `report/llm_quality.py` 的 A~F 分级（分级为只读旁路，未登记不影响任何既有功能）。若需纳入：在 `_MODULE_KEYS` 追加模块键（顺序须与 `llm_content` 四元组位置一致）、在 `_LENGTH_THRESHOLDS` 设定该模块的 `(降级下限, 参考篇幅)` 双阈值（依据真实健康输出实测字符数标定）；若其提示词规定了固定章节清单，还需在 `_REQUIRED_MARKERS` 登记标记——`test_llm_quality.py::TestRequiredMarkersMatchPrompts` 会直接比对提示词常量，标记与提示词不同步即测试失败。

> **提示词内容必须进指纹（唯一事实来源 `llm/module_fingerprint.py`）**：缓存键与提示词内容脱钩会静默复用陈旧结论（键不变 → 预检命中旧键 → 不重生成、不报错）。因此**凡进了提示词的段落都必须进该模块的指纹**：已渲染文本（`competitive_context` / `data_quality_text`）、量化指标（`metrics`）、以及 `pipeline_data` 派生的【环比变化】【数据质量降级】两段——**只进「提示词确实含该段」的模块**，不进提示词的模块并入即纯成本失效。判据与完整清单见 `llm-technical.md` §7.1。
>
> **开关改变提示词 → 同一后缀函数供两侧调用**：凡开关**会改变提示词内容**（`deterministic_signal` 注入信号块与确定性信号摘要、辩论增强后缀），其开关判定必须**收敛在后缀函数内部**，由 `module_fingerprint.py` 的构造器统一调用——写侧与预检侧只调用同一构造函数，不得任一环节自行拼接（自行拼接的后果是两侧结果永久不等：写侧照常写入、预检侧永不命中，表现为「开关看似生效但每次仍全量调用 LLM」）。后缀函数关闭时返回 `""`（键不变、不误伤既有缓存），开启时返回稳定短串（如 `"_dh"`）。**内容指纹型**后缀（如 `decision_ledger.lessons_cache_suffix`、`prompts_signals._signal_digest_cache_suffix`、`signal_ledger.summary_cache_suffix`）另取块内容 md5 作版本，使数值变化即换键。

> **追加型状态文件一律走共享原语 `core/jsonl_store.py`**：`perf`（性能历史）、`decision_ledger`（决策账本）、`signal_ledger`（信号账本）三者的「读全文 → 拼接 → 写临时文件 → `os.replace`」逻辑已抽为 `append_jsonl_atomic()` / `read_jsonl()`，**新增任何 JSONL 持久化都不得再抄一份**——各自只保留自己的序列化口径（如 `decision_ledger` 的 `sort_keys=True` + `ensure_ascii=False`）与 `prefix`/日志标签，行为逐字不变由 `test_jsonl_store.py::TestDelegationPreservesBehaviour` 锁定。新增持久化文件时**必须**在 `src/test/conftest.py` 的 `_isolate_sensitive_paths` 中把路径重定向到 `tmp_path`，不得依赖测试自行清理。
>
> **保留窗口分两类，不得混用**：① **遥测类**（`perf_history` 5000 行、`datasource_health` 2000 行）用 `append_jsonl_atomic(..., max_lines=N)`——按行数截断，丢的只是遥测样本；② **业务账本**（`decision_ledger` / `signal_ledger`）用 `prune_jsonl_by_age(path, retention_days=730, date_key=..., keep=...)`——一行一份状态，按行数截断会连最旧的**已结算**样本一起裁掉、跨期反思随即失样本；决策账本对 `settlement` 事件用 `keep` 谓词永久保留。坏行不裁（不替读取侧吞掉损坏证据），缺日期字段的行保留。

> **统计类输出默认只算「实时」记录**：凡把历史记录折叠成统计/排行榜/提示词摘要的功能（如 `core/signal_ledger.py::fold_signals(live_only=True)`），必须给每条记录附来源标签并可区分「可证明为实时」与其余，**默认只统计实时记录**、且**不引入新的合成数据开关**——来源判定复用既有数据质量设施（逐品种 `data_freshness` + 降级事件），未识别的取值一律保守判非实时；确需乐观缺省时（无逐品种条目可证伪）必须显式写入理由字段，不得静默。

### 新增功能开关检查清单

全部功能开关以**注册表驱动**：`config/features.py` 的 `feature_switch_registry`（唯一事实源）一处登记，即自动出现在三个面，**不得在任一渠道层另写一份开关清单**。每条声明六个字段——显示名、说明、**作用域分组**、**默认值**、产物影响、**实验身份**（末位可选，默认 `False`）。

**先定作用域分组，再定默认值，实验身份独立标注**（三者解耦，这是本注册表的核心取舍）：

| 作用域分组 | 成员特征 | `default` | `experimental` | 面板标题 |
|:--|:--|:--|:--|:--|
| `GROUP_PORTFOLIO` | 成本 / 申赎状态 / 成本收益 / 风险调整 | 混合 | `False` | 💼 持仓与交易 |
| `GROUP_MARKET` | 温度 / 估值分位 / 景气度 / 危机回放 | 混合 | `False` | 📈 市场与估值 |
| `GROUP_FUND_STYLE` | 候选比较 / 行业 Beta / 因子目录 | 多数 `False` | `False` | 🧩 基金与风格 |
| `GROUP_EVENT_SUMMARY` | 事件窗 / 情绪热点 / 数据质量 / 本期要点 | 混合 | `False` | 📰 事件与摘要 |
| `GROUP_PRESENTATION` | 只改呈现与追问入口 | `True` | 实验项 `True` | 🧭 呈现与交互 |
| `GROUP_MECHANISM` | 提示词注入 / 输出评级 | 机制项 `True`、实验项 `False` | 实验项 `True` | ⚙ 机制与质量 |
| `GROUP_STANDALONE` | 新增整页签或多期回放 | `False` | `False` | 📑 独立章节与回放 |
| `GROUP_CHAPTER_OPTIONS` | 不独立上屏，由 `[C]` 作章节子项渲染 | `False` | `False` | 🧩 章节内选项 |

**域与面板派生**：`GROUP_DOMAIN`（组 → 五域：报告内容 / 呈现与机制 / 数据与线路 / LLM 运行 / 运行与诊断）、`DOMAIN_ORDER`/`DOMAIN_LABELS`/`DOMAIN_HINTS`（Web 五域编排与提示）、`PANEL_GROUPS`（`[S]` = 六个内容组；`[C]` = `standalone` + `chapter_options`）均由注册表派生，新增组须同时补齐这三处映射（`dev-verify` 的注册表不变式用例会拦截漏配）。

| ② | **定作用域与默认值** | 同上声明第 3、4 位（第 6 位 `experimental` 可选） | 作用域入八组之一（持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 呈现与交互 / 机制与质量 / 独立章节与回放 / 章节内选项）；会改变产物且未验证 → `experimental=True` + `False`；常驻能力 → `False`（默认）+ `True`。作用域决定面板分块、`experimental` 决定实验身份与 `--experiment` 取值域、`default` 决定出厂取值——三者解耦，转正不会摘掉面板入口 |
| ②′ | **回答产物影响** | 同上声明第 5 位 | 该开关**能否改变报告产物内容**——能则 `True`，仅影响入口可见性（菜单项/卡片显隐）则 `False`。答 `False` 者不进报告生成条件自述（`enabled_experimental_features()` 按此过滤）：报告是脱离本机流转的文件，列进一个不改任何字节的开关，读者会推断内容受其影响 |
| ③ | **消费开关** | 功能实现处 | 一律经 `is_feature_enabled()` 读取；开关判定若影响提示词，须收敛在缓存后缀函数内部（见上方「缓存指纹必须读写两侧同源」） |
| ④ | **覆盖三面** | 自动 | TUI 菜单 `[S]`（四组分块取自 `GROUP_ORDER`）/ Web 配置面板（同构四组，服务端动态下发）/ CLI `--experiment`（只开全部实验项的简写）与 `--feature NAME=VALUE`（全域双向）均由注册表生成，无需改渠道代码 |
| ⑤ | **验证** | 终端 | `.venv/bin/python -m pytest src/test/unit/config/test_features.py src/test/unit/web/test_config_edit.py -v` — 注册表不变量（分组合法 / 五字段齐备 / 键集与派生投影一致）+ 配置编辑白名单覆盖全注册表 |

> **菜单项/卡片可见性由开关门控**：若实验功能有常驻入口（TUI 菜单项、Web 卡片），开关关闭时必须**就地裁剪**而非渲染后置灰——TUI 侧向 `tui/tui_menu.py::FEATURE_GATED_ITEMS` 登记 `(菜单项, 开关名)`，Web 侧由 `system_info` 透出 `*_enabled` 供前端决定是否渲染；`tui/tui_menu.py::_apply_feature_gates()` 是统一裁剪点。

> **「实验性」的准入与转正判据**：实验项的判定口径是「**能否改变报告产物内容**」，而非「新不新」。新增能力默认关的惯例适用于会改变产物的能力（LLM 增强、指标开关、数据结构变更）——它们需要真实数据验证，默认关是对既有用户产物的保护。但**只读诊断类能力（不改产物、不写文件、不在默认路径产生隐式网络或耗时代价）应默认开启**：默认关的实际代价是让最需要它的人（环境出故障的那批）恰好看不到它，而开启对默认输出零代价。此类能力转正后：① `experimental` 置 `False`、`default` 改 `True`（**两处字段改动**；作用域属机制与诊断，`group` 不变）——面板可见性随分组自动延续，不再出现「转正即从面板消失」；② 不再进产物自述（`affects_report` 答 `False` 且 `experimental` 为 `False`）；③ 门控读取（`FEATURE_GATED_ITEMS` / `system_info`）**保留**——转正不等于不可关，`features.json` 置 `false` 仍可隐藏入口；④ 门控表与消费点均须有「默认配置下入口可见」的测试，只依赖 `patch` 覆盖取值的用例测不出默认值本身。系统自检（`doctor_check`）是此模式的首例。

> **内部接缝类开关也应转正（第二类首例：`datasource_adapter`）**：判据与上一条同源但落在另一面——**开关两种取值下报告产物是否等价**。若等价（新实现只是把既有路径换成结构更清晰的等价实现，差异经等价性回归测试逐项锁定且不影响下游取值语义），则它既不是用户可感知的功能、也不是用户能做的选择，摆在用户面前只会让人误以为「开了有好处」，而默认关的实际代价是**生产路径从不执行新实现**、新数据源/新字段接入时才第一次实跑。此类开关转正为默认开（摘除实验身份，`group` 不变）：① `experimental` 置 `False` 且 `default` 置 `True`（**两处字段改动**）；② 开关经跨版本稳定期评估后**进一步内置化**（删开关与关态死分支；回退仅保留「适配器不可用时回落既有映射」的运行时安全网，不再可经配置触发）；③ 测试守两向——默认配置走新实现、回退与既有实现等价（见 `test_features.py::TestDatasourceAdapterBuiltinized` 与 `test_quote_adapter_parity.py`）。数据源适配契约（`datasource_adapter`）是此模式的首例（已内置）。

> **读侧增强类开关也应转正（第三类首例：`deterministic_signal` / `module_quality_gate` / `llm_debate_conditional`）**：判据落在「**开启的代价是否只在读侧**」——只在既有提示词或既有产物流水线上追加一段由**已算出的**数据派生的内容，不新增 LLM 调用次数、不写新的持久化文件、无隐式网络与耗时；且该段内容有确定的收益（方向性结论替代裸数值、结构化契约替代表格猜测、质量分级提示读者降级参考、缺凭据时给可读指引）。此类开关默认关的实际代价是**机制在生产路径从不执行**，用户手上的产物看不到这层增强；用户若逐项去 `features.json` 里打开它，等于用配置承担了本该由默认值表达的取舍（转正判据的可观测量：见 core/experiment_stats.py 的启用次数统计与 doctor 账本概览）。转正口径：① `experimental` 置 `False` 且 `default` 置 `True`（**两处字段改动**；作用域属机制与诊断，`group` 不变）；② `affects_report` **照实答 `True`**——它们确实改变产物内容（`deterministic_signal` 注入信号块、`module_quality_gate` 注入质量横幅、`llm_debate_conditional` 追加情景段），故 Web 面板照常带「（影响报告）」标记；③ 开关保留为关闭杠杆，`features.json` 置 false 即回到「未引入本机制」的行为；④ 凡开关改变提示词者，其缓存后缀函数（`structured_header_cache_suffix()` → `_dh`、`debate_feature_cache_suffix()` → `_c`、`prompts_signals._signal_digest_cache_suffix()`、`core.signal_ledger.summary_cache_suffix()` → `_sg`）随之由「默认返回空」变为「默认返回非空」——**升级后首次运行会换键重生成一次**，属预期行为，须在变更记录中写明；⑤ 测试补四向——默认值、非实验项（`--experiment` 取值域退出）、显式关闭仍走未引入前的路径（关闭基线必须**显式**置 false，不能再依赖 `reset_feature_flags()`，它现在返回的是已转正的默认值）、默认配置下走增强路径（见 `test_features.py::TestReadSidePromotion`）。
>
> **章节/页签类开关转正目标是独立章 / 事件与摘要组（第四类首例：`holding_change_review` / `whatif_trade_cost` / `event_window_impact` 已按此归入，default 保持 `False`）**：判据落在「产物形态」——独立章节/页签类能力验证通过后的归宿按作用域入独立章节与回放 / 分析增强组：`default` 保持 `False`（默认产物字节不因转正变化，读者拿到的报告不因转正多出章节），面板入口随分组自动延续，`--experiment` 取值域随 `experimental` 摘除同步退出，产物自述与启用统计随实验身份移除（「质量可能不稳定」警示只属于未验证功能，统计的观测使命随转正完成）。转正定义因此为「**摘除 experimental 身份，作用域变则同时改 group**」。
>
> **刻意不转正的两类（判据的反面）**：**写盘积累型**——`decision_reflection` / `report_qa` 仍标 `experimental=True`（账本结算样本尚不足以判转正，撤销死线见 plan.md）。`signal_ledger`（确定性信号沉淀）不再单独设开关：其真实积累已验证（账本有存量数据、写盘幂等开销可忽略），并入 `deterministic_signal` 转正（摘除实验身份）。**调用次数放大型**——`llm_debate_procon` 把一次 `expert_review` 调用换成最多三次（pro → con → synthesis），默认开启直接改变费用与耗时量级，保持默认关、由用户按需开启。集中度问答不再受开关控制（原 `llm_debate_qa_concentration` 已撤销），改为辩论流程内建段落（阈值触发）。实验功能的真实使用情况可用 `core/experiment_stats.py`（启用计数）加 `doctor` 账本概览观测，作为转正/撤销的客观数据。

> **生命周期单一事实位**：全部 `experimental=True` 开关的「实验目的 / 判据来源 / 转正条件 / 撤销条件 / 观察数据源 / 当前态」以 `technical.md` §6.9「实验项生命周期表」为**单一事实位**——立项（新增实验项）、转正（摘 `experimental`）、撤销（删注册表条目与机制）任一发生时**必须同步刷新该表**；判据详文仍留在 `plan.md` 死线条目与版本归档的评估记录（两者回链 `technical.md` §6.9「实验项生命周期表」，表内不复制全文，避免两处口径漂移）。上文的转正判据分类学讲「怎么判」，`technical.md` §6.9 记录「当前每个实验项处在哪一步」。

> **诊断类命令不得依赖 config 初始化**：`doctor` / `view-logs` / `check-sources` / `health-history` / `cassettes` 在 `main()` 中**先于 `init_config` 分派**——配置损坏正是它们要定位的场景，若先初始化配置再分派，用户会在最需要诊断能力时被配置错误挡在门外（死锁）。新增诊断类命令遵循同一模式：**先分派、后初始化**，并把「命令失败」（退出码 2）与「命令跑完但结论不佳」（退出码 1）用 `_EXIT_SUCCESS` / `_EXIT_PARTIAL` / `_EXIT_SEVERE` 常量区分开，不得写裸字面量。**诊断类命令自身永不抛异常**——任何内部异常都转成一条结果行，否则等于在最需要它的时刻失效（`core/doctor.py`）。

> **新增数值解析一律委托 `core/num_utils.py`，禁止自写 `try: float(x) / except`**：`float("nan")` / `float("±inf")` **不抛异常**，该形态的兜底对它们完全无效，脏值会一路穿透到聚合、绘图与 JSON 序列化；`value or 0.0` 同样是**假兜底**（NaN 是真值，`or` 不会短路）。按语义选入口：宽容解析（含数值字符串）用 `safe_num`、类型契约敏感场景用 `strict_num`、替代 `or 0.0` 惯用法用 `finite_or`、判定谓词用 `is_finite_number`。**不改变既有失败口径**（`0.0` 还是 `None` 由调用方契约决定），只保证「返回的数值一定有限」。

### 盘中敏感性（`market_ttl`）

盘中敏感是**数据属性**，登记在注册表，不进用户配置：

```python
DataModuleDef("股票价格", "price", cache_prefixes=("price_",),
              cache_ttl=CACHE_DAILY, market_ttl=30.0, cache_groups=("preload",))
```

- `get_ttl(data_type)` 解析顺序：**盘中敏感且有 `market_ttl`** → 交易时段用 `market_hour_ttl`（config 数值覆盖，缺钳 [30, 86400]）→ 否则静态 `cache_ttl` 覆盖 → 注册表默认 → `CACHE_DAILY` 兜底（未注册类型）。
- 只有行情价/指数是分钟级变化，**其余类型不得声明 `market_ttl`**——把非行情数据放进盘中降频等于把上游请求翻几倍而拿回同一份数据。
- 读侧（`cache.get`）与清理侧（`cleanup_expired`）取同一个数：`get_ttl` 是唯一出口，不得在任一侧另算。
- 改 TTL 默认值后必须同步两份只读参考表（`technical.md` 缓存各表 / `how-to-config.md`「cache_ttl 可调参数」）——`check-doc-drift.py` 第 22 项会逐类型对账。

### 缺失探测负缓存

只在**确定性**缺失时写入（已发布静态文档的章节 404、章节阶与备源均无正文），瞬时网络错误不写——否则一次抖动会污染整个 TTL 窗口。TTL 过短会反复重试打源、过长会把「源侧后来补解析」长期遮蔽。新增同类负缓存**必须**登记注册表（`data_type` + `cache_prefixes` + `cache_ttl`），否则清理侧按未注册默认 24h 判定、`cache_ttl` 覆盖与文档表格都覆盖不到。

### 精确键名缓存

```python
DataModuleDef("我的固定键", "fixed",
              exact_cache_keys=("my_special_cache",),
              cache_ttl=CACHE_WEEKLY),
```

精确键名不会被前缀通配误匹配，适合固定文件名的缓存。

### 计算模块注册表（_COMPUTATION_REGISTRY）

除 `_MODULE_REGISTRY`（有缓存的数据模块）外，还维护 `_COMPUTATION_REGISTRY`——纯计算模块（无缓存）的注册表，实现在 `core/computation_registry.py`（`core/registry.py` 顶部 re-export，原访问面不变）：

```python
@dataclass(frozen=True)
class ComputModuleDef:
    name: str               # 中文名称
    module_key: str         # 唯一键，如 "analytics_liquidity"
    label: str              # 短标签（日志/提示）
    dependencies: tuple     # 前置数据模块键名
    description: str        # 功能说明
```

| module_key | 名称 | 依赖 | 状态 |
|:-----------|:-----|:-----|:----:|
| `analytics_metrics` | 量化指标计算 | bond_yield, history | ✅ implemented |
| `analytics_liquidity` | 流动性分析 | — | ✅ implemented |
| `analytics_fx_exposure` | 外汇敞口分析 | — | ✅ implemented |
| `analytics_scenario` | 情景分析 | history | ✅ implemented |
| `analytics_alignment` | 组合校准分析 | — | ✅ implemented |
| `analytics_inferrer` | 用户画像推断 | — | ⏳ planned |
| `analytics_fact_checker` | 事实锚定校验器 | — | ✅ implemented |

新增计算模块只需在 `_COMPUTATION_REGISTRY` 中添加一行 `ComputModuleDef`，纯算法模块无需缓存注册。

### 费用与币种（LLM）

费用有三条硬纪律，改动任何一条都要同步跑 `test_pricing_currency.py` 与 `test_cache_fingerprint_alignment.py` 的对应用例：

1. **展示币种 = 模型生效币种**：`pricing.model_currency(model)` 解析（配置币种若条目 `alt` 提供 → 否则原生币种）；`MODEL_PRICING` **每条显式声明 `currency`**（CNY 厂商也写），改配置币种不会改变条目自身标价。
2. **跨币种不相加**：累计/历史/预估一律用「币种 → 金额」桶。桶的读写规则在 `core/costs.py`（`costs_of` 读取 / `add_cost_bucket` 累加，core、llm 与 `scripts/_perf_history` 三方共用，避免分层倒置与三份实现）；累加与格式化在 `llm/pricing.py`（`add_cost` / `merge_costs` / `format_costs`）。**新增费用展示位一律用 `format_costs` 出串，不得自拼符号与数值**。
3. **唯一的折算点在日预算**：`budget_status()` 判定超限时用 `pricing.FX_TO_CNY` 把各币种支出折到本币比对，折算结果**不进 `display`**（展示保持原生币种）；缺汇率的币种在摘要里点名，不按 0 静默计。

**重算归因有两条路径，新增模块两条都要覆盖**：预检侧（`_compute_module_cache_info` 覆盖的四个基础模块）与骨架侧（`skeleton.generate_llm_content`，覆盖键在上游产出后才确定的模块如 `self_review`）。只加一条会让 `recompute_reasons` 的 `ttl_expired` 占比失真，据此调 TTL 会判错。同理，命中/未命中**计数**也要两条路径都记（骨架路径已计入），且汇聚器必须在「LLM+新闻」阶段**之前**绑定——预检在该阶段内部，晚绑即丢每次进程重启后首份报告的全部样本。

`budget_status()` 只返回 `{enabled, exceeded, display}`：三渠道读 `exceeded` 作硬闸、前端读 `display` 整行直出。新增消费方只读这三个键，不要另加金额字段——那会让同一份数据出现两套格式（此前前端自拼 `low`/`symbol` 字段，后端改多币种后 `.toFixed()` 直接抛错）。

### 无需手动维护的派生产出

新增模块时只需在 `_MODULE_REGISTRY` 添加一行 `DataModuleDef`，即可自动同步到以下位置：

- 缓存 TTL 默认值 → `get_cache_ttl_defaults()`
- 盘中短 TTL（仅 `market_ttl` 非空类型）→ `get_market_ttl_map()`
- 缓存前缀/精确键名映射 → `get_prefix_type_map()` / `get_exact_type_map()`
- LLM settings 键名 → `get_known_llm_settings_keys()`
- LLM 模块名称 → `get_llm_module_names()`

> 报表页签标题与顺序由两张**独立**注册表分别驱动，**不**随 `_MODULE_REGISTRY` 自动派生：
> - `get_report_sheet_name(sheet_key)` → 读 `_REPORT_SHEET_NAMES`（sheet key → 中文标题映射；派生视图：非 LLM 章键值由 `_REPORT_SECTION_DEFAULT` 条目派生，LLM 章标题显式登记、差集键集为 `_LLM_SHEET_NAME_KEYS`）
> - `get_report_section_order(config)` → 读 `_REPORT_SECTION_DEFAULT`（章顺序与分组）
>
> 二者职责不同：前者管「页签叫什么」，后者管「章按什么顺序排」。新增报告章在 `_REPORT_SECTION_DEFAULT` 登记后，页签标题由派生视图自动跟进（LLM 章例外：其显示名在 `_REPORT_SHEET_NAMES` 显式登记并把键声明进 `_LLM_SHEET_NAME_KEYS`）；若该页签属报告章，还需在 `_REPORT_SECTION_DEFAULT` 登记顺序（`scripts/check-semantic-index.py` 校验合并章引用的 sheet key 存在于 `_REPORT_SECTION_DEFAULT`）。

### 测试

registry 的测试在 `src/test/unit/core/test_registry.py`，验证 TTL 默认值完整性、前缀类型映射一致性、精确键名映射、LLM settings keys 与模块列表匹配、所有 LLM 模块都有 settings_suffix、缓存分组标记完整性。

```bash
.venv/bin/python -m pytest src/test/unit/core/test_registry.py -v
```

## 任务编号规范与自动保障

### 编号规则

- `plan.md` 任务清单：`plan-{全局递增序号}`（从 1 开始单调递增，已归档或已完成序号不回收）
- `review-findings.md` 自审问题：`rf-{全局递增序号}`（同样从 1 开始单调递增）
- 序号仅用于标识，**不编码优先级/层级/分类**；优先级在分类表头文字中表达
- 跨文档引用时必须带前缀（`plan-`/`rf-`）避免歧义；历史数据保持原名不追溯重命名

### 编号源标记

各管理文档头部维护「编号源」标记记录**下一个可用编号**：`plan.md` → `plan-next`、`review-findings.md` → `rf-next`。新增任务时**取当前值**作为编号，完成后**递增更新标记**（+1）。标记单调递增、绝不回退，保证与历史归档编号不冲突。

### 语义化命名

代码标识符（函数/变量/类/模块/config 键）与文档正文一律用**语义名**，**禁止用任务代号**（`plan-{N}`/`rf-{N}`/系列代号）。任务代号仅存在于内部计划表作链接锚点，不扩散到实现层。该纪律由双脚本强制——`check-code-traces.py`（负面禁止）+ `check-semantic-index.py`（正面校验「功能语义命名表」与代码一致）。

### 外部借鉴前置比对清单

引入外部项目（开源仓库、方案、文章）的做法前，**必须先对照本仓库现状**——实测教训：已有多项借鉴（LLM 输出自检、多空双视角辩论、Prompt 模板外置、多源新闻交叉验证）的立项前提被「本仓库已有实现」推翻，属可避免的往返成本（该清单即为此固化的纪律）。

设计文档（`docs/plan/`）开头须逐条填写结论：

| # | 比对项 | 结论要求 |
|:--|:-------|:---------|
| 1 | **能力是否已存在** | 列出检索到的既有实现（模块/函数/开关）与代码位置；已存在则**直接归档为「已评估未采纳」**并写明证据 |
| 2 | **部分存在时的缺口边界** | 明确「已有什么」与「真实缺什么」，据此**重新定位**（例：确定性事实校验已有 → 模型自检改为「分层不重叠」而非新建同类） |
| 3 | **是否已有配置级/开关级替代** | 用户诉求能否由既有配置键或开关满足（例：prompt 定制已由 `system_prompt_*` 覆盖）——已满足则价值须重估 |
| 4 | **是否触及缓存指纹与已校准输出** | 改动若进入提示词正文、影响输入摘要或产物结构，须评估缓存键同源与既有校准的复验成本（缓存指纹唯一事实来源约束） |
| 5 | **是否有真实消费者** | 新能力必须有真实调用方（CLI/报告/评测脚本）；否则属死代码，须先定消费者或不做 |

> 比对结论写进对应设计文档与任务编号管理文档；已存在的能力直接归档为「已评估未采纳」并写明证据。

### 自动保障机制

任务编号全局单调递增、归档不回收，由 `check-task-numbering.py` 校验，防止新增编号与历史归档冲突。五层自动保障：

| 机制 | 触发 | 跨机器 |
|:-----|:-----|:------|
| **P0/P2 门禁** | 提交/发布前 10 个 `--ci` 守护脚本全量（清单见 P0/P2 门禁条款）；P2 另含设计护栏段（gate 内置 `check-style-guardrails`，E 级拦 / W 级观察统计） | ✅ 零配置 |
| **dev-verify preflight** | `test-runner.py --mode dev-verify` 自动运行（仅 `check-task-numbering` 快检；重量守护不入预检，由钩子唯一执行防同树重复） | ✅ 零配置 |
| **Claude Code hook** | 编辑 `plan.md`/`review-findings.md` 后实时校验 | ⚠️ clone 后运行 `.venv/bin/python scripts/hook-install-claude.py` |
| **git pre-commit** | `git commit` 执行十守护（与 P0/CI guards 同源）：**读写分层调度**——不读 folders.md 的守护（快集 code-traces/task-numbering/semantic-index/requirement-trace + py 域 file-length + 测试域 test-redundancy）先行后台启动，与 `check-doc-drift` 段并行执行（跨域守护恒跑；涉及**任一被统计域**（`docs/managements/` / `src/test/` / `src/python/` / `scripts/`）时 `--sync` 写路径串行先行并自动回写统计快照，其中暂存含 `src/test/` 时追加 `--with-test-count` 校验 `test-coverage.md` 的收集派生计数——否则新增用例后计数静默陈旧、只在 CI master 档才红；其余提交纯 `--ci` 后台并行）；读 folders.md 的 version-consistency 与 doc 域（doc-traces/doc-links）在 doc-drift 完成后启动（避 --sync 写读竞态）；域条件不变（doc 域仅 `*.md`、py 域仅 `*.py`、测试域仅 `src/test/` 变更触发），典型提交约 1~4 秒；六守护另有结论缓存（doc-traces/semantic-index/doc-links/code-traces/requirement-trace/doc-drift，输入与逻辑指纹未变回放上次结论，冷/热 --ci 输出逐字一致）；CI guards job 恒全量兜底 | ⚠️ clone 后运行 `sh .githooks/install-hooks.sh` |
| **CI guards job** | push / PR / tag 时自动校验（10 个 `--ci` 脚本之一） | ✅ 零配置 |

> `core.hooksPath` 与 `.claude/settings.json` 均为本地配置、不随仓库同步，新机器 clone 后运行上方激活命令一次即可；hook 脚本本体（`.githooks/`、`scripts/`）随仓库同步。

## 版本发布流程

发布版本时，按以下六步顺序执行：

> 可用 `scripts/release.py` 分步编排（发布流程的可执行封装，每步独立可审阅、失败即停）：`check`（预检）→ `archive-init`（**仅新小版本首发需要**：三份归档 + 目录树块 + 三处索引行一次建齐，幂等）→ `prepare`（版本全链、changelog 发布段归档**并自动重写归档头部「涵盖版本 / 归档时间」（区间与并入记录由归档内各发布段标题派生，无需人工维护）与主文件指针的版本号/日期/归档文件名**、一致性 `--fix`，收尾自动 `doc-drift --sync`）→ `refresh` + `evolution --release`（数据刷新——纯文档变更〔仅 `.md`/图片〕自动跳过 bench+collect，`--force-refresh` 强制；演进快照，evolution 收尾同样自动 sync）→ `gate`（P2 门禁：verify 与 regression 并行；若 `refresh` 的 bench **实跑过 `unit`** 且代码指纹未变，则复用该次结果替代 verify（`unit` 是 verify 的严格超集，由标记不变量保证），否则实跑；十守护并行且并发度随核数收敛 ≤4 路；`--with-portability` 加跑 portability 探针；全绿后写「版本+代码指纹」通过戳——**指纹 = `CODE_PATHS` 下文件内容的 sha256（与是否已提交无关）**：gate 打戳时 prepare 的改动尚未提交、publish 提交后再算，两者仍相等）→ `publish --title`（**代码指纹与 gate 戳一致时复用 P1 verify**；提交前按钩子同源参数 `--sync --ci --with-test-count` 同步统计快照——只跑 `--sync` 时 `test-coverage.md` 收集计数不被校验，会「本地通过、钩子仍红」白跑一轮；同步失败即中止 + release 提交 + P1 verify + `--no-ff` 合并 + tag）→ `devbump`（切开发版 + 默认 `git push origin dev`（`--no-push` 跳过），并清空上一版迁档占位节）；bench 默认只测发布子集四档（`--full-bench` 全量；`--bench-jobs N` 调整采集并行度，改变并行度会改变耗时口径，环境表需同并行度可比），采集顺序为「场景档先、长尾档后」（`regression → integration → unit → dev-verify`）——`--fail-fast` 只取消尚未启动的档，长尾档压后才能让场景失败立刻中止；每命令耗时、执行环境（provider/model/thinking）与 agent 会话 token 累计入 `logs/release.jsonl` 台账，失败命令另写 `failure`（失败步 / 退出码 / 报告目录 / 失败用例名 / 输出尾部）；`check` 会预演 changelog 派生（只算不写），publish 在 gate 戳指纹不一致时点名 gate 后改动的代码文件并说明将实跑 P1 verify，提交/合并/tag/推送分段计时入账（发布墙钟、token 成本与执行模型均可跳版本对拍）；rf/plan/docs-plan 归档迁移的**机械部分已由 `prepare` 自动完成**（含 plan.md「当前迭代」概述行按剩余任务重算在办项数与 P1~P4 分档编号；人工只复核条目归属与设计文件判定，见下方步骤③），`gate` 会断言该版本台账已迁完、changelog 归档段非空，未迁/为空则前置中止；`prepare` 不跨版本发布（`--version` 与开发链推导值不一致时立即中止并给四步指引）；**分层纪律**：归档迁移或任何涉及管理文档/代码注释的改动完成后，进 `gate` 前先跑秒级便宜守护（至少 `check-doc-traces --ci` + `check-doc-links --ci`，改动面大时十守护全跑）——守护发现前置，避免 P2 门禁的全量 regression 因文档级 finding 白跑第二轮。下列手动命令为底层口径，脚本失败时按手动步骤排查。**publish 的 release 提交仍走 pre-commit 钩子全量守护**（不跳过）：与 gate 重复约 2~6s，换取「自动化提交也不旁路守护」的兜底——实测收益小于风险，故不做跳过。

**① 版本号一致**

先修改 `src/python/core/constants.py`（`APP_VERSION`），然后运行：

```bash
.venv/bin/python scripts/check-version-consistency.py
```

按 `[ERR]` 提示逐个同步其余文件（`pyproject.toml`、`README.md`、各管理文档），直到全部 `[OK]` 再提交。任何版本号变更均应全局覆盖，避免遗漏。

**② 发布数据文档刷新**

发布版本前，必须运行（**纯文档变更例外**：上次发布 tag 以来仅 `.md`/图片变更时，`release.py refresh` 自动跳过 bench + collect——测试计数无变化，`--force-refresh` 强制恒跑；doc-drift stats sync 与下列人工核对始终执行）：

```bash
.venv/bin/python scripts/test-collect-coverage.py --update-docs
```

按实时收集结果回写/核对以下文档的数据快照（非版本号），保证统计与目录结构时效性：
- `test-coverage.md` — 模式/unit 子标记/跨类/功能域各项测试计数（`--update-docs` 自动回写）
- `folders.md` — 项目统计表及目录树新增/重命名文件；**版本演进对照表（`## 版本演进对照`）每次发布必须更新**：「最新发布」列按新 tag 重跑快照统计（复现方法见 folders.md 表头：`git ls-tree` + `git cat-file --batch` 计行 + `git grep -c "def test_"` 数用例），「当前开发版」列同步重跑；列头版本号与 tag/日期由 `check-version-consistency.py --fix`（`evolution_head`/`release_tag` 断言）同步，只改版本号不刷演进表数据行属发布遗漏
- `datasource.md` + `datasource-reliability.md` — 数据源清单/路由归属/可靠性描述与实际代码配置一致

`release.py evolution --release` 输出的「需人工核对的注释行」（test-coverage 用例口径注释中的 pytest 实际收集数与 opt-in live 项数、folders.md 文档注释行的目录分解数）脚本不代写，须按实测回填后再提交。

数据快照更新与「版本号一致」的版本头同步可在同一次提交内完成。

**③ 发布归档迁移（四项强制，未完成不得继续 `gate`/`publish`）**

- ① `review-findings.md`「已解决问题」区**全部**条目迁入对应版本的自审归档（同步更新归档头部涵盖版本/追加行与主文件「归档档案」索引行）——`release.py prepare` 自动：原表逐行搬运 + 占位 + 头部/索引延展，人工复核归属
- ② `plan.md` 不得残留 ✅/已完成任务节（完成态移入对应版本的 plan 归档）——`release.py prepare` 自动搬已完成节（**支持 `##`~`####` 各级标题**：台账任务节嵌在 `### P1~P4` 下，归档侧统一降为扁平 `## plan-N … ✅`），人工复核完成标记是否打对
- ③ changelog 已发布段移入对应版本的 changelog 归档（**归档段必须含实际条目**：`prepare` 归档前先断言开发段不是占位句，`gate` 再校验归档文件该版本段非空——空发布记录一旦落盘无法补回） + 归档头部「涵盖版本」「归档时间」两行重写 + 主文件「最近发布」指针的版本号/日期/归档文件名同步（`release.py prepare` 全部自动执行：段追加与头部区间/并入记录均由归档内 `## [版本] - 日期` 段列表派生；跨小版本时指针链接自动换名到新 train；人工只需核对 diff 中指针与归档索引行）
- ④ `docs/plan/` 中**已完成任务**的迭代设计文件移入对应版本归档子目录（在办任务的设计文件保留，按其关联 plan/rf 任务状态判定），同步更新 plan.md/folders.md 引用链接与目录树——`release.py prepare` 按「引用编号均已归档」判定候选并自动 `git mv` + 改写引用 + 搬目录树，人工复核候选是否真完成（无任务编号引用者也会列出待确认）

**④ 版本标签**

完成版本号更新并提交后，执行：

```bash
git tag v{版本号}
git push origin --tags
```

确保每次发布都可追溯。

**⑤ 开发版本切换**

发布版本并打 tag 后，**立即**将 `APP_VERSION` 和所有管理文档版本头改为**下一个版本的 `-dev`**（如发布 v0.6.8 后即改为 v0.6.9-dev），运行 `check-version-consistency.py` 验证全链 `[OK]` 后提交，然后继续开发。开发期间版本号始终标识为下一个预期发布版本的 `-dev`。

`release.py devbump` 会把这条链一次走完（版本号 + 文档版本头 + 提交），并在同一提交里**清空上一版的迁档占位节**（`### 开发期已修复（X-dev）` 只余一行「本版已随 vX 发布迁入归档档案」）——新开发周期的台账从空开始，上一版的归档信息只在归档文件与「归档档案」索引里。收尾的**发布闭环校验**把下面⑥的纪律变成机检：`v{发布版}` 必须落在 `master` 历史内、`master` 的 `APP_VERSION` 为发布版、本分支为下一开发版，不符即退出 1 并逐项点名（无 tag 只告警，供 `--no-push` 试跑）。

**⑥ 合并入 master**

发布并打 tag 后，**必须**把 `dev` 合并入 `master` 并推送（`master` 是发布分支，只存放已发布状态；不得只打 tag 而不更新 master）：

```bash
.venv/bin/python scripts/test-runner.py --mode verify   # P1 合入门禁，必须先通过
git checkout master && git merge --no-ff dev -m "Merge branch 'dev' — v{x.y.z} 发布" && git push origin master
git checkout dev
```

合入后确认 tag 所指提交已在 `master` 可达（`git merge-base --is-ancestor v{x.y.z} origin/master`）；`master` 推送会触发 CI 的 P1（`verify`）档。本步与步骤⑤互不替代：⑤ 是让 dev 进入下一个开发周期，⑥ 是把已发布状态同步到发布分支。

### 发布前本地门禁前置（`release.py check` 已内置）

`check` 除分支/工作树/版本/tag/归档前置外，**默认执行两项本地门禁**（`--no-local-gate` 可跳过）：

1. **统计快照同步**：`check-doc-drift --ci`（秒级）——测试文件增删或计数变化后未跑
   `test-collect-coverage --update-docs` + `check-doc-drift --sync --with-test-count`，
   这里立刻红；
2. **本地全量测试**：`test-runner --mode dev-verify`（≈30s）——失败用例名直接可见。

**为什么前移到 check**：实测一次发布里 `refresh` 失败 1 次、`gate` 失败 3 次，累计白跑
≈150s 门禁墙钟，根因只有一个——改完代码**只跑了局部测试**（如 `pytest src/test/scenario`）
就进 gate，连带统计快照也没同步。这两项都便宜且失败信息直指修法，放在动手前查掉。

**纪律**：改完测试/代码 → 跑一次 `dev-verify`（不是局部目录）→ `test-collect-coverage
--update-docs` + `check-doc-drift --sync` → 提交 → 才跑 `release.py`。跳过任一步，
gate 会用 40s×N 次把它演示给你看。

### CI 失败排查

CI 有 5 类 job（`test` 按 Python 3.11/3.12/3.13 跑三份矩阵 / `guards` / `perf-gate` / `portability` / `format`），**失败先按 job 定位，再本地复现**：

| job | 失败症状 | 先看 | 本地复现 |
|:---|:---------|:-----|:---------|
| `test` ×3 | 同一用例三版本全红 | 用例名 + 断言值 | `pytest <case> -q`（本地不绿就是真缺陷） |
| `test` ×3 | 只在 3.11/3.12 红 | `SyntaxError`/新语法/`match` 特性 | 换版本跑（见 `pyproject` 的 `requires-python`） |
| `test` ×3 | 本地绿、CI 红 | **仓库状态相关断言**（见下） | `git stash` 后跑，或 `git clean -xdf` 后重跑 |
| `guards` | 单守护非零退出 | 守护名 + finding 行 | 本地跑同名 `--ci` |
| `portability` | `EncodingWarning`/`UnicodeDecodeError` | 哪个文件的哪次 IO | `scripts/test-runner.py --mode portability`（等价复现两道探针；单看编码档可 `PYTHONWARNDEFAULTENCODING=1 pytest src/test/unit -q`） |
| `perf-gate` | basic 模式 >60s | 阶段耗时排行 | `scripts/test-perf-report.py --gate` |
| `format` | `ruff format --check` 有差异（**非阻塞**） | 文件列表 | `ruff format .` |

**「本地绿、CI 红」的三类常见根因**（都踩过）：

1. **断言了随环境/周期变化的仓库状态**——例如「主台账至少有一节」在 `devbump` 清空占位后不成立；本地恰巧补了内容就绿，CI 上是空台账。对策见 §测试文件规范「勿断言随周期变化的仓库状态」。
2. **游离改动未提交**：`check-doc-drift --sync` 按**工作区**写统计、CI 按 **committed** 树校验 → 提交前确认受检文件全部入库。
3. **locale/编码**：本机 UTF-8 掩盖了缺 `encoding=` 的 IO（`portability` job 专治）。

**定位顺序**：`guards`/`portability` 秒级 → 先修它们；`test` 的失败面再看具体用例；`perf-gate` 最后（耗时波动大，先记 `loadavg`）。

### 回滚与热修

| 场景 | 做法 | 注意 |
|:-----|:-----|:-----|
| dev 上改坏了、还未发布 | `git revert <sha>`（保留历史）而不是 `reset --hard` | 撤销提交同样要过 P0 门禁 |
| 已合并 master、但还没打 tag | 反合 master 上的问题提交 → 走一次正常发布流程 | 不要直接 `push --force` |
| **已发布（打过 tag）** | 走**新版本**：修好 → 发布 `vX.Y.Z+1`；同时把出问题的版本在 issue/变更日志标注 | **不要移动或删除已推送的 tag**——已拉到该 tag 的用户会静默不一致 |
| 需要紧急绕过常规节奏 | 仍走 `check → prepare → gate → publish`，但可 `--no-archive` 跳过归档迁移（台账随后补） | 门禁一步都不能省；`gate` 会拦未迁档 |
| 数据被改坏（配置/持仓） | 用 `.bak` 或外部备份恢复（见 [数据与备份](../manuals/data-and-backup.md)） | `.bak` 只保留上一版 |

### 依赖升级流程

`requirements.txt` 与 `pyproject.toml` 双份声明，改依赖时**两边同步**：

1. 改 `requirements.txt`（**必须保持 UTF-8 BOM**，否则 cp936 的旧 pip 解析会 `UnicodeDecodeError`）与 `pyproject.toml` 的对应字段；
2. 重建虚拟环境或 `pip install -r requirements.txt` 验证可装；
3. 跑 `pytest src/test/unit -q` + `PYTHONWARNDEFAULTENCODING=1 pytest src/test/unit -q`（本地模拟 `portability` job）；
4. 若升级涉及数据源库（如 openpyxl/httpx/pandas）：跑一次 `--mode dev-verify` 与 `scripts/test-smoke-web.py`；
5. 记录到 `changelog.md`（写清版本号与已知行为变化），必要时在 [datasource-reliability.md](../manuals/datasource-reliability.md) 更新兼容性说明。
## 辅助脚本速查
`scripts/` 下**全部顶层辅助脚本**（按用途分类、含设计逻辑与使用逻辑；实现拆包的条目在各节注明内部模块）已独立成文：
**[辅助脚本参考（scripts-reference.md）](scripts-reference.md)** —— 需要查「某脚本干什么 / 怎么跑 / 何时跑」时看它。

本指南只保留**最常用的十条**与按域索引。

### 最常用十条

| 场景 | 命令 |
|:-----|:-----|
| 提交前门禁（P0） | `.venv/bin/python scripts/test-runner.py --mode dev-verify` |
| 合入前门禁（P1） | `.venv/bin/python scripts/test-runner.py --mode verify` |
| 发布门禁（P2） | `.venv/bin/python scripts/release.py gate` |
| 只重跑失败用例 | `.venv/bin/python -m pytest src/test/ -q --lf` |
| 提取失败用例清单 | `.venv/bin/python scripts/test-extract-failures.py` |
| 顺序依赖定位 | `.venv/bin/python scripts/test-find-order-dependent.py <合跑红的用例…>` |
| 文档统计快照回写 | `.venv/bin/python scripts/check-doc-drift.py --sync` |
| 测试计数回写 | `.venv/bin/python scripts/test-collect-coverage.py --update-docs` |
| 版本号一致 | `.venv/bin/python scripts/check-version-consistency.py [--fix]` |
| 端到端性能门禁 | `.venv/bin/python scripts/test-perf-report.py --gate` |

### 按域索引

| 域 | 代表脚本 | 什么时候用 |
|:---|:---------|:-----------|
| 测试 | `test-runner.py` / `test-collect-coverage.py` / `test-extract-failures.py` / `test-find-order-dependent.py` / `test-smoke-web.py` / `check-test-redundancy.py` / `check-test-markers.py` | 跑测试、统计覆盖、定位失败、用例质量机检 |
| 文档 | `check-doc-traces.py` / `check-doc-links.py` / `check-doc-drift.py` / `check-semantic-index.py` / `make-assets.py` / `make-screenshots.py` | 文档漂移、死链、语义命名、视觉资产（预览图生成 / 架构图渲染体检 / README 与手册演示截图） |
| 代码与文件质量 | `check-code-traces.py` / `check-requirement-trace.py` / `check-task-numbering.py` / `check-file-length.py` / `check-version-consistency.py` / `check-style-guardrails.py` / `check-script-contract.py` | 痕迹、需求追溯、编号、行数红线、版本、样式护栏 |
| 发布 | `release.py`（分步编排）/ `test-collect-coverage.py` | 发版全流程 |
| 运维观测 | `perf-history.py` / `probe.py` / `check-sources`（CLI 子命令）/ `doctor`（CLI 子命令）/ `view-logs`（CLI 子命令） / `cassettes`（CLI 子命令） | 性能历史查看、数据源链路探测、日志与系统自检 |
| 评测与基准 | `test-perf-report.py` / `eval-llm-hallucination.py` / `eval-factor-zoo.py` / `eval-dedup-threshold.py` | 性能门禁压测、LLM 幻觉率采样、能力评测与阈值校准（不参与提交门禁） |
| 启动 | `launch.sh` / `launch.ps1`（TUI 与 `web` 子命令）/ `cli.sh` / `llm.sh` 及其 `.ps1` 版 | 免解释器前缀的常用入口 |
| CLI 子命令 | `report` / `cache` / `whatif` / `config` / `check-sources` / `health-history` / `view-logs` / `doctor` / `cassettes` | 用户侧命令行入口（详见 [CLI 手册](../manuals/how-to-use-cli-mode.md)；`config` 为持久化配置编辑） |

> 改名/合并脚本时按**五处同步**自查（本次改名的长尾教训）：① 同名测试文件；② `scripts-reference` 一览与详情小节；③ `folders.md` 目录树；④ CI/钩子/`release.py`/`test-runner` 等调用点；⑤ 文档与代码注释里的命令示例。机检覆盖 ②③④（一览覆盖、目录树双向、脚本存在性），①⑤ 靠本清单。
>
> **结构规则**：`scripts/` 顶层只放可直接运行的入口；共享库进 `_shared/`，单入口实现放 `_<语义名>/`，评测实现包用 `_eval_<x>/` 与 `eval-<x>.py` 对应——新增共享代码不得放顶层文件。
>
> 新增脚本时：先按 [scripts-reference.md](scripts-reference.md)「命名约定」选前缀（`check-` 仅限可入门禁的检查、`test-`/`eval-`/`perf-`/`probe-`/`hook-`/`make-` 各归其域），再入对应域小节，并在上表「按域索引」里确认该域已覆盖。
## 关键纪律来源

本指南为面向开发者的"入口版"。以下完整纪律以 [CLAUDE.md](../../CLAUDE.md) 为准：

- **架构遵从**：所有模块必须遵守 `technical.md` 的「架构设计约束」表格（含设计目的/违反后果/适用范围）和「概要设计—核心架构决策」。涉及数据降级/熔断逻辑时额外参考概要设计双重降级治理体系说明
- **测试隔离**：运行测试不得修改用户的配置文件、持仓文件等敏感数据；`conftest.py` 自动将 `config.json` 和缓存目录重定向到临时目录
- **缺陷自测**：发现并修复缺陷时，**必须**为该缺陷编写可自测的回归测试用例，避免再次回退；新增功能时**必须**同步编写测试用例覆盖
- **目录结构同步**：新增/重命名任何非排除文件或目录时，**必须**同步更新 `folders.md` 中的目录树，并确保每个文件都有简短说明
- **文件归属三原则**：中间计划文件 → `docs/plan/`；运行时临时产物 → `docs/tmp/`；`.claude/` 全局目录只存放 Claude Code 工具自动管理的运行时数据，**禁止主动写入**任何文件
- **设计契约**：Web/报告 UI 改动（样式、token、组件状态、版式、空态文案）前先读 [DESIGN.md](DESIGN.md)（`docs/managements/`）——Colors 角色表 / Typography 字阶 / 组件六态 / 断点表 / Do-Don't 护栏 / 迭代指引；新增声明取自契约档位，验收见 `src/test/unit/report/test_design_doc.py`