# 跨模块导入面重命名 — 分析与迁移方案（未实施）

> **状态**：分析稿（立项 `plan-208`，**不包含实施**）
> **范围**：`src/python/` 内跨模块/跨渠道的 re-export 兼容层、私有模块导入与 `__all__` 公共面
> **关联**：`docs/managements/technical.md`（架构约束）、`docs/managements/developer-guide.md`（脚本与模块归属）、`scripts-reference.md`（命名约定）

---

## 1. 结论摘要

1. 问题存在但**不是「把所有 re-export 删掉」**：`noqa: F401` 中有相当一部分是合法的类型/副作用/惰性导入；必须按「**它是否只是转发到另一个模块**」分流，而不是按关键字批量删除。
2. 主要收益不在代码行数，而在**可定位性与测试可信度**：patch 点与 owner 对齐后，能消除「用例绿、真实链路仍未被覆盖」的一类盲区。
3. 建议按 **P0 owner 表 → config → core/cache → analysis/report/llm/web → 测试与文档** 五阶段推进；每阶段独立提交、独立回滚，不做 flag day。
4. 本稿只做分析与方案；所有代码、配置、缓存、数据格式保持不变。

## 2. 基线盘点（分析时快照）

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

### 2.1 消费者面

| 消费者 | 实测 | 对迁移的含义 |
|:--|:--|:--|
| `scripts/` 深层/私有导入 | **37 条** | owner 表必须覆盖脚本（`_doc_drift` / `_eval_halluc_sampler` / `_eval_factor_zoo` / `_screenshots` 等） |
| 测试 patch 命中候选 | **110 条** | 只作为候选集，需按「patch 目标是否为转发模块」逐条分类；不能把 110 当作待改数 |
| 文档中的转发/私有模块路径 | **8 文件 / 20 处**（不含本分析稿） | P4 需同步 `folders` / `technical` / `requirements` / `llm-technical` / 设计稿 |
| 动态导入 | **2 文件 / 6 处** | `source_adapter`（`module_name`）与 `chain_incremental`（`module_path`）改名需同步字符串 |

### 2.2 重点热点

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
| I6 | 文档/目录树滞后 | 设计文档、注释、`folders.md` 仍指向转发模块 | 接手者按旧路径找代码 |

## 4. 目标与非目标

### 目标

- 建立「**一个符号 → 唯一 owner 模块**」所有权表；调用点能直接看出真实实现位置。
- 公共包门面只导出**已文档化的公共 API**，`__all__` 不含 `_` 私有名（保留项逐条登记理由）。
- 删除仅用于兼容历史导入路径的 re-export；测试 patch 点统一跟随 owner。
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
7. **删除即删除**：不保留 deprecated 别名、不做双写窗口；仓内调用点与文档同步更新（项目按无兼容别名策略执行）。

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

产出：`符号 | owner 模块 | 兼容导入路径 | 生产者调用点 | 测试 patch 点 | 处置（保留门面/删除转发/提升公开）`。
覆盖优先级：`config.__all__` 的 22 个私有名（分默认值/状态/校验常量三类）、31 处跨包私有导入（`web/config_edit` 6 / `llm/prompts_action` 4 / `startup_wizard` 4 优先）、103 行 F401 中疑似 re-export 的条目，以及 `scripts/` 的私有导入（`_doc_drift` / `_eval_halluc_sampler`）。
owner 表必须包含列：`符号 | owner 模块 | 兼容导入路径 | 生产调用点 | 测试 patch 点 | 脚本消费者 | 处置 | 例外理由`。示例行：`invalidate_config_cache | config/_core.py | config/__init__.py | tui/handlers_config.py, web/... | 无 | scripts/test-smoke-web.py | 保留公开名、删除私有别名 | -`。
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

- 批量更新测试导入与 `patch(...)` 字符串；更新 `folders.md` 目录树、设计文档与代码注释中的转发路径。
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
| 995 处局部导入被过度上提 | 中 / 中 | 只处理与迁移符号相关的局部导入，其余保留 |
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

## 附录 A — 复跑盘点命令

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
