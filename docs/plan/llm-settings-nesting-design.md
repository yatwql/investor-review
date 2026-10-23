# LLM 配置纵切设计（模块为第一层）

> **关联**：[`config-panel-taxonomy-design.md`](config-panel-taxonomy-design.md)（面板四域编排）；设计图样 [`config-panel-mockup/llm-config.html`](config-panel-mockup/llm-config.html)。
> **范围**：`data/config/llm_settings.json` 的组织方式（文件名与读取路径固定）、内存视图契约、校验、升级与文档口径。
> **不做**：改文件名/目录、改 `llm/` 包内任何调用、改写入语义（`.bak` 备份、范围校验、原子写）、改 `config.json` / `features.json` 的组织。

---

## 1. 目标与原则

| 原则 | 落点 |
|:--|:--|
| **一个业务对象在一处** | 一个 LLM 模块的全部设置（模型/温度/长度/超时/思考/提示词）收进同一段 |
| **缺省继承、只写差异** | 全模块同值的参数由 `defaults` 一次声明；模块段只写与缺省不同的项 |
| **文件结构 = 面板分区** | `runtime` 段对应面板「LLM 运行」域的调优参数；`modules.<m>` 对应章节启停与模块设置；`advanced` 对应增强与费用 |
| **确定性** | 同一份扁平输入恒产出同一份文件（可 diff、写入幂等、不依赖数据分布） |
| **前向兼容** | 不认识的段与键原样保留；高版本文件拒绝加载而非截断写回 |

---

## 2. 文件结构（schema v2）

```jsonc
{
  "schema_version": 2,

  // ── 缺省：所有模块继承；模块内只写差异（取值 = 参数缺键时的生效值）──
  "defaults": {
    "model": null,                 // null = 用线路默认模型
    "temperature": 0.3,
    "max_tokens": 3072,
    "timeout": 60,
    "cache": true,
    "output_brief": false,
    "system_prompt": null,         // null = 用内置提示词
    "thinking": { "enabled": false, "budget": null, "effort": null }
  },

  // ── 模块：一个业务对象一段，启停也在段内 ────────────────
  "modules": {
    "global_macro":     { "enabled": true, "temperature": 0.2 },
    "expert_review":    { "enabled": true, "max_tokens": 4096,
                          "thinking": { "enabled": true, "budget": 12000, "effort": "medium" } },
    "news_correlation": { "enabled": true, "max_tokens": 3000, "timeout": 90 },
    "health_check":     { "enabled": true, "thinking": { "enabled": true, "budget": 6000 } },
    "penetration_deep": { "enabled": true, "max_tokens": 6000, "timeout": 120 },
    "self_review":      { "enabled": true },      // 无差异：参数继承缺省
    "holding_change":   { "enabled": true }
  },

  // ── 运行约束：并发/重试/预算（＝面板「LLM 调优参数」）──
  "runtime": {
    "max_concurrency": 3,
    "thinking_concurrency": 2,
    "max_retries": 2,
    "full_fail_retry_delay_sec": 30,
    "time_budget_sec": 0,
    "daily_cost_limit": 0
  },

  // ── 高级选项：辩论/事实校验/计价/新闻条数（与 features.json 无关）──
  "advanced": {
    "debate": { "concentration_qa": { "threshold": 0.35 } },
    "fact_check": { },
    "pricing": { },
    "news_correlation": { "top_n": 10 }
  }
}
```

规则：**模块段内出现即业务意图**（写了 `timeout: 90` 就是"这个模块要 90 秒"），未出现即继承 `defaults`。两个例外：

1. `enabled` **不参与继承**——各模块出厂默认不同（`self_review` / `news_correlation` 默认关），每个模块都必须显式声明。
2. `thinking.budget` / `thinking.effort` 在 `thinking.enabled = false` 时**保留**（临时关停不丢预算）。

---

## 3. 键位映射（兼容读取用）

### 3.1 模块参数（10 参数 × 模块）

| 扁平键 | v2 位置 |
|:--|:--|
| `temperature_<m>` / `model_<m>` / `max_tokens_<m>` / `timeout_<m>` / `output_brief_<m>` / `system_prompt_<m>` | `modules.<m>.<同名去后缀>` |
| `cache_enabled_<m>` | `modules.<m>.cache` |
| `thinking_enabled_<m>` | `modules.<m>.thinking.enabled` |
| `thinking_budget_<m>` | `modules.<m>.thinking.budget` |
| `reasoning_effort_<m>` | `modules.<m>.thinking.effort` |
| `enabled_llm.<m>` | `modules.<m>.enabled` |

### 3.2 运行约束（6 项）

| 扁平键（对外契约） | v2 位置 |
|:--|:--|
| `llm_max_concurrency` | `runtime.max_concurrency` |
| `llm_max_thinking_concurrency` | `runtime.thinking_concurrency` |
| `max_retries` | `runtime.max_retries` |
| `llm_full_fail_retry_delay` | `runtime.full_fail_retry_delay_sec` |
| `llm_total_time_budget_sec` | `runtime.time_budget_sec` |
| `daily_cost_limit` | `runtime.daily_cost_limit` |

### 3.3 高级选项（4 项）

| 扁平键（对外契约） | v2 位置 |
|:--|:--|
| `debate` | `advanced.debate` |
| `fact_check` | `advanced.fact_check` |
| `pricing` | `advanced.pricing` |
| `news_correlation_top_n` | `advanced.news_correlation.top_n` |

---

## 4. 读写契约

### 4.1 读：扁平视图契约

1. **版本判定**：有 `schema_version` 取之为版本号；无版本号但出现 `modules` / `defaults` / `runtime` / `advanced` 任一段 → 按 2 载入并记一行 INFO；否则按 v1 载入。
2. **展平**：无论磁盘结构，`get_llm_config()` 始终返回**扁平视图**（`model_expert_review`、`thinking_enabled_health_check`、`enabled_llm`、`llm_max_concurrency`、`debate` …）。`llm/` 包与面板全部按此契约消费，不感知磁盘结构。
3. **三层取值**：`modules.<m>.<参数>` → `defaults.<参数>` → 内置默认。
4. 展平对"`defaults` 与内置默认都没有"的参数**不生成键**，保留下游回落路径。

### 4.2 写：反展平与幂等

1. 收到扁平视图 → 反展平为 v2：与 `defaults` 等值的项不写进模块段；`defaults` 未覆盖的参数补入 `defaults`。
2. 写前单槽 `.bak` 备份（`copy_file_atomic` 原语），文件直接落为 v2，不保留并存结构。
3. `runtime` / `advanced` 的写入经共享白名单与范围校验；`edit_ops` 对外键名固定（仍是 `llm_max_thinking_concurrency` 等），写入层做 `扁平键 → runtime.<新名>` 与 `enabled_llm.<m> → modules.<m>.enabled` 的映射。
4. **幂等**：读 → 写 → 读 → 写，第二次写出的内容与第一次逐字节相同。

### 4.3 `defaults` 的来源（唯一两条）

1. **模板生成**：取 `_llm_settings_defaults` 的内置默认值；模块段写与之不同的项。
2. **用户编辑**：用户改 `defaults`，所有未写差异的模块立即按新默认值生效。

程序**不做**按各模块取值的众数/均值推断——那会让写回结果依赖数据分布与遍历顺序，破坏幂等与可 diff。

### 4.4 补全等价约束

`defaults.<参数>` 的取值必须是"该参数缺键时的实际生效值"（`_llm_settings_defaults` 的模块缺省值或下游 `.get(key, DEFAULT)` 的回落常量）。验收口径：**v1 与 v2 两种载入方式下，每个模块的实际调用参数（模型/温度/长度/超时/thinking 三件套/缓存/简报/提示词）逐项相等**；参数段缺省的模块（`self_review` / `holding_change`）是重点核对对象。若有差异，修 `defaults` 取值而非放宽验证。

### 4.5 未知内容保留

| 情况 | 行为 |
|:--|:--|
| 不认识的段（如 `plugins`） | 原样保留（读时忽略、写时写回）+ WARNING |
| 模块段内不认识的参数 | 原样保留 + WARNING，使用侧忽略 |
| 未知模块名 | 保留该段，WARNING 列出该模块合法参数；`doctor` 报出 |
| `schema_version` 高于支持值 | 拒绝加载并提示升级（不截断写回） |

---

## 5. 结构升级与回滚

- **升级触发**：首次写入（任一面板保存或显式命令）即落为 v2，写前自动 `.bak`；记 INFO：`[config] llm_settings 结构升级 v1 → v2（模块 7 个，写入 N 个键）`。
- **降级风险**：v2 的段名不在 v1 的键白名单内，降级运行会把这些段当作未知键、参数回落默认。因此：
  - `how-to-config-llm.md` 提示：升级后如需回退，先还原 `llm_settings.json.bak` 再运行。
  - `doctor` 只读检查「llm_settings 结构版本 = v1 / v2」，v1 时提示"下次保存自动升级"。
- **回滚**：还原 `.bak` 即回到 v1；两种结构都能载入。

---

## 6. 校验与错误

| 场景 | 行为 |
|:--|:--|
| `defaults` / `modules` / `runtime` / `advanced` 不是对象 | 该段按空处理 + WARNING（其余段生效） |
| 模块参数类型/范围错误 | 读取回落默认 + WARNING；写入拒绝并说明范围（与 `edit_ops` 一致） |
| `defaults` 缺项 | 用内置默认补齐，不报错 |
| 未知段/未知键 | 保留 + WARNING |
| `schema_version` 高于支持 | 拒绝加载并提示升级 |

实现位置：`core/data_registry.get_known_llm_settings_keys()` 提供**结构白名单**（合法段名 + 模块名 ∈ 注册表 + 参数名 ∈ 参数白名单 + `runtime`/`advanced` 子键白名单）；`config/_validation_llm.py` 负责 `modules` 子键校验，错误文案口径与面板一致。

---

## 7. 影响面

**代码（7 个文件）**

| 文件 | 改动 |
|:--|:--|
| `config/_llm_settings.py` | 版本判定、展平/反展平、三层缺省合并、未知内容保留、升级日志 |
| `config/_llm_settings_defaults.py` | 模板生成输出 v2（含注释与 `defaults` 段） |
| `config/_validation_llm.py` | 模块子键校验改 `modules` |
| `core/data_registry.py` | 已知键白名单 → 结构白名单 |
| `config/edit_ops.py` | `llm_scalar` / `llm` 写入目标映射（对外键名固定） |
| `core/doctor.py` | 新增「llm_settings 结构版本」只读检查 |
| `config/__init__.py` | 若新增公开访问器（如 `get_llm_module_config`）在此 re-export |

**不改**：`llm/` 包全部实现（按扁平视图契约消费）、`config.json`、`features.json`、`llm_providers.json`、`llm_key.json`、面板渲染逻辑、CLI 参数名。

**文档**

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-config-llm.md` | 完整范例改模块段口径；全局参数表覆盖 `runtime`/`advanced`；补升级/回滚提示 |
| `manuals/how-to-config.md` | 配置项索引表中的 llm 键名 |
| `managements/llm-technical.md` | 全局键名清单 + 并发控制段落 + 「LLM 默认参数表」（`check-doc-drift` 第 7 项按 `_llm_settings_defaults` 校验，须同批改） |
| `managements/requirements.md` | 全局配置参数表（6 个调优键的落点） |
| `managements/testplan.md` | 配置解析覆盖（v1/v2 载入、往返幂等、未知内容保留） |

**仓库内数据文件**：`data/config/llm_settings.json` 随实现落为 v2，提交说明标注结构变更。

**规模**：解析层约 250~350 行净增（含校验与模板），测试 15~20 例。

---

## 8. 验证计划

1. **扁平视图等价**：同一份 v1 文件，v1 与 v2 两种载入下 `get_llm_config()` 逐键相等（快照对比，浮点用容差）。
2. **往返幂等**：读 → 写 → 读 → 写，第二次写出的内容与第一次逐字节相同。
3. **缺省模块等价**：`self_review` / `holding_change` 在两种载入下实际调用参数逐项相等。
4. **三层优先级矩阵**：模块有值 / 模块缺省但 `defaults` 有值 / 两者都缺 → 内置默认，三种组合逐一断言。
5. **未知内容保留**：注入未知段与未知参数，写回后仍在。
6. **写路径映射**：面板保存 `llm_max_thinking_concurrency` → 文件落到 `runtime.thinking_concurrency`；`enabled_llm.x` → `modules.x.enabled`；重载后扁平视图同键生效。
7. **高版本保护**：`schema_version: 99` → 拒绝加载并给出明确错误。
8. **人工**：用真实文件跑一次面板保存，核对 `.bak`、`doctor` 版本项与升级日志。
