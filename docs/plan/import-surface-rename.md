# 跨模块导入面重命名 — 分析与迁移方案（未实施）

> **状态**：分析稿（立项 `plan-208`，**不包含实施**）
> **范围**：`src/python/` 内跨模块/跨渠道的 re-export 兼容层、私有模块导入与 `__all__` 公共面
> **关联**：`docs/managements/technical.md`（架构约束）、`docs/managements/developer-guide.md`（脚本与模块归属）、`scripts-reference.md`（命名约定）

---

## 1. 背景

config / core / analysis / report 等模块经过多轮拆分，实现被搬进叶子模块，但调用方与测试仍按旧路径导入。为不打断调用点，仓库保留了一批「兼容既有导入面」的转发：

实测盘点（本次分析时）：

| 指标 | 数量 |
|:--|--:|
| `兼容既有导入面` / `公开别名` / `私有名保留` 类注释 | 29 处 |
| `# noqa: F401`（大量为 re-export 转发） | 103 行 |
| `config/__init__.py` 的 `__all__` 中私有名（`_` 前缀） | 22 个 |

这不是单一模块的问题：同一个符号往往同时存在「实现模块」「转发模块」「包门面」三条导入路径，测试又可能 patch 其中一条——代码可读性与可维护性被导入面拖累。

## 2. 现象与风险

### 2.1 典型转发族

| 转发位置 | 实际实现 | 现状 |
|:--|:--|:--|
| `config/_validation.py` | `_validation_llm.py` / `_validation_sections.py` / `_validation_scalars.py` | 仅少量符号被 `config/__init__.py` 与 `_core.py` 使用，大部分转发无消费方 |
| `config/_comments.py` | `core/json_comments.py` | 公开名 + 私有名双别名；core 侧为打破循环而独立实现 |
| `config/__init__.py` | `_core.py` / `_validation.py` / `_config_api.py` / `_comments.py` | 包门面同时导出公开 API 与大量 `_` 私有名 |
| `analysis/__init__.py` | `prosperity_scoring.py` / `_prosperity_inputs.py` / `rebalance.py` / `_silence.py` 等 | 包门面与拆分模块名称不完全对应 |
| `core/registry.py` | `computation_registry.py` / `data_registry.py` | 注册表实现与门面同名混用 |
| `core/code_utils.py` / `core/doctor.py` | `code_symbols.py` / `doctor_logs.py` | 门面仅做兼容转发 |
| `cache/operations.py` | `_cache_refresh.py` | 公开面与私有实现同名转发 |
| `report/` 多个模块 | `_fund_rating.py` / `_holdings_detail_blocks.py` / `html_writer_status.py` 等 | 页面入口与实现分层的转发 |
| `web/handlers.py` | `run_generation.py` / `handlers_health.py` | 路由门面转发内部实现 |

### 2.2 风险

1. **patch 点歧义**：测试 patch 的是转发模块属性，生产代码从实现模块导入；`unittest.mock.patch` 对已绑定的名字不生效，容易出现「用例绿、真实链路仍走旧实现」。
2. **所有权模糊**：新增代码可能从私有实现模块导入，也可能从旧门面导入，二者逐渐分叉。
3. **死转发**：`# noqa: F401` 掩盖无人使用的 re-export，静态检查无法判断「保留的公共面」与「历史残留」。
4. **循环导入**：门面转发把实现模块的依赖方向隐藏，拆分时容易触发循环。
5. **文档与目录树漂移**：说明文字、设计文档、测试注释仍指向旧模块名。

## 3. 目标与非目标

### 目标

- 建立「**一个符号 → 唯一 owner 模块**」的所有权表；`grep` 能直接从调用点看出真实实现位置。
- 公共包门面只导出**已文档化的公共 API**；`__all__` 只列公共名，不含 `_` 私有名。
- 删除仅为兼容旧导入路径而存在的 re-export；测试 patch 点统一指向 owner 模块。
- 保留必要的**叶子实现包**内部转发（包内可见），不跨包暴露。

### 非目标

- 不改变运行时行为、配置结构、缓存格式或数据契约。
- 不重命名业务概念（语义名保持不变），只调整模块边界与导入面。
- 不处理 `src/test/` 内部辅助模块的导入面（除非它是生产导出面的镜像）。
- 不在本阶段引入新的运行时依赖。

## 4. 目标规则

1. **唯一 owner**：每个符号只有一个实现模块；其他同名导出必须是显式的公共门面，且带文档。
2. **门面只放公共面**：`__all__` 只列稳定公共 API；私有符号（`_x`）不出现在跨包 `__all__`。
3. **私有模块不跨包**：`_x.py` 只允许同包内导入；跨包使用必须提升为公开模块或通过公共门面。
4. **patch 点跟随 owner**：测试对符号打 patch 时，必须指向实际查询/调用该符号的模块；转发模块只在测试其门面行为时 patch。
5. **删除兼容标注**：删除 `兼容既有导入面` / `公开别名` / `私有名保留` 类转发后，同步删除对应的 `# noqa: F401`；剩余 `noqa` 必须有具体理由（循环导入、延迟导入、类型检查）。
6. **命名与文件一致**：公开模块名不含 `_`；实现细节放 `_x`；同一概念不在两个公开模块各暴露一份。

## 5. 盘点方法（可复跑）

```bash
# 兼容转发与公开别名
grep -rn "兼容既有导入面\|兼容既有引用\|公开别名\|私有名保留" src/python --include=*.py

# re-export 噪音
grep -rn "noqa: F401" src/python --include=*.py

# 跨包导入私有模块（owner 候选）
grep -rn "from src.python.[a-z_.]*_[a-z_]* import" src/python src/test --include=*.py

# 包门面私有导出
sed -n '/__all__ = \[/,/^\]/p' src/python/config/__init__.py | grep '"_'
```

## 6. 分阶段迁移（仅方案，不实施）

| 阶段 | 范围 | 动作 | 退出条件 |
|:--|:--|:--|:--|
| P0 | 本分析稿 | 产出「符号 → 唯一 owner → 旧导入路径 → 调用方/测试 patch 点」表 | owner 表评审通过 |
| P1 | `config` 包 | 先处理 `_validation` / `_comments` / `__init__` 门面：公共面收窄，调用方改 owner，删除死转发 | 包内导入无兼容注释；测试 patch 点对齐 |
| P2 | `core` + `cache` | `code_utils` / `doctor` / `registry` / `operations` 等门面去转发；处理 `core` ↔ `config` 的循环导入边界 | 无跨包私有导入；导入图无环 |
| P3 | `analysis` + `report` + `llm` + `web` | 拆分模块与页面入口统一 owner；`report` 内部转发按「章节入口/实现」重新归属 | 章节入口只从 owner 导入；测试 patch 全对齐 |
| P4 | 测试与文档 | 批量更新测试导入、`patch(...)` 路径、`folders.md` 目录树、设计文档与注释；清理 `noqa` | 存量守护全绿；文档无旧路径 |

每阶段独立提交、独立回滚；每阶段结束跑 `dev-verify` 与对应域的 `verify`，不一次性重写全部导入。

## 7. 验收标准

- `grep` 无「兼容既有导入面 / 公开别名 / 私有名保留」类转发（保留项需逐条在技术设计文档登记理由）。
- `config/__init__.py` 等公共门面的 `__all__` 不含 `_` 私有名。
- 生产代码不出现跨包 `from src.python.<pkg>._x import ...`（同包内部除外）。
- 测试 `patch("...旧门面...")` 的路径与 owner 模块一致；相关用例全绿。
- `check-code-traces` / `check-doc-drift` / `check-doc-links` / `check-requirement-trace` / `check-file-length` / `check-test-redundancy` 全绿；`folders.md` 目录树与统计同步。
- 可考虑新增 `check-import-surface.py`（`check-` 前缀、`_shared` CLI 契约）：扫描兼容转发注释、`noqa: F401` 与跨包私有导入，作为导入面的**单一护栏**——是否新增列入实施阶段决策。

## 8. 风险与开放决策

| 风险 / 决策 | 说明 | 建议 |
|:--|:--|:--|
| 公共门面是否保留 | `config`/`core/registry` 等门面有大量调用方；全删会改动过宽 | 保留**已文档化**的公共面，只删兼容转发 |
| 测试 patch 点 | 有些用例刻意 patch 门面验证转发 | 改为 patch owner；若测试目标就是门面，保留并注明 |
| 循环导入 | `config` ↔ `core.json_comments` 已用叶子模块打破 | 迁移时保持「core 不向上依赖 config」的方向，不反向引入 |
| 动态/延迟导入 | 部分处理器在函数内 `from ... import ...`，改名会改变 patch 语义 | 逐处核对导入时机，优先改调用点而非补 shim |
| 外部脚本 | 仓库未承诺第三方导入面 | 不保留兼容别名；仅更新仓内调用方 |

## 9. 明确不做

- 不修改任何业务逻辑、配置默认值、缓存键或数据结构。
- 不借这次重命名调整模块职责（职责调整需另立设计与任务）。
- 不在实施前删除任何现有转发；本文件只用于评审范围与顺序。
