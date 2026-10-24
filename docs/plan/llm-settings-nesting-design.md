# LLM 配置纵切设计（模块为第一层）

> **关联**：[`config-panel-design.md`](config-panel-design.md)（面板四域编排）；设计图样 [`config-panel-mockup/llm-config.html`](config-panel-mockup/llm-config.html)。
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
| **不做旧版兼容** | 结构以当前 `schema_version` 为准：其他结构不解析、不转换、不写适配分支，直接拒绝并提示重新生成 |
| **向前保留** | 不认识的段与键原样保留（未来字段不丢）；更高版本拒绝加载而非截断写回 |

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
                          "thinking": { "enabled": true, "budget": 12000, "effort": "medium" },
                          "debate": {
                            "procon": { "synthesis_temperature": 0.5 },
                            "conditional": { "scenarios": ["涨", "跌", "震荡"] },
                            "concentration_qa": { "threshold": 0.35 }
                          } },
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
    "daily_cost_limit": 0,
    "debate_limits": { "max_tokens_per_report": 72000, "call_timeout_override_sec": 90 }
  },

  // ── 高级选项：事实校验 / 新闻条数（与 features.json 无关）──
  "advanced": {
    "fact_check": { "tolerance": 1.0, "tolerance_overrides": { "expert_review": 2.0 } },
    "news_correlation": { "top_n": 10 }
  }
}
```

### 2.1 计价参考独立成文件（`llm_pricing_ref.json`）

模型单价与峰谷规则属**参考数据**：随供应商调价更新、与运行参数无关，不该混在用户调优的 `llm_settings.json` 里。

```jsonc
// data/config/llm_pricing_ref.json
{
  "version": 1,
  "currency": "CNY",
  "timezone": "Asia/Shanghai",
  "peak_periods": ["09:00-12:00", "14:00-18:00"],
  "idle_periods": [],
  "weekend_always_idle": true,
  "holiday_always_idle": true,
  "models": {
    "deepseek-flash": { "input_price": 0.5, "output_price": 1.0,
                        "peak": { "input_price": 1.0, "output_price": 2.0 } }
  }
}
```

- **结构**：判定策略（币种/时区/峰谷时段/周末与节假日规则）在顶层；**模型单价统一收进 `models`**，与策略键分层。
- **合并口径**：代码内置基础价 → 本文件逐模型覆盖（只覆盖出现的模型与字段），合并结果即运行时 `PRICING_MERGED`。
- **缺失/异常**：文件缺失 → 仅用内置价；单个模型条目非法 → 告警并跳过该条；`version` 不符 → 拒绝加载并提示重新生成。
- **编辑面**：不进 TUI/Web 配置面板（参考数据，不是开关）；需要改价时直接编辑文件。
- **演进**：与配置同理，不做旧版兼容；结构变更即重新生成该文件并同步改生成器。

规则：**模块段内出现即业务意图**（写了 `timeout: 90` 就是"这个模块要 90 秒"），未出现即继承 `defaults`。两个例外：

1. `enabled` **不参与继承**——各模块出厂默认不同（`self_review` / `news_correlation` 默认关），每个模块都必须显式声明。
2. `thinking.budget` / `thinking.effort` 在 `thinking.enabled = false` 时**保留**（临时关停不丢预算）。

---

## 3. 键位对照（重新生成参考）

程序**不读取**表左列键位。下表只说明同一业务值在新结构中的位置，供一次性重新生成时人工/脚本对照。

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

### 3.3 高级选项与计价参考（5 行映射）

| 扁平键（对外契约） | v2 位置 |
|:--|:--|
| `debate.procon` / `debate.conditional` / `debate.concentration_qa` | `modules.expert_review.debate.*`（智囊团生成选项） |
| `debate.max_total_tokens_per_report` / `debate.per_call_timeout_override` | `runtime.debate_limits.{max_tokens_per_report, call_timeout_override_sec}`（报告级预算） |
| `fact_check` | `advanced.fact_check` |
| `pricing` | 独立文件 `llm_pricing_ref.json`（策略置顶、模型单价收进 `models`） |
| `news_correlation_top_n` | `advanced.news_correlation.top_n` |

---

## 4. 读写契约

### 4.1 读：扁平视图契约

1. **版本校验**：`schema_version` 必须等于 2。缺失或不等于 2 → 拒绝加载并提示重新生成（不解释其他结构、不尝试猜测字段）。
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

`defaults.<参数>` 的取值必须是「该参数缺键时的实际生效值」（`_llm_settings_defaults` 的模块缺省值或下游 `.get(key, DEFAULT)` 的回落常量）。

切换验收（**开发期一次性对照，不进入产品代码**）：文件生成后，实际调用参数与切换基准（现行实现）（模型/温度/长度/超时/thinking 三件套/缓存/简报/提示词）逐项相等；参数段缺省的模块（`self_review` / `holding_change`）是重点核对对象。若有差异，修 `defaults` 取值。

### 4.5 缓存一致性：生成参数必须进指纹

模块缓存键为 `CACHE_PREFIX_LLM + 模块名 + 指纹`，指纹当前只哈希**提示词输入**（持仓/穿透/竞争语境/指标/数据质量/辩论后缀），不含 `temperature` / `max_tokens` / `thinking`。后果：调参后仍命中旧缓存，表现为「改了却看不到变化」。

规则：上述三项以**模块级生成参数摘要**的形式作为指纹输入（同一函数、预检侧与写侧共享），参数变更即产生新缓存键。代价是调参后首轮全量重算——这是正确行为，不做规避。

### 4.6 未知内容保留

| 情况 | 行为 |
|:--|:--|
| 不认识的段（如 `plugins`） | 原样保留（读时忽略、写时写回）+ WARNING |
| 模块段内不认识的参数 | 原样保留 + WARNING，使用侧忽略 |
| 未知模块名 | 保留该段，WARNING 列出该模块合法参数；`doctor` 报出 |
| `schema_version` 缺失、不等于 2 或高于支持值 | 拒绝加载并提示重新生成（不截断写回） |

---

## 5. 结构版本与重新生成

- **版本不符即拒绝**：`schema_version` 缺失或不等于 2 时，加载直接失败并给出明确指引（备份/删除文件 → 运行生成器）。不提供其他结构的解析、转换脚本或适配分支。
- **重新生成**：由默认配置生成器产出新文件——`config/_llm_settings_defaults._get_default_llm_settings_template()` 输出带注释的新结构；文件缺失时首次启动自动生成。
- **生成器同步**：结构变更与生成器改动在同一批完成；模板未更新视为改动未完成（生成出的文件与代码期望不一致）。
- **用户值不随重建携带**：需要保留个人设置时由用户按文档自行重设；程序的 `.bak` 只是通用写前备份，不承担兼容职责。
- **降级不保证**：当前结构在其他版本程序中不被识别，属预期行为；回退同样通过重新生成对应版本的模板文件完成。
- **缓存不兼容**：LLM 模块缓存（按模块前缀的 JSON）只按当前格式读取；结构版本不符即按前缀清理重建（`clear_by_group`），不做格式转换。

---

## 6. 校验与错误

| 场景 | 行为 |
|:--|:--|
| `defaults` / `modules` / `runtime` / `advanced` 不是对象 | 该段按空处理 + WARNING（其余段生效） |
| 模块参数类型/范围错误 | 读取回落默认 + WARNING；写入拒绝并说明范围（与 `edit_ops` 一致） |
| `defaults` 缺项 | 用内置默认补齐，不报错 |
| 未知段/未知键 | 保留 + WARNING |
| `schema_version` 缺失、≠2 或高于支持 | 拒绝加载并提示重新生成 |

**模块参数范围表**（加载与面板写入共用，越界即拒绝；缺失或非法值回落默认）：

| 参数 | 范围 | 说明 |
|:--|:--|:--|
| `temperature` | 0–2 | 超范围直达 API 会报错或产出异常 |
| `max_tokens` | 1–200000 | 0 或负数非法 |
| `timeout` | 5–600 | 秒 |
| `thinking.budget` | 1024–100000 | `enabled=false` 时保留但校验 |
| `thinking.effort` | low / medium / high | 枚举 |
| `debate.procon.synthesis_temperature` | 0–2 | 校验口径与其他参数一致 |
| `runtime.debate_limits.max_tokens_per_report` | 1024–500000 | 报告级上限 |
| `runtime.debate_limits.call_timeout_override_sec` | 5–600 | 单次辩论调用超时 |

实现位置：`core/data_registry.get_known_llm_settings_keys()` 提供**结构白名单**（合法段名 + 模块名 ∈ 注册表 + 参数名 ∈ 参数白名单 + `runtime`/`advanced` 子键白名单）；`config/_validation_llm.py` 负责 `modules` 子键校验，错误文案口径与面板一致。

---

## 7. 影响面

**代码（7 个文件）**

| 文件 | 改动 |
|:--|:--|
| `config/_llm_settings.py` | 版本校验、展平/反展平、三层缺省合并、未知内容保留、模块参数范围校验；不合并 `pricing`（由计价参考文件提供） |
| `config/_llm_settings_defaults.py` | 默认配置生成器输出新结构（含注释与 `defaults` 段、参数范围注释）；文件缺失时据此生成；模板不含 `pricing` |
| `config/_validation_llm.py` | 模块参数范围校验（温度/长度/超时/思考预算与 effort 枚举） |
| `llm/module_fingerprint.py` | 提供模块级「生成参数摘要」（temperature / max_tokens / thinking） |
| `config/_llm_pricing.py`（新增） | 读取/校验 `llm_pricing_ref.json`，与内置价逐模型合并；mtime 缓存与失效 |
| `llm/pricing.py` | 合并来源为 `llm_pricing_ref.json`（`PRICING_MERGED` / `reload_pricing` 接口不变） |
| `data/config/llm_pricing_ref.json`（新增） | 参考数据文件：策略 + 模型单价；缺失时仅用内置价 |
| `config/_validation_llm.py` | 模块子键校验改 `modules` |
| `core/data_registry.py` | 已知键白名单 → 结构白名单 |
| `config/edit_ops.py` | `llm_scalar` / `llm` 写入目标映射（对外键名固定） |
| `core/doctor.py` | 新增「llm_settings 结构版本」只读检查 |
| `config/__init__.py` | 若新增公开访问器（如 `get_llm_module_config`）在此 re-export |

**不改**：`llm/` 包全部实现（按扁平视图契约消费）、`config.json`、`features.json`、`llm_providers.json`、`llm_key.json`、面板渲染逻辑、CLI 参数名。

**文档**

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-config-llm.md` | 完整范例改模块段口径；全局参数表覆盖 `runtime`/`advanced`；「完整模型定价表」章节说明 `llm_pricing_ref.json`（策略 + `models`）；补两个文件的重新生成指引 |
| `manuals/how-to-config.md` | 配置项索引表中的 llm 键名 |
| `managements/llm-technical.md` | 全局键名清单 + 并发控制段落 + 「LLM 默认参数表」（`check-doc-drift` 第 7 项按 `_llm_settings_defaults` 校验，须同批改） |
| `managements/requirements.md` | 全局配置参数表（6 个调优键的落点） |
| `managements/testplan.md` | 配置解析覆盖（非当前结构拒绝、生成器输出、往返幂等、未知内容保留） |

**仓库内数据文件**：`data/config/llm_settings.json` 随实现落为 v2，提交说明标注结构变更。

**相邻事项（不在本设计范围）**：`config.json` 的 `preferred_provider` 为 `{}` 空壳，模块级偏好实际在 `llm_providers.preferred_providers` —— 职责重叠，记为待清理项，不与本设计混做。

**规模**：解析层约 250~350 行净增（含校验、指纹摘要与模板），测试 15~20 例。

---

## 8. 验证计划

1. **非当前结构拒绝**：放置其他结构文件 → 加载失败并提示重新生成，不静默回落默认。
2. **往返幂等**：读 → 写 → 读 → 写，第二次写出的内容与第一次逐字节相同。
3. **生成器输出**：删除文件后由生成器产出的内容与 `_llm_settings_defaults` 模板逐键一致（不含用户值）。
4. **三层优先级矩阵**：模块有值 / 模块缺省但 `defaults` 有值 / 两者都缺 → 内置默认，三种组合逐一断言。
5. **未知内容保留**：注入未知段与未知参数，写回后仍在。
6. **写路径映射**：面板保存 `llm_max_thinking_concurrency` → 文件落到 `runtime.thinking_concurrency`；`enabled_llm.x` → `modules.x.enabled`；重载后扁平视图同键生效。
7. **高版本保护**：`schema_version: 99` → 拒绝加载并给出明确错误。
7b. **参数范围**：`temperature: 5` / `max_tokens: 0` / `timeout: 3` → 加载回落默认并告警；面板写入被拒并提示范围。
7c. **指纹失效**：调整 `temperature` 或 `max_tokens` 后，同一模块的缓存键随之变化。
7d. **debate 归属**：`modules.expert_review.debate.*` 与 `runtime.debate_limits.*` 展平结果包含全部设计键。
7e. **计价参考**：`llm_pricing_ref.json` 缺失 → 使用内置价；单模型覆盖生效；非法条目被跳过并告警；`version` 不符被拒。
8. **人工**：删除旧文件 → 启动生成 → 面板保存一次，核对 `.bak`、结构版本与生成器输出。

---

## 9. 约束遵从

| 约束 | 遵从方式 |
|:--|:--|
| 指纹唯一事实来源 | 生成参数摘要由 `llm/module_fingerprint.py` 提供，预检侧与写侧共用同一函数 |
| 原子写 | 写入经 `atomic_write` 原语；`.bak` 为单槽通用备份 |
| 路径绝对化 | `llm_settings.json` / `llm_pricing_ref.json` 路径在配置层输出绝对路径 |
| 凭据分离 | 两个文件均不含凭据；凭据仍在 `llm_key.json` |
| 中文注释 | 生成器输出带分类与逐项中文注释；读取经统一注释剥离器 |
| 缓存统一 | 「不做旧版兼容」下缓存清理经 `cache/` 接口，不直接操作文件 |
