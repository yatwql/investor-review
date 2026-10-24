# 跨模块导入面重命名 — 分析与迁移方案（未实施）

> **状态**：分析稿（立项 `plan-208`，**不包含实施**；经 80 轮复盘后的定稿）
> **范围**：`src/python/` 内跨模块/跨渠道的 re-export 兼容层、私有模块导入与 `__all__` 公共面
> **关联**：`docs/managements/technical.md`（架构约束）、`docs/managements/developer-guide.md`（脚本与模块归属）、`scripts-reference.md`（命名约定）

---

## 1. 结论摘要

1. 问题存在但**不是「把所有 re-export 删掉」**：`noqa: F401` 中有相当一部分是合法的类型/副作用/惰性导入；必须按「**它是否在替代一个旧导入路径**」分流，而不是按关键字批量删除。
2. 主要收益不在代码行数，而在**可定位性与测试可信度**：patch 点与 owner 对齐后，能消除「用例绿、真实链路仍走旧实现」的一类盲区。
3. 建议按 **P0 owner 表 → config → core/cache → analysis/report/llm/web → 测试与文档** 五阶段推进；每阶段独立提交、独立回滚，不做 flag day。
4. 本稿只做分析与方案；所有代码、配置、缓存、数据格式保持不变。

## 2. 基线盘点（本次分析快照）

| 指标 | 实测 | 口径 |
|:--|--:|:--|
| 兼容性注释（`兼容既有导入面` / `兼容既有引用` / `公开别名` / `私有名保留`） | **23 行 / 17 文件** | 四类关键词按行并集计（分项相加会重复计重叠行） |
| `noqa: F401` | **103 行 / 41 文件** | 其中仅一部分为兼容 re-export，需逐条分类 |
| `config/__init__.py` 的 `__all__` | **60 项，其中 22 项为 `_` 私有名** | AST 解析 `__all__` |
| 跨包私有模块导入 | **31 处 / 18 文件** | `from src.python.<pkg>._x import`（跨包、含函数内导入） |
| 函数内局部导入 | **995 处** | 多为打破循环/延迟可选依赖，不能一律上提 |
| 动态导入 | **6 处 / 2 文件** | `importlib` / `import_module`，改名需同步字符串 |
| 包级 import 候选环 | **7 组** | 仅看模块顶层语句（排除 `TYPE_CHECKING` 与函数内导入）；仍需逐条复核，不能直接判违规 |

复跑命令见附录 B。计数会随代码演进变化，实施前须以当次快照为准。

### 2.1 消费者面（本轮补充实测）

| 消费者 | 实测 | 对迁移的含义 |
|:--|:--|:--|
| `scripts/` 深层/私有导入 | **37 条** | owner 表必须覆盖脚本（`_doc_drift` / `_eval_halluc_sampler` / `_eval_factor_zoo` / `_screenshots` 等） |
| 测试 patch 命中候选 | **110 条** | 只作为候选集，需按「patch 目标是否为转发模块」逐条分类；不能把 110 当作待改数 |
| 文档中的旧模块路径 | **8 文件 / 20 处**（不含本分析稿） | P4 需同步 `folders` / `technical` / `requirements` / `llm-technical` / 设计稿 |
| 动态导入 | **2 文件 / 6 处** | `source_adapter`（`module_name`）与 `chain_incremental`（`module_path`）改名需同步字符串 |

### 2.2 重点热点（本轮补充实测）

- **`config.__all__` 的 22 个私有名**分三类：配置默认值/路径与模板（`_DEFAULT_CONFIG` / `_CONFIG_FILE` / `_get_default_config_template` 等）、缓存与失效状态（`_clear_config_cache` / `_config_cache` / `_config_mtime` / `_config_size` / `_config_lock` / LLM 同名缓存六项）、校验常量（`_KNOWN_*` / `_STRING_CONFIG_KEYS`）。私有**状态变量**不应作为公共 API；需要读状态时提供函数，不导出变量本身。
- **跨包私有导入热点**：`web/config_edit.py` 6 处、`llm/prompts_action.py` 4 处、`startup_wizard.py` 4 处；其余分布在 `fetcher/chain.py`、`tui/handlers_config.py`、`analysis/_rebalance_deviation.py` 等，共 31 处 / 18 文件。
- **动态导入字符串**：`fetcher/source_adapter.py`（`module_name`）、`fetcher/chain_incremental.py`（`module_path`，3 处）——模块改名必须同步字符串并用导入 smoke 覆盖。
- **测试 patch 转发模块的实例**：`report.fund_performance.write_fund_performance_sheet`、`cache.operations.update_basic_cache` / `update_position_cache`、`core.doctor.run_doctor_checks` 等；P0 需建立完整 patch 清单，不能只改生产导入。
- **脚本也是消费者**：`scripts/_doc_drift/_format.py` 导入 `config._config_defaults` / `_llm_settings_defaults`，`scripts/_eval_halluc_sampler` 导入 `llm.fact_checker._runner` / `_utils`；owner 表须覆盖 `scripts/`，不能只扫 `src/`。
- **文档引用需同步**：`folders.md` / `technical.md` / `requirements.md` / `llm-technical.md` 仍以 `code_utils`、`json_comments`、`_cache_refresh`、`doctor_logs` 等为路径锚点；P4 统一更新，避免代码与文档各说一套。

## 3. 问题模型

| 编号 | 问题 | 具体表现 | 影响 |
|:--:|:--|:--|:--|
| I1 | shim 与 owner 双路径 | 同一符号在实现模块、转发模块、包门面都能导入 | 新代码选择不确定，读写分叉 |
| I2 | patch 点错位 | 测试 patch 转发模块属性，生产代码从实现模块导入 | 用例通过但未覆盖真实路径（假绿） |
| I3 | 死转发 | `noqa: F401` 掩盖无人消费的 re-export | 公共面虚胖、静态检查失效 |
| I4 | 循环依赖被转发隐藏 | 门面把依赖方向折叠，拆分时才暴露 | 导入期崩溃或延迟导入蔓延 |
| I5 | 私有名进入公共面 | `config.__all__` 含 22 个 `_` 私有名 | 公共 API 边界失真，外部误依赖 |
| I6 | 文档/目录树滞后 | 设计文档、注释、`folders.md` 仍指向旧模块 | 接手者按旧路径找代码 |

## 4. 目标与非目标

### 目标

- 建立「**一个符号 → 唯一 owner 模块**」所有权表；调用点能直接看出真实实现位置。
- 公共包门面只导出**已文档化的公共 API**，`__all__` 不含 `_` 私有名（保留项逐条登记理由）。
- 删除仅用于兼容旧导入路径的 re-export；测试 patch 点统一跟随 owner。
- 保留合法的惰性/循环导入（附理由），不把 995 处局部导入当成债务一次性上提。

### 非目标

- 不改运行时行为、配置结构、缓存格式、数据契约。
- 不重命名业务概念（语义名保持），只调整模块边界与导入面。
- 不清理测试内部辅助模块的私有导入（除非它是生产导出面的镜像）。
- 不引入新运行时依赖，不做跨仓库 API 兼容承诺。

## 5. 所有权与导入规则

1. **owner 定义**：一个公开符号只有一个实现模块；包 `__init__` 可以作为公共门面，但必须显式声明且不复制实现。
2. **公共面**：`__all__` 只列稳定公共 API；私有符号不跨包导出。确需保留的私有名（如测试/工具入口）在技术设计文档登记原因与替代路径。
3. **私有模块**：`_x.py` 只允许同包内导入；跨包使用必须提升为公开模块或经公共门面，并通过 `check-channel-layering` 的同类约束。
4. **导入方向**：以现有分层为准（`core`/`schemas` 为底，`config`/`analysis`/`fetcher`/`providers`/`report`/`llm`/`qa`/`tui`/`web`/`cli` 依次向上）；新增跨层边必须在 §7 矩阵中登记，禁止用门面转发掩盖反向依赖。
5. **局部导入**：函数内导入只在「破环 / 可选依赖 / 避免导入期副作用」三种场景保留，并在代码注释写明原因；其余按 owner 移到模块顶部。
6. **测试 patch**：patch 目标必须是**实际查询/调用该符号的模块**；测试门面转发行为时才 patch 门面，并在用例 docstring 注明「测门面」。
7. **删除即删除**：不保留 deprecated 别名、不做双写窗口；仓内调用点与文档同步更新（项目明确不保留旧导入兼容）。

## 6. 迁移设计（不实施）

### 阶段工作量概览（按包，实测基线）

| 包 | 兼容注释 | `noqa: F401` | 迁移优先级 |
|:--|--:|--:|:--|
| `config` | 6 | 12 | P1 |
| `core` | 3 | 6 | P2 |
| `cache` | 2 | 1 | P2 |
| `analysis` | 3 | 22 | P3 |
| `report` | 5 | 35 | P3（F401 重灾区） |
| `llm` | 1 | 18 | P3 |
| `web` | 2 | 4 | P3 |
| `providers` | 1 | 4 | P3 |
| `tui` | 0 | 1 | P3（跨渠道） |

> 数字是**待分类的上限**，不等于删除数；F401 中合法类型/副作用/惰性导入不计入迁移。

### P0 — owner 表

产出：`符号 | owner 模块 | 旧导入路径 | 生产者调用点 | 测试 patch 点 | 处置（保留门面/删除转发/提升公开）`。
覆盖优先级：`config.__all__` 的 22 个私有名（分默认值/状态/校验常量三类）、31 处跨包私有导入（`web/config_edit` 6 / `llm/prompts_action` 4 / `startup_wizard` 4 优先）、103 行 F401 中疑似 re-export 的条目，以及 `scripts/` 的私有导入（`_doc_drift` / `_eval_halluc_sampler`）。
owner 表必须包含列：`符号 | owner 模块 | 旧导入路径 | 生产调用点 | 测试 patch 点 | 脚本消费者 | 处置 | 例外理由`。示例行：`invalidate_config_cache | config/_core.py | config/__init__.py | tui/handlers_config.py, web/... | 无 | scripts/test-smoke-web.py | 保留公开名、删除私有别名 | -`。
退出条件：owner 表评审通过；每个拟删除项都有调用点/测试/脚本清单；例外项登记理由、替代路径与复核期限；导入 smoke 与 patch 扫描命令已就绪。

### P1 — `config` 包

- `_validation.py`：确认哪些转发仍被 `config/__init__.py` / `_core.py` 使用；公共面收窄，死转发删除。
- `_comments.py`：统一到 `core/json_comments.py` 的唯一公开名；私有别名按调用点迁移。
- `__init__.py`：22 个私有名按三类处置——默认值/模板类收敛为公开访问器；缓存/失效状态类改为函数读取（不导出变量）；校验常量仅保留确有消费的项。仅测试使用的移出 `__all__`，删除无消费项。
- 退出条件：`config` 内无兼容转发注释；公共 `__all__` 无私有名（或例外表全绿）；`unit_config` + `verify` 全绿。

### P2 — `core` + `cache`

- `code_utils` / `doctor` / `registry` / `cache.operations` 等门面：符号迁到 owner，调用点改 owner，删除转发。
- 检查 `config ↔ analysis`、`analysis ↔ fetcher`、`fetcher ↔ analysis` 的顶层候选环，按实际导入时机区分「真实环 / 延迟导入」；不得靠新增转发绕环。
- 退出条件：跨包私有导入清单清零（例外表除外）；导入图无新增环；`unit_core` / `unit_scripts` 绿。

### P3 — `analysis` + `report` + `llm` + `web`

- `analysis` 包：拆分模块与包门面名称对齐；`prosperity_scoring` / `rebalance` / `metrics` 的转发按 owner 归位。
- `report`：35 行 F401 重灾区；按「章节入口 / 实现」重新归属，页面入口只从 owner 导入。
- `llm` / `web`：`web/config_edit.py`（6 处）、`llm/prompts_action.py`（4 处）、`startup_wizard.py`（4 处）等跨包私有导入优先处理。
- 退出条件：各域 `unit_*` + `verify` 绿；测试 patch 点审计清单清零或登记例外。

### P4 — 测试、文档与护栏

- 批量更新测试导入与 `patch(...)` 字符串；更新 `folders.md` 目录树、设计文档与代码注释中的旧路径。
- 清理 `noqa: F401`（保留项写具体理由：循环/类型/副作用/惰性）。
- 新增 `check-import-surface.py`（可选）：扫描兼容注释、跨包私有导入、公共 `__all__` 私有名；采用 `_shared/checklib` 契约，先观察期后入门禁（决策见 §8）。
- 退出条件：§7 指标全部达标；十守护 + 文档守护全绿。

## 7. 验收指标

| 指标 | 目标 |
|:--|:--|
| 兼容性转发注释 | 0（例外表登记项除外） |
| 跨包私有模块导入 | 0（例外表登记项除外） |
| `config.__all__` 私有名 | 0（或 ≤ 登记例外数） |
| 测试 patch 到转发模块 | 0（「测门面」用例须有 docstring 标记） |
| `noqa: F401` | 仅保留有具体理由的导入；数量下降且逐条可解释 |
| 包级 import 环 | 不新增；存量环按复核结果登记处置 |
| 门禁 | `dev-verify` / `verify` / 文档与结构守护全绿 |

### 7.1 `check-import-surface.py` 规格（建议，未实施）

| 规则 | 判据 | 处理 |
|:--|:--|:--|
| IS1 兼容注释 | 四类关键词出现在 `src/python` | 发现即 finding（例外表除外） |
| IS2 公共 `__all__` 私有名 | 包门面 `__all__` 中的 `_` 项 | 发现即 finding（例外表除外） |
| IS3 跨包私有导入 | 跨包 `from src.python.<pkg>._x import` | 发现即 finding（叶子/循环例外表） |
| IS4 动态导入目标 | `importlib.import_module` 的目标字符串是否指向现存模块 | 仅提示，无法静态判断改名前后的等价性 |

实现须复用 `_shared/checklib`（`-v/--ci`、退出 0/2）；例外表放独立 JSON（`reason` / `owner` / `expiry` / `replacement`），先观察期（与 `check-script-contract` 同模式）再评估入门禁。patch 错位不做机检（静态难以判定），用 P0 清单 + 域测试兜底。

## 8. 风险登记与收益

### 风险

| 风险 | 概率/影响 | 缓解 |
|:--|:--|:--|
| patch 点改漏，出现假绿 | 中 / 高 | P0 建 patch 清单；每阶段跑对应域用例 + `test-check-*`；抽查 `mock.patch` 目标 |
| 循环导入在导入期暴露 | 中 / 高 | 先做 P2 环复核；局部导入保留理由；每阶段单独提交、可回滚 |
| 动态导入字符串未同步 | 低 / 高 | 6 处清单逐条改；增加导入 smoke 测试 |
| 公共 API 收窄误伤仓内调用 | 中 / 中 | owner 表列调用方；先改调用点再删导出；例外表 |
| 995 处局部导入被过度上提 | 中 / 中 | 只处理与本次 owner 相关的局部导入，其余保留 |
| 文档/目录树漂移 | 中 / 低 | 每阶段跑 `check-doc-drift` / `check-doc-links`；P4 统一收口 |
| 一次性大改导致 review 困难 | 高 / 中 | 五阶段 + 每包小批次；不做 flag day |

### 收益

- **测试可信度**：patch 点对齐后，消除 re-export 造成的假绿；这是最直接的质量收益。
- **可定位性**：`grep` 一个符号即可找到 owner，减少「同名多入口」的认知成本。
- **公共面收敛**：22 个私有 `__all__` 项与死转发清理后，外部依赖面可审计。
- **循环依赖可见**：把转发隐藏的依赖边显式化，降低后续拆分风险。
- **文档一致性**：目录树/设计文档与代码路径同步，降低接手成本。

## 9. 开放决策（实施前确认）

| 决策 | 建议 |
|:--|:--|
| 是否保留包门面 | 保留已文档化公共面；其余转发删除。不新增兼容别名。 |
| 是否允许例外清单 | 允许，但必须写明「为何不能归 owner + 替代路径 + 复核期限」，并纳入护栏。 |
| 是否新增 `check-import-surface` | 建议新增，先观察期（与 `check-script-contract` 同模式），稳定后再评估入门禁。 |
| 是否在发布窗口实施 | 不建议；这是纯重构，避开 release/gate 窗口，避免与数据/配置变更混批。 |
| 是否改测试目录结构 | 不改；只改导入与 patch 点。 |

## 10. 明确不做

- 不修改业务逻辑、配置默认值、缓存键、数据契约。
- 不借重命名调整模块职责（职责调整另立设计）。
- 不在本阶段删除任何现有转发；本文件只用于评审范围与顺序。

## 附录 A — 80 轮复盘记录

| 轮次 | 复盘焦点 | 本轮改进 | 收益 | 风险 / 代价 |
|:--:|:--|:--|:--|:--|
| 1 | 基线数字 | 纠正 29→26 处兼容注释；确认 `__all__` 60/22；补充计数口径 | 分析可信 | 旧数字失效，需重跑 |
| 2 | 环数量 | 粗扫 130 组 → 仅顶层语句 7 组，排除 `TYPE_CHECKING` 与函数内导入 | 避免误判 | 真实环仍需人工复核 |
| 3 | F401 分类 | 区分 re-export / 类型 / 副作用 / 惰性导入 | 防止误删 | 分类需逐条读代码 |
| 4 | owner 定义 | 从「模块级」细化为「符号级」 | 归属唯一 | 包门面需例外 |
| 5 | 公共面 | 明确 `__all__` 只列公共 API；私有名例外登记 | API 可审计 | 仓内调用需同步 |
| 6 | patch 点 | 增加「patch 必须指向 owner」规则与假绿案例 | 测试可信 | 需更新大量 patch 字符串 |
| 7 | 局部导入 | 995 处不全上提，限定三种保留理由 | 避免制造环 | 需要注释纪律 |
| 8 | 动态导入 | 6 处清单化，要求字符串同步 + smoke 测试 | 迁移完整 | 易漏 |
| 9 | 导入方向 | 增加分层方向与跨层登记要求 | 防止反向依赖 | 例外表维护成本 |
| 10 | 私有导出 | 22 个 `__all__` 私有名分类处置 | 收缩公共面 | 可能影响测试入口 |
| 11 | 迁移顺序 | 先 config，再 core/cache，再 analysis/report | 降低爆炸半径 | 跨包依赖需穿插 |
| 12 | 批次与回滚 | 每包独立提交、可回滚，不做 flag day | 可 bisect | 中间态可能短暂不绿 |
| 13 | 测试策略 | 增加 import smoke 与 `__all__` 契约测试设计 | 提前暴露导入错误 | 测试维护成本 |
| 14 | 护栏设计 | `check-import-surface` 采用 `_shared/checklib`、观察期先行 | 防回归 | 规则误报 |
| 15 | 护栏接入 | 不直接进 pre-commit，先观察期 + CI 兜底 | 不阻塞开发 | 观察期约束弱 |
| 16 | 验收指标 | 全部改成可数、可复跑指标 | 可判定完成 | 指标可能被规避 |
| 17 | 例外机制 | 建立「理由 + 替代路径 + 复核期限」三元组 | 防止永久豁免 | 例外表可能膨胀 |
| 18 | 风险分级 | 按概率/影响列风险与缓解 | 排期依据 | 主观概率 |
| 19 | 收益量化 | 用 patch 假绿、私有导出、死转发三个可数收益 | 立项说服力 | 无法量化全部收益 |
| 20 | 文档同步 | 增加 technical/folders 同步与检查 | 防漂移 | 文档 churn |
| 21 | 导入测试 | 增加导入期 smoke 与公共面断言 | 防环/防缺名 | 导入副作用需隔离 |
| 22 | 阶段门槛 | 每阶段列出 grep/AST/测试三条退出条件 | 可执行 | 命令需维护 |
| 23 | 命名规范 | 公共模块无 `_`、实现细节 `_x` | 降低歧义 | 重命名范围扩大 |
| 24 | 私有符号 | 不强行全删，例外需登记替代路径 | 避免破坏测试 | 公共面仍留小口 |
| 25 | 跨渠道 | 把 TUI/Web/CLI 的跨渠道私有导入纳入 P3 | 防渠道耦合 | 需协调三渠道测试 |
| 26 | 发布协调 | 明确避开 release 窗口；不改配置/数据 | 降低风险 | 排期受限 |
| 27 | 结论措辞 | 删除「无环」过度断言，改为候选环复核 | 结论可信 | 结论不如口号简洁 |
| 28 | 术语统一 | 统一 shim / facade / owner / patch point | 减少歧义 | 纯文档成本 |
| 29 | 实施清单 | 增加每阶段「改调用点→删转发→跑门禁」顺序 | 防漏删/先删后改 | 执行力依赖 reviewer |
| 30 | 最终准入 | 增加开放决策与 go/no-go 前置 | 决策清晰 | 仍需 owner 表评审 |
| 31 | 私有导出分类 | 把 `config.__all__` 22 个私有名分成默认值/状态/校验常量三类；状态变量不导出 | 公共面可收窄 | 需要新增读取函数 |
| 32 | 脚本消费者 | owner 表覆盖 `scripts/`，记录 `_doc_drift` / `_eval_halluc_sampler` 的私有导入 | 避免漏改脚本 | 脚本测试面扩大 |
| 33 | patch 实例 | 加入 `fund_performance` / `cache.operations` / `core.doctor` 等真实 patch 样例 | patch 审计有靶子 | 改动用例数量增加 |
| 34 | 文档引用 | 把 `folders` / `technical` / `requirements` / `llm-technical` 的旧路径列入 P4 | 文档同步 | 文档 churn |
| 35 | 动态导入 | 精确到 2 文件 6 处，要求改字符串 + 导入 smoke | 迁移完整 | smoke 可能触发副作用 |
| 36 | 局部导入范围 | 明确只处理 owner 相关局部导入，不追求清零 995 处 | 避免无谓改动 | 指标变成定性 |
| 37 | 真实环 | 列出 `config↔analysis` / `analysis↔fetcher` 候选，要求按导入时机复核 | 不误删惰性导入 | 复核成本 |
| 38 | owner 表交付物 | 规定列（符号/owner/旧路径/调用点/测试 patch/处置）与评审门槛 | P0 可执行 | 表维护成本 |
| 39 | 例外政策 | 为 `_comments` 叶子、`TYPE_CHECKING` 等建立「理由+替代+期限」例外 | 不误删 | 例外表膨胀 |
| 40 | 公共面契约测试 | 设计「`__all__` 每项可解析、无私有名」测试 | 防回退 | 约束公共 API 演进 |
| 41 | patch 扫描自动化 | 给出 grep/AST 扫描 patch 目标的命令 | 可复跑 | 字符串匹配误报 |
| 42 | 导入 smoke | 设计 import 全模块 smoke（排除 side-effect 已知项） | 捕捉导入期错误 | 可能触发外部依赖 |
| 43 | 阶段例外 | 承认 config→analysis 跨阶段依赖，允许例外并登记 | 排期可行 | 例外协调 |
| 44 | 回滚纪律 | 禁止半删 shim；每阶段可 revert 且树保持绿 | 降低回滚风险 | review 粒度更细 |
| 45 | 文档路径 | 文档锚点同步列为 P4 退出条件 | 接手者不迷路 | 文档工作量 |
| 46 | 凭据边界 | 明确导入面重命名不改变 key/凭据路径；私有凭据不进入公共名 | 安全边界清晰 | 需核对配置入口 |
| 47 | 导入耗时 | 要求按阶段记录 import 时间与导入副作用 | 防性能回退 | 测量噪声 |
| 48 | 跨渠道 | 把 TUI/Web/CLI 私有导入纳入 P3，保留渠道分层测试 | 防渠道耦合 | 三渠道联调 |
| 49 | 发布窗口 | 明确避开 release/gate；不改配置/数据 | 降低发布风险 | 排期弹性变差 |
| 50 | 最终准入 | 汇总 owner 表、例外、指标、阶段门槛为 go/no-go 清单 | 决策可审计 | 仍需人工评审 |
| 51 | 计数口径 | 四类关键词改按行并集（23）而非分项相加（26），避免重复计数 | 基线可信 | 旧数字需改 |
| 52 | 脚本消费者 | 盘点出 `scripts/` 37 条深层导入，纳入 owner 表 | 不漏脚本 | 脚本测试面扩大 |
| 53 | patch 候选 | 110 条命中降级为候选集，要求按转发模块逐条分类 | 不虚增工作量 | 人工triage |
| 54 | 文档引用 | 统计 8 文件 / 20 处旧模块路径，列入 P4 | 文档同步 | 文档 churn |
| 55 | 公共状态变量 | 缓存/失效状态改为访问函数，不导出私有变量 | 公共面稳定 | 需新增函数 |
| 56 | owner 表示例 | 补一条完整示例行，固定列语义 | 可执行 | 示例可能过时 |
| 57 | 阶段工作量 | 按包列出兼容注释/F401 上限，确定 P1~P3 优先级 | 排期有据 | 上限非实际删除数 |
| 58 | 真实环复核 | 7 组候选环要求按导入时机复核，不直接删除 | 防误删 | 复核成本 |
| 59 | 类型导入 | `TYPE_CHECKING` 导入不计入环与护栏 | 减少误报 | 规则例外 |
| 60 | 通配导入 | 检查 `import *`，新代码禁止使用 | 公共面清晰 | 存量改造 |
| 61 | 护栏规格 | IS1~IS4 规则、退出码、观察期 | 可落地 | 规则误报 |
| 62 | 护栏例外 | 例外 JSON 含理由/owner/期限/替代路径 | 防永久豁免 | 维护成本 |
| 63 | 导入 smoke | 设计全模块导入脚本与副作用排除清单 | 捕捉导入错误 | 副作用风险 |
| 64 | 公共面契约 | 设计 `__all__` 可解析 + 无私有名测试 | 防回退 | 约束 API 演进 |
| 65 | 脚本迁移 | CLI 入口/字符串/脚本测试纳入 P4 | 防脚本断链 | 脚本回归 |
| 66 | 文档单一来源 | owner 表只放分析/技术文档一处，其他文档链接引用 | 防漂移 | 文档维护 |
| 67 | 状态访问器 | 为 `_config_cache` 等设计读函数而非直接导出变量 | 封装完整 | 改调用点 |
| 68 | 阶段门槛 | 每阶段固定 grep/AST/域测试三条退出条件 | 可验收 | 命令需更新 |
| 69 | 门面原子性 | `__init__` 删除导出与调用点更新同一提交，禁止半删 | 回滚安全 | 提交粒度变大 |
| 70 | 无外部兼容 | 明确不保留 deprecation 别名/双写窗口 | 边界清晰 | 外部使用者需自改 |
| 71 | 导入耗时 | 只记录各阶段 import 时间与副作用，不做性能优化 | 有观测 | 测量噪声 |
| 72 | 凭据边界 | 重命名不触碰 key/凭据路径，私有凭据不进入公共名 | 安全 | 需核对配置入口 |
| 73 | 跨渠道 | TUI/Web/CLI 私有导入纳入 P3，保留分层测试 | 防渠道耦合 | 三渠道联调 |
| 74 | 发布协调 | 避开 release/gate 窗口，不改配置/数据 | 降低风险 | 排期受限 |
| 75 | review 协议 | 每阶段限定 diff 范围与 reviewer 清单 | 可审 | 流程成本 |
| 76 | 收益排序 | 优先 patch 假绿与 config 私有导出，暂缓纯改名 | 性价比 | 部分债务延后 |
| 77 | 指标自动化 | 用单一审计脚本输出基线，避免手工数字漂移 | 可复跑 | 脚本维护 |
| 78 | 术语统一 | 固定 shim / facade / owner / patch point 用法 | 沟通清晰 | 文档成本 |
| 79 | 开放决策收敛 | 对公共门面、护栏、发布窗口给出默认建议 | 决策快 | 仍需拍板 |
| 80 | 最终准入 | 80 轮结论汇总为 go/no-go + 残余风险 | 可审计 | 仍需 owner 表评审 |



## 附录 B — 复跑盘点命令

```bash
# 兼容转发与公开别名
grep -rn "兼容既有导入面\|兼容既有引用\|公开别名\|私有名保留" src/python --include=*.py

# re-export 噪音
grep -rn "noqa: F401" src/python --include=*.py

# 跨包私有模块导入
grep -rn "from src.python.[a-z_.]*_[a-z_]* import" src/python src/test --include=*.py

# 包门面私有导出
python - <<'PY'
import ast
from pathlib import Path
tree = ast.parse(Path("src/python/config/__init__.py").read_text(encoding="utf-8"))
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets):
        values = ast.literal_eval(node.value)
        print("total", len(values), "private", len([v for v in values if v.startswith("_")]))
PY
```

> 说明：以上均为分析命令，不会修改代码；数量以实施当日快照为准。
